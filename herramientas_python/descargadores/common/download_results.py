"""Serialización estable de resultados comunes y claves heredadas."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def structured_sync_payload(
    *,
    status: str,
    reviewed_at: str,
    previous_review: str,
    counts: dict[str, int],
    changes_detected: bool,
    document_path: str,
    generated_format: str,
    document_sha256: str = "",
    platform: str = "PLACE",
    authentication_required: bool = True,
) -> dict[str, Any]:
    """Crea el contrato técnico sin obligar al motor a conocer el formato."""

    document_generated = bool(document_path and generated_format)
    document_name = Path(document_path).name if document_path else ""
    return {
        "status": status,
        "query_successful": True,
        "snapshot_complete": True,
        "authentication_successful": True,
        "authentication_required": authentication_required,
        "platform": platform,
        "reviewed_at": reviewed_at,
        "previous_review": previous_review,
        "total_questions": counts["total"],
        "answered_questions": counts["answered"],
        "incorporated_current_cycle": counts["incorporated"],
        "question_updates": counts["questions_modified"],
        "responses_updated": counts["responses_modified"],
        "answers_incorporated": counts["answers_incorporated"],
        "answers_removed": counts["answers_removed"],
        "questions_removed": counts["questions_removed"],
        "questions_restored": counts["questions_restored"],
        "changes_detected": changes_detected,
        "document_path": document_path,
        "document_generated": document_generated,
        "document_format": generated_format,
        "document_name": document_name,
        "document_sha256": document_sha256 if document_generated else "",
        "generated_format": generated_format,
        "errors": [],
        # Compatibilidad temporal con consumidores actuales de PLACE.
        "rtf_generated": document_generated and generated_format == "rtf",
        "rtf_path": document_path if generated_format == "rtf" else "",
    }
