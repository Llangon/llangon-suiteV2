from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timedelta
from http import HTTPStatus

from webapp.infonalia_webapp.agenda.email_summary import (
    build_operational_email_html,
    build_operational_email_text,
)
from webapp.infonalia_webapp.agenda.pending_tasks import (
    build_pending_tasks_response,
    is_pending_task_state,
    task_state_label,
)
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


def pending_tasks(app, *, username: str = "admin_test", role: str = "admin") -> tuple[HTTPStatus, dict]:
    handler = make_handler(app, "GET", "/api/agenda/pending-tasks", {}, csrf_token=None, username=username, role=role)
    dispatch(handler, "GET")
    status, payload = handler.responses[-1]
    return status, payload


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


def set_licitacion_deadline(app, licitacion_id: int, *, fecha: str, hora: str = "12:00", estado: str = "Preparar ficha") -> None:
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
        set_licitacion_deadline(app, licitacion_open, fecha=now.date().isoformat(), hora="23:00", estado="Preparar ficha")
        set_licitacion_deadline(app, licitacion_closed, fecha=now.date().isoformat(), hora="23:00", estado="Descartada")
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
        set_licitacion_deadline(app, licitacion_open, fecha="2026-06-14", hora="18:00", estado="Preparar ficha")
        set_licitacion_deadline(app, licitacion_overdue, fecha="2026-06-14", hora="09:00", estado="Preparar ficha")
        set_licitacion_deadline(app, licitacion_discarded, fecha="2026-06-14", hora="18:00", estado="Descartada")
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


def test_agenda_licitaciones_follow_official_visible_states() -> None:
    app = load_app_module()
    current = datetime(2026, 6, 14, 12, 0, 0)
    visible_states = {
        "Descargar para ver",
        "Preparar ficha",
        "Preparada",
    }
    hidden_states = {
        "Importada",
        "Descartada",
        "Enviada a Nuria",
        "Oferta enviada",
    }
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        for state in sorted(visible_states | hidden_states):
            licitacion_id = insert_licitacion(app, dia_id, f"AGENDA-{state}")
            set_licitacion_deadline(app, licitacion_id, fecha="2026-06-14", hora="18:00", estado=state)

        with app.db_session() as conn:
            events = app.build_agenda_events(
                conn,
                view="today",
                target_date=current.date(),
                include_overdue=True,
                current=current,
            )

    event_titles = titles(events)
    for state in visible_states:
        assert f"AGENDA-{state}" in event_titles
    for state in hidden_states:
        assert f"AGENDA-{state}" not in event_titles


def test_pending_task_state_normalization() -> None:
    assert task_state_label("pendiente") == "Pendiente"
    assert task_state_label("en_curso") == "Pendiente"
    assert task_state_label("preparada") == "Preparado"
    assert task_state_label("respondida") == "Enviado"
    assert task_state_label("cerrada") == "Enviado"
    assert task_state_label("enviada") == "Enviado"
    assert task_state_label("cancelada") == "Cancelado"
    assert is_pending_task_state("pendiente") is True
    assert is_pending_task_state("preparado") is True
    assert is_pending_task_state("enviado") is False
    assert is_pending_task_state("cancelado") is False


def test_pending_tasks_endpoint_filters_items_and_requires_admin() -> None:
    app = load_app_module()
    current = datetime(2026, 6, 14, 12, 0, 0)
    visible_licitaciones = {
        "PT-LIC-DESCARGAR": "Descargar para ver",
        "PT-LIC-PREPARAR": "Preparar ficha",
        "PT-LIC-PREPARADA": "Preparada",
    }
    hidden_licitaciones = {
        "PT-LIC-IMPORTADA": "Importada",
        "PT-LIC-DESCARTADA": "Descartada",
        "PT-LIC-NURIA": "Enviada a Nuria",
        "PT-LIC-OFERTA": "Oferta enviada",
    }
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        for expediente, state in {**visible_licitaciones, **hidden_licitaciones}.items():
            licitacion_id = insert_licitacion(app, dia_id, expediente)
            set_licitacion_deadline(app, licitacion_id, fecha="2026-06-14", hora="18:00", estado=state)
        create_actuacion(app, None, titulo="PT actuación pendiente", estado="pendiente", deadline_at="2026-06-14T18:00:00")
        create_actuacion(app, None, titulo="PT actuación preparada", estado="preparado", deadline_at="2026-06-15T09:00:00")
        create_actuacion(app, None, titulo="PT actuación enviada", estado="enviado", deadline_at="2026-06-14T18:00:00")
        create_actuacion(app, None, titulo="PT actuación cancelada", estado="cancelado", deadline_at="2026-06-14T18:00:00")
        create_internal_event(app, titulo="PT interno pendiente", estado="pendiente", starts_at="2026-06-14T18:00:00")
        create_internal_event(app, titulo="PT interno preparado", estado="preparado", starts_at="2026-06-15T09:00:00")
        create_internal_event(app, titulo="PT interno enviado", estado="enviado", starts_at="2026-06-14T18:00:00")
        create_internal_event(app, titulo="PT interno cancelado", estado="cancelado", starts_at="2026-06-14T18:00:00")

        status, payload = pending_tasks(app)
        nuria_status, _nuria_payload = pending_tasks(app, username="reviewer_test", role="nuria")
        with app.db_session() as conn:
            direct = build_pending_tasks_response(conn, current=current)

    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    titles_found = titles(payload["items"])
    sample_licitacion = next(item for item in payload["items"] if item["source_type"] == "licitacion")
    for key in (
        "expediente",
        "organismo",
        "objeto",
        "tipo",
        "presupuesto",
        "fecha_limite",
        "hora_limite",
        "plataforma",
        "enlace_perfil",
        "enlace_infonalia",
        "ruta_carpeta",
    ):
        assert key in sample_licitacion
    assert set(visible_licitaciones) <= titles_found
    assert "PT actuación pendiente" in titles_found
    assert "PT actuación preparada" in titles_found
    assert "PT interno pendiente" in titles_found
    assert "PT interno preparado" in titles_found
    for title in [*hidden_licitaciones, "PT actuación enviada", "PT actuación cancelada", "PT interno enviado", "PT interno cancelado"]:
        assert title not in titles_found
    assert nuria_status == HTTPStatus.FORBIDDEN
    direct_titles = [item["title"] for item in direct["items"]]
    assert direct_titles.index("PT-LIC-DESCARGAR") < direct_titles.index("PT actuación preparada")


def test_pending_task_quick_state_updates_remove_closed_items() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "PT-QUICK-LIC")
        set_licitacion_deadline(app, licitacion_id, fecha="2026-06-14", hora="18:00", estado="Preparar ficha")
        actuacion = create_actuacion(app, None, titulo="PT quick actuación", estado="pendiente", deadline_at="2026-06-14T18:00:00")
        evento = create_internal_event(app, titulo="PT quick interno", estado="pendiente", starts_at="2026-06-14T18:00:00")

        lic_patch = make_handler(app, "PATCH", f"/api/licitaciones/{licitacion_id}", {"estado": "Oferta enviada"})
        dispatch(lic_patch, "PATCH")
        act_patch = make_handler(app, "PATCH", f"/api/actuaciones/{actuacion['id']}", {"estado": "enviado"})
        dispatch(act_patch, "PATCH")
        event_patch = make_handler(app, "PATCH", f"/api/agenda/eventos/{evento['id']}", {"estado": "enviado"})
        dispatch(event_patch, "PATCH")
        _status, payload = pending_tasks(app)

    assert lic_patch.responses[-1][0] == HTTPStatus.OK
    assert act_patch.responses[-1][0] == HTTPStatus.OK
    assert event_patch.responses[-1][0] == HTTPStatus.OK
    assert {"PT-QUICK-LIC", "PT quick actuación", "PT quick interno"}.isdisjoint(titles(payload["items"]))


def test_agenda_week_month_and_type_filters() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "AGENDA-LIC-WEEK")
        monday = datetime(2026, 6, 15, 10, 0, 0)
        set_licitacion_deadline(app, licitacion_id, fecha="2026-06-17", hora="11:00", estado="Preparar ficha")
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
        set_licitacion_deadline(app, licitacion_id, fecha=now.date().isoformat(), hora="23:00", estado="Preparar ficha")
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


def test_agenda_workbench_counts_operational_priorities_in_order() -> None:
    app = load_app_module()
    current = datetime(2026, 6, 15, 12, 0, 0)
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        new_licitacion = insert_licitacion(app, dia_id, "WB-NUEVA")
        failed_licitacion = insert_licitacion(app, dia_id, "WB-DESCARGA")
        with app.db_session() as conn:
            conn.execute(
                "INSERT INTO download_jobs (licitacion_id, status, error_message, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (failed_licitacion, "failed", "fallo simulado", current.isoformat(), current.isoformat()),
            )
        create_actuacion(app, [new_licitacion], titulo="WB vencida", deadline_at="2026-06-15T09:00:00")
        create_actuacion(app, None, titulo="WB hoy", deadline_at="2026-06-15T18:00:00")
        create_actuacion(app, None, titulo="WB próxima", deadline_at="2026-06-20T12:00:00")
        create_actuacion(app, None, titulo="WB sin fecha", deadline_at="")
        create_actuacion(app, None, titulo="WB cerrada", estado="cerrada", deadline_at="2026-06-14T10:00:00")
        with app.db_session() as conn:
            data = app.build_agenda_workbench(conn, current=current)

    assert data["summary"]["overdue_count"] == 1
    assert data["summary"]["due_today_count"] == 1
    assert data["summary"]["next_7_days_count"] == 1
    assert data["summary"]["without_date_count"] == 1
    assert data["summary"]["new_licitaciones_count"] == 2
    assert data["summary"]["failed_downloads_count"] == 1
    assert [section["key"] for section in data["sections"]] == [
        "overdue",
        "due_today",
        "next_7_days",
        "without_date",
        "new_licitaciones",
        "failed_downloads",
    ]
    assert data["actuaciones_by_licitacion"][0]["expediente"] == "WB-NUEVA"


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
                "smtp_enabled": "0",
                "smtp_tls": "0",
                "smtp_ssl": "0",
                "email_dry_run": "0",
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
            {"view": "all", "date": "2026-06-14", "dry_run": False},
            email="agenda-user@example.test",
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert FakeSMTP.sent_messages
    message = FakeSMTP.sent_messages[0]
    assert message["To"] == "agenda-user@example.test"
    plain_body = message.get_body(preferencelist=("plain",)).get_content()
    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert "Resumen operativo" in plain_body
    assert "Agenda Llangón" in html_body
    assert "Resumen operativo diario" in html_body
    assert "PRINCIPAL / HOY" in html_body
    assert "RESTO DE LA SEMANA HASTA DOMINGO" in html_body
    assert "Resumen interno" in html_body
    assert "Sin elementos" in html_body
    assert "cid:llangon-logo" in html_body
    assert "Este es tu resumen operativo de Agenda" in html_body
    assert handler.responses[-1][1]["sent"] is True
    assert handler.responses[-1][1]["dry_run"] is False


def test_agenda_operational_email_template_matches_infonalia_family_and_empty_sections() -> None:
    payload = {
        "active_date_label": "14/06/2026",
        "sections": [
            {"title": "Principal / Hoy", "items": []},
            {"title": "Resto de la semana hasta domingo", "items": []},
        ],
        "counts": {"today": 0, "week_rest": 0},
    }

    text_body = build_operational_email_text(payload)
    html_body = build_operational_email_html(payload, generated_at="2026-06-14T10:30:00")

    assert "Agenda Llangón - Resumen operativo diario" in text_body
    assert "PRINCIPAL / HOY" in text_body
    assert "RESTO DE LA SEMANA HASTA DOMINGO" in text_body
    assert "- Sin elementos" in text_body
    assert "Consulta la aplicación para acceder al detalle completo." in text_body
    assert "<!doctype html>" in html_body
    assert "Llangón Web App" in html_body
    assert "Agenda Llangón" in html_body
    assert "Resumen operativo diario" in html_body
    assert "PRINCIPAL / HOY" in html_body
    assert "RESTO DE LA SEMANA HASTA DOMINGO" in html_body
    assert html_body.count("Sin elementos") == 2
    assert "cid:llangon-logo" in html_body
    assert "14/06/2026 10:30" in html_body
    assert "Este es tu resumen operativo de Agenda" in html_body


def test_agenda_email_summary_dry_run_does_not_call_smtp(monkeypatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        create_internal_event(app, titulo="Dry run interno", starts_at="2026-06-14T10:00:00")
        monkeypatch.setattr(app.smtplib, "SMTP", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no smtp")))

        handler = make_handler(
            app,
            "POST",
            "/api/agenda/email-summary",
            {"view": "all", "date": "2026-06-14", "dry_run": True},
            email="agenda-user@example.test",
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.OK
    payload = handler.responses[-1][1]
    assert payload["sent"] is False
    assert payload["dry_run"] is True
    assert payload["recipient"] == "agenda-user@example.test"
    assert "Dry run interno" in payload["preview"]


def test_agenda_email_summary_without_smtp_returns_clear_error() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/agenda/email-summary",
            {"view": "all", "date": "2026-06-14"},
            email="agenda-user@example.test",
        )
        dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert handler.responses[-1][1]["error"] == "SMTP no configurado. No se ha enviado el correo."


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
