from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from .dropbox_paths import dropbox_base_status
    from .environment import load_env_file
    from .system_contract import WINDOWS_TASKS, system_contract_payload, validate_database_contract
except ImportError:  # Compatibilidad con importación directa usada por módulos legacy.
    from dropbox_paths import dropbox_base_status
    from environment import load_env_file
    from system_contract import WINDOWS_TASKS, system_contract_payload, validate_database_contract


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
DEFAULT_DB_PATH = APP_ROOT / "data" / "infonalia.db"
DEFAULT_TIMEZONE = ZoneInfo("Europe/Madrid")

STATUS_OK = "OK"
STATUS_DEGRADED = "DEGRADADO"
STATUS_ERROR = "ERROR"
STATUS_ORDER = {STATUS_OK: 0, STATUS_DEGRADED: 1, STATUS_ERROR: 2}

SENSITIVE_TOKENS = ("password", "secret", "token", "api_key", "credential")


def _text(value: object) -> str:
    return str(value or "").strip()


def _bool(value: object, default: bool = False) -> bool:
    text = _text(value).lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "si", "sí"}


def _parse_datetime(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=DEFAULT_TIMEZONE)
    return parsed.astimezone(DEFAULT_TIMEZONE)


def _age_hours(value: object, now: datetime) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600)


def _read_only_connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe la base de datos: {path}")
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=3)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _component(
    key: str,
    label: str,
    status: str,
    summary: str,
    *,
    action: str = "",
    critical: bool = False,
    details: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "action": action,
        "critical": critical,
        "details": dict(details or {}),
    }


def _settings(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {
            _text(row[0]): _text(row[1])
            for row in conn.execute("SELECT key, value FROM app_settings").fetchall()
        }
    except sqlite3.Error:
        return {}


def _setting(
    settings: Mapping[str, str],
    environ: Mapping[str, str],
    key: str,
    env_key: str,
    default: str = "",
) -> str:
    return _text(settings.get(key)) or _text(environ.get(env_key)) or default


def _task_override(conn: sqlite3.Connection, key: str) -> bool | None:
    try:
        row = conn.execute(
            "SELECT enabled FROM automation_tasks WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.Error:
        return None
    if row is None or row[0] is None:
        return None
    return bool(row[0])


def _task_enabled(
    conn: sqlite3.Connection,
    environ: Mapping[str, str],
    key: str,
    env_key: str | None,
    default: bool,
) -> bool:
    override = _task_override(conn, key)
    if override is not None:
        return override
    if env_key:
        return _bool(environ.get(env_key), default)
    return default


def _latest_file(root: Path, pattern: str, *, recursive: bool = False) -> Path | None:
    if not root.is_dir():
        return None
    try:
        candidates = root.rglob(pattern) if recursive else root.glob(pattern)
        return max((item for item in candidates if item.is_file()), key=lambda item: item.stat().st_mtime, default=None)
    except OSError:
        return None


def _path_file_age(path: Path | None, now: datetime) -> float | None:
    if path is None:
        return None
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=DEFAULT_TIMEZONE)
    except OSError:
        return None
    return max(0.0, (now - modified).total_seconds() / 3600)


def _database_components(
    db_path: str | Path,
) -> tuple[sqlite3.Connection | None, list[dict[str, Any]], dict[str, Any]]:
    components: list[dict[str, Any]] = []
    contract: dict[str, Any] = {}
    try:
        conn = _read_only_connection(db_path)
        quick_check = _text(conn.execute("PRAGMA quick_check(1)").fetchone()[0])
        if quick_check.lower() != "ok":
            components.append(
                _component(
                    "database",
                    "Base de datos",
                    STATUS_ERROR,
                    "SQLite ha informado de un problema de integridad.",
                    action="Restaurar o reparar la base de datos antes de seguir trabajando.",
                    critical=True,
                    details={"integrity": "failed"},
                )
            )
        else:
            components.append(
                _component(
                    "database",
                    "Base de datos",
                    STATUS_OK,
                    "SQLite accesible en modo de solo lectura e integridad correcta.",
                    critical=True,
                    details={"integrity": "ok"},
                )
            )
        contract = validate_database_contract(conn)
        missing = contract["missing_tables"]
        migrations = contract["missing_migrations"]
        invalid_roles = contract["invalid_roles"]
        if missing or migrations:
            components.append(
                _component(
                    "schema",
                    "Contrato de sistema",
                    STATUS_ERROR,
                    "Faltan elementos esenciales del esquema o migraciones.",
                    action="Revisar las migraciones antes de usar la Suite.",
                    critical=True,
                    details={
                        "latest_migration": contract["latest_migration"],
                        "missing_table_count": len(missing),
                        "missing_migration_count": len(migrations),
                    },
                )
            )
        elif invalid_roles:
            components.append(
                _component(
                    "schema",
                    "Contrato de sistema",
                    STATUS_DEGRADED,
                    "El esquema está completo, pero hay roles no admitidos.",
                    action="Revisar los roles de usuario no reconocidos.",
                    critical=True,
                    details={
                        "latest_migration": contract["latest_migration"],
                        "invalid_role_count": len(invalid_roles),
                    },
                )
            )
        else:
            components.append(
                _component(
                    "schema",
                    "Contrato de sistema",
                    STATUS_OK,
                    f"Esquema completo hasta {contract['latest_migration']}.",
                    critical=True,
                    details={"latest_migration": contract["latest_migration"]},
                )
            )
        return conn, components, contract
    except (OSError, sqlite3.Error) as exc:
        components.append(
            _component(
                "database",
                "Base de datos",
                STATUS_ERROR,
                "No se puede abrir o consultar SQLite.",
                action="Comprobar el archivo y, si procede, restaurar la última copia válida.",
                critical=True,
                details={"error_type": type(exc).__name__},
            )
        )
        return None, components, contract


def _storage_component(environ: Mapping[str, str]) -> dict[str, Any]:
    status = dropbox_base_status(environ)
    if status.ok:
        return _component(
            "storage",
            "Dropbox local",
            STATUS_OK,
            "Carpeta base configurada y disponible en este equipo.",
            details={"configured": True, "available": True, "source": status.source},
        )
    return _component(
        "storage",
        "Dropbox local",
        STATUS_DEGRADED,
        status.error or "La carpeta base no está disponible.",
        action="Comprobar la configuración y la sincronización local de Dropbox.",
        details={"configured": status.configured, "available": False, "source": status.source},
    )


def _scheduler_component(
    conn: sqlite3.Connection,
    now: datetime,
    windows_tasks: Mapping[str, object] | None,
) -> dict[str, Any]:
    if windows_tasks and not windows_tasks.get("error"):
        items = windows_tasks.get("items") or []
        keeper = next(
            (
                item
                for item in items
                if isinstance(item, Mapping)
                and _text(item.get("name")) == "LlangonSuite-KeeperTick"
            ),
            None,
        )
        if keeper is not None:
            last_run = keeper.get("last_run")
            age = _age_hours(last_run, now)
            result = keeper.get("result")
            # 0x41301 / 267009 significa que la tarea sigue ejecutándose; no es
            # un fallo y puede observarse durante la consulta de cinco minutos.
            result_ok = result in (None, "", 0, "0", 267009, "267009")
            if _bool(keeper.get("enabled"), False) and age is not None and age <= (20 / 60) and result_ok:
                return _component(
                    "scheduler",
                    "Scheduler",
                    STATUS_OK,
                    "KeeperTick se ha ejecutado recientemente y sin error.",
                    details={
                        "evidence": "windows_task",
                        "age_minutes": round(age * 60, 1),
                        "last_result_ok": True,
                    },
                )
            return _component(
                "scheduler",
                "Scheduler",
                STATUS_DEGRADED,
                "KeeperTick está deshabilitado, atrasado o terminó con error.",
                action="Revisar la tarea Windows KeeperTick y su registro.",
                details={
                    "evidence": "windows_task",
                    "age_minutes": round(age * 60, 1) if age is not None else None,
                    "last_result_ok": result_ok,
                },
            )

    # Compatibilidad con el scheduler anterior. El orquestador único no actualiza
    # esta fila, por lo que solo se usa cuando Windows no está disponible.
    try:
        row = conn.execute(
            "SELECT checked_at, status, last_error FROM monitor_scheduler_heartbeat WHERE id = 1"
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        return _component(
            "scheduler",
            "Scheduler",
            STATUS_DEGRADED,
            "No hay heartbeat registrado del scheduler.",
            action="Comprobar la tarea Windows KeeperTick.",
            details={"heartbeat_present": False},
        )
    age = _age_hours(row["checked_at"], now)
    status = _text(row["status"]).lower()
    last_error = bool(_text(row["last_error"]))
    if age is None or age > (20 / 60) or status in {"failed", "error"} or last_error:
        return _component(
            "scheduler",
            "Scheduler",
            STATUS_DEGRADED,
            "El heartbeat está atrasado o registra un error.",
            action="Revisar KeeperTick y las últimas ejecuciones de automatización.",
            details={"heartbeat_present": True, "age_minutes": round((age or 0) * 60, 1), "reported_status": status},
        )
    return _component(
        "scheduler",
        "Scheduler",
        STATUS_OK,
        "Heartbeat reciente y sin error registrado.",
        details={"heartbeat_present": True, "age_minutes": round(age * 60, 1), "reported_status": status},
    )


def _backup_component(
    conn: sqlite3.Connection,
    environ: Mapping[str, str],
    now: datetime,
) -> dict[str, Any]:
    task_enabled = _task_enabled(conn, environ, "full_backup", "LLANGON_FULL_BACKUP_ENABLED", True)
    feature_enabled = _bool(environ.get("LLANGON_FULL_BACKUP_ENABLED"), False)
    if not task_enabled:
        return _component(
            "backups",
            "Backups",
            STATUS_OK,
            "Automatización desactivada de forma explícita.",
            details={"enabled": False},
        )

    runtime_root = Path(_text(environ.get("LLANGON_RUNTIME_ROOT")) or PROJECT_ROOT / "runtime")
    sqlite_root = Path(_text(environ.get("LLANGON_SQLITE_BACKUP_DIR")) or runtime_root / "backups" / "sqlite")
    full_root_text = _text(environ.get("LLANGON_FULL_BACKUP_ROOT"))
    full_root = Path(full_root_text) if full_root_text else None
    sqlite_latest = _latest_file(sqlite_root, "infonalia_*.db")
    full_latest = _latest_file(full_root, "*_LLANGON_SUITE_FULL_PRIVATE_BACKUP.zip", recursive=True) if full_root else None
    sqlite_age = _path_file_age(sqlite_latest, now)
    full_age = _path_file_age(full_latest, now)

    problems: list[str] = []
    if not feature_enabled:
        problems.append("la automatización está programada pero el backup completo está deshabilitado")
    if sqlite_age is None:
        problems.append("no se encontró una copia SQLite")
    elif sqlite_age > 36:
        problems.append("la copia SQLite tiene más de 36 horas")
    if full_age is None:
        problems.append("no se encontró un backup completo")
    elif full_age > 36:
        problems.append("el backup completo tiene más de 36 horas")

    details = {
        "enabled": True,
        "feature_enabled": feature_enabled,
        "sqlite_backup_present": sqlite_age is not None,
        "sqlite_backup_age_hours": round(sqlite_age, 1) if sqlite_age is not None else None,
        "full_backup_present": full_age is not None,
        "full_backup_age_hours": round(full_age, 1) if full_age is not None else None,
    }
    if problems:
        return _component(
            "backups",
            "Backups",
            STATUS_DEGRADED,
            "; ".join(problems).capitalize() + ".",
            action="Revisar la última ejecución de Backup completo.",
            critical=True,
            details=details,
        )
    return _component(
        "backups",
        "Backups",
        STATUS_OK,
        "Copia SQLite y backup completo recientes.",
        critical=True,
        details=details,
    )


def _queue_component(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    stale: dict[str, int] = {"downloads": 0, "ai": 0}
    recent_failed: dict[str, int] = {"downloads": 0, "ai": 0}
    cutoff = now - timedelta(hours=24)

    try:
        rows = conn.execute(
            "SELECT status, created_at, started_at, updated_at FROM download_jobs "
            "WHERE status IN ('pending', 'running', 'processing', 'failed') ORDER BY id DESC LIMIT 1000"
        ).fetchall()
        for row in rows:
            stamp = _parse_datetime(row["updated_at"] or row["started_at"] or row["created_at"])
            if _text(row["status"]).lower() == "failed":
                if stamp and stamp >= cutoff:
                    recent_failed["downloads"] += 1
            elif stamp and now - stamp > timedelta(hours=2):
                stale["downloads"] += 1
    except sqlite3.Error:
        stale["downloads"] = -1

    try:
        rows = conn.execute(
            "SELECT status, created_at, started_at, heartbeat_at, dismissed_at FROM ai_analysis_jobs "
            "WHERE status IN ('pending', 'queued', 'processing', 'deferred', 'error', 'failed') "
            "ORDER BY id DESC LIMIT 1000"
        ).fetchall()
        for row in rows:
            stamp = _parse_datetime(row["heartbeat_at"] or row["started_at"] or row["created_at"])
            status = _text(row["status"]).lower()
            if status in {"error", "failed"}:
                if not row["dismissed_at"] and stamp and stamp >= cutoff:
                    recent_failed["ai"] += 1
            else:
                threshold = timedelta(hours=24 if status == "deferred" else 2)
                if stamp and now - stamp > threshold:
                    stale["ai"] += 1
    except sqlite3.Error:
        stale["ai"] = -1

    total_attention = sum(value for value in (*stale.values(), *recent_failed.values()) if value > 0)
    if -1 in stale.values():
        return _component(
            "queues",
            "Colas de trabajo",
            STATUS_DEGRADED,
            "No se pudo consultar alguna cola de trabajo.",
            action="Revisar el esquema y las colas desde Administración.",
            details={"query_error": True},
        )
    if total_attention:
        return _component(
            "queues",
            "Colas de trabajo",
            STATUS_DEGRADED,
            f"Hay {total_attention} trabajo(s) atascado(s) o fallo(s) reciente(s).",
            action="Revisar las colas de descargas e IA.",
            details={"stale": stale, "failed_last_24h": recent_failed},
        )
    return _component(
        "queues",
        "Colas de trabajo",
        STATUS_OK,
        "Sin trabajos atascados ni fallos recientes sin descartar.",
        details={"stale": stale, "failed_last_24h": recent_failed},
    )


def _monitor_component(
    conn: sqlite3.Connection,
    environ: Mapping[str, str],
    now: datetime,
) -> dict[str, Any]:
    enabled = _task_enabled(conn, environ, "monitor_licitaciones", None, False)
    try:
        row = conn.execute(
            "SELECT status, created_at, heartbeat_at, finished_at, error_count, incident_count "
            "FROM tender_monitor_cycles ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        if enabled:
            return _component(
                "monitor",
                "Monitor de licitaciones",
                STATUS_DEGRADED,
                "Está activado, pero todavía no hay ciclos registrados.",
                action="Comprobar su próxima franja automática.",
                details={"enabled": True, "cycle_present": False},
            )
        return _component(
            "monitor",
            "Monitor de licitaciones",
            STATUS_OK,
            "Desactivado y sin incidencias operativas pendientes.",
            details={"enabled": False, "cycle_present": False},
        )

    status = _text(row["status"]).lower()
    age = _age_hours(row["heartbeat_at"] or row["finished_at"] or row["created_at"], now)
    errors = int(row["error_count"] or 0)
    incidents = int(row["incident_count"] or 0)
    recent = age is not None and age <= 24
    stale_running = status in {"running", "processing", "queued"} and (age is None or age > 2)
    failed_recent = recent and (status in {"failed", "error", "interrupted"} or errors or incidents)
    if stale_running or failed_recent:
        reason = "El último ciclo parece atascado." if stale_running else "El último ciclo terminó con incidencias."
        return _component(
            "monitor",
            "Monitor de licitaciones",
            STATUS_DEGRADED,
            reason,
            action="Abrir Monitor de licitaciones y revisar el último ciclo.",
            details={"enabled": enabled, "last_status": status, "age_hours": round(age, 1) if age is not None else None, "errors": errors, "incidents": incidents},
        )
    return _component(
        "monitor",
        "Monitor de licitaciones",
        STATUS_OK,
        "Sin incidencias recientes que requieran atención." if enabled else "Desactivado; no hay incidencias recientes.",
        details={"enabled": enabled, "last_status": status, "age_hours": round(age, 1) if age is not None else None},
    )


def _integration_components(
    conn: sqlite3.Connection,
    settings: Mapping[str, str],
    environ: Mapping[str, str],
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []

    actions_enabled = _bool(_setting(settings, environ, "email_actions_enabled", "LLANGON_EMAIL_ACTIONS_ENABLED", "0"))
    import_enabled = _bool(_setting(settings, environ, "infonalia_import_enabled", "LLANGON_INFONALIA_IMPORT_ENABLED", "0"))
    imap_enabled = actions_enabled or import_enabled
    imap_ready = all(
        (
            _setting(settings, environ, "actions_imap_host", "LLANGON_ACTIONS_IMAP_HOST", "imap.gmail.com"),
            _setting(settings, environ, "actions_imap_user", "LLANGON_ACTIONS_IMAP_USER"),
            _text(environ.get("LLANGON_ACTIONS_IMAP_PASSWORD")),
        )
    )
    components.append(
        _integration_component(
            "imap", "Correo entrante (IMAP)", imap_enabled, imap_ready,
            "Configuración disponible para los procesos activados.",
            "Faltan datos de configuración IMAP para un proceso activado.",
        )
    )

    smtp_enabled = _bool(_setting(settings, environ, "smtp_enabled", "INFONALIA_SMTP_ENABLED", "0"))
    smtp_ready = all(
        (
            _setting(settings, environ, "smtp_host", "INFONALIA_SMTP_HOST"),
            _setting(settings, environ, "smtp_user", "INFONALIA_SMTP_USER"),
            _text(settings.get("smtp_password")) or _text(environ.get("INFONALIA_SMTP_PASSWORD")),
            _setting(settings, environ, "smtp_from", "INFONALIA_SMTP_FROM"),
        )
    )
    components.append(
        _integration_component(
            "smtp", "Correo saliente (SMTP)", smtp_enabled, smtp_ready,
            "Configuración disponible; no se envió ningún correo de prueba.",
            "SMTP está activado, pero su configuración está incompleta.",
        )
    )

    provider = _setting(settings, environ, "ai_analysis_provider", "AI_ANALYSIS_PROVIDER", "disabled").lower()
    gemini_enabled = _bool(_setting(settings, environ, "gemini_enabled", "GEMINI_ENABLED", "0"))
    codex_enabled = _bool(environ.get("CODEX_LOCAL_ENABLED"), False)
    ai_enabled = provider not in {"", "disabled", "none"} or gemini_enabled or codex_enabled
    if provider == "gemini" or gemini_enabled:
        ai_ready = bool(_text(environ.get("GEMINI_API_KEY")))
    elif provider == "codex_local" or codex_enabled:
        ai_ready = True
    else:
        ai_ready = not ai_enabled
    components.append(
        _integration_component(
            "ai", "Análisis IA", ai_enabled, ai_ready,
            "Proveedor configurado; no se realizó ninguna petición externa.",
            "La IA está activada, pero falta su configuración necesaria.",
        )
    )

    telegram_enabled = _bool(environ.get("LLANGON_TELEGRAM_ENABLED"), False)
    telegram_destination = bool(_text(environ.get("LLANGON_TELEGRAM_GROUP_CHAT_ID")))
    if not telegram_destination:
        try:
            telegram_destination = bool(
                conn.execute(
                    "SELECT 1 FROM usuarios WHERE active = 1 AND telegram_notifications_enabled = 1 "
                    "AND COALESCE(telegram_chat_id, '') <> '' LIMIT 1"
                ).fetchone()
            )
        except sqlite3.Error:
            telegram_destination = False
    telegram_ready = bool(_text(environ.get("LLANGON_TELEGRAM_BOT_TOKEN"))) and telegram_destination
    components.append(
        _integration_component(
            "telegram", "Telegram", telegram_enabled, telegram_ready,
            "Configuración disponible; no se envió ningún mensaje de prueba.",
            "Telegram está activado, pero falta el bot o un destino.",
        )
    )
    return components


def _integration_component(
    key: str,
    label: str,
    enabled: bool,
    ready: bool,
    ready_summary: str,
    error_summary: str,
) -> dict[str, Any]:
    if not enabled:
        return _component(
            key,
            label,
            STATUS_OK,
            "Desactivado; no afecta al estado general.",
            details={"enabled": False, "check_mode": "configuration_only"},
        )
    if ready:
        return _component(
            key,
            label,
            STATUS_OK,
            ready_summary,
            details={"enabled": True, "configured": True, "check_mode": "configuration_only"},
        )
    return _component(
        key,
        label,
        STATUS_DEGRADED,
        error_summary,
        action=f"Completar la configuración de {label} o desactivar la función.",
        details={"enabled": True, "configured": False, "check_mode": "configuration_only"},
    )


def _windows_component(payload: Mapping[str, object] | None) -> dict[str, Any]:
    if payload is None:
        return _component(
            "windows_tasks",
            "Tareas Windows",
            STATUS_DEGRADED,
            "Comprobación no disponible en esta ejecución.",
            action="Ejecutar el diagnóstico desde la Suite en Windows.",
            details={"checked": False},
        )
    if payload.get("error"):
        return _component(
            "windows_tasks",
            "Tareas Windows",
            STATUS_DEGRADED,
            "Windows no permitió consultar las tareas programadas.",
            action="Revisar las tareas desde el Programador de tareas.",
            details={"checked": True, "query_error": True},
        )
    items = payload.get("items") or []
    by_name = {_text(item.get("name")): item for item in items if isinstance(item, Mapping)}
    missing = [name for name in WINDOWS_TASKS if name not in by_name]
    disabled = [name for name in WINDOWS_TASKS if name in by_name and not _bool(by_name[name].get("enabled"), False)]
    if missing or disabled:
        return _component(
            "windows_tasks",
            "Tareas Windows",
            STATUS_DEGRADED,
            "Falta una tarea esencial o está deshabilitada.",
            action="Restaurar KeeperTick y WakeTick con el instalador operativo.",
            details={"checked": True, "missing_count": len(missing), "disabled_count": len(disabled)},
        )
    return _component(
        "windows_tasks",
        "Tareas Windows",
        STATUS_OK,
        "KeeperTick y WakeTick están presentes y habilitadas.",
        details={"checked": True, "expected_count": len(WINDOWS_TASKS)},
    )


def _assert_no_sensitive_keys(value: object, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in SENSITIVE_TOKENS):
                raise ValueError(f"El diagnóstico contiene una clave sensible: {path}{key}")
            _assert_no_sensitive_keys(item, f"{path}{key}.")
    elif isinstance(value, list):
        for item in value:
            _assert_no_sensitive_keys(item, path)


def build_operational_health(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    environ: Mapping[str, str] | None = None,
    windows_tasks: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a non-destructive operational diagnosis for humans and machines."""

    env = os.environ if environ is None else environ
    current = now or datetime.now(DEFAULT_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=DEFAULT_TIMEZONE)
    else:
        current = current.astimezone(DEFAULT_TIMEZONE)

    components = [
        _component(
            "application",
            "Aplicación",
            STATUS_OK,
            "La aplicación está atendiendo la solicitud de diagnóstico.",
            critical=True,
        )
    ]
    conn, database_components, database_contract = _database_components(db_path)
    components.extend(database_components)
    components.append(_storage_component(env))
    if conn is not None:
        try:
            settings = _settings(conn)
            components.extend(
                (
                    _scheduler_component(conn, current, windows_tasks),
                    _backup_component(conn, env, current),
                    _queue_component(conn, current),
                    _monitor_component(conn, env, current),
                )
            )
            components.extend(_integration_components(conn, settings, env))
        finally:
            conn.close()
    else:
        for key, label in (
            ("scheduler", "Scheduler"),
            ("backups", "Backups"),
            ("queues", "Colas de trabajo"),
            ("monitor", "Monitor de licitaciones"),
            ("imap", "Correo entrante (IMAP)"),
            ("smtp", "Correo saliente (SMTP)"),
            ("ai", "Análisis IA"),
            ("telegram", "Telegram"),
        ):
            components.append(
                _component(
                    key,
                    label,
                    STATUS_DEGRADED,
                    "No se puede comprobar porque SQLite no está disponible.",
                    details={"checked": False},
                )
            )
    components.append(_windows_component(windows_tasks))

    overall = STATUS_OK
    if any(item["status"] == STATUS_ERROR and item["critical"] for item in components):
        overall = STATUS_ERROR
    elif any(item["status"] != STATUS_OK for item in components):
        overall = STATUS_DEGRADED

    attention = [item for item in components if item["status"] != STATUS_OK]
    counts = {
        status: sum(1 for item in components if item["status"] == status)
        for status in (STATUS_OK, STATUS_DEGRADED, STATUS_ERROR)
    }
    if overall == STATUS_OK:
        human_summary = "Suite operativa. No hay incidencias que requieran atención ahora."
    elif overall == STATUS_ERROR:
        human_summary = f"La Suite tiene {len(attention)} incidencia(s); al menos una impide garantizar su funcionamiento."
    else:
        human_summary = f"La Suite funciona de forma degradada y tiene {len(attention)} asunto(s) que revisar."

    payload = {
        "status": overall,
        "generated_at": current.replace(microsecond=0).isoformat(),
        "human_summary": human_summary,
        "summary": {"component_count": len(components), "attention_count": len(attention), "counts": counts},
        "needs_attention": attention,
        "components": components,
        "contract": {
            **system_contract_payload(),
            "database_validation": database_contract,
        },
        "check_policy": {
            "destructive": False,
            "external_connections": False,
            "integration_checks": "configuration_only",
        },
    }
    _assert_no_sensitive_keys(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditoría funcional no destructiva de Llangon Suite.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    load_env_file(APP_ROOT / ".env")
    payload = build_operational_health(db_path=args.db_path, windows_tasks=None)
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if payload["status"] != STATUS_ERROR else 2


if __name__ == "__main__":
    raise SystemExit(main())
