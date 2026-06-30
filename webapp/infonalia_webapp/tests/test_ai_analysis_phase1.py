from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.ai.config import AIConfig, get_ai_config
from webapp.infonalia_webapp.ai.codex_local_provider import CodexLocalProvider
from webapp.infonalia_webapp.ai.document_selector import inspect_document_selection, select_relevant_documents
from webapp.infonalia_webapp.ai.file_selection import AIFileSelectionError, list_ai_files, resolve_selected_ai_files
from webapp.infonalia_webapp.ai.gemini_provider import (
    AIProviderError,
    ProviderResult,
    build_gemini_contents,
    build_gemini_contents_for_mode,
    build_text_gemini_contents,
    classify_gemini_exception,
    parse_gemini_response,
)
from webapp.infonalia_webapp.ai.hashing import hash_documents
from webapp.infonalia_webapp.ai.manual_test import build_preflight_report, mark_interrupted_job
from webapp.infonalia_webapp.ai.pdf_text_extractor import ExtractedTextResult, extract_pdf_text
from webapp.infonalia_webapp.ai.queue import active_job, create_job, ensure_ai_schema, latest_summary
from webapp.infonalia_webapp.ai.rate_limit import check_rate_limit
from webapp.infonalia_webapp.ai.schemas import parse_summary_json, summary_quality_check
from webapp.infonalia_webapp.ai.service import delete_ai_summary, process_ai_job, request_ai_analysis
from webapp.infonalia_webapp.ai.workspace import prepare_ai_workspace
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def teardown_function() -> None:
    for key in list(os.environ):
        if key.startswith("GEMINI_") or key.startswith("CODEX_") or key == "AI_ANALYSIS_PROVIDER":
            os.environ.pop(key, None)
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            expediente TEXT,
            objeto TEXT,
            organismo TEXT,
            fecha_limite TEXT,
            hora_limite TEXT,
            enlace_perfil TEXT,
            ruta_carpeta TEXT
        )
        """
    )
    ensure_ai_schema(conn)
    return conn


def _insert_licitacion(conn: sqlite3.Connection, folder: Path, licitacion_id: int = 1) -> None:
    conn.execute(
        """
        INSERT INTO licitaciones (
            id, expediente, objeto, organismo, fecha_limite, hora_limite, enlace_perfil, ruta_carpeta
        )
        VALUES (?, 'EXP-IA', 'Suministro de prueba', 'Organo de prueba', '2026-07-01', '14:00',
                'https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=test', ?)
        """,
        (licitacion_id, str(folder)),
    )


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\ncontenido\n") -> Path:
    path.write_bytes(content)
    return path


class FakeProvider:
    def __init__(
        self,
        *,
        error: AIProviderError | None = None,
        invalid: bool = False,
        summary_payload: dict[str, object] | None = None,
        raw_usage: dict[str, object] | None = None,
    ) -> None:
        self.error = error
        self.invalid = invalid
        self.summary_payload = summary_payload
        self.raw_usage = raw_usage or {}
        self.calls = 0

    def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
        self.calls += 1
        if self.error:
            raise self.error
        if self.invalid:
            return ProviderResult(summary=[], raw_usage={})  # type: ignore[arg-type]
        if self.summary_payload is not None:
            return ProviderResult(summary=self.summary_payload, raw_usage=self.raw_usage)
        return ProviderResult(
            summary={
                "metadata": {"expediente": licitacion["expediente"], "titulo": licitacion["objeto"]},
                "resumen_ejecutivo": {"texto": "Resumen generado por mock.", "aspectos_clave": ["Clave"]},
            },
            raw_usage={"prompt_token_count": 10, "candidates_token_count": 5, "total_token_count": 15},
        )


class FakeGeminiResponse:
    def __init__(self, text: str = "", parsed: object | None = None) -> None:
        self.text = text
        if parsed is not None:
            self.parsed = parsed


class FakePart:
    @classmethod
    def from_bytes(cls, *, data: bytes, mime_type: str) -> dict[str, object]:
        return {"data": data, "mime_type": mime_type}


class FakeTypes:
    Part = FakePart


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakePdfReader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [FakePage(text) for text in pages]


def _reader_factory(mapping: dict[str, list[str]]):
    def factory(path: Path) -> FakePdfReader:
        return FakePdfReader(mapping.get(path.name, []))

    return factory


def _ai_config(**overrides: object) -> AIConfig:
    values = {
        "enabled": True,
        "api_key": "fake-key",
        "model": "gemini-test",
        "max_requests_per_minute": 2,
        "max_requests_per_day": 20,
        "cooldown_on_429_minutes": 15,
        "max_documents_per_analysis": 4,
        "max_file_mb": 45,
        "timeout_seconds": 120,
        "input_mode": "text",
        "max_extracted_chars": 180000,
        "max_chars_per_document": 90000,
        "pdf_inline_fallback": False,
        "min_extracted_chars": 1000,
    }
    values.update(overrides)
    return AIConfig(**values)


def test_ai_config_defaults_disabled_and_does_not_expose_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    config = get_ai_config()

    assert config.enabled is False
    assert config.configured is True
    assert config.input_mode == "text"
    assert "api_key" not in config.public_status()
    assert "secret-test-key" not in json.dumps(config.public_status())


def test_gemini_response_parser_uses_parsed_dict() -> None:
    payload, diagnostics = parse_gemini_response(FakeGeminiResponse(parsed={"metadata": {"expediente": "EXP"}}))

    assert payload["metadata"]["expediente"] == "EXP"
    assert diagnostics["parse_strategy"] == "response.parsed"


def test_gemini_response_parser_accepts_plain_json_text() -> None:
    payload, diagnostics = parse_gemini_response(FakeGeminiResponse('{"metadata":{"expediente":"EXP"}}'))

    assert payload["metadata"]["expediente"] == "EXP"
    assert diagnostics["parse_strategy"] == "response.text"


def test_gemini_response_parser_accepts_markdown_fenced_json() -> None:
    payload, diagnostics = parse_gemini_response(FakeGeminiResponse('```json\n{"metadata":{"expediente":"EXP"}}\n```'))

    assert payload["metadata"]["expediente"] == "EXP"
    assert diagnostics["markdown_fences_detected"] is True
    assert diagnostics["parse_strategy"] == "markdown_fence"


def test_gemini_response_parser_extracts_object_surrounded_by_text() -> None:
    payload, diagnostics = parse_gemini_response(FakeGeminiResponse('Respuesta:\n{"metadata":{"expediente":"EXP"}}\nFin.'))

    assert payload["metadata"]["expediente"] == "EXP"
    assert diagnostics["json_object_extraction_attempted"] is True
    assert diagnostics["parse_strategy"] == "first_json_object"


def test_gemini_response_parser_rejects_root_list() -> None:
    with pytest.raises(AIProviderError) as excinfo:
        parse_gemini_response(FakeGeminiResponse('[{"metadata":{"expediente":"EXP"}}]'))

    assert excinfo.value.code == "INVALID_JSON"
    assert "objeto JSON" in str(excinfo.value)
    assert any("root_type:list" in attempt for attempt in excinfo.value.diagnostics["parse_attempts"])


def test_gemini_response_parser_rejects_empty_text_with_preview() -> None:
    with pytest.raises(AIProviderError) as excinfo:
        parse_gemini_response(FakeGeminiResponse(""))

    assert excinfo.value.code == "INVALID_JSON"
    assert excinfo.value.diagnostics["text_length"] == 0
    assert excinfo.value.diagnostics["raw_response_preview"] == ""


def test_gemini_response_parser_limits_invalid_json_preview() -> None:
    long_text = "no json " + ("x" * 3000)

    with pytest.raises(AIProviderError) as excinfo:
        parse_gemini_response(FakeGeminiResponse(long_text))

    assert excinfo.value.code == "INVALID_JSON"
    assert len(excinfo.value.diagnostics["raw_response_preview"]) == 1500


def test_gemini_503_is_classified_as_unavailable() -> None:
    error = classify_gemini_exception(RuntimeError("503 UNAVAILABLE: model overloaded"))

    assert error.code == "GEMINI_UNAVAILABLE"
    assert "Reintentar" in str(error)


def test_gemini_timeout_is_classified() -> None:
    error = classify_gemini_exception(TimeoutError("timed out waiting for response"))

    assert error.code == "GEMINI_TIMEOUT"
    assert "tiempo configurado" in str(error)


def test_gemini_504_deadline_exceeded_is_classified() -> None:
    error = classify_gemini_exception(RuntimeError("504 DEADLINE_EXCEEDED: response took too long"))

    assert error.code == "GEMINI_DEADLINE_EXCEEDED"
    assert "plazo" in str(error)


def test_gemini_error_diagnostics_redact_api_key() -> None:
    error = classify_gemini_exception(
        RuntimeError("403 forbidden for key secret-test-key"),
        secrets=("secret-test-key",),
    )

    assert error.code == "AUTH_ERROR"
    assert "secret-test-key" not in json.dumps(error.diagnostics)
    assert "[redacted]" in error.diagnostics["provider_error_preview"]


def test_gemini_contents_include_real_pdf_bytes(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\nbytes reales\n")

    contents, diagnostics = build_gemini_contents(
        FakeTypes,
        {"expediente": "EXP", "objeto": "Objeto", "organismo": "Organo"},
        [{"path": str(pdf), "name": "PCAP.pdf", "relative_path": "PCAP.pdf", "reason": "Coincide con PCAP"}],
        max_file_mb=45,
    )

    assert diagnostics["document_send_method"] == "inline_pdf"
    assert diagnostics["sent_documents_count"] == 1
    assert diagnostics["sent_documents_names"] == ["PCAP.pdf"]
    assert diagnostics["total_pdf_bytes_sent"] == pdf.stat().st_size
    assert any(isinstance(part, dict) and part["mime_type"] == "application/pdf" and part["data"].startswith(b"%PDF") for part in contents)
    assert not any(str(pdf) in str(part) for part in contents if isinstance(part, dict))


def test_pdf_text_extractor_builds_structured_text(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    result = extract_pdf_text(
        [{"path": str(pdf), "name": "PCAP.pdf"}],
        max_total_chars=5000,
        max_chars_per_document=5000,
        reader_factory=_reader_factory({"PCAP.pdf": ["Clausula primera", "Criterios de adjudicacion"]}),
    )

    assert "=== DOCUMENTO 1: PCAP.pdf ===" in result.text
    assert "=== PÁGINA 1 ===" in result.text
    assert "Clausula primera" in result.text
    assert result.diagnostics["documents_text_extracted_count"] == 1
    assert result.diagnostics["pages_processed_by_document"]["PCAP.pdf"] == 2


def test_pdf_text_extractor_reports_no_extractable_text(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    result = extract_pdf_text(
        [{"path": str(pdf), "name": "PCAP.pdf"}],
        max_total_chars=5000,
        max_chars_per_document=5000,
        reader_factory=_reader_factory({"PCAP.pdf": ["", "   "]}),
    )

    assert result.text == ""
    assert result.extracted_chars_total == 0
    assert result.diagnostics["documents_text_extracted_count"] == 0


def test_pdf_text_extractor_respects_character_limits(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    result = extract_pdf_text(
        [{"path": str(pdf), "name": "PCAP.pdf"}],
        max_total_chars=120,
        max_chars_per_document=80,
        reader_factory=_reader_factory({"PCAP.pdf": ["x" * 1000]}),
    )

    assert len(result.text) <= 120
    assert result.diagnostics["extraction_warnings"]


def test_text_mode_builds_text_contents_without_inline_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    def fake_extract(*args, **kwargs):
        return ExtractedTextResult(
            text="Texto util del pliego " * 100,
            diagnostics={
                "documents_text_extracted_count": 1,
                "extracted_chars_total": 2100,
                "extracted_chars_by_document": {"PCAP.pdf": 2100},
                "pages_processed_by_document": {"PCAP.pdf": 3},
                "extraction_warnings": [],
            },
        )

    monkeypatch.setattr("webapp.infonalia_webapp.ai.gemini_provider.extract_pdf_text", fake_extract)
    contents, diagnostics = build_text_gemini_contents(
        {"expediente": "EXP", "objeto": "Objeto", "organismo": "Organo"},
        [{"path": str(pdf), "name": "PCAP.pdf", "relative_path": "PCAP.pdf", "reason": "Coincide con PCAP"}],
        config=_ai_config(input_mode="text", min_extracted_chars=1000),
    )

    assert diagnostics["document_send_method"] == "text_extraction"
    assert diagnostics["input_mode_used"] == "text"
    assert diagnostics["extracted_chars_total"] == 2100
    assert not any(isinstance(part, dict) and part.get("mime_type") == "application/pdf" for part in contents)
    assert "Texto extraido localmente" in str(contents[-1])


def test_text_mode_rejects_pdf_without_enough_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    monkeypatch.setattr(
        "webapp.infonalia_webapp.ai.gemini_provider.extract_pdf_text",
        lambda *args, **kwargs: ExtractedTextResult(
            text="",
            diagnostics={
                "documents_text_extracted_count": 0,
                "extracted_chars_total": 0,
                "extracted_chars_by_document": {"PCAP.pdf": 0},
                "pages_processed_by_document": {"PCAP.pdf": 0},
                "extraction_warnings": [],
            },
        ),
    )

    with pytest.raises(AIProviderError) as excinfo:
        build_text_gemini_contents(
            {"expediente": "EXP"},
            [{"path": str(pdf), "name": "PCAP.pdf"}],
            config=_ai_config(input_mode="text", min_extracted_chars=1000),
        )

    assert excinfo.value.code == "NO_EXTRACTED_TEXT"
    assert excinfo.value.diagnostics["input_mode_used"] == "text"


def test_auto_mode_uses_text_when_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf")

    monkeypatch.setattr(
        "webapp.infonalia_webapp.ai.gemini_provider.extract_pdf_text",
        lambda *args, **kwargs: ExtractedTextResult(
            text="Texto util del pliego " * 100,
            diagnostics={
                "documents_text_extracted_count": 1,
                "extracted_chars_total": 2100,
                "extracted_chars_by_document": {"PCAP.pdf": 2100},
                "pages_processed_by_document": {"PCAP.pdf": 1},
                "extraction_warnings": [],
            },
        ),
    )

    contents, diagnostics = build_gemini_contents_for_mode(
        FakeTypes,
        {"expediente": "EXP"},
        [{"path": str(pdf), "name": "PCAP.pdf"}],
        config=_ai_config(input_mode="auto", min_extracted_chars=1000),
    )

    assert diagnostics["input_mode_requested"] == "auto"
    assert diagnostics["input_mode_used"] == "text"
    assert not any(isinstance(part, dict) and part.get("mime_type") == "application/pdf" for part in contents)


def test_pdf_inline_mode_keeps_previous_behavior(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\nbytes reales\n")

    contents, diagnostics = build_gemini_contents_for_mode(
        FakeTypes,
        {"expediente": "EXP"},
        [{"path": str(pdf), "name": "PCAP.pdf"}],
        config=_ai_config(input_mode="pdf_inline"),
    )

    assert diagnostics["input_mode_used"] == "pdf_inline"
    assert diagnostics["document_send_method"] == "inline_pdf"
    assert any(isinstance(part, dict) and part["mime_type"] == "application/pdf" for part in contents)


def test_summary_quality_rejects_empty_template() -> None:
    parsed = parse_summary_json({})

    result = summary_quality_check(parsed)

    assert result["is_useful"] is False
    assert result["status"] == "empty_analysis"


def test_summary_quality_accepts_useful_json() -> None:
    parsed = parse_summary_json({"resumen_ejecutivo": {"texto": "Hay contenido útil."}})

    result = summary_quality_check(parsed)

    assert result["is_useful"] is True
    assert result["status"] == "ok"
    assert "resumen_ejecutivo.texto" in result["signals"]


def test_document_selector_prioritizes_and_excludes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    _write_pdf(tmp_path / "Acta apertura anterior.pdf")
    _write_pdf(tmp_path / "PPT tecnico.pdf")
    _write_pdf(tmp_path / "PCAP administrativo.pdf")
    _write_pdf(tmp_path / "Cuadro caracteristicas.pdf")
    _write_pdf(tmp_path / "Anexo I.pdf")
    (tmp_path / "Documento.txt").write_text("no pdf", encoding="utf-8")
    row = {"ruta_carpeta": str(tmp_path)}

    selected = select_relevant_documents(row, max_documents=3, max_file_mb=45)

    assert [item["name"] for item in selected] == [
        "Cuadro caracteristicas.pdf",
        "PCAP administrativo.pdf",
        "PPT tecnico.pdf",
    ]
    assert all("anterior" not in str(item["name"]).lower() for item in selected)


def test_document_selector_excludes_historical_year_subfolders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    current = tmp_path / "actual"
    historical = tmp_path / "Año 2022"
    current.mkdir()
    historical.mkdir()
    _write_pdf(current / "DOC20260526075132PCAP SUMINISTRO VIVERES GUARDERIA.pdf")
    _write_pdf(current / "DOC20260522132605PLIEGO CONDICIONES TECNICAS VIVERES GUARDERIA LA VEGUILLA.pdf")
    _write_pdf(historical / "DOC20211202122934PCAP suministro de viveres Guarderia la Veguilla.pdf")
    _write_pdf(historical / "DOC20211202122922PPT suministro viveres Guarderia Infantil la Veguilla.pdf")

    result = inspect_document_selection({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)

    selected_paths = [str(item["relative_path"]) for item in result["selected_documents"]]
    assert selected_paths == [
        str(Path("actual") / "DOC20260526075132PCAP SUMINISTRO VIVERES GUARDERIA.pdf"),
        str(Path("actual") / "DOC20260522132605PLIEGO CONDICIONES TECNICAS VIVERES GUARDERIA LA VEGUILLA.pdf"),
    ]
    assert not any("Año 2022" in item for item in selected_paths)
    assert any("ANO 2022" in str(item["reason"]) for item in result["diagnostics"]["discarded_documents"])


def test_document_selector_respects_max_file_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    _write_pdf(tmp_path / "PCAP.pdf", b"123456")

    assert select_relevant_documents({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=1)
    assert not select_relevant_documents({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=0)


def test_document_selector_resolves_relative_dropbox_folder_without_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "Dropbox" / "00000 LLANGON"
    folder = base / "2026" / "07 JULIO" / "02 JULIO 2359 JAEN MARTOS 20264096"
    folder.mkdir(parents=True)
    _write_pdf(folder / "DOC20260615132934PPT y ANEXO PPT.pdf")
    _write_pdf(folder / "DOC20260615135002PCAP.pdf")
    _write_pdf(folder / "DOC20260617115307RESOLUCION INCOACION.pdf")
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(base))

    result = inspect_document_selection(
        {"ruta_carpeta": r"2026\07 JULIO\02 JULIO 2359 JAEN MARTOS 20264096"},
        max_documents=4,
        max_file_mb=45,
    )

    names = [item["name"] for item in result["selected_documents"]]
    assert names == ["DOC20260615135002PCAP.pdf", "DOC20260615132934PPT y ANEXO PPT.pdf"]
    diagnostics = result["diagnostics"]
    assert diagnostics["resolved_path"] == str(folder)
    assert diagnostics["resolved_exists"] is True
    assert diagnostics["resolved_inside_dropbox"] is True
    assert diagnostics["pdfs_found_count"] == 3
    assert any("RESOLUCION" in item["name"] for item in diagnostics["discarded_documents"])


def test_document_selector_can_fallback_to_admin_pdf_without_core_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    _write_pdf(tmp_path / "DOC20260617115431RESOLUCION APROBACION PLIEGOS.pdf")

    selected = select_relevant_documents({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)

    assert [item["name"] for item in selected] == ["DOC20260617115431RESOLUCION APROBACION PLIEGOS.pdf"]


def test_document_selector_excludes_ficha_in_client_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    client_folder = tmp_path / "SALVADOR"
    client_folder.mkdir()
    _write_pdf(tmp_path / "PCAP.pdf")
    _write_pdf(client_folder / "Ficha.pdf")

    result = inspect_document_selection({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)

    assert [item["name"] for item in result["selected_documents"]] == ["PCAP.pdf"]
    discarded = result["diagnostics"]["discarded_documents"]
    assert any(item["relative_path"] == str(Path("SALVADOR") / "Ficha.pdf") for item in discarded)


def test_document_selector_excludes_previous_actas_and_adjudication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    _write_pdf(tmp_path / "Acta apertura.pdf")
    _write_pdf(tmp_path / "Resolucion adjudicacion.pdf")
    _write_pdf(tmp_path / "Oferta anterior.pdf")

    result = inspect_document_selection({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)

    assert result["selected_documents"] == []
    assert result["diagnostics"]["pdfs_found_count"] == 3
    assert result["diagnostics"]["discarded_documents_count"] == 3
    assert "todos fueron descartados" in result["diagnostics"]["final_reason"]


def test_document_selector_reports_folder_with_no_apt_pdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    (tmp_path / "notas.txt").write_text("sin pdf", encoding="utf-8")

    result = inspect_document_selection({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)

    assert result["selected_documents"] == []
    assert result["diagnostics"]["resolved_exists"] is True
    assert result["diagnostics"]["pdfs_found_count"] == 0
    assert "no se han encontrado PDFs" in result["diagnostics"]["final_reason"]


def test_document_selector_blocks_path_outside_dropbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "Dropbox"
    outside = tmp_path / "Outside"
    base.mkdir()
    outside.mkdir()
    _write_pdf(outside / "PCAP.pdf")
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(base))

    result = inspect_document_selection({"ruta_carpeta": str(outside)}, max_documents=4, max_file_mb=45)

    assert result["selected_documents"] == []
    assert result["diagnostics"]["resolved_inside_dropbox"] is False
    assert "fuera de la carpeta base" in result["diagnostics"]["final_reason"]


def test_document_selector_reports_missing_dropbox_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LLANGON_DROPBOX_BASE_PATH", raising=False)
    monkeypatch.delenv("INFONALIA_DROPBOX_ROOT", raising=False)

    result = inspect_document_selection({"ruta_carpeta": r"2026\07 JULIO\expediente"}, max_documents=4, max_file_mb=45)

    assert result["selected_documents"] == []
    assert result["diagnostics"]["dropbox_base_configured"] is False
    assert "Dropbox" in result["diagnostics"]["final_reason"]


def test_hash_documents_is_stable_and_changes_with_content(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf", b"uno")
    docs = [{"path": str(pdf), "name": pdf.name, "relative_path": pdf.name}]

    first = hash_documents(docs)
    second = hash_documents(docs)
    pdf.write_bytes(b"dos")

    assert first == second
    assert hash_documents(docs) != first


def test_queue_avoids_duplicate_active_job_and_saves_summary(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    docs = [{"path": str(_write_pdf(tmp_path / "PCAP.pdf")), "name": "PCAP.pdf"}]

    job_id = create_job(conn, licitacion_id=1, document_hash="hash", selected_documents=docs, model="gemini-test")
    duplicate = active_job(conn, 1, "hash")

    assert duplicate["id"] == job_id
    assert latest_summary(conn, 1, "hash") is None


def test_rate_limit_blocks_per_minute() -> None:
    conn = _conn()
    config = get_ai_config()
    current = datetime.now().replace(microsecond=0)
    conn.execute(
        """
        INSERT INTO ai_usage_log (provider, model, created_at, request_type, status)
        VALUES ('gemini', 'model', ?, 'analysis', 'completed')
        """,
        (current.isoformat(),),
    )
    config = type(config)(True, "key", "model", 1, 20, 15, 4, 45, 120)

    result = check_rate_limit(conn, config, now=current)

    assert result.allowed is False
    assert "minuto" in result.reason


def test_rate_limit_blocks_cooldown_after_429() -> None:
    conn = _conn()
    current = datetime.now().replace(microsecond=0)
    conn.execute(
        """
        INSERT INTO ai_usage_log (provider, model, created_at, request_type, status, error_code)
        VALUES ('gemini', 'model', ?, 'analysis', 'error', 'RESOURCE_EXHAUSTED')
        """,
        (current.isoformat(),),
    )
    config = type(get_ai_config())(True, "key", "model", 2, 20, 15, 4, 45, 120)

    result = check_rate_limit(conn, config, now=current + timedelta(minutes=5))

    assert result.allowed is False
    assert "Cooldown" in result.reason


def test_service_disabled_does_not_call_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    provider = FakeProvider()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "false")

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["enabled"] is False
    assert payload["job_status"] == "disabled"
    assert provider.calls == 0


def test_service_processes_job_with_mock_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=FakeProvider())

    assert payload["has_summary"] is True
    assert payload["summary"]["summary_text"] == "Resumen generado por mock."
    assert conn.execute("SELECT COUNT(*) FROM ai_usage_log").fetchone()[0] == 1


def test_service_marks_429_as_deferred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    payload = request_ai_analysis(
        conn,
        1,
        requested_by="tester",
        provider=FakeProvider(error=AIProviderError("429", code="RESOURCE_EXHAUSTED")),
    )

    assert payload["job_status"] == "deferred"
    assert payload["job"]["error_code"] == "RESOURCE_EXHAUSTED"


def test_service_marks_invalid_json_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=FakeProvider(invalid=True))

    assert payload["job_status"] == "error"
    assert payload["job"]["error_code"] == "INVALID_JSON"


def test_service_rejects_empty_valid_json_without_saving_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(
        summary_payload={},
        raw_usage={
            "sent_documents_count": 1,
            "sent_documents_names": ["PCAP.pdf"],
            "total_pdf_bytes_sent": 123,
            "parse_diagnostics": {"text_length": 1916, "raw_response_preview": "{}"},
        },
    )

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["job_status"] == "error"
    assert payload["job"]["error_code"] == "EMPTY_ANALYSIS"
    assert payload["job"]["summary_quality_status"] == "empty_analysis"
    assert payload["job"]["sent_documents_count"] == 1
    assert latest_summary(conn, 1) is None


def test_service_ignores_existing_empty_summary_and_regenerates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    selected = select_relevant_documents({"ruta_carpeta": str(tmp_path)}, max_documents=4, max_file_mb=45)
    document_hash = hash_documents(selected)
    conn.execute(
        """
        INSERT INTO ai_summaries (
            licitacion_id, document_hash, provider, model, summary_json, summary_text,
            created_at, updated_at, quality_status
        )
        VALUES (1, ?, 'gemini', 'gemini-test', '{}', '', '2026-01-01', '2026-01-01', 'pending_review')
        """,
        (document_hash,),
    )
    provider = FakeProvider(summary_payload={"resumen_ejecutivo": {"texto": "Resumen regenerado."}})

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert provider.calls == 1
    assert payload["job_status"] == "completed"
    assert payload["summary"]["summary_text"] == "Resumen regenerado."


def test_service_saves_useful_summary_after_quality_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(
        summary_payload={"resumen_ejecutivo": {"texto": "Análisis útil."}},
        raw_usage={
            "sent_documents_count": 1,
            "sent_documents_names": ["PCAP.pdf"],
            "total_pdf_bytes_sent": 123,
            "parse_diagnostics": {"text_length": 128, "raw_response_preview": '{"resumen_ejecutivo":{}}'},
        },
    )

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["job_status"] == "completed"
    assert payload["has_summary"] is True
    assert latest_summary(conn, 1) is not None


def test_service_stores_invalid_json_provider_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(
        error=AIProviderError(
            "La respuesta IA no tiene estructura de objeto JSON.",
            code="INVALID_JSON",
            diagnostics={"raw_response_preview": "[{}]", "parse_attempts": ["response.text:root_type:list"]},
        )
    )

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["job_status"] == "error"
    assert payload["job"]["error_code"] == "INVALID_JSON"
    assert payload["job"]["raw_response_preview"] == "[{}]"
    assert payload["job"]["parse_attempts"] == ["response.text:root_type:list"]


def test_ai_files_endpoint_lists_physical_folder_without_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "2026" / "06 JUNIO" / "expediente"
        historical = folder / "Año 2025"
        historical.mkdir(parents=True)
        _write_pdf(folder / "PCAP contrato.pdf")
        _write_pdf(folder / "Ficha.pdf")
        _write_pdf(historical / "PPT antiguo.pdf")
        (folder / "HTTP.url").write_text("[InternetShortcut]", encoding="utf-8")
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(app, "GET", "/api/licitaciones/1/ai-files")

        dispatch(handler, "GET")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        names = {item["name"]: item for item in payload["items"]}
        assert "PCAP contrato.pdf" in names
        assert "Ficha.pdf" in names
        assert "PPT antiguo.pdf" in names
        assert "HTTP.url" not in names
        assert names["PCAP contrato.pdf"]["selected_by_default"] is True
        assert names["Ficha.pdf"]["selected_by_default"] is False
        assert names["PPT antiguo.pdf"]["selected_by_default"] is False
        assert names["PPT antiguo.pdf"]["warning"]
        assert {"name", "extension", "modified_at", "size_bytes", "size_human", "relative_path"} <= set(names["PCAP contrato.pdf"])


def test_resolve_selected_ai_files_rejects_path_traversal_and_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    folder = tmp_path / "expediente"
    folder.mkdir()
    _write_pdf(folder / "PCAP.pdf")
    licitacion = {"ruta_carpeta": str(folder)}

    with pytest.raises(AIFileSelectionError):
        resolve_selected_ai_files(licitacion, ["..\\fuera.pdf"], max_file_mb=45)
    with pytest.raises(AIFileSelectionError):
        resolve_selected_ai_files(licitacion, [str(tmp_path / "expediente" / "PCAP.pdf")], max_file_mb=45)
    with pytest.raises(AIFileSelectionError):
        resolve_selected_ai_files(licitacion, ["C:PCAP.pdf"], max_file_mb=45)

    selected = resolve_selected_ai_files(licitacion, ["PCAP.pdf"], max_file_mb=45)
    assert selected[0]["name"] == "PCAP.pdf"


def test_generate_with_manual_selection_changes_document_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf", b"uno")
    _write_pdf(tmp_path / "PPT.pdf", b"dos")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    first = request_ai_analysis(
        conn,
        1,
        requested_by="tester",
        selected_files=["PCAP.pdf"],
        provider=FakeProvider(summary_payload={"resumen_ejecutivo": {"texto": "Resumen uno."}}),
    )
    second = request_ai_analysis(
        conn,
        1,
        requested_by="tester",
        selected_files=["PPT.pdf"],
        provider=FakeProvider(summary_payload={"resumen_ejecutivo": {"texto": "Resumen dos."}}),
    )

    assert first["document_hash"] != second["document_hash"]
    rows = conn.execute("SELECT selected_documents_json FROM ai_analysis_jobs ORDER BY id").fetchall()
    assert json.loads(rows[0]["selected_documents_json"])[0]["relative_path"] == "PCAP.pdf"
    assert json.loads(rows[1]["selected_documents_json"])[0]["relative_path"] == "PPT.pdf"


def test_generate_endpoint_rejects_invalid_selected_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "docs"
        folder.mkdir()
        _write_pdf(folder / "PCAP.pdf")
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(app, "POST", "/api/licitaciones/1/ai-summary/generate", {"selected_files": ["..\\PCAP.pdf"]})

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.BAD_REQUEST
        assert "ruta no permitida" in payload["error"]
        with app.db_session() as conn:
            assert conn.execute("SELECT COUNT(*) FROM ai_analysis_jobs").fetchone()[0] == 0


def test_delete_ai_summary_does_not_delete_documents(tmp_path: Path) -> None:
    conn = _conn()
    pdf = _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    conn.execute(
        """
        INSERT INTO ai_summaries (
            licitacion_id, document_hash, provider, model, summary_json, summary_text,
            created_at, updated_at, quality_status
        )
        VALUES (1, 'hash', 'gemini', 'gemini-test', '{"resumen_ejecutivo":{"texto":"Ok"}}',
                'Ok', '2026-01-01', '2026-01-01', 'pending_review')
        """
    )

    payload = delete_ai_summary(conn, 1)

    assert payload["has_summary"] is False
    assert latest_summary(conn, 1) is None
    assert pdf.exists()


def test_ai_summary_email_without_summary_fails_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "docs"
        folder.mkdir()
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(app, "POST", "/api/licitaciones/1/ai-summary/email", {"to": "admin@example.test"})

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.BAD_REQUEST
        assert "No hay un análisis IA" in payload["error"]


def test_ai_summary_email_with_mock_smtp_sends_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    calls: list[dict[str, object]] = []

    def fake_send_notification_email_with_settings(**kwargs):
        calls.append(kwargs)
        return "2026-01-01T10:00:00", None

    monkeypatch.setattr(app, "send_notification_email_with_settings", fake_send_notification_email_with_settings)
    with temporary_app_database(app):
        folder = tmp_path / "docs"
        folder.mkdir()
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, fecha_limite, hora_limite, ruta_carpeta, estado,
                    created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', '2026-07-01', '14:00', ?, 'Importada',
                        '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
            conn.execute(
                """
                INSERT INTO ai_summaries (
                    licitacion_id, document_hash, provider, model, summary_json, summary_text,
                    created_at, updated_at, quality_status
                )
                VALUES (1, 'hash', 'gemini', 'gemini-test',
                        '{"resumen_ejecutivo":{"texto":"Resumen útil"},"alertas":["Alerta"]}',
                        'Resumen útil', '2026-01-01', '2026-01-01', 'pending_review')
                """
            )
        handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/1/ai-summary/email",
            {"to": "destino@example.test", "subject": "Análisis"},
            email="usuario@example.test",
        )

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["recipient"] == "destino@example.test"
        assert calls
        assert "Resumen útil" in calls[0]["html_body"]
        assert "Análisis automático" in calls[0]["body"]


def test_prepare_ai_workspace_copies_only_selected_and_keeps_originals(tmp_path: Path) -> None:
    source_a = _write_pdf(tmp_path / "PCAP.pdf", b"a")
    source_b = _write_pdf(tmp_path / "PPT.pdf", b"b")
    workspace_root = tmp_path / "work"

    result = prepare_ai_workspace(
        job_id=42,
        licitacion={"id": 1, "expediente": "EXP", "objeto": "Objeto"},
        selected_documents=[{"path": str(source_a), "name": "PCAP.pdf", "relative_path": "PCAP.pdf"}],
        work_root=workspace_root,
    )

    job_root = Path(result["job_root"])
    assert (job_root / "inputs" / "PCAP.pdf").exists()
    assert not (job_root / "inputs" / "PPT.pdf").exists()
    assert source_a.exists()
    assert source_b.exists()
    manifest = json.loads((job_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["job_id"] == 42
    assert manifest["files"][0]["original_relative_path"] == "PCAP.pdf"


def test_prepare_ai_workspace_resolves_name_collisions(tmp_path: Path) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    source_a = _write_pdf(folder_a / "PCAP.pdf", b"a")
    source_b = _write_pdf(folder_b / "PCAP.pdf", b"b")

    result = prepare_ai_workspace(
        job_id=43,
        licitacion={"id": 1, "expediente": "EXP"},
        selected_documents=[
            {"path": str(source_a), "name": "PCAP.pdf", "relative_path": "a\\PCAP.pdf"},
            {"path": str(source_b), "name": "PCAP.pdf", "relative_path": "b\\PCAP.pdf"},
        ],
        work_root=tmp_path / "work",
    )

    files = json.loads((Path(result["job_root"]) / "manifest.json").read_text(encoding="utf-8"))["files"]
    copied = {item["copied_path"] for item in files}
    assert "inputs/PCAP.pdf" in copied or "inputs\\PCAP.pdf" in copied
    assert any("PCAP (2).pdf" in item for item in copied)


def test_codex_local_disabled_returns_controlled_error(tmp_path: Path) -> None:
    provider = CodexLocalProvider(_ai_config(analysis_provider="codex_local", codex_local_enabled=False), job_id=1)

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents({"id": 1}, [])

    assert excinfo.value.code == "CODEX_DISABLED"


def test_codex_local_not_found_returns_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: None)
    provider = CodexLocalProvider(_ai_config(analysis_provider="codex_local", codex_local_enabled=True), job_id=1)

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents({"id": 1}, [])

    assert excinfo.value.code == "CODEX_NOT_FOUND"


def test_codex_local_subprocess_is_sandboxed_and_saves_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: "codex")
    source = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")
    calls: list[dict[str, object]] = []

    def fake_runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"resumen_ejecutivo": {"texto": "Resumen Codex"}}),
            stderr="",
        )

    provider = CodexLocalProvider(
        _ai_config(
            analysis_provider="codex_local",
            codex_local_enabled=True,
            codex_executable="codex",
            codex_timeout_seconds=33,
            codex_sandbox="read-only",
        ),
        job_id=99,
        runner=fake_runner,
    )

    result = provider.analyze_documents(
        {"id": 1, "expediente": "EXP"},
        [{"path": str(source), "name": "PCAP.pdf", "relative_path": "PCAP.pdf"}],
    )

    assert result.summary["resumen_ejecutivo"]["texto"] == "Resumen Codex"
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 33
    assert str(tmp_path / "work" / "99") == calls[0]["cwd"]
    assert (tmp_path / "work" / "99" / "result.json").exists()


def test_codex_local_invalid_stdout_is_classified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: "codex")
    source = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="no-json", stderr="")

    provider = CodexLocalProvider(
        _ai_config(analysis_provider="codex_local", codex_local_enabled=True),
        job_id=100,
        runner=fake_runner,
    )

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents(
            {"id": 1, "expediente": "EXP"},
            [{"path": str(source), "name": "PCAP.pdf", "relative_path": "PCAP.pdf"}],
        )

    assert excinfo.value.code == "INVALID_JSON"


def test_mark_interrupted_job_sets_status_and_error(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash",
        selected_documents=[],
        model="gemini-test",
        requested_by="manual_test",
        status="processing",
    )

    assert mark_interrupted_job(conn, job_id) is True

    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row["status"] == "error"
    assert row["error_code"] == "INTERRUPTED"
    assert row["finished_at"]
    assert conn.execute("SELECT COUNT(*) FROM ai_usage_log WHERE error_code = 'INTERRUPTED'").fetchone()[0] == 1


def test_manual_preflight_report_has_timeout_and_no_api_key(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")

    report = build_preflight_report(
        job_id=9,
        model="gemini-3.1-flash-lite",
        selected_documents=[{"name": "PCAP.pdf", "size_bytes": pdf.stat().st_size}],
        timeout_seconds=12,
    )

    serialized = json.dumps(report, ensure_ascii=False)
    assert report["job_id"] == 9
    assert report["GEMINI_TIMEOUT_SECONDS"] == 12
    assert report["sent_documents_count"] == 1
    assert report["total_pdf_bytes_sent"] == pdf.stat().st_size
    assert "GEMINI_API_KEY" not in serialized
    assert "secret" not in serialized.lower()


def test_parse_summary_json_fills_missing_sections() -> None:
    parsed = parse_summary_json({"metadata": {"expediente": "EXP"}, "resumen_ejecutivo": {"texto": "ok"}})

    assert parsed["metadata"]["expediente"] == "EXP"
    assert "alertas" in parsed
    assert "solvencia" in parsed


def test_ai_summary_api_without_config_returns_controlled_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "docs"
        folder.mkdir()
        _write_pdf(folder / "PCAP.pdf")
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(app, "GET", "/api/licitaciones/1/ai-summary")

        dispatch(handler, "GET")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["enabled"] is False
        assert payload["selected_documents"]


def test_ai_generate_api_with_disabled_gemini_creates_disabled_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "docs"
        folder.mkdir()
        _write_pdf(folder / "PCAP.pdf")
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
                )
                VALUES (1, 'EXP-API', 'Objeto', 'Organo', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(app, "POST", "/api/licitaciones/1/ai-summary/generate")

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["job_status"] == "disabled"
        with app.db_session() as conn:
            assert conn.execute("SELECT COUNT(*) FROM ai_analysis_jobs").fetchone()[0] == 1


def test_manual_test_exposes_force_regeneration_flag() -> None:
    source = Path("webapp/infonalia_webapp/ai/manual_test.py").read_text(encoding="utf-8")

    assert '"--force"' in source
    assert '"--timeout"' in source
    assert '"--input-mode"' in source
    assert "force=args.force" in source
    assert "mark_interrupted_job" in source
