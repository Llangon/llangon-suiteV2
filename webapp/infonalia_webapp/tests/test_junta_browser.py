import io
import zipfile

import pytest
import requests

from herramientas_python.descargadores.common.download_models import extension_from_content
from herramientas_python.descargadores.junta_andalucia import browser
from herramientas_python.descargadores.junta_andalucia import documents


def test_legacy_junta_url_is_normalized_to_current_portal() -> None:
    legacy = (
        "http://www.juntadeandalucia.es/haciendayadministracionpublica/apl/"
        "pdc_sirec/perfiles-licitaciones/detalle-licitacion.jsf?idExpediente=947853"
    )

    assert browser.normalizar_url_licitacion(legacy) == (
        "https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/"
        "pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=947853"
    )


def test_current_junta_url_remains_canonical() -> None:
    current = (
        "https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/"
        "pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=944739"
    )

    assert browser.normalizar_url_licitacion(current) == current


@pytest.mark.parametrize("error_text", ("net::ERR_CONNECTION_RESET", "net::ERR_TIMED_OUT"))
def test_navigation_surfaces_transient_cdp_errors(error_text: str) -> None:
    class Page:
        @staticmethod
        def call(_method, _params, timeout):
            assert timeout == 25
            return {"errorText": error_text}

    with pytest.raises(browser.JuntaNavigationTransientError, match=error_text.split("::")[-1]) as raised:
        browser.navegar_a_licitacion(Page(), "https://example.test")

    assert browser.error_metadata(raised.value) == ("JUNTA_NAVIGATION_TRANSIENT", True)


def test_non_transient_navigation_error_is_not_marked_retryable() -> None:
    class Page:
        @staticmethod
        def call(_method, _params, timeout):
            assert timeout == 25
            return {"errorText": "net::ERR_INVALID_URL"}

    with pytest.raises(browser.JuntaBrowserError, match="ERR_INVALID_URL") as raised:
        browser.navegar_a_licitacion(Page(), "invalid")

    assert browser.error_metadata(raised.value) == ("JUNTA_BROWSER_ERROR", False)


def test_profile_cleanup_retries_windows_file_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def remove_tree(_path):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError("perfil todavía bloqueado")

    monkeypatch.setattr(browser.shutil, "rmtree", remove_tree)
    monkeypatch.setattr(browser.time, "sleep", lambda _seconds: None)

    assert browser.eliminar_perfil_temporal("temporary-profile") is True
    assert calls == 3


def test_close_chrome_survives_cdp_close_errors_and_waits_after_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenCDP:
        @staticmethod
        def close():
            raise OSError("canal roto")

    class Process:
        def __init__(self):
            self.calls = []

        def terminate(self):
            self.calls.append("terminate")
            raise OSError("terminate bloqueado")

        def kill(self):
            self.calls.append("kill")

        def wait(self, *, timeout):
            self.calls.append(("wait", timeout))

    process = Process()
    removed = []
    monkeypatch.setattr(browser, "eliminar_perfil_temporal", lambda path: removed.append(path))

    browser.cerrar_chrome(
        process,
        "temporary-profile",
        browser=BrokenCDP(),
        page=BrokenCDP(),
    )

    assert process.calls == ["terminate", "kill", ("wait", 5)]
    assert removed == ["temporary-profile"]


def test_browser_start_failure_cleans_process_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pass

    process = Process()
    cleaned = []
    monkeypatch.setattr(browser, "encontrar_chrome", lambda: "chrome.exe")
    monkeypatch.setattr(browser, "puerto_libre", lambda: 9222)
    monkeypatch.setattr(browser.tempfile, "mkdtemp", lambda **_kwargs: "temporary-profile")
    monkeypatch.setattr(browser.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        browser,
        "esperar_cdp",
        lambda _port: (_ for _ in ()).throw(RuntimeError("CDP no disponible")),
    )
    monkeypatch.setattr(browser, "terminar_proceso_chrome", lambda value: cleaned.append(("process", value)))
    monkeypatch.setattr(browser, "eliminar_perfil_temporal", lambda value: cleaned.append(("profile", value)))

    with pytest.raises(RuntimeError, match="CDP no disponible"):
        browser.abrir_chrome()

    assert cleaned == [("process", process), ("profile", "temporary-profile")]


def test_download_session_retries_transient_get_failures() -> None:
    class Page:
        @staticmethod
        def call(method, _params=None, timeout=0):
            if method == "Network.getAllCookies":
                return {"cookies": []}
            if method == "Runtime.evaluate":
                return {"result": {"value": "Mozilla/5.0 test"}}
            raise AssertionError(method)

    session = browser.crear_session_descarga(Page(), "https://example.test/ficha")
    retry = session.get_adapter("https://").max_retries

    assert retry.total == 4
    assert retry.connect == 4
    assert retry.read == 4
    assert 503 in retry.status_forcelist


def test_document_download_retries_connection_reset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class Response:
        content = b"%PDF-1.4 test"
        headers = {"Content-Type": "application/pdf"}

        @staticmethod
        def raise_for_status():
            return None

    class Session:
        def __init__(self):
            self.calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise requests.exceptions.ChunkedEncodingError("connection reset")
            return Response()

    session = Session()
    monkeypatch.setattr(documents.time, "sleep", lambda _seconds: None)

    filename, skipped = documents.descargar_por_url(
        session,
        {"href": "https://example.test/documento/1", "text": "Pliego.PDF"},
        tmp_path,
        "https://example.test/ficha",
    )

    assert session.calls == 2
    assert filename == "Pliego.PDF"
    assert skipped is False
    assert (tmp_path / filename).read_bytes() == b"%PDF-1.4 test"


def test_existing_document_is_reused_without_request(tmp_path) -> None:
    existing = tmp_path / "Pliego.PDF"
    existing.write_bytes(b"%PDF-1.4 existing")

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            raise AssertionError("No debe volver a solicitar un documento existente.")

    filename, skipped = documents.descargar_por_url(
        Session(),
        {"href": "https://example.test/documento/1", "text": "Pliego.PDF"},
        tmp_path,
        "https://example.test/ficha",
    )

    assert filename == existing.name
    assert skipped is True


def test_opendocument_text_keeps_odt_extension() -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr("content.xml", "<office:document/>")

    assert extension_from_content(content.getvalue()) == ".odt"
