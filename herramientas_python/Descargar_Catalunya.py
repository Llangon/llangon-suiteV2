"""Fachada operativa compatible del descargador de Catalunya."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from herramientas_python.descargadores.catalunya.browser_fallback import (
        CDP,
        JS_EXTRAER_ENLACES,
        abrir_chrome,
        cerrar_chrome,
        crear_pagina,
        encontrar_chrome,
        esperar_cdp,
        esperar_documentos,
        evaluar,
        extraer_documentos_renderizados,
        puerto_libre,
    )
    from herramientas_python.descargadores.catalunya.client import (
        DOMINIO_CATALUNYA,
        IDIOMAS_PORTAL,
        TIMEOUT_CARGA_PAGINA,
        TIMEOUT_DESCARGA,
        crear_session,
        es_url_catalunya,
        url_api_detall_publicacion,
    )
    from herramientas_python.descargadores.catalunya.documents import (
        EXTENSIONES_VALIDAS,
        MIME_A_EXTENSION,
        acortar_nombre,
        construir_nombre_archivo,
        descargar_documento,
        detectar_extension,
        es_enlace_documento,
        es_texto_generico,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        extension_desde_texto,
        extraer_documentos_de_api,
        extraer_documentos_de_html,
        fecha_desde_texto,
        limpiar_nombre,
        limpiar_titulo_documento,
        nombre_desde_content_disposition,
        nombre_logico_desde_enlace,
        normalizar,
        ruta_si_no_existe,
    )
    from herramientas_python.descargadores.catalunya.downloader import (
        ejecutar_descarga_catalunya,
        regenerar_docx_catalunya,
    )
    from herramientas_python.descargadores.catalunya.questions import obtener_snapshot_preguntas
except ModuleNotFoundError:
    from descargadores.catalunya.browser_fallback import (
        CDP,
        JS_EXTRAER_ENLACES,
        abrir_chrome,
        cerrar_chrome,
        crear_pagina,
        encontrar_chrome,
        esperar_cdp,
        esperar_documentos,
        evaluar,
        extraer_documentos_renderizados,
        puerto_libre,
    )
    from descargadores.catalunya.client import (
        DOMINIO_CATALUNYA,
        IDIOMAS_PORTAL,
        TIMEOUT_CARGA_PAGINA,
        TIMEOUT_DESCARGA,
        crear_session,
        es_url_catalunya,
        url_api_detall_publicacion,
    )
    from descargadores.catalunya.documents import (
        EXTENSIONES_VALIDAS,
        MIME_A_EXTENSION,
        acortar_nombre,
        construir_nombre_archivo,
        descargar_documento,
        detectar_extension,
        es_enlace_documento,
        es_texto_generico,
        extension_desde_content_type,
        extension_desde_contenido,
        extension_desde_nombre,
        extension_desde_texto,
        extraer_documentos_de_api,
        extraer_documentos_de_html,
        fecha_desde_texto,
        limpiar_nombre,
        limpiar_titulo_documento,
        nombre_desde_content_disposition,
        nombre_logico_desde_enlace,
        normalizar,
        ruta_si_no_existe,
    )
    from descargadores.catalunya.downloader import ejecutar_descarga_catalunya, regenerar_docx_catalunya
    from descargadores.catalunya.questions import obtener_snapshot_preguntas


def log(mensaje: object = "") -> None:
    print(mensaje, flush=True)


def _parsear_argumentos_completos(argv: list[str] | None = None):
    args = list(sys.argv[1:] if argv is None else argv)
    destination = os.path.dirname(os.path.abspath(__file__))
    regenerate = False
    if "--destino" in args:
        index = args.index("--destino")
        if index + 1 >= len(args):
            raise ValueError("Uso: python Descargar_Catalunya.py <URL> [--destino <CARPETA>]")
        destination = os.path.abspath(args[index + 1])
        del args[index : index + 2]
    if "--regenerar-docx-desde-estado" in args:
        args.remove("--regenerar-docx-desde-estado")
        regenerate = True
    if regenerate:
        if args:
            raise ValueError(
                "La regeneración desde estado no acepta una URL; indique únicamente --destino."
            )
    elif len(args) != 1:
        raise ValueError("Uso: python Descargar_Catalunya.py <URL> [--destino <CARPETA>]")
    Path(destination).mkdir(parents=True, exist_ok=True)
    return (args[0] if args else ""), destination, regenerate


def parsear_argumentos():
    """Contrato histórico: devuelve únicamente URL y carpeta de destino."""

    try:
        url, destination, _regenerate = _parsear_argumentos_completos()
        return url, destination
    except ValueError as exc:
        log(exc)
        sys.exit(1)


def _log_result(result) -> None:
    log(
        "Descarga terminada: "
        f"{result.documents_downloaded} documento(s) descargado(s), "
        f"{result.documents_skipped} omitido(s), "
        f"{len(result.document_download_errors)} error(es)."
    )
    if result.document_generated:
        log(f"Preguntas y respuestas guardadas como: {result.document_name}")
    elif result.no_changes and result.query_successful:
        log("Preguntas y respuestas: sin cambios.")
    for warning in result.warnings + result.structure_novelties:
        log(f"Aviso: {warning}")
    for error in result.errors:
        log(f"Error: {error}")
    log("RESULTADO_ESTRUCTURADO=" + json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    try:
        url, destination, regenerate = _parsear_argumentos_completos(argv)
    except ValueError as exc:
        log(exc)
        return 1
    try:
        if regenerate:
            result = regenerar_docx_catalunya(Path(destination))
        else:
            log(f"Accediendo a Contractacio Publica Catalunya: {url}")
            result = ejecutar_descarga_catalunya(url, Path(destination), log=log)
    except Exception as exc:
        log(f"Error ejecutando el descargador de Catalunya: {exc}")
        return 1
    _log_result(result)
    if result.status == "error" or not result.query_successful:
        return 1
    if not regenerate and result.documents_found == 0 and result.total_questions == 0:
        log("No se han encontrado documentos ni preguntas respondidas.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
