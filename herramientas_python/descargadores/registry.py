"""Registro mínimo de coordinadores para la Suite y el futuro monitor."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable

from .common.run_result import DownloadRunResult, PlatformCapabilities


@dataclass(frozen=True)
class DownloaderSpec:
    platform: str
    facade: str
    module: str
    callable_name: str
    capabilities: PlatformCapabilities

    def load_runner(self) -> Callable[..., DownloadRunResult]:
        runner = getattr(import_module(self.module), self.callable_name)
        if not callable(runner):
            raise TypeError(f"El coordinador {self.platform} no es invocable.")
        return runner


QUESTION_CAPABILITIES = PlatformCapabilities(
    documents=True,
    questions_and_answers=True,
    document_history=True,
    question_attachments=True,
)
DOCUMENT_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)


DOWNLOADER_SPECS = {
    "PLACE": DownloaderSpec(
        "PLACE",
        "Descargar_PLACE.py",
        "herramientas_python.descargadores.place.downloader",
        "run_place",
        QUESTION_CAPABILITIES,
    ),
    "CATALUNYA": DownloaderSpec(
        "CATALUNYA",
        "Descargar_Catalunya.py",
        "herramientas_python.descargadores.catalunya.downloader",
        "run_catalunya",
        QUESTION_CAPABILITIES,
    ),
    "NAVARRA": DownloaderSpec(
        "NAVARRA",
        "Descargar_Navarra.py",
        "herramientas_python.descargadores.navarra.downloader",
        "run_navarra",
        DOCUMENT_CAPABILITIES,
    ),
    "EUSKADI": DownloaderSpec(
        "EUSKADI",
        "Descargar_Euskadi.py",
        "herramientas_python.descargadores.euskadi.downloader",
        "run_euskadi",
        DOCUMENT_CAPABILITIES,
    ),
    "COMUNIDAD_MADRID": DownloaderSpec(
        "COMUNIDAD_MADRID",
        "Descargar_ComunidadMadrid.py",
        "herramientas_python.descargadores.madrid.downloader",
        "run_madrid",
        DOCUMENT_CAPABILITIES,
    ),
    "JUNTA_ANDALUCIA": DownloaderSpec(
        "JUNTA_ANDALUCIA",
        "Descargar_JuntaAndalucia.py",
        "herramientas_python.descargadores.junta_andalucia.downloader",
        "run_junta_andalucia",
        DOCUMENT_CAPABILITIES,
    ),
    "XUNTA_DE_GALICIA": DownloaderSpec(
        "XUNTA_DE_GALICIA",
        "Descargar_XuntaGalicia.py",
        "herramientas_python.descargadores.xunta_galicia.downloader",
        "run_xunta_galicia",
        DOCUMENT_CAPABILITIES,
    ),
}


PLATFORM_ALIASES = {
    "COMUNIDAD MADRID": "COMUNIDAD_MADRID",
    "MADRID": "COMUNIDAD_MADRID",
    "JUNTA ANDALUCIA": "JUNTA_ANDALUCIA",
    "JUNTA DE ANDALUCIA": "JUNTA_ANDALUCIA",
    "XUNTA GALICIA": "XUNTA_DE_GALICIA",
    "GALICIA": "XUNTA_DE_GALICIA",
    "CONTRATOS DE GALICIA": "XUNTA_DE_GALICIA",
}


def normalize_platform(value: object) -> str:
    platform = str(value or "").strip().upper().replace("Á", "A").replace("Í", "I")
    platform = " ".join(platform.replace("_", " ").split())
    return PLATFORM_ALIASES.get(platform, platform.replace(" ", "_"))


def get_downloader_spec(platform: object) -> DownloaderSpec:
    key = normalize_platform(platform)
    try:
        return DOWNLOADER_SPECS[key]
    except KeyError as exc:
        raise ValueError(f"Plataforma no registrada: {platform}") from exc


def run_downloader(
    platform: object,
    source_url: str,
    destination: str | Path,
    **options,
) -> DownloadRunResult:
    """Ejecuta un coordinador interno; no pasa por subprocess ni por una fachada CLI."""

    spec = get_downloader_spec(platform)
    result = spec.load_runner()(source_url, Path(destination), **options)
    if not isinstance(result, DownloadRunResult):
        raise TypeError(f"El coordinador {spec.platform} no devolvió DownloadRunResult.")
    return result
