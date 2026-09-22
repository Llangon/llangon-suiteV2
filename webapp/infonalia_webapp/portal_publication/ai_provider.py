from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..ai.codex_local_provider import _codex_process_error, _output_preview, config_sandbox_safe
from ..ai.config import AIConfig
from ..ai.gemini_provider import (
    AIProviderError,
    _http_options,
    _is_schema_config_error,
    _json_generation_config,
    _usage_to_dict,
    classify_gemini_exception,
    parse_gemini_response,
)
from .ai_prompt import PORTAL_AI_PROMPT, build_portal_ai_context


@dataclass(frozen=True)
class PortalProviderResult:
    payload: dict[str, Any]
    usage: dict[str, Any]


_SECRET_RE = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|password)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _safe_error_detail(value: object, *, limit: int = 1400) -> str:
    detail = _SECRET_RE.sub(lambda match: f"{match.group(1)}=[oculto]", str(value or ""))
    detail = _BEARER_RE.sub("Bearer [oculto]", detail)
    detail = re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", "", detail)
    detail = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", detail).strip()
    return f"[inicio omitido]\n{detail[-limit:]}" if len(detail) > limit else detail


def _portal_codex_process_error(stderr: str) -> tuple[str, str]:
    base_code, base_message = _codex_process_error(stderr)
    if base_code != "CODEX_ERROR":
        return base_code, base_message
    lowered = str(stderr or "").casefold()
    if any(marker in lowered for marker in ("401", "unauthorized", "not logged in", "authentication", "refresh token")):
        return "CODEX_AUTH_ERROR", "La sesión de Codex ha caducado o no está autorizada."
    if any(marker in lowered for marker in ("429", "rate limit", "too many requests", "quota", "usage limit")):
        return "CODEX_RATE_LIMIT", "Codex ha aplicado un límite temporal de uso."
    if any(marker in lowered for marker in ("context window", "context length", "too many tokens", "request too large", "payload too large")):
        return "CODEX_REQUEST_TOO_LARGE", "La ficha supera el tamaño admitido por Codex en una sola generación."
    if "image" in lowered and any(marker in lowered for marker in ("invalid", "unsupported", "too many", "failed", "error")):
        return "CODEX_IMAGE_ERROR", "Codex no pudo procesar alguna de las páginas visuales de la ficha."
    if "model" in lowered and any(marker in lowered for marker in ("not found", "unavailable", "unsupported")):
        return "CODEX_MODEL_ERROR", "El modelo configurado no está disponible para esta ejecución."
    if any(marker in lowered for marker in ("failed to connect", "connection", "network", "dns", "tls", "certificate")):
        return "CODEX_CONNECTION_ERROR", "Codex no pudo completar la conexión con el servicio."
    if any(marker in lowered for marker in ("permission denied", "access is denied", "acceso denegado", "read-only")):
        return "CODEX_PERMISSION_ERROR", "El entorno de seguridad impidió una operación necesaria de Codex."
    return base_code, base_message


def portal_provider_error_payload(error: AIProviderError) -> dict[str, object]:
    diagnostics = error.diagnostics or {}
    detail = _safe_error_detail(
        diagnostics.get("stderr_preview")
        or diagnostics.get("os_error_message")
        or diagnostics.get("response_preview")
        or diagnostics.get("stdout_preview")
    )
    return {
        "error": str(error),
        "error_code": error.code,
        "error_detail": detail,
    }


class PortalProviderProtocol(Protocol):
    name: str
    model: str

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        ...


class PortalGeminiProvider:
    name = "gemini"

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.model = config.model

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        if not self.config.enabled:
            raise AIProviderError("Gemini está desactivado.", code="GEMINI_DISABLED")
        if not self.config.api_key:
            raise AIProviderError("Gemini no está configurado.", code="GEMINI_NOT_CONFIGURED")
        try:
            from google import genai
            from google.genai import types
        except Exception as exc:
            raise AIProviderError("Falta instalar google-genai.", code="SDK_NOT_INSTALLED") from exc
        data = ficha_path.read_bytes()
        if not data:
            raise AIProviderError("Ficha.pdf está vacía.", code="DOCUMENT_READ_ERROR")
        if len(data) > self.config.max_file_mb * 1024 * 1024:
            raise AIProviderError("Ficha.pdf supera el límite configurado.", code="DOCUMENT_TOO_LARGE")
        started = time.perf_counter()
        diagnostics: dict[str, object] = {
            "provider": self.name,
            "model": self.model,
            "input_mode_used": "pdf_inline_with_page_text",
            "sent_documents_count": 1,
            "total_pdf_bytes_sent": len(data),
        }
        try:
            client = genai.Client(
                api_key=self.config.api_key,
                http_options=_http_options(types, self.config.timeout_seconds),
            )
            contents = [
                PORTAL_AI_PROMPT,
                build_portal_ai_context(base_model),
                types.Part.from_bytes(data=data, mime_type="application/pdf"),
            ]
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=True),
                )
            except Exception as exc:
                if not _is_schema_config_error(exc):
                    raise
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=False),
                )
        except AIProviderError:
            raise
        except Exception as exc:
            error = classify_gemini_exception(exc, secrets=(self.config.api_key,))
            error.diagnostics.update(diagnostics)
            raise error from exc
        payload, parse_diagnostics = parse_gemini_response(response)
        diagnostics["duration_seconds"] = round(time.perf_counter() - started, 3)
        diagnostics["parse_diagnostics"] = parse_diagnostics
        usage = _usage_to_dict(getattr(response, "usage_metadata", None))
        usage.update(diagnostics)
        return PortalProviderResult(payload=payload, usage=usage)


def _find_pdftoppm() -> str | None:
    direct = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
    if direct:
        return direct
    bundled = Path.home() / ".cache" / "codex-runtimes"
    if bundled.is_dir():
        matches = sorted(bundled.glob("*/dependencies/native/poppler/Library/bin/pdftoppm.exe"), reverse=True)
        if matches:
            return str(matches[0])
    return None


def _render_pdf_pages(ficha_path: Path, output_dir: Path) -> list[Path]:
    executable = _find_pdftoppm()
    if not executable:
        raise AIProviderError(
            "No se encuentra el componente para convertir Ficha.pdf en imágenes.",
            code="PDF_RENDERER_NOT_FOUND",
        )
    prefix = output_dir / "pagina"
    try:
        completed = subprocess.run(
            [executable, "-png", "-r", "130", str(ficha_path), str(prefix)],
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AIProviderError(
            "No se pudieron preparar las imágenes de Ficha.pdf.",
            code="PDF_RENDER_ERROR",
            diagnostics={"error": type(exc).__name__},
        ) from exc
    if completed.returncode != 0:
        raise AIProviderError(
            "No se pudieron preparar las imágenes de Ficha.pdf.",
            code="PDF_RENDER_ERROR",
            diagnostics={"stderr_preview": _output_preview(completed.stderr)},
        )
    pages = list(output_dir.glob("pagina-*.png"))
    pages.sort(key=lambda path: int((re.search(r"(\d+)$", path.stem) or ["0", "0"])[1]))
    if not pages:
        raise AIProviderError("Ficha.pdf no produjo páginas visuales.", code="PDF_RENDER_ERROR")
    return pages


def build_portal_codex_command(
    config: AIConfig,
    *,
    executable: str,
    images: list[Path],
    output_file: str = "codex-response.json",
) -> list[str]:
    command = [
        executable,
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
    # El argumento posicional debe ir antes de --image porque esta opción es
    # variádica en Codex CLI y, de otro modo, consume también el prompt.
    command.append(
        "Lee prompt.md, examina visualmente todas las imágenes adjuntas en su orden de página y devuelve únicamente el JSON final solicitado."
    )
    for image_path in images:
        command.extend(["--image", str(image_path)])
    return command


class PortalCodexLocalProvider:
    name = "codex_local"

    def __init__(self, config: AIConfig, *, runner: Any | None = None, page_renderer: Any | None = None) -> None:
        self.config = config
        self.model = config.codex_model
        self.runner = runner or subprocess.run
        self.page_renderer = page_renderer or _render_pdf_pages

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        if not self.config.codex_local_enabled:
            raise AIProviderError("Codex Local no está activado.", code="CODEX_DISABLED")
        executable = shutil.which(self.config.codex_executable)
        if not executable:
            raise AIProviderError("No se encuentra el ejecutable de Codex.", code="CODEX_NOT_FOUND")
        with tempfile.TemporaryDirectory(prefix="llangon-portal-") as temp_name:
            workspace = Path(temp_name)
            images_dir = workspace / "paginas"
            images_dir.mkdir()
            images = self.page_renderer(ficha_path, images_dir)
            expected_pages = int(dict(base_model.get("source") or {}).get("page_count") or 0)
            if len(images) != expected_pages:
                raise AIProviderError(
                    "No se han podido preparar visualmente todas las páginas de Ficha.pdf.",
                    code="PDF_RENDER_INCOMPLETE",
                    diagnostics={"expected_pages": expected_pages, "rendered_pages": len(images)},
                )
            prompt = "\n\n".join(
                [
                    PORTAL_AI_PROMPT,
                    "Las imágenes adjuntas pagina-1, pagina-2, etc. corresponden exactamente a las páginas del PDF. Debes inspeccionar cada una antes de marcar visualReviewed=true.",
                    build_portal_ai_context(base_model),
                ]
            )
            (workspace / "prompt.md").write_text(prompt, encoding="utf-8")
            response_path = workspace / "codex-response.json"
            command = build_portal_codex_command(
                self.config,
                executable=executable,
                images=images,
                output_file=response_path.name,
            )
            try:
                completed = self.runner(
                    command,
                    cwd=str(workspace),
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
                    diagnostics={"timeout_seconds": self.config.codex_timeout_seconds},
                ) from exc
            except OSError as exc:
                raise AIProviderError(
                    "No se pudo iniciar Codex Local.",
                    code="CODEX_LAUNCH_ERROR",
                    diagnostics={"os_error": type(exc).__name__, "os_error_message": str(exc)},
                ) from exc
            if completed.returncode != 0:
                error_code, error_message = _portal_codex_process_error(completed.stderr or "")
                raise AIProviderError(
                    error_message,
                    code=error_code,
                    diagnostics={
                        "returncode": completed.returncode,
                        "stderr_preview": _safe_error_detail(_output_preview(completed.stderr)),
                        "stdout_preview": _safe_error_detail(_output_preview(completed.stdout)),
                    },
                )
            response_text = response_path.read_text(encoding="utf-8") if response_path.is_file() else completed.stdout
            try:
                payload = json.loads(response_text)
            except json.JSONDecodeError as exc:
                raise AIProviderError(
                    "Codex Local no devolvió JSON válido.",
                    code="INVALID_JSON",
                    diagnostics={"response_preview": _output_preview(response_text)},
                ) from exc
            if not isinstance(payload, dict):
                raise AIProviderError("Codex Local no devolvió un objeto JSON.", code="INVALID_JSON")
            return PortalProviderResult(
                payload=payload,
                usage={
                    "provider": self.name,
                    "rendered_pages": len(images),
                    "codex_command": [command[0], command[1], "--sandbox", config_sandbox_safe(self.config.codex_sandbox)],
                    "codex_model_selection": "automatic" if self.config.codex_model.lower() == "auto" else "explicit",
                    "codex_model_requested": self.config.codex_model,
                },
            )


def portal_provider_for_config(config: AIConfig) -> PortalProviderProtocol:
    if config.analysis_provider == "gemini":
        return PortalGeminiProvider(config)
    if config.analysis_provider == "codex_local":
        return PortalCodexLocalProvider(config)
    raise AIProviderError("La IA está desactivada.", code="AI_DISABLED")
