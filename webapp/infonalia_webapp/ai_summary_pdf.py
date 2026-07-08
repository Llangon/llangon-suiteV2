from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from .dropbox_paths import resolve_licitacion_folder
    from .folder_names import safe_folder_name
    from .formatting import format_date_es, format_datetime_es
    from .normalization import clean_text
except ImportError:
    from dropbox_paths import resolve_licitacion_folder
    from folder_names import safe_folder_name
    from formatting import format_date_es, format_datetime_es
    from normalization import clean_text


LOGGER = logging.getLogger(__name__)
DEFAULT_FALLBACK_ROOT = Path(__file__).resolve().parent / "data" / "runtime" / "ai_summary_pdfs"
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
PAGE_MARGIN_X = 42.0
PAGE_MARGIN_TOP = 44.0
PAGE_MARGIN_BOTTOM = 42.0
CONTENT_WIDTH = PAGE_WIDTH - PAGE_MARGIN_X * 2

FONT_REGULAR = "F1"
FONT_BOLD = "F2"
COLOR_TEXT = (0.17, 0.20, 0.23)
COLOR_MUTED = (0.39, 0.43, 0.46)
COLOR_GREEN = (0.09, 0.37, 0.24)
COLOR_GREEN_SOFT = (0.945, 0.980, 0.953)
COLOR_GREEN_ROW = (0.965, 0.989, 0.971)
COLOR_ALERT = (0.996, 0.966, 0.910)
COLOR_BORDER = (0.80, 0.88, 0.83)
FONT_REGISTRY: tuple[str, str] | None = None

BROKEN_CHAR_REPLACEMENTS = {
    "\x80": "€",
    "\x95": "-",
    "": "€",
    "": "-",
    "Æ": "á",
    "Ø": "é",
    "œ": "ú",
    "æ": "ñ",
    "ð": "",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "\u00a0": " ",
}
JSONISH_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)
SPANISH_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€“", "â€”", "ðŸ", "�")
ORPHAN_ITEM_RE = re.compile(r"^(?:\d+|[IVXLCDM]+)\.?$", re.IGNORECASE)
ANNEX_ONLY_RE = re.compile(r"^anexo\s+[ivxlcdm]+[:.]?\s*$", re.IGNORECASE)


def _register_pdf_fonts() -> tuple[str, str]:
    global FONT_REGISTRY
    if FONT_REGISTRY:
        return FONT_REGISTRY

    fonts_dir = Path((Path.home().anchor or "C:\\") + "Windows\\Fonts")
    candidates = [
        ("Calibri", Path(fonts_dir) / "calibri.ttf", Path(fonts_dir) / "calibrib.ttf"),
        ("Arial", Path(fonts_dir) / "arial.ttf", Path(fonts_dir) / "arialbd.ttf"),
        ("SegoeUI", Path(fonts_dir) / "segoeui.ttf", Path(fonts_dir) / "segoeuib.ttf"),
        ("Verdana", Path(fonts_dir) / "verdana.ttf", Path(fonts_dir) / "verdanab.ttf"),
    ]
    for family, regular_path, bold_path in candidates:
        if not regular_path.exists() or not bold_path.exists():
            continue
        regular_name = f"{family}-Regular"
        bold_name = f"{family}-Bold"
        if regular_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
        if bold_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
        FONT_REGISTRY = (regular_name, bold_name)
        return FONT_REGISTRY
    FONT_REGISTRY = ("Helvetica", "Helvetica-Bold")
    return FONT_REGISTRY


@dataclass(frozen=True)
class PdfGenerationResult:
    ok: bool
    path: str
    filename: str
    used_fallback: bool
    warning: str
    error: str


@dataclass(frozen=True)
class _ReportSection:
    title: str
    items: list[str]
    style: str = "bullets"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _row_get(row: Any, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return ""


def _repair_utf8_latin1_mojibake(text: str) -> str:
    if not text or not any(marker in text for marker in SPANISH_MOJIBAKE_MARKERS):
        return text
    for source_encoding in ("latin-1", "cp1252"):
        try:
            repaired = text.encode(source_encoding, errors="strict").decode("utf-8", errors="strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired:
            return repaired
    return text


def clean_pdf_text(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = _repair_utf8_latin1_mojibake(text)
    for bad, good in BROKEN_CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def _format_money(value: object) -> str:
    if value in (None, ""):
        return "No consta"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return clean_pdf_text(value) or "No consta"
    return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_platform(value: object) -> str:
    text = clean_pdf_text(value)
    if not text:
        return "No consta"
    if text.upper() == "PLACE":
        return "PLACSP"
    return text


def _format_tipo(value: object) -> str:
    text = clean_pdf_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+", text):
        return ""
    return text


def _as_list(values: object) -> list[object]:
    if values is None:
        return []
    if isinstance(values, list):
        return values
    if isinstance(values, tuple):
        return list(values)
    return [values]


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = clean_pdf_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _clean_orphan_items(items: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = clean_pdf_text(item)
        if not text:
            continue
        if ORPHAN_ITEM_RE.fullmatch(text):
            continue
        if ANNEX_ONLY_RE.fullmatch(text):
            continue
        cleaned.append(text)
    return cleaned


def _limit_items(items: Sequence[str], maximum: int) -> list[str]:
    return list(items[:maximum])


def _merge_sentences(base: str, extra: str) -> str:
    base = clean_pdf_text(base).rstrip(". ")
    extra = clean_pdf_text(extra).rstrip(". ")
    if not base:
        return extra
    if not extra:
        return base
    if extra[:1].islower():
        return f"{base} {extra}."
    return f"{base}. {extra}."


def _normalize_action_text(text: str) -> str:
    text = clean_pdf_text(text)
    if not text:
        return ""
    replacements = (
        ("Preparar y controlar la presentación de muestras", "Preparar y controlar las muestras exigidas"),
        ("Preparar fichas técnicas exigidas", "Preparar las fichas técnicas e informes exigidos"),
        ("Documentación técnica a controlar", "Controlar la documentación técnica exigida antes de la presentación o ejecución"),
    )
    for source, target in replacements:
        if text.lower() == source.lower():
            return target
    return text


def _merge_action_reason_items(items: Sequence[str]) -> list[str]:
    merged: list[str] = []
    reason_starts = (
        "puede ",
        "podría ",
        "riesgo ",
        "documentación ",
        "no en ",
        "antes del ",
        "solo si ",
        "mejor oferta ",
        "puede ser ",
    )
    for raw in items:
        text = _normalize_action_text(raw)
        if not text:
            continue
        lower = text.lower()
        if merged and any(lower.startswith(prefix) for prefix in reason_starts):
            merged[-1] = _merge_sentences(merged[-1], text)
            continue
        if merged and lower in merged[-1].lower():
            continue
        merged.append(text)
    return _dedupe(_clean_orphan_items(merged))


def _merge_observation_items(items: Sequence[str]) -> list[str]:
    merged: list[str] = []
    suffix_starts = (
        "antes del ",
        "no en el ",
        "puede impedir ",
        "incluido en el ",
        "solo si ",
    )
    for raw in items:
        text = clean_pdf_text(raw)
        if not text:
            continue
        lower = text.lower()
        if merged and any(lower.startswith(prefix) for prefix in suffix_starts):
            merged[-1] = _merge_sentences(merged[-1], text)
            continue
        if "criterios de juicio de valor" in lower or "memoria técnica de oferta" in lower:
            continue
        merged.append(text)
    return _dedupe(_clean_orphan_items(merged))


def _map_annex_label(text: str) -> str:
    normalized = clean_pdf_text(text)
    lower = normalized.lower()
    mappings = {
        "anexo ii": "DRU / Anexo II.",
        "anexo iii": "Declaración de confidencialidad, solo si procede.",
        "anexo iv": "Compromiso UTE, solo si procede.",
        "anexo v": "Proposición económica / Anexo V, una por lote.",
        "anexo vi": "Declaración sobre datos del Registro de Licitadores, si procede.",
        "anexo vii": "Oposición a consulta de datos de identidad, solo si procede.",
        "anexo viii": "Declaración de incompatibilidad.",
        "anexo ix": "Autorización para cesión de información tributaria y Seguridad Social.",
        "anexo x": "Certificación de personas trabajadoras con discapacidad, si procede.",
        "anexo xi": "Declaración responsable de protección de menores, si procede.",
        "anexo xii": "Declaración sobre servidores o tratamiento de datos, si procede.",
        "anexo xiii": "Acuerdo de confidencialidad para formalización, si procede.",
    }
    for key, value in mappings.items():
        if lower.startswith(key):
            return value
    return normalized


def _group_documents_by_phase(items: Sequence[str]) -> list[str]:
    groups: dict[str, list[str]] = {
        "Documentación para presentar la oferta": [],
        "Documentación para mejor oferta / adjudicación": [],
        "Documentación para ejecución": [],
    }
    for raw in items:
        text = _map_annex_label(raw)
        if not text:
            continue
        lower = text.lower()
        if "pliego" in lower:
            continue
        if any(token in lower for token in ("certific", "adjudic", "registro de licitadores", "personalidad", "poder", "tribut", "seguridad social", "iae", "discapacidad", "plan de igualdad", "mejor oferta", "incompatibilidad", "datos de identidad", "servidores")):
            groups["Documentación para mejor oferta / adjudicación"].append(text)
        elif any(token in lower for token in ("muestra", "imprenta", "arte final", "albar", "medioambiental", "envasado", "informe", "etiquet", "ejecución")):
            groups["Documentación para ejecución"].append(text)
        elif any(token in lower for token in ("dru", "proposición económica", "confidencialidad", "ute", "sobre único", "oferta ")):
            groups["Documentación para presentar la oferta"].append(text)
        else:
            groups["Documentación para presentar la oferta"].append(text)
    result: list[str] = []
    for title, values in groups.items():
        cleaned = _dedupe(_clean_orphan_items(values))
        if not cleaned:
            continue
        result.append(f"## {title}")
        result.extend(cleaned)
    return result


def _human_lines(value: object, *, label: str = "", suppress_meta: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        title = clean_pdf_text(
            value.get("titulo")
            or value.get("nombre")
            or value.get("criterio")
            or value.get("objeto")
            or value.get("categoria")
            or value.get("accion")
            or value.get("detalle")
        )
        description_parts: list[str] = []
        for key in (
            "descripcion",
            "detalle",
            "observaciones",
            "motivo",
            "formula",
            "obligacion",
            "accion_recomendada",
            "sobre",
            "momento",
            "consecuencia_no_presentar",
        ):
            text = clean_pdf_text(value.get(key))
            if text and text != title and text not in description_parts:
                description_parts.append(text)
        for key, prefix in (
            ("puntuacion_maxima", "Puntuación máxima"),
            ("ponderacion", "Ponderación"),
            ("importe_minimo", "Importe mínimo"),
            ("riesgo", "Riesgo"),
        ):
            raw = value.get(key)
            text = clean_pdf_text(raw)
            if text:
                description_parts.append(f"{prefix}: {text}")
        if "existen" in value and not description_parts:
            detail = clean_pdf_text(value.get("detalle"))
            if detail:
                return [detail]
            return ["Sí"] if bool(value.get("existen")) else ["No"]
        lines: list[str] = []
        if title and title not in {"postproceso"}:
            lines.append(title)
        for part in description_parts:
            if part not in lines and part.lower() != "postproceso":
                lines.append(part)
        if not lines:
            useful_keys = []
            for key, raw in value.items():
                if suppress_meta and key in {
                    "nivel",
                    "prioridad",
                    "fuente",
                    "existen",
                    "titulo",
                    "descripcion",
                    "accion_recomendada",
                    "accion",
                    "motivo",
                    "detalle",
                    "nombre",
                    "criterio",
                    "objeto",
                    "categoria",
                }:
                    continue
                if isinstance(raw, (dict, list, tuple, set)):
                    useful_keys.extend(_human_lines(raw, label="", suppress_meta=suppress_meta))
                    continue
                text = clean_pdf_text(raw)
                if text:
                    useful_keys.append(text)
            lines.extend(useful_keys)
        return _dedupe(lines)
    if isinstance(value, (list, tuple, set)):
        lines: list[str] = []
        for item in value:
            lines.extend(_human_lines(item, label=label, suppress_meta=suppress_meta))
        return _dedupe(lines)
    text = clean_pdf_text(value)
    if not text:
        return []
    if JSONISH_RE.match(text):
        return []
    return [f"{label}: {text}" if label else text]


def _selected_document_names(selected_documents: Sequence[dict[str, object]] | object) -> list[str]:
    items: list[str] = []
    if not isinstance(selected_documents, Sequence) or isinstance(selected_documents, (str, bytes, bytearray)):
        return items
    for document in selected_documents:
        if not isinstance(document, dict):
            continue
        text = clean_pdf_text(document.get("name") or document.get("relative_path") or document.get("path"))
        if text and text not in items:
            items.append(text)
    return items


def _criteria_items(values: object) -> list[str]:
    if isinstance(values, dict):
        items: list[str] = []
        for block_name in ("juicio_valor", "formulas", "otros"):
            items.extend(_criteria_items(values.get(block_name)))
        observaciones = clean_pdf_text(values.get("observaciones"))
        total = clean_pdf_text(values.get("total_puntos"))
        if observaciones:
            items.append(observaciones)
        if total:
            items.append(f"Total puntos: {total}")
        return _dedupe(items)
    lines: list[str] = []
    for item in _as_list(values):
        if isinstance(item, dict):
            nombre = clean_pdf_text(item.get("nombre") or item.get("criterio"))
            descripcion = clean_pdf_text(item.get("descripcion") or item.get("detalle"))
            formula = clean_pdf_text(item.get("formula"))
            puntos = clean_pdf_text(item.get("puntuacion_maxima") or item.get("ponderacion"))
            parts = [part for part in (nombre, descripcion, formula) if part]
            text = " - ".join(parts[:2]) if parts else ""
            if len(parts) > 2:
                text = f"{text} - {parts[2]}" if text else parts[2]
            if puntos:
                text = f"{text} ({puntos} puntos)" if text else f"{puntos} puntos"
            if text:
                lines.append(text)
        else:
            lines.extend(_human_lines(item))
    return _dedupe(lines)


def _solvencia_items(values: object, *, prefix: str) -> list[str]:
    items: list[str] = []
    for item in _as_list(values):
        if isinstance(item, dict):
            objeto = clean_pdf_text(item.get("objeto"))
            detalle = clean_pdf_text(item.get("detalle"))
            importe = clean_pdf_text(item.get("importe_minimo"))
            parts = [part for part in (objeto, detalle) if part]
            text = " - ".join(parts) if parts else ""
            if importe:
                text = f"{text}. Importe mínimo: {importe}" if text else f"Importe mínimo: {importe}"
            if text:
                items.append(f"{prefix}: {text}")
        else:
            for line in _human_lines(item):
                items.append(f"{prefix}: {line}")
    return _dedupe(items)


def _operational_items(summary: dict[str, Any]) -> list[str]:
    items: list[str] = []
    observaciones = summary.get("observaciones_operativas") if isinstance(summary.get("observaciones_operativas"), dict) else {}
    muestras = summary.get("muestras_fichas_memoria") if isinstance(summary.get("muestras_fichas_memoria"), dict) else {}
    caracteristicas = summary.get("caracteristicas") if isinstance(summary.get("caracteristicas"), dict) else {}
    condiciones = summary.get("condiciones_especiales_ejecucion")
    for key in ("lugar_entrega", "horario_entrega", "plazo_entrega"):
        items.extend(_human_lines(observaciones.get(key)))
    for key in ("transporte",):
        text = clean_pdf_text(observaciones.get(key))
        if text:
            items.append(text)
    for key in ("muestras", "fichas_tecnicas", "memoria_tecnica"):
        items.extend(_human_lines(muestras.get(key)))
    if isinstance(caracteristicas.get("prorrogas"), dict):
        items.extend(_human_lines(caracteristicas.get("prorrogas")))
    items.extend(_human_lines(condiciones))
    return _limit_items(_merge_observation_items(items), 8)


def _build_key_aspects(summary: dict[str, Any]) -> list[str]:
    ejecutivo = summary.get("resumen_ejecutivo") if isinstance(summary.get("resumen_ejecutivo"), dict) else {}
    items = _human_lines(ejecutivo.get("aspectos_clave"))
    return _dedupe(_clean_orphan_items(items))


def _build_actions(summary: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    for item in _as_list(summary.get("acciones_recomendadas")):
        if isinstance(item, dict):
            action = clean_pdf_text(item.get("accion"))
            motivo = clean_pdf_text(item.get("motivo"))
            if action and motivo:
                actions.append(_merge_sentences(action, motivo))
            elif action:
                actions.append(action)
            else:
                actions.extend(_human_lines(item))
        else:
            actions.extend(_human_lines(item))
    for alert in _as_list(summary.get("alertas")):
        if not isinstance(alert, dict):
            continue
        action = clean_pdf_text(alert.get("accion_recomendada"))
        descripcion = clean_pdf_text(alert.get("descripcion"))
        if action and descripcion:
            actions.append(_merge_sentences(action, descripcion))
        elif action:
            actions.append(action)
    return _limit_items(_merge_action_reason_items(actions), 10)


def _summary_text(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    if isinstance(value, dict):
        return clean_pdf_text(value.get("texto") or value.get("detalle"))
    return clean_pdf_text(value)


def _build_header_pairs(licitacion: Any, summary: dict[str, Any], generated_at: str) -> list[tuple[str, str]]:
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    caracteristicas = summary.get("caracteristicas") if isinstance(summary.get("caracteristicas"), dict) else {}
    fecha_limite = " ".join(
        part for part in (format_date_es(_row_get(licitacion, "fecha_limite")), clean_pdf_text(_row_get(licitacion, "hora_limite"))) if part
    ).strip() or "No consta"
    ruta_carpeta = clean_pdf_text(_row_get(licitacion, "ruta_carpeta")) or "No consta"
    plataforma = _format_platform(_row_get(licitacion, "plataforma") or metadata.get("plataforma"))
    tipo = _format_tipo(_row_get(licitacion, "tipo") or metadata.get("tipo_contrato"))
    rows = [
        ("Expediente", clean_pdf_text(_row_get(licitacion, "expediente")) or clean_pdf_text(metadata.get("expediente")) or "Sin expediente"),
        ("Organismo", clean_pdf_text(_row_get(licitacion, "organismo")) or clean_pdf_text(metadata.get("organismo")) or "No consta"),
        ("Provincia", clean_pdf_text(_row_get(licitacion, "provincia")) or clean_pdf_text(metadata.get("provincia")) or "No consta"),
        ("Objeto", clean_pdf_text(_row_get(licitacion, "objeto")) or clean_pdf_text(metadata.get("titulo")) or "Sin descripción"),
        ("Fecha límite", fecha_limite),
        ("Presupuesto", _format_money(_row_get(licitacion, "presupuesto") or caracteristicas.get("presupuesto_base"))),
        ("Plataforma", plataforma),
        ("Estado", clean_pdf_text(_row_get(licitacion, "estado")) or "No consta"),
        ("Carpeta", ruta_carpeta),
        ("Fecha de generación", format_datetime_es(generated_at) or format_datetime_es(_now().isoformat())),
    ]
    if tipo:
        rows.insert(5, ("Tipo", tipo))
    return rows


def _build_sections(
    licitacion: Any,
    summary: dict[str, Any],
    *,
    selected_documents: Sequence[dict[str, object]] | None = None,
) -> list[_ReportSection]:
    ejecutivo = summary.get("resumen_ejecutivo") if isinstance(summary.get("resumen_ejecutivo"), dict) else {}
    presentation = summary.get("presentacion_documentacion") if isinstance(summary.get("presentacion_documentacion"), dict) else {}
    if not presentation:
        presentation = summary.get("presentacion") if isinstance(summary.get("presentacion"), dict) else {}
    plazos = summary.get("plazos") if isinstance(summary.get("plazos"), dict) else {}
    solvencia = summary.get("solvencia") if isinstance(summary.get("solvencia"), dict) else {}
    key_aspects = _build_key_aspects(summary)

    resumen_lines = [
        clean_pdf_text(ejecutivo.get("texto")) or _summary_text(summary, "summary_text") or "Sin resumen ejecutivo disponible.",
        *[
            f"Decisión preliminar: {line}"
            for line in _human_lines(ejecutivo.get("decision_preliminar"))
        ],
    ]
    alertas = _human_lines(summary.get("alertas")) or ["Sin alertas destacadas."]
    acciones = _build_actions(summary) or ["Sin acciones recomendadas destacadas."]
    criterios = _criteria_items(summary.get("criterios_adjudicacion")) or ["No localizados en el análisis."]
    documentacion_raw = _dedupe(
        [
            *_human_lines(presentation.get("documentacion_administrativa")),
            *_human_lines(presentation.get("documentacion_tecnica")),
            *_human_lines(presentation.get("documentacion_economica")),
            *_human_lines(presentation.get("anexos_relevantes")),
            *_selected_document_names(selected_documents or []),
        ]
    )
    documentacion = _group_documents_by_phase(documentacion_raw) or ["No consta documentación destacada."]
    requisitos = _dedupe(
        [
            *_solvencia_items(solvencia.get("economica"), prefix="Solvencia económica"),
            *_solvencia_items(solvencia.get("tecnica"), prefix="Solvencia técnica"),
            *_human_lines(solvencia.get("observaciones")),
            *_human_lines(plazos.get("prorrogas")),
        ]
    ) or ["No constan requisitos de solvencia destacados."]
    observaciones = _operational_items(summary) or ["Sin observaciones finales destacadas."]

    sections = [
        _ReportSection("Resumen ejecutivo", _dedupe(resumen_lines), "paragraphs"),
        _ReportSection("Alertas y puntos críticos", alertas, "alerts"),
        _ReportSection("Acciones recomendadas", acciones, "checklist"),
        _ReportSection("Criterios de adjudicación", criterios, "bullets"),
        _ReportSection("Documentación a preparar o revisar", documentacion, "grouped_bullets"),
        _ReportSection("Solvencia y requisitos", requisitos, "bullets"),
        _ReportSection("Observaciones finales", observaciones, "bullets"),
    ]
    if key_aspects:
        sections.insert(1, _ReportSection("Aspectos clave", key_aspects, "bullets"))
    return sections


def _pdf_escape(value: object) -> str:
    text = clean_pdf_text(value)
    encoded = text.encode("cp1252", errors="replace")
    interim = encoded.decode("latin-1")
    return interim.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _approx_width(text: str, font_size: float) -> float:
    units = 0.0
    for char in text:
        if char in "WMÁÉÍÓÚÜÑwm@#%&":
            units += 0.92
        elif char in "iltI.,:;!|'` ":
            units += 0.30 if char != " " else 0.32
        else:
            units += 0.56
    return units * font_size


def _wrap_text(text: str, font_size: float, max_width: float) -> list[str]:
    source = " ".join(clean_pdf_text(text).split())
    if not source:
        return [""]
    words = source.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}".strip()
        if _approx_width(candidate, font_size) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [source]


class _PdfLayout:
    def __init__(self, *, expediente: str, generated_at: str) -> None:
        self.pages: list[list[str]] = []
        self.page_number = 0
        self.y = 0.0
        self.expediente = clean_pdf_text(expediente) or "Sin expediente"
        self.generated_at = generated_at
        self._new_page(first_page=True)

    def _new_page(self, *, first_page: bool = False) -> None:
        self.pages.append([])
        self.page_number += 1
        self.y = PAGE_HEIGHT - PAGE_MARGIN_TOP
        header_height = 64 if first_page else 34
        self._rect(PAGE_MARGIN_X, PAGE_HEIGHT - PAGE_MARGIN_TOP - header_height + 8, CONTENT_WIDTH, header_height, fill=COLOR_GREEN_SOFT)
        if first_page:
            self._text("Asesores Llangón, S.L.", PAGE_MARGIN_X + 16, PAGE_HEIGHT - 53, font=FONT_BOLD, size=12.5, color=COLOR_GREEN)
            self._text("Informe resumen de licitación", PAGE_MARGIN_X + 16, PAGE_HEIGHT - 71, font=FONT_BOLD, size=18, color=COLOR_TEXT)
            self._text("Generado por Llangón Suite", PAGE_MARGIN_X + 16, PAGE_HEIGHT - 87, size=9.5, color=COLOR_MUTED)
            self._text(self.expediente, PAGE_MARGIN_X + CONTENT_WIDTH - 132, PAGE_HEIGHT - 71, font=FONT_BOLD, size=11, color=COLOR_GREEN)
            self._text(format_datetime_es(self.generated_at), PAGE_MARGIN_X + CONTENT_WIDTH - 132, PAGE_HEIGHT - 87, size=8.8, color=COLOR_MUTED)
            self.y = PAGE_HEIGHT - 118
        else:
            self._text("Informe resumen de licitación", PAGE_MARGIN_X + 12, PAGE_HEIGHT - 60, font=FONT_BOLD, size=11.5, color=COLOR_TEXT)
            self._text(self.expediente, PAGE_MARGIN_X + CONTENT_WIDTH - 180, PAGE_HEIGHT - 60, size=9.2, color=COLOR_MUTED)
            self.y = PAGE_HEIGHT - 86

    def _page(self) -> list[str]:
        return self.pages[-1]

    def _rect(self, x: float, y: float, w: float, h: float, *, fill: tuple[float, float, float]) -> None:
        r, g, b = fill
        self._page().append(f"q {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f Q")

    def _stroke_rect(self, x: float, y: float, w: float, h: float, *, color: tuple[float, float, float], line_width: float = 0.8) -> None:
        r, g, b = color
        self._page().append(f"q {line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S Q")

    def _line(self, x1: float, y1: float, x2: float, y2: float, *, color: tuple[float, float, float], line_width: float = 0.9) -> None:
        r, g, b = color
        self._page().append(f"q {line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q")

    def _text(
        self,
        text: str,
        x: float,
        y: float,
        *,
        font: str = FONT_REGULAR,
        size: float = 10.0,
        color: tuple[float, float, float] = COLOR_TEXT,
    ) -> None:
        r, g, b = color
        self._page().append(
            f"BT /{font} {size:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({_pdf_escape(text)}) Tj ET"
        )

    def _space(self, amount: float) -> None:
        self.y -= amount

    def ensure_space(self, amount: float) -> None:
        if self.y - amount < PAGE_MARGIN_BOTTOM:
            self._new_page()

    def section_title(self, text: str) -> None:
        self.ensure_space(26)
        self._text(text, PAGE_MARGIN_X, self.y, font=FONT_BOLD, size=12.7, color=COLOR_GREEN)
        self._line(PAGE_MARGIN_X, self.y - 4, PAGE_MARGIN_X + CONTENT_WIDTH, self.y - 4, color=COLOR_BORDER)
        self._space(18)

    def paragraph(self, text: str, *, size: float = 10.0, color: tuple[float, float, float] = COLOR_TEXT, indent: float = 0.0) -> None:
        lines = _wrap_text(text, size, CONTENT_WIDTH - indent)
        for line in lines:
            self.ensure_space(size + 5)
            self._text(line, PAGE_MARGIN_X + indent, self.y, size=size, color=color)
            self._space(size + 3.6)

    def bullet_item(self, text: str, *, bullet: str = "-") -> None:
        size = 9.9
        bullet_width = 12.0
        lines = _wrap_text(text, size, CONTENT_WIDTH - bullet_width)
        for index, line in enumerate(lines):
            self.ensure_space(size + 5)
            if index == 0:
                self._text(bullet, PAGE_MARGIN_X, self.y, font=FONT_BOLD, size=size, color=COLOR_GREEN)
            self._text(line, PAGE_MARGIN_X + bullet_width, self.y, size=size, color=COLOR_TEXT)
            self._space(size + 3.4)

    def checklist_item(self, text: str) -> None:
        self.bullet_item(text, bullet="[ ]")

    def alert_item(self, lines: Sequence[str]) -> None:
        cleaned = [clean_pdf_text(line) for line in lines if clean_pdf_text(line)]
        if not cleaned:
            return
        wrapped_lines: list[tuple[str, bool]] = []
        for index, line in enumerate(cleaned):
            for sub_index, wrapped in enumerate(_wrap_text(line, 9.7, CONTENT_WIDTH - 24)):
                wrapped_lines.append((wrapped, index == 0 and sub_index == 0))
        height = 16 + len(wrapped_lines) * 13.4
        self.ensure_space(height + 4)
        box_y = self.y - height + 8
        self._rect(PAGE_MARGIN_X, box_y, CONTENT_WIDTH, height, fill=COLOR_ALERT)
        self._stroke_rect(PAGE_MARGIN_X, box_y, CONTENT_WIDTH, height, color=(0.84, 0.74, 0.55))
        cursor_y = self.y - 10
        for line, is_title in wrapped_lines:
            self._text(line, PAGE_MARGIN_X + 12, cursor_y, font=FONT_BOLD if is_title else FONT_REGULAR, size=9.7, color=COLOR_TEXT)
            cursor_y -= 13.0
        self.y -= height + 5

    def key_value_table(self, pairs: Sequence[tuple[str, str]]) -> None:
        cell_width = (CONTENT_WIDTH - 12) / 2
        row_gap = 8.0
        left_x = PAGE_MARGIN_X
        right_x = PAGE_MARGIN_X + cell_width + 12
        for index in range(0, len(pairs), 2):
            left = pairs[index]
            right = pairs[index + 1] if index + 1 < len(pairs) else ("", "")
            left_lines = _wrap_text(left[1], 9.6, cell_width - 16)
            right_lines = _wrap_text(right[1], 9.6, cell_width - 16) if right[0] else [""]
            row_height = max(38, 18 + max(len(left_lines), len(right_lines)) * 12.4)
            self.ensure_space(row_height + row_gap)
            top = self.y
            for x, label, value_lines in (
                (left_x, left[0], left_lines),
                (right_x, right[0], right_lines),
            ):
                if not label:
                    continue
                box_y = top - row_height + 6
                self._rect(x, box_y, cell_width, row_height, fill=COLOR_GREEN_ROW)
                self._stroke_rect(x, box_y, cell_width, row_height, color=COLOR_BORDER)
                self._text(label, x + 8, top - 12, font=FONT_BOLD, size=8.3, color=COLOR_GREEN)
                line_y = top - 24
                for line in value_lines:
                    self._text(line, x + 8, line_y, size=9.6, color=COLOR_TEXT)
                    line_y -= 11.8
            self.y -= row_height + row_gap

    def footer_note(self, text: str) -> None:
        lines = _wrap_text(text, 8.8, CONTENT_WIDTH - 20)
        height = 16 + len(lines) * 12.4
        self.ensure_space(height + 6)
        box_y = self.y - height + 7
        self._rect(PAGE_MARGIN_X, box_y, CONTENT_WIDTH, height, fill=COLOR_GREEN_SOFT)
        self._stroke_rect(PAGE_MARGIN_X, box_y, CONTENT_WIDTH, height, color=COLOR_BORDER)
        line_y = self.y - 10
        for line in lines:
            self._text(line, PAGE_MARGIN_X + 10, line_y, size=8.8, color=COLOR_MUTED)
            line_y -= 11.6
        self.y -= height + 6

    def stamp_page_numbers(self) -> None:
        total = len(self.pages)
        for index, page in enumerate(self.pages, start=1):
            page.append(
                f"BT /{FONT_REGULAR} 8.20 Tf {COLOR_MUTED[0]:.3f} {COLOR_MUTED[1]:.3f} {COLOR_MUTED[2]:.3f} rg "
                f"1 0 0 1 {PAGE_WIDTH - PAGE_MARGIN_X - 54:.2f} 18.00 Tm ({_pdf_escape(f'Página {index} de {total}')}) Tj ET"
            )


def _build_pdf_bytes(
    licitacion: Any,
    summary: dict[str, Any],
    *,
    selected_documents: Sequence[dict[str, object]] | None = None,
    generated_at: str = "",
) -> bytes:
    generated_label = generated_at or _now().isoformat()
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    expediente = clean_pdf_text(_row_get(licitacion, "expediente")) or clean_pdf_text(metadata.get("expediente")) or "Sin expediente"
    regular_font, bold_font = _register_pdf_fonts()

    palette = {
        "text": colors.Color(*COLOR_TEXT),
        "muted": colors.Color(*COLOR_MUTED),
        "green": colors.Color(*COLOR_GREEN),
        "soft": colors.Color(*COLOR_GREEN_SOFT),
        "row": colors.Color(*COLOR_GREEN_ROW),
        "alert": colors.Color(*COLOR_ALERT),
        "border": colors.Color(*COLOR_BORDER),
    }

    stylesheet = getSampleStyleSheet()
    styles = {
        "body": ParagraphStyle(
            "SummaryBody",
            parent=stylesheet["BodyText"],
            fontName=regular_font,
            fontSize=10,
            leading=13.2,
            textColor=palette["text"],
            spaceAfter=0,
        ),
        "section": ParagraphStyle(
            "SummarySection",
            parent=stylesheet["Heading2"],
            fontName=bold_font,
            fontSize=12.8,
            leading=15,
            textColor=palette["green"],
            spaceBefore=8,
            spaceAfter=8,
        ),
        "label": ParagraphStyle(
            "SummaryLabel",
            parent=stylesheet["BodyText"],
            fontName=bold_font,
            fontSize=8.2,
            leading=10,
            textColor=palette["green"],
            spaceAfter=2,
            uppercase=True,
        ),
        "value": ParagraphStyle(
            "SummaryValue",
            parent=stylesheet["BodyText"],
            fontName=regular_font,
            fontSize=9.5,
            leading=12.0,
            textColor=palette["text"],
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "SummarySmall",
            parent=stylesheet["BodyText"],
            fontName=regular_font,
            fontSize=8.7,
            leading=11.0,
            textColor=palette["muted"],
        ),
        "alert_title": ParagraphStyle(
            "SummaryAlertTitle",
            parent=stylesheet["BodyText"],
            fontName=bold_font,
            fontSize=10,
            leading=12.5,
            textColor=palette["text"],
        ),
        "check": ParagraphStyle(
            "SummaryCheck",
            parent=stylesheet["BodyText"],
            fontName=regular_font,
            fontSize=9.7,
            leading=12.6,
            leftIndent=16,
            firstLineIndent=-12,
            textColor=palette["text"],
        ),
    }

    def _html(text: object) -> str:
        safe = clean_pdf_text(text)
        safe = safe.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return safe.replace("\n", "<br/>")

    def _section_heading(text: str) -> Paragraph:
        return Paragraph(_html(text), styles["section"])

    story: list[object] = []

    story.append(_section_heading("Datos principales"))
    pairs = _build_header_pairs(licitacion, summary, generated_label)
    table_rows: list[list[object]] = []
    for index in range(0, len(pairs), 2):
        left = pairs[index]
        right = pairs[index + 1] if index + 1 < len(pairs) else ("", "")
        left_cell = [
            Paragraph(_html(left[0]), styles["label"]),
            Spacer(1, 2),
            Paragraph(_html(left[1]), styles["value"]),
        ]
        right_cell = [
            Paragraph(_html(right[0]), styles["label"]),
            Spacer(1, 2),
            Paragraph(_html(right[1]), styles["value"]),
        ] if right[0] else [Paragraph("", styles["value"])]
        table_rows.append([left_cell, right_cell])
    header_table = Table(table_rows, colWidths=[(CONTENT_WIDTH - 12) / 2, (CONTENT_WIDTH - 12) / 2], hAlign="LEFT")
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["row"]),
                ("BOX", (0, 0), (-1, -1), 0.8, palette["border"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, palette["border"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([header_table, Spacer(1, 10)])

    for section in _build_sections(licitacion, summary, selected_documents=selected_documents):
        story.append(_section_heading(section.title))
        if section.style == "paragraphs":
            for item in section.items:
                story.append(Paragraph(_html(item), styles["body"]))
                story.append(Spacer(1, 6))
        elif section.style == "grouped_bullets":
            for item in section.items:
                if item.startswith("## "):
                    story.append(Paragraph(_html(item[3:]), styles["label"]))
                    story.append(Spacer(1, 3))
                    continue
                story.append(Paragraph(_html(f"- {item}"), styles["check"]))
                story.append(Spacer(1, 4))
        elif section.style == "alerts":
            grouped: list[list[str]] = []
            current: list[str] = []
            for item in section.items:
                if current and len(current) >= 3:
                    grouped.append(current)
                    current = []
                current.append(item)
            if current:
                grouped.append(current)
            for block in grouped:
                content: list[object] = []
                for index, item in enumerate(block):
                    style = styles["alert_title"] if index == 0 else styles["body"]
                    content.append(Paragraph(_html(item), style))
                    if index < len(block) - 1:
                        content.append(Spacer(1, 4))
                alert_table = Table([[content]], colWidths=[CONTENT_WIDTH], hAlign="LEFT")
                alert_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), palette["alert"]),
                            ("BOX", (0, 0), (-1, -1), 0.8, colors.Color(0.84, 0.74, 0.55)),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.extend([alert_table, Spacer(1, 8)])
        elif section.style == "checklist":
            for item in section.items:
                story.append(Paragraph(_html(f"[ ] {item}"), styles["check"]))
                story.append(Spacer(1, 4))
        else:
            for item in section.items:
                story.append(Paragraph(_html(f"- {item}"), styles["check"]))
                story.append(Spacer(1, 4))
        story.append(Spacer(1, 2))

    footer_table = Table(
        [[Paragraph(_html("Documento generado automáticamente por Llangón Suite. Revisar siempre contra los pliegos y documentos oficiales antes de usarlo con clientes."), styles["small"])]],
        colWidths=[CONTENT_WIDTH],
        hAlign="LEFT",
    )
    footer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["soft"]),
                ("BOX", (0, 0), (-1, -1), 0.8, palette["border"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(Spacer(1, 6))
    story.append(footer_table)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_X,
        rightMargin=PAGE_MARGIN_X,
        topMargin=104,
        bottomMargin=42,
        title=f"Informe resumen de licitación - {expediente}",
        author="Llangón Suite",
        subject="Informe resumen de licitación",
    )

    def _draw_header(canvas, document, first_page: bool) -> None:
        canvas.saveState()
        canvas.setFillColor(palette["soft"])
        if first_page:
            canvas.rect(PAGE_MARGIN_X, A4[1] - 92, CONTENT_WIDTH, 58, fill=1, stroke=0)
            canvas.setFillColor(palette["green"])
            canvas.setFont(bold_font, 12.5)
            canvas.drawString(PAGE_MARGIN_X + 14, A4[1] - 52, "Asesores Llangón, S.L.")
            canvas.setFillColor(palette["text"])
            canvas.setFont(bold_font, 18)
            canvas.drawString(PAGE_MARGIN_X + 14, A4[1] - 69, "Informe resumen de licitación")
            canvas.setFillColor(palette["muted"])
            canvas.setFont(regular_font, 9.2)
            canvas.drawString(PAGE_MARGIN_X + 14, A4[1] - 83, "Generado por Llangón Suite")
            canvas.setFillColor(palette["green"])
            canvas.setFont(bold_font, 10.5)
            canvas.drawRightString(PAGE_MARGIN_X + CONTENT_WIDTH - 12, A4[1] - 68, expediente)
            canvas.setFillColor(palette["muted"])
            canvas.setFont(regular_font, 8.6)
            canvas.drawRightString(PAGE_MARGIN_X + CONTENT_WIDTH - 12, A4[1] - 82, format_datetime_es(generated_label))
        else:
            canvas.rect(PAGE_MARGIN_X, A4[1] - 58, CONTENT_WIDTH, 26, fill=1, stroke=0)
            canvas.setFillColor(palette["text"])
            canvas.setFont(bold_font, 11.2)
            canvas.drawString(PAGE_MARGIN_X + 10, A4[1] - 47, "Informe resumen de licitación")
            canvas.setFillColor(palette["muted"])
            canvas.setFont(regular_font, 8.4)
            canvas.drawRightString(PAGE_MARGIN_X + CONTENT_WIDTH - 10, A4[1] - 47, expediente)
        canvas.setFillColor(palette["muted"])
        canvas.setFont(regular_font, 8.3)
        canvas.drawRightString(A4[0] - PAGE_MARGIN_X, 20, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=lambda canvas, document: _draw_header(canvas, document, True),
        onLaterPages=lambda canvas, document: _draw_header(canvas, document, False),
    )
    return buffer.getvalue()


def _target_directory(licitacion: Any, fallback_root: Path) -> tuple[Path, bool, str]:
    resolution = resolve_licitacion_folder(licitacion)
    if resolution.ok and resolution.exists and resolution.path and resolution.inside_dropbox_base:
        folder = Path(resolution.path)
        if folder.is_dir():
            return folder, False, ""
    target = fallback_root / f"licitacion_{clean_pdf_text(_row_get(licitacion, 'id')) or 'sin_id'}"
    warning = "La carpeta física de la licitación no es válida. El PDF se ha guardado en la carpeta segura de runtime."
    return target, True, warning


def _build_filename(licitacion: Any) -> str:
    expediente = clean_pdf_text(_row_get(licitacion, "expediente")) or f"licitacion_{clean_pdf_text(_row_get(licitacion, 'id')) or 'sin_id'}"
    return safe_folder_name(f"Informe resumen IA - {expediente}") + ".pdf"


def _next_available_path(directory: Path, filename: str, *, timestamp: datetime) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix or ".pdf"
    stamped = directory / f"{stem}_{timestamp.strftime('%Y%m%d_%H%M%S')}{suffix}"
    if not stamped.exists():
        return stamped
    counter = 2
    while True:
        versioned = directory / f"{stem}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{counter}{suffix}"
        if not versioned.exists():
            return versioned
        counter += 1


def generate_ai_summary_pdf(
    licitacion: Any,
    summary: dict[str, Any] | str,
    *,
    selected_documents: Sequence[dict[str, object]] | None = None,
    generated_at: str = "",
    fallback_root: Path | None = None,
) -> PdfGenerationResult:
    fallback = (fallback_root or DEFAULT_FALLBACK_ROOT).resolve(strict=False)
    now = _now()
    try:
        parsed_summary = json.loads(summary) if isinstance(summary, str) else summary
        if not isinstance(parsed_summary, dict):
            raise ValueError("El resumen IA no tiene formato válido.")
        target_dir, used_fallback, warning = _target_directory(licitacion, fallback)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = _next_available_path(target_dir, _build_filename(licitacion), timestamp=now)
        file_path.write_bytes(
            _build_pdf_bytes(
                licitacion,
                parsed_summary,
                selected_documents=selected_documents,
                generated_at=generated_at or now.isoformat(),
            )
        )
        if used_fallback:
            LOGGER.warning(
                "PDF IA guardado en fallback licitacion_id=%s path=%s",
                clean_pdf_text(_row_get(licitacion, "id")) or "?",
                file_path,
            )
        else:
            LOGGER.info(
                "PDF IA guardado en carpeta de licitacion licitacion_id=%s path=%s",
                clean_pdf_text(_row_get(licitacion, "id")) or "?",
                file_path,
            )
        return PdfGenerationResult(
            ok=True,
            path=str(file_path),
            filename=file_path.name,
            used_fallback=used_fallback,
            warning=warning,
            error="",
        )
    except Exception as exc:
        LOGGER.exception("No se pudo generar el PDF del resumen IA licitacion_id=%s", clean_pdf_text(_row_get(licitacion, "id")) or "?")
        return PdfGenerationResult(
            ok=False,
            path="",
            filename="",
            used_fallback=False,
            warning="",
            error=clean_pdf_text(exc) or "No se pudo generar el PDF del resumen IA.",
        )
