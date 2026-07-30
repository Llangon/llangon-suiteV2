from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime

import pytest

from webapp.infonalia_webapp import automation_orchestrator as orchestrator
from webapp.infonalia_webapp import automation_worker


def memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    return conn


def create_app_settings(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
        values.items(),
    )
    conn.commit()


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


def test_tender_monitor_can_be_automatically_enabled_with_three_daily_slots(tmp_path) -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_MONITOR_LICITACIONES)
    assert definition is not None
    assert definition.schedule_type == "daily_times"
    assert definition.daily_times == ("08:00", "13:00", "18:00")

    payload = orchestrator.set_task_enabled(
        orchestrator.TASK_TYPE_MONITOR_LICITACIONES,
        True,
        db_path=tmp_path / "suite.db",
        updated_by="admin",
    )

    assert payload["enabled"] is True
    assert payload["schedule_value"] == "08:00,13:00,18:00"
    assert payload["schedule_label"] == "Diario a las 08:00, 13:00, 18:00"


def record_completed_run(conn: sqlite3.Connection, definition, started_at: str) -> None:
    conn.execute(
        """
        INSERT INTO automation_runs
            (task_key, task_name, source, triggered_by, status, started_at, finished_at,
             duration_seconds, summary, details_json, error_message)
        VALUES (?, ?, 'keeper_tick', '', ?, ?, ?, 1, '', '{}', '')
        """,
        (definition.key, definition.name, orchestrator.STATUS_COMPLETED, started_at, started_at),
    )
    conn.commit()


def test_tender_monitor_daily_slots_catch_up_and_deduplicate() -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_MONITOR_LICITACIONES)
    assert definition is not None
    conn.execute(
        "INSERT OR REPLACE INTO automation_tasks (key, enabled, schedule_value, updated_at) VALUES (?, 1, ?, ?)",
        (definition.key, "08:00,13:00,18:00", "2026-07-19T20:00:00+02:00"),
    )
    conn.commit()

    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 7, 59)) is False
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 9, 15)) is True

    record_completed_run(conn, definition, "2026-07-20T09:15:00+02:00")
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 12, 59)) is False
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 14, 0)) is True

    record_completed_run(conn, definition, "2026-07-20T14:00:00+02:00")
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 17, 59)) is False
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 19, 30)) is True

    record_completed_run(conn, definition, "2026-07-20T19:30:00+02:00")
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 20, 20, 0)) is False


def test_tender_monitor_does_not_recover_slot_before_it_was_enabled() -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_MONITOR_LICITACIONES)
    assert definition is not None
    conn.execute(
        "INSERT OR REPLACE INTO automation_tasks (key, enabled, schedule_value, updated_at) VALUES (?, 1, ?, ?)",
        (definition.key, "08:00,13:00,18:00", "2026-07-20T20:00:00+02:00"),
    )
    conn.commit()

    current = datetime.fromisoformat("2026-07-20T20:30:00+02:00")
    assert orchestrator.due_for_tick(conn, definition, current=current) is False
    assert orchestrator.compute_next_run(conn, definition, current=current) == "2026-07-21T08:00:00+02:00"


def test_tender_monitor_automatic_slot_enqueues_automatic_cycle(monkeypatch, tmp_path) -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_MONITOR_LICITACIONES)
    assert definition is not None
    monkeypatch.setattr(
        orchestrator,
        "launch_tender_monitor_worker",
        lambda cycle_id, **_kwargs: {"ok": True, "cycle_id": cycle_id, "pid": 1234},
    )

    result = orchestrator.execute_task(
        conn,
        definition,
        db_path=tmp_path / "suite.db",
        source="wake_tick",
        triggered_by="windows_wake",
        current=datetime(2026, 7, 21, 8, 15),
    )

    cycle = conn.execute("SELECT * FROM tender_monitor_cycles WHERE id = ?", (result["cycle_id"],)).fetchone()
    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert result["summary"] == "Ciclo automático del monitor encolado."
    assert cycle["origin"] == "automatic_scheduler"
    assert cycle["requested_by"] == "windows_wake"
    assert json.loads(cycle["metadata_json"])["automation_source"] == "wake_tick"


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


def test_mail_automation_payload_uses_configured_poll_minutes(tmp_path) -> None:
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    create_app_settings(
        conn,
        {
            "email_actions_poll_minutes": "17",
            "infonalia_import_poll_minutes": "43",
        },
    )
    conn.close()

    payload = orchestrator.automation_tasks_payload(db_path=db_path)
    by_key = {item["key"]: item for item in payload}

    assert by_key[orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR]["schedule_value"] == "17"
    assert by_key[orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR]["schedule_label"] == "Cada 17 minutos"
    assert by_key[orchestrator.TASK_TYPE_INFONALIA_MAIL_IMPORT]["schedule_value"] == "43"
    assert by_key[orchestrator.TASK_TYPE_INFONALIA_MAIL_IMPORT]["schedule_label"] == "Cada 43 minutos"


def test_mail_automation_due_uses_configured_poll_minutes(tmp_path) -> None:
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    create_app_settings(conn, {"email_actions_poll_minutes": "30"})
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR)
    assert definition is not None
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
            "2026-07-08T08:40:00+02:00",
            "2026-07-08T08:41:00+02:00",
            60,
            "",
            "{}",
            "",
        ),
    )
    conn.commit()

    assert orchestrator.due_for_tick(
        conn,
        definition,
        current=datetime.fromisoformat("2026-07-08T09:00:00+02:00"),
        db_path=db_path,
    ) is False
    assert orchestrator.due_for_tick(
        conn,
        definition,
        current=datetime.fromisoformat("2026-07-08T09:11:00+02:00"),
        db_path=db_path,
    ) is True


def test_mail_task_dispatch_runs_only_the_requested_job(monkeypatch, tmp_path) -> None:
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR)
    assert definition is not None
    calls: list[dict[str, object]] = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return [{"task_type": orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR, "status": "completed"}]

    monkeypatch.setattr(orchestrator, "_run_mail_interval_jobs", fake_runner)

    result = orchestrator.run_mail_interval_task(
        definition,
        tmp_path / "suite.db",
        datetime(2026, 7, 16, 12, 0),
    )

    assert result["task_type"] == orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR
    assert calls[0]["task_types"] == {orchestrator.TASK_TYPE_EMAIL_ACTIONS_PROCESSOR}
    assert calls[0]["force_selected"] is True
    assert calls[0]["automation_run_id"] is None


def test_mail_task_enabled_uses_suite_setting_before_environment(monkeypatch) -> None:
    conn = memory_db()
    create_app_settings(conn, {"infonalia_import_enabled": "0"})
    monkeypatch.setenv("LLANGON_INFONALIA_IMPORT_ENABLED", "1")
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_INFONALIA_MAIL_IMPORT)
    assert definition is not None

    assert orchestrator.task_enabled(conn, definition) is False


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


def test_recover_orphaned_inventory_run_closes_both_history_rows(monkeypatch) -> None:
    conn = memory_db()
    conn.execute(
        """
        CREATE TABLE monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        )
        """
    )
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    owner = f"{orchestrator.socket.gethostname()}:999999:keeper_tick:1"
    acquired, _lock = orchestrator.acquire_lock(
        conn,
        f"task:{definition.key}",
        owner,
        ttl_minutes=60,
        current=datetime(2026, 7, 20, 17, 9),
    )
    assert acquired is True
    run_id = orchestrator.create_run(
        conn,
        definition,
        source="keeper_tick",
        lock_owner_value=owner,
        current=datetime(2026, 7, 20, 17, 9),
    )
    conn.execute(
        "INSERT INTO monitor_runs (mode, started_at, status) VALUES ('inventory', ?, 'running')",
        ("2026-07-20T17:09:01+02:00",),
    )
    conn.commit()
    monkeypatch.setattr(orchestrator, "lock_owner_process_is_alive", lambda _owner: False)

    recovered = orchestrator.recover_orphaned_automation_runs(
        conn,
        current=datetime.fromisoformat("2026-07-20T17:14:00+02:00"),
    )

    assert recovered == [run_id]
    automation_row = conn.execute(
        "SELECT status, finished_at, error_message, details_json FROM automation_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert automation_row["status"] == orchestrator.STATUS_INTERRUPTED
    assert automation_row["finished_at"] == "2026-07-20T17:14:00+02:00"
    assert "ya no está activo" in automation_row["error_message"]
    assert json.loads(automation_row["details_json"])["recovery"]["reason"] == "worker_process_not_alive"
    monitor_row = conn.execute("SELECT * FROM monitor_runs").fetchone()
    assert monitor_row["status"] == orchestrator.STATUS_INTERRUPTED
    assert monitor_row["warnings_count"] == 1
    assert conn.execute("SELECT COUNT(*) FROM automation_locks").fetchone()[0] == 0


def test_recover_inventory_monitor_run_uses_exact_automation_correlation() -> None:
    conn = memory_db()
    conn.execute(
        """
        CREATE TABLE monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            schedule_key TEXT
        )
        """
    )
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    outer_id = orchestrator.create_run(
        conn,
        definition,
        source="manual_worker",
        lock_owner_value="dead-owner",
        current=datetime.fromisoformat("2026-07-20T17:50:23+02:00"),
    )
    orchestrator.finish_run(
        conn,
        outer_id,
        status=orchestrator.STATUS_INTERRUPTED,
        current=datetime.fromisoformat("2026-07-20T17:51:00+02:00"),
    )
    monitor_id = conn.execute(
        """
        INSERT INTO monitor_runs (mode, started_at, status, schedule_key)
        VALUES ('inventory', ?, 'running', ?)
        """,
        (
            "2026-07-20T17:50:24+02:00",
            orchestrator.automation_run_schedule_key(outer_id),
        ),
    ).lastrowid
    conn.commit()

    recovered = orchestrator.recover_orphaned_inventory_monitor_runs(
        conn,
        current=datetime.fromisoformat("2026-07-20T18:02:00+02:00"),
    )

    assert recovered == [monitor_id]
    row = conn.execute("SELECT * FROM monitor_runs WHERE id = ?", (monitor_id,)).fetchone()
    assert row["status"] == orchestrator.STATUS_INTERRUPTED
    assert row["finished_at"] == "2026-07-20T18:02:00+02:00"
    assert row["warnings_count"] == 1


def test_recover_inventory_monitor_run_preserves_live_correlated_worker(monkeypatch) -> None:
    conn = memory_db()
    conn.execute(
        """
        CREATE TABLE monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            schedule_key TEXT
        )
        """
    )
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    owner = f"{orchestrator.socket.gethostname()}:1234:manual_worker:1"
    orchestrator.acquire_lock(
        conn,
        f"task:{definition.key}",
        owner,
        ttl_minutes=60,
        current=datetime.fromisoformat("2026-07-20T17:50:23+02:00"),
    )
    outer_id = orchestrator.create_run(
        conn,
        definition,
        source="manual_worker",
        lock_owner_value=owner,
        current=datetime.fromisoformat("2026-07-20T17:50:23+02:00"),
    )
    monitor_id = conn.execute(
        """
        INSERT INTO monitor_runs (mode, started_at, status, schedule_key)
        VALUES ('inventory', ?, 'running', ?)
        """,
        (
            "2026-07-20T17:50:24+02:00",
            orchestrator.automation_run_schedule_key(outer_id),
        ),
    ).lastrowid
    conn.commit()
    monkeypatch.setattr(orchestrator, "lock_owner_process_is_alive", lambda _owner: True)

    recovered = orchestrator.recover_orphaned_automation_runs(
        conn,
        current=datetime.fromisoformat("2026-07-20T18:02:00+02:00"),
    )

    assert recovered == []
    assert conn.execute("SELECT status FROM monitor_runs WHERE id = ?", (monitor_id,)).fetchone()[0] == "running"


def test_windows_pid_check_never_uses_os_kill(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        orchestrator,
        "windows_process_is_alive",
        lambda pid: calls.append(pid) or True,
    )
    monkeypatch.setattr(
        orchestrator.os,
        "kill",
        lambda *_args: pytest.fail("os.kill must not be called on Windows"),
    )

    assert orchestrator.process_id_is_alive(1234, platform_name="nt") is True
    assert calls == [1234]


def test_process_check_never_sends_signals_on_other_platforms(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator.os,
        "kill",
        lambda *_args: pytest.fail("process checks must never send signals"),
    )

    assert orchestrator.process_id_is_alive(1234, platform_name="posix") is None


@pytest.mark.skipif(os.name != "nt", reason="Windows process handles are required")
def test_windows_pid_check_distinguishes_an_exited_process_with_an_open_handle() -> None:
    process = orchestrator.subprocess.Popen(
        [orchestrator.sys.executable, "-c", "pass"],
        stdin=orchestrator.subprocess.DEVNULL,
        stdout=orchestrator.subprocess.DEVNULL,
        stderr=orchestrator.subprocess.DEVNULL,
    )
    process.wait(timeout=10)

    assert orchestrator.windows_process_is_alive(process.pid) is False


def test_automation_worker_launcher_is_detached_and_has_no_inherited_stdio(monkeypatch, tmp_path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(orchestrator.subprocess, "Popen", fake_popen)

    result = orchestrator.launch_automation_task_worker(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=tmp_path / "suite.db",
        triggered_by="admin",
    )

    assert result == {"ok": True, "pid": 4321, "task_key": orchestrator.TASK_TYPE_FILE_INVENTORY}
    command, kwargs = calls[0]
    assert command[:3] == [orchestrator.sys.executable, "-m", "webapp.infonalia_webapp.automation_worker"]
    assert command[command.index("--task-key") + 1] == orchestrator.TASK_TYPE_FILE_INVENTORY
    assert command[command.index("--db") + 1] == str(tmp_path / "suite.db")
    assert kwargs["cwd"] == str(orchestrator.PROJECT_ROOT)
    assert kwargs["stdin"] is orchestrator.subprocess.DEVNULL
    assert kwargs["stdout"] is orchestrator.subprocess.DEVNULL
    assert kwargs["stderr"] is orchestrator.subprocess.DEVNULL
    assert kwargs["shell"] is False


def test_automation_worker_timeout_terminates_only_its_child_and_recovers(monkeypatch, tmp_path) -> None:
    calls: list[object] = []

    class TimedOutProcess:
        def wait(self, timeout):
            calls.append(("wait", timeout))
            if timeout == 30:
                raise orchestrator.subprocess.TimeoutExpired(["worker"], timeout)
            return 1

        def terminate(self):
            calls.append("terminate")

        def kill(self):
            calls.append("kill")

    monkeypatch.setattr(automation_worker.subprocess, "Popen", lambda *_args, **_kwargs: TimedOutProcess())
    monkeypatch.setattr(
        automation_worker,
        "recover_after_worker_exit",
        lambda db_path: calls.append(("recover", db_path)) or [7],
    )
    args = argparse.Namespace(
        task_key=orchestrator.TASK_TYPE_FILE_INVENTORY,
        db=tmp_path / "suite.db",
        source="manual_worker",
        triggered_by="admin",
        timeout_seconds=30,
    )

    result = automation_worker.supervise(args)

    assert result == 124
    assert "terminate" in calls
    assert "kill" not in calls
    assert ("recover", tmp_path / "suite.db") in calls


def test_automation_worker_records_child_start_failure(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    monkeypatch.setattr(automation_worker, "latest_task_run_id", lambda *_args: 12)
    monkeypatch.setattr(
        automation_worker.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cannot spawn")),
    )
    monkeypatch.setattr(
        automation_worker,
        "record_supervisor_failure",
        lambda args, message: calls.append((args.task_key, message)) or 13,
    )
    args = argparse.Namespace(
        task_key=orchestrator.TASK_TYPE_FILE_INVENTORY,
        db=tmp_path / "suite.db",
        source="manual_worker",
        triggered_by="admin",
        timeout_seconds=30,
    )

    result = automation_worker.supervise(args)

    assert result == 1
    assert calls and calls[0][0] == orchestrator.TASK_TYPE_FILE_INVENTORY
    assert "cannot spawn" in calls[0][1]


def test_worker_launcher_records_failure_before_returning_http_error(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        orchestrator.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("launcher unavailable")),
    )
    monkeypatch.setattr(
        orchestrator,
        "record_automation_start_failure",
        lambda task_key, **kwargs: calls.append({"task_key": task_key, **kwargs}) or 7,
    )

    result = orchestrator.launch_automation_task_worker(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=tmp_path / "suite.db",
        triggered_by="admin",
    )

    assert result["ok"] is False
    assert "launcher unavailable" in result["error"]
    assert calls[0]["task_key"] == orchestrator.TASK_TYPE_FILE_INVENTORY
    assert calls[0]["triggered_by"] == "admin"


def test_automation_start_failure_is_persisted(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "suite.db"
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)

    run_id = orchestrator.record_automation_start_failure(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=db_path,
        source="manual_worker",
        triggered_by="admin",
        error_message="No se pudo crear el proceso hijo.",
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM automation_runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    assert row["status"] == orchestrator.STATUS_FAILED
    assert row["finished_at"]
    assert row["error_message"] == "No se pudo crear el proceso hijo."
    assert json.loads(row["details_json"])["phase"] == "worker_start"


def test_automation_worker_executes_task_only_in_child_mode(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        automation_worker,
        "run_task",
        lambda task_key, **kwargs: calls.append({"task_key": task_key, **kwargs})
        or {"status": orchestrator.STATUS_COMPLETED},
    )

    result = automation_worker.main([
        "--execute",
        "--task-key",
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        "--db",
        str(tmp_path / "suite.db"),
        "--source",
        "manual_worker",
        "--triggered-by",
        "admin",
    ])

    assert result == 0
    assert calls == [{
        "task_key": orchestrator.TASK_TYPE_FILE_INVENTORY,
        "db_path": tmp_path / "suite.db",
        "source": "manual_worker",
        "triggered_by": "admin",
    }]


def test_recover_orphaned_runs_preserves_live_worker(monkeypatch) -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    owner = f"{orchestrator.socket.gethostname()}:1234:keeper_tick:1"
    orchestrator.acquire_lock(
        conn,
        f"task:{definition.key}",
        owner,
        ttl_minutes=60,
        current=datetime(2099, 7, 20, 17, 9),
    )
    run_id = orchestrator.create_run(
        conn,
        definition,
        source="keeper_tick",
        lock_owner_value=owner,
        current=datetime(2099, 7, 20, 17, 9),
    )
    monkeypatch.setattr(orchestrator, "lock_owner_process_is_alive", lambda _owner: True)

    recovered = orchestrator.recover_orphaned_automation_runs(
        conn,
        current=datetime.fromisoformat("2099-07-20T17:14:00+02:00"),
    )

    assert recovered == []
    assert conn.execute("SELECT status FROM automation_runs WHERE id = ?", (run_id,)).fetchone()[0] == "running"
    assert orchestrator.task_payload(conn, definition)["status"] == "running"


def test_task_payload_does_not_report_an_old_orphan_as_running() -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    orchestrator.create_run(
        conn,
        definition,
        source="keeper_tick",
        lock_owner_value="old-owner",
        current=datetime(2026, 7, 20, 16, 0),
    )
    completed_id = orchestrator.create_run(
        conn,
        definition,
        source="keeper_tick",
        lock_owner_value="new-owner",
        current=datetime(2026, 7, 20, 16, 30),
    )
    orchestrator.finish_run(
        conn,
        completed_id,
        status=orchestrator.STATUS_COMPLETED,
        current=datetime(2026, 7, 20, 16, 31),
    )

    payload = orchestrator.task_payload(conn, definition)

    assert payload["status"] == "idle"
    assert payload["last_run"]["id"] == completed_id


def test_run_task_recovers_an_orphan_before_launching_again(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    orchestrator.ensure_automation_schema(conn)
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    old_owner = f"{orchestrator.socket.gethostname()}:999999:keeper_tick:1"
    orchestrator.acquire_lock(
        conn,
        f"task:{definition.key}",
        old_owner,
        ttl_minutes=60,
        current=datetime(2026, 7, 20, 17, 9),
    )
    old_run_id = orchestrator.create_run(
        conn,
        definition,
        source="keeper_tick",
        lock_owner_value=old_owner,
        current=datetime(2026, 7, 20, 17, 9),
    )
    conn.close()
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)
    monkeypatch.setattr(orchestrator, "lock_owner_process_is_alive", lambda owner: "999999" not in owner)
    monkeypatch.setattr(
        orchestrator,
        "execute_task",
        lambda *_args, **_kwargs: {"status": orchestrator.STATUS_COMPLETED, "summary": "Inventario simulado."},
    )

    result = orchestrator.run_task(
        definition.key,
        db_path=db_path,
        source="manual",
        current=datetime.fromisoformat("2026-07-20T17:14:00+02:00"),
    )

    assert result["status"] == orchestrator.STATUS_COMPLETED
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, status FROM automation_runs ORDER BY id").fetchall()
    assert [(row["id"], row["status"]) for row in rows] == [
        (old_run_id, orchestrator.STATUS_INTERRUPTED),
        (result["run_id"], orchestrator.STATUS_COMPLETED),
    ]
    assert conn.execute("SELECT COUNT(*) FROM automation_locks").fetchone()[0] == 0
    conn.close()


def test_run_task_records_worker_exception_as_failed(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "suite.db"
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)
    monkeypatch.setattr(
        orchestrator,
        "execute_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("inventory exploded")),
    )

    result = orchestrator.run_task(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=db_path,
        source="manual_worker",
    )

    assert result["status"] == orchestrator.STATUS_FAILED
    assert result["error_message"] == "inventory exploded"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status, finished_at, error_message FROM automation_runs").fetchone()
    assert row["status"] == orchestrator.STATUS_FAILED
    assert row["finished_at"]
    assert row["error_message"] == "inventory exploded"
    assert conn.execute("SELECT COUNT(*) FROM automation_locks").fetchone()[0] == 0
    conn.close()


def test_run_task_passes_its_run_id_to_the_inventory_executor(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "suite.db"
    captured: dict[str, object] = {}
    monkeypatch.setattr(orchestrator, "ensure_monitor_schema", lambda _conn: None)

    def fake_execute(*_args, **kwargs):
        captured.update(kwargs)
        return {"status": orchestrator.STATUS_COMPLETED, "summary": "Inventario simulado."}

    monkeypatch.setattr(orchestrator, "execute_task", fake_execute)

    result = orchestrator.run_task(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=db_path,
        source="manual_worker",
    )

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert captured["automation_run_id"] == result["run_id"]


def test_night_suspend_skips_when_download_jobs_are_pending() -> None:
    conn = memory_db()
    conn.execute("CREATE TABLE download_jobs (id INTEGER PRIMARY KEY, status TEXT)")
    conn.execute("INSERT INTO download_jobs (status) VALUES ('pending')")
    conn.commit()

    result = orchestrator.run_night_suspend(conn)

    assert result["status"] == orchestrator.STATUS_SKIPPED
    assert any("descargas en curso" in blocker for blocker in result["blockers"])


def test_pc_restart_is_a_manual_event_and_never_due_for_scheduler() -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_PC_RESTART)

    assert definition is not None
    assert definition.manual_allowed is True
    assert definition.schedule_type == "event"
    assert orchestrator.due_for_tick(conn, definition, current=datetime(2026, 7, 30, 10, 0)) is False


def test_pc_restart_schedules_a_forced_restart_with_a_cancellation_window(monkeypatch) -> None:
    commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        commands.append(command)
        return Completed()

    monkeypatch.setattr(orchestrator.os, "name", "nt")
    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    result = orchestrator.run_pc_restart(source="manual")

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert result["restart_delay_seconds"] == 60
    assert commands == [[
        "shutdown.exe", "/r", "/f", "/t", "60", "/d", "p:4:1", "/c",
        "Reinicio remoto solicitado desde Llangon Suite.",
    ]]


def test_pc_restart_does_not_run_from_a_scheduler_tick(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("El scheduler no debe reiniciar el PC."),
    )

    result = orchestrator.run_pc_restart(source="keeper_tick")

    assert result["status"] == orchestrator.STATUS_SKIPPED


def test_pc_restart_cancellation_uses_windows_abort_command(monkeypatch) -> None:
    commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        commands.append(command)
        return Completed()

    monkeypatch.setattr(orchestrator.os, "name", "nt")
    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)

    result = orchestrator.cancel_pc_restart(source="manual")

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert commands == [["shutdown.exe", "/a"]]


def test_inventory_is_deferred_while_tender_cycle_is_active(monkeypatch) -> None:
    conn = memory_db()
    orchestrator.ensure_tender_monitor_schema(conn)
    cycle_id = orchestrator.create_tender_cycle(conn, origin="test", requested_by="admin")
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    monkeypatch.setattr(
        orchestrator,
        "run_mail_interval_task",
        lambda *_args, **_kwargs: pytest.fail("El inventario no debe iniciarse."),
    )

    result = orchestrator.execute_task(
        conn,
        definition,
        db_path=":memory:",
        source="manual",
    )

    assert result["status"] == orchestrator.STATUS_SKIPPED
    assert result["cycle_id"] == cycle_id


def test_route_reconciliation_releases_schema_transaction_before_executor(monkeypatch) -> None:
    conn = memory_db()
    definition = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    assert definition is not None
    observed: dict[str, object] = {}

    def fake_executor(*_args, **_kwargs):
        observed["in_transaction"] = conn.in_transaction
        return {"status": orchestrator.STATUS_COMPLETED}

    monkeypatch.setattr(orchestrator, "run_mail_interval_task", fake_executor)

    result = orchestrator.execute_task(
        conn,
        definition,
        db_path=":memory:",
        source="manual",
    )

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert observed["in_transaction"] is False


def test_route_reconciliation_run_task_uses_a_second_connection_without_locking(tmp_path, monkeypatch) -> None:
    root = tmp_path / "Replica"
    folder = root / "2026" / "07 JULIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "suite.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            expediente TEXT,
            ruta_carpeta TEXT,
            seguimiento_activo INTEGER NOT NULL DEFAULT 0,
            seguimiento_ultimo_check TEXT,
            seguimiento_ultima_sync TEXT,
            seguimiento_marker_path TEXT,
            seguimiento_marker_warning TEXT,
            updated_at TEXT
        );
        INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at)
        VALUES (33, 'EXP-33', 'ruta antigua', '');
        """
    )
    conn.close()
    monkeypatch.setenv("INFONALIA_MONITOR_ROOT", str(root))

    result = orchestrator.run_task(
        orchestrator.TASK_TYPE_FILE_INVENTORY,
        db_path=db_path,
        source="manual_worker",
    )

    assert result["status"] == orchestrator.STATUS_COMPLETED
    assert result["result"]["route_updates_count"] == 1


def test_monitor_is_deferred_while_inventory_run_is_active(monkeypatch) -> None:
    conn = memory_db()
    inventory = orchestrator.automation_by_key(orchestrator.TASK_TYPE_FILE_INVENTORY)
    monitor = orchestrator.automation_by_key(orchestrator.TASK_TYPE_MONITOR_LICITACIONES)
    assert inventory is not None and monitor is not None
    inventory_run_id = orchestrator.create_run(
        conn,
        inventory,
        source="manual",
        triggered_by="admin",
        lock_owner_value="test",
    )
    monkeypatch.setattr(
        orchestrator,
        "launch_tender_monitor_worker",
        lambda *_args, **_kwargs: pytest.fail("El monitor no debe iniciarse."),
    )

    result = orchestrator.execute_task(
        conn,
        monitor,
        db_path=":memory:",
        source="manual",
    )

    assert result["status"] == orchestrator.STATUS_SKIPPED
    assert result["inventory_run_id"] == inventory_run_id


def test_scheduler_tick_recovers_orphan_tender_before_due_check(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "suite.db"
    conn = orchestrator.connect_db(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY)")
    orchestrator.ensure_monitor_schema(conn)
    orchestrator.ensure_automation_schema(conn)
    orchestrator.ensure_tender_monitor_schema(conn)
    cycle_id = orchestrator.create_tender_cycle(conn, origin="test", requested_by="admin")
    conn.execute(
        "UPDATE tender_monitor_cycles SET created_at = '2026-07-20T08:00:00' WHERE id = ?",
        (cycle_id,),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(orchestrator, "due_for_tick", lambda *_args, **_kwargs: False)

    result = orchestrator.scheduler_tick(
        db_path=db_path,
        current=datetime.fromisoformat("2026-07-20T10:00:00+02:00"),
    )

    assert result["recovered_tender_cycles"] == [cycle_id]
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT status FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)
    ).fetchone()[0] == "failed"
    conn.close()
