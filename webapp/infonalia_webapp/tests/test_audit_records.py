from __future__ import annotations

import sqlite3

from webapp.infonalia_webapp.audit_records import (
    create_download_job,
    create_import_run,
    finish_download_job,
    finish_import_run,
    import_payload_fingerprint,
    licitacion_id_for_payload,
    record_import_result,
)


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expediente TEXT,
            organismo TEXT
        );
        CREATE TABLE import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            triggered_by TEXT,
            input_name TEXT,
            input_hash TEXT,
            new_count INTEGER NOT NULL DEFAULT 0,
            updated_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE import_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_run_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            external_id TEXT,
            fingerprint TEXT,
            licitacion_id INTEGER,
            status TEXT NOT NULL,
            error_message TEXT,
            raw_payload TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE download_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            request_source TEXT,
            request_action TEXT,
            request_message_id TEXT,
            requested_by TEXT,
            storage_backend TEXT,
            storage_uri TEXT,
            file_manifest TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    return conn


def test_import_run_helpers_record_candidate_result() -> None:
    conn = make_conn()
    conn.execute("INSERT INTO licitaciones (expediente, organismo) VALUES (?, ?)", ("EXP-1", "Org"))
    payload = {"expediente": "EXP-1", "organismo": "Org", "objeto": "Servicio"}

    run_id = create_import_run(
        conn,
        source_name="csv",
        source_type="csv",
        mode="manual",
        input_hash="abc123",
        triggered_by="admin",
        timestamp="2026-06-12T10:00:00",
    )
    licitacion_id = licitacion_id_for_payload(conn, payload)
    record_import_result(
        conn,
        import_run_id=run_id,
        source_name="csv",
        payload=payload,
        status="inserted",
        licitacion_id=licitacion_id,
        timestamp="2026-06-12T10:00:01",
    )
    finish_import_run(
        conn,
        run_id,
        status="completed",
        new_count=1,
        updated_count=0,
        duplicate_count=0,
        error_count=0,
        timestamp="2026-06-12T10:00:02",
    )

    run = conn.execute("SELECT * FROM import_runs WHERE id = ?", (run_id,)).fetchone()
    result = conn.execute("SELECT * FROM import_results WHERE import_run_id = ?", (run_id,)).fetchone()

    assert run["status"] == "completed"
    assert run["new_count"] == 1
    assert run["triggered_by"] == "admin"
    assert result["external_id"] == "EXP-1"
    assert result["status"] == "inserted"
    assert result["licitacion_id"] == licitacion_id
    assert result["fingerprint"] == import_payload_fingerprint("csv", payload)


def test_download_job_helpers_record_success_metadata() -> None:
    conn = make_conn()

    job_id = create_download_job(
        conn,
        7,
        timestamp="2026-06-12T10:00:00",
        status="pending",
        request_source="email_action",
        request_action="Descargar para ver",
        request_message_id="<msg-1>",
        requested_by="nuria@example.test",
    )
    finish_download_job(
        conn,
        job_id,
        status="completed",
        storage_backend="local",
        storage_uri="local://descarga",
        file_manifest="local://descarga/.infonalia_manifest.json",
        timestamp="2026-06-12T10:00:03",
    )

    row = conn.execute("SELECT * FROM download_jobs WHERE id = ?", (job_id,)).fetchone()

    assert row["licitacion_id"] == 7
    assert row["status"] == "completed"
    assert row["request_source"] == "email_action"
    assert row["request_action"] == "Descargar para ver"
    assert row["request_message_id"] == "<msg-1>"
    assert row["requested_by"] == "nuria@example.test"
    assert row["storage_backend"] == "local"
    assert row["storage_uri"] == "local://descarga"
    assert row["file_manifest"].endswith(".infonalia_manifest.json")
    assert row["error_message"] is None
    assert row["finished_at"] == "2026-06-12T10:00:03"
