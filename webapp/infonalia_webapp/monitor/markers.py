from __future__ import annotations

import re
from pathlib import Path


FOLLOW_MARKER_NAME = "EnSeguimiento.llangon"
ID_MARKER_RE = re.compile(r"^([0-9]+)\.llangon$", re.IGNORECASE)


def read_marker_id(path: Path) -> int | None:
    match = ID_MARKER_RE.fullmatch(path.name)
    if not match:
        return None
    return int(match.group(1))


def is_id_marker(path: Path) -> bool:
    return read_marker_id(path) is not None


def is_follow_marker(path: Path) -> bool:
    return path.name.casefold() == FOLLOW_MARKER_NAME.casefold()


def is_monitor_marker(path: Path) -> bool:
    return is_id_marker(path) or is_follow_marker(path)

