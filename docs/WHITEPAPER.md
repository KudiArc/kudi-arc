# Kudi Arc — Technical Whitepaper

**Version:** 1.0 &nbsp;|&nbsp; **Date:** March 2026 &nbsp;|&nbsp; **Network:** Arc Testnet (Mainnet: Q3 2026)

> Built on Arc Network · Powered by Circle USDC & EURC  
> [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc) · [@KudiArc](https://twitter.com/KudiArc) · [discord.gg/kudiarc](https://discord.gg/nEJfqrAsqc)

---

## Table of Contents

1. [Abstract](#abstract)
2. [Problem Statement](#1-problem-statement)
3. [Solution Overview](#2-solution-overview)
4. [Competitive Landscape](#3-competitive-landscape)
5. [Smart Contract Architecture](#4-smart-contract-architecture)
6. [Backend Architecture](#5-backend-architecture)
7. [Fiat Settlement Layer](#6-fiat-settlement-layer)
8. [Supported Countries & Currencies](#7-supported-countries--currencies)
9. [Fee Structure & Protocol Economics](#8-fee-structure--protocol-economics)
10. [Security Model](#9-security-model)
11. [Governance & Upgrade Path](#10-governance--upgrade-path)
12. [Market Opportunity (TAM)](#11-market-opportunity-tam)
13. [Roadmap](#12-roadmap)
14. [Team](#13-team)
15. [Why Arc Network](#14-why-arc-network)
16. [Risks & Mitigations](#15-risks--mitigations)
17. [Legal Disclaimer](#16-legal-disclaimer)

---

## Abstract

Kudi Arc is a hybrid on-chain FX desk and remittance engine for Africa — built on Arc Network, the first EVM-compatible blockchain that uses USDC as its native gas token. By combining on-chain stablecoin swaps, off-chain fiat settlement, and tokenized yield, Kudi Arc addresses three structural failures in African financial infrastructure: prohibitive remittance costs, forex scarcity, and the absence of accessible low-risk yield products.

The protocol deploys KudiSwap V2 — a Solidity 0.8.24 smart contract — on Arc Testnet (Chain ID 5042002), enabling USDC ↔ EURC swaps with live FX rates, a 0.30% fee, and multi-layered security controls. A Flask-based backend bridges on-chain activity to licensed fiat payout partners (Bitnob, Flutterwave, Wave) across 10 African countries. USYC integration provides 4.86% APY on idle USDC balances via Circle's tokenized US Treasury product.

This document describes the protocol's architecture, economic model, security design, competitive positioning, risks, and roadmap to Arc Mainnet.

---

## 1. Problem Statement

### 1.1 The African Forex Crisis

Nigeria — Africa's largest economy with 220 million people — operates under severe foreign currency restrictions. The Central Bank of Nigeria (CBN) strictly limits USD access for individuals and businesses, creating a parallel market that routinely trades at a **30%+ premium** over the official rate. This forex scarcity forces businesses to absorb currency risk and individuals to pay extortionate rates just to preserve purchasing power.

This is not a Nigeria-only problem. Across sub-Saharan Africa, 14 of 54 countries maintain fixed or managed exchange rate regimes, creating endemic FX friction for cross-border commerce.

### 1.2 Remittance Costs

Africa received over **$50 billion** in inbound remittances in 2024 (World Bank). The average cost to send money to sub-Saharan Africa remains **8.5%** — the most expensive corridor in the world. A Nigerian diaspora worker sending $200 home loses $17 in fees. Traditional corridors through Western Union, MoneyGram, and local banks account for the majority of this flow.

The UN Sustainable Development Goal target is 3% by 2030. Current infrastructure is not on track.

### 1.3 The Yield Gap

Nigerian savings accounts offer 4–6% annual yield in NGN — a currency that devalued **70% against the USD in 2023** alone. In real USD-adjusted terms, most Nigerian savers experience negative returns. There is no accessible, low-risk, dollar-denominated yield product for ordinary Africans without navigating complex crypto infrastructure.

### 1.4 The Gas Problem in DeFi

Every EVM-compatible dApp requires ETH (or the chain's native token) for gas. For African users new to crypto, this creates an insurmountable UX barrier: to use USDC, you must first acquire ETH, understand wallets, manage two assets, and handle gas estimation. Arc Network eliminates this entirely — **all gas is paid in USDC**, meaning users only ever need a single asset.

---

## 2. Solution Overview

Kudi Arc provides three financial primitives on Arc Network, each targeting one of the problems above.

### 2.1 FX Swap (KudiSwap)

A USDC ↔ EURC swap contract with live rates sourced from the Open Exchange Rates API, refreshed every 5 minutes.

- **Fee:** 0.30% (vs 2–5% on traditional exchanges and 1–3% on competing crypto desks)
- **Slippage protection:** `minAmountOut` parameter enforced on-chain
- **Rate timelock:** 5-minute delay on any rate update — prevents flash manipulation
- **Rate bounds:** absolute (0.5–2.0 USDC/EURC) and relative (±20% per update) enforced in contract

### 2.2 Remittance (KudiSend)

A crypto-to-fiat flow that bridges on-chain stablecoin transfers to local bank and mobile wallet payouts:

1. User initiates send with wallet signature (on-chain authorization)
2. Backend receives signed intent, validates, routes to licensed payout partner
3. Recipient receives NGN / KES / GHS / XOF / FCFA in their bank account or mobile wallet
4. Reference tracking on every transaction — both on-chain TX hash and payout partner reference stored

Supports **10 African countries** at launch; planned expansion to 20+ on mainnet.

### 2.3 Yield (KudiYield)

Integration with Circle's USYC — a tokenized money market fund backed by short-duration US Treasury Bills, issued directly on Arc Network:

- **Current APY:** 4.86% (variable, tracks Fed Funds Rate)
- **$1.1163 per USYC — fetched in real time via Hashnote**
- Eligible to non-US institutions (African entities qualify under Circle's allowlist)
- No lock-up period — withdrawals processed on demand
- Earnings displayed in NGN equivalent to provide local context

---

## 3. Competitive Landscape

Kudi Arc occupies a distinct position: a crypto-native FX and remittance protocol built specifically for Africa, on infrastructure (Arc) that removes the gas complexity that has historically prevented adoption.

| Provider | Type | Fee | Crypto-Native | Yield | On-Chain Audit | Africa-First |
|----------|------|-----|---------------|-------|----------------|--------------|
| **Kudi Arc** | Hybrid DeFi/CeFi | **0.30%** | ✅ USDC-only | ✅ 4.86% APY | ✅ Arcscan | ✅ |
| Yellow Card | Crypto Exchange | 1.5–3% | ✅ Multi-token | ❌ | ❌ | ✅ |
| Chipper Cash | Mobile Money | Free–2% | ❌ Fiat-only | ❌ | ❌ | ✅ |
| Grey Finance | Stablecoin Wallet | 1% | ✅ USDC/USDT | ❌ | ❌ | ✅ |
| Western Union | Traditional | 5–9% | ❌ Fiat-only | ❌ | ❌ | ❌ |
| Lemfi | Neobank | 0.5–1% | ❌ Fiat-only | ❌ | ❌ | Partial |

**Key differentiators:**

- Only USDC-as-gas chain (Arc) — zero gas friction for non-crypto users
- Only protocol offering on-chain FX swap + remittance + yield in a single interface
- All swap logic is publicly verifiable on Arcscan — no black-box rate manipulation
- 0.30% fee is among the lowest in the market for stablecoin FX

---

## 4. Smart Contract Architecture

### 4.1 KudiSwap V2

| Item | Detail |
|------|--------|
| **Address** | `0x8a10D0e61201000B5456EC725165892B08832C5f` |
| **Compiler** | Solidity 0.8.24 |
| **Network** | Arc Testnet (Chain 5042002) |
| **Status** | ✅ Verified on Arcscan |

#### Core Functions

| Function | Description |
|----------|-------------|
| `swapUSDCforEURC(amountIn, minAmountOut)` | Swap USDC to EURC with slippage protection |
| `swapEURCforUSDC(amountIn, minAmountOut)` | Swap EURC to USDC with slippage protection |
| `previewSwapUSDCtoEURC(amountIn)` | Preview output amount before committing |
| `previewSwapEURCtoUSDC(amountIn)` | Preview output amount before committing |
| `getPoolBalances()` | Returns current USDC and EURC pool reserves |
| `getStats()` | Returns cumulative swap volume and fee totals |
| `withdrawFees()` | Owner-only: extract accrued protocol fees |
| `updateRate(newRate)` | Owner-only: update USDC/EURC rate (5-min timelock) |

#### Security Controls

| Threat | Control | Detail |
|--------|---------|--------|
| Reentrancy attack | `nonReentrant` + `_locked` bool | Applied to all fund-moving functions |
| Rate manipulation | 5-min timelock + ±20% bounds | Absolute bounds: 0.5–2.0 USDC/EURC |
| Liquidity drain | 24-hr timelock + 50% cap | Max 50% pool withdrawal per tx |
| Token transfer failure | SafeERC20 | Reverts on `false` return values |
| Ownership takeover | Two-step transfer | Pending owner must explicitly accept |
| Extreme fee setting | 2% cap (200 bps) | `setFee()` reverts above cap |
| Min liquidity breach | 1 USDC floor invariant | Contract reverts if pool would drop below |
| Flash price manipulation | Rate timelock | 5-min delay — users can exit before new rate applies |
| Pattern | CEI (Checks-Effects-Interactions) | State updates before all external calls |

### 4.2 Trust Model

Kudi Arc is deliberately custodial, not a trustless AMM. This is a considered design choice:

- NGN offramp **always** requires a licensed, centralized payout partner — full decentralization of fiat settlement is not feasible
- Mobile-first African users need simplicity; requiring private key management for every action increases abandonment
- Comparable to Bitnob, Yellow Card, and Grey Finance — all trusted operators with similar hybrid models

**Transparency measures that compensate for custodial nature:**

- Contract source code publicly verified on Arcscan
- All admin actions emit on-chain events with timestamps
- 5–24 hour timelocks give users advance warning of any owner action
- Rate bounds (absolute and relative) prevent extreme manipulation even by the owner

The roadmap toward progressive decentralization is outlined in [Section 10](#10-governance--upgrade-path).

---

## 5. Backend Architecture

The Flask backend (Python 3.10) bridges on-chain activity to off-chain payout infrastructure and FX data sources.

### 5.1 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rates` | GET | Live USD/EUR/NGN rates — refreshed every 2 minutes |
| `/api/countries` | GET | 10-country payout configs with live local currency rates |
| `/api/banks` | GET | Nigerian bank list (26 banks) for account validation |
| `/api/send/payout` | POST | Universal payout endpoint — routes to correct partner per country |
| `/api/swap/record` | POST | Records on-chain swap event to local database |
| `/api/history/:wallet` | GET | Per-wallet transaction history (swaps + sends) |
| `/api/yield/stats` | GET | USYC APY and pool data from Circle |
| `/api/yield/balance` | GET | User's USYC position by wallet address |
| `/api/health` | GET | Service health status for all components |

Full API documentation: [docs/API.md](./API.md)

### 5.2 Database

**Current (testnet):** SQLite — appropriate for beta scale.

**Known limitation:** SQLite's single-writer model is not suitable for concurrent production traffic. PostgreSQL migration is a pre-mainnet requirement (Phase 6).

**Schema (simplified):**

```sql
-- Swap records
CREATE TABLE transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet     TEXT    NOT NULL,
    tx_type    TEXT    NOT NULL,  -- 'swap' | 'send'
    from_token TEXT,
    to_token   TEXT,
    amount_in  REAL,
    amount_out REAL,
    rate       REAL,
    tx_hash    TEXT,
    created_at TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX idx_transactions_wallet ON transactions(wallet);
```

### 5.3 Infrastructure

| Component | Testnet | Mainnet (Planned) |
|-----------|---------|-------------------|
| Server | Oracle Cloud VM | Dedicated VM |
| Database | SQLite | PostgreSQL 15 |
| Cache | In-memory | Redis |
| WSGI | Gunicorn (4 workers) | Gunicorn (8+ workers) |
| Web server | Nginx | Nginx + Certbot SSL |
| Process mgr | systemd | systemd + monitoring |

---

## 6. Fiat Settlement Layer

This is the highest-risk component of the protocol. Fiat settlement depends on licensed third-party payout partners — Bitnob, Flutterwave, and Wave.

### 6.1 Transaction Flow

1. User connects wallet and inputs: destination country, recipient bank details, amount in USDC/EURC
2. User signs a message with their wallet (EIP-191 authorization)
3. Backend validates: signature, amount within daily limit, partner availability
4. Backend locks the user's USDC by initiating the on-chain transfer
5. Backend calls the relevant partner API (Bitnob for NGN, Flutterwave for KES/GHS/ZAR, Wave for XOF/XAF)
6. Partner processes payout to recipient's bank account or mobile wallet
7. Backend receives webhook confirmation and updates transaction status
8. User sees confirmed status with partner reference number

### 6.2 Partner Coverage

| Partner | Countries | Payout Methods | Status |
|---------|-----------|----------------|--------|
| Bitnob | Nigeria (NGN) | Bank transfer, mobile money | ✅ Live (testnet) |
| Flutterwave | Kenya, Ghana, South Africa, Tanzania, Nigeria, Uganda, Rwanda | Senegal, Côte d'Ivoire, Cameroon | Bank Transfer, M-Pesa, MTN MoMo, Orange Money | ✅ Live (testnet) |
| Paystack | Nigeria (NGN) | Bank transfer (fallback) | ✅ Live (integrated) |

### 6.3 Failure Modes & Recovery

| Failure | Handling |
|---------|----------|
| Partner timeout (>30s) | TX flagged `pending` — manual resolution within 2 hours |
| Bank rejection (invalid account) | USDC returned to user wallet within 10 minutes |
| Partial payout | Backend detects mismatch via webhook, escalates to manual review |
| Partner downtime | Country routes auto-disabled — users see "temporarily unavailable" |

**SLA (testnet):** Best-effort 2-hour resolution.  
**SLA (mainnet target):** Automated retry + 30-minute max resolution for reversible failures.

### 6.4 KYC & Compliance

At testnet stage, KYC is minimal (wallet address + phone number for mobile payouts). Mainnet compliance will depend on Arc Network's regulatory framework and partner requirements. Nigeria-specific: CBN's Virtual Asset Service Provider (VASP) regulations will apply to NGN offramp operations.

---

## 7. Supported Countries & Currencies

| Country | Currency | Symbol | Payout Methods | Partner |
|---------|----------|--------|----------------|---------|
| 🇳🇬 Nigeria | NGN | ₦ | Bank transfer, mobile money | Bitnob |
| 🇰🇪 Kenya | KES | KSh | Bank transfer, M-Pesa | Flutterwave |
| 🇬🇭 Ghana | GHS | GH₵ | Bank transfer, MTN MoMo | Flutterwave |
| 🇿🇦 South Africa | ZAR | R | Bank transfer (EFT) | Flutterwave |
| 🇸🇳 Senegal | XOF | CFA | Wave wallet, Orange Money | Wave |
| 🇨🇮 Côte d'Ivoire | XOF | CFA | Wave wallet, MTN MoMo | Wave |
| 🇨🇲 Cameroon | XAF | FCFA | Wave wallet, Orange Money | Wave |
| 🇹🇿 Tanzania | TZS | TSh | Bank transfer, M-Pesa | Flutterwave |
| 🇺🇬 Uganda | UGX | USh | Bank transfer, MTN MoMo | Flutterwave |
| 🇷🇼 Rwanda | RWF | RF | Bank transfer, MTN MoMo | Flutterwave |

FX data covers NGN, KES, GHS, ZAR, XOF, XAF, TZS, UGX, and RWF — 9 currencies refreshed every 5 minutes from the Open Exchange Rates API. Mainnet expansion target: 20+ countries.

---

## 8. Fee Structure & Protocol Economics

### 8.1 Fee Schedule

| Action | Fee | Collected In | Recipient |
|--------|-----|--------------|-----------|
| USDC → EURC Swap | 0.30% | USDC | Protocol treasury |
| EURC → USDC Swap | 0.30% | EURC | Protocol treasury |
| Remittance send | 0.30% | USDC | Protocol treasury + partner |
| USYC deposit | 0% | — | — |
| USYC withdrawal | 0% | — | — |

### 8.2 Fee Mechanics

Swap fees are collected in the swap token and tracked separately via the `accruedFees` state variable. Fees cannot be withdrawn together with liquidity — they are extracted exclusively via `withdrawFees()`. This separation prevents the owner from obscuring fee extraction within liquidity operations.

The fee cap is enforced in-contract at **2% (200 basis points)** — no fee above this can be set regardless of owner intent.

### 8.3 Protocol Economics (No Token)

Kudi Arc does not have a protocol token at this stage. All protocol fees accumulate in the contract treasury (USDC/EURC) and are used to fund development, partner integrations, and operational costs.

A future governance token (KUDI) is under consideration for Phase 7+ to facilitate decentralized LP governance and fee distribution. This is not committed — any token launch would be announced with a separate tokenomics document.

### 8.4 Revenue Projections (Illustrative)

| Scenario | Monthly Volume | Annual Fee Revenue |
|----------|---------------|-------------------|
| Conservative | $1M (0.1% Nigeria corridor) | $36,000/year |
| Growth | $33M (1% Nigeria + 0.5% others) | $1.2M/year |

> These figures are illustrative projections only, not forecasts.

---

## 9. Security Model

### 9.1 Audit Results

KudiSwap V2 was audited via SolidityScan (automated static analysis, March 2026):

| Metric | Result |
|--------|--------|
| Security Score | 60.58 / 100 |
| Threat Score | **97 / 100 — Low Risk** ✅ |
| Critical Vulnerabilities | **0** |
| High Vulnerabilities | **0** |

> **Note on the 60.58 score:** SolidityScan's methodology penalises custodial design patterns — specifically owner-controlled rate updates and liquidity management. These patterns are intentional and bounded. The **97/100 Threat Score** is the relevant vulnerability metric. All owner-callable functions have explicit timelocks, bounds, and emit public events. A third-party manual audit is planned for Q2 2026 before mainnet deployment.

### 9.2 Known Limitations

| Limitation | Detail | Mitigation |
|-----------|--------|------------|
| Centralized oracle | FX rates from Open Exchange Rates API | ±20% bounds limit exposure; Chainlink in Phase 8 |
| Custodial rate control | Owner can update rates within bounds + 5-min delay | Timelocked — users have 5 min to exit |
| Single-key ownership | Single EOA owner on testnet | 3-of-5 multisig before mainnet (Phase 6) |
| No manual audit | Automated tooling only | Third-party audit planned Q2 2026 |
| SQLite database | Not suitable for production scale | PostgreSQL migration pre-mainnet |

---

## 10. Governance & Upgrade Path

Kudi Arc launches as a centralized protocol with a clear, time-bound path toward progressive decentralization — mirroring the model used by Uniswap, Aave, and Compound.

| Phase | Governance Model | Timeline |
|-------|-----------------|----------|
| Testnet (Now) | Single EOA owner — full control with timelocked actions | Current |
| Mainnet Launch (Phase 6) | 3-of-5 multisig (Gnosis Safe) — team + 2 external signers | Q3 2026 |
| V3 (Phase 9) | Chainlink oracle anchors rates — owner can no longer set arbitrary rates | Q4 2026 |
| V4 (Phase 7+) | AMM formula replaces manual rates — owner rate control removed | 2027 |
| DAO (Future) | KUDI governance token — community fee votes, LP governance | TBD |

**Admin transparency:** Every privileged action (rate update, fee change, liquidity withdrawal) emits an on-chain event. Users can monitor the contract's event log on Arcscan at any time.

---

## 11. Market Opportunity (TAM)

| Market Segment | Size | Kudi Arc Relevance |
|---------------|------|-------------------|
| Sub-Saharan Africa inbound remittances | $54B/year (World Bank 2024) | Primary: KudiSend |
| Nigeria inbound remittances | $20B+/year | Primary: KudiSend (NGN corridor) |
| Africa stablecoin transaction volume | $180B+/year (Chainalysis 2024) | Primary: KudiSwap |
| Africa crypto user base | 53M+ users (Nigeria #3 globally) | Addressable user base |
| Tokenized T-Bill market (USYC) | $500M+ AUM and growing | KudiYield integration |
| Africa FX parallel market | $50B+/year | KudiSwap primary target |

**Conservative scenario:** Capture 0.1% of Nigeria's $20B remittance corridor = $20M annual volume = $60,000/year in fees.

**Growth scenario:** 1% of Nigeria + 0.5% of remaining 9 countries = ~$400M annual volume = $1.2M/year in fees.

---

## 12. Roadmap

### Testnet — Q1 2026 (Current)

| Milestone | Status |
|-----------|--------|
| KudiSwap V2 deployed & verified on Arcscan | ✅ Complete |
| 10-country remittance support (KudiSend) | ✅ Complete |
| USYC yield integration (KudiYield) | ✅ Complete |
| Transaction history per wallet | ✅ Complete |
| SolidityScan security audit | ✅ Complete |
| Bitnob API integration (NGN live) | ✅ Complete |
| Flutterwave API integration | ✅️ Complete |
| Circle USYC allowlist approval | ✅️ Complete |
| User beta testing program | ⏳ In Progress |

### Mainnet — Q3 2026

| Milestone | Target |
|-----------|--------|
| Arc Mainnet deployment | Q3 2026 |
| Real NGN/KES/GHS/XOF live payouts | Q3 2026 |
| SSL + CDN | Q3 2026 |
| PostgreSQL migration (replace SQLite) | Q3 2026 |
| 3-of-5 multisig ownership transfer | Q3 2026 |
| Third-party smart contract audit | Q2 2026 (pre-mainnet) |
| 20-country expansion | Q4 2026 |

### V3 — Q4 2026

| Milestone | Target |
|-----------|--------|
| Chainlink oracle integration | Q4 2026 |
| AMM model (x*y=k) replacing manual rate setting | Q4 2026 |
| Open liquidity provision + LP token system | Q4 2026 |
| (CCTP) Multi-chain deployment (Base, Stellar, Ethereum, Solana) | Q4 2026 |
| Circle Wallets integration | Q4 2026 |

### V4 — 2027

| Milestone | Target |
|-----------|--------|
| Mobile app (React Native) — iOS & Android | Q1 2027 |
| KUDI governance token consideration | Q2 2027 |
| DAO governance framework | Q3 2027 |
| Expand to 30+ African countries | 2027 |

---

## 13. Team

### Musa AIS — Founder & Lead Developer

Full-stack developer based in Nigeria with expertise spanning smart contract development (Solidity/Foundry), backend systems (Python/FastAPI/Flask), web frontend (React/ethers.js), and mobile (Flutter).

**Previous projects:**

- **Vortix Signal Bot** — Crypto futures signal service for Gate.io USDT Perpetuals using ICT/SMC analysis, with backtesting infrastructure and Twitter/X integration
- **ArcPay DeFi Protocol** — PaymentHub and LendingPool smart contracts on Arc Testnet with USDC payments, escrow, subscriptions, and 75% LTV lending
- **VTU Platform** — Virtual Top-Up platform for Nigerian mobile data/airtime resellers, built on FastAPI + React + Flutter with Oracle Cloud deployment 

**Links:** [GitHub](https://github.com/KudiArc) · [X/Twitter](https://twitter.com/KudiArc) · [Discord](https://discord.gg/nEJfqrAsqc)

> **Advisory & Hiring:** Kudi Arc is actively seeking advisors with backgrounds in African fintech regulation, Bitnob/Flutterwave partnership experience, and Arc Network ecosystem development. Community contributors are welcomed via GitHub.

---

## 14. Why Arc Network

Arc Network is the only blockchain that satisfies all requirements for an Africa-first stablecoin protocol simultaneously:

| Requirement | Arc Network | Ethereum L1 | Polygon | Base |
|-------------|-------------|-------------|---------|------|
| Gas paid in USDC | ✅ Native | ❌ Requires ETH | ❌ Requires MATIC | ❌ Requires ETH |
| Circle USDC/EURC/USYC native | ✅ First-class | Bridged only | Bridged only | Bridged only |
| EVM compatible | ✅ | ✅ | ✅ | ✅ |
| Deterministic finality | ✅ | Probabilistic | ✅ | ✅ |
| Low transaction cost | ✅ <$0.01 USDC | ❌ $1–50+ | ✅ <$0.01 | ✅ <$0.01 |
| MetaMask / Rabby support | ✅ | ✅ | ✅ | ✅ |

The USDC-as-gas design is not a minor convenience — it is the foundational unlock for African adoption. Requiring users to hold ETH before they can use USDC has been the primary barrier to DeFi adoption in developing markets. Arc eliminates this barrier at the infrastructure level.

---

## 15. Risks & Mitigations

| Risk | Category | Likelihood | Impact | Mitigation |
|------|----------|-----------|--------|------------|
| CBN regulatory action against crypto-to-NGN offramp | Regulatory | Medium | High | Monitor VASP framework; partner with CBN-licensed Bitnob; structure as stablecoin bridge |
| Arc Mainnet delayed or cancelled | Infrastructure | Low | High | Contracts are EVM-compatible; can redeploy to Base or Polygon with minor config changes |
| Payout partner (Bitnob/Flutterwave) API failure | Operational | Medium | Medium | Multi-partner routing; fallback to manual resolution; automated country disable |
| FX oracle manipulation (Open Exchange Rates) | Technical | Low | Medium | ±20% rate bounds in contract; Chainlink integration in Phase 8 |
| Smart contract exploit | Technical | Low | High | Reentrancy guards, timelocks, SafeERC20; third-party audit pre-mainnet; bug bounty planned |
| Circle USYC allowlist rejection | Business | Medium | Low | USYC is additive — swap and remittance features are fully independent |
| Single-founder key person risk | Team | Medium | High | Open-source codebase; seeking co-founder and advisors; multisig on mainnet |
| SQLite data loss at scale | Technical | High (testnet only) | Low | PostgreSQL migration is pre-mainnet requirement — already planned |
| NGN devaluation reduces perceived yield | Market | High | Low | USYC yield is USD-denominated; NGN display is informational only |

---

## 16. Legal Disclaimer

This whitepaper is provided for informational purposes only and does not constitute financial advice, investment advice, or a solicitation to purchase any securities or financial instruments. Nothing in this document should be construed as a promise or representation about future performance, returns, or outcomes.

Kudi Arc is currently deployed on **Arc Testnet only**. All figures (swap volumes, fees, APY) reflect testnet activity and are not indicative of mainnet performance. Testnet tokens have no real monetary value.

Participation in DeFi protocols involves significant risk, including but not limited to: smart contract vulnerabilities, regulatory changes, counterparty risk with fiat payout partners, and total loss of funds. Users should conduct their own research and consult qualified advisors before engaging with any financial protocol.

Kudi Arc does not hold a money transmission license, virtual asset service provider license, or any financial services license in any jurisdiction as of the date of this document. Mainnet operations will be structured in compliance with applicable regulations, particularly CBN VASP guidelines in Nigeria.

All contract addresses, APY figures, and partner integrations referenced in this document are subject to change. The most current information is always available at [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc).

---

*Kudi Arc — Financial infrastructure for Africa, built on Arc Network.*  
*Kudi means money. Arc means infrastructure. Together — financial freedom for Africa. 🌍*
