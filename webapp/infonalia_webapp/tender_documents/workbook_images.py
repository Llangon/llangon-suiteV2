"""Read pictures placed on the Ficha worksheet from an XLSM package.

Excel stores floating pictures in DrawingML and pictures placed in cells as
rich values.  The PDF bridge reads both representations from a temporary
``SaveCopyAs`` snapshot, so unsaved workbook images are included without
modifying the user's open file.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XDR_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
RICH_NS = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"
RICH_REL_NS = "http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel"

MAX_IMAGES = 50
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


@dataclass(frozen=True, slots=True)
class WorkbookImage:
    path: Path
    kind: str
    cell: str
    row: int
    column: int
    name: str
    section_number: int


@dataclass(frozen=True, slots=True)
class _SectionRange:
    min_row: int
    min_column: int
    max_row: int
    max_column: int
    section_number: int

    def contains(self, row: int, column: int) -> bool:
        return self.min_row <= row <= self.max_row and self.min_column <= column <= self.max_column


def _xml(package: zipfile.ZipFile, name: str) -> ET.Element:
    try:
        info = package.getinfo(name)
    except KeyError as exc:
        raise ValueError(f"El libro no contiene la pieza requerida: {name}.") from exc
    if info.file_size > 5 * 1024 * 1024:
        raise ValueError("Una pieza XML del libro supera el tamaño admitido.")
    return ET.fromstring(package.read(info))


def _optional_xml(package: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return _xml(package, name)
    except (KeyError, ValueError):
        return None


def _rels_path(source_part: str) -> str:
    source = PurePosixPath(source_part)
    return str(source.parent / "_rels" / f"{source.name}.rels")


def _resolve_part(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    source_dir = str(PurePosixPath(source_part).parent)
    return posixpath.normpath(posixpath.join(source_dir, target)).lstrip("/")


def _relationships(package: zipfile.ZipFile, source_part: str) -> dict[str, tuple[str, str]]:
    rels = _optional_xml(package, _rels_path(source_part))
    if rels is None:
        return {}
    result: dict[str, tuple[str, str]] = {}
    for relation in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
        relation_id = relation.get("Id", "")
        target = relation.get("Target", "")
        if relation_id and target and relation.get("TargetMode") != "External":
            result[relation_id] = (_resolve_part(source_part, target), relation.get("Type", ""))
    return result


def _ficha_sheet_part(package: zipfile.ZipFile) -> str:
    workbook_part = "xl/workbook.xml"
    workbook = _xml(package, workbook_part)
    relationships = _relationships(package, workbook_part)
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        if sheet.get("name", "").casefold() != "ficha":
            continue
        relation_id = sheet.get(f"{{{DOC_REL_NS}}}id", "")
        if relation_id in relationships:
            return relationships[relation_id][0]
    raise ValueError("El libro no contiene la hoja Ficha.")


def _cell_coordinates(reference: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Za-z]+)([1-9][0-9]*)", reference)
    if not match:
        return 0, 0
    column = 0
    for character in match.group(1).upper():
        column = column * 26 + ord(character) - 64
    return int(match.group(2)), column


def _cell_reference(row: int, column: int) -> str:
    letters = ""
    value = column
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row}" if row > 0 and letters else ""


def _range_coordinates(reference: str) -> tuple[int, int, int, int] | None:
    parts = reference.replace("$", "").split(":", 1)
    first_row, first_column = _cell_coordinates(parts[0])
    last_row, last_column = _cell_coordinates(parts[-1])
    if not first_row or not first_column or not last_row or not last_column:
        return None
    return (
        min(first_row, last_row),
        min(first_column, last_column),
        max(first_row, last_row),
        max(first_column, last_column),
    )


def _table_section_ranges(package: zipfile.ZipFile, sheet_part: str) -> list[_SectionRange]:
    section_by_table = {
        "tbllotes": 3,
        "tblcriteriosjuicio": 6,
        "tblcriteriosformula": 7,
        "tblcondicionesespeciales": 8,
    }
    sheet = _xml(package, sheet_part)
    relationships = _relationships(package, sheet_part)
    result: list[_SectionRange] = []
    for table_part in sheet.findall(f".//{{{MAIN_NS}}}tablePart"):
        relation_id = table_part.get(f"{{{DOC_REL_NS}}}id", "")
        target = relationships.get(relation_id, ("", ""))[0]
        if not target:
            continue
        table = _xml(package, target)
        table_name = table.get("name", table.get("displayName", "")).casefold()
        section_number = section_by_table.get(table_name)
        coordinates = _range_coordinates(table.get("ref", ""))
        if section_number is not None and coordinates is not None:
            result.append(_SectionRange(*coordinates, section_number))
    return result


def _defined_name_section(name: str) -> int | None:
    normalized = name.casefold()
    if normalized.startswith("llg_tender_") or normalized == "llg_source_place":
        return 1
    if not normalized.startswith("llg_analysis_"):
        return None
    field = normalized.removeprefix("llg_analysis_")
    if field in {"plazo", "plazo_comentario", "prorroga", "prorroga_comentario", "forma_adjudicacion"}:
        return 2
    if field.startswith(("garantia_", "adscripcion_", "fichas_", "memoria_", "subcontratacion")) or field == "numero_sobres":
        return 4
    if field.startswith("muestras"):
        return 5
    if field == "observaciones":
        return 9
    return None


def _defined_name_section_ranges(package: zipfile.ZipFile) -> list[_SectionRange]:
    workbook = _xml(package, "xl/workbook.xml")
    result: list[_SectionRange] = []
    for defined_name in workbook.findall(f".//{{{MAIN_NS}}}definedName"):
        section_number = _defined_name_section(defined_name.get("name", ""))
        formula = (defined_name.text or "").strip()
        if section_number is None or "!" not in formula:
            continue
        sheet_name, reference = formula.split("!", 1)
        if sheet_name.strip("'").casefold() != "ficha":
            continue
        coordinates = _range_coordinates(reference)
        if coordinates is not None:
            result.append(_SectionRange(*coordinates, section_number))
    return result


def _normalized_heading(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(without_accents.casefold().split())


def _shared_strings(package: zipfile.ZipFile) -> list[str]:
    root = _optional_xml(package, "xl/sharedStrings.xml")
    if root is None:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
        for item in root.findall(f"{{{MAIN_NS}}}si")
    ]


def _sheet_section_ranges(package: zipfile.ZipFile, sheet_part: str) -> list[_SectionRange]:
    section_by_heading = {
        "identificacion de la licitacion": 1,
        "datos economicos y plazos": 2,
        "lotes (opcional)": 3,
        "garantias y participacion": 4,
        "muestras": 5,
        "criterios sujetos a juicio de valor": 6,
        "criterios evaluables mediante formula": 7,
        "condiciones especiales de ejecucion": 8,
        "observaciones": 9,
    }
    strings = _shared_strings(package)
    sheet = _xml(package, sheet_part)
    section_rows: dict[int, int] = {}
    maximum_row = 1
    for cell in sheet.findall(f".//{{{MAIN_NS}}}c"):
        row, _column = _cell_coordinates(cell.get("r", ""))
        maximum_row = max(maximum_row, row)
        cell_type = cell.get("t", "")
        value = ""
        if cell_type == "s":
            raw_index = cell.findtext(f"{{{MAIN_NS}}}v", "")
            if raw_index.isdigit() and int(raw_index) < len(strings):
                value = strings[int(raw_index)]
        elif cell_type == "inlineStr":
            value = "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
        else:
            value = cell.findtext(f"{{{MAIN_NS}}}v", "")
        section_number = section_by_heading.get(_normalized_heading(value))
        if section_number is not None:
            section_rows[row] = section_number
    starts = sorted(section_rows.items())
    result: list[_SectionRange] = []
    for index, (start_row, section_number) in enumerate(starts):
        end_row = starts[index + 1][0] - 1 if index + 1 < len(starts) else maximum_row
        result.append(_SectionRange(start_row, 1, end_row, 16384, section_number))
    return result


def _section_for_position(row: int, column: int, section_ranges: list[_SectionRange]) -> int:
    for section_range in section_ranges:
        if section_range.contains(row, column):
            return section_range.section_number

    table_rows: dict[int, tuple[int, int]] = {}
    for section_number in (3, 6, 7, 8):
        matches = [item for item in section_ranges if item.section_number == section_number]
        if matches:
            table_rows[section_number] = (
                min(item.min_row for item in matches),
                max(item.max_row for item in matches),
            )
    if 8 in table_rows:
        condition_start, condition_end = table_rows[8]
        if row > condition_end:
            return 9
        if row >= condition_start - 1:
            return 8
    if 7 in table_rows and row >= table_rows[7][0] - 1:
        return 7
    if 6 in table_rows and row >= table_rows[6][0] - 1:
        return 6

    if row <= 10:
        return 0
    if row <= 21:
        return 1
    if row <= 29:
        return 2
    if row <= 36:
        return 3
    if row <= 46:
        return 4
    if row <= 50:
        return 5
    if row <= 65:
        return 6
    if row <= 80:
        return 7
    if row <= 90:
        return 8
    if row <= 119:
        return 9
    return 10


def _floating_records(package: zipfile.ZipFile, sheet_part: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    sheet_relationships = _relationships(package, sheet_part)
    drawing_parts = [part for part, relation_type in sheet_relationships.values() if relation_type.endswith("/drawing")]
    for drawing_part in drawing_parts:
        drawing = _xml(package, drawing_part)
        drawing_relationships = _relationships(package, drawing_part)
        for anchor in list(drawing):
            picture = anchor.find(f"{{{XDR_NS}}}pic")
            if picture is None:
                continue
            blip = picture.find(f".//{{{DRAWING_NS}}}blip")
            relation_id = blip.get(f"{{{DOC_REL_NS}}}embed", "") if blip is not None else ""
            media = drawing_relationships.get(relation_id, ("", ""))[0]
            if not media:
                continue
            marker = anchor.find(f"{{{XDR_NS}}}from")
            zero_col = int(marker.findtext(f"{{{XDR_NS}}}col", "0")) if marker is not None else 0
            zero_row = int(marker.findtext(f"{{{XDR_NS}}}row", "0")) if marker is not None else 0
            properties = picture.find(f"{{{XDR_NS}}}nvPicPr/{{{XDR_NS}}}cNvPr")
            name = properties.get("name", "Imagen superpuesta") if properties is not None else "Imagen superpuesta"
            row, column = zero_row + 1, zero_col + 1
            records.append(
                {
                    "media": media,
                    "kind": "floating",
                    "cell": _cell_reference(row, column),
                    "row": row,
                    "column": column,
                    "name": name,
                }
            )
    return records


def _rich_value_image_ids(package: zipfile.ZipFile) -> dict[int, int]:
    structures = _optional_xml(package, "xl/richData/rdrichvaluestructure.xml")
    values = _optional_xml(package, "xl/richData/rdrichvalue.xml")
    if structures is None or values is None:
        return {}
    structure_keys: list[list[str]] = []
    for structure in structures.findall(f"{{{RICH_NS}}}s"):
        structure_keys.append([key.get("n", "") for key in structure.findall(f"{{{RICH_NS}}}k")])
    result: dict[int, int] = {}
    for index, rich_value in enumerate(values.findall(f"{{{RICH_NS}}}rv")):
        structure_index = int(rich_value.get("s", "-1"))
        if not 0 <= structure_index < len(structure_keys):
            continue
        keys = structure_keys[structure_index]
        try:
            image_position = keys.index("_rvRel:LocalImageIdentifier")
        except ValueError:
            continue
        raw_values = rich_value.findall(f"{{{RICH_NS}}}v")
        if image_position >= len(raw_values) or raw_values[image_position].text is None:
            continue
        result[index] = int(raw_values[image_position].text)
    return result


def _metadata_rich_value_ids(package: zipfile.ZipFile) -> dict[int, int]:
    metadata = _optional_xml(package, "xl/metadata.xml")
    if metadata is None:
        return {}
    value_metadata = metadata.find(f"{{{MAIN_NS}}}valueMetadata")
    if value_metadata is None:
        return {}
    result: dict[int, int] = {}
    for metadata_index, block in enumerate(value_metadata.findall(f"{{{MAIN_NS}}}bk"), start=1):
        record = block.find(f"{{{MAIN_NS}}}rc")
        if record is not None and record.get("v", "").isdigit():
            result[metadata_index] = int(record.get("v", "0"))
    return result


def _rich_media_parts(package: zipfile.ZipFile) -> list[str]:
    relation_part = "xl/richData/richValueRel.xml"
    rich_relations = _optional_xml(package, relation_part)
    if rich_relations is None:
        return []
    relationships = _relationships(package, relation_part)
    result: list[str] = []
    for relation in rich_relations.findall(f"{{{RICH_REL_NS}}}rel"):
        relation_id = relation.get(f"{{{DOC_REL_NS}}}id", "")
        result.append(relationships.get(relation_id, ("", ""))[0])
    return result


def _in_cell_records(package: zipfile.ZipFile, sheet_part: str) -> list[dict[str, object]]:
    sheet = _xml(package, sheet_part)
    metadata_ids = _metadata_rich_value_ids(package)
    rich_image_ids = _rich_value_image_ids(package)
    rich_media = _rich_media_parts(package)
    records: list[dict[str, object]] = []
    for cell in sheet.findall(f".//{{{MAIN_NS}}}c"):
        metadata_index = cell.get("vm", "")
        if not metadata_index.isdigit():
            continue
        rich_value_index = metadata_ids.get(int(metadata_index))
        image_index = rich_image_ids.get(rich_value_index) if rich_value_index is not None else None
        if image_index is None or not 0 <= image_index < len(rich_media) or not rich_media[image_index]:
            continue
        reference = cell.get("r", "")
        row, column = _cell_coordinates(reference)
        records.append(
            {
                "media": rich_media[image_index],
                "kind": "in_cell",
                "cell": reference,
                "row": row,
                "column": column,
                "name": "Imagen en celda",
            }
        )
    return records


def extract_ficha_images(workbook_path: str | Path, output_dir: str | Path) -> tuple[WorkbookImage, ...]:
    """Extract supported images from the Ficha sheet into ``output_dir``."""

    workbook = Path(workbook_path)
    if not workbook.is_file():
        raise FileNotFoundError(f"No se encuentra la copia temporal del libro: {workbook.name}")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[WorkbookImage] = []
    total_bytes = 0
    try:
        with zipfile.ZipFile(workbook) as package:
            sheet_part = _ficha_sheet_part(package)
            section_ranges = (
                _table_section_ranges(package, sheet_part)
                + _sheet_section_ranges(package, sheet_part)
                + _defined_name_section_ranges(package)
            )
            records = _floating_records(package, sheet_part) + _in_cell_records(package, sheet_part)
            records.sort(key=lambda item: (int(item["row"]), int(item["column"]), str(item["kind"])))
            if len(records) > MAX_IMAGES:
                raise ValueError(f"La ficha contiene más de {MAX_IMAGES} imágenes; reduzca su número antes de generar el PDF.")
            for index, record in enumerate(records, start=1):
                media_part = str(record["media"])
                suffix = PurePosixPath(media_part).suffix.lower()
                if suffix not in ALLOWED_IMAGE_SUFFIXES:
                    continue
                try:
                    info = package.getinfo(media_part)
                except KeyError:
                    continue
                if info.file_size > MAX_IMAGE_BYTES:
                    raise ValueError(f"La imagen situada en {record['cell']} supera 10 MB.")
                total_bytes += info.file_size
                if total_bytes > MAX_TOTAL_IMAGE_BYTES:
                    raise ValueError("Las imágenes de la ficha superan 50 MB en conjunto.")
                target = destination / f"{index:02d}_{record['kind']}{suffix}"
                target.write_bytes(package.read(info))
                row = int(record["row"])
                extracted.append(
                    WorkbookImage(
                        path=target,
                        kind=str(record["kind"]),
                        cell=str(record["cell"]),
                        row=row,
                        column=int(record["column"]),
                        name=str(record["name"]),
                        section_number=_section_for_position(row, int(record["column"]), section_ranges),
                    )
                )
    except zipfile.BadZipFile as exc:
        raise ValueError("La copia temporal del libro no es un XLSM válido.") from exc
    return tuple(extracted)


__all__ = ("WorkbookImage", "extract_ficha_images")
