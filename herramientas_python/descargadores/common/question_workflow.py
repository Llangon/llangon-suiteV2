"""Coordinación común entre snapshot, estado, documento y capa de salida."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .corporate_document import CORPORATE_DOCUMENT
from .docx_renderer import DOCX_OUTPUT, render_question_document_docx, validate_docx_content
from .document_model import QuestionDocument, build_question_document
from .download_results import structured_sync_payload
from .question_models import (
    DocumentRenderError,
    PlatformQuestion,
    QuestionStateError,
    SafeFileError,
    SnapshotIncompleteError,
    SyncResult,
    iso_datetime,
    parse_platform_datetime,
)
from .question_state import (
    PLACE_STATE_LAYOUT,
    QuestionStateLayout,
    atomic_write_json,
    _validate_state,
    load_state as _load_state,
    state_directory,
    state_file,
    transaction_file,
)
from .question_sync import prepare_question_sync
from .rtf_renderer import RTF_OUTPUT, render_question_document, validate_rtf_content
from .safe_files import (
    DocumentContent,
    DocumentOutput,
    commit_document_and_state,
    document_content_sha256,
    publish_document,
    recover_document_transaction,
    unique_dated_path,
)


def recover_pending_transaction(
    destination: Path,
    *,
    output: DocumentOutput = DOCX_OUTPUT,
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> bool:
    destination = Path(destination).resolve()
    selected_output = output
    journal_path = transaction_file(destination, layout=layout)
    if journal_path.is_file():
        try:
            pending = json.loads(journal_path.read_text(encoding="utf-8"))
            target_name = str(pending.get("target_name") or "").casefold()
        except (OSError, json.JSONDecodeError):
            target_name = ""
        for candidate in (output, DOCX_OUTPUT, RTF_OUTPUT):
            if target_name.endswith("." + candidate.extension.lstrip(".").casefold()):
                selected_output = candidate
                break
    return recover_document_transaction(
        destination=destination,
        technical_directory=state_directory(destination, layout=layout),
        state_path=state_file(destination, layout=layout),
        journal_path=journal_path,
        output=selected_output,
        state_validator=_validate_state,
    )


def load_state(
    destination: Path,
    *,
    profile_url: str = "",
    metadata: dict[str, str] | None = None,
    output: DocumentOutput = DOCX_OUTPUT,
    platform: str = "",
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> tuple[dict[str, Any], list[str]]:
    destination = Path(destination)
    if state_directory(destination, layout=layout).exists():
        recover_pending_transaction(destination, output=output, layout=layout)
    return _load_state(
        destination,
        profile_url=profile_url,
        metadata=metadata,
        platform=platform,
        layout=layout,
    )


def render_cumulative_rtf(
    metadata: dict[str, str],
    state_or_questions: object,
    generated_at: datetime,
) -> str:
    model = build_question_document(metadata, state_or_questions, generated_at)
    return render_question_document(model)


def render_cumulative_docx(
    metadata: dict[str, str],
    state_or_questions: object,
    generated_at: datetime,
) -> bytes:
    model = build_question_document(metadata, state_or_questions, generated_at)
    return render_question_document_docx(model)


def build_cumulative_document(
    metadata: dict[str, str],
    state_or_questions: object,
    generated_at: datetime,
) -> QuestionDocument:
    return build_question_document(metadata, state_or_questions, generated_at)


def render_rtf(
    metadata: dict[str, str],
    questions: Iterable[PlatformQuestion],
    generated_at: datetime,
    history: Iterable[Any] = (),
) -> str:
    """Fachada histórica; construye primero el modelo documental neutral."""

    del history
    reviewed_at = iso_datetime(generated_at)
    stored_questions: dict[str, dict[str, Any]] = {}
    for number, question in enumerate(questions, start=1):
        stable_id = f"compat-{number}-{question.question_hash[:12]}"
        version = {
            "version": 1,
            "detected_at": reviewed_at,
            "question": question.question,
            "answer": question.answer,
            "question_hash": question.question_hash,
            "answer_hash": question.answer_hash,
            "attachments": [attachment.to_state() for attachment in question.attachments],
            "attachments_hash": question.attachments_hash,
            "fingerprint": question.fingerprint,
            "changed_fields": [],
            "change_type": "initial",
        }
        stored_questions[stable_id] = {
            "stable_id": stable_id,
            "number": number,
            "official_datetime": question.official_datetime,
            "question": question.question,
            "answer": question.answer,
            "attachments": version["attachments"],
            "first_seen": reviewed_at,
            "published": True,
            "publication_history": [],
            "versions": [version],
        }
    return render_cumulative_rtf(
        metadata,
        {"platform": "PLACE", "questions": stored_questions},
        generated_at,
    )


def output_path(destination: Path, generated_at: datetime) -> tuple[Path, datetime]:
    return unique_dated_path(
        destination,
        CORPORATE_DOCUMENT.output_prefix,
        ".rtf",
        generated_at,
    )


def document_output_path(
    destination: Path,
    generated_at: datetime,
    output: DocumentOutput,
) -> tuple[Path, datetime]:
    return unique_dated_path(
        destination,
        CORPORATE_DOCUMENT.output_prefix,
        output.extension,
        generated_at,
    )


def validate_rtf_file(path: Path) -> None:
    try:
        content = Path(path).read_text(encoding="ascii")
    except OSError as exc:
        raise DocumentRenderError("No se pudo validar el RTF generado.") from exc
    validate_rtf_content(content)


def validate_docx_file(path: Path) -> None:
    try:
        content = Path(path).read_bytes()
    except OSError as exc:
        raise DocumentRenderError("No se pudo validar el DOCX generado.") from exc
    validate_docx_content(content)


def _commit_changed_review(
    destination: Path,
    state: dict[str, Any],
    content: DocumentContent,
    target: Path,
    output: DocumentOutput,
    layout: QuestionStateLayout,
) -> None:
    technical_directory = state_directory(destination, create=True, layout=layout)
    commit_document_and_state(
        destination=destination,
        technical_directory=technical_directory,
        state_path=state_file(destination, layout=layout),
        journal_path=transaction_file(destination, layout=layout),
        state=state,
        content=content,
        target=target,
        output=output,
    )


def record_successful_review(
    destination: Path,
    metadata: dict[str, str],
    questions: Iterable[PlatformQuestion],
    *,
    reviewed_at: datetime | None = None,
    structure_novelties: Iterable[str] = (),
    snapshot_complete: bool = True,
    output: DocumentOutput = DOCX_OUTPUT,
    platform: str = "",
    authentication_required: bool = True,
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> SyncResult:
    if not snapshot_complete:
        raise SnapshotIncompleteError(
            "La consulta no produjo un snapshot completo; no se modificó el último estado válido."
        )
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = reviewed_at or datetime.now().astimezone()
    current_iso = iso_datetime(timestamp)
    items = list(questions)
    platform_name = (
        platform
        or next((item.platform for item in items if item.platform), "")
        or str(metadata.get("platform") or "")
    )
    state, warnings = load_state(
        destination,
        profile_url=metadata.get("url", ""),
        metadata=metadata,
        output=output,
        platform=platform_name,
        layout=layout,
    )
    previous_review = str(state.get("last_successful_review") or "")
    prepared = prepare_question_sync(
        state,
        metadata,
        items,
        timestamp,
        source_id_key=layout.source_id_key,
    )
    new_state = prepared.state
    events = list(prepared.events)
    counts = prepared.counts
    novelties = list(structure_novelties)
    for stored in sorted(new_state["questions"].values(), key=lambda item: int(item.get("number") or 0)):
        if not parse_platform_datetime(stored.get("official_datetime")):
            warning = (
                f"Pregunta {stored.get('number')} sin fecha oficial válida; "
                "se conserva al final con orden estable."
            )
            if warning not in novelties:
                novelties.append(warning)
    document_path = ""
    document_sha256 = ""
    visible_documents = list(
        destination.glob(
            f"{CORPORATE_DOCUMENT.output_prefix}*{output.extension}"
        )
    )
    restore_missing_document = bool(counts["total"] and not visible_documents)
    document_generated = bool(events or restore_missing_document)
    if document_generated:
        target, _filename_timestamp = document_output_path(destination, timestamp, output)
        document = build_question_document(metadata, new_state, timestamp)
        content = output.render(document)
        output.validator(content)
        document_sha256 = document_content_sha256(content, output)
        result_payload = structured_sync_payload(
            status="created" if events else "regenerated",
            reviewed_at=current_iso,
            previous_review=previous_review,
            counts=counts,
            changes_detected=bool(events),
            document_path=str(target),
            generated_format=output.format_name,
            document_sha256=document_sha256,
            platform=platform_name,
            authentication_required=authentication_required,
        )
        new_state["last_result"] = result_payload
        try:
            _commit_changed_review(destination, new_state, content, target, output, layout)
        except SafeFileError as exc:
            raise DocumentRenderError(
                "No se pudo completar de forma atómica la escritura del RTF y su estado técnico."
                if output.format_name == "rtf"
                else "No se pudo completar la escritura del documento y su estado técnico."
            ) from exc
        document_path = str(target)
        status = "created" if events else "regenerated"
    else:
        result_payload = structured_sync_payload(
            status="no_changes",
            reviewed_at=current_iso,
            previous_review=previous_review,
            counts=counts,
            changes_detected=False,
            document_path="",
            generated_format="",
            platform=platform_name,
            authentication_required=authentication_required,
        )
        new_state["last_result"] = result_payload
        state_directory(destination, create=True, layout=layout)
        try:
            atomic_write_json(state_file(destination, layout=layout), new_state)
        except OSError as exc:
            raise QuestionStateError("No se pudo actualizar el estado de la revisión sin cambios.") from exc
        status = "no_changes"
    return SyncResult(
        status=status,
        query_successful=True,
        authentication_successful=True,
        authentication_required=authentication_required,
        snapshot_complete=True,
        total_questions=counts["total"],
        answered_questions=counts["answered"],
        incorporated_current_cycle=counts["incorporated"],
        responses_updated=counts["responses_modified"],
        question_updates=counts["questions_modified"],
        answers_incorporated=counts["answers_incorporated"],
        answers_removed=counts["answers_removed"],
        questions_removed=counts["questions_removed"],
        questions_restored=counts["questions_restored"],
        changes_detected=bool(events),
        no_changes=not bool(events),
        rtf_generated=document_generated and output.format_name == "rtf",
        rtf_path=document_path if output.format_name == "rtf" else "",
        document_generated=document_generated,
        document_path=document_path,
        previous_review=previous_review,
        current_review=current_iso,
        warnings=warnings,
        structure_novelties=novelties,
        platform=platform_name or layout.platform,
        expediente=str(metadata.get("expediente") or ""),
        document_format=output.format_name if document_generated else "",
        document_name=Path(document_path).name if document_path else "",
        document_sha256=document_sha256 if document_generated else "",
        generated_format=output.format_name if document_generated else "",
    )


def regenerate_document_from_state(
    destination: Path,
    *,
    generated_at: datetime | None = None,
    output: DocumentOutput = DOCX_OUTPUT,
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
    authentication_required: bool = True,
) -> SyncResult:
    """Regenera un documento desde estado v2 sin simular cambios ni escribir estado."""

    destination = Path(destination).resolve()
    path = state_file(destination, layout=layout)
    if not path.is_file():
        raise QuestionStateError("No existe un estado v2 desde el que regenerar el documento.")
    if transaction_file(destination, layout=layout).exists():
        raise QuestionStateError(
            "Existe una transacción documental pendiente; debe resolverse antes de regenerar."
        )
    try:
        state = _validate_state(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionStateError("No se pudo leer el estado v2 para la regeneración.") from exc
    questions = list(state.get("questions", {}).values())
    if not questions:
        raise QuestionStateError("El estado v2 no contiene preguntas que regenerar.")
    metadata = dict(state.get("metadata") or {})
    timestamp = generated_at or datetime.now().astimezone()
    document = build_question_document(metadata, state, timestamp)
    content = output.render(document)
    output.validator(content)
    target, _filename_timestamp = document_output_path(destination, timestamp, output)
    try:
        written = publish_document(
            destination=destination,
            technical_directory=state_directory(destination, create=True, layout=layout),
            content=content,
            target=target,
            output=output,
        )
    except SafeFileError as exc:
        raise DocumentRenderError("No se pudo publicar el documento regenerado.") from exc
    published = [question for question in questions if question.get("published", True)]
    answered = sum(1 for question in published if str(question.get("answer") or "").strip())
    current_iso = iso_datetime(timestamp)
    return SyncResult(
        status="regenerated",
        query_successful=True,
        authentication_successful=True,
        authentication_required=authentication_required,
        snapshot_complete=True,
        total_questions=len(published),
        answered_questions=answered,
        changes_detected=False,
        no_changes=True,
        rtf_generated=output.format_name == "rtf",
        rtf_path=str(written.path) if output.format_name == "rtf" and written.path else "",
        document_generated=True,
        document_path=str(written.path or ""),
        document_format=output.format_name,
        document_name=written.path.name if written.path else "",
        document_sha256=written.sha256,
        generated_format=output.format_name,
        previous_review=str(state.get("last_successful_review") or ""),
        current_review=current_iso,
        expediente=str(metadata.get("expediente") or ""),
        platform=str(state.get("platform") or metadata.get("platform") or ""),
    )


def write_new_questions_rtf(
    destination: Path,
    metadata: dict[str, str],
    questions: Iterable[PlatformQuestion],
    *,
    generated_at: datetime | None = None,
    include_all: bool = False,
) -> tuple[Path | None, int]:
    del include_all
    result = record_successful_review(
        destination,
        metadata,
        questions,
        reviewed_at=generated_at,
        output=RTF_OUTPUT,
    )
    path = Path(result.rtf_path) if result.rtf_generated else None
    count = (
        result.incorporated_current_cycle
        + result.responses_updated
        + result.question_updates
        + result.answers_incorporated
        + result.answers_removed
        + result.questions_removed
        + result.questions_restored
    )
    return path, count
