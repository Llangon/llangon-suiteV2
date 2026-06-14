from __future__ import annotations

import sqlite3
from http import HTTPStatus
from types import ModuleType

import pytest

from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import (
    count_rows,
    foreign_key_check_rows,
    insert_dia,
    insert_download_job,
    insert_import_result,
    insert_licitacion,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    temporary_app_database,
)


def make_delete_licitacion_handler(
    app: ModuleType,
    licitacion_id: int,
    *,
    csrf_token: str | None = VALID_CSRF_TOKEN,
):
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = f"/api/licitaciones/{licitacion_id}"
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


def delete_licitacion(app: ModuleType, licitacion_id: int, *, csrf_token: str | None = VALID_CSRF_TOKEN):
    handler = make_delete_licitacion_handler(app, licitacion_id, csrf_token=csrf_token)
    handler.do_DELETE()
    return handler


def test_delete_licitacion_without_dependents_removes_row() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-LIC-001")

        handler = delete_licitacion(app, licitacion_id)

        assert handler.responses == [(HTTPStatus.OK, {"ok": True})]
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "infonalia_dias") == 1
        assert foreign_key_check_rows(app) == []


def test_delete_licitacion_with_download_jobs_deletes_operational_jobs() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-LIC-DL")
        insert_download_job(app, licitacion_id)

        handler = delete_licitacion(app, licitacion_id)

        assert handler.responses == [(HTTPStatus.OK, {"ok": True})]
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "download_jobs") == 0
        assert foreign_key_check_rows(app) == []


def test_delete_licitacion_with_import_results_preserves_audit_and_unlinks_licitacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-LIC-IMPORT")
        result_id = insert_import_result(app, licitacion_id)

        handler = delete_licitacion(app, licitacion_id)

        assert handler.responses == [(HTTPStatus.OK, {"ok": True})]
        with app.db_session() as conn:
            result = conn.execute("SELECT * FROM import_results WHERE id = ?", (result_id,)).fetchone()
            assert result is not None
            assert result["licitacion_id"] is None
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "import_runs") == 1
        assert count_rows(app, "import_results") == 1
        assert foreign_key_check_rows(app) == []


def test_delete_missing_licitacion_returns_not_found() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = delete_licitacion(app, 999)

        assert handler.responses == [
            (HTTPStatus.NOT_FOUND, {"error": "Licitacion no encontrada"})
        ]
        assert foreign_key_check_rows(app) == []


def test_delete_licitacion_without_csrf_is_rejected_and_preserves_row() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-LIC-CSRF")

        handler = delete_licitacion(app, licitacion_id, csrf_token=None)

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert "CSRF" in handler.responses[-1][1]["error"]
        assert count_rows(app, "licitaciones") == 1
        assert foreign_key_check_rows(app) == []


def test_delete_licitacion_integrity_error_rolls_back_partial_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "TEST-LIC-ROLLBACK")
        insert_download_job(app, licitacion_id)
        original_delete_dependents = app.delete_licitacion_dependents

        def fail_after_dependent_delete(conn: sqlite3.Connection, licitacion_ids: list[int]) -> None:
            original_delete_dependents(conn, licitacion_ids)
            raise sqlite3.IntegrityError("forced test failure")

        monkeypatch.setattr(app, "delete_licitacion_dependents", fail_after_dependent_delete)
        try:
            handler = delete_licitacion(app, licitacion_id)
        finally:
            monkeypatch.setattr(app, "delete_licitacion_dependents", original_delete_dependents)

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "download_jobs") == 1
        assert foreign_key_check_rows(app) == []
