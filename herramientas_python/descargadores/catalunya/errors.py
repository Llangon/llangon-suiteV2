"""Errores propios del acceso público a Catalunya."""

from __future__ import annotations

from ..common.question_models import QuestionWorkflowError, SnapshotIncompleteError


class CatalunyaError(QuestionWorkflowError):
    error_type = "catalunya"


class CatalunyaAccessError(CatalunyaError):
    error_type = "access"


class CatalunyaStructureError(CatalunyaError):
    error_type = "structure"


class CatalunyaQuestionDataError(CatalunyaError):
    error_type = "question_data"


class CatalunyaDocumentError(CatalunyaError):
    error_type = "document_download"


class CatalunyaSnapshotIncompleteError(CatalunyaError, SnapshotIncompleteError):
    error_type = "incomplete_snapshot"

