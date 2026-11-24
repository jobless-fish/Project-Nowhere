import json
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  source TEXT, text TEXT,
  status TEXT,              -- processed | needs_review | approved | rejected | failed
  extraction TEXT,          -- JSON
  erp_ref TEXT,
  audit TEXT DEFAULT '[]'   -- JSON list of events
);
CREATE TABLE IF NOT EXISTS llm_calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  document_id INTEGER, provider TEXT, model TEXT, prompt_version TEXT,
  input_tokens INTEGER, output_tokens INTEGER, latency_ms INTEGER,
  cost_usd REAL, ok INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS modes(doc_type TEXT PRIMARY KEY, mode TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outcomes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, doc_type TEXT,
  mode TEXT, agree INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS attendance(user_id TEXT, day TEXT, clock_in_at TEXT, PRIMARY KEY(user_id, day));
CREATE TABLE IF NOT EXISTS briefings(user_id TEXT, day TEXT, payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, day));
CREATE TABLE IF NOT EXISTS todo_feedback(user_id TEXT, day TEXT, todo_key TEXT, value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, day, todo_key));
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, day TEXT, todo_key TEXT, source_id TEXT, kind TEXT,
  to_ref TEXT, to_name TEXT, external INTEGER, draft_subject TEXT, draft_body TEXT, final_subject TEXT, final_body TEXT,
  status TEXT, edited INTEGER DEFAULT 0, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS erp_records(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(config.DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def add_audit(c, doc_id: int, event: str, **data):
    row = c.execute("SELECT audit FROM documents WHERE id=?", (doc_id,)).fetchone()
    log = json.loads(row["audit"])
    log.append({"event": event, **data})
    c.execute("UPDATE documents SET audit=? WHERE id=?", (json.dumps(log, ensure_ascii=False), doc_id))
