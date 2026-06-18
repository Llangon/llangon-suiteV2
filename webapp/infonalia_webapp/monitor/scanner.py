from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .markers import FOLLOW_MARKER_NAME, read_marker_id


@dataclass(frozen=True)
class MonitorIssue:
    code: str
    message: str
    path: str = ""
    licitacion_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.path:
            payload["path"] = self.path
        if self.licitacion_id is not None:
            payload["licitacion_id"] = self.licitacion_id
        return payload


@dataclass(frozen=True)
class MarkerRecord:
    licitacion_id: int
    folder_path: Path
    marker_path: Path
    follow_marker_path: Path | None = None

    @property
    def is_followed(self) -> bool:
        return self.follow_marker_path is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "licitacion_id": self.licitacion_id,
            "folder_path": str(self.folder_path),
            "marker_path": str(self.marker_path),
            "follow_marker_path": str(self.follow_marker_path or ""),
            "seguimiento_activo": self.is_followed,
        }


@dataclass
class ScanResult:
    root_path: Path
    year_roots: list[Path] = field(default_factory=list)
    markers: list[MarkerRecord] = field(default_factory=list)
    conflicts: list[MonitorIssue] = field(default_factory=list)
    warnings: list[MonitorIssue] = field(default_factory=list)
    raw_id_marker_count: int = 0

    @property
    def followed_count(self) -> int:
        return sum(1 for marker in self.markers if marker.is_followed)


def is_year_folder(name: object, min_year: int = 2000, max_year: int = 2300) -> bool:
    text = str(name or "").strip()
    if len(text) != 4 or not text.isdigit():
        return False
    year = int(text)
    return min_year <= year <= max_year


def iter_monitor_year_roots(root: Path | str, min_year: int = 2000, max_year: int = 2300) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"No existe la raiz del monitor: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"La raiz del monitor no es una carpeta: {root_path}")
    return [
        child
        for child in sorted(root_path.iterdir(), key=lambda path: path.name.casefold())
        if child.is_dir() and not child.is_symlink() and is_year_folder(child.name, min_year, max_year)
    ]


def find_id_markers(root: Path | str, min_year: int = 2000, max_year: int = 2300) -> list[Path]:
    markers: list[Path] = []
    for year_root in iter_monitor_year_roots(root, min_year, max_year):
        for dirpath, dirnames, filenames in os.walk(year_root, followlinks=False):
            folder = Path(dirpath)
            dirnames[:] = [name for name in dirnames if not (folder / name).is_symlink()]
            for filename in filenames:
                marker_path = folder / filename
                if read_marker_id(marker_path) is not None:
                    markers.append(marker_path)
    return sorted(markers, key=lambda path: str(path).casefold())


def scan_marker_tree(root: Path | str, min_year: int = 2000, max_year: int = 2300) -> ScanResult:
    root_path = Path(root)
    result = ScanResult(root_path=root_path)
    result.year_roots = iter_monitor_year_roots(root_path, min_year, max_year)
    by_folder: dict[Path, list[Path]] = {}

    for marker_path in find_id_markers(root_path, min_year, max_year):
        by_folder.setdefault(marker_path.parent, []).append(marker_path)
        result.raw_id_marker_count += 1

    candidates: list[MarkerRecord] = []
    for folder_path, marker_paths in sorted(by_folder.items(), key=lambda item: str(item[0]).casefold()):
        marker_paths = sorted(marker_paths, key=lambda path: path.name.casefold())
        if len(marker_paths) > 1:
            result.conflicts.append(
                MonitorIssue(
                    code="multiple_ids_in_folder",
                    message="La carpeta tiene varios marcadores de id .llangon.",
                    path=str(folder_path),
                )
            )
            continue
        marker_path = marker_paths[0]
        licitacion_id = read_marker_id(marker_path)
        if licitacion_id is None:
            continue
        follow_marker = folder_path / FOLLOW_MARKER_NAME
        candidates.append(
            MarkerRecord(
                licitacion_id=licitacion_id,
                folder_path=folder_path,
                marker_path=marker_path,
                follow_marker_path=follow_marker if follow_marker.is_file() else None,
            )
        )

    by_id: dict[int, list[MarkerRecord]] = {}
    for marker in candidates:
        by_id.setdefault(marker.licitacion_id, []).append(marker)
    duplicate_ids = {
        licitacion_id
        for licitacion_id, records in by_id.items()
        if len({str(record.folder_path).casefold() for record in records}) > 1
    }
    for licitacion_id in sorted(duplicate_ids):
        records = by_id[licitacion_id]
        result.conflicts.append(
            MonitorIssue(
                code="duplicate_id_marker",
                message="El mismo id de licitacion aparece en varias carpetas.",
                path=" | ".join(str(record.folder_path) for record in records),
                licitacion_id=licitacion_id,
            )
        )

    result.markers = [marker for marker in candidates if marker.licitacion_id not in duplicate_ids]
    return result

