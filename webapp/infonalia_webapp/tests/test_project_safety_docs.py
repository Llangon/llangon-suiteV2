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


def test_storagebackend_precheck_documents_current_download_flow() -> None:
    text = (DOCS_ROOT / "PRECHECK_STORAGEBACKEND.md").read_text(encoding="utf-8")

    for item in (
        "api_download_licitacion()",
        "resolve_destination_folder()",
        "write_http_url()",
        "validate_resolved_destination()",
        "validate_download_folder_limits()",
        "subprocess.run()",
        "DOWNLOAD_ROOT",
        "LAUNCHER_PATH",
        "MAX_DOWNLOAD_RUNTIME_SECONDS",
        "ruta_carpeta",
        "HTTP.url",
    ):
        assert item in text


def test_storagebackend_precheck_keeps_implementation_out_of_scope() -> None:
    text = (DOCS_ROOT / "PRECHECK_STORAGEBACKEND.md").read_text(encoding="utf-8")

    for item in (
        "No se implementa `StorageBackend`",
        "No se implementa Dropbox",
        "No se crea `DownloadJob`",
        "No se cambia SQLite",
        "No se toca `api_download_licitacion()`",
        "No se ejecutan descargadores reales",
    ):
        assert item in text
