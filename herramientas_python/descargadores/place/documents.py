"""Acceso y extracción de documentos específicos de PLACE."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from ..common.download_models import (
    MIME_TO_EXTENSION,
    VALID_EXTENSIONS,
    RemoteDocument,
    build_document_filename,
    detect_document_extension,
    extension_from_content,
    extension_from_content_type,
    extension_from_name,
    name_from_content_disposition,
)
from ..common.errors import SafeFileError
from ..common.safe_files import sanitize_filename, write_bytes_if_absent
from .browser_fallback import PlaceChallengeResolver, PlaceDocumentRequest, RenderedDocument
from .challenge import (
    canonicalizar_url_place,
    es_desafio_javascript_place as _es_desafio_javascript_place,
    es_host_place,
    es_url_place_segura,
    requiere_interaccion_place,
)
from .errors import PlaceBrowserError

EXTENSIONES_VALIDAS = VALID_EXTENSIONS
MIME_A_EXTENSION = MIME_TO_EXTENSION
PLACE_JS_CHALLENGE = "PLACE_JS_CHALLENGE"
PLACE_BROWSER_CHALLENGE = "PLACE_BROWSER_CHALLENGE"
PLACE_UNEXPECTED_HTML = "PLACE_UNEXPECTED_HTML"
DOCUMENT_ACCEPT_HEADER = (
    "application/pdf,application/octet-stream,application/xml,text/xml,"
    "application/zip,*/*;q=0.8"
)
MAX_REDIRECTS_PLACE = 5


class PlaceDocumentRedirectError(ValueError):
    """Una redirección documental no puede seguirse de forma segura."""


def limpiar_nombre(nombre):
    return sanitize_filename(nombre, max_length=None)


def extension_desde_nombre(nombre):
    return extension_from_name(nombre)


def nombre_desde_content_disposition(valor):
    return name_from_content_disposition(valor)


def extension_desde_contenido(contenido):
    return extension_from_content(contenido)


def extension_desde_content_type(content_type):
    return extension_from_content_type(content_type)


def detectar_extension(respuesta, texto_visible="", nombre_logico="", archivo_url=""):
    return detect_document_extension(
        RemoteDocument(
            source_url=archivo_url,
            content=respuesta.content,
            logical_name=nombre_logico,
            visible_text=texto_visible,
            content_type=respuesta.headers.get("Content-Type", ""),
            content_disposition=respuesta.headers.get("Content-Disposition", ""),
            platform="PLACE",
        )
    )


def construir_nombre_archivo(respuesta, nombre_logico, texto_visible, archivo_url, ext):
    document = RemoteDocument(
        source_url=archivo_url,
        content=respuesta.content,
        logical_name=nombre_logico,
        visible_text=texto_visible,
        content_type=respuesta.headers.get("Content-Type", ""),
        content_disposition=respuesta.headers.get("Content-Disposition", ""),
        platform="PLACE",
    )
    return build_document_filename(document, ext)


def ruta_si_no_existe(carpeta_destino, nombre_archivo):
    ruta = os.path.join(carpeta_destino, nombre_archivo)
    if os.path.exists(ruta):
        return None, nombre_archivo

    return ruta, nombre_archivo


def _response_transport_metadata(respuesta, archivo_url, contenido):
    headers = getattr(respuesta, "headers", {}) or {}
    try:
        http_status = int(getattr(respuesta, "status_code", 0) or 0)
    except (TypeError, ValueError):
        http_status = 0
    try:
        redirect_count = len(getattr(respuesta, "history", ()) or ())
    except TypeError:
        redirect_count = 0
    return {
        "content_type": str(headers.get("Content-Type", "") or ""),
        "size": len(contenido),
        "final_url": str(getattr(respuesta, "url", "") or archivo_url),
        "http_status": http_status,
        "redirect_count": redirect_count,
    }


def _respuesta_permanece_en_place(respuesta, archivo_url):
    urls = [str(archivo_url or "")]
    history = getattr(respuesta, "history", ()) or ()
    try:
        urls.extend(str(getattr(item, "url", "") or "") for item in history)
    except TypeError:
        return False
    urls.append(str(getattr(respuesta, "url", "") or ""))
    return all(
        es_url_place_segura(canonicalizar_url_place(item))
        for item in urls
        if item
    )


def _obtener_documento_sin_salir_de_place(session, archivo_url, *, referer):
    """Sigue únicamente redirecciones HTTPS internas de PLACE."""

    current_url = archivo_url
    history = []
    for _ in range(MAX_REDIRECTS_PLACE + 1):
        respuesta = session.get(
            current_url,
            timeout=60,
            headers={"Referer": referer, "Accept": DOCUMENT_ACCEPT_HEADER},
            allow_redirects=False,
        )
        try:
            status_code = int(getattr(respuesta, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status_code = 0
        if status_code not in {301, 302, 303, 307, 308}:
            if history:
                try:
                    previous = list(getattr(respuesta, "history", ()) or ())
                    respuesta.history = tuple(history + previous)
                except (AttributeError, TypeError):
                    pass
            return respuesta
        headers = getattr(respuesta, "headers", {}) or {}
        location = str(headers.get("Location", "") or "")
        next_url = canonicalizar_url_place(urljoin(current_url, location)) if location else ""
        if not next_url or not es_url_place_segura(next_url):
            raise PlaceDocumentRedirectError(
                "PLACE_DOCUMENT_REDIRECT_INVALID: PLACE redirigió el documento fuera de su dominio HTTPS autorizado."
            )
        history.append(respuesta)
        current_url = next_url
    raise PlaceDocumentRedirectError(
        "PLACE_DOCUMENT_REDIRECT_INVALID: PLACE superó el máximo de redirecciones documentales."
    )


def _registrar_evento(
    download_events,
    *,
    status,
    name,
    source_url,
    path="",
    sha256="",
    sha256_source="",
    error_code="",
    error_message="",
    metadata=None,
    retrieval_method="http",
    fallback_reason="",
):
    if download_events is None:
        return
    event = {
        "status": status,
        "name": name,
        "path": path,
        "source_url": source_url,
        "sha256": sha256,
        "sha256_source": sha256_source,
        "error_code": error_code,
        "error_message": error_message,
        "retrieval_method": retrieval_method,
        "fallback_reason": fallback_reason,
    }
    event.update(metadata or {})
    download_events.append(event)


def es_desafio_javascript_place(contenido):
    """Detecta la pantalla intermedia de PLACE sin guardar su cuerpo."""

    return _es_desafio_javascript_place(contenido)


def es_contenedor_documentos_place(contenido, url_base=""):
    """Un HTML de PLACE solo es contenedor si publica enlaces documentales."""

    soup = BeautifulSoup(contenido, "html.parser")
    return any(
        es_enlace_documento(str(link.get("href") or ""), url_base)
        for link in soup.find_all("a", href=True)
    )


def _texto_inicial_de_marcado(contenido):
    """Devuelve una muestra textual también para respuestas UTF-16."""

    sample = bytes(contenido)[:4096].lstrip()
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    if sample.startswith(b"\xff\xfe"):
        return sample[2:].decode("utf-16-le", errors="ignore").lstrip()
    if sample.startswith(b"\xfe\xff"):
        return sample[2:].decode("utf-16-be", errors="ignore").lstrip()
    if sample.startswith(b"<\x00"):
        return sample.decode("utf-16-le", errors="ignore").lstrip()
    if sample.startswith(b"\x00<"):
        return sample.decode("utf-16-be", errors="ignore").lstrip()
    return sample.decode("utf-8", errors="ignore").lstrip()


def _parece_html_de_respuesta(contenido):
    """Todo marcado debe justificarse como HTML o XML documental conocido."""

    return _texto_inicial_de_marcado(contenido).startswith("<")


def _es_xml_documental_esperado(contenido, *, logical_extension, disposition_extension, content_type):
    """Solo permite XML bien formado cuando el transporte o nombre lo declara."""

    declared_as_xml = (
        logical_extension == ".xml"
        or disposition_extension == ".xml"
        or extension_desde_content_type(content_type) == ".xml"
    )
    if not declared_as_xml:
        return False
    try:
        ElementTree.fromstring(bytes(contenido))
    except (ElementTree.ParseError, UnicodeError, ValueError):
        return False
    return True


def clasificar_respuesta_documental(
    respuesta,
    nombre_logico,
    texto_visible,
    archivo_url,
    *,
    strict_html=False,
):
    """Distingue documento publicable, contenedor legítimo y HTML no verificable."""

    contenido = respuesta.content
    if not contenido:
        return ".bin", "invalid", "PLACE_EMPTY_DOCUMENT", (
            "PLACE devolvió una respuesta vacía para un enlace documental."
        )
    # El WAF puede mentir con application/octet-stream; hay que reconocerlo antes
    # de inferir .bin a partir de MIME o del nombre lógico.
    if es_desafio_javascript_place(contenido):
        return ".html", "invalid", PLACE_JS_CHALLENGE, (
            "PLACE devolvió una pantalla que exige JavaScript en lugar del documento."
        )
    if requiere_interaccion_place(contenido):
        return ".html", "invalid", "PLACE_ACCESS_CHALLENGE", (
            "PLACE devolvió una respuesta de acceso o verificación en lugar del documento."
        )
    logical_extension = extension_desde_nombre(nombre_logico or texto_visible)
    disposition_extension = extension_desde_nombre(
        nombre_desde_content_disposition((getattr(respuesta, "headers", {}) or {}).get("Content-Disposition", ""))
    )
    ext = detectar_extension(respuesta, texto_visible, nombre_logico, archivo_url)
    markup = _parece_html_de_respuesta(contenido)
    if markup and _es_xml_documental_esperado(
        contenido,
        logical_extension=logical_extension,
        disposition_extension=disposition_extension,
        content_type=(getattr(respuesta, "headers", {}) or {}).get("Content-Type", ""),
    ):
        return ".xml", "document", "", ""
    if markup and es_contenedor_documentos_place(contenido, archivo_url):
        return ".html", "container", "", ""
    if markup:
        if not strict_html and (
            logical_extension in {".html", ".htm"}
            or disposition_extension in {".html", ".htm"}
        ):
            return ".html", "document", "", ""
        return ".html", "invalid", PLACE_UNEXPECTED_HTML, (
            "PLACE devolvió HTML no verificable para un enlace documental."
        )
    if ext not in {".html", ".htm"} and not _parece_html_de_respuesta(contenido):
        return ext, "document", "", ""
    if not strict_html and (
        logical_extension in {".html", ".htm"}
        or disposition_extension in {".html", ".htm"}
    ):
        return ".html", "document", "", ""
    return ".html", "invalid", PLACE_UNEXPECTED_HTML, (
        "PLACE devolvió HTML no verificable para un enlace documental."
    )


def _respuesta_renderizada(payload: RenderedDocument, archivo_url: str):
    final_url = canonicalizar_url_place(str(payload.final_url or payload.source_url or archivo_url))
    if not es_url_place_segura(final_url):
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: el navegador devolvió una URL documental no autorizada."
        )
    headers = {}
    if payload.content_type:
        headers["Content-Type"] = payload.content_type
    if payload.content_disposition:
        headers["Content-Disposition"] = payload.content_disposition
    return SimpleNamespace(
        content=bytes(payload.content),
        headers=headers,
        url=final_url,
        status_code=int(payload.http_status or 0),
        history=tuple(None for _ in range(max(0, int(payload.redirect_count or 0)))),
    )


def _resolver_desafio(resolver, request: PlaceDocumentRequest) -> RenderedDocument:
    resolve = getattr(resolver, "resolve", None)
    if not callable(resolve):
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: el fallback de navegador no implementa resolve()."
        )
    payload = resolve(request)
    if not isinstance(payload, RenderedDocument):
        raise PlaceBrowserError(
            "PLACE_BROWSER_DOWNLOAD_FAILED: el fallback de navegador devolvió un documento inválido."
        )
    return payload


def descargar_documento(
    session,
    url_base,
    href,
    nombre_logico,
    texto_visible,
    carpeta_destino,
    urls_descargadas,
    download_events=None,
    challenge_resolver: PlaceChallengeResolver | None = None,
):
    archivo_url = canonicalizar_url_place(urljoin(url_base, href))

    if archivo_url in urls_descargadas:
        return None
    if not es_url_place_segura(archivo_url):
        urls_descargadas.add(archivo_url)
        _registrar_evento(
            download_events,
            status="failed",
            name=limpiar_nombre(nombre_logico or texto_visible) or "documento",
            source_url=archivo_url,
            error_code="PLACE_DOCUMENT_URL_INVALID",
            error_message="PLACE expone un enlace documental fuera de su dominio HTTPS autorizado.",
        )
        print(f"Enlace documental no autorizado de PLACE: {archivo_url}")
        return None

    try:
        print(f"Descargando: {archivo_url}")
        respuesta = _obtener_documento_sin_salir_de_place(
            session,
            archivo_url,
            referer=url_base,
        )
        try:
            respuesta.raise_for_status()
        except requests.HTTPError:
            # Algunos WAF responden 403 aunque el cuerpo sea el mismo reto JS.
            # Se permite clasificarlo para que el fallback pueda actuar; otros
            # errores HTTP siguen su ruta habitual de fallo seguro.
            if not requiere_interaccion_place(getattr(respuesta, "content", b"")):
                raise

        contenido = respuesta.content
        metadata = _response_transport_metadata(respuesta, archivo_url, contenido)
        final_http_url = canonicalizar_url_place(str(getattr(respuesta, "url", "") or archivo_url))
        if not _respuesta_permanece_en_place(respuesta, archivo_url):
            urls_descargadas.add(archivo_url)
            _registrar_evento(
                download_events,
                status="failed",
                name=limpiar_nombre(nombre_logico or texto_visible) or "documento",
                source_url=archivo_url,
                error_code="PLACE_DOCUMENT_REDIRECT_INVALID",
                error_message="PLACE redirigió el documento a una URL fuera de su dominio HTTPS autorizado.",
                metadata=metadata,
            )
            print(f"Redirección documental no autorizada de PLACE: {final_http_url}")
            return None
        retrieval_method = "http"
        fallback_reason = ""
        ext, response_kind, error_code, error_message = clasificar_respuesta_documental(
            respuesta,
            nombre_logico,
            texto_visible,
            archivo_url,
        )
        if response_kind == "invalid" and error_code == PLACE_JS_CHALLENGE and challenge_resolver:
            try:
                rendered = _resolver_desafio(
                    challenge_resolver,
                    PlaceDocumentRequest(
                        document_url=archivo_url,
                        referer=canonicalizar_url_place(url_base),
                        href=str(href or ""),
                        logical_name=str(nombre_logico or ""),
                        visible_text=str(texto_visible or ""),
                    ),
                )
                respuesta = _respuesta_renderizada(rendered, archivo_url)
                contenido = respuesta.content
                metadata = _response_transport_metadata(respuesta, archivo_url, contenido)
                retrieval_method = "browser"
                fallback_reason = PLACE_JS_CHALLENGE
                ext, response_kind, error_code, error_message = clasificar_respuesta_documental(
                    respuesta,
                    nombre_logico,
                    texto_visible,
                    archivo_url,
                    strict_html=True,
                )
                if response_kind == "invalid" and error_code == PLACE_JS_CHALLENGE:
                    error_code = PLACE_BROWSER_CHALLENGE
                    error_message = (
                        "El navegador también recibió la pantalla de PLACE que exige JavaScript."
                    )
            except Exception as exc:
                urls_descargadas.add(archivo_url)
                code = str(getattr(exc, "error_code", "") or "PLACE_BROWSER_DOWNLOAD_FAILED")
                _registrar_evento(
                    download_events,
                    status="failed",
                    name=limpiar_nombre(nombre_logico or texto_visible) or "documento",
                    source_url=archivo_url,
                    error_code=code,
                    error_message=str(exc),
                    metadata=metadata,
                    retrieval_method="browser",
                    fallback_reason=PLACE_JS_CHALLENGE,
                )
                print(f"Fallback de navegador no disponible para {archivo_url}: {exc}")
                return None
        nombre_archivo = construir_nombre_archivo(respuesta, nombre_logico, texto_visible, archivo_url, ext)
        if response_kind == "invalid":
            urls_descargadas.add(archivo_url)
            _registrar_evento(
                download_events,
                status="failed",
                name=nombre_archivo,
                source_url=archivo_url,
                error_code=error_code,
                error_message=error_message,
                metadata=metadata,
                retrieval_method=retrieval_method,
                fallback_reason=fallback_reason,
            )
            print(f"Respuesta no válida de PLACE para {nombre_archivo}: {error_message}")
            return None

        remote_sha256 = hashlib.sha256(contenido).hexdigest()
        result = write_bytes_if_absent(carpeta_destino, nombre_archivo, contenido)
        if result.skipped:
            urls_descargadas.add(archivo_url)
            _registrar_evento(
                download_events,
                status="reused",
                name=nombre_archivo,
                path=str(Path(carpeta_destino) / nombre_archivo),
                source_url=archivo_url,
                sha256=remote_sha256,
                sha256_source="remote",
                metadata=metadata,
                retrieval_method=retrieval_method,
                fallback_reason=fallback_reason,
            )
            print(f"Omitido, ya existe: {nombre_archivo}")
            return None

        urls_descargadas.add(archivo_url)
        _registrar_evento(
            download_events,
            status="created",
            name=nombre_archivo,
            path=str(result.path or ""),
            source_url=archivo_url,
            sha256=result.sha256 or remote_sha256,
            sha256_source="remote",
            metadata=metadata,
            retrieval_method=retrieval_method,
            fallback_reason=fallback_reason,
        )

        if ext in {".html", ".htm", ".xml"}:
            print(f"Guardado como: {nombre_archivo} (se revisara por si contiene adjuntos)")
        else:
            print(f"Guardado como: {nombre_archivo}")

        return nombre_archivo

    except PlaceDocumentRedirectError as e:
        urls_descargadas.add(archivo_url)
        _registrar_evento(
            download_events,
            status="failed",
            name=limpiar_nombre(nombre_logico or texto_visible) or "documento",
            source_url=archivo_url,
            error_code="PLACE_DOCUMENT_REDIRECT_INVALID",
            error_message=str(e),
        )
        print(f"Redirección documental no autorizada de PLACE: {e}")
        return None
    except (requests.RequestException, SafeFileError, OSError, ValueError, TypeError) as e:
        _registrar_evento(
            download_events,
            status="failed",
            name=limpiar_nombre(nombre_logico or texto_visible) or "documento",
            source_url=archivo_url,
            error_code="PLACE_DOCUMENT_DOWNLOAD_FAILED",
            error_message=str(e),
        )
        print(f"Error descargando {archivo_url}: {e}")
        return None


def es_enlace_documento(href, url_base=""):
    """Reconoce solo enlaces documentales que permanezcan dentro de PLACE."""

    raw_href = str(href or "").strip()
    if not raw_href:
        return False
    absolute = canonicalizar_url_place(urljoin(url_base, raw_href)) if url_base else raw_href
    parsed = urlsplit(absolute)
    if parsed.hostname and not es_host_place(parsed.hostname):
        return False
    if parsed.scheme and parsed.scheme.casefold() != "https":
        return False
    target = f"{parsed.path}?{parsed.query}"
    return "GetDocumentByIdServlet" in target or "DocumentIdParam=" in target


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
        return canonicalizar_url_place(urljoin(url_base, base_tag["href"]))
    return canonicalizar_url_place(url_base)


def procesar_html(
    session,
    soup,
    url_base,
    carpeta_destino,
    urls_descargadas,
    download_events=None,
    challenge_resolver: PlaceChallengeResolver | None = None,
):
    archivos_descargados = []
    estamos_en_otros_documentos = False
    url_base_real = base_desde_soup(soup, url_base)

    for tag in soup.find_all(True):
        if tag.has_attr("title") and "Otros Documentos" in tag["title"]:
            estamos_en_otros_documentos = True

        if tag.name != "a" or not tag.has_attr("href"):
            continue

        href = tag["href"]
        if not es_enlace_documento(href, url_base_real):
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
            download_events,
            challenge_resolver,
        )

        if nombre_archivo:
            archivos_descargados.append(nombre_archivo)

    return archivos_descargados


def procesar_html_pliego(
    session,
    soup,
    url_base,
    carpeta_destino,
    urls_descargadas,
    download_events=None,
    challenge_resolver: PlaceChallengeResolver | None = None,
):
    archivos_descargados = []
    url_base_real = base_desde_soup(soup, url_base)

    for enlace in soup.find_all("a", href=True):
        href = enlace["href"]
        if not es_enlace_documento(href, url_base_real):
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
            download_events,
            challenge_resolver,
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
        ext = os.path.splitext(nombre.lower())[1]
        if ext in {".html", ".htm", ".xml"}:
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


def procesar_pliegos_descargados(
    session,
    url_base,
    carpeta_destino,
    archivos_primera_fase,
    urls_descargadas,
    download_events=None,
    source_urls_by_name=None,
    challenge_resolver: PlaceChallengeResolver | None = None,
):
    candidatos = candidatos_para_segunda_fase(carpeta_destino, archivos_primera_fase)
    total_adjuntos = 0
    archivos_descargados = []

    for archivo in candidatos:
        ruta = os.path.join(carpeta_destino, archivo)
        print(f"\nAnalizando adjuntos en: {archivo}")

        try:
            with open(ruta, "rb") as f:
                contenido = f.read()

            soup = BeautifulSoup(contenido, "html.parser")
            source_url = str((source_urls_by_name or {}).get(archivo) or url_base)
            adjuntos = procesar_html_pliego(
                session,
                soup,
                source_url,
                carpeta_destino,
                urls_descargadas,
                download_events,
                challenge_resolver,
            )
            total_adjuntos += len(adjuntos)
            archivos_descargados.extend(adjuntos)
            print(f"Adjuntos encontrados en {archivo}: {len(adjuntos)}")

        except (OSError, ValueError, TypeError) as e:
            print(f"Error procesando {archivo}: {e}")

    if candidatos:
        print(f"\nSegunda fase: {total_adjuntos} adjunto(s) descargado(s) desde documentos HTML/XML.")
    else:
        print("\nSegunda fase: no se encontraron documentos Pliego/HTML para analizar.")
    return archivos_descargados


def crear_session(_url_referer=""):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
    })
    return session
