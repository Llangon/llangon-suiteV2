"""Persistencia y migración del estado técnico de preguntas (esquema v2)."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .corporate_document import CORPORATE_DOCUMENT
from .question_models import (
    QuestionStateError,
    content_hash,
    extract_platform_datetime,
    iso_datetime,
    literal_text,
    normalize_label,
    normalized_key,
)
from .safe_files import atomic_write_json, mark_hidden

STATE_DIRECTORY_NAME = ".llangon-place"
STATE_FILE_NAME = "questions_state.json"
TRANSACTION_FILE_NAME = "pending_transaction.json"
STATE_BACKUP_FILE_NAME = "questions_state.pre_schema_2.json"
STATE_SCHEMA_VERSION = 2
OUTPUT_PREFIX = CORPORATE_DOCUMENT.output_prefix


@dataclass(frozen=True)
class QuestionStateLayout:
    """Ubicación y compatibilidad de un estado técnico de plataforma."""

    directory_name: str = STATE_DIRECTORY_NAME
    state_file_name: str = STATE_FILE_NAME
    transaction_file_name: str = TRANSACTION_FILE_NAME
    backup_file_name: str = STATE_BACKUP_FILE_NAME
    platform: str = "PLACE"
    source_id_key: str = "place_source_id"
    inventory_legacy_rtf: bool = True


PLACE_STATE_LAYOUT = QuestionStateLayout()


def state_directory(
    destination: Path,
    *,
    create: bool = False,
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> Path:
    path = destination / layout.directory_name
    if create:
        path.mkdir(parents=True, exist_ok=True)
        mark_hidden(path)
    return path


def state_file(destination: Path, *, layout: QuestionStateLayout = PLACE_STATE_LAYOUT) -> Path:
    return state_directory(destination, layout=layout) / layout.state_file_name


def transaction_file(destination: Path, *, layout: QuestionStateLayout = PLACE_STATE_LAYOUT) -> Path:
    return state_directory(destination, layout=layout) / layout.transaction_file_name


def _empty_state(
    profile_url: str,
    metadata: dict[str, str],
    *,
    platform: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "platform": platform or str(metadata.get("platform") or ""),
        "profile_url": profile_url or metadata.get("url", ""),
        "metadata": dict(metadata),
        "next_question_number": 1,
        "last_successful_review": "",
        "last_complete_snapshot": {},
        "last_result": {},
        "questions": {},
        "change_events": [],
        "legacy_revisions": [],
        "migration": {},
    }


def _validate_state(state: object) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise QuestionStateError("El estado técnico de preguntas no tiene un formato válido.")
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise QuestionStateError("La versión del estado técnico de preguntas no es compatible.")
    if (
        not isinstance(state.get("questions"), dict)
        or not isinstance(state.get("change_events"), list)
        or not isinstance(state.get("last_complete_snapshot"), dict)
    ):
        raise QuestionStateError("El estado técnico de preguntas está incompleto.")
    return state


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionStateError(f"No se pudo leer el estado técnico «{path.name}».") from exc
    if not isinstance(payload, dict):
        raise QuestionStateError(f"El archivo técnico «{path.name}» no contiene un objeto válido.")
    return payload


def _version_fingerprint(
    question_hash: str,
    answer_hash: str,
    attachments_hash: str,
) -> str:
    material = f"{question_hash}\n{answer_hash}\n{attachments_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _legacy_change_fields(change_type: object) -> list[str]:
    normalized = normalize_label(change_type)
    if normalized == "question updated":
        return ["question"]
    if normalized == "response updated":
        return ["answer"]
    return []


def _legacy_version(
    *,
    version_number: int,
    detected_at: str,
    question: object,
    answer: object,
    attachments: Iterable[dict[str, Any]],
    change_type: str,
    changed_fields: Iterable[str],
) -> dict[str, Any]:
    question_text = literal_text(question)
    answer_text = literal_text(answer)
    attachments_list = [dict(item) for item in attachments]
    question_hash = content_hash(question_text)
    answer_hash = content_hash(answer_text)
    attachments_hash = hashlib.sha256(
        "\n".join(
            sorted(
                "\n".join(
                    tuple(
                        part
                        for part in (
                            normalized_key(item.get("name")),
                            normalized_key(item.get("url")),
                            normalized_key(item.get("source_id")),
                            (
                                normalize_label(item.get("role"))
                                if normalize_label(item.get("role")) not in {"", "entry"}
                                else ""
                            ),
                        )
                        if part
                    )
                )
                for item in attachments_list
            )
        ).encode("utf-8")
    ).hexdigest()
    return {
        "version": version_number,
        "detected_at": detected_at,
        "question": question_text,
        "answer": answer_text,
        "question_hash": question_hash,
        "answer_hash": answer_hash,
        "attachments": attachments_list,
        "attachments_hash": attachments_hash,
        "fingerprint": _version_fingerprint(question_hash, answer_hash, attachments_hash),
        "changed_fields": list(changed_fields),
        "change_type": change_type,
    }


def _migrate_state_v1_to_v2(state: dict[str, Any]) -> dict[str, Any]:
    migrated = _empty_state(
        str(state.get("profile_url") or ""),
        dict(state.get("metadata") or {}),
        platform=str(state.get("platform") or "PLACE"),
    )
    migrated["next_question_number"] = int(state.get("next_question_number") or 1)
    migrated["last_successful_review"] = str(state.get("last_successful_review") or "")
    migrated["last_result"] = copy.deepcopy(state.get("last_result") or {})
    migrated["legacy_revisions"] = copy.deepcopy(state.get("revisions") or [])
    migrated["migration"] = copy.deepcopy(state.get("migration") or {})
    migrated["migration"].update(
        {
            "schema_from": 1,
            "schema_to": STATE_SCHEMA_VERSION,
            "visual_grouping_removed": True,
        }
    )
    revisions = list(state.get("revisions") or [])
    for stable_id, legacy in (state.get("questions") or {}).items():
        snapshots: list[dict[str, Any]] = []
        official_datetime = ""
        for revision in revisions:
            for entry in revision.get("entries") or []:
                if entry.get("stable_id") != stable_id:
                    continue
                official_datetime = official_datetime or extract_platform_datetime(
                    entry.get("asked_at") or entry.get("updated_at")
                )
                candidate = _legacy_version(
                    version_number=len(snapshots) + 1,
                    detected_at=str(revision.get("reviewed_at") or legacy.get("first_seen") or ""),
                    question=entry.get("question", ""),
                    answer=entry.get("answer", ""),
                    attachments=entry.get("attachments") or [],
                    change_type=(
                        "initial"
                        if not snapshots
                        else str(entry.get("change_type") or "content_modified")
                    ),
                    changed_fields=_legacy_change_fields(entry.get("change_type")),
                )
                if not snapshots or snapshots[-1]["fingerprint"] != candidate["fingerprint"]:
                    snapshots.append(candidate)
        current_candidate = _legacy_version(
            version_number=len(snapshots) + 1,
            detected_at=str(legacy.get("last_seen") or legacy.get("first_seen") or ""),
            question=legacy.get("question", ""),
            answer=legacy.get("answer", ""),
            attachments=legacy.get("attachments") or [],
            change_type="content_modified" if snapshots else "initial",
            changed_fields=[],
        )
        if not snapshots or snapshots[-1]["fingerprint"] != current_candidate["fingerprint"]:
            snapshots.append(current_candidate)
        for index, version in enumerate(snapshots, start=1):
            version["version"] = index
        official_datetime = (
            official_datetime
            or extract_platform_datetime(legacy.get("asked_at"))
            or extract_platform_datetime(legacy.get("updated_at"))
        )
        migrated["questions"][stable_id] = {
            "stable_id": stable_id,
            "place_source_id": str(legacy.get("place_source_id") or ""),
            "number": int(legacy.get("number") or 0),
            "official_datetime": official_datetime,
            "question": literal_text(legacy.get("question")),
            "question_hash": content_hash(legacy.get("question")),
            "answer": literal_text(legacy.get("answer")),
            "answer_hash": content_hash(legacy.get("answer")),
            "attachments": copy.deepcopy(legacy.get("attachments") or []),
            "attachments_hash": str(legacy.get("attachments_hash") or snapshots[-1]["attachments_hash"]),
            "status": str(legacy.get("status") or ""),
            "versions": snapshots,
            "first_seen": str(legacy.get("first_seen") or ""),
            "last_seen": str(legacy.get("last_seen") or ""),
            "published": True,
            "unpublished_at": "",
            "reappeared_at": "",
            "publication_history": [],
            "last_change_type": str(snapshots[-1].get("change_type") or "initial"),
            "last_change_at": str(snapshots[-1].get("detected_at") or ""),
        }
    snapshot_ids = sorted(migrated["questions"])
    migrated["last_complete_snapshot"] = {
        "reviewed_at": migrated["last_successful_review"],
        "question_ids": snapshot_ids,
        "total_questions": len(snapshot_ids),
        "fingerprint": hashlib.sha256("\n".join(snapshot_ids).encode("utf-8")).hexdigest(),
    }
    return migrated


def _backup_state_before_migration(
    destination: Path,
    state: dict[str, Any],
    *,
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> Path:
    directory = state_directory(destination, create=True, layout=layout)
    backup = directory / layout.backup_file_name
    if not backup.exists():
        atomic_write_json(backup, state)
    return backup


def legacy_rtf_inventory(destination: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(destination.glob(f"{OUTPUT_PREFIX}*.rtf"), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        inventory.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": iso_datetime(datetime.fromtimestamp(stat.st_mtime).astimezone()),
            }
        )
    return inventory


def load_state(
    destination: Path,
    *,
    profile_url: str = "",
    metadata: dict[str, str] | None = None,
    platform: str = "",
    layout: QuestionStateLayout = PLACE_STATE_LAYOUT,
) -> tuple[dict[str, Any], list[str]]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    path = state_file(destination, layout=layout)
    if path.is_file():
        raw_state = _read_json(path)
        if raw_state.get("schema_version") == 1:
            _backup_state_before_migration(destination, raw_state, layout=layout)
            warnings.append(
                "El estado técnico anterior se migró al listado cronológico único; se conservó una copia de seguridad."
            )
            return _validate_state(_migrate_state_v1_to_v2(raw_state)), warnings
        return _validate_state(raw_state), warnings
    state = _empty_state(
        profile_url,
        metadata or {},
        platform=platform or layout.platform,
    )
    legacy = legacy_rtf_inventory(destination) if layout.inventory_legacy_rtf else []
    if legacy:
        state["migration"] = {
            "mode": "fresh_structured_baseline",
            "legacy_rtf_files": legacy,
        }
        warnings.append(
            "Se conservaron los RTF anteriores como antecedente; esta revisión inicia el estado estructurado."
        )
    return state, warnings
