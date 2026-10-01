import os, time, logging, requests, uuid, json as _json, threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from web3 import Web3
from eth_account.messages import encode_defunct
from dotenv import load_dotenv
from db import init_db, save_swap, save_send, get_history, update_send_status

load_dotenv()

ARC_RPC       = os.getenv("ARC_RPC", "https://rpc.testnet.arc.network")
OWNER_PK      = os.getenv("OWNER_PRIVATE_KEY", "")
CONTRACT_ADDR = os.getenv("KUDI_CONTRACT_ADDRESS", "")
CHAIN_ID      = int(os.getenv("CHAIN_ID", "5042002"))
BITNOB_KEY    = os.getenv("BITNOB_SECRET_KEY", "mock")
BITNOB_BASE   = os.getenv("BITNOB_BASE_URL", "https://sandboxapi.bitnob.co/api/v1")
FLW_SECRET    = os.getenv("FLUTTERWAVE_SECRET_KEY", "mock").strip()
if FLW_SECRET.lower().startswith("bearer "): FLW_SECRET = FLW_SECRET[7:].strip()
FLW_BASE      = "https://api.flutterwave.com/v3"
PSK_SECRET    = os.getenv("PAYSTACK_SECRET_KEY", "mock")
PSK_BASE      = "https://api.paystack.co"
PORT = int(os.getenv("PORT", "5001"))
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS", "0x3BFA763D0973E0c5Fc904139A9065C790bf6C1f1").lower()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kudi-arc")

app = Flask(__name__)

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

_ADMIN_FILE = "admin_state.json"
def _load_admin():
    try:
        with open(_ADMIN_FILE) as f: return _json.load(f)
    except: return {"maintenance":False,"message":"KudiArc is under maintenance. We'll be back shortly.","send_fee_pct":0.3,"min_send_usd":5.0}
def _save_admin(s):
    try:
        with open(_ADMIN_FILE,"w") as f: _json.dump(s,f)
    except: pass
admin_state = _load_admin()
proto_stats = {"unique_wallets":set(),"swap_count":0,"send_count":0,"start_time":time.time()}

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
DB_PATH = "/home/ubuntu/kudi-arc/kudi.db"

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
    return jsonify({"status":status,"chain":"Arc Testnet","chain_id":CHAIN_ID,"components":components,"version":"1.0.0"})

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

@app.route("/api/swap/record", methods=["POST"])
def record_swap():
    d = request.get_json()
    if not d: return jsonify({"error":"No data"}), 400
    wallet = d.get("wallet","")
    if not wallet or not wallet.startswith("0x") or len(wallet) != 42:
        return jsonify({"error":"Invalid wallet address"}), 400
    tx_hash = d.get("tx_hash","")
    if not tx_hash or not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return jsonify({"error":"Invalid transaction hash"}), 400
    amount_in = d.get("amount_in", 0)
    if not isinstance(amount_in, (int, float)) or amount_in <= 0:
        return jsonify({"error":"Invalid amount"}), 400
    try:
        save_swap(wallet=wallet,from_token=d.get("from_token"),to_token=d.get("to_token"),
            amount_in=amount_in,amount_out=d.get("amount_out"),fee=d.get("fee"),
            rate=d.get("rate"),ngn_equiv=d.get("ngn_equiv"),tx_hash=tx_hash)
        proto_stats["unique_wallets"].add(wallet.lower())
        proto_stats["swap_count"] += 1
        return jsonify({"status":"saved"})
    except Exception as e:
        log.error(f"swap record failed: {e}")
        return jsonify({"error":str(e)}), 500

@app.route("/api/send/webhook", methods=["POST"])
def bitnob_webhook():
    secret = os.getenv("BITNOB_WEBHOOK_SECRET", "")
    if secret:
        token = request.headers.get("x-bitnob-signature", "")
        if token != secret:
            log.warning(f"Fake Bitnob webhook blocked from {request.remote_addr}")
            return jsonify({"error": "Unauthorized"}), 401
    data   = request.get_json()
    ref    = data.get("reference","")
    status = "completed" if data.get("status") in ("success","completed") else "failed"
    if ref:
        update_send_status(ref,status)
        log.info(f"Bitnob webhook: {ref} → {status}")
    return jsonify({"received":True})

@app.route("/api/send/flw-webhook", methods=["POST"])
def flutterwave_webhook():
    secret = request.headers.get("verif-hash","")
    if secret != os.getenv("FLW_WEBHOOK_SECRET",""):
        return jsonify({"error":"Unauthorized"}), 401
    data   = request.get_json()
    ref    = data.get("data",{}).get("reference","")
    status = data.get("data",{}).get("status","")
    mapped = "completed" if status in ("SUCCESSFUL","successful") else "failed"
    if ref:
        update_send_status(ref,mapped)
        log.info(f"Flutterwave webhook: {ref} → {mapped}")
    return jsonify({"received":True})

@app.route("/api/send/paystack-webhook", methods=["POST"])
def paystack_webhook():
    import hmac, hashlib
    secret    = os.getenv("PAYSTACK_SECRET_KEY","")
    signature = request.headers.get("x-paystack-signature","")
    body      = request.get_data()
    expected  = hmac.new(secret.encode(),body,hashlib.sha512).hexdigest()
    if signature != expected: return jsonify({"error":"Unauthorized"}), 401
    data   = request.get_json()
    ref    = data.get("data",{}).get("reference","")
    status = data.get("data",{}).get("status","")
    mapped = "completed" if status=="success" else "failed"
    if ref:
        update_send_status(ref,mapped)
        log.info(f"Paystack webhook: {ref} → {mapped}")
    return jsonify({"received":True})

@app.route("/api/send/payout", methods=["POST"])
def send_payout():
    d            = request.get_json()
    wallet       = d.get("wallet")
    amount_usd   = float(d.get("amount_usdc",0))
    country_code = d.get("country_code","NG")
    currency     = d.get("currency","NGN")
    recipient    = d.get("recipient_name","")
    account_no   = d.get("account_number","")
    bank_code    = d.get("bank_code","")
    bank_name    = d.get("bank_name","")
    phone        = d.get("phone","")
    method       = d.get("method","bank")

    if amount_usd <= 0: return jsonify({"error":"Invalid amount"}), 400

    rates      = get_multi_rates_fresh()
    rate       = rates.get(currency,0)
    fee_pct    = SEND_FEES.get(country_code,0.030)
    fee        = round(amount_usd*fee_pct,6)
    net_amount = amount_usd - fee
    payout     = round(net_amount*rate,2)
    ref        = f"KUDI-{currency}-{uuid.uuid4().hex[:10].upper()}"

    if FLW_SECRET=="mock" and BITNOB_KEY=="mock" and PSK_SECRET=="mock":
        log.info(f"[MOCK] {amount_usd} USDC → {currency} {payout:,.2f} → {recipient} ({country_code})")
        try:
            save_send(wallet,amount_usd,payout,recipient,bank_name or "Mobile Money",account_no,phone,ref,"mock_success")
            proto_stats["send_count"] += 1
            if wallet: proto_stats["unique_wallets"].add(wallet.lower())
        except Exception as e: log.warning(f"DB save failed: {e}")
        return jsonify({"status":"mock_success","reference":ref,"currency":currency,"country_code":country_code,
            "payout_amount":payout,"fee_usdc":fee,"fee_pct":round(fee_pct*100,2),"rate_used":rate,"partner":"Sandbox",
            "message":f"[SANDBOX] {currency} {payout:,.2f} would be sent to {recipient}","estimated_arrival":"1-2 business days"})

    def try_flutterwave():
        if FLW_SECRET=="mock": return False,"FLW not configured",None
        headers = {"Authorization":f"Bearer {FLW_SECRET}","Content-Type":"application/json"}
        if method=="mobile_money":
            payload = {"account_bank":country_code,"account_number":phone,"amount":payout,"currency":currency,
                "narration":f"KudiArc remittance to {recipient}","reference":ref,"beneficiary_name":recipient,
                "meta":{"mobile_number":phone}}
        else:
            if not bank_code:
                log.error(f"Missing bank_code for {country_code} bank transfer")
                return False,"Missing bank code — please select a bank",None
            payload = {"account_bank":bank_code,"account_number":account_no,"amount":payout,"currency":currency,
                "narration":f"KudiArc remittance to {recipient}","reference":ref,"beneficiary_name":recipient}
        try:
            resp = requests.post(f"{FLW_BASE}/transfers",json=payload,headers=headers,timeout=30)
            data = resp.json()
            if resp.status_code in (200,201) and data.get("status")=="success":
                return True,"Transfer initiated",data.get("data",{}).get("reference",ref)
            return False,data.get("message","FLW transfer failed"),None
        except Exception as e: return False,str(e),None

    def try_bitnob():
        if BITNOB_KEY=="mock" or country_code not in BITNOB_COUNTRIES:
            return False,"Bitnob not available for this corridor",None
        headers = {"Authorization":f"Bearer {BITNOB_KEY}","Content-Type":"application/json"}
        payload = {"customerEmail":f"{wallet[:8]}@kudiarc.app","amount":int(payout*100),"currency":currency,
            "reference":f"{ref}-BNB","bankCode":bank_code,"bankAccountNumber":account_no,
            "bankAccountName":recipient,"narration":f"KudiArc remittance {amount_usd} USDC"}
        try:
            resp = requests.post(f"{BITNOB_BASE}/offramps/initiate",json=payload,headers=headers,timeout=30)
            data = resp.json()
            if resp.status_code==200 and data.get("status"):
                return True,"Transfer initiated via Bitnob",f"{ref}-BNB"
            return False,data.get("message","Bitnob failed"),None
        except Exception as e: return False,str(e),None

    def try_paystack():
        if PSK_SECRET=="mock" or country_code not in PAYSTACK_COUNTRIES:
            return False,"Paystack not available for this corridor",None
        headers = {"Authorization":f"Bearer {PSK_SECRET}","Content-Type":"application/json"}
        payload = {"source":"balance","amount":int(payout*100),"currency":currency,"recipient":account_no,
            "reason":f"KudiArc remittance to {recipient}","reference":f"{ref}-PSK"}
        try:
            resp = requests.post(f"{PSK_BASE}/transfer",json=payload,headers=headers,timeout=30)
            data = resp.json()
            if resp.status_code==200 and data.get("status"):
                return True,"Transfer initiated via Paystack",f"{ref}-PSK"
            return False,data.get("message","Paystack failed"),None
        except Exception as e: return False,str(e),None

    success,message,provider_ref = try_flutterwave()
    provider = "Flutterwave"
    if not success:
        log.warning(f"FLW failed ({country_code}): {message} — trying Bitnob")
        success,message,provider_ref = try_bitnob()
        provider = "Bitnob"
    if not success:
        log.warning(f"Bitnob failed ({country_code}): {message} — trying Paystack")
        success,message,provider_ref = try_paystack()
        provider = "Paystack"

    if success:
        try:
            save_send(wallet,amount_usd,payout,recipient,bank_name or "Mobile Money",account_no,phone,ref,"pending")
            proto_stats["send_count"] += 1
            if wallet: proto_stats["unique_wallets"].add(wallet.lower())
        except Exception as e: log.warning(f"DB save failed: {e}")
        log.info(f"Payout success via {provider}: {amount_usd} USDC → {currency} {payout:,.2f}")
        return jsonify({"status":"pending","reference":ref,"provider_reference":provider_ref,
            "currency":currency,"country_code":country_code,"payout_amount":payout,"fee_usdc":fee,
            "fee_pct":round(fee_pct*100,2),"rate_used":rate,"partner":provider,
            "message":f"{currency} {payout:,.2f} is being sent to {recipient} via {provider}",
            "estimated_arrival":"Minutes" if provider in ("Bitnob","Flutterwave") and country_code=="NG" else "1-2 business days"})

    log.error(f"All providers failed for {country_code}: {message}")
    if "not available" in message.lower() or "corridor" in message.lower():
        return jsonify({"error":f"Payout to {country_code} is currently in sandbox mode. Live payouts activate at mainnet."}), 503
    if "resolve" in message.lower() or "creation failed" in message.lower():
        return jsonify({"error":"Account could not be verified. On testnet, only Flutterwave test account numbers work. Real accounts will work on mainnet."}), 503
    return jsonify({"error":f"Payout failed: {message}"}), 503

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

def verify_admin(data):
    try:
        sig  = data.get("signature","")
        msg  = data.get("message","")
        addr = data.get("wallet","").lower()
        if addr != OWNER_ADDRESS: return False
        recovered = w3.eth.account.recover_message(encode_defunct(text=msg),signature=sig).lower()
        return recovered == OWNER_ADDRESS
    except Exception as e:
        log.warning(f"Admin sig verify failed: {e}")
        return False

@app.route("/api/admin/status")
def admin_status():
    return jsonify({"maintenance":admin_state.get("maintenance",False),"message":admin_state.get("message","")})

@app.route("/api/admin/stats")
def admin_stats():
    uptime=int(time.time()-proto_stats["start_time"])
    swap_count=send_count=unique_wallets=0
    total_swap_fees=total_send_fees=0.0
    try:
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(DB_PATH)
        swap_count      = _conn.execute("SELECT COUNT(*) FROM transactions WHERE tx_type='swap'").fetchone()[0]
        send_count      = _conn.execute("SELECT COUNT(*) FROM transactions WHERE tx_type='send'").fetchone()[0]
        unique_wallets  = _conn.execute("SELECT COUNT(DISTINCT wallet) FROM transactions").fetchone()[0]
        total_swap_fees = round(float(_conn.execute("SELECT COALESCE(SUM(fee),0) FROM transactions WHERE tx_type='swap'").fetchone()[0] or 0),6)
        total_send_fees = round(float(_conn.execute("SELECT COALESCE(SUM(fee),0) FROM transactions WHERE tx_type='send'").fetchone()[0] or 0),6)
        total_swap_volume = round(float(_conn.execute("SELECT COALESCE(SUM(amount_in),0) FROM transactions WHERE tx_type='swap'").fetchone()[0] or 0),2)
        _conn.close()
    except Exception as _e:
        log.warning(f"admin_stats DB query failed: {_e}")
        swap_count=proto_stats["swap_count"]; send_count=proto_stats["send_count"]
        unique_wallets=len(proto_stats["unique_wallets"])
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
def admin_recent_txs():
    d = request.get_json()
    if not verify_admin(d): return jsonify({"error":"Unauthorized"}), 403
    try:
        import sqlite3
        conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
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
def admin_maintenance():
    d = request.get_json()
    if not verify_admin(d): return jsonify({"error":"Unauthorized"}), 403
    admin_state["maintenance"]=bool(d.get("maintenance",False))
    if "message" in d: admin_state["message"]=d["message"]
    _save_admin(admin_state)
    log.info(f"Maintenance={admin_state['maintenance']}")
    return jsonify({"status":"ok","maintenance":admin_state["maintenance"]})

@app.route("/api/admin/refresh-rates", methods=["POST"])
def admin_refresh_rates():
    d = request.get_json()
    if not verify_admin(d): return jsonify({"error":"Unauthorized"}), 403
    fetch_fx_rates()
    return jsonify({"status":"ok","usd_eur":rate_cache["usd_eur"],"ngn_per_usd":rate_cache["ngn_per_usd"]})

@app.route("/api/admin/send-settings", methods=["POST"])
def admin_send_settings():
    d = request.get_json()
    if not verify_admin(d): return jsonify({"error":"Unauthorized"}), 403
    if "send_fee_pct" in d:
        v=float(d["send_fee_pct"])
        if 0<=v<=5: admin_state["send_fee_pct"]=v
    if "min_send_usd" in d:
        v=float(d["min_send_usd"])
        if 0<v<=1000: admin_state["min_send_usd"]=v
    _save_admin(admin_state)
    return jsonify({"status":"ok","send_fee_pct":admin_state["send_fee_pct"],"min_send_usd":admin_state["min_send_usd"]})

fetch_fx_rates()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
