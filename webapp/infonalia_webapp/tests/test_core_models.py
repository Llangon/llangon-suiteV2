from __future__ import annotations

import importlib
import sys
from datetime import date, datetime, timezone
from decimal import Decimal

from webapp.infonalia_webapp.core.models import (
    DownloadJob,
    DownloadStatus,
    ImportMode,
    ImportResult,
    ImportRun,
    ImportRunStatus,
    LicitacionCandidate,
    LicitacionNormalized,
    NewsArticle,
    NewsStatus,
    StorageBackendName,
    StorageObject,
    StorageObjectType,
)


def test_core_model_imports_do_not_import_app_or_side_effect_modules() -> None:
    module_names = (
        "webapp.infonalia_webapp.core.models",
        "webapp.infonalia_webapp.core.source_contracts",
        "webapp.infonalia_webapp.core.storage_contracts",
        "webapp.infonalia_webapp.core.news_contracts",
    )
    for module_name in module_names:
        sys.modules.pop(module_name, None)

    before = set(sys.modules)

    for module_name in module_names:
        importlib.import_module(module_name)

    added = set(sys.modules) - before

    assert "app" not in sys.modules
    assert "webapp.infonalia_webapp.app" not in sys.modules
    assert not {"sqlite3", "requests", "http.server", "socketserver"} & added


def test_licitacion_models_can_be_instantiated() -> None:
    received_at = datetime(2026, 6, 11, 10, 30, tzinfo=timezone.utc)
    candidate = LicitacionCandidate(
        source_name="csv",
        raw_payload={"expediente": "EXP-1"},
        external_id="source-1",
        external_url="https://example.test/expediente/source-1",
        received_at=received_at,
    )

    normalized = LicitacionNormalized(
        source_name=candidate.source_name,
        titulo="Servicio de prueba",
        expediente="EXP-1",
        organismo="Ayuntamiento de prueba",
        descripcion="Descripcion de prueba",
        external_id=candidate.external_id,
        external_url=candidate.external_url,
        presupuesto=Decimal("1234.56"),
        fecha_publicacion=date(2026, 6, 10),
        fecha_limite=date(2026, 6, 30),
        estado="pendiente",
        cpv="72000000",
        raw_payload=candidate.raw_payload,
        fingerprint="csv:exp-1",
        imported_at=received_at,
        last_seen_at=received_at,
    )

    assert candidate.raw_payload["expediente"] == "EXP-1"
    assert normalized.source_name == "csv"
    assert normalized.presupuesto == Decimal("1234.56")
    assert normalized.fecha_limite == date(2026, 6, 30)


def test_import_models_can_be_instantiated() -> None:
    run = ImportRun(
        source_name="email_infonalia",
        mode=ImportMode.manual,
        status=ImportRunStatus.completed,
        total_seen=5,
        total_new=2,
        total_updated=1,
        total_duplicates=1,
        total_errors=1,
    )
    result = ImportResult(
        candidates_seen=5,
        normalized_ok=4,
        inserted=2,
        updated=1,
        duplicates=1,
        errors=1,
    )

    assert run.mode is ImportMode.manual
    assert run.status is ImportRunStatus.completed
    assert result.candidates_seen == 5
    assert result.errors == 1


def test_storage_and_download_models_can_be_instantiated() -> None:
    created_at = datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc)
    stored_file = StorageObject(
        backend_name=StorageBackendName.local,
        uri="local://licitaciones/1/documento.pdf",
        display_path="licitaciones/1/documento.pdf",
        object_type=StorageObjectType.file,
        size_bytes=128,
        checksum="sha256:abc",
        created_at=created_at,
        metadata={"content_type": "application/pdf"},
    )
    job = DownloadJob(
        licitacion_id=1,
        backend_name=StorageBackendName.local,
        status=DownloadStatus.completed,
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at,
        objects=[stored_file],
    )

    assert stored_file.object_type is StorageObjectType.file
    assert job.status is DownloadStatus.completed
    assert job.objects == [stored_file]


def test_news_article_can_be_instantiated() -> None:
    created_at = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    article = NewsArticle(
        title="Nueva licitacion",
        slug="nueva-licitacion",
        summary="Resumen breve",
        content_markdown="## Contenido",
        featured_image="https://example.test/image.jpg",
        status=NewsStatus.published,
        published_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )

    assert article.slug == "nueva-licitacion"
    assert article.status is NewsStatus.published


def test_enums_contain_expected_values() -> None:
    assert {item.value for item in ImportMode} == {"manual", "automatic"}
    assert {item.value for item in ImportRunStatus} == {"pending", "running", "completed", "failed"}
    assert {item.value for item in StorageBackendName} == {
        "local",
        "dropbox_sync_folder",
        "dropbox_api",
    }
    assert {item.value for item in StorageObjectType} == {"file", "folder"}
    assert {item.value for item in DownloadStatus} == {"pending", "running", "completed", "failed"}
    assert {item.value for item in NewsStatus} == {"draft", "published"}
