from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from .core.models import StorageBackendName, StorageObject, StorageObjectType


class LocalStorageError(ValueError):
    """Raised when a local storage URI cannot be safely resolved."""


class LocalStorageBackend:
    backend_name = StorageBackendName.local

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def _normalize_uri(self, destination_uri: str) -> str:
        text = str(destination_uri or "").strip().replace("\\", "/")
        if text.startswith("local://"):
            text = text[len("local://") :]
        if text.startswith("local:/"):
            text = text[len("local:/") :]
        text = text.strip("/")
        path = PurePosixPath(text)
        if (
            not text
            or path.is_absolute()
            or any(part in {"", ".", ".."} or ":" in part for part in path.parts)
        ):
            raise LocalStorageError("Unsafe local storage URI")
        return f"local://{path.as_posix()}"

    def _resolve(self, destination_uri: str) -> tuple[str, Path]:
        uri = self._normalize_uri(destination_uri)
        relative = PurePosixPath(uri[len("local://") :])
        path = (self.root / Path(*relative.parts)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise LocalStorageError("Local storage URI escapes root") from exc
        return uri, path

    def save_stream(
        self,
        stream: BinaryIO,
        destination_uri: str,
        *,
        display_path: str | None = None,
    ) -> StorageObject:
        uri, path = self._resolve(destination_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        digest = hashlib.sha256()
        size = 0
        try:
            with temp_path.open("wb") as destination:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        return StorageObject(
            backend_name=self.backend_name,
            uri=uri,
            display_path=display_path or str(path),
            object_type=StorageObjectType.file,
            size_bytes=size,
            checksum=digest.hexdigest(),
            created_at=datetime.now().replace(microsecond=0),
        )

    def create_folder(self, destination_uri: str, *, display_path: str | None = None) -> StorageObject:
        uri, path = self._resolve(destination_uri)
        path.mkdir(parents=True, exist_ok=True)
        return StorageObject(
            backend_name=self.backend_name,
            uri=uri,
            display_path=display_path or str(path),
            object_type=StorageObjectType.folder,
            created_at=datetime.now().replace(microsecond=0),
        )

    def delete_object(self, uri: str) -> None:
        _, path = self._resolve(uri)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    def get_display_path(self, uri: str) -> str:
        _, path = self._resolve(uri)
        return str(path)
