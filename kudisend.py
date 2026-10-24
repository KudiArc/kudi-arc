"""KudiSend: signed challenge -> quote -> escrow deposit -> verified payout."""
import os, re, time, uuid, secrets, logging
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from flask import Blueprint, jsonify, request
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from eth_account.messages import encode_defunct

import db, payouts

log = logging.getLogger("kudi-arc.send")

DEPOSITED_TOPIC = "0x" + Web3.keccak(text="Deposited(bytes32,address,address,uint256)").hex().removeprefix("0x")
ESCROW_ABI = [
    {"name": "deposits", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "", "type": "bytes32"}],
     "outputs": [{"name": "user", "type": "address"}, {"name": "token", "type": "address"},
                 {"name": "amount", "type": "uint256"}, {"name": "time", "type": "uint64"},
                 {"name": "state", "type": "uint8"}]},
    {"name": "minDeposit", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "maxDeposit", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": "", "type": "uint256"}]},
]

CHALLENGE_TTL = 300
MAX_OPEN_CHALLENGES = 10
CONFIRM_GRACE = 3600          # seconds after quote expiry we still honour an in-time deposit
DECIMALS = 6
HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")
QUOTE_ID = re.compile(r"^[0-9a-f]{32}$")
DEPOSIT_ACTIVE = 1
ORDER_STATUSES = {"quoted", "paying", "payout_pending", "completed", "refund_required",
                  "payout_unknown", "refunded"}


NETWORKS = {
    "testnet": {"name": "Arc Testnet", "chain_id": 5042002, "rpc": "https://rpc.testnet.arc.io",
                "explorer": "https://explorer.testnet.arc.io",
                "tokens": {"USDC": "0x3600000000000000000000000000000000000000",
                           "EURC": "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"}},
    # Mainnet EURC must be set explicitly (EURC_ADDRESS) after you have verified it.
    "mainnet": {"name": "Arc Mainnet", "chain_id": 5042, "rpc": "https://rpc.mainnet.arc.io",
                "explorer": "https://explorer.arc.io",
                "tokens": {"USDC": "0x3600000000000000000000000000000000000000"}},
}


def load_config():
    network = os.getenv("NETWORK", "testnet").strip().lower()
    if network not in NETWORKS:
        raise ValueError(f"NETWORK must be one of {sorted(NETWORKS)}, got {network!r}")
    preset = NETWORKS[network]
    mode = os.getenv("SEND_MODE", "mock").strip().lower()
    tokens = dict(preset["tokens"])
    for sym in ("USDC", "EURC"):
        override = os.getenv(f"{sym}_ADDRESS", "").strip()
        if override:
            tokens[sym] = override
    return {
        "network": network,
        "network_name": preset["name"],
        "rpc": os.getenv("ARC_RPC", preset["rpc"]),
        "escrow": os.getenv("ESCROW_ADDRESS", "").strip(),
        "chain_id": int(os.getenv("CHAIN_ID", str(preset["chain_id"]))),
        "quote_ttl": int(os.getenv("QUOTE_TTL_SECONDS", "600")),
        "mode": "live" if mode == "live" else "mock",      # anything else is safe mode
        "tokens": tokens,
        "min_usd": Decimal(os.getenv("SEND_MIN_USD", "10")),
        "max_usd": Decimal(os.getenv("SEND_MAX_USD", "50")),
        "explorer": os.getenv("EXPLORER_URL", preset["explorer"]).rstrip("/"),
    }


def _h(x):
    h = x.hex() if hasattr(x, "hex") else str(x)
    h = h.lower()
    return h if h.startswith("0x") else "0x" + h


def _to_base(amount):
    return int(amount * (10 ** DECIMALS))


def _fmt(d):
    return format(Decimal(d).normalize(), "f") if Decimal(d) != 0 else "0"


def _from_base(n):
    return format((Decimal(n) / (10 ** DECIMALS)).normalize(), "f") if n else "0"


def verify_deposit(w3, cfg, order, tx_hash):
    """Check a deposit tx against an order. Returns (state, reason).
    state: ok | pending | invalid | late | error"""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return "pending", "Transaction not found yet, try again in a moment"
    except Exception as e:
        log.warning(f"receipt lookup failed: {e}")
        return "error", "Chain lookup failed"
    if receipt is None:
        return "pending", "Transaction not found yet, try again in a moment"
    if receipt["status"] != 1:
        return "invalid", "Transaction failed on-chain"

    escrow = cfg["escrow"].lower()
    if str(receipt.get("to") or "").lower() != escrow:
        return "invalid", "Transaction was not sent to the escrow contract"

    ref = order["ref"].lower()
    found = None
    for lg in receipt["logs"]:
        if str(lg["address"]).lower() != escrow:
            continue
        topics = [_h(t) for t in lg["topics"]]
        if len(topics) == 4 and topics[0] == DEPOSITED_TOPIC and topics[1] == ref:
            found = ("0x" + topics[2][-40:], "0x" + topics[3][-40:], int(_h(lg["data"]), 16))
            break
    if not found:
        return "invalid", "No matching deposit found in this transaction"
    user, token, amount = found
    if user != order["wallet"].lower():
        return "invalid", "Deposit was made from a different wallet"
    if token != order["token_address"].lower():
        return "invalid", "Deposit token does not match the quote"
    if amount != order["amount_base"]:
        return "invalid", "Deposit amount does not match the quote"

    try:
        esc = w3.eth.contract(address=Web3.to_checksum_address(escrow), abi=ESCROW_ABI)
        d = esc.functions.deposits(bytes.fromhex(ref[2:])).call()
    except Exception as e:
        log.warning(f"escrow state lookup failed: {e}")
        return "error", "Chain lookup failed"
    if d[4] != DEPOSIT_ACTIVE or str(d[0]).lower() != user or d[2] != amount:
        return "invalid", "Deposit is no longer active"
    if d[3] > order["expires_at"]:
        return "late", "Deposit arrived after the quote expired"
    return "ok", ""


LOG_CHUNK = 10_000
LOG_MAX_CHUNKS = 150          # about 1.5M blocks of history


def find_deposit_tx(w3, escrow, ref, deposit_time):
    """Locate the tx that emitted Deposited(ref, ...). Scans backwards in small chunks."""
    hi = w3.eth.block_number
    for _ in range(LOG_MAX_CHUNKS):
        lo = max(0, hi - LOG_CHUNK + 1)
        logs = w3.eth.get_logs({"address": Web3.to_checksum_address(escrow),
                                "topics": [DEPOSITED_TOPIC, ref], "fromBlock": lo, "toBlock": hi})
        if logs:
            return _h(logs[0]["transactionHash"])
        if lo == 0 or w3.eth.get_block(lo)["timestamp"] < deposit_time - 300:
            return None
        hi = lo - 1
    return None


def create_blueprint(w3, get_rates, get_multi_rates, countries, fees,
                     is_maintenance, admin_min_usd, provider_keys, cfg=None, admin_required=None,
                     admin_fee_floor_pct=lambda: 0):
    """countries: list of {code, currency,...}; fees: {code: pct as float};
    get_rates()/get_multi_rates(): rate dicts; provider_keys: {flutterwave, bitnob, ...}"""
    cfg = cfg or load_config()
    bp = Blueprint("kudisend", __name__)
    currency_of = {c["code"]: c["currency"] for c in countries}
    limits_cache = {"at": 0, "min": None, "max": None}

    def err(msg, code, status):
        return jsonify({"error": msg, "code": code}), status

    def ready():
        """None if sending can run, else an error response."""
        if not cfg["escrow"] or not Web3.is_address(cfg["escrow"]):
            return err("Sending is not available yet", "escrow_not_configured", 503)
        if cfg["mode"] == "live" and not payouts.keys_configured(provider_keys):
            return err("Sending is not available yet", "payouts_not_configured", 503)
        return None

    def onchain_limits():
        if time.time() - limits_cache["at"] > 60:
            esc = w3.eth.contract(address=Web3.to_checksum_address(cfg["escrow"]), abi=ESCROW_ABI)
            limits_cache.update(at=time.time(),
                                min=esc.functions.minDeposit().call(),
                                max=esc.functions.maxDeposit().call())
        return limits_cache["min"], limits_cache["max"]

    def view(o):
        acct = o.get("account_number") or o.get("phone") or ""
        return {
            "quote_id": o["quote_id"], "status": o["status"], "token": o["token"],
            "amount": _from_base(o["amount_base"]), "fee": _from_base(o["fee_base"]),
            "rate": o["rate"], "payout_amount": o["payout_amount"], "currency": o["currency"],
            "country_code": o["country_code"], "recipient_name": o["recipient_name"],
            "recipient_account_last4": acct[-4:], "tx_hash": o["tx_hash"],
            "explorer_url": f"{cfg['explorer']}/tx/{o['tx_hash']}" if o["tx_hash"] else None,
            "expires_at": o["expires_at"], "created_at": o["created_at"],
        }

    # ── public config ──────────────────────────────────────
    @bp.route("/api/send/config")
    def send_config():
        return jsonify({
            "chain_id": cfg["chain_id"], "escrow_address": cfg["escrow"] or None,
            "network": {"name": cfg["network_name"], "chain_id": cfg["chain_id"], "rpc_url": cfg["rpc"],
                        "explorer_url": cfg["explorer"], "native_symbol": "USDC", "native_decimals": 18},
            "tokens": cfg["tokens"], "mode": cfg["mode"], "quote_ttl": cfg["quote_ttl"],
            "min_amount": str(max(cfg["min_usd"], admin_min_usd())), "max_amount": str(cfg["max_usd"]),
        })

    # ── 1. challenge ───────────────────────────────────────
    @bp.route("/api/send/challenge", methods=["POST"])
    def challenge():
        d = request.get_json(silent=True) or {}
        wallet = str(d.get("wallet", ""))
        if not Web3.is_address(wallet):
            return err("Invalid wallet address", "bad_wallet", 400)
        wallet = Web3.to_checksum_address(wallet)
        now = int(time.time())
        if db.open_challenge_count(wallet, now) >= MAX_OPEN_CHALLENGES:
            return err("Too many pending requests, try again shortly", "rate_limited", 429)
        nonce, expires = secrets.token_hex(16), now + CHALLENGE_TTL
        message = (f"KudiArc send authorization\nWallet: {wallet}\nNonce: {nonce}\n"
                   f"Chain: {cfg['chain_id']}\nExpires: {expires}")
        db.create_challenge(wallet, nonce, message, expires)
        return jsonify({"nonce": nonce, "message": message, "expires_at": expires})

    # ── 2. quote ───────────────────────────────────────────
    @bp.route("/api/send/quote", methods=["POST"])
    def quote():
        if is_maintenance():
            return err("KudiArc is under maintenance", "maintenance", 503)
        blocked = ready()
        if blocked:
            return blocked
        d = request.get_json(silent=True) or {}

        # input validation first, so a typo never burns a challenge
        wallet = str(d.get("wallet", ""))
        if not Web3.is_address(wallet):
            return err("Invalid wallet address", "bad_wallet", 400)
        wallet = Web3.to_checksum_address(wallet)
        token = str(d.get("token", "USDC")).upper()
        if token not in cfg["tokens"]:
            return err("Unsupported token", "bad_token", 400)
        try:
            amount = Decimal(str(d.get("amount", "")))
            if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal(1).scaleb(-DECIMALS)):
                raise InvalidOperation
        except InvalidOperation:
            return err("Invalid amount", "bad_amount", 400)
        country = str(d.get("country_code", "")).upper()
        if country not in currency_of:
            return err("Unsupported destination country", "bad_country", 400)
        currency = currency_of[country]
        method = str(d.get("method", "bank"))
        name = str(d.get("recipient_name", "")).strip()
        account = str(d.get("account_number", "")).strip()
        phone = re.sub(r"[\s\-()]", "", str(d.get("phone", "")))
        bank_code = str(d.get("bank_code", "")).strip()
        bank_name = str(d.get("bank_name", "")).strip()[:80]
        if not 2 <= len(name) <= 100:
            return err("Recipient name is required", "bad_recipient", 400)
        if method == "mobile_money":
            if not re.fullmatch(r"\+?\d{7,16}", phone):
                return err("A valid phone number is required", "bad_recipient", 400)
        elif method == "bank":
            if not re.fullmatch(r"\d{6,20}", account) or not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", bank_code):
                return err("A valid bank and account number are required", "bad_recipient", 400)
        else:
            return err("Unsupported payout method", "bad_method", 400)

        # challenge + signature
        nonce = str(d.get("nonce", ""))
        ch = db.get_challenge(nonce)
        now = int(time.time())
        if not ch or ch["used"] or ch["expires_at"] < now or ch["wallet"] != wallet.lower():
            return err("Authorization expired, please sign again", "bad_challenge", 401)
        try:
            signer = Account.recover_message(encode_defunct(text=ch["message"]),
                                             signature=str(d.get("signature", "")))
        except Exception:
            return err("Invalid signature", "bad_signature", 401)
        if signer.lower() != wallet.lower():
            return err("Invalid signature", "bad_signature", 401)

        # limits (token units; the contract enforces the same bounds)
        lo, hi = max(cfg["min_usd"], admin_min_usd()), cfg["max_usd"]
        try:
            chain_lo, chain_hi = onchain_limits()
        except Exception as e:
            log.warning(f"limit lookup failed: {e}")
            return err("Chain lookup failed, try again", "chain_error", 503)
        lo = max(lo, Decimal(chain_lo) / 10 ** DECIMALS)
        hi = min(hi, Decimal(chain_hi) / 10 ** DECIMALS)
        if amount < lo or amount > hi:
            return err(f"Amount must be between {lo.normalize():f} and {hi.normalize():f} {token}",
                       "amount_out_of_range", 400)

        # pricing (Decimal only)
        rate = Decimal(str(get_multi_rates().get(currency, 0)))
        if rate <= 0:
            return err("Rate unavailable, try again shortly", "rate_unavailable", 503)
        floor = max(Decimal(str(admin_fee_floor_pct() or 0)), Decimal(0)) / 100   # your revenue floor
        fee_pct = max(Decimal(str(fees.get(country, 0.030))), floor)
        fee = (amount * fee_pct).quantize(Decimal(1).scaleb(-DECIMALS), ROUND_HALF_UP)
        net = amount - fee
        if token == "EURC":
            net = net * Decimal(str(get_rates()["eur_usd"]))
        payout = (net * rate).quantize(Decimal("0.01"), ROUND_DOWN)
        if payout <= 0:
            return err("Amount too small", "amount_out_of_range", 400)

        if not db.consume_challenge(nonce):      # single use, atomic
            return err("Authorization already used", "bad_challenge", 401)

        quote_id = uuid.uuid4().hex
        order = {
            "quote_id": quote_id, "ref": _h(Web3.keccak(text=quote_id)), "wallet": wallet.lower(),
            "token": token, "token_address": cfg["tokens"][token].lower(),
            "amount_base": _to_base(amount), "fee_base": _to_base(fee), "rate": _fmt(rate),
            "payout_amount": str(payout), "country_code": country, "currency": currency,
            "method": method, "recipient_name": name, "bank_code": bank_code,
            "bank_name": bank_name, "account_number": account, "phone": phone,
            "expires_at": now + cfg["quote_ttl"],
        }
        db.create_order(order)
        return jsonify({
            "quote_id": quote_id, "ref": order["ref"], "escrow_address": cfg["escrow"],
            "chain_id": cfg["chain_id"], "token": token, "token_address": cfg["tokens"][token],
            "amount": _fmt(amount), "amount_base": str(order["amount_base"]),
            "fee": _fmt(fee), "fee_pct": float(fee_pct * 100), "rate": _fmt(rate),
            "payout_amount": str(payout), "currency": currency,
            "expires_at": order["expires_at"], "expires_in": cfg["quote_ttl"],
        })

    # ── 3. confirm ─────────────────────────────────────────
    def run_payout(order):
        qid = order["quote_id"]
        payout_ref = f"KUDI-{order['currency']}-{qid[:12].upper()}"
        db.update_order(qid, status="payout_pending", provider_ref=payout_ref)
        if cfg["mode"] != "live":
            db.update_order(qid, status="completed", provider="sandbox")
            log.info(f"[SANDBOX] order {qid}: {order['payout_amount']} {order['currency']}")
        else:
            state, msg, provider, _ = payouts.dispatch(order, payout_ref, provider_keys)
            if state == "ok":
                db.update_order(qid, provider=provider)
            elif state == "unknown":
                db.update_order(qid, status="payout_unknown", provider=provider, error=msg[:200])
            else:
                db.update_order(qid, status="refund_required", error=msg[:200])
        fresh = db.get_order(qid)
        if fresh["status"] in ("payout_pending", "completed"):
            try:
                db.save_send(fresh["wallet"], float(_from_base(fresh["amount_base"])),
                             float(fresh["payout_amount"]), fresh["recipient_name"],
                             fresh["bank_name"] or "Mobile Money", fresh["account_number"],
                             fresh["phone"], payout_ref, fresh["status"], tx_hash=fresh["tx_hash"],
                             from_token=fresh["token"], to_token=fresh["currency"],
                             fee=float(_from_base(fresh["fee_base"])))
            except Exception as e:
                log.warning(f"history save failed: {e}")
        return fresh

    def process_confirmation(order, tx_hash):
        """Verify a deposit tx for an order still in 'quoted', then pay out or park for refund.
        Returns (http_status, payload)."""
        quote_id = order["quote_id"]
        state, reason = verify_deposit(w3, cfg, order, tx_hash)
        if state == "pending":
            return 202, {"status": "pending", "message": reason}
        if state == "error":
            return 503, {"error": reason, "code": "chain_error"}
        if state == "invalid":
            return 400, {"error": reason, "code": "invalid_deposit"}

        stale = int(time.time()) > order["expires_at"] + CONFIRM_GRACE
        if state == "late" or stale:
            if db.claim_order(quote_id, tx_hash, "quoted", "refund_required"):
                db.update_order(quote_id, error="Deposit outside the quote window")
            return 200, view(db.get_order(quote_id))

        if not db.claim_order(quote_id, tx_hash, "quoted", "paying"):
            latest = db.get_order(quote_id)
            if (latest["tx_hash"] or "").lower() == tx_hash:
                return 200, view(latest)
            return 409, {"error": "This order was already processed", "code": "already_processed"}
        return 200, view(run_payout(db.get_order(quote_id)))

    @bp.route("/api/send/confirm", methods=["POST"])
    def confirm():
        blocked = ready()
        if blocked:
            return blocked
        d = request.get_json(silent=True) or {}
        quote_id, tx_hash = str(d.get("quote_id", "")), str(d.get("tx_hash", "")).lower()
        if not QUOTE_ID.match(quote_id) or not HEX32.match(tx_hash):
            return err("Invalid request", "bad_request", 400)
        order = db.get_order(quote_id)
        if not order:
            return err("Quote not found", "not_found", 404)
        if order["status"] != "quoted":
            if (order["tx_hash"] or "").lower() == tx_hash:
                return jsonify(view(order))          # safe to call again
            return err("This order was already processed", "already_processed", 409)

        try:
            if w3.eth.chain_id != cfg["chain_id"]:
                return err("Chain mismatch", "chain_error", 503)
        except Exception:
            return err("Chain lookup failed, try again", "chain_error", 503)

        code, payload = process_confirmation(order, tx_hash)
        return jsonify(payload), code

    # ── 4. status ──────────────────────────────────────────
    @bp.route("/api/send/order/<quote_id>")
    def order_status(quote_id):
        if not QUOTE_ID.match(quote_id):
            return err("Invalid request", "bad_request", 400)
        order = db.get_order(quote_id)
        if not order:
            return err("Quote not found", "not_found", 404)
        return jsonify(view(order))

    # ── admin (owner-signed) ───────────────────────────────
    if admin_required:
        def admin_view(o):
            acct = o.get("account_number") or o.get("phone") or ""
            action = None
            if o["chain_state"] == "none":
                action = {"completed": "settle", "refund_required": "refund",
                          "payout_unknown": "resolve", "payout_pending": "wait"}.get(o["status"])
            return {
                "quote_id": o["quote_id"], "ref": o["ref"], "wallet": o["wallet"], "token": o["token"],
                "amount": _from_base(o["amount_base"]), "fee": _from_base(o["fee_base"]),
                "payout_amount": o["payout_amount"], "currency": o["currency"],
                "country_code": o["country_code"], "recipient_name": o["recipient_name"],
                "recipient_account_last4": acct[-4:], "status": o["status"],
                "chain_state": o["chain_state"], "tx_hash": o["tx_hash"], "provider": o["provider"],
                "provider_ref": o["provider_ref"], "error": o["error"], "action": action,
                "created_at": o["created_at"], "updated_at": o["updated_at"], "expires_at": o["expires_at"],
            }

        @bp.route("/api/admin/send/orders")
        @admin_required
        def admin_orders():
            statuses = [x for x in request.args.get("status", "").split(",") if x in ORDER_STATUSES] or None
            chain_state = request.args.get("chain_state")
            if chain_state not in (None, "", "none", "settled", "refunded"):
                return err("Invalid chain_state", "bad_request", 400)
            try:
                limit = max(1, min(int(request.args.get("limit", "100")), 500))
            except ValueError:
                return err("Invalid limit", "bad_request", 400)
            rows = db.list_orders(statuses, chain_state or None, limit)
            return jsonify({"orders": [admin_view(o) for o in rows]})

        @bp.route("/api/admin/send/resolve", methods=["POST"])
        @admin_required
        def admin_resolve():
            """Record the real outcome of a payout whose result we could not confirm."""
            d = request.get_json(silent=True) or {}
            qid, outcome = str(d.get("quote_id", "")), d.get("outcome")
            to = {"paid": "completed", "failed": "refund_required"}.get(outcome)
            if not QUOTE_ID.match(qid) or not to:
                return err("Invalid request", "bad_request", 400)
            if not db.transition_order(qid, ("payout_unknown", "payout_pending"), to):
                return err("Order is not awaiting resolution", "bad_state", 409)
            log.info(f"admin resolved order {qid} as {outcome}")
            return jsonify(admin_view(db.get_order(qid)))

        @bp.route("/api/admin/send/chain-sync", methods=["POST"])
        @admin_required
        def admin_chain_sync():
            """Read-only: copy settle/refund results from the escrow contract into the DB."""
            blocked = ready()
            if blocked:
                return blocked
            esc = w3.eth.contract(address=Web3.to_checksum_address(cfg["escrow"]), abi=ESCROW_ABI)
            orders = db.list_orders(("completed", "refund_required", "payout_unknown", "payout_pending"),
                                    "none", 500)
            out = {"checked": len(orders), "settled": 0, "refunded": 0, "anomalies": []}
            for o in orders:
                try:
                    state = esc.functions.deposits(bytes.fromhex(o["ref"][2:])).call()[4]
                except Exception as e:
                    log.warning(f"chain-sync lookup failed: {e}")
                    return err("Chain lookup failed", "chain_error", 503)
                if state == 2:
                    db.update_order(o["quote_id"], chain_state="settled"); out["settled"] += 1
                elif state == 3:
                    db.update_order(o["quote_id"], chain_state="refunded"); out["refunded"] += 1
                    db.transition_order(o["quote_id"], ("refund_required", "payout_unknown", "payout_pending"),
                                        "refunded")
                elif state == 0:
                    out["anomalies"].append({"quote_id": o["quote_id"], "note": "no deposit on-chain"})
            return jsonify(out)

        @bp.route("/api/admin/send/reconcile", methods=["POST"])
        @admin_required
        def admin_reconcile():
            """Recover deposits that exist on-chain but were never confirmed (e.g. user closed the tab)."""
            blocked = ready()
            if blocked:
                return blocked
            esc = w3.eth.contract(address=Web3.to_checksum_address(cfg["escrow"]), abi=ESCROW_ABI)
            cutoff = int(time.time()) - 7 * 86400
            out = {"checked": 0, "recovered": [], "not_found": []}
            for o in db.list_orders(("quoted",), None, 200):
                if o["created_at"] < cutoff:
                    continue
                try:
                    dep = esc.functions.deposits(bytes.fromhex(o["ref"][2:])).call()
                    if dep[4] != DEPOSIT_ACTIVE:
                        continue
                    out["checked"] += 1
                    tx = find_deposit_tx(w3, cfg["escrow"], o["ref"], dep[3])
                except Exception as e:
                    log.warning(f"reconcile lookup failed: {e}")
                    return err("Chain lookup failed", "chain_error", 503)
                if not tx:
                    out["not_found"].append(o["quote_id"]); continue
                code, payload = process_confirmation(o, tx)
                out["recovered"].append({"quote_id": o["quote_id"], "tx_hash": tx,
                                         "result": payload.get("status") or payload.get("error")})
            return jsonify(out)

    return bp
