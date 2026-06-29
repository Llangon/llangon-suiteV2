from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import AIConfig


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    reason: str = ""
    retry_at: str = ""


def _parse_iso(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None


def check_rate_limit(conn: sqlite3.Connection, config: AIConfig, *, now: datetime | None = None) -> RateLimitResult:
    current = now or datetime.now().replace(microsecond=0)
    last_429 = conn.execute(
        """
        SELECT created_at FROM ai_usage_log
        WHERE provider = 'gemini' AND error_code = 'RESOURCE_EXHAUSTED'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    if last_429:
        created = _parse_iso(last_429["created_at"])
        if created:
            retry = created + timedelta(minutes=config.cooldown_on_429_minutes)
            if retry > current:
                return RateLimitResult(False, "Cooldown activo por limite 429 de Gemini.", retry.isoformat())

    minute_since = (current - timedelta(minutes=1)).isoformat()
    day_since = (current - timedelta(days=1)).isoformat()
    minute_count = conn.execute(
        "SELECT COUNT(*) FROM ai_usage_log WHERE provider = 'gemini' AND created_at >= ?",
        (minute_since,),
    ).fetchone()[0]
    if int(minute_count or 0) >= config.max_requests_per_minute:
        return RateLimitResult(False, "Limite interno por minuto alcanzado.", (current + timedelta(minutes=1)).isoformat())

    day_count = conn.execute(
        "SELECT COUNT(*) FROM ai_usage_log WHERE provider = 'gemini' AND created_at >= ?",
        (day_since,),
    ).fetchone()[0]
    if int(day_count or 0) >= config.max_requests_per_day:
        return RateLimitResult(False, "Limite interno diario alcanzado.", (current + timedelta(days=1)).isoformat())
    return RateLimitResult(True)

