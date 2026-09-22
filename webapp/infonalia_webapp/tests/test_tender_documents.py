from __future__ import annotations

import csv
import json
import sqlite3
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from webapp.infonalia_webapp.licitacion_capture import CaptureError
from webapp.infonalia_webapp.tender_documents.bridge import (
    _unique_pdf_path,
    _read_source_file,
    build_parser,
    export_clients,
    export_place,
)
from webapp.infonalia_webapp.tender_documents.client_reader import ClientReadError, open_read_only, read_clients
from webapp.infonalia_webapp.tender_documents.place_adapter import payload_from_place_source, payload_from_place_xml
from webapp.infonalia_webapp.tender_documents.pdf_renderer import render_tender_pdf
from webapp.infonalia_webapp.tender_documents.sample_payloads import extreme_payload, normal_payload, short_payload
from webapp.infonalia_webapp.tender_documents.validation import validate_payload
from webapp.infonalia_webapp.tender_documents.workbook_images import extract_ficha_images


_png_stream = BytesIO()
Image.new("RGB", (8, 8), (58, 174, 42)).save(_png_stream, format="PNG")
_ONE_PIXEL_PNG = _png_stream.getvalue()


def _workbook_with_both_image_kinds(path: Path) -> None:
    parts = {
        "xl/workbook.xml": """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ficha" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="llg_analysis_observaciones">Ficha!$B$92:$H$119</definedName></definedNames></workbook>""",
        "xl/_rels/workbook.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>""",
        "xl/worksheets/sheet1.xml": """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetData><row r="66"><c r="B66" t="inlineStr"><is><t>Criterios evaluables mediante fórmula</t></is></c></row><row r="68"><c r="E68" vm="1" t="e"><v>#VALUE!</v></c></row><row r="91"><c r="B91" t="inlineStr"><is><t>Observaciones</t></is></c></row><row r="93"><c r="B93" vm="2" t="e"><v>#VALUE!</v></c></row></sheetData><drawing r:id="rId1"/></worksheet>""",
        "xl/worksheets/_rels/sheet1.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/></Relationships>""",
        "xl/drawings/drawing1.xml": """<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><xdr:oneCellAnchor><xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="Logo flotante"/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId1"/></xdr:blipFill></xdr:pic></xdr:oneCellAnchor></xdr:wsDr>""",
        "xl/drawings/_rels/drawing1.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/floating.png"/></Relationships>""",
        "xl/metadata.xml": """<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><valueMetadata count="2"><bk><rc t="1" v="0"/></bk><bk><rc t="1" v="1"/></bk></valueMetadata></metadata>""",
        "xl/richData/rdrichvaluestructure.xml": """<rvStructures xmlns="http://schemas.microsoft.com/office/spreadsheetml/2017/richdata" count="1"><s t="_localImage"><k n="_rvRel:LocalImageIdentifier" t="i"/><k n="CalcOrigin" t="i"/></s></rvStructures>""",
        "xl/richData/rdrichvalue.xml": """<rvData xmlns="http://schemas.microsoft.com/office/spreadsheetml/2017/richdata" count="2"><rv s="0"><v>0</v><v>5</v></rv><rv s="0"><v>1</v><v>5</v></rv></rvData>""",
        "xl/richData/richValueRel.xml": """<richValueRels xmlns="http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><rel r:id="rId1"/><rel r:id="rId2"/></richValueRels>""",
        "xl/richData/_rels/richValueRel.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/formula.png"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/observation.png"/></Relationships>""",
    }
    with zipfile.ZipFile(path, "w") as package:
        for name, body in parts.items():
            package.writestr(name, body)
        package.writestr("xl/media/floating.png", _ONE_PIXEL_PNG)
        package.writestr("xl/media/formula.png", _ONE_PIXEL_PNG)
        package.writestr("xl/media/observation.png", _ONE_PIXEL_PNG)


def _client_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            razon_social TEXT NOT NULL,
            nombre_comercial TEXT,
            activo INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO clientes VALUES (1, 'Árbol Norte, S.L.', 'Árbol', 1, '2026-01-01T10:00:00');
        INSERT INTO clientes VALUES (2, 'Árbol Sur, S.L.', 'Árbol', 1, '2026-01-02T10:00:00');
        INSERT INTO clientes VALUES (3, 'Ñandú Histórico, S.A.', NULL, 0, '2025-01-01T10:00:00');
        """
    )
    conn.commit()
    conn.close()


def test_validation_distinguishes_errors_warnings_and_information() -> None:
    payload = short_payload()
    payload["tender"]["hora_limite"] = "11:30"
    payload["analysis"]["observaciones"] = ""
    issues = validate_payload(payload)
    severities = {issue.severity for issue in issues}
    assert "warning" in severities
    assert "info" in severities
    assert not [issue for issue in issues if issue.severity == "error"]


def test_read_only_connection_rejects_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "clients.sqlite"
    _client_db(db_path)
    before = db_path.read_bytes()
    conn = open_read_only(db_path)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("INSERT INTO clientes VALUES (9, 'No', NULL, 1, '')")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("CREATE TABLE forbidden (id INTEGER)")
    conn.close()
    assert db_path.read_bytes() == before


def test_missing_client_database_has_a_human_error(tmp_path: Path) -> None:
    with pytest.raises(ClientReadError, match="No se encuentra"):
        read_clients(tmp_path / "missing.sqlite")


def test_temporarily_locked_client_database_fails_cleanly(tmp_path: Path) -> None:
    db_path = tmp_path / "clients.sqlite"
    _client_db(db_path)
    writer = sqlite3.connect(db_path)
    writer.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(ClientReadError, match="No se pudo consultar"):
            read_clients(db_path, timeout=0.01)
    finally:
        writer.rollback()
        writer.close()


def test_empty_client_database_exports_an_empty_catalogue(tmp_path: Path) -> None:
    db_path = tmp_path / "clients.sqlite"
    _client_db(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute("DELETE FROM clientes")
    connection.commit()
    connection.close()
    output = tmp_path / "clients.json"
    path, count = export_clients(output, db_path=db_path)
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert count == 0
    assert parsed["clients"] == []


def test_client_export_handles_duplicates_unicode_and_inactive(tmp_path: Path) -> None:
    db_path = tmp_path / "clients.sqlite"
    _client_db(db_path)
    clients = read_clients(db_path)
    assert len(clients) == 3
    assert clients[0]["label"] == "Árbol Norte, S.L."
    assert clients[-1]["label"].endswith("(inactivo)")
    output = tmp_path / "clients.json"
    path, count = export_clients(output, db_path=db_path)
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert count == 3
    assert parsed["status"] == "ok"
    assert parsed["clients"][0]["display_name"] == "Árbol Norte, S.L."
    assert parsed["clients"][2]["display_name"] == "Ñandú Histórico, S.A."


def test_client_tsv_export_includes_new_database_columns_automatically(tmp_path: Path) -> None:
    db_path = tmp_path / "clients.sqlite"
    _client_db(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute("ALTER TABLE clientes ADD COLUMN campo_futuro TEXT")
    connection.execute("ALTER TABLE clientes ADD COLUMN observaciones_internas TEXT")
    connection.execute(
        "UPDATE clientes SET campo_futuro = ?, observaciones_internas = ? WHERE id = 1",
        ("Valor dinámico", 'Primera línea\nSegunda línea con "comillas"'),
    )
    connection.commit()
    connection.close()

    path, count = export_clients(tmp_path / "clients.tsv", db_path=db_path)
    rows = list(csv.reader(StringIO(path.read_text(encoding="utf-8")), delimiter="\t"))
    header = next(row for row in rows if row and row[0] == "id")
    first_client = next(row for row in rows if row and row[0] == "1")
    assert count == 3
    assert header[:7] == ["id", "label", "display_name", "razon_social", "nombre_comercial", "active", "updated_at"]
    assert "campo_futuro" in header
    assert first_client[header.index("campo_futuro")] == "Valor dinámico"
    assert first_client[header.index("observaciones_internas")] == 'Primera línea\nSegunda línea con "comillas"'


def test_bridge_only_accepts_enumerated_operations() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["sql", "SELECT 1"])


def test_bridge_reads_the_utf8_bom_written_by_excel(tmp_path: Path) -> None:
    source_url = "https://contrataciondelestado.es/wps/poc?idEvl=ficticio%2Bseguro%3D%3D"
    source_file = tmp_path / "source.txt"
    source_file.write_text(source_url, encoding="utf-8-sig")
    assert _read_source_file(source_file) == source_url


def test_pdf_output_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    requested = tmp_path / "ficha.pdf"
    requested.write_bytes(b"original")
    assert _unique_pdf_path(requested) == tmp_path / "ficha_r2.pdf"


def test_pdf_contains_a_clickable_tender_link(tmp_path: Path) -> None:
    output = tmp_path / "linked.pdf"
    render_tender_pdf(normal_payload(), output)
    reader = PdfReader(str(output))
    uris = []
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            if action and action.get("/URI"):
                uris.append(action.get("/URI"))
    assert "https://contrataciondelestado.es/ejemplo-ficticio" in uris


def test_workbook_image_extractor_reads_floating_and_in_cell_pictures(tmp_path: Path) -> None:
    workbook = tmp_path / "ficha.xlsm"
    _workbook_with_both_image_kinds(workbook)
    images = extract_ficha_images(workbook, tmp_path / "images")
    assert [(item.kind, item.cell, item.section_number) for item in images] == [
        ("floating", "B2", 0),
        ("in_cell", "E68", 7),
        ("in_cell", "B93", 9),
    ]
    assert all(item.path.is_file() for item in images)


def test_pdf_includes_workbook_images_in_their_sheet_context(tmp_path: Path) -> None:
    workbook = tmp_path / "ficha.xlsm"
    _workbook_with_both_image_kinds(workbook)
    images = extract_ficha_images(workbook, tmp_path / "images")
    output = tmp_path / "with-images.pdf"
    result = render_tender_pdf(normal_payload(), output, workbook_images=images)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output)).pages)
    assert result.page_count >= 1
    assert "Imagen en celda" not in text
    assert "posición" not in text
    assert "Error 2015" not in text


def test_place_adapter_maps_only_supported_fields() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ext:ContractFolderStatus xmlns:ext="urn:place"
      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
      xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:ContractFolderID>XML-33/2026</cbc:ContractFolderID>
      <cac:ProcurementProject>
        <cbc:Name>Servicio ficticio importado</cbc:Name>
        <cbc:TypeCode>Servicios</cbc:TypeCode>
        <cac:PlannedPeriod><cbc:DurationMeasure unitCode="MON">12</cbc:DurationMeasure></cac:PlannedPeriod>
      </cac:ProcurementProject>
      <cac:TenderingProcess>
        <cbc:ProcedureCode>Abierto</cbc:ProcedureCode>
        <cac:TenderSubmissionDeadlinePeriod>
          <cbc:EndDate>2030-10-15</cbc:EndDate><cbc:EndTime>14:00:00</cbc:EndTime>
        </cac:TenderSubmissionDeadlinePeriod>
      </cac:TenderingProcess>
    </ext:ContractFolderStatus>"""
    payload, warnings = payload_from_place_xml(
        xml,
        "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=ficticio",
    )
    assert payload["control"]["source"] == "place"
    assert payload["tender"]["expediente"] == "XML-33/2026"
    assert payload["tender"]["objeto"] == "Servicio ficticio importado"
    assert payload["analysis"]["plazo"] == "12 meses"
    assert isinstance(warnings, list)


def test_place_adapter_derives_calendar_term_and_extensions() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ext:ContractFolderStatus xmlns:ext="urn:place"
      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
      xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cac:ProcurementProject>
        <cac:PlannedPeriod>
          <cbc:StartDate>2026-12-05+01:00</cbc:StartDate>
          <cbc:EndDate>2026-12-30+01:00</cbc:EndDate>
        </cac:PlannedPeriod>
        <cac:ContractExtension><cbc:MaximumNumberNumeric>2</cbc:MaximumNumberNumeric></cac:ContractExtension>
      </cac:ProcurementProject>
    </ext:ContractFolderStatus>"""
    payload, _warnings = payload_from_place_xml(
        xml,
        "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=ficticio",
    )
    assert {key: payload["analysis"][key] for key in (
        "plazo", "plazo_comentario", "prorroga", "prorroga_comentario"
    )} == {
        "plazo": "25 días",
        "plazo_comentario": "Del 05/12/2026 al 30/12/2026",
        "prorroga": "Sí",
        "prorroga_comentario": "Máximo de 2 prórrogas.",
    }


def test_place_adapter_accepts_a_normal_tender_page_and_exports_bridge_tsv(tmp_path: Path) -> None:
    source_url = (
        "https://contrataciondelestado.es/wps/poc?"
        "uri=deeplink:detalle_licitacion&idEvl=ficticio%2Bseguro%3D%3D"
    )
    html = """
    <html><body><table>
      <tr><th>Número de expediente</th><td>PERFIL-44/2030</td></tr>
      <tr><th>Objeto del contrato</th><td>Servicio ficticio desde la página pública</td></tr>
      <tr><th>Órgano de contratación</th><td>Organismo Público de Prueba</td></tr>
      <tr><th>Fecha límite de presentación</th><td>20/11/2030 14:30</td></tr>
      <tr><th>Presupuesto base de licitación</th><td>12.345,67 EUR</td></tr>
    </table></body></html>
    """
    payload, warnings = payload_from_place_source(source_url, fetcher=lambda _url: html)
    assert payload["tender"]["expediente"] == "PERFIL-44/2030"
    assert payload["tender"]["objeto"] == "Servicio ficticio desde la página pública"
    assert payload["tender"]["fecha_limite"] == "2030-11-20"
    assert payload["tender"]["hora_limite"] == "14:30"
    assert payload["tender"]["enlace"] == source_url
    assert isinstance(warnings, list)

    output, count, warning_count = export_place(source_url, tmp_path / "place.tsv", fetcher=lambda _url: html)
    rows = list(csv.reader(output.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    exported = {row[0]: row[1] for row in rows if len(row) >= 2}
    assert count >= 6
    assert warning_count == len(warnings)
    assert exported["tender.expediente"] == "PERFIL-44/2030"
    assert exported["tender.enlace"] == source_url


def test_place_adapter_rejects_non_https_or_non_place_urls() -> None:
    for source_url in (
        "http://contrataciondelestado.es/wps/poc",
        "https://example.com/tender/1",
    ):
        with pytest.raises(CaptureError, match="Solo se permiten"):
            payload_from_place_source(source_url, fetcher=lambda _url: "<html></html>")


@pytest.mark.parametrize("factory", [short_payload, extreme_payload])
def test_pdf_renderer_creates_readable_multipage_document(tmp_path: Path, factory) -> None:
    output = tmp_path / f"{factory.__name__}.pdf"
    result = render_tender_pdf(factory(), output)
    reader = PdfReader(str(output))
    assert result.page_count == len(reader.pages)
    assert result.page_count >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "FICHA DE LICITACIÓN" in text
    assert "Página 1 de" in text
    assert "EXP-FICTICIO" in text
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        assert len(page_text.strip()) > 80
        assert f"Página {index} de {result.page_count}" in page_text
        assert "Cliente Demostración, S.L." in page_text
        assert "Documento confidencial para uso exclusivo de Cliente Demostración, S.L." in page_text


def test_pdf_final_rejects_payload_errors_but_draft_allows_them(tmp_path: Path) -> None:
    payload = short_payload()
    payload["tender"]["expediente"] = ""
    with pytest.raises(ValueError):
        render_tender_pdf(payload, tmp_path / "final.pdf")
    result = render_tender_pdf(payload, tmp_path / "draft.pdf", draft=True)
    assert result.page_count >= 1
