# Security Policy — Kudi Arc

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Kudi Arc — smart contracts, backend API, or frontend — please report it responsibly:

| Channel | Contact |
|---------|---------|
| **Email** | security@kudiarc.xyz |
| **Twitter DM** | [@KudiArc](https://twitter.com/KudiArc) (for initial contact only) |
| **Discord** | Private message to `@kudicarc` on [discord.gg/kudiarc](https://discord.gg/kudiarc) |

### Disclosure Timeline

| Step | Timeframe |
|------|-----------|
| Initial acknowledgement | Within 48 hours |
| Severity assessment | Within 5 business days |
| Patch or mitigation deployed | Within 14 days (critical), 30 days (high) |
| Public disclosure (coordinated) | After fix is deployed |

We follow coordinated responsible disclosure. We will credit researchers in the release notes unless they prefer to remain anonymous.

---

## Bug Bounty

> 🚧 **Formal bug bounty program launching at mainnet (Q3 2026).** Until then, we offer public recognition and a discretionary reward for valid findings.

**In scope:**
- KudiSwap V2 smart contract (`0x8a10D0e61201000B5456EC725165892B08832C5f`)
- Flask backend API (authentication bypass, injection, data leaks)
- Frontend wallet interaction (signature replay, approval phishing)

**Out of scope:**
- Issues on deprecated KudiSwap V1 (`0xb138329BF67cFe121A37D9947922D2B7278BdC29`)
- Theoretical issues without a proof-of-concept
- Social engineering attacks on team members
- Findings from automated scanners without manual confirmation

---

## Smart Contract Security

### KudiSwap V2

| Item | Detail |
|------|--------|
| **Address** | `0x8a10D0e61201000B5456EC725165892B08832C5f` |
| **Network** | Arc Testnet (Chain ID 5042002) |
| **Compiler** | Solidity 0.8.24 |
| **Audit Tool** | SolidityScan (automated, March 2026) |
| **Security Score** | 60.58 / 100 *(see note below)* |
| **Threat Score** | 97 / 100 — Low Risk ✅ |
| **Critical Issues** | 0 |
| **High Issues** | 0 *(custodial model is by design — see Known Limitations)* |
| **Explorer** | [View on Arcscan](https://testnet.arcscan.app/address/0x8a10D0e61201000B5456EC725165892B08832C5f) |

> **Note on Security Score (60.58):** SolidityScan's scoring system penalises custodial design patterns — specifically owner-controlled rate updates and liquidity management. These controls are **intentional and bounded**. The 97/100 Threat Score (the actual vulnerability risk metric) is the relevant number. All owner-callable functions have explicit timelocks, rate bounds, and emit public events. A third-party manual audit is planned for Q2 2026 before mainnet deployment.

### Security Controls

| Control | Implementation | Detail |
|---------|---------------|--------|
| Reentrancy | `nonReentrant` modifier + `_locked` bool | Applied to all fund-moving functions |
| Rate manipulation | 5-min timelock + ±20% relative bounds | Absolute bounds: 0.5 – 2.0 USDC/EURC |
| Liquidity drain | 24-hour timelock + 50% cap | Max 50% of pool per withdrawal transaction |
| Minimum liquidity | 1 USDC floor invariant | Contract reverts if pool would drop below |
| Token transfers | SafeERC20 inline library | Reverts on `false` return values |
| Ownership | Two-step transfer pattern | Pending owner must explicitly accept |
| Fee cap | 2% maximum (200 bps) | `setFee()` reverts if above cap |
| No action overwrite | Pending actions can't be overwritten | Prevents double-execution attacks |
| Pattern | CEI (Checks-Effects-Interactions) | State updates before external calls |
| Events | All admin actions emit events | Publicly auditable on Arcscan |

### Deprecated Contract

| Item | Detail |
|------|--------|
| **Address** | `0xb138329BF67cFe121A37D9947922D2B7278BdC29` |
| **Status** | ⚠️ Deprecated — do not interact |
| **Reason** | Replaced by V2 with enhanced security controls |

---

## Known Limitations

### Custodial FX Model (By Design)

KudiSwap V2 uses a custodial model where the contract owner controls exchange rates and provides liquidity. This is a deliberate architectural choice:

- NGN offramp **requires** licensed, centralized payout partners — full trustlessness is not possible at this layer
- Mobile-first African users need simpler UX than fully decentralized AMMs offer
- Comparable trust model to Bitnob, Yellow Card, and Grey Finance — all established, trusted operators

**Mitigations in place:**
- All rate changes require a 5-minute timelock — users can exit before new rates apply
- Rate bounds (±20% relative, 0.5–2.0 absolute) prevent extreme manipulation
- All admin actions emit on-chain events — anyone can monitor the contract
- Multisig ownership planned for mainnet (3-of-5 Gnosis Safe, Q3 2026)

### Oracle Dependency

FX rates are sourced from the Open Exchange Rates API (centralized). A stale or manipulated feed could result in unfavorable rates for users. The contract's rate bounds limit worst-case exposure. Chainlink oracle integration is planned for V3 (Q4 2026).

### Single-Key Ownership (Testnet Only)

The current deployment uses a single EOA owner. This is acceptable for testnet but will be replaced by a 3-of-5 multisig before mainnet deployment.

### SQLite Database

The backend currently uses SQLite for transaction records. This is a known testnet limitation — PostgreSQL migration is a pre-mainnet requirement.

---

## Audit Reports

| Version | Tool | Date | Status |
|---------|------|------|--------|
| KudiSwap V1 | SolidityScan | Feb 2026 | ✅ Complete — deprecated |
| KudiSwap V2 | SolidityScan | March 2026 | ✅ Complete |
| KudiSwap V2 | Third-party manual | Q2 2026 | ⏳ Planned (pre-mainnet) |

---

## Mainnet Security Roadmap

| Item | Target |
|------|--------|
| Third-party manual audit | Q2 2026 |
| 3-of-5 multisig ownership (Gnosis Safe) | Q3 2026 |
| Formal bug bounty program | Q3 2026 |
| Chainlink oracle (replace centralized feed) | Q4 2026 |
| AMM model (remove owner rate control) | Q4 2026 |

---

## Infrastructure Security

- **Server:** Oracle Cloud Ubuntu VM
- **Web server:** Nginx with reverse proxy
- **Process manager:** systemd (backend), Gunicorn (WSGI)
- **HTTPS:** Certbot SSL on mainnet domain
- **Firewall:** UFW — only ports 80, 443, and SSH exposed
- **Private keys:** Never stored on server — all signing happens client-side

---

*For non-security issues, open a GitHub issue at [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc).*
