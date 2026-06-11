from __future__ import annotations

import importlib
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from webapp.infonalia_webapp.download_safety import (
    DownloadFolderLimitExceeded,
    InvalidDownloadUrl,
    UnsafeDestination,
    ensure_safe_destination,
    scan_download_folder,
    summarize_process_output,
    validate_download_folder_limits,
    validate_download_url,
)


T = TypeVar("T", bound=BaseException)


def assert_raises(expected_exception: type[T], callback: Callable[[], object]) -> T:
    try:
        callback()
    except expected_exception as exc:
        return exc
    raise AssertionError(f"Expected {expected_exception.__name__}")


def test_download_safety_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.download_safety", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.download_safety")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_validate_download_url_accepts_http_and_https() -> None:
    assert validate_download_url("https://example.test/licitacion") == "https://example.test/licitacion"
    assert validate_download_url("http://example.test/licitacion") == "http://example.test/licitacion"


def test_validate_download_url_rejects_empty_and_unsafe_schemes() -> None:
    assert_raises(InvalidDownloadUrl, lambda: validate_download_url(""))
    assert_raises(InvalidDownloadUrl, lambda: validate_download_url("file:///tmp/documento.pdf"))
    assert_raises(InvalidDownloadUrl, lambda: validate_download_url("javascript:alert(1)"))
    assert_raises(InvalidDownloadUrl, lambda: validate_download_url("data:text/plain,contenido"))


def test_ensure_safe_destination_accepts_normal_destination() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        destination = ensure_safe_destination(tmp_dir, "expediente-001")

        assert destination == Path(tmp_dir).resolve() / "expediente-001"


def test_ensure_safe_destination_rejects_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        assert_raises(UnsafeDestination, lambda: ensure_safe_destination(tmp_dir, "../expediente-001"))
        assert_raises(UnsafeDestination, lambda: ensure_safe_destination(tmp_dir, "..\\expediente-001"))


def test_ensure_safe_destination_rejects_absolute_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        assert_raises(UnsafeDestination, lambda: ensure_safe_destination(tmp_dir, "C:\\temp\\expediente-001"))
        assert_raises(UnsafeDestination, lambda: ensure_safe_destination(tmp_dir, "/tmp/expediente-001"))


def test_summarize_process_output_truncates_long_output() -> None:
    output = summarize_process_output("a" * 30, "b" * 30, max_chars=10)

    assert output["stdout"] == "a" * 10
    assert output["stderr"] == "b" * 10
    assert len(output["combined"]) <= 10
    assert output["truncated"] is True


def test_scan_download_folder_with_few_files_passes_limits() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "a.txt").write_text("abc", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "b.txt").write_text("def", encoding="utf-8")

        summary = scan_download_folder(root)

        assert summary.file_count == 2
        assert summary.total_bytes == 6
        assert validate_download_folder_limits(summary, max_total_bytes=10, max_file_count=2) == summary


def test_download_folder_with_too_many_files_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "a.txt").write_text("a", encoding="utf-8")
        (root / "b.txt").write_text("b", encoding="utf-8")
        summary = scan_download_folder(root)

        assert_raises(
            DownloadFolderLimitExceeded,
            lambda: validate_download_folder_limits(summary, max_total_bytes=10, max_file_count=1),
        )


def test_download_folder_with_excessive_total_size_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "a.txt").write_text("12345678901", encoding="utf-8")
        summary = scan_download_folder(root)

        assert_raises(
            DownloadFolderLimitExceeded,
            lambda: validate_download_folder_limits(summary, max_total_bytes=10, max_file_count=1),
        )
