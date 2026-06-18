from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .classification import classify_document, classify_folder, is_relevant_document, is_system_file
from .markers import is_monitor_marker
from .scanner import MarkerRecord


@dataclass(frozen=True)
class InventoryFile:
    licitacion_id: int
    folder_path: Path
    absolute_path: Path
    relative_path: str
    file_name: str
    extension: str
    file_type: str
    folder_type: str
    is_relevant: bool
    is_system_file: bool
    size_bytes: int
    modified_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "licitacion_id": self.licitacion_id,
            "folder_path": str(self.folder_path),
            "absolute_path": str(self.absolute_path),
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "extension": self.extension,
            "file_type": self.file_type,
            "folder_type": self.folder_type,
            "is_relevant": self.is_relevant,
            "is_system_file": self.is_system_file,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
        }


def timestamp_iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds).replace(microsecond=0).isoformat()


def scan_inventory_files(marker: MarkerRecord) -> list[InventoryFile]:
    files: list[InventoryFile] = []
    if not marker.folder_path.exists() or not marker.folder_path.is_dir():
        return files
    for path in sorted(marker.folder_path.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or is_monitor_marker(path):
            continue
        relative_path = str(path.relative_to(marker.folder_path))
        file_type = classify_document(path, relative_path)
        folder_type = classify_folder(relative_path)
        system_file = is_system_file(path)
        stat = path.stat()
        files.append(
            InventoryFile(
                licitacion_id=marker.licitacion_id,
                folder_path=marker.folder_path,
                absolute_path=path,
                relative_path=relative_path,
                file_name=path.name,
                extension=path.suffix.casefold(),
                file_type=file_type,
                folder_type=folder_type,
                is_relevant=is_relevant_document(path, file_type, folder_type),
                is_system_file=system_file,
                size_bytes=stat.st_size,
                modified_at=timestamp_iso(stat.st_mtime),
            )
        )
    return files
