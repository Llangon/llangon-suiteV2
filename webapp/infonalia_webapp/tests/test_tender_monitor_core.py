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
    read_technical_sidecar,
    read_technical_snapshot,
    snapshot_from_result,
    write_monitor_sidecar_cache,
)
from webapp.infonalia_webapp.monitor.tender_schema import ensure_tender_monitor_schema
from webapp.infonalia_webapp.monitor.tender_rules import mark_ai_candidates
from webapp.infonalia_webapp.monitor.tender_repository import (
    create_cycle,
    create_execution,
    fail_cycle_with_retry,
    load_monitor_baseline,
    monitor_automation_state,
    recover_orphan_cycles,
    save_snapshot,
)
from webapp.infonalia_webapp.monitor.tender_preparation import preparation_for_row
from webapp.infonalia_webapp.monitor.tender_messages import CHANGE_LABELS


def test_monitor_automation_state_reflects_shared_scheduler_configuration() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE automation_tasks (key TEXT PRIMARY KEY, enabled INTEGER, schedule_value TEXT)"
    )
    conn.execute(
        "INSERT INTO automation_tasks (key, enabled, schedule_value) VALUES ('monitor_licitaciones', 1, '08:00,13:00,18:00')"
    )

    state = monitor_automation_state(conn)

    assert state["automatic_enabled"] is True
    assert state["automatic_schedule"] == "08:00,13:00,18:00"
    assert "08:00, 13:00, 18:00" in state["automatic_message"]


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
        "sha256_source": "remote",
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


def test_new_publication_is_reported_as_folder_creation_not_as_document() -> None:
    previous = snapshot_from_result(result_payload())
    folder_name = "2026-07-10 - Esmena - 300828471"
    current = snapshot_from_result(
        result_payload(
            artifacts=[
                {
                    "name": f"Esmena — carpeta «{folder_name}»",
                    "status": "created",
                    "source_url": "https://contractaciopublica.cat/es/detall-publicacio/exp/300828471",
                    "path": folder_name,
                    "role": "publication",
                    "remote_id": "publication:300828471",
                    "section": "Esmena",
                    "published_at": "2026-07-10T05:56:13.562Z",
                }
            ]
        )
    )

    differences = compare_snapshots(previous, current)

    assert len(differences) == 1
    assert differences[0]["change_type"] == "publication_new"
    assert differences[0]["item_type"] == "publication"
    assert folder_name in differences[0]["title"]
    assert CHANGE_LABELS["publication_new"] == "Nueva publicación y carpeta creada"
    assert difference_fingerprint(differences) == difference_fingerprint(list(reversed(differences)))


def test_document_hash_changes_content_without_changing_remote_identity() -> None:
    old_document = document("acta.pdf", "old", "https://example.test/docs/acta.pdf")
    new_document = document("acta.pdf", "new", "https://example.test/docs/acta.pdf")
    previous = snapshot_from_result(result_payload(artifacts=[old_document]))
    current = snapshot_from_result(result_payload(artifacts=[new_document]))

    differences = compare_snapshots(previous, current)

    assert [item["change_type"] for item in differences] == ["document_modified"]


def test_local_file_hash_change_never_becomes_official_document_modification() -> None:
    old_document = document("acta.pdf", "old", "https://example.test/docs/acta.pdf")
    new_document = document("acta.pdf", "new", "https://example.test/docs/acta.pdf")
    old_document["sha256_source"] = "local"
    new_document["sha256_source"] = "local"

    previous = snapshot_from_result(result_payload(artifacts=[old_document]))
    current = snapshot_from_result(result_payload(artifacts=[new_document]))

    assert compare_snapshots(previous, current) == []


def test_empty_schema_enrichment_does_not_modify_existing_document() -> None:
    previous = snapshot_from_result(
        result_payload(artifacts=[document("acta.pdf", "same", "https://example.test/docs/acta.pdf")])
    )
    previous_item = next(iter(previous["blocks"]["documents"]["items"].values()))
    previous_item.pop("remote_id")
    previous_item.pop("section")
    previous_item.pop("published_at")
    current = snapshot_from_result(
        result_payload(artifacts=[document("acta.pdf", "same", "https://example.test/docs/acta.pdf")])
    )

    assert compare_snapshots(previous, current) == []


def test_unique_legacy_name_identity_upgrades_to_remote_url_without_novelty() -> None:
    previous = snapshot_from_result(
        result_payload(artifacts=[document("acta.pdf", "", "")])
    )
    previous_items = previous["blocks"]["documents"]["items"]
    previous_item = next(iter(previous_items.values()))
    previous_item["source_url"] = ""
    previous_items.clear()
    previous_items["document:name:acta.pdf"] = previous_item
    current = snapshot_from_result(
        result_payload(
            artifacts=[document("acta.pdf", "observed-hash", "https://example.test/docs/acta.pdf")]
        )
    )

    assert compare_snapshots(previous, current) == []
    merged = merge_valid_blocks(previous, current)
    merged_items = merged["blocks"]["documents"]["items"]
    assert list(merged_items) == ["document:url:https://example.test/docs/acta.pdf"]
    assert next(iter(merged_items.values()))["sha256"] == "observed-hash"


def test_reused_place_documents_do_not_become_new_when_wrapper_urls_change() -> None:
    names = [
        "DOC_CAN_ADJ2026-000322278.xml",
        "DOC_CAN_ADJ2026-000322278.pdf",
        "DOC_CAN_ADJ2026-000322278.html",
        "DOC_CN2026-000040043.html",
        "DOC20260622080630ACTA 24_26 MESA.pdf",
        "DOC20260720105808ACTA 28_26 MESA.pdf",
        "DOC_CD2026-000043932.xml",
        "DOC20260623124305cambio apertura del Sobre C.pdf",
        "DOC20260629120616ACTA 25_26 MESA.pdf",
        "DOC_CD2026-000043932.pdf",
        "DOC_CN2026-000040043.pdf",
        "DOC_CN2026-000040043.xml",
        "DOC_CD2026-000043932.html",
    ]
    previous = snapshot_from_result(
        result_payload(
            artifacts=[
                document(name, f"hash-{index}", f"https://contratacion.test/legacy?id={index}")
                for index, name in enumerate(names)
            ]
        )
    )
    # Reproduce a baseline written before sha256_source was persisted.
    for item in previous["blocks"]["documents"]["items"].values():
        item.pop("sha256_source", None)
    current_artifacts = [
        document(name, f"hash-{index}", f"https://contratacion.test/wrapper?document={index}")
        for index, name in enumerate(names)
    ]
    for item in current_artifacts:
        item["status"] = "reused"
    current = snapshot_from_result(result_payload(artifacts=current_artifacts))

    assert compare_snapshots(previous, current) == []

    merged = merge_valid_blocks(previous, current)
    merged_items = merged["blocks"]["documents"]["items"]
    assert len(merged_items) == 13
    assert all("wrapper?document=" in key for key in merged_items)


def test_same_name_with_conflicting_hash_and_url_is_not_silently_reconciled() -> None:
    previous = snapshot_from_result(
        result_payload(
            artifacts=[document("Acta.pdf", "old-content", "https://contratacion.test/document/old")]
        )
    )
    current = snapshot_from_result(
        result_payload(
            artifacts=[document("Acta.pdf", "new-content", "https://contratacion.test/document/new")]
        )
    )

    assert {item["change_type"] for item in compare_snapshots(previous, current)} == {
        "document_new",
        "document_removed",
    }


def test_reused_unique_document_with_changed_url_and_hash_is_modified_not_new() -> None:
    previous = snapshot_from_result(
        result_payload(
            artifacts=[document("Acta.pdf", "old-content", "https://contratacion.test/document/old")]
        )
    )
    reused = document("Acta.pdf", "new-content", "https://contratacion.test/wrapper/new")
    reused["status"] = "reused"
    current = snapshot_from_result(result_payload(artifacts=[reused]))

    differences = compare_snapshots(previous, current)

    assert [item["change_type"] for item in differences] == ["document_modified"]
    merged = merge_valid_blocks(previous, current)
    merged_item = next(iter(merged["blocks"]["documents"]["items"].values()))
    assert "observation_status" not in merged_item


def test_failed_transport_wrapper_preserves_confirmed_document_without_modification() -> None:
    source_url = "https://example.test/docs/stable-id"
    previous = snapshot_from_result(
        result_payload(artifacts=[document("oferta.xls", "binary-hash", source_url)])
    )
    wrapper = document("intermediaria.html", "html-hash", source_url)
    wrapper["status"] = "failed"
    partial = snapshot_from_result(result_payload(status="partial", artifacts=[wrapper]))

    assert compare_snapshots(previous, partial) == []
    merged = merge_valid_blocks(previous, partial)
    merged_item = next(iter(merged["blocks"]["documents"]["items"].values()))
    assert merged_item["name"] == "oferta.xls"
    assert merged_item["sha256"] == "binary-hash"
    assert "observation_failed" not in merged_item


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


def test_partial_response_keeps_verified_addition_but_excludes_failed_unverifiable_artifact() -> None:
    previous = snapshot_from_result(
        result_payload(artifacts=[document("uno.pdf", "1"), document("dos.pdf", "2")])
    )
    verified_new = document("acta-publicada.pdf", "3")
    failed_new = document("proteccion-javascript.html", "html-blocked")
    failed_new["status"] = "failed"
    partial = snapshot_from_result(
        result_payload(
            status="partial",
            artifacts=[document("uno.pdf", "1"), verified_new, failed_new],
        )
    )

    observed_names = {
        item["name"] for item in partial["blocks"]["documents"]["items"].values()
    }
    assert observed_names == {"uno.pdf", "acta-publicada.pdf"}
    differences = compare_snapshots(previous, partial)
    merged = merge_valid_blocks(previous, partial)

    assert [item["change_type"] for item in differences] == ["document_new"]
    assert differences[0]["title"] == "acta-publicada.pdf"
    merged_items = merged["blocks"]["documents"]["items"]
    assert {item["name"] for item in merged_items.values()} == {
        "uno.pdf",
        "dos.pdf",
        "acta-publicada.pdf",
    }
    assert all(item["published"] for item in merged_items.values())
    assert all("observation_failed" not in item for item in merged_items.values())


def test_generated_questions_docx_is_not_an_official_document_or_false_withdrawal() -> None:
    official = document("pliego.pdf", "official")
    generated_questions = {
        "name": "Preguntas y respuestas a fecha 2026-07-20 17-24-33.docx",
        "status": "created",
        "path": "Preguntas y respuestas a fecha 2026-07-20 17-24-33.docx",
        "sha256": "generated",
        "role": "questions_document",
    }
    previous = snapshot_from_result(
        result_payload(artifacts=[official, generated_questions])
    )
    repeated_without_changes = snapshot_from_result(
        result_payload(artifacts=[official])
    )

    items = previous["blocks"]["documents"]["items"]
    assert len(items) == 1
    assert next(iter(items.values()))["name"] == "pliego.pdf"
    assert compare_snapshots(previous, repeated_without_changes) == []


def test_legacy_snapshot_questions_docx_is_silently_removed_from_technical_state() -> None:
    previous = snapshot_from_result(
        result_payload(artifacts=[document("pliego.pdf", "official")])
    )
    legacy_item = {
        "name": "Preguntas y respuestas a fecha 2026-07-20 17-24-33.docx",
        "sha256": "generated",
        "role": "questions_document",
        "published": True,
    }
    previous["blocks"]["documents"]["items"]["questions_document:sha256:generated"] = legacy_item
    current = snapshot_from_result(
        result_payload(artifacts=[document("pliego.pdf", "official")])
    )

    assert compare_snapshots(previous, current) == []
    merged = merge_valid_blocks(previous, current)
    assert all(
        item.get("role") != "questions_document"
        for item in merged["blocks"]["documents"]["items"].values()
    )


def test_local_rename_or_delete_does_not_change_snapshot() -> None:
    payload = result_payload(artifacts=[document("oficial.pdf", "same")])
    first = snapshot_from_result(payload)
    payload["artifacts"][0]["path"] = "subcarpeta/renombrado-local.pdf"
    second = snapshot_from_result(payload)
    assert compare_snapshots(first, second) == []


def test_monitor_sidecar_is_versioned_cache_with_confirmed_monitor_identity(tmp_path: Path) -> None:
    snapshot = snapshot_from_result(
        result_payload(artifacts=[document("acta.pdf", "hash-acta")])
    )

    written = write_monitor_sidecar_cache(
        tmp_path,
        snapshot,
        licitacion_id=7,
        snapshot_id=11,
        execution_id=13,
    )

    assert written.is_file()
    sidecar = read_technical_sidecar(tmp_path)
    assert sidecar is not None
    assert sidecar["writer"] == "monitor"
    assert sidecar["snapshot_id"] == 11
    assert read_technical_snapshot(tmp_path)["fingerprint"] == snapshot["fingerprint"]


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
        INSERT INTO automation_tasks (key, enabled, schedule_value, updated_at, updated_by)
        VALUES ('monitor_licitaciones', 1, '08:00,13:00,18:00', '2026-07-20T20:40:00', 'test');
        """
    )

    ensure_tender_monitor_schema(conn)
    ensure_tender_monitor_schema(conn)

    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert "tender_monitor_cycles" in tables
    assert "tender_monitor_batches" in tables
    assert "tender_monitor_baselines" in tables
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
    task = conn.execute(
        "SELECT enabled, schedule_value FROM automation_tasks WHERE key = 'monitor_licitaciones'"
    ).fetchone()
    assert task == (1, "08:00,13:00,18:00")


def test_baseline_backfill_ignores_unconfirmed_normal_download_imports() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT);
        CREATE TABLE usuarios (username TEXT PRIMARY KEY, email TEXT);
        CREATE TABLE ai_analysis_jobs (id INTEGER PRIMARY KEY);
        INSERT INTO licitaciones (id, expediente) VALUES (1, 'ONE'), (2, 'TWO'), (3, 'THREE');
        """
    )
    ensure_tender_monitor_schema(conn)
    timestamp = "2026-07-20T08:00:00"
    unconfirmed_id = save_snapshot(
        conn,
        licitacion_id=1,
        platform="PLACE",
        snapshot=snapshot_from_result(result_payload(artifacts=[document("manual.pdf", "m")])),
        source="normal_download_import",
        execution_id=None,
        timestamp=timestamp,
    )
    monitor_id = save_snapshot(
        conn,
        licitacion_id=2,
        platform="PLACE",
        snapshot=snapshot_from_result(result_payload(artifacts=[document("monitor.pdf", "a")])),
        source="monitor",
        execution_id=None,
        timestamp=timestamp,
    )
    save_snapshot(
        conn,
        licitacion_id=2,
        platform="PLACE",
        snapshot=snapshot_from_result(result_payload(artifacts=[document("manual-later.pdf", "b")])),
        source="normal_download_import",
        execution_id=None,
        timestamp="2026-07-20T09:00:00",
    )
    confirmed_import_id = save_snapshot(
        conn,
        licitacion_id=3,
        platform="PLACE",
        snapshot=snapshot_from_result(result_payload(artifacts=[document("confirmed.pdf", "c")])),
        source="normal_download_import",
        execution_id=None,
        timestamp="2026-07-20T10:00:00",
    )
    cycle_id = conn.execute(
        """
        INSERT INTO tender_monitor_cycles (origin, status, created_at, started_at, finished_at)
        VALUES ('migration-test', 'completed', ?, ?, ?)
        """,
        (timestamp, timestamp, "2026-07-20T10:05:00"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO tender_monitor_executions (
            cycle_id, licitacion_id, platform, status, current_snapshot_id, started_at, finished_at
        ) VALUES (?, 3, 'PLACE', 'no_changes', ?, ?, '2026-07-20T10:05:00')
        """,
        (cycle_id, confirmed_import_id, timestamp),
    )

    ensure_tender_monitor_schema(conn)

    assert load_monitor_baseline(conn, 1) == (None, None)
    assert unconfirmed_id is not None
    assert load_monitor_baseline(conn, 2)[0] == monitor_id
    assert load_monitor_baseline(conn, 3)[0] == confirmed_import_id


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
    conn.execute("INSERT INTO licitaciones (id, expediente) VALUES (7, 'EXP-7')")
    execution_id = create_execution(
        conn,
        cycle_id=cycle_id,
        licitacion_id=7,
        platform="PLACE",
        timestamp="2026-07-20T08:00:00",
    )
    conn.execute(
        """
        UPDATE tender_monitor_cycles
        SET created_at = '2026-07-20T08:00:00', current_licitacion_id = 7
        WHERE id = ?
        """,
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
    execution = conn.execute(
        "SELECT status, error_code FROM tender_monitor_executions WHERE id = ?", (execution_id,)
    ).fetchone()
    assert dict(execution) == {"status": "error", "error_code": "ORPHAN_CYCLE_RECOVERED"}


def test_preparation_prefers_canonical_http_shortcut_when_database_has_place_document_url(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "2026" / "EXP-29"
    folder.mkdir(parents=True)
    (folder / "29.llangon").write_text("", encoding="utf-8")
    (folder / "EnSeguimiento.llangon").write_text("", encoding="utf-8")
    profile_url = (
        "https://contrataciondelestado.es/wps/poc?"
        "uri=deeplink:detalle_licitacion&idEvl=correcta"
    )
    (folder / "HTTP.url").write_text(
        f"[InternetShortcut]\nURL={profile_url}\n", encoding="utf-8"
    )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY, plataforma TEXT, enlace_perfil TEXT, ruta_carpeta TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO licitaciones VALUES (
            29, 'PLACE',
            'https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=xml',
            ?
        )
        """,
        (str(folder),),
    )
    row = conn.execute("SELECT * FROM licitaciones WHERE id = 29").fetchone()

    prepared = preparation_for_row(row, root=tmp_path)

    assert prepared.prepared is True
    assert prepared.source_url == profile_url


def test_preparation_rejects_document_url_before_downloader(tmp_path: Path) -> None:
    folder = tmp_path / "2026" / "EXP-30"
    folder.mkdir(parents=True)
    (folder / "30.llangon").write_text("", encoding="utf-8")
    (folder / "EnSeguimiento.llangon").write_text("", encoding="utf-8")
    document_url = (
        "https://contrataciondelestado.es/FileSystem/servlet/"
        "GetDocumentByIdServlet?DocumentIdParam=xml"
    )
    (folder / "HTTP.url").write_text(
        f"[InternetShortcut]\nURL={document_url}\n", encoding="utf-8"
    )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, plataforma TEXT, enlace_perfil TEXT)"
    )
    conn.execute("INSERT INTO licitaciones VALUES (30, 'PLACE', ?)", (document_url,))
    row = conn.execute("SELECT * FROM licitaciones WHERE id = 30").fetchone()

    prepared = preparation_for_row(row, root=tmp_path)

    assert prepared.prepared is False
    assert prepared.preparation_code == "INVALID_PROFILE_URL"


def test_worker_failure_closes_cycle_execution_and_leases_with_fresh_connection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT);
        CREATE TABLE usuarios (username TEXT PRIMARY KEY, email TEXT);
        CREATE TABLE ai_analysis_jobs (id INTEGER PRIMARY KEY);
        CREATE TABLE automation_tasks (
            key TEXT PRIMARY KEY, enabled INTEGER, schedule_value TEXT, updated_at TEXT, updated_by TEXT
        );
        INSERT INTO licitaciones (id, expediente) VALUES (9, 'EXP-9');
        """
    )
    ensure_tender_monitor_schema(conn)
    cycle_id = create_cycle(conn, origin="test", requested_by="admin")
    execution_id = create_execution(
        conn,
        cycle_id=cycle_id,
        licitacion_id=9,
        platform="PLACE",
        timestamp="2026-07-20T08:00:00",
    )
    conn.execute(
        "UPDATE tender_monitor_cycles SET status = 'running', current_licitacion_id = 9 WHERE id = ?",
        (cycle_id,),
    )
    conn.execute(
        """
        INSERT INTO tender_monitor_leases
            (lease_key, owner, acquired_at, heartbeat_at, expires_at, metadata_json)
        VALUES ('tender-monitor:global', 'worker', '2026-07-20T08:00:00',
                '2026-07-20T08:00:00', '2026-07-20T09:00:00', ?)
        """,
        (json.dumps({"cycle_id": cycle_id}),),
    )
    conn.commit()
    conn.close()

    assert fail_cycle_with_retry(db_path, cycle_id, message="database is locked") is True

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cycle = conn.execute(
        "SELECT status, worker_exit_code FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)
    ).fetchone()
    execution = conn.execute(
        "SELECT status, error_code FROM tender_monitor_executions WHERE id = ?", (execution_id,)
    ).fetchone()
    assert dict(cycle) == {"status": "failed", "worker_exit_code": 1}
    assert dict(execution) == {"status": "error", "error_code": "WORKER_TERMINATED"}
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_leases").fetchone()[0] == 0
    conn.close()
