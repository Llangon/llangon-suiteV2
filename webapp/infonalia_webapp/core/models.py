"""Pure dataclasses and enums for future Infonalia flows.

This module intentionally has no dependency on app.py, SQLite, HTTP servers,
network calls, filesystem writes, Dropbox, or frontend code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class ImportMode(str, Enum):
    """How an import run was triggered."""

    manual = "manual"
    automatic = "automatic"


class ImportRunStatus(str, Enum):
    """Lifecycle for an import run."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class StorageBackendName(str, Enum):
    """Supported storage backend identities."""

    local = "local"
    dropbox_sync_folder = "dropbox_sync_folder"
    dropbox_api = "dropbox_api"


class StorageObjectType(str, Enum):
    """Stored object kind."""

    file = "file"
    folder = "folder"


class DownloadStatus(str, Enum):
    """Lifecycle for a download job."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class NewsStatus(str, Enum):
    """Publication state for news articles."""

    draft = "draft"
    published = "published"


@dataclass(slots=True)
class LicitacionCandidate:
    """Raw entry received from an external source before normalization."""

    source_name: str
    raw_payload: dict[str, Any]
    external_id: str | None = None
    external_url: str | None = None
    received_at: datetime | None = None


@dataclass(slots=True)
class LicitacionNormalized:
    """Normalized tender candidate ready for future persistence logic."""

    source_name: str
    titulo: str
    expediente: str | None = None
    organismo: str | None = None
    descripcion: str | None = None
    external_id: str | None = None
    external_url: str | None = None
    presupuesto: Decimal | None = None
    fecha_publicacion: date | None = None
    fecha_limite: date | None = None
    estado: str | None = None
    cpv: str | None = None
    raw_payload: dict[str, Any] | None = None
    fingerprint: str | None = None
    imported_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(slots=True)
class ImportRun:
    """Summary of one future import execution."""

    source_name: str
    mode: ImportMode
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: ImportRunStatus = ImportRunStatus.pending
    total_seen: int = 0
    total_new: int = 0
    total_updated: int = 0
    total_duplicates: int = 0
    total_errors: int = 0


@dataclass(slots=True)
class ImportResult:
    """Counters returned by a source/import pipeline."""

    candidates_seen: int = 0
    normalized_ok: int = 0
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    errors: int = 0


@dataclass(slots=True)
class StorageObject:
    """File or folder stored by a future storage backend."""

    backend_name: StorageBackendName
    uri: str
    display_path: str
    object_type: StorageObjectType
    size_bytes: int | None = None
    checksum: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DownloadJob:
    """Future download execution record."""

    licitacion_id: int
    backend_name: StorageBackendName
    status: DownloadStatus = DownloadStatus.pending
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    objects: list[StorageObject] = field(default_factory=list)


@dataclass(slots=True)
class NewsArticle:
    """Markdown-first news article prepared for future rendering."""

    title: str
    slug: str
    content_markdown: str
    summary: str | None = None
    featured_image: str | None = None
    status: NewsStatus = NewsStatus.draft
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

