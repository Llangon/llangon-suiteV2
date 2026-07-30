from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
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
    from .monitor.tender_repository import (
        active_cycle as active_tender_cycle,
        create_cycle as create_tender_cycle,
        recover_orphan_cycles,
    )
    from .monitor.tender_schema import ensure_tender_monitor_schema
    from .monitor.tender_worker_launcher import launch_tender_monitor_worker
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
    from monitor.tender_repository import (
        active_cycle as active_tender_cycle,
        create_cycle as create_tender_cycle,
        recover_orphan_cycles,
    )
    from monitor.tender_schema import ensure_tender_monitor_schema
    from monitor.tender_worker_launcher import launch_tender_monitor_worker
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
STATUS_INTERRUPTED = "interrupted"
AUTOMATION_RUN_SCHEDULE_PREFIX = "automation_run:"
TASK_TYPE_PC_RESTART = "pc_restart"
TASK_TYPE_PC_RESTART_CANCEL = "pc_restart_cancel"
PC_RESTART_DELAY_SECONDS = 60
TASK_INTERVAL_SETTING_KEYS = {
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR: "email_actions_poll_minutes",
    TASK_TYPE_INFONALIA_MAIL_IMPORT: "infonalia_import_poll_minutes",
}
TASK_ENABLED_SETTING_KEYS = {
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR: "email_actions_enabled",
    TASK_TYPE_INFONALIA_MAIL_IMPORT: "infonalia_import_enabled",
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
    daily_times: tuple[str, ...] = ()
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
        name="Reconciliación de rutas Dropbox",
        description="Localiza carpetas por su marcador {id}.llangon y corrige sus rutas.",
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
        key=TASK_TYPE_PC_RESTART,
        name="Reinicio remoto del PC",
        description="Programa un reinicio forzoso de Windows con 60 segundos de margen para cancelarlo.",
        schedule_type="event",
        default_enabled=True,
        manual_allowed=True,
        priority=210,
    ),
    AutomationDefinition(
        key=TASK_TYPE_PC_RESTART_CANCEL,
        name="Cancelar reinicio remoto",
        description="Cancela el reinicio de Windows que esté pendiente de ejecutarse.",
        schedule_type="event",
        default_enabled=True,
        manual_allowed=True,
        priority=211,
    ),
    AutomationDefinition(
        key=TASK_TYPE_MONITOR_LICITACIONES,
        name="Monitor licitaciones",
        description="Revisa las licitaciones seguidas tres veces al día y recupera la última franja al despertar.",
        schedule_type="daily_times",
        default_enabled=False,
        daily_times=("08:00", "13:00", "18:00"),
        manual_allowed=True,
        priority=300,
        env_enabled=None,
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


def parse_daily_times(value: object, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw_values = clean_text(value).replace(";", ",").split(",") if clean_text(value) else list(fallback)
    parsed: set[str] = set()
    for raw in raw_values:
        text = clean_text(raw)
        if not text:
            continue
        normalized = parse_hhmm(text, "")
        if normalized:
            parsed.add(normalized)
    if not parsed:
        parsed = {parse_hhmm(item, "") for item in fallback}
        parsed.discard("")
    return tuple(sorted(parsed))


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
    setting_key = TASK_ENABLED_SETTING_KEYS.get(definition.key)
    if setting_key:
        try:
            setting = conn.execute("SELECT value FROM app_settings WHERE key = ?", (setting_key,)).fetchone()
        except sqlite3.Error:
            setting = None
        if setting and clean_text(setting["value"]) != "":
            return bool_text(setting["value"])
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
    if definition.schedule_type == "daily_times":
        return ",".join(parse_daily_times("", definition.daily_times))
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


def last_completed_for_slot(conn: sqlite3.Connection, key: str, slot: datetime) -> sqlite3.Row | None:
    rows = conn.execute(
        """
        SELECT *
        FROM automation_runs
        WHERE task_key = ?
          AND status = ?
          AND source IN ('automatic', 'keeper_tick', 'wake_tick')
          AND substr(started_at, 1, 10) = ?
        ORDER BY id DESC
        """,
        (key, STATUS_COMPLETED, slot.date().isoformat()),
    ).fetchall()
    for row in rows:
        started = parse_iso(row["started_at"])
        if started and started >= slot:
            return row
    return None


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


def latest_daily_slot(target: datetime, times: tuple[str, ...], *, weekdays_only: bool = False) -> datetime | None:
    if weekdays_only and target.date().weekday() >= 5:
        return None
    candidates = [
        datetime.combine(
            target.date(),
            dt_time(*[int(part) for part in hhmm.split(":", 1)]),
            tzinfo=target.tzinfo,
        )
        for hhmm in times
    ]
    arrived = [candidate for candidate in candidates if candidate <= target]
    return max(arrived) if arrived else None


def next_daily_times(target: datetime, times: tuple[str, ...], *, weekdays_only: bool = False) -> datetime:
    candidates: list[datetime] = []
    for hhmm in times:
        candidates.append(next_daily_time(target, hhmm, weekdays_only=weekdays_only))
    return min(candidates) if candidates else target + timedelta(days=1)


def task_enabled_after_slot(conn: sqlite3.Connection, definition: AutomationDefinition, slot: datetime) -> bool:
    row = task_override(conn, definition.key)
    if not row or row["enabled"] != 1:
        return True
    updated_at = parse_iso(row["updated_at"])
    return not updated_at or updated_at <= slot


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
    if definition.schedule_type == "daily_times":
        times = parse_daily_times(
            task_schedule_value(conn, definition, db_path=db_path),
            definition.daily_times,
        )
        if due_for_tick(conn, definition, current=now, db_path=db_path):
            return now.replace(microsecond=0).isoformat()
        return next_daily_times(now, times, weekdays_only=definition.weekdays_only).replace(microsecond=0).isoformat()
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
    if definition.schedule_type == "daily_times":
        times = parse_daily_times(
            task_schedule_value(conn, definition, db_path=db_path),
            definition.daily_times,
        )
        slot = latest_daily_slot(now, times, weekdays_only=definition.weekdays_only)
        if slot is None or not task_enabled_after_slot(conn, definition, slot):
            return False
        return last_completed_for_slot(conn, definition.key, slot) is None
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


def windows_process_is_alive(pid: int) -> bool | None:
    """Check a Windows PID without sending it a signal or modifying the process."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        open_process.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        get_exit_code.restype = wintypes.BOOL
        handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            try:
                exit_code = wintypes.DWORD()
                if not get_exit_code(handle, ctypes.byref(exit_code)):
                    return None
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                close_handle(handle)
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: the PID does not exist.
            return False
        if error == 5:  # ERROR_ACCESS_DENIED: the process exists but cannot be queried.
            return True
        return None
    except (AttributeError, OSError, ValueError):
        return None


def process_id_is_alive(pid: int, *, platform_name: str | None = None) -> bool | None:
    platform = platform_name or os.name
    if platform == "nt":
        return windows_process_is_alive(pid)
    return None


def lock_owner_process_is_alive(owner: object) -> bool | None:
    """Return False only when a local lock owner can be proven to be dead."""
    parts = clean_text(owner).split(":", 3)
    if len(parts) < 2 or parts[0].casefold() != socket.gethostname().casefold():
        return None
    try:
        pid = int(parts[1])
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    return process_id_is_alive(pid)


def lock_is_live(lock: sqlite3.Row | dict[str, object] | None, *, current: datetime | None = None) -> bool:
    if not lock:
        return False
    expires_at = parse_iso(lock["expires_at"])
    if not expires_at or expires_at <= now_local(current):
        return False
    return lock_owner_process_is_alive(lock["owner"]) is not False


def recover_orphaned_automation_runs(
    conn: sqlite3.Connection,
    *,
    current: datetime | None = None,
) -> list[int]:
    """Close runs left as running after their worker process disappeared."""
    current_dt = now_local(current)
    finished_at = current_dt.replace(microsecond=0).isoformat()
    recovered: list[int] = []
    rows = conn.execute(
        "SELECT * FROM automation_runs WHERE status = ? ORDER BY id ASC",
        (STATUS_RUNNING,),
    ).fetchall()
    for row in rows:
        task_key = clean_text(row["task_key"])
        owner = clean_text(row["lock_owner"])
        lock = conn.execute(
            "SELECT * FROM automation_locks WHERE key = ? AND owner = ?",
            (f"task:{task_key}", owner),
        ).fetchone()
        if lock_is_live(lock, current=current_dt):
            continue

        started_at = parse_iso(row["started_at"])
        duration = max(0.0, (current_dt - started_at).total_seconds()) if started_at else None
        try:
            details = json.loads(clean_text(row["details_json"]) or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            details = {}
        if not isinstance(details, dict):
            details = {}
        details["recovery"] = {
            "reason": "worker_process_not_alive",
            "recovered_at": finished_at,
        }
        message = "Ejecución interrumpida porque el proceso que la inició ya no está activo."
        conn.execute(
            """
            UPDATE automation_runs
            SET status = ?, finished_at = ?, duration_seconds = ?, summary = ?,
                error_message = ?, details_json = ?
            WHERE id = ? AND status = ?
            """,
            (
                STATUS_INTERRUPTED,
                finished_at,
                duration,
                message,
                message,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                row["id"],
                STATUS_RUNNING,
            ),
        )
        conn.execute(
            "DELETE FROM automation_locks WHERE key = ? AND owner = ?",
            (f"task:{task_key}", owner),
        )
        recovered.append(int(row["id"]))
    recovered_monitor_runs = recover_orphaned_inventory_monitor_runs(
        conn,
        current=current_dt,
    )
    if recovered or recovered_monitor_runs:
        conn.commit()
    return recovered


def automation_run_schedule_key(run_id: int) -> str:
    return f"{AUTOMATION_RUN_SCHEDULE_PREFIX}{int(run_id)}"


def recover_orphaned_inventory_monitor_runs(
    conn: sqlite3.Connection,
    *,
    current: datetime | None = None,
) -> list[int]:
    """Close internal inventory rows whose owning automation is already terminal.

    New executions carry an exact automation-run correlation in ``schedule_key``.
    The bounded timestamp fallback exists only for rows created before that
    correlation was introduced.
    """
    try:
        monitor_rows = conn.execute(
            "SELECT * FROM monitor_runs WHERE status = 'running' AND mode = 'inventory' ORDER BY id ASC"
        ).fetchall()
    except sqlite3.Error:
        return []
    if not monitor_rows:
        return []

    automation_rows = conn.execute(
        """
        SELECT *
        FROM automation_runs
        WHERE task_key = ?
        ORDER BY id ASC
        """,
        (TASK_TYPE_FILE_INVENTORY,),
    ).fetchall()
    automation_by_id = {int(row["id"]): row for row in automation_rows}
    legacy_terminal_automation_rows = [
        row
        for row in automation_rows
        if clean_text(row["status"]) in {STATUS_FAILED, STATUS_INTERRUPTED}
    ]
    finished_at = now_iso(current)
    message = "Reconciliación de rutas interrumpida porque su proceso de automatización ya no está activo."
    recovered: list[int] = []

    for monitor_row in monitor_rows:
        row_keys = set(monitor_row.keys()) if hasattr(monitor_row, "keys") else set()
        schedule_key = clean_text(monitor_row["schedule_key"]) if "schedule_key" in row_keys else ""
        owner_run = None
        if schedule_key.startswith(AUTOMATION_RUN_SCHEDULE_PREFIX):
            try:
                owner_run = automation_by_id.get(int(schedule_key.removeprefix(AUTOMATION_RUN_SCHEDULE_PREFIX)))
            except ValueError:
                owner_run = None
            if owner_run is None or clean_text(owner_run["status"]) == STATUS_RUNNING:
                continue
        elif schedule_key:
            continue
        else:
            monitor_started = parse_iso(monitor_row["started_at"])
            if not monitor_started:
                continue
            for candidate in legacy_terminal_automation_rows:
                candidate_started = parse_iso(candidate["started_at"])
                if not candidate_started:
                    continue
                delta = monitor_started - candidate_started
                if -timedelta(seconds=30) <= delta <= timedelta(minutes=5):
                    owner_run = candidate
                    break
            if owner_run is None:
                continue

        cursor = conn.execute(
            """
            UPDATE monitor_runs
            SET status = ?, finished_at = ?, error_message = ?,
                warnings_count = CASE WHEN warnings_count < 1 THEN 1 ELSE warnings_count END
            WHERE id = ? AND status = 'running'
            """,
            (STATUS_INTERRUPTED, finished_at, message, monitor_row["id"]),
        )
        if cursor.rowcount:
            recovered.append(int(monitor_row["id"]))
    return recovered


def launch_automation_task_worker(
    key: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "manual_worker",
    triggered_by: str = "",
) -> dict[str, object]:
    definition = automation_by_key(key)
    if not definition:
        return {"ok": False, "error": f"Automatización no reconocida: {key}"}
    command = [
        sys.executable,
        "-m",
        "webapp.infonalia_webapp.automation_worker",
        "--task-key",
        definition.key,
        "--db",
        str(db_path),
        "--source",
        clean_text(source) or "manual_worker",
    ]
    if clean_text(triggered_by):
        command.extend(["--triggered-by", clean_text(triggered_by)])
    kwargs: dict[str, object] = {
        "cwd": str(PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": False,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(command, **kwargs)
    except Exception as exc:
        message = f"No se pudo iniciar el worker de automatización: {exc}"
        record_automation_start_failure(
            definition.key,
            db_path=db_path,
            source=source,
            triggered_by=triggered_by,
            error_message=message,
        )
        return {"ok": False, "error": message}
    return {"ok": True, "pid": process.pid, "task_key": definition.key}


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


def record_automation_start_failure(
    key: str,
    *,
    db_path: str | Path,
    source: str,
    triggered_by: str = "",
    error_message: str,
) -> int | None:
    """Persist a launcher/supervisor failure when no task process could start."""
    definition = automation_by_key(key)
    if not definition:
        return None
    conn = None
    try:
        conn = connect_db(db_path)
        conn.row_factory = sqlite3.Row
        ensure_monitor_schema(conn)
        ensure_automation_schema(conn)
        run_id = create_run(
            conn,
            definition,
            source=clean_text(source) or "worker_supervisor",
            triggered_by=clean_text(triggered_by),
            lock_owner_value="",
        )
        finish_run(
            conn,
            run_id,
            status=STATUS_FAILED,
            summary="No se pudo iniciar el proceso aislado.",
            error_message=clean_text(error_message),
            details={"phase": "worker_start"},
        )
        return run_id
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()


def summarize_result(result: dict[str, object]) -> str:
    if clean_text(result.get("summary")):
        return clean_text(result.get("summary"))
    pieces = []
    for label, key in (
        ("procesados", "processed_items_count"),
        ("importados", "imported"),
        ("acciones", "processed"),
        ("emails", "emails_sent_count"),
        ("marcadores", "processed_items_count"),
        ("corregidas", "route_updates_count"),
    ):
        value = result.get(key)
        if value not in (None, "", 0):
            pieces.append(f"{label}: {value}")
    return "; ".join(pieces) or clean_text(result.get("message")) or "Ejecución finalizada."


def run_mail_interval_task(
    definition: AutomationDefinition,
    db_path: str | Path,
    current: datetime,
    *,
    automation_run_id: int | None = None,
) -> dict[str, object]:
    reports = _run_mail_interval_jobs(
        db_path=db_path,
        current=current,
        dry_run=False,
        task_types={definition.key},
        force_selected=True,
        automation_run_id=automation_run_id,
    )
    return reports[0] if reports else {
        "task_type": definition.key,
        "status": STATUS_SKIPPED,
        "message": "No se pudo ejecutar la tarea solicitada.",
    }


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


def run_pc_restart(*, source: str) -> dict[str, object]:
    """Schedule a forced local Windows restart only after a manual API action."""
    if source != "manual":
        return {
            "status": STATUS_SKIPPED,
            "summary": "El reinicio remoto solo puede solicitarse manualmente desde la Suite.",
        }
    if os.name != "nt":
        return {"status": STATUS_SKIPPED, "summary": "El reinicio remoto solo está disponible en Windows."}
    command = [
        "shutdown.exe",
        "/r",
        "/f",
        "/t",
        str(PC_RESTART_DELAY_SECONDS),
        "/d",
        "p:4:1",
        "/c",
        "Reinicio remoto solicitado desde Llangon Suite.",
    ]
    try:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)
    except OSError as exc:
        return {"status": STATUS_FAILED, "summary": "No se pudo programar el reinicio remoto.", "error": str(exc)}
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode == 0:
        return {
            "status": STATUS_COMPLETED,
            "summary": f"Reinicio forzoso programado para dentro de {PC_RESTART_DELAY_SECONDS} segundos.",
            "restart_delay_seconds": PC_RESTART_DELAY_SECONDS,
            "output": output[-2000:],
        }
    return {
        "status": STATUS_FAILED,
        "summary": "Windows rechazó la solicitud de reinicio remoto.",
        "returncode": completed.returncode,
        "output": output[-2000:],
    }


def cancel_pc_restart(*, source: str) -> dict[str, object]:
    if source != "manual":
        return {
            "status": STATUS_SKIPPED,
            "summary": "La cancelación del reinicio remoto solo puede solicitarse manualmente desde la Suite.",
        }
    if os.name != "nt":
        return {"status": STATUS_SKIPPED, "summary": "La cancelación del reinicio remoto solo está disponible en Windows."}
    try:
        completed = subprocess.run(
            ["shutdown.exe", "/a"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return {"status": STATUS_FAILED, "summary": "No se pudo cancelar el reinicio remoto.", "error": str(exc)}
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode == 0:
        return {"status": STATUS_COMPLETED, "summary": "Reinicio remoto cancelado.", "output": output[-2000:]}
    return {
        "status": STATUS_SKIPPED,
        "summary": "No había un reinicio remoto pendiente que cancelar.",
        "returncode": completed.returncode,
        "output": output[-2000:],
    }


def execute_task(
    conn: sqlite3.Connection,
    definition: AutomationDefinition,
    *,
    db_path: str | Path,
    source: str,
    triggered_by: str = "",
    current: datetime | None = None,
    automation_run_id: int | None = None,
) -> dict[str, object]:
    current_dt = now_local(current)
    if definition.key == TASK_TYPE_FILE_INVENTORY:
        ensure_tender_monitor_schema(conn)
        # The reconciliation executor opens its own SQLite connections. Release
        # schema/default-setting writes first or the child connection can fail
        # immediately with ``database is locked``.
        conn.commit()
        active = active_tender_cycle(conn)
        # ``active_tender_cycle`` defensively ensures the schema again and can
        # therefore open a fresh write transaction of its own.
        conn.commit()
        if active:
            return {
                "status": STATUS_SKIPPED,
                "summary": "Reconciliación de rutas aplazada mientras el monitor de licitaciones está activo.",
                "cycle_id": active["id"],
            }
        return run_mail_interval_task(
            definition,
            db_path,
            current_dt,
            automation_run_id=automation_run_id,
        )
    if definition.key in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR}:
        return run_mail_interval_task(
            definition,
            db_path,
            current_dt,
            automation_run_id=automation_run_id,
        )
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
    if definition.key == TASK_TYPE_PC_RESTART:
        return run_pc_restart(source=source)
    if definition.key == TASK_TYPE_PC_RESTART_CANCEL:
        return cancel_pc_restart(source=source)
    if definition.key == TASK_TYPE_MONITOR_LICITACIONES:
        ensure_tender_monitor_schema(conn)
        inventory_run = conn.execute(
            """
            SELECT id FROM automation_runs
            WHERE task_key = ? AND status = ?
            ORDER BY id DESC LIMIT 1
            """,
            (TASK_TYPE_FILE_INVENTORY, STATUS_RUNNING),
        ).fetchone()
        if inventory_run:
            return {
                "status": STATUS_SKIPPED,
                "summary": "Monitor aplazado mientras la reconciliación de rutas está activa.",
                "inventory_run_id": inventory_run["id"],
            }
        active = active_tender_cycle(conn)
        if active:
            return {
                "status": STATUS_SKIPPED,
                "summary": "El monitor ya tiene un ciclo activo.",
                "cycle_id": active["id"],
            }
        cycle_id = create_tender_cycle(
            conn,
            origin="manual_automation_console" if source == "manual" else "automatic_scheduler",
            requested_by=clean_text(triggered_by) or ("admin" if source == "manual" else source),
            metadata={"automation_source": source},
        )
        conn.commit()
        root = clean_text(os.environ.get("INFONALIA_MONITOR_ROOT")) or None
        worker = launch_tender_monitor_worker(cycle_id, db_path=db_path, root=root)
        if worker.get("ok") is False:
            conn.execute(
                "UPDATE tender_monitor_cycles SET status = 'failed', finished_at = ? WHERE id = ?",
                (now_iso(current_dt), cycle_id),
            )
            conn.commit()
            return {
                "status": STATUS_FAILED,
                "summary": "No se pudo iniciar el worker del monitor.",
                "cycle_id": cycle_id,
                "error": clean_text(worker.get("error")),
            }
        return {
            "status": STATUS_COMPLETED,
            "summary": f"Ciclo {'manual' if source == 'manual' else 'automático'} del monitor encolado.",
            "cycle_id": cycle_id,
            "worker": worker,
        }
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
    recover_orphaned_automation_runs(conn, current=current)
    ensure_tender_monitor_schema(conn)
    lease_row = conn.execute(
        "SELECT value FROM tender_monitor_settings WHERE key = 'lease_minutes'"
    ).fetchone()
    try:
        tender_lease_minutes = int(lease_row["value"] if lease_row else 60)
    except (TypeError, ValueError):
        tender_lease_minutes = 60
    recover_orphan_cycles(conn, timestamp=now_local(current), minutes=tender_lease_minutes)
    conn.commit()
    owner = lock_owner(source)
    task_lock = f"task:{definition.key}"
    ttl = CRITICAL_TASK_LOCK_TTL_MINUTES if definition.prevents_suspend else DEFAULT_TASK_LOCK_TTL_MINUTES
    acquired, existing = acquire_lock(conn, task_lock, owner, ttl_minutes=ttl, metadata={"task": definition.key, "source": source}, current=current)
    if not acquired:
        return {"task_key": definition.key, "status": STATUS_SKIPPED, "summary": "Omitida: ya está en ejecución.", "lock": existing}
    run_id = create_run(conn, definition, source=source, triggered_by=triggered_by, lock_owner_value=owner, current=current)
    try:
        result = execute_task(
            conn,
            definition,
            db_path=db_path,
            source=source,
            triggered_by=triggered_by,
            current=current,
            automation_run_id=run_id,
        )
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
    recover_orphaned_automation_runs(conn, current=current)
    ensure_tender_monitor_schema(conn)
    lease_row = conn.execute(
        "SELECT value FROM tender_monitor_settings WHERE key = 'lease_minutes'"
    ).fetchone()
    try:
        tender_lease_minutes = int(lease_row["value"] if lease_row else 60)
    except (TypeError, ValueError):
        tender_lease_minutes = 60
    recovered_tender_cycles = recover_orphan_cycles(
        conn,
        timestamp=now_local(current),
        minutes=tender_lease_minutes,
    )
    conn.commit()
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
        return {
            "ok": True,
            "status": STATUS_COMPLETED,
            "source": source,
            "due_count": len(due),
            "recovered_tender_cycles": recovered_tender_cycles,
            "results": results,
        }
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


def set_task_schedule(
    key: str,
    schedule_value: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    updated_by: str = "",
) -> dict[str, object]:
    definition = automation_by_key(key)
    if not definition:
        raise ValueError(f"Automatización no reconocida: {key}")
    if definition.schedule_type == "daily_times":
        parsed = parse_daily_times(schedule_value, ())
        if not parsed:
            raise ValueError("La programación debe incluir al menos una hora válida HH:MM.")
        normalized = ",".join(parsed)
    elif definition.schedule_type == "daily_time":
        normalized = parse_hhmm(schedule_value, "")
        if not normalized:
            raise ValueError("La programación debe ser una hora válida HH:MM.")
    elif definition.schedule_type == "interval":
        try:
            normalized = str(max(1, int(schedule_value)))
        except (TypeError, ValueError) as exc:
            raise ValueError("El intervalo debe ser un número de minutos válido.") from exc
    else:
        raise ValueError("Esta automatización no admite una programación editable.")
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    conn.execute(
        """
        INSERT INTO automation_tasks (key, enabled, schedule_value, updated_at, updated_by)
        VALUES (?, NULL, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET schedule_value = excluded.schedule_value,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (key, normalized, now_iso(), clean_text(updated_by)),
    )
    conn.commit()
    payload = task_payload(conn, definition, db_path=db_path)
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
    running = None
    if row and clean_text(row["status"]) == STATUS_RUNNING:
        lock = conn.execute(
            "SELECT * FROM automation_locks WHERE key = ? AND owner = ?",
            (f"task:{definition.key}", clean_text(row["lock_owner"])),
        ).fetchone()
        if lock_is_live(lock):
            running = row
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
    if definition.schedule_type == "daily_times":
        values = [item for item in value.split(",") if item]
        return f"Diario a las {', '.join(values)}"
    if definition.schedule_type == "manual":
        return "Manual"
    return "Por evento"


def automation_tasks_payload(*, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    ensure_automation_schema(conn)
    recover_orphaned_automation_runs(conn)
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
    recover_orphaned_automation_runs(conn)
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
    recover_orphaned_automation_runs(conn)
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
