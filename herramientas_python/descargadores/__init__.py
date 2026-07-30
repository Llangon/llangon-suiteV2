"""Componentes reutilizables de los descargadores de licitaciones."""
from .registry import DOWNLOADER_SPECS, get_downloader_spec, run_downloader

__all__ = ["DOWNLOADER_SPECS", "get_downloader_spec", "run_downloader"]
