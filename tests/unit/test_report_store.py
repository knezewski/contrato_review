import os
import sqlite3
from datetime import UTC, datetime, timedelta

from src.store.reports import ReportStore

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def _report(**overrides):
    base = {"schema_version": "1.0", "clauses": [], "summary": {}}
    base.update(overrides)
    return base


def test_save_then_get_returns_report(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    store.save("abc", _report(), now=NOW)
    found = store.get("abc", now=NOW + timedelta(days=1))
    assert found["report"]["schema_version"] == "1.0"


def test_expires_at_is_thirty_days_after_creation(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    expires = store.save("abc", _report(), now=NOW)
    assert expires == NOW + timedelta(days=30)
    found = store.get("abc", now=NOW + timedelta(days=29))
    assert found["expires_at"].startswith("2026-11-12T12:00:00")


def test_expired_report_is_not_returned_and_is_deleted(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    store.save("abc", _report(), now=NOW)
    assert store.get("abc", now=NOW + timedelta(days=30)) is None
    assert store.count() == 0


def test_purge_removes_only_expired(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    store.save("old", _report(), now=NOW)
    store.save("new", _report(), now=NOW + timedelta(days=20))
    removed = store.purge_expired(now=NOW + timedelta(days=31))
    assert removed == 1
    assert store.get("new", now=NOW + timedelta(days=31)) is not None


def test_other_schema_version_is_not_returned(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    store.save("abc", _report(schema_version="0.9"), now=NOW)
    assert store.get("abc", now=NOW) is None


def test_unknown_id_is_none(tmp_path):
    store = ReportStore(str(tmp_path / "r.db"), retention_days=30)
    assert store.get("missing", now=NOW) is None


def test_file_is_private(tmp_path):
    path = tmp_path / "r.db"
    ReportStore(str(path), retention_days=30)
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_stored_row_has_no_contract_text_column(tmp_path):
    path = tmp_path / "r.db"
    ReportStore(str(path), retention_days=30)
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
    assert columns == {"report_id", "created_at", "expires_at", "report_json"}
