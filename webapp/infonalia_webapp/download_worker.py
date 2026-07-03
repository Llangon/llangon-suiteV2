from __future__ import annotations

import argparse
import pprint
from typing import Any


def process_jobs(*, job_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    try:
        from . import app
    except ImportError:
        import app  # type: ignore

    results: list[dict[str, object]] = []
    processed = 0
    with app.db_session() as conn:
        if job_id is not None:
            rows = conn.execute("SELECT id FROM download_jobs WHERE id = ?", (job_id,)).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id
                FROM download_jobs
                WHERE status = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (app.DOWNLOAD_JOB_STATUS_PENDING, int(limit)),
            ).fetchall()
    for row in rows:
        result = app.process_download_job(int(row["id"]))
        results.append(result)
        if result.get("ok"):
            processed += 1
    return {"job_id": job_id, "processed": processed, "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Procesa trabajos pendientes de descarga documental.")
    parser.add_argument("--once", action="store_true", help="Procesa los trabajos pendientes una sola vez.")
    parser.add_argument("--job-id", type=int, help="Procesa solo un trabajo concreto.")
    parser.add_argument("--limit", type=int, default=10, help="Límite máximo de trabajos en una pasada.")
    args = parser.parse_args(argv)

    if not args.once:
        parser.error("Usa --once.")
    if args.limit < 1:
        parser.error("--limit debe ser mayor que 0.")

    payload = process_jobs(job_id=args.job_id, limit=args.limit)
    pprint.pp(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
