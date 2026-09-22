"""Adapter from PLACE pages/XML to the Ficha v2 payload."""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from ..licitacion_capture import (
    MAX_CAPTURE_HTML_BYTES,
    CaptureError,
    CaptureFetchError,
    capture_licitacion_from_url,
    parse_place_document_xml,
)
from .payload import iso_now, normalize_payload


FIELD_MAP = {
    "expediente": "expediente",
    "objeto": "objeto",
    "organismo": "organismo",
    "presupuesto": "presupuesto_base",
    "valor_estimado": "valor_estimado",
    "tipo": "tipo_contrato",
    "procedimiento": "procedimiento",
    "regulacion_armonizada": "regulacion_armonizada",
    "provincia": "provincia",
    "fecha_limite": "fecha_limite",
    "hora_limite": "hora_limite",
    "enlace_perfil": "enlace",
    "plataforma": "plataforma",
}

PLACE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
PLACE_TIMEOUT = (5, 20)
PLACE_MAX_REDIRECTS = 5
PLACE_RETRY_STATUS = {500, 502, 503, 504}


def _is_safe_place_url(url: str) -> bool:
    parsed = urlsplit(str(url or "").strip())
    host = (parsed.hostname or "").casefold().rstrip(".")
    return (
        parsed.scheme.casefold() == "https"
        and (host == "contrataciondelestado.es" or host.endswith(".contrataciondelestado.es"))
    )


def _require_safe_place_url(url: str) -> str:
    candidate = str(url or "").strip()
    if not _is_safe_place_url(candidate):
        raise CaptureError("Solo se permiten URL HTTPS del dominio contrataciondelestado.es.")
    return candidate


def _looks_like_access_challenge(content: bytes) -> bool:
    sample = content[:65536].decode("utf-8", errors="ignore").casefold()
    markers = (
        "please enable javascript to view the page content",
        "verify you are human",
        "verification required",
        "verifique que es humano",
        "captcha",
    )
    return any(marker in sample for marker in markers)


def _looks_like_place_xml(text: str) -> bool:
    sample = str(text or "").lstrip()[:1600].casefold()
    return (
        sample.startswith("<?xml")
        or "contractfolderstatus" in sample
        or "<cbc:" in sample
        or "<cac:" in sample
    )


def _extract_place_xml_links(html_text: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: list[tuple[datetime, int, str]] = []
    seen: set[str] = set()
    for index, image in enumerate(soup.find_all("img")):
        alt = str(image.get("alt") or "").casefold()
        src = str(image.get("src") or "").casefold()
        if "documento xml" not in alt and "xml-icon" not in src:
            continue
        link = image.find_parent("a")
        href = str(link.get("href") or "") if link else ""
        candidate = urljoin(base_url, href)
        if not href or candidate in seen or not _is_safe_place_url(candidate):
            continue
        seen.add(candidate)
        row = image.find_parent("tr")
        row_text = " ".join(row.get_text(" ", strip=True).split()) if row else ""
        published_at = datetime.min
        for pattern in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            length = 19 if pattern.endswith("%S") else 16
            try:
                published_at = datetime.strptime(row_text[:length], pattern)
                break
            except ValueError:
                continue
        candidates.append((published_at, -index, candidate))
    candidates.sort(reverse=True)
    return [candidate for _published_at, _index, candidate in candidates]


def _first_xml_element(root: ElementTree.Element, local_name: str) -> ElementTree.Element | None:
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == local_name:
            return element
    return None


def _first_xml_descendant(
    root: ElementTree.Element,
    parent_local_name: str,
    child_local_name: str,
) -> ElementTree.Element | None:
    parent = _first_xml_element(root, parent_local_name)
    if parent is None:
        return None
    return _first_xml_element(parent, child_local_name)


def _direct_xml_child(parent: ElementTree.Element | None, local_name: str) -> ElementTree.Element | None:
    if parent is None:
        return None
    for child in parent:
        if child.tag.rsplit("}", 1)[-1] == local_name:
            return child
    return None


def _node_text(node: ElementTree.Element | None) -> str:
    return str(node.text or "").strip() if node is not None else ""


def _place_date(value: str) -> date | None:
    candidate = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _span_comment(start_text: str, end_text: str) -> str:
    start = _place_date(start_text)
    end = _place_date(end_text)
    if start and end:
        return f"Del {start:%d/%m/%Y} al {end:%d/%m/%Y}"
    if start:
        return f"Desde el {start:%d/%m/%Y}"
    if end:
        return f"Hasta el {end:%d/%m/%Y}"
    return ""


def _format_maximum_extensions(value: str) -> str:
    try:
        number = float(str(value or "").strip().replace(",", "."))
    except ValueError:
        return ""
    if number <= 0:
        return ""
    shown = str(int(number)) if number.is_integer() else str(number).replace(".", ",")
    label = "prórroga" if number == 1 else "prórrogas"
    return f"Máximo de {shown} {label}."


def _augment_payload_from_xml(payload: dict[str, Any], xml_text: str) -> None:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return
    tender = payload.setdefault("tender", {})
    analysis = payload.setdefault("analysis", {})
    for parent_name, local_name, key in (
        ("ProcurementProject", "TypeCode", "tipo_contrato"),
        ("TenderingProcess", "ProcedureCode", "procedimiento"),
    ):
        node = _first_xml_descendant(root, parent_name, local_name)
        if node is not None:
            value = str(node.attrib.get("name") or node.text or "").strip()
            if value:
                tender[key] = value
    threshold = _first_xml_element(root, "OverThresholdIndicator")
    if threshold is not None:
        normalized = str(threshold.text or "").strip().casefold()
        if normalized in {"true", "1", "si", "sí", "yes"}:
            tender["regulacion_armonizada"] = "Sí"
        elif normalized in {"false", "0", "no"}:
            tender["regulacion_armonizada"] = "No"
    procurement = _first_xml_element(root, "ProcurementProject")
    planned = _direct_xml_child(procurement, "PlannedPeriod")
    duration = _direct_xml_child(planned, "DurationMeasure")
    amount = _node_text(duration)
    start_text = _node_text(_direct_xml_child(planned, "StartDate"))
    end_text = _node_text(_direct_xml_child(planned, "EndDate"))
    if amount:
        unit = str(duration.attrib.get("unitCode") or "").strip().upper()
        labels = {
            "ANN": ("año", "años"),
            "YEAR": ("año", "años"),
            "MON": ("mes", "meses"),
            "WEE": ("semana", "semanas"),
            "DAY": ("día", "días"),
            "HUR": ("hora", "horas"),
        }
        singular, plural = labels.get(unit, ("", ""))
        if singular:
            analysis["plazo"] = f"{amount} {singular if amount in {'1', '1.0'} else plural}"
    else:
        start = _place_date(start_text)
        end = _place_date(end_text)
        if start and end and end >= start:
            days = (end - start).days
            analysis["plazo"] = f"{days} {'día' if days == 1 else 'días'}"

    period_comment = _span_comment(start_text, end_text)
    description = _node_text(_direct_xml_child(planned, "Description"))
    if period_comment and description:
        analysis["plazo_comentario"] = f"{period_comment}. {description}"
    elif period_comment or description:
        analysis["plazo_comentario"] = period_comment or description

    extension = _direct_xml_child(procurement, "ContractExtension")
    if extension is None:
        extension = _first_xml_element(root, "ContractExtension")
    if extension is not None:
        maximum = _node_text(_direct_xml_child(extension, "MaximumNumberNumeric"))
        detail = ""
        validity = _direct_xml_child(extension, "OptionValidityPeriod")
        for candidate in (
            _direct_xml_child(validity, "Description"),
            _direct_xml_child(extension, "OptionsDescription"),
            _direct_xml_child(extension, "Description"),
        ):
            detail = _node_text(candidate)
            if detail:
                break
        fallback_detail = _format_maximum_extensions(maximum)
        try:
            has_extension = float(maximum.replace(",", ".")) > 0 if maximum else bool(detail)
        except ValueError:
            has_extension = bool(detail)
        analysis["prorroga"] = "Sí" if has_extension else "No"
        if has_extension and (detail or fallback_detail):
            analysis["prorroga_comentario"] = detail or fallback_detail


def _read_limited_response(response: requests.Response) -> bytes:
    content = bytearray()
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        content.extend(chunk)
        if len(content) > MAX_CAPTURE_HTML_BYTES:
            raise CaptureFetchError("La respuesta de PLACE supera el limite de 2 MB.")
    return bytes(content)


def fetch_place_source_text(source_url: str, *, session: requests.Session | None = None) -> str:
    """Fetch a public PLACE page/XML with bounded redirects and browser headers."""

    current_url = _require_safe_place_url(source_url)
    active_session = session or requests.Session()
    active_session.headers.update(
        {
            "User-Agent": PLACE_USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/xml;q=0.9,*/*;q=0.8",
        }
    )
    try:
        for _ in range(PLACE_MAX_REDIRECTS + 1):
            response = None
            for attempt in range(3):
                try:
                    response = active_session.get(
                        current_url,
                        timeout=PLACE_TIMEOUT,
                        allow_redirects=False,
                        stream=True,
                    )
                except requests.RequestException as exc:
                    raise CaptureFetchError("No se pudo conectar con PLACE.") from exc
                if response.status_code not in PLACE_RETRY_STATUS or attempt == 2:
                    break
                response.close()
                time.sleep(0.35 * (attempt + 1))

            if response is None:
                raise CaptureFetchError("No se pudo conectar con PLACE.")
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = str(response.headers.get("Location") or "")
                    next_url = urljoin(current_url, location)
                    current_url = _require_safe_place_url(next_url)
                    continue
                if response.status_code < 200 or response.status_code >= 300:
                    raise CaptureFetchError(
                        f"PLACE no permitio consultar la licitacion (HTTP {response.status_code})."
                    )
                content = _read_limited_response(response)
                if _looks_like_access_challenge(content):
                    raise CaptureFetchError(
                        "PLACE solicita una validacion web. Abra el enlace en el navegador y vuelva a intentarlo."
                    )
                encoding = response.encoding or "utf-8"
                return content.decode(encoding, errors="replace")
            finally:
                response.close()
        raise CaptureFetchError("PLACE supero el maximo de redirecciones permitido.")
    finally:
        if session is None:
            active_session.close()


def payload_from_place_capture(capture: dict[str, object]) -> tuple[dict[str, Any], list[str]]:
    fields = dict(capture.get("fields") or {})
    tender: dict[str, Any] = {}
    for source_field, target_field in FIELD_MAP.items():
        value = fields.get(source_field)
        if value not in (None, ""):
            tender[target_field] = value
    analysis: dict[str, Any] = {}
    duration = fields.get("duracion")
    if duration not in (None, ""):
        analysis["plazo"] = duration
    payload = normalize_payload(
        {
            "control": {
                "source": "place",
                "last_import_at": iso_now(),
                "source_url": capture.get("source_url", ""),
            },
            "tender": tender,
            "analysis": analysis,
        }
    )
    return payload, list(capture.get("warnings") or [])


def payload_from_place_source(
    source_url: str,
    *,
    fetcher=None,
) -> tuple[dict[str, Any], list[str]]:
    safe_url = _require_safe_place_url(source_url)
    active_fetcher = fetcher or fetch_place_source_text
    source_text = active_fetcher(safe_url)
    if _looks_like_place_xml(source_text):
        capture = capture_licitacion_from_url(
            safe_url,
            fetcher=lambda _url: source_text,
            profile_url=safe_url,
        )
        payload, warnings = payload_from_place_capture(capture)
        _augment_payload_from_xml(payload, source_text)
        return payload, warnings

    for xml_url in _extract_place_xml_links(source_text, safe_url)[:12]:
        try:
            xml_text = active_fetcher(xml_url)
        except CaptureError:
            continue
        if not _looks_like_place_xml(xml_text):
            continue
        capture = capture_licitacion_from_url(
            xml_url,
            fetcher=lambda _url: xml_text,
            profile_url=safe_url,
        )
        capture["source_url"] = safe_url
        payload, warnings = payload_from_place_capture(capture)
        _augment_payload_from_xml(payload, xml_text)
        return payload, warnings

    capture = capture_licitacion_from_url(
        safe_url,
        fetcher=lambda _url: source_text,
        profile_url=safe_url,
    )
    return payload_from_place_capture(capture)


def payload_from_place_xml(xml_text: str, source_url: str) -> tuple[dict[str, Any], list[str]]:
    capture = parse_place_document_xml(xml_text, source_url)
    payload, warnings = payload_from_place_capture(capture)
    _augment_payload_from_xml(payload, xml_text)
    return payload, warnings


__all__ = (
    "FIELD_MAP",
    "fetch_place_source_text",
    "payload_from_place_capture",
    "payload_from_place_source",
    "payload_from_place_xml",
)
