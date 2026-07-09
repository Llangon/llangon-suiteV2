from __future__ import annotations

import sqlite3
from datetime import datetime

try:
    from .actuaciones import ACTUACION_ESTADOS_ABIERTOS, actuacion_to_dict
    from .normalization import clean_text
except ImportError:
    from actuaciones import ACTUACION_ESTADOS_ABIERTOS, actuacion_to_dict
    from normalization import clean_text


ACTUACIONES_FILTERS = {"abiertas", "vencidas", "sin_fecha", "sin_abiertas"}


def apply_licitacion_actuaciones_filter(
    where: list[str],
    values: list[object],
    filter_value: str,
    *,
    now_text: str,
) -> None:
    selected = clean_text(filter_value).lower()
    if selected not in ACTUACIONES_FILTERS:
        return
    placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
    if selected == "abiertas":
        where.append(
            f"""
            EXISTS (
                SELECT 1
                FROM actuacion_licitaciones al_filter
                JOIN actuaciones a_filter ON a_filter.id = al_filter.actuacion_id
                WHERE al_filter.licitacion_id = licitaciones.id
                  AND a_filter.estado IN ({placeholders})
            )
            """
        )
        values.extend(sorted(ACTUACION_ESTADOS_ABIERTOS))
    elif selected == "vencidas":
        where.append(
            f"""
            EXISTS (
                SELECT 1
                FROM actuacion_licitaciones al_filter
                JOIN actuaciones a_filter ON a_filter.id = al_filter.actuacion_id
                WHERE al_filter.licitacion_id = licitaciones.id
                  AND a_filter.estado IN ({placeholders})
                  AND a_filter.deadline_at IS NOT NULL
                  AND a_filter.deadline_at <> ''
                  AND a_filter.deadline_at < ?
            )
            """
        )
        values.extend([*sorted(ACTUACION_ESTADOS_ABIERTOS), now_text])
    elif selected == "sin_fecha":
        where.append(
            f"""
            EXISTS (
                SELECT 1
                FROM actuacion_licitaciones al_filter
                JOIN actuaciones a_filter ON a_filter.id = al_filter.actuacion_id
                WHERE al_filter.licitacion_id = licitaciones.id
                  AND a_filter.estado IN ({placeholders})
                  AND (a_filter.deadline_at IS NULL OR a_filter.deadline_at = '')
            )
            """
        )
        values.extend(sorted(ACTUACION_ESTADOS_ABIERTOS))
    elif selected == "sin_abiertas":
        where.append(
            f"""
            NOT EXISTS (
                SELECT 1
                FROM actuacion_licitaciones al_filter
                JOIN actuaciones a_filter ON a_filter.id = al_filter.actuacion_id
                WHERE al_filter.licitacion_id = licitaciones.id
                  AND a_filter.estado IN ({placeholders})
            )
            """
        )
        values.extend(sorted(ACTUACION_ESTADOS_ABIERTOS))


def fetch_licitacion_actuacion_indicators(
    conn: sqlite3.Connection,
    licitacion_ids: list[int],
    *,
    current: datetime,
) -> dict[int, dict[str, object]]:
    if not licitacion_ids:
        return {}
    ids_placeholders = ",".join("?" for _ in licitacion_ids)
    estado_placeholders = ",".join("?" for _ in ACTUACION_ESTADOS_ABIERTOS)
    rows = conn.execute(
        f"""
        SELECT
            al.licitacion_id,
            COUNT(DISTINCT a.id) AS total_abiertas,
            SUM(CASE WHEN a.deadline_at IS NOT NULL AND a.deadline_at <> '' AND a.deadline_at < ? THEN 1 ELSE 0 END) AS vencidas,
            SUM(CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END) AS sin_fecha,
            MIN(CASE WHEN a.deadline_at IS NOT NULL AND a.deadline_at <> '' AND a.deadline_at >= ? THEN a.deadline_at ELSE NULL END) AS proxima_fecha
        FROM actuacion_licitaciones al
        JOIN actuaciones a ON a.id = al.actuacion_id
        WHERE al.licitacion_id IN ({ids_placeholders})
          AND a.estado IN ({estado_placeholders})
        GROUP BY al.licitacion_id
        """,
        [current.isoformat(), current.isoformat(), *licitacion_ids, *sorted(ACTUACION_ESTADOS_ABIERTOS)],
    ).fetchall()
    return {
        int(row["licitacion_id"]): {
            "actuaciones_abiertas": int(row["total_abiertas"] or 0),
            "actuaciones_vencidas": int(row["vencidas"] or 0),
            "actuaciones_sin_fecha": int(row["sin_fecha"] or 0),
            "proxima_actuacion_at": row["proxima_fecha"] or "",
        }
        for row in rows
    }


def _licitacion_ref(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "expediente": row["expediente"] or "",
        "organismo": row["organismo"] or "",
        "objeto": row["objeto"] or "",
        "fecha_limite": row["fecha_limite"] or "",
        "hora_limite": row["hora_limite"] or "",
        "estado": row["estado"] or "",
        "provincia": row["provincia"] or "",
        "plataforma": row["plataforma"] or "",
    }


def _actuacion_licitaciones(conn: sqlite3.Connection, actuacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT l.id, l.expediente, l.organismo, l.objeto, l.fecha_limite, l.hora_limite,
               l.estado, l.provincia, l.plataforma
        FROM actuacion_licitaciones al
        JOIN licitaciones l ON l.id = al.licitacion_id
        WHERE al.actuacion_id = ?
        ORDER BY l.expediente ASC, l.id ASC
        """,
        (actuacion_id,),
    ).fetchall()
    return [_licitacion_ref(row) for row in rows]


def _historial_summary(conn: sqlite3.Connection, actuacion_id: int) -> tuple[int, str]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM actuacion_historial
        WHERE actuacion_id = ?
        """,
        (actuacion_id,),
    ).fetchone()
    comment = conn.execute(
        """
        SELECT comentario
        FROM actuacion_historial
        WHERE actuacion_id = ?
          AND comentario IS NOT NULL
          AND comentario <> ''
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (actuacion_id,),
    ).fetchone()
    return int(row["total"] if row else 0), clean_text(comment["comentario"] if comment else "")


def list_licitacion_actuaciones(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    current: datetime | None = None,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT a.*,
               (
                   SELECT COUNT(*)
                   FROM actuacion_licitaciones al_count
                   WHERE al_count.actuacion_id = a.id
               ) AS licitaciones_count
        FROM actuaciones a
        JOIN actuacion_licitaciones al ON al.actuacion_id = a.id
        WHERE al.licitacion_id = ?
        ORDER BY
            CASE WHEN LOWER(a.estado) IN ('pendiente', 'en_curso', 'en_preparacion', 'preparado', 'preparada') THEN 0 ELSE 1 END ASC,
            CASE WHEN a.deadline_at IS NULL OR a.deadline_at = '' THEN 1 ELSE 0 END ASC,
            a.deadline_at ASC,
            a.id DESC
        """,
        (licitacion_id,),
    ).fetchall()
    items = []
    for row in rows:
        historial_count, ultimo_comentario = _historial_summary(conn, int(row["id"]))
        item = actuacion_to_dict(
            row,
            licitaciones=_actuacion_licitaciones(conn, int(row["id"])),
            historial=[],
            now=current,
        )
        item["historial_count"] = historial_count
        item["ultimo_comentario"] = ultimo_comentario
        items.append(item)
    return items
