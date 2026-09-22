"""Local document tooling for Ficha Llangon v2.

This package is intentionally independent from the private web application's
request lifecycle.  It may be called from the Excel bridge without importing
``app.py`` or opening a writable database connection.
"""

from .payload import PAYLOAD_SCHEMA_VERSION, TEMPLATE_VERSION, normalize_payload
from .validation import ValidationIssue, validate_payload

__all__ = (
    "PAYLOAD_SCHEMA_VERSION",
    "TEMPLATE_VERSION",
    "ValidationIssue",
    "normalize_payload",
    "validate_payload",
)
