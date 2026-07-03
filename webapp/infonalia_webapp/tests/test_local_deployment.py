from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.backup_sqlite import create_backup
from webapp.infonalia_webapp.deployment import PROJECT_ROOT
from webapp.infonalia_webapp.serve import validate_host
from webapp.infonalia_webapp.tests.test_download_endpoint import make_download_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module


def test_health_endpoint_is_public_and_minimal() -> None:
    app = load_app_module()
    handler = make_download_handler(app, path="/api/health")
    handler.current_user = lambda: None

    handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload == {"status": "ok"}


def test_local_server_rejects_non_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFONALIA_ALLOW_NON_LOOPBACK", raising=False)

    validate_host("127.0.0.1")
    validate_host("localhost")

    with pytest.raises(ValueError, match="127.0.0.1"):
        validate_host("0.0.0.0")


def test_sqlite_backup_uses_backup_api_and_preserves_data(tmp_path: Path) -> None:
    source = tmp_path / "infonalia.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE muestra (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)")
    conn.execute("INSERT INTO muestra (nombre) VALUES (?)", ("licitacion",))
    conn.commit()
    conn.close()

    result = create_backup(
        source,
        tmp_path / "backups",
        retention=30,
        now=datetime(2026, 6, 23, 9, 30, 0),
    )

    assert result.destination.exists()
    assert result.integrity_ok is True
    backup_conn = sqlite3.connect(result.destination)
    try:
        row = backup_conn.execute("SELECT nombre FROM muestra WHERE id = 1").fetchone()
    finally:
        backup_conn.close()
    assert row[0] == "licitacion"


def test_sqlite_backup_retention_removes_only_matching_old_backups(tmp_path: Path) -> None:
    source = tmp_path / "infonalia.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE muestra (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    backup_dir = tmp_path / "backups"

    for index in range(4):
        create_backup(
            source,
            backup_dir,
            retention=30,
            now=datetime(2026, 6, 23, 8, 0, 0) + timedelta(seconds=index),
        )

    result = create_backup(
        source,
        backup_dir,
        retention=3,
        now=datetime(2026, 6, 23, 8, 0, 5),
    )

    backups = sorted(backup_dir.glob("infonalia_*.db"))
    assert len(backups) == 3
    assert result.removed_old_backups
    assert result.destination in backups


def test_windows_deployment_scripts_are_relative_and_documented() -> None:
    scripts_root = PROJECT_ROOT / "scripts" / "windows"
    expected = {
        "install_local_deployment.ps1",
        "uninstall_local_deployment.ps1",
        "status_local_deployment.ps1",
        "start_web_production.ps1",
        "run_scheduler_once.ps1",
        "run_agenda_wake_once.ps1",
        "suspend_windows.ps1",
        "run_backup_once.ps1",
    }
    script_names = {path.name for path in scripts_root.glob("*.ps1")}

    assert expected <= script_names
    for script in expected:
        text = (scripts_root / script).read_text(encoding="utf-8")
        assert "C:\\Users\\LLangon03" not in text
        assert (
            "Resolve-Path (Join-Path $ScriptRoot" in text
            or script in {"uninstall_local_deployment.ps1", "suspend_windows.ps1"}
        )

    start_web = (scripts_root / "start_web_production.ps1").read_text(encoding="utf-8")
    assert "Test-WebHealth" in start_web
    assert "webapp.infonalia_webapp.serve" in start_web
    assert "Ejecutando proceso web en primer plano" in start_web
    assert "Start-Process" not in start_web
    hidden_runner = (scripts_root / "run_powershell_hidden.vbs").read_text(encoding="utf-8")
    installer = (scripts_root / "install_local_deployment.ps1").read_text(encoding="utf-8")
    assert "shell.Run(command, 0, True)" in hidden_runner
    assert "wscript.exe" in installer
    assert "run_powershell_hidden.vbs" in installer
    assert "LlangonSuite-AgendaWake" in installer
    assert "-WakeToRun $true" in installer
    assert "LLANGON_AGENDA_WAKE_ENABLED" in installer
    assert "MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY" in installer
    assert "run_agenda_wake_once.ps1" in installer

    scheduler_script = (scripts_root / "run_scheduler_once.ps1").read_text(encoding="utf-8")
    assert "suspend_windows.ps1" not in scheduler_script
    assert "SetSuspendState" not in scheduler_script

    backup_script = (scripts_root / "run_backup_once.ps1").read_text(encoding="utf-8")
    assert "webapp.infonalia_webapp.backup_sqlite" in backup_script
    assert "webapp.infonalia_webapp.full_backup --once" in backup_script
    assert "Copia SQLite fallida. No se ejecuta backup completo." in backup_script

    agenda_wake = (scripts_root / "run_agenda_wake_once.ps1").read_text(encoding="utf-8")
    assert "agenda_wake.log" in agenda_wake
    assert "agenda_pendientes_diaria" in agenda_wake
    assert 'LLANGON_INFONALIA_IMPORT_ENABLED = "0"' in agenda_wake
    assert 'LLANGON_EMAIL_ACTIONS_ENABLED = "0"' in agenda_wake
    assert 'LLANGON_FILE_INVENTORY_ENABLED = "0"' in agenda_wake
    assert 'MONITOR_LICITACIONES_SCHEDULE_ENABLED = "0"' in agenda_wake
    assert "suspend_windows.ps1" in agenda_wake

    suspend_script = (scripts_root / "suspend_windows.ps1").read_text(encoding="utf-8")
    assert "GetLastInputInfo" in suspend_script
    assert "SetSuspendState($false, $false, $false)" in suspend_script
    assert "Suspension omitida: usuario activo" in suspend_script

    status_script = (scripts_root / "status_local_deployment.ps1").read_text(encoding="utf-8")
    assert "AgendaWake:" in status_script
    assert "Wake enabled" in status_script
    assert "agenda_wake.log" in status_script
    assert "Backup completo privado activado" in status_script
    assert "LLANGON_FULL_BACKUP_ROOT" in status_script
    assert "LLANGON_SUITE_FULL_PRIVATE_BACKUP.zip" in status_script

    uninstall_script = (scripts_root / "uninstall_local_deployment.ps1").read_text(encoding="utf-8")
    assert "LlangonSuite-AgendaWake" in uninstall_script

    docs = PROJECT_ROOT / "docs" / "DESPLIEGUE_LOCAL_WINDOWS.md"
    assert docs.exists()
    doc_text = docs.read_text(encoding="utf-8")
    assert "LlangonSuite-Web" in doc_text
    assert "LlangonSuite-AgendaWake" in doc_text
    assert "agenda_pendientes_diaria" in doc_text
    assert "LlangonSuite-Scheduler` no suspende" in doc_text
    assert "LLANGON_FULL_BACKUP_ROOT" in doc_text
    assert "BACKUPS_LL_Suite" in doc_text
    assert "http://127.0.0.1:8787" in doc_text
