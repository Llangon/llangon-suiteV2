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
    enable_foreign_keys,
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


def foreign_keys_enabled(conn: sqlite3.Connection) -> bool:
    return conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_run_migrations_creates_table_and_records_baseline() -> None:
    conn = sqlite3.connect(":memory:")

    applied = run_migrations(conn, now=lambda: "2026-06-12T10:00:00")

    assert applied == [
        "0001_baseline_schema",
        "0002_download_jobs",
        "0003_import_history",
        "0004_actuaciones",
        "0005_actuaciones_multilicitacion",
        "0006_agenda_eventos",
    ]
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
        (
            "0003_import_history",
            "Tablas preparatorias para historial de importaciones",
            "2026-06-12T10:00:00",
        ),
        (
            "0004_actuaciones",
            "Tabla operativa para actuaciones y vencimientos",
            "2026-06-12T10:00:00",
        ),
        (
            "0005_actuaciones_multilicitacion",
            "Modelo independiente de actuaciones con vinculos multiples e historial",
            "2026-06-12T10:00:00",
        ),
        (
            "0006_agenda_eventos",
            "Eventos internos para Agenda operativa",
            "2026-06-12T10:00:00",
        ),
    ]
    assert table_exists(conn, "download_jobs")
    assert table_exists(conn, "import_runs")
    assert table_exists(conn, "import_results")
    assert table_exists(conn, "actuaciones")
    assert table_exists(conn, "actuacion_licitaciones")
    assert table_exists(conn, "actuacion_historial")
    assert table_exists(conn, "agenda_eventos")
    assert not table_exists(conn, "licitacion_actuaciones")


def test_run_migrations_enables_foreign_key_enforcement() -> None:
    conn = sqlite3.connect(":memory:")

    assert not foreign_keys_enabled(conn)

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")

    assert foreign_keys_enabled(conn)


def test_run_migrations_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    assert run_migrations(conn, now=lambda: "2026-06-12T10:00:00") == [
        "0001_baseline_schema",
        "0002_download_jobs",
        "0003_import_history",
        "0004_actuaciones",
        "0005_actuaciones_multilicitacion",
        "0006_agenda_eventos",
    ]
    assert run_migrations(conn, now=lambda: "2026-06-12T10:05:00") == []

    rows = conn.execute(f"SELECT version, applied_at FROM {MIGRATIONS_TABLE}").fetchall()
    assert rows == [
        ("0001_baseline_schema", "2026-06-12T10:00:00"),
        ("0002_download_jobs", "2026-06-12T10:00:00"),
        ("0003_import_history", "2026-06-12T10:00:00"),
        ("0004_actuaciones", "2026-06-12T10:00:00"),
        ("0005_actuaciones_multilicitacion", "2026-06-12T10:00:00"),
        ("0006_agenda_eventos", "2026-06-12T10:00:00"),
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


def test_import_history_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    run_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(import_runs)").fetchall()
    }
    assert run_columns == {
        "id": "INTEGER",
        "source_name": "TEXT",
        "source_type": "TEXT",
        "mode": "TEXT",
        "started_at": "TEXT",
        "finished_at": "TEXT",
        "status": "TEXT",
        "triggered_by": "TEXT",
        "input_name": "TEXT",
        "input_hash": "TEXT",
        "new_count": "INTEGER",
        "updated_count": "INTEGER",
        "duplicate_count": "INTEGER",
        "error_count": "INTEGER",
        "notes": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    result_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(import_results)").fetchall()
    }
    assert result_columns == {
        "id": "INTEGER",
        "import_run_id": "INTEGER",
        "source_name": "TEXT",
        "external_id": "TEXT",
        "fingerprint": "TEXT",
        "licitacion_id": "INTEGER",
        "status": "TEXT",
        "error_message": "TEXT",
        "raw_payload": "TEXT",
        "created_at": "TEXT",
    }
    run_indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(import_runs)").fetchall()
    }
    result_indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(import_results)").fetchall()
    }
    assert {
        "idx_import_runs_source_started",
        "idx_import_runs_status",
    } <= run_indexes
    assert {
        "idx_import_results_run",
        "idx_import_results_licitacion",
        "idx_import_results_source_external",
        "idx_import_results_fingerprint",
    } <= result_indexes


def test_actuaciones_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(actuaciones)").fetchall()
    }
    assert columns == {
        "id": "INTEGER",
        "tipo": "TEXT",
        "titulo": "TEXT",
        "descripcion": "TEXT",
        "estado": "TEXT",
        "deadline_at": "TEXT",
        "recordatorio_email": "INTEGER",
        "origen": "TEXT",
        "created_by": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "closed_at": "TEXT",
        "closed_by": "TEXT",
    }
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(actuaciones)").fetchall()
    }
    assert {
        "idx_actuaciones_estado",
        "idx_actuaciones_deadline",
        "idx_actuaciones_tipo",
    } <= indexes

    bridge_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(actuacion_licitaciones)").fetchall()
    }
    assert bridge_columns == {
        "actuacion_id": "INTEGER",
        "licitacion_id": "INTEGER",
        "created_at": "TEXT",
        "created_by": "TEXT",
    }
    bridge_indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(actuacion_licitaciones)").fetchall()
    }
    assert {
        "idx_actuacion_licitaciones_licitacion",
        "idx_actuacion_licitaciones_actuacion",
    } <= bridge_indexes
    bridge_fks = conn.execute("PRAGMA foreign_key_list(actuacion_licitaciones)").fetchall()
    assert sorted((row[2], row[3], row[4], row[6]) for row in bridge_fks) == [
        ("actuaciones", "actuacion_id", "id", "NO ACTION"),
        ("licitaciones", "licitacion_id", "id", "NO ACTION"),
    ]

    history_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(actuacion_historial)").fetchall()
    }
    assert history_columns == {
        "id": "INTEGER",
        "actuacion_id": "INTEGER",
        "user_id": "TEXT",
        "event_type": "TEXT",
        "comentario": "TEXT",
        "old_value": "TEXT",
        "new_value": "TEXT",
        "created_at": "TEXT",
    }
    history_indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(actuacion_historial)").fetchall()
    }
    assert "idx_actuacion_historial_actuacion" in history_indexes


def test_actuaciones_multilicitacion_accepts_none_one_and_many_links() -> None:
    conn = sqlite3.connect(":memory:")
    enable_foreign_keys(conn)
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT)")
    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    conn.executemany(
        "INSERT INTO licitaciones (id, expediente) VALUES (?, ?)",
        [(1, "A"), (2, "B")],
    )
    conn.execute(
        """
        INSERT INTO actuaciones (tipo, titulo, estado, created_at, updated_at)
        VALUES ('otro', 'Sin vinculo', 'pendiente', '2026-06-12T10:00:00', '2026-06-12T10:00:00')
        """
    )
    cur = conn.execute(
        """
        INSERT INTO actuaciones (tipo, titulo, estado, created_at, updated_at)
        VALUES ('otro', 'Con varios', 'pendiente', '2026-06-12T10:00:00', '2026-06-12T10:00:00')
        """
    )
    actuacion_id = int(cur.lastrowid)
    conn.executemany(
        """
        INSERT INTO actuacion_licitaciones (actuacion_id, licitacion_id, created_at)
        VALUES (?, ?, '2026-06-12T10:00:00')
        """,
        [(actuacion_id, 1), (actuacion_id, 2)],
    )

    assert conn.execute("SELECT COUNT(*) FROM actuaciones").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM actuacion_licitaciones").fetchone()[0] == 2
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_agenda_eventos_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(agenda_eventos)").fetchall()
    }
    assert columns == {
        "id": "INTEGER",
        "titulo": "TEXT",
        "descripcion": "TEXT",
        "starts_at": "TEXT",
        "estado": "TEXT",
        "created_by": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "closed_at": "TEXT",
        "closed_by": "TEXT",
    }
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(agenda_eventos)").fetchall()
    }
    assert {
        "idx_agenda_eventos_starts_at",
        "idx_agenda_eventos_estado",
        "idx_agenda_eventos_created_by",
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
            conn = app.db()
            try:
                assert foreign_keys_enabled(conn)
                assert table_exists(conn, MIGRATIONS_TABLE)
                assert applied_migration_versions(conn) == {migration.version for migration in MIGRATIONS}
                assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            finally:
                conn.close()
        finally:
            app.DATA_ROOT = old_data_root
            app.DOWNLOAD_ROOT = old_download_root
            app.DB_PATH = old_db_path

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_enable_foreign_keys_helper_sets_sqlite_pragma() -> None:
    conn = sqlite3.connect(":memory:")

    enable_foreign_keys(conn)

    assert foreign_keys_enabled(conn)
