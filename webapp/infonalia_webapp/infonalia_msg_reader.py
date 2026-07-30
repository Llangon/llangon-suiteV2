from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InfonaliaMsgContent:
    plain: str
    html: str
    message_id: str
    subject: str
    date: str
    sender: str
    html_source_type: str
    html_decode_replacements: int
    plain_decode_replacements: int


def _as_text(value: object) -> str:
    return "" if value is None else str(value)


def _decode_html(value: object) -> tuple[str, str, int]:
    if isinstance(value, (bytes, bytearray)):
        decoded = bytes(value).decode("utf-8", errors="replace")
        return decoded, "bytes:utf-8", decoded.count("\ufffd")
    decoded = _as_text(value)
    return decoded, type(value).__name__, decoded.count("\ufffd")


def read_msg_path(path: str | Path) -> InfonaliaMsgContent:
    """Read an Outlook MSG through the same adapter used by manual import and tests."""

    import extract_msg

    message = extract_msg.Message(str(Path(path)))
    try:
        plain = _as_text(getattr(message, "body", ""))
        html, html_source_type, html_replacements = _decode_html(
            getattr(message, "htmlBody", b"") or b""
        )
        return InfonaliaMsgContent(
            plain=plain,
            html=html,
            message_id=_as_text(getattr(message, "messageId", "")),
            subject=_as_text(getattr(message, "subject", "")),
            date=_as_text(getattr(message, "date", "")),
            sender=_as_text(getattr(message, "sender", "")),
            html_source_type=html_source_type,
            html_decode_replacements=html_replacements,
            plain_decode_replacements=plain.count("\ufffd"),
        )
    finally:
        message.close()
