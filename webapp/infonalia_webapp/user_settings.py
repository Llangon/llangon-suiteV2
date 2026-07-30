from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Mapping

try:
    from .normalization import bool_text, clean_text
    from .operational_settings import SETTING_DEFINITIONS, effective_text
except ImportError:
    from normalization import bool_text, clean_text
    from operational_settings import SETTING_DEFINITIONS, effective_text


SETTINGS_UPDATE_KEYS = {
    "maintenance_mode",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_from",
    "smtp_enabled",
    "smtp_tls",
    "smtp_ssl",
    "email_dry_run",
    "agenda_email_to",
    "prepared_notice_email_to",
    "seguimiento_emails",
    "monitor_test_email",
    "monitor_agenda_pending_email_to",
    "email_actions_enabled",
    "email_actions_poll_minutes",
    "action_mailbox_to",
    "action_mailbox_cc",
    "action_notify_email",
    "action_allowed_senders",
    "actions_imap_host",
    "actions_imap_port",
    "actions_imap_user",
    "actions_imap_folder",
    "infonalia_import_enabled",
    "infonalia_import_notify_email",
    "infonalia_import_folder",
    "infonalia_import_poll_minutes",
    "infonalia_import_mark_read_on_success",
    "infonalia_import_lookback_hours",
    "ai_analysis_provider",
    "gemini_enabled",
    "gemini_model",
    "gemini_max_requests_per_minute",
    "gemini_max_requests_per_day",
    "gemini_max_documents_per_analysis",
    "gemini_max_file_mb",
    "gemini_timeout_seconds",
    "gemini_input_mode",
    "place_username",
}
BOOLEAN_SETTINGS = {
    "maintenance_mode",
    "smtp_enabled",
    "smtp_tls",
    "smtp_ssl",
    "email_dry_run",
    "email_actions_enabled",
    "infonalia_import_enabled",
    "infonalia_import_mark_read_on_success",
    "gemini_enabled",
}
SINGLE_EMAIL_SETTINGS = {
    "agenda_email_to": "Email agenda no valido.",
    "prepared_notice_email_to": "Email aviso ficha preparada no valido.",
    "action_mailbox_to": "Email destinatario de ordenes no valido.",
    "action_notify_email": "Email tecnico de avisos no valido.",
    "infonalia_import_notify_email": "Email aviso importador Infonalia no valido.",
    "monitor_test_email": "Email de pruebas del monitor no valido.",
}
EMAIL_LIST_SETTINGS = {
    "seguimiento_emails": "Lista de correos de seguimiento no valida.",
    "action_mailbox_cc": "Lista de correos en copia no valida.",
    "action_allowed_senders": "Lista de remitentes autorizados no valida.",
    "monitor_agenda_pending_email_to": "Lista de correos de agenda diaria no valida.",
}
INTEGER_RANGES = {
    "smtp_port": (1, 65535, "Puerto SMTP no valido."),
    "actions_imap_port": (1, 65535, "Puerto IMAP no valido."),
    "email_actions_poll_minutes": (1, 1440, "Frecuencia de acciones por correo no valida."),
    "infonalia_import_poll_minutes": (1, 1440, "Frecuencia de importacion Infonalia no valida."),
    "infonalia_import_lookback_hours": (1, 168, "Ventana de busqueda Infonalia no valida."),
    "gemini_max_requests_per_minute": (1, 1000, "Limite por minuto de Gemini no valido."),
    "gemini_max_requests_per_day": (1, 100000, "Limite diario de Gemini no valido."),
    "gemini_max_documents_per_analysis": (1, 20, "Numero maximo de documentos no valido."),
    "gemini_max_file_mb": (1, 100, "Tamano maximo por fichero no valido."),
    "gemini_timeout_seconds": (10, 900, "Timeout de Gemini no valido."),
}
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
USER_ROLES = {"admin", "nuria"}
USERNAME_PATTERN = re.compile(r"[a-zA-Z0-9_.-]{3,40}")
TELEGRAM_CHAT_ID_PATTERN = re.compile(r"-?\d+")


def _split_email_list(value: object) -> list[str]:
    result: list[str] = []
    for item in re.split(r"[;,\n\r]+", clean_text(value)):
        email = item.strip().lower()
        if email and email not in result:
            result.append(email)
    return result


def _validate_email(value: object, message: str, *, required: bool = False) -> str:
    email = clean_text(value).lower()
    if required and not email:
        raise ValueError(message)
    if email and not EMAIL_PATTERN.fullmatch(email):
        raise ValueError(message)
    return email


def _validate_email_list(value: object, message: str, *, required: bool = False) -> str:
    emails = _split_email_list(value)
    if required and not emails:
        raise ValueError(message)
    if any(not EMAIL_PATTERN.fullmatch(email) for email in emails):
        raise ValueError(message)
    return ", ".join(emails)


def _setting_value(
    key: str,
    updates: Mapping[str, object],
    current_settings: Mapping[str, object] | None,
    environ: Mapping[str, str] | None,
) -> str:
    if key in SETTING_DEFINITIONS:
        merged = {**(current_settings or {}), **updates}
        return effective_text(key, settings=merged, environ=environ)
    return clean_text(updates.get(key, (current_settings or {}).get(key, "")))


def normalize_telegram_chat_id(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if not TELEGRAM_CHAT_ID_PATTERN.fullmatch(text):
        raise ValueError("Telegram Chat ID no valido.")
    return text


def user_row_to_dict(row: sqlite3.Row | None, include_password: bool = False) -> dict | None:
    if not row:
        return None
    row_keys = set(row.keys())
    item = {
        "username": row["username"],
        "role": row["role"],
        "display_name": row["display_name"],
        "email": row["email"] or "",
        "telegram_chat_id": (row["telegram_chat_id"] if "telegram_chat_id" in row_keys else "") or "",
        "telegram_notifications_enabled": bool(row["telegram_notifications_enabled"]) if "telegram_notifications_enabled" in row_keys else False,
        "telegram_last_test_at": (row["telegram_last_test_at"] if "telegram_last_test_at" in row_keys else "") or "",
        "telegram_last_error": (row["telegram_last_error"] if "telegram_last_error" in row_keys else "") or "",
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_password:
        item["password_hash"] = row["password_hash"]
    return item


def new_user_payload(data: Mapping[str, object]) -> dict[str, object]:
    username = clean_text(data.get("username")).lower()
    password = clean_text(data.get("password"))
    role = clean_text(data.get("role")) or "nuria"
    display_name = clean_text(data.get("display_name")) or username
    email = clean_text(data.get("email"))
    telegram_chat_id = normalize_telegram_chat_id(data.get("telegram_chat_id"))
    telegram_enabled = 1 if data.get("telegram_notifications_enabled", False) else 0
    active = 1 if data.get("active", True) else 0

    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Usuario no valido. Usa 3-40 letras, numeros, punto, guion o guion bajo.")
    if not password:
        raise ValueError("La contraseña es obligatoria.")
    if role not in USER_ROLES:
        raise ValueError("Rol no valido.")

    return {
        "username": username,
        "password": password,
        "role": role,
        "display_name": display_name,
        "email": email,
        "telegram_chat_id": telegram_chat_id,
        "telegram_notifications_enabled": telegram_enabled,
        "active": active,
    }


def updated_user_payload(data: Mapping[str, object], row: Mapping[str, object], *, username: str) -> dict[str, object]:
    role = clean_text(data.get("role", row["role"])) or clean_text(row["role"])
    if role not in USER_ROLES:
        raise ValueError("Rol no valido.")
    row_keys = set(row.keys()) if hasattr(row, "keys") else set(row)
    existing_telegram_chat_id = clean_text(row["telegram_chat_id"]) if "telegram_chat_id" in row_keys else ""
    existing_telegram_enabled = bool(row["telegram_notifications_enabled"]) if "telegram_notifications_enabled" in row_keys else False

    return {
        "role": role,
        "display_name": clean_text(data.get("display_name", row["display_name"])) or username,
        "email": clean_text(data.get("email", row["email"])),
        "telegram_chat_id": normalize_telegram_chat_id(data.get("telegram_chat_id", existing_telegram_chat_id)),
        "telegram_notifications_enabled": 1
        if data.get("telegram_notifications_enabled", existing_telegram_enabled)
        else 0,
        "active": 1 if data.get("active", bool(row["active"])) else 0,
    }


def public_settings_payload(settings: Mapping[str, object]) -> dict[str, object]:
    payload = {
        "maintenance_mode": settings.get("maintenance_mode", "0"),
        "smtp_host": settings.get("smtp_host", ""),
        "smtp_port": settings.get("smtp_port", "587"),
        "smtp_user": settings.get("smtp_user", ""),
        "smtp_from": settings.get("smtp_from", ""),
        "smtp_enabled": settings.get("smtp_enabled", "0"),
        "smtp_tls": settings.get("smtp_tls", "1"),
        "smtp_ssl": settings.get("smtp_ssl", "0"),
        "email_dry_run": settings.get("email_dry_run", "1"),
        "agenda_email_to": settings.get("agenda_email_to", ""),
        "prepared_notice_email_to": settings.get("prepared_notice_email_to", "info3@llangon.com"),
        "seguimiento_emails": settings.get("seguimiento_emails", ""),
        "monitor_test_email": settings.get("monitor_test_email", ""),
        "monitor_agenda_pending_email_to": settings.get("monitor_agenda_pending_email_to", ""),
        "smtp_password_set": bool(clean_text(settings.get("smtp_password"))),
        "place_username": settings.get("place_username", ""),
        "place_password_set": bool(clean_text(settings.get("place_password"))),
    }
    for key in SETTING_DEFINITIONS:
        payload[key] = settings.get(key, "")
    return payload


def config_payload(users: list[dict], settings: Mapping[str, object]) -> dict[str, object]:
    return {
        "users": users,
        "settings": public_settings_payload(settings),
    }


def settings_update_payload(
    data: Mapping[str, object],
    *,
    current_settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    updates = {key: data.get(key, "") for key in SETTINGS_UPDATE_KEYS if key in data}
    for key, (minimum, maximum, message) in INTEGER_RANGES.items():
        if key not in updates:
            continue
        try:
            value = int(clean_text(updates[key]))
            if value < minimum or value > maximum:
                raise ValueError
            updates[key] = str(value)
        except ValueError:
            raise ValueError(message)
    for key in BOOLEAN_SETTINGS:
        if key in updates:
            updates[key] = "1" if bool_text(updates[key]) else "0"
    for key, message in SINGLE_EMAIL_SETTINGS.items():
        if key in updates:
            updates[key] = _validate_email(updates[key], message)
    for key, message in EMAIL_LIST_SETTINGS.items():
        if key in updates:
            updates[key] = _validate_email_list(updates[key], message)
    if "ai_analysis_provider" in updates:
        provider = clean_text(updates["ai_analysis_provider"]).lower()
        if provider not in {"gemini", "codex_local", "disabled"}:
            raise ValueError("Proveedor IA no valido.")
        updates["ai_analysis_provider"] = provider
    if "gemini_input_mode" in updates:
        mode = clean_text(updates["gemini_input_mode"]).lower()
        if mode not in {"text", "pdf_inline", "auto"}:
            raise ValueError("Modo de entrada de Gemini no valido.")
        updates["gemini_input_mode"] = mode
    if "gemini_model" in updates:
        updates["gemini_model"] = clean_text(updates["gemini_model"])
    if clean_text(data.get("smtp_password")):
        updates["smtp_password"] = clean_text(data.get("smtp_password"))
    elif data.get("clear_smtp_password"):
        updates["smtp_password"] = ""
    if "place_username" in updates:
        updates["place_username"] = clean_text(updates["place_username"])
    if clean_text(data.get("place_password")):
        updates["place_password"] = clean_text(data.get("place_password"))
    elif data.get("clear_place_password"):
        updates["place_password"] = ""
    env = environ or {}
    effective_updates = {**(current_settings or {}), **updates}
    if bool_text(_setting_value("email_actions_enabled", effective_updates, current_settings, env)):
        missing = []
        for key, label in (
            ("actions_imap_host", "servidor IMAP"),
            ("actions_imap_port", "puerto IMAP"),
            ("actions_imap_user", "usuario IMAP"),
            ("actions_imap_folder", "carpeta IMAP"),
        ):
            if not _setting_value(key, effective_updates, current_settings, env):
                missing.append(label)
        if not _validate_email_list(_setting_value("action_allowed_senders", effective_updates, current_settings, env), "Lista de remitentes autorizados no valida."):
            missing.append("remitentes autorizados")
        if not clean_text(env.get("LLANGON_ACTIONS_IMAP_PASSWORD")):
            missing.append("contraseña IMAP")
        if missing:
            raise ValueError("No se puede activar acciones por correo: falta " + ", ".join(missing) + ".")
    if bool_text(_setting_value("infonalia_import_enabled", effective_updates, current_settings, env)):
        missing = []
        for key, label in (
            ("actions_imap_host", "servidor IMAP"),
            ("actions_imap_port", "puerto IMAP"),
            ("actions_imap_user", "usuario IMAP"),
            ("infonalia_import_folder", "carpeta/etiqueta"),
        ):
            if not _setting_value(key, effective_updates, current_settings, env):
                missing.append(label)
        if not _validate_email(
            _setting_value("infonalia_import_notify_email", effective_updates, current_settings, env),
            "Email aviso importador Infonalia no valido.",
            required=True,
        ):
            missing.append("correo de aviso")
        if not clean_text(env.get("LLANGON_ACTIONS_IMAP_PASSWORD")):
            missing.append("contraseña IMAP")
        if missing:
            raise ValueError("No se puede activar importacion automatica: falta " + ", ".join(missing) + ".")
    if bool_text(_setting_value("gemini_enabled", effective_updates, current_settings, env)):
        if not _setting_value("gemini_model", effective_updates, current_settings, env):
            raise ValueError("No se puede activar Gemini sin modelo configurado.")
        if not clean_text(env.get("GEMINI_API_KEY")):
            raise ValueError("No se puede activar Gemini sin clave configurada en el entorno.")
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
                telegram_chat_id,
                telegram_notifications_enabled,
                telegram_last_test_at,
                telegram_last_error,
                active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, '', '', 1, ?, ?)
            """,
            (
                username,
                password_hasher(clean_text(user.get("password"))),
                clean_text(user.get("role")) or "nuria",
                clean_text(user.get("display_name")) or username,
                clean_text(user.get("email")),
                normalize_telegram_chat_id(user.get("telegram_chat_id")),
                "1" if bool_text(user.get("telegram_notifications_enabled")) else "0",
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
