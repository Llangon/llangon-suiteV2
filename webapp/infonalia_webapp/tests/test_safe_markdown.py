from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.core.news_contracts import NewsRenderer
from webapp.infonalia_webapp.safe_markdown import SafeMarkdownRenderer


def test_safe_markdown_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.safe_markdown", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.safe_markdown")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess", "smtplib"} & added


def test_safe_markdown_renderer_satisfies_news_renderer_contract() -> None:
    renderer: NewsRenderer = SafeMarkdownRenderer()

    assert isinstance(renderer, NewsRenderer)
    assert renderer.render_markdown("**Titular**") == "<p><strong>Titular</strong></p>"


def test_safe_markdown_renders_basic_allowed_markdown() -> None:
    renderer = SafeMarkdownRenderer()

    html = renderer.render_markdown(
        "# Titular\n\n"
        "Texto con **negrita**, *cursiva* y [enlace](https://example.test?a=1&b=2).\n\n"
        "- Uno\n"
        "- Dos"
    )

    assert "<h1>Titular</h1>" in html
    assert "<strong>negrita</strong>" in html
    assert "<em>cursiva</em>" in html
    assert '<a href="https://example.test?a=1&amp;b=2" rel="noopener noreferrer" target="_blank">enlace</a>' in html
    assert "<ul><li>Uno</li><li>Dos</li></ul>" in html


def test_safe_markdown_escapes_raw_html_and_blocks_unsafe_links() -> None:
    renderer = SafeMarkdownRenderer()

    html = renderer.render_markdown(
        '<script>alert(1)</script><img src=x onerror=alert(1)> '
        '[malo](javascript:alert(1)) [bueno](https://example.test) '
        '![imagen](javascript:alert(1))'
    )

    assert "<script" not in html.lower()
    assert "<img" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "malo" in html
    assert '<a href="https://example.test" rel="noopener noreferrer" target="_blank">bueno</a>' in html
    assert "imagen" in html


def test_sanitize_html_keeps_allowlist_and_removes_dangerous_parts() -> None:
    renderer = SafeMarkdownRenderer()

    html = renderer.sanitize_html(
        '<p onclick="x">Hola<script>alert(1)</script>'
        '<a href="javascript:alert(1)" onclick="x">malo</a>'
        '<a href="https://example.test?a=1&b=2" onclick="x">bueno</a>'
        '<iframe src="https://example.test"></iframe></p>'
    )

    assert "<script" not in html.lower()
    assert "alert(1)" not in html
    assert "onclick" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "<iframe" not in html.lower()
    assert "<p>Hola<a>malo</a>" in html
    assert '<a href="https://example.test?a=1&amp;b=2" rel="noopener noreferrer" target="_blank">bueno</a>' in html
