from __future__ import annotations

import os
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from .config import MonitorConfigError, load_monitor_config
from .email import prepare_monitor_emails
from .platforms import check_followed_platforms
from .repository import (
    TASK_TYPE_AGENDA_DIARIA,
    TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
    TASK_TYPE_AGENDA_SEMANAL,
    TASK_TYPE_AVISO_VENCIMIENTO_1D,
    TASK_TYPE_AVISO_VENCIMIENTO_3D,
    TASK_TYPE_AVISO_VENCIMIENTO_7D,
    TASK_TYPE_AVISO_VENCIMIENTO_HOY,
    TASK_TYPE_FILE_INVENTORY,
    TASK_TYPE_LICITACIONES,
    TASK_TYPE_MONITOR_LICITACIONES,
    TASK_TYPE_RESUMEN_AGENDA,
    TASK_TYPES,
    connect_db,
    ensure_monitor_schema,
    fetch_licitaciones,
    normalize_task_type,
    row_value,
)
from .routes import FolderNormalizer, repair_routes
from .scanner import MarkerRecord, MonitorIssue, ScanResult, scan_marker_tree

try:
    from ..agenda.email_summary import (
        build_pending_tasks_email_payload,
        build_operational_email_html,
        build_operational_email_payload,
        build_operational_email_text,
        email_day_section_title,
    )
    from ..agenda.pending_tasks import build_pending_tasks_response
    from ..agenda.service import active_date_label, agenda_week_bounds, build_agenda_events, build_agenda_response
    from ..environment import load_env_file
    from ..normalization import clean_text
    from ..storage_paths import folder_path_for_storage
except ImportError:
    from agenda.email_summary import (
        build_pending_tasks_email_payload,
        build_operational_email_html,
        build_operational_email_payload,
        build_operational_email_text,
        email_day_section_title,
    )
    from agenda.pending_tasks import build_pending_tasks_response
    from agenda.service import active_date_label, agenda_week_bounds, build_agenda_events, build_agenda_response
    from environment import load_env_file
    from normalization import clean_text
    from storage_paths import folder_path_for_storage


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = APP_ROOT / "data" / "infonalia.db"
load_env_file(APP_ROOT / ".env")
ALL_MODES = {"dry-run", "repair-routes", "inventory", "sync", "monitor"}
EmailSender = Callable[[str, str, str, str], tuple[str | None, str | None]]
AUTOMATION_MODE_MANUAL = "manual"
AUTOMATION_MODE_AUTOMATIC = "automatic"
DEFAULT_SCHEDULER_TIMEZONE = "Europe/Madrid"
SPANISH_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
LEGACY_AUTOMATION_TASKS = {
    TASK_TYPE_AGENDA_DIARIA,
    TASK_TYPE_AGENDA_SEMANAL,
    TASK_TYPE_AVISO_VENCIMIENTO_7D,
    TASK_TYPE_AVISO_VENCIMIENTO_3D,
    TASK_TYPE_AVISO_VENCIMIENTO_1D,
    TASK_TYPE_AVISO_VENCIMIENTO_HOY,
}
DEFAULT_MONITOR_AUTOMATION_SCHEDULES = {
    TASK_TYPE_AGENDA_PENDIENTES_DIARIA: {
        "frequency": "daily",
        "time": "06:00",
        "send_policy": "only_if_pending_tasks",
    },
    TASK_TYPE_MONITOR_LICITACIONES: {
        "frequency": "weekdays",
        "times": ["07:00", "12:30", "17:30"],
        "send_policy": "only_with_changes",
    },
}
LEGACY_AUTOMATION_SCHEDULES = {
    TASK_TYPE_AGENDA_DIARIA: {
        "frequency": "daily",
        "time": "06:00",
        "send_policy": "legacy_manual_alias",
        "active": False,
    },
    TASK_TYPE_AGENDA_SEMANAL: {
        "frequency": "weekly",
        "weekday": "monday",
        "time": "05:30",
        "send_policy": "legacy_manual_only",
        "active": False,
    },
    TASK_TYPE_AVISO_VENCIMIENTO_7D: {
        "frequency": "daily",
        "time": "06:15",
        "notice_days": 7,
        "notice_level": "7d",
        "send_policy": "legacy_manual_only",
        "active": False,
    },
    TASK_TYPE_AVISO_VENCIMIENTO_3D: {
        "frequency": "daily",
        "time": "06:20",
        "notice_days": 3,
        "notice_level": "3d",
        "send_policy": "legacy_manual_only",
        "active": False,
    },
    TASK_TYPE_AVISO_VENCIMIENTO_1D: {
        "frequency": "daily",
        "time": "06:25",
        "notice_days": 1,
        "notice_level": "1d",
        "send_policy": "legacy_manual_only",
        "active": False,
    },
    TASK_TYPE_AVISO_VENCIMIENTO_HOY: {
        "frequency": "daily",
        "time": "06:30",
        "notice_days": 0,
        "notice_level": "hoy",
        "send_policy": "legacy_manual_only",
        "active": False,
    },
}
NOTICE_TASK_TYPES = {
    TASK_TYPE_AVISO_VENCIMIENTO_7D,
    TASK_TYPE_AVISO_VENCIMIENTO_3D,
    TASK_TYPE_AVISO_VENCIMIENTO_1D,
    TASK_TYPE_AVISO_VENCIMIENTO_HOY,
}


class MonitorError(RuntimeError):
    """Monitor V0 failed before producing a usable report."""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def scheduler_timezone() -> ZoneInfo:
    name = clean_text(os.environ.get("MONITOR_SCHEDULER_TIMEZONE")) or DEFAULT_SCHEDULER_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_SCHEDULER_TIMEZONE)


def localize_scheduler_datetime(value: datetime | None = None) -> datetime:
    tz = scheduler_timezone()
    current = value or datetime.now(tz)
    if current.tzinfo is None:
        return current.replace(tzinfo=tz)
    return current.astimezone(tz)


def scheduler_now_iso(value: datetime | None = None) -> str:
    return localize_scheduler_datetime(value).replace(microsecond=0).isoformat()


def scheduler_naive_datetime(value: datetime) -> datetime:
    return localize_scheduler_datetime(value).replace(tzinfo=None)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return clean_text(raw).lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default)) or default))
    except (TypeError, ValueError):
        return default


def active_monitor_automation_schedules() -> dict[str, dict[str, object]]:
    schedules: dict[str, dict[str, object]] = {}
    if env_bool("MONITOR_AGENDA_PENDING_DAILY_ENABLED", True):
        schedules[TASK_TYPE_AGENDA_PENDIENTES_DIARIA] = {
            **DEFAULT_MONITOR_AUTOMATION_SCHEDULES[TASK_TYPE_AGENDA_PENDIENTES_DIARIA],
            "time": os.environ.get("MONITOR_AGENDA_PENDING_DAILY_TIME", "06:00"),
            "weekdays_only": env_bool("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", True),
        }
    # La futura programación reutilizará el mismo orquestador real, pero en esta
    # fase no existe ninguna ruta (ni siquiera por variable de entorno) que la active.
    return schedules


def normalize_mode(mode: str) -> str:
    clean = (mode or "dry-run").strip().lower()
    if clean not in ALL_MODES:
        raise MonitorError(f"Modo de monitor no valido: {mode}")
    return clean


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    )


def mode_steps(mode: str) -> set[str]:
    # ``inventory`` is kept as a compatibility alias for existing jobs and
    # clients. The file census is retired; both modes now only reconcile paths.
    if mode in {"repair-routes", "inventory"}:
        return {"repair"}
    return {"repair", "follow", "platforms", "email"}


def dedupe_issues(issues: Iterable[MonitorIssue]) -> list[MonitorIssue]:
    seen: set[tuple[object, ...]] = set()
    result: list[MonitorIssue] = []
    for issue in issues:
        key = (issue.code, issue.message, issue.path, issue.licitacion_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def existing_markers(
    conn: sqlite3.Connection,
    scan_result: ScanResult,
    warnings: list[MonitorIssue],
) -> tuple[list[MarkerRecord], dict[int, sqlite3.Row]]:
    rows = fetch_licitaciones(conn, sorted({marker.licitacion_id for marker in scan_result.markers}))
    markers: list[MarkerRecord] = []
    for marker in scan_result.markers:
        if marker.licitacion_id not in rows:
            warnings.append(
                MonitorIssue(
                    code="licitacion_missing",
                    message="Hay marcador .llangon pero la licitacion no existe en SQLite.",
                    path=str(marker.marker_path),
                    licitacion_id=marker.licitacion_id,
                )
            )
            continue
        markers.append(marker)
    return markers, rows


def sync_follow_status(
    conn: sqlite3.Connection,
    scan_result: ScanResult,
    dry_run: bool,
    timestamp: str,
    warnings: list[MonitorIssue],
) -> list[dict[str, object]]:
    markers, rows = existing_markers(conn, scan_result, warnings)
    updates: list[dict[str, object]] = []
    for marker in markers:
        row = rows[marker.licitacion_id]
        active = 1 if marker.is_followed else 0
        marker_path = str(marker.follow_marker_path or "")
        changed = (
            int(row_value(row, "seguimiento_activo", 0) or 0) != active
            or str(row_value(row, "seguimiento_marker_path", "") or "") != marker_path
        )
        if changed:
            updates.append(
                {
                    "licitacion_id": marker.licitacion_id,
                    "seguimiento_activo": bool(active),
                    "marker_path": marker_path,
                    "dry_run": dry_run,
                }
            )
        if not dry_run:
            conn.execute(
                """
                UPDATE licitaciones
                SET seguimiento_activo = ?,
                    seguimiento_ultimo_check = ?,
                    seguimiento_ultima_sync = ?,
                    seguimiento_marker_path = ?,
                    seguimiento_marker_warning = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (active, timestamp, timestamp, marker_path, timestamp, marker.licitacion_id),
            )
    return updates


def create_monitor_run(
    conn: sqlite3.Connection,
    *,
    task_type: str = TASK_TYPE_LICITACIONES,
    mode: str,
    root_path: Path | str,
    started_at: str,
    dry_run: bool,
    schedule_key: str = "",
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO monitor_runs (
            task_type,
            mode,
            root_path,
            started_at,
            status,
            dry_run,
            schedule_key
        )
        VALUES (?, ?, ?, ?, 'running', ?, ?)
        """,
        (normalize_task_type(task_type), mode, str(root_path), started_at, 1 if dry_run else 0, schedule_key),
    )
    return int(cursor.lastrowid)


def finish_monitor_run(
    conn: sqlite3.Connection,
    run_id: int,
    report: dict[str, object],
    error_message: str = "",
) -> None:
    details = {
        "task_details": report.get("task_details", {}),
        "route_updates": report.get("route_updates", [])[:50],
        "follow_updates": report.get("follow_updates", [])[:50],
        "platform_changes": report.get("platform_changes", [])[:50],
        "email_drafts": report.get("email_drafts", [])[:20],
        "conflicts": report.get("conflicts", [])[:50],
        "warnings": report.get("warnings", [])[:50],
    }
    conn.execute(
        """
        UPDATE monitor_runs
        SET finished_at = ?,
            status = ?,
            found_markers_count = ?,
            route_updates_count = ?,
            followed_count = ?,
            folders_checked_count = ?,
            folders_repaired_count = ?,
            folders_broken_count = ?,
            platforms_checked_count = ?,
            changes_detected_count = ?,
            emails_prepared_count = ?,
            emails_sent_count = ?,
            inventory_files_count = ?,
            conflicts_count = ?,
            warnings_count = ?,
            processed_items_count = ?,
            error_message = ?,
            details_json = ?
        WHERE id = ?
        """,
        (
            report.get("finished_at"),
            report.get("status"),
            report.get("found_markers_count", 0),
            report.get("route_updates_count", 0),
            report.get("followed_count", 0),
            report.get("folders_checked_count", 0),
            report.get("folders_repaired_count", report.get("route_updates_count", 0)),
            report.get("folders_broken_count", 0),
            report.get("platforms_checked_count", 0),
            report.get("changes_detected_count", 0),
            report.get("emails_prepared_count", 0),
            report.get("emails_sent_count", 0),
            report.get("inventory_files_count", 0),
            len(report.get("conflicts", [])),
            len(report.get("warnings", [])),
            report.get("processed_items_count", 0),
            error_message,
            json.dumps(details, ensure_ascii=False),
            run_id,
        ),
    )


def run_monitor(
    mode: str = "dry-run",
    *,
    dry_run: bool | None = None,
    db_path: str | Path | None = None,
    root: str | Path | None = None,
    normalize_folder_path: FolderNormalizer | None = None,
    schedule_key: str = "",
) -> dict[str, object]:
    clean_mode = normalize_mode(mode)
    effective_dry_run = True if clean_mode == "dry-run" else bool(dry_run)
    started_at = now_iso()
    run_id: int | None = None
    conn: sqlite3.Connection | None = None

    try:
        config = load_monitor_config(root)
        effective_folder_normalizer = normalize_folder_path or (
            lambda path: folder_path_for_storage(path, config.root_path)
        )
        db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        conn = connect_db(db_file, read_only=False)
        ensure_monitor_schema(conn)
        run_id = create_monitor_run(
            conn,
            task_type=TASK_TYPE_LICITACIONES,
            mode=clean_mode,
            root_path=config.root_path,
            started_at=started_at,
            dry_run=effective_dry_run,
            schedule_key=clean_text(schedule_key),
        )
        conn.commit()

        scan_result = scan_marker_tree(config.root_path, config.year_min, config.year_max)
        timestamp = now_iso()
        warnings = list(scan_result.warnings)

        report: dict[str, object] = {
            "mode": clean_mode,
            "task_type": TASK_TYPE_LICITACIONES,
            "dry_run": effective_dry_run,
            "root_path": str(config.root_path),
            "year_min": config.year_min,
            "year_max": config.year_max,
            "started_at": started_at,
            "finished_at": "",
            "status": "running",
            "monitor_run_id": run_id,
            "year_roots": [str(path) for path in scan_result.year_roots],
            "markers": [marker.to_dict() for marker in scan_result.markers],
            "found_markers_count": scan_result.raw_id_marker_count,
            "route_updates": [],
            "route_updates_count": 0,
            "follow_updates": [],
            "follow_updates_count": 0,
            "followed_count": scan_result.followed_count,
            "processed_items_count": len(scan_result.markers),
            "folders_checked_count": len(scan_result.markers),
            "folders_repaired_count": 0,
            "folders_broken_count": len(scan_result.conflicts),
            "platforms_checked_count": 0,
            "changes_detected_count": 0,
            "emails_prepared_count": 0,
            "emails_sent_count": 0,
            "platform_changes": [],
            "email_drafts": [],
            "inventory_files_count": 0,
            "conflicts": [issue.to_dict() for issue in scan_result.conflicts],
            "warnings": [],
            "task_details": {"operation": "marker_route_reconciliation"},
        }

        steps = mode_steps(clean_mode)
        if "repair" in steps:
            route_updates = repair_routes(
                conn,
                scan_result,
                effective_dry_run,
                timestamp,
                warnings,
                normalize_folder_path=effective_folder_normalizer,
            )
            report["route_updates"] = route_updates
            report["route_updates_count"] = len(route_updates)
            report["folders_repaired_count"] = len(route_updates)
        if "follow" in steps:
            follow_updates = sync_follow_status(conn, scan_result, effective_dry_run, timestamp, warnings)
            report["follow_updates"] = follow_updates
            report["follow_updates_count"] = len(follow_updates)
            report["followed_count"] = scan_result.followed_count
        if "platforms" in steps:
            platform_result = check_followed_platforms(scan_result.markers, dry_run=effective_dry_run)
            changes = list(platform_result.get("changes", []))
            report["platforms_checked_count"] = platform_result.get("platforms_checked_count", 0)
            report["platform_changes"] = changes[:50]
            report["changes_detected_count"] = len(changes)
        if "email" in steps:
            email_result = prepare_monitor_emails(
                list(report.get("platform_changes", [])),
                dry_run=effective_dry_run,
            )
            report["emails_prepared_count"] = email_result.get("emails_prepared_count", 0)
            report["emails_sent_count"] = email_result.get("emails_sent_count", 0)
            report["email_drafts"] = email_result.get("drafts", [])[:20]
        report["warnings"] = [issue.to_dict() for issue in dedupe_issues(warnings)]
        report["folders_broken_count"] = len(report["conflicts"])
        report["finished_at"] = now_iso()
        report["status"] = "completed_with_errors" if report["folders_broken_count"] else "completed"
        finish_monitor_run(conn, run_id, report)
        conn.commit()
        return report
    except (MonitorConfigError, FileNotFoundError, NotADirectoryError, sqlite3.Error, OSError) as exc:
        if conn is not None and run_id is not None:
            error_report = {
                "finished_at": now_iso(),
                "status": "failed",
                "found_markers_count": 0,
                "route_updates_count": 0,
                "followed_count": 0,
                "processed_items_count": 0,
                "folders_checked_count": 0,
                "folders_repaired_count": 0,
                "folders_broken_count": 1,
                "platforms_checked_count": 0,
                "changes_detected_count": 0,
                "emails_prepared_count": 0,
                "emails_sent_count": 0,
                "inventory_files_count": 0,
                "conflicts": [],
                "warnings": [{"code": "monitor_error", "message": str(exc)}],
            }
            finish_monitor_run(conn, run_id, error_report, str(exc))
            conn.commit()
        raise MonitorError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def monitor_automation_schedules() -> dict[str, dict[str, object]]:
    return {key: dict(value) for key, value in active_monitor_automation_schedules().items()}


def automation_schedule_for_task(task_type: str) -> dict[str, object]:
    return dict(
        active_monitor_automation_schedules().get(task_type)
        or DEFAULT_MONITOR_AUTOMATION_SCHEDULES.get(task_type)
        or LEGACY_AUTOMATION_SCHEDULES.get(task_type)
        or {}
    )


def schedule_time_has_arrived(current: datetime, time_text: object) -> bool:
    parts = clean_text(time_text).split(":")
    if len(parts) != 2:
        return False
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return False
    return (current.hour * 60 + current.minute) >= (hour * 60 + minute)


def schedule_runs_on_date(config: dict[str, object], day: date) -> bool:
    if config.get("frequency") == "weekdays" or bool(config.get("weekdays_only")):
        return day.weekday() < 5
    return True


def schedule_time_minutes(time_text: object) -> int | None:
    parts = clean_text(time_text).split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def latest_arrived_schedule_time(current: datetime, times: Iterable[object]) -> str:
    current_minutes = current.hour * 60 + current.minute
    arrived: list[tuple[int, str]] = []
    for time_text in times:
        minutes = schedule_time_minutes(time_text)
        if minutes is None or minutes > current_minutes:
            continue
        arrived.append((minutes, clean_text(time_text)))
    if not arrived:
        return ""
    return max(arrived, key=lambda item: item[0])[1]


def due_automation_task_types(current: datetime | None = None) -> list[str]:
    target = localize_scheduler_datetime(current)
    due: list[str] = []
    schedules = active_monitor_automation_schedules()
    daily_schedule = schedules.get(TASK_TYPE_AGENDA_PENDIENTES_DIARIA)
    if (
        daily_schedule
        and schedule_runs_on_date(daily_schedule, target.date())
        and schedule_time_has_arrived(target, daily_schedule.get("time"))
    ):
        due.append(TASK_TYPE_AGENDA_PENDIENTES_DIARIA)
    monitor_schedule = schedules.get(TASK_TYPE_MONITOR_LICITACIONES)
    if (
        monitor_schedule
        and schedule_runs_on_date(monitor_schedule, target.date())
        and latest_arrived_schedule_time(target, monitor_schedule.get("times") or [])
    ):
        due.append(TASK_TYPE_MONITOR_LICITACIONES)
    return due


def run_due_automation_tasks(
    *,
    dry_run: bool = False,
    db_path: str | Path | None = None,
    recipient: str = "",
    email_sender: EmailSender | None = None,
    current: datetime | None = None,
) -> list[dict[str, object]]:
    target = localize_scheduler_datetime(current)
    due_task_types = due_automation_task_types(target)
    if not due_task_types:
        return []
    db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    conn = connect_db(db_file, read_only=False)
    try:
        ensure_monitor_schema(conn)
        record_scheduler_heartbeat(
            conn,
            checked_at=scheduler_now_iso(target),
            status="checked",
            next_task="",
            next_run_at="",
            timezone=DEFAULT_SCHEDULER_TIMEZONE,
        )
        conn.commit()
    finally:
        conn.close()
    return [
        run_automation_task(
            task_type,
            dry_run=dry_run,
            db_path=db_path,
            recipient=recipient,
            email_sender=email_sender,
            current=target,
            trigger_mode=AUTOMATION_MODE_AUTOMATIC,
        )
        for task_type in due_task_types
    ]


def schedule_key_for_task(task_type: str, current: datetime) -> str:
    target = localize_scheduler_datetime(current)
    if task_type in {TASK_TYPE_AGENDA_PENDIENTES_DIARIA, TASK_TYPE_AGENDA_DIARIA} or task_type in NOTICE_TASK_TYPES:
        canonical = TASK_TYPE_AGENDA_PENDIENTES_DIARIA if task_type == TASK_TYPE_AGENDA_DIARIA else task_type
        return f"{canonical}:{target.date().isoformat()}"
    if task_type == TASK_TYPE_AGENDA_SEMANAL:
        calendar = target.date().isocalendar()
        return f"{task_type}:{calendar.year}-W{calendar.week:02d}"
    if task_type == TASK_TYPE_MONITOR_LICITACIONES:
        schedule = automation_schedule_for_task(TASK_TYPE_MONITOR_LICITACIONES)
        slot = latest_arrived_schedule_time(target, schedule.get("times") or [])
        slot_key = slot.replace(":", "")
        return f"{task_type}:{target.date().isoformat()}:{slot_key}" if slot else f"{task_type}:{target.date().isoformat()}"
    return ""


def reset_scheduler_test_state(
    conn: sqlite3.Connection,
    *,
    task_type: str = TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
    schedule_keys: Iterable[str] | None = None,
    reset_heartbeat: bool = True,
) -> dict[str, object]:
    keys = [clean_text(key) for key in (schedule_keys or []) if clean_text(key)]
    deleted_claims = 0
    cleared_run_keys = 0
    if keys:
        placeholders = ",".join("?" for _ in keys)
        deleted_claims = conn.execute(
            f"""
            DELETE FROM monitor_automation_claims
            WHERE task_type = ?
              AND schedule_key IN ({placeholders})
            """,
            (task_type, *keys),
        ).rowcount
        cleared_run_keys = conn.execute(
            f"""
            UPDATE monitor_runs
            SET schedule_key = NULL
            WHERE task_type = ?
              AND mode = ?
              AND schedule_key IN ({placeholders})
            """,
            (task_type, AUTOMATION_MODE_AUTOMATIC, *keys),
        ).rowcount
    else:
        deleted_claims = conn.execute(
            """
            DELETE FROM monitor_automation_claims
            WHERE task_type = ?
              AND status IN ('running', 'failed', 'smtp_uncertain')
            """,
            (task_type,),
        ).rowcount
    deleted_heartbeat = 0
    if reset_heartbeat:
        deleted_heartbeat = conn.execute("DELETE FROM monitor_scheduler_heartbeat WHERE id = 1").rowcount
    return {
        "task_type": task_type,
        "schedule_keys": keys,
        "claims_deleted": deleted_claims,
        "monitor_run_schedule_keys_cleared": cleared_run_keys,
        "heartbeat_deleted": deleted_heartbeat,
    }


def automatic_schedule_exists(
    conn: sqlite3.Connection,
    task_type: str,
    schedule_key: str,
    *,
    statuses: tuple[str, ...] = ("completed",),
) -> bool:
    if not schedule_key:
        return False
    placeholders = ",".join("?" for _ in statuses)
    row = conn.execute(
        f"""
        SELECT 1
        FROM monitor_runs
        WHERE task_type = ?
          AND schedule_key = ?
          AND mode = ?
          AND status IN ({placeholders})
        LIMIT 1
        """,
        (task_type, schedule_key, AUTOMATION_MODE_AUTOMATIC, *statuses),
    ).fetchone()
    return row is not None


def successful_schedule_exists(conn: sqlite3.Connection, task_type: str, schedule_key: str) -> bool:
    return automatic_schedule_exists(conn, task_type, schedule_key, statuses=("completed",))


def claim_automation_task(
    conn: sqlite3.Connection,
    *,
    task_type: str,
    schedule_key: str,
    claimed_at: str,
    worker_id: str = "",
    lease_minutes: int = 30,
) -> tuple[bool, dict[str, object]]:
    if not schedule_key:
        return True, {}
    lease_until = (datetime.fromisoformat(claimed_at) + timedelta(minutes=lease_minutes)).replace(microsecond=0).isoformat()
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute(
        "SELECT * FROM monitor_automation_claims WHERE task_type = ? AND schedule_key = ?",
        (task_type, schedule_key),
    ).fetchone()
    if existing:
        status = clean_text(existing["status"])
        current_lease = clean_text(existing["lease_until"])
        lease_expired = bool(current_lease and current_lease < claimed_at)
        if status in {"running", "smtp_uncertain"} and not lease_expired:
            conn.commit()
            return False, {"status": status, "schedule_key": schedule_key, "reason": "already_claimed"}
        if status == "completed":
            conn.commit()
            return False, {"status": status, "schedule_key": schedule_key, "reason": "already_completed"}
        if status == "smtp_uncertain":
            conn.commit()
            return False, {"status": status, "schedule_key": schedule_key, "reason": "smtp_uncertain"}
        conn.execute(
            """
            UPDATE monitor_automation_claims
            SET status = 'running',
                claimed_at = ?,
                lease_until = ?,
                completed_at = NULL,
                attempt_count = attempt_count + 1,
                last_error = NULL,
                worker_id = ?
            WHERE task_type = ? AND schedule_key = ?
            """,
            (claimed_at, lease_until, worker_id, task_type, schedule_key),
        )
    else:
        conn.execute(
            """
            INSERT INTO monitor_automation_claims (
                task_type, schedule_key, status, claimed_at, lease_until, worker_id
            )
            VALUES (?, ?, 'running', ?, ?, ?)
            """,
            (task_type, schedule_key, claimed_at, lease_until, worker_id),
        )
    conn.commit()
    return True, {"status": "running", "schedule_key": schedule_key}


def complete_automation_claim(
    conn: sqlite3.Connection,
    *,
    task_type: str,
    schedule_key: str,
    status: str,
    completed_at: str,
    run_id: int | None = None,
    last_error: str = "",
    email_attempted_at: str = "",
) -> None:
    if not schedule_key:
        return
    conn.execute(
        """
        UPDATE monitor_automation_claims
        SET status = ?,
            completed_at = ?,
            lease_until = NULL,
            run_id = COALESCE(?, run_id),
            last_error = ?,
            email_attempted_at = COALESCE(NULLIF(?, ''), email_attempted_at)
        WHERE task_type = ? AND schedule_key = ?
        """,
        (status, completed_at, run_id, last_error, email_attempted_at, task_type, schedule_key),
    )


def record_scheduler_heartbeat(
    conn: sqlite3.Connection,
    *,
    checked_at: str,
    status: str,
    next_task: str = "",
    next_run_at: str = "",
    timezone: str = DEFAULT_SCHEDULER_TIMEZONE,
    last_error: str = "",
    worker_id: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO monitor_scheduler_heartbeat (
            id, checked_at, status, next_task, next_run_at, timezone, last_error, worker_id
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            checked_at = excluded.checked_at,
            status = excluded.status,
            next_task = excluded.next_task,
            next_run_at = excluded.next_run_at,
            timezone = excluded.timezone,
            last_error = excluded.last_error,
            worker_id = excluded.worker_id
        """,
        (checked_at, status, next_task, next_run_at, timezone, last_error, worker_id),
    )


def event_date(value: object) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def agenda_events_for_exact_day(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> list[dict[str, object]]:
    target_day = target.date()
    agenda_current = scheduler_naive_datetime(target)
    events = build_agenda_events(
        conn,
        view="all",
        target_date=target_day,
        type_filter="all",
        include_overdue=True,
        current=agenda_current,
    )
    return [event for event in events if event_date(event.get("date")) == target_day]


def agenda_events_for_week(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> tuple[date, date, list[dict[str, object]]]:
    target_day = target.date()
    start, end = agenda_week_bounds(target_day)
    agenda_current = scheduler_naive_datetime(target)
    events = build_agenda_events(
        conn,
        view="all",
        target_date=target_day,
        type_filter="all",
        include_overdue=True,
        current=agenda_current,
    )
    return start, end, [
        event for event in events
        if (event_day := event_date(event.get("date"))) is not None and start <= event_day <= end
    ]


def day_section_title(day: date, *, current: date) -> str:
    return email_day_section_title(day, current=current)


def build_daily_agenda_email_payload(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    events = agenda_events_for_exact_day(conn, target=target)
    payload = {
        "active_date_label": active_date_label(target.date(), current=target.date()),
        "heading": "Agenda de hoy",
        "subtitle": "Vencimientos del día",
        "sections": [
            {
                "title": "Vencimientos del día",
                "items": events,
            },
        ],
        "counts": {
            "today": len(events),
            "week_rest": 0,
            "total_week": len(events),
        },
    }
    return payload, events


def build_weekly_agenda_email_payload(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    start, end, events = agenda_events_for_week(conn, target=target)
    sections = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        day_items = [event for event in events if event_date(event.get("date")) == day]
        if day_items:
            sections.append({"title": day_section_title(day, current=target.date()), "items": day_items})
    if not sections:
        sections.append({"title": f"Semana {start.isoformat()} a {end.isoformat()}", "items": []})
    payload = {
        "active_date_label": f"{start.isoformat()} a {end.isoformat()}",
        "heading": "Resumen semanal de agenda",
        "subtitle": "Planificación y vencimientos de la semana",
        "sections": sections,
        "counts": {
            "today": sum(1 for event in events if event_date(event.get("date")) == target.date()),
            "week_rest": sum(1 for event in events if event_date(event.get("date")) != target.date()),
            "total_week": len(events),
        },
    }
    return payload, events


def notice_config(task_type: str) -> dict[str, object]:
    return automation_schedule_for_task(task_type)


def notice_label(days: int) -> str:
    if days == 0:
        return "hoy"
    if days == 1:
        return "mañana"
    return f"en {days} días"


def notice_title(days: int) -> str:
    if days == 0:
        return "Vencimientos de hoy"
    if days == 1:
        return "Vencimientos de mañana"
    return f"Vencimientos en {days} días"


def event_due_at(item: dict[str, object]) -> str:
    return clean_text(item.get("datetime") or item.get("date") or item.get("deadline_at") or item.get("fecha_limite"))


def event_alert_key(item: dict[str, object]) -> str:
    source_type = clean_text(item.get("source_type")) or "agenda"
    source_id = clean_text(item.get("source_id") or item.get("id"))
    if not source_id:
        source_id = clean_text(item.get("title") or event_due_at(item))
    return f"{source_type}:{source_id}"


def already_alerted_pairs(
    conn: sqlite3.Connection,
    *,
    notice_level: str,
    events: list[dict[str, object]],
) -> set[tuple[str, str]]:
    pairs = {(event_alert_key(event), event_due_at(event)) for event in events if event_due_at(event)}
    if not pairs:
        return set()
    clauses = " OR ".join("(event_key = ? AND due_at = ?)" for _key, _due_at in pairs)
    params: list[object] = [notice_level]
    for key, due_at in pairs:
        params.extend([key, due_at])
    rows = conn.execute(
        f"""
        SELECT event_key, due_at
        FROM monitor_vencimiento_alerts
        WHERE notice_level = ?
          AND ({clauses})
        """,
        params,
    ).fetchall()
    return {(row["event_key"], row["due_at"]) for row in rows}


def due_notice_events(
    conn: sqlite3.Connection,
    *,
    task_type: str,
    target: datetime,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    config = notice_config(task_type)
    days = int(config.get("notice_days", 0) or 0)
    notice_level = clean_text(config.get("notice_level")) or f"{days}d"
    due_date = target.date() + timedelta(days=days)
    agenda_current = scheduler_naive_datetime(target)
    events = build_agenda_events(
        conn,
        view="all",
        target_date=target.date(),
        type_filter="all",
        include_overdue=True,
        current=agenda_current,
    )
    due_events = [
        event for event in events
        if event_date(event.get("date")) == due_date and event_due_at(event)
    ]
    alerted = already_alerted_pairs(conn, notice_level=notice_level, events=due_events)
    new_events = [
        event for event in due_events
        if (event_alert_key(event), event_due_at(event)) not in alerted
    ]
    return due_events, new_events, {
        **config,
        "notice_days": days,
        "notice_level": notice_level,
        "due_date": due_date.isoformat(),
    }


def build_notice_email_payload(
    *,
    task_type: str,
    target: datetime,
    events: list[dict[str, object]],
    config: dict[str, object],
) -> dict[str, object]:
    days = int(config.get("notice_days", 0) or 0)
    label = notice_label(days)
    title = notice_title(days)
    return {
        "active_date_label": clean_text(config.get("due_date")) or (target.date() + timedelta(days=days)).isoformat(),
        "heading": "Aviso de vencimientos",
        "subtitle": title,
        "sections": [
            {
                "title": f"{title} ({len(events)} elementos)",
                "items": events,
            }
        ],
        "counts": {
            "today": len(events) if days == 0 else 0,
            "week_rest": len(events),
            "total_notice": len(events),
        },
        "notice": {
            "task_type": task_type,
            "label": label,
            "level": clean_text(config.get("notice_level")),
            "days": days,
        },
    }


def notice_email_subject(config: dict[str, object], count: int) -> str:
    days = int(config.get("notice_days", 0) or 0)
    return f"{notice_title(days)} ({count} elementos)"


def record_notice_alerts(
    conn: sqlite3.Connection,
    *,
    task_type: str,
    events: list[dict[str, object]],
    config: dict[str, object],
    monitor_run_id: int,
    recipient: str,
    subject: str,
    generated_at: str,
) -> None:
    notice_level = clean_text(config.get("notice_level"))
    for event in events:
        source_type = clean_text(event.get("source_type")) or "agenda"
        source_id = clean_text(event.get("source_id") or event.get("id"))
        conn.execute(
            """
            INSERT OR IGNORE INTO monitor_vencimiento_alerts (
                task_type,
                notice_level,
                source_type,
                source_id,
                event_key,
                due_at,
                generated_at,
                monitor_run_id,
                recipient,
                subject,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent')
            """,
            (
                task_type,
                notice_level,
                source_type,
                source_id,
                event_alert_key(event),
                event_due_at(event),
                generated_at,
                monitor_run_id,
                recipient,
                subject,
            ),
        )


def build_summary_agenda_email_payload(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> tuple[dict[str, object], int]:
    target_date = target.date().isoformat()
    agenda_current = scheduler_naive_datetime(target)
    today_response = build_agenda_response(
        conn,
        params={"view": "day", "date": target_date, "type": "all"},
        current=agenda_current,
    )
    week_response = build_agenda_response(
        conn,
        params={"view": "week", "date": target_date, "type": "all"},
        current=agenda_current,
    )
    payload = build_operational_email_payload(today_response, week_response)
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    processed_items = int(counts.get("today", 0) or 0) + int(counts.get("week_rest", 0) or 0)
    return payload, processed_items


def build_pending_agenda_email_payload(
    conn: sqlite3.Connection,
    *,
    target: datetime,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    local_target = localize_scheduler_datetime(target)
    response = build_pending_tasks_response(conn, current=local_target.replace(tzinfo=None))
    items = list(response.get("items") or [])
    return build_pending_tasks_email_payload(response, current=local_target), items


def automation_email_subject(task_type: str, target: datetime, *, email_payload: dict[str, object] | None = None) -> str:
    if task_type in {TASK_TYPE_AGENDA_PENDIENTES_DIARIA, TASK_TYPE_AGENDA_DIARIA}:
        local_target = localize_scheduler_datetime(target)
        target_date = local_target.date()
        weekday = SPANISH_WEEKDAYS[target_date.weekday()]
        return f"Agenda Llangón {weekday} {target_date.strftime('%d-%m-%Y')}"
    if task_type == TASK_TYPE_AGENDA_SEMANAL:
        start, end = agenda_week_bounds(target.date())
        return f"Resumen semanal de agenda {start.isoformat()} a {end.isoformat()}"
    return f"Agenda Llangón - resumen operativo {target.date().isoformat()}"


def run_automation_task(
    task_type: str,
    *,
    dry_run: bool = True,
    db_path: str | Path | None = None,
    recipient: str = "",
    email_sender: EmailSender | None = None,
    current: datetime | None = None,
    trigger_mode: str = AUTOMATION_MODE_MANUAL,
) -> dict[str, object]:
    clean_task_type = normalize_task_type(task_type, default="")
    supported_tasks = {
        TASK_TYPE_RESUMEN_AGENDA,
        TASK_TYPE_AGENDA_PENDIENTES_DIARIA,
        TASK_TYPE_AGENDA_DIARIA,
        TASK_TYPE_AGENDA_SEMANAL,
        *NOTICE_TASK_TYPES,
        TASK_TYPE_MONITOR_LICITACIONES,
    }
    if clean_task_type not in TASK_TYPES or clean_task_type not in supported_tasks:
        raise MonitorError(f"Tipo de tarea de monitor no valido: {task_type}")

    started_at = now_iso()
    run_id: int | None = None
    conn: sqlite3.Connection | None = None
    try:
        db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        conn = connect_db(db_file, read_only=False)
        ensure_monitor_schema(conn)
        effective_dry_run = True if dry_run is None else bool(dry_run)
        requested_mode = AUTOMATION_MODE_AUTOMATIC if clean_text(trigger_mode).lower() == AUTOMATION_MODE_AUTOMATIC else AUTOMATION_MODE_MANUAL
        target = localize_scheduler_datetime(current)
        schedule_key = schedule_key_for_task(clean_task_type, target)
        run_mode = "dry-run" if effective_dry_run else requested_mode
        if run_mode == AUTOMATION_MODE_AUTOMATIC:
            canonical_task_type = TASK_TYPE_AGENDA_PENDIENTES_DIARIA if clean_task_type == TASK_TYPE_AGENDA_DIARIA else clean_task_type
            claimed, claim_info = claim_automation_task(
                conn,
                task_type=canonical_task_type,
                schedule_key=schedule_key,
                claimed_at=scheduler_now_iso(target),
            )
            if not claimed:
                return {
                    "task_type": canonical_task_type,
                    "mode": run_mode,
                    "dry_run": effective_dry_run,
                    "schedule_key": schedule_key,
                    "root_path": "",
                    "started_at": started_at,
                    "finished_at": now_iso(),
                    "status": "completed",
                    "monitor_run_id": None,
                    "processed_items_count": 0,
                    "found_markers_count": 0,
                    "route_updates_count": 0,
                    "followed_count": 0,
                    "folders_checked_count": 0,
                    "folders_repaired_count": 0,
                    "folders_broken_count": 0,
                    "platforms_checked_count": 0,
                    "changes_detected_count": 0,
                    "emails_prepared_count": 0,
                    "emails_sent_count": 0,
                    "inventory_files_count": 0,
                    "conflicts": [],
                    "warnings": [],
                    "error_message": "",
                    "task_details": {
                        "message": "Ejecución automática omitida: esta tarea ya se ejecutó o está en curso para el periodo.",
                        "skipped_duplicate": True,
                        "claim": claim_info,
                        "schedule": automation_schedule_for_task(clean_task_type),
                        "schedule_key": schedule_key,
                        "trigger_mode": run_mode,
                    },
                }
        run_id = create_monitor_run(
            conn,
            task_type=clean_task_type,
            mode=run_mode,
            root_path="",
            started_at=started_at,
            dry_run=effective_dry_run,
            schedule_key=schedule_key,
        )
        conn.commit()

        processed_items = 0
        emails_prepared_count = 0
        emails_sent_count = 0
        warnings: list[dict[str, object]] = []
        error_message = ""
        notice_events_to_record: list[dict[str, object]] = []
        notice_config_to_record: dict[str, object] = {}
        task_details: dict[str, object] = {
            "message": "Tarea automática ejecutada desde Monitor.",
            "email_sending_enabled": not effective_dry_run,
            "schedule": automation_schedule_for_task(clean_task_type),
            "schedule_key": schedule_key,
            "trigger_mode": run_mode,
        }
        if clean_task_type == TASK_TYPE_MONITOR_LICITACIONES:
            task_details.update(
                {
                    "message": "Monitor de licitaciones programado y registrado. Consulta real de plataformas pendiente de activar.",
                    "target_date": target.date().isoformat(),
                    "preview": "Ejecución segura sin consulta externa en esta fase.",
                }
            )
        elif table_exists(conn, "agenda_eventos"):
            if clean_task_type == TASK_TYPE_RESUMEN_AGENDA:
                email_payload, processed_items = build_summary_agenda_email_payload(conn, target=target)
            elif clean_task_type in {TASK_TYPE_AGENDA_PENDIENTES_DIARIA, TASK_TYPE_AGENDA_DIARIA}:
                email_payload, events = build_pending_agenda_email_payload(conn, target=target)
                processed_items = len(events)
                if not events:
                    task_details.update(
                        {
                            "message": "No se envía el correo porque no hay elementos en Tareas pendientes.",
                            "target_date": target.date().isoformat(),
                            "counts": {"total": 0, "overdue": 0, "today": 0, "upcoming": 0, "no_date": 0},
                            "preview": "",
                        }
                    )
                    email_payload = {}
            elif clean_task_type == TASK_TYPE_AGENDA_SEMANAL:
                # Legado: no programado. Se conserva solo para históricos antiguos.
                email_payload, events = build_weekly_agenda_email_payload(conn, target=target)
                processed_items = len(events)
            else:
                due_events, new_events, alert_config = due_notice_events(
                    conn,
                    task_type=clean_task_type,
                    target=target,
                )
                processed_items = len(due_events)
                notice_config_to_record = alert_config
                task_details.update(
                    {
                        "target_date": target.date().isoformat(),
                        "due_date": alert_config.get("due_date"),
                        "notice_level": alert_config.get("notice_level"),
                        "notice_days": alert_config.get("notice_days"),
                        "items_due_count": len(due_events),
                        "items_notified_count": len(new_events),
                    }
                )
                if new_events:
                    email_payload = build_notice_email_payload(
                        task_type=clean_task_type,
                        target=target,
                        events=new_events,
                        config=alert_config,
                    )
                    notice_events_to_record = new_events
                else:
                    email_payload = {}
                    task_details.update(
                        {
                            "message": (
                                "No se envía correo porque no hay vencimientos nuevos "
                                f"para el aviso {alert_config.get('notice_level')}."
                            ),
                            "counts": {"today": 0, "week_rest": 0},
                            "preview": "",
                        }
                    )

            if email_payload:
                subject = (
                    notice_email_subject(notice_config_to_record, len(notice_events_to_record))
                    if clean_task_type in NOTICE_TASK_TYPES
                    else automation_email_subject(clean_task_type, target, email_payload=email_payload)
                )
                body = build_operational_email_text(email_payload)
                html_body = build_operational_email_html(
                    email_payload,
                    generated_at=target.replace(microsecond=0).isoformat(),
                )
                counts = email_payload.get("counts") if isinstance(email_payload.get("counts"), dict) else {}
                emails_prepared_count = 1
                task_details.update(
                    {
                        "target_date": target.date().isoformat(),
                        "subject": subject,
                        "recipient": clean_text(recipient),
                        "preview": body[:1200],
                        "counts": counts,
                    }
                )
                if not effective_dry_run:
                    if not clean_text(recipient):
                        error_message = "No hay email de pruebas configurado para Monitor."
                        warnings.append({"code": "missing_monitor_test_email", "message": error_message})
                    elif email_sender is None:
                        error_message = "No hay mecanismo de envío configurado para Monitor."
                        warnings.append({"code": "missing_monitor_email_sender", "message": error_message})
                    else:
                        sent_at, error = email_sender(clean_text(recipient), subject, body, html_body)
                        if error:
                            error_message = error
                            warnings.append({"code": "monitor_email_error", "message": error})
                        else:
                            emails_sent_count = 1
                            task_details["sent_at"] = sent_at or now_iso()
                            if clean_task_type in NOTICE_TASK_TYPES and notice_events_to_record:
                                record_notice_alerts(
                                    conn,
                                    task_type=clean_task_type,
                                    events=notice_events_to_record,
                                    config=notice_config_to_record,
                                    monitor_run_id=run_id,
                                    recipient=clean_text(recipient),
                                    subject=subject,
                                    generated_at=task_details["sent_at"],
                                )
        else:
            error_message = "La tabla de agenda no existe."
            warnings.append({"code": "agenda_table_missing", "message": error_message})

        report: dict[str, object] = {
            "task_type": clean_task_type,
            "mode": run_mode,
            "dry_run": effective_dry_run,
            "schedule_key": schedule_key,
            "root_path": "",
            "started_at": started_at,
            "finished_at": now_iso(),
            "status": "failed" if error_message else "completed",
            "monitor_run_id": run_id,
            "processed_items_count": processed_items,
            "found_markers_count": 0,
            "route_updates_count": 0,
            "followed_count": 0,
            "folders_checked_count": 0,
            "folders_repaired_count": 0,
            "folders_broken_count": 0,
            "platforms_checked_count": 0,
            "changes_detected_count": int(task_details.get("items_notified_count", 0) or 0)
            if clean_task_type in NOTICE_TASK_TYPES
            else 0,
            "emails_prepared_count": emails_prepared_count,
            "emails_sent_count": emails_sent_count,
            "inventory_files_count": 0,
            "conflicts": [],
            "warnings": warnings,
            "error_message": error_message,
            "task_details": task_details,
        }
        finish_monitor_run(conn, run_id, report, error_message)
        if run_mode == AUTOMATION_MODE_AUTOMATIC:
            complete_automation_claim(
                conn,
                task_type=TASK_TYPE_AGENDA_PENDIENTES_DIARIA if clean_task_type == TASK_TYPE_AGENDA_DIARIA else clean_task_type,
                schedule_key=schedule_key,
                status="failed" if error_message else "completed",
                completed_at=scheduler_now_iso(target),
                run_id=run_id,
                last_error=error_message,
                email_attempted_at=clean_text(task_details.get("sent_at")),
            )
        conn.commit()
        return report
    except sqlite3.Error as exc:
        if conn is not None and run_id is not None:
            error_report = {
                "finished_at": now_iso(),
                "status": "failed",
                "processed_items_count": 0,
                "found_markers_count": 0,
                "route_updates_count": 0,
                "followed_count": 0,
                "folders_checked_count": 0,
                "folders_repaired_count": 0,
                "folders_broken_count": 1,
                "platforms_checked_count": 0,
                "changes_detected_count": 0,
                "emails_prepared_count": 0,
                "emails_sent_count": 0,
                "inventory_files_count": 0,
                "conflicts": [],
                "warnings": [{"code": "automation_task_error", "message": str(exc)}],
            }
            finish_monitor_run(conn, run_id, error_report, str(exc))
            conn.commit()
        raise MonitorError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
