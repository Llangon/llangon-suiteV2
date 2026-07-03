from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from webapp.infonalia_webapp.full_backup import (
    FullBackupConfig,
    FullBackupError,
    PRIVATE_BACKUP_MARKER,
    RESTORE_GUIDE_NAME,
    RESTORE_SCRIPT_NAME,
    apply_full_backup_retention,
    cleanup_audit,
    create_full_backup,
    validate_backup_root,
    verify_backup_zip,
)


def make_project(root: Path, *, include_env: bool = True) -> Path:
    project = root / "Llangon-SuiteV2"
    app_dir = project / "webapp" / "infonalia_webapp"
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True)
    (project / "README.md").write_text("# Llangon Suite V2\n", encoding="utf-8")
    (project / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
    (project / "scripts" / "windows").mkdir(parents=True)
    (project / "scripts" / "windows" / "install_local_deployment.ps1").write_text("Write-Host ok\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DESPLIEGUE_LOCAL_WINDOWS.md").write_text("docs\n", encoding="utf-8")
    (project / "herramientas_python").mkdir()
    (project / "herramientas_python" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (project / "macros").mkdir()
    (project / "macros" / "macro.bas").write_text("Sub Demo()\nEnd Sub\n", encoding="utf-8")
    (app_dir / "requirements.txt").write_text("waitress\n", encoding="utf-8")
    (app_dir / ".env.example").write_text("INFONALIA_HOST=127.0.0.1\n", encoding="utf-8")
    if include_env:
        (app_dir / ".env").write_text("SECRET=valor\n", encoding="utf-8")
    conn = sqlite3.connect(data_dir / "infonalia.db")
    try:
        conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT)")
        conn.execute("INSERT INTO licitaciones (expediente) VALUES ('EXP/1')")
        conn.commit()
    finally:
        conn.close()
    (project / ".venv" / "Scripts").mkdir(parents=True)
    (project / ".venv" / "Scripts" / "python.exe").write_text("fake\n", encoding="utf-8")
    (project / ".pytest_cache").mkdir()
    (project / ".pytest_cache" / "cache.txt").write_text("cache\n", encoding="utf-8")
    (app_dir / "__pycache__").mkdir()
    (app_dir / "__pycache__" / "mod.pyc").write_bytes(b"pyc")
    for name in (
        ".pytest_tmp",
        ".pytest_tmp_ai_inline_all",
        ".pytest_tmp_ai_inline_pdf",
        ".pytest_tmp_ai_json_all",
        ".pytest_tmp_ai_migration_full",
        ".pytest_tmp_codex_full",
        ".pytest_tmp_monitor_final",
        ".pytest_tmp_public_web_full",
    ):
        (project / name).mkdir()
        (project / name / "temporary.txt").write_text("temporal\n", encoding="utf-8")
    for name in (
        "pytest_clean_output.txt",
        "pytest_errors.txt",
        "pytest_errors_2.txt",
        "pytest_errors_3.txt",
        "pytest_full_output.txt",
        "custom_output.txt",
    ):
        (project / name).write_text("salida temporal de pruebas\n", encoding="utf-8")
    return project


def config_for(project: Path, backup_root: Path) -> FullBackupConfig:
    return FullBackupConfig(project_root=project, backup_root=backup_root, enabled=True)


def zip_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return set(archive.namelist())


def test_dry_run_does_not_create_zip(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    backup_root = tmp_path / "private_backups"

    result = create_full_backup(
        config=config_for(project, backup_root),
        now=datetime(2026, 7, 2, 3, 30),
        dry_run=True,
    )

    assert result.status == "dry-run"
    assert result.zip_path is not None
    assert not result.zip_path.exists()
    assert result.manifest["verification"]["dry_run"] is True


def test_real_backup_creates_restorable_zip_and_manifest(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    backup_root = tmp_path / "private_backups"

    result = create_full_backup(
        config=config_for(project, backup_root),
        now=datetime(2026, 7, 2, 3, 30),
    )

    assert result.status == "success"
    assert result.zip_path and result.zip_path.exists()
    assert result.manifest_path and result.manifest_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["backup_type"] == PRIVATE_BACKUP_MARKER
    assert manifest["env_included"] is True
    assert manifest["verification"]["ok"] is True
    assert "git_commit" in manifest
    assert "working_tree_dirty" in manifest

    names = zip_names(result.zip_path)
    assert "Llangon-SuiteV2/webapp/infonalia_webapp/.env" in names
    assert "Llangon-SuiteV2/webapp/infonalia_webapp/data/infonalia.db" in names
    assert "Llangon-SuiteV2/README.md" in names
    assert RESTORE_SCRIPT_NAME in names
    assert RESTORE_GUIDE_NAME in names
    assert "backup_manifest.json" in names
    with zipfile.ZipFile(result.zip_path, "r") as archive:
        internal_manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))
    assert internal_manifest["status"] == "success"
    assert internal_manifest["verification"].get("pending") is not True


def test_rebuildable_directories_are_excluded(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = create_full_backup(config=config_for(project, tmp_path / "backups"), now=datetime(2026, 7, 2, 3, 30))

    names = zip_names(result.zip_path)
    assert all(".venv/" not in name for name in names)
    assert all("__pycache__/" not in name for name in names)
    assert all(".pytest_cache/" not in name for name in names)
    assert all(".pytest_tmp" not in name for name in names)
    assert all(not Path(name).name.startswith("pytest_") for name in names)
    assert all(not Path(name).name.endswith("_output.txt") for name in names)
    assert result.manifest["exclusions_applied"]["test_temporary"] >= 1
    assert result.manifest["exclusions_applied"]["rebuildable"] >= 1


def test_dry_run_reports_test_temporary_exclusions(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    result = create_full_backup(
        config=config_for(project, tmp_path / "backups"),
        now=datetime(2026, 7, 2, 3, 30),
        dry_run=True,
    )

    assert result.status == "dry-run"
    assert result.manifest["exclusions_applied"]["test_temporary"] >= 1
    assert result.manifest["exclusions_applied"]["sqlite_replaced_by_safe_copy"] == 1


def test_cleanup_audit_lists_temporaries_without_deleting(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    items = cleanup_audit(project)

    paths = {Path(str(item["path"])).name for item in items}
    assert ".pytest_tmp_ai_inline_all" in paths
    assert "pytest_errors.txt" in paths
    assert all(item["will_delete"] is False for item in items)
    assert (project / ".pytest_tmp_ai_inline_all").exists()
    assert (project / "pytest_errors.txt").exists()


def test_backup_root_is_required_and_not_shared_by_default(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    disabled = create_full_backup(config=FullBackupConfig(project_root=project, backup_root=None, enabled=False))
    assert disabled.status == "disabled"

    shared_root = tmp_path / "Dropbox" / "00000 LLANGON"
    with pytest.raises(FullBackupError, match="00000 LLANGON"):
        validate_backup_root(FullBackupConfig(project_root=project, backup_root=shared_root, enabled=True), create=False)


def test_retention_only_deletes_inside_backup_root(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    root.mkdir()
    outside = tmp_path / f"outside_{PRIVATE_BACKUP_MARKER}.zip"
    outside.write_text("keep", encoding="utf-8")
    created: list[Path] = []
    for index in range(3):
        item = root / f"2026-07-0{index + 1}_0330_{PRIVATE_BACKUP_MARKER}.zip"
        item.write_text("zip", encoding="utf-8")
        timestamp = (datetime(2026, 7, 1) + timedelta(days=index)).timestamp()
        item.touch()
        created.append(item)

    removed = apply_full_backup_retention(root, keep_daily=1, keep_monthly=0)

    assert outside.exists()
    assert all(path.is_relative_to(root) for path in removed)
    assert len([path for path in created if path.exists()]) == 1


def test_verification_fails_when_env_or_db_are_missing(tmp_path: Path) -> None:
    project = make_project(tmp_path, include_env=False)
    result = create_full_backup(config=config_for(project, tmp_path / "backups"), now=datetime(2026, 7, 2, 3, 30))
    assert result.status == "failed"
    assert ".env" in result.manifest["errors"][0]

    project = make_project(tmp_path / "missing_db")
    (project / "webapp" / "infonalia_webapp" / "data" / "infonalia.db").unlink()
    result = create_full_backup(config=config_for(project, tmp_path / "backups2"), now=datetime(2026, 7, 2, 3, 30))
    assert result.status == "failed"
    assert "SQLite" in result.manifest["errors"][0]


def test_verify_backup_zip_reports_missing_required_entries(tmp_path: Path) -> None:
    zip_path = tmp_path / "broken.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Llangon-SuiteV2/README.md", "readme")

    verification = verify_backup_zip(zip_path, require_env=True)

    assert verification["ok"] is False
    assert "Llangon-SuiteV2/webapp/infonalia_webapp/.env" in verification["missing_entries"]
    assert "Llangon-SuiteV2/webapp/infonalia_webapp/data/infonalia.db" in verification["missing_entries"]
