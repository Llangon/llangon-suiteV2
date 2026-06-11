from __future__ import annotations

import tempfile
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from types import ModuleType, SimpleNamespace

from webapp.infonalia_webapp.tests.test_import_endpoints import (
    PRODUCTIVE_DB_PATH,
    load_app_module,
)


@contextmanager
def temporary_download_app(app: ModuleType):
    old_data_root = app.DATA_ROOT
    old_download_root = app.DOWNLOAD_ROOT
    old_db_path = app.DB_PATH
    old_launcher_path = app.LAUNCHER_PATH
    old_find_dropbox_root = app.find_dropbox_root

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        app.DATA_ROOT = tmp_root / "data"
        app.DOWNLOAD_ROOT = app.DATA_ROOT / "descargas"
        app.DB_PATH = app.DATA_ROOT / "infonalia.db"
        app.LAUNCHER_PATH = tmp_root / "Descargar_Licitacion.py"
        app.LAUNCHER_PATH.write_text("# fake launcher for tests\n", encoding="utf-8")
        app.find_dropbox_root = lambda: None
        app.init_db()
        try:
            yield tmp_root
        finally:
            app.DATA_ROOT = old_data_root
            app.DOWNLOAD_ROOT = old_download_root
            app.DB_PATH = old_db_path
            app.LAUNCHER_PATH = old_launcher_path
            app.find_dropbox_root = old_find_dropbox_root


def make_download_handler(app: ModuleType):
    handler = object.__new__(app.InfonaliaHandler)
    handler.headers = {}
    handler.responses = []
    handler.require_admin = lambda: True

    def send_json(payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, payload))

    handler.send_json = send_json
    return handler


def insert_fake_licitacion(
    app: ModuleType,
    *,
    enlace_perfil: str = "https://example.test/licitacion/1",
    ruta_carpeta: str = "",
) -> int:
    timestamp = datetime(2026, 6, 12, 10, 0, 0).isoformat()
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO licitaciones (
                expediente,
                objeto,
                organismo,
                provincia,
                fecha_limite,
                hora_limite,
                enlace_perfil,
                estado,
                ruta_carpeta,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TEST-DL-001",
                "Descarga ficticia",
                "Organismo ficticio",
                "Madrid",
                "2026-06-30",
                "12:00",
                enlace_perfil,
                "Descargar",
                ruta_carpeta,
                timestamp,
                timestamp,
            ),
        )
        return int(cur.lastrowid)


def get_ruta_carpeta(app: ModuleType, licitacion_id: int) -> str:
    with app.db_session() as conn:
        row = conn.execute("SELECT ruta_carpeta FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    return row["ruta_carpeta"] or ""


@contextmanager
def mocked_subprocess_run(app: ModuleType, fake_run):
    old_run = app.subprocess.run
    app.subprocess.run = fake_run
    try:
        yield
    finally:
        app.subprocess.run = old_run


def test_download_endpoint_success_updates_ruta_carpeta_with_mocked_subprocess() -> None:
    app = load_app_module()
    existed_before = PRODUCTIVE_DB_PATH.exists()
    stat_before = PRODUCTIVE_DB_PATH.stat().st_mtime_ns if existed_before else None

    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(
                {
                    "args": args,
                    "cwd": cwd,
                    "capture_output": capture_output,
                    "text": text,
                    "timeout": timeout,
                }
            )
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)

        assert status == HTTPStatus.OK
        assert payload["ok"] is True
        assert payload["codigo"] == 0
        assert ruta_carpeta
        assert ruta_carpeta == payload["ruta_carpeta"]
        assert Path(payload["carpeta"], "HTTP.url").exists()
        assert Path(payload["carpeta"], "documento-ficticio.pdf").exists()
        assert calls[0]["capture_output"] is True
        assert calls[0]["text"] is True
        assert calls[0]["timeout"] == app.MAX_DOWNLOAD_RUNTIME_SECONDS
        assert calls[0]["args"][-1] == "https://example.test/licitacion/1"

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_download_endpoint_failure_does_not_update_ruta_carpeta() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "salida-parcial.tmp").write_text("parcial", encoding="utf-8")
            return SimpleNamespace(returncode=2, stdout="", stderr="fallo ficticio")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.BAD_REQUEST
        assert payload["ok"] is False
        assert payload["codigo"] == 2
        assert "fallo ficticio" in payload["salida"]
        assert get_ruta_carpeta(app, licitacion_id) == ""


def test_download_endpoint_timeout_does_not_update_ruta_carpeta() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise app.subprocess.TimeoutExpired(cmd=args, timeout=timeout)

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.REQUEST_TIMEOUT
        assert "tardado demasiado" in payload["error"]
        assert get_ruta_carpeta(app, licitacion_id) == ""


def test_download_endpoint_folder_limit_failure_does_not_update_ruta_carpeta() -> None:
    app = load_app_module()
    old_max_file_count = app.MAX_DOWNLOAD_FILE_COUNT
    app.MAX_DOWNLOAD_FILE_COUNT = 1
    try:
        with temporary_download_app(app):
            licitacion_id = insert_fake_licitacion(app)

            def fake_run(args, cwd, capture_output, text, timeout):
                Path(cwd, "a.txt").write_text("a", encoding="utf-8")
                Path(cwd, "b.txt").write_text("b", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            handler = make_download_handler(app)
            with mocked_subprocess_run(app, fake_run):
                handler.api_download_licitacion(licitacion_id)

            status, payload = handler.responses[-1]

            assert status == HTTPStatus.BAD_REQUEST
            assert payload["ok"] is False
            assert "ficheros" in payload["error"]
            assert get_ruta_carpeta(app, licitacion_id) == ""
    finally:
        app.MAX_DOWNLOAD_FILE_COUNT = old_max_file_count


def test_download_endpoint_rejects_file_url_without_subprocess() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app, enlace_perfil="file:///tmp/documento.pdf")

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called for unsafe URLs")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.BAD_REQUEST
        assert "http o https" in payload["error"]
        assert get_ruta_carpeta(app, licitacion_id) == ""


def test_download_endpoint_rejects_empty_url_without_subprocess() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app, enlace_perfil="")

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called for empty URLs")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.BAD_REQUEST
        assert "enlace de perfil" in payload["error"]
        assert get_ruta_carpeta(app, licitacion_id) == ""


def test_download_endpoint_rejects_unsafe_destination_without_subprocess() -> None:
    app = load_app_module()
    with temporary_download_app(app) as tmp_root:
        unsafe_destination = str(tmp_root.parent / "fuera-de-descargas")
        licitacion_id = insert_fake_licitacion(app, ruta_carpeta=unsafe_destination)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called for unsafe destinations")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.BAD_REQUEST
        assert "fuera" in payload["error"]
        assert get_ruta_carpeta(app, licitacion_id) == unsafe_destination
