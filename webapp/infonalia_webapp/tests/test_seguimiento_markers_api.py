from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from webapp.infonalia_webapp.tests.test_download_endpoint import (
    make_download_handler,
    temporary_download_app,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import VALID_CSRF_TOKEN, load_app_module


def insert_licitacion_with_id(app, licitacion_id: int, ruta_carpeta: str = "") -> None:
    with app.db_session() as conn:
        conn.execute(
            """
            INSERT INTO licitaciones (
                id, expediente, objeto, organismo, provincia, fecha_limite,
                hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                licitacion_id,
                f"EXP-{licitacion_id}",
                "Objeto",
                "Organismo",
                "Madrid",
                "2026-06-30",
                "12:00",
                "https://example.test",
                "Preparar ficha",
                ruta_carpeta,
                "2026-06-17T10:00:00",
                "2026-06-17T10:00:00",
            ),
        )


def test_storage_markers_sync_endpoint_repairs_route_and_follow_state(tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    marker_folder = replica_root / "2026" / "06 JUNIO" / "no" / "licitacion X"
    ignored_folder = replica_root / "Infonalia" / "licitacion ignorada"
    marker_folder.mkdir(parents=True)
    ignored_folder.mkdir(parents=True)
    (marker_folder / "33.llangon").write_text("", encoding="utf-8")
    (marker_folder / "EnSeguimiento.llangon").write_text("", encoding="utf-8")
    (ignored_folder / "44.llangon").write_text("", encoding="utf-8")

    with temporary_download_app(app):
        app.find_dropbox_root = lambda: replica_root
        insert_licitacion_with_id(app, 33, "2026/antigua")
        insert_licitacion_with_id(app, 44, "")

        handler = make_download_handler(
            app,
            path="/api/storage/markers/sync",
            csrf_token=VALID_CSRF_TOKEN,
        )
        handler.do_POST()

        status, payload = handler.responses[-1]
        with app.db_session() as conn:
            lic_33 = conn.execute("SELECT * FROM licitaciones WHERE id = 33").fetchone()
            lic_44 = conn.execute("SELECT * FROM licitaciones WHERE id = 44").fetchone()

    assert status == HTTPStatus.OK
    assert payload["found"] == 1
    assert payload["updated"] == 1
    assert payload["following"] == 1
    assert Path(lic_33["ruta_carpeta"]).parts == ("2026", "06 JUNIO", "no", "licitacion X")
    assert lic_33["seguimiento_activo"] == 1
    assert lic_33["seguimiento_marker_path"].endswith("33.llangon")
    assert lic_44["ruta_carpeta"] == ""
    assert lic_44["seguimiento_activo"] == 0


def test_storage_markers_sync_endpoint_requires_csrf(tmp_path: Path) -> None:
    app = load_app_module()
    with temporary_download_app(app):
        app.find_dropbox_root = lambda: tmp_path
        handler = make_download_handler(app, path="/api/storage/markers/sync")

        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN


def test_licitacion_marker_endpoints_create_exact_files_without_overwriting(tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    folder = replica_root / "2026" / "licitacion"
    folder.mkdir(parents=True)

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [replica_root]
        app.marker_dropbox_root = lambda: None
        insert_licitacion_with_id(app, 33, str(folder))

        id_handler = make_download_handler(app, path="/api/licitaciones/33/markers/id", csrf_token=VALID_CSRF_TOKEN)
        id_handler.do_POST()
        follow_handler = make_download_handler(app, path="/api/licitaciones/33/markers/follow", csrf_token=VALID_CSRF_TOKEN)
        follow_handler.do_POST()

        id_marker = folder / "33.llangon"
        follow_marker = folder / "EnSeguimiento.llangon"
        id_marker.write_text("manual", encoding="utf-8")
        second_handler = make_download_handler(app, path="/api/licitaciones/33/markers/id", csrf_token=VALID_CSRF_TOKEN)
        second_handler.do_POST()

    assert id_handler.responses[-1][0] == HTTPStatus.OK
    assert id_handler.responses[-1][1]["created"] is True
    assert follow_handler.responses[-1][0] == HTTPStatus.OK
    assert follow_handler.responses[-1][1]["created"] is True
    assert id_marker.read_text(encoding="utf-8") == "manual"
    assert follow_marker.is_file()
    assert second_handler.responses[-1][0] == HTTPStatus.OK
    assert second_handler.responses[-1][1]["exists"] is True
    assert second_handler.responses[-1][1]["created"] is False


def test_licitacion_marker_endpoint_rejects_missing_folder(tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    replica_root.mkdir()
    missing_folder = replica_root / "2026" / "missing"

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [replica_root]
        app.marker_dropbox_root = lambda: None
        insert_licitacion_with_id(app, 33, str(missing_folder))

        handler = make_download_handler(app, path="/api/licitaciones/33/markers/id", csrf_token=VALID_CSRF_TOKEN)
        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert not (missing_folder / "33.llangon").exists()


def test_licitacion_marker_endpoint_rejects_folder_outside_allowed_root(tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    outside_folder = tmp_path / "Outside" / "licitacion"
    replica_root.mkdir()
    outside_folder.mkdir(parents=True)

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [replica_root]
        app.marker_dropbox_root = lambda: None
        insert_licitacion_with_id(app, 33, str(outside_folder))

        handler = make_download_handler(app, path="/api/licitaciones/33/markers/follow", csrf_token=VALID_CSRF_TOKEN)
        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert not (outside_folder / "EnSeguimiento.llangon").exists()


def test_open_folder_endpoint_uses_mocked_startfile_after_safe_validation(tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    folder = replica_root / "2026" / "licitacion"
    folder.mkdir(parents=True)
    opened: list[str] = []
    previous_startfile = getattr(app.os, "startfile", None)
    had_startfile = hasattr(app.os, "startfile")

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [replica_root]
        app.marker_dropbox_root = lambda: None
        setattr(app.os, "startfile", opened.append)
        insert_licitacion_with_id(app, 33, str(folder))

        handler = make_download_handler(app, path="/api/licitaciones/33/open-folder", csrf_token=VALID_CSRF_TOKEN)
        try:
            handler.do_POST()
        finally:
            if had_startfile:
                setattr(app.os, "startfile", previous_startfile)
            else:
                delattr(app.os, "startfile")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert opened == [str(folder.resolve())]


def test_marker_endpoints_require_admin_permission(tmp_path: Path) -> None:
    app = load_app_module()
    folder = tmp_path / "ReplicaDb" / "2026" / "licitacion"
    folder.mkdir(parents=True)

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [folder.parent.parent]
        app.marker_dropbox_root = lambda: None
        insert_licitacion_with_id(app, 33, str(folder))
        handler = make_download_handler(app, path="/api/licitaciones/33/markers/id", csrf_token=VALID_CSRF_TOKEN)

        def deny_admin() -> bool:
            handler.send_json({"error": "No tienes permiso para esta accion."}, HTTPStatus.FORBIDDEN)
            return False

        handler.require_admin = deny_admin
        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert not (folder / "33.llangon").exists()


def test_marker_endpoints_require_csrf_before_creating_files(tmp_path: Path) -> None:
    app = load_app_module()
    folder = tmp_path / "ReplicaDb" / "2026" / "licitacion"
    folder.mkdir(parents=True)

    with temporary_download_app(app):
        app.marker_allowed_roots = lambda: [folder.parent.parent]
        app.marker_dropbox_root = lambda: None
        insert_licitacion_with_id(app, 33, str(folder))
        handler = make_download_handler(app, path="/api/licitaciones/33/markers/id")
        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert not (folder / "33.llangon").exists()
