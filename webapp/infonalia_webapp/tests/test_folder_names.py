from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.folder_names import (
    expediente_folder_text,
    extract_municipio_from_organismo,
    extract_objeto_folder_key,
    folder_text,
    safe_folder_name,
    short_folder_phrase,
)


def test_folder_names_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.folder_names", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.folder_names")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_safe_folder_name_preserves_current_cleanup() -> None:
    assert safe_folder_name(' A/B:*?"<>|  C ') == "AB C"
    assert safe_folder_name("") == "licitacion"
    assert safe_folder_name("x" * 200) == "x" * 140


def test_folder_text_normalizes_accents_symbols_and_ampersand() -> None:
    assert folder_text("Área de compras & servicios") == "AREA DE COMPRAS Y SERVICIOS"
    assert folder_text(None) == ""


def test_expediente_folder_text_preserves_windows_compatible_characters() -> None:
    assert expediente_folder_text("SAS_Z3_2027_PA_011") == "SAS_Z3_2027_PA_011"
    assert expediente_folder_text("Exp. (Niñez)-12.2026 & lote_A") == "EXP. (NINEZ)-12.2026 & LOTE_A"


def test_expediente_folder_text_replaces_only_windows_forbidden_characters() -> None:
    assert expediente_folder_text('EXP/12:2026*?"<>|A') == "EXP 12 2026 A"
    assert expediente_folder_text("EXP-7.") == "EXP-7"


def test_short_folder_phrase_limits_words_after_normalization() -> None:
    assert short_folder_phrase("uno dos tres cuatro", max_words=2) == "UNO DOS"


def test_extract_municipio_from_organismo_handles_pinoso_special_case() -> None:
    assert extract_municipio_from_organismo("Ayuntamiento de Pinoso", "Alicante") == "EL PINOSO"


def test_extract_objeto_folder_key_preserves_preferred_phrases() -> None:
    assert extract_objeto_folder_key("Suministro de carne y derivados para centros") == "CARNE Y DERIVADOS"
    assert extract_objeto_folder_key("Servicio de escuela infantil municipal") == "ESCUELA INFANTIL"
