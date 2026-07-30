"""Descubrimiento y descarga de documentos generales de Catalunya."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from ..common.download_models import (
    MIME_TO_EXTENSION,
    VALID_EXTENSIONS,
    DocumentDownloadResult,
    DownloadedDocument,
    RemoteDocument,
    build_document_filename,
    detect_document_extension,
    extension_from_content,
    extension_from_content_type,
    extension_from_name,
    name_from_content_disposition,
)
from ..common.errors import SafeFileError
from ..common.safe_files import (
    ensure_safe_child,
    sanitize_filename,
    write_bytes_content_aware,
)
from .client import (
    TIMEOUT_DESCARGA,
    es_url_catalunya,
    get_json,
    identificadores_publicacion,
    idioma_desde_url,
    origen_catalunya,
    portal_api_url,
    url_api_detall_publicacion,
)
from .errors import CatalunyaStructureError


EXTENSIONES_VALIDAS = VALID_EXTENSIONS
MIME_A_EXTENSION = MIME_TO_EXTENSION
MAX_PUBLICACIONES_RELACIONADAS = 250
CLAVES_NAVEGACION_PUBLICACIONES = (
    "navegacioEsmenes",
    "navegacioFases",
    "navegacioCpp",
)


@dataclass
class CatalunyaDocumentInventory:
    links: list[dict[str, str]] = field(default_factory=list)
    publication_ids: list[str] = field(default_factory=list)
    publications: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.errors


def normalizar(texto: object) -> str:
    value = unicodedata.normalize("NFD", str(texto or ""))
    value = "".join(character for character in value if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", value).lower().strip()


def limpiar_nombre(nombre: object) -> str:
    return sanitize_filename(unescape(unquote(str(nombre or ""))))


def acortar_nombre(nombre: str, max_base: int = 150) -> str:
    base, extension = os.path.splitext(nombre)
    if len(base) > max_base:
        base = base[:max_base].rstrip(" .")
    return base + extension


def limpiar_titulo_documento(texto: object) -> str:
    value = unescape(str(texto or ""))
    value = re.sub(r"\b(Descarregar|Descargar|Download)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\b(PDF|XML|HTML?|DOCX?|XLSX?|ZIP|RTF|CSV|ODS|ODT)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|bytes?)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b", " ", value)
    return limpiar_nombre(re.sub(r"\s+", " ", value).strip(" .:-"))


def es_texto_generico(texto: object) -> bool:
    value = normalizar(texto)
    return not value or value in {
        "descarregar", "descargar", "download", "pdf", "xml", "documentacio",
        "documentacion", "fitxer", "archivo", "document", "documents",
    }


def extension_desde_nombre(nombre: object) -> str:
    return extension_from_name(nombre)


def extension_desde_texto(texto: object) -> str:
    tokens = re.split(r"[^a-z0-9]+", normalizar(texto))
    for extension in EXTENSIONES_VALIDAS:
        if extension.strip(".") in tokens:
            return extension
    return ""


def nombre_desde_content_disposition(valor: object) -> str:
    return name_from_content_disposition(valor)


def extension_desde_contenido(contenido: bytes) -> str:
    return extension_from_content(contenido)


def extension_desde_content_type(content_type: object) -> str:
    return extension_from_content_type(content_type)


def detectar_extension(respuesta, nombre_logico: str = "", archivo_url: str = "") -> str:
    remote = RemoteDocument(
        source_url=archivo_url,
        content=respuesta.content,
        logical_name=nombre_logico,
        content_type=respuesta.headers.get("Content-Type", ""),
        content_disposition=respuesta.headers.get("Content-Disposition", ""),
        platform="CATALUNYA",
    )
    return detect_document_extension(remote)


def construir_nombre_archivo(respuesta, nombre_logico: str, archivo_url: str, extension: str) -> str:
    remote = RemoteDocument(
        source_url=archivo_url,
        content=respuesta.content,
        logical_name=nombre_logico,
        content_type=respuesta.headers.get("Content-Type", ""),
        content_disposition=respuesta.headers.get("Content-Disposition", ""),
        platform="CATALUNYA",
    )
    # Compatibilidad: Catalunya prioriza el título publicado sobre la cabecera HTTP.
    if nombre_logico:
        candidate = limpiar_nombre(nombre_logico)
        base, current = os.path.splitext(candidate)
        current = current.lower()
        base_extension = os.path.splitext(base)[1].lower()
        if current in EXTENSIONES_VALIDAS:
            if current == extension or extension in ("", ".bin"):
                return acortar_nombre(candidate)
            if base_extension == extension:
                return acortar_nombre(base)
            if base_extension in EXTENSIONES_VALIDAS:
                return acortar_nombre(limpiar_nombre(os.path.splitext(base)[0]) + extension)
            return acortar_nombre(limpiar_nombre(base) + extension)
        return acortar_nombre(candidate + extension)
    return acortar_nombre(build_document_filename(remote, extension))


def ruta_si_no_existe(carpeta_destino: str | Path, nombre_archivo: str):
    path = os.path.join(str(carpeta_destino), nombre_archivo)
    return (None, nombre_archivo) if os.path.exists(path) else (path, nombre_archivo)


def es_enlace_documento(url: str) -> bool:
    path = urlparse(url).path.lower()
    return es_url_catalunya(url) and (
        "/portal-api/descarrega-document/" in path
        or "/portal-api/descarrega-document-antic/" in path
    )


def fecha_desde_texto(texto: object) -> str:
    match = re.search(
        r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?)?",
        str(texto or ""),
    )
    if not match:
        return ""
    day, month, year = (int(match.group(index)) for index in (1, 2, 3))
    if year < 100:
        year += 2000
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return ""
    if match.group(4) and match.group(5):
        return f"{year:04d}-{month:02d}-{day:02d}T{int(match.group(4)):02d}:{int(match.group(5)):02d}:00"
    return f"{year:04d}-{month:02d}-{day:02d}"


def _identificador(valor: object) -> str:
    identifier = str(valor or "").strip()
    return identifier if re.fullmatch(r"[A-Za-z0-9-]+", identifier) else ""


def _fecha_publicacion_detalle(detail: dict, fallback: str = "") -> str:
    dades = detail.get("dades")
    if isinstance(dades, dict):
        for key in ("dataPublicacioReal", "dataPublicacioPlanificada"):
            value = str(dades.get(key) or "").strip()
            if value:
                return value
    return str(detail.get("dataPublicacio") or fallback or "").strip()


def _tipo_publicacion_detalle(detail: dict) -> str:
    dades = detail.get("dades")
    publicacio = dades.get("publicacio") if isinstance(dades, dict) else None
    tipus = publicacio.get("tipusEsmena") if isinstance(publicacio, dict) else None
    if isinstance(tipus, dict):
        label = str(tipus.get("text") or "").strip()
        if label:
            return label
    fase = publicacio.get("fase") if isinstance(publicacio, dict) else None
    if isinstance(fase, dict):
        label = str(fase.get("text") or "").strip()
        if label:
            return label
    return "Publicación"


def _nombre_carpeta_publicacion(
    publication_id: str,
    publication_date: str,
    publication_type: str,
) -> str:
    date_label = (
        publication_date[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}", publication_date)
        else "Sin fecha"
    )
    type_label = sanitize_filename(
        publication_type or "Publicación",
        max_length=60,
    )
    return sanitize_filename(
        f"{date_label} - {type_label} - {publication_id}",
        max_length=None,
    )


def metadatos_publicacion_desde_url(url: str) -> dict[str, str]:
    identifiers = identificadores_publicacion(url)
    publication_id = _identificador(identifiers[-1] if identifiers else "")
    if not publication_id:
        return {}
    publication_type = "Publicación"
    publication_date = ""
    return {
        "publication_id": publication_id,
        "publication_url": url,
        "publication_date": publication_date,
        "publication_type": publication_type,
        "publication_folder": _nombre_carpeta_publicacion(
            publication_id,
            publication_date,
            publication_type,
        ),
    }


def _entradas_navegacion(detail: dict) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for navigation_key in CLAVES_NAVEGACION_PUBLICACIONES:
        navigation = detail.get(navigation_key)
        if not isinstance(navigation, list):
            continue
        for raw in navigation:
            if not isinstance(raw, dict):
                continue
            publication_id = _identificador(raw.get("publicacioId"))
            if not publication_id:
                continue
            entries.append(
                {
                    "publication_id": publication_id,
                    "publication_date": str(raw.get("dataPublicacio") or "").strip(),
                    "navigation": navigation_key,
                }
            )
    return entries


def _extraer_documentos_de_detalle(
    detail: dict,
    api_url: str,
    *,
    provenance: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    old_publication = bool(detail.get("publicacioAntiga"))
    publication_id = detail.get("publicacioId")
    parsed_api = urlparse(api_url)
    origin = f"{parsed_api.scheme}://{parsed_api.netloc}"
    documents: list[dict[str, str]] = []
    seen: set[str] = set()

    def walk(value, section: str = "Documentacio") -> None:
        if isinstance(value, dict):
            title = value.get("titol")
            document_hash = value.get("hash")
            document_id = value.get("id")
            subtype = value.get("subtipusDocument")
            if title and document_hash and subtype in (None, 0):
                if old_publication and publication_id:
                    href = f"{origin}/portal-api/descarrega-document-antic/{publication_id}/{document_hash}"
                elif document_id:
                    href = f"{origin}/portal-api/descarrega-document/{document_id}/{document_hash}"
                else:
                    href = ""
                key = href.lower()
                if href and key not in seen:
                    seen.add(key)
                    published = str(value.get("dataPublicacio") or "")
                    documents.append(
                        {
                            "href": href,
                            "text": str(title),
                            "title": str(title),
                            "download": str(title),
                            "itemText": " ".join(part for part in (str(title), published) if part),
                            "section": section,
                            "fecha": fecha_desde_texto(published),
                        }
                    )
                    if provenance:
                        documents[-1].update(provenance)
                        document_identity = str(document_id or document_hash)
                        documents[-1]["remote_id"] = (
                            f"{provenance.get('publication_id', publication_id)}:"
                            f"{document_identity}"
                        )
                        documents[-1]["remote_hash"] = str(document_hash)
                        if not documents[-1]["fecha"]:
                            documents[-1]["fecha"] = provenance.get("publication_date", "")
            for child_key, child in value.items():
                walk(child, str(child_key or section))
        elif isinstance(value, list):
            for child in value:
                walk(child, section)

    walk(detail)
    return documents


def extraer_documentos_de_api(session, url: str) -> list[dict[str, str]]:
    """Extrae una publicación concreta; se conserva para compatibilidad."""

    api_url = url_api_detall_publicacion(url)
    if not api_url:
        return []
    detail = get_json(session, api_url, referer=url)
    if not isinstance(detail, dict):
        return []
    return _extraer_documentos_de_detalle(detail, api_url)


def extraer_inventario_documentos_de_api(session, url: str) -> CatalunyaDocumentInventory:
    """Recorre todas las publicaciones relacionadas sin deduplicar enlaces remotos."""

    initial_api_url = url_api_detall_publicacion(url)
    origin = origen_catalunya(url)
    identifiers = identificadores_publicacion(url)
    if not initial_api_url or not origin or not identifiers:
        raise CatalunyaStructureError("La URL de Catalunya no identifica una publicación válida.")

    initial_detail = get_json(session, initial_api_url, referer=url)
    if not isinstance(initial_detail, dict):
        raise CatalunyaStructureError("El detalle de la publicación no tiene el formato esperado.")

    expedient_id = _identificador(
        initial_detail.get("expedientId")
        or (identifiers[0] if len(identifiers) == 2 else "")
    )
    initial_publication_id = _identificador(
        initial_detail.get("publicacioId") or identifiers[-1]
    )
    if not expedient_id or not initial_publication_id:
        raise CatalunyaStructureError(
            "Catalunya no devolvió los identificadores necesarios para recorrer el expediente."
        )

    language = idioma_desde_url(url)
    details: dict[str, tuple[dict, str, str]] = {}
    date_hints: dict[str, str] = {}
    queued: set[str] = set()
    queue: list[str] = []
    errors: list[str] = []
    attempted_publications = 1

    def publication_url(publication_id: str) -> str:
        return (
            f"{origin}/{language}/detall-publicacio/"
            f"{expedient_id}/{publication_id}"
        )

    def enqueue_navigation(detail: dict) -> None:
        for entry in _entradas_navegacion(detail):
            publication_id = entry["publication_id"]
            if entry["publication_date"] and not date_hints.get(publication_id):
                date_hints[publication_id] = entry["publication_date"]
            if publication_id in details or publication_id in queued:
                continue
            queued.add(publication_id)
            queue.append(publication_id)

    canonical_initial_url = publication_url(initial_publication_id)
    details[initial_publication_id] = (
        initial_detail,
        initial_api_url,
        canonical_initial_url,
    )
    enqueue_navigation(initial_detail)

    while queue:
        if attempted_publications >= MAX_PUBLICACIONES_RELACIONADAS:
            errors.append(
                "Catalunya superó el límite seguro de publicaciones relacionadas "
                f"({MAX_PUBLICACIONES_RELACIONADAS})."
            )
            break
        publication_id = queue.pop(0)
        attempted_publications += 1
        detail_url = publication_url(publication_id)
        api_url = portal_api_url(
            origin,
            f"detall-publicacio-expedient/{expedient_id}/{publication_id}",
        )
        try:
            detail = get_json(session, api_url, referer=detail_url)
        except Exception as exc:
            errors.append(
                f"No se pudo consultar la publicación {publication_id}: {exc}"
            )
            continue
        if not isinstance(detail, dict):
            errors.append(
                f"La publicación {publication_id} no devolvió un detalle estructurado."
            )
            continue
        returned_expedient_id = _identificador(detail.get("expedientId"))
        returned_publication_id = _identificador(
            detail.get("publicacioId") or publication_id
        )
        if returned_expedient_id != expedient_id:
            errors.append(
                f"La publicación {publication_id} pertenece a otro expediente."
            )
            continue
        if returned_publication_id != publication_id:
            errors.append(
                f"Catalunya devolvió otra publicación al consultar {publication_id}."
            )
            continue
        details[publication_id] = (detail, api_url, detail_url)
        enqueue_navigation(detail)

    def sort_key(item: tuple[str, tuple[dict, str, str]]) -> tuple[str, int, str]:
        publication_id, (detail, _api_url, _detail_url) = item
        publication_date = _fecha_publicacion_detalle(
            detail,
            date_hints.get(publication_id, ""),
        )
        numeric_id = int(publication_id) if publication_id.isdigit() else 0
        return publication_date or "9999", numeric_id, publication_id

    links: list[dict[str, str]] = []
    publication_ids: list[str] = []
    publications: list[dict[str, str]] = []
    for publication_id, (detail, api_url, detail_url) in sorted(
        details.items(),
        key=sort_key,
    ):
        publication_ids.append(publication_id)
        publication_date = _fecha_publicacion_detalle(
            detail,
            date_hints.get(publication_id, ""),
        )
        publication_type = _tipo_publicacion_detalle(detail)
        publication_folder = _nombre_carpeta_publicacion(
            publication_id,
            publication_date,
            publication_type,
        )
        publication = {
            "publication_id": publication_id,
            "publication_url": detail_url,
            "publication_date": publication_date,
            "publication_type": publication_type,
            "publication_folder": publication_folder,
        }
        publications.append(publication)
        links.extend(
            _extraer_documentos_de_detalle(
                detail,
                api_url,
                provenance=publication,
            )
        )
    return CatalunyaDocumentInventory(
        links=links,
        publication_ids=publication_ids,
        publications=publications,
        errors=errors,
    )


def nombre_logico_desde_enlace(enlace: dict, indice: int) -> str:
    for key in ("download", "text", "title"):
        value = enlace.get(key, "")
        if value and not es_texto_generico(value):
            return limpiar_titulo_documento(value)
    item_text = enlace.get("itemText", "")
    if item_text:
        candidates = [
            limpiar_titulo_documento(part)
            for part in re.split(r"\s{2,}|[:|]", item_text)
        ]
        candidates = [item for item in candidates if item and not es_texto_generico(item)]
        if candidates:
            return max(candidates, key=len)
    url_name = os.path.basename(urlparse(enlace.get("href", "")).path)
    if url_name and not es_texto_generico(url_name):
        return limpiar_titulo_documento(url_name)
    return f"documento_{indice}"


def extraer_documentos_de_html(html: str, url_base: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    documents: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(href, link_text="", title="", download="", item_text="", section="Documentacio"):
        absolute = urljoin(url_base, href)
        if not es_enlace_documento(absolute) or absolute.lower() in seen:
            return
        seen.add(absolute.lower())
        documents.append(
            {
                "href": absolute,
                "text": link_text,
                "title": title,
                "download": download,
                "itemText": item_text or link_text,
                "section": section,
                "fecha": fecha_desde_texto(item_text or link_text),
            }
        )

    for link in soup.find_all("a", href=True):
        link_text = link.get_text(" ", strip=True)
        parent = link.find_parent(["li", "tr", "div", "section", "article"])
        item_text = parent.get_text(" ", strip=True) if parent else link_text
        add(link["href"], link_text, link.get("title", ""), link.get("download", ""), item_text)
    pattern = re.compile(
        r'(?:https?://[^"\'\s<>]+)?/portal-api/descarrega-document(?:-antic)?/[^"\'\s<>]+',
        re.IGNORECASE,
    )
    for tag in soup.find_all(True):
        attributes = " ".join(
            " ".join(map(str, value)) if isinstance(value, list) else str(value)
            for value in tag.attrs.values()
        )
        if "descarrega-document" not in attributes:
            continue
        for href in pattern.findall(attributes):
            link_text = tag.get_text(" ", strip=True) or tag.get("title", "") or tag.get("aria-label", "")
            parent = tag.find_parent(["li", "tr", "div", "section", "article"])
            item_text = parent.get_text(" ", strip=True) if parent else link_text
            add(href, link_text, tag.get("title", "") or tag.get("aria-label", ""), "", item_text if len(item_text) <= 350 else link_text)
    return documents


def obtener_documento_remoto(session, url: str, nombre_logico: str, referer: str) -> RemoteDocument:
    response = session.get(
        url,
        timeout=TIMEOUT_DESCARGA,
        allow_redirects=True,
        headers={"Referer": referer},
    )
    response.raise_for_status()
    return RemoteDocument(
        source_url=url,
        content=response.content,
        logical_name=nombre_logico,
        content_type=response.headers.get("Content-Type", ""),
        content_disposition=response.headers.get("Content-Disposition", ""),
        platform="CATALUNYA",
    )


def guardar_documento_remoto(document: RemoteDocument, destination: Path):
    extension = detect_document_extension(document)
    filename = construir_nombre_desde_remoto(document, extension)
    return write_bytes_content_aware(destination, filename, document.content), extension


def construir_nombre_desde_remoto(document: RemoteDocument, extension: str) -> str:
    class ResponseAdapter:
        content = document.content
        headers = {
            "Content-Type": document.content_type,
            "Content-Disposition": document.content_disposition,
        }

    return construir_nombre_archivo(
        ResponseAdapter(),
        document.logical_name,
        document.source_url,
        extension,
    )


def descargar_documento(session, url: str, nombre_logico: str, carpeta_destino, referer: str):
    document = obtener_documento_remoto(session, url, nombre_logico, referer)
    written, _extension = guardar_documento_remoto(document, Path(carpeta_destino))
    name = written.path.name if written.path else construir_nombre_desde_remoto(
        document,
        detect_document_extension(document),
    )
    return ("descargado" if written.written else "omitido"), name


def preparar_carpetas_publicaciones(
    publications: list[dict[str, str]],
    destination: Path,
) -> DocumentDownloadResult:
    """Crea una carpeta estable por publicación y la expone al monitor."""

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    result = DocumentDownloadResult(platform="CATALUNYA", successful=True)
    for publication in publications:
        publication_id = str(publication.get("publication_id") or "")
        folder_name = str(publication.get("publication_folder") or "")
        publication_type = str(publication.get("publication_type") or "Publicación")
        if not publication_id or not folder_name:
            result.errors.append("Catalunya devolvió una publicación sin carpeta identificable.")
            continue
        folder_path = ensure_safe_child(destination, destination / folder_name)
        try:
            existed = folder_path.is_dir()
            if folder_path.exists() and not existed:
                raise SafeFileError(
                    f"El destino de la publicación {publication_id} no es una carpeta."
                )
            folder_path.mkdir(parents=True, exist_ok=True)
            artifact = DownloadedDocument(
                source_url=str(publication.get("publication_url") or ""),
                path=folder_path,
                filename=f"{publication_type} — carpeta «{folder_name}»",
                extension="",
                role="publication",
                remote_id=f"publication:{publication_id}",
                section=publication_type,
                published_at=str(publication.get("publication_date") or ""),
            )
            (result.skipped if existed else result.downloaded).append(artifact)
        except Exception as exc:
            result.errors.append(f"Publicación {publication_id}: {exc}")
            result.failed.append(
                {
                    "name": f"{publication_type} — carpeta «{folder_name}»",
                    "source_url": str(publication.get("publication_url") or ""),
                    "remote_id": f"publication:{publication_id}",
                    "role": "publication",
                    "section": publication_type,
                    "published_at": str(publication.get("publication_date") or ""),
                }
            )
    result.successful = not result.errors
    return result


def descargar_enlaces(session, links: list[dict], destination: Path, referer: str) -> DocumentDownloadResult:
    result = DocumentDownloadResult(platform="CATALUNYA", successful=True)
    observed_paths: set[str] = set()
    for index, link in enumerate(links, start=1):
        logical_name = nombre_logico_desde_enlace(link, index)
        if extension_desde_texto(link.get("itemText", "")) and not extension_desde_nombre(logical_name):
            logical_name += extension_desde_texto(link.get("itemText", ""))
        try:
            link_referer = str(link.get("publication_url") or referer)
            remote = obtener_documento_remoto(session, link["href"], logical_name, link_referer)
            publication_folder = str(link.get("publication_folder") or "")
            link_destination = (
                ensure_safe_child(destination, destination / publication_folder)
                if publication_folder
                else destination
            )
            link_destination.mkdir(parents=True, exist_ok=True)
            written, extension = guardar_documento_remoto(remote, link_destination)
            document_path = written.path or link_destination / logical_name
            path_identity = os.path.normcase(str(document_path.resolve(strict=False)))
            if path_identity in observed_paths:
                continue
            observed_paths.add(path_identity)
            downloaded = DownloadedDocument(
                source_url=remote.source_url,
                path=document_path,
                filename=document_path.name,
                extension=extension,
                sha256=written.sha256,
                role="document",
                remote_id=str(link.get("remote_id") or ""),
                section=str(link.get("publication_type") or link.get("section") or ""),
                published_at=str(link.get("fecha") or ""),
            )
            if written.written and written.path:
                result.downloaded.append(downloaded)
            else:
                result.skipped.append(downloaded)
        except Exception as exc:
            # El resultado parcial conserva el resto de documentos y expone el error.
            result.errors.append(f"{logical_name}: {exc}")
            result.failed.append(
                {
                    "name": logical_name,
                    "source_url": str(link.get("href") or ""),
                    "remote_id": str(link.get("remote_id") or ""),
                    "section": str(
                        link.get("publication_type") or link.get("section") or ""
                    ),
                    "published_at": str(link.get("fecha") or ""),
                }
            )
    result.found = len(result.downloaded) + len(result.skipped) + len(result.failed)
    result.successful = not result.errors
    return result
