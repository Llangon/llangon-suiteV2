import importlib.util
from pathlib import Path


def load_catalunya_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "herramientas_python" / "Descargar_Catalunya.py"
    spec = importlib.util.spec_from_file_location("descargar_catalunya_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def test_builds_current_detail_api_url() -> None:
    downloader = load_catalunya_module()
    url = (
        "https://contractaciopublica.cat/ca/detall-publicacio/"
        "7c0d79ac-3c43-432a-9b37-896fb0c436ec/300822730"
    )

    assert downloader.url_api_detall_publicacion(url) == (
        "https://contractaciopublica.cat/portal-api/detall-publicacio-expedient/"
        "7c0d79ac-3c43-432a-9b37-896fb0c436ec/300822730"
    )


def test_extracts_current_documents_from_detail_api() -> None:
    downloader = load_catalunya_module()
    url = "https://contractaciopublica.cat/ca/detall-publicacio/expedient-1/300822730"
    payload = {
        "publicacioId": 300822730,
        "publicacioAntiga": False,
        "dades": {
            "publicacio": {
                "dadesPublicacio": {
                    "plecsDeClausulesAdministratives": {
                        "docs": [
                            {
                                "id": 302403357,
                                "titol": "Plec administratiu.pdf",
                                "hash": "B3016058D0A08C4F52EC1DB6C494C969",
                            }
                        ]
                    },
                    "anotacio": {
                        "id": 99,
                        "titol": "No es un fichero",
                        "hash": "IGNORAR",
                        "subtipusDocument": 1,
                    },
                }
            }
        },
    }
    session = FakeSession(payload)

    documentos = downloader.extraer_documentos_de_api(session, url)

    assert session.calls[0][0].endswith("/detall-publicacio-expedient/expedient-1/300822730")
    assert documentos == [
        {
            "href": (
                "https://contractaciopublica.cat/portal-api/descarrega-document/"
                "302403357/B3016058D0A08C4F52EC1DB6C494C969"
            ),
            "text": "Plec administratiu.pdf",
            "title": "Plec administratiu.pdf",
            "download": "Plec administratiu.pdf",
            "itemText": "Plec administratiu.pdf",
            "section": "docs",
            "fecha": "",
        }
    ]


def test_extracts_legacy_documents_with_publication_id() -> None:
    downloader = load_catalunya_module()
    url = "https://contractaciopublica.cat/es/detall-publicacio/300000001"
    payload = {
        "publicacioId": 300000001,
        "publicacioAntiga": True,
        "dades": {
            "documentacio": [
                {
                    "titol": "Documento antiguo.pdf",
                    "hash": "ABCDEF123456",
                    "subtipusDocument": 0,
                }
            ]
        },
    }

    documentos = downloader.extraer_documentos_de_api(FakeSession(payload), url)

    assert documentos[0]["href"] == (
        "https://contractaciopublica.cat/portal-api/descarrega-document-antic/"
        "300000001/ABCDEF123456"
    )
