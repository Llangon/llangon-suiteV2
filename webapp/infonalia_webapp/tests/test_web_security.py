from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.web_security import (
    LoginRateLimiter,
    build_clear_cookie,
    build_security_headers,
    build_session_cookie,
    normalize_login_key,
)


def test_web_security_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.web_security", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.web_security")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_private_security_headers_include_basic_hardening() -> None:
    headers = build_security_headers(is_private=True)

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cache-Control"] == "no-store"


def test_session_cookie_contains_expected_attributes() -> None:
    cookie = build_session_cookie("session", "token", max_age=60, secure=False)

    assert cookie.startswith("session=token")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=60" in cookie
    assert "Secure" not in cookie


def test_session_cookie_adds_secure_when_requested() -> None:
    cookie = build_session_cookie("session", "token", secure=True)

    assert "Secure" in cookie


def test_clear_cookie_expires_session_cookie() -> None:
    cookie = build_clear_cookie("session", secure=True)

    assert cookie.startswith("session=")
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie


def test_normalize_login_key_normalizes_username() -> None:
    assert normalize_login_key("127.0.0.1", "  Admin@Test.COM ") == "127.0.0.1|admin@test.com"


def test_rate_limiter_allows_attempts_below_limit() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)

    assert limiter.is_limited(key) is False


def test_rate_limiter_blocks_at_limit() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)

    assert limiter.is_limited(key) is True


def test_rate_limiter_clears_after_success() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)
    limiter.clear(key)

    assert limiter.is_limited(key) is False


def test_rate_limiter_separates_users_and_ips() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=300, now=lambda: current_time)
    admin_key = normalize_login_key("127.0.0.1", "admin")
    other_user_key = normalize_login_key("127.0.0.1", "other")
    other_ip_key = normalize_login_key("127.0.0.2", "admin")

    limiter.record_failure(admin_key)

    assert limiter.is_limited(admin_key) is True
    assert limiter.is_limited(other_user_key) is False
    assert limiter.is_limited(other_ip_key) is False

