from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.ai_preview_helpers import (
    build_preview_payload,
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


def test_build_preview_payload_preserves_current_json_shape() -> None:
    row = {
        "expediente": "EXP-1",
        "objeto": "Servicio de limpieza para Hospital Central. Lote 1: Zona norte. Criterios de adjudicación: precio.",
        "organismo": "Ayuntamiento de Pinto",
        "provincia": "Madrid",
        "tipo": "Servicios",
        "presupuesto": 1234.5,
        "fecha_limite": "2026-06-30",
        "hora_limite": "09:05",
        "plataforma": "",
        "enlace_perfil": "https://contratacion.example/perfil",
    }

    payload = build_preview_payload(
        row,
        licitacion_id=7,
        generated_at="2026-06-12T10:30:00",
        detect_platform=lambda url: f"detectada:{url}",
    )

    assert payload["licitacion_id"] == 7
    assert payload["generated_at"] == "2026-06-12T10:30:00"
    assert payload["generated_at_formatted"] == "12/06/2026 10:30"
    assert payload["cabecera"] == {
        "Expediente": "EXP-1",
        "Objeto": row["objeto"],
        "Organismo": "Ayuntamiento de Pinto",
        "Provincia": "Madrid",
        "Tipo": "Servicios",
        "Presupuesto": "1.234,50 €",
        "Fecha límite": "30/06/2026 09:05",
        "Plataforma": "detectada:https://contratacion.example/perfil",
    }
    assert payload["centros"][:2] == ["Ayuntamiento de Pinto", "Hospital Central"]
    assert payload["criterios_adjudicacion"] == [
        "Servicio de limpieza para Hospital Central. Lote 1: Zona norte. Criterios de adjudicación: precio.",
        "limpieza para Hospital Central. Lote 1: Zona norte. Criterios de adjudicación: precio.",
    ]
    assert payload["resumen"] == "Contrato de servicios promovido por Ayuntamiento de Pinto con presentación hasta 30/06/2026 09:05."
    assert payload["nota"] == "Resumen automático orientativo generado con los datos ya guardados en la ficha."


def test_build_preview_payload_keeps_existing_platform_without_detection() -> None:
    row = {
        "expediente": "EXP-2",
        "objeto": "Servicio",
        "organismo": "",
        "provincia": "",
        "tipo": "",
        "presupuesto": None,
        "fecha_limite": "",
        "hora_limite": "",
        "plataforma": "PLACE",
        "enlace_perfil": "https://contratacion.example/perfil",
    }
    detector_calls = []

    payload = build_preview_payload(
        row,
        licitacion_id=8,
        generated_at="2026-06-12T10:30:00",
        detect_platform=lambda url: detector_calls.append(url) or "OTRA",
    )

    assert payload["cabecera"]["Plataforma"] == "PLACE"
    assert payload["cabecera"]["Presupuesto"] == ""
    assert detector_calls == []


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
