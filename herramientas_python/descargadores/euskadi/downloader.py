"""Coordinador del descargador de Euskadi."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from ..common.run_result import DownloadArtifact, DownloadRunResult, PlatformCapabilities, utc_now_iso
from ..common.safe_files import sha256_file
from .client import (
    TIMEOUT_DESCARGA,
    crear_session,
    extraer_documentos,
    extraer_expediente,
    extraer_ficha_pdf,
    extraer_paquetes_modelos,
)
from .documents import descargar_documento


EUSKADI_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)


def run_euskadi(
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
        logger(f"Accediendo a Euskadi: {url}")
        response = session.get(url, timeout=TIMEOUT_DESCARGA, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        expediente = extraer_expediente(soup)
        trabajos = []
        ficha = extraer_ficha_pdf(soup, response.url or url, expediente)
        if ficha:
            trabajos.append(ficha)
        trabajos.extend(extraer_documentos(soup))
        trabajos.extend(extraer_paquetes_modelos(soup, expediente))
        if not trabajos:
            raise ValueError("No se han encontrado documentos para descargar.")
    except Exception as exc:
        return DownloadRunResult.failed(
            platform="EUSKADI",
            tender_id=locals().get("expediente", ""),
            source_url=url,
            capabilities=EUSKADI_CAPABILITIES,
            error=exc,
            started_at=started,
        )

    logger(f"Documentos encontrados: {len(trabajos)}")
    artifacts = []
    errors = []
    referer = response.url or url
    for index, trabajo in enumerate(trabajos, 1):
        logger(f"\n[{index}/{len(trabajos)}] {trabajo['nombre_logico']}")
        try:
            try:
                estado, nombre = download_document(
                    session, trabajo, str(destination), referer, logger=logger
                )
            except TypeError as exc:
                if "logger" not in str(exc):
                    raise
                estado, nombre = download_document(session, trabajo, str(destination), referer)
            path = destination / nombre
            artifact_status = {
                "descargado": "created",
                "actualizado": "modified",
                "omitido": "reused",
            }.get(estado, "reused")
            artifacts.append(
                DownloadArtifact(
                    name=nombre,
                    status=artifact_status,
                    source_url=trabajo["url"],
                    path=str(path) if path.exists() else "",
                    sha256=sha256_file(path) if path.is_file() else "",
                    remote_id=str(trabajo.get("remote_id") or ""),
                    section=str(trabajo.get("section") or ""),
                    role=str(trabajo.get("role") or "document"),
                )
            )
        except Exception as exc:
            artifacts.append(
                DownloadArtifact(
                    name=str(trabajo.get("nombre_logico") or f"documento_{index}"),
                    status="failed",
                    source_url=str(trabajo.get("url") or ""),
                    remote_id=str(trabajo.get("remote_id") or ""),
                    section=str(trabajo.get("section") or ""),
                    role=str(trabajo.get("role") or "document"),
                )
            )
            errors.append(f"{trabajo['nombre_logico']}: {exc}")
            logger(f"Error descargando este enlace: {exc}")

    downloaded = sum(item.status == "created" for item in artifacts)
    modified = sum(item.status == "modified" for item in artifacts)
    skipped = sum(item.status == "reused" for item in artifacts)
    useful = downloaded + modified + skipped
    status = "partial" if errors and useful else "failed" if errors else "success"
    logger(
        f"\nDescarga terminada: {downloaded} documento(s) nuevo(s), "
        f"{modified} actualizado(s), "
        f"{skipped} omitido(s), {len(errors)} error(es)."
    )
    return DownloadRunResult(
        platform="EUSKADI",
        tender_id=expediente,
        source_url=url,
        started_at=started,
        finished_at=utc_now_iso(),
        status=status,
        capabilities=EUSKADI_CAPABILITIES,
        changes_detected=downloaded + modified > 0,
        documents_found=len(trabajos),
        documents_downloaded=downloaded + modified,
        documents_new=downloaded,
        documents_modified=modified,
        artifacts=artifacts,
        files_created=[
            item.path for item in artifacts if item.status in {"created", "modified"} and item.path
        ],
        files_reused=[item.path for item in artifacts if item.status == "reused" and item.path],
        recoverable_issues=errors,
        error="; ".join(errors) if status == "failed" else "",
        block_completeness={
            "documents": "invalid" if status == "failed" else "partial" if errors else "complete"
        },
    )
