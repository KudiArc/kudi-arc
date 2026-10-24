import json, sqlite3, time
import pytest
from eth_account import Account

import db, adminauth
from adminauth import AdminAuth
from flask import Flask
from conftest import ESCROW


def order_of(q):
    return db.get_order(q["quote_id"])


# ── authentication ───────────────────────────────────────
def test_signed_request_succeeds(make_env):
    e = make_env()
    assert e.admin("GET", "/api/test/echo").status_code == 200
    assert e.admin("POST", "/api/test/echo", {"a": 1}).status_code == 200


def test_missing_headers_rejected(make_env):
    e = make_env()
    assert e.client.get("/api/test/echo").status_code == 401
    assert e.client.get("/api/test/echo", headers={"X-Admin-Nonce": "x", "X-Admin-Signature": "y"}).status_code == 401


def test_nonce_cannot_be_replayed(make_env):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo")
    assert e.client.get("/api/test/echo", headers=h).status_code == 200
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_signature_from_non_owner_rejected(make_env):
    e = make_env()
    r = e.client.get("/api/test/echo", headers=e.admin_headers("GET", "/api/test/echo", signer=Account.create()))
    assert r.status_code == 401


def test_wrong_signer_does_not_burn_the_nonce(make_env):
    e = make_env()
    ch = e.client.get("/api/admin/challenge").get_json()
    bad = e.client.get("/api/test/echo", headers={"X-Admin-Nonce": ch["nonce"], "X-Admin-Signature": "0x" + "11" * 65})
    assert bad.status_code == 401
    assert db.get_admin_nonce(ch["nonce"])["used"] == 0          # a stranger can't use up the owner's nonce


def test_expired_nonce_rejected(make_env):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo")
    c = sqlite3.connect(db.DB_PATH); c.execute("UPDATE admin_nonces SET expires_at=1"); c.commit(); c.close()
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_expired_nonce_rejected_even_with_valid_signature(make_env):
    e = make_env()
    ch = e.client.get("/api/admin/challenge").get_json()
    past = int(time.time()) - 5
    c = sqlite3.connect(db.DB_PATH); c.execute("UPDATE admin_nonces SET expires_at=?", (past,)); c.commit(); c.close()
    msg = adminauth.build_message(ch["domain"], ch["chain_id"], "GET", "/api/test/echo",
                                  __import__("hashlib").sha256(b"").hexdigest(), ch["nonce"], past)
    h = {"X-Admin-Nonce": ch["nonce"], "X-Admin-Signature": e.sign(e.owner, msg)}   # signature itself is valid
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_signature_bound_to_path(make_env):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo", sign_path="/api/admin/send/orders")
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_signature_bound_to_method(make_env):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo", sign_method="POST")
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_signature_bound_to_body(make_env):
    e = make_env()
    h = e.admin_headers("POST", "/api/test/echo", b'{"outcome":"paid"}')
    r = e.client.post("/api/test/echo", data=b'{"outcome":"failed"}', headers=h, content_type="application/json")
    assert r.status_code == 401


def test_signature_bound_to_query_string(make_env):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo?x=1")
    assert e.client.get("/api/test/echo?x=2", headers=h).status_code == 401
    assert e.client.get("/api/test/echo?x=1", headers=e.admin_headers("GET", "/api/test/echo?x=1")).status_code == 200


def test_nonce_consume_atomic_under_race(make_env, monkeypatch):
    e = make_env()
    h = e.admin_headers("GET", "/api/test/echo")
    stale = db.get_admin_nonce(h["X-Admin-Nonce"])
    assert e.client.get("/api/test/echo", headers=h).status_code == 200
    monkeypatch.setattr(db, "get_admin_nonce", lambda n: stale)  # second request passed the 'unused' check
    assert e.client.get("/api/test/echo", headers=h).status_code == 401


def test_challenge_flood_is_capped(make_env):
    e = make_env()
    for _ in range(adminauth.MAX_OPEN_NONCES):
        assert e.client.get("/api/admin/challenge").status_code == 200
    assert e.client.get("/api/admin/challenge").status_code == 429


@pytest.mark.parametrize("owner", [None, "", "not-an-address"])
def test_fails_closed_when_owner_not_configured(owner):
    auth = AdminAuth(owner, 5042002)
    app = Flask(__name__)
    app.add_url_rule("/c", "c", lambda: auth.challenge())
    app.add_url_rule("/x", "x", auth.required(lambda: {"ok": True}))
    c = app.test_client()
    assert c.get("/c").status_code == 503 and c.get("/x").status_code == 503
    assert c.get("/x", headers={"X-Admin-Nonce": "a", "X-Admin-Signature": "b"}).status_code == 503


def test_app_has_no_default_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "boot2.db"))
    monkeypatch.delenv("OWNER_ADDRESS", raising=False)
    import importlib, app as appmod
    appmod = importlib.reload(appmod)
    assert appmod.OWNER_ADDRESS == "" and not appmod.admin_auth.enabled
    assert appmod.app.test_client().get("/api/admin/challenge").status_code == 503


def test_every_mutating_admin_route_in_app_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "boot.db"))
    monkeypatch.setenv("OWNER_ADDRESS", Account.create().address)
    import importlib, app as appmod
    appmod = importlib.reload(appmod)
    open_routes = []
    for rule in appmod.app.url_map.iter_rules():
        if rule.rule.startswith("/api/admin/") and "POST" in rule.methods:
            fn = appmod.app.view_functions[rule.endpoint]
            if not hasattr(fn, "__wrapped__"):
                open_routes.append(rule.rule)
    assert not open_routes, f"unauthenticated admin routes: {open_routes}"
    assert appmod.app.config.get("MAX_CONTENT_LENGTH"), "request bodies must be size-capped"
    c = appmod.app.test_client()
    for path in ("/api/admin/maintenance", "/api/admin/recent-txs", "/api/admin/send-settings",
                 "/api/admin/refresh-rates", "/api/admin/send/resolve", "/api/admin/send/chain-sync"):
        assert c.post(path, json={"maintenance": True, "wallet": "0x1", "signature": "x", "message": "y"}).status_code == 401, path
    assert c.get("/api/admin/send/orders").status_code == 401


# ── admin send endpoints ─────────────────────────────────
def _confirmed(e, amount="20", **over):
    q = e.quote(amount=amount, **over)
    e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address))
    return q


def test_orders_list_and_action_hints(make_env):
    e = make_env()
    q = _confirmed(e)
    db.update_order(q["quote_id"], status="completed")
    r = e.admin("GET", "/api/admin/send/orders?status=completed")
    o = r.get_json()["orders"][0]
    assert r.status_code == 200 and o["quote_id"] == q["quote_id"] and o["action"] == "settle"
    assert o["recipient_account_last4"] == "6789" and "account_number" not in o and len(o["ref"]) == 66


def test_orders_filters_and_validation(make_env):
    e = make_env(); _confirmed(e)
    assert e.admin("GET", "/api/admin/send/orders?status=refund_required").get_json()["orders"] == []
    assert e.admin("GET", "/api/admin/send/orders?chain_state=bogus").status_code == 400
    assert e.admin("GET", "/api/admin/send/orders?limit=abc").status_code == 400


def test_orders_endpoint_requires_owner(make_env):
    e = make_env()
    assert e.client.get("/api/admin/send/orders").status_code == 401
    assert e.admin("GET", "/api/admin/send/orders", signer=e.user).status_code == 401


def test_resolve_unknown_payout(make_env):
    e = make_env()
    q = _confirmed(e)
    db.update_order(q["quote_id"], status="payout_unknown")
    assert e.admin("POST", "/api/admin/send/resolve", {"quote_id": q["quote_id"], "outcome": "failed"}).get_json()["status"] == "refund_required"
    assert e.admin("POST", "/api/admin/send/resolve", {"quote_id": q["quote_id"], "outcome": "paid"}).status_code == 409   # already resolved


def test_resolve_validation(make_env):
    e = make_env(); q = _confirmed(e)
    assert e.admin("POST", "/api/admin/send/resolve", {"quote_id": q["quote_id"], "outcome": "maybe"}).status_code == 400
    assert e.admin("POST", "/api/admin/send/resolve", {"quote_id": "zz", "outcome": "paid"}).status_code == 400
    assert e.admin("POST", "/api/admin/send/resolve", {"quote_id": q["quote_id"], "outcome": "paid"}).status_code == 409   # completed already


def test_chain_sync_marks_settled_and_refunded(make_env):
    e = make_env()
    q1, q2, q3 = _confirmed(e), _confirmed(e), _confirmed(e)
    db.update_order(q2["quote_id"], status="refund_required")
    db.update_order(q3["quote_id"], status="payout_pending")
    e.chain.deposits[q1["ref"]] = e.chain.deposits[q1["ref"]][:4] + (2,)      # owner settled q1
    e.chain.deposits[q2["ref"]] = e.chain.deposits[q2["ref"]][:4] + (3,)      # owner refunded q2
    e.chain.deposits[q3["ref"]] = ("0x" + "0" * 40, "0x" + "0" * 40, 0, 0, 0)  # chain has nothing for q3
    r = e.admin("POST", "/api/admin/send/chain-sync", {}).get_json()
    assert (r["settled"], r["refunded"]) == (1, 1) and r["anomalies"][0]["quote_id"] == q3["quote_id"]
    assert order_of(q1)["chain_state"] == "settled"
    assert order_of(q2)["chain_state"] == "refunded" and order_of(q2)["status"] == "refunded"
    assert order_of(q3)["chain_state"] == "none"
    again = e.admin("POST", "/api/admin/send/chain-sync", {}).get_json()
    assert (again["settled"], again["refunded"]) == (0, 0)             # idempotent


def test_chain_sync_fails_closed_on_rpc_error(make_env):
    e = make_env(); _confirmed(e)
    e.chain.deposits = None                       # any lookup now raises
    assert e.admin("POST", "/api/admin/send/chain-sync", {}).status_code == 503


def test_send_fee_recorded_in_history(make_env):
    e = make_env(); q = _confirmed(e)
    c = sqlite3.connect(db.DB_PATH)
    fee = c.execute("SELECT fee FROM transactions WHERE tx_hash=?", (order_of(q)["tx_hash"],)).fetchone()[0]
    c.close()
    assert abs(fee - 0.16) < 1e-9
