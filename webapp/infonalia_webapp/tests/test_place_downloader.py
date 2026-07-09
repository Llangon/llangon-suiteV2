from __future__ import annotations

import importlib.util
from types import SimpleNamespace
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


def test_place_downloader_detects_rar_without_appending_bin() -> None:
    downloader = load_place_downloader()
    rar_bytes = b"Rar!\x1a\x07\x01\x00" + b"\x00" * 32
    response = SimpleNamespace(
        content=rar_bytes,
        headers={"Content-Type": "application/octet-stream"},
    )

    ext = downloader.detectar_extension(
        response,
        texto_visible="ANEXOS",
        nombre_logico="DOC20260708091325ANEXOS.rar",
        archivo_url="https://example.test/documento",
    )
    nombre = downloader.construir_nombre_archivo(
        response,
        "DOC20260708091325ANEXOS.rar",
        "ANEXOS",
        "https://example.test/documento",
        ext,
    )

    assert ext == ".rar"
    assert nombre == "DOC20260708091325ANEXOS.rar"
