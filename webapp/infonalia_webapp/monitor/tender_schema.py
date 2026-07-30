from __future__ import annotations

import sqlite3
from datetime import datetime


SETTING_DEFAULTS: dict[str, str] = {
    "automatic_enabled": "0",
    "future_frequency": "manual",
    "future_time": "",
    "ai_enabled": "0",
    "ai_timeout_seconds": "900",
    "download_retries": "2",
    "notification_retries": "2",
    "lease_minutes": "60",
    "document_ai_categories": "acta,resolucion,informe,requerimiento,adjudicacion,exclusion",
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_tender_monitor_schema(conn: sqlite3.Connection) -> None:
    """Create the additive, idempotent schema for the real tender monitor.

    Follow-up state deliberately has no SQLite flag here. The physical
    ``EnSeguimiento.llangon`` marker remains the only source of truth.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            requested_by TEXT,
            requested_licitacion_id INTEGER,
            status TEXT NOT NULL,
            created_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            heartbeat_at TEXT,
            current_licitacion_id INTEGER,
            total_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            no_changes_count INTEGER NOT NULL DEFAULT 0,
            changes_count INTEGER NOT NULL DEFAULT 0,
            baseline_count INTEGER NOT NULL DEFAULT 0,
            waiting_ai_count INTEGER NOT NULL DEFAULT 0,
            notified_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            incident_count INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (requested_licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (current_licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL,
            licitacion_id INTEGER NOT NULL,
            platform TEXT,
            status TEXT NOT NULL,
            preparation_status TEXT NOT NULL DEFAULT 'pending',
            preparation_reason TEXT,
            previous_snapshot_id INTEGER,
            current_snapshot_id INTEGER,
            batch_id INTEGER,
            ai_status TEXT NOT NULL DEFAULT 'not_required',
            notification_status TEXT NOT NULL DEFAULT 'not_required',
            started_at TEXT,
            finished_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            error_phase TEXT,
            error_code TEXT,
            error_message TEXT,
            log_json TEXT NOT NULL DEFAULT '[]',
            UNIQUE(cycle_id, licitacion_id),
            FOREIGN KEY (cycle_id) REFERENCES tender_monitor_cycles(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            completeness_json TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            source TEXT NOT NULL,
            execution_id INTEGER,
            created_at TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            UNIQUE(licitacion_id, fingerprint),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (execution_id) REFERENCES tender_monitor_executions(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_baselines (
            licitacion_id INTEGER PRIMARY KEY,
            snapshot_id INTEGER NOT NULL,
            execution_id INTEGER,
            reason TEXT NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (snapshot_id) REFERENCES tender_monitor_snapshots(id),
            FOREIGN KEY (execution_id) REFERENCES tender_monitor_executions(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL,
            execution_id INTEGER NOT NULL UNIQUE,
            licitacion_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            previous_snapshot_id INTEGER NOT NULL,
            current_snapshot_id INTEGER NOT NULL,
            difference_fingerprint TEXT NOT NULL,
            summary TEXT,
            ai_decision TEXT NOT NULL DEFAULT 'not_required',
            ai_status TEXT NOT NULL DEFAULT 'not_required',
            notification_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            notified_at TEXT,
            UNIQUE(licitacion_id, difference_fingerprint),
            FOREIGN KEY (cycle_id) REFERENCES tender_monitor_cycles(id),
            FOREIGN KEY (execution_id) REFERENCES tender_monitor_executions(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (previous_snapshot_id) REFERENCES tender_monitor_snapshots(id),
            FOREIGN KEY (current_snapshot_id) REFERENCES tender_monitor_snapshots(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_differences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            stable_key TEXT NOT NULL,
            block_name TEXT NOT NULL,
            change_type TEXT NOT NULL,
            item_type TEXT NOT NULL,
            item_key TEXT NOT NULL,
            title TEXT,
            old_value_json TEXT,
            new_value_json TEXT,
            ai_candidate INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(batch_id, stable_key),
            FOREIGN KEY (batch_id) REFERENCES tender_monitor_batches(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_ai_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            ai_job_id INTEGER,
            document_fingerprint TEXT NOT NULL,
            selected_paths_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            started_at TEXT,
            finished_at TEXT,
            error_message TEXT,
            UNIQUE(batch_id, document_fingerprint),
            FOREIGN KEY (batch_id) REFERENCES tender_monitor_batches(id),
            FOREIGN KEY (ai_job_id) REFERENCES ai_analysis_jobs(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            username TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            attempted_at TEXT,
            sent_at TEXT,
            next_attempt_at TEXT,
            external_id TEXT,
            error_message TEXT,
            FOREIGN KEY (batch_id) REFERENCES tender_monitor_batches(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL,
            execution_id INTEGER,
            licitacion_id INTEGER,
            phase TEXT NOT NULL,
            code TEXT NOT NULL,
            summary TEXT NOT NULL,
            technical_detail TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL DEFAULT 'recorded',
            dedupe_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(cycle_id, dedupe_key),
            FOREIGN KEY (cycle_id) REFERENCES tender_monitor_cycles(id),
            FOREIGN KEY (execution_id) REFERENCES tender_monitor_executions(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_incident_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL UNIQUE,
            recipient TEXT,
            subject TEXT,
            body_text TEXT,
            body_html TEXT,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            attempted_at TEXT,
            sent_at TEXT,
            error_message TEXT,
            FOREIGN KEY (cycle_id) REFERENCES tender_monitor_cycles(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_leases (
            lease_key TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            heartbeat_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tender_monitor_recipients (
            username TEXT PRIMARY KEY,
            email_enabled INTEGER NOT NULL DEFAULT 0,
            telegram_enabled INTEGER NOT NULL DEFAULT 0,
            incident_admin INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            updated_by TEXT,
            FOREIGN KEY (username) REFERENCES usuarios(username)
        )
        """
    )

    cycle_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(tender_monitor_cycles)")}
    additive_cycle_columns = {
        "created_at": "TEXT",
        "worker_launcher_pid": "INTEGER",
        "worker_pid": "INTEGER",
        "worker_started_at": "TEXT",
        "worker_finished_at": "TEXT",
        "worker_exit_code": "INTEGER",
        "worker_log_path": "TEXT",
    }
    for column, definition in additive_cycle_columns.items():
        if column not in cycle_columns:
            conn.execute(f"ALTER TABLE tender_monitor_cycles ADD COLUMN {column} {definition}")
    conn.execute(
        "UPDATE tender_monitor_cycles SET created_at = COALESCE(created_at, started_at, ?) WHERE created_at IS NULL",
        (_now_iso(),),
    )

    indexes = (
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_cycles_started ON tender_monitor_cycles(started_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_cycles_status ON tender_monitor_cycles(status, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_executions_licitacion ON tender_monitor_executions(licitacion_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_executions_status ON tender_monitor_executions(status, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_snapshots_licitacion ON tender_monitor_snapshots(licitacion_id, confirmed_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_baselines_snapshot ON tender_monitor_baselines(snapshot_id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_batches_licitacion ON tender_monitor_batches(licitacion_id, created_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_differences_batch ON tender_monitor_differences(batch_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_notifications_status ON tender_monitor_notifications(status, next_attempt_at)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_incidents_cycle ON tender_monitor_incidents(cycle_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_tender_monitor_leases_expires ON tender_monitor_leases(expires_at)",
    )
    for statement in indexes:
        conn.execute(statement)

    timestamp = _now_iso()
    for key, value in SETTING_DEFAULTS.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO tender_monitor_settings (key, value, updated_at, updated_by)
            VALUES (?, ?, ?, 'system')
            """,
            (key, value, timestamp),
        )

    # Backfill only states that a real monitor execution confirmed. Historical
    # normal_download_import rows that were never reviewed are deliberately
    # excluded so a direct download cannot silently consume future novelty.
    licitacion_ids = conn.execute(
        """
        SELECT DISTINCT snapshots.licitacion_id
        FROM tender_monitor_snapshots AS snapshots
        LEFT JOIN tender_monitor_baselines AS baselines
          ON baselines.licitacion_id = snapshots.licitacion_id
        WHERE baselines.licitacion_id IS NULL
        """
    ).fetchall()
    confirmed_statuses = (
        "baseline_rebuilt",
        "no_changes",
        "changes",
        "notified",
        "no_recipients",
        "notification_failed",
        "partial",
    )
    status_placeholders = ",".join("?" for _ in confirmed_statuses)
    for row in licitacion_ids:
        licitacion_id = int(row[0])
        candidate = conn.execute(
            f"""
            SELECT s.id AS snapshot_id, e.id AS execution_id,
                   COALESCE(e.finished_at, s.confirmed_at) AS confirmed_at
            FROM tender_monitor_snapshots AS s
            LEFT JOIN tender_monitor_executions AS e
              ON e.current_snapshot_id = s.id
             AND e.status IN ({status_placeholders})
            WHERE s.licitacion_id = ?
              AND (s.source IN ('monitor', 'baseline_rebuilt') OR e.id IS NOT NULL)
            ORDER BY COALESCE(e.finished_at, s.confirmed_at) DESC, s.id DESC, e.id DESC
            LIMIT 1
            """,
            (*confirmed_statuses, licitacion_id),
        ).fetchone()
        if candidate:
            conn.execute(
                """
                INSERT OR IGNORE INTO tender_monitor_baselines (
                    licitacion_id, snapshot_id, execution_id, reason, schema_version, updated_at
                ) VALUES (?, ?, ?, 'migration', 1, ?)
                """,
                (licitacion_id, int(candidate["snapshot_id"] if isinstance(candidate, sqlite3.Row) else candidate[0]),
                 candidate["execution_id"] if isinstance(candidate, sqlite3.Row) else candidate[1],
                 str(candidate["confirmed_at"] if isinstance(candidate, sqlite3.Row) else candidate[2]) or timestamp),
            )
