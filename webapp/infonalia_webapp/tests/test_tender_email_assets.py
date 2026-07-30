from __future__ import annotations

import json

from webapp.infonalia_webapp.monitor.tender_email_assets import (
    notification_files_and_differences,
    select_email_attachments,
)


def test_resolves_changed_document_and_latest_questions_document(tmp_path) -> None:
    document = tmp_path / "PCAP.zip"
    document.write_bytes(b"pcap")
    questions_document = tmp_path / "Preguntas y respuestas a fecha 22-07-2026 1543.docx"
    questions_document.write_bytes(b"docx")
    state_folder = tmp_path / ".llangon-catalunya"
    state_folder.mkdir()
    (state_folder / "questions_state.json").write_text(
        json.dumps({"questions": {"question-1": {"stable_id": "question-1", "number": 1, "question": "¿Cuál es el plazo?", "answer": "El indicado en el anuncio.", "attachments": [{"name": "Anexo.pdf", "source_id": "REF-1", "url": "https://example.test/anexo"}], "versions": []}}}),
        encoding="utf-8",
    )

    attachments, rows = notification_files_and_differences(
        tmp_path,
        [
            {"change_type": "document_new", "new_value": {"relative_path": "PCAP.zip"}},
            {"change_type": "question_new", "item_key": "question-1", "title": "hash"},
        ],
    )

    assert attachments == [document, questions_document]
    assert rows[1]["title"] == "Pregunta o respuesta 1"
    assert rows[1]["question_text"] == "¿Cuál es el plazo?"
    assert rows[1]["answer_text"] == "El indicado en el anuncio."
    assert rows[1]["question_number"] == 1
    assert rows[1]["question_attachments"] == [
        {"name": "Anexo.pdf", "source_id": "REF-1", "url": "https://example.test/anexo"}
    ]


def test_attachment_protection_keeps_small_files_and_reports_large_one(tmp_path) -> None:
    large = tmp_path / "PCAP.zip"
    large.write_bytes(b"x" * 100)
    small = tmp_path / "Preguntas.docx"
    small.write_bytes(b"docx")

    selected, skipped = select_email_attachments([large, small], limit_bytes=50)

    assert selected == [small]
    assert skipped == [{"name": "PCAP.zip", "size": 100, "reason": "size_limit"}]
