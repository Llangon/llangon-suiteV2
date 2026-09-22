from __future__ import annotations

import json


PORTAL_AI_PROMPT = """
Eres el motor de maquetación documental de Llangón Asesores. Convierte Ficha.pdf en un modelo JSON para una web de licitación de una sola página.

REGLAS ABSOLUTAS
1. No resumas, no descartes, no simplifiques y no inventes información.
2. Todo dato de Ficha.pdf debe aparecer en el modelo web, incluida confidencialidad, notas, tablas, fórmulas, antecedentes, pies y contenido dentro de imágenes.
3. Puedes reorganizar para mejorar la lectura, pero debes conservar cifras, unidades, fechas, nombres, condiciones, excepciones y matices.
4. Cada bloque lleva un id único y sourcePages con las páginas exactas que lo sustentan.
5. Para cada página devuelve sourceCoverage con su hash exacto, visualReviewed=true, los ids que la cubren y unmappedContent. Si existe cualquier contenido que no puedas trasladar con seguridad, escríbelo literalmente en unmappedContent.
6. No incluyas HTML, Markdown, recomendaciones comerciales ni conclusiones que no estén en la ficha.
7. La información repetida puede mostrarse una sola vez si el bloque referencia todas las páginas donde aparece.
8. Respeta el idioma original de cada contenido.

BLOQUES PERMITIDOS
- text: {id,type,title?,paragraphs?,bullets?,sourcePages}
- cards: {id,type,items:[{title,text}],sourcePages}
- notice: {id,type,tone:"important"|"success"|"neutral",title,text,sourcePages}
- criteria: {id,type,title,scope,criteria:[{name,score,description}],total,sourcePages}
- table: {id,type,title?,caption?,columns:[...],rows:[[...]],sourcePages}

FORMA DE RESPUESTA
{
  "tender": {
    "recipient": "",
    "reference": "",
    "title": "",
    "submissionChannel": "",
    "tenderUrl": "",
    "deadline": {"day":"","month":"","year":"","weekday":"","time":""},
    "highlights": [{"label":"","value":"","detail":""}],
    "details": [{"label":"","value":"","note":"","emphasis":"positive|warning|none"}]
  },
  "sections": [{
    "id": "",
    "eyebrow": "",
    "title": "",
    "introduction": "",
    "sourcePages": [1],
    "blocks": []
  }],
  "sourceCoverage": [{
    "page": 1,
    "sourceSha256": "hash facilitado",
    "visualReviewed": true,
    "coveredBlockIds": ["id-bloque"],
    "unmappedContent": []
  }],
  "qualityNotes": []
}

Devuelve únicamente el objeto JSON.
""".strip()


def build_portal_ai_context(base_model: dict[str, object]) -> str:
    source = dict(base_model.get("source") or {})
    pages = []
    for page in source.get("pages") or []:
        pages.append(
            {
                "page": page.get("number"),
                "sourceSha256": page.get("text_sha256"),
                "extractedText": page.get("text"),
                "embeddedImages": page.get("embedded_images"),
                "visualFallbackRequired": page.get("visual_fallback_required"),
            }
        )
    context = {
        "suiteTender": base_model.get("tender") or {},
        "sourcePdf": {
            "name": source.get("name"),
            "sha256": source.get("sha256"),
            "pageCount": source.get("page_count"),
            "pages": pages,
        },
    }
    return "CONTEXTO Y TEXTO EXTRAÍDO, PÁGINA A PÁGINA:\n" + json.dumps(context, ensure_ascii=False)
