from __future__ import annotations

import html
from datetime import datetime

try:
    from ..email_templates import build_llangon_email_shell
    from ..formatting import format_datetime_es
    from ..normalization import clean_text
except ImportError:
    from email_templates import build_llangon_email_shell
    from formatting import format_datetime_es
    from normalization import clean_text


TYPE_STYLES = {
    "actuacion": {
        "label": "Actuación",
        "color": "#d92d20",
        "background": "#fff5f5",
        "border": "#f4b4ad",
    },
    "licitacion": {
        "label": "Licitación",
        "color": "#b7791f",
        "background": "#fff8e1",
        "border": "#ead48a",
    },
    "interno": {
        "label": "Interno",
        "color": "#2563eb",
        "background": "#eff6ff",
        "border": "#bfdbfe",
    },
    "vencido": {
        "label": "Vencido",
        "color": "#344054",
        "background": "#f2f4f7",
        "border": "#d0d5dd",
    },
}


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


def _item_title(item: dict[str, object]) -> str:
    return str(
        item.get("title")
        or item.get("expediente")
        or item.get("objeto")
        or item.get("organismo")
        or item.get("id")
        or "Sin título"
    )


def _item_date(item: dict[str, object]) -> str:
    return str(
        item.get("datetime")
        or item.get("date")
        or item.get("deadline_at")
        or item.get("fecha_limite")
        or "Sin fecha"
    )


def _item_expediente(item: dict[str, object]) -> str:
    linked = item.get("linked_licitaciones") or []
    if isinstance(linked, list):
        for linked_item in linked:
            if not isinstance(linked_item, dict):
                continue
            expediente = clean_text(linked_item.get("expediente") or linked_item.get("id"))
            if expediente:
                return expediente
    return clean_text(item.get("expediente") or item.get("source_id")) or "Sin expediente"


def _item_source_key(item: dict[str, object]) -> str:
    if item.get("is_overdue"):
        return "vencido"
    source = clean_text(item.get("color_type") or item.get("source_type")).lower()
    return source if source in TYPE_STYLES else "interno"


def _item_description(item: dict[str, object]) -> str:
    return clean_text(
        item.get("subtitle")
        or item.get("description")
        or item.get("descripcion")
        or item.get("objeto")
        or ""
    )


def _item_linked_text(item: dict[str, object]) -> str:
    linked = item.get("linked_licitaciones") or []
    labels = []
    if isinstance(linked, list):
        for linked_item in linked:
            if not isinstance(linked_item, dict):
                continue
            label = clean_text(
                linked_item.get("expediente")
                or linked_item.get("organismo")
                or linked_item.get("id")
            )
            if label:
                labels.append(label)
    return ", ".join(labels)


def _item_row_html(item: dict[str, object], *, subdued: bool = False) -> str:
    source_key = _item_source_key(item)
    style = TYPE_STYLES[source_key]
    title = html.escape(_item_title(item))
    date_label = html.escape(format_datetime_es(_item_date(item)))
    expediente = html.escape(_item_expediente(item))
    status = html.escape(clean_text(item.get("status")) or "Sin estado")
    description = html.escape(_item_description(item))
    linked = html.escape(_item_linked_text(item))
    opacity_color = "#475467" if subdued else "#1f2937"
    description_html = (
        f"<p style='margin:6px 0 0 0; color:#475467; font-size:13px; line-height:1.35;'>{description}</p>"
        if description
        else ""
    )
    linked_html = (
        f"<p style='margin:7px 0 0 0; color:#667085; font-size:12px; line-height:1.35;'>Licitaciones: {linked}</p>"
        if linked
        else ""
    )
    return f"""
      <tr>
        <td style="padding:0 0 10px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; border:1px solid {style['border']}; border-left:5px solid {style['color']}; background:#ffffff;">
            <tr>
              <td style="padding:12px 14px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:top;">
                      <span style="display:inline-block; padding:3px 8px; background:{style['background']}; color:{style['color']}; border:1px solid {style['border']}; border-radius:999px; font-size:11px; font-weight:800; text-transform:uppercase;">{html.escape(style['label'])}</span>
                    </td>
                    <td align="right" style="vertical-align:top; color:#667085; font-size:12px; white-space:nowrap;">{date_label}</td>
                  </tr>
                </table>
                <p style="margin:9px 0 0 0; color:{opacity_color}; font-size:15px; font-weight:800; line-height:1.35;">{title}</p>
                {description_html}
                <p style="margin:7px 0 0 0; color:#667085; font-size:12px; line-height:1.45;">Expediente: {expediente}</p>
                <p style="margin:3px 0 0 0; color:#667085; font-size:12px; line-height:1.45;">Estado: {status}</p>
                <p style="margin:3px 0 0 0; color:#667085; font-size:12px; line-height:1.45;">Fecha/hora final: {date_label}</p>
                {linked_html}
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _section_html(section: dict[str, object], *, subdued: bool = False) -> str:
    title = clean_text(section.get("title") or "Sección").upper()
    items = section.get("items") or []
    if items:
        rows = "".join(_item_row_html(item, subdued=subdued) for item in items[:16] if isinstance(item, dict))
    else:
        rows = """
      <tr>
        <td style="padding:14px 16px; border:1px solid #d9e2ec; background:#f8fafc; color:#667085; font-size:14px;">
          Sin elementos.
        </td>
      </tr>"""
    title_color = "#1f2937" if not subdued else "#475467"
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:0 0 20px 0;">
      <tr>
        <td style="padding:0 0 10px 0;">
          <p style="margin:0; color:{title_color}; font-size:13px; font-weight:900; letter-spacing:0; text-transform:uppercase;">{html.escape(title)}</p>
        </td>
      </tr>
      {rows}
    </table>"""


def build_operational_email_subject(*, current: datetime | None = None) -> str:
    day = (current or datetime.now()).date().isoformat()
    return f"Agenda Llangón - resumen operativo {day}"


def _unique_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    unique = []
    for event in events:
        key = str(event.get("id") or f"{event.get('source_type')}:{event.get('source_id')}:{event.get('datetime')}")
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def build_operational_email_payload(
    today_response: dict[str, object],
    week_response: dict[str, object],
) -> dict[str, object]:
    today_groups = today_response.get("groups") or {}
    today_events = _unique_events([
        *(today_groups.get("overdue") or []),
        *(today_groups.get("day") or []),
    ])
    today_ids = {str(event.get("id")) for event in today_events}
    week_events = [
        event for event in _unique_events(week_response.get("events") or [])
        if str(event.get("id")) not in today_ids and not bool(event.get("is_overdue"))
    ]
    return {
        "active_date_label": today_response.get("active_date_label") or today_response.get("date"),
        "sections": [
            {
                "title": "Principal / Hoy",
                "items": today_events,
            },
            {
                "title": "Resto de la semana hasta domingo",
                "items": week_events,
            },
        ],
        "counts": {
            "today": len(today_events),
            "week_rest": len(week_events),
        },
    }


def build_operational_email_text(payload: dict[str, object]) -> str:
    heading = clean_text(payload.get("heading")) or "Resumen operativo de Agenda"
    subtitle = clean_text(payload.get("subtitle")) or "Resumen operativo diario"
    lines = [
        heading,
        f"Agenda Llangón - {subtitle}",
        f"Fecha: {payload.get('active_date_label') or ''}",
        "",
    ]
    for section in payload.get("sections") or []:
        lines.append(str(section.get("title") or "Sección").upper())
        items = section.get("items") or []
        if not items:
            lines.append("- Sin elementos")
        for item in items[:16]:
            status = item.get("status") or ""
            source = item.get("source_type") or ""
            lines.append(
                f"- [{source}] Expediente: {_item_expediente(item)} | "
                f"Título: {_item_title(item)} | Estado: {status} | "
                f"Fecha/hora final: {_item_date(item)}"
            )
        lines.append("")
    lines.extend(
        [
            "Este es tu resumen operativo de Agenda.",
            "Consulta la aplicación para acceder al detalle completo.",
        ]
    )
    return "\n".join(lines).strip()


def build_operational_email_html(payload: dict[str, object], *, generated_at: object = "") -> str:
    date_label = html.escape(clean_text(payload.get("active_date_label")) or "Fecha no disponible")
    generated_label = html.escape(format_datetime_es(generated_at or datetime.now().replace(microsecond=0).isoformat()))
    sections = payload.get("sections") or []
    rendered_sections = [section for section in sections if isinstance(section, dict)] or [
        {"title": "Principal / Hoy", "items": []},
        {"title": "Resto de la semana hasta domingo", "items": []},
    ]
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    today_count = html.escape(str(counts.get("today", 0)))
    week_count = html.escape(str(counts.get("week_rest", 0)))
    heading = html.escape(clean_text(payload.get("heading")) or "Agenda Llangón")
    subtitle = html.escape(clean_text(payload.get("subtitle")) or "Resumen operativo diario")
    sections_html = "".join(
        _section_html(section, subdued=index > 0)
        for index, section in enumerate(rendered_sections)
    )
    body_html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-left:5px solid #2dad2c; background:#ffffff; border-collapse:collapse; margin:0 0 22px 0;">
      <tr>
        <td style="padding:0 0 0 18px;">
          <p style="margin:0 0 8px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">{subtitle}</p>
          <h2 style="margin:0 0 10px 0; color:#1f2937; font-size:20px; line-height:1.25;">{heading}</h2>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <td style="padding:0; color:#475467; font-size:13px; line-height:1.45;">Fecha: {date_label}</td>
              <td align="right" style="padding:0; color:#667085; font-size:13px; line-height:1.45;">Generado: {generated_label}</td>
            </tr>
          </table>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-top:14px;">
            <tr>
              <td style="padding:9px 12px; border:1px solid #d9e2ec; color:#1f2937; font-size:13px; font-weight:800;">Hoy: {today_count}</td>
              <td style="padding:9px 12px; border:1px solid #d9e2ec; color:#1f2937; font-size:13px; font-weight:800;">Semana: {week_count}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    {sections_html}"""
    return build_llangon_email_shell(
        eyebrow="Llangón Web App",
        title=heading,
        subtitle=subtitle,
        body_html=body_html,
        footer_left_html="Resumen operativo de Agenda",
        footer_right_html=generated_label,
        closing_html=(
            "Este es tu resumen operativo de Agenda.<br>"
            "Consulta la aplicación para acceder al detalle completo."
        ),
    )
