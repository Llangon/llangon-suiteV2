from __future__ import annotations

import os
from pathlib import Path

from pypdf import PdfReader

from webapp.infonalia_webapp.ai_summary_pdf import generate_ai_summary_pdf
from webapp.infonalia_webapp.tests.test_ai_analysis_phase1 import _useful_summary_payload


def _licitacion_row(folder: str, licitacion_id: int = 1) -> dict[str, object]:
    return {
        "id": licitacion_id,
        "expediente": "EXP-IA",
        "objeto": "Suministro de prueba para residencia",
        "organismo": "Organo de prueba",
        "provincia": "Madrid",
        "fecha_limite": "2026-07-01",
        "hora_limite": "14:00",
        "tipo": "Suministro",
        "presupuesto": 12000,
        "plataforma": "PLACE",
        "estado": "Preparar",
        "ruta_carpeta": folder,
    }


def test_generate_ai_summary_pdf_saves_into_existing_folder(tmp_path: Path) -> None:
    os.environ["LLANGON_DROPBOX_BASE_PATH"] = str(tmp_path)
    folder = tmp_path / "2026" / "07 JULIO" / "EXPEDIENTE"
    folder.mkdir(parents=True)

    result = generate_ai_summary_pdf(
        _licitacion_row(str(folder)),
        _useful_summary_payload("Resumen útil para PDF."),
        selected_documents=[{"name": "PCAP.pdf"}],
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    assert result.used_fallback is False
    assert result.warning == ""
    saved = Path(result.path)
    assert saved.parent == folder
    assert saved.name.endswith(".pdf")
    assert saved.read_bytes().startswith(b"%PDF-1.4")


def test_generate_ai_summary_pdf_uses_fallback_for_missing_folder(tmp_path: Path) -> None:
    missing = tmp_path / "no-existe"

    result = generate_ai_summary_pdf(
        _licitacion_row(str(missing), licitacion_id=9),
        _useful_summary_payload("Resumen útil para fallback."),
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    assert result.used_fallback is True
    assert "runtime" in result.path
    assert "carpeta segura" in result.warning.lower()
    assert Path(result.path).is_file()


def test_generate_ai_summary_pdf_does_not_overwrite_existing_filename(tmp_path: Path) -> None:
    os.environ["LLANGON_DROPBOX_BASE_PATH"] = str(tmp_path)
    folder = tmp_path / "docs"
    folder.mkdir()
    existing = folder / "Informe resumen IA - EXP-IA.pdf"
    existing.write_bytes(b"original")

    result = generate_ai_summary_pdf(
        _licitacion_row(str(folder)),
        _useful_summary_payload("Resumen nuevo."),
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    assert Path(result.path).name != existing.name
    assert existing.read_bytes() == b"original"


def test_generate_ai_summary_pdf_uses_fallback_when_folder_is_outside_dropbox_base(tmp_path: Path, monkeypatch) -> None:
    dropbox_root = tmp_path / "dropbox"
    dropbox_root.mkdir()
    outside = tmp_path / "fuera"
    outside.mkdir()
    monkeypatch.setenv("LLANGON_DROPBOX_BASE_PATH", str(dropbox_root))

    result = generate_ai_summary_pdf(
        _licitacion_row(str(outside), licitacion_id=11),
        _useful_summary_payload("Resumen fuera de Dropbox."),
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    assert result.used_fallback is True
    assert Path(result.path).is_file()
    assert Path(result.path).parent != outside


def test_generate_ai_summary_pdf_cleans_text_and_hides_internal_dict_keys(tmp_path: Path) -> None:
    os.environ["LLANGON_DROPBOX_BASE_PATH"] = str(tmp_path)
    folder = tmp_path / "2026" / "07 JULIO" / "EXPEDIENTE"
    folder.mkdir(parents=True)
    summary = _useful_summary_payload("Transporte AØreo con hÆbiles, tØcnica, œnico, Pœblico, automÆticamente, espaæol y 1.500 .")
    summary["alertas"] = [
        {
            "nivel": "media",
            "titulo": "Fichas técnicas",
            "descripcion": "Debe adjuntarse documentación tØcnica con contenido en espaæol.",
            "accion_recomendada": "Preparar fichas y revisarlas automÆticamente.",
            "fuente": "postproceso",
        }
    ]
    summary["acciones_recomendadas"] = [{"prioridad": "media", "accion": "Revisar almacØn", "motivo": "Documento œnico."}]

    result = generate_ai_summary_pdf(
        _licitacion_row(str(folder), licitacion_id=88),
        summary,
        selected_documents=[{"name": "Pliego tØcnico.pdf"}],
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    reader = PdfReader(result.path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Aéreo" in text
    assert "hábiles" in text
    assert "técnica" in text
    assert "único" in text
    assert "Público" in text
    assert "automáticamente" in text
    assert "español" in text
    assert "€" in text
    assert "postproceso" not in text
    assert "{'" not in text
    assert "nivel" not in text
    assert "prioridad" not in text


def test_generate_ai_summary_pdf_groups_docs_and_removes_orphan_lines(tmp_path: Path) -> None:
    os.environ["LLANGON_DROPBOX_BASE_PATH"] = str(tmp_path)
    folder = tmp_path / "2026" / "07 JULIO" / "EXPEDIENTE"
    folder.mkdir(parents=True)
    summary = _useful_summary_payload("Resumen limpio.")
    summary["resumen_ejecutivo"]["aspectos_clave"] = ["Precio como único criterio", "Sobre único electrónico"]
    summary["acciones_recomendadas"] = [
        {"accion": "Preparar y controlar la presentación de muestras.", "motivo": "Puede impedir el visto bueno previo al envasado y generar riesgo de incumplimiento de la ejecución."},
        {"accion": "Preparar fichas técnicas exigidas.", "motivo": "Documentación técnica a controlar."},
    ]
    summary["presentacion_documentacion"]["documentacion_administrativa"] = ["Anexo II", "Anexo III", "Anexo IV"]
    summary["presentacion_documentacion"]["documentacion_economica"] = ["Anexo V"]
    summary["presentacion_documentacion"]["documentacion_tecnica"] = [
        "La mejor oferta deberá aportar certificación ecológica o IGP.",
        "Antes del envasado deberán presentarse informes de características, muestras o pruebas de imprenta según lote.",
    ]
    summary["presentacion_documentacion"]["anexos_relevantes"] = ["II", "III", "XIII", "Anexo IX"]
    summary["observaciones_operativas"] = {
        "lugar_entrega": ["Centro logístico"],
        "horario_entrega": ["Horario de mañana"],
        "plazo_entrega": ["48 horas"],
        "transporte": "A cargo del adjudicatario",
    }

    result = generate_ai_summary_pdf(
        _licitacion_row(str(folder), licitacion_id=90),
        summary,
        fallback_root=tmp_path / "runtime",
    )

    assert result.ok is True
    text = "\n".join(page.extract_text() or "" for page in PdfReader(result.path).pages)
    assert "Aspectos clave" in text
    assert "Aspecto clave:" not in text
    assert "Documentación para presentar la oferta" in text
    assert "Documentación para mejor oferta / adjudicación" in text
    assert "Documentación para ejecución" in text
    assert "visto bueno previo al envasado" in text
    assert "Documentación técnica a controlar" in text
    assert "[ ] Puede impedir el visto bueno previo al envasado" not in text
    assert "[ ] Documentación técnica a controlar" not in text
    assert "\n- 1\n" not in text
    assert "\n- II\n" not in text
    assert "\n- III\n" not in text
