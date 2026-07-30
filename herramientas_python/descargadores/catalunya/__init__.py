"""Adaptador específico de la Plataforma de Contractació Pública de Catalunya."""

from __future__ import annotations

from ..common.question_state import QuestionStateLayout


CATALUNYA_STATE_LAYOUT = QuestionStateLayout(
    directory_name=".llangon-catalunya",
    platform="CATALUNYA",
    source_id_key="source_id",
    inventory_legacy_rtf=False,
)


def run_catalunya(*args, **kwargs):
    from .downloader import run_catalunya as run

    return run(*args, **kwargs)
