"""Static economic fixture transcribed from the audited Salvador workbook."""

from __future__ import annotations

from decimal import Decimal

from webapp.infonalia_webapp.justificaciones_baja import (
    CostOrigin,
    CostRange,
    FinancialInput,
    Justification,
    Product,
    TransportInput,
)


# line_id, name, characteristics, quantity, offered price, percentage,
# factor, generated cost and optional effective compatibility/manual cost.
SALVADOR_PRODUCT_DATA: tuple[tuple[str, str, str, str, str, int, str, str, str | None], ...] = (
    ("P01", "BOLLO PAN INTEGRAL", "PAN INTEGRAL 80 G", "44000", "0.19", 42, "1.42", "0.134", None),
    ("P02", "BOLLO PAN INTEGRAL", "PAN INTEGRAL 45 G", "26002", "0.17", 42, "1.42", "0.120", "0.134"),
    ("P03", "BOLLO PAN NORMAL", "PAN NORMAL 80 G", "55000", "0.19", 43, "1.43", "0.133", None),
    ("P04", "BOLLO PAN NORMAL", "PAN NORMAL 45 G", "44000", "0.17", 42, "1.42", "0.120", "0.133"),
    ("P05", "BOLLO PAN TIERNO", "PAN TIERNO 85 G", "30000", "0.19", 47, "1.47", "0.129", None),
    ("P06", "BOLLO PAN TIERNO", "PAN TIERNO 55 G", "50000", "0.18", 41, "1.41", "0.128", "0.129"),
    ("P07", "PAN REDONDO", "HOGAZA 1 KG", "600", "1.90", 44, "1.44", "1.319", None),
    ("P08", "HARINA TRIGO", "SACO 25 KG", "20", "13.75", 41, "1.41", "9.752", None),
    ("P09", "HARINA DE FUERZA", "BOLSA 1 KG", "20", "0.70", 46, "1.46", "0.479", None),
    ("P10", "MEDIAS NOCHES", "TAMAÑO MEDIO", "600", "0.19", 45, "1.45", "0.131", None),
    ("P11", "PAN RALLADO", "BOLSA 5 KG", "100", "4.50", 47, "1.47", "3.061", None),
    ("P12", "PAN DE MOLDE TRAMESINI", "BOLSA 1 KG", "20", "4.90", 45, "1.45", "3.379", None),
    ("P13", "PAN DE MOLDE", "BOLSA 800 G", "100", "1.20", 40, "1.40", "0.857", None),
    ("P14", "SALAILLA PEQUEÑA", "PANECILLO PEQUEÑO", "300", "0.25", 41, "1.41", "0.177", None),
    ("P15", "LEVADURA FRESCA", "FORMATO 500 G", "20", "2.60", 43, "1.43", "1.818", None),
    ("P16", "LEVADURA FRESCA", "FORMATO 25 G", "36", "0.48", 46, "1.46", "0.329", "0.329"),
    ("P17", "BOLLERÍA", "BOLLO DULCE 110 G", "25000", "0.85", 44, "1.44", "0.590", None),
    ("P18", "ROSCOS FRITOS", "CAJA 2 KG", "20", "11", 47, "1.47", "7.483", None),
    ("P19", "ROSCOS FRITOS SIN AZÚCAR", "CAJA 2 KG", "20", "11", 44, "1.44", "7.639", None),
    ("P20", "PESTIÑOS FRITOS SIN AZÚCAR", "CAJA 2 KG", "20", "14", 45, "1.45", "9.655", None),
    ("P21", "PESTIÑOS FRITOS", "CAJA 2 KG", "20", "11", 44, "1.44", "7.639", None),
    ("P22", "ROSCÓN DE REYES", "NATA 1,5 KG", "30", "16", 45, "1.45", "11.034", None),
    ("P23", "TORTA DE LA VIRGEN", "CABELLO DE ÁNGEL 1 KG", "24", "12", 41, "1.41", "8.511", None),
    ("P24", "MAGDALENA INTEGRAL", "CAJA 2 KG", "428", "13", 46, "1.46", "8.904", None),
    ("P25", "BIZCOCHO EN PLANCHA", "PLANCHA 60X40", "40", "26", 41, "1.41", "18.440", None),
    ("P26", "TRONCO DE NAVIDAD", "PIEZA 1 KG", "100", "13", 47, "1.47", "8.844", None),
)


def salvador_justification(
    *,
    shared_orders: int = 25,
    kilometre_rate: str = "0.6776",
    hourly_rate: str = "39.75",
    operational_weeks: int = 104,
    weekly_deliveries: int = 7,
) -> Justification:
    products = tuple(
        Product(
            line_id=line_id,
            name=name,
            characteristics=characteristics,
            quantity=Decimal(quantity),
            offered_unit_price=Decimal(offered_price),
            applied_percentage=percentage,
            applied_factor=Decimal(factor),
            generated_unit_cost=Decimal(generated_cost),
            manual_unit_cost=Decimal(manual_cost) if manual_cost is not None else None,
            cost_origin=CostOrigin.MANUAL if manual_cost is not None else CostOrigin.GENERATED,
        )
        for (
            line_id,
            name,
            characteristics,
            quantity,
            offered_price,
            percentage,
            factor,
            generated_cost,
            manual_cost,
        ) in SALVADOR_PRODUCT_DATA
    )
    return Justification(
        lot_identifier="LOTE-1",
        products=products,
        transport=TransportInput(
            operational_weeks=operational_weeks,
            weekly_deliveries=weekly_deliveries,
            circular_kilometres=Decimal("250"),
            effective_decimal_hours=Decimal("2.7"),
            kilometre_rate=Decimal(kilometre_rate),
            hourly_rate=Decimal(hourly_rate),
            contract_stops=1,
            shared_orders=shared_orders,
            descriptive_months=24,
            route_duration_text="2 h 41 min",
        ),
        financial=FinancialInput(
            declared_lot_offer=Decimal("78627.62"),
            general_expense_base=Decimal("78627.62"),
            general_expense_percentage=Decimal("0.1"),
            indirect_costs=None,
        ),
        cost_range=CostRange(minimum_percentage=40, maximum_percentage=47),
    )
