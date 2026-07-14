"""Structured validation rules for the pure calculation domain."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from .domain import (
    CostOrigin,
    EconomicValues,
    IssueSeverity,
    Justification,
    ValidationIssue,
)


_HUMAN_DURATION_RE = re.compile(
    r"(?P<hours>\d+)\s*h(?:oras?)?\s*(?P<minutes>\d+)\s*min",
    re.IGNORECASE,
)


def issue(
    code: str,
    severity: IssueSeverity,
    message: str,
    *,
    field: str | None = None,
    line_id: str | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        message=message,
        field=field,
        line_id=line_id,
        metadata=metadata,
    )


def validate_justification(
    justification: Justification,
    *,
    require_effective_costs: bool = True,
) -> tuple[ValidationIssue, ...]:
    """Validate inputs without correcting or recalculating any value."""

    issues: list[ValidationIssue] = []
    financial = justification.financial
    transport = justification.transport
    cost_range = justification.cost_range

    if not justification.lot_identifier:
        issues.append(
            issue(
                "lote_sin_identificador",
                IssueSeverity.ERROR,
                "La justificación debe identificar un único lote.",
                field="lot_identifier",
            )
        )
    if financial.declared_lot_offer <= 0:
        issues.append(
            issue(
                "oferta_total_no_positiva",
                IssueSeverity.ERROR,
                "La oferta total declarada debe ser mayor que cero.",
                field="declared_lot_offer",
            )
        )
    if not justification.products:
        issues.append(
            issue(
                "sin_productos",
                IssueSeverity.ERROR,
                "La justificación debe contener al menos un producto.",
                field="products",
            )
        )
    if cost_range.minimum_percentage > cost_range.maximum_percentage:
        issues.append(
            issue(
                "horquilla_invalida",
                IssueSeverity.ERROR,
                "El porcentaje mínimo de la horquilla supera al máximo.",
                field="cost_range",
            )
        )
    if cost_range.minimum_percentage <= -100:
        issues.append(
            issue(
                "horquilla_factor_no_positivo",
                IssueSeverity.ERROR,
                "La horquilla puede producir un factor igual o inferior a cero.",
                field="minimum_percentage",
            )
        )

    numeric_errors = (
        (transport.operational_weeks < 0, "semanas_negativas", "operational_weeks", "Las semanas no pueden ser negativas."),
        (transport.weekly_deliveries < 0, "entregas_negativas", "weekly_deliveries", "Las entregas no pueden ser negativas."),
        (transport.circular_kilometres < 0, "kilometros_negativos", "circular_kilometres", "Los kilómetros no pueden ser negativos."),
        (transport.effective_decimal_hours < 0, "horas_negativas", "effective_decimal_hours", "Las horas no pueden ser negativas."),
        (transport.kilometre_rate < 0, "tarifa_km_negativa", "kilometre_rate", "La tarifa por kilómetro no puede ser negativa."),
        (transport.hourly_rate < 0, "tarifa_hora_negativa", "hourly_rate", "La tarifa por hora no puede ser negativa."),
        (transport.contract_stops < 0, "paradas_negativas", "contract_stops", "Las paradas no pueden ser negativas."),
        (transport.shared_orders <= 0, "pedidos_compartidos_no_positivos", "shared_orders", "Los pedidos compartidos deben ser mayores que cero."),
        (financial.general_expense_base < 0, "base_gastos_negativa", "general_expense_base", "La base de gastos generales no puede ser negativa."),
        (financial.general_expense_percentage < 0, "porcentaje_gastos_negativo", "general_expense_percentage", "El porcentaje de gastos generales no puede ser negativo."),
        (financial.indirect_costs is not None and financial.indirect_costs < 0, "costes_indirectos_negativos", "indirect_costs", "Los costes indirectos no pueden ser negativos."),
    )
    for condition, code, field, message in numeric_errors:
        if condition:
            issues.append(issue(code, IssueSeverity.ERROR, message, field=field))

    if financial.indirect_costs is None:
        issues.append(
            issue(
                "costes_indirectos_ausentes",
                IssueSeverity.WARNING,
                "Los costes indirectos ausentes se tratarán como cero.",
                field="indirect_costs",
            )
        )
    if financial.general_expense_percentage == 0:
        issues.append(
            issue(
                "gastos_generales_cero",
                IssueSeverity.WARNING,
                "El porcentaje de gastos generales es cero.",
                field="general_expense_percentage",
            )
        )

    line_ids = [product.line_id for product in justification.products if product.line_id]
    duplicate_line_ids = {line_id for line_id, count in Counter(line_ids).items() if count > 1}
    product_keys = [
        (product.name.casefold().strip(), product.characteristics.casefold().strip())
        for product in justification.products
    ]
    duplicate_keys = {key for key, count in Counter(product_keys).items() if count > 1}

    justified_offer = Decimal("0")
    for product in justification.products:
        justified_offer += product.quantity * product.offered_unit_price
        if not product.line_id:
            issues.append(
                issue(
                    "producto_sin_id",
                    IssueSeverity.ERROR,
                    "Cada producto debe tener un identificador de línea estable.",
                    field="line_id",
                )
            )
        elif product.line_id in duplicate_line_ids:
            issues.append(
                issue(
                    "producto_id_duplicado",
                    IssueSeverity.ERROR,
                    "El identificador de línea está duplicado.",
                    field="line_id",
                    line_id=product.line_id,
                )
            )
        if product.quantity < 0:
            issues.append(
                issue(
                    "cantidad_negativa",
                    IssueSeverity.ERROR,
                    "La cantidad del producto no puede ser negativa.",
                    field="quantity",
                    line_id=product.line_id or None,
                )
            )
        if product.offered_unit_price < 0:
            issues.append(
                issue(
                    "precio_ofertado_negativo",
                    IssueSeverity.ERROR,
                    "El precio ofertado no puede ser negativo.",
                    field="offered_unit_price",
                    line_id=product.line_id or None,
                )
            )
        effective_cost = product.effective_unit_cost
        if require_effective_costs and effective_cost is None:
            issues.append(
                issue(
                    "producto_sin_coste_efectivo",
                    IssueSeverity.ERROR,
                    "El producto no tiene un coste generado o manual efectivo.",
                    field="effective_unit_cost",
                    line_id=product.line_id or None,
                )
            )
        if effective_cost is not None and effective_cost < 0:
            issues.append(
                issue(
                    "coste_unitario_negativo",
                    IssueSeverity.ERROR,
                    "El coste unitario efectivo no puede ser negativo.",
                    field="effective_unit_cost",
                    line_id=product.line_id or None,
                )
            )
        if product.cost_origin is CostOrigin.MANUAL:
            issues.append(
                issue(
                    "coste_manual",
                    IssueSeverity.WARNING,
                    "El producto utiliza un coste manual.",
                    field="manual_unit_cost",
                    line_id=product.line_id or None,
                )
            )
        if (
            product.name.casefold().strip(),
            product.characteristics.casefold().strip(),
        ) in duplicate_keys:
            issues.append(
                issue(
                    "producto_nombre_caracteristicas_duplicado",
                    IssueSeverity.WARNING,
                    "Existen productos con el mismo nombre y características.",
                    line_id=product.line_id or None,
                )
            )
        if effective_cost is not None:
            if effective_cost > product.offered_unit_price:
                issues.append(
                    issue(
                        "coste_superior_precio",
                        IssueSeverity.WARNING,
                        "El coste unitario supera al precio ofertado.",
                        line_id=product.line_id or None,
                    )
                )
            margin = product.quantity * (product.offered_unit_price - effective_cost)
            if margin < 0:
                issues.append(
                    issue(
                        "margen_producto_negativo",
                        IssueSeverity.WARNING,
                        "El producto presenta margen negativo.",
                        line_id=product.line_id or None,
                        metadata=(("margen", format(margin, "f")),),
                    )
                )

    if justification.products and justified_offer == 0:
        issues.append(
            issue(
                "oferta_lineas_cero",
                IssueSeverity.ERROR,
                "La suma ofertada de las líneas es cero y no puede prorratearse.",
                field="products",
            )
        )
    if justified_offer != financial.declared_lot_offer:
        issues.append(
            issue(
                "oferta_total_distinta_lineas",
                IssueSeverity.WARNING,
                "La oferta total declarada no coincide con la suma de las líneas.",
                field="declared_lot_offer",
                metadata=(
                    ("oferta_declarada", format(financial.declared_lot_offer, "f")),
                    ("oferta_lineas", format(justified_offer, "f")),
                ),
            )
        )

    duration_issue = _validate_route_duration(justification)
    if duration_issue is not None:
        issues.append(duration_issue)

    return tuple(issues)


def validate_calculated_values(values: EconomicValues) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if values.profit < 0:
        issues.append(
            issue(
                "beneficio_final_negativo",
                IssueSeverity.WARNING,
                "El beneficio final calculado es negativo.",
                field="profit",
                metadata=(("beneficio", format(values.profit, "f")),),
            )
        )
    if values.visual_product_residual != 0:
        issues.append(
            issue(
                "residual_visual_productos",
                IssueSeverity.WARNING,
                "La suma de costes mostrados por línea difiere del total prorrateado.",
                field="visual_product_residual",
                metadata=(("residual", format(values.visual_product_residual, "f")),),
            )
        )
    return tuple(issues)


def _validate_route_duration(justification: Justification) -> ValidationIssue | None:
    text = justification.transport.route_duration_text
    if not text:
        return None
    match = _HUMAN_DURATION_RE.search(text)
    if match is None:
        return None
    hours = Decimal(match.group("hours"))
    minutes = Decimal(match.group("minutes"))
    human_decimal = hours + minutes / Decimal("60")
    difference = abs(human_decimal - justification.transport.effective_decimal_hours)
    if difference < Decimal("0.05"):
        return None
    return issue(
        "tiempo_humano_incoherente",
        IssueSeverity.WARNING,
        "El tiempo humano de la ruta puede no coincidir con las horas decimales efectivas.",
        field="route_duration_text",
        metadata=(
            ("horas_texto", format(human_decimal, "f")),
            ("horas_efectivas", format(justification.transport.effective_decimal_hours, "f")),
        ),
    )
