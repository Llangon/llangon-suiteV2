from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Callable

from .repository import fetch_licitaciones, row_value
from .scanner import MonitorIssue, ScanResult

try:
    from ..normalization import clean_text
    from ..seguimiento_markers import resolve_marker_folder, resolve_marker_folder_details
except ImportError:
    from normalization import clean_text
    from seguimiento_markers import resolve_marker_folder, resolve_marker_folder_details


FolderNormalizer = Callable[[Path], str]
MISSING_FOLDER_WARNING = "Carpeta no encontrada y sin marcador localizable."


def normalize_path(value: str | Path) -> str:
    text = str(value or "")
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


def normalize_route_key(value: str | Path, root_path: Path | str) -> str:
    text = clean_text(value).strip('"')
    if not text:
        return ""
    root = Path(root_path).resolve(strict=False)
    candidate = Path(text)
    if candidate.is_absolute() or (len(text) >= 2 and text[1] == ":"):
        resolved = candidate.resolve(strict=False)
        try:
            return os.path.normcase(str(resolved.relative_to(root)))
        except ValueError:
            return os.path.normcase(str(resolved))
    parts = [part for part in text.replace("\\", "/").split("/") if part and part not in {".", ".."}]
    return os.path.normcase(str(Path(*parts))) if parts else ""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone())


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _record_reconciliation_event(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int | None,
    timestamp: str,
    old_path: str = "",
    new_path: str = "",
    marker_path: str = "",
    result: str,
    reason: str,
    details: dict[str, object] | None = None,
) -> None:
    if not _table_exists(conn, "licitacion_path_reconciliation_events"):
        return
    conn.execute(
        """
        INSERT INTO licitacion_path_reconciliation_events (
            licitacion_id, created_at, old_path, new_path, marker_path, result, reason, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            licitacion_id,
            timestamp,
            old_path,
            new_path,
            marker_path,
            result,
            reason,
            json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
        ),
    )


def _update_marker_warning(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    warning: str,
    marker_path: str,
    timestamp: str,
) -> None:
    existing = conn.execute(
        "SELECT * FROM licitaciones WHERE id = ?",
        (licitacion_id,),
    ).fetchone()
    if existing is not None:
        current_warning = clean_text(row_value(existing, "seguimiento_marker_warning", ""))
        current_marker_path = clean_text(row_value(existing, "seguimiento_marker_path", ""))
        if current_warning == clean_text(warning) and current_marker_path == clean_text(marker_path):
            return
    updates: dict[str, object] = {"updated_at": timestamp}
    if _column_exists(conn, "licitaciones", "seguimiento_marker_warning"):
        updates["seguimiento_marker_warning"] = warning
    if _column_exists(conn, "licitaciones", "seguimiento_marker_path"):
        updates["seguimiento_marker_path"] = marker_path
    if _column_exists(conn, "licitaciones", "seguimiento_ultimo_check"):
        updates["seguimiento_ultimo_check"] = timestamp
    if _column_exists(conn, "licitaciones", "seguimiento_ultima_sync"):
        updates["seguimiento_ultima_sync"] = timestamp
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(f"UPDATE licitaciones SET {set_clause} WHERE id = ?", [*updates.values(), licitacion_id])


def repair_routes(
    conn: sqlite3.Connection,
    scan_result: ScanResult,
    dry_run: bool,
    timestamp: str,
    warnings: list[MonitorIssue],
    normalize_folder_path: FolderNormalizer | None = None,
) -> list[dict[str, object]]:
    rows = fetch_licitaciones(conn, sorted({marker.licitacion_id for marker in scan_result.markers}))
    updates: list[dict[str, object]] = []
    marker_ids = {marker.licitacion_id for marker in scan_result.markers}
    conflict_ids = {int(issue.licitacion_id) for issue in scan_result.conflicts if issue.licitacion_id is not None}
    for issue in scan_result.conflicts:
        if issue.licitacion_id is None:
            _record_reconciliation_event(
                conn,
                licitacion_id=None,
                timestamp=timestamp,
                marker_path=issue.path,
                result="conflict",
                reason=issue.code,
                details=issue.to_dict(),
            )
            continue
        row = conn.execute("SELECT id FROM licitaciones WHERE id = ?", (issue.licitacion_id,)).fetchone()
        if row:
            _update_marker_warning(
                conn,
                issue.licitacion_id,
                warning="Conflicto de marcadores: se encontraron varias carpetas posibles para esta licitación.",
                marker_path=issue.path,
                timestamp=timestamp,
            )
        _record_reconciliation_event(
            conn,
            licitacion_id=issue.licitacion_id,
            timestamp=timestamp,
            marker_path=issue.path,
            result="conflict",
            reason=issue.code,
            details=issue.to_dict(),
        )
    for marker in scan_result.markers:
        row = rows.get(marker.licitacion_id)
        if row is None:
            warnings.append(
                MonitorIssue(
                    code="licitacion_missing",
                    message="Hay marcador .llangon pero la licitacion no existe en SQLite.",
                    path=str(marker.marker_path),
                    licitacion_id=marker.licitacion_id,
                )
            )
            _record_reconciliation_event(
                conn,
                licitacion_id=marker.licitacion_id,
                timestamp=timestamp,
                marker_path=str(marker.marker_path),
                result="missing_licitacion",
                reason="marker_without_database_row",
                details=marker.to_dict(),
            )
            continue
        new_path = normalize_folder_path(marker.folder_path) if normalize_folder_path else str(marker.folder_path)
        old_path = str(row_value(row, "ruta_carpeta", "") or "")
        old_key = normalize_route_key(old_path, scan_result.root_path)
        new_key = normalize_route_key(new_path, scan_result.root_path)
        if old_key == new_key and clean_text(old_path) == clean_text(new_path):
            if not dry_run:
                _update_marker_warning(conn, marker.licitacion_id, warning="", marker_path=str(marker.marker_path), timestamp=timestamp)
            continue
        updates.append(
            {
                "licitacion_id": marker.licitacion_id,
                "old_path": old_path,
                "new_path": new_path,
                "dry_run": dry_run,
            }
        )
        if not dry_run:
            conn.execute(
                "UPDATE licitaciones SET ruta_carpeta = ?, updated_at = ? WHERE id = ?",
                (new_path, timestamp, marker.licitacion_id),
            )
            _update_marker_warning(conn, marker.licitacion_id, warning="", marker_path=str(marker.marker_path), timestamp=timestamp)
            _record_reconciliation_event(
                conn,
                licitacion_id=marker.licitacion_id,
                timestamp=timestamp,
                old_path=old_path,
                new_path=new_path,
                marker_path=str(marker.marker_path),
                result="updated",
                reason="unique_marker_found",
                details=marker.to_dict(),
            )
    rows_without_marker = conn.execute("SELECT * FROM licitaciones").fetchall()
    for row in rows_without_marker:
        licitacion_id = int(row["id"])
        if licitacion_id in marker_ids or licitacion_id in conflict_ids:
            continue
        old_path = clean_text(row_value(row, "ruta_carpeta", ""))
        if not old_path:
            continue
        folder_details = resolve_marker_folder_details(row, scan_result.root_path)
        folder = resolve_marker_folder(row, scan_result.root_path)
        if folder is not None and folder.exists() and folder.is_dir():
            continue
        if folder_details.get("reason") == "multiple_markers":
            warning = "Conflicto de marcadores: se encontraron varias carpetas posibles para esta licitación."
            _update_marker_warning(
                conn,
                licitacion_id,
                warning=warning,
                marker_path="",
                timestamp=timestamp,
            )
            _record_reconciliation_event(
                conn,
                licitacion_id=licitacion_id,
                timestamp=timestamp,
                old_path=old_path,
                result="conflict",
                reason="multiple_markers",
                details=folder_details,
            )
            warnings.append(
                MonitorIssue(
                    code="multiple_markers",
                    message=warning,
                    path=clean_text(folder_details.get("checked_path")) or old_path,
                    licitacion_id=licitacion_id,
                )
            )
            continue
        warnings.append(
            MonitorIssue(
                code="folder_missing_without_marker",
                message=MISSING_FOLDER_WARNING,
                path=clean_text(folder_details.get("checked_path")) or clean_text(folder_details.get("normalized_path")) or old_path,
                licitacion_id=licitacion_id,
            )
        )
        if not dry_run:
            current_warning = clean_text(row_value(row, "seguimiento_marker_warning", ""))
            current_marker_path = clean_text(row_value(row, "seguimiento_marker_path", ""))
            already_recorded = current_warning == MISSING_FOLDER_WARNING and current_marker_path == ""
            _update_marker_warning(
                conn,
                licitacion_id,
                warning=MISSING_FOLDER_WARNING,
                marker_path="",
                timestamp=timestamp,
            )
            if not already_recorded:
                _record_reconciliation_event(
                    conn,
                    licitacion_id=licitacion_id,
                    timestamp=timestamp,
                    old_path=old_path,
                    result="not_found",
                    reason="folder_missing_without_marker",
                    details={
                        "root_path": str(scan_result.root_path),
                        **folder_details,
                    },
                )
    return updates
