"""Fachada compatible del descargador de preguntas de PLACE.

La extracción vive en ``descargadores.place`` y todas las reglas de estado,
comparación y documento viven en ``descargadores.common``.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

try:  # Importación desde el repositorio (Suite y pruebas).
    from herramientas_python.descargadores.common.corporate_document import (
        CORPORATE_DOCUMENT,
    )
    from herramientas_python.descargadores.common.document_model import (
        build_question_document,
    )
    from herramientas_python.descargadores.common.docx_renderer import (
        DOCX_OUTPUT,
        render_question_document_docx,
        validate_docx_content,
    )
    from herramientas_python.descargadores.common.question_models import (
        DocumentRenderError,
        PlatformQuestion,
        PlatformQuestionAttachment,
        QuestionStateError,
        SnapshotIncompleteError,
        SyncResult,
        content_hash,
        extract_platform_datetime,
        format_detection_datetime,
        format_question_datetime,
        iso_datetime,
        literal_text,
        normalize_label,
        normalize_text,
        normalized_key,
        parse_iso_datetime,
        parse_platform_datetime,
    )
    from herramientas_python.descargadores.common.question_state import (
        STATE_BACKUP_FILE_NAME,
        STATE_DIRECTORY_NAME,
        STATE_FILE_NAME,
        STATE_SCHEMA_VERSION,
        TRANSACTION_FILE_NAME,
        _empty_state,
        _migrate_state_v1_to_v2,
        _validate_state,
        legacy_rtf_inventory,
        state_directory,
        state_file,
        transaction_file,
    )
    from herramientas_python.descargadores.common.question_sync import (
        _prepare_snapshot,
        prepare_question_sync,
    )
    from herramientas_python.descargadores.common.question_workflow import (
        build_cumulative_document,
        load_state,
        output_path,
        record_successful_review as _record_successful_review,
        regenerate_document_from_state as _regenerate_document_from_state,
        recover_pending_transaction,
        render_cumulative_docx,
        render_cumulative_rtf,
        render_rtf,
        validate_docx_file,
        validate_rtf_file,
        write_new_questions_rtf,
    )
    from herramientas_python.descargadores.common.rtf_renderer import (
        rtf_escape,
        rtf_hyperlink,
        validate_rtf_content,
    )
    from herramientas_python.descargadores.common.safe_files import (
        atomic_write_json as _atomic_write_json,
        mark_hidden as _mark_hidden,
        mark_visible as _mark_visible,
        replace_with_retry as _replace_with_retry,
    )
    from herramientas_python.descargadores.place.errors import (
        PlaceAuthenticationError,
        PlaceQuestionDataError,
        PlaceQuestionsError,
        PlaceResponseDataError,
        PlaceSessionError,
        PlaceSnapshotIncompleteError,
        PlaceStructureError,
    )
    from herramientas_python.descargadores.place.questions import (
        QuestionReference,
        confirmed_empty_question_list,
        direct_cells,
        extract_tender_metadata,
        fetch_answered_questions,
        fetch_question_snapshot,
        fetch_questions,
        field_value,
        find_next_page_link,
        first_labeled_value,
        has_labeled_row,
        labeled_value,
        normalize_place_question,
        pagination_requires_more,
        parse_question_attachments,
        parse_question_references,
        stable_source_id,
        validate_question_page,
    )
    from herramientas_python.descargadores.place.session import (
        build_form_payload,
        create_session,
        ensure_active_session,
        find_link_by_text,
        login,
        post_jsf_link,
        soup_from_response,
        submit_target,
    )
except ModuleNotFoundError:  # Ejecución directa del archivo central en Windows.
    from descargadores.common.corporate_document import CORPORATE_DOCUMENT
    from descargadores.common.document_model import build_question_document
    from descargadores.common.docx_renderer import (
        DOCX_OUTPUT,
        render_question_document_docx,
        validate_docx_content,
    )
    from descargadores.common.question_models import (
        DocumentRenderError,
        PlatformQuestion,
        PlatformQuestionAttachment,
        QuestionStateError,
        SnapshotIncompleteError,
        SyncResult,
        content_hash,
        extract_platform_datetime,
        format_detection_datetime,
        format_question_datetime,
        iso_datetime,
        literal_text,
        normalize_label,
        normalize_text,
        normalized_key,
        parse_iso_datetime,
        parse_platform_datetime,
    )
    from descargadores.common.question_state import (
        STATE_BACKUP_FILE_NAME,
        STATE_DIRECTORY_NAME,
        STATE_FILE_NAME,
        STATE_SCHEMA_VERSION,
        TRANSACTION_FILE_NAME,
        _empty_state,
        _migrate_state_v1_to_v2,
        _validate_state,
        legacy_rtf_inventory,
        state_directory,
        state_file,
        transaction_file,
    )
    from descargadores.common.question_sync import _prepare_snapshot, prepare_question_sync
    from descargadores.common.question_workflow import (
        build_cumulative_document,
        load_state,
        output_path,
        record_successful_review as _record_successful_review,
        regenerate_document_from_state as _regenerate_document_from_state,
        recover_pending_transaction,
        render_cumulative_docx,
        render_cumulative_rtf,
        render_rtf,
        validate_docx_file,
        validate_rtf_file,
        write_new_questions_rtf,
    )
    from descargadores.common.rtf_renderer import rtf_escape, rtf_hyperlink, validate_rtf_content
    from descargadores.common.safe_files import (
        atomic_write_json as _atomic_write_json,
        mark_hidden as _mark_hidden,
        mark_visible as _mark_visible,
        replace_with_retry as _replace_with_retry,
    )
    from descargadores.place.errors import (
        PlaceAuthenticationError,
        PlaceQuestionDataError,
        PlaceQuestionsError,
        PlaceResponseDataError,
        PlaceSessionError,
        PlaceSnapshotIncompleteError,
        PlaceStructureError,
    )
    from descargadores.place.questions import (
        QuestionReference,
        confirmed_empty_question_list,
        direct_cells,
        extract_tender_metadata,
        fetch_answered_questions,
        fetch_question_snapshot,
        fetch_questions,
        field_value,
        find_next_page_link,
        first_labeled_value,
        has_labeled_row,
        labeled_value,
        normalize_place_question,
        pagination_requires_more,
        parse_question_attachments,
        parse_question_references,
        stable_source_id,
        validate_question_page,
    )
    from descargadores.place.session import (
        build_form_payload,
        create_session,
        ensure_active_session,
        find_link_by_text,
        login,
        post_jsf_link,
        soup_from_response,
        submit_target,
    )


USER_ENV = "PLACE_USUARIO"
PASSWORD_ENV = "PLACE_CONTRASENA"
OUTPUT_PREFIX = CORPORATE_DOCUMENT.output_prefix
OUTPUT_DATETIME_FORMAT = "%Y-%m-%d %H-%M-%S"
COMPANY_INFO = {
    "nombre": CORPORATE_DOCUMENT.company_name,
    "cif": CORPORATE_DOCUMENT.tax_id,
    "direccion": CORPORATE_DOCUMENT.address,
    "email": CORPORATE_DOCUMENT.email,
    "telefono": CORPORATE_DOCUMENT.phone,
}

QuestionAnswer = PlatformQuestion
QuestionAttachment = PlatformQuestionAttachment
PlaceStateError = QuestionStateError
PlaceRtfError = DocumentRenderError
PlaceDocumentError = DocumentRenderError
extract_place_datetime = extract_platform_datetime
parse_place_datetime = parse_platform_datetime


def record_successful_review(
    destination: Path,
    metadata: dict[str, str],
    questions,
    *,
    reviewed_at: datetime | None = None,
    structure_novelties=(),
    snapshot_complete: bool = True,
) -> SyncResult:
    if not snapshot_complete:
        raise PlaceSnapshotIncompleteError(
            "La consulta no produjo un snapshot completo; no se modificó el último estado válido."
        )
    return _record_successful_review(
        destination,
        metadata,
        questions,
        reviewed_at=reviewed_at,
        structure_novelties=structure_novelties,
        snapshot_complete=True,
        platform="PLACE",
    )


def sync_place_questions(
    profile_url: str,
    destination: Path,
    username: str,
    password: str,
    *,
    reviewed_at: datetime | None = None,
    session: requests.Session | None = None,
) -> SyncResult:
    current_iso = iso_datetime(reviewed_at or datetime.now().astimezone())
    try:
        metadata, questions, novelties = fetch_questions(
            profile_url,
            username,
            password,
            session=session,
        )
        return record_successful_review(
            destination,
            metadata,
            questions,
            reviewed_at=reviewed_at,
            structure_novelties=novelties,
        )
    except (PlaceQuestionsError, QuestionStateError, DocumentRenderError, SnapshotIncompleteError) as exc:
        authentication_successful = not isinstance(exc, PlaceAuthenticationError)
        if isinstance(exc, PlaceStructureError) and "acceso" in normalized_key(str(exc)):
            authentication_successful = False
        local_error = isinstance(exc, (QuestionStateError, DocumentRenderError))
        return SyncResult(
            status="error",
            query_successful=local_error,
            authentication_successful=authentication_successful,
            snapshot_complete=local_error,
            current_review=current_iso,
            error_type=exc.error_type,
            errors=[str(exc)],
        )
    except requests.RequestException as exc:
        return SyncResult(
            status="error",
            query_successful=False,
            authentication_successful=False,
            current_review=current_iso,
            error_type="session",
            errors=[f"Error de conexión con PLACE: {exc.__class__.__name__}"],
        )
    except OSError as exc:
        return SyncResult(
            status="error",
            query_successful=True,
            authentication_successful=True,
            snapshot_complete=True,
            current_review=current_iso,
            error_type="document_write",
            errors=[f"Error de escritura: {exc.__class__.__name__}"],
        )


def regenerate_docx_from_state(
    destination: Path,
    *,
    generated_at: datetime | None = None,
) -> SyncResult:
    """Operación de mantenimiento explícita; no consulta PLACE ni modifica el estado."""

    return _regenerate_document_from_state(
        Path(destination).resolve(),
        generated_at=generated_at,
        output=DOCX_OUTPUT,
    )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga preguntas y respuestas de una licitación de PLACE.")
    parser.add_argument("url", nargs="?", help="URL pública de detalle de la licitación")
    parser.add_argument("--destino", required=True, help="Carpeta donde se guardará el DOCX")
    parser.add_argument("--usuario", default=os.environ.get(USER_ENV, ""), help=f"Usuario de PLACE (o {USER_ENV})")
    parser.add_argument(
        "--regenerar-docx-desde-estado",
        action="store_true",
        help="Crea un DOCX desde el estado v2 existente sin consultar PLACE ni alterar el estado.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    if args.regenerar_docx_desde_estado:
        try:
            result = regenerate_docx_from_state(Path(args.destino))
        except (QuestionStateError, DocumentRenderError) as exc:
            result = SyncResult(
                status="error",
                query_successful=True,
                authentication_successful=True,
                snapshot_complete=True,
                error_type=exc.error_type,
                errors=[str(exc)],
            )
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        return 0 if result.status != "error" else 1
    if not args.url:
        print("Falta la URL de detalle de la licitación.")
        return 2
    username = normalize_text(args.usuario)
    if not username:
        print(f"Falta el usuario de PLACE. Use --usuario o la variable {USER_ENV}.")
        return 2
    password = os.environ.get(PASSWORD_ENV, "")
    if not password and sys.stdin.isatty():
        password = getpass.getpass("Contraseña de PLACE: ")
    if not password:
        print(f"Falta la contraseña de PLACE. Defina temporalmente la variable {PASSWORD_ENV}.")
        return 2
    result = sync_place_questions(
        args.url,
        Path(args.destino).resolve(),
        username,
        password,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0 if result.status != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
