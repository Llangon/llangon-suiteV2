from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


ALLOWED_BLOCK_TYPES = {"text", "cards", "notice", "criteria", "table"}
ALLOWED_NOTICE_TONES = {"important", "success", "neutral"}


class PortalAISchemaError(ValueError):
    pass


def _text(value: object, *, limit: int = 50000) -> str:
    result = str(value or "").replace("\x00", "").strip()
    if "<script" in result.casefold() or "javascript:" in result.casefold():
        raise PortalAISchemaError("La respuesta IA contiene contenido no permitido.")
    return result[:limit]


def _string_list(value: object, *, limit: int = 500) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value[:limit] if _text(item)]


def _items(value: object, *, limit: int) -> list[object]:
    return value[:limit] if isinstance(value, list) else []


def _pages(value: object, page_count: int) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for raw in value:
        try:
            page = int(raw)
        except (TypeError, ValueError):
            continue
        if 1 <= page <= page_count and page not in result:
            result.append(page)
    return result


def _identifier(value: object, fallback: str) -> str:
    raw = unicodedata.normalize("NFKD", _text(value, limit=120))
    folded = "".join(char for char in raw if not unicodedata.combining(char)).casefold()
    clean = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return clean[:80] or fallback


def _normalize_block(raw: object, *, page_count: int, fallback_id: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise PortalAISchemaError("La respuesta IA contiene un bloque no válido.")
    block_type = _text(raw.get("type"), limit=30).casefold()
    if block_type not in ALLOWED_BLOCK_TYPES:
        raise PortalAISchemaError(f"Tipo de bloque no permitido: {block_type or 'vacío'}.")
    block: dict[str, object] = {
        "id": _identifier(raw.get("id"), fallback_id),
        "type": block_type,
        "sourcePages": _pages(raw.get("sourcePages"), page_count),
    }
    if not block["sourcePages"]:
        raise PortalAISchemaError(f"El bloque {block['id']} no indica páginas de origen.")
    if block_type == "text":
        block.update(
            {
                "title": _text(raw.get("title")),
                "paragraphs": _string_list(raw.get("paragraphs")),
                "bullets": _string_list(raw.get("bullets")),
            }
        )
    elif block_type == "cards":
        items = []
        for item in _items(raw.get("items"), limit=200):
            if isinstance(item, dict):
                items.append({"title": _text(item.get("title")), "text": _text(item.get("text"))})
        block["items"] = items
    elif block_type == "notice":
        tone = _text(raw.get("tone"), limit=20).casefold()
        block.update(
            {
                "tone": tone if tone in ALLOWED_NOTICE_TONES else "neutral",
                "title": _text(raw.get("title")),
                "text": _text(raw.get("text")),
            }
        )
    elif block_type == "criteria":
        criteria = []
        for item in _items(raw.get("criteria"), limit=500):
            if isinstance(item, dict):
                criteria.append(
                    {
                        "name": _text(item.get("name")),
                        "score": _text(item.get("score")),
                        "description": _text(item.get("description")),
                    }
                )
        block.update(
            {
                "title": _text(raw.get("title")),
                "scope": _text(raw.get("scope")),
                "criteria": criteria,
                "total": _text(raw.get("total")),
            }
        )
    else:
        columns = _string_list(raw.get("columns"), limit=100)
        rows = []
        for row in _items(raw.get("rows"), limit=5000):
            if isinstance(row, list):
                rows.append([_text(cell) for cell in row[: len(columns) or 100]])
        block.update(
            {
                "title": _text(raw.get("title")),
                "caption": _text(raw.get("caption")),
                "columns": columns,
                "rows": rows,
            }
        )
    return block


def _normalize_tender(raw: object, base: dict[str, object]) -> dict[str, object]:
    data = raw if isinstance(raw, dict) else {}
    deadline_raw = data.get("deadline") if isinstance(data.get("deadline"), dict) else {}
    deadline = {key: _text(deadline_raw.get(key), limit=100) for key in ("day", "month", "year", "weekday", "time")}
    highlights = []
    for item in _items(data.get("highlights"), limit=24):
        if isinstance(item, dict):
            highlights.append({key: _text(item.get(key)) for key in ("label", "value", "detail")})
    details = []
    for item in _items(data.get("details"), limit=200):
        if isinstance(item, dict):
            emphasis = _text(item.get("emphasis"), limit=20).casefold()
            details.append(
                {
                    "label": _text(item.get("label")),
                    "value": _text(item.get("value")),
                    "note": _text(item.get("note")),
                    "emphasis": emphasis if emphasis in {"positive", "warning"} else "",
                }
            )
    return {
        "recipient": _text(data.get("recipient") or base.get("recipient")),
        "reference": _text(data.get("reference") or base.get("reference")),
        "title": _text(data.get("title") or base.get("title")),
        "submissionChannel": _text(data.get("submissionChannel")),
        "tenderUrl": _text(data.get("tenderUrl") or base.get("tender_url")),
        "deadline": deadline,
        "highlights": highlights,
        "details": details,
    }


def parse_portal_ai_payload(payload: object, base_model: dict[str, object]) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise PortalAISchemaError("La IA no devolvió un objeto JSON.")
    source = dict(base_model.get("source") or {})
    page_count = int(source.get("page_count") or 0)
    if page_count <= 0:
        raise PortalAISchemaError("El modelo base no contiene páginas.")
    sections = []
    block_ids: set[str] = set()
    for section_index, raw_section in enumerate(_items(payload.get("sections"), limit=100), 1):
        if not isinstance(raw_section, dict):
            continue
        section_id = _identifier(raw_section.get("id"), f"seccion-{section_index}")
        blocks = []
        for block_index, raw_block in enumerate(_items(raw_section.get("blocks"), limit=500), 1):
            block = _normalize_block(raw_block, page_count=page_count, fallback_id=f"{section_id}-{block_index}")
            block_id = str(block["id"])
            if block_id in block_ids:
                block_id = f"{block_id}-{block_index}"
                block["id"] = block_id
            block_ids.add(block_id)
            blocks.append(block)
        if not blocks:
            continue
        section_pages = _pages(raw_section.get("sourcePages"), page_count)
        if not section_pages:
            section_pages = sorted({page for block in blocks for page in block["sourcePages"]})
        sections.append(
            {
                "id": section_id,
                "eyebrow": _text(raw_section.get("eyebrow")),
                "title": _text(raw_section.get("title")) or f"Sección {section_index}",
                "introduction": _text(raw_section.get("introduction")),
                "sourcePages": section_pages,
                "blocks": blocks,
            }
        )
    if not sections:
        raise PortalAISchemaError("La IA no devolvió secciones con contenido.")
    coverage = []
    seen_pages: set[int] = set()
    for raw in _items(payload.get("sourceCoverage"), limit=page_count):
        if not isinstance(raw, dict):
            continue
        try:
            page = int(raw.get("page"))
        except (TypeError, ValueError):
            continue
        if page < 1 or page > page_count or page in seen_pages:
            continue
        seen_pages.add(page)
        covered_ids = [item for item in _string_list(raw.get("coveredBlockIds"), limit=500) if item in block_ids]
        coverage.append(
            {
                "page": page,
                "sourceSha256": _text(raw.get("sourceSha256"), limit=100),
                "visualReviewed": bool(raw.get("visualReviewed")),
                "coveredBlockIds": covered_ids,
                "unmappedContent": _string_list(raw.get("unmappedContent"), limit=500),
            }
        )
    return {
        "tender": _normalize_tender(payload.get("tender"), dict(base_model.get("tender") or {})),
        "sections": sections,
        "sourceCoverage": coverage,
        "qualityNotes": _string_list(payload.get("qualityNotes"), limit=100),
        "payloadSha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
    }


def block_plain_text(block: dict[str, object]) -> str:
    values: list[str] = []
    for key, value in block.items():
        if key in {"id", "type", "sourcePages"}:
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, list):
                    values.extend(str(cell) for cell in item)
                elif isinstance(item, dict):
                    values.extend(str(cell) for cell in item.values())
    return " ".join(values)
