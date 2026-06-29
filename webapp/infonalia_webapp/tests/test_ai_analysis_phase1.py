from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.ai.config import get_ai_config
from webapp.infonalia_webapp.ai.document_selector import inspect_document_selection, select_relevant_documents
from webapp.infonalia_webapp.ai.gemini_provider import (
    AIProviderError,
    ProviderResult,
    build_gemini_contents,
    classify_gemini_exception,
    parse_gemini_response,
)
from webapp.infonalia_webapp.ai.hashing import hash_documents
from webapp.infonalia_webapp.ai.queue import active_job, create_job, ensure_ai_schema, latest_summary
from webapp.infonalia_webapp.ai.rate_limit import check_rate_limit
from webapp.infonalia_webapp.ai.schemas import parse_summary_json, summary_quality_check
from webapp.infonalia_webapp.ai.service import process_ai_job, request_ai_analysis
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def teardown_function() -> None:
    for key in list(os.environ):
        if key.startswith("GEMINI_"):
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


def test_ai_config_defaults_disabled_and_does_not_expose_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    config = get_ai_config()

    assert config.enabled is False
    assert config.configured is True
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
    assert "force=args.force" in source
