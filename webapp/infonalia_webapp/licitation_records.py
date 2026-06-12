from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


PlatformDetector = Callable[[str], str]
ValueNormalizer = Callable[[object], str]


def licitation_row_to_dict(
    row: Any,
    *,
    detect_platform: PlatformDetector,
    normalize_url_value: ValueNormalizer,
    normalize_folder_path: ValueNormalizer,
) -> dict[str, object]:
    item = {key: row[key] for key in row.keys()}
    if not clean_text(item.get("plataforma")):
        item["plataforma"] = detect_platform(clean_text(item.get("enlace_perfil")))
    item["enlace_perfil"] = normalize_url_value(item.get("enlace_perfil"))
    item["enlace_infonalia"] = normalize_url_value(item.get("enlace_infonalia"))
    item["ruta_carpeta"] = normalize_folder_path(item.get("ruta_carpeta"))
    return item
