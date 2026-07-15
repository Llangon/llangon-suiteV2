"""Small, named OOXML operations used by the document generators."""

from __future__ import annotations

from collections.abc import Sequence

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def set_repeat_table_header(row: object) -> None:
    properties = row._tr.get_or_add_trPr()
    element = properties.find(qn("w:tblHeader"))
    if element is None:
        element = OxmlElement("w:tblHeader")
        properties.append(element)
    element.set(qn("w:val"), "true")


def set_row_cant_split(row: object) -> None:
    properties = row._tr.get_or_add_trPr()
    element = properties.find(qn("w:cantSplit"))
    if element is None:
        element = OxmlElement("w:cantSplit")
        properties.append(element)


def set_table_geometry(
    table: object,
    widths_dxa: Sequence[int],
    *,
    indent_dxa: int = 0,
) -> None:
    if not widths_dxa or len(widths_dxa) != len(table.columns):
        raise ValueError("La geometría debe definir un ancho por columna.")
    total = sum(int(width) for width in widths_dxa)
    properties = table._tbl.tblPr
    _set_width_element(properties, "w:tblW", total)
    _set_width_element(properties, "w:tblInd", int(indent_dxa))
    layout = properties.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        properties.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(int(width)))
        grid.append(column)

    for row in table.rows:
        for index, cell in enumerate(row.cells):
            width = int(widths_dxa[index])
            cell_properties = cell._tc.get_or_add_tcPr()
            _set_width_element(cell_properties, "w:tcW", width)


def set_cell_margins(
    cell: object,
    *,
    top: int = 70,
    start: int = 90,
    bottom: int = 70,
    end: int = 90,
) -> None:
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.find(qn("w:tcMar"))
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            margins.append(node)
        node.set(qn("w:w"), str(int(value)))
        node.set(qn("w:type"), "dxa")


def shade_cell(cell: object, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_paragraph_keep_with_next(paragraph: object, enabled: bool = True) -> None:
    paragraph.paragraph_format.keep_with_next = enabled


def _set_width_element(parent: object, tag: str, width: int) -> None:
    element = parent.find(qn(tag))
    if element is None:
        element = OxmlElement(tag)
        parent.append(element)
    element.set(qn("w:w"), str(width))
    element.set(qn("w:type"), "dxa")


__all__ = (
    "set_cell_margins",
    "set_paragraph_keep_with_next",
    "set_repeat_table_header",
    "set_row_cant_split",
    "set_table_geometry",
    "shade_cell",
)
