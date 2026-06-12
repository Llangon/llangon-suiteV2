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


def create_download_job(conn: sqlite3.Connection, licitacion_id: int, *, timestamp: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO download_jobs (
            licitacion_id,
            status,
            created_at,
            started_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (licitacion_id, "running", timestamp, timestamp, timestamp),
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
