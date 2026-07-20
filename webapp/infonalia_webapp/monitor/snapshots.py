from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from herramientas_python.descargadores.common.safe_files import atomic_write_json, mark_hidden


SNAPSHOT_SCHEMA_VERSION = 1
TECHNICAL_DIRECTORY = ".llangon-monitor"
TECHNICAL_SNAPSHOT_FILE = "technical_snapshot.json"
STRUCTURED_RESULT_PREFIX = "RESULTADO_ESTRUCTURADO="
VOLATILE_QUERY_KEYS = {
    "_",
    "cache",
    "cachebuster",
    "expires",
    "nonce",
    "session",
    "sessionid",
    "sid",
    "sig",
    "signature",
    "timestamp",
    "token",
    "ts",
}
RELEVANT_GENERAL_FIELDS = {
    "budget",
    "contracting_authority",
    "contract_type",
    "estimated_value",
    "expediente",
    "lots",
    "organismo",
    "procedure",
    "procurement_status",
    "status",
    "tender_status",
    "title",
    "valor_estimado",
    "presupuesto",
}
RELEVANT_DATE_FIELDS = {
    "deadline",
    "fecha_fin_ofertas",
    "fecha_limite",
    "submission_deadline",
}


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_url(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if not parts.scheme or not parts.netloc:
        return text
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in VOLATILE_QUERY_KEYS
    ]
    query.sort(key=lambda item: (item[0].casefold(), item[1]))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _json_hash(value: object) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _clean_mapping(values: object, allowed_fields: set[str]) -> dict[str, object]:
    if not isinstance(values, Mapping):
        return {}
    result: dict[str, object] = {}
    for raw_key, raw_value in values.items():
        key = normalize_text(raw_key).casefold().replace(" ", "_")
        if key not in allowed_fields:
            continue
        if isinstance(raw_value, list):
            result[key] = sorted(normalize_text(item) for item in raw_value if normalize_text(item))
        elif isinstance(raw_value, Mapping):
            result[key] = {
                normalize_text(child_key): normalize_text(child_value)
                for child_key, child_value in sorted(raw_value.items(), key=lambda item: str(item[0]))
                if normalize_text(child_value)
            }
        else:
            result[key] = normalize_text(raw_value)
    return result


def _artifact_identity(item: Mapping[str, object]) -> str:
    role = normalize_text(item.get("role") or "document").casefold()
    source_url = canonical_url(item.get("source_url"))
    if source_url:
        return f"{role}:url:{source_url}"
    sha256 = normalize_text(item.get("sha256")).lower()
    name = normalize_text(item.get("name")).casefold()
    if sha256:
        return f"{role}:sha256:{sha256}"
    return f"{role}:name:{name}"


def _normalize_artifacts(values: object, destination: Path | None = None) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    if not isinstance(values, list):
        return result
    destination_resolved = destination.resolve(strict=False) if destination else None
    for raw in values:
        if not isinstance(raw, Mapping):
            continue
        item = {
            "name": normalize_text(raw.get("name")),
            "source_url": canonical_url(raw.get("source_url")),
            "sha256": normalize_text(raw.get("sha256")).lower(),
            "content_type": normalize_text(raw.get("content_type")).casefold(),
            "size": int(raw.get("size") or 0),
            "role": normalize_text(raw.get("role") or "document").casefold(),
            "published": True,
        }
        raw_path = normalize_text(raw.get("path"))
        if raw_path:
            candidate = Path(raw_path)
            if not candidate.is_absolute() and ".." not in candidate.parts:
                item["relative_path"] = candidate.as_posix()
            elif destination_resolved:
                try:
                    item["relative_path"] = candidate.resolve(strict=False).relative_to(destination_resolved).as_posix()
                except ValueError:
                    item["relative_path"] = ""
            else:
                item["relative_path"] = candidate.name
        identity = _artifact_identity(item)
        if identity.endswith(":name:"):
            continue
        existing = result.get(identity)
        if not existing or (not existing.get("sha256") and item.get("sha256")):
            result[identity] = item
    return dict(sorted(result.items()))


def _load_question_state(result: Mapping[str, object], destination: Path | None) -> dict[str, object]:
    raw_path = normalize_text(result.get("state_path"))
    if not raw_path:
        return {}
    path = Path(raw_path)
    if destination:
        try:
            path.resolve(strict=False).relative_to(destination.resolve(strict=False))
        except ValueError:
            return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_questions(state: Mapping[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    raw_questions = state.get("questions")
    if not isinstance(raw_questions, Mapping):
        return result
    for raw_key, raw in raw_questions.items():
        if not isinstance(raw, Mapping):
            continue
        stable_id = normalize_text(raw.get("stable_id") or raw_key)
        if not stable_id:
            continue
        versions = raw.get("versions") if isinstance(raw.get("versions"), list) else []
        latest = versions[-1] if versions and isinstance(versions[-1], Mapping) else {}
        status = normalize_text(raw.get("status") or "published").casefold()
        published = bool(raw.get("published", status not in {"removed", "withdrawn", "retirada"}))
        result[stable_id] = {
            "stable_id": stable_id,
            "number": int(raw.get("number") or 0),
            "question_hash": normalize_text(raw.get("question_hash") or latest.get("question_hash")),
            "answer_hash": normalize_text(raw.get("answer_hash") or latest.get("answer_hash")),
            "attachments_hash": normalize_text(raw.get("attachments_hash") or latest.get("attachments_hash")),
            "version_fingerprint": normalize_text(latest.get("fingerprint")),
            "official_datetime": normalize_text(raw.get("official_datetime")),
            "status": status,
            "published": published,
        }
    return dict(sorted(result.items()))


def snapshot_from_result(
    result: Mapping[str, object] | object,
    *,
    destination: Path | str | None = None,
    captured_at: str = "",
) -> dict[str, object]:
    payload = result.to_dict() if hasattr(result, "to_dict") else dict(result)  # type: ignore[arg-type]
    destination_path = Path(destination) if destination is not None else None
    status = normalize_text(payload.get("status")).casefold()
    successful = status in {"success", "success_with_warnings"}
    partial = status == "partial"
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), Mapping) else {}
    supports_questions = bool(capabilities.get("questions_and_answers"))
    question_result = payload.get("questions") if isinstance(payload.get("questions"), Mapping) else {}
    question_state = _load_question_state(payload, destination_path)
    question_complete = bool(
        supports_questions
        and question_result.get("query_successful")
        and question_result.get("snapshot_complete")
    )

    general = _clean_mapping(payload.get("general_data"), RELEVANT_GENERAL_FIELDS)
    dates = _clean_mapping(payload.get("relevant_dates"), RELEVANT_DATE_FIELDS)
    documents = _normalize_artifacts(payload.get("artifacts"), destination_path)
    questions = _normalize_questions(question_state)
    block_status = "complete" if successful else ("partial" if partial else "invalid")
    snapshot: dict[str, object] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "platform": normalize_text(payload.get("platform")).upper(),
        "source_url": canonical_url(payload.get("source_url")),
        "tender_id": normalize_text(payload.get("tender_id")),
        "captured_at": captured_at or normalize_text(payload.get("finished_at")),
        "blocks": {
            "general": {"status": block_status if general else "not_available", "data": general},
            "dates": {"status": block_status if dates else "not_available", "data": dates},
            "documents": {"status": block_status, "items": documents},
            "questions": {
                "status": "not_applicable" if not supports_questions else ("complete" if question_complete else "invalid"),
                "items": questions,
            },
        },
    }
    fingerprint_payload = deepcopy(snapshot)
    fingerprint_payload.pop("captured_at", None)
    snapshot["fingerprint"] = _json_hash(fingerprint_payload)
    return snapshot


def snapshot_completeness(snapshot: Mapping[str, object]) -> dict[str, str]:
    blocks = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), Mapping) else {}
    return {
        str(name): normalize_text(value.get("status")) if isinstance(value, Mapping) else "invalid"
        for name, value in blocks.items()
    }


def technical_snapshot_path(destination: Path | str) -> Path:
    return Path(destination) / TECHNICAL_DIRECTORY / TECHNICAL_SNAPSHOT_FILE


def read_technical_snapshot(destination: Path | str) -> dict[str, object] | None:
    path = technical_snapshot_path(destination)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 0) != SNAPSHOT_SCHEMA_VERSION:
        return None
    return payload


def write_technical_snapshot(destination: Path | str, snapshot: Mapping[str, object]) -> Path:
    path = technical_snapshot_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    mark_hidden(path.parent)
    atomic_write_json(path, dict(snapshot))
    return path


def parse_structured_result(output: object) -> dict[str, object] | None:
    for line in reversed(str(output or "").splitlines()):
        if not line.startswith(STRUCTURED_RESULT_PREFIX):
            continue
        try:
            payload = json.loads(line[len(STRUCTURED_RESULT_PREFIX) :])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def persist_normal_download_baseline(output: object, destination: Path | str) -> Path | None:
    result = parse_structured_result(output)
    if not result or normalize_text(result.get("status")).casefold() not in {"success", "success_with_warnings"}:
        return None
    snapshot = snapshot_from_result(result, destination=destination)
    return write_technical_snapshot(destination, snapshot)
