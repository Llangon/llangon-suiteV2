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


def create_actuacion(app: ModuleType, licitacion_id: int, **overrides: object) -> dict:
    payload = {
        "tipo": "requerimiento",
        "titulo": "Aportar documentación",
        "descripcion": "Subir anexos requeridos",
        "prioridad": "alta",
        "responsable_user_id": "admin_test",
        "deadline_at": (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat(),
        "recordatorio_email": True,
        "origen": "manual",
    }
    payload.update(overrides)
    handler = make_handler(app, "POST", f"/api/licitaciones/{licitacion_id}/actuaciones", payload)
    dispatch(handler, "POST")
    assert handler.responses[-1][0] == HTTPStatus.CREATED
    return handler.responses[-1][1]["item"]


def list_actuaciones(app: ModuleType, query: str = "") -> list[dict]:
    handler = make_handler(app, "GET", f"/api/actuaciones{query}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]["items"]


def test_create_and_list_actuacion_by_licitacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-001")

        item = create_actuacion(app, licitacion_id)
        rows = list_actuaciones(app, f"?licitacion_id={licitacion_id}")

        assert item["licitacion_id"] == licitacion_id
        assert rows[0]["titulo"] == "Aportar documentación"
        assert rows[0]["estado"] == "pendiente"
        assert foreign_key_check_rows(app) == []


def test_list_actuaciones_filters_vencidas_hoy_semana() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-002")
        now = datetime.now().replace(microsecond=0)
        create_actuacion(app, licitacion_id, titulo="Vencida", deadline_at=(now - timedelta(hours=2)).isoformat())
        create_actuacion(app, licitacion_id, titulo="Hoy", deadline_at=(now + timedelta(minutes=30)).isoformat())
        create_actuacion(app, licitacion_id, titulo="Semana", deadline_at=(now + timedelta(days=3)).isoformat())

        assert [item["titulo"] for item in list_actuaciones(app, "?vencidas=1")] == ["Vencida"]
        assert [item["titulo"] for item in list_actuaciones(app, "?hoy=1")] == ["Hoy"]
        assert [item["titulo"] for item in list_actuaciones(app, "?semana=1")] == ["Semana"]


def test_update_close_and_cancel_actuacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-003")
        item = create_actuacion(app, licitacion_id)

        patch = make_handler(app, "PATCH", f"/api/actuaciones/{item['id']}", {"estado": "en_curso"})
        dispatch(patch, "PATCH")
        assert patch.responses[-1][1]["item"]["estado"] == "en_curso"

        close = make_handler(app, "POST", f"/api/actuaciones/{item['id']}/cerrar", {})
        dispatch(close, "POST")
        assert close.responses[-1][1]["item"]["estado"] == "cerrada"
        assert close.responses[-1][1]["item"]["closed_at"]

        second = create_actuacion(app, licitacion_id, titulo="Cancelar")
        cancel = make_handler(app, "POST", f"/api/actuaciones/{second['id']}/cancelar", {})
        dispatch(cancel, "POST")
        assert cancel.responses[-1][1]["item"]["estado"] == "cancelada"


def test_actuacion_mutations_reject_missing_csrf() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-CSRF")
        handler = make_handler(
            app,
            "POST",
            f"/api/licitaciones/{licitacion_id}/actuaciones",
            {"titulo": "Sin CSRF"},
            csrf_token=None,
        )

        dispatch(handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert count_rows(app, "licitacion_actuaciones") == 0


def test_delete_licitacion_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DEL")
        create_actuacion(app, licitacion_id)

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "licitacion_actuaciones") == 1


def test_delete_dia_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DIA")
        create_actuacion(app, licitacion_id)

        handler = make_handler(app, "DELETE", f"/api/dias/{dia_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1


def test_delete_licitacion_with_closed_actuacion_removes_closed_record() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-CLOSED")
        item = create_actuacion(app, licitacion_id, estado="cerrada")

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "licitacion_actuaciones") == 0
        assert item["estado"] == "cerrada"
        assert foreign_key_check_rows(app) == []
