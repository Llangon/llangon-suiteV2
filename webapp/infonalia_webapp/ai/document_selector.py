from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from pathlib import Path


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
EXCLUDED_TERMS = (
    "ANTERIOR",
    "CONCURSO ANTERIOR",
    "OFERTAS ANTERIOR",
    "OFERTA ANTERIOR",
    "EJERCICIO ANTERIOR",
    "ADJUDICACION ANTERIOR",
    "ACTA",
    "APERTURA",
    "VALORACION",
    "CUADRO LICITACION ANTERIOR",
    "CUADRO OFERTAS ANTERIOR",
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


def _priority(name: str) -> tuple[int, str]:
    upper = _clean_text(name).upper()
    if any(term in upper for term in ("CUADRO", "CARACTERISTICAS")):
        return (0, name.lower())
    if "PCAP" in upper or "PCA" in upper:
        return (1, name.lower())
    if "PPT" in upper:
        return (2, name.lower())
    if "PLIEGO" in upper:
        return (3, name.lower())
    if "ANEX" in upper:
        return (4, name.lower())
    return (9, name.lower())


def _selection_reason(name: str) -> str:
    upper = _clean_text(name).upper()
    for term in PRIORITY_TERMS:
        if term in upper:
            return f"Coincide con {term}"
    return "PDF del expediente"


def _excluded(name: str) -> bool:
    upper = _clean_text(name).upper()
    return any(term in upper for term in EXCLUDED_TERMS)


def _is_relevant_pdf(path: Path, max_file_mb: int) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    if _excluded(path.name):
        return False
    try:
        return path.stat().st_size <= max_file_mb * 1024 * 1024
    except OSError:
        return False


def select_relevant_documents(
    licitacion: sqlite3.Row | dict,
    *,
    max_documents: int,
    max_file_mb: int,
) -> list[dict[str, object]]:
    folder_text = _row_value(licitacion, "ruta_carpeta")
    if not folder_text:
        return []
    folder = Path(folder_text)
    if not folder.exists() or not folder.is_dir():
        return []

    candidates: list[Path] = []
    for item in folder.rglob("*.pdf"):
        if item.is_file() and _is_relevant_pdf(item, max_file_mb):
            candidates.append(item)
    candidates.sort(key=lambda item: _priority(item.name))

    selected: list[dict[str, object]] = []
    for path in candidates[:max_documents]:
        try:
            stat = path.stat()
            relative = os.path.relpath(path, folder)
        except OSError:
            continue
        selected.append(
            {
                "path": str(path),
                "name": path.name,
                "relative_path": relative,
                "size_bytes": stat.st_size,
                "reason": _selection_reason(path.name),
            }
        )
    return selected

