"""Modelo documental neutral y constructor para preguntas acumulativas.

El contenido de este módulo no conoce RTF, DOCX, HTML ni detalles de acceso a
ninguna plataforma. Los renderizadores consumen estas estructuras inmutables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .corporate_document import (
    CORPORATE_DOCUMENT,
    NOTICE_ANSWER_ADDED,
    NOTICE_ANSWER_REMOVED,
    NOTICE_CONTENT_MODIFIED,
    NOTICE_QUESTION_REMOVED,
    NOTICE_QUESTION_RESTORED,
    CorporateDocumentConfig,
)
from .question_models import (
    extract_platform_datetime,
    format_detection_datetime,
    format_question_datetime,
    literal_text,
    parse_platform_datetime,
    state_questions,
)


@dataclass(frozen=True)
class DocumentLink:
    target: str
    label: str


@dataclass(frozen=True)
class TenderField:
    label: str
    value: str = ""
    link: DocumentLink | None = None


@dataclass(frozen=True)
class DocumentNotice:
    kind: str
    title: str
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentAttachment:
    name: str
    link: DocumentLink | None = None
    source_id: str = ""
    role: str = "entry"


@dataclass(frozen=True)
class DocumentVersion:
    label: str
    date_note: str
    question_text: str
    answer_text: str
    empty_answer_text: str
    question_date_note: str = ""
    answer_date_note: str = ""
    attachments: tuple[DocumentAttachment, ...] = ()
    show_question_label: bool = True


@dataclass(frozen=True)
class DocumentQuestion:
    stable_id: str
    latest_version: int
    number: int
    asked_at: str
    answered_at: str
    heading_at: str
    display_timezone: str
    publication_notices: tuple[DocumentNotice, ...]
    modification_notice: DocumentNotice | None
    show_version_history_heading: bool
    versions: tuple[DocumentVersion, ...]


@dataclass(frozen=True)
class QuestionDocument:
    corporate: CorporateDocumentConfig
    title: str
    updated_text: str
    tender_section_title: str
    tender_fields: tuple[TenderField, ...]
    questions: tuple[DocumentQuestion, ...]
    generated_at: str
    preferred_page_breaks: bool = True


def _question_sort_key(question: dict[str, Any]) -> tuple[int, float, int, str]:
    parsed = parse_platform_datetime(question.get("official_datetime"))
    if parsed:
        return (0, -parsed.timestamp(), int(question.get("number") or 0), str(question.get("stable_id") or ""))
    return (1, 0.0, int(question.get("number") or 0), str(question.get("stable_id") or ""))


def format_document_question_heading(question: DocumentQuestion) -> str:
    """Formatea el encabezado visible sin conocer la plataforma de origen."""

    heading = f"Pregunta {question.number}"
    visible_date = format_question_datetime(
        question.heading_at,
        timezone_name=question.display_timezone,
    )
    return f"{heading} del {visible_date}" if visible_date else heading


def _select_heading_datetime(*values: object) -> str:
    """Devuelve la primera fecha oficial fiable conservando su valor normalizado."""

    for value in values:
        extracted = extract_platform_datetime(value)
        if extracted and parse_platform_datetime(extracted):
            return extracted
    return ""


def _attachment_model(source: dict[str, Any]) -> DocumentAttachment:
    name = literal_text(source.get("name")) or "Archivo adjunto"
    url = literal_text(source.get("url"))
    return DocumentAttachment(
        name=name,
        link=DocumentLink(target=url, label=name) if url else None,
        source_id=literal_text(source.get("source_id")),
        role=literal_text(source.get("role")) or "entry",
    )


def _notice_for_modification(version: dict[str, Any], platform: str) -> DocumentNotice:
    change_type = str(version.get("change_type") or "")
    detected = format_detection_datetime(version.get("detected_at"))
    if change_type == "answer_added":
        return DocumentNotice(
            kind="answer_added",
            title=NOTICE_ANSWER_ADDED.format(platform=platform),
            lines=tuple(filter(None, (f"Incorporación detectada el {detected}." if detected else "",))),
        )
    if change_type == "answer_removed":
        return DocumentNotice(
            kind="answer_removed",
            title=NOTICE_ANSWER_REMOVED.format(platform=platform),
            lines=tuple(
                filter(None, (f"Ausencia de la respuesta detectada el {detected}." if detected else "",))
            ),
        )
    labels = {
        "question": "pregunta",
        "answer": "respuesta",
        "attachments": "archivos adjuntos",
        "official_datetime": "fecha oficial",
        "asked_at": "fecha de la pregunta",
        "answered_at": "fecha de la respuesta",
        "updated_at": "fecha de publicación",
    }
    elements = " y ".join(labels.get(item, item) for item in list(version.get("changed_fields") or []))
    return DocumentNotice(
        kind="content_modified",
        title=NOTICE_CONTENT_MODIFIED.format(platform=platform),
        lines=tuple(
            filter(
                None,
                (
                    f"Modificación detectada el {detected}." if detected else "",
                    f"Elementos modificados: {elements}." if elements else "",
                ),
            )
        ),
    )


def _publication_notices(question: dict[str, Any], platform: str) -> tuple[DocumentNotice, ...]:
    history = list(question.get("publication_history") or [])
    if not history:
        return ()
    notices: list[DocumentNotice] = []
    if not question.get("published", True):
        detected = format_detection_datetime(question.get("unpublished_at"))
        notices.append(
            DocumentNotice(
                kind="question_removed",
                title=NOTICE_QUESTION_REMOVED.format(platform=platform),
                lines=tuple(
                    filter(
                        None,
                        (
                            f"Ausencia detectada el {detected}." if detected else "",
                            "Se muestra la última versión conocida antes de que dejara de aparecer en la plataforma.",
                        ),
                    )
                ),
            )
        )
    elif history[-1].get("event") == "restored":
        detected = format_detection_datetime(history[-1].get("detected_at"))
        notices.append(
            DocumentNotice(
                kind="question_restored",
                title=NOTICE_QUESTION_RESTORED.format(platform=platform),
                lines=tuple(filter(None, (f"Reaparición detectada el {detected}." if detected else "",))),
            )
        )
    if len(history) > 1:
        lines: list[str] = []
        for event in reversed(history):
            detected = format_detection_datetime(event.get("detected_at"))
            label = "Reaparición" if event.get("event") == "restored" else "Ausencia"
            lines.append(f"{label} detectada el {detected}." if detected else label)
        notices.append(
            DocumentNotice(
                kind="publication_history",
                title=f"HISTORIAL DE PUBLICACIÓN EN {platform}",
                lines=tuple(lines),
            )
        )
    return tuple(notices)


def _versions_for_question(
    question: dict[str, Any],
    platform: str,
    timezone_name: str,
    heading_at: str,
) -> tuple[DocumentNotice | None, bool, tuple[DocumentVersion, ...]]:
    versions = sorted(
        list(question.get("versions") or []),
        key=lambda item: int(item.get("version") or 0),
        reverse=True,
    )
    if not versions:
        versions = [
            {
                "version": 1,
                "question": question.get("question", ""),
                "answer": question.get("answer", ""),
                "attachments": question.get("attachments") or [],
                "detected_at": question.get("first_seen", ""),
                "change_type": "initial",
                "asked_at": question.get("asked_at", ""),
                "answered_at": question.get("answered_at", ""),
            }
        ]
    if len(versions) == 1:
        withdrawn = not question.get("published", True)
        label = "ÚLTIMA VERSIÓN CONOCIDA" if withdrawn else ""
        return (
            None,
            False,
            (
                DocumentVersion(
                    label=label,
                    date_note="",
                    question_text=literal_text(versions[0].get("question")),
                    answer_text=literal_text(versions[0].get("answer")),
                    empty_answer_text=(
                        f"Sin respuesta publicada actualmente en {platform}."
                        if withdrawn
                        else f"Sin respuesta publicada en {platform}."
                    ),
                    answer_date_note=_answer_date_note(
                        versions[0].get("answered_at") or question.get("answered_at"),
                        timezone_name,
                        heading_at,
                    ),
                    attachments=tuple(
                        _attachment_model(item) for item in versions[0].get("attachments") or []
                    ),
                    show_question_label=withdrawn,
                ),
            ),
        )

    rendered: list[DocumentVersion] = []
    for index, version in enumerate(versions):
        detected = format_detection_datetime(version.get("detected_at"))
        if index == 0:
            label = (
                f"VERSIÓN VIGENTE EN {platform}"
                if question.get("published", True)
                else "ÚLTIMA VERSIÓN CONOCIDA"
            )
            date_note = f"Modificación detectada el {detected}." if detected else ""
        elif index == len(versions) - 1:
            label = "VERSIÓN INICIAL CONOCIDA" if len(versions) > 2 else "VERSIÓN ANTERIOR"
            date_note = f"Registrada el {detected}." if detected else ""
        else:
            label = "VERSIÓN ANTERIOR"
            date_note = f"Detectada como vigente el {detected}." if detected else ""
        rendered.append(
            DocumentVersion(
                label=label,
                date_note=date_note,
                question_text=literal_text(version.get("question")),
                answer_text=literal_text(version.get("answer")),
                empty_answer_text=(
                    f"Sin respuesta publicada actualmente en {platform}."
                    if index == 0
                    else f"Sin respuesta publicada en {platform}."
                ),
                answer_date_note=_answer_date_note(
                    version.get("answered_at")
                    or (question.get("answered_at") if index == 0 else ""),
                    timezone_name,
                    heading_at,
                ),
                attachments=tuple(_attachment_model(item) for item in version.get("attachments") or []),
            )
        )
    return _notice_for_modification(versions[0], platform), len(versions) > 2, tuple(rendered)


def _answer_date_note(value: object, timezone_name: str, heading_at: object = "") -> str:
    formatted = format_question_datetime(value, timezone_name=timezone_name)
    heading_date = format_question_datetime(heading_at, timezone_name=timezone_name)
    if formatted and formatted == heading_date:
        return ""
    return f"Respuesta publicada el {formatted}." if formatted else ""


def _question_model(
    question: dict[str, Any],
    platform: str,
    timezone_name: str,
) -> DocumentQuestion:
    asked_at = str(question.get("asked_at") or "")
    answered_at = str(question.get("answered_at") or "")
    heading_at = _select_heading_datetime(
        asked_at,
        answered_at,
        question.get("official_datetime"),
    )
    latest_version = max(
        (int(item.get("version") or 0) for item in question.get("versions") or []),
        default=0,
    )
    modification_notice, show_history, versions = _versions_for_question(
        question,
        platform,
        timezone_name,
        heading_at,
    )
    return DocumentQuestion(
        stable_id=str(question.get("stable_id") or ""),
        latest_version=latest_version,
        number=int(question.get("number") or 0),
        asked_at=asked_at,
        answered_at=answered_at,
        heading_at=heading_at,
        display_timezone=timezone_name,
        publication_notices=_publication_notices(question, platform),
        modification_notice=modification_notice,
        show_version_history_heading=show_history,
        versions=versions,
    )


def build_question_document(
    metadata: dict[str, str],
    state_or_questions: object,
    generated_at: datetime,
    *,
    corporate: CorporateDocumentConfig = CORPORATE_DOCUMENT,
) -> QuestionDocument:
    """Construye el contenido lógico sin generar ni escribir ningún fichero."""

    platform = str(metadata.get("platform") or "PLATAFORMA")
    if isinstance(state_or_questions, dict):
        platform = str(state_or_questions.get("platform") or platform)
    fields = [
        TenderField("Expediente", str(metadata.get("expediente") or "")),
        TenderField("Órgano de contratación", str(metadata.get("organismo") or "")),
        TenderField("Objeto", str(metadata.get("titulo") or "")),
        TenderField("Fin de presentación", str(metadata.get("fecha_fin_oferta") or "")),
    ]
    url = str(metadata.get("url") or "")
    fields.append(
        TenderField(
            "Enlace",
            url,
            DocumentLink(url, f"Abrir ficha de la licitación en {platform}") if url else None,
        )
    )
    timezone_name = str(metadata.get("display_timezone") or "")
    questions = tuple(
        _question_model(item, platform, timezone_name)
        for item in sorted(state_questions(state_or_questions), key=_question_sort_key)
    )
    return QuestionDocument(
        corporate=corporate,
        title=corporate.document_title,
        updated_text=f"Documento actualizado el {generated_at.strftime('%d/%m/%Y a las %H:%M')}",
        tender_section_title="DATOS PRINCIPALES DE LA LICITACIÓN",
        tender_fields=tuple(fields),
        questions=questions,
        generated_at=generated_at.isoformat(timespec="seconds"),
    )
