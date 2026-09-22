"""Preparación local y auditable del portal público de una licitación.

Este paquete no publica, no envía correos y no modifica los documentos fuente.
"""

from .generator import PortalGenerationError, build_portal_model
from .ai_schema import PortalAISchemaError
from .ai_service import build_ai_portal_preview
from .ai_provider import portal_provider_error_payload
from .selection import PortalFileSelectionError, list_portal_files, resolve_portal_files
from .store import approve_portal_review, ensure_portal_schema, ingest_portal_events, publication_rows, recover_portal_preview, save_portal_draft
from .remote import PortalRemoteError, publish_portal, rotate_portal_access_code, sync_portal_events

__all__ = [
    "PortalFileSelectionError",
    "PortalGenerationError",
    "PortalAISchemaError",
    "build_ai_portal_preview",
    "portal_provider_error_payload",
    "build_portal_model",
    "list_portal_files",
    "resolve_portal_files",
    "ensure_portal_schema",
    "approve_portal_review",
    "ingest_portal_events",
    "publication_rows",
    "recover_portal_preview",
    "save_portal_draft",
    "PortalRemoteError",
    "publish_portal",
    "rotate_portal_access_code",
    "sync_portal_events",
]
