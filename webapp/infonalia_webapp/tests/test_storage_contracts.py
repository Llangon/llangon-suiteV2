from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from webapp.infonalia_webapp.core.models import (
    StorageBackendName,
    StorageObject,
    StorageObjectType,
)
from webapp.infonalia_webapp.core.storage_contracts import StorageBackend


class FakeStorageBackend:
    backend_name = StorageBackendName.local

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def save_stream(
        self,
        stream: BinaryIO,
        destination_uri: str,
        *,
        display_path: str | None = None,
    ) -> StorageObject:
        size = len(stream.read())
        return StorageObject(
            backend_name=self.backend_name,
            uri=destination_uri,
            display_path=display_path or destination_uri,
            object_type=StorageObjectType.file,
            size_bytes=size,
        )

    def create_folder(self, destination_uri: str, *, display_path: str | None = None) -> StorageObject:
        return StorageObject(
            backend_name=self.backend_name,
            uri=destination_uri,
            display_path=display_path or destination_uri,
            object_type=StorageObjectType.folder,
        )

    def delete_object(self, uri: str) -> None:
        self.deleted.append(uri)

    def get_display_path(self, uri: str) -> str:
        return f"display:{uri}"


def test_storage_backend_protocol_can_be_used_with_fake_backend() -> None:
    backend: StorageBackend = FakeStorageBackend()

    stored_file = backend.save_stream(BytesIO(b"abc"), "local://expediente/documento.pdf")
    folder = backend.create_folder("local://expediente")
    backend.delete_object(stored_file.uri)

    assert isinstance(backend, StorageBackend)
    assert stored_file.size_bytes == 3
    assert stored_file.object_type is StorageObjectType.file
    assert folder.object_type is StorageObjectType.folder
    assert backend.get_display_path(folder.uri) == "display:local://expediente"
