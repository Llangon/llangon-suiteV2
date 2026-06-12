from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.auth_crypto import (
    hash_password,
    make_session_token,
    read_session_token,
    verify_password,
)


def test_auth_crypto_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.auth_crypto", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.auth_crypto")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_session_token_roundtrip_preserves_payload_shape() -> None:
    secret = b"test-secret"

    token = make_session_token(
        "admin",
        "admin",
        secret,
        csrf_token="csrf-token",
        issued_at=1_000,
    )
    payload = read_session_token(token, secret, max_age_seconds=600, now=lambda: 1_100)

    assert payload == {
        "u": "admin",
        "r": "admin",
        "iat": 1_000,
        "csrf": "csrf-token",
    }


def test_session_token_rejects_tampered_or_expired_values() -> None:
    secret = b"test-secret"
    token = make_session_token("admin", "admin", secret, csrf_token="csrf", issued_at=1_000)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    assert read_session_token(tampered, secret, max_age_seconds=600, now=lambda: 1_100) is None
    assert read_session_token(token, b"other-secret", max_age_seconds=600, now=lambda: 1_100) is None
    assert read_session_token(token, secret, max_age_seconds=600, now=lambda: 1_601) is None


def test_hash_password_uses_pbkdf2_and_verifies_plaintext_fallback() -> None:
    hashed = hash_password("secret", salt="0123456789abcdef0123456789abcdef")

    assert hashed.startswith("pbkdf2_sha256$0123456789abcdef0123456789abcdef$")
    assert verify_password(hashed, "secret") is True
    assert verify_password(hashed, "wrong") is False
    assert verify_password("legacy-secret", "legacy-secret") is True
    assert verify_password("legacy-secret", "wrong") is False
