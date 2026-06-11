"""Pure contracts for future Markdown news rendering."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NewsRenderer(Protocol):
    """Conceptual renderer for Markdown-first news content."""

    def render_markdown(self, markdown: str) -> str:
        """Render Markdown to HTML or another display format."""

    def sanitize_html(self, html: str) -> str:
        """Return sanitized HTML safe for controlled rendering."""

