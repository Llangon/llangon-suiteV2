"""Navegación CDP para las descargas protegidas por reCAPTCHA v3 de Xunta."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import websocket

from ..common.http import DEFAULT_USER_AGENT
from .documents import XuntaCaptchaBlockedError, XuntaDocumentError


PAGE_TIMEOUT = 45
DOWNLOAD_TIMEOUT = 60


class CDP:
    def __init__(self, websocket_url: str):
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.next_id = 1

    def close(self) -> None:
        try:
            self.ws.close()
        except (OSError, websocket.WebSocketException):
            return

    def call(self, method: str, params: dict | None = None, timeout: int = 30) -> dict:
        message_id = self.next_id
        self.next_id += 1
        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result", {})


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def find_browser() -> str:
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((candidate for candidate in candidates if candidate and os.path.isfile(candidate)), "")


def _wait_for_cdp(port: int, timeout: int = 15) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=0.5)
            if response.status_code == 200:
                return response.json()
        except (requests.RequestException, ValueError):
            time.sleep(0.2)
    raise RuntimeError("Chrome no ha abierto el puerto de control para Xunta.")


def open_browser():
    executable = find_browser()
    if not executable:
        raise RuntimeError("No se ha encontrado Chrome ni Edge para descargar desde Xunta.")
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="xunta_descargas_chrome_")
    command = [
        executable,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,2200",
        "--window-position=-32000,-32000",
        "about:blank",
    ]
    popen_options: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, **popen_options)
    try:
        version = _wait_for_cdp(port)
        return process, profile, CDP(version["webSocketDebuggerUrl"]), port
    except Exception:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
        shutil.rmtree(profile, ignore_errors=True)
        raise


def create_page(browser: CDP, port: int, download_directory: Path | str) -> CDP:
    websocket_url = ""
    deadline = time.time() + 10
    while time.time() < deadline and not websocket_url:
        pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        websocket_url = next(
            (
                item.get("webSocketDebuggerUrl", "")
                for item in pages
                if item.get("type") == "page" and item.get("webSocketDebuggerUrl")
            ),
            "",
        )
        if not websocket_url:
            browser.call("Target.createTarget", {"url": "about:blank"}, timeout=5)
            time.sleep(0.2)
    if not websocket_url:
        raise RuntimeError("No se ha podido abrir una pestaña para Xunta.")
    page = CDP(websocket_url)
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Network.enable")
    # contratosdegalicia.gal devuelve una página señuelo vacía al User-Agent
    # identificable de Chrome headless. Mantenemos el navegador en segundo
    # plano, pero usamos el mismo User-Agent público que el inventario HTTP.
    page.call(
        "Network.setUserAgentOverride",
        {"userAgent": DEFAULT_USER_AGENT, "platform": "Windows"},
    )
    path = str(Path(download_directory).resolve())
    errors: list[Exception] = []
    for target, method in ((browser, "Browser.setDownloadBehavior"), (page, "Page.setDownloadBehavior")):
        try:
            target.call(method, {"behavior": "allow", "downloadPath": path})
        except Exception as exc:
            errors.append(exc)
    if len(errors) == 2:
        raise RuntimeError("Chrome no ha permitido configurar la carpeta de descargas.") from errors[-1]
    return page


def _evaluate(page: CDP, expression: str, timeout: int = 30):
    result = page.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    return result.get("result", {}).get("value")


def navigate(page: CDP, url: str) -> None:
    page.call("Page.navigate", {"url": url}, timeout=15)
    deadline = time.time() + PAGE_TIMEOUT
    while time.time() < deadline:
        state = _evaluate(
            page,
            "({"
            "form:Boolean(document.querySelector('#formDescargaG'))," 
            "recaptcha:typeof grecaptcha === 'object' && typeof grecaptcha.execute === 'function',"
            "blocked:Boolean(document.body && document.body.classList.contains('block'))"
            "})",
            timeout=10,
        )
        if state.get("form") and state.get("recaptcha"):
            return
        if state.get("blocked"):
            raise RuntimeError(
                "Xunta bloqueó la navegación automatizada antes de mostrar la ficha."
            )
        time.sleep(0.25)
    raise RuntimeError("La ficha de Xunta no terminó de cargar en Chrome.")


def _files(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir() if path.is_file()}


def _wait_for_download(
    directory: Path,
    before: set[str],
    timeout: int,
    *,
    expected_extension: str = "",
) -> Path | None:
    expected = expected_extension.casefold()
    if expected and not expected.startswith("."):
        expected = f".{expected}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = _files(directory) - before
        incomplete = {name for name in current if name.casefold().endswith((".crdownload", ".tmp"))}
        complete = sorted(name for name in current if name not in incomplete)
        if expected:
            complete = [name for name in complete if Path(name).suffix.casefold() == expected]
        if complete:
            return directory / complete[0]
        time.sleep(0.25)
    return None


def download_by_click(
    page: CDP,
    call: str,
    download_directory: Path | str,
    *,
    timeout: int = DOWNLOAD_TIMEOUT,
    expected_extension: str = "",
) -> Path:
    directory = Path(download_directory)
    before = _files(directory)
    call_literal = json.dumps(call, ensure_ascii=False)
    clicked = _evaluate(
        page,
        r"""
        (() => {
          const expected = __CALL__;
          const links = Array.from(document.querySelectorAll('a[href]'))
            .filter((a) => (a.getAttribute('href') || '') === expected);
          const target = links.find((a) => !/^\s*Formato\b/i.test(a.textContent || '')) || links[0];
          if (!target) return false;
          target.click();
          return true;
        })()
        """.replace("__CALL__", call_literal),
        timeout=10,
    )
    if not clicked:
        raise XuntaDocumentError("Chrome no encontró el enlace documental esperado de Xunta.")
    downloaded = _wait_for_download(
        directory,
        before,
        timeout,
        expected_extension=expected_extension,
    )
    if downloaded:
        return downloaded
    recaptcha_active = _evaluate(
        page,
        "Boolean(document.querySelector('#recaptchav3active')) || "
        "/recaptcha|captcha|non son un robot|no soy un robot|not a robot/i.test("
        "(document.title || '') + ' ' + (document.body ? document.body.innerText : '')"
        ")",
        timeout=10,
    )
    if recaptcha_active:
        raise XuntaCaptchaBlockedError(
            "XUNTA_RECAPTCHA_BLOCKED: la plataforma no autorizó la descarga desatendida."
        )
    raise XuntaDocumentError("Chrome no publicó el archivo de Xunta dentro del tiempo esperado.")


def close_browser(process, profile: str, browser: CDP | None = None, page: CDP | None = None) -> None:
    try:
        if page:
            page.close()
    except Exception:
        pass
    try:
        if browser:
            browser.close()
    except Exception:
        pass
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    shutil.rmtree(profile, ignore_errors=True)
