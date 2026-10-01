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
| RPC URL | `https://rpc.testnet.arc.network` |
| Chain ID | `5042002` |
| Currency Symbol | USDC |
| Block Explorer | `https://testnet.arcscan.app` |

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
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
nano .env
```

### Environment Variables (`.env`)

```bash
# ── Wallet ──────────────────────────────────────────────────────
DEPLOYER_PRIVATE_KEY=0x_your_private_key_here
DEPLOYER_ADDRESS=0x_your_wallet_address

# ── Arc Network ──────────────────────────────────────────────────
ARC_RPC_URL=https://rpc.testnet.arc.network
ARC_CHAIN_ID=5042002

# ── Deployed Contract Addresses ──────────────────────────────────
KUDISWAP_ADDRESS=0x8a10D0e61201000B5456EC725165892B08832C5f
USDC_ADDRESS=0x3600000000000000000000000000000000000000
EURC_ADDRESS=0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a
USYC_ADDRESS=0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C

# ── Payout Partners ──────────────────────────────────────────────
BITNOB_API_KEY=your_bitnob_api_key
BITNOB_BASE_URL=https://api.bitnob.co/api/v1

FLUTTERWAVE_SECRET_KEY=FLWSECK-your_key
FLUTTERWAVE_BASE_URL=https://api.flutterwave.com/v3

WAVE_API_KEY=your_wave_api_key
WAVE_BASE_URL=https://api.wave.com/v1

# ── FX Oracle ────────────────────────────────────────────────────
OXR_APP_ID=your_open_exchange_rates_app_id

# ── App Config ───────────────────────────────────────────────────
FLASK_ENV=production
SECRET_KEY=generate_a_long_random_string_here
DB_PATH=/var/lib/kudi-arc/kudi.db
PORT=5000
```

> ⚠️ **Never commit `.env` to git.** It is already in `.gitignore`.

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

### Compile Contract

```bash
# Using Foundry
forge build contracts/KudiSwapV2.sol

# Or using the Python deploy script
python3 deploy.py --compile-only
```

### Deploy

```bash
# Deploy KudiSwap V2
python3 deploy.py

# Or with Foundry
forge create contracts/KudiSwapV2.sol:KudiSwapV2 \
  --rpc-url $ARC_RPC_URL \
  --private-key $DEPLOYER_PRIVATE_KEY \
  --constructor-args $USDC_ADDRESS $EURC_ADDRESS
```

Note the deployed address and update `KUDISWAP_ADDRESS` in `.env`.

### Verify on Arcscan

```bash
forge verify-contract \
  --rpc-url $ARC_RPC_URL \
  --etherscan-api-key dummy \
  --verifier blockscout \
  --verifier-url https://testnet.arcscan.app/api \
  $KUDISWAP_ADDRESS \
  contracts/KudiSwapV2.sol:KudiSwapV2
```

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
w3 = Web3(Web3.HTTPProvider(os.environ['ARC_RPC_URL']))
# ... (see add_liquidity.py for full implementation)
print('Pool seeded')
"
```

---

## 4. Backend Deployment

### Run Locally (Development)

```bash
source venv/bin/activate
python3 app.py
# API available at http://localhost:5000
```

### Production (Gunicorn + systemd)

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
Environment="PATH=/home/ubuntu/kudi-arc/venv/bin"
ExecStart=/home/ubuntu/kudi-arc/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile /var/log/kudi-arc/access.log \
    --error-logfile /var/log/kudi-arc/error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/kudi-arc
sudo chown ubuntu:ubuntu /var/log/kudi-arc

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
    root /home/ubuntu/kudi-arc;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Proxy API requests to Flask
    location /api/ {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

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
sudo certbot --nginx -d kudiarc.app -d api.kudiarc.app

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
BASE="http://129.80.199.123"  # Replace with your server IP or domain

# Health check
curl -s $BASE/api/health | python3 -m json.tool

# FX rates
curl -s $BASE/api/rates | python3 -m json.tool

# Countries
curl -s $BASE/api/countries | python3 -m json.tool

# Banks
curl -s $BASE/api/banks | python3 -m json.tool

# Yield stats
curl -s $BASE/api/yield/stats | python3 -m json.tool

# History (replace with a real wallet that has testnet activity)
curl -s "$BASE/api/history/0x7B77..." | python3 -m json.tool
```

Expected: all return `200 OK` with valid JSON, and `/api/health` shows all components as `"ok"`.

---

## 9. Updating the Deployment

```bash
cd /home/ubuntu/kudi-arc

# Pull latest changes
git pull origin main

# Install any new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart backend
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
| `Connection refused` on API | Gunicorn not bound to correct port | Check `PORT=5000` in `.env` |
| `Rate fetch failed` | Invalid OXR App ID | Verify `OXR_APP_ID` in `.env` |
| Swap preview returns 0 | Pool is empty | Run `python3 add_liquidity.py` |
| Send returns `partner_unavailable` | Bitnob/Flutterwave API key invalid | Check partner API keys in `.env` |
| DB errors | SQLite path wrong | Verify `DB_PATH` in `.env` and permissions |
| `gas estimation failed` | Insufficient USDC approval | User must approve KudiSwap before swap |

---

*For architecture details, see [ARCHITECTURE.md](./ARCHITECTURE.md).*  
*For security details, see [SECURITY.md](./SECURITY.md).*
