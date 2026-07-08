from __future__ import annotations

import logging
import re
import smtplib
import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ..ai_summary_pdf import generate_ai_summary_pdf
from ..email_templates import build_llangon_email_shell
from ..notification_delivery import send_notification_email_with_settings
from ..formatting import format_date_es
from ..normalization import clean_text


EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
EMAIL_EXTRACT_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
LOGGER = logging.getLogger(__name__)


class EmailListError(ValueError):
    pass


def ensure_ai_notifications_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            licitacion_id INTEGER NOT NULL,
            requested_by TEXT,
            recipient_email TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent_at TEXT,
            error_message TEXT,
            attempts INTEGER DEFAULT 0,
            manual INTEGER DEFAULT 0,
            pdf_path TEXT,
            pdf_generated_at TEXT,
            pdf_attached INTEGER DEFAULT 0,
            pdf_error TEXT,
            FOREIGN KEY (job_id) REFERENCES ai_analysis_jobs(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_analysis_notifications)").fetchall()}
    for column, definition in (
        ("pdf_path", "TEXT"),
        ("pdf_generated_at", "TEXT"),
        ("pdf_attached", "INTEGER DEFAULT 0"),
        ("pdf_error", "TEXT"),
    ):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE ai_analysis_notifications ADD COLUMN {column} {definition}")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_notifications_job_recipient
        ON ai_analysis_notifications(job_id, recipient_email)
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_notifications_job ON ai_analysis_notifications(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_notifications_licitacion ON ai_analysis_notifications(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_notifications_status ON ai_analysis_notifications(status)")


def normalize_email_list(value: object, *, required: bool = False) -> list[str]:
    if value is None:
        parts: list[str] = []
    elif isinstance(value, str):
        parts = re.split(r"[,;\n\r]+", value)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = []
        for item in value:
            parts.extend(re.split(r"[,;\n\r]+", clean_text(item)))
    else:
        raise EmailListError("La lista de destinatarios no es válida.")

    emails: list[str] = []
    invalid: list[str] = []
    for raw in parts:
        text = clean_text(raw).strip().strip("<>[]()")
        if not text:
            continue
        if text.lower().startswith("mailto:"):
            text = text[7:]
        extracted = EMAIL_EXTRACT_RE.findall(text)
        candidate = extracted[0] if extracted and ("mailto:" in text.lower() or "[" in text or "]" in text) else text
        candidate = clean_text(candidate).lower()
        if not EMAIL_RE.match(candidate):
            invalid.append(text)
            continue
        if candidate not in emails:
            emails.append(candidate)

    if invalid:
        raise EmailListError("Email no válido: " + ", ".join(invalid))
    if required and not emails:
        raise EmailListError("Indica al menos un email de destino válido.")
    return emails


def create_job_notifications(
    conn: sqlite3.Connection,
    *,
    job_id: int,
    licitacion_id: int,
    requested_by: str,
    recipients: Sequence[str],
    created_at: str,
    manual: bool = False,
) -> int:
    ensure_ai_notifications_schema(conn)
    count = 0
    for recipient in normalize_email_list(list(recipients)):
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO ai_analysis_notifications (
                job_id, licitacion_id, requested_by, recipient_email, status, created_at, manual
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (job_id, licitacion_id, clean_text(requested_by), recipient, created_at, 1 if manual else 0),
        )
        count += int(cur.rowcount or 0)
    return count


def notification_rows_for_job(conn: sqlite3.Connection, job_id: int) -> list[sqlite3.Row]:
    ensure_ai_notifications_schema(conn)
    return conn.execute(
        """
        SELECT * FROM ai_analysis_notifications
        WHERE job_id = ?
        ORDER BY id ASC
        """,
        (job_id,),
    ).fetchall()


def latest_notification_rows_for_licitacion(conn: sqlite3.Connection, licitacion_id: int) -> list[sqlite3.Row]:
    ensure_ai_notifications_schema(conn)
    row = conn.execute(
        """
        SELECT job_id
        FROM ai_analysis_notifications
        WHERE licitacion_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (licitacion_id,),
    ).fetchone()
    if not row:
        return []
    return notification_rows_for_job(conn, int(row["job_id"]))


def notification_status_payload(rows: Sequence[sqlite3.Row]) -> dict[str, object]:
    items = [
        {
            "recipient_email": row["recipient_email"],
            "status": row["status"],
            "sent_at": row["sent_at"] or "",
            "error_message": row["error_message"] or "",
            "manual": bool(row["manual"] or 0),
        }
        for row in rows
    ]
    sent = sum(1 for item in items if item["status"] == "sent")
    error = sum(1 for item in items if item["status"] == "error")
    pending = sum(1 for item in items if item["status"] == "pending")
    skipped = sum(1 for item in items if item["status"] == "skipped")
    if not items:
        label = "Sin aviso por email."
        state = "none"
    elif sent and not error and not pending:
        label = f"Aviso enviado a {sent} destinatario{'s' if sent != 1 else ''}."
        state = "sent"
    elif sent and error:
        label = f"Aviso enviado a {sent} destinatario{'s' if sent != 1 else ''}. Error en {error}."
        state = "partial"
    elif error and not sent:
        label = "No se pudo enviar el aviso por email."
        state = "error"
    elif pending:
        label = "Aviso pendiente de envío."
        state = "pending"
    elif skipped:
        label = "Aviso no enviado porque el análisis no finalizó correctamente."
        state = "skipped"
    else:
        label = "Sin aviso por email."
        state = "none"
    return {
        "state": state,
        "label": label,
        "sent_count": sent,
        "error_count": error,
        "pending_count": pending,
        "skipped_count": skipped,
        "items": items,
    }


def settings_from_conn(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {row["key"]: row["value"] or "" for row in conn.execute("SELECT key, value FROM app_settings")}
    except sqlite3.OperationalError:
        return {}


def _summary_section(title: str, content: str) -> str:
    if not clean_text(content):
        return ""
    return f"<h3>{title}</h3><p>{content}</p>"


def _list_html(values: object) -> str:
    if not isinstance(values, list) or not values:
        return ""
    parts: list[str] = []
    for item in values[:8]:
        if isinstance(item, dict):
            text = "; ".join(f"{key}: {value}" for key, value in item.items() if clean_text(value))
        else:
            text = clean_text(item)
        if text:
            parts.append(f"<li>{_escape(text)}</li>")
    return "<ul>" + "".join(parts) + "</ul>" if parts else ""


def _escape(value: object) -> str:
    import html

    return html.escape(clean_text(value))


def _row_value(row: sqlite3.Row, key: str) -> str:
    try:
        return clean_text(row[key])
    except (IndexError, KeyError):
        return ""


def build_ai_summary_email(
    licitacion: sqlite3.Row,
    summary: dict[str, Any],
    *,
    provider: str,
    selected_documents: Sequence[dict[str, object]],
) -> tuple[str, str, str]:
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    ejecutivo = summary.get("resumen_ejecutivo") if isinstance(summary.get("resumen_ejecutivo"), dict) else {}
    docs = ", ".join(clean_text(doc.get("name") or doc.get("relative_path")) for doc in selected_documents if isinstance(doc, dict))
    titulo = _row_value(licitacion, "objeto") or clean_text(metadata.get("titulo"))
    expediente = _row_value(licitacion, "expediente") or clean_text(metadata.get("expediente"))
    organismo = _row_value(licitacion, "organismo") or clean_text(metadata.get("organismo"))
    fecha_limite = " ".join(part for part in [format_date_es(_row_value(licitacion, "fecha_limite")), _row_value(licitacion, "hora_limite")] if part).strip()
    presupuesto = _row_value(licitacion, "presupuesto") or "No consta"
    subject = f"Análisis IA disponible - {expediente} - {titulo[:70]}".strip()
    resumen = clean_text(ejecutivo.get("texto")) or "El detalle completo se adjunta en PDF."
    text_intro = "Adjuntamos el resumen IA en PDF para su revisión."
    lines = [
        "El análisis IA solicitado ya está disponible.",
        text_intro,
        "",
        f"Expediente: {expediente}",
        f"Título: {titulo}",
        f"Organismo: {organismo}",
        f"Fecha límite: {fecha_limite or 'No consta'}",
        f"Presupuesto: {presupuesto}",
        f"Proveedor IA: {provider}",
        f"Documentos analizados: {docs or 'No consta'}",
        "",
        resumen,
        "",
        "Revisar siempre contra los pliegos antes de usarlo con clientes.",
    ]
    body_html = f"""
      <p style="margin:0 0 14px 0;">El análisis IA solicitado ya está disponible.</p>
      <p style="margin:0 0 18px 0;">Adjuntamos el resumen en PDF para que lo puedas revisar con calma.</p>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:0 0 18px 0;">
        <tr><td style="padding:0 0 8px 0; color:#667085; width:150px;"><strong>Expediente</strong></td><td style="padding:0 0 8px 0;">{_escape(expediente)}</td></tr>
        <tr><td style="padding:0 0 8px 0; color:#667085;"><strong>Título</strong></td><td style="padding:0 0 8px 0;">{_escape(titulo)}</td></tr>
        <tr><td style="padding:0 0 8px 0; color:#667085;"><strong>Organismo</strong></td><td style="padding:0 0 8px 0;">{_escape(organismo)}</td></tr>
        <tr><td style="padding:0 0 8px 0; color:#667085;"><strong>Fecha límite</strong></td><td style="padding:0 0 8px 0;">{_escape(fecha_limite or 'No consta')}</td></tr>
        <tr><td style="padding:0 0 8px 0; color:#667085;"><strong>Proveedor IA</strong></td><td style="padding:0 0 8px 0;">{_escape(provider)}</td></tr>
      </table>
      <p style="margin:0 0 12px 0;"><strong>Resumen breve</strong></p>
      <p style="margin:0 0 18px 0; line-height:1.55;">{_escape(resumen)}</p>
      <p style="margin:0; color:#667085;">Documentos analizados: {_escape(docs or 'No consta')}</p>
    """
    html = build_llangon_email_shell(
        eyebrow="Resumen IA adjunto",
        title=expediente or "Análisis IA disponible",
        subtitle=titulo,
        body_html=body_html,
        footer_left_html="Adjunto: resumen IA en PDF",
        footer_right_html=f"Fecha límite: {_escape(fecha_limite or 'No consta')}",
        closing_html="<strong>Aviso:</strong> Análisis automático. Revisar siempre contra los pliegos antes de usarlo con clientes.",
        compact=False,
    )
    return subject, "\n".join(line for line in lines if line is not None), html


def mark_job_notifications_skipped(conn: sqlite3.Connection, job_id: int, reason: str, *, now: Callable[[], str]) -> int:
    ensure_ai_notifications_schema(conn)
    cur = conn.execute(
        """
        UPDATE ai_analysis_notifications
        SET status = 'skipped', error_message = ?
        WHERE job_id = ? AND status = 'pending'
        """,
        (clean_text(reason), job_id),
    )
    return int(cur.rowcount or 0)


def send_pending_job_notifications(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    now: Callable[[], str],
    subject_override: str = "",
    pdf_output_root: Path | None = None,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
    smtp_ssl_factory: Callable[..., Any] = smtplib.SMTP_SSL,
) -> dict[str, object]:
    ensure_ai_notifications_schema(conn)
    pending = conn.execute(
        """
        SELECT n.*, j.provider, j.model, j.selected_documents_json, j.document_hash,
               l.*
        FROM ai_analysis_notifications n
        JOIN ai_analysis_jobs j ON j.id = n.job_id
        JOIN licitaciones l ON l.id = n.licitacion_id
        WHERE n.job_id = ? AND n.status = 'pending'
        ORDER BY n.id ASC
        """,
        (job_id,),
    ).fetchall()
    if not pending:
        return {"sent": 0, "error": 0}

    summary_row = conn.execute(
        """
        SELECT summary_json
        FROM ai_summaries
        WHERE created_from_job_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    if not summary_row:
        mark_job_notifications_skipped(conn, job_id, "No hay resumen IA útil para enviar.", now=now)
        return {"sent": 0, "error": 0}

    import json

    summary = json.loads(summary_row["summary_json"] or "{}")
    first = pending[0]
    selected = json.loads(first["selected_documents_json"] or "[]")
    subject, body, html_body = build_ai_summary_email(first, summary, provider=clean_text(first["provider"]), selected_documents=selected)
    if clean_text(subject_override):
        subject = clean_text(subject_override)
    pdf_result = generate_ai_summary_pdf(
        first,
        summary,
        selected_documents=selected,
        generated_at=now(),
        fallback_root=pdf_output_root,
    )
    if not pdf_result.ok:
        error_message = pdf_result.error or "No se pudo generar el PDF del resumen IA."
        LOGGER.error("No se enviará el resumen IA job_id=%s porque el PDF no pudo generarse: %s", job_id, error_message)
        for row in pending:
            conn.execute(
                """
                UPDATE ai_analysis_notifications
                SET status = 'error', attempts = COALESCE(attempts, 0) + 1, error_message = ?,
                    pdf_path = '', pdf_generated_at = ?, pdf_attached = 0, pdf_error = ?
                WHERE id = ?
                """,
                (error_message, now(), error_message, row["id"]),
            )
        return {"sent": 0, "error": len(pending), "pdf_path": "", "pdf_warning": "", "pdf_error": error_message}
    attachments = [Path(pdf_result.path)]
    if pdf_result.warning:
        LOGGER.warning("PDF IA generado con fallback job_id=%s path=%s", job_id, pdf_result.path)
    pdf_generated_at = now()
    for row in pending:
        conn.execute(
            """
            UPDATE ai_analysis_notifications
            SET pdf_path = ?, pdf_generated_at = ?, pdf_attached = 0, pdf_error = ?
            WHERE id = ?
            """,
            (pdf_result.path, pdf_generated_at, clean_text(pdf_result.warning), row["id"]),
        )
    settings = settings_from_conn(conn)
    sent = 0
    errors = 0
    for row in pending:
        sent_at, error = send_notification_email_with_settings(
            settings=settings,
            recipients=[row["recipient_email"]],
            subject=subject,
            body=body,
            html_body=html_body,
            logo_path=STATIC_ROOT / "logo-llangon.png",
            attachments=attachments,
            now=now,
            smtp_factory=smtp_factory,
            smtp_ssl_factory=smtp_ssl_factory,
        )
        if error:
            errors += 1
            conn.execute(
                """
                UPDATE ai_analysis_notifications
                SET status = 'error', attempts = COALESCE(attempts, 0) + 1, error_message = ?, pdf_attached = 0
                WHERE id = ?
                """,
                (clean_text(error), row["id"]),
            )
        else:
            sent += 1
            conn.execute(
                """
                UPDATE ai_analysis_notifications
                SET status = 'sent', attempts = COALESCE(attempts, 0) + 1, sent_at = ?, error_message = '', pdf_attached = 1
                WHERE id = ?
                """,
                (sent_at or now(), row["id"]),
            )
    return {
        "sent": sent,
        "error": errors,
        "pdf_path": pdf_result.path,
        "pdf_warning": pdf_result.warning,
        "pdf_error": "",
    }


def generate_ai_summary_pdf_and_email(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    recipients: Sequence[str],
    requested_by: str,
    now: Callable[[], str],
    subject_override: str = "",
    pdf_output_root: Path | None = None,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
    smtp_ssl_factory: Callable[..., Any] = smtplib.SMTP_SSL,
) -> dict[str, object]:
    ensure_ai_notifications_schema(conn)
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
        raise ValueError("No hay un análisis IA útil para enviar.")
    job_id = int(summary_row["created_from_job_id"] or 0)
    if not job_id:
        raise ValueError("El análisis IA no tiene job asociado para registrar el envío.")
    create_job_notifications(
        conn,
        job_id=job_id,
        licitacion_id=licitacion_id,
        requested_by=clean_text(requested_by) or "ui",
        recipients=normalize_email_list(list(recipients), required=True),
        created_at=now(),
        manual=True,
    )
    result = send_pending_job_notifications(
        conn,
        job_id,
        now=now,
        subject_override=subject_override,
        pdf_output_root=pdf_output_root,
        smtp_factory=smtp_factory,
        smtp_ssl_factory=smtp_ssl_factory,
    )
    result["job_id"] = job_id
    return result
