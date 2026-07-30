from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from herramientas_python.descargadores.euskadi.client import (
    extraer_documentos,
    extraer_paquetes_modelos,
)
from herramientas_python.descargadores.euskadi.documents import descargar_documento
from herramientas_python.descargadores.euskadi.downloader import run_euskadi


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        content: bytes = b"",
        url: str = "https://www.contratacion.euskadi.eus/expediente",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.content = content or text.encode("utf-8")
        self.url = url
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None


class SequentialSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)

    def get(self, _url: str, **_kwargs) -> FakeResponse:
        if not self.responses:
            raise AssertionError("GET no previsto")
        return self.responses.pop(0)


def test_realistic_page_extracts_individual_files_and_only_models_package() -> None:
    html = """
    <h1>2026/01444</h1>
    <a onclick="descargarFicheroPID(731085, 78)">Descarga de los ficheros</a>
    <a onclick="descargarFicheroPID(731085, 109)">Descargar los modelos</a>
    <div id="tabs-5">
      <a onclick="descargarFichero('6068253')">
        Pliego de Prescripciones Técnicas.pdf
      </a>
      <a onclick="descargarFichero('6068255')">Plantilla Fórmulas.xlsx</a>
      <a onclick="descargarFichero('6068257')">DEUC.zip</a>
    </div>
    <div id="tabs-10">
      <a onclick="descargarFicheroContrato('7000000')">Contrato firmado.pdf</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    documents = extraer_documentos(soup)
    packages = extraer_paquetes_modelos(soup, "2026_01444")

    assert [item["remote_id"] for item in documents] == [
        "6068253",
        "6068255",
        "6068257",
        "7000000",
    ]
    assert [item["section"] for item in documents] == [
        "Ficheros",
        "Ficheros",
        "Ficheros",
        "Contrato",
    ]
    assert "descargaFicheroContratoPorIdFichero" in documents[-1]["url"]
    assert len(packages) == 1
    assert packages[0]["remote_id"] == "PID:731085:109"
    assert packages[0]["role"] == "models_package"
    assert "idTipoFichero=109" in packages[0]["url"]


def test_content_change_is_preserved_as_a_version_and_then_reused(tmp_path: Path) -> None:
    document = {
        "url": "https://example.test/document",
        "nombre_logico": "Pliego.pdf",
    }
    first = FakeResponse(
        content=b"%PDF-1.4 primera version",
        headers={"Content-Type": "application/pdf"},
    )
    changed = FakeResponse(
        content=b"%PDF-1.4 segunda version",
        headers={"Content-Type": "application/pdf"},
    )
    repeated = FakeResponse(
        content=b"%PDF-1.4 segunda version",
        headers={"Content-Type": "application/pdf"},
    )
    logger = lambda _message: None

    first_status, first_name = descargar_documento(
        SequentialSession([first]), document, tmp_path, document["url"], logger=logger
    )
    changed_status, changed_name = descargar_documento(
        SequentialSession([changed]), document, tmp_path, document["url"], logger=logger
    )
    repeated_status, repeated_name = descargar_documento(
        SequentialSession([repeated]), document, tmp_path, document["url"], logger=logger
    )

    assert first_status == "descargado"
    assert changed_status == "actualizado"
    assert changed_name != first_name
    assert repeated_status == "omitido"
    assert repeated_name == changed_name
    assert sorted(path.read_bytes() for path in tmp_path.iterdir()) == sorted(
        [first.content, changed.content]
    )


def test_dokusi_path_prefix_does_not_become_filename_underscore(tmp_path: Path) -> None:
    document = {
        "url": "https://example.test/document",
        "nombre_logico": "Pliego técnico.pdf",
    }
    response = FakeResponse(
        content=b"%PDF-1.4 contenido",
        headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="/Pliego técnico.pdf"',
        },
    )

    status, name = descargar_documento(
        SequentialSession([response]),
        document,
        tmp_path,
        document["url"],
        logger=lambda _message: None,
    )

    assert status == "descargado"
    assert name == "Pliego técnico.pdf"
    assert (tmp_path / name).is_file()


def test_run_reports_remote_metadata_and_modified_document(tmp_path: Path) -> None:
    url = "https://www.contratacion.euskadi.eus/anuncio_contratacion/1"
    html = """
    <h1>EXP-EU-1</h1>
    <div id="tabs-5">
      <a onclick="descargarFichero('10')">Pliego.pdf</a>
    </div>
    """

    def modified_download(_session, _document, *_args, **_kwargs):
        path = tmp_path / "Pliego [actualizado].pdf"
        path.write_bytes(b"%PDF-1.4 actualizado")
        return "actualizado", path.name

    result = run_euskadi(
        url,
        tmp_path,
        session=SequentialSession([FakeResponse(text=html, url=url)]),
        download_document=modified_download,
        logger=lambda _message: None,
    )

    assert result.status == "success"
    assert result.changes_detected is True
    assert result.documents_downloaded == 1
    assert result.documents_new == 0
    assert result.documents_modified == 1
    assert result.artifacts[0].status == "modified"
    assert result.artifacts[0].remote_id == "10"
    assert result.artifacts[0].section == "Ficheros"


def test_run_is_failed_when_every_document_fails(tmp_path: Path) -> None:
    url = "https://www.contratacion.euskadi.eus/anuncio_contratacion/2"
    html = '<h1>EXP-EU-2</h1><a onclick="descargarFichero(20)">Pliego.pdf</a>'

    def failed_download(*_args, **_kwargs):
        raise OSError("fallo simulado")

    result = run_euskadi(
        url,
        tmp_path,
        session=SequentialSession([FakeResponse(text=html, url=url)]),
        download_document=failed_download,
        logger=lambda _message: None,
    )

    assert result.status == "failed"
    assert result.error == "Pliego.pdf: fallo simulado"
    assert result.block_completeness == {"documents": "invalid"}
    assert result.documents_downloaded == 0
