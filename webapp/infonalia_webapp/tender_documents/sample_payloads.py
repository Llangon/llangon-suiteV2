"""Fictitious payloads used for PDF and workbook acceptance tests."""

from __future__ import annotations

from typing import Any

from .payload import normalize_payload


LOREM = (
    "La documentación deberá presentarse con una redacción clara y coherente. "
    "Se comprobará la correspondencia entre la oferta técnica, los anexos y la documentación administrativa, "
    "evitando referencias contradictorias y explicando de forma expresa cualquier particularidad relevante."
)


def short_payload() -> dict[str, Any]:
    return normalize_payload({
        "control": {
            "document_id": "TEST-CORTO",
            "source": "manual",
            "confidentiality_notice": "Documento confidencial para uso exclusivo de {DESTINATARIO}.",
        },
        "recipient": {"client_id": 1001, "client_display": "CLIENTE DEMO", "razon_social_snapshot": "Cliente Demostración, S.L."},
        "tender": {
            "expediente": "EXP-FICTICIO-001",
            "objeto": "Suministro ficticio de material de oficina",
            "fecha_limite": "2030-10-15",
            "hora_limite": "14:00",
            "organismo": "Organismo Público de Demostración",
            "plataforma": "PLACE",
            "tipo_contrato": "Suministros",
            "procedimiento": "Abierto",
            "presupuesto_base": "25000.00",
        },
        "analysis": {"plazo": "12 meses", "observaciones": "Sin observaciones adicionales."},
        "quality": {"calendar_years": [2030]},
    })


def normal_payload() -> dict[str, Any]:
    payload = short_payload()
    payload["control"]["document_id"] = "TEST-NORMAL"
    payload["tender"].update({
        "expediente": "EXP-FICTICIO-002",
        "objeto": "Servicio ficticio de mantenimiento integral de instalaciones",
        "regulacion_armonizada": "No",
        "valor_estimado": "118500.00",
        "enlace": "https://contrataciondelestado.es/ejemplo-ficticio",
        "lotes": [
            {"numero": 1, "titulo": "Mantenimiento preventivo", "presupuesto": "42000", "valor_estimado": "84000", "comentarios": "Lote principal."},
            {"numero": 2, "titulo": "Asistencia correctiva", "presupuesto": "18000", "valor_estimado": "34500", "comentarios": "Atención bajo demanda."},
        ],
    })
    payload["analysis"].update({
        "plazo": "24 meses",
        "plazo_comentario": "Inicio previsto tras la formalización.",
        "prorroga": "Sí",
        "prorroga_comentario": "Una prórroga de doce meses.",
        "forma_adjudicacion": "Por lotes",
        "garantia_definitiva": "Sí",
        "garantia_definitiva_comentario": "Cinco por ciento del precio de adjudicación.",
        "fichas_tecnicas": "Sí",
        "fichas_tecnicas_comentario": "Incluir en el sobre técnico.",
        "memoria_tecnica": "Sí",
        "memoria_tecnica_comentario": "Máximo 40 páginas.",
        "muestras": "No",
        "subcontratacion": "Sí",
        "subcontratacion_comentario": "Sujeta a comunicación previa.",
        "criterios_juicio": [
            {"orden": 1, "criterio": "Plan de trabajo", "descripcion": "Metodología, organización y control.", "puntos": 25, "comentarios": "Describir hitos."},
            {"orden": 2, "criterio": "Calidad técnica", "subcriterio": "Medios", "descripcion": "Adecuación de medios personales y materiales.", "puntos": 15},
        ],
        "criterios_formula": [
            {"orden": 1, "criterio": "Oferta económica", "descripcion": "Valoración proporcional.", "puntos": 50, "formula_text": "Según fórmula indicada en el PCAP."},
            {"orden": 2, "criterio": "Reducción del plazo de respuesta", "puntos": 10, "formula_text": "Dos puntos por cada hora, hasta el máximo."},
        ],
        "condiciones_especiales": [
            {"orden": 1, "condicion": "Gestión ambiental", "detalle": "Separación y retirada acreditada de residuos."},
        ],
        "observaciones": "Revisar la coherencia de los compromisos técnicos con la oferta económica.",
    })
    return payload


def extreme_payload() -> dict[str, Any]:
    payload = normal_payload()
    payload["control"]["document_id"] = "TEST-EXTREMO"
    payload["tender"].update({
        "expediente": "EXP-FICTICIO-003-EXTREMO",
        "objeto": "Acuerdo marco ficticio para el suministro, implantación y soporte de equipamiento técnico en múltiples centros",
        "presupuesto_base": "975000.00",
        "valor_estimado": "3900000.00",
    })
    payload["tender"]["lotes"] = [
        {"numero": index, "titulo": f"Lote ficticio {index}", "presupuesto": str(60000 + index * 2500), "valor_estimado": str(240000 + index * 10000), "comentarios": LOREM}
        for index in range(1, 7)
    ]
    payload["analysis"].update({
        "garantia_provisional": "Sí",
        "garantia_provisional_comentario": LOREM,
        "garantia_complementaria": "Sí",
        "garantia_complementaria_comentario": LOREM,
        "adscripcion_medios": "Sí",
        "adscripcion_medios_comentario": LOREM,
        "fichas_tecnicas_comentario": LOREM,
        "memoria_tecnica_comentario": LOREM,
        "muestras": "Sí",
        "muestras_momento": "Antes de la adjudicación",
        "muestras_comentario": LOREM + " " + LOREM,
        "subcontratacion_comentario": LOREM + " " + LOREM,
        "observaciones": "\n\n".join([LOREM for _ in range(7)]),
        "criterios_juicio": [
            {"orden": index, "criterio": f"Criterio técnico ficticio {index}", "subcriterio": f"Subcriterio {index}.1" if index % 2 == 0 else "", "descripcion": LOREM, "puntos": 2.5, "comentarios": "Revisar la correspondencia con los anexos técnicos."}
            for index in range(1, 13)
        ],
        "criterios_formula": [
            {"orden": index, "criterio": f"Criterio automático ficticio {index}", "descripcion": LOREM, "puntos": 5, "formula_text": "Fórmula jurídica descrita literalmente en el PCAP; no se ejecuta en Excel.", "comentarios": "Comprobar el redondeo y los límites previstos."}
            for index in range(1, 8)
        ],
        "condiciones_especiales": [
            {"orden": index, "condicion": f"Condición especial ficticia {index}", "detalle": LOREM, "comentarios": "Revisar su aplicación al adjudicatario."}
            for index in range(1, 8)
        ],
    })
    return payload


__all__ = ("extreme_payload", "normal_payload", "short_payload")
