from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPOSITORY_ROOT / "docs"


def test_dangerous_checkpoints_are_documented() -> None:
    text = (DOCS_ROOT / "CHECKPOINTS_PELIGROSOS.md").read_text(encoding="utf-8")

    for topic in (
        "SQLite",
        "migraciones",
        "CSRF global",
        "StorageBackend",
        "noticias Markdown",
        "refactor de `app.py`",
    ):
        assert topic in text


def test_dangerous_checkpoint_doc_requires_verification_and_local_commit() -> None:
    text = (DOCS_ROOT / "CHECKPOINTS_PELIGROSOS.md").read_text(encoding="utf-8")

    for command in (
        "git status --short --untracked-files=all",
        "python -m compileall webapp herramientas_python",
        "python -m pytest -q",
        "node --check webapp/infonalia_webapp/static/app.js",
        "node --check webapp/infonalia_webapp/static/login.js",
        "node --check webapp/infonalia_webapp/static/public.js",
        "node --check firebase/public_firebase/static/public.js",
        "git diff --check",
    ):
        assert command in text

    assert "No hacer push" in text
    assert "Crear commit local" in text
    assert "no usar datos reales" in text.lower()
