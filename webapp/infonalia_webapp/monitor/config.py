from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from ..dropbox_paths import DROPBOX_BASE_ENV, LEGACY_DROPBOX_ROOT_ENV
except ImportError:
    from dropbox_paths import DROPBOX_BASE_ENV, LEGACY_DROPBOX_ROOT_ENV


DEFAULT_YEAR_MIN = 2000
DEFAULT_YEAR_MAX = 2300
REAL_DROPBOX_ERROR = (
    "El monitor esta configurado contra una carpeta Dropbox real. "
    "Para evitar accidentes, configura una replica local explicita o activa "
    "INFONALIA_MONITOR_ALLOW_REAL_DROPBOX=1."
)


class MonitorConfigError(ValueError):
    """Unsafe or invalid monitor configuration."""


@dataclass(frozen=True)
class MonitorConfig:
    root_path: Path
    year_min: int = DEFAULT_YEAR_MIN
    year_max: int = DEFAULT_YEAR_MAX
    allow_real_dropbox: bool = False
    root_source: str = ""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise MonitorConfigError(f"{name} debe ser un anio numerico.") from exc


def path_contains_dropbox(path: Path) -> bool:
    return any(part.casefold() == "dropbox" for part in path.parts)


def _configured_root_from_env() -> tuple[str, str]:
    explicit = os.environ.get("INFONALIA_MONITOR_ROOT")
    if explicit:
        return explicit, "INFONALIA_MONITOR_ROOT"
    dropbox_base = os.environ.get(DROPBOX_BASE_ENV)
    if dropbox_base:
        return dropbox_base, DROPBOX_BASE_ENV
    legacy = os.environ.get(LEGACY_DROPBOX_ROOT_ENV)
    if legacy:
        return legacy, LEGACY_DROPBOX_ROOT_ENV
    return "", "none"


def load_monitor_config(root_override: str | Path | None = None) -> MonitorConfig:
    raw_root, source = (str(root_override), "override") if root_override is not None else _configured_root_from_env()
    if not raw_root:
        raise MonitorConfigError("Inventario no ejecutado: LLANGON_DROPBOX_BASE_PATH no configurada o ruta inexistente.")
    root_path = Path(raw_root).expanduser()
    allow_real_dropbox = os.environ.get("INFONALIA_MONITOR_ALLOW_REAL_DROPBOX", "0") == "1"
    year_min = _env_int("INFONALIA_MONITOR_YEAR_MIN", DEFAULT_YEAR_MIN)
    year_max = _env_int("INFONALIA_MONITOR_YEAR_MAX", DEFAULT_YEAR_MAX)
    if year_min > year_max:
        raise MonitorConfigError("INFONALIA_MONITOR_YEAR_MIN no puede ser mayor que INFONALIA_MONITOR_YEAR_MAX.")
    if source == DROPBOX_BASE_ENV and (not root_path.exists() or not root_path.is_dir()):
        raise MonitorConfigError("Inventario no ejecutado: LLANGON_DROPBOX_BASE_PATH no configurada o ruta inexistente.")
    if source == LEGACY_DROPBOX_ROOT_ENV and (not root_path.exists() or not root_path.is_dir()):
        raise MonitorConfigError("Inventario no ejecutado: INFONALIA_DROPBOX_ROOT apunta a una ruta inexistente.")
    if source not in {DROPBOX_BASE_ENV, LEGACY_DROPBOX_ROOT_ENV} and path_contains_dropbox(root_path) and not allow_real_dropbox:
        raise MonitorConfigError(REAL_DROPBOX_ERROR)
    return MonitorConfig(
        root_path=root_path,
        year_min=year_min,
        year_max=year_max,
        allow_real_dropbox=allow_real_dropbox,
        root_source=source,
    )
