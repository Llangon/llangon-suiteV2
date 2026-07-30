"""Fachada compatible y estrecha del descargador de Junta de Andalucía."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from herramientas_python.descargadores.junta_andalucia.browser import *  # noqa: F403
    from herramientas_python.descargadores.junta_andalucia.downloader import run_junta_andalucia
except ModuleNotFoundError:
    from descargadores.junta_andalucia.browser import *  # noqa: F403
    from descargadores.junta_andalucia.downloader import run_junta_andalucia


def log(mensaje=""):
    print(mensaje, flush=True)


def _parsear_argumentos(argv=None):
    incluir_sellos = INCLUIR_SELLOS_TIEMPO  # noqa: F405
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))
    urls = []
    args = list(sys.argv[1:] if argv is None else argv)
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--incluir-sellos":
            incluir_sellos = True
        elif argument == "--sin-sellos":
            incluir_sellos = False
        elif argument == "--destino":
            if index + 1 >= len(args):
                raise ValueError(
                    "Uso: python Descargar_JuntaAndalucia.py <URL> "
                    "[--incluir-sellos] [--destino <CARPETA>]"
                )
            carpeta_destino = os.path.abspath(args[index + 1])
            index += 1
        else:
            urls.append(argument)
        index += 1
    if len(urls) != 1:
        raise ValueError(
            "Uso: python Descargar_JuntaAndalucia.py <URL> "
            "[--incluir-sellos] [--destino <CARPETA>]"
        )
    os.makedirs(carpeta_destino, exist_ok=True)
    return urls[0], incluir_sellos, carpeta_destino


def parsear_argumentos():
    try:
        return _parsear_argumentos()
    except ValueError as exc:
        log(exc)
        sys.exit(1)


def main(argv=None):
    try:
        url, incluir_sellos, carpeta_destino = _parsear_argumentos(argv)
    except ValueError as exc:
        log(exc)
        return 1
    result = run_junta_andalucia(
        url,
        Path(carpeta_destino),
        incluir_sellos=incluir_sellos,
        logger=log,
    )
    log(f"RESULTADO_ESTRUCTURADO={result.to_json()}")
    if result.status == "failed" and result.error:
        log(result.error)
    return 0 if result.successful else 1


if __name__ == "__main__":
    sys.exit(main())
