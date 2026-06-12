from __future__ import annotations

import importlib
import sys

import pytest

from webapp.infonalia_webapp.limits import InvalidUploadExtension, RequestTooLarge
from webapp.infonalia_webapp.multipart_uploads import extract_multipart_file, extract_multipart_filename


def multipart_body(field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----infonalia-upload-test"
    body = b"\r\n".join(
        [
            f"--{boundary}".encode("ascii"),
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode("utf-8"),
            b"Content-Type: application/octet-stream",
            b"",
            content,
            f"--{boundary}--".encode("ascii"),
            b"",
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def test_multipart_uploads_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.multipart_uploads", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.multipart_uploads")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_extract_multipart_filename_preserves_quoted_and_plain_rules() -> None:
    assert extract_multipart_filename(b'Content-Disposition: form-data; filename="licitaciones.csv"') == "licitaciones.csv"
    assert extract_multipart_filename(b"Content-Disposition: form-data; filename=licitaciones.csv") == "licitaciones.csv"
    assert extract_multipart_filename(b"Content-Disposition: form-data") is None


def test_extract_multipart_file_returns_named_part_and_validates_extension() -> None:
    body, content_type = multipart_body("csv_file", "licitaciones.csv", b"csv content\r\n")

    payload = extract_multipart_file(
        content_type,
        body,
        "csv_file",
        allowed_extensions={".csv"},
        max_upload_bytes=20,
    )

    assert payload == b"csv content"


def test_extract_multipart_file_rejects_disallowed_extension() -> None:
    body, content_type = multipart_body("csv_file", "licitaciones.exe", b"content")

    with pytest.raises(InvalidUploadExtension):
        extract_multipart_file(content_type, body, "csv_file", allowed_extensions={".csv"})


def test_extract_multipart_file_rejects_oversized_payload() -> None:
    body, content_type = multipart_body("csv_file", "licitaciones.csv", b"12345")

    with pytest.raises(RequestTooLarge):
        extract_multipart_file(content_type, body, "csv_file", max_upload_bytes=4)


def test_extract_multipart_file_preserves_current_missing_field_error() -> None:
    body, content_type = multipart_body("other_file", "licitaciones.csv", b"content")

    with pytest.raises(ValueError, match="fichero CSV"):
        extract_multipart_file(content_type, body, "csv_file")
