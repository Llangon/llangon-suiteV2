"""Deterministic economic calculations and locale-independent presentation."""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .domain import (
    CalculationResult,
    EconomicDisplay,
    EconomicValues,
    IssueSeverity,
    Justification,
    ProductLineDisplay,
    ProductLineResult,
    ValidationIssue,
)
from .validations import validate_calculated_values, validate_justification


MONEY_QUANTUM = Decimal("0.01")
UNIT_COST_QUANTUM = Decimal("0.001")
PERCENT_DISPLAY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")


def round_half_up(value: Decimal, quantum: Decimal) -> Decimal:
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        return Decimal("0").quantize(quantum)
    return rounded


def factor_for_percentage(percentage: int) -> Decimal:
    return Decimal("1") + Decimal(percentage) / HUNDRED


def calculate_generated_unit_cost(offered_unit_price: Decimal, percentage: int) -> Decimal:
    factor = factor_for_percentage(percentage)
    if factor <= 0:
        raise ValueError("El porcentaje aplicado debe producir un factor mayor que cero.")
    return round_half_up(offered_unit_price / factor, UNIT_COST_QUANTUM)


def canonical_decimal(value: Decimal) -> str:
    """Return a locale-independent decimal string while preserving its scale."""

    return format(value, "f")


def format_spanish_number(value: Decimal, decimal_places: int) -> str:
    quantum = Decimal("1").scaleb(-decimal_places)
    rounded = round_half_up(value, quantum)
    english = format(rounded, f",.{decimal_places}f")
    return english.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_spanish_amount(value: Decimal) -> str:
    return format_spanish_number(value, 2)


def format_spanish_unit_cost(value: Decimal) -> str:
    return format_spanish_number(value, 3)


def format_spanish_ratio_percentage(value: Decimal) -> str:
    return f"{format_spanish_number(value * HUNDRED, 2)} %"


def format_spanish_percentage_points(value: Decimal) -> str:
    return f"{format_spanish_number(value, 2)} %"


def calculate_justification(justification: Justification) -> CalculationResult:
    input_issues = validate_justification(justification, require_effective_costs=True)
    errors = tuple(item for item in input_issues if item.severity is IssueSeverity.ERROR)
    warnings = tuple(item for item in input_issues if item.severity is IssueSeverity.WARNING)
    if errors:
        return CalculationResult(values=None, errors=errors, warnings=warnings)

    product_lines: list[ProductLineResult] = []
    justified_lines_offer = Decimal("0")
    raw_product_cost = Decimal("0")
    visible_product_cost_sum = Decimal("0")

    for product in justification.products:
        effective_unit_cost = product.effective_unit_cost
        if effective_unit_cost is None:
            defensive_error = ValidationIssue(
                code="producto_sin_coste_efectivo",
                severity=IssueSeverity.ERROR,
                message="El producto no tiene un coste efectivo.",
                field="effective_unit_cost",
                line_id=product.line_id or None,
            )
            return CalculationResult(
                values=None,
                errors=errors + (defensive_error,),
                warnings=warnings,
            )
        offered_amount = product.quantity * product.offered_unit_price
        cost_amount = product.quantity * effective_unit_cost
        margin = offered_amount - cost_amount
        justified_lines_offer += offered_amount
        raw_product_cost += cost_amount
        visible_product_cost_sum += round_half_up(cost_amount, MONEY_QUANTUM)
        product_lines.append(
            ProductLineResult(
                line_id=product.line_id,
                name=product.name,
                characteristics=product.characteristics,
                quantity=product.quantity,
                offered_unit_price=product.offered_unit_price,
                effective_unit_cost=effective_unit_cost,
                offered_amount=offered_amount,
                cost_amount=cost_amount,
                margin=margin,
                display=ProductLineDisplay(
                    offered_unit_price=format_spanish_amount(product.offered_unit_price),
                    effective_unit_cost=format_spanish_unit_cost(effective_unit_cost),
                    offered_amount=format_spanish_amount(offered_amount),
                    cost_amount=format_spanish_amount(cost_amount),
                    margin=format_spanish_amount(margin),
                ),
            )
        )

    financial = justification.financial
    transport = justification.transport
    prorated_product_cost = round_half_up(
        raw_product_cost / justified_lines_offer * financial.declared_lot_offer,
        MONEY_QUANTUM,
    )
    gross_margin = financial.declared_lot_offer - prorated_product_cost
    gross_margin_percentage = gross_margin / financial.declared_lot_offer

    total_services = transport.operational_weeks * transport.weekly_deliveries
    temporal_cost = round_half_up(
        transport.hourly_rate * Decimal(total_services) * transport.effective_decimal_hours,
        MONEY_QUANTUM,
    )
    kilometre_cost = round_half_up(
        transport.kilometre_rate * Decimal(total_services) * transport.circular_kilometres,
        MONEY_QUANTUM,
    )
    full_route_cost = temporal_cost + kilometre_cost
    narrative_percentage = (
        Decimal(transport.contract_stops) / Decimal(transport.shared_orders) * HUNDRED
    )
    allocated_transport = (
        full_route_cost
        / Decimal(transport.shared_orders)
        * Decimal(transport.contract_stops)
    )

    general_expenses = (
        financial.general_expense_base * financial.general_expense_percentage
    )
    indirect_costs = financial.indirect_costs or Decimal("0")
    total_cost = (
        prorated_product_cost
        + allocated_transport
        + indirect_costs
        + general_expenses
    )
    profit = financial.declared_lot_offer - total_cost
    profit_percentage = profit / financial.declared_lot_offer
    visual_product_residual = prorated_product_cost - visible_product_cost_sum

    display = EconomicDisplay(
        declared_lot_offer=format_spanish_amount(financial.declared_lot_offer),
        justified_lines_offer=format_spanish_amount(justified_lines_offer),
        raw_product_cost=format_spanish_amount(raw_product_cost),
        prorated_product_cost=format_spanish_amount(prorated_product_cost),
        gross_margin=format_spanish_amount(gross_margin),
        gross_margin_percentage=format_spanish_ratio_percentage(gross_margin_percentage),
        temporal_cost=format_spanish_amount(temporal_cost),
        kilometre_cost=format_spanish_amount(kilometre_cost),
        full_route_cost=format_spanish_amount(full_route_cost),
        narrative_percentage=format_spanish_percentage_points(narrative_percentage),
        allocated_transport=format_spanish_amount(allocated_transport),
        general_expenses=format_spanish_amount(general_expenses),
        indirect_costs=format_spanish_amount(indirect_costs),
        total_cost=format_spanish_amount(total_cost),
        profit=format_spanish_amount(profit),
        profit_percentage=format_spanish_ratio_percentage(profit_percentage),
        visible_product_cost_sum=format_spanish_amount(visible_product_cost_sum),
        visual_product_residual=format_spanish_amount(visual_product_residual),
    )
    values = EconomicValues(
        product_lines=tuple(product_lines),
        declared_lot_offer=financial.declared_lot_offer,
        justified_lines_offer=justified_lines_offer,
        raw_product_cost=raw_product_cost,
        prorated_product_cost=prorated_product_cost,
        gross_margin=gross_margin,
        gross_margin_percentage=gross_margin_percentage,
        total_services=total_services,
        temporal_cost=temporal_cost,
        kilometre_cost=kilometre_cost,
        full_route_cost=full_route_cost,
        narrative_percentage=narrative_percentage,
        allocated_transport=allocated_transport,
        general_expenses=general_expenses,
        indirect_costs=indirect_costs,
        total_cost=total_cost,
        profit=profit,
        profit_percentage=profit_percentage,
        visible_product_cost_sum=visible_product_cost_sum,
        visual_product_residual=visual_product_residual,
        display=display,
    )
    post_issues = validate_calculated_values(values)
    post_errors = tuple(item for item in post_issues if item.severity is IssueSeverity.ERROR)
    post_warnings = tuple(item for item in post_issues if item.severity is IssueSeverity.WARNING)
    return CalculationResult(
        values=values if not post_errors else None,
        errors=errors + post_errors,
        warnings=warnings + post_warnings,
    )


def economic_payload(result: CalculationResult) -> dict[str, Any]:
    """Build a deterministic, document-neutral economic payload."""

    payload: dict[str, Any] = {
        "errors": [_issue_payload(item) for item in result.errors],
        "warnings": [_issue_payload(item) for item in result.warnings],
        "values": None,
    }
    values = result.values
    if values is None:
        return payload
    payload["values"] = {
        "raw": {
            "declared_lot_offer": canonical_decimal(values.declared_lot_offer),
            "justified_lines_offer": canonical_decimal(values.justified_lines_offer),
            "raw_product_cost": canonical_decimal(values.raw_product_cost),
            "prorated_product_cost": canonical_decimal(values.prorated_product_cost),
            "gross_margin": canonical_decimal(values.gross_margin),
            "gross_margin_percentage": canonical_decimal(values.gross_margin_percentage),
            "total_services": values.total_services,
            "temporal_cost": canonical_decimal(values.temporal_cost),
            "kilometre_cost": canonical_decimal(values.kilometre_cost),
            "full_route_cost": canonical_decimal(values.full_route_cost),
            "narrative_percentage": canonical_decimal(values.narrative_percentage),
            "allocated_transport": canonical_decimal(values.allocated_transport),
            "general_expenses": canonical_decimal(values.general_expenses),
            "indirect_costs": canonical_decimal(values.indirect_costs),
            "total_cost": canonical_decimal(values.total_cost),
            "profit": canonical_decimal(values.profit),
            "profit_percentage": canonical_decimal(values.profit_percentage),
            "visible_product_cost_sum": canonical_decimal(values.visible_product_cost_sum),
            "visual_product_residual": canonical_decimal(values.visual_product_residual),
        },
        "display": {
            item.name: getattr(values.display, item.name)
            for item in fields(values.display)
        },
        "product_lines": [
            {
                "line_id": line.line_id,
                "name": line.name,
                "characteristics": line.characteristics,
                "quantity": canonical_decimal(line.quantity),
                "offered_unit_price": canonical_decimal(line.offered_unit_price),
                "effective_unit_cost": canonical_decimal(line.effective_unit_cost),
                "offered_amount": canonical_decimal(line.offered_amount),
                "cost_amount": canonical_decimal(line.cost_amount),
                "margin": canonical_decimal(line.margin),
                "display": {
                    item.name: getattr(line.display, item.name)
                    for item in fields(line.display)
                },
            }
            for line in values.product_lines
        ],
    }
    return payload


def _issue_payload(item: ValidationIssue) -> dict[str, Any]:
    return {
        "code": item.code,
        "severity": item.severity.value,
        "message": item.message,
        "field": item.field,
        "line_id": item.line_id,
        "metadata": item.metadata_dict(),
    }
