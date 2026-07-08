from __future__ import annotations

import io
import json
import sqlite3
from http import HTTPStatus
from urllib.error import HTTPError, URLError

from webapp.infonalia_webapp.services.telegram_notifications import (
    TelegramResult,
    send_telegram_group_message,
    send_telegram_user_message,
    telegram_public_status,
)
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def telegram_env(**overrides: str) -> dict[str, str]:
    env = {
        "LLANGON_TELEGRAM_ENABLED": "1",
        "LLANGON_TELEGRAM_BOT_TOKEN": "secret-test-token",
        "LLANGON_TELEGRAM_GROUP_CHAT_ID": "-5269010979",
    }
    env.update(overrides)
    return env


def test_telegram_public_status_reports_safe_flags_only() -> None:
    payload = telegram_public_status(telegram_env())

    assert payload == {
        "enabled": True,
        "token_configured": True,
        "group_configured": True,
        "status_label": "Telegram listo",
    }
    assert "secret-test-token" not in json.dumps(payload)


def test_send_telegram_group_message_returns_disabled_when_global_flag_is_off() -> None:
    result = send_telegram_group_message("hola", env={"LLANGON_TELEGRAM_ENABLED": "0"})

    assert result.status == "disabled"
    assert result.message == "Telegram deshabilitado"


def test_send_telegram_group_message_requires_token() -> None:
    result = send_telegram_group_message("hola", env=telegram_env(LLANGON_TELEGRAM_BOT_TOKEN=""))

    assert result.ok is False
    assert result.error_code == "TELEGRAM_MISSING_TOKEN"
    assert "token" in result.error_message.lower()


def test_send_telegram_group_message_requires_group_chat_id() -> None:
    result = send_telegram_group_message("hola", env=telegram_env(LLANGON_TELEGRAM_GROUP_CHAT_ID=""))

    assert result.ok is False
    assert result.error_code == "TELEGRAM_MISSING_GROUP_CHAT_ID"


def test_send_telegram_group_message_handles_success() -> None:
    calls: list[tuple[str, dict[str, object], float]] = []

    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        calls.append((url, payload, timeout))
        return {"ok": True, "result": {"message_id": 77}}

    result = send_telegram_group_message("hola grupo", env=telegram_env(), sender=fake_sender)

    assert result.ok is True
    assert result.telegram_message_id == 77
    assert calls[0][1]["chat_id"] == "-5269010979"
    assert "secret-test-token" not in json.dumps(result.to_dict())


def test_send_telegram_group_message_handles_api_false_without_exposing_token() -> None:
    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        return {"ok": False, "description": "Bad Request: chat not found"}

    result = send_telegram_group_message("hola", env=telegram_env(), sender=fake_sender)

    assert result.ok is False
    assert result.error_code == "TELEGRAM_API_ERROR"
    assert "no encuentra el grupo" in result.error_message.lower()
    assert "secret-test-token" not in json.dumps(result.to_dict())


def test_send_telegram_group_message_reads_http_400_body_without_exposing_secrets() -> None:
    body = b'{"ok":false,"description":"Bad Request: chat not found"}'

    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        raise HTTPError(url, 400, "Bad Request", {}, io.BytesIO(body))

    result = send_telegram_group_message("hola", env=telegram_env(), sender=fake_sender)
    serialized = json.dumps(result.to_dict())

    assert result.ok is False
    assert result.error_code == "TELEGRAM_HTTP_ERROR"
    assert result.provider_status == 400
    assert "no encuentra el grupo" in result.error_message.lower()
    assert "supergrupos" in result.error_message.lower()
    assert "secret-test-token" not in serialized
    assert "-5269010979" not in serialized


def test_send_telegram_group_message_explains_supergroup_migration() -> None:
    body = b'{"ok":false,"description":"Bad Request: group chat was upgraded to a supergroup chat"}'

    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        raise HTTPError(url, 400, "Bad Request", {}, io.BytesIO(body))

    result = send_telegram_group_message("hola", env=telegram_env(), sender=fake_sender)

    assert result.ok is False
    assert result.error_code == "TELEGRAM_HTTP_ERROR"
    assert "migrado a supergrupo" in result.error_message.lower()


def test_send_telegram_group_message_handles_network_error() -> None:
    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        raise URLError("network down")

    result = send_telegram_group_message("hola", env=telegram_env(), sender=fake_sender)

    assert result.ok is False
    assert result.error_code == "TELEGRAM_NETWORK_ERROR"


def test_send_telegram_group_message_handles_timeout() -> None:
    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        raise TimeoutError("timeout")

    result = send_telegram_group_message("hola", env=telegram_env(), sender=fake_sender)

    assert result.ok is False
    assert result.error_code == "TELEGRAM_TIMEOUT"
    assert "tiempo" in result.error_message.lower()


def test_send_telegram_user_message_requires_chat_id() -> None:
    result = send_telegram_user_message(
        {"username": "manolo", "telegram_notifications_enabled": 1, "telegram_chat_id": ""},
        "hola",
        env=telegram_env(),
    )

    assert result.ok is False
    assert result.message == "Telegram no configurado para este usuario"


def test_send_telegram_user_message_requires_user_telegram_enabled() -> None:
    result = send_telegram_user_message(
        {"username": "manolo", "telegram_notifications_enabled": 0, "telegram_chat_id": "1648124154"},
        "hola",
        env=telegram_env(),
    )

    assert result.ok is False
    assert result.error_code == "TELEGRAM_USER_DISABLED"


def test_send_telegram_user_message_handles_success() -> None:
    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        return {"ok": True, "result": {"message_id": 99}}

    result = send_telegram_user_message(
        {"username": "manolo", "telegram_notifications_enabled": 1, "telegram_chat_id": "1648124154"},
        "hola",
        env=telegram_env(),
        sender=fake_sender,
    )

    assert result.ok is True
    assert result.telegram_message_id == 99


def test_send_telegram_user_message_accepts_sqlite_row() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE usuarios (
            username TEXT,
            telegram_notifications_enabled INTEGER,
            telegram_chat_id TEXT
        )
        """
    )
    conn.execute("INSERT INTO usuarios VALUES ('manolo', 1, '1648124154')")
    user = conn.execute("SELECT * FROM usuarios WHERE username = 'manolo'").fetchone()
    calls: list[dict[str, object]] = []

    def fake_sender(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        calls.append(payload)
        return {"ok": True, "result": {"message_id": 109}}

    result = send_telegram_user_message(user, "hola", env=telegram_env(), sender=fake_sender)

    assert result.ok is True
    assert result.telegram_message_id == 109
    assert calls[0]["chat_id"] == "1648124154"


def test_telegram_group_test_endpoint_requires_admin() -> None:
    app = load_app_module()
    handler = make_handler(app, "POST", "/api/admin/telegram/test-group", {}, role="nuria")
    handler.require_admin = lambda: False

    dispatch(handler, "POST")

    assert handler.responses == []


def test_telegram_user_test_endpoint_requires_admin() -> None:
    app = load_app_module()
    handler = make_handler(app, "POST", "/api/admin/users/manolo/telegram/test", {}, role="nuria")
    handler.require_admin = lambda: False

    dispatch(handler, "POST")

    assert handler.responses == []


def test_telegram_user_fields_can_be_saved_without_breaking_existing_users(monkeypatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        create_handler = make_handler(
            app,
            "POST",
            "/api/config/users",
            {
                "username": "manolo",
                "password": "secret123",
                "display_name": "Manolo",
                "email": "manolo@example.test",
                "role": "admin",
                "telegram_chat_id": "1648124154",
                "telegram_notifications_enabled": True,
                "active": True,
            },
        )
        dispatch(create_handler, "POST")
        assert create_handler.responses[-1][0] == HTTPStatus.CREATED

        with app.db_session() as conn:
            row = conn.execute(
                "SELECT telegram_chat_id, telegram_notifications_enabled FROM usuarios WHERE username = 'manolo'"
            ).fetchone()
        assert row["telegram_chat_id"] == "1648124154"
        assert row["telegram_notifications_enabled"] == 1


def test_telegram_group_test_endpoint_returns_safe_payload(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_TELEGRAM_ENABLED", "1")
    monkeypatch.setenv("LLANGON_TELEGRAM_BOT_TOKEN", "secret-test-token")
    monkeypatch.setenv("LLANGON_TELEGRAM_GROUP_CHAT_ID", "-5269010979")
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda *args, **kwargs: TelegramResult(
            ok=True,
            status="ok",
            message="Enviado correctamente",
            telegram_message_id=10,
        ),
    )
    handler = make_handler(app, "POST", "/api/admin/telegram/test-group", {})

    dispatch(handler, "POST")

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["ok"] is True
    assert "secret-test-token" not in json.dumps(payload)


def test_config_endpoint_exposes_only_safe_telegram_status(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_TELEGRAM_ENABLED", "1")
    monkeypatch.setenv("LLANGON_TELEGRAM_BOT_TOKEN", "secret-test-token")
    monkeypatch.setenv("LLANGON_TELEGRAM_GROUP_CHAT_ID", "-5269010979")
    handler = make_handler(app, "GET", "/api/config", {})

    dispatch(handler, "GET")

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["telegram"] == {
        "enabled": True,
        "token_configured": True,
        "group_configured": True,
        "status_label": "Telegram listo",
    }
    assert "secret-test-token" not in json.dumps(payload)


def test_config_endpoint_exposes_safe_diagnostics_without_mailbox_secrets(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "1")
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_USER", "info3llangon@example.test")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_PASSWORD", "secret-imap-password")
    monkeypatch.setenv("LLANGON_ACTION_ALLOWED_SENDERS", "nuria@example.test")
    handler = make_handler(app, "GET", "/api/config", {})

    dispatch(handler, "GET")

    status, payload = handler.responses[-1]
    serialized = json.dumps(payload)
    assert status == HTTPStatus.OK
    assert payload["diagnostics"]["mailboxes"]["email_actions"]["password_configured"] is True
    assert payload["diagnostics"]["mailboxes"]["infonalia_import"]["configured"] is True
    assert "secret-imap-password" not in serialized
    assert "LLANGON_ACTIONS_IMAP_PASSWORD" not in serialized


def test_config_endpoint_never_serializes_known_secret_values(monkeypatch) -> None:
    app = load_app_module()
    secret_env = {
        "GEMINI_API_KEY": "secret-gemini-key",
        "LLANGON_TELEGRAM_BOT_TOKEN": "secret-telegram-token",
        "INFONALIA_DROPBOX_APP_SECRET": "secret-dropbox-app",
        "INFONALIA_DROPBOX_REFRESH_TOKEN": "secret-dropbox-refresh",
        "LLANGON_ACTIONS_IMAP_PASSWORD": "secret-imap-password",
        "INFONALIA_SMTP_PASSWORD": "secret-smtp-password",
    }
    for key, value in secret_env.items():
        monkeypatch.setenv(key, value)
    handler = make_handler(app, "GET", "/api/config", {})

    dispatch(handler, "GET")

    status, payload = handler.responses[-1]
    serialized = json.dumps(payload)
    assert status == HTTPStatus.OK
    for key, value in secret_env.items():
        assert key not in serialized
        assert value not in serialized


def test_telegram_user_test_endpoint_updates_last_test_fields(monkeypatch) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO usuarios (
                    username, password_hash, role, display_name, email,
                    telegram_chat_id, telegram_notifications_enabled,
                    active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "manolo",
                    "hash",
                    "admin",
                    "Manolo",
                    "manolo@example.test",
                    "1648124154",
                    1,
                    1,
                    "2026-07-07T10:00:00",
                    "2026-07-07T10:00:00",
                ),
            )
        monkeypatch.setenv("LLANGON_TELEGRAM_ENABLED", "1")
        monkeypatch.setenv("LLANGON_TELEGRAM_BOT_TOKEN", "secret-test-token")
        monkeypatch.setattr(
            app,
            "send_telegram_user_message",
            lambda *args, **kwargs: TelegramResult(
                ok=True,
                status="ok",
                message="Enviado correctamente",
                telegram_message_id=15,
            ),
        )

        handler = make_handler(app, "POST", "/api/admin/users/manolo/telegram/test", {})
        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["user"]["username"] == "manolo"
        with app.db_session() as conn:
            row = conn.execute(
                "SELECT telegram_last_test_at, telegram_last_error FROM usuarios WHERE username = 'manolo'"
            ).fetchone()
        assert row["telegram_last_test_at"]
        assert row["telegram_last_error"] == ""
