from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from ..operational_settings import effective_bool, effective_int, effective_setting, effective_text
except ImportError:
    from operational_settings import effective_bool, effective_int, effective_setting, effective_text


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
    raw = os.environ.get(name)
    if raw is not None and not raw.strip():
        return "disabled" if "disabled" in choices else default
    value = (raw if raw is not None else default).strip().lower()
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
    codex_model: str = "auto"
    codex_max_files: int = 8
    codex_max_file_mb: int = 45

    @property
    def active_provider(self) -> str:
        return self.analysis_provider if self.analysis_provider in {"gemini", "codex_local", "disabled"} else "disabled"

    @property
    def provider_enabled(self) -> bool:
        if self.active_provider == "gemini":
            return self.enabled
        if self.active_provider == "codex_local":
            return self.codex_local_enabled
        return False

    @property
    def configured(self) -> bool:
        if self.active_provider == "codex_local":
            return True
        if self.active_provider == "gemini":
            return bool(self.api_key)
        return False

    @property
    def provider_status_label(self) -> str:
        if self.active_provider == "disabled":
            return "IA desactivada"
        if self.active_provider == "codex_local":
            return "Codex Local activo" if self.codex_local_enabled else "Codex Local desactivado"
        if not self.enabled:
            return "Gemini desactivado"
        if not self.configured:
            return "Gemini no configurado"
        return "Gemini activo"

    def public_status(self) -> dict[str, object]:
        return {
            "enabled": self.provider_enabled,
            "configured": self.configured,
            "active_provider": self.active_provider,
            "provider_enabled": self.provider_enabled,
            "provider_configured": self.configured,
            "provider_status_label": self.provider_status_label,
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
            "codex_model": self.codex_model,
            "codex_model_label": "Automático (Codex CLI)" if self.codex_model == "auto" else self.codex_model,
        }


def get_ai_config() -> AIConfig:
    provider_info = effective_setting("ai_analysis_provider")
    provider = (provider_info["value"] or "gemini").strip().lower()
    if provider_info["source"] != "settings" and "AI_ANALYSIS_PROVIDER" in os.environ and not os.environ.get("AI_ANALYSIS_PROVIDER", "").strip():
        provider = "disabled"
    if provider not in {"gemini", "codex_local", "disabled"}:
        provider = "gemini"
    input_mode = (effective_text("gemini_input_mode") or "text").strip().lower()
    if input_mode not in {"text", "pdf_inline", "auto"}:
        input_mode = "text"
    return AIConfig(
        analysis_provider=provider,
        enabled=effective_bool("gemini_enabled"),
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        model=effective_text("gemini_model") or "gemini-3.5-flash",
        max_requests_per_minute=effective_int("gemini_max_requests_per_minute", 2, minimum=1),
        max_requests_per_day=effective_int("gemini_max_requests_per_day", 20, minimum=1),
        cooldown_on_429_minutes=max(1, _int_env("GEMINI_COOLDOWN_ON_429_MINUTES", 15)),
        max_documents_per_analysis=effective_int("gemini_max_documents_per_analysis", 4, minimum=1),
        max_file_mb=effective_int("gemini_max_file_mb", 45, minimum=1),
        timeout_seconds=effective_int("gemini_timeout_seconds", 120, minimum=1),
        input_mode=input_mode,
        max_extracted_chars=max(1000, _int_env("GEMINI_MAX_EXTRACTED_CHARS", 180000)),
        max_chars_per_document=max(1000, _int_env("GEMINI_MAX_CHARS_PER_DOCUMENT", 90000)),
        pdf_inline_fallback=_bool_env("GEMINI_PDF_INLINE_FALLBACK", False),
        min_extracted_chars=max(1, _int_env("GEMINI_MIN_EXTRACTED_CHARS", 1000)),
        codex_local_enabled=_bool_env("CODEX_LOCAL_ENABLED", False),
        codex_executable=os.environ.get("CODEX_EXECUTABLE", "codex").strip() or "codex",
        codex_timeout_seconds=max(1, _int_env("CODEX_TIMEOUT_SECONDS", 600)),
        codex_work_root=os.environ.get("CODEX_WORK_ROOT", "runtime/ai_work/jobs").strip() or "runtime/ai_work/jobs",
        codex_sandbox=os.environ.get("CODEX_SANDBOX", "read-only").strip() or "read-only",
        codex_model=os.environ.get("CODEX_MODEL", "auto").strip() or "auto",
        codex_max_files=max(1, _int_env("CODEX_MAX_FILES", 8)),
        codex_max_file_mb=max(1, _int_env("CODEX_MAX_FILE_MB", 45)),
    )
