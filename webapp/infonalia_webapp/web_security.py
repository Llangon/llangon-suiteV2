from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable


DEFAULT_LOGIN_WINDOW_SECONDS = 5 * 60
DEFAULT_LOGIN_MAX_ATTEMPTS = 5


def build_content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


def build_public_content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self'",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


def build_security_headers(is_private: bool = True) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    if is_private:
        headers["Cache-Control"] = "no-store"
        headers["Content-Security-Policy"] = build_content_security_policy()
    else:
        headers["Content-Security-Policy"] = build_public_content_security_policy()
    return headers


def _clean_cookie_part(value: object) -> str:
    text = str(value)
    if any(character in text for character in ("\r", "\n", ";")):
        raise ValueError("Cookie value contains unsafe characters.")
    return text


def build_session_cookie(
    name: str,
    value: str,
    max_age: int | None = None,
    secure: bool = False,
    same_site: str = "Lax",
) -> str:
    parts = [
        f"{_clean_cookie_part(name)}={_clean_cookie_part(value)}",
        "HttpOnly",
        f"SameSite={_clean_cookie_part(same_site)}",
        "Path=/",
    ]
    if max_age is not None:
        parts.append(f"Max-Age={int(max_age)}")
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def build_clear_cookie(name: str, secure: bool = False, same_site: str = "Lax") -> str:
    return build_session_cookie(name, "", max_age=0, secure=secure, same_site=same_site)


def get_client_ip(handler: object) -> str:
    client_address = getattr(handler, "client_address", None)
    if isinstance(client_address, tuple) and client_address:
        return str(client_address[0]).strip() or "unknown"

    headers = getattr(handler, "headers", None)
    getter = getattr(headers, "get", None)
    if callable(getter):
        forwarded_for = str(getter("X-Forwarded-For", "")).split(",", 1)[0].strip()
        if forwarded_for:
            return forwarded_for

    return "unknown"


def normalize_login_key(ip: str, username: str) -> str:
    normalized_ip = str(ip or "unknown").strip().lower() or "unknown"
    normalized_username = str(username or "").strip().casefold()
    return f"{normalized_ip}|{normalized_username}"


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = DEFAULT_LOGIN_MAX_ATTEMPTS,
        window_seconds: int = DEFAULT_LOGIN_WINDOW_SECONDS,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._now = now or time.monotonic
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> list[float]:
        cutoff = self._now() - self.window_seconds
        attempts = [timestamp for timestamp in self._attempts.get(key, []) if timestamp >= cutoff]
        if attempts:
            self._attempts[key] = attempts
        else:
            self._attempts.pop(key, None)
        return attempts

    def is_limited(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        attempts = self._prune(key)
        attempts.append(self._now())
        self._attempts[key] = attempts

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)
