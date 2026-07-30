from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta

try:
    from ..actuaciones import ACTUACION_ESTADOS_ABIERTOS
    from ..licitacion_states import is_agenda_licitacion_estado
    from ..normalization import clean_text
except ImportError:
    from actuaciones import ACTUACION_ESTADOS_ABIERTOS
    from licitacion_states import is_agenda_licitacion_estado
    from normalization import clean_text


AGENDA_EVENTOS_ESTADOS_ABIERTOS = {"pendiente", "en_curso", "preparado", "preparada"}
AGENDA_EVENTOS_ESTADOS_CERRADOS = {"cerrado", "cerrada", "enviado", "enviada", "cancelado", "cancelada"}
AGENDA_EVENTOS_ESTADOS = AGENDA_EVENTOS_ESTADOS_ABIERTOS | AGENDA_EVENTOS_ESTADOS_CERRADOS
AGENDA_TYPE_FILTERS = {"all", "actuacion", "licitacion", "interno", "vencido", "sin_fecha"}
AGENDA_VIEWS = {"day", "today", "week", "month", "all"}
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def agenda_parse_date(value: object, *, fallback: date | None = None) -> date:
    text = clean_text(value)
    if not text:
        return fallback or date.today()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return fallback or date.today()


def agenda_parse_datetime(value: object) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def agenda_datetime_from_date_time(day_value: object, time_value: object = "") -> datetime | None:
    day = clean_text(day_value)
    if not day:
        return None
    hour = clean_text(time_value) or "23:59"
    if len(hour) == 5:
        hour = f"{hour}:00"
    return agenda_parse_datetime(f"{day}T{hour}")


def agenda_week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def active_date_label(target_date: date, *, current: date) -> str:
    weekday = WEEKDAYS[target_date.weekday()]
    if target_date == current:
        return f"Hoy, {weekday} {target_date.day}"
    return f"{weekday.capitalize()} {target_date.day} {MONTHS[target_date.month - 1]}"


def _actuaciones_select_sql(where: list[str] | None = None) -> str:
    sql = """
        SELECT a.*,
               (
                   SELECT COUNT(*)
                   FROM actuacion_licitaciones al_count
                   WHERE al_count.actuacion_id = a.id
               ) AS licitaciones_count
        FROM actuaciones a
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END ASC, a.deadline_at ASC, a.id DESC"
    return sql


def _licitacion_selection_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "expediente": row["expediente"] or "",
        "organismo": row["organismo"] or "",
        "objeto": row["objeto"] or "",
        "tipo": row["tipo"] or "",
        "presupuesto": row["presupuesto"],
        "fecha_limite": row["fecha_limite"] or "",
        "hora_limite": row["hora_limite"] or "",
        "estado": row["estado"] or "",
        "provincia": row["provincia"] or "",
        "plataforma": row["plataforma"] or "",
        "enlace_perfil": row["enlace_perfil"] or "",
        "enlace_infonalia": row["enlace_infonalia"] or "",
        "ruta_carpeta": row["ruta_carpeta"] or "",
    }


def _actuacion_licitaciones(conn: sqlite3.Connection, actuacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT l.id, l.expediente, l.organismo, l.objeto, l.tipo, l.presupuesto,
               l.fecha_limite, l.hora_limite, l.estado, l.provincia, l.plataforma,
               l.enlace_perfil, l.enlace_infonalia, l.ruta_carpeta
        FROM actuacion_licitaciones al
        JOIN licitaciones l ON l.id = al.licitacion_id
        WHERE al.actuacion_id = ?
        ORDER BY l.expediente ASC, l.id ASC
        """,
        (actuacion_id,),
    ).fetchall()
    return [_licitacion_selection_dict(row) for row in rows]


def agenda_is_open_licitacion_estado(estado: object) -> bool:
    return is_agenda_licitacion_estado(estado)


def agenda_date_warnings(value: object, *, current: datetime | None = None, required: bool = False) -> list[str]:
    text = clean_text(value)
    if not text:
        return ["sin_fecha"] if not required else ["fecha_obligatoria"]
    parsed = agenda_parse_datetime(text)
    if not parsed:
        return ["fecha_invalida"]
    warnings: list[str] = []
    if "T" not in text and " " not in text:
        warnings.append("hora_vacia")
    if parsed < (current or datetime.now()).replace(microsecond=0):
        warnings.append("fecha_pasada")
    return warnings


def agenda_color(source_type: str, event_dt: datetime | None, *, current: datetime) -> tuple[bool, str]:
    is_overdue = bool(event_dt and event_dt < current)
    return is_overdue, "vencido" if is_overdue else source_type


def agenda_base_event(
    *,
    source_type: str,
    source_id: int,
    title: str,
    subtitle: str,
    status: str,
    event_dt: datetime | None,
    current: datetime,
    linked_licitaciones: list[dict[str, object]] | None = None,
    search_extra: list[object] | None = None,
) -> dict[str, object]:
    is_overdue, color_type = agenda_color(source_type, event_dt, current=current)
    today = current.date()
    event_date = event_dt.date().isoformat() if event_dt else ""
    return {
        "id": f"{source_type}:{source_id}",
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "subtitle": subtitle,
        "date": event_date,
        "datetime": event_dt.replace(microsecond=0).isoformat() if event_dt else "",
        "status": status,
        "is_overdue": is_overdue,
        "is_today": bool(event_dt and event_dt.date() == today),
        "is_open": True,
        "color_type": color_type,
        "linked_licitaciones": linked_licitaciones or [],
        "origin_url": f"{source_type}:{source_id}",
        "date_warnings": agenda_date_warnings(event_dt.isoformat() if event_dt else "", current=current),
        "_search": " ".join(clean_text(value) for value in (search_extra or []) if clean_text(value)),
    }


def agenda_actuacion_events(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
    rows = conn.execute(
        _actuaciones_select_sql([f"a.estado IN ({placeholders})"]),
        sorted(ACTUACION_ESTADOS_ABIERTOS),
    ).fetchall()
    events = []
    for row in rows:
        linked = _actuacion_licitaciones(conn, int(row["id"]))
        event_dt = agenda_parse_datetime(row["deadline_at"])
        events.append(
            agenda_base_event(
                source_type="actuacion",
                source_id=int(row["id"]),
                title=row["titulo"],
                subtitle=row["descripcion"] or "Actuación sin descripción",
                status=row["estado"],
                event_dt=event_dt,
                current=current,
                linked_licitaciones=linked,
                search_extra=[
                    row["tipo"],
                    row["origen"],
                    *[
                        " ".join(
                            clean_text(licitacion.get(key))
                            for key in ("expediente", "organismo", "objeto", "plataforma", "provincia")
                        )
                        for licitacion in linked
                    ],
                ],
            )
        )
    return events


def agenda_licitacion_events(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, expediente, objeto, organismo, tipo, presupuesto, fecha_limite, hora_limite,
               estado, provincia, plataforma, enlace_perfil, enlace_infonalia, ruta_carpeta
        FROM licitaciones
        WHERE fecha_limite IS NOT NULL
          AND fecha_limite <> ''
          AND COALESCE(tipo_publicacion, 'licitacion') = 'licitacion'
        ORDER BY fecha_limite ASC, hora_limite ASC, id ASC
        """
    ).fetchall()
    events = []
    for row in rows:
        if not agenda_is_open_licitacion_estado(row["estado"]):
            continue
        event_dt = agenda_datetime_from_date_time(row["fecha_limite"], row["hora_limite"])
        linked = [_licitacion_selection_dict(row)]
        events.append(
            agenda_base_event(
                source_type="licitacion",
                source_id=int(row["id"]),
                title=row["expediente"] or f"Licitación {row['id']}",
                subtitle=row["objeto"] or row["organismo"] or "Licitación sin detalle",
                status=row["estado"],
                event_dt=event_dt,
                current=current,
                linked_licitaciones=linked,
                search_extra=[row["organismo"], row["objeto"], row["plataforma"], row["provincia"]],
            )
        )
    return events


def agenda_interno_events(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, titulo, descripcion, starts_at, estado
        FROM agenda_eventos
        WHERE estado IN ('pendiente', 'en_curso', 'preparado', 'preparada')
        ORDER BY starts_at ASC, id ASC
        """
    ).fetchall()
    return [
        agenda_base_event(
            source_type="interno",
            source_id=int(row["id"]),
            title=row["titulo"],
            subtitle=row["descripcion"] or "Evento interno",
            status=row["estado"],
            event_dt=agenda_parse_datetime(row["starts_at"]),
            current=current,
            search_extra=[row["estado"]],
        )
        for row in rows
    ]


def all_agenda_events(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    return [
        *agenda_actuacion_events(conn, current=current),
        *agenda_licitacion_events(conn, current=current),
        *agenda_interno_events(conn, current=current),
    ]


def event_matches_search(event: dict[str, object], query: str) -> bool:
    q = query.lower().strip()
    if not q:
        return True
    values = [
        event.get("title"),
        event.get("subtitle"),
        event.get("status"),
        event.get("source_type"),
        event.get("_search"),
    ]
    for licitacion in event.get("linked_licitaciones") or []:
        values.extend(
            licitacion.get(key)
            for key in ("expediente", "organismo", "objeto", "plataforma", "provincia", "estado")
        )
    return any(q in clean_text(value).lower() for value in values)


def event_matches_type(event: dict[str, object], type_filter: str) -> bool:
    if type_filter == "all":
        return True
    if type_filter == "vencido":
        return bool(event.get("is_overdue"))
    if type_filter == "sin_fecha":
        return not clean_text(event.get("date"))
    return event.get("source_type") == type_filter


def agenda_event_in_view(
    event: dict[str, object],
    *,
    view: str,
    target_date: date,
    include_overdue: bool,
    type_filter: str,
) -> bool:
    event_date_text = clean_text(event.get("date"))
    if not event_date_text:
        return view in {"day", "all"} or (type_filter == "sin_fecha" and view != "month")
    event_date = agenda_parse_date(event_date_text, fallback=target_date)
    if bool(event.get("is_overdue")) and include_overdue:
        return True
    if view == "day":
        return event_date == target_date
    if view == "week":
        start, end = agenda_week_bounds(target_date)
        return start <= event_date <= end
    if view == "month":
        return event_date.year == target_date.year and event_date.month == target_date.month
    if view == "all":
        return True
    return False


def sort_agenda_events(events: list[dict[str, object]], *, target_date: date, current: datetime) -> list[dict[str, object]]:
    today = current.date()

    def key(event: dict[str, object]) -> tuple[object, ...]:
        event_date_text = clean_text(event.get("date"))
        event_date = agenda_parse_date(event_date_text, fallback=target_date) if event_date_text else None
        if event.get("is_overdue"):
            bucket = 0
        elif event_date == target_date:
            bucket = 1
        elif event_date == today:
            bucket = 2
        elif event_date:
            bucket = 3
        else:
            bucket = 4
        return (
            bucket,
            event.get("datetime") or ("9999-12-31T23:59:59" if not event_date else f"{event_date}T23:59:59"),
            clean_text(event.get("title")).lower(),
        )

    return sorted(events, key=key)


def agenda_summary(events: list[dict[str, object]], *, target_date: date) -> dict[str, int]:
    start, end = agenda_week_bounds(target_date)
    summary = {
        "overdue": 0,
        "active_date": 0,
        "today": 0,
        "week": 0,
        "no_date": 0,
        "total_open": len(events),
        "actuaciones": 0,
        "licitaciones": 0,
        "internos": 0,
    }
    real_today = date.today()
    for event in events:
        source = clean_text(event.get("source_type"))
        if source == "actuacion":
            summary["actuaciones"] += 1
        elif source == "licitacion":
            summary["licitaciones"] += 1
        elif source == "interno":
            summary["internos"] += 1
        if event.get("is_overdue"):
            summary["overdue"] += 1
        event_date_text = clean_text(event.get("date"))
        if not event_date_text:
            summary["no_date"] += 1
            continue
        event_date = agenda_parse_date(event_date_text, fallback=target_date)
        if event_date == target_date:
            summary["active_date"] += 1
        if event_date == real_today:
            summary["today"] += 1
        if start <= event_date <= end:
            summary["week"] += 1
    return summary


def agenda_groups(events: list[dict[str, object]], *, target_date: date, current: datetime) -> dict[str, list[dict[str, object]]]:
    today = current.date()
    return {
        "overdue": sort_agenda_events([event for event in events if event.get("is_overdue")], target_date=target_date, current=current),
        "day": sort_agenda_events(
            [
                event for event in events
                if clean_text(event.get("date")) and agenda_parse_date(event.get("date"), fallback=target_date) == target_date and not event.get("is_overdue")
            ],
            target_date=target_date,
            current=current,
        ),
        "today": sort_agenda_events(
            [
                event for event in events
                if target_date != today
                and clean_text(event.get("date"))
                and agenda_parse_date(event.get("date"), fallback=target_date) == today
                and not event.get("is_overdue")
            ],
            target_date=target_date,
            current=current,
        ),
        "upcoming": sort_agenda_events(
            [
                event for event in events
                if clean_text(event.get("date"))
                and not event.get("is_overdue")
                and agenda_parse_date(event.get("date"), fallback=target_date) not in {target_date, today}
            ],
            target_date=target_date,
            current=current,
        ),
        "no_date": sort_agenda_events([event for event in events if not clean_text(event.get("date"))], target_date=target_date, current=current),
    }


def sanitize_event(event: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in event.items() if not key.startswith("_")}


def normalized_view(value: object) -> str:
    view = clean_text(value).lower() or "day"
    if view == "today":
        return "day"
    return view if view in AGENDA_VIEWS else "day"


def _first_param(params: Mapping[str, object], key: str, default: str = "") -> object:
    value = params.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def build_agenda_events(
    conn: sqlite3.Connection,
    *,
    view: str,
    target_date: date,
    type_filter: str = "all",
    include_overdue: bool = True,
    query: str = "",
    current: datetime | None = None,
) -> list[dict[str, object]]:
    current_dt = current or datetime.now().replace(microsecond=0)
    view = normalized_view(view)
    type_filter = type_filter if type_filter in AGENDA_TYPE_FILTERS else "all"
    events = [
        event for event in all_agenda_events(conn, current=current_dt)
        if event_matches_type(event, type_filter) and event_matches_search(event, query)
    ]
    filtered = [
        event for event in events
        if agenda_event_in_view(
            event,
            view=view,
            target_date=target_date,
            include_overdue=include_overdue,
            type_filter=type_filter,
        )
    ]
    return [sanitize_event(event) for event in sort_agenda_events(filtered, target_date=target_date, current=current_dt)]


def build_agenda_response(
    conn: sqlite3.Connection,
    *,
    params: Mapping[str, object],
    current: datetime | None = None,
) -> dict[str, object]:
    current_dt = current or datetime.now().replace(microsecond=0)
    view = normalized_view(_first_param(params, "view", "day"))
    target_date = agenda_parse_date(_first_param(params, "date", ""), fallback=current_dt.date())
    type_filter = clean_text(_first_param(params, "type", "all")).lower()
    if type_filter not in AGENDA_TYPE_FILTERS:
        type_filter = "all"
    query = clean_text(_first_param(params, "q", ""))
    include_overdue = clean_text(_first_param(params, "include_overdue", "")) == "1" or view in {"day", "week", "all"}
    base_events = [
        event for event in all_agenda_events(conn, current=current_dt)
        if event_matches_type(event, type_filter) and event_matches_search(event, query)
    ]
    visible_events = [
        event for event in base_events
        if agenda_event_in_view(
            event,
            view=view,
            target_date=target_date,
            include_overdue=include_overdue,
            type_filter=type_filter,
        )
    ]
    ordered = sort_agenda_events(visible_events, target_date=target_date, current=current_dt)
    groups = agenda_groups(ordered, target_date=target_date, current=current_dt)
    return {
        "ok": True,
        "view": view,
        "date": target_date.isoformat(),
        "active_date_label": active_date_label(target_date, current=current_dt.date()),
        "is_today": target_date == current_dt.date(),
        "events": [sanitize_event(event) for event in ordered],
        "groups": {
            key: [sanitize_event(event) for event in value]
            for key, value in groups.items()
        },
        "summary": agenda_summary(base_events, target_date=target_date),
    }


def agenda_event_payload(
    data: dict[str, object],
    *,
    partial: bool = False,
    existing: sqlite3.Row | None = None,
    now: Callable[[], str] | None = None,
) -> dict[str, object]:
    current_timestamp = now or (lambda: datetime.now().replace(microsecond=0).isoformat())
    payload: dict[str, object] = {}
    if not partial or "titulo" in data:
        titulo = clean_text(data.get("titulo"))
        if not titulo:
            raise ValueError("El título del evento es obligatorio.")
        payload["titulo"] = titulo
    if not partial or "descripcion" in data:
        payload["descripcion"] = clean_text(data.get("descripcion"))
    if not partial or "starts_at" in data:
        parsed_starts = agenda_parse_datetime(data.get("starts_at"))
        if not parsed_starts:
            raise ValueError("La fecha y hora del evento es obligatoria.")
        payload["starts_at"] = parsed_starts.replace(second=0, microsecond=0).isoformat()
    if not partial or "estado" in data:
        estado = clean_text(data.get("estado")).lower() or "pendiente"
        payload["estado"] = estado if estado in AGENDA_EVENTOS_ESTADOS else "pendiente"
    estado = clean_text(payload.get("estado", existing["estado"] if existing else "pendiente")).lower()
    if estado in AGENDA_EVENTOS_ESTADOS_ABIERTOS:
        payload["closed_at"] = None
        payload["closed_by"] = None
    elif estado in AGENDA_EVENTOS_ESTADOS_CERRADOS and existing and not existing["closed_at"]:
        payload["closed_at"] = current_timestamp()
    payload["updated_at"] = current_timestamp()
    return payload


def agenda_evento_to_dict(row: sqlite3.Row, *, current: datetime | None = None) -> dict[str, object]:
    return {
        "id": row["id"],
        "titulo": row["titulo"],
        "descripcion": row["descripcion"] or "",
        "starts_at": row["starts_at"],
        "estado": row["estado"],
        "created_by": row["created_by"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "closed_at": row["closed_at"] or "",
        "closed_by": row["closed_by"] or "",
        "date_warnings": agenda_date_warnings(row["starts_at"], current=current),
    }


def create_agenda_evento(
    conn: sqlite3.Connection,
    data: dict[str, object],
    *,
    username: str,
    timestamp: str,
) -> dict[str, object]:
    payload = agenda_event_payload(data, now=lambda: timestamp)
    payload.update({"created_by": username, "created_at": timestamp, "updated_at": timestamp})
    if payload.get("estado") in AGENDA_EVENTOS_ESTADOS_CERRADOS:
        payload["closed_at"] = timestamp
        payload["closed_by"] = username
    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    cur = conn.execute(
        f"INSERT INTO agenda_eventos ({columns}) VALUES ({placeholders})",
        list(payload.values()),
    )
    row = conn.execute("SELECT * FROM agenda_eventos WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return agenda_evento_to_dict(row)


def update_agenda_evento(
    conn: sqlite3.Connection,
    evento_id: int,
    data: dict[str, object],
    *,
    username: str,
    timestamp: str,
) -> dict[str, object] | None:
    existing = conn.execute("SELECT * FROM agenda_eventos WHERE id = ?", (evento_id,)).fetchone()
    if not existing:
        return None
    payload = agenda_event_payload(data, partial=True, existing=existing, now=lambda: timestamp)
    if payload.get("estado") in AGENDA_EVENTOS_ESTADOS_CERRADOS and not payload.get("closed_by"):
        payload["closed_by"] = username
    set_clause = ", ".join(f"{key} = ?" for key in payload)
    conn.execute(
        f"UPDATE agenda_eventos SET {set_clause} WHERE id = ?",
        list(payload.values()) + [evento_id],
    )
    row = conn.execute("SELECT * FROM agenda_eventos WHERE id = ?", (evento_id,)).fetchone()
    return agenda_evento_to_dict(row)


def set_agenda_evento_estado(
    conn: sqlite3.Connection,
    evento_id: int,
    estado: str,
    *,
    username: str,
    timestamp: str,
) -> dict[str, object] | None:
    if estado not in AGENDA_EVENTOS_ESTADOS_CERRADOS:
        raise ValueError("Estado no valido")
    existing = conn.execute("SELECT * FROM agenda_eventos WHERE id = ?", (evento_id,)).fetchone()
    if not existing:
        return None
    conn.execute(
        """
        UPDATE agenda_eventos
        SET estado = ?, closed_at = ?, closed_by = ?, updated_at = ?
        WHERE id = ?
        """,
        (estado, timestamp, username, timestamp, evento_id),
    )
    row = conn.execute("SELECT * FROM agenda_eventos WHERE id = ?", (evento_id,)).fetchone()
    return agenda_evento_to_dict(row)
