from __future__ import annotations

from webapp.infonalia_webapp.monitor.tender_messages import build_notification_content


DIFFERENCE = {"change_type": "document_new", "title": "Pliego nuevo"}


def _subject_for(licitacion: dict[str, object]) -> str:
    return build_notification_content(
        licitacion,
        platform="PLACE",
        checked_at="2026-07-21T08:00:00+02:00",
        differences=[DIFFERENCE],
    )["subject"]


def test_notification_subject_uses_dropbox_folder_from_year_onwards() -> None:
    subject = _subject_for(
        {
            "id": 29,
            "expediente": "6296/2025",
            "ruta_carpeta": (
                r"C:\Users\LLangon03\Dropbox\00000 LLANGON\2026\06 JUNIO"
                r"\22 JUNIO 2359 ZAMORA VIRGEN DEL CANTO DE TORO 62962025"
            ),
        }
    )

    assert subject == r"[Llangon Monitor] 22 JUNIO 2359 ZAMORA VIRGEN DEL CANTO DE TORO 62962025"


def test_notification_subject_accepts_relative_dropbox_folder() -> None:
    subject = _subject_for(
        {
            "id": 29,
            "expediente": "6296/2025",
            "ruta_carpeta": r"2026\06 JUNIO\22 JUNIO 2359 ZAMORA 62962025",
        }
    )

    assert subject == r"[Llangon Monitor] 22 JUNIO 2359 ZAMORA 62962025"


def test_notification_subject_falls_back_to_contract_reference_without_folder() -> None:
    subject = _subject_for({"id": 29, "expediente": "6296/2025", "ruta_carpeta": ""})

    assert subject == "[Llangon Monitor] 6296/2025"


def test_notification_body_is_forwardable_and_has_only_official_link() -> None:
    content = build_notification_content(
        {
            "id": 336,
            "expediente": "CS/AH08/1101474873/26/AMUP",
            "objeto": "Fórmulas enterales",
            "fecha_limite": "2026-07-31",
            "hora_limite": "14:00",
            "ruta_carpeta": r"C:\Dropbox\2026\07 JULIO\31 JULIO 1400 BARCELONA H VILADECANS",
            "enlace_perfil": "https://contractaciopublica.cat/publicacion",
        },
        platform="CATALUNYA",
        checked_at="2026-07-22T15:43:10+02:00",
        differences=[DIFFERENCE],
        ai_summary="Conviene revisar el nuevo pliego.",
        suite_url="http://127.0.0.1:8787/app/licitaciones/336",
        attachment_names=["Preguntas.docx"],
        omitted_attachments=[{"name": "PCAP.zip", "size": 30 * 1024 * 1024}],
    )

    assert content["subject"] == "[Llangon Monitor] 31 JULIO 1400 BARCELONA H VILADECANS"
    assert "31/07/2026 14:00" in content["text"]
    assert "Resumen ejecutivo" in content["html"]
    assert "Acceder a la plataforma oficial" in content["html"]
    assert "Archivos adjuntos</p>" not in content["html"]
    assert "Protección de tamaño activada" in content["html"]
    assert 'width="128"' in content["html"]
    assert "background:#eaf7ea" in content["html"]
    assert "Para ampliar la información" not in content["html"]
    assert "127.0.0.1" not in content["text"] + content["html"]


def test_questions_follow_the_corporate_document_reading_order() -> None:
    content = build_notification_content(
        {"expediente": "EXP-1", "objeto": "Contrato", "enlace_perfil": "https://example.test"},
        platform="CATALUNYA",
        checked_at="2026-07-22T15:43:10+02:00",
        differences=[
            {
                "change_type": "question_new",
                "title": "Pregunta o respuesta 12",
                "question_number": 12,
                "official_datetime": "2026-07-22T13:06:05.441Z",
                "question_text": "Texto de la pregunta",
                "answer_text": "Texto de la respuesta",
                "question_attachments": [
                    {"name": "PCAP.zip", "source_id": "302461252", "url": "https://example.test/pcap"}
                ],
            }
        ],
        attachment_names=["PCAP.zip", "Preguntas.docx"],
    )

    assert "Pregunta 12 del 22-07-2026 a las 15:06" in content["html"]
    assert "Archivos adjuntos a la respuesta" in content["html"]
    assert "Ref. 302461252" in content["html"]
    assert "Preguntas.docx" not in content["html"]
