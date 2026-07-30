"""Adaptador documental de la Plataforma de Contratación Pública de Euskadi."""

from .downloader import EUSKADI_CAPABILITIES, run_euskadi

__all__ = ["EUSKADI_CAPABILITIES", "run_euskadi"]

