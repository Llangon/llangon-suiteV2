from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from herramientas_python.descargadores.catalunya import downloader as catalunya_downloader
from herramientas_python.descargadores.catalunya.documents import descargar_enlaces
from herramientas_python.descargadores.common.question_models import SyncResult
from herramientas_python.descargadores.common.run_result import (
    DownloadArtifact,
    DownloadRunResult,
    PlatformCapabilities,
)
from herramientas_python.descargadores.euskadi.downloader import run_euskadi
from herramientas_python.descargadores.junta_andalucia.downloader import run_junta_andalucia
from herramientas_python.descargadores.junta_andalucia import browser as junta_browser
from herramientas_python.descargadores.madrid.downloader import run_madrid
from herramientas_python.descargadores.navarra.downloader import run_navarra
from herramientas_python.descargadores.place.downloader import run_place
from herramientas_python.descargadores.registry import (
    DOWNLOADER_SPECS,
    get_downloader_spec,
    run_downloader,
)


class FakeResponse:
    def __init__(self, *, text="", content=b"", url="https://example.test", json_data=None):
        self.text = text
        self.content = content or text.encode("utf-8")
        self.url = url
        self.headers = {}
        self._json_data = json_data

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


class SequentialSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError(f"GET no previsto: {url}")
        return self.responses.pop(0)


def test_common_result_is_simple_serializable_and_extensible() -> None:
    result = DownloadRunResult(
        platform="navarra",
        tender_id="EXP-1",
        source_url="https://example.test/tender/1",
        started_at="2026-07-19T08:00:00+00:00",
        finished_at="2026-07-19T08:00:01+00:00",
        status="success_with_warnings",
        capabilities=PlatformCapabilities(documents=True),
        documents_found=1,
        documents_downloaded=1,
        documents_new=1,
        artifacts=[DownloadArtifact("Pliego.pdf", "created", sha256="a" * 64)],
        warnings=["Aviso controlado"],
        error_code="REMOTE_TEMPORARY",
        retryable=True,
    )

    payload = json.loads(result.to_json())

    assert payload["schema_version"] == 2
    assert payload["platform"] == "NAVARRA"
    assert payload["successful"] is True and payload["has_warnings"] is True
    assert payload["capabilities"]["questions_and_answers"] is False
    assert payload["artifacts"][0]["status"] == "created"
    assert payload["error_code"] == "REMOTE_TEMPORARY"
    assert payload["retryable"] is True


def test_contract_keeps_remote_identity_and_block_completeness() -> None:
    result = DownloadRunResult(
        platform="PLACE",
        source_url="https://example.test/tender/1",
        started_at="inicio",
        finished_at="fin",
        status="partial",
        capabilities=PlatformCapabilities(documents=True, questions_and_answers=True),
        artifacts=[
            DownloadArtifact(
                "Acta.pdf",
                "reused",
                remote_id="DOC-77",
                section="Anuncios",
                published_at="2026-07-20",
            )
        ],
        block_completeness={"documents": "complete", "questions": "invalid"},
    )

    payload = result.to_dict()
    assert payload["artifacts"][0]["remote_id"] == "DOC-77"
    assert payload["block_completeness"] == {"documents": "complete", "questions": "invalid"}


@pytest.mark.parametrize("status", ["success", "success_with_warnings", "partial", "failed"])
def test_common_result_accepts_all_general_execution_states(status: str) -> None:
    result = DownloadRunResult(
        platform="EUSKADI",
        source_url="https://example.test",
        started_at="inicio",
        finished_at="fin",
        status=status,
        capabilities=PlatformCapabilities(),
    )
    assert result.status == status


def test_platform_without_questions_cannot_publish_question_payload() -> None:
    with pytest.raises(ValueError, match="sin preguntas"):
        DownloadRunResult(
            platform="NAVARRA",
            source_url="https://example.test",
            started_at="inicio",
            finished_at="fin",
            status="success",
            capabilities=PlatformCapabilities(documents=True, questions_and_answers=False),
            questions={"total_questions": 1},
        )


def test_registry_contains_every_operational_facade_and_real_capabilities() -> None:
    assert set(DOWNLOADER_SPECS) == {
        "PLACE",
        "CATALUNYA",
        "NAVARRA",
        "EUSKADI",
        "COMUNIDAD_MADRID",
        "JUNTA_ANDALUCIA",
        "XUNTA_DE_GALICIA",
    }
    assert get_downloader_spec("Comunidad Madrid").platform == "COMUNIDAD_MADRID"
    assert get_downloader_spec("Junta de Andalucia").platform == "JUNTA_ANDALUCIA"
    assert get_downloader_spec("Xunta de Galicia").platform == "XUNTA_DE_GALICIA"
    assert get_downloader_spec("Galicia").platform == "XUNTA_DE_GALICIA"
    assert DOWNLOADER_SPECS["PLACE"].capabilities.questions_and_answers is True
    assert DOWNLOADER_SPECS["CATALUNYA"].capabilities.questions_and_answers is True
    assert all(
        not DOWNLOADER_SPECS[name].capabilities.questions_and_answers
        for name in (
            "NAVARRA",
            "EUSKADI",
            "COMUNIDAD_MADRID",
            "JUNTA_ANDALUCIA",
            "XUNTA_DE_GALICIA",
        )
    )
    assert all(callable(spec.load_runner()) for spec in DOWNLOADER_SPECS.values())


def test_document_only_platforms_do_not_load_question_or_question_platform_modules() -> None:
    code = """
import sys
import herramientas_python.descargadores.navarra.downloader
import herramientas_python.descargadores.euskadi.downloader
import herramientas_python.descargadores.madrid.downloader
import herramientas_python.descargadores.junta_andalucia.downloader
import herramientas_python.descargadores.xunta_galicia.downloader
for name in sys.modules:
    if name.endswith('question_models') or '.place.' in name or '.catalunya.' in name:
        raise SystemExit(name)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_registry_executes_internal_runner_without_using_a_facade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("herramientas_python.descargadores.navarra.downloader")
    expected = DownloadRunResult(
        platform="NAVARRA",
        source_url="https://example.test/navarra",
        started_at="inicio",
        finished_at="fin",
        status="success",
        capabilities=PlatformCapabilities(documents=True),
    )
    monkeypatch.setattr(module, "run_navarra", lambda *_args, **_kwargs: expected)

    result = run_downloader("Navarra", expected.source_url, tmp_path)

    assert result is expected


def test_junta_runner_propagates_structured_transient_page_failure(tmp_path: Path) -> None:
    class BrowserAPI:
        navigation_attempts = 0

        @staticmethod
        def abrir_chrome():
            return object(), "temporary-profile", object(), 9222

        @staticmethod
        def crear_pagina(_browser, _port, _download_directory):
            return object()

        @staticmethod
        def normalizar_url_licitacion(url):
            return url

        @classmethod
        def navegar_a_licitacion(cls, _page, _url):
            cls.navigation_attempts += 1

        @staticmethod
        def preparar_reintento_navegacion(_page):
            return None

        @staticmethod
        def esperar_documentacion_complementaria(_page, *, logger):
            raise junta_browser.JuntaEmptyRenderError("Angular no produjo contenido")

        @staticmethod
        def error_metadata(exc):
            return junta_browser.error_metadata(exc)

        @staticmethod
        def cerrar_chrome(_process, _profile, _browser, _page):
            return None

    result = run_junta_andalucia(
        "https://www.juntadeandalucia.es/tender/1",
        tmp_path,
        browser_api=BrowserAPI,
        logger=lambda _message: None,
    )

    assert BrowserAPI.navigation_attempts == 3
    assert result.status == "failed"
    assert result.error_code == "JUNTA_EMPTY_RENDER"
    assert result.retryable is True


@pytest.mark.parametrize(
    ("facade", "runner_name"),
    (
        ("Descargar_PLACE", "run_place"),
        ("Descargar_Catalunya", "ejecutar_descarga_catalunya"),
        ("Descargar_Navarra", "run_navarra"),
        ("Descargar_Euskadi", "run_euskadi"),
        ("Descargar_ComunidadMadrid", "run_madrid"),
        ("Descargar_JuntaAndalucia", "run_junta_andalucia"),
        ("Descargar_XuntaGalicia", "run_xunta_galicia"),
    ),
)
def test_all_historical_facades_import_and_delegate(facade: str, runner_name: str) -> None:
    module = importlib.import_module(f"herramientas_python.{facade}")
    assert callable(module.main)
    runner = getattr(module, runner_name)
    assert ".descargadores." in runner.__module__


def test_navarra_result_supports_first_run_and_no_changes(tmp_path: Path) -> None:
    plena_url = "https://licitacionelectronica.navarra.es/licitador/licitadores/detalle/CODE/s"

    def session():
        return SequentialSession(
            [
                FakeResponse(json_data={"idExpediente": 7, "documentos": []}),
                FakeResponse(
                    json_data=[
                        {
                            "nombreDocumento": "Documento.pdf",
                            "referenciaDocumento": "expedientes/7/publicados",
                        }
                    ]
                ),
            ]
        )

    first = run_navarra(
        plena_url,
        tmp_path,
        session=session(),
        download_document=lambda *_args, **_kwargs: ("descargado", "Documento.pdf"),
        logger=lambda _message: None,
    )
    second = run_navarra(
        plena_url,
        tmp_path,
        session=session(),
        download_document=lambda *_args, **_kwargs: ("omitido", "Documento.pdf"),
        logger=lambda _message: None,
    )

    assert first.status == "success" and first.documents_new == 1
    assert first.capabilities.questions_and_answers is False and first.questions is None
    assert second.status == "success" and second.changes_detected is False
    assert second.artifacts[0].status == "reused"
    assert second.artifacts[0].source_url


def test_euskadi_result_reports_partial_document_failure(tmp_path: Path) -> None:
    html = """
    <h1>EXP-EU-1</h1>
    <a onclick="descargarFichero('10')">Pliego.pdf</a>
    <a onclick="descargarFicheroContrato('11')">Anexo.pdf</a>
    """
    response = FakeResponse(text=html, url="https://contratacion.euskadi.eus/anuncio_contratacion/1")

    def download(_session, document, *_args, **_kwargs):
        if "11" in document["url"]:
            raise OSError("fallo simulado")
        return "descargado", "Pliego.pdf"

    result = run_euskadi(
        response.url,
        tmp_path,
        session=SequentialSession([response]),
        download_document=download,
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.tender_id == "EXP-EU-1"
    assert result.documents_found == 2 and result.documents_downloaded == 1
    assert result.recoverable_issues and result.error == ""


def test_euskadi_first_download_returns_success_and_new_document(tmp_path: Path) -> None:
    url = "https://contratacion.euskadi.eus/anuncio_contratacion/2"
    response = FakeResponse(
        text='<h1>EXP-EU-2</h1><a onclick="descargarFichero(20)">Pliego.pdf</a>',
        url=url,
    )
    result = run_euskadi(
        url,
        tmp_path,
        session=SequentialSession([response]),
        download_document=lambda *_args, **_kwargs: ("descargado", "Pliego.pdf"),
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_new == 1 and result.changes_detected is True


def test_euskadi_reused_document_remains_in_remote_inventory(tmp_path: Path) -> None:
    url = "https://contratacion.euskadi.eus/anuncio_contratacion/3"
    response = FakeResponse(
        text='<h1>EXP-EU-3</h1><a onclick="descargarFichero(30)">Pliego.pdf</a>',
        url=url,
    )
    result = run_euskadi(
        url,
        tmp_path,
        session=SequentialSession([response]),
        download_document=lambda *_args, **_kwargs: ("omitido", "Pliego.pdf"),
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].status == "reused" and result.artifacts[0].source_url


def test_madrid_result_supports_repeated_documents_without_questions(tmp_path: Path) -> None:
    url = "https://contratos-publicos.comunidad.madrid/contrato-publico/1"
    html = """
    <div>Número de expediente</div><div>EXP-MAD-1</div>
    <a href="/contrato-publico/print/pdf/node/1">Ficha</a>
    <a href="/medias/anexo/download" title="Anexo técnico">Descargar</a>
    """
    result = run_madrid(
        url,
        tmp_path,
        session=SequentialSession([FakeResponse(text=html, url=url)]),
        download_document=lambda *_args, **_kwargs: ("omitido", "documento.pdf"),
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_found == 2 and result.documents_downloaded == 0
    assert result.changes_detected is False
    assert result.capabilities.questions_and_answers is False
    assert len(result.artifacts) == 2
    assert all(item.status == "reused" and item.source_url for item in result.artifacts)


def test_madrid_first_download_and_partial_error_are_distinguished(tmp_path: Path) -> None:
    url = "https://contratos-publicos.comunidad.madrid/contrato-publico/2"
    html = """
    <div>Número de expediente</div><div>EXP-MAD-2</div>
    <a href="/medias/uno/download" title="Uno.pdf">Descargar</a>
    <a href="/medias/dos/download" title="Dos.pdf">Descargar</a>
    """

    def download(_session, source_url, *_args, **_kwargs):
        if "/dos/" in source_url:
            raise OSError("fallo simulado")
        return "descargado", "Uno.pdf"

    result = run_madrid(
        url,
        tmp_path,
        session=SequentialSession([FakeResponse(text=html, url=url)]),
        download_document=download,
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.documents_found == 2 and result.documents_new == 1


class FakeJuntaPage:
    def __init__(self):
        self.calls = []

    def call(self, *_args, **_kwargs):
        self.calls.append((_args, _kwargs))
        return {}


class FakeJuntaBrowser:
    def __init__(self, *, fail_second=True, reused=False, wait_failures=0, navigation_failures=0):
        self.closed = False
        self.fail_second = fail_second
        self.reused = reused
        self.wait_failures = wait_failures
        self.navigation_failures = navigation_failures
        self.navigation_calls = 0
        self.wait_calls = 0
        self.navigation_preparations = 0
        self.page = FakeJuntaPage()

    def abrir_chrome(self):
        return object(), "perfil", object(), 9222

    def crear_pagina(self, _browser, _port, _directory):
        return self.page

    def navegar_a_licitacion(self, page, url):
        self.navigation_calls += 1
        if self.navigation_calls <= self.navigation_failures:
            raise junta_browser.JuntaNavigationTransientError(
                "Chrome no pudo abrir la licitación: net::ERR_TIMED_OUT"
            )
        return page.call("Page.navigate", {"url": url}, timeout=25)

    def preparar_reintento_navegacion(self, _page):
        self.navigation_preparations += 1

    def esperar_documentacion_complementaria(self, _page, **_kwargs):
        self.wait_calls += 1
        if self.wait_calls <= self.wait_failures:
            raise RuntimeError("carga incompleta simulada")
        return None

    def extraer_enlaces(self, _page, _include_stamps):
        return [
            {"href": "https://example.test/uno.pdf", "text": "Uno.pdf"},
            {"href": "https://example.test/dos.pdf", "text": "Dos.pdf"},
        ]

    def crear_session_descarga(self, _page, _url):
        return object()

    def limpiar_nombre(self, value):
        return value

    def href_descargable(self, _href):
        return True

    def descargar_por_url(self, _session, link, *_args):
        if self.fail_second and link["text"].startswith("Dos"):
            raise OSError("fallo simulado")
        return link["text"], self.reused

    def cerrar_chrome(self, *_args):
        self.closed = True


def test_junta_result_is_partial_and_always_closes_browser(tmp_path: Path) -> None:
    browser = FakeJuntaBrowser()
    result = run_junta_andalucia(
        "https://juntadeandalucia.es/licitacion/1",
        tmp_path,
        browser_api=browser,
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.documents_found == 2 and result.documents_downloaded == 1
    assert {item.status for item in result.artifacts} == {"created", "failed"}
    assert browser.closed is True
    assert result.capabilities.questions_and_answers is False
    navigate = browser.page.calls[0]
    assert navigate[0][0] == "Page.navigate"
    assert navigate[1]["timeout"] == 25


@pytest.mark.parametrize(
    ("reused", "expected_new", "expected_changes"),
    ((False, 2, True), (True, 0, False)),
)
def test_junta_success_distinguishes_first_run_and_reused_files(
    tmp_path: Path,
    reused: bool,
    expected_new: int,
    expected_changes: bool,
) -> None:
    browser = FakeJuntaBrowser(fail_second=False, reused=reused)
    result = run_junta_andalucia(
        "https://juntadeandalucia.es/licitacion/2",
        tmp_path,
        browser_api=browser,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_new == expected_new
    assert result.changes_detected is expected_changes
    assert browser.closed is True
    assert len(result.artifacts) == 2
    if reused:
        assert all(item.status == "reused" and item.source_url for item in result.artifacts)


def test_junta_retries_incomplete_page_navigation(tmp_path: Path) -> None:
    browser = FakeJuntaBrowser(fail_second=False, wait_failures=1)

    result = run_junta_andalucia(
        "https://juntadeandalucia.es/licitacion/2",
        tmp_path,
        browser_api=browser,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert browser.wait_calls == 2
    assert browser.navigation_preparations == 1
    assert sum(call[0][0] == "Page.navigate" for call in browser.page.calls) == 2


def test_junta_retries_page_navigate_timeout_inside_same_browser(tmp_path: Path) -> None:
    browser = FakeJuntaBrowser(
        fail_second=False,
        navigation_failures=1,
    )

    result = run_junta_andalucia(
        "https://juntadeandalucia.es/licitacion/2",
        tmp_path,
        browser_api=browser,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert browser.navigation_calls == 2
    assert browser.wait_calls == 1
    assert browser.navigation_preparations == 1


def test_place_reused_document_remains_in_remote_inventory(tmp_path: Path) -> None:
    url = "https://contrataciondelestado.es/ejemplo"
    html = '<a href="/GetDocumentByIdServlet?id=1">Pliego técnico</a>'

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return SyncResult(
                status="no_changes",
                query_successful=True,
                authentication_successful=True,
                snapshot_complete=True,
                no_changes=True,
                platform="PLACE",
            )

    first = run_place(
        url,
        tmp_path,
        session=SequentialSession(
            [FakeResponse(text=html, url=url), FakeResponse(content=b"%PDF-1.4 test", url=url)]
        ),
        usuario="usuario",
        contrasena="clave",
        modulo_preguntas=Questions,
        logger=lambda _message: None,
    )
    second = run_place(
        url,
        tmp_path,
        session=SequentialSession(
            [FakeResponse(text=html, url=url), FakeResponse(content=b"%PDF-1.4 test", url=url)]
        ),
        usuario="usuario",
        contrasena="clave",
        modulo_preguntas=Questions,
        logger=lambda _message: None,
    )

    assert first.artifacts[0].status == "created"
    assert second.artifacts[0].status == "reused"
    assert second.artifacts[0].source_url == first.artifacts[0].source_url


def test_catalunya_reused_document_preserves_remote_url_in_adapter(tmp_path: Path) -> None:
    url = "https://contractaciopublica.cat/portal-api/descarrega-document/1/hash"
    links = [{"href": url, "text": "Pliego", "section": "Documentacio", "fecha": "2026-07-20"}]
    first = descargar_enlaces(
        SequentialSession([FakeResponse(content=b"%PDF-1.4 test", url=url)]),
        links,
        tmp_path,
        "https://contractaciopublica.cat/es/detall-publicacio/test",
    )
    second = descargar_enlaces(
        SequentialSession([FakeResponse(content=b"%PDF-1.4 test", url=url)]),
        links,
        tmp_path,
        "https://contractaciopublica.cat/es/detall-publicacio/test",
    )
    sync = SyncResult(
        status="no_changes",
        query_successful=True,
        authentication_successful=True,
        snapshot_complete=True,
        no_changes=True,
        platform="CATALUNYA",
    )

    adapted = catalunya_downloader._apply_document_result(sync, second)

    assert first.downloaded[0].source_url == url
    assert second.skipped[0].source_url == url
    assert adapted.reused_documents[0]["source_url"] == url


def test_place_global_result_adapts_question_sync_without_changing_state(tmp_path: Path) -> None:
    url = "https://contrataciondelestado.es/ejemplo"
    session = SequentialSession([FakeResponse(text="<html></html>", url=url)])

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return SyncResult(
                status="no_changes",
                query_successful=True,
                authentication_successful=True,
                snapshot_complete=True,
                no_changes=True,
                platform="PLACE",
            )

    result = run_place(
        url,
        tmp_path,
        session=session,
        usuario="usuario",
        contrasena="clave",
        modulo_preguntas=Questions,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.capabilities.questions_and_answers is True
    assert result.questions["no_changes"] is True
    assert result.state_path == ""


def test_catalunya_global_result_adapts_existing_sync_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalunya_downloader,
        "ejecutar_descarga_catalunya",
        lambda *_args, **_kwargs: SyncResult(
            status="no_changes",
            query_successful=True,
            authentication_successful=True,
            authentication_required=False,
            snapshot_complete=True,
            no_changes=True,
            platform="CATALUNYA",
        ),
    )

    result = catalunya_downloader.run_catalunya(
        "https://contractaciopublica.cat/es/detall-publicacio/test",
        tmp_path,
        log=lambda _message: None,
    )

    assert result.status == "success"
    assert result.platform == "CATALUNYA"
    assert result.capabilities.questions_and_answers is True
    assert result.questions["snapshot_complete"] is True
