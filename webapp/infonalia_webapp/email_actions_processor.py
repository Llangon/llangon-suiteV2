from __future__ import annotations

import argparse
import email
import imaplib
import logging
import os
import pprint
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from typing import Any

try:
    from .email_actions import (
        action_notify_email,
        check_action_code,
        extract_action_code,
        process_email_action,
        split_emails,
    )
    from .normalization import clean_text
    from .operational_settings import effective_text
except ImportError:
    from email_actions import (
        action_notify_email,
        check_action_code,
        extract_action_code,
        process_email_action,
        split_emails,
    )
    from normalization import clean_text
    from operational_settings import effective_text


LOGGER = logging.getLogger(__name__)
COMMAND_SUBJECT_PREFIX = "LLANGON_CMD"
HEADER_PEEK_QUERY = "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM REPLY-TO MESSAGE-ID)])"
FULL_PEEK_QUERY = "(BODY.PEEK[])"


@dataclass(frozen=True)
class MailboxConfig:
    host: str
    port: int
    user: str
    password: str
    folder: str
    allowed_senders: list[str]
    notify_email: str

    @property
    def complete(self) -> bool:
        return bool(self.host and self.port and self.user and self.password and self.folder)


def mailbox_config_from_env(
    environ: dict[str, str] | None = None,
    settings: dict[str, object] | None = None,
) -> MailboxConfig:
    env = environ or os.environ
    suite_settings = {} if settings is None else settings
    return MailboxConfig(
        host=effective_text("actions_imap_host", settings=suite_settings, environ=env),
        port=int(effective_text("actions_imap_port", settings=suite_settings, environ=env) or "993"),
        user=effective_text("actions_imap_user", settings=suite_settings, environ=env),
        password=clean_text(env.get("LLANGON_ACTIONS_IMAP_PASSWORD")),
        folder=effective_text("actions_imap_folder", settings=suite_settings, environ=env) or "INBOX",
        allowed_senders=split_emails(effective_text("action_allowed_senders", settings=suite_settings, environ=env)),
        notify_email=effective_text("action_notify_email", settings=suite_settings, environ=env) or action_notify_email(env),
    )


def safe_subject(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    try:
        return clean_text(str(make_header(decode_header(text))))
    except Exception:
        return text


def is_command_subject(subject: object) -> bool:
    return safe_subject(subject).startswith(COMMAND_SUBJECT_PREFIX)


def _message_text(message: Message) -> str:
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
        return "\n".join(parts)
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")
    return clean_text(message.get_payload())


def _sender_email(message: Message) -> str:
    sender = clean_text(message.get("Reply-To")) or clean_text(message.get("From"))
    parsed = email.utils.parseaddr(sender)[1]
    return clean_text(parsed).lower()


def _fetch_bytes(fetch_data: object) -> bytes:
    if not fetch_data:
        return b""
    for item in fetch_data if isinstance(fetch_data, list) else [fetch_data]:
        if isinstance(item, tuple) and len(item) >= 2 and item[1]:
            return item[1]
    return b""


def _counter_increment(container: dict[str, int], key: object) -> None:
    label = clean_text(key) or "desconocido"
    container[label] = container.get(label, 0) + 1


def _initial_summary(config: MailboxConfig, *, mode: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "mode": mode,
        "mailbox_user": config.user,
        "folder": config.folder,
        "processed": 0,
        "candidates_seen": 0,
        "invalid_candidates": 0,
        "errors": 0,
        "skipped_non_candidates": 0,
        "ignored_by_reason": {},
        "errors_by_reason": {},
        "total_messages_with_action_code": 0,
        "total_valid_pending_codes": 0,
        "total_duplicate_codes": 0,
        "total_unauthorized_senders": 0,
    }


def _search_command_uids(client: Any, *, include_seen: bool, scan_all: bool) -> tuple[str, list[bytes]]:
    if scan_all:
        criteria: tuple[object, ...] = ("ALL",) if include_seen else ("UNSEEN",)
    elif include_seen:
        criteria = ("HEADER", "Subject", COMMAND_SUBJECT_PREFIX)
    else:
        criteria = ("UNSEEN", "HEADER", "Subject", COMMAND_SUBJECT_PREFIX)
    status, data = client.uid("SEARCH", None, *criteria)
    uids = (data[0] or b"").split() if status == "OK" and data else []
    return status, uids


def _fetch_header_message(client: Any, uid: bytes) -> Message | None:
    status, data = client.uid("FETCH", uid, HEADER_PEEK_QUERY)
    if status != "OK":
        return None
    raw = _fetch_bytes(data)
    return email.message_from_bytes(raw) if raw else None


def _fetch_full_message(client: Any, uid: bytes) -> Message | None:
    status, data = client.uid("FETCH", uid, FULL_PEEK_QUERY)
    if status != "OK":
        return None
    raw = _fetch_bytes(data)
    return email.message_from_bytes(raw) if raw else None


def process_mailbox_once(
    *,
    db_session_factory,
    notification_sender,
    config: MailboxConfig | None = None,
    settings: dict[str, object] | None = None,
    imap_factory=imaplib.IMAP4_SSL,
    dry_run: bool = False,
    verbose: bool = False,
    limit: int | None = None,
    include_seen: bool = False,
    scan_all: bool = False,
    mark_invalid_read: bool = False,
) -> dict[str, object]:
    config = config or mailbox_config_from_env(settings=settings)
    if not config.complete:
        message = "Procesador de órdenes por correo desactivado: falta configuración IMAP."
        LOGGER.info(message)
        return {"enabled": False, "processed": 0, "message": message}

    mode = "scan_all" if scan_all else "llangon_cmd_only"
    summary = _initial_summary(config, mode=mode)
    if scan_all:
        summary["total_messages_seen"] = 0

    with imap_factory(config.host, config.port) as client:
        client.login(config.user, config.password)
        client.select(config.folder)
        status, uids = _search_command_uids(client, include_seen=include_seen, scan_all=scan_all)
        if status != "OK":
            summary["errors"] += 1
            _counter_increment(summary["errors_by_reason"], "error búsqueda IMAP")
            summary["message"] = "No se pudo consultar el buzón."
            return summary

        reviewed_candidates = 0
        for uid in uids:
            if scan_all:
                summary["total_messages_seen"] += 1
            if limit is not None and reviewed_candidates >= limit:
                break

            header_message = _fetch_header_message(client, uid)
            if not header_message:
                summary["errors"] += 1
                _counter_increment(summary["errors_by_reason"], "error lectura cabecera")
                continue
            subject = safe_subject(header_message.get("Subject"))
            if not is_command_subject(subject):
                if scan_all:
                    summary["skipped_non_candidates"] += 1
                continue

            reviewed_candidates += 1
            summary["candidates_seen"] += 1
            message = _fetch_full_message(client, uid)
            if not message:
                summary["errors"] += 1
                _counter_increment(summary["errors_by_reason"], "error lectura candidato")
                continue
            subject = safe_subject(message.get("Subject"))
            sender = _sender_email(message)
            body = _message_text(message)
            code = extract_action_code(subject, body)
            if code:
                summary["total_messages_with_action_code"] += 1
            else:
                summary["invalid_candidates"] += 1
                _counter_increment(summary["ignored_by_reason"], "sin código")
                if verbose:
                    LOGGER.info("Candidato sin código: from=%s subject=%s", sender, subject)
                if mark_invalid_read and not dry_run:
                    client.uid("STORE", uid, "+FLAGS", "\\Seen")
                continue

            source_message_id = clean_text(message.get("Message-ID")) or uid.decode("ascii", errors="ignore")

            def send_confirmation(confirm_subject: str, confirm_body: str, confirm_html: str) -> None:
                notification_sender(config.notify_email, confirm_subject, confirm_body, confirm_html)

            with db_session_factory() as conn:
                check = check_action_code(
                    conn,
                    code=code,
                    sender_email=sender,
                    allowed_senders=config.allowed_senders,
                )
                if check.get("processable"):
                    summary["total_valid_pending_codes"] += 1
                elif check.get("reason") == "código ya procesado":
                    summary["total_duplicate_codes"] += 1
                elif check.get("reason") in {"remitente no autorizado", "sin remitentes autorizados configurados"}:
                    summary["total_unauthorized_senders"] += 1

                result = process_email_action(
                    conn,
                    code=code,
                    sender_email=sender,
                    source_message_id=source_message_id,
                    subject=subject,
                    allowed_senders=config.allowed_senders,
                    confirmation_sender=send_confirmation,
                    dry_run=dry_run,
                )

            result_status = clean_text(result.get("status"))
            reason = clean_text(result.get("error_code") or result.get("message"))
            if verbose:
                LOGGER.info(
                    "Candidato LLANGON_CMD: from=%s subject=%s code=%s result=%s reason=%s",
                    sender,
                    subject,
                    code,
                    result_status,
                    reason,
                )
            if result_status == "processed":
                summary["processed"] += 1
                if not dry_run:
                    client.uid("STORE", uid, "+FLAGS", "\\Seen")
            elif result_status == "dry_run":
                _counter_increment(summary["ignored_by_reason"], "dry-run")
            elif result_status == "ignored":
                _counter_increment(summary["ignored_by_reason"], reason or "ignorado")
                if result.get("error_code") in {"DUPLICATE_EMAIL_ACTION", "AI_SUMMARY_DISABLED"}:
                    if result.get("error_code") == "DUPLICATE_EMAIL_ACTION":
                        summary["total_duplicate_codes"] += 1
                    if not dry_run:
                        client.uid("STORE", uid, "+FLAGS", "\\Seen")
            else:
                summary["errors"] += 1
                _counter_increment(summary["errors_by_reason"], reason or "error")
                if mark_invalid_read and not dry_run:
                    client.uid("STORE", uid, "+FLAGS", "\\Seen")

    return summary


def check_code_payload(
    db_session_factory,
    code: str,
    settings: dict[str, object] | None = None,
) -> dict[str, object]:
    config = mailbox_config_from_env(settings=settings)
    with db_session_factory() as conn:
        return check_action_code(conn, code=code, allowed_senders=config.allowed_senders)


def simulate_code_payload(
    db_session_factory,
    *,
    code: str,
    from_email: str,
    dry_run: bool,
    settings: dict[str, object] | None = None,
) -> dict[str, object]:
    config = mailbox_config_from_env(settings=settings)
    with db_session_factory() as conn:
        return process_email_action(
            conn,
            code=code,
            sender_email=from_email,
            source_message_id="manual-simulation",
            subject=f"{COMMAND_SUBJECT_PREFIX} {code}",
            allowed_senders=config.allowed_senders,
            dry_run=dry_run,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Procesa órdenes por correo de Llangón Suite.")
    parser.add_argument("--once", action="store_true", help="Procesa el buzón una sola vez y termina.")
    parser.add_argument("--verbose", action="store_true", help="Muestra detalle de candidatos LLANGON_CMD.")
    parser.add_argument("--limit", type=int, default=None, help="Limita el número de candidatos LLANGON_CMD revisados.")
    parser.add_argument("--include-seen", action="store_true", help="Incluye órdenes LLANGON_CMD ya leídas.")
    parser.add_argument("--scan-all", action="store_true", help="Modo diagnóstico: inspecciona cabeceras de todo el buzón sin marcar como leído.")
    parser.add_argument("--dry-run", action="store_true", help="Valida lo que haría sin ejecutar acciones ni marcar correos.")
    parser.add_argument("--mark-invalid-read", action="store_true", help="Marca como leídos candidatos LLANGON_CMD inválidos. No usar en pruebas iniciales.")
    parser.add_argument("--check-code", help="Valida un código concreto contra la base de datos sin leer IMAP.")
    parser.add_argument("--simulate-code", help="Simula o ejecuta un código concreto sin leer IMAP.")
    parser.add_argument("--from-email", help="Remitente a usar con --simulate-code.")
    args = parser.parse_args(argv)

    if not args.once and not args.check_code and not args.simulate_code:
        parser.error("Usa --once, --check-code o --simulate-code.")
    if args.simulate_code and not args.from_email:
        parser.error("--simulate-code requiere --from-email.")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser mayor que 0.")

    try:
        from . import app
    except ImportError:
        import app  # type: ignore
    settings = app.get_settings()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.check_code:
        payload = check_code_payload(app.db_session, args.check_code, settings=settings)
        pprint.pp(payload)
        return 0

    if args.simulate_code:
        payload = simulate_code_payload(
            app.db_session,
            code=args.simulate_code,
            from_email=args.from_email,
            dry_run=args.dry_run,
            settings=settings,
        )
        pprint.pp(payload)
        return 0 if payload.get("status") in {"processed", "dry_run", "ignored"} else 1

    def sender(to_email: str, subject: str, body: str, html_body: str) -> None:
        sent_at, error = app.send_monitor_email(to_email, subject, body, html_body, settings=settings)
        if error:
            LOGGER.warning("No se pudo enviar confirmación de orden por correo: %s", error)
        else:
            LOGGER.info("Confirmación de orden enviada a %s en %s", to_email, sent_at)

    result = process_mailbox_once(
        db_session_factory=app.db_session,
        notification_sender=sender,
        settings=settings,
        dry_run=args.dry_run,
        verbose=args.verbose,
        limit=args.limit,
        include_seen=args.include_seen,
        scan_all=args.scan_all,
        mark_invalid_read=args.mark_invalid_read,
    )
    pprint.pp(result)
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
