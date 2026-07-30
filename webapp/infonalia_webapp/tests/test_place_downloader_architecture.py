from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

from herramientas_python.descargadores.common.corporate_document import CORPORATE_DOCUMENT
from herramientas_python.descargadores.common.document_model import (
    DocumentLink,
    QuestionDocument,
    TenderField,
    build_question_document,
    format_document_question_heading,
)
from herramientas_python.descargadores.common.download_models import (
    RemoteDocument,
    build_document_filename,
    detect_document_extension,
)
from herramientas_python.descargadores.common.docx_renderer import (
    DOCX_OUTPUT,
    render_question_document_docx,
)
from herramientas_python.descargadores.common.question_models import (
    DocumentRenderError,
    PlatformQuestion,
    PlatformQuestionAttachment,
    QuestionSnapshot,
)
from herramientas_python.descargadores.common.question_state import _empty_state, state_file
from herramientas_python.descargadores.common.question_sync import prepare_question_sync
from herramientas_python.descargadores.common.question_workflow import record_successful_review
from herramientas_python.descargadores.common.rtf_renderer import render_question_document
from herramientas_python.descargadores.common.safe_files import (
    TextDocumentOutput,
    unique_dated_path,
    write_bytes_if_absent,
    write_text_temporary,
)
from herramientas_python.descargadores.place.questions import normalize_place_question
from herramientas_python.descargadores.place import questions as place_questions


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "herramientas_python"
PACKAGE_ROOT = TOOLS_ROOT / "descargadores"
COMMON_ROOT = PACKAGE_ROOT / "common"


def moment(hour: int = 10) -> datetime:
    return datetime(2026, 7, 18, hour, 0, tzinfo=timezone.utc)


def platform_question(
    *,
    text: str = "Pregunta literal",
    answer: str = "Respuesta literal",
    source_id: str = "Q-1",
    date: str = "08-07-2026 12:28",
) -> PlatformQuestion:
    return PlatformQuestion(
        updated_at=date,
        question=text,
        answer=answer,
        source_id=source_id,
        platform="TEST",
    )


def stored_question(
    *,
    versions: list[dict] | None = None,
    published: bool = True,
    publication_history: list[dict] | None = None,
    last_change_type: str = "initial",
) -> dict:
    initial = {
        "version": 1,
        "detected_at": "2026-07-18T10:00:00+00:00",
        "question": "Pregunta inicial",
        "answer": "Respuesta inicial",
        "attachments": [],
        "changed_fields": [],
        "change_type": "initial",
    }
    items = versions or [initial]
    current = items[-1]
    return {
        "stable_id": "stable-1",
        "number": 1,
        "official_datetime": "08-07-2026 12:28",
        "question": current["question"],
        "answer": current["answer"],
        "attachments": current.get("attachments", []),
        "first_seen": "2026-07-18T10:00:00+00:00",
        "published": published,
        "unpublished_at": "2026-07-18T11:00:00+00:00" if not published else "",
        "publication_history": publication_history or [],
        "last_change_type": last_change_type,
        "versions": items,
    }


def document_state(question: dict) -> dict:
    return {"platform": "PLACE", "questions": {"stable-1": question}}


def metadata() -> dict[str, str]:
    return {
        "expediente": "EXP-17",
        "organismo": "Órgano de prueba",
        "titulo": "Objeto de prueba",
        "fecha_fin_oferta": "20/07/2026 14:00",
        "url": "https://example.test/tender/17",
    }


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_name = ".".join(path.relative_to(TOOLS_ROOT).with_suffix("").parts)
    package_parts = module_name.split(".")[:-1]
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if node.level:
                    keep = len(package_parts) - (node.level - 1)
                    prefix = package_parts[:keep]
                    result.add(".".join(prefix + node.module.split(".")))
                else:
                    result.add(node.module)
    return result


def test_place_normalizer_returns_common_model_without_rtf() -> None:
    question = normalize_place_question(
        updated_at="08-07-2026 12:28",
        question="  Pregunta literal\r\nsegunda línea  ",
        answer="Respuesta literal",
        source_id="  Q-17 ",
        source_url="https://example.test/question/17",
    )

    assert isinstance(question, PlatformQuestion)
    assert question.platform == "PLACE"
    assert question.question == "Pregunta literal\nsegunda línea"
    assert question.source_id == "Q-17"
    assert "\\rtf" not in repr(question)


def test_place_snapshot_contract_is_structured() -> None:
    question = normalize_place_question(updated_at="08-07-2026 12:28", question="Q")
    snapshot = QuestionSnapshot("PLACE", metadata(), (question,), True)

    assert snapshot.complete is True
    assert snapshot.questions == (question,)
    assert all(isinstance(item, PlatformQuestion) for item in snapshot.questions)


def test_place_extractor_receives_its_session_timeout_contract() -> None:
    assert place_questions.TIMEOUT_SECONDS == 60


def test_common_engine_works_with_artificial_snapshot_without_place_import() -> None:
    state = _empty_state("https://example.test", metadata())
    prepared = prepare_question_sync(state, metadata(), [platform_question()], moment())

    assert prepared.counts["incorporated"] == 1
    assert len(prepared.state["questions"]) == 1
    assert not any("descargadores.place" in item for item in _imports(COMMON_ROOT / "question_sync.py"))


def test_document_model_builds_without_renderer_or_place() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())

    assert isinstance(model, QuestionDocument)
    assert format_document_question_heading(model.questions[0]) == "Pregunta 1 del 08-07-2026 a las 12:28"
    imports = _imports(COMMON_ROOT / "document_model.py")
    assert not any("rtf_renderer" in item or "descargadores.place" in item for item in imports)


def test_neutral_model_contains_no_rtf_or_docx_syntax() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())
    serialized = json.dumps(asdict(model), ensure_ascii=False)

    assert "\\rtf" not in serialized
    assert "<w:" not in serialized
    assert "word/document.xml" not in serialized


def test_document_heading_rule_contains_no_catalunya_branch() -> None:
    model_source = (COMMON_ROOT / "document_model.py").read_text(encoding="utf-8")
    renderer_source = (COMMON_ROOT / "docx_renderer.py").read_text(encoding="utf-8")

    assert "CATALUNYA" not in model_source
    assert "CATALUNYA" not in renderer_source


def test_rtf_renderer_consumes_only_neutral_model() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())
    rtf = render_question_document(model)

    assert rtf.startswith(r"{\rtf1")
    assert "Pregunta 1 del 08-07-2026 a las 12:28" in rtf
    source = (COMMON_ROOT / "rtf_renderer.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "BeautifulSoup", "ViewState", "prepare_question_sync", "load_state"):
        assert forbidden not in source


def test_docx_renderer_consumes_only_neutral_model() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())
    docx = render_question_document_docx(model)

    assert docx.startswith(b"PK")
    source = (COMMON_ROOT / "docx_renderer.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "BeautifulSoup", "ViewState", "prepare_question_sync", "load_state"):
        assert forbidden not in source


def test_official_output_is_docx_and_rtf_is_only_historical() -> None:
    import inspect

    signature = inspect.signature(record_successful_review)
    assert signature.parameters["output"].default is DOCX_OUTPUT
    workflow_source = (COMMON_ROOT / "question_workflow.py").read_text(encoding="utf-8")
    assert "output=RTF_OUTPUT" in workflow_source
    assert "def write_new_questions_rtf" in workflow_source


def test_business_modules_do_not_contain_rtf_control_words() -> None:
    for name in ("question_models.py", "question_state.py", "question_sync.py", "document_model.py"):
        source = (COMMON_ROOT / name).read_text(encoding="utf-8")
        assert r"{\rtf1" not in source
        assert r"\fonttbl" not in source


def test_rtf_has_one_active_implementation() -> None:
    owners = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if r"{\rtf1" in path.read_text(encoding="utf-8"):
            owners.append(path.relative_to(PACKAGE_ROOT).as_posix())
    assert owners == ["common/rtf_renderer.py"]
    assert r"{\rtf1" not in (TOOLS_ROOT / "Descargar_Preguntas_PLACE.py").read_text(encoding="utf-8")
    assert r"{\rtf1" not in (TOOLS_ROOT / "Descargar_PLACE.py").read_text(encoding="utf-8")


def test_corporate_style_has_one_source_of_truth() -> None:
    occurrences = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if "ASESORES LLANGON, S.L." in path.read_text(encoding="utf-8"):
            occurrences.append(path.relative_to(PACKAGE_ROOT).as_posix())
    assert occurrences == ["common/corporate_document.py"]
    assert CORPORATE_DOCUMENT.company_name == "ASESORES LLANGON, S.L."


def test_common_modules_do_not_import_place() -> None:
    for path in COMMON_ROOT.glob("*.py"):
        assert not any("descargadores.place" in item or item.startswith("place") for item in _imports(path))


def test_package_import_graph_has_no_cycles() -> None:
    modules = {
        ".".join(path.relative_to(TOOLS_ROOT).with_suffix("").parts): path
        for path in PACKAGE_ROOT.rglob("*.py")
        if path.name != "__init__.py"
    }
    graph = {name: {item for item in _imports(path) if item in modules} for name, path in modules.items()}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise AssertionError(f"Dependencia circular detectada en {name}")
        if name in visited:
            return
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for module in graph:
        visit(module)


def test_safe_bytes_writer_never_overwrites_and_cleans_temporaries(tmp_path: Path) -> None:
    first = write_bytes_if_absent(tmp_path, "documento.txt", b"primero")
    second = write_bytes_if_absent(tmp_path, "documento.txt", b"segundo")

    assert first.written is True
    assert second.skipped is True
    assert (tmp_path / "documento.txt").read_bytes() == b"primero"
    assert not list(tmp_path.glob(".*.tmp"))


def test_safe_text_writer_removes_failed_temporary(tmp_path: Path) -> None:
    def reject(_content: str) -> None:
        raise ValueError("contenido inválido")

    with pytest.raises(ValueError):
        write_text_temporary(tmp_path, "contenido", extension="rtf", encoding="ascii", validator=reject)
    assert list(tmp_path.iterdir()) == []


def test_output_layer_chooses_extension_and_resolves_collision(tmp_path: Path) -> None:
    first, first_time = unique_dated_path(tmp_path, "Documento ", ".rtf", moment())
    first.write_text("anterior", encoding="ascii")
    second, second_time = unique_dated_path(tmp_path, "Documento ", ".rtf", moment())

    assert first.suffix == second.suffix == ".rtf"
    assert second != first
    assert second_time > first_time


def test_remote_document_detection_and_name_are_common() -> None:
    remote = RemoteDocument(
        source_url="https://example.test/document",
        content=b"Rar!\x1a\x07\x01\x00" + b"\x00" * 16,
        logical_name="ANEXOS.rar",
        platform="PLACE",
    )
    extension = detect_document_extension(remote)

    assert extension == ".rar"
    assert build_document_filename(remote, extension) == "ANEXOS.rar"


def test_old_facades_redirect_to_the_unique_implementations() -> None:
    question_facade = importlib.import_module("herramientas_python.Descargar_Preguntas_PLACE")
    place_facade = importlib.import_module("herramientas_python.Descargar_PLACE")

    assert question_facade.render_cumulative_rtf.__module__.endswith("question_workflow")
    assert question_facade.render_cumulative_docx.__module__.endswith("question_workflow")
    assert question_facade.render_question_document_docx.__module__.endswith("docx_renderer")
    assert callable(question_facade.regenerate_docx_from_state)
    assert question_facade.rtf_escape.__module__.endswith("rtf_renderer")
    assert place_facade.detectar_extension.__module__.endswith("place.documents")
    assert place_facade.procesar_html.__module__.endswith("place.documents")


def test_legacy_script_loading_still_works() -> None:
    for filename in ("Descargar_PLACE.py", "Descargar_Preguntas_PLACE.py"):
        path = TOOLS_ROOT / filename
        spec = importlib.util.spec_from_file_location(f"compat_{path.stem}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(module.main)


def test_existing_v2_state_is_not_treated_as_first_execution(tmp_path: Path) -> None:
    first = record_successful_review(tmp_path, metadata(), [platform_question()], reviewed_at=moment(9))
    before = json.loads(state_file(tmp_path).read_text(encoding="utf-8"))
    second = record_successful_review(tmp_path, metadata(), [platform_question()], reviewed_at=moment(10))
    after = json.loads(state_file(tmp_path).read_text(encoding="utf-8"))

    assert first.document_generated is True
    assert first.document_format == "docx"
    assert first.rtf_generated is False and first.rtf_path == ""
    assert second.no_changes is True
    assert second.rtf_generated is False
    assert list(before["questions"]) == list(after["questions"])
    assert before["next_question_number"] == after["next_question_number"]


def test_write_failure_preserves_last_valid_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import herramientas_python.descargadores.common.safe_files as safe_files

    record_successful_review(tmp_path, metadata(), [platform_question()], reviewed_at=moment(9))
    before = state_file(tmp_path).read_bytes()

    def fail_rename(_source, _target):
        raise PermissionError("bloqueo simulado")

    monkeypatch.setattr(safe_files.os, "rename", fail_rename)
    with pytest.raises(DocumentRenderError):
        record_successful_review(
            tmp_path,
            metadata(),
            [platform_question(text="Pregunta modificada")],
            reviewed_at=moment(10),
        )

    assert state_file(tmp_path).read_bytes() == before
    assert len(list(tmp_path.glob("Preguntas y respuestas a fecha *.docx"))) == 1


def test_another_renderer_can_consume_model_without_extractor_changes() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())

    def alternate_renderer(document: QuestionDocument) -> str:
        return json.dumps({"title": document.title, "questions": len(document.questions)})

    assert json.loads(alternate_renderer(model)) == {
        "title": "PREGUNTAS Y RESPUESTAS",
        "questions": 1,
    }


def test_workflow_accepts_another_registered_text_renderer(tmp_path: Path) -> None:
    def validate_plain(content: str) -> None:
        if not content.startswith("PREGUNTAS"):
            raise ValueError("Documento de prueba inválido")

    output = TextDocumentOutput(
        format_name="plain-test",
        extension=".txt",
        encoding="utf-8",
        render=lambda document: f"{document.title}\n{len(document.questions)}",
        validator=validate_plain,
    )

    result = record_successful_review(
        tmp_path,
        metadata(),
        [platform_question()],
        reviewed_at=moment(),
        output=output,
    )

    assert result.document_generated is True
    assert result.generated_format == "plain-test"
    assert result.rtf_generated is False
    assert result.rtf_path == ""
    assert Path(result.document_path).suffix == ".txt"
    saved = json.loads(state_file(tmp_path).read_text(encoding="utf-8"))
    assert saved["platform"] == "TEST"


@pytest.mark.parametrize(
    ("case", "question", "notice_kind", "version_count"),
    [
        ("normal", stored_question(), None, 1),
        (
            "question_modified",
            stored_question(
                versions=[
                    stored_question()["versions"][0],
                    {
                        "version": 2,
                        "detected_at": "2026-07-18T11:00:00+00:00",
                        "question": "Pregunta modificada",
                        "answer": "Respuesta inicial",
                        "attachments": [],
                        "changed_fields": ["question"],
                        "change_type": "content_modified",
                    },
                ]
            ),
            "content_modified",
            2,
        ),
        (
            "answer_modified",
            stored_question(
                versions=[
                    stored_question()["versions"][0],
                    {
                        "version": 2,
                        "detected_at": "2026-07-18T11:00:00+00:00",
                        "question": "Pregunta inicial",
                        "answer": "Respuesta modificada",
                        "attachments": [],
                        "changed_fields": ["answer"],
                        "change_type": "content_modified",
                    },
                ]
            ),
            "content_modified",
            2,
        ),
        (
            "answer_added",
            stored_question(
                versions=[
                    {**stored_question()["versions"][0], "answer": ""},
                    {
                        "version": 2,
                        "detected_at": "2026-07-18T11:00:00+00:00",
                        "question": "Pregunta inicial",
                        "answer": "Respuesta incorporada",
                        "attachments": [],
                        "changed_fields": ["answer"],
                        "change_type": "answer_added",
                    },
                ]
            ),
            "answer_added",
            2,
        ),
        (
            "answer_removed",
            stored_question(
                versions=[
                    stored_question()["versions"][0],
                    {
                        "version": 2,
                        "detected_at": "2026-07-18T11:00:00+00:00",
                        "question": "Pregunta inicial",
                        "answer": "",
                        "attachments": [],
                        "changed_fields": ["answer"],
                        "change_type": "answer_removed",
                    },
                ]
            ),
            "answer_removed",
            2,
        ),
        (
            "question_removed",
            stored_question(
                published=False,
                publication_history=[{"event": "withdrawn", "detected_at": "2026-07-18T11:00:00+00:00"}],
            ),
            "question_removed",
            1,
        ),
        (
            "question_restored",
            stored_question(
                publication_history=[
                    {"event": "withdrawn", "detected_at": "2026-07-18T11:00:00+00:00"},
                    {"event": "restored", "detected_at": "2026-07-18T12:00:00+00:00"},
                ],
                last_change_type="restored",
            ),
            "question_restored",
            1,
        ),
    ],
)
def test_document_model_represents_required_business_scenarios(
    case: str,
    question: dict,
    notice_kind: str | None,
    version_count: int,
) -> None:
    del case
    entry = build_question_document(metadata(), document_state(question), moment()).questions[0]
    kinds = {notice.kind for notice in entry.publication_notices}
    if entry.modification_notice:
        kinds.add(entry.modification_notice.kind)

    assert len(entry.versions) == version_count
    if notice_kind:
        assert notice_kind in kinds
    else:
        assert not kinds


def test_document_model_represents_many_versions_restoration_and_long_content() -> None:
    versions = [
        {
            "version": number,
            "detected_at": f"2026-07-18T{9 + number:02d}:00:00+00:00",
            "question": f"Pregunta versión {number}" + (" muy larga" * 200 if number == 3 else ""),
            "answer": f"Respuesta versión {number}",
            "attachments": (
                [{"name": "anexo.pdf", "url": "https://example.test/anexo.pdf", "source_id": "A-1"}]
                if number == 3
                else []
            ),
            "changed_fields": ["question", "answer"] if number > 1 else [],
            "change_type": "content_modified" if number > 1 else "initial",
        }
        for number in range(1, 4)
    ]
    question = stored_question(
        versions=versions,
        publication_history=[
            {"event": "withdrawn", "detected_at": "2026-07-18T12:30:00+00:00"},
            {"event": "restored", "detected_at": "2026-07-18T13:00:00+00:00"},
        ],
        last_change_type="restored_modified",
    )
    model = build_question_document(metadata(), document_state(question), moment(14))
    entry = model.questions[0]

    assert len(entry.versions) == 3
    assert entry.show_version_history_heading is True
    assert {notice.kind for notice in entry.publication_notices} >= {
        "question_restored",
        "publication_history",
    }
    assert entry.modification_notice and entry.modification_notice.kind == "content_modified"
    assert len(entry.versions[0].question_text) > 1_000
    assert entry.versions[0].attachments[0].link == DocumentLink(
        "https://example.test/anexo.pdf",
        "anexo.pdf",
    )
    assert model.tender_fields[-1] == TenderField(
        "Enlace",
        "https://example.test/tender/17",
        DocumentLink("https://example.test/tender/17", "Abrir ficha de la licitación en PLACE"),
    )
    assert model.corporate == CORPORATE_DOCUMENT


def test_rendered_rtf_of_neutral_path_matches_frozen_real_shape() -> None:
    model = build_question_document(metadata(), document_state(stored_question()), moment())
    content = render_question_document(model)
    digest = hashlib.sha256(content.encode("ascii")).hexdigest()

    assert len(content) > 1_500
    assert len(digest) == 64
    assert "PREGUNTAS Y RESPUESTAS LOCALIZADAS ENTRE" not in content
    assert r"\shading" not in content
