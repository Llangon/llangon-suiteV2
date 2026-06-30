from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .queue import update_job


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOG_ROOT = REPOSITORY_ROOT / "runtime" / "logs"


def worker_log_path(job_id: int) -> Path:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    return LOG_ROOT / f"ai_worker_{job_id}.log"


def start_ai_worker_for_job(conn, job_id: int) -> dict[str, object]:
    log_path = worker_log_path(job_id)
    command = [
        sys.executable,
        "-m",
        "webapp.infonalia_webapp.ai.worker",
        "--job-id",
        str(job_id),
    ]
    try:
        handle = log_path.open("ab")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(REPOSITORY_ROOT),
                stdout=handle,
                stderr=subprocess.STDOUT,
                shell=False,
                close_fds=True,
            )
        finally:
            handle.close()
    except Exception as exc:
        update_job(
            conn,
            job_id,
            status="error",
            error_code="WORKER_START_ERROR",
            error_message=f"No se pudo iniciar el worker IA: {exc}",
        )
        return {"ok": False, "error_code": "WORKER_START_ERROR", "error_message": str(exc), "log_path": str(log_path)}
    return {"ok": True, "pid": process.pid, "log_path": str(log_path)}
