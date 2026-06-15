from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Callable

from .base import DropboxClientProtocol
from .manifest import iter_manifest_files, sha256_file, write_dropbox_manifest_file


MODE = "incremental_non_destructive"


class DropboxStorageError(RuntimeError):
    """Raised when Dropbox incremental storage cannot complete safely."""


def normalize_dropbox_root(root: str | None) -> str:
    text = str(root or "/LlangonSuite").strip().replace("\\", "/")
    if not text:
        text = "/LlangonSuite"
    if not text.startswith("/"):
        text = f"/{text}"
    return "/" + "/".join(part for part in text.split("/") if part)


def sanitize_dropbox_segment(value: object, *, fallback: str = "SIN_NOMBRE") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\\/:\*\?\"<>\|\x00-\x1f]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip(" ._")
    if text in {"", ".", ".."}:
        return fallback
    return text[:120]


def safe_dropbox_path_join(*parts: str) -> str:
    clean_parts = []
    for part in parts:
        text = str(part or "").replace("\\", "/")
        for piece in text.split("/"):
            if not piece:
                continue
            if piece in {".", ".."}:
                raise DropboxStorageError("Ruta Dropbox insegura.")
            clean_parts.append(piece)
    return "/" + "/".join(clean_parts)


def relative_dropbox_path(relative_path: str) -> str:
    text = str(relative_path or "").replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DropboxStorageError("Ruta relativa insegura.")
    return "/".join(sanitize_dropbox_segment(part, fallback="archivo") for part in path.parts)


@dataclass(frozen=True)
class DropboxSyncResult:
    backend: str
    dry_run: bool
    mode: str
    licitacion_id: int
    expediente: str
    root_path: str
    destination_path: str
    storage_uri: str
    storage_display_path: str
    manifest_local_path: str
    manifest_dropbox_path: str
    manifest_uri: str
    total_files: int
    uploaded_count: int
    skipped_existing_count: int
    failed_count: int
    would_upload_count: int
    total_bytes: int
    no_changes: bool
    files: list[dict]
    warnings: list[str]
    errors: list[str]
    folder_status: str
    created_at: str

    @property
    def job_status(self) -> str:
        if self.failed_count:
            return "partial" if self.uploaded_count or self.skipped_existing_count else "failed"
        return "completed"

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "licitacion_id": self.licitacion_id,
            "expediente": self.expediente,
            "root_path": self.root_path,
            "destination_path": self.destination_path,
            "storage_uri": self.storage_uri,
            "storage_display_path": self.storage_display_path,
            "manifest_local_path": self.manifest_local_path,
            "manifest_dropbox_path": self.manifest_dropbox_path,
            "manifest_uri": self.manifest_uri,
            "total_files": self.total_files,
            "uploaded_count": self.uploaded_count,
            "skipped_existing_count": self.skipped_existing_count,
            "failed_count": self.failed_count,
            "would_upload_count": self.would_upload_count,
            "total_bytes": self.total_bytes,
            "no_changes": self.no_changes,
            "files": self.files,
            "warnings": self.warnings,
            "errors": self.errors,
            "folder_status": self.folder_status,
            "created_at": self.created_at,
            "job_status": self.job_status,
        }


class DropboxIncrementalStorage:
    """Incremental Dropbox writer that never deletes or overwrites."""

    backend = "dropbox"

    def __init__(
        self,
        *,
        client: DropboxClientProtocol | None = None,
        root: str = "/LlangonSuite",
        dry_run: bool = True,
        existing_paths: set[str] | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.client = client
        self.root = normalize_dropbox_root(root)
        self.dry_run = dry_run
        self.existing_paths = {normalize_dropbox_root(path) for path in (existing_paths or set())}
        self.now = now or (lambda: datetime.now().replace(microsecond=0).isoformat())

    def stable_licitation_folder(self, expediente: object, licitacion_id: int) -> str:
        safe_expediente = sanitize_dropbox_segment(expediente, fallback="SIN_EXPEDIENTE")
        return safe_dropbox_path_join(self.root, "Licitaciones", f"{safe_expediente}_{int(licitacion_id)}")

    def _exists(self, path: str) -> bool:
        normalized = normalize_dropbox_root(path)
        if self.dry_run:
            return normalized in self.existing_paths
        if not self.client:
            raise DropboxStorageError("Dropbox client is required when dry_run is disabled.")
        return self.client.path_exists(normalized)

    def _ensure_folder(self, path: str) -> str:
        if self.dry_run:
            return "would_reuse_existing" if self._exists(path) else "would_create_folder"
        if not self.client:
            raise DropboxStorageError("Dropbox client is required when dry_run is disabled.")
        result = self.client.ensure_folder(path)
        return str(result.get("status") or "unknown")

    def _upload_manifest(self, manifest: dict, manifests_folder: str, created_at: str) -> str:
        if self.dry_run:
            return ""
        if not self.client:
            raise DropboxStorageError("Dropbox client is required when dry_run is disabled.")
        content = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        timestamp = created_at.replace("-", "").replace(":", "").replace("T", "-").split(".")[0]
        for suffix in ["", *[f"_{index}" for index in range(2, 101)]]:
            remote_path = safe_dropbox_path_join(manifests_folder, f"manifest_{timestamp}{suffix}.json")
            if self.client.path_exists(remote_path):
                continue
            result = self.client.upload_stream_if_missing(BytesIO(content), remote_path)
            if result.get("status") == "uploaded":
                return remote_path
        raise DropboxStorageError("No se pudo crear un manifest Dropbox sin sobrescribir.")

    def sync_folder(
        self,
        local_folder: Path,
        *,
        licitacion_id: int,
        expediente: object,
        source_url: str = "",
    ) -> DropboxSyncResult:
        folder_path = Path(local_folder).resolve()
        if not folder_path.exists() or not folder_path.is_dir():
            raise DropboxStorageError("La carpeta local de descarga no existe.")

        created_at = self.now()
        destination_path = self.stable_licitation_folder(expediente, licitacion_id)
        manifests_folder = safe_dropbox_path_join(destination_path, "_manifests")
        warnings: list[str] = []
        errors: list[str] = []
        files: list[dict] = []
        total_bytes = 0
        uploaded_count = 0
        skipped_existing_count = 0
        failed_count = 0
        would_upload_count = 0

        if self.dry_run:
            warnings.append("Dropbox dry-run: no se han subido archivos reales.")

        folder_status = self._ensure_folder(destination_path)
        if not self.dry_run:
            self._ensure_folder(manifests_folder)

        for local_path, relative in iter_manifest_files(folder_path):
            size_bytes = local_path.stat().st_size
            checksum = sha256_file(local_path)
            total_bytes += size_bytes
            dropbox_path = safe_dropbox_path_join(destination_path, relative_dropbox_path(relative))
            item = {
                "local_path_relative": relative,
                "dropbox_path": dropbox_path,
                "size_bytes": size_bytes,
                "checksum": checksum,
                "status": "planned",
                "error": "",
            }

            try:
                if self.dry_run:
                    if self._exists(dropbox_path):
                        item["status"] = "dry_run_skip_existing"
                        skipped_existing_count += 1
                    else:
                        item["status"] = "dry_run_upload"
                        would_upload_count += 1
                    files.append(item)
                    continue

                if not self.client:
                    raise DropboxStorageError("Dropbox client is required when dry_run is disabled.")
                if self.client.path_exists(dropbox_path):
                    item["status"] = "skipped_existing"
                    skipped_existing_count += 1
                else:
                    result = self.client.upload_file_if_missing(local_path, dropbox_path)
                    status = str(result.get("status") or "")
                    item["status"] = status
                    item["upload_mode"] = result.get("upload_mode", "add")
                    item["autorename"] = bool(result.get("autorename", False))
                    if status == "uploaded":
                        uploaded_count += 1
                    elif status == "skipped_existing":
                        skipped_existing_count += 1
                    else:
                        failed_count += 1
                        item["error"] = f"Estado Dropbox inesperado: {status}"
                        errors.append(item["error"])
            except Exception as exc:
                failed_count += 1
                item["status"] = "failed"
                item["error"] = str(exc)
                errors.append(f"{relative}: {exc}")
            files.append(item)

        no_changes = failed_count == 0 and uploaded_count == 0 and would_upload_count == 0 and skipped_existing_count > 0
        manifest = {
            "schema": "infonalia.dropbox_manifest.v1",
            "backend": "dropbox",
            "dry_run": self.dry_run,
            "mode": MODE,
            "licitacion_id": licitacion_id,
            "expediente": str(expediente or ""),
            "created_at": created_at,
            "root_path": self.root,
            "destination_path": destination_path,
            "source_url": source_url,
            "files": files,
            "total_files": len(files),
            "uploaded_count": uploaded_count,
            "skipped_existing_count": skipped_existing_count,
            "failed_count": failed_count,
            "would_upload_count": would_upload_count,
            "total_bytes": total_bytes,
            "warnings": warnings,
            "errors": errors,
            "no_changes": no_changes,
        }
        manifest_local_path = write_dropbox_manifest_file(folder_path, manifest, created_at)
        manifest_dropbox_path = ""
        if not self.dry_run:
            manifest_dropbox_path = self._upload_manifest(manifest, manifests_folder, created_at)

        manifest_uri = (
            f"dropbox://{manifest_dropbox_path.lstrip('/')}"
            if manifest_dropbox_path
            else str(manifest_local_path)
        )
        return DropboxSyncResult(
            backend="dropbox",
            dry_run=self.dry_run,
            mode=MODE,
            licitacion_id=licitacion_id,
            expediente=str(expediente or ""),
            root_path=self.root,
            destination_path=destination_path,
            storage_uri=f"dropbox://{destination_path.lstrip('/')}",
            storage_display_path=destination_path,
            manifest_local_path=str(manifest_local_path),
            manifest_dropbox_path=manifest_dropbox_path,
            manifest_uri=manifest_uri,
            total_files=len(files),
            uploaded_count=uploaded_count,
            skipped_existing_count=skipped_existing_count,
            failed_count=failed_count,
            would_upload_count=would_upload_count,
            total_bytes=total_bytes,
            no_changes=no_changes,
            files=files,
            warnings=warnings,
            errors=errors,
            folder_status=folder_status,
            created_at=created_at,
        )
