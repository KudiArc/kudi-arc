# Kudi Arc — Technical Whitepaper

**Version:** 1.1 &nbsp;|&nbsp; **Date:** Updated October 2026 (first published March 2026) &nbsp;|&nbsp; **Network:** Arc Testnet (KudiArc mainnet launch date to be announced)

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

The protocol deploys KudiSwap V2 — a Solidity 0.8.24 smart contract — on Arc Testnet (Chain ID 5042002), enabling USDC ↔ EURC swaps with live FX rates, a 0.30% fee, and multi-layered security controls. A Flask-based backend bridges on-chain activity to licensed fiat payout partners (Flutterwave, with Bitnob and Paystack as fallbacks) across 10 African countries (sandbox payouts on testnet). USYC integration lets users earn a variable yield on idle USDC balances via Circle's tokenized US Treasury product.

This document describes the protocol's architecture, economic model, security design, competitive positioning, risks, and roadmap to Arc Mainnet.

---

## 1. Problem Statement

### 1.1 The African Forex Crisis

Nigeria — Africa's most populous country, with over 220 million people — has restricted access to US dollars for years, and the naira was sharply devalued in 2023–24. FX reforms have since narrowed the gap between the official and parallel market rates: the Central Bank governor reported the premium fell from about 50% in 2022 to under 2% on average in 2025, and in October 2026 the parallel rate was roughly 4% above the official rate. Even so, dollar access remains uneven and businesses and individuals still carry currency risk. That is the problem a stablecoin FX layer addresses.

This is not a Nigeria-only problem. Fourteen countries in West and Central Africa use CFA francs, which are pegged to the euro, and many other African countries manage their exchange rates, which adds FX friction to cross-border commerce.

### 1.2 Remittance Costs

Sub-Saharan Africa received about **$54 billion** in remittances in 2023 (World Bank, Migration and Development Brief 40). It is the most expensive region in the world to send money to: the average cost of sending $200 was **8.46%** in Q3 2025 (World Bank, Remittance Prices Worldwide), against a 6.36% global average. At that rate, sending $200 costs about $17 in fees. Money transfer operators and banks carry a large share of this flow.

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

- **Fee:** 0.30% per swap (fees at other providers vary and are often higher; see the approximate comparison below)
- **Slippage protection:** `minAmountOut` parameter enforced on-chain
- **Rate timelock:** 5-minute delay on any rate update — prevents flash manipulation
- **Rate bounds:** absolute (0.5–2.0 USDC/EURC) and relative (±20% per update) enforced in contract

### 2.2 Remittance (KudiSend)

A crypto-to-fiat flow that bridges on-chain stablecoin deposits to local bank and mobile-money payouts. On testnet, payouts run in **sandbox mode** (no real money moves).

1. User signs a one-time challenge with their wallet and receives a locked quote (exact fee, rate and payout, valid for 10 minutes)
2. User approves the token and deposits it into the `KudiSendEscrow` contract against the quote's reference
3. The backend reads the chain to verify the deposit (wallet, token, exact amount, quote window), then routes the payout to the payout partner
4. The partner pays the recipient's bank account or mobile wallet; the backend confirms the result with the partner
5. The owner settles confirmed orders to the treasury, or refunds failed ones. A sender can reclaim an untouched deposit after 72 hours
6. Both the on-chain deposit transaction and the payout partner reference are stored for every order

Supports **10 African countries** (sandbox payouts on testnet). The planned mainnet launch starts with **Nigeria (NGN)**, with other corridors to follow; expansion beyond 10 countries is a plan, not yet scheduled.

### 2.3 Yield (KudiYield)

Integration with Circle's USYC — a tokenized money market fund backed by short-duration US Treasury Bills, issued directly on Arc Network:

- **Current APY:** 4.86% (variable, tracks Fed Funds Rate)
- USYC price is read from the Teller at the time of use (it changes daily)
- Eligible to non-US institutions (African entities qualify under Circle's allowlist)
- No lock-up period in the KudiYield contract. Withdrawals depend on USYC redemption being available, and the owner can pause the contract
- Earnings displayed in NGN equivalent to provide local context

---

## 3. Competitive Landscape

Kudi Arc occupies a distinct position: a crypto-native FX and remittance protocol built specifically for Africa, on infrastructure (Arc) that removes the gas complexity that has historically prevented adoption.

| Provider | Type | Fee | Crypto-Native | Yield | On-chain verifiable | Africa-First |
|----------|------|-----|---------------|-------|----------------|--------------|
| **Kudi Arc** | Hybrid DeFi/CeFi | **0.30%** swap · **0.8–4.5%** send | ✅ USDC/EURC | ✅ via USYC (variable) | ✅ Arc explorer | ✅ |
| Yellow Card | Crypto Exchange | 1.5–3% | ✅ Multi-token | ❌ | ❌ | ✅ |
| Chipper Cash | Mobile Money | Free–2% | ❌ Fiat-only | ❌ | ❌ | ✅ |
| Grey Finance | Stablecoin Wallet | 1% | ✅ USDC/USDT | ❌ | ❌ | ✅ |
| Western Union | Traditional | 5–9% | ❌ Fiat-only | ❌ | ❌ | ❌ |
| Lemfi | Neobank | 0.5–1% | ❌ Fiat-only | ❌ | ❌ | Partial |

*Competitor figures are approximate, taken from public information at the time of first publication (March 2026), and may have changed. Verify before relying on them.*

**Key differentiators:**

- Built on Arc, where gas is paid in USDC, so users do not need to buy a separate gas token
- Combines on-chain FX swap, remittance and yield in a single interface
- All swap logic is publicly verifiable on the Arc explorer — no black-box rate manipulation
- 0.30% swap fee is low compared with the providers in the table above (approximate; see the note)

---

## 4. Smart Contract Architecture

### 4.1 KudiSwap V2

| Item | Detail |
|------|--------|
| **Address** | `0x8a10D0e61201000B5456EC725165892B08832C5f` |
| **Compiler** | Solidity 0.8.24 |
| **Network** | Arc Testnet (Chain 5042002) |
| **Status** | ✅ Verified on the Arc explorer |

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

- Contract source code publicly verified on the Arc explorer
- All admin actions emit on-chain events with timestamps
- 5-minute (rate) and 24-hour (liquidity withdrawal) timelocks give users advance warning of those owner actions
- Rate bounds (absolute and relative) prevent extreme manipulation even by the owner

The roadmap toward progressive decentralization is outlined in [Section 10](#10-governance--upgrade-path).

---

## 5. Backend Architecture

The Flask backend (Python 3.10) bridges on-chain activity to off-chain payout infrastructure and FX data sources.

### 5.1 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rates` | GET | Live USD/EUR/NGN rates — refreshed every 5 minutes |
| `/api/countries` | GET | 10-country payout configs with live local currency rates |
| `/api/banks` | GET | Nigerian bank list (26 banks) for account validation |
| `/api/send/challenge` · `/api/send/quote` | POST | Signed challenge, then a locked quote (fee, rate, payout) |
| `/api/send/confirm` | POST | Verifies the escrow deposit on-chain, then routes the payout to the correct partner per country |
| `/api/send/order/{id}` | GET | Order status |
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
| WSGI | Gunicorn (2 workers) | Gunicorn (8+ workers) |
| Web server | Nginx | Nginx + Certbot SSL |
| Process mgr | systemd | systemd + monitoring |

---

## 6. Fiat Settlement Layer

This is the highest-risk component of the protocol. Fiat settlement depends on third-party payout partners: Flutterwave (primary), with Bitnob and Paystack as fallbacks. **On testnet all payouts run in sandbox mode.**

### 6.1 Transaction Flow

1. User connects wallet and enters destination country, recipient details and amount (USDC or EURC)
2. User signs a one-time challenge (EIP-191) and the backend returns a locked quote
3. User approves the token and deposits into the `KudiSendEscrow` contract
4. Backend verifies the deposit on-chain (transaction succeeded, sent to the escrow, matching quote reference, wallet, token and exact amount, made within the quote window)
5. Backend claims the order exactly once and calls the payout partner (idempotent reference per order)
6. Partner pays the recipient's bank account or mobile wallet
7. Partner webhook arrives; the backend authenticates it, re-checks the result with the partner, and updates the order
8. Owner settles completed orders to the treasury, or refunds failed ones

### 6.2 Partner Coverage

| Partner | Countries | Role | Status |
|---------|-----------|------|--------|
| Flutterwave | All 10 corridors | Primary | Integrated (sandbox mode) |
| Bitnob | Nigeria, Ghana, Kenya | Fallback | Integrated (sandbox mode); webhook scheme not yet confirmed against its official documentation |
| Paystack | Nigeria, Ghana, Kenya, South Africa | Fallback | Integrated (sandbox mode) |

Payout methods are bank transfer or mobile money. Wave is not integrated.

### 6.3 Failure Modes & Recovery

| Situation | Handling |
|-----------|----------|
| Partner definitely rejects the transfer (e.g. invalid account) | Order becomes `refund_required`; the owner refunds the deposit to the sender |
| Partner timeout or server error (outcome unknown) | No second partner is tried (to avoid paying twice). Order becomes `payout_unknown`; the owner checks the partner dashboard and records the result |
| Deposit arrives after the quote expired | Order becomes `refund_required` |
| Partner webhook reports a non-final status | Ignored. Only final results change an order |
| Forged or unauthenticated webhook | Rejected. Webhooks are refused entirely until their secrets are configured |
| Owner takes no action | The sender can call `claimRefund` after 72 hours |

**Testnet:** best-effort, aiming to settle or refund every order within 24 to 48 hours.
**Mainnet target:** faster automated retry and resolution for reversible failures (not yet built).

### 6.4 KYC & Compliance

At testnet stage, KYC is minimal (wallet address + phone number for mobile payouts). Mainnet compliance will depend on Arc Network's regulatory framework and partner requirements. Nigeria-specific: CBN's Virtual Asset Service Provider (VASP) regulations will apply to NGN offramp operations.

---

## 7. Supported Countries & Currencies

| Country | Currency | Symbol | Payout Methods | Partner |
|---------|----------|--------|----------------|---------|
| 🇳🇬 Nigeria | NGN | ₦ | Bank transfer, mobile money | Flutterwave |
| 🇰🇪 Kenya | KES | KSh | Bank transfer, mobile money | Flutterwave |
| 🇬🇭 Ghana | GHS | GH₵ | Bank transfer, mobile money | Flutterwave |
| 🇿🇦 South Africa | ZAR | R | Bank transfer | Flutterwave |
| 🇸🇳 Senegal | XOF | CFA | Mobile money | Flutterwave |
| 🇨🇮 Côte d'Ivoire | XOF | CFA | Mobile money | Flutterwave |
| 🇨🇲 Cameroon | XAF | FCFA | Mobile money | Flutterwave |
| 🇹🇿 Tanzania | TZS | TSh | Bank transfer, mobile money | Flutterwave |
| 🇺🇬 Uganda | UGX | USh | Bank transfer, mobile money | Flutterwave |
| 🇷🇼 Rwanda | RWF | RF | Bank transfer, mobile money | Flutterwave |

FX data covers NGN, KES, GHS, ZAR, XOF, XAF, TZS, UGX, and RWF — 9 currencies refreshed every 5 minutes from the Open Exchange Rates API. Expansion to more countries is a plan, not yet scheduled.

---

## 8. Fee Structure & Protocol Economics

### 8.1 Fee Schedule

| Action | Fee | Collected In | Recipient |
|--------|-----|--------------|-----------|
| USDC → EURC Swap | 0.30% | USDC | Protocol treasury |
| EURC → USDC Swap | 0.30% | EURC | Protocol treasury |
| Remittance send | 0.8%–4.5% by corridor (a minimum fee floor, 0.3% by default, is configurable) | Sent token | Protocol treasury |
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

> These figures are illustrative projections only, not forecasts. They assume a 0.30% fee on all volume; remittance corridors currently charge more (0.8%–4.5%).

---

## 9. Security Model

### 9.1 Automated Scan Results

KudiSwap V2 was scanned with SolidityScan (automated static analysis, March 2026). **This is not a manual audit.** KudiSendEscrow (added in v2.0) has not been through an external scan or audit; it has 22 Foundry tests including a fuzz test.

| Metric | Result |
|--------|--------|
| Security Score | 60.58 / 100 |
| Threat Score | **97 / 100 — Low Risk** ✅ |
| Critical Vulnerabilities | **0** |
| High Vulnerabilities | **0** |

> **Note on the 60.58 score:** SolidityScan's methodology penalises custodial design patterns — specifically owner-controlled rate updates and liquidity management. These patterns are intentional and bounded. The **97/100 Threat Score** is the relevant vulnerability metric. All owner-callable functions have explicit timelocks, bounds, and emit public events. A third-party manual audit is planned before mainnet launch (date to be set).

### 9.2 Known Limitations

| Limitation | Detail | Mitigation |
|-----------|--------|------------|
| Centralized oracle | FX rates from Open Exchange Rates API | ±20% bounds limit exposure; Chainlink in Phase 8 |
| Custodial rate control | Owner can update rates within bounds + 5-min delay | Timelocked — users have 5 min to exit |
| Single-key ownership | Single EOA owner on testnet | Planned: multisig before mainnet (Phase 6) |
| No manual audit | Automated tooling and tests only | Third-party audit planned before mainnet (date to be set) |
| SQLite database | Not suitable for production scale | PostgreSQL migration pre-mainnet |

---

## 10. Governance & Upgrade Path

Kudi Arc launches as a centralized protocol with a planned path toward progressive decentralization. The stages below are intentions, not commitments.

| Phase | Governance Model | Timeline |
|-------|-----------------|----------|
| Testnet (Now) | Single EOA owner — full control with timelocked actions | Current |
| Mainnet Launch (Phase 6) | Planned: 3-of-5 multisig (team + 2 external signers) | Before mainnet launch (date to be set) |
| V3 (Phase 9) | Planned: Chainlink oracle anchors rates — owner can no longer set arbitrary rates | Indicative: Q4 2026 |
| V4 (Phase 7+) | Planned: AMM formula replaces manual rates — owner rate control removed | Indicative: 2027 |
| DAO (Future) | KUDI governance token — community fee votes, LP governance | TBD |

**Admin transparency:** Every privileged action (rate update, fee change, liquidity withdrawal) emits an on-chain event. Users can monitor the contract's event log on the Arc explorer at any time.

---

## 11. Market Opportunity (TAM)

| Market Segment | Size | Kudi Arc Relevance |
|---------------|------|-------------------|
| Sub-Saharan Africa inbound remittances | About $54B in 2023 (World Bank) | Primary: KudiSend |
| Nigeria inbound remittances | About $19.5B in 2023 (World Bank) | Primary: KudiSend (NGN corridor) |
| Sub-Saharan Africa on-chain crypto value received | $205B between July 2024 and June 2025, up 52% year on year. Stablecoins are about 43% of transaction volume (Chainalysis, 2025 Geography of Crypto report) | KudiSwap |
| Nigeria on-chain crypto value received | $92.1B between July 2024 and June 2025 (Chainalysis) | KudiSwap and KudiSend |
| Tokenized US Treasury products (USYC) | Growing market (no figure cited) | KudiYield integration |

*These are total market figures from the cited sources, checked in October 2026. They describe the market, not Kudi Arc's own usage. Earlier versions of this document cited a "$180B+ Africa stablecoin volume" figure and several unsourced market-size rows; these were removed because they could not be supported.*

**Conservative scenario (illustrative):** Capture 0.1% of Nigeria's roughly $19.5B in inbound remittances = about $19.5M annual volume = about $58,500/year in fees at a 0.30% fee (about $156,000 at the 0.8% NGN corridor fee).

**Growth scenario (illustrative):** 1% of Nigeria + 0.5% of the remaining 9 countries = ~$400M annual volume = ~$1.2M/year in fees at a 0.30% fee.

---

## 12. Roadmap

> Items below marked "Planned" are intentions, not commitments. Dates are indicative and may change.

### Testnet — 2026 (Current)

| Milestone | Status |
|-----------|--------|
| KudiSwap V2 deployed & verified on the Arc explorer | ✅ Complete |
| 10-country remittance support (KudiSend, sandbox payouts) | ✅ Complete |
| USYC yield integration (KudiYield) | ✅ Complete |
| Transaction history per wallet | ✅ Complete |
| SolidityScan automated scan | ✅ Complete |
| Flutterwave, Bitnob and Paystack integrations | ✅ Integrated (sandbox mode) |
| Circle USYC allowlist approval | ✅ Complete |
| Escrow-backed KudiSend, owner-signed admin dashboard, authenticated and verified webhooks, on-chain verified swap records (v2.0, October 2026) | ✅ Complete |
| SSL on kudiarc.xyz | ✅ In place |
| User beta testing program | ⏳ In Progress |

### Mainnet — date to be announced

| Milestone | Status |
|-----------|--------|
| KudiArc mainnet deployment (Arc Mainnet itself is live since 16 Sept 2026) | Planned |
| Real payouts (`SEND_MODE=live`), starting with Nigeria (NGN) after partner sandbox testing and webhook setup | Planned |
| PostgreSQL migration (replace SQLite) | Planned |
| Multisig ownership (3-of-5) | Planned |
| Third-party smart contract audit | Planned (before mainnet) |
| CDN | Planned |
| Remaining corridors after Nigeria, then expansion beyond 10 countries | Planned |

### V3 — Indicative: late 2026

| Milestone | Target |
|-----------|--------|
| Chainlink oracle integration | Q4 2026 |
| AMM model (x*y=k) replacing manual rate setting | Q4 2026 |
| Open liquidity provision + LP token system | Q4 2026 |
| (CCTP) Multi-chain deployment (Base, Stellar, Ethereum, Solana) | Planned |
| Paymaster | Q4 2026 |

### V4 — Indicative: 2027

| Milestone | Target |
|-----------|--------|
| Mobile app (React Native) — iOS & Android | Q1 2027 |
| KUDI governance token consideration | Q2 2027 |
| DAO governance framework | Q3 2027 |
| Expand to more African countries | Planned |
| Circle Programmable Wallets | Q1 2027 |

---

## 13. Team

### Musa Ali (Musa Ais) — Founder & Lead Developer

Full-stack developer based in Nigeria with expertise spanning smart contract development (Solidity/Foundry), backend systems (Python/FastAPI/Flask), web frontend (React/ethers.js), and mobile (Flutter). 

200Level Computer Science student, Federal University Dutse, Faculty of Computing, Nigeria.

**Previous projects:**

- **Vortix Signal Bot** — Crypto futures signal service for Gate.io USDT Perpetuals using ICT/SMC analysis, with backtesting infrastructure and Twitter/X integration
- **ArcPay DeFi Protocol** — PaymentHub and LendingPool smart contracts on Arc Testnet with USDC payments, escrow, subscriptions, and 75% LTV lending
- **VTU Platform** — Virtual Top-Up platform for Nigerian mobile data/airtime resellers, built on FastAPI + React + Flutter with Oracle Cloud deployment 

**Links:** [GitHub](https://github.com/KudiArc) · [X/Twitter](https://twitter.com/Musa_Ais) · [Discord](https://discord.gg/nEJfqrAsqc)

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
| Payout partner (Bitnob/Flutterwave) API failure | Operational | Medium | Medium | Multi-partner routing; unknown outcomes are held for manual resolution (no automatic country disable yet) |
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
