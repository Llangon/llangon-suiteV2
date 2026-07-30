"""Renderizador RTF puro para el modelo documental neutral."""

from __future__ import annotations

from .document_model import (
    DocumentAttachment,
    DocumentNotice,
    DocumentQuestion,
    DocumentVersion,
    QuestionDocument,
    TenderField,
    format_document_question_heading,
)
from .question_models import DocumentRenderError, literal_text, normalize_text
from .safe_files import TextDocumentOutput


def _rtf_unicode_unit(unit: int) -> str:
    signed = unit if unit <= 32767 else unit - 65536
    return f"\\u{signed}?"


def rtf_escape(value: object) -> str:
    result: list[str] = []
    for character in str(value or ""):
        if character == "\\":
            result.append("\\\\")
        elif character == "{":
            result.append("\\{")
        elif character == "}":
            result.append("\\}")
        elif character in {"\r", "\n"}:
            if not result or result[-1] != "\\line ":
                result.append("\\line ")
        else:
            codepoint = ord(character)
            if 32 <= codepoint < 127:
                result.append(character)
            elif codepoint < 32:
                result.append(" ")
            elif codepoint <= 0xFFFF:
                result.append(_rtf_unicode_unit(codepoint))
            else:
                encoded = character.encode("utf-16-le")
                for index in range(0, len(encoded), 2):
                    result.append(_rtf_unicode_unit(int.from_bytes(encoded[index : index + 2], "little")))
    return "".join(result)


def rtf_hyperlink(url: object, visible_text: object) -> str:
    target = rtf_escape(normalize_text(url)).replace('"', "%22")
    return (
        r'{\field{\*\fldinst{HYPERLINK "'
        + target
        + r'"}}{\fldrslt{\ul '
        + rtf_escape(visible_text)
        + r"}}}"
    )


def _metadata_table_row(field: TenderField) -> str:
    if not normalize_text(field.value):
        return ""
    displayed = rtf_hyperlink(field.link.target, field.link.label) if field.link else rtf_escape(field.value)
    return "".join(
        (
            r"\trowd\trgaph90\trleft0\trbrdrb\brdrs\brdrw5\brdrcf3\cellx2500\cellx9360 ",
            r"\pard\intbl\keepn\sa55\b\fs19 ",
            rtf_escape(field.label),
            r"\cell\pard\intbl\sa55\b0\fs19 ",
            displayed,
            r"\cell\row ",
        )
    )


def _render_notice(notice: DocumentNotice) -> str:
    parts = [
        r"\pard\keepn\sb75\sa45\brdrt\brdrs\brdrw18\brdrcf2"
        r"\brdrb\brdrs\brdrw8\brdrcf3\b\fs19 ",
        rtf_escape(notice.title),
        r"\par ",
    ]
    for line in notice.lines:
        if line:
            parts.extend(
                (
                    r"\pard\keepn\sa35\b0\i\fs18 ",
                    rtf_escape(line),
                    r"\i0\par ",
                )
            )
    return "".join(parts)


def _render_attachments(attachments: tuple[DocumentAttachment, ...]) -> str:
    if not attachments:
        return ""
    parts = [
        r"\pard\keepn\sb30\sa35\b\fs18 ",
        rtf_escape("Archivos adjuntos"),
        r"\par ",
    ]
    for attachment in attachments:
        rendered = (
            rtf_hyperlink(attachment.link.target, attachment.link.label)
            if attachment.link
            else rtf_escape(attachment.name)
        )
        parts.extend(
            (
                r"\pard\li260\fi-180\sa30\b0\fs18 ",
                rtf_escape("• "),
                rendered,
                r"\par ",
            )
        )
    return "".join(parts)


def _render_question_and_answer(version: DocumentVersion) -> str:
    rendered_answer = literal_text(version.answer_text) or version.empty_answer_text
    return "".join(
        (
            r"\pard\keepn\sb35\sa35\b\fs18 ",
            rtf_escape("Pregunta"),
            r"\par\pard\keep\sa90\b0\fs20 ",
            rtf_escape(version.question_text),
            r"\par\pard\keepn\sb25\sa35\b\fs18 ",
            rtf_escape("Respuesta"),
            r"\par\pard\keep\sa90\b0\fs20 ",
            rtf_escape(rendered_answer),
            r"\par ",
        )
    )


def _render_version(version: DocumentVersion) -> str:
    if not version.show_question_label:
        return "".join(
            (
                r"\pard\keep\sa90\b0\fs20 ",
                rtf_escape(version.question_text),
                r"\par\pard\keepn\sb25\sa35\b\fs18 ",
                rtf_escape("Respuesta"),
                r"\par\pard\keep\sa90\b0\fs20 ",
                rtf_escape(literal_text(version.answer_text) or version.empty_answer_text),
                r"\par ",
                _render_attachments(version.attachments),
            )
        )
    return "".join(
        (
            r"\pard\keepn\sb85\sa30\b\fs19 ",
            rtf_escape(version.label),
            r"\par ",
            (
                r"\pard\keepn\sa35\b0\i\fs17 "
                + rtf_escape(version.date_note)
                + r"\i0\par "
                if version.date_note
                else ""
            ),
            _render_question_and_answer(version),
            _render_attachments(version.attachments),
        )
    )


def _render_question(question: DocumentQuestion) -> str:
    parts = [
        r"{\*\llangonqaid ",
        rtf_escape(question.stable_id),
        r" \llangonversion ",
        rtf_escape(question.latest_version),
        "}",
        r"\pard\keepn\sb190\sa65\brdrb\brdrs\brdrw8\brdrcf3\b\fs22 ",
        rtf_escape(format_document_question_heading(question)),
        r"\par ",
    ]
    parts.extend(_render_notice(notice) for notice in question.publication_notices)
    if question.modification_notice:
        parts.append(_render_notice(question.modification_notice))
    if question.show_version_history_heading:
        parts.extend(
            (
                r"\pard\keepn\sb75\sa30\b\fs19 ",
                rtf_escape("HISTORIAL DE VERSIONES"),
                r"\par ",
            )
        )
    parts.extend(_render_version(version) for version in question.versions)
    parts.append(r"\pard\sa75\brdrb\brdrs\brdrw6\brdrcf3\par ")
    return "".join(parts)


def render_question_document(document: QuestionDocument) -> str:
    """Serializa exclusivamente el modelo neutral recibido."""

    corporate = document.corporate
    parts = [
        r"{\rtf1\ansi\ansicpg1252\deff0\uc1",
        r"{\fonttbl{\f0 " + rtf_escape(corporate.font_name) + r";}{\f1 "
        + rtf_escape(corporate.heading_font_name) + r";}}",
        r"{\colortbl;\red0\green0\blue0;\red90\green90\blue90;\red205\green205\blue205;}",
        r"\viewkind4\paperw11906\paperh16838\margl1134\margr1134\margt850\margb850\fs20 ",
        r"\pard\qc\keepn\sa25\b\fs23 ",
        rtf_escape(corporate.company_name),
        r"\par\pard\qc\keepn\sa20\b0\fs18 ",
        rtf_escape(f"CIF {corporate.tax_id}"),
        r"\par\pard\qc\keepn\sa20\fs18 ",
        rtf_escape(corporate.address),
        r"\par\pard\qc\keepn\sa95\fs18 ",
        rtf_escape(f"{corporate.phone} · {corporate.email}"),
        r"\par\pard\qc\keepn\sa45\brdrb\brdrs\brdrw16\brdrcf2\f1\b\fs31 ",
        rtf_escape(document.title),
        r"\par\pard\qc\sa160\f0\b0\fs18 ",
        rtf_escape(document.updated_text),
        r"\par\pard\keepn\sb30\sa70\b\fs21 ",
        rtf_escape(document.tender_section_title),
        r"\par ",
    ]
    parts.extend(_metadata_table_row(field) for field in document.tender_fields)
    parts.extend(_render_question(question) for question in document.questions)
    parts.append("}")
    content = "".join(parts)
    validate_rtf_content(content)
    return content


def validate_rtf_content(content: str) -> None:
    if not content.startswith(r"{\rtf1") or not content.endswith("}"):
        raise DocumentRenderError("El RTF generado no tiene una estructura completa.")
    if r"\shading" in content or r"\cbpat" in content or r"\highlight" in content:
        raise DocumentRenderError("El RTF generado contiene rellenos no permitidos.")
    if "TRAZABILIDAD DE FICHEROS ANTERIORES" in content:
        raise DocumentRenderError("El RTF generado conserva una sección de trazabilidad obsoleta.")
    forbidden_review_headers = (
        "PREGUNTAS Y RESPUESTAS LOCALIZADAS EN LA PRIMERA REVISI",
        "PREGUNTAS Y RESPUESTAS LOCALIZADAS ENTRE",
        "HISTÓRICO DE REVISIONES",
        "BLOQUES DE REVISIÓN",
    )
    if any(header in content for header in forbidden_review_headers):
        raise DocumentRenderError("El RTF generado conserva una agrupación visual por revisiones.")


RTF_OUTPUT = TextDocumentOutput(
    format_name="rtf",
    extension=".rtf",
    encoding="ascii",
    render=render_question_document,
    validator=validate_rtf_content,
)
