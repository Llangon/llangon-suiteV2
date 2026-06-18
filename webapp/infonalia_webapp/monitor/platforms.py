"""Future platform polling extension point.

Monitor V0 deliberately does not call PLACE or any remote platform.
"""

from __future__ import annotations

from .scanner import MarkerRecord


def check_followed_platforms(markers: list[MarkerRecord], *, dry_run: bool) -> dict[str, object]:
    followed = [marker for marker in markers if marker.is_followed]
    return {
        "dry_run": dry_run,
        "platforms_checked_count": 0,
        "followed_candidates_count": len(followed),
        "changes": [],
    }
