"""Motor puro de comparación, identidad, numeración y versionado."""

from __future__ import annotations

import copy
import difflib
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .question_models import (
    PlatformQuestion,
    datetime_sort_value,
    extract_platform_datetime,
    iso_datetime,
    literal_text,
    normalize_text,
    normalized_key,
    parse_platform_datetime,
)
from .question_state import _version_fingerprint


@dataclass(frozen=True)
class PreparedQuestionSync:
    state: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    counts: dict[str, int]


def _question_identity_base(question: PlatformQuestion) -> str:
    if normalize_text(question.source_id):
        platform = normalized_key(question.platform) or "place"
        material = f"{platform}:{normalize_text(question.source_id)}"
    else:
        material = f"fingerprint:{question.question_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _unique_identity(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _question_match(
    incoming: PlatformQuestion,
    questions_state: dict[str, dict[str, Any]],
    claimed: set[str],
    source_id_key: str,
) -> str:
    source_id = normalize_text(incoming.source_id)
    if source_id:
        matches = [
            stable_id
            for stable_id, stored in questions_state.items()
            if stable_id not in claimed and _stored_source_id(stored, source_id_key) == source_id
        ]
        if len(matches) == 1:
            return matches[0]
    exact_hash = [
        stable_id
        for stable_id, stored in questions_state.items()
        if stable_id not in claimed and stored.get("question_hash") == incoming.question_hash
    ]
    if len(exact_hash) == 1:
        return exact_hash[0]
    incoming_date = incoming.official_datetime
    if incoming_date:
        same_date = [
            stable_id
            for stable_id, stored in questions_state.items()
            if stable_id not in claimed
            and extract_platform_datetime(stored.get("official_datetime") or stored.get("asked_at")) == incoming_date
        ]
        if len(same_date) == 1:
            return same_date[0]
    return ""


def _attachments_state(question: PlatformQuestion) -> list[dict[str, str]]:
    return [attachment.to_state() for attachment in question.attachments]


def _stored_source_id(stored: dict[str, Any], source_id_key: str) -> str:
    for key in (source_id_key, "source_id", "place_source_id"):
        value = normalize_text(stored.get(key))
        if value:
            return value
    return ""


def _metadata_state(question: PlatformQuestion) -> list[list[str]]:
    return [[literal_text(key), literal_text(value)] for key, value in question.metadata]


def _metadata_value(question: PlatformQuestion, key: str) -> str:
    wanted = normalized_key(key)
    for candidate, value in question.metadata:
        if normalized_key(candidate) == wanted:
            return literal_text(value)
    return ""


def _match_snapshot_question(
    incoming: PlatformQuestion,
    questions_state: dict[str, dict[str, Any]],
    claimed: set[str],
    source_id_key: str,
) -> str:
    exact = _question_match(incoming, questions_state, claimed, source_id_key)
    if exact:
        return exact
    if normalize_text(incoming.source_id):
        return ""
    if literal_text(incoming.answer):
        answer_matches = [
            stable_id
            for stable_id, stored in questions_state.items()
            if stable_id not in claimed
            and stored.get("answer_hash") == incoming.answer_hash
            and literal_text(stored.get("answer"))
        ]
        if len(answer_matches) == 1:
            return answer_matches[0]
    candidates: list[tuple[float, str]] = []
    incoming_key = normalized_key(incoming.question)
    for stable_id, stored in questions_state.items():
        if stable_id in claimed:
            continue
        ratio = difflib.SequenceMatcher(
            None,
            incoming_key,
            normalized_key(stored.get("question")),
            autojunk=False,
        ).ratio()
        candidates.append((ratio, stable_id))
    candidates.sort(reverse=True)
    if candidates and candidates[0][0] >= 0.72:
        if len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= 0.08:
            return candidates[0][1]
    return ""


def _snapshot_version(
    question: PlatformQuestion,
    *,
    version: int,
    detected_at: str,
    change_type: str,
    changed_fields: Iterable[str],
) -> dict[str, Any]:
    return {
        "version": version,
        "detected_at": detected_at,
        "question": question.question,
        "answer": question.answer,
        "question_hash": question.question_hash,
        "answer_hash": question.answer_hash,
        "attachments": _attachments_state(question),
        "attachments_hash": question.attachments_hash,
        "fingerprint": _version_fingerprint(
            question.question_hash,
            question.answer_hash,
            question.attachments_hash,
        ),
        "changed_fields": list(changed_fields),
        "change_type": change_type,
        "updated_at": question.updated_at,
        "asked_at": question.asked_at,
        "answered_at": question.answered_at,
        "source_url": question.source_url,
        "metadata": _metadata_state(question),
        "status": question.status,
    }


def _snapshot_fingerprint(
    questions: dict[str, dict[str, Any]],
    observed_ids: Iterable[str],
) -> str:
    rows = []
    for stable_id in sorted(observed_ids):
        stored = questions[stable_id]
        versions = stored.get("versions") or []
        current_fingerprint = versions[-1].get("fingerprint", "") if versions else ""
        rows.append(f"{stable_id}|{current_fingerprint}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _prepare_snapshot(
    state: dict[str, Any],
    metadata: dict[str, str],
    questions: list[PlatformQuestion],
    reviewed_at: datetime,
    *,
    source_id_key: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    new_state = copy.deepcopy(state)
    reviewed_iso = iso_datetime(reviewed_at)
    questions_state: dict[str, dict[str, Any]] = new_state["questions"]
    claimed: set[str] = set()
    events: list[dict[str, Any]] = []
    counts = {
        "incorporated": 0,
        "questions_modified": 0,
        "responses_modified": 0,
        "answers_incorporated": 0,
        "answers_removed": 0,
        "questions_removed": 0,
        "questions_restored": 0,
        "total": len(questions),
        "answered": sum(1 for item in questions if literal_text(item.answer)),
    }
    next_number = int(new_state.get("next_question_number") or 1)

    ordered_questions = sorted(
        questions,
        key=lambda item: (
            0 if datetime_sort_value(item.official_datetime) is not None else 1,
            datetime_sort_value(item.official_datetime) or float("inf"),
            normalized_key(item.question),
        ),
    )
    for incoming in ordered_questions:
        stable_id = _match_snapshot_question(
            incoming,
            questions_state,
            claimed,
            source_id_key,
        )
        if not stable_id:
            stable_id = _unique_identity(_question_identity_base(incoming), set(questions_state) | claimed)
            initial_version = _snapshot_version(
                incoming,
                version=1,
                detected_at=reviewed_iso,
                change_type="initial",
                changed_fields=[],
            )
            stored_source = {source_id_key: incoming.source_id}
            questions_state[stable_id] = {
                "stable_id": stable_id,
                **stored_source,
                "current_source_id": _metadata_value(incoming, "current_source_id") or incoming.source_id,
                "number": next_number,
                "official_datetime": incoming.official_datetime,
                "place_reported_datetime": incoming.official_datetime,
                "updated_at": incoming.updated_at,
                "asked_at": incoming.asked_at,
                "answered_at": incoming.answered_at,
                "question": incoming.question,
                "question_hash": incoming.question_hash,
                "answer": incoming.answer,
                "answer_hash": incoming.answer_hash,
                "attachments": _attachments_state(incoming),
                "attachments_hash": incoming.attachments_hash,
                "status": incoming.status,
                "source_url": incoming.source_url,
                "metadata": _metadata_state(incoming),
                "versions": [initial_version],
                "first_seen": reviewed_iso,
                "last_seen": reviewed_iso,
                "published": True,
                "unpublished_at": "",
                "reappeared_at": "",
                "publication_history": [],
                "last_change_type": "incorporated",
                "last_change_at": reviewed_iso,
            }
            events.append({"stable_id": stable_id, "event": "incorporated"})
            counts["incorporated"] += 1
            next_number += 1
            claimed.add(stable_id)
            continue

        claimed.add(stable_id)
        stored = questions_state[stable_id]
        was_published = bool(stored.get("published", True))
        changed_fields: list[str] = []
        if stored.get("question_hash") != incoming.question_hash:
            changed_fields.append("question")
        if stored.get("answer_hash") != incoming.answer_hash:
            changed_fields.append("answer")
        if stored.get("attachments_hash") != incoming.attachments_hash:
            changed_fields.append("attachments")
        old_official = extract_platform_datetime(stored.get("official_datetime"))
        if incoming.official_datetime:
            if not old_official:
                stored["official_datetime"] = incoming.official_datetime
        for field in ("asked_at", "answered_at"):
            old_value = literal_text(stored.get(field))
            new_value = literal_text(getattr(incoming, field))
            if not old_value and new_value:
                stored[field] = new_value
            elif old_value != new_value:
                changed_fields.append(field)

        old_answer = literal_text(stored.get("answer"))
        new_answer = literal_text(incoming.answer)
        change_type = ""
        if changed_fields:
            if "answer" in changed_fields and not old_answer and new_answer:
                change_type = "answer_added"
                counts["answers_incorporated"] += 1
            elif "answer" in changed_fields and old_answer and not new_answer:
                change_type = "answer_removed"
                counts["answers_removed"] += 1
            else:
                change_type = "content_modified"
                if set(changed_fields) & {"answer", "answered_at", "updated_at", "attachments"}:
                    counts["responses_modified"] += 1
            if "question" in changed_fields:
                counts["questions_modified"] += 1
            versions = stored.setdefault("versions", [])
            versions.append(
                _snapshot_version(
                    incoming,
                    version=max((int(item.get("version") or 0) for item in versions), default=0) + 1,
                    detected_at=reviewed_iso,
                    change_type=change_type,
                    changed_fields=changed_fields,
                )
            )
            events.append(
                {
                    "stable_id": stable_id,
                    "event": change_type,
                    "changed_fields": list(changed_fields),
                }
            )

        if not was_published:
            stored["published"] = True
            stored["reappeared_at"] = reviewed_iso
            stored["unpublished_at"] = ""
            stored.setdefault("publication_history", []).append(
                {"event": "restored", "detected_at": reviewed_iso}
            )
            stored["last_change_type"] = "restored_modified" if changed_fields else "restored"
            stored["last_change_at"] = reviewed_iso
            events.append(
                {
                    "stable_id": stable_id,
                    "event": "restored",
                    "content_modified": bool(changed_fields),
                }
            )
            counts["questions_restored"] += 1
        elif changed_fields:
            stored["last_change_type"] = change_type
            stored["last_change_at"] = reviewed_iso

        stored.update(
            {
                source_id_key: incoming.source_id or _stored_source_id(stored, source_id_key),
                "current_source_id": (
                    _metadata_value(incoming, "current_source_id")
                    or stored.get("current_source_id", "")
                    or incoming.source_id
                ),
                "official_datetime": (
                    incoming.official_datetime
                    if incoming.answered_at
                    else stored.get("official_datetime", "") or incoming.official_datetime
                ),
                "place_reported_datetime": incoming.official_datetime,
                "updated_at": incoming.updated_at,
                "asked_at": incoming.asked_at,
                "answered_at": incoming.answered_at,
                "question": incoming.question,
                "question_hash": incoming.question_hash,
                "answer": incoming.answer,
                "answer_hash": incoming.answer_hash,
                "attachments": _attachments_state(incoming),
                "attachments_hash": incoming.attachments_hash,
                "status": incoming.status,
                "source_url": incoming.source_url,
                "metadata": _metadata_state(incoming),
                "last_seen": reviewed_iso,
            }
        )

    for stable_id, stored in questions_state.items():
        if stable_id in claimed or not stored.get("published", True):
            continue
        stored["published"] = False
        stored["unpublished_at"] = reviewed_iso
        stored["last_change_type"] = "withdrawn"
        stored["last_change_at"] = reviewed_iso
        stored.setdefault("publication_history", []).append(
            {"event": "withdrawn", "detected_at": reviewed_iso}
        )
        events.append({"stable_id": stable_id, "event": "withdrawn"})
        counts["questions_removed"] += 1

    new_state["next_question_number"] = next_number
    new_state["metadata"] = dict(metadata)
    new_state["platform"] = str(metadata.get("platform") or new_state.get("platform") or "")
    new_state["profile_url"] = metadata.get("url") or new_state.get("profile_url", "")
    new_state["last_successful_review"] = reviewed_iso
    new_state["last_complete_snapshot"] = {
        "reviewed_at": reviewed_iso,
        "question_ids": sorted(claimed),
        "total_questions": len(claimed),
        "fingerprint": _snapshot_fingerprint(questions_state, claimed),
    }
    if events:
        new_state.setdefault("change_events", []).append(
            {
                "reviewed_at": reviewed_iso,
                "events": copy.deepcopy(events),
            }
        )
    return new_state, events, counts


def prepare_question_sync(
    state: dict[str, Any],
    metadata: dict[str, str],
    questions: Iterable[PlatformQuestion],
    reviewed_at: datetime,
    *,
    source_id_key: str = "place_source_id",
) -> PreparedQuestionSync:
    """API pública del motor puro, utilizable con snapshots artificiales."""

    new_state, events, counts = _prepare_snapshot(
        state,
        metadata,
        questions,
        reviewed_at,
        source_id_key=source_id_key,
    )
    return PreparedQuestionSync(new_state, tuple(events), counts)
