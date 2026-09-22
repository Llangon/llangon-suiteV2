"""Versioned, deliberately small payload for Ficha Llangon v2."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PAYLOAD_SCHEMA_VERSION = "1.1"
TEMPLATE_VERSION = "2.1.0"
TEMPLATE_ID = "ficha_llangon"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split()).strip()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _text_items(value: object) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value in (None, ""):
        values = []
    else:
        values = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [text for item in values if (text := clean_text(item))]


def normalize_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a stable payload without inventing procurement facts."""

    source = copy.deepcopy(raw or {})
    control = _mapping(source.get("control"))
    recipient = _mapping(source.get("recipient"))
    tender = _mapping(source.get("tender"))
    analysis = _mapping(source.get("analysis"))
    quality = _mapping(source.get("quality"))

    control.setdefault("template_id", TEMPLATE_ID)
    control.setdefault("template_version", TEMPLATE_VERSION)
    control.setdefault("payload_schema_version", PAYLOAD_SCHEMA_VERSION)
    control.setdefault("document_id", "")
    control.setdefault("created_at", "")
    control.setdefault("source", "manual")
    control.setdefault("last_import_at", "")
    control.setdefault("last_clients_sync_at", "")
    control.setdefault("confidentiality_notice", "")

    recipient.setdefault("client_id", None)
    recipient.setdefault("client_display", "")
    recipient.setdefault("razon_social_snapshot", "")
    recipient.setdefault("client_active", True)

    for field in (
        "licitacion_id",
        "expediente",
        "objeto",
        "fecha_limite",
        "hora_limite",
        "enlace",
        "organismo",
        "plataforma",
        "tipo_contrato",
        "procedimiento",
        "regulacion_armonizada",
        "presupuesto_base",
        "valor_estimado",
    ):
        tender.setdefault(field, "")
    tender["lotes"] = _items(tender.get("lotes"))

    scalar_analysis = (
        "plazo",
        "plazo_comentario",
        "prorroga",
        "prorroga_comentario",
        "forma_adjudicacion",
        "garantia_provisional",
        "garantia_provisional_comentario",
        "garantia_definitiva",
        "garantia_definitiva_comentario",
        "garantia_complementaria",
        "garantia_complementaria_comentario",
        "adscripcion_medios",
        "adscripcion_medios_comentario",
        "numero_sobres",
        "fichas_tecnicas",
        "fichas_tecnicas_comentario",
        "memoria_tecnica",
        "memoria_tecnica_comentario",
        "subcontratacion",
        "subcontratacion_comentario",
        "muestras",
        "muestras_momento",
        "muestras_comentario",
    )
    for field in scalar_analysis:
        analysis.setdefault(field, "")
    analysis["criterios_juicio"] = _items(analysis.get("criterios_juicio"))
    analysis["criterios_formula"] = _items(analysis.get("criterios_formula"))
    analysis["condiciones_especiales"] = _items(analysis.get("condiciones_especiales"))
    analysis["observaciones"] = _text_items(analysis.get("observaciones"))

    quality.setdefault("calendar_years", [])
    quality.setdefault("draft", False)

    return {
        "control": control,
        "recipient": recipient,
        "tender": tender,
        "analysis": analysis,
        "quality": quality,
    }


def load_payload(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("El payload debe ser un objeto JSON.")
    return normalize_payload(data)


def write_payload(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(normalize_payload(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def iso_now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


__all__ = (
    "PAYLOAD_SCHEMA_VERSION",
    "TEMPLATE_ID",
    "TEMPLATE_VERSION",
    "clean_text",
    "iso_now",
    "load_payload",
    "normalize_payload",
    "write_payload",
)
