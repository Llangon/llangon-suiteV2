"""Decimal-safe DTO conversion without reproducing economic formulae."""

from __future__ import annotations

import copy
import re
import uuid
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from ..calculations import calculate_justification, canonical_decimal, economic_payload
from ..domain import (
    CostOrigin,
    CostRange,
    DomainValueError,
    FinancialInput,
    Justification,
    Product,
    TransportInput,
)
from ..imports import ProductImportError, parse_decimal


DRAFT_SCHEMA_VERSION = "1"
MAX_TEXT_LENGTH = 20_000
MAX_PRODUCTS = 5_000


def initial_draft(
    *,
    licitacion: Mapping[str, Any],
    cliente: Mapping[str, Any],
    lote_numero: str,
    lote_nombre: str = "",
    declared_offer: object = "0",
    proposals: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an editable local snapshot; master records are never referenced later."""

    proposed = dict(proposals or {})
    offer = _decimal_text(declared_offer, "declared_offer")
    representative = _text(cliente.get("representante_nombre") or cliente.get("representante"))
    client_name = _text(cliente.get("razon_social") or cliente.get("nombre_comercial"))
    address = _join_nonempty(
        cliente.get("domicilio_fiscal"),
        cliente.get("codigo_postal"),
        cliente.get("municipio"),
        cliente.get("provincia"),
    )
    return {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "identification": {
            "expediente": _text(licitacion.get("expediente")),
            "organismo": _text(licitacion.get("organismo")),
            "objeto": _text(licitacion.get("objeto")),
            "lot_number": _text(lote_numero) or "1",
            "lot_name": _text(lote_nombre),
            "duration_description": "",
            "place": _text(cliente.get("municipio")),
            "date_text": "",
        },
        "client": {
            "client_id": cliente.get("id"),
            "name": client_name,
            "nif": _text(cliente.get("nif_cif")),
            "address": address,
            "phone": _text(cliente.get("telefono_principal")),
            "email": _text(cliente.get("email_principal")),
            "representative": representative,
            "representative_dni": _text(
                cliente.get("representante_nif") or cliente.get("representante_dni")
            ),
            "role": _text(cliente.get("representante_cargo")),
            "signatory": representative,
        },
        "cost_range": {
            "minimum_percentage": _integer(proposed.get("minimum_percentage", 40), "minimum_percentage"),
            "maximum_percentage": _integer(proposed.get("maximum_percentage", 47), "maximum_percentage"),
        },
        "transport": {
            "operational_weeks": _integer(proposed.get("operational_weeks", 0), "operational_weeks"),
            "weekly_deliveries": _integer(proposed.get("weekly_deliveries", 0), "weekly_deliveries"),
            "circular_kilometres": _decimal_text(proposed.get("circular_kilometres", "0"), "circular_kilometres"),
            "effective_decimal_hours": _decimal_text(proposed.get("effective_decimal_hours", "0"), "effective_decimal_hours"),
            "kilometre_rate": _decimal_text(proposed.get("kilometre_rate", "0"), "kilometre_rate"),
            "hourly_rate": _decimal_text(proposed.get("hourly_rate", "0"), "hourly_rate"),
            "contract_stops": _integer(proposed.get("contract_stops", 1), "contract_stops"),
            "shared_orders": _integer(proposed.get("shared_orders", 15), "shared_orders"),
            "descriptive_months": None,
            "route_duration_text": "",
        },
        "financial": {
            "declared_lot_offer": offer,
            "general_expense_base": _decimal_text(proposed.get("general_expense_base", offer), "general_expense_base"),
            "general_expense_percentage": _decimal_text(proposed.get("general_expense_percentage", "0.10"), "general_expense_percentage"),
            "indirect_costs": None,
        },
        "transport_document": {
            "observatory": "Observatorio de Costes del Transporte de Mercancías por Carretera",
            "observatory_date": "",
            "observatory_url": "",
            "vehicle": "Vehículo rígido de 2 ejes de distribución",
        },
        "products": [],
        "narrative": {
            "subject": "Justificación de oferta anormalmente baja",
            "exposition": "",
            "arguments": [],
            "acquisition_text": "",
            "transport_text": "",
            "structure_text": "",
            "conclusion": "",
            "estimated_draft_notice": "BORRADOR ESTIMATIVO PENDIENTE DE VALIDACIÓN DEL CLIENTE",
            "confidentiality_text": "Documento confidencial para uso exclusivo en el procedimiento indicado.",
            "pending_validation_fields": ["costes unitarios", "medios y circunstancias empresariales"],
        },
        "route_image": None,
        "accepted_warning_codes": [],
        "source": {
            "defaults_are_proposals": True,
            "product_import": None,
        },
    }


def normalise_draft(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the closed, canonical draft shape accepted by persistence."""

    if not isinstance(value, Mapping):
        raise DomainValueError("borrador_invalido", "draft", "El borrador debe ser un objeto.")
    draft = copy.deepcopy(dict(value))
    if draft.get("schema_version", DRAFT_SCHEMA_VERSION) != DRAFT_SCHEMA_VERSION:
        raise DomainValueError("borrador_incompatible", "schema_version", "La versión del borrador no es compatible.")
    identification = _mapping(draft, "identification")
    client = _mapping(draft, "client")
    cost_range = _mapping(draft, "cost_range")
    transport = _mapping(draft, "transport")
    financial = _mapping(draft, "financial")
    transport_document = _mapping(draft, "transport_document")
    narrative = _mapping(draft, "narrative")
    raw_products = draft.get("products", [])
    if not isinstance(raw_products, list) or len(raw_products) > MAX_PRODUCTS:
        raise DomainValueError("productos_invalidos", "products", "La lista de productos no es válida.")

    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_products, start=1):
        if not isinstance(raw, Mapping):
            raise DomainValueError("producto_invalido", "products", "Cada producto debe ser un objeto.")
        line_id = _text(raw.get("line_id")) or f"manual-{uuid.uuid4().hex}"
        if line_id in seen:
            raise DomainValueError("producto_id_duplicado", "line_id", "El identificador de línea está duplicado.")
        seen.add(line_id)
        generated = _optional_decimal_text(raw.get("generated_unit_cost"), "generated_unit_cost")
        manual = _optional_decimal_text(raw.get("manual_unit_cost"), "manual_unit_cost")
        origin = _text(raw.get("cost_origin")) or (
            CostOrigin.MANUAL.value if manual is not None else CostOrigin.GENERATED.value if generated is not None else CostOrigin.UNGENERATED.value
        )
        if origin not in {item.value for item in CostOrigin}:
            raise DomainValueError("origen_coste_invalido", "cost_origin", "El origen del coste no es válido.")
        applied_percentage = raw.get("applied_percentage")
        products.append(
            {
                "line_id": line_id[:160],
                "name": _limited_text(raw.get("name"), "name", 1_000),
                "characteristics": _limited_text(raw.get("characteristics"), "characteristics", 4_000),
                "quantity": _decimal_text(raw.get("quantity", "0"), f"products[{index}].quantity"),
                "offered_unit_price": _decimal_text(raw.get("offered_unit_price", "0"), f"products[{index}].offered_unit_price"),
                "offered_amount_input": _optional_decimal_text(raw.get("offered_amount_input"), "offered_amount_input"),
                "applied_percentage": None if applied_percentage is None else _integer(applied_percentage, "applied_percentage"),
                "applied_factor": _optional_decimal_text(raw.get("applied_factor"), "applied_factor"),
                "generated_unit_cost": generated,
                "manual_unit_cost": manual,
                "locked": _boolean(raw.get("locked", False), "locked"),
                "cost_origin": origin,
                "source_row": raw.get("source_row"),
            }
        )

    return {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "identification": {
            key: _limited_text(identification.get(key), key)
            for key in ("expediente", "organismo", "objeto", "lot_number", "lot_name", "duration_description", "place", "date_text")
        },
        "client": {
            "client_id": client.get("client_id"),
            **{
                key: _limited_text(client.get(key), key)
                for key in ("name", "nif", "address", "phone", "email", "representative", "representative_dni", "role", "signatory")
            },
        },
        "cost_range": {
            "minimum_percentage": _integer(cost_range.get("minimum_percentage", 0), "minimum_percentage"),
            "maximum_percentage": _integer(cost_range.get("maximum_percentage", 0), "maximum_percentage"),
        },
        "transport": {
            "operational_weeks": _integer(transport.get("operational_weeks", 0), "operational_weeks"),
            "weekly_deliveries": _integer(transport.get("weekly_deliveries", 0), "weekly_deliveries"),
            "circular_kilometres": _decimal_text(transport.get("circular_kilometres", "0"), "circular_kilometres"),
            "effective_decimal_hours": _decimal_text(transport.get("effective_decimal_hours", "0"), "effective_decimal_hours"),
            "kilometre_rate": _decimal_text(transport.get("kilometre_rate", "0"), "kilometre_rate"),
            "hourly_rate": _decimal_text(transport.get("hourly_rate", "0"), "hourly_rate"),
            "contract_stops": _integer(transport.get("contract_stops", 0), "contract_stops"),
            "shared_orders": _integer(transport.get("shared_orders", 1), "shared_orders"),
            "descriptive_months": None if transport.get("descriptive_months") in (None, "") else _integer(transport.get("descriptive_months"), "descriptive_months"),
            "route_duration_text": _limited_text(transport.get("route_duration_text"), "route_duration_text"),
        },
        "financial": {
            "declared_lot_offer": _decimal_text(financial.get("declared_lot_offer", "0"), "declared_lot_offer"),
            "general_expense_base": _decimal_text(financial.get("general_expense_base", "0"), "general_expense_base"),
            "general_expense_percentage": _decimal_text(financial.get("general_expense_percentage", "0"), "general_expense_percentage"),
            "indirect_costs": _optional_decimal_text(financial.get("indirect_costs"), "indirect_costs"),
        },
        "transport_document": {
            key: _limited_text(transport_document.get(key), key)
            for key in ("observatory", "observatory_date", "observatory_url", "vehicle")
        },
        "products": products,
        "narrative": {
            "subject": _limited_text(narrative.get("subject"), "subject"),
            "exposition": _limited_text(narrative.get("exposition"), "exposition"),
            "arguments": _text_list(narrative.get("arguments"), "arguments"),
            "acquisition_text": _limited_text(narrative.get("acquisition_text"), "acquisition_text"),
            "transport_text": _limited_text(narrative.get("transport_text"), "transport_text"),
            "structure_text": _limited_text(narrative.get("structure_text"), "structure_text"),
            "conclusion": _limited_text(narrative.get("conclusion"), "conclusion"),
            "estimated_draft_notice": _limited_text(narrative.get("estimated_draft_notice"), "estimated_draft_notice"),
            "confidentiality_text": _limited_text(narrative.get("confidentiality_text"), "confidentiality_text"),
            "pending_validation_fields": _text_list(narrative.get("pending_validation_fields"), "pending_validation_fields"),
        },
        "route_image": _route_image(draft.get("route_image")),
        "accepted_warning_codes": _text_list(draft.get("accepted_warning_codes"), "accepted_warning_codes", maximum=500),
        "source": copy.deepcopy(draft.get("source")) if isinstance(draft.get("source"), Mapping) else {},
    }


def domain_from_draft(draft: Mapping[str, Any]) -> Justification:
    value = normalise_draft(draft)
    transport = value["transport"]
    financial = value["financial"]
    cost_range = value["cost_range"]
    products = tuple(
        Product(
            line_id=item["line_id"],
            name=item["name"],
            characteristics=item["characteristics"],
            quantity=item["quantity"],
            offered_unit_price=item["offered_unit_price"],
            applied_percentage=item["applied_percentage"],
            applied_factor=item["applied_factor"],
            generated_unit_cost=item["generated_unit_cost"],
            manual_unit_cost=item["manual_unit_cost"],
            locked=item["locked"],
            cost_origin=CostOrigin(item["cost_origin"]),
        )
        for item in value["products"]
    )
    return Justification(
        lot_identifier=value["identification"]["lot_number"],
        products=products,
        transport=TransportInput(**transport),
        financial=FinancialInput(**financial),
        cost_range=CostRange(**cost_range),
    )


def merge_domain_into_draft(draft: Mapping[str, Any], justification: Justification) -> dict[str, Any]:
    value = normalise_draft(draft)
    previous = {item["line_id"]: item for item in value["products"]}
    products: list[dict[str, Any]] = []
    for product in justification.products:
        old = previous.get(product.line_id, {})
        products.append(
            {
                "line_id": product.line_id,
                "name": product.name,
                "characteristics": product.characteristics,
                "quantity": canonical_decimal(product.quantity),
                "offered_unit_price": canonical_decimal(product.offered_unit_price),
                "offered_amount_input": old.get("offered_amount_input"),
                "applied_percentage": product.applied_percentage,
                "applied_factor": canonical_decimal(product.applied_factor) if product.applied_factor is not None else None,
                "generated_unit_cost": canonical_decimal(product.generated_unit_cost) if product.generated_unit_cost is not None else None,
                "manual_unit_cost": canonical_decimal(product.manual_unit_cost) if product.manual_unit_cost is not None else None,
                "locked": product.locked,
                "cost_origin": product.cost_origin.value,
                "source_row": old.get("source_row"),
            }
        )
    value["products"] = products
    value["identification"]["lot_number"] = justification.lot_identifier
    value["cost_range"] = {
        "minimum_percentage": justification.cost_range.minimum_percentage,
        "maximum_percentage": justification.cost_range.maximum_percentage,
    }
    value["transport"] = {
        "operational_weeks": justification.transport.operational_weeks,
        "weekly_deliveries": justification.transport.weekly_deliveries,
        "circular_kilometres": canonical_decimal(justification.transport.circular_kilometres),
        "effective_decimal_hours": canonical_decimal(justification.transport.effective_decimal_hours),
        "kilometre_rate": canonical_decimal(justification.transport.kilometre_rate),
        "hourly_rate": canonical_decimal(justification.transport.hourly_rate),
        "contract_stops": justification.transport.contract_stops,
        "shared_orders": justification.transport.shared_orders,
        "descriptive_months": justification.transport.descriptive_months,
        "route_duration_text": justification.transport.route_duration_text or "",
    }
    value["financial"] = {
        "declared_lot_offer": canonical_decimal(justification.financial.declared_lot_offer),
        "general_expense_base": canonical_decimal(justification.financial.general_expense_base),
        "general_expense_percentage": canonical_decimal(justification.financial.general_expense_percentage),
        "indirect_costs": canonical_decimal(justification.financial.indirect_costs) if justification.financial.indirect_costs is not None else None,
    }
    return value


def calculate_draft(draft: Mapping[str, Any]) -> dict[str, Any]:
    try:
        domain = domain_from_draft(draft)
    except (DomainValueError, ProductImportError, KeyError, TypeError, ValueError) as exc:
        return {
            "errors": [{"code": getattr(exc, "code", "borrador_invalido"), "severity": "error", "message": str(exc), "field": getattr(exc, "field", "draft"), "line_id": None, "metadata": {}}],
            "warnings": _document_input_warnings(draft),
            "values": None,
        }
    payload = economic_payload(calculate_justification(domain))
    payload["warnings"].extend(_document_input_warnings(draft))
    return payload


def _document_input_warnings(draft: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    image = draft.get("route_image") if isinstance(draft, Mapping) else None
    if not image:
        warnings.append(_simple_warning("imagen_ruta_ausente", "No se ha incorporado una imagen de la ruta.", "route_image"))
    document = draft.get("transport_document", {}) if isinstance(draft, Mapping) else {}
    if not isinstance(document, Mapping) or not _text(document.get("observatory_date")):
        warnings.append(_simple_warning("fecha_observatorio_ausente", "Falta confirmar la fecha del Observatorio.", "observatory_date"))
    if not isinstance(document, Mapping) or not _text(document.get("observatory_url")):
        warnings.append(_simple_warning("url_observatorio_ausente", "Falta confirmar la URL del Observatorio.", "observatory_url"))
    return warnings


def _simple_warning(code: str, message: str, field: str) -> dict[str, Any]:
    return {"code": code, "severity": "advertencia", "message": message, "field": field, "line_id": None, "metadata": {}}


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key, {})
    if not isinstance(value, Mapping):
        raise DomainValueError("seccion_invalida", key, f"{key} debe ser un objeto.")
    return value


def _decimal_text(value: object, field: str) -> str:
    # Draft JSON is canonical by contract. A comma explicitly opts into the
    # Spanish parser; a dot-only string remains a decimal point so generated
    # three-decimal costs can never turn into thousands on reopen.
    if isinstance(value, str) and "," not in value:
        text = value.strip()
        if re.fullmatch(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)", text):
            from ..domain import decimal_value

            return canonical_decimal(decimal_value(text, field))
    return canonical_decimal(parse_decimal(value, field=field))


def _optional_decimal_text(value: object | None, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _decimal_text(value, field)


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise DomainValueError("entero_invalido", field, f"{field} debe ser un entero.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text and text.lstrip("-").isdigit():
            return int(text)
    raise DomainValueError("entero_invalido", field, f"{field} debe ser un entero.")


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise DomainValueError("booleano_invalido", field, f"{field} debe ser booleano.")
    return value


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _limited_text(value: object, field: str, maximum: int = MAX_TEXT_LENGTH) -> str:
    text = _text(value)
    if len(text) > maximum:
        raise DomainValueError("texto_demasiado_largo", field, f"{field} supera el tamaño permitido.")
    return text


def _text_list(value: object, field: str, *, maximum: int = 200) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise DomainValueError("lista_invalida", field, f"{field} debe ser una lista.")
    return [_limited_text(item, field) for item in value if _text(item)]


def _join_nonempty(*parts: object) -> str:
    return ", ".join(_text(part) for part in parts if _text(part))


def _route_image(value: object) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, Mapping):
        raise DomainValueError("imagen_invalida", "route_image", "La referencia de imagen no es válida.")
    asset_id = _integer(value.get("asset_id", 0), "asset_id")
    if asset_id <= 0:
        raise DomainValueError("imagen_asset_invalido", "asset_id", "La imagen debe referenciar un asset válido.")
    mime_type = _limited_text(value.get("mime_type"), "mime_type", 100)
    if mime_type not in {"image/png", "image/jpeg"}:
        raise DomainValueError("imagen_mime_invalido", "mime_type", "El tipo de imagen no está permitido.")
    sha256 = _limited_text(value.get("sha256"), "sha256", 128).upper()
    if not re.fullmatch(r"[0-9A-F]{64}", sha256):
        raise DomainValueError("imagen_hash_invalido", "sha256", "El hash de imagen no es válido.")
    result = {
        "asset_id": asset_id,
        "logical_name": _limited_text(value.get("logical_name"), "logical_name", 255),
        "mime_type": mime_type,
        "width_px": _integer(value.get("width_px", 0), "width_px"),
        "height_px": _integer(value.get("height_px", 0), "height_px"),
        "sha256": sha256,
        "size_bytes": _integer(value.get("size_bytes", 0), "size_bytes"),
    }
    if result["width_px"] <= 0 or result["height_px"] <= 0 or result["size_bytes"] <= 0:
        raise DomainValueError("imagen_geometria_invalida", "route_image", "La geometría o tamaño de imagen no son válidos.")
    return result
