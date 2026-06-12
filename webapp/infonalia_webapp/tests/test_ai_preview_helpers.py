from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.ai_preview_helpers import (
    extract_centros_from_text,
    extract_keyword_context,
    extract_lotes_from_text,
    preview_payload_to_text,
)


def test_ai_preview_helpers_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.ai_preview_helpers", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.ai_preview_helpers")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_extract_lotes_from_text_preserves_current_limits_and_deduplication() -> None:
    text = "Lote 1: Limpieza norte Lote 2. Limpieza sur Lote 1: Limpieza norte"

    assert extract_lotes_from_text(text) == [
        "Lote 1: Limpieza norte",
        "Lote 2. Limpieza sur",
    ]


def test_extract_keyword_context_preserves_current_snippet_rule() -> None:
    snippets = extract_keyword_context(
        "Inicio. Criterios de adjudicación: precio y calidad. Final.",
        ["precio", "ausente"],
        window=20,
    )

    assert snippets == ["Inicio. Criterios de adjudicación: precio y calidad. Fi"]


def test_extract_centros_from_text_preserves_current_patterns() -> None:
    row = {"organismo": "Servicio Andaluz de Salud", "objeto": "Suministro para Hospital Central"}
    text = "Incluye Residencia Los Olivos y centros dependientes de la provincia."

    assert extract_centros_from_text(row, text) == [
        "Servicio Andaluz de Salud",
        "Hospital Central Incluye Residencia Los Olivos y centros dependientes de la provincia",
        "centros dependientes de la provincia",
    ]


def test_preview_payload_to_text_preserves_current_sections() -> None:
    text = preview_payload_to_text(
        {
            "cabecera": {"Expediente": "EXP-1", "Objeto": "Servicio"},
            "centros": ["Hospital Central"],
            "lotes": [],
            "criterios_adjudicacion": ["Precio"],
            "criterios_ejecucion": [],
            "resumen": "Resumen.",
            "nota": "Nota.",
        }
    )

    assert "Vista preliminar de licitación" in text
    assert "Expediente: EXP-1" in text
    assert "- Hospital Central" in text
    assert "Detalle de lotes e importes:\n- No detectado en la ficha disponible." in text
    assert "Resumen generado:\nResumen." in text
