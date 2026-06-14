from __future__ import annotations

import sqlite3
from datetime import datetime
from http import HTTPStatus
from types import ModuleType

import pytest

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
            (dia_id, "2026-06-14", expediente, "Servicio ficticio", "Pendiente", timestamp, timestamp),
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

        assert handler.responses == [
            (HTTPStatus.OK, {"ok": True, "titulo": "Infonalia 14/06/2026", "licitaciones_borradas": 0})
        ]
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
        original_delete_dependents = app.delete_licitacion_dependents

        def fail_after_dependent_delete(conn: sqlite3.Connection, licitacion_ids: list[int]) -> None:
            original_delete_dependents(conn, licitacion_ids)
            raise sqlite3.IntegrityError("forced test failure")

        monkeypatch.setattr(app, "delete_licitacion_dependents", fail_after_dependent_delete)
        try:
            handler = delete_dia(app, dia_id)
        finally:
            monkeypatch.setattr(app, "delete_licitacion_dependents", original_delete_dependents)

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "download_jobs") == 1
        assert foreign_key_check_rows(app) == []
