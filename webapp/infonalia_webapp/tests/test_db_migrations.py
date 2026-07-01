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
AI_JOB_PROGRESS_COLUMNS = {
    "progress_stage",
    "progress_message",
    "progress_percent",
    "heartbeat_at",
    "worker_pid",
    "started_by",
    "cancel_requested",
    "estimated_seconds",
}


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
        "0007_storage_uploads",
        "0008_licitaciones_center",
        "0009_licitaciones_estados_operativos",
        "0010_licitaciones_seguimiento_markers",
        "0011_monitor_licitaciones_v0",
        "0012_monitor_inventory_v05",
        "0013_ai_analysis_phase1",
        "0014_ai_jobs_dismissed",
        "0015_ai_jobs_progress",
        "0016_ai_analysis_notifications",
        "0017_comments_unified",
        "0018_email_action_codes",
        "0019_email_action_events",
        "0020_infonalia_email_imports",
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
        (
            "0007_storage_uploads",
            "Auditoria de almacenamiento local y Dropbox",
            "2026-06-12T10:00:00",
        ),
        (
            "0008_licitaciones_center",
            "Campos de trabajo, seguimiento e historial para licitaciones",
            "2026-06-12T10:00:00",
        ),
        (
            "0009_licitaciones_estados_operativos",
            "Normalizacion de estados operativos de licitaciones",
            "2026-06-12T10:00:00",
        ),
        (
            "0010_licitaciones_seguimiento_markers",
            "Cache derivada de marcadores Dropbox para seguimiento",
            "2026-06-12T10:00:00",
        ),
        (
            "0011_monitor_licitaciones_v0",
            "Monitor V0 local con runs e inventario de ficheros",
            "2026-06-12T10:00:00",
        ),
        (
            "0012_monitor_inventory_v05",
            "Clasificacion documental del inventario Monitor V0.5",
            "2026-06-12T10:00:00",
        ),
        (
            "0013_ai_analysis_phase1",
            "Analisis IA Gemini Fase 1 con jobs, summaries y usage log",
            "2026-06-12T10:00:00",
        ),
        (
            "0014_ai_jobs_dismissed",
            "Marca de descarte UI para jobs IA historicos",
            "2026-06-12T10:00:00",
        ),
        (
            "0015_ai_jobs_progress",
            "Campos de progreso y control para la cola IA",
            "2026-06-12T10:00:00",
        ),
        (
            "0016_ai_analysis_notifications",
            "Avisos por email asociados a jobs de analisis IA",
            "2026-06-12T10:00:00",
        ),
        (
            "0017_comments_unified",
            "Comentarios unificados por entidad",
            "2026-06-12T10:00:00",
        ),
        (
            "0018_email_action_codes",
            "Codigos de accion por correo para revision Infonalia",
            "2026-06-12T10:00:00",
        ),
        (
            "0019_email_action_events",
            "Auditoria de acciones por correo de revision Infonalia",
            "2026-06-12T10:00:00",
        ),
        (
            "0020_infonalia_email_imports",
            "Control idempotente de importaciones de correos Infonalia",
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
    assert table_exists(conn, "storage_uploads")
    assert table_exists(conn, "licitacion_historial")
    assert table_exists(conn, "licitacion_seguimiento_novedades")
    assert table_exists(conn, "monitor_runs")
    assert table_exists(conn, "licitacion_file_inventory")
    assert table_exists(conn, "monitor_vencimiento_alerts")
    assert table_exists(conn, "ai_analysis_jobs")
    assert table_exists(conn, "ai_summaries")
    assert table_exists(conn, "ai_usage_log")
    assert table_exists(conn, "ai_analysis_notifications")
    assert table_exists(conn, "comments")
    assert table_exists(conn, "email_action_codes")
    assert table_exists(conn, "email_action_events")
    assert table_exists(conn, "infonalia_email_imports")
    ai_job_columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_analysis_jobs)").fetchall()}
    assert {"dismissed_at", "dismissed_by"} | AI_JOB_PROGRESS_COLUMNS <= ai_job_columns
    assert not table_exists(conn, "licitacion_actuaciones")
    monitor_columns = {row[1] for row in conn.execute("PRAGMA table_info(monitor_runs)").fetchall()}
    assert {
        "task_type",
        "schedule_key",
        "processed_items_count",
        "folders_checked_count",
        "folders_repaired_count",
        "folders_broken_count",
        "platforms_checked_count",
        "changes_detected_count",
        "emails_prepared_count",
        "emails_sent_count",
        "details_json",
    } <= monitor_columns


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
        "0007_storage_uploads",
        "0008_licitaciones_center",
        "0009_licitaciones_estados_operativos",
        "0010_licitaciones_seguimiento_markers",
        "0011_monitor_licitaciones_v0",
        "0012_monitor_inventory_v05",
        "0013_ai_analysis_phase1",
        "0014_ai_jobs_dismissed",
        "0015_ai_jobs_progress",
        "0016_ai_analysis_notifications",
        "0017_comments_unified",
        "0018_email_action_codes",
        "0019_email_action_events",
        "0020_infonalia_email_imports",
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
        ("0007_storage_uploads", "2026-06-12T10:00:00"),
        ("0008_licitaciones_center", "2026-06-12T10:00:00"),
        ("0009_licitaciones_estados_operativos", "2026-06-12T10:00:00"),
        ("0010_licitaciones_seguimiento_markers", "2026-06-12T10:00:00"),
        ("0011_monitor_licitaciones_v0", "2026-06-12T10:00:00"),
        ("0012_monitor_inventory_v05", "2026-06-12T10:00:00"),
        ("0013_ai_analysis_phase1", "2026-06-12T10:00:00"),
        ("0014_ai_jobs_dismissed", "2026-06-12T10:00:00"),
        ("0015_ai_jobs_progress", "2026-06-12T10:00:00"),
        ("0016_ai_analysis_notifications", "2026-06-12T10:00:00"),
        ("0017_comments_unified", "2026-06-12T10:00:00"),
        ("0018_email_action_codes", "2026-06-12T10:00:00"),
        ("0019_email_action_events", "2026-06-12T10:00:00"),
        ("0020_infonalia_email_imports", "2026-06-12T10:00:00"),
    ]


def test_ai_jobs_progress_migration_updates_existing_phase1_database() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        f"""
        CREATE TABLE {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    old_migrations = [migration for migration in MIGRATIONS if migration.version != "0015_ai_jobs_progress"]
    conn.executemany(
        f"INSERT INTO {MIGRATIONS_TABLE} (version, description, applied_at) VALUES (?, ?, ?)",
        [(migration.version, migration.description, "2026-06-12T10:00:00") for migration in old_migrations],
    )
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT NOT NULL)")
    conn.execute("INSERT INTO licitaciones (id, expediente) VALUES (1, 'OLD-AI')")
    conn.execute(
        """
        CREATE TABLE ai_analysis_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            document_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'gemini',
            model TEXT,
            requested_by TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error_code TEXT,
            error_message TEXT,
            selected_documents_json TEXT,
            attempts INTEGER DEFAULT 0,
            next_retry_at TEXT,
            raw_usage_json TEXT,
            dismissed_at TEXT,
            dismissed_by TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO ai_analysis_jobs (
            id, licitacion_id, document_hash, status, provider, created_at, dismissed_at, dismissed_by
        )
        VALUES (7, 1, 'hash-antiguo', 'pending', 'gemini', '2026-06-12T10:00:00', NULL, NULL)
        """
    )

    columns_before = {row[1] for row in conn.execute("PRAGMA table_info(ai_analysis_jobs)").fetchall()}
    assert "progress_stage" not in columns_before

    assert run_migrations(conn, now=lambda: "2026-06-12T10:15:00") == ["0015_ai_jobs_progress"]

    columns_after = {row[1] for row in conn.execute("PRAGMA table_info(ai_analysis_jobs)").fetchall()}
    assert AI_JOB_PROGRESS_COLUMNS <= columns_after
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = 7").fetchone()
    assert row["document_hash"] == "hash-antiguo"
    assert row["status"] == "pending"
    assert row["cancel_requested"] == 0
    assert row["progress_stage"] is None
    assert "0015_ai_jobs_progress" in applied_migration_versions(conn)


def test_ai_notifications_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(ai_analysis_notifications)").fetchall()
    }
    assert columns == {
        "id": "INTEGER",
        "job_id": "INTEGER",
        "licitacion_id": "INTEGER",
        "requested_by": "TEXT",
        "recipient_email": "TEXT",
        "status": "TEXT",
        "created_at": "TEXT",
        "sent_at": "TEXT",
        "error_message": "TEXT",
        "attempts": "INTEGER",
        "manual": "INTEGER",
    }
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(ai_analysis_notifications)").fetchall()
    }
    assert {
        "idx_ai_notifications_job_recipient",
        "idx_ai_notifications_job",
        "idx_ai_notifications_licitacion",
        "idx_ai_notifications_status",
    } <= indexes


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


def test_storage_uploads_migration_schema_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(storage_uploads)").fetchall()
    }
    assert columns == {
        "id": "INTEGER",
        "licitacion_id": "INTEGER",
        "download_job_id": "INTEGER",
        "backend": "TEXT",
        "destination_uri": "TEXT",
        "manifest_json": "TEXT",
        "status": "TEXT",
        "dry_run": "INTEGER",
        "mode": "TEXT",
        "uploaded_count": "INTEGER",
        "skipped_existing_count": "INTEGER",
        "failed_count": "INTEGER",
        "no_changes": "INTEGER",
        "created_at": "TEXT",
        "completed_at": "TEXT",
        "error_message": "TEXT",
    }
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(storage_uploads)").fetchall()
    }
    assert {
        "idx_storage_uploads_licitacion",
        "idx_storage_uploads_job",
        "idx_storage_uploads_backend",
        "idx_storage_uploads_created",
    } <= indexes


def test_licitaciones_center_migration_prepares_followup_without_per_licitacion_recipients() -> None:
    conn = sqlite3.connect(":memory:")

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    run_migrations(conn, now=lambda: "2026-06-12T10:05:00")

    licitacion_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(licitaciones)").fetchall()
    }
    assert {
        "reviewed_at",
        "reviewed_by",
        "estado_interno",
        "notas_internas",
        "seguimiento_activo",
        "seguimiento_desde",
        "seguimiento_ultimo_check",
        "seguimiento_ultima_novedad",
        "seguimiento_notas",
        "seguimiento_ultima_sync",
        "seguimiento_marker_path",
        "seguimiento_marker_warning",
    } <= set(licitacion_columns)

    novedades_columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(licitacion_seguimiento_novedades)").fetchall()
    }
    assert novedades_columns == {
        "id": "INTEGER",
        "licitacion_id": "INTEGER",
        "detected_at": "TEXT",
        "source": "TEXT",
        "title": "TEXT",
        "summary": "TEXT",
        "change_type": "TEXT",
        "file_name": "TEXT",
        "file_path": "TEXT",
        "status": "TEXT",
        "raw_data_json": "TEXT",
    }
    assert not any("email" in column.lower() or "recipient" in column.lower() for column in novedades_columns)


def test_licitaciones_state_migration_normalizes_old_labels() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    run_migrations(conn, now=lambda: "2026-06-12T10:00:00")
    conn.executemany(
        "INSERT INTO licitaciones (expediente, estado) VALUES (?, ?)",
        [
            ("OLD-PENDIENTE", "Pendiente"),
            ("OLD-NURIA", "Pendiente Nuria"),
            ("OLD-DESCARGAR", "Descargar"),
            ("OLD-HACER", "Hacer"),
            ("OLD-DESCARTAR", "Descartar"),
            ("OLD-PRESENTADA", "Presentada"),
        ],
    )
    migration = [item for item in MIGRATIONS if item.version == "0009_licitaciones_estados_operativos"][0]

    migration.apply(conn)

    states = {
        row["expediente"]: row["estado"]
        for row in conn.execute("SELECT expediente, estado FROM licitaciones")
    }
    assert states == {
        "OLD-PENDIENTE": "Importada",
        "OLD-NURIA": "Enviada a Nuria",
        "OLD-DESCARGAR": "Descargar para ver",
        "OLD-HACER": "Preparar ficha",
        "OLD-DESCARTAR": "Descartada",
        "OLD-PRESENTADA": "Oferta enviada",
    }


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
