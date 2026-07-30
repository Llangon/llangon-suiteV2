from __future__ import annotations

import os
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from ..dropbox_paths import DropboxPathError, dropbox_base_status, resolve_licitacion_folder
from .document_selector import inspect_document_selection


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".xml", ".html", ".htm"}
BLOCKED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".llangon",
    ".url",
    ".tmp",
    ".zip",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".log",
}
HISTORICAL_TERMS = (
    "ANO 2022",
    "ANO 2023",
    "ANO 2024",
    "ANO 2025",
    "LICITACION ANTERIOR",
    "CONCURSO ANTERIOR",
    "HISTORICO",
    "ANTERIOR",
)


class AIFileSelectionError(ValueError):
    pass


def _clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


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


def _safe_relative_path(value: object) -> Path:
    text = str(value or "").replace("/", os.sep).strip()
    if not text:
        raise AIFileSelectionError("La selección contiene un fichero vacío.")
    rel = Path(text)
    if rel.is_absolute() or rel.drive or any(part in {"..", ""} for part in rel.parts):
        raise AIFileSelectionError("La selección contiene una ruta no permitida.")
    if any(":" in part or any(ord(ch) < 32 for ch in part) for part in rel.parts):
        raise AIFileSelectionError("La selección contiene una ruta no permitida.")
    return rel


def _is_historical(relative_path: str) -> bool:
    upper = _clean_text(relative_path).upper()
    return any(term in upper for term in HISTORICAL_TERMS)


def _is_internal_or_hidden(path: Path, relative_path: str) -> bool:
    if path.name.startswith("."):
        return True
    upper = _clean_text(relative_path).upper()
    return any(
        term in upper
        for term in (
            "INFONALIA_MANIFEST",
            "AI_WORK",
            "RUNTIME",
            "COMANDO_PYTHON",
            "PREGUNTAS Y RESPUESTAS",
            "ADJUNTOS DE PREGUNTAS",
        )
    )


def resolve_ai_source_folder(licitacion: sqlite3.Row | dict) -> tuple[Path, dict[str, object]]:
    base_status = dropbox_base_status()
    diagnostics: dict[str, object] = {
        "dropbox_base_path": base_status.path,
        "dropbox_base_configured": base_status.configured,
        "dropbox_base_ok": base_status.ok,
        "dropbox_base_error": base_status.error,
        "dropbox_base_source": base_status.source,
    }
    if not base_status.ok:
        raise AIFileSelectionError(base_status.error or "Carpeta Dropbox no configurada.")
    try:
        resolution = resolve_licitacion_folder(licitacion, dropbox_base=Path(base_status.path))
    except DropboxPathError as exc:
        raise AIFileSelectionError(str(exc)) from exc
    diagnostics.update(
        {
            "resolved_path": resolution.path,
            "resolved_exists": resolution.exists,
            "resolved_inside_dropbox": resolution.inside_dropbox_base,
            "resolved_reason": resolution.reason,
            "resolved_message": resolution.message,
        }
    )
    if not resolution.ok or not resolution.exists or not resolution.inside_dropbox_base:
        raise AIFileSelectionError(resolution.message or "La carpeta del expediente no es válida.")
    folder = Path(resolution.path)
    if not folder.is_dir():
        raise AIFileSelectionError("La ruta física de la licitación no es una carpeta.")
    return folder, diagnostics


def list_ai_files(
    licitacion: sqlite3.Row | dict,
    *,
    max_documents: int,
    max_file_mb: int,
) -> dict[str, object]:
    folder, diagnostics = resolve_ai_source_folder(licitacion)
    recommended = inspect_document_selection(licitacion, max_documents=max_documents, max_file_mb=max_file_mb)
    recommended_by_path = {
        str(item.get("relative_path") or item.get("name") or ""): str(item.get("reason") or "Recomendado")
        for item in recommended.get("selected_documents", [])
    }
    items: list[dict[str, object]] = []
    max_bytes = max_file_mb * 1024 * 1024

    for path in sorted(folder.rglob("*"), key=lambda item: str(item.relative_to(folder)).lower()):
        if not path.is_file():
            continue
        relative_path = os.path.relpath(path, folder)
        suffix = path.suffix.lower()
        if _is_internal_or_hidden(path, relative_path) or suffix in BLOCKED_EXTENSIONS:
            continue
        if suffix not in ALLOWED_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        historical = _is_historical(relative_path)
        is_ficha = "FICHA" in _clean_text(path.name).upper()
        too_large = size > max_bytes
        selected = relative_path in recommended_by_path and not historical and not is_ficha and not too_large
        warning = ""
        if historical:
            warning = "Histórico/no recomendado"
        elif is_ficha:
            warning = "Ficha generada/no recomendada"
        elif too_large:
            warning = f"Supera el límite de {max_file_mb} MB"
        items.append(
            {
                "id": relative_path,
                "name": path.name,
                "extension": suffix.lstrip(".").upper(),
                "modified_at": _modified_at(path),
                "size_bytes": size,
                "size_human": _human_size(size),
                "relative_path": relative_path,
                "selected_by_default": selected,
                "selectable": not too_large,
                "reason": recommended_by_path.get(relative_path, ""),
                "warning": warning,
            }
        )

    diagnostics["files_found_count"] = len(items)
    return {"items": items, "diagnostics": diagnostics}


def resolve_selected_ai_files(
    licitacion: sqlite3.Row | dict,
    selected_files: list[object],
    *,
    max_file_mb: int,
) -> list[dict[str, object]]:
    folder, _diagnostics = resolve_ai_source_folder(licitacion)
    max_bytes = max_file_mb * 1024 * 1024
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in selected_files:
        rel = _safe_relative_path(raw)
        relative_path = str(rel)
        if relative_path in seen:
            continue
        seen.add(relative_path)
        path = (folder / rel).resolve()
        try:
            path.relative_to(folder.resolve())
        except ValueError as exc:
            raise AIFileSelectionError("La selección contiene un fichero fuera del expediente.") from exc
        if not path.is_file():
            raise AIFileSelectionError(f"No se encuentra el fichero seleccionado: {relative_path}")
        if _is_internal_or_hidden(path, relative_path):
            raise AIFileSelectionError(
                f"El fichero pertenece al flujo de preguntas y respuestas y no puede enviarse a IA: {path.name}"
            )
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS or suffix in BLOCKED_EXTENSIONS:
            raise AIFileSelectionError(f"Tipo de fichero no permitido: {path.name}")
        size = path.stat().st_size
        if size > max_bytes:
            raise AIFileSelectionError(f"El fichero supera el límite configurado: {path.name}")
        selected.append(
            {
                "path": str(path),
                "name": path.name,
                "relative_path": relative_path,
                "size_bytes": size,
                "extension": suffix.lstrip(".").upper(),
                "reason": "Seleccionado manualmente",
            }
        )
    if not selected:
        raise AIFileSelectionError("Selecciona al menos un fichero para el análisis.")
    return selected
