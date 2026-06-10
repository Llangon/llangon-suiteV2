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
from urllib.parse import unquote, urlparse

import requests
import websocket


# Por defecto se descargan solo los documentos principales del bloque.
# Si tambien quieres descargar los enlaces "Descarga sello de tiempo...",
# ejecuta el script con el parametro: --incluir-sellos
INCLUIR_SELLOS_TIEMPO = False

TIMEOUT_CARGA_PAGINA = 60
TIMEOUT_DESCARGA = (5, 90)

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


def limpiar_nombre(nombre):
    nombre = unquote(str(nombre or ""))
    nombre = re.sub(r"\s*descarga\s+sello\s+de\s+tiempo.*$", "", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"^\s*descarga\s+documento\s+anuncio\s+pdf\s*", "", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"\(\s*activo\s*\)\s*\.?\s*$", "", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"\s*\(\.[A-Za-z0-9]{2,5}\)\s*$", "", nombre)
    nombre = re.sub(r"^\s*\([^)]+\)\s*", "", nombre)
    nombre = re.sub(r'[\\/*?:"<>|\n\r\t]+', "_", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip(" .")
    return nombre or "documento"


def acortar_nombre(nombre, max_base=150):
    base, ext = os.path.splitext(nombre)
    if len(base) > max_base:
        base = base[:max_base].rstrip(" .")
    return base + ext


def extension_desde_nombre(nombre):
    nombre = unquote(str(nombre or "")).split("?")[0].split("#")[0].strip()
    ext = os.path.splitext(nombre)[1].lower()
    return ext if ext in EXTENSIONES_VALIDAS else ""


def nombre_desde_content_disposition(valor):
    if not valor:
        return ""

    msg = Message()
    msg["content-disposition"] = valor
    filename = msg.get_filename()
    if filename:
        return limpiar_nombre(filename)

    match = re.search(r"filename\*=UTF-8''([^;]+)", valor, re.IGNORECASE)
    if match:
        return limpiar_nombre(match.group(1))

    match = re.search(r'filename="?([^";]+)"?', valor, re.IGNORECASE)
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


def nombre_previsto_desde_enlace(enlace):
    nombre_logico = nombre_logico_desde_enlace(enlace)
    nombre = limpiar_nombre(nombre_logico)

    if extension_desde_nombre(nombre):
        return acortar_nombre(nombre)

    if enlace.get("section") == "anuncios":
        return acortar_nombre(nombre + ".pdf")

    ext = extension_desde_nombre(urlparse(enlace.get("href", "")).path)
    if ext:
        return acortar_nombre(nombre + ext)

    return ""


def nombre_logico_desde_enlace(enlace):
    if enlace.get("section") == "anuncios":
        return enlace.get("itemText") or enlace.get("text") or enlace.get("title") or "anuncio"

    return enlace.get("download") or enlace.get("text") or enlace.get("title") or "documento"


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

    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    version = esperar_cdp(port)
    browser = CDP(version["webSocketDebuggerUrl"])
    return proceso, perfil_temporal, browser, port


def crear_pagina(browser, port, carpeta_descarga):
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

    try:
        browser.call("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": carpeta_descarga,
        })
    except Exception:
        pass

    try:
        page.call("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": carpeta_descarga,
        })
    except Exception:
        pass

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


def esperar_documentacion_complementaria(page):
    objetivos = {"documentacion complementaria", "anuncios publicados"}
    inicio = time.time()
    ultimo_aviso = 0

    while time.time() - inicio < TIMEOUT_CARGA_PAGINA:
        texto = evaluar(page, "document.body ? document.body.innerText : ''", timeout=10) or ""
        texto_normalizado = normalizar(texto)

        if any(objetivo in texto_normalizado for objetivo in objetivos):
            return

        transcurrido = int(time.time() - inicio)
        if transcurrido - ultimo_aviso >= 5:
            ultimo_aviso = transcurrido
            log("Esperando a que carguen las secciones documentales...")

        time.sleep(0.5)

    raise RuntimeError("No han aparecido las secciones documentales esperadas.")


def extraer_enlaces(page, incluir_sellos):
    js = JS_EXTRAER_ENLACES.replace("__INCLUIR_SELLOS__", "true" if incluir_sellos else "false")
    datos = evaluar(page, js, timeout=20)

    if not datos or not datos.get("ok"):
        error = datos.get("error") if isinstance(datos, dict) else "Error desconocido."
        raise RuntimeError(error)

    return datos.get("links", [])


def crear_session_descarga(page, referer):
    session = requests.Session()

    try:
        cookies = page.call("Network.getAllCookies", timeout=10).get("cookies", [])
        for cookie in cookies:
            session.cookies.set(
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path") or "/",
            )
    except Exception:
        pass

    try:
        user_agent = evaluar(page, "navigator.userAgent", timeout=5)
    except Exception:
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
    if not href:
        return False

    esquema = urlparse(href).scheme.lower()
    if esquema not in {"http", "https"}:
        return False

    if href.lower().startswith("javascript:"):
        return False

    return True


def descargar_por_url(session, enlace, carpeta_destino, referer):
    href = enlace.get("href", "")
    nombre_logico = nombre_logico_desde_enlace(enlace)

    respuesta = session.get(
        href,
        timeout=TIMEOUT_DESCARGA,
        allow_redirects=True,
        headers={"Referer": referer},
    )
    respuesta.raise_for_status()

    ext = detectar_extension(respuesta, nombre_logico, href)
    nombre_archivo = construir_nombre_archivo(respuesta, nombre_logico, href, ext)
    ruta_archivo, nombre_archivo = ruta_si_no_existe(carpeta_destino, nombre_archivo)

    if ruta_archivo is None:
        return nombre_archivo, True

    with open(ruta_archivo, "wb") as f:
        f.write(respuesta.content)

    return nombre_archivo, False


def archivos_actuales(carpeta):
    return {
        p.name
        for p in Path(carpeta).iterdir()
        if p.is_file()
    }


def esperar_descarga_chrome(carpeta, antes, timeout=45):
    fin = time.time() + timeout

    while time.time() < fin:
        despues = archivos_actuales(carpeta)
        nuevos = despues - antes
        incompletos = [n for n in nuevos if n.endswith(".crdownload") or n.endswith(".tmp")]
        completos = [n for n in nuevos if n not in incompletos]

        if completos and not incompletos:
            return completos[0]

        time.sleep(0.5)

    return ""


def descargar_por_click(page, enlace, carpeta_destino):
    nombre_previsto = nombre_previsto_desde_enlace(enlace)
    if nombre_previsto and os.path.exists(os.path.join(carpeta_destino, nombre_previsto)):
        return nombre_previsto, True

    antes = archivos_actuales(carpeta_destino)
    indice = int(enlace["index"])

    evaluar(
        page,
        f"""
        (() => {{
          const a = document.querySelector('[data-codex-junta-doc="{indice}"]');
          if (!a) return false;
          a.click();
          return true;
        }})()
        """,
        timeout=10,
    )

    nombre_descargado = esperar_descarga_chrome(carpeta_destino, antes)
    return nombre_descargado, False


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

    try:
        shutil.rmtree(perfil_temporal, ignore_errors=True)
    except Exception:
        pass


def parsear_argumentos():
    incluir_sellos = INCLUIR_SELLOS_TIEMPO
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))
    urls = []
    args = sys.argv[1:]
    i = 0

    while i < len(args):
        arg = args[i]
        if arg == "--incluir-sellos":
            incluir_sellos = True
        elif arg == "--sin-sellos":
            incluir_sellos = False
        elif arg == "--destino":
            if i + 1 >= len(args):
                log("Uso: python Descargar_JuntaAndalucia.py <URL> [--incluir-sellos] [--destino <CARPETA>]")
                sys.exit(1)
            carpeta_destino = os.path.abspath(args[i + 1])
            i += 1
        else:
            urls.append(arg)
        i += 1

    if len(urls) != 1:
        log("Uso: python Descargar_JuntaAndalucia.py <URL> [--incluir-sellos] [--destino <CARPETA>]")
        sys.exit(1)

    os.makedirs(carpeta_destino, exist_ok=True)
    return urls[0], incluir_sellos, carpeta_destino


def main():
    url, incluir_sellos, carpeta_destino = parsear_argumentos()

    log("Abriendo Chrome en segundo plano...")
    proceso = None
    perfil_temporal = None
    browser = None
    page = None

    try:
        proceso, perfil_temporal, browser, port = abrir_chrome()
        page = crear_pagina(browser, port, carpeta_destino)

        log("Cargando licitacion...")
        page.call("Page.navigate", {"url": url}, timeout=10)
        esperar_documentacion_complementaria(page)

        log("Localizando enlaces de Documentacion complementaria y Anuncios publicados...")
        enlaces = extraer_enlaces(page, incluir_sellos)

        if not enlaces:
            log("No se han encontrado enlaces dentro de Documentacion complementaria ni Anuncios publicados.")
            sys.exit(1)

        if incluir_sellos:
            log(f"Enlaces encontrados: {len(enlaces)}")
        else:
            log(f"Documentos encontrados: {len(enlaces)} (sellos de tiempo excluidos)")

        session = crear_session_descarga(page, url)
        descargados = 0
        omitidos = 0

        for i, enlace in enumerate(enlaces, 1):
            texto = limpiar_nombre(enlace.get("text") or enlace.get("title") or f"documento_{i}")
            log(f"\n[{i}/{len(enlaces)}] {texto}")

            try:
                if href_descargable(enlace.get("href", "")):
                    nombre, omitido = descargar_por_url(session, enlace, carpeta_destino, url)
                else:
                    nombre, omitido = descargar_por_click(page, enlace, carpeta_destino)

                if omitido:
                    omitidos += 1
                    log(f"Omitido, ya existe: {nombre}")
                elif nombre:
                    descargados += 1
                    log(f"Guardado como: {nombre}")
                else:
                    log("No se pudo confirmar la descarga de este enlace.")

            except Exception as e:
                log(f"Error descargando este enlace: {e}")

        log(f"\nDescarga terminada: {descargados} documento(s) descargado(s), {omitidos} omitido(s).")

    except Exception as e:
        log(f"Error: {e}")
        sys.exit(1)

    finally:
        if proceso and perfil_temporal:
            cerrar_chrome(proceso, perfil_temporal, browser, page)


if __name__ == "__main__":
    main()
