from __future__ import annotations

import re
from urllib.parse import urlparse

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


def normalize_url(value: object) -> str:
    url = clean_text(value)
    if not url:
        return ""
    if url.strip("<>") in {"http://", "https://"}:
        return ""
    url = url.strip("<>")
    lower = url.lower()
    if lower.startswith(("http://", "https://", "mailto:")):
        return url
    if url.startswith("//"):
        return "https:" + url
    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}([/:?#].*)?$", url, re.IGNORECASE):
        return "https://" + url
    return url


def should_update_url(current: object, incoming: object) -> bool:
    current_url = clean_text(current)
    incoming_url = clean_text(incoming)
    if not incoming_url:
        return False
    if not current_url:
        return True
    return normalize_url(current_url) != current_url and normalize_url(current_url) == incoming_url


def detectar_plataforma(url: str) -> str:
    normalized_url = normalize_url(url)
    parsed = urlparse(normalized_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    full_url = normalized_url.lower()

    if "contrataciondelestado.es" in host or "contrataciondelestado.es" in full_url:
        return "PLACE"
    if (
        "juntadeandalucia.es" in host
        or "junta-andalucia.es" in host
        or "pdc-front-publico" in path
        or "pdc-front-publico" in full_url
    ):
        return "Junta Andalucia"
    if "contratos-publicos.comunidad.madrid" in host or "contratos-publicos.comunidad.madrid" in full_url:
        return "Comunidad Madrid"
    if "contratacion.euskadi.eus" in host or (
        (host == "euskadi.eus" or host.endswith(".euskadi.eus")) and "/anuncio_contratacion/" in path
    ) or "contratacion.euskadi.eus" in full_url:
        return "Euskadi"
    if host == "contractaciopublica.cat" or host.endswith(".contractaciopublica.cat") or "contractaciopublica.cat" in full_url:
        return "Catalunya"
    if host in {"hacienda.navarra.es", "licitacionelectronica.navarra.es"}:
        return "Navarra"
    if host == "contratosdegalicia.gal" or host.endswith(".contratosdegalicia.gal"):
        return "Xunta de Galicia"
    return ""
