"""Fallback de navegador estándar para documentos públicos bloqueados por JS en PLACE.

La vía no copia cookies ni credenciales a ``requests`` y tampoco intenta resolver
CAPTCHA o retos que requieran interacción. Solo abre una ficha pública de PLACE,
deja que el navegador ejecute su JavaScript ordinario y activa el enlace oficial
que ya había sido descubierto por la vía HTTP.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import requests

from .challenge import canonicalizar_url_place, es_url_place_segura, requiere_interaccion_place
from .errors import PlaceBrowserError, PlaceBrowserInteractionRequiredError


PAGE_TIMEOUT_SECONDS = 45
DOWNLOAD_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class PlaceDocumentRequest:
    """Enlace de PLACE que una sesión de navegador puede activar de forma segura."""

    document_url: str
    referer: str
    href: str = ""
    logical_name: str = ""
    visible_text: str = ""


@dataclass(frozen=True)
class RenderedDocument:
    """Contenido observado por el navegador, aún sin publicar en destino final."""

    content: bytes
    source_url: str
    final_url: str = ""
    filename: str = ""
    content_type: str = ""
    content_disposition: str = ""
    http_status: int = 0
    redirect_count: int = 0


@dataclass(frozen=True)
class RenderedPage:
    """Estado mínimo de la ficha una vez renderizada en el navegador."""

    final_url: str
    html: bytes = b""


class PlaceChallengeResolver(Protocol):
    """Contrato inyectable para no iniciar Chrome durante las pruebas."""

    def resolve(self, request: PlaceDocumentRequest) -> RenderedDocument: ...

    def close(self) -> None: ...


class CDP:
    """Cliente CDP pequeño, limitado al navegador local que abre este módulo."""

    def __init__(self, websocket_url: str):
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover - depende de la instalación local
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: falta websocket-client para usar el navegador."
            ) from exc
        self._websocket = websocket
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.next_id = 1
        self._events: list[dict] = []

    def close(self) -> None:
        try:
            self.ws.close()
        except (OSError, self._websocket.WebSocketException):
            return

    def call(self, method: str, params: dict | None = None, timeout: int = 30) -> dict:
        message_id = self.next_id
        self.next_id += 1
        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") != message_id:
                # Eventos CDP ajenos a esta llamada no forman parte de este contrato.
                self._events.append(response)
                continue
            if "error" in response:
                raise PlaceBrowserError(f"PLACE_BROWSER_DOWNLOAD_FAILED: {response['error']}")
            return response.get("result", {})

    def drain_events(self) -> list[dict]:
        """Recoge eventos CDP pendientes sin leer cookies ni datos de sesión."""

        events = self._events
        self._events = []
        previous_timeout = self.ws.gettimeout()
        try:
            self.ws.settimeout(0.01)
            while True:
                events.append(json.loads(self.ws.recv()))
        except (OSError, self._websocket.WebSocketException, ValueError):
            return events
        finally:
            try:
                self.ws.settimeout(previous_timeout)
            except (OSError, self._websocket.WebSocketException):
                pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def find_browser() -> str:
    candidates = (
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )
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
    raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: Chrome no abrió el puerto de control local.")


def open_browser():
    """Abre Chrome/Edge normal fuera de pantalla con un perfil temporal aislado."""

    executable = find_browser()
    if not executable:
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: no se encontró Chrome ni Edge para PLACE."
        )
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="place_descargas_chrome_")
    command = [
        executable,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
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
    browser = None
    try:
        version = _wait_for_cdp(port)
        browser = CDP(version["webSocketDebuggerUrl"])
        return process, profile, browser, port
    except Exception:
        close_browser(process, profile, browser)
        raise


def create_page(browser: CDP, port: int, download_directory: Path | str) -> CDP:
    websocket_url = ""
    deadline = time.time() + 10
    while time.time() < deadline and not websocket_url:
        try:
            pages = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        except (requests.RequestException, ValueError) as exc:
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: no se pudo abrir una pestaña local de PLACE."
            ) from exc
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
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: no se pudo crear una pestaña para PLACE."
        )
    page = CDP(websocket_url)
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Network.enable")
    path = str(Path(download_directory).resolve())
    errors: list[Exception] = []
    for target, method in ((browser, "Browser.setDownloadBehavior"), (page, "Page.setDownloadBehavior")):
        try:
            target.call(method, {"behavior": "allow", "downloadPath": path})
        except Exception as exc:
            errors.append(exc)
    if len(errors) == 2:
        page.close()
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: Chrome no permitió configurar la carpeta temporal."
        ) from errors[-1]
    return page


def _evaluate(page: CDP, expression: str, *, timeout: int = 30, user_gesture: bool = False):
    result = page.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
            "userGesture": user_gesture,
        },
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise PlaceBrowserError(f"PLACE_BROWSER_DOWNLOAD_FAILED: {result['exceptionDetails']}")
    return result.get("result", {}).get("value")


def _page_state(page: CDP) -> dict[str, str]:
    state = _evaluate(
        page,
        "(() => ({"
        "ready:String(document.readyState || ''),"
        "url:String(location.href || ''),"
        "text:String(document.body ? document.body.innerText : '').slice(0, 65536)"
        "}))()",
        timeout=10,
    )
    return state if isinstance(state, dict) else {}


def open_profile(page: CDP, url: str) -> RenderedPage:
    """Navega únicamente a una ficha HTTPS de PLACE y espera al DOM estable."""

    target = canonicalizar_url_place(url)
    if not es_url_place_segura(target):
        raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: URL de ficha no autorizada.")
    profile_request_ids: set[str] = set()
    drain_events = getattr(page, "drain_events", None)
    if callable(drain_events):
        drain_events()
    page.call("Page.navigate", {"url": target}, timeout=15)
    deadline = time.time() + PAGE_TIMEOUT_SECONDS
    interaction_detected = False
    while time.time() < deadline:
        _new_document_navigation_is_safe(
            page,
            expected_url=target,
            request_ids=profile_request_ids,
        )
        state = _page_state(page)
        final_url = canonicalizar_url_place(str(state.get("url") or ""))
        if not final_url or final_url == "about:blank":
            time.sleep(0.25)
            continue
        if not es_url_place_segura(final_url):
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: PLACE redirigió la ficha a una URL no autorizada."
            )
        visible_text = str(state.get("text") or "")
        if requiere_interaccion_place(visible_text):
            # Un reto JS ordinario puede reemplazarse de forma asíncrona. Solo
            # se declara interacción requerida cuando persiste todo el plazo.
            interaction_detected = True
        elif str(state.get("ready") or "").casefold() == "complete":
            return RenderedPage(final_url=final_url)
        time.sleep(0.25)
    if interaction_detected:
        raise PlaceBrowserInteractionRequiredError(
            "PLACE_BROWSER_INTERACTION_REQUIRED: PLACE exige una validación manual en el navegador."
        )
    raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: la ficha de PLACE no terminó de cargar.")


def _files(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir() if path.is_file()}


def _new_document_navigation_is_safe(page, *, expected_url="", request_ids=None) -> None:
    drain_events = getattr(page, "drain_events", None)
    if not callable(drain_events):
        return
    expected = canonicalizar_url_place(expected_url)
    tracked = request_ids if request_ids is not None else set()
    for event in drain_events():
        if event.get("method") not in {"Network.requestWillBeSent", "Network.responseReceived"}:
            continue
        params = event.get("params") or {}
        if str(params.get("type") or "") != "Document":
            continue
        request_id = str(params.get("requestId") or "")
        if event.get("method") == "Network.requestWillBeSent":
            url = str((params.get("request") or {}).get("url") or "")
            redirect_url = str((params.get("redirectResponse") or {}).get("url") or "")
            normalized_url = canonicalizar_url_place(url)
            if expected and normalized_url == expected:
                if not es_url_place_segura(url):
                    raise PlaceBrowserError(
                        "PLACE_BROWSER_DOWNLOAD_FAILED: la descarga intentó navegar a una URL no autorizada."
                    )
                tracked.add(request_id)
                continue
            follows_target = request_id in tracked or (
                expected and canonicalizar_url_place(redirect_url) == expected
            )
        else:
            url = str((params.get("response") or {}).get("url") or "")
            follows_target = request_id in tracked
        if follows_target and url and not es_url_place_segura(canonicalizar_url_place(url)):
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: la descarga intentó navegar a una URL no autorizada."
            )


def _wait_for_download(
    directory: Path,
    before: set[str],
    timeout: int,
    *,
    page=None,
    expected_url="",
    request_ids=None,
) -> Path | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page is not None:
            _new_document_navigation_is_safe(
                page,
                expected_url=expected_url,
                request_ids=request_ids,
            )
        current = _files(directory) - before
        incomplete = {
            name
            for name in current
            if name.casefold().endswith((".crdownload", ".tmp", ".partial"))
        }
        completed = sorted(
            name for name in current - incomplete if name.casefold() not in {"downloads.htm"}
        )
        if completed:
            candidate = directory / completed[-1]
            try:
                if candidate.stat().st_size > 0:
                    return candidate
            except OSError:
                pass
        time.sleep(0.25)
    return None


def _click_document_link(page: CDP, document_url: str) -> str:
    target = json.dumps(document_url)
    result = _evaluate(
        page,
        "(() => {"
        f"const wanted = new URL({target}, document.baseURI).href;"
        "const link = Array.from(document.querySelectorAll('a[href]')).find((item) => {"
        "  try {"
        "    const candidate = new URL(item.href, document.baseURI);"
        "    if (candidate.protocol === 'http:' && (candidate.hostname === 'contrataciondelestado.es' || candidate.hostname.endsWith('.contrataciondelestado.es'))) candidate.protocol = 'https:';"
        "    return candidate.href === wanted;"
        "  }"
        "  catch (_error) { return false; }"
        "});"
        "if (!link) return 'missing';"
        "link.scrollIntoView({block: 'center', inline: 'nearest'});"
        # La comparación ya normaliza un href HTTP de PLACE a HTTPS. Hay que
        # navegar con esa misma URL normalizada, no con el atributo original.
        "link.href = wanted;"
        "if (!link.hasAttribute('download')) link.setAttribute('download', '');"
        "link.target = '_self';"
        "link.click();"
        "return 'clicked';"
        "})()",
        timeout=15,
        user_gesture=True,
    )
    return str(result or "")


def download_link(page: CDP, absolute_href: str, download_directory: Path | str) -> RenderedDocument:
    """Activa un enlace presente en la ficha ya abierta y lee su temporal."""

    target = canonicalizar_url_place(absolute_href)
    if not es_url_place_segura(target):
        raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: URL documental no autorizada.")
    directory = Path(download_directory)
    before = _files(directory)
    request_ids: set[str] = set()
    drain_events = getattr(page, "drain_events", None)
    if callable(drain_events):
        drain_events()
    click_deadline = time.time() + PAGE_TIMEOUT_SECONDS
    clicked = False
    interaction_detected = False
    while time.time() < click_deadline:
        state = _page_state(page)
        current_url = canonicalizar_url_place(str(state.get("url") or ""))
        if current_url and current_url != "about:blank" and not es_url_place_segura(current_url):
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: la ficha redirigió la descarga a una URL no autorizada."
            )
        if requiere_interaccion_place(str(state.get("text") or "")):
            interaction_detected = True
            time.sleep(0.25)
            continue
        if _click_document_link(page, target) == "clicked":
            clicked = True
            break
        time.sleep(0.25)
    if not clicked:
        if interaction_detected:
            raise PlaceBrowserInteractionRequiredError(
                "PLACE_BROWSER_INTERACTION_REQUIRED: PLACE exige una validación manual para descargar."
            )
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: el enlace oficial no aparece en la ficha renderizada."
        )
    temporary = _wait_for_download(
        directory,
        before,
        DOWNLOAD_TIMEOUT_SECONDS,
        page=page,
        expected_url=target,
        request_ids=request_ids,
    )
    if temporary is None:
        if requiere_interaccion_place(str(_page_state(page).get("text") or "")):
            raise PlaceBrowserInteractionRequiredError(
                "PLACE_BROWSER_INTERACTION_REQUIRED: PLACE exige una validación manual para descargar."
            )
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: Chrome no publicó el documento dentro del tiempo esperado."
        )
    _new_document_navigation_is_safe(page, expected_url=target, request_ids=request_ids)
    current_url = canonicalizar_url_place(str(_page_state(page).get("url") or ""))
    if current_url and current_url != "about:blank" and not es_url_place_segura(current_url):
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: PLACE redirigió la descarga a una URL no autorizada."
        )
    try:
        content = temporary.read_bytes()
    except OSError as exc:
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: no se pudo leer la descarga temporal de PLACE."
        ) from exc
    if not content:
        raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: PLACE descargó un archivo vacío.")
    return RenderedDocument(
        content=content,
        source_url=target,
        final_url=target,
        filename=temporary.name,
    )


def close_browser(process, profile: str, browser: CDP | None = None, page: CDP | None = None) -> None:
    """Cierra solo los recursos temporales creados por este fallback."""

    for client in (page, browser):
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    if process is not None:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
    if profile:
        for _attempt in range(3):
            shutil.rmtree(profile, ignore_errors=True)
            if not os.path.exists(profile):
                break
            time.sleep(0.25)


class ChromePlaceChallengeResolver:
    """Mantiene una sola sesión de navegador para los retos de una licitación."""

    def __init__(self, browser_api=None):
        self._browser_api = browser_api
        self._process = None
        self._profile = ""
        self._browser = None
        self._page = None
        self._downloads: tempfile.TemporaryDirectory[str] | None = None
        self._current_referer = ""
        self._terminal_error: Exception | None = None

    def _call(self, name: str, *args):
        target = getattr(self._browser_api, name) if self._browser_api is not None else globals()[name]
        return target(*args)

    def _start(self) -> None:
        self._downloads = tempfile.TemporaryDirectory(prefix="llangon-place-browser-")
        try:
            self._process, self._profile, self._browser, port = self._call("open_browser")
            self._page = self._call("create_page", self._browser, port, self._downloads.name)
        except Exception:
            self.close()
            raise

    def resolve(self, request: PlaceDocumentRequest) -> RenderedDocument:
        if self._terminal_error is not None:
            raise self._terminal_error
        referer = canonicalizar_url_place(request.referer)
        document_url = canonicalizar_url_place(request.document_url)
        if not es_url_place_segura(referer) or not es_url_place_segura(document_url):
            raise PlaceBrowserError("PLACE_BROWSER_DOWNLOAD_FAILED: URL de PLACE no autorizada.")
        if self._page is None:
            try:
                self._start()
            except Exception as exc:
                self._terminal_error = exc
                raise
        if self._current_referer != referer:
            try:
                rendered = self._call("open_profile", self._page, referer)
            except Exception as exc:
                self._terminal_error = exc
                raise
            final_referer = canonicalizar_url_place(str(getattr(rendered, "final_url", "") or referer))
            if not es_url_place_segura(final_referer):
                error = PlaceBrowserError(
                    "PLACE_BROWSER_DOWNLOAD_FAILED: la ficha renderizada no pertenece a PLACE."
                )
                self._terminal_error = error
                raise error
            self._current_referer = referer
        try:
            rendered_document = self._call("download_link", self._page, document_url, self._downloads.name)
        except PlaceBrowserInteractionRequiredError as exc:
            self._terminal_error = exc
            raise
        if not isinstance(rendered_document, RenderedDocument):
            raise PlaceBrowserError(
                "PLACE_BROWSER_DOWNLOAD_FAILED: el navegador devolvió un resultado documental inválido."
            )
        return rendered_document

    def close(self) -> None:
        try:
            if self._process is not None or self._profile:
                self._call("close_browser", self._process, self._profile, self._browser, self._page)
        finally:
            self._process = None
            self._profile = ""
            self._browser = None
            self._page = None
            self._current_referer = ""
            if self._downloads is not None:
                self._downloads.cleanup()
                self._downloads = None


def create_challenge_resolver() -> ChromePlaceChallengeResolver:
    """Fábrica perezosa: no abre Chrome hasta el primer reto documental real."""

    return ChromePlaceChallengeResolver()
