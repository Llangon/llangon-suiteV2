from __future__ import annotations

import hashlib
import importlib
import sys
from io import BytesIO

import pytest

from webapp.infonalia_webapp.core.models import StorageBackendName, StorageObjectType
from webapp.infonalia_webapp.core.storage_contracts import StorageBackend
from webapp.infonalia_webapp.local_storage import LocalStorageBackend, LocalStorageError


def test_local_storage_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.local_storage", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.local_storage")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"requests", "http.server", "socketserver", "subprocess", "smtplib"} & added


def test_local_storage_backend_satisfies_contract_and_saves_stream(tmp_path) -> None:
    backend: StorageBackend = LocalStorageBackend(tmp_path)

    stored = backend.save_stream(BytesIO(b"abc"), "local://expediente/documento.txt")

    saved_path = tmp_path / "expediente" / "documento.txt"
    assert isinstance(backend, StorageBackend)
    assert saved_path.read_bytes() == b"abc"
    assert stored.backend_name is StorageBackendName.local
    assert stored.uri == "local://expediente/documento.txt"
    assert stored.object_type is StorageObjectType.file
    assert stored.size_bytes == 3
    assert stored.checksum == hashlib.sha256(b"abc").hexdigest()


def test_local_storage_creates_folder_and_display_path(tmp_path) -> None:
    backend = LocalStorageBackend(tmp_path)

    folder = backend.create_folder("local://expediente/anexos")

    assert (tmp_path / "expediente" / "anexos").is_dir()
    assert folder.uri == "local://expediente/anexos"
    assert folder.object_type is StorageObjectType.folder
    assert backend.get_display_path(folder.uri) == str(tmp_path / "expediente" / "anexos")


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "../fuera.txt",
        "local://../fuera.txt",
        "local://expediente/../fuera.txt",
        "C:/temp/fuera.txt",
    ],
)
def test_local_storage_rejects_unsafe_uris(tmp_path, uri: str) -> None:
    backend = LocalStorageBackend(tmp_path)

    with pytest.raises(LocalStorageError):
        backend.save_stream(BytesIO(b"abc"), uri)


def test_local_storage_delete_object_stays_inside_root(tmp_path) -> None:
    backend = LocalStorageBackend(tmp_path)
    backend.save_stream(BytesIO(b"abc"), "local://expediente/documento.txt")
    backend.create_folder("local://expediente/anexos")
    (tmp_path / "expediente" / "anexos" / "extra.txt").write_text("x", encoding="utf-8")

    backend.delete_object("local://expediente")

    assert not (tmp_path / "expediente").exists()
