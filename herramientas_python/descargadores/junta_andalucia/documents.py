"""Selección, descarga y publicación documental específica de Junta."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from ..common.download_models import (
    MIME_TO_EXTENSION,
    VALID_EXTENSIONS,
    RemoteDocument,
    build_document_filename,
    detect_document_extension,
    extension_from_content,
    extension_from_content_type,
    extension_from_name,
    name_from_content_disposition,
)
from ..common.safe_files import sanitize_filename, write_bytes_if_absent


TIMEOUT_DESCARGA = (5, 90)
MAX_DOWNLOAD_ATTEMPTS = 4
EXTENSIONES_VALIDAS = VALID_EXTENSIONS
MIME_A_EXTENSION = MIME_TO_EXTENSION


def limpiar_nombre(nombre):
    name = str(nombre or "")
    name = re.sub(r"\s*descarga\s+sello\s+de\s+tiempo.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\s*descarga\s+documento\s+anuncio\s+pdf\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(\s*activo\s*\)\s*\.?\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(\.[A-Za-z0-9]{2,5}\)\s*$", "", name)
    name = re.sub(r"^\s*\([^)]+\)\s*", "", name)
    return sanitize_filename(name, max_length=None)


def acortar_nombre(nombre, max_base=150):
    base, extension = os.path.splitext(nombre)
    return base[:max_base].rstrip(" .") + extension if len(base) > max_base else nombre


def extension_desde_nombre(nombre):
    return extension_from_name(nombre)


def nombre_desde_content_disposition(valor):
    name = name_from_content_disposition(valor)
    return limpiar_nombre(name) if name else ""


def extension_desde_contenido(contenido):
    return extension_from_content(contenido)


def extension_desde_content_type(content_type):
    return extension_from_content_type(content_type)


def detectar_extension(respuesta, nombre_logico="", archivo_url=""):
    return detect_document_extension(
        RemoteDocument(
            source_url=archivo_url,
            content=respuesta.content,
            logical_name=nombre_logico,
            content_type=respuesta.headers.get("Content-Type", ""),
            content_disposition=respuesta.headers.get("Content-Disposition", ""),
            platform="JUNTA_ANDALUCIA",
        )
    )


def construir_nombre_archivo(respuesta, nombre_logico, archivo_url, extension):
    header_name = nombre_desde_content_disposition(respuesta.headers.get("Content-Disposition", ""))
    candidate = limpiar_nombre(
        nombre_logico or header_name or os.path.basename(urlparse(archivo_url).path)
    )
    base, current_extension = os.path.splitext(candidate)
    current_extension = current_extension.lower()
    base_extension = os.path.splitext(base)[1].lower()
    if current_extension in EXTENSIONES_VALIDAS:
        if current_extension == extension or extension in ("", ".bin"):
            return acortar_nombre(candidate)
        if base_extension == extension:
            return acortar_nombre(base)
        if base_extension in EXTENSIONES_VALIDAS:
            return acortar_nombre(limpiar_nombre(os.path.splitext(base)[0]) + extension)
        return acortar_nombre(limpiar_nombre(base) + extension)
    return acortar_nombre(candidate + extension)


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    path = os.path.join(carpeta_destino, nombre_archivo)
    return (None, nombre_archivo) if os.path.exists(path) else (path, nombre_archivo)


def nombre_logico_desde_enlace(enlace):
    if enlace.get("section") == "anuncios":
        return enlace.get("itemText") or enlace.get("text") or enlace.get("title") or "anuncio"
    return enlace.get("download") or enlace.get("text") or enlace.get("title") or "documento"


def nombre_previsto_desde_enlace(enlace):
    name = limpiar_nombre(nombre_logico_desde_enlace(enlace))
    if extension_desde_nombre(name):
        return acortar_nombre(name)
    if enlace.get("section") == "anuncios":
        return acortar_nombre(name + ".pdf")
    extension = extension_desde_nombre(urlparse(enlace.get("href", "")).path)
    return acortar_nombre(name + extension) if extension else ""


def href_descargable(href):
    if not href:
        return False
    scheme = urlparse(href).scheme.lower()
    return scheme in {"http", "https"} and not href.lower().startswith("javascript:")


def descargar_por_url(session, enlace, carpeta_destino, referer):
    href = enlace.get("href", "")
    logical_name = nombre_logico_desde_enlace(enlace)
    expected = nombre_previsto_desde_enlace(enlace)
    if expected and os.path.exists(os.path.join(carpeta_destino, expected)):
        return expected, True
    response = None
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            response = session.get(
                href,
                timeout=TIMEOUT_DESCARGA,
                allow_redirects=True,
                headers={"Referer": referer},
            )
            break
        except requests.RequestException:
            if attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise
            time.sleep(0.75 * attempt)
    if response is None:
        raise RuntimeError("No se recibió respuesta al descargar el documento.")
    response.raise_for_status()
    extension = detectar_extension(response, logical_name, href)
    filename = construir_nombre_archivo(response, logical_name, href, extension)
    result = write_bytes_if_absent(Path(carpeta_destino), filename, response.content)
    return filename, result.skipped


def archivos_actuales(carpeta):
    return {path.name for path in Path(carpeta).iterdir() if path.is_file()}


def esperar_descarga_chrome(carpeta, antes, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        new_files = archivos_actuales(carpeta) - antes
        incomplete = [name for name in new_files if name.endswith((".crdownload", ".tmp"))]
        complete = [name for name in new_files if name not in incomplete]
        if complete and not incomplete:
            return complete[0]
        time.sleep(0.5)
    return ""


def descargar_por_click(page, enlace, carpeta_destino):
    expected = nombre_previsto_desde_enlace(enlace)
    if expected and os.path.exists(os.path.join(carpeta_destino, expected)):
        return expected, True
    before = archivos_actuales(carpeta_destino)
    index = int(enlace["index"])
    result = page.call(
        "Runtime.evaluate",
        {
            "expression": (
                "(() => { const a = document.querySelector(" 
                f"'[data-codex-junta-doc=\"{index}\"]'" 
                "); if (!a) return false; a.click(); return true; })()"
            ),
            "returnByValue": True,
            "awaitPromise": True,
        },
        timeout=10,
    )
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    downloaded = esperar_descarga_chrome(carpeta_destino, before)
    return downloaded, False
