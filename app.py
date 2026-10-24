import os, time, logging, requests, uuid, json as _json, threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from web3 import Web3
from eth_account.messages import encode_defunct
from dotenv import load_dotenv
from decimal import Decimal
from db import init_db, save_swap, save_send, get_history, update_send_status, get_db, SharedState
import kudisend
import webhooks
import swapverify
from adminauth import AdminAuth

load_dotenv()

_NET          = kudisend.load_config()          # NETWORK=testnet|mainnet
ARC_RPC       = _NET["rpc"]
CONTRACT_ADDR = os.getenv("KUDI_CONTRACT_ADDRESS", "")
CHAIN_ID      = _NET["chain_id"]
BITNOB_KEY    = os.getenv("BITNOB_SECRET_KEY", "mock")
BITNOB_BASE   = os.getenv("BITNOB_BASE_URL", "https://sandboxapi.bitnob.co/api/v1")
FLW_SECRET    = os.getenv("FLUTTERWAVE_SECRET_KEY", "mock").strip()
if FLW_SECRET.lower().startswith("bearer "): FLW_SECRET = FLW_SECRET[7:].strip()
FLW_BASE      = "https://api.flutterwave.com/v3"
PSK_SECRET    = os.getenv("PAYSTACK_SECRET_KEY", "mock")
PSK_BASE      = "https://api.paystack.co"
PORT = int(os.getenv("PORT", "5001"))
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS", "").strip()      # required for admin; no default

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kudi-arc")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024      # reject oversized request bodies

ALLOWED_ORIGINS = [
    "https://kudiarc.xyz",
    "https://www.kudiarc.xyz",
    "https://admin.kudiarc.xyz",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
    "http://129.80.199.123",
    "http://129.80.199.123:5000",
]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

w3 = Web3(Web3.HTTPProvider(ARC_RPC))
init_db()

_ADMIN_DEFAULTS = {"maintenance": False, "message": "KudiArc is under maintenance. We'll be back shortly.",
                   "send_fee_pct": 0.3, "min_send_usd": 5.0}
admin_state = SharedState("admin", _ADMIN_DEFAULTS)     # stored in the DB, shared by all workers
try:                                                    # one-time import of the old JSON file
    with open("admin_state.json") as _f: admin_state.seed(_json.load(_f))
except Exception: pass
admin_auth = AdminAuth(OWNER_ADDRESS, CHAIN_ID,
                       os.getenv("PUBLIC_DOMAIN", "kudiarc.xyz"))
START_TIME = time.time()

rate_cache = {
    "usd_eur":0.8638,"eur_usd":1.1576,
    "ngn_per_usd":1377.0,"ngn_per_eur":1594.0,
    "last_updated":0,"multi":{},"multi_updated":0
}

KUDI_ABI = [
    {"inputs":[{"type":"uint256","name":"_usdcToEurc"},{"type":"uint256","name":"_eurcToUsdc"}],"name":"queueRateUpdate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"applyRateUpdate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"cancelRateUpdate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"pendingRate","outputs":[{"type":"uint256","name":"usdcToEurc"},{"type":"uint256","name":"eurcToUsdc"},{"type":"uint256","name":"effectiveAt"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getPoolBalances","outputs":[{"type":"uint256","name":"usdcBalance"},{"type":"uint256","name":"eurcBalance"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSwaps","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"paused","outputs":[{"type":"bool","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[{"type":"bool","name":"_paused"}],"name":"setPaused","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"type":"uint256","name":"_feeBps"}],"name":"updateFee","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"owner","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"}
]

NIGERIAN_BANKS = [
    {"code":"044","name":"Access Bank"},{"code":"023","name":"Citibank"},
    {"code":"050","name":"EcoBank"},{"code":"070","name":"Fidelity Bank"},
    {"code":"011","name":"First Bank"},{"code":"214","name":"First City Monument Bank"},
    {"code":"058","name":"GTBank"},{"code":"030","name":"Heritage Bank"},
    {"code":"301","name":"Jaiz Bank"},{"code":"082","name":"Keystone Bank"},
    {"code":"526","name":"Opay"},{"code":"076","name":"Polaris Bank"},
    {"code":"101","name":"Providus Bank"},{"code":"221","name":"Stanbic IBTC"},
    {"code":"068","name":"Standard Chartered"},{"code":"232","name":"Sterling Bank"},
    {"code":"100","name":"Suntrust Bank"},{"code":"032","name":"Union Bank"},
    {"code":"033","name":"UBA"},{"code":"215","name":"Unity Bank"},
    {"code":"035","name":"Wema Bank"},{"code":"057","name":"Zenith Bank"},
    {"code":"327","name":"Palmpay"},{"code":"090115","name":"Kuda Bank"},
    {"code":"565","name":"Carbon"},{"code":"50515","name":"Moniepoint"},
]

PAYOUT_COUNTRIES = [
    {"code":"NG","name":"Nigeria",       "currency":"NGN","symbol":"₦",   "flag":"🇳🇬","partner":"Flutterwave"},
    {"code":"KE","name":"Kenya",         "currency":"KES","symbol":"KSh", "flag":"🇰🇪","partner":"Flutterwave"},
    {"code":"GH","name":"Ghana",         "currency":"GHS","symbol":"GH₵", "flag":"🇬🇭","partner":"Flutterwave"},
    {"code":"ZA","name":"South Africa",  "currency":"ZAR","symbol":"R",   "flag":"🇿🇦","partner":"Flutterwave"},
    {"code":"SN","name":"Senegal",       "currency":"XOF","symbol":"CFA", "flag":"🇸🇳","partner":"Flutterwave"},
    {"code":"CI","name":"Côte d'Ivoire", "currency":"XOF","symbol":"CFA", "flag":"🇨🇮","partner":"Flutterwave"},
    {"code":"CM","name":"Cameroon",      "currency":"XAF","symbol":"FCFA","flag":"🇨🇲","partner":"Flutterwave"},
    {"code":"TZ","name":"Tanzania",      "currency":"TZS","symbol":"TSh", "flag":"🇹🇿","partner":"Flutterwave"},
    {"code":"UG","name":"Uganda",        "currency":"UGX","symbol":"USh", "flag":"🇺🇬","partner":"Flutterwave"},
    {"code":"RW","name":"Rwanda",        "currency":"RWF","symbol":"RF",  "flag":"🇷🇼","partner":"Flutterwave"},
]

SEND_FEES = {
    "NG":0.008,"KE":0.035,"GH":0.028,"ZA":0.035,
    "SN":0.030,"CI":0.030,"CM":0.020,"TZ":0.035,
    "UG":0.040,"RW":0.045,
}

BITNOB_COUNTRIES   = {"NG","GH","KE"}
PAYSTACK_COUNTRIES = {"NG","GH","KE","ZA"}

KUDI_YIELD_ADDR = "0x146F0CD9afbc4effa3EdFc9D1a666bf5AA0d7AD8"
KUDI_YIELD_ABI  = [
    {"inputs":[{"name":"usdcAmount","type":"uint256"}],"name":"deposit","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"usycAmount","type":"uint256"}],"name":"withdraw","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"user","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalUsyc","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]
USYC_ADDR = "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C"
USYC_ABI  = [
    {"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

def fetch_fx_rates():
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        data = resp.json()
        if data.get("result") == "success":
            rates = data["rates"]
            eur   = rates.get("EUR", 0.8638)
            ngn   = rates.get("NGN", 1377.0)
            multi = {}
            for country in PAYOUT_COUNTRIES:
                cur = country["currency"]
                multi[cur] = round(rates.get(cur, 0), 4)
            rate_cache.update({
                "usd_eur":round(eur,6),"eur_usd":round(1/eur,6),
                "ngn_per_usd":round(ngn,2),"ngn_per_eur":round(ngn/eur,2),
                "last_updated":int(time.time()),"multi":multi,"multi_updated":int(time.time())
            })
            log.info(f"Rates updated: 1 USD = {eur:.4f} EUR | {ngn:.0f} NGN")
    except Exception as e:
        log.warning(f"Rate fetch failed: {e}")


def get_usyc_price():
    try:
        TELLER_ADDR = "0x9fdF14c5B14173D74C08Af27AebFf39240dC105A"
        TELLER_ABI  = [
            {"name":"previewRedeem","type":"function","inputs":[{"name":"shares","type":"uint256"}],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
            {"name":"convertToAssets","type":"function","inputs":[{"name":"shares","type":"uint256"}],"outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"}
        ]
        teller = w3.eth.contract(address=Web3.to_checksum_address(TELLER_ADDR), abi=TELLER_ABI)
        try:    assets = teller.functions.previewRedeem(1_000_000).call()
        except: assets = teller.functions.convertToAssets(1_000_000).call()
        price = assets / 1_000_000
        return round(price, 6) if price > 0 else 1.117
    except Exception as e:
        log.warning(f"get_usyc_price failed: {e}")
        return 1.117

def get_rates_fresh():
    if time.time() - rate_cache["last_updated"] > 300:
        fetch_fx_rates()
    return rate_cache

def get_multi_rates_fresh():
    if time.time() - rate_cache.get("multi_updated",0) > 300:
        fetch_fx_rates()
    if rate_cache.get("multi"):
        return rate_cache["multi"]
    return {"NGN":1382.0,"KES":129.5,"GHS":15.2,"ZAR":18.6,"XOF":614.0,"XAF":614.0,"TZS":2580.0,"UGX":3720.0,"RWF":1370.0}


app.register_blueprint(kudisend.create_blueprint(
    w3=w3,
    get_rates=get_rates_fresh,
    get_multi_rates=get_multi_rates_fresh,
    countries=PAYOUT_COUNTRIES,
    fees=SEND_FEES,
    is_maintenance=lambda: bool(admin_state.get("maintenance")),
    admin_min_usd=lambda: Decimal(str(admin_state.get("min_send_usd", 0))),
    admin_fee_floor_pct=lambda: admin_state.get("send_fee_pct", 0),
    provider_keys={"flutterwave": FLW_SECRET, "bitnob": BITNOB_KEY,
                   "bitnob_base": BITNOB_BASE, "paystack": PSK_SECRET},
    admin_required=admin_auth.required,
    cfg=_NET,
))

@app.route("/api/health")
def health():
    r = rate_cache
    components = {
        "api":"ok",
        "fx_oracle":"ok" if r["last_updated"] > 0 else "stale",
        "arc_rpc":"ok" if w3.is_connected() else "unavailable",
        "bitnob":"mock" if BITNOB_KEY=="mock" else "ok",
    }
    status = "ok" if all(v in ("ok","mock") for v in components.values()) else "degraded"
    return jsonify({"status":status,"chain":_NET["network_name"],"chain_id":CHAIN_ID,"components":components,"version":"2.0.0"})

@app.route("/api/rates")
def get_rates():
    r = get_rates_fresh()
    return jsonify({
        "pairs":{
            "USDC/EURC":{"rate":r["usd_eur"],"display":f"1 USDC = {r['usd_eur']:.4f} EURC"},
            "EURC/USDC":{"rate":r["eur_usd"],"display":f"1 EURC = {r['eur_usd']:.4f} USDC"},
            "USDC/NGN": {"rate":r["ngn_per_usd"],"display":f"1 USDC ≈ ₦{r['ngn_per_usd']:,.0f}"},
            "EURC/NGN": {"rate":r["ngn_per_eur"],"display":f"1 EURC ≈ ₦{r['ngn_per_eur']:,.0f}"}
        },
        "last_updated":r["last_updated"],
        "contract":CONTRACT_ADDR or "not deployed"
    })

@app.route("/api/banks")
def get_banks():
    return jsonify({"banks":NIGERIAN_BANKS})

@app.route("/api/countries")
def get_countries():
    rates  = get_multi_rates_fresh()
    r      = get_rates_fresh()
    result = []
    for country in PAYOUT_COUNTRIES:
        cur      = country["currency"]
        usd_rate = rates.get(cur,0)
        eur_rate = round(usd_rate*r["eur_usd"],4) if r["eur_usd"] else 0
        result.append({**country,"rate_per_usd":usd_rate,"rate_per_eurc":eur_rate,
            "fee_pct":round(max(SEND_FEES.get(country["code"],0.030)*100, float(admin_state.get("send_fee_pct",0) or 0)),2),
            "display_usd":f"1 USDC = {country['symbol']}{usd_rate:,.2f}",
            "display_eur":f"1 EURC = {country['symbol']}{eur_rate:,.2f}","available":True})
    return jsonify({"countries":result})

@app.route("/api/history/<wallet>")
def get_tx_history(wallet):
    if not wallet or not wallet.startswith("0x") or len(wallet) != 42:
        return jsonify({"error":"Invalid wallet format"}), 400
    tx_type = request.args.get("type","all")
    limit   = min(int(request.args.get("limit",50)),200)
    txs     = get_history(wallet,limit=limit,tx_type=tx_type)
    for tx in txs:
        if tx.get("recipient_account"):
            tx["recipient_account"] = "****" + str(tx["recipient_account"])[-4:]
        if tx.get("recipient_phone"):
            tx["recipient_phone"] = "****" + str(tx["recipient_phone"])[-4:]
    return jsonify({"wallet":wallet,"transactions":txs,"count":len(txs)})

app.register_blueprint(swapverify.create_blueprint(
    w3=w3, contract_addr=CONTRACT_ADDR, tokens=_NET["tokens"],
    get_rates=get_rates_fresh, get_multi_rates=get_multi_rates_fresh,
))

app.register_blueprint(webhooks.create_blueprint(
    keys={"flutterwave": FLW_SECRET, "bitnob": BITNOB_KEY, "paystack": PSK_SECRET},
    secrets={"flutterwave": os.getenv("FLW_WEBHOOK_SECRET", ""), "bitnob": os.getenv("BITNOB_WEBHOOK_SECRET", "")},
))

@app.route("/api/send/payout", methods=["POST"])
def send_payout():
    # Retired: payouts now require a verified escrow deposit (see kudisend.py).
    return jsonify({"error": "This version of the app is out of date. Please refresh the page.",
                    "code": "deprecated"}), 410

@app.route("/api/yield/stats")
def yield_stats():
    r = get_rates_fresh()
    try:
        usyc_price= get_usyc_price()
        usyc      = w3.eth.contract(address=Web3.to_checksum_address(USYC_ADDR),abi=USYC_ABI)
        total_supply = usyc.functions.totalSupply().call()
        # Use USYC balanceOf(KudiYield) for real TVL — totalUsyc() tracks internal deposits only
        protocol_tvl_raw = usyc.functions.balanceOf(Web3.to_checksum_address(KUDI_YIELD_ADDR)).call()
        protocol_tvl = protocol_tvl_raw / 1e6
        return jsonify({"apy":4.86,"apy_source":"US Treasury Bills (USYC)","min_deposit":1,
            "total_supply":total_supply/1e6,"protocol_tvl":round(protocol_tvl,4),
            "protocol_tvl_usd":round(protocol_tvl*usyc_price,2),"usdc_per_usyc":usyc_price,
            "ngn_per_usyc":round(usyc_price*r["ngn_per_usd"],2),"ngn_per_usd":r["ngn_per_usd"],
            "allowlist_required":False,"status":"live"})
    except Exception as e:
        log.warning(f"yield_stats failed: {e}")
        return jsonify({"apy":4.86,"apy_source":"US Treasury Bills (USYC)","min_deposit":1,"total_supply":0,
            "usdc_per_usyc":get_usyc_price(),"ngn_per_usyc":round(1.02*r["ngn_per_usd"],2),
            "ngn_per_usd":r["ngn_per_usd"],"allowlist_required":False,"status":"live"})

@app.route("/api/yield/balance/<wallet>")
def yield_balance(wallet):
    if not wallet or len(wallet) < 10:
        return jsonify({"error":"Invalid wallet"}), 400
    r = get_rates_fresh()
    try:
        kudiyield = w3.eth.contract(address=Web3.to_checksum_address(KUDI_YIELD_ADDR),abi=KUDI_YIELD_ABI)
        bal       = kudiyield.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
        usyc_bal  = bal/1e6
        usyc_price= get_usyc_price()
        usdc_val  = usyc_bal * usyc_price
        earnings  = round((usyc_price - 1.0) * usyc_bal, 6)
        return jsonify({"wallet":wallet,"usyc_balance":usyc_bal,"usdc_value":round(usdc_val,4),
            "ngn_value":round(usdc_val*r["ngn_per_usd"],2),"is_allowlisted":True,"earnings_usdc":earnings})
    except Exception as e:
        log.warning(f"yield_balance fetch failed: {e}")
        return jsonify({"wallet":wallet,"usyc_balance":0,"usdc_value":0,"ngn_value":0,"is_allowlisted":True,"earnings_usdc":0})

@app.route("/api/admin/challenge")
def admin_challenge():
    return admin_auth.challenge()

@app.route("/api/admin/status")
def admin_status():
    return jsonify({"maintenance":admin_state.get("maintenance",False),"message":admin_state.get("message","")})

@app.route("/api/admin/stats")
def admin_stats():
    uptime=int(time.time()-START_TIME)
    swap_count=send_count=unique_wallets=0
    total_swap_fees=total_send_fees=0.0
    try:
        _conn = get_db()
        swap_count      = _conn.execute("SELECT COUNT(*) FROM transactions WHERE tx_type='swap'").fetchone()[0]
        send_count      = _conn.execute("SELECT COUNT(*) FROM transactions WHERE tx_type='send'").fetchone()[0]
        unique_wallets  = _conn.execute("SELECT COUNT(DISTINCT wallet) FROM transactions").fetchone()[0]
        total_swap_fees = round(float(_conn.execute("SELECT COALESCE(SUM(fee),0) FROM transactions WHERE tx_type='swap'").fetchone()[0] or 0),6)
        total_send_fees = round(float(_conn.execute("SELECT COALESCE(SUM(fee),0) FROM transactions WHERE tx_type='send'").fetchone()[0] or 0),6)
        total_swap_volume = round(float(_conn.execute("SELECT COALESCE(SUM(amount_in),0) FROM transactions WHERE tx_type='swap'").fetchone()[0] or 0),2)
        _conn.close()
    except Exception as _e:
        log.warning(f"admin_stats DB query failed: {_e}")
        total_swap_volume=0
    total_tx=swap_count+send_count
    tps=round(total_tx/max(uptime,1),6)
    on_chain={}
    try:
        if CONTRACT_ADDR:
            contract=w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDR),abi=KUDI_ABI)
            u,e=contract.functions.getPoolBalances().call()
            ts=contract.functions.totalSwaps().call()
            p=contract.functions.paused().call()
            on_chain={"pool_usdc":round(u/1e6,4),"pool_eurc":round(e/1e6,4),"total_swaps":int(ts),"swap_paused":p}
    except Exception as e: log.warning(f"admin_stats contract: {e}")
    yield_usyc=0
    try:
        kudiyield=w3.eth.contract(address=Web3.to_checksum_address(KUDI_YIELD_ADDR),abi=KUDI_YIELD_ABI)
        yield_usyc=round(kudiyield.functions.totalUsyc().call()/1e6,4)
    except: pass
    r=rate_cache
    return jsonify({"uptime_sec":uptime,"unique_wallets":unique_wallets,"swap_count":swap_count,
        "send_count":send_count,"total_tx":total_tx,"tps":tps,"fx_last_updated":r["last_updated"],
        "rates":{"usd_eur":r["usd_eur"],"eur_usd":r["eur_usd"],"ngn_per_usd":r["ngn_per_usd"]},
        "on_chain":on_chain,"yield_usyc":yield_usyc,"total_swap_fees":total_swap_fees,
        "total_send_fees":total_send_fees,"total_fees":round(total_swap_fees+total_send_fees,6),
        "total_swap_volume":total_swap_volume,
        "maintenance":admin_state.get("maintenance",False),"send_fee_pct":admin_state.get("send_fee_pct",0.3),
        "min_send_usd":admin_state.get("min_send_usd",5.0)})

@app.route("/api/admin/recent-txs", methods=["POST"])
@admin_auth.required
def admin_recent_txs():
    try:
        conn=get_db()
        rows=conn.execute("""
            SELECT tx_type, wallet, from_token, to_token, amount_in, amount_out,
                   fee, rate, tx_hash, status, recipient_name, recipient_bank,
                   recipient_account, bitnob_ref, created_at
            FROM transactions ORDER BY created_at DESC LIMIT 50
        """).fetchall()
        conn.close()
        txs = []
        for r in rows:
            row = dict(r)
            row["country"] = row.get("recipient_bank","") or ""
            txs.append(row)
        return jsonify({"transactions": txs})
    except Exception as e:
        log.error(f"admin_recent_txs failed: {e}")
        return jsonify({"error":str(e)}), 500

@app.route("/api/admin/maintenance", methods=["POST"])
@admin_auth.required
def admin_maintenance():
    d = request.get_json(silent=True) or {}
    admin_state["maintenance"]=bool(d.get("maintenance",False))
    if "message" in d: admin_state["message"]=str(d["message"])[:300]
    log.info(f"Maintenance={admin_state['maintenance']}")
    return jsonify({"status":"ok","maintenance":admin_state["maintenance"]})

@app.route("/api/admin/refresh-rates", methods=["POST"])
@admin_auth.required
def admin_refresh_rates():
    fetch_fx_rates()
    return jsonify({"status":"ok","usd_eur":rate_cache["usd_eur"],"ngn_per_usd":rate_cache["ngn_per_usd"]})

@app.route("/api/admin/send-settings", methods=["POST"])
@admin_auth.required
def admin_send_settings():
    d = request.get_json(silent=True) or {}
    if "send_fee_pct" in d:
        v=float(d["send_fee_pct"])
        if 0<=v<=5: admin_state["send_fee_pct"]=v
    if "min_send_usd" in d:
        v=float(d["min_send_usd"])
        if 0<v<=1000: admin_state["min_send_usd"]=v
    return jsonify({"status":"ok","send_fee_pct":admin_state["send_fee_pct"],"min_send_usd":admin_state["min_send_usd"]})

fetch_fx_rates()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
