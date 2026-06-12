from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


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
