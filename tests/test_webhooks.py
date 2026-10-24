import hashlib, hmac, json
import pytest
import db, payouts


class _Resp:
    def __init__(self, code, body): self.status_code, self._b = code, body
    def json(self): return self._b


@pytest.fixture
def live(make_env, monkeypatch):
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: ("ok", "x", "Flutterwave", "R"))
    return make_env(mode="live", keys={"flutterwave": "sk"})


def pending_order(e, amount="20"):
    q = e.quote(amount=amount)
    e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address))
    o = db.get_order(q["quote_id"])
    assert o["status"] == "payout_pending"
    return o


def flw(e, o, status="SUCCESSFUL", sig="flwhash", ref=None, pid=555):
    body = {"event": "transfer.completed", "data": {"id": pid, "reference": ref or o["provider_ref"], "status": status}}
    h = {"verif-hash": sig} if sig is not None else {}
    return e.client.post("/api/send/flw-webhook", data=json.dumps(body), headers=h, content_type="application/json")


def provider_says(monkeypatch, o, status, amount=None, currency=None, ref=None, calls=None):
    def get(url, **k):
        if calls is not None: calls.append(url)
        return _Resp(200, {"status": "success", "data": {
            "reference": ref or o["provider_ref"], "status": status,
            "amount": float(o["payout_amount"]) if amount is None else amount,
            "currency": currency or o["currency"]}})
    monkeypatch.setattr(payouts.requests, "get", get)


def status(o): return db.get_order(o["quote_id"])["status"]


# ── fail closed when not configured ──────────────────────
@pytest.mark.parametrize("val", [None, "", "mock", "  "])
def test_unconfigured_secrets_reject_everything(live, val):
    live.wh_secrets["flutterwave"] = val; live.wh_secrets["bitnob"] = val
    live.wh_keys["paystack"] = val
    o = pending_order(live)
    assert flw(live, o, sig="").status_code == 503          # empty header must NOT match an empty secret
    assert flw(live, o, sig="anything").status_code == 503
    sig = hmac.new(b"", b"{}", hashlib.sha512).hexdigest()  # signature made with an empty key
    assert live.client.post("/api/send/paystack-webhook", data=b"{}", headers={"x-paystack-signature": sig}).status_code == 503
    assert live.client.post("/api/send/webhook", data=b"{}", headers={"x-bitnob-signature": sig}).status_code == 503
    assert status(o) == "payout_pending"


# ── Flutterwave ──────────────────────────────────────────
def test_flw_rejects_missing_or_wrong_hash(live):
    o = pending_order(live)
    assert flw(live, o, sig=None).status_code == 401
    assert flw(live, o, sig="wrong").status_code == 401
    assert status(o) == "payout_pending"


def test_flw_success_verified_with_provider(live, monkeypatch):
    o = pending_order(live); calls = []
    provider_says(monkeypatch, o, "SUCCESSFUL", calls=calls)
    assert flw(live, o).status_code == 200
    assert status(o) == "completed" and calls and calls[0].endswith("/transfers/555")


def test_flw_failure_verified_requires_refund(live, monkeypatch):
    o = pending_order(live); provider_says(monkeypatch, o, "FAILED")
    flw(live, o, status="FAILED")
    assert status(o) == "refund_required"


def test_webhook_lie_is_overruled_by_provider(live, monkeypatch):
    o = pending_order(live); provider_says(monkeypatch, o, "FAILED")
    flw(live, o, status="SUCCESSFUL")                       # webhook claims success, provider says failed
    assert status(o) == "refund_required"


def test_provider_still_pending_changes_nothing(live, monkeypatch):
    o = pending_order(live); provider_says(monkeypatch, o, "PENDING")
    flw(live, o, status="SUCCESSFUL")
    assert status(o) == "payout_pending"


def test_non_final_webhook_is_ignored_without_lookup(live, monkeypatch):
    o = pending_order(live); calls = []; provider_says(monkeypatch, o, "SUCCESSFUL", calls=calls)
    for st in ("NEW", "PENDING", "", "weird"):
        assert flw(live, o, status=st).status_code == 200
    assert status(o) == "payout_pending" and not calls      # never treated as failure, never even looked up


@pytest.mark.parametrize("kw", [{"amount": 1.0}, {"currency": "USD"}, {"ref": "KUDI-OTHER"}])
def test_amount_currency_or_reference_mismatch_ignored(live, monkeypatch, kw):
    o = pending_order(live); provider_says(monkeypatch, o, "SUCCESSFUL", **kw)
    assert flw(live, o).status_code == 200
    assert status(o) == "payout_pending"


def test_provider_outage_asks_for_retry_and_changes_nothing(live, monkeypatch):
    o = pending_order(live)
    def boom(*a, **k): raise ConnectionError("down")
    monkeypatch.setattr(payouts.requests, "get", boom)
    assert flw(live, o).status_code == 503 and status(o) == "payout_pending"


def test_unknown_reference_is_harmless(live, monkeypatch):
    o = pending_order(live)
    monkeypatch.setattr(payouts.requests, "get", lambda *a, **k: _Resp(200, {"status": "success", "data": {"reference": "KUDI-NONE", "status": "SUCCESSFUL"}}))
    assert flw(live, o, ref="KUDI-NONE").status_code == 200 and status(o) == "payout_pending"


def test_finished_order_cannot_be_flipped_by_a_later_webhook(live, monkeypatch):
    o = pending_order(live)
    provider_says(monkeypatch, o, "SUCCESSFUL"); flw(live, o)
    provider_says(monkeypatch, o, "FAILED"); flw(live, o, status="FAILED")
    assert status(o) == "completed"


def test_stuck_unknown_payout_resolved_by_late_webhook(live, monkeypatch):
    o = pending_order(live); db.update_order(o["quote_id"], status="payout_unknown")
    provider_says(monkeypatch, o, "SUCCESSFUL"); flw(live, o)
    assert status(o) == "completed"


def test_legacy_transfer_without_order_still_updates_history(live, monkeypatch):
    db.save_send("0xabc", 5, 7500, "Old Customer", "GTB", "0123456789", "", "LEGACY-REF-1", "pending")
    monkeypatch.setattr(payouts.requests, "get", lambda *a, **k: _Resp(200, {"status": "success", "data": {
        "reference": "LEGACY-REF-1", "status": "SUCCESSFUL"}}))
    assert flw(live, {"provider_ref": "LEGACY-REF-1"}, ref="LEGACY-REF-1").status_code == 200
    import sqlite3
    c = sqlite3.connect(db.DB_PATH)
    assert c.execute("SELECT status FROM transactions WHERE bitnob_ref='LEGACY-REF-1'").fetchone()[0] == "completed"


# ── Paystack ─────────────────────────────────────────────
def psk(e, o, event="transfer.success", key="sk_psk", suffix="-PSK"):
    body = json.dumps({"event": event, "data": {"reference": o["provider_ref"] + suffix}}).encode()
    sig = hmac.new(key.encode(), body, hashlib.sha512).hexdigest()
    return e.client.post("/api/send/paystack-webhook", data=body, headers={"x-paystack-signature": sig}, content_type="application/json")


def psk_provider(monkeypatch, o, st, suffix="-PSK"):
    monkeypatch.setattr(payouts.requests, "get", lambda url, **k: _Resp(200, {"status": True, "data": {
        "reference": o["provider_ref"] + suffix, "status": st, "amount": float(o["payout_amount"]) * 100}}))


def test_paystack_bad_signature_rejected(live):
    o = pending_order(live)
    assert psk(live, o, key="not-the-key").status_code == 401 and status(o) == "payout_pending"


def test_paystack_success_and_failure_paths(live, monkeypatch):
    o = pending_order(live); psk_provider(monkeypatch, o, "success"); psk(live, o)
    assert status(o) == "completed"
    for event, st in (("transfer.failed", "failed"), ("transfer.reversed", "reversed")):
        o2 = pending_order(live); psk_provider(monkeypatch, o2, st); psk(live, o2, event=event)
        assert status(o2) == "refund_required"


def test_paystack_wrong_amount_ignored(live, monkeypatch):
    o = pending_order(live)
    monkeypatch.setattr(payouts.requests, "get", lambda url, **k: _Resp(200, {"status": True, "data": {
        "reference": o["provider_ref"] + "-PSK", "status": "success", "amount": 100}}))
    psk(live, o)
    assert status(o) == "payout_pending"


# ── Bitnob ───────────────────────────────────────────────
def bnb(e, o, st="success", sig=None, secret="bnbsecret"):
    body = json.dumps({"reference": o["provider_ref"] + "-BNB", "status": st}).encode()
    sig = sig if sig is not None else hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return e.client.post("/api/send/webhook", data=body, headers={"x-bitnob-signature": sig}, content_type="application/json")


def test_bitnob_rejects_bad_and_old_style_signatures(live):
    o = pending_order(live)
    assert bnb(live, o, sig="wrong").status_code == 401
    assert bnb(live, o, sig="bnbsecret").status_code == 401        # the old "header equals secret" scheme
    assert bnb(live, o, secret="other").status_code == 401
    assert bnb(live, o, sig="").status_code == 401
    assert status(o) == "payout_pending"


def test_bitnob_signed_results_apply(live):
    o = pending_order(live); assert bnb(live, o).status_code == 200 and status(o) == "completed"
    o2 = pending_order(live); bnb(live, o2, st="failed"); assert status(o2) == "refund_required"


def test_bitnob_non_final_status_is_not_a_failure(live):
    o = pending_order(live)
    for st in ("pending", "processing", "", "queued"):
        assert bnb(live, o, st=st).status_code == 200
    assert status(o) == "payout_pending"
