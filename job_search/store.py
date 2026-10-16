"""Persistencia SQLite local: dedup entre ejecuciones y seguimiento de estado."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
STATUSES = ("new", "recommended", "maybe", "skipped", "filtered", "applied", "discarded", "error")


class Store:
    def __init__(self, path: Path | None = None):
        path = path or DATA_DIR / "jobs.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                uid TEXT PRIMARY KEY, job TEXT NOT NULL, kw_score REAL, match TEXT,
                score REAL, status TEXT NOT NULL DEFAULT 'new', note TEXT,
                first_seen TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )

    @staticmethod
    def _now() -> str:
        return dt.datetime.now().isoformat(timespec="seconds")

    def seen(self, uid: str) -> bool:
        return self.db.execute("SELECT 1 FROM jobs WHERE uid=?", (uid,)).fetchone() is not None

    def upsert(self, job: dict, *, status: str, kw_score: float | None = None,
               match: dict | None = None, score: float | None = None, note: str | None = None) -> None:
        now = self._now()
        self.db.execute(
            """INSERT INTO jobs (uid, job, kw_score, match, score, status, note, first_seen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(uid) DO UPDATE SET job=excluded.job, kw_score=excluded.kw_score,
                 match=excluded.match, score=excluded.score, status=excluded.status,
                 note=excluded.note, updated_at=excluded.updated_at""",
            (job["uid"], json.dumps(job, ensure_ascii=False), kw_score,
             json.dumps(match, ensure_ascii=False) if match else None, score, status, note, now, now),
        )
        self.db.commit()

    def set_status(self, uid: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"Estado inválido: {status}. Usa uno de {STATUSES}")
        cur = self.db.execute("UPDATE jobs SET status=?, updated_at=? WHERE uid LIKE ?",
                              (status, self._now(), uid + "%"))
        self.db.commit()
        return cur.rowcount > 0

    def get(self, uid: str) -> dict | None:
        row = self.db.execute("SELECT * FROM jobs WHERE uid LIKE ?", (uid + "%",)).fetchone()
        return self._row(row) if row else None

    def list(self, statuses: tuple[str, ...] | None = None) -> list[dict]:
        sql = "SELECT * FROM jobs"
        args: tuple = ()
        if statuses:
            sql += f" WHERE status IN ({','.join('?' * len(statuses))})"
            args = statuses
        sql += " ORDER BY score IS NULL, score DESC, kw_score DESC"
        return [self._row(r) for r in self.db.execute(sql, args)]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["job"] = json.loads(d["job"])
        d["match"] = json.loads(d["match"]) if d["match"] else None
        return d
