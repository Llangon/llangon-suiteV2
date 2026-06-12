from __future__ import annotations

import base64
import hashlib
import hmac
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
from urllib import request as urlrequest
from urllib.parse import parse_qs, unquote, urlparse

try:
    from .csrf import generate_csrf_token, validate_csrf_token
except ImportError:
    from csrf import generate_csrf_token, validate_csrf_token

try:
    from .normalization import clean_text, bool_text, parse_date_value, parse_money, parse_time_value
except ImportError:
    from normalization import clean_text, bool_text, parse_date_value, parse_money, parse_time_value

try:
    from .formatting import format_date_es, format_datetime_es
except ImportError:
    from formatting import format_date_es, format_datetime_es

try:
    from .folder_names import (
        expediente_folder_text,
        extract_hospital_phrase,
        extract_municipio_from_organismo,
        extract_objeto_folder_key,
        extract_residencia_phrase,
        folder_text,
        safe_folder_name,
        short_folder_phrase,
    )
except ImportError:
    from folder_names import (
        expediente_folder_text,
        extract_hospital_phrase,
        extract_municipio_from_organismo,
        extract_objeto_folder_key,
        extract_residencia_phrase,
        folder_text,
        safe_folder_name,
        short_folder_phrase,
    )

try:
    from .url_helpers import detectar_plataforma, normalize_url, should_update_url
except ImportError:
    from url_helpers import detectar_plataforma, normalize_url, should_update_url

try:
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
    from .news_helpers import NEWS_STATUSES, news_to_dict, normalize_news_status, slugify
except ImportError:
    from news_helpers import NEWS_STATUSES, news_to_dict, normalize_news_status, slugify

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
    from .ai_preview_helpers import (
        extract_centros_from_text,
        extract_keyword_context,
        extract_lotes_from_text,
        preview_payload_to_text,
    )
except ImportError:
    from ai_preview_helpers import (
        extract_centros_from_text,
        extract_keyword_context,
        extract_lotes_from_text,
        preview_payload_to_text,
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
        validate_upload_filename,
        validate_upload_size,
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
        validate_upload_filename,
        validate_upload_size,
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


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = os.path.expandvars(value)


load_env_file()


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable obligatoria {name}. Configúrala en el archivo .env local.")
    return value


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
SMTP_USE_TLS = os.environ.get("INFONALIA_SMTP_TLS", "1") != "0"
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


ESTADOS_ORDEN = [
    "Pendiente",
    "Descartada por mí",
    "Pendiente Nuria",
    "Descartar",
    "Descargar",
    "Hacer",
]
ESTADOS_VALIDOS = set(ESTADOS_ORDEN)
NURIA_ESTADOS = ["Pendiente Nuria", "Descartar", "Descargar", "Hacer"]
NURIA_ESTADOS_VALIDOS = set(NURIA_ESTADOS)
NURIA_LICITACIONES_ESTADOS = ["Descargar", "Hacer"]
CALENDARIO_ESTADOS = ["Pendiente Nuria", "Descargar", "Hacer"]

ESTADO_LABELS = {
    "Pendiente": "Pendiente",
    "Descartada por mí": "Descartada por mí",
    "Pendiente Nuria": "Pendiente de revisión",
    "Descartar": "Descartada",
    "Descargar": "Solo descargar",
    "Hacer": "Preparar licitación",
}

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
    "smtp_tls": "1" if SMTP_USE_TLS else "0",
    "smtp_ssl": "1" if SMTP_USE_SSL else "0",
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
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")
    signature = hmac.new(get_secret(), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded_payload}.{signature}"


def make_token(
    username: str,
    role: str,
    csrf_token: str | None = None,
    issued_at: int | None = None,
) -> str:
    payload = {
        "u": username,
        "r": role,
        "iat": int(time.time()) if issued_at is None else int(issued_at),
        "csrf": csrf_token or generate_csrf_token(),
    }
    return encode_token_payload(payload)


def read_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None

    encoded_payload, signature = token.rsplit(".", 1)
    expected = hmac.new(get_secret(), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        padded = encoded_payload + ("=" * (-len(encoded_payload) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:
        return None

    issued_at = int(payload.get("iat", 0))
    if issued_at + SESSION_MAX_AGE_SECONDS < int(time.time()):
        return None
    return payload


def db() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session():
    conn = db()
    try:
        yield conn
        conn.commit()
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
                estado TEXT NOT NULL DEFAULT 'Pendiente',
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
        seed_users_and_settings(conn)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        clean_text(password).encode("utf-8"),
        salt.encode("ascii"),
        120_000,
    ).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(stored: object, password: object) -> bool:
    stored_text = clean_text(stored)
    password_text = clean_text(password)
    if not stored_text:
        return False
    if stored_text.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest = stored_text.split("$", 2)
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password_text.encode("utf-8"),
            salt.encode("ascii"),
            120_000,
        ).hex()
        return hmac.compare_digest(candidate, digest)
    return hmac.compare_digest(stored_text, password_text)


def seed_users_and_settings(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    for user in USERS.values():
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
                hash_password(clean_text(user.get("password"))),
                clean_text(user.get("role")) or "nuria",
                clean_text(user.get("display_name")) or username,
                clean_text(user.get("email")),
                timestamp,
                timestamp,
            ),
        )

    for key, value in DEFAULT_SETTINGS.items():
        exists = conn.execute("SELECT key FROM app_settings WHERE key = ?", (key,)).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, clean_text(value), timestamp),
        )


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    item = {key: row[key] for key in row.keys()}
    if not clean_text(item.get("plataforma")):
        item["plataforma"] = detectar_plataforma(clean_text(item.get("enlace_perfil")))
    item["enlace_perfil"] = normalize_url(item.get("enlace_perfil"))
    item["enlace_infonalia"] = normalize_url(item.get("enlace_infonalia"))
    item["ruta_carpeta"] = folder_path_for_storage(item.get("ruta_carpeta"))
    return item


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
    timestamp = now_iso()
    for key, value in settings.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, clean_text(value), timestamp),
        )


def maintenance_mode_enabled() -> bool:
    return bool_text(get_setting("maintenance_mode", "0"))


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def find_dropbox_root() -> Path | None:
    configured = clean_text(os.environ.get("INFONALIA_DROPBOX_ROOT"))
    candidates = []
    if configured:
        candidates.append(Path(configured))

    home = Path.home()
    candidates.extend(
        [
            home / "Dropbox" / "00000 LLANGON",
            home / "Dropbox",
        ]
    )

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def is_internal_download_path(value: object) -> bool:
    text = clean_text(value)
    if not text:
        return False
    path = Path(text)
    if not path.is_absolute():
        return False
    return path_is_relative_to(path, DOWNLOAD_ROOT)


def normalize_relative_folder_path(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parts = [
        safe_folder_name(part)
        for part in re.split(r"[\\/]+", text)
        if clean_text(part) and clean_text(part) not in {".", ".."}
    ]
    return str(Path(*parts)) if parts else ""


def dropbox_relative_path(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value).strip('"')
    if not text:
        return ""

    path = Path(text)
    if not path.is_absolute():
        return normalize_relative_folder_path(text)

    root = dropbox_root or find_dropbox_root()
    if root:
        try:
            return normalize_relative_folder_path(str(path.resolve().relative_to(root.resolve())))
        except ValueError:
            pass

    parts = [
        part.strip()
        for part in re.split(r"[\\/]+", text)
        if part.strip() and not re.fullmatch(r"[A-Za-z]:", part.strip())
    ]
    lower_parts = [part.lower() for part in parts]

    for marker in ("00000 llangon", "dropbox"):
        if marker in lower_parts:
            index = lower_parts.index(marker)
            relative_parts = parts[index + 1 :]
            if relative_parts:
                return normalize_relative_folder_path("\\".join(relative_parts))

    return ""


def folder_path_for_storage(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value)
    if not text:
        return ""

    relative = dropbox_relative_path(text, dropbox_root)
    if relative:
        return relative
    return text


def get_or_create_dia(conn: sqlite3.Connection, fecha_infonalia: str) -> int:
    fecha = clean_text(fecha_infonalia) or "sin-fecha"
    row = conn.execute("SELECT id FROM infonalia_dias WHERE fecha = ?", (fecha,)).fetchone()
    if row:
        return int(row["id"])

    timestamp = now_iso()
    title_date = "sin fecha" if fecha == "sin-fecha" else format_date_es(fecha)
    cur = conn.execute(
        """
        INSERT INTO infonalia_dias (fecha, titulo, estado, created_at, updated_at)
        VALUES (?, ?, 'Importado', ?, ?)
        """,
        (fecha, f"Infonalia {title_date}", timestamp, timestamp),
    )
    return int(cur.lastrowid)


def is_nuria_update_pending(row: sqlite3.Row | dict | None) -> bool:
    if not row:
        return False
    dirty_at = clean_text(row_get(row, "nuria_dirty_at"))
    sent_at = clean_text(row_get(row, "enviado_nuria_at"))
    return bool(dirty_at and (not sent_at or dirty_at >= sent_at))


def mark_dia_nuria_dirty(conn: sqlite3.Connection, dia_id: int | None, timestamp: str | None = None) -> None:
    if not dia_id:
        return
    timestamp = timestamp or now_iso()
    conn.execute(
        "UPDATE infonalia_dias SET nuria_dirty_at = ?, updated_at = ? WHERE id = ?",
        (timestamp, timestamp, dia_id),
    )


def refresh_dia_estado(conn: sqlite3.Connection, dia_id: int) -> None:
    day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    rows = conn.execute(
        """
        SELECT estado, COUNT(*) AS total
        FROM licitaciones
        WHERE infonalia_dia_id = ?
        GROUP BY estado
        """,
        (dia_id,),
    ).fetchall()
    counts = {row["estado"]: row["total"] for row in rows}
    total = sum(counts.values())
    pendientes = counts.get("Pendiente", 0)
    pendientes_nuria = counts.get("Pendiente Nuria", 0)
    decisiones_nuria = counts.get("Descartar", 0) + counts.get("Descargar", 0) + counts.get("Hacer", 0)
    enviado_nuria_at = clean_text(day["enviado_nuria_at"]) if day and "enviado_nuria_at" in day.keys() else ""
    reviewed_at = clean_text(day["reviewed_at"]) if day and "reviewed_at" in day.keys() else ""
    nuria_pending_update = is_nuria_update_pending(day)

    if total == 0:
        estado = "Importado"
    elif pendientes > 0:
        estado = "En filtrado interno"
    elif reviewed_at and not nuria_pending_update:
        estado = "Completado"
    elif nuria_pending_update and enviado_nuria_at:
        estado = "Cambios pendientes para Nuria"
    elif not enviado_nuria_at and (pendientes_nuria > 0 or decisiones_nuria > 0):
        estado = "Listo para enviar a Nuria"
    elif pendientes_nuria > 0 and enviado_nuria_at:
        estado = "Pendiente de revisión Nuria"
    elif decisiones_nuria > 0:
        estado = "Revisión parcial"
    else:
        estado = "Completado"

    conn.execute(
        "UPDATE infonalia_dias SET estado = ?, updated_at = ? WHERE id = ?",
        (estado, now_iso(), dia_id),
    )


def dia_to_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    counts_rows = conn.execute(
        """
        SELECT estado, COUNT(*) AS total
        FROM licitaciones
        WHERE infonalia_dia_id = ?
        GROUP BY estado
        """,
        (row["id"],),
    ).fetchall()
    counts = {count_row["estado"]: count_row["total"] for count_row in counts_rows}
    total = sum(counts.values())
    decisiones_nuria = counts.get("Descartar", 0) + counts.get("Descargar", 0) + counts.get("Hacer", 0)
    nuria_total = counts.get("Pendiente Nuria", 0) + decisiones_nuria
    nuria_pending_update = is_nuria_update_pending(row)
    return {
        "id": row["id"],
        "fecha": row["fecha"],
        "fecha_formateada": format_date_es(row["fecha"]),
        "titulo": row["titulo"],
        "estado": row["estado"],
        "total": total,
        "total_nuria": nuria_total,
        "pendientes": counts.get("Pendiente", 0),
        "descartadas_mi": counts.get("Descartada por mí", 0),
        "pendientes_nuria": counts.get("Pendiente Nuria", 0),
        "decisiones_nuria": decisiones_nuria,
        "descartadas_nuria": counts.get("Descartar", 0),
        "solo_descargar": counts.get("Descargar", 0),
        "preparar_licitacion": counts.get("Hacer", 0),
        "descargadas": 0,
        "enviado_nuria_at": row["enviado_nuria_at"] if "enviado_nuria_at" in row.keys() else "",
        "fecha_envio_nuria": format_datetime_es(row["enviado_nuria_at"]) if "enviado_nuria_at" in row.keys() else "",
        "nuria_dirty_at": row["nuria_dirty_at"] if "nuria_dirty_at" in row.keys() else "",
        "fecha_cambio_nuria": format_datetime_es(row["nuria_dirty_at"]) if "nuria_dirty_at" in row.keys() else "",
        "nuria_pending_update": nuria_pending_update,
        "reviewed_at": row["reviewed_at"] if "reviewed_at" in row.keys() else "",
        "fecha_revision": format_datetime_es(row["reviewed_at"]) if "reviewed_at" in row.keys() else "",
        "counts": counts,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


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


def import_csv_content(content: bytes) -> dict:
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
        for row in rows:
            payload = build_payload_from_csv_row(row, mapping)
            if not clean_text(payload.get("expediente")):
                without_expediente += 1
                continue
            dia_id = get_or_create_dia(conn, clean_text(payload.get("fecha_infonalia")))
            touched_days.add(dia_id)
            result = insert_payload(conn, payload, dia_id)
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
                "estado": "Pendiente",
                "comentario": "",
                "ruta_carpeta": "",
            }
        )

    return payloads


def find_pdftotext() -> Path | None:
    configured = clean_text(os.environ.get("INFONALIA_PDFTOTEXT"))
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            PROJECT_ROOT / "pdftotext.exe",
            APP_ROOT / "pdftotext.exe",
            Path.home() / "Dropbox" / "00000 LLANGON" / "Infonalia" / "pdftotext.exe",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def download_to_path(url: str, destination: Path) -> bool:
    try:
        req = urlrequest.Request(
            normalize_url(url),
            headers={"User-Agent": "Mozilla/5.0 InfonaliaWeb"},
        )
        with urlrequest.urlopen(req, timeout=30) as response:
            destination.write_bytes(response.read())
        return destination.exists() and destination.stat().st_size > 0
    except Exception:
        return False


def pdf_to_text(pdf_path: Path) -> str:
    exe = find_pdftotext()
    if not exe:
        return ""
    txt_path = pdf_path.with_suffix(".txt")
    try:
        subprocess.run(
            [str(exe), "-layout", str(pdf_path), str(txt_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def enrich_from_infonalia_pdf(url: str, fecha_limite: str) -> dict[str, str]:
    temp_dir = DATA_ROOT / "tmp_pdf"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = temp_dir / f"infonalia_{time.time_ns()}.pdf"
    if not download_to_path(url, pdf_path):
        return {}
    texto = pdf_to_text(pdf_path)
    return {
        "tipo": extract_tipo_contrato(texto),
        "hora_limite": extract_hora_limite_from_text(texto, fecha_limite),
    }


def import_msg_content(content: bytes, enrich_pdf: bool = True) -> dict:
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
        dia_id = get_or_create_dia(conn, fecha_infonalia)
        for payload in payloads:
            result = insert_payload(conn, payload, dia_id)
            if result == "inserted":
                imported += 1
                mark_dia_nuria_dirty(conn, dia_id)
            elif result == "updated":
                updated += 1
                mark_dia_nuria_dirty(conn, dia_id)
            else:
                skipped += 1
        refresh_dia_estado(conn, dia_id)

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


def folder_descriptor(row: sqlite3.Row | dict) -> str:
    provincia = folder_text(row_get(row, "provincia"))
    municipio = extract_municipio_from_organismo(row_get(row, "organismo"), provincia)
    objeto_key = extract_objeto_folder_key(row_get(row, "objeto"))

    pieces = []
    if municipio and municipio != provincia and not objeto_key.startswith(municipio):
        pieces.append(municipio)
    if objeto_key:
        pieces.append(objeto_key)

    descriptor = " ".join(piece for piece in pieces if piece)
    return safe_folder_name(descriptor) if descriptor else ""


def row_get(row: sqlite3.Row | dict, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError):
        return ""


def get_nombre_mes(mes_numero: int) -> str:
    meses = [
        "",
        "ENERO",
        "FEBRERO",
        "MARZO",
        "ABRIL",
        "MAYO",
        "JUNIO",
        "JULIO",
        "AGOSTO",
        "SEPTIEMBRE",
        "OCTUBRE",
        "NOVIEMBRE",
        "DICIEMBRE",
    ]
    if 1 <= mes_numero <= 12:
        return meses[mes_numero]
    return ""


def default_dropbox_folder(row: sqlite3.Row | dict, dropbox_root: Path) -> Path:
    expediente = expediente_folder_text(row_get(row, "expediente"))
    provincia = folder_text(row_get(row, "provincia"))
    descriptor = folder_descriptor(row)
    fecha_limite = clean_text(row_get(row, "fecha_limite"))
    hora = parse_time_value(row_get(row, "hora_limite")).replace(":", "")

    try:
        fecha = datetime.strptime(fecha_limite, "%Y-%m-%d")
    except ValueError:
        label = safe_folder_name(f"{provincia} {descriptor} {expediente}".strip())
        return dropbox_root / "Descargas Infonalia" / label

    mes_nombre = get_nombre_mes(fecha.month)
    carpeta_mes = f"{fecha.month:02d} {mes_nombre}"
    piezas = [
        f"{fecha.day:02d}",
        mes_nombre,
        hora,
        provincia,
        descriptor,
        expediente,
    ]
    carpeta_final = safe_folder_name(" ".join(pieza for pieza in piezas if pieza))
    return dropbox_root / f"{fecha.year:04d}" / carpeta_mes / carpeta_final


def resolve_destination_folder(row: sqlite3.Row | dict) -> Path:
    ruta = clean_text(row["ruta_carpeta"])
    dropbox_root = find_dropbox_root()

    if ruta:
        relative = dropbox_relative_path(ruta, dropbox_root)
        if relative and dropbox_root:
            return dropbox_root / relative

        candidate = Path(ruta)
        if candidate.is_absolute():
            if is_internal_download_path(candidate) and dropbox_root:
                return default_dropbox_folder(row, dropbox_root)
            return candidate

        if dropbox_root:
            return dropbox_root / normalize_relative_folder_path(ruta)

    if dropbox_root:
        return default_dropbox_folder(row, dropbox_root)

    label = f"{row_get(row, 'fecha_limite') or row_get(row, 'id')} {row_get(row, 'expediente')}"
    return DOWNLOAD_ROOT / safe_folder_name(label)


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


def write_http_url(folder: Path, url: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "HTTP.url").write_text(
        "[InternetShortcut]\n" f"URL={url}\n",
        encoding="utf-8",
    )


def build_ai_preview_payload(licitacion_id: int) -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            raise ValueError("Licitación no encontrada")

    objeto = clean_text(row["objeto"])
    text_excerpt = objeto
    lotes = extract_lotes_from_text(objeto)
    criterios = extract_keyword_context(
        text_excerpt,
        ["criterios de adjudicación", "criterios adjudicación", "precio", "calidad"],
    )
    ejecucion = extract_keyword_context(
        text_excerpt,
        ["condiciones especiales de ejecución", "criterios especiales de ejecución", "condición especial"],
    )
    centros = extract_centros_from_text(row, text_excerpt)

    fecha_limite = " ".join(
        part for part in [format_date_es(row["fecha_limite"]), clean_text(row["hora_limite"])] if part
    )
    cabecera = {
        "Expediente": clean_text(row["expediente"]),
        "Objeto": objeto,
        "Organismo": clean_text(row["organismo"]),
        "Provincia": clean_text(row["provincia"]),
        "Tipo": clean_text(row["tipo"]),
        "Presupuesto": f"{float(row['presupuesto']):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".") if row["presupuesto"] is not None else "",
        "Fecha límite": fecha_limite,
        "Plataforma": clean_text(row["plataforma"]) or detectar_plataforma(clean_text(row["enlace_perfil"])),
    }

    summary_parts = []
    if cabecera["Tipo"]:
        summary_parts.append(f"Contrato de {cabecera['Tipo'].lower()}")
    if cabecera["Organismo"]:
        summary_parts.append(f"promovido por {cabecera['Organismo']}")
    if cabecera["Fecha límite"]:
        summary_parts.append(f"con presentación hasta {cabecera['Fecha límite']}")
    resumen = " ".join(summary_parts)
    if resumen:
        resumen += "."
    else:
        resumen = "No hay datos suficientes para generar un resumen automático fiable."

    generated_at = now_iso()
    return {
        "licitacion_id": licitacion_id,
        "generated_at": generated_at,
        "generated_at_formatted": format_datetime_es(generated_at),
        "cabecera": cabecera,
        "centros": centros,
        "lotes": lotes,
        "criterios_adjudicacion": criterios,
        "criterios_ejecucion": ejecucion,
        "resumen": resumen,
        "nota": "Resumen automático orientativo generado con los datos ya guardados en la ficha.",
    }


def notification_recipients(usuario_destino: str | None) -> list[str]:
    destinatario = clean_text(usuario_destino)
    if destinatario:
        user = get_user_record(destinatario)
        users = [user] if user and user.get("active") else []
    else:
        users = list_user_records(active_only=True)
    emails = []
    for user in users:
        email = clean_text(user.get("email"))
        if email and email not in emails:
            emails.append(email)
    return emails


def notification_body_parts(cuerpo: str) -> tuple[list[str], list[tuple[str, str]]]:
    paragraphs: list[str] = []
    details: list[tuple[str, str]] = []

    for raw_line in (cuerpo or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue

        if ":" in line:
            label, value = line.split(":", 1)
            label = clean_text(label)
            value = clean_text(value)
            if label and value and len(label) <= 45:
                details.append((label, value))
                continue

        paragraphs.append(line)

    return paragraphs, details


PLATFORM_URL = os.environ.get("INFONALIA_PLATFORM_URL", "").strip()


def parse_day_review_notification(cuerpo: str) -> dict[str, object] | None:
    total = ""
    pendientes = ""
    intro_lines: list[str] = []
    pending_items: list[dict[str, str]] = []
    no_interesting = False

    for raw_line in (cuerpo or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if line.startswith("Total de licitaciones del día:"):
            total = clean_text(line.split(":", 1)[1])
            continue
        if line.startswith("Licitaciones pendientes de revisión:"):
            pendientes = clean_text(line.split(":", 1)[1])
            continue
        if line == "NO HAY LICITACIONES INTERESANTES":
            no_interesting = True
            continue
        if line.startswith("- "):
            parts = [clean_text(part) for part in line[2:].split(" | ")]
            if len(parts) >= 3:
                pending_items.append(
                    {
                        "expediente": parts[0],
                        "titulo": parts[1],
                        "fecha_hora": parts[2],
                    }
                )
            continue
        if line != "Listado de licitaciones pendientes:":
            intro_lines.append(line)

    if not total and not pendientes and not no_interesting and not pending_items:
        return None

    return {
        "intro": intro_lines,
        "total": total or "0",
        "pendientes": pendientes or "0",
        "no_interesting": no_interesting,
        "pending_items": pending_items,
    }


def render_notification_email_html(asunto: str, cuerpo: str, usuario_destino: str | None) -> str:
    parsed_day_review = None
    paragraphs, details = notification_body_parts(cuerpo)
    safe_subject = html.escape(clean_text(asunto) or "Notificación")
    recipient_label = clean_text(usuario_destino) or "Todos los usuarios"
    recipient_label = html.escape(recipient_label)
    date_label = html.escape(format_datetime_es(now_iso()))
    action_button_html = ""

    if "disponible para revisar" in clean_text(asunto).lower() and PLATFORM_URL:
        parsed_day_review = parse_day_review_notification(cuerpo)
        action_button_html = (
            f"<div style='margin:16px 0 18px 0;'>"
            f"<a href='{html.escape(PLATFORM_URL)}' "
            "style='display:inline-block; background:#19b51f; color:#ffffff; text-decoration:none; "
            "padding:11px 18px; border-radius:8px; font-size:14px; font-weight:800;'>"
            "Acceder a la plataforma"
            "</a>"
            "</div>"
        )

    if parsed_day_review:
        intro_html = "".join(
            f"<p style='margin:0 0 10px 0; line-height:1.45;'>{html.escape(paragraph)}</p>"
            for paragraph in parsed_day_review["intro"]
        )
        metrics_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin-top:18px; "
            "border:1px solid #d9e2ec; border-radius:10px; overflow:hidden;'>"
            "<tr>"
            "<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase; border-bottom:1px solid #e4eaf0;'>Total de licitaciones del día</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; border-bottom:1px solid #e4eaf0; text-align:right;'>{html.escape(str(parsed_day_review['total']))}</td>"
            "</tr>"
            "<tr>"
            "<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase;'>Licitaciones pendientes de revisión</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; text-align:right;'>{html.escape(str(parsed_day_review['pendientes']))}</td>"
            "</tr>"
            "</table>"
        )
        if parsed_day_review["no_interesting"]:
            pending_html = (
                "<div style='margin-top:18px; padding:16px 18px; background:#f1fff2; border:1px solid #d7e7d8; "
                "border-radius:10px; color:#0e7f15; font-size:15px; font-weight:800;'>"
                "NO HAY LICITACIONES INTERESANTES"
                "</div>"
            )
        else:
            rows = "".join(
                "<tr>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; font-weight:700; vertical-align:top;'>{html.escape(item['expediente'])}</td>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; vertical-align:top;'>{html.escape(item['titulo'])}</td>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; vertical-align:top; white-space:nowrap;'>{html.escape(item['fecha_hora'])}</td>"
                "</tr>"
                for item in parsed_day_review["pending_items"]
            )
            pending_html = (
                "<div style='margin-top:18px;'>"
                "<p style='margin:0 0 10px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;'>Listado de licitaciones pendientes</p>"
                "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; border:1px solid #d9e2ec; border-radius:10px; overflow:hidden;'>"
                "<tr>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Expediente</th>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Título</th>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Fecha y hora de presentación</th>"
                "</tr>"
                f"{rows}"
                "</table>"
                "</div>"
            )
        body_html = f"{intro_html}{metrics_html}{pending_html}"
        details_html = ""
    elif paragraphs:
        body_html = "".join(
            f"<p style='margin:0 0 10px 0; line-height:1.45;'>{html.escape(paragraph)}</p>"
            for paragraph in paragraphs
        )
    else:
        body_html = "<p style='margin:0; line-height:1.45;'>Tienes una nueva notificación en el panel privado.</p>"

    if not parsed_day_review and details:
        detail_rows = "".join(
            "<tr>"
            f"<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase; border-bottom:1px solid #e4eaf0;'>{html.escape(label)}</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; border-bottom:1px solid #e4eaf0; text-align:right;'>{html.escape(value)}</td>"
            "</tr>"
            for label, value in details
        )
        details_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin-top:18px; border:1px solid #d9e2ec;'>"
            f"{detail_rows}"
            "</table>"
        )
    elif not parsed_day_review:
        details_html = ""

    return f"""<!doctype html>
<html lang="es">
  <body style="margin:0; padding:0; background:#f5f7fb; font-family:Calibri, Segoe UI, Arial, sans-serif; color:#1f2937;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fb; padding:28px 14px;">
      <tr>
        <td align="center">
          <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px; background:#ffffff; border:1px solid #d9e2ec; border-radius:10px; overflow:hidden;">
            <tr>
              <td style="padding:24px 28px; border-bottom:1px solid #d9e2ec;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="vertical-align:middle;">
                      <p style="margin:0 0 4px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">Llangón Web App</p>
                      <h1 style="margin:0; color:#1f2937; font-size:22px; line-height:1.2;">Nueva notificación</h1>
                    </td>
                    <td align="right" style="vertical-align:middle;">
                      <img src="cid:llangon-logo" alt="Asesores Llangón" style="display:block; max-width:170px; height:auto;">
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:26px 28px;">
                {action_button_html}
                <table width="100%" cellpadding="0" cellspacing="0" style="border-left:5px solid #2dad2c; background:#ffffff;">
                  <tr>
                    <td style="padding:0 0 0 18px;">
                      <p style="margin:0 0 8px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">Asunto</p>
                      <h2 style="margin:0 0 18px 0; color:#1f2937; font-size:20px; line-height:1.25;">{safe_subject}</h2>
                      <div style="margin:0 0 18px 0; color:#1f2937; font-size:15px;">
                        {body_html}
                      </div>
                      {details_html}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 28px; background:#eaf7ea; border-top:1px solid #d9e2ec;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="color:#1f7a4d; font-size:13px; font-weight:700;">Destinatario: {recipient_label}</td>
                    <td align="right" style="color:#667085; font-size:13px;">{date_label}</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px; color:#667085; font-size:12px; line-height:1.4;">
                Este correo se ha generado automáticamente desde el panel privado de Asesores Llangón.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def attach_notification_logo(message: EmailMessage) -> None:
    logo_path = STATIC_ROOT / "logo-llangon.png"
    if not logo_path.exists():
        return

    try:
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<llangon-logo>",
        )
    except Exception:
        return


def send_notification_email(usuario_destino: str | None, asunto: str, cuerpo: str) -> tuple[str | None, str | None]:
    settings = get_settings()
    smtp_host = clean_text(settings.get("smtp_host"))
    smtp_port = int(clean_text(settings.get("smtp_port")) or "587")
    smtp_user = clean_text(settings.get("smtp_user"))
    smtp_password = clean_text(settings.get("smtp_password"))
    smtp_from = clean_text(settings.get("smtp_from")) or smtp_user
    smtp_use_ssl = bool_text(settings.get("smtp_ssl"))
    smtp_use_tls = bool_text(settings.get("smtp_tls", "1"))
    recipients = notification_recipients(usuario_destino)
    if not smtp_host:
        return None, "SMTP no configurado"
    if not smtp_from:
        return None, "Remitente SMTP no configurado"
    if not recipients:
        return None, "El usuario de destino no tiene email configurado"

    message = EmailMessage()
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = asunto
    message.set_content(cuerpo or asunto)
    message.add_alternative(
        render_notification_email_html(asunto, cuerpo or asunto, usuario_destino),
        subtype="html",
    )
    attach_notification_logo(message)

    try:
        if smtp_use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        with server:
            if smtp_use_tls and not smtp_use_ssl:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return now_iso(), None
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == 10013:
            return None, (
                "Windows ha bloqueado la conexión SMTP saliente "
                f"({smtp_host}:{smtp_port}). Revisa firewall, antivirus, proxy o permisos de red."
            )
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


def create_notification(
    conn: sqlite3.Connection,
    usuario_origen: str | None,
    usuario_destino: str | None,
    asunto: str,
    cuerpo: str,
    ficheros_adjuntos: str = "",
) -> int:
    sent_at, email_error = send_notification_email(usuario_destino, asunto, cuerpo)
    timestamp = now_iso()
    cur = conn.execute(
        """
        INSERT INTO notificaciones (
            fecha_hora,
            usuario_origen,
            usuario_destino,
            asunto,
            cuerpo,
            ficheros_adjuntos,
            email_sent_at,
            email_error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            clean_text(usuario_origen),
            clean_text(usuario_destino),
            clean_text(asunto),
            cuerpo,
            clean_text(ficheros_adjuntos),
            sent_at,
            email_error,
        ),
    )
    return int(cur.lastrowid)


def extract_multipart_filename(headers: bytes) -> str | None:
    headers_text = headers.decode("utf-8", errors="replace")
    quoted = re.search(r'filename="(?P<filename>[^"]*)"', headers_text)
    if quoted:
        return quoted.group("filename")
    plain = re.search(r"filename=(?P<filename>[^;\r\n]+)", headers_text)
    if plain:
        return plain.group("filename").strip().strip('"')
    return None


def extract_multipart_file(
    content_type: str,
    body: bytes,
    field_name: str,
    *,
    allowed_extensions: set[str] | None = None,
    max_upload_bytes: int | None = None,
) -> bytes:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("No se ha recibido un fichero válido.")

    boundary = match.group("boundary").strip().strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    for part in body.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        headers, _, data = part.partition(b"\r\n\r\n")
        if not data:
            continue
        if f'name="{field_name}"'.encode("utf-8") in headers:
            if allowed_extensions is not None:
                validate_upload_filename(extract_multipart_filename(headers), allowed_extensions)
            payload = data.rstrip(b"\r\n")
            if max_upload_bytes is not None:
                validate_upload_size(len(payload), max_upload_bytes)
            return payload

    raise ValueError("No se ha encontrado el fichero CSV en la petición.")


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
        elif path == "/api/licitaciones":
            self.api_list_licitaciones(parsed.query)
        elif path == "/api/notificaciones":
            self.api_list_notificaciones(parsed.query)
        elif path == "/api/config":
            self.api_get_config()
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
        elif path == "/api/config/users":
            self.api_create_user()
        elif path == "/api/config/test-smtp":
            self.api_test_smtp()
        elif path == "/api/news":
            self.api_create_news()
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

        if path.startswith("/api/licitaciones/"):
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
        if method == "POST":
            if path in {
                "/api/licitaciones",
                "/api/config/users",
                "/api/config/test-smtp",
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
            ):
                return True
            return False
        if method == "PATCH":
            return (
                path.startswith("/api/licitaciones/")
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
        public_settings = {
            "maintenance_mode": settings.get("maintenance_mode", "0"),
            "smtp_host": settings.get("smtp_host", ""),
            "smtp_port": settings.get("smtp_port", "587"),
            "smtp_user": settings.get("smtp_user", ""),
            "smtp_from": settings.get("smtp_from", ""),
            "smtp_tls": settings.get("smtp_tls", "1"),
            "smtp_ssl": settings.get("smtp_ssl", "0"),
            "smtp_password_set": bool(clean_text(settings.get("smtp_password"))),
        }
        return {
            "users": list_user_records(active_only=False),
            "settings": public_settings,
        }

    def api_get_config(self) -> None:
        if not self.require_admin():
            return
        self.send_json(self.config_payload())

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
        title = clean_text(data.get("title"))
        if not title:
            raise ValueError("El título es obligatorio.")

        status = normalize_news_status(data.get("status"))
        slug = slugify(data.get("slug") or title)
        published_at = clean_text(data.get("publishedAt"))
        if status == "published" and not published_at:
            published_at = now_iso()

        return {
            "title": title,
            "slug": slug,
            "excerpt": clean_text(data.get("excerpt")),
            "content": clean_text(data.get("content")),
            "category": clean_text(data.get("category")),
            "tags": clean_text(data.get("tags")),
            "featured_image": normalize_url(data.get("featuredImage")),
            "status": status,
            "is_featured": 1 if data.get("isFeatured") else 0,
            "published_at": published_at,
        }

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
        username = clean_text(data.get("username")).lower()
        password = clean_text(data.get("password"))
        role = clean_text(data.get("role")) or "nuria"
        display_name = clean_text(data.get("display_name")) or username
        email = clean_text(data.get("email"))
        active = 1 if data.get("active", True) else 0

        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,40}", username):
            self.send_json({"error": "Usuario no valido. Usa 3-40 letras, numeros, punto, guion o guion bajo."}, HTTPStatus.BAD_REQUEST)
            return
        if not password:
            self.send_json({"error": "La contraseña es obligatoria."}, HTTPStatus.BAD_REQUEST)
            return
        if role not in {"admin", "nuria"}:
            self.send_json({"error": "Rol no valido."}, HTTPStatus.BAD_REQUEST)
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
                        username,
                        hash_password(password),
                        role,
                        display_name,
                        email,
                        active,
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

            role = clean_text(data.get("role", row["role"])) or row["role"]
            if role not in {"admin", "nuria"}:
                self.send_json({"error": "Rol no valido."}, HTTPStatus.BAD_REQUEST)
                return

            active = 1 if data.get("active", bool(row["active"])) else 0
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

            updates = {
                "role": role,
                "display_name": clean_text(data.get("display_name", row["display_name"])) or username,
                "email": clean_text(data.get("email", row["email"])),
                "active": active,
                "updated_at": now_iso(),
            }
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
        allowed = {
            "maintenance_mode",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_from",
            "smtp_tls",
            "smtp_ssl",
        }
        updates = {key: data.get(key, "") for key in allowed if key in data}
        if "smtp_port" in updates:
            try:
                port = int(clean_text(updates["smtp_port"]))
                if port <= 0:
                    raise ValueError
                updates["smtp_port"] = str(port)
            except ValueError:
                self.send_json({"error": "Puerto SMTP no valido."}, HTTPStatus.BAD_REQUEST)
                return
        for key in ("maintenance_mode", "smtp_tls", "smtp_ssl"):
            if key in updates:
                updates[key] = "1" if bool_text(updates[key]) else "0"
        if clean_text(data.get("smtp_password")):
            updates["smtp_password"] = clean_text(data.get("smtp_password"))
        elif data.get("clear_smtp_password"):
            updates["smtp_password"] = ""

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
        search = clean_text(params.get("q", [""])[0])
        usuario_destino = clean_text(params.get("usuario_destino", [""])[0]).lower()
        usuario_origen = clean_text(params.get("usuario_origen", [""])[0]).lower()
        email_estado = clean_text(params.get("email_estado", [""])[0])
        scope = clean_text(params.get("scope", ["mine"])[0])

        where = []
        values: list[object] = []

        if user.get("role") == "admin" and scope == "all":
            pass
        else:
            destinos = ["", user["username"]]
            placeholders = ", ".join("?" for _ in destinos)
            where.append(f"COALESCE(usuario_destino, '') IN ({placeholders})")
            values.extend(destinos)

        if usuario_destino:
            where.append("COALESCE(usuario_destino, '') = ?")
            values.append(usuario_destino)
        if usuario_origen:
            where.append("COALESCE(usuario_origen, '') = ?")
            values.append(usuario_origen)
        if search:
            where.append("(asunto LIKE ? OR cuerpo LIKE ?)")
            like = f"%{search}%"
            values.extend([like, like])
        if email_estado == "sent":
            where.append("email_sent_at IS NOT NULL AND email_sent_at <> ''")
        elif email_estado == "pending":
            where.append("(email_sent_at IS NULL OR email_sent_at = '')")

        with db_session() as conn:
            sql = "SELECT * FROM notificaciones"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY fecha_hora DESC, id DESC LIMIT 200"
            rows = conn.execute(
                sql,
                values,
            ).fetchall()
            items = []
            unread = 0
            for row in rows:
                item = {key: row[key] for key in row.keys()}
                item["fecha_hora_formateada"] = format_datetime_es(row["fecha_hora"])
                if not clean_text(row["read_at"]):
                    unread += 1
                items.append(item)

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

    def api_list_licitaciones(self, query: str) -> None:
        user = self.current_user() or {}
        params = parse_qs(query)
        estado = clean_text(params.get("estado", [""])[0])
        search = clean_text(params.get("q", [""])[0])
        dia_id = clean_text(params.get("dia_id", [""])[0])
        vigentes = clean_text(params.get("vigentes", [""])[0]) == "1"
        vivas = clean_text(params.get("vivas", [""])[0]) == "1"
        calendario = clean_text(params.get("calendario", [""])[0]) == "1"
        orden_fecha = clean_text(params.get("orden_fecha", ["asc"])[0]).lower()
        direccion_fecha = "DESC" if orden_fecha == "desc" else "ASC"
        nuria_visible_states = None
        calendario_estados = NURIA_LICITACIONES_ESTADOS if user.get("role") == "nuria" else CALENDARIO_ESTADOS
        vivas_estados = NURIA_LICITACIONES_ESTADOS if user.get("role") == "nuria" else CALENDARIO_ESTADOS
        if calendario:
            if estado and estado != "Todos" and estado not in calendario_estados:
                estado = ""
        elif vivas:
            if estado and estado != "Todos" and estado not in vivas_estados:
                estado = ""
        elif user.get("role") == "nuria":
            nuria_visible_states = NURIA_ESTADOS if dia_id.isdigit() else NURIA_LICITACIONES_ESTADOS
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
        elif user.get("role") == "nuria":
            placeholders = ", ".join("?" for _ in nuria_visible_states)
            where.append(f"estado IN ({placeholders})")
            values.extend(nuria_visible_states)
        if dia_id.isdigit():
            where.append("infonalia_dia_id = ?")
            values.append(int(dia_id))
        elif vigentes or vivas:
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
            totals = {
                row["estado"]: row["total"]
                for row in conn.execute(totals_sql, values)
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
                    SELECT estado, COUNT(*) AS total
                    FROM licitaciones
                    WHERE infonalia_dia_id = ?
                    GROUP BY estado
                    """,
                    (int(dia_id),),
                ).fetchall()
                day_counts = {row["estado"]: row["total"] for row in day_counts_rows}
                day_pending_review = day_counts.get("Pendiente Nuria", 0)
                day_pending_admin = day_counts.get("Pendiente", 0)
                day_nuria_total = (
                    day_counts.get("Pendiente Nuria", 0)
                    + day_counts.get("Descartar", 0)
                    + day_counts.get("Descargar", 0)
                    + day_counts.get("Hacer", 0)
                )
        if calendario:
            estados = calendario_estados
        elif vivas:
            estados = vivas_estados
        elif user.get("role") == "nuria":
            estados = NURIA_ESTADOS if dia_id.isdigit() else NURIA_LICITACIONES_ESTADOS
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
            "estado": normalize_estado(data.get("estado")) or "Pendiente",
            "comentario": clean_text(data.get("comentario")),
            "ruta_carpeta": folder_path_for_storage(data.get("ruta_carpeta")),
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        if payload["estado"] not in ESTADOS_VALIDOS:
            payload["estado"] = "Pendiente"

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
            result = import_csv_content(csv_bytes)
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
            result = import_msg_content(msg_bytes, enrich_pdf=enrich_pdf)
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
            counts = {row["estado"]: row["total"] for row in counts_rows}
            pendientes = counts.get("Pendiente", 0)
            pendientes_nuria = counts.get("Pendiente Nuria", 0)
            decisiones_nuria = counts.get("Descartar", 0) + counts.get("Descargar", 0) + counts.get("Hacer", 0)
            nuria_total = pendientes_nuria + decisiones_nuria
            pending_rows = conn.execute(
                """
                SELECT expediente, objeto, fecha_limite, hora_limite
                FROM licitaciones
                WHERE infonalia_dia_id = ? AND estado = 'Pendiente Nuria'
                ORDER BY fecha_limite ASC, hora_limite ASC, id ASC
                """,
                (dia_id,),
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
                WHERE infonalia_dia_id = ? AND estado = 'Pendiente Nuria'
                """,
                (dia_id,),
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
                counts = {row["estado"]: row["total"] for row in counts_rows}
                asunto = f"Día Infonalia revisado: {day['titulo']}"
                cuerpo = (
                    f"El equipo revisor ha marcado como revisado el día {day['titulo']}.\n\n"
                    f"Descartadas: {counts.get('Descartar', 0)}\n"
                    f"Solo descargar: {counts.get('Descargar', 0)}\n"
                    f"Preparar licitación: {counts.get('Hacer', 0)}"
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

        dropbox_root = find_dropbox_root()
        allowed_destination_roots = [DOWNLOAD_ROOT]
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

        try:
            completed = subprocess.run(
                [sys.executable, str(LAUNCHER_PATH), url],
                cwd=str(destino),
                capture_output=True,
                text=True,
                timeout=MAX_DOWNLOAD_RUNTIME_SECONDS,
            )
        except subprocess.TimeoutExpired:
            self.send_json(
                {"error": "La descarga ha tardado demasiado y se ha detenido.", "carpeta": str(destino)},
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
        except DownloadSafetyError as exc:
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

        updates = {
            "ruta_carpeta": ruta_guardada,
            "updated_at": now_iso(),
        }

        set_clause = ", ".join(f"{key} = ?" for key in updates)
        with db_session() as conn:
            conn.execute(
                f"UPDATE licitaciones SET {set_clause} WHERE id = ?",
                list(updates.values()) + [licitacion_id],
            )
            if row["infonalia_dia_id"]:
                refresh_dia_estado(conn, int(row["infonalia_dia_id"]))

        self.send_json(
            {
                "ok": True,
                "codigo": completed.returncode,
                "carpeta": str(destino),
                "ruta_carpeta": ruta_guardada,
                "salida": salida,
            },
            HTTPStatus.OK,
        )

    def api_update_licitacion(self, licitacion_id: int) -> None:
        user = self.current_user() or {}
        data = self.read_json()

        if user.get("role") == "nuria":
            estado = clean_text(data.get("estado"))
            if not estado:
                self.send_json({"error": "No hay cambios"}, HTTPStatus.BAD_REQUEST)
                return
            if estado not in NURIA_ESTADOS_VALIDOS:
                self.send_json({"error": "Estado no permitido para esta revision."}, HTTPStatus.FORBIDDEN)
                return

            with db_session() as conn:
                row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
                if not row:
                    self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                    return
                if row["estado"] not in NURIA_ESTADOS_VALIDOS:
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
        if "estado" in updates and updates["estado"] not in ESTADOS_VALIDOS:
            self.send_json({"error": "Estado no valido"}, HTTPStatus.BAD_REQUEST)
            return
        if not updates:
            self.send_json({"error": "No hay cambios"}, HTTPStatus.BAD_REQUEST)
            return

        mark_for_nuria = any(
            key != "ruta_carpeta"
            for key in updates
        )
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [licitacion_id]

        with db_session() as conn:
            conn.execute(f"UPDATE licitaciones SET {set_clause} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if row and row["infonalia_dia_id"]:
                if mark_for_nuria:
                    mark_dia_nuria_dirty(conn, int(row["infonalia_dia_id"]))
                refresh_dia_estado(conn, int(row["infonalia_dia_id"]))
        if not row:
            self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json(row_to_dict(row))

    def api_delete_licitacion(self, licitacion_id: int) -> None:
        if not self.require_admin():
            return

        with db_session() as conn:
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                self.send_json({"error": "Licitacion no encontrada"}, HTTPStatus.NOT_FOUND)
                return
            dia_id = row["infonalia_dia_id"]
            conn.execute("DELETE FROM licitaciones WHERE id = ?", (licitacion_id,))
            if dia_id:
                mark_dia_nuria_dirty(conn, int(dia_id))
                refresh_dia_estado(conn, int(dia_id))

        self.send_json({"ok": True})

    def api_delete_dia(self, dia_id: int) -> None:
        if not self.require_admin():
            return

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

            if licitacion_ids:
                placeholders = ",".join("?" for _ in licitacion_ids)
                conn.execute(
                    f"DELETE FROM licitaciones WHERE id IN ({placeholders})",
                    licitacion_ids,
                )

            conn.execute("DELETE FROM infonalia_dias WHERE id = ?", (dia_id,))

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
