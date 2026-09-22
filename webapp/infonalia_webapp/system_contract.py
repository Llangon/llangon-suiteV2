from __future__ import annotations

import sqlite3
from typing import Any

from herramientas_python.descargadores.registry import DOWNLOADER_SPECS

try:
    from .actuaciones import ACTUACION_ESTADO_ORDEN
    from .db_migrations import MIGRATIONS, MIGRATIONS_TABLE
    from .licitacion_states import ESTADOS_ORDEN
    from .user_settings import USER_ROLES
except ImportError:  # Compatibilidad con importación directa usada por módulos legacy.
    from actuaciones import ACTUACION_ESTADO_ORDEN
    from db_migrations import MIGRATIONS, MIGRATIONS_TABLE
    from licitacion_states import ESTADOS_ORDEN
    from user_settings import USER_ROLES


CONTRACT_VERSION = "2026-09-12"
LATEST_MIGRATION = MIGRATIONS[-1].version

# Estas son condiciones mínimas del producto, no un inventario de todas las tablas.
ESSENTIAL_TABLES = frozenset(
    {
        MIGRATIONS_TABLE,
        "infonalia_dias",
        "licitaciones",
        "usuarios",
        "app_settings",
        "download_jobs",
        "ai_analysis_jobs",
        "comments",
        "actuaciones",
        "clientes",
        "cliente_envios",
        "automation_tasks",
        "automation_runs",
        "automation_locks",
        "monitor_scheduler_heartbeat",
        "tender_monitor_cycles",
        "tender_monitor_incidents",
    }
)

ESSENTIAL_ROUTES = (
    "/api/health",
    "/api/me",
    "/api/dias",
    "/api/licitaciones",
    "/api/agenda",
    "/api/actuaciones",
    "/api/clientes",
    "/api/config",
    "/api/admin/automation/status",
    "/api/admin/operational-health",
    "/api/tender-monitor",
)

WINDOWS_TASKS = ("LlangonSuite-KeeperTick", "LlangonSuite-WakeTick")


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def validate_database_contract(conn: sqlite3.Connection) -> dict[str, Any]:
    """Validate the durable database contract without changing the database."""

    tables = _table_names(conn)
    missing_tables = sorted(ESSENTIAL_TABLES - tables)

    applied_migrations: set[str] = set()
    if MIGRATIONS_TABLE in tables:
        applied_migrations = {
            str(row[0])
            for row in conn.execute(
                f"SELECT version FROM {MIGRATIONS_TABLE}"
            ).fetchall()
        }
    expected_migrations = {migration.version for migration in MIGRATIONS}
    missing_migrations = sorted(expected_migrations - applied_migrations)

    invalid_roles: list[str] = []
    if "usuarios" in tables:
        invalid_roles = sorted(
            {
                str(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT role FROM usuarios WHERE role IS NOT NULL"
                ).fetchall()
                if str(row[0]) not in USER_ROLES
            }
        )

    return {
        "version": CONTRACT_VERSION,
        "latest_migration": LATEST_MIGRATION,
        "missing_tables": missing_tables,
        "missing_migrations": missing_migrations,
        "invalid_roles": invalid_roles,
        "ok": not missing_tables and not missing_migrations and not invalid_roles,
    }


def system_contract_payload() -> dict[str, Any]:
    """Return the non-secret, machine-readable product contract."""

    return {
        "version": CONTRACT_VERSION,
        "database": {
            "latest_migration": LATEST_MIGRATION,
            "essential_tables": sorted(ESSENTIAL_TABLES),
        },
        "routes": list(ESSENTIAL_ROUTES),
        "roles": sorted(USER_ROLES),
        "licitacion_states": list(ESTADOS_ORDEN),
        "actuacion_states": list(ACTUACION_ESTADO_ORDEN),
        "windows_tasks": list(WINDOWS_TASKS),
        "platforms": sorted(DOWNLOADER_SPECS),
    }
