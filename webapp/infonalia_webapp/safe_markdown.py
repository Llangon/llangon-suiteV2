from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


ALLOWED_TAGS = {"p", "h1", "h2", "h3", "ul", "ol", "li", "strong", "em", "a", "br"}
SKIP_CONTENT_TAGS = {"script", "style"}


def is_safe_url(value: str) -> bool:
    parsed = urlparse(clean_text(value))
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _format_emphasis(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def _format_inline(text: str) -> str:
    image_pattern = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)\)")
    link_pattern = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")

    def image_replacement(match: re.Match[str]) -> str:
        return _format_emphasis(match.group(1))

    text = image_pattern.sub(image_replacement, text)
    parts: list[str] = []
    position = 0
    for match in link_pattern.finditer(text):
        parts.append(_format_emphasis(text[position : match.start()]))
        label = _format_emphasis(match.group(1))
        url = clean_text(match.group(2))
        if is_safe_url(url):
            safe_url = html.escape(url, quote=True)
            parts.append(
                f'<a href="{safe_url}" rel="noopener noreferrer" target="_blank">{label}</a>'
            )
        else:
            parts.append(label)
        position = match.end()
    parts.append(_format_emphasis(text[position:]))
    return "".join(parts)


def _strip_list_marker(line: str) -> str:
    return re.sub(r"^[-*]\s+", "", line)


class _HtmlSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = ""
            for name, value in attrs:
                if name.lower() == "href" and value and is_safe_url(value):
                    href = html.escape(clean_text(value), quote=True)
                    break
            if href:
                self.parts.append(
                    f'<a href="{href}" rel="noopener noreferrer" target="_blank">'
                )
            else:
                self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        if not self.skip_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.skip_depth:
            self.parts.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self.parts)


class SafeMarkdownRenderer:
    def render_markdown(self, markdown: str) -> str:
        blocks = re.split(r"\n\s*\n", clean_text(markdown).replace("\r\n", "\n"))
        rendered: list[str] = []

        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", lines[0])
            if heading and len(lines) == 1:
                level = len(heading.group(1))
                rendered.append(f"<h{level}>{_format_inline(heading.group(2))}</h{level}>")
                continue
            if all(re.match(r"^[-*]\s+.+$", line) for line in lines):
                items = "".join(
                    f"<li>{_format_inline(_strip_list_marker(line))}</li>"
                    for line in lines
                )
                rendered.append(f"<ul>{items}</ul>")
                continue
            paragraph = " ".join(lines)
            rendered.append(f"<p>{_format_inline(paragraph)}</p>")

        return self.sanitize_html("".join(rendered))

    def sanitize_html(self, html_text: str) -> str:
        sanitizer = _HtmlSanitizer()
        sanitizer.feed(html_text or "")
        sanitizer.close()
        return sanitizer.get_html()
