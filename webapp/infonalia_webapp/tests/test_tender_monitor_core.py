from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from webapp.infonalia_webapp.monitor.comparison import (
    compare_snapshots,
    difference_fingerprint,
    merge_valid_blocks,
)
from webapp.infonalia_webapp.monitor.snapshots import (
    canonical_url,
    persist_normal_download_baseline,
    read_technical_snapshot,
    snapshot_from_result,
)
from webapp.infonalia_webapp.monitor.tender_schema import ensure_tender_monitor_schema
from webapp.infonalia_webapp.monitor.tender_rules import mark_ai_candidates
from webapp.infonalia_webapp.monitor.tender_repository import create_cycle, recover_orphan_cycles


def result_payload(*, status: str = "success", artifacts: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "platform": "PLACE",
        "source_url": "https://contrataciondelestado.es/tender/1",
        "started_at": "2026-07-20T09:00:00",
        "finished_at": "2026-07-20T09:01:00",
        "status": status,
        "capabilities": {"documents": True, "questions_and_answers": False},
        "tender_id": "EXP-1",
        "general_data": {"title": "Servicio   de limpieza", "volatile": "ignored"},
        "relevant_dates": {"deadline": "2026-08-01", "downloaded_at": "ignored"},
        "artifacts": artifacts or [],
    }


def document(name: str, sha: str, url: str = "") -> dict[str, object]:
    return {
        "name": name,
        "status": "created",
        "source_url": url or f"https://example.test/docs/{name}?token=temporary",
        "path": name,
        "sha256": sha,
        "role": "document",
    }


def test_snapshot_uses_only_structured_downloader_state_and_ignores_local_tree(tmp_path: Path) -> None:
    (tmp_path / "manual.pdf").write_bytes(b"manual")
    (tmp_path / "subcarpeta").mkdir()
    snapshot = snapshot_from_result(result_payload(artifacts=[document("oficial.pdf", "aaa")]), destination=tmp_path)

    items = snapshot["blocks"]["documents"]["items"]
    assert len(items) == 1
    assert all("manual.pdf" not in json.dumps(value) for value in items.values())
    assert all("subcarpeta" not in json.dumps(value) for value in items.values())


def test_canonical_url_ignores_temporary_parameters_but_keeps_official_identity() -> None:
    first = canonical_url("https://Example.test/doc?id=7&token=one&ts=1")
    second = canonical_url("https://example.test/doc?ts=2&id=7&token=two")
    assert first == second == "https://example.test/doc?id=7"


def test_semantic_comparison_groups_new_modified_and_removed_documents() -> None:
    previous = snapshot_from_result(
        result_payload(
            artifacts=[
                document("estable.pdf", "aaa"),
                document("modificado.pdf", "old"),
                document("retirado.pdf", "gone"),
            ]
        )
    )
    current = snapshot_from_result(
        result_payload(
            artifacts=[
                document("estable.pdf", "aaa"),
                document("modificado.pdf", "new"),
                document("nuevo.pdf", "fresh"),
            ]
        )
    )

    differences = compare_snapshots(previous, current)
    assert {item["change_type"] for item in differences} == {
        "document_new",
        "document_modified",
        "document_removed",
    }
    assert difference_fingerprint(differences) == difference_fingerprint(list(reversed(differences)))


def test_partial_document_response_never_creates_false_withdrawals_and_preserves_state() -> None:
    previous = snapshot_from_result(
        result_payload(artifacts=[document("uno.pdf", "1"), document("dos.pdf", "2")])
    )
    partial = snapshot_from_result(
        result_payload(status="partial", artifacts=[document("uno.pdf", "1")])
    )

    assert compare_snapshots(previous, partial) == []
    merged = merge_valid_blocks(previous, partial)
    assert len(merged["blocks"]["documents"]["items"]) == 2
    assert all(item["published"] for item in merged["blocks"]["documents"]["items"].values())


def test_local_rename_or_delete_does_not_change_snapshot() -> None:
    payload = result_payload(artifacts=[document("oficial.pdf", "same")])
    first = snapshot_from_result(payload)
    payload["artifacts"][0]["path"] = "subcarpeta/renombrado-local.pdf"
    second = snapshot_from_result(payload)
    assert compare_snapshots(first, second) == []


def test_normal_download_structured_result_updates_baseline_without_monitor_batch(tmp_path: Path) -> None:
    payload = result_payload(artifacts=[document("acta.pdf", "hash-acta")])
    output = "inicio\nRESULTADO_ESTRUCTURADO=" + json.dumps(payload, ensure_ascii=False)

    written = persist_normal_download_baseline(output, tmp_path)

    assert written is not None and written.is_file()
    assert read_technical_snapshot(tmp_path)["fingerprint"]


def test_tender_monitor_schema_is_idempotent_global_and_keeps_follow_marker_outside_sqlite() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT);
        CREATE TABLE usuarios (username TEXT PRIMARY KEY, email TEXT);
        CREATE TABLE ai_analysis_jobs (id INTEGER PRIMARY KEY);
        CREATE TABLE automation_tasks (
            key TEXT PRIMARY KEY, enabled INTEGER, schedule_value TEXT, updated_at TEXT, updated_by TEXT
        );
        """
    )

    ensure_tender_monitor_schema(conn)
    ensure_tender_monitor_schema(conn)

    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert "tender_monitor_cycles" in tables
    assert "tender_monitor_batches" in tables
    assert "tender_monitor_recipients" in tables
    assert "licitacion_id" not in {
        row[1] for row in conn.execute("PRAGMA table_info(tender_monitor_recipients)").fetchall()
    }
    assert not any(
        "seguimiento" in row[1]
        for table in tables
        if table.startswith("tender_monitor_")
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    )
    task = conn.execute("SELECT enabled, schedule_value FROM automation_tasks WHERE key = 'monitor_licitaciones'").fetchone()
    assert task == (0, None)


def test_questions_never_trigger_ai_even_when_title_mentions_acta() -> None:
    differences = [
        {
            "change_type": "question_new",
            "item_type": "question",
            "title": "Pregunta sobre el acta de adjudicación",
            "new_value": {"relative_path": "preguntas.json"},
        },
        {
            "change_type": "document_new",
            "item_type": "document",
            "title": "Acta de adjudicación.pdf",
            "new_value": {"relative_path": "Acta de adjudicación.pdf"},
        },
    ]

    marked = mark_ai_candidates(differences, enabled_categories=["acta", "adjudicacion"])

    assert marked[0]["ai_candidate"] is False
    assert marked[1]["ai_candidate"] is True


def test_question_tombstones_are_reported_as_removed_and_then_restored() -> None:
    base = {
        "blocks": {
            "questions": {
                "status": "complete",
                "items": {
                    "q-1": {
                        "stable_id": "q-1",
                        "question_hash": "one",
                        "answer_hash": "answer",
                        "published": True,
                    }
                },
            }
        }
    }
    withdrawn = json.loads(json.dumps(base))
    withdrawn["blocks"]["questions"]["items"]["q-1"]["published"] = False

    removed = compare_snapshots(base, withdrawn)
    restored = compare_snapshots(withdrawn, base)

    assert [item["change_type"] for item in removed] == ["question_removed"]
    assert [item["change_type"] for item in restored] == ["question_restored"]


def test_orphan_cycle_is_recovered_after_lease_window() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT);
        CREATE TABLE usuarios (username TEXT PRIMARY KEY, email TEXT);
        CREATE TABLE ai_analysis_jobs (id INTEGER PRIMARY KEY);
        CREATE TABLE automation_tasks (key TEXT PRIMARY KEY, enabled INTEGER, schedule_value TEXT, updated_at TEXT, updated_by TEXT);
        """
    )
    ensure_tender_monitor_schema(conn)
    cycle_id = create_cycle(conn, origin="test", requested_by="admin")
    conn.execute(
        "UPDATE tender_monitor_cycles SET created_at = '2026-07-20T08:00:00' WHERE id = ?",
        (cycle_id,),
    )

    recovered = recover_orphan_cycles(
        conn,
        timestamp=datetime(2026, 7, 20, 10, 0, 0),
        minutes=60,
    )

    assert recovered == [cycle_id]
    assert conn.execute(
        "SELECT status FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)
    ).fetchone()["status"] == "failed"
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE cycle_id = ?", (cycle_id,)
    ).fetchone()["code"] == "ORPHAN_CYCLE_RECOVERED"
