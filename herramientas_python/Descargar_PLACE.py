import io
import os
import re
import sys
import zipfile
from email.message import Message
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


EXTENSIONES_VALIDAS = {
    ".pdf", ".xml", ".html", ".htm", ".txt",
    ".xls", ".xlsx", ".xlsm",
    ".doc", ".docx",
    ".ppt", ".pptx",
    ".zip", ".rtf",
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
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/rtf": ".rtf",
    "text/rtf": ".rtf",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "text/plain": ".txt",
    "text/xml": ".xml",
    "application/xml": ".xml",
}


def limpiar_nombre(nombre):
    nombre = unquote(str(nombre or ""))
    nombre = re.sub(r'[\\/*?:"<>|\n\r\t]+', "_", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip(" .")
    return nombre or "documento"


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
    if "pdf" in ct:
        return ".pdf"
    if "html" in ct:
        return ".html"
    if ct.endswith("/xml") or ct in {"text/xml", "application/xml"}:
        return ".xml"

    return ""


def detectar_extension(respuesta, texto_visible="", nombre_logico="", archivo_url=""):
    return (
        extension_desde_contenido(respuesta.content)
        or extension_desde_content_type(respuesta.headers.get("Content-Type", ""))
        or extension_desde_nombre(nombre_desde_content_disposition(respuesta.headers.get("Content-Disposition", "")))
        or extension_desde_nombre(texto_visible)
        or extension_desde_nombre(nombre_logico)
        or extension_desde_nombre(urlparse(archivo_url).path)
        or ".bin"
    )


def construir_nombre_archivo(respuesta, nombre_logico, texto_visible, archivo_url, ext):
    nombre_cabecera = nombre_desde_content_disposition(respuesta.headers.get("Content-Disposition", ""))
    candidato = nombre_cabecera or nombre_logico or texto_visible or os.path.basename(urlparse(archivo_url).path)
    candidato = limpiar_nombre(candidato)

    base, ext_actual = os.path.splitext(candidato)
    ext_actual = ext_actual.lower()
    ext_base = os.path.splitext(base)[1].lower()

    if ext_actual in EXTENSIONES_VALIDAS:
        if ext_actual == ext or ext in ("", ".bin"):
            return candidato
        if ext_base == ext:
            return base
        if ext_base in EXTENSIONES_VALIDAS:
            return limpiar_nombre(os.path.splitext(base)[0]) + ext
        return limpiar_nombre(base) + ext

    return candidato + ext


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    ruta = os.path.join(carpeta_destino, nombre_archivo)
    if os.path.exists(ruta):
        return None, nombre_archivo

    return ruta, nombre_archivo


def descargar_documento(session, url_base, href, nombre_logico, texto_visible, carpeta_destino, urls_descargadas):
    archivo_url = urljoin(url_base, href)

    if archivo_url in urls_descargadas:
        return None

    try:
        print(f"Descargando: {archivo_url}")
        respuesta = session.get(archivo_url, timeout=60, headers={"Referer": url_base})
        respuesta.raise_for_status()

        ext = detectar_extension(respuesta, texto_visible, nombre_logico, archivo_url)
        nombre_archivo = construir_nombre_archivo(respuesta, nombre_logico, texto_visible, archivo_url, ext)
        ruta_archivo, nombre_archivo = ruta_si_no_existe(carpeta_destino, nombre_archivo)

        if ruta_archivo is None:
            urls_descargadas.add(archivo_url)
            print(f"Omitido, ya existe: {nombre_archivo}")
            return None

        with open(ruta_archivo, "wb") as f:
            f.write(respuesta.content)

        urls_descargadas.add(archivo_url)

        if ext in {".html", ".htm", ".xml"}:
            print(f"Guardado como: {nombre_archivo} (se revisara por si contiene adjuntos)")
        else:
            print(f"Guardado como: {nombre_archivo}")

        return nombre_archivo

    except Exception as e:
        print(f"Error descargando {archivo_url}: {e}")
        return None


def es_enlace_documento(href):
    return "GetDocumentByIdServlet" in href or "DocumentIdParam=" in href


def nombre_desde_tabla(enlace, estamos_en_otros_documentos):
    if estamos_en_otros_documentos:
        span = enlace.find_previous("span", class_="outputText")
        if span and span.get_text(strip=True):
            return limpiar_nombre(span.get_text(" ", strip=True))

    td_actual = enlace.find_parent("td")
    if td_actual:
        td_anterior = td_actual.find_previous_sibling("td")
        if td_anterior:
            div = td_anterior.find("div")
            if div and div.get_text(strip=True):
                return limpiar_nombre(div.get_text(" ", strip=True))

            texto = td_anterior.get_text(" ", strip=True)
            if texto:
                return limpiar_nombre(texto)

    return ""


def base_desde_soup(soup, url_base):
    base_tag = soup.find("base", href=True)
    if base_tag:
        return urljoin(url_base, base_tag["href"])
    return url_base


def procesar_html(session, soup, url_base, carpeta_destino, urls_descargadas):
    archivos_descargados = []
    estamos_en_otros_documentos = False
    url_base_real = base_desde_soup(soup, url_base)

    for tag in soup.find_all(True):
        if tag.has_attr("title") and "Otros Documentos" in tag["title"]:
            estamos_en_otros_documentos = True

        if tag.name != "a" or not tag.has_attr("href"):
            continue

        href = tag["href"]
        if not es_enlace_documento(href):
            continue

        texto_visible = tag.get_text(" ", strip=True)
        nombre_logico = (
            nombre_desde_tabla(tag, estamos_en_otros_documentos)
            or limpiar_nombre(texto_visible)
            or f"documento_{len(archivos_descargados) + 1}"
        )

        nombre_archivo = descargar_documento(
            session,
            url_base_real,
            href,
            nombre_logico,
            texto_visible,
            carpeta_destino,
            urls_descargadas,
        )

        if nombre_archivo:
            archivos_descargados.append(nombre_archivo)

    return archivos_descargados


def procesar_html_pliego(session, soup, url_base, carpeta_destino, urls_descargadas):
    archivos_descargados = []
    url_base_real = base_desde_soup(soup, url_base)

    for enlace in soup.find_all("a", href=True):
        href = enlace["href"]
        if not es_enlace_documento(href):
            continue

        texto_visible = enlace.get_text(" ", strip=True)
        nombre_logico = limpiar_nombre(texto_visible) or f"documento_pliego_{len(archivos_descargados) + 1}"

        nombre_archivo = descargar_documento(
            session,
            url_base_real,
            href,
            nombre_logico,
            texto_visible,
            carpeta_destino,
            urls_descargadas,
        )

        if nombre_archivo:
            archivos_descargados.append(nombre_archivo)

    return archivos_descargados


def candidatos_para_segunda_fase(carpeta_destino, archivos_primera_fase):
    candidatos = []

    for nombre in archivos_primera_fase:
        ext = os.path.splitext(nombre)[1].lower()
        if ext in {".html", ".htm", ".xml"}:
            candidatos.append(nombre)

    for nombre in os.listdir(carpeta_destino):
        nombre_lower = nombre.lower()
        ext = os.path.splitext(nombre_lower)[1]
        if "pliego" in nombre_lower and ext in {".html", ".htm", ".xml"}:
            candidatos.append(nombre)

    resultado = []
    vistos = set()
    for nombre in candidatos:
        ruta = os.path.join(carpeta_destino, nombre)
        clave = os.path.abspath(ruta).lower()
        if clave not in vistos and os.path.isfile(ruta):
            vistos.add(clave)
            resultado.append(nombre)

    return resultado


def procesar_pliegos_descargados(session, url_base, carpeta_destino, archivos_primera_fase, urls_descargadas):
    candidatos = candidatos_para_segunda_fase(carpeta_destino, archivos_primera_fase)
    total_adjuntos = 0

    for archivo in candidatos:
        ruta = os.path.join(carpeta_destino, archivo)
        print(f"\nAnalizando adjuntos en: {archivo}")

        try:
            with open(ruta, "rb") as f:
                contenido = f.read()

            soup = BeautifulSoup(contenido, "html.parser")
            adjuntos = procesar_html_pliego(session, soup, url_base, carpeta_destino, urls_descargadas)
            total_adjuntos += len(adjuntos)
            print(f"Adjuntos encontrados en {archivo}: {len(adjuntos)}")

        except Exception as e:
            print(f"Error procesando {archivo}: {e}")

    if candidatos:
        print(f"\nSegunda fase: {total_adjuntos} adjunto(s) descargado(s) desde documentos HTML/XML.")
    else:
        print("\nSegunda fase: no se encontraron documentos Pliego/HTML para analizar.")


def crear_session(url_referer):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Referer": url_referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session


def parsear_argumentos():
    args = sys.argv[1:]
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))

    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            print("Uso: python Descargar_PLACE.py <URL> [--destino <CARPETA>]")
            sys.exit(1)
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]

    if len(args) != 1:
        print("Uso: python Descargar_PLACE.py <URL> [--destino <CARPETA>]")
        sys.exit(1)

    os.makedirs(carpeta_destino, exist_ok=True)
    return args[0], carpeta_destino


def main():
    url, carpeta_destino = parsear_argumentos()
    session = crear_session(url)
    urls_descargadas = set()

    try:
        respuesta = session.get(url, timeout=60)
        respuesta.raise_for_status()
    except Exception as e:
        print(f"Error accediendo a la URL: {e}")
        sys.exit(1)

    soup = BeautifulSoup(respuesta.text, "html.parser")
    archivos_primera_fase = procesar_html(session, soup, url, carpeta_destino, urls_descargadas)

    if archivos_primera_fase:
        print(f"\nPrimera fase: {len(archivos_primera_fase)} archivo(s) descargado(s).")
    else:
        print("No se encontraron documentos en la primera fase.")

    procesar_pliegos_descargados(
        session,
        url,
        carpeta_destino,
        archivos_primera_fase,
        urls_descargadas,
    )


if __name__ == "__main__":
    main()
