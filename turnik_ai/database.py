"""Mashg'ulotlar tarixi (SQLite)."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import settings as S


class Database:
    def __init__(self, path: Path = S.DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL, duration_s REAL NOT NULL,
            total INTEGER NOT NULL, correct INTEGER NOT NULL, wrong INTEGER NOT NULL,
            error_stats TEXT NOT NULL, reps TEXT NOT NULL)""")
        self.conn.commit()

    def save_session(self, started_at: datetime, duration_s: float, counter) -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions(started_at,duration_s,total,correct,wrong,error_stats,reps) VALUES(?,?,?,?,?,?,?)",
            (started_at.isoformat(timespec="seconds"), duration_s, counter.total, counter.correct, counter.wrong,
             json.dumps(counter.error_stats, ensure_ascii=False),
             json.dumps([v.to_dict() for v in counter.verdicts], ensure_ascii=False)))
        self.conn.commit()
        return cur.lastrowid

    def list_sessions(self, limit=100):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))]

    def delete_session(self, sid: int):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.conn.commit()

    def close(self):
        self.conn.close()
