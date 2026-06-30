from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from .pdf_text_extractor import extract_pdf_text
from .prompts import GEMINI_ANALYSIS_PROMPT
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


def _write_pdf_text(copied_path: Path, text_dir: Path) -> str:
    if copied_path.suffix.lower() != ".pdf":
        return ""
    result = extract_pdf_text(
        [{"path": str(copied_path), "name": copied_path.name}],
        max_total_chars=2_000_000,
        max_chars_per_document=2_000_000,
    )
    if not result.text:
        return ""
    txt_path = _unique_destination(text_dir, f"{copied_path.stem}.txt")
    txt_path.write_text(result.text, encoding="utf-8")
    return str(txt_path.relative_to(text_dir.parent))


def build_codex_prompt() -> str:
    return (
        "Actua como analista experto en licitaciones publicas espanolas.\n\n"
        "Trabaja unicamente con los ficheros copiados dentro de este workspace temporal. "
        "Lee inputs/ y, si existen, los TXT de extracted_text/. No accedas a Dropbox ni al repositorio.\n\n"
        "Ignora licitaciones anteriores salvo que el usuario lo pida expresamente. "
        "Prioriza PCAP, PPT, cuadro de caracteristicas y anexos. No inventes datos; usa null, cadena vacia o arrays vacios si no encuentras informacion.\n\n"
        "Devuelve un unico objeto JSON puro compatible con el schema indicado. No uses markdown.\n\n"
        f"{GEMINI_ANALYSIS_PROMPT}"
    )


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
        try:
            extracted_text_path = _write_pdf_text(destination, text_dir)
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
    }
    (job_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (job_root / "prompt.md").write_text(build_codex_prompt(), encoding="utf-8")
    (job_root / "schema.json").write_text(json.dumps(SUMMARY_TEMPLATE, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "job_root": str(job_root),
        "inputs_dir": str(inputs_dir),
        "manifest": manifest,
        "copied_files_count": len(files),
    }
