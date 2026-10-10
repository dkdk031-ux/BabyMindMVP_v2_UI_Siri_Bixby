"""SQLite 저장소. 시각은 모두 서버 기준 시간대(+09:00) ISO 문자열로 저장한다."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

COLUMNS = ["id", "type", "started_at", "ended_at", "amount", "unit", "note", "source", "raw_text", "created_at"]


def db_path() -> str:
    return os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "babymind.db"))


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            amount REAL,
            unit TEXT,
            note TEXT,
            source TEXT NOT NULL DEFAULT 'app',
            raw_text TEXT,
            created_at TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_started ON events(started_at)")


def insert_event(e: dict, source: str, raw_text: str | None, tz) -> dict:
    def norm(v):
        return datetime.fromisoformat(v).astimezone(tz).isoformat(timespec="seconds") if v else None

    row = {
        "type": e["type"], "started_at": norm(e["started_at"]), "ended_at": norm(e.get("ended_at")),
        "amount": e.get("amount"), "unit": e.get("unit"), "note": e.get("note"),
        "source": source, "raw_text": raw_text,
        "created_at": datetime.now(tz).isoformat(timespec="seconds"),
    }
    with connect() as c:
        cur = c.execute(f"INSERT INTO events ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                        list(row.values()))
        row["id"] = cur.lastrowid
    return row


def list_events(start: str, end: str) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM events WHERE started_at >= ? AND started_at < ? ORDER BY started_at DESC",
                         (start, end)).fetchall()
    return [dict(r) for r in rows]


def delete_event(event_id: int) -> bool:
    with connect() as c:
        return c.execute("DELETE FROM events WHERE id = ?", (event_id,)).rowcount > 0
