from __future__ import annotations

import argparse
import json
import os
import socket
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from .config import MonitorConfigError, load_monitor_config
from .repository import (
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
    TASK_TYPE_FILE_INVENTORY,
    TASK_TYPE_INFONALIA_MAIL_IMPORT,
    connect_db,
    ensure_monitor_schema,
)
from .service import (
    DEFAULT_DB_PATH,
    DEFAULT_SCHEDULER_TIMEZONE,
    EmailSender,
    env_bool,
    due_automation_task_types,
    localize_scheduler_datetime,
    monitor_automation_schedules,
    record_scheduler_heartbeat,
    reset_scheduler_test_state,
    run_monitor,
    run_due_automation_tasks,
    schedule_runs_on_date,
    scheduler_now_iso,
)

try:
    from ..operational_settings import effective_bool, effective_int
except ImportError:
    from operational_settings import effective_bool, effective_int


TaskRunner = Callable[[datetime], list[dict[str, object]]]


class MonitorScheduler:
    """Legacy in-process wrapper kept for tests; production uses CLI --once."""

    def __init__(
        self,
        *,
        interval_seconds: int,
        task_runner: TaskRunner,
        now_factory: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.interval_seconds = max(5, int(interval_seconds or 60))
        self.task_runner = task_runner
        self.now_factory = now_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.last_check_at = ""
        self.last_error = ""
        self.last_reports: list[dict[str, object]] = []

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="infonalia-monitor-scheduler", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def run_once(self, current: datetime | None = None) -> list[dict[str, object]]:
        target = localize_scheduler_datetime(current or self.now_factory())
        self.last_check_at = target.replace(microsecond=0).isoformat()
        try:
            reports = self.task_runner(target)
        except Exception as exc:  # pragma: no cover
            self.last_error = str(exc)
            self.last_reports = []
            return []
        self.last_error = ""
        self.last_reports = reports
        return reports

    def status(self) -> dict[str, object]:
        now = localize_scheduler_datetime(self.now_factory())
        return {
            "enabled": True,
            "running": self.is_running(),
            "interval_seconds": self.interval_seconds,
            "last_check_at": self.last_check_at,
            "last_error": self.last_error,
            "last_reports_count": len(self.last_reports),
            "due_now": due_automation_task_types(now),
            "timezone": DEFAULT_SCHEDULER_TIMEZONE,
        }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.interval_seconds)


_scheduler: MonitorScheduler | None = None
_scheduler_lock = threading.Lock()


def scheduler_enabled_from_env() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return os.environ.get("MONITOR_SCHEDULER_ENABLED", "0").strip() == "1"


def scheduler_interval_from_env() -> int:
    try:
        return max(1, int(os.environ.get("MONITOR_SCHEDULER_POLL_MINUTES", "5") or "5")) * 60
    except ValueError:
        return 300


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_minutes(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default)) or default))
    except ValueError:
        return default


def operational_minutes(key: str, default: int, *, db_path: str | Path | None = None) -> int:
    return effective_int(key, default, db_path=db_path, minimum=1)


def operational_enabled(key: str, *, db_path: str | Path | None = None) -> bool:
    return effective_bool(key, db_path=db_path)


def file_inventory_config_status() -> dict[str, object]:
    try:
        config = load_monitor_config()
    except MonitorConfigError as exc:
        return {
            "root_path": "",
            "root_source": "",
            "config_ok": False,
            "config_error": str(exc),
        }
    return {
        "root_path": str(config.root_path),
        "root_source": config.root_source,
        "config_ok": config.root_path.exists() and config.root_path.is_dir(),
        "config_error": "" if config.root_path.exists() and config.root_path.is_dir() else "La raíz de reconciliación no existe.",
    }


def _last_task_started(conn, task_type: str) -> datetime | None:
    row = conn.execute(
        """
        SELECT started_at
        FROM monitor_runs
        WHERE task_type = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (task_type,),
    ).fetchone()
    if not row or not row["started_at"]:
        return None
    try:
        return parse_now(row["started_at"])
    except Exception:
        return None


def _interval_task_due(conn, *, task_type: str, current: datetime, interval_minutes: int) -> bool:
    last_started = _last_task_started(conn, task_type)
    if not last_started:
        return True
    return localize_scheduler_datetime(current) - localize_scheduler_datetime(last_started) >= timedelta(minutes=interval_minutes)


def _record_interval_run(
    conn,
    *,
    task_type: str,
    started_at: str,
    finished_at: str,
    status: str,
    dry_run: bool,
    processed_items_count: int = 0,
    emails_sent_count: int = 0,
    inventory_files_count: int = 0,
    route_updates_count: int = 0,
    conflicts_count: int = 0,
    error_message: str = "",
    details: dict[str, object] | None = None,
    schedule_key: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO monitor_runs (
            task_type, mode, root_path, started_at, finished_at, status, dry_run,
            schedule_key, processed_items_count, emails_sent_count, inventory_files_count,
            route_updates_count, conflicts_count, error_message, details_json
        )
        VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_type,
            "dry-run" if dry_run else "automatic",
            started_at,
            finished_at,
            status,
            1 if dry_run else 0,
            schedule_key or localize_scheduler_datetime().date().isoformat(),
            processed_items_count,
            emails_sent_count,
            inventory_files_count,
            route_updates_count,
            conflicts_count,
            error_message,
            json.dumps(details or {}, ensure_ascii=False, sort_keys=True, default=str),
        ),
    )
    return int(cur.lastrowid)


def _interval_error_message(result: dict[str, object]) -> str:
    for key in ("error_message", "message", "error"):
        value = str(result.get(key) or "").strip()
        if value:
            return value
    reasons = result.get("errors_by_reason")
    if isinstance(reasons, dict):
        parts: list[str] = []
        for reason, count in reasons.items():
            label = str(reason or "").strip()
            if not label:
                continue
            try:
                amount = int(count or 0)
            except (TypeError, ValueError):
                amount = 0
            parts.append(f"{label}: {amount}" if amount > 1 else label)
        if parts:
            return "Errores: " + "; ".join(parts)
    if result.get("errors"):
        return "La tarea terminó con errores."
    return ""


def _run_mail_interval_jobs(
    *,
    db_path: str | Path,
    current: datetime,
    dry_run: bool,
    task_types: set[str] | None = None,
    force_selected: bool = False,
    automation_run_id: int | None = None,
) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    db_file = Path(db_path)
    conn = connect_db(db_file)
    ensure_monitor_schema(conn)
    try:
        jobs = [
            (
                TASK_TYPE_FILE_INVENTORY,
                "LLANGON_FILE_INVENTORY_ENABLED",
                env_minutes("LLANGON_FILE_INVENTORY_POLL_MINUTES", 60),
            ),
            (
                TASK_TYPE_INFONALIA_MAIL_IMPORT,
                "infonalia_import_enabled",
                operational_minutes("infonalia_import_poll_minutes", 30, db_path=db_file),
            ),
            (
                TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
                "email_actions_enabled",
                operational_minutes("email_actions_poll_minutes", 10, db_path=db_file),
            ),
        ]
        due_jobs = [
            (task_type, enabled_var, interval)
            for task_type, enabled_var, interval in jobs
            if (
                (task_types is None or task_type in task_types)
                and (
                    force_selected
                    or (
                        (
                            env_bool(enabled_var, False)
                            if enabled_var.startswith("LLANGON_")
                            else operational_enabled(enabled_var, db_path=db_file)
                        )
                        and _interval_task_due(conn, task_type=task_type, current=current, interval_minutes=interval)
                    )
                )
            )
        ]
    finally:
        conn.close()

    if not due_jobs:
        return reports

    app = None
    process_action_mailbox_once = None
    process_infonalia_mailbox_once = None
    settings: dict[str, object] = {}
    if any(
        task_type in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR}
        for task_type, _enabled_var, _interval in due_jobs
    ):
        try:
            from .. import app
            from ..email_actions_processor import process_mailbox_once as process_action_mailbox_once
            from ..infonalia_mail_importer import process_mailbox_once as process_infonalia_mailbox_once
        except ImportError:
            import app  # type: ignore
            from email_actions_processor import process_mailbox_once as process_action_mailbox_once
            from infonalia_mail_importer import process_mailbox_once as process_infonalia_mailbox_once

        settings = app.get_settings()

    for task_type, _enabled_var, _interval in due_jobs:
        started_at = scheduler_now_iso(current)
        error_message = ""
        try:
            if task_type == TASK_TYPE_INFONALIA_MAIL_IMPORT:
                assert app is not None and process_infonalia_mailbox_once is not None
                result = process_infonalia_mailbox_once(
                    dry_run=dry_run,
                    settings=settings,
                    notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html, settings=settings),
                )
                processed = int(result.get("imported", 0) or 0) + int(result.get("duplicates", 0) or 0)
                emails_sent = int(result.get("notified", 0) or 0)
                inventory_count = 0
                route_updates = 0
                conflicts = int(result.get("conflicts", 0) or 0) + int(result.get("quarantined", 0) or 0)
            elif task_type == TASK_TYPE_EMAIL_ACTIONS_PROCESSOR:
                assert app is not None and process_action_mailbox_once is not None
                result = process_action_mailbox_once(
                    db_session_factory=app.db_session,
                    notification_sender=lambda to, subject, body, html: app.send_monitor_email(to, subject, body, html, settings=settings),
                    settings=settings,
                    dry_run=dry_run,
                )
                if not dry_run:
                    try:
                        result["telegram_notifications"] = app.notify_pending_email_action_telegram_events()
                    except Exception as exc:
                        result["telegram_notifications"] = {
                            "checked": 0,
                            "sent": 0,
                            "failed": 1,
                            "items": [],
                            "error": str(exc),
                        }
                processed = int(result.get("processed", 0) or 0)
                emails_sent = 0
                inventory_count = 0
                route_updates = 0
                conflicts = 0
            else:
                result = run_monitor(
                    "repair-routes",
                    db_path=db_file,
                    dry_run=dry_run,
                    schedule_key=(
                        f"automation_run:{automation_run_id}"
                        if automation_run_id is not None
                        else ""
                    ),
                )
                processed = int(result.get("processed_items_count", 0) or 0)
                emails_sent = 0
                inventory_count = 0
                route_updates = int(result.get("route_updates_count", 0) or 0)
                conflicts = len(result.get("conflicts", []) or [])
            status = "failed" if result.get("errors") else "completed"
        except Exception as exc:  # pragma: no cover
            result = {"enabled": True, "task_type": task_type, "errors": 1, "error_message": str(exc)}
            processed = 0
            emails_sent = 0
            inventory_count = 0
            route_updates = 0
            conflicts = 0
            status = "failed"
            error_message = str(exc)
        finished_at = scheduler_now_iso()
        conn = connect_db(db_file)
        ensure_monitor_schema(conn)
        try:
            run_id = _record_interval_run(
                conn,
                task_type=task_type,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                dry_run=dry_run,
                processed_items_count=processed,
                emails_sent_count=emails_sent,
                inventory_files_count=inventory_count,
                route_updates_count=route_updates,
                conflicts_count=conflicts,
                error_message=error_message or _interval_error_message(result),
                details=result,
                schedule_key=localize_scheduler_datetime(current).date().isoformat(),
            )
            conn.commit()
        finally:
            conn.close()
        reports.append({**result, "task_type": task_type, "monitor_run_id": run_id})
    return reports


def build_task_runner(*, db_path: str | Path, recipient_factory: Callable[[], str], email_sender: EmailSender) -> TaskRunner:
    def runner(current: datetime) -> list[dict[str, object]]:
        return run_due_automation_tasks(
            dry_run=False,
            db_path=db_path,
            recipient=recipient_factory(),
            email_sender=email_sender,
            current=current,
        )

    return runner


def start_monitor_scheduler(
    *,
    db_path: str | Path,
    recipient_factory: Callable[[], str],
    email_sender: EmailSender,
    enabled: bool | None = None,
    interval_seconds: int | None = None,
) -> MonitorScheduler | None:
    if enabled is None:
        enabled = False
    if not enabled:
        return None
    with _scheduler_lock:
        global _scheduler
        if _scheduler and _scheduler.is_running():
            return _scheduler
        _scheduler = MonitorScheduler(
            interval_seconds=interval_seconds or scheduler_interval_from_env(),
            task_runner=build_task_runner(db_path=db_path, recipient_factory=recipient_factory, email_sender=email_sender),
        )
        _scheduler.start()
        return _scheduler


def stop_monitor_scheduler() -> None:
    with _scheduler_lock:
        if _scheduler:
            _scheduler.stop()


def next_schedule_preview(current: datetime | None = None) -> dict[str, object]:
    now = localize_scheduler_datetime(current)
    schedules = monitor_automation_schedules()
    candidates: list[tuple[datetime, str]] = []
    for task_type, config in schedules.items():
        times = config.get("times") if isinstance(config.get("times"), list) else [config.get("time")]
        for day_offset in range(0, 8):
            day = now.date() + timedelta(days=day_offset)
            if not schedule_runs_on_date(config, day):
                continue
            for time_text in times:
                if not time_text:
                    continue
                hour, minute = [int(part) for part in str(time_text).split(":", 1)]
                candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
                if candidate > now:
                    candidates.append((candidate, task_type))
    if not candidates:
        return {"task_type": "", "run_at": ""}
    run_at, task_type = min(candidates, key=lambda item: item[0])
    return {"task_type": task_type, "run_at": run_at.replace(microsecond=0).isoformat()}


def monitor_scheduler_status(db_path: str | Path | None = None) -> dict[str, object]:
    enabled = scheduler_enabled_from_env()
    db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    schedules = monitor_automation_schedules()
    status = {
        "enabled": enabled,
        "running": False,
        "interval_seconds": scheduler_interval_from_env(),
        "last_check_at": "",
        "last_error": "",
        "last_reports_count": 0,
        "due_now": due_automation_task_types(),
        "timezone": DEFAULT_SCHEDULER_TIMEZONE,
        "next": next_schedule_preview(),
        "schedules": schedules,
        "agenda_pending_recipients": configured_agenda_pending_recipients(db_path),
        "monitor_licitaciones_schedule_enabled": False,
        "monitor_licitaciones_real_enabled": False,
        "infonalia_mail_importer": {
            "enabled": operational_enabled("infonalia_import_enabled", db_path=db_file),
            "interval_minutes": operational_minutes("infonalia_import_poll_minutes", 30, db_path=db_file),
            "last_run": None,
        },
        "email_actions_processor": {
            "enabled": operational_enabled("email_actions_enabled", db_path=db_file),
            "interval_minutes": operational_minutes("email_actions_poll_minutes", 10, db_path=db_file),
            "last_run": None,
        },
        "file_inventory": {
            "enabled": env_bool("LLANGON_FILE_INVENTORY_ENABLED", False),
            "interval_minutes": env_minutes("LLANGON_FILE_INVENTORY_POLL_MINUTES", 60),
            "last_run": None,
            **file_inventory_config_status(),
        },
        "last_automatic_run": None,
    }
    try:
        conn = connect_db(db_file)
        ensure_monitor_schema(conn)
        monitor_task = conn.execute(
            "SELECT enabled FROM automation_tasks WHERE key = 'monitor_licitaciones'"
        ).fetchone()
        monitor_enabled = bool(monitor_task and int(monitor_task["enabled"] or 0) == 1)
        status["monitor_licitaciones_schedule_enabled"] = monitor_enabled
        status["monitor_licitaciones_real_enabled"] = monitor_enabled
        row = conn.execute("SELECT * FROM monitor_scheduler_heartbeat WHERE id = 1").fetchone()
        if row:
            heartbeat_next_task = row["next_task"] or ""
            heartbeat_next_run_at = row["next_run_at"] or ""
            status.update(
                {
                    "last_check_at": row["checked_at"],
                    "last_error": row["last_error"] or "",
                    "heartbeat_status": row["status"],
                }
            )
            if heartbeat_next_task or heartbeat_next_run_at:
                status["next"] = {"task_type": heartbeat_next_task, "run_at": heartbeat_next_run_at}
        last_run = conn.execute(
            """
            SELECT id, task_type, mode, schedule_key, started_at, finished_at, status,
                   emails_prepared_count, emails_sent_count, error_message
            FROM monitor_runs
            WHERE task_type = 'agenda_pendientes_diaria'
              AND mode = 'automatic'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if last_run:
            status["last_automatic_run"] = {
                "id": last_run["id"],
                "task_type": last_run["task_type"],
                "mode": last_run["mode"],
                "schedule_key": last_run["schedule_key"] or "",
                "started_at": last_run["started_at"] or "",
                "finished_at": last_run["finished_at"] or "",
                "status": last_run["status"] or "",
                "emails_prepared_count": last_run["emails_prepared_count"],
                "emails_sent_count": last_run["emails_sent_count"],
                "error_message": last_run["error_message"] or "",
            }
        for key, task_type in (
            ("infonalia_mail_importer", TASK_TYPE_INFONALIA_MAIL_IMPORT),
            ("email_actions_processor", TASK_TYPE_EMAIL_ACTIONS_PROCESSOR),
            ("file_inventory", TASK_TYPE_FILE_INVENTORY),
        ):
            row = conn.execute(
                """
                SELECT id, task_type, mode, started_at, finished_at, status,
                       processed_items_count, emails_sent_count, error_message,
                       inventory_files_count, route_updates_count, conflicts_count
                FROM monitor_runs
                WHERE task_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (task_type,),
            ).fetchone()
            if row:
                status[key]["last_run"] = {
                    "id": row["id"],
                    "task_type": row["task_type"],
                    "mode": row["mode"],
                    "started_at": row["started_at"] or "",
                    "finished_at": row["finished_at"] or "",
                    "status": row["status"] or "",
                    "processed_items_count": row["processed_items_count"],
                    "emails_sent_count": row["emails_sent_count"],
                    "inventory_files_count": row["inventory_files_count"],
                    "route_updates_count": row["route_updates_count"],
                    "conflicts_count": row["conflicts_count"],
                    "error_message": row["error_message"] or "",
                }
        conn.close()
    except Exception as exc:  # pragma: no cover
        status["last_error"] = str(exc)
    return status


def split_email_recipients(value: object) -> list[str]:
    import re

    recipients: list[str] = []
    for part in re.split(r"[;,\n\r]+", str(value or "")):
        email = part.strip()
        if email and email not in recipients:
            recipients.append(email)
    return recipients


def configured_agenda_pending_recipients(db_path: str | Path | None = None) -> list[str]:
    env_value = os.environ.get("MONITOR_AGENDA_PENDING_EMAIL_TO", "")
    if env_value.strip():
        return split_email_recipients(env_value)
    db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    try:
        conn = connect_db(db_file)
        rows = conn.execute(
            """
            SELECT key, value
            FROM app_settings
            WHERE key IN ('monitor_agenda_pending_email_to', 'monitor_test_email', 'agenda_email_to')
            """
        ).fetchall()
        conn.close()
    except Exception:
        return []
    values = {row["key"]: row["value"] or "" for row in rows}
    return split_email_recipients(
        values.get("monitor_agenda_pending_email_to")
        or values.get("monitor_test_email")
        or values.get("agenda_email_to")
    )


def parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return localize_scheduler_datetime(parsed)


def list_schedule(current: datetime | None = None) -> list[dict[str, object]]:
    now = localize_scheduler_datetime(current)
    schedules = []
    for task_type, config in monitor_automation_schedules().items():
        schedules.append({"task_type": task_type, **config})
    return [{"now": now.replace(microsecond=0).isoformat(), "schedules": schedules, "next": next_schedule_preview(now)}]


def run_once(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    current: datetime | None = None,
    dry_run: bool = False,
    recipient: str = "",
    email_sender: EmailSender | None = None,
    worker_id: str = "",
) -> list[dict[str, object]]:
    now = localize_scheduler_datetime(current)
    effective_recipient = recipient
    effective_email_sender = email_sender
    if not dry_run and (not effective_recipient or effective_email_sender is None):
        from ..app import get_settings, monitor_agenda_pending_recipient, send_monitor_email

        settings = get_settings()
        effective_recipient = effective_recipient or monitor_agenda_pending_recipient(settings=settings)
        effective_email_sender = effective_email_sender or (
            lambda to, subject, body, html: send_monitor_email(to, subject, body, html, settings=settings)
        )
    conn = connect_db(db_path)
    ensure_monitor_schema(conn)
    next_item = next_schedule_preview(now)
    record_scheduler_heartbeat(
        conn,
        checked_at=scheduler_now_iso(now),
        status="dry-run" if dry_run else "checked",
        next_task=str(next_item.get("task_type") or ""),
        next_run_at=str(next_item.get("run_at") or ""),
        timezone=DEFAULT_SCHEDULER_TIMEZONE,
        worker_id=worker_id,
    )
    conn.commit()
    conn.close()
    reports = _run_mail_interval_jobs(db_path=db_path, current=now, dry_run=dry_run)
    reports.extend(run_due_automation_tasks(
        dry_run=dry_run,
        db_path=db_path,
        recipient=effective_recipient,
        email_sender=effective_email_sender,
        current=now,
    ))
    return reports


def reset_test_state(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    schedule_keys: list[str] | None = None,
    task_type: str = "agenda_pendientes_diaria",
) -> dict[str, object]:
    conn = connect_db(db_path)
    ensure_monitor_schema(conn)
    result = reset_scheduler_test_state(conn, task_type=task_type, schedule_keys=schedule_keys)
    conn.commit()
    conn.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runner independiente del scheduler de LlangonSuiteV2.")
    parser.add_argument("--once", action="store_true", help="Comprueba tareas pendientes y termina.")
    parser.add_argument("--tick", action="store_true", help="Ejecuta el orquestador interno unico de automatizaciones.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué ejecutaría sin enviar correos.")
    parser.add_argument("--status", action="store_true", help="Muestra estado del scheduler y trabajos de correo.")
    parser.add_argument("--list-schedule", action="store_true", help="Lista tareas activas y próxima ejecución.")
    parser.add_argument("--reset-test-state", action="store_true", help="Limpia estado temporal del scheduler sin borrar histórico.")
    parser.add_argument("--schedule-key", action="append", default=[], help="Schedule key que se puede liberar para repetir una prueba.")
    parser.add_argument("--task-type", default="agenda_pendientes_diaria", help="Tipo de tarea para reset-test-state.")
    parser.add_argument("--now", help="Fecha/hora ISO simulada en Europe/Madrid si no incluye zona.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--source", default="keeper_tick")
    args = parser.parse_args(argv)
    now = parse_now(args.now)
    if args.tick:
        try:
            from ..automation_orchestrator import scheduler_tick
        except ImportError:
            from automation_orchestrator import scheduler_tick
        print(json.dumps(
            scheduler_tick(db_path=args.db_path, source=args.source, current=now),
            ensure_ascii=False,
            indent=2,
            default=str,
        ))
        return 0
    if args.reset_test_state:
        print(json.dumps(
            reset_test_state(db_path=args.db_path, schedule_keys=args.schedule_key, task_type=args.task_type),
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    if args.list_schedule:
        print(json.dumps(list_schedule(now), ensure_ascii=False, indent=2))
        return 0
    if args.status:
        print(json.dumps(monitor_scheduler_status(args.db_path), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.once or args.dry_run:
        reports = run_once(
            db_path=args.db_path,
            current=now,
            dry_run=args.dry_run,
            worker_id=f"{socket.gethostname()}:{os.getpid()}",
        )
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
