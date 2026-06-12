from __future__ import annotations

import importlib
import sys
from datetime import datetime

from webapp.infonalia_webapp.msg_parsing import (
    extract_hora_limite_from_text,
    extract_msg_date,
    extract_tipo_contrato,
    extraer_despues_de_dos_puntos,
    extraer_fecha_msg,
)


def test_msg_parsing_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.msg_parsing", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.msg_parsing")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_extraer_despues_de_dos_puntos_preserves_url_angle_bracket_rule() -> None:
    assert extraer_despues_de_dos_puntos("Perfil: <https://example.test/a>") == "https://example.test/a"
    assert extraer_despues_de_dos_puntos("Expediente: 2026/001") == "2026/001"
    assert extraer_despues_de_dos_puntos("Sin separador") == ""


def test_msg_date_helpers_preserve_current_date_parsing() -> None:
    assert extract_msg_date(datetime(2026, 6, 12, 9, 30)) == "2026-06-12"
    assert extract_msg_date("12/06/2026") == "2026-06-12"
    assert extraer_fecha_msg("Plazo presentación: 30/06/2026 09:05") == "2026-06-30"
    assert extraer_fecha_msg("sin fecha") == ""


def test_extract_tipo_contrato_preserves_context_priority() -> None:
    assert extract_tipo_contrato("Tipo de contrato: concesión de servicios para comedor") == "Concesión de servicios"
    assert extract_tipo_contrato("Contrato de obras de reforma") == "Obras"
    assert extract_tipo_contrato("Expediente sin tipo") == ""


def test_extract_hora_limite_from_text_preserves_nearby_date_rule() -> None:
    text = "Otra fecha 29/06/2026 08:00\nPresentación 30/06/2026\nHasta las 9:05 horas"

    assert extract_hora_limite_from_text(text, "2026-06-30") == "09:05"
    assert extract_hora_limite_from_text(text, "2026-07-01") == ""
