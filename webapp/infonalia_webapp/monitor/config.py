from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MONITOR_ROOT = Path(r"C:\ReplicaDb")
DEFAULT_YEAR_MIN = 2000
DEFAULT_YEAR_MAX = 2300
REAL_DROPBOX_ERROR = (
    "El monitor esta configurado contra una carpeta Dropbox real. "
    "Para evitar accidentes, usa C:\\ReplicaDb o activa explicitamente "
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


def load_monitor_config(root_override: str | Path | None = None) -> MonitorConfig:
    raw_root = (
        str(root_override)
        if root_override is not None
        else os.environ.get("INFONALIA_MONITOR_ROOT")
        or os.environ.get("INFONALIA_DROPBOX_ROOT")
        or str(DEFAULT_MONITOR_ROOT)
    )
    root_path = Path(raw_root).expanduser()
    allow_real_dropbox = os.environ.get("INFONALIA_MONITOR_ALLOW_REAL_DROPBOX", "0") == "1"
    year_min = _env_int("INFONALIA_MONITOR_YEAR_MIN", DEFAULT_YEAR_MIN)
    year_max = _env_int("INFONALIA_MONITOR_YEAR_MAX", DEFAULT_YEAR_MAX)
    if year_min > year_max:
        raise MonitorConfigError("INFONALIA_MONITOR_YEAR_MIN no puede ser mayor que INFONALIA_MONITOR_YEAR_MAX.")
    if path_contains_dropbox(root_path) and not allow_real_dropbox:
        raise MonitorConfigError(REAL_DROPBOX_ERROR)
    return MonitorConfig(
        root_path=root_path,
        year_min=year_min,
        year_max=year_max,
        allow_real_dropbox=allow_real_dropbox,
    )

