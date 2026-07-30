"""Acceso público y extracción específica de Navarra."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

from ..common.http import create_public_session
from ..common.safe_files import sanitize_filename


TIMEOUT_DESCARGA = (5, 90)
DOMINIO_PCN = "hacienda.navarra.es"
DOMINIO_PLENA = "licitacionelectronica.navarra.es"
RUTA_DOCUMENTO_PCN = "/sicpportal/mtogeneradocumento.aspx"
RUTA_DETALLE_PCN = "/sicpportal/mtoanunciosmodalidad.aspx"
RUTA_DETALLE_PLENA = "/licitador/licitadores/detalle/"
BASE_API_PLENA = f"https://{DOMINIO_PLENA}/licitador/api"


def limpiar_nombre(nombre):
    return sanitize_filename(unescape(str(nombre or "")), max_length=None)


def crear_session():
    return create_public_session(
        accept="text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"
    )


def host_sin_www(url):
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def es_url_pcn(url):
    return host_sin_www(url) == DOMINIO_PCN


def es_url_plena(url):
    return host_sin_www(url) == DOMINIO_PLENA


def extraer_codigo_anuncio(url):
    parsed = urlparse(url)
    if host_sin_www(url) == DOMINIO_PCN:
        valores = parse_qs(parsed.query, keep_blank_values=False)
        for clave, items in valores.items():
            if clave.lower() == "cod" and items:
                return items[0].strip()
    if host_sin_www(url) == DOMINIO_PLENA:
        match = re.search(r"/licitadores/detalle/([^/?#]+)", parsed.path, re.IGNORECASE)
        if match:
            return unquote(match.group(1)).strip()
    return ""


def es_enlace_documento_pcn(url):
    parsed = urlparse(url)
    if host_sin_www(url) != DOMINIO_PCN or parsed.path.lower() != RUTA_DOCUMENTO_PCN:
        return False
    claves = {clave.lower() for clave in parse_qs(parsed.query)}
    return {"doa", "dol"}.issubset(claves)


def extraer_documentos_pcn(soup, url_base):
    documentos = []
    vistos = set()
    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if not es_enlace_documento_pcn(url):
            continue
        clave = url.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        documentos.append(
            {
                "url": url,
                "nombre_logico": limpiar_nombre(enlace.get_text(" ", strip=True)),
                "origen": "PCN",
            }
        )
    return documentos


def extraer_url_plena(soup, url_base):
    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if es_url_plena(url) and RUTA_DETALLE_PLENA in urlparse(url).path.lower():
            return url
    return ""


def url_plena_para_codigo(codigo):
    return f"https://{DOMINIO_PLENA}/licitador/licitadores/detalle/{quote(codigo, safe='')}/s"


def cabeceras_plena(referer):
    return {
        "Origin": f"https://{DOMINIO_PLENA}",
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
    }


def normalizar_lista_json(respuesta, descripcion):
    datos = respuesta.json()
    if datos is None:
        return []
    if not isinstance(datos, list):
        raise ValueError(f"Respuesta inesperada al consultar {descripcion} en PLENA.")
    return datos


def consultar_plena(session, codigo, url_plena):
    headers = cabeceras_plena(url_plena)
    url_expediente = f"{BASE_API_PLENA}/expedientes/getExpedienteAllowAnonymous/{quote(codigo, safe='')}"
    respuesta = session.get(url_expediente, timeout=TIMEOUT_DESCARGA, headers=headers)
    respuesta.raise_for_status()
    expediente = respuesta.json()
    if not isinstance(expediente, dict) or not expediente.get("idExpediente"):
        raise ValueError("PLENA no ha devuelto un identificador de expediente valido.")

    pliegos = []
    for documento in expediente.get("documentos") or []:
        if not isinstance(documento, dict) or documento.get("linea") in (None, ""):
            continue
        linea = str(documento["linea"]).strip()
        nombre = limpiar_nombre(documento.get("nombreFichero") or f"pliego_{linea}")
        url = (
            f"https://{DOMINIO_PCN}/sicpportal/mtoGeneraDocumento.aspx"
            f"?DOA={quote(codigo, safe='')}&DOL={quote(linea, safe='')}"
        )
        pliegos.append({"url": url, "nombre_logico": nombre, "origen": "PLENA-pliegos"})

    id_expediente = quote(str(expediente["idExpediente"]), safe="")
    url_documentos = f"{BASE_API_PLENA}/expedientes/getDocumentosAnonymous/{id_expediente}"
    respuesta_documentos = session.get(url_documentos, timeout=TIMEOUT_DESCARGA, headers=headers)
    respuesta_documentos.raise_for_status()
    publicados = normalizar_lista_json(respuesta_documentos, "documentos publicados")

    adicionales = []
    for documento in publicados:
        if not isinstance(documento, dict):
            continue
        referencia = str(documento.get("referenciaDocumento") or "").strip().rstrip("/")
        nombre_original = str(documento.get("nombreDocumento") or "").strip().lstrip("/")
        if not referencia or not nombre_original:
            continue
        ruta_remota = f"{referencia}/{nombre_original}"
        adicionales.append(
            {
                "url": (
                    f"{BASE_API_PLENA}/file/downloadFileAllowAnonymous"
                    f"?fullPath={quote(ruta_remota, safe='')}"
                ),
                "nombre_logico": limpiar_nombre(nombre_original),
                "origen": "PLENA-documentos",
                "headers": headers,
            }
        )
    return pliegos, adicionales


def clave_trabajo(trabajo):
    url = trabajo["url"]
    parsed = urlparse(url)
    if es_enlace_documento_pcn(url):
        query = {clave.lower(): valor for clave, valor in parse_qs(parsed.query).items()}
        doa = (query.get("doa") or [""])[0].lower()
        dol = (query.get("dol") or [""])[0].lower()
        return "pcn", doa, dol
    return "url", url.lower()


def eliminar_duplicados(trabajos):
    resultado = []
    vistos = set()
    for trabajo in trabajos:
        clave = clave_trabajo(trabajo)
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(trabajo)
    return resultado
