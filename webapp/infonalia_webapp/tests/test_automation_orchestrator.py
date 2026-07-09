from __future__ import annotations

import sqlite3
from datetime import datetime

from webapp.infonalia_webapp import automation_orchestrator as orchestrator


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    return conn


def test_automation_schema_creates_expected_tables() -> None:
    conn = memory_db()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'automation_%'"
        )
    }

    assert {"automation_tasks", "automation_runs", "automation_locks"}.issubset(tables)


def test_task_enabled_can_be_overridden() -> None:
    conn = memory_db()
    definition = orchestrator.AutomationDefinition(
        key="sample_task",
        name="Sample",
        description="Test task",
        schedule_type="interval",
        default_enabled=True,
        interval_minutes=5,
    )

    assert orchestrator.task_enabled(conn, definition) is True
    conn.execute(
        "INSERT INTO automation_tasks (key, enabled) VALUES (?, ?)",
        (definition.key, 0),
    )
    conn.commit()
    assert orchestrator.task_enabled(conn, definition) is False


def test_daily_task_deduplicates_same_day_unless_manual() -> None:
    conn = memory_db()
    definition = orchestrator.AutomationDefinition(
        key="daily_task",
        name="Daily",
        description="Daily test task",
        schedule_type="daily_time",
        default_enabled=True,
        daily_time="08:00",
        weekdays_only=True,
    )
    current = datetime(2026, 7, 8, 9, 0)

    assert orchestrator.due_for_tick(conn, definition, current=current) is True
    conn.execute(
        """
        INSERT INTO automation_runs
            (task_key, task_name, source, triggered_by, status, started_at, finished_at, duration_seconds, summary, details_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            definition.key,
            definition.name,
            "keeper_tick",
            "",
            orchestrator.STATUS_COMPLETED,
            "2026-07-08T08:01:00",
            "2026-07-08T08:02:00",
            60,
            "",
            "{}",
            "",
        ),
    )
    conn.commit()

    assert orchestrator.due_for_tick(conn, definition, current=current) is False


def test_scheduler_tick_skips_when_global_lock_is_active(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    locked, _lock = orchestrator.acquire_lock(conn, orchestrator.GLOBAL_LOCK_KEY, "other-owner", ttl_minutes=30)
    assert locked is True
    conn.close()

    result = orchestrator.scheduler_tick(db_path=db_path, current=datetime(2026, 7, 8, 9, 0))

    assert result["status"] == "skipped"
    assert "already running" in result["message"]


def test_scheduler_tick_ignores_stale_legacy_global_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)
    monkeypatch.setattr(orchestrator, "AUTOMATIONS", tuple())
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    locked, lock = orchestrator.acquire_lock(
        conn,
        orchestrator.GLOBAL_LOCK_KEY,
        "old-owner",
        ttl_minutes=180,
        current=datetime(2026, 7, 8, 13, 10),
    )
    assert locked is True
    assert str(lock["expires_at"]).startswith("2026-07-08T16:10:00")
    conn.close()

    result = orchestrator.scheduler_tick(db_path=db_path, current=datetime(2026, 7, 8, 13, 26))

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert result["due_count"] == 0


def test_night_suspend_skips_when_download_jobs_are_pending() -> None:
    conn = memory_db()
    conn.execute("CREATE TABLE download_jobs (id INTEGER PRIMARY KEY, status TEXT)")
    conn.execute("INSERT INTO download_jobs (status) VALUES ('pending')")
    conn.commit()

    result = orchestrator.run_night_suspend(conn)

    assert result["status"] == orchestrator.STATUS_SKIPPED
    assert any("descargas en curso" in blocker for blocker in result["blockers"])
