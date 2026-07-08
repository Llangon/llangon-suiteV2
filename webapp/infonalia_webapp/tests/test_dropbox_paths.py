from __future__ import annotations

from pathlib import Path

import pytest

from webapp.infonalia_webapp.dropbox_paths import (
    DROPBOX_BASE_ENV,
    LEGACY_DROPBOX_ROOT_ENV,
    DropboxPathError,
    build_expected_expediente_relative_path,
    dropbox_base_status,
    folder_status_label,
    resolve_licitacion_folder,
    resolve_expected_expediente_path,
    resolve_path_inside_base,
    validate_dropbox_base_path,
)
from webapp.infonalia_webapp.storage_paths import DOWNLOAD_BAT_FILENAME, write_http_url


def test_dropbox_base_path_not_defined_is_controlled() -> None:
    status = dropbox_base_status({})

    assert status.configured is False
    assert status.ok is False
    assert status.error == "Carpeta Dropbox no configurada."
    with pytest.raises(DropboxPathError, match="no configurada"):
        validate_dropbox_base_path({})


def test_dropbox_base_path_defined_and_existing(tmp_path: Path) -> None:
    env = {DROPBOX_BASE_ENV: str(tmp_path)}

    status = dropbox_base_status(env)

    assert status.configured is True
    assert status.ok is True
    assert Path(status.path) == tmp_path
    assert validate_dropbox_base_path(env) == tmp_path


def test_dropbox_base_path_defined_but_missing(tmp_path: Path) -> None:
    missing = tmp_path / "Dropbox real"
    env = {DROPBOX_BASE_ENV: str(missing)}

    status = dropbox_base_status(env)

    assert status.configured is True
    assert status.ok is False
    assert status.exists is False
    assert "no existe" in status.error


def test_dropbox_base_path_has_priority_over_legacy(tmp_path: Path) -> None:
    base = tmp_path / "DropboxReal"
    legacy = tmp_path / "ReplicaDb"
    base.mkdir()
    legacy.mkdir()
    env = {
        DROPBOX_BASE_ENV: str(base),
        LEGACY_DROPBOX_ROOT_ENV: str(legacy),
    }

    status = dropbox_base_status(env)

    assert status.ok is True
    assert status.path == str(base)
    assert status.source == "env"
    assert status.env_var == DROPBOX_BASE_ENV


def test_invalid_primary_dropbox_base_does_not_fall_back_to_legacy(tmp_path: Path) -> None:
    missing_base = tmp_path / "DropboxReal"
    legacy = tmp_path / "ReplicaDb"
    legacy.mkdir()
    env = {
        DROPBOX_BASE_ENV: str(missing_base),
        LEGACY_DROPBOX_ROOT_ENV: str(legacy),
    }

    status = dropbox_base_status(env)

    assert status.ok is False
    assert status.path == str(missing_base)
    assert status.source == "env"
    assert status.env_var == DROPBOX_BASE_ENV


def test_legacy_dropbox_root_is_used_as_fallback_when_existing(tmp_path: Path) -> None:
    legacy = tmp_path / "ReplicaDb"
    legacy.mkdir()
    env = {LEGACY_DROPBOX_ROOT_ENV: str(legacy)}

    status = dropbox_base_status(env)

    assert status.ok is True
    assert status.path == str(legacy)
    assert status.source == "legacy"
    assert status.env_var == LEGACY_DROPBOX_ROOT_ENV
    assert "legado" in status.label.lower()


def test_legacy_missing_dropbox_root_does_not_force_real_dropbox(tmp_path: Path) -> None:
    env = {LEGACY_DROPBOX_ROOT_ENV: str(tmp_path / "ReplicaDb")}

    status = dropbox_base_status(env)

    assert status.configured is False
    assert status.ok is False
    assert status.error == "Carpeta Dropbox no configurada."


def test_licitacion_folder_inside_dropbox_base(tmp_path: Path) -> None:
    folder = tmp_path / "2026" / "06 JUNIO" / "EXP TEST"
    folder.mkdir(parents=True)

    result = resolve_licitacion_folder(
        {"ruta_carpeta": r"2026\06 JUNIO\EXP TEST"},
        dropbox_base=tmp_path,
    )

    assert result.ok is True
    assert result.exists is True
    assert result.inside_dropbox_base is True
    assert Path(result.path) == folder
    assert folder_status_label(result) == "Carpeta válida."


def test_expected_expediente_path_is_year_month_folder_inside_base(tmp_path: Path) -> None:
    licitacion = {
        "expediente": "A2026004397",
        "provincia": "Castilla y Leon",
        "organismo": "Gerencia de Servicios Sociales de Castilla y Leon",
        "objeto": "El suministro de carne y derivados para los centros dependientes",
        "fecha_limite": "2026-06-30",
        "hora_limite": "19:00",
    }

    relative = build_expected_expediente_relative_path(licitacion)
    absolute = resolve_expected_expediente_path(licitacion, dropbox_base=tmp_path)

    assert Path(relative).parts[:2] == ("2026", "06 JUNIO")
    assert Path(relative).name == "30 JUNIO 1900 CASTILLA Y LEON CARNE Y DERIVADOS A2026004397"
    assert absolute == tmp_path / relative


def test_licitacion_folder_legacy_month_route_can_resolve_existing_year_folder(tmp_path: Path) -> None:
    folder = tmp_path / "2026" / "07 JULIO" / "EXP TEST"
    folder.mkdir(parents=True)

    result = resolve_licitacion_folder(
        {"ruta_carpeta": r"07 JULIO\EXP TEST"},
        dropbox_base=tmp_path,
    )

    assert result.ok is True
    assert result.exists is True
    assert result.inside_dropbox_base is True
    assert Path(result.path) == folder
    assert result.reason == "valid"


def test_licitacion_folder_outside_dropbox_base(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir()

    result = resolve_licitacion_folder(
        {"ruta_carpeta": str(outside)},
        dropbox_base=tmp_path,
    )

    assert result.ok is True
    assert result.exists is True
    assert result.inside_dropbox_base is False
    assert result.reason == "outside_dropbox_base"
    assert folder_status_label(result) == "La ruta está fuera de la carpeta base de Dropbox."


@pytest.mark.parametrize("relative_path", [r"..\fuera", "../fuera", r"2026\..\fuera"])
def test_resolve_path_inside_base_rejects_traversal(tmp_path: Path, relative_path: str) -> None:
    with pytest.raises(DropboxPathError):
        resolve_path_inside_base(tmp_path, relative_path)


def test_resolve_path_inside_base_normalizes_windows_path(tmp_path: Path) -> None:
    result = resolve_path_inside_base(tmp_path, r"2026\06 JUNIO\EXP TEST")

    assert result == tmp_path / "2026" / "06 JUNIO" / "EXP TEST"


def test_write_http_url_does_not_overwrite_existing_files(tmp_path: Path) -> None:
    folder = tmp_path / "licitacion"
    folder.mkdir()
    http_file = folder / "HTTP.url"
    bat_file = folder / DOWNLOAD_BAT_FILENAME
    http_file.write_text("manual", encoding="utf-8")
    bat_file.write_text("manual bat", encoding="utf-8")

    write_http_url(folder, "https://example.test/nuevo")

    assert http_file.read_text(encoding="utf-8") == "manual"
    assert bat_file.read_text(encoding="utf-8") == "manual bat"
