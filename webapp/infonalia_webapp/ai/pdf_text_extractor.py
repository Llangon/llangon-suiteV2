from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ReaderFactory = Callable[[Path], Any]


@dataclass(frozen=True)
class ExtractedTextResult:
    text: str
    diagnostics: dict[str, object]

    @property
    def extracted_chars_total(self) -> int:
        return int(self.diagnostics.get("extracted_chars_total") or 0)


def _default_reader_factory(path: Path) -> Any:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError("pypdf no está instalado. Instala requirements.txt para activar el modo text.") from exc
    return PdfReader(str(path))


def _trim_to_limit(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def extract_pdf_text(
    documents: list[dict[str, object]],
    *,
    max_total_chars: int,
    max_chars_per_document: int,
    reader_factory: ReaderFactory | None = None,
) -> ExtractedTextResult:
    factory = reader_factory or _default_reader_factory
    chunks: list[str] = []
    warnings: list[str] = []
    extracted_by_document: dict[str, int] = {}
    pages_by_document: dict[str, int] = {}
    docs_with_text = 0
    total_chars = 0

    for index, doc in enumerate(documents, 1):
        if total_chars >= max_total_chars:
            warnings.append("Límite total de caracteres alcanzado antes de procesar todos los documentos.")
            break

        path = Path(str(doc.get("path") or ""))
        name = str(doc.get("name") or path.name or f"documento_{index}.pdf")
        try:
            reader = factory(path)
            pages = list(getattr(reader, "pages", []) or [])
        except Exception as exc:
            warnings.append(f"{name}: no se pudo leer el PDF ({type(exc).__name__}).")
            extracted_by_document[name] = 0
            pages_by_document[name] = 0
            continue

        doc_chunks = [f"=== DOCUMENTO {index}: {name} ==="]
        doc_chars = 0
        pages_processed = 0
        truncated = False
        for page_index, page in enumerate(pages, 1):
            if total_chars >= max_total_chars or doc_chars >= max_chars_per_document:
                truncated = True
                break
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                warnings.append(f"{name} página {page_index}: no se pudo extraer texto ({type(exc).__name__}).")
                continue
            page_text = page_text.strip()
            if not page_text:
                continue

            page_block = f"=== PÁGINA {page_index} ===\n{page_text}\n"
            remaining_doc = max_chars_per_document - doc_chars
            remaining_total = max_total_chars - total_chars
            allowed = max(0, min(remaining_doc, remaining_total))
            if allowed <= 0:
                truncated = True
                break
            page_block, was_truncated = _trim_to_limit(page_block, allowed)
            truncated = truncated or was_truncated
            doc_chunks.append(page_block)
            added = len(page_block)
            doc_chars += added
            total_chars += added
            pages_processed += 1
            if was_truncated:
                break

        if doc_chars:
            docs_with_text += 1
            chunks.append("\n".join(doc_chunks))
        if truncated:
            warnings.append(f"{name}: texto truncado por límite de caracteres.")
        extracted_by_document[name] = doc_chars
        pages_by_document[name] = pages_processed

    text = "\n\n".join(chunks).strip()
    text, final_truncated = _trim_to_limit(text, max_total_chars)
    if final_truncated:
        warnings.append("Texto final truncado por límite total de caracteres.")
    return ExtractedTextResult(
        text=text,
        diagnostics={
            "documents_text_extracted_count": docs_with_text,
            "extracted_chars_total": len(text),
            "extracted_chars_by_document": extracted_by_document,
            "pages_processed_by_document": pages_by_document,
            "extraction_warnings": warnings,
        },
    )
