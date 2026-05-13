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
app.py                  — Main Flask application, route definitions
db.py                   — SQLite schema + query helpers
deploy.py               — Contract deployment script (Foundry/web3.py)
add_liquidity.py        — Liquidity management helper
requirements.txt        — Python dependencies
.env                    — Environment variables (never commit)
```

### Data Flow — Remittance

```
Frontend                Backend                 Partner API
   │                       │                        │
   │── POST /send/payout ──▶│                        │
   │   (wallet, amount,     │                        │
   │    signature, bank)    │                        │
   │                        │── Verify signature     │
   │                        │── Validate bank code   │
   │                        │── Check partner status │
   │                        │                        │
   │                        │── POST /transfer ─────▶│
   │                        │   (amount, bank, name) │
   │                        │                        │
   │                        │◀── { reference, status}│
   │                        │                        │
   │                        │── Write to SQLite      │
   │◀── { status, ref } ───│                        │
   │                        │                        │
   │  (partner webhook) ────│──────────────────────▶│
   │                        │◀── { status: success } │
   │                        │── Update TX status     │
```

### Database Schema

```sql
-- Swap records
CREATE TABLE transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet       TEXT    NOT NULL,
    tx_type      TEXT    NOT NULL,  -- 'swap' | 'send'
    from_token   TEXT,
    to_token     TEXT,
    amount_in    REAL,
    amount_out   REAL,
    rate         REAL,
    tx_hash      TEXT,
    created_at   TEXT    DEFAULT (datetime('now'))
);

-- Send/remittance records
CREATE TABLE sends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet          TEXT    NOT NULL,
    amount_usdc     REAL    NOT NULL,
    currency        TEXT    NOT NULL,
    country_code    TEXT    NOT NULL,
    recipient_name  TEXT    NOT NULL,
    account_number  TEXT    NOT NULL,
    bank_code       TEXT,
    reference       TEXT    UNIQUE,
    partner_ref     TEXT,
    status          TEXT    DEFAULT 'pending',
    payout_amount   REAL,
    rate_used       REAL,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX idx_transactions_wallet ON transactions(wallet);
CREATE INDEX idx_sends_wallet        ON sends(wallet);
CREATE INDEX idx_sends_reference     ON sends(reference);
```

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
├── Public IP: 129.80.199.123
│
├── Nginx
│   ├── Serves static HTML files
│   └── Reverse proxies /api/* to Flask:5000
│
├── Gunicorn (WSGI)
│   └── Flask app (4 workers)
│
├── systemd
│   └── kudi-arc.service (auto-restart on failure)
│
├── UFW Firewall
│   ├── 22/tcp (SSH)
│   ├── 80/tcp (HTTP)
│   └── 443/tcp (HTTPS — mainnet only)
│
└── SQLite
    └── /var/lib/kudi-arc/kudi.db
```

### Planned (Mainnet)

```
Production VM (dedicated)
├── PostgreSQL 15
│   └── Separate DB host with daily backups
├── Redis
│   └── FX rate cache (replaces in-memory)
├── Nginx + Certbot SSL
│   └── api.kudiarc.app
├── Gunicorn (8+ workers)
└── Systemd + monitoring (Prometheus/Grafana or UptimeRobot)
```

---

## Security Architecture

See [SECURITY.md](./SECURITY.md) for the full security policy.

**Key design decisions:**

- **No private keys on server** — all transaction signing happens in the user's wallet. The backend never holds custody.
- **Signature verification** — remittance requests are authorized by EIP-191 wallet signatures, not API tokens.
- **On-chain event log** — every admin action (rate change, withdrawal) is permanently recorded on Arc Network.
- **Timelocks as circuit breakers** — 5-minute rate timelock + 24-hour withdrawal timelock give users reaction time.

---

## Sequence Diagrams

### Complete Remittance Flow

```
User     Frontend    Backend    KudiSwap     Bitnob
 │           │           │          │           │
 │──Connect──▶│           │          │           │
 │           │──getRate──▶│          │           │
 │           │◀──rate─────│          │           │
 │──InputSend▶│           │          │           │
 │           │──approve───────────────▶│          │
 │           │◀──txHash───────────────│          │
 │           │──sign msg──▶(wallet)   │          │
 │           │◀──signature─│          │          │
 │           │──POST /payout─▶│       │          │
 │           │           │──verifySign│          │
 │           │           │──POST transfer────────▶│
 │           │           │◀──{ ref, pending }─────│
 │           │◀──{ ref }──│           │          │
 │──ShowRef──│           │           │          │
 │           │           │◀──webhook(success)────│
 │           │           │──updateDB  │          │
```

---

*For deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).*  
*For API reference, see [API.md](./API.md).*
