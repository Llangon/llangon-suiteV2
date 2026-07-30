from __future__ import annotations

import json
import os
import socket
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Sequence

from herramientas_python.descargadores import run_downloader
from herramientas_python.descargadores.common.run_result import DownloadRunResult
from herramientas_python.descargadores.common.destination_lock import (
    DestinationBusyError,
    destination_lock,
)

try:
    from ..ai.service import request_ai_analysis
    from ..ai.worker_launcher import start_ai_worker_for_job
    from ..services.telegram_notifications import send_telegram_user_message
except ImportError:  # pragma: no cover
    from ai.service import request_ai_analysis
    from ai.worker_launcher import start_ai_worker_for_job
    from services.telegram_notifications import send_telegram_user_message

from .comparison import compare_snapshots, difference_fingerprint, merge_valid_blocks
from .config import load_monitor_config
from .snapshots import (
    normalize_text,
    read_technical_sidecar,
    snapshot_completeness,
    snapshot_from_result,
    write_monitor_sidecar_cache,
)
from .tender_messages import (
    build_incident_report,
    build_notification_content,
    differences_summary,
)
from .tender_email_assets import (
    DEFAULT_EMAIL_ATTACHMENT_LIMIT_BYTES,
    notification_files_and_differences,
    select_email_attachments,
)
from .tender_preparation import TenderPreparation, discover_followed, preparation_for_row
from .tender_repository import (
    acquire_lease,
    create_batch,
    create_execution,
    cycle_row,
    finish_cycle,
    finish_execution,
    heartbeat_cycle,
    incident_admin_recipient,
    increment_cycle,
    json_dump,
    json_load,
    load_monitor_baseline,
    notification_recipients,
    now_iso,
    record_incident,
    refresh_lease,
    release_lease,
    save_snapshot,
    set_monitor_baseline,
    start_cycle,
)
from .tender_rules import mark_ai_candidates, selected_document_paths
from .tender_schema import ensure_tender_monitor_schema


EmailSender = Callable[..., tuple[str | None, str | None]]
TelegramSender = Callable[[Mapping[str, object], str], object]
Downloader = Callable[..., DownloadRunResult]
AIRequester = Callable[[sqlite3.Connection, int, list[str], str], dict[str, object]]
AIStarter = Callable[[sqlite3.Connection, int], dict[str, object]]


@dataclass
class TenderMonitorDependencies:
    downloader: Downloader = run_downloader
    email_sender: EmailSender | None = None
    telegram_sender: TelegramSender | None = None
    ai_requester: AIRequester | None = None
    ai_starter: AIStarter | None = None
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], datetime] = datetime.now
    suite_base_url: str = ""
    email_attachment_limit_bytes: int = DEFAULT_EMAIL_ATTACHMENT_LIMIT_BYTES
    env: Mapping[str, object] | None = None
    logger: Callable[[str], None] = print


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    ensure_tender_monitor_schema(conn)
    return conn


def _setting(conn: sqlite3.Connection, key: str, default: str) -> str:
    row = conn.execute("SELECT value FROM tender_monitor_settings WHERE key = ?", (key,)).fetchone()
    return normalize_text(row["value"] if row else default) or default


def _setting_bool(conn: sqlite3.Connection, key: str, default: bool = False) -> bool:
    return _setting(conn, key, "1" if default else "0").casefold() in {"1", "true", "yes", "si", "sí", "on"}


def _setting_int(conn: sqlite3.Connection, key: str, default: int, *, minimum: int = 1, maximum: int = 86400) -> int:
    try:
        return max(minimum, min(int(_setting(conn, key, str(default))), maximum))
    except ValueError:
        return default


def _owner(cycle_id: int) -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{cycle_id}:{uuid.uuid4().hex[:8]}"


def _row_dict(row: sqlite3.Row | Mapping[str, object]) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}  # type: ignore[attr-defined]


def _transient_error(exc: BaseException) -> bool:
    text = str(exc).casefold()
    return isinstance(exc, (TimeoutError, ConnectionError)) or any(
        token in text for token in ("timeout", "timed out", "temporal", "temporarily", "connection", "503", "429", "bloqueo")
    )


def _transient_failed_result(result: DownloadRunResult) -> bool:
    if normalize_text(result.status).casefold() != "failed":
        return False
    if result.retryable:
        return True
    message = normalize_text(result.error) or "; ".join(
        normalize_text(item) for item in result.recoverable_issues if normalize_text(item)
    )
    return bool(message) and _transient_error(RuntimeError(message))


def _run_downloader(
    deps: TenderMonitorDependencies,
    prep: TenderPreparation,
    *,
    db_path: str | Path,
    attempts: int,
) -> tuple[DownloadRunResult, int]:
    last_error: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        deps.logger(f"Descargador {prep.platform}: intento {attempt}/{max(1, attempts)}.")
        try:
            options = {"db_path": db_path} if prep.platform == "PLACE" else {}
            result = deps.downloader(prep.platform, prep.source_url, prep.destination, **options)
            if attempt < attempts and _transient_failed_result(result):
                message = normalize_text(result.error) or "; ".join(result.recoverable_issues)
                deps.logger(
                    f"Descargador {prep.platform}: fallo transitorio en intento {attempt}; "
                    f"se abrirá una ejecución nueva ({message})."
                )
                deps.sleep(min(2**attempt, 5))
                continue
            return result, attempt
        except BaseException as exc:
            last_error = exc
            if attempt >= attempts or not _transient_error(exc):
                raise
            deps.logger(
                f"Descargador {prep.platform}: excepción transitoria en intento {attempt}; "
                f"se reintentará ({type(exc).__name__}: {exc})."
            )
            deps.sleep(min(2**attempt, 5))
    raise RuntimeError(str(last_error or "Error desconocido del descargador"))


def _choose_previous_snapshot(
    conn: sqlite3.Connection,
    *,
    prep: TenderPreparation,
    cycle_id: int,
    execution_id: int,
    timestamp: str,
) -> tuple[int | None, dict[str, object] | None]:
    baseline_id, baseline = load_monitor_baseline(conn, prep.licitacion_id)
    sidecar = read_technical_sidecar(prep.destination) if prep.destination else None
    if not sidecar:
        return baseline_id, baseline
    sidecar_fingerprint = normalize_text(sidecar.get("fingerprint"))
    baseline_fingerprint = normalize_text(baseline.get("fingerprint")) if baseline else ""
    sidecar_snapshot_id = sidecar.get("snapshot_id")
    try:
        sidecar_snapshot_id_value = int(sidecar_snapshot_id)
    except (TypeError, ValueError):
        sidecar_snapshot_id_value = None
    is_current_cache = bool(
        baseline_id
        and sidecar.get("writer") == "monitor"
        and sidecar_fingerprint == baseline_fingerprint
        and sidecar_snapshot_id_value == int(baseline_id)
    )
    legacy_matches_baseline = bool(
        baseline_id
        and sidecar.get("legacy")
        and sidecar_fingerprint
        and sidecar_fingerprint == baseline_fingerprint
    )
    # Without an authoritative SQLite baseline there is nothing that a cache
    # can diverge from. The first complete remote review will create the
    # baseline and replace any orphaned/legacy sidecar silently.
    if baseline_id and not is_current_cache and not legacy_matches_baseline:
        code = "LEGACY_SIDECAR_IGNORED" if sidecar.get("legacy") else "SIDECAR_DIVERGENT"
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            licitacion_id=prep.licitacion_id,
            phase="baseline",
            code=code,
            summary="El estado técnico de carpeta no se usó como baseline; SQLite conserva la autoridad.",
            technical_detail=json_dump(
                {
                    "baseline_snapshot_id": baseline_id,
                    "baseline_fingerprint": baseline_fingerprint,
                    "sidecar_snapshot_id": sidecar_snapshot_id,
                    "sidecar_fingerprint": sidecar_fingerprint,
                    "sidecar_writer": sidecar.get("writer"),
                }
            ),
            outcome="cache_repair_pending",
            timestamp=timestamp,
        )
    return baseline_id, baseline


def _write_sidecar_after_commit(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    execution_id: int,
    prep: TenderPreparation,
    snapshot_id: int,
    snapshot: Mapping[str, object],
    timestamp: str,
) -> None:
    try:
        write_monitor_sidecar_cache(
            prep.destination,
            snapshot,
            licitacion_id=prep.licitacion_id,
            snapshot_id=snapshot_id,
            execution_id=execution_id,
        )
    except (OSError, ValueError, TypeError) as exc:
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            licitacion_id=prep.licitacion_id,
            phase="sidecar",
            code="SIDECAR_WRITE_FAILED",
            summary="El baseline quedó confirmado en SQLite, pero falló su copia técnica de carpeta.",
            technical_detail=str(exc),
            outcome="cache_repair_pending",
            timestamp=timestamp,
        )
        conn.commit()


def _record_partial_incident(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    execution_id: int,
    prep: TenderPreparation,
    result: DownloadRunResult,
    attempt_count: int,
    timestamp: str,
) -> None:
    details = "; ".join([*result.warnings, *result.recoverable_issues, result.error]).strip("; ")
    record_incident(
        conn,
        cycle_id=cycle_id,
        execution_id=execution_id,
        licitacion_id=prep.licitacion_id,
        phase="download",
        code="PARTIAL_PLATFORM_RESPONSE",
        summary="La plataforma devolvió un resultado parcial; no se interpretaron ausencias como retiradas.",
        technical_detail=details,
        retry_count=max(0, attempt_count - 1),
        outcome="partial_state_preserved",
        timestamp=timestamp,
    )


def _result_is_usable(result: DownloadRunResult) -> bool:
    return result.status in {"success", "success_with_warnings", "partial"}


def _observation_log(
    result: DownloadRunResult,
    snapshot: Mapping[str, object],
    *,
    previous_snapshot_id: int | None,
    current_snapshot_id: int | None = None,
    differences: list[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    statuses: dict[str, int] = {}
    for artifact in result.artifacts:
        key = normalize_text(artifact.status).casefold() or "unknown"
        statuses[key] = statuses.get(key, 0) + 1
    return [
        {
            "event": "remote_inventory",
            "result_status": result.status,
            "previous_snapshot_id": previous_snapshot_id,
            "current_snapshot_id": current_snapshot_id,
            "documents_observed": len(result.artifacts),
            "artifact_status_counts": statuses,
            "block_completeness": snapshot_completeness(snapshot),
            "difference_count": len(differences or []),
        }
    ]


def _batch_differences(conn: sqlite3.Connection, batch_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM tender_monitor_differences WHERE batch_id = ? ORDER BY id", (batch_id,)
    ).fetchall()
    return [
        {
            **dict(row),
            "block": row["block_name"],
            "old_value": json_load(row["old_value_json"], None),
            "new_value": json_load(row["new_value_json"], None),
            "ai_candidate": bool(row["ai_candidate"]),
        }
        for row in rows
    ]


def _send_email(
    sender: EmailSender | None,
    destination: str,
    content: Mapping[str, str],
    attachments: Sequence[Path],
) -> tuple[str | None, str | None]:
    if not sender:
        return None, "Correo no configurado"
    try:
        return sender(destination, content["subject"], content["text"], content["html"], attachments)
    except TypeError:
        # Compatibility with injected four-argument senders used by older jobs/tests.
        return sender(destination, content["subject"], content["text"], content["html"])


def _ai_request_default(conn: sqlite3.Connection, licitacion_id: int, paths: list[str], requested_by: str) -> dict[str, object]:
    return request_ai_analysis(
        conn,
        licitacion_id,
        requested_by=requested_by,
        selected_files=paths,
        notify_on_completion=False,
    )


def _ai_summary_for_job(conn: sqlite3.Connection, job_id: int) -> str:
    row = conn.execute(
        """
        SELECT summary_text, summary_json FROM ai_summaries
        WHERE created_from_job_id = ? ORDER BY id DESC LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    if not row:
        return ""
    return normalize_text(row["summary_text"]) or normalize_text(row["summary_json"])


def _process_ai(
    conn: sqlite3.Connection,
    *,
    deps: TenderMonitorDependencies,
    cycle: sqlite3.Row,
    execution_id: int,
    batch_id: int,
    licitacion_id: int,
    differences: list[dict[str, object]],
    timestamp: str,
) -> tuple[str, str, bool]:
    candidates = [item for item in differences if item.get("ai_candidate")]
    if not candidates or not _setting_bool(conn, "ai_enabled", False):
        conn.execute(
            "UPDATE tender_monitor_batches SET ai_decision = 'not_required', ai_status = 'not_required' WHERE id = ?",
            (batch_id,),
        )
        return "not_required", "", False
    paths = selected_document_paths(candidates)
    if not paths:
        record_incident(
            conn,
            cycle_id=int(cycle["id"]),
            execution_id=execution_id,
            licitacion_id=licitacion_id,
            phase="ai",
            code="AI_DOCUMENT_PATH_MISSING",
            summary="La novedad era candidata a IA, pero no se encontró una ruta técnica segura del documento.",
            outcome="notified_without_ai",
            timestamp=timestamp,
        )
        conn.execute(
            "UPDATE tender_monitor_batches SET ai_decision = 'required', ai_status = 'failed' WHERE id = ?",
            (batch_id,),
        )
        return "failed", "", True
    requester = deps.ai_requester or _ai_request_default
    payload = requester(conn, licitacion_id, paths, normalize_text(cycle["requested_by"]))
    raw_job_id = payload.get("job_id") or (payload.get("job") or {}).get("id") if isinstance(payload.get("job"), Mapping) else payload.get("job_id")
    job_id = int(raw_job_id or 0)
    fingerprint = normalize_text(payload.get("document_hash")) or str(hash(tuple(paths)))
    if not job_id:
        reason = normalize_text(payload.get("motivo_si_no_puede_generar") or payload.get("message")) or "La cola IA no aceptó el trabajo."
        conn.execute(
            """
            INSERT OR IGNORE INTO tender_monitor_ai_links (
                batch_id, document_fingerprint, selected_paths_json, status,
                started_at, finished_at, error_message
            ) VALUES (?, ?, ?, 'failed', ?, ?, ?)
            """,
            (batch_id, fingerprint, json_dump(paths), timestamp, timestamp, reason),
        )
        record_incident(
            conn,
            cycle_id=int(cycle["id"]),
            execution_id=execution_id,
            licitacion_id=licitacion_id,
            phase="ai",
            code="AI_QUEUE_REJECTED",
            summary="La cola IA no pudo preparar el análisis; se notificará sin IA.",
            technical_detail=reason,
            outcome="notified_without_ai",
            timestamp=timestamp,
        )
        conn.execute(
            "UPDATE tender_monitor_batches SET ai_decision = 'required', ai_status = 'failed' WHERE id = ?",
            (batch_id,),
        )
        return "failed", "", True

    conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_ai_links (
            batch_id, ai_job_id, document_fingerprint, selected_paths_json,
            status, started_at
        ) VALUES (?, ?, ?, ?, 'waiting', ?)
        """,
        (batch_id, job_id, fingerprint, json_dump(paths), timestamp),
    )
    conn.execute(
        "UPDATE tender_monitor_batches SET ai_decision = 'required', ai_status = 'waiting' WHERE id = ?",
        (batch_id,),
    )
    conn.execute(
        "UPDATE tender_monitor_executions SET status = 'waiting_ai', ai_status = 'waiting' WHERE id = ?",
        (execution_id,),
    )
    increment_cycle(conn, int(cycle["id"]), waiting_ai_count=1)
    conn.commit()

    job = conn.execute("SELECT status FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if job and normalize_text(job["status"]) not in {"completed", "error", "cancelled", "disabled"}:
        starter = deps.ai_starter or start_ai_worker_for_job
        start_result = starter(conn, job_id)
        if start_result.get("ok") is False:
            conn.commit()
    timeout_seconds = _setting_int(conn, "ai_timeout_seconds", 900, minimum=5, maximum=86400)
    deadline = time.monotonic() + timeout_seconds
    status = ""
    while time.monotonic() < deadline:
        row = conn.execute("SELECT status, error_message FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
        status = normalize_text(row["status"] if row else "error")
        if status in {"completed", "error", "cancelled", "disabled"}:
            break
        deps.sleep(1.0)
    if status == "completed":
        summary = _ai_summary_for_job(conn, job_id)
        conn.execute(
            "UPDATE tender_monitor_ai_links SET status = 'completed', finished_at = ? WHERE batch_id = ? AND ai_job_id = ?",
            (now_iso(deps.now()), batch_id, job_id),
        )
        conn.execute("UPDATE tender_monitor_batches SET ai_status = 'completed' WHERE id = ?", (batch_id,))
        return "completed", summary, False

    timed_out = status not in {"error", "cancelled", "disabled"}
    error_message = "La IA superó el tiempo máximo del monitor." if timed_out else normalize_text(
        (conn.execute("SELECT error_message FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone() or {"error_message": ""})["error_message"]
    )
    if timed_out:
        conn.execute(
            """
            UPDATE ai_analysis_jobs SET cancel_requested = 1, status = 'error',
                error_code = 'MONITOR_AI_TIMEOUT', error_message = ?, finished_at = ?
            WHERE id = ? AND status IN ('pending', 'queued', 'processing', 'deferred')
            """,
            (error_message, now_iso(deps.now()), job_id),
        )
    conn.execute(
        """
        UPDATE tender_monitor_ai_links SET status = ?, finished_at = ?, error_message = ?
        WHERE batch_id = ? AND ai_job_id = ?
        """,
        ("timeout" if timed_out else "failed", now_iso(deps.now()), error_message, batch_id, job_id),
    )
    conn.execute("UPDATE tender_monitor_batches SET ai_status = 'failed' WHERE id = ?", (batch_id,))
    record_incident(
        conn,
        cycle_id=int(cycle["id"]),
        execution_id=execution_id,
        licitacion_id=licitacion_id,
        phase="ai",
        code="AI_TIMEOUT" if timed_out else "AI_FAILED",
        summary="La IA no terminó correctamente; las novedades se enviarán sin análisis.",
        technical_detail=error_message,
        outcome="notified_without_ai",
        timestamp=now_iso(deps.now()),
    )
    return "failed", "", True


def _telegram_result(result: object) -> tuple[bool, str, str]:
    if isinstance(result, Mapping):
        return bool(result.get("ok")), normalize_text(result.get("error_message") or result.get("error")), normalize_text(result.get("telegram_message_id") or result.get("message_id"))
    return bool(getattr(result, "ok", False)), normalize_text(getattr(result, "error_message", "")), normalize_text(getattr(result, "telegram_message_id", ""))


def send_batch_notifications(
    conn: sqlite3.Connection,
    *,
    deps: TenderMonitorDependencies,
    cycle_id: int,
    execution_id: int,
    batch_id: int,
    licitacion: Mapping[str, object],
    platform: str,
    checked_at: str,
    ai_summary: str,
    ai_failed: bool,
) -> str:
    differences = _batch_differences(conn, batch_id)
    attachments, differences = notification_files_and_differences(
        licitacion.get("ruta_carpeta"), differences
    )
    attachments, omitted_attachments = select_email_attachments(
        attachments, limit_bytes=deps.email_attachment_limit_bytes
    )
    suite_url = ""
    if deps.suite_base_url:
        suite_url = deps.suite_base_url.rstrip("/") + f"/app/licitaciones/{licitacion.get('id')}"
    content = build_notification_content(
        licitacion,
        platform=platform,
        checked_at=checked_at,
        differences=differences,
        ai_summary=ai_summary,
        ai_failed=ai_failed,
        suite_url=suite_url,
        attachment_names=[path.name for path in attachments],
        omitted_attachments=omitted_attachments,
    )
    recipients = notification_recipients(conn)
    email_rows = [row for row in recipients if bool(row["email_enabled"]) and normalize_text(row["email"])]
    telegram_rows = [row for row in recipients if bool(row["telegram_enabled"]) and normalize_text(row["telegram_chat_id"])]
    if not email_rows and not telegram_rows:
        conn.execute("UPDATE tender_monitor_batches SET notification_status = 'no_recipients' WHERE id = ?", (batch_id,))
        finish_execution(
            conn,
            execution_id,
            status="no_recipients",
            timestamp=checked_at,
            notification_status="no_recipients",
        )
        return "no_recipients"

    successes = 0
    failures = 0
    notification_attempts = _setting_int(conn, "notification_retries", 2, minimum=1, maximum=5)
    if email_rows:
        destinations = sorted({normalize_text(row["email"]) for row in email_rows})
        destination = ",".join(destinations)
        key = f"batch:{batch_id}:email:{destination.casefold()}"
        exists = conn.execute(
            "SELECT status FROM tender_monitor_notifications WHERE idempotency_key = ?", (key,)
        ).fetchone()
        if exists and exists["status"] == "sent":
            successes += 1
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO tender_monitor_notifications (
                    batch_id, channel, username, destination, status,
                    idempotency_key, created_at
                ) VALUES (?, 'email', ?, ?, 'pending', ?, ?)
                """,
                (batch_id, ",".join(row["username"] for row in email_rows), destination, key, checked_at),
            )
            sent_at = None
            error = "Correo no configurado"
            attempts_used = 0
            for attempt in range(1, notification_attempts + 1):
                attempts_used = attempt
                sent_at, error = _send_email(deps.email_sender, destination, content, attachments)
                if sent_at and not error:
                    break
                if attempt < notification_attempts:
                    deps.sleep(min(2**attempt, 5))
            if sent_at and not error:
                successes += 1
                conn.execute(
                    """
                    UPDATE tender_monitor_notifications SET status = 'sent', attempt_count = attempt_count + ?,
                        attempted_at = ?, sent_at = ?, error_message = NULL WHERE idempotency_key = ?
                    """,
                    (attempts_used, checked_at, sent_at, key),
                )
            else:
                failures += 1
                conn.execute(
                    """
                    UPDATE tender_monitor_notifications SET status = 'failed', attempt_count = attempt_count + ?,
                        attempted_at = ?, error_message = ? WHERE idempotency_key = ?
                    """,
                    (attempts_used, checked_at, normalize_text(error), key),
                )
                record_incident(
                    conn,
                    cycle_id=cycle_id,
                    execution_id=execution_id,
                    licitacion_id=int(licitacion["id"]),
                    phase="notification_email",
                    code="EMAIL_FAILED",
                    summary="Falló el correo de novedades; Telegram se procesó de forma independiente.",
                    technical_detail=normalize_text(error),
                    retry_count=max(0, attempts_used - 1),
                    outcome="retry_available",
                    timestamp=checked_at,
                )

    telegram_sender = deps.telegram_sender or (
        lambda user, message: send_telegram_user_message(user, message, env=deps.env or os.environ)
    )
    for row in telegram_rows:
        key = f"batch:{batch_id}:telegram:{row['username']}:{row['telegram_chat_id']}"
        exists = conn.execute(
            "SELECT status FROM tender_monitor_notifications WHERE idempotency_key = ?", (key,)
        ).fetchone()
        if exists and exists["status"] == "sent":
            successes += 1
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO tender_monitor_notifications (
                batch_id, channel, username, destination, status,
                idempotency_key, created_at
            ) VALUES (?, 'telegram', ?, ?, 'pending', ?, ?)
            """,
            (batch_id, row["username"], row["telegram_chat_id"], key, checked_at),
        )
        ok = False
        error = ""
        external_id = ""
        attempts_used = 0
        for attempt in range(1, notification_attempts + 1):
            attempts_used = attempt
            result = telegram_sender(_row_dict(row), content["telegram"])
            ok, error, external_id = _telegram_result(result)
            if ok:
                break
            if attempt < notification_attempts:
                deps.sleep(min(2**attempt, 5))
        if ok:
            successes += 1
            conn.execute(
                """
                UPDATE tender_monitor_notifications SET status = 'sent', attempt_count = attempt_count + ?,
                    attempted_at = ?, sent_at = ?, external_id = ?, error_message = NULL
                WHERE idempotency_key = ?
                """,
                (attempts_used, checked_at, checked_at, external_id, key),
            )
        else:
            failures += 1
            conn.execute(
                """
                UPDATE tender_monitor_notifications SET status = 'failed', attempt_count = attempt_count + ?,
                    attempted_at = ?, error_message = ? WHERE idempotency_key = ?
                """,
                (attempts_used, checked_at, error, key),
            )
            record_incident(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                licitacion_id=int(licitacion["id"]),
                phase="notification_telegram",
                code="TELEGRAM_FAILED",
                summary="Falló Telegram; el correo se procesó de forma independiente.",
                technical_detail=error,
                retry_count=max(0, attempts_used - 1),
                outcome="retry_available",
                timestamp=checked_at,
            )

    status = "notified" if successes and not failures else ("partial" if successes else "notification_failed")
    conn.execute(
        "UPDATE tender_monitor_batches SET notification_status = ?, notified_at = ? WHERE id = ?",
        (status, checked_at if successes else None, batch_id),
    )
    finish_execution(
        conn,
        execution_id,
        status=status,
        timestamp=checked_at,
        notification_status=status,
    )
    return status


def _retry_context(
    conn: sqlite3.Connection,
    batch_id: int,
) -> tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row, sqlite3.Row] | None:
    batch = conn.execute(
        "SELECT * FROM tender_monitor_batches WHERE id = ?", (batch_id,)
    ).fetchone()
    if not batch:
        return None
    execution = conn.execute(
        "SELECT * FROM tender_monitor_executions WHERE id = ?", (batch["execution_id"],)
    ).fetchone()
    cycle = cycle_row(conn, int(batch["cycle_id"]))
    licitacion = conn.execute(
        "SELECT * FROM licitaciones WHERE id = ?", (batch["licitacion_id"],)
    ).fetchone()
    if not execution or not cycle or not licitacion:
        return None
    return batch, execution, cycle, licitacion


def _refresh_notification_outcome(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    execution_id: int,
    timestamp: str,
) -> str:
    rows = conn.execute(
        "SELECT status FROM tender_monitor_notifications WHERE batch_id = ?", (batch_id,)
    ).fetchall()
    statuses = [normalize_text(row["status"]) for row in rows]
    if not statuses:
        status = "no_recipients"
    elif all(value == "sent" for value in statuses):
        status = "notified"
    elif any(value == "sent" for value in statuses):
        status = "partial"
    else:
        status = "notification_failed"
    conn.execute(
        "UPDATE tender_monitor_batches SET notification_status = ?, notified_at = CASE WHEN ? IN ('notified', 'partial') THEN ? ELSE notified_at END WHERE id = ?",
        (status, status, timestamp, batch_id),
    )
    finish_execution(
        conn,
        execution_id,
        status=status,
        timestamp=timestamp,
        notification_status=status,
    )
    return status


def retry_notification(
    conn: sqlite3.Connection,
    notification_id: int,
    *,
    deps: TenderMonitorDependencies,
) -> dict[str, object]:
    """Reintenta un único canal ya persistido sin repetir descarga ni IA."""
    notification = conn.execute(
        "SELECT * FROM tender_monitor_notifications WHERE id = ?", (notification_id,)
    ).fetchone()
    if not notification:
        return {"ok": False, "error": "Notificación no encontrada."}
    if normalize_text(notification["status"]) == "sent":
        return {"ok": True, "status": "sent", "already_sent": True}
    context = _retry_context(conn, int(notification["batch_id"]))
    if not context:
        return {"ok": False, "error": "El lote de la notificación ya no está disponible."}
    batch, execution, cycle, licitacion = context
    timestamp = now_iso(deps.now())
    differences = _batch_differences(conn, int(batch["id"]))
    attachments, differences = notification_files_and_differences(
        licitacion["ruta_carpeta"] if "ruta_carpeta" in licitacion.keys() else "",
        differences,
    )
    attachments, omitted_attachments = select_email_attachments(
        attachments, limit_bytes=deps.email_attachment_limit_bytes
    )
    link = conn.execute(
        """
        SELECT l.status, l.ai_job_id, s.summary_text, s.summary_json
        FROM tender_monitor_ai_links AS l
        LEFT JOIN ai_summaries AS s ON s.created_from_job_id = l.ai_job_id
        WHERE l.batch_id = ? ORDER BY l.id DESC LIMIT 1
        """,
        (batch["id"],),
    ).fetchone()
    ai_summary = ""
    if link and normalize_text(link["status"]) == "completed":
        ai_summary = normalize_text(link["summary_text"]) or normalize_text(link["summary_json"])
    content = build_notification_content(
        _row_dict(licitacion),
        platform=normalize_text(batch["platform"]),
        checked_at=normalize_text(batch["created_at"]),
        differences=differences,
        ai_summary=ai_summary,
        ai_failed=normalize_text(batch["ai_status"]) == "failed",
        suite_url=(
            deps.suite_base_url.rstrip("/") + f"/app/licitaciones/{licitacion['id']}"
            if deps.suite_base_url
            else ""
        ),
        attachment_names=[path.name for path in attachments],
        omitted_attachments=omitted_attachments,
    )
    channel = normalize_text(notification["channel"])
    error = ""
    external_id = ""
    sent_at = ""
    if channel == "email":
        result = _send_email(
            deps.email_sender,
            normalize_text(notification["destination"]),
            content,
            attachments,
        )
        raw_sent_at, raw_error = result
        sent_at, error = normalize_text(raw_sent_at), normalize_text(raw_error)
        ok = bool(sent_at and not error)
    elif channel == "telegram":
        user = conn.execute(
            "SELECT * FROM usuarios WHERE username = ?", (notification["username"],)
        ).fetchone()
        sender = deps.telegram_sender or (
            lambda value, message: send_telegram_user_message(value, message, env=deps.env or os.environ)
        )
        result = sender(_row_dict(user) if user else {}, content["telegram"])
        ok, error, external_id = _telegram_result(result)
        sent_at = timestamp if ok else ""
    else:
        return {"ok": False, "error": f"Canal no reconocido: {channel}."}

    conn.execute(
        """
        UPDATE tender_monitor_notifications
        SET status = ?, attempt_count = attempt_count + 1, attempted_at = ?,
            sent_at = CASE WHEN ? THEN ? ELSE sent_at END,
            external_id = CASE WHEN ? THEN ? ELSE external_id END,
            error_message = ?
        WHERE id = ?
        """,
        (
            "sent" if ok else "failed",
            timestamp,
            1 if ok else 0,
            sent_at or timestamp,
            1 if ok else 0,
            external_id,
            None if ok else error,
            notification_id,
        ),
    )
    if not ok:
        record_incident(
            conn,
            cycle_id=int(cycle["id"]),
            execution_id=int(execution["id"]),
            licitacion_id=int(licitacion["id"]),
            phase=f"notification_{channel}",
            code=f"{channel.upper()}_RETRY_FAILED",
            summary=f"Falló el reintento de {channel}.",
            technical_detail=error,
            outcome="retry_available",
            dedupe_key=f"notification-retry:{notification_id}:{int(notification['attempt_count']) + 1}",
            timestamp=timestamp,
        )
    overall = _refresh_notification_outcome(
        conn,
        batch_id=int(batch["id"]),
        execution_id=int(execution["id"]),
        timestamp=timestamp,
    )
    return {
        "ok": ok,
        "notification_id": notification_id,
        "status": "sent" if ok else "failed",
        "overall_status": overall,
        "error": error,
    }


def retry_batch_ai(
    conn: sqlite3.Connection,
    batch_id: int,
    *,
    deps: TenderMonitorDependencies,
) -> dict[str, object]:
    """Reencola únicamente la IA de un lote, conservando descarga y notificaciones."""
    context = _retry_context(conn, batch_id)
    if not context:
        return {"ok": False, "error": "Lote no encontrado."}
    batch, execution, cycle, licitacion = context
    if normalize_text(batch["ai_status"]) == "completed":
        return {"ok": True, "status": "completed", "already_completed": True}
    differences = _batch_differences(conn, batch_id)
    if not any(item.get("ai_candidate") for item in differences):
        return {"ok": False, "error": "El lote no contiene documentos candidatos a IA."}
    conn.execute(
        "DELETE FROM tender_monitor_ai_links WHERE batch_id = ? AND status IN ('failed', 'timeout')",
        (batch_id,),
    )
    conn.execute(
        "UPDATE tender_monitor_batches SET ai_decision = 'required', ai_status = 'waiting' WHERE id = ?",
        (batch_id,),
    )
    status, summary, failed = _process_ai(
        conn,
        deps=deps,
        cycle=cycle,
        execution_id=int(execution["id"]),
        batch_id=batch_id,
        licitacion_id=int(licitacion["id"]),
        differences=differences,
        timestamp=now_iso(deps.now()),
    )
    conn.execute(
        "UPDATE tender_monitor_executions SET ai_status = ? WHERE id = ?",
        (status, execution["id"]),
    )
    return {"ok": not failed, "status": status, "summary": summary, "error": "" if not failed else "La IA volvió a fallar."}


def _process_tender(
    conn: sqlite3.Connection,
    *,
    deps: TenderMonitorDependencies,
    cycle: sqlite3.Row,
    row: sqlite3.Row,
    prep: TenderPreparation,
    db_path: str | Path,
    owner: str,
) -> str:
    cycle_id = int(cycle["id"])
    timestamp = now_iso(deps.now())
    execution_id = create_execution(
        conn,
        cycle_id=cycle_id,
        licitacion_id=prep.licitacion_id,
        platform=prep.platform,
        timestamp=timestamp,
    )
    if not prep.followed:
        finish_execution(
            conn,
            execution_id,
            status="not_followed",
            timestamp=timestamp,
            preparation_status="not_followed",
            preparation_reason=prep.reason,
        )
        increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            licitacion_id=prep.licitacion_id,
            phase="preparation",
            code="NOT_FOLLOWED",
            summary=prep.reason,
            outcome="skipped",
            timestamp=timestamp,
        )
        return "not_followed"
    if not prep.prepared:
        incident_code = prep.preparation_code or "NOT_PREPARED"
        finish_execution(
            conn,
            execution_id,
            status="not_prepared",
            timestamp=timestamp,
            preparation_status="not_prepared",
            preparation_reason=prep.reason,
            error_phase="preparation",
            error_code=incident_code,
            error_message=prep.reason,
        )
        increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            licitacion_id=prep.licitacion_id,
            phase="preparation",
            code=incident_code,
            summary=prep.reason,
            outcome="skipped",
            timestamp=timestamp,
        )
        return "not_prepared"

    lease_minutes = _setting_int(conn, "lease_minutes", 60, minimum=5, maximum=1440)
    lease_key = f"tender-io:licitacion:{prep.licitacion_id}"
    acquired, existing = acquire_lease(
        conn,
        lease_key=lease_key,
        owner=owner,
        minutes=lease_minutes,
        timestamp=deps.now(),
        metadata={"cycle_id": cycle_id, "execution_id": execution_id},
    )
    if not acquired:
        reason = f"La licitación ya se está procesando ({existing.get('owner') if existing else 'otra operación'})."
        finish_execution(
            conn,
            execution_id,
            status="deferred_busy",
            timestamp=timestamp,
            preparation_status="prepared",
            error_phase="lock",
            error_code="TENDER_OPERATION_BUSY",
            error_message=reason,
        )
        increment_cycle(conn, cycle_id, processed_count=1)
        return "deferred_busy"
    conn.commit()

    path_lock = destination_lock(
        prep.destination,
        owner=f"monitor:{cycle_id}:{execution_id}:{owner}",
    )
    try:
        path_lock.__enter__()
    except DestinationBusyError as exc:
        finish_execution(
            conn,
            execution_id,
            status="deferred_busy",
            timestamp=timestamp,
            preparation_status="prepared",
            error_phase="lock",
            error_code="DESTINATION_BUSY",
            error_message=str(exc),
        )
        increment_cycle(conn, cycle_id, processed_count=1)
        release_lease(conn, lease_key=lease_key, owner=owner)
        conn.commit()
        return "deferred_busy"
    path_lock_active = True
    try:
        cycle_metadata = json_load(cycle["metadata_json"], {})
        force_baseline = bool(
            isinstance(cycle_metadata, Mapping) and cycle_metadata.get("force_baseline")
        )
        if force_baseline:
            previous_id, previous = None, None
        else:
            previous_id, previous = _choose_previous_snapshot(
                conn,
                prep=prep,
                cycle_id=cycle_id,
                execution_id=execution_id,
                timestamp=timestamp,
            )
        conn.commit()
        attempts = _setting_int(conn, "download_retries", 2, minimum=1, maximum=5)
        try:
            result, attempt_count = _run_downloader(deps, prep, db_path=db_path, attempts=attempts)
        except BaseException as exc:
            finished = now_iso(deps.now())
            finish_execution(
                conn,
                execution_id,
                status="error",
                timestamp=finished,
                preparation_status="prepared",
                previous_snapshot_id=previous_id,
                error_phase="download",
                error_code="DOWNLOADER_EXCEPTION",
                error_message=str(exc),
            )
            increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
            record_incident(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                licitacion_id=prep.licitacion_id,
                phase="download",
                code="DOWNLOADER_EXCEPTION",
                summary="El descargador no pudo completar la consulta.",
                technical_detail=str(exc),
                retry_count=attempts - 1 if _transient_error(exc) else 0,
                outcome="retry_available",
                timestamp=finished,
            )
            return "error"
        conn.execute(
            "UPDATE tender_monitor_executions SET attempt_count = ? WHERE id = ?",
            (attempt_count, execution_id),
        )
        finished = now_iso(deps.now())
        if not _result_is_usable(result):
            message = result.error or "; ".join(result.recoverable_issues) or "El descargador no devolvió un estado utilizable."
            finish_execution(
                conn,
                execution_id,
                status="error",
                timestamp=finished,
                preparation_status="prepared",
                previous_snapshot_id=previous_id,
                error_phase="download",
                error_code="DOWNLOADER_FAILED",
                error_message=message,
            )
            increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
            record_incident(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                licitacion_id=prep.licitacion_id,
                phase="download",
                code="DOWNLOADER_FAILED",
                summary="La consulta de la plataforma falló y se conservó el último estado válido.",
                technical_detail=message,
                retry_count=max(0, attempt_count - 1),
                outcome="state_preserved",
                timestamp=finished,
            )
            return "error"
        current_raw = snapshot_from_result(result, destination=prep.destination, captured_at=finished)
        if result.status == "partial":
            _record_partial_incident(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                prep=prep,
                result=result,
                attempt_count=attempt_count,
                timestamp=finished,
            )
        if previous is None:
            document_status = normalize_text(current_raw["blocks"]["documents"]["status"])
            if document_status != "complete":
                finish_execution(
                    conn,
                    execution_id,
                status="partial",
                timestamp=finished,
                preparation_status="prepared",
                error_phase="baseline",
                    error_code="BASELINE_INCOMPLETE",
                    error_message="No se confirmó una línea base a partir de una respuesta parcial.",
                    log=_observation_log(
                        result,
                        current_raw,
                        previous_snapshot_id=None,
                    ),
                )
                increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
                return "partial"
            current_id = save_snapshot(
                conn,
                licitacion_id=prep.licitacion_id,
                platform=prep.platform,
                snapshot=current_raw,
                source="baseline_rebuilt",
                execution_id=execution_id,
                timestamp=finished,
            )
            set_monitor_baseline(
                conn,
                licitacion_id=prep.licitacion_id,
                snapshot_id=current_id,
                execution_id=execution_id,
                reason="manual_rebuild" if force_baseline else "initial",
                timestamp=finished,
            )
            finish_execution(
                conn,
                execution_id,
                status="baseline_rebuilt",
                timestamp=finished,
                preparation_status="prepared",
                current_snapshot_id=current_id,
                log=_observation_log(
                    result,
                    current_raw,
                    previous_snapshot_id=None,
                    current_snapshot_id=current_id,
                ),
            )
            increment_cycle(conn, cycle_id, processed_count=1, baseline_count=1)
            conn.commit()
            _write_sidecar_after_commit(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                prep=prep,
                snapshot_id=current_id,
                snapshot=current_raw,
                timestamp=finished,
            )
            return "baseline_rebuilt"

        differences = compare_snapshots(previous, current_raw)
        categories = [item.strip() for item in _setting(conn, "document_ai_categories", "").split(",") if item.strip()]
        differences = mark_ai_candidates(differences, enabled_categories=categories)
        confirmed = merge_valid_blocks(previous, current_raw)
        current_id = save_snapshot(
            conn,
            licitacion_id=prep.licitacion_id,
            platform=prep.platform,
            snapshot=confirmed,
            source="monitor",
            execution_id=execution_id,
            timestamp=finished,
        )
        set_monitor_baseline(
            conn,
            licitacion_id=prep.licitacion_id,
            snapshot_id=current_id,
            execution_id=execution_id,
            reason="monitor_review",
            timestamp=finished,
        )
        if not differences:
            finish_execution(
                conn,
                execution_id,
                status="no_changes" if result.status != "partial" else "partial",
                timestamp=finished,
                preparation_status="prepared",
                previous_snapshot_id=previous_id,
                current_snapshot_id=current_id,
                log=_observation_log(
                    result,
                    confirmed,
                    previous_snapshot_id=previous_id,
                    current_snapshot_id=current_id,
                    differences=differences,
                ),
            )
            increment_cycle(conn, cycle_id, processed_count=1, no_changes_count=1)
            conn.commit()
            _write_sidecar_after_commit(
                conn,
                cycle_id=cycle_id,
                execution_id=execution_id,
                prep=prep,
                snapshot_id=current_id,
                snapshot=confirmed,
                timestamp=finished,
            )
            return "no_changes"

        batch_id, created = create_batch(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            licitacion_id=prep.licitacion_id,
            platform=prep.platform,
            previous_snapshot_id=int(previous_id),
            current_snapshot_id=current_id,
            difference_fingerprint=difference_fingerprint(differences),
            summary=differences_summary(differences),
            differences=differences,
            timestamp=finished,
        )
        finish_execution(
            conn,
            execution_id,
            status="changes" if created else "no_changes",
            timestamp=finished,
            preparation_status="prepared",
            previous_snapshot_id=previous_id,
            current_snapshot_id=current_id,
            batch_id=batch_id,
            ai_status="pending" if created else "already_processed",
            notification_status="pending" if created else "already_processed",
            log=_observation_log(
                result,
                confirmed,
                previous_snapshot_id=previous_id,
                current_snapshot_id=current_id,
                differences=differences,
            ),
        )
        increment_cycle(conn, cycle_id, processed_count=1, **({"changes_count": 1} if created else {"no_changes_count": 1}))
        conn.commit()
        _write_sidecar_after_commit(
            conn,
            cycle_id=cycle_id,
            execution_id=execution_id,
            prep=prep,
            snapshot_id=current_id,
            snapshot=confirmed,
            timestamp=finished,
        )
        path_lock.__exit__(None, None, None)
        path_lock_active = False
        if not created:
            return "no_changes"
        ai_status, ai_summary, ai_failed = _process_ai(
            conn,
            deps=deps,
            cycle=cycle,
            execution_id=execution_id,
            batch_id=batch_id,
            licitacion_id=prep.licitacion_id,
            differences=differences,
            timestamp=finished,
        )
        notified_at = now_iso(deps.now())
        notification_status = send_batch_notifications(
            conn,
            deps=deps,
            cycle_id=cycle_id,
            execution_id=execution_id,
            batch_id=batch_id,
            licitacion=_row_dict(row),
            platform=prep.platform,
            checked_at=notified_at,
            ai_summary=ai_summary,
            ai_failed=ai_failed,
        )
        conn.execute(
            "UPDATE tender_monitor_executions SET ai_status = ? WHERE id = ?",
            (ai_status, execution_id),
        )
        if notification_status in {"notified", "partial"}:
            increment_cycle(conn, cycle_id, notified_count=1)
        elif notification_status == "notification_failed":
            increment_cycle(conn, cycle_id, error_count=1)
        return notification_status
    except BaseException:
        # Never let the lease-release commit confirm a half-built review. Commits
        # performed earlier (baseline + batch) remain durable, while any pending
        # transaction from the failing phase is discarded.
        conn.rollback()
        raise
    finally:
        if path_lock_active:
            path_lock.__exit__(None, None, None)
        release_lease(conn, lease_key=lease_key, owner=owner)
        conn.commit()


def send_consolidated_incident_report(
    conn: sqlite3.Connection,
    *,
    deps: TenderMonitorDependencies,
    cycle_id: int,
) -> str:
    existing = conn.execute(
        "SELECT * FROM tender_monitor_incident_reports WHERE cycle_id = ?", (cycle_id,)
    ).fetchone()
    if existing and existing["status"] == "sent":
        return "sent"
    incidents = conn.execute(
        """
        SELECT i.*, l.expediente, l.objeto, l.plataforma
        FROM tender_monitor_incidents AS i
        LEFT JOIN licitaciones AS l ON l.id = i.licitacion_id
        WHERE i.cycle_id = ? ORDER BY i.id
        """,
        (cycle_id,),
    ).fetchall()
    if not incidents:
        return "not_required"
    cycle = cycle_row(conn, cycle_id)
    admin = incident_admin_recipient(conn)
    content = build_incident_report(
        dict(cycle),
        [dict(row) for row in incidents],
        suite_base_url=deps.suite_base_url,
    )
    timestamp = now_iso(deps.now())
    recipient = normalize_text(admin["email"] if admin else "")
    conn.execute(
        """
        INSERT INTO tender_monitor_incident_reports (
            cycle_id, recipient, subject, body_text, body_html, status, created_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
        ON CONFLICT(cycle_id) DO UPDATE SET recipient = excluded.recipient,
            subject = excluded.subject, body_text = excluded.body_text,
            body_html = excluded.body_html
        """,
        (cycle_id, recipient, content["subject"], content["text"], content["html"], timestamp),
    )
    if not recipient:
        conn.execute(
            """
            UPDATE tender_monitor_incident_reports SET status = 'failed', attempt_count = attempt_count + 1,
                attempted_at = ?, error_message = 'No hay administrador de incidencias con correo configurado.'
            WHERE cycle_id = ?
            """,
            (timestamp, cycle_id),
        )
        return "failed"
    sent_at, error = deps.email_sender(recipient, content["subject"], content["text"], content["html"]) if deps.email_sender else (None, "Correo no configurado")
    if sent_at and not error:
        conn.execute(
            """
            UPDATE tender_monitor_incident_reports SET status = 'sent', attempt_count = attempt_count + 1,
                attempted_at = ?, sent_at = ?, error_message = NULL WHERE cycle_id = ?
            """,
            (timestamp, sent_at, cycle_id),
        )
        return "sent"
    conn.execute(
        """
        UPDATE tender_monitor_incident_reports SET status = 'failed', attempt_count = attempt_count + 1,
            attempted_at = ?, error_message = ? WHERE cycle_id = ?
        """,
        (timestamp, normalize_text(error), cycle_id),
    )
    return "failed"


def run_tender_monitor_cycle(
    cycle_id: int,
    *,
    db_path: str | Path,
    root: str | Path | None = None,
    dependencies: TenderMonitorDependencies | None = None,
) -> dict[str, object]:
    deps = dependencies or TenderMonitorDependencies()
    conn = connect(db_path)
    cycle = cycle_row(conn, cycle_id)
    if not cycle:
        conn.close()
        raise ValueError("Ciclo de monitor no encontrado.")
    try:
        config = load_monitor_config(root)
    except BaseException as exc:
        timestamp = now_iso(deps.now())
        finish_cycle(conn, cycle_id, status="failed", timestamp=timestamp)
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=None,
            licitacion_id=cycle["requested_licitacion_id"],
            phase="configuration",
            code="MONITOR_CONFIGURATION_INVALID",
            summary="La configuración del monitor no permite iniciar el ciclo.",
            technical_detail=str(exc),
            outcome="configuration_required",
            timestamp=timestamp,
        )
        conn.commit()
        conn.close()
        return {"cycle_id": cycle_id, "status": "failed", "message": str(exc)}
    owner = _owner(cycle_id)
    global_minutes = _setting_int(conn, "lease_minutes", 60, minimum=5, maximum=1440)
    acquired, existing = acquire_lease(
        conn,
        lease_key="tender-monitor:global",
        owner=owner,
        minutes=global_minutes,
        timestamp=deps.now(),
        metadata={"cycle_id": cycle_id},
    )
    if not acquired:
        finish_cycle(conn, cycle_id, status="failed", timestamp=now_iso(deps.now()))
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=None,
            licitacion_id=cycle["requested_licitacion_id"],
            phase="lock",
            code="CYCLE_ALREADY_RUNNING",
            summary="Ya existe un ciclo del monitor en ejecución.",
            technical_detail=json_dump(existing or {}),
            outcome="skipped",
        )
        conn.commit()
        conn.close()
        return {"cycle_id": cycle_id, "status": "failed", "message": "Ya existe un ciclo activo."}

    try:
        markers, discovered = discover_followed(config.root_path, config.year_min, config.year_max)
        markers_by_id = {marker.licitacion_id: marker for marker in markers}
        if cycle["requested_licitacion_id"]:
            target_ids = [int(cycle["requested_licitacion_id"])]
            scan_result = None
        else:
            scan_result = discovered
            target_ids = sorted(markers_by_id)
        started = now_iso(deps.now())
        if not start_cycle(conn, cycle_id, total_count=len(target_ids), timestamp=started):
            current = cycle_row(conn, cycle_id)
            return {"cycle_id": cycle_id, "status": current["status"] if current else "missing"}
        if scan_result:
            for issue in [*scan_result.conflicts, *scan_result.warnings]:
                record_incident(
                    conn,
                    cycle_id=cycle_id,
                    execution_id=None,
                    licitacion_id=issue.licitacion_id,
                    phase="discovery",
                    code=issue.code.upper(),
                    summary=issue.message,
                    technical_detail=issue.path,
                    outcome="skipped" if issue.code in {"duplicate_id_marker", "multiple_ids_in_folder"} else "recorded",
                    dedupe_key=f"discovery:{issue.code}:{issue.licitacion_id}:{issue.path}",
                    timestamp=started,
                )
        conn.commit()
        cycle = cycle_row(conn, cycle_id)
        results: list[dict[str, object]] = []
        for licitacion_id in target_ids:
            heartbeat_cycle(conn, cycle_id, current_licitacion_id=licitacion_id, timestamp=now_iso(deps.now()))
            refresh_lease(
                conn,
                lease_key="tender-monitor:global",
                owner=owner,
                minutes=global_minutes,
                timestamp=deps.now(),
            )
            row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if not row:
                record_incident(
                    conn,
                    cycle_id=cycle_id,
                    execution_id=None,
                    licitacion_id=licitacion_id,
                    phase="discovery",
                    code="LICITACION_MISSING",
                    summary="Existe marcador de seguimiento, pero la licitación no está en SQLite.",
                    outcome="skipped",
                )
                increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
                conn.commit()
                continue
            prep = preparation_for_row(
                row,
                root=config.root_path,
                marker=markers_by_id.get(licitacion_id),
                year_min=config.year_min,
                year_max=config.year_max,
            )
            try:
                status = _process_tender(
                    conn,
                    deps=deps,
                    cycle=cycle,
                    row=row,
                    prep=prep,
                    db_path=db_path,
                    owner=owner,
                )
            except BaseException as exc:
                conn.rollback()
                timestamp = now_iso(deps.now())
                execution = conn.execute(
                    "SELECT id FROM tender_monitor_executions WHERE cycle_id = ? AND licitacion_id = ?",
                    (cycle_id, licitacion_id),
                ).fetchone()
                execution_id = int(execution["id"]) if execution else None
                if execution_id:
                    finish_execution(
                        conn,
                        execution_id,
                        status="error",
                        timestamp=timestamp,
                        error_phase="unexpected",
                        error_code="UNEXPECTED_ERROR",
                        error_message=str(exc),
                    )
                increment_cycle(conn, cycle_id, processed_count=1, error_count=1)
                record_incident(
                    conn,
                    cycle_id=cycle_id,
                    execution_id=execution_id,
                    licitacion_id=licitacion_id,
                    phase="unexpected",
                    code="UNEXPECTED_ERROR",
                    summary="Error inesperado procesando la licitación; el ciclo continuará.",
                    technical_detail=str(exc),
                    outcome="retry_available",
                    timestamp=timestamp,
                )
                status = "error"
            conn.commit()
            results.append({"licitacion_id": licitacion_id, "status": status})
        report_status = send_consolidated_incident_report(conn, deps=deps, cycle_id=cycle_id)
        incidents = int(conn.execute("SELECT COUNT(*) FROM tender_monitor_incidents WHERE cycle_id = ?", (cycle_id,)).fetchone()[0])
        final_status = "completed_with_incidents" if incidents else "completed"
        finish_cycle(conn, cycle_id, status=final_status, timestamp=now_iso(deps.now()))
        conn.commit()
        return {
            "cycle_id": cycle_id,
            "status": final_status,
            "processed": len(results),
            "results": results,
            "incident_report_status": report_status,
        }
    finally:
        release_lease(conn, lease_key="tender-monitor:global", owner=owner)
        conn.commit()
        conn.close()
