from __future__ import annotations

from http import HTTPStatus

import pytest

from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
)


POST_CASES = [
    ("POST", "/api/licitaciones", "api_create_licitacion", ()),
    ("POST", "/api/config/users", "api_create_user", ()),
    ("POST", "/api/config/test-smtp", "api_test_smtp", ()),
    ("POST", "/api/news", "api_create_news", ()),
    ("POST", "/api/import/msg", "api_import_msg", ()),
    ("POST", "/api/import/csv", "api_import_csv", ()),
    ("POST", "/api/dias/7/revisado", "api_mark_dia_revisado", (7,)),
    ("POST", "/api/dias/7/enviar-nuria", "api_send_dia_to_nuria", (7,)),
    ("POST", "/api/dias/7/desmarcar-revisado", "api_unmark_dia_revisado", (7,)),
    ("POST", "/api/licitaciones/9/descargar", "api_download_licitacion", (9,)),
    ("POST", "/api/licitaciones/9/ia-preview/email", "api_send_ai_preview_email", (9,)),
    ("POST", "/api/licitaciones/9/ia-preview", "api_generate_ai_preview", (9,)),
]

PATCH_CASES = [
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
