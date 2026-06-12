from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime


MIGRATIONS_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    apply: Callable[[sqlite3.Connection], None]


def _baseline_schema(_: sqlite3.Connection) -> None:
    return None


def _download_jobs_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS download_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            storage_backend TEXT,
            storage_uri TEXT,
            file_manifest TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_licitacion ON download_jobs(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_created ON download_jobs(created_at)")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001_baseline_schema",
        description="Baseline del esquema historico gestionado por init_db",
        apply=_baseline_schema,
    ),
    Migration(
        version="0002_download_jobs",
        description="Tabla preparatoria para jobs de descarga",
        apply=_download_jobs_schema,
    ),
)


def migration_timestamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def applied_migration_versions(conn: sqlite3.Connection) -> set[str]:
    ensure_migrations_table(conn)
    return {
        row[0]
        for row in conn.execute(
            f"SELECT version FROM {MIGRATIONS_TABLE}"
        ).fetchall()
    }


def validate_migrations(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    items = tuple(migrations)
    seen: set[str] = set()
    duplicates: list[str] = []
    for migration in items:
        if not migration.version:
            raise ValueError("Migration version cannot be empty")
        if migration.version in seen:
            duplicates.append(migration.version)
        seen.add(migration.version)
    if duplicates:
        joined = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"Duplicate migration version: {joined}")
    return items


def run_migrations(
    conn: sqlite3.Connection,
    migrations: Iterable[Migration] = MIGRATIONS,
    *,
    now: Callable[[], str] = migration_timestamp,
) -> list[str]:
    items = validate_migrations(migrations)
    ensure_migrations_table(conn)
    applied = applied_migration_versions(conn)
    applied_now: list[str] = []

    for migration in items:
        if migration.version in applied:
            continue
        migration.apply(conn)
        conn.execute(
            f"""
            INSERT INTO {MIGRATIONS_TABLE} (version, description, applied_at)
            VALUES (?, ?, ?)
            """,
            (migration.version, migration.description, now()),
        )
        applied.add(migration.version)
        applied_now.append(migration.version)

    return applied_now
