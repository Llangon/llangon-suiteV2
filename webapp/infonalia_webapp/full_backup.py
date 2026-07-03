from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .backup_sqlite import BackupError, create_backup
from .deployment import PROJECT_ROOT, load_deployment_env, setup_rotating_logger


FULL_BACKUP_ENABLED_ENV = "LLANGON_FULL_BACKUP_ENABLED"
FULL_BACKUP_ROOT_ENV = "LLANGON_FULL_BACKUP_ROOT"
FULL_BACKUP_RETENTION_DAILY_ENV = "LLANGON_FULL_BACKUP_RETENTION_DAILY"
FULL_BACKUP_RETENTION_MONTHLY_ENV = "LLANGON_FULL_BACKUP_RETENTION_MONTHLY"
FULL_BACKUP_INCLUDE_ENV_ENV = "LLANGON_FULL_BACKUP_INCLUDE_ENV"
FULL_BACKUP_INCLUDE_SECRETS_ENV = "LLANGON_FULL_BACKUP_INCLUDE_SECRETS"
FULL_BACKUP_INCLUDE_CODE_ENV = "LLANGON_FULL_BACKUP_INCLUDE_CODE"
FULL_BACKUP_EXCLUDE_REBUILDABLE_ENV = "LLANGON_FULL_BACKUP_EXCLUDE_REBUILDABLE"
FULL_BACKUP_ALLOW_SHARED_ROOT_ENV = "LLANGON_FULL_BACKUP_ALLOW_SHARED_ROOT"

PRIVATE_BACKUP_MARKER = "LLANGON_SUITE_FULL_PRIVATE_BACKUP"
RESTORE_SCRIPT_NAME = "restore_from_backup.ps1"
RESTORE_GUIDE_NAME = "RESTAURAR_LL_SUITE.md"
MANIFEST_NAME = "backup_manifest.json"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
EXCLUDED_ROOT_DIR_NAMES = {
    ".local_backups",
    ".local_runtime",
    "logs",
    "runtime",
}
EXCLUDED_FILE_SUFFIXES = {".pyc"}
EXCLUDED_FILE_NAMES = {
    PRIVATE_BACKUP_MARKER,
}
MONTH_NAMES_ES = [
    "ENERO",
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
    "JUNIO",
    "JULIO",
    "AGOSTO",
    "SEPTIEMBRE",
    "OCTUBRE",
    "NOVIEMBRE",
    "DICIEMBRE",
]


class FullBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class FullBackupConfig:
    project_root: Path = PROJECT_ROOT
    backup_root: Path | None = None
    enabled: bool = False
    retention_daily: int = 30
    retention_monthly: int = 12
    include_env: bool = True
    include_secrets: bool = True
    include_code: bool = True
    exclude_rebuildable: bool = True
    allow_shared_root: bool = False


@dataclass
class FullBackupResult:
    status: str
    manifest: dict[str, object]
    zip_path: Path | None = None
    manifest_path: Path | None = None
    removed_old_backups: list[Path] = field(default_factory=list)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.environ.get(name, str(default)).strip() or str(default)
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def default_db_path(project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "webapp" / "infonalia_webapp" / "data" / "infonalia.db"


def env_path(project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "webapp" / "infonalia_webapp" / ".env"


def load_config_from_env(*, project_root: Path = PROJECT_ROOT) -> FullBackupConfig:
    raw_root = os.environ.get(FULL_BACKUP_ROOT_ENV, "").strip()
    backup_root = Path(raw_root).expanduser().resolve() if raw_root else None
    return FullBackupConfig(
        project_root=project_root.resolve(),
        backup_root=backup_root,
        enabled=env_bool(FULL_BACKUP_ENABLED_ENV, False),
        retention_daily=env_int(FULL_BACKUP_RETENTION_DAILY_ENV, 30, minimum=1),
        retention_monthly=env_int(FULL_BACKUP_RETENTION_MONTHLY_ENV, 12, minimum=0),
        include_env=env_bool(FULL_BACKUP_INCLUDE_ENV_ENV, True),
        include_secrets=env_bool(FULL_BACKUP_INCLUDE_SECRETS_ENV, True),
        include_code=env_bool(FULL_BACKUP_INCLUDE_CODE_ENV, True),
        exclude_rebuildable=env_bool(FULL_BACKUP_EXCLUDE_REBUILDABLE_ENV, True),
        allow_shared_root=env_bool(FULL_BACKUP_ALLOW_SHARED_ROOT_ENV, False),
    )


def timestamp_for_file(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d_%H%M")


def month_folder_name(value: datetime) -> str:
    return f"{value.month:02d} {MONTH_NAMES_ES[value.month - 1]}"


def backup_destination_dir(config: FullBackupConfig, now: datetime | None = None) -> Path:
    if config.backup_root is None:
        raise FullBackupError(f"{FULL_BACKUP_ROOT_ENV} no esta configurada.")
    value = now or datetime.now()
    return config.backup_root / f"{value.year:04d}" / month_folder_name(value)


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_backup_root(config: FullBackupConfig, *, create: bool) -> list[str]:
    warnings: list[str] = []
    if not config.enabled:
        return warnings
    if config.backup_root is None:
        raise FullBackupError(f"{FULL_BACKUP_ROOT_ENV} no esta configurada. Backup completo desactivado.")
    root = config.backup_root
    if "00000 LLANGON" in {part.upper() for part in root.parts} and not config.allow_shared_root:
        raise FullBackupError(
            "La ruta de backup completo apunta a '00000 LLANGON'. "
            f"Usa {FULL_BACKUP_ROOT_ENV} en Dropbox privado o define {FULL_BACKUP_ALLOW_SHARED_ROOT_ENV}=1 bajo tu responsabilidad."
        )
    if root.exists() and not root.is_dir():
        raise FullBackupError(f"La ruta de backup completo no es una carpeta: {root}")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    else:
        parent = root if root.exists() else root.parent
        if not parent.exists():
            raise FullBackupError(f"No existe la ruta base ni su carpeta padre: {root}")
        warnings.append(f"Dry-run: destino validado, se usaria {root}")
    return warnings


def should_exclude(path: Path, project_root: Path, config: FullBackupConfig) -> tuple[bool, str]:
    rel = path.relative_to(project_root)
    parts = set(rel.parts)
    if config.exclude_rebuildable and parts & EXCLUDED_DIR_NAMES:
        return True, "rebuildable"
    if rel.parts and rel.parts[0] in EXCLUDED_ROOT_DIR_NAMES:
        return True, "runtime_or_local"
    if path.is_file() and path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
        return True, "compiled"
    if path.name in EXCLUDED_FILE_NAMES:
        return True, "backup_marker"
    if rel.as_posix() == "webapp/infonalia_webapp/data/infonalia.db":
        return True, "sqlite_replaced_by_safe_copy"
    if rel.as_posix() == "webapp/infonalia_webapp/.env" and not config.include_env:
        return True, "env_excluded_by_config"
    return False, ""


def iter_project_files(config: FullBackupConfig) -> tuple[list[tuple[Path, str]], dict[str, int]]:
    root = config.project_root
    included: list[tuple[Path, str]] = []
    exclusions: dict[str, int] = {}
    for path in root.rglob("*"):
        excluded, reason = should_exclude(path, root, config)
        if excluded:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            if path.is_dir():
                continue
            continue
        if path.is_file():
            arcname = f"Llangon-SuiteV2/{path.relative_to(root).as_posix()}"
            included.append((path, arcname))
    return included, exclusions


def git_info(project_root: Path) -> dict[str, object]:
    def run_git(args: list[str]) -> str:
        return subprocess.check_output(
            ["git", "-C", str(project_root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()

    info: dict[str, object] = {
        "available": False,
        "commit": "",
        "working_tree_dirty": None,
    }
    try:
        info["commit"] = run_git(["rev-parse", "HEAD"])
        status = run_git(["status", "--porcelain"])
        info["available"] = True
        info["working_tree_dirty"] = bool(status)
    except Exception:
        info["working_tree_dirty"] = None
    return info


def sqlite_basic_query_ok(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        return True
    finally:
        conn.close()


def restore_script_text() -> str:
    return r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$Destination = "",
    [switch]$DryRun
)

if (-not $Destination) {
    $Destination = Read-Host "Carpeta destino para restaurar Llangon Suite V2"
}

$Target = [System.IO.Path]::GetFullPath($Destination)
Write-Host "Destino: $Target"
Write-Host "AVISO: este backup privado puede contener .env con claves y secretos."

if (Test-Path -LiteralPath $Target) {
    $Confirm = Read-Host "La carpeta existe. Escribe RESTAURAR para continuar sin borrar nada"
    if ($Confirm -ne "RESTAURAR") {
        Write-Host "Restauracion cancelada."
        exit 1
    }
}

if ($DryRun) {
    Write-Host "Dry-run: no se copiara ningun fichero."
    exit 0
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null
$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectSource = Join-Path $SourceRoot "Llangon-SuiteV2"
if (-not (Test-Path -LiteralPath $ProjectSource)) {
    throw "No se encuentra la carpeta Llangon-SuiteV2 dentro del backup descomprimido."
}

Get-ChildItem -LiteralPath $ProjectSource -Force | Copy-Item -Destination $Target -Recurse -Force
Write-Host "Archivos copiados. Revisa webapp\infonalia_webapp\.env: contiene secretos."

Set-Location -LiteralPath $Target
if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r "webapp\infonalia_webapp\requirements.txt"
if (Test-Path -LiteralPath "requirements-dev.txt") {
    & ".\.venv\Scripts\python.exe" -m pip install -r "requirements-dev.txt"
}

Write-Host "Restauracion base completada."
Write-Host "Para instalar tareas Windows:"
Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_local_deployment.ps1"
Write-Host "Para probar healthcheck:"
Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_web_production.ps1"
Write-Host "Invoke-WebRequest http://127.0.0.1:8787/api/health -UseBasicParsing"
'''


def restore_guide_text() -> str:
    return """# Restaurar Llangon Suite V2 desde backup privado

Este backup es sensible: incluye la base de datos y, si estaba activado, el fichero `.env` con claves y secretos.
No lo compartas fuera del Dropbox privado.

## Restauración manual recomendada

1. Copia este ZIP al equipo nuevo.
2. Descomprímelo en una carpeta temporal.
3. Abre PowerShell dentro de la carpeta descomprimida.
4. Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\\restore_from_backup.ps1
```

El script pregunta la carpeta destino, copia la Suite, crea `.venv`, instala dependencias e indica cómo reinstalar tareas Windows.

## Comprobación posterior

```powershell
cd C:\\Ruta\\Destino\\Llangon-SuiteV2
powershell -ExecutionPolicy Bypass -File .\\scripts\\windows\\install_local_deployment.ps1
powershell -ExecutionPolicy Bypass -File .\\scripts\\windows\\start_web_production.ps1
Invoke-WebRequest http://127.0.0.1:8787/api/health -UseBasicParsing
```

## Notas

- No sobrescribas una instalación existente sin revisar antes.
- Revisa `webapp/infonalia_webapp/.env`; contiene configuración sensible.
- La carpeta Dropbox de expedientes puede necesitar configuración local nueva.
"""


def build_manifest(
    *,
    config: FullBackupConfig,
    status: str,
    started_at: datetime,
    zip_path: Path | None,
    sqlite_backup_path: Path | None,
    included_files_count: int,
    exclusions: dict[str, int],
    verification: dict[str, object],
    warnings: list[str],
    errors: list[str],
) -> dict[str, object]:
    current_git_info = git_info(config.project_root)
    return {
        "status": status,
        "backup_type": PRIVATE_BACKUP_MARKER,
        "created_at": started_at.isoformat(timespec="seconds"),
        "timestamp": started_at.timestamp(),
        "computer_name": platform.node(),
        "windows_user": getpass.getuser(),
        "project_root": str(config.project_root),
        "backup_root": str(config.backup_root or ""),
        "zip_name": zip_path.name if zip_path else "",
        "zip_path": str(zip_path or ""),
        "zip_size_bytes": zip_path.stat().st_size if zip_path and zip_path.exists() else 0,
        "git": current_git_info,
        "git_commit": current_git_info.get("commit", ""),
        "working_tree_dirty": current_git_info.get("working_tree_dirty"),
        "python_version": sys.version,
        "sqlite_db_source": str(default_db_path(config.project_root)),
        "sqlite_backup_included_from": str(sqlite_backup_path or ""),
        "env_included": bool(config.include_env),
        "include_secrets": bool(config.include_secrets),
        "included_files_count": included_files_count,
        "exclusions_applied": exclusions,
        "verification": verification,
        "warnings": warnings,
        "errors": errors,
    }


def verify_backup_zip(zip_path: Path, *, require_env: bool = True) -> dict[str, object]:
    required = {
        "infonalia_db": "Llangon-SuiteV2/webapp/infonalia_webapp/data/infonalia.db",
        "readme": "Llangon-SuiteV2/README.md",
        "restore_script": RESTORE_SCRIPT_NAME,
        "restore_guide": RESTORE_GUIDE_NAME,
        "manifest": MANIFEST_NAME,
    }
    if require_env:
        required["env"] = "Llangon-SuiteV2/webapp/infonalia_webapp/.env"
    result: dict[str, object] = {
        "ok": False,
        "zip_exists": zip_path.exists(),
        "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "required_entries": {},
        "missing_entries": [],
    }
    if not zip_path.exists() or zip_path.stat().st_size <= 0:
        return result
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
    present: dict[str, bool] = {}
    missing: list[str] = []
    for key, name in required.items():
        present[key] = name in names
        if name not in names:
            missing.append(name)
    result["required_entries"] = present
    result["missing_entries"] = missing
    result["ok"] = not missing
    return result


def safe_retention_delete(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if not is_relative_to(target_resolved, root_resolved):
        raise FullBackupError(f"Retencion bloqueada fuera de la raiz de backups: {target}")
    target_resolved.unlink()


def apply_full_backup_retention(root: Path, *, keep_daily: int, keep_monthly: int) -> list[Path]:
    if keep_daily < 1:
        return []
    backups = sorted(
        root.rglob(f"*_{PRIVATE_BACKUP_MARKER}.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    keep: set[Path] = set(backups[:keep_daily])
    if keep_monthly > 0:
        monthly_seen: set[str] = set()
        for item in backups:
            key = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m")
            if key in monthly_seen:
                continue
            monthly_seen.add(key)
            keep.add(item)
            if len(monthly_seen) >= keep_monthly:
                break
    removed: list[Path] = []
    for item in backups:
        if item in keep:
            continue
        manifest = item.with_name(item.name.replace(".zip", "_manifest.json"))
        safe_retention_delete(root, item)
        removed.append(item)
        if manifest.exists():
            safe_retention_delete(root, manifest)
            removed.append(manifest)
    return removed


def cleanup_audit(project_root: Path = PROJECT_ROOT) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    names = {".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
    prefixes = (".pytest_tmp",)
    for path in project_root.rglob("*"):
        if path.name in names or any(path.name.startswith(prefix) for prefix in prefixes):
            try:
                size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.is_dir() else path.stat().st_size
            except OSError:
                size = 0
            candidates.append({"path": str(path), "is_dir": path.is_dir(), "size_bytes": size})
    return candidates


def create_full_backup(
    *,
    config: FullBackupConfig | None = None,
    db_path: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> FullBackupResult:
    config = config or load_config_from_env()
    started_at = now or datetime.now()
    warnings: list[str] = []
    errors: list[str] = []

    if not config.enabled:
        manifest = build_manifest(
            config=config,
            status="disabled",
            started_at=started_at,
            zip_path=None,
            sqlite_backup_path=None,
            included_files_count=0,
            exclusions={},
            verification={"ok": False, "reason": f"{FULL_BACKUP_ENABLED_ENV}=0"},
            warnings=[f"Backup completo desactivado. Configura {FULL_BACKUP_ENABLED_ENV}=1."],
            errors=[],
        )
        return FullBackupResult(status="disabled", manifest=manifest)

    warnings.extend(validate_backup_root(config, create=not dry_run))
    included_files, exclusions = iter_project_files(config)
    destination_dir = backup_destination_dir(config, started_at)
    zip_name = f"{timestamp_for_file(started_at)}_{PRIVATE_BACKUP_MARKER}.zip"
    zip_path = destination_dir / zip_name
    manifest_path = destination_dir / zip_name.replace(".zip", "_manifest.json")
    source_db = (db_path or default_db_path(config.project_root)).resolve()
    source_env = env_path(config.project_root)

    if config.include_env and not source_env.exists():
        errors.append(f"No se encuentra .env requerido: {source_env}")
    if not source_db.exists():
        errors.append(f"No se encuentra SQLite requerido: {source_db}")
    if errors:
        manifest = build_manifest(
            config=config,
            status="failed",
            started_at=started_at,
            zip_path=zip_path,
            sqlite_backup_path=None,
            included_files_count=len(included_files),
            exclusions=exclusions,
            verification={"ok": False},
            warnings=warnings,
            errors=errors,
        )
        return FullBackupResult(status="failed", manifest=manifest, zip_path=zip_path, manifest_path=manifest_path)

    if dry_run:
        manifest = build_manifest(
            config=config,
            status="dry-run",
            started_at=started_at,
            zip_path=zip_path,
            sqlite_backup_path=None,
            included_files_count=len(included_files),
            exclusions=exclusions,
            verification={"ok": True, "dry_run": True},
            warnings=warnings,
            errors=[],
        )
        return FullBackupResult(status="dry-run", manifest=manifest, zip_path=zip_path, manifest_path=manifest_path)

    destination_dir.mkdir(parents=True, exist_ok=True)
    removed: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="llangon_full_backup_") as tmp:
        tmp_path = Path(tmp)
        sqlite_copy_dir = tmp_path / "sqlite"
        sqlite_result = create_backup(source_db, sqlite_copy_dir, retention=9999, now=started_at)
        sqlite_copy = sqlite_result.destination
        if not sqlite_basic_query_ok(sqlite_copy):
            raise BackupError(f"La copia SQLite no respondio a consulta basica: {sqlite_copy}")

        def write_archive(manifest: dict[str, object]) -> None:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path, arcname in included_files:
                    archive.write(path, arcname)
                archive.write(sqlite_copy, "Llangon-SuiteV2/webapp/infonalia_webapp/data/infonalia.db")
                archive.writestr(RESTORE_SCRIPT_NAME, restore_script_text())
                archive.writestr(RESTORE_GUIDE_NAME, restore_guide_text())
                archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2, default=str))

        manifest_for_zip = build_manifest(
            config=config,
            status="success",
            started_at=started_at,
            zip_path=zip_path,
            sqlite_backup_path=sqlite_copy,
            included_files_count=len(included_files) + 4,
            exclusions=exclusions,
            verification={"ok": False, "pending": True},
            warnings=warnings,
            errors=[],
        )
        write_archive(manifest_for_zip)

        verification = verify_backup_zip(zip_path, require_env=config.include_env)
        status = "success" if verification.get("ok") else "failed"
        if status != "success":
            errors.extend(str(item) for item in verification.get("missing_entries", []))
        final_manifest = build_manifest(
            config=config,
            status=status,
            started_at=started_at,
            zip_path=zip_path,
            sqlite_backup_path=source_db,
            included_files_count=len(included_files) + 4,
            exclusions=exclusions,
            verification=verification,
            warnings=warnings,
            errors=errors,
        )
        # Rebuild once so the manifest inside the ZIP is the final manifest, not a preliminary one.
        write_archive(final_manifest)
        verification = verify_backup_zip(zip_path, require_env=config.include_env)
        status = "success" if verification.get("ok") else "failed"
        if status != "success" and not errors:
            errors.extend(str(item) for item in verification.get("missing_entries", []))
        final_manifest = build_manifest(
            config=config,
            status=status,
            started_at=started_at,
            zip_path=zip_path,
            sqlite_backup_path=source_db,
            included_files_count=len(included_files) + 4,
            exclusions=exclusions,
            verification=verification,
            warnings=warnings,
            errors=errors,
        )
        write_archive(final_manifest)

    verification = verify_backup_zip(zip_path, require_env=config.include_env)
    status = "success" if verification.get("ok") else "failed"
    if status != "success" and not errors:
        errors.extend(str(item) for item in verification.get("missing_entries", []))
    final_manifest = build_manifest(
        config=config,
        status=status,
        started_at=started_at,
        zip_path=zip_path,
        sqlite_backup_path=source_db,
        included_files_count=len(included_files) + 4,
        exclusions=exclusions,
        verification=verification,
        warnings=warnings,
        errors=errors,
    )

    manifest_path.write_text(json.dumps(final_manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if status == "success":
        removed = apply_full_backup_retention(
            config.backup_root or destination_dir,
            keep_daily=config.retention_daily,
            keep_monthly=config.retention_monthly,
        )

    if verbose:
        print(json.dumps(final_manifest, ensure_ascii=False, indent=2, default=str))
    return FullBackupResult(
        status=status,
        manifest=final_manifest,
        zip_path=zip_path,
        manifest_path=manifest_path,
        removed_old_backups=removed,
    )


def latest_full_backup(root: Path) -> dict[str, object]:
    backups = sorted(root.rglob(f"*_{PRIVATE_BACKUP_MARKER}.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not backups:
        return {"found": False}
    latest = backups[0]
    manifest = latest.with_name(latest.name.replace(".zip", "_manifest.json"))
    return {
        "found": True,
        "zip_path": str(latest),
        "zip_size_bytes": latest.stat().st_size,
        "modified_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds"),
        "manifest_path": str(manifest) if manifest.exists() else "",
    }


def main(argv: list[str] | None = None) -> int:
    load_deployment_env()
    parser = argparse.ArgumentParser(description="Backup completo privado restaurable de Llangon Suite V2.")
    parser.add_argument("--once", action="store_true", help="Ejecuta backup completo una vez.")
    parser.add_argument("--dry-run", action="store_true", help="Valida y muestra que se incluiria sin crear ZIP.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--cleanup-audit", action="store_true", help="Lista temporales reconstruibles sin borrar nada.")
    parser.add_argument("--db-path", default="")
    args = parser.parse_args(argv)

    logger = setup_rotating_logger("llangon.full_backup", "full_backup.log")
    if args.cleanup_audit:
        items = cleanup_audit(PROJECT_ROOT)
        print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
        return 0
    if not args.once:
        parser.print_help()
        return 0
    try:
        result = create_full_backup(
            db_path=Path(args.db_path).resolve() if args.db_path else None,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except Exception as exc:
        logger.exception("Fallo el backup completo.")
        print(f"No se pudo crear el backup completo: {exc}")
        return 1
    if result.status == "disabled":
        print(result.manifest["warnings"][0])
        return 0
    if result.status == "dry-run":
        print(f"Dry-run correcto. Destino previsto: {result.zip_path}")
        return 0
    if result.status != "success":
        logger.error("Backup completo fallido: %s", result.manifest.get("errors"))
        print(f"Backup completo fallido. Revisa manifest: {result.manifest_path}")
        return 1
    logger.info("Backup completo creado: %s", result.zip_path)
    print(f"Backup completo creado: {result.zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
