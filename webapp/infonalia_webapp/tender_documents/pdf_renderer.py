"""Professional ReportLab renderer for Ficha Llangon v2."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    CondPageBreak,
    Image as PlatypusImage,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .payload import clean_text, normalize_payload
from .validation import validate_payload
from .workbook_images import WorkbookImage


BRAND_GREEN = colors.HexColor("#3AAE2A")
BRAND_GREEN_DARK = colors.HexColor("#176B32")
TEXT = colors.HexColor("#263238")
MUTED = colors.HexColor("#607067")
LIGHT_GREEN = colors.HexColor("#F0F8F1")
LIGHT_GREY = colors.HexColor("#F4F6F5")
BORDER = colors.HexColor("#CBD8CF")
ALERT = colors.HexColor("#FFF4D8")
PAGE_W, PAGE_H = A4
MARGIN_X = 15 * mm
MARGIN_TOP = 30 * mm
MARGIN_BOTTOM = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X


@dataclass(frozen=True, slots=True)
class PdfResult:
    path: Path
    page_count: int
    sha256: str
    size_bytes: int
    warnings: tuple[str, ...]


def _fonts() -> tuple[str, str]:
    windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    candidates = (
        ("SegoeUI", windows_fonts / "segoeui.ttf", windows_fonts / "segoeuib.ttf"),
        ("Calibri", windows_fonts / "calibri.ttf", windows_fonts / "calibrib.ttf"),
        ("Arial", windows_fonts / "arial.ttf", windows_fonts / "arialbd.ttf"),
    )
    for family, regular, bold in candidates:
        if not regular.is_file() or not bold.is_file():
            continue
        regular_name = f"{family}-Ficha-Regular"
        bold_name = f"{family}-Ficha-Bold"
        if regular_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
        if bold_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
        return regular_name, bold_name
    return "Helvetica", "Helvetica-Bold"


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = clean_text(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _url_paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = clean_text(value)
    parsed = urlparse(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return _paragraph(text, style)
    href = escape(text, quote=True)
    label = escape(text)
    return Paragraph(f'<link href="{href}" color="#176B32"><u>{label}</u></link>', style)


def _money(value: object) -> str:
    if value in (None, ""):
        return ""
    text = clean_text(value).replace("€", "").replace(" ", "")
    try:
        amount = float(text.replace(".", "").replace(",", ".") if "," in text else text)
    except ValueError:
        return clean_text(value)
    return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _nonempty_rows(items: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    return [item for item in items if any(clean_text(item.get(key)) for key in keys)]


def _recipient_name(recipient: dict[str, Any]) -> str:
    return clean_text(recipient.get("razon_social_snapshot") or recipient.get("client_display"))


def _notice_text(template: object, recipient_name: str) -> str:
    return clean_text(template).replace("{DESTINATARIO}", recipient_name)


def render_tender_pdf(
    payload_raw: dict[str, Any],
    output_path: str | Path,
    *,
    draft: bool = False,
    workbook_images: Iterable[WorkbookImage] = (),
) -> PdfResult:
    from pypdf import PdfReader

    payload = normalize_payload(payload_raw)
    issues = validate_payload(payload)
    errors = [item for item in issues if item.severity == "error"]
    if errors and not draft:
        raise ValueError("El PDF final no puede generarse mientras existan errores de validación.")

    regular, bold = _fonts()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "FichaBody", parent=styles["BodyText"], fontName=regular, fontSize=9.2,
        leading=12.2, textColor=TEXT, spaceAfter=2,
    )
    small = ParagraphStyle(
        "FichaSmall", parent=body, fontSize=8, leading=10, textColor=MUTED,
    )
    label = ParagraphStyle(
        "FichaLabel", parent=small, fontName=bold, textColor=BRAND_GREEN_DARK,
    )
    title = ParagraphStyle(
        "FichaTitle", parent=styles["Title"], fontName=bold, fontSize=19,
        leading=22, textColor=TEXT, alignment=TA_LEFT, spaceAfter=2,
    )
    subtitle = ParagraphStyle(
        "FichaSubtitle", parent=body, fontName=bold, fontSize=10.5,
        leading=13, textColor=BRAND_GREEN_DARK,
    )
    section = ParagraphStyle(
        "FichaSection", parent=body, fontName=bold, fontSize=11.2,
        leading=14, textColor=BRAND_GREEN_DARK, spaceBefore=7, spaceAfter=5,
        keepWithNext=False,
    )
    table_head = ParagraphStyle(
        "FichaTableHead", parent=small, fontName=bold, textColor=colors.white,
        alignment=TA_LEFT,
    )
    table_body = ParagraphStyle("FichaTableBody", parent=small, textColor=TEXT)
    warning_style = ParagraphStyle(
        "FichaWarning", parent=small, fontName=bold, textColor=colors.HexColor("#795600"),
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Ya existe el PDF de destino: {target.name}")
    image_items = tuple(item for item in workbook_images if item.path.is_file())
    workbook_logo = next(
        (item for item in image_items if item.kind == "floating" and item.section_number == 0 and item.row <= 5),
        None,
    )
    body_images = tuple(item for item in image_items if item is not workbook_logo)
    logo = workbook_logo.path if workbook_logo is not None else Path(__file__).resolve().parents[1] / "static" / "logo-llangon.png"
    tender = payload["tender"]
    recipient = payload["recipient"]
    analysis = payload["analysis"]
    recipient_name = _recipient_name(recipient) or "No consta"
    confidentiality_notice = _notice_text(payload["control"].get("confidentiality_notice"), recipient_name)
    chrome_header = ParagraphStyle(
        "FichaChromeHeader", parent=small, fontName=regular, fontSize=7.2,
        leading=8.6, textColor=MUTED, alignment=TA_RIGHT,
    )
    chrome_footer = ParagraphStyle(
        "FichaChromeFooter", parent=small, fontName=regular, fontSize=6.8,
        leading=8, textColor=MUTED, alignment=TA_LEFT,
    )

    def page_chrome(canvas: Canvas, _doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        if logo.is_file():
            canvas.drawImage(str(logo), MARGIN_X, PAGE_H - 17 * mm, width=30 * mm, height=12.5 * mm, preserveAspectRatio=True, mask="auto")
        header = Paragraph(
            f'<font name="{bold}">DESTINATARIO:</font> {escape(recipient_name)}',
            chrome_header,
        )
        header_width, header_height = header.wrap(132 * mm, 11 * mm)
        header.drawOn(canvas, PAGE_W - MARGIN_X - header_width, PAGE_H - 8 * mm - header_height)
        canvas.setStrokeColor(BRAND_GREEN)
        canvas.setLineWidth(1.1)
        canvas.line(MARGIN_X, PAGE_H - 19 * mm, PAGE_W - MARGIN_X, PAGE_H - 19 * mm)
        if confidentiality_notice:
            footer = Paragraph(escape(confidentiality_notice), chrome_footer)
            footer_width, footer_height = footer.wrap(135 * mm, 12 * mm)
            footer.drawOn(canvas, MARGIN_X, 5.2 * mm)
        if draft:
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.65, 0.72, 0.67, alpha=0.14))
            canvas.setFont(bold, 52)
            canvas.translate(PAGE_W / 2, PAGE_H / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "BORRADOR")
            canvas.restoreState()
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(target.with_suffix(".tmp.pdf")), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title="Ficha de licitación - Llangon",
        author="Llangon",
        subject="Ficha profesional de licitación",
    )
    story: list[Any] = []

    header_left = [
        _paragraph("FICHA DE LICITACIÓN", title),
        _paragraph(tender.get("objeto") or "Licitación sin título", subtitle),
    ]
    header_right = [
        _paragraph("EXPEDIENTE", label),
        _paragraph(tender.get("expediente") or "No consta", subtitle),
        Spacer(1, 3),
        _paragraph("DESTINATARIO", label),
        _paragraph(recipient_name, body),
    ]
    top = Table([[header_left, header_right]], colWidths=[CONTENT_W * 0.66, CONTENT_W * 0.34])
    top.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether([top, Spacer(1, 5)]))

    deadline_text = clean_text(tender.get("fecha_limite")) or "No consta"
    if clean_text(tender.get("hora_limite")):
        deadline_text += f" - {clean_text(tender.get('hora_limite'))}"
    deadline = Table([
        [_paragraph("FECHA LÍMITE", label), _paragraph(deadline_text, subtitle), _paragraph("PLATAFORMA", label), _paragraph(tender.get("plataforma") or "No consta", body)]
    ], colWidths=[29 * mm, 55 * mm, 28 * mm, CONTENT_W - 112 * mm])
    deadline.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
        ("BOX", (0, 0), (-1, -1), 0.7, BRAND_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([deadline, Spacer(1, 7)])

    warnings = [item.message for item in issues if item.severity == "warning"]
    if warnings:
        alert_rows = [[_paragraph("AVISOS DE REVISIÓN", warning_style)]] + [[_paragraph(f"- {item}", small)] for item in warnings[:5]]
        alert = Table(alert_rows, colWidths=[CONTENT_W])
        alert.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ALERT),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E8CE89")),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend([alert, Spacer(1, 5)])

    def heading(text: str) -> None:
        story.extend([CondPageBreak(28 * mm), _paragraph(text, section)])

    def pairs_table(pairs: list[tuple[str, object]], *, widths: tuple[float, float] | None = None) -> bool:
        filtered = [(name, value) for name, value in pairs if clean_text(value)]
        if not filtered:
            return False
        rows = [
            [_paragraph(name, label), _url_paragraph(value, body) if name == "Enlace" else _paragraph(value, body)]
            for name, value in filtered
        ]
        table = LongTable(
            rows,
            colWidths=list(widths or (45 * mm, CONTENT_W - 45 * mm)),
            repeatRows=0,
            splitByRow=1,
            splitInRow=1,
        )
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([table, Spacer(1, 4)])
        return True

    def pair_section(title_text: str, pairs: list[tuple[str, object]]) -> bool:
        if not any(clean_text(value) for _name, value in pairs):
            return False
        heading(title_text)
        pairs_table(pairs)
        return True

    def append_graphics(section_number: int, title_text: str, heading_already: bool) -> bool:
        selected = [item for item in body_images if item.section_number == section_number]
        if not selected:
            return heading_already
        needs_heading = not heading_already
        for item in selected:
            graphic = PlatypusImage(str(item.path))
            if not graphic.imageWidth or not graphic.imageHeight:
                continue
            scale = min(CONTENT_W / graphic.imageWidth, (125 * mm) / graphic.imageHeight, 1.0)
            graphic.drawWidth = graphic.imageWidth * scale
            graphic.drawHeight = graphic.imageHeight * scale
            graphic.hAlign = "LEFT"
            required_height = graphic.drawHeight + (16 * mm if needs_heading else 8 * mm)
            story.append(CondPageBreak(min(required_height, 145 * mm)))
            if needs_heading:
                story.append(_paragraph(title_text, section))
                needs_heading = False
            story.extend([graphic, Spacer(1, 5)])
        return True

    section_shown = pair_section("1. Identificación", [
        ("Organismo", tender.get("organismo")),
        ("Tipo de contrato", tender.get("tipo_contrato")),
        ("Procedimiento", tender.get("procedimiento")),
        ("Regulación armonizada", tender.get("regulacion_armonizada")),
        ("Enlace", tender.get("enlace")),
    ])
    append_graphics(1, "1. Identificación", section_shown)

    section_shown = pair_section("2. Datos económicos y plazo", [
        ("Presupuesto base", _money(tender.get("presupuesto_base"))),
        ("Valor estimado", _money(tender.get("valor_estimado"))),
        ("Plazo", analysis.get("plazo")),
        ("Comentario de plazo", analysis.get("plazo_comentario")),
        ("Prórroga", analysis.get("prorroga")),
        ("Detalle de prórroga", analysis.get("prorroga_comentario")),
        ("Forma de adjudicación", analysis.get("forma_adjudicacion")),
    ])
    append_graphics(2, "2. Datos económicos y plazo", section_shown)

    lotes = _nonempty_rows(tender.get("lotes", []), ("numero", "titulo", "presupuesto", "valor_estimado", "comentarios"))
    section_shown = bool(lotes)
    if section_shown:
        rows = [[_paragraph(value, table_head) for value in ("N.º", "Lote", "Presupuesto", "Valor estimado", "Comentarios")]]
        for item in lotes:
            rows.append([
                _paragraph(item.get("numero"), table_body),
                _paragraph(item.get("titulo"), table_body),
                _paragraph(_money(item.get("presupuesto")), table_body),
                _paragraph(_money(item.get("valor_estimado")), table_body),
                _paragraph(item.get("comentarios"), table_body),
            ])
        table = LongTable(rows, repeatRows=1, splitByRow=1, splitInRow=0, colWidths=[12*mm, 42*mm, 27*mm, 27*mm, CONTENT_W-108*mm])
        table.setStyle(_data_table_style())
        available_height = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
        _width, table_height = table.wrap(CONTENT_W, available_height)
        lot_heading = _paragraph("3. Lotes", section)
        if table_height + 18 * mm <= available_height:
            story.append(KeepTogether([lot_heading, table, Spacer(1, 4)]))
        else:
            heading("3. Lotes")
            story.extend([table, Spacer(1, 4)])
    append_graphics(3, "3. Lotes", section_shown)

    section_shown = pair_section("4. Garantías y participación", [
        ("Garantía provisional", _joined(analysis.get("garantia_provisional"), analysis.get("garantia_provisional_comentario"))),
        ("Garantía definitiva", _joined(analysis.get("garantia_definitiva"), analysis.get("garantia_definitiva_comentario"))),
        ("Garantía complementaria", _joined(analysis.get("garantia_complementaria"), analysis.get("garantia_complementaria_comentario"))),
        ("Adscripción de medios", _joined(analysis.get("adscripcion_medios"), analysis.get("adscripcion_medios_comentario"))),
        ("Número de sobres", analysis.get("numero_sobres")),
        ("Fichas técnicas", _joined(analysis.get("fichas_tecnicas"), analysis.get("fichas_tecnicas_comentario"))),
        ("Memoria técnica", _joined(analysis.get("memoria_tecnica"), analysis.get("memoria_tecnica_comentario"))),
        ("Subcontratación", _joined(analysis.get("subcontratacion"), analysis.get("subcontratacion_comentario"))),
    ])
    append_graphics(4, "4. Garantías y participación", section_shown)

    section_shown = pair_section("5. Muestras", [
        ("Exigidas", analysis.get("muestras")),
        ("Momento", analysis.get("muestras_momento")),
        ("Detalle", analysis.get("muestras_comentario")),
    ])
    append_graphics(5, "5. Muestras", section_shown)

    def criteria_section(title_text: str, items: list[dict[str, Any]]) -> bool:
        records = _nonempty_rows(items, ("criterio", "descripcion", "puntos"))
        if not records:
            return False
        heading(title_text)
        headers = ["Criterio", "Descripción", "Puntos"]
        widths = [48 * mm, CONTENT_W - 73 * mm, 25 * mm]
        rows: list[list[Paragraph]] = [[_paragraph(value, table_head) for value in headers]]
        total = 0.0
        for item in records:
            values: list[object] = [item.get("criterio"), item.get("descripcion"), item.get("puntos")]
            rows.append([_paragraph(value, table_body) for value in values])
            try:
                total += float(str(item.get("puntos") or "0").replace(",", "."))
            except ValueError:
                pass
        total_cells: list[Paragraph] = [_paragraph("", table_body) for _ in headers]
        total_cells[-2] = _paragraph("Total", table_head)
        total_cells[-1] = _paragraph(f"{total:g}", table_head)
        rows.append(total_cells)
        table = LongTable(rows, repeatRows=1, splitByRow=1, splitInRow=0, colWidths=widths)
        table.setStyle(_data_table_style(total_row=True))
        story.extend([table, Spacer(1, 5)])
        return True

    section_shown = criteria_section("6. Criterios sujetos a juicio de valor", analysis.get("criterios_juicio", []))
    append_graphics(6, "6. Criterios sujetos a juicio de valor", section_shown)
    section_shown = criteria_section("7. Criterios evaluables mediante fórmula", analysis.get("criterios_formula", []))
    append_graphics(7, "7. Criterios evaluables mediante fórmula", section_shown)

    conditions = _nonempty_rows(analysis.get("condiciones_especiales", []), ("condicion", "detalle", "comentarios"))
    section_shown = bool(conditions)
    if section_shown:
        heading("8. Condiciones especiales de ejecución")
        for index, item in enumerate(conditions):
            row = Table(
                [[_paragraph(_joined_many(item.get("condicion"), item.get("detalle"), item.get("comentarios")), table_body)]],
                colWidths=[CONTENT_W],
            )
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white if index % 2 == 0 else LIGHT_GREY),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(row)
        story.append(Spacer(1, 5))
    append_graphics(8, "8. Condiciones especiales de ejecución", section_shown)

    observations = [clean_text(value) for value in analysis.get("observaciones", []) if clean_text(value)]
    section_shown = bool(observations)
    if section_shown:
        heading("9. Observaciones")
        for value in observations:
            row = Table([[_paragraph(value, body)]], colWidths=[CONTENT_W])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(row)
    append_graphics(9, "9. Observaciones", section_shown)
    section_shown = append_graphics(0, "10. Documentación gráfica", False)
    append_graphics(10, "10. Documentación gráfica", section_shown)

    if draft and errors:
        story.extend([PageBreak(), _paragraph("Errores pendientes antes de emitir el PDF final", section)])
        for issue in errors:
            story.append(_paragraph(f"- {issue.message}", warning_style))

    temp_pdf = target.with_suffix(".tmp.pdf")
    document.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
    if not temp_pdf.is_file() or temp_pdf.stat().st_size < 1000:
        raise RuntimeError("El motor PDF no produjo un documento válido.")
    reader = PdfReader(str(temp_pdf))
    page_count = len(reader.pages)
    from pypdf import PdfWriter

    writer = PdfWriter()
    for page_number, page in enumerate(reader.pages, start=1):
        packet = io.BytesIO()
        overlay = Canvas(packet, pagesize=A4)
        overlay.setFont("Helvetica", 8)
        overlay.setFillColor(MUTED)
        overlay.drawRightString(PAGE_W - MARGIN_X, 8 * mm, f"Página {page_number} de {page_count}")
        overlay.save()
        packet.seek(0)
        page.merge_page(PdfReader(packet).pages[0])
        writer.add_page(page)
    with target.open("wb") as output_stream:
        writer.write(output_stream)
    temp_pdf.unlink(missing_ok=True)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return PdfResult(
        path=target,
        page_count=page_count,
        sha256=digest,
        size_bytes=target.stat().st_size,
        warnings=tuple(item.message for item in issues if item.severity != "error"),
    )


def _joined(first: object, second: object) -> str:
    left = clean_text(first)
    right = clean_text(second)
    if left and right:
        return f"{left}. {right}"
    return left or right


def _joined_many(*values: object) -> str:
    return ". ".join(text for value in values if (text := clean_text(value)))


def _data_table_style(*, total_row: bool = False) -> TableStyle:
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN_DARK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2 if total_row else -1), [colors.white, LIGHT_GREY]),
    ]
    if total_row:
        commands.extend([
            ("BACKGROUND", (0, -1), (-1, -1), BRAND_GREEN_DARK),
            ("SPAN", (0, -1), (-3, -1)),
        ])
    return TableStyle(commands)


__all__ = ("PdfResult", "render_tender_pdf")
