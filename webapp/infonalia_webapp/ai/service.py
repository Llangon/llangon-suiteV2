from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Protocol

from .config import AIConfig, get_ai_config
from .document_selector import inspect_document_selection
from .gemini_provider import AIProviderError, GeminiProvider, ProviderResult
from .hashing import hash_documents
from .queue import (
    active_job,
    create_job,
    latest_job,
    latest_summary,
    record_usage,
    row_to_dict,
    save_summary,
    update_job,
)
from .rate_limit import check_rate_limit
from .schemas import AISchemaError, parse_summary_json, summary_quality_check, summary_text


class ProviderProtocol(Protocol):
    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        ...


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


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
    if str(row["quality_status"] or "") == "empty_analysis":
        return False
    try:
        raw_summary = json.loads(str(row["summary_json"] or "{}"))
        quality = summary_quality_check(parse_summary_json(raw_summary))
    except Exception:
        return True
    if quality["is_useful"]:
        return True
    conn.execute("UPDATE ai_summaries SET quality_status = 'empty_analysis', updated_at = ? WHERE id = ?", (_now(), row["id"]))
    return False


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
    return {
        "id": data["id"],
        "status": data["status"],
        "document_hash": data["document_hash"],
        "model": data.get("model") or "",
        "created_at": data.get("created_at") or "",
        "started_at": data.get("started_at") or "",
        "finished_at": data.get("finished_at") or "",
        "error_code": data.get("error_code") or "",
        "error_message": data.get("error_message") or "",
        "next_retry_at": data.get("next_retry_at") or "",
        "attempts": data.get("attempts") or 0,
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


def _select_documents(config: AIConfig, row: sqlite3.Row) -> tuple[list[dict[str, object]], dict[str, object]]:
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
    configured = config.configured
    reason = ""
    if not config.enabled:
        reason = "IA desactivada"
    elif not configured:
        reason = "IA no configurada"
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
        "puede_generar": bool(config.enabled and configured and selected_documents),
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
    summary = _latest_useful_summary(conn, licitacion_id, document_hash) if document_hash else _latest_useful_summary(conn, licitacion_id)
    job = active_job(conn, licitacion_id, document_hash) if document_hash else None
    if not job:
        job = latest_job(conn, licitacion_id, document_hash or None)
    payload.update(
        {
            "has_summary": summary is not None,
            "summary": _summary_payload(summary),
            "job_status": job["status"] if job else "",
            "job": _job_payload(job),
        }
    )
    return payload


def request_ai_analysis(
    conn: sqlite3.Connection,
    licitacion_id: int,
    *,
    requested_by: str = "",
    force: bool = False,
    provider: ProviderProtocol | None = None,
) -> dict[str, object]:
    config = get_ai_config()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        raise ValueError("Licitacion no encontrada")
    selected, diagnostics = _select_documents(config, row)
    if not selected:
        return _base_payload(config, selected, diagnostics=diagnostics)
    document_hash = hash_documents(selected)
    if not force:
        summary = _latest_useful_summary(conn, licitacion_id, document_hash)
        if summary:
            payload = _base_payload(config, selected, document_hash, diagnostics)
            payload.update({"has_summary": True, "summary": _summary_payload(summary), "job_status": "completed"})
            return payload
        existing_job = active_job(conn, licitacion_id, document_hash)
        if existing_job:
            payload = _base_payload(config, selected, document_hash, diagnostics)
            payload.update({"job_status": existing_job["status"], "job": _job_payload(existing_job)})
            return payload

    if not config.enabled or not config.configured:
        job_id = create_job(
            conn,
            licitacion_id=licitacion_id,
            document_hash=document_hash,
            selected_documents=selected,
            model=config.model,
            requested_by=requested_by,
            status="disabled",
            error_code="DISABLED" if not config.enabled else "NOT_CONFIGURED",
            error_message="IA desactivada" if not config.enabled else "Gemini no esta configurado.",
        )
        payload = _base_payload(config, selected, document_hash, diagnostics)
        job = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
        payload.update({"job_status": "disabled", "job": _job_payload(job)})
        return payload

    job_id = create_job(
        conn,
        licitacion_id=licitacion_id,
        document_hash=document_hash,
        selected_documents=selected,
        model=config.model,
        requested_by=requested_by,
    )
    return process_ai_job(conn, job_id, provider=provider)


def process_ai_job(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    provider: ProviderProtocol | None = None,
) -> dict[str, object]:
    config = get_ai_config()
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job IA no encontrado")
    licitacion_id = int(row["licitacion_id"])
    licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not licitacion:
        raise ValueError("Licitacion no encontrada")

    if not config.enabled or not config.configured:
        update_job(
            conn,
            job_id,
            status="disabled",
            finished_at=_now(),
            error_code="DISABLED" if not config.enabled else "NOT_CONFIGURED",
            error_message="IA desactivada" if not config.enabled else "Gemini no esta configurado.",
        )
        return get_ai_summary_payload(conn, licitacion_id)

    selected = json.loads(row["selected_documents_json"] or "[]")
    limit = check_rate_limit(conn, config)
    if not limit.allowed:
        update_job(
            conn,
            job_id,
            status="deferred",
            error_code="RATE_LIMIT",
            error_message=limit.reason,
            next_retry_at=limit.retry_at,
        )
        return get_ai_summary_payload(conn, licitacion_id)

    started_at = _now()
    update_job(conn, job_id, status="processing", started_at=started_at, attempts=int(row["attempts"] or 0) + 1)
    active_provider = provider or GeminiProvider(config)
    try:
        result = active_provider.analyze_documents(dict(licitacion), selected)
        summary = parse_summary_json(result.summary)
    except AISchemaError as exc:
        record_usage(conn, model=config.model, status="error", error_code="INVALID_JSON", licitacion_id=licitacion_id, job_id=job_id)
        update_job(conn, job_id, status="error", finished_at=_now(), error_code="INVALID_JSON", error_message=str(exc))
        return get_ai_summary_payload(conn, licitacion_id)
    except AIProviderError as exc:
        status = "deferred" if exc.code == "RESOURCE_EXHAUSTED" else "error"
        record_usage(conn, model=config.model, status="error", error_code=exc.code, licitacion_id=licitacion_id, job_id=job_id)
        retry_at = ""
        if exc.code == "RESOURCE_EXHAUSTED":
            retry_at = (datetime.now().replace(microsecond=0) + timedelta(minutes=config.cooldown_on_429_minutes)).isoformat()
        safe_diagnostics = {"diagnostics": exc.diagnostics} if exc.diagnostics else {}
        update_job(
            conn,
            job_id,
            status=status,
            finished_at=_now(),
            error_code=exc.code,
            error_message=str(exc),
            next_retry_at=retry_at,
            raw_usage_json=json.dumps(safe_diagnostics, ensure_ascii=False) if safe_diagnostics else "",
        )
        return get_ai_summary_payload(conn, licitacion_id)

    raw_usage = result.raw_usage or {}
    quality_check = summary_quality_check(summary)
    raw_usage["quality_check"] = quality_check
    if not quality_check["is_useful"]:
        record_usage(conn, model=config.model, status="error", error_code="EMPTY_ANALYSIS", licitacion_id=licitacion_id, job_id=job_id)
        update_job(
            conn,
            job_id,
            status="error",
            finished_at=_now(),
            error_code="EMPTY_ANALYSIS",
            error_message="Gemini devolvió un JSON válido pero sin contenido útil.",
            raw_usage_json=json.dumps(raw_usage, ensure_ascii=False),
        )
        return get_ai_summary_payload(conn, licitacion_id)

    save_summary(
        conn,
        licitacion_id=licitacion_id,
        document_hash=row["document_hash"],
        model=config.model,
        summary=summary,
        text=summary_text(summary),
        job_id=job_id,
    )
    record_usage(
        conn,
        model=config.model,
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
        error_code="",
        error_message="",
        raw_usage_json=json.dumps(raw_usage, ensure_ascii=False),
    )
    return get_ai_summary_payload(conn, licitacion_id)


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
    return [dict(row) for row in rows]
