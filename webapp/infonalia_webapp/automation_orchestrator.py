from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

try:
    from .backup_sqlite import configured_backup_dir, create_backup
    from .full_backup import FullBackupError, create_full_backup, load_config_from_env
    from .monitor.repository import (
        TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
        TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
        TASK_TYPE_FILE_INVENTORY,
        TASK_TYPE_INFONALIA_MAIL_IMPORT,
        TASK_TYPE_MONITOR_LICITACIONES,
        connect_db,
        ensure_monitor_schema,
    )
    from .monitor.scheduler import _run_mail_interval_jobs, configured_agenda_pending_recipients
    from .monitor.service import (
        AUTOMATION_MODE_AUTOMATIC,
        AUTOMATION_MODE_MANUAL,
        localize_scheduler_datetime,
        run_automation_task,
    )
    from .normalization import bool_text, clean_text
    from .operational_settings import effective_bool, effective_int
    from .dropbox_paths import preferred_dropbox_base_path
except ImportError:  # pragma: no cover
    from backup_sqlite import configured_backup_dir, create_backup
    from full_backup import FullBackupError, create_full_backup, load_config_from_env
    from monitor.repository import (
        TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
        TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
        TASK_TYPE_FILE_INVENTORY,
        TASK_TYPE_INFONALIA_MAIL_IMPORT,
        TASK_TYPE_MONITOR_LICITACIONES,
        connect_db,
        ensure_monitor_schema,
    )
    from monitor.scheduler import _run_mail_interval_jobs, configured_agenda_pending_recipients
    from monitor.service import (
        AUTOMATION_MODE_AUTOMATIC,
        AUTOMATION_MODE_MANUAL,
        localize_scheduler_datetime,
        run_automation_task,
    )
    from normalization import bool_text, clean_text
    from operational_settings import effective_bool, effective_int
    from dropbox_paths import preferred_dropbox_base_path


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
DEFAULT_DB_PATH = APP_ROOT / "data" / "infonalia.db"
DEFAULT_TZ = "Europe/Madrid"
GLOBAL_LOCK_KEY = "scheduler:global"
GLOBAL_LOCK_TTL_MINUTES = 15
DEFAULT_TASK_LOCK_TTL_MINUTES = 60
CRITICAL_TASK_LOCK_TTL_MINUTES = 180
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
TASK_INTERVAL_SETTING_KEYS = {
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR: "email_actions_poll_minutes",
    TASK_TYPE_INFONALIA_MAIL_IMPORT: "infonalia_import_poll_minutes",
}


@dataclass(frozen=True)
class AutomationDefinition:
    key: str
    name: str
    description: str
    schedule_type: str
    default_enabled: bool
    interval_minutes: int | None = None
    daily_time: str | None = None
    weekdays_only: bool = False
    manual_allowed: bool = True
    critical: bool = False
    prevents_suspend: bool = False
    priority: int = 100
    env_enabled: str | None = None
    env_interval: str | None = None
    env_time: str | None = None


AUTOMATIONS: tuple[AutomationDefinition, ...] = (
    AutomationDefinition(
        key=TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
        name="Acciones por correo",
        description="Procesa respuestas LLANGON_CMD y encola descargas cuando procede.",
        schedule_type="interval",
        default_enabled=True,
        interval_minutes=10,
        priority=10,
        env_enabled="LLANGON_EMAIL_ACTIONS_ENABLED",
        env_interval="LLANGON_EMAIL_ACTIONS_POLL_MINUTES",
    ),
    AutomationDefinition(
        key=TASK_TYPE_INFONALIA_MAIL_IMPORT,
        name="Importación Infonalia",
        description="Lee el buzón Infonalia e importa nuevos días y licitaciones.",
        schedule_type="interval",
        default_enabled=True,
        interval_minutes=30,
        priority=20,
        env_enabled="LLANGON_INFONALIA_IMPORT_ENABLED",
        env_interval="LLANGON_INFONALIA_IMPORT_POLL_MINUTES",
    ),
    AutomationDefinition(
        key=TASK_TYPE_FILE_INVENTORY,
        name="Inventario Dropbox",
        description="Actualiza inventario de ficheros y reconciliación de rutas.",
        schedule_type="interval",
        default_enabled=True,
        interval_minutes=240,
        priority=80,
        env_enabled="LLANGON_FILE_INVENTORY_ENABLED",
        env_interval="LLANGON_FILE_INVENTORY_POLL_MINUTES",
    ),
    AutomationDefinition(
        key=TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
        name="Agenda diaria",
        description="Envía el resumen diario de tareas y vencimientos pendientes.",
        schedule_type="daily_time",
        default_enabled=True,
        daily_time="08:00",
        weekdays_only=True,
        priority=30,
        env_enabled="MONITOR_AGENDA_PENDING_DAILY_ENABLED",
        env_time="MONITOR_AGENDA_PENDING_DAILY_TIME",
    ),
    AutomationDefinition(
        key="full_backup",
        name="Backup completo",
        description="Crea copia SQLite y backup privado restaurable.",
        schedule_type="daily_time",
        default_enabled=True,
        daily_time="16:00",
        critical=True,
        prevents_suspend=True,
        priority=40,
        env_enabled="LLANGON_FULL_BACKUP_ENABLED",
        env_time="LLANGON_FULL_BACKUP_TIME",
    ),
    AutomationDefinition(
        key="night_suspend",
        name="Suspensión nocturna",
        description="Suspende Windows si no hay actividad ni trabajos críticos.",
        schedule_type="daily_time",
        default_enabled=True,
        daily_time="21:00",
        manual_allowed=True,
        priority=200,
        env_enabled="LLANGON_NIGHT_SUSPEND_ENABLED",
        env_time="LLANGON_NIGHT_SUSPEND_TIME",
    ),
    AutomationDefinition(
        key=TASK_TYPE_MONITOR_LICITACIONES,
        name="Monitor licitaciones",
        description="Monitor futuro de novedades en plataformas. Se mantiene desactivado.",
        schedule_type="manual",
        default_enabled=False,
        manual_allowed=True,
        priority=300,
        env_enabled="MONITOR_LICITACIONES_SCHEDULE_ENABLED",
    ),
    AutomationDefinition(
        key="telegram_status",
        name="Telegram",
        description="Comprobación manual de estado de Telegram.",
        schedule_type="event",
        default_enabled=True,
        manual_allowed=True,
        priority=400,
        env_enabled="LLANGON_TELEGRAM_ENABLED",
    ),
)


def now_local(value: datetime | None = None) -> datetime:
    return localize_scheduler_datetime(value)


def now_iso(value: datetime | None = None) -> str:
    return now_local(value).replace(microsecond=0).isoformat()


def parse_iso(value: object) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return now_local(datetime.fromisoformat(text))
    except ValueError:
        return None


def parse_hhmm(value: object, fallback: str) -> str:
    text = clean_text(value) or fallback
    try:
        hour, minute = [int(part) for part in text.split(":", 1)]
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    except Exception:
        pass
    return fallback


def env_bool(name: str | None, default: bool) -> bool:
    if not name:
        return default
    raw = os.environ.get(name)
    if clean_text(raw) == "":
        return default
    return bool_text(raw)


def env_minutes(name: str | None, default: int) -> int:
    if not name:
        return default
    try:
        return max(1, int(os.environ.get(name, str(default)) or default))
    except ValueError:
        return default


def ensure_automation_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_tasks (
            key TEXT PRIMARY KEY,
            enabled INTEGER,
            schedule_value TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_key TEXT NOT NULL,
            task_name TEXT NOT NULL,
            source TEXT NOT NULL,
            triggered_by TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            summary TEXT,
            error_message TEXT,
            details_json TEXT,
            lock_owner TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_locks (
            key TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            metadata_json TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_runs_task ON automation_runs(task_key, started_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_runs_status ON automation_runs(status, started_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_locks_expires ON automation_locks(expires_at)")
    seed_automation_tasks(conn)
    conn.commit()


def seed_automation_tasks(conn: sqlite3.Connection) -> None:
    stamp = now_iso()
    for definition in AUTOMATIONS:
        conn.execute(
            """
            INSERT OR IGNORE INTO automation_tasks (key, enabled, schedule_value, updated_at, updated_by)
            VALUES (?, NULL, NULL, ?, 'system')
            """,
            (definition.key, stamp),
        )


def automation_by_key(key: str) -> AutomationDefinition | None:
    clean = clean_text(key)
    return next((item for item in AUTOMATIONS if item.key == clean), None)


def task_override(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM automation_tasks WHERE key = ?", (key,)).fetchone()


def task_enabled(conn: sqlite3.Connection, definition: AutomationDefinition) -> bool:
    row = task_override(conn, definition.key)
    if row and row["enabled"] is not None:
        return bool(row["enabled"])
    return env_bool(definition.env_enabled, definition.default_enabled)


def task_schedule_value(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str:
    row = task_override(conn, definition.key)
    if row and clean_text(row["schedule_value"]):
        return clean_text(row["schedule_value"])
    if definition.schedule_type == "interval":
        setting_key = TASK_INTERVAL_SETTING_KEYS.get(definition.key)
        if setting_key:
            return str(effective_int(setting_key, definition.interval_minutes or 1, db_path=db_path, minimum=1))
        return str(env_minutes(definition.env_interval, definition.interval_minutes or 1))
    if definition.schedule_type == "daily_time":
        return parse_hhmm(os.environ.get(definition.env_time or ""), definition.daily_time or "00:00")
    return ""


def last_run(conn: sqlite3.Connection, key: str, *, automatic_only: bool = False) -> sqlite3.Row | None:
    sql = "SELECT * FROM automation_runs WHERE task_key = ?"
    params: list[object] = [key]
    if automatic_only:
        sql += " AND source IN ('automatic', 'keeper_tick', 'wake_tick')"
    sql += " ORDER BY id DESC LIMIT 1"
    return conn.execute(sql, params).fetchone()


def last_completed_for_day(conn: sqlite3.Connection, key: str, day: date) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM automation_runs
        WHERE task_key = ?
          AND status = ?
          AND source IN ('automatic', 'keeper_tick', 'wake_tick')
          AND substr(started_at, 1, 10) = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (key, STATUS_COMPLETED, day.isoformat()),
    ).fetchone()


def next_daily_time(target: datetime, hhmm: str, *, weekdays_only: bool = False) -> datetime:
    hour, minute = [int(part) for part in hhmm.split(":", 1)]
    for offset in range(0, 8):
        day = target.date() + timedelta(days=offset)
        if weekdays_only and day.weekday() >= 5:
            continue
        candidate = datetime.combine(day, dt_time(hour, minute), tzinfo=target.tzinfo)
        if candidate > target:
            return candidate
    return target + timedelta(days=1)


def previous_daily_slot(target: datetime, hhmm: str) -> datetime:
    hour, minute = [int(part) for part in hhmm.split(":", 1)]
    slot = datetime.combine(target.date(), dt_time(hour, minute), tzinfo=target.tzinfo)
    if slot > target:
        slot -= timedelta(days=1)
    return slot


def compute_next_run(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    current: datetime | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str:
    now = now_local(current)
    if not task_enabled(conn, definition):
        return ""
    if definition.schedule_type == "interval":
        minutes = int(task_schedule_value(conn, definition, db_path=db_path) or definition.interval_minutes or 1)
        row = last_run(conn, definition.key, automatic_only=True)
        started = parse_iso(row["started_at"]) if row else None
        candidate = (started + timedelta(minutes=minutes)) if started else now
        return max(candidate, now).replace(microsecond=0).isoformat()
    if definition.schedule_type == "daily_time":
        return next_daily_time(
            now,
            task_schedule_value(conn, definition, db_path=db_path) or definition.daily_time or "00:00",
            weekdays_only=definition.weekdays_only,
        ).replace(microsecond=0).isoformat()
    return ""


def due_for_tick(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    current: datetime | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    now = now_local(current)
    if not task_enabled(conn, definition) or definition.schedule_type in {"manual", "event"}:
        return False
    if definition.schedule_type == "interval":
        minutes = int(task_schedule_value(conn, definition, db_path=db_path) or definition.interval_minutes or 1)
        row = last_run(conn, definition.key, automatic_only=True)
        if not row:
            return True
        started = parse_iso(row["started_at"])
        return not started or now - started >= timedelta(minutes=minutes)
    if definition.schedule_type == "daily_time":
        hhmm = task_schedule_value(conn, definition, db_path=db_path) or definition.daily_time or "00:00"
        if definition.weekdays_only and now.date().weekday() >= 5:
            return False
        slot = previous_daily_slot(now, hhmm)
        if slot.date() != now.date():
            return False
        return last_completed_for_day(conn, definition.key, slot.date()) is None
    return False


def lock_owner(source: str) -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{source}:{int(time.time())}"


def acquire_lock(
    conn: sqlite3.Connection,
    key: str,
    owner: str,
    *,
    ttl_minutes: int = 60,
    metadata: dict[str, object] | None = None,
    current: datetime | None = None,
) -> tuple[bool, dict[str, object]]:
    now = now_local(current)
    stamp = now.replace(microsecond=0).isoformat()
    expires = (now + timedelta(minutes=ttl_minutes)).replace(microsecond=0).isoformat()
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute("SELECT * FROM automation_locks WHERE key = ?", (key,)).fetchone()
    if existing and key == GLOBAL_LOCK_KEY:
        acquired_at = parse_iso(existing["acquired_at"])
        if acquired_at and now - acquired_at >= timedelta(minutes=GLOBAL_LOCK_TTL_MINUTES):
            existing = None
    if existing and clean_text(existing["expires_at"]) > stamp:
        conn.commit()
        return False, dict(existing)
    conn.execute(
        """
        INSERT INTO automation_locks (key, owner, acquired_at, expires_at, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            owner = excluded.owner,
            acquired_at = excluded.acquired_at,
            expires_at = excluded.expires_at,
            metadata_json = excluded.metadata_json
        """,
        (key, owner, stamp, expires, json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
    )
    conn.commit()
    return True, {"key": key, "owner": owner, "acquired_at": stamp, "expires_at": expires}


def release_lock(conn: sqlite3.Connection, key: str, owner: str) -> None:
    conn.execute("DELETE FROM automation_locks WHERE key = ? AND owner = ?", (key, owner))
    conn.commit()


def active_locks(conn: sqlite3.Connection, *, current: datetime | None = None) -> list[dict[str, object]]:
    stamp = now_iso(current)
    return [dict(row) for row in conn.execute(
        "SELECT * FROM automation_locks WHERE expires_at > ? ORDER BY acquired_at ASC",
        (stamp,),
    ).fetchall()]


def create_run(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    source: str,
    triggered_by: str = "",
    lock_owner_value: str = "",
    current: datetime | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO automation_runs (
            task_key, task_name, source, triggered_by, status, started_at, lock_owner
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (definition.key, definition.name, source, triggered_by, STATUS_RUNNING, now_iso(current), lock_owner_value),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    summary: str = "",
    error_message: str = "",
    details: dict[str, object] | None = None,
    current: datetime | None = None,
) -> None:
    finished = now_local(current)
    row = conn.execute("SELECT started_at FROM automation_runs WHERE id = ?", (run_id,)).fetchone()
    started = parse_iso(row["started_at"]) if row else None
    duration = (finished - started).total_seconds() if started else None
    conn.execute(
        """
        UPDATE automation_runs
        SET status = ?, finished_at = ?, duration_seconds = ?, summary = ?,
            error_message = ?, details_json = ?
        WHERE id = ?
        """,
        (
            status,
            finished.replace(microsecond=0).isoformat(),
            duration,
            clean_text(summary),
            clean_text(error_message),
            json.dumps(details or {}, ensure_ascii=False, sort_keys=True, default=str),
            run_id,
        ),
    )
    conn.commit()


def summarize_result(result: dict[str, object]) -> str:
    if clean_text(result.get("summary")):
        return clean_text(result.get("summary"))
    pieces = []
    for label, key in (
        ("procesados", "processed_items_count"),
        ("importados", "imported"),
        ("acciones", "processed"),
        ("emails", "emails_sent_count"),
        ("inventario", "inventory_files_count"),
        ("corregidas", "route_updates_count"),
    ):
        value = result.get(key)
        if value not in (None, "", 0):
            pieces.append(f"{label}: {value}")
    return "; ".join(pieces) or clean_text(result.get("message")) or "Ejecución finalizada."


def run_mail_interval_task(definition: AutomationDefinition, db_path: str | Path, current: datetime) -> dict[str, object]:
    previous: dict[str, str | None] = {}
    for item in AUTOMATIONS:
        if item.key in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR, TASK_TYPE_FILE_INVENTORY}:
            for env_name in (item.env_enabled, item.env_interval):
                if env_name:
                    previous[env_name] = os.environ.get(env_name)
    try:
        for item in AUTOMATIONS:
            if item.key in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR, TASK_TYPE_FILE_INVENTORY}:
                if item.env_enabled:
                    os.environ[item.env_enabled] = "1" if item.key == definition.key else "0"
                if item.env_interval:
                    os.environ[item.env_interval] = "1"
        reports = _run_mail_interval_jobs(db_path=db_path, current=current, dry_run=False)
    finally:
        for env_name, value in previous.items():
            if value is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = value
    return reports[0] if reports else {"task_type": definition.key, "status": STATUS_SKIPPED, "message": "No estaba vencida según el scheduler heredado."}


def run_full_backup(db_path: str | Path) -> dict[str, object]:
    sqlite_result = create_backup(Path(db_path), configured_backup_dir())
    full_result = create_full_backup(config=load_config_from_env())
    status = STATUS_COMPLETED if full_result.status == "success" else STATUS_SKIPPED
    warnings = list(full_result.manifest.get("warnings") or [])
    errors = list(full_result.manifest.get("errors") or [])
    if full_result.status == "failed":
        status = STATUS_FAILED
    return {
        "status": status,
        "sqlite_backup": str(sqlite_result.destination),
        "full_backup": str(full_result.zip_path or ""),
        "full_backup_status": full_result.status,
        "warnings": warnings,
        "errors": errors,
        "removed_old_backups": [str(item) for item in full_result.removed_old_backups],
        "summary": f"SQLite: {sqlite_result.destination.name}. Backup completo: {full_result.status}.",
    }


def blocking_work(conn: sqlite3.Connection) -> list[str]:
    blockers: list[str] = []
    locks = active_locks(conn)
    for item in locks:
        key = clean_text(item.get("key"))
        if key and key != GLOBAL_LOCK_KEY:
            blockers.append(f"lock activo: {key}")
    for table, label, statuses in (
        ("download_jobs", "descargas en curso", ("pending", "running", "processing")),
        ("ai_analysis_jobs", "análisis IA en curso", ("pending", "queued", "processing", "deferred")),
    ):
        try:
            placeholders = ",".join("?" for _ in statuses)
            row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ({placeholders})", statuses).fetchone()
            if row and int(row[0] or 0) > 0:
                blockers.append(f"{label}: {row[0]}")
        except sqlite3.Error:
            continue
    return blockers


def run_night_suspend(conn: sqlite3.Connection, *, manual: bool = False) -> dict[str, object]:
    blockers = blocking_work(conn)
    if blockers:
        return {"status": STATUS_SKIPPED, "summary": "Suspensión omitida por seguridad.", "blockers": blockers}
    script = PROJECT_ROOT / "scripts" / "windows" / "suspend_windows.ps1"
    if not script.exists():
        return {"status": STATUS_SKIPPED, "summary": "No existe suspend_windows.ps1.", "blockers": ["script no encontrado"]}
    skip_if_user_active = clean_text(os.environ.get("LLANGON_NIGHT_SUSPEND_SKIP_IF_USER_ACTIVE", "1")).lower() not in {"0", "false", "no"}
    command = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        f"-SkipIfUserActive:${str(skip_if_user_active).lower()}",
        "-LogPath",
        str(PROJECT_ROOT / "runtime" / "logs" / "night_suspend.log"),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode == 0:
        return {"status": STATUS_COMPLETED, "summary": "Solicitud de suspensión enviada o comprobación completada.", "output": output[-2000:]}
    return {"status": STATUS_SKIPPED, "summary": "Suspensión omitida o rechazada por Windows.", "returncode": completed.returncode, "output": output[-2000:]}


def execute_task(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    db_path: str | Path,
    source: str,
    triggered_by: str = "",
    current: datetime | None = None,
) -> dict[str, object]:
    current_dt = now_local(current)
    if definition.key in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR, TASK_TYPE_FILE_INVENTORY}:
        return run_mail_interval_task(definition, db_path, current_dt)
    if definition.key == TASK_TYPE_AGENDA_PENDIENTES_DIARIA:
        recipients = configured_agenda_pending_recipients(db_path)
        from . import app
        settings = app.get_settings()
        recipient = ",".join(recipients)
        return run_automation_task(
            TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
            dry_run=False,
            db_path=db_path,
            recipient=recipient,
            current=current_dt,
            trigger_mode=AUTOMATION_MODE_AUTOMATIC if source != "manual" else AUTOMATION_MODE_MANUAL,
            email_sender=lambda to, subject, body, html_body: app.send_monitor_email(
                to, subject, body, html_body, settings=settings
            ),
        )
    if definition.key == "full_backup":
        return run_full_backup(db_path)
    if definition.key == "night_suspend":
        return run_night_suspend(conn, manual=(source == "manual"))
    if definition.key == TASK_TYPE_MONITOR_LICITACIONES:
        return {"status": STATUS_SKIPPED, "summary": "Monitor licitaciones está desactivado por decisión operativa."}
    if definition.key == "telegram_status":
        return {"status": STATUS_COMPLETED, "summary": "Telegram está configurado." if env_bool("LLANGON_TELEGRAM_ENABLED", False) else "Telegram no está activo."}
    return {"status": STATUS_SKIPPED, "summary": "Automatización sin ejecutor asociado."}


def run_task(
    key: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "manual",
    triggered_by: str = "",
    current: datetime | None = None,
) -> dict[str, object]:
    definition = automation_by_key(key)
    if not definition:
        raise ValueError(f"Automatización no reconocida: {key}")
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_monitor_schema(conn)
    ensure_automation_schema(conn)
    owner = lock_owner(source)
    task_lock = f"task:{definition.key}"
    ttl = CRITICAL_TASK_LOCK_TTL_MINUTES if definition.prevents_suspend else DEFAULT_TASK_LOCK_TTL_MINUTES
    acquired, existing = acquire_lock(conn, task_lock, owner, ttl_minutes=ttl, metadata={"task": definition.key, "source": source}, current=current)
    if not acquired:
        return {"task_key": definition.key, "status": STATUS_SKIPPED, "summary": "Omitida: ya está en ejecución.", "lock": existing}
    run_id = create_run(conn, definition, source=source, triggered_by=triggered_by, lock_owner_value=owner, current=current)
    try:
        result = execute_task(conn, definition, db_path=db_path, source=source, triggered_by=triggered_by, current=current)
        status = clean_text(result.get("status")) or STATUS_COMPLETED
        if status not in {STATUS_COMPLETED, STATUS_FAILED, STATUS_SKIPPED, "completed_with_errors"}:
            status = STATUS_COMPLETED if not result.get("errors") else STATUS_FAILED
        error = clean_text(result.get("error_message") or result.get("error"))
        if error and status == STATUS_COMPLETED:
            status = STATUS_FAILED
        summary = summarize_result(result)
        finish_run(conn, run_id, status=status, summary=summary, error_message=error, details=result)
        return {"run_id": run_id, "task_key": definition.key, "status": status, "summary": summary, "result": result}
    except Exception as exc:
        finish_run(conn, run_id, status=STATUS_FAILED, summary="Falló la automatización.", error_message=str(exc), details={})
        return {"run_id": run_id, "task_key": definition.key, "status": STATUS_FAILED, "summary": "Falló la automatización.", "error_message": str(exc)}
    finally:
        release_lock(conn, task_lock, owner)
        conn.close()


def scheduler_tick(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "keeper_tick",
    triggered_by: str = "",
    current: datetime | None = None,
) -> dict[str, object]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_monitor_schema(conn)
    ensure_automation_schema(conn)
    owner = lock_owner(source)
    acquired, existing = acquire_lock(
        conn,
        GLOBAL_LOCK_KEY,
        owner,
        ttl_minutes=GLOBAL_LOCK_TTL_MINUTES,
        metadata={"source": source},
        current=current,
    )
    if not acquired:
        conn.close()
        return {"ok": True, "status": STATUS_SKIPPED, "message": "skipped: already running", "lock": existing}
    due = sorted(
        [definition for definition in AUTOMATIONS if due_for_tick(conn, definition, current=current, db_path=db_path)],
        key=lambda item: item.priority,
    )
    conn.commit()
    results: list[dict[str, object]] = []
    try:
        for definition in due:
            results.append(run_task(definition.key, db_path=db_path, source=source, triggered_by=triggered_by, current=current))
        return {"ok": True, "status": STATUS_COMPLETED, "source": source, "due_count": len(due), "results": results}
    finally:
        release_lock(conn, GLOBAL_LOCK_KEY, owner)
        conn.close()


def set_task_enabled(
    key: str,
    enabled: bool,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    updated_by: str = "",
) -> dict[str, object]:
    if not automation_by_key(key):
        raise ValueError(f"Automatización no reconocida: {key}")
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    conn.execute(
        """
        INSERT INTO automation_tasks (key, enabled, updated_at, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET enabled = excluded.enabled,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (key, 1 if enabled else 0, now_iso(), clean_text(updated_by)),
    )
    conn.commit()
    payload = task_payload(conn, automation_by_key(key), db_path=db_path)
    conn.close()
    return payload


def task_payload(
    conn: sqlite3.Connection,
    definition: AutomationDefinition | None,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, object]:
    if not definition:
        return {}
    row = last_run(conn, definition.key)
    running = conn.execute(
        "SELECT * FROM automation_runs WHERE task_key = ? AND status = ? ORDER BY id DESC LIMIT 1",
        (definition.key, STATUS_RUNNING),
    ).fetchone()
    enabled = task_enabled(conn, definition)
    schedule_value = task_schedule_value(conn, definition, db_path=db_path)
    return {
        "key": definition.key,
        "name": definition.name,
        "description": definition.description,
        "type": definition.schedule_type,
        "enabled": enabled,
        "schedule_value": schedule_value,
        "schedule_label": schedule_label(definition, schedule_value),
        "next_run": compute_next_run(conn, definition, db_path=db_path) if enabled else "",
        "last_run": dict(row) if row else None,
        "status": "running" if running else ("disabled" if not enabled else "idle"),
        "manual_allowed": definition.manual_allowed,
        "critical": definition.critical,
        "prevents_suspend": definition.prevents_suspend,
        "priority": definition.priority,
    }


def schedule_label(definition: AutomationDefinition, value: str) -> str:
    if definition.schedule_type == "interval":
        return f"Cada {value} minutos"
    if definition.schedule_type == "daily_time":
        suffix = " laborables" if definition.weekdays_only else " diario"
        return f"{value}{suffix}"
    if definition.schedule_type == "manual":
        return "Manual"
    return "Por evento"


def automation_tasks_payload(*, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    items = [task_payload(conn, definition, db_path=db_path) for definition in sorted(AUTOMATIONS, key=lambda item: item.priority)]
    conn.close()
    return items


def automation_runs_payload(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    task_key: str = "",
    status: str = "",
    limit: int = 100,
) -> list[dict[str, object]]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    clauses: list[str] = []
    params: list[object] = []
    if task_key:
        clauses.append("task_key = ?")
        params.append(task_key)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM automation_runs {where} ORDER BY id DESC LIMIT ?",
        (*params, max(1, min(500, int(limit or 100)))),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def queue_status(conn: sqlite3.Connection) -> dict[str, object]:
    result: dict[str, object] = {}
    for table, statuses in {
        "download_jobs": ("pending", "running", "failed", "completed"),
        "ai_analysis_jobs": ("pending", "queued", "processing", "deferred", "error", "completed"),
    }.items():
        try:
            rows = conn.execute(f"SELECT status, COUNT(*) count FROM {table} GROUP BY status").fetchall()
            counts = {row["status"]: row["count"] for row in rows}
            result[table] = {status: counts.get(status, 0) for status in statuses}
        except sqlite3.Error:
            result[table] = {"error": "tabla no disponible"}
    return result


def automation_status_payload(*, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, object]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    locks = active_locks(conn)
    tasks = [task_payload(conn, definition, db_path=db_path) for definition in sorted(AUTOMATIONS, key=lambda item: item.priority)]
    heartbeat = None
    try:
        heartbeat = conn.execute("SELECT * FROM monitor_scheduler_heartbeat WHERE id = 1").fetchone()
    except sqlite3.Error:
        heartbeat = None
    payload = {
        "server_time": now_iso(),
        "web": {"status": "ok"},
        "last_scheduler_tick": dict(heartbeat) if heartbeat else None,
        "scheduler_running": any(item["key"] == GLOBAL_LOCK_KEY for item in locks),
        "locks": locks,
        "tasks": tasks,
        "queues": queue_status(conn),
        "dropbox_base": str(preferred_dropbox_base_path() or ""),
        "smtp": {"configured": bool(os.environ.get("INFONALIA_SMTP_HOST") and os.environ.get("INFONALIA_SMTP_USER"))},
        "telegram": {"enabled": env_bool("LLANGON_TELEGRAM_ENABLED", False), "group_configured": bool(os.environ.get("LLANGON_TELEGRAM_GROUP_CHAT_ID"))},
        "imap": {
            "infonalia_enabled": effective_bool("infonalia_import_enabled", db_path=db_path),
            "actions_enabled": effective_bool("email_actions_enabled", db_path=db_path),
        },
    }
    conn.close()
    return payload


def windows_tasks_payload() -> dict[str, object]:
    names = [
        "LlangonSuite-KeeperTick",
        "LlangonSuite-WakeTick",
        "LlangonSuite-Web",
        "LlangonSuite-Scheduler",
        "LlangonSuite-Backup",
        "LlangonSuite-AgendaWake",
        "LlangonSuiteV2-MonitorScheduler",
    ]
    try:
        script = "; ".join([
            "$names=@(" + ",".join("'" + item + "'" for item in names) + ")",
            "$items=@()",
            "foreach($n in $names){$t=Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue; if($t){$i=Get-ScheduledTaskInfo -TaskName $n; $items += [pscustomobject]@{name=$n;state=$t.State.ToString();enabled=$t.Settings.Enabled;wake_to_run=$t.Settings.WakeToRun;last_run=$i.LastRunTime;next_run=$i.NextRunTime;result=$i.LastTaskResult;action=($t.Actions|%{\"$($_.Execute) $($_.Arguments)\"}) -join ' || '}}}",
            "$items | ConvertTo-Json -Depth 4",
        ])
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
        if completed.returncode != 0:
            return {"items": [], "error": completed.stderr.strip() or completed.stdout.strip()}
        text = completed.stdout.strip()
        items = json.loads(text) if text else []
        if isinstance(items, dict):
            items = [items]
        legacy = [item for item in items if clean_text(item.get("name")) in names[2:]]
        return {"items": items, "legacy_warnings": legacy}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


def automation_diagnostic(*, db_path: str | Path = DEFAULT_DB_PATH) -> str:
    status = automation_status_payload(db_path=db_path)
    runs = automation_runs_payload(db_path=db_path, limit=20)
    windows = windows_tasks_payload()
    lines = [
        "# Diagnóstico automatizaciones Llangon Suite",
        f"Generado: {status['server_time']}",
        "",
        "## Estado general",
        f"- Scheduler en ejecución: {status['scheduler_running']}",
        f"- Locks activos: {len(status['locks'])}",
        f"- Dropbox base: {status.get('dropbox_base') or 'no configurada'}",
        f"- SMTP configurado: {status['smtp']['configured']}",
        f"- Telegram activo: {status['telegram']['enabled']}",
        "",
        "## Automatizaciones",
    ]
    for task in status["tasks"]:
        last = task.get("last_run") or {}
        lines.append(
            f"- {task['name']} ({task['key']}): {task['status']} | {task['schedule_label']} | "
            f"siguiente={task.get('next_run') or '-'} | última={last.get('started_at') or '-'} {last.get('status') or ''}"
        )
    lines.extend(["", "## Tareas Windows"])
    for item in windows.get("items", []):
        lines.append(f"- {item.get('name')}: {item.get('state')} enabled={item.get('enabled')} wake={item.get('wake_to_run')} next={item.get('next_run')}")
    if windows.get("legacy_warnings"):
        lines.append("Advertencia: existen tareas legacy de Llangon que pueden duplicar ejecuciones.")
    lines.extend(["", "## Últimas ejecuciones"])
    for run in runs[:20]:
        lines.append(f"- #{run['id']} {run['task_key']} {run['status']} {run['started_at']} {run.get('summary') or ''} {run.get('error_message') or ''}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Orquestador interno de automatizaciones Llangon Suite.")
    parser.add_argument("--tick", action="store_true", help="Ejecuta un tick del scheduler interno.")
    parser.add_argument("--run", help="Ejecuta una automatización concreta.")
    parser.add_argument("--status", action="store_true", help="Muestra estado JSON.")
    parser.add_argument("--diagnostic", action="store_true", help="Muestra diagnóstico Markdown.")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)
    if args.tick:
        print(json.dumps(scheduler_tick(db_path=args.db_path, source=args.source), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.run:
        print(json.dumps(run_task(args.run, db_path=args.db_path, source=args.source), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.status:
        print(json.dumps(automation_status_payload(db_path=args.db_path), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.diagnostic:
        print(automation_diagnostic(db_path=args.db_path))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
