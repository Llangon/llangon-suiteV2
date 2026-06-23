from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .folder_names import (
        expediente_folder_text,
        extract_municipio_from_organismo,
        extract_objeto_folder_key,
        folder_text,
        safe_folder_name,
    )
    from .local_storage import LocalStorageError
    from .normalization import clean_text, parse_time_value
except ImportError:
    from folder_names import (
        expediente_folder_text,
        extract_municipio_from_organismo,
        extract_objeto_folder_key,
        folder_text,
        safe_folder_name,
    )
    from local_storage import LocalStorageError
    from normalization import clean_text, parse_time_value


DOWNLOAD_BAT_FILENAME = "Descargar ficheros de la plataforma.bat"
DOWNLOAD_BAT_CONTENT = """@echo off
setlocal
cd /d "%~dp0"
set "BUSCAR=%CD%"
:buscar_lanzador
if exist "%BUSCAR%\\Infonalia\\Descargar_Licitacion.py" (
    set "SCRIPT=%BUSCAR%\\Infonalia\\Descargar_Licitacion.py"
    goto ejecutar
)
for %%I in ("%BUSCAR%\\..") do set "PADRE=%%~fI"
if /I "%PADRE%"=="%BUSCAR%" goto no_encontrado
set "BUSCAR=%PADRE%"
goto buscar_lanzador
:no_encontrado
echo No se encontro Infonalia\\Descargar_Licitacion.py buscando desde:
echo %~dp0
pause
exit /b 1
:ejecutar
python "%SCRIPT%"
if errorlevel 1 pause
"""


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def is_internal_download_path(value: object, download_root: Path) -> bool:
    text = clean_text(value)
    if not text:
        return False
    path = Path(text)
    if not path.is_absolute():
        return False
    return path_is_relative_to(path, download_root)


def normalize_relative_folder_path(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parts = [
        safe_folder_name(part)
        for part in re.split(r"[\\/]+", text)
        if clean_text(part) and clean_text(part) not in {".", ".."}
    ]
    return str(Path(*parts)) if parts else ""


def dropbox_relative_path(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value).strip('"')
    if not text:
        return ""

    path = Path(text)
    if not path.is_absolute():
        return normalize_relative_folder_path(text)

    if dropbox_root:
        try:
            return normalize_relative_folder_path(str(path.resolve().relative_to(dropbox_root.resolve())))
        except ValueError:
            pass

    parts = [
        part.strip()
        for part in re.split(r"[\\/]+", text)
        if part.strip() and not re.fullmatch(r"[A-Za-z]:", part.strip())
    ]
    lower_parts = [part.lower() for part in parts]

    for marker in ("00000 llangon", "dropbox"):
        if marker in lower_parts:
            index = lower_parts.index(marker)
            relative_parts = parts[index + 1 :]
            if relative_parts:
                return normalize_relative_folder_path("\\".join(relative_parts))

    return ""


def folder_path_for_storage(value: object, dropbox_root: Path | None = None) -> str:
    text = clean_text(value)
    if not text:
        return ""

    relative = dropbox_relative_path(text, dropbox_root)
    if relative:
        return relative
    return text


def row_get(row: Any, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError):
        return ""


def folder_descriptor(row: Any) -> str:
    provincia = folder_text(row_get(row, "provincia"))
    municipio = extract_municipio_from_organismo(row_get(row, "organismo"), provincia)
    objeto_key = extract_objeto_folder_key(row_get(row, "objeto"))

    pieces = []
    if municipio and municipio != provincia and not objeto_key.startswith(municipio):
        pieces.append(municipio)
    if objeto_key:
        pieces.append(objeto_key)

    descriptor = " ".join(piece for piece in pieces if piece)
    return safe_folder_name(descriptor) if descriptor else ""


def get_nombre_mes(mes_numero: int) -> str:
    meses = [
        "",
        "ENERO",
        "FEBRERO",
        "MARZO",
        "ABRIL",
        "MAYO",
        "JUNIO",
        "JULIO",
        "AGOSTO",
        "SEPTIEMBRE",
        "OCTUBRE",
        "NOVIEMBRE",
        "DICIEMBRE",
    ]
    if 1 <= mes_numero <= 12:
        return meses[mes_numero]
    return ""


def default_dropbox_folder(row: Any, dropbox_root: Path) -> Path:
    expediente = expediente_folder_text(row_get(row, "expediente"))
    provincia = folder_text(row_get(row, "provincia"))
    descriptor = folder_descriptor(row)
    fecha_limite = clean_text(row_get(row, "fecha_limite"))
    hora = parse_time_value(row_get(row, "hora_limite")).replace(":", "")

    try:
        fecha = datetime.strptime(fecha_limite, "%Y-%m-%d")
    except ValueError:
        label = safe_folder_name(f"{provincia} {descriptor} {expediente}".strip())
        return dropbox_root / "Descargas Infonalia" / label

    mes_nombre = get_nombre_mes(fecha.month)
    carpeta_mes = f"{fecha.month:02d} {mes_nombre}"
    piezas = [
        f"{fecha.day:02d}",
        mes_nombre,
        hora,
        provincia,
        descriptor,
        expediente,
    ]
    carpeta_final = safe_folder_name(" ".join(pieza for pieza in piezas if pieza))
    return dropbox_root / f"{fecha.year:04d}" / carpeta_mes / carpeta_final


def resolve_destination_folder(row: Any, *, download_root: Path, dropbox_root: Path | None = None) -> Path:
    ruta = clean_text(row["ruta_carpeta"])

    if ruta:
        relative = dropbox_relative_path(ruta, dropbox_root)
        if relative and dropbox_root:
            return dropbox_root / relative

        candidate = Path(ruta)
        if candidate.is_absolute():
            if is_internal_download_path(candidate, download_root) and dropbox_root:
                return default_dropbox_folder(row, dropbox_root)
            return candidate

        if dropbox_root:
            return dropbox_root / normalize_relative_folder_path(ruta)

    if dropbox_root:
        return default_dropbox_folder(row, dropbox_root)

    label = f"{row_get(row, 'fecha_limite') or row_get(row, 'id')} {row_get(row, 'expediente')}"
    return download_root / safe_folder_name(label)


def write_http_url(folder: Path, url: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    http_url = folder / "HTTP.url"
    if not http_url.exists():
        http_url.write_text(
            "[InternetShortcut]\n" f"URL={url}\n",
            encoding="utf-8",
        )
    bat_path = folder / DOWNLOAD_BAT_FILENAME
    if not bat_path.exists():
        bat_path.write_text(DOWNLOAD_BAT_CONTENT, encoding="utf-8")


def storage_root_for_destination(destination: Path, allowed_roots: list[Path]) -> Path:
    resolved_destination = destination.resolve(strict=False)
    for root in allowed_roots:
        resolved_root = Path(root).resolve(strict=False)
        try:
            resolved_destination.relative_to(resolved_root)
            return resolved_root
        except ValueError:
            continue
    raise LocalStorageError("La carpeta de destino queda fuera del almacenamiento local permitido.")
