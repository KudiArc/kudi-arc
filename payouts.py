"""Fiat payout providers for KudiSend.

dispatch() returns (state, message, provider, provider_ref) where state is:
  ok        provider accepted the transfer
  rejected  provider definitely did not execute it (safe to try the next one / refund)
  unknown   outcome unclear (timeout, 5xx): never fail over, needs manual review
"""
import logging
from decimal import Decimal, InvalidOperation
import requests

log = logging.getLogger("kudi-arc.payouts")

FLW_BASE = "https://api.flutterwave.com/v3"
PSK_BASE = "https://api.paystack.co"
BITNOB_COUNTRIES = {"NG", "GH", "KE"}
PAYSTACK_COUNTRIES = {"NG", "GH", "KE", "ZA"}


def _configured(secret):
    return bool(secret) and secret != "mock"


def keys_configured(keys):
    return any(_configured(keys.get(k)) for k in ("flutterwave", "bitnob", "paystack"))


def _post(url, payload, headers):
    """Returns (http_status, json_or_None, state_on_error)."""
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.exceptions.ConnectionError:
        return None, None, "rejected"      # never reached the provider
    except Exception:
        return None, None, "unknown"       # timeout etc: may have gone through
    try:
        body = resp.json()
    except Exception:
        body = None
    return resp.status_code, body, None


def _result(status, body, ok, ref, label):
    if status is None:
        return None
    if ok(status, body):
        return "ok", f"Transfer initiated via {label}", ref
    if status >= 500:
        return "unknown", f"{label} server error", None
    msg = (body or {}).get("message", f"{label} rejected the transfer")
    return "rejected", str(msg)[:200], None


def _flutterwave(order, ref, keys):
    secret = keys.get("flutterwave")
    if not _configured(secret):
        return "skipped", "Flutterwave not configured", None
    payout = float(Decimal(order["payout_amount"]))
    name = order["recipient_name"]
    if order["method"] == "mobile_money":
        payload = {"account_bank": order["country_code"], "account_number": order["phone"],
                   "amount": payout, "currency": order["currency"],
                   "narration": f"KudiArc remittance to {name}", "reference": ref,
                   "beneficiary_name": name, "meta": {"mobile_number": order["phone"]}}
    else:
        payload = {"account_bank": order["bank_code"], "account_number": order["account_number"],
                   "amount": payout, "currency": order["currency"],
                   "narration": f"KudiArc remittance to {name}", "reference": ref,
                   "beneficiary_name": name}
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    status, body, err = _post(f"{FLW_BASE}/transfers", payload, headers)
    if err:
        return err, "Flutterwave unreachable" if err == "rejected" else "Flutterwave timeout", None
    return _result(status, body,
                   lambda s, b: s in (200, 201) and (b or {}).get("status") == "success",
                   ref, "Flutterwave")


def _bitnob(order, ref, keys):
    secret = keys.get("bitnob")
    if not _configured(secret) or order["country_code"] not in BITNOB_COUNTRIES:
        return "skipped", "Bitnob not available for this corridor", None
    pref = f"{ref}-BNB"
    minor = int(Decimal(order["payout_amount"]) * 100)
    payload = {"customerEmail": f"{order['wallet'][:8]}@kudiarc.app", "amount": minor,
               "currency": order["currency"], "reference": pref, "bankCode": order["bank_code"],
               "bankAccountNumber": order["account_number"], "bankAccountName": order["recipient_name"],
               "narration": "KudiArc remittance"}
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    base = keys.get("bitnob_base", "https://sandboxapi.bitnob.co/api/v1")
    status, body, err = _post(f"{base}/offramps/initiate", payload, headers)
    if err:
        return err, "Bitnob unreachable" if err == "rejected" else "Bitnob timeout", None
    return _result(status, body, lambda s, b: s == 200 and bool((b or {}).get("status")), pref, "Bitnob")


def _paystack(order, ref, keys):
    secret = keys.get("paystack")
    if not _configured(secret) or order["country_code"] not in PAYSTACK_COUNTRIES:
        return "skipped", "Paystack not available for this corridor", None
    pref = f"{ref}-PSK"
    minor = int(Decimal(order["payout_amount"]) * 100)
    payload = {"source": "balance", "amount": minor, "currency": order["currency"],
               "recipient": order["account_number"],
               "reason": f"KudiArc remittance to {order['recipient_name']}", "reference": pref}
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    status, body, err = _post(f"{PSK_BASE}/transfer", payload, headers)
    if err:
        return err, "Paystack unreachable" if err == "rejected" else "Paystack timeout", None
    return _result(status, body, lambda s, b: s == 200 and bool((b or {}).get("status")), pref, "Paystack")


def dispatch(order, ref, keys):
    """Try providers in order. Stops at the first ok, or at the first unknown outcome."""
    last = "No payout provider available for this corridor"
    for label, fn in (("Flutterwave", _flutterwave), ("Bitnob", _bitnob), ("Paystack", _paystack)):
        state, msg, pref = fn(order, ref, keys)
        if state == "ok":
            return "ok", msg, label, pref
        if state == "unknown":
            log.error(f"{label} outcome unknown for {ref}: {msg}")
            return "unknown", msg, label, None
        if state == "rejected":
            log.warning(f"{label} rejected {ref}: {msg}")
            last = msg
    return "rejected", last, None, None


# ── Re-check a payout with the provider itself ─────────────────
def _get(url, headers):
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        log.warning(f"provider lookup failed: {e}")
        return None, None
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, None


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def verify(provider, ref, keys, order=None, provider_id=None):
    """Ask the provider what really happened to a transfer.
    Returns (state, detail): completed | failed | pending | unverifiable | error | mismatch"""
    if provider == "flutterwave":
        secret = keys.get("flutterwave")
        if not _configured(secret) or not provider_id:
            return "error", "cannot look up transfer"
        status, body = _get(f"{FLW_BASE}/transfers/{provider_id}", {"Authorization": f"Bearer {secret}"})
        if status != 200 or not isinstance(body, dict) or body.get("status") != "success":
            return "error", "provider lookup failed"
        d = body.get("data") or {}
        if d.get("reference") != ref:
            return "mismatch", "reference differs"
        if order and (_dec(d.get("amount")) != _dec(order["payout_amount"]) or d.get("currency") != order["currency"]):
            return "mismatch", "amount or currency differs"
        st = str(d.get("status", "")).upper()
        return {"SUCCESSFUL": "completed", "FAILED": "failed"}.get(st, "pending"), st
    if provider == "paystack":
        secret = keys.get("paystack")
        if not _configured(secret):
            return "error", "cannot look up transfer"
        status, body = _get(f"{PSK_BASE}/transfer/verify/{ref}", {"Authorization": f"Bearer {secret}"})
        if status != 200 or not isinstance(body, dict) or not body.get("status"):
            return "error", "provider lookup failed"
        d = body.get("data") or {}
        if d.get("reference") != ref:
            return "mismatch", "reference differs"
        if order and _dec(d.get("amount")) != _dec(order["payout_amount"]) * 100:
            return "mismatch", "amount differs"
        st = str(d.get("status", "")).lower()
        return {"success": "completed", "failed": "failed", "reversed": "failed"}.get(st, "pending"), st
    return "unverifiable", "no status endpoint available"
