import os
import subprocess
import sys
from urllib.parse import urlparse


def log(mensaje=""):
    print(mensaje, flush=True)


def script_en_misma_carpeta(nombre):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre)


def leer_url_desde_http_url(carpeta):
    ruta = os.path.join(carpeta, "HTTP.url")
    if not os.path.exists(ruta):
        return ""

    with open(ruta, "r", encoding="utf-8-sig", errors="ignore") as f:
        for linea in f:
            linea = linea.strip()
            if linea.lower().startswith("url="):
                return linea[4:].strip()

    return ""


def detectar_plataforma(url):
    host = urlparse(url).netloc.lower()
    ruta = urlparse(url).path.lower()

    if "contrataciondelestado.es" in host:
        return "PLACE"

    if (
        "juntadeandalucia.es" in host
        or "junta-andalucia.es" in host
        or "pdc-front-publico" in ruta
    ):
        return "JUNTA_ANDALUCIA"

    if "contratos-publicos.comunidad.madrid" in host:
        return "COMUNIDAD_MADRID"

    if (
        "contratacion.euskadi.eus" in host
        or (
            (host == "euskadi.eus" or host.endswith(".euskadi.eus"))
            and "/anuncio_contratacion/" in ruta
        )
    ):
        return "EUSKADI"

    return ""


def ejecutar(script, argumentos, carpeta_destino):
    if not os.path.exists(script):
        log(f"No se encuentra el script necesario: {script}")
        return 1

    comando = [sys.executable, script] + argumentos + ["--destino", carpeta_destino]
    return subprocess.call(comando, cwd=carpeta_destino)


def main():
    carpeta_destino = os.getcwd()

    if len(sys.argv) >= 2:
        url = sys.argv[1]
        opciones = sys.argv[2:]
    else:
        url = leer_url_desde_http_url(carpeta_destino)
        opciones = []

    if not url:
        log("Uso: python Descargar_Licitacion.py <URL> [opciones]")
        log("Tambien puede ejecutarse sin argumentos desde una carpeta que contenga HTTP.url.")
        sys.exit(1)

    plataforma = detectar_plataforma(url)

    if plataforma == "PLACE":
        log("Plataforma detectada: PLACE")
        script = script_en_misma_carpeta("Descargar_PLACE.py")
        sys.exit(ejecutar(script, [url], carpeta_destino))

    if plataforma == "JUNTA_ANDALUCIA":
        log("Plataforma detectada: Junta de Andalucia")
        script = script_en_misma_carpeta("Descargar_JuntaAndalucia.py")
        sys.exit(ejecutar(script, [url] + opciones, carpeta_destino))

    if plataforma == "COMUNIDAD_MADRID":
        log("Plataforma detectada: Comunidad de Madrid")
        script = script_en_misma_carpeta("Descargar_ComunidadMadrid.py")
        sys.exit(ejecutar(script, [url], carpeta_destino))

    if plataforma == "EUSKADI":
        log("Plataforma detectada: Euskadi")
        script = script_en_misma_carpeta("Descargar_Euskadi.py")
        sys.exit(ejecutar(script, [url], carpeta_destino))

    log("No se reconoce la plataforma de esta URL.")
    log("Por ahora estan soportadas: PLACE, Junta de Andalucia, Comunidad de Madrid y Euskadi.")
    sys.exit(1)


if __name__ == "__main__":
    main()
