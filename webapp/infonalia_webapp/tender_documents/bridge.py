"""Closed-command local bridge used by Ficha Llangon v2.

Supported operations are intentionally enumerated.  The bridge accepts neither
SQL nor a database path from Excel.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .client_reader import ClientReadError, default_db_path, read_client_catalog
from .payload import iso_now, load_payload
from .place_adapter import payload_from_place_source
from .pdf_renderer import render_tender_pdf
from .workbook_images import extract_ficha_images


BRIDGE_VERSION = "1.4.0"


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        Path(temp_name).replace(path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _write_result(path: Path | None, *, status: str, **values: object) -> None:
    if path is None:
        return
    lines = [f"status\t{status}", f"bridge_version\t{BRIDGE_VERSION}"]
    for key, value in values.items():
        safe = str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")
        lines.append(f"{key}\t{safe}")
    _atomic_text(path, "\n".join(lines) + "\n")


def _clients_tsv(clients: list[dict[str, Any]], columns: list[str], generated_at: str) -> str:
    from io import StringIO

    stream = StringIO(newline="")
    stream.write(f"#schema_version\t2\n#generated_at\t{generated_at}\n#dynamic_columns\ttrue\n")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    for item in clients:
        values = []
        for column in columns:
            value = item.get(column)
            if column == "active":
                value = "1" if value else "0"
            values.append("" if value is None else value)
        writer.writerow(values)
    return stream.getvalue()


def export_clients(output: str | Path, *, db_path: str | Path | None = None) -> tuple[Path, int]:
    target = Path(output)
    columns, clients = read_client_catalog(db_path)
    generated_at = iso_now()
    if target.suffix.lower() == ".json":
        body = json.dumps(
            {
                "schema_version": "1",
                "bridge_version": BRIDGE_VERSION,
                "generated_at": generated_at,
                "status": "ok",
                "columns": columns,
                "clients": clients,
            },
            ensure_ascii=False,
            indent=2,
        )
    else:
        body = _clients_tsv(clients, columns, generated_at)
    _atomic_text(target, body)
    return target, len(clients)


PLACE_TSV_FIELDS = (
    ("tender.fecha_limite", "tender", "fecha_limite"),
    ("tender.hora_limite", "tender", "hora_limite"),
    ("tender.objeto", "tender", "objeto"),
    ("tender.expediente", "tender", "expediente"),
    ("tender.organismo", "tender", "organismo"),
    ("tender.enlace", "tender", "enlace"),
    ("tender.tipo_contrato", "tender", "tipo_contrato"),
    ("tender.procedimiento", "tender", "procedimiento"),
    ("tender.regulacion_armonizada", "tender", "regulacion_armonizada"),
    ("tender.plataforma", "tender", "plataforma"),
    ("tender.presupuesto_base", "tender", "presupuesto_base"),
    ("tender.valor_estimado", "tender", "valor_estimado"),
    ("analysis.plazo", "analysis", "plazo"),
    ("analysis.plazo_comentario", "analysis", "plazo_comentario"),
    ("analysis.prorroga", "analysis", "prorroga"),
    ("analysis.prorroga_comentario", "analysis", "prorroga_comentario"),
)


def _place_tsv(payload: dict[str, Any], warnings: list[str]) -> tuple[str, int]:
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(("#schema_version", "1"))
    writer.writerow(("#source_url", payload.get("control", {}).get("source_url", "")))
    for warning in warnings:
        writer.writerow(("#warning", warning))
    writer.writerow(("logical_id", "value"))
    count = 0
    for logical_id, section, key in PLACE_TSV_FIELDS:
        value = payload.get(section, {}).get(key)
        if value in (None, ""):
            continue
        writer.writerow((logical_id, value))
        count += 1
    return stream.getvalue(), count


def export_place(source_url: str, output: str | Path, *, fetcher=None) -> tuple[Path, int, int]:
    target = Path(output)
    payload, warnings = payload_from_place_source(source_url, fetcher=fetcher)
    body, count = _place_tsv(payload, warnings)
    _atomic_text(target, body)
    return target, count, len(warnings)


def _read_source_file(path: str | Path) -> str:
    source_path = Path(path)
    if not source_path.is_file() or source_path.stat().st_size > 16384:
        raise ValueError("No se pudo leer el origen PLACE temporal.")
    return source_path.read_text(encoding="utf-8-sig").strip()


def _unique_pdf_path(requested: Path) -> Path:
    if not requested.exists():
        return requested
    for revision in range(2, 1000):
        candidate = requested.with_name(f"{requested.stem}_r{revision}{requested.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("No se pudo determinar un nombre libre para el PDF.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llangon-excel-bridge", add_help=True)
    parser.add_argument("--version", action="version", version=BRIDGE_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    clients = subparsers.add_parser("clients", help="Exporta el catálogo de clientes en solo lectura.")
    clients.add_argument("--output", required=True)
    clients.add_argument("--result")

    place = subparsers.add_parser("place", help="Obtiene datos de una página o XML público de PLACE.")
    source_group = place.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source")
    source_group.add_argument("--source-file")
    place.add_argument("--output", required=True)
    place.add_argument("--result")

    render = subparsers.add_parser("render-pdf", help="Valida y renderiza una ficha.")
    render.add_argument("--input", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--result")
    render.add_argument("--workbook")
    render.add_argument("--draft", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result_path = Path(args.result) if getattr(args, "result", None) else None
    try:
        if args.command == "clients":
            output, count = export_clients(args.output)
            _write_result(
                result_path,
                status="ok",
                output=output,
                count=count,
                generated_at=iso_now(),
                db_path=default_db_path(),
                read_only="true",
            )
            return 0
        if args.command == "place":
            source_url = args.source if args.source is not None else _read_source_file(args.source_file)
            output, count, warning_count = export_place(source_url, args.output)
            _write_result(
                result_path,
                status="ok",
                output=output,
                count=count,
                warnings=warning_count,
                source_url=source_url,
            )
            return 0
        if args.command == "render-pdf":
            payload = load_payload(args.input)
            output = _unique_pdf_path(Path(args.output))
            if args.workbook:
                with tempfile.TemporaryDirectory(prefix="llangon_ficha_images_") as image_dir:
                    workbook_images = extract_ficha_images(args.workbook, image_dir)
                    rendered = render_tender_pdf(
                        payload,
                        output,
                        draft=bool(args.draft),
                        workbook_images=workbook_images,
                    )
                    image_count = len(workbook_images)
            else:
                rendered = render_tender_pdf(payload, output, draft=bool(args.draft))
                image_count = 0
            _write_result(
                result_path,
                status="ok",
                output=rendered.path,
                pages=rendered.page_count,
                sha256=rendered.sha256,
                size_bytes=rendered.size_bytes,
                images=image_count,
            )
            return 0
        raise ValueError("Operación no admitida.")
    except (ClientReadError, FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        _write_result(result_path, status="error", message=str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
