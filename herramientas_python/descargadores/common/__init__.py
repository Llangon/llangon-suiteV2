"""Núcleo independiente de plataforma para descargas y preguntas."""
from .errors import DownloaderError, SafeFileError
from .run_result import (
    DownloadArtifact,
    DownloadRunResult,
    PlatformCapabilities,
    result_from_question_sync,
)

__all__ = [
    "DownloadArtifact",
    "DownloaderError",
    "DownloadRunResult",
    "PlatformCapabilities",
    "SafeFileError",
    "result_from_question_sync",
]
