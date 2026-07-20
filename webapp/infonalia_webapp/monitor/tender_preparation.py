from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
        }


def discover_followed(root: Path | str, year_min: int = 2000, year_max: int = 2300) -> tuple[list[MarkerRecord], ScanResult]:
    result = scan_marker_tree(root, year_min, year_max)
    return [marker for marker in result.markers if marker.is_followed], result


def preparation_for_row(
    row: sqlite3.Row | Mapping[str, object],
    *,
    root: Path | str | None,
    marker: MarkerRecord | None = None,
) -> TenderPreparation:
    licitacion_id = int(row["id"])
    if marker is not None:
        destination = marker.folder_path
        marker_path = marker.follow_marker_path
        followed = marker.is_followed and bool(marker.follow_marker_path and marker.follow_marker_path.is_file())
    else:
        status = get_marker_status_for_licitacion(row, Path(root) if root else None)
        destination_text = normalize_text(status.get("folder_path"))
        destination = Path(destination_text) if destination_text else None
        marker_text = normalize_text(status.get("follow_marker_path"))
        marker_path = Path(marker_text) if marker_text else None
        followed = bool(status.get("activo")) and bool(marker_path and marker_path.is_file())
    platform = normalize_platform(row["plataforma"] if "plataforma" in row.keys() else "")  # type: ignore[attr-defined]
    source_url = normalize_text(row["enlace_perfil"] if "enlace_perfil" in row.keys() else "")  # type: ignore[attr-defined]
    reason = ""
    if not followed:
        reason = "No existe el marcador físico EnSeguimiento.llangon."
    elif not destination or not destination.is_dir():
        reason = "La carpeta documental registrada no existe."
    elif not source_url:
        reason = "Falta el enlace oficial de la plataforma."
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
    )
