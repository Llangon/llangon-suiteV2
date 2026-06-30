from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta


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
    _ensure_column(conn, "ai_analysis_jobs", "progress_stage", "TEXT")
    _ensure_column(conn, "ai_analysis_jobs", "progress_message", "TEXT")
    _ensure_column(conn, "ai_analysis_jobs", "progress_percent", "INTEGER")
    _ensure_column(conn, "ai_analysis_jobs", "heartbeat_at", "TEXT")
    _ensure_column(conn, "ai_analysis_jobs", "worker_pid", "INTEGER")
    _ensure_column(conn, "ai_analysis_jobs", "started_by", "TEXT")
    _ensure_column(conn, "ai_analysis_jobs", "cancel_requested", "INTEGER DEFAULT 0")
    _ensure_column(conn, "ai_analysis_jobs", "estimated_seconds", "INTEGER")
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


def parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def estimate_seconds_for_job(provider: str, selected_documents_count: int) -> int:
    if provider != "codex_local":
        return 120
    if selected_documents_count <= 1:
        return 7 * 60
    if selected_documents_count == 2:
        return 10 * 60
    if selected_documents_count <= 4:
        return 15 * 60
    return 18 * 60


def estimate_label_for_job(provider: str, selected_documents_count: int) -> str:
    if provider != "codex_local":
        return "1-3 min aprox."
    if selected_documents_count <= 1:
        return "4-7 min aprox."
    if selected_documents_count == 2:
        return "6-10 min aprox."
    if selected_documents_count <= 4:
        return "8-15 min aprox."
    return "puede tardar más de 15 min"


def elapsed_seconds_for_row(row: sqlite3.Row | dict[str, object], now: datetime | None = None) -> int:
    current = now or datetime.now().replace(microsecond=0)
    started = parse_iso(row["started_at"] if isinstance(row, sqlite3.Row) else row.get("started_at"))
    created = parse_iso(row["created_at"] if isinstance(row, sqlite3.Row) else row.get("created_at"))
    finished = parse_iso(row["finished_at"] if isinstance(row, sqlite3.Row) else row.get("finished_at"))
    begin = started or created
    if not begin:
        return 0
    end = finished or current
    return max(0, int((end - begin).total_seconds()))


def human_stage(value: object, status: object = "") -> str:
    stage = str(value or "").strip()
    if not stage:
        stage = str(status or "").strip()
    labels = {
        "pending": "En cola",
        "queued": "En cola",
        "deferred": "En espera",
        "preparing_workspace": "Preparando documentos",
        "extracting_text": "Extrayendo texto",
        "launching_provider": "Preparando proveedor",
        "running_codex": "Ejecutando Codex",
        "validating_result": "Validando resultado",
        "saving_summary": "Guardando ficha IA",
        "completed": "Completado",
        "error": "Error",
        "cancelled": "Cancelado",
        "stale": "Atascado",
        "processing": "Procesando",
    }
    return labels.get(stage, stage.replace("_", " ").strip().capitalize() or "Sin estado")


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
    selected_count = len(selected_documents)
    estimate = estimate_seconds_for_job(provider, selected_count)
    cur = conn.execute(
        """
        INSERT INTO ai_analysis_jobs (
            licitacion_id, document_hash, status, provider, model, requested_by,
            created_at, error_code, error_message, selected_documents_json, attempts,
            progress_stage, progress_message, estimated_seconds, cancel_requested
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 0)
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
            status if status in {"pending", "queued", "deferred"} else "",
            "Análisis IA en cola." if status in {"pending", "queued", "deferred"} else "",
            estimate,
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
        SET status = 'processing',
            started_at = ?,
            attempts = COALESCE(attempts, 0) + 1,
            progress_stage = 'preparing_workspace',
            progress_message = 'Preparando carpeta temporal',
            progress_percent = 5,
            heartbeat_at = ?,
            cancel_requested = 0
        WHERE id = ?
          AND status IN ('pending', 'queued', 'deferred')
          AND (dismissed_at IS NULL OR dismissed_at = '')
        """,
        (timestamp, timestamp, job_id),
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


def touch_job_progress(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    stage: str,
    message: str,
    percent: int | None = None,
    worker_pid: int | None = None,
) -> None:
    fields: dict[str, object] = {
        "progress_stage": stage,
        "progress_message": message,
        "heartbeat_at": now_iso(),
    }
    if percent is not None:
        fields["progress_percent"] = max(0, min(100, int(percent)))
    if worker_pid is not None:
        fields["worker_pid"] = worker_pid
    update_job(conn, job_id, **fields)


def cancel_job(conn: sqlite3.Connection, job_id: int) -> dict[str, object]:
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job IA no encontrado")
    status = str(row["status"] or "")
    if status in {"pending", "queued", "deferred"}:
        update_job(
            conn,
            job_id,
            status="cancelled",
            finished_at=now_iso(),
            progress_stage="cancelled",
            progress_message="Cancelado antes de iniciar.",
            cancel_requested=1,
            error_code="CANCELLED",
            error_message="Análisis IA cancelado por el usuario.",
        )
        return {"ok": True, "message": "Análisis IA cancelado."}
    if status == "processing":
        update_job(
            conn,
            job_id,
            cancel_requested=1,
            progress_message="Cancelación solicitada. El proceso puede finalizar cuando termine la fase actual.",
            heartbeat_at=now_iso(),
        )
        return {"ok": True, "message": "Cancelación solicitada. El proceso puede finalizar cuando termine la fase actual."}
    return {"ok": False, "message": "El job ya no se puede cancelar."}


def dismiss_job(conn: sqlite3.Connection, job_id: int, dismissed_by: str = "") -> None:
    row = conn.execute("SELECT id FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job IA no encontrado")
    update_job(conn, job_id, dismissed_at=now_iso(), dismissed_by=dismissed_by or "ui")


def mark_stale_jobs_in_conn(conn: sqlite3.Connection, *, processing_timeout_seconds: int, pending_timeout_minutes: int = 30) -> int:
    now = datetime.now().replace(microsecond=0)
    heartbeat_threshold = (now - timedelta(seconds=max(60, processing_timeout_seconds))).isoformat()
    pending_threshold = (now - timedelta(minutes=max(5, pending_timeout_minutes))).isoformat()
    processing = conn.execute(
        """
        SELECT id FROM ai_analysis_jobs
        WHERE status = 'processing'
          AND COALESCE(NULLIF(heartbeat_at, ''), started_at, created_at) < ?
          AND (dismissed_at IS NULL OR dismissed_at = '')
        """,
        (heartbeat_threshold,),
    ).fetchall()
    pending = conn.execute(
        """
        SELECT id FROM ai_analysis_jobs
        WHERE status IN ('pending', 'queued', 'deferred')
          AND created_at < ?
          AND (dismissed_at IS NULL OR dismissed_at = '')
        """,
        (pending_threshold,),
    ).fetchall()
    for row in processing:
        update_job(
            conn,
            int(row["id"]),
            status="error",
            finished_at=now.isoformat(),
            error_code="STALE_JOB",
            error_message="Job marcado como atascado por falta de actividad reciente.",
            progress_stage="stale",
            progress_message="Atascado por falta de heartbeat reciente.",
        )
    for row in pending:
        update_job(
            conn,
            int(row["id"]),
            status="error",
            finished_at=now.isoformat(),
            error_code="STALE_PENDING_JOB",
            error_message="Job pendiente marcado como atascado porque no llegó a arrancar.",
            progress_stage="stale",
            progress_message="Pendiente atascado sin worker.",
        )
    return len(processing) + len(pending)


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
