from __future__ import annotations

import importlib
import sqlite3
import sys

from webapp.infonalia_webapp.user_settings import (
    config_payload,
    public_settings_payload,
    new_user_payload,
    seed_users_and_settings,
    settings_update_payload,
    update_settings,
    updated_user_payload,
    user_row_to_dict,
)
from webapp.infonalia_webapp.operational_settings import effective_setting, effective_text
from webapp.infonalia_webapp.email_actions_processor import mailbox_config_from_env
from webapp.infonalia_webapp.infonalia_mail_importer import config_from_env as infonalia_import_config_from_env


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            email TEXT,
            telegram_chat_id TEXT,
            telegram_notifications_enabled INTEGER NOT NULL DEFAULT 0,
            telegram_last_test_at TEXT,
            telegram_last_error TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    return conn


def test_user_settings_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.user_settings", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.user_settings")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"requests", "http.server", "socketserver", "subprocess"} & added


def test_seed_users_and_settings_preserves_defaults_and_existing_rows() -> None:
    conn = make_conn()
    conn.execute(
        "INSERT INTO usuarios (username, password_hash, role, display_name, email, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("admin", "existing-hash", "admin", "Existing", "", 1, "old", "old"),
    )
    conn.execute("INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)", ("smtp_host", "existing", "old"))

    seed_users_and_settings(
        conn,
        {
            "admin": {"username": "admin", "password": "new", "role": "admin", "display_name": "New"},
            "reviewer": {
                "username": "reviewer",
                "password": "reviewer-pass",
                "role": "nuria",
                "display_name": "Reviewer",
                "email": "reviewer@example.test",
            },
        },
        {"smtp_host": "default-host", "smtp_port": "587"},
        timestamp="2026-06-12T10:00:00",
        password_hasher=lambda value: f"hashed:{value}",
    )

    rows = {
        row["username"]: row
        for row in conn.execute("SELECT * FROM usuarios ORDER BY username").fetchall()
    }
    settings = {
        row["key"]: row["value"]
        for row in conn.execute("SELECT key, value FROM app_settings ORDER BY key").fetchall()
    }

    assert rows["admin"]["password_hash"] == "existing-hash"
    assert rows["reviewer"]["password_hash"] == "hashed:reviewer-pass"
    assert rows["reviewer"]["email"] == "reviewer@example.test"
    assert settings == {"smtp_host": "existing", "smtp_port": "587"}


def test_user_row_to_dict_hides_password_by_default() -> None:
    conn = make_conn()
    conn.execute(
        "INSERT INTO usuarios (username, password_hash, role, display_name, email, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("admin", "hash", "admin", "Admin", None, 0, "created", "updated"),
    )
    row = conn.execute("SELECT * FROM usuarios WHERE username = ?", ("admin",)).fetchone()

    public = user_row_to_dict(row)
    private = user_row_to_dict(row, include_password=True)

    assert public == {
        "username": "admin",
        "role": "admin",
        "display_name": "Admin",
        "email": "",
        "telegram_chat_id": "",
        "telegram_notifications_enabled": False,
        "telegram_last_test_at": "",
        "telegram_last_error": "",
        "active": False,
        "created_at": "created",
        "updated_at": "updated",
    }
    assert private["password_hash"] == "hash"


def test_new_user_payload_preserves_current_normalization() -> None:
    payload = new_user_payload(
        {
            "username": " Nuevo.Admin ",
            "password": " secret ",
            "role": "",
            "display_name": "",
            "email": " admin@example.test ",
            "telegram_chat_id": " 1648124154 ",
            "telegram_notifications_enabled": True,
            "active": False,
        }
    )

    assert payload == {
        "username": "nuevo.admin",
        "password": "secret",
        "role": "nuria",
        "display_name": "nuevo.admin",
        "email": "admin@example.test",
        "telegram_chat_id": "1648124154",
        "telegram_notifications_enabled": 1,
        "active": 0,
    }


def test_new_user_payload_preserves_current_validation_errors() -> None:
    cases = [
        ({}, "Usuario no valido. Usa 3-40 letras, numeros, punto, guion o guion bajo."),
        ({"username": "ab", "password": "x"}, "Usuario no valido. Usa 3-40 letras, numeros, punto, guion o guion bajo."),
        ({"username": "valid-user"}, "La contraseña es obligatoria."),
        ({"username": "valid-user", "password": "x", "role": "editor"}, "Rol no valido."),
    ]

    for data, message in cases:
        try:
            new_user_payload(data)
        except ValueError as exc:
            assert str(exc) == message
        else:
            raise AssertionError(f"accepted invalid user payload: {data!r}")


def test_updated_user_payload_preserves_current_defaults() -> None:
    row = {
        "role": "admin",
        "display_name": "Admin Actual",
        "email": "old@example.test",
        "telegram_chat_id": "",
        "telegram_notifications_enabled": 0,
        "active": 1,
    }

    assert updated_user_payload({}, row, username="admin") == {
        "role": "admin",
        "display_name": "Admin Actual",
        "email": "old@example.test",
        "telegram_chat_id": "",
        "telegram_notifications_enabled": 0,
        "active": 1,
    }
    assert updated_user_payload(
        {
            "role": "nuria",
            "display_name": " ",
            "email": " new@example.test ",
            "telegram_chat_id": "-5269010979",
            "telegram_notifications_enabled": True,
            "active": False,
        },
        row,
        username="admin",
    ) == {
        "role": "nuria",
        "display_name": "admin",
        "email": "new@example.test",
        "telegram_chat_id": "-5269010979",
        "telegram_notifications_enabled": 1,
        "active": 0,
    }


def test_updated_user_payload_rejects_invalid_role() -> None:
    try:
        updated_user_payload({"role": "editor"}, {"role": "admin", "display_name": "Admin", "email": "", "active": 1}, username="admin")
    except ValueError as exc:
        assert str(exc) == "Rol no valido."
    else:
        raise AssertionError("accepted invalid role")


def test_public_settings_payload_preserves_current_public_shape() -> None:
    payload = public_settings_payload(
        {
            "maintenance_mode": "1",
            "smtp_host": "smtp.example.test",
            "smtp_port": "2525",
            "smtp_user": "user",
            "smtp_password": "secret",
        }
    )

    assert payload | {
        "maintenance_mode": "1",
        "smtp_host": "smtp.example.test",
        "smtp_port": "2525",
        "smtp_user": "user",
        "smtp_from": "",
        "smtp_enabled": "0",
        "smtp_tls": "1",
        "smtp_ssl": "0",
        "email_dry_run": "1",
        "agenda_email_to": "",
        "prepared_notice_email_to": "info3@llangon.com",
        "seguimiento_emails": "",
        "smtp_password_set": True,
    } == payload
    assert "smtp_password" not in payload
    assert "email_actions_enabled" in payload
    assert "gemini_model" in payload


def test_config_payload_combines_users_and_public_settings_without_password() -> None:
    users = [{"username": "admin"}]

    payload = config_payload(users, {"smtp_password": ""})

    assert payload["users"] == users
    assert payload["settings"]["maintenance_mode"] == "0"
    assert payload["settings"]["smtp_port"] == "587"
    assert payload["settings"]["prepared_notice_email_to"] == "info3@llangon.com"
    assert payload["settings"]["smtp_password_set"] is False
    assert "smtp_password" not in payload["settings"]
    assert "email_actions_poll_minutes" in payload["settings"]


def test_new_user_payload_rejects_invalid_telegram_chat_id() -> None:
    try:
        new_user_payload({"username": "valid-user", "password": "x", "telegram_chat_id": "abc"})
    except ValueError as exc:
        assert str(exc) == "Telegram Chat ID no valido."
    else:
        raise AssertionError("accepted invalid telegram chat id")


def test_settings_update_payload_preserves_current_normalization() -> None:
    updates = settings_update_payload(
        {
            "maintenance_mode": "yes",
            "smtp_host": " smtp.example.test ",
            "smtp_port": " 2525 ",
            "smtp_user": "user",
            "smtp_tls": "0",
            "smtp_ssl": "on",
            "prepared_notice_email_to": " info3@llangon.com ",
            "smtp_password": " secret ",
            "ignored": "value",
        }
    )

    assert updates == {
        "maintenance_mode": "1",
        "smtp_host": " smtp.example.test ",
        "smtp_port": "2525",
        "smtp_user": "user",
        "smtp_tls": "0",
        "smtp_ssl": "1",
        "prepared_notice_email_to": "info3@llangon.com",
        "smtp_password": "secret",
    }


def test_settings_update_payload_preserves_password_clear_rule() -> None:
    assert settings_update_payload({"clear_smtp_password": True}) == {"smtp_password": ""}
    assert settings_update_payload({"smtp_password": " nuevo ", "clear_smtp_password": True}) == {
        "smtp_password": "nuevo"
    }


def test_settings_update_payload_rejects_invalid_smtp_port() -> None:
    for value in ["", "0", "-1", "abc"]:
        try:
            settings_update_payload({"smtp_port": value})
        except ValueError as exc:
            assert str(exc) == "Puerto SMTP no valido."
        else:
            raise AssertionError(f"accepted invalid port: {value!r}")


def test_settings_update_payload_rejects_invalid_prepared_notice_email() -> None:
    try:
        settings_update_payload({"prepared_notice_email_to": "sin-arroba"})
    except ValueError as exc:
        assert str(exc) == "Email aviso ficha preparada no valido."
    else:
        raise AssertionError("accepted invalid prepared notice email")


def test_operational_setting_prefers_suite_then_env_then_default() -> None:
    assert effective_setting(
        "email_actions_poll_minutes",
        settings={"email_actions_poll_minutes": "15"},
        environ={"LLANGON_EMAIL_ACTIONS_POLL_MINUTES": "30"},
    ) == {"value": "15", "source": "settings", "label": "Configurado en la Suite"}
    assert effective_setting(
        "email_actions_poll_minutes",
        settings={},
        environ={"LLANGON_EMAIL_ACTIONS_POLL_MINUTES": "30"},
    )["value"] == "30"
    assert effective_text("email_actions_poll_minutes", settings={}, environ={}) == "10"


def test_settings_update_payload_rejects_enabled_email_actions_without_password() -> None:
    try:
        settings_update_payload(
            {
                "email_actions_enabled": "1",
                "actions_imap_host": "imap.example.test",
                "actions_imap_port": "993",
                "actions_imap_user": "robot@example.test",
                "actions_imap_folder": "INBOX",
                "action_allowed_senders": "nuria@example.test",
            },
            environ={},
        )
    except ValueError as exc:
        assert "contraseña IMAP" in str(exc)
    else:
        raise AssertionError("accepted enabled email actions without IMAP password")


def test_settings_update_payload_accepts_complete_operational_settings() -> None:
    updates = settings_update_payload(
        {
            "email_actions_enabled": "1",
            "email_actions_poll_minutes": "20",
            "actions_imap_host": "imap.example.test",
            "actions_imap_port": "993",
            "actions_imap_user": "robot@example.test",
            "actions_imap_folder": "INBOX",
            "action_allowed_senders": "nuria@example.test, manolo@example.test",
            "gemini_enabled": "1",
            "gemini_model": "gemini-test",
            "gemini_timeout_seconds": "120",
        },
        environ={
            "LLANGON_ACTIONS_IMAP_PASSWORD": "secret",
            "GEMINI_API_KEY": "secret",
        },
    )

    assert updates["email_actions_enabled"] == "1"
    assert updates["action_allowed_senders"] == "nuria@example.test\nmanolo@example.test"
    assert updates["gemini_enabled"] == "1"
    assert "LLANGON_ACTIONS_IMAP_PASSWORD" not in updates
    assert "GEMINI_API_KEY" not in updates


def test_settings_update_payload_rejects_gemini_enabled_without_key() -> None:
    try:
        settings_update_payload({"gemini_enabled": "1", "gemini_model": "gemini-test"}, environ={})
    except ValueError as exc:
        assert "clave configurada" in str(exc)
    else:
        raise AssertionError("accepted Gemini enabled without API key")


def test_email_action_mailbox_config_reads_suite_settings_before_env() -> None:
    config = mailbox_config_from_env(
        {
            "LLANGON_ACTIONS_IMAP_HOST": "imap-env.example.test",
            "LLANGON_ACTIONS_IMAP_PORT": "993",
            "LLANGON_ACTIONS_IMAP_USER": "env@example.test",
            "LLANGON_ACTIONS_IMAP_PASSWORD": "secret",
            "LLANGON_ACTION_ALLOWED_SENDERS": "env-sender@example.test",
        },
        settings={
            "actions_imap_host": "imap-suite.example.test",
            "actions_imap_user": "suite@example.test",
            "actions_imap_folder": "LLANGON",
            "action_allowed_senders": "suite-sender@example.test",
            "action_notify_email": "avisos@example.test",
        },
    )

    assert config.host == "imap-suite.example.test"
    assert config.user == "suite@example.test"
    assert config.folder == "LLANGON"
    assert config.allowed_senders == ["suite-sender@example.test"]
    assert config.password == "secret"


def test_infonalia_import_config_reads_suite_settings_before_env() -> None:
    config = infonalia_import_config_from_env(
        {
            "LLANGON_ACTIONS_IMAP_USER": "env@example.test",
            "LLANGON_ACTIONS_IMAP_PASSWORD": "secret",
            "LLANGON_INFONALIA_IMPORT_FOLDER": "ENV_FOLDER",
        },
        settings={
            "infonalia_import_enabled": "1",
            "infonalia_import_folder": "SUITE_FOLDER",
            "infonalia_import_notify_email": "avisos@example.test",
            "infonalia_import_poll_minutes": "15",
            "infonalia_import_lookback_hours": "24",
        },
    )

    assert config.enabled is True
    assert config.folder == "SUITE_FOLDER"
    assert config.notify_email == "avisos@example.test"
    assert config.lookback_hours == 24
    assert config.password == "secret"


def test_update_settings_upserts_values_with_timestamp() -> None:
    conn = make_conn()
    conn.execute("INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)", ("smtp_host", "old", "old"))

    update_settings(conn, {"smtp_host": "new", "smtp_port": 587}, timestamp="2026-06-12T10:00:00")

    rows = {
        row["key"]: (row["value"], row["updated_at"])
        for row in conn.execute("SELECT key, value, updated_at FROM app_settings").fetchall()
    }
    assert rows == {
        "smtp_host": ("new", "2026-06-12T10:00:00"),
        "smtp_port": ("587", "2026-06-12T10:00:00"),
    }
