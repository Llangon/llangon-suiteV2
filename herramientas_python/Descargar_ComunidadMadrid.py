import io
import os
import re
import sys
import unicodedata
import zipfile
from email.message import Message
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


TIMEOUT_DESCARGA = (5, 90)
DOMINIO_MADRID = "contratos-publicos.comunidad.madrid"

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
    texto = re.sub(r"\bDescargar\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bPDF\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|bytes?)\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\([^)]*Publicado el[^)]*\)", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bPublicado el\b.*$", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bFecha de\b.*$", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+", " ", texto).strip(" .:-")
    return limpiar_nombre(texto)


def es_texto_generico(texto):
    n = normalizar(texto)
    if not n:
        return True
    if n in {
        "descargar", "pdf", "email", "secciones", "datos del expediente",
        "anuncio", "suscribase a las alertas", "menu pcon", "menu pie pcon",
    }:
        return True
    if n.startswith("fecha de "):
        return True
    if re.fullmatch(r"\d+(?:[.,]\d+)?\s*(kb|mb|gb|bytes?)", n):
        return True
    return False


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


def es_url_interna(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host == DOMINIO_MADRID


def es_enlace_ficha_pdf(url):
    path = urlparse(url).path.lower()
    return "/contrato-publico/print/pdf/" in path


def es_enlace_adjunto(url):
    path = urlparse(url).path.lower()
    if es_enlace_ficha_pdf(url):
        return False
    if "/medias/" in path and "/download" in path:
        return True
    if path.endswith("/download") or "/download/" in path:
        return True
    if extension_desde_nombre(path):
        return True
    return False


def extraer_numero_expediente(soup):
    textos = [t.strip() for t in soup.stripped_strings if t.strip()]
    for i, texto in enumerate(textos[:-1]):
        n = normalizar(texto)
        if n in {"numero de expediente", "n de expediente", "n expediente", "expediente"}:
            return limpiar_nombre(textos[i + 1])

    cuerpo = soup.get_text("\n", strip=True)
    patron_expediente = "N[" + chr(186) + "o]?\\s*(?:de\\s*)?expediente\\s*[:\\n]\\s*([^\\n]+)"
    match = re.search(patron_expediente, cuerpo, re.IGNORECASE)
    if match:
        return limpiar_nombre(match.group(1))

    return ""


def extraer_node_id(soup, html):
    nodo = soup.find(attrs={"data-history-node-id": True})
    if nodo:
        return nodo.get("data-history-node-id", "").strip()

    for patron in [
        r"data-history-node-id=[\"'](\d+)[\"']",
        r"page-node-(\d+)",
        r"/node/(\d+)",
        r"/print/pdf/node/(\d+)",
    ]:
        match = re.search(patron, html)
        if match:
            return match.group(1)

    return ""


def extraer_enlace_ficha_pdf(soup, url_base, html):
    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if es_url_interna(url) and es_enlace_ficha_pdf(url):
            return url

    node_id = extraer_node_id(soup, html)
    if node_id:
        return urljoin(url_base, f"/contrato-publico/print/pdf/node/{node_id}")

    return ""


def textos_previos_utiles(enlace, limite=25):
    resultado = []
    for texto in enlace.find_all_previous(string=True, limit=limite):
        t = " ".join(str(texto).split())
        if not t or es_texto_generico(t):
            continue
        resultado.append(t)
    return resultado


def nombre_logico_desde_enlace(enlace, indice):
    for clave in ("download", "title"):
        valor = enlace.get(clave, "")
        if valor and not es_texto_generico(valor):
            return limpiar_titulo_documento(valor)

    texto_enlace = enlace.get_text(" ", strip=True)
    if texto_enlace and not es_texto_generico(texto_enlace):
        return limpiar_titulo_documento(texto_enlace)

    for texto in textos_previos_utiles(enlace):
        candidato = limpiar_titulo_documento(texto)
        if candidato and not es_texto_generico(candidato):
            return candidato

    padre = enlace.find_parent(["li", "tr", "div", "section", "article"])
    if padre:
        candidato = limpiar_titulo_documento(padre.get_text(" ", strip=True))
        if candidato and not es_texto_generico(candidato):
            return candidato

    return f"documento_{indice}"


def extraer_adjuntos(soup, url_base):
    adjuntos = []
    vistos = set()

    for enlace in soup.find_all("a", href=True):
        url = urljoin(url_base, enlace["href"])
        if not es_url_interna(url) or not es_enlace_adjunto(url):
            continue

        clave = url.lower()
        if clave in vistos:
            continue
        vistos.add(clave)

        nombre_logico = nombre_logico_desde_enlace(enlace, len(adjuntos) + 1)
        adjuntos.append({
            "url": url,
            "nombre_logico": nombre_logico,
        })

    return adjuntos


def descargar_documento(session, url, nombre_logico, carpeta_destino, referer):
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
            log("Uso: python Descargar_ComunidadMadrid.py <URL> [--destino <CARPETA>]")
            sys.exit(1)
        carpeta_destino = os.path.abspath(args[idx + 1])
        del args[idx:idx + 2]

    if len(args) != 1:
        log("Uso: python Descargar_ComunidadMadrid.py <URL> [--destino <CARPETA>]")
        sys.exit(1)

    os.makedirs(carpeta_destino, exist_ok=True)
    return args[0], carpeta_destino


def main():
    url, carpeta_destino = parsear_argumentos()
    session = crear_session()

    try:
        log(f"Accediendo a Comunidad de Madrid: {url}")
        respuesta = session.get(url, timeout=TIMEOUT_DESCARGA)
        respuesta.raise_for_status()
    except Exception as e:
        log(f"Error accediendo a la URL: {e}")
        sys.exit(1)

    soup = BeautifulSoup(respuesta.text, "html.parser")
    expediente = extraer_numero_expediente(soup)
    ficha_pdf = extraer_enlace_ficha_pdf(soup, url, respuesta.text)
    adjuntos = extraer_adjuntos(soup, url)

    trabajos = []
    if ficha_pdf:
        nombre_ficha = f"Ficha expediente {expediente}" if expediente else "Ficha expediente"
        trabajos.append({
            "url": ficha_pdf,
            "nombre_logico": nombre_ficha + ".pdf",
        })

    trabajos.extend(adjunto for adjunto in adjuntos if adjunto["url"] != ficha_pdf)

    if not trabajos:
        log("No se han encontrado documentos internos para descargar.")
        sys.exit(1)

    log(f"Documentos internos encontrados: {len(trabajos)}")

    descargados = 0
    omitidos = 0
    errores = 0

    for i, trabajo in enumerate(trabajos, 1):
        log(f"\n[{i}/{len(trabajos)}] {trabajo['nombre_logico']}")
        try:
            estado, _ = descargar_documento(
                session,
                trabajo["url"],
                trabajo["nombre_logico"],
                carpeta_destino,
                url,
            )
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
