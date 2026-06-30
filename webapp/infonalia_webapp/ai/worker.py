from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from ..app import db_session
except ImportError:  # pragma: no cover
    from webapp.infonalia_webapp.app import db_session

from .config import get_ai_config
from .queue import mark_stale_jobs_in_conn, next_pending_job, update_job
from .service import process_ai_job


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOG_ROOT = REPOSITORY_ROOT / "runtime" / "logs"
LOG_ROOT.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("llangon.ai.worker")


def configure_logging(job_id: int | None = None) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    paths = [LOG_ROOT / "ai_worker.log"]
    if job_id is not None:
        paths.append(LOG_ROOT / f"ai_worker_{job_id}.log")
    handlers: list[logging.Handler] = []
    for path in paths:
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def processing_stale_before() -> str:
    config = get_ai_config()
    timeout = max(config.timeout_seconds, config.codex_timeout_seconds) + 120
    return (datetime.now().replace(microsecond=0) - timedelta(seconds=timeout)).isoformat()


def mark_stale_jobs() -> int:
    config = get_ai_config()
    timeout = max(config.timeout_seconds, config.codex_timeout_seconds) + 120
    with db_session() as conn:
        return mark_stale_jobs_in_conn(conn, processing_timeout_seconds=timeout)


def process_one_job(job_id: int | None = None) -> dict[str, object] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone() if job_id else next_pending_job(conn)
        if not row:
            LOGGER.info("No hay jobs IA pendientes.")
            return None
        job_id = int(row["id"])
        LOGGER.info("Inicio worker IA job_id=%s provider=%s status=%s", job_id, row["provider"], row["status"])
        update_job(
            conn,
            job_id,
            worker_pid=os.getpid(),
            heartbeat_at=_now(),
            progress_message="Worker iniciado.",
        )
        started = datetime.now()
        try:
            payload = process_ai_job(conn, job_id)
        except Exception as exc:
            LOGGER.exception("Error no controlado procesando job IA job_id=%s", job_id)
            update_job(
                conn,
                job_id,
                status="error",
                finished_at=_now(),
                progress_stage="error",
                progress_message=f"Error no controlado en worker IA: {type(exc).__name__}",
                heartbeat_at=_now(),
                error_code="WORKER_ERROR",
                error_message=f"Error no controlado en worker IA: {type(exc).__name__}",
            )
            payload = {"job_id": job_id, "job_status": "error", "error_code": "WORKER_ERROR"}
        duration = (datetime.now() - started).total_seconds()
        job = payload.get("job") if isinstance(payload, dict) else {}
        LOGGER.info(
            "Fin worker IA job_id=%s status=%s error_code=%s duration=%ss",
            job_id,
            payload.get("job_status") if isinstance(payload, dict) else "",
            job.get("error_code") if isinstance(job, dict) else "",
            round(duration, 2),
        )
        return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker de analisis IA documental Llangon Suite.")
    parser.add_argument("--once", action="store_true", help="Procesa el siguiente job pendiente y termina.")
    parser.add_argument("--job-id", type=int, help="Procesa un job IA concreto.")
    parser.add_argument("--mark-stale", action="store_true", help="Marca jobs processing antiguos como atascados.")
    args = parser.parse_args(argv)
    configure_logging(args.job_id)

    if args.mark_stale:
        count = mark_stale_jobs()
        LOGGER.info("Jobs IA atascados marcados: %s", count)
        return 0

    if args.job_id:
        process_one_job(args.job_id)
        return 0

    process_one_job(None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
