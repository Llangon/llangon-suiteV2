from __future__ import annotations

import html
from datetime import datetime
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

try:
    from ..email_templates import build_llangon_email_shell
except ImportError:  # pragma: no cover
    from email_templates import build_llangon_email_shell

from .snapshots import normalize_text
from .tender_email_assets import folder_name


CHANGE_LABELS = {
    "publication_new": "Nueva publicación y carpeta creada",
    "publication_modified": "Publicación modificada",
    "publication_removed": "Publicación retirada oficialmente",
    "publication_restored": "Publicación restaurada",
    "document_new": "Documento nuevo",
    "document_modified": "Documento modificado",
    "document_removed": "Documento retirado oficialmente",
    "document_restored": "Documento restaurado oficialmente",
    "question_new": "Pregunta o respuesta nueva",
    "question_modified": "Pregunta o respuesta modificada",
    "question_removed": "Pregunta o respuesta retirada",
    "question_restored": "Pregunta o respuesta restaurada",
    "field_changed": "Dato oficial modificado",
}


def differences_summary(differences: Iterable[Mapping[str, object]]) -> str:
    counts: dict[str, int] = {}
    for item in differences:
        label = CHANGE_LABELS.get(normalize_text(item.get("change_type")), "Cambio oficial")
        counts[label] = counts.get(label, 0) + 1
    return "; ".join(f"{label}: {count}" for label, count in counts.items())


def _deadline_label(licitacion: Mapping[str, object]) -> str:
    raw_date = normalize_text(licitacion.get("fecha_limite") or licitacion.get("fecha_presentacion"))
    raw_time = normalize_text(licitacion.get("hora_limite"))
    if not raw_date:
        return "No consta"
    try:
        value = datetime.strptime(raw_date[:10], "%Y-%m-%d")
        label = value.strftime("%d/%m/%Y")
    except ValueError:
        label = raw_date
    return " ".join(part for part in (label, raw_time) if part)


def _file_size_label(value: object) -> str:
    size = int(value or 0)
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} bytes" if size else "tamaño no disponible"


def _datetime_label(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return "No consta"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%d/%m/%Y · %H:%M")


FIELD_LABELS = {
    "fecha_limite": "fecha límite de presentación",
    "hora_limite": "hora límite de presentación",
    "presupuesto": "presupuesto",
    "presupuesto_base": "presupuesto base",
    "valor_estimado": "valor estimado",
    "estado": "estado del expediente",
    "objeto": "objeto del contrato",
    "organismo": "organismo",
}


def _readable_value(value: object) -> str:
    if value in (None, "", [], {}):
        return "sin información"
    if isinstance(value, Mapping):
        for key in ("name", "title", "value", "label"):
            if normalize_text(value.get(key)):
                return normalize_text(value.get(key))
    return normalize_text(value)


def _field_change_sentence(item: Mapping[str, object]) -> str:
    key = normalize_text(item.get("item_key")).casefold()
    label = FIELD_LABELS.get(key, key.replace("_", " ") or "dato del expediente")
    old = _readable_value(item.get("old_value"))
    new = _readable_value(item.get("new_value"))
    if item.get("old_value") in (None, "", [], {}):
        return f"Se ha informado {label}: {new}."
    if item.get("new_value") in (None, "", [], {}):
        return f"Ya no consta {label}; anteriormente figuraba {old}."
    return f"{label[:1].upper() + label[1:]}: antes figuraba {old} y ahora figura {new}."


def _document_details(item: Mapping[str, object]) -> tuple[str, str, str]:
    value = item.get("new_value") if isinstance(item.get("new_value"), Mapping) else {}
    name = normalize_text(item.get("title") or value.get("name")) or "Documento sin nombre"
    date_label = _datetime_label(value.get("published_at")) if value.get("published_at") else ""
    document_type = normalize_text(value.get("section") or value.get("role"))
    if document_type.casefold() in {"document", "documento"}:
        document_type = "Documento de la licitación"
    description = normalize_text(value.get("description") or value.get("descripcion"))
    meta = " · ".join(part for part in (document_type, date_label) if part)
    return name, meta, description


def _question_datetime_label(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(ZoneInfo("Europe/Madrid"))
    return parsed.strftime("%d-%m-%Y a las %H:%M")


def _html_text(value: object) -> str:
    return html.escape(normalize_text(value)).replace("\n", "<br>")


def build_notification_content(
    licitacion: Mapping[str, object],
    *,
    platform: str,
    checked_at: str,
    differences: Iterable[Mapping[str, object]],
    ai_summary: str = "",
    ai_failed: bool = False,
    suite_url: str = "",
    attachment_names: Iterable[str] = (),
    omitted_attachments: Iterable[Mapping[str, object]] = (),
) -> dict[str, str]:
    rows = list(differences)
    expediente = normalize_text(licitacion.get("expediente")) or f"ID {licitacion.get('id')}"
    title = normalize_text(licitacion.get("objeto")) or "Sin título"
    platform_url = normalize_text(licitacion.get("enlace_perfil"))
    summary = differences_summary(rows)
    folder_path = normalize_text(licitacion.get("ruta_carpeta"))
    subject_label = folder_name(folder_path) or expediente
    subject = f"[Llangon Monitor] {subject_label}"
    deadline = _deadline_label(licitacion)
    attached = [normalize_text(name) for name in attachment_names if normalize_text(name)]
    omitted = [dict(item) for item in omitted_attachments]
    checked_label = _datetime_label(checked_at)
    organismo = normalize_text(licitacion.get("organismo")) or "No consta"
    status = normalize_text(licitacion.get("estado")) or "En seguimiento"
    documents = [item for item in rows if normalize_text(item.get("change_type")).startswith("document_")]
    questions = [item for item in rows if normalize_text(item.get("change_type")).startswith("question_")]
    field_changes = [item for item in rows if normalize_text(item.get("change_type")) == "field_changed"]
    known_ids = {id(item) for item in [*documents, *questions, *field_changes]}
    other_changes = [item for item in rows if id(item) not in known_ids]
    novelty_word = "novedad" if len(rows) == 1 else "novedades"
    text_parts = [
        "INFORME DE SEGUIMIENTO DE LICITACIÓN",
        "",
        title,
        f"Expediente: {expediente}",
        f"Organismo: {organismo}",
        f"Revisión: {checked_label}",
        f"Estado: {status}",
        f"Fecha límite de presentación: {deadline}",
        f"Ubicación en Dropbox: {folder_path or 'No consta'}",
        "",
    ]
    if ai_summary:
        text_parts.extend(["RESUMEN EJECUTIVO", ai_summary, ""])
    text_parts.extend(["¿QUÉ HA CAMBIADO?", f"Desde la última revisión se han detectado {len(rows)} {novelty_word}.", ""])
    if documents:
        text_parts.append("DOCUMENTOS PUBLICADOS")
        for item in documents:
            name, meta, description = _document_details(item)
            text_parts.append(f"- {name}" + (f" | {meta}" if meta else "") + (f" | {description}" if description else ""))
        text_parts.append("")
    if field_changes:
        text_parts.extend(["CAMBIOS DEL EXPEDIENTE", *[f"- {_field_change_sentence(item)}" for item in field_changes], ""])
    if questions:
        text_parts.append("PREGUNTAS Y RESPUESTAS")
        for item in questions:
            text_parts.append(f"- {normalize_text(item.get('title'))}")
            if normalize_text(item.get("question_text")):
                text_parts.append(f"  Pregunta: {normalize_text(item.get('question_text'))}")
            if normalize_text(item.get("answer_text")):
                text_parts.append(f"  Respuesta: {normalize_text(item.get('answer_text'))}")
        text_parts.append("")
    if other_changes:
        text_parts.extend(
            [
                "OTRAS NOVEDADES",
                *[f"- {CHANGE_LABELS.get(normalize_text(item.get('change_type')), 'Cambio oficial')}: {normalize_text(item.get('title'))}" for item in other_changes],
                "",
            ]
        )
    if omitted:
        text_parts.extend(
            [
                "Archivos no adjuntados por protección de tamaño:",
                *[f"- {normalize_text(item.get('name'))} ({_file_size_label(item.get('size'))})" for item in omitted],
                f"Están disponibles en Dropbox: {folder_path or 'No consta'}",
                "",
            ]
        )
    if platform_url:
        text_parts.extend([f"Publicación oficial: {platform_url}", ""])
    text_parts.append("Correo generado automáticamente por Llangon Suite.")
    text = "\n".join(text_parts).strip()

    def section_title(label: str) -> str:
        return (
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
            'style="margin:28px 0 12px;border-collapse:collapse;background:#eaf7ea;border-left:4px solid #2dad2c">'
            '<tr><td style="padding:8px 11px">'
            f'<h2 style="margin:0;color:#1f5f36;font-size:15px;line-height:1.3">{html.escape(label)}</h2>'
            '</td></tr></table>'
        )

    documents_html = ""
    if documents:
        entries = []
        for item in documents:
            name, meta, description = _document_details(item)
            entries.append(
                '<div style="margin:0 0 14px;padding:0 0 14px;border-bottom:1px solid #eaecf0">'
                f'<p style="margin:0;color:#1f2937;font-size:15px;font-weight:800;line-height:1.35">{html.escape(name)}</p>'
                + (f'<p style="margin:5px 0 0;color:#667085;font-size:12px">{html.escape(meta)}</p>' if meta else "")
                + (f'<p style="margin:7px 0 0;color:#475467;font-size:13px;line-height:1.5">{html.escape(description)}</p>' if description else "")
                + '</div>'
            )
        documents_html = section_title("Documentos publicados") + "".join(entries)

    fields_html = ""
    if field_changes:
        fields_html = section_title("Cambios del expediente") + "".join(
            f'<p style="margin:0 0 10px;padding-left:14px;border-left:3px solid #d0d5dd;color:#344054;font-size:14px;line-height:1.5">{html.escape(_field_change_sentence(item))}</p>'
            for item in field_changes
        )

    questions_html = ""
    if questions:
        question_blocks = []
        for index, item in enumerate(questions, start=1):
            question = normalize_text(item.get("question_text"))
            answer = normalize_text(item.get("answer_text"))
            number = int(item.get("question_number") or index)
            date_label = _question_datetime_label(item.get("official_datetime"))
            label = f"Pregunta {number}" + (f" del {date_label}" if date_label else "")
            response_attachments = item.get("question_attachments") if isinstance(item.get("question_attachments"), list) else []
            content = [
                '<div style="margin:0 0 28px">',
                f'<p style="margin:0;padding:0 0 8px;border-bottom:1px solid #cfd4dc;color:#1f2937;font-size:14px;font-weight:800;line-height:1.35">{html.escape(label)}</p>',
            ]
            if question:
                content.append(f'<p style="margin:10px 0 0;color:#1f2937;font-size:13px;line-height:1.55">{_html_text(question)}</p>')
            if answer:
                content.append(f'<p style="margin:10px 0 5px;color:#1f2937;font-size:13px;font-weight:800">Respuesta</p><p style="margin:0;color:#1f2937;font-size:13px;line-height:1.55">{_html_text(answer)}</p>')
            if response_attachments:
                content.append('<p style="margin:10px 0 4px;color:#1f2937;font-size:12px;font-weight:800">Archivos adjuntos a la respuesta</p>')
                for attachment in response_attachments:
                    attachment_name = html.escape(normalize_text(attachment.get("name")))
                    attachment_url = html.escape(normalize_text(attachment.get("url")), quote=True)
                    reference = html.escape(normalize_text(attachment.get("source_id")))
                    name_html = f'<a href="{attachment_url}" style="color:#344054;text-decoration:underline">{attachment_name}</a>' if attachment_url else f'<span style="text-decoration:underline">{attachment_name}</span>'
                    reference_html = f' &nbsp;·&nbsp; Ref. {reference}' if reference else ''
                    content.append(f'<p style="margin:0 0 0 16px;color:#667085;font-size:11px;line-height:1.45">{name_html}{reference_html}</p>')
            content.append('</div>')
            question_blocks.append("".join(content))
        questions_html = section_title("Preguntas y respuestas") + "".join(question_blocks)

    other_html = ""
    if other_changes:
        other_html = section_title("Otras novedades") + "".join(
            f'<p style="margin:0 0 9px;color:#344054;font-size:14px;line-height:1.45"><strong>{html.escape(CHANGE_LABELS.get(normalize_text(item.get("change_type")), "Cambio oficial"))}:</strong> {html.escape(normalize_text(item.get("title")))}</p>'
            for item in other_changes
        )
    omitted_html = ""
    if omitted:
        omitted_html = (
            '<table width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0 0;border-collapse:collapse;background:#fff8e1;border:1px solid #ead48a;border-radius:8px"><tr><td style="padding:14px 16px">'
            '<p style="margin:0 0 6px;color:#8a5a00;font-size:13px;font-weight:800">Protección de tamaño activada</p>'
            '<p style="margin:0;color:#6f5200;font-size:13px;line-height:1.45">El correo se ha enviado sin los siguientes archivos para evitar que el servidor lo rechace:</p>'
            + "".join(f'<p style="margin:6px 0 0;color:#6f5200;font-size:13px"><strong>{html.escape(normalize_text(item.get("name")))}</strong> · {html.escape(_file_size_label(item.get("size")))}</p>' for item in omitted)
            + '<p style="margin:8px 0 0;color:#6f5200;font-size:13px">Los archivos permanecen disponibles en la ruta de Dropbox indicada.</p></td></tr></table>'
        )
    fact_rows = [
        ("Licitación", title),
        ("Expediente", expediente),
        ("Organismo", organismo),
        ("Fecha de revisión", checked_label),
        ("Estado actual", status),
        ("Fecha límite", deadline),
    ]
    facts_html = "".join(
        '<tr>'
        f'<td width="32%" style="padding:5px 12px 5px 0;color:#667085;font-size:12px;vertical-align:top">{html.escape(label)}</td>'
        f'<td style="padding:5px 0;color:#1f2937;font-size:13px;font-weight:{"800" if label == "Licitación" else "400"};line-height:1.4">{html.escape(value)}</td>'
        '</tr>'
        for label, value in fact_rows
    )
    body_parts = [
        f'<p style="margin:0 0 16px"><span style="display:inline-block;padding:4px 9px;border-radius:999px;background:#ecfdf3;color:#067647;font-size:11px;font-weight:800">{len(rows)} {html.escape(novelty_word)}</span></p>',
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{facts_html}</table>',
    ]
    if ai_summary:
        body_parts.append(f'<div style="margin:24px 0 0;padding:20px;background:#f0fdf4;border-left:4px solid #2dad2c;border-radius:6px"><p style="margin:0 0 8px;color:#067647;font-size:12px;font-weight:800;text-transform:uppercase">Resumen ejecutivo</p><p style="margin:0;color:#1f2937;font-size:15px;line-height:1.6;white-space:pre-line">{html.escape(ai_summary)}</p></div>')
    body_parts.append(
        section_title("¿Qué ha cambiado?")
        + f'<p style="margin:0 0 20px;color:#344054;font-size:15px;line-height:1.55">Desde la última revisión se han detectado <strong>{len(rows)} {html.escape(novelty_word)}</strong>.</p>'
        + documents_html
        + fields_html
        + questions_html
        + other_html
        + omitted_html
    )
    if platform_url:
        body_parts.append(
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:26px 0 0;border-collapse:collapse;border-top:1px solid #eaecf0"><tr><td align="center" style="padding:22px 0 2px">'
            '<p style="margin:0 0 12px;color:#667085;font-size:12px;line-height:1.4">Consulta el anuncio y la documentación publicados por el órgano de contratación.</p>'
            '<table cellpadding="0" cellspacing="0" role="presentation" style="border-collapse:separate"><tr><td bgcolor="#1f7a4d" style="border-radius:7px">'
            f'<a href="{html.escape(platform_url, quote=True)}" style="display:inline-block;padding:12px 22px;color:#ffffff;text-decoration:none;font-size:13px;font-weight:800">Acceder a la plataforma oficial &nbsp;&rarr;</a>'
            '</td></tr></table></td></tr></table>'
        )
    body_html = "".join(body_parts)
    rendered_html = build_llangon_email_shell(
        eyebrow="Llangon Suite",
        title="Informe de seguimiento",
        subtitle=subject_label,
        body_html=body_html,
        footer_left_html=f"{len(rows)} novedad{'es' if len(rows) != 1 else ''} detectada{'s' if len(rows) != 1 else ''}",
        footer_right_html=html.escape(checked_at),
        closing_html="Correo generado automáticamente por Llangon Suite.",
    )

    telegram = f"🔎 {expediente} · {title[:80]}\n{summary}"
    if ai_summary:
        telegram += "\nIA: análisis disponible"
    elif ai_failed:
        telegram += "\nIA: aviso enviado sin análisis"
    return {"subject": subject, "text": text, "html": rendered_html, "telegram": telegram[:3900]}


def build_incident_report(
    cycle: Mapping[str, object],
    incidents: Iterable[Mapping[str, object]],
    *,
    suite_base_url: str = "",
) -> dict[str, str]:
    rows = list(incidents)
    subject = f"[Llangon Monitor] Incidencias del ciclo {cycle.get('id')} ({len(rows)})"
    lines = [f"Ciclo: {cycle.get('id')}", f"Origen: {cycle.get('origin')}", ""]
    html_rows = []
    for item in rows:
        expediente = normalize_text(item.get("expediente")) or f"Licitación {item.get('licitacion_id') or '-'}"
        title = normalize_text(item.get("objeto")) or "Sin título"
        platform = normalize_text(item.get("plataforma")) or "Sin plataforma"
        summary = normalize_text(item.get("summary"))
        phase = normalize_text(item.get("phase"))
        outcome = normalize_text(item.get("outcome"))
        suite_url = ""
        if suite_base_url and item.get("licitacion_id"):
            suite_url = suite_base_url.rstrip("/") + f"/app/licitaciones/{item.get('licitacion_id')}"
        lines.append(
            f"- {expediente} · {title} · {platform} · {phase}: {summary} · "
            f"reintentos {item.get('retry_count', 0)} · {outcome}"
            + (f" · {suite_url}" if suite_url else "")
        )
        expediente_html = html.escape(expediente)
        if suite_url:
            expediente_html = f'<a href="{html.escape(suite_url, quote=True)}">{expediente_html}</a>'
        html_rows.append(
            "<tr>"
            f"<td>{expediente_html}</td><td>{html.escape(title)}</td><td>{html.escape(platform)}</td><td>{html.escape(phase)}</td>"
            f"<td>{html.escape(summary)}</td><td>{int(item.get('retry_count') or 0)}</td>"
            f"<td>{html.escape(outcome)}</td></tr>"
        )
    body_html = (
        "<main style=\"font-family:Arial,sans-serif\"><h1>Incidencias del monitor</h1>"
        f"<p>Ciclo {int(cycle.get('id') or 0)} · {html.escape(normalize_text(cycle.get('origin')))}</p>"
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"6\"><thead><tr>"
        "<th>Expediente</th><th>Título</th><th>Plataforma</th><th>Fase</th><th>Resumen</th><th>Reintentos</th><th>Resultado</th>"
        "</tr></thead><tbody>" + "".join(html_rows) + "</tbody></table></main>"
    )
    return {"subject": subject, "text": "\n".join(lines), "html": body_html}
