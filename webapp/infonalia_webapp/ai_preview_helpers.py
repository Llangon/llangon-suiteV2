from __future__ import annotations

import re
from typing import Any

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


def extract_lotes_from_text(text: str) -> list[str]:
    source = clean_text(text)
    if not source:
        return []
    pattern = re.compile(
        r"(Lote\s+\d+[\s:.-]+.*?)(?=(?:\s+Lote\s+\d+[\s:.-]+)|$)",
        re.IGNORECASE,
    )
    lotes = []
    for match in pattern.finditer(source):
        lote = clean_text(match.group(1))
        if lote and lote not in lotes:
            lotes.append(lote[:260])
    return lotes[:18]


def extract_keyword_context(text: str, keywords: list[str], window: int = 420) -> list[str]:
    source = clean_text(text)
    lower = source.lower()
    snippets = []
    for keyword in keywords:
        index = lower.find(keyword.lower())
        if index < 0:
            continue
        start = max(0, index - 80)
        end = min(len(source), index + window)
        snippet = clean_text(source[start:end])
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    return snippets[:3]


def _row_get(row: Any, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError):
        return ""


def extract_centros_from_text(row: Any, text: str) -> list[str]:
    values = []
    organismo = clean_text(_row_get(row, "organismo"))
    objeto = clean_text(_row_get(row, "objeto"))
    if organismo:
        values.append(organismo)

    combined = clean_text(f"{objeto} {text[:5000]}")
    patterns = [
        r"\b(?:Hospital|Residencia|Centro|Escuela Infantil|Parador|Colegio|Instituto)\b[^.;\n]{0,110}",
        r"\b(?:centros dependientes|centros de suministro)\b[^.;\n]{0,140}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, combined, re.IGNORECASE):
            value = clean_text(match.group(0))
            if value and value not in values:
                values.append(value)
            if len(values) >= 8:
                return values
    return values[:8]


def preview_payload_to_text(preview: dict) -> str:
    lines = ["Vista preliminar de licitación", ""]
    lines.append("Datos de cabecera:")
    for key, value in preview.get("cabecera", {}).items():
        if value:
            lines.append(f"{key}: {value}")

    def add_section(title: str, items: list[str]) -> None:
        lines.extend(["", f"{title}:"])
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- No detectado en la ficha disponible.")

    add_section("Centro o centros de suministro", preview.get("centros") or [])
    add_section("Detalle de lotes e importes", preview.get("lotes") or [])
    add_section("Criterios de adjudicación", preview.get("criterios_adjudicacion") or [])
    add_section("Criterios especiales de ejecución", preview.get("criterios_ejecucion") or [])
    lines.extend(["", "Resumen generado:", preview.get("resumen") or "", "", preview.get("nota") or ""])
    return "\n".join(lines).strip()
