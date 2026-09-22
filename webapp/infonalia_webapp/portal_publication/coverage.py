from __future__ import annotations

from typing import Iterable


def audit_coverage(source: dict[str, object], sections: Iterable[dict[str, object]]) -> dict[str, object]:
    pages = list(source.get("pages") or [])
    mapped: dict[int, list[dict[str, object]]] = {}
    for section in sections:
        for block in section.get("blocks") or []:
            for page_number in block.get("sourcePages") or block.get("source_pages") or []:
                mapped.setdefault(int(page_number), []).append(block)
    missing_pages: list[int] = []
    altered_pages: list[int] = []
    visual_required: list[int] = []
    for page in pages:
        number = int(page["number"])
        blocks = mapped.get(number, [])
        if not blocks:
            missing_pages.append(number)
            continue
        source_text = str(page.get("text") or "")
        faithful = any(
            block.get("type") == "source_page"
            and str(block.get("text") or "") == source_text
            and str(block.get("sourceSha256") or block.get("source_sha256") or "")
            == str(page.get("text_sha256") or "")
            for block in blocks
        )
        if not faithful:
            altered_pages.append(number)
        if bool(page.get("visual_fallback_required")):
            visual_required.append(number)
    fully_mapped = not missing_pages and not altered_pages and len(mapped) == len(pages)
    status = "ready_for_ai_enrichment" if fully_mapped and not visual_required else "needs_review"
    warnings: list[str] = []
    if missing_pages:
        warnings.append(f"Páginas sin mapear: {', '.join(map(str, missing_pages))}.")
    if altered_pages:
        warnings.append(f"Páginas cuyo texto no se conserva literalmente: {', '.join(map(str, altered_pages))}.")
    if visual_required:
        warnings.append(
            "Se exige respaldo visual para las páginas: " + ", ".join(map(str, visual_required)) + "."
        )
    return {
        "status": status,
        "publication_allowed": False,
        "pages_total": len(pages),
        "pages_mapped": len(set(mapped) & {int(page["number"]) for page in pages}),
        "missing_pages": missing_pages,
        "altered_pages": altered_pages,
        "visual_fallback_required_pages": visual_required,
        "literal_source_preserved": fully_mapped,
        "warnings": warnings,
    }
