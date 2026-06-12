from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

from webapp.infonalia_webapp.news_helpers import news_to_dict, normalize_news_status, slugify


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


def test_news_to_dict_preserves_public_shape() -> None:
    row = {
        "id": 4,
        "title": "Titulo",
        "slug": "titulo",
        "excerpt": "Resumen",
        "content": "Contenido",
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
        "content": "Contenido",
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
