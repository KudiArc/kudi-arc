import sqlite3, threading, time
import pytest
import requests
from eth_account import Account

import db, kudisend, payouts
from conftest import ESCROW, USDC, EURC


def order_of(q):
    return db.get_order(q["quote_id"])


# ── challenge ────────────────────────────────────────────
def test_challenge_rejects_bad_wallet(make_env):
    e = make_env()
    assert e.client.post("/api/send/challenge", json={"wallet": "nope"}).status_code == 400


def test_challenge_open_cap(make_env):
    e = make_env()
    for _ in range(kudisend.MAX_OPEN_CHALLENGES):
        assert e.client.post("/api/send/challenge", json={"wallet": e.user.address}).status_code == 200
    assert e.client.post("/api/send/challenge", json={"wallet": e.user.address}).status_code == 429


# ── quote: happy path + pricing ──────────────────────────
def test_quote_pricing_is_exact_decimal(make_env):
    e = make_env()
    q = e.quote()                    # 20 USDC to NG, fee 0.8%, rate 1500
    assert q["fee"] == "0.16" and q["payout_amount"] == "29760.00"
    assert q["amount_base"] == "20000000" and q["currency"] == "NGN"
    assert q["escrow_address"] == ESCROW and q["expires_in"] == 600
    o = order_of(q)
    assert o["status"] == "quoted" and o["wallet"] == e.user.address.lower()
    assert o["ref"] == q["ref"] and len(o["ref"]) == 66


def test_quote_rounds_payout_down(make_env):
    e = make_env()
    # unrounded payout is 14880.0060; rounding half-up would pay 14880.01
    assert e.quote(amount="10.000004")["payout_amount"] == "14880.00"


def test_quote_eurc_converted_to_usd(make_env):
    e = make_env()
    q = e.quote(token="EURC", amount="20")   # (20-0.16) * 1.1 * 1500
    assert q["token_address"].lower() == EURC.lower() and q["payout_amount"] == "32736.00"


def test_quote_mobile_money(make_env):
    e = make_env()
    e.quote(country_code="KE", method="mobile_money", phone="+254700000000", account_number="", bank_code="")


# ── quote: abuse ─────────────────────────────────────────
def test_quote_bad_signature_wrong_signer(make_env):
    e = make_env()
    other = Account.create()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    r = e.client.post("/api/send/quote", json={
        "wallet": e.user.address, "nonce": ch["nonce"], "signature": e.sign(other, ch["message"]),
        "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
        "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"})
    assert r.status_code == 401


def test_quote_challenge_single_use(make_env):
    e = make_env()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    body = {"wallet": e.user.address, "nonce": ch["nonce"], "signature": e.sign(e.user, ch["message"]),
            "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
            "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"}
    assert e.client.post("/api/send/quote", json=body).status_code == 200
    assert e.client.post("/api/send/quote", json=body).status_code == 401   # replay


def test_challenge_consume_is_atomic_under_race(make_env, monkeypatch):
    e = make_env()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    stale = db.get_challenge(ch["nonce"])            # what a racing request would still see
    body = {"wallet": e.user.address, "nonce": ch["nonce"], "signature": e.sign(e.user, ch["message"]),
            "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
            "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"}
    assert e.client.post("/api/send/quote", json=body).status_code == 200
    monkeypatch.setattr(db, "get_challenge", lambda n: stale)   # second request slipped past the check
    assert e.client.post("/api/send/quote", json=body).status_code == 401


def test_quote_challenge_bound_to_wallet(make_env):
    e = make_env()
    thief = Account.create()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    r = e.client.post("/api/send/quote", json={
        "wallet": thief.address, "nonce": ch["nonce"], "signature": e.sign(thief, ch["message"]),
        "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
        "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"})
    assert r.status_code == 401


def test_quote_expired_challenge(make_env):
    e = make_env()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    c = sqlite3.connect(db.DB_PATH); c.execute("UPDATE send_challenges SET expires_at=1"); c.commit(); c.close()
    r = e.client.post("/api/send/quote", json={
        "wallet": e.user.address, "nonce": ch["nonce"], "signature": e.sign(e.user, ch["message"]),
        "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
        "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"})
    assert r.status_code == 401


@pytest.mark.parametrize("over,code", [
    ({"amount": "9.99"}, "amount_out_of_range"),     # contract min is 10
    ({"amount": "50.000001"}, "amount_out_of_range"),
    ({"amount": "20.1234567"}, "bad_amount"),        # more than 6 dp
    ({"amount": "-5"}, "bad_amount"), ({"amount": "abc"}, "bad_amount"),
    ({"amount": "1e400"}, "bad_amount"), ({"amount": "NaN"}, "bad_amount"),
    ({"token": "DOGE"}, "bad_token"), ({"country_code": "ZZ"}, "bad_country"),
    ({"recipient_name": ""}, "bad_recipient"), ({"account_number": "12ab"}, "bad_recipient"),
    ({"bank_code": "../x"}, "bad_recipient"), ({"method": "cash"}, "bad_method"),
])
def test_quote_validation(make_env, over, code):
    e = make_env()
    r = e.quote(expect=400, **over)
    assert r["code"] == code


def test_invalid_input_does_not_burn_challenge(make_env):
    e = make_env()
    ch = e.client.post("/api/send/challenge", json={"wallet": e.user.address}).get_json()
    body = {"wallet": e.user.address, "nonce": ch["nonce"], "signature": e.sign(e.user, ch["message"]),
            "token": "USDC", "amount": "9", "country_code": "NG", "method": "bank",
            "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058"}
    assert e.client.post("/api/send/quote", json=body).status_code == 400
    body["amount"] = "20"
    assert e.client.post("/api/send/quote", json=body).status_code == 200


def test_quote_blocked_when_maintenance_or_unconfigured(make_env):
    assert make_env(maintenance=True).quote(expect=503)["code"] == "maintenance"
    assert make_env(escrow="")                   .quote(expect=503)["code"] == "escrow_not_configured"


def test_live_mode_without_provider_keys_refuses(make_env):
    e = make_env(mode="live", keys={"flutterwave": "mock"})
    assert e.quote(expect=503)["code"] == "payouts_not_configured"


# ── mock-mode safety ─────────────────────────────────────
@pytest.mark.parametrize("val,expected", [("live", "live"), (" LIVE ", "live"), ("", "mock"),
                                          ("true", "mock"), ("yes", "mock"), ("mock", "mock")])
def test_send_mode_defaults_to_safe(monkeypatch, val, expected):
    monkeypatch.setenv("SEND_MODE", val)
    monkeypatch.setenv("FLUTTERWAVE_SECRET_KEY", "real-looking-key")   # a real key must not enable live
    assert kudisend.load_config()["mode"] == expected


def test_real_provider_key_never_pays_in_mock_mode(make_env, monkeypatch):
    called = []
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: called.append(1))
    e = make_env(mode="mock", keys={"flutterwave": "sk_live_real"})
    q = e.quote()
    r = e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address))
    assert r.get_json()["status"] == "completed" and not called


# ── confirm: happy path + idempotency ────────────────────
def test_confirm_happy_path_mock(make_env):
    e = make_env()
    q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address)
    r = e.confirm(q["quote_id"], tx)
    j = r.get_json()
    assert r.status_code == 200 and j["status"] == "completed" and j["tx_hash"] == tx
    assert j["recipient_account_last4"] == "6789" and "account_number" not in j
    assert db.get_history(e.user.address)[0]["tx_hash"] == tx
    r2 = e.confirm(q["quote_id"], tx)                       # safe to call again
    assert r2.status_code == 200 and r2.get_json()["status"] == "completed"
    assert e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address)).status_code == 409


def test_confirm_pending_when_tx_not_found(make_env):
    e = make_env()
    q = e.quote()
    r = e.confirm(q["quote_id"], "0x" + "ab" * 32)
    assert r.status_code == 202 and order_of(q)["status"] == "quoted"


# ── confirm: every way to cheat ──────────────────────────
def _expect_invalid(e, q, tx):
    r = e.confirm(q["quote_id"], tx)
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_deposit", r.get_json()
    assert order_of(q)["status"] == "quoted"             # order stays usable


def test_confirm_rejects_failed_tx(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, e.user.address, status=0))


def test_confirm_rejects_wrong_contract(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, e.user.address, to="0x" + "11" * 20))


def test_confirm_rejects_wrong_amount(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, e.user.address, amount=10_000_000))


def test_confirm_rejects_other_wallet(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, Account.create().address))


def test_confirm_rejects_wrong_token(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, e.user.address, token=EURC))


def test_confirm_rejects_deposit_for_another_order(make_env):
    e = make_env(); q1, q2 = e.quote(), e.quote()
    tx_for_1 = e.chain.add_deposit(q1, e.user.address)
    _expect_invalid(e, q2, tx_for_1)                      # tx proves q1, not q2


def test_confirm_rejects_event_for_other_ref_even_if_state_looks_active(make_env):
    e = make_env(); q1, q2 = e.quote(), e.quote()
    tx = e.chain.add_deposit(q2, e.user.address, event_ref=q1["ref"])   # event says q1, state says q2
    _expect_invalid(e, q2, tx)


def test_confirm_rejects_inactive_deposit(make_env):
    e = make_env(); q = e.quote()
    _expect_invalid(e, q, e.chain.add_deposit(q, e.user.address, state=2))   # already settled


def test_confirm_rejects_malformed_input(make_env):
    e = make_env(); q = e.quote()
    assert e.confirm("zz", "0x" + "ab" * 32).status_code == 400
    assert e.confirm(q["quote_id"], "0x12").status_code == 400
    assert e.confirm("0" * 32, "0x" + "ab" * 32).status_code == 404


def test_same_tx_cannot_pay_two_orders(make_env):
    e = make_env(); q1, q2 = e.quote(), e.quote()
    tx = e.chain.add_deposit(q1, e.user.address)
    assert e.confirm(q1["quote_id"], tx).status_code == 200
    # even a forged deposits entry for q2 can't reuse the same tx hash
    e.chain.deposits[q2["ref"]] = (e.user.address, q2["token_address"], 20_000_000, int(time.time()), 1)
    e.chain.receipts[tx]["logs"].append({
        "address": ESCROW, "topics": [kudisend.DEPOSITED_TOPIC, q2["ref"],
                                       "0x" + "0" * 24 + e.user.address[2:].lower(),
                                       "0x" + "0" * 24 + q2["token_address"][2:].lower()],
        "data": "0x" + format(20_000_000, "064x")})
    r = e.confirm(q2["quote_id"], tx)
    assert order_of(q2)["status"] != "completed", r.get_json()


def test_chain_mismatch_blocks_confirm(make_env):
    e = make_env(); q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address)
    e.chain.chain_id = 1
    assert e.confirm(q["quote_id"], tx).status_code == 503


# ── timing ───────────────────────────────────────────────
def test_late_deposit_goes_to_refund_not_payout(make_env, monkeypatch):
    called = []
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: called.append(1))
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address, at=q["expires_at"] + 5)
    j = e.confirm(q["quote_id"], tx).get_json()
    assert j["status"] == "refund_required" and not called


def test_stale_confirm_goes_to_refund(make_env):
    e = make_env(); q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address, at=int(time.time()) - 9000)
    c = sqlite3.connect(db.DB_PATH)
    c.execute("UPDATE send_orders SET expires_at=?", (int(time.time()) - 7200,)); c.commit(); c.close()
    assert e.confirm(q["quote_id"], tx).get_json()["status"] == "refund_required"


def test_in_time_deposit_confirmed_slightly_late_still_pays(make_env):
    e = make_env(); q = e.quote()
    tx = e.chain.add_deposit(q, e.user.address, at=int(time.time()) - 100)
    c = sqlite3.connect(db.DB_PATH)
    c.execute("UPDATE send_orders SET expires_at=?", (int(time.time()) - 60,)); c.commit(); c.close()
    assert e.confirm(q["quote_id"], tx).get_json()["status"] == "completed"


# ── live mode outcomes ───────────────────────────────────
@pytest.mark.parametrize("result,status", [
    (("ok", "x", "Flutterwave", "REF"), "payout_pending"),
    (("rejected", "bad account", None, None), "refund_required"),
    (("unknown", "timeout", "Flutterwave", None), "payout_unknown"),
])
def test_live_payout_outcomes(make_env, monkeypatch, result, status):
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: result)
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote()
    j = e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address)).get_json()
    assert j["status"] == status
    assert order_of(q)["provider_ref"].startswith("KUDI-NGN-")


def test_concurrent_confirms_pay_once(make_env, monkeypatch):
    calls = []
    def slow(*a, **k):
        calls.append(1); time.sleep(0.05); return ("ok", "x", "Flutterwave", "R")
    monkeypatch.setattr(payouts, "dispatch", slow)
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote(); tx = e.chain.add_deposit(q, e.user.address)
    codes = []
    def go(): codes.append(e.app.test_client().post("/api/send/confirm",
                                                    json={"quote_id": q["quote_id"], "tx_hash": tx}).status_code)
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(calls) == 1, codes


# ── providers: no failover on unknown outcome ────────────
ORDER = {"payout_amount": "29760.00", "recipient_name": "Ada", "method": "bank", "country_code": "NG",
         "currency": "NGN", "bank_code": "058", "account_number": "0123456789", "phone": "",
         "wallet": "0xabcdef1234567890"}
KEYS = {"flutterwave": "f", "bitnob": "b", "paystack": "p"}


class _Resp:
    def __init__(self, code, body): self.status_code, self._b = code, body
    def json(self): return self._b


def test_timeout_never_fails_over(monkeypatch):
    urls = []
    def post(url, **k):
        urls.append(url); raise requests.exceptions.ReadTimeout()
    monkeypatch.setattr(payouts.requests, "post", post)
    state, *_ = payouts.dispatch(ORDER, "KUDI-X", KEYS)
    assert state == "unknown" and len(urls) == 1


def test_5xx_never_fails_over(monkeypatch):
    urls = []
    monkeypatch.setattr(payouts.requests, "post", lambda u, **k: (urls.append(u), _Resp(502, None))[1])
    assert payouts.dispatch(ORDER, "KUDI-X", KEYS)[0] == "unknown" and len(urls) == 1


def test_definite_rejection_fails_over(monkeypatch):
    def post(url, **k):
        if "flutterwave" in url: return _Resp(400, {"message": "bad account"})
        return _Resp(200, {"status": True})
    monkeypatch.setattr(payouts.requests, "post", post)
    state, _, provider, pref = payouts.dispatch(ORDER, "KUDI-X", KEYS)
    assert (state, provider, pref) == ("ok", "Bitnob", "KUDI-X-BNB")


def test_unreachable_provider_fails_over(monkeypatch):
    def post(url, **k):
        if "flutterwave" in url: raise requests.exceptions.ConnectionError()
        return _Resp(200, {"status": True})
    monkeypatch.setattr(payouts.requests, "post", post)
    assert payouts.dispatch(ORDER, "KUDI-X", KEYS)[0] == "ok"


def test_all_rejected(monkeypatch):
    monkeypatch.setattr(payouts.requests, "post", lambda u, **k: _Resp(400, {"message": "no"}))
    assert payouts.dispatch(ORDER, "KUDI-X", KEYS)[0] == "rejected"


def test_unconfigured_providers_are_skipped(monkeypatch):
    monkeypatch.setattr(payouts.requests, "post", lambda *a, **k: pytest.fail("must not be called"))
    assert payouts.dispatch(ORDER, "KUDI-X", {"flutterwave": "mock"})[0] == "rejected"


# ── webhooks / status ────────────────────────────────────
def test_webhook_moves_only_pending_orders(make_env, monkeypatch):
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: ("ok", "x", "Bitnob", "R"))
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote(); e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address))
    ref = order_of(q)["provider_ref"]
    db.update_send_status(ref + "-BNB", "completed")            # provider suffix handled
    assert order_of(q)["status"] == "completed"
    db.update_send_status(ref, "failed")                        # too late to flip a finished order
    assert order_of(q)["status"] == "completed"


def test_webhook_failure_requires_refund(make_env, monkeypatch):
    monkeypatch.setattr(payouts, "dispatch", lambda *a, **k: ("ok", "x", "Flutterwave", "R"))
    e = make_env(mode="live", keys={"flutterwave": "sk"})
    q = e.quote(); e.confirm(q["quote_id"], e.chain.add_deposit(q, e.user.address))
    db.update_send_status(order_of(q)["provider_ref"], "failed")
    assert order_of(q)["status"] == "refund_required"


def test_order_status_endpoint_and_config(make_env):
    e = make_env(); q = e.quote()
    assert e.client.get(f"/api/send/order/{q['quote_id']}").get_json()["status"] == "quoted"
    assert e.client.get("/api/send/order/not-an-id").status_code == 400
    cfgj = e.client.get("/api/send/config").get_json()
    assert cfgj["escrow_address"] == ESCROW and cfgj["min_amount"] == "10" and cfgj["mode"] == "mock"


def test_phone_with_spaces_and_dashes_is_normalized(make_env):
    e = make_env()
    q = e.quote(country_code="KE", method="mobile_money", phone="+254 700-000 000", account_number="", bank_code="")
    assert order_of(q)["phone"] == "+254700000000"


# ── network presets ──────────────────────────────────────
def test_network_defaults_to_testnet(monkeypatch):
    for k in ("NETWORK", "CHAIN_ID", "ARC_RPC", "EXPLORER_URL", "USDC_ADDRESS", "EURC_ADDRESS"):
        monkeypatch.delenv(k, raising=False)
    c = kudisend.load_config()
    assert c["network"] == "testnet" and c["chain_id"] == 5042002 and c["rpc"] == "https://rpc.testnet.arc.io"
    assert c["explorer"] == "https://explorer.testnet.arc.io" and set(c["tokens"]) == {"USDC", "EURC"}


def test_mainnet_preset_has_no_eurc_until_you_set_it(monkeypatch):
    for k in ("CHAIN_ID", "ARC_RPC", "EXPLORER_URL", "USDC_ADDRESS", "EURC_ADDRESS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NETWORK", "mainnet")
    c = kudisend.load_config()
    assert c["chain_id"] == 5042 and c["rpc"].endswith("mainnet.arc.io") and set(c["tokens"]) == {"USDC"}
    monkeypatch.setenv("EURC_ADDRESS", "0x" + "ab" * 20)
    assert kudisend.load_config()["tokens"]["EURC"] == "0x" + "ab" * 20


def test_unknown_network_fails_loudly(monkeypatch):
    monkeypatch.setenv("NETWORK", "mainet")           # a typo must not silently fall back to testnet
    with pytest.raises(ValueError):
        kudisend.load_config()


def test_env_overrides_beat_presets(monkeypatch):
    monkeypatch.setenv("NETWORK", "testnet"); monkeypatch.setenv("ARC_RPC", "http://x"); monkeypatch.setenv("CHAIN_ID", "7")
    c = kudisend.load_config()
    assert c["rpc"] == "http://x" and c["chain_id"] == 7


def test_mainnet_without_eurc_rejects_eurc_quotes(make_env, monkeypatch):
    monkeypatch.setenv("NETWORK", "mainnet"); monkeypatch.delenv("EURC_ADDRESS", raising=False)
    e = make_env()
    assert e.quote(token="EURC", expect=400)["code"] == "bad_token"


def test_send_config_exposes_network_for_the_frontend(make_env):
    e = make_env()
    n = e.client.get("/api/send/config").get_json()["network"]
    assert n["chain_id"] == 5042002 and n["rpc_url"].startswith("https://") and n["native_decimals"] == 18
