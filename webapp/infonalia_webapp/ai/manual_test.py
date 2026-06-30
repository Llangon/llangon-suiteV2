from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime

__test__ = False

try:
    from .. import app
    from .config import get_ai_config
    from .document_selector import inspect_document_selection
    from .hashing import hash_documents
    from .pdf_text_extractor import extract_pdf_text
    from .queue import active_job, create_job, latest_summary, record_usage, update_job
    from .service import get_ai_summary_payload, process_ai_job
except ImportError:  # pragma: no cover - soporte para ejecucion directa/coleccion externa
    from webapp.infonalia_webapp import app
    from webapp.infonalia_webapp.ai.config import get_ai_config
    from webapp.infonalia_webapp.ai.document_selector import inspect_document_selection
    from webapp.infonalia_webapp.ai.hashing import hash_documents
    from webapp.infonalia_webapp.ai.pdf_text_extractor import extract_pdf_text
    from webapp.infonalia_webapp.ai.queue import active_job, create_job, latest_summary, record_usage, update_job
    from webapp.infonalia_webapp.ai.service import get_ai_summary_payload, process_ai_job


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def build_preflight_report(
    *,
    job_id: int,
    model: str,
    selected_documents: list[dict[str, object]],
    timeout_seconds: int,
    input_mode: str = "",
    extraction_diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "modelo": model,
        "input_mode": input_mode,
        "documentos": [str(item.get("name") or item.get("relative_path") or "Documento") for item in selected_documents],
        "sent_documents_count": len(selected_documents),
        "total_pdf_bytes_sent": sum(int(item.get("size_bytes") or 0) for item in selected_documents),
        "extraction_diagnostics": extraction_diagnostics or {},
        "GEMINI_TIMEOUT_SECONDS": timeout_seconds,
        "mensaje": "Llamando a Gemini...",
    }


def build_extraction_preflight(selected_documents: list[dict[str, object]], config) -> dict[str, object]:
    if config.input_mode not in {"text", "auto"}:
        return {}
    try:
        return extract_pdf_text(
            selected_documents,
            max_total_chars=config.max_extracted_chars,
            max_chars_per_document=config.max_chars_per_document,
        ).diagnostics
    except Exception as exc:
        return {
            "documents_text_extracted_count": 0,
            "extracted_chars_total": 0,
            "extraction_warnings": [f"No se pudo preparar diagnostico de extraccion ({type(exc).__name__})."],
        }


def mark_interrupted_job(conn, job_id: int, *, message: str = "Prueba manual interrumpida por el usuario.") -> bool:
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row or row["status"] not in {"pending", "processing"}:
        return False
    update_job(
        conn,
        job_id,
        status="error",
        finished_at=_now(),
        error_code="INTERRUPTED",
        error_message=message,
        raw_usage_json=json.dumps({"diagnostics": {"interrupted": True}}, ensure_ascii=False),
    )
    record_usage(
        conn,
        model=row["model"] or "",
        status="error",
        error_code="INTERRUPTED",
        licitacion_id=int(row["licitacion_id"]),
        job_id=job_id,
    )
    return True


def _prepare_manual_job(conn, licitacion_id: int, *, force: bool) -> tuple[int, dict[str, object] | None]:
    config = get_ai_config()
    row = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not row:
        raise ValueError("Licitacion no encontrada")
    selection = inspect_document_selection(
        row,
        max_documents=config.max_documents_per_analysis,
        max_file_mb=config.max_file_mb,
    )
    selected = list(selection["selected_documents"])
    if not selected or not config.enabled or not config.configured:
        return 0, get_ai_summary_payload(conn, licitacion_id)

    document_hash = hash_documents(selected)
    if not force and latest_summary(conn, licitacion_id, document_hash):
        return 0, get_ai_summary_payload(conn, licitacion_id)

    existing = None if force else active_job(conn, licitacion_id, document_hash)
    if existing:
        return int(existing["id"]), None

    return (
        create_job(
            conn,
            licitacion_id=licitacion_id,
            document_hash=document_hash,
            selected_documents=selected,
            model=config.model,
            requested_by="manual_test",
        ),
        None,
    )


def _safe_payload(payload: dict[str, object]) -> dict[str, object]:
    safe_payload = dict(payload)
    safe_payload.pop("summary", None)
    job = safe_payload.get("job") or {}
    if isinstance(job, dict):
        safe_payload["summary_quality_status"] = job.get("summary_quality_status", "")
        safe_payload["sent_documents_count"] = job.get("sent_documents_count", 0)
        safe_payload["sent_documents_names"] = job.get("sent_documents_names", [])
        safe_payload["total_pdf_bytes_sent"] = job.get("total_pdf_bytes_sent", 0)
        safe_payload["input_mode_used"] = job.get("input_mode_used", "")
        safe_payload["documents_text_extracted_count"] = job.get("documents_text_extracted_count", 0)
        safe_payload["extracted_chars_total"] = job.get("extracted_chars_total", 0)
        safe_payload["extracted_chars_by_document"] = job.get("extracted_chars_by_document", {})
        safe_payload["pages_processed_by_document"] = job.get("pages_processed_by_document", {})
        safe_payload["extraction_warnings"] = job.get("extraction_warnings", [])
        safe_payload["response_text_length"] = job.get("response_text_length", 0)
        safe_payload["duration_seconds"] = job.get("duration_seconds", 0)
        safe_payload["timeout_seconds"] = job.get("timeout_seconds", 0)
        safe_payload["usage_metadata"] = job.get("usage_metadata", {})
        safe_payload["empty_analysis_rejected"] = job.get("error_code") == "EMPTY_ANALYSIS"
        safe_payload["interrupted"] = job.get("error_code") == "INTERRUPTED"
    return safe_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba manual controlada de analisis IA Gemini.")
    parser.add_argument("--licitacion-id", type=int, required=True)
    parser.add_argument("--generate", action="store_true", help="Crear/procesar job si esta configurado.")
    parser.add_argument("--force", action="store_true", help="Regenerar aunque ya exista un resumen para los documentos actuales.")
    parser.add_argument("--timeout", type=int, help="Sobrescribe temporalmente GEMINI_TIMEOUT_SECONDS para esta prueba.")
    parser.add_argument("--input-mode", choices=("text", "pdf_inline", "auto"), help="Sobrescribe temporalmente GEMINI_INPUT_MODE para esta prueba.")
    parser.add_argument("--debug", action="store_true", help="Muestra traceback completo si se interrumpe la prueba.")
    args = parser.parse_args()

    if args.timeout:
        os.environ["GEMINI_TIMEOUT_SECONDS"] = str(max(1, args.timeout))
    if args.input_mode:
        os.environ["GEMINI_INPUT_MODE"] = args.input_mode

    app.init_db()
    job_id = 0
    started = time.perf_counter()
    with app.db_session() as conn:
        try:
            if args.generate or args.force:
                job_id, payload = _prepare_manual_job(conn, args.licitacion_id, force=args.force)
                if job_id:
                    job = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
                    selected = json.loads(job["selected_documents_json"] or "[]") if job else []
                    config = get_ai_config()
                    print(json.dumps(build_preflight_report(
                        job_id=job_id,
                        model=config.model,
                        selected_documents=selected,
                        timeout_seconds=config.timeout_seconds,
                        input_mode=config.input_mode,
                        extraction_diagnostics=build_extraction_preflight(selected, config),
                    ), ensure_ascii=False, indent=2))
                    payload = process_ai_job(conn, job_id)
                elif payload is None:
                    payload = get_ai_summary_payload(conn, args.licitacion_id)
            else:
                payload = get_ai_summary_payload(conn, args.licitacion_id)
        except KeyboardInterrupt:
            if job_id:
                mark_interrupted_job(conn, job_id)
            print("\nPrueba interrumpida por el usuario. El job se ha marcado como INTERRUPTED.")
            if args.debug:
                conn.commit()
                raise
            payload = get_ai_summary_payload(conn, args.licitacion_id)

    safe_payload = _safe_payload(payload)
    safe_payload["manual_test_duration_seconds"] = round(time.perf_counter() - started, 3)
    print(json.dumps(safe_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
