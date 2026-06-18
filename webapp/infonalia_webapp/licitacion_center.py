from __future__ import annotations

import sqlite3
from pathlib import Path

try:
    from .download_safety import INTERNAL_DOWNLOAD_FILENAMES, INTERNAL_DOWNLOAD_PREFIXES
    from .monitor.document_summary import document_payload_for_licitacion
    from .normalization import bool_text, clean_text
except ImportError:
    from download_safety import INTERNAL_DOWNLOAD_FILENAMES, INTERNAL_DOWNLOAD_PREFIXES
    from monitor.document_summary import document_payload_for_licitacion
    from normalization import bool_text, clean_text


ESTADOS_INTERNOS = {
    "Nueva",
    "Pendiente revisión",
    "En estudio",
    "Preparando oferta",
    "Presentada",
    "En seguimiento",
    "Descartada",
    "Finalizada",
}


def document_category(name: str) -> str:
    text = clean_text(name).upper()
    if "PCAP" in text or "ADMINISTRATIV" in text:
        return "PCAP"
    if "PPT" in text or "TECNIC" in text:
        return "PPT"
    if "ANEX" in text:
        return "Anexos"
    if "ANUNC" in text:
        return "Anuncios"
    if "ACLAR" in text or "CONSULT" in text:
        return "Aclaraciones"
    if "CORRE" in text or "RECTIF" in text:
        return "Correcciones"
    if "MODELO" in text or "DEUC" in text:
        return "Modelos"
    return "Otros"


def _is_internal_file(path: Path) -> bool:
    return path.name in INTERNAL_DOWNLOAD_FILENAMES or path.name.startswith(INTERNAL_DOWNLOAD_PREFIXES)


def _file_url(path: Path) -> str:
    try:
        return path.resolve(strict=False).as_uri()
    except ValueError:
        return ""


def licitacion_documents(row: sqlite3.Row | dict) -> list[dict[str, object]]:
    folder_text = clean_text(row["ruta_carpeta"] if "ruta_carpeta" in row.keys() else "")
    if not folder_text:
        return []
    folder = Path(folder_text)
    if not folder.exists() or not folder.is_dir():
        return []
    documents: list[dict[str, object]] = []
    for item in sorted(folder.rglob("*")):
        if not item.is_file() or _is_internal_file(item):
            continue
        try:
            stat = item.stat()
            relative = str(item.relative_to(folder))
        except OSError:
            continue
        documents.append(
            {
                "name": item.name,
                "relative_path": relative,
                "path": str(item),
                "open_url": _file_url(item),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "extension": item.suffix.lower().lstrip("."),
                "category": document_category(item.name),
            }
        )
    return documents


def fetch_licitacion_download_indicators(
    conn: sqlite3.Connection,
    licitacion_ids: list[int],
) -> dict[int, dict[str, object]]:
    if not licitacion_ids:
        return {}
    placeholders = ",".join("?" for _ in licitacion_ids)
    rows = conn.execute(
        f"""
        SELECT licitacion_id,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
               MAX(CASE WHEN status = 'failed' THEN error_message ELSE '' END) AS last_error
        FROM download_jobs
        WHERE licitacion_id IN ({placeholders})
        GROUP BY licitacion_id
        """,
        licitacion_ids,
    ).fetchall()
    return {
        int(row["licitacion_id"]): {
            "descarga_fallida": int(row["failed_count"] or 0) > 0,
            "download_error": row["last_error"] or "",
        }
        for row in rows
    }


def seguimiento_novedades(conn: sqlite3.Connection, licitacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, detected_at, source, title, summary, change_type, file_name,
               file_path, status, raw_data_json
        FROM licitacion_seguimiento_novedades
        WHERE licitacion_id = ?
        ORDER BY detected_at DESC, id DESC
        LIMIT 20
        """,
        (licitacion_id,),
    ).fetchall()
    return [{key: row[key] or "" for key in row.keys()} for row in rows]


def licitacion_history(conn: sqlite3.Connection, licitacion_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, event_type, old_value, new_value, user_id, created_at
        FROM licitacion_historial
        WHERE licitacion_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (licitacion_id,),
    ).fetchall()
    return [{key: row[key] or "" for key in row.keys()} for row in rows]


def record_licitacion_history(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    event_type: str,
    old_value: object = "",
    new_value: object = "",
    user_id: str = "",
    timestamp: str,
) -> None:
    conn.execute(
        """
        INSERT INTO licitacion_historial (
            licitacion_id, event_type, old_value, new_value, user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            licitacion_id,
            clean_text(event_type),
            clean_text(old_value),
            clean_text(new_value),
            clean_text(user_id),
            timestamp,
        ),
    )


def center_update_payload(
    data: dict,
    old_row: sqlite3.Row,
    *,
    username: str,
    timestamp: str,
) -> tuple[dict[str, object], list[tuple[str, object, object]]]:
    updates: dict[str, object] = {}
    history: list[tuple[str, object, object]] = []

    if "estado_interno" in data:
        estado = clean_text(data.get("estado_interno")) or "Nueva"
        if estado not in ESTADOS_INTERNOS:
            raise ValueError("Estado interno no valido.")
        updates["estado_interno"] = estado

    if "notas_internas" in data:
        updates["notas_internas"] = clean_text(data.get("notas_internas"))

    if "revisada" in data:
        revisada = bool_text(data.get("revisada"))
        updates["reviewed_at"] = timestamp if revisada else ""
        updates["reviewed_by"] = username if revisada else ""

    for key, new_value in updates.items():
        old_value = old_row[key] if key in old_row.keys() else ""
        if str(old_value or "") != str(new_value or ""):
            history.append((key, old_value, new_value))

    return updates, history


def build_licitacion_center_detail(
    conn: sqlite3.Connection,
    item: dict[str, object],
    *,
    actuaciones: list[dict[str, object]],
) -> dict[str, object]:
    licitacion_id = int(item["id"])
    documents = licitacion_documents(item)
    inventory_payload = document_payload_for_licitacion(conn, licitacion_id)
    if inventory_payload.get("has_inventory"):
        documents = inventory_payload["documents"]
    download = fetch_licitacion_download_indicators(conn, [licitacion_id]).get(licitacion_id, {})
    novedades = seguimiento_novedades(conn, licitacion_id)
    item["revisada"] = bool(clean_text(item.get("reviewed_at")))
    item["estado_interno"] = clean_text(item.get("estado_interno")) or "Nueva"
    item["seguimiento_activo"] = bool(item.get("seguimiento_activo"))
    item["documentacion_descargada"] = bool(clean_text(item.get("ruta_carpeta"))) or bool(documents)
    item["descarga_fallida"] = bool(download.get("descarga_fallida"))
    item["download_error"] = download.get("download_error") or ""
    item["documentos"] = documents
    item["document_summary"] = inventory_payload["summary"]
    item["document_groups"] = inventory_payload["groups"]
    item["documentacion"] = {
        "folder_path": clean_text(item.get("ruta_carpeta")),
        "downloaded": item["documentacion_descargada"],
        "count": len(documents),
        "documents": documents,
        "summary": inventory_payload["summary"],
        "groups": inventory_payload["groups"],
        "from_inventory": bool(inventory_payload.get("has_inventory")),
    }
    item["actuaciones"] = actuaciones
    item["seguimiento"] = {
        "activo": item["seguimiento_activo"],
        "fuente": "cache",
        "desde": clean_text(item.get("seguimiento_desde")),
        "ultimo_check": clean_text(item.get("seguimiento_ultimo_check")),
        "ultima_sync": clean_text(item.get("seguimiento_ultima_sync")),
        "ultima_novedad": clean_text(item.get("seguimiento_ultima_novedad")),
        "marker_path": clean_text(item.get("seguimiento_marker_path")),
        "warning": clean_text(item.get("seguimiento_marker_warning")),
        "novedades": novedades,
        "novedades_count": len(novedades),
    }
    item["historial"] = licitacion_history(conn, licitacion_id)
    return item
