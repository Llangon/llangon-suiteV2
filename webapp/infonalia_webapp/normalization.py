from __future__ import annotations

import re
from datetime import datetime, timedelta


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def bool_text(value: object) -> bool:
    return clean_text(value).lower() in {"1", "true", "yes", "si", "sí", "on"}


def parse_money(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw_text = str(value).strip()
    match = re.search(r"\d+(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?", raw_text)
    if not match:
        return None
    text = match.group(0).replace(" EUR", "").replace("€", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date_value(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""

    if re.fullmatch(r"\d+(\.\d+)?", text):
        try:
            serial = float(text)
            if serial > 20000:
                return (datetime(1899, 12, 30) + timedelta(days=serial)).date().isoformat()
        except ValueError:
            pass

    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            return ""

    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if not match:
        return ""

    day, month, year = map(int, match.groups())
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return ""


def parse_time_value(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""

    if re.fullmatch(r"0?\.\d+", text):
        try:
            total_minutes = round(float(text) * 24 * 60)
            hours, minutes = divmod(total_minutes, 60)
            return f"{hours % 24:02d}:{minutes:02d}"
        except ValueError:
            pass

    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        hours, minutes = map(int, match.groups())
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return ""
