from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

from webapp.infonalia_webapp.web_security import (
    LoginRateLimiter,
    build_clear_cookie,
    build_content_security_policy,
    build_public_content_security_policy,
    build_security_headers,
    build_session_cookie,
    normalize_login_key,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
FIREBASE_ROOT = REPOSITORY_ROOT / "firebase" / "public_firebase"


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
    assert headers["Content-Security-Policy"] == build_content_security_policy()


def test_private_content_security_policy_is_strict_and_self_hosted() -> None:
    policy = build_content_security_policy()

    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "style-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "base-uri 'self'" in policy
    assert "form-action 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy


def test_public_security_headers_apply_public_csp_without_private_cache() -> None:
    headers = build_security_headers(is_private=False)

    assert headers["Content-Security-Policy"] == build_public_content_security_policy()
    assert "Cache-Control" not in headers


def test_private_html_entrypoints_do_not_need_inline_scripts() -> None:
    for name in ("index.html", "login.html"):
        html = (STATIC_ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"<script(?!\s+src=)", html)
        assert "<style" not in html
        assert not re.search(r"<[^>]+\son[a-z]+\s*=", html)


def test_public_html_entrypoints_do_not_need_inline_scripts() -> None:
    for path in (STATIC_ROOT / "public.html", FIREBASE_ROOT / "index.html"):
        html = path.read_text(encoding="utf-8")
        assert 'data-private-app-url="' in html
        assert not re.search(r"<script(?!\s+src=)", html)
        assert "<style" not in html
        assert not re.search(r"<[^>]+\son[a-z]+\s*=", html)


def test_firebase_hosting_headers_include_public_csp() -> None:
    config = json.loads((FIREBASE_ROOT / "firebase.json").read_text(encoding="utf-8"))
    headers = config["hosting"]["headers"]
    global_headers = next(entry["headers"] for entry in headers if entry["source"] == "**")
    header_map = {entry["key"]: entry["value"] for entry in global_headers}

    assert header_map["Content-Security-Policy"] == build_public_content_security_policy()
    assert header_map["X-Content-Type-Options"] == "nosniff"
    assert header_map["X-Frame-Options"] == "DENY"
    assert header_map["Referrer-Policy"] == "same-origin"


def test_public_js_escapes_dynamic_button_hrefs() -> None:
    for path in (STATIC_ROOT / "public.js", FIREBASE_ROOT / "static" / "public.js"):
        script = path.read_text(encoding="utf-8")
        assert "function safeHref" in script
        assert 'if (text.startsWith("//")) return "#";' in script
        assert '["http:", "https:"]' in script
        assert 'href="${escapeHtml(safeHref(href))}"' in script
        assert ">${escapeHtml(label)}</a>" in script
        assert 'href="${href}"' not in script


def test_private_app_normalize_url_rejects_unsafe_schemes() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function normalizeUrl" in script
    assert 'lower.startsWith("http://") || lower.startsWith("https://")' in script
    assert 'if (url.startsWith("//")) return "";' in script
    assert 'if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return "";' in script
    assert 'return `https://${url}`;' in script
    assert 'startsWith("mailto:")' not in script


def test_private_app_escapes_dynamic_data_attributes() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert not re.search(r'data-[a-z0-9-]+="\$\{(?:item|dia)\.id\}"', script)
    assert 'data-calendar-date="${key}"' not in script
    assert 'data-open-dia="${escapeHtml(dia.id)}"' in script
    assert 'data-calendar-date="${escapeHtml(key)}"' in script
    assert 'data-id="${escapeHtml(item.id)}"' in script
    assert 'data-download-id="${escapeHtml(item.id)}"' in script
    assert 'data-email-preview-id="${escapeHtml(item.id)}"' in script


def test_private_app_sanitizes_dynamic_css_class_tokens() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function cssClassToken" in script
    assert "function badgeClass" in script
    assert 'return cssClassToken(value, "Pendiente");' in script
    assert ".replace(/[^a-zA-Z0-9_-]+/g, \"-\")" in script
    assert ".replace(/^-+|-+$/g, \"\")" in script
    assert ".replaceAll(\" \", \"-\")" not in script


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
