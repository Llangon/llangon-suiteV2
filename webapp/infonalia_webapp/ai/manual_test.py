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
    args = parser.parse_args()

    app.init_db()
    with app.db_session() as conn:
        if args.generate:
            payload = request_ai_analysis(conn, args.licitacion_id, requested_by="manual_test")
        else:
            payload = get_ai_summary_payload(conn, args.licitacion_id)
    safe_payload = dict(payload)
    safe_payload.pop("summary", None)
    print(json.dumps(safe_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
