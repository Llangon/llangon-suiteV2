from __future__ import annotations

from http import HTTPStatus

import pytest

from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
)


POST_CASES = [
    ("POST", "/api/licitaciones", "api_create_licitacion", ()),
    ("POST", "/api/licitaciones/capture", "api_capture_licitacion", ()),
    ("POST", "/api/config/users", "api_create_user", ()),
    ("POST", "/api/config/test-smtp", "api_test_smtp", ()),
    ("POST", "/api/clientes", "api_create_cliente", ()),
    ("POST", "/api/cliente-envios", "api_create_cliente_envio", ()),
    ("POST", "/api/cliente-envios/folder-files", "api_cliente_envio_folder_files", ()),
    ("POST", "/api/admin/telegram/test-group", "api_test_telegram_group", ()),
    ("POST", "/api/admin/users/manolo/telegram/test", "api_test_telegram_user", ("manolo",)),
    ("POST", "/api/storage/markers/sync", "api_storage_markers_sync", ()),
    ("POST", "/api/news", "api_create_news", ()),
    ("POST", "/api/import/msg", "api_import_msg", ()),
    ("POST", "/api/import/csv", "api_import_csv", ()),
    ("POST", "/api/agenda/email-summary", "api_send_agenda_email_summary", ()),
    ("POST", "/api/agenda/eventos", "api_create_agenda_evento", ()),
    ("POST", "/api/dias/7/revisado", "api_mark_dia_revisado", (7,)),
    ("POST", "/api/dias/7/enviar-nuria", "api_send_dia_to_nuria", (7,)),
    ("POST", "/api/dias/7/desmarcar-revisado", "api_unmark_dia_revisado", (7,)),
    ("POST", "/api/licitaciones/9/descargar", "api_download_licitacion", (9,)),
    ("POST", "/api/licitaciones/9/open-folder", "api_open_licitacion_folder", (9,)),
    ("POST", "/api/licitaciones/9/ia-preview/email", "api_send_ai_preview_email", (9,)),
    ("POST", "/api/licitaciones/9/prepared-notice/email", "api_send_prepared_notice_email", (9,)),
    ("POST", "/api/licitaciones/9/ia-preview", "api_generate_ai_preview", (9,)),
    ("POST", "/api/actuaciones", "api_create_actuacion", ()),
    ("POST", "/api/licitaciones/9/actuaciones", "api_create_actuacion", (9,)),
    ("POST", "/api/actuaciones/3/cerrar", "api_close_actuacion", (3,)),
    ("POST", "/api/actuaciones/3/cancelar", "api_cancel_actuacion", (3,)),
    ("POST", "/api/actuaciones/3/historial", "api_add_actuacion_historial", (3,)),
    ("POST", "/api/actuaciones/3/duplicar", "api_duplicate_actuacion", (3,)),
    ("POST", "/api/cliente-envios/4/generate-draft", "api_generate_cliente_envio_draft", (4,)),
    ("POST", "/api/cliente-envios/4/mark-sent", "api_mark_cliente_envio_sent", (4,)),
    ("POST", "/api/cliente-envios/4/open-folder", "api_open_cliente_envio_folder", (4,)),
    ("POST", "/api/cliente-envios/4/open-draft", "api_open_cliente_envio_draft", (4,)),
    ("POST", "/api/agenda/eventos/4/cerrar", "api_set_agenda_evento_estado", (4, "cerrado")),
    ("POST", "/api/agenda/eventos/4/cancelar", "api_set_agenda_evento_estado", (4, "cancelado")),
]

PATCH_CASES = [
    ("PATCH", "/api/clientes/7", "api_update_cliente", (7,)),
    ("PATCH", "/api/cliente-envios/4", "api_update_cliente_envio", (4,)),
    ("PATCH", "/api/agenda/eventos/4", "api_update_agenda_evento", (4,)),
    ("PATCH", "/api/actuaciones/3", "api_update_actuacion", (3,)),
    ("PATCH", "/api/licitaciones/9", "api_update_licitacion", (9,)),
    ("PATCH", "/api/config/users/admin_test", "api_update_user", ("admin_test",)),
    ("PATCH", "/api/config/settings", "api_update_settings", ()),
    ("PATCH", "/api/news/4", "api_update_news", (4,)),
]

DELETE_CASES = [
    ("DELETE", "/api/licitaciones/9", "api_delete_licitacion", (9,)),
    ("DELETE", "/api/dias/7", "api_delete_dia", (7,)),
    ("DELETE", "/api/config/users/admin_test", "api_delete_user", ("admin_test",)),
    ("DELETE", "/api/news/4", "api_delete_news", (4,)),
]


def make_csrf_handler(app, method: str, path: str, csrf_token: str | None = None):
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = path
    handler.headers = {}
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.responses = []
    handler.errors = []
    handler.called = []
    handler.current_user = lambda: {
        "username": "admin_test",
        "role": "admin",
        "display_name": "Admin Test",
        "csrf_token": VALID_CSRF_TOKEN,
    }

    def send_json(payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    handler.send_json = send_json
    handler.send_error = send_error
    return handler


def install_fake_endpoint(handler, endpoint_name: str):
    def fake_endpoint(*args):
        handler.called.append((endpoint_name, args))

    setattr(handler, endpoint_name, fake_endpoint)


@pytest.mark.parametrize(("method", "path", "endpoint_name", "expected_args"), POST_CASES + PATCH_CASES + DELETE_CASES)
def test_private_mutating_routes_reject_missing_csrf_before_endpoint(method, path, endpoint_name, expected_args) -> None:
    app = load_app_module()
    handler = make_csrf_handler(app, method, path)
    install_fake_endpoint(handler, endpoint_name)

    getattr(handler, f"do_{method}")()

    assert handler.called == []
    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]


@pytest.mark.parametrize(("method", "path", "endpoint_name", "expected_args"), POST_CASES + PATCH_CASES + DELETE_CASES)
def test_private_mutating_routes_accept_valid_csrf_and_reach_endpoint(method, path, endpoint_name, expected_args) -> None:
    app = load_app_module()
    handler = make_csrf_handler(app, method, path, csrf_token=VALID_CSRF_TOKEN)
    install_fake_endpoint(handler, endpoint_name)

    getattr(handler, f"do_{method}")()

    assert handler.responses == []
    assert handler.errors == []
    assert handler.called == [(endpoint_name, expected_args)]


def test_unknown_post_route_is_not_converted_to_csrf_error() -> None:
    app = load_app_module()
    handler = make_csrf_handler(app, "POST", "/api/unknown")

    handler.do_POST()

    assert handler.responses == []
    assert handler.errors[-1][0] == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/news"),
        ("PATCH", "/api/news/4"),
        ("DELETE", "/api/news/4"),
    ],
)
def test_app_csrf_decision_uses_global_policy_for_known_mutations(method, path) -> None:
    app = load_app_module()
    handler = make_csrf_handler(app, method, path)

    assert handler.csrf_required_for_path(method, path) is True


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/login"),
        ("GET", "/api/news"),
        ("POST", "/api/unknown"),
        ("PATCH", "/api/unknown"),
        ("DELETE", "/api/unknown"),
    ],
)
def test_app_csrf_decision_keeps_global_exceptions_and_unknown_routes(method, path) -> None:
    app = load_app_module()
    handler = make_csrf_handler(app, method, path)

    assert handler.csrf_required_for_path(method, path) is False
