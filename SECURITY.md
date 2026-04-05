# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Kudi Arc, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Contact us at: security@kudiarc.xyz

We will respond within 48 hours and work with you to resolve the issue.

---

## Smart Contract Security

### KudiSwap V2

| Item | Detail |
|---|---|
| Address | `0x8a10D0e61201000B5456EC725165892B08832C5f` |
| Network | Arc Testnet |
| Compiler | Solidity 0.8.24 |
| Audit | SolidityScan (March 2026) |
| Security Score | 60.58 / 100 |
| Threat Score | 97 / 100 — Low Risk |
| Critical Issues | 0 |
| High Issues | 1 (custodial model — by design) |

### Security Features

- ✅ Reentrancy guard on all fund-moving functions
- ✅ 5-minute timelock on rate updates
- ✅ 24-hour timelock on withdrawals
- ✅ 50% maximum withdrawal per transaction
- ✅ Minimum liquidity invariant (1 USDC)
- ✅ Absolute rate bounds (0.5 — 2.0)
- ✅ Relative rate bounds (±20% per update)
- ✅ SafeERC20 for all token transfers
- ✅ Two-step ownership transfer
- ✅ No pending action overwrite
- ✅ CEI (Checks-Effects-Interactions) pattern

### Known Limitations

This contract uses a **custodial FX model**:
- Owner controls exchange rates (bounded + timelocked)
- Owner provides liquidity (withdrawal is timelocked)
- Users trust the operator — similar to Bitnob, Yellowcard

This is intentional. NGN offramp requires centralized partners.
Full AMM model is planned for V3.

---

## Audit Reports

- [SolidityScan Report — KudiSwap V1](docs/audit-v1.pdf)
- [SolidityScan Report — KudiSwap V2](docs/audit-v2.pdf)
