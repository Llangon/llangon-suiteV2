from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from .automation_orchestrator import (
    PROJECT_ROOT,
    STATUS_FAILED,
    connect_db,
    ensure_automation_schema,
    record_automation_start_failure,
    recover_orphaned_automation_runs,
    run_task,
)


DEFAULT_TIMEOUT_SECONDS = 900


def configured_timeout_seconds() -> int:
    try:
        value = int(os.environ.get("LLANGON_FILE_INVENTORY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_SECONDS
    return max(30, min(7200, value))


def recover_after_worker_exit(db_path: Path) -> list[int]:
    conn = connect_db(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_automation_schema(conn)
        return recover_orphaned_automation_runs(conn)
    finally:
        conn.close()


def latest_task_run_id(db_path: Path, task_key: str) -> int:
    conn = None
    try:
        conn = connect_db(db_path)
        conn.row_factory = sqlite3.Row
        ensure_automation_schema(conn)
        row = conn.execute(
            "SELECT MAX(id) AS id FROM automation_runs WHERE task_key = ?",
            (task_key,),
        ).fetchone()
        return int(row["id"] or 0) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        if conn is not None:
            conn.close()


def record_supervisor_failure(args: argparse.Namespace, message: str) -> int | None:
    return record_automation_start_failure(
        args.task_key,
        db_path=args.db,
        source=args.source,
        triggered_by=args.triggered_by,
        error_message=message,
    )


def supervised_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "webapp.infonalia_webapp.automation_worker",
        "--execute",
        "--task-key",
        args.task_key,
        "--db",
        str(args.db),
        "--source",
        args.source,
    ]
    if args.triggered_by:
        command.extend(["--triggered-by", args.triggered_by])
    return command


def supervise(args: argparse.Namespace) -> int:
    baseline_run_id = latest_task_run_id(args.db, args.task_key)
    kwargs: dict[str, object] = {
        "cwd": str(PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": False,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(supervised_command(args), **kwargs)
    except Exception as exc:
        record_supervisor_failure(args, f"No se pudo iniciar el proceso hijo de reconciliación de rutas: {exc}")
        return 1
    try:
        return_code = process.wait(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        recovered = recover_after_worker_exit(args.db)
        if not recovered and latest_task_run_id(args.db, args.task_key) <= baseline_run_id:
            record_supervisor_failure(
                args,
                f"El proceso hijo de reconciliación de rutas superó el límite de {args.timeout_seconds} segundos.",
            )
        return 124
    if return_code != 0:
        recovered = recover_after_worker_exit(args.db)
        if not recovered and latest_task_run_id(args.db, args.task_key) <= baseline_run_id:
            record_supervisor_failure(
                args,
                f"El proceso hijo de reconciliación de rutas terminó con código {return_code} antes de registrar la ejecución.",
            )
    return int(return_code or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker aislado para automatizaciones internas de Llangon Suite.")
    parser.add_argument("--task-key", required=True)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--source", default="manual_worker")
    parser.add_argument("--triggered-by", default="")
    parser.add_argument("--timeout-seconds", type=int, default=configured_timeout_seconds())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    args.timeout_seconds = max(30, min(7200, int(args.timeout_seconds)))
    if not args.execute:
        return supervise(args)
    result = run_task(
        args.task_key,
        db_path=args.db,
        source=args.source,
        triggered_by=args.triggered_by,
    )
    return 1 if result.get("status") == STATUS_FAILED else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
