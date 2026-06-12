from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.csrf import (
    generate_csrf_token,
    is_csrf_required,
    is_mutating_method,
    normalize_path_for_csrf,
    validate_csrf_token,
)


def test_csrf_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.csrf", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.csrf")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_generate_csrf_token_returns_non_empty_string() -> None:
    token = generate_csrf_token()

    assert isinstance(token, str)
    assert token


def test_generate_csrf_token_returns_distinct_tokens() -> None:
    assert generate_csrf_token() != generate_csrf_token()


def test_validate_csrf_token_accepts_matching_token() -> None:
    assert validate_csrf_token("abc123", "abc123") is True


def test_validate_csrf_token_rejects_missing_provided_token() -> None:
    assert validate_csrf_token("abc123", None) is False


def test_validate_csrf_token_rejects_different_token() -> None:
    assert validate_csrf_token("abc123", "different") is False


def test_validate_csrf_token_rejects_missing_expected_token() -> None:
    assert validate_csrf_token(None, "abc123") is False


def test_is_mutating_method_detects_mutating_methods_case_insensitively() -> None:
    assert is_mutating_method("POST") is True
    assert is_mutating_method("put") is True
    assert is_mutating_method("Patch") is True
    assert is_mutating_method("DELETE") is True


def test_is_mutating_method_ignores_safe_methods() -> None:
    assert is_mutating_method("GET") is False
    assert is_mutating_method("HEAD") is False
    assert is_mutating_method("OPTIONS") is False


def test_normalize_path_for_csrf_strips_querystring() -> None:
    assert normalize_path_for_csrf("/api/news?status=draft") == "/api/news"


def test_normalize_path_for_csrf_adds_leading_slash() -> None:
    assert normalize_path_for_csrf("api/news") == "/api/news"


def test_is_csrf_required_for_authenticated_mutating_post() -> None:
    assert is_csrf_required("POST", "/api/news", authenticated=True) is True


def test_is_csrf_required_false_for_get() -> None:
    assert is_csrf_required("GET", "/api/news", authenticated=True) is False


def test_is_csrf_required_false_for_public_excluded_route() -> None:
    assert is_csrf_required("POST", "/api/public/noticias", authenticated=True) is False


def test_is_csrf_required_false_for_login_in_this_phase() -> None:
    assert is_csrf_required("POST", "/login", authenticated=False) is False
    assert is_csrf_required("POST", "/login", authenticated=True) is False


def test_is_csrf_required_false_when_not_authenticated() -> None:
    assert is_csrf_required("POST", "/api/news", authenticated=False) is False
