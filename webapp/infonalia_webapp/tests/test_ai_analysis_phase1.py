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
from webapp.infonalia_webapp.ai.codex_local_provider import CodexLocalProvider, build_codex_command
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
from webapp.infonalia_webapp.ai.notifications import (
    create_job_notifications,
    normalize_email_list,
    notification_status_payload,
    send_pending_job_notifications,
)
from webapp.infonalia_webapp.ai.pdf_text_extractor import ExtractedTextResult, extract_pdf_text
from webapp.infonalia_webapp.ai.postprocess import postprocess_summary
from webapp.infonalia_webapp.ai.queue import active_job, create_job, ensure_ai_schema, latest_job, latest_summary, save_summary, update_job
from webapp.infonalia_webapp.ai.rate_limit import check_rate_limit
from webapp.infonalia_webapp.ai.schemas import parse_summary_json, summary_quality_check
from webapp.infonalia_webapp.ai.service import cancel_ai_job, delete_ai_summary, dismiss_ai_job, dismiss_finished_ai_jobs, get_ai_queue_payload, get_ai_summary_payload, mark_stale_ai_jobs, process_ai_job, request_ai_analysis
from webapp.infonalia_webapp.ai.worker import mark_stale_jobs, process_one_job
from webapp.infonalia_webapp.ai.worker_launcher import start_ai_worker_for_job
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


def _insert_app_licitacion_for_ai(conn: sqlite3.Connection, folder: Path, licitacion_id: int = 1) -> None:
    conn.execute(
        """
        INSERT INTO licitaciones (
            id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at
        )
        VALUES (?, 'EXP-COLA', 'Suministro cola IA', 'Organo de prueba', ?, 'Importada', '2026-01-01', '2026-01-01')
        """,
        (licitacion_id, str(folder)),
    )


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\ncontenido\n") -> Path:
    path.write_bytes(content)
    return path


def _useful_summary_payload(text: str | None = None) -> dict[str, object]:
    summary_text = text or "Resumen generado por mock."
    return {
        "metadata": {
            "expediente": "EXP-IA",
            "titulo": "Suministro de prueba",
            "organismo": "Organo de prueba",
            "provincia": "Madrid",
            "plataforma": "PLACE",
            "fecha_limite_presentacion": "01/07/2026",
            "hora_limite_presentacion": "14:00",
            "tipo_contrato": "Suministro",
        },
        "resumen_ejecutivo": {
            "texto": summary_text,
            "aspectos_clave": ["Dos sobres electrónicos", "Plazo de entrega de 48 horas"],
        },
        "caracteristicas": {
            "presupuesto_base": 12000,
            "valor_estimado": 14000,
            "moneda": "EUR",
            "plazo_ejecucion_inicial": "12 meses",
            "prorrogas": {"existen": True, "detalle": "Una prórroga posible."},
            "adjudicacion": "Expediente completo",
            "numero_sobres": 2,
        },
        "lotes": [
            {
                "numero_lote": "1",
                "denominacion": "Productos de alimentación",
                "presupuesto": 12000,
                "valor_estimado": 14000,
                "duracion": "12 meses",
                "observaciones": "Oferta completa del lote.",
                "fuente": "PCAP, página 5",
            }
        ],
        "productos": [
            {
                "lote": "1",
                "codigo": "P-01",
                "descripcion": "Aceite de oliva virgen extra",
                "unidad": "Botella 1 l",
                "cantidad_estimada": 500,
                "precio_unitario_maximo": 8.5,
                "importe_estimado": 4250,
                "especificaciones_relevantes": "Envase reciclable.",
                "fuente": "PPT, página 12",
            }
        ],
        "presentacion_documentacion": {
            "forma_presentacion": "Electrónica",
            "documentacion_administrativa": ["DEUC"],
            "documentacion_tecnica": ["Memoria técnica"],
            "documentacion_economica": ["Oferta económica"],
            "anexos_relevantes": ["Anexo I"],
        },
        "muestras_fichas_memoria": {
            "muestras": {"exigidas": False, "momento": "", "detalle": "", "consecuencia_no_presentar": ""},
            "fichas_tecnicas": {"exigidas": True, "sobre": "Sobre técnico", "detalle": "Aportar fichas técnicas de producto."},
            "memoria_tecnica": {"exigida": True, "detalle": "Memoria con metodología de suministro."},
            "adscripcion_medios": {"exigida": False, "detalle": ""},
        },
        "criterios_adjudicacion": {
            "juicio_valor": [{"nombre": "Memoria técnica", "puntuacion_maxima": 20, "descripcion": "Calidad de la propuesta."}],
            "formulas": [{"nombre": "Precio", "puntuacion_maxima": 80, "formula": "Mejor precio obtiene máxima puntuación."}],
            "total_puntos": 100,
            "observaciones": "Separar documentación técnica y económica.",
        },
        "solvencia": {
            "economica": [{"objeto": "Volumen anual", "importe_minimo": 10000, "detalle": "Acreditar solvencia económica."}],
            "tecnica": [{"objeto": "Suministros similares", "detalle": "Relación de suministros realizados."}],
        },
        "condiciones_especiales_ejecucion": [
            {
                "categoria": "Social",
                "obligacion": "Cumplimiento laboral",
                "consecuencia_incumplimiento": "Penalidad prevista en el PCAP",
                "fuente": "PCAP, página 31",
            }
        ],
        "observaciones_operativas": {
            "lugar_entrega": ["Centro indicado en pedido"],
            "horario_entrega": ["Horario de mañana"],
            "plazo_entrega": ["48 horas desde pedido"],
            "transporte": "A cargo del adjudicatario",
        },
        "puntos_atencion": [
            {
                "titulo": "Oferta por lote completo",
                "detalle": "No se admiten ofertas parciales dentro del lote.",
                "fuente": "PCAP, página 8",
            }
        ],
        "fuentes_consultadas": [
            {"documento": "PCAP.pdf", "tipo": "PCAP", "paginas_relevantes": [5, 8, 31]},
            {"documento": "PPT.pdf", "tipo": "PPT", "paginas_relevantes": [12]},
        ],
        "control_calidad": {"campos_no_encontrados": [], "campos_con_baja_confianza": [], "advertencias": []},
    }


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
            summary=_useful_summary_payload(),
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


def test_ai_provider_blank_env_means_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "")

    config = get_ai_config()

    assert config.active_provider == "disabled"
    assert config.provider_enabled is False
    assert config.provider_status_label == "IA desactivada"


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
    parsed = parse_summary_json(_useful_summary_payload())

    result = summary_quality_check(parsed)

    assert result["is_useful"] is True
    assert result["status"] == "ok"
    assert "resumen_ejecutivo.texto" in result["signals"]
    assert result["has_criterios"] is True
    assert result["has_alertas"] is True


def test_summary_quality_rejects_low_quality_json() -> None:
    parsed = parse_summary_json({"resumen_ejecutivo": {"texto": "Hay contenido útil, pero insuficiente."}})

    result = summary_quality_check(parsed)

    assert result["is_useful"] is False
    assert result["status"] == "low_quality_analysis"


def test_summary_quality_rejects_mojibake() -> None:
    payload = _useful_summary_payload("LicitaciÃ³n pÃºblica con garantÃ­a y adjudicaciÃ³n mal codificadas.")
    parsed = parse_summary_json(payload)

    result = summary_quality_check(parsed)

    assert result["is_useful"] is False
    assert result["status"] == "encoding_error"
    assert result["contains_mojibake"] is True


def test_postprocess_removes_recommendations_and_keeps_factual_information() -> None:
    summary = parse_summary_json(
        {
            "metadata": {"plataforma": "Junta de Andalucía", "hora_limite_presentacion": "14:00"},
            "resumen_ejecutivo": {"texto": "La licitación se adjudica con criterio precio y exige revisión documental."},
            "acciones_recomendadas": [{"accion": "Revisar anexos", "motivo": "Evitar omisiones."}],
            "alertas": [
                {
                    "titulo": "Muestras obligatorias",
                    "descripcion": "Se exigen muestras etiquetadas.",
                    "accion_recomendada": "Preparar muestras.",
                }
            ],
            "garantias": {"garantia_definitiva": {"exigida": True}},
            "muestras_fichas_memoria": {
                "fichas_tecnicas": {"exigidas": True, "detalle": "Fichas por producto."},
                "muestras": {"exigidas": True, "detalle": "Muestras etiquetadas."},
            },
            "criterios_adjudicacion": {"juicio_valor": [], "formulas": [], "total_puntos": 100},
        }
    )

    processed = postprocess_summary(summary)

    point_titles = {item["titulo"] for item in processed["puntos_atencion"]}
    warnings = processed["control_calidad"]["advertencias"]
    assert "Muestras obligatorias" in point_titles
    assert "acciones_recomendadas" not in processed
    assert "alertas" not in processed
    assert "accion_recomendada" not in processed["puntos_atencion"][0]
    assert any("criterios" in item.lower() for item in warnings)


def test_ai_queue_payload_counts_active_and_estimates(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    pdf = _write_pdf(tmp_path / "PCAP.pdf")
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash",
        selected_documents=[{"name": "PCAP.pdf", "path": str(pdf), "relative_path": "PCAP.pdf"}],
        model="codex",
        provider="codex_local",
        status="pending",
    )

    payload = get_ai_queue_payload(conn)

    assert payload["counts"]["active"] == 1
    assert payload["counts"]["pending"] == 1
    assert payload["active_jobs"][0]["id"] == job_id
    assert payload["active_jobs"][0]["estimated_label"] == "4-7 min aprox."
    assert payload["active_jobs"][0]["progress_label"] == "En cola"


def test_ai_queue_payload_exposes_safe_codex_error_diagnostic(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash-error",
        selected_documents=[],
        model="codex",
        provider="codex_local",
        status="pending",
    )
    update_job(
        conn,
        job_id,
        status="error",
        error_code="CODEX_ERROR",
        error_message="Codex Local terminó con error.",
        raw_usage_json=json.dumps(
            {
                "diagnostics": {
                    "returncode": 1,
                    "stderr_preview": "access_token=very-secret-value\n401 Unauthorized",
                }
            }
        ),
    )

    payload = get_ai_queue_payload(conn)

    diagnostic = payload["recent_jobs"][0]["error_diagnostic"]
    assert diagnostic["code"] == "CODEX_ERROR"
    assert diagnostic["returncode"] == 1
    assert "sesión de Codex" in diagnostic["hint"]
    assert "very-secret-value" not in diagnostic["detail"]
    assert "[oculto]" in diagnostic["detail"]


def test_dismiss_finished_ai_jobs_preserves_every_active_status(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    job_ids: dict[str, int] = {}
    for status in ("pending", "queued", "processing", "deferred", "completed", "error", "cancelled"):
        job_ids[status] = create_job(
            conn,
            licitacion_id=1,
            document_hash=f"hash-{status}",
            selected_documents=[],
            model="codex",
            provider="codex_local",
            status=status,
        )

    result = dismiss_finished_ai_jobs(conn, dismissed_by="nuria")

    assert result["ok"] is True
    assert result["dismissed"] == 3
    rows = {
        row["status"]: row
        for row in conn.execute("SELECT status, dismissed_at, dismissed_by FROM ai_analysis_jobs").fetchall()
    }
    for status in ("pending", "queued", "processing", "deferred"):
        assert not rows[status]["dismissed_at"]
        assert not rows[status]["dismissed_by"]
    for status in ("completed", "error", "cancelled"):
        assert rows[status]["dismissed_at"]
        assert rows[status]["dismissed_by"] == "nuria"
    payload = get_ai_queue_payload(conn)
    assert {job["status"] for job in payload["active_jobs"]} == {"pending", "queued", "processing", "deferred"}
    assert payload["recent_jobs"] == []


def test_ai_queue_endpoint_returns_active_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (id, expediente, objeto, estado, created_at, updated_at)
                VALUES (1, 'EXP-COLA', 'Objeto cola', 'Importada', '2026-01-01', '2026-01-01')
                """
            )
            create_job(
                conn,
                licitacion_id=1,
                document_hash="hash",
                selected_documents=[],
                model="codex",
                provider="codex_local",
                status="pending",
            )
        handler = make_handler(app, "GET", "/api/ai/queue", email="admin@example.test")

        dispatch(handler, "GET")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["counts"]["active"] == 1
        assert payload["active_jobs"][0]["expediente"] == "EXP-COLA"


def test_ai_queue_dismiss_finished_endpoint_keeps_active_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "cola-limpieza"
        folder.mkdir()
        with app.db_session() as conn:
            _insert_app_licitacion_for_ai(conn, folder)
            for status in ("pending", "processing", "completed", "error", "cancelled"):
                create_job(
                    conn,
                    licitacion_id=1,
                    document_hash=f"endpoint-{status}",
                    selected_documents=[],
                    model="codex",
                    provider="codex_local",
                    status=status,
                )

        handler = make_handler(app, "POST", "/api/ai/queue/dismiss-finished", {}, username="nuria")
        dispatch(handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert handler.responses[-1][1]["ok"] is True
        assert handler.responses[-1][1]["dismissed"] == 3
        with app.db_session() as conn:
            visible = get_ai_queue_payload(conn)
            assert {job["status"] for job in visible["active_jobs"]} == {"pending", "processing"}
            assert visible["recent_jobs"] == []
            hidden_by = {
                row["status"]: row["dismissed_by"]
                for row in conn.execute("SELECT status, dismissed_by FROM ai_analysis_jobs").fetchall()
            }
            assert hidden_by["pending"] in (None, "")
            assert hidden_by["processing"] in (None, "")
            assert hidden_by["completed"] == "nuria"
            assert hidden_by["error"] == "nuria"
            assert hidden_by["cancelled"] == "nuria"


def test_ai_cancel_pending_and_processing(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    pending_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash-pending",
        selected_documents=[],
        model="codex",
        provider="codex_local",
        status="pending",
    )
    processing_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash-processing",
        selected_documents=[],
        model="codex",
        provider="codex_local",
        status="processing",
    )

    cancelled = cancel_ai_job(conn, pending_id)
    requested = cancel_ai_job(conn, processing_id)

    pending = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (pending_id,)).fetchone()
    processing = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (processing_id,)).fetchone()
    assert cancelled["job"]["status"] == "cancelled"
    assert pending["progress_stage"] == "cancelled"
    assert requested["ok"] is True
    assert processing["cancel_requested"] == 1


def test_ai_cancel_endpoint_handles_pending_processing_completed_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    launched: list[int] = []
    monkeypatch.setattr(app, "start_ai_worker_for_job", lambda conn, job_id: launched.append(job_id))
    with temporary_app_database(app):
        folder = tmp_path / "cola"
        folder.mkdir()
        with app.db_session() as conn:
            _insert_app_licitacion_for_ai(conn, folder)
            pending_id = create_job(
                conn,
                licitacion_id=1,
                document_hash="hash-pending",
                selected_documents=[],
                model="codex",
                provider="codex_local",
                status="pending",
            )
            processing_id = create_job(
                conn,
                licitacion_id=1,
                document_hash="hash-processing",
                selected_documents=[],
                model="codex",
                provider="codex_local",
                status="processing",
            )
            completed_id = create_job(
                conn,
                licitacion_id=1,
                document_hash="hash-completed",
                selected_documents=[],
                model="codex",
                provider="codex_local",
                status="completed",
            )

        pending_handler = make_handler(app, "POST", f"/api/ai/jobs/{pending_id}/cancel", {})
        processing_handler = make_handler(app, "POST", f"/api/ai/jobs/{processing_id}/cancel", {})
        completed_handler = make_handler(app, "POST", f"/api/ai/jobs/{completed_id}/cancel", {})
        missing_handler = make_handler(app, "POST", "/api/ai/jobs/999999/cancel", {})

        dispatch(pending_handler, "POST")
        dispatch(processing_handler, "POST")
        dispatch(completed_handler, "POST")
        dispatch(missing_handler, "POST")

        assert pending_handler.responses[-1][0] == HTTPStatus.OK
        assert pending_handler.responses[-1][1]["ok"] is True
        assert pending_handler.responses[-1][1]["job"]["status"] == "cancelled"
        assert processing_handler.responses[-1][0] == HTTPStatus.OK
        assert processing_handler.responses[-1][1]["ok"] is True
        assert processing_handler.responses[-1][1]["job"]["status"] == "processing"
        assert completed_handler.responses[-1][0] == HTTPStatus.OK
        assert completed_handler.responses[-1][1]["ok"] is True
        assert completed_handler.responses[-1][1]["message"] == "El trabajo ya no está activo."
        assert missing_handler.responses[-1] == (
            HTTPStatus.NOT_FOUND,
            {
                "ok": False,
                "job_id": 999999,
                "error_code": "JOB_NOT_FOUND",
                "error_message": "Trabajo IA no encontrado.",
            },
        )
        assert launched == []
        with app.db_session() as conn:
            pending = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (pending_id,)).fetchone()
            processing = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (processing_id,)).fetchone()
            assert pending["status"] == "cancelled"
            assert pending["progress_message"] == "Cancelado por el usuario."
            assert processing["status"] == "processing"
            assert processing["cancel_requested"] == 1


def test_ai_dismiss_endpoint_marks_job_without_deleting_summary_or_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        folder = tmp_path / "expediente"
        folder.mkdir()
        document = _write_pdf(folder / "PCAP.pdf")
        with app.db_session() as conn:
            _insert_app_licitacion_for_ai(conn, folder)
            job_id = create_job(
                conn,
                licitacion_id=1,
                document_hash="hash-dismiss",
                selected_documents=[],
                model="codex",
                provider="codex_local",
                status="completed",
            )
            save_summary(
                conn,
                licitacion_id=1,
                document_hash="hash-dismiss",
                model="codex",
                summary=_useful_summary_payload(),
                text="Resumen",
                job_id=job_id,
                provider="codex_local",
            )

        handler = make_handler(app, "POST", f"/api/ai/jobs/{job_id}/dismiss", {}, username="manolo")
        missing_handler = make_handler(app, "POST", "/api/ai/jobs/999999/dismiss", {})

        dispatch(handler, "POST")
        dispatch(missing_handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert handler.responses[-1][1]["ok"] is True
        assert handler.responses[-1][1]["job_id"] == job_id
        assert missing_handler.responses[-1] == (
            HTTPStatus.NOT_FOUND,
            {
                "ok": False,
                "job_id": 999999,
                "error_code": "JOB_NOT_FOUND",
                "error_message": "Trabajo IA no encontrado.",
            },
        )
        assert document.exists()
        with app.db_session() as conn:
            row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
            assert row["dismissed_at"]
            assert row["dismissed_by"] == "manolo"
            assert conn.execute("SELECT COUNT(*) FROM ai_summaries").fetchone()[0] == 1


def test_ai_queue_endpoints_return_json_on_internal_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("simulated schema issue")

    monkeypatch.setattr(app, "cancel_ai_job", boom)
    monkeypatch.setattr(app, "dismiss_ai_job", boom)
    monkeypatch.setattr(app, "dismiss_finished_ai_jobs", boom)
    monkeypatch.setattr(app, "get_ai_queue_payload", boom)
    monkeypatch.setattr(app, "get_ai_job_payload", boom)

    cancel_handler = make_handler(app, "POST", "/api/ai/jobs/7/cancel", {})
    dismiss_handler = make_handler(app, "POST", "/api/ai/jobs/7/dismiss", {})
    dismiss_finished_handler = make_handler(app, "POST", "/api/ai/queue/dismiss-finished", {})
    queue_handler = make_handler(app, "GET", "/api/ai/queue", {})
    job_handler = make_handler(app, "GET", "/api/ai/jobs/7", {})

    dispatch(cancel_handler, "POST")
    dispatch(dismiss_handler, "POST")
    dispatch(dismiss_finished_handler, "POST")
    dispatch(queue_handler, "GET")
    dispatch(job_handler, "GET")

    assert cancel_handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert cancel_handler.responses[-1][1]["ok"] is False
    assert cancel_handler.responses[-1][1]["error_code"] == "AI_CANCEL_ERROR"
    assert dismiss_handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert dismiss_handler.responses[-1][1]["ok"] is False
    assert dismiss_handler.responses[-1][1]["error_code"] == "AI_DISMISS_ERROR"
    assert dismiss_finished_handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert dismiss_finished_handler.responses[-1][1]["ok"] is False
    assert dismiss_finished_handler.responses[-1][1]["error_code"] == "AI_DISMISS_FINISHED_ERROR"
    assert queue_handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert queue_handler.responses[-1][1]["ok"] is False
    assert queue_handler.responses[-1][1]["error_code"] == "AI_QUEUE_ERROR"
    assert job_handler.responses[-1][0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert job_handler.responses[-1][1]["ok"] is False
    assert job_handler.responses[-1][1]["error_code"] == "AI_QUEUE_ERROR"


def test_mark_stale_jobs_handles_processing_and_old_pending(tmp_path: Path) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    processing_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash-processing",
        selected_documents=[],
        model="codex",
        provider="codex_local",
        status="processing",
        created_at="2026-01-01T10:00:00",
    )
    pending_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash-pending",
        selected_documents=[],
        model="codex",
        provider="codex_local",
        status="pending",
        created_at="2026-01-01T10:00:00",
    )
    update_job(conn, processing_id, started_at="2026-01-01T10:00:00", heartbeat_at="2026-01-01T10:00:00")

    result = mark_stale_ai_jobs(conn, timeout_seconds=60)

    assert result["marked"] == 2
    processing = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (processing_id,)).fetchone()
    pending = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (pending_id,)).fetchone()
    assert processing["error_code"] == "STALE_JOB"
    assert pending["error_code"] == "STALE_PENDING_JOB"


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


def test_document_selector_resolves_legacy_month_route_inside_year_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "Dropbox" / "00000 LLANGON"
    folder = base / "2026" / "07 JULIO" / "02 JULIO 2359 JAEN MARTOS 20264096"
    folder.mkdir(parents=True)
    _write_pdf(folder / "DOC20260615135002PCAP.pdf")
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(base))

    result = inspect_document_selection(
        {"ruta_carpeta": r"07 JULIO\02 JULIO 2359 JAEN MARTOS 20264096"},
        max_documents=4,
        max_file_mb=45,
    )

    assert result["diagnostics"]["resolved_path"] == str(folder)
    assert result["diagnostics"]["resolved_exists"] is True
    assert [item["name"] for item in result["selected_documents"]] == ["DOC20260615135002PCAP.pdf"]


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
    assert payload["active_provider"] == "gemini"
    assert payload["job_status"] == "pending"
    assert provider.calls == 0
    processed = process_ai_job(conn, payload["job_id"], provider=provider)
    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "GEMINI_DISABLED"
    assert provider.calls == 0


def test_codex_local_disabled_does_not_call_gemini_or_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    provider = FakeProvider()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "codex_local")
    monkeypatch.setenv("CODEX_LOCAL_ENABLED", "false")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["active_provider"] == "codex_local"
    assert payload["provider_enabled"] is False
    assert payload["provider_status_label"] == "Codex Local desactivado"
    assert payload["job_status"] == "pending"
    assert payload["job"]["provider"] == "codex_local"
    assert provider.calls == 0
    processed = process_ai_job(conn, payload["job_id"], provider=provider)
    assert processed["job_status"] == "error"
    assert processed["job"]["provider"] == "codex_local"
    assert processed["job"]["error_code"] == "CODEX_DISABLED"
    assert processed["job"]["error_message"] == "Codex Local no está activado."
    assert provider.calls == 0


def test_service_processes_job_with_mock_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    provider = FakeProvider()
    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["job_status"] == "pending"
    assert provider.calls == 0
    processed = process_ai_job(conn, payload["job_id"], provider=provider)
    assert processed["has_summary"] is True
    assert processed["summary"]["summary_text"] == "Resumen generado por mock."
    assert processed["job"]["progress_stage"] == "completed"
    assert processed["job"]["progress_percent"] == 100
    assert processed["job"]["elapsed_seconds"] >= 0
    assert conn.execute("SELECT COUNT(*) FROM ai_usage_log").fetchone()[0] == 1


def test_generate_creates_pending_job_without_running_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    provider = FakeProvider()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)

    assert payload["ok"] is True
    assert payload["job_id"]
    assert payload["job_status"] == "pending"
    assert payload["message"] == "Análisis IA en cola."
    assert provider.calls == 0
    row = conn.execute("SELECT status, provider FROM ai_analysis_jobs WHERE id = ?", (payload["job_id"],)).fetchone()
    assert dict(row) == {"status": "pending", "provider": "gemini"}


def test_email_list_normalization_accepts_common_separators_and_rejects_invalid() -> None:
    assert normalize_email_list(
        "Info3@Llangon.com, info@llangon.com; info3@llangon.com\nmailto:nuria@example.test",
        required=True,
    ) == ["info3@llangon.com", "info@llangon.com", "nuria@example.test"]
    assert normalize_email_list(["[Aviso](mailto:aviso@example.test)"]) == ["aviso@example.test"]
    assert normalize_email_list("", required=False) == []
    with pytest.raises(ValueError, match="Email no válido"):
        normalize_email_list("correcto@example.test; no-es-email", required=True)
    with pytest.raises(ValueError, match="Indica al menos un email"):
        normalize_email_list("", required=True)


def test_generate_with_email_notice_creates_pending_notifications(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        notify_on_completion=True,
        notification_emails="Info3@Llangon.com; info3@llangon.com\nnuria@example.test",
    )

    assert payload["notification_recipients_count"] == 2
    assert payload["notification_status"]["pending_count"] == 2
    rows = conn.execute("SELECT recipient_email, status FROM ai_analysis_notifications ORDER BY id").fetchall()
    assert [dict(row) for row in rows] == [
        {"recipient_email": "info3@llangon.com", "status": "pending"},
        {"recipient_email": "nuria@example.test", "status": "pending"},
    ]


def test_worker_processes_pending_job_with_mock_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    payload = request_ai_analysis(conn, 1, requested_by="tester")

    processed = process_ai_job(conn, payload["job_id"], provider=FakeProvider())

    assert processed["job_status"] == "completed"
    assert processed["has_summary"] is True
    row = conn.execute("SELECT status, attempts FROM ai_analysis_jobs WHERE id = ?", (payload["job_id"],)).fetchone()
    assert row["status"] == "completed"
    assert row["attempts"] == 1


def test_worker_completed_keeps_analysis_completed_when_smtp_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        notify_on_completion=True,
        notification_emails="aviso@example.test",
    )

    processed = process_ai_job(conn, payload["job_id"], provider=FakeProvider())

    assert processed["job_status"] == "completed"
    assert processed["notification_status"]["state"] == "error"
    notification = conn.execute(
        "SELECT status, attempts, error_message FROM ai_analysis_notifications WHERE job_id = ?",
        (payload["job_id"],),
    ).fetchone()
    assert notification["status"] == "error"
    assert notification["attempts"] == 1
    assert notification["error_message"] == "SMTP no configurado"
    assert latest_summary(conn, 1) is not None


def test_worker_respects_cancel_requested_before_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider()
    payload = request_ai_analysis(
        conn,
        1,
        requested_by="tester",
        notify_on_completion=True,
        notification_emails="aviso@example.test",
    )
    update_job(conn, payload["job_id"], cancel_requested=1)

    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "cancelled"
    assert provider.calls == 0
    assert latest_summary(conn, 1) is None
    notification = conn.execute("SELECT status FROM ai_analysis_notifications").fetchone()
    assert notification["status"] == "skipped"


def test_worker_does_not_save_summary_or_send_email_if_cancelled_after_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        notify_on_completion=True,
        notification_emails="aviso@example.test",
    )
    sent: list[int] = []

    class CancellingProvider(FakeProvider):
        def analyze_documents(self, licitacion: dict[str, object], documents: list[dict[str, object]]) -> ProviderResult:
            result = super().analyze_documents(licitacion, documents)
            update_job(conn, payload["job_id"], cancel_requested=1)
            return result

    processed = process_ai_job(
        conn,
        payload["job_id"],
        provider=CancellingProvider(),
        notification_sender=lambda _conn, job_id: sent.append(job_id),
    )

    assert processed["job_status"] == "cancelled"
    assert latest_summary(conn, 1) is None
    assert sent == []
    notification = conn.execute("SELECT status FROM ai_analysis_notifications").fetchone()
    assert notification["status"] == "skipped"


def test_worker_does_not_process_same_job_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    payload = request_ai_analysis(conn, 1, requested_by="tester")
    conn.execute("UPDATE ai_analysis_jobs SET status = 'processing', started_at = '2026-01-01T10:00:00' WHERE id = ?", (payload["job_id"],))
    provider = FakeProvider()

    result = process_ai_job(conn, payload["job_id"], provider=provider)

    assert result["job_status"] == "processing"
    assert provider.calls == 0


def test_service_marks_429_as_deferred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    provider = FakeProvider(error=AIProviderError("429", code="RESOURCE_EXHAUSTED"))
    payload = request_ai_analysis(
        conn,
        1,
        requested_by="tester",
        provider=provider,
    )
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "deferred"
    assert processed["job"]["error_code"] == "RESOURCE_EXHAUSTED"


def test_service_marks_invalid_json_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    provider = FakeProvider(invalid=True)
    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "INVALID_JSON"


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
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "EMPTY_ANALYSIS"
    assert processed["job"]["summary_quality_status"] == "empty_analysis"
    assert processed["job"]["sent_documents_count"] == 1
    assert latest_summary(conn, 1) is None


def test_service_rejects_low_quality_analysis_without_saving_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(summary_payload={"resumen_ejecutivo": {"texto": "Resumen demasiado pobre."}})

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "LOW_QUALITY_ANALYSIS"
    assert processed["job"]["summary_quality_status"] == "low_quality_analysis"
    assert latest_summary(conn, 1) is None


def test_service_rejects_encoding_error_without_saving_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(summary_payload=_useful_summary_payload("LicitaciÃ³n pÃºblica con garantÃ­a mal codificada."))

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "ENCODING_ERROR"
    assert processed["job"]["summary_quality_status"] == "encoding_error"
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
    provider = FakeProvider(summary_payload=_useful_summary_payload("Resumen regenerado."))

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert provider.calls == 1
    assert processed["job_status"] == "completed"
    assert processed["summary"]["summary_text"] == "Resumen regenerado."


def test_service_saves_useful_summary_after_quality_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = FakeProvider(
        summary_payload=_useful_summary_payload("Análisis útil."),
        raw_usage={
            "sent_documents_count": 1,
            "sent_documents_names": ["PCAP.pdf"],
            "total_pdf_bytes_sent": 123,
            "parse_diagnostics": {"text_length": 128, "raw_response_preview": '{"resumen_ejecutivo":{}}'},
        },
    )

    payload = request_ai_analysis(conn, 1, requested_by="tester", provider=provider)
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "completed"
    assert processed["has_summary"] is True
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
    processed = process_ai_job(conn, payload["job_id"], provider=provider)

    assert processed["job_status"] == "error"
    assert processed["job"]["error_code"] == "INVALID_JSON"
    assert processed["job"]["raw_response_preview"] == "[{}]"
    assert processed["job"]["parse_attempts"] == ["response.text:root_type:list"]


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
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash",
        selected_documents=[{"name": "PCAP.pdf", "path": str(pdf), "relative_path": "PCAP.pdf"}],
        model="gemini-test",
        provider="gemini",
        status="error",
        error_code="PROVIDER_ERROR",
        error_message="Error consultando Gemini.",
    )
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
    assert payload["job_status"] == ""
    assert payload["job"] is None
    assert payload["dismissed_jobs"] == 1
    assert latest_summary(conn, 1) is None
    assert latest_job(conn, 1) is None
    row = conn.execute("SELECT * FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row["dismissed_at"]
    assert row["dismissed_by"] == "delete_ai_summary"
    assert pdf.exists()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("DELETE", "/api/licitaciones/1/ai-summary", {}),
        ("POST", "/api/licitaciones/1/ai-summary/email", {"to": "admin@example.test"}),
        ("POST", "/api/licitaciones/1/ai-summary/save-pdf", {}),
        ("POST", "/api/licitaciones/1/ai-summary/regenerate", {}),
    ],
)
def test_ai_summary_effect_routes_require_admin(method: str, path: str, payload: dict[str, object]) -> None:
    app = load_app_module()
    handler = make_handler(
        app,
        method,
        path,
        payload,
        username="reviewer_test",
        role="nuria",
    )

    dispatch(handler, method)

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN


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

    def fake_generate_pdf_and_email(conn, *, licitacion_id, recipients, requested_by, now, subject_override="", **kwargs):
        summary_row = conn.execute(
            "SELECT created_from_job_id FROM ai_summaries WHERE licitacion_id = ? ORDER BY id DESC LIMIT 1",
            (licitacion_id,),
        ).fetchone()
        job_id = int(summary_row["created_from_job_id"])
        create_job_notifications(
            conn,
            job_id=job_id,
            licitacion_id=licitacion_id,
            requested_by=requested_by,
            recipients=recipients,
            created_at=now(),
            manual=True,
        )
        calls.append(
            {
                "job_id": job_id,
                "licitacion_id": licitacion_id,
                "recipients": list(recipients),
                "requested_by": requested_by,
                "subject_override": subject_override,
                **kwargs,
            }
        )
        conn.execute(
            """
            UPDATE ai_analysis_notifications
            SET status = 'sent', sent_at = '2026-01-01T10:00:00', attempts = attempts + 1
            WHERE job_id = ? AND status = 'pending'
            """,
            (job_id,),
        )
        return {"sent": 2, "error": 0, "job_id": job_id, "pdf_path": str(tmp_path / "docs" / "Resumen IA - EXP-API.pdf"), "pdf_warning": "", "pdf_error": ""}

    monkeypatch.setattr(app, "generate_ai_summary_pdf_and_email", fake_generate_pdf_and_email)
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
            job_id = create_job(
                conn,
                licitacion_id=1,
                document_hash="hash",
                selected_documents=[],
                model="gemini-test",
                provider="gemini",
                status="completed",
            )
            summary_json = json.dumps(_useful_summary_payload("Resumen útil con información técnica y garantía."), ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO ai_summaries (
                    licitacion_id, document_hash, provider, model, summary_json, summary_text,
                    created_at, updated_at, created_from_job_id, quality_status
                )
                VALUES (1, 'hash', 'gemini', 'gemini-test', ?, 'Resumen útil',
                        '2026-01-01', '2026-01-01', ?, 'pending_review')
                """,
                (summary_json, job_id),
            )
        handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/1/ai-summary/email",
            {"notification_emails": ["destino@example.test", "nuria@example.test"], "subject": "Análisis"},
            email="usuario@example.test",
        )

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["recipients"] == ["destino@example.test", "nuria@example.test"]
        assert payload["notification_status"]["sent_count"] == 2
        assert calls
        assert calls[0]["subject_override"] == "Análisis"
        assert calls[0]["pdf_output_root"] == app.DATA_ROOT / "runtime" / "ai_summary_pdfs"


def test_ai_pending_notifications_send_summary_email_without_raw_json_or_paths(tmp_path: Path) -> None:
    os.environ["LLANGON_DROPBOX_BASE_PATH"] = str(tmp_path)
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    conn.execute(
        """
        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, '2026-01-01')",
        [
            ("smtp_host", "smtp.example.test"),
            ("smtp_port", "2525"),
            ("smtp_from", "ia@example.test"),
            ("smtp_tls", "0"),
            ("smtp_ssl", "0"),
        ],
    )
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash",
        selected_documents=[{"name": "PCAP.pdf", "path": str(tmp_path / "PCAP.pdf")}],
        model="gemini-test",
        provider="gemini",
        status="completed",
    )
    save_summary(
        conn,
        licitacion_id=1,
        document_hash="hash",
        model="gemini-test",
        summary=_useful_summary_payload("Resumen útil con información técnica y garantías."),
        text="Resumen útil",
        job_id=job_id,
        provider="gemini",
    )
    create_job_notifications(
        conn,
        job_id=job_id,
        licitacion_id=1,
        requested_by="tester",
        recipients=["destino@example.test"],
        created_at="2026-01-01T10:00:00",
    )
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self) -> None:
            raise AssertionError("TLS desactivado")

        def login(self, *_args) -> None:
            raise AssertionError("login no configurado")

        def send_message(self, message) -> None:
            sent_messages.append(message)

    result = send_pending_job_notifications(
        conn,
        job_id,
        now=lambda: "2026-01-01T10:05:00",
        pdf_output_root=tmp_path / "runtime",
        smtp_factory=FakeSMTP,
        smtp_ssl_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no ssl")),
    )

    assert result["sent"] == 1
    assert result["error"] == 0
    assert result["pdf_error"] == ""
    assert Path(result["pdf_path"]).is_file()
    assert sent_messages
    message = sent_messages[0]
    text_body = message.get_body(preferencelist=("plain",)).get_content()
    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert "Resumen IA adjunto" in html_body
    assert "garant" in text_body
    assert '"resumen_ejecutivo"' not in text_body + html_body
    assert str(tmp_path) not in text_body + html_body
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename().endswith(".pdf")
    notification_rows = conn.execute("SELECT * FROM ai_analysis_notifications WHERE job_id = ?", (job_id,)).fetchall()
    assert notification_rows[0]["pdf_path"]
    assert notification_rows[0]["pdf_generated_at"]
    assert notification_rows[0]["pdf_attached"] == 1
    assert notification_rows[0]["pdf_error"] == ""
    status = notification_status_payload(notification_rows)
    assert status["state"] == "sent"


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
    assert "extracted_text_files" in manifest
    assert "extracted_chars_by_file" in manifest
    assert "pages_by_file" in manifest
    prompt = (job_root / "prompt.md").read_text(encoding="utf-8")
    schema = json.loads((job_root / "schema.json").read_text(encoding="utf-8"))
    assert "ficha previa de interés" in prompt
    assert "No emitas decisiones preliminares" in prompt
    assert "productos" in prompt
    assert "extracted_text" in prompt
    assert "caracteristicas" in schema
    assert "observaciones_operativas" in schema
    assert isinstance(schema["criterios_adjudicacion"], dict)


def test_prepare_ai_workspace_writes_extracted_text_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")

    def fake_extract_pdf_text(*_args, **_kwargs):
        return ExtractedTextResult(
            text="Licitación pública con garantía, adjudicación e información técnica.",
            diagnostics={
                "documents_text_extracted_count": 1,
                "extracted_chars_total": 64,
                "extracted_chars_by_document": {"PCAP.pdf": 64},
                "pages_processed_by_document": {"PCAP.pdf": 3},
                "extraction_warnings": [],
            },
        )

    monkeypatch.setattr("webapp.infonalia_webapp.ai.workspace.extract_pdf_text", fake_extract_pdf_text)
    result = prepare_ai_workspace(
        job_id=44,
        licitacion={"id": 1, "expediente": "EXP"},
        selected_documents=[{"path": str(source), "name": "PCAP.pdf", "relative_path": "PCAP.pdf"}],
        work_root=tmp_path / "work",
    )

    job_root = Path(result["job_root"])
    manifest = json.loads((job_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extracted_text_files"] == ["extracted_text/PCAP.txt"] or manifest["extracted_text_files"] == ["extracted_text\\PCAP.txt"]
    assert manifest["extracted_chars_by_file"]["PCAP.pdf"] == 64
    assert manifest["pages_by_file"]["PCAP.pdf"] == 3
    extracted_path = job_root / manifest["extracted_text_files"][0]
    assert "Licitación pública" in extracted_path.read_text(encoding="utf-8")


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
    resolved_executable = str(tmp_path / "codex.CMD")
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: resolved_executable)
    source = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")
    calls: list[dict[str, object]] = []

    def fake_runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        output_name = command[command.index("--output-last-message") + 1]
        Path(kwargs["cwd"], output_name).write_text(
            json.dumps({"resumen_ejecutivo": {"texto": "Resumen Codex"}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="salida auxiliar que no es JSON",
            stderr="progreso interno",
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
    assert calls[0]["command"][0] == resolved_executable
    assert "--ignore-user-config" in calls[0]["command"]
    assert "--ephemeral" in calls[0]["command"]
    assert "--output-last-message" in calls[0]["command"]
    assert "--model" not in calls[0]["command"]
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 33
    assert str(tmp_path / "work" / "99") == calls[0]["cwd"]
    assert (tmp_path / "work" / "99" / "result.json").exists()


def test_codex_local_allows_explicit_model_override_without_loading_user_config() -> None:
    command = build_codex_command(
        _ai_config(
            analysis_provider="codex_local",
            codex_local_enabled=True,
            codex_model="gpt-explicit-test",
        ),
        executable="codex.CMD",
    )

    assert "--ignore-user-config" in command
    assert command[command.index("--model") + 1] == "gpt-explicit-test"


def test_codex_local_nonzero_exit_keeps_tail_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: str(tmp_path / "codex.CMD"))
    source = _write_pdf(tmp_path / "PCAP.pdf", b"%PDF-1.4\n")

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="salida parcial", stderr=("x" * 3500) + "\n401 Unauthorized")

    provider = CodexLocalProvider(
        _ai_config(analysis_provider="codex_local", codex_local_enabled=True),
        job_id=101,
        runner=fake_runner,
    )

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents(
            {"id": 1, "expediente": "EXP"},
            [{"path": str(source), "name": "PCAP.pdf", "relative_path": "PCAP.pdf"}],
        )

    assert excinfo.value.code == "CODEX_ERROR"
    assert excinfo.value.diagnostics["returncode"] == 1
    assert "401 Unauthorized" in excinfo.value.diagnostics["stderr_preview"]
    assert excinfo.value.diagnostics["stdout_preview"] == "salida parcial"


def test_codex_local_update_required_has_specific_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: str(tmp_path / "codex.CMD"))

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="The 'gpt-test' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.",
        )

    provider = CodexLocalProvider(
        _ai_config(analysis_provider="codex_local", codex_local_enabled=True),
        job_id=103,
        runner=fake_runner,
    )

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents({"id": 1, "expediente": "EXP"}, [])

    assert excinfo.value.code == "CODEX_UPDATE_REQUIRED"
    assert "no es compatible" in str(excinfo.value)


def test_codex_local_launch_error_is_classified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setattr("webapp.infonalia_webapp.ai.codex_local_provider.shutil.which", lambda _value: str(tmp_path / "codex.CMD"))

    def fake_runner(command, **kwargs):
        raise PermissionError("Acceso denegado")

    provider = CodexLocalProvider(
        _ai_config(analysis_provider="codex_local", codex_local_enabled=True),
        job_id=102,
        runner=fake_runner,
    )

    with pytest.raises(AIProviderError) as excinfo:
        provider.analyze_documents({"id": 1, "expediente": "EXP"}, [])

    assert excinfo.value.code == "CODEX_LAUNCH_ERROR"
    assert excinfo.value.diagnostics["os_error"] == "PermissionError"


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
    assert "puntos_atencion" in parsed
    assert "productos" in parsed
    assert "solvencia" in parsed


def test_ai_summary_ui_source_renders_operational_ficha() -> None:
    source = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    html_source = Path("webapp/infonalia_webapp/static/index.html").read_text(encoding="utf-8")

    assert "ai-ficha" in source
    assert "Resumen ejecutivo" in source
    assert "Datos clave" in source
    assert "Información relevante" in source
    assert "Productos" in source
    assert "Criterios sujetos a juicio de valor" in source
    assert "Observaciones operativas" in source
    assert "Acciones recomendadas" not in source
    assert "decision_preliminar" not in source
    assert "Ver detalles técnicos" in source
    assert "Ver JSON técnico" not in source
    assert "low_quality_analysis" in source
    assert "encoding_error" in source
    assert "ai-queue-button" in html_source
    assert "ai-queue-dialog" in html_source
    assert 'id="clear-finished-ai-queue"' in html_source
    assert "/api/ai/queue" in source
    assert "/api/ai/queue/dismiss-finished" in source
    assert "Limpiar terminados" in html_source
    assert "handleAiQueueActionError" in source
    assert "Diagnóstico del error" in source
    assert "Ver detalle técnico" in source
    assert "error_diagnostic" in source
    assert "No se pudo contactar con la web local. Comprueba que la Suite sigue arrancada." in source
    assert source.count("Failed to fetch") == 1


def test_ai_queue_modal_has_mobile_cards_and_accessible_close_behavior() -> None:
    source = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    html_source = Path("webapp/infonalia_webapp/static/index.html").read_text(encoding="utf-8")
    styles = Path("webapp/infonalia_webapp/static/styles.css").read_text(encoding="utf-8")

    assert 'aria-labelledby="ai-queue-title"' in html_source
    assert 'aria-describedby="ai-queue-description"' in html_source
    assert 'aria-label="Cerrar Cola IA"' in html_source
    assert 'aria-live="polite"' in html_source
    assert "function renderAiQueueCard(job)" in source
    assert 'class="ai-queue-card-list"' in source
    assert 'aiQueueDialog.addEventListener("close", handleAiQueueDialogClosed);' in source
    assert "#ai-queue-dialog[open]" in styles
    assert ".ai-queue-card-list" in styles
    assert ".ai-queue-table-wrap {\n    display: none;" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));" in styles
    assert "overscroll-behavior: contain;" in styles


def test_ai_summary_api_without_config_returns_controlled_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = load_app_module()
    launched: list[int] = []
    monkeypatch.setattr(
        app,
        "start_ai_worker_for_job",
        lambda conn, job_id: launched.append(job_id) or {"ok": True, "pid": 123, "log_path": "worker.log"},
    )
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


def test_ai_summary_payload_falls_back_to_saved_summary_when_current_hash_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    folder = tmp_path / "docs"
    folder.mkdir()
    _write_pdf(folder / "PCAP.pdf", b"%PDF-1.4\nversion inicial\n")
    conn = _conn()
    try:
        _insert_licitacion(conn, folder)
        save_summary(
            conn,
            licitacion_id=1,
            document_hash="hash-anterior",
            model="gemini-test",
            summary=_useful_summary_payload("Resumen guardado visible."),
            text="Resumen guardado visible.",
            job_id=1,
            provider="gemini",
            timestamp="2026-07-01T10:00:00",
        )
        _write_pdf(folder / "Anexo nuevo.pdf", b"%PDF-1.4\nnuevo\n")

        payload = get_ai_summary_payload(conn, 1)
    finally:
        conn.close()

    assert payload["has_summary"] is True
    assert payload["summary"]["summary_text"] == "Resumen guardado visible."
    assert payload["document_hash"] != "hash-anterior"


def test_ai_generate_api_with_disabled_gemini_creates_disabled_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = load_app_module()
    launched: list[int] = []
    monkeypatch.setattr(
        app,
        "start_ai_worker_for_job",
        lambda conn, job_id: launched.append(job_id) or {"ok": True, "pid": 123, "log_path": "worker.log"},
    )
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
        assert payload["active_provider"] == "gemini"
        assert payload["job_status"] == "pending"
        assert payload["job"]["provider"] == "gemini"
        assert payload["worker"]["ok"] is True
        assert launched == [payload["job_id"]]
        with app.db_session() as conn:
            assert conn.execute("SELECT COUNT(*) FROM ai_analysis_jobs").fetchone()[0] == 1


def test_ai_generate_api_codex_disabled_uses_payload_provider_without_gemini_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_LOCAL_ENABLED", "false")
    app = load_app_module()
    launched: list[int] = []
    monkeypatch.setattr(
        app,
        "start_ai_worker_for_job",
        lambda conn, job_id: launched.append(job_id) or {"ok": True, "pid": 123, "log_path": "worker.log"},
    )
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
        handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/1/ai-summary/generate",
            {"selected_files": ["PCAP.pdf"], "provider": "codex_local"},
        )

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        serialized = json.dumps(payload, ensure_ascii=False)
        assert status == HTTPStatus.OK
        assert payload["active_provider"] == "codex_local"
        assert payload["provider_enabled"] is False
        assert payload["job_status"] == "pending"
        assert payload["job"]["provider"] == "codex_local"
        assert "Gemini" not in serialized
        assert launched == [payload["job_id"]]
        with app.db_session() as conn:
            row = conn.execute("SELECT provider, status, error_code FROM ai_analysis_jobs").fetchone()
            assert dict(row) == {"provider": "codex_local", "status": "pending", "error_code": ""}


def test_ai_generate_api_rejects_unknown_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(app, "POST", "/api/licitaciones/1/ai-summary/generate", {"provider": "otro"})

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.BAD_REQUEST
        assert "Proveedor IA no válido" in payload["error"]


def test_ai_generate_api_marks_worker_start_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    app = load_app_module()
    def fail_worker(conn, job_id):
        conn.execute(
            "UPDATE ai_analysis_jobs SET status = 'error', error_code = 'WORKER_START_ERROR', error_message = 'fallo' WHERE id = ?",
            (job_id,),
        )
        return {"ok": False, "error_code": "WORKER_START_ERROR", "error_message": "fallo", "log_path": "worker.log"}

    monkeypatch.setattr(app, "start_ai_worker_for_job", fail_worker)
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
        handler = make_handler(app, "POST", "/api/licitaciones/1/ai-summary/generate", {"selected_files": ["PCAP.pdf"]})

        dispatch(handler, "POST")

        status, payload = handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["job_status"] == "error"
        assert payload["job"]["error_code"] == "WORKER_START_ERROR"
        assert payload["worker"]["ok"] is False


def test_worker_launcher_uses_popen_without_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    job_id = create_job(conn, licitacion_id=1, document_hash="hash", selected_documents=[], model="gemini-test")
    calls: list[dict[str, object]] = []

    class FakeProcess:
        pid = 777

    def fake_popen(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return FakeProcess()

    monkeypatch.setattr("webapp.infonalia_webapp.ai.worker_launcher.LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr("webapp.infonalia_webapp.ai.worker_launcher.subprocess.Popen", fake_popen)

    result = start_ai_worker_for_job(conn, job_id)

    assert result["ok"] is True
    assert result["pid"] == 777
    assert calls
    assert calls[0]["shell"] is False
    assert "--job-id" in calls[0]["command"]


def test_worker_mark_stale_jobs_updates_old_processing_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _insert_licitacion(conn, tmp_path)
    job_id = create_job(
        conn,
        licitacion_id=1,
        document_hash="hash",
        selected_documents=[],
        model="gemini-test",
        status="processing",
    )
    conn.execute("UPDATE ai_analysis_jobs SET started_at = '2020-01-01T00:00:00' WHERE id = ?", (job_id,))

    from contextlib import contextmanager

    @contextmanager
    def fake_db_session():
        yield conn

    monkeypatch.setattr("webapp.infonalia_webapp.ai.worker.db_session", fake_db_session)

    assert mark_stale_jobs() == 1
    row = conn.execute("SELECT status, error_code FROM ai_analysis_jobs WHERE id = ?", (job_id,)).fetchone()
    assert dict(row) == {"status": "error", "error_code": "STALE_JOB"}


def test_worker_once_processes_codex_disabled_job_without_real_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    _write_pdf(tmp_path / "PCAP.pdf")
    _insert_licitacion(conn, tmp_path)
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("AI_ANALYSIS_PROVIDER", "codex_local")
    monkeypatch.setenv("CODEX_LOCAL_ENABLED", "false")
    payload = request_ai_analysis(conn, 1, requested_by="tester", provider_name="codex_local")

    from contextlib import contextmanager

    @contextmanager
    def fake_db_session():
        yield conn

    monkeypatch.setattr("webapp.infonalia_webapp.ai.worker.db_session", fake_db_session)

    result = process_one_job()

    assert result["job_status"] == "error"
    assert result["job"]["error_code"] == "CODEX_DISABLED"
    row = conn.execute("SELECT status, error_code FROM ai_analysis_jobs WHERE id = ?", (payload["job_id"],)).fetchone()
    assert dict(row) == {"status": "error", "error_code": "CODEX_DISABLED"}


def test_ai_ui_has_provider_specific_error_messages() -> None:
    source = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    html = Path("webapp/infonalia_webapp/static/index.html").read_text(encoding="utf-8")

    assert 'code === "CODEX_DISABLED"' in source
    assert "Codex Local no está activado." in source
    assert "Error consultando Codex Local." in source
    assert 'provider === "gemini"' in source
    assert "startAiSummaryPolling" in source
    assert "Análisis IA en cola" in source
    assert "Iniciando análisis IA" in source
    assert "parseEmailList" in source
    assert "notify_on_completion" in source
    assert "notification_emails" in source
    assert "No se pudo contactar con la web local" in source
    assert "Avisar por email cuando esté listo" in html
    assert 'id="ai-notification-emails"' in html


def test_manual_test_exposes_force_regeneration_flag() -> None:
    source = Path("webapp/infonalia_webapp/ai/manual_test.py").read_text(encoding="utf-8")

    assert '"--force"' in source
    assert '"--timeout"' in source
    assert '"--input-mode"' in source
    assert "force=args.force" in source
    assert "mark_interrupted_job" in source
