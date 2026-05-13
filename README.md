[🌍 Project Overview](https://intro.kudiarc.xyz)

# 🟡 Kudi Arc

### Stablecoin FX & Remittance Protocol for Africa — Built on Arc Network

**Built on Arc Network · Powered by Circle USDC & EURC**

[![Testnet](https://img.shields.io/badge/Testnet%20-Live-27AE74?style=for-the-badge)](https://kudiarc.xyz/)
[![Contract](https://img.shields.io/badge/Contract-Verified-27AE74?style=for-the-badge)](https://testnet.arcscan.app/address/0x8a10D0e61201000B5456EC725165892B08832C5f)
[![Audit](https://img.shields.io/badge/Security%20Audit-SolidityScan-F5A623?style=for-the-badge)](https://solidityscan.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=for-the-badge)](https://discord.gg/nEJfqrAsqc)

---

> **Swap USDC ↔ EURC · Send to 10 African countries · Earn 4.86% APY via USYC**

---

## What is Kudi Arc?

Kudi Arc is an Africa-first stablecoin FX desk and remittance engine built on **Arc Network** — the first blockchain where gas is paid in USDC. No ETH. No friction. Just USDC.

We solve three structural failures in African finance:

| Problem | Our Solution | Impact |
|---------|-------------|--------|
| Nigeria forex scarcity (30%+ parallel market premium) | USDC ↔ EURC swap at live rates, 0.30% fee | 10–90× cheaper than the parallel market |
| Africa remittance costs avg 8.5% (World Bank) | Crypto-to-fiat payout to 10 countries | Under 1% total cost |
| No accessible USD yield for Africans | 4.86% APY via Circle USYC (tokenized T-Bills) | Real returns in a stable currency |

**It combines:** On-chain stablecoin swaps · Off-chain fiat settlement · Yield on idle balances

---

## Live Stats — Arc Testnet (May 2026)

| Metric | Value |
|--------|-------|
|Swap Volume:  |      $63,800+ USDC equivalent|
| Total Tnx | 27,000+ |
|Active Wallets:   |  293+|
KudiYield TVL:      6,718+ USYC
|USDC Pool:          1,000+ USDC
|EURC Pool:          28,700+ EURC
|1 USYC Value:  |     $1.1163 (live via Teller)|

---

## Features

### ⇄ FX Swap (KudiSwap)
- Swap USDC ↔ EURC at live market rates
- **0.30% fee** — lowest in the market vs 1–5% competitors
- Slippage protection (`minAmountOut`) enforced on-chain
- 5-minute rate timelock — no surprise rate changes
- Real-time NGN equivalent displayed

### 📤 Send Money (KudiSend)
- Send USDC or EURC → recipient gets local cash in their bank or mobile wallet
- **10 African countries:** 🇳🇬 Nigeria · 🇰🇪 Kenya · 🇬🇭 Ghana · 🇿🇦 South Africa · 🇸🇳 Senegal · 🇨🇮 Côte d'Ivoire · 🇨🇲 Cameroon · 🇹🇿 Tanzania · 🇺🇬 Uganda · 🇷🇼 Rwanda
- Powered by Bitnob (NGN), Flutterwave (KES/GHS/ZAR), Wave (XOF/XAF)
- Wallet signature required for every transfer — you stay in control
- Full reference tracking with both on-chain TX hash and payout reference

### 📈 Yield (KudiYield)
- Earn **4.86% APY** on your USDC
- Backed by Circle's USYC — tokenized short-duration US Treasury Bills
- No lock-up — withdraw anytime
- Earnings shown in NGN equivalent for local context

### 📋 Transaction History
- Full history of swaps and remittances per wallet
- Clickable TX hashes linking to Arcscan explorer
- Status tracking for all payout transactions

---

## Smart Contracts

| Contract | Address | Status |
|----------|---------|--------|
| **KudiSwap V2** | [`0x8a10D0e61201000B5456EC725165892B08832C5f`](https://testnet.arcscan.app/address/0x8a10D0e61201000B5456EC725165892B08832C5f) | ✅ Verified |
| KudiSwap V1 *(deprecated)* | [`0xb138329BF67cFe121A37D9947922D2B7278BdC29`](https://testnet.arcscan.app/address/0xb138329BF67cFe121A37D9947922D2B7278BdC29) | ⚠️ Deprecated |
| USDC (Arc) | `0x3600000000000000000000000000000000000000` | Circle Official |
| EURC (Arc) | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` | Circle Official |
| USYC (Arc) | `0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C` | Circle Official |

### Security

| Item | Detail |
|------|--------|
| Compiler | Solidity 0.8.24 |
| Audit | SolidityScan (March 2026) |
| Threat Score | **97/100 — Low Risk** ✅ |
| Critical Vulnerabilities | **0** |
| Manual Audit | Planned Q2 2026 (pre-mainnet) |

**Security controls in KudiSwap V2:**
- `nonReentrant` modifier + `_locked` bool on all fund-moving functions
- 5-minute timelock on rate updates + ±20% relative bounds
- 24-hour timelock on liquidity withdrawals + 50% cap per transaction
- Absolute rate bounds (0.5 — 2.0 USDC/EURC)
- Minimum 1 USDC pool invariant always maintained
- SafeERC20 for all token transfers
- Two-step ownership transfer pattern
- CEI (Checks-Effects-Interactions) pattern throughout

> **Note on security score:** SolidityScan's 60.58/100 score reflects custodial design patterns that are intentional — the 97/100 Threat Score is the relevant vulnerability metric. See [SECURITY.md](./SECURITY.md) for full context.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       FRONTEND (PWA)                        │
│         index.html · send.html · yield.html                 │
│              Ethers.js v6 · MetaMask / Rabby                │
└──────────────────────┬──────────────────────────────────────┘
                       │  REST API + ethers.js RPC
          ┌────────────┴────────────┐
          │                         │
┌─────────▼──────────┐   ┌──────────▼──────────────────────────┐
│   FLASK BACKEND    │   │         ARC NETWORK (EVM)            │
│   Python 3.10      │   │                                      │
│                    │   │  KudiSwap V2 Smart Contract          │
│  Live FX rates     │   │  0x8a10D0e61201...832C5f             │
│  Payout routing    │   │                                      │
│  TX history DB     │   │  ✅ Reentrancy Guard                 │
│  Webhook handler   │   │  ✅ Rate Timelock (5 min)            │
│                    │   │  ✅ Withdrawal Timelock (24hr)       │
│  Nginx + Gunicorn  │   │  ✅ Rate Bounds (±20%, abs 0.5–2.0) │
└─────────┬──────────┘   │  ✅ SafeERC20 · Two-step Ownership  │
          │               └──────────────────────────────────────┘
┌─────────▼──────────────────────────────────────────────────┐
│                  FIAT SETTLEMENT LAYER                      │
│  Bitnob (NGN) · Flutterwave (KES/GHS/ZAR/TZS/UGX/RWF)    │
│  Flutterwave (XOF/XAF) · Webhook callbacks · Reference tracking   │
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
| RPC URL | `https://rpc.testnet.arc.network` |
| Chain ID | `5042002` |
| Currency | USDC |
| Explorer | `https://testnet.arcscan.app` |

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
# Fill in your RPC URL, API keys, and payout partner credentials

# Initialize database
python3 db.py

# Start backend
python3 app.py
# API available at http://localhost:5000

# Open frontend
# Open index.html in your browser, or:
python3 -m http.server 8080
```

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for full production deployment instructions.

---

## How It Works

```
1. User connects wallet to Arc Testnet
        │
2. User swaps USDC ↔ EURC on-chain (KudiSwap V2)
        │
3. User initiates remittance — signs with wallet
        │
4. Backend verifies signature + routes to payout partner
        │
5. Bitnob / Flutterwave / Wave processes fiat payout
        │
6. Recipient receives NGN / KES / GHS / XOF / FCFA
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Blockchain | Arc Network (EVM, Chain 5042002) |
| Smart Contract | Solidity 0.8.24, Foundry |
| Frontend | HTML/CSS/JS, Ethers.js 6.7 |
| Backend | Python 3.10, Flask, Gunicorn |
| Database | SQLite (testnet) → PostgreSQL (mainnet) |
| Web Server | Nginx |
| Process Manager | systemd |
| FX Rates | Open Exchange Rates API |
| Payout Partners | Bitnob, Flutterwave, Wave |
| Wallet Support | MetaMask, Rabby, any EVM wallet |

---

## Project Structure

```
kudi-arc/
├── contracts/
│   ├── KudiSwapV2.sol        # Main swap contract (current)
│   └── KudiSwap.sol          # V1 (deprecated)
├── docs/
│   ├── WHITEPAPER.md         # Technical whitepaper v2.0
│   ├── ARCHITECTURE.md       # System architecture & diagrams
│   ├── API.md                # Backend API reference
│   └── DEPLOYMENT.md         # Deployment guide
├── app.py                    # Flask backend
├── db.py                     # Database schema + helpers
├── deploy.py                 # Contract deployment script
├── add_liquidity.py          # Liquidity management
├── index.html                # FX Swap dApp
├── send.html                 # Remittance dApp
├── yield.html                # Yield dApp
├── requirements.txt          # Python dependencies
├── CONTRIBUTING.md           # Contribution guide
├── SECURITY.md               # Security policy & bug bounty
└── .env.example              # Environment template
```

---

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | USDC ↔ EURC swap on Arc Testnet | ✅ Complete |
| Phase 2 | NGN remittance + 10-country support | ✅ Complete |
| Phase 3 | USYC yield integration | ✅ Complete |
| Phase 4 | Multi-currency (KES, GHS, XOF, FCFA) | ✅ Complete |
| Phase 5 | Bitnob / Flutterwave live integration | 🔄 In Progress |
| Phase 6 | Arc Mainnet + PostgreSQL + Multisig | ⏳ Q3 2026 |
| Phase 7 | AMM model (x\*y=k) + open liquidity provision | 📋 Q4 2026 |
| Phase 8 | Chainlink oracle integration | 📋 Q4 2026 |
| Phase 9 | CCTP, Multi-chain (Base, Stellar, Polygon) | 📋 2027 |
| Phase 10 | Mobile app (React Native) | 📋 Q1 2027 |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/WHITEPAPER.md](./docs/WHITEPAPER.md) | Full technical whitepaper v1.0 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System architecture, diagrams, data flows |
| [docs/API.md](./docs/API.md) | Backend API reference with examples |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Production deployment guide |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](./SECURITY.md) | Security policy & vulnerability reporting |

---

## Contributing

We welcome contributions from the African developer community. Areas where help is most needed:

- 🌍 **New country corridors** — Ethiopia, Egypt, Mozambique
- 🧪 **Test coverage** — pytest suite for the Flask API
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

Contact us at **security@kudiarc.xyz** or DM [@KudiArc](https://twitter.com/KudiArc) on X.

We respond within 48 hours. See [SECURITY.md](./SECURITY.md) for the full disclosure policy and bug bounty scope.

---

## License

MIT License — see [LICENSE](./LICENSE) for details.

---

## Builder

Built by **Musa AIS** · Nigeria 🇳🇬

[![X](https://img.shields.io/badge/X-@KudiArc-000000?style=flat-square&logo=x)](https://twitter.com/KudiArc)
[![Discord](https://img.shields.io/badge/Discord-kudiarc-5865F2?style=flat-square&logo=discord)](https://discord.gg/nEJfqrAsqc)
[![GitHub](https://img.shields.io/badge/GitHub-KudiArc-181717?style=flat-square&logo=github)](https://github.com/KudiArc)

---

<div align="center">

**Built in Africa 🌍**

*Kudi means money. Arc means infrastructure. Together — financial freedom for Africa.*

</div>
