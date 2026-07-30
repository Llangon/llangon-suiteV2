from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from herramientas_python.descargadores.common.http import DEFAULT_USER_AGENT
from herramientas_python.descargadores.xunta_galicia import browser as xunta_browser
from herramientas_python.descargadores.xunta_galicia.client import (
    parse_download_call,
    parse_tender_page,
)
from herramientas_python.descargadores.xunta_galicia.documents import (
    XuntaCaptchaBlockedError,
    publish_download,
)
from herramientas_python.descargadores.xunta_galicia.downloader import run_xunta_galicia
from webapp.infonalia_webapp.monitor.tender_rules import ai_category


FIXTURE = Path(__file__).parent / "fixtures" / "xunta" / "licitacion_827794.html"
URL = "https://www.contratosdegalicia.gal/licitacion?N=827794"
PDF_A = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
PDF_B = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Version/1.7>>endobj\n%%EOF\n"


class FakeResponse:
    def __init__(self, content: bytes, url: str = URL):
        self.content = content
        self.url = url

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, content: bytes):
        self.content = content
        self.calls: list[tuple[str, object, bool]] = []

    def get(self, url: str, *, timeout, allow_redirects: bool):
        self.calls.append((url, timeout, allow_redirects))
        return FakeResponse(self.content)


class FakeBrowser:
    def __init__(self, results: dict[str, bytes | BaseException] | None = None):
        self.results = results or {}
        self.open_count = 0
        self.download_calls: list[str] = []
        self.closed = 0

    def open_browser(self):
        self.open_count += 1
        return object(), "fake-profile", object(), 9222

    def create_page(self, _browser, _port, _directory):
        return object()

    def navigate(self, _page, url: str) -> None:
        assert url == URL

    def download_by_click(
        self,
        _page,
        call: str,
        directory: str,
        *,
        expected_extension: str = "",
    ):
        self.download_calls.append(call)
        result = self.results.get(call, PDF_A)
        if isinstance(result, BaseException):
            raise result
        path = Path(directory) / f"download-{len(self.download_calls)}.pdf"
        path.write_bytes(result)
        return path

    def close_browser(self, *_args) -> None:
        self.closed += 1


class RecordingCDP:
    instances: list["RecordingCDP"] = []

    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.calls: list[tuple[str, dict, int]] = []
        self.__class__.instances.append(self)

    def call(self, method: str, params: dict | None = None, timeout: int = 30):
        self.calls.append((method, params or {}, timeout))
        return {}


class FakeProcess:
    def terminate(self) -> None:
        return None

    def wait(self, timeout: int) -> None:
        return None

    def kill(self) -> None:
        return None


def row(call: str, title: str, date: str = "20-04-2026 10:18:18") -> str:
    return (
        f'<tr><td><a href="{call}">{title}</a></td>'
        f"<td>{date}</td><td>Vixente</td>"
        f'<td><a href="{call}">Formato .pdf</a> (1 KB)</td></tr>'
    )


def page_html(rows: list[str], *, extra_anchor: str = "", include_form: bool = True) -> bytes:
    form = '<form id="formDescargaG" action="./descargaG"></form>' if include_form else ""
    html = f"""<!doctype html><html><head><meta charset="ISO-8859-1">
    <title>Detalle procedemento: 827794 - Contratos Públicos de Galicia</title></head><body>
    <div id="consulta-datos-xerais">
      <div class="titulo"><em>Pendente de adxudicar</em></div>
      <div class="organismo"><div class="logo-texto"><a>Consellería de Proba</a></div></div>
      <dl><dt>Referencia</dt><dd>EXP-827794</dd></dl>
      <dl><dt>Obxecto</dt><dd>Contrato de proba</dd></dl>
      <dl><dt>Tipo de procedemento</dt><dd>Aberto</dd></dl>
      <dl><dt>Tipo de contrato</dt><dd>Servizos</dd></dl>
      <dl><dt>Orzamento base de licitación</dt><dd>1.000,00 con IVE</dd></dl>
      <dl><dt>Nº lotes</dt><dd>1</dd></dl>
      <dl><dt>Valor estimado</dt><dd>826,45 sen IVE</dd></dl>
    </div>
    <dl><dt>Data e hora límite:</dt><dd>31/07/2026 23:59</dd></dl>
    {form}<div id="consulta-documentos"><div id="collapseDocInicio"><table>
    {''.join(rows)}</table>{extra_anchor}</div></div></body></html>"""
    return html.encode("iso-8859-1")


def test_cdp_page_uses_public_user_agent_before_navigation(monkeypatch, tmp_path: Path) -> None:
    RecordingCDP.instances.clear()
    response = SimpleNamespace(
        json=lambda: [
            {
                "type": "page",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/test",
            }
        ]
    )
    monkeypatch.setattr(xunta_browser, "CDP", RecordingCDP)
    monkeypatch.setattr(xunta_browser.requests, "get", lambda *_args, **_kwargs: response)
    control = RecordingCDP("ws://127.0.0.1/devtools/browser/test")

    page = xunta_browser.create_page(control, 9222, tmp_path)

    assert (
        "Network.setUserAgentOverride",
        {"userAgent": DEFAULT_USER_AGENT, "platform": "Windows"},
        30,
    ) in page.calls


def test_browser_uses_standard_chrome_offscreen_instead_of_headless(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    profile = tmp_path / "profile"
    profile.mkdir()

    def fake_popen(command, **options):
        captured["command"] = command
        captured["options"] = options
        return FakeProcess()

    monkeypatch.setattr(xunta_browser, "find_browser", lambda: r"C:\Chrome\chrome.exe")
    monkeypatch.setattr(xunta_browser, "_free_port", lambda: 9222)
    monkeypatch.setattr(xunta_browser.tempfile, "mkdtemp", lambda **_kwargs: str(profile))
    monkeypatch.setattr(xunta_browser.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        xunta_browser,
        "_wait_for_cdp",
        lambda _port: {"webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/test"},
    )
    monkeypatch.setattr(xunta_browser, "CDP", RecordingCDP)

    xunta_browser.open_browser()

    command = captured["command"]
    assert "--window-position=-32000,-32000" in command
    assert not any(argument.startswith("--headless") for argument in command)


def test_cdp_navigation_accepts_loaded_form_before_ready_state_complete(monkeypatch) -> None:
    page = RecordingCDP("ws://127.0.0.1/devtools/page/test")
    monkeypatch.setattr(
        xunta_browser,
        "_evaluate",
        lambda *_args, **_kwargs: {
            "form": True,
            "recaptcha": True,
            "blocked": False,
        },
    )

    xunta_browser.navigate(page, URL)

    assert page.calls == [("Page.navigate", {"url": URL}, 15)]


def test_download_wait_ignores_unrelated_chrome_auxiliary_file(tmp_path: Path) -> None:
    (tmp_path / "downloads.htm").write_bytes(b"Cr24 auxiliary browser model")
    expected = tmp_path / "Memoria.pdf"
    expected.write_bytes(PDF_A)

    found = xunta_browser._wait_for_download(
        tmp_path,
        set(),
        1,
        expected_extension=".pdf",
    )

    assert found == expected


def test_fixture_extracts_fifteen_unique_documents_and_metadata() -> None:
    content = FIXTURE.read_text(encoding="utf-8").encode("iso-8859-1")
    page = parse_tender_page(content, URL)

    assert page.complete is True
    assert len(page.documents) == 15
    assert len({item.call for item in page.documents}) == 15
    assert page.general_data["expediente"] == "CPS-2026-0057"
    assert page.general_data["organismo"] == "Consellería de Política Social e Igualdade"
    assert page.relevant_dates == {"fecha_limite": "05/05/2026 23:55"}
    assert page.documents[0].source_url == (
        "https://www.contratosdegalicia.gal/descargaG?F=1&N=827794&T=206&V=1"
    )
    assert page.documents[0].declared_size == int(199.02 * 1024)
    assert {item.section for item in page.documents} >= {
        "collapseDocInicio",
        "collapsePliegos",
        "collapsePregResp",
        "collapseMesa4",
    }


@pytest.mark.parametrize(
    ("call", "expected"),
    (
        ("javascript:mostrarTabla(18,1,2,827794,4)", {"T": "18", "F": "1", "V": "2", "N": "827794", "M": "4"}),
        ("javascript:mostrarTablaPub(7,827794)", {"T": "7", "F": "0", "N": "827794"}),
        ("javascript:mostrarTablaResolucionAdx(9,2,827794)", {"J": "9", "L": "2", "N": "827794"}),
        ("javascript:mostrarTablaFormalizacion(10,3,827794)", {"K2": "10", "L": "3", "N": "827794"}),
        ("javascript:mostrarTablaFicheroAnexo(827794,11)", {"N": "827794", "D": "11"}),
        ("javascript:mostrarTablaFicheroAnexoContrato(827794,12)", {"N": "827794", "DC": "12"}),
        ("javascript:mostrarTablaFicheroAnexoEjecucion(827794,13)", {"N": "827794", "DE": "13"}),
    ),
)
def test_all_official_download_calls_map_to_post_fields(call: str, expected: dict[str, str]) -> None:
    _function, _arguments, fields, source_url = parse_download_call(call, URL)

    assert dict(fields) == expected
    assert source_url.startswith("https://www.contratosdegalicia.gal/descargaG?")


def test_first_run_downloads_and_second_run_reuses_state_without_browser(tmp_path: Path) -> None:
    call = "javascript:mostrarTabla(206,1,1,827794)"
    content = page_html([row(call, "Memoria xustificativa")])
    first_browser = FakeBrowser({call: PDF_A})

    first = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(content),
        browser_api=first_browser,
        logger=lambda _message: None,
    )
    second_browser = FakeBrowser()
    second = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(content),
        browser_api=second_browser,
        logger=lambda _message: None,
    )

    assert first.status == second.status == "success"
    assert first.documents_new == 1 and first.documents_downloaded == 1
    assert second.documents_new == second.documents_modified == 0
    assert first_browser.open_count == first_browser.closed == 1
    assert second_browser.open_count == 0
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256
    assert (tmp_path / ".llangon-xunta" / "documents_state.json").is_file()


def test_modified_document_keeps_previous_file_and_updates_same_identity(tmp_path: Path) -> None:
    call = "javascript:mostrarTabla(206,1,1,827794)"
    initial = page_html([row(call, "Memoria xustificativa")])
    changed = page_html([row(call, "Memoria xustificativa", "21-07-2026 10:00:00")])
    run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(initial),
        browser_api=FakeBrowser({call: PDF_A}),
        logger=lambda _message: None,
    )

    result = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(changed),
        browser_api=FakeBrowser({call: PDF_B}),
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_modified == 1
    assert result.documents_new == 0
    assert "[" in Path(result.artifacts[0].path).name
    assert len(list(tmp_path.glob("Memoria xustificativa*.pdf"))) == 2


def test_complete_inventory_confirms_removal_without_deleting_file(tmp_path: Path) -> None:
    first_call = "javascript:mostrarTabla(206,1,1,827794)"
    second_call = "javascript:mostrarTabla(209,1,1,827794)"
    initial = page_html([row(first_call, "Memoria"), row(second_call, "Aprobación")])
    reduced = page_html([row(first_call, "Memoria")])
    run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(initial),
        browser_api=FakeBrowser({first_call: PDF_A, second_call: PDF_B}),
        logger=lambda _message: None,
    )

    result = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(reduced),
        browser_api=FakeBrowser(),
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.documents_removed == 1
    assert len(result.artifacts) == 1
    assert result.artifacts[0].status == "reused"
    assert result.artifacts[0].source_url
    assert (tmp_path / "Aprobación.pdf").is_file()


def test_recaptcha_block_returns_partial_and_preserves_complete_state(tmp_path: Path) -> None:
    old_call = "javascript:mostrarTabla(206,1,1,827794)"
    new_call = "javascript:mostrarTabla(18,1,1,827794,4)"
    initial = page_html([row(old_call, "Memoria")])
    changed = page_html([row(old_call, "Memoria"), row(new_call, "Acta nova")])
    run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(initial),
        browser_api=FakeBrowser({old_call: PDF_A}),
        logger=lambda _message: None,
    )
    blocked = FakeBrowser(
        {new_call: XuntaCaptchaBlockedError("XUNTA_RECAPTCHA_BLOCKED: reto interactivo")}
    )

    result = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(changed),
        browser_api=blocked,
        logger=lambda _message: None,
    )
    state = json.loads((tmp_path / ".llangon-xunta" / "documents_state.json").read_text(encoding="utf-8"))

    assert result.status == "partial"
    assert len(result.artifacts) == 2
    assert {item.status for item in result.artifacts} == {"reused", "failed"}
    assert "XUNTA_RECAPTCHA_BLOCKED" in result.recoverable_issues[0]
    assert blocked.closed == 1
    assert state["last_complete_keys"] == [result.artifacts[0].source_url]
    assert state["last_run_complete"] is False


def test_unknown_document_function_prevents_complete_snapshot(tmp_path: Path) -> None:
    call = "javascript:mostrarTabla(206,1,1,827794)"
    unknown = '<a href="javascript:mostrarTablaNueva(7,827794)">Documento futuro</a>'
    content = page_html([row(call, "Memoria")], extra_anchor=unknown)

    result = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(content),
        browser_api=FakeBrowser({call: PDF_A}),
        logger=lambda _message: None,
    )

    assert result.status == "partial"
    assert any("mostrarTablaNueva" in warning for warning in result.warnings)


def test_corrupt_state_is_rebuilt_and_missing_local_file_is_downloaded_again(tmp_path: Path) -> None:
    call = "javascript:mostrarTabla(206,1,1,827794)"
    content = page_html([row(call, "Memoria")])
    technical = tmp_path / ".llangon-xunta"
    technical.mkdir()
    (technical / "documents_state.json").write_text("{invalid", encoding="utf-8")
    first_browser = FakeBrowser({call: PDF_A})
    first = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(content),
        browser_api=first_browser,
        logger=lambda _message: None,
    )
    Path(first.artifacts[0].path).unlink()
    second_browser = FakeBrowser({call: PDF_A})

    second = run_xunta_galicia(
        URL,
        tmp_path,
        session=FakeSession(content),
        browser_api=second_browser,
        logger=lambda _message: None,
    )

    assert first.status == second.status == "success"
    assert any("no es legible" in warning for warning in first.warnings)
    assert first_browser.open_count == second_browser.open_count == 1


def test_html_captcha_response_is_never_published(tmp_path: Path) -> None:
    temporary = tmp_path / "respuesta.pdf"
    temporary.write_bytes(b"<!doctype html><html><body>reCAPTCHA</body></html>")
    page = parse_tender_page(
        page_html([row("javascript:mostrarTabla(206,1,1,827794)", "Memoria")]),
        URL,
    )

    with pytest.raises(XuntaCaptchaBlockedError, match="XUNTA_RECAPTCHA_BLOCKED"):
        publish_download(temporary, page.documents[0], tmp_path / "destino")


@pytest.mark.parametrize(
    ("title", "categories", "expected"),
    (
        ("Resolución de adxudicación", ["adjudicacion"], "adjudicacion"),
        ("Requirimento de documentación", ["requerimiento"], "requerimiento"),
        ("Relación de empresas excluídas", ["exclusion"], "exclusion"),
    ),
)
def test_galician_ai_category_aliases(title: str, categories: list[str], expected: str) -> None:
    assert ai_category(title, categories) == expected
