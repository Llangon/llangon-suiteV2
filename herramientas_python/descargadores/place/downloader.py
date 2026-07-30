"""Coordinación operativa de documentos y preguntas de PLACE."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..common.question_models import SyncResult
from ..common.run_result import (
    DownloadArtifact,
    DownloadRunResult,
    PlatformCapabilities,
    result_from_question_sync,
    utc_now_iso,
)
from ..common.safe_files import sha256_file
from .access import resolver_credenciales_place
from .browser_fallback import create_challenge_resolver
from .challenge import (
    canonicalizar_url_place,
    es_url_place_segura,
    requiere_interaccion_place,
)
from .documents import crear_session, procesar_html, procesar_pliegos_descargados


PLACE_CAPABILITIES = PlatformCapabilities(
    documents=True,
    questions_and_answers=True,
    document_history=True,
    question_attachments=True,
)
_QUESTION_MODULE = None
MAX_PROFILE_REDIRECTS_PLACE = 5


class PlaceProfileRedirectError(ValueError):
    """La ficha no puede seguir redirecciones fuera de PLACE."""


def _obtener_ficha_sin_salir_de_place(session, source_url: str):
    current_url = source_url
    history = []
    for _ in range(MAX_PROFILE_REDIRECTS_PLACE + 1):
        response = session.get(current_url, timeout=60, allow_redirects=False)
        try:
            status_code = int(getattr(response, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status_code = 0
        if status_code not in {301, 302, 303, 307, 308}:
            if history:
                try:
                    previous = list(getattr(response, "history", ()) or ())
                    response.history = tuple(history + previous)
                except (AttributeError, TypeError):
                    pass
            return response
        headers = getattr(response, "headers", {}) or {}
        location = str(headers.get("Location", "") or "")
        next_url = canonicalizar_url_place(urljoin(current_url, location)) if location else ""
        if not next_url or not es_url_place_segura(next_url):
            raise PlaceProfileRedirectError(
                "PLACE_PROFILE_REDIRECT_INVALID: PLACE redirigió la ficha fuera de su dominio HTTPS autorizado."
            )
        history.append(response)
        current_url = next_url
    raise PlaceProfileRedirectError(
        "PLACE_PROFILE_REDIRECT_INVALID: PLACE superó el máximo de redirecciones de la ficha."
    )


def _response_remains_in_place(response, source_url: str) -> bool:
    urls = [str(source_url or "")]
    history = getattr(response, "history", ()) or ()
    try:
        urls.extend(str(getattr(item, "url", "") or "") for item in history)
    except TypeError:
        return False
    urls.append(str(getattr(response, "url", "") or ""))
    return all(
        es_url_place_segura(canonicalizar_url_place(item))
        for item in urls
        if item
    )


class _LazyChallengeResolver:
    """Crea Chrome únicamente si una respuesta documental lo necesita."""

    def __init__(self, factory):
        self._factory = factory
        self._resolver = None

    def resolve(self, request):
        if self._resolver is None:
            self._resolver = self._factory()
        resolve = getattr(self._resolver, "resolve", None)
        if not callable(resolve):
            raise RuntimeError("El fallback de navegador de PLACE no implementa resolve().")
        return resolve(request)

    def close(self) -> None:
        if self._resolver is None:
            return
        close = getattr(self._resolver, "close", None)
        if callable(close):
            close()


def cargar_modulo_preguntas_place():
    global _QUESTION_MODULE
    if _QUESTION_MODULE is not None:
        return _QUESTION_MODULE
    path = Path(__file__).resolve().parents[2] / "Descargar_Preguntas_PLACE.py"
    spec = importlib.util.spec_from_file_location("descargar_preguntas_place_operativo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se pudo cargar el componente de preguntas y respuestas de PLACE.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _QUESTION_MODULE = module
    return module


def procesar_preguntas_y_respuestas(
    url,
    carpeta_destino,
    *,
    usuario=None,
    contrasena=None,
    modulo_preguntas=None,
    db_path=None,
    logger=print,
):
    usuario, contrasena = resolver_credenciales_place(usuario, contrasena, db_path=db_path)
    if not usuario and not contrasena:
        logger(
            "\nPreguntas y respuestas: omitidas porque la cuenta de PLACE no está "
            "configurada en la Suite."
        )
        return SyncResult(
            status="not_configured",
            query_successful=False,
            authentication_successful=False,
            error_type="configuration",
            warnings=["La cuenta de PLACE no está configurada en la Suite."],
            platform="PLACE",
        ).to_dict()
    if not usuario or not contrasena:
        logger("\nError de configuración: faltan datos de acceso para consultar preguntas y respuestas de PLACE.")
        return SyncResult(
            status="error",
            query_successful=False,
            authentication_successful=False,
            error_type="configuration",
            errors=["Faltan datos de acceso de PLACE."],
            platform="PLACE",
        ).to_dict()
    try:
        api = modulo_preguntas or cargar_modulo_preguntas_place()
        result = api.sync_place_questions(url, Path(carpeta_destino).resolve(), usuario, contrasena)
    except Exception as exc:
        logger(f"\nError consultando preguntas y respuestas de PLACE: {exc}")
        return SyncResult(
            status="error",
            query_successful=False,
            authentication_successful=False,
            error_type="unexpected",
            errors=[str(exc)],
            platform="PLACE",
        ).to_dict()

    payload = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    payload.setdefault("platform", "PLACE")
    logger(f"\nPreguntas respondidas encontradas: {payload['answered_questions']}")
    if payload["status"] == "error":
        logger("Error consultando preguntas y respuestas de PLACE: " + "; ".join(payload.get("errors") or []))
    elif payload.get("document_generated") or payload.get("rtf_generated"):
        changes = sum(
            int(payload.get(key) or 0)
            for key in (
                "incorporated_current_cycle",
                "responses_updated",
                "question_updates",
                "answers_incorporated",
                "answers_removed",
                "questions_removed",
                "questions_restored",
            )
        )
        document_format = str(
            payload.get("document_format") or payload.get("generated_format") or "documento"
        ).upper()
        document_path = payload.get("document_path") or payload.get("rtf_path") or ""
        logger(f"{document_format} acumulativo creado con {changes} cambio(s): {document_path}")
    else:
        logger("La revisión terminó sin cambios; no se creó ningún documento de preguntas.")
    return payload


def run_place(
    url: str,
    destination: Path,
    *,
    session=None,
    usuario=None,
    contrasena=None,
    modulo_preguntas=None,
    db_path=None,
    logger=print,
    started_at: str | None = None,
    challenge_resolver_factory=create_challenge_resolver,
) -> DownloadRunResult:
    started = started_at or utc_now_iso()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    source_url = canonicalizar_url_place(url)
    if not es_url_place_segura(source_url):
        return DownloadRunResult.failed(
            platform="PLACE",
            source_url=source_url or str(url or ""),
            capabilities=PLACE_CAPABILITIES,
            error="La URL de PLACE debe usar HTTPS y el dominio oficial de la plataforma.",
            error_code="PLACE_PROFILE_URL_INVALID",
            started_at=started,
            block_completeness={"documents": "invalid", "questions": "invalid"},
        )
    session = session or crear_session(source_url)
    downloaded_names = []
    downloaded_urls = set()
    document_events = []
    challenge_resolver = (
        _LazyChallengeResolver(challenge_resolver_factory)
        if challenge_resolver_factory is not None
        else None
    )
    try:
        response = _obtener_ficha_sin_salir_de_place(session, source_url)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            if not requiere_interaccion_place(getattr(response, "content", b"")):
                raise
        profile_url = canonicalizar_url_place(str(getattr(response, "url", "") or source_url))
        if not _response_remains_in_place(response, source_url):
            raise ValueError("PLACE redirigió la ficha a una URL fuera de su dominio HTTPS autorizado.")
        if requiere_interaccion_place(getattr(response, "content", b"")):
            return DownloadRunResult.failed(
                platform="PLACE",
                source_url=source_url,
                capabilities=PLACE_CAPABILITIES,
                error="PLACE exige una validación de acceso antes de mostrar la ficha de la licitación.",
                error_code="PLACE_ACCESS_CHALLENGE",
                started_at=started,
                block_completeness={"documents": "invalid", "questions": "invalid"},
            )
        soup = BeautifulSoup(response.text, "html.parser")
        first_phase_names = procesar_html(
            session,
            soup,
            profile_url,
            str(destination),
            downloaded_urls,
            document_events,
            challenge_resolver=challenge_resolver,
        )
        downloaded_names.extend(first_phase_names)
        source_urls_by_name = {
            str(event.get("name") or ""): str(
                event.get("final_url") or event.get("source_url") or profile_url
            )
            for event in document_events
            if event.get("name") and event.get("status") in {"created", "reused"}
        }
        downloaded_names.extend(
            procesar_pliegos_descargados(
                session,
                profile_url,
                str(destination),
                list(downloaded_names),
                downloaded_urls,
                document_events,
                source_urls_by_name=source_urls_by_name,
                challenge_resolver=challenge_resolver,
            )
        )
    except PlaceProfileRedirectError as exc:
        return DownloadRunResult.failed(
            platform="PLACE",
            source_url=source_url,
            capabilities=PLACE_CAPABILITIES,
            error=str(exc),
            error_code="PLACE_PROFILE_REDIRECT_INVALID",
            started_at=started,
            block_completeness={"documents": "invalid", "questions": "invalid"},
        )
    except Exception as exc:
        return DownloadRunResult.failed(
            platform="PLACE",
            source_url=source_url,
            capabilities=PLACE_CAPABILITIES,
            error=f"Error accediendo a la URL: {exc}",
            started_at=started,
        )
    finally:
        if challenge_resolver is not None:
            try:
                challenge_resolver.close()
            except Exception as exc:
                logger(f"No se pudo cerrar el navegador temporal de PLACE: {exc}")

    question_payload = procesar_preguntas_y_respuestas(
        profile_url,
        str(destination),
        usuario=usuario,
        contrasena=contrasena,
        modulo_preguntas=modulo_preguntas,
        db_path=db_path,
        logger=logger,
    )
    state_path = destination / ".llangon-place" / "questions_state.json"
    adapted = result_from_question_sync(
        question_payload,
        source_url=source_url,
        capabilities=PLACE_CAPABILITIES,
        started_at=started,
        state_path=str(state_path) if state_path.is_file() else "",
    )
    document_artifacts = []
    for event in document_events:
        name = event["name"]
        raw_path = str(event.get("path") or "")
        path = Path(raw_path) if raw_path else None
        document_artifacts.append(
            DownloadArtifact(
                name=name,
                status=event["status"],
                source_url=event.get("source_url", ""),
                path=str(path) if path and path.is_file() else "",
                sha256=event.get("sha256") or (sha256_file(path) if path and path.is_file() else ""),
                sha256_source=event.get("sha256_source", ""),
                content_type=event.get("content_type", ""),
                size=int(event.get("size") or 0),
                final_url=event.get("final_url", ""),
                http_status=int(event.get("http_status") or 0),
                redirect_count=int(event.get("redirect_count") or 0),
                error_code=event.get("error_code", ""),
                error_message=event.get("error_message", ""),
                retrieval_method=event.get("retrieval_method", ""),
                fallback_reason=event.get("fallback_reason", ""),
            )
        )
    adapted.artifacts = document_artifacts + adapted.artifacts
    adapted.files_created = [
        item.path for item in adapted.artifacts if item.status == "created" and item.path
    ]
    adapted.documents_found += len(document_artifacts)
    created_documents = sum(item.status == "created" for item in document_artifacts)
    adapted.documents_downloaded += created_documents
    adapted.documents_new += created_documents
    adapted.files_reused = [
        item.path for item in adapted.artifacts if item.status == "reused" and item.path
    ]
    adapted.changes_detected = adapted.changes_detected or created_documents > 0
    document_failures = [item for item in document_artifacts if item.status == "failed"]
    adapted.block_completeness["documents"] = "partial" if document_failures else "complete"
    for item in document_failures:
        message = item.error_message or "No se pudo verificar la respuesta documental de PLACE."
        detail = f"{item.name}: {message}"
        if detail not in adapted.recoverable_issues:
            adapted.recoverable_issues.append(detail)
    if document_failures:
        adapted.error_code = next(
            (item.error_code for item in document_failures if item.error_code),
            "PLACE_DOCUMENT_RESPONSE_INVALID",
        )
    if question_payload.get("error_type") == "access_challenge" and not adapted.error_code:
        adapted.error_code = "PLACE_LOGIN_CHALLENGE"
    adapted.general_data["legacy_exit_code"] = 2 if question_payload.get("status") == "error" else 0
    if question_payload.get("status") == "not_configured":
        adapted.status = "partial" if document_failures else "success_with_warnings"
        adapted.error = ""
    elif question_payload.get("status") == "error" and document_artifacts:
        adapted.status = "partial"
    elif document_failures and adapted.status in {"success", "success_with_warnings"}:
        adapted.status = "partial"
    return adapted
