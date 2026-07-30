from __future__ import annotations

import argparse
import email
import hashlib
import imaplib
import json
import logging
import os
import pprint
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

try:
    from .email_templates import build_llangon_email_shell
    from .environment import load_env_file
    from .formatting import format_date_es, format_datetime_es
    from .infonalia_import_core import (
        PARSER_VERSION,
        ParseIssue,
        ReconciledMessage,
        block_to_legacy_item,
        comparison_value,
        legacy_items,
        parse_representation,
        reconcile_message,
    )
    from .licitacion_publication import detect_tipo_publicacion_from_texts
    from .msg_parsing import extraer_fecha_msg
    from .normalization import clean_text
    from .operational_settings import effective_bool, effective_int, effective_text
except ImportError:
    from email_templates import build_llangon_email_shell
    from environment import load_env_file
    from formatting import format_date_es, format_datetime_es
    from infonalia_import_core import (
        PARSER_VERSION,
        ParseIssue,
        ReconciledMessage,
        block_to_legacy_item,
        comparison_value,
        legacy_items,
        parse_representation,
        reconcile_message,
    )
    from licitacion_publication import detect_tipo_publicacion_from_texts
    from msg_parsing import extraer_fecha_msg
    from normalization import clean_text
    from operational_settings import effective_bool, effective_int, effective_text


APP_ROOT = Path(__file__).resolve().parent
load_env_file(APP_ROOT / ".env")

LOGGER = logging.getLogger(__name__)
EXPECTED_FROM = "envios@infonalia.net"
EXPECTED_SUBJECT = "LICITACIONES - Envío de Novedades - 149022"
HEADER_PEEK_QUERY = "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
FULL_PEEK_QUERY = "(BODY.PEEK[])"
INCLUDE_SEEN_UID_LIMIT = 100
IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
IMPORT_CLAIM_STALE_MINUTES = 60


@dataclass(frozen=True)
class InfonaliaImportConfig:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    folder: str
    expected_from: str
    expected_subject: str
    notify_email: str
    mark_read_on_success: bool
    test_forwarders: list[str]
    lookback_hours: int
    strict_mode: bool = False

    @property
    def complete(self) -> bool:
        return bool(self.host and self.port and self.user and self.password and self.folder and self.notify_email)


def env_bool(name: str, default: bool = False, environ: dict[str, str] | None = None) -> bool:
    env = environ or os.environ
    raw = env.get(name)
    if raw is None:
        return default
    return clean_text(raw).lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_int(name: str, default: int, environ: dict[str, str] | None = None, *, minimum: int = 0) -> int:
    env = environ or os.environ
    try:
        return max(minimum, int(clean_text(env.get(name)) or str(default)))
    except ValueError:
        return default


def split_emails(value: object) -> list[str]:
    result: list[str] = []
    for item in re.split(r"[;,\n\r]+", clean_text(value)):
        email = item.strip().lower()
        if email and email not in result:
            result.append(email)
    return result


def config_from_env(
    environ: dict[str, str] | None = None,
    settings: dict[str, object] | None = None,
) -> InfonaliaImportConfig:
    env = environ or os.environ
    suite_settings = {} if settings is None else settings
    return InfonaliaImportConfig(
        enabled=effective_bool("infonalia_import_enabled", settings=suite_settings, environ=env),
        host=effective_text("actions_imap_host", settings=suite_settings, environ=env) or "imap.gmail.com",
        port=effective_int("actions_imap_port", 993, settings=suite_settings, environ=env, minimum=1),
        user=effective_text("actions_imap_user", settings=suite_settings, environ=env),
        password=clean_text(env.get("LLANGON_ACTIONS_IMAP_PASSWORD")),
        folder=effective_text("infonalia_import_folder", settings=suite_settings, environ=env) or "LLANGON_INFONALIA",
        expected_from=clean_text(env.get("LLANGON_INFONALIA_IMPORT_FROM")) or EXPECTED_FROM,
        expected_subject=clean_text(env.get("LLANGON_INFONALIA_IMPORT_SUBJECT")) or EXPECTED_SUBJECT,
        notify_email=effective_text("infonalia_import_notify_email", settings=suite_settings, environ=env) or "info3@llangon.com",
        mark_read_on_success=effective_bool("infonalia_import_mark_read_on_success", settings=suite_settings, environ=env),
        test_forwarders=split_emails(env.get("LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS")),
        lookback_hours=effective_int("infonalia_import_lookback_hours", 48, settings=suite_settings, environ=env, minimum=1),
        strict_mode=env_bool("LLANGON_INFONALIA_STRICT_IMPORT_ENABLED", False, environ=env),
    )


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def safe_header(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    try:
        return clean_text(str(make_header(decode_header(text))))
    except Exception:
        return text


def normalized_from(value: object) -> str:
    return clean_text(parseaddr(safe_header(value))[1]).lower()


def parsed_message_datetime(value: object) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    try:
        return parsed.astimezone(ZoneInfo("Europe/Madrid"))
    except Exception:
        return parsed


def iso_from_message_date(value: object) -> str:
    parsed = parsed_message_datetime(value)
    if not parsed:
        return ""
    return parsed.replace(microsecond=0).isoformat()


def date_for_infonalia_day(value: object) -> str:
    parsed = parsed_message_datetime(value)
    if parsed:
        return parsed.date().isoformat()
    return datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()


def message_text_parts(message: Message) -> tuple[str, str]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if message.is_multipart():
        parts = message.walk()
    else:
        parts = [message]
    for part in parts:
        if part.get_content_maintype() == "multipart":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            raw_payload = part.get_payload()
            payload_text = clean_text(raw_payload)
        else:
            payload_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        content_type = part.get_content_type().lower()
        if content_type == "text/plain":
            plain_parts.append(payload_text)
        elif content_type == "text/html":
            html_parts.append(payload_text)
    return "\n".join(plain_parts), "\n".join(html_parts)


def html_to_text(html: str) -> str:
    if not clean_text(html):
        return ""
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text("\n")
    except Exception:
        text = re.sub(r"(?i)<br\s*/?>", "\n", html)
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return unescape(text)


def after_colon(line: str) -> str:
    if ":" not in line:
        return ""
    value = clean_text(line.split(":", 1)[1])
    if value.startswith("<") and ">" in value:
        return clean_text(value.strip("<>"))
    match = re.search(r"<([^>]+)>", value)
    return clean_text(match.group(1) if match else value)


def is_object_field(line_lower: str) -> bool:
    normalized = clean_text(line_lower).lower()
    if "resumen del objeto" in normalized or "objeto del contrato" in normalized:
        return True
    return normalized in {"objeto", "objeto:"} or normalized.startswith("objeto:")


def is_province_field(line_lower: str) -> bool:
    normalized = clean_text(line_lower).lower()
    return bool(re.match(r"^provincia(?:\s+de\s+ejecuci[oó]n)?\s*:?", normalized))


def normalize_url(value: object) -> str:
    text = clean_text(value).strip("<>")
    if not text:
        return ""
    if text.startswith("//"):
        return "https:" + text
    if re.match(r"(?i)^https?://", text):
        return text
    if "." in text:
        return "https://" + text
    return text


def parse_money_value(value: object) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"[-+]?\d[\d.,]*", text)
    if not match:
        return None
    number = match.group(0)
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def parse_source_date(line: str) -> str:
    match = re.search(r"(\d{2}/\d{2}/\d{2,4}(?:\s+\d{1,2}:\d{2})?)", line)
    return clean_text(match.group(1)) if match else ""


def split_licitacion_blocks(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    marker = re.compile(r"(?im)^(?=\s*Ref\.?\s+Infonalia\s*:)")
    return [chunk for chunk in marker.split(normalized) if re.match(r"(?is)^\s*Ref\.?\s+Infonalia\s*:", chunk)]


def parse_licitacion_blocks(text: str) -> list[dict[str, object]]:
    parsed = parse_representation(text, representation="text", enforce_ref_format=False)
    items: list[dict[str, object]] = []
    for block in parsed.blocks:
        item = block_to_legacy_item(block)
        source_text = clean_text(item.get("fuente_texto"))
        item["fecha_fuente"] = parse_source_date(source_text)
        if source_text:
            item["plataforma_origen"] = source_text
        items.append(item)
    return items


def parse_infonalia_email(raw_bytes: bytes, *, strict: bool = False) -> dict[str, object]:
    message = email.message_from_bytes(raw_bytes)
    plain, html = message_text_parts(message)
    message_id = clean_text(message.get("Message-ID"))
    reconciliation = reconcile_message(
        plain_text=plain,
        html_text=html,
        message_id=message_id,
        require_both=strict,
        enforce_ref_format=strict,
    )
    return {
        "subject": safe_header(message.get("Subject")),
        "from_email": normalized_from(message.get("From")),
        "message_id": message_id,
        "received_at": iso_from_message_date(message.get("Date")),
        "plain_text": plain,
        "html_text": html,
        "items": legacy_items(reconciliation, require_safe=strict),
        "strict_mode": strict,
        "reconciliation": reconciliation,
        "detected_text": reconciliation.text.marker_count,
        "detected_html": reconciliation.html.marker_count,
        "safe_to_persist": reconciliation.safe_to_persist,
    }


def is_expected_infonalia_message(parsed: dict[str, object], config: InfonaliaImportConfig) -> tuple[bool, str]:
    from_email = clean_text(parsed.get("from_email")).lower()
    subject = clean_text(parsed.get("subject"))
    allowed_forwarders = set(config.test_forwarders)
    if from_email != config.expected_from.lower() and from_email not in allowed_forwarders:
        return False, "remitente no coincide"
    if subject != config.expected_subject:
        return False, "asunto no coincide"
    return True, ""


def imap_date(value: datetime) -> str:
    return f"{value.day:02d}-{IMAP_MONTHS[value.month - 1]}-{value.year:04d}"


def imap_search_criteria(
    config: InfonaliaImportConfig,
    *,
    include_seen: bool = False,
    current: datetime | None = None,
) -> tuple[object, ...]:
    now = current or datetime.now().astimezone()
    cutoff = now - timedelta(hours=config.lookback_hours)
    return (("ALL",) if include_seen else ("UNSEEN",)) + ("SINCE", imap_date(cutoff))


def message_is_within_lookback(
    parsed: dict[str, object],
    config: InfonaliaImportConfig,
    *,
    current: datetime | None = None,
) -> bool:
    received_at = clean_text(parsed.get("received_at"))
    if not received_at:
        return True
    try:
        received = datetime.fromisoformat(received_at)
    except ValueError:
        return True
    now = current or datetime.now().astimezone()
    if received.tzinfo is None:
        received = received.replace(tzinfo=now.tzinfo)
    if now.tzinfo is None:
        now = now.replace(tzinfo=received.tzinfo)
    return received >= now - timedelta(hours=config.lookback_hours)


def has_infonalia_structure(parsed: dict[str, object]) -> bool:
    reconciliation = parsed.get("reconciliation")
    if isinstance(reconciliation, ReconciledMessage):
        return reconciliation.detected_count > 0
    return bool(parsed.get("items"))


def body_hash_for_raw(raw_bytes: bytes) -> str:
    parsed = parse_infonalia_email(raw_bytes)
    text = clean_text(parsed.get("plain_text")) or clean_text(html_to_text(clean_text(parsed.get("html_text"))))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_infonalia_email_import_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS infonalia_email_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            processed_at TEXT,
            mailbox_user TEXT,
            imap_uid TEXT,
            message_id TEXT,
            from_email TEXT,
            subject TEXT,
            received_at TEXT,
            body_hash TEXT,
            status TEXT NOT NULL,
            infonalia_dia_id INTEGER,
            imported_count INTEGER NOT NULL DEFAULT 0,
            skipped_duplicate_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            notification_sent_at TEXT,
            telegram_notification_attempted_at TEXT,
            telegram_notification_status TEXT,
            telegram_notification_target TEXT,
            telegram_notification_error TEXT,
            telegram_notification_message_id TEXT,
            FOREIGN KEY (infonalia_dia_id) REFERENCES infonalia_dias(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_infonalia_email_imports_message ON infonalia_email_imports(message_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_infonalia_email_imports_hash ON infonalia_email_imports(body_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_infonalia_email_imports_status ON infonalia_email_imports(status)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS infonalia_email_import_claims (
            dedupe_key TEXT PRIMARY KEY,
            message_id TEXT,
            body_hash TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            status TEXT NOT NULL,
            import_id INTEGER,
            error_message TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_email_claims_status "
        "ON infonalia_email_import_claims(status, claimed_at)"
    )
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(infonalia_email_imports)").fetchall()}
    if "telegram_notification_attempted_at" not in existing_columns:
        conn.execute("ALTER TABLE infonalia_email_imports ADD COLUMN telegram_notification_attempted_at TEXT")
    if "telegram_notification_status" not in existing_columns:
        conn.execute("ALTER TABLE infonalia_email_imports ADD COLUMN telegram_notification_status TEXT")
    if "telegram_notification_target" not in existing_columns:
        conn.execute("ALTER TABLE infonalia_email_imports ADD COLUMN telegram_notification_target TEXT")
    if "telegram_notification_error" not in existing_columns:
        conn.execute("ALTER TABLE infonalia_email_imports ADD COLUMN telegram_notification_error TEXT")
    if "telegram_notification_message_id" not in existing_columns:
        conn.execute("ALTER TABLE infonalia_email_imports ADD COLUMN telegram_notification_message_id TEXT")
    audit_columns = {
        "started_at": "TEXT",
        "finished_at": "TEXT",
        "detected_html_count": "INTEGER NOT NULL DEFAULT 0",
        "detected_text_count": "INTEGER NOT NULL DEFAULT 0",
        "canonical_count": "INTEGER NOT NULL DEFAULT 0",
        "conflict_count": "INTEGER NOT NULL DEFAULT 0",
        "quarantine_count": "INTEGER NOT NULL DEFAULT 0",
        "reconciliation_status": "TEXT",
        "committed": "INTEGER NOT NULL DEFAULT 0",
        "marked_seen": "INTEGER NOT NULL DEFAULT 0",
        "parser_version": "TEXT",
        "issues_json": "TEXT",
        "references_json": "TEXT",
    }
    for column_name, definition in audit_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE infonalia_email_imports ADD COLUMN {column_name} {definition}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS infonalia_email_import_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL,
            ordinal INTEGER NOT NULL,
            ref_infonalia TEXT,
            expediente TEXT,
            organismo TEXT,
            result_status TEXT NOT NULL,
            persistence_detail TEXT,
            issues_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (import_id) REFERENCES infonalia_email_imports(id)
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_infonalia_email_import_blocks_ordinal "
        "ON infonalia_email_import_blocks(import_id, ordinal)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS infonalia_email_import_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedupe_key TEXT NOT NULL UNIQUE,
            import_id INTEGER,
            message_id TEXT,
            body_hash TEXT,
            status TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            parser_version TEXT,
            summary TEXT,
            issues_json TEXT,
            alert_attempted_at TEXT,
            alert_sent_at TEXT,
            alert_error TEXT,
            resolved_at TEXT,
            FOREIGN KEY (import_id) REFERENCES infonalia_email_imports(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_email_incidents_status "
        "ON infonalia_email_import_incidents(status, last_seen_at)"
    )


def existing_import_row(conn: sqlite3.Connection, *, message_id: str, body_hash: str) -> sqlite3.Row | None:
    ensure_infonalia_email_import_schema(conn)
    if message_id:
        row = conn.execute(
            "SELECT * FROM infonalia_email_imports "
            "WHERE message_id = ? AND status IN ('imported', 'committed_but_unseen') "
            "ORDER BY id DESC LIMIT 1",
            (message_id,),
        ).fetchone()
        if row:
            return row
    if body_hash:
        return conn.execute(
            "SELECT * FROM infonalia_email_imports "
            "WHERE body_hash = ? AND status IN ('imported', 'committed_but_unseen') "
            "ORDER BY id DESC LIMIT 1",
            (body_hash,),
        ).fetchone()
    return None


def _strict_reconciliation(parsed: dict[str, object]) -> ReconciledMessage | None:
    reconciliation = parsed.get("reconciliation")
    return reconciliation if isinstance(reconciliation, ReconciledMessage) else None


def _issues_json(reconciliation: ReconciledMessage) -> str:
    return json.dumps(
        reconciliation.to_audit_dict().get("issues", []),
        ensure_ascii=False,
        sort_keys=True,
    )


def _record_strict_incident(
    app_module: Any,
    parsed: dict[str, object],
    *,
    raw_bytes: bytes,
    mailbox_user: str,
    imap_uid: str,
    notify: bool,
    notification_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None,
    notify_email: str,
) -> dict[str, object]:
    reconciliation = _strict_reconciliation(parsed)
    if reconciliation is None:
        raise ValueError("Falta el resultado de conciliación estricta.")
    timestamp = now_iso()
    body_hash = body_hash_for_raw(raw_bytes)
    message_id = clean_text(parsed.get("message_id"))
    dedupe_key = f"strict:{message_id or body_hash}"
    detected = reconciliation.detected_count
    conflicts = reconciliation.conflict_count
    quarantined = detected - conflicts
    if quarantined < 0 or detected != conflicts + quarantined:
        raise AssertionError(
            f"Conciliación inválida: detectados={detected}, conflictos={conflicts}, cuarentena={quarantined}."
        )
    issue_messages = [issue.message for issue in reconciliation.issues]
    summary_text = "; ".join(issue_messages[:8]) or "El correo no supera la conciliación estricta."

    with app_module.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        cursor = conn.execute(
            """
            INSERT INTO infonalia_email_imports (
                created_at, started_at, processed_at, finished_at, mailbox_user, imap_uid,
                message_id, from_email, subject, received_at, body_hash, status,
                imported_count, skipped_duplicate_count, error_message,
                detected_html_count, detected_text_count, canonical_count,
                conflict_count, quarantine_count, reconciliation_status,
                committed, marked_seen, parser_version, issues_json, references_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'quarantined', 0, 0, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
            """,
            (
                timestamp,
                timestamp,
                timestamp,
                timestamp,
                mailbox_user,
                imap_uid,
                message_id,
                clean_text(parsed.get("from_email")),
                clean_text(parsed.get("subject")),
                clean_text(parsed.get("received_at")),
                body_hash,
                summary_text[:2000],
                reconciliation.html.marker_count,
                reconciliation.text.marker_count,
                len(reconciliation.canonical_blocks),
                conflicts,
                quarantined,
                reconciliation.reconciliation_status,
                PARSER_VERSION,
                _issues_json(reconciliation),
                json.dumps(
                    [block.ref_infonalia for block in reconciliation.canonical_blocks],
                    ensure_ascii=False,
                ),
            ),
        )
        import_id = int(cursor.lastrowid)
        for block in reconciliation.canonical_blocks:
            result_status = "conflict" if block.status == "conflict" else "quarantined"
            conn.execute(
                """
                INSERT INTO infonalia_email_import_blocks (
                    import_id, ordinal, ref_infonalia, expediente, organismo,
                    result_status, persistence_detail, issues_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    block.ordinal,
                    block.ref_infonalia,
                    block.expediente,
                    block.organismo,
                    result_status,
                    "No persistido: el correo completo quedó bloqueado por conciliación fail-closed.",
                    json.dumps([item.__dict__ for item in block.issues], ensure_ascii=False),
                    timestamp,
                ),
            )
        existing = conn.execute(
            "SELECT * FROM infonalia_email_import_incidents WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE infonalia_email_import_incidents
                SET import_id = ?, last_seen_at = ?, occurrence_count = occurrence_count + 1,
                    status = 'open', summary = ?, issues_json = ?, resolved_at = NULL
                WHERE id = ?
                """,
                (import_id, timestamp, summary_text[:2000], _issues_json(reconciliation), existing["id"]),
            )
            incident_id = int(existing["id"])
            already_alerted = bool(clean_text(existing["alert_sent_at"]))
        else:
            incident_cursor = conn.execute(
                """
                INSERT INTO infonalia_email_import_incidents (
                    dedupe_key, import_id, message_id, body_hash, status,
                    first_seen_at, last_seen_at, occurrence_count, parser_version,
                    summary, issues_json
                )
                VALUES (?, ?, ?, ?, 'open', ?, ?, 1, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    import_id,
                    message_id,
                    body_hash,
                    timestamp,
                    timestamp,
                    PARSER_VERSION,
                    summary_text[:2000],
                    _issues_json(reconciliation),
                ),
            )
            incident_id = int(incident_cursor.lastrowid)
            already_alerted = False

    notified = 0
    notification_error = ""
    if notify and notification_sender and not already_alerted:
        subject = "[INCIDENCIA] Correo Infonalia bloqueado por conciliación"
        body = "\n".join(
            [
                "El importador fail-closed ha dejado un correo pendiente y sin marcar como leído.",
                f"Message-ID: {message_id or 'No consta'}",
                f"Bloques texto: {reconciliation.text.marker_count}",
                f"Bloques HTML: {reconciliation.html.marker_count}",
                f"Conflictos: {conflicts}",
                f"Cuarentena: {quarantined}",
                f"Parser: {PARSER_VERSION}",
                "",
                summary_text,
            ]
        )
        html_body = build_llangon_email_shell(
            eyebrow="Importador Infonalia",
            title="Correo Infonalia bloqueado",
            subtitle="La conciliación fail-closed ha detectado una incidencia.",
            body_html=(
                f"<p><strong>Message-ID:</strong> {escape(message_id or 'No consta')}</p>"
                f"<p><strong>Bloques texto:</strong> {reconciliation.text.marker_count}<br>"
                f"<strong>Bloques HTML:</strong> {reconciliation.html.marker_count}<br>"
                f"<strong>Conflictos:</strong> {conflicts}<br>"
                f"<strong>Cuarentena:</strong> {quarantined}</p>"
                f"<p>{escape(summary_text)}</p>"
            ),
        )
        attempted_at = now_iso()
        try:
            sent_at, notification_error = notification_sender(notify_email, subject, body, html_body)
            notified = 1 if sent_at else 0
        except Exception as exc:
            sent_at = None
            notification_error = f"No se pudo enviar el aviso de incidencia: {exc}"
        with app_module.db_session() as conn:
            ensure_infonalia_email_import_schema(conn)
            conn.execute(
                """
                UPDATE infonalia_email_import_incidents
                SET alert_attempted_at = ?, alert_sent_at = COALESCE(?, alert_sent_at), alert_error = ?
                WHERE id = ?
                """,
                (attempted_at, sent_at, clean_text(notification_error)[:2000], incident_id),
            )
    LOGGER.error(
        "Correo Infonalia bloqueado message_id=%s texto=%s html=%s conflictos=%s cuarentena=%s: %s",
        message_id,
        reconciliation.text.marker_count,
        reconciliation.html.marker_count,
        conflicts,
        quarantined,
        summary_text,
    )
    return {
        "enabled": True,
        "mode": "infonalia_import",
        "status": "quarantined",
        "mailbox_user": mailbox_user,
        "candidates_seen": 1,
        "parsed_items": detected,
        "detected_html": reconciliation.html.marker_count,
        "detected_text": reconciliation.text.marker_count,
        "imported": 0,
        "duplicates": 0,
        "conflicts": conflicts,
        "quarantined": quarantined,
        "ignored": 0,
        "errors": 1,
        "notified": notified,
        "notification_error": notification_error,
        "import_audit_id": import_id,
        "incident_id": incident_id,
        "parser_version": PARSER_VERSION,
        "reconciliation_status": reconciliation.reconciliation_status,
        "last_error": summary_text,
        "safe_to_persist": False,
    }


def _record_seen_outcome(
    app_module: Any,
    parsed: dict[str, object],
    *,
    import_id: int | None,
    success: bool,
    error_message: str = "",
) -> None:
    message_id = clean_text(parsed.get("message_id"))
    raw_body_hash = ""
    reconciliation = _strict_reconciliation(parsed)
    if reconciliation:
        raw_body_hash = reconciliation.content_hash
    timestamp = now_iso()
    with app_module.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        clauses: list[str] = []
        values: list[object] = []
        if import_id:
            clauses.append("id = ?")
            values.append(import_id)
        if message_id:
            clauses.append("message_id = ?")
            values.append(message_id)
        if not clauses:
            return
        where = " OR ".join(clauses)
        if success:
            conn.execute(
                f"""
                UPDATE infonalia_email_imports
                SET marked_seen = 1,
                    status = CASE WHEN status = 'committed_but_unseen' THEN 'imported' ELSE status END,
                    error_message = CASE WHEN status = 'committed_but_unseen' THEN '' ELSE error_message END
                WHERE {where}
                """,
                values,
            )
            if message_id:
                conn.execute(
                    """
                    UPDATE infonalia_email_import_incidents
                    SET status = 'resolved', resolved_at = ?, last_seen_at = ?
                    WHERE dedupe_key = ? AND status = 'open'
                    """,
                    (timestamp, timestamp, f"seen:{message_id}"),
                )
            return

        conn.execute(
            f"""
            UPDATE infonalia_email_imports
            SET marked_seen = 0,
                status = CASE WHEN committed = 1 AND status = 'imported' THEN 'committed_but_unseen' ELSE status END,
                error_message = ?
            WHERE {where}
            """,
            [clean_text(error_message)[:2000], *values],
        )
        dedupe_key = f"seen:{message_id or import_id or raw_body_hash}"
        existing = conn.execute(
            "SELECT id FROM infonalia_email_import_incidents WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE infonalia_email_import_incidents
                SET import_id = ?, last_seen_at = ?, occurrence_count = occurrence_count + 1,
                    status = 'open', summary = ?, resolved_at = NULL
                WHERE id = ?
                """,
                (import_id, timestamp, clean_text(error_message)[:2000], existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO infonalia_email_import_incidents (
                    dedupe_key, import_id, message_id, body_hash, status,
                    first_seen_at, last_seen_at, occurrence_count, parser_version, summary, issues_json
                )
                VALUES (?, ?, ?, ?, 'open', ?, ?, 1, ?, ?, '[]')
                """,
                (
                    dedupe_key,
                    import_id,
                    message_id,
                    raw_body_hash,
                    timestamp,
                    timestamp,
                    PARSER_VERSION,
                    clean_text(error_message)[:2000],
                ),
            )
    LOGGER.error("Commit Infonalia realizado, pero el correo no pudo marcarse leído: %s", error_message)


def _notify_seen_incident_once(
    app_module: Any,
    parsed: dict[str, object],
    *,
    notification_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None,
    notify_email: str,
    error_message: str,
) -> tuple[int, str]:
    if notification_sender is None:
        return 0, ""
    message_id = clean_text(parsed.get("message_id"))
    dedupe_key = f"seen:{message_id}"
    with app_module.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        incident = conn.execute(
            "SELECT * FROM infonalia_email_import_incidents WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if not incident or clean_text(incident["alert_sent_at"]):
            return 0, ""
        incident_id = int(incident["id"])
    subject = "[INCIDENCIA] Importación confirmada, correo Infonalia aún no leído"
    body = "\n".join(
        [
            "Las licitaciones se confirmaron en la base de datos, pero IMAP no permitió marcar el correo como leído.",
            "El siguiente reintento será idempotente y volverá a intentar únicamente el cierre IMAP.",
            f"Message-ID: {message_id or 'No consta'}",
            f"Motivo: {error_message}",
        ]
    )
    html_body = build_llangon_email_shell(
        eyebrow="Importador Infonalia",
        title="Commit realizado; cierre IMAP pendiente",
        body_html=(
            "<p>Las licitaciones quedaron confirmadas, pero el correo no pudo marcarse como leído.</p>"
            f"<p><strong>Message-ID:</strong> {escape(message_id or 'No consta')}<br>"
            f"<strong>Motivo:</strong> {escape(error_message)}</p>"
        ),
    )
    attempted_at = now_iso()
    try:
        sent_at, send_error = notification_sender(notify_email, subject, body, html_body)
        notified = 1 if sent_at else 0
    except Exception as exc:
        sent_at = None
        send_error = f"No se pudo enviar el aviso de cierre IMAP pendiente: {exc}"
        notified = 0
    with app_module.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        conn.execute(
            """
            UPDATE infonalia_email_import_incidents
            SET alert_attempted_at = ?, alert_sent_at = COALESCE(?, alert_sent_at), alert_error = ?
            WHERE id = ?
            """,
            (attempted_at, sent_at, clean_text(send_error)[:2000], incident_id),
        )
    return notified, clean_text(send_error)


def import_claim_keys(*, message_id: str, body_hash: str) -> list[str]:
    keys: list[str] = []
    if message_id:
        keys.append(f"message:{message_id}")
    if body_hash:
        keys.append(f"body:{body_hash}")
    return keys


def import_claim_key(*, message_id: str, body_hash: str) -> str:
    keys = import_claim_keys(message_id=message_id, body_hash=body_hash)
    return keys[0] if keys else "message:unknown"


def _claim_is_stale(claimed_at: object, *, current: datetime) -> bool:
    try:
        claimed = datetime.fromisoformat(clean_text(claimed_at))
    except ValueError:
        return True
    if claimed.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=claimed.tzinfo)
    elif claimed.tzinfo is None and current.tzinfo is not None:
        claimed = claimed.replace(tzinfo=current.tzinfo)
    return current - claimed >= timedelta(minutes=IMPORT_CLAIM_STALE_MINUTES)


def claim_import_attempt(
    app_module: Any,
    *,
    message_id: str,
    body_hash: str,
    timestamp: str,
) -> dict[str, object]:
    dedupe_keys = import_claim_keys(message_id=message_id, body_hash=body_hash)
    if not dedupe_keys:
        dedupe_keys = ["message:unknown"]
    dedupe_key = dedupe_keys[0]
    current = datetime.fromisoformat(timestamp)
    with app_module.db_session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ensure_infonalia_email_import_schema(conn)
        previous = existing_import_row(conn, message_id=message_id, body_hash=body_hash)
        if previous:
            return {"status": "duplicate", "dedupe_key": dedupe_key, "previous": dict(previous)}

        placeholders = ",".join("?" for _ in dedupe_keys)
        claims = conn.execute(
            f"SELECT * FROM infonalia_email_import_claims WHERE dedupe_key IN ({placeholders})",
            dedupe_keys,
        ).fetchall()
        if any(
            clean_text(item["status"]) == "processing"
            and not _claim_is_stale(item["claimed_at"], current=current)
            for item in claims
        ):
            return {
                "status": "in_progress",
                "dedupe_key": dedupe_key,
                "dedupe_keys": dedupe_keys,
            }

        for current_key in dedupe_keys:
            conn.execute(
                """
                INSERT INTO infonalia_email_import_claims (
                    dedupe_key, message_id, body_hash, claimed_at, status, import_id, error_message
                )
                VALUES (?, ?, ?, ?, 'processing', NULL, '')
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    message_id = excluded.message_id,
                    body_hash = excluded.body_hash,
                    claimed_at = excluded.claimed_at,
                    status = 'processing',
                    import_id = NULL,
                    error_message = ''
                """,
                (current_key, message_id, body_hash, timestamp),
            )
    return {"status": "claimed", "dedupe_key": dedupe_key, "dedupe_keys": dedupe_keys}


def mark_import_claim(
    conn: sqlite3.Connection,
    *,
    dedupe_key: str,
    status: str,
    import_id: int | None = None,
    error_message: str = "",
) -> None:
    conn.execute(
        """
        UPDATE infonalia_email_import_claims
        SET status = ?, import_id = ?, error_message = ?
        WHERE dedupe_key = ?
        """,
        (clean_text(status), import_id, clean_text(error_message)[:1000], dedupe_key),
    )


def fail_import_claim(app_module: Any, *, dedupe_key: str, error_message: str) -> None:
    try:
        with app_module.db_session() as conn:
            mark_import_claim(
                conn,
                dedupe_key=dedupe_key,
                status="failed",
                error_message=error_message,
            )
    except Exception:
        LOGGER.exception("No se pudo liberar la reserva del correo Infonalia tras un fallo")


@contextmanager
def import_claim_failure_guard(
    app_module: Any,
    dedupe_keys: list[str],
    *,
    enabled: bool,
):
    try:
        yield
    except Exception as exc:
        if enabled:
            for dedupe_key in dedupe_keys:
                fail_import_claim(app_module, dedupe_key=dedupe_key, error_message=str(exc))
        raise


def fail_claim_for_email(parsed: dict[str, object], raw_bytes: bytes, error_message: str) -> None:
    try:
        from . import app
    except ImportError:
        import app  # type: ignore
    body_hash = body_hash_for_raw(raw_bytes)
    for dedupe_key in import_claim_keys(
        message_id=clean_text(parsed.get("message_id")),
        body_hash=body_hash,
    ):
        fail_import_claim(app, dedupe_key=dedupe_key, error_message=error_message)


def item_to_payload(item: dict[str, object], fecha_infonalia: str) -> dict[str, object]:
    url_perfil = clean_text(item.get("url_perfil_contratante"))
    fecha_limite = clean_text(item.get("plazo_presentacion_fecha"))
    tipo_publicacion = detect_tipo_publicacion_from_texts(
        item.get("expediente"),
        item.get("resumen_objeto"),
        item.get("plazo_presentacion_texto"),
        item.get("fuente_texto"),
        item.get("bloque_texto"),
        has_fecha_limite=bool(fecha_limite),
    )
    try:
        from .app import detectar_plataforma
    except ImportError:
        from app import detectar_plataforma
    return {
        "fecha_infonalia": fecha_infonalia,
        "expediente": clean_text(item.get("expediente")),
        "objeto": clean_text(item.get("resumen_objeto")),
        "organismo": clean_text(item.get("organismo")),
        "provincia": clean_text(item.get("provincia_ejecucion")),
        "tipo": "",
        "presupuesto": item.get("presupuesto"),
        "fecha_limite": fecha_limite,
        "hora_limite": "",
        "tipo_publicacion": tipo_publicacion,
        "plataforma": detectar_plataforma(url_perfil),
        "enlace_perfil": url_perfil,
        "enlace_infonalia": clean_text(item.get("url_anuncio_infonalia")),
        "estado": "Importada",
        "comentario": "",
        "ruta_carpeta": "",
    }


def _strict_existing_record_conflicts(
    app_module: Any,
    items: list[dict[str, object]],
    *,
    fecha_infonalia: str,
) -> list[tuple[int, ParseIssue]]:
    comparisons = {
        "objeto": "resumen_objeto",
        "provincia": "provincia_ejecucion",
        "presupuesto": "presupuesto_texto",
        "fecha_limite": "plazo_presentacion_texto",
        "enlace_perfil": "url_perfil_contratante",
        "enlace_infonalia": "url_anuncio_infonalia",
    }
    conflicts: list[tuple[int, ParseIssue]] = []
    with app_module.db_session() as conn:
        for ordinal, item in enumerate(items, start=1):
            payload = item_to_payload(item, fecha_infonalia)
            expediente = clean_text(payload.get("expediente"))
            organismo = clean_text(payload.get("organismo"))
            row = conn.execute(
                """
                SELECT * FROM licitaciones
                WHERE expediente = ? AND COALESCE(organismo, '') = ?
                LIMIT 1
                """,
                (expediente, organismo),
            ).fetchone()
            if not row:
                continue
            for database_field, canonical_field in comparisons.items():
                incoming = payload.get(database_field)
                current = row[database_field]
                if incoming is None or clean_text(incoming) == "" or current is None or clean_text(current) == "":
                    continue
                if database_field == "presupuesto":
                    equal = abs(float(incoming) - float(current)) < 0.005
                elif database_field == "fecha_limite":
                    equal = clean_text(incoming) == clean_text(current)
                else:
                    equal = comparison_value(canonical_field, incoming) == comparison_value(canonical_field, current)
                if equal:
                    continue
                conflicts.append(
                    (
                        ordinal,
                        ParseIssue(
                            code="conflicting_field",
                            message=(
                                f"La licitación {expediente} ya existe y el campo {database_field} difiere: "
                                f"base={current!r}, correo={incoming!r}."
                            ),
                            representation="persistence",
                            ordinal=ordinal,
                            ref_infonalia=clean_text(item.get("ref_infonalia")),
                            field_name=canonical_field,
                        ),
                    )
                )
    return conflicts


def enrich_payload_from_manual_pdf_flow(
    payload: dict[str, object],
    *,
    app_module: Any,
) -> tuple[dict[str, object], str]:
    enriched_payload = dict(payload)
    url = clean_text(enriched_payload.get("enlace_infonalia"))
    if not url:
        return enriched_payload, ""

    pdftotext_path = app_module.find_pdftotext()
    if not pdftotext_path:
        return enriched_payload, "No se encontró pdftotext.exe; revisa INFONALIA_PDFTOTEXT."

    try:
        enriched = app_module.enrich_from_infonalia_pdf(url, clean_text(enriched_payload.get("fecha_limite")))
    except Exception as exc:
        LOGGER.warning("No se pudo enriquecer PDF Infonalia %s: %s", url, exc)
        return enriched_payload, f"No se pudo enriquecer el PDF de Infonalia: {exc}"

    if not enriched:
        return enriched_payload, "No se pudo enriquecer el PDF de Infonalia."
    if clean_text(enriched.get("tipo")):
        enriched_payload["tipo"] = clean_text(enriched.get("tipo"))
    if clean_text(enriched.get("hora_limite")):
        enriched_payload["hora_limite"] = clean_text(enriched.get("hora_limite"))
    return enriched_payload, ""


def import_parsed_email(
    parsed: dict[str, object],
    *,
    raw_bytes: bytes,
    mailbox_user: str = "",
    imap_uid: str = "",
    dry_run: bool = False,
    notify: bool = True,
    notification_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None = None,
    notify_email: str = "info3@llangon.com",
) -> dict[str, object]:
    items = list(parsed.get("items") or [])
    reconciliation = _strict_reconciliation(parsed)
    strict_mode = bool(parsed.get("strict_mode"))
    parsed_item_count = reconciliation.detected_count if strict_mode and reconciliation else len(items)
    body_hash = body_hash_for_raw(raw_bytes)
    message_id = clean_text(parsed.get("message_id"))
    fecha_infonalia = date_for_infonalia_day(parsed.get("received_at"))
    if parsed.get("received_at"):
        try:
            fecha_infonalia = datetime.fromisoformat(clean_text(parsed["received_at"])).date().isoformat()
        except ValueError:
            pass
    summary: dict[str, object] = {
        "enabled": True,
        "mode": "infonalia_import",
        "mailbox_user": mailbox_user,
        "folder": "",
        "candidates_seen": 1,
        "parsed_items": parsed_item_count,
        "imported": 0,
        "duplicates": 0,
        "conflicts": 0,
        "quarantined": 0,
        "ignored": 0,
        "errors": 0,
        "notified": 0,
        "enriched_updates": 0,
        "pdf_warning_count": 0,
        "pdf_warnings": [],
        "dia_id": None,
        "fecha_infonalia": fecha_infonalia,
    }
    if dry_run:
        would_block = bool(strict_mode and reconciliation and not reconciliation.safe_to_persist)
        summary.update(
            {
                "status": "would_block" if would_block else "dry_run",
                "would_import": 0 if would_block else len(items),
                "would_quarantine": parsed_item_count if would_block else 0,
                "body_hash": body_hash,
                "safe_to_persist": not would_block,
            }
        )
        return summary

    try:
        from . import app
    except ImportError:
        import app  # type: ignore

    if strict_mode and reconciliation and not reconciliation.safe_to_persist:
        return _record_strict_incident(
            app,
            parsed,
            raw_bytes=raw_bytes,
            mailbox_user=mailbox_user,
            imap_uid=imap_uid,
            notify=notify,
            notification_sender=notification_sender,
            notify_email=notify_email,
        )

    if strict_mode and reconciliation:
        persistence_conflicts = _strict_existing_record_conflicts(
            app,
            items,
            fecha_infonalia=fecha_infonalia,
        )
        if persistence_conflicts:
            for ordinal, issue in persistence_conflicts:
                reconciliation.issues.append(issue)
                if 1 <= ordinal <= len(reconciliation.canonical_blocks):
                    reconciliation.canonical_blocks[ordinal - 1].issues.append(issue)
            reconciliation.safe_to_persist = False
            reconciliation.reconciliation_status = "failed"
            return _record_strict_incident(
                app,
                parsed,
                raw_bytes=raw_bytes,
                mailbox_user=mailbox_user,
                imap_uid=imap_uid,
                notify=notify,
                notification_sender=notification_sender,
                notify_email=notify_email,
            )

    timestamp = now_iso()
    claim = claim_import_attempt(
        app,
        message_id=message_id,
        body_hash=body_hash,
        timestamp=timestamp,
    )
    claim_status = clean_text(claim.get("status"))
    claim_key = clean_text(claim.get("dedupe_key"))
    claim_keys = [clean_text(item) for item in list(claim.get("dedupe_keys") or [claim_key]) if clean_text(item)]
    if claim_status == "in_progress":
        summary.update(
            {
                "status": "in_progress",
                "ignored": 1,
                "message": "El mismo correo ya está siendo procesado por otra ejecución.",
            }
        )
        return summary

    with import_claim_failure_guard(
        app,
        claim_keys,
        enabled=claim_status == "claimed",
    ), app.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        pdf_warnings: list[str] = []
        previous = dict(claim.get("previous") or {}) if claim_status == "duplicate" else None
        if previous:
            dia_id = previous["infonalia_dia_id"] or app.get_or_create_dia(conn, fecha_infonalia)
            enriched_updates = 0
            for item in items:
                payload = item_to_payload(item, fecha_infonalia)
                payload, warning = enrich_payload_from_manual_pdf_flow(payload, app_module=app)
                if warning:
                    pdf_warnings.append(warning)
                result = app.insert_payload(conn, payload, dia_id)
                if result == "updated":
                    enriched_updates += 1
                    app.mark_dia_nuria_dirty(conn, dia_id)
            if enriched_updates:
                app.refresh_dia_estado(conn, dia_id)
            summary.update(
                {
                    "status": "duplicate",
                    "duplicates": len(items),
                    "dia_id": dia_id,
                    "notified": 0,
                    "enriched_updates": enriched_updates,
                    "pdf_warning_count": len(pdf_warnings),
                    "pdf_warnings": pdf_warnings,
                    "message": "Correo ya importado anteriormente.",
                }
            )
            duplicate_cursor = conn.execute(
                """
                INSERT INTO infonalia_email_imports (
                    created_at, processed_at, mailbox_user, imap_uid, message_id,
                    from_email, subject, received_at, body_hash, status,
                    infonalia_dia_id, imported_count, skipped_duplicate_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'duplicate', ?, 0, ?)
                """,
                (
                    timestamp,
                    timestamp,
                    mailbox_user,
                    imap_uid,
                    message_id,
                    clean_text(parsed.get("from_email")),
                    clean_text(parsed.get("subject")),
                    clean_text(parsed.get("received_at")),
                    body_hash,
                    dia_id,
                    len(items),
                ),
            )
            duplicate_import_id = int(duplicate_cursor.lastrowid)
            if strict_mode and reconciliation:
                conn.execute(
                    """
                    UPDATE infonalia_email_imports
                    SET started_at = ?, finished_at = ?, detected_html_count = ?,
                        detected_text_count = ?, canonical_count = ?, conflict_count = 0,
                        quarantine_count = 0, reconciliation_status = 'reconciled',
                        committed = 1, parser_version = ?, issues_json = '[]', references_json = ?
                    WHERE id = ?
                    """,
                    (
                        timestamp,
                        now_iso(),
                        reconciliation.html.marker_count,
                        reconciliation.text.marker_count,
                        len(items),
                        PARSER_VERSION,
                        json.dumps([item.get("ref_infonalia") for item in items], ensure_ascii=False),
                        duplicate_import_id,
                    ),
                )
                for ordinal, item in enumerate(items, start=1):
                    conn.execute(
                        """
                        INSERT INTO infonalia_email_import_blocks (
                            import_id, ordinal, ref_infonalia, expediente, organismo,
                            result_status, persistence_detail, issues_json, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'duplicate', ?, '[]', ?)
                        """,
                        (
                            duplicate_import_id,
                            ordinal,
                            clean_text(item.get("ref_infonalia")),
                            clean_text(item.get("expediente")),
                            clean_text(item.get("organismo")),
                            "Correo completo validado como ya procesado.",
                            timestamp,
                        ),
                    )
                summary["import_audit_id"] = duplicate_import_id
                summary["parser_version"] = PARSER_VERSION
                summary["safe_to_persist"] = True
            app.record_infonalia_activity(
                conn,
                category="import",
                event_type="infonalia_email_duplicate",
                source="email_importer",
                actor=mailbox_user or clean_text(parsed.get("from_email")),
                result="ignored",
                title="Correo diario de Infonalia ya importado",
                detail=(
                    f"Se reconocieron {len(items)} elementos ya importados. "
                    f"Actualizaciones de enriquecimiento: {enriched_updates}."
                ),
                day_id=int(dia_id),
                severity=app.SEVERITY_ATTENTION if pdf_warnings else app.SEVERITY_NORMAL,
                metadata={"message_id": message_id, "body_hash": body_hash},
                dedupe_key=f"infonalia_email_duplicate:{message_id or body_hash}",
                timestamp=timestamp,
            )
            return summary
        dia_id = app.get_or_create_dia(conn, fecha_infonalia)
        imported = 0
        duplicates = 0
        block_results: list[str] = []
        for item in items:
            payload = item_to_payload(item, fecha_infonalia)
            payload, warning = enrich_payload_from_manual_pdf_flow(payload, app_module=app)
            if warning:
                pdf_warnings.append(warning)
            result = app.insert_payload(conn, payload, dia_id)
            block_results.append(result)
            if result in {"inserted", "updated"}:
                imported += 1
                app.mark_dia_nuria_dirty(conn, dia_id)
            else:
                duplicates += 1
        app.refresh_dia_estado(conn, dia_id)
        cur = conn.execute(
            """
            INSERT INTO infonalia_email_imports (
                created_at, processed_at, mailbox_user, imap_uid, message_id,
                from_email, subject, received_at, body_hash, status,
                infonalia_dia_id, imported_count, skipped_duplicate_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported', ?, ?, ?)
            """,
            (
                timestamp,
                timestamp,
                mailbox_user,
                imap_uid,
                message_id,
                clean_text(parsed.get("from_email")),
                clean_text(parsed.get("subject")),
                clean_text(parsed.get("received_at")),
                body_hash,
                dia_id,
                imported,
                duplicates,
            ),
        )
        import_id = int(cur.lastrowid)
        if strict_mode and reconciliation:
            detected = reconciliation.detected_count
            if detected != imported + duplicates or detected != len(block_results):
                raise AssertionError(
                    "Resultado de persistencia no conciliado: "
                    f"detectados={detected}, insertados={imported}, duplicados={duplicates}, "
                    f"resultados={len(block_results)}."
                )
            conn.execute(
                """
                UPDATE infonalia_email_imports
                SET started_at = ?, finished_at = ?, detected_html_count = ?,
                    detected_text_count = ?, canonical_count = ?, conflict_count = 0,
                    quarantine_count = 0, reconciliation_status = 'reconciled',
                    committed = 1, parser_version = ?, issues_json = '[]', references_json = ?
                WHERE id = ?
                """,
                (
                    timestamp,
                    now_iso(),
                    reconciliation.html.marker_count,
                    reconciliation.text.marker_count,
                    len(items),
                    PARSER_VERSION,
                    json.dumps([item.get("ref_infonalia") for item in items], ensure_ascii=False),
                    import_id,
                ),
            )
            for ordinal, (item, persistence_result) in enumerate(zip(items, block_results), start=1):
                result_status = "duplicate" if persistence_result == "skipped" else "inserted"
                conn.execute(
                    """
                    INSERT INTO infonalia_email_import_blocks (
                        import_id, ordinal, ref_infonalia, expediente, organismo,
                        result_status, persistence_detail, issues_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?)
                    """,
                    (
                        import_id,
                        ordinal,
                        clean_text(item.get("ref_infonalia")),
                        clean_text(item.get("expediente")),
                        clean_text(item.get("organismo")),
                        result_status,
                        persistence_result,
                        timestamp,
                    ),
                )
        summary.update(
            {
                "status": "imported",
                "imported": imported,
                "duplicates": duplicates,
                "dia_id": dia_id,
                "pdf_warning_count": len(pdf_warnings),
                "pdf_warnings": pdf_warnings,
                "import_audit_id": import_id,
                "parser_version": PARSER_VERSION if strict_mode else "legacy",
                "safe_to_persist": True,
            }
        )
        severity = app.SEVERITY_ATTENTION if pdf_warnings else app.SEVERITY_NORMAL
        app.record_infonalia_activity(
            conn,
            category="import",
            event_type="infonalia_email_import",
            source="email_importer",
            actor=mailbox_user or clean_text(parsed.get("from_email")),
            result="processed",
            title="Correo diario de Infonalia importado",
            detail=(
                f"Se incorporaron {imported} licitaciones y se omitieron {duplicates} duplicados."
                + (f" Avisos PDF: {len(pdf_warnings)}." if pdf_warnings else "")
            ),
            day_id=dia_id,
            severity=severity,
            metadata={
                "import_id": import_id,
                "message_id": message_id,
                "imap_uid": clean_text(imap_uid),
                "imported": imported,
                "duplicates": duplicates,
                "pdf_warning_count": len(pdf_warnings),
            },
            dedupe_key=f"infonalia_email_import:{import_id}",
            timestamp=timestamp,
        )
        for current_claim_key in claim_keys:
            mark_import_claim(
                conn,
                dedupe_key=current_claim_key,
                status="completed",
                import_id=import_id,
            )
        # Persist the import and its idempotency claim before any external side effect.
        conn.commit()
        notified = 0
        notification_error = ""
        if notify and notification_sender:
            subject, body, html_body = build_import_notification(parsed, summary | {"dia_id": dia_id, "imported": imported, "duplicates": duplicates})
            try:
                sent_at, notification_error = notification_sender(notify_email, subject, body, html_body)
            except Exception as exc:
                sent_at = None
                notification_error = f"No se pudo enviar el aviso: {exc}"
                LOGGER.warning("Importación Infonalia realizada, pero falló el aviso: %s", exc)
            if sent_at:
                notified = 1
                conn.execute(
                    "UPDATE infonalia_email_imports SET notification_sent_at = ? WHERE id = ?",
                    (sent_at, import_id),
                )
        telegram_delivery = {"ok": False, "status": "", "target": "", "message_id": None, "error": ""}
        if notify:
            try:
                telegram_delivery = _deliver_import_telegram_notification(
                    conn,
                    app_module=app,
                    parsed=parsed,
                    summary=summary
                    | {
                        "dia_id": dia_id,
                        "imported": imported,
                        "duplicates": duplicates,
                    },
                )
            except Exception as exc:
                telegram_delivery = {
                    "ok": False,
                    "status": "failed",
                    "target": "",
                    "message_id": None,
                    "error": f"No se pudo enviar el Telegram: {exc}",
                }
                LOGGER.warning("Importación Infonalia realizada, pero falló el Telegram: %s", exc)
            _mark_import_telegram_result(
                conn,
                import_id=import_id,
                timestamp=now_iso(),
                status=str(telegram_delivery.get("status") or "failed"),
                target=str(telegram_delivery.get("target") or ""),
                error=str(telegram_delivery.get("error") or ""),
                message_id=telegram_delivery.get("message_id"),
            )
        summary.update(
            {
                "status": "imported",
                "imported": imported,
                "duplicates": duplicates,
                "dia_id": dia_id,
                "notified": notified,
                "notification_error": notification_error,
                "telegram_notified": 1 if telegram_delivery.get("ok") else 0,
                "telegram_notification_status": clean_text(telegram_delivery.get("status")),
                "telegram_notification_target": clean_text(telegram_delivery.get("target")),
                "telegram_notification_error": clean_text(telegram_delivery.get("error")),
                "pdf_warning_count": len(pdf_warnings),
                "pdf_warnings": pdf_warnings,
            }
        )
        return summary


def build_import_telegram_message(parsed: dict[str, object], summary: dict[str, object]) -> str:
    fecha = clean_text(summary.get("fecha_infonalia"))
    fecha_label = format_date_es(fecha) or fecha or "Sin fecha"
    received_label = format_datetime_es(parsed.get("received_at")) or clean_text(parsed.get("received_at")) or "No consta"
    mailbox_user = clean_text(summary.get("mailbox_user")) or "info3.llangon@gmail.com"
    parsed_items = int(summary.get("parsed_items") or 0)
    imported = int(summary.get("imported") or 0)
    duplicates = int(summary.get("duplicates") or 0)
    dia_id = clean_text(summary.get("dia_id")) or "No consta"

    return "\n".join(
        [
            "📥 Nuevo día de Infonalia importado",
            "",
            "Ya tienes disponible en la Suite un nuevo día de Infonalia para revisar.",
            "",
            f"Día: {fecha_label}",
            f"Licitaciones importadas: {imported}",
            f"Duplicadas detectadas: {duplicates}",
            f"Registros detectados: {parsed_items}",
            "Correo origen: Infonalia",
            f"Buzón revisado: {mailbox_user}",
            f"Fecha/hora del correo: {received_label}",
            f"Asunto: {clean_text(parsed.get('subject')) or 'No consta'}",
            f"Día Infonalia en Suite: {dia_id}",
            "",
            "Puedes revisarlo en la Suite.",
        ]
    )


def _deliver_import_telegram_notification(
    conn: sqlite3.Connection,
    *,
    app_module: Any,
    parsed: dict[str, object],
    summary: dict[str, object],
) -> dict[str, object]:
    text = build_import_telegram_message(parsed, summary)
    errors: list[str] = []

    for admin_row in app_module._preferred_admin_rows_for_telegram(conn):
        username = clean_text(admin_row["username"])
        result = app_module.send_telegram_user_message(admin_row, text, env=os.environ)
        if result.ok:
            LOGGER.info(
                "Telegram Infonalia enviado al admin. message_id=%s target=user:%s dia_id=%s",
                clean_text(parsed.get("message_id")),
                username,
                clean_text(summary.get("dia_id")),
            )
            return {
                "ok": True,
                "status": "sent_user",
                "target": f"user:{username}",
                "message_id": result.telegram_message_id,
                "error": "",
            }
        errors.append(f"user:{username}:{result.error_code or result.status}")

    group_result = app_module.send_telegram_group_message(text, env=os.environ)
    if group_result.ok:
        LOGGER.info(
            "Telegram Infonalia enviado al grupo. message_id=%s dia_id=%s",
            clean_text(parsed.get("message_id")),
            clean_text(summary.get("dia_id")),
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
        "Telegram Infonalia no enviado. message_id=%s dia_id=%s errors=%s",
        clean_text(parsed.get("message_id")),
        clean_text(summary.get("dia_id")),
        error_text,
    )
    return {
        "ok": False,
        "status": "failed",
        "target": "",
        "message_id": None,
        "error": error_text or clean_text(group_result.error_message) or "Telegram no configurado.",
    }


def _mark_import_telegram_result(
    conn: sqlite3.Connection,
    *,
    import_id: int,
    timestamp: str,
    status: str,
    target: str = "",
    error: str = "",
    message_id: object = None,
) -> None:
    conn.execute(
        """
        UPDATE infonalia_email_imports
        SET telegram_notification_attempted_at = ?,
            telegram_notification_status = ?,
            telegram_notification_target = ?,
            telegram_notification_error = ?,
            telegram_notification_message_id = ?
        WHERE id = ?
        """,
        (
            timestamp,
            clean_text(status),
            clean_text(target),
            clean_text(error)[:1000],
            clean_text(message_id),
            import_id,
        ),
    )


def build_import_notification(parsed: dict[str, object], summary: dict[str, object]) -> tuple[str, str, str]:
    fecha = clean_text(summary.get("fecha_infonalia"))
    fecha_label = format_date_es(fecha) or fecha
    received_label = format_datetime_es(parsed.get("received_at")) or clean_text(parsed.get("received_at"))
    subject = f"Infonalia importado — listo para revisión — {fecha_label}"
    platform_url = clean_text(os.environ.get("INFONALIA_PLATFORM_URL"))
    link_html = f"<p><a href='{platform_url}'>Abrir Llangón Suite</a></p>" if platform_url.startswith("http") else ""
    body = "\n".join(
        [
            "Se ha importado automáticamente el correo de Infonalia.",
            "",
            f"Fecha del correo: {received_label}",
            f"Registros detectados: {summary.get('parsed_items')}",
            f"Registros importados: {summary.get('imported')}",
            f"Duplicados omitidos: {summary.get('duplicates')}",
            f"Día Infonalia: {summary.get('dia_id')} / {fecha_label}",
            "",
            "El día queda disponible en la Suite para la primera revisión.",
        ]
    )
    html_body = build_llangon_email_shell(
        eyebrow="Importación automática",
        title="Infonalia importado",
        subtitle=f"Listo para revisión — {fecha_label}",
        body_html=(
            "<p>Se ha importado automáticamente el correo de Infonalia.</p>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'>"
            f"<tr><td><strong>Fecha del correo</strong></td><td>{received_label}</td></tr>"
            f"<tr><td><strong>Registros detectados</strong></td><td>{summary.get('parsed_items')}</td></tr>"
            f"<tr><td><strong>Registros importados</strong></td><td>{summary.get('imported')}</td></tr>"
            f"<tr><td><strong>Duplicados omitidos</strong></td><td>{summary.get('duplicates')}</td></tr>"
            f"<tr><td><strong>Día Infonalia</strong></td><td>{summary.get('dia_id')} / {fecha_label}</td></tr>"
            "</table>"
            "<p>El día queda disponible en la Suite para la primera revisión.</p>"
            f"{link_html}"
        ),
    )
    return subject, body, html_body


def _fetch_bytes(fetch_data: object) -> bytes:
    if not fetch_data:
        return b""
    for item in fetch_data if isinstance(fetch_data, list) else [fetch_data]:
        if isinstance(item, tuple) and len(item) >= 2 and item[1]:
            return item[1]
    return b""


def process_mailbox_once(
    *,
    config: InfonaliaImportConfig | None = None,
    settings: dict[str, object] | None = None,
    imap_factory=imaplib.IMAP4_SSL,
    dry_run: bool = False,
    include_seen: bool = False,
    verbose: bool = False,
    current: datetime | None = None,
    notification_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None = None,
) -> dict[str, object]:
    config = config or config_from_env(settings=settings)
    if not config.enabled:
        return {"enabled": False, "mode": "infonalia_import", "message": "Importador Infonalia desactivado."}
    if not config.complete:
        return {"enabled": False, "mode": "infonalia_import", "message": "Importador Infonalia incompleto: falta configuración IMAP."}
    summary: dict[str, object] = {
        "enabled": True,
        "mode": "infonalia_import",
        "mailbox_user": config.user,
        "folder": config.folder,
        "candidates_seen": 0,
        "parsed_items": 0,
        "imported": 0,
        "duplicates": 0,
        "ignored": 0,
        "errors": 0,
        "notified": 0,
    }
    current_dt = current or datetime.now().astimezone()
    criteria = imap_search_criteria(config, include_seen=include_seen, current=current_dt)
    try:
        with imap_factory(config.host, config.port) as client:
            client.login(config.user, config.password)
            select_status, _select_data = client.select(config.folder)
            if select_status != "OK":
                summary["errors"] += 1
                summary["status"] = "failed"
                summary["last_error"] = (
                    f"No se pudo seleccionar la etiqueta IMAP {config.folder}. "
                    "Comprueba que existe y que IMAP la muestra como carpeta."
                )
                return summary
            status, data = client.uid("SEARCH", *criteria)
            if status != "OK":
                summary["errors"] += 1
                summary["status"] = "failed"
                summary["last_error"] = f"IMAP UID SEARCH devolvió estado {status}."
                return summary
            uids = (data[0] or b"").split() if data else []
            if include_seen and len(uids) > INCLUDE_SEEN_UID_LIMIT:
                summary["include_seen_total_uids"] = len(uids)
                summary["include_seen_limited_to"] = INCLUDE_SEEN_UID_LIMIT
                uids = uids[-INCLUDE_SEEN_UID_LIMIT:]
            for uid in uids:
                header_status, header_data = client.uid("FETCH", uid, HEADER_PEEK_QUERY)
                if header_status != "OK":
                    summary["errors"] += 1
                    continue
                header_message = email.message_from_bytes(_fetch_bytes(header_data))
                header_subject = safe_header(header_message.get("Subject"))
                header_from = normalized_from(header_message.get("From"))
                full_status, full_data = client.uid("FETCH", uid, FULL_PEEK_QUERY)
                if full_status != "OK":
                    summary["errors"] += 1
                    continue
                raw = _fetch_bytes(full_data)
                parsed = parse_infonalia_email(raw, strict=config.strict_mode)
                strict_header_candidate = bool(
                    config.strict_mode
                    and header_from == config.expected_from.lower()
                    and header_subject == config.expected_subject
                )
                if not has_infonalia_structure(parsed) and not strict_header_candidate:
                    summary["ignored"] += 1
                    summary["last_ignored_reason"] = "Correo sin estructura válida de LICITACIONES Infonalia."
                    if verbose:
                        LOGGER.info(
                            "Correo ignorado uid=%s: sin estructura Infonalia (from=%s subject=%s)",
                            uid,
                            header_from,
                            header_subject,
                        )
                    continue
                if not message_is_within_lookback(parsed, config, current=current_dt):
                    summary["ignored"] += 1
                    summary["stale_ignored"] = int(summary.get("stale_ignored", 0) or 0) + 1
                    summary["last_ignored_reason"] = (
                        f"Correo fuera de la ventana de {config.lookback_hours} horas."
                    )
                    if not dry_run and config.mark_read_on_success:
                        client.uid("STORE", uid, "+FLAGS", "\\Seen")
                    continue
                summary["candidates_seen"] += 1
                try:
                    result = import_parsed_email(
                        parsed,
                        raw_bytes=raw,
                        mailbox_user=config.user,
                        imap_uid=uid.decode("ascii", errors="ignore"),
                        dry_run=dry_run,
                        notify=True,
                        notification_sender=notification_sender,
                        notify_email=config.notify_email,
                    )
                except Exception as exc:
                    LOGGER.exception("Error importando candidato Infonalia uid=%s", uid)
                    fail_claim_for_email(parsed, raw, str(exc))
                    if config.strict_mode:
                        reconciliation = _strict_reconciliation(parsed)
                        if reconciliation is not None:
                            reconciliation.issues.append(
                                ParseIssue(
                                    code="persistence_failure",
                                    message=f"Falló la transacción de persistencia: {exc}",
                                    representation="persistence",
                                )
                            )
                            reconciliation.safe_to_persist = False
                            reconciliation.reconciliation_status = "failed"
                        try:
                            from . import app as strict_app_module
                        except ImportError:
                            import app as strict_app_module  # type: ignore
                        incident_result = _record_strict_incident(
                            app_module=strict_app_module,
                            parsed=parsed,
                            raw_bytes=raw,
                            mailbox_user=config.user,
                            imap_uid=uid.decode("ascii", errors="ignore"),
                            notify=True,
                            notification_sender=notification_sender,
                            notify_email=config.notify_email,
                        )
                        for key in ("parsed_items", "conflicts", "quarantined", "notified"):
                            summary[key] = int(summary.get(key, 0) or 0) + int(incident_result.get(key, 0) or 0)
                    summary["errors"] += 1
                    summary["last_error"] = str(exc)
                    continue
                for key in (
                    "parsed_items",
                    "imported",
                    "duplicates",
                    "conflicts",
                    "quarantined",
                    "notified",
                    "enriched_updates",
                    "pdf_warning_count",
                ):
                    summary[key] = int(summary.get(key, 0) or 0) + int(result.get(key, 0) or 0)
                if result.get("pdf_warnings"):
                    summary["pdf_warnings"] = list(summary.get("pdf_warnings") or []) + list(result.get("pdf_warnings") or [])
                if result.get("status") == "duplicate":
                    summary["ignored"] += 1
                if result.get("errors"):
                    summary["errors"] += int(result.get("errors") or 0)
                if result.get("status") in {"imported", "duplicate"} and not dry_run and config.mark_read_on_success:
                    store_error = ""
                    try:
                        store_status, _store_data = client.uid("STORE", uid, "+FLAGS", "\\Seen")
                        if store_status != "OK":
                            store_error = f"IMAP STORE devolvió estado {store_status}."
                    except Exception as exc:
                        store_error = f"No se pudo marcar el correo como leído: {exc}"
                    if config.strict_mode:
                        try:
                            from . import app as app_module
                        except ImportError:
                            import app as app_module  # type: ignore
                        _record_seen_outcome(
                            app_module,
                            parsed,
                            import_id=int(result.get("import_audit_id") or 0) or None,
                            success=not store_error,
                            error_message=store_error,
                        )
                    if store_error:
                        summary["errors"] += 1
                        summary["committed_but_unseen"] = int(summary.get("committed_but_unseen", 0) or 0) + 1
                        summary["last_error"] = store_error
                        if config.strict_mode:
                            incident_notified, incident_notify_error = _notify_seen_incident_once(
                                app_module,
                                parsed,
                                notification_sender=notification_sender,
                                notify_email=config.notify_email,
                                error_message=store_error,
                            )
                            summary["incident_notified"] = int(summary.get("incident_notified", 0) or 0) + incident_notified
                            if incident_notify_error:
                                summary["incident_notification_error"] = incident_notify_error
    except imaplib.IMAP4.error as exc:
        LOGGER.exception("Error IMAP en importador Infonalia")
        summary["errors"] += 1
        summary["status"] = "failed"
        summary["last_error"] = f"Error IMAP: {exc}"
    except OSError as exc:
        LOGGER.exception("Error de conexión IMAP en importador Infonalia")
        summary["errors"] += 1
        summary["status"] = "failed"
        summary["last_error"] = f"Error de conexión IMAP: {exc}"
    return summary


def parse_eml_file(path: str | Path) -> dict[str, object]:
    return parse_infonalia_email(Path(path).read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importador automático del correo LICITACIONES de Infonalia.")
    parser.add_argument("--once", action="store_true", help="Procesa el buzón una sola vez y termina.")
    parser.add_argument("--dry-run", action="store_true", help="Valida sin importar, marcar leído ni notificar.")
    parser.add_argument("--verbose", action="store_true", help="Muestra más detalle.")
    parser.add_argument("--include-seen", action="store_true", help="Incluye correos ya leídos.")
    parser.add_argument("--from-eml", help="Lee un .eml local sin IMAP.")
    parser.add_argument("--parse-only", action="store_true", help="Solo parsea el .eml local.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    if args.from_eml:
        raw = Path(args.from_eml).read_bytes()
        parsed = parse_infonalia_email(raw)
        if args.parse_only:
            pprint.pp(parsed)
            return 0
        try:
            from . import app
        except ImportError:
            import app  # type: ignore
        settings = app.get_settings()
        result = import_parsed_email(
            parsed,
            raw_bytes=raw,
            dry_run=args.dry_run,
            notify=not args.dry_run,
            notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html, settings=settings),
            notify_email=config_from_env(settings=settings).notify_email,
        )
        pprint.pp(result)
        return 0 if not result.get("errors") else 1
    if not args.once:
        parser.error("Usa --once o --from-eml.")
    try:
        from . import app
    except ImportError:
        import app  # type: ignore
    settings = app.get_settings()
    result = process_mailbox_once(
        dry_run=args.dry_run,
        include_seen=args.include_seen,
        verbose=args.verbose,
        settings=settings,
        notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html, settings=settings),
    )
    pprint.pp(result)
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
