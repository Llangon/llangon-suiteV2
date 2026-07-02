from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .dropbox_paths import resolve_licitacion_folder
    from .monitor.classification import classify_document, classify_folder, is_system_file
    from .monitor.document_summary import fetch_inventory_rows, inventory_row_to_document
    from .normalization import clean_text
except ImportError:
    from dropbox_paths import resolve_licitacion_folder
    from monitor.classification import classify_document, classify_folder, is_system_file
    from monitor.document_summary import fetch_inventory_rows, inventory_row_to_document
    from normalization import clean_text


@dataclass(frozen=True)
class DocumentTreeOptions:
    max_depth: int = 8
    max_files: int = 1000


def _row_get(row: Any, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return ""


def _safe_relative_parts(value: object) -> list[str]:
    text = clean_text(value).replace("\\", "/")
    parts = [part.strip() for part in text.split("/") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        raise ValueError("Ruta relativa no segura.")
    if any(Path(part).is_absolute() or (len(part) >= 2 and part[1] == ":") for part in parts):
        raise ValueError("Ruta relativa no segura.")
    return parts


def _empty_folder_node(name: str, relative_path: str = "") -> dict[str, object]:
    return {
        "type": "folder",
        "name": name,
        "relative_path": relative_path,
        "children": [],
    }


def _insert_file(root: dict[str, object], document: dict[str, object]) -> dict[str, object] | None:
    parts = _safe_relative_parts(document.get("relative_path") or document.get("name"))
    if not parts:
        return None
    node = root
    relative_parts: list[str] = []
    for folder_name in parts[:-1]:
        relative_parts.append(folder_name)
        children = node.setdefault("children", [])
        found = None
        for child in children:
            if child.get("type") == "folder" and child.get("name") == folder_name:
                found = child
                break
        if found is None:
            found = _empty_folder_node(folder_name, "/".join(relative_parts))
            children.append(found)
        node = found
    file_name = parts[-1]
    file_node = {
        "type": "file",
        "name": document.get("name") or file_name,
        "relative_path": "/".join(parts),
        "extension": clean_text(document.get("extension")),
        "size_bytes": int(document.get("size_bytes") or 0),
        "modified_at": clean_text(document.get("modified_at")),
        "category": clean_text(document.get("category") or document.get("file_type")),
        "open_url": clean_text(document.get("open_url")),
    }
    node.setdefault("children", []).append(file_node)
    return file_node


def _sort_tree(node: dict[str, object]) -> None:
    children = list(node.get("children") or [])
    children.sort(key=lambda item: (0 if item.get("type") == "folder" else 1, clean_text(item.get("name")).casefold()))
    node["children"] = children
    for child in children:
        if child.get("type") == "folder":
            _sort_tree(child)


def _tree_from_documents(root_name: str, documents: list[dict[str, object]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    root = _empty_folder_node(root_name)
    accepted: list[dict[str, object]] = []
    for document in documents:
        try:
            file_node = _insert_file(root, document)
        except ValueError:
            continue
        if file_node:
            accepted.append(file_node)
    _sort_tree(root)
    return root, accepted


def _file_url(path: Path) -> str:
    try:
        return path.resolve(strict=False).as_uri()
    except ValueError:
        return ""


def _latest_reconciliation_event(conn: sqlite3.Connection, licitacion_id: int) -> dict[str, object]:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'licitacion_path_reconciliation_events'"
    ).fetchone()
    if not table:
        return {}
    row = conn.execute(
        """
        SELECT *
        FROM licitacion_path_reconciliation_events
        WHERE licitacion_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (licitacion_id,),
    ).fetchone()
    if not row:
        return {}
    return {key: row[key] for key in row.keys()}


def _reconciliation_message(event: dict[str, object], marker_warning: str) -> str:
    if marker_warning:
        return marker_warning
    result = clean_text(event.get("result"))
    reason = clean_text(event.get("reason"))
    if result == "updated" and reason == "unique_marker_found":
        return "Ruta de expediente actualizada automáticamente por marcador local."
    if result == "unchanged" and reason == "unique_marker_found":
        return "Ruta validada por marcador local."
    if result == "not_found":
        return "Carpeta no encontrada y sin marcador localizable."
    if result == "conflict":
        return "Conflicto de marcadores: se encontraron varias carpetas posibles para esta licitación."
    return ""


def _physical_documents(folder: Path, options: DocumentTreeOptions) -> tuple[list[dict[str, object]], bool]:
    documents: list[dict[str, object]] = []
    truncated = False
    root = folder.resolve(strict=False)
    for path in sorted(folder.rglob("*"), key=lambda item: str(item).casefold()):
        if len(documents) >= options.max_files:
            truncated = True
            break
        if not path.is_file():
            continue
        try:
            resolved = path.resolve(strict=False)
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if len(parts) > options.max_depth:
            continue
        if is_system_file(path):
            continue
        stat = path.stat()
        relative_text = str(relative).replace("\\", "/")
        documents.append(
            {
                "name": path.name,
                "relative_path": relative_text,
                "extension": path.suffix.lower().lstrip("."),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat(),
                "category": classify_document(path, relative_text),
                "folder_type": classify_folder(relative_text),
                "open_url": _file_url(path),
            }
        )
    return documents, truncated


def build_document_tree_payload(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    options: DocumentTreeOptions | None = None,
) -> dict[str, object]:
    opts = options or DocumentTreeOptions()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        raise ValueError("Licitacion no encontrada")

    resolution = resolve_licitacion_folder(row)
    marker_warning = clean_text(_row_get(row, "seguimiento_marker_warning"))
    reconciliation_event = _latest_reconciliation_event(conn, licitacion_id)
    reconcile_message = _reconciliation_message(reconciliation_event, marker_warning)
    root_name = Path(resolution.path).name if resolution.path else clean_text(_row_get(row, "expediente")) or "Expediente"
    inventory_rows = fetch_inventory_rows(conn, licitacion_id, visible_only=True)
    documents = [inventory_row_to_document(item) for item in inventory_rows]
    source = "inventory" if documents else "physical"
    truncated = False

    if not documents and resolution.ok and resolution.exists:
        documents, truncated = _physical_documents(Path(resolution.path), opts)

    status = "valid" if resolution.ok and resolution.exists else resolution.reason or "missing"
    message = resolution.message
    if marker_warning:
        status = "marker_conflict" if "Conflicto" in marker_warning else "marker_warning"
        message = marker_warning
    if resolution.ok and resolution.exists and not documents and not marker_warning:
        message = "No hay documentación inventariada."

    tree, accepted_documents = _tree_from_documents(root_name, documents)
    return {
        "ok": True,
        "licitacion_id": licitacion_id,
        "root_name": root_name,
        "root_status": status,
        "message": message,
        "folder_status": resolution.to_dict(),
        "path_reconciled": clean_text(reconciliation_event.get("result")) == "updated",
        "path_reconcile_result": clean_text(reconciliation_event.get("result")),
        "path_reconcile_message": reconcile_message,
        "path_reconcile_event": reconciliation_event,
        "marker_warning": marker_warning,
        "last_indexed_at": max([clean_text(doc.get("modified_at")) for doc in accepted_documents if doc.get("modified_at")] or [""]),
        "source": source,
        "truncated": truncated,
        "count": len(accepted_documents),
        "tree": tree.get("children") or [],
    }
