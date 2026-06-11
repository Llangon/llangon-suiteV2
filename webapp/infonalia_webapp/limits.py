from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath


MAX_BODY_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_IMPORT_EXTENSIONS = {".csv", ".msg"}


class UploadLimitError(ValueError):
    """Base class for controlled upload validation errors."""


class RequestTooLarge(UploadLimitError):
    """Raised when an HTTP body or uploaded file exceeds the configured limit."""


class InvalidContentLength(UploadLimitError):
    """Raised when Content-Length is missing or invalid for a required body."""


class InvalidUploadName(UploadLimitError):
    """Raised when an upload filename is empty or path-like."""


class InvalidUploadExtension(UploadLimitError):
    """Raised when an upload filename has a disallowed extension."""


def _header_value(headers: Mapping[str, object] | object, name: str) -> object | None:
    getter = getattr(headers, "get", None)
    if callable(getter):
        return getter(name)
    if isinstance(headers, Mapping):
        return headers.get(name)
    return None


def parse_content_length(headers: Mapping[str, object] | object) -> int | None:
    raw_value = _header_value(headers, "Content-Length")
    if raw_value is None:
        return None

    value = str(raw_value).strip()
    if not value:
        return None
    if not value.isdecimal():
        raise InvalidContentLength("Content-Length no valido.")

    return int(value)


def validate_content_length(headers: Mapping[str, object] | object, max_bytes: int) -> int:
    length = parse_content_length(headers)
    if length is None:
        raise InvalidContentLength("Content-Length obligatorio.")
    if length < 0:
        raise InvalidContentLength("Content-Length no valido.")
    if length > max_bytes:
        raise RequestTooLarge("La peticion supera el tamano maximo permitido.")
    return length


def get_safe_upload_filename(filename: str | None) -> str:
    if filename is None:
        raise InvalidUploadName("Nombre de fichero obligatorio.")

    clean_name = str(filename).strip()
    if not clean_name or clean_name in {".", ".."}:
        raise InvalidUploadName("Nombre de fichero no valido.")
    if "\x00" in clean_name:
        raise InvalidUploadName("Nombre de fichero no valido.")
    if "/" in clean_name or "\\" in clean_name:
        raise InvalidUploadName("El nombre de fichero no puede contener rutas.")
    if PureWindowsPath(clean_name).drive or PurePosixPath(clean_name).is_absolute():
        raise InvalidUploadName("El nombre de fichero no puede contener rutas.")
    if any(part == ".." for part in PurePosixPath(clean_name).parts):
        raise InvalidUploadName("El nombre de fichero no puede contener rutas.")

    return clean_name


def is_allowed_upload_filename(filename: str | None, allowed_extensions: set[str]) -> bool:
    try:
        clean_name = get_safe_upload_filename(filename)
    except InvalidUploadName:
        return False

    suffix = PureWindowsPath(clean_name).suffix.lower()
    return suffix in {extension.lower() for extension in allowed_extensions}


def validate_upload_filename(filename: str | None, allowed_extensions: set[str]) -> str:
    clean_name = get_safe_upload_filename(filename)
    suffix = PureWindowsPath(clean_name).suffix.lower()
    if suffix not in {extension.lower() for extension in allowed_extensions}:
        raise InvalidUploadExtension("Extension de fichero no permitida.")
    return clean_name


def validate_upload_size(size_bytes: int, max_bytes: int = MAX_UPLOAD_BYTES) -> int:
    if size_bytes > max_bytes:
        raise RequestTooLarge("El fichero supera el tamano maximo permitido.")
    return size_bytes
