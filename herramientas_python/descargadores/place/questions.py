"""Extracción y validación de snapshots de preguntas específicos de PLACE."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from ..common.question_models import (
    PlatformQuestion,
    PlatformQuestionAttachment,
    QuestionSnapshot,
    extract_platform_datetime,
    literal_text,
    normalize_label,
    normalize_text,
    normalized_key,
)
from .errors import (
    PlaceQuestionDataError,
    PlaceResponseDataError,
    PlaceSessionError,
    PlaceSnapshotIncompleteError,
    PlaceStructureError,
)
from .session import (
    SUBMIT_FORM_RE,
    TIMEOUT_SECONDS,
    create_session,
    ensure_active_session,
    find_link_by_text,
    login,
    post_jsf_link,
    soup_from_response,
)

QUESTION_LINK_RE = re.compile(r"tableEx1:\d+:link\d+$")
QUESTION_STRUCTURE_RE = re.compile(r"tableEx1", re.IGNORECASE)
EMPTY_QUESTION_MARKERS = (
    "no existen preguntas",
    "no hay preguntas",
    "no se han encontrado preguntas",
    "no se encontraron preguntas",
)
EMPTY_TABLE_MARKERS = (
    *EMPTY_QUESTION_MARKERS,
    "no existen registros",
    "no hay registros",
    "no se han encontrado resultados",
    "no se encontraron resultados",
    "no hay resultados",
    "sin resultados",
    "no existen datos",
)


@dataclass(frozen=True)
class QuestionReference:
    updated_at: str
    question: str
    status: str
    source_id: str
    stable_source_id: str = ""


QuestionAnswer = PlatformQuestion
QuestionAttachment = PlatformQuestionAttachment


def normalize_place_question(
    *,
    updated_at: str,
    question: str,
    answer: str = "",
    attachments: tuple[PlatformQuestionAttachment, ...] = (),
    asked_at: str = "",
    answered_at: str = "",
    status: str = "Respondida",
    source_id: str = "",
    source_url: str = "",
) -> PlatformQuestion:
    """Transforma campos PLACE al contrato común sin generar documentos."""

    return PlatformQuestion(
        updated_at=updated_at,
        question=literal_text(question),
        answer=literal_text(answer),
        attachments=tuple(attachments),
        asked_at=extract_platform_datetime(asked_at),
        answered_at=extract_platform_datetime(answered_at),
        status=normalize_text(status),
        source_id=normalize_text(source_id),
        platform="PLACE",
        source_url=source_url,
    )


def direct_cells(row: Tag) -> list[Tag]:
    return [cell for cell in row.find_all(["td", "th"], recursive=False) if isinstance(cell, Tag)]


def field_value(cell: Tag, *, preserve_literal: bool = False) -> str:
    control = cell.find(["textarea", "input"])
    if isinstance(control, Tag):
        raw = control.get_text() if control.name == "textarea" else control.get("value")
        return literal_text(raw) if preserve_literal else normalize_text(raw)
    raw = cell.get_text("\n" if preserve_literal else " ", strip=not preserve_literal)
    return literal_text(raw) if preserve_literal else normalize_text(raw)


def labeled_value(soup: BeautifulSoup, label: str, *, preserve_literal: bool = False) -> str:
    wanted = normalized_key(label)
    for row in soup.find_all("tr"):
        cells = direct_cells(row)
        if len(cells) < 2:
            continue
        if normalized_key(cells[0].get_text(" ", strip=True)) == wanted:
            return field_value(cells[1], preserve_literal=preserve_literal)
    return ""


def first_labeled_value(
    soup: BeautifulSoup,
    *labels: str,
    preserve_literal: bool = False,
) -> str:
    for label in labels:
        value = labeled_value(soup, label, preserve_literal=preserve_literal)
        if value:
            return value
    return ""


def detail_value(soup: BeautifulSoup, label: str) -> str:
    wanted = normalize_label(label)
    label_node: Tag | None = None
    for candidate in soup.find_all(attrs={"title": True}):
        if normalize_label(candidate.get("title")) == wanted:
            label_node = candidate
            break
    if label_node is None:
        for candidate in soup.find_all(["span", "label", "div"]):
            if normalize_label(candidate.get_text(" ", strip=True)) == wanted:
                label_node = candidate
                break
    if not isinstance(label_node, Tag):
        return labeled_value(soup, label)
    container = label_node.find_parent("div", class_="flex-inline")
    if not isinstance(container, Tag):
        return labeled_value(soup, label)
    direct_children = [child for child in container.children if isinstance(child, Tag)]
    try:
        label_index = direct_children.index(label_node)
    except ValueError:
        label_index = -1
    value_children = direct_children[label_index + 1 :]
    if value_children and all(sibling.name == "span" for sibling in value_children):
        combined = normalize_text(" ".join(sibling.get_text(" ", strip=True) for sibling in value_children))
        if combined:
            return combined
    for sibling in value_children:
        if sibling.name == "span":
            value = normalize_text(sibling.get_text(" ", strip=True))
            if value:
                return value
        preferred = sibling.find("a") or sibling.find("span")
        if isinstance(preferred, Tag):
            value = normalize_text(preferred.get_text(" ", strip=True))
            if value:
                return value
        value = normalize_text(sibling.get_text(" ", strip=True))
        if value:
            return value
    return labeled_value(soup, label)


def extract_tender_metadata(soup: BeautifulSoup, profile_url: str) -> dict[str, str]:
    fields = {
        "expediente": "Expediente",
        "organismo": "Órgano de contratación",
        "titulo": "Objeto del contrato",
        "fecha_fin_oferta": "Fecha fin de presentación de oferta",
    }
    metadata = {key: detail_value(soup, label) for key, label in fields.items()}
    metadata["url"] = profile_url
    return metadata


def stable_source_id(link: Tag) -> str:
    for attribute in ("data-question-id", "data-id-pregunta", "data-record-id"):
        value = normalize_text(link.get(attribute))
        if value:
            return value
    href = normalize_text(link.get("href"))
    if href and not href.lower().startswith("javascript"):
        query = parse_qs(urlparse(href).query)
        for key in ("idPregunta", "questionId", "idpregunta"):
            values = query.get(key)
            if values and normalize_text(values[0]):
                return normalize_text(values[0])
    return ""


def question_link_from_row(row: Tag) -> Tag | None:
    candidates = [
        link
        for link in row.find_all("a", id=QUESTION_LINK_RE)
        if (
            isinstance(link, Tag)
            and link.find_parent("tr") is row
            and normalize_text(link.get_text(" ", strip=True))
        )
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    cells = direct_cells(row)
    content_cells = cells[1:-1] if len(cells) >= 3 else []
    content_candidates = [
        link
        for link in candidates
        if any(link.find_parent(["td", "th"]) is cell for cell in content_cells)
    ]
    if len(content_candidates) == 1:
        return content_candidates[0]
    if content_candidates:
        candidates = content_candidates

    actionable = [
        link for link in candidates if SUBMIT_FORM_RE.search(str(link.get("onclick") or ""))
    ]
    if len(actionable) == 1:
        return actionable[0]

    stable = [link for link in candidates if stable_source_id(link)]
    if len(stable) == 1:
        return stable[0]
    candidate_summary = ", ".join(
        f"{normalize_text(link.get('id'))}={normalize_text(link.get_text(' ', strip=True))[:40]}"
        for link in candidates
    )
    raise PlaceStructureError(
        "PLACE mostró más de un enlace candidato para la misma pregunta"
        + (f": {candidate_summary}." if candidate_summary else ".")
    )


def parse_question_references(soup: BeautifulSoup) -> list[QuestionReference]:
    references: list[QuestionReference] = []
    for row in soup.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        link = question_link_from_row(row)
        if link is None:
            continue
        cells = direct_cells(row)
        if len(cells) < 3:
            raise PlaceStructureError("PLACE mostró una fila de pregunta con una estructura incompleta.")
        status = normalize_text(cells[-1].get_text(" ", strip=True))
        question = literal_text(link.get_text(" ", strip=True))
        source_id = str(link.get("id") or "")
        if not question or not source_id:
            raise PlaceQuestionDataError("PLACE mostró una fila de pregunta sin texto o identificador.")
        references.append(
            QuestionReference(
                updated_at=(
                    extract_platform_datetime(cells[0].get_text(" ", strip=True))
                    or extract_platform_datetime(row.get_text(" ", strip=True))
                ),
                question=question,
                status=status,
                source_id=source_id,
                stable_source_id=stable_source_id(link),
            )
        )
    return references


def parse_question_attachments(soup: BeautifulSoup, current_url: str) -> tuple[PlatformQuestionAttachment, ...]:
    attachment_labels = {
        "adjunto",
        "adjuntos",
        "archivo adjunto",
        "archivos adjuntos",
        "documento adjunto",
        "documentos adjuntos",
        "fichero adjunto",
        "ficheros adjuntos",
    }
    attachments: list[PlatformQuestionAttachment] = []
    seen: set[str] = set()
    for row in soup.find_all("tr"):
        cells = direct_cells(row)
        if len(cells) < 2 or normalize_label(cells[0].get_text(" ", strip=True)) not in attachment_labels:
            continue
        for cell in cells[1:]:
            for link in cell.find_all("a"):
                href = normalize_text(link.get("href"))
                source_id = normalize_text(link.get("id"))
                url = urljoin(current_url, href) if href and href not in {"#", "javascript:void(0)"} else ""
                name = (
                    literal_text(link.get_text(" ", strip=True))
                    or literal_text(link.get("title"))
                    or "Archivo adjunto"
                )
                identity = url or source_id or normalized_key(name)
                if identity in seen:
                    continue
                seen.add(identity)
                attachments.append(PlatformQuestionAttachment(name=name, url=url, source_id=source_id))
    return tuple(attachments)


def has_labeled_row(soup: BeautifulSoup, label: str) -> bool:
    wanted = normalized_key(label)
    for row in soup.find_all("tr"):
        cells = direct_cells(row)
        if cells and normalized_key(cells[0].get_text(" ", strip=True)) == wanted:
            return True
    return False


def _has_empty_marker(value: object, markers: tuple[str, ...]) -> bool:
    text = normalized_key(value)
    return any(marker in text for marker in markers)


def _question_table(soup: BeautifulSoup) -> Tag | None:
    structure = soup.find(attrs={"id": QUESTION_STRUCTURE_RE})
    if not isinstance(structure, Tag):
        return None
    if structure.name == "table":
        return structure
    nested = structure.find("table")
    if isinstance(nested, Tag):
        return nested
    parent = structure.find_parent("table")
    return parent if isinstance(parent, Tag) else None


def confirmed_empty_question_list(soup: BeautifulSoup) -> bool:
    page_text = soup.get_text(" ", strip=True)
    if _has_empty_marker(page_text, EMPTY_QUESTION_MARKERS):
        return True

    table = _question_table(soup)
    if table is None:
        return False

    structure = soup.find(attrs={"id": QUESTION_STRUCTURE_RE})
    if isinstance(structure, Tag) and structure.find("a", id=QUESTION_LINK_RE):
        return False

    substantive_rows: list[Tag] = []
    for row in table.find_all("tr"):
        if row.find_parent(["thead", "tfoot"]) is not None:
            continue
        cells = direct_cells(row)
        if not cells or all(cell.name == "th" for cell in cells):
            continue
        row_text = row.get_text(" ", strip=True)
        if _has_empty_marker(row_text, EMPTY_TABLE_MARKERS):
            continue
        if any(cell.get_text(" ", strip=True) for cell in cells):
            substantive_rows.append(row)

    return not substantive_rows


def _question_structure_present(soup: BeautifulSoup) -> bool:
    return bool(
        soup.find(attrs={"id": QUESTION_STRUCTURE_RE})
        or soup.find("a", id=QUESTION_LINK_RE)
        or confirmed_empty_question_list(soup)
    )


def find_next_page_link(soup: BeautifulSoup) -> Tag | None:
    labels = {"siguiente", "pagina siguiente", "página siguiente", "next"}
    for link in soup.find_all("a"):
        label = normalize_label(
            link.get("title")
            or link.get("aria-label")
            or link.get_text(" ", strip=True)
        )
        if label not in {normalize_label(item) for item in labels}:
            continue
        parent_classes = " ".join(str(item) for item in (link.parent.get("class") or [])) if link.parent else ""
        disabled = (
            str(link.get("aria-disabled") or "").casefold() == "true"
            or "disabled" in str(link.get("class") or "").casefold()
            or "disabled" in parent_classes.casefold()
        )
        if not disabled and SUBMIT_FORM_RE.search(str(link.get("onclick") or "")):
            return link
    return None


def pagination_requires_more(soup: BeautifulSoup) -> bool:
    text = normalize_label(soup.get_text(" ", strip=True))
    match = re.search(r"pagina (\d+) de (\d+)", text)
    return bool(match and int(match.group(1)) < int(match.group(2)))


def _reference_page_signature(references: Iterable[QuestionReference]) -> str:
    material = "\n".join(
        f"{item.updated_at}|{normalized_key(item.question)}|{normalize_label(item.status)}"
        for item in references
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_question_page(soup: BeautifulSoup, references: list[QuestionReference]) -> None:
    if references:
        return
    if confirmed_empty_question_list(soup):
        return
    raise PlaceSnapshotIncompleteError(
        "PLACE no confirmó de forma fiable que la lista de preguntas estuviera vacía."
    )


def fetch_questions(
    profile_url: str,
    username: str,
    password: str,
    *,
    session: requests.Session | None = None,
) -> tuple[dict[str, str], list[PlatformQuestion], list[str]]:
    active_session = session or create_session()
    login(active_session, username, password)
    try:
        response = active_session.get(profile_url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise PlaceSessionError("No se pudo abrir la ficha de la licitación en PLACE.") from exc
    ensure_active_session(response)
    soup = soup_from_response(response)
    metadata = extract_tender_metadata(soup, profile_url)
    information_link = find_link_by_text(soup, "Solicitar Información")
    response = post_jsf_link(active_session, soup, response.url, information_link)
    ensure_active_session(response)
    soup = soup_from_response(response)
    if not _question_structure_present(soup):
        raise PlaceStructureError("PLACE no mostró la estructura esperada de preguntas y respuestas.")
    metadata["expediente"] = metadata.get("expediente") or labeled_value(soup, "Expediente")
    metadata["titulo"] = metadata.get("titulo") or labeled_value(soup, "Título")
    questions: list[PlatformQuestion] = []
    structure_novelties: list[str] = []
    known_statuses = {"respondida", "pendiente", "enviada", "anulada"}
    seen_pages: set[str] = set()
    for _page_number in range(1, 101):
        references = parse_question_references(soup)
        validate_question_page(soup, references)
        signature = _reference_page_signature(references)
        if signature in seen_pages:
            raise PlaceSnapshotIncompleteError(
                "PLACE repitió una página de preguntas; el snapshot no puede considerarse completo."
            )
        seen_pages.add(signature)
        for reference in references:
            status_key = normalize_label(reference.status)
            if status_key and status_key not in known_statuses:
                structure_novelties.append(f"Estado de pregunta no reconocido: {reference.status}")
            link = soup.find("a", id=reference.source_id)
            if not isinstance(link, Tag):
                raise PlaceSnapshotIncompleteError(
                    "PLACE cambió la lista mientras se consultaban las preguntas."
                )
            response = post_jsf_link(active_session, soup, response.url, link)
            ensure_active_session(response)
            soup = soup_from_response(response)
            answer_field_present = has_labeled_row(soup, "Respuesta")
            answer = labeled_value(soup, "Respuesta", preserve_literal=True)
            detail_question = labeled_value(soup, "Pregunta", preserve_literal=True) or reference.question
            if not literal_text(detail_question):
                raise PlaceQuestionDataError("PLACE devolvió una pregunta sin texto.")
            if status_key == "respondida" and not answer_field_present:
                raise PlaceResponseDataError(
                    "PLACE no mostró el campo de respuesta de una pregunta respondida."
                )
            detail_updated = (
                extract_platform_datetime(labeled_value(soup, "Actualización"))
                or extract_platform_datetime(reference.updated_at)
            )
            asked_at = extract_platform_datetime(
                first_labeled_value(
                    soup,
                    "Fecha y hora de la pregunta",
                    "Fecha de la pregunta",
                    "Fecha pregunta",
                )
            )
            answered_at = extract_platform_datetime(
                first_labeled_value(
                    soup,
                    "Fecha y hora de la respuesta",
                    "Fecha de la respuesta",
                    "Fecha respuesta",
                )
            )
            questions.append(
                normalize_place_question(
                    updated_at=detail_updated,
                    question=detail_question,
                    answer=answer,
                    attachments=parse_question_attachments(soup, response.url),
                    asked_at=asked_at,
                    answered_at=answered_at,
                    status=reference.status,
                    source_id=reference.stable_source_id,
                    source_url=response.url,
                )
            )
        next_link = find_next_page_link(soup)
        if next_link is None:
            if pagination_requires_more(soup):
                raise PlaceSnapshotIncompleteError(
                    "PLACE indica que existen más páginas, pero no expone la navegación esperada."
                )
            break
        response = post_jsf_link(active_session, soup, response.url, next_link)
        ensure_active_session(response)
        soup = soup_from_response(response)
        if not _question_structure_present(soup):
            raise PlaceSnapshotIncompleteError(
                "La página siguiente no contiene una lista completa de preguntas."
            )
    else:
        raise PlaceSnapshotIncompleteError("PLACE superó el límite seguro de páginas de preguntas.")
    return metadata, questions, structure_novelties


def fetch_question_snapshot(
    profile_url: str,
    username: str,
    password: str,
    *,
    session: requests.Session | None = None,
) -> QuestionSnapshot:
    """Contrato estructurado del adaptador para el motor común."""

    metadata, questions, warnings = fetch_questions(
        profile_url,
        username,
        password,
        session=session,
    )
    return QuestionSnapshot(
        platform="PLACE",
        metadata=metadata,
        questions=tuple(questions),
        complete=True,
        warnings=tuple(warnings),
    )


def fetch_answered_questions(
    profile_url: str,
    username: str,
    password: str,
    *,
    session: requests.Session | None = None,
) -> tuple[dict[str, str], list[PlatformQuestion]]:
    metadata, questions, _novelties = fetch_questions(
        profile_url,
        username,
        password,
        session=session,
    )
    return metadata, [question for question in questions if question.is_answered]
