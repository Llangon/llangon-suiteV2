import io
import os
import re
import sys
import zipfile
from email.message import Message
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


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


def log(mensaje=""):
    print(mensaje, flush=True)


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


def extraer_expediente(soup):
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return limpiar_nombre(h1.get_text(" ", strip=True))

    textos = [t.strip() for t in soup.stripped_strings if t.strip()]
    for i, texto in enumerate(textos[:-1]):
        if texto.lower() == "expediente":
            return limpiar_nombre(textos[i + 1])

    return ""


def extraer_ficha_pdf(soup, url_base, expediente):
    for enlace in soup.find_all("a", href=True):
        href = urljoin(url_base, enlace["href"])
        if "fichaExpediente.pdf" in href:
            nombre = f"Ficha expediente {expediente}.pdf" if expediente else "Ficha expediente.pdf"
            return {"url": href, "nombre_logico": nombre}

    return None


def endpoint_descarga(funcion, id_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/downloadDokusiREST"
    if funcion == "descargarFicheroContrato":
        return (
            f"{base}/descargaFicheroContratoPorIdFichero"
            f"?idFichero={id_fichero}&R01HNoPortal=true"
        )

    return (
        f"{base}/descargaFicheroPorIdFichero"
        f"?idFichero={id_fichero}&R01HNoPortal=true"
    )


def endpoint_comprobacion(funcion, id_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/downloadDokusiREST"
    if funcion == "descargarFicheroContrato":
        return f"{base}/comprobarFicheroContratoPorIdFichero?idFichero={id_fichero}"

    return f"{base}/comprobarFicheroPorIdFichero?idFichero={id_fichero}"


def extraer_documentos(soup):
    documentos = []
    vistos = set()
    patron = re.compile(r"(descargarFicheroContrato|descargarFichero)\(\s*['\"]?(\d+)['\"]?\s*\)")

    for enlace in soup.find_all("a"):
        onclick = enlace.get("onclick", "")
        match = patron.search(onclick)
        if not match:
            continue

        funcion, id_fichero = match.groups()
        clave = (funcion, id_fichero)
        if clave in vistos:
            continue
        vistos.add(clave)

        nombre_logico = limpiar_nombre(enlace.get_text(" ", strip=True)) or f"fichero_{id_fichero}"
        documentos.append({
            "url": endpoint_descarga(funcion, id_fichero),
            "check_url": endpoint_comprobacion(funcion, id_fichero),
            "nombre_logico": nombre_logico,
        })

    return documentos


def comprobar_disponible(session, documento, referer):
    check_url = documento.get("check_url")
    if not check_url:
        return True

    respuesta = session.get(check_url, timeout=TIMEOUT_DESCARGA, headers={"Referer": referer})
    respuesta.raise_for_status()
    texto = respuesta.text.strip().lower()
    return texto in {"true", "1", "ok", ""}


def descargar_documento(session, documento, carpeta_destino, referer):
    url = documento["url"]
    nombre_logico = documento["nombre_logico"]
    log(f"Descargando: {url}")

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
        log(f"Omitido, ya existe: {nombre_archivo}")
        return "omitido", nombre_archivo

    with open(ruta_archivo, "wb") as f:
        f.write(respuesta.content)

    log(f"Guardado como: {nombre_archivo}")
    return "descargado", nombre_archivo


def parsear_argumentos():
    args = sys.argv[1:]
    carpeta_destino = os.path.dirname(os.path.abspath(__file__))

    if "--destino" in args:
        idx = args.index("--destino")
        if idx + 1 >= len(args):
            log("Uso: python Descargar_Euskadi.py <URL> [--destino <CARPETA>]")
            sys.exit(1)
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]

    if len(args) != 1:
        log("Uso: python Descargar_Euskadi.py <URL> [--destino <CARPETA>]")
        sys.exit(1)

    os.makedirs(carpeta_destino, exist_ok=True)
    return args[0], carpeta_destino


def main():
    url, carpeta_destino = parsear_argumentos()
    session = crear_session()

    try:
        log(f"Accediendo a Euskadi: {url}")
        respuesta = session.get(url, timeout=TIMEOUT_DESCARGA, allow_redirects=True)
        respuesta.raise_for_status()
    except Exception as e:
        log(f"Error accediendo a la URL: {e}")
        sys.exit(1)

    soup = BeautifulSoup(respuesta.text, "html.parser")
    expediente = extraer_expediente(soup)
    trabajos = []

    ficha = extraer_ficha_pdf(soup, respuesta.url, expediente)
    if ficha:
        trabajos.append(ficha)

    trabajos.extend(extraer_documentos(soup))

    if not trabajos:
        log("No se han encontrado documentos para descargar.")
        sys.exit(1)

    log(f"Documentos encontrados: {len(trabajos)}")

    descargados = 0
    omitidos = 0
    errores = 0

    for i, trabajo in enumerate(trabajos, 1):
        log(f"\n[{i}/{len(trabajos)}] {trabajo['nombre_logico']}")
        try:
            estado, _ = descargar_documento(session, trabajo, carpeta_destino, respuesta.url)
            if estado == "descargado":
                descargados += 1
            elif estado == "omitido":
                omitidos += 1
        except Exception as e:
            errores += 1
            log(f"Error descargando este enlace: {e}")

    log(
        f"\nDescarga terminada: {descargados} documento(s) descargado(s), "
        f"{omitidos} omitido(s), {errores} error(es)."
    )

    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
