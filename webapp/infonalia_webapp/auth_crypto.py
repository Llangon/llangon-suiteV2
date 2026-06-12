from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable

try:
    from .csrf import generate_csrf_token
    from .normalization import clean_text
except ImportError:
    from csrf import generate_csrf_token
    from normalization import clean_text


PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 120_000


def encode_token_payload(payload: dict, secret: bytes) -> str:
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")
    signature = hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded_payload}.{signature}"


def make_session_token(
    username: str,
    role: str,
    secret: bytes,
    *,
    csrf_token: str | None = None,
    issued_at: int | None = None,
    csrf_token_factory: Callable[[], str] = generate_csrf_token,
    now: Callable[[], float] | None = None,
) -> str:
    current_time = int((now or time.time)()) if issued_at is None else int(issued_at)
    payload = {
        "u": username,
        "r": role,
        "iat": current_time,
        "csrf": csrf_token or csrf_token_factory(),
    }
    return encode_token_payload(payload, secret)


def read_session_token(
    token: str | None,
    secret: bytes,
    max_age_seconds: int,
    *,
    now: Callable[[], float] | None = None,
) -> dict | None:
    if not token or "." not in token:
        return None

    encoded_payload, signature = token.rsplit(".", 1)
    expected = hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        padded = encoded_payload + ("=" * (-len(encoded_payload) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:
        return None

    issued_at = int(payload.get("iat", 0))
    current_time = int((now or time.time)())
    if issued_at + max_age_seconds < current_time:
        return None
    return payload


def hash_password(password: str, *, salt: str | None = None) -> str:
    password_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        clean_text(password).encode("utf-8"),
        password_salt.encode("ascii"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_SCHEME}${password_salt}${digest}"


def verify_password(stored: object, password: object) -> bool:
    stored_text = clean_text(stored)
    password_text = clean_text(password)
    if not stored_text:
        return False
    if stored_text.startswith(f"{PASSWORD_HASH_SCHEME}$"):
        try:
            _, salt, digest = stored_text.split("$", 2)
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password_text.encode("utf-8"),
            salt.encode("ascii"),
            PASSWORD_HASH_ITERATIONS,
        ).hex()
        return hmac.compare_digest(candidate, digest)
    return hmac.compare_digest(stored_text, password_text)
