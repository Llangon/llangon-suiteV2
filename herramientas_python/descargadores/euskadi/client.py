"""Navegación y extracción específicas de Euskadi."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from ..common.http import create_public_session
from ..common.safe_files import sanitize_filename


TIMEOUT_DESCARGA = (5, 90)


def limpiar_nombre(nombre):
    return sanitize_filename(nombre, max_length=None)


def crear_session():
    return create_public_session()


def extraer_expediente(soup):
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return limpiar_nombre(h1.get_text(" ", strip=True))
    textos = [text.strip() for text in soup.stripped_strings if text.strip()]
    for index, texto in enumerate(textos[:-1]):
        if texto.lower() == "expediente":
            return limpiar_nombre(textos[index + 1])
    return ""


def extraer_ficha_pdf(soup, url_base, expediente):
    for enlace in soup.find_all("a", href=True):
        href = urljoin(url_base, enlace["href"])
        if "fichaExpediente.pdf" in href:
            nombre = f"Ficha expediente {expediente}.pdf" if expediente else "Ficha expediente.pdf"
            return {
                "url": href,
                "nombre_logico": nombre,
                "section": "Ficha",
                "role": "tender_summary",
            }
    return None


def _seccion_enlace(enlace):
    contenedor = enlace.find_parent(id=re.compile(r"^tabs-\d+$"))
    if not contenedor:
        return ""
    titulos = {
        "tabs-5": "Ficheros",
        "tabs-7": "Tablón de anuncios",
        "tabs-9": "Resolución",
        "tabs-10": "Contrato",
        "tabs-11": "Publicaciones",
        "tabs-14": "Recursos",
        "tabs-16": "Histórico",
    }
    return titulos.get(contenedor.get("id", ""), "")


def endpoint_descarga(funcion, id_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/downloadDokusiREST"
    if funcion == "descargarFicheroContrato":
        return f"{base}/descargaFicheroContratoPorIdFichero?idFichero={id_fichero}&R01HNoPortal=true"
    return f"{base}/descargaFicheroPorIdFichero?idFichero={id_fichero}&R01HNoPortal=true"


def endpoint_comprobacion(funcion, id_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/downloadDokusiREST"
    if funcion == "descargarFicheroContrato":
        return f"{base}/comprobarFicheroContratoPorIdFichero?idFichero={id_fichero}"
    return f"{base}/comprobarFicheroPorIdFichero?idFichero={id_fichero}"


def endpoint_descarga_pid(id_expediente_origen, id_tipo_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/ficherosPid"
    return (
        f"{base}/descargarDocumentosPorTipo?idExpOrigen={id_expediente_origen}"
        f"&idTipoFichero={id_tipo_fichero}&R01HNoPortal=true"
    )


def endpoint_comprobacion_pid(id_expediente_origen, id_tipo_fichero):
    base = "https://www.contratacion.euskadi.eus/ac70cPublicidadWar/ficherosPid"
    return (
        f"{base}/existeDocumentoPorTipo?idExpOrigen={id_expediente_origen}"
        f"&idTipoFichero={id_tipo_fichero}"
    )


def extraer_documentos(soup):
    documentos = []
    vistos = set()
    patron = re.compile(r"(descargarFicheroContrato|descargarFichero)\(\s*['\"]?(\d+)['\"]?\s*\)")
    for enlace in soup.find_all("a"):
        match = patron.search(enlace.get("onclick", ""))
        if not match:
            continue
        funcion, id_fichero = match.groups()
        clave = funcion, id_fichero
        if clave in vistos:
            continue
        vistos.add(clave)
        documentos.append(
            {
                "url": endpoint_descarga(funcion, id_fichero),
                "check_url": endpoint_comprobacion(funcion, id_fichero),
                "nombre_logico": limpiar_nombre(enlace.get_text(" ", strip=True)) or f"fichero_{id_fichero}",
                "remote_id": id_fichero,
                "section": _seccion_enlace(enlace),
                "role": "document",
            }
        )
    return documentos


def extraer_paquetes_modelos(soup, expediente=""):
    """Extrae el paquete específico de modelos, sin duplicar el ZIP general."""

    paquetes = []
    vistos = set()
    patron = re.compile(r"descargarFicheroPID\(\s*(\d+)\s*,\s*(\d+)\s*\)")
    for enlace in soup.find_all("a"):
        match = patron.search(enlace.get("onclick", ""))
        if not match:
            continue
        id_expediente_origen, id_tipo_fichero = match.groups()
        if id_tipo_fichero != "109":
            continue
        clave = id_expediente_origen, id_tipo_fichero
        if clave in vistos:
            continue
        vistos.add(clave)
        nombre = limpiar_nombre(enlace.get_text(" ", strip=True)) or "Modelos"
        if expediente:
            nombre = f"{nombre} {expediente}"
        paquetes.append(
            {
                "url": endpoint_descarga_pid(id_expediente_origen, id_tipo_fichero),
                "check_url": endpoint_comprobacion_pid(id_expediente_origen, id_tipo_fichero),
                "nombre_logico": f"{nombre}.zip",
                "remote_id": f"PID:{id_expediente_origen}:{id_tipo_fichero}",
                "section": "Modelos",
                "role": "models_package",
            }
        )
    return paquetes


def comprobar_disponible(session, documento, referer):
    check_url = documento.get("check_url")
    if not check_url:
        return True
    respuesta = session.get(check_url, timeout=TIMEOUT_DESCARGA, headers={"Referer": referer})
    respuesta.raise_for_status()
    return respuesta.text.strip().lower() in {"true", "1", "ok", ""}
