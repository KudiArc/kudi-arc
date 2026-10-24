"""Payout provider webhooks.

A webhook is only a trigger: authenticate it (fail closed), ask the provider what
really happened, and only act on a final answer from the provider.
"""
import hashlib, hmac, logging
from flask import Blueprint, jsonify, request

import db, payouts

log = logging.getLogger("kudi-arc.webhooks")


def _set(secret):
    value = str(secret or "").strip()
    return bool(value) and value.lower() != "mock"


def _same(a, b):
    return hmac.compare_digest(str(a).encode(), str(b).encode())


def create_blueprint(keys, secrets):
    """keys: provider API keys; secrets: {flutterwave: verif hash, bitnob: HMAC secret}"""
    bp = Blueprint("webhooks", __name__)

    def deny(reason, status=401):
        log.warning(f"webhook rejected: {reason} from {request.remote_addr}")
        return jsonify({"error": "Unauthorized"}), status

    def finish(provider, ref, claimed, provider_id, trust_signed=False):
        """Apply a final result for ref after checking it with the provider."""
        if claimed == "pending":
            return jsonify({"received": True, "ignored": "not final"})
        if not ref:
            return jsonify({"received": True, "ignored": "no reference"})
        order = db.get_order_by_provider_ref(ref)
        state, detail = payouts.verify(provider, ref, keys, order, provider_id)
        if state == "unverifiable" and trust_signed:
            final = claimed                       # authentic signed event, no lookup API available
        elif state in ("completed", "failed"):
            final = state                         # the provider's own answer wins
        elif state == "error":
            return jsonify({"error": "Could not verify, retry later"}), 503
        else:
            log.warning(f"{provider} webhook for {ref} ignored: {state} ({detail})")
            return jsonify({"received": True, "ignored": state})
        if final != claimed:
            log.warning(f"{provider} webhook for {ref} said {claimed} but provider says {final}")
        db.update_send_status(ref, "completed" if final == "completed" else "failed")
        log.info(f"{provider} payout {ref} -> {final}")
        return jsonify({"received": True})

    # ── Flutterwave: static secret hash in the verif-hash header ──
    @bp.route("/api/send/flw-webhook", methods=["POST"])
    def flutterwave():
        secret = secrets.get("flutterwave")
        if not _set(secret):
            return deny("flutterwave webhook secret not configured", 503)
        if not _same(request.headers.get("verif-hash", ""), secret):
            return deny("bad verif-hash")
        data = (request.get_json(silent=True) or {}).get("data") or {}
        st = str(data.get("status", "")).upper()
        claimed = {"SUCCESSFUL": "completed", "FAILED": "failed"}.get(st, "pending")
        return finish("flutterwave", str(data.get("reference", "")), claimed, data.get("id"))

    # ── Paystack: HMAC-SHA512 of the raw body with the secret key ──
    @bp.route("/api/send/paystack-webhook", methods=["POST"])
    def paystack():
        secret = keys.get("paystack")
        if not _set(secret):
            return deny("paystack key not configured", 503)
        expected = hmac.new(secret.encode(), request.get_data(), hashlib.sha512).hexdigest()
        if not _same(request.headers.get("x-paystack-signature", ""), expected):
            return deny("bad signature")
        body = request.get_json(silent=True) or {}
        claimed = {"transfer.success": "completed", "transfer.failed": "failed",
                   "transfer.reversed": "failed"}.get(body.get("event"), "pending")
        return finish("paystack", str((body.get("data") or {}).get("reference", "")), claimed, None)

    # ── Bitnob: HMAC-SHA512 of the raw body (scheme unconfirmed, see docs) ──
    @bp.route("/api/send/webhook", methods=["POST"])
    def bitnob():
        secret = secrets.get("bitnob")
        if not _set(secret):
            return deny("bitnob webhook secret not configured", 503)
        expected = hmac.new(secret.encode(), request.get_data(), hashlib.sha512).hexdigest()
        if not _same(request.headers.get("x-bitnob-signature", ""), expected):
            return deny("bad signature")
        body = request.get_json(silent=True) or {}
        st = str(body.get("status", "")).lower()
        claimed = {"success": "completed", "completed": "completed", "failed": "failed"}.get(st, "pending")
        return finish("bitnob", str(body.get("reference", "")), claimed, None, trust_signed=True)

    return bp
