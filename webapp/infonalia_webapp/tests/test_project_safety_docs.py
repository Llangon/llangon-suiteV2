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


def test_markdown_news_precheck_documents_current_news_flow() -> None:
    text = (DOCS_ROOT / "PRECHECK_NOTICIAS_MARKDOWN.md").read_text(encoding="utf-8")

    for item in (
        "noticias",
        "title",
        "slug",
        "content",
        "featured_image",
        "api_public_news()",
        "api_create_news()",
        "api_update_news()",
        "GET /api/public/noticias",
        "POST /api/news",
        "PATCH /api/news/{id}",
        "DELETE /api/news/{id}",
        "public.js",
        "escapeHtml()",
        "NewsRenderer",
        "NewsArticle",
    ):
        assert item in text


def test_markdown_news_precheck_keeps_implementation_out_of_scope() -> None:
    text = (DOCS_ROOT / "PRECHECK_NOTICIAS_MARKDOWN.md").read_text(encoding="utf-8")

    for item in (
        "No se implementa Markdown",
        "No se anade parser Markdown",
        "No se anade sanitizador",
        "No se cambia SQLite",
        "No se cambia `api_public_news()`",
        "No se cambia `public.js`",
        "No se cambia Firebase",
    ):
        assert item in text


def test_sqlite_migration_precheck_documents_current_schema() -> None:
    text = (DOCS_ROOT / "PRECHECK_SQLITE_MIGRACIONES.md").read_text(encoding="utf-8")

    for item in (
        "DB_PATH",
        "db()",
        "db_session()",
        "init_db()",
        "ensure_column()",
        "seed_users_and_settings()",
        "infonalia_dias",
        "licitaciones",
        "notificaciones",
        "usuarios",
        "app_settings",
        "noticias",
        "idx_licitaciones_estado",
        "idx_noticias_published",
        "schema_migrations",
    ):
        assert item in text


def test_sqlite_migration_precheck_keeps_implementation_out_of_scope() -> None:
    text = (DOCS_ROOT / "PRECHECK_SQLITE_MIGRACIONES.md").read_text(encoding="utf-8")

    for item in (
        "No se cambia SQLite",
        "No se implementan migraciones",
        "No se toca `app.py`",
        "No se modifica la base productiva",
        "SQLite temporal",
        "No se usan datos reales",
    ):
        assert item in text
