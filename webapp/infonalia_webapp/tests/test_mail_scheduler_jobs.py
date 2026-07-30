from __future__ import annotations

from datetime import datetime

from webapp.infonalia_webapp.monitor import scheduler
from webapp.infonalia_webapp.monitor.repository import (
    TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,
    TASK_TYPE_FILE_INVENTORY,
    TASK_TYPE_INFONALIA_MAIL_IMPORT,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def test_mail_scheduler_jobs_stay_disabled_by_default(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "0")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_ENABLED", "0")
    with temporary_app_database(app) as db_path:
        reports = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=True)

    assert all(report.get("task_type") not in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR} for report in reports)
    assert all(report.get("task_type") != TASK_TYPE_FILE_INVENTORY for report in reports)


def test_scheduler_status_uses_the_internal_monitor_task_as_source_of_truth() -> None:
    app = load_app_module()
    with temporary_app_database(app) as db_path:
        with app.db_session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO automation_tasks (key, enabled, schedule_value, updated_at, updated_by) "
                "VALUES ('monitor_licitaciones', 1, '08:00,13:00,18:00', '2026-07-20T20:40:00', 'test')"
            )
        status = scheduler.monitor_scheduler_status(db_path)

    assert status["monitor_licitaciones_schedule_enabled"] is True
    assert status["monitor_licitaciones_real_enabled"] is True


def test_mail_scheduler_runs_enabled_jobs_without_interference(monkeypatch) -> None:
    app = load_app_module()
    telegram_sweeps: list[str] = []
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "1")
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_POLL_MINUTES", "30")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_POLL_MINUTES", "10")

    def fake_importer(**_kwargs):
        return {
            "enabled": True,
            "mode": "infonalia_import",
            "imported": 2,
            "duplicates": 0,
            "notified": 1,
            "errors": 0,
        }

    def fake_actions(**_kwargs):
        return {
            "enabled": True,
            "mode": "llangon_cmd_only",
            "processed": 1,
            "errors": 0,
        }

    monkeypatch.setattr("webapp.infonalia_webapp.infonalia_mail_importer.process_mailbox_once", fake_importer)
    monkeypatch.setattr("webapp.infonalia_webapp.email_actions_processor.process_mailbox_once", fake_actions)
    monkeypatch.setattr(
        app,
        "notify_pending_email_action_telegram_events",
        lambda: telegram_sweeps.append("sweep") or {"checked": 1, "sent": 1, "failed": 0, "items": []},
    )

    with temporary_app_database(app) as db_path:
        reports = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=False)
        status = scheduler.monitor_scheduler_status(db_path)

    by_type = {report["task_type"]: report for report in reports if report.get("task_type") in {TASK_TYPE_INFONALIA_MAIL_IMPORT, TASK_TYPE_EMAIL_ACTIONS_PROCESSOR}}
    assert by_type[TASK_TYPE_INFONALIA_MAIL_IMPORT]["imported"] == 2
    assert by_type[TASK_TYPE_EMAIL_ACTIONS_PROCESSOR]["processed"] == 1
    assert by_type[TASK_TYPE_EMAIL_ACTIONS_PROCESSOR]["telegram_notifications"]["sent"] == 1
    assert telegram_sweeps == ["sweep"]
    assert status["infonalia_mail_importer"]["enabled"] is True
    assert status["email_actions_processor"]["enabled"] is True
    assert status["infonalia_mail_importer"]["last_run"]["processed_items_count"] == 2
    assert status["email_actions_processor"]["last_run"]["processed_items_count"] == 1


def test_mail_scheduler_surfaces_strict_import_quarantine_as_failure(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_ENABLED", "0")

    def fake_importer(**_kwargs):
        return {
            "enabled": True,
            "mode": "infonalia_import",
            "imported": 0,
            "duplicates": 0,
            "conflicts": 1,
            "quarantined": 2,
            "notified": 1,
            "errors": 1,
            "last_error": "HTML y texto no coinciden.",
        }

    monkeypatch.setattr("webapp.infonalia_webapp.infonalia_mail_importer.process_mailbox_once", fake_importer)
    with temporary_app_database(app) as db_path:
        reports = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=False)
        with app.db_session() as conn:
            row = conn.execute(
                "SELECT status, processed_items_count, conflicts_count, details_json FROM monitor_runs "
                "WHERE task_type = ? ORDER BY id DESC LIMIT 1",
                (TASK_TYPE_INFONALIA_MAIL_IMPORT,),
            ).fetchone()

    report = next(item for item in reports if item.get("task_type") == TASK_TYPE_INFONALIA_MAIL_IMPORT)
    assert report["errors"] == 1
    assert row["status"] == "failed"
    assert row["processed_items_count"] == 0
    assert row["conflicts_count"] == 3
    assert '"quarantined": 2' in row["details_json"]


def test_mail_scheduler_records_email_action_error_reasons(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "0")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "1")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_ENABLED", "0")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_POLL_MINUTES", "10")

    def fake_actions(**_kwargs):
        return {
            "enabled": True,
            "mode": "llangon_cmd_only",
            "processed": 0,
            "errors": 1,
            "errors_by_reason": {"NO_ALLOWED_SENDERS": 1},
        }

    monkeypatch.setattr("webapp.infonalia_webapp.email_actions_processor.process_mailbox_once", fake_actions)

    with temporary_app_database(app):
        reports = scheduler.run_once(db_path=app.DB_PATH, current=datetime(2026, 6, 5, 12, 0), dry_run=False)
        with app.db_session() as conn:
            row = conn.execute(
                """
                SELECT status, error_message, details_json
                FROM monitor_runs
                WHERE task_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (TASK_TYPE_EMAIL_ACTIONS_PROCESSOR,),
            ).fetchone()

    assert reports[0]["task_type"] == TASK_TYPE_EMAIL_ACTIONS_PROCESSOR
    assert reports[0]["errors"] == 1
    assert row["status"] == "failed"
    assert row["error_message"] == "Errores: NO_ALLOWED_SENDERS"
    assert '"NO_ALLOWED_SENDERS": 1' in row["details_json"]


def test_mail_scheduler_respects_poll_interval(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_POLL_MINUTES", "30")
    calls = {"count": 0}

    def fake_importer(**_kwargs):
        calls["count"] += 1
        return {"enabled": True, "mode": "infonalia_import", "imported": 0, "duplicates": 0, "notified": 0, "errors": 0}

    monkeypatch.setattr("webapp.infonalia_webapp.infonalia_mail_importer.process_mailbox_once", fake_importer)

    with temporary_app_database(app) as db_path:
        first = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=True)
        second = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 5), dry_run=True)

    assert any(report.get("task_type") == TASK_TYPE_INFONALIA_MAIL_IMPORT for report in first)
    assert all(report.get("task_type") != TASK_TYPE_INFONALIA_MAIL_IMPORT for report in second)
    assert calls["count"] == 1


def test_mail_scheduler_does_not_break_with_incomplete_imap_config(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_PORT", "993")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_USER", "")
    monkeypatch.setenv("LLANGON_ACTIONS_IMAP_PASSWORD", "")

    with temporary_app_database(app) as db_path:
        reports = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=False)
        status = scheduler.monitor_scheduler_status(db_path)

    importer_reports = [report for report in reports if report.get("task_type") == TASK_TYPE_INFONALIA_MAIL_IMPORT]
    assert len(importer_reports) == 1
    assert importer_reports[0]["enabled"] is False
    assert "falta configuración IMAP" in importer_reports[0]["message"]
    assert status["infonalia_mail_importer"]["last_run"]["status"] == "completed"


def test_file_inventory_scheduler_runs_when_enabled(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "0")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_ENABLED", "1")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_POLL_MINUTES", "60")
    calls = {"count": 0}

    def fake_run_monitor(*_args, **_kwargs):
        calls["count"] += 1
        return {
            "status": "completed",
            "processed_items_count": 7,
            "inventory_files_count": 0,
            "route_updates_count": 2,
            "conflicts": [{"type": "duplicate_licitacion_marker"}],
            "warnings": [],
            "errors": 0,
        }

    monkeypatch.setattr(scheduler, "run_monitor", fake_run_monitor)

    with temporary_app_database(app) as db_path:
        first = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=True)
        second = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 30), dry_run=True)
        status = scheduler.monitor_scheduler_status(db_path)

    inventory_reports = [report for report in first if report.get("task_type") == TASK_TYPE_FILE_INVENTORY]
    assert len(inventory_reports) == 1
    assert inventory_reports[0]["processed_items_count"] == 7
    assert calls["count"] == 1
    assert all(report.get("task_type") != TASK_TYPE_FILE_INVENTORY for report in second)
    assert status["file_inventory"]["enabled"] is True
    assert status["file_inventory"]["last_run"]["processed_items_count"] == 7
    assert status["file_inventory"]["last_run"]["inventory_files_count"] == 0
    assert status["file_inventory"]["last_run"]["route_updates_count"] == 2
    assert status["file_inventory"]["last_run"]["conflicts_count"] == 1


def test_file_inventory_receives_the_owning_automation_run_id(monkeypatch) -> None:
    app = load_app_module()
    calls: list[dict[str, object]] = []

    def fake_run_monitor(*_args, **kwargs):
        calls.append(kwargs)
        return {
            "status": "completed",
            "inventory_files_count": 0,
            "route_updates_count": 0,
            "conflicts": [],
            "warnings": [],
            "errors": 0,
        }

    monkeypatch.setattr(scheduler, "run_monitor", fake_run_monitor)

    with temporary_app_database(app) as db_path:
        scheduler._run_mail_interval_jobs(
            db_path=db_path,
            current=datetime(2026, 7, 20, 17, 50),
            dry_run=True,
            task_types={TASK_TYPE_FILE_INVENTORY},
            force_selected=True,
            automation_run_id=664,
        )

    assert calls == [{
        "db_path": db_path,
        "dry_run": True,
        "schedule_key": "automation_run:664",
    }]


def test_scheduler_records_inventory_config_error_without_blocking_mail_import(monkeypatch, tmp_path) -> None:
    app = load_app_module()
    missing_root = tmp_path / "missing-dropbox"
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_ENABLED", "1")
    monkeypatch.setenv("LLANGON_FILE_INVENTORY_POLL_MINUTES", "60")
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(missing_root))
    monkeypatch.delenv("INFONALIA_MONITOR_ROOT", raising=False)
    monkeypatch.delenv("INFONALIA_DROPBOX_ROOT", raising=False)
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    monkeypatch.setenv("LLANGON_EMAIL_ACTIONS_ENABLED", "0")

    def fake_importer(**_kwargs):
        return {
            "enabled": True,
            "mode": "infonalia_import",
            "imported": 1,
            "duplicates": 0,
            "notified": 0,
            "errors": 0,
        }

    monkeypatch.setattr("webapp.infonalia_webapp.infonalia_mail_importer.process_mailbox_once", fake_importer)

    with temporary_app_database(app) as db_path:
        reports = scheduler.run_once(db_path=db_path, current=datetime(2026, 6, 5, 12, 0), dry_run=True)
        status = scheduler.monitor_scheduler_status(db_path)

    by_type = {report["task_type"]: report for report in reports if report.get("task_type")}
    assert by_type[TASK_TYPE_FILE_INVENTORY]["errors"] == 1
    assert "LLANGON_DROPBOX_BASE_PATH" in by_type[TASK_TYPE_FILE_INVENTORY]["error_message"]
    assert by_type[TASK_TYPE_INFONALIA_MAIL_IMPORT]["imported"] == 1
    assert status["file_inventory"]["config_ok"] is False
    assert "LLANGON_DROPBOX_BASE_PATH" in status["file_inventory"]["config_error"]
    assert status["file_inventory"]["last_run"]["status"] == "failed"
