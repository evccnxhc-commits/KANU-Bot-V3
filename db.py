"""SQLite storage: users, conversations, messages, and processed webhook events.

NOTE: on Render's free plan the local filesystem is ephemeral. Data survives restarts
only if DATABASE_PATH points at a persistent disk (paid) -- otherwise accounts and
conversations may be lost when the service restarts or redeploys.
"""
import os
import sqlite3
import threading
import time
from pathlib import Path

_lock = threading.Lock()


def db_path():
    return os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "kanu_users.sqlite3"))


def connect():
    conn = sqlite3.connect(db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    Path(db_path()).parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT 'محادثة جديدة',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id);
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL);
        """)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---- webhook de-duplication -------------------------------------------------
_seen_memory = {}


def claim_event(event_id, ttl=7 * 86400):
    """Atomically claim a Messenger event id. True = first time (process it)."""
    if not event_id:
        return True  # cannot dedupe without an id; never drop a legitimate message
    now = int(time.time())
    with _lock:
        if event_id in _seen_memory:
            return False
        _seen_memory[event_id] = now
        if len(_seen_memory) > 5000:
            for k in sorted(_seen_memory, key=_seen_memory.get)[:1000]:
                _seen_memory.pop(k, None)
    try:
        with connect() as conn:
            cur = conn.execute("INSERT OR IGNORE INTO processed_events(event_id, created_at) VALUES (?, ?)", (event_id, now))
            if cur.rowcount == 0:
                return False
            conn.execute("DELETE FROM processed_events WHERE created_at < ?", (now - ttl,))
    except sqlite3.Error:
        pass  # in-memory guard above still protects this process
    return True


# ---- conversations ----------------------------------------------------------
def list_conversations(user_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.id, c.title, c.updated_at, "
            "(SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last "
            "FROM conversations c WHERE c.user_id = ? ORDER BY c.updated_at DESC, c.id DESC LIMIT 100", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def create_conversation(user_id, title="محادثة جديدة"):
    with connect() as conn:
        cur = conn.execute("INSERT INTO conversations(user_id, title, created_at, updated_at) VALUES (?,?,?,?)",
                           (user_id, title, _now(), _now()))
        return cur.lastrowid


def get_conversation(user_id, conv_id):
    with connect() as conn:
        row = conn.execute("SELECT id, title FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)).fetchone()
    return dict(row) if row else None


def get_messages(conv_id, limit=200):
    with connect() as conn:
        rows = conn.execute("SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? "
                            "ORDER BY id DESC LIMIT ?", (conv_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def add_message(conv_id, role, content):
    now = _now()
    with connect() as conn:
        cur = conn.execute("INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?,?,?,?)",
                           (conv_id, role, content, now))
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        return {"id": cur.lastrowid, "role": role, "content": content, "created_at": now}


def set_title(conv_id, title):
    with connect() as conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))


def delete_conversation(user_id, conv_id):
    with connect() as conn:
        return conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)).rowcount > 0
