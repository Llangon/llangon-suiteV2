"""Extracción pública y normalización de preguntas respondidas de Catalunya."""

from __future__ import annotations

import json
from typing import Any

from ..common.question_models import (
    PlatformQuestion,
    PlatformQuestionAttachment,
    QuestionSnapshot,
    datetime_sort_value,
    extract_platform_datetime,
    literal_text,
)
from .client import (
    get_json,
    idioma_desde_url,
    origen_catalunya,
    portal_api_url,
    url_api_detall_publicacion,
)
from .errors import (
    CatalunyaAccessError,
    CatalunyaQuestionDataError,
    CatalunyaSnapshotIncompleteError,
    CatalunyaStructureError,
)


DEFAULT_PAGE_SIZE = 20
MAX_SAFE_PAGES = 500


def _as_list(value: object) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _string(value: object) -> str:
    if isinstance(value, dict):
        return literal_text(value.get("text") or value.get("label") or value.get("nom") or value.get("name"))
    return literal_text(value)


def _deadline(detail: dict[str, Any]) -> str:
    try:
        return _string(
            detail["dades"]["publicacio"]["dadesPublicacio"]["dataTerminiPresentacioOSolicitud"]
        )
    except (KeyError, TypeError):
        return ""


def _question_metadata(detail: dict[str, Any], info: dict[str, Any], profile_url: str) -> dict[str, str]:
    return {
        "platform": "CATALUNYA",
        "expediente": _string(info.get("codiExpedient") or detail.get("codiExpedient")),
        "organismo": _string(info.get("organ") or detail.get("organ")),
        "titulo": _string(
            info.get("denominacio")
            or detail.get("titol")
            or detail.get("denominacioUltimaPublicacioExpedient")
        ),
        "fecha_fin_oferta": _deadline(detail),
        "url": profile_url,
        "display_timezone": "Europe/Madrid",
        "authentication_required": "false",
        "expedient_id": _string(info.get("expedientId") or detail.get("expedientId")),
    }


def obtener_contexto_licitacion(session, profile_url: str) -> tuple[str, str, dict, dict, dict[str, str]]:
    detail_url = url_api_detall_publicacion(profile_url)
    if not detail_url:
        raise CatalunyaStructureError("La URL de Catalunya no identifica una publicación válida.")
    detail = get_json(session, detail_url, referer=profile_url)
    if not isinstance(detail, dict):
        raise CatalunyaStructureError("El detalle de la publicación no tiene el formato esperado.")
    expedient_id = _string(detail.get("expedientId"))
    if not expedient_id:
        raise CatalunyaStructureError("Catalunya no devolvió el identificador del expediente.")
    origin = origen_catalunya(profile_url)
    info_url = portal_api_url(origin, f"informacio-basica/{expedient_id}")
    info = get_json(session, info_url, referer=profile_url)
    if not isinstance(info, dict):
        raise CatalunyaStructureError("La información básica del expediente no es válida.")
    if bool(info.get("accesExclusiu") or detail.get("accesExclusiu")):
        raise CatalunyaAccessError(
            "El expediente requiere acceso exclusivo y no puede consultarse con el flujo público."
        )
    returned_id = _string(info.get("expedientId") or expedient_id)
    if returned_id != expedient_id:
        raise CatalunyaSnapshotIncompleteError("La información básica pertenece a otro expediente.")
    return origin, expedient_id, detail, info, _question_metadata(detail, info, profile_url)


def _validate_page(payload: object, expected_page: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
        raise CatalunyaSnapshotIncompleteError("Catalunya devolvió una página de respuestas incompleta.")
    try:
        page_number = int(payload.get("number"))
        total_pages = int(payload.get("totalPages"))
        total_elements = int(payload.get("totalElements"))
    except (TypeError, ValueError) as exc:
        raise CatalunyaSnapshotIncompleteError("La paginación de respuestas no contiene totales válidos.") from exc
    if page_number != expected_page or total_pages < 0 or total_elements < 0:
        raise CatalunyaSnapshotIncompleteError("La paginación de respuestas no es coherente.")
    if total_pages > MAX_SAFE_PAGES:
        raise CatalunyaSnapshotIncompleteError("Catalunya superó el límite seguro de páginas de respuestas.")
    return payload


def _page_signature(page: dict[str, Any]) -> tuple[int, int, tuple[str, ...]]:
    return (
        int(page.get("totalPages") or 0),
        int(page.get("totalElements") or 0),
        tuple(_string(item.get("id")) for item in page.get("content") or [] if isinstance(item, dict)),
    )


def obtener_listado_completo(
    session,
    origin: str,
    expedient_id: str,
    profile_url: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], list[str]]:
    list_url = portal_api_url(origin, f"respostes/{expedient_id}")

    def fetch(page: int) -> dict[str, Any]:
        return _validate_page(
            get_json(
                session,
                list_url,
                referer=profile_url,
                params={"page": page, "pageSize": page_size},
            ),
            page,
        )

    first = fetch(0)
    total_pages = int(first.get("totalPages") or 0)
    total_elements = int(first.get("totalElements") or 0)
    try:
        reported_size = int(first.get("size") or page_size)
    except (TypeError, ValueError) as exc:
        raise CatalunyaSnapshotIncompleteError("Catalunya no indicó un tamaño de página válido.") from exc
    expected_pages = 0 if total_elements == 0 else (total_elements + reported_size - 1) // reported_size
    if reported_size <= 0 or total_pages != expected_pages:
        raise CatalunyaSnapshotIncompleteError(
            f"Catalunya anunció {total_elements} respuestas con una paginación incoherente."
        )
    pages = [first]
    for page_number in range(1, total_pages):
        page = fetch(page_number)
        if int(page.get("totalPages") or 0) != total_pages or int(page.get("totalElements") or 0) != total_elements:
            raise CatalunyaSnapshotIncompleteError("Los totales cambiaron durante la paginación.")
        pages.append(page)
    confirmation = fetch(0)
    if _page_signature(confirmation) != _page_signature(first):
        raise CatalunyaSnapshotIncompleteError("Las respuestas cambiaron durante la consulta.")
    items = [item for page in pages for item in page.get("content") or []]
    if len(items) != total_elements:
        raise CatalunyaSnapshotIncompleteError(
            f"Catalunya anunció {total_elements} respuestas pero se obtuvieron {len(items)}."
        )
    identifiers = [_string(item.get("id")) for item in items if isinstance(item, dict)]
    if any(not identifier for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
        raise CatalunyaSnapshotIncompleteError("El listado contiene identificadores vacíos o duplicados.")
    return items, []


def _root_publication_id(detail: dict[str, Any], current_id: str) -> tuple[str, tuple[str, ...]]:
    navigation = [item for item in _as_list(detail.get("navegacioEsmenes")) if isinstance(item, dict)]
    identifiers = tuple(
        _string(item.get("publicacioId") or item.get("id"))
        for item in sorted(
            navigation,
            key=lambda item: (
                datetime_sort_value(item.get("dataPublicacio")) is None,
                datetime_sort_value(item.get("dataPublicacio")) or float("inf"),
            ),
        )
        if _string(item.get("publicacioId") or item.get("id"))
    )
    return (identifiers[0] if identifiers else current_id), identifiers or (current_id,)


def _attachments(origin: str, data: dict[str, Any]) -> tuple[PlatformQuestionAttachment, ...]:
    attachments: list[PlatformQuestionAttachment] = []
    for document in _as_list(data.get("documents")):
        if not isinstance(document, dict):
            continue
        document_id = _string(document.get("id"))
        document_hash = _string(document.get("hash"))
        if not document_id or not document_hash:
            raise CatalunyaQuestionDataError("Una respuesta contiene un adjunto sin identificador o hash.")
        name = _string(document.get("titol")) or f"Adjunto {document_id}"
        attachments.append(
            PlatformQuestionAttachment(
                name=name,
                url=portal_api_url(origin, f"descarrega-document/{document_id}/{document_hash}"),
                source_id=document_id,
                role="answer",
            )
        )
    return tuple(attachments)


def _serialized_optional(value: object) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return literal_text(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalizar_respuesta(
    item: dict[str, Any],
    detail: dict[str, Any],
    *,
    origin: str,
    language: str,
) -> tuple[PlatformQuestion, list[str]]:
    current_id = _string(item.get("id"))
    data = detail.get("dades")
    if not current_id or not isinstance(data, dict):
        raise CatalunyaQuestionDataError("Una respuesta publicada no contiene su detalle completo.")
    if bool(detail.get("despublicat")):
        raise CatalunyaSnapshotIncompleteError("Una respuesta listada figura simultáneamente como despublicada.")
    question_text = literal_text(item.get("titol"))
    answer_text = literal_text(item.get("descripcio"))
    detail_question = literal_text(data.get("titol"))
    detail_answer = literal_text(data.get("descripcio"))
    if not question_text or not detail_question:
        raise CatalunyaQuestionDataError("Catalunya publicó una respuesta sin texto de pregunta.")
    if question_text != detail_question or answer_text != detail_answer:
        raise CatalunyaSnapshotIncompleteError("El listado y el detalle de una respuesta no coinciden.")
    published_at = extract_platform_datetime(detail.get("dataPublicacio") or item.get("dataPublicacio"))
    if not published_at:
        raise CatalunyaQuestionDataError("Una respuesta no contiene una fecha de publicación válida.")
    root_id, chain = _root_publication_id(detail, current_id)
    question_attachments = _attachments(origin, data)
    warnings: list[str] = []
    if not answer_text and not question_attachments:
        warnings.append(f"La respuesta {current_id} no contiene texto ni adjuntos.")
    metadata: list[tuple[str, str]] = [
        ("current_source_id", current_id),
        ("amendment_chain", ",".join(chain)),
        ("amendment", "true" if bool(item.get("esEsmena") or data.get("tipusEsmena")) else "false"),
    ]
    amendment_reason = _string(data.get("descripcioEsmena"))
    if amendment_reason:
        metadata.append(("amendment_reason", amendment_reason))
    lots = _serialized_optional(data.get("lots"))
    if lots:
        metadata.append(("lots", lots))
    related = _serialized_optional(data.get("linkInteres"))
    if related:
        metadata.append(("related_links", related))
    source_url = f"{origin}/{language}/detall-avis/resposta/{current_id}"
    return (
        PlatformQuestion(
            updated_at=published_at,
            question=question_text,
            answer=answer_text,
            attachments=question_attachments,
            asked_at="",
            answered_at=published_at,
            status="Respondida",
            source_id=root_id,
            platform="CATALUNYA",
            source_url=source_url,
            metadata=tuple(metadata),
        ),
        warnings,
    )


def obtener_snapshot_preguntas(
    session,
    profile_url: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> QuestionSnapshot:
    origin, expedient_id, _detail, _info, metadata = obtener_contexto_licitacion(session, profile_url)
    items, warnings = obtener_listado_completo(
        session,
        origin,
        expedient_id,
        profile_url,
        page_size=page_size,
    )
    questions: list[PlatformQuestion] = []
    language = idioma_desde_url(profile_url)
    for item in items:
        if not isinstance(item, dict):
            raise CatalunyaSnapshotIncompleteError("El listado contiene una respuesta no estructurada.")
        current_id = _string(item.get("id"))
        detail_url = portal_api_url(origin, f"detall-avis/resposta/{current_id}")
        detail = get_json(session, detail_url, referer=profile_url)
        if not isinstance(detail, dict) or _string(detail.get("expedientId")) != expedient_id:
            raise CatalunyaSnapshotIncompleteError("El detalle de una respuesta pertenece a otro expediente.")
        normalized, item_warnings = normalizar_respuesta(
            item,
            detail,
            origin=origin,
            language=language,
        )
        questions.append(normalized)
        warnings.extend(item_warnings)
    return QuestionSnapshot(
        platform="CATALUNYA",
        metadata=metadata,
        questions=tuple(questions),
        complete=True,
        warnings=tuple(dict.fromkeys(warnings)),
    )
