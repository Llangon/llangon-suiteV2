from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timedelta
from http import HTTPStatus

from webapp.infonalia_webapp.tests.test_actuaciones_api import create_actuacion, dispatch, make_handler
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import count_rows, insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    temporary_app_database,
)


def teardown_function() -> None:
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)


def agenda(app, query: str = "") -> dict:
    handler = make_handler(app, "GET", f"/api/agenda{query}", {}, csrf_token=None)
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]


def create_internal_event(app, **overrides: object) -> dict:
    payload = {
        "titulo": "Evento interno",
        "descripcion": "Seguimiento interno",
        "starts_at": (datetime.now() + timedelta(hours=1)).replace(microsecond=0).isoformat(),
        "estado": "pendiente",
    }
    payload.update(overrides)
    handler = make_handler(app, "POST", "/api/agenda/eventos", payload)
    dispatch(handler, "POST")
    assert handler.responses[-1][0] == HTTPStatus.CREATED
    return handler.responses[-1][1]["item"]


def set_licitacion_deadline(app, licitacion_id: int, *, fecha: str, hora: str = "12:00", estado: str = "Hacer") -> None:
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE licitaciones
            SET fecha_limite = ?, hora_limite = ?, estado = ?, updated_at = ?
            WHERE id = ?
            """,
            (fecha, hora, estado, datetime.now().replace(microsecond=0).isoformat(), licitacion_id),
        )


def titles(events: list[dict]) -> set[str]:
    return {event["title"] for event in events}


class FakeSMTP:
    sent_messages: list[object] = []

    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, *_args: object) -> None:
        return None

    def send_message(self, message: object) -> None:
        self.sent_messages.append(message)


def test_agenda_today_returns_open_overdue_and_today_events() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_open = insert_licitacion(app, dia_id, "AGENDA-LIC-HOY")
        licitacion_closed = insert_licitacion(app, dia_id, "AGENDA-LIC-DESC")
        now = datetime.now().replace(microsecond=0)
        set_licitacion_deadline(app, licitacion_open, fecha=now.date().isoformat(), hora="23:00", estado="Hacer")
        set_licitacion_deadline(app, licitacion_closed, fecha=now.date().isoformat(), hora="23:00", estado="Descartar")
        create_actuacion(app, None, titulo="Actuación hoy", deadline_at=f"{now.date().isoformat()}T23:30:00")
        create_actuacion(app, None, titulo="Actuación cerrada", estado="cerrada", deadline_at=f"{now.date().isoformat()}T23:30:00")
        create_internal_event(app, titulo="Interno vencido", starts_at=(now - timedelta(hours=1)).isoformat())
        create_internal_event(app, titulo="Interno cerrado", starts_at=(now + timedelta(hours=1)).isoformat(), estado="cerrado")

        data = agenda(app, f"?view=today&date={now.date().isoformat()}")

    event_titles = titles(data["events"])
    assert "Actuación hoy" in event_titles
    assert "AGENDA-LIC-HOY" in event_titles
    assert "Interno vencido" in event_titles
    assert "Actuación cerrada" not in event_titles
    assert "AGENDA-LIC-DESC" not in event_titles
    assert "Interno cerrado" not in event_titles
    overdue = [event for event in data["events"] if event["title"] == "Interno vencido"][0]
    assert overdue["color_type"] == "vencido"
    assert overdue["is_overdue"] is True


def test_agenda_color_type_contract_and_hidden_closed_items() -> None:
    app = load_app_module()
    current = datetime(2026, 6, 14, 12, 0, 0)
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_open = insert_licitacion(app, dia_id, "AGENDA-LIC-COLOR")
        licitacion_overdue = insert_licitacion(app, dia_id, "AGENDA-LIC-VENCIDA")
        licitacion_discarded = insert_licitacion(app, dia_id, "AGENDA-LIC-DESCARTADA")
        set_licitacion_deadline(app, licitacion_open, fecha="2026-06-14", hora="18:00", estado="Hacer")
        set_licitacion_deadline(app, licitacion_overdue, fecha="2026-06-14", hora="09:00", estado="Hacer")
        set_licitacion_deadline(app, licitacion_discarded, fecha="2026-06-14", hora="18:00", estado="Descartar")
        create_actuacion(app, None, titulo="Actuación color", deadline_at="2026-06-14T18:00:00")
        create_actuacion(app, None, titulo="Actuación vencida", deadline_at="2026-06-14T09:00:00")
        create_actuacion(app, None, titulo="Actuación cerrada color", estado="cerrada", deadline_at="2026-06-14T18:00:00")
        create_internal_event(app, titulo="Interno color", starts_at="2026-06-14T18:00:00")
        create_internal_event(app, titulo="Interno vencido color", starts_at="2026-06-14T09:00:00")
        create_internal_event(app, titulo="Interno cancelado color", starts_at="2026-06-14T18:00:00", estado="cancelado")

        with app.db_session() as conn:
            events = app.build_agenda_events(
                conn,
                view="today",
                target_date=current.date(),
                include_overdue=True,
                current=current,
            )

    colors = {event["title"]: event["color_type"] for event in events}
    assert colors["Actuación color"] == "actuacion"
    assert colors["AGENDA-LIC-COLOR"] == "licitacion"
    assert colors["Interno color"] == "interno"
    assert colors["Actuación vencida"] == "vencido"
    assert colors["AGENDA-LIC-VENCIDA"] == "vencido"
    assert colors["Interno vencido color"] == "vencido"
    assert "Actuación cerrada color" not in colors
    assert "AGENDA-LIC-DESCARTADA" not in colors
    assert "Interno cancelado color" not in colors


def test_agenda_week_month_and_type_filters() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "AGENDA-LIC-WEEK")
        monday = datetime(2026, 6, 15, 10, 0, 0)
        set_licitacion_deadline(app, licitacion_id, fecha="2026-06-17", hora="11:00", estado="Hacer")
        create_actuacion(app, None, titulo="Actuación semana", deadline_at="2026-06-18T10:00:00")
        create_internal_event(app, titulo="Interno mes", starts_at="2026-06-25T09:00:00")

        week = agenda(app, "?view=week&date=2026-06-15")
        month = agenda(app, "?view=month&date=2026-06-01&include_overdue=1")
        only_actuaciones = agenda(app, "?view=week&date=2026-06-15&type=actuacion")
        only_licitaciones = agenda(app, "?view=week&date=2026-06-15&type=licitacion")
        only_internos = agenda(app, "?view=month&date=2026-06-01&type=interno")

    assert monday.date().isoformat() == "2026-06-15"
    assert {"AGENDA-LIC-WEEK", "Actuación semana"} <= titles(week["events"])
    assert {"AGENDA-LIC-WEEK", "Actuación semana", "Interno mes"} <= titles(month["events"])
    assert titles(only_actuaciones["events"]) == {"Actuación semana"}
    assert titles(only_licitaciones["events"]) == {"AGENDA-LIC-WEEK"}
    assert titles(only_internos["events"]) == {"Interno mes"}


def test_agenda_day_all_filters_no_date_and_search() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "AGENDA-LIC-SEARCH")
        now = datetime.now().replace(microsecond=0)
        set_licitacion_deadline(app, licitacion_id, fecha=now.date().isoformat(), hora="23:00", estado="Hacer")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET organismo = ?, plataforma = ?, provincia = ? WHERE id = ?",
                ("Ayuntamiento de Pruebas", "PLACE Test", "Sevilla", licitacion_id),
            )
        create_actuacion(app, None, titulo="Actuación sin fecha API", deadline_at="")
        create_internal_event(app, titulo="Interno mañana API", starts_at=(now + timedelta(days=1)).isoformat())

        day = agenda(app, f"?view=day&date={now.date().isoformat()}")
        alias = agenda(app, f"?view=today&date={now.date().isoformat()}")
        all_events = agenda(app, f"?view=all&date={now.date().isoformat()}")
        no_date = agenda(app, f"?view=all&date={now.date().isoformat()}&type=sin_fecha")
        vencidos = agenda(app, f"?view=all&date={now.date().isoformat()}&type=vencido")
        search = agenda(app, f"?view=all&date={now.date().isoformat()}&q=ayuntamiento")
        month_no_date = agenda(app, f"?view=month&date={now.date().isoformat()}&type=sin_fecha")

    assert day["view"] == "day"
    assert alias["view"] == "day"
    assert "active_date_label" in day
    assert "AGENDA-LIC-SEARCH" in titles(day["events"])
    assert {"AGENDA-LIC-SEARCH", "Actuación sin fecha API", "Interno mañana API"} <= titles(all_events["events"])
    assert titles(no_date["events"]) == {"Actuación sin fecha API"}
    assert all(event["is_overdue"] for event in vencidos["events"])
    assert titles(search["events"]) == {"AGENDA-LIC-SEARCH"}
    assert month_no_date["events"] == []
    assert all_events["summary"]["no_date"] == 1
    assert all_events["summary"]["total_open"] >= 3


def test_agenda_includes_actuacion_without_deadline_in_today_only() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        create_actuacion(app, None, titulo="Actuación sin fecha", deadline_at="")

        today = agenda(app, "?view=today")
        month = agenda(app, "?view=month&date=2026-06-01&include_overdue=1")

    assert "Actuación sin fecha" in titles(today["events"])
    assert "Actuación sin fecha" not in titles(month["events"])


def test_internal_event_mutations_and_visibility() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        item = create_internal_event(app, titulo="Cerrar interno")

        patch = make_handler(app, "PATCH", f"/api/agenda/eventos/{item['id']}", {"estado": "en_curso"})
        dispatch(patch, "PATCH")
        assert patch.responses[-1][1]["item"]["estado"] == "en_curso"

        close = make_handler(app, "POST", f"/api/agenda/eventos/{item['id']}/cerrar", {})
        dispatch(close, "POST")
        assert close.responses[-1][1]["item"]["estado"] == "cerrado"

        cancelled = create_internal_event(app, titulo="Cancelar interno")
        cancel = make_handler(app, "POST", f"/api/agenda/eventos/{cancelled['id']}/cancelar", {})
        dispatch(cancel, "POST")
        assert cancel.responses[-1][1]["item"]["estado"] == "cancelado"

        data = agenda(app, "?view=today")

    assert "Cerrar interno" not in titles(data["events"])
    assert "Cancelar interno" not in titles(data["events"])


def test_internal_event_create_requires_csrf() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/agenda/eventos",
            {"titulo": "Sin CSRF", "starts_at": "2026-06-14T10:00:00"},
            csrf_token=None,
        )
        dispatch(handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert count_rows(app, "agenda_eventos") == 0


def test_agenda_email_summary_uses_logged_user_email_and_fake_smtp(monkeypatch) -> None:
    app = load_app_module()
    FakeSMTP.sent_messages = []
    with temporary_app_database(app):
        with app.db_session() as conn:
            for key, value in {
                "smtp_host": "smtp.example.test",
                "smtp_port": "2525",
                "smtp_from": "agenda@example.test",
                "smtp_tls": "0",
                "smtp_ssl": "0",
            }.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, "2026-06-14T10:00:00"),
                )
        create_internal_event(app, titulo="Resumen interno", starts_at="2026-06-14T10:00:00")
        monkeypatch.setattr(app.smtplib, "SMTP", FakeSMTP)

        handler = make_handler(
            app,
            "POST",
            "/api/agenda/email-summary",
            {"view": "all", "date": "2026-06-14"},
            email="agenda-user@example.test",
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert FakeSMTP.sent_messages
    message = FakeSMTP.sent_messages[0]
    assert message["To"] == "agenda-user@example.test"
    assert "Resumen de Agenda" in message.get_body(preferencelist=("plain",)).get_content()


def test_agenda_email_summary_requires_logged_user_email() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/agenda/email-summary",
            {"view": "all", "date": "2026-06-14"},
            email="",
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "email" in handler.responses[-1][1]["error"].lower()


def test_agenda_get_requires_auth_but_not_csrf() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        ok = make_handler(app, "GET", "/api/agenda?view=today", {}, csrf_token=None)
        dispatch(ok, "GET")
        assert ok.responses[-1][0] == HTTPStatus.OK

        body = json.dumps({}).encode("utf-8")
        unauth = object.__new__(app.InfonaliaHandler)
        unauth.path = "/api/agenda?view=today"
        unauth.rfile = io.BytesIO(body)
        unauth.headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        unauth.current_user = lambda: None
        unauth.redirects = []
        unauth.redirect = lambda location, clear_cookie=False: unauth.redirects.append((location, clear_cookie))
        unauth.do_GET()

    assert unauth.redirects == [("/login", False)]
