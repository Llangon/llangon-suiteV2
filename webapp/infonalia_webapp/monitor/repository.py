from __future__ import annotations

import json
import sqlite3
from pathlib import Path


TASK_TYPE_LICITACIONES = "licitaciones"
TASK_TYPE_RESUMEN_AGENDA = "resumen_agenda"
TASK_TYPE_AGENDA_PENDIENTES_DIARIA = "agenda_pendientes_diaria"
TASK_TYPE_AGENDA_DIARIA = "agenda_diaria"
TASK_TYPE_AGENDA_SEMANAL = "agenda_semanal"
TASK_TYPE_AVISO_VENCIMIENTO_7D = "aviso_vencimiento_7d"
TASK_TYPE_AVISO_VENCIMIENTO_3D = "aviso_vencimiento_3d"
TASK_TYPE_AVISO_VENCIMIENTO_1D = "aviso_vencimiento_1d"
TASK_TYPE_AVISO_VENCIMIENTO_HOY = "aviso_vencimiento_hoy"
TASK_TYPE_MONITOR_LICITACIONES = "monitor_licitaciones"
TASK_TYPE_INFONALIA_MAIL_IMPORT = "infonalia_mail_import"
TASK_TYPE_EMAIL_ACTIONS_PROCESSOR = "email_actions_processor"
TASK_TYPE_AVISOS_VENCIMIENTOS = "avisos_vencimientos"
TASK_TYPE_TAREAS_PENDIENTES = "tareas_pendientes"
TASK_TYPE_OTRO = "otro"
TASK_TYPES = {
    TASK_TYPE_LICITACIONES,
    TASK_TYPE_RESUMEN_AGENDA,
    TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
    TASK_TYPE_AGENDA_DIARIA,
    TASK_TYPE_AGENDA_SEMANAL,
    TASK_TYPE_AVISO_VENCIMIENTO_7D,
    TASK_TYPE_AVISO_VENCIMIENTO_3D,
    TASK_TYPE_AVISO_VENCIMIENTO_1D,
    TASK_TYPE_AVISO_VENCIMIENTO_HOY,
    TASK_TYPE_MONITOR_LICITACIONES,
    TASK_TYPE_INFONALIA_MAIL_IMPORT,
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
    TASK_TYPE_AVISOS_VENCIMIENTOS,
    TASK_TYPE_TAREAS_PENDIENTES,
    TASK_TYPE_OTRO,
}


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_monitor_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "licitaciones", "seguimiento_activo", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "licitaciones", "seguimiento_ultimo_check", "TEXT")
    ensure_column(conn, "licitaciones", "seguimiento_ultima_sync", "TEXT")
    ensure_column(conn, "licitaciones", "seguimiento_marker_path", "TEXT")
    ensure_column(conn, "licitaciones", "seguimiento_marker_warning", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL DEFAULT 'licitaciones',
            mode TEXT NOT NULL,
            root_path TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            dry_run INTEGER NOT NULL DEFAULT 0,
            schedule_key TEXT,
            found_markers_count INTEGER NOT NULL DEFAULT 0,
            route_updates_count INTEGER NOT NULL DEFAULT 0,
            followed_count INTEGER NOT NULL DEFAULT 0,
            folders_checked_count INTEGER NOT NULL DEFAULT 0,
            folders_repaired_count INTEGER NOT NULL DEFAULT 0,
            folders_broken_count INTEGER NOT NULL DEFAULT 0,
            platforms_checked_count INTEGER NOT NULL DEFAULT 0,
            changes_detected_count INTEGER NOT NULL DEFAULT 0,
            emails_prepared_count INTEGER NOT NULL DEFAULT 0,
            emails_sent_count INTEGER NOT NULL DEFAULT 0,
            inventory_files_count INTEGER NOT NULL DEFAULT 0,
            conflicts_count INTEGER NOT NULL DEFAULT 0,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            processed_items_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            details_json TEXT
        )
        """
    )
    for column, definition in {
        "task_type": "TEXT NOT NULL DEFAULT 'licitaciones'",
        "schedule_key": "TEXT",
        "folders_checked_count": "INTEGER NOT NULL DEFAULT 0",
        "folders_repaired_count": "INTEGER NOT NULL DEFAULT 0",
        "folders_broken_count": "INTEGER NOT NULL DEFAULT 0",
        "platforms_checked_count": "INTEGER NOT NULL DEFAULT 0",
        "changes_detected_count": "INTEGER NOT NULL DEFAULT 0",
        "emails_prepared_count": "INTEGER NOT NULL DEFAULT 0",
        "emails_sent_count": "INTEGER NOT NULL DEFAULT 0",
        "processed_items_count": "INTEGER NOT NULL DEFAULT 0",
        "details_json": "TEXT",
    }.items():
        ensure_column(conn, "monitor_runs", column, definition)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_monitor_runs_started ON monitor_runs(started_at)")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_monitor_runs_schedule
        ON monitor_runs(task_type, schedule_key, status)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licitacion_file_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            folder_path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            extension TEXT,
            file_type TEXT,
            folder_type TEXT,
            is_relevant INTEGER NOT NULL DEFAULT 1,
            is_system_file INTEGER NOT NULL DEFAULT 0,
            size_bytes INTEGER,
            modified_at TEXT,
            discovered_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            checksum TEXT,
            is_missing INTEGER NOT NULL DEFAULT 0,
            missing_since TEXT,
            source TEXT NOT NULL DEFAULT 'local_dropbox',
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    ensure_column(conn, "licitacion_file_inventory", "folder_type", "TEXT")
    ensure_column(conn, "licitacion_file_inventory", "is_relevant", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "licitacion_file_inventory", "is_system_file", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "licitacion_file_inventory", "missing_since", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licitacion_file_inventory_unique
        ON licitacion_file_inventory(licitacion_id, relative_path, source)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_licitacion_file_inventory_licitacion
        ON licitacion_file_inventory(licitacion_id, is_missing)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licitacion_seguimiento_novedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            detected_at TEXT NOT NULL,
            source TEXT,
            title TEXT,
            summary TEXT,
            change_type TEXT,
            file_name TEXT,
            file_path TEXT,
            status TEXT NOT NULL DEFAULT 'nueva',
            raw_data_json TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_vencimiento_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            notice_level TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            event_key TEXT NOT NULL,
            due_at TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            monitor_run_id INTEGER NOT NULL,
            recipient TEXT,
            subject TEXT,
            status TEXT NOT NULL DEFAULT 'sent',
            FOREIGN KEY (monitor_run_id) REFERENCES monitor_runs(id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_monitor_vencimiento_alerts_unique
        ON monitor_vencimiento_alerts(notice_level, event_key, due_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_monitor_vencimiento_alerts_run
        ON monitor_vencimiento_alerts(monitor_run_id)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_automation_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            schedule_key TEXT NOT NULL,
            status TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            lease_until TEXT,
            completed_at TEXT,
            run_id INTEGER,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            last_error TEXT,
            email_attempted_at TEXT,
            worker_id TEXT,
            UNIQUE(task_type, schedule_key)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_monitor_automation_claims_status
        ON monitor_automation_claims(status, lease_until)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_scheduler_heartbeat (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            checked_at TEXT NOT NULL,
            status TEXT NOT NULL,
            next_task TEXT,
            next_run_at TEXT,
            timezone TEXT,
            last_error TEXT,
            worker_id TEXT
        )
        """
    )


def connect_db(db_path: str | Path, read_only: bool = False) -> sqlite3.Connection:
    db_text = str(db_path)
    if read_only and db_text != ":memory:":
        path = Path(db_text)
        if not path.exists():
            raise FileNotFoundError(f"No existe la base de datos: {path}")
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_text)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_licitaciones(conn: sqlite3.Connection, ids: list[int]) -> dict[int, sqlite3.Row]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT * FROM licitaciones WHERE id IN ({placeholders})", ids).fetchall()
    return {int(row["id"]): row for row in rows}


def row_value(row: sqlite3.Row, key: str, default: object = None) -> object:
    if key not in row.keys():
        return default
    return row[key]


def monitor_run_to_dict(row: sqlite3.Row, *, include_details: bool = False) -> dict[str, object]:
    item = {
        "id": row["id"],
        "task_type": row_value(row, "task_type", TASK_TYPE_LICITACIONES) or TASK_TYPE_LICITACIONES,
        "mode": row["mode"],
        "root_path": row["root_path"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"] or "",
        "status": row["status"],
        "dry_run": bool(row["dry_run"]),
        "schedule_key": row_value(row, "schedule_key", "") or "",
        "found_markers_count": row["found_markers_count"],
        "route_updates_count": row["route_updates_count"],
        "followed_count": row["followed_count"],
        "folders_checked_count": row_value(row, "folders_checked_count", 0),
        "folders_repaired_count": row_value(row, "folders_repaired_count", row["route_updates_count"]),
        "folders_broken_count": row_value(row, "folders_broken_count", 0),
        "platforms_checked_count": row_value(row, "platforms_checked_count", 0),
        "changes_detected_count": row_value(row, "changes_detected_count", 0),
        "emails_prepared_count": row_value(row, "emails_prepared_count", 0),
        "emails_sent_count": row_value(row, "emails_sent_count", 0),
        "inventory_files_count": row["inventory_files_count"],
        "conflicts_count": row["conflicts_count"],
        "warnings_count": row["warnings_count"],
        "processed_items_count": row_value(row, "processed_items_count", 0),
        "error_message": row["error_message"] or "",
    }
    if include_details:
        try:
            item["details"] = json.loads(row_value(row, "details_json", "") or "{}")
        except json.JSONDecodeError:
            item["details"] = {}
    return item


def normalize_task_type(value: object, *, default: str = TASK_TYPE_LICITACIONES) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in TASK_TYPES else default


def list_monitor_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    task_type: str = "",
) -> list[dict[str, object]]:
    clean_task_type = normalize_task_type(task_type, default="") if task_type else ""
    where = "WHERE task_type = ?" if clean_task_type else ""
    params: list[object] = []
    if clean_task_type:
        params.append(clean_task_type)
    params.append(max(1, min(int(limit or 50), 200)))
    rows = conn.execute(
        f"""
        SELECT *
        FROM monitor_runs
        {where}
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [monitor_run_to_dict(row) for row in rows]


def get_monitor_run(conn: sqlite3.Connection, run_id: int) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM monitor_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return monitor_run_to_dict(row, include_details=True)
