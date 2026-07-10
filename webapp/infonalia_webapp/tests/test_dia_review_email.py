from __future__ import annotations

from http import HTTPStatus

from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def prepare_dia_for_nuria(app) -> int:
    dia_id = insert_dia(app)
    licitacion_id = insert_licitacion(app, dia_id, "EXP-NURIA-1")
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE licitaciones
            SET estado = ?, fecha_limite = ?, hora_limite = ?
            WHERE id = ?
            """,
            ("Enviada a Nuria", "2026-06-30", "12:30", licitacion_id),
        )
    return dia_id


def test_send_dia_to_nuria_uses_confirmed_email_recipient(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []

    def fake_send_notification_email(usuario_destino, asunto, cuerpo, email_recipients=None, html_body=None):
        sent.append(
            {
                "usuario_destino": usuario_destino,
                "asunto": asunto,
                "cuerpo": cuerpo,
                "email_recipients": email_recipients,
                "html_body": html_body,
            }
        )
        return ("2026-06-24T10:00:00", None)

    monkeypatch.setattr(app, "send_notification_email", fake_send_notification_email)
    with temporary_app_database(app):
        dia_id = prepare_dia_for_nuria(app)
        handler = make_handler(
            app,
            "POST",
            f"/api/dias/{dia_id}/enviar-nuria",
            {"notification_email": "otro-destino@example.test"},
        )

        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert sent
    assert sent[0]["usuario_destino"] == app.REVIEWER_USER
    assert sent[0]["email_recipients"] == ["otro-destino@example.test"]
    assert "Infonalia del día" in sent[0]["asunto"]
    assert "EXP-NURIA-1" in sent[0]["cuerpo"]
    assert "Descartar" in sent[0]["html_body"]
    assert "Descargar para ver" in sent[0]["html_body"]
    assert "Preparar ficha" in sent[0]["html_body"]
    assert "Revisado" in sent[0]["html_body"]
    assert "cc=" not in sent[0]["html_body"]


def test_send_dia_to_nuria_places_previous_notices_at_end_with_discard_only(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []

    def fake_send_notification_email(usuario_destino, asunto, cuerpo, email_recipients=None, html_body=None):
        sent.append({"cuerpo": cuerpo, "html_body": html_body})
        return ("2026-06-24T10:00:00", None)

    monkeypatch.setattr(app, "send_notification_email", fake_send_notification_email)
    with temporary_app_database(app):
        dia_id = prepare_dia_for_nuria(app)
        previous_id = insert_licitacion(app, dia_id, "EXP-PREVIO-1")
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE licitaciones
                SET tipo_publicacion = ?, estado = ?, fecha_limite = ?, hora_limite = ?
                WHERE id = ?
                """,
                ("anuncio_previo", "Importada", "", "", previous_id),
            )
        handler = make_handler(
            app,
            "POST",
            f"/api/dias/{dia_id}/enviar-nuria",
            {"notification_email": "nuria@example.test"},
        )

        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert sent
    html_body = sent[0]["html_body"]
    assert html_body.index("EXP-NURIA-1") < html_body.index("Anuncios previos") < html_body.index("EXP-PREVIO-1")
    previous_notice_section = html_body.split("Anuncios previos", 1)[1]
    assert "Descartar" in previous_notice_section
    assert "Descargar para ver" not in previous_notice_section
    assert "Preparar ficha" not in previous_notice_section
    assert "Anuncio previo: EXP-PREVIO-1" in sent[0]["cuerpo"]


def test_send_dia_to_nuria_uses_configured_action_mailbox_cc(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []

    def fake_send_notification_email(usuario_destino, asunto, cuerpo, email_recipients=None, html_body=None):
        sent.append({"html_body": html_body})
        return ("2026-06-24T10:00:00", None)

    monkeypatch.setattr(app, "send_notification_email", fake_send_notification_email)
    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                ("action_mailbox_cc", "copia@example.test", "2026-06-24T09:00:00"),
            )
        dia_id = prepare_dia_for_nuria(app)
        handler = make_handler(
            app,
            "POST",
            f"/api/dias/{dia_id}/enviar-nuria",
            {"notification_email": "otro-destino@example.test"},
        )

        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert sent
    assert "cc=copia%40example.test" in sent[0]["html_body"]


def test_send_dia_to_nuria_rejects_invalid_confirmed_email(monkeypatch) -> None:
    app = load_app_module()
    sent: list[dict] = []
    monkeypatch.setattr(
        app,
        "send_notification_email",
        lambda *args, **kwargs: sent.append({"args": args, "kwargs": kwargs}),
    )

    with temporary_app_database(app):
        dia_id = prepare_dia_for_nuria(app)
        handler = make_handler(
            app,
            "POST",
            f"/api/dias/{dia_id}/enviar-nuria",
            {"notification_email": "correo-no-valido"},
        )

        dispatch(handler, "POST")

        with app.db_session() as conn:
            row = conn.execute("SELECT estado, enviado_nuria_at FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "correo de destino" in handler.responses[-1][1]["error"]
    assert sent == []
    assert row["estado"] == "Importado"
    assert not row["enviado_nuria_at"]
