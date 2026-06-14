from __future__ import annotations

import importlib
import sqlite3
import sys

from webapp.infonalia_webapp.user_settings import (
    config_payload,
    public_settings_payload,
    seed_users_and_settings,
    settings_update_payload,
    update_settings,
    user_row_to_dict,
)


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
        "active": False,
        "created_at": "created",
        "updated_at": "updated",
    }
    assert private["password_hash"] == "hash"


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

    assert payload == {
        "maintenance_mode": "1",
        "smtp_host": "smtp.example.test",
        "smtp_port": "2525",
        "smtp_user": "user",
        "smtp_from": "",
        "smtp_tls": "1",
        "smtp_ssl": "0",
        "smtp_password_set": True,
    }


def test_config_payload_combines_users_and_public_settings_without_password() -> None:
    users = [{"username": "admin"}]

    payload = config_payload(users, {"smtp_password": ""})

    assert payload == {
        "users": users,
        "settings": {
            "maintenance_mode": "0",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_from": "",
            "smtp_tls": "1",
            "smtp_ssl": "0",
            "smtp_password_set": False,
        },
    }


def test_settings_update_payload_preserves_current_normalization() -> None:
    updates = settings_update_payload(
        {
            "maintenance_mode": "yes",
            "smtp_host": " smtp.example.test ",
            "smtp_port": " 2525 ",
            "smtp_user": "user",
            "smtp_tls": "0",
            "smtp_ssl": "on",
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
