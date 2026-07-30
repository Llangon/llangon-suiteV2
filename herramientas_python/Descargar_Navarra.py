"""Fachada compatible y estrecha del descargador de Navarra."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from herramientas_python.descargadores.navarra.client import (
        BASE_API_PLENA,
        DOMINIO_PCN,
        DOMINIO_PLENA,
        RUTA_DETALLE_PCN,
        RUTA_DETALLE_PLENA,
        RUTA_DOCUMENTO_PCN,
        TIMEOUT_DESCARGA,
        cabeceras_plena,
        clave_trabajo,
        consultar_plena,
        crear_session,
        eliminar_duplicados,
        es_enlace_documento_pcn,
        es_url_pcn,
        es_url_plena,
        extraer_codigo_anuncio,
        extraer_documentos_pcn,
        extraer_url_plena,
        host_sin_www,
        normalizar_lista_json,
        url_plena_para_codigo,
    )
    from herramientas_python.descargadores.navarra.documents import (
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
    from herramientas_python.descargadores.navarra.downloader import run_navarra
except ModuleNotFoundError:
    from descargadores.navarra.client import (
        BASE_API_PLENA,
        DOMINIO_PCN,
        DOMINIO_PLENA,
        RUTA_DETALLE_PCN,
        RUTA_DETALLE_PLENA,
        RUTA_DOCUMENTO_PCN,
        TIMEOUT_DESCARGA,
        cabeceras_plena,
        clave_trabajo,
        consultar_plena,
        crear_session,
        eliminar_duplicados,
        es_enlace_documento_pcn,
        es_url_pcn,
        es_url_plena,
        extraer_codigo_anuncio,
        extraer_documentos_pcn,
        extraer_url_plena,
        host_sin_www,
        normalizar_lista_json,
        url_plena_para_codigo,
    )
    from descargadores.navarra.documents import (
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
    from descargadores.navarra.downloader import run_navarra


def log(mensaje=""):
    print(mensaje, flush=True)


def _parsear_argumentos(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))
    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            raise ValueError("Uso: python Descargar_Navarra.py <URL> [--destino <CARPETA>]")
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]
    if len(args) != 1:
        raise ValueError("Uso: python Descargar_Navarra.py <URL> [--destino <CARPETA>]")
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
    result = run_navarra(
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
