from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from .classification import document_group


GROUP_ORDER = [
    "Documentos principales",
    "Requerimientos",
    "Anexos",
    "Oferta / Sobres",
    "Otros",
]


def _row_dict(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _file_url(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        return path.resolve(strict=False).as_uri()
    except ValueError:
        normalized = path_text.replace("\\", "/")
        if len(normalized) >= 3 and normalized[1:3] == ":/":
            return f"file:///{quote(normalized)}"
    return ""


def inventory_row_to_document(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
    item = _row_dict(row)
    folder_path = str(item.get("folder_path") or "")
    relative_path = str(item.get("relative_path") or "")
    absolute_path = str(Path(folder_path) / relative_path) if folder_path and relative_path else ""
    file_type = str(item.get("file_type") or "Otro")
    folder_type = str(item.get("folder_type") or "otros")
    return {
        "name": item.get("file_name") or "",
        "relative_path": relative_path,
        "path": absolute_path,
        "open_url": _file_url(absolute_path),
        "size_bytes": int(item.get("size_bytes") or 0),
        "modified_at": item.get("modified_at") or "",
        "extension": str(item.get("extension") or "").lstrip("."),
        "category": file_type,
        "file_type": file_type,
        "folder_type": folder_type,
        "is_relevant": bool(item.get("is_relevant")),
        "is_system_file": bool(item.get("is_system_file")),
        "group": document_group(file_type, folder_type),
    }


def fetch_inventory_rows(conn: sqlite3.Connection, licitacion_id: int, *, visible_only: bool = False) -> list[sqlite3.Row]:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'licitacion_file_inventory'"
    ).fetchone()
    if table is None:
        return []
    where = ["licitacion_id = ?", "is_missing = 0"]
    values: list[object] = [licitacion_id]
    if visible_only:
        where.append("is_relevant = 1")
        where.append("is_system_file = 0")
    return conn.execute(
        f"""
        SELECT *
        FROM licitacion_file_inventory
        WHERE {" AND ".join(where)}
        ORDER BY
            CASE file_type
                WHEN 'PCAP' THEN 1
                WHEN 'PPT' THEN 2
                WHEN 'Anuncio' THEN 3
                WHEN 'Requerimiento' THEN 4
                WHEN 'Anexo' THEN 5
                ELSE 20
            END,
            relative_path COLLATE NOCASE
        """,
        values,
    ).fetchall()


def build_document_summary(licitacion_id: int, rows: list[sqlite3.Row | dict[str, object]]) -> dict[str, object]:
    items = [_row_dict(row) for row in rows]
    relevant = [item for item in items if item.get("is_relevant") and not item.get("is_system_file") and not item.get("is_missing")]
    file_types = [str(item.get("file_type") or "") for item in relevant]
    folder_types = [str(item.get("folder_type") or "") for item in relevant]
    last_seen_values = [str(item.get("last_seen_at") or "") for item in items if item.get("last_seen_at")]
    modified_values = [str(item.get("modified_at") or "") for item in items if item.get("modified_at")]
    return {
        "licitacion_id": licitacion_id,
        "total_files": len([item for item in items if not item.get("is_missing")]),
        "relevant_files_count": len(relevant),
        "system_files_count": len([item for item in items if item.get("is_system_file") and not item.get("is_missing")]),
        "has_pcap": "PCAP" in file_types,
        "has_ppt": "PPT" in file_types,
        "has_announcement": "Anuncio" in file_types,
        "has_annexes": "Anexo" in file_types,
        "has_requirements": "Requerimiento" in file_types or "requerimiento" in folder_types,
        "has_offer_documents": any(item in file_types for item in ["Oferta", "Sobre 1", "Sobre 2", "Sobre 3"]),
        "has_subfolders_sobre_1": "sobre_1" in folder_types,
        "has_subfolders_sobre_2": "sobre_2" in folder_types,
        "has_subfolders_sobre_3": "sobre_3" in folder_types,
        "pcap_count": file_types.count("PCAP"),
        "ppt_count": file_types.count("PPT"),
        "announcement_count": file_types.count("Anuncio"),
        "annex_count": file_types.count("Anexo"),
        "requirement_count": file_types.count("Requerimiento"),
        "offer_count": sum(1 for item in file_types if item in {"Oferta", "Sobre 1", "Sobre 2", "Sobre 3"}),
        "certificates_count": file_types.count("Certificado"),
        "last_inventory_at": max(last_seen_values) if last_seen_values else "",
        "last_file_modified_at": max(modified_values) if modified_values else "",
    }


def build_document_groups(rows: list[sqlite3.Row | dict[str, object]]) -> list[dict[str, object]]:
    documents = [inventory_row_to_document(row) for row in rows]
    grouped: dict[str, list[dict[str, object]]] = {group: [] for group in GROUP_ORDER}
    for document in documents:
        group = str(document.get("group") or "Otros")
        grouped.setdefault(group, []).append(document)
    return [
        {"name": group, "documents": grouped[group], "count": len(grouped[group])}
        for group in GROUP_ORDER
        if grouped.get(group)
    ]


def document_payload_for_licitacion(conn: sqlite3.Connection, licitacion_id: int) -> dict[str, object]:
    all_rows = fetch_inventory_rows(conn, licitacion_id, visible_only=False)
    visible_rows = [row for row in all_rows if row["is_relevant"] and not row["is_system_file"]]
    return {
        "summary": build_document_summary(licitacion_id, all_rows),
        "documents": [inventory_row_to_document(row) for row in visible_rows],
        "groups": build_document_groups(visible_rows),
        "has_inventory": bool(all_rows),
    }
