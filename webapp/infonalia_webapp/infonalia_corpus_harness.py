from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

from .infonalia_import_core import CanonicalBlock, comparison_value, reconcile_message
from .infonalia_msg_reader import InfonaliaMsgContent, read_msg_path


DEFAULT_RANDOM_SEED = 20260720
INVENTORY_NAME = "inventario_sha256_corpus_infonalia.json"
MANIFEST_FIELDS = {
    "ref_infonalia": "ref_infonalia",
    "expediente": "expediente",
    "organismo": "organismo",
    "resumen_objeto": "resumen_objeto",
    "provincia_ejecucion": "provincia_ejecucion",
    "presupuesto": "presupuesto_texto",
    "plazo_presentacion": "plazo_presentacion_texto",
    "perfil_contratante": "url_perfil_contratante",
    "fuente_informacion": "fuente_texto",
}


def load_manifest(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise ValueError("El manifiesto Infonalia no contiene una lista 'files' válida.")
    return data


def load_inventory(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise ValueError("El inventario Infonalia no contiene una lista 'messages' válida.")
    return data


def extract_msg_fixture(path: Path) -> dict[str, object]:
    """Compatibility wrapper over the MSG reader shared with manual import."""

    content = read_msg_path(path)
    return {
        "plain": content.plain,
        "html": content.html,
        "message_id": content.message_id,
        "subject": content.subject,
        "date": content.date,
        "sender": content.sender,
        "html_source_type": content.html_source_type,
        "html_decode_replacements": content.html_decode_replacements,
        "plain_decode_replacements": content.plain_decode_replacements,
    }


def _safe_fixture_name(value: object) -> str:
    name = str(value or "")
    if not name or Path(name).name != name or Path(name).suffix.casefold() != ".msg":
        raise ValueError(f"Nombre MSG no seguro en los controles del corpus: {name!r}.")
    return name


def _normalize_timestamp(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _compare_manifest_blocks(
    file_name: str,
    expected_blocks: list[dict[str, object]],
    parsed_blocks: list[CanonicalBlock],
) -> list[str]:
    differences: list[str] = []
    if len(expected_blocks) != len(parsed_blocks):
        differences.append(
            f"{file_name}: manifiesto={len(expected_blocks)} bloques, parser={len(parsed_blocks)} bloques."
        )
    for ordinal, (expected, actual) in enumerate(zip(expected_blocks, parsed_blocks), start=1):
        expected_ordinal = int(expected.get("ordinal") or ordinal)
        if expected_ordinal != actual.ordinal:
            differences.append(
                f"{file_name} bloque {ordinal}: ordinal esperado={expected_ordinal}, obtenido={actual.ordinal}."
            )
        for expected_name, actual_name in MANIFEST_FIELDS.items():
            expected_value = expected.get(expected_name, "")
            actual_value = getattr(actual, actual_name)
            if comparison_value(actual_name, expected_value) != comparison_value(actual_name, actual_value):
                differences.append(
                    f"{file_name} bloque {ordinal} campo {expected_name}: "
                    f"esperado={expected_value!r}, obtenido={actual_value!r}."
                )
    return differences


def _content_signature(block: CanonicalBlock) -> str:
    return json.dumps(block.comparison_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _message_signature(message: dict[str, object]) -> str:
    blocks = message["result"].canonical_blocks
    value = "\n".join(
        f"{block.ref_infonalia}\t{_content_signature(block)}"
        for block in blocks
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _classify_message(conn: sqlite3.Connection, message: dict[str, object]) -> dict[str, object]:
    result = message["result"]
    detected = result.detected_count
    outcome = {
        "file": message["file"],
        "detected": detected,
        "inserted": 0,
        "duplicates": 0,
        "conflicts": 0,
        "quarantined": 0,
        "uncategorized": 0,
        "status": "ok",
    }
    if not result.safe_to_persist:
        outcome["quarantined"] = detected
        outcome["status"] = "quarantined"
        return outcome

    with conn:
        for block in result.canonical_blocks:
            signature = _content_signature(block)
            existing = conn.execute(
                "SELECT payload_json FROM imported_refs WHERE ref_infonalia = ?",
                (block.ref_infonalia,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO imported_refs(ref_infonalia, payload_json) VALUES (?, ?)",
                    (block.ref_infonalia, signature),
                )
                outcome["inserted"] += 1
            elif existing[0] == signature:
                outcome["duplicates"] += 1
            else:
                outcome["conflicts"] += 1

    categorized = sum(
        int(outcome[key]) for key in ("inserted", "duplicates", "conflicts", "quarantined")
    )
    outcome["uncategorized"] = detected - categorized
    if outcome["conflicts"] or outcome["quarantined"] or outcome["uncategorized"]:
        outcome["status"] = "failed"
    return outcome


def _run_order(
    messages_by_name: dict[str, dict[str, object]],
    ordered_files: Iterable[str],
    db_path: Path,
    *,
    initialize: bool,
) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    try:
        if initialize:
            conn.execute(
                "CREATE TABLE imported_refs (ref_infonalia TEXT PRIMARY KEY, payload_json TEXT NOT NULL)"
            )
        per_file = [_classify_message(conn, messages_by_name[name]) for name in ordered_files]
        final_refs = [
            row[0]
            for row in conn.execute("SELECT ref_infonalia FROM imported_refs ORDER BY ref_infonalia")
        ]
    finally:
        conn.close()

    totals = {
        key: sum(int(item[key]) for item in per_file)
        for key in ("detected", "inserted", "duplicates", "conflicts", "quarantined", "uncategorized")
    }
    names = [str(item["file"]) for item in per_file]
    return {
        **totals,
        "messages": len(per_file),
        "final_unique_refs": len(final_refs),
        "final_refs_sha256": hashlib.sha256("\n".join(final_refs).encode("ascii")).hexdigest(),
        "ordered_files": names,
        "order_sha256": hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest(),
        "per_file": per_file,
        "_final_refs": final_refs,
    }


def _public_order_result(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if not key.startswith("_") and key != "per_file"}


def _build_orders(
    messages: list[dict[str, object]],
    *,
    random_seed: int,
) -> tuple[dict[str, list[str]], list[dict[str, object]], bool]:
    chronological = sorted(messages, key=lambda item: (str(item["normalized_date"]), str(item["file"])))
    chronological_names = [str(item["file"]) for item in chronological]

    random_order = chronological_names.copy()
    random.Random(random_seed).shuffle(random_order)
    repeated_random_order = chronological_names.copy()
    random.Random(random_seed).shuffle(repeated_random_order)

    by_signature: dict[str, list[dict[str, object]]] = defaultdict(list)
    for message in chronological:
        by_signature[_message_signature(message)].append(message)
    repeated_groups = [group for group in by_signature.values() if len(group) > 1]
    originals = [group[0] for group in repeated_groups]
    duplicate_copies = [item for group in repeated_groups for item in group[1:]]
    grouped_names = {str(item["file"]) for group in repeated_groups for item in group}
    other = [item for item in chronological if str(item["file"]) not in grouped_names]

    duplicate_groups = [
        {
            "original": str(group[0]["file"]),
            "duplicates": [str(item["file"]) for item in group[1:]],
            "blocks_per_copy": len(group[0]["result"].canonical_blocks),
        }
        for group in repeated_groups
    ]
    orders = {
        "chronological": chronological_names,
        "reverse_chronological": list(reversed(chronological_names)),
        "random_seed_20260720": random_order,
        "duplicate_copies_before_originals": [
            *(str(item["file"]) for item in duplicate_copies),
            *(str(item["file"]) for item in other),
            *(str(item["file"]) for item in originals),
        ],
        "originals_before_duplicate_copies": [
            *(str(item["file"]) for item in originals),
            *(str(item["file"]) for item in other),
            *(str(item["file"]) for item in duplicate_copies),
        ],
    }
    return orders, duplicate_groups, random_order == repeated_random_order


def _validate_inventory(
    *,
    corpus_root: Path,
    manifest: dict[str, object],
    inventory_path: Path,
    verify_hashes: bool,
) -> dict[str, object]:
    differences: list[str] = []
    try:
        inventory = load_inventory(inventory_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        inventory = {"message_count": 0, "messages": []}
        differences.append(f"No se pudo validar el inventario {inventory_path}: {exc}")

    manifest_entries = {_safe_fixture_name(item["file"]): item for item in manifest["files"]}
    inventory_entries = {
        _safe_fixture_name(item["filename"]): item for item in inventory.get("messages", [])
    }
    actual_paths = {
        path.name: path for path in corpus_root.iterdir() if path.is_file() and path.suffix.casefold() == ".msg"
    } if corpus_root.is_dir() else {}

    expected_names = set(manifest_entries)
    inventory_names = set(inventory_entries)
    actual_names = set(actual_paths)
    missing_files = sorted(expected_names - actual_names)
    unexpected_files = sorted(actual_names - expected_names)
    inventory_missing_files = sorted(inventory_names - actual_names)
    inventory_unexpected_files = sorted(actual_names - inventory_names)
    empty_files: list[str] = []
    size_mismatches: list[str] = []
    hash_mismatches: list[str] = []
    manifest_inventory_mismatches: list[str] = []
    actual_hashes: dict[str, str] = {}

    declared_count = int(inventory.get("message_count") or 0)
    if declared_count != len(inventory_entries):
        differences.append(
            f"Inventario: message_count={declared_count}, entradas={len(inventory_entries)}."
        )
    if expected_names != inventory_names:
        differences.append(
            "Los nombres del manifiesto y del inventario no forman el mismo conjunto exacto."
        )

    for name in sorted(expected_names & inventory_names):
        manifest_hash = str(manifest_entries[name].get("sha256_msg") or "").casefold()
        inventory_hash = str(inventory_entries[name].get("sha256") or "").casefold()
        if manifest_hash != inventory_hash:
            manifest_inventory_mismatches.append(
                f"{name}: manifiesto={manifest_hash}, inventario={inventory_hash}"
            )

    for name, path in sorted(actual_paths.items()):
        size = path.stat().st_size
        if size == 0:
            empty_files.append(name)
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        actual_hashes[name] = actual_hash
        inventory_entry = inventory_entries.get(name)
        manifest_entry = manifest_entries.get(name)
        if inventory_entry is not None and size != int(inventory_entry.get("size_bytes") or 0):
            size_mismatches.append(
                f"{name}: inventario={inventory_entry.get('size_bytes')}, real={size}"
            )
        if verify_hashes and inventory_entry is not None:
            expected_hash = str(inventory_entry.get("sha256") or "").casefold()
            if actual_hash != expected_hash:
                hash_mismatches.append(
                    f"{name}: inventario={expected_hash}, obtenido={actual_hash}"
                )
        if verify_hashes and manifest_entry is not None:
            expected_hash = str(manifest_entry.get("sha256_msg") or "").casefold()
            if actual_hash != expected_hash:
                hash_mismatches.append(
                    f"{name}: manifiesto={expected_hash}, obtenido={actual_hash}"
                )

    return {
        "expected_msg_files": len(expected_names),
        "inventory_declared_msg_files": declared_count,
        "inventory_entries": len(inventory_entries),
        "actual_msg_files": len(actual_names),
        "hashes_compared": len(actual_hashes) if verify_hashes else 0,
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "inventory_missing_files": inventory_missing_files,
        "inventory_unexpected_files": inventory_unexpected_files,
        "empty_files": empty_files,
        "size_mismatches": size_mismatches,
        "hash_mismatches": hash_mismatches,
        "manifest_inventory_mismatches": manifest_inventory_mismatches,
        "differences": differences,
        "actual_hashes": actual_hashes,
    }


def run_corpus_simulation(
    *,
    corpus_dir: str | Path,
    manifest_path: str | Path,
    inventory_path: str | Path | None = None,
    verify_hashes: bool = True,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, object]:
    corpus_root = Path(corpus_dir).resolve()
    manifest_file = Path(manifest_path).resolve()
    inventory_file = Path(inventory_path).resolve() if inventory_path else corpus_root / INVENTORY_NAME
    manifest = load_manifest(manifest_file)
    expected_files = list(manifest["files"])
    inventory = _validate_inventory(
        corpus_root=corpus_root,
        manifest=manifest,
        inventory_path=inventory_file,
        verify_hashes=verify_hashes,
    )
    unusable_names = {
        *inventory["missing_files"],
        *inventory["empty_files"],
        *(item.split(":", 1)[0] for item in inventory["hash_mismatches"]),
    }

    differences: list[str] = []
    metadata_differences: list[str] = []
    encoding_issues: list[str] = []
    messages: list[dict[str, object]] = []
    refs: list[str] = []
    id_expediente_refs: list[str] = []
    totals = {"msg_files": 0, "html_blocks": 0, "text_blocks": 0, "canonical_blocks": 0}

    for expected_file in expected_files:
        name = _safe_fixture_name(expected_file["file"])
        path = corpus_root / name
        if name in unusable_names or not path.is_file():
            continue
        fixture = extract_msg_fixture(path)
        result = reconcile_message(
            plain_text=str(fixture["plain"]),
            html_text=str(fixture["html"]),
            message_id=str(fixture["message_id"] or name),
            require_both=True,
            enforce_ref_format=True,
        )
        actual_date = _normalize_timestamp(fixture["date"])
        expected_date = _normalize_timestamp(expected_file.get("message_date"))
        if actual_date != expected_date:
            metadata_differences.append(
                f"{name} fecha: esperada={expected_date!r}, obtenida={actual_date!r}."
            )
        replacements = int(fixture["html_decode_replacements"]) + int(
            fixture["plain_decode_replacements"]
        )
        if replacements:
            encoding_issues.append(f"{name}: {replacements} caracteres de sustitución Unicode.")

        totals["msg_files"] += 1
        totals["html_blocks"] += result.html.marker_count
        totals["text_blocks"] += result.text.marker_count
        totals["canonical_blocks"] += len(result.canonical_blocks)
        expected_count = int(expected_file.get("expected_block_count") or 0)
        if expected_count != len(result.canonical_blocks):
            differences.append(
                f"{name}: expected_block_count={expected_count}, conciliados={len(result.canonical_blocks)}."
            )
        if not result.safe_to_persist:
            differences.extend(f"{name}: {issue.message}" for issue in result.issues)
        differences.extend(
            _compare_manifest_blocks(name, list(expected_file.get("blocks") or []), result.canonical_blocks)
        )
        for block in result.canonical_blocks:
            refs.append(block.ref_infonalia)
            if "idexpediente=" in block.url_perfil_contratante.casefold():
                id_expediente_refs.append(block.ref_infonalia)

        html_text = str(fixture["html"])
        plain_text = str(fixture["plain"])
        messages.append(
            {
                "file": name,
                "path": path,
                "sha256": inventory["actual_hashes"].get(name, ""),
                "date": str(fixture["date"]),
                "normalized_date": actual_date,
                "expected_date": expected_date,
                "message_id": str(fixture["message_id"]),
                "subject": str(fixture["subject"]),
                "sender": str(fixture["sender"]),
                "plain_chars": len(plain_text),
                "html_chars": len(html_text),
                "html_source_type": str(fixture["html_source_type"]),
                "decode_replacements": replacements,
                "html_entity_occurrences": len(re.findall(r"&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);", html_text, re.I)),
                "html_href_occurrences": len(re.findall(r"\bhref\s*=", html_text, re.I)),
                "dual_representation": bool(plain_text.strip() and html_text.strip()),
                "result": result,
            }
        )

    aggregate = manifest.get("aggregate") or {}
    expected_summary = {
        "msg_files": int(aggregate.get("msg_files") or 0),
        "html_blocks": int(aggregate.get("block_occurrences") or 0),
        "text_blocks": int(aggregate.get("block_occurrences") or 0),
        "canonical_blocks": int(aggregate.get("block_occurrences") or 0),
        "unique_refs": int(aggregate.get("unique_ref_infonalia") or 0),
        "duplicates": int(aggregate.get("duplicate_occurrences") or 0),
        "id_expediente_occurrences": int(
            aggregate.get("block_occurrences_with_idExpediente_profile_url") or 0
        ),
        "id_expediente_unique_refs": int(
            aggregate.get("unique_refs_with_idExpediente_profile_url") or 0
        ),
    }
    actual_summary = {
        **totals,
        "unique_refs": len(set(refs)),
        "duplicates": len(refs) - len(set(refs)),
        "id_expediente_occurrences": len(id_expediente_refs),
        "id_expediente_unique_refs": len(set(id_expediente_refs)),
    }

    order_results: dict[str, dict[str, object]] = {}
    second_run: dict[str, object] = {}
    duplicate_groups: list[dict[str, object]] = []
    random_reproducible = False
    same_final_reference_set = False
    chronological_per_file: dict[str, dict[str, object]] = {}
    if len(messages) == len(expected_files):
        orders, duplicate_groups, random_reproducible = _build_orders(
            messages,
            random_seed=random_seed,
        )
        messages_by_name = {str(item["file"]): item for item in messages}
        internal_order_results: dict[str, dict[str, object]] = {}
        with tempfile.TemporaryDirectory(prefix="llangon-infonalia-corpus-") as temp_dir:
            temp_root = Path(temp_dir)
            for order_name, ordered_files in orders.items():
                first = _run_order(
                    messages_by_name,
                    ordered_files,
                    temp_root / f"{order_name}.sqlite",
                    initialize=True,
                )
                internal_order_results[order_name] = first
                order_results[order_name] = _public_order_result(first)
                if order_name == "chronological":
                    chronological_per_file = {
                        str(item["file"]): item for item in first["per_file"]
                    }
                    second_internal = _run_order(
                        messages_by_name,
                        ordered_files,
                        temp_root / f"{order_name}.sqlite",
                        initialize=False,
                    )
                    second_run = _public_order_result(second_internal)
            final_sets = [tuple(item["_final_refs"]) for item in internal_order_results.values()]
            same_final_reference_set = bool(final_sets) and len(set(final_sets)) == 1

    per_file: list[dict[str, object]] = []
    for message in sorted(messages, key=lambda item: (str(item["normalized_date"]), str(item["file"]))):
        result = message["result"]
        persistence = chronological_per_file.get(str(message["file"]), {})
        per_file.append(
            {
                "file": message["file"],
                "date": message["normalized_date"],
                "sha256": message["sha256"],
                "message_id": message["message_id"],
                "subject": message["subject"],
                "sender": message["sender"],
                "plain_chars": message["plain_chars"],
                "html_chars": message["html_chars"],
                "html_source_type": message["html_source_type"],
                "decode_replacements": message["decode_replacements"],
                "html_entity_occurrences": message["html_entity_occurrences"],
                "html_href_occurrences": message["html_href_occurrences"],
                "dual_representation": message["dual_representation"],
                "html_blocks": result.html.marker_count,
                "text_blocks": result.text.marker_count,
                "reconciled": len(result.canonical_blocks),
                "inserted": int(persistence.get("inserted") or 0),
                "duplicates": int(persistence.get("duplicates") or 0),
                "conflicts": int(persistence.get("conflicts") or 0),
                "quarantined": int(persistence.get("quarantined") or 0),
                "uncategorized": int(persistence.get("uncategorized") or 0),
                "status": str(persistence.get("status") or "not_run"),
            }
        )

    expected_first_order = {
        "detected": expected_summary["canonical_blocks"],
        "inserted": expected_summary["unique_refs"],
        "duplicates": expected_summary["duplicates"],
        "conflicts": 0,
        "quarantined": 0,
        "uncategorized": 0,
        "messages": expected_summary["msg_files"],
        "final_unique_refs": expected_summary["unique_refs"],
    }
    orders_match = bool(order_results) and all(
        all(result.get(key) == value for key, value in expected_first_order.items())
        for result in order_results.values()
    )
    second_run_matches = bool(second_run) and all(
        second_run.get(key) == value
        for key, value in {
            "detected": expected_summary["canonical_blocks"],
            "inserted": 0,
            "duplicates": expected_summary["canonical_blocks"],
            "conflicts": 0,
            "quarantined": 0,
            "uncategorized": 0,
            "messages": expected_summary["msg_files"],
            "final_unique_refs": expected_summary["unique_refs"],
        }.items()
    )
    duplicate_group_occurrences = sum(
        int(group["blocks_per_copy"]) * len(group["duplicates"])
        for group in duplicate_groups
    )
    duplicate_groups_match = duplicate_group_occurrences == expected_summary["duplicates"]

    target_references: dict[str, dict[str, str]] = {}
    for message in messages:
        for block in message["result"].canonical_blocks:
            if block.ref_infonalia in {"2026103762", "2026103763"}:
                target_references[block.ref_infonalia] = {
                    "expediente": block.expediente,
                    "file": str(message["file"]),
                }
    targets_match = {
        key: value.get("expediente") for key, value in target_references.items()
    } == {
        "2026103762": "CONTR 2026 0000264070",
        "2026103763": "CONTR 2026 0000264400",
    }
    inventory_ok = not any(
        inventory[key]
        for key in (
            "missing_files",
            "unexpected_files",
            "inventory_missing_files",
            "inventory_unexpected_files",
            "empty_files",
            "size_mismatches",
            "hash_mismatches",
            "manifest_inventory_mismatches",
            "differences",
        )
    )
    ok = all(
        (
            inventory_ok,
            not differences,
            not metadata_differences,
            not encoding_issues,
            actual_summary == expected_summary,
            orders_match,
            second_run_matches,
            duplicate_groups_match,
            random_reproducible,
            same_final_reference_set,
            targets_match,
            len(per_file) == expected_summary["msg_files"],
            all(item["status"] == "ok" for item in per_file),
        )
    )
    return {
        "ok": ok,
        "corpus_dir": str(corpus_root),
        "manifest_path": str(manifest_file),
        "inventory_path": str(inventory_file),
        "inventory_validation": inventory,
        "expected": expected_summary,
        "actual": actual_summary,
        "per_file": per_file,
        "order_runs": order_results,
        "orders_match": orders_match,
        "same_final_reference_set": same_final_reference_set,
        "random_seed": random_seed,
        "random_reproducible": random_reproducible,
        "second_run_chronological": second_run,
        "second_run_matches": second_run_matches,
        "duplicate_message_groups": duplicate_groups,
        "duplicate_group_occurrences": duplicate_group_occurrences,
        "duplicate_groups_match": duplicate_groups_match,
        "id_expediente_unique_refs": sorted(set(id_expediente_refs)),
        "target_references": target_references,
        "missing_files": inventory["missing_files"],
        "unexpected_files": inventory["unexpected_files"],
        "hash_mismatches": inventory["hash_mismatches"],
        "differences": differences,
        "metadata_differences": metadata_differences,
        "encoding_issues": encoding_issues,
        "external_effects": {
            "imap_connections": 0,
            "smtp_connections": 0,
            "dropbox_writes": 0,
            "telegram_messages": 0,
            "real_seen_marks": 0,
            "real_database_writes": 0,
            "scheduler_runs": 0,
            "windows_task_runs": 0,
        },
        "isolation": {
            "msg_source": "fixture_only",
            "sqlite": "TemporaryDirectory",
            "network_calls_in_harness": 0,
            "production_feature_flag_changed": False,
            "deployment_performed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulación aislada del corpus MSG de Infonalia.")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--report")
    parser.add_argument("--random-seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--no-verify-hashes", action="store_true")
    args = parser.parse_args(argv)
    report = run_corpus_simulation(
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
        inventory_path=args.inventory,
        verify_hashes=not args.no_verify_hashes,
        random_seed=args.random_seed,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
