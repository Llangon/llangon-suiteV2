from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.licitation_records import licitation_row_to_dict


class FakeRow(dict):
    pass


def test_licitation_records_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.licitation_records", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.licitation_records")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_licitation_row_to_dict_detects_platform_and_normalizes_output_fields() -> None:
    row = FakeRow(
        {
            "id": 7,
            "expediente": "EXP-7",
            "plataforma": " ",
            "enlace_perfil": " https://contratacion.example/perfil ",
            "enlace_infonalia": " https://infonalia.example/item ",
            "ruta_carpeta": " C:\\ReplicaDb\\2026\\EXP-7 ",
        }
    )

    item = licitation_row_to_dict(
        row,
        detect_platform=lambda url: f"plataforma:{url}",
        normalize_url_value=lambda value: f"url:{str(value).strip()}",
        normalize_folder_path=lambda value: f"folder:{str(value).strip()}",
    )

    assert item["id"] == 7
    assert item["expediente"] == "EXP-7"
    assert item["plataforma"] == "plataforma:https://contratacion.example/perfil"
    assert item["enlace_perfil"] == "url:https://contratacion.example/perfil"
    assert item["enlace_infonalia"] == "url:https://infonalia.example/item"
    assert item["ruta_carpeta"] == "folder:C:\\ReplicaDb\\2026\\EXP-7"


def test_licitation_row_to_dict_keeps_existing_platform() -> None:
    row = FakeRow(
        {
            "plataforma": "PLACE",
            "enlace_perfil": "https://example.test/perfil",
            "enlace_infonalia": "",
            "ruta_carpeta": "",
        }
    )
    detector_calls = []

    item = licitation_row_to_dict(
        row,
        detect_platform=lambda url: detector_calls.append(url) or "OTRA",
        normalize_url_value=lambda value: str(value or ""),
        normalize_folder_path=lambda value: str(value or ""),
    )

    assert item["plataforma"] == "PLACE"
    assert detector_calls == []
