from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from .normalization import clean_text
    from .storage_paths import dropbox_relative_path, path_is_relative_to
except ImportError:
    from normalization import clean_text
    from storage_paths import dropbox_relative_path, path_is_relative_to


DROPBOX_BASE_ENV = "LLANGON_DROPBOX_BASE_PATH"
LEGACY_DROPBOX_ROOT_ENV = "INFONALIA_DROPBOX_ROOT"


class DropboxPathError(ValueError):
    """Raised when a local Dropbox path cannot be resolved safely."""


@dataclass(frozen=True)
class DropboxBaseStatus:
    configured: bool
    ok: bool
    path: str
    exists: bool
    is_dir: bool
    error: str
    source: str
    env_var: str
    label: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LicitacionFolderResolution:
    ok: bool
    path: str
    exists: bool
    inside_dropbox_base: bool
    reason: str
    message: str
    base_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _env(environ: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _expand_path(value: object) -> Path:
    return Path(os.path.expandvars(clean_text(value)).strip('"')).expanduser()


def configured_dropbox_base_path(environ: Mapping[str, str] | None = None) -> Path | None:
    configured = clean_text(_env(environ).get(DROPBOX_BASE_ENV))
    if not configured:
        return None
    return _expand_path(configured)


def legacy_dropbox_root_path(environ: Mapping[str, str] | None = None) -> Path | None:
    configured = clean_text(_env(environ).get(LEGACY_DROPBOX_ROOT_ENV))
    if not configured:
        return None
    return _expand_path(configured)


def preferred_dropbox_base_path(environ: Mapping[str, str] | None = None) -> Path | None:
    return configured_dropbox_base_path(environ) or legacy_dropbox_root_path(environ)


def dropbox_base_status(environ: Mapping[str, str] | None = None) -> DropboxBaseStatus:
    base = configured_dropbox_base_path(environ)
    source = "env" if base else "none"
    env_var = DROPBOX_BASE_ENV if base else ""
    label = "LLANGON_DROPBOX_BASE_PATH" if base else "No configurada"
    if not base:
        legacy = legacy_dropbox_root_path(environ)
        if legacy and legacy.exists() and legacy.is_dir():
            base = legacy
            source = "legacy"
            env_var = LEGACY_DROPBOX_ROOT_ENV
            label = "Fallback legado INFONALIA_DROPBOX_ROOT"
    if not base:
        return DropboxBaseStatus(
            configured=False,
            ok=False,
            path="",
            exists=False,
            is_dir=False,
            error="Carpeta Dropbox no configurada.",
            source=source,
            env_var=env_var,
            label=label,
        )

    exists = base.exists()
    is_dir = exists and base.is_dir()
    return DropboxBaseStatus(
        configured=True,
        ok=is_dir,
        path=str(base),
        exists=exists,
        is_dir=is_dir,
        error="" if is_dir else "La carpeta base de Dropbox no existe o no es una carpeta.",
        source=source,
        env_var=env_var,
        label=label,
    )


def validate_dropbox_base_path(environ: Mapping[str, str] | None = None) -> Path:
    status = dropbox_base_status(environ)
    if not status.configured:
        raise DropboxPathError("Carpeta Dropbox no configurada.")
    if not status.ok:
        raise DropboxPathError(status.error)
    return Path(status.path)


def resolve_path_inside_base(base_path: Path | str, relative_path: object) -> Path:
    text = clean_text(relative_path).strip('"')
    if not text:
        raise DropboxPathError("La ruta relativa está vacía.")
    if "\x00" in text:
        raise DropboxPathError("La ruta contiene caracteres no permitidos.")

    raw = Path(text)
    if raw.is_absolute() or (len(text) >= 2 and text[1] == ":"):
        raise DropboxPathError("No se admiten rutas absolutas.")

    parts = [part for part in text.replace("\\", "/").split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise DropboxPathError("La ruta no puede salir de la carpeta base de Dropbox.")

    base = Path(base_path).resolve(strict=False)
    resolved = (base / Path(*parts)).resolve(strict=False)
    if not path_is_relative_to(resolved, base):
        raise DropboxPathError("La ruta queda fuera de la carpeta base de Dropbox.")
    return resolved


def path_inside_base(path: Path | str, base_path: Path | str) -> bool:
    return path_is_relative_to(Path(path).resolve(strict=False), Path(base_path).resolve(strict=False))


def resolve_licitacion_folder(
    licitacion: Any,
    *,
    dropbox_base: Path | None = None,
    download_root: Path | None = None,
) -> LicitacionFolderResolution:
    base = dropbox_base or preferred_dropbox_base_path()
    base_ok = bool(base and Path(base).exists() and Path(base).is_dir())
    base_path = str(base) if base else ""
    ruta = clean_text(_row_get(licitacion, "ruta_carpeta")).strip('"')

    if ruta:
        candidate = Path(ruta)
        if candidate.is_absolute() or (len(ruta) >= 2 and ruta[1] == ":"):
            exists = candidate.exists()
            inside = bool(base_ok and path_inside_base(candidate, Path(base)))
            if base_ok and not inside:
                return LicitacionFolderResolution(
                    ok=True,
                    path=str(candidate),
                    exists=exists,
                    inside_dropbox_base=False,
                    reason="outside_dropbox_base",
                    message="La ruta está fuera de la carpeta base de Dropbox.",
                    base_path=base_path,
                )
            if not base_ok:
                return LicitacionFolderResolution(
                    ok=True,
                    path=str(candidate),
                    exists=exists,
                    inside_dropbox_base=False,
                    reason="dropbox_base_not_configured",
                    message="Carpeta no configurada.",
                    base_path=base_path,
                )
            return LicitacionFolderResolution(
                ok=True,
                path=str(candidate),
                exists=exists,
                inside_dropbox_base=True,
                reason="valid" if exists else "missing",
                message="Carpeta válida." if exists else "La ruta no existe.",
                base_path=base_path,
            )

        if base_ok:
            try:
                resolved = resolve_path_inside_base(Path(base), ruta)
            except DropboxPathError as exc:
                return LicitacionFolderResolution(
                    ok=False,
                    path="",
                    exists=False,
                    inside_dropbox_base=False,
                    reason="invalid_path",
                    message=str(exc),
                    base_path=base_path,
                )
            exists = resolved.exists()
            return LicitacionFolderResolution(
                ok=True,
                path=str(resolved),
                exists=exists,
                inside_dropbox_base=True,
                reason="valid" if exists else "missing",
                message="Carpeta válida." if exists else "La ruta no existe.",
                base_path=base_path,
            )

        return LicitacionFolderResolution(
            ok=False,
            path=ruta,
            exists=False,
            inside_dropbox_base=False,
            reason="dropbox_base_not_configured",
            message="Carpeta no configurada.",
            base_path=base_path,
        )

    if download_root:
        fallback = Path(download_root).resolve(strict=False)
        return LicitacionFolderResolution(
            ok=True,
            path=str(fallback),
            exists=fallback.exists(),
            inside_dropbox_base=False,
            reason="fallback",
            message="Carpeta no configurada.",
            base_path=base_path,
        )

    return LicitacionFolderResolution(
        ok=False,
        path="",
        exists=False,
        inside_dropbox_base=False,
        reason="missing",
        message="Carpeta no configurada.",
        base_path=base_path,
    )


def folder_status_label(resolution: LicitacionFolderResolution) -> str:
    if not resolution.ok:
        return resolution.message or "Carpeta no configurada."
    if not resolution.path:
        return "Carpeta no configurada."
    if resolution.reason == "outside_dropbox_base":
        return "La ruta está fuera de la carpeta base de Dropbox."
    if not resolution.exists:
        return "La ruta no existe."
    if resolution.inside_dropbox_base:
        return "Carpeta válida."
    return "Carpeta no configurada."


def stored_folder_path_for_base(value: object, base_path: Path | None = None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if base_path:
        relative = dropbox_relative_path(text, base_path)
        if relative:
            return relative
    return dropbox_relative_path(text) or text


def _row_get(row: Any, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return ""
