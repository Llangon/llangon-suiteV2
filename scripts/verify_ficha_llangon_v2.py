"""Static acceptance checks for the generated Ficha Llangon v2 workbook.

This complements (but does not replace) the real Excel/COM acceptance test.
It reads the OOXML package directly and never edits the workbook.
"""

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

EXPECTED_SHEETS = {"Ficha", "Informe_PDF", "_Listas", "_Llangon"}
VERY_HIDDEN_SHEETS = {"_Listas", "_Llangon"}
EXPECTED_TABLES = {
    "tblClientes",
    "tblFestivos",
    "tblFieldRegistry",
}
EXPECTED_ACTIONS = {
    "UpdateClients",
    "ImportPlace",
    "ReviewFichaAction",
    "PreparePDF",
    "OpenLastPdfOrReport",
    "VolverAFicha",
    "ExportFallbackExcel",
}
FORBIDDEN_PACKAGE_PREFIXES = (
    "xl/externalLinks/",
    "xl/model/",
    "xl/queries/",
)
FORBIDDEN_TEXT_MARKERS = ("#REF!", "_xlfn.", "DataMashup")


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
    rel_targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in rels.findall("p:Relationship", NS)
    }
    paths: dict[str, str] = {}
    states: dict[str, str] = {}
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[f"{{{REL_NS}}}id"]
        target = rel_targets[rel_id]
        paths[name] = posixpath.normpath(posixpath.join("xl", target))
        states[name] = sheet.attrib.get("state", "visible")
    return paths, states


def _defined_names(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = _xml(archive, "xl/workbook.xml")
    return {
        item.attrib["name"]: (item.text or "")
        for item in workbook.findall("m:definedNames/m:definedName", NS)
    }


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _xml(archive, "xl/sharedStrings.xml")
    return ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", NS)).strip()
    value = cell.findtext("m:v", default="", namespaces=NS).strip()
    if cell_type == "s" and value.isdigit():
        index = int(value)
        return shared[index].strip() if index < len(shared) else value
    return value


def _client_labels_use_legal_names(archive: zipfile.ZipFile, listas_path: str) -> bool:
    shared = _shared_strings(archive)
    root = _xml(archive, listas_path)
    rows: dict[int, dict[str, str]] = {}
    for cell in root.findall(".//m:sheetData/m:row/m:c", NS):
        reference = cell.attrib.get("r", "")
        match = re.fullmatch(r"([A-Z]+)(\d+)", reference)
        if not match:
            continue
        column, row_text = match.groups()
        row = int(row_text)
        if column in {"G", "H", "I", "J", "K", "L", "M"} and 2 <= row <= 501:
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
        names = set(archive.namelist())
        _require("xl/vbaProject.bin" in names, "El XLSM no contiene proyecto VBA.")
        _require(archive.getinfo("xl/vbaProject.bin").file_size > 1000, "El proyecto VBA está vacío o dañado.")
        content_types = archive.read("[Content_Types].xml").decode("utf-8", errors="replace")
        _require("macroEnabled.main+xml" in content_types, "El tipo OOXML no está marcado como libro con macros.")

        sheet_paths, sheet_states = _sheet_paths(archive)
        _require(set(sheet_paths) == EXPECTED_SHEETS, f"Hojas inesperadas: {sorted(sheet_paths)}")
        for sheet_name in VERY_HIDDEN_SHEETS:
            _require(sheet_states[sheet_name] == "veryHidden", f"{sheet_name} no está VeryHidden.")
        informe = _xml(archive, sheet_paths["Informe_PDF"])
        _require(informe.find("m:sheetProtection", NS) is not None, "Informe_PDF no está protegido.")

        defined_names = _defined_names(archive)
        layout = json.loads((repo_root / "webapp/infonalia_webapp/tender_documents/workbook_layout.json").read_text(encoding="utf-8"))
        required_names = set(layout["names"]) | {"llg_client_choices"}
        missing_names = sorted(required_names - set(defined_names))
        _require(not missing_names, f"Faltan nombres estables: {missing_names}")
        _require(not any("#REF!" in value.upper() for value in defined_names.values()), "Hay nombres con referencias rotas.")

        table_names: set[str] = set()
        for name in names:
            if name.startswith("xl/tables/") and name.endswith(".xml"):
                table_names.add(_xml(archive, name).attrib.get("name", ""))
        _require(EXPECTED_TABLES <= table_names, f"Faltan tablas: {sorted(EXPECTED_TABLES - table_names)}")
        _require(_client_labels_use_legal_names(archive, sheet_paths["_Listas"]), "La lista de clientes no utiliza la razón social completa.")
        forbidden_user_tables = {"tblLotes", "tblCriteriosJuicio", "tblCriteriosFormula", "tblCondicionesEspeciales"}
        _require(not (forbidden_user_tables & table_names), "Las secciones simplificadas no deben volver a convertirse en tablas.")

        for prefix in FORBIDDEN_PACKAGE_PREFIXES:
            _require(not any(name.startswith(prefix) for name in names), f"Se encontró contenido heredado: {prefix}")
        _require("xl/connections.xml" not in names, "El libro contiene conexiones externas.")
        textual_parts = []
        for name in names:
            if name.endswith((".xml", ".rels")):
                textual_parts.append(archive.read(name).decode("utf-8", errors="replace"))
        package_text = "\n".join(textual_parts)
        for marker in FORBIDDEN_TEXT_MARKERS:
            _require(marker.casefold() not in package_text.casefold(), f"Se encontró el marcador heredado {marker}.")

        drawing_text = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
            if name.startswith("xl/drawings/") and name.endswith(".xml")
        )
        missing_actions = sorted(action for action in EXPECTED_ACTIONS if action not in drawing_text)
        _require(not missing_actions, f"Faltan acciones de botones: {missing_actions}")

    macro_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((repo_root / "macros/ficha_llangon_v2").glob("*.bas"))
    )
    for event_name in ("Workbook_Open", "Auto_Open", "Worksheet_Activate", "Workbook_Activate"):
        _require(event_name.casefold() not in macro_sources.casefold(), f"Existe un evento automático no permitido: {event_name}")
    _require("mode=ro" in (repo_root / "webapp/infonalia_webapp/tender_documents/client_reader.py").read_text(encoding="utf-8"), "Falta mode=ro en el lector SQLite.")

    return {
        "workbook": str(workbook_path),
        "size_bytes": workbook_path.stat().st_size,
        "sheets": sorted(EXPECTED_SHEETS),
        "very_hidden": sorted(VERY_HIDDEN_SHEETS),
        "tables": sorted(EXPECTED_TABLES),
        "stable_names": len(required_names),
        "buttons": sorted(EXPECTED_ACTIONS),
        "client_labels_use_legal_names": True,
        "automatic_client_refresh": False,
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
