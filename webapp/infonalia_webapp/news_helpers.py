from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

try:
    from .formatting import format_datetime_es
    from .normalization import clean_text
    from .safe_markdown import SafeMarkdownRenderer
except ImportError:
    from formatting import format_datetime_es
    from normalization import clean_text
    from safe_markdown import SafeMarkdownRenderer


NEWS_STATUSES = {"draft", "published", "archived"}
NEWS_RENDERER = SafeMarkdownRenderer()


def slugify(value: object) -> str:
    text = unicodedata.normalize("NFD", clean_text(value).lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:100].strip("-") or f"noticia-{int(time.time())}"


def normalize_news_status(value: object) -> str:
    status = clean_text(value).lower()
    return status if status in NEWS_STATUSES else "draft"


def news_to_dict(row: Any) -> dict:
    content = row["content"]
    return {
        "id": row["id"],
        "title": row["title"],
        "slug": row["slug"],
        "excerpt": row["excerpt"],
        "content": content,
        "contentHtml": NEWS_RENDERER.render_markdown(content),
        "category": row["category"],
        "tags": row["tags"],
        "featuredImage": row["featured_image"],
        "status": row["status"],
        "isFeatured": bool(row["is_featured"]),
        "publishedAt": row["published_at"],
        "publishedAtFormatted": format_datetime_es(row["published_at"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "author": row["author"],
    }
