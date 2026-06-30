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


def _choice_env(name: str, default: str, choices: set[str]) -> str:
    value = os.environ.get(name, default).strip().lower()
    return value if value in choices else default


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
    analysis_provider: str = "gemini"
    input_mode: str = "text"
    max_extracted_chars: int = 180000
    max_chars_per_document: int = 90000
    pdf_inline_fallback: bool = False
    min_extracted_chars: int = 1000
    codex_local_enabled: bool = False
    codex_executable: str = "codex"
    codex_timeout_seconds: int = 600
    codex_work_root: str = "runtime/ai_work/jobs"
    codex_sandbox: str = "read-only"
    codex_max_files: int = 8
    codex_max_file_mb: int = 45

    @property
    def configured(self) -> bool:
        if self.analysis_provider == "codex_local":
            return True
        return bool(self.api_key)

    def public_status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "analysis_provider": self.analysis_provider,
            "model": self.model,
            "max_documents_per_analysis": self.max_documents_per_analysis,
            "max_file_mb": self.max_file_mb,
            "input_mode": self.input_mode,
            "max_extracted_chars": self.max_extracted_chars,
            "max_chars_per_document": self.max_chars_per_document,
            "pdf_inline_fallback": self.pdf_inline_fallback,
            "min_extracted_chars": self.min_extracted_chars,
            "codex_local_enabled": self.codex_local_enabled,
            "codex_sandbox": self.codex_sandbox,
        }


def get_ai_config() -> AIConfig:
    return AIConfig(
        analysis_provider=_choice_env("AI_ANALYSIS_PROVIDER", "gemini", {"gemini", "codex_local", "disabled"}),
        enabled=_bool_env("GEMINI_ENABLED", False),
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash",
        max_requests_per_minute=max(1, _int_env("GEMINI_MAX_REQUESTS_PER_MINUTE", 2)),
        max_requests_per_day=max(1, _int_env("GEMINI_MAX_REQUESTS_PER_DAY", 20)),
        cooldown_on_429_minutes=max(1, _int_env("GEMINI_COOLDOWN_ON_429_MINUTES", 15)),
        max_documents_per_analysis=max(1, _int_env("GEMINI_MAX_DOCUMENTS_PER_ANALYSIS", 4)),
        max_file_mb=max(1, _int_env("GEMINI_MAX_FILE_MB", 45)),
        timeout_seconds=max(1, _int_env("GEMINI_TIMEOUT_SECONDS", 120)),
        input_mode=_choice_env("GEMINI_INPUT_MODE", "text", {"text", "pdf_inline", "auto"}),
        max_extracted_chars=max(1000, _int_env("GEMINI_MAX_EXTRACTED_CHARS", 180000)),
        max_chars_per_document=max(1000, _int_env("GEMINI_MAX_CHARS_PER_DOCUMENT", 90000)),
        pdf_inline_fallback=_bool_env("GEMINI_PDF_INLINE_FALLBACK", False),
        min_extracted_chars=max(1, _int_env("GEMINI_MIN_EXTRACTED_CHARS", 1000)),
        codex_local_enabled=_bool_env("CODEX_LOCAL_ENABLED", False),
        codex_executable=os.environ.get("CODEX_EXECUTABLE", "codex").strip() or "codex",
        codex_timeout_seconds=max(1, _int_env("CODEX_TIMEOUT_SECONDS", 600)),
        codex_work_root=os.environ.get("CODEX_WORK_ROOT", "runtime/ai_work/jobs").strip() or "runtime/ai_work/jobs",
        codex_sandbox=os.environ.get("CODEX_SANDBOX", "read-only").strip() or "read-only",
        codex_max_files=max(1, _int_env("CODEX_MAX_FILES", 8)),
        codex_max_file_mb=max(1, _int_env("CODEX_MAX_FILE_MB", 45)),
    )
