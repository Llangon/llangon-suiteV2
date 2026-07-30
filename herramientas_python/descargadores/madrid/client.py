"""Navegación y extracción específicas de Comunidad de Madrid."""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from urllib.parse import urljoin, urlparse

from ..common.http import create_public_session
from ..common.download_models import extension_from_name
from ..common.safe_files import sanitize_filename


TIMEOUT_DESCARGA = (5, 90)
DOMINIO_MADRID = "contratos-publicos.comunidad.madrid"


def normalizar(texto):
    text = unicodedata.normalize("NFD", str(texto or ""))
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", text).lower().strip()


def limpiar_nombre(nombre):
    return sanitize_filename(unescape(str(nombre or "")), max_length=None)


def limpiar_titulo_documento(texto):
    text = unescape(str(texto or ""))
    text = re.sub(r"\bDescargar\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPDF\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|bytes?)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\([^)]*Publicado el[^)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPublicado el\b.*$", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bFecha de\b.*$", " ", text, flags=re.IGNORECASE)
    return limpiar_nombre(re.sub(r"\s+", " ", text).strip(" .:-"))


def es_texto_generico(texto):
    normalized = normalizar(texto)
    if not normalized:
        return True
    if normalized in {
        "descargar", "pdf", "email", "secciones", "datos del expediente",
        "anuncio", "suscribase a las alertas", "menu pcon", "menu pie pcon",
    }:
        return True
    return normalized.startswith("fecha de ") or bool(
        re.fullmatch(r"\d+(?:[.,]\d+)?\s*(kb|mb|gb|bytes?)", normalized)
    )


def crear_session():
    return create_public_session()


def es_url_interna(url):
    host = urlparse(url).netloc.lower()
    return (host[4:] if host.startswith("www.") else host) == DOMINIO_MADRID


def es_enlace_ficha_pdf(url):
    return "/contrato-publico/print/pdf/" in urlparse(url).path.lower()


def es_enlace_adjunto(url):
    path = urlparse(url).path.lower()
    if es_enlace_ficha_pdf(url):
        return False
    return (
        ("/medias/" in path and "/download" in path)
        or path.endswith("/download")
        or "/download/" in path
        or bool(extension_from_name(path))
    )


def extraer_numero_expediente(soup):
    textos = [text.strip() for text in soup.stripped_strings if text.strip()]
    for index, texto in enumerate(textos[:-1]):
        if normalizar(texto) in {"numero de expediente", "n de expediente", "n expediente", "expediente"}:
            return limpiar_nombre(textos[index + 1])
    cuerpo = soup.get_text("\n", strip=True)
    patron = "N[" + chr(186) + "o]?\\s*(?:de\\s*)?expediente\\s*[:\\n]\\s*([^\\n]+)"
    match = re.search(patron, cuerpo, re.IGNORECASE)
    return limpiar_nombre(match.group(1)) if match else ""


def extraer_node_id(soup, html):
    nodo = soup.find(attrs={"data-history-node-id": True})
    if nodo:
        return nodo.get("data-history-node-id", "").strip()
    for patron in (
        r"data-history-node-id=[\"'](\d+)[\"']",
        r"page-node-(\d+)",
        r"/node/(\d+)",
        r"/print/pdf/node/(\d+)",
    ):
        match = re.search(patron, html)
        if match:
            return match.group(1)
    return ""


def extraer_enlace_ficha_pdf(soup, url_base, html):
    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if es_url_interna(url) and es_enlace_ficha_pdf(url):
            return url
    node_id = extraer_node_id(soup, html)
    return urljoin(url_base, f"/contrato-publico/print/pdf/node/{node_id}") if node_id else ""


def textos_previos_utiles(enlace, limite=25):
    result = []
    for texto in enlace.find_all_previous(string=True, limit=limite):
        value = " ".join(str(texto).split())
        if value and not es_texto_generico(value):
            result.append(value)
    return result


def nombre_logico_desde_enlace(enlace, indice):
    for key in ("download", "title"):
        value = enlace.get(key, "")
        if value and not es_texto_generico(value):
            return limpiar_titulo_documento(value)
    text = enlace.get_text(" ", strip=True)
    if text and not es_texto_generico(text):
        return limpiar_titulo_documento(text)
    for text in textos_previos_utiles(enlace):
        candidate = limpiar_titulo_documento(text)
        if candidate and not es_texto_generico(candidate):
            return candidate
    parent = enlace.find_parent(["li", "tr", "div", "section", "article"])
    if parent:
        candidate = limpiar_titulo_documento(parent.get_text(" ", strip=True))
        if candidate and not es_texto_generico(candidate):
            return candidate
    return f"documento_{indice}"


def extraer_adjuntos(soup, url_base):
    attachments = []
    seen = set()
    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if not es_url_interna(url) or not es_enlace_adjunto(url) or url.lower() in seen:
            continue
        seen.add(url.lower())
        attachments.append(
            {"url": url, "nombre_logico": nombre_logico_desde_enlace(enlace, len(attachments) + 1)}
        )
    return attachments
