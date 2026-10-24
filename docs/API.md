# Kudi Arc — API Reference

**Base URL (Testnet):** `https://kudiarc.xyz`  
**Base URL (Mainnet):** not available yet (date to be announced)  
**Version:** v1  
**Protocol:** HTTP/REST  
**Response Format:** JSON  

> ⚠️ **Testnet Notice:** Payouts run in sandbox mode: orders complete immediately with provider `sandbox` and no real money moves. Real payouts are planned for mainnet.

---

## Authentication

Read endpoints (rates, countries, banks, yield, history, health) are public.

**Send (KudiSend)** uses a short-lived wallet challenge. The app requests a one-time message (`POST /api/send/challenge`), the user signs it (EIP-191), and the signed challenge is exchanged for a locked quote. A challenge works once and expires after 5 minutes.

**Admin endpoints (`/api/admin/*`)** accept only the owner wallet. Every request carries a single-use nonce and a signature over that exact request:

1. `GET /api/admin/challenge` returns `{ nonce, expires_at, domain, chain_id }`
2. Build this message and sign it (EIP-191) with the owner wallet:

```
KudiArc admin request
Domain: <domain>
Chain: <chain_id>
Method: <HTTP method>
Path: <path including query string>
Body: <sha256 hex of the raw request body, or of an empty string for GET>
Nonce: <nonce>
Expires: <expires_at>
```

3. Send the request with headers `X-Admin-Nonce` and `X-Admin-Signature`.

The nonce is consumed on first use, and a signature is valid only for that exact method, path, query and body. If `OWNER_ADDRESS` is not configured, admin endpoints return `503`.

Rate limiting and optional API key authentication for partner integrations are planned for mainnet.

---

## Rate Limiting

General per-IP rate limiting is **not implemented yet** (planned for mainnet). Current protections:

- At most 10 open send challenges per wallet and 50 open admin nonces (excess returns `429`)
- Request bodies are limited to 1 MB

## Error Format

Errors from the send and admin endpoints use a short code:

```json
{
  "error": "Amount must be between 10 and 50 USDC",
  "code": "amount_out_of_range"
}
```

Older read endpoints return `{ "error": "message" }`.

| HTTP Code | Meaning |
|-----------|---------|
| `400` | Bad request: invalid or missing parameters |
| `401` | Unauthorized: bad, used or expired challenge/signature, or not the owner |
| `404` | Resource not found |
| `409` | Conflict: order already processed |
| `410` | Endpoint retired (`/api/send/payout`) |
| `429` | Too many open challenges |
| `500` | Internal server error |
| `503` | Temporarily unavailable (maintenance, chain lookup failed, or not configured) |

---

---

## Endpoints

### Rates

#### `GET /api/rates`

Returns live FX rates for all USDC/EURC pairs and their local currency equivalents. Rates are refreshed every 5 minutes from the Open Exchange Rates API.

**Request**
```
GET /api/rates
```

**Response `200 OK`**
```json
{
  "pairs": {
    "USDC/EURC": { "rate": 0.8638, "display": "1 USDC = 0.8638 EURC" },
    "EURC/USDC": { "rate": 1.1576, "display": "1 EURC = 1.1576 USDC" },
    "USDC/NGN":  { "rate": 1382.5, "display": "1 USDC ≈ ₦1,382" },
    "EURC/NGN":  { "rate": 1592.5, "display": "1 EURC ≈ ₦1,592" }
  },
  "last_updated": 1774663084,
  "contract": "0x8a10D0e61201000B5456EC725165892B08832C5f"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `pairs` | object | All supported FX pairs with live rates |
| `last_updated` | unix timestamp | When rates were last fetched from the oracle |
| `contract` | string | KudiSwap V2 contract address for reference |

**cURL Example**
```bash
curl https://kudiarc.xyz/api/rates
```

---

### Countries

#### `GET /api/countries`

Returns all supported payout countries with live local currency rates and partner information.

**Response `200 OK`**
```json
{
  "countries": [
    {
      "code": "NG",
      "name": "Nigeria",
      "currency": "NGN",
      "symbol": "₦",
      "flag": "🇳🇬",
      "partner": "Bitnob",
      "rate_per_usd": 1382.5,
      "rate_per_eurc": 1592.5,
      "display_usd": "1 USDC = ₦1,382.5",
      "display_eur": "1 EURC = ₦1,592.5",
      "available": true
    },
    {
      "code": "KE",
      "name": "Kenya",
      "currency": "KES",
      "symbol": "KSh",
      "flag": "🇰🇪",
      "partner": "Flutterwave",
      "rate_per_usd": 129.4,
      "rate_per_eurc": 149.8,
      "display_usd": "1 USDC = KSh129.4",
      "display_eur": "1 EURC = KSh149.8",
      "available": true
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | ISO 3166-1 alpha-2 country code |
| `currency` | string | ISO 4217 currency code |
| `partner` | string | Fiat payout partner for this corridor |
| `rate_per_usd` | float | How much local currency 1 USDC buys |
| `available` | boolean | `false` if partner is temporarily down for this country |

**Supported Countries**

| Code | Country | Currency | Partner |
|------|---------|----------|---------|
| NG | Nigeria | NGN | Bitnob • Flutterwave |
| KE | Kenya | KES | Flutterwave |
| GH | Ghana | GHS | Flutterwave |
| ZA | South Africa | ZAR | Flutterwave |
| SN | Senegal | XOF | Flutterwave |
| CI | Côte d'Ivoire | XOF | Flutterwave |
| CM | Cameroon | XAF | Flutterwave |
| TZ | Tanzania | TZS | Flutterwave |
| UG | Uganda | UGX | Flutterwave |
| RW | Rwanda | RWF | Flutterwave |

---

### Banks

#### `GET /api/banks`

Returns the list of Nigerian banks supported for NGN payouts, including bank codes required by the `/api/send/quote` endpoint.

**Response `200 OK`**
```json
{
  "banks": [
    { "name": "Access Bank",       "code": "044" },
    { "name": "GTBank",            "code": "058" },
    { "name": "Zenith Bank",       "code": "057" },
    { "name": "First Bank",        "code": "011" },
    { "name": "UBA",               "code": "033" },
    { "name": "Kuda Bank",         "code": "090267" },
    { "name": "OPay",              "code": "999992" },
    { "name": "Moniepoint",        "code": "50515" }
  ],
  "count": 26
}
```

> **Note:** `bank_code` from this response is required as input to `POST /api/send/quote` for Nigerian recipients.

---

### Send / Remittance

KudiSend is a four-step flow: **challenge → quote → deposit → confirm.**

#### `GET /api/send/config`

Public settings the app needs: network, escrow address, token addresses, limits.

```json
{
  "chain_id": 5042002,
  "escrow_address": "0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010",
  "network": { "name": "Arc Testnet", "chain_id": 5042002, "rpc_url": "https://rpc.testnet.arc.io",
               "explorer_url": "https://explorer.testnet.arc.io", "native_symbol": "USDC", "native_decimals": 18 },
  "tokens": { "USDC": "0x3600…0000", "EURC": "0x89B5…D72a" },
  "mode": "mock", "quote_ttl": 600, "min_amount": "10", "max_amount": "50"
}
```

#### `POST /api/send/challenge`

Request: `{ "wallet": "0x…" }`. Response: `{ "nonce", "message", "expires_at" }`. The user signs `message` with their wallet. At most 10 open challenges per wallet.

#### `POST /api/send/quote`

Exchanges a signed challenge for a locked quote.

```json
{
  "wallet": "0x…", "nonce": "<from challenge>", "signature": "0x…",
  "token": "USDC", "amount": "20",
  "country_code": "NG", "method": "bank",
  "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058", "bank_name": "GTBank"
}
```

For `method: "mobile_money"` send `phone` instead of the bank fields. `amount` is a decimal string with at most 6 decimal places.

**Response `200 OK`**

```json
{
  "quote_id": "9f2c…", "ref": "0x…", "escrow_address": "0xd2e4…", "chain_id": 5042002,
  "token": "USDC", "token_address": "0x3600…0000",
  "amount": "20", "amount_base": "20000000", "fee": "0.16", "fee_pct": 0.8, "rate": "1500",
  "payout_amount": "29760.00", "currency": "NGN", "expires_at": 1790000600, "expires_in": 600
}
```

The fee is the higher of the country fee and the platform's minimum fee. `payout_amount` is rounded down.

| Error code | Meaning |
|------------|---------|
| `bad_challenge` / `bad_signature` (401) | Challenge unknown, used, expired, or signed by another wallet |
| `amount_out_of_range` (400) | Outside the minimum or maximum |
| `bad_amount`, `bad_token`, `bad_country`, `bad_recipient`, `bad_method` (400) | Invalid input |
| `rate_unavailable`, `chain_error`, `maintenance` (503) | Try again shortly |
| `escrow_not_configured`, `payouts_not_configured` (503) | Sending is not available yet |

#### On-chain deposit

The user approves the exact `amount_base` for the escrow, then calls:

```javascript
await escrow.deposit(token_address, amount_base, ref);   // ref comes from the quote
```

#### `POST /api/send/confirm`

Request: `{ "quote_id": "9f2c…", "tx_hash": "0x…" }`. The server checks the transaction on-chain (success, sent to the escrow, matching quote reference, wallet, token and exact amount, still active, and made inside the quote window) and then starts the payout. Safe to call again with the same hash.

| Status | Meaning |
|--------|---------|
| `200` | Order view (see below) |
| `202` | Transaction not visible yet, retry in a couple of seconds |
| `400 invalid_deposit` | The transaction does not match the quote |
| `409` | Order already processed with a different transaction |

#### `GET /api/send/order/{quote_id}`

Returns the order view: `quote_id, status, token, amount, fee, rate, payout_amount, currency, country_code, recipient_name, recipient_account_last4, tx_hash, explorer_url, expires_at, created_at`.

| Order status | Meaning |
|--------------|---------|
| `quoted` | Waiting for the deposit |
| `payout_pending` | Payout accepted by the partner, awaiting its final result |
| `completed` | Payout confirmed; ready for the owner to settle |
| `refund_required` | Payout failed or deposit arrived late; the owner refunds it |
| `payout_unknown` | Partner outcome unclear; held for manual review |
| `refunded` | Deposit returned to the sender |

#### Partner webhooks

`POST /api/send/flw-webhook` (header `verif-hash`), `POST /api/send/paystack-webhook` (`x-paystack-signature`, HMAC-SHA512) and `POST /api/send/webhook` (Bitnob, `x-bitnob-signature`). Webhooks are rejected with `503` if their secret is not configured and `401` if the signature is wrong. A webhook only triggers a check: the server asks the partner what happened and acts only on a final answer. Pending statuses are ignored.

#### `POST /api/send/payout` — retired

Returns `410 Gone`. Use the flow above.

---

### Swap Recording

#### `POST /api/swap/record`

Records a swap after the frontend sees it succeed. The server reads the swap from the chain (wallet, tokens, amounts and fee come from the contract's `Swapped` event), so only the wallet and transaction hash are needed. Anything else in the body is ignored.

```json
{ "wallet": "0x…", "tx_hash": "0x…" }
```

| Status | Meaning |
|--------|---------|
| `200` `{"status":"saved"}` | Recorded (or already recorded) |
| `202` `{"status":"pending"}` | Transaction not visible yet |
| `400` | Not a successful swap on the KudiSwap contract, or made by a different wallet |
| `503` | Chain lookup failed or swaps are not configured |

---

### Transaction History

#### `GET /api/history/:wallet`

Returns the full transaction history for a wallet address — including swaps and remittance sends.

**Path Parameter**

| Parameter | Description |
|-----------|-------------|
| `wallet` | EVM wallet address (checksummed or lowercase) |

**Query Parameters (optional)**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | `all` | Filter by `swap`, `send`, or `all` |
| `limit` | integer | 50 | Max results to return (max: 200) |
| `offset` | integer | 0 | Pagination offset |

**Response `200 OK`**
```json
{
  "wallet": "0x1234...",
  "count": 5,
  "transactions": [
    {
      "id": 42,
      "tx_type": "swap",
      "from_token": "USDC",
      "to_token": "EURC",
      "amount_in": 1.32,
      "amount_out": 1.14,
      "rate": 0.8638,
      "tx_hash": "0xecc2...",
      "explorer_url": "https://explorer.testnet.arc.io/tx/0xecc2...",
      "created_at": "2026-03-27T11:19:28Z"
    },
    {
      "id": 38,
      "tx_type": "send",
      "token": "USDC",
      "amount_usdc": 10.0,
      "payout_amount": 13795.2,
      "currency": "NGN",
      "country_code": "NG",
      "reference": "KUDI-NGN-ABCD1234",
      "status": "completed",
      "created_at": "2026-03-26T09:44:11Z"
    }
  ]
}
```

**Error Responses**
```json
{ "error": "not_found", "message": "No transactions found for this wallet", "code": 404 }
```

**cURL Example**
```bash
curl "https://kudiarc.xyz/api/history/0x1234...?type=swap&limit=10"
```

---

### Yield

#### `GET /api/yield/stats`

Returns USYC yield statistics from Circle's Arc deployment.

**Response `200 OK`**
```json
{
  "token": "USYC",
  "contract": "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C",
  "apy": 4.86,
  "price_per_usyc": 1.0214,
  "total_supply": 500000,
  "backing": "US Treasury Bills (short-duration)",
  "issuer": "Circle",
  "eligible_regions": ["Africa", "Asia", "Europe", "non-US globally"],
  "last_updated": 1774663084
}
```

| Field | Type | Description |
|-------|------|-------------|
| `apy` | float | Current annualized yield percentage |
| `price_per_usyc` | float | Current USYC price in USDC terms |
| `backing` | string | What the fund is backed by |

> ℹ️ KudiYield deposits are active on testnet. APY is a live reading; actual returns follow the USYC price, which changes over time.

---

#### `GET /api/yield/balance/:wallet`

Returns a user's USYC position and accrued earnings.

**Response `200 OK`**
```json
{
  "wallet": "0x1234...",
  "usyc_balance": 9.79,
  "usdc_value": 10.0,
  "earnings_usdc": 0.21,
  "earnings_ngn": 290.3,
  "apy": 4.86,
  "deposit_date": "2026-02-15T08:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `usyc_balance` | float | User's USYC token balance |
| `usdc_value` | float | Current USDC value of position |
| `earnings_usdc` | float | Total yield earned in USDC |
| `earnings_ngn` | float | Earnings displayed in NGN equivalent |

---

### Health

#### `GET /api/health`

Returns service health. Useful for monitoring. The endpoint always answers `200`; read the `status` field.

**Response `200 OK`**
```json
{
  "status": "ok",
  "chain": "Arc Testnet",
  "chain_id": 5042002,
  "components": {
    "api": "ok",
    "fx_oracle": "ok",
    "arc_rpc": "ok",
    "bitnob": "mock"
  },
  "version": "2.0.0"
}
```

| Component | Values |
|-----------|--------|
| `api` | `ok` |
| `fx_oracle` | `ok`, or `stale` before the first rate fetch |
| `arc_rpc` | `ok`, or `unavailable` when the chain RPC cannot be reached |
| `bitnob` | `mock` in sandbox mode, `ok` when a live key is configured |

`status` is `ok` when every component is `ok` or `mock`, otherwise `degraded`. Country routes are not disabled automatically.

---

## Admin (owner-signed)

All admin endpoints need the signed headers described under [Authentication](#authentication).

| Endpoint | Purpose |
|----------|---------|
| `GET /api/admin/challenge` | Get a single-use nonce |
| `GET /api/admin/send/orders?status=&chain_state=&limit=` | List send orders with a suggested action (`settle`, `refund`, `resolve`, `wait`) |
| `POST /api/admin/send/resolve` | Record the real result of an unclear payout: `{ "quote_id", "outcome": "paid" \| "failed" }` |
| `POST /api/admin/send/chain-sync` | Read settle/refund results from the escrow into the database |
| `POST /api/admin/send/reconcile` | Find deposits that exist on-chain but were never confirmed and process them |
| `POST /api/admin/maintenance` | Toggle maintenance mode |
| `POST /api/admin/send-settings` | Set the revenue fee floor and minimum send |
| `POST /api/admin/refresh-rates` | Force an FX rate refresh |
| `POST /api/admin/recent-txs` | Recent transactions |

Settling and refunding are done by the owner wallet directly on the escrow contract (the dashboard's Send Orders page does this); the server never holds a key.

---

## Smart Contract Interface

For direct on-chain interaction with KudiSwap V2 (`0x8a10D0e61201000B5456EC725165892B08832C5f`):

```javascript
// ethers.js v6 example
const provider = new ethers.BrowserProvider(window.ethereum);
const signer   = await provider.getSigner();
const contract = new ethers.Contract(KUDISWAP_ADDRESS, ABI, signer);

// Preview swap (no gas)
const amountOut = await contract.previewSwapUSDCtoEURC(
  ethers.parseUnits("10", 6)  // 10 USDC
);

// Execute swap
const tx = await contract.swapUSDCforEURC(
  ethers.parseUnits("10", 6),   // amountIn: 10 USDC
  ethers.parseUnits("8.5", 6)   // minAmountOut: 8.5 EURC (slippage protection)
);
await tx.wait();
```

**Key contract constants:**

| Constant | Value | Description |
|----------|-------|-------------|
| USDC address | `0x3600000000000000000000000000000000000000` | Circle USDC on Arc |
| EURC address | `0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a` | Circle EURC on Arc |
| Fee | `30` (basis points) | 0.30% per swap |
| Rate timelock | `300` seconds | 5-minute delay on rate updates |
| Withdrawal timelock | `86400` seconds | 24-hour delay on liquidity withdrawal |

### KudiSendEscrow (`0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010`)

| Function | Who | Purpose |
|----------|-----|---------|
| `deposit(token, amount, ref)` | Anyone | Deposit against a backend-issued `ref`. One deposit per `ref` |
| `claimRefund(ref)` | The depositor | Reclaim an untouched deposit after `REFUND_DELAY` (72 hours). Works while paused |
| `settle(refs[])` | Owner | Send paid-out deposits to the treasury (max 100 per call) |
| `refund(ref)` | Owner | Return a deposit to the depositor |
| `setPaused`, `setLimits`, `setTreasury`, `setTokenAllowed` | Owner | Configuration. Pausing stops new deposits only |
| `transferOwnership` / `acceptOwnership` | Owner / new owner | Two-step ownership |

Events: `Deposited(ref, user, token, amount)`, `Settled(...)`, `Refunded(..., byUser)`.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | March 2026 | Initial testnet release — rates, countries, banks, send, history, yield, health |
| v2.0 | October 2026 | Escrow-backed send (challenge, quote, confirm), owner-signed admin API, verified swap recording, authenticated webhooks. `POST /api/send/payout` retired |

---

*For integration support, open an issue at [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc) or join [discord.gg/kudiarc](https://discord.gg/nEJfqrAsqc).*
