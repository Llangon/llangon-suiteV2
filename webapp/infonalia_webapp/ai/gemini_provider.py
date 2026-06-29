from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AIConfig
from .prompts import GEMINI_ANALYSIS_PROMPT


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "PROVIDER_ERROR") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderResult:
    summary: dict[str, Any]
    raw_usage: dict[str, Any]


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
            response = client.models.generate_content(
                model=self.config.model,
                contents=[
                    GEMINI_ANALYSIS_PROMPT,
                    "Contexto interno de la licitacion:\n" + json.dumps(context, ensure_ascii=False),
                    *uploaded_files,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
        except Exception as exc:
            text = str(exc)
            if "429" in text or "RESOURCE_EXHAUSTED" in text:
                raise AIProviderError("Gemini ha devuelto limite 429.", code="RESOURCE_EXHAUSTED") from exc
            if "timeout" in text.lower():
                raise AIProviderError("Tiempo de espera agotado al consultar Gemini.", code="TIMEOUT") from exc
            raise AIProviderError("Error consultando Gemini.", code="PROVIDER_ERROR") from exc

        raw_text = getattr(response, "text", "") or ""
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise AIProviderError("Gemini no devolvio JSON valido.", code="INVALID_JSON") from exc
        return ProviderResult(summary=payload, raw_usage=_usage_to_dict(getattr(response, "usage_metadata", None)))

