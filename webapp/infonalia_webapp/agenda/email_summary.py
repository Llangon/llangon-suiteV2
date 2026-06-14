from __future__ import annotations

import html


def _event_line(event: dict[str, object]) -> str:
    date_text = event.get("datetime") or event.get("date") or "Sin fecha"
    linked = event.get("linked_licitaciones") or []
    linked_text = ""
    if linked:
        labels = [
            str(item.get("expediente") or item.get("organismo") or item.get("id") or "")
            for item in linked
        ]
        linked_text = f" | Licitaciones: {', '.join(label for label in labels if label)}"
    return (
        f"- [{event.get('source_type')}] {event.get('title')} | "
        f"{date_text} | {event.get('status')}{linked_text}"
    )


def build_agenda_email_summary(agenda_response: dict[str, object]) -> str:
    groups = agenda_response.get("groups") or {}
    labels = [
        ("overdue", "Vencidos abiertos"),
        ("day", "Fecha activa"),
        ("upcoming", "Próximos"),
        ("no_date", "Sin fecha"),
    ]
    lines = [
        "Resumen de Agenda",
        f"Vista: {agenda_response.get('view')}",
        f"Fecha activa: {agenda_response.get('active_date_label') or agenda_response.get('date')}",
        "",
    ]
    for key, title in labels:
        events = groups.get(key) or []
        lines.append(title)
        if events:
            lines.extend(_event_line(event) for event in events)
        else:
            lines.append("- Sin elementos")
        lines.append("")
    return "\n".join(lines).strip()


def build_agenda_email_html(agenda_response: dict[str, object]) -> str:
    text = build_agenda_email_summary(agenda_response)
    escaped = html.escape(text).replace("\n", "<br>")
    return f"<h1>Resumen de Agenda</h1><p>{escaped}</p>"
