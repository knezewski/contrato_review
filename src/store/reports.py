"""Report storage for 30 days (spec §4, AC15; research.md R14; data-model.md §10).

SQLite file with mode 0600. report_json holds only the language-neutral report, without contract text.
Expired records are removed before every read and write and at application startup.

Failure modes:
- an expired or unknown report_id → None (the caller returns 404 without distinction);
- schema_version mismatch → None (no migrations in the MVP);
- write failure → exception; the report is not returned (REPORT_STORE_FAILED).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = "1.0"


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


class ReportStore:
    def __init__(self, path: str, retention_days: int = 30):
        self._path = Path(path)
        self._retention = timedelta(days=retention_days)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        created = not self._path.exists()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reports ("
                "report_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
                "expires_at TEXT NOT NULL, report_json TEXT NOT NULL)"
            )
        if created:
            os.chmod(self._path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def save(
        self, report_id: str, report: dict, now: datetime | None = None
    ) -> datetime:
        moment = now or datetime.now(UTC)
        expires = moment + self._retention
        self.purge_expired(now=moment)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (report_id, created_at, expires_at, report_json) VALUES (?, ?, ?, ?)",
                (
                    report_id,
                    _iso(moment),
                    _iso(expires),
                    json.dumps(report, ensure_ascii=False),
                ),
            )
        return expires

    def get(self, report_id: str, now: datetime | None = None) -> dict | None:
        moment = now or datetime.now(UTC)
        self.purge_expired(now=moment)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT report_json, expires_at FROM reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        report = json.loads(row[0])
        if report.get("schema_version") != SCHEMA_VERSION:
            return None
        return {"report": report, "expires_at": row[1]}

    def purge_expired(self, now: datetime | None = None) -> int:
        moment = now or datetime.now(UTC)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM reports WHERE expires_at <= ?", (_iso(moment),)
            )
            return cursor.rowcount

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
