"""Shared immutable result objects for document generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentGenerationResult:
    path: Path
    sha256: str
    size_bytes: int
    warnings: tuple[str, ...]
    template_version: str
    snapshot_sha256: str
    payload_sha256: str
    version: int


__all__ = ("DocumentGenerationResult",)
