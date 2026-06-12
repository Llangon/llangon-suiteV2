from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.normalization import (
    bool_text,
    clean_text,
    parse_date_value,
    parse_money,
    parse_time_value,
)


def test_normalization_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.normalization", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.normalization")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_clean_text_handles_none_and_strips_text() -> None:
    assert clean_text(None) == ""
    assert clean_text("  texto  ") == "texto"
    assert clean_text(123) == "123"


def test_bool_text_accepts_existing_truthy_values() -> None:
    for value in ("1", "true", "yes", "si", "sí", "on", " ON "):
        assert bool_text(value) is True

    assert bool_text("0") is False
    assert bool_text("") is False


def test_parse_money_preserves_current_spanish_formats() -> None:
    assert parse_money(None) is None
    assert parse_money("") is None
    assert parse_money("1.234,56 EUR") == 1234.56
    assert parse_money("importe 987,65 €") == 987.65
    assert parse_money(42) == 42.0


def test_parse_date_value_preserves_current_formats() -> None:
    assert parse_date_value("") == ""
    assert parse_date_value("2026-06-12") == "2026-06-12"
    assert parse_date_value("12/06/2026") == "2026-06-12"
    assert parse_date_value("12-06-26") == "2026-06-12"
    assert parse_date_value("invalid") == ""


def test_parse_time_value_preserves_current_formats() -> None:
    assert parse_time_value("") == ""
    assert parse_time_value("9:05") == "09:05"
    assert parse_time_value("23:59") == "23:59"
    assert parse_time_value("24:00") == ""
    assert parse_time_value("0.5") == "12:00"
