from __future__ import annotations

from datetime import datetime

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


def format_date_es(value: object) -> str:
    text = clean_text(value)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return text or "Sin fecha"


def format_datetime_es(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if "T" not in text and " " not in text:
            return parsed.strftime("%d/%m/%Y")
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass

    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        if pattern == "%Y-%m-%d":
            return parsed.strftime("%d/%m/%Y")
        return parsed.strftime("%d/%m/%Y %H:%M")
    return text
