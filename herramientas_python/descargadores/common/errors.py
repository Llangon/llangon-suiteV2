"""Errores comunes sin dependencias de plataforma ni de capacidades opcionales."""


class DownloaderError(RuntimeError):
    error_type = "downloader"


class QuestionWorkflowError(DownloaderError):
    error_type = "question_workflow"


class SnapshotIncompleteError(QuestionWorkflowError):
    error_type = "incomplete_snapshot"


class QuestionStateError(QuestionWorkflowError):
    error_type = "state"


class DocumentRenderError(QuestionWorkflowError):
    error_type = "document_write"


class SafeFileError(DownloaderError):
    error_type = "file_write"

