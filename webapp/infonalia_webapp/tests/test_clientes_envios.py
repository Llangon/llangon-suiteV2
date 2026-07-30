from __future__ import annotations

import sys
import sqlite3
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.clientes_envios import (
    CORREOS_PREPARADOS_FOLDER,
    create_cliente,
    create_cliente_envio,
    ensure_client_shipments_schema,
    generate_cliente_envio_draft,
    get_cliente,
    list_clientes,
    list_dropbox_folder_files,
    mark_cliente_envio_sent,
    set_cliente_active,
    update_cliente_envio,
    validate_selected_attachments,
)
from webapp.infonalia_webapp.dropbox_paths import DropboxPathError
from webapp.infonalia_webapp.outlook_drafts import DraftGenerationResult
from webapp.infonalia_webapp.tests.test_actuaciones_api import create_actuacion, dispatch, make_handler
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


TIMESTAMP = "2026-07-09T10:00:00"


def teardown_function() -> None:
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)


def configure_dropbox_base(monkeypatch, tmp_path: Path) -> Path:
    base = tmp_path / "Dropbox" / "00000 LLANGON"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(base))
    monkeypatch.delenv("INFONALIA_DROPBOX_ROOT", raising=False)
    return base


def create_dropbox_folder(base: Path, *, folder_name: str) -> str:
    folder = base / "2026" / "07 JULIO" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ficha.pdf").write_bytes(b"pdf")
    (folder / "subcarpeta").mkdir(exist_ok=True)
    (folder / "subcarpeta" / "anexo.docx").write_bytes(b"docx")
    (folder / "~$temporal.docx").write_bytes(b"x")
    (folder / "vacio.txt").write_bytes(b"")
    prepared = folder / CORREOS_PREPARADOS_FOLDER
    prepared.mkdir(exist_ok=True)
    (prepared / "previo.msg").write_bytes(b"msg")
    return str(folder.relative_to(base))


def create_test_cliente(conn, *, nombre: str, email: str) -> dict[str, object]:
    return create_cliente(
        conn,
        {
            "razon_social": nombre,
            "nombre_comercial": nombre,
            "nif_cif": "B12345678",
            "email_principal": email,
            "telefono_principal": "954000000",
        },
        user_id="admin_test",
        timestamp=TIMESTAMP,
    )


def create_test_licitacion(app, *, expediente: str) -> int:
    dia_id = insert_dia(app)
    licitacion_id = insert_licitacion(app, dia_id, expediente)
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE licitaciones
            SET objeto = ?, organismo = ?, enlace_perfil = ?
            WHERE id = ?
            """,
            ("Servicio de prueba", "Ayuntamiento de Prueba", "https://perfil.example.test/expediente", licitacion_id),
        )
    return licitacion_id


def test_client_schema_adds_new_fields_to_existing_table() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    ensure_client_shipments_schema(conn)
    cliente = create_cliente(
        conn,
        {
            "razon_social": "Cliente Legacy",
            "nombre_comercial": "Legacy",
            "nif_cif": "B12345678",
            "email_principal": "legacy@example.test",
            "tipo_cliente": "Recurrente",
            "plantilla_contractual": "General",
        },
        user_id="admin_test",
        timestamp=TIMESTAMP,
    )

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(clientes)").fetchall()}
    assert {
        "nombre_comercial",
        "email_principal",
        "tipo_cliente",
        "plantilla_contractual",
        "activo",
        "desactivado_at",
        "desactivado_by",
    } <= columns
    assert cliente["display_name"] == "Legacy"
    assert cliente["activo"] is True
    assert cliente["email_principal"] == "legacy@example.test"
    assert cliente["tipo_cliente"] == "Recurrente"


def test_cliente_status_filters_and_reversible_deactivation_are_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_client_shipments_schema(conn)
    cliente = create_test_cliente(conn, nombre="Cliente Estado", email="estado@example.test")

    assert [item["id"] for item in list_clientes(conn)] == [cliente["id"]]
    assert list_clientes(conn, estado="inactivos") == []

    inactive = set_cliente_active(
        conn,
        int(cliente["id"]),
        active=False,
        user_id="admin_test",
        timestamp="2026-07-09T11:00:00",
    )
    repeated = set_cliente_active(
        conn,
        int(cliente["id"]),
        active=False,
        user_id="otro_admin",
        timestamp="2026-07-09T11:30:00",
    )

    assert inactive["activo"] is False
    assert repeated["desactivado_at"] == "2026-07-09T11:00:00"
    assert repeated["desactivado_by"] == "admin_test"
    assert list_clientes(conn) == []
    assert [item["id"] for item in list_clientes(conn, estado="inactivos")] == [cliente["id"]]
    assert [item["id"] for item in list_clientes(conn, estado="todos", search="Estado")] == [cliente["id"]]

    active = set_cliente_active(
        conn,
        int(cliente["id"]),
        active=True,
        user_id="admin_test",
        timestamp="2026-07-09T12:00:00",
    )
    assert active["activo"] is True
    assert active["desactivado_at"] == ""
    assert active["desactivado_by"] == ""


def test_cliente_status_endpoints_are_admin_only_and_keep_history() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Endpoint Estado", email="estado-api@example.test")

        forbidden = make_handler(
            app,
            "POST",
            f"/api/clientes/{cliente['id']}/desactivar",
            username="reviewer_test",
            role="nuria",
        )
        dispatch(forbidden, "POST")
        deactivate = make_handler(app, "POST", f"/api/clientes/{cliente['id']}/desactivar")
        dispatch(deactivate, "POST")
        default_list = make_handler(app, "GET", "/api/clientes")
        dispatch(default_list, "GET")
        inactive_list = make_handler(app, "GET", "/api/clientes?estado=inactivos&q=Endpoint")
        dispatch(inactive_list, "GET")
        reactivate = make_handler(app, "POST", f"/api/clientes/{cliente['id']}/reactivar")
        dispatch(reactivate, "POST")

    assert forbidden.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert deactivate.responses[-1][1]["item"]["activo"] is False
    assert default_list.responses[-1][1]["items"] == []
    assert [item["id"] for item in inactive_list.responses[-1][1]["items"]] == [cliente["id"]]
    assert reactivate.responses[-1][1]["item"]["activo"] is True


def test_init_db_repairs_client_schema_when_migration_was_already_applied(tmp_path: Path) -> None:
    app = load_app_module()
    from webapp.infonalia_webapp.db_migrations import MIGRATIONS, MIGRATIONS_TABLE

    old_data_root = app.DATA_ROOT
    old_download_root = app.DOWNLOAD_ROOT
    old_db_path = app.DB_PATH
    try:
        app.DATA_ROOT = tmp_path / "data"
        app.DOWNLOAD_ROOT = app.DATA_ROOT / "descargas"
        app.DB_PATH = app.DATA_ROOT / "infonalia.db"
        app.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(app.DB_PATH)
        conn.execute(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razon_social TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE {MIGRATIONS_TABLE} (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            f"INSERT INTO {MIGRATIONS_TABLE} (version, description, applied_at) VALUES (?, ?, ?)",
            [(migration.version, migration.description, TIMESTAMP) for migration in MIGRATIONS],
        )
        conn.commit()
        conn.close()

        app.init_db()
        with app.db_session() as conn:
            cliente = create_cliente(
                conn,
                {
                    "razon_social": "Cliente Arranque",
                    "nombre_comercial": "Arranque",
                    "email_principal": "arranque@example.test",
                },
                user_id="admin_test",
                timestamp=TIMESTAMP,
            )

        assert cliente["display_name"] == "Arranque"
        assert cliente["email_principal"] == "arranque@example.test"
    finally:
        app.DATA_ROOT = old_data_root
        app.DOWNLOAD_ROOT = old_download_root
        app.DB_PATH = old_db_path


def test_create_cliente_and_envio_from_licitacion_records_history(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Astur Santina")

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-001")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Astur Santina", email="cliente@example.test")
            envio = create_cliente_envio(
                conn,
                {
                    "cliente_id": cliente["id"],
                    "licitacion_id": licitacion_id,
                    "tipo_envio": "ficha_inicial",
                    "estado": "listo_para_preparar_correo",
                    "carpeta_dropbox": folder_path,
                    "adjuntos": ["ficha.pdf", "subcarpeta/anexo.docx"],
                },
                user_id="admin_test",
                timestamp=TIMESTAMP,
            )
            cliente_detalle = get_cliente(conn, cliente["id"])

    assert envio["cliente_id"] == cliente["id"]
    assert envio["licitacion_id"] == licitacion_id
    assert envio["attachment_count"] == 2
    assert "CLI-ENV-001" in envio["asunto"]
    assert any(event["event_type"] == "creacion" for event in envio["events"])
    assert cliente_detalle is not None
    assert [item["id"] for item in cliente_detalle["envios"]] == [envio["id"]]


def test_inactive_cliente_rejects_new_envio_but_existing_envio_can_continue(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Inactivo")

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-INACTIVO-001")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Inactivo", email="inactivo@example.test")
            envio = create_cliente_envio(
                conn,
                {
                    "cliente_id": cliente["id"],
                    "licitacion_id": licitacion_id,
                    "tipo_envio": "ficha_inicial",
                    "estado": "en_preparacion",
                    "carpeta_dropbox": folder_path,
                    "adjuntos": ["ficha.pdf"],
                },
                user_id="admin_test",
                timestamp=TIMESTAMP,
            )
            set_cliente_active(
                conn,
                int(cliente["id"]),
                active=False,
                user_id="admin_test",
                timestamp="2026-07-09T11:00:00",
            )

            with pytest.raises(ValueError, match="desactivado"):
                create_cliente_envio(
                    conn,
                    {
                        "cliente_id": cliente["id"],
                        "licitacion_id": licitacion_id,
                        "tipo_envio": "otro",
                        "estado": "en_preparacion",
                        "carpeta_dropbox": folder_path,
                        "adjuntos": ["ficha.pdf"],
                    },
                    user_id="admin_test",
                    timestamp="2026-07-09T11:05:00",
                )

            updated = update_cliente_envio(
                conn,
                int(envio["id"]),
                {
                    "cliente_id": cliente["id"],
                    "licitacion_id": licitacion_id,
                    "tipo_envio": "ficha_inicial",
                    "estado": "listo_para_preparar_correo",
                    "carpeta_dropbox": folder_path,
                    "adjuntos": ["ficha.pdf"],
                },
                user_id="admin_test",
                timestamp="2026-07-09T11:10:00",
            )

    assert updated["estado"] == "listo_para_preparar_correo"
    assert updated["cliente_activo"] is False


def test_create_envio_endpoint_accepts_base_route(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Endpoint")

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-BASE")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Endpoint", email="endpoint@example.test")
        payload = {
            "cliente_id": cliente["id"],
            "licitacion_id": licitacion_id,
            "tipo_envio": "ficha_inicial",
            "estado": "listo_para_preparar_correo",
            "carpeta_dropbox": folder_path,
            "adjuntos": ["ficha.pdf"],
        }

        handler = make_handler(app, "POST", "/api/cliente-envios", payload)
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.CREATED
    item = handler.responses[-1][1]["item"]
    assert item["cliente_id"] == cliente["id"]
    assert item["licitacion_id"] == licitacion_id
    assert item["attachment_count"] == 1


def test_delete_envio_endpoint_is_admin_only_and_keeps_dropbox_files(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Eliminar")
    source_file = base / folder_path / "ficha.pdf"

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-DELETE")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Eliminar", email="eliminar@example.test")
            envio = create_cliente_envio(
                conn,
                {
                    "cliente_id": cliente["id"],
                    "licitacion_id": licitacion_id,
                    "tipo_envio": "ficha_inicial",
                    "estado": "en_preparacion",
                    "carpeta_dropbox": folder_path,
                    "adjuntos": ["ficha.pdf"],
                },
                user_id="admin_test",
                timestamp=TIMESTAMP,
            )

        forbidden = make_handler(
            app,
            "DELETE",
            f"/api/cliente-envios/{envio['id']}",
            username="reviewer_test",
            role="nuria",
        )
        dispatch(forbidden, "DELETE")

        handler = make_handler(app, "DELETE", f"/api/cliente-envios/{envio['id']}")
        dispatch(handler, "DELETE")

        with app.db_session() as conn:
            envio_count = conn.execute("SELECT COUNT(*) FROM cliente_envios WHERE id = ?", (envio["id"],)).fetchone()[0]
            attachment_count = conn.execute("SELECT COUNT(*) FROM cliente_envio_adjuntos WHERE envio_id = ?", (envio["id"],)).fetchone()[0]
            event_count = conn.execute("SELECT COUNT(*) FROM cliente_envio_eventos WHERE envio_id = ?", (envio["id"],)).fetchone()[0]

    assert forbidden.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert handler.responses[-1][0] == HTTPStatus.OK
    assert handler.responses[-1][1]["item"]["id"] == envio["id"]
    assert envio_count == 0
    assert attachment_count == 0
    assert event_count == 0
    assert source_file.exists()


def test_list_dropbox_folder_files_excludes_temp_empty_and_prepared_files(monkeypatch, tmp_path: Path) -> None:
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Ficheros")

    payload = list_dropbox_folder_files(folder_path, dropbox_base=base)

    relative_paths = {item["relative_path"].replace("\\", "/") for item in payload["files"]}
    assert relative_paths == {"ficha.pdf", "subcarpeta/anexo.docx"}
    assert payload["total_files"] == 2


def test_folder_files_endpoint_requires_admin(monkeypatch, tmp_path: Path) -> None:
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Ficheros Endpoint")
    app = load_app_module()

    forbidden = make_handler(
        app,
        "POST",
        "/api/cliente-envios/folder-files",
        {"carpeta_dropbox": folder_path},
        username="reviewer_test",
        role="nuria",
    )
    dispatch(forbidden, "POST")

    handler = make_handler(app, "POST", "/api/cliente-envios/folder-files", {"carpeta_dropbox": folder_path})
    dispatch(handler, "POST")

    assert forbidden.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert handler.responses[-1][0] == HTTPStatus.OK
    assert handler.responses[-1][1]["total_files"] == 2


def test_create_envio_rejects_folder_outside_dropbox_base(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    _base = configure_dropbox_base(monkeypatch, tmp_path)
    outside_folder = tmp_path / "FueraDropbox" / "Cliente"
    outside_folder.mkdir(parents=True, exist_ok=True)
    (outside_folder / "ficha.pdf").write_bytes(b"pdf")

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-002")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Fuera", email="fuera@example.test")
            with pytest.raises(DropboxPathError, match="base permitida de Dropbox"):
                create_cliente_envio(
                    conn,
                    {
                        "cliente_id": cliente["id"],
                        "licitacion_id": licitacion_id,
                        "tipo_envio": "ficha_inicial",
                        "estado": "en_preparacion",
                        "carpeta_dropbox": str(outside_folder),
                        "adjuntos": ["ficha.pdf"],
                    },
                    user_id="admin_test",
                    timestamp=TIMESTAMP,
                )


def test_validate_selected_attachments_rejects_paths_outside_folder(monkeypatch, tmp_path: Path) -> None:
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Validacion")

    with pytest.raises(ValueError, match="carpeta asignada al envio"):
        validate_selected_attachments(folder_path, ["..\\otro-cliente.pdf"], dropbox_base=base)


def test_create_envio_from_actuacion_endpoint_links_context_and_keeps_admin_only(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Actuacion")

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-003")
        actuacion = create_actuacion(app, [licitacion_id], titulo="Subsanación para cliente")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Actuacion", email="actuacion@example.test")
        payload = {
            "cliente_id": cliente["id"],
            "licitacion_id": licitacion_id,
            "tipo_envio": "subsanacion",
            "estado": "en_preparacion",
            "carpeta_dropbox": folder_path,
            "adjuntos": ["ficha.pdf"],
        }

        forbidden = make_handler(
            app,
            "POST",
            f"/api/actuaciones/{actuacion['id']}/cliente-envios",
            payload,
            username="reviewer_test",
            role="nuria",
        )
        dispatch(forbidden, "POST")

        handler = make_handler(app, "POST", f"/api/actuaciones/{actuacion['id']}/cliente-envios", payload)
        dispatch(handler, "POST")

    assert forbidden.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert handler.responses[-1][0] == HTTPStatus.CREATED
    item = handler.responses[-1][1]["item"]
    assert item["actuacion_id"] == actuacion["id"]
    assert item["licitacion_id"] == licitacion_id
    assert item["tipo_envio"] == "subsanacion"


def test_generate_draft_and_mark_sent_update_state_and_history(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Draft")
    generated_paths: list[Path] = []

    def fake_generator(**kwargs) -> DraftGenerationResult:
        preferred_msg_path = kwargs["preferred_msg_path"]
        preferred_msg_path.parent.mkdir(parents=True, exist_ok=True)
        preferred_msg_path.write_bytes(b"msg")
        generated_paths.append(preferred_msg_path)
        return DraftGenerationResult(
            ok=True,
            path=str(preferred_msg_path),
            file_format="msg",
            message="Correo Outlook generado.",
            opened=False,
        )

    with temporary_app_database(app):
        licitacion_id = create_test_licitacion(app, expediente="CLI-ENV-004")
        with app.db_session() as conn:
            cliente = create_test_cliente(conn, nombre="Cliente Draft", email="draft@example.test")
            envio = create_cliente_envio(
                conn,
                {
                    "cliente_id": cliente["id"],
                    "licitacion_id": licitacion_id,
                    "tipo_envio": "documentacion_revision",
                    "estado": "listo_para_preparar_correo",
                    "carpeta_dropbox": folder_path,
                    "adjuntos": ["ficha.pdf"],
                },
                user_id="admin_test",
                timestamp=TIMESTAMP,
            )
            draft = generate_cliente_envio_draft(
                conn,
                envio["id"],
                user_id="reviewer_test",
                timestamp="2026-07-09T10:30:00",
                overrides={
                    "destinatario_email": "nuria@example.test",
                    "asunto": "Correo revisado",
                    "cuerpo": "Adjuntamos la documentación.",
                    "adjuntos": ["ficha.pdf"],
                },
                generator=fake_generator,
                opener=None,
            )
            sent = mark_cliente_envio_sent(
                conn,
                envio["id"],
                user_id="reviewer_test",
                timestamp="2026-07-09T10:45:00",
            )

    assert draft["estado"] == "correo_outlook_generado"
    assert draft["correo_generado_formato"] == "msg"
    assert draft["correo_generado_path"].endswith(".msg")
    assert draft["draft_generation"]["ok"] is True
    assert generated_paths and generated_paths[0].exists()
    assert sent["estado"] == "enviado"
    assert sent["enviado_by"] == "reviewer_test"
    assert any(event["event_type"] == "correo_generado" for event in sent["events"])
    assert any(event["event_type"] == "marcado_enviado" for event in sent["events"])
