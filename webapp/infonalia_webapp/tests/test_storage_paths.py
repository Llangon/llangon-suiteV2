from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from webapp.infonalia_webapp.local_storage import LocalStorageError
from webapp.infonalia_webapp.storage_paths import (
    DOWNLOAD_BAT_FILENAME,
    default_dropbox_folder,
    dropbox_relative_path,
    expected_dropbox_relative_folder,
    folder_descriptor,
    folder_path_for_storage,
    get_nombre_mes,
    is_internal_download_path,
    normalize_relative_folder_path,
    resolve_destination_folder,
    storage_root_for_destination,
    write_http_url,
)


def test_storage_paths_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.storage_paths", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.storage_paths")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_normalize_relative_folder_path_preserves_safe_parts() -> None:
    assert normalize_relative_folder_path("2026/../Madrid//Expediente: 1") == str(Path("2026") / "Madrid" / "Expediente 1")
    assert normalize_relative_folder_path("") == ""


def test_dropbox_relative_path_accepts_relative_and_absolute_under_root(tmp_path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "JUNIO"
    folder.mkdir(parents=True)

    assert dropbox_relative_path("2026/JUNIO", root) == str(Path("2026") / "JUNIO")
    assert dropbox_relative_path(str(folder), root) == str(Path("2026") / "JUNIO")


def test_folder_path_for_storage_keeps_non_dropbox_absolute_path(tmp_path) -> None:
    root = tmp_path / "ReplicaDb"
    external = tmp_path / "externo" / "carpeta"

    assert folder_path_for_storage(str(external), root) == str(external)


def test_default_dropbox_folder_preserves_current_date_shape(tmp_path) -> None:
    row = {
        "expediente": "EXP/2026:001",
        "provincia": "Madrid",
        "organismo": "Ayuntamiento de Pinto",
        "objeto": "Servicio de limpieza del hospital central",
        "fecha_limite": "2026-06-30",
        "hora_limite": "09:05",
    }

    folder = default_dropbox_folder(row, tmp_path)

    assert folder.parts[-3:] == (
        "2026",
        "06 JUNIO",
        "30 JUNIO 0905 MADRID PINTO HOSPITAL CENTRAL EXP 2026 001",
    )
    assert get_nombre_mes(6) == "JUNIO"


def test_expected_dropbox_relative_folder_includes_year_month_and_leaf() -> None:
    row = {
        "expediente": "1718652R",
        "provincia": "Alicante",
        "organismo": "Alcaldia del Ayuntamiento de Pinoso (Alicante)",
        "objeto": "Suministro de alimentos para el comedor de la escuela infantil municipal",
        "fecha_limite": "2026-07-20",
        "hora_limite": "14:00",
    }

    relative = expected_dropbox_relative_folder(row)

    assert relative.parts[:2] == ("2026", "07 JULIO")
    assert relative.name == "20 JULIO 1400 ALICANTE EL PINOSO ESCUELA INFANTIL 1718652R"


def test_default_dropbox_folder_falls_back_to_fecha_infonalia_with_year_month(tmp_path) -> None:
    row = {
        "expediente": "EXP-7",
        "provincia": "Jaen",
        "organismo": "Ayuntamiento de Martos",
        "objeto": "",
        "fecha_limite": "",
        "fecha_infonalia": "2026-07-02",
        "hora_limite": "",
    }

    folder = default_dropbox_folder(row, tmp_path)

    assert folder.parts[-3:-1] == ("2026", "07 JULIO")
    assert folder.name == "02 JULIO JAEN MARTOS EXP-7"


def test_resolve_destination_folder_uses_download_root_without_dropbox(tmp_path) -> None:
    row = {
        "id": 7,
        "expediente": "EXP-7",
        "ruta_carpeta": "",
        "fecha_limite": "2026-06-30",
    }

    destination = resolve_destination_folder(row, download_root=tmp_path, dropbox_root=None)

    assert destination == tmp_path / "2026-06-30 EXP-7"


def test_resolve_destination_folder_rehomes_missing_legacy_month_route_under_year(tmp_path) -> None:
    dropbox_root = tmp_path / "00000 LLANGON"
    dropbox_root.mkdir()
    row = {
        "id": 7,
        "expediente": "EXP-7",
        "ruta_carpeta": r"07 JULIO\20 JULIO 1400 ALICANTE EL PINOSO ESCUELA INFANTIL EXP7",
        "fecha_limite": "2026-07-20",
        "hora_limite": "14:00",
        "provincia": "Alicante",
        "organismo": "Ayuntamiento de Pinoso",
        "objeto": "Suministro de alimentos para la escuela infantil",
    }

    destination = resolve_destination_folder(row, download_root=tmp_path / "descargas", dropbox_root=dropbox_root)

    assert destination == dropbox_root / "2026" / "07 JULIO" / "20 JULIO 1400 ALICANTE EL PINOSO ESCUELA INFANTIL EXP7"
    assert not (dropbox_root / "07 JULIO").exists()


def test_resolve_destination_folder_keeps_existing_legacy_month_route_readable(tmp_path) -> None:
    dropbox_root = tmp_path / "00000 LLANGON"
    legacy_folder = dropbox_root / "07 JULIO" / "carpeta antigua"
    legacy_folder.mkdir(parents=True)
    row = {
        "id": 7,
        "expediente": "EXP-7",
        "ruta_carpeta": r"07 JULIO\carpeta antigua",
        "fecha_limite": "2026-07-20",
        "hora_limite": "14:00",
    }

    destination = resolve_destination_folder(row, download_root=tmp_path / "descargas", dropbox_root=dropbox_root)

    assert destination == legacy_folder


def test_storage_root_for_destination_rejects_outside_path(tmp_path) -> None:
    root = tmp_path / "root"
    inside = root / "folder"
    outside = tmp_path / "outside"

    assert storage_root_for_destination(inside, [root]) == root.resolve()
    with pytest.raises(LocalStorageError):
        storage_root_for_destination(outside, [root])


def test_write_http_url_creates_shortcut_file(tmp_path) -> None:
    launcher = tmp_path / "suite app" / "herramientas_python" / "Descargar_Licitacion.py"
    python = tmp_path / "suite app" / ".venv" / "Scripts" / "python.exe"
    write_http_url(
        tmp_path,
        "https://example.test/perfil",
        launcher_path=launcher,
        python_executable=python,
    )

    assert (tmp_path / "HTTP.url").read_text(encoding="utf-8") == "[InternetShortcut]\nURL=https://example.test/perfil\n"
    bat = (tmp_path / DOWNLOAD_BAT_FILENAME).read_text(encoding="utf-8")
    assert f'set "PYTHON={python.resolve()}"' in bat
    assert f'set "SCRIPT={launcher.resolve()}"' in bat
    assert '"%PYTHON%" "%SCRIPT%"' in bat
    assert 'Infonalia\\Descargar_Licitacion.py' not in bat


def test_write_http_url_migrates_legacy_generated_bat(tmp_path) -> None:
    bat_path = tmp_path / DOWNLOAD_BAT_FILENAME
    bat_path.write_text(
        '@echo off\n:buscar_lanzador\nif exist "%BUSCAR%\\Infonalia\\Descargar_Licitacion.py" echo legacy\n',
        encoding="utf-8",
    )
    launcher = tmp_path / "repo" / "herramientas_python" / "Descargar_Licitacion.py"

    write_http_url(tmp_path, "https://example.test/perfil", launcher_path=launcher)

    bat = bat_path.read_text(encoding="utf-8")
    assert str(launcher.resolve()) in bat
    assert ":buscar_lanzador" not in bat


def test_is_internal_download_path_checks_download_root(tmp_path) -> None:
    root = tmp_path / "descargas"
    inside = root / "expediente"
    outside = tmp_path / "otra"

    assert is_internal_download_path(inside, root) is True
    assert is_internal_download_path(outside, root) is False
    assert folder_descriptor({"provincia": "Madrid", "organismo": "Ayuntamiento de Pinto", "objeto": "Servicio de limpieza"}) == "PINTO LIMPIEZA"
