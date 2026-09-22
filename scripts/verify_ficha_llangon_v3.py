"""Static acceptance checks for the Excel-native Ficha Llangon 3 workbook."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}

EXPECTED_SHEETS = {"Ficha", "_Listas", "_Llangon"}
VERY_HIDDEN_SHEETS = {"_Listas", "_Llangon"}
EXPECTED_TABLES = {"tblClientes", "tblFestivos"}
EXPECTED_ACTIONS = {
    "UpdateClients",
    "ImportPlace",
    "ReviewFichaAction",
}
FORBIDDEN_ACTIONS = {
    "PreparePDF",
    "OpenLastPdfOrReport",
    "ExportFallbackExcel",
    "RefreshInformePDF",
}
FORBIDDEN_PACKAGE_PREFIXES = ("xl/externalLinks/", "xl/model/", "xl/queries/")
FORBIDDEN_TEXT_MARKERS = ("#REF!", "_xlfn.", "DataMashup", "Informe_PDF")


class VerificationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError as exc:
        raise VerificationError(f"Falta la parte OOXML {name}.") from exc


def _sheet_paths(archive: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    workbook = _xml(archive, "xl/workbook.xml")
    rels = _xml(archive, "xl/_rels/workbook.xml.rels")
    rel_targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels.findall("p:Relationship", NS)}
    paths: dict[str, str] = {}
    states: dict[str, str] = {}
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        name = sheet.attrib["name"]
        target = rel_targets[sheet.attrib[f"{{{REL_NS}}}id"]]
        paths[name] = posixpath.normpath(posixpath.join("xl", target))
        states[name] = sheet.attrib.get("state", "visible")
    return paths, states


def _defined_names(archive: zipfile.ZipFile) -> dict[str, str]:
    root = _xml(archive, "xl/workbook.xml")
    return {
        item.attrib["name"]: item.text or ""
        for item in root.findall("m:definedNames/m:definedName", NS)
    }


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _xml(archive, "xl/sharedStrings.xml")
    return ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", NS)).strip()
    value = cell.findtext("m:v", default="", namespaces=NS).strip()
    if cell.attrib.get("t") == "s" and value.isdigit():
        index = int(value)
        return shared[index].strip() if index < len(shared) else value
    return value


def _client_labels_use_legal_names(archive: zipfile.ZipFile, listas_path: str) -> bool:
    shared = _shared_strings(archive)
    root = _xml(archive, listas_path)
    rows: dict[int, dict[str, str]] = {}
    for cell in root.findall(".//m:sheetData/m:row/m:c", NS):
        match = re.fullmatch(r"([A-Z]+)(\d+)", cell.attrib.get("r", ""))
        if not match:
            continue
        column, row_text = match.groups()
        row = int(row_text)
        if column in {"H", "I", "J"} and 2 <= row <= 501:
            rows.setdefault(row, {})[column] = _cell_text(cell, shared)
    for values in rows.values():
        reason = values.get("J", "").strip()
        label = values.get("H", "").strip()
        display = values.get("I", "").strip()
        if reason and (not label.startswith(reason) or display != reason):
            return False
    return True


def verify(workbook_path: Path, repo_root: Path) -> dict[str, object]:
    _require(workbook_path.is_file(), f"No existe el libro: {workbook_path}")
    _require(workbook_path.suffix.lower() == ".xlsm", "La plantilla final debe tener extensión .xlsm.")
    with zipfile.ZipFile(workbook_path) as archive:
        package_names = set(archive.namelist())
        _require("xl/vbaProject.bin" in package_names, "El XLSM no contiene proyecto VBA.")
        _require(archive.getinfo("xl/vbaProject.bin").file_size > 1000, "El proyecto VBA está vacío o dañado.")
        _require("macroEnabled.main+xml" in archive.read("[Content_Types].xml").decode("utf-8", errors="replace"), "El libro no está marcado como XLSM.")

        sheet_paths, sheet_states = _sheet_paths(archive)
        _require(set(sheet_paths) == EXPECTED_SHEETS, f"Hojas inesperadas: {sorted(sheet_paths)}")
        for name in VERY_HIDDEN_SHEETS:
            _require(sheet_states[name] == "veryHidden", f"{name} no está VeryHidden.")

        defined = _defined_names(archive)
        required_names = {
            "llg_recipient_client_display",
            "llg_document_confidentiality_notice",
            "llg_ui_cache_status",
            "llg_ui_review_status",
            "llg_control_workbook_schema",
            "llg_native_print_area",
            "llg_print_end",
            "llg_client_choices",
            "_xlnm.Print_Area",
            "_xlnm.Print_Titles",
        }
        missing = sorted(required_names - set(defined))
        _require(not missing, f"Faltan nombres nativos: {missing}")
        _require("llg_control_payload_version" not in defined, "Permanece el nombre de versión de payload PDF.")
        _require("llg_last_pdf_path" not in defined, "Permanece el nombre del último PDF generado.")
        _require(not any("#REF!" in value.upper() for value in defined.values()), "Hay nombres con referencias rotas.")
        _require("$1:$5" in defined["_xlnm.Print_Titles"], "Las filas 1:5 no se repiten en cada página.")
        _require("$B$1:$H$101" in defined["_xlnm.Print_Area"], "El área de impresión no es B1:H101.")

        table_names = {
            _xml(archive, name).attrib.get("name", "")
            for name in package_names
            if name.startswith("xl/tables/") and name.endswith(".xml")
        }
        _require(table_names == EXPECTED_TABLES, f"Tablas inesperadas: {sorted(table_names)}")
        _require(_client_labels_use_legal_names(archive, sheet_paths["_Listas"]), "La lista de clientes no utiliza la razón social completa.")

        ficha = _xml(archive, sheet_paths["Ficha"])
        page_setup = ficha.find("m:pageSetup", NS)
        _require(page_setup is not None, "Falta la configuración de página.")
        _require(page_setup.attrib.get("orientation") == "portrait", "La orientación no es vertical.")
        sheet_pr = ficha.find("m:sheetPr/m:pageSetUpPr", NS)
        _require(sheet_pr is not None and sheet_pr.attrib.get("fitToPage") == "1", "La ficha no usa ajuste a página.")
        _require(page_setup.attrib.get("fitToWidth", "1") == "1", "La ficha no está ajustada a una página de ancho.")
        header_footer = ficha.find("m:headerFooter", NS)
        _require(header_footer is not None, "Faltan encabezados y pies nativos.")
        footer_text = "".join(header_footer.itertext())
        _require("&P" in footer_text and "&N" in footer_text, "Falta la numeración Página X de Y.")
        formula_by_cell = {
            cell.attrib.get("r", ""): cell.findtext("m:f", default="", namespaces=NS)
            for cell in ficha.findall(".//m:sheetData/m:row/m:c", NS)
        }
        _require("$L$5" in formula_by_cell.get("D4", ""), "El encabezado no enlaza con el cliente editable.")
        _require("SUBSTITUTE" in formula_by_cell.get("B5", "").upper(), "El aviso no sustituye dinámicamente el destinatario.")
        _require("$L$8" in formula_by_cell.get("B5", ""), "El aviso no enlaza con el texto editable.")

        for prefix in FORBIDDEN_PACKAGE_PREFIXES:
            _require(not any(name.startswith(prefix) for name in package_names), f"Se encontró contenido heredado: {prefix}")
        _require("xl/connections.xml" not in package_names, "El libro contiene conexiones externas.")
        package_text = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in package_names
            if name.endswith((".xml", ".rels"))
        )
        for marker in FORBIDDEN_TEXT_MARKERS:
            _require(marker.casefold() not in package_text.casefold(), f"Se encontró el marcador heredado {marker}.")

        drawing_text = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in package_names
            if name.startswith("xl/drawings/") and name.endswith(".xml")
        )
        missing_actions = sorted(action for action in EXPECTED_ACTIONS if action not in drawing_text)
        _require(not missing_actions, f"Faltan botones: {missing_actions}")
        present_forbidden = sorted(action for action in FORBIDDEN_ACTIONS if action in drawing_text)
        _require(not present_forbidden, f"Quedan botones PDF: {present_forbidden}")

    macro_sources = "\n".join(
        (repo_root / "macros/ficha_llangon_v2" / name).read_text(encoding="utf-8")
        for name in ("modLlangonCore.bas", "modLlangonBridge.bas", "modLlangonPlace.bas")
    )
    for event_name in ("Workbook_Open", "Auto_Open", "Worksheet_Activate", "Workbook_Activate", "Workbook_BeforePrint"):
        _require(event_name.casefold() not in macro_sources.casefold(), f"Existe un evento automático no permitido: {event_name}")

    return {
        "workbook": str(workbook_path),
        "size_bytes": workbook_path.stat().st_size,
        "sheets": sorted(EXPECTED_SHEETS),
        "very_hidden": sorted(VERY_HIDDEN_SHEETS),
        "tables": sorted(EXPECTED_TABLES),
        "buttons": sorted(EXPECTED_ACTIONS),
        "print_area": "Ficha!B1:H101",
        "repeated_rows": "1:5",
        "client_labels_use_legal_names": True,
        "pdf_macro_dependency": False,
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = verify(args.workbook.resolve(), args.repo_root.resolve())
    except (OSError, ValueError, zipfile.BadZipFile, VerificationError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
