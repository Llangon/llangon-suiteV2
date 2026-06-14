from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from email.message import EmailMessage

try:
    from .actuaciones import actuacion_to_dict, summarize_actuaciones
    from .notification_delivery import build_notification_message, send_notification_email_with_settings
except ImportError:
    from actuaciones import actuacion_to_dict, summarize_actuaciones
    from notification_delivery import build_notification_message, send_notification_email_with_settings


def reminder_rows(conn, *, now: datetime | None = None) -> list:
    current = now or datetime.now()
    rows = conn.execute(
        """
        SELECT a.*, l.expediente, l.organismo
        FROM licitacion_actuaciones a
        LEFT JOIN licitaciones l ON l.id = a.licitacion_id
        WHERE a.recordatorio_email = 1
          AND a.estado IN ('pendiente', 'en_curso', 'respondida')
        ORDER BY CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END ASC,
                 a.deadline_at ASC,
                 a.prioridad DESC,
                 a.id DESC
        """
    ).fetchall()
    return [
        row for row in rows
        if actuacion_to_dict(row, now=current)["estado_visual"] in {
            "vencida",
            "vence_hoy",
            "vence_esta_semana",
            "sin_fecha",
        }
    ]


def grouped_reminder_items(rows: list, *, now: datetime | None = None) -> dict[str, list[dict]]:
    current = now or datetime.now()
    groups = {
        "vencidas": [],
        "hoy": [],
        "semana": [],
        "sin_responsable": [],
    }
    for row in rows:
        item = actuacion_to_dict(row, now=current)
        if item["estado_visual"] == "vencida":
            groups["vencidas"].append(item)
        elif item["estado_visual"] == "vence_hoy":
            groups["hoy"].append(item)
        elif item["estado_visual"] == "vence_esta_semana":
            groups["semana"].append(item)
        if not item["responsable_user_id"]:
            groups["sin_responsable"].append(item)
    return groups


def item_line(item: dict) -> str:
    parts = [
        f"{item['expediente'] or 'Sin expediente'}",
        f"{item['organismo'] or 'Sin organismo'}",
        f"{item['titulo']}",
        f"tipo={item['tipo']}",
        f"limite={item['deadline_at'] or 'sin fecha'}",
        f"responsable={item['responsable_user_id'] or 'sin responsable'}",
        f"/app?actuacion_id={item['id']}",
    ]
    return " | ".join(str(part) for part in parts)


def build_reminder_body(rows: list, *, now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now()
    groups = grouped_reminder_items(rows, now=current)
    summary = summarize_actuaciones(rows, now=current)
    sections = [
        ("Actuaciones vencidas", groups["vencidas"]),
        ("Vencen hoy", groups["hoy"]),
        ("Vencen en los proximos 7 dias", groups["semana"]),
        ("Sin responsable", groups["sin_responsable"]),
    ]
    text_lines = [
        "Resumen de actuaciones y vencimientos",
        (
            f"Abiertas: {summary['total_abiertas']} | Vencidas: {summary['vencidas']} | "
            f"Hoy: {summary['vencen_hoy']} | Semana: {summary['vencen_semana']} | "
            f"Sin responsable: {summary['sin_responsable']}"
        ),
        "",
    ]
    html_sections = [
        "<h1>Resumen de actuaciones y vencimientos</h1>",
        (
            f"<p>Abiertas: {summary['total_abiertas']} | Vencidas: {summary['vencidas']} | "
            f"Hoy: {summary['vencen_hoy']} | Semana: {summary['vencen_semana']} | "
            f"Sin responsable: {summary['sin_responsable']}</p>"
        ),
    ]
    for title, items in sections:
        text_lines.append(title)
        if items:
            text_lines.extend(f"- {item_line(item)}" for item in items)
            html_sections.append(f"<h2>{title}</h2><ul>")
            html_sections.extend(f"<li>{item_line(item)}</li>" for item in items)
            html_sections.append("</ul>")
        else:
            text_lines.append("- Sin elementos")
            html_sections.append(f"<h2>{title}</h2><p>Sin elementos</p>")
        text_lines.append("")
    return "\n".join(text_lines).strip(), "\n".join(html_sections)


def build_dry_run_message(*, smtp_from: str, recipients: Sequence[str], rows: list) -> EmailMessage:
    text, html = build_reminder_body(rows)
    return build_notification_message(
        smtp_from=smtp_from,
        recipients=recipients,
        subject="Actuaciones y vencimientos",
        text_body=text,
        html_body=html,
        logo_path=None,
    )


def send_reminder_email(
    *,
    settings: dict[str, object],
    recipients: Sequence[str],
    rows: list,
    now,
    smtp_factory,
    smtp_ssl_factory,
) -> tuple[str | None, str | None]:
    text, html = build_reminder_body(rows)
    return send_notification_email_with_settings(
        settings=settings,
        recipients=recipients,
        subject="Actuaciones y vencimientos",
        body=text,
        html_body=html,
        logo_path=None,
        now=now,
        smtp_factory=smtp_factory,
        smtp_ssl_factory=smtp_ssl_factory,
    )
