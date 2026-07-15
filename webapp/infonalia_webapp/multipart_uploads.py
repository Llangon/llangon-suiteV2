from __future__ import annotations

import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser

try:
    from .limits import validate_upload_filename, validate_upload_size
except ImportError:
    from limits import validate_upload_filename, validate_upload_size


def extract_multipart_filename(headers: bytes) -> str | None:
    headers_text = headers.decode("utf-8", errors="replace")
    quoted = re.search(r'filename="(?P<filename>[^"]*)"', headers_text)
    if quoted:
        return quoted.group("filename")
    plain = re.search(r"filename=(?P<filename>[^;\r\n]+)", headers_text)
    if plain:
        return plain.group("filename").strip().strip('"')
    return None


def extract_multipart_file(
    content_type: str,
    body: bytes,
    field_name: str,
    *,
    allowed_extensions: set[str] | None = None,
    max_upload_bytes: int | None = None,
) -> bytes:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("No se ha recibido un fichero válido.")

    boundary = match.group("boundary").strip().strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    for part in body.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        headers, _, data = part.partition(b"\r\n\r\n")
        if not data:
            continue
        if f'name="{field_name}"'.encode("utf-8") in headers:
            if allowed_extensions is not None:
                validate_upload_filename(extract_multipart_filename(headers), allowed_extensions)
            payload = data.rstrip(b"\r\n")
            if max_upload_bytes is not None:
                validate_upload_size(len(payload), max_upload_bytes)
            return payload

    raise ValueError("No se ha encontrado el fichero CSV en la petición.")


@dataclass(frozen=True, slots=True)
class MultipartFile:
    field_name: str
    filename: str
    content_type: str
    content: bytes


def extract_multipart_fields(
    content_type: str,
    body: bytes,
    *,
    allowed_file_fields: dict[str, set[str]] | None = None,
    max_upload_bytes: int | None = None,
) -> tuple[dict[str, str], dict[str, MultipartFile]]:
    """Parse a bounded multipart body without trimming uploaded binary bytes."""

    if "multipart/form-data" not in str(content_type).lower():
        raise ValueError("La petición no contiene un formulario multipart válido.")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("ascii", errors="strict") + b"\r\n"
        b"MIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise ValueError("No se ha recibido un formulario multipart válido.")
    fields: dict[str, str] = {}
    files: dict[str, MultipartFile] = {}
    allowed = allowed_file_fields or {}
    for part in message.iter_parts():
        field_name = str(part.get_param("name", header="content-disposition") or "").strip()
        if not field_name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is None:
            if field_name in fields:
                raise ValueError(f"El campo {field_name} está duplicado.")
            charset = part.get_content_charset() or "utf-8"
            fields[field_name] = payload.decode(charset, errors="strict")
            continue
        if field_name in files:
            raise ValueError(f"El fichero {field_name} está duplicado.")
        extensions = allowed.get(field_name)
        clean_name = (
            validate_upload_filename(filename, extensions)
            if extensions is not None
            else validate_upload_filename(filename, {".xlsx", ".png", ".jpg", ".jpeg"})
        )
        if max_upload_bytes is not None:
            validate_upload_size(len(payload), max_upload_bytes)
        files[field_name] = MultipartFile(
            field_name=field_name,
            filename=clean_name,
            content_type=str(part.get_content_type() or "application/octet-stream"),
            content=payload,
        )
    return fields, files
