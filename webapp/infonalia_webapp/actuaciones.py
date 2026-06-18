from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any


ACTUACION_TIPOS = {
    "requerimiento",
    "subsanacion",
    "aclaracion",
    "documentacion_adicional",
    "justificacion_baja",
    "garantia_definitiva",
    "firma_contrato",
    "presentacion_oferta",
    "visita_tecnica",
    "apertura_mesa",
    "consulta_organo",
    "recurso_alegaciones",
    "revision_interna",
    "comunicacion_cliente",
    "seguimiento",
    "otro",
}

ACTUACION_ESTADOS_ABIERTOS = {"pendiente", "en_curso", "preparado", "preparada"}
ACTUACION_ESTADOS_CERRADOS = {"respondida", "cerrada", "enviado", "enviada", "cancelado", "cancelada"}
ACTUACION_ESTADOS = ACTUACION_ESTADOS_ABIERTOS | ACTUACION_ESTADOS_CERRADOS


def clean_value(value: object) -> str:
    return str(value or "").strip()


def bool_int(value: object, default: bool = True) -> int:
    if value is None:
        return 1 if default else 0
    if isinstance(value, bool):
        return 1 if value else 0
    text = clean_value(value).lower()
    if text in {"0", "false", "no", "off"}:
        return 0
    if text in {"1", "true", "yes", "si", "sí", "on"}:
        return 1
    return 1 if default else 0


def normalize_choice(value: object, allowed: set[str], default: str) -> str:
    text = clean_value(value).lower()
    return text if text in allowed else default


def normalize_deadline(value: object) -> str | None:
    text = clean_value(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Fecha límite no válida") from exc
    return parsed.replace(second=0, microsecond=0).isoformat()


def parse_datetime(value: object) -> datetime | None:
    text = clean_value(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_open_estado(estado: object) -> bool:
    return clean_value(estado).lower() in ACTUACION_ESTADOS_ABIERTOS


def visual_state(row: Any, *, now: datetime | None = None) -> str:
    current = now or datetime.now()
    estado = clean_value(row["estado"]).lower()
    deadline = parse_datetime(row["deadline_at"])
    closed_at = parse_datetime(row["closed_at"])
    if estado == "cerrada" and deadline and closed_at and closed_at > deadline:
        return "cerrada_fuera_de_plazo"
    if estado in ACTUACION_ESTADOS_CERRADOS:
        return estado
    if not deadline:
        return "sin_fecha"
    if deadline < current:
        return "vencida"
    if deadline.date() == current.date():
        return "vence_hoy"
    if deadline <= current + timedelta(days=7):
        return "vence_esta_semana"
    return "pendiente"


def actuacion_payload(
    data: dict[str, object],
    *,
    partial: bool = False,
    existing: Any | None = None,
    now: Callable[[], str],
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if not partial or "tipo" in data:
        payload["tipo"] = normalize_choice(data.get("tipo"), ACTUACION_TIPOS, "otro")
    if not partial or "titulo" in data:
        titulo = clean_value(data.get("titulo"))
        if not titulo:
            raise ValueError("El título de la actuación es obligatorio.")
        payload["titulo"] = titulo
    if not partial or "descripcion" in data:
        payload["descripcion"] = clean_value(data.get("descripcion"))
    if not partial or "estado" in data:
        payload["estado"] = normalize_choice(data.get("estado"), ACTUACION_ESTADOS, "pendiente")
    if not partial or "deadline_at" in data:
        payload["deadline_at"] = normalize_deadline(data.get("deadline_at"))
    if not partial or "recordatorio_email" in data:
        payload["recordatorio_email"] = bool_int(data.get("recordatorio_email"), default=True)
    if not partial or "origen" in data:
        payload["origen"] = clean_value(data.get("origen")) or "manual"
    estado = clean_value(payload.get("estado", existing["estado"] if existing else "pendiente")).lower()
    if estado in ACTUACION_ESTADOS_CERRADOS and existing and not existing["closed_at"]:
        timestamp = now()
        payload["closed_at"] = timestamp
    if estado in ACTUACION_ESTADOS_ABIERTOS:
        payload["closed_at"] = None
        payload["closed_by"] = None
    payload["updated_at"] = now()
    return payload


def actuacion_to_dict(
    row: Any,
    *,
    licitaciones: list[dict[str, object]] | None = None,
    historial: list[dict[str, object]] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    linked = licitaciones or []
    return {
        "id": row["id"],
        "tipo": row["tipo"],
        "titulo": row["titulo"],
        "descripcion": row["descripcion"] or "",
        "estado": row["estado"],
        "estado_visual": visual_state(row, now=now),
        "deadline_at": row["deadline_at"] or "",
        "recordatorio_email": bool(row["recordatorio_email"]),
        "origen": row["origen"],
        "created_by": row["created_by"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "closed_at": row["closed_at"] or "",
        "closed_by": row["closed_by"] or "",
        "licitaciones": linked,
        "licitaciones_count": len(linked),
        "historial": historial or [],
    }


def empty_summary() -> dict[str, int]:
    return {
        "vencidas": 0,
        "vencen_hoy": 0,
        "vencen_semana": 0,
        "sin_licitacion": 0,
        "total_abiertas": 0,
    }


def summarize_actuaciones(rows: list[Any], *, now: datetime | None = None) -> dict[str, int]:
    summary = empty_summary()
    for row in rows:
        if not is_open_estado(row["estado"]):
            continue
        summary["total_abiertas"] += 1
        linked_count = row["licitaciones_count"] if "licitaciones_count" in row.keys() else 0
        if not int(linked_count or 0):
            summary["sin_licitacion"] += 1
        state = visual_state(row, now=now)
        if state == "vencida":
            summary["vencidas"] += 1
        elif state == "vence_hoy":
            summary["vencen_hoy"] += 1
        elif state == "vence_esta_semana":
            summary["vencen_semana"] += 1
    return summary
