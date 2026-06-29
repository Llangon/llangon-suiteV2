from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AIConfig
from .prompts import GEMINI_ANALYSIS_PROMPT


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "PROVIDER_ERROR", diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class ProviderResult:
    summary: dict[str, Any]
    raw_usage: dict[str, Any]


MAX_RESPONSE_PREVIEW = 1500


def _usage_to_dict(value: object) -> dict[str, Any]:
    if not value:
        return {}
    if hasattr(value, "to_json_dict"):
        try:
            return dict(value.to_json_dict())
        except Exception:
            return {}
    if isinstance(value, dict):
        return value
    return {name: getattr(value, name) for name in dir(value) if name.endswith("token_count") and not name.startswith("_")}


def _preview(value: object, limit: int = MAX_RESPONSE_PREVIEW) -> str:
    return str(value or "")[:limit]


def _extract_fenced_json(text: str) -> tuple[str, bool]:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return "", False
    return match.group(1).strip(), True


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _parse_json_candidate(candidate: str) -> tuple[dict[str, Any] | None, str]:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"json_error:{exc.msg}:pos={exc.pos}"
    if isinstance(parsed, dict):
        return parsed, "ok"
    return None, f"root_type:{type(parsed).__name__}"


def parse_gemini_response(response: object) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_text = str(getattr(response, "text", "") or "")
    parsed = getattr(response, "parsed", None)
    fenced, has_fence = _extract_fenced_json(raw_text)
    diagnostics: dict[str, Any] = {
        "response_type": type(response).__name__,
        "parsed_exists": parsed is not None,
        "parsed_type": type(parsed).__name__ if parsed is not None else "",
        "text_length": len(raw_text),
        "raw_response_preview": _preview(raw_text),
        "markdown_fences_detected": has_fence,
        "json_object_extraction_attempted": False,
        "parse_attempts": [],
    }

    attempts = diagnostics["parse_attempts"]
    if isinstance(parsed, dict):
        attempts.append("response.parsed:ok")
        diagnostics["parse_strategy"] = "response.parsed"
        return parsed, diagnostics
    if parsed is not None:
        attempts.append(f"response.parsed:root_type:{type(parsed).__name__}")

    text = raw_text.strip()
    if not text:
        attempts.append("response.text:empty")
        raise AIProviderError(
            "Gemini no devolvio contenido JSON.",
            code="INVALID_JSON",
            diagnostics=diagnostics,
        )

    candidates: list[tuple[str, str]] = [("response.text", text)]
    if fenced:
        candidates.append(("markdown_fence", fenced))
    extracted = _extract_first_json_object(text)
    if extracted:
        diagnostics["json_object_extraction_attempted"] = True
        if extracted not in {text, fenced}:
            candidates.append(("first_json_object", extracted))

    seen: set[str] = set()
    non_dict_root = ""
    for label, candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        parsed_candidate, attempt = _parse_json_candidate(candidate)
        attempts.append(f"{label}:{attempt}")
        if parsed_candidate is not None:
            diagnostics["parse_strategy"] = label
            return parsed_candidate, diagnostics
        if attempt.startswith("root_type:"):
            non_dict_root = attempt
            break

    message = "La respuesta IA no tiene estructura de objeto JSON." if non_dict_root else "Gemini no devolvio JSON valido."
    raise AIProviderError(message, code="INVALID_JSON", diagnostics=diagnostics)


def classify_gemini_exception(exc: Exception) -> AIProviderError:
    text = str(exc)
    upper = text.upper()
    diagnostics = {
        "provider_exception_type": type(exc).__name__,
        "provider_error_preview": _preview(text),
    }
    if "429" in upper or "RESOURCE_EXHAUSTED" in upper:
        return AIProviderError("Gemini ha devuelto limite 429.", code="RESOURCE_EXHAUSTED", diagnostics=diagnostics)
    if "503" in upper or "UNAVAILABLE" in upper:
        return AIProviderError(
            "Gemini saturado temporalmente. Reintentar más tarde.",
            code="GEMINI_UNAVAILABLE",
            diagnostics=diagnostics,
        )
    if "401" in upper or "403" in upper or "UNAUTHENTICATED" in upper or "PERMISSION_DENIED" in upper:
        return AIProviderError("Gemini no ha autorizado la petición. Revisa la configuración.", code="AUTH_ERROR", diagnostics=diagnostics)
    if "404" in upper or "MODEL NOT FOUND" in upper or "NOT_FOUND" in upper:
        return AIProviderError("El modelo Gemini configurado no existe o no está disponible.", code="MODEL_ERROR", diagnostics=diagnostics)
    if "TIMEOUT" in upper or "TIMED OUT" in upper:
        return AIProviderError("Tiempo de espera agotado al consultar Gemini.", code="TIMEOUT", diagnostics=diagnostics)
    return AIProviderError("Error consultando Gemini.", code="PROVIDER_ERROR", diagnostics=diagnostics)


def _json_generation_config(types: Any, *, with_schema: bool) -> Any:
    kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "temperature": 0.1,
    }
    if with_schema:
        kwargs["response_schema"] = {"type": "object"}
    return types.GenerateContentConfig(**kwargs)


def _is_schema_config_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "response_schema" in text or "schema" in text


class GeminiProvider:
    def __init__(self, config: AIConfig) -> None:
        self.config = config

    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        if not self.config.enabled:
            raise AIProviderError("La IA esta desactivada.", code="DISABLED")
        if not self.config.api_key:
            raise AIProviderError("Gemini no esta configurado.", code="NOT_CONFIGURED")
        try:
            from google import genai
            from google.genai import types
        except Exception as exc:
            raise AIProviderError("Falta instalar google-genai.", code="SDK_NOT_INSTALLED") from exc

        try:
            client = genai.Client(api_key=self.config.api_key)
            uploaded_files = [client.files.upload(file=str(Path(str(doc["path"])))) for doc in documents]
            context = {
                "licitacion": {
                    "id": licitacion.get("id"),
                    "expediente": licitacion.get("expediente"),
                    "objeto": licitacion.get("objeto"),
                    "organismo": licitacion.get("organismo"),
                    "fecha_limite": licitacion.get("fecha_limite"),
                    "hora_limite": licitacion.get("hora_limite"),
                    "enlace_perfil": licitacion.get("enlace_perfil"),
                },
                "documentos": [
                    {"name": doc.get("name"), "relative_path": doc.get("relative_path"), "reason": doc.get("reason")}
                    for doc in documents
                ],
            }
            contents = [
                GEMINI_ANALYSIS_PROMPT,
                "Contexto interno de la licitacion:\n" + json.dumps(context, ensure_ascii=False),
                *uploaded_files,
            ]
            try:
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=True),
                )
            except Exception as exc:
                if not _is_schema_config_error(exc):
                    raise
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=False),
                )
        except Exception as exc:
            raise classify_gemini_exception(exc) from exc

        payload, parse_diagnostics = parse_gemini_response(response)
        raw_usage = _usage_to_dict(getattr(response, "usage_metadata", None))
        raw_usage["parse_diagnostics"] = parse_diagnostics
        return ProviderResult(summary=payload, raw_usage=raw_usage)
