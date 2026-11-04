import sqlite3, os, re, time, json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.expanduser("~"), ".kudi-data", "kudi.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_type           TEXT    NOT NULL,
            wallet            TEXT    NOT NULL,
            from_token        TEXT,
            to_token          TEXT,
            amount_in         REAL,
            amount_out        REAL,
            fee               REAL,
            rate              REAL,
            ngn_equiv         REAL,
            tx_hash           TEXT,
            status            TEXT DEFAULT 'completed',
            recipient_name    TEXT,
            recipient_bank    TEXT,
            recipient_account TEXT,
            recipient_phone   TEXT,
            bitnob_ref        TEXT,
            created_at        TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_wallet      ON transactions(wallet);
        CREATE INDEX IF NOT EXISTS idx_bitnob_ref  ON transactions(bitnob_ref);
        CREATE INDEX IF NOT EXISTS idx_created_at  ON transactions(created_at DESC);

        CREATE TABLE IF NOT EXISTS send_challenges (
            nonce       TEXT PRIMARY KEY,
            wallet      TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            expires_at  INTEGER NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS send_orders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id       TEXT    NOT NULL UNIQUE,
            ref            TEXT    NOT NULL UNIQUE,
            wallet         TEXT    NOT NULL,
            token          TEXT    NOT NULL,
            token_address  TEXT    NOT NULL,
            amount_base    INTEGER NOT NULL,
            fee_base       INTEGER NOT NULL,
            rate           TEXT    NOT NULL,
            payout_amount  TEXT    NOT NULL,
            country_code   TEXT    NOT NULL,
            currency       TEXT    NOT NULL,
            method         TEXT    NOT NULL,
            recipient_name TEXT,
            bank_code      TEXT,
            bank_name      TEXT,
            account_number TEXT,
            phone          TEXT,
            status         TEXT    NOT NULL DEFAULT 'quoted',
            tx_hash        TEXT    UNIQUE,
            provider       TEXT,
            provider_ref   TEXT,
            error          TEXT,
            chain_state    TEXT    NOT NULL DEFAULT 'none',
            expires_at     INTEGER NOT NULL,
            created_at     INTEGER NOT NULL,
            updated_at     INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admin_nonces (
            nonce       TEXT PRIMARY KEY,
            expires_at  INTEGER NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS kv_state (
            ns     TEXT NOT NULL,
            key    TEXT NOT NULL,
            value  TEXT NOT NULL,
            PRIMARY KEY (ns, key)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_wallet ON send_orders(wallet);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON send_orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_pref   ON send_orders(provider_ref);
    """)
    conn.commit()
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_hash_unique "
                     "ON transactions(tx_hash) WHERE tx_hash IS NOT NULL")
        conn.commit()
    except sqlite3.IntegrityError:
        print("⚠️  Old duplicate tx_hash rows exist; relying on application-level duplicate checks")
    conn.close()
    print("✅ Database initialized")

def save_swap(wallet, from_token, to_token, amount_in, amount_out, fee, rate, ngn_equiv, tx_hash):
    conn = get_db()
    conn.execute("""
        INSERT INTO transactions
        (tx_type, wallet, from_token, to_token, amount_in, amount_out, fee, rate, ngn_equiv, tx_hash, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, ("swap", wallet, from_token, to_token, amount_in, amount_out, fee, rate, ngn_equiv, tx_hash, "completed"))
    conn.commit()
    conn.close()

def save_send(wallet, amount_usdc, ngn_amount, recipient_name, recipient_bank,
              recipient_account, recipient_phone, bitnob_ref, status="pending",
              tx_hash=None, from_token="USDC", to_token="NGN", fee=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO transactions
        (tx_type, wallet, from_token, to_token, amount_in, ngn_equiv,
         recipient_name, recipient_bank, recipient_account, recipient_phone, bitnob_ref, status, tx_hash, fee)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, ("send", wallet, from_token, to_token, amount_usdc, ngn_amount,
          recipient_name, recipient_bank, recipient_account, recipient_phone, bitnob_ref, status, tx_hash, fee))
    conn.commit()
    conn.close()

def get_history(wallet, limit=50, tx_type="all"):
    conn  = get_db()
    limit = min(limit, 200)
    if tx_type == "all":
        rows = conn.execute("""
            SELECT * FROM transactions
            WHERE LOWER(wallet)=LOWER(?)
            ORDER BY created_at DESC LIMIT ?
        """, (wallet, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM transactions
            WHERE LOWER(wallet)=LOWER(?) AND tx_type=?
            ORDER BY created_at DESC LIMIT ?
        """, (wallet, tx_type, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_send_status(bitnob_ref, status):
    bitnob_ref = re.sub(r"-(BNB|PSK)$", "", bitnob_ref or "")   # provider suffixes
    conn = get_db()
    conn.execute("UPDATE transactions SET status=? WHERE bitnob_ref=?", (status, bitnob_ref))
    # Provider results move an order forward only from payout_pending.
    order_status = "completed" if status == "completed" else "refund_required"
    conn.execute(
        "UPDATE send_orders SET status=?, updated_at=? "
        "WHERE status IN ('payout_pending','payout_unknown') AND (ref=? OR provider_ref=?)",
        (order_status, int(time.time()), bitnob_ref, bitnob_ref))
    conn.commit()
    conn.close()

# ── KudiSend orders ───────────────────────────────────────────
ORDER_FIELDS = ("quote_id","ref","wallet","token","token_address","amount_base","fee_base",
                "rate","payout_amount","country_code","currency","method","recipient_name",
                "bank_code","bank_name","account_number","phone","expires_at")

def create_challenge(wallet, nonce, message, expires_at):
    conn = get_db()
    conn.execute("INSERT INTO send_challenges (nonce,wallet,message,expires_at) VALUES (?,?,?,?)",
                 (nonce, wallet.lower(), message, expires_at))
    conn.commit(); conn.close()

def open_challenge_count(wallet, now):
    """Also purges challenges that expired over an hour ago."""
    conn = get_db()
    conn.execute("DELETE FROM send_challenges WHERE expires_at < ?", (now - 3600,))
    n = conn.execute("SELECT COUNT(*) FROM send_challenges WHERE wallet=? AND used=0 AND expires_at>=?",
                     (wallet.lower(), now)).fetchone()[0]
    conn.commit(); conn.close()
    return n

def get_challenge(nonce):
    conn = get_db()
    row = conn.execute("SELECT * FROM send_challenges WHERE nonce=?", (nonce,)).fetchone()
    conn.close()
    return dict(row) if row else None

def consume_challenge(nonce):
    """Atomically mark a challenge used. True only for the first caller."""
    conn = get_db()
    cur = conn.execute("UPDATE send_challenges SET used=1 WHERE nonce=? AND used=0", (nonce,))
    conn.commit(); ok = cur.rowcount == 1; conn.close()
    return ok

def create_order(order):
    now = int(time.time())
    conn = get_db()
    cols = ORDER_FIELDS + ("created_at","updated_at")
    vals = [order[k] for k in ORDER_FIELDS] + [now, now]
    conn.execute(f"INSERT INTO send_orders ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals)
    conn.commit(); conn.close()

def get_order(quote_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM send_orders WHERE quote_id=?", (quote_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def claim_order(quote_id, tx_hash, from_status="quoted", to_status="paying"):
    """Atomic state move. True only if this call performed the move."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE send_orders SET status=?, tx_hash=?, updated_at=? WHERE quote_id=? AND status=?",
            (to_status, tx_hash, int(time.time()), quote_id, from_status))
        conn.commit(); ok = cur.rowcount == 1
    except sqlite3.IntegrityError:   # tx_hash already used by another order
        ok = False
    conn.close()
    return ok

def update_order(quote_id, **fields):
    allowed = {"status","provider","provider_ref","error","chain_state"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields: return
    fields["updated_at"] = int(time.time())
    conn = get_db()
    conn.execute(f"UPDATE send_orders SET {','.join(k+'=?' for k in fields)} WHERE quote_id=?",
                 list(fields.values()) + [quote_id])
    conn.commit(); conn.close()

if __name__ == "__main__":
    init_db()


# ── Admin nonces (single-use, shared across workers) ──────────
def open_admin_nonce_count(now):
    conn = get_db()
    conn.execute("DELETE FROM admin_nonces WHERE expires_at < ?", (now - 3600,))
    n = conn.execute("SELECT COUNT(*) FROM admin_nonces WHERE used=0 AND expires_at>=?", (now,)).fetchone()[0]
    conn.commit(); conn.close()
    return n

def create_admin_nonce(nonce, expires_at):
    conn = get_db()
    conn.execute("INSERT INTO admin_nonces (nonce, expires_at) VALUES (?,?)", (nonce, expires_at))
    conn.commit(); conn.close()

def get_admin_nonce(nonce):
    conn = get_db()
    row = conn.execute("SELECT * FROM admin_nonces WHERE nonce=?", (nonce,)).fetchone()
    conn.close()
    return dict(row) if row else None

def consume_admin_nonce(nonce):
    conn = get_db()
    cur = conn.execute("UPDATE admin_nonces SET used=1 WHERE nonce=? AND used=0", (nonce,))
    conn.commit(); ok = cur.rowcount == 1; conn.close()
    return ok

# ── Shared key/value state (replaces per-worker memory) ───────
class SharedState:
    """dict-like view of kv_state so every worker sees the same values."""
    def __init__(self, ns, defaults=None):
        self.ns, self.defaults = ns, dict(defaults or {})

    def get(self, key, default=None):
        conn = get_db()
        row = conn.execute("SELECT value FROM kv_state WHERE ns=? AND key=?", (self.ns, key)).fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
        return self.defaults.get(key, default)

    def __getitem__(self, key):
        v = self.get(key, None)
        if v is None and key not in self.defaults:
            raise KeyError(key)
        return v

    def __setitem__(self, key, value):
        conn = get_db()
        conn.execute("INSERT INTO kv_state (ns,key,value) VALUES (?,?,?) "
                     "ON CONFLICT(ns,key) DO UPDATE SET value=excluded.value",
                     (self.ns, key, json.dumps(value)))
        conn.commit(); conn.close()

    def seed(self, values):
        """Store values only for keys not set yet (one-time migration)."""
        conn = get_db()
        for k, v in values.items():
            conn.execute("INSERT OR IGNORE INTO kv_state (ns,key,value) VALUES (?,?,?)",
                         (self.ns, k, json.dumps(v)))
        conn.commit(); conn.close()

# ── Admin views of send orders ────────────────────────────────
def list_orders(statuses=None, chain_state=None, limit=100):
    q, args = "SELECT * FROM send_orders", []
    cond = []
    if statuses:
        cond.append(f"status IN ({','.join('?'*len(statuses))})"); args += list(statuses)
    if chain_state:
        cond.append("chain_state=?"); args.append(chain_state)
    if cond: q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY created_at DESC LIMIT ?"; args.append(int(limit))
    conn = get_db()
    rows = [dict(r) for r in conn.execute(q, args).fetchall()]
    conn.close()
    return rows

def transition_order(quote_id, from_statuses, to_status, error=None):
    """Atomic status move that only applies from the listed states."""
    conn = get_db()
    cur = conn.execute(
        f"UPDATE send_orders SET status=?, error=COALESCE(?, error), updated_at=? "
        f"WHERE quote_id=? AND status IN ({','.join('?'*len(from_statuses))})",
        [to_status, error, int(time.time()), quote_id] + list(from_statuses))
    conn.commit(); ok = cur.rowcount == 1; conn.close()
    return ok


def get_order_by_provider_ref(provider_ref):
    provider_ref = re.sub(r"-(BNB|PSK)$", "", provider_ref or "")
    conn = get_db()
    row = conn.execute("SELECT * FROM send_orders WHERE provider_ref=?", (provider_ref,)).fetchone()
    conn.close()
    return dict(row) if row else None


def swap_exists(tx_hash):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM transactions WHERE tx_hash=? LIMIT 1", (tx_hash,)).fetchone()
    conn.close()
    return row is not None
