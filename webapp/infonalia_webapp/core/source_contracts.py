"""Pure contracts for future licitation sources."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from .models import LicitacionCandidate, LicitacionNormalized


@runtime_checkable
class LicitationSource(Protocol):
    """Conceptual source of licitation candidates.

    Implementations must not write to SQLite directly. Future adapters should
    fetch raw candidates and normalize them into domain objects.
    """

    name: str

    def fetch_candidates(self, *args: object, **kwargs: object) -> Iterable[LicitacionCandidate]:
        """Return raw candidates from the source."""

    def normalize(self, candidate: LicitacionCandidate) -> LicitacionNormalized:
        """Transform one raw candidate into the normalized model."""

