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
    total = sum(counts.values())
    decisiones_nuria = (
        counts.get(ESTADO_DESCARTADA, 0)
        + counts.get(ESTADO_DESCARGAR_PARA_VER, 0)
        + counts.get(ESTADO_PREPARAR_FICHA, 0)
    )
    nuria_total = counts.get(ESTADO_ENVIADA_NURIA, 0) + decisiones_nuria
    nuria_pending_update = is_nuria_update_pending(row)
    return {
        "id": row["id"],
        "fecha": row["fecha"],
        "fecha_formateada": format_date_es(row["fecha"]),
        "titulo": row["titulo"],
        "estado": row["estado"],
        "total": total,
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
        "counts": counts,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
