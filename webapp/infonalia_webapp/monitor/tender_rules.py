from __future__ import annotations

import re
from typing import Iterable, Mapping

from .snapshots import normalize_text


DEFAULT_AI_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "acta": (r"\bacta\b",),
    "resolucion": (r"\bresoluci[oó]n\b",),
    "informe": (r"\binforme\b",),
    "requerimiento": (r"\brequerimiento\b", r"\bsubsanaci[oó]n\b"),
    "adjudicacion": (r"\badjudicaci[oó]n\b",),
    "exclusion": (r"\bexclusi[oó]n\b", r"\bexcluid[oa]s?\b"),
}


def ai_category(title: object, enabled_categories: Iterable[str]) -> str:
    text = normalize_text(title).casefold()
    for category in enabled_categories:
        clean = normalize_text(category).casefold()
        for pattern in DEFAULT_AI_CATEGORY_PATTERNS.get(clean, ()):
            if re.search(pattern, text, re.IGNORECASE):
                return clean
    return ""


def mark_ai_candidates(
    differences: list[dict[str, object]],
    *,
    enabled_categories: Iterable[str],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for source in differences:
        item = dict(source)
        change_type = normalize_text(item.get("change_type"))
        category = ""
        if item.get("item_type") == "document" and change_type in {"document_new", "document_modified"}:
            category = ai_category(item.get("title"), enabled_categories)
        item["ai_candidate"] = bool(category)
        item["ai_category"] = category
        result.append(item)
    return result


def selected_document_paths(differences: Iterable[Mapping[str, object]]) -> list[str]:
    paths: list[str] = []
    for item in differences:
        if not item.get("ai_candidate"):
            continue
        value = item.get("new_value")
        if not isinstance(value, Mapping):
            continue
        path = normalize_text(value.get("relative_path"))
        if path and path not in paths:
            paths.append(path)
    return paths
