from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from typing import TypeVar

from webapp.infonalia_webapp.limits import (
    ALLOWED_IMPORT_EXTENSIONS,
    InvalidContentLength,
    InvalidUploadExtension,
    InvalidUploadName,
    RequestTooLarge,
    get_safe_upload_filename,
    is_allowed_upload_filename,
    parse_content_length,
    validate_content_length,
    validate_upload_filename,
)


T = TypeVar("T", bound=BaseException)


def assert_raises(expected_exception: type[T], callback: Callable[[], object]) -> T:
    try:
        callback()
    except expected_exception as exc:
        return exc
    raise AssertionError(f"Expected {expected_exception.__name__}")


def test_limits_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.limits", None)
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.limits")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert "webapp.infonalia_webapp.app" not in sys.modules
    assert not {"sqlite3", "requests", "http.server", "socketserver"} & added


def test_parse_content_length_valid() -> None:
    assert parse_content_length({"Content-Length": "123"}) == 123
    assert validate_content_length({"Content-Length": "123"}, max_bytes=1024) == 123


def test_parse_content_length_missing() -> None:
    assert parse_content_length({}) is None
    assert_raises(InvalidContentLength, lambda: validate_content_length({}, max_bytes=1024))


def test_parse_content_length_non_numeric() -> None:
    assert_raises(InvalidContentLength, lambda: parse_content_length({"Content-Length": "abc"}))
    assert_raises(InvalidContentLength, lambda: validate_content_length({"Content-Length": "abc"}, 1024))


def test_parse_content_length_negative() -> None:
    assert_raises(InvalidContentLength, lambda: parse_content_length({"Content-Length": "-1"}))
    assert_raises(InvalidContentLength, lambda: validate_content_length({"Content-Length": "-1"}, 1024))


def test_content_length_above_limit() -> None:
    assert_raises(RequestTooLarge, lambda: validate_content_length({"Content-Length": "1025"}, 1024))


def test_valid_upload_names() -> None:
    assert get_safe_upload_filename("archivo.csv") == "archivo.csv"
    assert is_allowed_upload_filename("archivo.csv", ALLOWED_IMPORT_EXTENSIONS)
    assert is_allowed_upload_filename("archivo.msg", ALLOWED_IMPORT_EXTENSIONS)
    assert validate_upload_filename("archivo.csv", {".csv"}) == "archivo.csv"
    assert validate_upload_filename("archivo.msg", {".msg"}) == "archivo.msg"


def test_invalid_upload_extension() -> None:
    assert not is_allowed_upload_filename("archivo.exe", ALLOWED_IMPORT_EXTENSIONS)
    assert not is_allowed_upload_filename("archivo", ALLOWED_IMPORT_EXTENSIONS)
    assert not is_allowed_upload_filename("archivo.csv.exe", ALLOWED_IMPORT_EXTENSIONS)
    assert_raises(InvalidUploadExtension, lambda: validate_upload_filename("archivo.exe", ALLOWED_IMPORT_EXTENSIONS))
    assert_raises(InvalidUploadExtension, lambda: validate_upload_filename("archivo", ALLOWED_IMPORT_EXTENSIONS))
    assert_raises(
        InvalidUploadExtension,
        lambda: validate_upload_filename("archivo.csv.exe", ALLOWED_IMPORT_EXTENSIONS),
    )


def test_invalid_path_like_upload_names() -> None:
    invalid_names = [
        "../archivo.csv",
        "..\\archivo.csv",
        "C:\\temp\\archivo.csv",
        "/tmp/archivo.csv",
        "",
    ]

    for filename in invalid_names:
        assert not is_allowed_upload_filename(filename, ALLOWED_IMPORT_EXTENSIONS)
        assert_raises(InvalidUploadName, lambda filename=filename: get_safe_upload_filename(filename))
        assert_raises(
            InvalidUploadName,
            lambda filename=filename: validate_upload_filename(filename, ALLOWED_IMPORT_EXTENSIONS),
        )
