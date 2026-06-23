from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from ..email_templates import build_llangon_email_shell
    from ..formatting import format_date_es, format_datetime_es
    from ..normalization import clean_text
except ImportError:
    from email_templates import build_llangon_email_shell
    from formatting import format_date_es, format_datetime_es
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

STATE_STYLES = {
    "preparada": {"color": "#067647", "background": "#ecfdf3", "border": "#abefc6"},
    "preparado": {"color": "#067647", "background": "#ecfdf3", "border": "#abefc6"},
    "pendiente": {"color": "#b54708", "background": "#fff7ed", "border": "#fed7aa"},
    "descargar para ver": {"color": "#175cd3", "background": "#eff8ff", "border": "#b2ddff"},
    "preparar ficha": {"color": "#b42318", "background": "#fef3f2", "border": "#fecdca"},
}

DEFAULT_STATE_STYLE = {"color": "#344054", "background": "#f8fafc", "border": "#d0d5dd"}

WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MADRID_TZ = ZoneInfo("Europe/Madrid")


def _event_line(event: dict[str, object]) -> str:
    date_text = event.get("datetime") or event.get("date") or "Sin fecha"
    linked = event.get("linked_licitaciones") or []
    linked_text = ""
    if linked:
        labels = [
            str(item.get("expediente") or item.get("organismo") or item.get("id") or "")
            for item in linked
        ]
        linked_text = f" | Asociado: {', '.join(label for label in labels if label)}"
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
            expediente = clean_text(linked_item.get("expediente"))
            if is_real_expediente(expediente):
                return expediente
    expediente = clean_text(item.get("expediente"))
    return expediente if is_real_expediente(expediente) else ""


def is_real_expediente(value: object) -> bool:
    expediente = clean_text(value)
    if not expediente:
        return False
    if expediente.isdigit():
        return False
    return bool(re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ/-]", expediente))


def email_day_section_title(day, *, current) -> str:
    weekday = WEEKDAY_NAMES[day.weekday()].upper()
    formatted = format_date_es(day.isoformat())
    if day == current:
        return f"HOY, {weekday} {formatted}"
    if day == current + timedelta(days=1):
        return f"MAÑANA, {weekday} {formatted}"
    return f"{weekday} {formatted}"


def local_email_reference(current: datetime | None = None) -> datetime:
    value = current or datetime.now(MADRID_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=MADRID_TZ)
    return value.astimezone(MADRID_TZ)


def pending_day_bucket(item_date: date | None, *, current: datetime | None = None) -> tuple[str, str]:
    today = local_email_reference(current).date()
    if item_date is None:
        return "sin_fecha", "SIN FECHA"
    weekday = WEEKDAY_NAMES[item_date.weekday()].upper()
    formatted = format_date_es(item_date.isoformat())
    if item_date < today:
        return "vencidos", "VENCIDOS"
    if item_date == today:
        return "hoy", f"HOY, {weekday} {formatted}"
    if item_date == today + timedelta(days=1):
        return "manana", f"MAÑANA, {weekday} {formatted}"
    return item_date.isoformat(), f"{weekday} {formatted}"


def _item_date_value(item: dict[str, object]) -> date | None:
    value = clean_text(item.get("date") or item.get("datetime") or item.get("deadline_at") or item.get("fecha_limite"))
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _pending_sort_key(item: dict[str, object]) -> tuple[object, ...]:
    return (
        item.get("datetime") or "9999-12-31T23:59:59",
        clean_text(item.get("expediente")).lower(),
        clean_text(item.get("title")).lower(),
    )


def _pending_sections(items: list[dict[str, object]], *, current: datetime) -> list[dict[str, object]]:
    today = current.date()
    week_limit = today + timedelta(days=7)
    grouped = {
        "today": {"title": "HOY", "items": []},
        "next_7_days": {"title": "PRÓXIMOS 7 DÍAS", "items": [], "group_by_date": True},
        "later": {"title": "PRÓXIMAMENTE", "items": [], "group_by_date": True},
    }
    for item in sorted(items, key=_pending_sort_key):
        item_day = _item_date_value(item)
        if item_day == today:
            grouped["today"]["items"].append(item)
        elif item_day is not None and today < item_day <= week_limit:
            grouped["next_7_days"]["items"].append(item)
        elif item_day is None or item_day > week_limit:
            grouped["later"]["items"].append(item)
        else:
            continue
    return [section for section in grouped.values() if section["items"]]


def _valid_profile_url(value: object) -> str:
    url = clean_text(value)
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return ""
    return url


def _item_profile_url(item: dict[str, object]) -> str:
    url = _valid_profile_url(item.get("enlace_perfil"))
    if url:
        return url
    linked = item.get("linked_licitaciones") or []
    if isinstance(linked, list):
        for linked_item in linked:
            if isinstance(linked_item, dict):
                url = _valid_profile_url(linked_item.get("enlace_perfil"))
                if url:
                    return url
    return ""


def build_pending_tasks_email_payload(
    pending_response: dict[str, object],
    *,
    current: datetime | None = None,
) -> dict[str, object]:
    reference = local_email_reference(current)
    items = [item for item in pending_response.get("items") or [] if isinstance(item, dict)]
    today = reference.date()
    counts = {
        "total": len(items),
        "overdue": sum(1 for item in items if (_item_date_value(item) is not None and _item_date_value(item) < today)),
        "today": sum(1 for item in items if _item_date_value(item) == today),
        "tomorrow": sum(1 for item in items if _item_date_value(item) == today + timedelta(days=1)),
        "no_date": sum(1 for item in items if _item_date_value(item) is None),
    }
    counts["upcoming"] = max(0, counts["total"] - counts["overdue"] - counts["today"] - counts["no_date"])
    sections = _pending_sections(items, current=reference)
    counts["next_7_days"] = sum(len(section["items"]) for section in sections if section["title"] == "PRÓXIMOS 7 DÍAS")
    counts["later"] = sum(len(section["items"]) for section in sections if section["title"] == "PRÓXIMAMENTE")
    return {
        "active_date_label": format_date_es(today.isoformat()),
        "heading": "Pendientes de Agenda",
        "subtitle": "Tareas pendientes",
        "sections": sections,
        "counts": counts,
        "is_pending_digest": True,
    }


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
                (_item_expediente(linked_item) if isinstance(linked_item, dict) else "")
                or linked_item.get("organismo")
            )
            if label:
                labels.append(label)
    return ", ".join(labels)


def _item_status_style(status: str) -> dict[str, str]:
    normalized = clean_text(status).lower()
    return STATE_STYLES.get(normalized, DEFAULT_STATE_STYLE)


def _item_type_label(item: dict[str, object], *, source_key: str) -> str:
    return clean_text(item.get("tipo")) or TYPE_STYLES[source_key]["label"]


def _item_row_html(item: dict[str, object], *, subdued: bool = False, pending_digest: bool = False) -> str:
    source_key = _item_source_key(item)
    style = TYPE_STYLES[source_key]
    title = html.escape(_item_title(item))
    date_label = html.escape(format_datetime_es(_item_date(item)))
    expediente = html.escape(_item_expediente(item))
    status_text = clean_text(item.get("status")) or "Sin estado"
    status = html.escape(status_text)
    status_style = _item_status_style(status_text)
    type_label = html.escape(_item_type_label(item, source_key=source_key))
    description = html.escape(_item_description(item))
    profile_url = html.escape(_item_profile_url(item))
    opacity_color = "#475467" if subdued else "#1f2937"
    due_badge_html = ""
    if pending_digest and _item_date_value(item) is not None:
        due_badge_html = (
            f"<span style='display:inline-block; padding:5px 9px; border:1px solid #b6d7a8; "
            f"background:#f0f9ec; color:#1f7a4d; border-radius:999px; font-size:12px; "
            f"font-weight:900; white-space:nowrap;'>Vence: {date_label}</span>"
        )
    description_html = (
        f"<p style='margin:6px 0 0 0; color:#475467; font-size:13px; line-height:1.35;'>{description}</p>"
        if description
        else ""
    )
    expediente_html = (
        f"<p style='margin:7px 0 0 0; color:#667085; font-size:12px; line-height:1.45;'>Expediente: {expediente}</p>"
        if expediente
        else ""
    )
    profile_link_html = (
        f"<p style='margin:10px 0 0 0; font-size:13px; line-height:1.35;'><a href='{profile_url}' style='color:#1f7a4d; font-weight:800; text-decoration:underline;'>Ver perfil del contratante</a></p>"
        if profile_url
        else ""
    )
    detail_cells = [
        f"<td style=\"padding:8px 10px; border:1px solid #d9e2ec; background:#f8fafc; color:#1f2937; font-size:13px; line-height:1.35;\"><strong>Estado:</strong> <span style=\"display:inline-block; padding:2px 7px; border:1px solid {status_style['border']}; background:{status_style['background']}; color:{status_style['color']}; border-radius:999px; font-weight:800;\">{status}</span></td>",
    ]
    if not pending_digest:
        detail_cells.append(
            f"<td style=\"padding:8px 10px; border:1px solid #d9e2ec; background:#f8fafc; color:#1f2937; font-size:13px; line-height:1.35;\"><strong>Fecha/hora final:</strong> {date_label}</td>"
        )
    detail_cells.append(
        f"<td style=\"padding:8px 10px; border:1px solid #d9e2ec; background:#f8fafc; color:#1f2937; font-size:13px; line-height:1.35;\"><strong>Tipo:</strong> {type_label}</td>"
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
                    <td align="right" style="vertical-align:top;">{due_badge_html}</td>
                  </tr>
                </table>
                <p style="margin:9px 0 0 0; color:{opacity_color}; font-size:15px; font-weight:800; line-height:1.35;">{title}</p>
                {description_html}
                {expediente_html}
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-top:9px;">
                  <tr>
                    {"".join(detail_cells)}
                  </tr>
                </table>
                {profile_link_html}
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _date_group_title(item_date: date | None) -> str:
    if item_date is None:
        return "SIN FECHA"
    weekday = WEEKDAY_NAMES[item_date.weekday()].upper()
    return f"{weekday} {format_date_es(item_date.isoformat())}"


def _items_grouped_by_date(items: list[dict[str, object]]) -> list[tuple[date | None, list[dict[str, object]]]]:
    groups: list[tuple[date | None, list[dict[str, object]]]] = []
    for item in sorted(items, key=_pending_sort_key):
        item_date = _item_date_value(item)
        if not groups or groups[-1][0] != item_date:
            groups.append((item_date, []))
        groups[-1][1].append(item)
    return groups


def _date_group_rows(items: list[dict[str, object]], *, pending_digest: bool) -> str:
    rows = []
    for item_date, group_items in _items_grouped_by_date(items):
        rows.append(f"""
      <tr>
        <td style="padding:2px 0 8px 0; color:#667085; font-size:12px; font-weight:900; text-transform:uppercase;">
          {html.escape(_date_group_title(item_date))}
        </td>
      </tr>""")
        rows.extend(_item_row_html(item, pending_digest=pending_digest, subdued=True) for item in group_items)
    return "".join(rows)


def _section_html(section: dict[str, object], *, subdued: bool = False, pending_digest: bool = False) -> str:
    title = clean_text(section.get("title") or "Sección").upper()
    items = section.get("items") or []
    if items:
        section_items = [item for item in items if isinstance(item, dict)]
        if pending_digest and bool(section.get("group_by_date")):
            rows = _date_group_rows(section_items, pending_digest=pending_digest)
        else:
            rows = "".join(_item_row_html(item, subdued=subdued, pending_digest=pending_digest) for item in section_items)
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
            "total_week": len(today_events) + len(week_events),
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
    is_pending = bool(payload.get("is_pending_digest"))
    for section in payload.get("sections") or []:
        lines.append(str(section.get("title") or "Sección").upper())
        items = section.get("items") or []
        if not items:
            lines.append("- Sin elementos")
        item_groups = (
            _items_grouped_by_date([item for item in items if isinstance(item, dict)])
            if is_pending and bool(section.get("group_by_date"))
            else [(None, [item for item in items if isinstance(item, dict)])]
        )
        for item_date, group_items in item_groups:
            if is_pending and bool(section.get("group_by_date")):
                lines.append(_date_group_title(item_date))
            for item in group_items:
                status = item.get("status") or ""
                source = item.get("source_type") or ""
                expediente = _item_expediente(item)
                expediente_text = f"Expediente: {expediente} | " if expediente else ""
                profile_url = _item_profile_url(item)
                link_text = f" | Ver perfil del contratante: {profile_url}" if profile_url else ""
                if is_pending:
                    due_text = f"Vence: {_item_date(item)} | " if _item_date_value(item) is not None else ""
                else:
                    due_text = f"Fecha/hora final: {_item_date(item)} | "
                lines.append(
                    f"- [{source}] {expediente_text}"
                    f"Título: {_item_title(item)} | Estado: {status} | "
                    f"{due_text}Tipo: {_item_type_label(item, source_key=_item_source_key(item))}"
                    f"{link_text}"
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
    is_pending = bool(payload.get("is_pending_digest"))
    rendered_sections = [section for section in sections if isinstance(section, dict)]
    if not rendered_sections and not is_pending:
        rendered_sections = [
            {"title": "Principal / Hoy", "items": []},
            {"title": "Resto de la semana hasta domingo", "items": []},
        ]
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    today_count = html.escape(str(counts.get("today", 0)))
    is_notice = isinstance(payload.get("notice"), dict)
    right_label = "Total aviso" if is_notice else "Total semana"
    right_count_value = counts.get("total_notice") if is_notice else counts.get("total_week")
    if is_pending:
        summary_cells = [
            ("Total pendientes", counts.get("total", 0)),
            ("Vencen hoy", counts.get("today", 0)),
            ("Próximos 7 días", counts.get("next_7_days", 0)),
            ("Próximamente", counts.get("later", 0)),
        ]
        if int(counts.get("no_date", 0) or 0):
            summary_cells.append(("Sin fecha", counts.get("no_date", 0)))
    else:
        if right_count_value is None:
            right_count_value = int(counts.get("today", 0) or 0) + int(counts.get("week_rest", 0) or 0)
        summary_cells = [("Vence hoy", today_count), (right_label, right_count_value)]
    heading = html.escape(clean_text(payload.get("heading")) or "Agenda Llangón")
    subtitle = html.escape(clean_text(payload.get("subtitle")) or "Resumen operativo diario")
    sections_html = "".join(
        _section_html(section, subdued=index > 0, pending_digest=is_pending)
        for index, section in enumerate(rendered_sections)
    )
    summary_html = "".join(
        f"<td style='padding:8px 10px; border:1px solid #d9e2ec; color:#1f2937; font-size:13px; font-weight:800;'>{html.escape(str(label))}: {html.escape(str(value))}</td>"
        for label, value in summary_cells
    )
    body_html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-left:5px solid #2dad2c; background:#ffffff; border-collapse:collapse; margin:0 0 16px 0;">
      <tr>
        <td style="padding:0 0 0 14px;">
          <p style="margin:0 0 5px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">{subtitle}</p>
          <h2 style="margin:0 0 7px 0; color:#1f2937; font-size:20px; line-height:1.25;">{heading}</h2>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <td style="padding:0; color:#475467; font-size:13px; line-height:1.45;">Fecha: {date_label}</td>
              <td align="right" style="padding:0; color:#667085; font-size:13px; line-height:1.45;">Generado: {generated_label}</td>
            </tr>
          </table>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-top:10px;">
            <tr>
              {summary_html}
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
        compact=is_pending,
    )
