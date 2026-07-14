from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import AIConfig
from .encoding_utils import safe_json_dump, safe_read_text_utf8, safe_write_text_utf8
from .gemini_provider import AIProviderError, ProviderResult
from .workspace import prepare_ai_workspace


RunCallable = Callable[..., subprocess.CompletedProcess[str]]


def build_codex_command(config: AIConfig, *, executable: str | None = None, output_file: str = "codex-response.json") -> list[str]:
    command = [
        executable or config.codex_executable,
        "exec",
        "--ignore-user-config",
        "--sandbox",
        config.codex_sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--output-last-message",
        output_file,
    ]
    if config.codex_model.lower() != "auto":
        command.extend(["--model", config.codex_model])
    command.append("Lee prompt.md y devuelve únicamente el JSON final solicitado.")
    return command


def _output_preview(value: str, *, limit: int = 3000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"[inicio omitido; se muestran los últimos {limit} caracteres]\n{text[-limit:]}"


def _codex_process_error(stderr: str) -> tuple[str, str]:
    lowered = str(stderr or "").lower()
    if "requires a newer version of codex" in lowered or "please upgrade to the latest app or cli" in lowered:
        return (
            "CODEX_UPDATE_REQUIRED",
            "La versión instalada de Codex no es compatible con el modelo configurado.",
        )
    return "CODEX_ERROR", "Codex Local terminó con error."


class CodexLocalProvider:
    def __init__(self, config: AIConfig, *, job_id: int, runner: RunCallable | None = None) -> None:
        self.config = config
        self.job_id = job_id
        self.runner = runner or subprocess.run

    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        if not self.config.codex_local_enabled:
            raise AIProviderError("Codex Local no está activado.", code="CODEX_DISABLED")
        executable = shutil.which(self.config.codex_executable)
        if not executable:
            raise AIProviderError("No se encuentra el ejecutable de Codex.", code="CODEX_NOT_FOUND")

        workspace = prepare_ai_workspace(job_id=self.job_id, licitacion=licitacion, selected_documents=documents)
        job_root = Path(str(workspace["job_root"]))
        response_path = job_root / "codex-response.json"
        command = build_codex_command(self.config, executable=executable, output_file=response_path.name)
        try:
            completed = self.runner(
                command,
                cwd=str(job_root),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.codex_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise AIProviderError(
                "Codex Local superó el tiempo configurado.",
                code="CODEX_TIMEOUT",
                diagnostics={"timeout_seconds": self.config.codex_timeout_seconds, **workspace},
            ) from exc
        except OSError as exc:
            raise AIProviderError(
                "No se pudo iniciar Codex Local.",
                code="CODEX_LAUNCH_ERROR",
                diagnostics={"os_error": type(exc).__name__, "os_error_message": str(exc), **workspace},
            ) from exc

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        safe_write_text_utf8(job_root / "logs" / "stdout.log", stdout)
        safe_write_text_utf8(job_root / "logs" / "stderr.log", stderr)
        if completed.returncode != 0:
            error_code, error_message = _codex_process_error(stderr)
            raise AIProviderError(
                error_message,
                code=error_code,
                diagnostics={
                    "returncode": completed.returncode,
                    "stderr_preview": _output_preview(stderr),
                    "stdout_preview": _output_preview(stdout),
                    **workspace,
                },
            )

        response_text = safe_read_text_utf8(response_path) if response_path.is_file() else stdout
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                "Codex Local no devolvió JSON válido.",
                code="INVALID_JSON",
                diagnostics={
                    "response_source": response_path.name if response_path.is_file() else "stdout",
                    "stdout_preview": _output_preview(response_text),
                    "stderr_preview": _output_preview(stderr),
                    **workspace,
                },
            ) from exc
        if not isinstance(payload, dict):
            raise AIProviderError(
                "Codex Local no devolvió un objeto JSON.",
                code="INVALID_JSON",
                diagnostics={"stdout_preview": _output_preview(response_text), **workspace},
            )
        safe_json_dump(job_root / "result.json", payload)
        usage: dict[str, Any] = {
            "provider": "codex_local",
            "workspace": workspace,
            "codex_command": [command[0], command[1], "--sandbox", config_sandbox_safe(self.config.codex_sandbox)],
            "codex_model_selection": "automatic" if self.config.codex_model.lower() == "auto" else "explicit",
            "codex_model_requested": self.config.codex_model,
        }
        return ProviderResult(summary=payload, raw_usage=usage)


def config_sandbox_safe(value: str) -> str:
    return value if value in {"read-only", "workspace-write"} else "custom"
