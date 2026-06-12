from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest

from webapp.infonalia_webapp.news_helpers import build_news_payload, news_to_dict, normalize_news_status, slugify


def test_news_helpers_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.news_helpers", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.news_helpers")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_slugify_preserves_current_rules() -> None:
    assert slugify("Nueva contratación pública: Andalucía 2026") == "nueva-contratacion-publica-andalucia-2026"

    with patch("webapp.infonalia_webapp.news_helpers.time.time", return_value=12345):
        assert slugify("!!!") == "noticia-12345"


def test_normalize_news_status_preserves_current_defaults() -> None:
    assert normalize_news_status("published") == "published"
    assert normalize_news_status("ARCHIVED") == "archived"
    assert normalize_news_status("visible") == "draft"
    assert normalize_news_status("") == "draft"


def test_build_news_payload_preserves_current_normalization() -> None:
    payload = build_news_payload(
        {
            "title": " Nueva noticia ",
            "slug": "",
            "excerpt": " Resumen ",
            "content": " Contenido ",
            "category": " Categoria ",
            "tags": " uno,dos ",
            "featuredImage": " https://example.test/image.jpg ",
            "status": "published",
            "isFeatured": True,
            "publishedAt": "",
        },
        now=lambda: "2026-06-12T10:00:00",
        normalize_url_value=lambda value: f"url:{str(value).strip()}",
    )

    assert payload == {
        "title": "Nueva noticia",
        "slug": "nueva-noticia",
        "excerpt": "Resumen",
        "content": "Contenido",
        "category": "Categoria",
        "tags": "uno,dos",
        "featured_image": "url:https://example.test/image.jpg",
        "status": "published",
        "is_featured": 1,
        "published_at": "2026-06-12T10:00:00",
    }


def test_build_news_payload_keeps_explicit_published_at_and_draft_defaults() -> None:
    payload = build_news_payload(
        {
            "title": "Borrador",
            "slug": "slug-manual",
            "status": "unknown",
            "isFeatured": False,
            "publishedAt": "2026-06-11T09:00:00",
        },
        now=lambda: "2026-06-12T10:00:00",
        normalize_url_value=lambda value: str(value or ""),
    )

    assert payload["slug"] == "slug-manual"
    assert payload["status"] == "draft"
    assert payload["is_featured"] == 0
    assert payload["published_at"] == "2026-06-11T09:00:00"


def test_build_news_payload_requires_title() -> None:
    with pytest.raises(ValueError, match="El título es obligatorio."):
        build_news_payload({}, now=lambda: "2026-06-12T10:00:00", normalize_url_value=lambda value: str(value or ""))


def test_news_to_dict_preserves_public_shape() -> None:
    row = {
        "id": 4,
        "title": "Titulo",
        "slug": "titulo",
        "excerpt": "Resumen",
        "content": "Contenido con **negrita** y <script>alert(1)</script> [malo](javascript:alert(1))",
        "category": "Categoria",
        "tags": '["uno"]',
        "featured_image": "https://example.test/image.jpg",
        "status": "published",
        "is_featured": 1,
        "published_at": "2026-06-12T09:30:00",
        "created_at": "2026-06-11T08:00:00",
        "updated_at": "2026-06-12T10:00:00",
        "author": "Infonalia",
    }

    item = news_to_dict(row)

    assert item == {
        "id": 4,
        "title": "Titulo",
        "slug": "titulo",
        "excerpt": "Resumen",
        "content": "Contenido con **negrita** y <script>alert(1)</script> [malo](javascript:alert(1))",
        "contentHtml": "<p>Contenido con <strong>negrita</strong> y &lt;script&gt;alert(1)&lt;/script&gt; malo)</p>",
        "category": "Categoria",
        "tags": '["uno"]',
        "featuredImage": "https://example.test/image.jpg",
        "status": "published",
        "isFeatured": True,
        "publishedAt": "2026-06-12T09:30:00",
        "publishedAtFormatted": "12/06/2026 09:30",
        "createdAt": "2026-06-11T08:00:00",
        "updatedAt": "2026-06-12T10:00:00",
        "author": "Infonalia",
    }
    assert "<script" not in item["contentHtml"].lower()
    assert "javascript:" not in item["contentHtml"].lower()
