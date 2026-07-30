"""Memoria técnica, local y segura del inventario descargado de Xunta."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ..common.safe_files import atomic_write_json, ensure_safe_child, mark_hidden, sha256_file
from .client import DownloadDescriptor


STATE_SCHEMA_VERSION = 1
TECHNICAL_DIRECTORY = ".llangon-xunta"
STATE_FILENAME = "documents_state.json"


def state_path(destination: Path | str) -> Path:
    return Path(destination) / TECHNICAL_DIRECTORY / STATE_FILENAME


def empty_state(*, tender_id: str, source_url: str) -> dict[str, object]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "platform": "XUNTA_DE_GALICIA",
        "tender_id": tender_id,
        "source_url": source_url,
        "documents": {},
        "last_complete_keys": [],
        "last_complete_inventory_fingerprint": "",
        "last_run_complete": False,
        "last_run_at": "",
        "last_issues": [],
    }


def load_state(
    destination: Path | str,
    *,
    tender_id: str,
    source_url: str,
) -> tuple[dict[str, object], list[str]]:
    path = state_path(destination)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty_state(tender_id=tender_id, source_url=source_url), []
    except (OSError, json.JSONDecodeError):
        return (
            empty_state(tender_id=tender_id, source_url=source_url),
            ["El estado técnico de Xunta no es legible; se reconstruirá sin borrar documentos."],
        )
    if (
        not isinstance(payload, dict)
        or int(payload.get("schema_version") or 0) != STATE_SCHEMA_VERSION
        or str(payload.get("tender_id") or "") != tender_id
        or not isinstance(payload.get("documents"), dict)
    ):
        return (
            empty_state(tender_id=tender_id, source_url=source_url),
            ["El estado técnico de Xunta no es compatible; se reconstruirá sin borrar documentos."],
        )
    return payload, []


def record_for_descriptor(
    descriptor: DownloadDescriptor,
    *,
    destination: Path,
    path: Path,
    sha256: str,
    content_type: str,
    size: int,
) -> dict[str, object]:
    relative_path = path.resolve(strict=False).relative_to(destination.resolve(strict=False)).as_posix()
    return {
        "source_url": descriptor.source_url,
        "call": descriptor.call,
        "descriptor_fingerprint": descriptor.fingerprint,
        "title": descriptor.title,
        "published_at": descriptor.published_at,
        "remote_status": descriptor.remote_status,
        "extension": descriptor.extension,
        "declared_size": descriptor.declared_size,
        "section": descriptor.section,
        "relative_path": relative_path,
        "sha256": sha256,
        "content_type": content_type,
        "size": size,
    }


def reusable_record(
    record: object,
    descriptor: DownloadDescriptor,
    *,
    destination: Path,
) -> tuple[dict[str, object], Path] | None:
    if not isinstance(record, Mapping):
        return None
    if str(record.get("descriptor_fingerprint") or "") != descriptor.fingerprint:
        return None
    relative_text = str(record.get("relative_path") or "").strip()
    expected_hash = str(record.get("sha256") or "").strip().lower()
    if not relative_text or not expected_hash:
        return None
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    try:
        path = ensure_safe_child(destination, destination / relative)
    except Exception:
        return None
    if not path.is_file() or sha256_file(path).lower() != expected_hash:
        return None
    return dict(record), path


def save_state(destination: Path | str, payload: dict[str, object]) -> Path:
    path = state_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    mark_hidden(path.parent)
    atomic_write_json(path, payload)
    return path
