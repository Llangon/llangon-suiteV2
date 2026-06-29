from __future__ import annotations

import copy
import json
from typing import Any


SUMMARY_TEMPLATE: dict[str, Any] = {
    "metadata": {
        "expediente": "",
        "titulo": "",
        "organismo": "",
        "plataforma": "",
        "enlace_licitacion": "",
        "fecha_limite_presentacion": "",
        "hora_limite_presentacion": "",
        "tipo_contrato": "",
        "regulacion_armonizada": None,
    },
    "resumen_ejecutivo": {"texto": "", "decision_preliminar": "", "aspectos_clave": []},
    "datos_economicos": {"presupuesto_base": None, "valor_estimado": None, "moneda": "EUR", "observaciones": ""},
    "plazos": {
        "plazo_ejecucion_inicial": "",
        "fecha_inicio_prevista": "",
        "fecha_fin_prevista": "",
        "prorrogas": {"existen": None, "detalle": ""},
    },
    "lotes": [],
    "garantias": {
        "garantia_provisional": {"exigida": None, "importe": None, "observaciones": "", "alerta": ""},
        "garantia_definitiva": {"exigida": None, "importe": None, "observaciones": ""},
        "garantia_complementaria": {"exigida": None, "observaciones": ""},
    },
    "presentacion": {
        "numero_sobres": None,
        "forma_presentacion": "",
        "documentacion_administrativa": [],
        "documentacion_economica": [],
        "documentacion_tecnica": [],
        "anexos_relevantes": [],
    },
    "muestras_fichas_memoria": {
        "muestras": {"exigidas": None, "detalle": ""},
        "fichas_tecnicas": {"exigidas": None, "detalle": ""},
        "memoria_tecnica": {"exigida": None, "detalle": ""},
        "adscripcion_medios": {"exigida": None, "detalle": ""},
    },
    "criterios_adjudicacion": [],
    "subcontratacion": {
        "permitida": None,
        "debe_declararse_en_oferta": None,
        "pago_directo_subcontratistas": None,
        "restricciones": "",
        "penalidades": "",
        "comentario_practico": "",
        "alerta": "",
    },
    "solvencia": {"economica": [], "tecnica": [], "observaciones": ""},
    "condiciones_especiales_ejecucion": [],
    "logistica_entrega": {
        "lugares_entrega": [],
        "horarios_entrega": [],
        "plazos_entrega_desde_pedido": [],
        "periodicidad": "",
        "transporte": "",
        "albaranes": "",
        "descarga": "",
        "observaciones_producto": [],
    },
    "alertas": [],
    "control_calidad": {"campos_no_encontrados": [], "campos_con_baja_confianza": [], "advertencias": []},
}


class AISchemaError(ValueError):
    pass


def _merge_template(template: Any, value: Any) -> Any:
    if isinstance(template, dict):
        merged = copy.deepcopy(template)
        if isinstance(value, dict):
            for key, item in value.items():
                merged[key] = _merge_template(template.get(key), item) if key in template else item
        return merged
    if isinstance(template, list):
        return value if isinstance(value, list) else []
    return value if value is not None else template


def parse_summary_json(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AISchemaError("Gemini no devolvio JSON valido.") from exc
    else:
        parsed = raw
    if not isinstance(parsed, dict):
        raise AISchemaError("La respuesta IA no tiene estructura de objeto JSON.")
    return _merge_template(SUMMARY_TEMPLATE, parsed)


def _non_empty_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def summary_quality_check(summary: dict[str, Any]) -> dict[str, Any]:
    metadata = summary.get("metadata") or {}
    executive = summary.get("resumen_ejecutivo") or {}
    economic = summary.get("datos_economicos") or {}
    presentation = summary.get("presentacion") or {}
    signals: list[str] = []

    if _non_empty_text(executive.get("texto")):
        signals.append("resumen_ejecutivo.texto")
    if _non_empty_text(metadata.get("titulo")):
        signals.append("metadata.titulo")
    if _non_empty_text(metadata.get("expediente")):
        signals.append("metadata.expediente")
    if economic.get("presupuesto_base") is not None:
        signals.append("datos_economicos.presupuesto_base")
    if _non_empty_list(summary.get("lotes")):
        signals.append("lotes")
    if _non_empty_list(summary.get("criterios_adjudicacion")):
        signals.append("criterios_adjudicacion")
    if _non_empty_list(summary.get("alertas")):
        signals.append("alertas")
    for key in (
        "documentacion_administrativa",
        "documentacion_economica",
        "documentacion_tecnica",
        "anexos_relevantes",
    ):
        if _non_empty_list(presentation.get(key)):
            signals.append(f"presentacion.{key}")

    return {
        "status": "ok" if signals else "empty_analysis",
        "is_useful": bool(signals),
        "signals": signals,
    }


def summary_text(summary: dict[str, Any]) -> str:
    executive = summary.get("resumen_ejecutivo") or {}
    text = str(executive.get("texto") or "").strip()
    if text:
        return text
    title = str((summary.get("metadata") or {}).get("titulo") or "").strip()
    return title or "Análisis IA generado."
