"""Canonical in-memory snapshots without filesystem or database access."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from .calculations import calculate_justification, canonical_decimal, economic_payload
from .domain import (
    CalculationResult,
    CostOrigin,
    CostRange,
    DomainValueError,
    FinancialInput,
    IssueSeverity,
    Justification,
    Product,
    TransportInput,
    ValidationIssue,
    decimal_value,
    integer_value,
)


SNAPSHOT_SCHEMA_VERSION = "1"
CALCULATION_ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    created_at: str
    created_by: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", str(self.created_at).strip())
        object.__setattr__(self, "created_by", str(self.created_by).strip())


@dataclass(frozen=True, slots=True)
class CanonicalSnapshot:
    metadata: SnapshotMetadata
    justification: Justification
    calculation: CalculationResult
    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    algorithm_version: str = CALCULATION_ALGORITHM_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm_version": self.algorithm_version,
            "metadata": {
                "created_at": self.metadata.created_at,
                "created_by": self.metadata.created_by,
            },
            "input": _justification_payload(self.justification),
            "calculation": economic_payload(self.calculation),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class SnapshotBuildResult:
    snapshot: CanonicalSnapshot | None
    errors: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.snapshot is not None and not self.errors


@dataclass(frozen=True, slots=True)
class SnapshotLoadResult:
    snapshot: CanonicalSnapshot | None
    errors: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.snapshot is not None and not self.errors


def create_snapshot(
    justification: Justification,
    calculation: CalculationResult,
    metadata: SnapshotMetadata,
) -> SnapshotBuildResult:
    if not metadata.created_at:
        return SnapshotBuildResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_sin_fecha", "El snapshot requiere una fecha de creación."),),
        )
    if not calculation.is_valid:
        return SnapshotBuildResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_calculo_invalido", "No puede congelarse un cálculo con errores."),),
        )
    recalculated = calculate_justification(justification)
    if not recalculated.is_valid or economic_payload(recalculated) != economic_payload(calculation):
        return SnapshotBuildResult(
            snapshot=None,
            errors=(
                _snapshot_error(
                    "snapshot_resultado_incoherente",
                    "El resultado no coincide con los datos de entrada del snapshot.",
                ),
            ),
        )
    return SnapshotBuildResult(
        snapshot=CanonicalSnapshot(
            metadata=metadata,
            justification=justification,
            calculation=calculation,
        )
    )


def load_snapshot(payload: str | Mapping[str, Any]) -> SnapshotLoadResult:
    if isinstance(payload, str):
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return SnapshotLoadResult(
                snapshot=None,
                errors=(_snapshot_error("snapshot_json_invalido", "El JSON del snapshot no es válido."),),
            )
    else:
        raw = dict(payload)
    if not isinstance(raw, dict):
        return SnapshotLoadResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_incompatible", "El snapshot debe ser un objeto JSON."),),
        )
    if raw.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return SnapshotLoadResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_incompatible", "La versión del esquema no es compatible."),),
        )
    if raw.get("algorithm_version") != CALCULATION_ALGORITHM_VERSION:
        return SnapshotLoadResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_incompatible", "La versión del algoritmo no es compatible."),),
        )
    try:
        metadata_raw = _mapping(raw["metadata"], "metadata")
        metadata = SnapshotMetadata(
            created_at=_string(metadata_raw["created_at"], "created_at"),
            created_by=_string(metadata_raw.get("created_by", ""), "created_by"),
        )
        justification = _justification_from_payload(_mapping(raw["input"], "input"))
        stored_calculation = _mapping(raw["calculation"], "calculation")
    except (KeyError, TypeError, DomainValueError) as exc:
        return SnapshotLoadResult(
            snapshot=None,
            errors=(
                _snapshot_error(
                    "snapshot_incompatible",
                    f"El snapshot no puede reconstruirse: {exc}",
                ),
            ),
        )
    calculation = calculate_justification(justification)
    if not calculation.is_valid:
        return SnapshotLoadResult(
            snapshot=None,
            errors=(_snapshot_error("snapshot_incompatible", "El snapshot contiene entradas no calculables."),),
        )
    if economic_payload(calculation) != dict(stored_calculation):
        return SnapshotLoadResult(
            snapshot=None,
            errors=(
                _snapshot_error(
                    "snapshot_resultado_incoherente",
                    "Las cifras almacenadas no coinciden con las entradas del snapshot.",
                ),
            ),
        )
    return SnapshotLoadResult(
        snapshot=CanonicalSnapshot(
            metadata=metadata,
            justification=justification,
            calculation=calculation,
        )
    )


def _justification_payload(justification: Justification) -> dict[str, Any]:
    transport = justification.transport
    financial = justification.financial
    return {
        "lot_identifier": justification.lot_identifier,
        "cost_range": {
            "minimum_percentage": justification.cost_range.minimum_percentage,
            "maximum_percentage": justification.cost_range.maximum_percentage,
        },
        "transport": {
            "operational_weeks": transport.operational_weeks,
            "weekly_deliveries": transport.weekly_deliveries,
            "circular_kilometres": canonical_decimal(transport.circular_kilometres),
            "effective_decimal_hours": canonical_decimal(transport.effective_decimal_hours),
            "kilometre_rate": canonical_decimal(transport.kilometre_rate),
            "hourly_rate": canonical_decimal(transport.hourly_rate),
            "contract_stops": transport.contract_stops,
            "shared_orders": transport.shared_orders,
            "descriptive_months": transport.descriptive_months,
            "route_duration_text": transport.route_duration_text,
        },
        "financial": {
            "declared_lot_offer": canonical_decimal(financial.declared_lot_offer),
            "general_expense_base": canonical_decimal(financial.general_expense_base),
            "general_expense_percentage": canonical_decimal(financial.general_expense_percentage),
            "indirect_costs": (
                canonical_decimal(financial.indirect_costs)
                if financial.indirect_costs is not None
                else None
            ),
        },
        "products": [
            {
                "line_id": product.line_id,
                "name": product.name,
                "characteristics": product.characteristics,
                "quantity": canonical_decimal(product.quantity),
                "offered_unit_price": canonical_decimal(product.offered_unit_price),
                "applied_percentage": product.applied_percentage,
                "applied_factor": (
                    canonical_decimal(product.applied_factor)
                    if product.applied_factor is not None
                    else None
                ),
                "generated_unit_cost": (
                    canonical_decimal(product.generated_unit_cost)
                    if product.generated_unit_cost is not None
                    else None
                ),
                "manual_unit_cost": (
                    canonical_decimal(product.manual_unit_cost)
                    if product.manual_unit_cost is not None
                    else None
                ),
                "locked": product.locked,
                "cost_origin": product.cost_origin.value,
            }
            for product in justification.products
        ],
    }


def _justification_from_payload(payload: Mapping[str, Any]) -> Justification:
    range_raw = _mapping(payload["cost_range"], "cost_range")
    transport_raw = _mapping(payload["transport"], "transport")
    financial_raw = _mapping(payload["financial"], "financial")
    products_raw = payload["products"]
    if not isinstance(products_raw, list):
        raise TypeError("products debe ser una lista")
    products = tuple(_product_from_payload(_mapping(item, "product")) for item in products_raw)
    indirect_raw = financial_raw.get("indirect_costs")
    return Justification(
        lot_identifier=_string(payload["lot_identifier"], "lot_identifier"),
        products=products,
        transport=TransportInput(
            operational_weeks=integer_value(transport_raw["operational_weeks"], "operational_weeks"),
            weekly_deliveries=integer_value(transport_raw["weekly_deliveries"], "weekly_deliveries"),
            circular_kilometres=_snapshot_decimal(transport_raw["circular_kilometres"], "circular_kilometres"),
            effective_decimal_hours=_snapshot_decimal(transport_raw["effective_decimal_hours"], "effective_decimal_hours"),
            kilometre_rate=_snapshot_decimal(transport_raw["kilometre_rate"], "kilometre_rate"),
            hourly_rate=_snapshot_decimal(transport_raw["hourly_rate"], "hourly_rate"),
            contract_stops=integer_value(transport_raw["contract_stops"], "contract_stops"),
            shared_orders=integer_value(transport_raw["shared_orders"], "shared_orders"),
            descriptive_months=(
                integer_value(transport_raw["descriptive_months"], "descriptive_months")
                if transport_raw.get("descriptive_months") is not None
                else None
            ),
            route_duration_text=(
                _string(transport_raw["route_duration_text"], "route_duration_text")
                if transport_raw.get("route_duration_text") is not None
                else None
            ),
        ),
        financial=FinancialInput(
            declared_lot_offer=_snapshot_decimal(financial_raw["declared_lot_offer"], "declared_lot_offer"),
            general_expense_base=_snapshot_decimal(financial_raw["general_expense_base"], "general_expense_base"),
            general_expense_percentage=_snapshot_decimal(financial_raw["general_expense_percentage"], "general_expense_percentage"),
            indirect_costs=(
                _snapshot_decimal(indirect_raw, "indirect_costs")
                if indirect_raw is not None
                else None
            ),
        ),
        cost_range=CostRange(
            minimum_percentage=integer_value(range_raw["minimum_percentage"], "minimum_percentage"),
            maximum_percentage=integer_value(range_raw["maximum_percentage"], "maximum_percentage"),
        ),
    )


def _product_from_payload(payload: Mapping[str, Any]) -> Product:
    applied_percentage = payload.get("applied_percentage")
    locked = payload["locked"]
    if not isinstance(locked, bool):
        raise TypeError("locked debe ser booleano")
    return Product(
        line_id=_string(payload["line_id"], "line_id"),
        name=_string(payload["name"], "name"),
        characteristics=_string(payload.get("characteristics", ""), "characteristics"),
        quantity=_snapshot_decimal(payload["quantity"], "quantity"),
        offered_unit_price=_snapshot_decimal(payload["offered_unit_price"], "offered_unit_price"),
        applied_percentage=(
            integer_value(applied_percentage, "applied_percentage")
            if applied_percentage is not None
            else None
        ),
        applied_factor=_optional_snapshot_decimal(payload.get("applied_factor"), "applied_factor"),
        generated_unit_cost=_optional_snapshot_decimal(payload.get("generated_unit_cost"), "generated_unit_cost"),
        manual_unit_cost=_optional_snapshot_decimal(payload.get("manual_unit_cost"), "manual_unit_cost"),
        locked=locked,
        cost_origin=_cost_origin(payload["cost_origin"]),
    )


def _snapshot_decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise DomainValueError(
            "snapshot_decimal_no_texto",
            field,
            f"{field} debe estar serializado como texto decimal.",
        )
    return decimal_value(value, field)


def _optional_snapshot_decimal(value: object | None, field: str) -> Decimal | None:
    if value is None:
        return None
    return _snapshot_decimal(value, field)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} debe ser un objeto")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} debe ser texto")
    return value


def _cost_origin(value: object) -> CostOrigin:
    text = _string(value, "cost_origin")
    try:
        return CostOrigin(text)
    except ValueError as exc:
        raise DomainValueError(
            "origen_coste_invalido",
            "cost_origin",
            "El origen del coste del snapshot no es compatible.",
        ) from exc


def _snapshot_error(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=IssueSeverity.ERROR,
        message=message,
        field="snapshot",
    )
