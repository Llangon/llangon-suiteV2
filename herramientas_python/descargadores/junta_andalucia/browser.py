"""Navegación CDP y operaciones documentales específicas de Junta de Andalucía."""

import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

import requests
import websocket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..common.safe_files import write_bytes_if_absent
from . import documents as document_ops


# Por defecto se descargan solo los documentos principales del bloque.
# Si tambien quieres descargar los enlaces "Descarga sello de tiempo...",
# ejecuta el script con el parametro: --incluir-sellos
INCLUIR_SELLOS_TIEMPO = False

TIMEOUT_CARGA_PAGINA = 60
TIMEOUT_DESCARGA = (5, 90)
INTENTOS_LIMPIEZA_PERFIL = 8
RUTA_DETALLE_ACTUAL = (
    "/haciendayadministracionpublica/apl/pdc-front-publico/"
    "perfiles-licitaciones/detalle-licitacion"
)
ERRORES_NAVEGACION_TRANSITORIOS = {
    "ERR_ABORTED",
    "ERR_CONNECTION_ABORTED",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_EMPTY_RESPONSE",
    "ERR_HTTP2_PROTOCOL_ERROR",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_NETWORK_CHANGED",
    "ERR_QUIC_PROTOCOL_ERROR",
    "ERR_TEMPORARILY_THROTTLED",
    "ERR_TIMED_OUT",
}

EXTENSIONES_VALIDAS = {
    ".pdf", ".xml", ".html", ".htm", ".txt",
    ".xls", ".xlsx", ".xlsm",
    ".doc", ".docx",
    ".ppt", ".pptx",
    ".zip", ".rtf",
    ".csv", ".ods", ".odt",
}

MIME_A_EXTENSION = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/rtf": ".rtf",
    "text/rtf": ".rtf",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/xml": ".xml",
    "application/xml": ".xml",
}


class JuntaBrowserError(RuntimeError):
    """Fallo clasificado del navegador auxiliar de la Junta."""

    error_code = "JUNTA_BROWSER_ERROR"
    retryable = False


class JuntaTransientBrowserError(JuntaBrowserError):
    """Fallo temporal para el que merece la pena abrir un Chrome nuevo."""

    retryable = True


class JuntaNavigationTransientError(JuntaTransientBrowserError):
    error_code = "JUNTA_NAVIGATION_TRANSIENT"


class JuntaEmptyRenderError(JuntaTransientBrowserError):
    error_code = "JUNTA_EMPTY_RENDER"


class JuntaDocumentSectionsTimeout(JuntaTransientBrowserError):
    error_code = "JUNTA_DOCUMENT_SECTIONS_TIMEOUT"


def error_metadata(exc):
    """Devuelve código estable y reintentabilidad sin depender del texto en el Monitor."""

    error_code = str(getattr(exc, "error_code", "") or "JUNTA_DOWNLOAD_FAILED")
    retryable = bool(getattr(exc, "retryable", False))
    if isinstance(exc, (TimeoutError, ConnectionError)):
        retryable = True
    return error_code, retryable

JS_EXTRAER_ENLACES = r"""
(() => {
  const incluirSellos = __INCLUIR_SELLOS__;

  const norm = (s) => (s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

  const esTitulo = (el) => /^H[1-6]$/.test(el.tagName || "");
  const texto = (el) => ((el && (el.innerText || el.textContent)) || "")
    .replace(/\s+/g, " ")
    .trim();

  const candidatosTitulo = Array.from(document.body.querySelectorAll(
    "h1,h2,h3,h4,h5,h6,legend,strong,b,span,div,p"
  ));

  const todos = Array.from(document.body.querySelectorAll("*"));

  const bloques = [
    {
      clave: "documentacion",
      titulo: "documentacion complementaria",
      error: "No se ha encontrado el bloque Documentacion complementaria."
    },
    {
      clave: "anuncios",
      titulo: "anuncios publicados",
      error: "No se ha encontrado el bloque Anuncios publicados."
    }
  ];

  const enlacesDeBloque = (bloque) => {
    const titulo = candidatosTitulo.find((el) => norm(texto(el)) === bloque.titulo);
    if (!titulo) return [];

    const indiceTitulo = todos.indexOf(titulo);
    const nivelTitulo = esTitulo(titulo) ? Number(titulo.tagName.substring(1)) : 3;
    let indiceFin = todos.length;

    for (let i = indiceTitulo + 1; i < todos.length; i++) {
      const el = todos[i];
      if (!esTitulo(el)) continue;

      const t = norm(texto(el));
      if (!t || t === bloque.titulo) continue;

      const nivel = Number(el.tagName.substring(1));
      if (nivel <= nivelTitulo) {
        indiceFin = i;
        break;
      }
    }

    let enlaces = Array.from(document.body.querySelectorAll("a")).filter((a) => {
      const i = todos.indexOf(a);
      return i > indiceTitulo && i < indiceFin;
    });

    if (enlaces.length === 0) {
      const nodos = [];
      let n = titulo.nextElementSibling;
      for (let i = 0; n && i < 12; i++, n = n.nextElementSibling) {
        nodos.push(n);
        if (n.querySelector && n.querySelector("a")) break;
      }
      enlaces = nodos.flatMap((nodo) => Array.from(nodo.querySelectorAll("a")));
    }

    return enlaces.map((a) => ({ a, bloque }));
  };

  const resultado = [];
  const vistos = new Set();

  const enlaces = bloques.flatMap((bloque) => enlacesDeBloque(bloque));

  for (const item of enlaces) {
    const a = item.a;
    const bloque = item.bloque;
    const linkText = texto(a) || a.getAttribute("title") || a.getAttribute("download") || "";
    const href = a.href || a.getAttribute("href") || "";
    const itemText = texto(a.closest("li")) || texto(a.closest("tr")) || texto(a.parentElement) || linkText;
    const normalizadoLink = norm(linkText + " " + (a.getAttribute("title") || ""));
    const normalizadoItem = norm(itemText + " " + linkText + " " + href);

    if (!linkText && !href) continue;
    if (!incluirSellos && normalizadoLink.includes("sello de tiempo")) continue;
    if (bloque.clave === "anuncios") {
      if (!normalizadoItem.includes("documento anuncio pdf")) continue;
      if (normalizadoItem.includes("documento descriptivo") || normalizadoItem.includes("xml")) continue;
    }

    const clave = (bloque.clave + "|" + href + "|" + linkText).toLowerCase();
    if (vistos.has(clave)) continue;
    vistos.add(clave);

    a.setAttribute("data-codex-junta-doc", String(resultado.length));
    resultado.push({
      index: resultado.length,
      text: linkText,
      href,
      title: a.getAttribute("title") || "",
      download: a.getAttribute("download") || "",
      itemText,
      section: bloque.clave
    });
  }

  return {
    ok: true,
    heading: "Documentacion complementaria / Anuncios publicados",
    count: resultado.length,
    links: resultado
  };
})()
"""


def log(mensaje=""):
    print(mensaje, flush=True)


def normalizar(texto):
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return re.sub(r"\s+", " ", texto).lower().strip()


def normalizar_url_licitacion(url):
    parsed = urlparse(str(url or "").strip())
    expediente = (parse_qs(parsed.query).get("idExpediente") or [""])[0].strip()
    if not expediente or "juntadeandalucia.es" not in parsed.netloc.lower():
        return str(url or "").strip()
    return urlunparse(
        (
            "https",
            parsed.netloc,
            RUTA_DETALLE_ACTUAL,
            "",
            urlencode({"idExpediente": expediente}),
            "",
        )
    )


def limpiar_nombre(nombre):
    return document_ops.limpiar_nombre(nombre)


def acortar_nombre(nombre, max_base=150):
    return document_ops.acortar_nombre(nombre, max_base)


def extension_desde_nombre(nombre):
    return document_ops.extension_desde_nombre(nombre)


def nombre_desde_content_disposition(valor):
    return document_ops.nombre_desde_content_disposition(valor)


def extension_desde_contenido(contenido):
    return document_ops.extension_desde_contenido(contenido)


def extension_desde_content_type(content_type):
    return document_ops.extension_desde_content_type(content_type)


def detectar_extension(respuesta, nombre_logico="", archivo_url=""):
    return document_ops.detectar_extension(respuesta, nombre_logico, archivo_url)


def construir_nombre_archivo(respuesta, nombre_logico, archivo_url, ext):
    return document_ops.construir_nombre_archivo(respuesta, nombre_logico, archivo_url, ext)


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    return document_ops.ruta_si_no_existe(carpeta_destino, nombre_archivo)


def nombre_previsto_desde_enlace(enlace):
    return document_ops.nombre_previsto_desde_enlace(enlace)


def nombre_logico_desde_enlace(enlace):
    return document_ops.nombre_logico_desde_enlace(enlace)


class CDP:
    def __init__(self, websocket_url):
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.next_id = 1

    def close(self):
        try:
            self.ws.close()
        except (OSError, websocket.WebSocketException) as exc:
            log(f"Aviso al cerrar el canal CDP: {type(exc).__name__}.")

    def call(self, method, params=None, timeout=30):
        msg_id = self.next_id
        self.next_id += 1

        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": method,
            "params": params or {},
        }))

        while True:
            respuesta = json.loads(self.ws.recv())
            if respuesta.get("id") != msg_id:
                continue
            if "error" in respuesta:
                raise RuntimeError(respuesta["error"])
            return respuesta.get("result", {})


def puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def encontrar_chrome():
    candidatos = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]

    for candidato in candidatos:
        if candidato and os.path.exists(candidato):
            return candidato

    return ""


def esperar_cdp(port, timeout=15):
    url = f"http://127.0.0.1:{port}/json/version"
    fin = time.time() + timeout

    while time.time() < fin:
        try:
            respuesta = requests.get(url, timeout=0.5)
            if respuesta.status_code == 200:
                return respuesta.json()
        except (requests.RequestException, ValueError):
            time.sleep(0.2)

    raise RuntimeError("Chrome no ha abierto el puerto de control.")


def terminar_proceso_chrome(proceso):
    if not proceso:
        return
    try:
        proceso.terminate()
        proceso.wait(timeout=5)
        return
    except Exception:
        pass
    try:
        proceso.kill()
        proceso.wait(timeout=5)
    except Exception as exc:
        log(f"Aviso: no se pudo cerrar el navegador auxiliar ({type(exc).__name__}).")


def eliminar_perfil_temporal(perfil_temporal, *, attempts=INTENTOS_LIMPIEZA_PERFIL):
    if not perfil_temporal:
        return True
    last_error = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            shutil.rmtree(perfil_temporal)
            return True
        except FileNotFoundError:
            return True
        except OSError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.5)
    log(f"Aviso: no se pudo eliminar el perfil temporal de Chrome ({last_error}).")
    return False


def abrir_chrome():
    chrome = encontrar_chrome()
    if not chrome:
        raise RuntimeError("No se ha encontrado Chrome ni Edge en el equipo.")

    port = puerto_libre()
    perfil_temporal = tempfile.mkdtemp(prefix="junta_descargas_chrome_")

    comando = [
        chrome,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={perfil_temporal}",
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,2200",
        "about:blank",
    ]

    proceso = None
    try:
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        version = esperar_cdp(port)
        browser = CDP(version["webSocketDebuggerUrl"])
        return proceso, perfil_temporal, browser, port
    except BaseException:
        terminar_proceso_chrome(proceso)
        eliminar_perfil_temporal(perfil_temporal)
        raise


def crear_pagina(browser, port, carpeta_descarga):
    websocket_url = ""
    create_target_error = None

    fin = time.time() + 10
    while time.time() < fin and not websocket_url:
        lista = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
        for item in lista:
            if item.get("type") == "page" and item.get("webSocketDebuggerUrl"):
                websocket_url = item.get("webSocketDebuggerUrl", "")
                break

        if not websocket_url:
            try:
                browser.call("Target.createTarget", {"url": "about:blank"}, timeout=5)
            except Exception as exc:
                create_target_error = exc
            time.sleep(0.2)

    if not websocket_url:
        raise RuntimeError("No se ha podido abrir una pestana de Chrome.") from create_target_error

    page = CDP(websocket_url)
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Network.enable")

    download_errors = []
    try:
        browser.call("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": carpeta_descarga,
        })
    except Exception as exc:
        download_errors.append(exc)

    try:
        page.call("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": carpeta_descarga,
        })
    except Exception as exc:
        download_errors.append(exc)

    if len(download_errors) == 2:
        raise RuntimeError("Chrome no ha permitido configurar la carpeta de descargas.") from download_errors[-1]

    return page


def evaluar(page, expresion, timeout=30):
    resultado = page.call("Runtime.evaluate", {
        "expression": expresion,
        "returnByValue": True,
        "awaitPromise": True,
    }, timeout=timeout)

    if "exceptionDetails" in resultado:
        raise RuntimeError(resultado["exceptionDetails"])

    return resultado.get("result", {}).get("value")


def diagnosticar_pagina(page):
    estado = evaluar(
        page,
        r"""
(() => {
  const body = document.body;
  const text = body ? (body.innerText || "") : "";
  const normalized = text.normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
  const root = document.querySelector("app-root");
  return {
    url: location.href || "",
    title: document.title || "",
    readyState: document.readyState || "",
    bodyLength: text.length,
    bodySample: text.replace(/\s+/g, " ").trim().slice(0, 300),
    appRootLength: root ? root.innerHTML.length : 0,
    links: body ? body.querySelectorAll("a").length : 0,
    sectionsReady: normalized.includes("documentacion complementaria")
      || normalized.includes("anuncios publicados")
  };
})()
""",
        timeout=10,
    )
    return estado if isinstance(estado, dict) else {}


def navegar_a_licitacion(page, url):
    resultado = page.call("Page.navigate", {"url": url}, timeout=25)
    error = str(resultado.get("errorText") or "").strip()
    if error:
        error_type = (
            JuntaNavigationTransientError
            if any(token in error.upper() for token in ERRORES_NAVEGACION_TRANSITORIOS)
            else JuntaBrowserError
        )
        raise error_type(f"Chrome no pudo abrir la licitación: {error}")
    return resultado


def preparar_reintento_navegacion(page):
    try:
        page.call("Network.clearBrowserCache", timeout=10)
    except Exception:
        pass
    try:
        page.call("Page.navigate", {"url": "about:blank"}, timeout=10)
    except Exception:
        pass


def esperar_documentacion_complementaria(
    page,
    *,
    logger=log,
    timeout=TIMEOUT_CARGA_PAGINA,
    empty_page_timeout=25,
):
    inicio = time.time()
    ultimo_aviso = 0
    ultimo_estado = {}

    while time.time() - inicio < timeout:
        ultimo_estado = diagnosticar_pagina(page)
        if ultimo_estado.get("sectionsReady"):
            return ultimo_estado

        transcurrido = int(time.time() - inicio)
        if (
            transcurrido >= empty_page_timeout
            and ultimo_estado.get("readyState") in {"interactive", "complete"}
            and not ultimo_estado.get("bodyLength")
            and not ultimo_estado.get("appRootLength")
        ):
            raise JuntaEmptyRenderError(
                "La aplicación de la Junta no llegó a renderizar contenido "
                f"(URL final: {ultimo_estado.get('url') or '(desconocida)'})."
            )
        if transcurrido - ultimo_aviso >= 5:
            ultimo_aviso = transcurrido
            logger("Esperando a que carguen las secciones documentales...")

        time.sleep(0.5)

    detalle = (
        f"URL final: {ultimo_estado.get('url') or '(desconocida)'}; "
        f"estado: {ultimo_estado.get('readyState') or '(desconocido)'}; "
        f"texto: {ultimo_estado.get('bodySample') or '(vacío)'}"
    )
    raise JuntaDocumentSectionsTimeout(
        f"No han aparecido las secciones documentales esperadas. {detalle}"
    )


def extraer_enlaces(page, incluir_sellos):
    js = JS_EXTRAER_ENLACES.replace("__INCLUIR_SELLOS__", "true" if incluir_sellos else "false")
    datos = evaluar(page, js, timeout=20)

    if not datos or not datos.get("ok"):
        error = datos.get("error") if isinstance(datos, dict) else "Error desconocido."
        raise RuntimeError(error)

    return datos.get("links", [])


def crear_session_descarga(page, referer):
    session = requests.Session()
    retry_policy = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry_policy, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        cookies = page.call("Network.getAllCookies", timeout=10).get("cookies", [])
        for cookie in cookies:
            session.cookies.set(
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path") or "/",
            )
    except Exception as exc:
        log(f"Aviso: no se pudieron copiar las cookies de navegación ({type(exc).__name__}).")

    try:
        user_agent = evaluar(page, "navigator.userAgent", timeout=5)
    except Exception as exc:
        log(f"Aviso: no se pudo leer el User-Agent del navegador ({type(exc).__name__}).")
        user_agent = ""

    session.headers.update({
        "User-Agent": user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Referer": referer,
        "Accept": "application/pdf,application/octet-stream,*/*",
    })

    return session


def href_descargable(href):
    return document_ops.href_descargable(href)


def descargar_por_url(session, enlace, carpeta_destino, referer):
    return document_ops.descargar_por_url(session, enlace, carpeta_destino, referer)


def archivos_actuales(carpeta):
    return document_ops.archivos_actuales(carpeta)


def esperar_descarga_chrome(carpeta, antes, timeout=45):
    return document_ops.esperar_descarga_chrome(carpeta, antes, timeout)


def descargar_por_click(page, enlace, carpeta_destino):
    return document_ops.descargar_por_click(page, enlace, carpeta_destino)


def cerrar_chrome(proceso, perfil_temporal, browser=None, page=None):
    if page:
        try:
            page.close()
        except Exception as exc:
            log(f"Aviso al cerrar la página CDP: {type(exc).__name__}.")
    if browser:
        try:
            browser.close()
        except Exception as exc:
            log(f"Aviso al cerrar el navegador CDP: {type(exc).__name__}.")

    terminar_proceso_chrome(proceso)
    eliminar_perfil_temporal(perfil_temporal)
