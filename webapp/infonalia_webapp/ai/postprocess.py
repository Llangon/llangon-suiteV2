from __future__ import annotations

import re
from typing import Any


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text(value: object) -> str:
    return str(value or "").strip()


def _quality(summary: dict[str, Any]) -> dict[str, Any]:
    quality = _as_dict(summary.get("control_calidad"))
    quality.setdefault("campos_no_encontrados", [])
    quality.setdefault("campos_con_baja_confianza", [])
    quality.setdefault("advertencias", [])
    summary["control_calidad"] = quality
    return quality


def _add_warning(summary: dict[str, Any], message: str) -> None:
    quality = _quality(summary)
    warnings = _as_list(quality.get("advertencias"))
    quality["advertencias"] = warnings
    if message not in warnings:
        warnings.append(message)


def _point_from_legacy_alert(value: object) -> dict[str, str] | None:
    if isinstance(value, dict):
        title = _text(value.get("titulo") or value.get("nombre"))
        detail = _text(value.get("descripcion") or value.get("detalle") or value.get("observaciones"))
        source = _text(value.get("fuente"))
    else:
        title = _text(value)
        detail = ""
        source = ""
    if not title and not detail:
        return None
    return {"titulo": title or "Información relevante", "detalle": detail, "fuente": source}


def _normalize_points(summary: dict[str, Any]) -> None:
    candidates = [*_as_list(summary.get("puntos_atencion")), *_as_list(summary.pop("alertas", []))]
    points: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        point = _point_from_legacy_alert(candidate)
        if not point:
            continue
        signature = (point["titulo"].lower(), point["detalle"].lower())
        if signature in seen:
            continue
        seen.add(signature)
        points.append(point)
    summary["puntos_atencion"] = points


def _strip_recommendations(summary: dict[str, Any]) -> None:
    executive = _as_dict(summary.get("resumen_ejecutivo"))
    executive.pop("decision_preliminar", None)
    summary["resumen_ejecutivo"] = executive
    summary.pop("acciones_recomendadas", None)
    summary.pop("preguntas_revisar", None)

    guarantees = _as_dict(summary.get("garantias"))
    provisional = _as_dict(guarantees.get("garantia_provisional"))
    legacy_alert = _text(provisional.pop("alerta", None))
    if legacy_alert and not _text(provisional.get("observaciones")):
        provisional["observaciones"] = legacy_alert

    subcontracting = _as_dict(summary.get("subcontratacion"))
    legacy_comment = subcontracting.pop("comentario_practico", None)
    legacy_alert = subcontracting.pop("alerta", None)
    legacy_observation = _text(legacy_comment or legacy_alert)
    if legacy_observation and not _text(subcontracting.get("observaciones")):
        subcontracting["observaciones"] = legacy_observation


def postprocess_summary(summary: dict[str, Any]) -> dict[str, Any]:
    _strip_recommendations(summary)
    _normalize_points(summary)
    _quality(summary)

    summary["lotes"] = _as_list(summary.get("lotes"))
    summary["productos"] = _as_list(summary.get("productos"))
    summary["fuentes_consultadas"] = _as_list(summary.get("fuentes_consultadas"))

    criteria = _as_dict(summary.get("criterios_adjudicacion"))
    executive = _as_dict(summary.get("resumen_ejecutivo"))
    criteria_items = _as_list(criteria.get("juicio_valor")) + _as_list(criteria.get("formulas"))
    total_points = criteria.get("total_puntos")
    summary_text = " ".join([_text(executive.get("texto")), _text(criteria.get("observaciones"))]).lower()
    mentions_price_criteria = bool(re.search(r"(criterio|valoraci[oó]n).{0,40}(precio|econ[oó]mic)", summary_text)) or "único criterio" in summary_text
    if (mentions_price_criteria or total_points not in (None, "")) and not criteria_items:
        _add_warning(summary, "Inconsistencia: el resumen o el total de puntos menciona criterios, pero no hay criterios estructurados.")

    weak_fields = _as_list(_quality(summary).get("campos_con_baja_confianza"))
    _quality(summary)["campos_con_baja_confianza"] = weak_fields
    for lot in summary["lotes"]:
        if not isinstance(lot, dict):
            continue
        if not _text(lot.get("numero_lote")) and _text(lot.get("denominacion")):
            message = f"Número de lote no localizado para: {_text(lot.get('denominacion'))}"
            if message not in weak_fields:
                weak_fields.append(message)

    return summary
