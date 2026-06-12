from __future__ import annotations

import re

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
