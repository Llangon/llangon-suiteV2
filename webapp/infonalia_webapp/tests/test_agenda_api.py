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


def test_agenda_today_returns_open_overdue_and_today_events() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_open = insert_licitacion(app, dia_id, "AGENDA-LIC-HOY")
        licitacion_closed = insert_licitacion(app, dia_id, "AGENDA-LIC-DESC")
        now = datetime.now().replace(microsecond=0)
        set_licitacion_deadline(app, licitacion_open, fecha=now.date().isoformat(), hora="23:00", estado="Hacer")
        set_licitacion_deadline(app, licitacion_closed, fecha=now.date().isoformat(), hora="23:00", estado="Descartar")
        create_actuacion(app, None, titulo="Actuación hoy", deadline_at=(now + timedelta(hours=1)).isoformat())
        create_actuacion(app, None, titulo="Actuación cerrada", estado="cerrada", deadline_at=(now + timedelta(hours=1)).isoformat())
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
