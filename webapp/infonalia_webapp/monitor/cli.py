from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reports import report_to_json
from .service import ALL_MODES, MonitorError, run_monitor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor V0 de licitaciones locales")
    parser.add_argument("--mode", choices=sorted(ALL_MODES), default="dry-run")
    parser.add_argument("--dry-run", action="store_true", help="No escribir cambios en SQLite.")
    parser.add_argument("--root", help="Raiz local tipo Dropbox. Por defecto usa INFONALIA_MONITOR_ROOT.")
    parser.add_argument("--db", help="Ruta de SQLite. Por defecto usa webapp/infonalia_webapp/data/infonalia.db.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_monitor(
            args.mode,
            dry_run=args.dry_run,
            root=args.root,
            db_path=Path(args.db) if args.db else None,
        )
    except MonitorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(report_to_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

