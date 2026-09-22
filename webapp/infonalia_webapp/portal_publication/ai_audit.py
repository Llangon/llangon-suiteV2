from __future__ import annotations

import re
import unicodedata

from .ai_schema import block_plain_text


TOKEN_COVERAGE_THRESHOLD = 0.95


def _tokens(value: object) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    folded = "".join(char for char in normalized if not unicodedata.combining(char)).casefold()
    return {token for token in re.findall(r"[a-z0-9]+", folded) if len(token) >= 3 or token.isdigit()}


def audit_ai_enrichment(base_model: dict[str, object], enrichment: dict[str, object]) -> dict[str, object]:
    source = dict(base_model.get("source") or {})
    pages = list(source.get("pages") or [])
    blocks_by_id: dict[str, dict[str, object]] = {}
    for section in enrichment.get("sections") or []:
        for block in section.get("blocks") or []:
            blocks_by_id[str(block.get("id") or "")] = block
    coverage_by_page = {
        int(item["page"]): item
        for item in enrichment.get("sourceCoverage") or []
        if isinstance(item, dict) and item.get("page")
    }
    missing_coverage_pages: list[int] = []
    invalid_hash_pages: list[int] = []
    visual_unreviewed_pages: list[int] = []
    unmapped_pages: list[int] = []
    resolved_unmapped_by_page: dict[str, list[str]] = {}
    invalid_block_mapping_pages: list[int] = []
    pages_below_token_threshold: list[int] = []
    token_coverage_by_page: dict[str, float] = {}
    fallback_pages: set[int] = set()

    for page in pages:
        number = int(page["number"])
        item = coverage_by_page.get(number)
        if not item:
            missing_coverage_pages.append(number)
            fallback_pages.add(number)
            continue
        if str(item.get("sourceSha256") or "") != str(page.get("text_sha256") or ""):
            invalid_hash_pages.append(number)
            fallback_pages.add(number)
        # El PDF se envía también como documento visual: cada página debe quedar
        # confirmada, incluso cuando la extracción de texto parezca fiable.
        if not bool(item.get("visualReviewed")):
            visual_unreviewed_pages.append(number)
            fallback_pages.add(number)
        covered_ids = [str(value) for value in item.get("coveredBlockIds") or []]
        mapped_blocks = [blocks_by_id[block_id] for block_id in covered_ids if block_id in blocks_by_id]
        if not mapped_blocks or any(number not in (block.get("sourcePages") or []) for block in mapped_blocks):
            invalid_block_mapping_pages.append(number)
            fallback_pages.add(number)
        source_tokens = _tokens(page.get("text"))
        rendered_tokens = _tokens(" ".join(block_plain_text(block) for block in mapped_blocks))
        unresolved_items: list[str] = []
        resolved_items: list[str] = []
        for raw_unmapped in item.get("unmappedContent") or []:
            unmapped_text = str(raw_unmapped or "").strip()
            if not unmapped_text:
                continue
            unmapped_tokens = _tokens(unmapped_text)
            unmapped_ratio = 1.0 if not unmapped_tokens else len(unmapped_tokens & rendered_tokens) / len(unmapped_tokens)
            if unmapped_ratio >= TOKEN_COVERAGE_THRESHOLD:
                resolved_items.append(unmapped_text)
            else:
                unresolved_items.append(unmapped_text)
        if resolved_items:
            resolved_unmapped_by_page[str(number)] = resolved_items
        if unresolved_items:
            unmapped_pages.append(number)
            fallback_pages.add(number)
        ratio = 1.0 if not source_tokens else len(source_tokens & rendered_tokens) / len(source_tokens)
        token_coverage_by_page[str(number)] = round(ratio, 4)
        if ratio < TOKEN_COVERAGE_THRESHOLD:
            pages_below_token_threshold.append(number)
            fallback_pages.add(number)

    ready = not fallback_pages and len(coverage_by_page) == len(pages)
    warnings: list[str] = []
    if missing_coverage_pages:
        warnings.append("Faltan declaraciones de cobertura para páginas: " + ", ".join(map(str, missing_coverage_pages)) + ".")
    if invalid_hash_pages:
        warnings.append("No coinciden las huellas de páginas: " + ", ".join(map(str, invalid_hash_pages)) + ".")
    if visual_unreviewed_pages:
        warnings.append("Falta revisión visual en páginas: " + ", ".join(map(str, visual_unreviewed_pages)) + ".")
    if unmapped_pages:
        warnings.append("La IA declara contenido no trasladado en páginas: " + ", ".join(map(str, unmapped_pages)) + ".")
    if invalid_block_mapping_pages:
        warnings.append("La trazabilidad de bloques es incompleta en páginas: " + ", ".join(map(str, invalid_block_mapping_pages)) + ".")
    if pages_below_token_threshold:
        warnings.append("La cobertura textual es inferior al 95 % en páginas: " + ", ".join(map(str, pages_below_token_threshold)) + ".")
    return {
        "status": "preview_ready" if ready else "needs_review",
        "publication_allowed": False,
        "ready_for_publication_review": ready,
        "pages_total": len(pages),
        "pages_audited": len(coverage_by_page),
        "missing_coverage_pages": missing_coverage_pages,
        "invalid_hash_pages": invalid_hash_pages,
        "visual_unreviewed_pages": visual_unreviewed_pages,
        "unmapped_pages": unmapped_pages,
        "resolved_unmapped_by_page": resolved_unmapped_by_page,
        "invalid_block_mapping_pages": invalid_block_mapping_pages,
        "pages_below_token_threshold": pages_below_token_threshold,
        "token_coverage_by_page": token_coverage_by_page,
        "fallback_pages": sorted(fallback_pages),
        "warnings": warnings,
    }


def apply_ai_enrichment(
    base_model: dict[str, object],
    enrichment: dict[str, object],
    audit: dict[str, object],
    *,
    provider: str,
    model: str,
) -> dict[str, object]:
    sections = list(enrichment.get("sections") or [])
    fallback_pages = set(int(page) for page in audit.get("fallback_pages") or [])
    if fallback_pages:
        blocks = []
        for page in base_model.get("source", {}).get("pages", []):
            number = int(page["number"])
            if number not in fallback_pages:
                continue
            blocks.append(
                {
                    "type": "source_page",
                    "page": number,
                    "text": page.get("text") or "",
                    "sourcePages": [number],
                    "sourceSha256": page.get("text_sha256") or "",
                    "visualFallbackRequired": bool(page.get("visual_fallback_required")),
                }
            )
        sections.append(
            {
                "id": "verificacion-contenido-literal",
                "eyebrow": "Control de integridad",
                "title": "Contenido pendiente de estructuración completa",
                "introduction": "Estas páginas se conservan literalmente porque la auditoría automática no permite certificar todavía su traslado completo.",
                "sourcePages": sorted(fallback_pages),
                "blocks": blocks,
            }
        )
    generation = dict(base_model.get("generation") or {})
    generation.update(
        {
            "mode": "ai_enriched",
            "provider": provider,
            "model": model,
            "published": False,
            "external_actions": [],
        }
    )
    return {
        **base_model,
        "schema_version": "llangon.portal.v2",
        "generation": generation,
        "tender": enrichment.get("tender") or base_model.get("tender") or {},
        "sections": sections,
        "sourceCoverage": enrichment.get("sourceCoverage") or [],
        "qualityNotes": enrichment.get("qualityNotes") or [],
        "coverage": audit,
    }
