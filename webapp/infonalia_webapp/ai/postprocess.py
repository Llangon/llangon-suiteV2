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


def _contains_any(value: object, needles: tuple[str, ...]) -> bool:
    text = _text(value).lower()
    return any(needle in text for needle in needles)


def _has_meaningful_value(value: object) -> bool:
    if isinstance(value, dict):
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    return bool(_text(value))


def _append_unique(items: list[Any], item: dict[str, Any], keys: tuple[str, ...]) -> None:
    signature = tuple(_text(item.get(key)).lower() for key in keys)
    for existing in items:
        if not isinstance(existing, dict):
            continue
        if tuple(_text(existing.get(key)).lower() for key in keys) == signature:
            return
    items.append(item)


def _ensure_alert(summary: dict[str, Any], *, nivel: str, titulo: str, descripcion: str, accion: str = "") -> None:
    alerts = _as_list(summary.get("alertas"))
    summary["alertas"] = alerts
    _append_unique(
        alerts,
        {"nivel": nivel, "titulo": titulo, "descripcion": descripcion, "accion_recomendada": accion, "fuente": "postproceso"},
        ("titulo", "descripcion"),
    )


def _ensure_action(summary: dict[str, Any], *, prioridad: str, accion: str, motivo: str) -> None:
    actions = _as_list(summary.get("acciones_recomendadas"))
    summary["acciones_recomendadas"] = actions
    _append_unique(actions, {"prioridad": prioridad, "accion": accion, "motivo": motivo}, ("accion", "motivo"))


def _quality(summary: dict[str, Any]) -> dict[str, Any]:
    quality = _as_dict(summary.get("control_calidad"))
    quality.setdefault("campos_no_encontrados", [])
    quality.setdefault("campos_con_baja_confianza", [])
    quality.setdefault("advertencias", [])
    summary["control_calidad"] = quality
    return quality


def _add_warning(summary: dict[str, Any], message: str) -> None:
    warnings = _as_list(_quality(summary).get("advertencias"))
    _quality(summary)["advertencias"] = warnings
    if message not in warnings:
        warnings.append(message)


def postprocess_summary(summary: dict[str, Any]) -> dict[str, Any]:
    metadata = _as_dict(summary.get("metadata"))
    caracteristicas = _as_dict(summary.get("caracteristicas"))
    garantias = _as_dict(summary.get("garantias"))
    muestras = _as_dict(summary.get("muestras_fichas_memoria"))
    criterios = _as_dict(summary.get("criterios_adjudicacion"))
    presentacion = _as_dict(summary.get("presentacion_documentacion"))
    operaciones = _as_dict(summary.get("observaciones_operativas"))
    ejecutivo = _as_dict(summary.get("resumen_ejecutivo"))

    provisional = _as_dict(garantias.get("garantia_provisional"))
    definitiva = _as_dict(garantias.get("garantia_definitiva"))
    complementaria = _as_dict(garantias.get("garantia_complementaria"))
    if provisional.get("exigida") is True:
        _ensure_alert(summary, nivel="alta", titulo="Garantía provisional", descripcion="El pliego exige garantía provisional.", accion="Controlar su constitución antes de presentar oferta.")
        _ensure_action(summary, prioridad="alta", accion="Controlar garantía provisional.", motivo="Puede bloquear la presentación si no se aporta correctamente.")
    if definitiva.get("exigida") is True:
        _ensure_action(summary, prioridad="media", accion="Controlar constitución de garantía definitiva si resulta adjudicatario.", motivo="Obligación posterior a adjudicación.")
    if complementaria.get("exigida") is True:
        _ensure_alert(summary, nivel="media", titulo="Garantía complementaria", descripcion="El pliego menciona garantía complementaria.", accion="Revisar supuesto de aplicación.")

    samples = _as_dict(muestras.get("muestras"))
    fichas = _as_dict(muestras.get("fichas_tecnicas"))
    memoria = _as_dict(muestras.get("memoria_tecnica"))
    medios = _as_dict(muestras.get("adscripcion_medios"))
    if samples.get("exigidas") is True:
        _ensure_alert(summary, nivel="alta", titulo="Muestras obligatorias", descripcion=_text(samples.get("detalle")) or "El pliego exige presentación de muestras.", accion="Planificar muestras y etiquetado.")
        _ensure_action(summary, prioridad="alta", accion="Preparar y controlar la presentación de muestras.", motivo=_text(samples.get("consecuencia_no_presentar")) or "Puede afectar a la admisión o valoración.")
    if fichas.get("exigidas") is True:
        _ensure_alert(summary, nivel="media", titulo="Fichas técnicas", descripcion=_text(fichas.get("detalle")) or "Se solicitan fichas técnicas.", accion="Preparar fichas por producto/lote.")
        _ensure_action(summary, prioridad="media", accion="Preparar fichas técnicas exigidas.", motivo="Documentación técnica a controlar.")
    if memoria.get("exigida") is True:
        _ensure_alert(summary, nivel="media", titulo="Memoria técnica", descripcion=_text(memoria.get("detalle")) or "Se exige memoria técnica.", accion="Preparar memoria técnica.")
        _ensure_action(summary, prioridad="media", accion="Preparar memoria técnica.", motivo="Puede afectar a la valoración técnica.")
    if medios.get("exigida") is True:
        _ensure_alert(summary, nivel="media", titulo="Adscripción de medios", descripcion=_text(medios.get("detalle")) or "Se exige adscripción de medios.", accion="Comprobar medios exigidos.")

    platform = _text(metadata.get("plataforma"))
    if platform and "place" not in platform.lower() and "contrataciondelestado" not in platform.lower():
        _ensure_alert(summary, nivel="media", titulo="Plataforma no habitual", descripcion=f"Plataforma detectada: {platform}.", accion="Revisar requisitos de presentación en la plataforma.")
    hour = _text(metadata.get("hora_limite_presentacion"))
    if hour and not hour.startswith("23:59"):
        _ensure_alert(summary, nivel="baja", titulo="Hora límite no estándar", descripcion=f"Hora límite indicada: {hour}.", accion="Agendar vencimiento con margen.")

    criterios_list = _as_list(criterios.get("juicio_valor")) + _as_list(criterios.get("formulas"))
    total_points = criterios.get("total_puntos")
    resumen_text = " ".join([_text(ejecutivo.get("texto")), _text(criterios.get("observaciones"))]).lower()
    mentions_price_criteria = bool(re.search(r"(criterio|valoraci[oó]n).{0,40}(precio|econ[oó]mic)", resumen_text)) or "único criterio" in resumen_text
    if (mentions_price_criteria or total_points not in (None, "")) and not criterios_list:
        _add_warning(summary, "Inconsistencia: el resumen o el total de puntos menciona criterios, pero no hay criterios estructurados.")
        _ensure_action(summary, prioridad="media", accion="Revisar manualmente los criterios de adjudicación.", motivo="El análisis detecta posible incoherencia interna.")

    lotes = _as_list(summary.get("lotes"))
    summary["lotes"] = lotes
    adjudicacion = _text(caracteristicas.get("adjudicacion")).lower()
    if "lote" in adjudicacion and lotes:
        weak = _as_list(_quality(summary).get("campos_con_baja_confianza"))
        _quality(summary)["campos_con_baja_confianza"] = weak
        for lote in lotes:
            if isinstance(lote, dict) and not _text(lote.get("numero_lote")) and _text(lote.get("denominacion")):
                message = f"Número de lote no localizado para: {_text(lote.get('denominacion'))}"
                if message not in weak:
                    weak.append(message)

    joined_operational = " ".join(
        _text(value)
        for value in [
            caracteristicas.get("observaciones"),
            presentacion.get("observaciones"),
            operaciones.get("observaciones_producto"),
            operaciones.get("plazo_entrega"),
            operaciones.get("periodicidad"),
        ]
    )
    if _contains_any(joined_operational, ("precio máximo", "precios máximos", "precio unitario", "precios unitarios")):
        _ensure_alert(summary, nivel="media", titulo="Precios unitarios máximos", descripcion="Se mencionan precios máximos o unitarios.", accion="Controlar que ningún precio unitario supere el máximo del pliego.")
        _ensure_action(summary, prioridad="alta", accion="Controlar que ningún precio unitario supere el máximo del pliego.", motivo="Puede ser causa de exclusión o rechazo.")
    if _contains_any(joined_operational, ("todos los productos", "totalidad de productos", "ofertar todos")):
        _ensure_action(summary, prioridad="media", accion="Comprobar que se oferta la totalidad de productos del lote seleccionado.", motivo="El pliego puede exigir oferta completa.")
    if _contains_any(joined_operational, ("24 horas", "48 horas", "plazo corto", "urgente")):
        _ensure_alert(summary, nivel="media", titulo="Plazo de entrega ajustado", descripcion="Se ha detectado un plazo de entrega corto o exigente.", accion="Validar capacidad logística antes de ofertar.")

    actions = _as_list(summary.get("acciones_recomendadas"))
    alerts = _as_list(summary.get("alertas"))
    if not actions and not alerts:
        if any(_as_list(presentacion.get(key)) for key in ("documentacion_administrativa", "documentacion_tecnica", "documentacion_economica", "anexos_relevantes")):
            _ensure_action(summary, prioridad="media", accion="Revisar y preparar la documentación exigida por sobres/anexos.", motivo="Hay documentación estructurada que controlar.")
        if caracteristicas.get("presupuesto_base") not in (None, "") or caracteristicas.get("valor_estimado") not in (None, ""):
            _ensure_action(summary, prioridad="baja", accion="Comprobar importes y límites económicos antes de ofertar.", motivo="Hay datos económicos relevantes.")
        if _has_meaningful_value(operaciones):
            _ensure_action(summary, prioridad="media", accion="Revisar condiciones logísticas de entrega.", motivo="Hay observaciones operativas detectadas.")

    return summary
