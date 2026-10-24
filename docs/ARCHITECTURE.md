# Kudi Arc — System Architecture

**Version:** 1.0  
**Network:** Arc Testnet (Chain ID 5042002)  
**Last Updated:** March 2026

---

## Overview

Kudi Arc is a three-layer hybrid system: an EVM smart contract layer for on-chain FX swaps, a Python/Flask backend layer for off-chain coordination and fiat bridging, and an HTML/JS frontend layer for user interaction. The layers are loosely coupled — the smart contracts are fully self-contained, the backend is stateless for most read operations, and the frontend operates independently of the backend for all on-chain actions.

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│          MetaMask / Rabby Wallet  ·  Arc Testnet Network        │
└───────────────────────────┬─────────────────────────────────────┘
                            │  EIP-1193 Provider
┌───────────────────────────▼─────────────────────────────────────┐
│                      FRONTEND (PWA)                             │
│                                                                 │
│   index.html          send.html           yield.html            │
│   FX Swap UI          Remittance UI       Yield UI              │
│                                                                 │
│   Ethers.js v6 · Wallet connect · Live rate display             │
│   Reads contract state directly · Signs transactions            │
└──────────┬────────────────────────┬────────────────────────────┘
           │ REST API               │ ethers.js RPC calls
           │                        │
┌──────────▼──────────┐   ┌────────▼──────────────────────────────┐
│   FLASK BACKEND     │   │         ARC NETWORK (EVM)             │
│                     │   │                                       │
│  FX rates oracle    │   │  KudiSwap V2                          │
│  Fiat payout logic  │   │  0x8a10D0e61201000B5456EC725165892B08 │
│  TX history DB      │   │  832C5f                               │
│  Partner API calls  │   │                                       │
│  SQLite (testnet)   │   │  USDC · EURC · USYC                   │
│                     │   │  (Circle native tokens)               │
└──────────┬──────────┘   └───────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                   FIAT SETTLEMENT LAYER                         │
│                                                                 │
│   Bitnob (NGN)    Flutterwave (KES/GHS/ZAR/TZS/UGX/RWF/XOF/XAF/NGN)       │
│   Paystack (fallback)                                               │
│                                                                 │
│   Webhook callbacks · Reference tracking · Status polling      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Smart Contracts

### KudiSwap V2

The core on-chain component. A single Solidity contract that holds USDC and EURC liquidity and executes swaps at a rate set by the protocol owner.

**State variables:**

```
usdcToken      : IERC20   — 0x3600000000000000000000000000000000000000
eurcToken      : IERC20   — 0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a
rate           : uint256   — USDC/EURC rate × 1e6 (e.g. 863800 = 0.8638)
feeBps         : uint256   — fee in basis points (default: 30 = 0.30%)
accruedFees    : uint256   — accumulated USDC fees (separate from liquidity)
pendingRate    : uint256   — rate queued by timelock
rateUpdateTime : uint256   — timestamp when pending rate becomes active
owner          : address   — current owner
pendingOwner   : address   — two-step ownership transfer target
_locked        : bool      — reentrancy guard
```

**Swap execution flow (USDC → EURC):**

```
1. User calls approve(KudiSwap, amount) on USDC contract
2. User calls swapUSDCforEURC(amountIn, minAmountOut)
3. Contract checks: not locked, sufficient EURC pool balance
4. fee = amountIn × feeBps / 10000
5. netIn = amountIn - fee
6. amountOut = netIn × rate / 1e6
7. Require: amountOut >= minAmountOut (slippage check)
8. accruedFees += fee
9. SafeERC20.transferFrom(user, contract, amountIn)
10. SafeERC20.transfer(user, amountOut)
11. Emit Swap event
```

**Rate update flow (timelocked):**

```
1. Owner calls setRate(newRate)
2. Require: newRate within absolute bounds (0.5e6 – 2.0e6)
3. Require: newRate within relative bounds (±20% of current rate)
4. pendingRate = newRate
5. rateUpdateTime = block.timestamp + 300 (5 minutes)
6. Emit RateUpdateQueued event
7. After 5 minutes: applyRate() makes pending rate active
```

### Token Contracts (Circle)

All tokens are Circle-issued, first-class on Arc Network:

| Token | Address | Decimals |
|-------|---------|----------|
| USDC | `0x3600000000000000000000000000000000000000` | 6 |
| EURC | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` | 6 |
| USYC | `0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C` | 6 |

---

## Layer 2 — Backend (Flask)

### Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.10 |
| Framework | Flask |
| WSGI server | Gunicorn |
| Web server | Nginx (reverse proxy) |
| Database | SQLite (testnet) → PostgreSQL (mainnet) |
| Process manager | systemd |
| FX data | Open Exchange Rates API |

### Module Structure

```
app.py              — Flask app: rates, countries, history, yield, health, admin settings
kudisend.py         — KudiSend: challenge, quote, confirm, order status, admin order endpoints
payouts.py          — Payout partners (Flutterwave, Bitnob, Paystack) and result verification
webhooks.py         — Partner webhooks: authenticate, re-verify with the partner, update order
swapverify.py       — Reads swaps from the chain before recording them
adminauth.py        — Owner-signed, single-use, request-bound admin authentication
db.py               — SQLite schema + helpers (orders, nonces, shared settings)
deploy.py           — Contract deployment script (Foundry/web3.py)
add_liquidity.py    — Liquidity management helper
src/                — Solidity sources (KudiSwapV2, KudiYield, KudiSendEscrow)
test/ · tests/      — Foundry tests (contracts) · pytest suite (backend)
.env                — Environment variables (never commit)
```

### Data Flow — Remittance (escrow)

```
Frontend            Backend              Escrow contract       Partner API
   │                   │                       │                    │
   │─ challenge ──────▶│ one-time message      │                    │
   │◀─ message ────────│                       │                    │
   │─ sign + quote ───▶│ verify signature,     │                    │
   │                   │ price (exact decimals)│                    │
   │◀─ locked quote ───│ ref, amount, expiry   │                    │
   │                                           │                    │
   │─ approve + deposit(token, amount, ref) ──▶│                    │
   │                   │                       │                    │
   │─ confirm(tx) ────▶│── read receipt + ────▶│                    │
   │                   │   deposits(ref)       │                    │
   │                   │── claim order once    │                    │
   │                   │── transfer ───────────────────────────────▶│
   │◀─ order status ───│                       │                    │
   │                   │◀── webhook ──────────────────────────────  │
   │                   │── re-check with partner, update order      │
   │                   │                       │                    │
 Owner wallet          │                       │                    │
   │─ settle(refs) / refund(ref) ────────────▶│  (signed in wallet) │
   │─ chain-sync ─────▶│ copy result to DB     │                    │
```

If a sender never confirms, the owner's **reconcile** finds the deposit by its on-chain event. If the owner does nothing, the sender can call `claimRefund` after 72 hours.

### Database Schema

```sql
-- History of swaps and sends (shown in the app)
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tx_type TEXT, wallet TEXT,
    from_token TEXT, to_token TEXT, amount_in REAL, amount_out REAL, fee REAL,
    rate REAL, ngn_equiv REAL, tx_hash TEXT,
    recipient_name TEXT, recipient_bank TEXT, recipient_account TEXT, recipient_phone TEXT,
    bitnob_ref TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_tx_hash_unique ON transactions(tx_hash) WHERE tx_hash IS NOT NULL;

-- One row per KudiSend order (the source of truth for payouts)
CREATE TABLE send_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id TEXT UNIQUE NOT NULL, ref TEXT UNIQUE NOT NULL, wallet TEXT NOT NULL,
    token TEXT, token_address TEXT, amount_base INTEGER, fee_base INTEGER,
    rate TEXT, payout_amount TEXT, country_code TEXT, currency TEXT, method TEXT,
    recipient_name TEXT, bank_code TEXT, bank_name TEXT, account_number TEXT, phone TEXT,
    status TEXT NOT NULL DEFAULT 'quoted',   -- quoted | payout_pending | completed | refund_required | payout_unknown | refunded
    tx_hash TEXT UNIQUE, provider TEXT, provider_ref TEXT, error TEXT,
    chain_state TEXT NOT NULL DEFAULT 'none',  -- none | settled | refunded
    expires_at INTEGER, created_at INTEGER, updated_at INTEGER
);

-- Single-use values
CREATE TABLE send_challenges (nonce TEXT PRIMARY KEY, wallet TEXT, message TEXT, expires_at INTEGER, used INTEGER);
CREATE TABLE admin_nonces    (nonce TEXT PRIMARY KEY, expires_at INTEGER, used INTEGER);

-- Admin settings shared by every worker
CREATE TABLE kv_state (ns TEXT, key TEXT, value TEXT, PRIMARY KEY (ns, key));
```

Order status changes are atomic (`UPDATE … WHERE status = …`) so concurrent requests cannot pay an order twice.

### FX Rate Caching

Rates are fetched from Open Exchange Rates API and cached in memory for 5 minutes. The cache refresh is triggered on the first request after expiry (lazy refresh). On mainnet, Redis will replace in-memory caching for multi-worker consistency.

```
Request → Check cache age
              │
        < 5 min? ──Yes──▶ Return cached rates
              │
             No
              │
        Fetch from OXR API
              │
        Update cache + timestamp
              │
        Return rates
```

---

## Layer 3 — Frontend

Three single-page HTML files, each using Ethers.js v6 for wallet and contract interaction. No build step required — pure HTML/CSS/JS.

| File | Purpose |
|------|---------|
| `index.html` | FX swap interface (KudiSwap) |
| `send.html` | Remittance interface (KudiSend) |
| `yield.html` | Yield interface (KudiYield) |

### Wallet Connection Flow

```
1. User clicks "Connect Wallet"
2. Frontend calls window.ethereum.request({ method: 'eth_requestAccounts' })
3. Checks chain ID — if not Arc Testnet (5042002), calls wallet_addEthereumChain
4. Arc Testnet added automatically with correct RPC/explorer config
5. ethers.BrowserProvider wraps the injected provider
6. UI updates with wallet address and live balances
```

### Swap Flow (Frontend → Contract)

```javascript
// 1. Get preview (no gas)
const preview = await contract.previewSwapUSDCtoEURC(amountIn);

// 2. Approve USDC spend
const usdc = new ethers.Contract(USDC_ADDRESS, ERC20_ABI, signer);
await usdc.approve(KUDISWAP_ADDRESS, amountIn);

// 3. Execute swap with slippage (0.5% tolerance)
const minOut = preview * 995n / 1000n;
const tx = await contract.swapUSDCforEURC(amountIn, minOut);
await tx.wait();

// 4. Record swap in backend
await fetch('/api/swap/record', { method: 'POST', body: JSON.stringify({...}) });
```

---

## Infrastructure

### Current (Testnet)

```
Oracle Cloud Free Tier VM
├── Ubuntu 22.04 LTS
├── 1 OCPU / 1GB RAM / 47GB storage
├── Public IP: <server IP>
│
├── Nginx
│   ├── Serves static HTML files
│   └── Reverse proxies /api/* to Flask:5001
│
├── Gunicorn (WSGI)
│   └── Flask app (2 workers)
│
├── systemd
│   └── kudi-arc.service (auto-restart on failure)
│
├── UFW Firewall
│   ├── 22/tcp (SSH)
│   ├── 80/tcp (HTTP)
│   └── 443/tcp (HTTPS)
│
└── SQLite
    └── kudi.db (next to db.py, or the path in DB_PATH)
```

### Planned (Mainnet)

```
Production VM (dedicated)
├── PostgreSQL 15
│   └── Separate DB host with daily backups
├── Redis
│   └── FX rate cache (replaces in-memory)
├── Gunicorn (8+ workers)
└── Systemd + monitoring (Prometheus/Grafana or UptimeRobot)
```

---

## Security Architecture

See [SECURITY.md](./SECURITY.md) for the full security policy.

**Key design decisions:**

- **No private keys on the server.** Deposits are verified by reading the chain; settle and refund are signed by the owner's wallet. The backend never holds custody or a signing key.
- **Escrow, not trust.** A sender's funds sit in `KudiSendEscrow` until the payout is verified, and can always be reclaimed after 72 hours.
- **Locked, signed quotes.** Fee, rate and payout are fixed server-side for 10 minutes; the deposit must match the quote exactly (wallet, token, amount, reference).
- **Owner-only admin.** Every admin request carries a single-use nonce and a signature bound to the exact request. Admin is disabled if `OWNER_ADDRESS` is unset.
- **Webhooks are triggers, not truth.** They are authenticated (and rejected when unconfigured), then re-checked with the partner before an order changes.
- **No double payouts.** A partner timeout never triggers a second partner; the order is held for review.
- **On-chain event log.** Every admin action on the contracts is permanently recorded on Arc Network.
- **Timelocks as circuit breakers.** 5-minute rate timelock + 24-hour withdrawal timelock on KudiSwap give users reaction time.

---

## Sequence Diagrams

### Complete Remittance Flow

```
User     Frontend    Backend      Escrow      Partner
 │          │           │            │           │
 │─Connect─▶│           │            │           │
 │─Input───▶│           │            │           │
 │          │─challenge▶│            │           │
 │          │◀─message──│            │           │
 │          │─sign msg─▶(wallet)     │           │
 │          │─quote────▶│ verify sig │           │
 │          │◀─locked───│            │           │
 │          │─approve + deposit(ref)▶│           │
 │          │◀─txHash───────────────│           │
 │          │─confirm──▶│─read chain▶│           │
 │          │           │◀─deposit ok│           │
 │          │           │─transfer──────────────▶│
 │          │◀─status───│            │           │
 │          │           │◀─webhook──────────────│
 │          │           │─re-check with partner─▶│
 │          │           │─update order           │
 │ Owner────────────────────settle / refund────▶│
```

---

*For deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).*  
*For API reference, see [API.md](./API.md).*
