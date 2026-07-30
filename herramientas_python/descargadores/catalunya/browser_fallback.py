"""Respaldo documental mediante Chrome/Edge y el protocolo CDP."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urljoin

import requests
import websocket

from .client import TIMEOUT_CARGA_PAGINA
from .documents import es_enlace_documento, fecha_desde_texto, normalizar


JS_EXTRAER_ENLACES = r"""
(() => {
  const texto = (el) => ((el && (el.innerText || el.textContent)) || "")
    .replace(/\s+/g, " ").trim();
  const esDocumento = (href) => /\/portal-api\/descarrega-document(?:-antic)?\//i.test(href || "");
  const resultado = [];
  const vistos = new Set();
  const agregar = (el, rawHref) => {
    const href = rawHref.startsWith("http") ? rawHref : new URL(rawHref, location.href).href;
    if (!esDocumento(href) || vistos.has(href.toLowerCase())) return;
    vistos.add(href.toLowerCase());
    const cercano = el.closest("li,tr,[class*='document'],mat-list-item,mat-card,section") || el.parentElement;
    const linkText = texto(el) || el.getAttribute("title") || el.getAttribute("aria-label") || "";
    resultado.push({
      index: resultado.length,
      href,
      text: linkText,
      title: el.getAttribute("title") || el.getAttribute("aria-label") || "",
      download: el.getAttribute("download") || "",
      itemText: texto(cercano) || linkText,
      section: "Documentacio"
    });
  };
  for (const el of Array.from(document.querySelectorAll("a[href]"))) {
    agregar(el, el.href || el.getAttribute("href") || "");
  }
  for (const el of Array.from(document.querySelectorAll("button,[role='button'],[onclick],[data-url]"))) {
    const matches = (el.outerHTML || "").match(/(?:https?:\/\/[^"'\s<>]+)?\/portal-api\/descarrega-document(?:-antic)?\/[^"'\s<>]+/gi) || [];
    for (const href of matches) agregar(el, href);
  }
  return {ok: true, count: resultado.length, title: document.title || "", text: texto(document.body), links: resultado};
})()
"""


class CDP:
    def __init__(self, websocket_url):
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.next_id = 1

    def close(self):
        try:
            self.ws.close()
        except (OSError, websocket.WebSocketException) as exc:
            print(f"Aviso al cerrar el canal CDP: {type(exc).__name__}.", flush=True)

    def call(self, method, params=None, timeout=30):
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


def puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def encontrar_chrome() -> str:
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((candidate for candidate in candidates if candidate and os.path.exists(candidate)), "")


def esperar_cdp(port: int, timeout: int = 15):
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=0.5)
            if response.status_code == 200:
                return response.json()
        except (requests.RequestException, ValueError):
            time.sleep(0.2)
    raise RuntimeError("Chrome no ha abierto el puerto de control.")


def abrir_chrome():
    chrome = encontrar_chrome()
    if not chrome:
        raise RuntimeError("No se ha encontrado Chrome ni Edge en el equipo.")
    port = puerto_libre()
    profile = tempfile.mkdtemp(prefix="catalunya_descargas_chrome_")
    command = [
        chrome,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
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
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    version = esperar_cdp(port)
    browser = CDP(version["webSocketDebuggerUrl"])
    return process, profile, browser, port


def crear_pagina(browser, port: int):
    websocket_url = ""
    create_target_error = None
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
            try:
                browser.call("Target.createTarget", {"url": "about:blank"}, timeout=5)
            except Exception as exc:
                create_target_error = exc
            time.sleep(0.2)
    if not websocket_url:
        raise RuntimeError("No se ha podido abrir una pestaña de Chrome.") from create_target_error
    page = CDP(websocket_url)
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Network.enable")
    return page


def evaluar(page, expresion, timeout=30):
    result = page.call(
        "Runtime.evaluate",
        {"expression": expresion, "returnByValue": True, "awaitPromise": True},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    return result.get("result", {}).get("value")


def esperar_documentos(page, *, log=print):
    started = time.time()
    last_notice = 0
    while time.time() - started < TIMEOUT_CARGA_PAGINA:
        data = evaluar(page, JS_EXTRAER_ENLACES, timeout=10) or {}
        if data.get("links"):
            return data
        text = evaluar(page, "document.body ? document.body.innerText : ''", timeout=10) or ""
        normalized = normalizar(text)
        if "el vostre navegador no suporta javascript" not in normalized and (
            "documentacio" in normalized or "plec" in normalized
        ):
            data = evaluar(page, JS_EXTRAER_ENLACES, timeout=10) or {}
            if data.get("links"):
                return data
        elapsed = int(time.time() - started)
        if elapsed - last_notice >= 5:
            last_notice = elapsed
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
        except Exception as kill_exc:
            print(
                f"Aviso: no se pudo cerrar el navegador auxiliar ({type(kill_exc).__name__}).",
                flush=True,
            )
    shutil.rmtree(perfil_temporal, ignore_errors=True)


def extraer_documentos_renderizados(url: str, *, log=print) -> list[dict]:
    process = profile = browser = page = None
    try:
        process, profile, browser, port = abrir_chrome()
        page = crear_pagina(browser, port)
        page.call("Page.navigate", {"url": url}, timeout=10)
        data = esperar_documentos(page, log=log)
        documents: list[dict] = []
        seen: set[str] = set()
        for link in data.get("links") or []:
            href = urljoin(url, link.get("href", ""))
            if not es_enlace_documento(href) or href.lower() in seen:
                continue
            seen.add(href.lower())
            normalized = dict(link)
            normalized["href"] = href
            normalized["fecha"] = fecha_desde_texto(normalized.get("itemText", ""))
            documents.append(normalized)
        return documents
    finally:
        if process and profile:
            cerrar_chrome(process, profile, browser, page)
