"""Generate the three fictitious acceptance PDFs for Ficha Llangon v2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webapp.infonalia_webapp.tender_documents.pdf_renderer import render_tender_pdf
from webapp.infonalia_webapp.tender_documents.sample_payloads import (
    extreme_payload,
    normal_payload,
    short_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/pdf/ficha_llangon_v2")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, factory in (
        ("Ficha_Llangon_v2_caso_corto", short_payload),
        ("Ficha_Llangon_v2_caso_normal", normal_payload),
        ("Ficha_Llangon_v2_caso_extremo", extreme_payload),
    ):
        pdf_path = output_dir / f"{name}.pdf"
        pdf_path.unlink(missing_ok=True)
        result = render_tender_pdf(factory(), pdf_path)
        results.append({
            "path": str(result.path),
            "pages": result.page_count,
            "size_bytes": result.size_bytes,
            "sha256": result.sha256,
        })
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
