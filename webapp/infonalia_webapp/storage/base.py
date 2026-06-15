from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class DropboxClientProtocol(Protocol):
    def path_exists(self, path: str) -> bool:
        """Return whether the Dropbox path already exists."""

    def ensure_folder(self, path: str) -> dict:
        """Create a folder if missing, or reuse it when it already exists."""

    def upload_file_if_missing(self, local_path: Path, dropbox_path: str) -> dict:
        """Upload a local file only when the remote path does not exist."""

    def upload_stream_if_missing(self, stream: BinaryIO, dropbox_path: str) -> dict:
        """Upload stream content only when the remote path does not exist."""

    def get_metadata(self, path: str) -> dict:
        """Return Dropbox metadata for a path."""

