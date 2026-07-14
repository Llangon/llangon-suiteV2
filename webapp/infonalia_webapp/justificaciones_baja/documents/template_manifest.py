"""Closed manifest for the versioned Word justification template."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PAYLOAD_SCHEMA_VERSION = "1"
WORD_TEMPLATE_VERSION = "JB-WORD-V1"
WORD_TEMPLATE_FILENAME = "justificacion_baja_v1.docx"
WORD_TEMPLATE_SENTINEL = "PLANTILLA_JB_V1"

REQUIRED_TEMPLATE_VARIABLES = frozenset(
    {
        "control",
        "identification",
        "narrative",
        "products",
        "products_empty",
        "transport",
        "summary",
        "route_image",
        "route_image_note",
        "show_indirect_costs",
    }
)
OPTIONAL_TEMPLATE_VARIABLES = frozenset()
REPEATABLE_BLOCKS = frozenset({"narrative.arguments", "products"})
IMAGE_VARIABLES = frozenset({"route_image"})
REQUIRED_TEMPLATE_MARKERS = frozenset(
    {
        "{%p endfor %}",
        "{%p endif %}",
        "{%p for argument in narrative.arguments %}",
        "{%p if products_empty %}",
        "{%tr endfor %}",
        "{%tr endif %}",
        "{%tr for product in products %}",
        "{%tr if show_indirect_costs %}",
        "{{ argument }}",
        "{{ control.snapshot_sha256 }}",
        "{{ control.template_version }}",
        "{{ identification.address }}",
        "{{ identification.client }}",
        "{{ identification.date_text }}",
        "{{ identification.duration_description }}",
        "{{ identification.expediente }}",
        "{{ identification.lot_name }}",
        "{{ identification.lot_number }}",
        "{{ identification.nif }}",
        "{{ identification.objeto }}",
        "{{ identification.organismo }}",
        "{{ identification.place }}",
        "{{ identification.representative }}",
        "{{ identification.representative_dni }}",
        "{{ identification.role }}",
        "{{ identification.signatory }}",
        "{{ narrative.acquisition_text }}",
        "{{ narrative.conclusion }}",
        "{{ narrative.confidentiality_text }}",
        "{{ narrative.estimated_draft_notice }}",
        "{{ narrative.exposition }}",
        "{{ narrative.structure_text }}",
        "{{ narrative.subject }}",
        "{{ narrative.transport_text }}",
        "{{ product.characteristics }}",
        "{{ product.cost_amount.display }}",
        "{{ product.effective_unit_cost.display }}",
        "{{ product.name }}",
        "{{ product.offered_amount.display }}",
        "{{ product.offered_unit_price.display }}",
        "{{ product.quantity.display }}",
        "{{ route_image }}",
        "{{ route_image_note }}",
        "{{ summary.allocated_transport.display }}",
        "{{ summary.general_expenses.display }}",
        "{{ summary.gross_margin.display }}",
        "{{ summary.gross_margin_percentage.display }}",
        "{{ summary.indirect_costs.display }}",
        "{{ summary.justified_lines_offer.display }}",
        "{{ summary.offer.display }}",
        "{{ summary.profit.display }}",
        "{{ summary.profit_percentage.display }}",
        "{{ summary.prorated_product_cost.display }}",
        "{{ summary.total_cost.display }}",
        "{{ transport.allocated_transport.display }}",
        "{{ transport.circular_kilometres.display }}",
        "{{ transport.effective_decimal_hours.display }}",
        "{{ transport.full_route_cost.display }}",
        "{{ transport.hourly_rate.display }}",
        "{{ transport.kilometre_cost.display }}",
        "{{ transport.kilometre_rate.display }}",
        "{{ transport.observatory }}",
        "{{ transport.observatory_date }}",
        "{{ transport.route_duration_text }}",
        "{{ transport.shared_orders }}",
        "{{ transport.temporal_cost.display }}",
        "{{ transport.total_services }}",
        "{{ transport.vehicle }}",
    }
)


@dataclass(frozen=True, slots=True)
class TemplateManifest:
    version: str = WORD_TEMPLATE_VERSION
    filename: str = WORD_TEMPLATE_FILENAME
    sentinel: str = WORD_TEMPLATE_SENTINEL
    required_variables: frozenset[str] = REQUIRED_TEMPLATE_VARIABLES
    optional_variables: frozenset[str] = OPTIONAL_TEMPLATE_VARIABLES
    repeatable_blocks: frozenset[str] = REPEATABLE_BLOCKS
    image_variables: frozenset[str] = IMAGE_VARIABLES
    required_markers: frozenset[str] = REQUIRED_TEMPLATE_MARKERS

    @property
    def allowed_variables(self) -> frozenset[str]:
        return self.required_variables | self.optional_variables


DEFAULT_TEMPLATE_MANIFEST = TemplateManifest()
DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / WORD_TEMPLATE_FILENAME


__all__ = (
    "DEFAULT_TEMPLATE_MANIFEST",
    "DEFAULT_TEMPLATE_PATH",
    "IMAGE_VARIABLES",
    "OPTIONAL_TEMPLATE_VARIABLES",
    "PAYLOAD_SCHEMA_VERSION",
    "REPEATABLE_BLOCKS",
    "REQUIRED_TEMPLATE_MARKERS",
    "REQUIRED_TEMPLATE_VARIABLES",
    "TemplateManifest",
    "WORD_TEMPLATE_FILENAME",
    "WORD_TEMPLATE_SENTINEL",
    "WORD_TEMPLATE_VERSION",
)
