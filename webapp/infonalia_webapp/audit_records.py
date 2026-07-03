from __future__ import annotations

import hashlib
import json
import sqlite3

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


def licitacion_id_for_payload(conn: sqlite3.Connection, payload: dict[str, object]) -> int | None:
    expediente = clean_text(payload.get("expediente"))
    organismo = clean_text(payload.get("organismo"))
    if not expediente:
        return None
    row = conn.execute(
        """
        SELECT id FROM licitaciones
        WHERE expediente = ? AND COALESCE(organismo, '') = ?
        LIMIT 1
        """,
        (expediente, organismo),
    ).fetchone()
    return int(row["id"]) if row else None


def import_payload_fingerprint(source_name: str, payload: dict[str, object]) -> str:
    normalized = {
        "source_name": clean_text(source_name),
        "expediente": clean_text(payload.get("expediente")),
        "organismo": clean_text(payload.get("organismo")),
        "enlace_perfil": clean_text(payload.get("enlace_perfil")),
        "enlace_infonalia": clean_text(payload.get("enlace_infonalia")),
    }
    content = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_import_run(
    conn: sqlite3.Connection,
    *,
    source_name: str,
    source_type: str,
    mode: str,
    input_hash: str,
    triggered_by: str = "",
    input_name: str = "",
    timestamp: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO import_runs (
            source_name,
            source_type,
            mode,
            started_at,
            status,
            triggered_by,
            input_name,
            input_hash,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_name,
            source_type,
            mode,
            timestamp,
            "running",
            triggered_by,
            input_name,
            input_hash,
            timestamp,
            timestamp,
        ),
    )
    return int(cur.lastrowid)


def finish_import_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    new_count: int,
    updated_count: int,
    duplicate_count: int,
    error_count: int,
    notes: str = "",
    timestamp: str,
) -> None:
    conn.execute(
        """
        UPDATE import_runs
        SET status = ?,
            finished_at = ?,
            new_count = ?,
            updated_count = ?,
            duplicate_count = ?,
            error_count = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            timestamp,
            new_count,
            updated_count,
            duplicate_count,
            error_count,
            notes,
            timestamp,
            run_id,
        ),
    )


def record_import_result(
    conn: sqlite3.Connection,
    *,
    import_run_id: int,
    source_name: str,
    payload: dict[str, object],
    status: str,
    licitacion_id: int | None = None,
    error_message: str = "",
    timestamp: str,
) -> None:
    raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    conn.execute(
        """
        INSERT INTO import_results (
            import_run_id,
            source_name,
            external_id,
            fingerprint,
            licitacion_id,
            status,
            error_message,
            raw_payload,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            import_run_id,
            source_name,
            clean_text(payload.get("expediente")),
            import_payload_fingerprint(source_name, payload),
            licitacion_id,
            status,
            error_message,
            raw_payload,
            timestamp,
        ),
    )


def create_download_job(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    timestamp: str,
    status: str = "running",
    request_source: str = "",
    request_action: str = "",
    request_message_id: str = "",
    requested_by: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO download_jobs (
            licitacion_id,
            status,
            request_source,
            request_action,
            request_message_id,
            requested_by,
            created_at,
            started_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            licitacion_id,
            clean_text(status) or "running",
            clean_text(request_source),
            clean_text(request_action),
            clean_text(request_message_id),
            clean_text(requested_by),
            timestamp,
            timestamp if (clean_text(status) or "running") == "running" else None,
            timestamp,
        ),
    )
    return int(cur.lastrowid)


def finish_download_job(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    status: str,
    storage_backend: str | None = None,
    storage_uri: str | None = None,
    file_manifest: str | None = None,
    error_message: str | None = None,
    timestamp: str,
) -> None:
    conn.execute(
        """
        UPDATE download_jobs
        SET status = ?,
            storage_backend = ?,
            storage_uri = ?,
            file_manifest = ?,
            error_message = ?,
            finished_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            storage_backend,
            storage_uri,
            file_manifest,
            error_message,
            timestamp,
            timestamp,
            job_id,
        ),
    )


def record_storage_upload(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    download_job_id: int | None,
    backend: str,
    destination_uri: str,
    manifest: dict,
    status: str,
    dry_run: bool,
    mode: str,
    uploaded_count: int,
    skipped_existing_count: int,
    failed_count: int,
    no_changes: bool,
    timestamp: str,
    error_message: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO storage_uploads (
            licitacion_id,
            download_job_id,
            backend,
            destination_uri,
            manifest_json,
            status,
            dry_run,
            mode,
            uploaded_count,
            skipped_existing_count,
            failed_count,
            no_changes,
            created_at,
            completed_at,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            licitacion_id,
            download_job_id,
            backend,
            destination_uri,
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, default=str),
            status,
            1 if dry_run else 0,
            mode,
            uploaded_count,
            skipped_existing_count,
            failed_count,
            1 if no_changes else 0,
            timestamp,
            timestamp,
            error_message,
        ),
    )
    return int(cur.lastrowid)
