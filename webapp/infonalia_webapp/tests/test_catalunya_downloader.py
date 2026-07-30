import importlib.util
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import requests

from herramientas_python.descargadores.catalunya import CATALUNYA_STATE_LAYOUT
from herramientas_python.descargadores.catalunya.downloader import (
    ejecutar_descarga_catalunya,
    regenerar_docx_catalunya,
    run_catalunya,
)
from herramientas_python.descargadores.catalunya.documents import (
    extraer_inventario_documentos_de_api,
)
from herramientas_python.descargadores.common import safe_files as safe_files_module
from herramientas_python.descargadores.common.question_models import SyncResult
from herramientas_python.descargadores.common.question_models import format_question_datetime
from herramientas_python.descargadores.catalunya.questions import obtener_snapshot_preguntas
from herramientas_python.descargadores.common.question_state import state_file
from herramientas_python.descargadores.common.question_workflow import record_successful_review
from herramientas_python.descargadores.common.safe_files import write_bytes_content_aware


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


def test_catalunya_facade_redirects_to_platform_modules() -> None:
    downloader = load_catalunya_module()

    assert downloader.extraer_documentos_de_api.__module__.endswith("catalunya.documents")
    assert downloader.extraer_documentos_renderizados.__module__.endswith("catalunya.browser_fallback")
    assert downloader.obtener_snapshot_preguntas.__module__.endswith("catalunya.questions")
    assert downloader.ejecutar_descarga_catalunya.__module__.endswith("catalunya.downloader")


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


PROFILE_URL = (
    "https://contractaciopublica.cat/es/detall-publicacio/"
    "7b9b64bc-a2a0-452f-827d-3988e48d8011/300824573"
)
EXPEDIENT_ID = "7b9b64bc-a2a0-452f-827d-3988e48d8011"


def response_item(identifier: int, published_at: str, question: str, answer: str, *, amendment=False):
    return {
        "id": identifier,
        "titol": question,
        "descripcio": answer,
        "dataPublicacio": published_at,
        "esEsmena": amendment,
    }


def response_detail(
    identifier: int,
    published_at: str,
    question: str,
    answer: str,
    *,
    navigation=None,
    documents=None,
    amendment_reason: str = "",
):
    return {
        "expedientId": EXPEDIENT_ID,
        "dataPublicacio": published_at,
        "despublicat": None,
        "navegacioEsmenes": navigation
        or [{"publicacioId": identifier, "dataPublicacio": published_at, "tipusEsmena": None}],
        "dades": {
            "titol": question,
            "descripcio": answer,
            "documents": documents,
            "lots": None,
            "linkInteres": None,
            "tipusEsmena": {"text": "Esmena"} if amendment_reason else None,
            "descripcioEsmena": amendment_reason or None,
        },
    }


class RoutedSession:
    def __init__(self, *, page_total: int = 2):
        self.calls = []
        self.page_total = page_total
        self.items = [
            response_item(
                300836900,
                "2026-07-17T12:40:08.727Z",
                "¿Se admite saborizado?",
                "No; debe ser neutro.",
            ),
            response_item(
                300832162,
                "2026-07-14T08:40:17.498Z",
                "¿Pueden publicar el Excel corregido?",
                "Se adjunta corregido.",
            ),
        ]
        self.details = {
            300836900: response_detail(
                300836900,
                "2026-07-17T12:40:08.727Z",
                "¿Se admite saborizado?",
                "No; debe ser neutro.",
            ),
            300832162: response_detail(
                300832162,
                "2026-07-14T08:40:17.498Z",
                "¿Pueden publicar el Excel corregido?",
                "Se adjunta corregido.",
                documents={
                    "id": 302431795,
                    "titol": "Annex 16 Oferta economica LOT15.xlsx",
                    "hash": "4DA8784AB985410853D67C2EDDA6650E",
                    "idioma": "ca",
                    "mida": 14595,
                },
            ),
        }

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/detall-publicacio-expedient/" in url:
            return FakeResponse(
                {
                    "expedientId": EXPEDIENT_ID,
                    "publicacioId": 300824573,
                    "publicacioAntiga": False,
                    "codiExpedient": "CS/AH02/1101474371/27/AMUP",
                    "titol": "Subministrament de Fórmules enteral",
                    "dades": {
                        "publicacio": {
                            "dadesPublicacio": {
                                "dataTerminiPresentacioOSolicitud": "2026-07-20T12:00:00Z"
                            }
                        }
                    },
                }
            )
        if "/informacio-basica/" in url:
            return FakeResponse(
                {
                    "expedientId": EXPEDIENT_ID,
                    "codiExpedient": "CS/AH02/1101474371/27/AMUP",
                    "denominacio": "Subministrament de Fórmules enteral",
                    "organ": "ICS - Hospital Universitari de Bellvitge",
                    "accesExclusiu": False,
                    "noAdmetrePreguntes": False,
                }
            )
        if "/respostes/" in url:
            page = int((kwargs.get("params") or {}).get("page", 0))
            content = [self.items[page]] if page < len(self.items) else []
            return FakeResponse(
                {
                    "content": content,
                    "totalPages": self.page_total,
                    "totalElements": len(self.items),
                    "number": page,
                    "size": 1,
                }
            )
        if "/detall-avis/resposta/" in url:
            identifier = int(url.rsplit("/", 1)[1])
            return FakeResponse(self.details[identifier])
        raise AssertionError(f"GET no esperado: {url}")


class BinaryResponse:
    def __init__(self, content: bytes, *, content_type: str):
        self.content = content
        self.headers = {"Content-Type": content_type, "Content-Disposition": ""}

    def raise_for_status(self):
        return None


class DownloadSession(RoutedSession):
    def get(self, url, **kwargs):
        if "/descarrega-document/" in url:
            self.calls.append((url, kwargs))
            return BinaryResponse(
                b"contenido excel simulado",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        return super().get(url, **kwargs)


def publication_document(
    document_id: int,
    title: str,
    document_hash: str,
) -> dict[str, object]:
    return {
        "id": document_id,
        "titol": title,
        "hash": document_hash,
    }


def publication_payload(
    publication_id: int,
    published_at: str,
    *,
    documents: list[dict[str, object]],
    amendments: list[tuple[int, str]] | None = None,
    phases: list[tuple[int, str]] | None = None,
    publication_type: str = "Publicación",
) -> dict[str, object]:
    def navigation(values: list[tuple[int, str]] | None) -> list[dict[str, object]]:
        return [
            {
                "publicacioId": identifier,
                "dataPublicacio": date,
                "tipusEsmena": None,
            }
            for identifier, date in (values or [])
        ]

    return {
        "expedientId": EXPEDIENT_ID,
        "publicacioId": publication_id,
        "publicacioAntiga": False,
        "navegacioEsmenes": navigation(amendments),
        "navegacioFases": navigation(phases),
        "navegacioCpp": [],
        "dades": {
            "dataPublicacioReal": published_at,
            "publicacio": {
                "tipusEsmena": {"text": publication_type},
                "dadesPublicacio": {
                    "altresDocuments": {
                        "docs": documents,
                    }
                },
            },
        },
    }


class PublicationHistorySession:
    def __init__(
        self,
        payloads: dict[int, dict[str, object]],
        *,
        contents: dict[int, bytes] | None = None,
        failed_publications: set[int] | None = None,
    ):
        self.payloads = payloads
        self.contents = contents or {}
        self.failed_publications = failed_publications or set()
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/detall-publicacio-expedient/" in url:
            publication_id = int(url.rstrip("/").rsplit("/", 1)[1])
            if publication_id in self.failed_publications:
                raise requests.ConnectionError("fallo simulado")
            return FakeResponse(self.payloads[publication_id])
        if "/descarrega-document/" in url:
            document_id = int(url.split("/descarrega-document/", 1)[1].split("/", 1)[0])
            return BinaryResponse(
                self.contents[document_id],
                content_type="application/pdf",
            )
        raise AssertionError(f"GET no esperado: {url}")


class ExclusiveSession(RoutedSession):
    def get(self, url, **kwargs):
        response = super().get(url, **kwargs)
        if "/informacio-basica/" in url:
            response.payload["accesExclusiu"] = True
        return response


def test_document_inventory_walks_amendments_and_all_phases_from_any_publication() -> None:
    dates = {
        300803161: "2026-06-18T05:36:13.214Z",
        300824573: "2026-07-07T06:22:14.494Z",
        300828471: "2026-07-10T05:56:13.562Z",
        300829338: "2026-07-10T11:26:19.997Z",
    }
    first_phase = [(300803161, dates[300803161]), (300824573, dates[300824573])]
    second_phase = [(300828471, dates[300828471]), (300829338, dates[300829338])]
    phases = [(300824573, dates[300824573]), (300829338, dates[300829338])]
    payloads = {
        300803161: publication_payload(
            300803161,
            dates[300803161],
            documents=[publication_document(401, "Inicial.pdf", "HASH-INITIAL")],
            amendments=first_phase,
            phases=phases,
            publication_type="Publicación inicial",
        ),
        300824573: publication_payload(
            300824573,
            dates[300824573],
            documents=[publication_document(402, "Correccion.pdf", "HASH-CORRECTION")],
            amendments=first_phase,
            phases=phases,
            publication_type="Correcció",
        ),
        300828471: publication_payload(
            300828471,
            dates[300828471],
            documents=[publication_document(403, "Enmienda.pdf", "HASH-AMENDMENT")],
            amendments=second_phase,
            phases=phases,
            publication_type="Esmena",
        ),
        300829338: publication_payload(
            300829338,
            dates[300829338],
            documents=[publication_document(404, "Final.pdf", "HASH-FINAL")],
            amendments=second_phase,
            phases=phases,
            publication_type="Correcció",
        ),
    }
    session = PublicationHistorySession(payloads)

    inventory = extraer_inventario_documentos_de_api(session, PROFILE_URL)

    assert inventory.complete is True
    assert inventory.publication_ids == [
        "300803161",
        "300824573",
        "300828471",
        "300829338",
    ]
    assert [item["publication_id"] for item in inventory.links] == inventory.publication_ids
    assert [item["publication_type"] for item in inventory.publications] == [
        "Publicación inicial",
        "Correcció",
        "Esmena",
        "Correcció",
    ]
    assert inventory.publications[1]["publication_folder"] == (
        "2026-07-07 - Correcció - 300824573"
    )
    detail_calls = [url for url, _kwargs in session.calls if "/detall-publicacio-expedient/" in url]
    assert len(detail_calls) == 4
    assert len(set(detail_calls)) == 4


def test_same_remote_title_and_hash_never_hide_different_bytes(tmp_path: Path) -> None:
    dates = {
        300824573: "2026-07-07T06:22:14.494Z",
        300829338: "2026-07-10T11:26:19.997Z",
    }
    navigation = list(dates.items())
    payloads = {
        publication_id: publication_payload(
            publication_id,
            published_at,
            documents=[
                publication_document(
                    501 if publication_id == 300824573 else 502,
                    "Anexo corregido.pdf",
                    "MISMO-HASH-REMOTO",
                )
            ],
            amendments=navigation,
        )
        for publication_id, published_at in dates.items()
    }
    session = PublicationHistorySession(
        payloads,
        contents={
            501: b"%PDF-1.4 contenido de la primera publicacion",
            502: b"%PDF-1.4 contenido diferente de la segunda publicacion",
        },
    )

    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )

    assert result.status == "documents"
    assert result.documents_found == 2
    assert result.documents_downloaded == 2
    document_items = [
        item for item in result.downloaded_documents if item["role"] == "document"
    ]
    publication_items = [
        item for item in result.downloaded_documents if item["role"] == "publication"
    ]
    paths = [Path(item["path"]) for item in document_items]
    assert len(set(paths)) == 2
    assert {path.read_bytes() for path in paths} == set(session.contents.values())
    assert len(publication_items) == 2
    assert {path.parent.name for path in paths} == {
        "2026-07-07 - Publicación - 300824573",
        "2026-07-10 - Publicación - 300829338",
    }
    assert all(path.parent.parent == tmp_path for path in paths)
    document_calls = [url for url, _kwargs in session.calls if "/descarrega-document/" in url]
    assert len(document_calls) == 2


def test_identical_republished_bytes_are_stored_once_per_publication(
    tmp_path: Path,
) -> None:
    dates = {
        300824573: "2026-07-07T06:22:14.494Z",
        300829338: "2026-07-10T11:26:19.997Z",
    }
    navigation = list(dates.items())
    payloads = {
        publication_id: publication_payload(
            publication_id,
            published_at,
            documents=[
                publication_document(
                    601 if publication_id == 300824573 else 602,
                    "Documento comun.pdf",
                    "MISMO-HASH-REMOTO",
                )
            ],
            amendments=navigation,
        )
        for publication_id, published_at in dates.items()
    }
    content = b"%PDF-1.4 contenido exactamente igual"
    session = PublicationHistorySession(
        payloads,
        contents={601: content, 602: content},
    )

    first = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )
    second = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )

    assert first.documents_found == 2 and first.documents_downloaded == 2
    assert second.documents_found == 2 and second.documents_skipped == 2
    assert first.changes_detected is True and second.changes_detected is False
    first_documents = [
        item for item in first.downloaded_documents if item["role"] == "document"
    ]
    first_publications = [
        item for item in first.downloaded_documents if item["role"] == "publication"
    ]
    assert len(first_documents) == len(first_publications) == 2
    assert len({Path(item["path"]).parent for item in first_documents}) == 2
    assert all(Path(item["path"]).read_bytes() == content for item in first_documents)
    assert not [
        item for item in second.downloaded_documents if item["role"] == "publication"
    ]
    assert len(
        [item for item in second.reused_documents if item["role"] == "publication"]
    ) == 2
    document_calls = [url for url, _kwargs in session.calls if "/descarrega-document/" in url]
    assert len(document_calls) == 4


def test_neutral_result_exposes_publication_folders_without_treating_them_as_files(
    tmp_path: Path,
) -> None:
    dates = {
        300824573: "2026-07-07T06:22:14.494Z",
        300829338: "2026-07-10T11:26:19.997Z",
    }
    payloads = {
        publication_id: publication_payload(
            publication_id,
            published_at,
            documents=[
                publication_document(
                    651 if publication_id == 300824573 else 652,
                    "Documento comun.pdf",
                    "HASH-COMUN",
                )
            ],
            amendments=list(dates.items()),
            publication_type="Correcció",
        )
        for publication_id, published_at in dates.items()
    }
    session = PublicationHistorySession(
        payloads,
        contents={
            651: b"%PDF-1.4 contenido comun",
            652: b"%PDF-1.4 contenido comun",
        },
    )

    result = run_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )

    publication_artifacts = [
        item for item in result.artifacts if item.role == "publication"
    ]
    document_artifacts = [
        item for item in result.artifacts if item.role == "document"
    ]
    assert len(publication_artifacts) == len(document_artifacts) == 2
    assert result.changes_detected is True
    assert result.documents_found == result.documents_downloaded == 2
    assert all(Path(item.path).is_dir() for item in publication_artifacts)
    assert all(Path(item.path).is_file() for item in document_artifacts)
    assert all(Path(path).is_file() for path in result.files_created)


def test_publication_without_documents_still_creates_and_reports_its_folder(
    tmp_path: Path,
) -> None:
    payloads = {
        300824573: publication_payload(
            300824573,
            "2026-07-07T06:22:14.494Z",
            documents=[],
            publication_type="Correcció",
        )
    }
    session = PublicationHistorySession(payloads)

    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )

    publication_items = [
        item for item in result.downloaded_documents if item["role"] == "publication"
    ]
    assert result.documents_found == result.documents_downloaded == 0
    assert result.changes_detected is True
    assert len(publication_items) == 1
    folder = Path(publication_items[0]["path"])
    assert folder.is_dir()
    assert folder.name == "2026-07-07 - Correcció - 300824573"


def test_unreachable_related_publication_makes_document_inventory_partial(
    tmp_path: Path,
) -> None:
    dates = {
        300824573: "2026-07-07T06:22:14.494Z",
        300829338: "2026-07-10T11:26:19.997Z",
    }
    payloads = {
        300824573: publication_payload(
            300824573,
            dates[300824573],
            documents=[publication_document(701, "Disponible.pdf", "HASH-AVAILABLE")],
            amendments=list(dates.items()),
        ),
    }
    session = PublicationHistorySession(
        payloads,
        contents={701: b"%PDF-1.4 disponible"},
        failed_publications={300829338},
    )

    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        include_questions=False,
        log=lambda _message: None,
    )

    assert result.status == "partial"
    assert result.documents_found == 1 and result.documents_downloaded == 1
    assert any("300829338" in error for error in result.errors)


def document_text(path: Path) -> str:
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    return "\n".join(
        "".join(node.text or "" for node in paragraph.iter(f"{{{namespace}}}t"))
        for paragraph in root.iter(f"{{{namespace}}}p")
    )


def test_extracts_complete_paginated_question_snapshot_with_response_attachment() -> None:
    session = RoutedSession()

    snapshot = obtener_snapshot_preguntas(session, PROFILE_URL, page_size=1)

    assert snapshot.complete is True
    assert snapshot.platform == "CATALUNYA"
    assert snapshot.metadata["expediente"] == "CS/AH02/1101474371/27/AMUP"
    assert snapshot.metadata["display_timezone"] == "Europe/Madrid"
    assert len(snapshot.questions) == 2
    newest, attached = snapshot.questions
    assert newest.asked_at == ""
    assert newest.answered_at == "2026-07-17T12:40:08.727Z"
    assert attached.attachments[0].role == "answer"
    assert attached.attachments[0].name == "Annex 16 Oferta economica LOT15.xlsx"
    assert attached.attachments[0].url.endswith(
        "/descarrega-document/302431795/4DA8784AB985410853D67C2EDDA6650E"
    )
    assert all(call[0].startswith("https://contractaciopublica.cat/") for call in session.calls)


def test_catalunya_iso_dates_follow_madrid_summer_and_winter_time() -> None:
    assert format_question_datetime(
        "2026-07-17T12:40:08.727Z",
        timezone_name="Europe/Madrid",
    ) == "17-07-2026 a las 14:40"
    assert format_question_datetime(
        "2026-01-17T12:40:08Z",
        timezone_name="Europe/Madrid",
    ) == "17-01-2026 a las 13:40"
    assert format_question_datetime("2026-07-17T12:40:08") == "17-07-2026 a las 12:40"


def test_catalunya_state_docx_date_and_no_change_are_independent_from_place(tmp_path: Path) -> None:
    snapshot = obtener_snapshot_preguntas(RoutedSession(), PROFILE_URL, page_size=1)
    reviewed_at = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

    first = record_successful_review(
        tmp_path,
        snapshot.metadata,
        snapshot.questions,
        reviewed_at=reviewed_at,
        platform="CATALUNYA",
        authentication_required=False,
        layout=CATALUNYA_STATE_LAYOUT,
    )
    second = record_successful_review(
        tmp_path,
        snapshot.metadata,
        snapshot.questions,
        reviewed_at=datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc),
        platform="CATALUNYA",
        authentication_required=False,
        layout=CATALUNYA_STATE_LAYOUT,
    )

    assert first.document_generated is True and first.platform == "CATALUNYA"
    assert first.authentication_required is False
    assert second.no_changes is True and second.document_generated is False
    assert not (tmp_path / ".llangon-place").exists()
    state_path = state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    stored = sorted(state["questions"].values(), key=lambda item: item["number"])[0]
    newest_stored = max(state["questions"].values(), key=lambda item: item["number"])
    assert "source_id" in stored and "place_source_id" not in stored
    assert newest_stored["asked_at"] == ""
    assert newest_stored["answered_at"] == "2026-07-17T12:40:08.727Z"
    text = document_text(Path(first.document_path))
    assert "Pregunta 2 del 17-07-2026 a las 14:40" in text
    assert "Respuesta publicada el 17-07-2026 a las 14:40." not in text
    assert "Archivos adjuntos a la respuesta" in text


def test_amendment_chain_keeps_number_and_creates_a_new_version(tmp_path: Path) -> None:
    session = RoutedSession(page_total=1)
    session.items = [
        response_item(90, "2026-07-14T08:40:17Z", "Pregunta", "Respuesta")
    ]
    session.details = {
        90: response_detail(90, "2026-07-14T08:40:17Z", "Pregunta", "Respuesta")
    }
    initial = obtener_snapshot_preguntas(session, PROFILE_URL, page_size=20)
    record_successful_review(
        tmp_path,
        initial.metadata,
        initial.questions,
        reviewed_at=datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc),
        layout=CATALUNYA_STATE_LAYOUT,
        platform="CATALUNYA",
        authentication_required=False,
    )
    session.items = [
        response_item(102, "2026-07-18T08:40:17Z", "Pregunta", "Respuesta", amendment=True)
    ]
    session.details = {
        102: response_detail(
            102,
            "2026-07-18T08:40:17Z",
            "Pregunta",
            "Respuesta",
            navigation=[
                {"publicacioId": 90, "dataPublicacio": "2026-07-14T08:40:17Z"},
                {"publicacioId": 102, "dataPublicacio": "2026-07-18T08:40:17Z"},
            ],
            amendment_reason="Corrección formal",
        )
    }
    changed = obtener_snapshot_preguntas(session, PROFILE_URL, page_size=20)
    result = record_successful_review(
        tmp_path,
        changed.metadata,
        changed.questions,
        reviewed_at=datetime(2026, 7, 18, 11, 0, tzinfo=timezone.utc),
        layout=CATALUNYA_STATE_LAYOUT,
        platform="CATALUNYA",
        authentication_required=False,
    )

    state = json.loads(state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT).read_text(encoding="utf-8"))
    stored = next(iter(state["questions"].values()))
    assert result.responses_updated == 1
    assert stored["source_id"] == "90"
    assert stored["current_source_id"] == "102"
    assert stored["number"] == 1
    assert len(stored["versions"]) == 2
    changed_text = document_text(Path(result.document_path))
    assert "Pregunta 1 del 18-07-2026 a las 10:40" in changed_text
    assert "Respuesta publicada el 18-07-2026 a las 10:40." not in changed_text


def test_incomplete_pagination_is_rejected_before_state_changes() -> None:
    session = RoutedSession(page_total=3)

    with pytest.raises(Exception, match="anunció 2 respuestas"):
        obtener_snapshot_preguntas(session, PROFILE_URL, page_size=1)


def test_content_aware_writer_skips_same_bytes_and_preserves_different_collision(tmp_path: Path) -> None:
    first = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"primero")
    same = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"primero")
    different = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"segundo")

    assert first.written is True
    assert same.skipped is True and same.path == first.path
    assert different.written is True and different.path != first.path
    assert first.path.read_bytes() == b"primero"
    assert different.path.read_bytes() == b"segundo"


def test_content_aware_writer_compares_bytes_even_if_sha256_collides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDigest:
        def hexdigest(self) -> str:
            return "a" * 64

    monkeypatch.setattr(
        safe_files_module.hashlib,
        "sha256",
        lambda _content=b"": FixedDigest(),
    )

    first = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"primero")
    second = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"segundo")
    third = write_bytes_content_aware(tmp_path, "Anexo.xlsx", b"tercero")

    assert first.written and second.written and third.written
    assert len({first.path, second.path, third.path}) == 3
    assert {path.read_bytes() for path in (first.path, second.path, third.path)} == {
        b"primero",
        b"segundo",
        b"tercero",
    }


def test_explicit_catalunya_regeneration_uses_its_state_without_fake_changes(tmp_path: Path) -> None:
    snapshot = obtener_snapshot_preguntas(RoutedSession(), PROFILE_URL, page_size=1)
    record_successful_review(
        tmp_path,
        snapshot.metadata,
        snapshot.questions,
        reviewed_at=datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc),
        layout=CATALUNYA_STATE_LAYOUT,
        platform="CATALUNYA",
        authentication_required=False,
    )
    before = state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT).read_bytes()

    result = regenerar_docx_catalunya(
        tmp_path,
        generated_at=datetime(2026, 7, 18, 11, 0, tzinfo=timezone.utc),
    )

    assert result.status == "regenerated"
    assert result.platform == "CATALUNYA"
    assert result.authentication_required is False
    assert state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT).read_bytes() == before


def test_operational_flow_downloads_response_attachments_and_is_idempotent(tmp_path: Path) -> None:
    session = DownloadSession()
    first = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        reviewed_at=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
        include_general_documents=False,
        log=lambda _message: None,
    )
    second = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        reviewed_at=datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc),
        include_general_documents=False,
        log=lambda _message: None,
    )

    assert first.status == "created"
    assert first.documents_found == 1 and first.documents_downloaded == 1
    assert Path(first.downloaded_documents[0]["path"]).read_bytes() == b"contenido excel simulado"
    assert second.status == "no_changes"
    assert second.documents_downloaded == 0 and second.documents_skipped == 1
    assert len(list(tmp_path.glob("Preguntas y respuestas a fecha *.docx"))) == 1


def test_facade_cli_emits_structured_result_without_changing_launcher_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    facade = load_catalunya_module()
    fake = SyncResult(
        status="no_changes",
        query_successful=True,
        authentication_successful=True,
        authentication_required=False,
        snapshot_complete=True,
        total_questions=2,
        no_changes=True,
        platform="CATALUNYA",
    )
    monkeypatch.setattr(facade, "ejecutar_descarga_catalunya", lambda *_args, **_kwargs: fake)

    exit_code = facade.main([PROFILE_URL, "--destino", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "RESULTADO_ESTRUCTURADO=" in output
    assert '"platform": "CATALUNYA"' in output


def test_incomplete_catalunya_snapshot_preserves_last_valid_state(tmp_path: Path) -> None:
    initial = obtener_snapshot_preguntas(RoutedSession(), PROFILE_URL, page_size=1)
    record_successful_review(
        tmp_path,
        initial.metadata,
        initial.questions,
        reviewed_at=datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc),
        layout=CATALUNYA_STATE_LAYOUT,
        platform="CATALUNYA",
        authentication_required=False,
    )
    path = state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT)
    before = path.read_bytes()

    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=RoutedSession(page_total=3),
        reviewed_at=datetime(2026, 7, 18, 11, 0, tzinfo=timezone.utc),
        include_general_documents=False,
        log=lambda _message: None,
    )

    assert result.status == "error"
    assert result.snapshot_complete is False
    assert result.questions_removed == 0
    assert path.read_bytes() == before
    assert len(list(tmp_path.glob("Preguntas y respuestas a fecha *.docx"))) == 1


def test_public_empty_question_list_is_a_complete_idempotent_snapshot(tmp_path: Path) -> None:
    session = RoutedSession(page_total=0)
    session.items = []
    session.details = {}

    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=session,
        reviewed_at=datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc),
        include_general_documents=False,
        log=lambda _message: None,
    )

    assert result.status == "no_changes"
    assert result.snapshot_complete is True
    assert result.total_questions == 0
    assert state_file(tmp_path, layout=CATALUNYA_STATE_LAYOUT).is_file()
    assert not list(tmp_path.glob("Preguntas y respuestas a fecha *.docx"))


def test_exclusive_expedient_is_reported_without_using_credentials(tmp_path: Path) -> None:
    result = ejecutar_descarga_catalunya(
        PROFILE_URL,
        tmp_path,
        session=ExclusiveSession(),
        include_general_documents=False,
        log=lambda _message: None,
    )

    assert result.status == "error"
    assert result.error_type == "access"
    assert result.authentication_required is False
    assert result.authentication_successful is False
    assert not (tmp_path / ".llangon-catalunya").exists()
