import sqlite3, time
import pytest
from flask import Flask
from eth_account import Account
import db, swapverify
from conftest import FakeChain, USDC, EURC, ESCROW

SWAP = "0x" + "5a" * 20
TOKENS = {"USDC": USDC, "EURC": EURC}


def pad(a): return "0x" + "0" * 24 + a.lower().replace("0x", "")


class Env:
    pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "s.db")); db.init_db()
    monkeypatch.setattr(swapverify.time, "sleep", lambda s: None)
    e = Env(); e.chain = FakeChain(); e.user = Account.create()
    app = Flask(__name__)
    app.register_blueprint(swapverify.create_blueprint(e.chain, SWAP, TOKENS, lambda: {"eur_usd": 1.1}, lambda: {"NGN": 1500.0}))
    e.client = app.test_client()

    def swap_tx(user=None, src=USDC, dst=EURC, a_in=10_000_000, a_out=8_500_000, fee=30_000,
                to=SWAP, status=1, log_addr=SWAP):
        h = "0x" + __import__("secrets").token_hex(32)
        log = {"address": log_addr, "topics": [swapverify.SWAPPED_TOPIC, pad(user or e.user.address), pad(src), pad(dst)],
               "data": "0x" + "".join(format(v, "064x") for v in (a_in, a_out, fee))}
        e.chain.receipts[h] = {"status": status, "to": to, "logs": [log]}
        return h

    def record(tx, wallet=None, **extra):
        return e.client.post("/api/swap/record", json={"wallet": wallet or e.user.address, "tx_hash": tx, **extra})

    def rows():
        c = sqlite3.connect(db.DB_PATH); c.row_factory = sqlite3.Row
        r = [dict(x) for x in c.execute("SELECT * FROM transactions WHERE tx_type='swap'")]; c.close(); return r

    e.swap_tx, e.record, e.rows = swap_tx, record, rows
    return e


def test_records_what_the_chain_says_not_what_the_browser_says(env):
    tx = env.swap_tx()
    r = env.record(tx, amount_in=999999, amount_out=999999, fee=0, rate=50, ngn_equiv=10**9)   # lies are ignored
    assert r.status_code == 200
    row = env.rows()[0]
    assert (row["amount_in"], row["amount_out"], row["fee"]) == (10.0, 8.5, 0.03)
    assert row["from_token"] == "USDC" and row["to_token"] == "EURC" and row["wallet"] == env.user.address
    assert abs(row["rate"] - 8.5 / 9.97) < 1e-9 and row["ngn_equiv"] == 15000.0


def test_eurc_to_usdc_converted_for_ngn(env):
    env.record(env.swap_tx(src=EURC, dst=USDC, a_in=10_000_000, a_out=11_000_000, fee=0))
    assert env.rows()[0]["ngn_equiv"] == pytest.approx(10 * 1.1 * 1500)


def test_duplicate_tx_recorded_once(env):
    tx = env.swap_tx()
    assert env.record(tx).status_code == 200 and env.record(tx).status_code == 200
    assert len(env.rows()) == 1


def test_wrong_wallet_rejected(env):
    r = env.record(env.swap_tx(), wallet=Account.create().address)
    assert r.status_code == 400 and not env.rows()


def test_failed_or_foreign_transactions_rejected(env):
    assert env.record(env.swap_tx(status=0)).status_code == 400
    assert env.record(env.swap_tx(to="0x" + "11" * 20)).status_code == 400            # not sent to the swap contract
    assert env.record(env.swap_tx(log_addr="0x" + "11" * 20)).status_code == 400      # event from some other contract
    assert not env.rows()


def test_unknown_token_rejected(env):
    assert env.record(env.swap_tx(dst="0x" + "22" * 20)).status_code == 400 and not env.rows()


def test_tx_without_swap_event_rejected(env):
    h = "0x" + "ab" * 32
    env.chain.receipts[h] = {"status": 1, "to": SWAP, "logs": []}
    assert env.record(h).status_code == 400


def test_tx_not_found_yet_returns_pending(env):
    assert env.record("0x" + "cd" * 32).status_code == 202 and not env.rows()


def test_rpc_failure_is_503(env):
    env.chain.receipts = None
    assert env.record("0x" + "cd" * 32).status_code == 503


@pytest.mark.parametrize("body", [{}, {"wallet": "x", "tx_hash": "0x" + "ab" * 32}, {"wallet": "0x" + "1" * 40, "tx_hash": "0x12"}])
def test_malformed_input(env, body):
    assert env.client.post("/api/swap/record", json=body).status_code == 400


def test_unconfigured_contract_is_503(env):
    app = Flask(__name__)
    app.register_blueprint(swapverify.create_blueprint(env.chain, "", TOKENS, lambda: {}, lambda: {}))
    assert app.test_client().post("/api/swap/record", json={}).status_code == 503


def test_duplicate_protected_by_unique_index_when_race(env, monkeypatch):
    tx = env.swap_tx()
    monkeypatch.setattr(db, "swap_exists", lambda h: False)      # both racing requests passed the check
    assert env.record(tx).status_code == 200 and env.record(tx).status_code == 200
    assert len(env.rows()) == 1


def test_duplicates_blocked_even_on_old_databases_without_the_unique_index(env):
    c = sqlite3.connect(db.DB_PATH); c.execute("DROP INDEX IF EXISTS idx_tx_hash_unique"); c.commit(); c.close()
    tx = env.swap_tx()
    assert env.record(tx).status_code == 200 and env.record(tx).status_code == 200
    assert len(env.rows()) == 1


def test_startup_survives_old_database_with_duplicate_tx_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "old.db"))
    c = sqlite3.connect(db.DB_PATH)
    c.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, tx_type TEXT, wallet TEXT, from_token TEXT, to_token TEXT, amount_in REAL, amount_out REAL, fee REAL, rate REAL, ngn_equiv REAL, tx_hash TEXT, recipient_name TEXT, recipient_bank TEXT, recipient_account TEXT, recipient_phone TEXT, bitnob_ref TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.executemany("INSERT INTO transactions (tx_type, tx_hash) VALUES ('swap', ?)", [("0xdup",), ("0xdup",)]); c.commit(); c.close()
    db.init_db()                                   # must not crash on the duplicates
