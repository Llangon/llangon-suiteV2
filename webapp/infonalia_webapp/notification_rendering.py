from __future__ import annotations

import html

try:
    from .email_templates import build_llangon_email_shell
    from .formatting import format_datetime_es
    from .normalization import clean_text
except ImportError:
    from email_templates import build_llangon_email_shell
    from formatting import format_datetime_es
    from normalization import clean_text


def notification_body_parts(cuerpo: str) -> tuple[list[str], list[tuple[str, str]]]:
    paragraphs: list[str] = []
    details: list[tuple[str, str]] = []

    for raw_line in (cuerpo or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue

        if ":" in line:
            label, value = line.split(":", 1)
            label = clean_text(label)
            value = clean_text(value)
            if label and value and len(label) <= 45:
                details.append((label, value))
                continue

        paragraphs.append(line)

    return paragraphs, details


def parse_day_review_notification(cuerpo: str) -> dict[str, object] | None:
    total = ""
    pendientes = ""
    intro_lines: list[str] = []
    pending_items: list[dict[str, str]] = []
    no_interesting = False

    for raw_line in (cuerpo or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if line.startswith("Total de licitaciones del día:"):
            total = clean_text(line.split(":", 1)[1])
            continue
        if line.startswith("Licitaciones pendientes de revisión:"):
            pendientes = clean_text(line.split(":", 1)[1])
            continue
        if line == "NO HAY LICITACIONES INTERESANTES":
            no_interesting = True
            continue
        if line.startswith("- "):
            parts = [clean_text(part) for part in line[2:].split(" | ")]
            if len(parts) >= 3:
                pending_items.append(
                    {
                        "expediente": parts[0],
                        "titulo": parts[1],
                        "fecha_hora": parts[2],
                    }
                )
            continue
        if line != "Listado de licitaciones pendientes:":
            intro_lines.append(line)

    if not total and not pendientes and not no_interesting and not pending_items:
        return None

    return {
        "intro": intro_lines,
        "total": total or "0",
        "pendientes": pendientes or "0",
        "no_interesting": no_interesting,
        "pending_items": pending_items,
    }


def build_notification_email_html(
    asunto: str,
    cuerpo: str,
    usuario_destino: str | None,
    platform_url: str = "",
    generated_at: object = "",
) -> str:
    parsed_day_review = None
    paragraphs, details = notification_body_parts(cuerpo)
    safe_subject = html.escape(clean_text(asunto) or "Notificación")
    recipient_label = clean_text(usuario_destino) or "Todos los usuarios"
    recipient_label = html.escape(recipient_label)
    date_label = html.escape(format_datetime_es(generated_at))
    action_button_html = ""

    if "disponible para revisar" in clean_text(asunto).lower() and platform_url:
        parsed_day_review = parse_day_review_notification(cuerpo)
        action_button_html = (
            f"<div style='margin:16px 0 18px 0;'>"
            f"<a href='{html.escape(platform_url)}' "
            "style='display:inline-block; background:#19b51f; color:#ffffff; text-decoration:none; "
            "padding:11px 18px; border-radius:8px; font-size:14px; font-weight:800;'>"
            "Acceder a la plataforma"
            "</a>"
            "</div>"
        )

    if parsed_day_review:
        intro_html = "".join(
            f"<p style='margin:0 0 10px 0; line-height:1.45;'>{html.escape(paragraph)}</p>"
            for paragraph in parsed_day_review["intro"]
        )
        metrics_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin-top:18px; "
            "border:1px solid #d9e2ec; border-radius:10px; overflow:hidden;'>"
            "<tr>"
            "<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase; border-bottom:1px solid #e4eaf0;'>Total de licitaciones del día</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; border-bottom:1px solid #e4eaf0; text-align:right;'>{html.escape(str(parsed_day_review['total']))}</td>"
            "</tr>"
            "<tr>"
            "<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase;'>Licitaciones pendientes de revisión</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; text-align:right;'>{html.escape(str(parsed_day_review['pendientes']))}</td>"
            "</tr>"
            "</table>"
        )
        if parsed_day_review["no_interesting"]:
            pending_html = (
                "<div style='margin-top:18px; padding:16px 18px; background:#f1fff2; border:1px solid #d7e7d8; "
                "border-radius:10px; color:#0e7f15; font-size:15px; font-weight:800;'>"
                "NO HAY LICITACIONES INTERESANTES"
                "</div>"
            )
        else:
            rows = "".join(
                "<tr>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; font-weight:700; vertical-align:top;'>{html.escape(item['expediente'])}</td>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; vertical-align:top;'>{html.escape(item['titulo'])}</td>"
                f"<td style='padding:12px; border-bottom:1px solid #e4eaf0; color:#1f2937; font-size:13px; vertical-align:top; white-space:nowrap;'>{html.escape(item['fecha_hora'])}</td>"
                "</tr>"
                for item in parsed_day_review["pending_items"]
            )
            pending_html = (
                "<div style='margin-top:18px;'>"
                "<p style='margin:0 0 10px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;'>Listado de licitaciones pendientes</p>"
                "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; border:1px solid #d9e2ec; border-radius:10px; overflow:hidden;'>"
                "<tr>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Expediente</th>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Título</th>"
                "<th align='left' style='padding:10px 12px; background:#f7faf8; color:#667085; font-size:12px; text-transform:uppercase;'>Fecha y hora de presentación</th>"
                "</tr>"
                f"{rows}"
                "</table>"
                "</div>"
            )
        body_html = f"{intro_html}{metrics_html}{pending_html}"
        details_html = ""
    elif paragraphs:
        body_html = "".join(
            f"<p style='margin:0 0 10px 0; line-height:1.45;'>{html.escape(paragraph)}</p>"
            for paragraph in paragraphs
        )
    else:
        body_html = "<p style='margin:0; line-height:1.45;'>Tienes una nueva notificación en el panel privado.</p>"

    if not parsed_day_review and details:
        detail_rows = "".join(
            "<tr>"
            f"<td style='padding:10px 12px; color:#667085; font-size:12px; font-weight:700; text-transform:uppercase; border-bottom:1px solid #e4eaf0;'>{html.escape(label)}</td>"
            f"<td style='padding:10px 12px; color:#1f2937; font-size:14px; border-bottom:1px solid #e4eaf0; text-align:right;'>{html.escape(value)}</td>"
            "</tr>"
            for label, value in details
        )
        details_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin-top:18px; border:1px solid #d9e2ec;'>"
            f"{detail_rows}"
            "</table>"
        )
    elif not parsed_day_review:
        details_html = ""

    content_html = f"""
                {action_button_html}
                <table width="100%" cellpadding="0" cellspacing="0" style="border-left:5px solid #2dad2c; background:#ffffff; border-collapse:collapse;">
                  <tr>
                    <td style="padding:0 0 0 18px;">
                      <p style="margin:0 0 8px 0; color:#667085; font-size:12px; font-weight:800; text-transform:uppercase;">Asunto</p>
                      <h2 style="margin:0 0 18px 0; color:#1f2937; font-size:20px; line-height:1.25;">{safe_subject}</h2>
                      <div style="margin:0 0 18px 0; color:#1f2937; font-size:15px;">
                        {body_html}
                      </div>
                      {details_html}
                    </td>
                  </tr>
                </table>"""

    return build_llangon_email_shell(
        eyebrow="Llangón Web App",
        title="Nueva notificación",
        body_html=content_html,
        footer_left_html=f"Destinatario: {recipient_label}",
        footer_right_html=date_label,
        closing_html="Este correo se ha generado automáticamente desde el panel privado de Asesores Llangón.",
    )
