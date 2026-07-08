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
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

try:
    from .email_templates import build_llangon_email_shell
    from .environment import load_env_file
    from .formatting import format_date_es, format_datetime_es
    from .msg_parsing import extraer_fecha_msg
    from .normalization import clean_text
    from .operational_settings import effective_bool, effective_int, effective_text
except ImportError:
    from email_templates import build_llangon_email_shell
    from environment import load_env_file
    from formatting import format_date_es, format_datetime_es
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
    for item in re.split(r"[;,]", clean_text(value)):
        email = item.strip().lower()
        if email and email not in result:
            result.append(email)
    return result


def config_from_env(
    environ: dict[str, str] | None = None,
    settings: dict[str, object] | None = None,
) -> InfonaliaImportConfig:
    env = environ or os.environ
    return InfonaliaImportConfig(
        enabled=effective_bool("infonalia_import_enabled", settings=settings, environ=env),
        host=effective_text("actions_imap_host", settings=settings, environ=env) or "imap.gmail.com",
        port=effective_int("actions_imap_port", 993, settings=settings, environ=env, minimum=1),
        user=effective_text("actions_imap_user", settings=settings, environ=env),
        password=clean_text(env.get("LLANGON_ACTIONS_IMAP_PASSWORD")),
        folder=effective_text("infonalia_import_folder", settings=settings, environ=env) or "LLANGON_INFONALIA",
        expected_from=clean_text(env.get("LLANGON_INFONALIA_IMPORT_FROM")) or EXPECTED_FROM,
        expected_subject=clean_text(env.get("LLANGON_INFONALIA_IMPORT_SUBJECT")) or EXPECTED_SUBJECT,
        notify_email=effective_text("infonalia_import_notify_email", settings=settings, environ=env) or "info3@llangon.com",
        mark_read_on_success=effective_bool("infonalia_import_mark_read_on_success", settings=settings, environ=env),
        test_forwarders=split_emails(env.get("LLANGON_INFONALIA_IMPORT_TEST_FORWARDERS")),
        lookback_hours=effective_int("infonalia_import_lookback_hours", 48, settings=settings, environ=env, minimum=1),
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
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block for block in re.split(r"_{20,}", normalized) if "Ref. Infonalia:" in block]
    if blocks:
        return blocks
    chunks = re.split(r"(?=Ref\.?\s+Infonalia\s*:)", normalized, flags=re.IGNORECASE)
    return [chunk for chunk in chunks if "Ref. Infonalia:" in chunk]


def parse_licitacion_blocks(text: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for block in split_licitacion_blocks(text):
        item: dict[str, object] = {
            "ref_infonalia": "",
            "expediente": "",
            "organismo": "",
            "resumen_objeto": "",
            "provincia_ejecucion": "",
            "presupuesto": None,
            "plazo_presentacion_texto": "",
            "plazo_presentacion_fecha": "",
            "url_anuncio_infonalia": "",
            "url_perfil_contratante": "",
            "fuente_texto": "",
            "plataforma_origen": "",
            "fecha_fuente": "",
        }
        current_field = ""
        for raw_line in block.splitlines():
            line = clean_text(raw_line)
            if not line:
                continue
            lower = line.lower()
            target_field = ""
            value = ""
            if "ref. infonalia" in lower or "ref infonalia" in lower:
                target_field, value = "ref_infonalia", after_colon(line)
            elif "nº expediente" in lower or "n expediente" in lower or "expediente" in lower:
                target_field, value = "expediente", after_colon(line)
            elif lower.startswith("organismo"):
                target_field, value = "organismo", after_colon(line)
            elif "resumen del objeto" in lower:
                target_field, value = "resumen_objeto", after_colon(line)
            elif "provincia" in lower:
                target_field, value = "provincia_ejecucion", after_colon(line)
            elif lower.startswith("presupuesto"):
                target_field, value = "presupuesto", after_colon(line)
            elif "plazo presentación" in lower or "plazo presentacion" in lower:
                target_field, value = "plazo_presentacion_texto", after_colon(line) or line
            elif "ver el texto íntegro del anuncio" in lower or "ver el texto integro del anuncio" in lower:
                target_field, value = "url_anuncio_infonalia", normalize_url(after_colon(line))
            elif "perfil del contratante" in lower:
                target_field, value = "url_perfil_contratante", normalize_url(after_colon(line))
            elif "información extraída" in lower or "informacion extraida" in lower:
                target_field, value = "fuente_texto", line
            if target_field:
                current_field = target_field
                if target_field == "presupuesto":
                    item[target_field] = parse_money_value(value)
                else:
                    item[target_field] = clean_text(value)
                continue
            if current_field:
                continuation = clean_text(line)
                if re.match(r"^[^:]{1,120}:\s*$", continuation):
                    continue
                existing_value = clean_text(item.get(current_field))
                if current_field == "presupuesto":
                    if item[current_field] is None:
                        parsed_money = parse_money_value(continuation)
                        if parsed_money is not None:
                            item[current_field] = parsed_money
                elif current_field in {"url_anuncio_infonalia", "url_perfil_contratante"}:
                    if not existing_value:
                        item[current_field] = normalize_url(continuation)
                elif current_field in {"resumen_objeto", "organismo", "fuente_texto", "plazo_presentacion_texto"}:
                    item[current_field] = clean_text(f"{existing_value} {continuation}")
                elif not existing_value:
                    item[current_field] = continuation
        item["plazo_presentacion_fecha"] = extraer_fecha_msg(clean_text(item["plazo_presentacion_texto"]))
        source_text = clean_text(item["fuente_texto"])
        item["fecha_fuente"] = parse_source_date(source_text)
        if source_text:
            item["plataforma_origen"] = clean_text(source_text.split(":", 1)[-1]) if ":" in source_text else source_text
        if clean_text(item["expediente"]):
            items.append(item)
    return items


def parse_infonalia_email(raw_bytes: bytes) -> dict[str, object]:
    message = email.message_from_bytes(raw_bytes)
    plain, html = message_text_parts(message)
    body_for_parse = plain if clean_text(plain) else html_to_text(html)
    return {
        "subject": safe_header(message.get("Subject")),
        "from_email": normalized_from(message.get("From")),
        "message_id": clean_text(message.get("Message-ID")),
        "received_at": iso_from_message_date(message.get("Date")),
        "plain_text": plain,
        "html_text": html,
        "items": parse_licitacion_blocks(body_for_parse),
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


def imap_search_criteria(config: InfonaliaImportConfig, *, include_seen: bool = False) -> tuple[object, ...]:
    return ("ALL",) if include_seen else ("UNSEEN",)


def has_infonalia_structure(parsed: dict[str, object]) -> bool:
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


def existing_import_row(conn: sqlite3.Connection, *, message_id: str, body_hash: str) -> sqlite3.Row | None:
    ensure_infonalia_email_import_schema(conn)
    if message_id:
        row = conn.execute(
            "SELECT * FROM infonalia_email_imports WHERE message_id = ? AND status = 'imported' ORDER BY id DESC LIMIT 1",
            (message_id,),
        ).fetchone()
        if row:
            return row
    if body_hash:
        return conn.execute(
            "SELECT * FROM infonalia_email_imports WHERE body_hash = ? AND status = 'imported' ORDER BY id DESC LIMIT 1",
            (body_hash,),
        ).fetchone()
    return None


def item_to_payload(item: dict[str, object], fecha_infonalia: str) -> dict[str, object]:
    url_perfil = clean_text(item.get("url_perfil_contratante"))
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
        "fecha_limite": clean_text(item.get("plazo_presentacion_fecha")),
        "hora_limite": "",
        "plataforma": detectar_plataforma(url_perfil),
        "enlace_perfil": url_perfil,
        "enlace_infonalia": clean_text(item.get("url_anuncio_infonalia")),
        "estado": "Importada",
        "comentario": "",
        "ruta_carpeta": "",
    }


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
    body_hash = body_hash_for_raw(raw_bytes)
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
        "parsed_items": len(items),
        "imported": 0,
        "duplicates": 0,
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
        summary.update({"status": "dry_run", "would_import": len(items), "body_hash": body_hash})
        return summary

    try:
        from . import app
    except ImportError:
        import app  # type: ignore

    timestamp = now_iso()
    with app.db_session() as conn:
        ensure_infonalia_email_import_schema(conn)
        pdf_warnings: list[str] = []
        previous = existing_import_row(
            conn,
            message_id=clean_text(parsed.get("message_id")),
            body_hash=body_hash,
        )
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
            conn.execute(
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
                    clean_text(parsed.get("message_id")),
                    clean_text(parsed.get("from_email")),
                    clean_text(parsed.get("subject")),
                    clean_text(parsed.get("received_at")),
                    body_hash,
                    dia_id,
                    len(items),
                ),
            )
            return summary
        dia_id = app.get_or_create_dia(conn, fecha_infonalia)
        imported = 0
        duplicates = 0
        for item in items:
            payload = item_to_payload(item, fecha_infonalia)
            payload, warning = enrich_payload_from_manual_pdf_flow(payload, app_module=app)
            if warning:
                pdf_warnings.append(warning)
            result = app.insert_payload(conn, payload, dia_id)
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
                clean_text(parsed.get("message_id")),
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
    imap_factory=imaplib.IMAP4_SSL,
    dry_run: bool = False,
    include_seen: bool = False,
    verbose: bool = False,
    notification_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None = None,
) -> dict[str, object]:
    config = config or config_from_env()
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
    criteria = imap_search_criteria(config, include_seen=include_seen)
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
                parsed = parse_infonalia_email(raw)
                if not has_infonalia_structure(parsed):
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
                    summary["errors"] += 1
                    summary["last_error"] = str(exc)
                    continue
                for key in ("parsed_items", "imported", "duplicates", "notified", "enriched_updates", "pdf_warning_count"):
                    summary[key] = int(summary.get(key, 0) or 0) + int(result.get(key, 0) or 0)
                if result.get("pdf_warnings"):
                    summary["pdf_warnings"] = list(summary.get("pdf_warnings") or []) + list(result.get("pdf_warnings") or [])
                if result.get("status") == "duplicate":
                    summary["ignored"] += 1
                if result.get("errors"):
                    summary["errors"] += int(result.get("errors") or 0)
                if result.get("status") in {"imported", "duplicate"} and not dry_run and config.mark_read_on_success:
                    client.uid("STORE", uid, "+FLAGS", "\\Seen")
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
        result = import_parsed_email(
            parsed,
            raw_bytes=raw,
            dry_run=args.dry_run,
            notify=not args.dry_run,
            notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html),
            notify_email=config_from_env().notify_email,
        )
        pprint.pp(result)
        return 0 if not result.get("errors") else 1
    if not args.once:
        parser.error("Usa --once o --from-eml.")
    try:
        from . import app
    except ImportError:
        import app  # type: ignore
    result = process_mailbox_once(
        dry_run=args.dry_run,
        include_seen=args.include_seen,
        verbose=args.verbose,
        notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html),
    )
    pprint.pp(result)
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
