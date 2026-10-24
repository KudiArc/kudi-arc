import sqlite3, time
from eth_account import Account
import db


def _order_of(q):
    return db.get_order(q["quote_id"])


def _recon(e):
    r = e.admin("POST", "/api/admin/send/reconcile", {})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_requires_owner_signature(make_env):
    e = make_env()
    assert e.client.post("/api/admin/send/reconcile", json={}).status_code == 401
    assert e.admin("POST", "/api/admin/send/reconcile", {}, signer=e.user).status_code == 401


def test_recovers_deposit_that_was_never_confirmed(make_env):
    e = make_env()
    q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address)             # user paid, then closed the tab
    assert _order_of(q)["status"] == "quoted"
    out = _recon(e)
    assert out["checked"] == 1 and out["recovered"][0]["tx_hash"] == tx and out["recovered"][0]["result"] == "completed"
    o = _order_of(q)
    assert o["status"] == "completed" and o["tx_hash"] == tx


def test_idempotent_and_pays_once(make_env, monkeypatch):
    import payouts
    calls = []
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: (calls.append(1), ("ok", "x", "Flutterwave", "R"))[1])
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote(); e.chain.add_deposit(q, e.user.address)
    _recon(e); out2 = _recon(e)
    assert len(calls) == 1 and out2["checked"] == 0


def test_ignores_orders_without_a_deposit(make_env):
    e = make_env(); q = e.quote()
    out = _recon(e)
    assert out["checked"] == 0 and _order_of(q)["status"] == "quoted"


def test_deposit_without_findable_tx_is_reported_not_guessed(make_env):
    e = make_env(); q = e.quote()
    e.chain.add_deposit(q, e.user.address); e.chain.logs.clear()
    out = _recon(e)
    assert out["not_found"] == [q["quote_id"]] and _order_of(q)["status"] == "quoted"


def test_old_orders_are_skipped(make_env):
    e = make_env(); q = e.quote(); e.chain.add_deposit(q, e.user.address)
    c = sqlite3.connect(db.DB_PATH); c.execute("UPDATE send_orders SET created_at=?", (int(time.time()) - 8 * 86400,)); c.commit(); c.close()
    assert _recon(e)["checked"] == 0


def test_late_deposit_goes_to_refund(make_env):
    e = make_env(); q = e.quote()
    e.chain.add_deposit(q, e.user.address, at=q["expires_at"] + 10)
    out = _recon(e)
    assert out["recovered"][0]["result"] == "refund_required" and _order_of(q)["status"] == "refund_required"


def test_wrong_wallet_deposit_is_not_paid(make_env):
    e = make_env(); q = e.quote()
    e.chain.add_deposit(q, Account.create().address)
    out = _recon(e)
    assert out["recovered"][0]["result"] != "completed" and _order_of(q)["status"] == "quoted"


def test_fails_closed_on_rpc_error(make_env):
    e = make_env(); q = e.quote(); e.chain.add_deposit(q, e.user.address)
    e.chain.deposits = None
    assert e.admin("POST", "/api/admin/send/reconcile", {}).status_code == 503
