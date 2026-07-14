"""Pure domain objects for one abnormally-low-bid justification lot."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias


DecimalInput: TypeAlias = Decimal | str | int
IssueMetadata: TypeAlias = tuple[tuple[str, str], ...]


class DomainValueError(ValueError):
    """Raised when a value cannot enter the decimal-safe domain."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field


def decimal_value(value: object, field: str) -> Decimal:
    """Create a finite Decimal without ever accepting binary floats."""

    if isinstance(value, bool) or isinstance(value, float):
        raise DomainValueError(
            "tipo_decimal_invalido",
            field,
            f"{field} debe recibirse como Decimal, string decimal o entero; no se admite float.",
        )
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise DomainValueError(
                "decimal_invalido",
                field,
                f"{field} no contiene un decimal canónico válido.",
            ) from exc
    else:
        raise DomainValueError(
            "tipo_decimal_invalido",
            field,
            f"{field} debe recibirse como Decimal, string decimal o entero.",
        )
    if not result.is_finite():
        raise DomainValueError(
            "decimal_no_finito",
            field,
            f"{field} debe ser un decimal finito.",
        )
    return result


def optional_decimal_value(value: object | None, field: str) -> Decimal | None:
    if value is None:
        return None
    return decimal_value(value, field)


def integer_value(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainValueError(
            "entero_invalido",
            field,
            f"{field} debe ser un entero.",
        )
    return value


class CostOrigin(str, Enum):
    UNGENERATED = "sin_generar"
    GENERATED = "generado"
    MANUAL = "manual"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "advertencia"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    field: str | None = None
    line_id: str | None = None
    metadata: IssueMetadata = ()

    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)


@dataclass(frozen=True, slots=True)
class Product:
    line_id: str
    name: str
    quantity: Decimal
    offered_unit_price: Decimal
    characteristics: str = ""
    applied_percentage: int | None = None
    applied_factor: Decimal | None = None
    generated_unit_cost: Decimal | None = None
    manual_unit_cost: Decimal | None = None
    locked: bool = False
    cost_origin: CostOrigin = CostOrigin.UNGENERATED

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_id", str(self.line_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "characteristics", str(self.characteristics).strip())
        object.__setattr__(self, "quantity", decimal_value(self.quantity, "quantity"))
        object.__setattr__(
            self,
            "offered_unit_price",
            decimal_value(self.offered_unit_price, "offered_unit_price"),
        )
        object.__setattr__(
            self,
            "applied_factor",
            optional_decimal_value(self.applied_factor, "applied_factor"),
        )
        object.__setattr__(
            self,
            "generated_unit_cost",
            optional_decimal_value(self.generated_unit_cost, "generated_unit_cost"),
        )
        object.__setattr__(
            self,
            "manual_unit_cost",
            optional_decimal_value(self.manual_unit_cost, "manual_unit_cost"),
        )
        if self.applied_percentage is not None:
            object.__setattr__(
                self,
                "applied_percentage",
                integer_value(self.applied_percentage, "applied_percentage"),
            )
        if isinstance(self.cost_origin, str) and not isinstance(self.cost_origin, CostOrigin):
            try:
                object.__setattr__(self, "cost_origin", CostOrigin(self.cost_origin))
            except ValueError as exc:
                raise DomainValueError(
                    "origen_coste_invalido",
                    "cost_origin",
                    "El origen del coste no es compatible con el dominio.",
                ) from exc

    @property
    def effective_unit_cost(self) -> Decimal | None:
        if self.cost_origin is CostOrigin.MANUAL:
            return self.manual_unit_cost
        if self.cost_origin is CostOrigin.GENERATED:
            return self.generated_unit_cost
        return None


@dataclass(frozen=True, slots=True)
class TransportInput:
    operational_weeks: int
    weekly_deliveries: int
    circular_kilometres: Decimal
    effective_decimal_hours: Decimal
    kilometre_rate: Decimal
    hourly_rate: Decimal
    contract_stops: int
    shared_orders: int
    descriptive_months: int | None = None
    route_duration_text: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operational_weeks",
            integer_value(self.operational_weeks, "operational_weeks"),
        )
        object.__setattr__(
            self,
            "weekly_deliveries",
            integer_value(self.weekly_deliveries, "weekly_deliveries"),
        )
        object.__setattr__(
            self,
            "circular_kilometres",
            decimal_value(self.circular_kilometres, "circular_kilometres"),
        )
        object.__setattr__(
            self,
            "effective_decimal_hours",
            decimal_value(self.effective_decimal_hours, "effective_decimal_hours"),
        )
        object.__setattr__(
            self,
            "kilometre_rate",
            decimal_value(self.kilometre_rate, "kilometre_rate"),
        )
        object.__setattr__(self, "hourly_rate", decimal_value(self.hourly_rate, "hourly_rate"))
        object.__setattr__(
            self,
            "contract_stops",
            integer_value(self.contract_stops, "contract_stops"),
        )
        object.__setattr__(
            self,
            "shared_orders",
            integer_value(self.shared_orders, "shared_orders"),
        )
        if self.descriptive_months is not None:
            object.__setattr__(
                self,
                "descriptive_months",
                integer_value(self.descriptive_months, "descriptive_months"),
            )
        if self.route_duration_text is not None:
            object.__setattr__(self, "route_duration_text", str(self.route_duration_text).strip())


@dataclass(frozen=True, slots=True)
class FinancialInput:
    declared_lot_offer: Decimal
    general_expense_base: Decimal
    general_expense_percentage: Decimal
    indirect_costs: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "declared_lot_offer",
            decimal_value(self.declared_lot_offer, "declared_lot_offer"),
        )
        object.__setattr__(
            self,
            "general_expense_base",
            decimal_value(self.general_expense_base, "general_expense_base"),
        )
        object.__setattr__(
            self,
            "general_expense_percentage",
            decimal_value(self.general_expense_percentage, "general_expense_percentage"),
        )
        object.__setattr__(
            self,
            "indirect_costs",
            optional_decimal_value(self.indirect_costs, "indirect_costs"),
        )


@dataclass(frozen=True, slots=True)
class CostRange:
    minimum_percentage: int
    maximum_percentage: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_percentage",
            integer_value(self.minimum_percentage, "minimum_percentage"),
        )
        object.__setattr__(
            self,
            "maximum_percentage",
            integer_value(self.maximum_percentage, "maximum_percentage"),
        )


@dataclass(frozen=True, slots=True)
class Justification:
    lot_identifier: str
    products: tuple[Product, ...]
    transport: TransportInput
    financial: FinancialInput
    cost_range: CostRange

    def __post_init__(self) -> None:
        object.__setattr__(self, "lot_identifier", str(self.lot_identifier).strip())
        object.__setattr__(self, "products", tuple(self.products))


@dataclass(frozen=True, slots=True)
class ProductLineDisplay:
    offered_unit_price: str
    effective_unit_cost: str
    offered_amount: str
    cost_amount: str
    margin: str


@dataclass(frozen=True, slots=True)
class ProductLineResult:
    line_id: str
    name: str
    characteristics: str
    quantity: Decimal
    offered_unit_price: Decimal
    effective_unit_cost: Decimal
    offered_amount: Decimal
    cost_amount: Decimal
    margin: Decimal
    display: ProductLineDisplay


@dataclass(frozen=True, slots=True)
class EconomicDisplay:
    declared_lot_offer: str
    justified_lines_offer: str
    raw_product_cost: str
    prorated_product_cost: str
    gross_margin: str
    gross_margin_percentage: str
    temporal_cost: str
    kilometre_cost: str
    full_route_cost: str
    narrative_percentage: str
    allocated_transport: str
    general_expenses: str
    indirect_costs: str
    total_cost: str
    profit: str
    profit_percentage: str
    visible_product_cost_sum: str
    visual_product_residual: str


@dataclass(frozen=True, slots=True)
class EconomicValues:
    product_lines: tuple[ProductLineResult, ...]
    declared_lot_offer: Decimal
    justified_lines_offer: Decimal
    raw_product_cost: Decimal
    prorated_product_cost: Decimal
    gross_margin: Decimal
    gross_margin_percentage: Decimal
    total_services: int
    temporal_cost: Decimal
    kilometre_cost: Decimal
    full_route_cost: Decimal
    narrative_percentage: Decimal
    allocated_transport: Decimal
    general_expenses: Decimal
    indirect_costs: Decimal
    total_cost: Decimal
    profit: Decimal
    profit_percentage: Decimal
    visible_product_cost_sum: Decimal
    visual_product_residual: Decimal
    display: EconomicDisplay


@dataclass(frozen=True, slots=True)
class CalculationResult:
    values: EconomicValues | None
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.values is not None and not self.errors


@dataclass(frozen=True, slots=True)
class CostActionResult:
    justification: Justification
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors
