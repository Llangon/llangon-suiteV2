from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse


MAX_DOWNLOAD_RUNTIME_SECONDS = 900
MAX_DOWNLOAD_TOTAL_BYTES = 500 * 1024 * 1024
MAX_DOWNLOAD_FILE_COUNT = 500
MAX_CAPTURED_OUTPUT_CHARS = 20000
INTERNAL_DOWNLOAD_FILENAMES = frozenset({".infonalia_manifest.json"})
INTERNAL_DOWNLOAD_PREFIXES = (".infonalia_dropbox_manifest_",)


class DownloadSafetyError(ValueError):
    """Base class for controlled download safety errors."""


class InvalidDownloadUrl(DownloadSafetyError):
    """Raised when a download URL is empty or uses an unsafe scheme."""


class UnsafeDestination(DownloadSafetyError):
    """Raised when a destination escapes an allowed base directory."""


class DownloadFolderLimitExceeded(DownloadSafetyError):
    """Raised when a download folder exceeds configured limits."""


@dataclass(frozen=True, slots=True)
class DownloadFolderSummary:
    folder: Path
    total_bytes: int
    file_count: int


def validate_download_url(url: str | None) -> str:
    clean_url = str(url or "").strip()
    if not clean_url:
        raise InvalidDownloadUrl("La URL de descarga es obligatoria.")

    parsed = urlparse(clean_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidDownloadUrl("La URL de descarga debe usar http o https.")
    if not parsed.netloc:
        raise InvalidDownloadUrl("La URL de descarga no es valida.")
    return clean_url


def _looks_absolute_or_drive_path(value: str) -> bool:
    return bool(PureWindowsPath(value).drive) or PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


def _has_parent_traversal(value: str) -> bool:
    windows_parts = PureWindowsPath(value).parts
    posix_parts = PurePosixPath(value).parts
    return any(part == ".." for part in windows_parts + posix_parts)


def ensure_safe_destination(base_dir: str | Path, folder_name: str | Path) -> Path:
    raw_folder = str(folder_name).strip()
    if not raw_folder:
        raise UnsafeDestination("La carpeta de destino es obligatoria.")
    if _looks_absolute_or_drive_path(raw_folder) or _has_parent_traversal(raw_folder):
        raise UnsafeDestination("La carpeta de destino no puede contener rutas inseguras.")

    base_path = Path(base_dir).resolve(strict=False)
    destination = (base_path / raw_folder).resolve(strict=False)
    try:
        destination.relative_to(base_path)
    except ValueError as exc:
        raise UnsafeDestination("La carpeta de destino queda fuera de la ruta permitida.") from exc
    return destination


def validate_resolved_destination(destination: str | Path, allowed_base_dirs: list[str | Path]) -> Path:
    if not allowed_base_dirs:
        raise UnsafeDestination("No hay rutas base permitidas para descargas.")

    resolved_destination = Path(destination).resolve(strict=False)
    for base_dir in allowed_base_dirs:
        resolved_base = Path(base_dir).resolve(strict=False)
        try:
            resolved_destination.relative_to(resolved_base)
            return resolved_destination
        except ValueError:
            continue

    raise UnsafeDestination("La carpeta de destino queda fuera de las rutas permitidas.")


def _truncate_text(value: str | None, max_chars: int) -> tuple[str, bool]:
    text = value or ""
    if len(text) <= max_chars:
        return text, False
    return text[-max_chars:], True


def summarize_process_output(stdout: str | None, stderr: str | None, max_chars: int = MAX_CAPTURED_OUTPUT_CHARS) -> dict:
    stdout_text, stdout_truncated = _truncate_text(stdout, max_chars)
    stderr_text, stderr_truncated = _truncate_text(stderr, max_chars)
    combined_text, combined_truncated = _truncate_text(
        "\n".join(part for part in (stdout_text, stderr_text) if part).strip(),
        max_chars,
    )
    return {
        "stdout": stdout_text,
        "stderr": stderr_text,
        "combined": combined_text,
        "truncated": stdout_truncated or stderr_truncated or combined_truncated,
    }


def scan_download_folder(folder: str | Path) -> DownloadFolderSummary:
    folder_path = Path(folder)
    total_bytes = 0
    file_count = 0

    if not folder_path.exists():
        return DownloadFolderSummary(folder=folder_path, total_bytes=0, file_count=0)

    for item in folder_path.rglob("*"):
        if not item.is_file():
            continue
        if item.name in INTERNAL_DOWNLOAD_FILENAMES or item.name.startswith(INTERNAL_DOWNLOAD_PREFIXES):
            continue
        file_count += 1
        total_bytes += item.stat().st_size

    return DownloadFolderSummary(folder=folder_path, total_bytes=total_bytes, file_count=file_count)


def validate_download_folder_limits(
    summary: DownloadFolderSummary,
    max_total_bytes: int = MAX_DOWNLOAD_TOTAL_BYTES,
    max_file_count: int = MAX_DOWNLOAD_FILE_COUNT,
) -> DownloadFolderSummary:
    if summary.total_bytes > max_total_bytes:
        raise DownloadFolderLimitExceeded("La descarga supera el tamano maximo permitido.")
    if summary.file_count > max_file_count:
        raise DownloadFolderLimitExceeded("La descarga supera el numero maximo de ficheros permitido.")
    return summary
