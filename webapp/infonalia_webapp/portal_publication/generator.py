from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .coverage import audit_coverage
from .pdf_source import PortalPdfError, read_ficha_pdf


class PortalGenerationError(ValueError):
    pass


def _row(row: Mapping[str, object] | object, key: str) -> str:
    try:
        value = row[key]  # type: ignore[index]
    except Exception:
        value = ""
    return str(value or "").strip()


def _first_url(text: str) -> str:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(".,);]") if match else ""


def build_portal_model(
    licitacion: Mapping[str, object] | object,
    ficha: dict[str, object],
    downloads: list[dict[str, object]],
) -> dict[str, object]:
    try:
        source = read_ficha_pdf(Path(str(ficha["path"])))
    except (KeyError, PortalPdfError) as exc:
        raise PortalGenerationError(str(exc)) from exc
    pages = list(source["pages"])
    all_text = "\n".join(str(page.get("text") or "") for page in pages)
    sections: list[dict[str, object]] = []
    for page in pages:
        number = int(page["number"])
        sections.append(
            {
                "id": f"ficha-pagina-{number}",
                "eyebrow": "Ficha de licitación",
                "title": f"Página {number}",
                "sourcePages": [number],
                "blocks": [
                    {
                        "type": "source_page",
                        "page": number,
                        "text": page["text"],
                        "sourcePages": [number],
                        "sourceSha256": page["text_sha256"],
                        "visualFallbackRequired": page["visual_fallback_required"],
                    }
                ],
            }
        )
    coverage = audit_coverage(source, sections)
    return {
        "schema_version": "llangon.portal.v1",
        "generation": {
            "mode": "local_deterministic",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "published": False,
            "external_actions": [],
        },
        "tender": {
            "id": _row(licitacion, "id"),
            "reference": _row(licitacion, "expediente"),
            "title": _row(licitacion, "objeto"),
            "recipient": _row(licitacion, "cliente") or _row(licitacion, "representada"),
            "deadline_date": _row(licitacion, "fecha_limite"),
            "deadline_time": _row(licitacion, "hora_limite"),
            "tender_url": _row(licitacion, "enlace_perfil") or _first_url(all_text),
        },
        "source": source,
        "sections": sections,
        "downloads": [
            {
                "name": item["name"],
                "relative_path": item["relative_path"],
                "extension": item["extension"],
                "size_bytes": item["size_bytes"],
                "size_human": item.get("size_human", ""),
                "is_ficha": bool(item.get("is_ficha")),
            }
            for item in downloads
        ],
        "coverage": coverage,
    }
