"""Apply the two OOXML details that localized Excel COM cannot express reliably."""

from __future__ import annotations

import argparse
import os
import posixpath
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}


def ficha_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels.findall("p:Relationship", NS)}
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        if sheet.attrib.get("name") == "Ficha":
            rel_id = sheet.attrib[f"{{{REL_NS}}}id"]
            return posixpath.normpath(posixpath.join("xl", targets[rel_id]))
    raise RuntimeError("No se encuentra la hoja Ficha.")


def patch_workbook(path: Path) -> None:
    handle, temp_name = tempfile.mkstemp(prefix="ficha_v3_", suffix=".xlsm", dir=path.parent)
    os.close(handle)
    temp_path = Path(temp_name)
    with zipfile.ZipFile(path, "r") as source:
        sheet_path = ficha_sheet_path(source)
        sheet_bytes = source.read(sheet_path)
        old = "Página &amp;P de &amp;F".encode("utf-8")
        new = "Página &amp;P de &amp;N".encode("utf-8")
        if old in sheet_bytes:
            sheet_bytes = sheet_bytes.replace(old, new, 1)
        elif new not in sheet_bytes:
            raise RuntimeError("El pie de página nativo no tiene el formato esperado.")

        with zipfile.ZipFile(temp_path, "w") as target:
            for info in source.infolist():
                payload = sheet_bytes if info.filename == sheet_path else source.read(info.filename)
                target.writestr(info, payload)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    patch_workbook(args.workbook.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
