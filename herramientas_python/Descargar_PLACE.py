"""Fachada operativa compatible y estrecha del descargador de PLACE."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from herramientas_python.descargadores.common.download_models import (
        MIME_TO_EXTENSION as MIME_A_EXTENSION,
        VALID_EXTENSIONS as EXTENSIONES_VALIDAS,
    )
    from herramientas_python.descargadores.place.access import (
        DEFAULT_SUITE_DB_PATH,
        PLACE_PASSWORD_ENV,
        PLACE_USER_ENV,
        credenciales_place_desde_suite,
        resolver_credenciales_place,
    )
    from herramientas_python.descargadores.place.documents import (
        base_desde_soup,
        candidatos_para_segunda_fase,
        construir_nombre_archivo,
        crear_session,
        descargar_documento,
        detectar_extension,
        es_enlace_documento,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        limpiar_nombre,
        nombre_desde_content_disposition,
        nombre_desde_tabla,
        procesar_html,
        procesar_html_pliego,
        procesar_pliegos_descargados,
        ruta_si_no_existe,
    )
    from herramientas_python.descargadores.place.downloader import (
        cargar_modulo_preguntas_place,
        procesar_preguntas_y_respuestas,
        run_place,
    )
except ModuleNotFoundError:
    from descargadores.common.download_models import (
        MIME_TO_EXTENSION as MIME_A_EXTENSION,
        VALID_EXTENSIONS as EXTENSIONES_VALIDAS,
    )
    from descargadores.place.access import (
        DEFAULT_SUITE_DB_PATH,
        PLACE_PASSWORD_ENV,
        PLACE_USER_ENV,
        credenciales_place_desde_suite,
        resolver_credenciales_place,
    )
    from descargadores.place.documents import (
        base_desde_soup,
        candidatos_para_segunda_fase,
        construir_nombre_archivo,
        crear_session,
        descargar_documento,
        detectar_extension,
        es_enlace_documento,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        limpiar_nombre,
        nombre_desde_content_disposition,
        nombre_desde_tabla,
        procesar_html,
        procesar_html_pliego,
        procesar_pliegos_descargados,
        ruta_si_no_existe,
    )
    from descargadores.place.downloader import (
        cargar_modulo_preguntas_place,
        procesar_preguntas_y_respuestas,
        run_place,
    )


def _parsear_argumentos(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    destination = os.path.dirname(os.path.abspath(__file__))
    if "--destino" in args:
        index = args.index("--destino")
        if index + 1 >= len(args):
            raise ValueError("Uso: python Descargar_PLACE.py <URL> [--destino <CARPETA>]")
        destination = os.path.abspath(args[index + 1])
        del args[index:index + 2]
    if len(args) != 1:
        raise ValueError("Uso: python Descargar_PLACE.py <URL> [--destino <CARPETA>]")
    os.makedirs(destination, exist_ok=True)
    return args[0], destination


def parsear_argumentos():
    try:
        return _parsear_argumentos()
    except ValueError as exc:
        print(exc, flush=True)
        sys.exit(1)


def main(argv=None):
    try:
        url, destination = _parsear_argumentos(argv)
    except ValueError as exc:
        print(exc, flush=True)
        return 1
    result = run_place(url, Path(destination), logger=lambda message="": print(message, flush=True))
    print(f"RESULTADO_ESTRUCTURADO={result.to_json()}", flush=True)
    if result.status == "failed":
        if result.error:
            print(result.error, flush=True)
        return 1
    if result.general_data.get("legacy_exit_code") == 2:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
