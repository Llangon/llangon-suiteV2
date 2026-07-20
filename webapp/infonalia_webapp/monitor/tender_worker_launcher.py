from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def launch_tender_monitor_worker(
    cycle_id: int,
    *,
    db_path: str | Path,
    root: str | Path | None = None,
) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "webapp.infonalia_webapp.monitor.tender_worker",
        "--cycle-id",
        str(int(cycle_id)),
        "--db",
        str(db_path),
    ]
    if root:
        command.extend(["--root", str(root)])
    kwargs: dict[str, object] = {
        "cwd": str(REPOSITORY_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": False,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(command, **kwargs)
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo iniciar el worker del monitor: {exc}"}
    return {"ok": True, "pid": process.pid, "cycle_id": int(cycle_id)}
