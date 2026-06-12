from __future__ import annotations

import importlib
import sys
from pathlib import Path

from webapp.infonalia_webapp.pdf_enrichment import (
    download_to_path,
    enrich_from_pdf_url,
    find_pdftotext_path,
    pdf_file_to_text,
)


def test_pdf_enrichment_import_does_not_import_app() -> None:
    sys.modules.pop("webapp.infonalia_webapp.pdf_enrichment", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules

    importlib.import_module("webapp.infonalia_webapp.pdf_enrichment")

    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported


def test_find_pdftotext_path_prefers_configured_executable(tmp_path: Path) -> None:
    configured = tmp_path / "custom" / "pdftotext.exe"
    project_exe = tmp_path / "project" / "pdftotext.exe"
    configured.parent.mkdir()
    project_exe.parent.mkdir()
    configured.write_text("configured", encoding="utf-8")
    project_exe.write_text("project", encoding="utf-8")

    assert find_pdftotext_path(
        tmp_path / "project",
        tmp_path / "app",
        environ={"INFONALIA_PDFTOTEXT": str(configured)},
        home=tmp_path / "home",
    ) == configured


def test_find_pdftotext_path_checks_project_app_and_dropbox_candidates(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    app_root = tmp_path / "app"
    home = tmp_path / "home"
    dropbox_exe = home / "Dropbox" / "00000 LLANGON" / "Infonalia" / "pdftotext.exe"
    dropbox_exe.parent.mkdir(parents=True)
    dropbox_exe.write_text("dropbox", encoding="utf-8")

    assert find_pdftotext_path(project_root, app_root, environ={}, home=home) == dropbox_exe

    app_exe = app_root / "pdftotext.exe"
    app_exe.parent.mkdir()
    app_exe.write_text("app", encoding="utf-8")
    assert find_pdftotext_path(project_root, app_root, environ={}, home=home) == app_exe

    project_exe = project_root / "pdftotext.exe"
    project_exe.parent.mkdir()
    project_exe.write_text("project", encoding="utf-8")
    assert find_pdftotext_path(project_root, app_root, environ={}, home=home) == project_exe


def test_download_to_path_writes_response_without_real_network(tmp_path: Path) -> None:
    destination = tmp_path / "licitacion.pdf"
    captured = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"%PDF fake"

    def opener(request, *, timeout: int):
        captured["url"] = request.full_url
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return FakeResponse()

    assert download_to_path(" https://example.test/ficha.pdf ", destination, opener=opener) is True
    assert destination.read_bytes() == b"%PDF fake"
    assert captured == {
        "url": "https://example.test/ficha.pdf",
        "user_agent": "Mozilla/5.0 InfonaliaWeb",
        "timeout": 30,
    }


def test_download_to_path_returns_false_on_errors(tmp_path: Path) -> None:
    def opener(*_: object, **__: object):
        raise OSError("network disabled")

    assert download_to_path("https://example.test/ficha.pdf", tmp_path / "x.pdf", opener=opener) is False


def test_pdf_file_to_text_runs_pdftotext_and_reads_txt(tmp_path: Path) -> None:
    exe = tmp_path / "pdftotext.exe"
    pdf_path = tmp_path / "documento.pdf"
    exe.write_text("exe", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF fake")
    captured = {}

    def runner(command: list[str], **kwargs: object) -> None:
        captured["command"] = command
        captured["kwargs"] = kwargs
        Path(command[-1]).write_text("Texto extraido", encoding="utf-8")

    assert pdf_file_to_text(pdf_path, exe, runner=runner) == "Texto extraido"
    assert captured["command"] == [str(exe), "-layout", str(pdf_path), str(pdf_path.with_suffix(".txt"))]
    assert captured["kwargs"] == {
        "capture_output": True,
        "text": True,
        "timeout": 60,
        "check": False,
    }


def test_pdf_file_to_text_returns_empty_without_executable(tmp_path: Path) -> None:
    assert pdf_file_to_text(tmp_path / "documento.pdf", None) == ""


def test_enrich_from_pdf_url_uses_injected_downloader_and_reader(tmp_path: Path) -> None:
    calls = {}

    def downloader(url: str, path: Path) -> bool:
        calls["download"] = (url, path)
        path.write_bytes(b"%PDF fake")
        return True

    def text_reader(path: Path) -> str:
        calls["read"] = path
        return "Tipo de contrato: obras\nPresentación 30/06/2026\nHasta las 9:05 horas"

    result = enrich_from_pdf_url(
        "https://example.test/ficha.pdf",
        "2026-06-30",
        temp_dir=tmp_path,
        downloader=downloader,
        text_reader=text_reader,
        clock_ns=lambda: 123,
    )

    expected_path = tmp_path / "infonalia_123.pdf"
    assert calls == {
        "download": ("https://example.test/ficha.pdf", expected_path),
        "read": expected_path,
    }
    assert result == {"tipo": "Obras", "hora_limite": "09:05"}


def test_enrich_from_pdf_url_returns_empty_when_download_fails(tmp_path: Path) -> None:
    reads = []

    result = enrich_from_pdf_url(
        "https://example.test/ficha.pdf",
        "2026-06-30",
        temp_dir=tmp_path,
        downloader=lambda _url, _path: False,
        text_reader=lambda path: reads.append(path) or "",
        clock_ns=lambda: 123,
    )

    assert result == {}
    assert reads == []
