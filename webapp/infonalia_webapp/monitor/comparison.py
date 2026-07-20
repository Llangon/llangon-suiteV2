from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Mapping

from .snapshots import normalize_text


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
    for key in ("sha256", "version_fingerprint", "question_hash", "answer_hash", "attachments_hash"):
        old_value = normalize_text(old.get(key))
        new_value = normalize_text(new.get(key))
        if old_value and new_value and old_value != new_value:
            return True
    comparable_old = {key: value for key, value in old.items() if key not in {"relative_path", "published"}}
    comparable_new = {key: value for key, value in new.items() if key not in {"relative_path", "published"}}
    return comparable_old != comparable_new


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
    old_items = previous.get("items") if isinstance(previous.get("items"), Mapping) else {}
    new_items = current.get("items") if isinstance(current.get("items"), Mapping) else {}
    result: list[dict[str, object]] = []
    for key, raw_new in new_items.items():
        if not isinstance(raw_new, Mapping):
            continue
        raw_old = old_items.get(key)
        title = normalize_text(raw_new.get("name") or raw_new.get("stable_id") or key)
        if not isinstance(raw_old, Mapping):
            if not bool(raw_new.get("published", True)):
                continue
            result.append(
                _difference(
                    block=block,
                    change_type=f"{item_type}_new",
                    item_type=item_type,
                    item_key=str(key),
                    title=title,
                    new_value=dict(raw_new),
                )
            )
        elif bool(raw_old.get("published", True)) and not bool(raw_new.get("published", True)):
            result.append(
                _difference(
                    block=block,
                    change_type=f"{item_type}_removed",
                    item_type=item_type,
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
                    change_type=f"{item_type}_restored",
                    item_type=item_type,
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
                    change_type=f"{item_type}_modified",
                    item_type=item_type,
                    item_key=str(key),
                    title=title,
                    old_value=dict(raw_old),
                    new_value=dict(raw_new),
                )
            )
    if status == COMPLETE:
        for key, raw_old in old_items.items():
            if key in new_items or not isinstance(raw_old, Mapping) or not bool(raw_old.get("published", True)):
                continue
            title = normalize_text(raw_old.get("name") or raw_old.get("stable_id") or key)
            result.append(
                _difference(
                    block=block,
                    change_type=f"{item_type}_removed",
                    item_type=item_type,
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
            old_items = old_block.get("items") if isinstance(old_block.get("items"), Mapping) else {}
            new_items = raw_current.get("items") if isinstance(raw_current.get("items"), Mapping) else {}
            items = deepcopy(dict(old_items))
            for key, value in new_items.items():
                items[str(key)] = deepcopy(value)
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
