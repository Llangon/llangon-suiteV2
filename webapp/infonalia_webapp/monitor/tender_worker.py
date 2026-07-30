from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path

from .tender_orchestrator import TenderMonitorDependencies, run_tender_monitor_cycle
from .tender_repository import fail_cycle_with_retry, now_iso, update_cycle_worker_with_retry


def run_worker(cycle_id: int, *, db_path: str | Path, root: str | Path | None = None) -> dict[str, object]:
    try:
        from .. import app
    except ImportError:  # pragma: no cover
        import app  # type: ignore

    settings = app.get_settings()
    dependencies = TenderMonitorDependencies(
        email_sender=lambda to, subject, text, html, attachments=None: app.send_monitor_email(
            to, subject, text, html, attachments=attachments, settings=settings
        ),
        suite_base_url=str(app.PLATFORM_URL or "http://127.0.0.1:8787"),
    )
    return run_tender_monitor_cycle(
        cycle_id,
        db_path=db_path,
        root=root,
        dependencies=dependencies,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker de un ciclo real del monitor de licitaciones.")
    parser.add_argument("--cycle-id", type=int, required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--root")
    parser.add_argument("--log-path", default="")
    args = parser.parse_args(argv)
    update_cycle_worker_with_retry(
        args.db,
        args.cycle_id,
        worker_pid=os.getpid(),
        started_at=now_iso(),
        log_path=args.log_path or None,
    )
    try:
        report = run_worker(args.cycle_id, db_path=args.db, root=args.root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        exit_code = 0 if report.get("status") in {"completed", "completed_with_incidents"} else 1
    except BaseException as exc:
        traceback.print_exc()
        message = f"{type(exc).__name__}: {exc}"
        fail_cycle_with_retry(args.db, args.cycle_id, message=message, exit_code=1)
        exit_code = 1
    update_cycle_worker_with_retry(
        args.db,
        args.cycle_id,
        finished_at=now_iso(),
        exit_code=exit_code,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
