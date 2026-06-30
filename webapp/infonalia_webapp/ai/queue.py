from __future__ import annotations

import json
import sqlite3
from datetime import datetime


ACTIVE_JOB_STATUSES = ("pending", "processing", "deferred")
PROCESSING_STALE_STATUSES = ("processing",)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_ai_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            document_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'gemini',
            model TEXT,
            requested_by TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error_code TEXT,
            error_message TEXT,
            selected_documents_json TEXT,
            attempts INTEGER DEFAULT 0,
            next_retry_at TEXT,
            raw_usage_json TEXT,
            dismissed_at TEXT,
            dismissed_by TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    _ensure_column(conn, "ai_analysis_jobs", "dismissed_at", "TEXT")
    _ensure_column(conn, "ai_analysis_jobs", "dismissed_by", "TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_jobs_licitacion ON ai_analysis_jobs(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_jobs_document_hash ON ai_analysis_jobs(document_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_jobs_status ON ai_analysis_jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_jobs_created ON ai_analysis_jobs(created_at)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            document_hash TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'gemini',
            model TEXT,
            summary_json TEXT NOT NULL,
            summary_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_from_job_id INTEGER,
            quality_status TEXT DEFAULT 'pending_review',
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (created_from_job_id) REFERENCES ai_analysis_jobs(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_summaries_licitacion ON ai_summaries(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_summaries_hash ON ai_summaries(document_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_summaries_created ON ai_summaries(created_at)")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_summaries_unique_document
        ON ai_summaries(licitacion_id, document_hash)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL,
            request_type TEXT,
            status TEXT,
            tokens_input INTEGER,
            tokens_output INTEGER,
            tokens_total INTEGER,
            error_code TEXT,
            licitacion_id INTEGER,
            job_id INTEGER,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (job_id) REFERENCES ai_analysis_jobs(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_provider_created ON ai_usage_log(provider, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_job ON ai_usage_log(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_licitacion ON ai_usage_log(licitacion_id)")


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def latest_summary(conn: sqlite3.Connection, licitacion_id: int, document_hash: str | None = None) -> sqlite3.Row | None:
    values: list[object] = [licitacion_id]
    where = "licitacion_id = ?"
    if document_hash:
        where += " AND document_hash = ?"
        values.append(document_hash)
    return conn.execute(
        f"SELECT * FROM ai_summaries WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT 1",
        values,
    ).fetchone()


def active_job(conn: sqlite3.Connection, licitacion_id: int, document_hash: str, provider: str | None = None) -> sqlite3.Row | None:
    placeholders = ",".join("?" for _ in ACTIVE_JOB_STATUSES)
    provider_clause = " AND provider = ?" if provider else ""
    values: list[object] = [licitacion_id, document_hash, *ACTIVE_JOB_STATUSES]
    if provider:
        values.append(provider)
    return conn.execute(
        f"""
        SELECT * FROM ai_analysis_jobs
        WHERE licitacion_id = ? AND document_hash = ? AND status IN ({placeholders})
          AND (dismissed_at IS NULL OR dismissed_at = '')
          {provider_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        values,
    ).fetchone()


def latest_job(
    conn: sqlite3.Connection,
    licitacion_id: int,
    document_hash: str | None = None,
    provider: str | None = None,
) -> sqlite3.Row | None:
    values: list[object] = [licitacion_id]
    where = "licitacion_id = ? AND (dismissed_at IS NULL OR dismissed_at = '')"
    if document_hash:
        where += " AND document_hash = ?"
        values.append(document_hash)
    if provider:
        where += " AND provider = ?"
        values.append(provider)
    return conn.execute(
        f"""
        SELECT * FROM ai_analysis_jobs
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        values,
    ).fetchone()


def create_job(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    document_hash: str,
    selected_documents: list[dict[str, object]],
    model: str,
    provider: str = "gemini",
    requested_by: str = "",
    status: str = "pending",
    error_code: str = "",
    error_message: str = "",
    created_at: str | None = None,
) -> int:
    timestamp = created_at or now_iso()
    cur = conn.execute(
        """
        INSERT INTO ai_analysis_jobs (
            licitacion_id, document_hash, status, provider, model, requested_by,
            created_at, error_code, error_message, selected_documents_json, attempts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            licitacion_id,
            document_hash,
            status,
            provider,
            model,
            requested_by,
            timestamp,
            error_code,
            error_message,
            json.dumps(selected_documents, ensure_ascii=False),
        ),
    )
    return int(cur.lastrowid)


def update_job(conn: sqlite3.Connection, job_id: int, **fields: object) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(f"UPDATE ai_analysis_jobs SET {set_clause} WHERE id = ?", [*fields.values(), job_id])


def claim_pending_job(conn: sqlite3.Connection, job_id: int, *, started_at: str | None = None) -> sqlite3.Row | None:
    timestamp = started_at or now_iso()
    cur = conn.execute(
        """
        UPDATE ai_analysis_jobs
        SET status = 'processing', started_at = ?, attempts = COALESCE(attempts, 0) + 1
        WHERE id = ?
          AND status IN ('pending', 'queued', 'deferred')
          AND (dismissed_at IS NULL OR dismissed_at = '')
        """,
        (timestamp, job_id),
    )
    if cur.rowcount <= 0:
        return None
    return conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()


def next_pending_job(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM ai_analysis_jobs
        WHERE status IN ('pending', 'queued', 'deferred')
          AND (dismissed_at IS NULL OR dismissed_at = '')
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """
    ).fetchone()


def save_summary(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    document_hash: str,
    model: str,
    summary: dict[str, object],
    text: str,
    job_id: int,
    provider: str = "gemini",
    timestamp: str | None = None,
) -> int:
    now = timestamp or now_iso()
    existing = latest_summary(conn, licitacion_id, document_hash)
    payload = json.dumps(summary, ensure_ascii=False)
    if existing:
        conn.execute(
            """
            UPDATE ai_summaries
            SET provider = ?, model = ?, summary_json = ?, summary_text = ?, updated_at = ?,
                created_from_job_id = ?, quality_status = 'pending_review'
            WHERE id = ?
            """,
            (provider, model, payload, text, now, job_id, existing["id"]),
        )
        return int(existing["id"])
    cur = conn.execute(
        """
        INSERT INTO ai_summaries (
            licitacion_id, document_hash, provider, model, summary_json, summary_text,
            created_at, updated_at, created_from_job_id, quality_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review')
        """,
        (licitacion_id, document_hash, provider, model, payload, text, now, now, job_id),
    )
    return int(cur.lastrowid)


def record_usage(
    conn: sqlite3.Connection,
    *,
    model: str,
    status: str,
    provider: str = "gemini",
    request_type: str = "analysis",
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    tokens_total: int | None = None,
    error_code: str = "",
    licitacion_id: int | None = None,
    job_id: int | None = None,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ai_usage_log (
            provider, model, created_at, request_type, status,
            tokens_input, tokens_output, tokens_total, error_code, licitacion_id, job_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider,
            model,
            created_at or now_iso(),
            request_type,
            status,
            tokens_input,
            tokens_output,
            tokens_total,
            error_code,
            licitacion_id,
            job_id,
        ),
    )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
    if not row:
        return None
    result = dict(row)
    if result.get("selected_documents_json"):
        try:
            result["selected_documents"] = json.loads(str(result["selected_documents_json"]))
        except json.JSONDecodeError:
            result["selected_documents"] = []
    if result.get("summary_json"):
        try:
            result["summary"] = json.loads(str(result["summary_json"]))
        except json.JSONDecodeError:
            result["summary"] = {}
    return result
