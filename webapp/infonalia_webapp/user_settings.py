from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping

try:
    from .normalization import bool_text, clean_text
except ImportError:
    from normalization import bool_text, clean_text


SETTINGS_UPDATE_KEYS = {
    "maintenance_mode",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_from",
    "smtp_tls",
    "smtp_ssl",
}
BOOLEAN_SETTINGS = {"maintenance_mode", "smtp_tls", "smtp_ssl"}


def user_row_to_dict(row: sqlite3.Row | None, include_password: bool = False) -> dict | None:
    if not row:
        return None
    item = {
        "username": row["username"],
        "role": row["role"],
        "display_name": row["display_name"],
        "email": row["email"] or "",
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_password:
        item["password_hash"] = row["password_hash"]
    return item


def public_settings_payload(settings: Mapping[str, object]) -> dict[str, object]:
    return {
        "maintenance_mode": settings.get("maintenance_mode", "0"),
        "smtp_host": settings.get("smtp_host", ""),
        "smtp_port": settings.get("smtp_port", "587"),
        "smtp_user": settings.get("smtp_user", ""),
        "smtp_from": settings.get("smtp_from", ""),
        "smtp_tls": settings.get("smtp_tls", "1"),
        "smtp_ssl": settings.get("smtp_ssl", "0"),
        "smtp_password_set": bool(clean_text(settings.get("smtp_password"))),
    }


def config_payload(users: list[dict], settings: Mapping[str, object]) -> dict[str, object]:
    return {
        "users": users,
        "settings": public_settings_payload(settings),
    }


def settings_update_payload(data: Mapping[str, object]) -> dict[str, object]:
    updates = {key: data.get(key, "") for key in SETTINGS_UPDATE_KEYS if key in data}
    if "smtp_port" in updates:
        try:
            port = int(clean_text(updates["smtp_port"]))
            if port <= 0:
                raise ValueError
            updates["smtp_port"] = str(port)
        except ValueError:
            raise ValueError("Puerto SMTP no valido.")
    for key in BOOLEAN_SETTINGS:
        if key in updates:
            updates[key] = "1" if bool_text(updates[key]) else "0"
    if clean_text(data.get("smtp_password")):
        updates["smtp_password"] = clean_text(data.get("smtp_password"))
    elif data.get("clear_smtp_password"):
        updates["smtp_password"] = ""
    return updates


def seed_users_and_settings(
    conn: sqlite3.Connection,
    users: Mapping[str, Mapping[str, object]],
    default_settings: Mapping[str, object],
    *,
    timestamp: str,
    password_hasher: Callable[[str], str],
) -> None:
    for user in users.values():
        username = clean_text(user.get("username")).lower()
        if not username:
            continue
        exists = conn.execute("SELECT username FROM usuarios WHERE username = ?", (username,)).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO usuarios (
                username,
                password_hash,
                role,
                display_name,
                email,
                active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                password_hasher(clean_text(user.get("password"))),
                clean_text(user.get("role")) or "nuria",
                clean_text(user.get("display_name")) or username,
                clean_text(user.get("email")),
                timestamp,
                timestamp,
            ),
        )

    for key, value in default_settings.items():
        exists = conn.execute("SELECT key FROM app_settings WHERE key = ?", (key,)).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, clean_text(value), timestamp),
        )


def update_settings(conn: sqlite3.Connection, settings: dict[str, object], *, timestamp: str) -> None:
    for key, value in settings.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, clean_text(value), timestamp),
        )
