from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

from webapp.infonalia_webapp.db_migrations import (
    MIGRATIONS,
    MIGRATIONS_TABLE,
    Migration,
    applied_migration_versions,
    run_migrations,
    validate_migrations,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_MODULE_NAME = "webapp.infonalia_webapp.app"
PRODUCTIVE_DB_PATH = REPOSITORY_ROOT / "webapp" / "infonalia_webapp" / "data" / "infonalia.db"


def load_app_module() -> ModuleType:
    os.environ["INFONALIA_ADMIN_USER"] = "admin_test"
    os.environ["INFONALIA_ADMIN_PASSWORD"] = "admin_password_test"
    os.environ["INFONALIA_REVIEWER_USER"] = "reviewer_test"
    os.environ["INFONALIA_REVIEWER_PASSWORD"] = "reviewer_password_test"
    os.environ["INFONALIA_ENABLE_ADMIN_ALIAS"] = "0"
    return importlib.import_module(APP_MODULE_NAME)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def test_run_migrations_creates_table_and_records_baseline() -> None:
    conn = sqlite3.connect(":memory:")

    applied = run_migrations(conn, now=lambda: "2026-06-12T10:00:00")

    assert applied == ["0001_baseline_schema", "0002_download_jobs"]
    assert table_exists(conn, MIGRATIONS_TABLE)
    rows = conn.execute(
        f"SELECT version, description, applied_at FROM {MIGRATIONS_TABLE}"
    ).fetchall()
    assert rows == [
        (
            "0001_baseline_schema",
            "Baseline del esquema historico gestionado por init_db",
            "2026-06-12T10:00:00",
        ),
        (
            "0002_download_jobs",
            "Tabla preparatoria para jobs de descarga",
            "2026-06-12T10:00:00",
        ),
    ]
    assert table_exists(conn, "download_jobs")


def test_run_migrations_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    assert run_migrations(conn, now=lambda: "2026-06-12T10:00:00") == [
        "0001_baseline_schema",
        "0002_download_jobs",
    ]
    assert run_migrations(conn, now=lambda: "2026-06-12T10:05:00") == []

    rows = conn.execute(f"SELECT version, applied_at FROM {MIGRATIONS_TABLE}").fetchall()
    assert rows == [
        ("0001_baseline_schema", "2026-06-12T10:00:00"),
        ("0002_download_jobs", "2026-06-12T10:00:00"),
    ]


def test_validate_migrations_rejects_duplicate_versions() -> None:
    duplicate = Migration("0002_demo", "demo", lambda conn: None)

    with pytest.raises(ValueError, match="Duplicate migration version: 0002_demo"):
        validate_migrations([duplicate, duplicate])


def test_failed_migration_is_not_recorded() -> None:
    conn = sqlite3.connect(":memory:")

    def fail(_: sqlite3.Connection) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_migrations(
            conn,
            migrations=[Migration("0002_fail", "fail", fail)],
            now=lambda: "2026-06-12T10:00:00",
        )

    assert applied_migration_versions(conn) == set()


def test_download_jobs_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(download_jobs)").fetchall()
    }
    assert columns == {
        "id": "INTEGER",
        "licitacion_id": "INTEGER",
        "status": "TEXT",
        "storage_backend": "TEXT",
        "storage_uri": "TEXT",
        "file_manifest": "TEXT",
        "error_message": "TEXT",
        "created_at": "TEXT",
        "started_at": "TEXT",
        "finished_at": "TEXT",
        "updated_at": "TEXT",
    }
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(download_jobs)").fetchall()
    }
    assert {
        "idx_download_jobs_licitacion",
        "idx_download_jobs_status",
        "idx_download_jobs_created",
    } <= indexes


def test_init_db_runs_migrations_on_temporary_database_only() -> None:
    app = load_app_module()
    existed_before = PRODUCTIVE_DB_PATH.exists()
    stat_before = PRODUCTIVE_DB_PATH.stat().st_mtime_ns if existed_before else None
    old_data_root = app.DATA_ROOT
    old_download_root = app.DOWNLOAD_ROOT
    old_db_path = app.DB_PATH

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        app.DATA_ROOT = tmp_root / "data"
        app.DOWNLOAD_ROOT = app.DATA_ROOT / "descargas"
        app.DB_PATH = app.DATA_ROOT / "infonalia.db"
        try:
            app.init_db()
            conn = sqlite3.connect(app.DB_PATH)
            try:
                assert table_exists(conn, MIGRATIONS_TABLE)
                assert applied_migration_versions(conn) == {migration.version for migration in MIGRATIONS}
            finally:
                conn.close()
        finally:
            app.DATA_ROOT = old_data_root
            app.DOWNLOAD_ROOT = old_download_root
            app.DB_PATH = old_db_path

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before
