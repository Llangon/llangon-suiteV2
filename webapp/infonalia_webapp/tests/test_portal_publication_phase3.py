from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import subprocess

import pytest
from reportlab.pdfgen import canvas

from webapp.infonalia_webapp.ai.config import AIConfig
from webapp.infonalia_webapp.portal_publication.ai_provider import (
    _portal_codex_process_error,
    PortalCodexLocalProvider,
    PortalProviderResult,
    portal_provider_error_payload,
    portal_provider_for_config,
)
from webapp.infonalia_webapp.ai.gemini_provider import AIProviderError
from webapp.infonalia_webapp.portal_publication.ai_schema import PortalAISchemaError, parse_portal_ai_payload
from webapp.infonalia_webapp.portal_publication.ai_service import build_ai_portal_preview
from webapp.infonalia_webapp.portal_publication.generator import build_portal_model
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def _pdf(path: Path, pages: list[str]) -> Path:
    writer = canvas.Canvas(str(path))
    for text in pages:
        writer.drawString(50, 790, text)
        writer.showPage()
    writer.save()
    return path


def _files(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    item = {
        "path": str(path),
        "name": "Ficha.pdf",
        "relative_path": "Ficha.pdf",
        "size_bytes": path.stat().st_size,
        "size_human": "1 KB",
        "extension": "PDF",
        "is_ficha": True,
    }
    return item, [item]


def _licitacion(folder: Path) -> dict[str, object]:
    return {
        "id": 1,
        "expediente": "EXP-FASE-3",
        "objeto": "Suministro completo de prueba",
        "fecha_limite": "2026-09-01",
        "hora_limite": "14:00",
        "ruta_carpeta": str(folder),
    }


def _codex_config(**overrides: object) -> AIConfig:
    values = {
        "enabled": False,
        "api_key": "",
        "model": "",
        "max_requests_per_minute": 1,
        "max_requests_per_day": 1,
        "cooldown_on_429_minutes": 1,
        "max_documents_per_analysis": 4,
        "max_file_mb": 45,
        "timeout_seconds": 120,
        "analysis_provider": "codex_local",
        "codex_local_enabled": True,
        "codex_executable": "codex",
        "codex_timeout_seconds": 30,
        "codex_sandbox": "read-only",
        "codex_model": "auto",
    }
    values.update(overrides)
    return AIConfig(**values)


class CompleteProvider:
    name = "fake_visual"
    model = "fake-complete"

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        pages = base_model["source"]["pages"]
        blocks = [
            {
                "id": f"pagina-{page['number']}",
                "type": "text",
                "title": f"Contenido página {page['number']}",
                "paragraphs": [page["text"]],
                "sourcePages": [page["number"]],
            }
            for page in pages
        ]
        payload = {
            "tender": {
                "reference": "EXP-FASE-3",
                "title": "Suministro completo de prueba",
                "deadline": {"day": "1", "month": "septiembre", "year": "2026", "time": "14:00"},
            },
            "sections": [
                {
                    "id": "contenido-completo",
                    "eyebrow": "Ficha",
                    "title": "Contenido completo",
                    "sourcePages": [page["number"] for page in pages],
                    "blocks": blocks,
                }
            ],
            "sourceCoverage": [
                {
                    "page": page["number"],
                    "sourceSha256": page["text_sha256"],
                    "visualReviewed": True,
                    "coveredBlockIds": [f"pagina-{page['number']}"],
                    "unmappedContent": [],
                }
                for page in pages
            ],
            "qualityNotes": [],
        }
        return PortalProviderResult(payload=payload, usage={"tokens_total": 10})


class OmissionProvider(CompleteProvider):
    model = "fake-omission"

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        result = super().generate(base_model, ficha_path)
        result.payload["sourceCoverage"] = result.payload["sourceCoverage"][:1]
        result.payload["sections"][0]["blocks"] = result.payload["sections"][0]["blocks"][:1]
        return result


class NoVisualReviewProvider(CompleteProvider):
    model = "fake-no-visual-review"

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        result = super().generate(base_model, ficha_path)
        result.payload["sourceCoverage"][0]["visualReviewed"] = False
        return result


class RedundantUnmappedProvider(CompleteProvider):
    model = "fake-redundant-unmapped"

    def generate(self, base_model: dict[str, object], ficha_path: Path) -> PortalProviderResult:
        result = super().generate(base_model, ficha_path)
        result.payload["sourceCoverage"][0]["unmappedContent"] = [base_model["source"]["pages"][0]["text"]]
        return result


def test_complete_ai_enrichment_is_audited_and_ready_for_preview(tmp_path: Path) -> None:
    path = _pdf(
        tmp_path / "Ficha.pdf",
        [
            "Página uno con expediente, plazo y presupuesto íntegros para la licitación.",
            "Página dos con criterios, condiciones y observaciones completas de ejecución.",
        ],
    )
    ficha, downloads = _files(path)

    model = build_ai_portal_preview(_licitacion(tmp_path), ficha, downloads, provider=CompleteProvider())

    assert model["schema_version"] == "llangon.portal.v2"
    assert model["generation"]["mode"] == "ai_enriched"
    assert model["generation"]["published"] is False
    assert model["coverage"]["status"] == "preview_ready"
    assert model["coverage"]["ready_for_publication_review"] is True
    assert model["coverage"]["fallback_pages"] == []
    assert all(block["type"] != "source_page" for section in model["sections"] for block in section["blocks"])


def test_ai_omission_is_blocked_and_literal_page_is_added(tmp_path: Path) -> None:
    path = _pdf(
        tmp_path / "Ficha.pdf",
        [
            "Página uno completa con información esencial de la licitación y su presupuesto.",
            "Página dos omitida por la IA con condiciones especiales y criterios completos.",
        ],
    )
    ficha, downloads = _files(path)

    model = build_ai_portal_preview(_licitacion(tmp_path), ficha, downloads, provider=OmissionProvider())

    assert model["coverage"]["status"] == "needs_review"
    assert model["coverage"]["publication_allowed"] is False
    assert model["coverage"]["fallback_pages"] == [2]
    fallback = model["sections"][-1]
    assert fallback["id"] == "verificacion-contenido-literal"
    assert fallback["blocks"][0]["page"] == 2
    assert "Página dos omitida" in fallback["blocks"][0]["text"]


def test_every_page_requires_visual_confirmation_even_when_text_is_reliable(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "Ficha.pdf", ["Página con texto fiable que también debe comprobarse visualmente de forma obligatoria."])
    ficha, downloads = _files(path)

    model = build_ai_portal_preview(_licitacion(tmp_path), ficha, downloads, provider=NoVisualReviewProvider())

    assert model["coverage"]["status"] == "needs_review"
    assert model["coverage"]["visual_unreviewed_pages"] == [1]
    assert model["coverage"]["fallback_pages"] == [1]


def test_declared_unmapped_content_does_not_block_when_it_is_already_rendered(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "Ficha.pdf", ["Contenido completo ya trasladado al bloque principal de la página."])
    ficha, downloads = _files(path)

    model = build_ai_portal_preview(_licitacion(tmp_path), ficha, downloads, provider=RedundantUnmappedProvider())

    assert model["coverage"]["status"] == "preview_ready"
    assert model["coverage"]["unmapped_pages"] == []
    assert model["coverage"]["resolved_unmapped_by_page"]["1"]


def test_codex_local_portal_receives_every_rendered_page_and_returns_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _pdf(
        tmp_path / "Ficha.pdf",
        ["Primera página completa para Codex Local.", "Segunda página completa para Codex Local."],
    )
    ficha, downloads = _files(path)
    base = build_portal_model(_licitacion(tmp_path), ficha, downloads)
    expected = CompleteProvider().generate(base, path).payload
    calls: list[dict[str, object]] = []

    def fake_renderer(_path: Path, output_dir: Path) -> list[Path]:
        images = [output_dir / "pagina-1.png", output_dir / "pagina-2.png"]
        for image in images:
            image.write_bytes(b"fake png")
        return images

    def fake_runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        output_name = command[command.index("--output-last-message") + 1]
        Path(kwargs["cwd"], output_name).write_text(json.dumps(expected), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("webapp.infonalia_webapp.portal_publication.ai_provider.shutil.which", lambda _value: "codex.CMD")
    provider = PortalCodexLocalProvider(_codex_config(), runner=fake_runner, page_renderer=fake_renderer)

    model = build_ai_portal_preview(_licitacion(tmp_path), ficha, downloads, provider=provider)

    command = calls[0]["command"]
    assert command.count("--image") == 2
    assert "--ignore-user-config" in command
    prompt_index = next(index for index, value in enumerate(command) if value.startswith("Lee prompt.md"))
    assert prompt_index < command.index("--image")
    assert calls[0]["shell"] is False
    assert model["generation"]["provider"] == "codex_local"
    assert model["generation"]["published"] is False
    assert model["coverage"]["status"] == "preview_ready"
    assert model["generation"]["usage"]["rendered_pages"] == 2


def test_codex_local_is_a_supported_portal_provider() -> None:
    provider = portal_provider_for_config(_codex_config())

    assert isinstance(provider, PortalCodexLocalProvider)


def test_codex_portal_error_is_classified_and_secrets_are_hidden() -> None:
    code, message = _portal_codex_process_error("401 Unauthorized: refresh token expired")
    payload = portal_provider_error_payload(
        AIProviderError(
            message,
            code=code,
            diagnostics={"stderr_preview": "access_token=very-secret-value\n401 Unauthorized"},
        )
    )

    assert code == "CODEX_AUTH_ERROR"
    assert "sesión de Codex" in message
    assert "very-secret-value" not in payload["error_detail"]
    assert "[oculto]" in payload["error_detail"]


def test_private_ui_contains_ai_preview_mobile_print_and_integrity_fallback() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    script = (root / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "static" / "styles.css").read_text(encoding="utf-8")

    assert 'id="portal-preview-dialog"' in html
    assert "Generar vista previa con IA" in html
    assert 'mode: "ai"' in script
    assert 'block.type === "source_page"' in script
    assert "Las páginas dudosas se han conservado literalmente" in script
    assert "@media (max-width: 760px)" in styles
    assert "body:has(.portal-preview-dialog[open])" in styles
    assert "Vista previa privada · No publicada" in script


def test_portal_ai_schema_rejects_unsafe_or_unknown_blocks(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "Ficha.pdf", ["Contenido completo de una página para validar el esquema del portal."])
    ficha, downloads = _files(path)
    base = build_portal_model(_licitacion(tmp_path), ficha, downloads)
    payload = {
        "sections": [
            {
                "id": "mala",
                "title": "Sección",
                "sourcePages": [1],
                "blocks": [{"id": "x", "type": "html", "text": "<script>alert(1)</script>", "sourcePages": [1]}],
            }
        ]
    }

    with pytest.raises(PortalAISchemaError, match="Tipo de bloque no permitido"):
        parse_portal_ai_payload(payload, base)


def test_portal_endpoint_ai_mode_uses_ai_pipeline_without_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(tmp_path))
    app = load_app_module()
    captured: dict[str, object] = {}

    def fake_ai_preview(row, ficha, downloads):
        captured["ficha"] = ficha["name"]
        captured["downloads"] = [item["name"] for item in downloads]
        return {"schema_version": "llangon.portal.v2", "generation": {"published": False}, "coverage": {"status": "preview_ready"}}

    monkeypatch.setattr(app, "build_ai_portal_preview", fake_ai_preview)
    with temporary_app_database(app):
        folder = tmp_path / "expediente"
        folder.mkdir()
        _pdf(folder / "Ficha.pdf", ["Ficha completa para la vista previa con IA."])
        _pdf(folder / "PPT.pdf", ["Documento descargable."])
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (id, expediente, objeto, organismo, ruta_carpeta, estado, created_at, updated_at)
                VALUES (1, 'EXP-FASE-3', 'Objeto', 'Órgano', ?, 'Importada', '2026-01-01', '2026-01-01')
                """,
                (str(folder),),
            )
        handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/1/portal-preview/generate",
            {"selected_files": ["Ficha.pdf", "PPT.pdf"], "mode": "ai"},
        )

        dispatch(handler, "POST")
        status, payload = handler.responses[-1]

        assert status == HTTPStatus.OK
        assert payload["generation"]["published"] is False
        assert captured == {"ficha": "Ficha.pdf", "downloads": ["Ficha.pdf", "PPT.pdf"]}
