"""Coordinación neutral del descargador de Navarra."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..common.run_result import (
    DownloadArtifact,
    DownloadRunResult,
    PlatformCapabilities,
    utc_now_iso,
)
from ..common.safe_files import sha256_file
from .client import (
    RUTA_DETALLE_PCN,
    TIMEOUT_DESCARGA,
    consultar_plena,
    crear_session,
    eliminar_duplicados,
    es_url_pcn,
    es_url_plena,
    extraer_codigo_anuncio,
    extraer_documentos_pcn,
    extraer_url_plena,
    url_plena_para_codigo,
)
from .documents import descargar_documento


NAVARRA_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)


def run_navarra(
    url: str,
    destination: Path,
    *,
    session=None,
    download_document=None,
    logger=print,
    started_at: str | None = None,
) -> DownloadRunResult:
    started = started_at or utc_now_iso()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    session = session or crear_session()
    download_document = download_document or descargar_documento
    trabajos = []
    codigo = extraer_codigo_anuncio(url)
    url_plena = url if es_url_plena(url) else ""

    try:
        if es_url_pcn(url):
            if urlparse(url).path.lower() != RUTA_DETALLE_PCN:
                raise ValueError("La URL de Navarra no corresponde a una ficha de licitacion admitida.")
            logger(f"Accediendo al Portal de Contratacion de Navarra: {url}")
            respuesta = session.get(url, timeout=TIMEOUT_DESCARGA, allow_redirects=True)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.content, "html.parser")
            trabajos.extend(extraer_documentos_pcn(soup, respuesta.url or url))
            url_plena = extraer_url_plena(soup, respuesta.url or url) or url_plena
            codigo = codigo or extraer_codigo_anuncio(url_plena)
        elif not es_url_plena(url):
            raise ValueError("La URL no pertenece al Portal de Contratacion de Navarra ni a PLENA.")
        if not codigo:
            raise ValueError("No se ha podido obtener el codigo de anuncio de Navarra.")
        url_plena = url_plena or url_plena_para_codigo(codigo)
        logger(f"Consultando documentacion publica en PLENA: {url_plena}")
        pliegos_plena, documentos_adicionales = consultar_plena(session, codigo, url_plena)
        trabajos.extend(pliegos_plena)
        trabajos.extend(documentos_adicionales)
    except Exception as exc:
        return DownloadRunResult.failed(
            platform="NAVARRA",
            tender_id=codigo,
            source_url=url,
            capabilities=NAVARRA_CAPABILITIES,
            error=exc,
            started_at=started,
        )

    trabajos = eliminar_duplicados(trabajos)
    if not trabajos:
        return DownloadRunResult.failed(
            platform="NAVARRA",
            tender_id=codigo,
            source_url=url,
            capabilities=NAVARRA_CAPABILITIES,
            error="No se han encontrado documentos publicos para descargar.",
            started_at=started,
        )

    logger(f"Documentos publicos encontrados: {len(trabajos)}")
    artifacts = []
    errors = []
    for index, trabajo in enumerate(trabajos, 1):
        logger(f"\n[{index}/{len(trabajos)}] {trabajo['nombre_logico']} ({trabajo['origen']})")
        try:
            try:
                estado, nombre = download_document(
                    session,
                    trabajo,
                    str(destination),
                    url_plena,
                    logger=logger,
                )
            except TypeError as exc:
                if "logger" not in str(exc):
                    raise
                estado, nombre = download_document(session, trabajo, str(destination), url_plena)
            path = destination / nombre
            artifacts.append(
                DownloadArtifact(
                    name=nombre,
                    status="created" if estado == "descargado" else "reused",
                    source_url=trabajo["url"],
                    path=str(path) if path.exists() else "",
                    sha256=sha256_file(path) if path.is_file() else "",
                )
            )
        except Exception as exc:
            artifacts.append(
                DownloadArtifact(
                    name=str(trabajo.get("nombre_logico") or f"documento_{index}"),
                    status="failed",
                    source_url=str(trabajo.get("url") or ""),
                )
            )
            errors.append(f"{trabajo['nombre_logico']}: {exc}")
            logger(f"Error descargando este enlace: {exc}")

    downloaded = sum(item.status == "created" for item in artifacts)
    skipped = sum(item.status == "reused" for item in artifacts)
    if errors and artifacts:
        status = "partial"
    elif errors:
        status = "failed"
    else:
        status = "success"
    logger(
        f"\nDescarga terminada: {downloaded} documento(s) descargado(s), "
        f"{skipped} omitido(s), {len(errors)} error(es)."
    )
    return DownloadRunResult(
        platform="NAVARRA",
        tender_id=codigo,
        source_url=url,
        started_at=started,
        finished_at=utc_now_iso(),
        status=status,
        capabilities=NAVARRA_CAPABILITIES,
        changes_detected=downloaded > 0,
        documents_found=len(trabajos),
        documents_downloaded=downloaded,
        documents_new=downloaded,
        artifacts=artifacts,
        files_created=[item.path for item in artifacts if item.status == "created" and item.path],
        files_reused=[item.path for item in artifacts if item.status == "reused" and item.path],
        recoverable_issues=errors,
        error="; ".join(errors) if status == "failed" else "",
        block_completeness={"documents": "partial" if errors else "complete"},
    )
