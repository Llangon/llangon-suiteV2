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
