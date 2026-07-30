"""Contrato neutral de una ejecución completa de cualquier descargador."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


RUN_RESULT_SCHEMA_VERSION = 2
RUN_STATUSES = {"success", "success_with_warnings", "partial", "failed"}
BLOCK_COMPLETENESS_STATUSES = {
    "complete",
    "partial",
    "invalid",
    "not_available",
    "not_applicable",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PlatformCapabilities:
    """Capacidades reales, sin obligar a todas las plataformas a implementarlas."""

    documents: bool = True
    questions_and_answers: bool = False
    document_history: bool = False
    question_attachments: bool = False


@dataclass(frozen=True)
class DownloadArtifact:
    """Documento o archivo observado durante la ejecución."""

    name: str
    status: str
    source_url: str = ""
    path: str = ""
    sha256: str = ""
    sha256_source: str = ""
    content_type: str = ""
    size: int = 0
    role: str = "document"
    remote_id: str = ""
    section: str = ""
    published_at: str = ""
    # Diagnóstico de transporte. Son opcionales para preservar la
    # compatibilidad de las fachadas históricas y no contienen cookies ni
    # cuerpos de respuesta.
    final_url: str = ""
    http_status: int = 0
    redirect_count: int = 0
    error_code: str = ""
    error_message: str = ""
    # Vía observada para recuperar el contenido. No almacena credenciales,
    # cookies ni cuerpos de respuesta.
    retrieval_method: str = ""
    fallback_reason: str = ""


@dataclass
class DownloadRunResult:
    """Resultado estable que consumirán la Suite y el futuro monitor.

    Las fachadas históricas pueden continuar devolviendo sus valores actuales. Este
    contrato pertenece a la API Python interna y no introduce capacidades ficticias.
    """

    platform: str
    source_url: str
    started_at: str
    finished_at: str
    status: str
    capabilities: PlatformCapabilities
    tender_id: str = ""
    changes_detected: bool = False
    general_data: dict[str, Any] = field(default_factory=dict)
    relevant_dates: dict[str, str] = field(default_factory=dict)
    documents_found: int = 0
    documents_downloaded: int = 0
    documents_new: int = 0
    documents_modified: int = 0
    documents_replaced: int = 0
    documents_removed: int = 0
    artifacts: list[DownloadArtifact] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_reused: list[str] = field(default_factory=list)
    state_path: str = ""
    warnings: list[str] = field(default_factory=list)
    recoverable_issues: list[str] = field(default_factory=list)
    error: str = ""
    error_code: str = ""
    retryable: bool = False
    questions: dict[str, Any] | None = None
    block_completeness: dict[str, str] = field(default_factory=dict)
    schema_version: int = RUN_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.platform = str(self.platform or "").strip().upper()
        self.source_url = str(self.source_url or "").strip()
        self.status = str(self.status or "").strip().lower()
        if not self.platform:
            raise ValueError("El resultado necesita una plataforma.")
        if self.status not in RUN_STATUSES:
            raise ValueError(f"Estado de ejecución no válido: {self.status or '(vacío)'}")
        if not self.capabilities.questions_and_answers and self.questions not in (None, {}):
            raise ValueError("Una plataforma sin preguntas no puede publicar resultados de preguntas.")
        for field_name in (
            "documents_found",
            "documents_downloaded",
            "documents_new",
            "documents_modified",
            "documents_replaced",
            "documents_removed",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} no puede ser negativo.")
        normalized_completeness: dict[str, str] = {}
        for raw_block, raw_status in self.block_completeness.items():
            block = str(raw_block or "").strip().casefold()
            block_status = str(raw_status or "").strip().casefold()
            if not block or block_status not in BLOCK_COMPLETENESS_STATUSES:
                raise ValueError(f"Completitud de bloque no válida: {raw_block}={raw_status}")
            normalized_completeness[block] = block_status
        self.block_completeness = normalized_completeness

    @property
    def successful(self) -> bool:
        return self.status in {"success", "success_with_warnings"}

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings or self.recoverable_issues)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "successful": self.successful,
                "has_warnings": self.has_warnings,
                "capabilities": asdict(self.capabilities),
                "artifacts": [asdict(item) for item in self.artifacts],
            }
        )
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def failed(
        cls,
        *,
        platform: str,
        source_url: str,
        capabilities: PlatformCapabilities,
        error: object,
        started_at: str = "",
        finished_at: str = "",
        **values: Any,
    ) -> "DownloadRunResult":
        return cls(
            platform=platform,
            source_url=source_url,
            started_at=started_at or utc_now_iso(),
            finished_at=finished_at or utc_now_iso(),
            status="failed",
            capabilities=capabilities,
            error=str(error or "Error desconocido."),
            **values,
        )


def artifact_from_mapping(value: Mapping[str, Any], *, default_status: str) -> DownloadArtifact:
    path = str(value.get("path") or value.get("ruta") or "")
    name = str(value.get("name") or value.get("filename") or value.get("nombre") or "")
    if not name and path:
        name = Path(path).name
    return DownloadArtifact(
        name=name,
        status=str(value.get("status") or default_status),
        source_url=str(value.get("source_url") or value.get("url") or ""),
        path=path,
        sha256=str(value.get("sha256") or ""),
        sha256_source=str(value.get("sha256_source") or ""),
        content_type=str(value.get("content_type") or value.get("mime") or ""),
        size=int(value.get("size") or 0),
        role=str(value.get("role") or "document"),
        remote_id=str(value.get("remote_id") or value.get("id") or ""),
        section=str(value.get("section") or value.get("seccion") or ""),
        published_at=str(value.get("published_at") or value.get("publication_date") or ""),
        final_url=str(value.get("final_url") or value.get("url_final") or ""),
        http_status=int(value.get("http_status") or value.get("status_code") or 0),
        redirect_count=int(value.get("redirect_count") or value.get("redirections") or 0),
        error_code=str(value.get("error_code") or ""),
        error_message=str(value.get("error_message") or value.get("error") or ""),
        retrieval_method=str(value.get("retrieval_method") or ""),
        fallback_reason=str(value.get("fallback_reason") or ""),
    )


def result_from_question_sync(
    sync_result: object,
    *,
    source_url: str,
    capabilities: PlatformCapabilities,
    started_at: str,
    finished_at: str | None = None,
    state_path: str = "",
) -> DownloadRunResult:
    """Adapta `SyncResult` sin acoplar este módulo al motor de preguntas."""

    if hasattr(sync_result, "to_dict"):
        payload = sync_result.to_dict()
    elif isinstance(sync_result, Mapping):
        payload = dict(sync_result)
    else:
        raise TypeError("El resultado de preguntas no es serializable.")

    errors = [str(item) for item in payload.get("errors", []) if str(item)]
    warnings = [str(item) for item in payload.get("warnings", []) if str(item)]
    warnings.extend(str(item) for item in payload.get("structure_novelties", []) if str(item))
    document_errors = [str(item) for item in payload.get("document_download_errors", []) if str(item)]
    artifacts = [
        artifact_from_mapping(item, default_status="created")
        for item in payload.get("downloaded_documents", [])
        if isinstance(item, Mapping)
    ]
    artifacts.extend(
        artifact_from_mapping(item, default_status="reused")
        for item in payload.get("reused_documents", [])
        if isinstance(item, Mapping)
    )
    artifacts.extend(
        artifact_from_mapping(item, default_status="failed")
        for item in payload.get("failed_documents", [])
        if isinstance(item, Mapping)
    )
    document_path = str(payload.get("document_path") or payload.get("rtf_path") or "")
    if document_path:
        artifacts.append(
            DownloadArtifact(
                name=str(payload.get("document_name") or Path(document_path).name),
                path=document_path,
                sha256=str(payload.get("document_sha256") or ""),
                status="created" if payload.get("document_generated") else "reused",
                role="questions_document",
            )
        )

    query_successful = bool(payload.get("query_successful"))
    useful_output = bool(artifacts or payload.get("documents_downloaded"))
    if errors and useful_output:
        status = "partial"
    elif errors or not query_successful:
        status = "failed"
    elif warnings or document_errors:
        status = "success_with_warnings"
    else:
        status = "success"

    created = [
        item.path
        for item in artifacts
        if item.path and item.status == "created" and item.role != "publication"
    ]
    reused = [
        item.path
        for item in artifacts
        if item.path and item.status == "reused" and item.role != "publication"
    ]
    question_payload = dict(payload)
    return DownloadRunResult(
        platform=str(payload.get("platform") or ""),
        tender_id=str(payload.get("expediente") or ""),
        source_url=source_url,
        started_at=started_at,
        finished_at=finished_at or utc_now_iso(),
        status=status,
        capabilities=capabilities,
        changes_detected=bool(payload.get("changes_detected")),
        documents_found=int(payload.get("documents_found") or 0),
        documents_downloaded=int(payload.get("documents_downloaded") or 0),
        documents_new=int(payload.get("documents_downloaded") or 0),
        artifacts=artifacts,
        files_created=created,
        files_reused=reused,
        state_path=state_path,
        warnings=warnings,
        recoverable_issues=document_errors,
        error="; ".join(errors),
        questions=question_payload,
        block_completeness={
            "documents": "partial" if errors else "complete",
            "questions": "complete" if payload.get("snapshot_complete") else "invalid",
        },
    )
