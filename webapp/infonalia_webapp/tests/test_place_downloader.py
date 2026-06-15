from __future__ import annotations

import importlib.util
from pathlib import Path


def load_place_downloader():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "herramientas_python" / "Descargar_PLACE.py"
    spec = importlib.util.spec_from_file_location("descargar_place_for_tests", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_place_document_html_is_reprocessed_for_missing_attachments(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    (tmp_path / "DOC_CD2026-000165479.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "DOC_CN2026-000165535.xml").write_text("<xml></xml>", encoding="utf-8")

    assert downloader.candidatos_para_segunda_fase(str(tmp_path), []) == [
        "DOC_CD2026-000165479.html",
        "DOC_CN2026-000165535.xml",
    ]
