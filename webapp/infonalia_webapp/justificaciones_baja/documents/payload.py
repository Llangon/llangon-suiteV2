"""Typed, calculation-free document payloads for low-bid justifications."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..calculations import canonical_decimal
from ..domain import CostOrigin, ValidationIssue
from ..snapshot import (
    CALCULATION_ALGORITHM_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    CanonicalSnapshot,
)
from .template_manifest import PAYLOAD_SCHEMA_VERSION, WORD_TEMPLATE_VERSION


class DocumentPayloadError(ValueError):
    """Raised when a source snapshot cannot become a document payload."""


@dataclass(frozen=True, slots=True)
class IdentificationInput:
    expediente: str
    organismo: str
    objeto: str
    lot_number: str
    lot_name: str
    duration_description: str
    place: str
    date_text: str
    client: str
    nif: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    representative: str = ""
    representative_dni: str = ""
    role: str = ""
    signatory: str = ""


@dataclass(frozen=True, slots=True)
class NarrativeInput:
    subject: str
    exposition: str
    arguments: tuple[str, ...]
    acquisition_text: str
    transport_text: str
    structure_text: str
    conclusion: str
    estimated_draft_notice: str = (
        "BORRADOR ESTIMATIVO PENDIENTE DE VALIDACIÓN DEL CLIENTE"
    )
    confidentiality_text: str = (
        "Documento confidencial para uso exclusivo en el procedimiento indicado."
    )
    pending_validation_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", tuple(self.arguments))
        object.__setattr__(
            self,
            "pending_validation_fields",
            tuple(self.pending_validation_fields),
        )


@dataclass(frozen=True, slots=True)
class TransportDocumentInput:
    observatory: str
    observatory_date: str
    observatory_url: str
    vehicle: str


@dataclass(frozen=True, slots=True)
class RouteImageReference:
    logical_name: str
    mime_type: str
    width_px: int
    height_px: int
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class RawDisplayValue:
    raw: str
    display: str


@dataclass(frozen=True, slots=True)
class DocumentIssueV1:
    code: str
    severity: str
    message: str
    field: str | None = None
    line_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentControlV1:
    payload_schema_version: str
    snapshot_schema_version: str
    calculation_algorithm_version: str
    snapshot_sha256: str
    template_version: str
    generated_at: str
    generated_by: str
    draft: bool


@dataclass(frozen=True, slots=True)
class DocumentIdentificationV1:
    expediente: str
    organismo: str
    objeto: str
    lot_number: str
    lot_name: str
    duration_description: str
    place: str
    date_text: str
    client: str
    nif: str
    address: str
    phone: str
    email: str
    representative: str
    representative_dni: str
    role: str
    signatory: str


@dataclass(frozen=True, slots=True)
class DocumentProductV1:
    line_id: str
    name: str
    characteristics: str
    quantity: RawDisplayValue
    offered_unit_price: RawDisplayValue
    offered_amount: RawDisplayValue
    generated_unit_cost_raw: str | None
    manual_unit_cost_raw: str | None
    effective_unit_cost: RawDisplayValue
    cost_amount: RawDisplayValue
    margin: RawDisplayValue
    cost_origin: str
    locked: bool
    warnings: tuple[DocumentIssueV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class DocumentTransportV1:
    observatory: str
    observatory_date: str
    observatory_url: str
    vehicle: str
    operational_weeks: int
    weekly_deliveries: int
    total_services: int
    circular_kilometres: RawDisplayValue
    effective_decimal_hours: RawDisplayValue
    route_duration_text: str
    kilometre_rate: RawDisplayValue
    hourly_rate: RawDisplayValue
    temporal_cost: RawDisplayValue
    kilometre_cost: RawDisplayValue
    full_route_cost: RawDisplayValue
    contract_stops: int
    shared_orders: int
    narrative_percentage: RawDisplayValue
    allocated_transport: RawDisplayValue
    route_image: RouteImageReference | None


@dataclass(frozen=True, slots=True)
class DocumentSummaryV1:
    offer: RawDisplayValue
    justified_lines_offer: RawDisplayValue
    raw_product_cost: RawDisplayValue
    prorated_product_cost: RawDisplayValue
    gross_margin: RawDisplayValue
    gross_margin_percentage: RawDisplayValue
    allocated_transport: RawDisplayValue
    indirect_costs: RawDisplayValue
    general_expenses: RawDisplayValue
    total_cost: RawDisplayValue
    profit: RawDisplayValue
    profit_percentage: RawDisplayValue
    visible_product_cost_sum: RawDisplayValue
    visual_product_residual: RawDisplayValue


@dataclass(frozen=True, slots=True)
class DocumentNarrativeV1:
    subject: str
    exposition: str
    arguments: tuple[str, ...]
    acquisition_text: str
    transport_text: str
    structure_text: str
    conclusion: str
    estimated_draft_notice: str
    confidentiality_text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", tuple(self.arguments))


@dataclass(frozen=True, slots=True)
class DocumentWarningsV1:
    economic_issues: tuple[DocumentIssueV1, ...] = ()
    document_warnings: tuple[DocumentIssueV1, ...] = ()
    pending_validation_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "economic_issues", tuple(self.economic_issues))
        object.__setattr__(self, "document_warnings", tuple(self.document_warnings))
        object.__setattr__(
            self,
            "pending_validation_fields",
            tuple(self.pending_validation_fields),
        )


@dataclass(frozen=True, slots=True)
class DocumentPayloadV1:
    control: DocumentControlV1
    identification: DocumentIdentificationV1
    products: tuple[DocumentProductV1, ...]
    transport: DocumentTransportV1
    summary: DocumentSummaryV1
    narrative: DocumentNarrativeV1
    warnings: DocumentWarningsV1

    def __post_init__(self) -> None:
        object.__setattr__(self, "products", tuple(self.products))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest().upper()


def build_document_payload(
    snapshot: CanonicalSnapshot,
    identification: IdentificationInput,
    narrative: NarrativeInput,
    transport_document: TransportDocumentInput,
    *,
    route_image: RouteImageReference | None = None,
    route_image_path: str | Path | None = None,
    route_image_logical_name: str | None = None,
    generated_at: str | None = None,
    generated_by: str | None = None,
    template_version: str = WORD_TEMPLATE_VERSION,
    draft: bool = True,
) -> DocumentPayloadV1:
    """Transform a valid frozen snapshot without invoking the economic engine."""

    if route_image is not None and route_image_path is not None:
        raise DocumentPayloadError(
            "No se puede proporcionar simultáneamente una referencia y una ruta de imagen."
        )
    if route_image_path is not None:
        # Local import keeps payload types independent from document parsers while
        # allowing the small public builder API to create the logical reference.
        from .validators import inspect_route_image

        route_image = inspect_route_image(
            route_image_path,
            logical_name=route_image_logical_name,
        )

    if snapshot.schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise DocumentPayloadError("La versión del snapshot no es compatible.")
    if snapshot.algorithm_version != CALCULATION_ALGORITHM_VERSION:
        raise DocumentPayloadError("La versión del algoritmo económico no es compatible.")
    if not snapshot.calculation.is_valid or snapshot.calculation.values is None:
        raise DocumentPayloadError("El snapshot no contiene un cálculo válido y congelado.")
    snapshot_json = snapshot.to_json()
    snapshot_sha256 = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest().upper()
    values = snapshot.calculation.values
    source_products = {product.line_id: product for product in snapshot.justification.products}
    warnings_by_line: dict[str, list[DocumentIssueV1]] = {}
    all_issues = tuple(snapshot.calculation.errors) + tuple(snapshot.calculation.warnings)
    for issue in all_issues:
        if issue.line_id:
            warnings_by_line.setdefault(issue.line_id, []).append(_document_issue(issue))

    products: list[DocumentProductV1] = []
    for line in values.product_lines:
        source = source_products.get(line.line_id)
        if source is None:
            raise DocumentPayloadError(f"La línea {line.line_id!r} no existe en el snapshot.")
        products.append(
            DocumentProductV1(
                line_id=line.line_id,
                name=line.name,
                characteristics=line.characteristics,
                quantity=RawDisplayValue(
                    raw=canonical_decimal(line.quantity),
                    display=_format_quantity(line.quantity),
                ),
                offered_unit_price=RawDisplayValue(
                    raw=canonical_decimal(line.offered_unit_price),
                    display=line.display.offered_unit_price,
                ),
                offered_amount=RawDisplayValue(
                    raw=canonical_decimal(line.offered_amount),
                    display=line.display.offered_amount,
                ),
                generated_unit_cost_raw=(
                    canonical_decimal(source.generated_unit_cost)
                    if source.generated_unit_cost is not None
                    else None
                ),
                manual_unit_cost_raw=(
                    canonical_decimal(source.manual_unit_cost)
                    if source.manual_unit_cost is not None
                    else None
                ),
                effective_unit_cost=RawDisplayValue(
                    raw=canonical_decimal(line.effective_unit_cost),
                    display=line.display.effective_unit_cost,
                ),
                cost_amount=RawDisplayValue(
                    raw=canonical_decimal(line.cost_amount),
                    display=line.display.cost_amount,
                ),
                margin=RawDisplayValue(
                    raw=canonical_decimal(line.margin),
                    display=line.display.margin,
                ),
                cost_origin=(
                    source.cost_origin.value
                    if isinstance(source.cost_origin, CostOrigin)
                    else str(source.cost_origin)
                ),
                locked=source.locked,
                warnings=tuple(warnings_by_line.get(line.line_id, ())),
            )
        )

    display = values.display
    summary = DocumentSummaryV1(
        offer=_pair(values.declared_lot_offer, display.declared_lot_offer),
        justified_lines_offer=_pair(
            values.justified_lines_offer,
            display.justified_lines_offer,
        ),
        raw_product_cost=_pair(values.raw_product_cost, display.raw_product_cost),
        prorated_product_cost=_pair(
            values.prorated_product_cost,
            display.prorated_product_cost,
        ),
        gross_margin=_pair(values.gross_margin, display.gross_margin),
        gross_margin_percentage=_pair(
            values.gross_margin_percentage,
            display.gross_margin_percentage,
        ),
        allocated_transport=_pair(
            values.allocated_transport,
            display.allocated_transport,
        ),
        indirect_costs=_pair(values.indirect_costs, display.indirect_costs),
        general_expenses=_pair(values.general_expenses, display.general_expenses),
        total_cost=_pair(values.total_cost, display.total_cost),
        profit=_pair(values.profit, display.profit),
        profit_percentage=_pair(values.profit_percentage, display.profit_percentage),
        visible_product_cost_sum=_pair(
            values.visible_product_cost_sum,
            display.visible_product_cost_sum,
        ),
        visual_product_residual=_pair(
            values.visual_product_residual,
            display.visual_product_residual,
        ),
    )
    source_transport = snapshot.justification.transport
    transport = DocumentTransportV1(
        observatory=transport_document.observatory,
        observatory_date=transport_document.observatory_date,
        observatory_url=transport_document.observatory_url,
        vehicle=transport_document.vehicle,
        operational_weeks=source_transport.operational_weeks,
        weekly_deliveries=source_transport.weekly_deliveries,
        total_services=values.total_services,
        circular_kilometres=RawDisplayValue(
            canonical_decimal(source_transport.circular_kilometres),
            _format_decimal_es(source_transport.circular_kilometres, 2),
        ),
        effective_decimal_hours=RawDisplayValue(
            canonical_decimal(source_transport.effective_decimal_hours),
            _format_decimal_es(source_transport.effective_decimal_hours, 2),
        ),
        route_duration_text=source_transport.route_duration_text or "",
        kilometre_rate=RawDisplayValue(
            canonical_decimal(source_transport.kilometre_rate),
            _format_decimal_es(source_transport.kilometre_rate, 4),
        ),
        hourly_rate=RawDisplayValue(
            canonical_decimal(source_transport.hourly_rate),
            _format_decimal_es(source_transport.hourly_rate, 2),
        ),
        temporal_cost=_pair(values.temporal_cost, display.temporal_cost),
        kilometre_cost=_pair(values.kilometre_cost, display.kilometre_cost),
        full_route_cost=_pair(values.full_route_cost, display.full_route_cost),
        contract_stops=source_transport.contract_stops,
        shared_orders=source_transport.shared_orders,
        narrative_percentage=_pair(
            values.narrative_percentage,
            display.narrative_percentage,
        ),
        allocated_transport=_pair(
            values.allocated_transport,
            display.allocated_transport,
        ),
        route_image=route_image,
    )
    generated_at_value = generated_at or datetime.now(timezone.utc).isoformat()
    generated_by_value = (
        snapshot.metadata.created_by if generated_by is None else str(generated_by).strip()
    )
    return DocumentPayloadV1(
        control=DocumentControlV1(
            payload_schema_version=PAYLOAD_SCHEMA_VERSION,
            snapshot_schema_version=snapshot.schema_version,
            calculation_algorithm_version=snapshot.algorithm_version,
            snapshot_sha256=snapshot_sha256,
            template_version=template_version,
            generated_at=str(generated_at_value).strip(),
            generated_by=generated_by_value,
            draft=bool(draft),
        ),
        identification=DocumentIdentificationV1(**asdict(identification)),
        products=tuple(products),
        transport=transport,
        summary=summary,
        narrative=DocumentNarrativeV1(
            subject=narrative.subject,
            exposition=narrative.exposition,
            arguments=tuple(narrative.arguments),
            acquisition_text=narrative.acquisition_text,
            transport_text=narrative.transport_text,
            structure_text=narrative.structure_text,
            conclusion=narrative.conclusion,
            estimated_draft_notice=narrative.estimated_draft_notice,
            confidentiality_text=narrative.confidentiality_text,
        ),
        warnings=DocumentWarningsV1(
            economic_issues=tuple(_document_issue(issue) for issue in all_issues),
            document_warnings=(),
            pending_validation_fields=tuple(narrative.pending_validation_fields),
        ),
    )


def _document_issue(issue: ValidationIssue) -> DocumentIssueV1:
    return DocumentIssueV1(
        code=issue.code,
        severity=issue.severity.value,
        message=issue.message,
        field=issue.field,
        line_id=issue.line_id,
    )


def _pair(value: Decimal, display: str) -> RawDisplayValue:
    return RawDisplayValue(raw=canonical_decimal(value), display=display)


def _format_quantity(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,}".replace(",", ".")
    return _format_decimal_es(value, 3).rstrip("0").rstrip(",")


def _format_decimal_es(value: Decimal, decimals: int) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


__all__ = (
    "DocumentControlV1",
    "DocumentIdentificationV1",
    "DocumentIssueV1",
    "DocumentNarrativeV1",
    "DocumentPayloadError",
    "DocumentPayloadV1",
    "DocumentProductV1",
    "DocumentSummaryV1",
    "DocumentTransportV1",
    "DocumentWarningsV1",
    "IdentificationInput",
    "NarrativeInput",
    "RawDisplayValue",
    "RouteImageReference",
    "TransportDocumentInput",
    "build_document_payload",
)
