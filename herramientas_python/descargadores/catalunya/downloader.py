"""Coordinación operativa del adaptador Catalunya."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import requests

from ..common.download_models import DocumentDownloadResult
from ..common.question_models import QuestionWorkflowError, SyncResult
from ..common.question_state import state_file
from ..common.question_workflow import record_successful_review, regenerate_document_from_state
from ..common.run_result import PlatformCapabilities, result_from_question_sync, utc_now_iso
from . import CATALUNYA_STATE_LAYOUT
from .browser_fallback import extraer_documentos_renderizados
from .client import TIMEOUT_DESCARGA, crear_session
from .documents import (
    CatalunyaDocumentInventory,
    descargar_enlaces,
    extraer_documentos_de_html,
    extraer_inventario_documentos_de_api,
    metadatos_publicacion_desde_url,
    preparar_carpetas_publicaciones,
)
from .questions import obtener_snapshot_preguntas


QUESTION_ATTACHMENTS_DIRECTORY = "Adjuntos de preguntas y respuestas"
CATALUNYA_CAPABILITIES = PlatformCapabilities(
    documents=True,
    questions_and_answers=True,
    document_history=True,
    question_attachments=True,
)


def _merge_document_results(*results: DocumentDownloadResult) -> DocumentDownloadResult:
    merged = DocumentDownloadResult(platform="CATALUNYA", successful=True)
    for result in results:
        merged.found += result.found
        merged.downloaded.extend(result.downloaded)
        merged.skipped.extend(result.skipped)
        merged.failed.extend(result.failed)
        merged.errors.extend(result.errors)
    merged.successful = not merged.errors
    return merged


def descubrir_documentos_generales(
    session,
    url: str,
    *,
    log=print,
) -> CatalunyaDocumentInventory:
    api_error = ""
    try:
        inventory = extraer_inventario_documentos_de_api(session, url)
        if inventory.publications or inventory.links or inventory.errors:
            return inventory
    except Exception as exc:
        api_error = f"No se pudo confirmar el inventario completo mediante API: {exc}"

    documents: list[dict] = []
    try:
        response = session.get(url, timeout=TIMEOUT_DESCARGA)
        response.raise_for_status()
        documents = extraer_documentos_de_html(response.text, url)
    except Exception:
        documents = []
    if not documents:
        log("La ficha necesita Javascript. Abriendo Chrome en segundo plano...")
        documents = extraer_documentos_renderizados(url, log=log)
    errors = [api_error] if api_error else []
    if documents and not api_error:
        errors.append(
            "La API no enumeró documentos, pero la ficha sí; "
            "no se pudo confirmar el inventario completo del expediente."
        )
    publication = metadatos_publicacion_desde_url(url)
    if publication:
        for document in documents:
            document.update(publication)
    return CatalunyaDocumentInventory(
        links=documents,
        publication_ids=[publication["publication_id"]] if publication else [],
        publications=[publication] if publication else [],
        errors=errors,
    )


def descargar_adjuntos_respuestas(session, snapshot, destination: Path, referer: str) -> DocumentDownloadResult:
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for question in snapshot.questions:
        for attachment in question.attachments:
            if not attachment.url or attachment.url.casefold() in seen:
                continue
            seen.add(attachment.url.casefold())
            links.append(
                {
                    "href": attachment.url,
                    "text": attachment.name,
                    "title": attachment.name,
                    "download": attachment.name,
                    "itemText": attachment.name,
                    "section": "Preguntas y respuestas",
                    "fecha": question.answered_at,
                }
            )
    return descargar_enlaces(
        session,
        links,
        destination / QUESTION_ATTACHMENTS_DIRECTORY,
        referer,
    )


def _apply_document_result(result: SyncResult, documents: DocumentDownloadResult) -> SyncResult:
    if documents.downloaded:
        result.changes_detected = True
        result.no_changes = False
    result.documents_found = documents.found
    result.documents_downloaded = sum(
        item.role == "document" for item in documents.downloaded
    )
    result.documents_skipped = sum(
        item.role == "document" for item in documents.skipped
    )
    result.downloaded_documents = [
        {
            "name": item.filename,
            "path": str(item.path),
            "source_url": item.source_url,
            "sha256": item.sha256,
            "role": item.role,
            "remote_id": item.remote_id,
            "section": item.section,
            "published_at": item.published_at,
        }
        for item in documents.downloaded
    ]
    result.reused_documents = [
        {
            "name": item.filename,
            "path": str(item.path),
            "source_url": item.source_url,
            "sha256": item.sha256,
            "role": item.role,
            "remote_id": item.remote_id,
            "section": item.section,
            "published_at": item.published_at,
        }
        for item in documents.skipped
    ]
    result.failed_documents = list(documents.failed)
    result.document_download_errors = list(documents.errors)
    result.errors.extend(error for error in documents.errors if error not in result.errors)
    if documents.errors and result.status != "error":
        result.status = "partial"
    return result


def ejecutar_descarga_catalunya(
    url: str,
    destination: Path,
    *,
    session=None,
    reviewed_at: datetime | None = None,
    include_general_documents: bool = True,
    include_questions: bool = True,
    log=print,
) -> SyncResult:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    active_session = session or crear_session()
    document_results: list[DocumentDownloadResult] = []
    if include_general_documents:
        try:
            inventory = descubrir_documentos_generales(active_session, url, log=log)
            folder_result = preparar_carpetas_publicaciones(
                inventory.publications,
                destination,
            )
            file_result = descargar_enlaces(
                active_session,
                inventory.links,
                destination,
                url,
            )
            document_result = _merge_document_results(folder_result, file_result)
            document_result.errors.extend(inventory.errors)
            document_result.successful = not document_result.errors
            document_results.append(document_result)
        except Exception as exc:
            document_results.append(
                DocumentDownloadResult(
                    platform="CATALUNYA",
                    successful=False,
                    errors=[f"Documentos generales: {exc}"],
                )
            )
    documents = _merge_document_results(*document_results)
    if not include_questions:
        return _apply_document_result(
            SyncResult(
                status="documents",
                query_successful=documents.successful,
                authentication_successful=True,
                authentication_required=False,
                snapshot_complete=False,
                no_changes=not documents.downloaded,
                platform="CATALUNYA",
            ),
            documents,
        )
    try:
        snapshot = obtener_snapshot_preguntas(active_session, url)
        attachment_result = descargar_adjuntos_respuestas(
            active_session,
            snapshot,
            destination,
            url,
        )
        documents = _merge_document_results(documents, attachment_result)
        result = record_successful_review(
            destination,
            snapshot.metadata,
            snapshot.questions,
            reviewed_at=reviewed_at,
            structure_novelties=snapshot.warnings,
            snapshot_complete=snapshot.complete,
            platform="CATALUNYA",
            authentication_required=False,
            layout=CATALUNYA_STATE_LAYOUT,
        )
        return _apply_document_result(result, documents)
    except QuestionWorkflowError as exc:
        return _apply_document_result(
            SyncResult(
                status="error",
                query_successful=False,
                authentication_successful=exc.error_type != "access",
                authentication_required=False,
                snapshot_complete=False,
                error_type=exc.error_type,
                errors=[str(exc)],
                platform="CATALUNYA",
            ),
            documents,
        )
    except requests.RequestException as exc:
        return _apply_document_result(
            SyncResult(
                status="error",
                query_successful=False,
                authentication_successful=True,
                authentication_required=False,
                snapshot_complete=False,
                error_type="access",
                errors=[str(exc)],
                platform="CATALUNYA",
            ),
            documents,
        )
    except Exception as exc:
        return _apply_document_result(
            SyncResult(
                status="error",
                query_successful=False,
                authentication_successful=True,
                authentication_required=False,
                snapshot_complete=False,
                error_type="unexpected",
                errors=[f"Error inesperado consultando Catalunya: {exc}"],
                platform="CATALUNYA",
            ),
            documents,
        )


def regenerar_docx_catalunya(destination: Path, *, generated_at: datetime | None = None) -> SyncResult:
    return regenerate_document_from_state(
        destination,
        generated_at=generated_at,
        layout=CATALUNYA_STATE_LAYOUT,
        authentication_required=False,
    )


def run_catalunya(
    url: str,
    destination: Path,
    *,
    session=None,
    reviewed_at: datetime | None = None,
    include_general_documents: bool = True,
    include_questions: bool = True,
    log=print,
    started_at: str | None = None,
):
    """API neutral para la Suite y el futuro monitor."""

    started = started_at or utc_now_iso()
    destination = Path(destination).resolve()
    result = ejecutar_descarga_catalunya(
        url,
        destination,
        session=session,
        reviewed_at=reviewed_at,
        include_general_documents=include_general_documents,
        include_questions=include_questions,
        log=log,
    )
    path = state_file(destination, layout=CATALUNYA_STATE_LAYOUT)
    return result_from_question_sync(
        result,
        source_url=url,
        capabilities=CATALUNYA_CAPABILITIES,
        started_at=started,
        state_path=str(path) if path.is_file() else "",
    )
