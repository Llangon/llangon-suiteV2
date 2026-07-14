from __future__ import annotations

import json
import re
import smtplib
import sqlite3
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .codex_local_provider import CodexLocalProvider
from .config import AIConfig, get_ai_config
from .document_selector import inspect_document_selection
from .file_selection import AIFileSelectionError, resolve_selected_ai_files
from .gemini_provider import AIProviderError, GeminiProvider, ProviderResult
from .hashing import hash_documents
from .notifications import (
    create_job_notifications,
    latest_notification_rows_for_licitacion,
    mark_job_notifications_skipped,
    normalize_email_list,
    notification_rows_for_job,
    notification_status_payload,
    send_pending_job_notifications,
)
from .queue import (
    active_job,
    cancel_job,
    claim_pending_job,
    create_job,
    dismiss_finished_jobs,
    dismiss_job,
    elapsed_seconds_for_row,
    estimate_label_for_job,
    estimate_seconds_for_job,
    human_stage,
    latest_job,
    latest_summary,
    mark_stale_jobs_in_conn,
    now_iso as queue_now_iso,
    record_usage,
    row_to_dict,
    save_summary,
    touch_job_progress,
    update_job,
)
from .rate_limit import check_rate_limit
from .postprocess import postprocess_summary
from .schemas import AISchemaError, parse_summary_json, summary_quality_check, summary_text


class ProviderProtocol(Protocol):
    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        ...


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _commit_if_possible(conn: sqlite3.Connection) -> None:
    try:
        conn.commit()
    except sqlite3.Error:
        pass


def _is_cancel_requested(conn: sqlite3.Connection, job_id: int) -> bool:
    row = conn.execute("SELECT cancel_requested FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    return bool(row and int(row["cancel_requested"] or 0))


def _mark_cancelled(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    message: str = "Cancelado por el usuario.",
    skip_notifications: bool = True,
) -> None:
    update_job(
        conn,
        job_id,
        status="cancelled",
        finished_at=_now(),
        progress_stage="cancelled",
        progress_message=message,
        heartbeat_at=_now(),
        error_code="CANCELLED",
        error_message="Análisis IA cancelado por el usuario.",
    )
    if skip_notifications:
        mark_job_notifications_skipped(conn, job_id, "Análisis IA cancelado por el usuario.", now=_now)


def _usage_value(raw: dict[str, object], *names: str) -> int | None:
    for name in names:
        value = raw.get(name)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _provider_enabled(config: AIConfig) -> bool:
    return config.provider_enabled


def _provider_configured(config: AIConfig) -> bool:
    return config.configured


def _provider_model(config: AIConfig) -> str:
    if config.analysis_provider == "gemini":
        return config.model
    if config.analysis_provider == "codex_local":
        return config.codex_model
    return config.analysis_provider


def _provider_unavailable(config: AIConfig) -> tuple[str, str, str]:
    if config.analysis_provider == "codex_local":
        if not config.codex_local_enabled:
            return "error", "CODEX_DISABLED", "Codex Local no está activado."
        return "error", "CODEX_NOT_CONFIGURED", "Codex Local no está configurado."
    if config.analysis_provider == "gemini":
        if not config.enabled:
            return "error", "GEMINI_DISABLED", "Gemini desactivado."
        if not config.configured:
            return "error", "GEMINI_NOT_CONFIGURED", "Gemini no configurado."
    return "disabled", "AI_DISABLED", "IA desactivada."


def _summary_payload(row: sqlite3.Row | None) -> dict[str, object] | None:
    data = row_to_dict(row)
    if not data:
        return None
    return {
        "id": data["id"],
        "document_hash": data["document_hash"],
        "provider": data["provider"],
        "model": data.get("model") or "",
        "summary": data.get("summary") or {},
        "summary_text": data.get("summary_text") or "",
        "created_at": data.get("created_at") or "",
        "updated_at": data.get("updated_at") or "",
        "quality_status": data.get("quality_status") or "pending_review",
    }


def _summary_row_is_useful(conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
    if str(row["quality_status"] or "") in {"empty_analysis", "low_quality_analysis", "encoding_error"}:
        return False
    try:
        raw_summary = json.loads(str(row["summary_json"] or "{}"))
        quality = summary_quality_check(postprocess_summary(parse_summary_json(raw_summary)))
    except Exception:
        return True
    if quality["is_useful"]:
        return True
    conn.execute(
        "UPDATE ai_summaries SET quality_status = ?, updated_at = ? WHERE id = ?",
        (quality["status"], _now(), row["id"]),
    )
    return False


def _quality_error(quality_check: dict[str, object]) -> tuple[str, str]:
    status = str(quality_check.get("status") or "empty_analysis")
    if status == "encoding_error":
        return "ENCODING_ERROR", "El análisis IA contiene caracteres mal codificados."
    if status == "low_quality_analysis":
        return "LOW_QUALITY_ANALYSIS", "El análisis IA no tiene estructura operativa suficiente."
    return "EMPTY_ANALYSIS", "La IA devolvió un JSON válido pero sin contenido útil."


def _latest_useful_summary(
    conn: sqlite3.Connection,
    licitacion_id: int,
    document_hash: str | None = None,
) -> sqlite3.Row | None:
    values: list[object] = [licitacion_id]
    where = "licitacion_id = ?"
    if document_hash:
        where += " AND document_hash = ?"
        values.append(document_hash)
    rows = conn.execute(
        f"SELECT * FROM ai_summaries WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT 10",
        values,
    ).fetchall()
    for row in rows:
        if _summary_row_is_useful(conn, row):
            return row
    return None


_ANSI_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|password)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _safe_provider_error_preview(value: object, *, limit: int = 1800) -> str:
    text = _ANSI_ESCAPE_RE.sub("", str(value or ""))
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[oculto]", text)
    text = _BEARER_RE.sub("Bearer [oculto]", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()
    if len(text) > limit:
        text = f"[inicio omitido]\n{text[-limit:]}"
    return text


def _provider_error_hint(error_code: str, preview: str) -> str:
    code = str(error_code or "").upper()
    lowered = preview.lower()
    if code == "CODEX_NOT_FOUND":
        return "No se localiza el ejecutable configurado de Codex."
    if code == "CODEX_LAUNCH_ERROR":
        return "Codex está instalado, pero Windows no ha podido iniciar el proceso."
    if code == "CODEX_UPDATE_REQUIRED":
        return "La versión instalada de Codex es demasiado antigua para el modelo configurado; hay que actualizar Codex CLI."
    if code == "CODEX_TIMEOUT":
        return "Codex superó el tiempo máximo configurado antes de devolver el informe."
    if code == "INVALID_JSON":
        return "Codex respondió, pero el resultado no tenía el formato estructurado esperado."
    if code == "RESOURCE_EXHAUSTED":
        return "El proveedor ha aplicado un límite temporal; el trabajo puede reintentarse más tarde."
    if code != "CODEX_ERROR":
        return "Consulta el detalle técnico para identificar la fase exacta del fallo."
    if "requires a newer version of codex" in lowered or "please upgrade to the latest app or cli" in lowered:
        return "La versión instalada de Codex es demasiado antigua para el modelo configurado; hay que actualizar Codex CLI."
    if any(marker in lowered for marker in ("401", "unauthorized", "not logged in", "authentication", "credentials", "refresh token")):
        return "La sesión de Codex no está autorizada o ha caducado."
    if any(marker in lowered for marker in ("429", "rate limit", "too many requests", "quota")):
        return "Codex ha aplicado un límite temporal de uso."
    if any(marker in lowered for marker in ("context window", "context length", "too many tokens", "maximum context")):
        return "La documentación o la respuesta superó la capacidad admitida por el modelo."
    if any(marker in lowered for marker in ("failed to connect", "connection", "network", "dns", "tls", "certificate")):
        return "Codex no pudo completar la conexión con el servicio."
    if any(marker in lowered for marker in ("permission denied", "access is denied", "acceso denegado", "sandbox", "read-only")):
        return "Windows o el entorno de seguridad impidió una operación necesaria."
    if "model" in lowered and any(marker in lowered for marker in ("not found", "unavailable", "unsupported")):
        return "El modelo configurado no está disponible para esta ejecución."
    return "Codex terminó antes de entregar el informe; el detalle técnico contiene la causa devuelta por el ejecutable."


def _job_error_diagnostic(data: dict[str, object], diagnostics: dict[str, object]) -> dict[str, object]:
    error_code = str(data.get("error_code") or "")
    if not error_code:
        return {}
    detail = _safe_provider_error_preview(
        diagnostics.get("stderr_preview")
        or diagnostics.get("provider_error_preview")
        or diagnostics.get("os_error_message")
        or diagnostics.get("stdout_preview")
        or diagnostics.get("raw_response_preview")
    )
    return {
        "code": error_code,
        "returncode": diagnostics.get("returncode"),
        "detail": detail,
        "hint": _provider_error_hint(error_code, detail),
    }


def _job_payload(row: sqlite3.Row | None) -> dict[str, object] | None:
    data = row_to_dict(row)
    if not data:
        return None
    raw_diagnostics: dict[str, object] = {}
    raw_usage: dict[str, object] = {}
    raw_payload = data.get("raw_usage_json") or ""
    if raw_payload:
        try:
            decoded = json.loads(str(raw_payload))
            if isinstance(decoded, dict):
                raw_usage = decoded
                if isinstance(decoded.get("diagnostics"), dict):
                    raw_diagnostics = decoded["diagnostics"]
                elif isinstance(decoded.get("parse_diagnostics"), dict):
                    raw_diagnostics = decoded["parse_diagnostics"]
        except json.JSONDecodeError:
            raw_diagnostics = {}
    quality_check = raw_usage.get("quality_check") if isinstance(raw_usage.get("quality_check"), dict) else {}
    selected_documents = data.get("selected_documents") if isinstance(data.get("selected_documents"), list) else []
    selected_documents_count = len(selected_documents)
    provider = str(data.get("provider") or "")
    estimated_seconds = int(data.get("estimated_seconds") or estimate_seconds_for_job(provider, selected_documents_count))
    elapsed_seconds = elapsed_seconds_for_row(data)
    status = str(data.get("status") or "")
    progress_stage = str(data.get("progress_stage") or status)
    is_taking_longer = bool(status == "processing" and estimated_seconds and elapsed_seconds > estimated_seconds + 120)
    return {
        "id": data["id"],
        "status": status,
        "provider": provider,
        "document_hash": data["document_hash"],
        "model": data.get("model") or "",
        "created_at": data.get("created_at") or "",
        "started_at": data.get("started_at") or "",
        "finished_at": data.get("finished_at") or "",
        "progress_stage": progress_stage,
        "progress_label": human_stage(progress_stage, status),
        "progress_message": data.get("progress_message") or "",
        "progress_percent": data.get("progress_percent"),
        "heartbeat_at": data.get("heartbeat_at") or "",
        "worker_pid": data.get("worker_pid"),
        "cancel_requested": bool(data.get("cancel_requested") or 0),
        "elapsed_seconds": elapsed_seconds,
        "estimated_seconds": estimated_seconds,
        "estimated_label": estimate_label_for_job(provider, selected_documents_count),
        "is_taking_longer_than_expected": is_taking_longer,
        "error_code": data.get("error_code") or "",
        "error_message": data.get("error_message") or "",
        "error_diagnostic": _job_error_diagnostic(data, raw_diagnostics),
        "next_retry_at": data.get("next_retry_at") or "",
        "dismissed_at": data.get("dismissed_at") or "",
        "dismissed_by": data.get("dismissed_by") or "",
        "attempts": data.get("attempts") or 0,
        "selected_documents_count": selected_documents_count,
        "diagnostics": raw_diagnostics,
        "raw_response_preview": raw_diagnostics.get("raw_response_preview", ""),
        "parse_attempts": raw_diagnostics.get("parse_attempts", []),
        "summary_quality_status": quality_check.get("status", ""),
        "quality_check": quality_check,
        "sent_documents_count": raw_usage.get("sent_documents_count") or raw_diagnostics.get("sent_documents_count") or 0,
        "sent_documents_names": raw_usage.get("sent_documents_names") or raw_diagnostics.get("sent_documents_names") or [],
        "total_pdf_bytes_sent": raw_usage.get("total_pdf_bytes_sent") or raw_diagnostics.get("total_pdf_bytes_sent") or 0,
        "input_mode_used": raw_usage.get("input_mode_used") or raw_diagnostics.get("input_mode_used") or "",
        "document_send_method": raw_usage.get("document_send_method") or raw_diagnostics.get("document_send_method") or "",
        "documents_text_extracted_count": raw_usage.get("documents_text_extracted_count")
        or raw_diagnostics.get("documents_text_extracted_count")
        or 0,
        "extracted_chars_total": raw_usage.get("extracted_chars_total") or raw_diagnostics.get("extracted_chars_total") or 0,
        "extracted_chars_by_document": raw_usage.get("extracted_chars_by_document")
        or raw_diagnostics.get("extracted_chars_by_document")
        or {},
        "pages_processed_by_document": raw_usage.get("pages_processed_by_document")
        or raw_diagnostics.get("pages_processed_by_document")
        or {},
        "extraction_warnings": raw_usage.get("extraction_warnings") or raw_diagnostics.get("extraction_warnings") or [],
        "response_text_length": raw_diagnostics.get("text_length", 0),
        "duration_seconds": raw_usage.get("duration_seconds") or raw_diagnostics.get("duration_seconds") or 0,
        "timeout_seconds": raw_usage.get("timeout_seconds") or raw_diagnostics.get("timeout_seconds") or 0,
        "usage_metadata": {
            key: value
            for key, value in raw_usage.items()
            if key
            not in {
                "diagnostics",
                "parse_diagnostics",
                "quality_check",
                "sent_documents_names",
            }
        },
    }


def _select_documents(
    config: AIConfig,
    row: sqlite3.Row,
    selected_files: list[object] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if selected_files is not None:
        try:
            selected = resolve_selected_ai_files(row, selected_files, max_file_mb=config.max_file_mb)
        except AIFileSelectionError as exc:
            return [], {"final_reason": str(exc), "manual_selection_error": True}
        return selected, {"manual_selection": True, "selected_files_count": len(selected)}
    selection = inspect_document_selection(
        row,
        max_documents=config.max_documents_per_analysis,
        max_file_mb=config.max_file_mb,
    )
    return list(selection["selected_documents"]), dict(selection["diagnostics"])


def _base_payload(
    config: AIConfig,
    selected_documents: list[dict[str, object]],
    document_hash: str = "",
    diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    configured = _provider_configured(config)
    enabled = _provider_enabled(config)
    reason = ""
    if not enabled:
        reason = config.provider_status_label
    elif not configured:
        reason = config.provider_status_label
    elif not selected_documents:
        reason = str((diagnostics or {}).get("final_reason") or "No hay documentos aptos para análisis IA")
    return {
        **config.public_status(),
        "has_summary": False,
        "summary": None,
        "job_status": "",
        "job": None,
        "selected_documents": selected_documents,
        "document_diagnostics": diagnostics or {},
        "document_hash": document_hash,
        "puede_generar": bool(config.analysis_provider != "disabled" and selected_documents),
        "motivo_si_no_puede_generar": reason,
    }


def get_ai_summary_payload(conn: sqlite3.Connection, licitacion_id: int) -> dict[str, object]:
    config = get_ai_config()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        raise ValueError("Licitacion no encontrada")
    selected, diagnostics = _select_documents(config, row)
    document_hash = hash_documents(selected) if selected else ""
    payload = _base_payload(config, selected, document_hash, diagnostics)
    summary = _latest_useful_summary(conn, licitacion_id, document_hash) if document_hash else None
    if summary is None:
        summary = _latest_useful_summary(conn, licitacion_id)
    job = active_job(conn, licitacion_id, document_hash, provider=config.analysis_provider) if document_hash else None
    if not job:
        job = latest_job(conn, licitacion_id, document_hash or None, provider=config.analysis_provider)
    payload.update(
        {
            "has_summary": summary is not None,
            "summary": _summary_payload(summary),
            "job_status": job["status"] if job else "",
            "job": _job_payload(job),
            "notification_status": notification_status_payload(
                notification_rows_for_job(conn, int(job["id"])) if job else latest_notification_rows_for_licitacion(conn, licitacion_id)
            ),
        }
    )
    return payload


def _payload_with_job_selection(
    conn: sqlite3.Connection,
    licitacion_id: int,
    job_row: sqlite3.Row,
    selected_documents: list[dict[str, object]],
) -> dict[str, object]:
    payload = get_ai_summary_payload(conn, licitacion_id)
    document_hash = str(job_row["document_hash"] or "")
    summary = _latest_useful_summary(conn, licitacion_id, document_hash) if document_hash else None
    refreshed_job = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_row["id"],)).fetchone() or job_row
    payload["selected_documents"] = selected_documents
    payload["document_hash"] = document_hash or str(payload.get("document_hash") or "")
    diagnostics = dict(payload.get("document_diagnostics") or {})
    diagnostics.update({"job_selection": True, "selected_files_count": len(selected_documents)})
    payload["document_diagnostics"] = diagnostics
    payload.update(
        {
            "has_summary": summary is not None,
            "summary": _summary_payload(summary),
            "job_status": refreshed_job["status"] if refreshed_job else "",
            "job": _job_payload(refreshed_job),
            "notification_status": notification_status_payload(
                notification_rows_for_job(conn, int(refreshed_job["id"])) if refreshed_job else []
            ),
        }
    )
    return payload


def delete_ai_summary(conn: sqlite3.Connection, licitacion_id: int) -> dict[str, object]:
    exists = conn.execute("SELECT id FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not exists:
        raise ValueError("Licitacion no encontrada")
    cur = conn.execute("DELETE FROM ai_summaries WHERE licitacion_id = ?", (licitacion_id,))
    dismissed_at = _now()
    jobs = conn.execute(
        """
        UPDATE ai_analysis_jobs
        SET dismissed_at = ?, dismissed_by = 'delete_ai_summary'
        WHERE licitacion_id = ? AND (dismissed_at IS NULL OR dismissed_at = '')
        """,
        (dismissed_at, licitacion_id),
    )
    payload = get_ai_summary_payload(conn, licitacion_id)
    payload["deleted_summaries"] = int(cur.rowcount or 0)
    payload["dismissed_jobs"] = int(jobs.rowcount or 0)
    return payload


def request_ai_analysis(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    requested_by: str = "",
    force: bool = False,
    selected_files: list[object] | None = None,
    provider_name: str | None = None,
    provider: ProviderProtocol | None = None,
    notify_on_completion: bool = False,
    notification_emails: list[object] | str | None = None,
) -> dict[str, object]:
    config = get_ai_config()
    if provider_name:
        config = type(config)(**{**config.__dict__, "analysis_provider": provider_name})
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        raise ValueError("Licitacion no encontrada")
    selected, diagnostics = _select_documents(config, row, selected_files)
    if diagnostics.get("manual_selection_error"):
        raise AIFileSelectionError(str(diagnostics.get("final_reason") or "Selección de ficheros no válida."))
    if not selected:
        return _base_payload(config, selected, diagnostics=diagnostics)
    normalized_notification_emails = normalize_email_list(notification_emails, required=notify_on_completion) if notify_on_completion else []
    document_hash = hash_documents(selected)
    if not force:
        summary = _latest_useful_summary(conn, licitacion_id, document_hash)
        if summary:
            payload = _base_payload(config, selected, document_hash, diagnostics)
            payload.update({"has_summary": True, "summary": _summary_payload(summary), "job_status": "completed"})
            return payload
        existing_job = active_job(conn, licitacion_id, document_hash, provider=config.analysis_provider)
        if existing_job:
            payload = _base_payload(config, selected, document_hash, diagnostics)
            payload.update({"job_status": existing_job["status"], "job": _job_payload(existing_job)})
            return payload

    job_id = create_job(
        conn,
        licitacion_id=licitacion_id,
        document_hash=document_hash,
        selected_documents=selected,
        model=_provider_model(config),
        provider=config.analysis_provider,
        requested_by=requested_by,
        status="pending",
    )
    notifications_count = 0
    if notify_on_completion:
        notifications_count = create_job_notifications(
            conn,
            job_id=job_id,
            licitacion_id=licitacion_id,
            requested_by=requested_by,
            recipients=normalized_notification_emails,
            created_at=_now(),
        )
    payload = _base_payload(config, selected, document_hash, diagnostics)
    job = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    payload.update(
        {
            "ok": True,
            "job_id": job_id,
            "job_status": "pending",
            "provider": config.analysis_provider,
            "message": "Análisis IA en cola.",
            "job": _job_payload(job),
            "notification_status": notification_status_payload(notification_rows_for_job(conn, job_id)),
            "notification_recipients_count": notifications_count,
        }
    )
    return payload


def process_ai_job(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    provider: ProviderProtocol | None = None,
    notification_sender: Callable[[sqlite3.Connection, int], object] | None = None,
) -> dict[str, object]:
    config = get_ai_config()
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job IA no encontrado")
    initial_status = str(row["status"] or "")
    if initial_status not in {"pending", "queued", "deferred", "processing"}:
        return _payload_with_job_selection(conn, int(row["licitacion_id"]), row, json.loads(row["selected_documents_json"] or "[]"))
    if initial_status == "processing":
        return _payload_with_job_selection(conn, int(row["licitacion_id"]), row, json.loads(row["selected_documents_json"] or "[]"))
    if initial_status in {"pending", "queued", "deferred"}:
        claimed = claim_pending_job(conn, job_id, started_at=_now())
        if not claimed:
            row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
            if row and int(row["cancel_requested"] or 0):
                selected = json.loads(row["selected_documents_json"] or "[]")
                _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de ejecutar el proveedor IA.")
                return _payload_with_job_selection(conn, int(row["licitacion_id"]), row, selected)
            return _payload_with_job_selection(conn, int(row["licitacion_id"]), row, json.loads(row["selected_documents_json"] or "[]"))
        row = claimed
        _commit_if_possible(conn)
    licitacion_id = int(row["licitacion_id"])
    job_provider = str(row["provider"] or config.analysis_provider or "gemini")
    if job_provider != config.analysis_provider:
        config = type(config)(**{**config.__dict__, "analysis_provider": job_provider})
    licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not licitacion:
        raise ValueError("Licitacion no encontrada")

    if not _provider_enabled(config) or not _provider_configured(config):
        status, error_code, error_message = _provider_unavailable(config)
        update_job(
            conn,
            job_id,
            status=status,
            finished_at=_now(),
            progress_stage="error",
            progress_message=error_message,
            heartbeat_at=_now(),
            error_code=error_code,
            error_message=error_message,
        )
        if status == "error":
            mark_job_notifications_skipped(conn, job_id, "El análisis IA no pudo ejecutarse.", now=_now)
        selected = json.loads(row["selected_documents_json"] or "[]")
        return _payload_with_job_selection(conn, licitacion_id, row, selected)

    selected = json.loads(row["selected_documents_json"] or "[]")
    if int(row["cancel_requested"] or 0) or _is_cancel_requested(conn, job_id):
        _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de ejecutar el proveedor IA.")
        return _payload_with_job_selection(conn, licitacion_id, row, selected)
    if config.analysis_provider == "gemini":
        limit = check_rate_limit(conn, config)
        if not limit.allowed:
            update_job(
                conn,
                job_id,
                status="deferred",
                progress_stage="queued",
                progress_message=limit.reason,
                error_code="RATE_LIMIT",
                error_message=limit.reason,
                next_retry_at=limit.retry_at,
            )
            return _payload_with_job_selection(conn, licitacion_id, row, selected)

    active_provider = provider or (CodexLocalProvider(config, job_id=job_id) if config.analysis_provider == "codex_local" else GeminiProvider(config))
    try:
        touch_job_progress(
            conn,
            job_id,
            stage="running_codex" if config.analysis_provider == "codex_local" else "launching_provider",
            message="Ejecutando Codex Local" if config.analysis_provider == "codex_local" else "Consultando proveedor IA",
            percent=30,
        )
        _commit_if_possible(conn)
        if _is_cancel_requested(conn, job_id):
            _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de ejecutar el proveedor IA.")
            return _payload_with_job_selection(conn, licitacion_id, row, selected)
        result = active_provider.analyze_documents(dict(licitacion), selected)
        if _is_cancel_requested(conn, job_id):
            _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de guardar la ficha IA.")
            return _payload_with_job_selection(conn, licitacion_id, row, selected)
        touch_job_progress(conn, job_id, stage="validating_result", message="Validando resultado IA", percent=85)
        summary = postprocess_summary(parse_summary_json(result.summary))
    except AISchemaError as exc:
        record_usage(conn, provider=config.analysis_provider, model=_provider_model(config), status="error", error_code="INVALID_JSON", licitacion_id=licitacion_id, job_id=job_id)
        update_job(conn, job_id, status="error", finished_at=_now(), progress_stage="error", progress_message=str(exc), heartbeat_at=_now(), error_code="INVALID_JSON", error_message=str(exc))
        mark_job_notifications_skipped(conn, job_id, "El análisis IA finalizó con error.", now=_now)
        return _payload_with_job_selection(conn, licitacion_id, row, selected)
    except AIProviderError as exc:
        status = "deferred" if exc.code == "RESOURCE_EXHAUSTED" else "error"
        record_usage(conn, provider=config.analysis_provider, model=_provider_model(config), status="error", error_code=exc.code, licitacion_id=licitacion_id, job_id=job_id)
        retry_at = ""
        if exc.code == "RESOURCE_EXHAUSTED":
            retry_at = (datetime.now().replace(microsecond=0) + timedelta(minutes=config.cooldown_on_429_minutes)).isoformat()
        safe_diagnostics = {"diagnostics": exc.diagnostics} if exc.diagnostics else {}
        update_job(
            conn,
            job_id,
            status=status,
            finished_at=_now(),
            progress_stage="error" if status == "error" else "queued",
            progress_message=str(exc),
            heartbeat_at=_now(),
            error_code=exc.code,
            error_message=str(exc),
            next_retry_at=retry_at,
            raw_usage_json=json.dumps(safe_diagnostics, ensure_ascii=False) if safe_diagnostics else "",
        )
        if status == "error":
            mark_job_notifications_skipped(conn, job_id, "El análisis IA finalizó con error.", now=_now)
        return _payload_with_job_selection(conn, licitacion_id, row, selected)

    raw_usage = result.raw_usage or {}
    if _is_cancel_requested(conn, job_id):
        _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de guardar la ficha IA.")
        return _payload_with_job_selection(conn, licitacion_id, row, selected)
    touch_job_progress(conn, job_id, stage="validating_result", message="Comprobando calidad de la ficha IA", percent=88)
    quality_check = summary_quality_check(summary)
    raw_usage["quality_check"] = quality_check
    if not quality_check["is_useful"]:
        error_code, error_message = _quality_error(quality_check)
        record_usage(conn, provider=config.analysis_provider, model=_provider_model(config), status="error", error_code=error_code, licitacion_id=licitacion_id, job_id=job_id)
        update_job(
            conn,
            job_id,
            status="error",
            finished_at=_now(),
            progress_stage="error",
            progress_message=error_message,
            heartbeat_at=_now(),
            error_code=error_code,
            error_message=error_message,
            raw_usage_json=json.dumps(raw_usage, ensure_ascii=False),
        )
        mark_job_notifications_skipped(conn, job_id, "El análisis IA finalizó sin resumen útil.", now=_now)
        return _payload_with_job_selection(conn, licitacion_id, row, selected)

    if _is_cancel_requested(conn, job_id):
        _mark_cancelled(conn, job_id, message="Cancelado por el usuario antes de guardar la ficha IA.")
        return _payload_with_job_selection(conn, licitacion_id, row, selected)
    touch_job_progress(conn, job_id, stage="saving_summary", message="Guardando ficha IA", percent=95)
    save_summary(
        conn,
        licitacion_id=licitacion_id,
        document_hash=row["document_hash"],
        model=_provider_model(config),
        summary=summary,
        text=summary_text(summary),
        job_id=job_id,
        provider=config.analysis_provider,
    )
    record_usage(
        conn,
        provider=config.analysis_provider,
        model=_provider_model(config),
        status="completed",
        tokens_input=_usage_value(raw_usage, "prompt_token_count", "input_token_count"),
        tokens_output=_usage_value(raw_usage, "candidates_token_count", "output_token_count"),
        tokens_total=_usage_value(raw_usage, "total_token_count"),
        licitacion_id=licitacion_id,
        job_id=job_id,
    )
    update_job(
        conn,
        job_id,
        status="completed",
        finished_at=_now(),
        progress_stage="completed",
        progress_message="Ficha IA guardada.",
        progress_percent=100,
        heartbeat_at=_now(),
        error_code="",
        error_message="",
        raw_usage_json=json.dumps(raw_usage, ensure_ascii=False),
    )
    if notification_sender:
        notification_sender(conn, job_id)
    else:
        send_pending_job_notifications(
            conn,
            job_id,
            now=_now,
            smtp_factory=smtplib.SMTP,
            smtp_ssl_factory=smtplib.SMTP_SSL,
        )
    return _payload_with_job_selection(conn, licitacion_id, row, selected)


def list_ai_jobs(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT j.*, l.expediente, l.objeto
        FROM ai_analysis_jobs j
        LEFT JOIN licitaciones l ON l.id = j.licitacion_id
        ORDER BY j.created_at DESC, j.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_queue_job_item(row) for row in rows]


def _queue_job_item(row: sqlite3.Row) -> dict[str, object]:
    payload = _job_payload(row) or {}
    payload.update(
        {
            "licitacion_id": row["licitacion_id"],
            "expediente": row["expediente"] or "",
            "titulo_corto": str(row["objeto"] or "")[:120],
            "can_cancel": str(row["status"] or "") in {"pending", "queued", "deferred", "processing"},
            "can_retry": str(row["status"] or "") in {"error", "deferred", "cancelled"},
            "can_open": row["licitacion_id"] is not None,
        }
    )
    return payload


def get_ai_queue_payload(conn: sqlite3.Connection, limit: int = 30) -> dict[str, object]:
    rows = conn.execute(
        """
        SELECT j.*, l.expediente, l.objeto
        FROM ai_analysis_jobs j
        LEFT JOIN licitaciones l ON l.id = j.licitacion_id
        WHERE (j.dismissed_at IS NULL OR j.dismissed_at = '')
        ORDER BY
          CASE WHEN j.status IN ('pending', 'queued', 'processing', 'deferred') THEN 0 ELSE 1 END,
          COALESCE(j.started_at, j.created_at) DESC,
          j.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    items = [_queue_job_item(row) for row in rows]
    for item in items:
        item["notification_status"] = notification_status_payload(notification_rows_for_job(conn, int(item["id"])))
    active = [item for item in items if item["status"] in {"pending", "queued", "processing", "deferred"}]
    recent = [item for item in items if item["status"] not in {"pending", "queued", "processing", "deferred"}]
    counts = {
        "pending": sum(1 for item in items if item["status"] in {"pending", "queued", "deferred"}),
        "processing": sum(1 for item in items if item["status"] == "processing"),
        "completed_recent": sum(1 for item in items if item["status"] == "completed"),
        "error_recent": sum(1 for item in items if item["status"] == "error"),
        "active": len(active),
    }
    return {"active_jobs": active, "recent_jobs": recent, "counts": counts, "now": queue_now_iso()}


def cancel_ai_job(conn: sqlite3.Connection, job_id: int) -> dict[str, object]:
    result = cancel_job(conn, job_id)
    if not result.get("ok"):
        return result
    payload = get_ai_job_payload(conn, job_id)
    payload.update(result)
    return payload


def dismiss_ai_job(conn: sqlite3.Connection, job_id: int, dismissed_by: str = "") -> dict[str, object]:
    return dismiss_job(conn, job_id, dismissed_by=dismissed_by)


def dismiss_finished_ai_jobs(conn: sqlite3.Connection, dismissed_by: str = "") -> dict[str, object]:
    return dismiss_finished_jobs(conn, dismissed_by=dismissed_by)


def mark_stale_ai_jobs(conn: sqlite3.Connection, *, timeout_seconds: int) -> dict[str, object]:
    count = mark_stale_jobs_in_conn(conn, processing_timeout_seconds=timeout_seconds + 120)
    return {"ok": True, "marked": count}


def get_ai_job_payload(conn: sqlite3.Connection, job_id: int) -> dict[str, object]:
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job IA no encontrado")
    return {"job": _job_payload(row), "job_status": row["status"], "job_id": job_id}
