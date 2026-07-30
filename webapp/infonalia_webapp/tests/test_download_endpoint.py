from __future__ import annotations

import json
import io
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    PRODUCTIVE_DB_PATH,
    VALID_CSRF_TOKEN,
    load_app_module,
)


@pytest.fixture(autouse=True)
def default_download_storage_env(monkeypatch):
    monkeypatch.setenv("INFONALIA_STORAGE_BACKEND", "local")
    monkeypatch.delenv("INFONALIA_DOWNLOAD_STAGING_ROOT", raising=False)
    monkeypatch.delenv("LLANGON_DROPBOX_BASE_PATH", raising=False)


@contextmanager
def temporary_download_app(app: ModuleType):
    old_data_root = app.DATA_ROOT
    old_download_root = app.DOWNLOAD_ROOT
    old_db_path = app.DB_PATH
    old_launcher_path = app.LAUNCHER_PATH
    old_find_dropbox_root = app.find_dropbox_root
    old_marker_allowed_roots = getattr(app, "marker_allowed_roots", None)
    old_marker_dropbox_root = getattr(app, "marker_dropbox_root", None)

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
            if old_marker_allowed_roots is not None:
                app.marker_allowed_roots = old_marker_allowed_roots
            if old_marker_dropbox_root is not None:
                app.marker_dropbox_root = old_marker_dropbox_root


def make_download_handler(
    app: ModuleType,
    *,
    path: str = "/api/licitaciones/1/descargar",
    csrf_token: str | None = None,
    payload: dict | None = None,
):
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    handler = object.__new__(app.InfonaliaHandler)
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
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


def suggested_download_folder_name(app: ModuleType, licitacion_id: int) -> str:
    return default_download_destination(app, licitacion_id).name


def default_download_destination(app: ModuleType, licitacion_id: int) -> Path:
    with app.db_session() as conn:
        row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    return app.resolve_destination_folder(row)


def confirmed_download_payload(app: ModuleType, licitacion_id: int, folder_name: str | None = None) -> dict:
    return {"folder_name_confirmed": folder_name or suggested_download_folder_name(app, licitacion_id)}


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


def get_download_jobs(app: ModuleType, licitacion_id: int) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM download_jobs WHERE licitacion_id = ? ORDER BY id",
            (licitacion_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_storage_uploads(app: ModuleType, licitacion_id: int) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM storage_uploads WHERE licitacion_id = ? ORDER BY id",
            (licitacion_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_download_dia_as_reviewed(app: ModuleType, dia_id: int) -> None:
    timestamp = datetime(2026, 6, 14, 12, 0, 0).isoformat()
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE infonalia_dias
            SET estado = 'Completado',
                reviewed_at = ?,
                nuria_dirty_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, dia_id),
        )


def get_download_dia_review_state(app: ModuleType, dia_id: int) -> dict:
    with app.db_session() as conn:
        row = conn.execute(
            "SELECT estado, reviewed_at, nuria_dirty_at FROM infonalia_dias WHERE id = ?",
            (dia_id,),
        ).fetchone()
        return dict(row)


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

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
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
        bat_path = Path(payload["carpeta"], "Descargar ficheros de la plataforma.bat")
        assert bat_path.exists()
        bat_content = bat_path.read_text(encoding="utf-8")
        assert str(app.LAUNCHER_PATH.resolve()) in bat_content
        assert str(Path(sys.executable).resolve()) in bat_content
        assert '"%PYTHON%" "%SCRIPT%"' in bat_content
        assert Path(payload["carpeta"], "documento-ficticio.pdf").exists()
        assert Path(payload["carpeta"], f"{licitacion_id}.llangon").exists()
        assert not Path(payload["carpeta"], "EnSeguimiento.llangon").exists()
        assert payload["marker"]["path"].endswith(f"{licitacion_id}.llangon")
        manifest_path = Path(payload["carpeta"], ".infonalia_manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["schema"] == "infonalia.download_manifest.v1"
        assert manifest["source_url"] == "https://example.test/licitacion/1"
        assert sorted(item["path"] for item in manifest["files"]) == [
            "Descargar ficheros de la plataforma.bat",
            "HTTP.url",
            "documento-ficticio.pdf",
        ]
        jobs = get_download_jobs(app, licitacion_id)
        assert len(jobs) == 1
        assert jobs[0]["status"] == "completed"
        assert jobs[0]["storage_backend"] == "local"
        assert jobs[0]["storage_uri"].startswith("local://")
        assert jobs[0]["file_manifest"].endswith(".infonalia_manifest.json")
        assert jobs[0]["error_message"] is None
        assert jobs[0]["started_at"]
        assert jobs[0]["finished_at"]
        assert calls[0]["capture_output"] is True
        assert calls[0]["text"] is True
        assert calls[0]["timeout"] == app.MAX_DOWNLOAD_RUNTIME_SECONDS
        assert calls[0]["args"][-1] == "https://example.test/licitacion/1"
        uploads = get_storage_uploads(app, licitacion_id)
        assert len(uploads) == 1
        assert uploads[0]["backend"] == "local"
        assert uploads[0]["status"] == "completed"

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_normal_download_endpoint_does_not_update_monitor_baseline_or_notify() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            document_path = Path(cwd, "acta.pdf")
            document_path.write_bytes(b"acta")
            structured = {
                "platform": "PLACE",
                "source_url": "https://example.test/licitacion/1",
                "started_at": "2026-07-20T09:00:00",
                "finished_at": "2026-07-20T09:01:00",
                "status": "success",
                "capabilities": {"documents": True, "questions_and_answers": False},
                "tender_id": "TEST-DL-001",
                "artifacts": [
                    {
                        "name": "acta.pdf",
                        "path": str(document_path),
                        "sha256": "hash-acta",
                        "source_url": "https://example.test/docs/acta.pdf",
                        "role": "document",
                    }
                ],
            }
            return SimpleNamespace(
                returncode=0,
                stdout="RESULTADO_ESTRUCTURADO=" + json.dumps(structured),
                stderr="",
            )

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)
        destination = Path(handler.responses[-1][1]["carpeta"])
        sidecar = destination / ".llangon-monitor" / "technical_snapshot.json"
        sidecar_exists = sidecar.is_file()
        with app.db_session() as conn:
            baseline_count = conn.execute("SELECT COUNT(*) FROM tender_monitor_baselines").fetchone()[0]
            snapshot_count = conn.execute("SELECT COUNT(*) FROM tender_monitor_snapshots").fetchone()[0]
            batch_count = conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0]
            notification_count = conn.execute("SELECT COUNT(*) FROM tender_monitor_notifications").fetchone()[0]

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert sidecar_exists is False
    assert baseline_count == 0
    assert snapshot_count == 0
    assert batch_count == 0
    assert notification_count == 0


def test_manual_download_returns_conflict_when_monitor_holds_shared_lease() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO tender_monitor_leases (
                    lease_key, owner, acquired_at, heartbeat_at, expires_at, metadata_json
                ) VALUES (?, 'monitor:test', '2026-07-22T10:00:00', '2026-07-22T10:00:00',
                          '2999-01-01T00:00:00', '{}')
                """,
                (f"tender-io:licitacion:{licitacion_id}",),
            )
        handler = make_download_handler(
            app,
            payload=confirmed_download_payload(app, licitacion_id),
        )

        handler.api_download_licitacion(licitacion_id)

        jobs = get_download_jobs(app, licitacion_id)
        with app.db_session() as conn:
            baseline_count = conn.execute("SELECT COUNT(*) FROM tender_monitor_baselines").fetchone()[0]

    assert handler.responses[-1][0] == HTTPStatus.CONFLICT
    assert handler.responses[-1][1]["deferred"] is False
    assert jobs[0]["status"] == "failed"
    assert baseline_count == 0


def test_email_download_job_is_requeued_when_monitor_holds_shared_lease() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        with app.db_session() as conn:
            request = app.create_download_job_request(
                conn,
                licitacion_id,
                timestamp=app.now_iso(),
                request_source="email",
                request_action="02",
                request_message_id="<busy-test>",
                requested_by="nuria",
            )
            job_id = int(request["job_id"])
            conn.execute(
                """
                INSERT INTO tender_monitor_leases (
                    lease_key, owner, acquired_at, heartbeat_at, expires_at, metadata_json
                ) VALUES (?, 'monitor:test', '2026-07-22T10:00:00', '2026-07-22T10:00:00',
                          '2999-01-01T00:00:00', '{}')
                """,
                (f"tender-io:licitacion:{licitacion_id}",),
            )

        result = app.process_download_job(job_id)
        jobs = get_download_jobs(app, licitacion_id)

    assert result["ok"] is True
    assert result["status"] == "pending"
    assert jobs[0]["status"] == "pending"


def test_download_endpoint_keeps_reviewed_day_closed() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_fake_licitacion(app)
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET infonalia_dia_id = ? WHERE id = ?",
                (dia_id, licitacion_id),
            )
        mark_download_dia_as_reviewed(app, dia_id)

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        state = get_download_dia_review_state(app, dia_id)

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert state["estado"] == "Completado"
    assert state["reviewed_at"]
    assert not state["nuria_dirty_at"]


def test_download_endpoint_dropbox_dry_run_records_incremental_storage(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    monkeypatch.setenv("INFONALIA_STORAGE_BACKEND", "dropbox")
    monkeypatch.setenv("INFONALIA_DOWNLOAD_STAGING_ROOT", str(tmp_path / "staging"))
    monkeypatch.setenv("INFONALIA_DROPBOX_ENABLED", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_DRY_RUN", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_API_ROOT", "/LlangonSuite")

    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["storage"]["backend"] == "dropbox"
        assert payload["storage"]["dry_run"] is True
        assert payload["storage"]["would_upload_count"] == 3
        assert payload["storage"]["storage_uri"] == "dropbox://LlangonSuite/Licitaciones/TEST-DL-001_1"
        jobs = get_download_jobs(app, licitacion_id)
        assert jobs[0]["storage_backend"] == "dropbox"
        assert jobs[0]["storage_uri"] == "dropbox://LlangonSuite/Licitaciones/TEST-DL-001_1"
        assert "infonalia_dropbox_manifest" in jobs[0]["file_manifest"]
        uploads = get_storage_uploads(app, licitacion_id)
        assert uploads[0]["backend"] == "dropbox"
        assert uploads[0]["dry_run"] == 1
        assert uploads[0]["uploaded_count"] == 0
        assert uploads[0]["skipped_existing_count"] == 0
        assert uploads[0]["failed_count"] == 0


def test_download_endpoint_dropbox_backend_uses_staging_outside_dropbox_desktop(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    staging_root = tmp_path / "staging-downloads"
    replica_root = tmp_path / "ReplicaDb"
    replica_root.mkdir(parents=True)
    monkeypatch.setenv("INFONALIA_STORAGE_BACKEND", "dropbox")
    monkeypatch.setenv("INFONALIA_DOWNLOAD_STAGING_ROOT", str(staging_root))
    monkeypatch.setenv("INFONALIA_DROPBOX_ENABLED", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_DRY_RUN", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_API_ROOT", "/LlangonSuite")

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: replica_root
        licitacion_id = insert_fake_licitacion(app, ruta_carpeta=str(replica_root / "ruta-antigua"))
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        cwd = calls[0].resolve()
        assert status == HTTPStatus.OK
        assert cwd.is_relative_to(staging_root.resolve())
        assert not cwd.is_relative_to(replica_root.resolve())
        assert Path(payload["carpeta"]).resolve() == cwd
        assert get_download_jobs(app, licitacion_id)[0]["storage_backend"] == "dropbox"


def test_download_route_success_with_valid_csrf_and_mocked_subprocess() -> None:
    app = load_app_module()

    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(
            app,
            path=f"/api/licitaciones/{licitacion_id}/descargar",
            csrf_token=VALID_CSRF_TOKEN,
            payload=confirmed_download_payload(app, licitacion_id),
        )
        with mocked_subprocess_run(app, fake_run):
            handler.do_POST()

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["ok"] is True
        assert get_ruta_carpeta(app, licitacion_id) == payload["ruta_carpeta"]


def test_download_existing_folder_does_not_request_confirmation() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        destination = default_download_destination(app, licitacion_id)
        destination.mkdir(parents=True)
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(cwd)
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert "needs_folder_confirmation" not in payload
    assert calls == [str(destination)]


@pytest.mark.parametrize("stale_confirmation", [False, True])
def test_download_reuses_folder_found_by_unique_id_marker(stale_confirmation: bool, tmp_path: Path) -> None:
    app = load_app_module()
    dropbox_root = tmp_path / "00000 LLANGON"
    marker_folder = dropbox_root / "2026" / "07 JULIO" / "24 JULIO 1400 BARCELONA HOSP BELLVITGE"
    marker_folder.mkdir(parents=True)

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: dropbox_root
        licitacion_id = insert_fake_licitacion(
            app,
            ruta_carpeta=r"2026\07 JULIO\BARCELONA HOSP BELLVITGE CARPETA ANTIGUA",
        )
        (marker_folder / f"{licitacion_id}.llangon").write_text("", encoding="utf-8")
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        payload = {"folder_name_confirmed": "CARPETA DUPLICADA"} if stale_confirmation else None
        handler = make_download_handler(app, payload=payload)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, result = handler.responses[-1]
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)

    assert status == HTTPStatus.OK
    assert result["ok"] is True
    assert "needs_folder_confirmation" not in result
    assert calls == [marker_folder]
    assert Path(result["carpeta"]) == marker_folder
    assert Path(ruta_carpeta).parts == ("2026", "07 JULIO", marker_folder.name)
    assert not (marker_folder.parent / "CARPETA DUPLICADA").exists()


def test_download_missing_folder_returns_confirmation_without_creating_folder() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        destination = default_download_destination(app, licitacion_id)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called before folder confirmation")

        handler = make_download_handler(app)
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)
        jobs = get_download_jobs(app, licitacion_id)
        destination_exists = destination.exists()

    assert status == HTTPStatus.OK
    assert payload["needs_folder_confirmation"] is True
    assert payload["suggested_folder_name"] == destination.name
    assert not destination_exists
    assert ruta_carpeta == ""
    assert jobs == []


def test_download_suggested_folder_name_is_windows_safe() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        handler = make_download_handler(app)
        handler.api_download_licitacion(licitacion_id)

        suggested = handler.responses[-1][1]["suggested_folder_name"]

    assert suggested
    assert not any(char in suggested for char in '\\/:*?"<>|')
    assert ".." not in suggested


def test_download_confirmed_folder_name_creates_edited_folder_and_runs_download() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        default_destination = default_download_destination(app, licitacion_id)
        edited_name = "30 JUNIO 1200 MADRID NOMBRE EDITADO TEST"
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(
            app,
            payload={"folder_name_confirmed": edited_name},
        )
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        edited_destination = default_destination.parent / edited_name
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)
        edited_exists = edited_destination.exists()

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert edited_exists
    assert calls == [edited_destination]
    assert ruta_carpeta.endswith(edited_name)


def test_manual_download_persists_an_immediately_resolvable_folder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = load_app_module()
    dropbox_root = tmp_path / "00000 LLANGON"
    dropbox_root.mkdir()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(dropbox_root))

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: dropbox_root
        licitacion_id = insert_fake_licitacion(app)
        default_destination = default_download_destination(app, licitacion_id)
        confirmed_name = "30 JUNIO 1200  MADRID NOMBRE EDITADO TEST"
        canonical_name = "30 JUNIO 1200 MADRID NOMBRE EDITADO TEST"

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(
            app,
            payload={"folder_name_confirmed": confirmed_name},
        )
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        expected_destination = default_destination.parent / canonical_name
        with app.db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        item = app.row_to_dict(row)
        marker_status = app.get_marker_status_for_licitacion(item, dropbox_root)

        assert status == HTTPStatus.OK
        assert payload["ok"] is True
        assert Path(payload["carpeta"]).resolve() == expected_destination.resolve()
        assert item["folder_status"]["exists"] is True
        assert Path(item["folder_status"]["path"]).resolve() == expected_destination.resolve()
        assert marker_status["folder_exists"] is True
        assert marker_status["id_marker_exists"] is True


def test_manual_download_frontend_refreshes_the_open_detail_without_touching_email_worker() -> None:
    script = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    finish_download = script.split("async function finishDownload", 1)[1].split("async function downloadLicitacion", 1)[0]
    manual_download = script.split("async function downloadLicitacion", 1)[1].split("async function confirmDownloadFolder", 1)[0]
    confirmed_download = script.split("async function confirmDownloadFolder", 1)[1].split("async function toggleDetails", 1)[0]

    assert "await refreshLicitacionDetail(id);" in finish_download
    assert "activateDetailTabByName(activeTab);" in finish_download
    assert "await finishDownload(result, id);" in manual_download
    assert "await finishDownload(result, pending.id);" in confirmed_download

    app = load_app_module()
    worker_source = Path(app.__file__).read_text(encoding="utf-8").split("def process_download_job", 1)[1].split("def repair_internal_download_routes", 1)[0]
    assert "manual_download_folder_path_for_storage" not in worker_source


@pytest.mark.parametrize(
    "folder_name",
    [
        "../fuera",
        "..\\fuera",
        "C:\\fuera",
        "/fuera",
        "carpeta/con/barra",
        "carpeta\\con\\barra",
        'carpeta:con*caracteres?"<malos>|',
        "..",
    ],
)
def test_download_rejects_invalid_confirmed_folder_names(folder_name: str) -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called for invalid folder names")

        handler = make_download_handler(app, payload={"folder_name_confirmed": folder_name})
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        jobs = get_download_jobs(app, licitacion_id)

    assert status == HTTPStatus.BAD_REQUEST
    assert "carpeta" in payload["error"].lower()
    assert jobs == []


def test_download_rejects_confirmed_folder_that_already_exists_without_overwriting() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)
        destination = default_download_destination(app, licitacion_id)
        existing_name = "CARPETA EXISTENTE"
        existing = destination.parent / existing_name
        existing.mkdir(parents=True)
        marker = existing / "manual.txt"
        marker.write_text("no tocar", encoding="utf-8")

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called when confirmed folder already exists")

        handler = make_download_handler(app, payload={"folder_name_confirmed": existing_name})
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        marker_text = marker.read_text(encoding="utf-8")
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)
        jobs = get_download_jobs(app, licitacion_id)

    assert status == HTTPStatus.CONFLICT
    assert payload["folder_exists"] is True
    assert marker_text == "no tocar"
    assert ruta_carpeta == ""
    assert jobs == []


def test_download_rejects_missing_configured_dropbox_base(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    missing_base = tmp_path / "Dropbox inexistente"
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(missing_base))

    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise AssertionError("subprocess.run must not be called with invalid Dropbox base")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        jobs = get_download_jobs(app, licitacion_id)

    assert status == HTTPStatus.BAD_REQUEST
    assert "Dropbox" in payload["error"]
    assert jobs == []


def test_download_uses_llangon_dropbox_base_before_legacy_root(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    dropbox_root = tmp_path / "Dropbox"
    legacy_root = tmp_path / "ReplicaDb"
    dropbox_root.mkdir()
    legacy_root.mkdir()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(dropbox_root))
    monkeypatch.setenv("INFONALIA_DROPBOX_ROOT", str(legacy_root))

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: dropbox_root
        licitacion_id = insert_fake_licitacion(app)
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        cwd = calls[0].resolve()

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert cwd.is_relative_to(dropbox_root.resolve())
    assert not cwd.is_relative_to(legacy_root.resolve())
    assert Path(payload["carpeta"]).resolve() == cwd


def test_download_with_dropbox_base_creates_year_month_folder_and_stores_relative_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = load_app_module()
    dropbox_root = tmp_path / "00000 LLANGON"
    dropbox_root.mkdir()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(dropbox_root))

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: dropbox_root
        licitacion_id = insert_fake_licitacion(app)
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE licitaciones
                SET fecha_limite = ?, hora_limite = ?, provincia = ?, organismo = ?, objeto = ?, expediente = ?
                WHERE id = ?
                """,
                (
                    "2026-07-20",
                    "14:00",
                    "Alicante",
                    "Alcaldia del Ayuntamiento de Pinoso (Alicante)",
                    "Suministro de alimentos para el comedor de la escuela infantil municipal",
                    "PASO202613SIM 1418652R",
                    licitacion_id,
                ),
            )
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)
        cwd = calls[0].resolve()

    assert status == HTTPStatus.OK
    assert cwd.is_relative_to((dropbox_root / "2026" / "07 JULIO").resolve())
    assert not (dropbox_root / "07 JULIO").exists()
    assert Path(ruta_carpeta).parts[:2] == ("2026", "07 JULIO")
    assert "00000 LLANGON" not in Path(ruta_carpeta).parts
    assert Path(payload["carpeta"]).resolve() == cwd


def test_download_missing_legacy_month_route_is_not_recreated_without_year(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = load_app_module()
    dropbox_root = tmp_path / "00000 LLANGON"
    dropbox_root.mkdir()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(dropbox_root))

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: dropbox_root
        legacy_route = r"07 JULIO\20 JULIO 1400 ALICANTE ESCUELA INFANTIL PASO202613SIM 1418652R"
        licitacion_id = insert_fake_licitacion(app, ruta_carpeta=legacy_route)
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET fecha_limite = ?, hora_limite = ?, provincia = ? WHERE id = ?",
                ("2026-07-20", "14:00", "Alicante", licitacion_id),
            )
        calls = []

        def fake_run(args, cwd, capture_output, text, timeout):
            calls.append(Path(cwd))
            Path(cwd, "documento-ficticio.pdf").write_bytes(b"fake pdf")
            return SimpleNamespace(returncode=0, stdout="descarga correcta", stderr="")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]
        ruta_carpeta = get_ruta_carpeta(app, licitacion_id)
        cwd = calls[0].resolve()

    assert status == HTTPStatus.OK
    assert cwd == dropbox_root / "2026" / "07 JULIO" / Path(legacy_route).name
    assert not (dropbox_root / "07 JULIO").exists()
    assert Path(ruta_carpeta).parts[:2] == ("2026", "07 JULIO")
    assert payload["ruta_carpeta"] == ruta_carpeta


def test_download_route_rejects_missing_csrf_before_subprocess() -> None:
    app = load_app_module()

    def fake_run(args, cwd, capture_output, text, timeout):
        raise AssertionError("subprocess.run must not be called without CSRF")

    handler = make_download_handler(app, path="/api/licitaciones/123/descargar")
    with mocked_subprocess_run(app, fake_run):
        handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_download_route_rejects_invalid_csrf_before_subprocess() -> None:
    app = load_app_module()

    def fake_run(args, cwd, capture_output, text, timeout):
        raise AssertionError("subprocess.run must not be called with invalid CSRF")

    handler = make_download_handler(
        app,
        path="/api/licitaciones/123/descargar",
        csrf_token="wrong-token",
    )
    with mocked_subprocess_run(app, fake_run):
        handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


def test_download_endpoint_failure_does_not_update_ruta_carpeta() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            Path(cwd, "salida-parcial.tmp").write_text("parcial", encoding="utf-8")
            return SimpleNamespace(returncode=2, stdout="", stderr="fallo ficticio")

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.BAD_REQUEST
        assert payload["ok"] is False
        assert payload["codigo"] == 2
        assert "fallo ficticio" in payload["salida"]
        assert get_ruta_carpeta(app, licitacion_id) == ""
        jobs = get_download_jobs(app, licitacion_id)
        assert len(jobs) == 1
        assert jobs[0]["status"] == "failed"
        assert "codigo 2" in jobs[0]["error_message"]
        assert "fallo ficticio" in jobs[0]["error_message"]
        assert jobs[0]["finished_at"]


def test_download_endpoint_timeout_does_not_update_ruta_carpeta() -> None:
    app = load_app_module()
    with temporary_download_app(app):
        licitacion_id = insert_fake_licitacion(app)

        def fake_run(args, cwd, capture_output, text, timeout):
            raise app.subprocess.TimeoutExpired(cmd=args, timeout=timeout)

        handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
        with mocked_subprocess_run(app, fake_run):
            handler.api_download_licitacion(licitacion_id)

        status, payload = handler.responses[-1]

        assert status == HTTPStatus.REQUEST_TIMEOUT
        assert "tardado demasiado" in payload["error"]
        assert get_ruta_carpeta(app, licitacion_id) == ""
        jobs = get_download_jobs(app, licitacion_id)
        assert len(jobs) == 1
        assert jobs[0]["status"] == "failed"
        assert "tardado demasiado" in jobs[0]["error_message"]
        assert jobs[0]["finished_at"]


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

            handler = make_download_handler(app, payload=confirmed_download_payload(app, licitacion_id))
            with mocked_subprocess_run(app, fake_run):
                handler.api_download_licitacion(licitacion_id)

            status, payload = handler.responses[-1]

            assert status == HTTPStatus.BAD_REQUEST
            assert payload["ok"] is False
            assert "ficheros" in payload["error"]
            assert get_ruta_carpeta(app, licitacion_id) == ""
            jobs = get_download_jobs(app, licitacion_id)
            assert len(jobs) == 1
            assert jobs[0]["status"] == "failed"
            assert "ficheros" in jobs[0]["error_message"]
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
        assert get_download_jobs(app, licitacion_id) == []


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
        assert get_download_jobs(app, licitacion_id) == []


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
        assert get_download_jobs(app, licitacion_id) == []
