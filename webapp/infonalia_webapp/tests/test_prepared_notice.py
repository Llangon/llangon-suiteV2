from __future__ import annotations

from http import HTTPStatus

from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def patch_licitacion_state(app, licitacion_id: int, estado: str):
    handler = make_handler(app, "PATCH", f"/api/licitaciones/{licitacion_id}", {"estado": estado})
    dispatch(handler, "PATCH")
    return handler.responses[-1]


def test_prepared_notice_preview_is_returned_only_on_real_transition() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-PREP-1")
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE licitaciones
                SET fecha_limite = ?, hora_limite = ?, ruta_carpeta = ?
                WHERE id = ?
                """,
                ("2026-06-30", "12:30", "2026/06 JUNIO/EXP-PREP-1", licitacion_id),
            )

        status, payload = patch_licitacion_state(app, licitacion_id, " preparada ")

    assert status == HTTPStatus.OK
    preview = payload["prepared_notice_preview"]
    assert preview["to"] == "info3@llangon.com"
    assert preview["can_send_email"] is True
    assert "EXP-PREP-1" in preview["subject"]
    assert "ha cambiado a Preparada" in preview["email_body"]
    assert "Fecha presentación: 30/06/2026 12:30" in preview["email_body"]
    assert "2026/06 JUNIO/EXP-PREP-1" in preview["whatsapp_text"]


def test_prepared_notice_preview_is_not_returned_when_already_prepared() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-PREP-2")
        with app.db_session() as conn:
            conn.execute("UPDATE licitaciones SET estado = ? WHERE id = ?", ("Preparada", licitacion_id))

        status, payload = patch_licitacion_state(app, licitacion_id, "Preparada")

    assert status == HTTPStatus.OK
    assert "prepared_notice_preview" not in payload


def test_prepared_notice_preview_disables_email_when_recipient_is_invalid() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-PREP-3")
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('prepared_notice_email_to', 'correo-no-valido', '2026-06-22T10:00:00')
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            )

        status, payload = patch_licitacion_state(app, licitacion_id, "Preparada")

    assert status == HTTPStatus.OK
    preview = payload["prepared_notice_preview"]
    assert preview["can_send_email"] is False
    assert "email válido" in preview["email_warning"]


def test_send_prepared_notice_email_uses_edited_recipient_and_edited_body(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []

    def fake_sender(**kwargs):
        sent.append(kwargs)
        return ("2026-06-22T10:30:00", None)

    monkeypatch.setattr(app, "send_notification_email_with_settings", fake_sender)
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-PREP-4")

        handler = make_handler(
            app,
            "POST",
            f"/api/licitaciones/{licitacion_id}/prepared-notice/email",
            {
                "to": "nuria.extra@example.test",
                "subject": "Ficha preparada — EXP-PREP-4 — texto editado",
                "email_body": "Mensaje editado por Manolo.",
            },
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert sent
    assert sent[0]["recipients"] == ["nuria.extra@example.test"]
    assert sent[0]["subject"] == "Ficha preparada — EXP-PREP-4 — texto editado"
    assert sent[0]["body"] == "Mensaje editado por Manolo."


def test_send_prepared_notice_email_rejects_invalid_edited_recipient(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []
    monkeypatch.setattr(app, "send_notification_email_with_settings", lambda **kwargs: sent.append(kwargs))

    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-PREP-5")

        handler = make_handler(
            app,
            "POST",
            f"/api/licitaciones/{licitacion_id}/prepared-notice/email",
            {
                "to": "correo-no-valido",
                "subject": "Ficha preparada — EXP-PREP-5",
                "email_body": "Mensaje editado por Manolo.",
            },
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "email de destino" in handler.responses[-1][1]["error"].lower()
    assert sent == []
