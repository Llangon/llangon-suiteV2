"""Única fuente de verdad para el documento corporativo de preguntas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorporateDocumentConfig:
    company_name: str = "ASESORES LLANGON, S.L."
    tax_id: str = "B73803637"
    address: str = "C/ ULIA, 9, 1.º D, 41005, SEVILLA"
    email: str = "info@llangon.com"
    phone: str = "617 11 02 81"
    document_title: str = "PREGUNTAS Y RESPUESTAS"
    output_prefix: str = "Preguntas y respuestas a fecha "
    font_name: str = "Calibri"
    heading_font_name: str = "Calibri Light"


CORPORATE_DOCUMENT = CorporateDocumentConfig()

NOTICE_CONTENT_MODIFIED = "AVISO: CONTENIDO MODIFICADO EN {platform}"
NOTICE_ANSWER_ADDED = "AVISO: RESPUESTA INCORPORADA EN {platform}"
NOTICE_ANSWER_REMOVED = "AVISO: LA RESPUESTA YA NO SE ENCUENTRA PUBLICADA EN {platform}"
NOTICE_QUESTION_REMOVED = "AVISO: ESTA PREGUNTA YA NO SE ENCUENTRA PUBLICADA EN {platform}"
NOTICE_QUESTION_RESTORED = "AVISO: ESTA PREGUNTA HA VUELTO A APARECER EN {platform}"
