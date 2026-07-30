from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from typing import Any

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


SEVERITY_NORMAL = "normal"
SEVERITY_ATTENTION = "attention"
SEVERITY_CRITICAL = "critical"
SEVERITIES = {SEVERITY_NORMAL, SEVERITY_ATTENTION, SEVERITY_CRITICAL}

CATEGORIES = {
    "import",
    "internal_review",
    "nuria_delivery",
    "nuria_action",
    "closure",
    "download_ai",
    "comment",
    "system",
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_infonalia_history_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS infonalia_activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_id INTEGER,
            licitacion_id INTEGER,
            day_date TEXT,
            day_title TEXT,
            expediente TEXT,
            organismo TEXT,
            category TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            actor TEXT,
            result TEXT,
            title TEXT NOT NULL,
            detail TEXT,
            old_value TEXT,
            new_value TEXT,
            severity TEXT NOT NULL DEFAULT 'normal',
            requires_review INTEGER NOT NULL DEFAULT 0,
            reviewed_at TEXT,
            reviewed_by TEXT,
            metadata_json TEXT,
            dedupe_key TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (day_id) REFERENCES infonalia_dias(id) ON DELETE SET NULL,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_infonalia_activity_dedupe "
        "ON infonalia_activity_events(dedupe_key) WHERE dedupe_key IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_activity_created "
        "ON infonalia_activity_events(created_at DESC, id DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_activity_day "
        "ON infonalia_activity_events(day_id, created_at DESC, id DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_activity_review "
        "ON infonalia_activity_events(requires_review, reviewed_at, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_infonalia_activity_category "
        "ON infonalia_activity_events(category, severity, created_at DESC)"
    )


def _snapshots(
    conn: sqlite3.Connection,
    *,
    day_id: int | None,
    licitacion_id: int | None,
) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "day_id": int(day_id or 0) or None,
        "licitacion_id": int(licitacion_id or 0) or None,
        "day_date": "",
        "day_title": "",
        "expediente": "",
        "organismo": "",
    }
    if snapshot["licitacion_id"]:
        row = conn.execute(
            "SELECT infonalia_dia_id, expediente, organismo FROM licitaciones WHERE id = ?",
            (snapshot["licitacion_id"],),
        ).fetchone()
        if row:
            if not snapshot["day_id"]:
                snapshot["day_id"] = int(row[0] or 0) or None
            snapshot["expediente"] = clean_text(row[1])
            snapshot["organismo"] = clean_text(row[2])
        else:
            snapshot["licitacion_id"] = None
    if snapshot["day_id"]:
        row = conn.execute(
            "SELECT fecha, titulo FROM infonalia_dias WHERE id = ?",
            (snapshot["day_id"],),
        ).fetchone()
        if row:
            snapshot["day_date"] = clean_text(row[0])
            snapshot["day_title"] = clean_text(row[1])
        else:
            snapshot["day_id"] = None
    return snapshot


def record_infonalia_activity(
    conn: sqlite3.Connection,
    *,
    category: str,
    event_type: str,
    source: str,
    title: str,
    day_id: int | None = None,
    licitacion_id: int | None = None,
    actor: str = "",
    result: str = "processed",
    detail: str = "",
    old_value: object = "",
    new_value: object = "",
    severity: str = SEVERITY_NORMAL,
    requires_review: bool | None = None,
    metadata: Mapping[str, object] | None = None,
    dedupe_key: str = "",
    timestamp: str | None = None,
) -> int | None:
    ensure_infonalia_history_schema(conn)
    normalized_category = clean_text(category).lower()
    if normalized_category not in CATEGORIES:
        normalized_category = "system"
    normalized_severity = clean_text(severity).lower()
    if normalized_severity not in SEVERITIES:
        normalized_severity = SEVERITY_NORMAL
    review_required = normalized_severity != SEVERITY_NORMAL if requires_review is None else bool(requires_review)
    snapshot = _snapshots(conn, day_id=day_id, licitacion_id=licitacion_id)
    normalized_dedupe = clean_text(dedupe_key) or None
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO infonalia_activity_events (
            day_id, licitacion_id, day_date, day_title, expediente, organismo,
            category, event_type, source, actor, result, title, detail,
            old_value, new_value, severity, requires_review, metadata_json,
            dedupe_key, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot["day_id"],
            snapshot["licitacion_id"],
            snapshot["day_date"],
            snapshot["day_title"],
            snapshot["expediente"],
            snapshot["organismo"],
            normalized_category,
            clean_text(event_type) or "event",
            clean_text(source) or "system",
            clean_text(actor),
            clean_text(result),
            clean_text(title) or "Actividad Infonalia",
            clean_text(detail),
            clean_text(old_value),
            clean_text(new_value),
            normalized_severity,
            1 if review_required else 0,
            json.dumps(dict(metadata or {}), ensure_ascii=False) if metadata else "",
            normalized_dedupe,
            timestamp or now_iso(),
        ),
    )
    return int(cur.lastrowid) if cur.rowcount else None


def _history_where(filters: Mapping[str, object], *, include_cursor: bool) -> tuple[list[str], list[object]]:
    where: list[str] = []
    values: list[object] = []
    day_id = clean_text(filters.get("day_id"))
    if day_id.isdigit():
        where.append("day_id = ?")
        values.append(int(day_id))
    for key, column, allowed in (
        ("category", "category", CATEGORIES),
        ("severity", "severity", SEVERITIES),
    ):
        value = clean_text(filters.get(key)).lower()
        if value in allowed:
            where.append(f"{column} = ?")
            values.append(value)
    result = clean_text(filters.get("result"))
    if result:
        where.append("result = ?")
        values.append(result)
    for key in ("source", "actor"):
        value = clean_text(filters.get(key))
        if value:
            where.append(f"{key} LIKE ?")
            values.append(f"%{value}%")
    review_state = clean_text(filters.get("review_state")).lower()
    if review_state == "pending":
        where.append("requires_review = 1 AND COALESCE(reviewed_at, '') = ''")
    elif review_state == "reviewed":
        where.append("requires_review = 1 AND COALESCE(reviewed_at, '') <> ''")
    elif review_state == "normal":
        where.append("requires_review = 0")
    date_from = clean_text(filters.get("date_from"))
    if date_from:
        where.append("created_at >= ?")
        values.append(f"{date_from}T00:00:00" if len(date_from) == 10 else date_from)
    date_to = clean_text(filters.get("date_to"))
    if date_to:
        where.append("created_at <= ?")
        values.append(f"{date_to}T23:59:59" if len(date_to) == 10 else date_to)
    query = clean_text(filters.get("q"))
    if query:
        like = f"%{query}%"
        where.append(
            "(expediente LIKE ? OR organismo LIKE ? OR title LIKE ? OR detail LIKE ? "
            "OR actor LIKE ? OR day_title LIKE ?)"
        )
        values.extend([like] * 6)
    if include_cursor:
        cursor = clean_text(filters.get("cursor"))
        if "|" in cursor:
            cursor_date, cursor_id = cursor.rsplit("|", 1)
            if cursor_date and cursor_id.isdigit():
                where.append("(created_at < ? OR (created_at = ? AND id < ?))")
                values.extend([cursor_date, cursor_date, int(cursor_id)])
    return where, values


def _event_to_dict(row: sqlite3.Row) -> dict[str, object]:
    item = {key: row[key] for key in row.keys()}
    try:
        item["metadata"] = json.loads(clean_text(item.pop("metadata_json")) or "{}")
    except (TypeError, ValueError):
        item["metadata"] = {}
    item["requires_review"] = bool(item.get("requires_review"))
    item["is_reviewed"] = bool(clean_text(item.get("reviewed_at")))
    item["day_exists"] = bool(item.get("day_exists"))
    item["licitacion_exists"] = bool(item.get("licitacion_exists"))
    return item


def list_infonalia_history(
    conn: sqlite3.Connection,
    *,
    filters: Mapping[str, object] | None = None,
    limit: int = 50,
) -> dict[str, object]:
    ensure_infonalia_history_schema(conn)
    active_filters = filters or {}
    page_size = max(1, min(int(limit or 50), 100))
    where, values = _history_where(active_filters, include_cursor=True)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        """
        SELECT e.*,
               EXISTS(SELECT 1 FROM infonalia_dias d WHERE d.id = e.day_id) AS day_exists,
               EXISTS(SELECT 1 FROM licitaciones l WHERE l.id = e.licitacion_id) AS licitacion_exists
        FROM infonalia_activity_events e
        """
        + where_sql
        + " ORDER BY e.created_at DESC, e.id DESC LIMIT ?",
        [*values, page_size + 1],
    ).fetchall()
    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    items = [_event_to_dict(row) for row in page_rows]
    next_cursor = ""
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = f"{last['created_at']}|{last['id']}"

    summary_where, summary_values = _history_where(active_filters, include_cursor=False)
    summary_where_sql = f" WHERE {' AND '.join(summary_where)}" if summary_where else ""
    summary = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN requires_review = 1 AND COALESCE(reviewed_at, '') = '' THEN 1 ELSE 0 END) AS pending_review,
               SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical,
               SUM(CASE WHEN severity = 'attention' THEN 1 ELSE 0 END) AS attention
        FROM infonalia_activity_events
        """
        + summary_where_sql,
        summary_values,
    ).fetchone()
    return {
        "items": items,
        "next_cursor": next_cursor,
        "summary": {
            "total": int(summary[0] or 0),
            "pending_review": int(summary[1] or 0),
            "critical": int(summary[2] or 0),
            "attention": int(summary[3] or 0),
        },
    }


def acknowledge_infonalia_event(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    reviewed_by: str,
    timestamp: str | None = None,
) -> bool:
    ensure_infonalia_history_schema(conn)
    cur = conn.execute(
        """
        UPDATE infonalia_activity_events
        SET reviewed_at = ?, reviewed_by = ?
        WHERE id = ? AND requires_review = 1 AND COALESCE(reviewed_at, '') = ''
        """,
        (timestamp or now_iso(), clean_text(reviewed_by), int(event_id)),
    )
    return bool(cur.rowcount)


def acknowledge_filtered_infonalia_events(
    conn: sqlite3.Connection,
    *,
    filters: Mapping[str, object] | None,
    reviewed_by: str,
    timestamp: str | None = None,
) -> int:
    ensure_infonalia_history_schema(conn)
    where, values = _history_where(filters or {}, include_cursor=False)
    where.extend(["requires_review = 1", "COALESCE(reviewed_at, '') = ''"])
    cur = conn.execute(
        "UPDATE infonalia_activity_events SET reviewed_at = ?, reviewed_by = ? "
        f"WHERE {' AND '.join(where)}",
        [timestamp or now_iso(), clean_text(reviewed_by), *values],
    )
    return int(cur.rowcount or 0)
