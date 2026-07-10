from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

try:
    from ..actuaciones import ACTUACION_ESTADOS_ABIERTOS
    from ..normalization import clean_text
    from .service import all_agenda_events, agenda_parse_date, sort_agenda_events
except ImportError:
    from actuaciones import ACTUACION_ESTADOS_ABIERTOS
    from normalization import clean_text
    from agenda.service import all_agenda_events, agenda_parse_date, sort_agenda_events


SECTION_TITLES = {
    "overdue": "Vencidos abiertos",
    "due_today": "Vencen hoy",
    "next_7_days": "Próximos 7 días",
    "without_date": "Sin fecha",
    "new_licitaciones": "Licitaciones nuevas sin revisar",
    "failed_downloads": "Descargas fallidas",
}
SECTION_ORDER = ["overdue", "due_today", "next_7_days", "without_date", "new_licitaciones", "failed_downloads"]
DOWNLOAD_REVIEW_STATUSES = {"failed", "error", "partial", "in_progress", "pending_review", "needs_review"}


def _sanitize(event: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in event.items() if not key.startswith("_")}


def _licitacion_item(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "expediente": row["expediente"] or "",
        "objeto": row["objeto"] or "",
        "organismo": row["organismo"] or "",
        "estado": row["estado"] or "",
        "fecha_limite": row["fecha_limite"] or "",
        "hora_limite": row["hora_limite"] or "",
        "source_type": "licitacion",
    }


def new_licitaciones_items(conn: sqlite3.Connection, *, limit: int = 20) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, expediente, objeto, organismo, estado, fecha_limite, hora_limite
        FROM licitaciones
        WHERE estado = 'Importada'
          AND COALESCE(tipo_publicacion, 'licitacion') = 'licitacion'
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_licitacion_item(row) for row in rows]


def failed_download_items(conn: sqlite3.Connection, *, limit: int = 20) -> list[dict[str, object]]:
    statuses = sorted(DOWNLOAD_REVIEW_STATUSES)
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"""
        SELECT l.id, l.expediente, l.objeto, l.organismo, l.estado, l.fecha_limite, l.hora_limite,
               dj.status AS download_status, dj.error_message, dj.updated_at AS download_updated_at
        FROM download_jobs dj
        JOIN (
            SELECT licitacion_id, MAX(id) AS latest_id
            FROM download_jobs
            GROUP BY licitacion_id
        ) latest ON latest.latest_id = dj.id
        JOIN licitaciones l ON l.id = dj.licitacion_id
        WHERE LOWER(COALESCE(dj.status, '')) IN ({placeholders})
        ORDER BY dj.updated_at DESC, dj.id DESC
        LIMIT ?
        """,
        [*statuses, limit],
    ).fetchall()
    items = []
    for row in rows:
        item = _licitacion_item(row)
        item.update(
            {
                "download_status": row["download_status"] or "",
                "error_message": row["error_message"] or "",
                "download_updated_at": row["download_updated_at"] or "",
            }
        )
        items.append(item)
    return items


def actuaciones_by_licitacion(conn: sqlite3.Connection, *, current: datetime, limit: int = 12) -> list[dict[str, object]]:
    placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
    rows = conn.execute(
        f"""
        SELECT l.id, l.expediente, l.objeto, l.organismo,
               COUNT(DISTINCT a.id) AS abiertas,
               SUM(CASE WHEN a.deadline_at IS NOT NULL AND a.deadline_at <> '' AND a.deadline_at < ? THEN 1 ELSE 0 END) AS vencidas,
               SUM(CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END) AS sin_fecha,
               MIN(CASE WHEN a.deadline_at IS NOT NULL AND a.deadline_at <> '' AND a.deadline_at >= ? THEN a.deadline_at ELSE NULL END) AS proxima_fecha
        FROM licitaciones l
        JOIN actuacion_licitaciones al ON al.licitacion_id = l.id
        JOIN actuaciones a ON a.id = al.actuacion_id
        WHERE a.estado IN ({placeholders})
        GROUP BY l.id
        ORDER BY vencidas DESC, abiertas DESC, proxima_fecha ASC, l.id DESC
        LIMIT ?
        """,
        [current.isoformat(), current.isoformat(), *sorted(ACTUACION_ESTADOS_ABIERTOS), limit],
    ).fetchall()
    return [
        {
            "licitacion_id": row["id"],
            "expediente": row["expediente"] or "",
            "objeto": row["objeto"] or "",
            "organismo": row["organismo"] or "",
            "open_count": int(row["abiertas"] or 0),
            "overdue_count": int(row["vencidas"] or 0),
            "without_date_count": int(row["sin_fecha"] or 0),
            "next_deadline_at": row["proxima_fecha"] or "",
        }
        for row in rows
    ]


def build_agenda_workbench(conn: sqlite3.Connection, *, current: datetime | None = None) -> dict[str, object]:
    current_dt = current or datetime.now().replace(microsecond=0)
    today = current_dt.date()
    next_limit = today + timedelta(days=7)
    events = all_agenda_events(conn, current=current_dt)
    ordered = sort_agenda_events(events, target_date=today, current=current_dt)

    overdue = [event for event in ordered if event.get("is_overdue")]
    due_today = []
    next_7_days = []
    without_date = []
    for event in ordered:
        event_date_text = clean_text(event.get("date"))
        if not event_date_text:
            without_date.append(event)
            continue
        event_date = agenda_parse_date(event_date_text, fallback=today)
        if event.get("is_overdue"):
            continue
        if event_date == today:
            due_today.append(event)
        elif today < event_date <= next_limit:
            next_7_days.append(event)

    new_items = new_licitaciones_items(conn)
    failed_items = failed_download_items(conn)
    section_items = {
        "overdue": [_sanitize(event) for event in overdue],
        "due_today": [_sanitize(event) for event in due_today],
        "next_7_days": [_sanitize(event) for event in next_7_days],
        "without_date": [_sanitize(event) for event in without_date],
        "new_licitaciones": new_items,
        "failed_downloads": failed_items,
    }
    summary = {
        "overdue_count": len(overdue),
        "due_today_count": len(due_today),
        "next_7_days_count": len(next_7_days),
        "without_date_count": len(without_date),
        "new_licitaciones_count": len(new_items),
        "failed_downloads_count": len(failed_items),
        "open_actuaciones_count": sum(1 for event in events if event.get("source_type") == "actuacion"),
    }
    return {
        "ok": True,
        "generated_at": current_dt.isoformat(),
        "summary": summary,
        "sections": [
            {
                "key": key,
                "title": SECTION_TITLES[key],
                "count": len(section_items[key]),
                "items": section_items[key],
            }
            for key in SECTION_ORDER
        ],
        "actuaciones_by_licitacion": actuaciones_by_licitacion(conn, current=current_dt),
    }
