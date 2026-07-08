from __future__ import annotations

from collections.abc import Callable, Sequence
from email.message import EmailMessage
import mimetypes
from pathlib import Path
from typing import Any

try:
    from .normalization import bool_text, clean_text
except ImportError:
    from normalization import bool_text, clean_text


UserGetter = Callable[[object], dict | None]
UserLister = Callable[..., list[dict]]
NowFactory = Callable[[], str]
SmtpFactory = Callable[..., Any]


def notification_recipients_for_target(
    usuario_destino: str | None,
    *,
    get_user: UserGetter,
    list_users: UserLister,
) -> list[str]:
    destinatario = clean_text(usuario_destino)
    if destinatario:
        user = get_user(destinatario)
        users = [user] if user and user.get("active") else []
    else:
        users = list_users(active_only=True)
    emails = []
    for user in users:
        email = clean_text(user.get("email"))
        if email and email not in emails:
            emails.append(email)
    return emails


def attach_logo_to_message(message: EmailMessage, logo_path: Path) -> None:
    if not logo_path.exists():
        return

    try:
        html_part = next((part for part in message.walk() if part.get_content_type() == "text/html"), None)
        if html_part is None:
            return
        html_part.add_related(logo_path.read_bytes(), maintype="image", subtype="png", cid="<llangon-logo>")
    except Exception:
        return


def attach_files_to_message(message: EmailMessage, attachments: Sequence[Path] | None) -> None:
    for attachment in attachments or []:
        path = Path(attachment)
        if not path.exists() or not path.is_file():
            continue
        guessed_type, _encoding = mimetypes.guess_type(path.name)
        if guessed_type and "/" in guessed_type:
            maintype, subtype = guessed_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)


def build_notification_message(
    *,
    smtp_from: str,
    recipients: Sequence[str],
    subject: str,
    text_body: str,
    html_body: str,
    logo_path: Path | None = None,
    attachments: Sequence[Path] | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    if logo_path:
        attach_logo_to_message(message, logo_path)
    attach_files_to_message(message, attachments)
    return message


def send_notification_email_with_settings(
    *,
    settings: dict[str, object],
    recipients: Sequence[str],
    subject: str,
    body: str,
    html_body: str,
    logo_path: Path | None,
    attachments: Sequence[Path] | None = None,
    now: NowFactory,
    smtp_factory: SmtpFactory,
    smtp_ssl_factory: SmtpFactory,
) -> tuple[str | None, str | None]:
    smtp_host = clean_text(settings.get("smtp_host"))
    smtp_port = int(clean_text(settings.get("smtp_port")) or "587")
    smtp_user = clean_text(settings.get("smtp_user"))
    smtp_password = clean_text(settings.get("smtp_password"))
    smtp_from = clean_text(settings.get("smtp_from")) or smtp_user
    smtp_use_ssl = bool_text(settings.get("smtp_ssl"))
    smtp_use_tls = bool_text(settings.get("smtp_tls", "1"))
    if not smtp_host:
        return None, "SMTP no configurado"
    if not smtp_from:
        return None, "Remitente SMTP no configurado"
    if not recipients:
        return None, "El usuario de destino no tiene email configurado"

    message = build_notification_message(
        smtp_from=smtp_from,
        recipients=recipients,
        subject=subject,
        text_body=body or subject,
        html_body=html_body,
        logo_path=logo_path,
        attachments=attachments,
    )

    try:
        if smtp_use_ssl:
            server = smtp_ssl_factory(smtp_host, smtp_port, timeout=20)
        else:
            server = smtp_factory(smtp_host, smtp_port, timeout=20)
        with server:
            if smtp_use_tls and not smtp_use_ssl:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return now(), None
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == 10013:
            return None, (
                "Windows ha bloqueado la conexión SMTP saliente "
                f"({smtp_host}:{smtp_port}). Revisa firewall, antivirus, proxy o permisos de red."
            )
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


def create_notification_record(
    conn: Any,
    *,
    usuario_origen: str | None,
    usuario_destino: str | None,
    asunto: str,
    cuerpo: str,
    ficheros_adjuntos: str,
    sent_at: str | None,
    email_error: str | None,
    timestamp: str,
) -> int:
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
