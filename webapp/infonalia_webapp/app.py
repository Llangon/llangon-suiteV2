from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import os
import re
import secrets
import smtplib
import sqlite3
import subprocess
import sys
import time
from email.message import EmailMessage
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    from .environment import load_env_file, required_env
except ImportError:
    from environment import load_env_file, required_env

try:
    from .user_settings import (
        config_payload as settings_config_payload,
        new_user_payload,
        seed_users_and_settings as seed_user_settings,
        settings_update_payload,
        update_settings as update_settings_values,
        updated_user_payload,
        user_row_to_dict,
    )
except ImportError:
    from user_settings import (
        config_payload as settings_config_payload,
        new_user_payload,
        seed_users_and_settings as seed_user_settings,
        settings_update_payload,
        update_settings as update_settings_values,
        updated_user_payload,
        user_row_to_dict,
    )

try:
    from .actuaciones import (
        ACTUACION_ESTADOS,
        ACTUACION_ESTADOS_ABIERTOS,
        ACTUACION_ESTADOS_CERRADOS,
        ACTUACION_TIPOS,
        actuacion_payload,
        actuacion_to_dict,
        clean_value as clean_actuacion_value,
        summarize_actuaciones,
        visual_state as actuacion_visual_state,
    )
except ImportError:
    from actuaciones import (
        ACTUACION_ESTADOS,
        ACTUACION_ESTADOS_ABIERTOS,
        ACTUACION_ESTADOS_CERRADOS,
        ACTUACION_TIPOS,
        actuacion_payload,
        actuacion_to_dict,
        clean_value as clean_actuacion_value,
        summarize_actuaciones,
        visual_state as actuacion_visual_state,
    )

try:
    from .auth_crypto import (
        encode_token_payload as encode_signed_token_payload,
        hash_password,
        make_session_token,
        read_session_token,
        verify_password,
    )
except ImportError:
    from auth_crypto import (
        encode_token_payload as encode_signed_token_payload,
        hash_password,
        make_session_token,
        read_session_token,
        verify_password,
    )

try:
    from .audit_records import (
        create_download_job,
        create_import_run,
        finish_download_job,
        finish_import_run,
        licitacion_id_for_payload,
        record_storage_upload,
        record_import_result,
    )
except ImportError:
    from audit_records import (
        create_download_job,
        create_import_run,
        finish_download_job,
        finish_import_run,
        licitacion_id_for_payload,
        record_storage_upload,
        record_import_result,
    )

try:
    from .csrf import generate_csrf_token, is_csrf_required, validate_csrf_token
except ImportError:
    from csrf import generate_csrf_token, is_csrf_required, validate_csrf_token

try:
    from .normalization import clean_text, bool_text, parse_date_value, parse_money, parse_time_value
except ImportError:
    from normalization import clean_text, bool_text, parse_date_value, parse_money, parse_time_value

try:
    from .formatting import format_date_es, format_datetime_es
except ImportError:
    from formatting import format_date_es, format_datetime_es

try:
    from .url_helpers import detectar_plataforma, normalize_url, should_update_url
except ImportError:
    from url_helpers import detectar_plataforma, normalize_url, should_update_url

try:
    from .licitacion_capture import CaptureError, capture_licitacion_from_url
except ImportError:
    from licitacion_capture import CaptureError, capture_licitacion_from_url

try:
    from .licitacion_states import (
        ADMIN_REVIEW_STATES,
        AGENDA_LICITACION_STATES,
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
        ESTADOS_ORDEN,
        ESTADOS_VALIDOS,
        ESTADO_LABELS,
        NURIA_DEFAULT_REVIEW_STATES,
        NURIA_DISCARDED_STATES,
        NURIA_REVIEW_STATES,
        NURIA_VISIBLE_STATES,
        normalize_licitacion_estado,
    )
    from .csv_parsing import (
        CSV_ALIASES,
        build_payload_from_csv_row,
        csv_alias_map,
        decode_csv_bytes,
        normalize_estado,
        normalize_key,
        read_csv_rows,
        row_value,
    )
except ImportError:
    from licitacion_states import (
        ADMIN_REVIEW_STATES,
        AGENDA_LICITACION_STATES,
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
        ESTADOS_ORDEN,
        ESTADOS_VALIDOS,
        ESTADO_LABELS,
        NURIA_DEFAULT_REVIEW_STATES,
        NURIA_DISCARDED_STATES,
        NURIA_REVIEW_STATES,
        NURIA_VISIBLE_STATES,
        normalize_licitacion_estado,
    )
    from csv_parsing import (
        CSV_ALIASES,
        build_payload_from_csv_row,
        csv_alias_map,
        decode_csv_bytes,
        normalize_estado,
        normalize_key,
        read_csv_rows,
        row_value,
    )

try:
    from .infonalia_days import (
        day_row_to_dict,
        get_or_create_day,
        is_nuria_update_pending as day_nuria_update_pending,
        mark_day_nuria_dirty,
        refresh_day_status,
    )
except ImportError:
    from infonalia_days import (
        day_row_to_dict,
        get_or_create_day,
        is_nuria_update_pending as day_nuria_update_pending,
        mark_day_nuria_dirty,
        refresh_day_status,
    )

try:
    from .licitation_records import licitation_row_to_dict
except ImportError:
    from licitation_records import licitation_row_to_dict

try:
    from .news_helpers import build_news_payload, news_to_dict
except ImportError:
    from news_helpers import build_news_payload, news_to_dict

try:
    from .msg_parsing import (
        extract_hora_limite_from_text,
        extract_msg_date,
        extract_tipo_contrato,
        extraer_despues_de_dos_puntos,
        extraer_fecha_msg,
    )
except ImportError:
    from msg_parsing import (
        extract_hora_limite_from_text,
        extract_msg_date,
        extract_tipo_contrato,
        extraer_despues_de_dos_puntos,
        extraer_fecha_msg,
    )

try:
    from .multipart_uploads import extract_multipart_file
except ImportError:
    from multipart_uploads import extract_multipart_file

try:
    from .pdf_enrichment import (
        download_to_path as pdf_download_to_path,
        enrich_from_pdf_url,
        find_pdftotext_path,
        pdf_file_to_text,
    )
except ImportError:
    from pdf_enrichment import (
        download_to_path as pdf_download_to_path,
        enrich_from_pdf_url,
        find_pdftotext_path,
        pdf_file_to_text,
    )

try:
    from .storage_paths import (
        default_dropbox_folder,
        folder_descriptor,
        get_nombre_mes,
        normalize_relative_folder_path,
        path_is_relative_to,
        row_get,
        storage_root_for_destination,
        write_http_url,
        dropbox_relative_path as storage_dropbox_relative_path,
        is_internal_download_path as storage_is_internal_download_path,
        resolve_destination_folder as storage_resolve_destination_folder,
    )
except ImportError:
    from storage_paths import (
        default_dropbox_folder,
        folder_descriptor,
        get_nombre_mes,
        normalize_relative_folder_path,
        path_is_relative_to,
        row_get,
        storage_root_for_destination,
        write_http_url,
        dropbox_relative_path as storage_dropbox_relative_path,
        is_internal_download_path as storage_is_internal_download_path,
        resolve_destination_folder as storage_resolve_destination_folder,
    )

try:
    from .ai_preview_helpers import (
        build_preview_payload,
        preview_payload_to_text,
    )
except ImportError:
    from ai_preview_helpers import (
        build_preview_payload,
        preview_payload_to_text,
    )

try:
    from .notification_rendering import (
        build_notification_email_html,
        notification_body_parts,
        parse_day_review_notification,
    )
except ImportError:
    from notification_rendering import (
        build_notification_email_html,
        notification_body_parts,
        parse_day_review_notification,
    )

try:
    from .notification_delivery import (
        attach_logo_to_message,
        create_notification_record,
        notification_recipients_for_target,
        send_notification_email_with_settings,
    )
except ImportError:
    from notification_delivery import (
        attach_logo_to_message,
        create_notification_record,
        notification_recipients_for_target,
        send_notification_email_with_settings,
    )

try:
    from .notification_records import notification_items_and_unread, notification_query_filters
except ImportError:
    from notification_records import notification_items_and_unread, notification_query_filters

try:
    from .db_migrations import enable_foreign_keys, run_migrations
except ImportError:
    from db_migrations import enable_foreign_keys, run_migrations

try:
    from .seguimiento_markers import (
        ensure_id_marker,
        get_marker_status_for_licitacion,
        marker_status_for_folder,
        monitor_year_bounds,
        sync_marker_paths,
    )
except ImportError:
    from seguimiento_markers import (
        ensure_id_marker,
        get_marker_status_for_licitacion,
        marker_status_for_folder,
        monitor_year_bounds,
        sync_marker_paths,
    )

try:
    from .monitor.service import MonitorError, run_automation_task, run_monitor
    from .monitor.repository import ensure_monitor_schema, get_monitor_run, list_monitor_runs
except ImportError:
    from monitor.service import MonitorError, run_automation_task, run_monitor
    from monitor.repository import ensure_monitor_schema, get_monitor_run, list_monitor_runs

try:
    from .actuacion_indicators import (
        apply_licitacion_actuaciones_filter,
        fetch_licitacion_actuacion_indicators,
        list_licitacion_actuaciones,
    )
    from .licitacion_center import (
        ESTADOS_INTERNOS,
        build_licitacion_center_detail,
        center_update_payload,
        fetch_licitacion_download_indicators,
        record_licitacion_history,
    )
    from .agenda.email_summary import (
        build_agenda_email_html,
        build_agenda_email_summary,
        build_operational_email_html,
        build_operational_email_payload,
        build_operational_email_subject,
        build_operational_email_text,
    )
    from .agenda.service import (
        build_agenda_events,
        build_agenda_response,
        create_agenda_evento,
        set_agenda_evento_estado,
        update_agenda_evento,
    )
    from .agenda.pending_tasks import build_pending_tasks_response
    from .agenda.workbench import build_agenda_workbench
except ImportError:
    from actuacion_indicators import (
        apply_licitacion_actuaciones_filter,
        fetch_licitacion_actuacion_indicators,
        list_licitacion_actuaciones,
    )
    from licitacion_center import (
        ESTADOS_INTERNOS,
        build_licitacion_center_detail,
        center_update_payload,
        fetch_licitacion_download_indicators,
        record_licitacion_history,
    )
    from agenda.email_summary import (
        build_agenda_email_html,
        build_agenda_email_summary,
        build_operational_email_html,
        build_operational_email_payload,
        build_operational_email_subject,
        build_operational_email_text,
    )
    from agenda.service import (
        build_agenda_events,
        build_agenda_response,
        create_agenda_evento,
        set_agenda_evento_estado,
        update_agenda_evento,
    )
    from agenda.pending_tasks import build_pending_tasks_response
    from agenda.workbench import build_agenda_workbench

try:
    from .local_storage import LocalStorageError, write_local_manifest
except ImportError:
    from local_storage import LocalStorageError, write_local_manifest

try:
    from .services.download_storage_service import (
        DropboxStorageError,
        StorageConfigurationError,
        download_staging_root_for_backend,
        finalize_download_storage,
        simulate_dropbox_dry_run,
        storage_status_payload,
        test_dropbox_configuration,
        uses_dropbox_api_backend,
    )
except ImportError:
    from services.download_storage_service import (
        DropboxStorageError,
        StorageConfigurationError,
        download_staging_root_for_backend,
        finalize_download_storage,
        simulate_dropbox_dry_run,
        storage_status_payload,
        test_dropbox_configuration,
        uses_dropbox_api_backend,
    )

try:
    from .web_security import (
        DEFAULT_LOGIN_MAX_ATTEMPTS,
        DEFAULT_LOGIN_WINDOW_SECONDS,
        LoginRateLimiter,
        build_clear_cookie,
        build_security_headers,
        build_session_cookie,
        get_client_ip,
        normalize_login_key,
    )
except ImportError:
    from web_security import (
        DEFAULT_LOGIN_MAX_ATTEMPTS,
        DEFAULT_LOGIN_WINDOW_SECONDS,
        LoginRateLimiter,
        build_clear_cookie,
        build_security_headers,
        build_session_cookie,
        get_client_ip,
        normalize_login_key,
    )

try:
    from .download_safety import (
        MAX_CAPTURED_OUTPUT_CHARS,
        MAX_DOWNLOAD_FILE_COUNT,
        MAX_DOWNLOAD_RUNTIME_SECONDS,
        MAX_DOWNLOAD_TOTAL_BYTES,
        DownloadSafetyError,
        scan_download_folder,
        summarize_process_output,
        validate_download_folder_limits,
        validate_download_url,
        validate_resolved_destination,
    )
except ImportError:
    from download_safety import (
        MAX_CAPTURED_OUTPUT_CHARS,
        MAX_DOWNLOAD_FILE_COUNT,
        MAX_DOWNLOAD_RUNTIME_SECONDS,
        MAX_DOWNLOAD_TOTAL_BYTES,
        DownloadSafetyError,
        scan_download_folder,
        summarize_process_output,
        validate_download_folder_limits,
        validate_download_url,
        validate_resolved_destination,
    )

try:
    from .limits import (
        MAX_BODY_BYTES,
        MAX_UPLOAD_BYTES,
        InvalidContentLength,
        InvalidUploadExtension,
        InvalidUploadName,
        RequestTooLarge,
        validate_content_length,
    )
except ImportError:
    from limits import (
        MAX_BODY_BYTES,
        MAX_UPLOAD_BYTES,
        InvalidContentLength,
        InvalidUploadExtension,
        InvalidUploadName,
        RequestTooLarge,
        validate_content_length,
    )


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
TOOLS_ROOT = REPOSITORY_ROOT / "herramientas_python"
STATIC_ROOT = APP_ROOT / "static"
DATA_ROOT = APP_ROOT / "data"
DOWNLOAD_ROOT = DATA_ROOT / "descargas"
DB_PATH = DATA_ROOT / "infonalia.db"
SECRET_PATH = DATA_ROOT / "secret.key"
LAUNCHER_PATH = TOOLS_ROOT / "Descargar_Licitacion.py"
ENV_PATH = APP_ROOT / ".env"
PUBLIC_ROUTES = {
    "/",
    "/servicios",
    "/metodologia",
    "/contratacion-publica",
    "/noticias",
    "/zona-privada",
    "/contacto",
    "/aviso-legal",
    "/politica-privacidad",
    "/politica-cookies",
}

load_env_file(ENV_PATH)


ADMIN_USER = required_env("INFONALIA_ADMIN_USER")
ADMIN_PASSWORD = required_env("INFONALIA_ADMIN_PASSWORD")
ADMIN_EMAIL = os.environ.get("INFONALIA_ADMIN_EMAIL", "").strip()
REVIEWER_USER = required_env("INFONALIA_REVIEWER_USER")
REVIEWER_PASSWORD = required_env("INFONALIA_REVIEWER_PASSWORD")
REVIEWER_EMAIL = os.environ.get("INFONALIA_REVIEWER_EMAIL", "").strip()
ADMIN_DISPLAY_NAME = os.environ.get("INFONALIA_ADMIN_DISPLAY_NAME", "Administración")
REVIEWER_DISPLAY_NAME = os.environ.get("INFONALIA_REVIEWER_DISPLAY_NAME", "Revisión")
SMTP_HOST = os.environ.get("INFONALIA_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("INFONALIA_SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("INFONALIA_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("INFONALIA_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("INFONALIA_SMTP_FROM", SMTP_USER or ADMIN_EMAIL or REVIEWER_EMAIL)
SMTP_USE_SSL = os.environ.get("INFONALIA_SMTP_SSL", "0") == "1"
SMTP_ENABLED = os.environ.get("INFONALIA_SMTP_ENABLED", "0") == "1"
SMTP_USE_TLS = os.environ.get("INFONALIA_SMTP_USE_TLS", os.environ.get("INFONALIA_SMTP_TLS", "1")) != "0"
EMAIL_DRY_RUN = os.environ.get("INFONALIA_EMAIL_DRY_RUN", "1") != "0"
AGENDA_EMAIL_TO = os.environ.get("INFONALIA_AGENDA_EMAIL_TO", "").strip()
SEGUIMIENTO_EMAILS = os.environ.get("INFONALIA_SEGUIMIENTO_EMAILS", "").strip()
MONITOR_TEST_EMAIL = (
    os.environ.get("MONITOR_TEST_EMAIL")
    or os.environ.get("INFONALIA_MONITOR_TEST_EMAIL")
    or ""
).strip()
MONITOR_YEAR_MIN, MONITOR_YEAR_MAX = monitor_year_bounds()
COOKIE_SECURE = os.environ.get("INFONALIA_COOKIE_SECURE", "0") == "1"
SESSION_COOKIE = "infonalia_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 10
CSRF_HEADER = "X-CSRF-Token"
LOGIN_RATE_LIMITER = LoginRateLimiter(
    max_attempts=int(os.environ.get("INFONALIA_LOGIN_MAX_ATTEMPTS", str(DEFAULT_LOGIN_MAX_ATTEMPTS)) or DEFAULT_LOGIN_MAX_ATTEMPTS),
    window_seconds=int(
        os.environ.get("INFONALIA_LOGIN_WINDOW_SECONDS", str(DEFAULT_LOGIN_WINDOW_SECONDS))
        or DEFAULT_LOGIN_WINDOW_SECONDS
    ),
)


NURIA_ESTADOS = NURIA_VISIBLE_STATES
NURIA_ESTADOS_VALIDOS = set(NURIA_REVIEW_STATES)
NURIA_LICITACIONES_ESTADOS = AGENDA_LICITACION_STATES
CALENDARIO_ESTADOS = AGENDA_LICITACION_STATES

USERS = {
    ADMIN_USER: {
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
        "role": "admin",
        "display_name": ADMIN_DISPLAY_NAME,
        "email": ADMIN_EMAIL,
    },
    REVIEWER_USER: {
        "username": REVIEWER_USER,
        "password": REVIEWER_PASSWORD,
        "role": "nuria",
        "display_name": REVIEWER_DISPLAY_NAME,
        "email": REVIEWER_EMAIL,
    },
}
admin_alias_password = os.environ.get("INFONALIA_ADMIN_ALIAS_PASSWORD", "").strip()
if os.environ.get("INFONALIA_ENABLE_ADMIN_ALIAS", "0") == "1" and "admin" not in USERS:
    if not admin_alias_password:
        raise RuntimeError(
            "INFONALIA_ADMIN_ALIAS_PASSWORD es obligatoria cuando INFONALIA_ENABLE_ADMIN_ALIAS=1."
        )
    USERS["admin"] = {
        "username": "admin",
        "password": admin_alias_password,
        "role": "admin",
        "display_name": ADMIN_DISPLAY_NAME,
        "email": ADMIN_EMAIL,
    }

DEFAULT_SETTINGS = {
    "maintenance_mode": "0",
    "smtp_host": SMTP_HOST,
    "smtp_port": str(SMTP_PORT),
    "smtp_user": SMTP_USER,
    "smtp_password": SMTP_PASSWORD,
    "smtp_from": SMTP_FROM,
    "smtp_enabled": "1" if SMTP_ENABLED else "0",
    "smtp_tls": "1" if SMTP_USE_TLS else "0",
    "smtp_ssl": "1" if SMTP_USE_SSL else "0",
    "email_dry_run": "1" if EMAIL_DRY_RUN else "0",
    "agenda_email_to": AGENDA_EMAIL_TO,
    "seguimiento_emails": SEGUIMIENTO_EMAILS,
    "monitor_test_email": MONITOR_TEST_EMAIL,
}

DIA_ESTADOS_ORDEN = [
    "Importado",
    "En filtrado interno",
    "Listo para enviar a Nuria",
    "Cambios pendientes para Nuria",
    "Pendiente de revisión Nuria",
    "Enviado a Nuria",
    "Abierto por Nuria",
    "Revisión parcial",
    "Completado",
]
DIA_ESTADOS_VALIDOS = set(DIA_ESTADOS_ORDEN)

def ensure_data_dir() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def get_secret() -> bytes:
    ensure_data_dir()
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")


def encode_token_payload(payload: dict) -> str:
    return encode_signed_token_payload(payload, get_secret())


def make_token(
    username: str,
    role: str,
    csrf_token: str | None = None,
    issued_at: int | None = None,
) -> str:
    return make_session_token(
        username,
        role,
        get_secret(),
        csrf_token=csrf_token,
        issued_at=issued_at,
        csrf_token_factory=generate_csrf_token,
    )


def read_token(token: str | None) -> dict | None:
    return read_session_token(token, get_secret(), SESSION_MAX_AGE_SECONDS)


def db() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    enable_foreign_keys(conn)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session():
    conn = db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS infonalia_dias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL UNIQUE,
                titulo TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Importado',
                enviado_nuria_at TEXT,
                nuria_dirty_at TEXT,
                abierto_nuria_at TEXT,
                completado_at TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                infonalia_dia_id INTEGER,
                fecha_infonalia TEXT,
                expediente TEXT NOT NULL,
                objeto TEXT,
                organismo TEXT,
                provincia TEXT,
                tipo TEXT,
                presupuesto REAL,
                fecha_limite TEXT,
                hora_limite TEXT,
                plataforma TEXT,
                enlace_perfil TEXT,
                enlace_infonalia TEXT,
                estado TEXT NOT NULL DEFAULT 'Importada',
                comentario TEXT,
                ruta_carpeta TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (infonalia_dia_id) REFERENCES infonalia_dias(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT NOT NULL,
                usuario_origen TEXT,
                usuario_destino TEXT,
                asunto TEXT NOT NULL,
                cuerpo TEXT,
                ficheros_adjuntos TEXT,
                email_sent_at TEXT,
                email_error TEXT,
                read_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                email TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS noticias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                excerpt TEXT,
                content TEXT,
                category TEXT,
                tags TEXT,
                featured_image TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                is_featured INTEGER NOT NULL DEFAULT 0,
                published_at TEXT,
                author TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "licitaciones", "infonalia_dia_id", "INTEGER")
        ensure_column(conn, "infonalia_dias", "reviewed_at", "TEXT")
        ensure_column(conn, "infonalia_dias", "nuria_dirty_at", "TEXT")
        ensure_column(conn, "notificaciones", "email_sent_at", "TEXT")
        ensure_column(conn, "notificaciones", "email_error", "TEXT")
        ensure_column(conn, "notificaciones", "read_at", "TEXT")
        ensure_column(conn, "usuarios", "email", "TEXT")
        ensure_column(conn, "usuarios", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "usuarios", "created_at", "TEXT")
        ensure_column(conn, "usuarios", "updated_at", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_dia ON licitaciones(infonalia_dia_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_estado ON licitaciones(estado)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha_limite ON licitaciones(fecha_limite)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_destino ON notificaciones(usuario_destino)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_fecha ON notificaciones(fecha_hora)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_role ON usuarios(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_noticias_status ON noticias(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_noticias_published ON noticias(published_at)")
        run_migrations(conn)
        seed_users_and_settings(conn)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def actuaciones_select_sql(where: list[str] | None = None) -> str:
    sql = """
        SELECT a.*,
               (
                   SELECT COUNT(*)
                   FROM actuacion_licitaciones al_count
                   WHERE al_count.actuacion_id = a.id
               ) AS licitaciones_count
        FROM actuaciones a
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END ASC, a.deadline_at ASC, a.id DESC"
    return sql


def get_actuacion_row(conn: sqlite3.Connection, actuacion_id: int) -> sqlite3.Row | None:
    rows = conn.execute(actuaciones_select_sql(["a.id = ?"]), (actuacion_id,)).fetchall()
    return rows[0] if rows else None


def licitacion_selection_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "expediente": row["expediente"] or "",
        "organismo": row["organismo"] or "",
        "objeto": row["objeto"] or "",
        "fecha_limite": row["fecha_limite"] or "",
        "hora_limite": row["hora_limite"] or "",
        "estado": row["estado"] or "",
        "provincia": row["provincia"] or "",
        "plataforma": row["plataforma"] or "",
    }


def actuacion_licitaciones(conn: sqlite3.Connection, actuacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT l.id, l.expediente, l.organismo, l.objeto, l.fecha_limite, l.hora_limite,
               l.estado, l.provincia, l.plataforma
        FROM actuacion_licitaciones al
        JOIN licitaciones l ON l.id = al.licitacion_id
        WHERE al.actuacion_id = ?
        ORDER BY l.expediente ASC, l.id ASC
        """,
        (actuacion_id,),
    ).fetchall()
    return [licitacion_selection_dict(row) for row in rows]


def actuacion_historial(conn: sqlite3.Connection, actuacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, actuacion_id, user_id, event_type, comentario, old_value, new_value, created_at
        FROM actuacion_historial
        WHERE actuacion_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (actuacion_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "actuacion_id": row["actuacion_id"],
            "user_id": row["user_id"] or "",
            "event_type": row["event_type"],
            "comentario": row["comentario"] or "",
            "old_value": row["old_value"] or "",
            "new_value": row["new_value"] or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def actuacion_response(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    include_historial: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    return actuacion_to_dict(
        row,
        licitaciones=actuacion_licitaciones(conn, int(row["id"])),
        historial=actuacion_historial(conn, int(row["id"])) if include_historial else [],
        now=now,
    )


def normalize_licitacion_ids(value: object) -> list[int]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise ValueError("licitacion_ids debe ser una lista.")
    normalized: list[int] = []
    seen: set[int] = set()
    for raw in value:
        try:
            licitacion_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("licitacion_ids contiene un id no valido.") from exc
        if licitacion_id <= 0:
            raise ValueError("licitacion_ids contiene un id no valido.")
        if licitacion_id not in seen:
            normalized.append(licitacion_id)
            seen.add(licitacion_id)
    return normalized


def validate_licitacion_ids(conn: sqlite3.Connection, licitacion_ids: list[int]) -> list[int]:
    if not licitacion_ids:
        return []
    placeholders = ",".join("?" for _ in licitacion_ids)
    existing = {
        int(row["id"])
        for row in conn.execute(
            f"SELECT id FROM licitaciones WHERE id IN ({placeholders})",
            licitacion_ids,
        ).fetchall()
    }
    missing = [str(licitacion_id) for licitacion_id in licitacion_ids if licitacion_id not in existing]
    if missing:
        raise ValueError(f"Licitaciones vinculadas no encontradas: {', '.join(missing)}")
    return licitacion_ids


def current_actuacion_licitacion_ids(conn: sqlite3.Connection, actuacion_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT licitacion_id FROM actuacion_licitaciones WHERE actuacion_id = ? ORDER BY licitacion_id ASC",
        (actuacion_id,),
    ).fetchall()
    return [int(row["licitacion_id"]) for row in rows]


def record_actuacion_event(
    conn: sqlite3.Connection,
    actuacion_id: int,
    *,
    user_id: str,
    event_type: str,
    comentario: str = "",
    old_value: object = "",
    new_value: object = "",
    timestamp: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO actuacion_historial (
            actuacion_id, user_id, event_type, comentario, old_value, new_value, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actuacion_id,
            user_id,
            event_type,
            comentario,
            str(old_value or ""),
            str(new_value or ""),
            timestamp or now_iso(),
        ),
    )


def set_actuacion_licitaciones(
    conn: sqlite3.Connection,
    actuacion_id: int,
    licitacion_ids: list[int],
    *,
    user_id: str,
    timestamp: str,
    record_event: bool = True,
) -> bool:
    valid_ids = validate_licitacion_ids(conn, licitacion_ids)
    old_ids = current_actuacion_licitacion_ids(conn, actuacion_id)
    if old_ids == sorted(valid_ids):
        return False
    conn.execute("DELETE FROM actuacion_licitaciones WHERE actuacion_id = ?", (actuacion_id,))
    for licitacion_id in valid_ids:
        conn.execute(
            """
            INSERT OR IGNORE INTO actuacion_licitaciones (
                actuacion_id, licitacion_id, created_at, created_by
            )
            VALUES (?, ?, ?, ?)
            """,
            (actuacion_id, licitacion_id, timestamp, user_id),
        )
    if record_event:
        record_actuacion_event(
            conn,
            actuacion_id,
            user_id=user_id,
            event_type="licitaciones",
            comentario="Cambio de licitaciones vinculadas",
            old_value=",".join(str(item) for item in old_ids),
            new_value=",".join(str(item) for item in sorted(valid_ids)),
            timestamp=timestamp,
        )
    return True


def open_actuaciones_count(conn: sqlite3.Connection, licitacion_ids: list[int]) -> int:
    if not licitacion_ids:
        return 0
    placeholders = ",".join("?" for _ in licitacion_ids)
    estado_placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
    row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT a.id) AS total
        FROM actuaciones a
        JOIN actuacion_licitaciones al ON al.actuacion_id = a.id
        WHERE al.licitacion_id IN ({placeholders})
          AND a.estado IN ({estado_placeholders})
        """,
        [*licitacion_ids, *sorted(ACTUACION_ESTADOS_ABIERTOS)],
    ).fetchone()
    return int(row["total"] if row else 0)


def delete_licitacion_dependents(conn: sqlite3.Connection, licitacion_ids: list[int]) -> None:
    if not licitacion_ids:
        return
    placeholders = ",".join("?" for _ in licitacion_ids)
    conn.execute(
        f"DELETE FROM download_jobs WHERE licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    conn.execute(
        f"UPDATE import_results SET licitacion_id = NULL WHERE licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    conn.execute(
        f"DELETE FROM actuacion_licitaciones WHERE licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    conn.execute(
        f"DELETE FROM licitacion_historial WHERE licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    conn.execute(
        f"DELETE FROM licitacion_seguimiento_novedades WHERE licitacion_id IN ({placeholders})",
        licitacion_ids,
    )


def seed_users_and_settings(conn: sqlite3.Connection) -> None:
    seed_user_settings(
        conn,
        USERS,
        DEFAULT_SETTINGS,
        timestamp=now_iso(),
        password_hasher=hash_password,
    )


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    return licitation_row_to_dict(
        row,
        detect_platform=detectar_plataforma,
        normalize_url_value=normalize_url,
        normalize_folder_path=folder_path_for_storage,
    )


def get_user_record(username: object, include_password: bool = False) -> dict | None:
    key = clean_text(username).lower()
    if not key:
        return None
    with db_session() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (key,)).fetchone()
    return user_row_to_dict(row, include_password=include_password)


def list_user_records(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM usuarios"
    values: list[object] = []
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY role ASC, display_name COLLATE NOCASE ASC, username ASC"
    with db_session() as conn:
        return [user_row_to_dict(row) for row in conn.execute(sql, values)]


def get_settings() -> dict[str, str]:
    with db_session() as conn:
        return {row["key"]: row["value"] or "" for row in conn.execute("SELECT key, value FROM app_settings")}


def get_setting(key: str, default: str = "") -> str:
    with db_session() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"] or ""
    return default


def update_settings(conn: sqlite3.Connection, settings: dict[str, object]) -> None:
    update_settings_values(conn, settings, timestamp=now_iso())


def maintenance_mode_enabled() -> bool:
    return bool_text(get_setting("maintenance_mode", "0"))


def find_dropbox_root() -> Path | None:
    configured = clean_text(os.environ.get("INFONALIA_DROPBOX_ROOT"))
    if configured:
        candidate = Path(os.path.expandvars(configured)).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    home = Path.home()
    for candidate in [
        home / "Dropbox" / "00000 LLANGON",
        home / "Dropbox",
    ]:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def is_internal_download_path(value: object) -> bool:
    return storage_is_internal_download_path(value, DOWNLOAD_ROOT)


def dropbox_relative_path(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value).strip('"')
    if not text:
        return ""
    if not Path(text).is_absolute():
        return storage_dropbox_relative_path(text, dropbox_root)
    return storage_dropbox_relative_path(text, dropbox_root or find_dropbox_root())


def folder_path_for_storage(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    relative = dropbox_relative_path(text, dropbox_root)
    if relative:
        return relative
    return text


def get_or_create_dia(conn: sqlite3.Connection, fecha_infonalia: str) -> int:
    return get_or_create_day(conn, fecha_infonalia, now=now_iso)


def is_nuria_update_pending(row: sqlite3.Row | dict | None) -> bool:
    return day_nuria_update_pending(row)


def dia_is_reviewed(conn: sqlite3.Connection, dia_id: int | None) -> bool:
    if not dia_id:
        return False
    row = conn.execute(
        "SELECT reviewed_at FROM infonalia_dias WHERE id = ?",
        (dia_id,),
    ).fetchone()
    return bool(row and clean_text(row["reviewed_at"]))


def mark_dia_nuria_dirty(conn: sqlite3.Connection, dia_id: int | None, timestamp: str | None = None) -> None:
    if not dia_id:
        return
    if dia_is_reviewed(conn, dia_id):
        return
    mark_day_nuria_dirty(conn, dia_id, timestamp=timestamp or now_iso())


def refresh_dia_estado(conn: sqlite3.Connection, dia_id: int) -> None:
    if dia_is_reviewed(conn, dia_id):
        return
    refresh_day_status(conn, dia_id, timestamp=now_iso())


def dia_to_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return day_row_to_dict(conn, row)


def insert_payload(conn: sqlite3.Connection, payload: dict[str, object], dia_id: int | None = None) -> str:
    expediente = clean_text(payload.get("expediente"))
    organismo = clean_text(payload.get("organismo"))
    if not expediente:
        return "skipped"

    exists = conn.execute(
        """
        SELECT * FROM licitaciones
        WHERE expediente = ? AND COALESCE(organismo, '') = ?
        LIMIT 1
        """,
        (expediente, organismo),
    ).fetchone()
    if exists:
        updates = {}
        if dia_id and not exists["infonalia_dia_id"]:
            updates["infonalia_dia_id"] = dia_id
        nueva_ruta = folder_path_for_storage(payload.get("ruta_carpeta"))
        ruta_actual = clean_text(exists["ruta_carpeta"])
        if nueva_ruta and (not ruta_actual or is_internal_download_path(ruta_actual)):
            updates["ruta_carpeta"] = nueva_ruta

        for key in (
            "fecha_infonalia",
            "objeto",
            "provincia",
            "tipo",
            "presupuesto",
            "fecha_limite",
            "hora_limite",
            "plataforma",
            "comentario",
        ):
            if key not in payload:
                continue
            current = exists[key]
            incoming = payload[key]
            if (current is None or clean_text(current) == "") and clean_text(incoming) != "":
                updates[key] = incoming

        for key in ("enlace_perfil", "enlace_infonalia"):
            if key not in payload:
                continue
            current = exists[key]
            incoming = payload[key]
            if should_update_url(current, incoming):
                updates[key] = incoming

        if updates:
            updates["updated_at"] = now_iso()
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE licitaciones SET {set_clause} WHERE id = ?",
                list(updates.values()) + [exists["id"]],
            )
            return "updated"

        return "skipped"

    timestamp = now_iso()
    payload = dict(payload)
    payload["estado"] = normalize_licitacion_estado(payload.get("estado"), default=ESTADO_IMPORTADA)
    if "ruta_carpeta" in payload:
        payload["ruta_carpeta"] = folder_path_for_storage(payload.get("ruta_carpeta"))
    payload["infonalia_dia_id"] = dia_id
    payload["created_at"] = timestamp
    payload["updated_at"] = timestamp
    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    conn.execute(
        f"INSERT INTO licitaciones ({columns}) VALUES ({placeholders})",
        list(payload.values()),
    )
    return "inserted"


def import_csv_content(content: bytes, *, triggered_by: str = "", input_name: str = "") -> dict:
    rows, headers = read_csv_rows(content)
    mapping = csv_alias_map(headers)
    if "expediente" not in mapping:
        raise ValueError("No encuentro la columna Expediente en el CSV.")

    imported = 0
    updated = 0
    skipped = 0
    without_expediente = 0
    touched_days: set[int] = set()

    with db_session() as conn:
        run_timestamp = now_iso()
        import_run_id = create_import_run(
            conn,
            source_name="csv",
            source_type="csv",
            mode="manual",
            input_hash=hashlib.sha256(content).hexdigest(),
            triggered_by=clean_text(triggered_by),
            input_name=clean_text(input_name),
            timestamp=run_timestamp,
        )
        for row in rows:
            payload = build_payload_from_csv_row(row, mapping)
            if not clean_text(payload.get("expediente")):
                without_expediente += 1
                record_import_result(
                    conn,
                    import_run_id=import_run_id,
                    source_name="csv",
                    payload=payload,
                    status="skipped",
                    error_message="Sin expediente",
                    timestamp=now_iso(),
                )
                continue
            dia_id = get_or_create_dia(conn, clean_text(payload.get("fecha_infonalia")))
            touched_days.add(dia_id)
            result = insert_payload(conn, payload, dia_id)
            licitacion_id = licitacion_id_for_payload(conn, payload)
            record_import_result(
                conn,
                import_run_id=import_run_id,
                source_name="csv",
                payload=payload,
                status=result,
                licitacion_id=licitacion_id,
                timestamp=now_iso(),
            )
            if result == "inserted":
                imported += 1
                mark_dia_nuria_dirty(conn, dia_id)
            elif result == "updated":
                updated += 1
                mark_dia_nuria_dirty(conn, dia_id)
            else:
                skipped += 1
        for dia_id in touched_days:
            refresh_dia_estado(conn, dia_id)
        finish_import_run(
            conn,
            import_run_id,
            status="completed",
            new_count=imported,
            updated_count=updated,
            duplicate_count=skipped,
            error_count=without_expediente,
            timestamp=now_iso(),
        )

    return {
        "importadas": imported,
        "actualizadas": updated,
        "omitidas": skipped,
        "sin_expediente": without_expediente,
        "dias": len(touched_days),
        "columnas_detectadas": sorted(mapping.keys()),
    }


def parse_msg_body(body: str, fecha_infonalia: str, enrich_pdf: bool = True) -> list[dict[str, object]]:
    blocks = [block for block in re.split(r"_{20,}", body or "") if "Ref. Infonalia:" in block]
    payloads: list[dict[str, object]] = []

    for block in blocks:
        data = {
            "enlace_infonalia": "",
            "enlace_perfil": "",
            "expediente": "",
            "organismo": "",
            "objeto": "",
            "provincia": "",
            "fecha_limite": "",
            "presupuesto": None,
            "tipo": "",
            "hora_limite": "",
        }

        for raw_line in block.splitlines():
            line = clean_text(raw_line)
            if not line:
                continue
            lower = line.lower()

            if "ver el texto íntegro del anuncio:" in lower or "ver el texto integro del anuncio:" in lower:
                data["enlace_infonalia"] = normalize_url(extraer_despues_de_dos_puntos(line))
            elif "perfil del contratante" in lower:
                data["enlace_perfil"] = normalize_url(extraer_despues_de_dos_puntos(line))
            elif "expediente" in lower:
                data["expediente"] = extraer_despues_de_dos_puntos(line)
            elif lower.startswith("organismo"):
                data["organismo"] = extraer_despues_de_dos_puntos(line)
            elif "resumen del objeto" in lower:
                data["objeto"] = extraer_despues_de_dos_puntos(line)
            elif "provincia" in lower:
                data["provincia"] = extraer_despues_de_dos_puntos(line)
            elif "plazo presentación" in lower or "plazo presentacion" in lower:
                data["fecha_limite"] = extraer_fecha_msg(line)
            elif lower.startswith("presupuesto"):
                data["presupuesto"] = parse_money(extraer_despues_de_dos_puntos(line))

        if not clean_text(data["expediente"]):
            continue

        if enrich_pdf and data["enlace_infonalia"]:
            enriched = enrich_from_infonalia_pdf(
                clean_text(data["enlace_infonalia"]),
                clean_text(data["fecha_limite"]),
            )
            if enriched.get("tipo"):
                data["tipo"] = enriched["tipo"]
            if enriched.get("hora_limite"):
                data["hora_limite"] = enriched["hora_limite"]

        payloads.append(
            {
                "fecha_infonalia": fecha_infonalia,
                "expediente": clean_text(data["expediente"]),
                "objeto": clean_text(data["objeto"]),
                "organismo": clean_text(data["organismo"]),
                "provincia": clean_text(data["provincia"]),
                "tipo": clean_text(data["tipo"]),
                "presupuesto": data["presupuesto"],
                "fecha_limite": clean_text(data["fecha_limite"]),
                "hora_limite": clean_text(data["hora_limite"]),
                "plataforma": detectar_plataforma(clean_text(data["enlace_perfil"])),
                "enlace_perfil": clean_text(data["enlace_perfil"]),
                "enlace_infonalia": clean_text(data["enlace_infonalia"]),
                "estado": ESTADO_IMPORTADA,
                "comentario": "",
                "ruta_carpeta": "",
            }
        )

    return payloads


def find_pdftotext() -> Path | None:
    return find_pdftotext_path(PROJECT_ROOT, APP_ROOT)


def download_to_path(url: str, destination: Path) -> bool:
    return pdf_download_to_path(url, destination)


def pdf_to_text(pdf_path: Path) -> str:
    return pdf_file_to_text(pdf_path, find_pdftotext())


def enrich_from_infonalia_pdf(url: str, fecha_limite: str) -> dict[str, str]:
    return enrich_from_pdf_url(
        url,
        fecha_limite,
        temp_dir=DATA_ROOT / "tmp_pdf",
        downloader=download_to_path,
        text_reader=pdf_to_text,
    )


def import_msg_content(
    content: bytes,
    enrich_pdf: bool = True,
    *,
    triggered_by: str = "",
    input_name: str = "",
) -> dict:
    try:
        import extract_msg
    except ImportError as exc:
        raise ValueError("No está disponible la librería para leer ficheros MSG.") from exc

    upload_dir = DATA_ROOT / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    msg_path = upload_dir / f"infonalia_{time.time_ns()}.msg"
    msg_path.write_bytes(content)

    try:
        msg = extract_msg.Message(str(msg_path))
        try:
            fecha_infonalia = extract_msg_date(msg.date)
            body = msg.body or ""
        finally:
            msg.close()
    except Exception as exc:
        raise ValueError(f"No se pudo leer el MSG: {exc}") from exc

    payloads = parse_msg_body(body, fecha_infonalia, enrich_pdf=enrich_pdf)
    if not payloads:
        raise ValueError("No se han encontrado licitaciones dentro del MSG.")

    imported = 0
    updated = 0
    skipped = 0
    dia_id = None

    with db_session() as conn:
        run_timestamp = now_iso()
        import_run_id = create_import_run(
            conn,
            source_name="email_infonalia",
            source_type="email_infonalia",
            mode="manual",
            input_hash=hashlib.sha256(content).hexdigest(),
            triggered_by=clean_text(triggered_by),
            input_name=clean_text(input_name),
            timestamp=run_timestamp,
        )
        dia_id = get_or_create_dia(conn, fecha_infonalia)
        for payload in payloads:
            result = insert_payload(conn, payload, dia_id)
            licitacion_id = licitacion_id_for_payload(conn, payload)
            record_import_result(
                conn,
                import_run_id=import_run_id,
                source_name="email_infonalia",
                payload=payload,
                status=result,
                licitacion_id=licitacion_id,
                timestamp=now_iso(),
            )
            if result == "inserted":
                imported += 1
                mark_dia_nuria_dirty(conn, dia_id)
            elif result == "updated":
                updated += 1
                mark_dia_nuria_dirty(conn, dia_id)
            else:
                skipped += 1
        refresh_dia_estado(conn, dia_id)
        finish_import_run(
            conn,
            import_run_id,
            status="completed",
            new_count=imported,
            updated_count=updated,
            duplicate_count=skipped,
            error_count=0,
            timestamp=now_iso(),
        )

    return {
        "dias": 1,
        "dia_id": dia_id,
        "fecha_infonalia": fecha_infonalia,
        "importadas": imported,
        "actualizadas": updated,
        "omitidas": skipped,
        "sin_expediente": 0,
        "pdf_enriquecido": bool(enrich_pdf and find_pdftotext()),
    }


def resolve_destination_folder(row: sqlite3.Row | dict) -> Path:
    download_root = download_staging_root_for_backend(REPOSITORY_ROOT, DOWNLOAD_ROOT)
    dropbox_root = None if uses_dropbox_api_backend() else find_dropbox_root()
    destination_row = dict(row) if uses_dropbox_api_backend() else row
    if uses_dropbox_api_backend():
        destination_row["ruta_carpeta"] = ""
    return storage_resolve_destination_folder(
        destination_row,
        download_root=download_root,
        dropbox_root=dropbox_root,
    )


def repair_internal_download_routes() -> int:
    dropbox_root = find_dropbox_root()
    if not dropbox_root:
        return 0

    repaired = 0
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT * FROM licitaciones
            WHERE ruta_carpeta IS NOT NULL AND ruta_carpeta <> ''
            """
        ).fetchall()
        for row in rows:
            ruta = clean_text(row["ruta_carpeta"])
            if not ruta:
                continue
            if is_internal_download_path(ruta):
                nueva_ruta = folder_path_for_storage(default_dropbox_folder(row, dropbox_root), dropbox_root)
            else:
                nueva_ruta = folder_path_for_storage(ruta, dropbox_root)
            if nueva_ruta and nueva_ruta != ruta:
                conn.execute(
                    "UPDATE licitaciones SET ruta_carpeta = ?, updated_at = ? WHERE id = ?",
                    (nueva_ruta, now_iso(), row["id"]),
                )
                repaired += 1
    return repaired


def build_ai_preview_payload(licitacion_id: int) -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            raise ValueError("Licitación no encontrada")

    return build_preview_payload(
        row,
        licitacion_id=licitacion_id,
        generated_at=now_iso(),
        detect_platform=detectar_plataforma,
    )


def notification_recipients(usuario_destino: str | None) -> list[str]:
    return notification_recipients_for_target(
        usuario_destino,
        get_user=get_user_record,
        list_users=list_user_records,
    )


PLATFORM_URL = os.environ.get("INFONALIA_PLATFORM_URL", "").strip()


def render_notification_email_html(asunto: str, cuerpo: str, usuario_destino: str | None) -> str:
    return build_notification_email_html(
        asunto,
        cuerpo,
        usuario_destino,
        platform_url=PLATFORM_URL,
        generated_at=now_iso(),
    )


def attach_notification_logo(message: EmailMessage) -> None:
    attach_logo_to_message(message, STATIC_ROOT / "logo-llangon.png")


def send_notification_email(usuario_destino: str | None, asunto: str, cuerpo: str) -> tuple[str | None, str | None]:
    settings = get_settings()
    recipients = notification_recipients(usuario_destino)
    return send_notification_email_with_settings(
        settings=settings,
        recipients=recipients,
        subject=asunto,
        body=cuerpo,
        html_body=render_notification_email_html(asunto, cuerpo or asunto, usuario_destino),
        logo_path=STATIC_ROOT / "logo-llangon.png",
        now=now_iso,
        smtp_factory=smtplib.SMTP,
        smtp_ssl_factory=smtplib.SMTP_SSL,
    )


def monitor_test_recipient(user: dict | None = None, settings: dict[str, str] | None = None) -> str:
    settings = settings or get_settings()
    user = user or {}
    return clean_text(
        os.environ.get("MONITOR_TEST_EMAIL")
        or os.environ.get("INFONALIA_MONITOR_TEST_EMAIL")
        or settings.get("monitor_test_email")
        or settings.get("agenda_email_to")
        or user.get("email")
    )


def send_monitor_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: str,
    *,
    settings: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    return send_notification_email_with_settings(
        settings=settings or get_settings(),
        recipients=[recipient],
        subject=subject,
        body=body,
        html_body=html_body,
        logo_path=STATIC_ROOT / "logo-llangon.png",
        now=now_iso,
        smtp_factory=smtplib.SMTP,
        smtp_ssl_factory=smtplib.SMTP_SSL,
    )


def create_notification(
    conn: sqlite3.Connection,
    usuario_origen: str | None,
    usuario_destino: str | None,
    asunto: str,
    cuerpo: str,
    ficheros_adjuntos: str = "",
) -> int:
    sent_at, email_error = send_notification_email(usuario_destino, asunto, cuerpo)
    return create_notification_record(
        conn,
        usuario_origen=usuario_origen,
        usuario_destino=usuario_destino,
        asunto=asunto,
        cuerpo=cuerpo,
        ficheros_adjuntos=ficheros_adjuntos,
        sent_at=sent_at,
        email_error=email_error,
        timestamp=now_iso(),
    )


class InfonaliaHandler(BaseHTTPRequestHandler):
    server_version = "InfonaliaWeb/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/login":
            self.send_file(STATIC_ROOT / "login.html")
            return
        if path == "/logout":
            self.send_json({"error": "Usa POST para cerrar sesión."}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        if path.startswith("/static/"):
            self.send_file(STATIC_ROOT / unquote(path.removeprefix("/static/")), is_private=False)
            return
        if path == "/api/public/noticias":
            self.api_public_news()
            return

        if path in PUBLIC_ROUTES or path.startswith("/noticias/"):
            self.send_public_page()
            return

        if not self.current_user():
            self.redirect("/login")
            return

        if path == "/app" or path.startswith("/app/"):
            self.send_file(STATIC_ROOT / "index.html")
        elif path == "/api/health":
            self.send_json({"ok": True})
        elif path == "/api/me":
            self.api_me()
        elif path == "/api/dias":
            self.api_list_dias()
        elif path == "/api/agenda/pending-tasks":
            self.api_agenda_pending_tasks(parsed.query)
        elif path == "/api/agenda/workbench":
            self.api_agenda_workbench()
        elif path == "/api/agenda":
            self.api_agenda(parsed.query)
        elif path == "/api/licitaciones/search":
            self.api_search_licitaciones(parsed.query)
        elif path == "/api/licitaciones":
            self.api_list_licitaciones(parsed.query)
        elif path.startswith("/api/licitaciones/") and path.endswith("/actuaciones"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/actuaciones").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_licitacion_actuaciones(int(licitacion_id))
        elif path.startswith("/api/licitaciones/"):
            licitacion_id = path.removeprefix("/api/licitaciones/").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_licitacion(int(licitacion_id))
        elif path == "/api/actuaciones":
            self.api_list_actuaciones(parsed.query)
        elif path == "/api/actuaciones/resumen":
            self.api_actuaciones_resumen()
        elif path.startswith("/api/actuaciones/"):
            actuacion_id = path.removeprefix("/api/actuaciones/").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_actuacion(int(actuacion_id))
        elif path == "/api/notificaciones":
            self.api_list_notificaciones(parsed.query)
        elif path == "/api/config":
            self.api_get_config()
        elif path == "/api/storage/status":
            self.api_storage_status()
        elif path == "/api/monitor/runs":
            self.api_monitor_runs(parsed.query)
        elif path.startswith("/api/monitor/runs/"):
            run_id = path.removeprefix("/api/monitor/runs/").strip("/")
            if not run_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_monitor_run_detail(int(run_id))
        elif path == "/api/news":
            self.api_list_news()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/login":
            self.handle_login()
            return
        if path == "/logout":
            if not self.current_user():
                self.redirect("/login", clear_cookie=True)
                return
            if not self.require_csrf_token():
                return
            self.redirect("/login", clear_cookie=True)
            return

        if not self.current_user():
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        if self.csrf_required_for_path("POST", path) and not self.require_csrf_token():
            return

        if path == "/api/licitaciones":
            self.api_create_licitacion()
        elif path == "/api/licitaciones/capture":
            self.api_capture_licitacion()
        elif path == "/api/config/users":
            self.api_create_user()
        elif path == "/api/config/test-smtp":
            self.api_test_smtp()
        elif path == "/api/storage/dropbox/test":
            self.api_storage_dropbox_test()
        elif path == "/api/storage/dropbox/dry-run":
            self.api_storage_dropbox_dry_run()
        elif path == "/api/storage/markers/sync":
            self.api_storage_markers_sync()
        elif path == "/api/monitor/run":
            self.api_monitor_run()
        elif path == "/api/news":
            self.api_create_news()
        elif path == "/api/agenda/email-summary":
            self.api_send_agenda_email_summary()
        elif path == "/api/agenda/eventos":
            self.api_create_agenda_evento()
        elif path == "/api/actuaciones":
            self.api_create_actuacion()
        elif path == "/api/import/msg":
            self.api_import_msg()
        elif path == "/api/import/csv":
            self.api_import_csv()
        elif path.startswith("/api/dias/") and path.endswith("/revisado"):
            dia_id = path.removeprefix("/api/dias/").removesuffix("/revisado").strip("/")
            if not dia_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_mark_dia_revisado(int(dia_id))
        elif path.startswith("/api/dias/") and path.endswith("/enviar-nuria"):
            dia_id = path.removeprefix("/api/dias/").removesuffix("/enviar-nuria").strip("/")
            if not dia_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_send_dia_to_nuria(int(dia_id))
        elif path.startswith("/api/dias/") and path.endswith("/desmarcar-revisado"):
            dia_id = path.removeprefix("/api/dias/").removesuffix("/desmarcar-revisado").strip("/")
            if not dia_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_unmark_dia_revisado(int(dia_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/descargar"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/descargar").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_download_licitacion(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ia-preview/email"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ia-preview/email").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_send_ai_preview_email(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ia-preview"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ia-preview").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_generate_ai_preview(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/actuaciones"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/actuaciones").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_create_actuacion(int(licitacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/historial"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/historial").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_add_actuacion_historial(int(actuacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/duplicar"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/duplicar").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_duplicate_actuacion(int(actuacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/cerrar"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/cerrar").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_close_actuacion(int(actuacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/cancelar"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/cancelar").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_cancel_actuacion(int(actuacion_id))
        elif path.startswith("/api/agenda/eventos/") and path.endswith("/cerrar"):
            evento_id = path.removeprefix("/api/agenda/eventos/").removesuffix("/cerrar").strip("/")
            if not evento_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_set_agenda_evento_estado(int(evento_id), "cerrado")
        elif path.startswith("/api/agenda/eventos/") and path.endswith("/cancelar"):
            evento_id = path.removeprefix("/api/agenda/eventos/").removesuffix("/cancelar").strip("/")
            if not evento_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_set_agenda_evento_estado(int(evento_id), "cancelado")
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if not self.current_user():
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        if self.csrf_required_for_path("PATCH", path) and not self.require_csrf_token():
            return

        if path.startswith("/api/agenda/eventos/"):
            evento_id = path.removeprefix("/api/agenda/eventos/").strip("/")
            if not evento_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_agenda_evento(int(evento_id))
        elif path.startswith("/api/actuaciones/"):
            actuacion_id = path.removeprefix("/api/actuaciones/").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_actuacion(int(actuacion_id))
        elif path.startswith("/api/licitaciones/"):
            licitacion_id = path.removeprefix("/api/licitaciones/").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_licitacion(int(licitacion_id))
        elif path.startswith("/api/config/users/"):
            username = unquote(path.removeprefix("/api/config/users/").strip("/"))
            self.api_update_user(username)
        elif path == "/api/config/settings":
            self.api_update_settings()
        elif path.startswith("/api/news/"):
            news_id = path.removeprefix("/api/news/").strip("/")
            if not news_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_news(int(news_id))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if not self.current_user():
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        if self.csrf_required_for_path("DELETE", path) and not self.require_csrf_token():
            return

        if path.startswith("/api/licitaciones/"):
            licitacion_id = path.removeprefix("/api/licitaciones/").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_delete_licitacion(int(licitacion_id))
        elif path.startswith("/api/dias/"):
            dia_id = path.removeprefix("/api/dias/").strip("/")
            if not dia_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_delete_dia(int(dia_id))
        elif path.startswith("/api/config/users/"):
            username = unquote(path.removeprefix("/api/config/users/").strip("/"))
            self.api_delete_user(username)
        elif path.startswith("/api/news/"):
            news_id = path.removeprefix("/api/news/").strip("/")
            if not news_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_delete_news(int(news_id))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")

    def current_user(self) -> dict | None:
        if hasattr(self, "_current_user_cache"):
            return self._current_user_cache

        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        payload = read_token(token.value if token else None)
        if not payload:
            self._current_user_cache = None
            return None
        username = str(payload.get("u", ""))
        user = get_user_record(username)
        if not user or not user.get("active"):
            self._current_user_cache = None
            return None
        if maintenance_mode_enabled() and user.get("role") != "admin":
            self._current_user_cache = None
            return None
        csrf_token = str(payload.get("csrf") or "")
        if not csrf_token:
            csrf_token = generate_csrf_token()
            self._pending_session_cookie = make_token(
                username,
                str(user["role"]),
                csrf_token=csrf_token,
                issued_at=int(payload.get("iat", int(time.time()))),
            )
        user = dict(user)
        user["csrf_token"] = csrf_token
        self._current_user_cache = user
        return user

    def csrf_required_for_path(self, method: str, path: str) -> bool:
        method = method.upper()
        if not is_csrf_required(method, path, authenticated=True):
            return False
        return self.is_known_mutating_route(method, path)

    def is_known_mutating_route(self, method: str, path: str) -> bool:
        method = method.upper()
        if method == "POST":
            if path in {
                "/api/licitaciones",
                "/api/licitaciones/capture",
                "/api/actuaciones",
                "/api/agenda/email-summary",
                "/api/agenda/eventos",
                "/api/config/users",
                "/api/config/test-smtp",
                "/api/storage/dropbox/test",
                "/api/storage/dropbox/dry-run",
                "/api/storage/markers/sync",
                "/api/monitor/run",
                "/api/news",
                "/api/import/csv",
                "/api/import/msg",
            }:
                return True
            if path.startswith("/api/dias/") and (
                path.endswith("/revisado")
                or path.endswith("/enviar-nuria")
                or path.endswith("/desmarcar-revisado")
            ):
                return True
            if path.startswith("/api/licitaciones/") and (
                path.endswith("/descargar")
                or path.endswith("/ia-preview")
                or path.endswith("/ia-preview/email")
                or path.endswith("/actuaciones")
            ):
                return True
            if path.startswith("/api/actuaciones/") and (
                path.endswith("/cerrar")
                or path.endswith("/cancelar")
                or path.endswith("/historial")
                or path.endswith("/duplicar")
            ):
                return True
            if path.startswith("/api/agenda/eventos/") and (
                path.endswith("/cerrar")
                or path.endswith("/cancelar")
            ):
                return True
            return False
        if method == "PATCH":
            return (
                path.startswith("/api/agenda/eventos/")
                or path.startswith("/api/actuaciones/")
                or path.startswith("/api/licitaciones/")
                or path.startswith("/api/config/users/")
                or path == "/api/config/settings"
                or path.startswith("/api/news/")
            )
        if method == "DELETE":
            return (
                path.startswith("/api/licitaciones/")
                or path.startswith("/api/dias/")
                or path.startswith("/api/config/users/")
                or path.startswith("/api/news/")
            )
        return False

    def require_csrf_token(self) -> bool:
        user = self.current_user()
        expected = str(user.get("csrf_token") or "") if user else None
        provided = self.headers.get(CSRF_HEADER)
        if validate_csrf_token(expected, provided):
            return True
        self.send_json({"error": "CSRF token invalido"}, HTTPStatus.FORBIDDEN)
        return False

    def is_admin(self) -> bool:
        user = self.current_user()
        return bool(user and user.get("role") == "admin")

    def require_admin(self) -> bool:
        if self.is_admin():
            return True
        self.send_json({"error": "No tienes permiso para esta accion."}, HTTPStatus.FORBIDDEN)
        return False

    def read_body(self, max_bytes: int | None = None) -> bytes:
        if max_bytes is None:
            length = int(self.headers.get("Content-Length", "0") or "0")
        else:
            length = validate_content_length(self.headers, max_bytes)
        return self.rfile.read(length)

    def read_json(self) -> dict:
        body = self.read_body()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def handle_login(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = parse_qs(self.read_body().decode("utf-8"))
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
        else:
            data = self.read_json()
            username = str(data.get("username", ""))
            password = str(data.get("password", ""))

        login_key = normalize_login_key(get_client_ip(self), username)
        if LOGIN_RATE_LIMITER.is_limited(login_key):
            self.redirect("/login?error=rate")
            return

        user = get_user_record(username, include_password=True)
        if user and user.get("active") and verify_password(user.get("password_hash"), password):
            if maintenance_mode_enabled() and user.get("role") != "admin":
                self.redirect("/login?error=maintenance")
                return
            LOGIN_RATE_LIMITER.clear(login_key)
            token = make_token(username, str(user["role"]))
            self.redirect("/app", cookie=token)
        else:
            LOGIN_RATE_LIMITER.record_failure(login_key)
            self.redirect("/login?error=1")

    def api_me(self) -> None:
        user = self.current_user()
        if not user:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        self.send_json(
            {
                "username": user["username"],
                "role": user["role"],
                "display_name": user["display_name"],
                "csrf_token": user.get("csrf_token", ""),
                "maintenance_mode": maintenance_mode_enabled(),
                "labels": ESTADO_LABELS,
                "nuria_estados": NURIA_ESTADOS,
            }
        )

    def config_payload(self) -> dict:
        settings = get_settings()
        return settings_config_payload(list_user_records(active_only=False), settings)

    def api_get_config(self) -> None:
        if not self.require_admin():
            return
        self.send_json(self.config_payload())

    def api_storage_status(self) -> None:
        if not self.require_admin():
            return
        try:
            payload = storage_status_payload()
            dropbox_root = find_dropbox_root()
            local_download_root = dropbox_root or DOWNLOAD_ROOT
            payload.update(
                {
                    "local_download_root": str(local_download_root),
                    "dropbox_desktop_detected": bool(dropbox_root),
                    "dropbox_desktop_root": str(dropbox_root) if dropbox_root else "",
                    "local_flow_label": "Dropbox Desktop" if dropbox_root else "carpeta local interna",
                    "monitor_year_min": MONITOR_YEAR_MIN,
                    "monitor_year_max": MONITOR_YEAR_MAX,
                }
            )
            self.send_json(payload)
        except StorageConfigurationError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def api_storage_dropbox_test(self) -> None:
        if not self.require_admin():
            return
        try:
            self.send_json(test_dropbox_configuration())
        except StorageConfigurationError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def api_storage_dropbox_dry_run(self) -> None:
        if not self.require_admin():
            return
        try:
            self.send_json(simulate_dropbox_dry_run())
        except StorageConfigurationError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def api_storage_markers_sync(self) -> None:
        if not self.require_admin():
            return
        dropbox_root = find_dropbox_root()
        if not dropbox_root:
            self.send_json(
                {"ok": False, "error": "No se ha encontrado la raíz local de Dropbox."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        with db_session() as conn:
            result = sync_marker_paths(
                conn,
                dropbox_root,
                MONITOR_YEAR_MIN,
                MONITOR_YEAR_MAX,
                timestamp=now_iso(),
                normalize_folder_path=lambda path: folder_path_for_storage(path, dropbox_root),
            )
        self.send_json(result)

    def api_monitor_run(self) -> None:
        if not self.require_admin():
            return
        data = self.read_json()
        task_type = clean_text(data.get("task_type")) or "licitaciones"
        mode = clean_text(data.get("mode")) or "dry-run"
        dry_run_value = data.get("dry_run")
        try:
            if task_type == "licitaciones":
                report = run_monitor(
                    mode,
                    dry_run=bool(dry_run_value) if dry_run_value is not None else None,
                    db_path=DB_PATH,
                )
            else:
                settings = get_settings()
                recipient = monitor_test_recipient(self.current_user(), settings)
                report = run_automation_task(
                    task_type,
                    dry_run=False if dry_run_value is None else bool_text(dry_run_value),
                    db_path=DB_PATH,
                    recipient=recipient,
                    trigger_mode=clean_text(data.get("trigger_mode")) or "manual",
                    email_sender=lambda to, subject, body, html_body: send_monitor_email(
                        to,
                        subject,
                        body,
                        html_body,
                        settings=settings,
                    ),
                )
        except MonitorError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if task_type != "licitaciones" and report.get("status") == "failed":
            self.send_json(
                {**report, "ok": False, "error": clean_text(report.get("error_message")) or "No se pudo ejecutar la tarea."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        self.send_json(report)

    def api_monitor_runs(self, query: str) -> None:
        if not self.require_admin():
            return
        params = parse_qs(query)
        try:
            limit = int(params.get("limit", ["50"])[0])
        except ValueError:
            limit = 50
        task_type = clean_text(params.get("task_type", [""])[0])
        with db_session() as conn:
            ensure_monitor_schema(conn)
            items = list_monitor_runs(conn, limit=limit, task_type=task_type)
        self.send_json({"items": items})

    def api_monitor_run_detail(self, run_id: int) -> None:
        if not self.require_admin():
            return
        with db_session() as conn:
            ensure_monitor_schema(conn)
            item = get_monitor_run(conn, run_id)
        if not item:
            self.send_json({"error": "Ejecucion de monitor no encontrada"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"item": item})

    def require_news_manager(self) -> bool:
        user = self.current_user()
        if user and user.get("role") in {"admin", "editor"}:
            return True
        self.send_json({"error": "No tienes permiso para gestionar noticias."}, HTTPStatus.FORBIDDEN)
        return False

    def api_public_news(self) -> None:
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM noticias
                WHERE status = 'published'
                ORDER BY is_featured DESC, COALESCE(published_at, created_at) DESC, id DESC
                LIMIT 30
                """
            ).fetchall()
        self.send_json({"items": [news_to_dict(row) for row in rows]})

    def api_list_news(self) -> None:
        if not self.require_news_manager():
            return
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM noticias
                ORDER BY COALESCE(published_at, created_at) DESC, id DESC
                """
            ).fetchall()
        self.send_json({"items": [news_to_dict(row) for row in rows]})

    def read_news_payload(self) -> dict:
        data = self.read_json()
        return build_news_payload(data, now=now_iso, normalize_url_value=normalize_url)

    def api_create_news(self) -> None:
        if not self.require_news_manager():
            return
        try:
            payload = self.read_news_payload()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        timestamp = now_iso()
        current = self.current_user() or {}
        author = clean_text(current.get("username"))
        try:
            with db_session() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO noticias (
                        title, slug, excerpt, content, category, tags, featured_image,
                        status, is_featured, published_at, author, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["title"],
                        payload["slug"],
                        payload["excerpt"],
                        payload["content"],
                        payload["category"],
                        payload["tags"],
                        payload["featured_image"],
                        payload["status"],
                        payload["is_featured"],
                        payload["published_at"],
                        author,
                        timestamp,
                        timestamp,
                    ),
                )
                row = conn.execute("SELECT * FROM noticias WHERE id = ?", (cur.lastrowid,)).fetchone()
        except sqlite3.IntegrityError:
            self.send_json({"error": "Ya existe una noticia con ese slug."}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "item": news_to_dict(row)})

    def api_update_news(self, news_id: int) -> None:
        if not self.require_news_manager():
            return
        try:
            payload = self.read_news_payload()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        timestamp = now_iso()
        try:
            with db_session() as conn:
                row = conn.execute("SELECT * FROM noticias WHERE id = ?", (news_id,)).fetchone()
                if not row:
                    self.send_json({"error": "Noticia no encontrada"}, HTTPStatus.NOT_FOUND)
                    return
                conn.execute(
                    """
                    UPDATE noticias
                    SET title = ?, slug = ?, excerpt = ?, content = ?, category = ?, tags = ?,
                        featured_image = ?, status = ?, is_featured = ?, published_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["title"],
                        payload["slug"],
                        payload["excerpt"],
                        payload["content"],
                        payload["category"],
                        payload["tags"],
                        payload["featured_image"],
                        payload["status"],
                        payload["is_featured"],
                        payload["published_at"],
                        timestamp,
                        news_id,
                    ),
                )
                updated = conn.execute("SELECT * FROM noticias WHERE id = ?", (news_id,)).fetchone()
        except sqlite3.IntegrityError:
            self.send_json({"error": "Ya existe una noticia con ese slug."}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "item": news_to_dict(updated)})

    def api_delete_news(self, news_id: int) -> None:
        if not self.require_news_manager():
            return
        with db_session() as conn:
            row = conn.execute("SELECT id FROM noticias WHERE id = ?", (news_id,)).fetchone()
            if not row:
                self.send_json({"error": "Noticia no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            conn.execute("DELETE FROM noticias WHERE id = ?", (news_id,))
        self.send_json({"ok": True})

    def api_create_user(self) -> None:
        if not self.require_admin():
            return

        data = self.read_json()
        try:
            payload = new_user_payload(data)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        timestamp = now_iso()
        try:
            with db_session() as conn:
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["username"],
                        hash_password(payload["password"]),
                        payload["role"],
                        payload["display_name"],
                        payload["email"],
                        payload["active"],
                        timestamp,
                        timestamp,
                    ),
                )
        except sqlite3.IntegrityError:
            self.send_json({"error": "Ya existe un usuario con ese nombre."}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json(self.config_payload(), HTTPStatus.CREATED)

    def api_update_user(self, username: str) -> None:
        if not self.require_admin():
            return

        username = clean_text(username).lower()
        data = self.read_json()
        current = self.current_user() or {}

        with db_session() as conn:
            row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
            if not row:
                self.send_json({"error": "Usuario no encontrado."}, HTTPStatus.NOT_FOUND)
                return

            try:
                payload = updated_user_payload(data, row, username=username)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            role = payload["role"]
            active = payload["active"]
            if username == current.get("username") and not active:
                self.send_json({"error": "No puedes desactivar tu propio usuario."}, HTTPStatus.BAD_REQUEST)
                return

            if (row["role"] == "admin" and role != "admin") or (row["role"] == "admin" and not active):
                other_admins = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM usuarios
                    WHERE username <> ? AND role = 'admin' AND active = 1
                    """,
                    (username,),
                ).fetchone()["total"]
                if not other_admins:
                    self.send_json({"error": "Debe quedar al menos un administrador activo."}, HTTPStatus.BAD_REQUEST)
                    return

            updates = dict(payload)
            updates["updated_at"] = now_iso()
            password = clean_text(data.get("password"))
            if password:
                updates["password_hash"] = hash_password(password)

            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE usuarios SET {set_clause} WHERE username = ?",
                list(updates.values()) + [username],
            )

        self.send_json(self.config_payload())

    def api_delete_user(self, username: str) -> None:
        if not self.require_admin():
            return

        username = clean_text(username).lower()
        current = self.current_user() or {}
        if username == current.get("username"):
            self.send_json({"error": "No puedes darte de baja a ti mismo."}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,)).fetchone()
            if not row:
                self.send_json({"error": "Usuario no encontrado."}, HTTPStatus.NOT_FOUND)
                return
            if row["role"] == "admin":
                other_admins = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM usuarios
                    WHERE username <> ? AND role = 'admin' AND active = 1
                    """,
                    (username,),
                ).fetchone()["total"]
                if not other_admins:
                    self.send_json({"error": "Debe quedar al menos un administrador activo."}, HTTPStatus.BAD_REQUEST)
                    return
            conn.execute(
                "UPDATE usuarios SET active = 0, updated_at = ? WHERE username = ?",
                (now_iso(), username),
            )

        self.send_json(self.config_payload())

    def api_update_settings(self) -> None:
        if not self.require_admin():
            return

        data = self.read_json()
        try:
            updates = settings_update_payload(data)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            update_settings(conn, updates)

        self.send_json(self.config_payload())

    def api_test_smtp(self) -> None:
        if not self.require_admin():
            return

        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        display_name = clean_text(user.get("display_name")) or username or "Administrador"
        subject = "Prueba SMTP Llangón Web App"
        body = (
            f"Hola {display_name},\n\n"
            "Este es un correo de prueba enviado desde la configuración SMTP de Llangón Web App.\n\n"
            f"Fecha y hora: {format_datetime_es(now_iso())}"
        )
        sent_at, error = send_notification_email(username, subject, body)
        if error:
            self.send_json(
                {
                    "ok": False,
                    "error": error,
                    "message": "No se pudo enviar el correo de prueba.",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        self.send_json(
            {
                "ok": True,
                "email_sent_at": sent_at,
                "message": "Correo de prueba enviado correctamente.",
            }
        )

    def api_list_notificaciones(self, query: str = "") -> None:
        user = self.current_user()
        if not user:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return

        params = parse_qs(query)
        where, values = notification_query_filters(params, user)

        with db_session() as conn:
            sql = "SELECT * FROM notificaciones"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY fecha_hora DESC, id DESC LIMIT 200"
            rows = conn.execute(
                sql,
                values,
            ).fetchall()
            items, unread = notification_items_and_unread(rows)

        self.send_json({"items": items, "unread": unread, "users": list_user_records(active_only=False)})

    def api_list_dias(self) -> None:
        user = self.current_user() or {}
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM infonalia_dias
                ORDER BY CASE WHEN fecha = 'sin-fecha' THEN 1 ELSE 0 END ASC,
                         fecha DESC,
                         id DESC
                """
            ).fetchall()
            items = [dia_to_dict(conn, row) for row in rows]
        if user.get("role") == "nuria":
            items = [
                item for item in items
                if item["pendientes_nuria"]
                or item["descartadas_nuria"]
                or item["solo_descargar"]
                or item["preparar_licitacion"]
                or item["descargadas"]
                or item["reviewed_at"]
            ]
        self.send_json({"items": items, "estados": DIA_ESTADOS_ORDEN})

    def api_agenda(self, query: str) -> None:
        params = parse_qs(query)
        with db_session() as conn:
            response = build_agenda_response(conn, params=params)
        self.send_json(response)

    def api_agenda_pending_tasks(self, query: str) -> None:
        if not self.require_admin():
            return
        params = parse_qs(query)
        search = clean_text(params.get("q", [""])[0])
        with db_session() as conn:
            response = build_pending_tasks_response(conn, query=search)
        self.send_json(response)

    def api_agenda_workbench(self) -> None:
        with db_session() as conn:
            response = build_agenda_workbench(conn)
        self.send_json(response)

    def api_send_agenda_email_summary(self) -> None:
        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        settings = get_settings()
        recipient = clean_text(user.get("email")) or clean_text(settings.get("agenda_email_to"))
        if not recipient:
            self.send_json(
                {"error": "No hay email destinatario para el resumen de Agenda."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        dry_run = data.get("dry_run") is not None and bool_text(data.get("dry_run"))
        target_date = clean_text(data.get("date")) or datetime.now().date().isoformat()
        with db_session() as conn:
            today_response = build_agenda_response(
                conn,
                params={"view": "day", "date": target_date, "type": "all"},
            )
            week_response = build_agenda_response(
                conn,
                params={"view": "week", "date": target_date, "type": "all"},
            )
        email_payload = build_operational_email_payload(today_response, week_response)
        subject = build_operational_email_subject()
        body = build_operational_email_text(email_payload)
        sent_at = None
        error = None
        if not dry_run:
            sent_at, error = send_notification_email_with_settings(
                settings=settings,
                recipients=[recipient],
                subject=subject,
                body=body,
                html_body=build_operational_email_html(email_payload),
                logo_path=STATIC_ROOT / "logo-llangon.png",
                now=now_iso,
                smtp_factory=smtplib.SMTP,
                smtp_ssl_factory=smtplib.SMTP_SSL,
            )
            if error:
                if error == "SMTP no configurado":
                    error = "SMTP no configurado. No se ha enviado el correo."
                self.send_json({"error": error}, HTTPStatus.BAD_REQUEST)
                return
        with db_session() as conn:
            create_notification_record(
                conn,
                usuario_origen=username,
                usuario_destino=username,
                asunto=subject,
                cuerpo=body,
                ficheros_adjuntos="",
                sent_at=sent_at,
                email_error=None,
                timestamp=now_iso(),
            )
        self.send_json(
            {
                "ok": True,
                "sent": bool(sent_at),
                "sent_at": sent_at,
                "dry_run": dry_run,
                "recipient": recipient,
                "subject": subject,
                "preview": body,
                "counts": email_payload.get("counts", {}),
            }
        )

    def api_create_agenda_evento(self) -> None:
        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        timestamp = now_iso()
        with db_session() as conn:
            try:
                item = create_agenda_evento(conn, data, username=username, timestamp=timestamp)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_update_agenda_evento(self, evento_id: int) -> None:
        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        timestamp = now_iso()
        with db_session() as conn:
            try:
                item = update_agenda_evento(conn, evento_id, data, username=username, timestamp=timestamp)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if not item:
                self.send_json({"error": "Evento interno no encontrado"}, HTTPStatus.NOT_FOUND)
                return
        self.send_json({"ok": True, "item": item})

    def api_set_agenda_evento_estado(self, evento_id: int, estado: str) -> None:
        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        timestamp = now_iso()
        with db_session() as conn:
            try:
                item = set_agenda_evento_estado(conn, evento_id, estado, username=username, timestamp=timestamp)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if not item:
                self.send_json({"error": "Evento interno no encontrado"}, HTTPStatus.NOT_FOUND)
                return
        self.send_json({"ok": True, "item": item})

    def api_list_licitaciones(self, query: str) -> None:
        user = self.current_user() or {}
        params = parse_qs(query)
        estado = clean_text(params.get("estado", [""])[0])
        search = clean_text(params.get("q", [""])[0])
        dia_id = clean_text(params.get("dia_id", [""])[0])
        vigentes = clean_text(params.get("vigentes", [""])[0]) == "1"
        vivas = clean_text(params.get("vivas", [""])[0]) == "1"
        calendario = clean_text(params.get("calendario", [""])[0]) == "1"
        nuria_filter = clean_text(params.get("nuria_filter", [""])[0]).lower()
        default_order = "asc" if vivas or calendario else "desc"
        orden_fecha = clean_text(params.get("orden_fecha", [default_order])[0]).lower()
        actuaciones_filter = clean_text(params.get("actuaciones", [""])[0]).lower()
        revision_filter = clean_text(params.get("revision", [""])[0]).lower()
        seguimiento_filter = clean_text(params.get("seguimiento", [""])[0]).lower()
        documentacion_filter = clean_text(params.get("documentacion", [""])[0]).lower()
        estado_interno_filter = clean_text(params.get("estado_interno", [""])[0])
        direccion_fecha = "DESC" if orden_fecha == "desc" else "ASC"
        nuria_visible_states = None
        calendario_estados = CALENDARIO_ESTADOS
        vivas_estados = CALENDARIO_ESTADOS
        if calendario:
            if estado and estado != "Todos" and estado not in calendario_estados:
                estado = ""
        elif vivas:
            if estado and estado != "Todos" and estado not in vivas_estados:
                estado = ""
        elif user.get("role") == "nuria":
            if dia_id.isdigit():
                if nuria_filter in {"all", "todas"}:
                    nuria_visible_states = NURIA_VISIBLE_STATES
                elif nuria_filter in {"discarded", "descartadas"}:
                    nuria_visible_states = NURIA_DISCARDED_STATES
                else:
                    nuria_visible_states = NURIA_DEFAULT_REVIEW_STATES
            else:
                nuria_visible_states = CALENDARIO_ESTADOS
            if estado and estado != "Todos" and estado not in nuria_visible_states:
                estado = ""

        where = []
        values: list[object] = []

        if estado and estado != "Todos":
            where.append("estado = ?")
            values.append(estado)
        if calendario:
            placeholders = ", ".join("?" for _ in calendario_estados)
            where.append(f"estado IN ({placeholders})")
            values.extend(calendario_estados)
        elif vivas:
            placeholders = ", ".join("?" for _ in vivas_estados)
            where.append(f"estado IN ({placeholders})")
            values.extend(vivas_estados)
        elif user.get("role") == "nuria" and not (estado and estado != "Todos"):
            placeholders = ", ".join("?" for _ in nuria_visible_states)
            where.append(f"estado IN ({placeholders})")
            values.extend(nuria_visible_states)
        if dia_id.isdigit():
            where.append("infonalia_dia_id = ?")
            values.append(int(dia_id))
        elif vigentes:
            current = datetime.now()
            where.append(
                """
                fecha_limite IS NOT NULL
                AND fecha_limite <> ''
                AND (
                    fecha_limite > ?
                    OR (
                        fecha_limite = ?
                        AND COALESCE(NULLIF(hora_limite, ''), '23:59') >= ?
                    )
                )
                """
            )
            values.extend([
                current.date().isoformat(),
                current.date().isoformat(),
                current.strftime("%H:%M"),
            ])
        if search:
            where.append(
                "(expediente LIKE ? OR objeto LIKE ? OR organismo LIKE ? OR provincia LIKE ?)"
            )
            like = f"%{search}%"
            values.extend([like, like, like, like])
        if revision_filter == "pendiente":
            where.append("(reviewed_at IS NULL OR reviewed_at = '')")
        elif revision_filter == "revisada":
            where.append("reviewed_at IS NOT NULL AND reviewed_at <> ''")
        if seguimiento_filter == "1":
            where.append("seguimiento_activo = 1")
        if documentacion_filter == "sin_descargar":
            where.append("(ruta_carpeta IS NULL OR ruta_carpeta = '')")
        elif documentacion_filter == "fallida":
            where.append(
                """
                EXISTS (
                    SELECT 1 FROM download_jobs dj_filter
                    WHERE dj_filter.licitacion_id = licitaciones.id
                      AND dj_filter.status = 'failed'
                )
                """
            )
        if estado_interno_filter in ESTADOS_INTERNOS:
            where.append("estado_interno = ?")
            values.append(estado_interno_filter)
        current = datetime.now().replace(microsecond=0)
        apply_licitacion_actuaciones_filter(where, values, actuaciones_filter, now_text=current.isoformat())

        sql = "SELECT * FROM licitaciones"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (
            " ORDER BY CASE WHEN fecha_limite IS NULL OR fecha_limite = '' THEN 1 ELSE 0 END ASC, "
            f"fecha_limite {direccion_fecha}, "
            f"hora_limite {direccion_fecha}, "
            "id DESC"
        )

        totals_sql = "SELECT estado, COUNT(*) AS total FROM licitaciones"
        if where:
            totals_sql += " WHERE " + " AND ".join(where)
        totals_sql += " GROUP BY estado"

        with db_session() as conn:
            rows = [row_to_dict(row) for row in conn.execute(sql, values)]
            if rows:
                licitacion_ids = [int(row["id"]) for row in rows]
                counts = fetch_licitacion_actuacion_indicators(conn, licitacion_ids, current=current)
                downloads = fetch_licitacion_download_indicators(conn, licitacion_ids)
                for row in rows:
                    count_row = counts.get(row["id"])
                    download_row = downloads.get(row["id"], {})
                    row["actuaciones_abiertas"] = int(count_row["actuaciones_abiertas"] if count_row else 0)
                    row["actuaciones_vencidas"] = int(count_row["actuaciones_vencidas"] if count_row else 0)
                    row["actuaciones_sin_fecha"] = int(count_row["actuaciones_sin_fecha"] if count_row else 0)
                    row["proxima_actuacion_at"] = count_row["proxima_actuacion_at"] if count_row else ""
                    row["revisada"] = bool(clean_text(row.get("reviewed_at")))
                    row["documentacion_descargada"] = bool(clean_text(row.get("ruta_carpeta")))
                    row["descarga_fallida"] = bool(download_row.get("descarga_fallida"))
                    row["download_error"] = download_row.get("download_error") or ""
            totals: dict[str, int] = {}
            for row in conn.execute(totals_sql, values):
                normalized_state = normalize_licitacion_estado(row["estado"])
                totals[normalized_state] = totals.get(normalized_state, 0) + int(row["total"] or 0)
            day_pending_review = None
            day_pending_admin = None
            day_sent_nuria_at = None
            day_nuria_dirty_at = None
            day_nuria_pending_update = False
            day_reviewed_at = None
            day_nuria_total = None
            if dia_id.isdigit():
                day_row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (int(dia_id),)).fetchone()
                if day_row:
                    day_sent_nuria_at = day_row["enviado_nuria_at"]
                    day_nuria_dirty_at = day_row["nuria_dirty_at"] if "nuria_dirty_at" in day_row.keys() else ""
                    day_nuria_pending_update = is_nuria_update_pending(day_row)
                    day_reviewed_at = day_row["reviewed_at"] if "reviewed_at" in day_row.keys() else ""
                day_counts_rows = conn.execute(
                    """
                    SELECT estado, COUNT(*) AS total
                    FROM licitaciones
                    WHERE infonalia_dia_id = ?
                    GROUP BY estado
                    """,
                    (int(dia_id),),
                ).fetchall()
                day_counts: dict[str, int] = {}
                for row in day_counts_rows:
                    normalized_state = normalize_licitacion_estado(row["estado"])
                    day_counts[normalized_state] = day_counts.get(normalized_state, 0) + int(row["total"] or 0)
                day_pending_review = day_counts.get(ESTADO_ENVIADA_NURIA, 0)
                day_pending_admin = day_counts.get(ESTADO_IMPORTADA, 0)
                day_nuria_total = sum(day_counts.get(state, 0) for state in NURIA_VISIBLE_STATES)
        if calendario:
            estados = calendario_estados
        elif vivas:
            estados = vivas_estados
        elif user.get("role") == "nuria":
            estados = nuria_visible_states if dia_id.isdigit() else CALENDARIO_ESTADOS
        else:
            estados = ESTADOS_ORDEN
        self.send_json(
            {
                "items": rows,
                "totals": totals,
                "estados": estados,
                "day_pending_review": day_pending_review,
                "day_pending_admin": day_pending_admin,
                "day_sent_nuria_at": day_sent_nuria_at,
                "day_nuria_dirty_at": day_nuria_dirty_at,
                "day_nuria_pending_update": day_nuria_pending_update,
                "day_reviewed_at": day_reviewed_at,
                "day_nuria_total": day_nuria_total,
            }
        )

    def api_get_licitacion(self, licitacion_id: int) -> None:
        current = datetime.now().replace(microsecond=0)
        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            item = row_to_dict(row)
            indicators = fetch_licitacion_actuacion_indicators(conn, [licitacion_id], current=current).get(licitacion_id, {})
            actuaciones = list_licitacion_actuaciones(conn, licitacion_id, current=current)
            item.update(
                {
                    "actuaciones_abiertas": int(indicators.get("actuaciones_abiertas") or 0),
                    "actuaciones_vencidas": int(indicators.get("actuaciones_vencidas") or 0),
                    "actuaciones_sin_fecha": int(indicators.get("actuaciones_sin_fecha") or 0),
                    "proxima_actuacion_at": indicators.get("proxima_actuacion_at") or "",
                }
            )
            item = build_licitacion_center_detail(conn, item, actuaciones=actuaciones)
            marker_status = get_marker_status_for_licitacion(item, find_dropbox_root())
            item["seguimiento_activo"] = bool(marker_status.get("activo"))
            item["seguimiento"] = {
                **(item.get("seguimiento") or {}),
                **marker_status,
                "activo": bool(marker_status.get("activo")),
                "fuente": "marcador Dropbox",
            }
        self.send_json({"item": item})

    def api_get_licitacion_actuaciones(self, licitacion_id: int) -> None:
        current = datetime.now().replace(microsecond=0)
        with db_session() as conn:
            exists = conn.execute("SELECT 1 FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not exists:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            items = list_licitacion_actuaciones(conn, licitacion_id, current=current)
        self.send_json({"items": items})

    def api_search_licitaciones(self, query: str) -> None:
        params = parse_qs(query)
        search = clean_text(params.get("q", [""])[0])
        estado = clean_text(params.get("estado", [""])[0])
        provincia = clean_text(params.get("provincia", [""])[0])
        plataforma = clean_text(params.get("plataforma", [""])[0])
        try:
            limit = int(params.get("limit", ["50"])[0])
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        where: list[str] = []
        values: list[object] = []
        if search:
            where.append(
                """
                (
                    expediente LIKE ? OR organismo LIKE ? OR objeto LIKE ? OR provincia LIKE ?
                    OR estado LIKE ? OR fecha_limite LIKE ? OR plataforma LIKE ?
                )
                """
            )
            like = f"%{search}%"
            values.extend([like, like, like, like, like, like, like])
        if estado:
            where.append("estado = ?")
            values.append(estado)
        if provincia:
            where.append("provincia LIKE ?")
            values.append(f"%{provincia}%")
        if plataforma:
            where.append("plataforma = ?")
            values.append(plataforma)

        sql = """
            SELECT id, expediente, organismo, objeto, fecha_limite, hora_limite,
                   estado, provincia, plataforma
            FROM licitaciones
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += """
            ORDER BY CASE WHEN fecha_limite IS NULL OR fecha_limite = '' THEN 1 ELSE 0 END ASC,
                     fecha_limite ASC,
                     hora_limite ASC,
                     id DESC
            LIMIT ?
        """
        values.append(limit)
        with db_session() as conn:
            rows = conn.execute(sql, values).fetchall()
        self.send_json({"items": [licitacion_selection_dict(row) for row in rows]})

    def api_list_actuaciones(self, query: str) -> None:
        params = parse_qs(query)
        where: list[str] = []
        values: list[object] = []
        licitacion_id = clean_text(params.get("licitacion_id", [""])[0])
        estado = clean_text(params.get("estado", [""])[0]).lower()

        if licitacion_id.isdigit():
            where.append(
                """
                EXISTS (
                    SELECT 1 FROM actuacion_licitaciones al_filter
                    WHERE al_filter.actuacion_id = a.id
                      AND al_filter.licitacion_id = ?
                )
                """
            )
            values.append(int(licitacion_id))
        if clean_text(params.get("sin_licitacion", [""])[0]) == "1":
            where.append(
                """
                NOT EXISTS (
                    SELECT 1 FROM actuacion_licitaciones al_empty
                    WHERE al_empty.actuacion_id = a.id
                )
                """
            )
        if estado in ACTUACION_ESTADOS:
            where.append("a.estado = ?")
            values.append(estado)
        if clean_text(params.get("abiertas", [""])[0]) == "1":
            placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
            where.append(f"a.estado IN ({placeholders})")
            values.extend(sorted(ACTUACION_ESTADOS_ABIERTOS))

        current = datetime.now()
        with db_session() as conn:
            rows = conn.execute(actuaciones_select_sql(where), values).fetchall()
            items = [actuacion_response(conn, row, now=current) for row in rows]

        if clean_text(params.get("vencidas", [""])[0]) == "1":
            items = [item for item in items if item["estado_visual"] == "vencida"]
        if clean_text(params.get("hoy", [""])[0]) == "1":
            items = [item for item in items if item["estado_visual"] == "vence_hoy"]
        if clean_text(params.get("semana", [""])[0]) == "1":
            items = [item for item in items if item["estado_visual"] == "vence_esta_semana"]

        self.send_json(
            {
                "items": items,
                "summary": summarize_actuaciones(rows, now=current),
                "tipos": sorted(ACTUACION_TIPOS),
                "estados": sorted(ACTUACION_ESTADOS),
            }
        )

    def api_actuaciones_resumen(self) -> None:
        current = datetime.now()
        placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
        with db_session() as conn:
            rows = conn.execute(
                actuaciones_select_sql([f"a.estado IN ({placeholders})"]),
                sorted(ACTUACION_ESTADOS_ABIERTOS),
            ).fetchall()
        self.send_json(summarize_actuaciones(rows, now=current))

    def api_get_actuacion(self, actuacion_id: int) -> None:
        with db_session() as conn:
            row = get_actuacion_row(conn, actuacion_id)
            if not row:
                self.send_json({"error": "Actuacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            item = actuacion_response(conn, row, include_historial=True)
        self.send_json({"item": item})

    def api_create_actuacion(self, default_licitacion_id: int | None = None) -> None:
        user = self.current_user() or {}
        username = clean_actuacion_value(user.get("username"))
        try:
            data = self.read_json()
            if default_licitacion_id is not None and "licitacion_ids" not in data:
                data["licitacion_ids"] = [default_licitacion_id]
            licitacion_ids = normalize_licitacion_ids(data.get("licitacion_ids"))
            payload = actuacion_payload(data, now=now_iso)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        timestamp = now_iso()
        with db_session() as conn:
            try:
                licitacion_ids = validate_licitacion_ids(conn, licitacion_ids)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            payload.update(
                {
                    "created_by": username,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            if payload.get("estado") in ACTUACION_ESTADOS_CERRADOS:
                payload["closed_at"] = timestamp
                payload["closed_by"] = username
            columns = ", ".join(payload.keys())
            placeholders = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO actuaciones ({columns}) VALUES ({placeholders})",
                list(payload.values()),
            )
            actuacion_id = int(cur.lastrowid)
            set_actuacion_licitaciones(
                conn,
                actuacion_id,
                licitacion_ids,
                user_id=username,
                timestamp=timestamp,
                record_event=False,
            )
            record_actuacion_event(
                conn,
                actuacion_id,
                user_id=username,
                event_type="creacion",
                comentario="Actuacion creada",
                timestamp=timestamp,
            )
            if licitacion_ids:
                record_actuacion_event(
                    conn,
                    actuacion_id,
                    user_id=username,
                    event_type="licitaciones",
                    comentario="Licitaciones vinculadas al crear la actuacion",
                    new_value=",".join(str(item) for item in sorted(licitacion_ids)),
                    timestamp=timestamp,
                )
            row = get_actuacion_row(conn, actuacion_id)
            item = actuacion_response(conn, row, include_historial=True)

        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_update_actuacion(self, actuacion_id: int) -> None:
        user = self.current_user() or {}
        username = clean_actuacion_value(user.get("username"))
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            existing = get_actuacion_row(conn, actuacion_id)
            if not existing:
                self.send_json({"error": "Actuacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            try:
                payload = actuacion_payload(data, partial=True, existing=existing, now=now_iso)
                licitacion_ids = normalize_licitacion_ids(data.get("licitacion_ids")) if "licitacion_ids" in data else None
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if payload.get("estado") in ACTUACION_ESTADOS_CERRADOS and not payload.get("closed_by"):
                payload["closed_by"] = username
            timestamp = clean_actuacion_value(payload.get("updated_at")) or now_iso()
            old_estado = existing["estado"]
            old_deadline = existing["deadline_at"] or ""
            if licitacion_ids is not None:
                try:
                    licitacion_ids = validate_licitacion_ids(conn, licitacion_ids)
                except ValueError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return
            set_clause = ", ".join(f"{key} = ?" for key in payload)
            conn.execute(
                f"UPDATE actuaciones SET {set_clause} WHERE id = ?",
                list(payload.values()) + [actuacion_id],
            )
            if "estado" in payload and payload["estado"] != old_estado:
                record_actuacion_event(
                    conn,
                    actuacion_id,
                    user_id=username,
                    event_type="estado",
                    comentario="Cambio de estado",
                    old_value=old_estado,
                    new_value=payload["estado"],
                    timestamp=timestamp,
                )
            if "deadline_at" in payload and (payload["deadline_at"] or "") != old_deadline:
                record_actuacion_event(
                    conn,
                    actuacion_id,
                    user_id=username,
                    event_type="deadline",
                    comentario="Cambio de fecha limite",
                    old_value=old_deadline,
                    new_value=payload["deadline_at"] or "",
                    timestamp=timestamp,
                )
            if licitacion_ids is not None:
                set_actuacion_licitaciones(
                    conn,
                    actuacion_id,
                    licitacion_ids,
                    user_id=username,
                    timestamp=timestamp,
                )
            row = get_actuacion_row(conn, actuacion_id)
            item = actuacion_response(conn, row, include_historial=True)

        self.send_json({"ok": True, "item": item})

    def api_close_actuacion(self, actuacion_id: int) -> None:
        self.api_set_actuacion_closed_state(actuacion_id, "cerrada")

    def api_cancel_actuacion(self, actuacion_id: int) -> None:
        self.api_set_actuacion_closed_state(actuacion_id, "cancelada")

    def api_set_actuacion_closed_state(self, actuacion_id: int, estado: str) -> None:
        user = self.current_user() or {}
        username = clean_actuacion_value(user.get("username"))
        timestamp = now_iso()
        with db_session() as conn:
            row = get_actuacion_row(conn, actuacion_id)
            if not row:
                self.send_json({"error": "Actuacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            conn.execute(
                """
                UPDATE actuaciones
                SET estado = ?, closed_at = ?, closed_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (estado, timestamp, username, timestamp, actuacion_id),
            )
            record_actuacion_event(
                conn,
                actuacion_id,
                user_id=username,
                event_type="cierre" if estado == "cerrada" else "cancelacion",
                comentario="Actuacion cerrada" if estado == "cerrada" else "Actuacion cancelada",
                old_value=row["estado"],
                new_value=estado,
                timestamp=timestamp,
            )
            updated = get_actuacion_row(conn, actuacion_id)
            item = actuacion_response(conn, updated, include_historial=True)
        self.send_json({"ok": True, "item": item})

    def api_add_actuacion_historial(self, actuacion_id: int) -> None:
        user = self.current_user() or {}
        username = clean_actuacion_value(user.get("username"))
        try:
            data = self.read_json()
            comentario = clean_actuacion_value(data.get("comentario"))
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not comentario:
            self.send_json({"error": "El comentario es obligatorio."}, HTTPStatus.BAD_REQUEST)
            return
        timestamp = now_iso()
        with db_session() as conn:
            row = get_actuacion_row(conn, actuacion_id)
            if not row:
                self.send_json({"error": "Actuacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            record_actuacion_event(
                conn,
                actuacion_id,
                user_id=username,
                event_type="comentario",
                comentario=comentario,
                timestamp=timestamp,
            )
            item = actuacion_response(conn, row, include_historial=True)
        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_duplicate_actuacion(self, actuacion_id: int) -> None:
        user = self.current_user() or {}
        username = clean_actuacion_value(user.get("username"))
        timestamp = now_iso()
        with db_session() as conn:
            row = get_actuacion_row(conn, actuacion_id)
            if not row:
                self.send_json({"error": "Actuacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            licitacion_ids = current_actuacion_licitacion_ids(conn, actuacion_id)
            estado = row["estado"] if row["estado"] in ACTUACION_ESTADOS_ABIERTOS else "pendiente"
            payload = {
                "tipo": row["tipo"],
                "titulo": f"{row['titulo']} (copia)",
                "descripcion": row["descripcion"] or "",
                "deadline_at": row["deadline_at"] or "",
                "recordatorio_email": int(row["recordatorio_email"] or 0),
                "estado": estado,
                "origen": row["origen"] or "manual",
                "created_by": username,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            columns = ", ".join(payload.keys())
            placeholders = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO actuaciones ({columns}) VALUES ({placeholders})",
                list(payload.values()),
            )
            new_id = int(cur.lastrowid)
            set_actuacion_licitaciones(
                conn,
                new_id,
                licitacion_ids,
                user_id=username,
                timestamp=timestamp,
                record_event=False,
            )
            record_actuacion_event(
                conn,
                new_id,
                user_id=username,
                event_type="duplicado",
                comentario=f"Actuacion duplicada desde {actuacion_id}",
                old_value=actuacion_id,
                timestamp=timestamp,
            )
            duplicated = get_actuacion_row(conn, new_id)
            item = actuacion_response(conn, duplicated, include_historial=True)
        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_capture_licitacion(self) -> None:
        if not self.require_admin():
            return
        try:
            data = self.read_json()
            result = capture_licitacion_from_url(data.get("url"), profile_url=data.get("profile_url"))
        except json.JSONDecodeError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except CaptureError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception:
            self.send_json({"ok": False, "error": "Error consultando plataforma."}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(result)

    def api_create_licitacion(self) -> None:
        if not self.require_admin():
            return

        data = self.read_json()
        expediente = clean_text(data.get("expediente"))
        if not expediente:
            self.send_json({"error": "El expediente es obligatorio"}, HTTPStatus.BAD_REQUEST)
            return

        timestamp = now_iso()
        enlace_perfil = normalize_url(data.get("enlace_perfil"))
        enlace_infonalia = normalize_url(data.get("enlace_infonalia"))
        plataforma = clean_text(data.get("plataforma")) or detectar_plataforma(enlace_perfil)
        payload = {
            "fecha_infonalia": clean_text(data.get("fecha_infonalia")),
            "expediente": expediente,
            "objeto": clean_text(data.get("objeto")),
            "organismo": clean_text(data.get("organismo")),
            "provincia": clean_text(data.get("provincia")),
            "tipo": clean_text(data.get("tipo")),
            "presupuesto": parse_money(data.get("presupuesto")),
            "fecha_limite": clean_text(data.get("fecha_limite")),
            "hora_limite": clean_text(data.get("hora_limite")),
            "plataforma": plataforma,
            "enlace_perfil": enlace_perfil,
            "enlace_infonalia": enlace_infonalia,
            "estado": normalize_estado(data.get("estado")) or ESTADO_IMPORTADA,
            "comentario": clean_text(data.get("comentario")),
            "ruta_carpeta": folder_path_for_storage(data.get("ruta_carpeta")),
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        payload["estado"] = normalize_licitacion_estado(payload["estado"], default=ESTADO_IMPORTADA)
        if payload["estado"] not in ESTADOS_VALIDOS:
            payload["estado"] = ESTADO_IMPORTADA

        with db_session() as conn:
            dia_id = None
            if payload["fecha_infonalia"]:
                dia_id = get_or_create_dia(conn, clean_text(payload["fecha_infonalia"]))
            payload["infonalia_dia_id"] = dia_id
            columns = ", ".join(payload.keys())
            placeholders = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO licitaciones ({columns}) VALUES ({placeholders})",
                list(payload.values()),
            )
            if dia_id:
                mark_dia_nuria_dirty(conn, dia_id)
                refresh_dia_estado(conn, dia_id)
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (cur.lastrowid,)).fetchone()
        self.send_json(row_to_dict(row), HTTPStatus.CREATED)

    def api_import_csv(self) -> None:
        if not self.require_admin():
            return

        try:
            content_type = self.headers.get("Content-Type", "")
            body = self.read_body(max_bytes=MAX_BODY_BYTES)
            csv_bytes = extract_multipart_file(
                content_type,
                body,
                "csv_file",
                allowed_extensions={".csv"},
                max_upload_bytes=MAX_UPLOAD_BYTES,
            )
            user = self.current_user() or {}
            result = import_csv_content(csv_bytes, triggered_by=clean_text(user.get("username")))
        except RequestTooLarge as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        except InvalidContentLength as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except (InvalidUploadName, InvalidUploadExtension) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json({"error": f"No se pudo importar el CSV: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json(result)

    def api_import_msg(self) -> None:
        if not self.require_admin():
            return

        try:
            content_type = self.headers.get("Content-Type", "")
            body = self.read_body(max_bytes=MAX_BODY_BYTES)
            msg_bytes = extract_multipart_file(
                content_type,
                body,
                "msg_file",
                allowed_extensions={".msg"},
                max_upload_bytes=MAX_UPLOAD_BYTES,
            )
            enrich_pdf = b'name="enrich_pdf"' in body
            user = self.current_user() or {}
            result = import_msg_content(
                msg_bytes,
                enrich_pdf=enrich_pdf,
                triggered_by=clean_text(user.get("username")),
            )
        except RequestTooLarge as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        except InvalidContentLength as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except (InvalidUploadName, InvalidUploadExtension) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json({"error": f"No se pudo importar el MSG: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json(result)

    def api_send_dia_to_nuria(self, dia_id: int) -> None:
        if not self.require_admin():
            return

        user = self.current_user() or {}
        with db_session() as conn:
            day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            if not day:
                self.send_json({"error": "Dia Infonalia no encontrado"}, HTTPStatus.NOT_FOUND)
                return

            counts_rows = conn.execute(
                """
                SELECT estado, COUNT(*) AS total
                FROM licitaciones
                WHERE infonalia_dia_id = ?
                GROUP BY estado
                """,
                (dia_id,),
            ).fetchall()
            counts: dict[str, int] = {}
            for row in counts_rows:
                normalized_state = normalize_licitacion_estado(row["estado"])
                counts[normalized_state] = counts.get(normalized_state, 0) + int(row["total"] or 0)
            pendientes = counts.get(ESTADO_IMPORTADA, 0)
            pendientes_nuria = counts.get(ESTADO_ENVIADA_NURIA, 0)
            decisiones_nuria = (
                counts.get(ESTADO_DESCARTADA, 0)
                + counts.get(ESTADO_DESCARGAR_PARA_VER, 0)
                + counts.get(ESTADO_PREPARAR_FICHA, 0)
            )
            nuria_total = pendientes_nuria + decisiones_nuria
            pending_rows = conn.execute(
                """
                SELECT expediente, objeto, fecha_limite, hora_limite
                FROM licitaciones
                WHERE infonalia_dia_id = ? AND estado = ?
                ORDER BY fecha_limite ASC, hora_limite ASC, id ASC
                """,
                (dia_id, ESTADO_ENVIADA_NURIA),
            ).fetchall()
            already_sent = bool(clean_text(day["enviado_nuria_at"]))
            pending_update = is_nuria_update_pending(day)
            if pendientes:
                self.send_json(
                    {"error": "Aun quedan licitaciones pendientes de revision interna."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            if not nuria_total and not (already_sent and pending_update):
                self.send_json(
                    {"error": "No hay licitaciones pendientes de revision para Nuria."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            if already_sent and not pending_update and not clean_text(day["reviewed_at"]):
                self.send_json(
                    {"error": "El dia ya esta enviado a Nuria y no hay cambios pendientes."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            timestamp = now_iso()
            conn.execute(
                """
                UPDATE infonalia_dias
                SET estado = 'Pendiente de revisión Nuria',
                    enviado_nuria_at = ?,
                    nuria_dirty_at = NULL,
                    reviewed_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, timestamp, dia_id),
            )
            asunto = f"Infonalia del día {format_date_es(day['fecha'])} disponible para revisar"
            intro = (
                f"{user.get('display_name', 'Administrador')} ha dejado disponible el día {day['titulo']} para su revisión."
            )
            body_lines = [
                intro,
                "",
                f"Total de licitaciones del día: {sum(counts.values())}",
                f"Licitaciones pendientes de revisión: {pendientes_nuria}",
            ]
            if pendientes_nuria == 0:
                body_lines.extend(["", "NO HAY LICITACIONES INTERESANTES"])
            else:
                body_lines.extend(["", "Listado de licitaciones pendientes:"])
                for row in pending_rows:
                    fecha_hora = " ".join(
                        part
                        for part in [
                            format_date_es(row["fecha_limite"]),
                            parse_time_value(row["hora_limite"]),
                        ]
                        if clean_text(part)
                    ).strip()
                    body_lines.append(
                        f"- {clean_text(row['expediente'])} | "
                        f"{clean_text(row['objeto'])} | "
                        f"{fecha_hora or 'Sin fecha'}"
                    )
            cuerpo = "\n".join(body_lines)
            create_notification(
                conn,
                user.get("username"),
                REVIEWER_USER,
                asunto,
                cuerpo,
            )
            row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            item = dia_to_dict(conn, row)

        self.send_json(item)

    def api_mark_dia_revisado(self, dia_id: int) -> None:
        user = self.current_user() or {}
        with db_session() as conn:
            day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            if not day:
                self.send_json({"error": "Dia Infonalia no encontrado"}, HTTPStatus.NOT_FOUND)
                return

            pendientes = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM licitaciones
                WHERE infonalia_dia_id = ? AND estado = ?
                """,
                (dia_id, ESTADO_ENVIADA_NURIA),
            ).fetchone()["total"]
            if pendientes:
                self.send_json(
                    {"error": "Aun quedan licitaciones pendientes de revision."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            timestamp = now_iso()
            conn.execute(
                """
                UPDATE infonalia_dias
                SET reviewed_at = ?,
                    nuria_dirty_at = NULL,
                    estado = 'Completado',
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, timestamp, dia_id),
            )
            if user.get("role") == "nuria":
                counts_rows = conn.execute(
                    """
                    SELECT estado, COUNT(*) AS total
                    FROM licitaciones
                    WHERE infonalia_dia_id = ?
                    GROUP BY estado
                    """,
                    (dia_id,),
                ).fetchall()
                counts: dict[str, int] = {}
                for row in counts_rows:
                    normalized_state = normalize_licitacion_estado(row["estado"])
                    counts[normalized_state] = counts.get(normalized_state, 0) + int(row["total"] or 0)
                asunto = f"Día Infonalia revisado: {day['titulo']}"
                cuerpo = (
                    f"El equipo revisor ha marcado como revisado el día {day['titulo']}.\n\n"
                    f"Descartadas: {counts.get(ESTADO_DESCARTADA, 0)}\n"
                    f"Descargar para ver: {counts.get(ESTADO_DESCARGAR_PARA_VER, 0)}\n"
                    f"Preparar ficha: {counts.get(ESTADO_PREPARAR_FICHA, 0)}"
                )
                create_notification(
                    conn,
                    user.get("username"),
                    ADMIN_USER,
                    asunto,
                    cuerpo,
                )
            row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            item = dia_to_dict(conn, row)

        self.send_json(item)

    def api_unmark_dia_revisado(self, dia_id: int) -> None:
        if not self.require_admin():
            return

        with db_session() as conn:
            day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            if not day:
                self.send_json({"error": "Dia Infonalia no encontrado"}, HTTPStatus.NOT_FOUND)
                return

            timestamp = now_iso()
            conn.execute(
                "UPDATE infonalia_dias SET reviewed_at = NULL, updated_at = ? WHERE id = ?",
                (timestamp, dia_id),
            )
            refresh_dia_estado(conn, dia_id)
            row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            item = dia_to_dict(conn, row)

        self.send_json(item)

    def api_generate_ai_preview(self, licitacion_id: int) -> None:
        try:
            preview = build_ai_preview_payload(licitacion_id)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"preview": preview})

    def api_send_ai_preview_email(self, licitacion_id: int) -> None:
        user = self.current_user() or {}
        username = clean_text(user.get("username"))
        if not username:
            self.send_json({"error": "Usuario no válido"}, HTTPStatus.UNAUTHORIZED)
            return

        try:
            preview = build_ai_preview_payload(licitacion_id)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        expediente = preview.get("cabecera", {}).get("Expediente") or "licitación"
        asunto = f"Vista preliminar: {expediente}"
        cuerpo = preview_payload_to_text(preview)

        with db_session() as conn:
            create_notification(conn, "Sistema", username, asunto, cuerpo)

        self.send_json({"ok": True, "message": "Vista preliminar enviada al buzón y al email configurado."})

    def api_download_licitacion(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()

        if not row:
            self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
            return

        url = normalize_url(row["enlace_perfil"])
        if not url:
            self.send_json({"error": "Esta licitacion no tiene enlace de perfil."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            url = validate_download_url(url)
        except DownloadSafetyError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not LAUNCHER_PATH.exists():
            self.send_json({"error": f"No se encuentra el lanzador: {LAUNCHER_PATH}"}, HTTPStatus.BAD_REQUEST)
            return

        download_root = download_staging_root_for_backend(REPOSITORY_ROOT, DOWNLOAD_ROOT)
        dropbox_root = None if uses_dropbox_api_backend() else find_dropbox_root()
        allowed_destination_roots = [download_root]
        if dropbox_root:
            allowed_destination_roots.append(dropbox_root)

        try:
            destino = validate_resolved_destination(resolve_destination_folder(row), allowed_destination_roots)
        except DownloadSafetyError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        ruta_guardada = folder_path_for_storage(destino)
        destino.mkdir(parents=True, exist_ok=True)
        write_http_url(destino, url)
        with db_session() as conn:
            download_job_id = create_download_job(conn, licitacion_id, timestamp=now_iso())

        try:
            completed = subprocess.run(
                [sys.executable, str(LAUNCHER_PATH), url],
                cwd=str(destino),
                capture_output=True,
                text=True,
                timeout=MAX_DOWNLOAD_RUNTIME_SECONDS,
            )
        except subprocess.TimeoutExpired:
            error_message = "La descarga ha tardado demasiado y se ha detenido."
            with db_session() as conn:
                finish_download_job(
                    conn,
                    download_job_id,
                    status="failed",
                    error_message=error_message,
                    timestamp=now_iso(),
                )
            self.send_json(
                {"error": error_message, "carpeta": str(destino)},
                HTTPStatus.REQUEST_TIMEOUT,
            )
            return

        output_summary = summarize_process_output(
            completed.stdout,
            completed.stderr,
            MAX_CAPTURED_OUTPUT_CHARS,
        )
        salida = output_summary["combined"]

        if completed.returncode != 0:
            error_message = f"El descargador devolvio codigo {completed.returncode}: {salida}".strip()
            with db_session() as conn:
                finish_download_job(
                    conn,
                    download_job_id,
                    status="failed",
                    error_message=error_message[:2000],
                    timestamp=now_iso(),
                )
            self.send_json(
                {
                    "ok": False,
                    "codigo": completed.returncode,
                    "carpeta": str(destino),
                    "ruta_carpeta": ruta_guardada,
                    "salida": salida,
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            folder_summary = scan_download_folder(destino)
            validate_download_folder_limits(
                folder_summary,
                max_total_bytes=MAX_DOWNLOAD_TOTAL_BYTES,
                max_file_count=MAX_DOWNLOAD_FILE_COUNT,
            )
            storage_root = storage_root_for_destination(destino, allowed_destination_roots)
            manifest_object = write_local_manifest(storage_root, destino, source_url=url)
            storage_result = finalize_download_storage(
                local_storage_root=storage_root,
                local_folder=destino,
                local_manifest_uri=manifest_object.uri,
                licitacion_id=licitacion_id,
                expediente=row["expediente"],
                source_url=url,
            )
        except DownloadSafetyError as exc:
            with db_session() as conn:
                finish_download_job(
                    conn,
                    download_job_id,
                    status="failed",
                    error_message=str(exc)[:2000],
                    timestamp=now_iso(),
                )
            self.send_json(
                {
                    "ok": False,
                    "codigo": completed.returncode,
                    "error": str(exc),
                    "carpeta": str(destino),
                    "ruta_carpeta": ruta_guardada,
                    "salida": salida,
                },
                HTTPStatus.BAD_REQUEST,
            )
            return
        except (LocalStorageError, OSError, StorageConfigurationError, DropboxStorageError) as exc:
            error_message = f"No se pudo confirmar el almacenamiento de descarga: {exc}"
            with db_session() as conn:
                finish_download_job(
                    conn,
                    download_job_id,
                    status="failed",
                    error_message=error_message[:2000],
                    timestamp=now_iso(),
                )
            self.send_json(
                {
                    "ok": False,
                    "codigo": completed.returncode,
                    "error": error_message,
                    "carpeta": str(destino),
                    "ruta_carpeta": ruta_guardada,
                    "salida": salida,
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        marker_result = ensure_id_marker(licitacion_id, destino)
        marker_status = marker_status_for_folder(licitacion_id, destino)
        if marker_result.get("error") and not marker_status.get("warning"):
            marker_status["warning"] = marker_result.get("error")

        timestamp = now_iso()
        updates = {
            "ruta_carpeta": ruta_guardada,
            "seguimiento_activo": 1 if marker_status.get("activo") else 0,
            "seguimiento_ultimo_check": timestamp,
            "seguimiento_ultima_sync": timestamp,
            "seguimiento_marker_path": clean_text(marker_result.get("path")),
            "seguimiento_marker_warning": clean_text(marker_status.get("warning")),
            "updated_at": timestamp,
        }

        set_clause = ", ".join(f"{key} = ?" for key in updates)
        storage_status = str(storage_result.get("job_status") or "completed")
        storage_errors = storage_result.get("errors") or []
        storage_error_message = "; ".join(str(error) for error in storage_errors)[:2000]
        with db_session() as conn:
            conn.execute(
                f"UPDATE licitaciones SET {set_clause} WHERE id = ?",
                list(updates.values()) + [licitacion_id],
            )
            if row["infonalia_dia_id"]:
                refresh_dia_estado(conn, int(row["infonalia_dia_id"]))
            finish_download_job(
                conn,
                download_job_id,
                status=storage_status,
                storage_backend=str(storage_result.get("backend") or "local"),
                storage_uri=str(storage_result.get("storage_uri") or ""),
                file_manifest=str(storage_result.get("manifest_uri") or manifest_object.uri),
                error_message=storage_error_message or None,
                timestamp=timestamp,
            )
            record_storage_upload(
                conn,
                licitacion_id=licitacion_id,
                download_job_id=download_job_id,
                backend=str(storage_result.get("backend") or "local"),
                destination_uri=str(storage_result.get("storage_uri") or ""),
                manifest=storage_result,
                status=storage_status,
                dry_run=bool(storage_result.get("dry_run")),
                mode=str(storage_result.get("mode") or ""),
                uploaded_count=int(storage_result.get("uploaded_count") or 0),
                skipped_existing_count=int(storage_result.get("skipped_existing_count") or 0),
                failed_count=int(storage_result.get("failed_count") or 0),
                no_changes=bool(storage_result.get("no_changes")),
                timestamp=timestamp,
                error_message=storage_error_message,
            )

        self.send_json(
            {
                "ok": True,
                "codigo": completed.returncode,
                "carpeta": str(destino),
                "ruta_carpeta": ruta_guardada,
                "salida": salida,
                "marker": marker_result,
                "storage": {
                    "backend": storage_result.get("backend"),
                    "dry_run": storage_result.get("dry_run"),
                    "storage_uri": storage_result.get("storage_uri"),
                    "manifest_uri": storage_result.get("manifest_uri"),
                    "no_changes": storage_result.get("no_changes"),
                    "uploaded_count": storage_result.get("uploaded_count"),
                    "skipped_existing_count": storage_result.get("skipped_existing_count"),
                    "failed_count": storage_result.get("failed_count"),
                    "would_upload_count": storage_result.get("would_upload_count"),
                },
            },
            HTTPStatus.OK,
        )

    def api_update_licitacion(self, licitacion_id: int) -> None:
        user = self.current_user() or {}
        data = self.read_json()

        if user.get("role") == "nuria":
            estado = normalize_licitacion_estado(data.get("estado"), default="")
            if not estado:
                self.send_json({"error": "No hay cambios"}, HTTPStatus.BAD_REQUEST)
                return
            if estado not in NURIA_REVIEW_STATES:
                self.send_json({"error": "Estado no permitido para esta revision."}, HTTPStatus.FORBIDDEN)
                return

            with db_session() as conn:
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if not row:
                    self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                    return
                if normalize_licitacion_estado(row["estado"]) not in NURIA_VISIBLE_STATES:
                    self.send_json({"error": "Esta licitacion no esta en revision de Nuria."}, HTTPStatus.FORBIDDEN)
                    return
                conn.execute(
                    "UPDATE licitaciones SET estado = ?, updated_at = ? WHERE id = ?",
                    (estado, now_iso(), licitacion_id),
                )
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if row and row["infonalia_dia_id"]:
                    refresh_dia_estado(conn, int(row["infonalia_dia_id"]))
            self.send_json(row_to_dict(row))
            return

        if user.get("role") != "admin":
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return

        allowed = {
            "fecha_infonalia",
            "expediente",
            "objeto",
            "organismo",
            "provincia",
            "tipo",
            "fecha_limite",
            "hora_limite",
            "plataforma",
            "enlace_perfil",
            "enlace_infonalia",
            "estado",
            "comentario",
            "ruta_carpeta",
        }

        updates: dict[str, object] = {}
        for key in allowed:
            if key in data:
                updates[key] = clean_text(data.get(key))
        if "enlace_perfil" in updates:
            updates["enlace_perfil"] = normalize_url(updates["enlace_perfil"])
            if "plataforma" not in updates or not updates.get("plataforma"):
                updates["plataforma"] = detectar_plataforma(updates["enlace_perfil"])
        if "enlace_infonalia" in updates:
            updates["enlace_infonalia"] = normalize_url(updates["enlace_infonalia"])
        if "ruta_carpeta" in updates:
            updates["ruta_carpeta"] = folder_path_for_storage(updates["ruta_carpeta"])
        if "presupuesto" in data:
            updates["presupuesto"] = parse_money(data.get("presupuesto"))
        if "estado" in updates:
            updates["estado"] = normalize_licitacion_estado(updates["estado"], default="")
            if updates["estado"] not in ESTADOS_VALIDOS:
                self.send_json({"error": "Estado no valido"}, HTTPStatus.BAD_REQUEST)
                return
        if not updates and not any(
            key in data
            for key in {"estado_interno", "notas_internas", "revisada"}
        ):
            self.send_json({"error": "No hay cambios"}, HTTPStatus.BAD_REQUEST)
            return

        mark_for_nuria = any(
            key != "ruta_carpeta"
            for key in updates
        )
        timestamp = now_iso()

        with db_session() as conn:
            old_row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not old_row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            try:
                center_updates, center_history = center_update_payload(
                    data,
                    old_row,
                    username=clean_text(user.get("username")),
                    timestamp=timestamp,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            updates.update(center_updates)
            if not updates:
                self.send_json({"error": "No hay cambios"}, HTTPStatus.BAD_REQUEST)
                return
            for key, new_value in updates.items():
                if key in {"updated_at", "ruta_carpeta"}:
                    continue
                old_value = old_row[key] if key in old_row.keys() else ""
                if str(old_value or "") != str(new_value or ""):
                    record_licitacion_history(
                        conn,
                        licitacion_id,
                        event_type=key,
                        old_value=old_value,
                        new_value=new_value,
                        user_id=clean_text(user.get("username")),
                        timestamp=timestamp,
                    )
            for key, old_value, new_value in center_history:
                if key in updates:
                    continue
                record_licitacion_history(
                    conn,
                    licitacion_id,
                    event_type=key,
                    old_value=old_value,
                    new_value=new_value,
                    user_id=clean_text(user.get("username")),
                    timestamp=timestamp,
                )
            updates["updated_at"] = timestamp
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values()) + [licitacion_id]
            conn.execute(f"UPDATE licitaciones SET {set_clause} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if row and row["infonalia_dia_id"]:
                if mark_for_nuria:
                    mark_dia_nuria_dirty(conn, int(row["infonalia_dia_id"]))
                refresh_dia_estado(conn, int(row["infonalia_dia_id"]))
        self.send_json(row_to_dict(row))

    def api_delete_licitacion(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return

        try:
            with db_session() as conn:
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if not row:
                    self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                    return
                dia_id = row["infonalia_dia_id"]
                if open_actuaciones_count(conn, [licitacion_id]):
                    self.send_json(
                        {"error": "No se puede borrar la licitación porque tiene actuaciones abiertas."},
                        HTTPStatus.CONFLICT,
                    )
                    return
                delete_licitacion_dependents(conn, [licitacion_id])
                conn.execute("DELETE FROM licitaciones WHERE id = ?", (licitacion_id,))
                if dia_id:
                    mark_dia_nuria_dirty(conn, int(dia_id))
                    refresh_dia_estado(conn, int(dia_id))
        except sqlite3.IntegrityError as exc:
            print(f"No se pudo borrar licitacion {licitacion_id}: {exc}", file=sys.stderr)
            self.send_json(
                {"error": "No se pudo borrar la licitacion por datos relacionados"},
                HTTPStatus.CONFLICT,
            )
            return

        self.send_json({"ok": True})

    def api_delete_dia(self, dia_id: int) -> None:
        if not self.require_admin():
            return

        try:
            with db_session() as conn:
                day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
                if not day:
                    self.send_json({"error": "Dia Infonalia no encontrado"}, HTTPStatus.NOT_FOUND)
                    return

                licitacion_rows = conn.execute(
                    "SELECT id FROM licitaciones WHERE infonalia_dia_id = ?",
                    (dia_id,),
                ).fetchall()
                licitacion_ids = [int(row["id"]) for row in licitacion_rows]

                if open_actuaciones_count(conn, licitacion_ids):
                    self.send_json(
                        {"error": "No se puede borrar el día porque contiene licitaciones con actuaciones abiertas."},
                        HTTPStatus.CONFLICT,
                    )
                    return
                delete_licitacion_dependents(conn, licitacion_ids)
                if licitacion_ids:
                    placeholders = ",".join("?" for _ in licitacion_ids)
                    conn.execute(
                        f"DELETE FROM licitaciones WHERE id IN ({placeholders})",
                        licitacion_ids,
                    )
                conn.execute(
                    "DELETE FROM infonalia_dias WHERE id = ?",
                    (dia_id,),
                )
        except sqlite3.IntegrityError as exc:
            print(f"No se pudo borrar Dia Infonalia {dia_id}: {exc}", file=sys.stderr)
            self.send_json(
                {"error": "No se pudo borrar el Dia Infonalia por datos relacionados"},
                HTTPStatus.CONFLICT,
            )
            return

        self.send_json(
            {
                "ok": True,
                "titulo": clean_text(day["titulo"]),
                "licitaciones_borradas": len(licitacion_ids),
            }
        )

    def send_public_page(self) -> None:
        path = STATIC_ROOT / "public.html"
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")
            return

        private_url = clean_text(os.environ.get("NEXT_PUBLIC_PRIVATE_APP_URL")) or "/login"
        body = path.read_text(encoding="utf-8").replace("__PRIVATE_APP_URL__", html.escape(private_url)).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_security_headers(is_private=False)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, is_private: bool = True) -> None:
        resolved = path.resolve()
        if not str(resolved).startswith(str(STATIC_ROOT.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN, "Acceso no permitido")
            return
        if not resolved.exists() or not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")
            return

        content_type, _ = mimetypes.guess_type(str(resolved))
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_security_headers(is_private=is_private)
        self.send_pending_session_cookie()
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_security_headers(is_private=True)
        self.send_pending_session_cookie()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_security_headers(self, is_private: bool = True) -> None:
        for name, value in build_security_headers(is_private=is_private).items():
            self.send_header(name, value)

    def send_pending_session_cookie(self) -> None:
        cookie = getattr(self, "_pending_session_cookie", None)
        if not cookie:
            return
        self.send_header(
            "Set-Cookie",
            build_session_cookie(
                SESSION_COOKIE,
                cookie,
                max_age=SESSION_MAX_AGE_SECONDS,
                secure=COOKIE_SECURE,
            ),
        )
        self._pending_session_cookie = None

    def redirect(self, location: str, cookie: str | None = None, clear_cookie: bool = False) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_security_headers(is_private=True)
        self.send_header("Location", location)
        if cookie:
            self.send_header(
                "Set-Cookie",
                build_session_cookie(
                    SESSION_COOKIE,
                    cookie,
                    max_age=SESSION_MAX_AGE_SECONDS,
                    secure=COOKIE_SECURE,
                ),
            )
        if clear_cookie:
            self.send_header(
                "Set-Cookie",
                build_clear_cookie(SESSION_COOKIE, secure=COOKIE_SECURE),
            )
        self.end_headers()


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    init_db()
    repaired = repair_internal_download_routes()
    server = ThreadingHTTPServer((host, port), InfonaliaHandler)
    print(f"Infonalia app disponible en http://{host}:{port}")
    print(f"Usuario administrador: {ADMIN_USER}")
    print(f"Usuario de revisión: {REVIEWER_USER}")
    if repaired:
        print(f"Rutas de descarga normalizadas: {repaired}")
    server.serve_forever()


if __name__ == "__main__":
    run(
        host=os.environ.get("INFONALIA_HOST", "127.0.0.1"),
        port=int(os.environ.get("INFONALIA_PORT", "8787")),
    )
