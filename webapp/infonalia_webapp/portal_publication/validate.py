from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import build_portal_model


def validate_fichas(paths: list[Path]) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for path in paths:
        resolved = path.resolve()
        item = {
            "path": str(resolved),
            "name": resolved.name,
            "relative_path": resolved.name,
            "size_bytes": resolved.stat().st_size if resolved.is_file() else 0,
            "size_human": "",
            "extension": "PDF",
            "is_ficha": True,
        }
        try:
            model = build_portal_model({}, {**item, "path": str(resolved)}, [item])
            coverage = model["coverage"]
            results.append(
                {
                    "path": str(resolved),
                    "ok": bool(coverage["literal_source_preserved"]),
                    "status": coverage["status"],
                    "pages_total": coverage["pages_total"],
                    "pages_mapped": coverage["pages_mapped"],
                    "visual_fallback_required_pages": coverage["visual_fallback_required_pages"],
                    "warnings": coverage["warnings"],
                }
            )
        except Exception as exc:
            results.append({"path": str(resolved), "ok": False, "status": "error", "error": str(exc)})
    return {
        "files_total": len(results),
        "files_literal_source_preserved": sum(1 for result in results if result.get("ok")),
        "pages_total": sum(int(result.get("pages_total") or 0) for result in results),
        "pages_mapped": sum(int(result.get("pages_mapped") or 0) for result in results),
        "files_ready_for_ai_enrichment": sum(
            1 for result in results if result.get("status") == "ready_for_ai_enrichment"
        ),
        "files_needing_review": sum(1 for result in results if result.get("status") == "needs_review"),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida fichas PDF sin modificarlas ni publicar contenido.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    report = validate_fichas(args.paths)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["files_literal_source_preserved"] == report["files_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
