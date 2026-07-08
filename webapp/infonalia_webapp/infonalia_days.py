from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from .licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARAR_FICHA,
        normalize_licitacion_estado,
    )
    from .formatting import format_date_es, format_datetime_es
    from .normalization import clean_text
except ImportError:
    from licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARAR_FICHA,
        normalize_licitacion_estado,
    )
    from formatting import format_date_es, format_datetime_es
    from normalization import clean_text


TimestampFactory = Callable[[], str]
REVIEWER_STATE_FALLBACKS = {
    ESTADO_DESCARTADA,
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
}


def row_has_key(row: Any, key: str) -> bool:
    try:
        return key in row.keys()
    except AttributeError:
        return isinstance(row, dict) and key in row


def row_value(row: Any, key: str, default: object = "") -> object:
    if row is None or not row_has_key(row, key):
        return default
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def table_exists(conn: Any, table_name: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table_name,),
        ).fetchone()
    except Exception:
        return False
    return bool(row)


def _max_timestamp(*values: object) -> str:
    timestamps = [clean_text(value) for value in values if clean_text(value)]
    return max(timestamps) if timestamps else ""


def _format_timestamp(value: object) -> str:
    text = clean_text(value)
    return format_datetime_es(text) if text else ""


def _load_user_roles(conn: Any) -> dict[str, str]:
    if not table_exists(conn, "usuarios"):
        return {}
    try:
        rows = conn.execute("SELECT username, role FROM usuarios").fetchall()
    except Exception:
        return {}
    roles: dict[str, str] = {}
    for row in rows:
        username = clean_text(row_value(row, "username")).lower()
        role = clean_text(row_value(row, "role")).lower()
        if username:
            roles[username] = role
    return roles


def _actor_kind(user_id: object, roles: dict[str, str]) -> str:
    username = clean_text(user_id).lower()
    if not username:
        return ""
    role = roles.get(username, "")
    if role in {"nuria", "reviewer", "revisor"}:
        return "reviewer"
    if "nuria" in username or "revisor" in username or "review" in username:
        return "reviewer"
    return "admin"


def _base_activity(licitacion_rows: list[Any]) -> dict[int, dict[str, object]]:
    return {
        int(row["id"]): {
            "admin": normalize_licitacion_estado(row["estado"]) != ESTADO_IMPORTADA,
            "reviewer": normalize_licitacion_estado(row["estado"]) in REVIEWER_STATE_FALLBACKS,
            "last_activity_at": clean_text(row_value(row, "updated_at")),
            "last_reviewer_at": "",
        }
        for row in licitacion_rows
    }


def _apply_history_activity(conn: Any, activity: dict[int, dict[str, object]], licitacion_ids: list[int]) -> None:
    if not activity or not licitacion_ids or not table_exists(conn, "licitacion_historial"):
        return
    placeholders = ", ".join("?" for _ in licitacion_ids)
    roles = _load_user_roles(conn)
    try:
        rows = conn.execute(
            f"""
            SELECT licitacion_id, event_type, old_value, new_value, user_id, created_at
            FROM licitacion_historial
            WHERE licitacion_id IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            licitacion_ids,
        ).fetchall()
    except Exception:
        return

    for row in rows:
        licitacion_id = int(row_value(row, "licitacion_id") or 0)
        current = activity.get(licitacion_id)
        if not current:
            continue
        actor = _actor_kind(row_value(row, "user_id"), roles)
        created_at = clean_text(row_value(row, "created_at"))
        current["last_activity_at"] = _max_timestamp(current.get("last_activity_at"), created_at)
        if actor == "reviewer":
            current["reviewer"] = True
            current["last_reviewer_at"] = _max_timestamp(current.get("last_reviewer_at"), created_at)
        elif actor == "admin":
            current["admin"] = True


def _apply_email_activity(conn: Any, activity: dict[int, dict[str, object]], licitacion_ids: list[int]) -> None:
    if not activity or not licitacion_ids or not table_exists(conn, "email_action_events"):
        return
    placeholders = ", ".join("?" for _ in licitacion_ids)
    try:
        rows = conn.execute(
            f"""
            SELECT licitacion_id, created_at, result
            FROM email_action_events
            WHERE licitacion_id IN ({placeholders})
              AND COALESCE(result, '') = 'processed'
            ORDER BY created_at ASC, id ASC
            """,
            licitacion_ids,
        ).fetchall()
    except Exception:
        return

    for row in rows:
        licitacion_id = int(row_value(row, "licitacion_id") or 0)
        current = activity.get(licitacion_id)
        if not current:
            continue
        created_at = clean_text(row_value(row, "created_at"))
        current["reviewer"] = True
        current["admin"] = True
        current["last_activity_at"] = _max_timestamp(current.get("last_activity_at"), created_at)
        current["last_reviewer_at"] = _max_timestamp(current.get("last_reviewer_at"), created_at)


def _licitacion_activity(conn: Any, licitacion_rows: list[Any]) -> dict[int, dict[str, object]]:
    activity = _base_activity(licitacion_rows)
    licitacion_ids = list(activity.keys())
    _apply_history_activity(conn, activity, licitacion_ids)
    _apply_email_activity(conn, activity, licitacion_ids)
    return activity


def _day_visual_state(
    row: Any,
    *,
    total: int,
    pendientes: int,
    pendientes_nuria: int,
    reviewer_managed: int,
) -> str:
    reviewed_at = clean_text(row_value(row, "reviewed_at"))
    sent_at = clean_text(row_value(row, "enviado_nuria_at"))
    if reviewed_at:
        return "Cerrado / revisado"
    if reviewer_managed > 0:
        return "Revisado por Nuria · pendiente de cerrar"
    if sent_at or pendientes_nuria > 0:
        return "Enviado a Nuria"
    if total == 0 or pendientes > 0:
        return "Abierto / pendiente de gestión"
    return "Abierto / pendiente de gestión"


def get_or_create_day(conn: Any, fecha_infonalia: str, *, now: TimestampFactory) -> int:
    fecha = clean_text(fecha_infonalia) or "sin-fecha"
    row = conn.execute("SELECT id FROM infonalia_dias WHERE fecha = ?", (fecha,)).fetchone()
    if row:
        return int(row["id"])

    timestamp = now()
    title_date = "sin fecha" if fecha == "sin-fecha" else format_date_es(fecha)
    cur = conn.execute(
        """
        INSERT INTO infonalia_dias (fecha, titulo, estado, created_at, updated_at)
        VALUES (?, ?, 'Importado', ?, ?)
        """,
        (fecha, f"Infonalia {title_date}", timestamp, timestamp),
    )
    return int(cur.lastrowid)


def is_nuria_update_pending(row: Any | None) -> bool:
    if not row:
        return False
    dirty_at = clean_text(row_value(row, "nuria_dirty_at"))
    sent_at = clean_text(row_value(row, "enviado_nuria_at"))
    return bool(dirty_at and (not sent_at or dirty_at >= sent_at))


def mark_day_nuria_dirty(conn: Any, dia_id: int, *, timestamp: str) -> None:
    conn.execute(
        "UPDATE infonalia_dias SET nuria_dirty_at = ?, updated_at = ? WHERE id = ?",
        (timestamp, timestamp, dia_id),
    )


def refresh_day_status(conn: Any, dia_id: int, *, timestamp: str) -> None:
    day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    rows = conn.execute(
        """
        SELECT estado, COUNT(*) AS total
        FROM licitaciones
        WHERE infonalia_dia_id = ?
        GROUP BY estado
        """,
        (dia_id,),
    ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        estado = normalize_licitacion_estado(row["estado"])
        counts[estado] = counts.get(estado, 0) + int(row["total"] or 0)
    total = sum(counts.values())
    pendientes = counts.get(ESTADO_IMPORTADA, 0)
    pendientes_nuria = counts.get(ESTADO_ENVIADA_NURIA, 0)
    decisiones_nuria = (
        counts.get(ESTADO_DESCARTADA, 0)
        + counts.get(ESTADO_DESCARGAR_PARA_VER, 0)
        + counts.get(ESTADO_PREPARAR_FICHA, 0)
    )
    enviado_nuria_at = clean_text(row_value(day, "enviado_nuria_at"))
    reviewed_at = clean_text(row_value(day, "reviewed_at"))
    nuria_pending_update = is_nuria_update_pending(day)

    if total == 0:
        estado = "Importado"
    elif pendientes > 0:
        estado = "En filtrado interno"
    elif reviewed_at and not nuria_pending_update:
        estado = "Completado"
    elif nuria_pending_update and enviado_nuria_at:
        estado = "Cambios pendientes para Nuria"
    elif not enviado_nuria_at and (pendientes_nuria > 0 or decisiones_nuria > 0):
        estado = "Listo para enviar a Nuria"
    elif pendientes_nuria > 0 and enviado_nuria_at:
        estado = "Pendiente de revisión Nuria"
    elif decisiones_nuria > 0:
        estado = "Revisión parcial"
    else:
        estado = "Completado"

    conn.execute(
        "UPDATE infonalia_dias SET estado = ?, updated_at = ? WHERE id = ?",
        (estado, timestamp, dia_id),
    )


def day_row_to_dict(conn: Any, row: Any) -> dict[str, object]:
    licitacion_rows = conn.execute(
        """
        SELECT id, estado, updated_at
        FROM licitaciones
        WHERE infonalia_dia_id = ?
        ORDER BY id ASC
        """,
        (row["id"],),
    ).fetchall()
    counts_rows = conn.execute(
        """
        SELECT estado, COUNT(*) AS total
        FROM licitaciones
        WHERE infonalia_dia_id = ?
        GROUP BY estado
        """,
        (row["id"],),
    ).fetchall()
    counts: dict[str, int] = {}
    for count_row in counts_rows:
        estado = normalize_licitacion_estado(count_row["estado"])
        counts[estado] = counts.get(estado, 0) + int(count_row["total"] or 0)
    total = len(licitacion_rows)
    decisiones_nuria = (
        counts.get(ESTADO_DESCARTADA, 0)
        + counts.get(ESTADO_DESCARGAR_PARA_VER, 0)
        + counts.get(ESTADO_PREPARAR_FICHA, 0)
    )
    nuria_total = counts.get(ESTADO_ENVIADA_NURIA, 0) + decisiones_nuria
    nuria_pending_update = is_nuria_update_pending(row)
    activity = _licitacion_activity(conn, licitacion_rows)
    admin_managed = sum(1 for item in activity.values() if item.get("admin"))
    reviewer_managed = sum(1 for item in activity.values() if item.get("reviewer"))
    avance = round(((total - counts.get(ESTADO_IMPORTADA, 0)) / total) * 100) if total else 0
    last_activity_at = _max_timestamp(
        row_value(row, "updated_at"),
        row_value(row, "enviado_nuria_at"),
        row_value(row, "reviewed_at"),
        *(item.get("last_activity_at") for item in activity.values()),
    )
    last_reviewer_at = _max_timestamp(*(item.get("last_reviewer_at") for item in activity.values()))
    estado_visual = _day_visual_state(
        row,
        total=total,
        pendientes=counts.get(ESTADO_IMPORTADA, 0),
        pendientes_nuria=counts.get(ESTADO_ENVIADA_NURIA, 0),
        reviewer_managed=reviewer_managed,
    )
    return {
        "id": row["id"],
        "fecha": row["fecha"],
        "fecha_formateada": format_date_es(row["fecha"]),
        "titulo": row["titulo"],
        "estado": row["estado"],
        "estado_visual": estado_visual,
        "total": total,
        "licitaciones_texto": f"{total} licitaciones" if total != 1 else "1 licitación",
        "gestionadas_admin": admin_managed,
        "gestionadas_nuria": reviewer_managed,
        "avance_porcentaje": avance,
        "total_nuria": nuria_total,
        "pendientes": counts.get(ESTADO_IMPORTADA, 0),
        "descartadas_mi": counts.get(ESTADO_DESCARTADA, 0),
        "pendientes_nuria": counts.get(ESTADO_ENVIADA_NURIA, 0),
        "decisiones_nuria": decisiones_nuria,
        "descartadas_nuria": counts.get(ESTADO_DESCARTADA, 0),
        "solo_descargar": counts.get(ESTADO_DESCARGAR_PARA_VER, 0),
        "preparar_licitacion": counts.get(ESTADO_PREPARAR_FICHA, 0),
        "descargadas": 0,
        "enviado_nuria_at": row_value(row, "enviado_nuria_at"),
        "fecha_envio_nuria": format_datetime_es(row_value(row, "enviado_nuria_at")) if row_has_key(row, "enviado_nuria_at") else "",
        "nuria_dirty_at": row_value(row, "nuria_dirty_at"),
        "fecha_cambio_nuria": format_datetime_es(row_value(row, "nuria_dirty_at")) if row_has_key(row, "nuria_dirty_at") else "",
        "nuria_pending_update": nuria_pending_update,
        "reviewed_at": row_value(row, "reviewed_at"),
        "fecha_revision": format_datetime_es(row_value(row, "reviewed_at")) if row_has_key(row, "reviewed_at") else "",
        "ultima_actividad_at": last_activity_at,
        "ultima_actividad": _format_timestamp(last_activity_at),
        "ultima_accion_nuria_at": last_reviewer_at,
        "ultima_accion_nuria": _format_timestamp(last_reviewer_at),
        "counts": counts,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
