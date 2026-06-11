"""Pure contracts for future storage backends."""

from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from .models import StorageBackendName, StorageObject


@runtime_checkable
class StorageBackend(Protocol):
    """Conceptual storage backend for downloaded objects."""

    backend_name: StorageBackendName

    def save_stream(
        self,
        stream: BinaryIO,
        destination_uri: str,
        *,
        display_path: str | None = None,
    ) -> StorageObject:
        """Save a stream and return the resulting storage object."""

    def create_folder(self, destination_uri: str, *, display_path: str | None = None) -> StorageObject:
        """Create or represent a folder in the backend."""

    def delete_object(self, uri: str) -> None:
        """Delete or mark an object for removal in the backend."""

    def get_display_path(self, uri: str) -> str:
        """Return a human-readable path for a backend URI."""

