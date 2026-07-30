"""Coordinador del descargador de Comunidad de Madrid."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from ..common.run_result import DownloadArtifact, DownloadRunResult, PlatformCapabilities, utc_now_iso
from ..common.safe_files import sha256_file
from .client import (
    TIMEOUT_DESCARGA,
    crear_session,
    extraer_adjuntos,
    extraer_enlace_ficha_pdf,
    extraer_numero_expediente,
)
from .documents import descargar_documento


MADRID_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)


def run_madrid(
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
    try:
        logger(f"Accediendo a Comunidad de Madrid: {url}")
        response = session.get(url, timeout=TIMEOUT_DESCARGA)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        expediente = extraer_numero_expediente(soup)
        ficha_pdf = extraer_enlace_ficha_pdf(soup, url, response.text)
        adjuntos = extraer_adjuntos(soup, url)
        trabajos = []
        if ficha_pdf:
            trabajos.append(
                {
                    "url": ficha_pdf,
                    "nombre_logico": (f"Ficha expediente {expediente}" if expediente else "Ficha expediente") + ".pdf",
                }
            )
        trabajos.extend(item for item in adjuntos if item["url"] != ficha_pdf)
        if not trabajos:
            raise ValueError("No se han encontrado documentos internos para descargar.")
    except Exception as exc:
        return DownloadRunResult.failed(
            platform="COMUNIDAD_MADRID",
            tender_id=locals().get("expediente", ""),
            source_url=url,
            capabilities=MADRID_CAPABILITIES,
            error=exc,
            started_at=started,
        )

    logger(f"Documentos internos encontrados: {len(trabajos)}")
    artifacts = []
    errors = []
    for index, trabajo in enumerate(trabajos, 1):
        logger(f"\n[{index}/{len(trabajos)}] {trabajo['nombre_logico']}")
        try:
            try:
                estado, nombre = download_document(
                    session,
                    trabajo["url"],
                    trabajo["nombre_logico"],
                    str(destination),
                    url,
                    logger=logger,
                )
            except TypeError as exc:
                if "logger" not in str(exc):
                    raise
                estado, nombre = download_document(
                    session, trabajo["url"], trabajo["nombre_logico"], str(destination), url
                )
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
    status = "partial" if errors and artifacts else "failed" if errors else "success"
    logger(
        f"\nDescarga terminada: {downloaded} documento(s) descargado(s), "
        f"{skipped} omitido(s), {len(errors)} error(es)."
    )
    return DownloadRunResult(
        platform="COMUNIDAD_MADRID",
        tender_id=expediente,
        source_url=url,
        started_at=started,
        finished_at=utc_now_iso(),
        status=status,
        capabilities=MADRID_CAPABILITIES,
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
