import sqlite3, os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kudi.db"))

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
    """)
    conn.commit()
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
              recipient_account, recipient_phone, bitnob_ref, status="pending"):
    conn = get_db()
    conn.execute("""
        INSERT INTO transactions
        (tx_type, wallet, from_token, to_token, amount_in, ngn_equiv,
         recipient_name, recipient_bank, recipient_account, recipient_phone, bitnob_ref, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, ("send", wallet, "USDC", "NGN", amount_usdc, ngn_amount,
          recipient_name, recipient_bank, recipient_account, recipient_phone, bitnob_ref, status))
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
    conn = get_db()
    conn.execute("UPDATE transactions SET status=? WHERE bitnob_ref=?", (status, bitnob_ref))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
