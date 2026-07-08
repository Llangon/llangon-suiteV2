from __future__ import annotations

import sqlite3
from datetime import datetime
from http import HTTPStatus
from types import ModuleType

import pytest

from webapp.infonalia_webapp.ai.queue import ensure_ai_schema
from webapp.infonalia_webapp.comments import ensure_comments_schema
from webapp.infonalia_webapp.email_actions import ensure_email_action_schema
from webapp.infonalia_webapp.infonalia_mail_importer import ensure_infonalia_email_import_schema
from webapp.infonalia_webapp.monitor.repository import ensure_monitor_schema
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    temporary_app_database,
)


def make_delete_dia_handler(app: ModuleType, dia_id: int, *, csrf_token: str | None = VALID_CSRF_TOKEN):
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = f"/api/dias/{dia_id}"
    handler.headers = {}
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.responses = []
    handler.errors = []
    handler.current_user = lambda: {
        "username": "admin_test",
        "role": "admin",
        "display_name": "Admin Test",
        "csrf_token": VALID_CSRF_TOKEN,
    }

    def send_json(payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    handler.send_json = send_json
    handler.send_error = send_error
    return handler


def make_get_handler(app: ModuleType, path: str):
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = path
    handler.headers = {}
    handler.responses = []
    handler.errors = []

    def send_json(payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    handler.send_json = send_json
    handler.send_error = send_error
    handler.current_user = lambda: None
    handler.redirect = lambda _path: handler.errors.append((HTTPStatus.FOUND, "redirect"))
    return handler


def insert_dia(app: ModuleType) -> int:
    timestamp = datetime(2026, 6, 14, 10, 0, 0).isoformat()
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO infonalia_dias (fecha, titulo, estado, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2026-06-14", "Infonalia 14/06/2026", "Importado", timestamp, timestamp),
        )
        return int(cur.lastrowid)


def insert_licitacion(app: ModuleType, dia_id: int, expediente: str) -> int:
    timestamp = datetime(2026, 6, 14, 10, 5, 0).isoformat()
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO licitaciones (
                infonalia_dia_id, fecha_infonalia, expediente, objeto, estado, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (dia_id, "2026-06-14", expediente, "Servicio ficticio", "Importada", timestamp, timestamp),
        )
        return int(cur.lastrowid)


def insert_download_job(app: ModuleType, licitacion_id: int) -> int:
    timestamp = datetime(2026, 6, 14, 10, 10, 0).isoformat()
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO download_jobs (licitacion_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (licitacion_id, "completed", timestamp, timestamp),
        )
        return int(cur.lastrowid)


def insert_import_result(app: ModuleType, licitacion_id: int) -> int:
    timestamp = datetime(2026, 6, 14, 10, 15, 0).isoformat()
    with app.db_session() as conn:
        run_cur = conn.execute(
            """
            INSERT INTO import_runs (
                source_name, source_type, mode, started_at, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("test", "csv", "manual", timestamp, "completed", timestamp, timestamp),
        )
        result_cur = conn.execute(
            """
            INSERT INTO import_results (
                import_run_id, source_name, external_id, fingerprint, licitacion_id, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(run_cur.lastrowid), "test", "ext-1", "fingerprint-1", licitacion_id, "created", timestamp),
        )
        return int(result_cur.lastrowid)


def insert_storage_upload(app: ModuleType, licitacion_id: int, download_job_id: int) -> int:
    timestamp = datetime(2026, 6, 14, 10, 20, 0).isoformat()
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO storage_uploads (
                licitacion_id, download_job_id, backend, status, dry_run, mode,
                uploaded_count, skipped_existing_count, failed_count, no_changes, created_at
            )
            VALUES (?, ?, ?, ?, 0, ?, 1, 0, 0, 0, ?)
            """,
            (licitacion_id, download_job_id, "local", "completed", "download", timestamp),
        )
        return int(cur.lastrowid)


def count_rows(app: ModuleType, table: str) -> int:
    with app.db_session() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def foreign_key_check_rows(app: ModuleType) -> list[sqlite3.Row]:
    with app.db_session() as conn:
        return conn.execute("PRAGMA foreign_key_check").fetchall()


def delete_dia(app: ModuleType, dia_id: int, *, csrf_token: str | None = VALID_CSRF_TOKEN):
    handler = make_delete_dia_handler(app, dia_id, csrf_token=csrf_token)
    handler.do_DELETE()
    return handler


def test_delete_dia_without_licitaciones_removes_day() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert handler.responses[-1][1]["ok"] is True
        assert handler.responses[-1][1]["titulo"] == "Infonalia 14/06/2026"
        assert handler.responses[-1][1]["licitaciones_borradas"] == 0
        assert handler.responses[-1][1]["deleted"]["licitaciones"] == 0
        assert count_rows(app, "infonalia_dias") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_missing_dia_returns_not_found() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = delete_dia(app, 999)

        assert handler.responses == [
            (HTTPStatus.NOT_FOUND, {"error": "Dia Infonalia no encontrado"})
        ]


def test_delete_dia_with_simple_licitaciones_removes_day_and_licitaciones() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "TEST-DIA-001")
        insert_licitacion(app, dia_id, "TEST-DIA-002")

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert handler.responses[-1][1]["licitaciones_borradas"] == 2
        assert count_rows(app, "infonalia_dias") == 0
        assert count_rows(app, "licitaciones") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_download_jobs_deletes_operational_jobs() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-DIA-DL")
        insert_download_job(app, licitacion_id)

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "infonalia_dias") == 0
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "download_jobs") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_storage_uploads_deletes_uploads_before_jobs() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-DIA-STORAGE")
        download_job_id = insert_download_job(app, licitacion_id)
        insert_storage_upload(app, licitacion_id, download_job_id)

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert handler.responses[-1][1]["deleted"]["storage_uploads"] == 1
        assert handler.responses[-1][1]["deleted"]["download_jobs"] == 1
        assert count_rows(app, "storage_uploads") == 0
        assert count_rows(app, "download_jobs") == 0
        assert count_rows(app, "licitaciones") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_import_results_preserves_audit_and_unlinks_licitacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-DIA-IMPORT")
        result_id = insert_import_result(app, licitacion_id)

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        with app.db_session() as conn:
            result = conn.execute("SELECT * FROM import_results WHERE id = ?", (result_id,)).fetchone()
            assert result is not None
            assert result["licitacion_id"] is None
        assert count_rows(app, "infonalia_dias") == 0
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "import_runs") == 1
        assert count_rows(app, "import_results") == 1
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_ai_inventory_comments_and_email_records_is_controlled() -> None:
    app = load_app_module()
    timestamp = datetime(2026, 6, 14, 10, 30, 0).isoformat()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-DIA-DEPS")
        with app.db_session() as conn:
            ensure_ai_schema(conn)
            ensure_monitor_schema(conn)
            ensure_comments_schema(conn)
            ensure_email_action_schema(conn)
            ensure_infonalia_email_import_schema(conn)
            job_id = conn.execute(
                """
                INSERT INTO ai_analysis_jobs (
                    licitacion_id, document_hash, status, provider, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (licitacion_id, "hash-1", "completed", "gemini", timestamp),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO ai_summaries (
                    licitacion_id, document_hash, provider, summary_json, summary_text,
                    created_at, updated_at, created_from_job_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (licitacion_id, "hash-1", "gemini", "{}", "Resumen", timestamp, timestamp, job_id),
            )
            conn.execute(
                """
                INSERT INTO ai_usage_log (
                    provider, created_at, status, licitacion_id, job_id
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("gemini", timestamp, "completed", licitacion_id, job_id),
            )
            conn.execute(
                """
                INSERT INTO licitacion_file_inventory (
                    licitacion_id, folder_path, relative_path, file_name,
                    discovered_at, last_seen_at, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (licitacion_id, "C:/fake", "doc.pdf", "doc.pdf", timestamp, timestamp, "local_dropbox"),
            )
            conn.execute(
                """
                INSERT INTO licitacion_path_reconciliation_events (
                    licitacion_id, created_at, result
                )
                VALUES (?, ?, ?)
                """,
                (licitacion_id, timestamp, "matched"),
            )
            conn.execute(
                """
                INSERT INTO comments (
                    entity_type, entity_id, body, author_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("licitacion", licitacion_id, "Comentario", "admin", timestamp, timestamp),
            )
            conn.execute(
                """
                INSERT INTO email_action_codes (
                    code, review_id, licitacion_id, action_code, action_name, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("CODE-DEP", dia_id, licitacion_id, "descargar", "Descargar", "pending", timestamp),
            )
            conn.execute(
                """
                INSERT INTO email_action_events (
                    created_at, review_id, licitacion_id, result
                )
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, dia_id, licitacion_id, "received"),
            )
            conn.execute(
                """
                INSERT INTO infonalia_email_imports (
                    created_at, processed_at, message_id, body_hash, status, infonalia_dia_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, timestamp, "<msg-delete@example.test>", "body-hash-delete", "imported", dia_id),
            )

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        payload = handler.responses[-1][1]
        assert payload["deleted"]["ai_analysis_jobs"] == 1
        assert payload["deleted"]["ai_summaries"] == 1
        assert payload["deleted"]["ai_usage_log"] == 1
        assert payload["deleted"]["licitacion_file_inventory"] == 1
        assert payload["deleted"]["email_action_codes"] == 1
        assert payload["deleted"]["email_action_events"] == 1
        assert payload["deleted"]["comments_deleted"] == 1
        assert payload["deleted"]["infonalia_email_imports_unlinked"] == 1
        with app.db_session() as conn:
            comment = conn.execute("SELECT is_deleted FROM comments").fetchone()
            event = conn.execute("SELECT licitacion_id FROM licitacion_path_reconciliation_events").fetchone()
            mail_import = conn.execute("SELECT status, infonalia_dia_id FROM infonalia_email_imports").fetchone()
        assert comment["is_deleted"] == 1
        assert event["licitacion_id"] is None
        assert mail_import["status"] == "deleted"
        assert mail_import["infonalia_dia_id"] is None
        assert count_rows(app, "licitaciones") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_dia_imported_email_can_be_reimported_after_delete() -> None:
    app = load_app_module()
    timestamp = datetime(2026, 6, 14, 10, 40, 0).isoformat()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "TEST-DIA-REIMPORT")
        with app.db_session() as conn:
            ensure_infonalia_email_import_schema(conn)
            conn.execute(
                """
                INSERT INTO infonalia_email_imports (
                    created_at, processed_at, message_id, body_hash, status, infonalia_dia_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, timestamp, "<msg-reimport@example.test>", "hash-reimport", "imported", dia_id),
            )

        handler = delete_dia(app, dia_id)

        assert handler.responses[-1][0] == HTTPStatus.OK
        with app.db_session() as conn:
            row = conn.execute(
                "SELECT status, infonalia_dia_id FROM infonalia_email_imports WHERE message_id = ?",
                ("<msg-reimport@example.test>",),
            ).fetchone()
        assert row["status"] == "deleted"
        assert row["infonalia_dia_id"] is None


def test_notificaciones_do_not_reference_days_or_licitaciones() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        with app.db_session() as conn:
            assert conn.execute("PRAGMA foreign_key_list(notificaciones)").fetchall() == []


def test_delete_dia_without_csrf_is_rejected_and_preserves_day() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)

        handler = delete_dia(app, dia_id, csrf_token=None)

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert "CSRF" in handler.responses[-1][1]["error"]
        assert count_rows(app, "infonalia_dias") == 1


def test_delete_dia_integrity_error_rolls_back_partial_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-DIA-ROLLBACK")
        insert_download_job(app, licitacion_id)
        original_delete_dependents = app.delete_licitacion_dependents_with_counts

        def fail_after_dependent_delete(conn: sqlite3.Connection, licitacion_ids: list[int]) -> dict[str, int]:
            original_delete_dependents(conn, licitacion_ids)
            raise sqlite3.IntegrityError("forced test failure")

        monkeypatch.setattr(app, "delete_licitacion_dependents_with_counts", fail_after_dependent_delete)
        try:
            handler = delete_dia(app, dia_id)
        finally:
            monkeypatch.setattr(app, "delete_licitacion_dependents_with_counts", original_delete_dependents)

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "download_jobs") == 1
        assert foreign_key_check_rows(app) == []


def test_delete_dia_unexpected_error_returns_json_and_health_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "TEST-DIA-UNEXPECTED")
        original_delete_dependents = app.delete_licitacion_dependents_with_counts

        def fail_delete(_conn: sqlite3.Connection, _licitacion_ids: list[int]) -> dict[str, int]:
            raise RuntimeError("fallo inesperado controlado")

        monkeypatch.setattr(app, "delete_licitacion_dependents_with_counts", fail_delete)
        try:
            handler = delete_dia(app, dia_id)
        finally:
            monkeypatch.setattr(app, "delete_licitacion_dependents_with_counts", original_delete_dependents)

        assert handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert handler.responses[-1][1]["ok"] is False
        assert "cancelado de forma segura" in handler.responses[-1][1]["error"]
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1
        assert foreign_key_check_rows(app) == []

        health = make_get_handler(app, "/api/health")
        health.do_GET()
        assert health.responses[-1] == (HTTPStatus.OK, {"status": "ok"})
