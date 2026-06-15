from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:
    from ..local_storage import local_uri_for_path
    from ..storage.dropbox_client import DropboxClientError, DropboxCredentials, DropboxHttpClient
    from ..storage.dropbox_incremental import (
        DropboxIncrementalStorage,
        DropboxStorageError,
        MODE,
        normalize_dropbox_root,
    )
except ImportError:
    from local_storage import local_uri_for_path
    from storage.dropbox_client import DropboxClientError, DropboxCredentials, DropboxHttpClient
    from storage.dropbox_incremental import DropboxIncrementalStorage, DropboxStorageError, MODE, normalize_dropbox_root


class StorageConfigurationError(ValueError):
    """Raised when storage configuration is incomplete or invalid."""


def _bool_env(value: object, default: bool = False) -> bool:
    text = str(value if value is not None else "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "si", "sí"}


@dataclass(frozen=True)
class StorageConfig:
    backend: str
    dropbox_enabled: bool
    dry_run: bool
    root: str
    non_destructive: bool
    app_key: str
    app_secret: str
    refresh_token: str

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret and self.refresh_token)

    def safe_payload(self) -> dict:
        warnings = []
        if self.backend == "dropbox" and not self.dropbox_enabled:
            warnings.append("Dropbox esta seleccionado como backend, pero INFONALIA_DROPBOX_ENABLED no esta activo.")
        if self.dropbox_enabled and not self.configured:
            warnings.append("Dropbox esta activo, pero faltan credenciales.")
        if self.dry_run:
            warnings.append("Dropbox dry-run activo: no se subiran archivos reales.")
        return {
            "backend": self.backend,
            "dropbox_enabled": self.dropbox_enabled,
            "dry_run": self.dry_run,
            "root": self.root,
            "non_destructive": self.non_destructive,
            "configured": self.configured,
            "mode": MODE,
            "warnings": warnings,
        }

    def validate_for_real_dropbox(self) -> None:
        if self.backend != "dropbox":
            return
        if not self.dropbox_enabled:
            raise StorageConfigurationError("Dropbox no esta activado.")
        if not self.dry_run and not self.configured:
            raise StorageConfigurationError(
                "Dropbox esta activo sin dry-run, pero faltan credenciales: "
                "INFONALIA_DROPBOX_APP_KEY, INFONALIA_DROPBOX_APP_SECRET e INFONALIA_DROPBOX_REFRESH_TOKEN."
            )


def remote_root_from_env(environ: Mapping[str, str]) -> str:
    explicit = (
        environ.get("INFONALIA_DROPBOX_API_ROOT")
        or environ.get("INFONALIA_DROPBOX_REMOTE_ROOT")
        or ""
    ).strip()
    if explicit:
        return normalize_dropbox_root(explicit)

    legacy = str(environ.get("INFONALIA_DROPBOX_ROOT") or "").strip()
    if legacy.startswith("/") and "\\" not in legacy and ":" not in legacy:
        return normalize_dropbox_root(legacy)
    return "/LlangonSuite"


def storage_config_from_env(environ: Mapping[str, str] | None = None) -> StorageConfig:
    env = environ or os.environ
    backend = str(env.get("INFONALIA_STORAGE_BACKEND") or "local").strip().lower() or "local"
    if backend not in {"local", "dropbox"}:
        raise StorageConfigurationError("INFONALIA_STORAGE_BACKEND debe ser local o dropbox.")
    return StorageConfig(
        backend=backend,
        dropbox_enabled=_bool_env(env.get("INFONALIA_DROPBOX_ENABLED"), False),
        dry_run=_bool_env(env.get("INFONALIA_DROPBOX_DRY_RUN"), True),
        root=remote_root_from_env(env),
        non_destructive=True,
        app_key=str(env.get("INFONALIA_DROPBOX_APP_KEY") or "").strip(),
        app_secret=str(env.get("INFONALIA_DROPBOX_APP_SECRET") or "").strip(),
        refresh_token=str(env.get("INFONALIA_DROPBOX_REFRESH_TOKEN") or "").strip(),
    )


def storage_status_payload(environ: Mapping[str, str] | None = None) -> dict:
    return storage_config_from_env(environ).safe_payload()


def test_dropbox_configuration(environ: Mapping[str, str] | None = None) -> dict:
    config = storage_config_from_env(environ)
    payload = config.safe_payload()
    payload["ok"] = True
    payload["network_checked"] = False
    if config.backend != "dropbox" or not config.dropbox_enabled or config.dry_run:
        payload["message"] = "Configuracion Dropbox validada en modo seguro sin red."
        return payload
    config.validate_for_real_dropbox()
    payload["message"] = "Credenciales Dropbox presentes. No se ha subido ningun archivo."
    return payload


def simulate_dropbox_dry_run(environ: Mapping[str, str] | None = None) -> dict:
    config = storage_config_from_env(environ)
    storage = DropboxIncrementalStorage(root=config.root, dry_run=True)
    destination = storage.stable_licitation_folder("SIMULACION-DROPBOX", 0)
    file_path = f"{destination}/documento-ficticio.pdf"
    return {
        "ok": True,
        "backend": "dropbox",
        "dry_run": True,
        "mode": MODE,
        "root_path": config.root,
        "destination_path": destination,
        "folder_status": "would_create_folder",
        "files": [
            {
                "local_path_relative": "documento-ficticio.pdf",
                "dropbox_path": file_path,
                "size_bytes": 0,
                "checksum": "",
                "status": "dry_run_upload",
                "error": "",
            }
        ],
        "total_files": 1,
        "uploaded_count": 0,
        "skipped_existing_count": 0,
        "failed_count": 0,
        "would_upload_count": 1,
        "no_changes": False,
        "warnings": ["Dropbox dry-run: no se han subido archivos reales."],
    }


def _local_storage_result(local_storage_root: Path, local_folder: Path, local_manifest_uri: str) -> dict:
    storage_uri = local_uri_for_path(local_storage_root, local_folder)
    return {
        "backend": "local",
        "dry_run": False,
        "mode": "local_manifest",
        "storage_uri": storage_uri,
        "storage_display_path": str(local_folder),
        "manifest_uri": local_manifest_uri,
        "manifest_local_path": str(local_folder / ".infonalia_manifest.json"),
        "job_status": "completed",
        "uploaded_count": 0,
        "skipped_existing_count": 0,
        "failed_count": 0,
        "would_upload_count": 0,
        "no_changes": False,
        "warnings": [],
        "errors": [],
    }


def finalize_download_storage(
    *,
    local_storage_root: Path,
    local_folder: Path,
    local_manifest_uri: str,
    licitacion_id: int,
    expediente: object,
    source_url: str = "",
    environ: Mapping[str, str] | None = None,
) -> dict:
    config = storage_config_from_env(environ)
    if config.backend != "dropbox":
        return _local_storage_result(local_storage_root, local_folder, local_manifest_uri)

    config.validate_for_real_dropbox()
    client = None
    if not config.dry_run:
        client = DropboxHttpClient(
            DropboxCredentials(
                app_key=config.app_key,
                app_secret=config.app_secret,
                refresh_token=config.refresh_token,
            )
        )
    storage = DropboxIncrementalStorage(client=client, root=config.root, dry_run=config.dry_run)
    try:
        return storage.sync_folder(
            Path(local_folder),
            licitacion_id=licitacion_id,
            expediente=expediente,
            source_url=source_url,
        ).to_dict()
    except DropboxClientError as exc:
        raise DropboxStorageError(str(exc)) from exc
