"""Validación de URLs y detección conservadora de retos de acceso de PLACE."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


PLACE_ROOT_HOST = "contrataciondelestado.es"
_JS_CHALLENGE_MARKERS = (
    "please enable javascript to view the page content",
    "support id",
)
_INTERACTION_MARKERS = (
    "captcha",
    "verify you are human",
    "verification required",
    "security check",
    "access denied",
    "verifique que es humano",
    "verificación requerida",
)


def es_host_place(host: str | None) -> bool:
    """Devuelve si el host pertenece a la infraestructura pública de PLACE."""

    normalized = str(host or "").strip().casefold().rstrip(".")
    return normalized == PLACE_ROOT_HOST or normalized.endswith(f".{PLACE_ROOT_HOST}")


def canonicalizar_url_place(url: str) -> str:
    """Normaliza enlaces de PLACE a HTTPS sin alterar URLs ajenas."""

    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() == "http" and es_host_place(parsed.hostname):
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return raw


def es_url_place_segura(url: str) -> bool:
    """Autoriza solo navegación HTTPS hacia PLACE o sus subdominios."""

    parsed = urlsplit(str(url or "").strip())
    return parsed.scheme.casefold() == "https" and es_host_place(parsed.hostname)


def _texto_visible(contenido: bytes | bytearray | memoryview | str | object) -> str:
    if isinstance(contenido, str):
        return contenido[:65536].casefold()
    if isinstance(contenido, (bytes, bytearray, memoryview)):
        return bytes(contenido)[:65536].decode("utf-8", errors="ignore").casefold()
    return str(contenido or "")[:65536].casefold()


def es_desafio_javascript_place(contenido: bytes | bytearray | memoryview | str | object) -> bool:
    """Detecta la pantalla WAF de PLACE que pide habilitar JavaScript."""

    sample = _texto_visible(contenido)
    return all(marker in sample for marker in _JS_CHALLENGE_MARKERS)


def requiere_interaccion_place(contenido: bytes | bytearray | memoryview | str | object) -> bool:
    """Detecta un reto que no debe automatizarse si persiste en el navegador."""

    sample = _texto_visible(contenido)
    return es_desafio_javascript_place(sample) or any(marker in sample for marker in _INTERACTION_MARKERS)
