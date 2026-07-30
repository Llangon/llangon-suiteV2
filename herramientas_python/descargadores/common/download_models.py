"""Modelos y reglas locales para documentos ya obtenidos de una plataforma."""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from email.message import Message
from pathlib import Path
from urllib.parse import urlparse

from .safe_files import sanitize_filename


VALID_EXTENSIONS = {
    ".pdf", ".xml", ".html", ".htm", ".txt",
    ".xls", ".xlsx", ".xlsm", ".doc", ".docx",
    ".ppt", ".pptx", ".zip", ".rar", ".rtf",
    ".csv", ".ods", ".odt",
}

MIME_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/vnd.rar": ".rar",
    "application/x-rar": ".rar",
    "application/x-rar-compressed": ".rar",
    "application/rtf": ".rtf",
    "text/rtf": ".rtf",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/plain": ".txt",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "text/csv": ".csv",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "application/vnd.oasis.opendocument.text": ".odt",
}


@dataclass(frozen=True)
class RemoteDocument:
    source_url: str
    content: bytes
    logical_name: str = ""
    visible_text: str = ""
    content_type: str = ""
    content_disposition: str = ""
    platform: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DownloadedDocument:
    source_url: str
    path: Path
    filename: str
    extension: str
    sha256: str = ""
    role: str = "document"
    remote_id: str = ""
    section: str = ""
    published_at: str = ""


@dataclass
class DocumentDownloadResult:
    platform: str
    successful: bool
    found: int = 0
    downloaded: list[DownloadedDocument] = field(default_factory=list)
    skipped: list[DownloadedDocument] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extension_from_name(name: object) -> str:
    text = str(name or "").split("?")[0].split("#")[0].strip()
    extension = os.path.splitext(text)[1].lower()
    return extension if extension in VALID_EXTENSIONS else ""


def name_from_content_disposition(value: object) -> str:
    if not value:
        return ""
    message = Message()
    message["content-disposition"] = str(value)
    filename = message.get_filename()
    if filename:
        return sanitize_filename(filename, max_length=None)
    encoded = re.search(r"filename\*=UTF-8''([^;]+)", str(value), re.IGNORECASE)
    if encoded:
        return sanitize_filename(encoded.group(1), max_length=None)
    plain = re.search(r'filename="?([^";]+)"?', str(value), re.IGNORECASE)
    return sanitize_filename(plain.group(1), max_length=None) if plain else ""


def extension_from_content(content: bytes) -> str:
    beginning = content[:4096]
    if beginning.startswith(b"\xef\xbb\xbf"):
        beginning = beginning[3:]
    beginning = beginning.lstrip()
    lower = beginning[:512].lower()
    if content.startswith(b"%PDF"):
        return ".pdf"
    if content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                if "mimetype" in names:
                    mimetype = archive.read("mimetype").decode("ascii", errors="ignore").strip()
                    if mimetype == "application/vnd.oasis.opendocument.spreadsheet":
                        return ".ods"
                    if mimetype == "application/vnd.oasis.opendocument.text":
                        return ".odt"
                if "xl/vbaProject.bin" in names:
                    return ".xlsm"
                if any(name.startswith("xl/") for name in names):
                    return ".xlsx"
                if any(name.startswith("word/") for name in names):
                    return ".docx"
                if any(name.startswith("ppt/") for name in names):
                    return ".pptx"
        except zipfile.BadZipFile:
            pass
        return ".zip"
    if content.startswith((b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")):
        return ".rar"
    if lower.startswith(b"<!doctype html") or b"<html" in lower:
        return ".html"
    if lower.startswith(b"<?xml") or lower.startswith(b"<"):
        return ".xml"
    if lower.startswith(b"{\\rtf"):
        return ".rtf"
    return ""


def extension_from_content_type(content_type: object) -> str:
    value = str(content_type or "").split(";")[0].strip().lower()
    if value in MIME_TO_EXTENSION:
        return MIME_TO_EXTENSION[value]
    if "spreadsheetml" in value:
        return ".xlsx"
    if "wordprocessingml" in value:
        return ".docx"
    if "presentationml" in value:
        return ".pptx"
    if "ms-excel" in value or "excel" in value:
        return ".xls"
    if "msword" in value:
        return ".doc"
    if "pdf" in value:
        return ".pdf"
    if "rar" in value:
        return ".rar"
    if "html" in value:
        return ".html"
    if value.endswith("/xml") or value in {"text/xml", "application/xml"}:
        return ".xml"
    return ""


def detect_document_extension(document: RemoteDocument) -> str:
    return (
        extension_from_content(document.content)
        or extension_from_content_type(document.content_type)
        or extension_from_name(name_from_content_disposition(document.content_disposition))
        or extension_from_name(document.visible_text)
        or extension_from_name(document.logical_name)
        or extension_from_name(urlparse(document.source_url).path)
        or ".bin"
    )


def build_document_filename(document: RemoteDocument, extension: str) -> str:
    header_name = name_from_content_disposition(document.content_disposition)
    candidate = (
        header_name
        or document.logical_name
        or document.visible_text
        or os.path.basename(urlparse(document.source_url).path)
    )
    candidate = sanitize_filename(candidate)
    base, current_extension = os.path.splitext(candidate)
    current_extension = current_extension.lower()
    base_extension = os.path.splitext(base)[1].lower()
    if current_extension in VALID_EXTENSIONS:
        if current_extension == extension or extension in ("", ".bin"):
            return candidate
        if base_extension == extension:
            return base
        if base_extension in VALID_EXTENSIONS:
            return sanitize_filename(os.path.splitext(base)[0]) + extension
        return sanitize_filename(base) + extension
    return candidate + extension
