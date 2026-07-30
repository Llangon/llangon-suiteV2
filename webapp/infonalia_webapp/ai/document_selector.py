from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from pathlib import Path

try:
    from ..dropbox_paths import (
        DropboxPathError,
        dropbox_base_status,
        resolve_licitacion_folder,
    )
except ImportError:  # pragma: no cover - soporte para ejecucion directa
    from dropbox_paths import DropboxPathError, dropbox_base_status, resolve_licitacion_folder


PRIORITY_TERMS = (
    "CUADRO",
    "CARACTERISTICAS",
    "CARACTERISTICAS",
    "PCAP",
    "PCA",
    "PPT",
    "PLIEGO",
    "ANEXO",
    "ANEXOS",
)
CORE_PRIORITY_TERMS = (
    "CUADRO",
    "CARACTERISTICAS",
    "CARACTERISTICAS",
    "PCAP",
    "PCA",
    "PPT",
    "ANEXO",
    "ANEXOS",
)
ADMIN_FALLBACK_TERMS = (
    "RESOLUCION",
    "RESOLUCIÓN",
    "APROBACION",
    "APROBACIÓN",
    "INCOACION",
    "INCOACIÓN",
    "PROVIDENCIA",
    "INFORME NECESIDADES",
    "CONCEJALIA",
    "CONCEJALÍA",
)
EXCLUDED_TERMS = (
    "ANO 2022",
    "ANO 2023",
    "ANO 2024",
    "ANO 2025",
    "ANTERIOR",
    "CONCURSO ANTERIOR",
    "LICITACION ANTERIOR",
    "OFERTAS ANTERIOR",
    "OFERTA ANTERIOR",
    "EJERCICIO ANTERIOR",
    "ADJUDICACION ANTERIOR",
    "ACTA",
    "APERTURA",
    "VALORACION",
    "VALORACIÓN",
    "ADJUDICACION",
    "ADJUDICACIÓN",
    "RESOLUCION DE ADJUDICACION",
    "RESOLUCIÓN DE ADJUDICACIÓN",
    "CUADRO LICITACION ANTERIOR",
    "CUADRO OFERTAS ANTERIOR",
    "HISTORICO",
    "HISTÓRICO",
)
CLIENT_OR_GENERATED_FOLDER_TERMS = (
    "CLIENTE",
    "CLIENTES",
    "SALVADOR",
    "NURIA",
    "MANOLO",
    "LLANGON",
    "ASESORES",
    "OFERTA",
    "OFERTAS",
    "PREPARACION",
    "PREPARACIÓN",
    "PROPUESTA",
    "PROPUESTAS",
    "RESUMEN",
    "INDICE",
    "ÍNDICE",
    "PREGUNTAS Y RESPUESTAS",
)


def _clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _row_value(row: sqlite3.Row | dict | object, key: str) -> str:
    try:
        if isinstance(row, sqlite3.Row):
            return str(row[key] or "") if key in row.keys() else ""
        if isinstance(row, dict):
            return str(row.get(key) or "")
    except Exception:
        return ""
    return ""


def _priority(path: Path, root: Path) -> tuple[int, int, str]:
    upper = _clean_text(path.name).upper()
    try:
        depth = max(0, len(path.relative_to(root).parts) - 1)
    except ValueError:
        depth = 99
    if any(term in upper for term in ("CUADRO", "CARACTERISTICAS")):
        return (0, depth, path.name.lower())
    if "PCAP" in upper or "PCA" in upper:
        return (1, depth, path.name.lower())
    if "PPT" in upper:
        return (2, depth, path.name.lower())
    if "PLIEGO" in upper:
        return (3, depth, path.name.lower())
    if "ANEX" in upper:
        return (4, depth, path.name.lower())
    return (9, depth, path.name.lower())


def _selection_reason(name: str) -> str:
    upper = _clean_text(name).upper()
    for term in PRIORITY_TERMS:
        if term in upper:
            return f"Coincide con {term}"
    return "PDF del expediente"


def _has_priority(name: str) -> bool:
    upper = _clean_text(name).upper()
    return any(term in upper for term in PRIORITY_TERMS)


def _has_core_priority(name: str) -> bool:
    upper = _clean_text(name).upper()
    return any(term in upper for term in CORE_PRIORITY_TERMS)


def _is_admin_fallback_document(name: str) -> bool:
    upper = _clean_text(name).upper()
    return any(term in upper for term in ADMIN_FALLBACK_TERMS)


def _path_info(path: Path, root: Path) -> dict[str, object]:
    try:
        stat = path.stat()
        relative = os.path.relpath(path, root)
    except OSError:
        stat = None
        relative = path.name
    return {
        "path": str(path),
        "name": path.name,
        "relative_path": relative,
        "size_bytes": stat.st_size if stat else 0,
    }


def _discard_reason(path: Path, root: Path, max_file_mb: int) -> str:
    if path.suffix.lower() != ".pdf":
        return "No es PDF"

    upper_name = _clean_text(path.name).upper()
    upper_stem = _clean_text(path.stem).upper()
    if "FICHA" in upper_name:
        return "Ficha/resumen generado, no apto para análisis IA"

    upper_relative = _clean_text(os.path.relpath(path, root)).upper()
    for term in EXCLUDED_TERMS:
        if term in upper_name or term in upper_relative:
            return f"Descartado por {term}"

    try:
        relative_parts = path.relative_to(root).parts[:-1]
    except ValueError:
        relative_parts = ()
    for part in relative_parts:
        upper_part = _clean_text(part).upper()
        if any(term in upper_part for term in CLIENT_OR_GENERATED_FOLDER_TERMS):
            return "Subcarpeta de cliente o documentación generada manualmente"

    try:
        if path.stat().st_size > max_file_mb * 1024 * 1024:
            return f"Supera el límite de {max_file_mb} MB"
    except OSError:
        return "No se puede leer el fichero"

    if not upper_stem:
        return "Nombre de fichero no válido"
    return ""


def _final_reason(diagnostics: dict[str, object], selected: list[dict[str, object]]) -> str:
    if selected:
        return ""
    if not diagnostics.get("ruta_carpeta"):
        return "La licitación no tiene ruta de carpeta configurada."
    if not diagnostics.get("dropbox_base_ok"):
        return diagnostics.get("dropbox_base_error") or "Carpeta Dropbox no configurada."
    if not diagnostics.get("resolved_inside_dropbox"):
        return "La ruta queda fuera de la carpeta base de Dropbox."
    if not diagnostics.get("resolved_exists"):
        return "La ruta física de la licitación no existe."
    if not diagnostics.get("resolved_is_dir"):
        return "La ruta física de la licitación no es una carpeta."
    if int(diagnostics.get("pdfs_found_count") or 0) == 0:
        return "Carpeta válida, pero no se han encontrado PDFs."
    if int(diagnostics.get("discarded_documents_count") or 0) > 0:
        return "Carpeta válida, PDFs encontrados, pero todos fueron descartados."
    return "No hay documentos aptos para análisis IA"


def inspect_document_selection(
    licitacion: sqlite3.Row | dict,
    *,
    max_documents: int,
    max_file_mb: int,
) -> dict[str, object]:
    folder_text = _row_value(licitacion, "ruta_carpeta")
    base_status = dropbox_base_status()
    diagnostics: dict[str, object] = {
        "dropbox_base_path": base_status.path,
        "dropbox_base_configured": base_status.configured,
        "dropbox_base_ok": base_status.ok,
        "dropbox_base_error": base_status.error,
        "dropbox_base_source": base_status.source,
        "ruta_carpeta": folder_text,
        "resolved_path": "",
        "resolved_exists": False,
        "resolved_is_dir": False,
        "resolved_inside_dropbox": False,
        "resolved_reason": "",
        "resolved_message": "",
        "pdfs_found_count": 0,
        "pdfs_found": [],
        "discarded_documents_count": 0,
        "discarded_documents": [],
        "selected_documents": [],
        "final_reason": "",
    }

    if not folder_text:
        diagnostics["final_reason"] = _final_reason(diagnostics, [])
        return {"selected_documents": [], "diagnostics": diagnostics}

    if not base_status.ok:
        diagnostics["final_reason"] = _final_reason(diagnostics, [])
        return {"selected_documents": [], "diagnostics": diagnostics}

    try:
        resolution = resolve_licitacion_folder(licitacion, dropbox_base=Path(base_status.path))
    except DropboxPathError as exc:
        diagnostics["resolved_message"] = str(exc)
        diagnostics["resolved_reason"] = "invalid_path"
        diagnostics["final_reason"] = str(exc)
        return {"selected_documents": [], "diagnostics": diagnostics}

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
        diagnostics["final_reason"] = _final_reason(diagnostics, [])
        return {"selected_documents": [], "diagnostics": diagnostics}

    folder = Path(resolution.path)
    diagnostics["resolved_is_dir"] = folder.is_dir()
    if not folder.is_dir():
        diagnostics["final_reason"] = _final_reason(diagnostics, [])
        return {"selected_documents": [], "diagnostics": diagnostics}

    found: list[Path] = []
    for item in folder.rglob("*.pdf"):
        if item.is_file():
            found.append(item)
    found.sort(key=lambda item: (len(item.relative_to(folder).parts), str(item).lower()))
    diagnostics["pdfs_found"] = [_path_info(item, folder) for item in found]
    diagnostics["pdfs_found_count"] = len(found)

    candidates: list[Path] = []
    discarded: list[dict[str, object]] = []
    for item in found:
        reason = _discard_reason(item, folder, max_file_mb)
        if reason:
            info = _path_info(item, folder)
            info["reason"] = reason
            discarded.append(info)
            continue
        candidates.append(item)
    core_priority_candidates = [item for item in candidates if _has_core_priority(item.name)]
    if core_priority_candidates:
        filtered_candidates: list[Path] = []
        for item in candidates:
            if _is_admin_fallback_document(item.name):
                info = _path_info(item, folder)
                info["reason"] = "Documento administrativo omitido al existir PCAP/PPT/Cuadro/Anexo prioritario"
                discarded.append(info)
                continue
            filtered_candidates.append(item)
        candidates = filtered_candidates

    diagnostics["discarded_documents"] = discarded
    diagnostics["discarded_documents_count"] = len(discarded)
    priority_candidates = [item for item in candidates if _has_priority(item.name)]
    selected_pool = priority_candidates or candidates
    selected_pool.sort(key=lambda item: _priority(item, folder))

    selected: list[dict[str, object]] = []
    for path in selected_pool[:max_documents]:
        info = _path_info(path, folder)
        info["reason"] = _selection_reason(path.name)
        selected.append(info)

    diagnostics["selected_documents"] = selected
    diagnostics["final_reason"] = _final_reason(diagnostics, selected)
    return {"selected_documents": selected, "diagnostics": diagnostics}


def select_relevant_documents(
    licitacion: sqlite3.Row | dict,
    *,
    max_documents: int,
    max_file_mb: int,
) -> list[dict[str, object]]:
    result = inspect_document_selection(licitacion, max_documents=max_documents, max_file_mb=max_file_mb)
    return list(result["selected_documents"])
