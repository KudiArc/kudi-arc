# Kudi Arc — API Reference

**Base URL (Testnet):** `https://kudiarc.xyz`  
**Base URL (Mainnet):** `https://api.kudiarc.xyz` *(Q3 2026)*  
**Version:** v1  
**Protocol:** HTTP/REST  
**Response Format:** JSON  

> ⚠️ **Testnet Notice:** No real funds are moved on testnet. The `status` field will be `mock_success` until mainnet launch.

---

## Authentication

Currently, the API is public and requires no API key. Wallet-level authorization is enforced via **EIP-191 message signatures** on write endpoints (`/api/send/payout`).

Mainnet will introduce rate limiting and optional API key authentication for partner integrations.

---

## Rate Limiting

| Tier | Limit |
|------|-------|
| Public (testnet) | 60 requests/minute per IP |
| Partner (mainnet) | 300 requests/minute per API key |

Exceeded requests return `429 Too Many Requests`.

---

## Error Format

All errors follow a consistent structure:

```json
{
  "error": "validation_failed",
  "message": "amount_usdc must be greater than 0",
  "code": 400
}
```

| HTTP Code | Meaning |
|-----------|---------|
| `400` | Bad request — invalid or missing parameters |
| `404` | Resource not found (e.g. unknown wallet) |
| `422` | Unprocessable — signature invalid or amount out of range |
| `429` | Rate limit exceeded |
| `500` | Internal server error — report to team |
| `503` | Payout partner temporarily unavailable |

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

Returns the list of Nigerian banks supported for NGN payouts, including bank codes required by the `/api/send/payout` endpoint.

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

> **Note:** `bank_code` from this response is required as input to `POST /api/send/payout` for Nigerian recipients.

---

### Send / Remittance

#### `POST /api/send/payout`

Initiates a crypto-to-fiat remittance. The user must sign a message with their wallet before calling this endpoint — the `signature` field proves authorization without an on-chain transaction at this step.

**Request Body**

```json
{
  "wallet": "0x7B77...",
  "amount_usdc": 10,
  "token": "USDC",
  "country_code": "NG",
  "currency": "NGN",
  "recipient_name": "John Doe",
  "account_number": "0123456789",
  "bank_name": "GTBank",
  "bank_code": "058",
  "signature": "0x...",
  "approve_tx": "0x...",
  "method": "bank"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wallet` | string | ✅ | Sender's EVM wallet address |
| `amount_usdc` | float | ✅ | Amount to send in USDC (min: 1.0) |
| `token` | string | ✅ | `"USDC"` or `"EURC"` |
| `country_code` | string | ✅ | ISO 3166-1 alpha-2 (e.g. `"NG"`) |
| `currency` | string | ✅ | Target fiat currency (e.g. `"NGN"`) |
| `recipient_name` | string | ✅ | Full name of recipient |
| `account_number` | string | ✅ | Bank account number or mobile wallet ID |
| `bank_name` | string | ✅ | Human-readable bank name |
| `bank_code` | string | ✅ | Bank code from `/api/banks` |
| `signature` | string | ✅ | EIP-191 signed message from sender wallet |
| `approve_tx` | string | ✅ | On-chain `approve()` transaction hash |
| `method` | string | ✅ | `"bank"` or `"mobile_money"` |

**Response `200 OK`**
```json
{
  "status": "mock_success",
  "reference": "KUDI-NGN-ABCD1234",
  "currency": "NGN",
  "payout_amount": 13795.2,
  "fee_usdc": 0.03,
  "rate_used": 1382.5,
  "message": "[SANDBOX] ₦13,795 would be sent to John Doe",
  "partner_reference": "BNB-TX-9988776655",
  "estimated_arrival": "1-2 business days"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `mock_success` (testnet) / `success` / `pending` / `failed` |
| `reference` | string | Kudi Arc internal reference ID — save this |
| `payout_amount` | float | Amount recipient will receive in local currency |
| `fee_usdc` | float | Protocol fee deducted (0.30% of `amount_usdc`) |
| `rate_used` | float | FX rate applied at time of transaction |
| `partner_reference` | string | Payout partner's own reference ID |
| `estimated_arrival` | string | Expected delivery time for the payout |

**Error Responses**

```json
{ "error": "invalid_signature",   "message": "Wallet signature could not be verified", "code": 422 }
{ "error": "country_unavailable", "message": "NGN corridor temporarily unavailable",    "code": 503 }
{ "error": "amount_too_low",      "message": "Minimum send amount is 1 USDC",           "code": 400 }
{ "error": "invalid_bank_code",   "message": "Bank code 999 not found",                 "code": 400 }
```

**cURL Example**
```bash
curl -X POST https://kudiarc.xyz/api/send/payout \
  -H "Content-Type: application/json" \
  -d '{
    "wallet": "0x7B77...",
    "amount_usdc": 10,
    "token": "USDC",
    "country_code": "NG",
    "currency": "NGN",
    "recipient_name": "John Doe",
    "account_number": "0123456789",
    "bank_name": "GTBank",
    "bank_code": "058",
    "signature": "0x...",
    "approve_tx": "0x...",
    "method": "bank"
  }'
```

---

### Swap Recording

#### `POST /api/swap/record`

Records a completed on-chain swap event to the Kudi Arc database. Called automatically by the frontend after a successful swap transaction.

**Request Body**

```json
{
  "wallet": "0x7B77...",
  "tx_hash": "0xecc2...",
  "from_token": "USDC",
  "to_token": "EURC",
  "amount_in": 10.0,
  "amount_out": 8.638,
  "rate": 0.8638
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wallet` | string | ✅ | Wallet that executed the swap |
| `tx_hash` | string | ✅ | On-chain transaction hash |
| `from_token` | string | ✅ | Input token: `"USDC"` or `"EURC"` |
| `to_token` | string | ✅ | Output token: `"USDC"` or `"EURC"` |
| `amount_in` | float | ✅ | Amount of input token |
| `amount_out` | float | ✅ | Amount of output token received |
| `rate` | float | ✅ | Rate used for this swap |

**Response `200 OK`**
```json
{
  "status": "recorded",
  "id": 42
}
```

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
  "wallet": "0x7B77...",
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
      "explorer_url": "https://testnet.arcscan.app/tx/0xecc2...",
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
curl "http://129.80.199.123/api/history/0x7B77...?type=swap&limit=10"
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

> ⚠️ USYC deposits are pending Circle allowlist approval. APY is live data; deposits are not yet active.

---

#### `GET /api/yield/balance/:wallet`

Returns a user's USYC position and accrued earnings.

**Response `200 OK`**
```json
{
  "wallet": "0x7B77...",
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

Returns service health status for all components. Useful for monitoring and uptime checks.

**Response `200 OK` — All systems operational**
```json
{
  "status": "ok",
  "timestamp": 1774663084,
  "components": {
    "api": "ok",
    "database": "ok",
    "fx_oracle": "ok",
    "bitnob": "ok",
    "flutterwave": "ok",
    "wave": "ok",
    "arc_rpc": "ok"
  },
  "version": "1.0.0"
}
```

**Response `503 Service Unavailable` — Degraded**
```json
{
  "status": "degraded",
  "timestamp": 1774663084,
  "components": {
    "api": "ok",
    "database": "ok",
    "fx_oracle": "ok",
    "bitnob": "unavailable",
    "flutterwave": "ok",
    "wave": "ok",
    "arc_rpc": "ok"
  },
  "version": "1.0.0"
}
```

When a component shows `"unavailable"`, the corresponding country routes are automatically disabled in `/api/countries` (`"available": false`).

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

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | March 2026 | Initial testnet release — rates, countries, banks, send, history, yield, health |

---

*For integration support, open an issue at [github.com/KudiArc/kudi-arc](https://github.com/KudiArc/kudi-arc) or join [discord.gg/kudiarc](https://discord.gg/nEJfqrAsqc).*
