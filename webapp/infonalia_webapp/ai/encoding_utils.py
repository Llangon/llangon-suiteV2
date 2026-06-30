from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MOJIBAKE_MARKERS = ("Ã", "Â", "â€”", "â€“", "â€", "ðŸ", "�")


def safe_read_text_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def safe_write_text_utf8(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", errors="replace")


def safe_json_dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_json_load(path: Path) -> Any:
    return json.loads(safe_read_text_utf8(path))


def contains_mojibake(value: object) -> bool:
    if isinstance(value, dict):
        return any(contains_mojibake(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(contains_mojibake(item) for item in value)
    text = str(value or "")
    return any(marker in text for marker in MOJIBAKE_MARKERS)
