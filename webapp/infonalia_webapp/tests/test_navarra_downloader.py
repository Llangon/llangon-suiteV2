import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "herramientas_python" / "Descargar_Navarra.py"
CODIGO = "260715105302B4482A94"
URL_PCN = f"https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod={CODIGO}"
URL_PLENA = f"https://licitacionelectronica.navarra.es/licitador/licitadores/detalle/{CODIGO}/s"


def load_module():
    spec = importlib.util.spec_from_file_location("descargar_navarra_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, *, json_data=None, content=b"", url="", headers=None):
        self._json_data = json_data
        self.content = content
        self.url = url
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert self.responses, f"Peticion no prevista: {url}"
        return self.responses.pop(0)


def test_extracts_pcn_documents_and_plena_link() -> None:
    module = load_module()
    html = f"""
    <html><body>
      <a href="mtoGeneraDocumento.aspx?DOA={CODIGO}&amp;DOL=1">
        Pliego suministro comida 0 a 3 años.pdf
      </a>
      <a href="https://example.test/documento.pdf">No permitido</a>
      <a href="{URL_PLENA}">Ver las aclaraciones</a>
    </body></html>
    """
    soup = module.BeautifulSoup(html, "html.parser")

    documentos = module.extraer_documentos_pcn(soup, URL_PCN)

    assert documentos == [{
        "url": f"https://hacienda.navarra.es/sicpportal/mtoGeneraDocumento.aspx?DOA={CODIGO}&DOL=1",
        "nombre_logico": "Pliego suministro comida 0 a 3 años.pdf",
        "origen": "PCN",
    }]
    assert module.extraer_url_plena(soup, URL_PCN) == URL_PLENA


def test_consultar_plena_returns_pliegos_and_entity_documents() -> None:
    module = load_module()
    session = FakeSession([
        FakeResponse(json_data={
            "idExpediente": 863,
            "documentos": [{
                "linea": 1,
                "nombreFichero": "Pliego suministro comida 0 a 3 años.pdf",
            }],
        }),
        FakeResponse(json_data=[{
            "id": 44,
            "nombreDocumento": "Nuevo documento.pdf",
            "referenciaDocumento": "expedientes/863/publicados",
        }]),
    ])

    pliegos, adicionales = module.consultar_plena(session, CODIGO, URL_PLENA)

    assert len(pliegos) == 1
    assert pliegos[0]["url"].endswith(f"DOA={CODIGO}&DOL=1")
    assert adicionales[0]["nombre_logico"] == "Nuevo documento.pdf"
    assert "downloadFileAllowAnonymous?fullPath=" in adicionales[0]["url"]
    assert "expedientes%2F863%2Fpublicados%2FNuevo%20documento.pdf" in adicionales[0]["url"]
    assert all(call[1]["headers"]["Origin"] == "https://licitacionelectronica.navarra.es" for call in session.calls)


def test_main_downloads_old_pliego_once_and_checks_only_plena_documents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    html = f"""
    <html><body>
      <a href="mtoGeneraDocumento.aspx?DOA={CODIGO}&amp;DOL=1">Pliego.pdf</a>
      <a href="{URL_PLENA}">Ver las aclaraciones</a>
    </body></html>
    """.encode("iso-8859-1")
    session = FakeSession([
        FakeResponse(content=html, url=URL_PCN),
        FakeResponse(json_data={
            "idExpediente": 863,
            "documentos": [{"linea": 1, "nombreFichero": "Pliego.pdf"}],
        }),
        FakeResponse(json_data=[{
            "id": 45,
            "nombreDocumento": "Documento posterior.pdf",
            "referenciaDocumento": "expedientes/863/publicados",
        }]),
    ])
    descargados = []

    monkeypatch.setattr(module, "crear_session", lambda: session)
    monkeypatch.setattr(
        module,
        "descargar_documento",
        lambda _session, trabajo, _destino, _referer: descargados.append(trabajo) or ("descargado", trabajo["nombre_logico"]),
    )
    monkeypatch.setattr(sys, "argv", ["Descargar_Navarra.py", URL_PCN, "--destino", str(tmp_path)])

    module.main()

    assert [trabajo["nombre_logico"] for trabajo in descargados] == [
        "Pliego.pdf",
        "Documento posterior.pdf",
    ]
    urls_consultadas = [call[0] for call in session.calls]
    assert any("getExpedienteAllowAnonymous" in url for url in urls_consultadas)
    assert any("getDocumentosAnonymous" in url for url in urls_consultadas)
    assert not any("Preguntas" in url or "preguntas" in url for url in urls_consultadas)


def test_accepts_direct_plena_url_and_builds_old_pliego_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    session = FakeSession([
        FakeResponse(json_data={
            "idExpediente": 863,
            "documentos": [{"linea": 2, "nombreFichero": "Pliego técnico.pdf"}],
        }),
        FakeResponse(json_data=[]),
    ])
    descargados = []
    monkeypatch.setattr(module, "crear_session", lambda: session)
    monkeypatch.setattr(
        module,
        "descargar_documento",
        lambda _session, trabajo, _destino, _referer: descargados.append(trabajo) or ("descargado", trabajo["nombre_logico"]),
    )
    monkeypatch.setattr(sys, "argv", ["Descargar_Navarra.py", URL_PLENA, "--destino", str(tmp_path)])

    module.main()

    assert len(descargados) == 1
    assert descargados[0]["url"].endswith(f"DOA={CODIGO}&DOL=2")

