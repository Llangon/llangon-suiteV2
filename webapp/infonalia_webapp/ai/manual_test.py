from __future__ import annotations

import argparse
import json

__test__ = False

try:
    from .. import app
    from .service import get_ai_summary_payload, request_ai_analysis
except ImportError:  # pragma: no cover - soporte para ejecucion directa/coleccion externa
    from webapp.infonalia_webapp import app
    from webapp.infonalia_webapp.ai.service import get_ai_summary_payload, request_ai_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba manual controlada de analisis IA Gemini.")
    parser.add_argument("--licitacion-id", type=int, required=True)
    parser.add_argument("--generate", action="store_true", help="Crear/procesar job si esta configurado.")
    parser.add_argument("--force", action="store_true", help="Regenerar aunque ya exista un resumen para los documentos actuales.")
    args = parser.parse_args()

    app.init_db()
    with app.db_session() as conn:
        if args.generate or args.force:
            payload = request_ai_analysis(conn, args.licitacion_id, requested_by="manual_test", force=args.force)
        else:
            payload = get_ai_summary_payload(conn, args.licitacion_id)
    safe_payload = dict(payload)
    safe_payload.pop("summary", None)
    job = safe_payload.get("job") or {}
    if isinstance(job, dict):
        safe_payload["summary_quality_status"] = job.get("summary_quality_status", "")
        safe_payload["sent_documents_count"] = job.get("sent_documents_count", 0)
        safe_payload["sent_documents_names"] = job.get("sent_documents_names", [])
        safe_payload["total_pdf_bytes_sent"] = job.get("total_pdf_bytes_sent", 0)
        safe_payload["response_text_length"] = job.get("response_text_length", 0)
        safe_payload["usage_metadata"] = job.get("usage_metadata", {})
        safe_payload["empty_analysis_rejected"] = job.get("error_code") == "EMPTY_ANALYSIS"
    print(json.dumps(safe_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
