from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO

try:
    from .core.models import StorageBackendName, StorageObject, StorageObjectType
except ImportError:
    from core.models import StorageBackendName, StorageObject, StorageObjectType


MANIFEST_FILENAME = ".infonalia_manifest.json"


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


def local_uri_for_path(root: Path | str, path: Path | str) -> str:
    root_path = Path(root).resolve()
    target_path = Path(path).resolve()
    try:
        relative = target_path.relative_to(root_path)
    except ValueError as exc:
        raise LocalStorageError("Local path escapes storage root") from exc
    if not relative.parts:
        raise LocalStorageError("Local storage URI cannot point to root")
    return f"local://{PurePosixPath(*relative.parts).as_posix()}"


def file_storage_object(root: Path | str, path: Path | str) -> StorageObject:
    target_path = Path(path)
    digest = hashlib.sha256(target_path.read_bytes()).hexdigest()
    return StorageObject(
        backend_name=StorageBackendName.local,
        uri=local_uri_for_path(root, target_path),
        display_path=str(target_path),
        object_type=StorageObjectType.file,
        size_bytes=target_path.stat().st_size,
        checksum=digest,
    )


def build_local_manifest(
    root: Path | str,
    folder: Path | str,
    *,
    source_url: str = "",
    generated_at: Callable[[], str] | None = None,
) -> dict:
    root_path = Path(root).resolve()
    folder_path = Path(folder).resolve()
    local_uri_for_path(root_path, folder_path / MANIFEST_FILENAME)
    timestamp = generated_at() if generated_at else datetime.now().replace(microsecond=0).isoformat()
    files = []

    for item in sorted(folder_path.rglob("*")):
        if not item.is_file() or item.name == MANIFEST_FILENAME:
            continue
        stored = file_storage_object(root_path, item)
        relative = PurePosixPath(*item.resolve().relative_to(folder_path).parts).as_posix()
        files.append(
            {
                "path": relative,
                "uri": stored.uri,
                "size_bytes": stored.size_bytes,
                "checksum": stored.checksum,
            }
        )

    return {
        "schema": "infonalia.download_manifest.v1",
        "backend": StorageBackendName.local.value,
        "folder_uri": local_uri_for_path(root_path, folder_path),
        "display_path": str(folder_path),
        "source_url": source_url,
        "generated_at": timestamp,
        "files": files,
    }


def write_local_manifest(
    root: Path | str,
    folder: Path | str,
    *,
    source_url: str = "",
    generated_at: Callable[[], str] | None = None,
) -> StorageObject:
    manifest = build_local_manifest(root, folder, source_url=source_url, generated_at=generated_at)
    content = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest_uri = local_uri_for_path(root, Path(folder) / MANIFEST_FILENAME)
    return LocalStorageBackend(root).save_stream(BytesIO(content), manifest_uri)
