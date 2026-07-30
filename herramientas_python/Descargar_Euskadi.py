"""Fachada compatible y estrecha del descargador de Euskadi."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from herramientas_python.descargadores.euskadi.client import (
        TIMEOUT_DESCARGA,
        comprobar_disponible,
        crear_session,
        endpoint_comprobacion,
        endpoint_comprobacion_pid,
        endpoint_descarga,
        endpoint_descarga_pid,
        extraer_documentos,
        extraer_expediente,
        extraer_ficha_pdf,
        extraer_paquetes_modelos,
    )
    from herramientas_python.descargadores.euskadi.documents import (
        EXTENSIONES_VALIDAS,
        MIME_A_EXTENSION,
        acortar_nombre,
        construir_nombre_archivo,
        descargar_documento,
        detectar_extension,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        limpiar_nombre,
        nombre_desde_content_disposition,
        ruta_si_no_existe,
    )
    from herramientas_python.descargadores.euskadi.downloader import run_euskadi
except ModuleNotFoundError:
    from descargadores.euskadi.client import (
        TIMEOUT_DESCARGA,
        comprobar_disponible,
        crear_session,
        endpoint_comprobacion,
        endpoint_comprobacion_pid,
        endpoint_descarga,
        endpoint_descarga_pid,
        extraer_documentos,
        extraer_expediente,
        extraer_ficha_pdf,
        extraer_paquetes_modelos,
    )
    from descargadores.euskadi.documents import (
        EXTENSIONES_VALIDAS,
        MIME_A_EXTENSION,
        acortar_nombre,
        construir_nombre_archivo,
        descargar_documento,
        detectar_extension,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        limpiar_nombre,
        nombre_desde_content_disposition,
        ruta_si_no_existe,
    )
    from descargadores.euskadi.downloader import run_euskadi


def log(mensaje=""):
    print(mensaje, flush=True)


def _parsear_argumentos(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))
    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            raise ValueError("Uso: python Descargar_Euskadi.py <URL> [--destino <CARPETA>]")
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]
    if len(args) != 1:
        raise ValueError("Uso: python Descargar_Euskadi.py <URL> [--destino <CARPETA>]")
    os.makedirs(carpeta_destino, exist_ok=True)
    return args[0], carpeta_destino


def parsear_argumentos():
    try:
        return _parsear_argumentos()
    except ValueError as exc:
        log(exc)
        sys.exit(1)


def main(argv=None):
    try:
        url, carpeta_destino = _parsear_argumentos(argv)
    except ValueError as exc:
        log(exc)
        return 1
    result = run_euskadi(
        url,
        Path(carpeta_destino),
        session=crear_session(),
        download_document=descargar_documento,
        logger=log,
    )
    log(f"RESULTADO_ESTRUCTURADO={result.to_json()}")
    if result.status == "failed" and result.error:
        log(result.error)
    return 0 if result.successful else 1


if __name__ == "__main__":
    sys.exit(main())
