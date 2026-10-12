"""SQLite persistence. Atomic answers and optimistic interview transitions."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, role TEXT NOT NULL, profile TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','complete')), mode TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 summary TEXT
);
CREATE TABLE IF NOT EXISTS questions (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, payload TEXT NOT NULL, answer TEXT,
 answered_at TEXT, UNIQUE(session_id, ordinal)
);
CREATE TABLE IF NOT EXISTS chunks (
 id TEXT PRIMARY KEY, page INTEGER NOT NULL, source TEXT NOT NULL,
 text TEXT NOT NULL, embedding TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
