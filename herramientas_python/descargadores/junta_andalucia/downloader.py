"""Coordinación del descargador de Junta de Andalucía."""

from __future__ import annotations

import tempfile
import shutil
import time
from pathlib import Path

from ..common.run_result import DownloadArtifact, DownloadRunResult, PlatformCapabilities, utc_now_iso
from ..common.safe_files import sha256_file, write_bytes_if_absent
from . import browser as platform_browser


JUNTA_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)
MAX_NAVIGATION_ATTEMPTS = 3


def run_junta_andalucia(
    url: str,
    destination: Path,
    *,
    incluir_sellos: bool = False,
    browser_api=platform_browser,
    logger=print,
    started_at: str | None = None,
) -> DownloadRunResult:
    started = started_at or utc_now_iso()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    proceso = perfil_temporal = browser = page = None
    click_directory = ""
    artifacts = []
    errors = []
    phase = "browser_start"

    try:
        logger("Abriendo Chrome en segundo plano...")
        proceso, perfil_temporal, browser, port = browser_api.abrir_chrome()
        click_directory = tempfile.mkdtemp(prefix="llangon-junta-download-")
        phase = "page_creation"
        page = browser_api.crear_pagina(browser, port, click_directory)
        navigation_url = (
            browser_api.normalizar_url_licitacion(url)
            if hasattr(browser_api, "normalizar_url_licitacion")
            else url
        )
        if navigation_url != url:
            logger(f"Usando la dirección actual del portal: {navigation_url}")
        logger("Cargando licitacion...")
        phase = "initial_navigation"
        last_navigation_error = None
        for navigation_attempt in range(1, MAX_NAVIGATION_ATTEMPTS + 1):
            if navigation_attempt > 1:
                logger(
                    "La ficha no se cargó completamente; "
                    f"reintentando navegación ({navigation_attempt}/{MAX_NAVIGATION_ATTEMPTS})..."
                )
                if hasattr(browser_api, "preparar_reintento_navegacion"):
                    browser_api.preparar_reintento_navegacion(page)
            try:
                phase = "initial_navigation"
                if hasattr(browser_api, "navegar_a_licitacion"):
                    browser_api.navegar_a_licitacion(page, navigation_url)
                else:
                    page.call("Page.navigate", {"url": navigation_url}, timeout=25)
                phase = "document_sections"
                try:
                    browser_api.esperar_documentacion_complementaria(page, logger=logger)
                except TypeError as exc:
                    if "logger" not in str(exc):
                        raise
                    browser_api.esperar_documentacion_complementaria(page)
                last_navigation_error = None
                break
            except Exception as exc:
                last_navigation_error = exc
                if navigation_attempt == MAX_NAVIGATION_ATTEMPTS:
                    raise
        if last_navigation_error:
            raise last_navigation_error
        logger("Localizando enlaces de Documentacion complementaria y Anuncios publicados...")
        enlaces = browser_api.extraer_enlaces(page, incluir_sellos)
        if not enlaces:
            raise ValueError(
                "No se han encontrado enlaces dentro de Documentacion complementaria "
                "ni Anuncios publicados."
            )
        if incluir_sellos:
            logger(f"Enlaces encontrados: {len(enlaces)}")
        else:
            logger(f"Documentos encontrados: {len(enlaces)} (sellos de tiempo excluidos)")
        session = browser_api.crear_session_descarga(page, navigation_url)

        for index, enlace in enumerate(enlaces, 1):
            text = browser_api.limpiar_nombre(
                enlace.get("text") or enlace.get("title") or f"documento_{index}"
            )
            logger(f"\n[{index}/{len(enlaces)}] {text}")
            try:
                if browser_api.href_descargable(enlace.get("href", "")):
                    nombre, omitido = browser_api.descargar_por_url(
                        session, enlace, str(destination), navigation_url
                    )
                else:
                    nombre_temporal, _ = browser_api.descargar_por_click(
                        page, enlace, click_directory
                    )
                    if not nombre_temporal:
                        raise RuntimeError("No se pudo confirmar la descarga de este enlace.")
                    source = Path(click_directory) / nombre_temporal
                    if not source.is_file():
                        raise RuntimeError("Chrome no publicó el archivo descargado esperado.")
                    safe = write_bytes_if_absent(destination, nombre_temporal, source.read_bytes())
                    nombre, omitido = nombre_temporal, safe.skipped

                path = destination / nombre
                status = "reused" if omitido else "created"
                artifacts.append(
                    DownloadArtifact(
                        name=nombre,
                        status=status,
                        source_url=str(enlace.get("href") or ""),
                        path=str(path) if path.exists() else "",
                        sha256=sha256_file(path) if path.is_file() else "",
                        size=path.stat().st_size if path.is_file() else 0,
                        section=str(enlace.get("section") or ""),
                    )
                )
                logger(f"Omitido, ya existe: {nombre}" if omitido else f"Guardado como: {nombre}")
            except Exception as exc:
                artifacts.append(
                    DownloadArtifact(
                        name=text,
                        status="failed",
                        source_url=str(enlace.get("href") or ""),
                    )
                )
                errors.append(f"{text}: {exc}")
                logger(f"Error descargando este enlace: {exc}")
    except Exception as exc:
        logger(f"Error Junta en fase {phase}: {type(exc).__name__}: {exc}")
        error_code, retryable = (
            browser_api.error_metadata(exc)
            if hasattr(browser_api, "error_metadata")
            else ("JUNTA_DOWNLOAD_FAILED", False)
        )
        return DownloadRunResult.failed(
            platform="JUNTA_ANDALUCIA",
            source_url=url,
            capabilities=JUNTA_CAPABILITIES,
            error=exc,
            error_code=error_code,
            retryable=retryable,
            started_at=started,
            artifacts=artifacts,
            files_created=[item.path for item in artifacts if item.status == "created" and item.path],
            files_reused=[item.path for item in artifacts if item.status == "reused" and item.path],
            documents_found=len(artifacts),
            documents_downloaded=sum(item.status == "created" for item in artifacts),
        )
    finally:
        if proceso and perfil_temporal:
            browser_api.cerrar_chrome(proceso, perfil_temporal, browser, page)
        if click_directory:
            for cleanup_attempt in range(6):
                try:
                    shutil.rmtree(click_directory)
                    break
                except FileNotFoundError:
                    break
                except OSError as exc:
                    if cleanup_attempt == 5:
                        logger(f"Aviso: no se pudo limpiar el temporal de descarga: {exc}")
                    else:
                        time.sleep(0.5)

    downloaded = sum(item.status == "created" for item in artifacts)
    skipped = sum(item.status == "reused" for item in artifacts)
    status = "partial" if errors and artifacts else "failed" if errors else "success"
    logger(
        f"\nDescarga terminada: {downloaded} documento(s) descargado(s), "
        f"{skipped} omitido(s), {len(errors)} error(es)."
    )
    return DownloadRunResult(
        platform="JUNTA_ANDALUCIA",
        source_url=url,
        started_at=started,
        finished_at=utc_now_iso(),
        status=status,
        capabilities=JUNTA_CAPABILITIES,
        changes_detected=downloaded > 0,
        documents_found=len(artifacts),
        documents_downloaded=downloaded,
        documents_new=downloaded,
        artifacts=artifacts,
        files_created=[item.path for item in artifacts if item.status == "created" and item.path],
        files_reused=[item.path for item in artifacts if item.status == "reused" and item.path],
        recoverable_issues=errors,
        error="; ".join(errors) if status == "failed" else "",
        block_completeness={"documents": "partial" if errors else "complete"},
    )
