from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
from types import SimpleNamespace
from pathlib import Path

import requests
import pytest

from herramientas_python.descargadores.place import browser_fallback as place_browser
from herramientas_python.descargadores.place.browser_fallback import (
    ChromePlaceChallengeResolver,
    PlaceDocumentRequest,
    RenderedDocument,
    RenderedPage,
)
from herramientas_python.descargadores.place.errors import (
    PlaceBrowserError,
    PlaceBrowserInteractionRequiredError,
)
from herramientas_python.descargadores.place import session as place_session
from herramientas_python.descargadores.place.errors import PlaceAccessChallengeError


def load_place_downloader():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "herramientas_python" / "Descargar_PLACE.py"
    spec = importlib.util.spec_from_file_location("descargar_place_for_tests", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_place_document_html_is_reprocessed_for_missing_attachments(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    (tmp_path / "DOC_CD2026-000165479.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "DOC_CN2026-000165535.xml").write_text("<xml></xml>", encoding="utf-8")

    assert downloader.candidatos_para_segunda_fase(str(tmp_path), []) == [
        "DOC_CD2026-000165479.html",
        "DOC_CN2026-000165535.xml",
    ]


def test_place_downloader_detects_rar_without_appending_bin() -> None:
    downloader = load_place_downloader()
    rar_bytes = b"Rar!\x1a\x07\x01\x00" + b"\x00" * 32
    response = SimpleNamespace(
        content=rar_bytes,
        headers={"Content-Type": "application/octet-stream"},
    )

    ext = downloader.detectar_extension(
        response,
        texto_visible="ANEXOS",
        nombre_logico="DOC20260708091325ANEXOS.rar",
        archivo_url="https://example.test/documento",
    )
    nombre = downloader.construir_nombre_archivo(
        response,
        "DOC20260708091325ANEXOS.rar",
        "ANEXOS",
        "https://example.test/documento",
        ext,
    )

    assert ext == ".rar"
    assert nombre == "DOC20260708091325ANEXOS.rar"


def test_place_js_challenge_without_extension_is_not_published(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    challenge = (
        b"<!DOCTYPE html><html><body>Please enable JavaScript to view the page content. "
        b"Support ID: 123456</body></html>"
    )
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=stable"
    final_url = "https://contrataciondelestado.es/waf/challenge?support=123456"

    class FakeResponse:
        content = challenge
        headers = {"Content-Type": "text/html; charset=utf-8"}
        url = final_url
        status_code = 200
        history = [SimpleNamespace(url=source_url)]

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeSession:
        @staticmethod
        def get(*_args, **_kwargs):
            return FakeResponse()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        FakeSession(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=stable",
        "Pliego de cláusulas administrativas",
        "Pliego de cláusulas administrativas",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "failed"
    assert event["path"] == ""
    assert event["sha256"] == ""
    assert event["source_url"] == source_url
    assert event["final_url"] == final_url
    assert event["content_type"] == "text/html; charset=utf-8"
    assert event["size"] == len(challenge)
    assert event["http_status"] == 200
    assert event["redirect_count"] == 1
    assert event["error_code"] == "PLACE_JS_CHALLENGE"
    assert event["error_message"]


def test_place_allows_legitimate_html_document_container_and_records_metadata(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    container = (
        b"<!DOCTYPE html><html><body><a "
        b'href="/GetDocumentByIdServlet?DocumentIdParam=attachment">Abrir adjunto</a>'
        b"</body></html>"
    )
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=container"
    final_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_documento:container"

    class FakeResponse:
        content = container
        headers = {"Content-Type": "text/html; charset=utf-8"}
        url = final_url
        status_code = 200
        history = [SimpleNamespace(url=source_url)]

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeSession:
        @staticmethod
        def get(*_args, **_kwargs):
            return FakeResponse()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        FakeSession(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=container",
        "DOC_CD2026-000165479",
        "DOC_CD2026-000165479",
        str(tmp_path),
        set(),
        events,
    )

    assert result == "DOC_CD2026-000165479.html"
    assert (tmp_path / result).read_bytes() == container
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "created"
    assert event["path"] == str(tmp_path / result)
    assert event["source_url"] == source_url
    assert event["final_url"] == final_url
    assert event["content_type"] == "text/html; charset=utf-8"
    assert event["size"] == len(container)
    assert event["http_status"] == 200
    assert event["redirect_count"] == 1
    assert event["error_code"] == ""
    assert event["error_message"] == ""


def test_place_run_keeps_rejected_html_out_of_created_files_and_uses_final_referer(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    initial_url = "http://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:85"
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:85"
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=85"
    final_url = "https://contrataciondelestado.es/waf/challenge?support=85"
    challenge = (
        b"<!DOCTYPE html><html><body>Please enable JavaScript to view the page content. "
        b"Support ID: 85</body></html>"
    )

    class FakeResponse:
        def __init__(self, *, text: str = "", content: bytes = b"", url: str, headers=None, history=None):
            self.text = text
            self.content = content or text.encode("utf-8")
            self.url = url
            self.headers = headers or {}
            self.status_code = 200
            self.history = history or []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def get(self, url: str, **kwargs):
            self.calls.append((url, kwargs))
            if url == tender_url:
                return FakeResponse(
                    text='<a href="/GetDocumentByIdServlet?DocumentIdParam=85">Pliego administrativo</a>',
                    url=tender_url,
                )
            if url == source_url:
                return FakeResponse(
                    content=challenge,
                    url=final_url,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    history=[SimpleNamespace(url=source_url)],
                )
            raise AssertionError(f"GET no previsto: {url}")

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return {
                "status": "no_changes",
                "query_successful": True,
                "authentication_successful": True,
                "snapshot_complete": True,
                "no_changes": True,
                "answered_questions": 0,
                "document_generated": False,
                "rtf_generated": False,
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
                "platform": "PLACE",
            }

    session = FakeSession()
    result = downloader.run_place(
        initial_url,
        tmp_path,
        session=session,
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=Questions,
        logger=lambda _message: None,
        challenge_resolver_factory=None,
    )

    assert session.calls[0][0] == tender_url
    assert session.calls[1][1]["headers"]["Referer"] == tender_url
    assert result.files_created == []
    assert result.documents_new == 0
    assert result.changes_detected is False
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.status == "failed"
    assert artifact.path == ""
    assert artifact.sha256 == ""
    assert artifact.content_type == "text/html; charset=utf-8"
    assert artifact.size == len(challenge)
    assert artifact.error_code == "PLACE_JS_CHALLENGE"
    assert artifact.final_url == final_url


def test_place_js_challenge_uses_one_browser_resolver_and_publishes_only_pdf(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:86"
    first_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=one"
    second_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=two"
    challenge = (
        b"<!DOCTYPE html><html><body>Please enable JavaScript to view the page content. "
        b"Support ID: 86</body></html>"
    )

    class FakeResponse:
        def __init__(self, *, text: str = "", content: bytes = b"", url: str):
            self.text = text
            self.content = content or text.encode("utf-8")
            self.url = url
            self.headers = {"Content-Type": "text/html; charset=utf-8"} if content else {}
            self.status_code = 200
            self.history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeSession:
        def get(self, url: str, **_kwargs):
            if url == tender_url:
                return FakeResponse(
                    text=(
                        '<a href="/GetDocumentByIdServlet?DocumentIdParam=one">Pliego A</a>'
                        '<a href="/GetDocumentByIdServlet?DocumentIdParam=two">Pliego B</a>'
                    ),
                    url=tender_url,
                )
            if url in {first_document, second_document}:
                return FakeResponse(content=challenge, url=url)
            raise AssertionError(f"GET no previsto: {url}")

    class Resolver:
        def __init__(self) -> None:
            self.requests = []
            self.closed = 0

        def resolve(self, request):
            self.requests.append(request)
            suffix = b"A" if request.document_url == first_document else b"B"
            return RenderedDocument(
                content=b"%PDF-1.4\n" + suffix + b"\n%%EOF\n",
                source_url=request.document_url,
                final_url=request.document_url,
            )

        def close(self) -> None:
            self.closed += 1

    resolver = Resolver()
    factory_calls = []

    def resolver_factory():
        factory_calls.append(True)
        return resolver

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return {
                "status": "no_changes",
                "query_successful": True,
                "authentication_successful": True,
                "snapshot_complete": True,
                "no_changes": True,
                "answered_questions": 0,
                "document_generated": False,
                "rtf_generated": False,
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
                "platform": "PLACE",
            }

    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=FakeSession(),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=Questions,
        challenge_resolver_factory=resolver_factory,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_new == 2
    assert len(result.files_created) == 2
    assert factory_calls == [True]
    assert [request.document_url for request in resolver.requests] == [first_document, second_document]
    assert resolver.closed == 1
    assert all(item.retrieval_method == "browser" for item in result.artifacts)
    assert all(item.fallback_reason == "PLACE_JS_CHALLENGE" for item in result.artifacts)
    assert all(item.http_status == 0 for item in result.artifacts)
    assert not list(tmp_path.glob("*.html"))


def test_place_browser_interaction_requirement_remains_partial_and_closes_resolver(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:87"
    document_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=blocked"
    challenge = (
        b"Please enable JavaScript to view the page content. Support ID: blocked"
    )

    class Response:
        def __init__(self, content: bytes, url: str):
            self.content = content
            self.text = content.decode("utf-8", errors="ignore")
            self.url = url
            self.headers = {"Content-Type": "text/html"}
            self.status_code = 200
            self.history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        def get(self, url: str, **_kwargs):
            if url == tender_url:
                return Response(
                    b'<a href="/GetDocumentByIdServlet?DocumentIdParam=blocked">Pliego</a>',
                    tender_url,
                )
            if url == document_url:
                return Response(challenge, document_url)
            raise AssertionError(url)

    class Resolver:
        def __init__(self) -> None:
            self.closed = 0

        @staticmethod
        def resolve(_request):
            raise PlaceBrowserInteractionRequiredError(
                "PLACE_BROWSER_INTERACTION_REQUIRED: validación manual"
            )

        def close(self) -> None:
            self.closed += 1

    resolver = Resolver()

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return {
                "status": "no_changes",
                "query_successful": True,
                "authentication_successful": True,
                "snapshot_complete": True,
                "no_changes": True,
                "answered_questions": 0,
                "document_generated": False,
                "rtf_generated": False,
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
                "platform": "PLACE",
            }

    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=Session(),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=Questions,
        challenge_resolver_factory=lambda: resolver,
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.files_created == []
    assert resolver.closed == 1
    assert result.artifacts[0].status == "failed"
    assert result.artifacts[0].error_code == "PLACE_BROWSER_INTERACTION_REQUIRED"
    assert result.artifacts[0].retrieval_method == "browser"
    assert result.artifacts[0].fallback_reason == "PLACE_JS_CHALLENGE"


def test_place_browser_html_challenge_is_never_published_even_with_octet_stream(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    challenge = b"Please enable JavaScript to view the page content. Support ID: browser"
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=browser"

    class Response:
        content = challenge
        headers = {"Content-Type": "application/octet-stream"}
        url = source_url
        status_code = 200
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    class Resolver:
        @staticmethod
        def resolve(request):
            return RenderedDocument(
                content=challenge,
                source_url=request.document_url,
                final_url=request.document_url,
                content_type="application/octet-stream",
            )

        @staticmethod
        def close() -> None:
            return None

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=browser",
        "documento.html",
        "documento.html",
        str(tmp_path),
        set(),
        events,
        Resolver(),
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert events[0]["error_code"] == "PLACE_BROWSER_CHALLENGE"
    assert events[0]["retrieval_method"] == "browser"


def test_place_http_403_javascript_challenge_can_use_browser_fallback(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    challenge = b"Please enable JavaScript to view the page content. Support ID: 403"
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=403"

    class Response:
        content = challenge
        headers = {"Content-Type": "text/html"}
        url = source_url
        status_code = 403
        history = []

        @staticmethod
        def raise_for_status() -> None:
            raise requests.HTTPError("403")

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    class Resolver:
        @staticmethod
        def resolve(request):
            return RenderedDocument(
                content=b"%PDF-1.4\nFallback 403\n%%EOF\n",
                source_url=request.document_url,
                final_url=request.document_url,
            )

        @staticmethod
        def close() -> None:
            return None

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=403",
        "pliego-403",
        "pliego-403",
        str(tmp_path),
        set(),
        events,
        Resolver(),
    )

    assert result == "pliego-403.pdf"
    assert (tmp_path / result).read_bytes().startswith(b"%PDF")
    assert events[0]["retrieval_method"] == "browser"
    assert events[0]["http_status"] == 0


def test_place_access_denied_plain_text_is_not_published_as_pdf(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=denied"

    class Response:
        content = b"Access denied"
        headers = {"Content-Type": "application/pdf"}
        url = source_url
        status_code = 200
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=denied",
        "pliego.pdf",
        "pliego.pdf",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert events[0]["error_code"] == "PLACE_ACCESS_CHALLENGE"


def test_place_html_error_fragment_is_not_published_from_pdf_name(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=fragment"

    class Response:
        content = b"<div>Servicio temporalmente no disponible</div>"
        headers = {"Content-Type": "application/pdf"}
        url = source_url
        status_code = 200
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=fragment",
        "pliego.pdf",
        "pliego.pdf",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert events[0]["error_code"] == "PLACE_UNEXPECTED_HTML"


def test_place_paragraph_html_fragment_is_not_published_as_xml(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=paragraph"

    class Response:
        content = b"<p>Servicio temporalmente no disponible</p>"
        headers = {"Content-Type": "application/pdf"}
        url = source_url
        status_code = 200
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=paragraph",
        "pliego.pdf",
        "pliego.pdf",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert events[0]["error_code"] == "PLACE_UNEXPECTED_HTML"


def test_place_declared_well_formed_xml_is_preserved(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=xml"

    class Response:
        content = b'<?xml version="1.0" encoding="UTF-8"?><documento><id>1</id></documento>'
        headers = {"Content-Type": "application/xml"}
        url = source_url
        status_code = 200
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=xml",
        "datos.xml",
        "datos.xml",
        str(tmp_path),
        set(),
    )

    assert result == "datos.xml"
    assert (tmp_path / result).read_bytes().startswith(b"<?xml")


def test_place_document_redirect_outside_official_host_is_rejected(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=redirect"

    class Response:
        content = b"%PDF-1.4\nredirect\n%%EOF\n"
        headers = {"Content-Type": "application/pdf"}
        url = "https://external.example/document.pdf"
        status_code = 200
        history = [SimpleNamespace(url=source_url)]

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        Session(),
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=redirect",
        "pliego.pdf",
        "pliego.pdf",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []
    assert events[0]["error_code"] == "PLACE_DOCUMENT_REDIRECT_INVALID"


def test_place_document_does_not_follow_redirect_to_external_host(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    source_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=redirect-stop"

    class Response:
        content = b""
        headers = {"Location": "https://external.example/document.pdf"}
        url = source_url
        status_code = 302
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    session = Session()
    events: list[dict[str, object]] = []
    result = downloader.descargar_documento(
        session,
        "https://contrataciondelestado.es/tender/1",
        "/GetDocumentByIdServlet?DocumentIdParam=redirect-stop",
        "pliego.pdf",
        "pliego.pdf",
        str(tmp_path),
        set(),
        events,
    )

    assert result is None
    assert [call[0] for call in session.calls] == [source_url]
    assert session.calls[0][1]["allow_redirects"] is False
    assert events[0]["error_code"] == "PLACE_DOCUMENT_REDIRECT_INVALID"


def test_place_profile_does_not_follow_redirect_to_external_host(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:redirect-stop"

    class Response:
        content = b""
        text = ""
        headers = {"Location": "https://external.example/profile"}
        url = tender_url
        status_code = 302
        history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    session = Session()
    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=session,
        challenge_resolver_factory=None,
    )

    assert result.status == "failed"
    assert result.error_code == "PLACE_PROFILE_REDIRECT_INVALID"
    assert [call[0] for call in session.calls] == [tender_url]
    assert session.calls[0][1]["allow_redirects"] is False


def test_place_generic_profile_access_error_never_becomes_complete_download(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:access"

    class Response:
        content = b"Access denied"
        text = "Access denied"
        url = tender_url

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=Session(),
        challenge_resolver_factory=None,
    )

    assert result.status == "failed"
    assert result.error_code == "PLACE_ACCESS_CHALLENGE"
    assert result.block_completeness == {"documents": "invalid", "questions": "invalid"}


def test_place_direct_document_never_constructs_browser_resolver(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:direct"
    document_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=direct"

    class Response:
        def __init__(self, content: bytes, url: str):
            self.content = content
            self.text = content.decode("utf-8", errors="ignore")
            self.url = url
            self.headers = {}
            self.status_code = 200
            self.history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        def get(self, url: str, **_kwargs):
            if url == tender_url:
                return Response(
                    b'<a href="/GetDocumentByIdServlet?DocumentIdParam=direct">Pliego directo</a>',
                    tender_url,
                )
            if url == document_url:
                return Response(b"%PDF-1.4\nDirecto\n%%EOF\n", document_url)
            raise AssertionError(url)

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return {
                "status": "no_changes",
                "query_successful": True,
                "authentication_successful": True,
                "snapshot_complete": True,
                "no_changes": True,
                "answered_questions": 0,
                "document_generated": False,
                "rtf_generated": False,
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
                "platform": "PLACE",
            }

    factory_calls = []

    def factory():
        factory_calls.append(True)
        raise AssertionError("No se debe abrir navegador para un PDF HTTP válido.")

    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=Session(),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=Questions,
        challenge_resolver_factory=factory,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert factory_calls == []
    assert result.artifacts[0].retrieval_method == "http"


def test_place_login_access_challenge_is_exposed_at_top_level(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:questions"
    document_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=questions"

    class Response:
        def __init__(self, content: bytes, url: str):
            self.content = content
            self.text = content.decode("utf-8", errors="ignore")
            self.url = url
            self.headers = {}
            self.status_code = 200
            self.history = []

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        def get(self, url: str, **_kwargs):
            if url == tender_url:
                return Response(
                    b'<a href="/GetDocumentByIdServlet?DocumentIdParam=questions">Pliego</a>',
                    tender_url,
                )
            if url == document_url:
                return Response(b"%PDF-1.4\nQuestions\n%%EOF\n", document_url)
            raise AssertionError(url)

    class Questions:
        @staticmethod
        def sync_place_questions(_url, _destination, _username, _password):
            return {
                "status": "error",
                "query_successful": False,
                "authentication_successful": False,
                "snapshot_complete": False,
                "answered_questions": 0,
                "document_generated": False,
                "rtf_generated": False,
                "errors": ["PLACE_LOGIN_CHALLENGE: PLACE exige JavaScript"],
                "warnings": [],
                "structure_novelties": [],
                "error_type": "access_challenge",
                "platform": "PLACE",
            }

    result = downloader.run_place(
        tender_url,
        tmp_path,
        session=Session(),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=Questions,
        challenge_resolver_factory=None,
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.error_code == "PLACE_LOGIN_CHALLENGE"
    assert result.block_completeness["questions"] == "invalid"


def test_chrome_place_resolver_reuses_one_browser_and_closes_it() -> None:
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:resolver"
    first_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=first"
    second_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=second"

    class BrowserApi:
        def __init__(self) -> None:
            self.open_count = 0
            self.profile_calls = []
            self.download_calls = []
            self.closed = 0

        def open_browser(self):
            self.open_count += 1
            return object(), "fake-place-profile", object(), 9223

        @staticmethod
        def create_page(_browser, _port, _directory):
            return object()

        def open_profile(self, _page, url):
            self.profile_calls.append(url)
            return RenderedPage(final_url=url)

        def download_link(self, _page, url, _directory):
            self.download_calls.append(url)
            return RenderedDocument(
                content=b"%PDF-1.4\nResolver\n%%EOF\n",
                source_url=url,
                final_url=url,
            )

        def close_browser(self, _process, _profile, _browser, _page):
            self.closed += 1

    api = BrowserApi()
    resolver = ChromePlaceChallengeResolver(browser_api=api)
    first = resolver.resolve(PlaceDocumentRequest(first_document, tender_url))
    second = resolver.resolve(PlaceDocumentRequest(second_document, tender_url))
    resolver.close()

    assert first.content.startswith(b"%PDF") and second.content.startswith(b"%PDF")
    assert api.open_count == 1
    assert api.profile_calls == [tender_url]
    assert api.download_calls == [first_document, second_document]
    assert api.closed == 1


def test_chrome_place_resolver_caches_terminal_profile_failure() -> None:
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:blocked"
    first_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=blocked-1"
    second_document = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=blocked-2"

    class BrowserApi:
        def __init__(self) -> None:
            self.open_count = 0
            self.profile_calls = 0
            self.closed = 0

        def open_browser(self):
            self.open_count += 1
            return object(), "fake-place-profile", object(), 9224

        @staticmethod
        def create_page(_browser, _port, _directory):
            return object()

        def open_profile(self, _page, _url):
            self.profile_calls += 1
            raise PlaceBrowserInteractionRequiredError(
                "PLACE_BROWSER_INTERACTION_REQUIRED: validación manual"
            )

        def close_browser(self, _process, _profile, _browser, _page):
            self.closed += 1

    api = BrowserApi()
    resolver = ChromePlaceChallengeResolver(browser_api=api)
    with pytest.raises(PlaceBrowserInteractionRequiredError):
        resolver.resolve(PlaceDocumentRequest(first_document, tender_url))
    with pytest.raises(PlaceBrowserInteractionRequiredError):
        resolver.resolve(PlaceDocumentRequest(second_document, tender_url))
    resolver.close()

    assert api.open_count == 1
    assert api.profile_calls == 1
    assert api.closed == 1


def test_browser_download_retries_link_after_dom_is_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tender_url = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:late"
    document_url = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=late"
    downloaded = tmp_path / "late.pdf"
    downloaded.write_bytes(b"%PDF-1.4\nlate\n%%EOF\n")
    click_states = iter(["missing", "clicked"])
    captured = []

    monkeypatch.setattr(
        place_browser,
        "_page_state",
        lambda _page: {"url": tender_url, "text": ""},
    )
    monkeypatch.setattr(
        place_browser,
        "_click_document_link",
        lambda _page, url: (captured.append(url), next(click_states))[1],
    )
    monkeypatch.setattr(place_browser, "_wait_for_download", lambda *_args, **_kwargs: downloaded)
    monkeypatch.setattr(place_browser.time, "sleep", lambda _seconds: None)

    result = place_browser.download_link(object(), document_url, tmp_path)

    assert result.content.startswith(b"%PDF")
    assert captured == [document_url, document_url]


def test_browser_click_rewrites_an_http_place_href_to_https(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=http-link"
    captured: dict[str, object] = {}

    def fake_evaluate(_page, expression: str, **kwargs):
        captured["expression"] = expression
        captured["kwargs"] = kwargs
        return "clicked"

    monkeypatch.setattr(place_browser, "_evaluate", fake_evaluate)

    assert place_browser._click_document_link(object(), target) == "clicked"
    assert "link.href = wanted;" in str(captured["expression"])
    assert captured["kwargs"] == {"timeout": 15, "user_gesture": True}


def test_browser_rejects_document_navigation_outside_place() -> None:
    target = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=external"

    class Page:
        @staticmethod
        def drain_events():
            return [
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "type": "Document",
                        "requestId": "request-1",
                        "request": {"url": target},
                    },
                },
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "type": "Document",
                        "requestId": "request-1",
                        "request": {"url": "https://external.example/document.pdf"},
                        "redirectResponse": {"url": target},
                    },
                }
            ]

    with pytest.raises(PlaceBrowserError, match="URL no autorizada"):
        place_browser._new_document_navigation_is_safe(
            Page(),
            expected_url=target,
            request_ids=set(),
        )


def test_browser_rejects_http_document_navigation_even_if_it_is_place() -> None:
    target = "https://contrataciondelestado.es/GetDocumentByIdServlet?DocumentIdParam=http-redirect"

    class Page:
        @staticmethod
        def drain_events():
            return [
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "type": "Document",
                        "requestId": "request-http",
                        "request": {"url": target.replace("https://", "http://")},
                    },
                }
            ]

    with pytest.raises(PlaceBrowserError, match="URL no autorizada"):
        place_browser._new_document_navigation_is_safe(
            Page(),
            expected_url=target,
            request_ids=set(),
        )


def test_browser_profile_checks_external_redirect_events_before_reading_dom() -> None:
    target = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion:redirect"

    class Page:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []
            self.event_batches = [
                [],
                [
                    {
                        "method": "Network.requestWillBeSent",
                        "params": {
                            "type": "Document",
                            "requestId": "profile-request",
                            "request": {"url": target},
                        },
                    },
                    {
                        "method": "Network.requestWillBeSent",
                        "params": {
                            "type": "Document",
                            "requestId": "profile-request",
                            "request": {"url": "https://external.example/redirect"},
                            "redirectResponse": {"url": target},
                        },
                    },
                ],
            ]

        def call(self, method: str, params: dict[str, object], **_kwargs):
            self.calls.append((method, params))
            return {}

        def drain_events(self):
            return self.event_batches.pop(0) if self.event_batches else []

    page = Page()
    with pytest.raises(PlaceBrowserError, match="URL no autorizada"):
        place_browser.open_profile(page, target)
    assert page.calls == [("Page.navigate", {"url": target})]


def test_place_login_js_challenge_is_not_reported_as_missing_form() -> None:
    challenge = (
        b"<!doctype html>Please enable JavaScript to view the page content. Support ID: login"
    )

    class Response:
        content = challenge
        text = challenge.decode("utf-8")
        url = place_session.LOGIN_URL

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    try:
        place_session.login(Session(), "usuario", "clave")
    except PlaceAccessChallengeError as exc:
        assert "PLACE_LOGIN_CHALLENGE" in str(exc)
    else:
        raise AssertionError("El reto de acceso debe clasificarse antes de buscar el formulario.")


def test_place_reused_document_reports_remote_hash_not_local_hash(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    local_content = b"contenido local distinto"
    remote_content = b"contenido oficial observado"
    (tmp_path / "Oferta.xls").write_bytes(local_content)

    class FakeResponse:
        content = remote_content
        headers = {"Content-Type": "application/vnd.ms-excel"}

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeSession:
        @staticmethod
        def get(*_args, **_kwargs):
            return FakeResponse()

    events: list[dict[str, object]] = []
    downloader.descargar_documento(
        FakeSession(),
        "https://contrataciondelestado.es/tender/1",
        "/document?id=stable",
        "Oferta.xls",
        "Oferta.xls",
        str(tmp_path),
        set(),
        events,
    )

    assert events[0]["status"] == "reused"
    assert events[0]["sha256"] == hashlib.sha256(remote_content).hexdigest()
    assert events[0]["sha256_source"] == "remote"


def test_place_questions_are_optional_when_credentials_are_not_configured(tmp_path: Path) -> None:
    downloader = load_place_downloader()

    result = downloader.procesar_preguntas_y_respuestas(
        "https://contrataciondelestado.es/ejemplo",
        str(tmp_path),
        usuario="",
        contrasena="",
    )

    assert result["status"] == "not_configured"
    assert result["error_type"] == "configuration"
    assert result["rtf_generated"] is False
    assert result["document_generated"] is False


def test_place_questions_are_written_by_the_operational_downloader(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    expected_path = tmp_path / "Preguntas y respuestas a fecha 2026-07-16 20-00-00.docx"

    class FakeQuestionsModule:
        @staticmethod
        def sync_place_questions(url, destination, username, password):
            assert url == "https://contrataciondelestado.es/ejemplo"
            assert destination == tmp_path.resolve()
            assert username == "usuario-prueba"
            assert password == "clave-prueba"
            return {
                "status": "created",
                "query_successful": True,
                "authentication_successful": True,
                "total_questions": 1,
                "answered_questions": 1,
                "incorporated_current_cycle": 1,
                "responses_updated": 0,
                "question_updates": 0,
                "changes_detected": True,
                "no_changes": False,
                "rtf_generated": False,
                "rtf_path": "",
                "document_generated": True,
                "document_path": str(expected_path),
                "document_format": "docx",
                "previous_review": "",
                "current_review": "2026-07-16T20:00:00+02:00",
                "error_type": "",
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
            }

    result = downloader.procesar_preguntas_y_respuestas(
        "https://contrataciondelestado.es/ejemplo",
        str(tmp_path),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=FakeQuestionsModule,
    )

    assert result["status"] == "created"
    assert result["answered_questions"] == 1
    assert result["incorporated_current_cycle"] == 1
    assert result["document_path"] == str(expected_path)
    assert result["document_format"] == "docx"
    assert result["rtf_generated"] is False and result["rtf_path"] == ""


def test_place_questions_failure_is_reported_without_hiding_it(tmp_path: Path) -> None:
    downloader = load_place_downloader()

    class FailingQuestionsModule:
        @staticmethod
        def sync_place_questions(url, destination, username, password):
            raise RuntimeError("PLACE no disponible")

    result = downloader.procesar_preguntas_y_respuestas(
        "https://contrataciondelestado.es/ejemplo",
        str(tmp_path),
        usuario="usuario-prueba",
        contrasena="clave-prueba",
        modulo_preguntas=FailingQuestionsModule,
    )

    assert result["status"] == "error"


def test_place_downloader_reads_credentials_from_suite_settings(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    db_path = tmp_path / "suite.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        conn.executemany(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, '')",
            [
                ("place_username", "usuario-suite"),
                ("place_password", "clave-suite"),
            ],
        )

    assert downloader.credenciales_place_desde_suite(db_path) == ("usuario-suite", "clave-suite")


def test_operational_downloader_uses_suite_credentials_without_prompts(tmp_path: Path) -> None:
    downloader = load_place_downloader()
    db_path = tmp_path / "suite.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        conn.executemany(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, '')",
            [
                ("place_username", "usuario-suite"),
                ("place_password", "clave-suite"),
            ],
        )

    class FakeQuestionsModule:
        @staticmethod
        def sync_place_questions(url, destination, username, password):
            assert username == "usuario-suite"
            assert password == "clave-suite"
            return {
                "status": "no_changes",
                "query_successful": True,
                "authentication_successful": True,
                "total_questions": 0,
                "answered_questions": 0,
                "incorporated_current_cycle": 0,
                "responses_updated": 0,
                "question_updates": 0,
                "changes_detected": False,
                "no_changes": True,
                "rtf_generated": False,
                "rtf_path": "",
                "document_generated": False,
                "document_path": "",
                "document_format": "",
                "previous_review": "",
                "current_review": "2026-07-16T20:00:00+02:00",
                "error_type": "",
                "errors": [],
                "warnings": [],
                "structure_novelties": [],
            }

    result = downloader.procesar_preguntas_y_respuestas(
        "https://contrataciondelestado.es/ejemplo",
        str(tmp_path),
        modulo_preguntas=FakeQuestionsModule,
        db_path=db_path,
    )

    assert result["status"] == "no_changes"
