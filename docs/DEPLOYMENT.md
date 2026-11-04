# Kudi Arc — Deployment Guide

This guide covers deploying the full Kudi Arc stack: smart contracts, Flask backend, and static frontend. Follow sections in order for a fresh deployment.

---

## Prerequisites

### Wallets & Accounts

- MetaMask or Rabby with Arc Testnet configured
- Testnet USDC from [faucet.circle.com](https://faucet.circle.com) (for liquidity seeding)
- [Pinata](https://app.pinata.cloud) account (optional, for IPFS metadata)

### Arc Testnet Config

Add Arc Testnet to your wallet:

| Field | Value |
|-------|-------|
| Network Name | Arc Testnet |
| RPC URL | `https://rpc.testnet.arc.io` |
| Chain ID | `5042002` |
| Currency Symbol | USDC |
| Block Explorer | `https://explorer.testnet.arc.io` |

For mainnet set `NETWORK=mainnet` (chain ID 5042) in `.env`; the backend and the send/admin pages then take the RPC, explorer and chain ID from that setting.

### Software Requirements

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | `sudo apt install python3.10` |
| pip | Latest | `sudo apt install python3-pip` |
| Node.js | 18+ | `sudo apt install nodejs` |
| Foundry | Latest | `curl -L https://foundry.paradigm.xyz \| bash && foundryup` |
| Nginx | Latest | `sudo apt install nginx` |

---

## 1. Clone & Configure

```bash
git clone https://github.com/KudiArc/kudi-arc.git
cd kudi-arc

# Create Python virtual environment
python3 -m venv kudi-env
source kudi-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
nano .env
```

### Environment Variables (`.env`)

```bash
# ── Network ──────────────────────────────────────────────────────
NETWORK=testnet                 # testnet | mainnet (sets RPC, chain ID, explorer, tokens)
# ARC_RPC, CHAIN_ID, EXPLORER_URL, USDC_ADDRESS, EURC_ADDRESS override the preset

# ── Admin (REQUIRED) ─────────────────────────────────────────────
OWNER_ADDRESS=0xYourOwnerWalletAddress   # admin stays disabled if unset
PUBLIC_DOMAIN=kudiarc.xyz

# ── Contracts ────────────────────────────────────────────────────
KUDI_CONTRACT_ADDRESS=0x8a10D0e61201000B5456EC725165892B08832C5f   # KudiSwap V2
ESCROW_ADDRESS=0xYourDeployedKudiSendEscrow

# ── KudiSend ─────────────────────────────────────────────────────
SEND_MODE=mock                  # "live" enables real payouts; anything else = sandbox
QUOTE_TTL_SECONDS=600
SEND_MIN_USD=10
SEND_MAX_USD=50

# ── Payout Partners (used only when SEND_MODE=live) ──────────────
FLUTTERWAVE_SECRET_KEY=mock
BITNOB_SECRET_KEY=mock
BITNOB_BASE_URL=https://sandboxapi.bitnob.co/api/v1
PAYSTACK_SECRET_KEY=mock

# ── Webhook secrets (webhooks are rejected if unset) ─────────────
FLW_WEBHOOK_SECRET=
BITNOB_WEBHOOK_SECRET=

# ── Server ───────────────────────────────────────────────────────
PORT=5001
DB_PATH=/absolute/path/to/kudi.db   # optional: defaults to kudi.db next to db.py
```

> ⚠️ **Never commit `.env` to git.** It is already in `.gitignore`.
>
> ⚠️ **Never put a private key in the server's `.env`.** The backend does not need one: deposits are verified by reading the chain, and the owner signs settle/refund from their own wallet. Keys are only used on your own machine for the one-off contract deployment (typed at a prompt).

---

## 2. Database Initialisation

```bash
# Create database directory
sudo mkdir -p /var/lib/kudi-arc
sudo chown $USER:$USER /var/lib/kudi-arc

# Initialise schema
python3 db.py

# Verify
sqlite3 /var/lib/kudi-arc/kudi.db ".tables"
# Expected output: sends  transactions
```

---

## 3. Smart Contract Deployment

> **Skip this section** if you are using the existing verified deployment at `0x8a10D0e61201000B5456EC725165892B08832C5f`.

### Compile and Test

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup
forge install foundry-rs/forge-std      # test library (kept out of git)
forge build
forge test                              # 22 escrow tests
```

### Deploy KudiSwap V2

```bash
forge create src/KudiSwapV2.sol:KudiSwapV2 \
  --rpc-url https://rpc.testnet.arc.io \
  --interactive --broadcast \
  --constructor-args $USDC_ADDRESS $EURC_ADDRESS
```

`--interactive` asks for the deployer key as hidden input, so it never lands in your shell history. Note the deployed address and set `KUDI_CONTRACT_ADDRESS` in `.env`.

### Deploy KudiSendEscrow

The deployer only pays gas. `ESCROW_OWNER` is the wallet that will control the escrow (settle, refund, pause) and should be a different wallet from the deployer.

```bash
export ESCROW_OWNER=0xYourOwnerWallet
export ESCROW_TREASURY=0xWhereSettledFundsGo

forge script script/DeployEscrow.s.sol:DeployEscrow \
  --rpc-url https://rpc.testnet.arc.io \
  --broadcast --interactive \
  --verify --verifier blockscout \
  --verifier-url https://explorer.testnet.arc.io/api/
```

Defaults: Arc Testnet USDC and EURC, minimum 10 and maximum 50 per deposit (`ESCROW_MIN` / `ESCROW_MAX` in token base units, `ESCROW_USDC` / `ESCROW_EURC` to override the tokens). The script prints `KudiSendEscrow: 0x…`. Set that as `ESCROW_ADDRESS` in `.env`, then check it:

```bash
cast call $ESCROW_ADDRESS "owner()(address)" --rpc-url https://rpc.testnet.arc.io
cast call $ESCROW_ADDRESS "tokenCount()(uint256)" --rpc-url https://rpc.testnet.arc.io   # expect 2
```

If automatic verification fails the deploy has still succeeded. Verify separately:

```bash
forge verify-contract $ESCROW_ADDRESS src/KudiSendEscrow.sol:KudiSendEscrow \
  --rpc-url https://rpc.testnet.arc.io --verifier blockscout \
  --verifier-url https://explorer.testnet.arc.io/api/ --watch \
  --constructor-args $(cast abi-encode "constructor(address,address,uint256,uint256,address[])" \
    $ESCROW_OWNER $ESCROW_TREASURY 10000000 50000000 "[$USDC_ADDRESS,$EURC_ADDRESS]")
```

The `broadcast/` folder Foundry creates is in `.gitignore`. Do not commit it.

### Seed Initial Liquidity

The contract needs USDC and EURC deposited before swaps work:

```bash
# Approve and deposit liquidity
python3 add_liquidity.py --usdc 500 --eurc 400

# Check pool balances
python3 -c "
from web3 import Web3
import json, os
from dotenv import load_dotenv
load_dotenv()
w3 = Web3(Web3.HTTPProvider(os.environ['ARC_RPC']))
# ... (see add_liquidity.py for full implementation)
print('Pool seeded')
"
```

---

## 4. Backend Deployment

### Run Locally (Development)

```bash
source kudi-env/bin/activate
python3 app.py
# API available at http://localhost:5001
```

### Production (Gunicorn + systemd)

Gunicorn listens on localhost only; nginx (below) is the public entry point.

```bash
# Create systemd service
sudo tee /etc/systemd/system/kudi-arc.service > /dev/null <<EOF
[Unit]
Description=Kudi Arc Flask Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kudi-arc
Environment="PATH=/home/ubuntu/kudi-arc/kudi-env/bin"
ExecStart=/home/ubuntu/kudi-arc/kudi-env/bin/gunicorn -w 2 -b 127.0.0.1:5001 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable kudi-arc
sudo systemctl start kudi-arc

# Check status
sudo systemctl status kudi-arc
```

---

## 5. Nginx Configuration

```bash
# Create Nginx config
sudo tee /etc/nginx/sites-available/kudi-arc > /dev/null <<EOF
server {
    listen 80;
    server_name _;  # Replace with your domain on mainnet

    # Static frontend files
    # ONLY the public/ folder is a web root. Never point root at the project
    # folder: it holds .env, kudi.db, .git and the backend source.
    root /home/ubuntu/kudi-arc/public;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Proxy API requests to Flask
    location /api/ {
        proxy_pass         http://127.0.0.1:5001;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # Defence in depth: never serve dotfiles or data/source files
    location ~ /\\. { deny all; return 404; }
    location ~* \\.(env|db|sqlite|json|py|sh|log|md|toml|ini)\$ { deny all; return 404; }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/kudi-arc /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 6. SSL (Mainnet / Custom Domain)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate (replace with your domain)
sudo certbot --nginx -d kudiarc.xyz

# Auto-renewal is set up by Certbot automatically
# Verify: sudo certbot renew --dry-run
```

---

## 7. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'   # Ports 80 and 443
sudo ufw enable
sudo ufw status
```

---

## 8. Smoke Tests

Run these after deployment to verify everything is working:

```bash
BASE="https://kudiarc.xyz"  # or http://your-server-ip

# Health check
curl -s $BASE/api/health | python3 -m json.tool

# FX rates
curl -s $BASE/api/rates | python3 -m json.tool

# Countries
curl -s $BASE/api/countries | python3 -m json.tool

# Banks
curl -s $BASE/api/banks | python3 -m json.tool

# Send settings (escrow address, network, limits)
curl -s $BASE/api/send/config | python3 -m json.tool

# Admin login is disabled-by-default: this should return a nonce, not a 503
curl -s $BASE/api/admin/challenge | python3 -m json.tool

# Yield stats
curl -s $BASE/api/yield/stats | python3 -m json.tool

# History (replace with a real wallet that has testnet activity)
curl -s "$BASE/api/history/0xYourWallet" | python3 -m json.tool
```

Expected: all return `200 OK` with valid JSON, and `/api/health` shows all components as `"ok"`.

---

## Owner Operations (Settle & Refund)

Deposits sit in the escrow until the owner settles or refunds them. Open **admin.html**, connect the owner wallet (`OWNER_ADDRESS`) and use **Send Orders**:

| List | What to do |
|------|-----------|
| Ready to settle | Payout confirmed. **Settle** sends the funds to the treasury (up to 100 per transaction) |
| Needs refund | Payout failed or the deposit arrived late. **Refund** returns the deposit to the sender |
| Needs your decision | Partner result unclear. Check the partner dashboard, then record **Was paid** or **Not paid** |
| Waiting for provider | Partner accepted the payout; the final result arrives by webhook |

**Sync chain** copies settle/refund results into the database. **Find missed deposits** processes deposits that were made but never confirmed (for example a sender who closed the page). Aim to settle or refund every order within 24 to 48 hours. A sender can always reclaim an untouched deposit after 72 hours.

Every admin action is signed by the owner wallet. The server never holds a key.

## Going Live with Real Payouts

Keep `SEND_MODE` unset (sandbox) until all of these are done:

1. `OWNER_ADDRESS`, `ESCROW_ADDRESS` and the partner keys are set, and the partner keys are **live** keys.
2. `FLW_WEBHOOK_SECRET` (and `BITNOB_WEBHOOK_SECRET` if you use Bitnob) are set, and the same values are configured in each partner's dashboard.
3. Webhook URLs are registered with each partner: `/api/send/flw-webhook`, `/api/send/paystack-webhook`, `/api/send/webhook`.
4. A small end-to-end transfer has been tested in the partner's sandbox.
5. Then set `SEND_MODE=live` and restart.

> Bitnob's webhook signature scheme and status lookup are not confirmed against its official docs. Test Bitnob in its sandbox before relying on it.

## 9. Updating the Deployment

```bash
cd /home/ubuntu/kudi-arc

# Pull latest changes
git pull origin main

# Install any new dependencies
source kudi-env/bin/activate
pip install -r requirements.txt

# Run the tests first
pip install -r requirements-dev.txt && python3 -m pytest

# Restart the backend (a full restart is required to load new code)
sudo systemctl restart kudi-arc

# Check logs for errors
sudo journalctl -u kudi-arc -n 50 --no-pager
```

---

## 10. Monitoring

```bash
# View live backend logs
sudo journalctl -u kudi-arc -f

# View Nginx access logs
sudo tail -f /var/log/kudi-arc/access.log

# View Nginx error logs
sudo tail -f /var/log/kudi-arc/error.log

# Check service status
sudo systemctl status kudi-arc nginx
```

### Uptime Monitoring

For external uptime monitoring, configure a ping to `GET /api/health` from:
- [UptimeRobot](https://uptimerobot.com) (free tier)
- [Better Uptime](https://betteruptime.com)

Alert threshold: any non-`200` response from `/api/health`.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `502 Bad Gateway` | Flask not running | `sudo systemctl restart kudi-arc` |
| `Connection refused` on API | Gunicorn port differs from nginx | The `-b` address in the service file (`127.0.0.1:5001`) must match nginx's `proxy_pass` |
| `Rate fetch failed` | Invalid OXR App ID | Verify `OXR_APP_ID` in `.env` |
| Swap preview returns 0 | Pool is empty | Run `python3 add_liquidity.py` |
| Send returns `partner_unavailable` | Bitnob/Flutterwave API key invalid | Check partner API keys in `.env` |
| DB errors | SQLite path wrong | Verify `DB_PATH` in `.env` and permissions |
| `gas estimation failed` | Insufficient USDC approval | User must approve KudiSwap before swap |

---

*For architecture details, see [ARCHITECTURE.md](./ARCHITECTURE.md).*  
*For security details, see [SECURITY.md](./SECURITY.md).*

### Admin dashboard says "Admin is not configured"
`OWNER_ADDRESS` is missing from `.env`. Set it to the owner wallet and restart.

### Send shows "Sending is not available yet"
`ESCROW_ADDRESS` is missing or invalid. In live mode at least one real partner key must also be set.

### Webhooks return 503
The matching webhook secret (`FLW_WEBHOOK_SECRET`, `BITNOB_WEBHOOK_SECRET`) or partner key is not set. Webhooks are intentionally rejected until configured.

### "Chain mismatch" or "Chain lookup failed" on send
The server's `NETWORK` / `CHAIN_ID` / `ARC_RPC` does not match the chain the user's wallet is on, or the RPC is unreachable.

### An extra gunicorn is listening on port 5000
`start.sh` / `gunicorn.conf.py` are only a quick manual alternative. They bind **all interfaces** on port 5000, bypassing nginx and TLS. Do not run them alongside the systemd service, and keep port 5000 closed in your firewall. Stop a stray one with `pkill -f "gunicorn -c gunicorn.conf.py"`.
