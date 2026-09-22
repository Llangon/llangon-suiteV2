from __future__ import annotations

import os
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from ..ai.file_selection import BLOCKED_EXTENSIONS, resolve_ai_source_folder


PORTAL_DOWNLOAD_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".xml",
    ".html",
    ".htm",
    ".zip",
    ".7z",
}
MAX_PORTAL_FILE_MB = 100


class PortalFileSelectionError(ValueError):
    pass


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _is_ficha(path: Path) -> bool:
    return path.suffix.casefold() == ".pdf" and _fold(path.stem).strip().startswith("ficha")


def _is_hidden_or_internal(path: Path, relative_path: str) -> bool:
    folded = _fold(relative_path)
    return path.name.startswith(".") or any(
        term in folded
        for term in (
            "infonalia_manifest",
            "ai_work",
            "runtime",
            "comando_python",
            "preguntas y respuestas",
            "adjuntos de preguntas",
        )
    )


def _safe_relative(value: object) -> Path:
    text = str(value or "").replace("/", os.sep).strip()
    rel = Path(text)
    if (
        not text
        or rel.is_absolute()
        or rel.drive
        or any(part in {"", ".."} for part in rel.parts)
        or any(":" in part or any(ord(ch) < 32 for ch in part) for part in rel.parts)
    ):
        raise PortalFileSelectionError("La selección contiene una ruta no permitida.")
    return rel


def _human_size(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    if value >= 1024:
        return f"{round(value / 1024)} KB"
    return f"{value} B"


def _modified_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat()
    except OSError:
        return ""


def list_portal_files(licitacion: sqlite3.Row | dict, *, max_file_mb: int = MAX_PORTAL_FILE_MB) -> dict[str, object]:
    folder, diagnostics = resolve_ai_source_folder(licitacion)
    max_bytes = max_file_mb * 1024 * 1024
    items: list[dict[str, object]] = []
    ficha_count = 0
    for path in sorted(folder.rglob("*"), key=lambda item: str(item.relative_to(folder)).casefold()):
        if not path.is_file():
            continue
        relative_path = os.path.relpath(path, folder)
        suffix = path.suffix.casefold()
        if _is_hidden_or_internal(path, relative_path) or suffix in BLOCKED_EXTENSIONS - {".zip", ".7z"}:
            continue
        if suffix not in PORTAL_DOWNLOAD_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        is_ficha = _is_ficha(path)
        ficha_count += int(is_ficha)
        too_large = size > max_bytes
        items.append(
            {
                "id": relative_path,
                "name": path.name,
                "extension": suffix.lstrip(".").upper(),
                "modified_at": _modified_at(path),
                "size_bytes": size,
                "size_human": _human_size(size),
                "relative_path": relative_path,
                "is_ficha_candidate": is_ficha,
                "required": False,
                "selected_by_default": False,
                "selectable": not too_large,
                "warning": f"Supera el límite de {max_file_mb} MB" if too_large else "",
            }
        )
    if ficha_count == 1:
        for item in items:
            if item["is_ficha_candidate"] and item["selectable"]:
                item["required"] = True
                item["selected_by_default"] = True
    diagnostics.update({"files_found_count": len(items), "ficha_candidates_count": ficha_count})
    return {
        "items": items,
        "diagnostics": diagnostics,
        "can_prepare": ficha_count >= 1,
        "blocking_error": (
            "No se encuentra Ficha.pdf en la carpeta del expediente."
            if ficha_count == 0
            else ""
        ),
        "selection_notice": (
            "Hay varias fichas de cliente. Selecciona una sola; cada ficha generará un portal independiente."
            if ficha_count > 1
            else ""
        ),
    }


def resolve_portal_files(
    licitacion: sqlite3.Row | dict,
    selected_files: list[object],
    *,
    max_file_mb: int = MAX_PORTAL_FILE_MB,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    folder, _diagnostics = resolve_ai_source_folder(licitacion)
    max_bytes = max_file_mb * 1024 * 1024
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in selected_files:
        rel = _safe_relative(raw)
        relative_path = str(rel)
        key = relative_path.casefold()
        if key in seen:
            continue
        seen.add(key)
        path = (folder / rel).resolve()
        try:
            path.relative_to(folder.resolve())
        except ValueError as exc:
            raise PortalFileSelectionError("La selección contiene un fichero fuera del expediente.") from exc
        if not path.is_file():
            raise PortalFileSelectionError(f"No se encuentra el fichero seleccionado: {relative_path}")
        if _is_hidden_or_internal(path, relative_path):
            raise PortalFileSelectionError(f"El fichero no puede incluirse en el portal: {path.name}")
        suffix = path.suffix.casefold()
        if suffix not in PORTAL_DOWNLOAD_EXTENSIONS:
            raise PortalFileSelectionError(f"Tipo de fichero no permitido: {path.name}")
        size = path.stat().st_size
        if size > max_bytes:
            raise PortalFileSelectionError(f"El fichero supera el límite configurado: {path.name}")
        selected.append(
            {
                "path": str(path),
                "name": path.name,
                "relative_path": relative_path,
                "size_bytes": size,
                "size_human": _human_size(size),
                "extension": suffix.lstrip(".").upper(),
                "is_ficha": _is_ficha(path),
            }
        )
    fichas = [item for item in selected if item["is_ficha"]]
    if not selected:
        raise PortalFileSelectionError("Selecciona los ficheros que estarán disponibles en el portal.")
    if len(fichas) != 1:
        raise PortalFileSelectionError("La selección debe incluir una única Ficha.pdf.")
    return fichas[0], selected
