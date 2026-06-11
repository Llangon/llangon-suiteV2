from __future__ import annotations

from webapp.infonalia_webapp.core.news_contracts import NewsRenderer


class FakeNewsRenderer:
    def render_markdown(self, markdown: str) -> str:
        return markdown.replace("**", "<strong>", 1).replace("**", "</strong>", 1)

    def sanitize_html(self, html: str) -> str:
        return html.replace("<script>", "").replace("</script>", "")


def test_news_renderer_protocol_can_be_used_with_fake_renderer() -> None:
    renderer: NewsRenderer = FakeNewsRenderer()

    html = renderer.render_markdown("**Titular**")
    safe_html = renderer.sanitize_html("<script>alert(1)</script><p>Texto</p>")

    assert isinstance(renderer, NewsRenderer)
    assert html == "<strong>Titular</strong>"
    assert safe_html == "alert(1)<p>Texto</p>"

