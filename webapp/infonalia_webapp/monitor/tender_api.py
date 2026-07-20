from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import parse_qs

try:
    from ..seguimiento_markers import (
        create_follow_marker_for_licitacion,
        remove_follow_marker_for_licitacion,
    )
except ImportError:  # pragma: no cover
    from seguimiento_markers import create_follow_marker_for_licitacion, remove_follow_marker_for_licitacion

from .config import MonitorConfigError, load_monitor_config
from .snapshots import normalize_text
from .tender_orchestrator import (
    TenderMonitorDependencies,
    retry_batch_ai,
    retry_notification,
    send_consolidated_incident_report,
)
from .tender_preparation import discover_followed, preparation_for_row
from .tender_repository import (
    active_cycle,
    create_cycle,
    get_cycle,
    json_load,
    list_cycles,
    now_iso,
    recover_orphan_cycles,
    record_incident,
    save_settings,
    settings_payload,
)
from .tender_schema import ensure_tender_monitor_schema
from .tender_worker_launcher import launch_tender_monitor_worker


@dataclass(frozen=True)
class APIResponse:
    payload: dict[str, object]
    status: HTTPStatus = HTTPStatus.OK


@dataclass
class TenderMonitorAPIContext:
    db_path: str | Path
    user: Mapping[str, object]
    root: str | Path | None
    email_sender: Callable[[str, str, str, str], tuple[str | None, str | None]] | None = None
    telegram_sender: Callable[[Mapping[str, object], str], object] | None = None
    worker_launcher: Callable[..., dict[str, object]] = launch_tender_monitor_worker
    now: Callable[[], datetime] = datetime.now

    @property
    def username(self) -> str:
        return normalize_text(self.user.get("username"))

    @property
    def role(self) -> str:
        return normalize_text(self.user.get("role")).casefold()

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _connect(context: TenderMonitorAPIContext) -> sqlite3.Connection:
    conn = sqlite3.connect(str(context.db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_tender_monitor_schema(conn)
    return conn


def _forbidden() -> APIResponse:
    return APIResponse({"error": "No tienes permiso para esta acción."}, HTTPStatus.FORBIDDEN)


def _not_found(message: str) -> APIResponse:
    return APIResponse({"error": message}, HTTPStatus.NOT_FOUND)


def _root_config(context: TenderMonitorAPIContext):
    return load_monitor_config(context.root)


def _followed_rows(conn: sqlite3.Connection, context: TenderMonitorAPIContext) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    config = _root_config(context)
    markers, scan = discover_followed(config.root_path, config.year_min, config.year_max)
    items: list[dict[str, object]] = []
    for marker in markers:
        row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (marker.licitacion_id,)).fetchone()
        if not row:
            continue
        prep = preparation_for_row(row, root=config.root_path, marker=marker)
        latest = conn.execute(
            """
            SELECT e.status, e.finished_at, e.ai_status, e.notification_status,
                   b.created_at AS last_change_at
            FROM tender_monitor_executions AS e
            LEFT JOIN tender_monitor_batches AS b ON b.id = e.batch_id
            WHERE e.licitacion_id = ? ORDER BY e.id DESC LIMIT 1
            """,
            (marker.licitacion_id,),
        ).fetchone()
        item = {
            "id": row["id"],
            "expediente": row["expediente"],
            "title": row["objeto"],
            "platform": prep.platform,
            "followed": prep.followed,
            "prepared": prep.prepared,
            "preparation_reason": prep.reason,
            "has_technical_state": prep.has_technical_state,
            "folder_path": str(prep.destination or ""),
            "last_review": latest["finished_at"] if latest else "",
            "last_result": latest["status"] if latest else "never",
            "last_change": latest["last_change_at"] if latest else "",
            "ai_status": latest["ai_status"] if latest else "not_required",
            "notification_status": latest["notification_status"] if latest else "not_required",
        }
        items.append(item)
    issues = [issue.to_dict() for issue in [*scan.conflicts, *scan.warnings]]
    return items, issues


def summary_payload(conn: sqlite3.Connection, context: TenderMonitorAPIContext) -> dict[str, object]:
    try:
        followed, discovery_issues = _followed_rows(conn, context)
        config_error = ""
    except (MonitorConfigError, OSError) as exc:
        followed, discovery_issues, config_error = [], [], str(exc)
    active = active_cycle(conn)
    last = conn.execute("SELECT * FROM tender_monitor_cycles ORDER BY id DESC LIMIT 1").fetchone()
    prepared = sum(1 for item in followed if item["prepared"])
    return {
        "automatic_enabled": False,
        "automatic_message": "Ejecución automática desactivada. El monitor solo se ejecuta manualmente.",
        "config_error": config_error,
        "active_cycle": dict(active) if active else None,
        "last_cycle": dict(last) if last else None,
        "counts": {
            "followed": len(followed),
            "prepared": prepared,
            "not_prepared": len(followed) - prepared,
            "discovery_issues": len(discovery_issues),
        },
    }


def tender_detail_payload(conn: sqlite3.Connection, licitacion_id: int, context: TenderMonitorAPIContext) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        return None
    config = _root_config(context)
    prep = preparation_for_row(row, root=config.root_path)
    executions = conn.execute(
        """
        SELECT id, cycle_id, status, preparation_status, preparation_reason,
               ai_status, notification_status, started_at, finished_at, batch_id
        FROM tender_monitor_executions
        WHERE licitacion_id = ? ORDER BY id DESC LIMIT 20
        """,
        (licitacion_id,),
    ).fetchall()
    return {
        "licitacion": {"id": row["id"], "expediente": row["expediente"], "title": row["objeto"]},
        "monitor": prep.to_dict(),
        "executions": [dict(item) for item in executions],
    }


def _redact_cycle_for_reviewer(payload: dict[str, object]) -> dict[str, object]:
    for incident in payload.get("incidents", []):
        if isinstance(incident, dict):
            incident.pop("technical_detail", None)
    for execution in payload.get("executions", []):
        if isinstance(execution, dict):
            execution.pop("log", None)
            execution.pop("error_message", None)
    return payload


def dispatch_get(path: str, query: str, context: TenderMonitorAPIContext) -> APIResponse | None:
    if not path.startswith("/api/tender-monitor"):
        return None
    conn = _connect(context)
    try:
        if path == "/api/tender-monitor/summary":
            return APIResponse(summary_payload(conn, context))
        if path == "/api/tender-monitor/followed":
            try:
                items, issues = _followed_rows(conn, context)
            except (MonitorConfigError, OSError) as exc:
                return APIResponse({"items": [], "issues": [], "error": str(exc)}, HTTPStatus.CONFLICT)
            return APIResponse({"items": items, "issues": issues})
        if path == "/api/tender-monitor/settings":
            if not context.is_admin:
                return _forbidden()
            return APIResponse(settings_payload(conn))
        if path == "/api/tender-monitor/cycles":
            params = parse_qs(query)
            try:
                limit = int(params.get("limit", ["50"])[0])
                tender_id = int(params.get("licitacion_id", ["0"])[0]) or None
            except ValueError:
                return APIResponse({"error": "Filtros no válidos."}, HTTPStatus.BAD_REQUEST)
            changes = params.get("with_changes", [""])[0]
            incidents = params.get("with_incidents", [""])[0]
            waiting = params.get("waiting_ai", [""])[0]
            notification_failed = params.get("notification_failed", [""])[0]
            items = list_cycles(
                conn,
                limit=limit,
                status=normalize_text(params.get("status", [""])[0]),
                licitacion_id=tender_id,
                platform=normalize_text(params.get("platform", [""])[0]),
                date_from=normalize_text(params.get("date_from", [""])[0]),
                date_to=normalize_text(params.get("date_to", [""])[0]),
                with_changes=None if changes == "" else changes == "1",
                with_incidents=None if incidents == "" else incidents == "1",
                waiting_ai=None if waiting == "" else waiting == "1",
                notification_failed=None if notification_failed == "" else notification_failed == "1",
            )
            return APIResponse({"items": items})
        if path.startswith("/api/tender-monitor/cycles/"):
            raw_id = path.removeprefix("/api/tender-monitor/cycles/").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de ciclo no válido."}, HTTPStatus.BAD_REQUEST)
            item = get_cycle(conn, int(raw_id))
            if not item:
                return _not_found("Ciclo no encontrado.")
            return APIResponse(item if context.is_admin else _redact_cycle_for_reviewer(item))
        if path.startswith("/api/tender-monitor/licitaciones/"):
            raw_id = path.removeprefix("/api/tender-monitor/licitaciones/").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de licitación no válido."}, HTTPStatus.BAD_REQUEST)
            try:
                item = tender_detail_payload(conn, int(raw_id), context)
            except (MonitorConfigError, OSError) as exc:
                return APIResponse({"error": str(exc)}, HTTPStatus.CONFLICT)
            return APIResponse(item) if item else _not_found("Licitación no encontrada.")
        return None
    finally:
        conn.close()


def _start_cycle(
    conn: sqlite3.Connection,
    context: TenderMonitorAPIContext,
    *,
    licitacion_id: int | None,
    force_baseline: bool = False,
) -> APIResponse:
    if licitacion_id is None and not context.is_admin:
        return _forbidden()
    if licitacion_id is not None and context.role not in {"admin", "nuria"}:
        return _forbidden()
    if force_baseline and not context.is_admin:
        return _forbidden()
    lease_row = conn.execute(
        "SELECT value FROM tender_monitor_settings WHERE key = 'lease_minutes'"
    ).fetchone()
    try:
        lease_minutes = max(5, min(int(lease_row["value"] if lease_row else 60), 1440))
    except (TypeError, ValueError):
        lease_minutes = 60
    recover_orphan_cycles(conn, timestamp=context.now(), minutes=lease_minutes)
    conn.commit()
    active = active_cycle(conn)
    if active:
        return APIResponse(
            {"error": "El monitor ya está ejecutando un ciclo.", "active_cycle_id": active["id"]},
            HTTPStatus.CONFLICT,
        )
    if licitacion_id is not None:
        row = conn.execute("SELECT id FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
        if not row:
            return _not_found("Licitación no encontrada.")
    cycle_id = create_cycle(
        conn,
        origin=("manual_baseline_rebuild" if force_baseline else ("manual_individual" if licitacion_id is not None else "manual_global")),
        requested_by=context.username,
        licitacion_id=licitacion_id,
        metadata={"force_baseline": True} if force_baseline else None,
    )
    conn.commit()
    worker = context.worker_launcher(cycle_id, db_path=context.db_path, root=context.root)
    if worker.get("ok") is False:
        timestamp = now_iso(context.now())
        conn.execute(
            "UPDATE tender_monitor_cycles SET status = 'failed', finished_at = ? WHERE id = ?",
            (timestamp, cycle_id),
        )
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=None,
            licitacion_id=licitacion_id,
            phase="launcher",
            code="WORKER_LAUNCH_FAILED",
            summary="No se pudo iniciar el worker del monitor.",
            technical_detail=normalize_text(worker.get("error")),
            outcome="retry_available",
            timestamp=timestamp,
        )
        conn.commit()
        return APIResponse(
            {"error": normalize_text(worker.get("error")) or "No se pudo iniciar el monitor.", "cycle_id": cycle_id},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    return APIResponse({"ok": True, "cycle_id": cycle_id, "status": "pending", "worker": worker}, HTTPStatus.ACCEPTED)


def _toggle_follow(
    conn: sqlite3.Connection,
    context: TenderMonitorAPIContext,
    licitacion_id: int,
    active: bool,
) -> APIResponse:
    if not context.is_admin:
        return _forbidden()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        return _not_found("Licitación no encontrada.")
    config = _root_config(context)
    result = (
        create_follow_marker_for_licitacion(
            row,
            allowed_roots=[config.root_path],
            dropbox_root=config.root_path,
        )
        if active
        else remove_follow_marker_for_licitacion(
            row,
            allowed_roots=[config.root_path],
            dropbox_root=config.root_path,
        )
    )
    status = HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT
    return APIResponse(result, status)


def _test_channel(
    conn: sqlite3.Connection,
    context: TenderMonitorAPIContext,
    *,
    channel: str,
    username: str,
) -> APIResponse:
    if not context.is_admin:
        return _forbidden()
    row = conn.execute("SELECT * FROM usuarios WHERE username = ? AND active = 1", (username,)).fetchone()
    if not row:
        return _not_found("Usuario no encontrado o inactivo.")
    if channel == "email":
        destination = normalize_text(row["email"])
        if not destination:
            return APIResponse({"error": "El usuario no tiene correo configurado."}, HTTPStatus.CONFLICT)
        sent_at, error = context.email_sender(
            destination,
            "[Llangon Monitor] Prueba de correo",
            "Prueba de configuración del Monitor de licitaciones. No representa una novedad.",
            "<p>Prueba de configuración del <strong>Monitor de licitaciones</strong>. No representa una novedad.</p>",
        ) if context.email_sender else (None, "Correo no configurado")
        return APIResponse({"ok": bool(sent_at and not error), "sent_at": sent_at or "", "error": error or ""}, HTTPStatus.OK if sent_at and not error else HTTPStatus.CONFLICT)
    destination = normalize_text(row["telegram_chat_id"])
    if not destination:
        return APIResponse({"error": "El usuario no tiene Telegram configurado."}, HTTPStatus.CONFLICT)
    result = context.telegram_sender(dict(row), "🔔 Prueba del Monitor de licitaciones. No representa una novedad.") if context.telegram_sender else {"ok": False, "error": "Telegram no configurado"}
    ok = bool(result.get("ok")) if isinstance(result, Mapping) else bool(getattr(result, "ok", False))
    error = normalize_text(result.get("error_message") or result.get("error")) if isinstance(result, Mapping) else normalize_text(getattr(result, "error_message", ""))
    return APIResponse({"ok": ok, "error": error}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)


def dispatch_post(
    path: str,
    payload: Mapping[str, object],
    context: TenderMonitorAPIContext,
) -> APIResponse | None:
    if not path.startswith("/api/tender-monitor"):
        return None
    conn = _connect(context)
    try:
        if path == "/api/tender-monitor/cycles":
            return _start_cycle(conn, context, licitacion_id=None)
        if path.startswith("/api/tender-monitor/licitaciones/") and path.endswith("/cycles"):
            raw_id = path.removeprefix("/api/tender-monitor/licitaciones/").removesuffix("/cycles").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de licitación no válido."}, HTTPStatus.BAD_REQUEST)
            return _start_cycle(conn, context, licitacion_id=int(raw_id))
        if path.startswith("/api/tender-monitor/licitaciones/") and path.endswith("/rebuild-baseline"):
            raw_id = path.removeprefix("/api/tender-monitor/licitaciones/").removesuffix("/rebuild-baseline").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de licitación no válido."}, HTTPStatus.BAD_REQUEST)
            return _start_cycle(conn, context, licitacion_id=int(raw_id), force_baseline=True)
        if path.startswith("/api/tender-monitor/licitaciones/") and path.endswith("/follow"):
            raw_id = path.removeprefix("/api/tender-monitor/licitaciones/").removesuffix("/follow").strip("/")
            if not raw_id.isdigit() or not isinstance(payload.get("active"), bool):
                return APIResponse({"error": "Solicitud de seguimiento no válida."}, HTTPStatus.BAD_REQUEST)
            try:
                return _toggle_follow(conn, context, int(raw_id), bool(payload["active"]))
            except (MonitorConfigError, OSError, ValueError) as exc:
                return APIResponse({"error": str(exc)}, HTTPStatus.CONFLICT)
        if path in {"/api/tender-monitor/test-email", "/api/tender-monitor/test-telegram"}:
            channel = "email" if path.endswith("test-email") else "telegram"
            return _test_channel(conn, context, channel=channel, username=normalize_text(payload.get("username")))
        if path.startswith("/api/tender-monitor/incident-reports/") and path.endswith("/retry"):
            if not context.is_admin:
                return _forbidden()
            raw_id = path.removeprefix("/api/tender-monitor/incident-reports/").removesuffix("/retry").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de ciclo no válido."}, HTTPStatus.BAD_REQUEST)
            deps = TenderMonitorDependencies(email_sender=context.email_sender, now=context.now)
            status = send_consolidated_incident_report(conn, deps=deps, cycle_id=int(raw_id))
            conn.commit()
            return APIResponse({"ok": status == "sent", "status": status}, HTTPStatus.OK if status == "sent" else HTTPStatus.CONFLICT)
        if path.startswith("/api/tender-monitor/notifications/") and path.endswith("/retry"):
            if not context.is_admin:
                return _forbidden()
            raw_id = path.removeprefix("/api/tender-monitor/notifications/").removesuffix("/retry").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de notificación no válido."}, HTTPStatus.BAD_REQUEST)
            deps = TenderMonitorDependencies(
                email_sender=context.email_sender,
                telegram_sender=context.telegram_sender,
                now=context.now,
            )
            result = retry_notification(conn, int(raw_id), deps=deps)
            conn.commit()
            if not result.get("ok") and result.get("error") == "Notificación no encontrada.":
                return _not_found(str(result["error"]))
            return APIResponse(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT)
        if path.startswith("/api/tender-monitor/batches/") and path.endswith("/retry-ai"):
            if not context.is_admin:
                return _forbidden()
            raw_id = path.removeprefix("/api/tender-monitor/batches/").removesuffix("/retry-ai").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de lote no válido."}, HTTPStatus.BAD_REQUEST)
            deps = TenderMonitorDependencies(now=context.now)
            result = retry_batch_ai(conn, int(raw_id), deps=deps)
            conn.commit()
            if not result.get("ok") and result.get("error") == "Lote no encontrado.":
                return _not_found(str(result["error"]))
            return APIResponse(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT)
        if path.startswith("/api/tender-monitor/executions/") and path.endswith("/retry"):
            if not context.is_admin:
                return _forbidden()
            raw_id = path.removeprefix("/api/tender-monitor/executions/").removesuffix("/retry").strip("/")
            if not raw_id.isdigit():
                return APIResponse({"error": "Id de ejecución no válido."}, HTTPStatus.BAD_REQUEST)
            execution = conn.execute("SELECT licitacion_id FROM tender_monitor_executions WHERE id = ?", (int(raw_id),)).fetchone()
            if not execution:
                return _not_found("Ejecución no encontrada.")
            return _start_cycle(conn, context, licitacion_id=int(execution["licitacion_id"]))
        return None
    finally:
        conn.close()


def dispatch_patch(
    path: str,
    payload: Mapping[str, object],
    context: TenderMonitorAPIContext,
) -> APIResponse | None:
    if path != "/api/tender-monitor/settings":
        return None
    if not context.is_admin:
        return _forbidden()
    values = payload.get("values") if isinstance(payload.get("values"), Mapping) else {}
    users = payload.get("users") if isinstance(payload.get("users"), list) else []
    if values.get("automatic_enabled") in {True, 1, "1", "true"}:
        return APIResponse({"error": "La ejecución automática no puede activarse en esta fase."}, HTTPStatus.CONFLICT)
    for key, minimum, maximum in (
        ("ai_timeout_seconds", 5, 86400),
        ("download_retries", 1, 5),
        ("notification_retries", 1, 5),
        ("lease_minutes", 5, 1440),
    ):
        if key not in values:
            continue
        try:
            number = int(values[key])
        except (TypeError, ValueError):
            return APIResponse({"error": f"{key} debe ser numérico."}, HTTPStatus.BAD_REQUEST)
        if number < minimum or number > maximum:
            return APIResponse({"error": f"{key} queda fuera del rango permitido."}, HTTPStatus.BAD_REQUEST)
    conn = _connect(context)
    try:
        item = save_settings(
            conn,
            values=values,
            users=[item for item in users if isinstance(item, Mapping)],
            updated_by=context.username,
            timestamp=now_iso(context.now()),
        )
        conn.commit()
        return APIResponse(item)
    finally:
        conn.close()
