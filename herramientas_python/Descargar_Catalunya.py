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
import unicodedata
import zipfile
from email.message import Message
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

import requests
import websocket
from bs4 import BeautifulSoup


TIMEOUT_CARGA_PAGINA = 60
TIMEOUT_DESCARGA = (5, 90)
DOMINIO_CATALUNYA = "contractaciopublica.cat"

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

JS_EXTRAER_ENLACES = r"""
(() => {
  const texto = (el) => ((el && (el.innerText || el.textContent)) || "")
    .replace(/\s+/g, " ")
    .trim();

  const norm = (s) => (s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

  const esTitulo = (el) => /^H[1-6]$/.test(el.tagName || "");
  const esDocumento = (href) => /\/portal-api\/descarrega-document(?:-antic)?\//i.test(href || "");

  const tituloAnterior = (el) => {
    let actual = el;
    for (let i = 0; actual && i < 80; i++) {
      actual = actual.previousElementSibling || actual.parentElement;
      if (!actual) break;
      if (esTitulo(actual)) {
        const t = texto(actual);
        if (t) return t;
      }
      const dentro = actual.querySelector && actual.querySelector("h1,h2,h3,h4,h5,h6,legend");
      if (dentro) {
        const t = texto(dentro);
        if (t) return t;
      }
    }
    return "";
  };

  const bloqueCercano = (el) => {
    const candidatos = [
      el.closest("li"),
      el.closest("tr"),
      el.closest("[class*='document']"),
      el.closest("[class*='Document']"),
      el.closest("mat-list-item"),
      el.closest("mat-card"),
      el.closest("section"),
      el.parentElement
    ];
    for (const candidato of candidatos) {
      const t = texto(candidato);
      if (t && t.length <= 700) return t;
    }
    return texto(el);
  };

  const resultado = [];
  const vistos = new Set();

  for (const a of Array.from(document.querySelectorAll("a[href]"))) {
    const href = a.href || a.getAttribute("href") || "";
    if (!esDocumento(href)) continue;
    const linkText = texto(a) || a.getAttribute("title") || a.getAttribute("download") || "";
    const itemText = bloqueCercano(a);
    const clave = href.toLowerCase();
    if (vistos.has(clave)) continue;
    vistos.add(clave);
    resultado.push({
      index: resultado.length,
      href,
      text: linkText,
      title: a.getAttribute("title") || "",
      download: a.getAttribute("download") || "",
      itemText,
      section: tituloAnterior(a) || "Documentacio"
    });
  }

  for (const el of Array.from(document.querySelectorAll("button,[role='button'],[onclick],[ng-reflect-router-link],[data-url]"))) {
    const html = el.outerHTML || "";
    const matches = html.match(/(?:https?:\/\/[^"'\s<>]+)?\/portal-api\/descarrega-document(?:-antic)?\/[^"'\s<>]+/gi) || [];
    for (const rawHref of matches) {
      const href = rawHref.startsWith("http") ? rawHref : new URL(rawHref, location.href).href;
      if (!esDocumento(href)) continue;
      const linkText = texto(el) || el.getAttribute("title") || el.getAttribute("aria-label") || "";
      const itemText = bloqueCercano(el);
      const clave = href.toLowerCase();
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      resultado.push({
        index: resultado.length,
        href,
        text: linkText,
        title: el.getAttribute("title") || el.getAttribute("aria-label") || "",
        download: "",
        itemText,
        section: tituloAnterior(el) || "Documentacio"
      });
    }
  }

  return {
    ok: true,
    count: resultado.length,
    title: document.title || "",
    text: texto(document.body),
    links: resultado
  };
})()
"""


def log(mensaje=""):
    print(mensaje, flush=True)


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).lower().strip()


def limpiar_nombre(nombre):
    nombre = unquote(unescape(str(nombre or "")))
    nombre = re.sub(r'[\\/*?:"<>|\n\r\t]+', "_", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip(" .")
    return nombre or "documento"


def acortar_nombre(nombre, max_base=150):
    base, ext = os.path.splitext(nombre)
    if len(base) > max_base:
        base = base[:max_base].rstrip(" .")
    return base + ext


def limpiar_titulo_documento(texto):
    texto = unescape(str(texto or ""))
    texto = re.sub(r"\b(Descarregar|Descargar|Download)\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b(PDF|XML|HTML?|DOCX?|XLSX?|ZIP|RTF|CSV|ODS|ODT)\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|bytes?)\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .:-")
    return limpiar_nombre(texto)


def es_texto_generico(texto):
    n = normalizar(texto)
    if not n:
        return True
    if n in {
        "descarregar", "descargar", "download", "pdf", "xml", "documentacio",
        "documentacion", "fitxer", "archivo", "document", "documents",
    }:
        return True
    return False


def extension_desde_nombre(nombre):
    nombre = unquote(str(nombre or "")).split("?")[0].split("#")[0].strip()
    ext = os.path.splitext(nombre)[1].lower()
    return ext if ext in EXTENSIONES_VALIDAS else ""


def extension_desde_texto(texto):
    n = normalizar(texto)
    for ext in EXTENSIONES_VALIDAS:
        if ext.strip(".") in re.split(r"[^a-z0-9]+", n):
            return ext
    return ""


def nombre_desde_content_disposition(valor):
    if not valor:
        return ""

    msg = Message()
    msg["content-disposition"] = valor
    filename = msg.get_filename()
    if filename:
        return limpiar_nombre(filename)

    for patron in [
        r"filename\*=UTF-8''([^;\r\n]+)",
        r'filename="?([^";\r\n]+)"?',
        r'name="?([^";\r\n]+)"?',
    ]:
        match = re.search(patron, valor, re.IGNORECASE)
        if match:
            return limpiar_nombre(match.group(1))

    return ""


def extension_desde_contenido(contenido):
    inicio = contenido[:4096]
    if inicio.startswith(b"\xef\xbb\xbf"):
        inicio = inicio[3:]
    inicio = inicio.lstrip()
    inicio_lower = inicio[:512].lower()

    if contenido.startswith(b"%PDF"):
        return ".pdf"

    if contenido.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                nombres = z.namelist()
                if "xl/vbaProject.bin" in nombres:
                    return ".xlsm"
                if any(n.startswith("xl/") for n in nombres):
                    return ".xlsx"
                if any(n.startswith("word/") for n in nombres):
                    return ".docx"
                if any(n.startswith("ppt/") for n in nombres):
                    return ".pptx"
        except zipfile.BadZipFile:
            pass
        return ".zip"

    if inicio_lower.startswith(b"<!doctype html") or b"<html" in inicio_lower:
        return ".html"

    if inicio_lower.startswith(b"<?xml") or inicio_lower.startswith(b"<"):
        return ".xml"

    if inicio_lower.startswith(b"{\\rtf"):
        return ".rtf"

    return ""


def extension_desde_content_type(content_type):
    ct = (content_type or "").split(";")[0].strip().lower()

    if ct in MIME_A_EXTENSION:
        return MIME_A_EXTENSION[ct]

    if "spreadsheetml" in ct:
        return ".xlsx"
    if "wordprocessingml" in ct:
        return ".docx"
    if "presentationml" in ct:
        return ".pptx"
    if "ms-excel" in ct or "excel" in ct:
        return ".xls"
    if "msword" in ct:
        return ".doc"
    if "opendocument.spreadsheet" in ct:
        return ".ods"
    if "opendocument.text" in ct:
        return ".odt"
    if "pdf" in ct:
        return ".pdf"
    if "html" in ct:
        return ".html"
    if "csv" in ct:
        return ".csv"
    if ct.endswith("/xml") or ct in {"text/xml", "application/xml"}:
        return ".xml"

    return ""


def detectar_extension(respuesta, nombre_logico="", archivo_url=""):
    nombre_cabecera = nombre_desde_content_disposition(respuesta.headers.get("Content-Disposition", ""))
    return (
        extension_desde_contenido(respuesta.content)
        or extension_desde_content_type(respuesta.headers.get("Content-Type", ""))
        or extension_desde_nombre(nombre_cabecera)
        or extension_desde_nombre(nombre_logico)
        or extension_desde_nombre(urlparse(archivo_url).path)
        or ".bin"
    )


def construir_nombre_archivo(respuesta, nombre_logico, archivo_url, ext):
    nombre_cabecera = nombre_desde_content_disposition(respuesta.headers.get("Content-Disposition", ""))
    candidato = nombre_logico or nombre_cabecera or os.path.basename(urlparse(archivo_url).path)
    candidato = limpiar_nombre(candidato)

    base, ext_actual = os.path.splitext(candidato)
    ext_actual = ext_actual.lower()
    ext_base = os.path.splitext(base)[1].lower()

    if ext_actual in EXTENSIONES_VALIDAS:
        if ext_actual == ext or ext in ("", ".bin"):
            return acortar_nombre(candidato)
        if ext_base == ext:
            return acortar_nombre(base)
        if ext_base in EXTENSIONES_VALIDAS:
            return acortar_nombre(limpiar_nombre(os.path.splitext(base)[0]) + ext)
        return acortar_nombre(limpiar_nombre(base) + ext)

    return acortar_nombre(candidato + ext)


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    ruta = os.path.join(carpeta_destino, nombre_archivo)
    if os.path.exists(ruta):
        return None, nombre_archivo
    return ruta, nombre_archivo


def crear_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session


def es_url_catalunya(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host == DOMINIO_CATALUNYA


def es_enlace_documento(url):
    path = urlparse(url).path.lower()
    return es_url_catalunya(url) and (
        "/portal-api/descarrega-document/" in path
        or "/portal-api/descarrega-document-antic/" in path
    )


def fecha_desde_texto(texto):
    match = re.search(
        r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?)?",
        str(texto or ""),
    )
    if not match:
        return ""
    dia = int(match.group(1))
    mes = int(match.group(2))
    anio = int(match.group(3))
    if anio < 100:
        anio += 2000
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        return ""
    if match.group(4) and match.group(5):
        return f"{anio:04d}-{mes:02d}-{dia:02d}T{int(match.group(4)):02d}:{int(match.group(5)):02d}:00"
    return f"{anio:04d}-{mes:02d}-{dia:02d}"


def nombre_logico_desde_enlace(enlace, indice):
    for clave in ("download", "text", "title"):
        valor = enlace.get(clave, "")
        if valor and not es_texto_generico(valor):
            return limpiar_titulo_documento(valor)

    item_text = enlace.get("itemText", "")
    if item_text:
        candidatos = []
        for parte in re.split(r"\s{2,}|[:|]", item_text):
            candidato = limpiar_titulo_documento(parte)
            if candidato and not es_texto_generico(candidato):
                candidatos.append(candidato)
        if candidatos:
            return max(candidatos, key=len)

    nombre_url = os.path.basename(urlparse(enlace.get("href", "")).path)
    if nombre_url and not es_texto_generico(nombre_url):
        return limpiar_titulo_documento(nombre_url)

    return f"documento_{indice}"


def extraer_documentos_de_html(html, url_base):
    soup = BeautifulSoup(html, "html.parser")
    documentos = []
    vistos = set()

    def agregar(href, link_text="", title="", download="", item_text="", section="Documentacio"):
        href_abs = urljoin(url_base, href)
        if not es_enlace_documento(href_abs):
            return
        clave = href_abs.lower()
        if clave in vistos:
            return
        vistos.add(clave)
        documentos.append({
            "href": href_abs,
            "text": link_text,
            "title": title,
            "download": download,
            "itemText": item_text or link_text,
            "section": section,
            "fecha": fecha_desde_texto(item_text or link_text),
        })

    for enlace in soup.find_all("a", href=True):
        href = urljoin(url_base, enlace["href"])
        link_text = enlace.get_text(" ", strip=True)
        padre = enlace.find_parent(["li", "tr", "div", "section", "article"])
        item_text = padre.get_text(" ", strip=True) if padre else link_text
        agregar(href, link_text, enlace.get("title", ""), enlace.get("download", ""), item_text)

    patron_url = re.compile(r'(?:https?://[^"\'\s<>]+)?/portal-api/descarrega-document(?:-antic)?/[^"\'\s<>]+', re.IGNORECASE)
    for tag in soup.find_all(True):
        attr_text = " ".join(
            " ".join(map(str, value)) if isinstance(value, list) else str(value)
            for value in tag.attrs.values()
        )
        if "descarrega-document" not in attr_text:
            continue
        for href in patron_url.findall(attr_text):
            link_text = tag.get_text(" ", strip=True) or tag.get("title", "") or tag.get("aria-label", "")
            padre = tag.find_parent(["li", "tr", "div", "section", "article"])
            item_text = padre.get_text(" ", strip=True) if padre else link_text
            if len(item_text) > 350:
                item_text = link_text
            agregar(href, link_text, tag.get("title", "") or tag.get("aria-label", ""), "", item_text)

    return documentos


class CDP:
    def __init__(self, websocket_url):
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.next_id = 1

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

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
        except Exception:
            time.sleep(0.2)

    raise RuntimeError("Chrome no ha abierto el puerto de control.")


def abrir_chrome():
    chrome = encontrar_chrome()
    if not chrome:
        raise RuntimeError("No se ha encontrado Chrome ni Edge en el equipo.")

    port = puerto_libre()
    perfil_temporal = tempfile.mkdtemp(prefix="catalunya_descargas_chrome_")

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

    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    version = esperar_cdp(port)
    browser = CDP(version["webSocketDebuggerUrl"])
    return proceso, perfil_temporal, browser, port


def crear_pagina(browser, port):
    websocket_url = ""
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
            except Exception:
                pass
            time.sleep(0.2)

    if not websocket_url:
        raise RuntimeError("No se ha podido abrir una pestana de Chrome.")

    page = CDP(websocket_url)
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Network.enable")
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


def esperar_documentos(page):
    inicio = time.time()
    ultimo_aviso = 0

    while time.time() - inicio < TIMEOUT_CARGA_PAGINA:
        datos = evaluar(page, JS_EXTRAER_ENLACES, timeout=10) or {}
        if datos.get("links"):
            return datos

        texto = evaluar(page, "document.body ? document.body.innerText : ''", timeout=10) or ""
        texto_normalizado = normalizar(texto)
        if "el vostre navegador no suporta javascript" not in texto_normalizado and (
            "documentacio" in texto_normalizado or "plec" in texto_normalizado
        ):
            datos = evaluar(page, JS_EXTRAER_ENLACES, timeout=10) or {}
            if datos.get("links"):
                return datos

        transcurrido = int(time.time() - inicio)
        if transcurrido - ultimo_aviso >= 5:
            ultimo_aviso = transcurrido
            log("Esperando a que cargue la documentacion...")

        time.sleep(0.5)

    return evaluar(page, JS_EXTRAER_ENLACES, timeout=10) or {"links": []}


def cerrar_chrome(proceso, perfil_temporal, browser=None, page=None):
    if page:
        page.close()
    if browser:
        browser.close()

    try:
        proceso.terminate()
        proceso.wait(timeout=5)
    except Exception:
        try:
            proceso.kill()
        except Exception:
            pass

    shutil.rmtree(perfil_temporal, ignore_errors=True)


def extraer_documentos_renderizados(url):
    proceso = None
    perfil_temporal = None
    browser = None
    page = None

    try:
        proceso, perfil_temporal, browser, port = abrir_chrome()
        page = crear_pagina(browser, port)
        page.call("Page.navigate", {"url": url}, timeout=10)
        datos = esperar_documentos(page)
        documentos = []
        vistos = set()
        for enlace in datos.get("links") or []:
            href = urljoin(url, enlace.get("href", ""))
            if not es_enlace_documento(href):
                continue
            clave = href.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            enlace["href"] = href
            enlace["fecha"] = fecha_desde_texto(enlace.get("itemText", ""))
            documentos.append(enlace)
        return documentos
    finally:
        if proceso and perfil_temporal:
            cerrar_chrome(proceso, perfil_temporal, browser, page)


def descargar_documento(session, url, nombre_logico, carpeta_destino, referer):
    respuesta = session.get(
        url,
        timeout=TIMEOUT_DESCARGA,
        allow_redirects=True,
        headers={"Referer": referer},
    )
    respuesta.raise_for_status()

    ext = detectar_extension(respuesta, nombre_logico, url)
    nombre_archivo = construir_nombre_archivo(respuesta, nombre_logico, url, ext)
    ruta_archivo, nombre_archivo = ruta_si_no_existe(carpeta_destino, nombre_archivo)

    if ruta_archivo is None:
        return "omitido", nombre_archivo

    with open(ruta_archivo, "wb") as f:
        f.write(respuesta.content)

    return "descargado", nombre_archivo


def parsear_argumentos():
    args = sys.argv[1:]
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))

    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            log("Uso: python Descargar_Catalunya.py <URL> [--destino <CARPETA>]")
            sys.exit(1)
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]

    if len(args) != 1:
        log("Uso: python Descargar_Catalunya.py <URL> [--destino <CARPETA>]")
        sys.exit(1)

    os.makedirs(carpeta_destino, exist_ok=True)
    return args[0], carpeta_destino


def main():
    url, carpeta_destino = parsear_argumentos()
    session = crear_session()

    documentos = []
    try:
        log(f"Accediendo a Contractacio Publica Catalunya: {url}")
        respuesta = session.get(url, timeout=TIMEOUT_DESCARGA)
        respuesta.raise_for_status()
        documentos = extraer_documentos_de_html(respuesta.text, url)
    except Exception:
        documentos = []

    if not documentos:
        log("La ficha necesita Javascript. Abriendo Chrome en segundo plano...")
        try:
            documentos = extraer_documentos_renderizados(url)
        except Exception as e:
            log(f"Error localizando documentos: {e}")
            sys.exit(1)

    if not documentos:
        log("No se han encontrado documentos para descargar.")
        sys.exit(1)

    trabajos = []
    for i, enlace in enumerate(documentos, 1):
        nombre_logico = nombre_logico_desde_enlace(enlace, i)
        if extension_desde_texto(enlace.get("itemText", "")) and not extension_desde_nombre(nombre_logico):
            nombre_logico += extension_desde_texto(enlace.get("itemText", ""))
        trabajos.append({
            "url": enlace["href"],
            "nombre_logico": nombre_logico,
        })

    log(f"Documentos encontrados: {len(trabajos)}")
    descargados = 0
    omitidos = 0
    errores = 0

    for i, trabajo in enumerate(trabajos, 1):
        log(f"\n[{i}/{len(trabajos)}] {trabajo['nombre_logico']}")
        try:
            estado, nombre = descargar_documento(
                session,
                trabajo["url"],
                trabajo["nombre_logico"],
                carpeta_destino,
                url,
            )
            if estado == "descargado":
                descargados += 1
                log(f"Guardado como: {nombre}")
            elif estado == "omitido":
                omitidos += 1
                log(f"Omitido, ya existe: {nombre}")
        except Exception as e:
            errores += 1
            log(f"Error descargando este enlace: {e}")

    log(f"\nDescarga terminada: {descargados} documento(s) descargado(s), {omitidos} omitido(s), {errores} error(es).")
    if descargados == 0 and omitidos == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
