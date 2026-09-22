from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ..ai.config import AIConfig, get_ai_config
from .ai_audit import apply_ai_enrichment, audit_ai_enrichment
from .ai_provider import PortalProviderProtocol, portal_provider_for_config
from .ai_schema import parse_portal_ai_payload
from .generator import PortalGenerationError, build_portal_model


def build_ai_portal_preview(
    licitacion: Mapping[str, object] | object,
    ficha: dict[str, object],
    downloads: list[dict[str, object]],
    *,
    provider: PortalProviderProtocol | None = None,
    config: AIConfig | None = None,
) -> dict[str, object]:
    base_model = build_portal_model(licitacion, ficha, downloads)
    active_provider = provider or portal_provider_for_config(config or get_ai_config())
    result = active_provider.generate(base_model, Path(str(ficha["path"])))
    try:
        enrichment = parse_portal_ai_payload(result.payload, base_model)
    except (PortalGenerationError, ValueError):
        raise
    except Exception as exc:
        raise PortalGenerationError(
            f"Codex respondió, pero falló la lectura de su estructura ({type(exc).__name__})."
        ) from exc
    try:
        audit = audit_ai_enrichment(base_model, enrichment)
    except Exception as exc:
        raise PortalGenerationError(
            f"Falló la auditoría página a página del resultado ({type(exc).__name__})."
        ) from exc
    try:
        model = apply_ai_enrichment(
            base_model,
            enrichment,
            audit,
            provider=active_provider.name,
            model=active_provider.model,
        )
        model["generation"]["usage"] = json.loads(json.dumps(result.usage, ensure_ascii=False, default=str))
        json.dumps(model, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        raise PortalGenerationError(
            f"La vista se generó, pero no pudo prepararse para el navegador ({type(exc).__name__})."
        ) from exc
    return model
