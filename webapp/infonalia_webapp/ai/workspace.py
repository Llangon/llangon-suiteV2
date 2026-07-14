from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from .encoding_utils import safe_json_dump, safe_write_text_utf8
from .pdf_text_extractor import extract_pdf_text
from .schemas import SUMMARY_TEMPLATE


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def codex_work_root() -> Path:
    configured = os.environ.get("CODEX_WORK_ROOT", "runtime/ai_work/jobs").strip() or "runtime/ai_work/jobs"
    path = Path(configured)
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    return path.resolve()


def _safe_filename(name: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', " ", name or "documento")
    value = re.sub(r"\s+", " ", value).strip().rstrip(".")
    return value or "documento"


def _unique_destination(folder: Path, name: str) -> Path:
    safe = _safe_filename(name)
    stem = Path(safe).stem or "documento"
    suffix = Path(safe).suffix
    candidate = folder / safe
    index = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({index}){suffix}"
        index += 1
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_pdf_text(copied_path: Path, text_dir: Path) -> tuple[str, int, int]:
    if copied_path.suffix.lower() != ".pdf":
        return "", 0, 0
    result = extract_pdf_text(
        [{"path": str(copied_path), "name": copied_path.name}],
        max_total_chars=2_000_000,
        max_chars_per_document=2_000_000,
    )
    if not result.text:
        return "", 0, 0
    txt_path = _unique_destination(text_dir, f"{copied_path.stem}.txt")
    safe_write_text_utf8(txt_path, result.text)
    diagnostics = result.diagnostics or {}
    pages_by_document = diagnostics.get("pages_processed_by_document") if isinstance(diagnostics.get("pages_processed_by_document"), dict) else {}
    chars_by_document = diagnostics.get("extracted_chars_by_document") if isinstance(diagnostics.get("extracted_chars_by_document"), dict) else {}
    pages = int((pages_by_document or {}).get(copied_path.name) or 0)
    chars = int((chars_by_document or {}).get(copied_path.name) or len(result.text))
    return str(txt_path.relative_to(text_dir.parent)), chars, pages


def _document_role(name: str) -> str:
    upper = name.upper()
    if "PCAP" in upper or "PCA" in upper or "CLAUSULAS" in upper:
        return "PCAP/PCA"
    if "PPT" in upper or "TECNIC" in upper or "PRESCRIP" in upper:
        return "PPT"
    if "CUADRO" in upper:
        return "cuadro de características"
    if "ANEX" in upper:
        return "anexo"
    return "documento"


def build_codex_prompt(files: list[dict[str, object]] | None = None) -> str:
    file_lines = "\n".join(
        f"- {item.get('copied_path')} ({_document_role(str(item.get('original_name') or ''))}); texto extraído: {item.get('extracted_text_path') or 'no'}"
        for item in (files or [])
    )
    return f"""Actúa como analista senior de licitaciones públicas españolas para una asesoría que prepara ofertas para clientes.

No quiero un resumen de todo el pliego. Quiero una ficha previa de interés, estructurada y objetiva, que permita a Nuria decidir por sí misma si la licitación merece entrar en el flujo de preparación.

La aplicación solo debe aportar información. No emitas decisiones preliminares, recomendaciones, acciones, consejos, conclusiones de participación ni valoraciones del tipo "conviene/no conviene", "se recomienda" o "debe prepararse".

Trabaja únicamente con este workspace temporal. No accedas a Dropbox ni al repositorio.

Debes revisar los documentos disponibles en inputs/ y, si existen, los textos extraídos en extracted_text/. Usa preferentemente los TXT extraídos, porque contienen el texto de los PDFs por páginas. Solo consulta los PDFs originales si necesitas verificar algo.

Archivos disponibles:
{file_lines or '- No se ha podido listar ningún archivo.'}

Prioriza PCAP, PPT, cuadro de características y anexos. Ignora fichas generadas para cliente, históricos y licitaciones anteriores salvo que se indique expresamente.

No analices licitaciones anteriores. Si aparecen referencias históricas, indícalas únicamente en referencias_historicas_no_analizadas con el motivo: "La licitación anterior queda fuera del alcance de la Fase 1.".

Devuelve únicamente JSON válido conforme a schema.json. La raíz debe ser un objeto, no una lista. No uses markdown. No inventes datos: si un dato no consta, usa null, cadena vacía o array vacío. Si dudas, añádelo a control_calidad.campos_con_baja_confianza.

Tu salida debe parecerse en estructura a una ficha de licitación Llangón, no a una respuesta de chat. Si solo devuelves un párrafo genérico, la respuesta será inválida.

Presta especial atención a expediente, título/objeto, organismo, plataforma, fecha y hora límite, presupuesto base, valor estimado, duración, prórrogas, lotes, productos, cantidades, precios unitarios máximos, garantías, número de sobres, documentación administrativa/técnica/económica, anexos, muestras, fichas técnicas, memoria técnica, adscripción de medios, solvencia, criterios de adjudicación, fórmulas, subcontratación, condiciones especiales, penalidades y logística de entrega.

Reglas de contenido para la ficha:
- resumen_ejecutivo.texto debe sintetizar objeto, alcance, estructura por lotes, dimensión económica y temporal y singularidades relevantes. No repitas en prosa todas las cifras de las tablas.
- resumen_ejecutivo.aspectos_clave tendrá como máximo cinco hechos breves y objetivos.
- lotes usará objetos con numero_lote, denominacion, presupuesto, valor_estimado, duracion, observaciones y fuente.
- cuando existan relaciones de artículos o suministros, productos usará objetos con lote, codigo, descripcion, unidad, cantidad_estimada, precio_unitario_maximo, importe_estimado, especificaciones_relevantes y fuente. Extrae todas las filas legibles; si la tabla está incompleta, indícalo en control_calidad.
- criterios_adjudicacion incluirá nombre, puntuacion_maxima, formula o descripcion, documentacion_a_aportar, observaciones y fuente.
- puntos_atencion se reservará para hechos singulares o condiciones relevantes que no queden suficientemente claras en otra sección. Cada punto tendrá titulo, detalle y fuente, sin recomendaciones.
- fuentes_consultadas usará objetos con documento, tipo y paginas_relevantes.
- las fuentes deben ser legibles, por ejemplo: "PCAP, cláusula 12, página 18".
- evita duplicar el mismo dato en varias secciones. Si una condición ya figura en su tabla específica, no la repitas como punto de atención salvo que exista una contradicción o limitación transversal.

Comprueba la coherencia interna antes de responder: si dices en el resumen que hay un criterio de adjudicación, debe aparecer en criterios_adjudicacion.

Para lotes, intenta extraer número y denominación. Si no encuentras presupuesto por lote, deja presupuesto null y añade una observación objetiva.

Usa lenguaje claro y operativo, orientado a una asesoría de licitaciones. No uses lenguaje promocional.
"""


def prepare_ai_workspace(
    *,
    job_id: int,
    licitacion: dict[str, object],
    selected_documents: list[dict[str, object]],
    work_root: Path | None = None,
) -> dict[str, object]:
    root = (work_root or codex_work_root()).resolve()
    job_root = root / str(job_id)
    inputs_dir = job_root / "inputs"
    text_dir = job_root / "extracted_text"
    logs_dir = job_root / "logs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, object]] = []
    for doc in selected_documents:
        source = Path(str(doc.get("path") or "")).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"No se encuentra el fichero seleccionado: {doc.get('relative_path') or source.name}")
        destination = _unique_destination(inputs_dir, str(doc.get("name") or source.name))
        shutil.copy2(source, destination)
        extracted_text_path = ""
        extracted_chars = 0
        extracted_pages = 0
        try:
            extracted_text_path, extracted_chars, extracted_pages = _write_pdf_text(destination, text_dir)
        except Exception as exc:
            extracted_text_path = f"ERROR: {type(exc).__name__}"
        files.append(
            {
                "original_relative_path": doc.get("relative_path") or source.name,
                "original_name": doc.get("name") or source.name,
                "copied_path": str(destination.relative_to(job_root)),
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
                "extracted_text_path": extracted_text_path,
                "extracted_chars": extracted_chars,
                "pages": extracted_pages,
                "role": _document_role(str(doc.get("name") or source.name)),
            }
        )

    manifest = {
        "job_id": job_id,
        "licitacion_id": licitacion.get("id"),
        "expediente": licitacion.get("expediente"),
        "objeto": licitacion.get("objeto"),
        "organismo": licitacion.get("organismo"),
        "fecha_limite": licitacion.get("fecha_limite"),
        "hora_limite": licitacion.get("hora_limite"),
        "plataforma": licitacion.get("plataforma"),
        "created_at": _now(),
        "files": files,
        "extracted_text_files": [str(item["extracted_text_path"]) for item in files if str(item.get("extracted_text_path") or "").endswith(".txt")],
        "extracted_chars_by_file": {str(item["original_name"]): item["extracted_chars"] for item in files},
        "pages_by_file": {str(item["original_name"]): item["pages"] for item in files},
    }
    safe_json_dump(job_root / "manifest.json", manifest)
    safe_write_text_utf8(job_root / "prompt.md", build_codex_prompt(files))
    safe_json_dump(job_root / "schema.json", SUMMARY_TEMPLATE)
    return {
        "job_root": str(job_root),
        "inputs_dir": str(inputs_dir),
        "manifest": manifest,
        "copied_files_count": len(files),
    }
