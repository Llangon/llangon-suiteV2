from __future__ import annotations

import importlib
import io
import os
import sys
import tempfile
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from types import ModuleType


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_MODULE_NAME = "webapp.infonalia_webapp.app"
PRODUCTIVE_DB_PATH = REPOSITORY_ROOT / "webapp" / "infonalia_webapp" / "data" / "infonalia.db"
VALID_CSRF_TOKEN = "csrf-test-token"


def load_app_module() -> ModuleType:
    os.environ["INFONALIA_ADMIN_USER"] = "admin_test"
    os.environ["INFONALIA_ADMIN_PASSWORD"] = "admin_password_test"
    os.environ["INFONALIA_REVIEWER_USER"] = "reviewer_test"
    os.environ["INFONALIA_REVIEWER_PASSWORD"] = "reviewer_password_test"
    os.environ["INFONALIA_ENABLE_ADMIN_ALIAS"] = "0"

    return importlib.import_module(APP_MODULE_NAME)


@contextmanager
def temporary_app_database(app: ModuleType):
    old_data_root = app.DATA_ROOT
    old_download_root = app.DOWNLOAD_ROOT
    old_db_path = app.DB_PATH

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        app.DATA_ROOT = tmp_root / "data"
        app.DOWNLOAD_ROOT = app.DATA_ROOT / "descargas"
        app.DB_PATH = app.DATA_ROOT / "infonalia.db"
        app.init_db()
        try:
            yield app.DB_PATH
        finally:
            app.DATA_ROOT = old_data_root
            app.DOWNLOAD_ROOT = old_download_root
            app.DB_PATH = old_db_path


def make_multipart_body(field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----infonalia-test-boundary"
    body = b"\r\n".join(
        [
            f"--{boundary}".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"'
            ).encode("utf-8"),
            b"Content-Type: application/octet-stream",
            b"",
            content,
            f"--{boundary}--".encode("ascii"),
            b"",
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def make_handler(
    app: ModuleType,
    body: bytes,
    content_type: str,
    content_length: int | None = None,
    *,
    path: str = "/api/import/csv",
    csrf_token: str | None = None,
):
    handler = object.__new__(app.InfonaliaHandler)
    handler.headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(body) if content_length is None else content_length),
    }
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.path = path
    handler.rfile = io.BytesIO(body)
    handler.responses = []
    handler.current_user = lambda: {
        "username": "admin_test",
        "role": "admin",
        "display_name": "Admin Test",
        "csrf_token": VALID_CSRF_TOKEN,
    }
    handler.require_admin = lambda: True

    def send_json(payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, payload))

    handler.send_json = send_json
    return handler


def valid_csv_bytes() -> bytes:
    return (
        "Fecha Infonalia;Expediente;Objeto;Organismo\n"
        "2026-06-12;TEST-001;Servicio ficticio;Organismo ficticio\n"
    ).encode("utf-8")


def get_import_runs(app: ModuleType) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute("SELECT * FROM import_runs ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_import_results(app: ModuleType, import_run_id: int) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM import_results WHERE import_run_id = ? ORDER BY id",
            (import_run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def test_app_import_does_not_start_server_or_create_productive_db() -> None:
    existed_before = PRODUCTIVE_DB_PATH.exists()
    stat_before = PRODUCTIVE_DB_PATH.stat().st_mtime_ns if existed_before else None

    app = load_app_module()

    assert hasattr(app, "run")
    assert hasattr(app, "InfonaliaHandler")
    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_csv_import_endpoint_accepts_small_valid_csv_with_temp_db() -> None:
    app = load_app_module()
    existed_before = PRODUCTIVE_DB_PATH.exists()
    stat_before = PRODUCTIVE_DB_PATH.stat().st_mtime_ns if existed_before else None
    body, content_type = make_multipart_body("csv_file", "licitaciones.csv", valid_csv_bytes())

    with temporary_app_database(app) as db_path:
        assert db_path != PRODUCTIVE_DB_PATH
        handler = make_handler(app, body, content_type)

        handler.api_import_csv()

        assert handler.responses
        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["importadas"] == 1
        assert payload["actualizadas"] == 0
        assert payload["omitidas"] == 0
        assert payload["sin_expediente"] == 0
        assert payload["dias"] == 1

        with app.db_session() as conn:
            row = conn.execute(
                "SELECT id, expediente, objeto, organismo, estado FROM licitaciones WHERE expediente = ?",
                ("TEST-001",),
            ).fetchone()

        assert row["objeto"] == "Servicio ficticio"
        assert row["organismo"] == "Organismo ficticio"
        assert row["estado"] == "Importada"
        runs = get_import_runs(app)
        assert len(runs) == 1
        assert runs[0]["source_name"] == "csv"
        assert runs[0]["source_type"] == "csv"
        assert runs[0]["mode"] == "manual"
        assert runs[0]["status"] == "completed"
        assert runs[0]["triggered_by"] == "admin_test"
        assert runs[0]["new_count"] == 1
        assert runs[0]["updated_count"] == 0
        assert runs[0]["duplicate_count"] == 0
        assert runs[0]["error_count"] == 0
        assert runs[0]["input_hash"]
        assert runs[0]["started_at"]
        assert runs[0]["finished_at"]
        results = get_import_results(app, runs[0]["id"])
        assert len(results) == 1
        assert results[0]["source_name"] == "csv"
        assert results[0]["external_id"] == "TEST-001"
        assert results[0]["status"] == "inserted"
        assert results[0]["licitacion_id"] == row["id"]
        assert results[0]["fingerprint"]
        assert "Servicio ficticio" in results[0]["raw_payload"]

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_csv_import_route_accepts_small_valid_csv_with_csrf() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "licitaciones.csv", valid_csv_bytes())

    with temporary_app_database(app):
        handler = make_handler(
            app,
            body,
            content_type,
            path="/api/import/csv",
            csrf_token=VALID_CSRF_TOKEN,
        )

        handler.do_POST()

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["importadas"] == 1
        assert payload["dias"] == 1


def test_msg_import_content_records_import_history_with_fake_msg(monkeypatch) -> None:
    app = load_app_module()

    class FakeMessage:
        date = "12/06/2026"
        body = """
        Ref. Infonalia: 123
        Perfil del contratante: https://example.test/perfil
        Expediente: MSG-001
        Organismo: Organismo MSG
        Objeto del contrato: Servicio MSG ficticio
        Provincia: Madrid
        Plazo presentacion: 30/06/2026
        Presupuesto: 1234,56
        """

        def __init__(self, _path: str) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setitem(sys.modules, "extract_msg", type("FakeExtractMsg", (), {"Message": FakeMessage}))

    with temporary_app_database(app):
        payload = app.import_msg_content(b"msg ficticio", enrich_pdf=False, triggered_by="admin_test")

        assert payload["importadas"] == 1
        assert payload["actualizadas"] == 0
        assert payload["omitidas"] == 0
        assert payload["fecha_infonalia"] == "2026-06-12"

        runs = get_import_runs(app)
        assert len(runs) == 1
        assert runs[0]["source_name"] == "email_infonalia"
        assert runs[0]["source_type"] == "email_infonalia"
        assert runs[0]["status"] == "completed"
        assert runs[0]["triggered_by"] == "admin_test"
        assert runs[0]["new_count"] == 1

        results = get_import_results(app, runs[0]["id"])
        assert len(results) == 1
        assert results[0]["source_name"] == "email_infonalia"
        assert results[0]["external_id"] == "MSG-001"
        assert results[0]["status"] == "inserted"
        assert "Servicio MSG ficticio" in results[0]["raw_payload"]


def test_csv_import_route_rejects_missing_csrf_before_importing() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "licitaciones.csv", valid_csv_bytes())
    handler = make_handler(app, body, content_type, path="/api/import/csv")

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_csv_import_route_rejects_invalid_csrf_before_importing() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "licitaciones.csv", valid_csv_bytes())
    handler = make_handler(app, body, content_type, path="/api/import/csv", csrf_token="wrong-token")

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_csv_import_endpoint_rejects_wrong_extension() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "licitaciones.exe", valid_csv_bytes())
    handler = make_handler(app, body, content_type)

    handler.api_import_csv()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert "Extension" in payload["error"]


def test_csv_import_endpoint_rejects_unsafe_filename() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "../licitaciones.csv", valid_csv_bytes())
    handler = make_handler(app, body, content_type)

    handler.api_import_csv()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert "ruta" in payload["error"].lower() or "rutas" in payload["error"].lower()


def test_csv_import_endpoint_rejects_body_above_limit_without_large_file() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("csv_file", "licitaciones.csv", valid_csv_bytes())
    handler = make_handler(app, body, content_type, content_length=app.MAX_BODY_BYTES + 1)

    handler.api_import_csv()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert "maximo" in payload["error"]


def test_msg_import_endpoint_rejects_wrong_extension_without_parsing_msg() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "licitaciones.exe", b"msg ficticio")
    handler = make_handler(app, body, content_type)

    handler.api_import_msg()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert "Extension" in payload["error"]


def test_msg_import_route_with_valid_csrf_reaches_extension_validation() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "licitaciones.exe", b"msg ficticio")
    handler = make_handler(
        app,
        body,
        content_type,
        path="/api/import/msg",
        csrf_token=VALID_CSRF_TOKEN,
    )

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert "Extension" in payload["error"]


def test_msg_import_route_rejects_missing_csrf_before_validation() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "licitaciones.exe", b"msg ficticio")
    handler = make_handler(app, body, content_type, path="/api/import/msg")

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_msg_import_route_rejects_invalid_csrf_before_validation() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "licitaciones.exe", b"msg ficticio")
    handler = make_handler(app, body, content_type, path="/api/import/msg", csrf_token="wrong-token")

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_msg_import_endpoint_rejects_unsafe_filename_without_parsing_msg() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "..\\licitaciones.msg", b"msg ficticio")
    handler = make_handler(app, body, content_type)

    handler.api_import_msg()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert "ruta" in payload["error"].lower() or "rutas" in payload["error"].lower()


def test_msg_import_endpoint_rejects_body_above_limit_without_large_file() -> None:
    app = load_app_module()
    body, content_type = make_multipart_body("msg_file", "licitaciones.msg", b"msg ficticio")
    handler = make_handler(app, body, content_type, content_length=app.MAX_BODY_BYTES + 1)

    handler.api_import_msg()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert "maximo" in payload["error"]
