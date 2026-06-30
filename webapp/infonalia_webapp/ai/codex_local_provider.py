from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import AIConfig
from .gemini_provider import AIProviderError, ProviderResult
from .workspace import prepare_ai_workspace


RunCallable = Callable[..., subprocess.CompletedProcess[str]]


def build_codex_command(config: AIConfig) -> list[str]:
    return [
        config.codex_executable,
        "exec",
        "--sandbox",
        config.codex_sandbox,
        "--skip-git-repo-check",
        "Lee prompt.md y devuelve únicamente el JSON final solicitado.",
    ]


class CodexLocalProvider:
    def __init__(self, config: AIConfig, *, job_id: int, runner: RunCallable | None = None) -> None:
        self.config = config
        self.job_id = job_id
        self.runner = runner or subprocess.run

    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        if not self.config.codex_local_enabled:
            raise AIProviderError("Codex Local no está activado.", code="CODEX_DISABLED")
        if not shutil.which(self.config.codex_executable):
            raise AIProviderError("No se encuentra el ejecutable de Codex.", code="CODEX_NOT_FOUND")

        workspace = prepare_ai_workspace(job_id=self.job_id, licitacion=licitacion, selected_documents=documents)
        job_root = Path(str(workspace["job_root"]))
        command = build_codex_command(self.config)
        try:
            completed = self.runner(
                command,
                cwd=str(job_root),
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.config.codex_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AIProviderError("Codex Local superó el tiempo configurado.", code="CODEX_TIMEOUT") from exc

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        (job_root / "logs" / "stdout.log").write_text(stdout, encoding="utf-8")
        (job_root / "logs" / "stderr.log").write_text(stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise AIProviderError(
                "Codex Local terminó con error.",
                code="CODEX_ERROR",
                diagnostics={"returncode": completed.returncode, "stderr_preview": stderr[:1500], **workspace},
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                "Codex Local no devolvió JSON válido.",
                code="INVALID_JSON",
                diagnostics={"stdout_preview": stdout[:1500], **workspace},
            ) from exc
        if not isinstance(payload, dict):
            raise AIProviderError(
                "Codex Local no devolvió un objeto JSON.",
                code="INVALID_JSON",
                diagnostics={"stdout_preview": stdout[:1500], **workspace},
            )
        (job_root / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        usage: dict[str, Any] = {
            "provider": "codex_local",
            "workspace": workspace,
            "codex_command": [command[0], command[1], "--sandbox", config_sandbox_safe(self.config.codex_sandbox)],
        }
        return ProviderResult(summary=payload, raw_usage=usage)


def config_sandbox_safe(value: str) -> str:
    return value if value in {"read-only", "workspace-write"} else "custom"
