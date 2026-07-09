from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.clientes_envios import (
    CORREOS_PREPARADOS_FOLDER,
    create_cliente,
    create_cliente_envio,
    generate_cliente_envio_draft,
    get_cliente,
    list_dropbox_folder_files,
    mark_cliente_envio_sent,
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


def test_list_dropbox_folder_files_excludes_temp_empty_and_prepared_files(monkeypatch, tmp_path: Path) -> None:
    base = configure_dropbox_base(monkeypatch, tmp_path)
    folder_path = create_dropbox_folder(base, folder_name="Cliente Ficheros")

    payload = list_dropbox_folder_files(folder_path, dropbox_base=base)

    relative_paths = {item["relative_path"].replace("\\", "/") for item in payload["files"]}
    assert relative_paths == {"ficha.pdf", "subcarpeta/anexo.docx"}
    assert payload["total_files"] == 2


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
