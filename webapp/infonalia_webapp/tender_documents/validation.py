"""Focused validation rules for Ficha Llangon v2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from .payload import PAYLOAD_SCHEMA_VERSION, clean_text, normalize_payload


VALID_STATES = {"", "Sí", "No", "No consta", "No aplica", "Si"}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    field: str = ""


def _parse_date(value: object) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    return None


def _parse_time(value: object) -> time | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return None


def _is_url(value: object) -> bool:
    text = clean_text(value)
    if not text:
        return True
    parsed = urlparse(text)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    text = clean_text(value).replace("€", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def validate_payload(raw: dict[str, Any], *, today: date | None = None) -> list[ValidationIssue]:
    payload = normalize_payload(raw)
    control = payload["control"]
    recipient = payload["recipient"]
    tender = payload["tender"]
    analysis = payload["analysis"]
    today = today or date.today()
    issues: list[ValidationIssue] = []

    def add(severity: str, code: str, message: str, field: str = "") -> None:
        issues.append(ValidationIssue(severity, code, message, field))

    if clean_text(control.get("payload_schema_version")) != PAYLOAD_SCHEMA_VERSION:
        add("error", "schema_version", "La versión del payload no es compatible.", "control.payload_schema_version")
    for field, label in (
        ("client_display", "cliente"),
        ("expediente", "expediente"),
        ("objeto", "objeto o título"),
    ):
        source = recipient if field == "client_display" else tender
        if not clean_text(source.get(field)):
            add("error", f"required_{field}", f"Falta el {label}.", f"recipient.{field}" if source is recipient else f"tender.{field}")

    if recipient.get("client_id") in (None, "", 0, "0"):
        add("warning", "client_without_id", "El cliente no tiene un ID de la Suite; la ficha puede seguir usándose offline.", "recipient.client_id")
    if recipient.get("client_active") is False:
        add("warning", "inactive_client", "El cliente seleccionado figura como inactivo; se conserva el vínculo histórico.", "recipient.client_id")

    deadline = _parse_date(tender.get("fecha_limite"))
    if not clean_text(tender.get("fecha_limite")):
        add("error", "required_deadline", "Falta la fecha límite.", "tender.fecha_limite")
    elif deadline is None:
        add("error", "invalid_deadline", "La fecha límite no tiene un formato válido.", "tender.fecha_limite")
    else:
        if deadline < today:
            add("warning", "past_deadline", "La fecha límite ya ha vencido.", "tender.fecha_limite")
        elif deadline <= today + timedelta(days=3):
            add("warning", "near_deadline", "La fecha límite está a tres días o menos.", "tender.fecha_limite")
        if deadline.weekday() >= 5:
            add("warning", "weekend_deadline", "La fecha límite cae en fin de semana.", "tender.fecha_limite")
        years = {int(value) for value in payload["quality"].get("calendar_years", []) if str(value).isdigit()}
        if deadline.year not in years:
            add("warning", "holiday_coverage", f"El calendario de festivos no acredita cobertura para {deadline.year}.", "tender.fecha_limite")

    deadline_time = _parse_time(tender.get("hora_limite"))
    if clean_text(tender.get("hora_limite")) and deadline_time is None:
        add("error", "invalid_time", "La hora límite no tiene un formato válido.", "tender.hora_limite")
    elif deadline_time and deadline_time < time(12, 0):
        add("warning", "early_deadline", "La hora límite es anterior a las 12:00.", "tender.hora_limite")

    if not _is_url(tender.get("enlace")):
        add("error", "invalid_url", "El enlace de la licitación debe utilizar HTTP o HTTPS.", "tender.enlace")

    for field in ("presupuesto_base", "valor_estimado"):
        value = tender.get(field)
        if clean_text(value) and _decimal(value) is None:
            add("error", f"invalid_{field}", f"El valor de {field.replace('_', ' ')} no es numérico.", f"tender.{field}")

    dependencies = (
        ("prorroga", "prorroga_comentario", "Detalle la prórroga indicada."),
        ("garantia_provisional", "garantia_provisional_comentario", "Detalle la garantía provisional."),
        ("garantia_definitiva", "garantia_definitiva_comentario", "Detalle la garantía definitiva."),
        ("garantia_complementaria", "garantia_complementaria_comentario", "Detalle la garantía complementaria."),
        ("adscripcion_medios", "adscripcion_medios_comentario", "Detalle los medios exigidos."),
        ("fichas_tecnicas", "fichas_tecnicas_comentario", "Detalle las fichas técnicas exigidas."),
        ("memoria_tecnica", "memoria_tecnica_comentario", "Detalle la memoria técnica exigida."),
        ("subcontratacion", "subcontratacion_comentario", "Detalle las condiciones de subcontratación."),
        ("muestras", "muestras_comentario", "Detalle las muestras exigidas."),
    )
    for state_field, detail_field, message in dependencies:
        state = clean_text(analysis.get(state_field))
        if state not in VALID_STATES:
            add("error", f"invalid_state_{state_field}", "El estado debe ser Sí, No, No consta o No aplica.", f"analysis.{state_field}")
        if state.casefold() in {"sí", "si"} and not clean_text(analysis.get(detail_field)):
            add("warning", f"missing_detail_{state_field}", message, f"analysis.{detail_field}")

    points_total = Decimal("0")
    criterion_count = 0
    for group in ("criterios_juicio", "criterios_formula"):
        for index, item in enumerate(analysis.get(group, []), start=1):
            if not any(clean_text(value) for value in item.values()):
                continue
            criterion_count += 1
            if not clean_text(item.get("criterio")):
                add("error", "criterion_without_name", f"Hay un criterio sin nombre en {group}, fila {index}.", f"analysis.{group}")
            points = _decimal(item.get("puntos"))
            if clean_text(item.get("puntos")) and points is None:
                add("error", "invalid_points", f"La puntuación del criterio {index} no es numérica.", f"analysis.{group}")
            elif points is not None:
                if points < 0:
                    add("error", "negative_points", f"La puntuación del criterio {index} no puede ser negativa.", f"analysis.{group}")
                points_total += points
    if criterion_count == 0:
        add("info", "no_criteria", "No se han introducido criterios de adjudicación.", "analysis.criterios")
    elif points_total != Decimal("100"):
        add("warning", "criteria_total", f"La suma de puntos es {points_total}; revise si el total esperado es 100.", "analysis.criterios")

    observations = analysis.get("observaciones", [])
    if not any(clean_text(value) for value in observations if not isinstance(value, dict)):
        add("info", "no_observations", "No hay observaciones generales.", "analysis.observaciones")
    return issues


def issues_by_severity(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
    return {
        severity: [issue for issue in issues if issue.severity == severity]
        for severity in ("error", "warning", "info")
    }


__all__ = ("ValidationIssue", "issues_by_severity", "validate_payload")
