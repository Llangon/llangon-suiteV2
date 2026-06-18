from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Callable

from .repository import fetch_licitaciones, row_value
from .scanner import MonitorIssue, ScanResult


FolderNormalizer = Callable[[Path], str]


def normalize_path(value: str | Path) -> str:
    text = str(value or "")
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


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
            continue
        new_path = normalize_folder_path(marker.folder_path) if normalize_folder_path else str(marker.folder_path)
        old_path = str(row_value(row, "ruta_carpeta", "") or "")
        if normalize_path(old_path) == normalize_path(new_path):
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
    return updates

