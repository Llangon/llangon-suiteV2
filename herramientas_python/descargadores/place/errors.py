"""Errores que solo puede producir el adaptador de PLACE."""

from __future__ import annotations

from ..common.question_models import QuestionWorkflowError, SnapshotIncompleteError


class PlaceQuestionsError(QuestionWorkflowError):
    error_type = "place_error"


class PlaceAuthenticationError(PlaceQuestionsError):
    error_type = "authentication"


class PlaceAccessChallengeError(PlaceAuthenticationError):
    """PLACE mostró una pantalla de acceso antes de poder autenticar."""

    error_type = "access_challenge"


class PlaceSessionError(PlaceQuestionsError):
    error_type = "session"


class PlaceStructureError(PlaceQuestionsError):
    error_type = "structure"


class PlaceQuestionDataError(PlaceQuestionsError):
    error_type = "question_data"


class PlaceResponseDataError(PlaceQuestionsError):
    error_type = "response_data"


class PlaceSnapshotIncompleteError(PlaceQuestionsError, SnapshotIncompleteError):
    error_type = "incomplete_snapshot"


class PlaceBrowserError(RuntimeError):
    """El navegador no pudo recuperar un documento público de PLACE."""

    error_code = "PLACE_BROWSER_DOWNLOAD_FAILED"


class PlaceBrowserInteractionRequiredError(PlaceBrowserError):
    """PLACE requiere una interacción que el descargador no automatiza."""

    error_code = "PLACE_BROWSER_INTERACTION_REQUIRED"
