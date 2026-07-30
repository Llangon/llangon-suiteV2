from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from bs4 import BeautifulSoup


def load_downloader():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "herramientas_python" / "Descargar_Preguntas_PLACE.py"
    spec = importlib.util.spec_from_file_location("descargar_preguntas_place_for_tests", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def downloader():
    return load_downloader()


def tender_metadata() -> dict[str, str]:
    return {
        "expediente": "EXP-17",
        "organismo": "Órgano de prueba",
        "titulo": "Licitación de alimentación",
        "fecha_fin_oferta": "20/07/2026 14:00",
        "url": (
            "https://contrataciondelestado.es/wps/poc?"
            "uri=deeplink:detalle_licitacion&idEvl=ABC%2B123%3D%3D"
        ),
    }


def moment(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 7, day, hour, minute, second, tzinfo=timezone.utc)


def question(
    downloader,
    number: int,
    *,
    text: str | None = None,
    answer: str | None = None,
    updated_at: str | None = None,
    source_id: str | None = None,
    status: str = "Respondida",
    attachments=(),
):
    return downloader.QuestionAnswer(
        updated_at=updated_at if updated_at is not None else f"{number:02d}-07-2026 10:{number:02d}",
        question=text if text is not None else f"Pregunta literal {number}",
        answer=answer if answer is not None else f"Respuesta literal {number}",
        status=status,
        source_id=source_id if source_id is not None else f"place-question-{number}",
        attachments=tuple(attachments),
    )


def state(downloader, destination: Path) -> dict:
    return json.loads(downloader.state_file(destination).read_text(encoding="utf-8"))


def documents(destination: Path) -> list[Path]:
    return sorted(destination.glob("Preguntas y respuestas a fecha *.docx"))


def document_text(result) -> str:
    with zipfile.ZipFile(result.document_path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    return "\n".join(
        "".join(node.text or "" for node in paragraph.iter(f"{{{namespace}}}t"))
        for paragraph in root.iter(f"{{{namespace}}}p")
    )


def document_package_text(result) -> str:
    with zipfile.ZipFile(result.document_path) as package:
        return "\n".join(
            package.read(name).decode("utf-8", errors="ignore")
            for name in package.namelist()
            if name.endswith((".xml", ".rels"))
        )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_parser_keeps_answered_pending_and_stable_source_ids(downloader) -> None:
    soup = BeautifulSoup(
        """
        <table id="form1:tableEx1">
          <tr>
            <td>08-07-2026 12:28</td>
            <td><a id="form1:tableEx1:0:link2" data-question-id="Q-80">Respondida</a></td>
            <td>Respondida</td>
          </tr>
          <tr>
            <td>08-07-2026 12:30</td>
            <td><a id="form1:tableEx1:1:link3">Pendiente</a></td>
            <td>Pendiente</td>
          </tr>
        </table>
        """,
        "html.parser",
    )

    references = downloader.parse_question_references(soup)

    assert [item.status for item in references] == ["Respondida", "Pendiente"]
    assert references[0].stable_source_id == "Q-80"


def test_pagination_helpers_detect_next_page_and_incomplete_indicator(downloader) -> None:
    soup = BeautifulSoup(
        """
        <form id="form1">
          <span>Página 1 de 2</span>
          <a title="Página siguiente"
             onclick="submitForm('form1','form1:tableEx1:next')">Siguiente</a>
        </form>
        """,
        "html.parser",
    )

    assert downloader.find_next_page_link(soup) is not None
    assert downloader.pagination_requires_more(soup) is True


@pytest.mark.parametrize(
    "html",
    [
        """
        <table id="form1:tableEx1">
          <thead><tr><th>Fecha</th><th>Pregunta</th><th>Estado</th></tr></thead>
          <tbody></tbody>
        </table>
        """,
        """
        <div id="form1:tableEx1">
          <table>
            <thead><tr><th>Fecha</th><th>Pregunta</th><th>Estado</th></tr></thead>
            <tbody><tr><td colspan="3">No se han encontrado resultados.</td></tr></tbody>
          </table>
        </div>
        """,
        """
        <table id="form1:tableEx1">
          <thead><tr><th>Fecha</th><th>Pregunta</th><th>Estado</th></tr></thead>
          <tbody><tr><td colspan="3">No existen datos para la consulta realizada.</td></tr></tbody>
        </table>
        """,
        "<p>No hay preguntas para esta licitación.</p>",
    ],
)
def test_empty_question_variants_are_confirmed_without_false_partial(downloader, html: str) -> None:
    soup = BeautifulSoup(html, "html.parser")

    downloader.validate_question_page(soup, [])

    assert downloader.confirmed_empty_question_list(soup) is True


def test_unknown_question_rows_are_not_misclassified_as_empty(downloader) -> None:
    html = """
    <table id="form1:tableEx1">
      <tbody><tr><td>20-07-2026</td><td>Contenido no reconocido</td><td>Respondida</td></tr></tbody>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert downloader.parse_question_references(soup) == []
    assert downloader.confirmed_empty_question_list(soup) is False
    with pytest.raises(downloader.PlaceSnapshotIncompleteError):
        downloader.validate_question_page(soup, [])


@pytest.mark.parametrize("prefix", ["", "<p>Sin resultados en otro filtro.</p>"])
def test_alternate_question_link_suffix_is_detected_and_never_treated_as_empty(
    downloader,
    prefix: str,
) -> None:
    soup = BeautifulSoup(
        prefix
        + """
        <table id="form1:tableEx1">
          <tbody><tr>
            <td>20-07-2026 11:45</td>
            <td><a id="form1:tableEx1:0:link3">Pregunta real</a></td>
            <td>Respondida</td>
          </tr></tbody>
        </table>
        """,
        "html.parser",
    )

    references = downloader.parse_question_references(soup)

    assert len(references) == 1
    assert references[0].question == "Pregunta real"
    assert references[0].source_id.endswith(":link3")
    assert downloader.confirmed_empty_question_list(soup) is False
    downloader.validate_question_page(soup, references)


def test_question_link_is_selected_from_content_column_when_status_is_also_linked(
    downloader,
) -> None:
    soup = BeautifulSoup(
        """
        <table id="form1:tableEx1">
          <tbody><tr>
            <td>20-07-2026 11:45</td>
            <td><a id="form1:tableEx1:0:link3">Pregunta real</a></td>
            <td><a id="form1:tableEx1:0:link4">Respondida</a></td>
          </tr></tbody>
        </table>
        """,
        "html.parser",
    )

    references = downloader.parse_question_references(soup)

    assert len(references) == 1
    assert references[0].question == "Pregunta real"
    assert references[0].source_id.endswith(":link3")
    assert references[0].status == "Respondida"


def test_nested_place_layout_assigns_each_question_to_its_immediate_row(downloader) -> None:
    soup = BeautifulSoup(
        """
        <table><tr><td>
          <table id="form1:tableEx1"><tbody>
            <tr>
              <td>20-07-2026 11:45</td>
              <td><a id="form1:tableEx1:0:link2">Primera pregunta</a></td>
              <td>Respondida</td>
            </tr>
            <tr>
              <td>20-07-2026 11:50</td>
              <td><a id="form1:tableEx1:1:link2">Segunda pregunta</a></td>
              <td>Respondida</td>
            </tr>
          </tbody></table>
        </td></tr></table>
        """,
        "html.parser",
    )

    references = downloader.parse_question_references(soup)

    assert [item.question for item in references] == [
        "Primera pregunta",
        "Segunda pregunta",
    ]


def test_ambiguous_question_links_fail_closed_without_declaring_empty(downloader) -> None:
    soup = BeautifulSoup(
        """
        <table id="form1:tableEx1">
          <tbody><tr>
            <td>20-07-2026 11:45</td>
            <td>
              <a id="form1:tableEx1:0:link2">Primera</a>
              <a id="form1:tableEx1:0:link3">Segunda</a>
            </td>
            <td>Respondida</td>
          </tr></tbody>
        </table>
        """,
        "html.parser",
    )

    with pytest.raises(downloader.PlaceStructureError):
        downloader.parse_question_references(soup)
    assert downloader.confirmed_empty_question_list(soup) is False


def test_literal_text_and_attachment_metadata_are_preserved(downloader) -> None:
    soup = BeautifulSoup(
        """
        <table>
          <tr><td>Pregunta</td><td><textarea>¿Se acepta  A/B?
Segunda línea.</textarea></td></tr>
          <tr><td>Respuesta</td><td><textarea>Sí; se acepta  tal cual.</textarea></td></tr>
          <tr><td>Archivos adjuntos</td><td>
            <a id="a1" href="/docs/aclaracion.pdf">Aclaración {final}.pdf</a>
          </td></tr>
        </table>
        """,
        "html.parser",
    )

    assert downloader.labeled_value(soup, "Pregunta", preserve_literal=True) == (
        "¿Se acepta  A/B?\nSegunda línea."
    )
    attachments = downloader.parse_question_attachments(soup, "https://example.test/detail")
    assert attachments[0].name == "Aclaración {final}.pdf"
    assert attachments[0].url == "https://example.test/docs/aclaracion.pdf"


def test_01_first_execution_is_one_chronological_list_without_review_blocks(
    downloader,
    tmp_path: Path,
) -> None:
    items = [
        question(downloader, 1, updated_at="03-07-2026 14:14"),
        question(downloader, 2, updated_at="08-07-2026 12:28"),
        question(downloader, 3, updated_at="08-07-2026 10:21"),
    ]

    result = downloader.record_successful_review(
        tmp_path,
        tender_metadata(),
        items,
        reviewed_at=moment(16, 18),
    )

    content = document_text(result)
    assert result.incorporated_current_cycle == 3
    assert content.index("Pregunta 3 del 08-07-2026 a las 12:28") < content.index(
        "Pregunta 2 del 08-07-2026 a las 10:21"
    )
    assert content.index("Pregunta 2 del 08-07-2026 a las 10:21") < content.index(
        "Pregunta 1 del 03-07-2026 a las 14:14"
    )
    assert "PRIMERA REVISI" not in content
    assert "LOCALIZADAS ENTRE" not in content
    assert "REALIZADA EL" not in content
    assert len(state(downloader, tmp_path)["change_events"]) == 1


def test_02_second_execution_without_changes_only_updates_state(
    downloader,
    tmp_path: Path,
) -> None:
    items = [question(downloader, 1), question(downloader, 2)]
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), items, reviewed_at=moment(14, 9)
    )
    first_path = Path(first.document_path)
    original_hash = file_hash(first_path)
    original_mtime = first_path.stat().st_mtime_ns

    repeated = downloader.record_successful_review(
        tmp_path, tender_metadata(), list(reversed(items)), reviewed_at=moment(15, 9)
    )

    assert repeated.no_changes is True
    assert repeated.snapshot_complete is True
    assert len(documents(tmp_path)) == 1
    assert file_hash(first_path) == original_hash
    assert first_path.stat().st_mtime_ns == original_mtime
    assert state(downloader, tmp_path)["last_successful_review"] == "2026-07-15T09:00:00+00:00"


def test_03_new_question_keeps_numbers_and_creates_complete_snapshot(
    downloader,
    tmp_path: Path,
) -> None:
    q1 = question(downloader, 1, updated_at="10-07-2026 09:00")
    q2 = question(downloader, 2, updated_at="12-07-2026 11:00")
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1], reviewed_at=moment(14, 9)
    )

    second = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q2, q1], reviewed_at=moment(15, 9)
    )

    content = document_text(second)
    assert Path(first.document_path).exists()
    assert len(documents(tmp_path)) == 2
    assert "Pregunta 1 del 10-07-2026" in content
    assert "Pregunta 2 del 12-07-2026" in content
    assert content.index("Pregunta 2 del") < content.index("Pregunta 1 del")
    numbers = {item["place_source_id"]: item["number"] for item in state(downloader, tmp_path)["questions"].values()}
    assert numbers == {"place-question-1": 1, "place-question-2": 2}


def test_04_several_new_questions_use_one_list_not_blocks(downloader, tmp_path: Path) -> None:
    q1 = question(downloader, 1, updated_at="09-07-2026 09:00")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1], reviewed_at=moment(14, 9)
    )
    q2 = question(downloader, 2, updated_at="12-07-2026 09:00")
    q3 = question(downloader, 3, updated_at="11-07-2026 09:00")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q3, q1, q2], reviewed_at=moment(15, 9)
    )

    content = document_text(result)
    assert result.incorporated_current_cycle == 2
    assert content.index("Pregunta 3 del") < content.index("Pregunta 2 del")
    assert content.index("Pregunta 2 del") < content.index("Pregunta 1 del")
    assert "LOCALIZADAS" not in content


def test_05_question_change_keeps_identity_number_and_shows_both_versions(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(
        downloader,
        1,
        text="¿Se admite el formato A?",
        updated_at="10-07-2026 09:00",
    )
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    changed = question(
        downloader,
        1,
        text="¿Se admite el formato A o B?",
        updated_at="12-07-2026 12:00",
    )

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [changed], reviewed_at=moment(15, 10)
    )

    content = document_text(result)
    assert result.question_updates == 1
    assert "AVISO: CONTENIDO MODIFICADO EN PLACE" in content
    assert "Elementos modificados: pregunta." in content
    assert "VERSI" in content and "ANTERIOR" in content and "VIGENTE EN PLACE" in content
    assert "formato A?" in content and "formato A o B?" in content
    stored = next(iter(state(downloader, tmp_path)["questions"].values()))
    assert stored["number"] == 1
    assert stored["official_datetime"] == "10-07-2026 09:00"
    assert len(stored["versions"]) == 2


def test_06_answer_change_shows_previous_and_current_complete_context(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(downloader, 1, answer="Respuesta original.")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    changed = question(downloader, 1, answer="Respuesta corregida.")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [changed], reviewed_at=moment(15, 9)
    )

    content = document_text(result)
    assert result.responses_updated == 1
    assert "Elementos modificados: respuesta." in content
    assert content.count("Pregunta literal 1") == 2
    assert "Respuesta original." in content and "Respuesta corregida." in content


def test_07_simultaneous_question_and_answer_change_is_explicit(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(downloader, 1, text="Texto inicial", answer="Respuesta inicial")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    changed = question(downloader, 1, text="Texto vigente", answer="Respuesta vigente")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [changed], reviewed_at=moment(15, 9)
    )

    content = document_text(result)
    assert result.question_updates == 1 and result.responses_updated == 1
    assert "Elementos modificados: pregunta y respuesta." in content
    for value in ("Texto inicial", "Respuesta inicial", "Texto vigente", "Respuesta vigente"):
        assert value in content


def test_simultaneous_change_without_place_id_uses_robust_fallback_identity(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(
        downloader,
        1,
        text="¿Se admite el envase de un kilogramo?",
        answer="Sí, se admite.",
        updated_at="10-07-2026 09:00",
        source_id="",
    )
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    changed = question(
        downloader,
        1,
        text="¿Se admite el envase de un kilogramo o de dos kilogramos?",
        answer="Se admiten ambos formatos.",
        updated_at="12-07-2026 11:00",
        source_id="",
    )

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [changed], reviewed_at=moment(15, 9)
    )

    assert result.incorporated_current_cycle == 0
    assert result.question_updates == 1 and result.responses_updated == 1
    stored = next(iter(state(downloader, tmp_path)["questions"].values()))
    assert stored["number"] == 1 and len(stored["versions"]) == 2


def test_08_successive_modifications_keep_every_version_newest_to_initial(
    downloader,
    tmp_path: Path,
) -> None:
    snapshots = [
        question(downloader, 1, answer="Versión uno"),
        question(downloader, 1, answer="Versión dos"),
        question(downloader, 1, answer="Versión tres"),
    ]
    for index, item in enumerate(snapshots):
        result = downloader.record_successful_review(
            tmp_path,
            tender_metadata(),
            [item],
            reviewed_at=moment(14 + index, 9),
        )

    content = document_text(result)
    assert "HISTORIAL DE VERSIONES" in content
    assert content.index("Versión tres") < content.index("Versión dos")
    assert content.index("Versión dos") < content.index("Versión uno")
    stored = next(iter(state(downloader, tmp_path)["questions"].values()))
    assert [item["version"] for item in stored["versions"]] == [1, 2, 3]


def test_09_unanswered_question_becoming_answered_is_not_new(
    downloader,
    tmp_path: Path,
) -> None:
    pending = question(downloader, 1, answer="", status="Pendiente")
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [pending], reviewed_at=moment(14, 9)
    )
    responded = question(downloader, 1, answer="Respuesta publicada", status="Respondida")

    second = downloader.record_successful_review(
        tmp_path, tender_metadata(), [responded], reviewed_at=moment(15, 9)
    )

    content = document_text(second)
    assert first.incorporated_current_cycle == 1
    assert second.incorporated_current_cycle == 0
    assert second.answers_incorporated == 1
    assert "AVISO: RESPUESTA INCORPORADA EN PLACE" in content
    assert "Sin respuesta publicada en PLACE." in content
    assert "Respuesta publicada" in content
    assert len(state(downloader, tmp_path)["questions"]) == 1


def test_10_existing_answer_disappears_without_withdrawing_question(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(downloader, 1, answer="Respuesta existente")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    without_answer = question(downloader, 1, answer="", status="Respondida")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [without_answer], reviewed_at=moment(15, 9)
    )

    content = document_text(result)
    assert result.answers_removed == 1
    assert result.questions_removed == 0
    assert "AVISO: LA RESPUESTA YA NO SE ENCUENTRA PUBLICADA EN PLACE" in content
    assert "Respuesta existente" in content
    assert "Sin respuesta publicada actualmente en PLACE." in content
    assert next(iter(state(downloader, tmp_path)["questions"].values()))["published"] is True


def test_11_withdrawn_question_stays_in_position_with_last_known_version(
    downloader,
    tmp_path: Path,
) -> None:
    newer = question(downloader, 1, updated_at="12-07-2026 10:00")
    older = question(downloader, 2, updated_at="10-07-2026 10:00")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [older, newer], reviewed_at=moment(14, 9)
    )

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [older], reviewed_at=moment(15, 9)
    )

    content = document_text(result)
    assert result.questions_removed == 1
    assert "AVISO: ESTA PREGUNTA YA NO SE ENCUENTRA PUBLICADA EN PLACE" in content
    assert "Se muestra la " in content
    assert content.index("Pregunta 2 del 12-07-2026") < content.index("Pregunta 1 del 10-07-2026")
    stored = {item["number"]: item for item in state(downloader, tmp_path)["questions"].values()}
    assert stored[2]["published"] is False
    assert stored[2]["number"] == 2


def test_12_incomplete_snapshot_cannot_mark_withdrawals_or_change_state(
    downloader,
    tmp_path: Path,
) -> None:
    item = question(downloader, 1)
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [item], reviewed_at=moment(14, 9)
    )
    before = downloader.state_file(tmp_path).read_bytes()
    before_documents = [file_hash(path) for path in documents(tmp_path)]

    with pytest.raises(downloader.PlaceSnapshotIncompleteError):
        downloader.record_successful_review(
            tmp_path,
            tender_metadata(),
            [],
            reviewed_at=moment(15, 9),
            snapshot_complete=False,
        )

    assert downloader.state_file(tmp_path).read_bytes() == before
    assert [file_hash(path) for path in documents(tmp_path)] == before_documents


def test_13_authentication_error_preserves_last_valid_state(
    downloader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [question(downloader, 1)], reviewed_at=moment(14, 9)
    )
    before = downloader.state_file(tmp_path).read_bytes()

    def fail(*_args, **_kwargs):
        raise downloader.PlaceAuthenticationError("Acceso rechazado")

    monkeypatch.setattr(downloader, "fetch_questions", fail)
    result = downloader.sync_place_questions(
        tender_metadata()["url"], tmp_path, "configured-account", "configured-secret"
    )

    assert result.status == "error"
    assert result.authentication_successful is False
    assert result.snapshot_complete is False
    assert downloader.state_file(tmp_path).read_bytes() == before
    assert len(documents(tmp_path)) == 1


@pytest.mark.parametrize(
    "error_class",
    ["PlaceSessionError", "PlaceStructureError", "PlaceQuestionDataError", "PlaceResponseDataError"],
)
def test_14_question_or_response_read_error_is_an_incomplete_snapshot(
    downloader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_class: str,
) -> None:
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [question(downloader, 1)], reviewed_at=moment(14, 9)
    )
    before = downloader.state_file(tmp_path).read_bytes()
    exception_type = getattr(downloader, error_class)

    def fail(*_args, **_kwargs):
        raise exception_type("Lectura incompleta")

    monkeypatch.setattr(downloader, "fetch_questions", fail)
    result = downloader.sync_place_questions(
        tender_metadata()["url"], tmp_path, "configured-account", "configured-secret"
    )

    assert result.status == "error"
    assert result.snapshot_complete is False
    assert result.no_changes is False
    assert downloader.state_file(tmp_path).read_bytes() == before


def test_15_restored_question_keeps_identity_number_and_history(
    downloader,
    tmp_path: Path,
) -> None:
    item = question(downloader, 1)
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [item], reviewed_at=moment(14, 9)
    )
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [], reviewed_at=moment(15, 9)
    )

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [item], reviewed_at=moment(16, 9)
    )

    content = document_text(result)
    assert result.questions_restored == 1
    assert result.incorporated_current_cycle == 0
    assert "AVISO: ESTA PREGUNTA HA VUELTO A APARECER EN PLACE" in content
    stored = next(iter(state(downloader, tmp_path)["questions"].values()))
    assert stored["number"] == 1 and stored["published"] is True
    assert [event["event"] for event in stored["publication_history"]] == ["withdrawn", "restored"]


def test_16_restored_question_with_changed_content_shows_both_events(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(downloader, 1, answer="Respuesta anterior")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [], reviewed_at=moment(15, 9)
    )
    restored = question(downloader, 1, answer="Respuesta al reaparecer")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [restored], reviewed_at=moment(16, 9)
    )

    content = document_text(result)
    assert result.questions_restored == 1 and result.responses_updated == 1
    assert "HA VUELTO A APARECER" in content
    assert "CONTENIDO MODIFICADO" in content
    assert "Respuesta anterior" in content and "Respuesta al reaparecer" in content
    assert len(state(downloader, tmp_path)["questions"]) == 1


def test_17_place_reordering_does_not_create_document_or_change_numbers(
    downloader,
    tmp_path: Path,
) -> None:
    items = [question(downloader, number) for number in (1, 2, 3)]
    downloader.record_successful_review(
        tmp_path, tender_metadata(), items, reviewed_at=moment(14, 9)
    )
    before = {
        item["place_source_id"]: item["number"]
        for item in state(downloader, tmp_path)["questions"].values()
    }

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [items[2], items[0], items[1]], reviewed_at=moment(15, 9)
    )

    after = {
        item["place_source_id"]: item["number"]
        for item in state(downloader, tmp_path)["questions"].values()
    }
    assert result.no_changes is True
    assert before == after
    assert len(documents(tmp_path)) == 1


def test_18_identical_dates_use_persistent_number_as_stable_tie_break(
    downloader,
    tmp_path: Path,
) -> None:
    date = "12-07-2026 10:00"
    q1 = question(downloader, 1, updated_at=date)
    q2 = question(downloader, 2, updated_at=date)
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1, q2], reviewed_at=moment(14, 9)
    )
    first_content = document_text(first)
    repeated = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q2, q1], reviewed_at=moment(15, 9)
    )

    assert first_content.index("Pregunta 1 del") < first_content.index("Pregunta 2 del")
    assert repeated.no_changes is True


def test_19_missing_or_invalid_date_is_kept_last_without_fabrication(
    downloader,
    tmp_path: Path,
) -> None:
    dated = question(downloader, 1, updated_at="12-07-2026 10:00")
    undated = question(downloader, 2, updated_at="")

    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [undated, dated], reviewed_at=moment(14, 9)
    )

    content = document_text(result)
    assert content.index("Pregunta 1 del 12-07-2026") < content.index("Pregunta 2")
    assert "Pregunta 2 del" not in content
    assert any("sin fecha oficial válida" in warning for warning in result.structure_novelties)


def legacy_v1_state(downloader) -> dict:
    item = question(downloader, 1, text="Pregunta migrada", answer="Respuesta migrada")
    stable_id = "legacy-stable-id"
    reviewed = "2026-07-14T09:00:00+00:00"
    return {
        "schema_version": 1,
        "platform": "PLACE",
        "profile_url": tender_metadata()["url"],
        "metadata": tender_metadata(),
        "next_question_number": 2,
        "last_successful_review": reviewed,
        "last_result": {"status": "created"},
        "questions": {
            stable_id: {
                "stable_id": stable_id,
                "place_source_id": "place-question-1",
                "number": 1,
                "question": item.question,
                "question_hash": item.question_hash,
                "question_history": [],
                "asked_at": "",
                "updated_at": item.updated_at,
                "answered_at": "",
                "status": "Respondida",
                "answer": item.answer,
                "answer_hash": item.answer_hash,
                "attachments": [],
                "attachments_hash": item.attachments_hash,
                "current_response_version": 1,
                "response_versions": [],
                "first_seen": reviewed,
                "last_seen": reviewed,
                "first_revision_id": "r1",
                "last_revision_id": "r1",
                "revision_membership": ["r1"],
            }
        },
        "revisions": [
            {
                "id": "r1",
                "reviewed_at": reviewed,
                "previous_review": "",
                "first_review": True,
                "rtf_filename": "legacy.rtf",
                "entries": [
                    {
                        "stable_id": stable_id,
                        "number": 1,
                        "question": item.question,
                        "answer": item.answer,
                        "updated_at": item.updated_at,
                        "asked_at": "",
                        "answered_at": "",
                        "attachments": [],
                        "change_type": "incorporated",
                    }
                ],
            }
        ],
        "migration": {},
    }


def test_20_migration_from_revision_blocks_is_automatic_idempotent_and_non_destructive(
    downloader,
    tmp_path: Path,
) -> None:
    technical = downloader.state_directory(tmp_path, create=True)
    legacy = legacy_v1_state(downloader)
    downloader._atomic_write_json(downloader.state_file(tmp_path), legacy)
    same = question(downloader, 1, text="Pregunta migrada", answer="Respuesta migrada")

    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [same], reviewed_at=moment(15, 9)
    )
    migrated = state(downloader, tmp_path)
    backup = technical / downloader.STATE_BACKUP_FILE_NAME
    second = downloader.record_successful_review(
        tmp_path, tender_metadata(), [same], reviewed_at=moment(16, 9)
    )

    assert first.no_changes is True and second.no_changes is True
    assert migrated["schema_version"] == 2
    assert next(iter(migrated["questions"].values()))["number"] == 1
    assert next(iter(migrated["questions"].values()))["versions"][0]["answer"] == "Respuesta migrada"
    assert migrated["legacy_revisions"][0]["first_review"] is True
    assert json.loads(backup.read_text(encoding="utf-8"))["schema_version"] == 1
    assert first.status == "regenerated" and first.document_generated is True
    assert second.status == "no_changes" and second.document_generated is False
    assert len(documents(tmp_path)) == 1


def test_21_manual_docx_deletion_does_not_reset_state_or_duplicate_questions(
    downloader,
    tmp_path: Path,
) -> None:
    q1 = question(downloader, 1)
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1], reviewed_at=moment(14, 9)
    )
    Path(first.document_path).unlink()
    repeated = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1], reviewed_at=moment(15, 9)
    )
    regenerated = Path(repeated.document_path)
    q2 = question(downloader, 2)
    changed = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1, q2], reviewed_at=moment(16, 9)
    )

    assert repeated.no_changes is True
    assert repeated.status == "regenerated"
    assert repeated.document_generated is True
    assert regenerated.is_file()
    assert len(state(downloader, tmp_path)["questions"]) == 2
    content = document_text(changed)
    assert "Pregunta 1" in content and "Pregunta 2" in content


def test_22_format_is_monochrome_and_has_no_review_grouping(
    downloader,
    tmp_path: Path,
) -> None:
    original = question(downloader, 1, answer="Anterior")
    downloader.record_successful_review(
        tmp_path, tender_metadata(), [original], reviewed_at=moment(14, 9)
    )
    changed = question(downloader, 1, answer="Vigente")
    result = downloader.record_successful_review(
        tmp_path, tender_metadata(), [changed], reviewed_at=moment(15, 9)
    )
    content = document_text(result)
    with zipfile.ZipFile(result.document_path) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert all(color not in document_xml for color in ("2E74B5", "0563C1", "954F72", "0000FF"))
    assert "<w:shd" not in document_xml and "w:highlight" not in document_xml
    assert "PRIMERA REVISI" not in content
    assert "LOCALIZADAS ENTRE" not in content
    assert "HIST" not in content or "HISTORIAL DE VERSIONES" in content
    assert "AVISO: CONTENIDO MODIFICADO EN PLACE" in content
    assert "ANTERIOR" in content and "VIGENTE EN PLACE" in content
    assert document_xml.count("<w:hyperlink") == 1
    assert content.count("Abrir ficha de la licitación en PLACE") == 1
    assert result.document_format == "docx"
    assert result.rtf_generated is False and result.rtf_path == ""


def test_23_identical_complete_snapshot_is_idempotent(
    downloader,
    tmp_path: Path,
) -> None:
    items = [question(downloader, 1), question(downloader, 2)]
    downloader.record_successful_review(
        tmp_path, tender_metadata(), items, reviewed_at=moment(14, 9)
    )
    initial_state = state(downloader, tmp_path)
    for hour in (10, 11, 12):
        result = downloader.record_successful_review(
            tmp_path, tender_metadata(), list(reversed(items)), reviewed_at=moment(14, hour)
        )
        assert result.no_changes is True

    final_state = state(downloader, tmp_path)
    assert len(documents(tmp_path)) == 1
    assert len(final_state["questions"]) == 2
    assert [len(item["versions"]) for item in final_state["questions"].values()] == [1, 1]
    assert {
        key: value["number"] for key, value in initial_state["questions"].items()
    } == {
        key: value["number"] for key, value in final_state["questions"].items()
    }
    assert len(final_state["change_events"]) == 1


def test_24_previous_docx_is_byte_for_byte_intact_after_new_file(
    downloader,
    tmp_path: Path,
) -> None:
    q1 = question(downloader, 1)
    first = downloader.record_successful_review(
        tmp_path, tender_metadata(), [q1], reviewed_at=moment(14, 9)
    )
    previous = Path(first.document_path)
    digest = file_hash(previous)
    mtime = previous.stat().st_mtime_ns

    downloader.record_successful_review(
        tmp_path,
        tender_metadata(),
        [q1, question(downloader, 2)],
        reviewed_at=moment(15, 9),
    )

    assert file_hash(previous) == digest
    assert previous.stat().st_mtime_ns == mtime
    assert len(documents(tmp_path)) == 2


def test_structured_result_exposes_requested_spanish_contract(
    downloader,
    tmp_path: Path,
) -> None:
    result = downloader.record_successful_review(
        tmp_path,
        tender_metadata(),
        [question(downloader, 1)],
        reviewed_at=moment(14, 9),
    )
    payload = result.to_dict()

    for key in (
        "consulta_correcta",
        "snapshot_completo",
        "autenticacion_correcta",
        "preguntas_totales",
        "preguntas_incorporadas",
        "preguntas_modificadas",
        "respuestas_modificadas",
        "respuestas_incorporadas",
        "respuestas_retiradas",
        "preguntas_retiradas",
        "preguntas_reaparecidas",
        "cambios_detectados",
        "sin_cambios",
        "rtf_generado",
        "ruta_rtf",
        "documento_generado",
        "ruta_documento",
        "formato_documento",
        "nombre_documento",
        "sha256_documento",
        "fecha_revision",
        "errores",
        "avisos",
    ):
        assert key in payload
    assert payload["documento_generado"] is True
    assert payload["formato_documento"] == "docx"
    assert payload["nombre_documento"].endswith(".docx")
    assert len(payload["sha256_documento"]) == 64
    assert payload["rtf_generado"] is False and payload["ruta_rtf"] == ""


def test_atomic_state_replace_retries_transient_dropbox_lock(
    downloader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("{}", encoding="utf-8")
    real_replace = downloader.os.replace
    attempts = 0

    def transient_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("bloqueo transitorio")
        return real_replace(source, destination)

    monkeypatch.setattr(downloader.os, "replace", transient_replace)
    monkeypatch.setattr(downloader.time, "sleep", lambda _seconds: None)
    downloader._atomic_write_json(target, {"review": "ok"})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"review": "ok"}


def test_docx_output_is_visible_on_windows(downloader, tmp_path: Path) -> None:
    result = downloader.record_successful_review(
        tmp_path,
        tender_metadata(),
        [question(downloader, 1)],
        reviewed_at=moment(14, 9),
    )
    if os.name == "nt":
        assert not (Path(result.document_path).stat().st_file_attributes & 0x2)


def test_explicit_regeneration_cli_uses_state_without_credentials_or_fake_changes(
    downloader,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    downloader.record_successful_review(
        tmp_path,
        tender_metadata(),
        [question(downloader, 1)],
        reviewed_at=moment(14, 9),
    )
    before = downloader.state_file(tmp_path).read_bytes()
    before_events = len(state(downloader, tmp_path)["change_events"])

    exit_code = downloader.main(
        ["--destino", str(tmp_path), "--regenerar-docx-desde-estado"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "regenerated"
    assert payload["documento_generado"] is True
    assert payload["formato_documento"] == "docx"
    assert payload["cambios_detectados"] is False
    assert payload["rtf_generado"] is False and payload["ruta_rtf"] == ""
    assert downloader.state_file(tmp_path).read_bytes() == before
    assert len(state(downloader, tmp_path)["change_events"]) == before_events
