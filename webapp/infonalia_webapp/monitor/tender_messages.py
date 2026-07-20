from __future__ import annotations

import html
from typing import Iterable, Mapping

from .snapshots import normalize_text


CHANGE_LABELS = {
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


def build_notification_content(
    licitacion: Mapping[str, object],
    *,
    platform: str,
    checked_at: str,
    differences: Iterable[Mapping[str, object]],
    ai_summary: str = "",
    ai_failed: bool = False,
    suite_url: str = "",
) -> dict[str, str]:
    rows = list(differences)
    expediente = normalize_text(licitacion.get("expediente")) or f"ID {licitacion.get('id')}"
    title = normalize_text(licitacion.get("objeto")) or "Sin título"
    platform_url = normalize_text(licitacion.get("enlace_perfil"))
    summary = differences_summary(rows)
    subject = f"[Llangon Monitor] {expediente}: {len(rows)} novedad(es)"
    detail_lines = [
        f"- {CHANGE_LABELS.get(normalize_text(item.get('change_type')), 'Cambio oficial')}: {normalize_text(item.get('title'))}"
        for item in rows
    ]
    text_parts = [
        f"Expediente: {expediente}",
        f"Título: {title}",
        f"Plataforma: {platform}",
        f"Comprobación: {checked_at}",
        "",
        f"Resumen: {summary}",
        *detail_lines,
    ]
    if ai_summary:
        text_parts.extend(["", "Análisis IA:", ai_summary])
    elif ai_failed:
        text_parts.extend(["", "El análisis IA no pudo completarse; el aviso se envía sin análisis."])
    if suite_url:
        text_parts.extend(["", f"Ficha de la Suite: {suite_url}"])
    if platform_url:
        text_parts.append(f"Plataforma oficial: {platform_url}")
    text = "\n".join(text_parts)

    items_html = "".join(
        f"<li><strong>{html.escape(CHANGE_LABELS.get(normalize_text(item.get('change_type')), 'Cambio oficial'))}:</strong> "
        f"{html.escape(normalize_text(item.get('title')))}</li>"
        for item in rows
    )
    html_parts = [
        "<main style=\"font-family:Arial,sans-serif;line-height:1.5;color:#172033\">",
        f"<h1>Novedades en {html.escape(expediente)}</h1>",
        f"<p><strong>{html.escape(title)}</strong></p>",
        f"<p>Plataforma: {html.escape(platform)}<br>Comprobación: {html.escape(checked_at)}</p>",
        f"<p>{html.escape(summary)}</p><ul>{items_html}</ul>",
    ]
    if ai_summary:
        html_parts.append(f"<h2>Análisis IA</h2><p>{html.escape(ai_summary)}</p>")
    elif ai_failed:
        html_parts.append("<p><strong>La IA falló o agotó su tiempo; este aviso se envía sin análisis.</strong></p>")
    links = []
    if suite_url:
        links.append(f'<a href="{html.escape(suite_url, quote=True)}">Abrir ficha en la Suite</a>')
    if platform_url:
        links.append(f'<a href="{html.escape(platform_url, quote=True)}">Abrir plataforma oficial</a>')
    if links:
        html_parts.append("<p>" + " · ".join(links) + "</p>")
    html_parts.append("</main>")

    telegram = f"🔎 {expediente} · {title[:80]}\n{summary}"
    if ai_summary:
        telegram += "\nIA: análisis disponible"
    elif ai_failed:
        telegram += "\nIA: aviso enviado sin análisis"
    if suite_url:
        telegram += f"\n{suite_url}"
    return {"subject": subject, "text": text, "html": "".join(html_parts), "telegram": telegram[:3900]}


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
