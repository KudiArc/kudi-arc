[🌍 Project Overview](https://intro.kudiarc.xyz)

# 🟡 Kudi Arc

### Stablecoin FX & Remittance for Africa — Built on Arc Network

**Built on Arc Network · Powered by Circle USDC & EURC**

[![Release](https://img.shields.io/github/v/release/KudiArc/kudi-arc?style=for-the-badge&color=27AE74)](https://github.com/KudiArc/kudi-arc/releases/latest)
[![Testnet](https://img.shields.io/badge/Testnet%20-Live-27AE74?style=for-the-badge)](https://kudiarc.xyz/)
[![Contract](https://img.shields.io/badge/Contract-Verified-27AE74?style=for-the-badge)](https://explorer.testnet.arc.io/address/0x8a10D0e61201000B5456EC725165892B08832C5f)
[![Scan](https://img.shields.io/badge/Security%20Scan-SolidityScan-F5A623?style=for-the-badge)](https://solidityscan.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=for-the-badge)](https://discord.gg/nEJfqrAsqc)

---

> **Swap USDC ↔ EURC · Send to 10 African countries (sandbox payouts) · Earn yield via USYC**
>
> *Running on Arc Testnet. No real money moves yet.*

---

## What is Kudi Arc?

Kudi Arc is an Africa-first stablecoin FX desk and remittance engine built on **Arc Network** — Circle's EVM Layer 1, where gas is paid in USDC. No ETH. Just USDC.

We target three problems in African finance:

| Problem | Our approach |
|---------|-------------|
| Limited, expensive access to hard-currency FX | On-chain USDC ↔ EURC swaps with a 0.30% fee |
| Sub-Saharan Africa is the most expensive region in the world to send money to (World Bank) | Crypto-to-local-currency payouts to 10 countries (sandbox on testnet), service fee 0.8%–4.5% by corridor |
| Few accessible USD-denominated yield options | Tokenized T-bill yield via Circle USYC |

**It combines:** On-chain stablecoin swaps · Off-chain fiat settlement · Yield on idle balances

---

## Live Stats — Arc Testnet (as of 11 October 2026)

| Metric | Value |
|--------|-------|
| On-chain swaps (KudiSwap V2 counter) | 71,000+ |
| Wallets recorded by the app | 500+ |
| Swap volume recorded by the app | $129,000+ USDC-equivalent |
| Sandbox payouts processed | 390+ (test mode — no real funds moved) |
| KudiYield TVL | 11,877 USYC |
| Swap pool | 34,598 USDC · 402 EURC |

> Testnet figures. Wallet, volume and payout counts come from the app's own database; swap count and pool/TVL balances are read from the contracts.

---

## Features

### ⇄ FX Swap (KudiSwap)
- Swap USDC ↔ EURC at protocol-set rates, refreshed from live FX data
- **0.30% swap fee**
- Slippage protection (`minAmountOut`) enforced on-chain
- 5-minute timelock on every rate change
- NGN equivalent shown on the swap page

### 📤 Send Money (KudiSend)
- Send USDC or EURC → recipient receives local currency in a bank account or mobile wallet
- **10 African countries:** 🇳🇬 Nigeria · 🇰🇪 Kenya · 🇬🇭 Ghana · 🇿🇦 South Africa · 🇸🇳 Senegal · 🇨🇮 Côte d'Ivoire · 🇨🇲 Cameroon · 🇹🇿 Tanzania · 🇺🇬 Uganda · 🇷🇼 Rwanda
- **Locked quotes:** you sign one request, get the exact fee, rate and payout, and have 10 minutes to pay
- **Escrow-backed:** your deposit goes into an on-chain escrow (`KudiSendEscrow`) and is released only after the payout is verified (in sandbox mode the payout is simulated). If anything goes wrong it is refunded, and you can reclaim an untouched deposit yourself after 72 hours
- Payouts are routed through **Flutterwave**, with **Bitnob** (NG/GH/KE) and **Paystack** (NG/GH/KE/ZA) as fallbacks
- Service fee **0.8%–4.5%** depending on corridor
- In live mode, Flutterwave and Paystack payout results are confirmed with the provider before an order is marked complete (Bitnob relies on its signed webhook)
- **Payout partners run in sandbox mode unless `SEND_MODE=live`.** Live payouts are planned for mainnet launch, starting with Nigeria (NGN); other countries follow.

### 📈 Yield (KudiYield)
- Earn yield on USDC through Circle's USYC — tokenized short-duration US Treasury Bills
- The in-app APY figure is currently a fixed estimate (4.86%); actual returns follow the USYC price
- No lock-up period in the KudiYield contract. Withdrawals depend on USYC redemption being available, and the owner can pause the contract
- Earnings shown with an NGN equivalent

### 📋 Transaction History
- History of swaps and remittances per wallet
- Swap transaction hashes link to the Arc explorer
- Status tracking for payout transactions

---

## Smart Contracts

| Contract | Address | Status |
|----------|---------|--------|
| **KudiSwap V2** | [`0x8a10D0e61201000B5456EC725165892B08832C5f`](https://explorer.testnet.arc.io/address/0x8a10D0e61201000B5456EC725165892B08832C5f) | ✅ Verified |
| **KudiSendEscrow** | [`0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010`](https://explorer.testnet.arc.io/address/0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010) | ✅ Verified on Arc Testnet |
| **KudiYield** | [`0x146F0CD9afbc4effa3EdFc9D1a666bf5AA0d7AD8`](https://explorer.testnet.arc.io/address/0x146F0CD9afbc4effa3EdFc9D1a666bf5AA0d7AD8) | Testnet |
| KudiSwap V1 *(deprecated)* | [`0xb138329BF67cFe121A37D9947922D2B7278BdC29`](https://explorer.testnet.arc.io/address/0xb138329BF67cFe121A37D9947922D2B7278BdC29) | ⚠️ Deprecated |
| USDC (Arc) | `0x3600000000000000000000000000000000000000` | Circle Official |
| EURC (Arc) | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` | Circle Official |
| USYC (Arc) | `0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C` | Circle Official |

### Security

| Item | Detail |
|------|--------|
| Compiler | Solidity 0.8.24 |
| Automated scan | SolidityScan (March 2026): Security Score 60.58/100 · Threat Score 97/100 · 0 critical findings |
| Manual audit | **Not yet completed** — planned before holding real user funds on mainnet |

KudiSwap is a **custodial, owner-operated pool**: the owner sets rates and manages liquidity, constrained by the on-chain controls below. An automated scan is not a substitute for a manual audit.

**Security controls in KudiSwap V2:**
- `nonReentrant` guard on swaps, liquidity and withdrawal functions
- 5-minute timelock on rate updates, with ±20% relative bounds
- Absolute rate bounds (0.5 – 2.0)
- 24-hour timelock on owner liquidity withdrawals, capped at 50% of the pool per withdrawal
- Minimum 1 USDC/EURC liquidity enforced on owner withdrawals
- SafeERC20-style transfers
- Two-step ownership transfer
- Checks-Effects-Interactions pattern

**Security controls in KudiSendEscrow:**
- One deposit per quote reference, ever (no replays), and only allow-listed 6-decimal tokens
- Per-deposit minimum and maximum enforced on-chain
- Exact-amount check on deposit (fee-on-transfer tokens are rejected)
- `nonReentrant` guard on deposit, settle and refund paths
- Pausing stops new deposits only. Settle, refund and the user's 72-hour `claimRefund` always keep working
- Two-step ownership transfer (a multisig is planned for mainnet)
- 22 Foundry tests including a fuzz test (`forge test`)

See [SECURITY.md](./SECURITY.md) for the full policy.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND (static HTML/JS)                 │
│    index.html · send.html · yield.html · admin.html         │
│              Ethers.js v6 · MetaMask / Rabby                │
└──────────────────────┬──────────────────────────────────────┘
                       │  REST API + ethers.js RPC
          ┌────────────┴────────────┐
          │                         │
┌─────────▼──────────┐   ┌──────────▼──────────────────────────┐
│   FLASK BACKEND    │   │         ARC NETWORK (EVM)            │
│   Python           │   │                                      │
│                    │   │  KudiSwap V2 · KudiYield             │
│  Live FX rates     │   │  KudiSendEscrow                      │
│  Payout routing    │   │                                      │
│  Escrow checks     │   │  ✅ Reentrancy Guard                 │
│  TX history DB     │   │  ✅ Rate Timelock (5 min)            │
│  Verified webhooks │   │  ✅ Withdrawal Timelock (24hr)       │
│                    │   │  ✅ Rate Bounds (±20%, abs 0.5–2.0)  │
│  Gunicorn          │   │  ✅ Two-step Ownership               │
└─────────┬──────────┘   └──────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│                  FIAT SETTLEMENT LAYER                      │
│  Flutterwave (primary, all 10 corridors)                    │
│  Bitnob (NG/GH/KE) · Paystack (NG/GH/KE/ZA) as fallbacks    │
│  Webhook callbacks · Reference tracking                     │
└────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- MetaMask or Rabby wallet
- Arc Testnet is auto-added when you visit the dApp
- Testnet USDC from [faucet.circle.com](https://faucet.circle.com)

### Use the dApp

1. Visit **[https://kudiarc.xyz](https://kudiarc.xyz)** (testnet)
2. Click **Connect Wallet** — Arc Testnet is added automatically
3. Get testnet USDC from [faucet.circle.com](https://faucet.circle.com)
4. Start swapping, sending, or depositing for yield

**Arc Testnet config (manual):**

| Field | Value |
|-------|-------|
| Network Name | Arc Testnet |
| RPC URL | `https://rpc.testnet.arc.io` |
| Chain ID | `5042002` |
| Currency | USDC |
| Explorer | `https://explorer.testnet.arc.io` |

### Run Locally

```bash
# Clone
git clone https://github.com/KudiArc/kudi-arc.git
cd kudi-arc

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Set OWNER_ADDRESS (required for the admin dashboard), ESCROW_ADDRESS,
# and leave the payout keys as "mock" to stay in sandbox mode

# Initialize database
python3 db.py

# Start backend
python3 app.py
# API available at http://localhost:5001

# Open frontend
# Open index.html in your browser, or:
python3 -m http.server 8080
```

### Run the Tests

```bash
# Backend (pytest)
pip install -r requirements-dev.txt
python3 -m pytest

# Contracts (Foundry)
forge install foundry-rs/forge-std
forge test
```

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for production deployment instructions.

### Configuration

| Setting | Purpose |
|---------|---------|
| `NETWORK` | `testnet` (default) or `mainnet`. Sets RPC, chain ID, explorer and token addresses |
| `OWNER_ADDRESS` | Wallet allowed to use the admin dashboard. **Admin stays disabled if unset** |
| `ESCROW_ADDRESS` | Deployed `KudiSendEscrow` contract |
| `SEND_MODE` | `live` enables real payouts; anything else is sandbox |
| `QUOTE_TTL_SECONDS` | How long a quote stays valid (default 600) |
| `SEND_MIN_USD` / `SEND_MAX_USD` | Per-transfer limits (default 10 / 50) |
| `FLUTTERWAVE_SECRET_KEY`, `BITNOB_SECRET_KEY`, `PAYSTACK_SECRET_KEY` | Payout partner keys (used only when `SEND_MODE=live`) |
| `FLW_WEBHOOK_SECRET`, `BITNOB_WEBHOOK_SECRET` | Webhook secrets. Webhooks are rejected if these are unset |
| `DB_PATH` | SQLite database file |

See `.env.example` for the full list. The server never needs a private key.

---

## How It Works

```
1. User connects wallet to Arc Testnet
        │
2. User swaps USDC ↔ EURC on-chain (KudiSwap V2)
        │
3. For a remittance, the user signs one request and receives a locked quote
        │
4. User approves the token and deposits it into the KudiSendEscrow contract
        │
5. Backend verifies the deposit on-chain, then routes the payout
   to Flutterwave (Bitnob / Paystack as fallback)
        │
6. Partner pays out (sandbox mode unless SEND_MODE=live); the backend
   confirms the result with the partner before completing the order
        │
7. Owner settles confirmed orders to the treasury, or refunds failed ones
        │
8. Recipient receives NGN / KES / GHS / XOF / XAF / TZS / UGX / RWF / ZAR
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Blockchain | Arc Network (EVM, testnet chain ID 5042002) |
| Smart Contracts | Solidity 0.8.24, Foundry (`forge test`) |
| Frontend | HTML/CSS/JS, Ethers.js 6.7 |
| Backend | Python, Flask, Gunicorn, web3.py |
| Testing | pytest (backend), Foundry (contracts) |
| Database | SQLite (PostgreSQL planned for mainnet) |
| FX Rates | ExchangeRate-API (open.er-api.com) |
| Payout Partners | Flutterwave, Bitnob, Paystack |
| Wallet Support | MetaMask, Rabby, any EVM wallet |

---

## Project Structure

```
kudi-arc/
├── src/                      # Solidity sources (Foundry)
│   ├── KudiSwapV2.sol        # Swap contract (current)
│   ├── KudiYield.sol         # USYC yield wrapper
│   └── KudiSendEscrow.sol    # KudiSend escrow
├── contracts/
│   └── KudiSwap.sol          # V1 (deprecated)
├── test/                     # Foundry tests (escrow)
├── script/                   # Foundry deploy scripts
├── tests/                    # pytest suite (backend)
├── docs/
│   ├── WHITEPAPER.md         # Technical whitepaper v1.0
│   ├── ARCHITECTURE.md       # System architecture & diagrams
│   ├── API.md                # Backend API reference
│   └── DEPLOYMENT.md         # Deployment guide
├── app.py                    # Flask app, routes, FX rates
├── kudisend.py               # KudiSend: challenge, quote, confirm, admin orders
├── payouts.py                # Payout partners (Flutterwave, Bitnob, Paystack)
├── webhooks.py               # Partner webhooks (authenticated, re-verified)
├── swapverify.py             # On-chain verification of recorded swaps
├── adminauth.py              # Owner-signed admin authentication
├── db.py                     # Database schema + helpers
├── deploy.py                 # Contract deployment script
├── add_liquidity.py          # Liquidity management
├── gunicorn.conf.py          # Optional manual gunicorn config
├── start.sh                  # Optional manual start (port 5000); production runs under systemd
├── foundry.toml              # Foundry config
├── pytest.ini                # pytest config
├── index.html                # FX Swap dApp
├── send.html                 # Remittance dApp
├── yield.html                # Yield dApp
├── admin.html                # Admin dashboard (incl. Send Orders)
├── kudiarc-intro.html        # Project overview page
├── requirements.txt          # Python dependencies
├── requirements-dev.txt      # Test dependencies
├── CHANGELOG.md              # Release notes
├── CONTRIBUTING.md           # Contribution guide
├── SECURITY.md               # Security policy
└── .env.example              # Environment template
```

---

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | USDC ↔ EURC swap on Arc Testnet | ✅ Complete |
| Phase 2 | NGN remittance + 10-country support (sandbox payouts) | ✅ Complete (sandbox) |
| Phase 3 | USYC yield integration | ✅ Complete |
| Phase 4 | Multi-currency (KES, GHS, XOF, XAF, ZAR, TZS, UGX, RWF) | ✅ Complete |
| Phase 5 | Flutterwave / Bitnob / Paystack payout integration | ✅ Integrated (sandbox mode) |
| Phase 6 | KudiArc mainnet launch, Nigeria (NGN) first (Arc Mainnet itself is live since 16 Sept 2026) · PostgreSQL · multisig · manual audit | 🔨 In progress |
| Phase 7 | AMM model (x\*y=k) + open liquidity provision | 📋 Planned |
| Phase 8 | Chainlink oracle integration | 📋 Planned |
| Phase 9 | CCTP, Multi-chain (Base, Stellar, Polygon) | 📋 Planned |
| Phase 10 | Mobile app (React Native) | 📋 Planned |

> Planned items are intentions, not commitments, and dates may change.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/WHITEPAPER.md](./docs/WHITEPAPER.md) | Technical whitepaper v1.0 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System architecture, diagrams, data flows |
| [docs/API.md](./docs/API.md) | Backend API reference with examples |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Production deployment guide |
| [CHANGELOG.md](./CHANGELOG.md) | Release notes |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](./SECURITY.md) | Security policy & vulnerability reporting |

---

## Contributing

We welcome contributions from the African developer community. Areas where help is most needed:

- 🌍 **New country corridors** — Ethiopia, Egypt, Mozambique
- 🧪 **Test coverage** — extend the pytest suite in `tests/` and add CI
- 📱 **Mobile UX** — CSS improvements, PWA manifest
- 🌐 **Localisation** — Hausa, Swahili, French UI

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full guide.

```bash
git checkout -b feature/your-feature
git commit -m "feat: your change"
git push origin feature/your-feature
# Open a Pull Request
```

---

## Security

Found a vulnerability? **Do not open a public issue.**

Report it privately via [GitHub security advisories](https://github.com/KudiArc/kudi-arc/security/advisories/new) or DM [@KudiArc](https://twitter.com/KudiArc) on X.

We respond within 48 hours. See [SECURITY.md](./SECURITY.md) for the full disclosure policy.

---

## License

MIT License — see [LICENSE](./LICENSE) for details.

---

## Builder

Built by **Musa AIS** · CS student at Federal University Dutse (FUD). Builder, PenTester & Dev. Appointed Lepton Peer Mentor by Canteen.

[![X](https://img.shields.io/badge/X-@KudiArc-000000?style=flat-square&logo=x)](https://twitter.com/KudiArc)
[![Discord](https://img.shields.io/badge/Discord-kudiarc-5865F2?style=flat-square&logo=discord)](https://discord.gg/nEJfqrAsqc)
[![GitHub](https://img.shields.io/badge/GitHub-KudiArc-181717?style=flat-square&logo=github)](https://github.com/KudiArc)

---

<div align="center">

**Built in Africa 🌍**

*Kudi means money. Arc means infrastructure. Together — financial freedom for Africa.*

</div>
