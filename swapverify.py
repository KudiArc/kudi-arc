"""Record swaps from what the chain says happened, never from what the browser says."""
import logging, re, sqlite3, time
from decimal import Decimal
from flask import Blueprint, jsonify, request
from web3 import Web3
from web3.exceptions import TransactionNotFound

import db

log = logging.getLogger("kudi-arc.swap")

SWAPPED_TOPIC = "0x" + Web3.keccak(text="Swapped(address,address,address,uint256,uint256,uint256)").hex().removeprefix("0x")
HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")
DECIMALS = 10 ** 6
LOOKUP_TRIES = 4


def _h(x):
    h = x.hex() if hasattr(x, "hex") else str(x)
    h = h.lower()
    return h if h.startswith("0x") else "0x" + h


def read_swap(w3, contract_addr, tokens, tx_hash):
    """Return (state, info). state: ok | pending | invalid | error"""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return "pending", "Transaction not found yet"
    except Exception as e:
        log.warning(f"swap receipt lookup failed: {e}")
        return "error", "Chain lookup failed"
    if receipt is None:
        return "pending", "Transaction not found yet"
    if receipt["status"] != 1:
        return "invalid", "Transaction failed on-chain"
    contract = contract_addr.lower()
    if str(receipt.get("to") or "").lower() != contract:
        return "invalid", "Transaction was not sent to the swap contract"
    by_addr = {addr.lower(): sym for sym, addr in tokens.items()}
    for lg in receipt["logs"]:
        if str(lg["address"]).lower() != contract:
            continue
        topics = [_h(t) for t in lg["topics"]]
        if len(topics) != 4 or topics[0] != SWAPPED_TOPIC:
            continue
        data = _h(lg["data"])[2:]
        if len(data) != 192:
            continue
        src, dst = by_addr.get("0x" + topics[2][-40:]), by_addr.get("0x" + topics[3][-40:])
        if not src or not dst:
            return "invalid", "Unsupported token in swap"
        a_in, a_out, fee = (int(data[i:i + 64], 16) for i in (0, 64, 128))
        return "ok", {"user": "0x" + topics[1][-40:], "from_token": src, "to_token": dst,
                      "amount_in": a_in, "amount_out": a_out, "fee": fee}
    return "invalid", "No swap found in this transaction"


def create_blueprint(w3, contract_addr, tokens, get_rates, get_multi_rates):
    bp = Blueprint("swapverify", __name__)

    @bp.route("/api/swap/record", methods=["POST"])
    def record_swap():
        if not contract_addr or not Web3.is_address(contract_addr):
            return jsonify({"error": "Swaps are not available yet"}), 503
        d = request.get_json(silent=True) or {}
        wallet, tx_hash = str(d.get("wallet", "")), str(d.get("tx_hash", "")).lower()
        if not Web3.is_address(wallet) or not HEX32.match(tx_hash):
            return jsonify({"error": "Invalid wallet or transaction hash"}), 400
        if db.swap_exists(tx_hash):
            return jsonify({"status": "saved"})                    # safe to call again

        for attempt in range(LOOKUP_TRIES):                        # node may lag a moment behind
            state, info = read_swap(w3, contract_addr, tokens, tx_hash)
            if state != "pending":
                break
            time.sleep(1)
        if state == "pending":
            return jsonify({"status": "pending"}), 202
        if state == "error":
            return jsonify({"error": info}), 503
        if state == "invalid":
            return jsonify({"error": info}), 400
        if info["user"].lower() != wallet.lower():
            return jsonify({"error": "Swap was made by a different wallet"}), 400

        a_in, a_out, fee = (Decimal(info[k]) / DECIMALS for k in ("amount_in", "amount_out", "fee"))
        net = a_in - fee
        rate = float(a_out / net) if net > 0 else 0.0
        try:
            usd = a_in if info["from_token"] == "USDC" else a_in * Decimal(str(get_rates()["eur_usd"]))
            ngn = float(usd * Decimal(str(get_multi_rates().get("NGN", 0))))
        except Exception:
            ngn = 0.0
        try:
            db.save_swap(wallet=Web3.to_checksum_address(wallet), from_token=info["from_token"],
                         to_token=info["to_token"], amount_in=float(a_in), amount_out=float(a_out),
                         fee=float(fee), rate=rate, ngn_equiv=ngn, tx_hash=tx_hash)
        except sqlite3.IntegrityError:
            pass                                                   # a concurrent request saved it first
        return jsonify({"status": "saved"})

    return bp
