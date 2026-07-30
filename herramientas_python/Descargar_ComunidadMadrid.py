"""Fachada compatible y estrecha del descargador de Comunidad de Madrid."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from herramientas_python.descargadores.madrid.client import (
        DOMINIO_MADRID,
        TIMEOUT_DESCARGA,
        crear_session,
        es_enlace_adjunto,
        es_enlace_ficha_pdf,
        es_texto_generico,
        es_url_interna,
        extraer_adjuntos,
        extraer_enlace_ficha_pdf,
        extraer_node_id,
        extraer_numero_expediente,
        limpiar_titulo_documento,
        nombre_logico_desde_enlace,
        normalizar,
        textos_previos_utiles,
    )
    from herramientas_python.descargadores.madrid.documents import (
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
    from herramientas_python.descargadores.madrid.downloader import run_madrid
except ModuleNotFoundError:
    from descargadores.madrid.client import (
        DOMINIO_MADRID,
        TIMEOUT_DESCARGA,
        crear_session,
        es_enlace_adjunto,
        es_enlace_ficha_pdf,
        es_texto_generico,
        es_url_interna,
        extraer_adjuntos,
        extraer_enlace_ficha_pdf,
        extraer_node_id,
        extraer_numero_expediente,
        limpiar_titulo_documento,
        nombre_logico_desde_enlace,
        normalizar,
        textos_previos_utiles,
    )
    from descargadores.madrid.documents import (
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
    from descargadores.madrid.downloader import run_madrid


def log(mensaje=""):
    print(mensaje, flush=True)


def _parsear_argumentos(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))
    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            raise ValueError("Uso: python Descargar_ComunidadMadrid.py <URL> [--destino <CARPETA>]")
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]
    if len(args) != 1:
        raise ValueError("Uso: python Descargar_ComunidadMadrid.py <URL> [--destino <CARPETA>]")
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
    result = run_madrid(
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
