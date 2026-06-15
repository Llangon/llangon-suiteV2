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
    root = tmp_path / "Dropbox" / "00000 LLANGON"
    folder = root / "2026" / "JUNIO"
    folder.mkdir(parents=True)

    assert dropbox_relative_path("2026/JUNIO", root) == str(Path("2026") / "JUNIO")
    assert dropbox_relative_path(str(folder), root) == str(Path("2026") / "JUNIO")


def test_folder_path_for_storage_keeps_non_dropbox_absolute_path(tmp_path) -> None:
    root = tmp_path / "Dropbox"
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
        "30 JUNIO 0905 MADRID PINTO HOSPITAL CENTRAL EXP2026 001",
    )
    assert get_nombre_mes(6) == "JUNIO"


def test_resolve_destination_folder_uses_download_root_without_dropbox(tmp_path) -> None:
    row = {
        "id": 7,
        "expediente": "EXP-7",
        "ruta_carpeta": "",
        "fecha_limite": "2026-06-30",
    }

    destination = resolve_destination_folder(row, download_root=tmp_path, dropbox_root=None)

    assert destination == tmp_path / "2026-06-30 EXP-7"


def test_storage_root_for_destination_rejects_outside_path(tmp_path) -> None:
    root = tmp_path / "root"
    inside = root / "folder"
    outside = tmp_path / "outside"

    assert storage_root_for_destination(inside, [root]) == root.resolve()
    with pytest.raises(LocalStorageError):
        storage_root_for_destination(outside, [root])


def test_write_http_url_creates_shortcut_file(tmp_path) -> None:
    write_http_url(tmp_path, "https://example.test/perfil")

    assert (tmp_path / "HTTP.url").read_text(encoding="utf-8") == "[InternetShortcut]\nURL=https://example.test/perfil\n"
    bat = (tmp_path / DOWNLOAD_BAT_FILENAME).read_text(encoding="utf-8")
    assert 'Infonalia\\Descargar_Licitacion.py' in bat
    assert 'python "%SCRIPT%"' in bat


def test_is_internal_download_path_checks_download_root(tmp_path) -> None:
    root = tmp_path / "descargas"
    inside = root / "expediente"
    outside = tmp_path / "otra"

    assert is_internal_download_path(inside, root) is True
    assert is_internal_download_path(outside, root) is False
    assert folder_descriptor({"provincia": "Madrid", "organismo": "Ayuntamiento de Pinto", "objeto": "Servicio de limpieza"}) == "PINTO LIMPIEZA"
