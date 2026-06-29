from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    api_key: str
    model: str
    max_requests_per_minute: int
    max_requests_per_day: int
    cooldown_on_429_minutes: int
    max_documents_per_analysis: int
    max_file_mb: int
    timeout_seconds: int

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def public_status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "model": self.model,
            "max_documents_per_analysis": self.max_documents_per_analysis,
            "max_file_mb": self.max_file_mb,
        }


def get_ai_config() -> AIConfig:
    return AIConfig(
        enabled=_bool_env("GEMINI_ENABLED", False),
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash",
        max_requests_per_minute=max(1, _int_env("GEMINI_MAX_REQUESTS_PER_MINUTE", 2)),
        max_requests_per_day=max(1, _int_env("GEMINI_MAX_REQUESTS_PER_DAY", 20)),
        cooldown_on_429_minutes=max(1, _int_env("GEMINI_COOLDOWN_ON_429_MINUTES", 15)),
        max_documents_per_analysis=max(1, _int_env("GEMINI_MAX_DOCUMENTS_PER_ANALYSIS", 4)),
        max_file_mb=max(1, _int_env("GEMINI_MAX_FILE_MB", 45)),
        timeout_seconds=max(1, _int_env("GEMINI_TIMEOUT_SECONDS", 120)),
    )
