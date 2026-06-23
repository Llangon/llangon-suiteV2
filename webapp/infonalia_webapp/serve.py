from __future__ import annotations

import os
import socket
import sys
from http.server import ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen

from .deployment import AlreadyRunningError, FileLock, load_deployment_env, setup_rotating_logger


LOGGER_NAME = "llangon.local_web"


def configured_host() -> str:
    return os.environ.get("INFONALIA_HOST", "127.0.0.1").strip() or "127.0.0.1"


def configured_port() -> int:
    raw = os.environ.get("INFONALIA_PORT", "8787").strip() or "8787"
    return int(raw)


def allow_non_loopback() -> bool:
    return os.environ.get("INFONALIA_ALLOW_NON_LOOPBACK", "0").strip() == "1"


def validate_host(host: str) -> None:
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    if allow_non_loopback():
        return
    raise ValueError("Por seguridad, el servidor local debe escuchar en 127.0.0.1.")


def health_url(host: str, port: int) -> str:
    target_host = "127.0.0.1" if host == "localhost" else host
    return f"http://{target_host}:{port}/api/health"


def healthcheck_ok(host: str, port: int, *, timeout: float = 1.5) -> bool:
    try:
        with urlopen(health_url(host, port), timeout=timeout) as response:  # nosec B310 - local loopback only
            return response.status == 200 and b'"status": "ok"' in response.read(200)
    except (OSError, URLError, TimeoutError):
        return False


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def serve_forever(host: str, port: int) -> None:
    from . import app

    app.init_db()
    repaired = app.repair_internal_download_routes()
    server = ThreadingHTTPServer((host, port), app.InfonaliaHandler)
    logger = setup_rotating_logger(LOGGER_NAME, "web.log")
    logger.info("Servidor iniciado en http://%s:%s", host, port)
    if repaired:
        logger.info("Rutas de descarga normalizadas: %s", repaired)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        logger.info("Servidor detenido")


def main() -> int:
    load_deployment_env()
    logger = setup_rotating_logger(LOGGER_NAME, "web.log")
    try:
        host = configured_host()
        port = configured_port()
        validate_host(host)
    except Exception as exc:
        logger.error("Configuracion invalida del servidor local: %s", exc)
        print(f"Configuracion invalida del servidor local: {exc}", file=sys.stderr)
        return 2

    if healthcheck_ok(host, port):
        logger.info("Servidor ya activo en %s", health_url(host, port))
        return 0
    if port_is_open(host, port):
        logger.error("El puerto %s ya esta ocupado por otro proceso.", port)
        print(f"El puerto {port} ya esta ocupado por otro proceso.", file=sys.stderr)
        return 3

    try:
        with FileLock("web"):
            serve_forever(host, port)
    except AlreadyRunningError:
        logger.info("Arranque omitido: ya hay una instancia en ejecucion.")
        return 0
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario.")
        return 0
    except Exception:
        logger.exception("Fallo inesperado del servidor local.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

