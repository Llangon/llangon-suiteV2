from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable


ReaderFactory = Callable[[Path], Any]


class PortalPdfError(ValueError):
    pass


def _reader(path: Path) -> Any:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf no está instalado.") from exc
    return PdfReader(str(path))


def normalize_source_text(value: object) -> str:
    text = str(value or "").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _quality(text: str) -> dict[str, object]:
    length = len(text)
    replacement_count = text.count("�") + text.count("\ufffd")
    control_count = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    suspicious_ratio = (replacement_count + control_count) / max(length, 1)
    return {
        "chars": length,
        "replacement_chars": replacement_count,
        "control_chars": control_count,
        "suspicious_ratio": round(suspicious_ratio, 6),
        "text_reliable": bool(length >= 40 and replacement_count == 0 and suspicious_ratio < 0.001),
    }


def read_ficha_pdf(path: Path, *, reader_factory: ReaderFactory | None = None) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        raise PortalPdfError("Ficha.pdf no existe o no es un PDF válido.")
    try:
        reader = (reader_factory or _reader)(path)
        raw_pages = list(getattr(reader, "pages", []) or [])
    except Exception as exc:
        raise PortalPdfError(f"No se pudo abrir Ficha.pdf ({type(exc).__name__}).") from exc
    if not raw_pages:
        raise PortalPdfError("Ficha.pdf no contiene páginas.")
    pages: list[dict[str, object]] = []
    for index, page in enumerate(raw_pages, 1):
        warnings: list[str] = []
        try:
            text = normalize_source_text(page.extract_text() or "")
        except Exception as exc:
            text = ""
            warnings.append(f"No se pudo extraer el texto ({type(exc).__name__}).")
        quality = _quality(text)
        try:
            embedded_images = len(list(getattr(page, "images", []) or []))
        except Exception:
            embedded_images = 0
        if not quality["text_reliable"]:
            warnings.append("El texto extraído no es suficientemente fiable; se exige respaldo visual.")
        if embedded_images > 1:
            warnings.append("La página contiene elementos gráficos adicionales; se exige respaldo visual.")
        visual_fallback_required = not quality["text_reliable"] or embedded_images > 1
        pages.append(
            {
                "number": index,
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "quality": quality,
                "embedded_images": embedded_images,
                "warnings": warnings,
                "visual_fallback_required": visual_fallback_required,
            }
        )
    return {
        "name": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "page_count": len(pages),
        "pages": pages,
    }
