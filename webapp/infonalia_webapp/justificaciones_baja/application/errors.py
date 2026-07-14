"""Errors raised by the application layer and translated by the HTTP facade."""


class JustificationApplicationError(RuntimeError):
    status_code = 400
    code = "justificacion_invalida"


class JustificationValidationError(JustificationApplicationError):
    code = "validacion_justificacion"

    def __init__(self, message: str, *, issues: list[dict] | None = None) -> None:
        super().__init__(message)
        self.issues = list(issues or [])


class JustificationPermissionError(JustificationApplicationError):
    status_code = 403
    code = "permiso_denegado"


class JustificationConflictApplicationError(JustificationApplicationError):
    status_code = 409
    code = "conflicto_revision"


class JustificationNotFoundApplicationError(JustificationApplicationError):
    status_code = 404
    code = "justificacion_no_encontrada"


class JustificationStorageError(JustificationApplicationError):
    code = "almacenamiento_no_disponible"

