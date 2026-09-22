from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from webapp.infonalia_webapp.portal_publication.coverage import audit_coverage
from webapp.infonalia_webapp.portal_publication.generator import build_portal_model
from webapp.infonalia_webapp.portal_publication.pdf_source import read_ficha_pdf
from webapp.infonalia_webapp.portal_publication.selection import (
    PortalFileSelectionError,
    list_portal_files,
    resolve_portal_files,
)
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def _pdf(path: Path, pages: list[str]) -> Path:
    writer = canvas.Canvas(str(path))
    for text in pages:
        writer.drawString(50, 790, text)
        writer.showPage()
    writer.save()
    return path


def _licitacion(folder: Path) -> dict[str, object]:
    return {
        "id": 7,
        "expediente": "EXP-PORTAL",
        "objeto": "Suministro de prueba",
        "fecha_limite": "2026-09-01",
        "hora_limite": "14:00",
        "enlace_perfil": "https://example.test/licitacion",
        "ruta_carpeta": str(folder),
    }


def test_portal_selection_requires_exactly_one_ficha_and_keeps_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    folder = tmp_path / "expediente"
    folder.mkdir()
    _pdf(folder / "Ficha.pdf", ["Ficha completa del expediente EXP-PORTAL"])
    _pdf(folder / "PPT.pdf", ["Prescripciones técnicas"])
    (folder / "Oferta.xlsx").write_bytes(b"xlsx")

    payload = list_portal_files(_licitacion(folder))

    assert payload["can_prepare"] is True
    assert {item["name"] for item in payload["items"]} == {"Ficha.pdf", "PPT.pdf", "Oferta.xlsx"}
    ficha_item = next(item for item in payload["items"] if item["name"] == "Ficha.pdf")
    optional_items = [item for item in payload["items"] if item["name"] != "Ficha.pdf"]
    assert ficha_item["required"] is True
    assert ficha_item["selected_by_default"] is True
    assert all(item["selected_by_default"] is False for item in optional_items)
    ficha, selected = resolve_portal_files(_licitacion(folder), ["Ficha.pdf", "PPT.pdf", "Oferta.xlsx"])
    assert ficha["name"] == "Ficha.pdf"
    assert len(selected) == 3


def test_portal_selection_rejects_traversal_and_missing_ficha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    folder = tmp_path / "expediente"
    folder.mkdir()
    _pdf(folder / "Ficha.pdf", ["Contenido suficiente de la ficha de licitación"])
    _pdf(folder / "PPT.pdf", ["Prescripciones"])

    with pytest.raises(PortalFileSelectionError, match="ruta no permitida"):
        resolve_portal_files(_licitacion(folder), ["..\\fuera.pdf", "Ficha.pdf"])
    with pytest.raises(PortalFileSelectionError, match="única Ficha"):
        resolve_portal_files(_licitacion(folder), ["PPT.pdf"])


def test_multiple_client_fichas_are_chosen_one_at_a_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    folder = tmp_path / "expediente"
    client_a = folder / "CLIENTE A"
    client_b = folder / "CLIENTE B"
    client_a.mkdir(parents=True)
    client_b.mkdir(parents=True)
    _pdf(client_a / "Ficha.pdf", ["Ficha completa del cliente A"])
    _pdf(client_b / "Ficha.pdf", ["Ficha completa del cliente B"])
    _pdf(folder / "PPT.pdf", ["Documento técnico compartido"])

    payload = list_portal_files(_licitacion(folder))
    fichas = [item for item in payload["items"] if item["is_ficha_candidate"]]

    assert payload["can_prepare"] is True
    assert "portal independiente" in payload["selection_notice"]
    assert len(fichas) == 2
    assert all(item["required"] is False for item in fichas)
    assert all(item["selected_by_default"] is False for item in fichas)
    selected_ficha, selected = resolve_portal_files(
        _licitacion(folder),
        [str(Path("CLIENTE A") / "Ficha.pdf"), "PPT.pdf"],
    )
    assert selected_ficha["relative_path"] == str(Path("CLIENTE A") / "Ficha.pdf")
    assert len(selected) == 2


def test_generated_model_preserves_every_page_verbatim_and_never_publishes(tmp_path: Path) -> None:
    ficha_path = _pdf(
        tmp_path / "Ficha.pdf",
        [
            "Página uno con todos los datos generales del expediente de contratación.",
            "Página dos con criterios, condiciones y observaciones completas.",
        ],
    )
    file_item = {
        "path": str(ficha_path),
        "name": "Ficha.pdf",
        "relative_path": "Ficha.pdf",
        "size_bytes": ficha_path.stat().st_size,
        "size_human": "1 KB",
        "extension": "PDF",
        "is_ficha": True,
    }

    model = build_portal_model(_licitacion(tmp_path), file_item, [file_item])

    assert model["generation"]["published"] is False
    assert model["generation"]["external_actions"] == []
    assert model["coverage"]["publication_allowed"] is False
    assert model["coverage"]["pages_total"] == 2
    assert model["coverage"]["pages_mapped"] == 2
    assert model["coverage"]["literal_source_preserved"] is True
    for page, section in zip(model["source"]["pages"], model["sections"], strict=True):
        block = section["blocks"][0]
        assert block["text"] == page["text"]
        assert block["sourceSha256"] == page["text_sha256"]


def test_unreliable_extraction_requires_visual_fallback(tmp_path: Path) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        pages = [Page("T�tulo y licitaci�n"), Page("")]

    fake_pdf = tmp_path / "Ficha.pdf"
    fake_pdf.write_bytes(b"%PDF fake for injected reader")
    source = read_ficha_pdf(
        fake_pdf,
        reader_factory=lambda _path: Reader(),
    )
    sections = [
        {
            "blocks": [
                {
                    "type": "source_page",
                    "text": page["text"],
                    "source_sha256": page["text_sha256"],
                    "source_pages": [page["number"]],
                }
            ]
        }
        for page in source["pages"]
    ]

    coverage = audit_coverage(source, sections)

    assert coverage["literal_source_preserved"] is True
    assert coverage["status"] == "needs_review"
    assert coverage["visual_fallback_required_pages"] == [1, 2]


def test_portal_endpoints_prepare_in_memory_without_changing_source_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "expediente"
        folder.mkdir()
        ficha_path = _pdf(folder / "Ficha.pdf", ["Ficha completa para preparar la vista web local."])
        download_path = _pdf(folder / "PPT.pdf", ["Documento técnico descargable."])
        before = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in folder.iterdir()}
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                ) VALUES (1, 'EXP-PORTAL', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )

        list_handler = make_handler(app, "GET", "/api/licitaciones/1/portal-files")
        dispatch(list_handler, "GET")
        assert list_handler.responses[-1][0] == HTTPStatus.OK

        generate_handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/1/portal-preview/generate",
            {"selected_files": ["Ficha.pdf", "PPT.pdf"]},
        )
        dispatch(generate_handler, "POST")
        status, payload = generate_handler.responses[-1]

        assert status == HTTPStatus.OK
        assert payload["generation"]["published"] is False
        assert payload["coverage"]["pages_mapped"] == 1
        assert {item["name"] for item in payload["downloads"]} == {ficha_path.name, download_path.name}
        after = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in folder.iterdir()}
        assert after == before


def test_ai_and_portal_selectors_share_collapsed_folder_tree() -> None:
    static_root = Path(__file__).resolve().parents[1] / "static"
    html = (static_root / "index.html").read_text(encoding="utf-8")
    script = (static_root / "app.js").read_text(encoding="utf-8")
    styles = (static_root / "styles.css").read_text(encoding="utf-8")

    assert 'class="file-picker-tree" id="ai-file-list"' in html
    assert 'class="file-picker-tree" id="portal-file-list"' in html
    assert '<tbody id="ai-file-list">' not in html
    assert '<tbody id="portal-file-list">' not in html
    assert "function buildFilePickerTree(" in script
    assert "renderFilePicker(aiFileList" in script
    assert "renderFilePicker(portalFileList" in script
    assert '<details class="file-picker-folder" role="treeitem">' in script
    assert '<details class="file-picker-folder" role="treeitem" open>' not in script
    assert ".file-picker-folder[open]" in styles
    assert 'data-is-ficha="${fichaCandidate ? "1" : "0"}"' in script
    assert "selectedFichas.length !== 1" in script
