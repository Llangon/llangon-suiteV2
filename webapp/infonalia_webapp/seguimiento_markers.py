from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

try:
    from .normalization import clean_text
    from .storage_paths import normalize_relative_folder_path, path_is_relative_to
except ImportError:
    from normalization import clean_text
    from storage_paths import normalize_relative_folder_path, path_is_relative_to


FOLLOW_MARKER_NAME = "EnSeguimiento.llangon"
ID_MARKER_RE = re.compile(r"^([0-9]+)\.llangon$")
DEFAULT_MONITOR_YEAR_MIN = 2000
DEFAULT_MONITOR_YEAR_MAX = 2300
LEGACY_REPLICA_PREFIX = re.compile(r"^[A-Za-z]:\\ReplicaDb(?:\\|/)?", re.IGNORECASE)


def monitor_year_bounds(env: dict[str, str] | None = None) -> tuple[int, int]:
    source = os.environ if env is None else env
    try:
        min_year = int(source.get("INFONALIA_MONITOR_YEAR_MIN", str(DEFAULT_MONITOR_YEAR_MIN)) or DEFAULT_MONITOR_YEAR_MIN)
    except (TypeError, ValueError):
        min_year = DEFAULT_MONITOR_YEAR_MIN
    try:
        max_year = int(source.get("INFONALIA_MONITOR_YEAR_MAX", str(DEFAULT_MONITOR_YEAR_MAX)) or DEFAULT_MONITOR_YEAR_MAX)
    except (TypeError, ValueError):
        max_year = DEFAULT_MONITOR_YEAR_MAX
    if min_year > max_year:
        return DEFAULT_MONITOR_YEAR_MIN, DEFAULT_MONITOR_YEAR_MAX
    return min_year, max_year


def is_year_folder(name: object, min_year: int = DEFAULT_MONITOR_YEAR_MIN, max_year: int = DEFAULT_MONITOR_YEAR_MAX) -> bool:
    text = clean_text(name)
    if not re.fullmatch(r"\d{4}", text):
        return False
    year = int(text)
    return min_year <= year <= max_year


def iter_monitor_year_roots(
    dropbox_root: Path | str,
    min_year: int = DEFAULT_MONITOR_YEAR_MIN,
    max_year: int = DEFAULT_MONITOR_YEAR_MAX,
) -> list[Path]:
    root = Path(dropbox_root)
    if not root.exists() or not root.is_dir():
        return []
    roots: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.is_dir() and not child.is_symlink() and is_year_folder(child.name, min_year, max_year):
            roots.append(child)
    return roots


def ensure_id_marker(licitacion_id: int, folder_path: Path | str) -> dict[str, object]:
    folder = Path(folder_path)
    marker_path = folder / f"{int(licitacion_id)}.llangon"
    result = {
        "ok": False,
        "created": False,
        "exists": False,
        "path": str(marker_path),
        "error": "",
    }
    if int(licitacion_id) <= 0:
        result["error"] = "Id de licitacion no valido."
        return result
    if not folder.exists() or not folder.is_dir():
        result["error"] = "La carpeta de licitacion no existe."
        return result
    if marker_path.exists():
        result["ok"] = marker_path.is_file()
        result["exists"] = marker_path.is_file()
        if not marker_path.is_file():
            result["error"] = "El marcador existe pero no es un fichero."
        return result
    try:
        with marker_path.open("x", encoding="utf-8"):
            pass
    except FileExistsError:
        result["ok"] = marker_path.is_file()
        result["exists"] = marker_path.is_file()
        return result
    except OSError as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    result["created"] = True
    result["exists"] = True
    return result


def _marker_result(
    *,
    ok: bool = False,
    created: bool = False,
    exists: bool = False,
    path: Path | str = "",
    folder_path: Path | str = "",
    error: str = "",
    message: str = "",
) -> dict[str, object]:
    return {
        "ok": ok,
        "created": created,
        "exists": exists,
        "path": str(path),
        "folder_path": str(folder_path),
        "error": error,
        "message": message,
    }


def allowed_marker_folder(
    row: sqlite3.Row | dict[str, object],
    *,
    allowed_roots: Iterable[Path | str],
    dropbox_root: Path | None = None,
) -> tuple[Path | None, str]:
    folder = resolve_marker_folder(row, dropbox_root)
    if folder is None:
        return None, "Sin carpeta asignada."
    if str(folder).startswith("\\\\"):
        return None, "No se permiten rutas UNC para crear marcadores."
    if not folder.exists() or not folder.is_dir():
        return None, "Carpeta no encontrada."
    if folder.is_symlink():
        return None, "No se permiten enlaces simbólicos como carpeta de licitación."
    try:
        resolved = folder.resolve(strict=True)
    except OSError:
        return None, "No se pudo resolver la carpeta."
    for root in allowed_roots:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            continue
        if path_is_relative_to(resolved, root_path):
            return resolved, ""
    return None, "La carpeta queda fuera de las raíces permitidas."


def create_marker_file(
    marker_path: Path,
    *,
    folder_path: Path,
) -> dict[str, object]:
    if marker_path.parent.resolve(strict=True) != folder_path.resolve(strict=True):
        return _marker_result(path=marker_path, folder_path=folder_path, error="Ruta de marcador no segura.")
    if marker_path.exists():
        if marker_path.is_file():
            return _marker_result(
                ok=True,
                exists=True,
                path=marker_path,
                folder_path=folder_path,
                message="El marcador ya existe.",
            )
        return _marker_result(path=marker_path, folder_path=folder_path, error="El marcador existe pero no es un fichero.")
    try:
        with marker_path.open("x", encoding="utf-8"):
            pass
    except FileExistsError:
        return _marker_result(
            ok=marker_path.is_file(),
            exists=marker_path.is_file(),
            path=marker_path,
            folder_path=folder_path,
            message="El marcador ya existe.",
        )
    except OSError as exc:
        return _marker_result(path=marker_path, folder_path=folder_path, error=str(exc))
    return _marker_result(
        ok=True,
        created=True,
        exists=True,
        path=marker_path,
        folder_path=folder_path,
        message="Marcador creado.",
    )


def create_id_marker_for_licitacion(
    row: sqlite3.Row | dict[str, object],
    *,
    allowed_roots: Iterable[Path | str],
    dropbox_root: Path | None = None,
) -> dict[str, object]:
    licitacion_id = int(_row_value(row, "id") or 0)
    if licitacion_id <= 0:
        return _marker_result(error="Id de licitación no válido.")
    folder, error = allowed_marker_folder(row, allowed_roots=allowed_roots, dropbox_root=dropbox_root)
    if folder is None:
        return _marker_result(error=error)
    marker_path = folder / f"{licitacion_id}.llangon"
    return create_marker_file(marker_path, folder_path=folder)


def create_follow_marker_for_licitacion(
    row: sqlite3.Row | dict[str, object],
    *,
    allowed_roots: Iterable[Path | str],
    dropbox_root: Path | None = None,
) -> dict[str, object]:
    folder, error = allowed_marker_folder(row, allowed_roots=allowed_roots, dropbox_root=dropbox_root)
    if folder is None:
        return _marker_result(error=error)
    return create_marker_file(folder / FOLLOW_MARKER_NAME, folder_path=folder)


def remove_follow_marker_for_licitacion(
    row: sqlite3.Row | dict[str, object],
    *,
    allowed_roots: Iterable[Path | str],
    dropbox_root: Path | None = None,
) -> dict[str, object]:
    """Remove only the real follow marker after validating its exact folder."""

    folder, error = allowed_marker_folder(row, allowed_roots=allowed_roots, dropbox_root=dropbox_root)
    if folder is None:
        return {**_marker_result(error=error), "removed": False}
    marker_path = folder / FOLLOW_MARKER_NAME
    if marker_path.parent.resolve(strict=True) != folder.resolve(strict=True):
        return {**_marker_result(path=marker_path, folder_path=folder, error="Ruta de marcador no segura."), "removed": False}
    if not marker_path.exists():
        return {
            **_marker_result(ok=True, path=marker_path, folder_path=folder, message="El marcador no existía."),
            "removed": False,
        }
    if not marker_path.is_file() or marker_path.is_symlink():
        return {
            **_marker_result(path=marker_path, folder_path=folder, error="El marcador no es un fichero normal."),
            "removed": False,
        }
    try:
        marker_path.unlink()
    except OSError as exc:
        return {**_marker_result(path=marker_path, folder_path=folder, error=str(exc)), "removed": False}
    return {
        **_marker_result(ok=True, path=marker_path, folder_path=folder, message="Seguimiento desactivado."),
        "removed": True,
    }


def open_licitacion_folder(
    row: sqlite3.Row | dict[str, object],
    *,
    allowed_roots: Iterable[Path | str],
    dropbox_root: Path | None = None,
    opener: Callable[[str], object] | None = None,
) -> dict[str, object]:
    folder, error = allowed_marker_folder(row, allowed_roots=allowed_roots, dropbox_root=dropbox_root)
    if folder is None:
        return {"ok": False, "folder_path": "", "error": error}
    open_with = opener or getattr(os, "startfile", None)
    if open_with is None:
        return {"ok": False, "folder_path": str(folder), "error": "No hay mecanismo disponible para abrir la carpeta."}
    try:
        open_with(str(folder))
    except OSError as exc:
        return {"ok": False, "folder_path": str(folder), "error": str(exc)}
    return {"ok": True, "folder_path": str(folder), "message": "Carpeta abierta."}


def _row_value(row: sqlite3.Row | dict[str, object], key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError):
        return ""


def _candidate_years_for_row(row: sqlite3.Row | dict[str, object]) -> list[str]:
    years: list[str] = []
    for key in ("fecha_limite", "fecha_presentacion", "fecha_de_presentacion", "fecha_infonalia", "created_at"):
        raw = clean_text(_row_value(row, key))
        if not raw:
            continue
        date_text = raw.replace("Z", "+00:00")
        parsed: datetime | None = None
        try:
            parsed = datetime.fromisoformat(date_text)
        except ValueError:
            parsed = None
        if parsed is None:
            token = re.split(r"\s+", raw, maxsplit=1)[0]
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    parsed = datetime.strptime(token, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            continue
        year = f"{parsed.year:04d}"
        if year not in years:
            years.append(year)
    return years


def _normalize_legacy_route_text(value: str) -> str:
    text = clean_text(value).strip('"')
    if not text:
        return ""
    text = LEGACY_REPLICA_PREFIX.sub("", text).strip("\\/")
    return normalize_relative_folder_path(text)


def _search_relative_candidates(root: Path, relative: str, row: sqlite3.Row | dict[str, object]) -> list[Path]:
    if not relative:
        return []
    relative_path = Path(relative)
    parts = relative_path.parts
    if not parts:
        return []
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key in seen:
            return
        seen.add(key)
        candidates.append(path)

    direct = root / relative_path
    add(direct)

    if not is_year_folder(parts[0]):
        for year in _candidate_years_for_row(row):
            add(root / year / relative_path)
        for year_root in iter_monitor_year_roots(root):
            add(year_root / relative_path)
        if len(parts) == 1:
            for year_root in iter_monitor_year_roots(root):
                for month_dir in sorted((child for child in year_root.iterdir() if child.is_dir()), key=lambda item: item.name):
                    add(month_dir / relative_path)
    return candidates


def _marker_matches_for_row(
    row: sqlite3.Row | dict[str, object],
    dropbox_root: Path,
) -> list[Path]:
    licitacion_id = int(_row_value(row, "id") or 0)
    if licitacion_id <= 0:
        return []
    marker_name = f"{licitacion_id}.llangon"
    matches: list[Path] = []
    for year_root in iter_monitor_year_roots(dropbox_root):
        for dirpath, dirnames, filenames in os.walk(year_root, followlinks=False):
            folder = Path(dirpath)
            dirnames[:] = [name for name in dirnames if not (folder / name).is_symlink()]
            if marker_name in filenames:
                matches.append(folder)
    matches.sort(key=lambda item: str(item).casefold())
    return matches


def resolve_marker_folder_details(
    row: sqlite3.Row | dict[str, object],
    dropbox_root: Path | None = None,
) -> dict[str, object]:
    original = clean_text(_row_value(row, "ruta_carpeta")).strip('"')
    details: dict[str, object] = {
        "original_path": original,
        "normalized_path": "",
        "checked_path": "",
        "resolved_path": "",
        "marker_path": "",
        "marker_match_count": 0,
        "reason": "empty",
        "exists": False,
        "inside_dropbox_root": False,
    }
    if not original:
        return details

    root = Path(dropbox_root).resolve(strict=False) if dropbox_root else None
    relative = _normalize_legacy_route_text(original)
    details["normalized_path"] = relative

    candidate = Path(original)
    if candidate.is_absolute() and root is None:
        details["checked_path"] = str(candidate)
        details["resolved_path"] = str(candidate)
        details["exists"] = candidate.exists() and candidate.is_dir()
        details["reason"] = "absolute_without_root"
        return details

    if candidate.is_absolute() and root is not None:
        resolved = candidate.resolve(strict=False)
        if path_is_relative_to(resolved, root):
            details["checked_path"] = str(resolved)
            details["resolved_path"] = str(resolved)
            details["exists"] = resolved.exists() and resolved.is_dir()
            details["inside_dropbox_root"] = True
            details["reason"] = "absolute_inside_dropbox" if details["exists"] else "absolute_inside_dropbox_missing"
            return details

    if root is None:
        fallback = Path(relative) if relative else candidate
        details["checked_path"] = str(fallback)
        details["resolved_path"] = str(fallback)
        details["exists"] = fallback.exists() and fallback.is_dir()
        details["reason"] = "relative_without_root"
        return details

    for possible in _search_relative_candidates(root, relative, row):
        details["checked_path"] = str(possible)
        if possible.exists() and possible.is_dir():
            details["resolved_path"] = str(possible)
            details["exists"] = True
            details["inside_dropbox_root"] = True
            details["reason"] = "resolved_relative"
            return details

    marker_matches = _marker_matches_for_row(row, root)
    details["marker_match_count"] = len(marker_matches)
    if len(marker_matches) == 1:
        match = marker_matches[0]
        details["checked_path"] = str(match)
        details["resolved_path"] = str(match)
        details["exists"] = match.exists() and match.is_dir()
        details["inside_dropbox_root"] = True
        details["marker_path"] = str(match / f"{int(_row_value(row, 'id') or 0)}.llangon")
        details["reason"] = "resolved_by_unique_marker"
        return details
    if len(marker_matches) > 1:
        details["checked_path"] = str(root)
        details["inside_dropbox_root"] = True
        details["reason"] = "multiple_markers"
        return details

    if relative:
        possible = root / Path(relative)
        details["checked_path"] = str(possible)
        details["inside_dropbox_root"] = True
        details["reason"] = "missing_after_normalization"
        return details

    details["checked_path"] = str(root)
    details["inside_dropbox_root"] = True
    details["reason"] = "unresolved"
    return details


def resolve_marker_folder(row: sqlite3.Row | dict[str, object], dropbox_root: Path | None = None) -> Path | None:
    details = resolve_marker_folder_details(row, dropbox_root)
    resolved = clean_text(details.get("resolved_path"))
    if not resolved:
        checked = clean_text(details.get("checked_path"))
        return Path(checked) if checked else None
    return Path(resolved)


def marker_status_for_folder(licitacion_id: int, folder_path: Path | str | None) -> dict[str, object]:
    if not folder_path:
        return {
            "activo": False,
            "fuente": "marcador Dropbox",
            "folder_path": "",
            "folder_exists": False,
            "id_marker_path": "",
            "id_marker_exists": False,
            "follow_marker_path": "",
            "follow_marker_exists": False,
            "warning": "Sin carpeta asignada.",
        }
    folder = Path(folder_path)
    id_marker = folder / f"{int(licitacion_id)}.llangon"
    follow_marker = folder / FOLLOW_MARKER_NAME
    folder_exists = folder.exists() and folder.is_dir()
    id_exists = folder_exists and id_marker.is_file()
    follow_exists = folder_exists and follow_marker.is_file()
    warning = ""
    if not folder_exists:
        warning = "La ruta guardada no existe."
    elif not id_exists:
        warning = "Falta marcador de identificacion."
    return {
        "activo": bool(follow_exists),
        "fuente": "marcador Dropbox",
        "folder_path": str(folder),
        "folder_exists": bool(folder_exists),
        "id_marker_path": str(id_marker),
        "id_marker_exists": bool(id_exists),
        "follow_marker_path": str(follow_marker),
        "follow_marker_exists": bool(follow_exists),
        "warning": warning,
    }


def get_marker_status_for_licitacion(
    row: sqlite3.Row | dict[str, object],
    dropbox_root: Path | None = None,
) -> dict[str, object]:
    folder = resolve_marker_folder(row, dropbox_root)
    status = marker_status_for_folder(int(_row_value(row, "id") or 0), folder)
    status["ultima_sync"] = clean_text(_row_value(row, "seguimiento_ultima_sync")) or clean_text(
        _row_value(row, "seguimiento_ultimo_check")
    )
    status["marker_path_cache"] = clean_text(_row_value(row, "seguimiento_marker_path"))
    status["warning_cache"] = clean_text(_row_value(row, "seguimiento_marker_warning"))
    return status


def find_id_markers(
    dropbox_root: Path | str,
    min_year: int = DEFAULT_MONITOR_YEAR_MIN,
    max_year: int = DEFAULT_MONITOR_YEAR_MAX,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for year_root in iter_monitor_year_roots(dropbox_root, min_year, max_year):
        for dirpath, dirnames, filenames in os.walk(year_root, followlinks=False):
            folder = Path(dirpath)
            dirnames[:] = [
                name for name in dirnames
                if not (folder / name).is_symlink()
            ]
            for filename in sorted(filenames):
                match = ID_MARKER_RE.fullmatch(filename)
                if not match:
                    continue
                licitacion_id = int(match.group(1))
                marker_path = folder / filename
                records.append(
                    {
                        "licitacion_id": licitacion_id,
                        "folder_path": folder,
                        "marker_path": marker_path,
                        "follow_marker_exists": (folder / FOLLOW_MARKER_NAME).is_file(),
                        "year_root": year_root,
                    }
                )
    return records


def scan_follow_markers(
    dropbox_root: Path | str,
    min_year: int = DEFAULT_MONITOR_YEAR_MIN,
    max_year: int = DEFAULT_MONITOR_YEAR_MAX,
) -> dict[str, object]:
    records = find_id_markers(dropbox_root, min_year, max_year)
    by_folder: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_id: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_folder[str(record["folder_path"])].append(record)
        by_id[int(record["licitacion_id"])].append(record)
    return {
        "found": len(records),
        "following": sum(1 for record in records if record["follow_marker_exists"]),
        "year_roots": [str(path) for path in iter_monitor_year_roots(dropbox_root, min_year, max_year)],
        "folder_conflicts": [
            {"folder_path": folder, "ids": sorted({int(item["licitacion_id"]) for item in items})}
            for folder, items in by_folder.items()
            if len(items) > 1
        ],
        "duplicate_conflicts": [
            {"licitacion_id": licitacion_id, "folders": sorted({str(item["folder_path"]) for item in items})}
            for licitacion_id, items in by_id.items()
            if len({str(item["folder_path"]) for item in items}) > 1
        ],
    }


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _update_licitacion_marker_cache(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    ruta_carpeta: str | None,
    seguimiento_activo: bool,
    marker_path: str,
    warning: str,
    timestamp: str,
) -> None:
    updates: dict[str, object] = {
        "seguimiento_activo": 1 if seguimiento_activo else 0,
        "seguimiento_ultimo_check": timestamp,
    }
    if ruta_carpeta is not None:
        updates["ruta_carpeta"] = ruta_carpeta
    if _column_exists(conn, "licitaciones", "seguimiento_ultima_sync"):
        updates["seguimiento_ultima_sync"] = timestamp
    if _column_exists(conn, "licitaciones", "seguimiento_marker_path"):
        updates["seguimiento_marker_path"] = marker_path
    if _column_exists(conn, "licitaciones", "seguimiento_marker_warning"):
        updates["seguimiento_marker_warning"] = warning
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(
        f"UPDATE licitaciones SET {set_clause}, updated_at = ? WHERE id = ?",
        [*updates.values(), timestamp, licitacion_id],
    )


def _reconciliation_events_table_exists(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'licitacion_path_reconciliation_events'"
        ).fetchone()
    )


def _record_path_reconciliation_event(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int | None,
    timestamp: str,
    old_path: str = "",
    new_path: str = "",
    marker_path: str = "",
    result: str,
    reason: str = "",
    details: dict[str, object] | None = None,
) -> None:
    if not _reconciliation_events_table_exists(conn):
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


def sync_marker_paths(
    conn: sqlite3.Connection,
    dropbox_root: Path | str,
    min_year: int = DEFAULT_MONITOR_YEAR_MIN,
    max_year: int = DEFAULT_MONITOR_YEAR_MAX,
    *,
    timestamp: str,
    normalize_folder_path: Callable[[Path], str] | None = None,
) -> dict[str, object]:
    marker_records = find_id_markers(dropbox_root, min_year, max_year)
    by_folder: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_id: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in marker_records:
        by_folder[str(record["folder_path"])].append(record)
        by_id[int(record["licitacion_id"])].append(record)

    folder_conflict_paths = {
        folder for folder, items in by_folder.items() if len(items) > 1
    }
    duplicate_ids = {
        licitacion_id
        for licitacion_id, items in by_id.items()
        if len({str(item["folder_path"]) for item in items}) > 1
    }
    conflicts: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    for folder in sorted(folder_conflict_paths):
        items = by_folder[folder]
        ids = sorted({int(item["licitacion_id"]) for item in items})
        conflicts.append(
            {
                "type": "folder_multiple_id_markers",
                "folder_path": folder,
                "ids": ids,
            }
        )
        for item in items:
            warning = "Conflicto de marcadores: se encontraron varios identificadores en la misma carpeta."
            if conn.execute("SELECT 1 FROM licitaciones WHERE id = ?", (int(item["licitacion_id"]),)).fetchone():
                _update_licitacion_marker_cache(
                    conn,
                    int(item["licitacion_id"]),
                    ruta_carpeta=None,
                    seguimiento_activo=False,
                    marker_path=str(item["marker_path"]),
                    warning=warning,
                    timestamp=timestamp,
                )
            _record_path_reconciliation_event(
                conn,
                licitacion_id=int(item["licitacion_id"]),
                timestamp=timestamp,
                marker_path=str(item["marker_path"]),
                result="conflict",
                reason="folder_multiple_id_markers",
                details={"folder_path": folder, "ids": ids},
            )
    for licitacion_id in sorted(duplicate_ids):
        items = by_id[licitacion_id]
        folders = sorted({str(item["folder_path"]) for item in items})
        conflicts.append(
            {
                "type": "duplicate_licitacion_marker",
                "licitacion_id": licitacion_id,
                "folders": folders,
            }
        )
        warning = "Conflicto de marcadores: se encontraron varias carpetas posibles para esta licitación."
        for item in items:
            if conn.execute("SELECT 1 FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone():
                _update_licitacion_marker_cache(
                    conn,
                    licitacion_id,
                    ruta_carpeta=None,
                    seguimiento_activo=False,
                    marker_path=str(item["marker_path"]),
                    warning=warning,
                    timestamp=timestamp,
                )
            _record_path_reconciliation_event(
                conn,
                licitacion_id=licitacion_id,
                timestamp=timestamp,
                marker_path=str(item["marker_path"]),
                result="conflict",
                reason="duplicate_licitacion_marker",
                details={"folders": folders},
            )

    updated = 0
    following = 0
    for record in marker_records:
        licitacion_id = int(record["licitacion_id"])
        folder_text = str(record["folder_path"])
        if folder_text in folder_conflict_paths or licitacion_id in duplicate_ids:
            continue
        row = conn.execute("SELECT id, ruta_carpeta FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            warnings.append(
                {
                    "type": "missing_licitacion",
                    "licitacion_id": licitacion_id,
                    "folder_path": folder_text,
                }
            )
            _record_path_reconciliation_event(
                conn,
                licitacion_id=licitacion_id,
                timestamp=timestamp,
                marker_path=str(record["marker_path"]),
                result="missing_licitacion",
                reason="marker_without_database_row",
                details={"folder_path": folder_text},
            )
            continue
        normalized_folder = normalize_folder_path(Path(record["folder_path"])) if normalize_folder_path else folder_text
        old_folder = clean_text(row["ruta_carpeta"])
        should_update_path = normalized_folder != old_folder
        marker_warning = ""
        _update_licitacion_marker_cache(
            conn,
            licitacion_id,
            ruta_carpeta=normalized_folder if should_update_path else None,
            seguimiento_activo=bool(record["follow_marker_exists"]),
            marker_path=str(record["marker_path"]),
            warning=marker_warning,
            timestamp=timestamp,
        )
        updated += 1 if should_update_path else 0
        following += 1 if record["follow_marker_exists"] else 0
        _record_path_reconciliation_event(
            conn,
            licitacion_id=licitacion_id,
            timestamp=timestamp,
            old_path=old_folder,
            new_path=normalized_folder,
            marker_path=str(record["marker_path"]),
            result="updated" if should_update_path else "unchanged",
            reason="unique_marker_found",
            details={"follow_marker_exists": bool(record["follow_marker_exists"])},
        )

    missing_without_marker = 0
    rows_without_marker = conn.execute("SELECT id, ruta_carpeta FROM licitaciones").fetchall()
    for row in rows_without_marker:
        licitacion_id = int(row["id"])
        if licitacion_id in by_id:
            continue
        old_folder = clean_text(row["ruta_carpeta"])
        if not old_folder:
            continue
        resolved = resolve_marker_folder(row, Path(dropbox_root))
        if resolved is not None and resolved.exists() and resolved.is_dir():
            continue
        missing_without_marker += 1
        warning = "Carpeta no encontrada y sin marcador localizable."
        _update_licitacion_marker_cache(
            conn,
            licitacion_id,
            ruta_carpeta=None,
            seguimiento_activo=False,
            marker_path="",
            warning=warning,
            timestamp=timestamp,
        )
        _record_path_reconciliation_event(
            conn,
            licitacion_id=licitacion_id,
            timestamp=timestamp,
            old_path=old_folder,
            result="not_found",
            reason="folder_missing_without_marker",
            details={"dropbox_root": str(dropbox_root)},
        )
        warnings.append(
            {
                "type": "folder_missing_without_marker",
                "licitacion_id": licitacion_id,
                "folder_path": old_folder,
            }
        )

    return {
        "ok": True,
        "found": len(marker_records),
        "updated": updated,
        "following": following,
        "missing_without_marker": missing_without_marker,
        "conflicts": conflicts,
        "warnings": warnings,
        "year_roots": [str(path) for path in iter_monitor_year_roots(dropbox_root, min_year, max_year)],
        "min_year": min_year,
        "max_year": max_year,
    }
