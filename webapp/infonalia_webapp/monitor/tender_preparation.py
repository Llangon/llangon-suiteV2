from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from herramientas_python.descargadores.registry import get_downloader_spec, normalize_platform

try:
    from ..seguimiento_markers import get_marker_status_for_licitacion
except ImportError:  # pragma: no cover
    from seguimiento_markers import get_marker_status_for_licitacion

from .scanner import MarkerRecord, ScanResult, scan_marker_tree
from .snapshots import normalize_text, read_technical_snapshot


@dataclass(frozen=True)
class TenderPreparation:
    licitacion_id: int
    followed: bool
    prepared: bool
    reason: str
    platform: str
    source_url: str
    destination: Path | None
    marker_path: Path | None
    has_technical_state: bool
    preparation_code: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "licitacion_id": self.licitacion_id,
            "followed": self.followed,
            "prepared": self.prepared,
            "reason": self.reason,
            "platform": self.platform,
            "source_url": self.source_url,
            "destination": str(self.destination or ""),
            "marker_path": str(self.marker_path or ""),
            "has_technical_state": self.has_technical_state,
            "preparation_code": self.preparation_code,
        }


def read_http_shortcut_url(folder: Path | None) -> str:
    if folder is None:
        return ""
    shortcut = folder / "HTTP.url"
    if not shortcut.is_file():
        return ""
    try:
        for line in shortcut.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if line.strip().lower().startswith("url="):
                return normalize_text(line.split("=", 1)[1])
    except OSError:
        return ""
    return ""


def valid_profile_url(platform: str, value: object) -> bool:
    """Accept an HTTP(S) tender profile URL, never a downloadable document."""

    url = normalize_text(value)
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    lowered_path = parsed.path.lower()
    lowered_query = parsed.query.lower()
    if (
        "getdocumentbyidservlet" in lowered_path
        or "documentidparam=" in lowered_query
        or lowered_path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".xml"))
    ):
        return False
    host = parsed.hostname.lower() if parsed.hostname else ""
    if platform == "PLACE" and host.endswith("contrataciondelestado.es"):
        return True
    return True


def resolve_profile_url(platform: str, stored_url: object, destination: Path | None) -> str:
    database_url = normalize_text(stored_url)
    shortcut_url = read_http_shortcut_url(destination)
    if valid_profile_url(platform, database_url):
        return database_url
    if valid_profile_url(platform, shortcut_url):
        return shortcut_url
    return database_url or shortcut_url


def discover_followed(root: Path | str, year_min: int = 2000, year_max: int = 2300) -> tuple[list[MarkerRecord], ScanResult]:
    result = scan_marker_tree(root, year_min, year_max)
    return [marker for marker in result.markers if marker.is_followed], result


def canonical_follow_marker_for_row(
    row: sqlite3.Row | Mapping[str, object],
    *,
    root: Path | str | None,
    marker: MarkerRecord | None = None,
    year_min: int = 2000,
    year_max: int = 2300,
) -> MarkerRecord | None:
    """Resolve follow state from the live id marker, never from a stored folder path."""

    licitacion_id = int(row["id"])
    if marker is not None and marker.licitacion_id == licitacion_id:
        return marker
    if root is None:
        return None
    markers, _scan = discover_followed(root, year_min, year_max)
    return next((item for item in markers if item.licitacion_id == licitacion_id), None)


def preparation_for_row(
    row: sqlite3.Row | Mapping[str, object],
    *,
    root: Path | str | None,
    marker: MarkerRecord | None = None,
    year_min: int = 2000,
    year_max: int = 2300,
) -> TenderPreparation:
    licitacion_id = int(row["id"])
    canonical_marker = canonical_follow_marker_for_row(
        row,
        root=root,
        marker=marker,
        year_min=year_min,
        year_max=year_max,
    )
    if canonical_marker is not None:
        destination = canonical_marker.folder_path
        marker_path = canonical_marker.follow_marker_path
        followed = canonical_marker.is_followed and bool(
            canonical_marker.follow_marker_path and canonical_marker.follow_marker_path.is_file()
        )
    elif root is not None:
        # A configured monitor root is authoritative. Do not fall back to a
        # potentially stale ruta_carpeta stored in SQLite.
        destination = None
        marker_path = None
        followed = False
    else:
        status = get_marker_status_for_licitacion(row, None)
        destination_text = normalize_text(status.get("folder_path"))
        destination = Path(destination_text) if destination_text else None
        marker_text = normalize_text(status.get("follow_marker_path"))
        marker_path = Path(marker_text) if marker_text else None
        followed = bool(status.get("activo")) and bool(marker_path and marker_path.is_file())
    platform = normalize_platform(row["plataforma"] if "plataforma" in row.keys() else "")  # type: ignore[attr-defined]
    stored_url = row["enlace_perfil"] if "enlace_perfil" in row.keys() else ""  # type: ignore[attr-defined]
    source_url = resolve_profile_url(platform, stored_url, destination)
    reason = ""
    preparation_code = ""
    if not followed:
        reason = "No existe el marcador físico EnSeguimiento.llangon."
    elif not destination or not destination.is_dir():
        reason = "La carpeta documental registrada no existe."
    elif not source_url:
        reason = "Falta el enlace oficial de la plataforma."
        preparation_code = "INVALID_PROFILE_URL"
    elif not valid_profile_url(platform, source_url):
        reason = "La URL registrada no corresponde a una ficha válida de la plataforma."
        preparation_code = "INVALID_PROFILE_URL"
    elif not platform:
        reason = "Falta la plataforma de contratación."
    else:
        try:
            get_downloader_spec(platform)
        except ValueError:
            reason = f"La plataforma {platform} no dispone de descargador registrado."
    return TenderPreparation(
        licitacion_id=licitacion_id,
        followed=followed,
        prepared=not reason,
        reason=reason,
        platform=platform,
        source_url=source_url,
        destination=destination,
        marker_path=marker_path,
        has_technical_state=bool(destination and read_technical_snapshot(destination)),
        preparation_code=preparation_code,
    )
