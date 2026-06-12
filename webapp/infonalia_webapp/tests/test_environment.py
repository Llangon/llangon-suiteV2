from __future__ import annotations

import importlib
import os
import sys

import pytest

from webapp.infonalia_webapp.environment import load_env_file, required_env


def test_environment_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.environment", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.environment")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_load_env_file_preserves_existing_values_and_parses_quotes(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
        # comment
        INFONALIA_EXISTING=from-file
        INFONALIA_NEW='new value'
        INFONALIA_DOUBLE="double value"
        MALFORMED
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("INFONALIA_EXISTING", "already-set")
    monkeypatch.delenv("INFONALIA_NEW", raising=False)
    monkeypatch.delenv("INFONALIA_DOUBLE", raising=False)

    load_env_file(env_path)

    assert os.environ["INFONALIA_EXISTING"] == "already-set"
    assert os.environ["INFONALIA_NEW"] == "new value"
    assert os.environ["INFONALIA_DOUBLE"] == "double value"


def test_load_env_file_expands_environment_variables(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("INFONALIA_EXPANDED=%INFONALIA_BASE%\\data\n", encoding="utf-8")
    monkeypatch.setenv("INFONALIA_BASE", "C:\\Base")
    monkeypatch.delenv("INFONALIA_EXPANDED", raising=False)

    load_env_file(env_path)

    assert os.environ["INFONALIA_EXPANDED"] == "C:\\Base\\data"


def test_required_env_returns_stripped_value_and_rejects_missing(monkeypatch) -> None:
    monkeypatch.setenv("INFONALIA_REQUIRED_TEST", " value ")
    assert required_env("INFONALIA_REQUIRED_TEST") == "value"

    monkeypatch.delenv("INFONALIA_REQUIRED_TEST", raising=False)
    with pytest.raises(RuntimeError, match="Falta la variable obligatoria INFONALIA_REQUIRED_TEST"):
        required_env("INFONALIA_REQUIRED_TEST")
