"""Validación y publicación segura de archivos obtenidos mediante Chrome."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from ..common.download_models import extension_from_content
from ..common.safe_files import sanitize_filename, write_bytes_content_aware
from .client import DownloadDescriptor


ZIP_BASED_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".pptx", ".odt", ".ods", ".zip"}


class XuntaDocumentError(RuntimeError):
    """El resultado de una descarga no es un documento publicable."""


class XuntaCaptchaBlockedError(XuntaDocumentError):
    """La descarga no pudo superar el control legítimo de reCAPTCHA."""


@dataclass(frozen=True)
class PublishedDocument:
    path: Path
    written: bool
    sha256: str
    content_type: str
    size: int
    warnings: tuple[str, ...] = ()


def _looks_like_html(content: bytes) -> bool:
    beginning = content[:4096].lstrip().lower()
    return beginning.startswith(b"<!doctype html") or b"<html" in beginning


def _filename(descriptor: DownloadDescriptor, extension: str) -> str:
    title = sanitize_filename(descriptor.title, max_length=170)
    if Path(title).suffix.casefold() == extension.casefold():
        return title
    if Path(title).suffix:
        title = Path(title).stem
    return sanitize_filename(f"{title}{extension}", max_length=180)


def publish_download(
    temporary_path: Path | str,
    descriptor: DownloadDescriptor,
    destination: Path | str,
) -> PublishedDocument:
    temporary_path = Path(temporary_path)
    content = temporary_path.read_bytes()
    if not content:
        raise XuntaDocumentError("La plataforma devolvió un archivo vacío.")
    if _looks_like_html(content):
        text = content[:65536].decode("utf-8", errors="ignore").casefold()
        if "recaptcha" in text or "captcha" in text:
            raise XuntaCaptchaBlockedError(
                "XUNTA_RECAPTCHA_BLOCKED: la plataforma exigió una validación interactiva."
            )
        raise XuntaDocumentError("La plataforma devolvió HTML en lugar de un documento.")

    detected = extension_from_content(content)
    expected = descriptor.extension.casefold()
    if detected == ".zip" and expected in ZIP_BASED_EXTENSIONS:
        extension = expected
    else:
        extension = detected or expected or temporary_path.suffix.casefold() or ".bin"
    if detected and expected and detected != expected and not (
        detected == ".zip" and expected in ZIP_BASED_EXTENSIONS
    ):
        raise XuntaDocumentError(
            f"El contenido descargado es {detected}, pero la ficha anuncia {expected}."
        )

    result = write_bytes_content_aware(Path(destination), _filename(descriptor, extension), content)
    if not result.path:
        raise XuntaDocumentError("No se pudo confirmar la ruta publicada.")
    content_type = mimetypes.guess_type(result.path.name)[0] or "application/octet-stream"
    warnings: list[str] = []
    if descriptor.declared_size:
        tolerance = max(2048, int(descriptor.declared_size * 0.10))
        if abs(len(content) - descriptor.declared_size) > tolerance:
            warnings.append(
                f"{descriptor.title}: el tamaño publicado y el descargado no coinciden."
            )
    return PublishedDocument(
        path=result.path,
        written=result.written,
        sha256=result.sha256,
        content_type=content_type,
        size=len(content),
        warnings=tuple(warnings),
    )
