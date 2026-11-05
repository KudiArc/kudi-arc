# Changelog

## v2.1 — November 2026

### Deployment hardening
- The web server now serves only the new `public/` folder (the five front-end pages). Backend code, `.env`, the database and `.git` are no longer inside the web root.
- The database now defaults to `~/.kudi-data/kudi.db`, outside the project folder; set `DB_PATH` to move it.
- Example nginx config denies dotfiles and data/source file types as a second layer.
- New `scripts/check_exposure.sh`: run it after every deploy; it fails if any sensitive path is publicly readable.
- Tests fail if `public/` ever contains source, data or secret files.
- Security reports now go through GitHub private vulnerability reporting (see `SECURITY.md`).
- Thanks to kta1kri for responsible disclosure of a web server exposure.

## v2.0 — October 2026

### KudiSend now uses an on-chain escrow
- New `KudiSendEscrow` contract holds a sender's deposit until the payout is verified (settle) or fails (refund). Senders can reclaim an untouched deposit after 72 hours, and pausing never blocks that.
- New send flow: signed one-time challenge, locked quote (10-minute countdown), approve and deposit, server-side on-chain verification, payout.
- The old `POST /api/send/payout` endpoint is retired and returns `410`.
- Money maths uses exact decimals and always rounds payouts down.
- A provider timeout never triggers a second provider; the order is held for review instead.
- The send page shows the real per-country fee.

### Admin dashboard
- Owner-signed admin login: single-use nonce, signature bound to the exact request (method, path, query, body).
- Admin is disabled unless `OWNER_ADDRESS` is configured. The server no longer reads any private key.
- New **Send Orders** page: settle, refund, record unknown payout results, and find deposits that were never confirmed.
- Revenue fee floor, editable in the dashboard.
- Admin settings are stored in the database (shared by all workers).
- Dashboard RPC status now reflects the server's view of the chain, and warns when the wallet's own RPC is unreachable (checked before settle/refund).
- Fixed the admin menu not responding to taps on phones.

### Backend hardening
- Webhooks are rejected unless their secrets are configured, use constant-time comparison, and are re-verified with the payout partner before an order is marked final. Pending statuses are never treated as failures.
- `POST /api/swap/record` now reads the swap from the chain (wallet, tokens, amounts, fee) instead of trusting the browser, and ignores duplicates.
- `NETWORK=testnet|mainnet` setting with server-provided network details for the pages.
- Request bodies are size-limited. Sandbox mode is an explicit `SEND_MODE` setting.
- Updated Arc RPC and explorer URLs.

### Documentation
- Documentation now describes only what is live, with future work clearly marked as planned. Removed claims about unbuilt features (Wave payouts, automatic route disabling, a mainnet API, rate limiting, "audited" for an automated scan) and updated stale dates, fees, the yield status, health-check output and live statistics. Market-size figures and the Nigeria FX-premium claim in the whitepaper were re-checked against the World Bank, Chainalysis and the Central Bank of Nigeria and corrected.

### Known issues documented
- SECURITY.md now lists two known KudiSwap V2 limitations: fee accounting across both swap directions (low severity, fix planned for the next contract version) and rate changes being visible before they apply.

### Tooling
- 149 backend tests (pytest) and 22 contract tests (Foundry).
- Duplicate contract copies removed: `src/` is the single source.

## v1.0 — March 2026
Initial testnet release: rates, countries, banks, swap, send, history, yield, health.
