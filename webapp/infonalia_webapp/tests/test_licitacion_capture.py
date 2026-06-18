from __future__ import annotations

from http import HTTPStatus

import pytest

from webapp.infonalia_webapp.licitacion_capture import (
    CaptureFetchError,
    UnsupportedPlatform,
    UnsafeCaptureUrl,
    capture_licitacion_from_url,
    detect_platform_from_url,
    parse_place_detail_html,
    parse_place_document_xml,
    validate_capture_url,
)
from webapp.infonalia_webapp.tests.test_actuaciones_api import dispatch, make_handler
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import count_rows
from webapp.infonalia_webapp.tests.test_import_endpoints import VALID_CSRF_TOKEN, load_app_module, temporary_app_database


PLACE_URL = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=test"
PLACE_XML_URL = "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=test"
PLACE_HTML = """
<html>
  <body>
    <table>
      <tr><th>Número de Expediente</th><td>EXP-123/2026</td></tr>
      <tr><th>Objeto del Contrato</th><td>Suministro de material de oficina</td></tr>
      <tr><th>Órgano de Contratación</th><td>Junta de Contratación de Prueba</td></tr>
      <tr><th>Presupuesto base de licitación</th><td>12.345,67 EUR</td></tr>
      <tr><th>Fecha fin de presentación de oferta</th><td>20/07/2026 14:00</td></tr>
      <tr><th>Provincia</th><td>Madrid</td></tr>
      <tr><th>Tipo de Contrato</th><td>Suministros</td></tr>
      <tr><th>Procedimiento de contratación</th><td>Abierto</td></tr>
      <tr><th>Código CPV</th><td>30190000</td></tr>
      <tr><th>Valor estimado del contrato</th><td>15.000,00 EUR</td></tr>
      <tr><th>Duración del contrato</th><td>12 meses</td></tr>
    </table>
  </body>
</html>
"""
PLACE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ext:ContractFolderStatus
  xmlns:ext="urn:place"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ContractFolderID>XML-33/2026</cbc:ContractFolderID>
  <cbc:ContractFolderStatusCode>EV</cbc:ContractFolderStatusCode>
  <ext:LocatedContractingParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>Ayuntamiento de Prueba XML</cbc:Name>
      </cac:PartyName>
    </cac:Party>
  </ext:LocatedContractingParty>
  <cac:ProcurementProject>
    <cbc:Name>Servicio de mantenimiento capturado desde XML</cbc:Name>
    <cbc:TypeCode>Servicios</cbc:TypeCode>
    <cac:BudgetAmount>
      <cbc:TotalAmount currencyID="EUR">12345.67</cbc:TotalAmount>
      <cbc:EstimatedOverallContractAmount currencyID="EUR">15000.00</cbc:EstimatedOverallContractAmount>
    </cac:BudgetAmount>
    <cac:RequiredCommodityClassification>
      <cbc:ItemClassificationCode>72000000</cbc:ItemClassificationCode>
    </cac:RequiredCommodityClassification>
    <cac:RealizedLocation>
      <cac:Address>
        <cbc:CountrySubentity>Madrid</cbc:CountrySubentity>
        <cbc:CityName>Madrid</cbc:CityName>
      </cac:Address>
    </cac:RealizedLocation>
    <cac:PlannedPeriod>
      <cbc:DurationMeasure unitCode="MON">12</cbc:DurationMeasure>
    </cac:PlannedPeriod>
  </cac:ProcurementProject>
  <cac:TenderingProcess>
    <cbc:ProcedureCode>Abierto</cbc:ProcedureCode>
    <cac:TenderSubmissionDeadlinePeriod>
      <cbc:EndDate>2026-07-20</cbc:EndDate>
      <cbc:EndTime>14:00:00</cbc:EndTime>
    </cac:TenderSubmissionDeadlinePeriod>
  </cac:TenderingProcess>
</ext:ContractFolderStatus>
"""


def test_detect_platform_from_place_url() -> None:
    assert detect_platform_from_url(PLACE_URL) == "PLACE"
    assert detect_platform_from_url("https://example.test/licitacion") == ""


def test_capture_unknown_platform_is_not_available() -> None:
    with pytest.raises(UnsupportedPlatform, match="no disponible"):
        capture_licitacion_from_url("https://example.test/licitacion", fetcher=lambda _url: "<html></html>")


def test_parse_place_detail_html_extracts_safe_fields() -> None:
    payload = parse_place_detail_html(PLACE_HTML, PLACE_URL)
    fields = payload["fields"]

    assert payload["ok"] is True
    assert payload["platform"] == "PLACE"
    assert fields["expediente"] == "EXP-123/2026"
    assert fields["objeto"] == "Suministro de material de oficina"
    assert fields["organismo"] == "Junta de Contratación de Prueba"
    assert fields["organo_contratacion"] == "Junta de Contratación de Prueba"
    assert fields["presupuesto"] == "12.345,67 EUR"
    assert fields["fecha_limite"] == "2026-07-20"
    assert fields["fecha_presentacion"] == "2026-07-20"
    assert fields["hora_limite"] == "14:00"
    assert fields["provincia"] == "Madrid"
    assert fields["tipo"] == "Suministros"
    assert fields["procedimiento"] == "Abierto"
    assert fields["cpv"] == "30190000"
    assert fields["valor_estimado"] == "15.000,00 EUR"
    assert fields["duracion"] == "12 meses"
    assert fields["plataforma"] == "PLACE"
    assert fields["enlace_perfil"] == PLACE_URL


def test_parse_place_document_xml_extracts_codice_fields_and_preserves_profile_url() -> None:
    payload = parse_place_document_xml(PLACE_XML, PLACE_XML_URL, profile_url=PLACE_URL)
    fields = payload["fields"]

    assert payload["ok"] is True
    assert payload["platform"] == "PLACE"
    assert payload["source_url"] == PLACE_XML_URL
    assert fields["expediente"] == "XML-33/2026"
    assert fields["objeto"] == "Servicio de mantenimiento capturado desde XML"
    assert fields["organismo"] == "Ayuntamiento de Prueba XML"
    assert fields["organo_contratacion"] == "Ayuntamiento de Prueba XML"
    assert fields["presupuesto"] == "12345.67"
    assert fields["valor_estimado"] == "15000.00"
    assert fields["fecha_limite"] == "2026-07-20"
    assert fields["fecha_presentacion"] == "2026-07-20"
    assert fields["hora_limite"] == "14:00"
    assert fields["provincia"] == "Madrid"
    assert fields["tipo"] == "Servicios"
    assert fields["procedimiento"] == "Abierto"
    assert fields["cpv"] == "72000000"
    assert fields["estado_licitacion"] == "EV"
    assert fields["duracion"] == "12"
    assert fields["plataforma"] == "PLACE"
    assert fields["enlace_perfil"] == PLACE_URL


def test_parse_place_detail_html_omits_missing_and_ambiguous_fields() -> None:
    html = """
    <table>
      <tr><th>Número de Expediente</th><td>EXP-A</td></tr>
      <tr><th>Número de Expediente</th><td>EXP-B</td></tr>
      <tr><th>Objeto del Contrato</th><td>Servicio claro</td></tr>
    </table>
    """

    payload = parse_place_detail_html(html, PLACE_URL)

    assert "expediente" not in payload["fields"]
    assert payload["fields"]["objeto"] == "Servicio claro"
    assert "Campo ambiguo omitido: expediente." in payload["warnings"]


def test_validate_capture_url_rejects_unsafe_urls() -> None:
    for url in ["file:///C:/temp/a.html", "http://localhost:8787", "http://127.0.0.1/test", "http://192.168.1.3/x"]:
        with pytest.raises(UnsafeCaptureUrl):
            validate_capture_url(url)


def test_capture_licitacion_uses_fake_fetcher_without_network() -> None:
    calls = []

    def fake_fetcher(url: str) -> str:
        calls.append(url)
        return PLACE_HTML

    payload = capture_licitacion_from_url(PLACE_URL, fetcher=fake_fetcher)

    assert calls == [PLACE_URL]
    assert payload["fields"]["expediente"] == "EXP-123/2026"


def test_capture_licitacion_uses_xml_document_without_network() -> None:
    calls = []

    def fake_fetcher(url: str) -> str:
        calls.append(url)
        return PLACE_XML

    payload = capture_licitacion_from_url(PLACE_XML_URL, fetcher=fake_fetcher, profile_url=PLACE_URL)

    assert calls == [PLACE_XML_URL]
    assert payload["source_url"] == PLACE_XML_URL
    assert payload["fields"]["expediente"] == "XML-33/2026"
    assert payload["fields"]["enlace_perfil"] == PLACE_URL


def test_capture_api_returns_fields_without_saving(monkeypatch) -> None:
    app = load_app_module()
    captured = {
        "ok": True,
        "platform": "PLACE",
        "fields": {"expediente": "EXP-API", "plataforma": "PLACE", "enlace_perfil": PLACE_URL},
        "warnings": [],
        "source_url": PLACE_URL,
    }
    seen = {}

    def fake_capture(url: str, profile_url: str | None = None) -> dict[str, object]:
        seen["url"] = url
        seen["profile_url"] = profile_url
        return captured

    monkeypatch.setattr(app, "capture_licitacion_from_url", fake_capture)
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/licitaciones/capture",
            {"url": PLACE_XML_URL, "profile_url": PLACE_URL},
            csrf_token=VALID_CSRF_TOKEN,
        )
        dispatch(handler, "POST")

        assert handler.responses[-1] == (HTTPStatus.OK, captured)
        assert seen == {"url": PLACE_XML_URL, "profile_url": PLACE_URL}
        assert count_rows(app, "licitaciones") == 0


def test_capture_api_requires_auth() -> None:
    app = load_app_module()
    handler = make_handler(
        app,
        "POST",
        "/api/licitaciones/capture",
        {"url": PLACE_URL},
        csrf_token=VALID_CSRF_TOKEN,
    )
    handler.current_user = lambda: None

    dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.UNAUTHORIZED


def test_capture_api_requires_csrf() -> None:
    app = load_app_module()
    handler = make_handler(app, "POST", "/api/licitaciones/capture", {"url": PLACE_URL}, csrf_token=None)

    dispatch(handler, "POST")

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN


def test_capture_api_handles_network_error_without_500(monkeypatch) -> None:
    app = load_app_module()

    def fake_capture(_url: str) -> dict[str, object]:
        raise CaptureFetchError("Error consultando plataforma.")

    monkeypatch.setattr(app, "capture_licitacion_from_url", fake_capture)
    handler = make_handler(
        app,
        "POST",
        "/api/licitaciones/capture",
        {"url": PLACE_URL},
        csrf_token=VALID_CSRF_TOKEN,
    )

    dispatch(handler, "POST")

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert payload == {"ok": False, "error": "Error consultando plataforma."}


def test_capture_api_rejects_unsafe_url() -> None:
    app = load_app_module()
    handler = make_handler(
        app,
        "POST",
        "/api/licitaciones/capture",
        {"url": "file:///C:/temp/a.html"},
        csrf_token=VALID_CSRF_TOKEN,
    )

    dispatch(handler, "POST")

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False
    assert "http o https" in payload["error"]
