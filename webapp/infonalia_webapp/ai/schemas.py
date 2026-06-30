from __future__ import annotations

import copy
import json
from typing import Any

from .encoding_utils import contains_mojibake


SUMMARY_TEMPLATE: dict[str, Any] = {
    "metadata": {
        "expediente": "",
        "titulo": "",
        "organismo": "",
        "provincia": "",
        "plataforma": "",
        "enlace_licitacion": "",
        "fecha_limite_presentacion": "",
        "hora_limite_presentacion": "",
        "tipo_contrato": "",
        "regulacion_armonizada": None,
    },
    "resumen_ejecutivo": {"texto": "", "decision_preliminar": "", "aspectos_clave": []},
    "caracteristicas": {
        "presupuesto_base": None,
        "valor_estimado": None,
        "moneda": "EUR",
        "plazo_ejecucion_inicial": "",
        "fecha_inicio_prevista": "",
        "prorrogas": {"existen": None, "detalle": ""},
        "adjudicacion": "",
        "numero_sobres": None,
        "observaciones": "",
    },
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
    "presentacion_documentacion": {
        "numero_sobres": None,
        "forma_presentacion": "",
        "documentacion_administrativa": [],
        "documentacion_economica": [],
        "documentacion_tecnica": [],
        "anexos_relevantes": [],
        "observaciones": "",
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
        "muestras": {"exigidas": None, "momento": "", "detalle": "", "consecuencia_no_presentar": ""},
        "fichas_tecnicas": {"exigidas": None, "sobre": "", "detalle": ""},
        "memoria_tecnica": {"exigida": None, "detalle": ""},
        "adscripcion_medios": {"exigida": None, "detalle": ""},
    },
    "criterios_adjudicacion": {"juicio_valor": [], "formulas": [], "total_puntos": None, "observaciones": ""},
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
    "observaciones_operativas": {
        "habilitacion_profesional": "",
        "seguro_obligatorio": "",
        "lugar_entrega": [],
        "horario_entrega": [],
        "plazo_entrega": [],
        "periodicidad": "",
        "transporte": "",
        "descarga": "",
        "albaranes": "",
        "envases_etiquetado": "",
        "caducidad_consumo_preferente": "",
        "observaciones_producto": [],
    },
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
    "acciones_recomendadas": [],
    "preguntas_revisar": [],
    "referencias_historicas_no_analizadas": [],
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
    merged = _merge_template(SUMMARY_TEMPLATE, parsed)
    _normalize_legacy_sections(merged)
    return merged


def _normalize_legacy_sections(summary: dict[str, Any]) -> None:
    economic = summary.get("datos_economicos") if isinstance(summary.get("datos_economicos"), dict) else {}
    caracteristicas = summary.get("caracteristicas") if isinstance(summary.get("caracteristicas"), dict) else {}
    for key in ("presupuesto_base", "valor_estimado", "moneda"):
        if caracteristicas.get(key) in (None, "") and economic.get(key) not in (None, ""):
            caracteristicas[key] = economic.get(key)
    plazos = summary.get("plazos") if isinstance(summary.get("plazos"), dict) else {}
    if caracteristicas.get("plazo_ejecucion_inicial") == "" and plazos.get("plazo_ejecucion_inicial"):
        caracteristicas["plazo_ejecucion_inicial"] = plazos.get("plazo_ejecucion_inicial")
    if isinstance(plazos.get("prorrogas"), dict) and not caracteristicas.get("prorrogas", {}).get("detalle"):
        caracteristicas["prorrogas"] = plazos["prorrogas"]
    presentation = summary.get("presentacion") if isinstance(summary.get("presentacion"), dict) else {}
    presentation_doc = summary.get("presentacion_documentacion") if isinstance(summary.get("presentacion_documentacion"), dict) else {}
    for key in (
        "numero_sobres",
        "forma_presentacion",
        "documentacion_administrativa",
        "documentacion_economica",
        "documentacion_tecnica",
        "anexos_relevantes",
    ):
        if presentation_doc.get(key) in (None, "", []) and presentation.get(key) not in (None, "", []):
            presentation_doc[key] = presentation.get(key)
    criterios = summary.get("criterios_adjudicacion")
    if isinstance(criterios, list):
        summary["criterios_adjudicacion"] = {"juicio_valor": [], "formulas": criterios, "total_puntos": None, "observaciones": ""}
    logistics = summary.get("logistica_entrega") if isinstance(summary.get("logistica_entrega"), dict) else {}
    operations = summary.get("observaciones_operativas") if isinstance(summary.get("observaciones_operativas"), dict) else {}
    mapping = {
        "lugares_entrega": "lugar_entrega",
        "horarios_entrega": "horario_entrega",
        "plazos_entrega_desde_pedido": "plazo_entrega",
    }
    for old, new in mapping.items():
        if operations.get(new) in (None, "", []) and logistics.get(old) not in (None, "", []):
            operations[new] = logistics.get(old)
    for key in ("periodicidad", "transporte", "descarga", "albaranes", "observaciones_producto"):
        if operations.get(key) in (None, "", []) and logistics.get(key) not in (None, "", []):
            operations[key] = logistics.get(key)


def _non_empty_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def summary_quality_check(summary: dict[str, Any]) -> dict[str, Any]:
    metadata = summary.get("metadata") or {}
    executive = summary.get("resumen_ejecutivo") or {}
    caracteristicas = summary.get("caracteristicas") or {}
    economic = summary.get("datos_economicos") or {}
    presentation = summary.get("presentacion_documentacion") or summary.get("presentacion") or {}
    criterios = summary.get("criterios_adjudicacion") or {}
    operations = summary.get("observaciones_operativas") or {}
    solvencia = summary.get("solvencia") or {}
    signals: list[str] = []
    contains_bad_encoding = contains_mojibake(summary)
    json_len = len(json.dumps(summary, ensure_ascii=False))

    resumen_text = str(executive.get("texto") or "").strip()
    if resumen_text:
        signals.append("resumen_ejecutivo.texto")
    if _non_empty_text(metadata.get("titulo")):
        signals.append("metadata.titulo")
    if _non_empty_text(metadata.get("expediente")):
        signals.append("metadata.expediente")
    if economic.get("presupuesto_base") is not None or caracteristicas.get("presupuesto_base") is not None:
        signals.append("presupuesto_base")
    if economic.get("valor_estimado") is not None or caracteristicas.get("valor_estimado") is not None:
        signals.append("valor_estimado")
    if _non_empty_text(caracteristicas.get("plazo_ejecucion_inicial")):
        signals.append("caracteristicas.plazo_ejecucion_inicial")
    if _non_empty_list(summary.get("lotes")):
        signals.append("lotes")
    has_criterios = bool(_non_empty_list(criterios.get("juicio_valor")) or _non_empty_list(criterios.get("formulas"))) if isinstance(criterios, dict) else _non_empty_list(criterios)
    if has_criterios:
        signals.append("criterios_adjudicacion")
    if _non_empty_list(summary.get("alertas")):
        signals.append("alertas")
    if _non_empty_list(summary.get("acciones_recomendadas")):
        signals.append("acciones_recomendadas")
    for key in (
        "documentacion_administrativa",
        "documentacion_economica",
        "documentacion_tecnica",
        "anexos_relevantes",
    ):
        if _non_empty_list(presentation.get(key)):
            signals.append(f"presentacion.{key}")
    if _non_empty_list(solvencia.get("economica")) or _non_empty_list(solvencia.get("tecnica")):
        signals.append("solvencia")
    if _non_empty_list(summary.get("condiciones_especiales_ejecucion")):
        signals.append("condiciones_especiales_ejecucion")
    if any(_non_empty_text(operations.get(key)) or _non_empty_list(operations.get(key)) for key in operations):
        signals.append("observaciones_operativas")

    has_operational_blocks = len(
        {
            root
            for signal in signals
            for root in [signal.split(".")[0]]
            if root
            not in {
                "resumen_ejecutivo",
                "metadata",
            }
        }
    )
    if contains_bad_encoding:
        status = "encoding_error"
        useful = False
    elif json_len < 900 or (len(resumen_text) < 200 and has_operational_blocks < 2) or not signals:
        status = "low_quality_analysis" if signals else "empty_analysis"
        useful = False
    else:
        status = "ok"
        useful = True

    return {
        "status": status,
        "is_useful": useful,
        "signals": signals,
        "has_metadata": bool(metadata.get("expediente") or metadata.get("titulo")),
        "has_resumen": bool(resumen_text),
        "has_caracteristicas": any(caracteristicas.get(key) not in (None, "", []) for key in caracteristicas),
        "has_criterios": has_criterios,
        "has_lotes": _non_empty_list(summary.get("lotes")),
        "has_alertas": _non_empty_list(summary.get("alertas")),
        "has_acciones": _non_empty_list(summary.get("acciones_recomendadas")),
        "has_logistica": "observaciones_operativas" in signals,
        "has_documentacion": any(signal.startswith("presentacion.") for signal in signals),
        "has_solvencia": "solvencia" in signals,
        "has_condiciones": "condiciones_especiales_ejecucion" in signals,
        "contains_mojibake": contains_bad_encoding,
        "json_len": json_len,
    }


def summary_text(summary: dict[str, Any]) -> str:
    executive = summary.get("resumen_ejecutivo") or {}
    text = str(executive.get("texto") or "").strip()
    if text:
        return text
    title = str((summary.get("metadata") or {}).get("titulo") or "").strip()
    return title or "Análisis IA generado."
