from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlsplit


CSRF_EXEMPT_PATHS = frozenset({"/login"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf_token(expected: str | None, provided: str | None) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


def is_mutating_method(method: str) -> bool:
    return method.upper() in MUTATING_METHODS


def normalize_path_for_csrf(path: str) -> str:
    normalized = urlsplit(path).path or "/"
    if not normalized.startswith("/"):
        return f"/{normalized}"
    return normalized


def is_csrf_required(method: str, path: str, authenticated: bool = True) -> bool:
    if not authenticated:
        return False
    if not is_mutating_method(method):
        return False

    normalized_path = normalize_path_for_csrf(path)
    if normalized_path in CSRF_EXEMPT_PATHS:
        return False
    return True
