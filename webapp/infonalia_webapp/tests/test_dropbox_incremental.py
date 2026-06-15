from __future__ import annotations

import json
from pathlib import Path

import pytest

from webapp.infonalia_webapp.storage.dropbox_incremental import (
    DropboxIncrementalStorage,
    DropboxStorageError,
)


class FakeDropboxClient:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = set(existing or set())
        self.uploads: list[dict] = []
        self.folders: list[str] = []
        self.destructive_calls: list[str] = []

    def path_exists(self, path: str) -> bool:
        return path in self.existing

    def ensure_folder(self, path: str) -> dict:
        self.folders.append(path)
        if path in self.existing:
            return {"status": "reused_existing", "path": path}
        self.existing.add(path)
        return {"status": "created", "path": path}

    def upload_file_if_missing(self, local_path: Path, dropbox_path: str) -> dict:
        if dropbox_path in self.existing:
            return {"status": "skipped_existing", "path": dropbox_path, "upload_mode": "add", "autorename": False}
        self.existing.add(dropbox_path)
        self.uploads.append(
            {
                "local_path": str(local_path),
                "dropbox_path": dropbox_path,
                "upload_mode": "add",
                "autorename": False,
            }
        )
        return {"status": "uploaded", "path": dropbox_path, "upload_mode": "add", "autorename": False}

    def upload_stream_if_missing(self, stream, dropbox_path: str) -> dict:
        if dropbox_path in self.existing:
            return {"status": "skipped_existing", "path": dropbox_path, "upload_mode": "add", "autorename": False}
        self.existing.add(dropbox_path)
        self.uploads.append(
            {
                "local_path": "<stream>",
                "dropbox_path": dropbox_path,
                "upload_mode": "add",
                "autorename": False,
            }
        )
        return {"status": "uploaded", "path": dropbox_path, "upload_mode": "add", "autorename": False}

    def get_metadata(self, path: str) -> dict:
        if path not in self.existing:
            raise FileNotFoundError(path)
        return {"path_display": path}

    def delete(self, path: str) -> None:
        self.destructive_calls.append(f"delete:{path}")
        raise AssertionError("delete must not be called")

    def overwrite(self, path: str) -> None:
        self.destructive_calls.append(f"overwrite:{path}")
        raise AssertionError("overwrite must not be called")

    def move_destructive(self, source: str, destination: str) -> None:
        self.destructive_calls.append(f"move:{source}->{destination}")
        raise AssertionError("move_destructive must not be called")


def make_folder(tmp_path: Path) -> Path:
    (tmp_path / "pliego.pdf").write_bytes(b"pliego")
    (tmp_path / "anexos.zip").write_bytes(b"anexos")
    (tmp_path / ".infonalia_manifest.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_dropbox_storage_has_no_functional_delete_or_overwrite_methods() -> None:
    storage = DropboxIncrementalStorage(dry_run=True)

    with pytest.raises(AttributeError):
        getattr(storage, "delete")
    with pytest.raises(AttributeError):
        getattr(storage, "overwrite")


def test_stable_licitation_folder_sanitizes_expediente_and_blocks_traversal() -> None:
    storage = DropboxIncrementalStorage(root="/LlangonSuite", dry_run=True)

    assert storage.stable_licitation_folder("EXP/2026:123", 42) == "/LlangonSuite/Licitaciones/EXP_2026_123_42"

    with pytest.raises(DropboxStorageError):
        storage.sync_folder(Path("/no/existe"), licitacion_id=1, expediente="../x")


def test_existing_remote_file_is_skipped_and_never_uploaded(tmp_path: Path) -> None:
    folder = make_folder(tmp_path)
    destination = "/LlangonSuite/Licitaciones/EXP_1"
    existing_file = f"{destination}/pliego.pdf"
    client = FakeDropboxClient(existing={destination, existing_file})
    storage = DropboxIncrementalStorage(
        client=client,
        root="/LlangonSuite",
        dry_run=False,
        now=lambda: "2026-06-14T10:00:00",
    )

    result = storage.sync_folder(folder, licitacion_id=1, expediente="EXP")
    payload = result.to_dict()

    assert payload["folder_status"] == "reused_existing"
    assert payload["skipped_existing_count"] == 1
    assert payload["uploaded_count"] == 1
    assert {item["status"] for item in payload["files"]} == {"skipped_existing", "uploaded"}
    assert [upload["dropbox_path"] for upload in client.uploads if upload["local_path"] != "<stream>"] == [
        f"{destination}/anexos.zip"
    ]
    assert all(upload["upload_mode"] == "add" for upload in client.uploads)
    assert all(upload["autorename"] is False for upload in client.uploads)
    assert client.destructive_calls == []


def test_retry_without_changes_uploads_no_documents_and_sets_no_changes(tmp_path: Path) -> None:
    folder = make_folder(tmp_path)
    destination = "/LlangonSuite/Licitaciones/EXP_1"
    client = FakeDropboxClient(
        existing={
            destination,
            f"{destination}/pliego.pdf",
            f"{destination}/anexos.zip",
        }
    )
    storage = DropboxIncrementalStorage(
        client=client,
        root="/LlangonSuite",
        dry_run=False,
        now=lambda: "2026-06-14T10:00:00",
    )

    result = storage.sync_folder(folder, licitacion_id=1, expediente="EXP").to_dict()

    document_uploads = [upload for upload in client.uploads if upload["local_path"] != "<stream>"]
    assert document_uploads == []
    assert result["uploaded_count"] == 0
    assert result["skipped_existing_count"] == 2
    assert result["no_changes"] is True


def test_retry_with_new_file_only_uploads_new_file(tmp_path: Path) -> None:
    folder = make_folder(tmp_path)
    (folder / "aclaracion.pdf").write_bytes(b"nueva")
    destination = "/LlangonSuite/Licitaciones/EXP_1"
    client = FakeDropboxClient(
        existing={
            destination,
            f"{destination}/pliego.pdf",
            f"{destination}/anexos.zip",
        }
    )
    storage = DropboxIncrementalStorage(
        client=client,
        root="/LlangonSuite",
        dry_run=False,
        now=lambda: "2026-06-14T10:00:00",
    )

    result = storage.sync_folder(folder, licitacion_id=1, expediente="EXP").to_dict()

    document_uploads = [upload for upload in client.uploads if upload["local_path"] != "<stream>"]
    assert [upload["dropbox_path"] for upload in document_uploads] == [f"{destination}/aclaracion.pdf"]
    assert result["uploaded_count"] == 1
    assert result["skipped_existing_count"] == 2
    assert result["no_changes"] is False


def test_dry_run_does_not_call_client_and_generates_manifest(tmp_path: Path) -> None:
    folder = make_folder(tmp_path)
    destination = "/LlangonSuite/Licitaciones/EXP_1"
    client = FakeDropboxClient(existing={f"{destination}/pliego.pdf"})
    storage = DropboxIncrementalStorage(
        client=client,
        root="/LlangonSuite",
        dry_run=True,
        existing_paths={f"{destination}/pliego.pdf"},
        now=lambda: "2026-06-14T10:00:00",
    )

    result = storage.sync_folder(folder, licitacion_id=1, expediente="EXP").to_dict()

    assert client.uploads == []
    assert client.folders == []
    assert result["dry_run"] is True
    assert result["would_upload_count"] == 1
    assert result["skipped_existing_count"] == 1
    assert result["folder_status"] == "would_create_folder"
    manifest_path = Path(result["manifest_local_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dry_run"] is True
    assert {item["status"] for item in manifest["files"]} == {"dry_run_upload", "dry_run_skip_existing"}

