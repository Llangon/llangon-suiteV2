"""Fachada compatible y estrecha del descargador de Xunta de Galicia."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from herramientas_python.descargadores.xunta_galicia.downloader import run_xunta_galicia
except ModuleNotFoundError:
    from descargadores.xunta_galicia.downloader import run_xunta_galicia


def log(mensaje=""):
    print(mensaje, flush=True)


def _parsear_argumentos(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    destination = os.path.dirname(os.path.abspath(__file__))
    if "--destino" in args:
        index = args.index("--destino")
        if index + 1 >= len(args):
            raise ValueError("Uso: python Descargar_XuntaGalicia.py <URL> [--destino <CARPETA>]")
        destination = os.path.abspath(args[index + 1])
        del args[index:index + 2]
    if len(args) != 1:
        raise ValueError("Uso: python Descargar_XuntaGalicia.py <URL> [--destino <CARPETA>]")
    os.makedirs(destination, exist_ok=True)
    return args[0], destination


def parsear_argumentos():
    try:
        return _parsear_argumentos()
    except ValueError as exc:
        log(exc)
        sys.exit(1)


def main(argv=None):
    try:
        url, destination = _parsear_argumentos(argv)
    except ValueError as exc:
        log(exc)
        return 1
    result = run_xunta_galicia(url, Path(destination), logger=log)
    log(f"RESULTADO_ESTRUCTURADO={result.to_json()}")
    if result.status == "failed" and result.error:
        log(result.error)
    return 0 if result.successful else 1


if __name__ == "__main__":
    sys.exit(main())
