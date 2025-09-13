import sqlite3

def get_conn():
    conn = sqlite3.connect("events.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
      CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT,
        date TEXT,
        location TEXT,
        url TEXT,
        notified INTEGER DEFAULT 0
      )
    """)
    conn.commit()
    conn.close()

init_db()
