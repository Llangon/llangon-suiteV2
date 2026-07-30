"""Escenarios visuales reproducibles para el DOCX de preguntas."""

from __future__ import annotations

from datetime import datetime, timezone

from herramientas_python.descargadores.common.document_model import (
    QuestionDocument,
    build_question_document,
)


GENERATED_AT = datetime(2026, 7, 18, 16, 30, tzinfo=timezone.utc)


def metadata(*, long_title: bool = False, url: str = "https://example.test/licitacion/EXP-17"):
    title = "Suministro de alimentos para centros hospitalarios"
    if long_title:
        title = (
            "Suministro sucesivo y por precios unitarios de alimentos enlatados, "
            "productos precocinados y referencias sin gluten para varios centros "
            "hospitalarios, con condiciones especiales de entrega y trazabilidad"
        )
    return {
        "platform": "PLACE",
        "expediente": "EXP-17/2026",
        "organismo": "Órgano de contratación de prueba",
        "titulo": title,
        "fecha_fin_oferta": "20/07/2026 14:00",
        "url": url,
    }


def version(
    number: int,
    question: str,
    answer: str,
    *,
    change_type: str = "initial",
    changed_fields=(),
    attachments=(),
):
    return {
        "version": number,
        "detected_at": f"2026-07-{10 + number:02d}T09:30:00+02:00",
        "question": question,
        "answer": answer,
        "attachments": list(attachments),
        "change_type": change_type,
        "changed_fields": list(changed_fields),
    }


def stored_question(
    stable_id: str,
    number: int,
    official_datetime: str,
    question: str,
    answer: str,
    *,
    versions=None,
    published: bool = True,
    publication_history=(),
    attachments=(),
):
    return {
        "stable_id": stable_id,
        "number": number,
        "official_datetime": official_datetime,
        "question": question,
        "answer": answer,
        "attachments": list(attachments),
        "published": published,
        "unpublished_at": "2026-07-16T09:30:00+02:00" if not published else "",
        "publication_history": list(publication_history),
        "versions": list(versions or [version(1, question, answer, attachments=attachments)]),
    }


def _document(name: str, questions, *, long_title: bool = False, url: str | None = None):
    del name
    tender = metadata(long_title=long_title, url=url or "https://example.test/licitacion/EXP-17")
    state = {"platform": "PLACE", "questions": {item["stable_id"]: item for item in questions}}
    return build_question_document(tender, state, GENERATED_AT)


def visual_scenarios() -> dict[str, QuestionDocument]:
    attachment = {
        "name": "Aclaración técnica del órgano de contratación.pdf",
        "url": "https://example.test/adjuntos/aclaracion.pdf",
        "source_id": "ATT-17",
    }
    long_question = (
        "¿Puede confirmarse si, para cada una de las entregas parciales previstas durante "
        "la vigencia del contrato, se aceptarán formatos equivalentes siempre que se mantengan "
        "el peso neto, la composición, el etiquetado, los alérgenos y los requisitos de trazabilidad? "
    ) * 5
    long_answer = (
        "Sí. Se admitirán formatos equivalentes cuando se acredite documentalmente el cumplimiento "
        "de todas las especificaciones técnicas y no se alteren ni el precio unitario ni las condiciones "
        "de entrega indicadas en los pliegos. "
    ) * 8
    special_question = "¿Se admite A/B, piñón, café y símbolos { } \\?\nSegunda línea."
    normal = stored_question("q-normal", 1, "08-07-2026 12:28", "¿Se admite el formato A?", "Sí.")
    many_versions = [
        version(1, "Pregunta inicial", "Respuesta inicial"),
        version(2, "Pregunta inicial", "Respuesta revisada", change_type="content_modified", changed_fields=("answer",)),
        version(3, "Pregunta revisada", "Respuesta revisada", change_type="content_modified", changed_fields=("question",)),
        version(4, "Pregunta vigente", "Respuesta vigente", change_type="content_modified", changed_fields=("question", "answer")),
    ]
    return {
        "01_normal": _document("normal", [normal]),
        "02_varias_ordenadas": _document(
            "varias",
            [
                stored_question("q-old", 1, "03-07-2026 14:14", "Pregunta antigua", "Respuesta 1"),
                stored_question("q-new", 2, "08-07-2026 12:28", "Pregunta reciente", "Respuesta 2"),
                stored_question("q-mid", 3, "08-07-2026 10:21", "Pregunta intermedia", "Respuesta 3"),
            ],
        ),
        "03_pendiente": _document(
            "pendiente",
            [stored_question("q-pending", 1, "08-07-2026 12:28", "¿Cuándo se responde?", "")],
        ),
        "04_pregunta_modificada": _document(
            "pregunta-modificada",
            [
                stored_question(
                    "q-mod-q",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta vigente",
                    "Respuesta",
                    versions=[
                        version(1, "Pregunta inicial", "Respuesta"),
                        version(2, "Pregunta vigente", "Respuesta", change_type="content_modified", changed_fields=("question",)),
                    ],
                )
            ],
        ),
        "05_respuesta_modificada": _document(
            "respuesta-modificada",
            [
                stored_question(
                    "q-mod-a",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta",
                    "Respuesta vigente",
                    versions=[
                        version(1, "Pregunta", "Respuesta inicial"),
                        version(2, "Pregunta", "Respuesta vigente", change_type="content_modified", changed_fields=("answer",)),
                    ],
                )
            ],
        ),
        "06_respuesta_incorporada": _document(
            "respuesta-incorporada",
            [
                stored_question(
                    "q-added-a",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta",
                    "Respuesta incorporada",
                    versions=[
                        version(1, "Pregunta", ""),
                        version(2, "Pregunta", "Respuesta incorporada", change_type="answer_added", changed_fields=("answer",)),
                    ],
                )
            ],
        ),
        "07_respuesta_retirada": _document(
            "respuesta-retirada",
            [
                stored_question(
                    "q-removed-a",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta",
                    "",
                    versions=[
                        version(1, "Pregunta", "Respuesta inicial"),
                        version(2, "Pregunta", "", change_type="answer_removed", changed_fields=("answer",)),
                    ],
                )
            ],
        ),
        "08_pregunta_retirada": _document(
            "pregunta-retirada",
            [
                stored_question(
                    "q-withdrawn",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta que dejó de publicarse",
                    "Última respuesta conocida",
                    published=False,
                    publication_history=({"event": "withdrawn", "detected_at": "2026-07-16T09:30:00+02:00"},),
                )
            ],
        ),
        "09_pregunta_reaparecida": _document(
            "pregunta-reaparecida",
            [
                stored_question(
                    "q-restored",
                    1,
                    "08-07-2026 12:28",
                    "Pregunta que reapareció",
                    "Respuesta",
                    publication_history=(
                        {"event": "withdrawn", "detected_at": "2026-07-15T09:30:00+02:00"},
                        {"event": "restored", "detected_at": "2026-07-16T09:30:00+02:00"},
                    ),
                )
            ],
        ),
        "10_historial_extenso": _document(
            "historial",
            [stored_question("q-many", 1, "08-07-2026 12:28", "Pregunta vigente", "Respuesta vigente", versions=many_versions)],
        ),
        "11_adjunto": _document(
            "adjunto",
            [stored_question("q-att", 1, "08-07-2026 12:28", "Consulte el adjunto", "Se adjunta aclaración", attachments=(attachment,))],
        ),
        "12_contenido_largo": _document(
            "contenido-largo",
            [stored_question("q-long", 1, "08-07-2026 12:28", long_question, long_answer)],
            long_title=True,
        ),
        "13_caracteres_y_sin_fecha": _document(
            "caracteres",
            [
                stored_question(
                    "q-special",
                    1,
                    "",
                    special_question,
                    "Sí; se admite tal cual.",
                    versions=[version(1, special_question, "Sí; se admite tal cual.")],
                )
            ],
        ),
    }
