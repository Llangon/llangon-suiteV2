from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.formatting import format_date_es, format_datetime_es


def test_formatting_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.formatting", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.formatting")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_format_date_es_preserves_current_behavior() -> None:
    assert format_date_es("2026-06-12") == "12/06/2026"
    assert format_date_es("") == "Sin fecha"
    assert format_date_es(None) == "Sin fecha"
    assert format_date_es("sin-fecha") == "sin-fecha"


def test_format_datetime_es_preserves_current_iso_behavior() -> None:
    assert format_datetime_es("") == ""
    assert format_datetime_es("2026-06-12") == "12/06/2026"
    assert format_datetime_es("2026-06-12T09:30:00") == "12/06/2026 09:30"
    assert format_datetime_es("2026-06-12 09:30:00") == "12/06/2026 09:30"
    assert format_datetime_es("2026-06-12T09:30:00Z") == "12/06/2026 09:30"


def test_format_datetime_es_returns_original_text_when_unknown() -> None:
    assert format_datetime_es("sin fecha clara") == "sin fecha clara"
