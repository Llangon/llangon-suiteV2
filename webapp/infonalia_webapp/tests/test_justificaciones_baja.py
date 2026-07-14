from __future__ import annotations

import ast
import importlib
import json
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from webapp.infonalia_webapp.justificaciones_baja import (
    CostOrigin,
    CostRange,
    DomainValueError,
    FinancialInput,
    Justification,
    Product,
    SnapshotMetadata,
    TransportInput,
    calculate_generated_unit_cost,
    calculate_justification,
    create_snapshot,
    economic_payload,
    generate_initial_costs,
    load_snapshot,
    recalculate_products,
    remove_manual_cost,
    set_manual_cost,
    set_product_lock,
)
from webapp.infonalia_webapp.tests.fixtures.justificaciones_baja_salvador import (
    salvador_justification,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "justificaciones_baja"


class SequenceRandom:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)
        self.calls = 0

    def randint(self, minimum: int, maximum: int) -> int:
        value = self.values[self.calls]
        self.calls += 1
        assert minimum <= value <= maximum
        return value


def product(
    line_id: str,
    *,
    price: str = "10",
    quantity: str = "1",
    percentage: int | None = 40,
    generated_cost: str | None = "7.143",
    manual_cost: str | None = None,
    locked: bool = False,
) -> Product:
    if manual_cost is not None:
        origin = CostOrigin.MANUAL
    elif generated_cost is not None:
        origin = CostOrigin.GENERATED
    else:
        origin = CostOrigin.UNGENERATED
    factor = (
        Decimal("1") + Decimal(percentage) / Decimal("100")
        if percentage is not None
        else None
    )
    return Product(
        line_id=line_id,
        name=f"Producto {line_id}",
        characteristics="Formato de prueba",
        quantity=Decimal(quantity),
        offered_unit_price=Decimal(price),
        applied_percentage=percentage,
        applied_factor=factor,
        generated_unit_cost=(
            Decimal(generated_cost) if generated_cost is not None else None
        ),
        manual_unit_cost=Decimal(manual_cost) if manual_cost is not None else None,
        locked=locked,
        cost_origin=origin,
    )


def justification(
    products: tuple[Product, ...],
    *,
    declared_offer: str | None = None,
    minimum: int = 40,
    maximum: int = 47,
    shared_orders: int = 1,
    weeks: int = 0,
    deliveries: int = 0,
    kilometres: str = "0",
    hours: str = "0",
    kilometre_rate: str = "0",
    hourly_rate: str = "0",
    general_base: str = "0",
    general_percentage: str = "0",
    indirect_costs: str | None = "0",
    descriptive_months: int | None = None,
) -> Justification:
    offer = sum(
        (item.quantity * item.offered_unit_price for item in products),
        Decimal("0"),
    )
    return Justification(
        lot_identifier="LOT-TEST",
        products=products,
        transport=TransportInput(
            operational_weeks=weeks,
            weekly_deliveries=deliveries,
            circular_kilometres=Decimal(kilometres),
            effective_decimal_hours=Decimal(hours),
            kilometre_rate=Decimal(kilometre_rate),
            hourly_rate=Decimal(hourly_rate),
            contract_stops=1,
            shared_orders=shared_orders,
            descriptive_months=descriptive_months,
        ),
        financial=FinancialInput(
            declared_lot_offer=Decimal(declared_offer) if declared_offer else offer,
            general_expense_base=Decimal(general_base),
            general_expense_percentage=Decimal(general_percentage),
            indirect_costs=(
                Decimal(indirect_costs) if indirect_costs is not None else None
            ),
        ),
        cost_range=CostRange(minimum_percentage=minimum, maximum_percentage=maximum),
    )


def warning_codes(result) -> set[str]:
    return {item.code for item in result.warnings}


def error_codes(result) -> set[str]:
    return {item.code for item in result.errors}


def test_01_golden_salvador_reproduces_raw_and_displayed_values() -> None:
    draft = salvador_justification()
    result = calculate_justification(draft)

    assert result.is_valid
    assert result.values is not None
    values = result.values
    assert len(values.product_lines) == 26
    assert values.declared_lot_offer == Decimal("78627.62")
    assert values.justified_lines_offer == Decimal("78627.62")
    assert values.raw_product_cost == Decimal("55869.088")
    assert values.prorated_product_cost == Decimal("55869.09")
    assert values.gross_margin == Decimal("22758.53")
    assert values.display.gross_margin_percentage == "28,94 %"
    assert values.total_services == 728
    assert values.temporal_cost == Decimal("78132.60")
    assert values.kilometre_cost == Decimal("123323.20")
    assert values.full_route_cost == Decimal("201455.80")
    assert values.allocated_transport == Decimal("8058.232")
    assert values.display.allocated_transport == "8.058,23"
    assert values.general_expenses == Decimal("7862.762")
    assert values.display.general_expenses == "7.862,76"
    assert values.total_cost == Decimal("71790.084")
    assert values.display.total_cost == "71.790,08"
    assert values.profit == Decimal("6837.536")
    assert values.display.profit == "6.837,54"
    assert values.display.profit_percentage == "8,70 %"
    assert values.visual_product_residual == Decimal("0.01")
    assert values.display.visual_product_residual == "0,01"
    raw_payload = economic_payload(result)["values"]["raw"]
    assert raw_payload["general_expenses"] == "7862.762"
    assert raw_payload["total_cost"] == "71790.084"
    assert raw_payload["profit"] == "6837.536"
    assert warning_codes(result) >= {
        "costes_indirectos_ausentes",
        "coste_manual",
        "residual_visual_productos",
    }


def test_02_small_price_rounds_generated_unit_cost_to_three_decimals() -> None:
    draft = justification(
        (product("P1", price="0.01", generated_cost=None, percentage=None),),
        minimum=47,
        maximum=47,
    )
    random_source = SequenceRandom([47])

    generated = generate_initial_costs(draft, random_source)

    assert generated.is_valid
    assert generated.justification.products[0].generated_unit_cost == Decimal("0.007")
    assert generated.justification.products[0].applied_percentage == 47
    assert random_source.calls == 1


def test_03_negative_product_margin_is_warning_not_error() -> None:
    draft = justification(
        (product("P1", price="1.00", quantity="10", percentage=None, generated_cost=None, manual_cost="1.100"),)
    )

    result = calculate_justification(draft)

    assert result.is_valid
    assert result.values is not None
    assert result.values.raw_product_cost == Decimal("11.000")
    assert result.values.profit == Decimal("-1.00")
    assert {"coste_superior_precio", "margen_producto_negativo", "beneficio_final_negativo"} <= warning_codes(result)


def test_04_manual_edit_preserves_generated_cost_and_becomes_effective() -> None:
    draft = justification((product("P1", quantity="2"),))

    edited = set_manual_cost(draft, "P1", Decimal("7.500"))
    result = calculate_justification(edited.justification)

    assert edited.is_valid
    changed = edited.justification.products[0]
    assert changed.generated_unit_cost == Decimal("7.143")
    assert changed.manual_unit_cost == Decimal("7.500")
    assert changed.effective_unit_cost == Decimal("7.500")
    assert changed.cost_origin is CostOrigin.MANUAL
    assert result.values is not None
    assert result.values.raw_product_cost == Decimal("15.000")
    assert result.values.product_lines[0].margin == Decimal("5.000")


def test_05_selective_recalculation_never_changes_a_locked_product() -> None:
    draft = justification(
        (
            product("A", generated_cost=None, percentage=None),
            product("B", generated_cost=None, percentage=None),
            product("C", generated_cost=None, percentage=None),
        )
    )
    initial_random = SequenceRandom([40, 40, 40])
    initial = generate_initial_costs(draft, initial_random).justification
    locked = set_product_lock(initial, "A", locked=True).justification
    recalc_random = SequenceRandom([47])

    recalculated = recalculate_products(locked, {"A", "B"}, recalc_random)

    by_id = {item.line_id: item for item in recalculated.justification.products}
    assert by_id["A"].generated_unit_cost == Decimal("7.143")
    assert by_id["A"].applied_percentage == 40
    assert by_id["B"].generated_unit_cost == Decimal("6.803")
    assert by_id["B"].applied_percentage == 47
    assert by_id["C"].generated_unit_cost == Decimal("7.143")
    assert by_id["C"].applied_percentage == 40
    assert recalc_random.calls == 1


def test_06_changing_range_only_takes_effect_after_explicit_recalculation() -> None:
    draft = justification(
        (product("P1", price="0.19", generated_cost=None, percentage=None),),
        minimum=40,
        maximum=40,
    )
    generated = generate_initial_costs(draft, SequenceRandom([40])).justification
    changed_range = replace(
        generated,
        cost_range=CostRange(minimum_percentage=47, maximum_percentage=47),
    )

    assert changed_range.products[0].generated_unit_cost == Decimal("0.136")
    recalculated = recalculate_products(changed_range, {"P1"}, SequenceRandom([47]))
    assert recalculated.justification.products[0].generated_unit_cost == Decimal("0.129")


def test_07_shared_orders_change_transport_by_direct_division() -> None:
    at_25 = calculate_justification(salvador_justification(shared_orders=25))
    at_20 = calculate_justification(salvador_justification(shared_orders=20))

    assert at_25.values is not None and at_20.values is not None
    assert at_25.values.allocated_transport == Decimal("8058.232")
    assert at_20.values.allocated_transport == Decimal("10072.79")
    assert at_20.values.display.allocated_transport == "10.072,79"


def test_08_changed_kilometre_rate_recalculates_transport() -> None:
    result = calculate_justification(salvador_justification(kilometre_rate="0.7000"))

    assert result.values is not None
    assert result.values.kilometre_cost == Decimal("127400.00")
    assert result.values.full_route_cost == Decimal("205532.60")
    assert result.values.allocated_transport == Decimal("8221.304")
    assert result.values.display.allocated_transport == "8.221,30"


def test_09_changed_hourly_rate_recalculates_transport() -> None:
    result = calculate_justification(salvador_justification(hourly_rate="40.00"))

    assert result.values is not None
    assert result.values.temporal_cost == Decimal("78624.00")
    assert result.values.full_route_cost == Decimal("201947.20")
    assert result.values.allocated_transport == Decimal("8077.888")
    assert result.values.display.allocated_transport == "8.077,89"


def test_10_descriptive_months_do_not_replace_operational_weeks() -> None:
    draft = salvador_justification(operational_weeks=104, weekly_deliveries=7)
    changed_months = replace(
        draft,
        transport=replace(draft.transport, descriptive_months=1),
    )

    result = calculate_justification(changed_months)

    assert result.values is not None
    assert changed_months.transport.descriptive_months == 1
    assert result.values.total_services == 728


def test_11_multiple_weekly_deliveries_multiply_operational_weeks() -> None:
    result = calculate_justification(
        salvador_justification(operational_weeks=10, weekly_deliveries=3)
    )

    assert result.values is not None
    assert result.values.total_services == 30
    assert result.values.temporal_cost == Decimal("3219.75")
    assert result.values.kilometre_cost == Decimal("5082.00")


def test_12_visual_cent_residual_is_kept_and_warned_without_redistribution() -> None:
    result = calculate_justification(salvador_justification())

    assert result.values is not None
    assert result.values.visible_product_cost_sum == Decimal("55869.08")
    assert result.values.prorated_product_cost == Decimal("55869.09")
    assert result.values.visual_product_residual == Decimal("0.01")
    assert "residual_visual_productos" in warning_codes(result)


def test_13_snapshot_reopening_preserves_costs_and_does_not_generate() -> None:
    draft = salvador_justification()
    calculation = calculate_justification(draft)
    built = create_snapshot(
        draft,
        calculation,
        SnapshotMetadata(created_at="2026-07-14T12:00:00+02:00", created_by="test"),
    )

    assert built.snapshot is not None
    reopened = load_snapshot(built.snapshot.to_json())

    assert reopened.is_valid
    assert reopened.snapshot is not None
    assert reopened.snapshot.justification.products == draft.products
    assert economic_payload(reopened.snapshot.calculation) == economic_payload(calculation)
    assert reopened.snapshot.to_json() == built.snapshot.to_json()


def test_14_two_logical_document_payloads_from_snapshot_are_identical() -> None:
    draft = salvador_justification()
    calculation = calculate_justification(draft)
    built = create_snapshot(
        draft,
        calculation,
        SnapshotMetadata(created_at="2026-07-14T12:00:00+02:00"),
    )

    assert built.snapshot is not None
    first_payload = economic_payload(built.snapshot.calculation)
    second_payload = economic_payload(built.snapshot.calculation)
    assert first_payload == second_payload
    assert first_payload["values"]["display"]["profit"] == "6.837,54"


def test_float_is_rejected_in_domain_inputs() -> None:
    with pytest.raises(DomainValueError) as exc_info:
        Product(
            line_id="P1",
            name="Producto",
            quantity=1.0,  # type: ignore[arg-type]
            offered_unit_price=Decimal("1.00"),
        )

    assert exc_info.value.code == "tipo_decimal_invalido"
    assert exc_info.value.field == "quantity"


def test_invalid_range_returns_structured_error_without_calling_random() -> None:
    draft = justification(
        (product("P1", generated_cost=None, percentage=None),),
        minimum=47,
        maximum=40,
    )
    random_source = SequenceRandom([])

    action = generate_initial_costs(draft, random_source)
    calculation = calculate_justification(draft)

    assert error_codes(action) == {"horquilla_invalida"}
    assert "horquilla_invalida" in error_codes(calculation)
    assert random_source.calls == 0


def test_zero_shared_orders_returns_structured_error() -> None:
    result = calculate_justification(
        justification((product("P1"),), shared_orders=0)
    )

    assert not result.is_valid
    assert "pedidos_compartidos_no_positivos" in error_codes(result)


def test_product_without_stable_id_returns_structured_error() -> None:
    result = calculate_justification(justification((product(""),)))

    assert not result.is_valid
    assert "producto_sin_id" in error_codes(result)


def test_declared_offer_different_from_lines_is_warning() -> None:
    result = calculate_justification(
        justification((product("P1"),), declared_offer="11")
    )

    assert result.is_valid
    assert "oferta_total_distinta_lineas" in warning_codes(result)
    assert result.values is not None
    assert result.values.raw_product_cost == Decimal("7.143")
    assert result.values.prorated_product_cost == Decimal("7.86")


def test_absent_indirect_costs_are_zero_and_warning() -> None:
    result = calculate_justification(
        justification((product("P1"),), indirect_costs=None)
    )

    assert result.values is not None
    assert result.values.indirect_costs == Decimal("0")
    assert "costes_indirectos_ausentes" in warning_codes(result)


def test_removing_manual_cost_restores_previous_generated_cost_without_random() -> None:
    draft = justification(
        (product("P1", generated_cost="7.143", manual_cost="7.500"),)
    )

    restored = remove_manual_cost(draft, "P1")

    assert restored.is_valid
    changed = restored.justification.products[0]
    assert changed.manual_unit_cost is None
    assert changed.generated_unit_cost == Decimal("7.143")
    assert changed.effective_unit_cost == Decimal("7.143")
    assert changed.cost_origin is CostOrigin.GENERATED


def test_snapshot_serializes_decimals_as_strings_and_roundtrips_without_loss() -> None:
    draft = salvador_justification(kilometre_rate="0.7000")
    calculation = calculate_justification(draft)
    built = create_snapshot(
        draft,
        calculation,
        SnapshotMetadata(created_at="2026-07-14T12:00:00+02:00"),
    )

    assert built.snapshot is not None
    payload = built.snapshot.to_dict()
    assert payload["input"]["transport"]["kilometre_rate"] == "0.7000"
    assert isinstance(payload["input"]["products"][0]["quantity"], str)
    assert isinstance(payload["calculation"]["values"]["raw"]["profit"], str)
    reopened = load_snapshot(payload)
    assert reopened.snapshot is not None
    assert reopened.snapshot.justification.transport.kilometre_rate == Decimal("0.7000")
    assert reopened.snapshot.to_json() == built.snapshot.to_json()


def test_canonical_json_is_stable_and_utf8_safe() -> None:
    draft = salvador_justification()
    calculation = calculate_justification(draft)
    built = create_snapshot(
        draft,
        calculation,
        SnapshotMetadata(created_at="2026-07-14T12:00:00+02:00", created_by="asesoría"),
    )

    assert built.snapshot is not None
    first = built.snapshot.to_json()
    second = built.snapshot.to_json()
    assert first == second
    assert "asesoría" in first
    assert "asesor\\u00eda" not in first
    assert json.loads(first)["schema_version"] == "1"


def test_incompatible_snapshot_returns_structured_error() -> None:
    result = load_snapshot({"schema_version": "999", "algorithm_version": "1.0.0"})

    assert not result.is_valid
    assert error_codes(result) == {"snapshot_incompatible"}


def test_generation_formula_matches_excel_round_half_up_examples() -> None:
    assert calculate_generated_unit_cost(Decimal("0.19"), 40) == Decimal("0.136")
    assert calculate_generated_unit_cost(Decimal("0.19"), 47) == Decimal("0.129")
    assert calculate_generated_unit_cost(Decimal("13"), 45) == Decimal("8.966")


def test_golden_fixture_generated_costs_match_all_audited_effective_factors() -> None:
    draft = salvador_justification()

    for item in draft.products:
        assert item.applied_percentage is not None
        assert item.generated_unit_cost == calculate_generated_unit_cost(
            item.offered_unit_price,
            item.applied_percentage,
        )


def test_initial_generation_does_not_regenerate_existing_products() -> None:
    draft = justification(
        (
            product("A", generated_cost="7.143", percentage=40),
            product("B", generated_cost=None, percentage=None),
        )
    )
    random_source = SequenceRandom([47])

    generated = generate_initial_costs(draft, random_source)

    by_id = {item.line_id: item for item in generated.justification.products}
    assert by_id["A"].generated_unit_cost == Decimal("7.143")
    assert by_id["B"].generated_unit_cost == Decimal("6.803")
    assert random_source.calls == 1


def test_package_imports_have_no_forbidden_dependencies_or_side_effect_modules() -> None:
    package_modules = [
        name
        for name in list(sys.modules)
        if name.startswith("webapp.infonalia_webapp.justificaciones_baja")
    ]
    for module_name in package_modules:
        sys.modules.pop(module_name, None)
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.justificaciones_baja")

    added = set(sys.modules) - before
    forbidden_added = {
        "sqlite3",
        "requests",
        "http.server",
        "openpyxl",
        "docx",
        "pandas",
        "numpy",
        "webapp.infonalia_webapp.app",
    }
    assert not (forbidden_added & added)

    forbidden_import_roots = {
        "sqlite3",
        "requests",
        "random",
        "pathlib",
        "os",
        "socket",
        "urllib",
        "openpyxl",
        "docx",
        "pandas",
        "numpy",
        "app",
    }
    for source_path in PACKAGE_ROOT.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        float_literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, float)
        ]
        assert not float_literals, source_path.name
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
        assert not (roots & forbidden_import_roots), source_path.name
