"""Adaptador documental del Portal de Contratación de Navarra y PLENA."""

from .downloader import NAVARRA_CAPABILITIES, run_navarra

__all__ = ["NAVARRA_CAPABILITIES", "run_navarra"]

