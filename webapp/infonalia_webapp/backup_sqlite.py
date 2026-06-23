from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .deployment import default_backup_dir, load_deployment_env, setup_rotating_logger


BACKUP_DIR_ENV = "LLANGON_SQLITE_BACKUP_DIR"
RETENTION_ENV = "LLANGON_SQLITE_BACKUP_RETENTION"
DEFAULT_RETENTION = 30


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    source: Path
    destination: Path
    integrity_ok: bool
    removed_old_backups: list[Path]


def configured_backup_dir() -> Path:
    configured = os.environ.get(BACKUP_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return default_backup_dir()


def configured_retention() -> int:
    raw = os.environ.get(RETENTION_ENV, str(DEFAULT_RETENTION)).strip() or str(DEFAULT_RETENTION)
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_RETENTION


def unique_backup_path(backup_dir: Path, source_db: Path, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = source_db.stem or "infonalia"
    candidate = backup_dir / f"{stem}_{timestamp}.db"
    suffix = 1
    while candidate.exists():
        candidate = backup_dir / f"{stem}_{timestamp}_{suffix}.db"
        suffix += 1
    return candidate


def sqlite_integrity_ok(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")
    finally:
        conn.close()


def apply_retention(backup_dir: Path, source_stem: str, retention: int) -> list[Path]:
    if retention < 1:
        return []
    backups = sorted(
        backup_dir.glob(f"{source_stem}_*.db"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for old_backup in backups[retention:]:
        old_backup.unlink()
        removed.append(old_backup)
    return removed


def create_backup(
    source_db: str | Path,
    backup_dir: str | Path,
    *,
    retention: int = DEFAULT_RETENTION,
    logger: logging.Logger | None = None,
    now: datetime | None = None,
) -> BackupResult:
    source = Path(source_db).expanduser().resolve()
    destination_dir = Path(backup_dir).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise BackupError(f"No se encuentra la base de datos: {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_backup_path(destination_dir, source, now)

    source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()

    integrity_ok = sqlite_integrity_ok(destination)
    if not integrity_ok:
        raise BackupError(f"La copia se creo, pero no supero integrity_check: {destination}")

    removed = apply_retention(destination_dir, source.stem or "infonalia", retention)
    if logger:
        logger.info("Copia SQLite creada: %s", destination)
        if removed:
            logger.info("Copias antiguas eliminadas por retencion: %s", len(removed))
    return BackupResult(
        source=source,
        destination=destination,
        integrity_ok=integrity_ok,
        removed_old_backups=removed,
    )


def default_db_path() -> Path:
    from .app import DB_PATH

    return Path(DB_PATH).resolve()


def main(argv: list[str] | None = None) -> int:
    load_deployment_env()
    parser = argparse.ArgumentParser(description="Copia segura de la base SQLite de Llangon Suite.")
    parser.add_argument("--db-path", default=str(default_db_path()))
    parser.add_argument("--backup-dir", default=str(configured_backup_dir()))
    parser.add_argument("--retention", type=int, default=configured_retention())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logger = setup_rotating_logger("llangon.backup_sqlite", "backup.log")
    source = Path(args.db_path).expanduser().resolve()
    target_dir = Path(args.backup_dir).expanduser().resolve()
    if args.dry_run:
        logger.info("Dry-run backup SQLite: origen=%s destino=%s retencion=%s", source, target_dir, args.retention)
        print(f"Dry-run correcto. Origen: {source}. Destino: {target_dir}.")
        return 0
    try:
        result = create_backup(source, target_dir, retention=args.retention, logger=logger)
    except Exception as exc:
        logger.exception("Fallo la copia SQLite.")
        print(f"No se pudo crear la copia de seguridad: {exc}")
        return 1
    print(f"Copia creada: {result.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

