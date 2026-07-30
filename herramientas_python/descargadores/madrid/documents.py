"""Persistencia segura de documentos de Comunidad de Madrid."""

from __future__ import annotations

import os
from pathlib import Path

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
from .client import TIMEOUT_DESCARGA


EXTENSIONES_VALIDAS = VALID_EXTENSIONS
MIME_A_EXTENSION = MIME_TO_EXTENSION


def limpiar_nombre(nombre):
    return sanitize_filename(nombre, max_length=None)


def acortar_nombre(nombre, max_base=150):
    base, ext = os.path.splitext(nombre)
    return base[:max_base].rstrip(" .") + ext if len(base) > max_base else nombre


def extension_desde_nombre(nombre):
    return extension_from_name(nombre)


def nombre_desde_content_disposition(valor):
    return name_from_content_disposition(valor)


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
            platform="COMUNIDAD_MADRID",
        )
    )


def construir_nombre_archivo(respuesta, nombre_logico, archivo_url, ext):
    return acortar_nombre(
        build_document_filename(
            RemoteDocument(
                source_url=archivo_url,
                content=respuesta.content,
                logical_name=nombre_logico,
                content_type=respuesta.headers.get("Content-Type", ""),
                content_disposition=respuesta.headers.get("Content-Disposition", ""),
                platform="COMUNIDAD_MADRID",
            ),
            ext,
        )
    )


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    ruta = os.path.join(carpeta_destino, nombre_archivo)
    return (None, nombre_archivo) if os.path.exists(ruta) else (ruta, nombre_archivo)


def descargar_documento(session, url, nombre_logico, carpeta_destino, referer, *, logger=print):
    logger(f"Descargando: {url}")
    response = session.get(
        url,
        timeout=TIMEOUT_DESCARGA,
        allow_redirects=True,
        headers={"Referer": referer},
    )
    response.raise_for_status()
    extension = detectar_extension(response, nombre_logico, url)
    filename = construir_nombre_archivo(response, nombre_logico, url, extension)
    result = write_bytes_if_absent(Path(carpeta_destino), filename, response.content)
    if result.skipped:
        logger(f"Omitido, ya existe: {filename}")
        return "omitido", filename
    logger(f"Guardado como: {filename}")
    return "descargado", filename

