from __future__ import annotations

import io
from contextlib import contextmanager
from http import HTTPStatus
from http.cookies import SimpleCookie
from urllib.parse import urlencode

from webapp.infonalia_webapp.tests.test_import_endpoints import (
    PRODUCTIVE_DB_PATH,
    load_app_module,
    temporary_app_database,
)


@contextmanager
def temporary_rate_limiter(app, max_attempts: int = 2):
    old_limiter = app.LOGIN_RATE_LIMITER
    app.LOGIN_RATE_LIMITER = app.LoginRateLimiter(max_attempts=max_attempts, window_seconds=300)
    try:
        yield app.LOGIN_RATE_LIMITER
    finally:
        app.LOGIN_RATE_LIMITER = old_limiter


def make_login_handler(app, username: str, password: str, ip: str = "127.0.0.1"):
    body = urlencode({"username": username, "password": password}).encode("utf-8")
    handler = object.__new__(app.InfonaliaHandler)
    handler.headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(body)),
    }
    handler.rfile = io.BytesIO(body)
    handler.client_address = (ip, 12345)
    handler.statuses = []
    handler.headers_sent = []

    def send_response(status):
        handler.statuses.append(status)

    def send_header(name, value):
        handler.headers_sent.append((name, value))

    def end_headers():
        return None

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    return handler


def last_header(handler, name: str) -> str:
    for header_name, value in reversed(handler.headers_sent):
        if header_name.lower() == name.lower():
            return value
    return ""


def session_cookie_value(handler) -> str:
    cookie = SimpleCookie(last_header(handler, "Set-Cookie"))
    morsel = cookie.get("infonalia_session")
    return morsel.value if morsel else ""


def test_repeated_failed_login_is_rate_limited_with_temp_db() -> None:
    app = load_app_module()
    existed_before = PRODUCTIVE_DB_PATH.exists()
    stat_before = PRODUCTIVE_DB_PATH.stat().st_mtime_ns if existed_before else None

    with temporary_app_database(app), temporary_rate_limiter(app, max_attempts=2):
        first = make_login_handler(app, "admin_test", "bad-password")
        first.handle_login()
        second = make_login_handler(app, "admin_test", "bad-password")
        second.handle_login()
        third = make_login_handler(app, "admin_test", "bad-password")
        third.handle_login()

        assert first.statuses[-1] == HTTPStatus.SEE_OTHER
        assert last_header(first, "Location") == "/login?error=1"
        assert second.statuses[-1] == HTTPStatus.SEE_OTHER
        assert last_header(second, "Location") == "/login?error=1"
        assert third.statuses[-1] == HTTPStatus.SEE_OTHER
        assert last_header(third, "Location") == "/login?error=rate"

    assert PRODUCTIVE_DB_PATH.exists() is existed_before
    if existed_before:
        assert PRODUCTIVE_DB_PATH.stat().st_mtime_ns == stat_before


def test_successful_login_clears_failed_attempts_and_sets_cookie() -> None:
    app = load_app_module()

    with temporary_app_database(app), temporary_rate_limiter(app, max_attempts=2) as limiter:
        failed = make_login_handler(app, "admin_test", "bad-password")
        failed.handle_login()

        success = make_login_handler(app, "admin_test", "admin_password_test")
        success.handle_login()

        login_key = app.normalize_login_key("127.0.0.1", "admin_test")

        assert success.statuses[-1] == HTTPStatus.SEE_OTHER
        assert last_header(success, "Location") == "/app"
        assert "HttpOnly" in last_header(success, "Set-Cookie")
        assert "SameSite=Lax" in last_header(success, "Set-Cookie")
        assert "Path=/" in last_header(success, "Set-Cookie")
        payload = app.read_token(session_cookie_value(success))
        assert payload
        assert payload["csrf"]
        assert limiter.is_limited(login_key) is False


def test_current_user_lazily_adds_csrf_to_old_signed_session() -> None:
    app = load_app_module()

    with temporary_app_database(app):
        old_token = app.encode_token_payload(
            {
                "u": "admin_test",
                "r": "admin",
                "iat": int(app.time.time()),
            }
        )
        handler = object.__new__(app.InfonaliaHandler)
        handler.headers = {"Cookie": f"{app.SESSION_COOKIE}={old_token}"}

        user = handler.current_user()

        assert user
        assert user["csrf_token"]
        refreshed_cookie = getattr(handler, "_pending_session_cookie", "")
        assert refreshed_cookie
        refreshed_payload = app.read_token(refreshed_cookie)
        assert refreshed_payload["csrf"] == user["csrf_token"]
