from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:
    from .normalization import bool_text, clean_text
except ImportError:
    from normalization import bool_text, clean_text


APP_ROOT = Path(__file__).resolve().parent
DB_PATH = APP_ROOT / "data" / "infonalia.db"


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    env_var: str
    default: str = ""


SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "email_actions_enabled": SettingDefinition("email_actions_enabled", "LLANGON_EMAIL_ACTIONS_ENABLED", "0"),
    "email_actions_poll_minutes": SettingDefinition(
        "email_actions_poll_minutes", "LLANGON_EMAIL_ACTIONS_POLL_MINUTES", "10"
    ),
    "action_mailbox_to": SettingDefinition("action_mailbox_to", "LLANGON_ACTION_MAILBOX_TO", ""),
    "action_mailbox_cc": SettingDefinition("action_mailbox_cc", "LLANGON_ACTION_MAILBOX_CC", ""),
    "action_notify_email": SettingDefinition("action_notify_email", "LLANGON_ACTION_NOTIFY_EMAIL", ""),
    "action_allowed_senders": SettingDefinition(
        "action_allowed_senders", "LLANGON_ACTION_ALLOWED_SENDERS", ""
    ),
    "actions_imap_host": SettingDefinition("actions_imap_host", "LLANGON_ACTIONS_IMAP_HOST", "imap.gmail.com"),
    "actions_imap_port": SettingDefinition("actions_imap_port", "LLANGON_ACTIONS_IMAP_PORT", "993"),
    "actions_imap_user": SettingDefinition("actions_imap_user", "LLANGON_ACTIONS_IMAP_USER", ""),
    "actions_imap_folder": SettingDefinition("actions_imap_folder", "LLANGON_ACTIONS_IMAP_FOLDER", "INBOX"),
    "infonalia_import_enabled": SettingDefinition(
        "infonalia_import_enabled", "LLANGON_INFONALIA_IMPORT_ENABLED", "0"
    ),
    "infonalia_import_notify_email": SettingDefinition(
        "infonalia_import_notify_email", "LLANGON_INFONALIA_IMPORT_NOTIFY_EMAIL", "info3@llangon.com"
    ),
    "infonalia_import_folder": SettingDefinition(
        "infonalia_import_folder", "LLANGON_INFONALIA_IMPORT_FOLDER", "LLANGON_INFONALIA"
    ),
    "infonalia_import_poll_minutes": SettingDefinition(
        "infonalia_import_poll_minutes", "LLANGON_INFONALIA_IMPORT_POLL_MINUTES", "30"
    ),
    "infonalia_import_mark_read_on_success": SettingDefinition(
        "infonalia_import_mark_read_on_success", "LLANGON_INFONALIA_IMPORT_MARK_READ_ON_SUCCESS", "1"
    ),
    "infonalia_import_lookback_hours": SettingDefinition(
        "infonalia_import_lookback_hours", "LLANGON_INFONALIA_IMPORT_LOOKBACK_HOURS", "48"
    ),
    "file_inventory_enabled": SettingDefinition("file_inventory_enabled", "LLANGON_FILE_INVENTORY_ENABLED", "1"),
    "file_inventory_poll_minutes": SettingDefinition(
        "file_inventory_poll_minutes", "LLANGON_FILE_INVENTORY_POLL_MINUTES", "240"
    ),
    "full_backup_enabled": SettingDefinition("full_backup_enabled", "LLANGON_FULL_BACKUP_ENABLED", "1"),
    "full_backup_time": SettingDefinition("full_backup_time", "LLANGON_FULL_BACKUP_TIME", "16:00"),
    "night_suspend_enabled": SettingDefinition("night_suspend_enabled", "LLANGON_NIGHT_SUSPEND_ENABLED", "1"),
    "night_suspend_time": SettingDefinition("night_suspend_time", "LLANGON_NIGHT_SUSPEND_TIME", "21:00"),
    "night_suspend_skip_if_user_active": SettingDefinition(
        "night_suspend_skip_if_user_active", "LLANGON_NIGHT_SUSPEND_SKIP_IF_USER_ACTIVE", "1"
    ),
    "ai_analysis_provider": SettingDefinition("ai_analysis_provider", "AI_ANALYSIS_PROVIDER", "gemini"),
    "gemini_enabled": SettingDefinition("gemini_enabled", "GEMINI_ENABLED", "0"),
    "gemini_model": SettingDefinition("gemini_model", "GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini_max_requests_per_minute": SettingDefinition(
        "gemini_max_requests_per_minute", "GEMINI_MAX_REQUESTS_PER_MINUTE", "2"
    ),
    "gemini_max_requests_per_day": SettingDefinition(
        "gemini_max_requests_per_day", "GEMINI_MAX_REQUESTS_PER_DAY", "20"
    ),
    "gemini_max_documents_per_analysis": SettingDefinition(
        "gemini_max_documents_per_analysis", "GEMINI_MAX_DOCUMENTS_PER_ANALYSIS", "4"
    ),
    "gemini_max_file_mb": SettingDefinition("gemini_max_file_mb", "GEMINI_MAX_FILE_MB", "45"),
    "gemini_timeout_seconds": SettingDefinition("gemini_timeout_seconds", "GEMINI_TIMEOUT_SECONDS", "120"),
    "gemini_input_mode": SettingDefinition("gemini_input_mode", "GEMINI_INPUT_MODE", "text"),
}


def load_app_settings(db_path: str | Path | None = None) -> dict[str, str]:
    path = Path(db_path) if db_path else DB_PATH
    if not path.exists():
        return {}
    try:
        conn = sqlite3.connect(path)
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        conn.close()
    except sqlite3.Error:
        return {}
    return {clean_text(key): clean_text(value) for key, value in rows}


def effective_setting(
    key: str,
    *,
    settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    db_path: str | Path | None = None,
) -> dict[str, str]:
    definition = SETTING_DEFINITIONS[key]
    env = os.environ if environ is None else environ
    values = dict(settings) if settings is not None else load_app_settings(db_path)
    if clean_text(values.get(key)) != "":
        return {"value": clean_text(values.get(key)), "source": "settings", "label": "Configurado en la Suite"}
    if clean_text(env.get(definition.env_var)) != "":
        return {"value": clean_text(env.get(definition.env_var)), "source": "env", "label": "Variable de entorno"}
    if definition.default != "":
        return {"value": definition.default, "source": "default", "label": "Valor por defecto"}
    return {"value": "", "source": "missing", "label": "No configurado"}


def effective_text(
    key: str,
    *,
    settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    db_path: str | Path | None = None,
) -> str:
    return effective_setting(key, settings=settings, environ=environ, db_path=db_path)["value"]


def effective_bool(
    key: str,
    *,
    settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    db_path: str | Path | None = None,
) -> bool:
    return bool_text(effective_text(key, settings=settings, environ=environ, db_path=db_path))


def effective_int(
    key: str,
    default: int,
    *,
    settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    db_path: str | Path | None = None,
    minimum: int = 1,
) -> int:
    try:
        return max(minimum, int(effective_text(key, settings=settings, environ=environ, db_path=db_path)))
    except (TypeError, ValueError):
        return default


def source_map(
    keys: list[str] | tuple[str, ...],
    *,
    settings: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    return {key: effective_setting(key, settings=settings, environ=environ) for key in keys}
