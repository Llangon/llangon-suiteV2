from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AIConfig
from .pdf_text_extractor import extract_pdf_text
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
LOGGER = logging.getLogger(__name__)


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


def _redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


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


def classify_gemini_exception(exc: Exception, *, secrets: tuple[str, ...] = ()) -> AIProviderError:
    text = str(exc)
    safe_text = _redact(text, secrets)
    exc_type = type(exc).__name__
    upper = text.upper()
    upper_type = exc_type.upper()
    diagnostics = {
        "provider_exception_type": exc_type,
        "provider_error_preview": _preview(safe_text),
    }
    if "429" in upper or "RESOURCE_EXHAUSTED" in upper:
        return AIProviderError("Gemini ha devuelto limite 429.", code="RESOURCE_EXHAUSTED", diagnostics=diagnostics)
    if "503" in upper or "UNAVAILABLE" in upper:
        return AIProviderError(
            "Gemini saturado temporalmente. Reintentar más tarde.",
            code="GEMINI_UNAVAILABLE",
            diagnostics=diagnostics,
        )
    if "504" in upper or "DEADLINE_EXCEEDED" in upper:
        return AIProviderError(
            "Gemini agotó el plazo de respuesta.",
            code="GEMINI_DEADLINE_EXCEEDED",
            diagnostics=diagnostics,
        )
    if "401" in upper or "403" in upper or "UNAUTHENTICATED" in upper or "PERMISSION_DENIED" in upper:
        return AIProviderError("Gemini no ha autorizado la petición. Revisa la configuración.", code="AUTH_ERROR", diagnostics=diagnostics)
    if "404" in upper or "MODEL NOT FOUND" in upper or "NOT_FOUND" in upper:
        return AIProviderError("El modelo Gemini configurado no existe o no está disponible.", code="MODEL_ERROR", diagnostics=diagnostics)
    if "TIMEOUT" in upper or "TIMED OUT" in upper or "TIMEOUT" in upper_type:
        return AIProviderError(
            "Gemini no respondió dentro del tiempo configurado.",
            code="GEMINI_TIMEOUT",
            diagnostics=diagnostics,
        )
    if "CONNECTERROR" in upper_type or "CONNECTION" in upper or "NETWORK" in upper:
        return AIProviderError("Error de conexión consultando Gemini.", code="NETWORK_ERROR", diagnostics=diagnostics)
    return AIProviderError("Error consultando Gemini.", code="PROVIDER_ERROR", diagnostics=diagnostics)


def _json_generation_config(types: Any, *, with_schema: bool) -> Any:
    kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "temperature": 0.1,
    }
    if with_schema:
        kwargs["response_schema"] = {"type": "object"}
    return types.GenerateContentConfig(**kwargs)


def _http_options(types: Any, timeout_seconds: int) -> Any:
    # google-genai define HttpOptions.timeout en milisegundos y lo convierte internamente a segundos para httpx.
    return types.HttpOptions(timeout=max(1, int(timeout_seconds)) * 1000)


def _context_payload(licitacion: dict[str, object], documents: list[dict[str, object]]) -> dict[str, object]:
    return {
        "licitacion": {
            "id": licitacion.get("id"),
            "expediente": licitacion.get("expediente"),
            "objeto": licitacion.get("objeto"),
            "organismo": licitacion.get("organismo"),
            "fecha_limite": licitacion.get("fecha_limite"),
            "hora_limite": licitacion.get("hora_limite"),
            "plataforma": licitacion.get("plataforma"),
            "presupuesto": licitacion.get("presupuesto"),
            "enlace_perfil": licitacion.get("enlace_perfil"),
        },
        "documentos": [
            {"name": doc.get("name"), "relative_path": doc.get("relative_path"), "reason": doc.get("reason")}
            for doc in documents
        ],
    }


def build_gemini_contents(
    types: Any,
    licitacion: dict[str, object],
    documents: list[dict[str, object]],
    *,
    max_file_mb: int,
) -> tuple[list[object], dict[str, Any]]:
    pdf_parts: list[object] = []
    sent_names: list[str] = []
    total_bytes = 0
    max_bytes = max_file_mb * 1024 * 1024

    for doc in documents:
        path = Path(str(doc.get("path") or ""))
        name = str(doc.get("name") or path.name)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise AIProviderError(
                f"No se pudo leer el PDF seleccionado: {name}",
                code="DOCUMENT_READ_ERROR",
                diagnostics={"document_send_method": "inline_pdf", "document_name": name},
            ) from exc
        if not data:
            raise AIProviderError(
                f"El PDF seleccionado está vacío: {name}",
                code="DOCUMENT_READ_ERROR",
                diagnostics={"document_send_method": "inline_pdf", "document_name": name},
            )
        if len(data) > max_bytes:
            raise AIProviderError(
                f"El PDF seleccionado supera el límite configurado: {name}",
                code="DOCUMENT_TOO_LARGE",
                diagnostics={"document_send_method": "inline_pdf", "document_name": name, "size_bytes": len(data)},
            )
        pdf_parts.append(types.Part.from_bytes(data=data, mime_type="application/pdf"))
        sent_names.append(name)
        total_bytes += len(data)

    diagnostics: dict[str, Any] = {
        "document_send_method": "inline_pdf",
        "input_mode_used": "pdf_inline",
        "sent_documents_count": len(pdf_parts),
        "sent_documents_names": sent_names,
        "total_pdf_bytes_sent": total_bytes,
    }
    contents: list[object] = [
        GEMINI_ANALYSIS_PROMPT,
        "Contexto interno de la licitacion:\n" + json.dumps(_context_payload(licitacion, documents), ensure_ascii=False),
        *pdf_parts,
    ]
    return contents, diagnostics


def build_text_gemini_contents(
    licitacion: dict[str, object],
    documents: list[dict[str, object]],
    *,
    config: AIConfig,
    input_mode_requested: str | None = None,
) -> tuple[list[object], dict[str, Any]]:
    base_diagnostics: dict[str, Any] = {
        "document_send_method": "text_extraction",
        "input_mode_requested": input_mode_requested or config.input_mode,
        "input_mode_used": "text",
        "sent_documents_count": 0,
        "sent_documents_names": [],
        "total_pdf_bytes_sent": 0,
        "selected_documents_names": [
            str(doc.get("name") or doc.get("relative_path") or Path(str(doc.get("path") or "")).name)
            for doc in documents
        ],
    }
    try:
        extraction = extract_pdf_text(
            documents,
            max_total_chars=config.max_extracted_chars,
            max_chars_per_document=config.max_chars_per_document,
        )
    except RuntimeError as exc:
        raise AIProviderError(
            str(exc),
            code="PDF_TEXT_EXTRACTOR_NOT_AVAILABLE",
            diagnostics={**base_diagnostics, "extraction_warnings": [str(exc)]},
        ) from exc
    diagnostics: dict[str, Any] = {
        **base_diagnostics,
        **extraction.diagnostics,
    }
    if extraction.extracted_chars_total < config.min_extracted_chars:
        raise AIProviderError(
            "No se pudo extraer texto suficiente de los PDFs seleccionados.",
            code="NO_EXTRACTED_TEXT",
            diagnostics=diagnostics,
        )

    contents: list[object] = [
        GEMINI_ANALYSIS_PROMPT,
        "Contexto interno de la licitacion:\n" + json.dumps(_context_payload(licitacion, documents), ensure_ascii=False),
        "Texto extraido localmente de los PDFs seleccionados:\n\n" + extraction.text,
    ]
    return contents, diagnostics


def build_gemini_contents_for_mode(
    types: Any,
    licitacion: dict[str, object],
    documents: list[dict[str, object]],
    *,
    config: AIConfig,
) -> tuple[list[object], dict[str, Any]]:
    mode = config.input_mode
    if mode == "text":
        return build_text_gemini_contents(licitacion, documents, config=config)
    if mode == "pdf_inline":
        contents, diagnostics = build_gemini_contents(
            types,
            licitacion,
            documents,
            max_file_mb=config.max_file_mb,
        )
        diagnostics["input_mode_requested"] = mode
        return contents, diagnostics

    try:
        return build_text_gemini_contents(licitacion, documents, config=config, input_mode_requested="auto")
    except AIProviderError as exc:
        if exc.code != "NO_EXTRACTED_TEXT" or not config.pdf_inline_fallback:
            raise
        text_diagnostics = dict(exc.diagnostics)
        contents, diagnostics = build_gemini_contents(
            types,
            licitacion,
            documents,
            max_file_mb=config.max_file_mb,
        )
        diagnostics.update(
            {
                "input_mode_requested": "auto",
                "input_mode_used": "pdf_inline",
                "input_mode_fallback_reason": "NO_EXTRACTED_TEXT",
                "text_extraction_diagnostics": text_diagnostics,
            }
        )
        return contents, diagnostics


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

        send_diagnostics: dict[str, Any] = {
            "model": self.config.model,
            "timeout_seconds": self.config.timeout_seconds,
            "timeout_milliseconds": self.config.timeout_seconds * 1000,
        }
        started = time.perf_counter()
        try:
            client = genai.Client(api_key=self.config.api_key, http_options=_http_options(types, self.config.timeout_seconds))
            contents, send_diagnostics = build_gemini_contents_for_mode(
                types,
                licitacion,
                documents,
                config=self.config,
            )
            send_diagnostics["model"] = self.config.model
            send_diagnostics["timeout_seconds"] = self.config.timeout_seconds
            send_diagnostics["timeout_milliseconds"] = self.config.timeout_seconds * 1000
            LOGGER.info(
                "Inicio llamada Gemini model=%s mode=%s pdfs=%s bytes=%s extracted_chars=%s timeout=%ss",
                self.config.model,
                send_diagnostics.get("input_mode_used", self.config.input_mode),
                send_diagnostics.get("sent_documents_count", 0),
                send_diagnostics.get("total_pdf_bytes_sent", 0),
                send_diagnostics.get("extracted_chars_total", 0),
                self.config.timeout_seconds,
            )
            try:
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=True),
                )
            except Exception as exc:
                if not _is_schema_config_error(exc):
                    raise
                LOGGER.info("Gemini response_schema no aceptado; reintentando solo con response_mime_type.")
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=_json_generation_config(types, with_schema=False),
                )
        except AIProviderError as exc:
            exc.diagnostics.setdefault("model", self.config.model)
            exc.diagnostics.setdefault("timeout_seconds", self.config.timeout_seconds)
            exc.diagnostics.setdefault("timeout_milliseconds", self.config.timeout_seconds * 1000)
            exc.diagnostics.setdefault("duration_seconds", round(time.perf_counter() - started, 3))
            raise
        except Exception as exc:
            error = classify_gemini_exception(exc, secrets=(self.config.api_key,))
            send_diagnostics["duration_seconds"] = round(time.perf_counter() - started, 3)
            error.diagnostics.update(send_diagnostics)
            LOGGER.warning(
                "Error llamada Gemini code=%s model=%s duration=%ss",
                error.code,
                self.config.model,
                send_diagnostics["duration_seconds"],
            )
            raise error from exc

        payload, parse_diagnostics = parse_gemini_response(response)
        send_diagnostics["duration_seconds"] = round(time.perf_counter() - started, 3)
        parse_diagnostics.update(send_diagnostics)
        raw_usage = _usage_to_dict(getattr(response, "usage_metadata", None))
        raw_usage.update(send_diagnostics)
        raw_usage["parse_diagnostics"] = parse_diagnostics
        LOGGER.info(
            "Fin llamada Gemini model=%s mode=%s duration=%ss text_length=%s extracted_chars=%s",
            self.config.model,
            send_diagnostics.get("input_mode_used", self.config.input_mode),
            send_diagnostics["duration_seconds"],
            parse_diagnostics.get("text_length", 0),
            send_diagnostics.get("extracted_chars_total", 0),
        )
        return ProviderResult(summary=payload, raw_usage=raw_usage)
