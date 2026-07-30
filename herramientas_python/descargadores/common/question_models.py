"""Modelos y normalización comunes para preguntas de cualquier plataforma."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import (
    DocumentRenderError,
    QuestionStateError,
    QuestionWorkflowError,
    SafeFileError,
    SnapshotIncompleteError,
)


ISO_PLATFORM_DATETIME_RE = re.compile(
    r"(?<!\d)\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?(?!\d)",
    re.IGNORECASE,
)
PLATFORM_DATETIME_RE = re.compile(
    r"(?<!\d)(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{1,2}-\d{1,2})"
    r"(?:\s+(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?(?!\d)"
)


@dataclass(frozen=True)
class ResultMessage:
    """Error o aviso serializable sin información sensible."""

    code: str
    message: str
    category: str = "common"


@dataclass(frozen=True)
class PlatformQuestionAttachment:
    name: str
    url: str = ""
    source_id: str = ""
    role: str = "entry"

    @property
    def identity(self) -> str:
        values = [
            normalized_key(self.name),
            normalized_key(self.url),
            normalized_key(self.source_id),
        ]
        role = normalize_label(self.role) or "entry"
        # Mantiene las huellas históricas de PLACE para el rol neutro.
        if role != "entry":
            values.append(role)
        return "\n".join(values)

    def to_state(self) -> dict[str, str]:
        return {
            "name": self.name,
            "url": self.url,
            "source_id": self.source_id,
            "role": normalize_label(self.role) or "entry",
        }


@dataclass(frozen=True)
class PlatformQuestion:
    """Pregunta normalizada producida por un extractor de plataforma."""

    updated_at: str
    question: str
    answer: str = ""
    attachments: tuple[PlatformQuestionAttachment, ...] = ()
    asked_at: str = ""
    answered_at: str = ""
    status: str = "Respondida"
    source_id: str = ""
    platform: str = ""
    source_url: str = ""
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def question_hash(self) -> str:
        return content_hash(self.question)

    @property
    def answer_hash(self) -> str:
        return content_hash(self.answer)

    @property
    def attachments_hash(self) -> str:
        material = "\n".join(sorted(attachment.identity for attachment in self.attachments))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def fingerprint(self) -> str:
        material = "\n".join(
            (
                normalized_key(self.updated_at),
                normalized_key(self.question),
                normalized_key(self.answer),
                self.attachments_hash,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def is_answered(self) -> bool:
        return normalize_label(self.status) == "respondida" and bool(literal_text(self.answer))

    @property
    def official_datetime(self) -> str:
        return extract_platform_datetime(self.asked_at) or extract_platform_datetime(self.updated_at)


@dataclass(frozen=True)
class QuestionSnapshot:
    """Snapshot completo y normalizado entregado por un adaptador."""

    platform: str
    metadata: dict[str, str]
    questions: tuple[PlatformQuestion, ...]
    complete: bool
    warnings: tuple[str, ...] = ()


@dataclass
class SyncResult:
    """Contrato estable para la Suite y para un monitor futuro."""

    status: str
    query_successful: bool
    authentication_successful: bool
    authentication_required: bool = True
    snapshot_complete: bool = False
    total_questions: int = 0
    answered_questions: int = 0
    incorporated_current_cycle: int = 0
    responses_updated: int = 0
    question_updates: int = 0
    answers_incorporated: int = 0
    answers_removed: int = 0
    questions_removed: int = 0
    questions_restored: int = 0
    changes_detected: bool = False
    no_changes: bool = False
    rtf_generated: bool = False
    rtf_path: str = ""
    document_generated: bool = False
    document_path: str = ""
    previous_review: str = ""
    current_review: str = ""
    error_type: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structure_novelties: list[str] = field(default_factory=list)
    platform: str = "PLACE"
    expediente: str = ""
    documents_found: int = 0
    documents_downloaded: int = 0
    documents_skipped: int = 0
    downloaded_documents: list[dict[str, str]] = field(default_factory=list)
    reused_documents: list[dict[str, str]] = field(default_factory=list)
    failed_documents: list[dict[str, str]] = field(default_factory=list)
    document_download_errors: list[str] = field(default_factory=list)
    document_format: str = ""
    document_name: str = ""
    document_sha256: str = ""
    generated_format: str = ""

    @property
    def execution_successful(self) -> bool:
        return self.status != "error" and self.query_successful

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "execution_successful": self.execution_successful,
                "ejecucion_correcta": self.execution_successful,
                "consulta_correcta": self.query_successful,
                "snapshot_completo": self.snapshot_complete,
                "autenticacion_correcta": self.authentication_successful,
                "autenticacion_requerida": self.authentication_required,
                "preguntas_totales": self.total_questions,
                "preguntas_incorporadas": self.incorporated_current_cycle,
                "preguntas_modificadas": self.question_updates,
                "respuestas_modificadas": self.responses_updated,
                "respuestas_incorporadas": self.answers_incorporated,
                "respuestas_retiradas": self.answers_removed,
                "preguntas_retiradas": self.questions_removed,
                "preguntas_reaparecidas": self.questions_restored,
                "cambios_detectados": self.changes_detected,
                "sin_cambios": self.no_changes,
                "rtf_generado": self.rtf_generated,
                "documento_generado": self.document_generated or self.rtf_generated,
                "ruta_rtf": self.rtf_path,
                "ruta_documento": self.document_path or self.rtf_path,
                "formato_documento": self.document_format or self.generated_format,
                "nombre_documento": self.document_name,
                "sha256_documento": self.document_sha256,
                "fecha_revision": self.current_review,
                "errores": list(self.errors),
                "avisos": list(self.warnings) + list(self.structure_novelties),
                "formato_generado": self.generated_format,
                "documentos_nuevos": list(self.downloaded_documents),
                "documentos_reutilizados": list(self.reused_documents),
                "documentos_fallidos": list(self.failed_documents),
                "errores_documentos": list(self.document_download_errors),
            }
        )
        return payload


def literal_text(value: object) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    return text.strip(" \t\n")


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", literal_text(value)).strip()


def normalized_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", literal_text(value)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def normalize_label(value: object) -> str:
    text = unicodedata.normalize("NFD", normalized_key(value))
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def content_hash(value: object) -> str:
    return hashlib.sha256(normalized_key(value).encode("utf-8")).hexdigest()


def extract_platform_datetime(value: object) -> str:
    text = normalize_text(value)
    match = ISO_PLATFORM_DATETIME_RE.search(text)
    if match:
        return match.group(0)
    match = PLATFORM_DATETIME_RE.search(text)
    return normalize_text(match.group(0)) if match else ""


def parse_platform_datetime(value: object) -> datetime | None:
    text = extract_platform_datetime(value)
    if not text:
        return None
    if "T" in text.upper():
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError:
            return None
    normalized = text.replace("/", "-")
    for pattern in (
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def datetime_sort_value(value: object) -> float | None:
    parsed = parse_platform_datetime(value)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def format_question_datetime(value: object, *, timezone_name: str = "") -> str:
    parsed = parse_platform_datetime(value)
    if not parsed:
        return ""
    if timezone_name and parsed.tzinfo is not None:
        try:
            parsed = parsed.astimezone(ZoneInfo(timezone_name))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return parsed.strftime("%d-%m-%Y a las %H:%M")


def iso_datetime(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def parse_iso_datetime(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None


def format_detection_datetime(value: object) -> str:
    parsed = parse_iso_datetime(value)
    return parsed.strftime("%d/%m/%Y a las %H:%M") if parsed else ""


def state_questions(source: object) -> list[dict[str, Any]]:
    if isinstance(source, dict) and isinstance(source.get("questions"), dict):
        return list(source["questions"].values())
    if isinstance(source, dict):
        return [item for item in source.values() if isinstance(item, dict)]
    return [item for item in source if isinstance(item, dict)] if isinstance(source, Iterable) else []


# Alias histórico conservado para los puntos de entrada actuales.
QuestionAnswer = PlatformQuestion
QuestionAttachment = PlatformQuestionAttachment
extract_place_datetime = extract_platform_datetime
parse_place_datetime = parse_platform_datetime
