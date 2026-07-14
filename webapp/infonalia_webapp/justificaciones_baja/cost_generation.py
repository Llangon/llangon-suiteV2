"""Explicit and injectable cost generation actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol, TypeAlias

from .calculations import calculate_generated_unit_cost, factor_for_percentage
from .domain import (
    CostActionResult,
    CostOrigin,
    IssueSeverity,
    Justification,
    Product,
    ValidationIssue,
    decimal_value,
)


class RandomIntegerSource(Protocol):
    def randint(self, minimum: int, maximum: int) -> int: ...


RandomSource: TypeAlias = RandomIntegerSource | Callable[[int, int], int]


def generate_initial_costs(
    justification: Justification,
    random_source: RandomSource,
) -> CostActionResult:
    """Generate only products that have no previous generated cost."""

    range_errors = _range_errors(justification)
    if range_errors:
        return CostActionResult(justification=justification, errors=range_errors)
    products: list[Product] = []
    for product in justification.products:
        if product.generated_unit_cost is None:
            products.append(_generate_product(product, justification, random_source))
        else:
            products.append(product)
    return CostActionResult(justification=replace(justification, products=tuple(products)))


def recalculate_products(
    justification: Justification,
    line_ids: set[str] | frozenset[str] | tuple[str, ...] | list[str],
    random_source: RandomSource,
) -> CostActionResult:
    """Regenerate selected, unlocked lines and leave every other line untouched."""

    range_errors = _range_errors(justification)
    if range_errors:
        return CostActionResult(justification=justification, errors=range_errors)
    selected = set(line_ids)
    known = {product.line_id for product in justification.products}
    unknown = sorted(selected - known)
    warnings = tuple(
        ValidationIssue(
            code="linea_no_encontrada",
            severity=IssueSeverity.WARNING,
            message="La línea seleccionada para recálculo no existe.",
            field="line_ids",
            line_id=line_id,
        )
        for line_id in unknown
    )
    products: list[Product] = []
    for product in justification.products:
        if product.line_id in selected and not product.locked:
            products.append(_generate_product(product, justification, random_source))
        else:
            products.append(product)
    return CostActionResult(
        justification=replace(justification, products=tuple(products)),
        warnings=warnings,
    )


def set_product_lock(
    justification: Justification,
    line_id: str,
    *,
    locked: bool,
) -> CostActionResult:
    return _replace_line(
        justification,
        line_id,
        lambda product: replace(product, locked=bool(locked)),
    )


def set_manual_cost(
    justification: Justification,
    line_id: str,
    manual_unit_cost: object,
) -> CostActionResult:
    cost = decimal_value(manual_unit_cost, "manual_unit_cost")
    return _replace_line(
        justification,
        line_id,
        lambda product: replace(
            product,
            manual_unit_cost=cost,
            cost_origin=CostOrigin.MANUAL,
        ),
    )


def remove_manual_cost(
    justification: Justification,
    line_id: str,
) -> CostActionResult:
    def remove(product: Product) -> Product:
        next_origin = (
            CostOrigin.GENERATED
            if product.generated_unit_cost is not None
            else CostOrigin.UNGENERATED
        )
        return replace(
            product,
            manual_unit_cost=None,
            cost_origin=next_origin,
        )

    return _replace_line(justification, line_id, remove)


def _generate_product(
    product: Product,
    justification: Justification,
    random_source: RandomSource,
) -> Product:
    minimum = justification.cost_range.minimum_percentage
    maximum = justification.cost_range.maximum_percentage
    percentage = _draw_percentage(random_source, minimum, maximum)
    factor = factor_for_percentage(percentage)
    generated_cost = calculate_generated_unit_cost(product.offered_unit_price, percentage)
    origin = CostOrigin.MANUAL if product.manual_unit_cost is not None else CostOrigin.GENERATED
    return replace(
        product,
        applied_percentage=percentage,
        applied_factor=factor,
        generated_unit_cost=generated_cost,
        cost_origin=origin,
    )


def _draw_percentage(random_source: RandomSource, minimum: int, maximum: int) -> int:
    value = (
        random_source(minimum, maximum)
        if callable(random_source)
        else random_source.randint(minimum, maximum)
    )
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("El generador inyectado debe devolver un entero.")
    if value < minimum or value > maximum:
        raise ValueError("El generador inyectado devolvió un valor fuera de la horquilla.")
    return value


def _range_errors(justification: Justification) -> tuple[ValidationIssue, ...]:
    cost_range = justification.cost_range
    if cost_range.minimum_percentage > cost_range.maximum_percentage:
        return (
            ValidationIssue(
                code="horquilla_invalida",
                severity=IssueSeverity.ERROR,
                message="El porcentaje mínimo de la horquilla supera al máximo.",
                field="cost_range",
            ),
        )
    if cost_range.minimum_percentage <= -100:
        return (
            ValidationIssue(
                code="horquilla_factor_no_positivo",
                severity=IssueSeverity.ERROR,
                message="La horquilla puede producir un factor igual o inferior a cero.",
                field="minimum_percentage",
            ),
        )
    return ()


def _replace_line(
    justification: Justification,
    line_id: str,
    operation: Callable[[Product], Product],
) -> CostActionResult:
    found = False
    products: list[Product] = []
    for product in justification.products:
        if product.line_id == line_id:
            products.append(operation(product))
            found = True
        else:
            products.append(product)
    if not found:
        return CostActionResult(
            justification=justification,
            errors=(
                ValidationIssue(
                    code="linea_no_encontrada",
                    severity=IssueSeverity.ERROR,
                    message="La línea indicada no existe.",
                    field="line_id",
                    line_id=line_id,
                ),
            ),
        )
    return CostActionResult(justification=replace(justification, products=tuple(products)))
