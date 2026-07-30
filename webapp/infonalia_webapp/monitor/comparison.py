from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Mapping

from .snapshots import canonical_url, normalize_text


COMPLETE = "complete"
PARTIAL = "partial"


def _hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _block(snapshot: Mapping[str, object], name: str) -> Mapping[str, object]:
    blocks = snapshot.get("blocks") if isinstance(snapshot.get("blocks"), Mapping) else {}
    value = blocks.get(name) if isinstance(blocks, Mapping) else {}
    return value if isinstance(value, Mapping) else {}


def _difference(
    *,
    block: str,
    change_type: str,
    item_type: str,
    item_key: str,
    title: str,
    old_value: object = None,
    new_value: object = None,
) -> dict[str, object]:
    stable_material = {
        "block": block,
        "change_type": change_type,
        "item_type": item_type,
        "item_key": item_key,
        "old": old_value,
        "new": new_value,
    }
    return {
        "stable_key": _hash(stable_material),
        "block": block,
        "change_type": change_type,
        "item_type": item_type,
        "item_key": item_key,
        "title": title,
        "old_value": old_value,
        "new_value": new_value,
    }


def _compare_fields(previous: Mapping[str, object], current: Mapping[str, object], block: str) -> list[dict[str, object]]:
    status = normalize_text(current.get("status"))
    if status not in {COMPLETE, PARTIAL}:
        return []
    old_data = previous.get("data") if isinstance(previous.get("data"), Mapping) else {}
    new_data = current.get("data") if isinstance(current.get("data"), Mapping) else {}
    result: list[dict[str, object]] = []
    for key, new_value in new_data.items():
        if key in old_data and old_data.get(key) == new_value:
            continue
        result.append(
            _difference(
                block=block,
                change_type="field_changed",
                item_type="official_field",
                item_key=str(key),
                title=f"Cambio en {key}",
                old_value=old_data.get(key),
                new_value=new_value,
            )
        )
    if status == COMPLETE:
        for key, old_value in old_data.items():
            if key in new_data:
                continue
            result.append(
                _difference(
                    block=block,
                    change_type="field_changed",
                    item_type="official_field",
                    item_key=str(key),
                    title=f"Cambio en {key}",
                    old_value=old_value,
                    new_value=None,
                )
            )
    return result


def _item_changed(old: Mapping[str, object], new: Mapping[str, object]) -> bool:
    if bool(new.get("observation_failed")):
        return False
    for key in ("sha256", "version_fingerprint", "question_hash", "answer_hash", "attachments_hash"):
        old_value = normalize_text(old.get(key))
        new_value = normalize_text(new.get(key))
        if key == "sha256" and not (
            normalize_text(old.get("sha256_source")).casefold() == "remote"
            and normalize_text(new.get("sha256_source")).casefold() == "remote"
        ):
            continue
        if old_value and new_value and old_value != new_value:
            return True
    ignored = {
        "relative_path",
        "published",
        "observation_failed",
        "observation_status",
        # A download endpoint is transport metadata. PLACE can expose the same
        # official document through a different wrapper URL between reviews.
        "source_url",
        "sha256",
        "sha256_source",
        "version_fingerprint",
        "question_hash",
        "answer_hash",
        "attachments_hash",
    }
    for key in sorted((set(old) | set(new)) - ignored):
        old_value = old.get(key)
        new_value = new.get(key)
        # Adding an optional descriptor to the snapshot schema, or temporarily
        # failing to observe one, is enrichment/incomplete data rather than a
        # remote modification. Only two concrete, different values can change
        # an already identified item.
        if old_value in (None, "", 0, [], {}) or new_value in (None, "", 0, [], {}):
            continue
        if old_value != new_value:
            return True
    return False


def _is_local_generated_item(block: str, item: object) -> bool:
    return bool(
        block == "documents"
        and isinstance(item, Mapping)
        and normalize_text(item.get("role")).casefold() == "questions_document"
    )


def _comparable_items(value: object, *, block: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if not _is_local_generated_item(block, item)
    }


def _comparison_item_type(item: Mapping[str, object], fallback: str) -> str:
    if normalize_text(item.get("role")).casefold() == "publication":
        return "publication"
    return fallback


def _same_item_identity(old: Mapping[str, object], new: Mapping[str, object]) -> bool:
    """Confirm an identity migration without relying on a mutable URL."""

    old_remote_id = normalize_text(old.get("remote_id"))
    new_remote_id = normalize_text(new.get("remote_id"))
    if old_remote_id and new_remote_id:
        return old_remote_id == new_remote_id

    old_hash = normalize_text(old.get("sha256")).casefold()
    new_hash = normalize_text(new.get("sha256")).casefold()
    if old_hash and new_hash and old_hash == new_hash:
        # Equal bytes are conclusive even for snapshots created before
        # sha256_source was recorded.
        return True

    old_url = normalize_text(old.get("source_url"))
    new_url = normalize_text(new.get("source_url"))
    if old_url and new_url and canonical_url(old_url) == canonical_url(new_url):
        return True

    if normalize_text(new.get("observation_status")).casefold() == "reused":
        # The downloader observed the remote item and associated it with the
        # already present local filename. Unique-name matching is enforced by
        # _identity_aliases, so URL-wrapper drift cannot turn it into a new item.
        return True

    # Compatibility with name-only snapshots created by older monitor builds.
    return not (old_remote_id or old_url) and bool(new_remote_id or new_url)


def _identity_aliases(
    old_items: Mapping[str, object],
    new_items: Mapping[str, object],
) -> dict[str, str]:
    """Reconcile a unique item whose technical identity representation changed.

    Both snapshots must contain one unique item with the same normalized name,
    and a stable signal must corroborate the match. Ambiguous duplicate names
    and conflicting strong identifiers are never reconciled automatically.
    """

    old_by_name: dict[str, list[str]] = {}
    new_by_name: dict[str, list[str]] = {}
    for key, value in old_items.items():
        if not isinstance(value, Mapping):
            continue
        name = normalize_text(value.get("name")).casefold()
        if name:
            old_by_name.setdefault(name, []).append(str(key))
    for key, value in new_items.items():
        if not isinstance(value, Mapping):
            continue
        name = normalize_text(value.get("name")).casefold()
        if name:
            new_by_name.setdefault(name, []).append(str(key))
    aliases: dict[str, str] = {}
    for name, current_keys in new_by_name.items():
        legacy_keys = old_by_name.get(name, [])
        if len(current_keys) != 1 or len(legacy_keys) != 1:
            continue
        current_key = current_keys[0]
        previous_key = legacy_keys[0]
        if current_key == previous_key:
            continue
        old_item = old_items.get(previous_key)
        new_item = new_items.get(current_key)
        if (
            isinstance(old_item, Mapping)
            and isinstance(new_item, Mapping)
            and _same_item_identity(old_item, new_item)
        ):
            aliases[current_key] = previous_key
    return aliases


def _compare_items(
    previous: Mapping[str, object],
    current: Mapping[str, object],
    *,
    block: str,
    item_type: str,
) -> list[dict[str, object]]:
    status = normalize_text(current.get("status"))
    if status not in {COMPLETE, PARTIAL}:
        return []
    old_items = _comparable_items(previous.get("items"), block=block)
    new_items = _comparable_items(current.get("items"), block=block)
    identity_aliases = _identity_aliases(old_items, new_items)
    matched_previous_keys = set(identity_aliases.values())
    result: list[dict[str, object]] = []
    for key, raw_new in new_items.items():
        if not isinstance(raw_new, Mapping):
            continue
        # Defensa en profundidad para snapshots antiguos que todavía puedan
        # contener observaciones fallidas.
        if bool(raw_new.get("observation_failed")):
            continue
        raw_old = old_items.get(key)
        if not isinstance(raw_old, Mapping) and str(key) in identity_aliases:
            raw_old = old_items.get(identity_aliases[str(key)])
        title = normalize_text(raw_new.get("name") or raw_new.get("stable_id") or key)
        effective_item_type = _comparison_item_type(raw_new, item_type)
        if not isinstance(raw_old, Mapping):
            if not bool(raw_new.get("published", True)):
                continue
            result.append(
                _difference(
                    block=block,
                    change_type=f"{effective_item_type}_new",
                    item_type=effective_item_type,
                    item_key=str(key),
                    title=title,
                    new_value=dict(raw_new),
                )
            )
        elif bool(raw_old.get("published", True)) and not bool(raw_new.get("published", True)):
            result.append(
                _difference(
                    block=block,
                    change_type=f"{effective_item_type}_removed",
                    item_type=effective_item_type,
                    item_key=str(key),
                    title=title,
                    old_value=dict(raw_old),
                    new_value=dict(raw_new),
                )
            )
        elif not bool(raw_old.get("published", True)) and bool(raw_new.get("published", True)):
            result.append(
                _difference(
                    block=block,
                    change_type=f"{effective_item_type}_restored",
                    item_type=effective_item_type,
                    item_key=str(key),
                    title=title,
                    old_value=dict(raw_old),
                    new_value=dict(raw_new),
                )
            )
        elif bool(raw_new.get("published", True)) and _item_changed(raw_old, raw_new):
            result.append(
                _difference(
                    block=block,
                    change_type=f"{effective_item_type}_modified",
                    item_type=effective_item_type,
                    item_key=str(key),
                    title=title,
                    old_value=dict(raw_old),
                    new_value=dict(raw_new),
                )
            )
    if status == COMPLETE:
        for key, raw_old in old_items.items():
            if (
                key in new_items
                or key in matched_previous_keys
                or not isinstance(raw_old, Mapping)
                or not bool(raw_old.get("published", True))
            ):
                continue
            title = normalize_text(raw_old.get("name") or raw_old.get("stable_id") or key)
            effective_item_type = _comparison_item_type(raw_old, item_type)
            result.append(
                _difference(
                    block=block,
                    change_type=f"{effective_item_type}_removed",
                    item_type=effective_item_type,
                    item_key=str(key),
                    title=title,
                    old_value=dict(raw_old),
                )
            )
    return result


def compare_snapshots(previous: Mapping[str, object], current: Mapping[str, object]) -> list[dict[str, object]]:
    differences: list[dict[str, object]] = []
    differences.extend(_compare_fields(_block(previous, "general"), _block(current, "general"), "general"))
    differences.extend(_compare_fields(_block(previous, "dates"), _block(current, "dates"), "dates"))
    differences.extend(
        _compare_items(_block(previous, "documents"), _block(current, "documents"), block="documents", item_type="document")
    )
    differences.extend(
        _compare_items(_block(previous, "questions"), _block(current, "questions"), block="questions", item_type="question")
    )
    return sorted(differences, key=lambda item: str(item["stable_key"]))


def merge_valid_blocks(previous: Mapping[str, object], current: Mapping[str, object]) -> dict[str, object]:
    """Merge a partial snapshot without turning missing data into withdrawals."""

    merged = deepcopy(dict(previous))
    merged.update({key: deepcopy(value) for key, value in current.items() if key != "blocks"})
    merged_blocks = merged.setdefault("blocks", {})
    current_blocks = current.get("blocks") if isinstance(current.get("blocks"), Mapping) else {}
    previous_blocks = previous.get("blocks") if isinstance(previous.get("blocks"), Mapping) else {}
    for name, raw_current in current_blocks.items():
        if not isinstance(raw_current, Mapping):
            continue
        status = normalize_text(raw_current.get("status"))
        raw_previous = previous_blocks.get(name) if isinstance(previous_blocks, Mapping) else {}
        old_block = deepcopy(dict(raw_previous)) if isinstance(raw_previous, Mapping) else {}
        if status not in {COMPLETE, PARTIAL, "not_applicable"}:
            merged_blocks[name] = old_block
            continue
        if "items" in raw_current:
            old_items = _comparable_items(old_block.get("items"), block=str(name))
            new_items = _comparable_items(raw_current.get("items"), block=str(name))
            items = deepcopy(dict(old_items))
            identity_aliases = _identity_aliases(old_items, new_items)
            for current_key, previous_key in identity_aliases.items():
                current_item = new_items.get(current_key)
                if isinstance(current_item, Mapping) and bool(current_item.get("observation_failed")):
                    continue
                items.pop(previous_key, None)
            for key, value in new_items.items():
                if isinstance(value, Mapping) and bool(value.get("observation_failed")):
                    continue
                clean_value = deepcopy(value)
                if isinstance(clean_value, dict):
                    clean_value.pop("observation_failed", None)
                    clean_value.pop("observation_status", None)
                items[str(key)] = clean_value
            if status == COMPLETE:
                for key, value in list(items.items()):
                    if key in new_items or not isinstance(value, Mapping):
                        continue
                    value = dict(value)
                    value["published"] = False
                    items[key] = value
            merged_blocks[name] = {
                "status": normalize_text(old_block.get("status")) or COMPLETE if status == PARTIAL else status,
                "items": items,
            }
        elif "data" in raw_current:
            data = deepcopy(dict(old_block.get("data") or {}))
            data.update(deepcopy(dict(raw_current.get("data") or {})))
            merged_blocks[name] = {
                "status": normalize_text(old_block.get("status")) or COMPLETE if status == PARTIAL else status,
                "data": data,
            }
        else:
            merged_blocks[name] = deepcopy(dict(raw_current))
    fingerprint_payload = deepcopy(merged)
    fingerprint_payload.pop("captured_at", None)
    fingerprint_payload.pop("fingerprint", None)
    merged["fingerprint"] = _hash(fingerprint_payload)
    return merged


def difference_fingerprint(differences: list[Mapping[str, object]]) -> str:
    return _hash(sorted(str(item.get("stable_key") or "") for item in differences))
