from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from types import ModuleType

from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import (
    count_rows,
    foreign_key_check_rows,
    insert_dia,
    insert_licitacion,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    temporary_app_database,
)


def teardown_function() -> None:
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)


def make_handler(
    app: ModuleType,
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    csrf_token: str | None = VALID_CSRF_TOKEN,
    username: str = "admin_test",
    role: str = "admin",
):
    body = json.dumps(payload or {}).encode("utf-8")
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = path
    handler.rfile = io.BytesIO(body)
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.responses = []
    handler.errors = []
    handler.current_user = lambda: {
        "username": username,
        "role": role,
        "display_name": username,
        "csrf_token": VALID_CSRF_TOKEN,
    }

    def send_json(response_payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, response_payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    handler.send_json = send_json
    handler.send_error = send_error
    return handler


def dispatch(handler, method: str) -> None:
    getattr(handler, f"do_{method}")()


def create_actuacion(app: ModuleType, licitacion_ids: list[int] | None = None, **overrides: object) -> dict:
    payload = {
        "tipo": "requerimiento",
        "titulo": "Aportar documentación",
        "descripcion": "Subir anexos requeridos",
        "deadline_at": (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat(),
        "recordatorio_email": True,
        "origen": "manual",
        "licitacion_ids": licitacion_ids or [],
    }
    payload.update(overrides)
    handler = make_handler(app, "POST", "/api/actuaciones", payload)
    dispatch(handler, "POST")
    assert handler.responses[-1][0] == HTTPStatus.CREATED
    return handler.responses[-1][1]["item"]


def list_actuaciones(app: ModuleType, query: str = "") -> list[dict]:
    handler = make_handler(app, "GET", f"/api/actuaciones{query}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]["items"]


def detail_actuacion(app: ModuleType, actuacion_id: int) -> dict:
    handler = make_handler(app, "GET", f"/api/actuaciones/{actuacion_id}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]["item"]


def test_create_actuacion_without_licitacion_and_filter() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        item = create_actuacion(app, None)
        rows = list_actuaciones(app, "?sin_licitacion=1")

        assert item["licitaciones"] == []
        assert item["licitaciones_count"] == 0
        assert rows[0]["titulo"] == "Aportar documentación"
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert foreign_key_check_rows(app) == []


def test_create_actuacion_with_one_and_multiple_licitaciones() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_a = insert_licitacion(app, dia_id, "ACT-001")
        licitacion_b = insert_licitacion(app, dia_id, "ACT-002")

        one = create_actuacion(app, [licitacion_a], titulo="Una")
        multiple = create_actuacion(app, [licitacion_a, licitacion_b, licitacion_a], titulo="Varias")
        rows = list_actuaciones(app, f"?licitacion_id={licitacion_b}")

        assert [item["id"] for item in one["licitaciones"]] == [licitacion_a]
        assert [item["id"] for item in multiple["licitaciones"]] == [licitacion_a, licitacion_b]
        assert [item["titulo"] for item in rows] == ["Varias"]
        assert count_rows(app, "actuacion_licitaciones") == 3


def test_update_licitaciones_and_detail_history() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_a = insert_licitacion(app, dia_id, "ACT-003")
        licitacion_b = insert_licitacion(app, dia_id, "ACT-004")
        item = create_actuacion(app, [licitacion_a])

        patch = make_handler(
            app,
            "PATCH",
            f"/api/actuaciones/{item['id']}",
            {"licitacion_ids": [licitacion_b], "estado": "en_curso"},
        )
        dispatch(patch, "PATCH")
        assert patch.responses[-1][0] == HTTPStatus.OK

        comment = make_handler(
            app,
            "POST",
            f"/api/actuaciones/{item['id']}/historial",
            {"comentario": "Comentario de seguimiento"},
        )
        dispatch(comment, "POST")
        assert comment.responses[-1][0] == HTTPStatus.CREATED

        detail = detail_actuacion(app, item["id"])
        assert [linked["id"] for linked in detail["licitaciones"]] == [licitacion_b]
        event_types = [entry["event_type"] for entry in detail["historial"]]
        assert "creacion" in event_types
        assert "licitaciones" in event_types
        assert "estado" in event_types
        assert "comentario" in event_types


def test_list_actuaciones_filters_vencidas_hoy_semana() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        now = datetime.now().replace(microsecond=0)
        create_actuacion(app, None, titulo="Vencida", deadline_at=(now - timedelta(hours=2)).isoformat())
        create_actuacion(app, None, titulo="Hoy", deadline_at=(now + timedelta(minutes=30)).isoformat())
        create_actuacion(app, None, titulo="Semana", deadline_at=(now + timedelta(days=3)).isoformat())

        assert [item["titulo"] for item in list_actuaciones(app, "?vencidas=1")] == ["Vencida"]
        assert [item["titulo"] for item in list_actuaciones(app, "?hoy=1")] == ["Hoy"]
        assert [item["titulo"] for item in list_actuaciones(app, "?semana=1")] == ["Semana"]


def test_close_and_cancel_actuacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        item = create_actuacion(app, None)

        close = make_handler(app, "POST", f"/api/actuaciones/{item['id']}/cerrar", {})
        dispatch(close, "POST")
        assert close.responses[-1][1]["item"]["estado"] == "cerrada"
        assert close.responses[-1][1]["item"]["closed_at"]

        second = create_actuacion(app, None, titulo="Cancelar")
        cancel = make_handler(app, "POST", f"/api/actuaciones/{second['id']}/cancelar", {})
        dispatch(cancel, "POST")
        assert cancel.responses[-1][1]["item"]["estado"] == "cancelada"


def test_licitaciones_search_for_selector() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "SEL-001")
        insert_licitacion(app, dia_id, "OTRA-002")

        handler = make_handler(app, "GET", "/api/licitaciones/search?q=SEL", {})
        dispatch(handler, "GET")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert [item["expediente"] for item in handler.responses[-1][1]["items"]] == ["SEL-001"]


def test_actuacion_mutations_reject_missing_csrf() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/actuaciones",
            {"titulo": "Sin CSRF"},
            csrf_token=None,
        )

        dispatch(handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert count_rows(app, "actuaciones") == 0


def test_delete_licitacion_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DEL")
        create_actuacion(app, [licitacion_id])

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert handler.responses[-1][1]["error"] == "No se puede borrar la licitación porque tiene actuaciones abiertas."
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 1


def test_delete_dia_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DIA")
        create_actuacion(app, [licitacion_id])

        handler = make_handler(app, "DELETE", f"/api/dias/{dia_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert handler.responses[-1][1]["error"] == "No se puede borrar el día porque contiene licitaciones con actuaciones abiertas."
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1


def test_delete_licitacion_with_closed_actuacion_only_unlinks_relation() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-CLOSED")
        item = create_actuacion(app, [licitacion_id], estado="cerrada")

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert detail_actuacion(app, item["id"])["estado"] == "cerrada"
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_closed_actuacion_only_unlinks_relations() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DIA-CLOSED")
        create_actuacion(app, [licitacion_id], estado="cancelada")

        handler = make_handler(app, "DELETE", f"/api/dias/{dia_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "infonalia_dias") == 0
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert foreign_key_check_rows(app) == []
