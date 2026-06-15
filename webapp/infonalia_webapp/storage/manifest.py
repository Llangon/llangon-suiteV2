from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable


LOCAL_DROPBOX_MANIFEST_PREFIX = ".infonalia_dropbox_manifest_"
LOCAL_DROPBOX_MANIFEST_SUFFIX = ".json"
LOCAL_DOWNLOAD_MANIFEST = ".infonalia_manifest.json"


def is_internal_download_file_name(name: str) -> bool:
    return name == LOCAL_DOWNLOAD_MANIFEST or (
        name.startswith(LOCAL_DROPBOX_MANIFEST_PREFIX) and name.endswith(LOCAL_DROPBOX_MANIFEST_SUFFIX)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def iter_manifest_files(folder: Path) -> Iterable[tuple[Path, str]]:
    folder_path = Path(folder).resolve()
    for item in sorted(folder_path.rglob("*")):
        if not item.is_file() or is_internal_download_file_name(item.name):
            continue
        relative = PurePosixPath(*item.resolve().relative_to(folder_path).parts).as_posix()
        yield item, relative


def safe_manifest_timestamp(value: str | None = None) -> str:
    text = value or datetime.now().replace(microsecond=0).isoformat()
    return text.replace("-", "").replace(":", "").replace("T", "-").split(".")[0]


def write_dropbox_manifest_file(folder: Path, manifest: dict, created_at: str | None = None) -> Path:
    folder_path = Path(folder)
    timestamp = safe_manifest_timestamp(created_at or str(manifest.get("created_at") or ""))
    path = folder_path / f"{LOCAL_DROPBOX_MANIFEST_PREFIX}{timestamp}{LOCAL_DROPBOX_MANIFEST_SUFFIX}"
    suffix = 2
    while path.exists():
        path = folder_path / f"{LOCAL_DROPBOX_MANIFEST_PREFIX}{timestamp}_{suffix}{LOCAL_DROPBOX_MANIFEST_SUFFIX}"
        suffix += 1
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path

