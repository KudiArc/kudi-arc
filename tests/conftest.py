import os, sys, time, secrets, json, hashlib
from decimal import Decimal
import pytest
from flask import Flask
from eth_account import Account
from eth_account.messages import encode_defunct
from web3.exceptions import TransactionNotFound

import db, kudisend, webhooks
from adminauth import AdminAuth, build_message

ESCROW = "0xd2e4eBA288FDcAef6Cec0095C763483DEfA2e010"
USDC = "0x3600000000000000000000000000000000000000"
EURC = "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"
ZERO = "0x" + "0" * 40
COUNTRIES = [{"code": "NG", "currency": "NGN"}, {"code": "KE", "currency": "KES"}]
FEES = {"NG": 0.008, "KE": 0.035}
RATES = {"NGN": 1500.0, "KES": 130.0}
TOPIC = kudisend.DEPOSITED_TOPIC


def _pad(addr):
    return "0x" + "0" * 24 + addr.lower().replace("0x", "")


class _Call:
    def __init__(self, v): self.v = v
    def call(self): return self.v


class _Funcs:
    def __init__(self, chain): self.c = chain
    def minDeposit(self): return _Call(self.c.min)
    def maxDeposit(self): return _Call(self.c.max)
    def deposits(self, ref):
        return _Call(self.c.deposits.get("0x" + ref.hex(), (ZERO, ZERO, 0, 0, 0)))


class _Contract:
    def __init__(self, chain): self.functions = _Funcs(chain)


class _Eth:
    def __init__(self, chain): self.c = chain
    @property
    def chain_id(self): return self.c.chain_id
    def contract(self, address=None, abi=None): return _Contract(self.c)
    @property
    def block_number(self): return 1000
    def get_block(self, n): return {"timestamp": 0}
    def get_logs(self, flt):
        want = [str(t).lower() for t in flt["topics"]]
        return [lg for lg in self.c.logs
                if [t.lower() for t in lg["topics"][:len(want)]] == want and lg["address"].lower() == flt["address"].lower()]

    def get_transaction_receipt(self, h):
        if h not in self.c.receipts:
            raise TransactionNotFound(h)
        return self.c.receipts[h]


class FakeChain:
    """Minimal stand-in for web3: receipts + the escrow's deposits() view."""
    def __init__(self):
        self.chain_id, self.min, self.max = 5042002, 10_000_000, 50_000_000
        self.receipts, self.deposits, self.logs = {}, {}, []
        self.eth = _Eth(self)

    def add_deposit(self, quote, user, token=None, amount=None, at=None, to=None,
                    status=1, ref=None, state=1, event_ref=None):
        ref = ref or quote["ref"]
        token = token or quote["token_address"]
        amount = int(quote["amount_base"]) if amount is None else amount
        at = int(time.time()) if at is None else at
        h = "0x" + secrets.token_hex(32)
        log = {"address": ESCROW, "topics": [TOPIC, event_ref or ref, _pad(user), _pad(token)],
               "data": "0x" + format(amount, "064x")}
        self.receipts[h] = {"status": status, "to": to or ESCROW, "logs": [log]}
        self.logs.append({**log, "transactionHash": h})
        self.deposits[ref] = (user, token, amount, at, state)
        return h


class Env:
    pass


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Every test runs against a throwaway database, ignores the real .env and has no network."""
    import dotenv, requests
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "isolated.db"))

    def _no_network(*a, **k):
        raise requests.exceptions.ConnectionError("network is disabled in tests")
    monkeypatch.setattr(requests, "get", _no_network)
    monkeypatch.setattr(requests, "post", _no_network)


@pytest.fixture
def make_env(tmp_path, monkeypatch):
    def build(mode="mock", keys=None, maintenance=False, escrow=ESCROW):
        monkeypatch.setattr(db, "DB_PATH", str(tmp_path / f"t{secrets.token_hex(3)}.db"))
        db.init_db()
        monkeypatch.setenv("SEND_MODE", mode)
        monkeypatch.setenv("ESCROW_ADDRESS", escrow)
        cfg = kudisend.load_config()
        e = Env()
        e.chain, e.cfg = FakeChain(), cfg
        e.user = Account.create()
        e.owner = Account.create()
        e.auth = AdminAuth(e.owner.address, 5042002, "kudiarc.xyz")
        e.maintenance = maintenance
        e.fee_floor = 0
        bp = kudisend.create_blueprint(
            w3=e.chain, get_rates=lambda: {"eur_usd": 1.1}, get_multi_rates=lambda: RATES,
            countries=COUNTRIES, fees=FEES, is_maintenance=lambda: e.maintenance,
            admin_min_usd=lambda: Decimal("5"), provider_keys=keys or {}, cfg=cfg,
            admin_required=e.auth.required, admin_fee_floor_pct=lambda: e.fee_floor)
        app = Flask(__name__)
        app.register_blueprint(bp)
        e.wh_keys = {"flutterwave": "sk_flw", "paystack": "sk_psk"}
        e.wh_secrets = {"flutterwave": "flwhash", "bitnob": "bnbsecret"}
        app.register_blueprint(webhooks.create_blueprint(e.wh_keys, e.wh_secrets))
        app.add_url_rule("/api/admin/challenge", "admin_challenge", lambda: e.auth.challenge())

        @app.route("/api/test/echo", methods=["GET", "POST"])
        @e.auth.required
        def _echo():
            return {"ok": True}

        e.client = app.test_client()
        e.app = app

        def sign(acct, message):
            return Account.sign_message(encode_defunct(text=message), acct.key).signature.hex()

        def quote(acct=None, expect=200, **over):
            acct = acct or e.user
            ch = e.client.post("/api/send/challenge", json={"wallet": acct.address}).get_json()
            body = {"wallet": acct.address, "nonce": ch["nonce"], "signature": sign(acct, ch["message"]),
                    "token": "USDC", "amount": "20", "country_code": "NG", "method": "bank",
                    "recipient_name": "Ada Obi", "account_number": "0123456789", "bank_code": "058",
                    "bank_name": "GTBank"}
            body.update(over)
            r = e.client.post("/api/send/quote", json=body)
            assert r.status_code == expect, r.get_json()
            return r.get_json()

        def confirm(quote_id, tx_hash):
            return e.client.post("/api/send/confirm", json={"quote_id": quote_id, "tx_hash": tx_hash})

        def admin_headers(method, path, raw=b"", signer=None, sign_path=None, sign_method=None, sign_raw=None):
            ch = e.client.get("/api/admin/challenge").get_json()
            msg = build_message(ch["domain"], ch["chain_id"], sign_method or method, sign_path or path,
                                hashlib.sha256(raw if sign_raw is None else sign_raw).hexdigest(),
                                ch["nonce"], ch["expires_at"])
            return {"X-Admin-Nonce": ch["nonce"], "X-Admin-Signature": sign(signer or e.owner, msg)}

        def admin(method, path, body=None, **kw):
            raw = b"" if body is None else json.dumps(body).encode()
            h = admin_headers(method, path, raw, **kw)
            return e.client.open(path, method=method, data=raw, headers=h, content_type="application/json")

        e.sign, e.quote, e.confirm, e.admin, e.admin_headers = sign, quote, confirm, admin, admin_headers
        return e
    return build
