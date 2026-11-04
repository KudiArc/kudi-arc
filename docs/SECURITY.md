# Security Policy — Kudi Arc

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Kudi Arc — smart contracts, backend API, or frontend — please report it responsibly:

| Channel | Contact |
|---------|---------|
| **GitHub (preferred)** | [Report privately](https://github.com/KudiArc/kudi-arc/security/advisories/new) |
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

> 🚧 **A formal bug bounty program is planned for mainnet launch (date to be announced).** Until then, we offer public recognition and a discretionary reward for valid findings.

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
| **Explorer** | [View on the Arc explorer](https://explorer.testnet.arc.io/address/0x8a10D0e61201000B5456EC725165892B08832C5f) |

> **Note on Security Score (60.58):** SolidityScan's scoring system penalises custodial design patterns — specifically owner-controlled rate updates and liquidity management. These controls are **intentional and bounded**. The 97/100 Threat Score (the actual vulnerability risk metric) is the relevant number. All owner-callable functions have explicit timelocks, rate bounds, and emit public events. A third-party manual audit is planned before mainnet launch (date to be set).

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
| Events | All admin actions emit events | Publicly viewable on the Arc explorer |

### KudiSend Escrow

| Item | Detail |
|------|--------|
| **Address** | `0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010` |
| **Network** | Arc Testnet (Chain ID 5042002), source verified on the explorer |
| **Compiler** | Solidity 0.8.24 |
| **Tests** | 22 Foundry tests including a fuzz test |
| **Audit** | Not yet audited. Planned before holding real user funds on mainnet |

| Control | Detail |
|---------|--------|
| One deposit per reference | A quote reference can never be reused, even after settle or refund |
| Allow-listed tokens | Only 6-decimal tokens added by the owner (USDC, EURC) |
| On-chain limits | Minimum and maximum deposit enforced by the contract |
| Exact amount | Deposits that arrive short (fee-on-transfer tokens) are rejected |
| Reentrancy | `nonReentrant` on deposit, claimRefund, settle and refund |
| User escape hatch | The depositor can `claimRefund` after 72 hours. Pausing never blocks this |
| Pause | Stops new deposits only. Settle, refund and claimRefund keep working |
| Ownership | Two-step transfer (a multisig is planned for mainnet) |

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
- Multisig ownership planned for mainnet (3-of-5 Gnosis Safe, before mainnet launch)

### Oracle Dependency

FX rates are sourced from the Open Exchange Rates API (centralized). A stale or manipulated feed could result in unfavorable rates for users. The contract's rate bounds limit worst-case exposure. Chainlink oracle integration is planned for V3 (date to be set).

### Rate Changes Are Visible Before They Apply

A queued rate change is public for 5 minutes before it can be applied, and applying it is permissionless. Traders can therefore see an upcoming rate and trade at the current one first. The owner can also move the rate up to 20% per update inside the 0.5–2.0 band, so swappers are protected only by their `minAmountOut`. This follows from the owner-set-rate design; the planned oracle and AMM versions remove it.

### Fee Accounting in KudiSwap V2 (Known, Low Severity)

Swap fees are charged in the input token, but both swap directions add them to a single `accruedFees` counter, and fee funds are not kept separate from pool balances. As a result:

- `withdrawFees(token)` pays the whole counter in whichever token the owner chooses, so one token can be over-paid (using pool liquidity) or the call can revert, while fees in the other token stay in the pool
- the 50% and minimum-liquidity checks on liquidity withdrawals include fee funds
- the counter does not match the pool's real fee balances

Swappers' funds are not at risk: only the owner can add liquidity or withdraw fees. The deployed contract is immutable, so the fix (separate USDC and EURC fee counters, excluded from the liquidity checks) is planned for the next contract version, before any mainnet deployment. The dashboard's fee revenue figures come from the app's database, not from this counter. Until the fix, do not rely on `withdrawFees` on the testnet contract.

### Single-Key Ownership (Testnet Only)

The current deployment uses a single EOA owner. This is acceptable for testnet but will be replaced by a 3-of-5 multisig before mainnet deployment.

### Single-Key Escrow Owner (Testnet Only)

The escrow owner is a single wallet that can settle or refund deposits. It cannot take a deposit that is not tied to a verified payout without the funds going to the treasury address set at deployment, and it cannot block a depositor's 72-hour refund. A multisig will replace the single owner before mainnet.

### SQLite Database

The backend currently uses SQLite for transaction records. This is a known testnet limitation — PostgreSQL migration is a pre-mainnet requirement.

---

## Audit Reports

| Version | Tool | Date | Status |
|---------|------|------|--------|
| KudiSwap V1 | SolidityScan | Feb 2026 | ✅ Complete — deprecated |
| KudiSwap V2 | SolidityScan | March 2026 | ✅ Complete |
| KudiSwap V2 and KudiSendEscrow | Third-party manual | Date to be set | ⏳ Planned (before mainnet) |

---

## Mainnet Security Roadmap

Planned items, not commitments. Dates are to be set.

| Item | Target |
|------|--------|
| Third-party manual audit | Before mainnet launch |
| 3-of-5 multisig ownership (Gnosis Safe) | Before mainnet launch |
| Formal bug bounty program | At mainnet launch |
| Chainlink oracle (replace centralized feed) | Indicative: late 2026 |
| AMM model (remove owner rate control) | Indicative: late 2026 / 2027 |

---

## Infrastructure Security

- **Server:** Oracle Cloud Ubuntu VM
- **Web server:** Nginx with reverse proxy
- **Process manager:** systemd (backend), Gunicorn (WSGI)
- **HTTPS:** Certbot SSL in place on kudiarc.xyz
- **Firewall:** operators should restrict inbound traffic to SSH, HTTP and HTTPS (check with `sudo ufw status` and the cloud security list)
- **Private keys:** Never stored on server — all signing happens client-side

---

*For non-security issues, open a GitHub issue at [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc).*

**Application controls (v2.0):**
- The server holds no private key. Admin actions are signed by the owner wallet.
- Admin endpoints accept only single-use, request-bound owner signatures and are disabled unless `OWNER_ADDRESS` is set.
- Partner webhooks are rejected unless their secrets are configured, and results are re-checked with the partner before an order is finalised.
- Swap records are read from the chain, not taken from the browser.
- Request bodies are size-limited and money maths uses exact decimals.
