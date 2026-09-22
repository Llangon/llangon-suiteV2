from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from webapp.infonalia_webapp import automation_orchestrator
from webapp.infonalia_webapp.operational_health import (
    STATUS_DEGRADED,
    STATUS_ERROR,
    STATUS_OK,
    build_operational_health,
)
from webapp.infonalia_webapp.system_contract import (
    ESSENTIAL_ROUTES,
    LATEST_MIGRATION,
    WINDOWS_TASKS,
    system_contract_payload,
    validate_database_contract,
)
from webapp.infonalia_webapp.tests.test_download_endpoint import make_download_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=TZ)


def _windows_payload(now: datetime = NOW) -> dict[str, object]:
    return {
        "items": [
            {
                "name": name,
                "state": "Ready",
                "enabled": True,
                "last_run": (now - timedelta(minutes=5)).isoformat(),
                "next_run": (now + timedelta(minutes=5)).isoformat(),
                "result": 0,
            }
            for name in WINDOWS_TASKS
        ],
        "legacy_warnings": [],
    }


def _health_environment(tmp_path: Path, now: datetime = NOW) -> dict[str, str]:
    dropbox = tmp_path / "dropbox"
    sqlite_backups = tmp_path / "sqlite-backups"
    full_backups = tmp_path / "full-backups"
    dropbox.mkdir()
    sqlite_backups.mkdir()
    full_backups.mkdir()

    sqlite_file = sqlite_backups / "infonalia_20260912.db"
    full_file = full_backups / "2026-09-12_1100_LLANGON_SUITE_FULL_PRIVATE_BACKUP.zip"
    sqlite_file.write_bytes(b"sqlite-backup-placeholder")
    full_file.write_bytes(b"full-backup-placeholder")
    stamp = now.timestamp()
    os.utime(sqlite_file, (stamp, stamp))
    os.utime(full_file, (stamp, stamp))
    return {
        "LLANGON_DROPBOX_BASE_PATH": str(dropbox),
        "LLANGON_SQLITE_BACKUP_DIR": str(sqlite_backups),
        "LLANGON_FULL_BACKUP_ENABLED": "1",
        "LLANGON_FULL_BACKUP_ROOT": str(full_backups),
        "LLANGON_TELEGRAM_ENABLED": "0",
        "CODEX_LOCAL_ENABLED": "0",
        "GEMINI_ENABLED": "0",
    }


def _normalize_test_settings(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for key, value in {
            "smtp_enabled": "0",
            "email_actions_enabled": "0",
            "infonalia_import_enabled": "0",
            "ai_analysis_provider": "disabled",
            "gemini_enabled": "0",
        }.items():
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, NOW.isoformat()),
            )
        conn.execute(
            "INSERT INTO automation_tasks (key, enabled, updated_at, updated_by) VALUES ('full_backup', 1, ?, 'test') "
            "ON CONFLICT(key) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
            (NOW.isoformat(),),
        )
        conn.execute(
            "INSERT INTO automation_tasks (key, enabled, updated_at, updated_by) VALUES ('monitor_licitaciones', 0, ?, 'test') "
            "ON CONFLICT(key) DO UPDATE SET enabled = 0, updated_at = excluded.updated_at",
            (NOW.isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def test_system_contract_is_derived_from_current_modules_and_validates_initialized_db() -> None:
    app = load_app_module()
    with temporary_app_database(app) as db_path:
        conn = sqlite3.connect(db_path)
        try:
            result = validate_database_contract(conn)
        finally:
            conn.close()

    payload = system_contract_payload()
    assert result["ok"] is True
    assert result["latest_migration"] == LATEST_MIGRATION == "0036_tender_monitor_baseline_ownership"
    assert payload["roles"] == ["admin", "nuria"]
    assert payload["platforms"] == [
        "CATALUNYA",
        "COMUNIDAD_MADRID",
        "EUSKADI",
        "JUNTA_ANDALUCIA",
        "NAVARRA",
        "PLACE",
        "XUNTA_DE_GALICIA",
    ]
    assert "/api/admin/operational-health" in ESSENTIAL_ROUTES
    app_source = Path(app.__file__).read_text(encoding="utf-8")
    for route in ESSENTIAL_ROUTES:
        assert route in app_source


def test_scheduler_accepts_windows_running_result_as_healthy(tmp_path: Path) -> None:
    app = load_app_module()
    windows = _windows_payload()
    windows["items"][0]["state"] = "Running"
    windows["items"][0]["result"] = 267009
    with temporary_app_database(app) as db_path:
        _normalize_test_settings(db_path)
        payload = build_operational_health(
            db_path=db_path,
            environ=_health_environment(tmp_path),
            windows_tasks=windows,
            now=NOW,
        )

    scheduler = next(item for item in payload["components"] if item["key"] == "scheduler")
    assert scheduler["status"] == STATUS_OK


def test_operational_health_can_report_everything_ok_without_writing_to_db(tmp_path: Path) -> None:
    app = load_app_module()
    with temporary_app_database(app) as db_path:
        _normalize_test_settings(db_path)
        before = db_path.read_bytes()
        payload = build_operational_health(
            db_path=db_path,
            environ=_health_environment(tmp_path),
            windows_tasks=_windows_payload(),
            now=NOW,
        )
        after = db_path.read_bytes()

    assert payload["status"] == STATUS_OK
    assert payload["needs_attention"] == []
    assert payload["check_policy"] == {
        "destructive": False,
        "external_connections": False,
        "integration_checks": "configuration_only",
    }
    assert before == after


def test_operational_health_detects_stale_download_as_degraded(tmp_path: Path) -> None:
    app = load_app_module()
    with temporary_app_database(app) as db_path:
        _normalize_test_settings(db_path)
        conn = sqlite3.connect(db_path)
        try:
            stamp = (NOW - timedelta(days=3)).isoformat()
            tender_id = conn.execute(
                "INSERT INTO licitaciones (expediente, estado, created_at, updated_at) VALUES ('HEALTH-1', 'Importada', ?, ?)",
                (stamp, stamp),
            ).lastrowid
            conn.execute(
                "INSERT INTO download_jobs (licitacion_id, status, created_at, started_at, updated_at) "
                "VALUES (?, 'running', ?, ?, ?)",
                (tender_id, stamp, stamp, stamp),
            )
            conn.commit()
        finally:
            conn.close()

        payload = build_operational_health(
            db_path=db_path,
            environ=_health_environment(tmp_path),
            windows_tasks=_windows_payload(),
            now=NOW,
        )

    assert payload["status"] == STATUS_DEGRADED
    queues = next(item for item in payload["needs_attention"] if item["key"] == "queues")
    assert queues["details"]["stale"]["downloads"] == 1


def test_operational_health_marks_missing_database_as_error_without_leaking_secrets(tmp_path: Path) -> None:
    secret_values = {
        "GEMINI_API_KEY": "gemini-super-secret",
        "LLANGON_TELEGRAM_BOT_TOKEN": "telegram-super-secret",
        "INFONALIA_SMTP_PASSWORD": "smtp-super-secret",
    }
    payload = build_operational_health(
        db_path=tmp_path / "missing.db",
        environ={**_health_environment(tmp_path), **secret_values},
        windows_tasks=_windows_payload(),
        now=NOW,
    )
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload["status"] == STATUS_ERROR
    assert next(item for item in payload["components"] if item["key"] == "database")["critical"] is True
    assert all(value not in serialized for value in secret_values.values())
    assert all(word not in serialized for word in ("api_key", "password", "token"))


def test_operational_health_endpoint_is_admin_only_and_keeps_public_health_minimal(monkeypatch) -> None:
    app = load_app_module()
    expected = {"status": STATUS_OK, "human_summary": "Sin incidencias."}
    monkeypatch.setattr(app, "windows_tasks_payload", lambda: {"items": []})
    monkeypatch.setattr(app, "build_operational_health", lambda **_kwargs: expected)

    handler = make_download_handler(app, path="/api/admin/operational-health")
    handler.do_GET()
    assert handler.responses[-1] == (HTTPStatus.OK, expected)

    denied = make_download_handler(app, path="/api/admin/operational-health")
    denied.require_admin = lambda: False
    denied.api_admin_operational_health()
    assert denied.responses == []

    public = make_download_handler(app, path="/api/health")
    public.current_user = lambda: None
    public.do_GET()
    assert public.responses[-1] == (HTTPStatus.OK, {"status": "ok"})


def test_windows_task_payload_requests_iso_dates(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **_kwargs):
        captured["script"] = args[-1]
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(automation_orchestrator.subprocess, "run", fake_run)
    payload = automation_orchestrator.windows_tasks_payload()

    assert payload["items"] == []
    assert "LastRunTime.ToString('o')" in str(captured["script"])
    assert "NextRunTime.ToString('o')" in str(captured["script"])


def test_operational_dashboard_is_exception_focused_and_uses_current_defaults() -> None:
    static = Path(__file__).resolve().parents[1] / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    javascript = (static / "app.js").read_text(encoding="utf-8")
    styles = (static / "styles.css").read_text(encoding="utf-8")

    assert "¿Qué necesita atención ahora?" in html
    assert 'id="operational-health-attention"' in html
    assert 'fetch("/api/admin/operational-health")' in javascript
    assert "function renderOperationalHealth(payload)" in javascript
    assert 'automation.agenda_pending_daily_time || "08:00"' in javascript
    assert "automation.file_inventory_poll_minutes || 240" in javascript
    assert ".operational-health-attention" in styles


def test_portal_mutations_are_covered_by_the_central_csrf_gate() -> None:
    app = load_app_module()
    handler = make_download_handler(app)

    for path in (
        "/api/licitaciones/12/portal-preview/generate",
        "/api/portal-publications/7/publish",
        "/api/portal-publications/7/recover-preview",
        "/api/portal-publications/7/rotate-access-code",
        "/api/portal-publications/7/approve-review",
        "/api/portal-publications/7/sync-events",
    ):
        assert handler.is_known_mutating_route("POST", path) is True
        assert handler.csrf_required_for_path("POST", path) is True
