"""Sesión pública, rutas y GET JSON de Catalunya."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

import requests

from ..common.http import create_public_session

from .errors import CatalunyaAccessError, CatalunyaStructureError


TIMEOUT_CARGA_PAGINA = 60
TIMEOUT_DESCARGA = (5, 90)
DOMINIO_CATALUNYA = "contractaciopublica.cat"
IDIOMAS_PORTAL = {"ca", "es", "en", "oc"}


def crear_session() -> requests.Session:
    return create_public_session()


def es_url_catalunya(url: object) -> bool:
    host = urlparse(str(url or "")).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host == DOMINIO_CATALUNYA


def origen_catalunya(url: str) -> str:
    parsed = urlparse(url)
    if not es_url_catalunya(url):
        return ""
    return f"{parsed.scheme or 'https'}://{parsed.netloc}"


def idioma_desde_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[0].lower() if parts and parts[0].lower() in IDIOMAS_PORTAL else "ca"


def identificadores_publicacion(url: str) -> tuple[str, ...]:
    parsed = urlparse(url)
    if not es_url_catalunya(url):
        return ()
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if parts and parts[0].lower() in IDIOMAS_PORTAL:
        parts = parts[1:]
    if len(parts) not in (2, 3) or parts[0].lower() != "detall-publicacio":
        return ()
    identifiers = tuple(parts[1:])
    if not all(re.fullmatch(r"[A-Za-z0-9-]+", value) for value in identifiers):
        return ()
    return identifiers


def url_api_detall_publicacion(url: str) -> str:
    identifiers = identificadores_publicacion(url)
    origin = origen_catalunya(url)
    if not identifiers or not origin:
        return ""
    return f"{origin}/portal-api/detall-publicacio-expedient/{'/'.join(identifiers)}"


def portal_api_url(origin: str, path: str) -> str:
    return f"{origin.rstrip('/')}/portal-api/{path.lstrip('/')}"


def get_json(session, url: str, *, referer: str = "", params: dict | None = None):
    headers = {"Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    try:
        response = session.get(
            url,
            timeout=TIMEOUT_DESCARGA,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise CatalunyaAccessError(f"No se pudo consultar Catalunya: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise CatalunyaStructureError("Catalunya no devolvió un JSON válido.") from exc
    if not isinstance(payload, (dict, list)):
        raise CatalunyaStructureError("Catalunya devolvió una respuesta JSON inesperada.")
    return payload
