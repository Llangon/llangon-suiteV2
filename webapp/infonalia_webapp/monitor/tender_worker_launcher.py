from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .tender_repository import update_cycle_worker_with_retry


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def launch_tender_monitor_worker(
    cycle_id: int,
    *,
    db_path: str | Path,
    root: str | Path | None = None,
) -> dict[str, object]:
    log_directory = REPOSITORY_ROOT / "runtime" / "monitor-workers"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"cycle-{int(cycle_id)}.log"
    stored_log_path = str(log_path.relative_to(REPOSITORY_ROOT))
    command = [
        sys.executable,
        "-u",
        "-m",
        "webapp.infonalia_webapp.monitor.tender_worker",
        "--cycle-id",
        str(int(cycle_id)),
        "--db",
        str(db_path),
        "--log-path",
        stored_log_path,
    ]
    if root:
        command.extend(["--root", str(root)])
    log_handle = log_path.open("ab")
    kwargs: dict[str, object] = {
        "cwd": str(REPOSITORY_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "shell": False,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(command, **kwargs)
    except Exception as exc:
        log_handle.close()
        return {"ok": False, "error": f"No se pudo iniciar el worker del monitor: {exc}"}
    finally:
        log_handle.close()
    telemetry_saved = update_cycle_worker_with_retry(
        db_path,
        cycle_id,
        launcher_pid=process.pid,
        log_path=stored_log_path,
    )
    return {
        "ok": True,
        "pid": process.pid,
        "cycle_id": int(cycle_id),
        "log_path": stored_log_path,
        "telemetry_saved": telemetry_saved,
    }
