from __future__ import annotations

import hashlib
import html
import json
import logging
import mimetypes
import os
import re
import secrets
import smtplib
import sqlite3
import stat
import subprocess
import sys
import time
from collections.abc import Mapping
from email.message import EmailMessage
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


LOGGER = logging.getLogger(__name__)

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
    from .operational_settings import SETTING_DEFINITIONS, effective_bool, effective_int, effective_setting, effective_text
except ImportError:
    from operational_settings import SETTING_DEFINITIONS, effective_bool, effective_int, effective_setting, effective_text

try:
    from .actuaciones import (
        ACTUACION_ESTADOS,
        ACTUACION_ESTADO_ORDEN,
        ACTUACION_ESTADOS_ABIERTOS,
        ACTUACION_ESTADOS_CERRADOS,
        ACTUACION_TIPOS,
        actuacion_payload,
        actuacion_to_dict,
        clean_value as clean_actuacion_value,
        estado_db_values,
        normalize_actuacion_estado,
        summarize_actuaciones,
        visual_state as actuacion_visual_state,
    )
except ImportError:
    from actuaciones import (
        ACTUACION_ESTADOS,
        ACTUACION_ESTADO_ORDEN,
        ACTUACION_ESTADOS_ABIERTOS,
        ACTUACION_ESTADOS_CERRADOS,
        ACTUACION_TIPOS,
        actuacion_payload,
        actuacion_to_dict,
        clean_value as clean_actuacion_value,
        estado_db_values,
        normalize_actuacion_estado,
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
    from .services.telegram_notifications import (
        DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
        send_telegram_group_message,
        send_telegram_user_message,
        telegram_public_status,
    )
except ImportError:
    from services.telegram_notifications import (
        DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
        send_telegram_group_message,
        send_telegram_user_message,
        telegram_public_status,
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
        ESTADO_OFERTA_ENVIADA,
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
    from .licitacion_publication import (
        TIPO_PUBLICACION_ANUNCIO_PREVIO,
        TIPO_PUBLICACION_LABELS,
        TIPO_PUBLICACION_LICITACION,
        TIPOS_PUBLICACION,
        is_anuncio_previo,
        normalize_tipo_publicacion,
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
        ESTADO_OFERTA_ENVIADA,
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
    from licitacion_publication import (
        TIPO_PUBLICACION_ANUNCIO_PREVIO,
        TIPO_PUBLICACION_LABELS,
        TIPO_PUBLICACION_LICITACION,
        TIPOS_PUBLICACION,
        is_anuncio_previo,
        normalize_tipo_publicacion,
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
    from .multipart_uploads import extract_multipart_fields, extract_multipart_file
except ImportError:
    from multipart_uploads import extract_multipart_fields, extract_multipart_file

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
    from .dropbox_paths import (
        DropboxPathError,
        LicitacionFolderResolution,
        dropbox_base_status,
        folder_status_label,
        path_inside_base,
        preferred_dropbox_base_path,
        resolve_path_inside_base,
        resolve_licitacion_folder,
        stored_folder_path_for_base,
        validate_dropbox_base_path,
    )
except ImportError:
    from dropbox_paths import (
        DropboxPathError,
        LicitacionFolderResolution,
        dropbox_base_status,
        folder_status_label,
        path_inside_base,
        preferred_dropbox_base_path,
        resolve_path_inside_base,
        resolve_licitacion_folder,
        stored_folder_path_for_base,
        validate_dropbox_base_path,
    )

try:
    from .clientes_envios import (
        CLIENTE_ENVIO_ESTADOS,
        CLIENTE_ENVIO_TIPOS,
        create_cliente,
        create_cliente_envio,
        ensure_client_shipments_schema,
        generate_cliente_envio_draft,
        get_cliente,
        get_cliente_envio,
        list_clientes,
        list_cliente_envios,
        list_dropbox_folder_files,
        mark_cliente_envio_sent,
        open_cliente_envio_draft,
        open_cliente_envio_folder,
        update_cliente,
        update_cliente_envio,
    )
except ImportError:
    from clientes_envios import (
        CLIENTE_ENVIO_ESTADOS,
        CLIENTE_ENVIO_TIPOS,
        create_cliente,
        create_cliente_envio,
        ensure_client_shipments_schema,
        generate_cliente_envio_draft,
        get_cliente,
        get_cliente_envio,
        list_clientes,
        list_cliente_envios,
        list_dropbox_folder_files,
        mark_cliente_envio_sent,
        open_cliente_envio_draft,
        open_cliente_envio_folder,
        update_cliente,
        update_cliente_envio,
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
    from .ai_summary_pdf import generate_ai_summary_pdf
except ImportError:
    from ai_summary_pdf import generate_ai_summary_pdf

try:
    from .ai.config import get_ai_config
    from .ai.file_selection import AIFileSelectionError, list_ai_files
    from .ai.notifications import (
        EmailListError,
        create_job_notifications,
        generate_ai_summary_pdf_and_email,
        normalize_email_list,
        notification_status_payload,
    )
    from .ai.service import (
        cancel_ai_job,
        delete_ai_summary,
        dismiss_ai_job,
        dismiss_finished_ai_jobs,
        get_ai_job_payload,
        get_ai_queue_payload,
        get_ai_summary_payload,
        list_ai_jobs,
        mark_stale_ai_jobs,
        request_ai_analysis,
    )
    from .ai.worker_launcher import start_ai_worker_for_job
except ImportError:
    from ai.config import get_ai_config
    from ai.file_selection import AIFileSelectionError, list_ai_files
    from ai.notifications import (
        EmailListError,
        create_job_notifications,
        generate_ai_summary_pdf_and_email,
        normalize_email_list,
        notification_status_payload,
    )
    from ai.service import (
        cancel_ai_job,
        delete_ai_summary,
        dismiss_ai_job,
        dismiss_finished_ai_jobs,
        get_ai_job_payload,
        get_ai_queue_payload,
        get_ai_summary_payload,
        list_ai_jobs,
        mark_stale_ai_jobs,
        request_ai_analysis,
    )
    from ai.worker_launcher import start_ai_worker_for_job

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
    from .email_actions import (
        action_mailbox_cc,
        action_mailbox_to,
        build_infonalia_review_email_html,
        ensure_email_action_schema,
        ensure_review_action_codes,
    )
except ImportError:
    from email_actions import (
        action_mailbox_cc,
        action_mailbox_to,
        build_infonalia_review_email_html,
        ensure_email_action_schema,
        ensure_review_action_codes,
    )

try:
    from .comments import (
        comments_summary_for_entities,
        create_comment,
        create_system_comment,
        delete_comment,
        list_comments,
        recent_comments,
        set_comment_pinned,
        update_comment,
    )
except ImportError:
    from comments import (
        comments_summary_for_entities,
        create_comment,
        create_system_comment,
        delete_comment,
        list_comments,
        recent_comments,
        set_comment_pinned,
        update_comment,
    )

try:
    from .db_migrations import enable_foreign_keys, run_migrations
except ImportError:
    from db_migrations import enable_foreign_keys, run_migrations

try:
    from .justificaciones_baja.application import JustificationApplicationService
    from .justificaciones_baja.application.errors import JustificationApplicationError
    from .justificaciones_baja.imports import ProductImportError, preview_tabular, preview_xlsx
    from .justificaciones_baja.persistence import (
        JustificationNotFoundError,
        JustificationRepository,
    )
    from .justificaciones_baja.documents.filenames import safe_component
except ImportError:
    from justificaciones_baja.application import JustificationApplicationService
    from justificaciones_baja.application.errors import JustificationApplicationError
    from justificaciones_baja.imports import ProductImportError, preview_tabular, preview_xlsx
    from justificaciones_baja.persistence import (
        JustificationNotFoundError,
        JustificationRepository,
    )
    from justificaciones_baja.documents.filenames import safe_component

try:
    from .infonalia_mail_importer import process_mailbox_once as process_infonalia_mailbox_once
except ImportError:
    from infonalia_mail_importer import process_mailbox_once as process_infonalia_mailbox_once

try:
    from .document_tree import build_document_tree_payload
except ImportError:
    from document_tree import build_document_tree_payload

try:
    from .seguimiento_markers import (
        create_follow_marker_for_licitacion,
        create_id_marker_for_licitacion,
        ensure_id_marker,
        get_marker_status_for_licitacion,
        marker_status_for_folder,
        monitor_year_bounds,
        open_licitacion_folder,
        sync_marker_paths,
    )
except ImportError:
    from seguimiento_markers import (
        create_follow_marker_for_licitacion,
        create_id_marker_for_licitacion,
        ensure_id_marker,
        get_marker_status_for_licitacion,
        marker_status_for_folder,
        monitor_year_bounds,
        open_licitacion_folder,
        sync_marker_paths,
    )

try:
    from .monitor.service import MonitorError, run_automation_task, run_monitor
    from .monitor.repository import ensure_monitor_schema, get_monitor_run, list_monitor_runs
    from .monitor.scheduler import monitor_scheduler_status, start_monitor_scheduler, stop_monitor_scheduler
    from .automation_orchestrator import (
        automation_diagnostic,
        automation_runs_payload,
        automation_status_payload,
        automation_tasks_payload,
        run_task as run_internal_automation_task,
        scheduler_tick as run_internal_scheduler_tick,
        set_task_enabled as set_internal_automation_enabled,
        windows_tasks_payload,
    )
except ImportError:
    from monitor.service import MonitorError, run_automation_task, run_monitor
    from monitor.repository import ensure_monitor_schema, get_monitor_run, list_monitor_runs
    from monitor.scheduler import monitor_scheduler_status, start_monitor_scheduler, stop_monitor_scheduler
    from automation_orchestrator import (
        automation_diagnostic,
        automation_runs_payload,
        automation_status_payload,
        automation_tasks_payload,
        run_task as run_internal_automation_task,
        scheduler_tick as run_internal_scheduler_tick,
        set_task_enabled as set_internal_automation_enabled,
        windows_tasks_payload,
    )

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
MONITOR_AGENDA_PENDING_EMAIL_TO = os.environ.get("MONITOR_AGENDA_PENDING_EMAIL_TO", "").strip()
PREPARED_NOTICE_EMAIL_TO = (
    os.environ.get("INFONALIA_PREPARED_NOTICE_EMAIL_TO", "").strip()
    or "info3@llangon.com"
)
TELEGRAM_ENABLED = os.environ.get("LLANGON_TELEGRAM_ENABLED", "0").strip()
TELEGRAM_GROUP_CHAT_ID = os.environ.get("LLANGON_TELEGRAM_GROUP_CHAT_ID", "").strip()
ACTION_MAILBOX_TO = action_mailbox_to()
ACTION_MAILBOX_CC = action_mailbox_cc()
MONITOR_SCHEDULER_ENABLED = os.environ.get("MONITOR_SCHEDULER_ENABLED", "0") == "1"
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
GESTIONADAS_ESTADOS = [
    ESTADO_OFERTA_ENVIADA,
    ESTADO_PREPARADA,
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
    "Preparar",
]

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
    "prepared_notice_email_to": PREPARED_NOTICE_EMAIL_TO,
    "seguimiento_emails": SEGUIMIENTO_EMAILS,
    "monitor_test_email": MONITOR_TEST_EMAIL,
    "monitor_agenda_pending_email_to": MONITOR_AGENDA_PENDING_EMAIL_TO,
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
                tipo_publicacion TEXT NOT NULL DEFAULT 'licitacion',
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
                telegram_chat_id TEXT,
                telegram_notifications_enabled INTEGER NOT NULL DEFAULT 0,
                telegram_last_test_at TEXT,
                telegram_last_error TEXT,
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
        ensure_column(conn, "licitaciones", "tipo_publicacion", "TEXT NOT NULL DEFAULT 'licitacion'")
        ensure_column(conn, "infonalia_dias", "reviewed_at", "TEXT")
        ensure_column(conn, "infonalia_dias", "nuria_dirty_at", "TEXT")
        ensure_column(conn, "notificaciones", "email_sent_at", "TEXT")
        ensure_column(conn, "notificaciones", "email_error", "TEXT")
        ensure_column(conn, "notificaciones", "read_at", "TEXT")
        ensure_column(conn, "usuarios", "email", "TEXT")
        ensure_column(conn, "usuarios", "telegram_chat_id", "TEXT")
        ensure_column(conn, "usuarios", "telegram_notifications_enabled", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "usuarios", "telegram_last_test_at", "TEXT")
        ensure_column(conn, "usuarios", "telegram_last_error", "TEXT")
        ensure_column(conn, "usuarios", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "usuarios", "created_at", "TEXT")
        ensure_column(conn, "usuarios", "updated_at", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_dia ON licitaciones(infonalia_dia_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_estado ON licitaciones(estado)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha_limite ON licitaciones(fecha_limite)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_tipo_publicacion ON licitaciones(tipo_publicacion)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_destino ON notificaciones(usuario_destino)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_fecha ON notificaciones(fecha_hora)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_role ON usuarios(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_noticias_status ON noticias(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_noticias_published ON noticias(published_at)")
        run_migrations(conn)
        ensure_client_shipments_schema(conn)
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
    row_keys = row.keys()
    return {
        "id": row["id"],
        "expediente": row["expediente"] or "",
        "organismo": row["organismo"] or "",
        "objeto": row["objeto"] or "",
        "fecha_limite": row["fecha_limite"] or "",
        "hora_limite": row["hora_limite"] or "",
        "ruta_carpeta": row["ruta_carpeta"] if "ruta_carpeta" in row_keys else "",
        "estado": row["estado"] or "",
        "provincia": row["provincia"] or "",
        "plataforma": row["plataforma"] or "",
        "tipo_publicacion": normalize_tipo_publicacion(row["tipo_publicacion"] if "tipo_publicacion" in row_keys else ""),
    }


def actuacion_licitaciones(conn: sqlite3.Connection, actuacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT l.id, l.expediente, l.organismo, l.objeto, l.fecha_limite, l.hora_limite,
               l.ruta_carpeta,
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
          AND LOWER(a.estado) IN ({estado_placeholders})
        """,
        [*licitacion_ids, *sorted(ACTUACION_ESTADOS_ABIERTOS)],
    ).fetchone()
    return int(row["total"] if row else 0)


def sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def sqlite_delete_if_table(
    conn: sqlite3.Connection,
    table_name: str,
    where_sql: str,
    values: list[object],
) -> int:
    if not sqlite_table_exists(conn, table_name):
        return 0
    cur = conn.execute(f"DELETE FROM {table_name} WHERE {where_sql}", values)
    return int(cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0)


def sqlite_update_if_table(
    conn: sqlite3.Connection,
    table_name: str,
    set_sql: str,
    where_sql: str,
    values: list[object],
) -> int:
    if not sqlite_table_exists(conn, table_name):
        return 0
    cur = conn.execute(f"UPDATE {table_name} SET {set_sql} WHERE {where_sql}", values)
    return int(cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0)


def delete_licitacion_dependents(conn: sqlite3.Connection, licitacion_ids: list[int]) -> None:
    delete_licitacion_dependents_with_counts(conn, licitacion_ids)


def delete_licitacion_dependents_with_counts(conn: sqlite3.Connection, licitacion_ids: list[int]) -> dict[str, int]:
    counts = {
        "storage_uploads": 0,
        "download_jobs": 0,
        "import_results_unlinked": 0,
        "actuacion_licitaciones": 0,
        "licitacion_historial": 0,
        "licitacion_seguimiento_novedades": 0,
        "licitacion_file_inventory": 0,
        "licitacion_path_reconciliation_events_unlinked": 0,
        "ai_usage_log": 0,
        "ai_summaries": 0,
        "ai_analysis_jobs": 0,
        "email_action_codes": 0,
        "email_action_events": 0,
        "comments_deleted": 0,
    }
    if not licitacion_ids:
        return counts
    placeholders = ",".join("?" for _ in licitacion_ids)

    if sqlite_table_exists(conn, "ai_analysis_jobs"):
        job_rows = conn.execute(
            f"SELECT id FROM ai_analysis_jobs WHERE licitacion_id IN ({placeholders})",
            licitacion_ids,
        ).fetchall()
        ai_job_ids = [int(row["id"]) for row in job_rows]
    else:
        ai_job_ids = []
    ai_job_placeholders = ",".join("?" for _ in ai_job_ids)
    if ai_job_ids:
        counts["ai_usage_log"] += sqlite_delete_if_table(
            conn,
            "ai_usage_log",
            f"job_id IN ({ai_job_placeholders})",
            ai_job_ids,
        )
    counts["ai_usage_log"] += sqlite_delete_if_table(
        conn,
        "ai_usage_log",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["ai_summaries"] += sqlite_delete_if_table(
        conn,
        "ai_summaries",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["ai_analysis_jobs"] += sqlite_delete_if_table(
        conn,
        "ai_analysis_jobs",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )

    counts["storage_uploads"] += sqlite_delete_if_table(
        conn,
        "storage_uploads",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["download_jobs"] += sqlite_delete_if_table(
        conn,
        "download_jobs",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )

    counts["import_results_unlinked"] += sqlite_update_if_table(
        conn,
        "import_results",
        "licitacion_id = NULL",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["actuacion_licitaciones"] += sqlite_delete_if_table(
        conn,
        "actuacion_licitaciones",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["licitacion_historial"] += sqlite_delete_if_table(
        conn,
        "licitacion_historial",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["licitacion_seguimiento_novedades"] += sqlite_delete_if_table(
        conn,
        "licitacion_seguimiento_novedades",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["licitacion_file_inventory"] += sqlite_delete_if_table(
        conn,
        "licitacion_file_inventory",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["licitacion_path_reconciliation_events_unlinked"] += sqlite_update_if_table(
        conn,
        "licitacion_path_reconciliation_events",
        "licitacion_id = NULL",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["email_action_events"] += sqlite_delete_if_table(
        conn,
        "email_action_events",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )
    counts["email_action_codes"] += sqlite_delete_if_table(
        conn,
        "email_action_codes",
        f"licitacion_id IN ({placeholders})",
        licitacion_ids,
    )

    timestamp = now_iso()
    counts["comments_deleted"] += sqlite_update_if_table(
        conn,
        "comments",
        "is_deleted = 1, deleted_at = ?, updated_at = ?",
        f"entity_type = 'licitacion' AND entity_id IN ({placeholders}) AND is_deleted = 0",
        [timestamp, timestamp, *licitacion_ids],
    )
    return counts


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
    item = licitation_row_to_dict(
        row,
        detect_platform=detectar_plataforma,
        normalize_url_value=normalize_url,
        normalize_folder_path=folder_path_for_storage,
    )
    resolution = resolve_licitacion_folder(item, dropbox_base=find_dropbox_root())
    item["folder_status"] = {
        **resolution.to_dict(),
        "label": folder_status_label(resolution),
    }
    return item


def ai_summary_indicators(conn: sqlite3.Connection, licitacion_ids: list[int]) -> dict[int, dict[str, object]]:
    if not licitacion_ids:
        return {}
    placeholders = ",".join("?" for _ in licitacion_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT licitacion_id,
                   MAX(id) AS ai_summary_id,
                   MAX(updated_at) AS ai_summary_updated_at
            FROM ai_summaries
            WHERE licitacion_id IN ({placeholders})
              AND COALESCE(summary_json, '') <> ''
              AND COALESCE(summary_json, '') <> '{{}}'
              AND COALESCE(quality_status, '') NOT IN ('empty_analysis', 'low_quality_analysis', 'encoding_error')
            GROUP BY licitacion_id
            """,
            licitacion_ids,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {
        int(row["licitacion_id"]): {
            "has_ai_summary": True,
            "ai_summary_status": "available",
            "ai_summary_id": int(row["ai_summary_id"] or 0),
            "ai_summary_updated_at": row["ai_summary_updated_at"] or "",
        }
        for row in rows
    }


def apply_licitacion_list_metadata(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    licitacion_ids = [int(row["id"]) for row in rows if row.get("id")]
    ai = ai_summary_indicators(conn, licitacion_ids)
    comments = comments_summary_for_entities(conn, [("licitacion", licitacion_id) for licitacion_id in licitacion_ids])
    for row in rows:
        licitacion_id = int(row["id"])
        ai_row = ai.get(licitacion_id, {})
        row["has_ai_summary"] = bool(ai_row.get("has_ai_summary"))
        row["ai_summary_status"] = ai_row.get("ai_summary_status") or ""
        row["ai_summary_id"] = ai_row.get("ai_summary_id") or 0
        row["ai_summary_updated_at"] = ai_row.get("ai_summary_updated_at") or ""
        row["comments_summary"] = comments.get(("licitacion", licitacion_id), {"count": 0, "latest": None, "pinned_count": 0})


def apply_comments_metadata(conn: sqlite3.Connection, items: list[dict[str, object]]) -> None:
    entities: list[tuple[str, int]] = []
    for item in items:
        source_type = clean_text(item.get("source_type") or item.get("type"))
        source_id = item.get("source_id") or item.get("id")
        if source_type == "interno":
            source_type = "agenda_evento"
        if source_type not in {"licitacion", "actuacion", "agenda_evento"}:
            continue
        try:
            entities.append((source_type, int(source_id)))
        except (TypeError, ValueError):
            continue
    summaries = comments_summary_for_entities(conn, entities)
    ai = ai_summary_indicators(conn, [entity_id for entity_type, entity_id in entities if entity_type == "licitacion"])
    for item in items:
        source_type = clean_text(item.get("source_type") or item.get("type"))
        source_id = item.get("source_id") or item.get("id")
        if source_type == "interno":
            source_type = "agenda_evento"
        try:
            entity_id = int(source_id)
        except (TypeError, ValueError):
            continue
        item["comments_summary"] = summaries.get((source_type, entity_id), {"count": 0, "latest": None, "pinned_count": 0})
        if source_type == "licitacion":
            ai_row = ai.get(entity_id, {})
            item["has_ai_summary"] = bool(ai_row.get("has_ai_summary"))
            item["ai_summary_status"] = ai_row.get("ai_summary_status") or ""


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


def update_user_telegram_test_status(
    conn: sqlite3.Connection,
    username: str,
    *,
    tested_at: str | None = None,
    error_message: str = "",
) -> None:
    conn.execute(
        """
        UPDATE usuarios
        SET telegram_last_test_at = ?,
            telegram_last_error = ?,
            updated_at = ?
        WHERE username = ?
        """,
        (tested_at or "", clean_text(error_message), now_iso(), clean_text(username).lower()),
    )


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


def env_enabled(name: str, default: str = "0") -> bool:
    return bool_text(os.environ.get(name, default))


def env_value(name: str, default: str = "") -> str:
    return clean_text(os.environ.get(name, default))


def env_int_value(name: str, default: int) -> int:
    try:
        return int(env_value(name, str(default)) or default)
    except ValueError:
        return default


def configured_flag(name: str) -> bool:
    return bool(env_value(name))


def config_diagnostics_payload(settings: dict[str, str]) -> dict[str, object]:
    action_enabled = effective_bool("email_actions_enabled", settings=settings)
    action_user_configured = bool(effective_text("actions_imap_user", settings=settings))
    action_password_configured = configured_flag("LLANGON_ACTIONS_IMAP_PASSWORD")
    action_allowed_senders = effective_text("action_allowed_senders", settings=settings)
    infonalia_enabled = effective_bool("infonalia_import_enabled", settings=settings)
    infonalia_user_configured = bool(effective_text("actions_imap_user", settings=settings))
    infonalia_password_configured = configured_flag("LLANGON_ACTIONS_IMAP_PASSWORD")
    infonalia_folder = effective_text("infonalia_import_folder", settings=settings)
    infonalia_notify = effective_text("infonalia_import_notify_email", settings=settings)
    return {
        "mailboxes": {
            "email_actions": {
                "enabled": action_enabled,
                "configured": action_enabled
                and action_user_configured
                and action_password_configured
                and bool(effective_text("actions_imap_host", settings=settings))
                and bool(effective_text("actions_imap_folder", settings=settings))
                and bool(action_allowed_senders),
                "folder": effective_text("actions_imap_folder", settings=settings) or "INBOX",
                "user_configured": action_user_configured,
                "password_configured": action_password_configured,
                "allowed_senders": action_allowed_senders or "No configurado",
                "notify_email": effective_text("action_notify_email", settings=settings),
                "mailbox_to": effective_text("action_mailbox_to", settings=settings),
                "mailbox_cc": effective_text("action_mailbox_cc", settings=settings),
                "host": effective_text("actions_imap_host", settings=settings),
                "port": effective_int("actions_imap_port", 993, settings=settings, minimum=1),
                "poll_minutes": effective_int("email_actions_poll_minutes", 10, settings=settings, minimum=1),
                "sources": {
                    key: effective_setting(key, settings=settings)["label"]
                    for key in (
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
                    )
                },
            },
            "infonalia_import": {
                "enabled": infonalia_enabled,
                "configured": infonalia_enabled
                and infonalia_user_configured
                and infonalia_password_configured
                and bool(infonalia_folder)
                and bool(infonalia_notify),
                "folder": infonalia_folder or "LLANGON_INFONALIA",
                "notify_email": infonalia_notify or "info3@llangon.com",
                "poll_minutes": effective_int("infonalia_import_poll_minutes", 30, settings=settings, minimum=1),
                "lookback_hours": effective_int("infonalia_import_lookback_hours", 48, settings=settings, minimum=1),
                "mark_read_on_success": effective_bool("infonalia_import_mark_read_on_success", settings=settings),
                "expected_from": env_value("LLANGON_INFONALIA_IMPORT_FROM", "envios@infonalia.net"),
                "expected_subject": env_value("LLANGON_INFONALIA_IMPORT_SUBJECT"),
                "test_forwarders_configured": configured_flag("LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS"),
                "imap_user_configured": infonalia_user_configured,
                "password_configured": infonalia_password_configured,
                "sources": {
                    key: effective_setting(key, settings=settings)["label"]
                    for key in (
                        "infonalia_import_enabled",
                        "infonalia_import_notify_email",
                        "infonalia_import_folder",
                        "infonalia_import_poll_minutes",
                        "infonalia_import_mark_read_on_success",
                        "infonalia_import_lookback_hours",
                    )
                },
            },
        },
        "automation": {
            "scheduler_enabled": env_enabled("MONITOR_SCHEDULER_ENABLED"),
            "timezone": env_value("MONITOR_SCHEDULER_TIMEZONE", "Europe/Madrid"),
            "poll_minutes": env_int_value("MONITOR_SCHEDULER_POLL_MINUTES", 5),
            "agenda_pending_daily_enabled": env_enabled("MONITOR_AGENDA_PENDING_DAILY_ENABLED", "1"),
            "agenda_pending_daily_time": env_value("MONITOR_AGENDA_PENDING_DAILY_TIME", "08:00"),
            "agenda_pending_weekdays_only": env_enabled("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", "1"),
            "file_inventory_enabled": env_enabled("LLANGON_FILE_INVENTORY_ENABLED"),
            "file_inventory_poll_minutes": env_int_value("LLANGON_FILE_INVENTORY_POLL_MINUTES", 240),
            "file_inventory_reconcile_paths": env_enabled("LLANGON_FILE_INVENTORY_RECONCILE_PATHS", "1"),
            "monitor_licitaciones_schedule_enabled": env_enabled("MONITOR_LICITACIONES_SCHEDULE_ENABLED"),
            "monitor_licitaciones_real_enabled": env_enabled("MONITOR_LICITACIONES_REAL_ENABLED"),
            "full_backup_time": env_value("LLANGON_FULL_BACKUP_TIME", "16:00"),
            "night_suspend_time": env_value("LLANGON_NIGHT_SUSPEND_TIME", "21:00"),
        },
        "advanced": {
            "public_site_url": env_value("LLANGON_PUBLIC_SITE_URL", "https://llangon-web-publica-prueba.web.app/"),
            "host": env_value("INFONALIA_HOST", "127.0.0.1"),
            "port": env_int_value("INFONALIA_PORT", 8787),
            "storage_backend": env_value("INFONALIA_STORAGE_BACKEND", "local"),
            "dropbox_base_configured": configured_flag("LLANGON_DROPBOX_BASE_PATH"),
            "legacy_dropbox_root_configured": configured_flag("INFONALIA_DROPBOX_ROOT"),
            "download_staging_root_configured": configured_flag("INFONALIA_DOWNLOAD_STAGING_ROOT"),
            "runtime_root_configured": configured_flag("LLANGON_RUNTIME_ROOT"),
            "sqlite_backup_dir_configured": configured_flag("LLANGON_SQLITE_BACKUP_DIR"),
            "sqlite_backup_retention": env_int_value("LLANGON_SQLITE_BACKUP_RETENTION", 30),
            "full_backup_enabled": env_enabled("LLANGON_FULL_BACKUP_ENABLED"),
            "full_backup_root_configured": configured_flag("LLANGON_FULL_BACKUP_ROOT"),
            "full_backup_include_env": env_enabled("LLANGON_FULL_BACKUP_INCLUDE_ENV", "1"),
            "full_backup_include_secrets": env_enabled("LLANGON_FULL_BACKUP_INCLUDE_SECRETS", "1"),
            "pending_review": {
                "monitor_test_email": bool(clean_text(settings.get("monitor_test_email")) or MONITOR_TEST_EMAIL),
                "monitor_agenda_pending_email_to": bool(
                    clean_text(settings.get("monitor_agenda_pending_email_to")) or MONITOR_AGENDA_PENDING_EMAIL_TO
                ),
                "infonalia_platform_url": configured_flag("INFONALIA_PLATFORM_URL"),
                "dropbox_api_enabled": env_enabled("INFONALIA_DROPBOX_ENABLED"),
                "review_ai_summary_button": env_enabled("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED"),
            },
        },
    }


def find_dropbox_root() -> Path | None:
    try:
        return validate_dropbox_base_path()
    except DropboxPathError:
        return None


def marker_allowed_roots() -> list[Path]:
    roots: list[Path] = []
    configured = preferred_dropbox_base_path()
    if configured:
        roots.append(configured)
    roots.append(DOWNLOAD_ROOT)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def marker_dropbox_root() -> Path | None:
    configured = preferred_dropbox_base_path()
    if configured:
        return configured if configured.exists() and configured.is_dir() else None
    return None


def download_allowed_destination_roots() -> list[Path]:
    download_root = download_staging_root_for_backend(REPOSITORY_ROOT, DOWNLOAD_ROOT)
    roots = [download_root]
    if not uses_dropbox_api_backend():
        dropbox_root = find_dropbox_root()
        if dropbox_root:
            roots.append(dropbox_root)
    return roots


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
    return stored_folder_path_for_base(value, dropbox_root or find_dropbox_root())


def _path_component_is_link(path: Path) -> bool:
    """Detect links and Windows reparse points without following them.

    ``Path.is_junction`` was added in Python 3.12.  On 3.10/3.11 the
    ``st_file_attributes`` fallback rejects junctions (and other reparse
    points) conservatively instead of silently treating them as directories.
    """
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        try:
            attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
        except FileNotFoundError:
            # Output directories may not exist yet; absence is not a link.
            return False
        reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))
        return bool(attributes & reparse_flag)
    except FileNotFoundError:
        return False
    except (OSError, ValueError, TypeError):
        # Permission/stat failures are unsafe to follow, so fail closed.
        return True


def _ensure_no_link_components(base_path: Path, candidate_path: Path) -> Path:
    """Validate a lexical path below *base_path* before any component is resolved."""
    base = Path(base_path).resolve(strict=True)
    candidate = Path(os.path.abspath(candidate_path))
    try:
        relative = candidate.relative_to(base)
    except ValueError as exc:
        raise DropboxPathError("La ruta queda fuera de la carpeta permitida.") from exc

    current = base
    for part in relative.parts:
        current = current / part
        if _path_component_is_link(current):
            raise DropboxPathError("La ruta contiene un enlace simbólico o unión no permitidos.")
    return candidate


def _resolve_existing_path_without_links(base_path: Path, relative_path: object) -> Path:
    """Resolve an existing relative path while rejecting traversal and link escapes."""
    base = Path(base_path).resolve(strict=True)
    text = str(relative_path or "").strip().strip('"')
    resolve_path_inside_base(base, text)
    parts = [part for part in text.replace("\\", "/").split("/") if part]
    lexical = _ensure_no_link_components(base, base.joinpath(*parts))
    try:
        resolved = lexical.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise DropboxPathError("La ruta seleccionada no existe.") from exc
    if not path_inside_base(resolved, base):
        raise DropboxPathError("La ruta queda fuera de la carpeta permitida.")
    return resolved


def _resolve_licitacion_folder_without_links(
    licitacion: object,
    base_path: Path,
    resolution: LicitacionFolderResolution,
) -> Path:
    """Recover the stored lexical folder before resolving any link component."""

    base = Path(base_path).resolve(strict=True)
    try:
        stored = clean_text(licitacion["ruta_carpeta"]).strip('"')  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        stored = ""
    if not stored:
        raise DropboxPathError("La licitación no tiene una ruta de carpeta válida.")

    raw = Path(stored)
    if raw.is_absolute() or (len(stored) >= 2 and stored[1] == ":"):
        lexical = _ensure_no_link_components(base, raw)
        try:
            resolved = lexical.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise DropboxPathError("La carpeta de la licitación no existe.") from exc
        if not path_inside_base(resolved, base):
            raise DropboxPathError("La carpeta de la licitación queda fuera de Dropbox.")
        return resolved

    # This validates absolute paths, traversal and NULs but its returned path is
    # deliberately ignored because it may already have followed a junction.
    resolve_path_inside_base(base, stored)
    parts = [part for part in stored.replace("\\", "/").split("/") if part]
    direct = _ensure_no_link_components(base, base.joinpath(*parts))
    if direct.exists():
        try:
            return direct.resolve(strict=True)
        except OSError as exc:
            raise DropboxPathError("La carpeta de la licitación no puede resolverse.") from exc

    # Preserve the existing legacy lookup for records stored without their year
    # prefix, while checking every lexical candidate before resolving it.
    legacy_candidates: list[Path] = []
    try:
        year_directories = list(base.iterdir())
    except OSError as exc:
        raise DropboxPathError("No se puede inspeccionar la carpeta base de Dropbox.") from exc
    for year_directory in year_directories:
        if len(year_directory.name) != 4 or not year_directory.name.isdigit():
            continue
        candidate = year_directory.joinpath(*parts)
        if not candidate.exists():
            continue
        legacy_candidates.append(_ensure_no_link_components(base, candidate))
    if len(legacy_candidates) == 1:
        return legacy_candidates[0].resolve(strict=True)

    # Do not fall back to resolution.path: resolve_licitacion_folder currently
    # returns a resolved path, so doing so would lose evidence of a symlink.
    if resolution.exists:
        raise DropboxPathError(
            "La ruta almacenada de la licitación no puede reconstruirse de forma segura."
        )
    raise DropboxPathError("La carpeta de la licitación no existe.")


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
            "tipo_publicacion",
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
    payload["tipo_publicacion"] = normalize_tipo_publicacion(
        payload.get("tipo_publicacion"),
        default=TIPO_PUBLICACION_LICITACION,
    )
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
            elif "resumen del objeto" in lower or "objeto del contrato" in lower or lower in {"objeto", "objeto:"} or lower.startswith("objeto:"):
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


WINDOWS_FOLDER_NAME_INVALID_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def validate_confirmed_download_folder_name(value: object) -> str:
    name = clean_text(value)
    if not name:
        raise DownloadSafetyError("El nombre de carpeta es obligatorio.")
    if len(name) > 140:
        raise DownloadSafetyError("El nombre de carpeta es demasiado largo.")
    if name in {".", ".."} or ".." in name:
        raise DownloadSafetyError("El nombre de carpeta no puede contener '..'.")
    if Path(name).is_absolute() or re.match(r"^[A-Za-z]:", name):
        raise DownloadSafetyError("El nombre de carpeta no puede ser una ruta absoluta.")
    if WINDOWS_FOLDER_NAME_INVALID_RE.search(name):
        raise DownloadSafetyError("El nombre de carpeta contiene caracteres no permitidos.")
    if name.endswith("."):
        raise DownloadSafetyError("El nombre de carpeta no puede terminar en punto.")
    return name


def confirmed_download_destination(default_destination: Path, folder_name: object) -> Path:
    return default_destination.parent / validate_confirmed_download_folder_name(folder_name)


DOWNLOAD_JOB_STATUS_PENDING = "pending"
DOWNLOAD_JOB_STATUS_RUNNING = "running"
DOWNLOAD_JOB_STATUS_COMPLETED = "completed"
DOWNLOAD_JOB_STATUS_FAILED = "failed"

DOWNLOAD_REQUEST_SOURCE_MANUAL = "manual_button"
DOWNLOAD_REQUEST_SOURCE_EMAIL_ACTION = "email_action"

EMAIL_ACTION_DOWNLOAD_REVIEW_CODE = "02"
EMAIL_ACTION_PREPARE_CODE = "03"
EMAIL_ACTION_AI_SUMMARY_CODE = "04"
EMAIL_ACTION_TELEGRAM_CODES = {
    EMAIL_ACTION_DOWNLOAD_REVIEW_CODE,
    EMAIL_ACTION_PREPARE_CODE,
}


def _latest_download_job(conn: sqlite3.Connection, licitacion_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM download_jobs
        WHERE licitacion_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (licitacion_id,),
    ).fetchone()


def _prepare_download_job_request(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    timestamp: str | None = None,
    request_source: str = "",
    request_action: str = "",
    request_message_id: str = "",
    requested_by: str = "",
) -> dict[str, object]:
    created_at = timestamp or now_iso()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        LOGGER.info(
            "Download NO solicitado porque la licitación %s no existe. source=%s action=%s",
            licitacion_id,
            clean_text(request_source),
            clean_text(request_action),
        )
        return {
            "ok": False,
            "status": "error",
            "error_code": "LICITACION_NOT_FOUND",
            "message": "La licitación no existe.",
        }

    latest_job = _latest_download_job(conn, licitacion_id)
    if latest_job and clean_text(latest_job["status"]) in {DOWNLOAD_JOB_STATUS_PENDING, DOWNLOAD_JOB_STATUS_RUNNING}:
        LOGGER.info(
            "Download NO solicitado porque ya existe trabajo pendiente/en curso. licitacion_id=%s source=%s action=%s existing_job_id=%s status=%s",
            licitacion_id,
            clean_text(request_source),
            clean_text(request_action),
            int(latest_job["id"]),
            clean_text(latest_job["status"]),
        )
        return {
            "ok": True,
            "status": "already_pending",
            "created": False,
            "job_id": int(latest_job["id"]),
            "message": "Ya existe una descarga en curso o pendiente para esta licitación.",
        }

    return {
        "ok": True,
        "status": "ready",
        "created": False,
        "job_id": None,
        "message": "Download listo para crear trabajo.",
        "row": row,
    }


def create_download_job_request(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    timestamp: str | None = None,
    request_source: str = "",
    request_action: str = "",
    request_message_id: str = "",
    requested_by: str = "",
) -> dict[str, object]:
    created_at = timestamp or now_iso()
    prepared = _prepare_download_job_request(
        conn,
        licitacion_id,
        timestamp=created_at,
        request_source=request_source,
        request_action=request_action,
        request_message_id=request_message_id,
        requested_by=requested_by,
    )
    if clean_text(prepared.get("status")) != "ready":
        return prepared

    job_id = create_download_job(
        conn,
        licitacion_id,
        timestamp=created_at,
        status=DOWNLOAD_JOB_STATUS_PENDING,
        request_source=request_source,
        request_action=request_action,
        request_message_id=request_message_id,
        requested_by=requested_by,
    )
    record_licitacion_history(
        conn,
        licitacion_id,
        event_type="download_request",
        old_value=request_source,
        new_value=f"job:{job_id} {clean_text(request_action)}".strip(),
        user_id=clean_text(requested_by),
        timestamp=created_at,
    )
    LOGGER.info(
        "Download solicitado por email/manual. licitacion_id=%s source=%s action=%s job_id=%s",
        licitacion_id,
        clean_text(request_source),
        clean_text(request_action),
        job_id,
    )
    return {
        "ok": True,
        "status": "queued",
        "created": True,
        "job_id": job_id,
        "message": "Descarga solicitada y encolada.",
    }


def request_licitacion_download(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    timestamp: str | None = None,
    request_source: str = "",
    request_action: str = "",
    request_message_id: str = "",
    requested_by: str = "",
) -> dict[str, object]:
    try:
        row = conn.execute("SELECT tipo_publicacion FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if row and is_anuncio_previo(row["tipo_publicacion"] if "tipo_publicacion" in row.keys() else ""):
            return {
                "ok": False,
                "status": "skipped",
                "created": False,
                "message": "Los anuncios previos no tienen documentación de licitación para descargar.",
            }
    except sqlite3.OperationalError:
        pass
    return create_download_job_request(
        conn,
        licitacion_id,
        timestamp=timestamp,
        request_source=request_source,
        request_action=request_action,
        request_message_id=request_message_id,
        requested_by=requested_by,
    )


def start_download_worker(*, job_id: int | None = None) -> dict[str, object]:
    command = [sys.executable, "-m", "webapp.infonalia_webapp.download_worker", "--once"]
    if job_id is not None:
        command.extend(["--job-id", str(int(job_id))])
    kwargs: dict[str, object] = {
        "cwd": str(REPOSITORY_ROOT),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        process = subprocess.Popen(command, **kwargs)
    except Exception as exc:
        return {"started": False, "error": str(exc), "command": command}
    return {"started": True, "pid": process.pid, "command": command}


def _preferred_admin_rows_for_telegram(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM usuarios
        WHERE role = 'admin' AND active = 1
        ORDER BY
            CASE
                WHEN LOWER(COALESCE(username, '')) = 'manolo' THEN 0
                ELSE 1
            END,
            LOWER(COALESCE(display_name, username, '')),
            LOWER(COALESCE(username, ''))
        """
    ).fetchall()


def _email_action_deadline_text(row: sqlite3.Row) -> str:
    row_keys = set(row.keys())
    if "fecha_presentacion" in row_keys:
        fecha = format_date_es(row["fecha_presentacion"])
    elif "fecha_limite" in row_keys:
        fecha = format_date_es(row["fecha_limite"])
    else:
        fecha = ""
    if fecha.lower() in {"sin fecha", "fecha no válida", "fecha no valida"}:
        fecha = ""
    hora = clean_text(parse_time_value(row["hora_limite"])) if "hora_limite" in row_keys else ""
    if fecha and hora:
        return f"{fecha} {hora}"
    if fecha:
        return fecha
    if hora:
        return hora
    return "No consta"


def _email_action_folder_name(path_value: object) -> str:
    ruta = clean_text(path_value)
    if not ruta:
        return "no consta"
    parts = [part for part in re.split(r"[\\/]+", ruta) if part]
    if not parts:
        return "no consta"
    return parts[-1]


def _build_email_action_telegram_text(
    *,
    licitacion: sqlite3.Row,
    event: sqlite3.Row,
) -> str:
    licitacion_keys = set(licitacion.keys())
    action_code = clean_text(event["action_code"])
    action_name = clean_text(event["action_name"]) or "Acción por correo"
    if action_code == EMAIL_ACTION_PREPARE_CODE:
        headline = "📄 Licitación lista para preparar ficha"
        detail = "La documentación ya está disponible para preparar la ficha."
    else:
        headline = "✅ Licitación descargada"
        detail = "La licitación se ha descargado correctamente."

    expediente = clean_text(licitacion["expediente"]) or f"Licitación {int(licitacion['id'])}"
    titulo = clean_text(licitacion["titulo"]) if "titulo" in licitacion_keys else ""
    objeto = clean_text(licitacion["objeto"]) if "objeto" in licitacion_keys else ""
    organismo = clean_text(licitacion["organismo"]) if "organismo" in licitacion_keys else ""
    objeto = titulo or objeto or "Sin descripción"
    organismo = organismo or "Sin organismo"
    deadline = _email_action_deadline_text(licitacion)
    carpeta = clean_text(licitacion["ruta_carpeta"]) or "no consta"
    carpeta_nombre = _email_action_folder_name(licitacion["ruta_carpeta"])
    perfil = clean_text(licitacion["enlace_perfil"]) or "Sin enlace"
    estado = clean_text(licitacion["estado"]) or action_name

    return "\n".join(
        [
            headline,
            "",
            f"Nuria ha solicitado: {action_name}",
            "",
            f"Expediente: {expediente}",
            f"Título: {objeto}",
            f"Vencimiento: {deadline}",
            f"Estado actual: {estado}",
            f"Organismo: {organismo}",
            "",
            detail,
            "",
            f"Carpeta: {carpeta_nombre}",
            f"Ruta Dropbox: {carpeta}",
            f"Perfil del contratante: {perfil}",
            "Origen: correo de revisión Infonalia",
        ]
    )


def _deliver_email_action_telegram_notification(
    conn: sqlite3.Connection,
    *,
    text: str,
    licitacion_id: int,
    action_name: str,
) -> dict[str, object]:
    errors: list[str] = []
    for admin_row in _preferred_admin_rows_for_telegram(conn):
        username = clean_text(admin_row["username"])
        result = send_telegram_user_message(admin_row, text, env=os.environ)
        if result.ok:
            LOGGER.info(
                "Telegram email_action enviado al admin. licitacion_id=%s action=%s target=user:%s",
                licitacion_id,
                action_name,
                username,
            )
            return {
                "ok": True,
                "status": "sent_user",
                "target": f"user:{username}",
                "message_id": result.telegram_message_id,
                "error": "",
            }
        errors.append(f"user:{username}:{result.error_code or result.status}")

    group_result = send_telegram_group_message(text, env=os.environ)
    if group_result.ok:
        LOGGER.info(
            "Telegram email_action enviado al grupo. licitacion_id=%s action=%s",
            licitacion_id,
            action_name,
        )
        return {
            "ok": True,
            "status": "sent_group",
            "target": "group",
            "message_id": group_result.telegram_message_id,
            "error": "",
        }

    errors.append(f"group:{group_result.error_code or group_result.status}")
    error_text = "; ".join(error for error in errors if error)[:1000]
    LOGGER.warning(
        "Telegram email_action no enviado. licitacion_id=%s action=%s errors=%s",
        licitacion_id,
        action_name,
        error_text,
    )
    return {
        "ok": False,
        "status": "failed",
        "target": "",
        "message_id": None,
        "error": error_text or clean_text(group_result.error_message) or "No se pudo enviar el aviso de Telegram.",
    }


def _mark_email_action_telegram_result(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    timestamp: str,
    status: str,
    target: str = "",
    error: str = "",
    message_id: object = None,
) -> None:
    conn.execute(
        """
        UPDATE email_action_events
        SET telegram_notification_status = ?,
            telegram_notification_attempted_at = ?,
            telegram_notification_target = ?,
            telegram_notification_error = ?,
            telegram_notification_message_id = ?
        WHERE id = ?
        """,
        (
            clean_text(status),
            timestamp,
            clean_text(target),
            clean_text(error)[:1000],
            clean_text(message_id),
            event_id,
        ),
    )


def notify_pending_email_action_telegram_events(
    *,
    licitacion_id: int,
    download_job_id: int | None = None,
) -> dict[str, object]:
    notified = 0
    failed = 0
    items: list[dict[str, object]] = []
    with db_session() as conn:
        licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not licitacion:
            return {"checked": 0, "sent": 0, "failed": 0, "items": []}
        event_rows = conn.execute(
            """
            SELECT *
            FROM email_action_events
            WHERE licitacion_id = ?
              AND result = 'processed'
              AND action_code IN (?, ?)
              AND COALESCE(telegram_notification_attempted_at, '') = ''
            ORDER BY id ASC
            """,
            (
                licitacion_id,
                EMAIL_ACTION_DOWNLOAD_REVIEW_CODE,
                EMAIL_ACTION_PREPARE_CODE,
            ),
        ).fetchall()
        if not event_rows:
            return {"checked": 0, "sent": 0, "failed": 0, "items": []}

        for event_row in event_rows:
            action_name = clean_text(event_row["action_name"]) or clean_text(event_row["action_code"])
            text = _build_email_action_telegram_text(licitacion=licitacion, event=event_row)
            delivery = _deliver_email_action_telegram_notification(
                conn,
                text=text,
                licitacion_id=licitacion_id,
                action_name=action_name,
            )
            timestamp = now_iso()
            _mark_email_action_telegram_result(
                conn,
                event_id=int(event_row["id"]),
                timestamp=timestamp,
                status=str(delivery.get("status") or "failed"),
                target=str(delivery.get("target") or ""),
                error=str(delivery.get("error") or ""),
                message_id=delivery.get("message_id"),
            )
            items.append(
                {
                    "event_id": int(event_row["id"]),
                    "action_code": clean_text(event_row["action_code"]),
                    "action_name": action_name,
                    "status": clean_text(delivery.get("status")),
                    "target": clean_text(delivery.get("target")),
                }
            )
            if delivery.get("ok"):
                notified += 1
            else:
                failed += 1

    return {
        "checked": len(items),
        "sent": notified,
        "failed": failed,
        "job_id": download_job_id,
        "items": items,
    }


def _download_completed_successfully(http_status: HTTPStatus, payload: dict[str, object]) -> bool:
    if http_status != HTTPStatus.OK or not bool(payload.get("ok")):
        return False
    storage = payload.get("storage")
    if isinstance(storage, dict):
        storage_status = clean_text(storage.get("job_status"))
        if storage_status:
            return storage_status == DOWNLOAD_JOB_STATUS_COMPLETED
    return True


def _email_ai_summary_request_rows_for_download(conn: sqlite3.Connection, download_job_id: int) -> list[sqlite3.Row]:
    ensure_email_action_schema(conn)
    return conn.execute(
        """
        SELECT *
        FROM email_ai_summary_requests
        WHERE download_job_id = ? AND status = 'download_pending'
        ORDER BY id ASC
        """,
        (download_job_id,),
    ).fetchall()


def _update_email_ai_summary_request(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    status: str,
    detail: str,
    ai_job_id: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE email_ai_summary_requests
        SET status = ?, detail = ?, ai_job_id = COALESCE(?, ai_job_id), updated_at = ?
        WHERE id = ?
        """,
        (status, clean_text(detail)[:2000], ai_job_id, now_iso(), request_id),
    )


def _record_email_ai_summary_request_history(
    conn: sqlite3.Connection,
    request: sqlite3.Row,
    *,
    state: str,
    detail: str,
) -> None:
    record_licitacion_history(
        conn,
        int(request["licitacion_id"]),
        event_type="resumen_ia_correo",
        old_value="",
        new_value=f"{state}: {clean_text(detail)[:500]}",
        user_id=clean_text(request["requested_by"]) or "correo_infonalia",
        timestamp=now_iso(),
    )


def mark_email_ai_summary_requests_download_failed(download_job_id: int, error_message: str) -> int:
    """Deja trazada la petición de resumen si su descarga previa no pudo terminar."""
    with db_session() as conn:
        requests = _email_ai_summary_request_rows_for_download(conn, download_job_id)
        for request in requests:
            _update_email_ai_summary_request(
                conn,
                int(request["id"]),
                status="download_failed",
                detail=error_message,
            )
            _record_email_ai_summary_request_history(
                conn,
                request,
                state="descarga_fallida",
                detail=error_message,
            )
        return len(requests)


def start_email_ai_summary_requests_for_download(download_job_id: int) -> dict[str, object]:
    """Encola o entrega los resúmenes IA pedidos desde un correo ya descargado."""
    result: dict[str, object] = {
        "checked": 0,
        "queued": 0,
        "waiting_for_active_job": 0,
        "delivered_existing_summary": 0,
        "skipped": 0,
        "errors": 0,
        "workers": [],
    }
    jobs_to_start: list[int] = []
    with db_session() as conn:
        requests = _email_ai_summary_request_rows_for_download(conn, download_job_id)
        result["checked"] = len(requests)
        for request in requests:
            request_id = int(request["id"])
            licitacion_id = int(request["licitacion_id"])
            recipient = clean_text(request["requested_by"]).lower()
            if not recipient:
                detail = "La orden de resumen IA no contiene un email de destino válido."
                _update_email_ai_summary_request(conn, request_id, status="analysis_skipped", detail=detail)
                _record_email_ai_summary_request_history(conn, request, state="sin_destinatario", detail=detail)
                result["skipped"] = int(result["skipped"]) + 1
                continue
            try:
                payload = request_ai_analysis(
                    conn,
                    licitacion_id,
                    requested_by=recipient,
                    selected_files=None,
                    notify_on_completion=True,
                    notification_emails=[recipient],
                )
            except (AIFileSelectionError, EmailListError, ValueError) as exc:
                detail = f"No se pudo preparar el resumen IA: {exc}"
                _update_email_ai_summary_request(conn, request_id, status="analysis_error", detail=detail)
                _record_email_ai_summary_request_history(conn, request, state="error_preparando_ia", detail=detail)
                result["errors"] = int(result["errors"]) + 1
                continue

            if payload.get("has_summary"):
                try:
                    delivery = generate_ai_summary_pdf_and_email(
                        conn,
                        licitacion_id=licitacion_id,
                        recipients=[recipient],
                        requested_by=recipient,
                        now=now_iso,
                        pdf_output_root=DATA_ROOT / "runtime" / "ai_summary_pdfs",
                    )
                except Exception as exc:
                    detail = f"No se pudo enviar el resumen IA ya disponible: {exc}"
                    _update_email_ai_summary_request(conn, request_id, status="delivery_error", detail=detail)
                    _record_email_ai_summary_request_history(conn, request, state="error_envio_resumen", detail=detail)
                    result["errors"] = int(result["errors"]) + 1
                    continue
                sent = int(delivery.get("sent") or 0)
                errors = int(delivery.get("error") or 0)
                detail = "Resumen IA existente enviado por correo." if sent and not errors else "El resumen IA existente no pudo enviarse por completo."
                _update_email_ai_summary_request(
                    conn,
                    request_id,
                    status="summary_delivered" if sent and not errors else "delivery_error",
                    detail=detail,
                    ai_job_id=int(delivery.get("job_id") or 0) or None,
                )
                _record_email_ai_summary_request_history(
                    conn,
                    request,
                    state="resumen_enviado" if sent and not errors else "error_envio_resumen",
                    detail=detail,
                )
                if sent and not errors:
                    result["delivered_existing_summary"] = int(result["delivered_existing_summary"]) + 1
                else:
                    result["errors"] = int(result["errors"]) + 1
                continue

            job = payload.get("job")
            job = job if isinstance(job, Mapping) else {}
            raw_job_id = payload.get("job_id") or job.get("id")
            try:
                ai_job_id = int(raw_job_id) if raw_job_id is not None else 0
            except (TypeError, ValueError):
                ai_job_id = 0
            if not ai_job_id:
                detail = clean_text(payload.get("motivo_si_no_puede_generar")) or "No hay documentos aptos para generar el resumen IA."
                _update_email_ai_summary_request(conn, request_id, status="analysis_skipped", detail=detail)
                _record_email_ai_summary_request_history(conn, request, state="analisis_no_disponible", detail=detail)
                result["skipped"] = int(result["skipped"]) + 1
                continue

            create_job_notifications(
                conn,
                job_id=ai_job_id,
                licitacion_id=licitacion_id,
                requested_by=recipient,
                recipients=[recipient],
                created_at=now_iso(),
            )
            new_job = bool(payload.get("job_id"))
            detail = "Análisis IA en cola; el resumen se enviará al terminar." if new_job else "La petición se ha añadido a un análisis IA ya en curso."
            _update_email_ai_summary_request(
                conn,
                request_id,
                status="analysis_queued" if new_job else "analysis_waiting",
                detail=detail,
                ai_job_id=ai_job_id,
            )
            _record_email_ai_summary_request_history(
                conn,
                request,
                state="analisis_ia_en_cola" if new_job else "esperando_analisis_ia",
                detail=detail,
            )
            if new_job:
                jobs_to_start.append(ai_job_id)
                result["queued"] = int(result["queued"]) + 1
            else:
                result["waiting_for_active_job"] = int(result["waiting_for_active_job"]) + 1

    for ai_job_id in dict.fromkeys(jobs_to_start):
        with db_session() as conn:
            worker = start_ai_worker_for_job(conn, ai_job_id)
        workers = result["workers"]
        if isinstance(workers, list):
            workers.append({"job_id": ai_job_id, **worker})
    return result


def _finish_failed_download_job(download_job_id: int, error_message: str) -> None:
    with db_session() as conn:
        finish_download_job(
            conn,
            download_job_id,
            status=DOWNLOAD_JOB_STATUS_FAILED,
            error_message=error_message[:2000],
            timestamp=now_iso(),
        )
    mark_email_ai_summary_requests_download_failed(download_job_id, error_message)


def execute_download_for_destination(
    *,
    licitacion_id: int,
    row: sqlite3.Row,
    destino: Path,
    ruta_guardada: str,
    download_job_id: int,
    source_url: str,
) -> tuple[HTTPStatus, dict[str, object]]:
    url = clean_text(source_url)
    destino.mkdir(parents=True, exist_ok=True)
    write_http_url(
        destino,
        url,
        launcher_path=LAUNCHER_PATH,
        python_executable=sys.executable,
    )

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
        _finish_failed_download_job(download_job_id, error_message)
        return (
            HTTPStatus.REQUEST_TIMEOUT,
            {"error": error_message, "carpeta": str(destino), "ruta_carpeta": ruta_guardada},
        )

    output_summary = summarize_process_output(
        completed.stdout,
        completed.stderr,
        MAX_CAPTURED_OUTPUT_CHARS,
    )
    salida = output_summary["combined"]

    if completed.returncode != 0:
        error_message = f"El descargador devolvio codigo {completed.returncode}: {salida}".strip()
        _finish_failed_download_job(download_job_id, error_message)
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "ok": False,
                "codigo": completed.returncode,
                "carpeta": str(destino),
                "ruta_carpeta": ruta_guardada,
                "salida": salida,
                "error": error_message,
            },
        )

    try:
        folder_summary = scan_download_folder(destino)
        validate_download_folder_limits(
            folder_summary,
            max_total_bytes=MAX_DOWNLOAD_TOTAL_BYTES,
            max_file_count=MAX_DOWNLOAD_FILE_COUNT,
        )
        storage_root = storage_root_for_destination(destino, download_allowed_destination_roots())
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
        _finish_failed_download_job(download_job_id, str(exc))
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "ok": False,
                "codigo": completed.returncode,
                "error": str(exc),
                "carpeta": str(destino),
                "ruta_carpeta": ruta_guardada,
                "salida": salida,
            },
        )
    except (LocalStorageError, OSError, StorageConfigurationError, DropboxStorageError) as exc:
        error_message = f"No se pudo confirmar el almacenamiento de descarga: {exc}"
        _finish_failed_download_job(download_job_id, error_message)
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "ok": False,
                "codigo": completed.returncode,
                "error": error_message,
                "carpeta": str(destino),
                "ruta_carpeta": ruta_guardada,
                "salida": salida,
            },
        )

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
    storage_status = str(storage_result.get("job_status") or DOWNLOAD_JOB_STATUS_COMPLETED)
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

    return (
        HTTPStatus.OK,
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
                "mode": storage_result.get("mode"),
                "storage_uri": storage_result.get("storage_uri"),
                "manifest_uri": storage_result.get("manifest_uri"),
                "uploaded_count": storage_result.get("uploaded_count"),
                "skipped_existing_count": storage_result.get("skipped_existing_count"),
                "failed_count": storage_result.get("failed_count"),
                "would_upload_count": storage_result.get("would_upload_count"),
                "no_changes": storage_result.get("no_changes"),
                "warnings": storage_result.get("warnings") or [],
                "errors": storage_result.get("errors") or [],
            },
        },
    )


def process_download_job(job_id: int) -> dict[str, object]:
    base_status = dropbox_base_status()
    if not uses_dropbox_api_backend() and base_status.configured and not base_status.ok:
        _finish_failed_download_job(job_id, base_status.error or "La carpeta base de Dropbox no es válida.")
        return {
            "ok": False,
            "status": "failed",
            "job_id": job_id,
            "message": base_status.error or "La carpeta base de Dropbox no es válida.",
        }
    with db_session() as conn:
        job = conn.execute("SELECT * FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            return {"ok": False, "status": "error", "message": "Trabajo de descarga no encontrado."}
        claimed = conn.execute(
            """
            UPDATE download_jobs
            SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                DOWNLOAD_JOB_STATUS_RUNNING,
                now_iso(),
                now_iso(),
                job_id,
                DOWNLOAD_JOB_STATUS_PENDING,
            ),
        ).rowcount
        if claimed == 0:
            current = conn.execute("SELECT status FROM download_jobs WHERE id = ?", (job_id,)).fetchone()
            return {
                "ok": True,
                "status": "ignored",
                "job_id": job_id,
                "message": f"Trabajo no procesado porque está en estado {clean_text(current['status']) or 'desconocido'}.",
            }
        licitacion_id = int(job["licitacion_id"])
        row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            finish_download_job(
                conn,
                job_id,
                status=DOWNLOAD_JOB_STATUS_FAILED,
                error_message="La licitación asociada ya no existe.",
                timestamp=now_iso(),
            )
            return {"ok": False, "status": "failed", "job_id": job_id, "message": "Licitación asociada no encontrada."}

    url = normalize_url(row["enlace_perfil"])
    if not url:
        _finish_failed_download_job(job_id, "Esta licitación no tiene enlace de perfil.")
        return {"ok": False, "status": "failed", "job_id": job_id, "message": "La licitación no tiene enlace de perfil."}
    try:
        url = validate_download_url(url)
        destino = validate_resolved_destination(resolve_destination_folder(row), download_allowed_destination_roots())
    except DownloadSafetyError as exc:
        _finish_failed_download_job(job_id, str(exc))
        return {"ok": False, "status": "failed", "job_id": job_id, "message": str(exc)}
    if destino.exists() and not destino.is_dir():
        _finish_failed_download_job(job_id, "La ruta de destino existe pero no es una carpeta.")
        return {"ok": False, "status": "failed", "job_id": job_id, "message": "La ruta de destino no es una carpeta."}
    ruta_guardada = folder_path_for_storage(destino)
    http_status, payload = execute_download_for_destination(
        licitacion_id=licitacion_id,
        row=row,
        destino=destino,
        ruta_guardada=ruta_guardada,
        download_job_id=job_id,
        source_url=url,
    )
    if _download_completed_successfully(http_status, payload):
        payload["ai_summary_requests"] = start_email_ai_summary_requests_for_download(job_id)
        payload["telegram_notifications"] = notify_pending_email_action_telegram_events(
            licitacion_id=licitacion_id,
            download_job_id=job_id,
        )
    else:
        payload["ai_summary_requests"] = {
            "download_failed": mark_email_ai_summary_requests_download_failed(
                job_id,
                clean_text(payload.get("error")) or "La descarga necesaria para el resumen IA no pudo completarse.",
            )
        }
    return {"ok": http_status == HTTPStatus.OK, "status": payload.get("ok") and "completed" or "failed", "job_id": job_id, "payload": payload}

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


def send_notification_email(
    usuario_destino: str | None,
    asunto: str,
    cuerpo: str,
    email_recipients: list[str] | None = None,
    html_body: str | None = None,
) -> tuple[str | None, str | None]:
    settings = get_settings()
    recipients = email_recipients if email_recipients is not None else notification_recipients(usuario_destino)
    return send_notification_email_with_settings(
        settings=settings,
        recipients=recipients,
        subject=asunto,
        body=cuerpo,
        html_body=html_body or render_notification_email_html(asunto, cuerpo or asunto, usuario_destino),
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


def split_email_recipients(value: object) -> list[str]:
    recipients: list[str] = []
    for part in re.split(r"[;,\n\r]+", clean_text(value)):
        email = clean_text(part)
        if email and email not in recipients:
            recipients.append(email)
    return recipients


def is_valid_email_address(value: object) -> bool:
    email = clean_text(value)
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def shorten_text(value: object, max_length: int) -> str:
    text = clean_text(value)
    if max_length <= 1 or len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _ai_summary_list(items: object, limit: int = 6) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            text = clean_text(
                item.get("titulo")
                or item.get("nombre")
                or item.get("accion")
                or item.get("detalle")
                or item.get("descripcion")
                or item.get("accion_recomendada")
                or item.get("obligacion")
                or json.dumps(item, ensure_ascii=False)
            )
        else:
            text = clean_text(item)
        if text:
            result.append(text)
    return result


def _ai_summary_sequence(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value:
        return [value]
    return []


def _ai_summary_criteria_items(criteria: object, limit: int = 8) -> list[str]:
    result: list[str] = []
    if isinstance(criteria, dict):
        for label, key in (("Juicio de valor", "juicio_valor"), ("Fórmulas", "formulas")):
            for item in _ai_summary_sequence(criteria.get(key)):
                if isinstance(item, dict):
                    name = clean_text(item.get("nombre") or item.get("descripcion"))
                    points = clean_text(item.get("puntuacion_maxima"))
                    formula = clean_text(item.get("formula"))
                    text = f"{label}: {name}"
                    if points:
                        text += f" ({points} puntos)"
                    if formula:
                        text += f" - {formula}"
                    result.append(text)
                else:
                    result.append(f"{label}: {clean_text(item)}")
    else:
        result.extend(_ai_summary_list(criteria))
    return [item for item in result if item][:limit]


def _ai_summary_operational_items(summary: dict[str, object], limit: int = 8) -> list[str]:
    operations = summary.get("observaciones_operativas") if isinstance(summary, dict) else {}
    if not isinstance(operations, dict):
        return []
    labels = (
        ("Lugar de entrega", "lugar_entrega"),
        ("Horario", "horario_entrega"),
        ("Plazo de entrega", "plazo_entrega"),
        ("Periodicidad", "periodicidad"),
        ("Transporte", "transporte"),
        ("Descarga", "descarga"),
        ("Albaranes", "albaranes"),
        ("Envases/etiquetado", "envases_etiquetado"),
        ("Caducidad/consumo preferente", "caducidad_consumo_preferente"),
    )
    result: list[str] = []
    for label, key in labels:
        value = operations.get(key)
        values = _ai_summary_sequence(value)
        text = "; ".join(clean_text(item) for item in values if clean_text(item))
        if text:
            result.append(f"{label}: {text}")
    return result[:limit]


def ai_summary_email_text(row: sqlite3.Row, summary: dict[str, object]) -> str:
    ejecutivo = summary.get("resumen_ejecutivo") if isinstance(summary, dict) else {}
    metadata = summary.get("metadata") if isinstance(summary, dict) else {}
    caracteristicas = summary.get("caracteristicas") if isinstance(summary, dict) else {}
    presentation = summary.get("presentacion_documentacion") if isinstance(summary, dict) else {}
    if not isinstance(presentation, dict):
        presentation = summary.get("presentacion") if isinstance(summary, dict) else {}
    alertas = _ai_summary_list(summary.get("alertas") if isinstance(summary, dict) else [])
    acciones = _ai_summary_list(summary.get("acciones_recomendadas") if isinstance(summary, dict) else [])
    criterios = _ai_summary_criteria_items(summary.get("criterios_adjudicacion") if isinstance(summary, dict) else [])
    observaciones = _ai_summary_operational_items(summary if isinstance(summary, dict) else {})
    documentos = []
    if isinstance(presentation, dict):
        documentos = _ai_summary_list(
            [
                *_ai_summary_sequence(presentation.get("documentacion_administrativa")),
                *_ai_summary_sequence(presentation.get("documentacion_tecnica")),
                *_ai_summary_sequence(presentation.get("documentacion_economica")),
                *_ai_summary_sequence(presentation.get("anexos_relevantes")),
            ]
        )
    return "\n".join(
        [
            f"Expediente: {clean_text(row['expediente']) or clean_text((metadata or {}).get('expediente'))}",
            f"Objeto: {clean_text(row['objeto'])}",
            f"Fecha límite: {' '.join([format_date_es(row['fecha_limite']) if row['fecha_limite'] else '', clean_text(row['hora_limite'])]).strip()}",
            "",
            clean_text((ejecutivo or {}).get("texto")) or "Sin resumen ejecutivo.",
            "",
            "Datos clave:",
            f"- Tipo: {clean_text((metadata or {}).get('tipo_contrato')) or 'No consta'}",
            f"- Plataforma: {clean_text((metadata or {}).get('plataforma')) or 'No consta'}",
            f"- Presupuesto base: {clean_text((caracteristicas or {}).get('presupuesto_base')) or 'No consta'}",
            f"- Valor estimado: {clean_text((caracteristicas or {}).get('valor_estimado')) or 'No consta'}",
            "",
            "Alertas:",
            *[f"- {item}" for item in alertas],
            "",
            "Acciones recomendadas:",
            *[f"- {item}" for item in acciones],
            "",
            "Criterios:",
            *[f"- {item}" for item in criterios],
            "",
            "Documentación:",
            *[f"- {item}" for item in documentos],
            "",
            "Observaciones operativas:",
            *[f"- {item}" for item in observaciones],
            "",
            "Análisis automático. Revisar contra pliegos.",
        ]
    )


def ai_summary_email_html(row: sqlite3.Row, summary: dict[str, object]) -> str:
    ejecutivo = summary.get("resumen_ejecutivo") if isinstance(summary, dict) else {}
    metadata = summary.get("metadata") if isinstance(summary, dict) else {}
    caracteristicas = summary.get("caracteristicas") if isinstance(summary, dict) else {}
    alertas = _ai_summary_list(summary.get("alertas") if isinstance(summary, dict) else [])
    acciones = _ai_summary_list(summary.get("acciones_recomendadas") if isinstance(summary, dict) else [])
    criterios = _ai_summary_criteria_items(summary.get("criterios_adjudicacion") if isinstance(summary, dict) else [])
    presentation = summary.get("presentacion_documentacion") if isinstance(summary, dict) else {}
    if not isinstance(presentation, dict):
        presentation = summary.get("presentacion") if isinstance(summary, dict) else {}
    documentos = []
    if isinstance(presentation, dict):
        documentos = _ai_summary_list(
            [
                *_ai_summary_sequence(presentation.get("documentacion_administrativa")),
                *_ai_summary_sequence(presentation.get("documentacion_tecnica")),
                *_ai_summary_sequence(presentation.get("documentacion_economica")),
                *_ai_summary_sequence(presentation.get("anexos_relevantes")),
            ]
        )
    observaciones = _ai_summary_operational_items(summary if isinstance(summary, dict) else {})
    fecha_limite = " ".join([format_date_es(row["fecha_limite"]) if row["fecha_limite"] else "", clean_text(row["hora_limite"])]).strip()

    def items_html(values: list[str]) -> str:
        if not values:
            return "<p style='margin:0;color:#667085;'>Sin datos destacados.</p>"
        return "<ul style='margin:8px 0 0 18px;padding:0;'>" + "".join(f"<li>{html.escape(item)}</li>" for item in values) + "</ul>"

    datos_clave = [
        f"Tipo: {clean_text((metadata or {}).get('tipo_contrato')) or 'No consta'}",
        f"Plataforma: {clean_text((metadata or {}).get('plataforma')) or 'No consta'}",
        f"Presupuesto base: {clean_text((caracteristicas or {}).get('presupuesto_base')) or 'No consta'}",
        f"Valor estimado: {clean_text((caracteristicas or {}).get('valor_estimado')) or 'No consta'}",
    ]

    return f"""
    <div style="font-family:Calibri,Arial,sans-serif;color:#172033;background:#f6f8fb;padding:24px;">
      <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #dbe5dc;border-radius:10px;overflow:hidden;">
        <div style="padding:22px 26px;border-left:6px solid #24a324;">
          <p style="margin:0 0 6px;color:#667085;font-size:12px;font-weight:bold;text-transform:uppercase;">Análisis IA documental</p>
          <h1 style="margin:0;font-size:22px;">{html.escape(clean_text(row['expediente']) or 'Licitación')}</h1>
          <p style="margin:10px 0 0;font-size:15px;line-height:1.45;">{html.escape(clean_text(row['objeto']))}</p>
        </div>
        <div style="padding:18px 26px;border-top:1px solid #e6ece8;">
          <p><strong>Fecha límite:</strong> {html.escape(fecha_limite or 'No consta')}</p>
          <h2 style="font-size:16px;">Resumen ejecutivo</h2>
          <p style="line-height:1.55;">{html.escape(clean_text((ejecutivo or {}).get('texto')) or 'Sin resumen ejecutivo.')}</p>
          <h2 style="font-size:16px;">Datos clave</h2>
          {items_html(datos_clave)}
          <h2 style="font-size:16px;">Alertas</h2>
          {items_html(alertas)}
          <h2 style="font-size:16px;">Acciones recomendadas</h2>
          {items_html(acciones)}
          <h2 style="font-size:16px;">Criterios</h2>
          {items_html(criterios)}
          <h2 style="font-size:16px;">Documentación</h2>
          {items_html(documentos)}
          <h2 style="font-size:16px;">Observaciones operativas</h2>
          {items_html(observaciones)}
          <p style="margin-top:22px;padding:12px;background:#fff8dd;border:1px solid #f0d278;border-radius:8px;color:#6f5200;font-weight:bold;">
            Análisis automático. Revisar siempre contra los pliegos antes de usarlo con clientes.
          </p>
        </div>
      </div>
    </div>
    """


def prepared_notice_recipient(settings: dict[str, str] | None = None) -> str:
    settings = settings or get_settings()
    return clean_text(settings.get("prepared_notice_email_to")) or PREPARED_NOTICE_EMAIL_TO


def is_prepared_state_transition(old_estado: object, new_estado: object) -> bool:
    old_normalized = normalize_licitacion_estado(old_estado, default=clean_text(old_estado))
    new_normalized = normalize_licitacion_estado(new_estado, default=clean_text(new_estado))
    return old_normalized != ESTADO_PREPARADA and new_normalized == ESTADO_PREPARADA


def prepared_notice_limit(row: sqlite3.Row) -> str:
    fecha = format_date_es(row["fecha_limite"]) if row["fecha_limite"] else ""
    hora = clean_text(row["hora_limite"])
    if fecha and hora:
        return f"{fecha} {hora}"
    return fecha or "No consta"


def build_prepared_notice_preview(
    row: sqlite3.Row,
    *,
    previous_state: object,
    current_state: object,
    user: dict | None,
    settings: dict[str, str] | None = None,
) -> dict:
    settings = settings or get_settings()
    recipient = prepared_notice_recipient(settings)
    valid_recipient = is_valid_email_address(recipient)
    expediente = clean_text(row["expediente"]) or "Sin expediente"
    titulo = clean_text(row["objeto"]) or "Sin título"
    titulo_corto = shorten_text(titulo, 58)
    subject = shorten_text(f"Ficha preparada — {expediente} — {titulo_corto}", 120)
    ruta = clean_text(row["ruta_carpeta"])
    ruta_line = ruta or "No consta una ruta de Dropbox asociada a esta licitación."
    actor = clean_text((user or {}).get("display_name")) or clean_text((user or {}).get("username")) or "No consta"
    estado_anterior = clean_text(previous_state) or "No consta"
    estado_nuevo = normalize_licitacion_estado(current_state, default=clean_text(current_state)) or ESTADO_PREPARADA
    fecha_limite = prepared_notice_limit(row)
    body = "\n".join(
        [
            f"El estado del expediente {expediente} – {titulo} ha cambiado a {estado_nuevo}.",
            "",
            f"Estado anterior: {estado_anterior}",
            f"Estado nuevo: {estado_nuevo}",
            f"Fecha presentación: {fecha_limite}",
            f"Ruta Dropbox: {ruta_line}",
            f"Cambio realizado por: {actor}",
        ]
    )
    whatsapp_text = "\n".join(
        [
            "Ficha preparada.",
            f"Expediente: {expediente}",
            f"Título: {titulo}",
            f"Estado: {estado_nuevo}",
            f"Ruta Dropbox: {ruta_line}",
        ]
    )
    warning = "" if valid_recipient else "Configura un email válido para poder enviar el aviso."
    if not valid_recipient:
        print(f"Aviso ficha preparada sin destinatario valido para licitacion {row['id']}: {recipient}", file=sys.stderr)
    return {
        "licitacion_id": row["id"],
        "to": recipient,
        "subject": subject,
        "email_body": body,
        "whatsapp_text": whatsapp_text,
        "can_send_email": valid_recipient,
        "email_warning": warning,
    }


def monitor_agenda_pending_recipient(settings: dict[str, str] | None = None) -> str:
    settings = settings or get_settings()
    return clean_text(
        os.environ.get("MONITOR_AGENDA_PENDING_EMAIL_TO")
        or settings.get("monitor_agenda_pending_email_to")
        or monitor_test_recipient(settings=settings)
    )


def send_monitor_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: str,
    *,
    settings: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    recipients = split_email_recipients(recipient)
    return send_notification_email_with_settings(
        settings=settings or get_settings(),
        recipients=recipients,
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
    email_recipients: list[str] | None = None,
    html_body: str | None = None,
) -> int:
    sent_at, email_error = send_notification_email(
        usuario_destino,
        asunto,
        cuerpo,
        email_recipients=email_recipients,
        html_body=html_body,
    )
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

        if path == "/":
            self.redirect("/app" if self.current_user() else "/login")
            return
        if path == "/login":
            self.send_login_page()
            return
        if path == "/logout":
            self.send_json({"error": "Usa POST para cerrar sesión."}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        if path.startswith("/static/"):
            self.send_file(STATIC_ROOT / unquote(path.removeprefix("/static/")), is_private=False)
            return
        if path == "/api/health":
            self.send_json({"status": "ok"})
            return

        if not self.current_user():
            self.redirect("/login")
            return

        if path == "/app" or path.startswith("/app/"):
            self.send_file(STATIC_ROOT / "index.html")
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
        elif path == "/api/comments/recent":
            self.api_recent_comments(parsed.query)
        elif path == "/api/comments":
            self.api_list_comments(parsed.query)
        elif path == "/api/clientes":
            self.api_list_clientes(parsed.query)
        elif path.startswith("/api/clientes/") and path.endswith("/envios"):
            cliente_id = path.removeprefix("/api/clientes/").removesuffix("/envios").strip("/")
            if not cliente_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_list_cliente_envios(parsed.query, cliente_id=int(cliente_id))
        elif path.startswith("/api/clientes/"):
            cliente_id = path.removeprefix("/api/clientes/").strip("/")
            if not cliente_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_cliente(int(cliente_id))
        elif path == "/api/cliente-envios":
            self.api_list_cliente_envios(parsed.query)
        elif path.startswith("/api/cliente-envios/"):
            envio_id = path.removeprefix("/api/cliente-envios/").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_cliente_envio(int(envio_id))
        elif path == "/api/justificaciones-baja":
            self.api_list_justificaciones_baja(parsed.query)
        elif path.startswith("/api/justificaciones-baja/documentos/") and path.endswith("/download"):
            document_id = path.removeprefix("/api/justificaciones-baja/documentos/").removesuffix("/download").strip("/")
            if not document_id.isdigit():
                self.send_json({"error": "Id no válido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_download_justificacion_document(int(document_id))
        elif path.startswith("/api/justificaciones-baja/"):
            justification_id = path.removeprefix("/api/justificaciones-baja/").strip("/")
            if not justification_id.isdigit():
                self.send_json({"error": "Id no válido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_justificacion_baja(int(justification_id))
        elif path == "/api/licitaciones/search":
            self.api_search_licitaciones(parsed.query)
        elif path == "/api/licitaciones":
            self.api_list_licitaciones(parsed.query)
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-files"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-files").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_list_ai_files(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_ai_summary(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/document-tree"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/document-tree").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_document_tree(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/actuaciones"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/actuaciones").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_licitacion_actuaciones(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/cliente-envios"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/cliente-envios").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_list_cliente_envios(parsed.query, licitacion_id=int(licitacion_id))
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
        elif path.startswith("/api/actuaciones/") and path.endswith("/cliente-envios"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/cliente-envios").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_list_cliente_envios(parsed.query, actuacion_id=int(actuacion_id))
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
        elif path == "/api/admin/automation/status":
            self.api_admin_automation_status()
        elif path == "/api/admin/automation/tasks":
            self.api_admin_automation_tasks()
        elif path.startswith("/api/admin/automation/tasks/"):
            task_key = unquote(path.removeprefix("/api/admin/automation/tasks/").strip("/"))
            self.api_admin_automation_task(task_key)
        elif path == "/api/admin/automation/runs":
            self.api_admin_automation_runs(parsed.query)
        elif path == "/api/admin/automation/diagnostic":
            self.api_admin_automation_diagnostic()
        elif path == "/api/admin/automation/windows-tasks":
            self.api_admin_automation_windows_tasks()
        elif path == "/api/monitor/runs":
            self.api_monitor_runs(parsed.query)
        elif path in {"/api/monitor/scheduler", "/api/monitor/scheduler/status"}:
            self.api_monitor_scheduler_status()
        elif path.startswith("/api/monitor/runs/"):
            run_id = path.removeprefix("/api/monitor/runs/").strip("/")
            if not run_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_monitor_run_detail(int(run_id))
        elif path == "/api/ai/queue":
            self.api_ai_queue()
        elif path == "/api/ai/jobs":
            self.api_list_ai_jobs()
        elif path.startswith("/api/ai/jobs/"):
            job_id = path.removeprefix("/api/ai/jobs/").strip("/")
            if not job_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_get_ai_job(int(job_id))
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

        if path == "/api/justificaciones-baja" or path.startswith("/api/justificaciones-baja/"):
            self.api_post_justificacion_baja(path)
        elif path == "/api/licitaciones":
            self.api_create_licitacion()
        elif path == "/api/comments":
            self.api_create_comment()
        elif path.startswith("/api/comments/") and path.endswith("/pin"):
            comment_id = path.removeprefix("/api/comments/").removesuffix("/pin").strip("/")
            if not comment_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_pin_comment(int(comment_id), True)
        elif path.startswith("/api/comments/") and path.endswith("/unpin"):
            comment_id = path.removeprefix("/api/comments/").removesuffix("/unpin").strip("/")
            if not comment_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_pin_comment(int(comment_id), False)
        elif path == "/api/licitaciones/capture":
            self.api_capture_licitacion()
        elif path == "/api/config/users":
            self.api_create_user()
        elif path == "/api/config/test-smtp":
            self.api_test_smtp()
        elif path == "/api/clientes":
            self.api_create_cliente()
        elif path == "/api/cliente-envios":
            self.api_create_cliente_envio()
        elif path == "/api/cliente-envios/folder-files":
            self.api_cliente_envio_folder_files()
        elif path == "/api/admin/telegram/test-group":
            self.api_test_telegram_group()
        elif path.startswith("/api/admin/users/") and path.endswith("/telegram/test"):
            user_key = unquote(path.removeprefix("/api/admin/users/").removesuffix("/telegram/test").strip("/"))
            self.api_test_telegram_user(user_key)
        elif path == "/api/storage/dropbox/test":
            self.api_storage_dropbox_test()
        elif path == "/api/storage/dropbox/dry-run":
            self.api_storage_dropbox_dry_run()
        elif path == "/api/storage/markers/sync":
            self.api_storage_markers_sync()
        elif path.startswith("/api/admin/automation/tasks/") and path.endswith("/run"):
            task_key = unquote(path.removeprefix("/api/admin/automation/tasks/").removesuffix("/run").strip("/"))
            self.api_admin_automation_run_task(task_key)
        elif path.startswith("/api/admin/automation/tasks/") and path.endswith("/enable"):
            task_key = unquote(path.removeprefix("/api/admin/automation/tasks/").removesuffix("/enable").strip("/"))
            self.api_admin_automation_set_enabled(task_key, True)
        elif path.startswith("/api/admin/automation/tasks/") and path.endswith("/disable"):
            task_key = unquote(path.removeprefix("/api/admin/automation/tasks/").removesuffix("/disable").strip("/"))
            self.api_admin_automation_set_enabled(task_key, False)
        elif path == "/api/admin/automation/tick":
            self.api_admin_automation_tick()
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
        elif path == "/api/import/infonalia-mail/run-now":
            self.api_import_infonalia_mail_run_now()
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
        elif path.startswith("/api/licitaciones/") and path.endswith("/markers/id"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/markers/id").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_create_licitacion_marker(int(licitacion_id), marker_type="id")
        elif path.startswith("/api/licitaciones/") and path.endswith("/markers/follow"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/markers/follow").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_create_licitacion_marker(int(licitacion_id), marker_type="follow")
        elif path.startswith("/api/licitaciones/") and path.endswith("/open-folder"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/open-folder").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_open_licitacion_folder(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary/generate"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary/generate").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_generate_ai_summary(int(licitacion_id), force=False)
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary/regenerate"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary/regenerate").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_generate_ai_summary(int(licitacion_id), force=True)
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary/email"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary/email").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_send_ai_summary_email(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary/save-pdf"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary/save-pdf").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_save_ai_summary_pdf(int(licitacion_id))
        elif path == "/api/ai/jobs/mark-stale":
            self.api_mark_stale_ai_jobs()
        elif path == "/api/ai/queue/dismiss-finished":
            self.api_dismiss_finished_ai_jobs()
        elif path.startswith("/api/ai/jobs/") and path.endswith("/cancel"):
            job_id = path.removeprefix("/api/ai/jobs/").removesuffix("/cancel").strip("/")
            if not job_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_cancel_ai_job(int(job_id))
        elif path.startswith("/api/ai/jobs/") and path.endswith("/dismiss"):
            job_id = path.removeprefix("/api/ai/jobs/").removesuffix("/dismiss").strip("/")
            if not job_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_dismiss_ai_job(int(job_id))
        elif path.startswith("/api/ai/jobs/") and path.endswith("/start"):
            job_id = path.removeprefix("/api/ai/jobs/").removesuffix("/start").strip("/")
            if not job_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_start_ai_job(int(job_id))
        elif path.startswith("/api/ai/jobs/") and path.endswith("/run"):
            job_id = path.removeprefix("/api/ai/jobs/").removesuffix("/run").strip("/")
            if not job_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_start_ai_job(int(job_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ia-preview/email"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ia-preview/email").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_send_ai_preview_email(int(licitacion_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/prepared-notice/email"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/prepared-notice/email").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_send_prepared_notice_email(int(licitacion_id))
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
        elif path.startswith("/api/licitaciones/") and path.endswith("/cliente-envios"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/cliente-envios").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_create_cliente_envio(default_licitacion_id=int(licitacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/cliente-envios"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/cliente-envios").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_create_cliente_envio(default_actuacion_id=int(actuacion_id))
        elif path.startswith("/api/actuaciones/") and path.endswith("/historial"):
            actuacion_id = path.removeprefix("/api/actuaciones/").removesuffix("/historial").strip("/")
            if not actuacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_add_actuacion_historial(int(actuacion_id))
        elif path.startswith("/api/cliente-envios/") and path.endswith("/generate-draft"):
            envio_id = path.removeprefix("/api/cliente-envios/").removesuffix("/generate-draft").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_generate_cliente_envio_draft(int(envio_id))
        elif path.startswith("/api/cliente-envios/") and path.endswith("/mark-sent"):
            envio_id = path.removeprefix("/api/cliente-envios/").removesuffix("/mark-sent").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_mark_cliente_envio_sent(int(envio_id))
        elif path.startswith("/api/cliente-envios/") and path.endswith("/open-folder"):
            envio_id = path.removeprefix("/api/cliente-envios/").removesuffix("/open-folder").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_open_cliente_envio_folder(int(envio_id))
        elif path.startswith("/api/cliente-envios/") and path.endswith("/open-draft"):
            envio_id = path.removeprefix("/api/cliente-envios/").removesuffix("/open-draft").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_open_cliente_envio_draft(int(envio_id))
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

        if path.startswith("/api/justificaciones-baja/"):
            justification_id = path.removeprefix("/api/justificaciones-baja/").strip("/")
            if not justification_id.isdigit():
                self.send_json({"error": "Id no válido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_justificacion_baja(int(justification_id))
        elif path.startswith("/api/comments/"):
            comment_id = path.removeprefix("/api/comments/").strip("/")
            if not comment_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_comment(int(comment_id))
        elif path.startswith("/api/clientes/"):
            cliente_id = path.removeprefix("/api/clientes/").strip("/")
            if not cliente_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_cliente(int(cliente_id))
        elif path.startswith("/api/cliente-envios/"):
            envio_id = path.removeprefix("/api/cliente-envios/").strip("/")
            if not envio_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_update_cliente_envio(int(envio_id))
        elif path.startswith("/api/agenda/eventos/"):
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

        if path.startswith("/api/comments/"):
            comment_id = path.removeprefix("/api/comments/").strip("/")
            if not comment_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_delete_comment(int(comment_id))
        elif path.startswith("/api/licitaciones/") and path.endswith("/ai-summary"):
            licitacion_id = path.removeprefix("/api/licitaciones/").removesuffix("/ai-summary").strip("/")
            if not licitacion_id.isdigit():
                self.send_json({"error": "Id no valido"}, HTTPStatus.BAD_REQUEST)
                return
            self.api_delete_ai_summary(int(licitacion_id))
        elif path.startswith("/api/licitaciones/"):
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
            if path == "/api/justificaciones-baja" or path.startswith("/api/justificaciones-baja/"):
                return True
            if path in {
                "/api/licitaciones",
                "/api/licitaciones/capture",
                "/api/actuaciones",
                "/api/clientes",
                "/api/cliente-envios",
                "/api/cliente-envios/folder-files",
                "/api/agenda/email-summary",
                "/api/agenda/eventos",
                "/api/config/users",
                "/api/config/test-smtp",
                "/api/admin/telegram/test-group",
                "/api/admin/automation/tick",
                "/api/storage/dropbox/test",
                "/api/storage/dropbox/dry-run",
                "/api/storage/markers/sync",
                "/api/monitor/run",
                "/api/news",
                "/api/import/csv",
                "/api/import/msg",
                "/api/import/infonalia-mail/run-now",
                "/api/comments",
            }:
                return True
            if path.startswith("/api/comments/") and (
                path.endswith("/pin")
                or path.endswith("/unpin")
            ):
                return True
            if path.startswith("/api/admin/users/") and path.endswith("/telegram/test"):
                return True
            if path.startswith("/api/admin/automation/tasks/") and (
                path.endswith("/run")
                or path.endswith("/enable")
                or path.endswith("/disable")
            ):
                return True
            if path.startswith("/api/dias/") and (
                path.endswith("/revisado")
                or path.endswith("/enviar-nuria")
                or path.endswith("/desmarcar-revisado")
            ):
                return True
            if path.startswith("/api/licitaciones/") and (
                path.endswith("/descargar")
                or path.endswith("/markers/id")
                or path.endswith("/markers/follow")
                or path.endswith("/open-folder")
                or path.endswith("/ai-summary/generate")
                or path.endswith("/ai-summary/regenerate")
                or path.endswith("/ai-summary/email")
                or path.endswith("/ai-summary/save-pdf")
                or path.endswith("/ia-preview")
                or path.endswith("/ia-preview/email")
                or path.endswith("/prepared-notice/email")
                or path.endswith("/actuaciones")
                or path.endswith("/cliente-envios")
            ):
                return True
            if path.startswith("/api/actuaciones/") and path.endswith("/cliente-envios"):
                return True
            if path.startswith("/api/cliente-envios/") and (
                path.endswith("/generate-draft")
                or path.endswith("/mark-sent")
                or path.endswith("/open-folder")
                or path.endswith("/open-draft")
            ):
                return True
            if path == "/api/ai/jobs/mark-stale":
                return True
            if path == "/api/ai/queue/dismiss-finished":
                return True
            if path.startswith("/api/ai/jobs/") and (
                path.endswith("/run")
                or path.endswith("/start")
                or path.endswith("/cancel")
                or path.endswith("/dismiss")
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
                path.startswith("/api/justificaciones-baja/")
                or path.startswith("/api/comments/")
                or path.startswith("/api/clientes/")
                or path.startswith("/api/cliente-envios/")
                or path.startswith("/api/agenda/eventos/")
                or path.startswith("/api/actuaciones/")
                or path.startswith("/api/licitaciones/")
                or path.startswith("/api/config/users/")
                or path == "/api/config/settings"
                or path.startswith("/api/news/")
            )
        if method == "DELETE":
            return (
                path.startswith("/api/comments/")
                or path.startswith("/api/licitaciones/")
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
                "email": user.get("email", ""),
                "csrf_token": user.get("csrf_token", ""),
                "maintenance_mode": maintenance_mode_enabled(),
                "labels": ESTADO_LABELS,
                "nuria_estados": NURIA_ESTADOS,
            }
        )

    def config_payload(self) -> dict:
        settings = get_settings()
        payload = settings_config_payload(list_user_records(active_only=False), settings)
        reviewer = get_user_record(REVIEWER_USER) or {}
        default_review_email = clean_text(reviewer.get("email")) or REVIEWER_EMAIL or PREPARED_NOTICE_EMAIL_TO
        payload["settings"]["nuria_review_email_to"] = default_review_email
        payload["telegram"] = telegram_public_status(os.environ)
        payload["ai"] = get_ai_config().public_status()
        payload["ai"]["gemini_api_key_set"] = configured_flag("GEMINI_API_KEY")
        payload["settings_sources"] = {
            key: effective_setting(key, settings=settings)["label"] for key in SETTING_DEFINITIONS
        }
        payload["diagnostics"] = config_diagnostics_payload(settings)
        return payload

    def api_get_config(self) -> None:
        if not self.require_admin():
            return
        self.send_json(self.config_payload())

    def api_storage_status(self) -> None:
        if not self.require_admin():
            return
        try:
            payload = storage_status_payload()
            base_status = dropbox_base_status()
            dropbox_root = find_dropbox_root()
            local_download_root = base_status.path if base_status.configured else str(DOWNLOAD_ROOT)
            if dropbox_root:
                if base_status.source == "legacy":
                    local_flow_label = "Dropbox Desktop (fallback / legado)"
                else:
                    local_flow_label = "Dropbox Desktop (LLANGON_DROPBOX_BASE_PATH)"
            elif base_status.configured and base_status.source == "env":
                local_flow_label = "Dropbox Desktop (ruta no encontrada)"
            else:
                local_flow_label = "carpeta local interna"
            payload.update(
                {
                    "local_download_root": str(local_download_root),
                    "dropbox_base": base_status.to_dict(),
                    "dropbox_desktop_detected": bool(dropbox_root),
                    "dropbox_desktop_root": str(dropbox_root) if dropbox_root else "",
                    "local_flow_label": local_flow_label,
                    "monitor_year_min": MONITOR_YEAR_MIN,
                    "monitor_year_max": MONITOR_YEAR_MAX,
                }
            )
            self.send_json(payload)
        except StorageConfigurationError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def send_comment_error(self, exc: Exception) -> None:
        if isinstance(exc, LookupError):
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if isinstance(exc, PermissionError):
            self.send_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
            return
        if isinstance(exc, (ValueError, json.JSONDecodeError)):
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        raise exc

    def api_list_comments(self, query: str) -> None:
        params = parse_qs(query)
        entity_type = params.get("entity_type", [""])[0]
        entity_id = params.get("entity_id", [""])[0]
        user = self.current_user() or {}
        try:
            with db_session() as conn:
                items = list_comments(conn, entity_type=entity_type, entity_id=entity_id, user=user)
                summary = comments_summary_for_entities(conn, [(clean_text(entity_type).lower(), int(entity_id))])
        except Exception as exc:
            self.send_comment_error(exc)
            return
        self.send_json(
            {
                "items": items,
                "summary": summary.get((clean_text(entity_type).lower(), int(entity_id)), {"count": 0, "latest": None, "pinned_count": 0}),
            }
        )

    def api_recent_comments(self, query: str) -> None:
        params = parse_qs(query)
        try:
            limit = int(params.get("limit", ["20"])[0])
        except ValueError:
            limit = 20
        with db_session() as conn:
            items = recent_comments(conn, limit=limit)
        self.send_json({"items": items})

    def api_create_comment(self) -> None:
        user = self.current_user() or {}
        try:
            data = self.read_json()
            with db_session() as conn:
                item = create_comment(
                    conn,
                    entity_type=data.get("entity_type"),
                    entity_id=data.get("entity_id"),
                    body=data.get("body"),
                    visibility=data.get("visibility", "internal"),
                    user=user,
                )
        except Exception as exc:
            self.send_comment_error(exc)
            return
        self.send_json({"ok": True, "comment": item}, HTTPStatus.CREATED)

    def api_update_comment(self, comment_id: int) -> None:
        user = self.current_user() or {}
        try:
            data = self.read_json()
            with db_session() as conn:
                item = update_comment(conn, comment_id=comment_id, body=data.get("body"), user=user)
        except Exception as exc:
            self.send_comment_error(exc)
            return
        self.send_json({"ok": True, "comment": item})

    def api_delete_comment(self, comment_id: int) -> None:
        user = self.current_user() or {}
        try:
            with db_session() as conn:
                item = delete_comment(conn, comment_id=comment_id, user=user)
        except Exception as exc:
            self.send_comment_error(exc)
            return
        self.send_json({"ok": True, "comment": item})

    def api_pin_comment(self, comment_id: int, pinned: bool) -> None:
        user = self.current_user() or {}
        try:
            with db_session() as conn:
                item = set_comment_pinned(conn, comment_id=comment_id, pinned=pinned, user=user)
        except Exception as exc:
            self.send_comment_error(exc)
            return
        self.send_json({"ok": True, "comment": item})

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
        if task_type == "agenda_diaria":
            task_type = "agenda_pendientes_diaria"
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
                recipient = (
                    monitor_agenda_pending_recipient(settings)
                    if task_type == "agenda_pendientes_diaria"
                    else monitor_test_recipient(self.current_user(), settings)
                )
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

    def api_admin_automation_status(self) -> None:
        if not self.require_admin():
            return
        self.send_json(automation_status_payload(db_path=DB_PATH))

    def api_admin_automation_tasks(self) -> None:
        if not self.require_admin():
            return
        self.send_json({"items": automation_tasks_payload(db_path=DB_PATH)})

    def api_admin_automation_task(self, task_key: str) -> None:
        if not self.require_admin():
            return
        clean_key = clean_text(task_key)
        tasks = automation_tasks_payload(db_path=DB_PATH)
        item = next((task for task in tasks if task.get("key") == clean_key), None)
        if not item:
            self.send_json({"error": "Automatización no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"item": item})

    def api_admin_automation_runs(self, query: str) -> None:
        if not self.require_admin():
            return
        params = parse_qs(query)
        try:
            limit = int(params.get("limit", ["100"])[0])
        except ValueError:
            limit = 100
        self.send_json({
            "items": automation_runs_payload(
                db_path=DB_PATH,
                task_key=clean_text(params.get("task_key", [""])[0]),
                status=clean_text(params.get("status", [""])[0]),
                limit=limit,
            )
        })

    def api_admin_automation_diagnostic(self) -> None:
        if not self.require_admin():
            return
        self.send_json({"diagnostic": automation_diagnostic(db_path=DB_PATH)})

    def api_admin_automation_windows_tasks(self) -> None:
        if not self.require_admin():
            return
        self.send_json(windows_tasks_payload())

    def api_admin_automation_run_task(self, task_key: str) -> None:
        if not self.require_admin():
            return
        try:
            result = run_internal_automation_task(
                clean_text(task_key),
                db_path=DB_PATH,
                source="manual",
                triggered_by=clean_text((self.current_user() or {}).get("username")),
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"ok": result.get("status") != "failed", **result})

    def api_admin_automation_set_enabled(self, task_key: str, enabled: bool) -> None:
        if not self.require_admin():
            return
        try:
            item = set_internal_automation_enabled(
                clean_text(task_key),
                enabled,
                db_path=DB_PATH,
                updated_by=clean_text((self.current_user() or {}).get("username")),
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"ok": True, "item": item})

    def api_admin_automation_tick(self) -> None:
        if not self.require_admin():
            return
        result = run_internal_scheduler_tick(
            db_path=DB_PATH,
            source="manual",
            triggered_by=clean_text((self.current_user() or {}).get("username")),
        )
        self.send_json(result)

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

    def api_monitor_scheduler_status(self) -> None:
        if not self.require_admin():
            return
        self.send_json({"scheduler": monitor_scheduler_status(DB_PATH)})

    def require_news_manager(self) -> bool:
        user = self.current_user()
        if user and user.get("role") in {"admin", "editor"}:
            return True
        self.send_json({"error": "No tienes permiso para gestionar noticias."}, HTTPStatus.FORBIDDEN)
        return False

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
                        telegram_chat_id,
                        telegram_notifications_enabled,
                        telegram_last_test_at,
                        telegram_last_error,
                        active,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["username"],
                        hash_password(payload["password"]),
                        payload["role"],
                        payload["display_name"],
                        payload["email"],
                        payload["telegram_chat_id"],
                        payload["telegram_notifications_enabled"],
                        "",
                        "",
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
            updates = settings_update_payload(data, current_settings=get_settings(), environ=os.environ)
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

    def api_test_telegram_group(self) -> None:
        if not self.require_admin():
            return

        user = self.current_user() or {}
        username = clean_text(user.get("username")) or "admin"
        display_name = clean_text(user.get("display_name")) or username or "Administrador"
        message = (
            "🔔 Prueba de Telegram - Llangon Suite\n\n"
            "La suite ha enviado correctamente un aviso al grupo general configurado.\n\n"
            "Destino: grupo general de avisos\n"
            "Origen: panel de administración/configuración\n"
            f"Usuario: {display_name}\n"
            f"Fecha/hora: {format_datetime_es(now_iso())}"
        )
        LOGGER.info("Telegram test requested for general group by %s", username)
        result = send_telegram_group_message(
            message,
            env=os.environ,
            timeout_seconds=DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
        )
        status = HTTPStatus.OK if result.ok else (
            HTTPStatus.BAD_REQUEST if result.status != "disabled" else HTTPStatus.OK
        )
        self.send_json(result.to_dict(), status)

    def api_test_telegram_user(self, user_key: str) -> None:
        if not self.require_admin():
            return

        username = clean_text(user_key).lower()
        if not username:
            self.send_json({"ok": False, "error": "Usuario no encontrado."}, HTTPStatus.NOT_FOUND)
            return

        admin = self.current_user() or {}
        admin_name = clean_text(admin.get("display_name")) or clean_text(admin.get("username")) or "Administrador"
        user = get_user_record(username)
        if not user:
            self.send_json({"ok": False, "error": "Usuario no encontrado."}, HTTPStatus.NOT_FOUND)
            return

        message = (
            "🔔 Prueba privada de Telegram - Llangon Suite\n\n"
            "La suite ha enviado correctamente un aviso privado a tu cuenta de Telegram.\n\n"
            "Destino: usuario configurado\n"
            "Origen: panel de administración/configuración\n"
            f"Solicitado por: {admin_name}\n"
            f"Fecha/hora: {format_datetime_es(now_iso())}"
        )
        LOGGER.info("Telegram test requested for user %s by %s", username, clean_text(admin.get("username")) or "admin")
        result = send_telegram_user_message(
            user,
            message,
            env=os.environ,
            timeout_seconds=DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
        )
        timestamp = now_iso() if result.ok else ""
        with db_session() as conn:
            update_user_telegram_test_status(
                conn,
                username,
                tested_at=timestamp,
                error_message="" if result.ok else result.error_message or result.message,
            )
        status = HTTPStatus.OK if result.ok else (
            HTTPStatus.BAD_REQUEST if result.status != "disabled" else HTTPStatus.OK
        )
        payload = result.to_dict()
        payload["user"] = get_user_record(username)
        self.send_json(payload, status)

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
            comments = comments_summary_for_entities(conn, [("infonalia_dia", int(item["id"])) for item in items])
            for item in items:
                item["comments_summary"] = comments.get(
                    ("infonalia_dia", int(item["id"])),
                    {"count": 0, "latest": None, "pinned_count": 0},
                )
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
            apply_comments_metadata(conn, response.get("events") or [])
            for group_items in (response.get("groups") or {}).values():
                apply_comments_metadata(conn, group_items)
        self.send_json(response)

    def api_agenda_pending_tasks(self, query: str) -> None:
        user = self.current_user() or {}
        if user.get("role") not in {"admin", "nuria"}:
            self.send_json({"error": "No tienes permiso para esta accion."}, HTTPStatus.FORBIDDEN)
            return
        params = parse_qs(query)
        search = clean_text(params.get("q", [""])[0])
        with db_session() as conn:
            response = build_pending_tasks_response(conn, query=search)
            apply_comments_metadata(conn, response.get("items") or [])
        self.send_json(response)

    def api_list_clientes(self, query: str) -> None:
        params = parse_qs(query)
        search = clean_text(params.get("q", [""])[0])
        with db_session() as conn:
            items = list_clientes(conn, search=search)
        self.send_json({"items": items})

    def api_get_cliente(self, cliente_id: int) -> None:
        with db_session() as conn:
            item = get_cliente(conn, cliente_id)
        if not item:
            self.send_json({"error": "Cliente no encontrado"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"item": item})

    def api_create_cliente(self) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            try:
                item = create_cliente(conn, data, user_id=user.get("username"), timestamp=now_iso())
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_update_cliente(self, cliente_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            try:
                item = update_cliente(conn, cliente_id, data, user_id=user.get("username"), timestamp=now_iso())
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item})

    def api_list_cliente_envios(
        self,
        query: str,
        *,
        cliente_id: int | None = None,
        licitacion_id: int | None = None,
        actuacion_id: int | None = None,
    ) -> None:
        params = parse_qs(query)
        state = clean_text(params.get("estado", [""])[0])
        search = clean_text(params.get("q", [""])[0])
        with db_session() as conn:
            items = list_cliente_envios(
                conn,
                cliente_id=cliente_id,
                licitacion_id=licitacion_id,
                actuacion_id=actuacion_id,
                state=state,
                search=search,
            )
        self.send_json(
            {
                "items": items,
                "state_options": CLIENTE_ENVIO_ESTADOS,
                "type_options": CLIENTE_ENVIO_TIPOS,
            }
        )

    def api_get_cliente_envio(self, envio_id: int) -> None:
        with db_session() as conn:
            item = get_cliente_envio(conn, envio_id, include_available_files=True)
        if not item:
            self.send_json({"error": "Envio no encontrado"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"item": item})

    def api_cliente_envio_folder_files(self) -> None:
        if not self.require_admin():
            return
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = list_dropbox_folder_files(data.get("carpeta_dropbox"))
        except (ValueError, DropboxPathError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(payload)

    def api_create_cliente_envio(
        self,
        *,
        default_licitacion_id: int | None = None,
        default_actuacion_id: int | None = None,
    ) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            try:
                item = create_cliente_envio(
                    conn,
                    data,
                    user_id=user.get("username"),
                    timestamp=now_iso(),
                    default_licitacion_id=default_licitacion_id,
                    default_actuacion_id=default_actuacion_id,
                )
            except (ValueError, DropboxPathError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item}, HTTPStatus.CREATED)

    def api_update_cliente_envio(self, envio_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            try:
                item = update_cliente_envio(conn, envio_id, data, user_id=user.get("username"), timestamp=now_iso())
            except (ValueError, DropboxPathError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item})

    def api_generate_cliente_envio_draft(self, envio_id: int) -> None:
        user = self.current_user() or {}
        if user.get("role") not in {"admin", "nuria"}:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            data = {}
        with db_session() as conn:
            try:
                item = generate_cliente_envio_draft(
                    conn,
                    envio_id,
                    user_id=user.get("username"),
                    timestamp=now_iso(),
                    overrides=data,
                    opener=getattr(os, "startfile", None),
                )
            except (ValueError, DropboxPathError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item})

    def api_mark_cliente_envio_sent(self, envio_id: int) -> None:
        user = self.current_user() or {}
        if user.get("role") not in {"admin", "nuria"}:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        with db_session() as conn:
            try:
                item = mark_cliente_envio_sent(conn, envio_id, user_id=user.get("username"), timestamp=now_iso())
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        self.send_json({"ok": True, "item": item})

    def api_open_cliente_envio_folder(self, envio_id: int) -> None:
        user = self.current_user() or {}
        if user.get("role") not in {"admin", "nuria"}:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        with db_session() as conn:
            try:
                result = open_cliente_envio_folder(conn, envio_id, opener=getattr(os, "startfile", None))
            except (ValueError, DropboxPathError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self.send_json(result, status)

    def api_open_cliente_envio_draft(self, envio_id: int) -> None:
        user = self.current_user() or {}
        if user.get("role") not in {"admin", "nuria"}:
            self.send_json({"error": "No autorizado"}, HTTPStatus.UNAUTHORIZED)
            return
        with db_session() as conn:
            try:
                result = open_cliente_envio_draft(conn, envio_id, opener=getattr(os, "startfile", None))
            except (ValueError, DropboxPathError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self.send_json(result, status)

    def api_agenda_workbench(self) -> None:
        with db_session() as conn:
            response = build_agenda_workbench(conn)
            for section in response.get("sections") or []:
                apply_comments_metadata(conn, section.get("items") or [])
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
        tipo_publicacion = normalize_tipo_publicacion(params.get("tipo_publicacion", [""])[0], default="")
        search = clean_text(params.get("q", [""])[0])
        dia_id = clean_text(params.get("dia_id", [""])[0])
        ejercicio_text = clean_text(params.get("ejercicio", [""])[0])
        mes_text = clean_text(params.get("mes", [""])[0])
        vigentes = clean_text(params.get("vigentes", [""])[0]) == "1"
        vivas = clean_text(params.get("vivas", [""])[0]) == "1"
        gestionadas = clean_text(params.get("gestionadas", [""])[0]) == "1"
        calendario = clean_text(params.get("calendario", [""])[0]) == "1"
        nuria_filter = clean_text(params.get("nuria_filter", [""])[0]).lower()
        default_order = "asc" if vivas or gestionadas or calendario else "desc"
        orden_fecha = clean_text(params.get("orden_fecha", [default_order])[0]).lower()
        actuaciones_filter = clean_text(params.get("actuaciones", [""])[0]).lower()
        revision_filter = clean_text(params.get("revision", [""])[0]).lower()
        seguimiento_filter = clean_text(params.get("seguimiento", [""])[0]).lower()
        documentacion_filter = clean_text(params.get("documentacion", [""])[0]).lower()
        estado_interno_filter = clean_text(params.get("estado_interno", [""])[0])
        tipo_publicacion_filter = normalize_tipo_publicacion(
            params.get("tipo_publicacion", [""])[0],
            default="",
        )
        tipo_publicacion_raw = clean_text(params.get("tipo_publicacion", [""])[0]).lower()
        direccion_fecha = "DESC" if orden_fecha == "desc" else "ASC"
        selected_year = int(ejercicio_text) if ejercicio_text.isdigit() and len(ejercicio_text) == 4 else None
        selected_month = int(mes_text) if mes_text.isdigit() and 1 <= int(mes_text) <= 12 else None
        nuria_visible_states = None
        calendario_estados = CALENDARIO_ESTADOS
        vivas_estados = CALENDARIO_ESTADOS
        gestionadas_estados = GESTIONADAS_ESTADOS
        if calendario:
            if estado and estado != "Todos" and estado not in calendario_estados:
                estado = ""
        elif vivas:
            if estado and estado != "Todos" and estado not in vivas_estados:
                estado = ""
        elif gestionadas:
            if estado and estado != "Todos" and estado not in gestionadas_estados:
                estado = ""
        elif user.get("role") == "nuria" and dia_id.isdigit():
            if nuria_filter in {"all", "todas"}:
                nuria_visible_states = NURIA_VISIBLE_STATES
            elif nuria_filter in {"discarded", "descartadas"}:
                nuria_visible_states = NURIA_DISCARDED_STATES
            else:
                nuria_visible_states = NURIA_DEFAULT_REVIEW_STATES
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
        elif gestionadas:
            placeholders = ", ".join("?" for _ in gestionadas_estados)
            where.append(f"LOWER(estado) IN ({placeholders})")
            values.extend([item.lower() for item in gestionadas_estados])
        elif user.get("role") == "nuria" and dia_id.isdigit() and not (estado and estado != "Todos"):
            placeholders = ", ".join("?" for _ in nuria_visible_states)
            where.append(f"estado IN ({placeholders})")
            values.extend(nuria_visible_states)
        if dia_id.isdigit():
            where.append("infonalia_dia_id = ?")
            values.append(int(dia_id))
        elif tipo_publicacion_raw in {"all", "todas", "todos"}:
            pass
        elif tipo_publicacion_filter:
            where.append("COALESCE(tipo_publicacion, ?) = ?")
            values.extend([TIPO_PUBLICACION_LICITACION, tipo_publicacion_filter])
        else:
            where.append("COALESCE(tipo_publicacion, ?) = ?")
            values.extend([TIPO_PUBLICACION_LICITACION, TIPO_PUBLICACION_LICITACION])

        current = datetime.now()
        if not dia_id.isdigit() and (vigentes or vivas):
            where.append(
                """
                fecha_limite GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
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
        date_filter_base_where = list(where)
        date_filter_base_values = list(values)
        if not dia_id.isdigit():
            if selected_year is not None:
                where.append("fecha_limite >= ? AND fecha_limite < ?")
                values.extend([f"{selected_year:04d}-01-01", f"{selected_year + 1:04d}-01-01"])
            if selected_month is not None:
                where.append("fecha_limite GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
                where.append("substr(fecha_limite, 6, 2) = ?")
                values.append(f"{selected_month:02d}")

        def build_where_sql(clauses: list[str]) -> str:
            return " WHERE " + " AND ".join(clauses) if clauses else ""

        sql = "SELECT * FROM licitaciones"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (
            " ORDER BY CASE WHEN fecha_limite GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 0 ELSE 1 END ASC, "
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
                apply_licitacion_list_metadata(conn, rows)
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
            date_filters = {"years": [], "month_counts": {}, "year_all_count": 0, "month_all_count": 0}
            if not dia_id.isdigit():
                valid_fecha_clause = (
                    "fecha_limite GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
                )
                year_all_count_sql = (
                    "SELECT COUNT(*) AS total FROM licitaciones"
                    f"{build_where_sql(date_filter_base_where)}"
                )
                year_all_count = int(
                    conn.execute(year_all_count_sql, date_filter_base_values).fetchone()["total"] or 0
                )

                years_where = [*date_filter_base_where, valid_fecha_clause]
                years_sql = (
                    "SELECT DISTINCT substr(fecha_limite, 1, 4) AS ejercicio "
                    "FROM licitaciones"
                    f"{build_where_sql(years_where)} "
                    "ORDER BY ejercicio DESC"
                )
                years = [
                    str(row["ejercicio"])
                    for row in conn.execute(years_sql, date_filter_base_values)
                    if row["ejercicio"]
                ]

                month_all_where = list(date_filter_base_where)
                month_all_values = list(date_filter_base_values)
                if selected_year is not None:
                    month_all_where.append("fecha_limite >= ? AND fecha_limite < ?")
                    month_all_values.extend([f"{selected_year:04d}-01-01", f"{selected_year + 1:04d}-01-01"])
                month_all_count_sql = (
                    "SELECT COUNT(*) AS total FROM licitaciones"
                    f"{build_where_sql(month_all_where)}"
                )
                month_all_count = int(
                    conn.execute(month_all_count_sql, month_all_values).fetchone()["total"] or 0
                )

                month_where = [*date_filter_base_where, valid_fecha_clause]
                month_values = list(date_filter_base_values)
                if selected_year is not None:
                    month_where.append("fecha_limite >= ? AND fecha_limite < ?")
                    month_values.extend([f"{selected_year:04d}-01-01", f"{selected_year + 1:04d}-01-01"])
                month_counts_sql = (
                    "SELECT CAST(substr(fecha_limite, 6, 2) AS INTEGER) AS mes, COUNT(*) AS total "
                    "FROM licitaciones"
                    f"{build_where_sql(month_where)} "
                    "GROUP BY mes"
                )
                month_counts = {
                    str(int(row["mes"])): int(row["total"] or 0)
                    for row in conn.execute(month_counts_sql, month_values)
                    if row["mes"]
                }
                date_filters = {
                    "years": years,
                    "month_counts": month_counts,
                    "year_all_count": year_all_count,
                    "month_all_count": month_all_count,
                }
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
                    SELECT estado, COALESCE(tipo_publicacion, 'licitacion') AS tipo_publicacion, COUNT(*) AS total
                    FROM licitaciones
                    WHERE infonalia_dia_id = ?
                    GROUP BY estado, tipo_publicacion
                    """,
                    (int(dia_id),),
                ).fetchall()
                day_counts: dict[str, int] = {}
                day_counts_normales: dict[str, int] = {}
                day_anuncios_previos = 0
                for row in day_counts_rows:
                    normalized_state = normalize_licitacion_estado(row["estado"])
                    total_row = int(row["total"] or 0)
                    day_counts[normalized_state] = day_counts.get(normalized_state, 0) + total_row
                    if is_anuncio_previo(row["tipo_publicacion"]):
                        if normalized_state != ESTADO_DESCARTADA:
                            day_anuncios_previos += total_row
                    else:
                        day_counts_normales[normalized_state] = day_counts_normales.get(normalized_state, 0) + total_row
                day_pending_review = day_counts_normales.get(ESTADO_ENVIADA_NURIA, 0)
                day_pending_admin = day_counts_normales.get(ESTADO_IMPORTADA, 0)
                day_nuria_total = sum(day_counts.get(state, 0) for state in NURIA_VISIBLE_STATES)
                day_nuria_total += day_anuncios_previos
        if calendario:
            estados = calendario_estados
        elif vivas:
            estados = vivas_estados
        elif gestionadas:
            estados = gestionadas_estados
        elif user.get("role") == "nuria" and dia_id.isdigit():
            estados = nuria_visible_states
        else:
            estados = ESTADOS_ORDEN
        self.send_json(
            {
                "items": rows,
                "totals": totals,
                "estados": estados,
                "date_filters": date_filters,
                "day_pending_review": day_pending_review,
                "day_pending_admin": day_pending_admin,
                "day_sent_nuria_at": day_sent_nuria_at,
                "day_nuria_dirty_at": day_nuria_dirty_at,
                "day_nuria_pending_update": day_nuria_pending_update,
                "day_reviewed_at": day_reviewed_at,
                "day_nuria_total": day_nuria_total,
            }
        )

    def _justificaciones_permissions(self) -> dict[str, bool]:
        editable = self.is_admin()
        return {
            "view": True,
            "download": True,
            "create": editable,
            "edit": editable,
            "generate_costs": editable,
            "freeze": editable,
            "generate_documents": editable,
            "change_state": editable,
        }

    def _justificaciones_service(self, conn: sqlite3.Connection) -> JustificationApplicationService:
        return JustificationApplicationService(
            JustificationRepository(conn),
            temporary_root=PROJECT_ROOT / "tmp" / "justificaciones_baja_runtime",
        )

    def _read_bounded_json(self) -> dict:
        body = self.read_body(max_bytes=MAX_BODY_BYTES)
        if not body:
            return {}
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("El cuerpo JSON debe ser un objeto.")
        return value

    def _send_justificaciones_error(self, exc: Exception) -> None:
        if isinstance(exc, JustificationApplicationError):
            payload = {"error": str(exc), "code": exc.code}
            issues = getattr(exc, "issues", None)
            if issues:
                payload["issues"] = issues
            self.send_json(payload, HTTPStatus(exc.status_code))
            return
        if isinstance(exc, JustificationNotFoundError):
            self.send_json(
                {"error": str(exc), "code": "justificacion_no_encontrada"},
                HTTPStatus.NOT_FOUND,
            )
            return
        if isinstance(exc, (ProductImportError, DropboxPathError, ValueError, KeyError, TypeError)):
            self.send_json({"error": str(exc), "code": "peticion_invalida"}, HTTPStatus.BAD_REQUEST)
            return
        LOGGER.exception("Fallo no controlado en justificaciones de baja", exc_info=exc)
        self.send_json({"error": "No se pudo completar la operación."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def api_list_justificaciones_baja(self, query: str) -> None:
        params = parse_qs(query)
        try:
            filters: dict[str, object] = {}
            for query_name, filter_name in (("licitacion_id", "licitacion_id"), ("cliente_id", "cliente_id")):
                raw = str(params.get(query_name, [""])[0]).strip()
                if raw:
                    if not raw.isdigit():
                        raise ValueError(f"{query_name} no es válido.")
                    filters[filter_name] = int(raw)
            state = str(params.get("estado", [""])[0]).strip()
            if state:
                filters["state"] = state
            q = str(params.get("q", [""])[0]).strip()
            if q:
                filters["q"] = q
            with db_session() as conn:
                items = self._justificaciones_service(conn).list(**filters)
            self.send_json({"items": items, "permissions": self._justificaciones_permissions()})
        except Exception as exc:
            self._send_justificaciones_error(exc)

    def api_get_justificacion_baja(self, justification_id: int) -> None:
        try:
            with db_session() as conn:
                item = self._justificaciones_service(conn).get(justification_id)
            self.send_json({"item": item, "permissions": self._justificaciones_permissions()})
        except Exception as exc:
            self._send_justificaciones_error(exc)

    def api_update_justificacion_baja(self, justification_id: int) -> None:
        if not self.require_admin():
            return
        try:
            data = self._read_bounded_json()
            with db_session() as conn:
                item = self._justificaciones_service(conn).save(
                    justification_id,
                    draft=data["draft"],
                    expected_revision=int(data["revision"]),
                    user_id=str(self.current_user()["username"]),
                )
            self.send_json({"item": item, "permissions": self._justificaciones_permissions()})
        except Exception as exc:
            self._send_justificaciones_error(exc)

    def api_post_justificacion_baja(self, path: str) -> None:
        if not self.require_admin():
            return
        try:
            if path == "/api/justificaciones-baja/importar-xlsx/preview":
                content_type = self.headers.get("Content-Type", "")
                body = self.read_body(max_bytes=MAX_BODY_BYTES)
                fields, files = extract_multipart_fields(
                    content_type,
                    body,
                    allowed_file_fields={"file": {".xlsx"}},
                    max_upload_bytes=MAX_UPLOAD_BYTES,
                )
                upload = files.get("file")
                if upload is None:
                    raise ValueError("Falta el fichero XLSX.")
                mapping_raw = fields.get("mapping", "").strip()
                mapping = json.loads(mapping_raw) if mapping_raw else None
                result = preview_xlsx(
                    upload.content,
                    filename=upload.filename,
                    sheet_name=fields.get("sheet_name") or None,
                    start_row=int(fields.get("start_row") or 1),
                    mapping=mapping,
                    preview_rows=int(fields.get("preview_rows") or 20),
                )
                self.send_json({"preview": result})
                return
            if path == "/api/justificaciones-baja/pegar/preview":
                data = self._read_bounded_json()
                result = preview_tabular(
                    str(data.get("text") or ""),
                    start_row=int(data.get("start_row") or 1),
                    mapping=data.get("mapping"),
                    preview_rows=int(data.get("preview_rows") or 20),
                )
                self.send_json({"preview": result})
                return
            if path == "/api/justificaciones-baja/preview":
                data = self._read_bounded_json()
                with db_session() as conn:
                    result = self._justificaciones_service(conn).preview(data["draft"])
                self.send_json(result)
                return
            if path == "/api/justificaciones-baja":
                data = self._read_bounded_json()
                licitacion_id = int(data["licitacion_id"])
                cliente_id = int(data["cliente_id"])
                supplied_draft = data.get("draft")
                if supplied_draft is not None and not isinstance(supplied_draft, dict):
                    raise ValueError("draft debe ser un objeto o null.")
                if "proposals" in data:
                    raise ValueError(
                        "proposals ya no forma parte del contrato; envía los valores dentro de draft."
                    )
                with db_session() as conn:
                    licitacion_row = conn.execute(
                        "SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)
                    ).fetchone()
                    if licitacion_row is None:
                        raise ValueError("La licitación indicada no existe.")
                    cliente = get_cliente(conn, cliente_id)
                    if cliente is None:
                        raise ValueError("El cliente indicado no existe.")
                    item = self._justificaciones_service(conn).create(
                        licitacion=row_to_dict(licitacion_row),
                        cliente=cliente,
                        lote_numero=str(data.get("lote_numero") or "1"),
                        lote_nombre=str(data.get("lote_nombre") or ""),
                        declared_offer=data.get("importe_ofertado", "0"),
                        draft=supplied_draft,
                        user_id=str(self.current_user()["username"]),
                    )
                self.send_json({"item": item, "permissions": self._justificaciones_permissions()}, HTTPStatus.CREATED)
                return

            parts = path.removeprefix("/api/justificaciones-baja/").strip("/").split("/")
            if not parts or not parts[0].isdigit():
                raise ValueError("Id de justificación no válido.")
            justification_id = int(parts[0])
            action = "/".join(parts[1:])
            if action == "imagen-ruta":
                self._api_attach_justificacion_image(justification_id)
                return
            data = self._read_bounded_json()
            revision = int(data.get("revision") or 0)
            username = str(self.current_user()["username"])
            with db_session() as conn:
                service = self._justificaciones_service(conn)
                if action == "costes/generar":
                    item = service.generate_costs(justification_id, expected_revision=revision, user_id=username)
                elif action == "costes/recalcular":
                    line_ids = data.get("line_ids")
                    if line_ids is not None and not isinstance(line_ids, list):
                        raise ValueError("line_ids debe ser una lista o null.")
                    item = service.recalculate_costs(
                        justification_id,
                        expected_revision=revision,
                        line_ids=line_ids,
                        user_id=username,
                    )
                elif action == "costes/manual":
                    item = service.set_manual_cost(
                        justification_id,
                        expected_revision=revision,
                        line_id=str(data["line_id"]),
                        manual_unit_cost=data["manual_unit_cost"],
                        user_id=username,
                    )
                elif action == "costes/retirar-manual":
                    item = service.remove_manual_cost(
                        justification_id,
                        expected_revision=revision,
                        line_id=str(data["line_id"]),
                        user_id=username,
                    )
                elif action == "productos/bloqueo":
                    if not isinstance(data.get("locked"), bool):
                        raise ValueError("locked debe ser booleano.")
                    raw_line_ids = data.get("line_ids")
                    if raw_line_ids is None and data.get("line_id") not in (None, ""):
                        raw_line_ids = [data.get("line_id")]
                    if not isinstance(raw_line_ids, list) or not raw_line_ids:
                        raise ValueError("line_ids debe ser una lista no vacía.")
                    line_ids = [str(line_id).strip() for line_id in raw_line_ids]
                    if any(not line_id for line_id in line_ids):
                        raise ValueError("line_ids contiene identificadores vacíos.")
                    item = service.set_product_locks(
                        justification_id,
                        expected_revision=revision,
                        line_ids=line_ids,
                        locked=bool(data["locked"]),
                        user_id=username,
                    )
                elif action == "congelar":
                    result = service.freeze(
                        justification_id, expected_revision=revision, user_id=username
                    )
                    self.send_json({**result, "permissions": self._justificaciones_permissions()})
                    return
                elif action == "estado":
                    item = service.update_state(
                        justification_id,
                        expected_revision=revision,
                        state=str(data.get("state") or ""),
                        user_id=username,
                    )
                elif len(parts) == 5 and parts[1] == "versiones" and parts[2].isdigit() and parts[3] == "documentos":
                    raise ValueError("Ruta documental no válida.")
                elif len(parts) == 4 and parts[1] == "versiones" and parts[2].isdigit() and parts[3] == "documentos":
                    version_number = int(parts[2])
                    output, base = self._justificacion_output_directory(
                        conn, justification_id, version_number
                    )
                    result = service.generate_documents(
                        justification_id,
                        version_number=version_number,
                        output_directory=output,
                        dropbox_base=base,
                        user_id=username,
                    )
                    self.send_json({**result, "permissions": self._justificaciones_permissions()}, HTTPStatus.CREATED)
                    return
                else:
                    raise ValueError("Acción de justificación no reconocida.")
            self.send_json({"item": item, "permissions": self._justificaciones_permissions()})
        except Exception as exc:
            self._send_justificaciones_error(exc)

    def _api_attach_justificacion_image(self, justification_id: int) -> None:
        content_type = self.headers.get("Content-Type", "")
        username = str(self.current_user()["username"])
        if "multipart/form-data" in content_type.lower():
            body = self.read_body(max_bytes=MAX_BODY_BYTES)
            fields, files = extract_multipart_fields(
                content_type,
                body,
                allowed_file_fields={
                    "file": {".png", ".jpg", ".jpeg"},
                    "image": {".png", ".jpg", ".jpeg"},
                },
                max_upload_bytes=MAX_UPLOAD_BYTES,
            )
            upload = files.get("file") or files.get("image")
            if upload is None:
                raise ValueError("Falta la imagen de ruta.")
            revision = int(fields.get("revision") or 0)
            filename = upload.filename
            content = upload.content
        else:
            data = self._read_bounded_json()
            revision = int(data.get("revision") or 0)
            relative_path = str(data.get("relative_path") or "").strip()
            if not relative_path:
                raise ValueError("Falta la ruta relativa de la imagen.")
            with db_session() as conn:
                row = conn.execute(
                    """
                    SELECT l.* FROM licitaciones l
                    JOIN justificaciones_baja jb ON jb.licitacion_id = l.id
                    WHERE jb.id = ? AND jb.archived_at IS NULL
                    """,
                    (justification_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("No existe la justificación.")
                base = validate_dropbox_base_path()
                resolution = resolve_licitacion_folder(row, dropbox_base=base)
                if not (resolution.ok and resolution.exists and resolution.inside_dropbox_base):
                    raise DropboxPathError("La carpeta de la licitación no es una salida Dropbox válida.")
                licitation_folder = _resolve_licitacion_folder_without_links(
                    row, base, resolution
                )
                resolved = _resolve_existing_path_without_links(
                    licitation_folder, relative_path
                )
                if not path_inside_base(resolved, licitation_folder):
                    raise DropboxPathError("La imagen queda fuera de la carpeta de la licitación.")
                if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not resolved.is_file():
                    raise ValueError("El documento seleccionado no es una imagen PNG/JPEG.")
                filename = resolved.name
                with resolved.open("rb") as stream:
                    size = os.fstat(stream.fileno()).st_size
                    if size > MAX_UPLOAD_BYTES:
                        raise ValueError("La imagen supera el tamaño permitido.")
                    content = stream.read(MAX_UPLOAD_BYTES + 1)
                if len(content) != size or len(content) > MAX_UPLOAD_BYTES:
                    raise ValueError("La imagen cambió durante la lectura o supera el tamaño permitido.")
        with db_session() as conn:
            item = self._justificaciones_service(conn).attach_route_image(
                justification_id,
                expected_revision=revision,
                filename=filename,
                content=content,
                user_id=username,
            )
        self.send_json({"item": item, "permissions": self._justificaciones_permissions()})

    def _justificacion_output_directory(
        self,
        conn: sqlite3.Connection,
        justification_id: int,
        version_number: int,
    ) -> tuple[Path, Path]:
        row = conn.execute(
            """
            SELECT l.*, v.document_context_json
            FROM licitaciones l
            JOIN justificaciones_baja jb ON jb.licitacion_id = l.id
            JOIN justificacion_baja_versiones v ON v.justificacion_id = jb.id
            WHERE jb.id = ? AND jb.archived_at IS NULL AND v.version_number = ?
            """,
            (justification_id, version_number),
        ).fetchone()
        if row is None:
            raise ValueError("No existe la justificación o la versión congelada indicada.")
        base = validate_dropbox_base_path().resolve(strict=True)
        resolution = resolve_licitacion_folder(row, dropbox_base=base)
        if not (
            resolution.ok
            and resolution.exists
            and resolution.inside_dropbox_base
            and Path(resolution.path).is_dir()
        ):
            raise DropboxPathError("La carpeta de la licitación no es una salida Dropbox válida.")
        licitation_folder = _resolve_licitacion_folder_without_links(
            row, base, resolution
        )
        if not path_inside_base(licitation_folder, base):
            raise DropboxPathError("La carpeta de la licitación queda fuera de Dropbox.")
        try:
            context = json.loads(row["document_context_json"])
            frozen_lot = context["identification"]["lot_number"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("La versión congelada no identifica el lote de forma íntegra.") from exc
        lot = safe_component(frozen_lot, maximum_length=40)
        output = _ensure_no_link_components(
            base,
            licitation_folder
            / "Justificaciones de baja"
            / f"Lote_{lot}"
            / f"Justificacion_{justification_id}",
        )
        if not path_inside_base(output, base):
            raise DropboxPathError("La salida documental queda fuera de Dropbox.")
        return output, base

    def api_download_justificacion_document(self, document_id: int) -> None:
        try:
            with db_session() as conn:
                repository = JustificationRepository(conn)
                document = repository.get_document_by_id(document_id)
                licitacion = conn.execute(
                    "SELECT * FROM licitaciones WHERE id = ?", (document["licitacion_id"],)
                ).fetchone()
                if licitacion is None:
                    raise ValueError("No existe la licitación del documento.")
                base = validate_dropbox_base_path().resolve(strict=True)
                resolution = resolve_licitacion_folder(licitacion, dropbox_base=base)
                if not (resolution.ok and resolution.exists and resolution.inside_dropbox_base):
                    raise DropboxPathError("La carpeta de la licitación no es válida.")
                licitation_folder = _resolve_licitacion_folder_without_links(
                    licitacion, base, resolution
                )
                if (
                    not licitation_folder.is_dir()
                    or not path_inside_base(licitation_folder, base)
                ):
                    raise DropboxPathError("La carpeta de la licitación no es válida.")
                path = _resolve_existing_path_without_links(
                    base, document["relative_path"]
                )
                if (
                    not path_inside_base(path, base)
                    or not path_inside_base(path, licitation_folder)
                    or not path.is_file()
                ):
                    raise DropboxPathError("El documento no está en una ruta permitida.")
                if path.suffix.lower() not in {".docx", ".xlsx"}:
                    raise ValueError("El tipo documental no está permitido.")
                expected_size = int(document["size_bytes"])
                if expected_size < 0 or expected_size > 64 * 1024 * 1024:
                    raise ValueError("El tamaño registrado del documento no es admisible.")
                with path.open("rb") as stream:
                    actual_size = os.fstat(stream.fileno()).st_size
                    if actual_size != expected_size:
                        raise ValueError("El tamaño del documento no coincide con el registro.")
                    body = stream.read(expected_size + 1)
                if len(body) != expected_size:
                    raise ValueError("El documento cambió durante la lectura.")
                digest = hashlib.sha256(body).hexdigest().upper()
                if digest != str(document["sha256"]).upper():
                    raise ValueError("El hash del documento no coincide con el registro.")
            self.send_private_document(body, str(document["file_name"]), path.suffix.lower())
        except Exception as exc:
            self._send_justificaciones_error(exc)

    def send_private_document(self, body: bytes, filename: str, suffix: str) -> None:
        safe_name = Path(filename).name.replace('"', "_")
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if suffix == ".docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.send_response(HTTPStatus.OK)
        self.send_security_headers(is_private=True)
        self.send_pending_session_cookie()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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
                    "cliente_envios": list_cliente_envios(conn, licitacion_id=licitacion_id),
                }
            )
            item = build_licitacion_center_detail(conn, item, actuaciones=actuaciones)
            apply_licitacion_list_metadata(conn, [item])
            for actuacion in item.get("actuaciones") or []:
                actuacion["source_type"] = "actuacion"
                actuacion["source_id"] = int(actuacion["id"])
            apply_comments_metadata(conn, item.get("actuaciones") or [])
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

    def api_get_document_tree(self, licitacion_id: int) -> None:
        try:
            with db_session() as conn:
                ensure_monitor_schema(conn)
                payload = build_document_tree_payload(conn, licitacion_id)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        except Exception as exc:
            print(f"No se pudo construir arbol documental de licitacion {licitacion_id}: {exc}", file=sys.stderr)
            self.send_json({"error": "No se pudo consultar la documentacion del expediente."}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(payload)

    def api_create_licitacion_marker(self, licitacion_id: int, *, marker_type: str) -> None:
        if not self.require_admin():
            return
        if marker_type not in {"id", "follow"}:
            self.send_json({"error": "Tipo de marcador no valido"}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            roots = marker_allowed_roots()
            dropbox_root = marker_dropbox_root()
            if marker_type == "id":
                result = create_id_marker_for_licitacion(row, allowed_roots=roots, dropbox_root=dropbox_root)
            else:
                result = create_follow_marker_for_licitacion(row, allowed_roots=roots, dropbox_root=dropbox_root)
            result["seguimiento"] = get_marker_status_for_licitacion(row, dropbox_root)
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        if not result.get("ok") and result.get("error"):
            result["message"] = result["error"]
        self.send_json(result, status)

    def api_open_licitacion_folder(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            result = open_licitacion_folder(
                row,
                allowed_roots=marker_allowed_roots(),
                dropbox_root=marker_dropbox_root(),
                opener=getattr(os, "startfile", None),
            )
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        if not result.get("ok") and result.get("error"):
            result["message"] = result["error"]
        self.send_json(result, status)

    def api_search_licitaciones(self, query: str) -> None:
        params = parse_qs(query)
        search = clean_text(params.get("q", [""])[0])
        estado = clean_text(params.get("estado", [""])[0])
        provincia = clean_text(params.get("provincia", [""])[0])
        plataforma = clean_text(params.get("plataforma", [""])[0])
        tipo_publicacion = normalize_tipo_publicacion(params.get("tipo_publicacion", [""])[0], default="")
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
        if tipo_publicacion:
            where.append("COALESCE(tipo_publicacion, ?) = ?")
            values.extend([TIPO_PUBLICACION_LICITACION, tipo_publicacion])
        if provincia:
            where.append("provincia LIKE ?")
            values.append(f"%{provincia}%")
        if plataforma:
            where.append("plataforma = ?")
            values.append(plataforma)

        sql = """
            SELECT id, expediente, organismo, objeto, fecha_limite, hora_limite,
                   estado, provincia, plataforma, ruta_carpeta, tipo_publicacion
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
        estado = normalize_actuacion_estado(params.get("estado", [""])[0], default="")

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
        if estado:
            estado_values = sorted(estado_db_values(estado))
            if estado_values:
                placeholders = ",".join("?" for _ in estado_values)
                where.append(f"LOWER(a.estado) IN ({placeholders})")
                values.extend(estado_values)
        if clean_text(params.get("abiertas", [""])[0]) == "1":
            placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
            where.append(f"LOWER(a.estado) IN ({placeholders})")
            values.extend(sorted(ACTUACION_ESTADOS_ABIERTOS))

        current = datetime.now()
        with db_session() as conn:
            rows = conn.execute(actuaciones_select_sql(where), values).fetchall()
            items = [actuacion_response(conn, row, now=current) for row in rows]
            for item in items:
                item["source_type"] = "actuacion"
                item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, items)

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
                "estados": ACTUACION_ESTADO_ORDEN,
            }
        )

    def api_actuaciones_resumen(self) -> None:
        current = datetime.now()
        placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
        with db_session() as conn:
            rows = conn.execute(
                actuaciones_select_sql([f"LOWER(a.estado) IN ({placeholders})"]),
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
            item["cliente_envios"] = list_cliente_envios(conn, actuacion_id=actuacion_id)
            item["source_type"] = "actuacion"
            item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, [item])
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
            item["source_type"] = "actuacion"
            item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, [item])

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
                create_system_comment(
                    conn,
                    entity_type="actuacion",
                    entity_id=actuacion_id,
                    body=f"Estado cambiado: {old_estado or 'Sin estado'} -> {payload['estado'] or 'Sin estado'}",
                    metadata={"event_type": "estado", "old_value": old_estado or "", "new_value": payload["estado"] or ""},
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
            item["source_type"] = "actuacion"
            item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, [item])

        self.send_json({"ok": True, "item": item})

    def api_close_actuacion(self, actuacion_id: int) -> None:
        self.api_set_actuacion_closed_state(actuacion_id, "enviado")

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
                event_type="cierre" if estado == "enviado" else "cancelacion",
                comentario="Actuacion enviada" if estado == "enviado" else "Actuacion cancelada",
                old_value=row["estado"],
                new_value=estado,
                timestamp=timestamp,
            )
            create_system_comment(
                conn,
                entity_type="actuacion",
                entity_id=actuacion_id,
                body=f"Estado cambiado: {row['estado'] or 'Sin estado'} -> {estado}",
                metadata={"event_type": "estado", "old_value": row["estado"] or "", "new_value": estado},
                timestamp=timestamp,
            )
            updated = get_actuacion_row(conn, actuacion_id)
            item = actuacion_response(conn, updated, include_historial=True)
            item["source_type"] = "actuacion"
            item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, [item])
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
            create_comment(
                conn,
                entity_type="actuacion",
                entity_id=actuacion_id,
                body=comentario,
                user=user,
                timestamp=timestamp,
            )
            item = actuacion_response(conn, row, include_historial=True)
            item["source_type"] = "actuacion"
            item["source_id"] = int(item["id"])
            apply_comments_metadata(conn, [item])
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
            estado = normalize_actuacion_estado(row["estado"], default="pendiente")
            if estado not in {"pendiente", "en_preparacion", "preparado"}:
                estado = "pendiente"
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
            "tipo_publicacion": normalize_tipo_publicacion(data.get("tipo_publicacion")),
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

    def api_import_infonalia_mail_run_now(self) -> None:
        if not self.require_admin():
            return

        user = self.current_user() or {}
        username = clean_text(user.get("username")) or "admin"
        LOGGER.info("Importación manual Infonalia/Gmail solicitada por %s", username)
        try:
            result = process_infonalia_mailbox_once(
                dry_run=False,
                include_seen=False,
                verbose=False,
                notification_sender=lambda to, subject, body, html: send_monitor_email(to, subject, body, html),
            )
        except Exception:
            LOGGER.exception("Error en importación manual Infonalia/Gmail solicitada por %s", username)
            self.send_json(
                {
                    "ok": False,
                    "message": "No se pudo importar desde Gmail. Revisa la configuración o los logs.",
                    "result": {"candidates_seen": 0, "parsed_items": 0, "imported": 0, "duplicates": 0, "errors": 1, "notified": 0},
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        summary = {
            "candidates_seen": int(result.get("candidates_seen", 0) or 0),
            "parsed_items": int(result.get("parsed_items", 0) or 0),
            "imported": int(result.get("imported", 0) or 0),
            "duplicates": int(result.get("duplicates", 0) or 0),
            "errors": int(result.get("errors", 0) or 0),
            "notified": int(result.get("notified", 0) or 0),
        }
        if not result.get("enabled", True):
            self.send_json(
                {
                    "ok": False,
                    "message": "No se pudo importar desde Gmail. Revisa la configuración o los logs.",
                    "detail": clean_text(result.get("message")),
                    "result": summary,
                    "source": "manual",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return
        if summary["errors"] > 0 or clean_text(result.get("status")) == "failed":
            self.send_json(
                {
                    "ok": False,
                    "message": "No se pudo importar desde Gmail. Revisa la configuración o los logs.",
                    "detail": clean_text(result.get("last_error")) or clean_text(result.get("message")),
                    "result": summary,
                    "source": "manual",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        if summary["imported"] > 0:
            message = f"Importación completada: {summary['imported']} licitaciones importadas."
        elif summary["duplicates"] > 0 and summary["candidates_seen"] > 0:
            message = "No se han importado nuevas licitaciones. El correo ya estaba procesado."
        else:
            message = "No hay correos nuevos de Infonalia para importar."

        self.send_json(
            {
                "ok": True,
                "message": message,
                "result": summary,
                "source": "manual",
                "uses_scheduler_importer": True,
                "llangon_cmd_touched": False,
            }
        )

    def api_send_dia_to_nuria(self, dia_id: int) -> None:
        if not self.require_admin():
            return

        data = self.read_json()
        email_recipients: list[str] | None = None
        if "notification_email" in data:
            notification_email = clean_text(data.get("notification_email"))
            if not notification_email or not is_valid_email_address(notification_email):
                self.send_json({"error": "El correo de destino no es valido."}, HTTPStatus.BAD_REQUEST)
                return
            email_recipients = [notification_email]

        user = self.current_user() or {}
        with db_session() as conn:
            day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            if not day:
                self.send_json({"error": "Dia Infonalia no encontrado"}, HTTPStatus.NOT_FOUND)
                return

            counts_rows = conn.execute(
                """
                SELECT estado, COALESCE(tipo_publicacion, 'licitacion') AS tipo_publicacion, COUNT(*) AS total
                FROM licitaciones
                WHERE infonalia_dia_id = ?
                GROUP BY estado, tipo_publicacion
                """,
                (dia_id,),
            ).fetchall()
            counts: dict[str, int] = {}
            normal_counts: dict[str, int] = {}
            anuncios_previos_count = 0
            for row in counts_rows:
                normalized_state = normalize_licitacion_estado(row["estado"])
                total_row = int(row["total"] or 0)
                counts[normalized_state] = counts.get(normalized_state, 0) + total_row
                if is_anuncio_previo(row["tipo_publicacion"]):
                    if normalized_state != ESTADO_DESCARTADA:
                        anuncios_previos_count += total_row
                else:
                    normal_counts[normalized_state] = normal_counts.get(normalized_state, 0) + total_row
            pendientes = normal_counts.get(ESTADO_IMPORTADA, 0)
            pendientes_nuria = normal_counts.get(ESTADO_ENVIADA_NURIA, 0)
            decisiones_nuria = (
                normal_counts.get(ESTADO_DESCARTADA, 0)
                + normal_counts.get(ESTADO_DESCARGAR_PARA_VER, 0)
                + normal_counts.get(ESTADO_PREPARAR_FICHA, 0)
            )
            nuria_total = pendientes_nuria + decisiones_nuria + anuncios_previos_count
            review_rows = conn.execute(
                """
                SELECT *
                FROM licitaciones
                WHERE infonalia_dia_id = ?
                  AND (
                    (COALESCE(tipo_publicacion, 'licitacion') = 'licitacion' AND estado IN (?, ?, ?))
                    OR (COALESCE(tipo_publicacion, 'licitacion') = 'anuncio_previo' AND estado <> ?)
                  )
                ORDER BY CASE WHEN COALESCE(tipo_publicacion, 'licitacion') = 'anuncio_previo' THEN 1 ELSE 0 END ASC,
                         fecha_limite ASC, hora_limite ASC, id ASC
                """,
                (
                    dia_id,
                    ESTADO_ENVIADA_NURIA,
                    ESTADO_DESCARGAR_PARA_VER,
                    ESTADO_PREPARAR_FICHA,
                    ESTADO_DESCARTADA,
                ),
            ).fetchall()
            pending_rows = conn.execute(
                """
                SELECT expediente, objeto, fecha_limite, hora_limite, tipo_publicacion
                FROM licitaciones
                WHERE infonalia_dia_id = ?
                  AND (
                    (COALESCE(tipo_publicacion, 'licitacion') = 'licitacion' AND estado = ?)
                    OR (COALESCE(tipo_publicacion, 'licitacion') = 'anuncio_previo' AND estado <> ?)
                  )
                ORDER BY CASE WHEN COALESCE(tipo_publicacion, 'licitacion') = 'anuncio_previo' THEN 1 ELSE 0 END ASC,
                         fecha_limite ASC, hora_limite ASC, id ASC
                """,
                (dia_id, ESTADO_ENVIADA_NURIA, ESTADO_DESCARTADA),
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
            action_codes = ensure_review_action_codes(
                conn,
                review_id=dia_id,
                licitaciones=review_rows,
                timestamp=timestamp,
            )
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
            create_system_comment(
                conn,
                entity_type="infonalia_dia",
                entity_id=dia_id,
                body=f"Día enviado a Nuria por {clean_text(user.get('display_name')) or clean_text(user.get('username')) or 'administrador'}.",
                metadata={"event": "send_to_nuria"},
                timestamp=timestamp,
            )
            asunto = f"Infonalia del día {format_date_es(day['fecha'])}"
            intro = (
                f"{user.get('display_name', 'Administrador')} ha dejado disponible el día {day['titulo']} para su revisión."
            )
            body_lines = [
                intro,
                "",
                f"Total de licitaciones del día: {sum(counts.values())}",
                f"Licitaciones pendientes de revisión: {len(pending_rows)}",
            ]
            if not pending_rows:
                body_lines.extend(["", "NO HAY LICITACIONES INTERESANTES"])
            else:
                body_lines.extend(["", "Listado de licitaciones pendientes:"])
                for row in pending_rows:
                    tipo_label = (
                        "Anuncio previo"
                        if is_anuncio_previo(row["tipo_publicacion"])
                        else "Licitación"
                    )
                    fecha_hora = " ".join(
                        part
                        for part in [
                            format_date_es(row["fecha_limite"]),
                            parse_time_value(row["hora_limite"]),
                        ]
                        if clean_text(part)
                    ).strip()
                    body_lines.append(
                        f"- {tipo_label}: {clean_text(row['expediente'])} | "
                        f"{clean_text(row['objeto'])} | "
                        f"{fecha_hora or 'Sin fecha'}"
                    )
            cuerpo = "\n".join(body_lines)
            settings = get_settings()
            mailbox_to = effective_text("action_mailbox_to", settings=settings) or ACTION_MAILBOX_TO
            mailbox_cc = (
                clean_text(settings.get("action_mailbox_cc"))
                if "action_mailbox_cc" in settings
                else effective_text("action_mailbox_cc", settings=settings)
            )
            html_body = build_infonalia_review_email_html(
                day=day,
                licitaciones=review_rows,
                action_codes=action_codes,
                mailbox_to=mailbox_to,
                mailbox_cc=mailbox_cc,
                generated_at=datetime.fromisoformat(timestamp),
            )
            create_notification(
                conn,
                user.get("username"),
                REVIEWER_USER,
                asunto,
                cuerpo,
                email_recipients=email_recipients,
                html_body=html_body,
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
            create_system_comment(
                conn,
                entity_type="infonalia_dia",
                entity_id=dia_id,
                body=f"Día marcado como revisado por {clean_text(user.get('display_name')) or clean_text(user.get('username')) or 'usuario'}.",
                metadata={"event": "mark_reviewed"},
                timestamp=timestamp,
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
            create_system_comment(
                conn,
                entity_type="infonalia_dia",
                entity_id=dia_id,
                body=f"Día reabierto por {clean_text((self.current_user() or {}).get('display_name')) or 'administrador'}.",
                metadata={"event": "unmark_reviewed"},
                timestamp=timestamp,
            )
            refresh_dia_estado(conn, dia_id)
            row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            item = dia_to_dict(conn, row)

        self.send_json(item)

    def api_get_ai_summary(self, licitacion_id: int) -> None:
        try:
            with db_session() as conn:
                payload = get_ai_summary_payload(conn, licitacion_id)
        except AIFileSelectionError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        except Exception:
            self.send_json({"error": "No se pudo consultar el analisis IA."}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(payload)

    def api_list_ai_files(self, licitacion_id: int) -> None:
        config = get_ai_config()
        try:
            with db_session() as conn:
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if not row:
                    self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                    return
                payload = list_ai_files(
                    row,
                    max_documents=config.max_documents_per_analysis,
                    max_file_mb=config.max_file_mb,
                )
        except AIFileSelectionError as exc:
            self.send_json({"error": str(exc), "items": []}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(payload)

    def api_generate_ai_summary(self, licitacion_id: int, *, force: bool = False) -> None:
        if force and not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        selected_files = data.get("selected_files")
        if selected_files is not None and not isinstance(selected_files, list):
            self.send_json({"error": "selected_files debe ser una lista."}, HTTPStatus.BAD_REQUEST)
            return
        provider_name = clean_text(data.get("provider"))
        if provider_name and provider_name not in {"gemini", "codex_local", "disabled"}:
            self.send_json({"error": "Proveedor IA no válido."}, HTTPStatus.BAD_REQUEST)
            return
        notify_on_completion = bool(data.get("notify_on_completion"))
        notification_emails = data.get("notification_emails")
        if notification_emails is None and data.get("notification_email"):
            notification_emails = data.get("notification_email")
        job_id = 0
        try:
            with db_session() as conn:
                payload = request_ai_analysis(
                    conn,
                    licitacion_id,
                    requested_by=clean_text(user.get("username")),
                    force=force,
                    selected_files=selected_files,
                    provider_name=provider_name or None,
                    notify_on_completion=notify_on_completion,
                    notification_emails=notification_emails,
                )
                job_id = int(payload.get("job_id") or 0)
        except AIFileSelectionError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except EmailListError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        except Exception:
            self.send_json({"error": "No se pudo generar el analisis IA."}, HTTPStatus.BAD_REQUEST)
            return
        if job_id and payload.get("job_status") in {"pending", "queued", "deferred"}:
            with db_session() as conn:
                worker = start_ai_worker_for_job(conn, job_id)
            payload["worker"] = worker
            if not worker.get("ok"):
                with db_session() as conn:
                    payload = get_ai_summary_payload(conn, licitacion_id)
                    payload["worker"] = worker
        self.send_json(payload)

    def api_delete_ai_summary(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            with db_session() as conn:
                payload = delete_ai_summary(conn, licitacion_id)
                record_licitacion_history(
                    conn,
                    licitacion_id,
                    event_type="ai_summary_deleted",
                    old_value="summary",
                    new_value="",
                    user_id=clean_text(user.get("username")) or "Sistema",
                    timestamp=now_iso(),
                )
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        self.send_json(payload)

    def api_send_ai_summary_email(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        try:
            recipients = normalize_email_list(
                data.get("notification_emails") if "notification_emails" in data else data.get("to"),
                required=True,
            )
        except EmailListError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            summary_row = conn.execute(
                """
                SELECT *
                FROM ai_summaries
                WHERE licitacion_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (licitacion_id,),
            ).fetchone()
            payload = get_ai_summary_payload(conn, licitacion_id)
        if not payload.get("has_summary") or not payload.get("summary"):
            self.send_json({"error": "No hay un análisis IA útil para enviar."}, HTTPStatus.BAD_REQUEST)
            return
        if not summary_row or not int(summary_row["created_from_job_id"] or 0):
            self.send_json({"error": "El análisis IA no tiene job asociado para registrar el envío."}, HTTPStatus.BAD_REQUEST)
            return
        with db_session() as conn:
            result = generate_ai_summary_pdf_and_email(
                conn,
                licitacion_id=licitacion_id,
                recipients=recipients,
                requested_by=clean_text(user.get("username")) or "ui",
                now=now_iso,
                subject_override=shorten_text(data.get("subject"), 160),
                pdf_output_root=DATA_ROOT / "runtime" / "ai_summary_pdfs",
                smtp_factory=smtplib.SMTP,
                smtp_ssl_factory=smtplib.SMTP_SSL,
            )
            job_id = int(result.get("job_id") or summary_row["created_from_job_id"] or 0)
            status_payload = notification_status_payload(
                conn.execute(
                    "SELECT * FROM ai_analysis_notifications WHERE job_id = ? ORDER BY id ASC",
                    (job_id,),
                ).fetchall()
            )
        ok = int(result.get("sent") or 0) > 0 and int(result.get("error") or 0) == 0
        self.send_json({"ok": ok, "result": result, "notification_status": status_payload, "recipients": recipients})

    def api_save_ai_summary_pdf(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            summary_row = conn.execute(
                """
                SELECT *
                FROM ai_summaries
                WHERE licitacion_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (licitacion_id,),
            ).fetchone()
            if not summary_row:
                self.send_json({"error": "No hay un resumen IA disponible para guardar."}, HTTPStatus.BAD_REQUEST)
                return
            selected_documents = []
            job_id = int(summary_row["created_from_job_id"] or 0)
            if job_id:
                job_row = conn.execute(
                    """
                    SELECT selected_documents_json
                    FROM ai_analysis_jobs
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                if job_row and clean_text(job_row["selected_documents_json"]):
                    try:
                        selected_documents = json.loads(job_row["selected_documents_json"] or "[]")
                    except json.JSONDecodeError:
                        selected_documents = []
            try:
                summary_payload = json.loads(summary_row["summary_json"] or "{}")
            except json.JSONDecodeError:
                self.send_json({"error": "El resumen IA guardado no tiene un formato válido."}, HTTPStatus.BAD_REQUEST)
                return
            result = generate_ai_summary_pdf(
                row,
                summary_payload,
                selected_documents=selected_documents,
                generated_at=now_iso(),
                fallback_root=DATA_ROOT / "runtime" / "ai_summary_pdfs",
            )
            if not result.ok:
                self.send_json({"error": result.error or "No se pudo guardar el PDF del resumen IA."}, HTTPStatus.BAD_REQUEST)
                return
            record_licitacion_history(
                conn,
                licitacion_id,
                event_type="ai_summary_pdf_saved",
                old_value="",
                new_value=result.path,
                user_id=clean_text(user.get("username")) or "Sistema",
                timestamp=now_iso(),
            )
        self.send_json(
            {
                "ok": True,
                "path": result.path,
                "filename": result.filename,
                "used_fallback": bool(result.used_fallback),
                "warning": clean_text(result.warning),
                "message": (
                    "No se ha podido guardar en la carpeta de la licitación. "
                    "Se ha guardado en una ubicación alternativa."
                    if result.used_fallback
                    else "PDF guardado correctamente en la carpeta de la licitación."
                ),
            }
        )

    def api_get_ai_job(self, job_id: int) -> None:
        if not self.require_admin():
            return
        try:
            with db_session() as conn:
                payload = get_ai_job_payload(conn, job_id)
        except ValueError as exc:
            self.send_json(
                {"ok": False, "error_code": "JOB_NOT_FOUND", "error_message": str(exc), "error": str(exc)},
                HTTPStatus.NOT_FOUND,
            )
            return
        except Exception:
            LOGGER.exception("Error consultando job IA job_id=%s", job_id)
            self.send_json(
                {
                    "ok": False,
                    "error_code": "AI_QUEUE_ERROR",
                    "error_message": "No se pudo consultar el trabajo IA.",
                    "error": "No se pudo consultar el trabajo IA.",
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self.send_json(payload)

    def api_ai_queue(self) -> None:
        try:
            with db_session() as conn:
                payload = get_ai_queue_payload(conn)
        except Exception:
            LOGGER.exception("Error consultando Cola IA")
            self.send_json(
                {
                    "ok": False,
                    "error_code": "AI_QUEUE_ERROR",
                    "error_message": "No se pudo consultar la Cola IA.",
                    "error": "No se pudo consultar la Cola IA.",
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self.send_json(payload)

    def api_cancel_ai_job(self, job_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        username = clean_text(user.get("username")) or "ui"
        LOGGER.info("Cancelacion IA solicitada job_id=%s usuario=%s", job_id, username)
        try:
            with db_session() as conn:
                payload = cancel_ai_job(conn, job_id)
        except Exception:
            LOGGER.exception("Error cancelando job IA job_id=%s usuario=%s", job_id, username)
            self.send_json(
                {
                    "ok": False,
                    "job_id": job_id,
                    "error_code": "AI_CANCEL_ERROR",
                    "error_message": "No se pudo cancelar el trabajo IA.",
                    "error": "No se pudo cancelar el trabajo IA.",
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        if not payload.get("ok"):
            LOGGER.warning(
                "Cancelacion IA rechazada job_id=%s usuario=%s error_code=%s",
                job_id,
                username,
                payload.get("error_code"),
            )
            self.send_json(payload, HTTPStatus.NOT_FOUND if payload.get("error_code") == "JOB_NOT_FOUND" else HTTPStatus.BAD_REQUEST)
            return
        LOGGER.info(
            "Cancelacion IA resuelta job_id=%s usuario=%s estado_anterior=%s estado_nuevo=%s",
            job_id,
            username,
            payload.get("previous_status", ""),
            payload.get("status") or payload.get("job_status", ""),
        )
        self.send_json(payload)

    def api_dismiss_ai_job(self, job_id: int) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        username = clean_text(user.get("username")) or "ui"
        LOGGER.info("Ocultacion IA solicitada job_id=%s usuario=%s", job_id, username)
        try:
            with db_session() as conn:
                payload = dismiss_ai_job(conn, job_id, dismissed_by=username)
        except Exception:
            LOGGER.exception("Error ocultando job IA job_id=%s usuario=%s", job_id, username)
            self.send_json(
                {
                    "ok": False,
                    "job_id": job_id,
                    "error_code": "AI_DISMISS_ERROR",
                    "error_message": "No se pudo ocultar el trabajo IA.",
                    "error": "No se pudo ocultar el trabajo IA.",
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        if not payload.get("ok"):
            LOGGER.warning(
                "Ocultacion IA rechazada job_id=%s usuario=%s error_code=%s",
                job_id,
                username,
                payload.get("error_code"),
            )
            self.send_json(payload, HTTPStatus.NOT_FOUND if payload.get("error_code") == "JOB_NOT_FOUND" else HTTPStatus.BAD_REQUEST)
            return
        LOGGER.info(
            "Ocultacion IA resuelta job_id=%s usuario=%s estado=%s",
            job_id,
            username,
            payload.get("status", ""),
        )
        self.send_json(payload)

    def api_dismiss_finished_ai_jobs(self) -> None:
        if not self.require_admin():
            return
        user = self.current_user() or {}
        username = clean_text(user.get("username")) or "ui"
        LOGGER.info("Limpieza de trabajos IA terminados solicitada usuario=%s", username)
        try:
            with db_session() as conn:
                payload = dismiss_finished_ai_jobs(conn, dismissed_by=username)
        except Exception:
            LOGGER.exception("Error limpiando trabajos IA terminados usuario=%s", username)
            self.send_json(
                {
                    "ok": False,
                    "error_code": "AI_DISMISS_FINISHED_ERROR",
                    "error_message": "No se pudieron limpiar los trabajos IA terminados.",
                    "error": "No se pudieron limpiar los trabajos IA terminados.",
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        LOGGER.info(
            "Limpieza de trabajos IA terminados resuelta usuario=%s ocultados=%s",
            username,
            payload.get("dismissed", 0),
        )
        self.send_json(payload)

    def api_mark_stale_ai_jobs(self) -> None:
        if not self.require_admin():
            return
        config = get_ai_config()
        timeout = max(config.timeout_seconds, config.codex_timeout_seconds)
        with db_session() as conn:
            payload = mark_stale_ai_jobs(conn, timeout_seconds=timeout)
        self.send_json(payload)

    def api_start_ai_job(self, job_id: int) -> None:
        if not self.require_admin():
            return
        try:
            with db_session() as conn:
                existing = get_ai_job_payload(conn, job_id)
                status = str(existing.get("job_status") or "")
                if status not in {"pending", "queued", "deferred"}:
                    self.send_json(existing)
                    return
            with db_session() as conn:
                worker = start_ai_worker_for_job(conn, job_id)
            with db_session() as conn:
                payload = get_ai_job_payload(conn, job_id)
                payload["worker"] = worker
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        except Exception:
            self.send_json({"error": "No se pudo iniciar el worker IA."}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(payload)

    def api_list_ai_jobs(self) -> None:
        if not self.require_admin():
            return
        with db_session() as conn:
            items = list_ai_jobs(conn)
        self.send_json({"items": items})

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

    def api_send_prepared_notice_email(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        try:
            data = self.read_json()
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        subject = shorten_text(data.get("subject"), 120)
        body = clean_text(data.get("email_body"))
        if not subject:
            self.send_json({"error": "El asunto del aviso es obligatorio."}, HTTPStatus.BAD_REQUEST)
            return
        if not body:
            self.send_json({"error": "El mensaje del aviso es obligatorio."}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
            return

        settings = get_settings()
        recipient = clean_text(data.get("to")) or prepared_notice_recipient(settings)
        if not is_valid_email_address(recipient):
            self.send_json(
                {"error": "El email de destino del aviso de ficha preparada no es válido."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        sent_at, error = send_notification_email_with_settings(
            settings=settings,
            recipients=[recipient],
            subject=subject,
            body=body,
            html_body=render_notification_email_html(subject, body, None),
            logo_path=STATIC_ROOT / "logo-llangon.png",
            now=now_iso,
            smtp_factory=smtplib.SMTP,
            smtp_ssl_factory=smtplib.SMTP_SSL,
        )
        if error:
            print(f"No se pudo enviar aviso de ficha preparada {licitacion_id}: {error}", file=sys.stderr)
            self.send_json(
                {
                    "ok": False,
                    "error": error,
                    "message": "No se ha podido enviar el email. La licitación se ha guardado correctamente.",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        print(f"Aviso de ficha preparada enviado para licitacion {licitacion_id} a {recipient}", file=sys.stderr)
        self.send_json(
            {
                "ok": True,
                "sent_at": sent_at,
                "recipient": recipient,
                "message": "Email enviado correctamente.",
            }
        )

    def api_download_licitacion(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return
        try:
            data = self.read_json()
        except AttributeError:
            data = {}
        except json.JSONDecodeError as exc:
            self.send_json({"error": f"Solicitud no válida: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()

        if not row:
            self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
            return
        if is_anuncio_previo(row["tipo_publicacion"] if "tipo_publicacion" in row.keys() else ""):
            self.send_json(
                {"error": "Los anuncios previos no tienen documentación de licitación para descargar."},
                HTTPStatus.BAD_REQUEST,
            )
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

        base_status = dropbox_base_status()
        if not uses_dropbox_api_backend() and base_status.configured and not base_status.ok:
            self.send_json(
                {"error": base_status.error or "La carpeta base de Dropbox no es valida."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        allowed_destination_roots = download_allowed_destination_roots()

        try:
            destino_sugerido = validate_resolved_destination(resolve_destination_folder(row), allowed_destination_roots)
            folder_name_confirmed = clean_text(
                data.get("folder_name_confirmed")
                or data.get("create_folder_name")
            )
            if folder_name_confirmed:
                destino = validate_resolved_destination(
                    confirmed_download_destination(destino_sugerido, folder_name_confirmed),
                    allowed_destination_roots,
                )
                if destino.exists():
                    self.send_json(
                        {
                            "error": "La carpeta ya existe. Revisa el nombre o continúa si corresponde.",
                            "folder_exists": True,
                            "carpeta": str(destino),
                        },
                        HTTPStatus.CONFLICT,
                    )
                    return
            else:
                destino = destino_sugerido
                if not destino.exists():
                    self.send_json(
                        {
                            "needs_folder_confirmation": True,
                            "suggested_folder_name": destino.name,
                            "message": "La carpeta de esta licitación no existe. Revisa el nombre antes de crearla.",
                        }
                    )
                    return
                if not destino.is_dir():
                    self.send_json(
                        {"error": "La ruta de destino existe pero no es una carpeta."},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
        except DownloadSafetyError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as conn:
            request_result = create_download_job_request(
                conn,
                licitacion_id,
                timestamp=now_iso(),
                request_source=DOWNLOAD_REQUEST_SOURCE_MANUAL,
                request_action="manual_download",
                requested_by=clean_text((self.current_user() or {}).get("username")),
            )
            if not request_result.get("ok"):
                self.send_json({"error": clean_text(request_result.get("message")) or "No se pudo solicitar la descarga."}, HTTPStatus.BAD_REQUEST)
                return
            if clean_text(request_result.get("status")) == "already_pending":
                self.send_json(
                    {
                        "ok": True,
                        "message": clean_text(request_result.get("message")),
                        "job_id": request_result.get("job_id"),
                    }
                )
                return
            download_job_id = int(request_result.get("job_id") or 0)
            if download_job_id <= 0:
                self.send_json({"error": clean_text(request_result.get("message")) or "No se pudo crear el trabajo de descarga."}, HTTPStatus.BAD_REQUEST)
                return
            conn.execute(
                """
                UPDATE download_jobs
                SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE id = ?
                """,
                (DOWNLOAD_JOB_STATUS_RUNNING, now_iso(), now_iso(), download_job_id),
            )

        ruta_guardada = folder_path_for_storage(destino)
        http_status, payload = execute_download_for_destination(
            licitacion_id=licitacion_id,
            row=row,
            destino=destino,
            ruta_guardada=ruta_guardada,
            download_job_id=download_job_id,
            source_url=url,
        )
        if _download_completed_successfully(http_status, payload):
            payload["ai_summary_requests"] = start_email_ai_summary_requests_for_download(download_job_id)
            payload["telegram_notifications"] = notify_pending_email_action_telegram_events(
                licitacion_id=licitacion_id,
                download_job_id=download_job_id,
            )
        else:
            payload["ai_summary_requests"] = {
                "download_failed": mark_email_ai_summary_requests_download_failed(
                    download_job_id,
                    clean_text(payload.get("error")) or "La descarga necesaria para el resumen IA no pudo completarse.",
                )
            }
        self.send_json(payload, http_status)

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
                old_estado = row["estado"] or ""
                if normalize_licitacion_estado(row["estado"]) not in NURIA_VISIBLE_STATES:
                    self.send_json({"error": "Esta licitacion no esta en revision de Nuria."}, HTTPStatus.FORBIDDEN)
                    return
                timestamp = now_iso()
                conn.execute(
                    "UPDATE licitaciones SET estado = ?, updated_at = ? WHERE id = ?",
                    (estado, timestamp, licitacion_id),
                )
                if estado != old_estado:
                    record_licitacion_history(
                        conn,
                        licitacion_id,
                        event_type="estado",
                        old_value=old_estado,
                        new_value=estado,
                        user_id=clean_text(user.get("username")),
                        timestamp=timestamp,
                    )
                    create_system_comment(
                        conn,
                        entity_type="licitacion",
                        entity_id=licitacion_id,
                        body=f"Estado cambiado: {old_estado or 'Sin estado'} -> {estado or 'Sin estado'}",
                        metadata={"event_type": "estado", "old_value": old_estado, "new_value": estado},
                        timestamp=timestamp,
                    )
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if row and row["infonalia_dia_id"]:
                    refresh_dia_estado(conn, int(row["infonalia_dia_id"]))
                response = row_to_dict(row)
                apply_licitacion_list_metadata(conn, [response])
            self.send_json(response)
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
            "tipo_publicacion",
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
        if "tipo_publicacion" in updates:
            updates["tipo_publicacion"] = normalize_tipo_publicacion(updates["tipo_publicacion"])
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
                    if key == "estado":
                        create_system_comment(
                            conn,
                            entity_type="licitacion",
                            entity_id=licitacion_id,
                            body=f"Estado cambiado: {old_value or 'Sin estado'} -> {new_value or 'Sin estado'}",
                            metadata={"event_type": "estado", "old_value": old_value or "", "new_value": new_value or ""},
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
        response = row_to_dict(row)
        with db_session() as conn:
            apply_licitacion_list_metadata(conn, [response])
        if row and is_prepared_state_transition(old_row["estado"], row["estado"]):
            response["prepared_notice_preview"] = build_prepared_notice_preview(
                row,
                previous_state=old_row["estado"],
                current_state=row["estado"],
                user=user,
            )
        self.send_json(response)

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

                open_count = open_actuaciones_count(conn, licitacion_ids)
                if open_count:
                    self.send_json(
                        {
                            "ok": False,
                            "error": "No se puede borrar el Día Infonalia porque existen actuaciones abiertas vinculadas.",
                            "blocking": {"open_actuaciones": open_count},
                        },
                        HTTPStatus.CONFLICT,
                    )
                    return
                deleted_counts = delete_licitacion_dependents_with_counts(conn, licitacion_ids)
                deleted_counts["email_action_events"] = deleted_counts.get("email_action_events", 0) + sqlite_delete_if_table(
                    conn,
                    "email_action_events",
                    "review_id = ?",
                    [dia_id],
                )
                deleted_counts["email_action_codes"] = deleted_counts.get("email_action_codes", 0) + sqlite_delete_if_table(
                    conn,
                    "email_action_codes",
                    "review_id = ?",
                    [dia_id],
                )
                deleted_counts["day_comments_deleted"] = sqlite_update_if_table(
                    conn,
                    "comments",
                    "is_deleted = 1, deleted_at = ?, updated_at = ?",
                    "entity_type = 'infonalia_dia' AND entity_id = ?",
                    [now_iso(), now_iso(), dia_id],
                )
                deleted_counts["infonalia_email_imports_unlinked"] = sqlite_update_if_table(
                    conn,
                    "infonalia_email_imports",
                    "status = 'deleted', infonalia_dia_id = NULL, error_message = ?",
                    "infonalia_dia_id = ?",
                    [f"Día Infonalia {dia_id} eliminado; se permite reimportación controlada.", dia_id],
                )
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
                {
                    "ok": False,
                    "error": "No se pudo borrar el Día Infonalia por datos relacionados.",
                    "detail": clean_text(exc),
                },
                HTTPStatus.CONFLICT,
            )
            return
        except Exception as exc:
            print(f"Error inesperado al borrar Dia Infonalia {dia_id}: {exc}", file=sys.stderr)
            self.send_json(
                {
                    "ok": False,
                    "error": "No se pudo borrar el Día Infonalia. La operación se ha cancelado de forma segura.",
                    "detail": clean_text(exc),
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self.send_json(
            {
                "ok": True,
                "titulo": clean_text(day["titulo"]),
                "licitaciones_borradas": len(licitacion_ids),
                "deleted": {
                    "dia_id": dia_id,
                    "licitaciones": len(licitacion_ids),
                    **deleted_counts,
                },
            }
        )

    def send_login_page(self) -> None:
        path = STATIC_ROOT / "login.html"
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "No encontrado")
            return

        default_public_site_url = "https://llangon-web-publica-prueba.web.app/"
        public_site_url = clean_text(os.environ.get("LLANGON_PUBLIC_SITE_URL")) or default_public_site_url
        body = path.read_text(encoding="utf-8").replace(default_public_site_url, html.escape(public_site_url)).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_security_headers(is_private=True)
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
    print("Scheduler Monitor: runner independiente; usar python -m webapp.infonalia_webapp.monitor.scheduler --once")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run(
        host=os.environ.get("INFONALIA_HOST", "127.0.0.1"),
        port=int(os.environ.get("INFONALIA_PORT", "8787")),
    )
