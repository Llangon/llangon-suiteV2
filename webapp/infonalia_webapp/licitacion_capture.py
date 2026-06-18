from __future__ import annotations

import html
import ipaddress
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from html.parser import HTMLParser
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse


MAX_CAPTURE_HTML_BYTES = 2 * 1024 * 1024
CAPTURE_TIMEOUT_SECONDS = 12
CAPTURE_USER_AGENT = "InfonaliaWeb platform capture/1.0"


class CaptureError(ValueError):
    pass


class UnsupportedPlatform(CaptureError):
    pass


class UnsafeCaptureUrl(CaptureError):
    pass


class CaptureFetchError(CaptureError):
    pass


class _SafeRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_capture_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _VisibleTextParser(HTMLParser):
    block_tags = {
        "article",
        "br",
        "dd",
        "div",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "label",
        "li",
        "p",
        "td",
        "th",
        "tr",
    }
    skip_tags = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.skip_tags:
            self._skip_depth += 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags and self._skip_depth:
            self._skip_depth -= 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "expediente": ("numero de expediente", "num expediente", "expediente"),
    "objeto": ("objeto del contrato", "objeto"),
    "organismo": ("organo de contratacion", "poder adjudicador", "entidad adjudicadora"),
    "presupuesto": ("presupuesto base de licitacion", "presupuesto base"),
    "valor_estimado": ("valor estimado del contrato", "valor estimado"),
    "fecha_limite": (
        "fecha fin de presentacion de oferta",
        "fecha limite de presentacion",
        "fecha limite de presentacion de oferta",
        "plazo de presentacion",
    ),
    "provincia": ("provincia", "lugar de ejecucion", "subentidad nacional"),
    "tipo": ("tipo de contrato", "tipo contrato"),
    "procedimiento": ("procedimiento de contratacion", "procedimiento"),
    "cpv": ("codigo cpv", "cpv"),
    "estado_licitacion": ("estado de la licitacion", "estado"),
    "duracion": ("duracion del contrato", "plazo de ejecucion", "duracion"),
}

FORM_FIELD_ALIASES = {
    "organismo": "organo_contratacion",
    "fecha_limite": "fecha_presentacion",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _norm(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _clean_value(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" :\t\r\n")
    return text


def detect_platform_from_url(url: str | None) -> str:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.hostname or "").lower().strip(".")
    if host == "contrataciondelestado.es" or host.endswith(".contrataciondelestado.es"):
        return "PLACE"
    return ""


def validate_capture_url(url: str | None) -> str:
    clean_url = str(url or "").strip()
    if not clean_url:
        raise UnsafeCaptureUrl("La URL es obligatoria.")
    parsed = urlparse(clean_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeCaptureUrl("La URL debe usar http o https.")
    if not parsed.netloc or not parsed.hostname:
        raise UnsafeCaptureUrl("La URL no es valida.")

    host = parsed.hostname.lower().strip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeCaptureUrl("No se permiten URLs locales.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return clean_url
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise UnsafeCaptureUrl("No se permiten IPs privadas o locales.")
    return clean_url


def _visible_tokens(html_text: str) -> list[str]:
    parser = _VisibleTextParser()
    parser.feed(html_text)
    joined = " ".join(parser.parts)
    lines = [line.strip() for line in re.split(r"\s*\n\s*", joined) if line.strip()]
    if len(lines) <= 1:
        lines = [part.strip() for part in re.split(r"\s{2,}", joined) if part.strip()]
    return [_clean_value(line) for line in lines if _clean_value(line)]


def _target_for_label(label: str) -> str:
    normalized = _norm(label)
    matches: list[str] = []
    for field, aliases in FIELD_ALIASES.items():
        if any(normalized == alias or normalized.startswith(f"{alias} ") for alias in aliases):
            matches.append(field)
    return matches[0] if len(matches) == 1 else ""


def _add_candidate(candidates: dict[str, list[str]], label: str, value: str) -> None:
    target = _target_for_label(label)
    cleaned = _clean_value(value)
    if target and cleaned and not _target_for_label(cleaned):
        candidates[target].append(cleaned)


def _extract_candidates(tokens: list[str]) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = defaultdict(list)
    for index, token in enumerate(tokens):
        if ":" in token:
            label, value = token.split(":", 1)
            _add_candidate(candidates, label, value)
        if index + 1 < len(tokens):
            _add_candidate(candidates, token, tokens[index + 1])
    return candidates


def _single_safe_value(field: str, values: list[str], warnings: list[str]) -> str:
    unique = []
    for value in values:
        cleaned = _clean_value(value)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    if not unique:
        return ""
    if len(unique) > 1:
        warnings.append(f"Campo ambiguo omitido: {field}.")
        return ""
    return unique[0]


def _normalize_date(value: str) -> tuple[str, str]:
    text = _clean_value(value)
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        year, month, day = (int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return "", ""
        date_value = f"{year:04d}-{month:02d}-{day:02d}"
        return date_value, _normalize_time(text)
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
    if not match:
        return "", ""
    day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return "", ""
    date_value = f"{year:04d}-{month:02d}-{day:02d}"
    time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if not time_match:
        return date_value, ""
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return date_value, f"{hour:02d}:{minute:02d}"
    return date_value, ""


def _normalize_time(value: str) -> str:
    text = _clean_value(value)
    time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if not time_match:
        return ""
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return ""


def parse_place_detail_html(html_text: str, url: str, *, profile_url: str | None = None) -> dict[str, object]:
    tokens = _visible_tokens(html_text)
    candidates = _extract_candidates(tokens)
    warnings: list[str] = []
    fields: dict[str, str] = {
        "plataforma": "PLACE",
        "enlace_perfil": validate_capture_url(profile_url or url),
    }

    for field, values in candidates.items():
        value = _single_safe_value(field, values, warnings)
        if value:
            fields[field] = value

    if fields.get("organismo"):
        fields["organo_contratacion"] = fields["organismo"]
    if fields.get("fecha_limite"):
        date_value, time_value = _normalize_date(fields["fecha_limite"])
        if date_value:
            fields["fecha_limite"] = date_value
            fields["fecha_presentacion"] = date_value
            if time_value:
                fields["hora_limite"] = time_value
        else:
            fields.pop("fecha_limite", None)
            warnings.append("Fecha limite omitida por formato no reconocido.")

    if len(fields) <= 2:
        warnings.append("No se han encontrado datos suficientes.")

    return {
        "ok": True,
        "platform": "PLACE",
        "fields": fields,
        "warnings": warnings,
        "source_url": validate_capture_url(url),
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _first_element(root: ET.Element | None, *names: str) -> ET.Element | None:
    if root is None:
        return None
    wanted = set(names)
    for element in root.iter():
        if _local_name(element.tag) in wanted:
            return element
    return None


def _first_text(root: ET.Element | None, *names: str) -> str:
    element = _first_element(root, *names)
    return _clean_value(element.text if element is not None else "")


def _first_available(*elements: ET.Element | None) -> ET.Element | None:
    for element in elements:
        if element is not None:
            return element
    return None


def _set_field(fields: dict[str, str], field: str, value: str) -> None:
    cleaned = _clean_value(value)
    if cleaned:
        fields[field] = cleaned


def _looks_like_xml(text: str) -> bool:
    sample = text.lstrip()[:1200].lower()
    return (
        sample.startswith("<?xml")
        or "contractfolderstatus" in sample
        or "<contractfolder" in sample
        or "<cbc:" in sample
        or "<cac:" in sample
    )


def parse_place_document_xml(xml_text: str, url: str, *, profile_url: str | None = None) -> dict[str, object]:
    source_url = validate_capture_url(url)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise CaptureError("No se pudo leer el XML de PLACE.") from exc

    warnings: list[str] = []
    fields: dict[str, str] = {
        "plataforma": "PLACE",
        "enlace_perfil": validate_capture_url(profile_url or source_url),
    }

    project = _first_element(root, "ProcurementProject")
    party = _first_element(root, "LocatedContractingParty", "ContractingParty")
    party_name = _first_element(party, "PartyName")
    budget = _first_available(_first_element(project, "BudgetAmount"), _first_element(root, "BudgetAmount"))
    process = _first_element(root, "TenderingProcess")
    deadline = _first_available(
        _first_element(process, "TenderSubmissionDeadlinePeriod"),
        _first_element(root, "TenderSubmissionDeadlinePeriod"),
    )
    location = _first_available(_first_element(project, "RealizedLocation"), _first_element(root, "RealizedLocation"))
    classification = _first_available(
        _first_element(project, "RequiredCommodityClassification"),
        _first_element(root, "RequiredCommodityClassification"),
    )
    period = _first_available(_first_element(project, "PlannedPeriod"), _first_element(root, "PlannedPeriod"))

    _set_field(fields, "expediente", _first_text(root, "ContractFolderID"))
    _set_field(fields, "objeto", _first_text(project, "Name"))
    _set_field(fields, "organismo", _first_text(party_name, "Name") or _first_text(party, "Name"))
    _set_field(fields, "presupuesto", _first_text(budget, "TotalAmount") or _first_text(budget, "TaxExclusiveAmount"))
    _set_field(fields, "valor_estimado", _first_text(budget, "EstimatedOverallContractAmount"))
    _set_field(fields, "tipo", _first_text(project, "TypeCode"))
    _set_field(fields, "procedimiento", _first_text(process, "ProcedureCode"))
    _set_field(fields, "cpv", _first_text(classification, "ItemClassificationCode"))
    _set_field(
        fields,
        "provincia",
        _first_text(location, "CountrySubentity") or _first_text(location, "CityName") or _first_text(location, "Description"),
    )
    _set_field(fields, "estado_licitacion", _first_text(root, "ContractFolderStatusCode"))
    _set_field(fields, "duracion", _first_text(period, "DurationMeasure") or _first_text(period, "Description"))

    if fields.get("organismo"):
        fields["organo_contratacion"] = fields["organismo"]

    deadline_date = _first_text(deadline, "EndDate")
    deadline_time = _first_text(deadline, "EndTime")
    if deadline_date:
        date_value, parsed_time = _normalize_date(deadline_date)
        if date_value:
            fields["fecha_limite"] = date_value
            fields["fecha_presentacion"] = date_value
        else:
            warnings.append("Fecha limite omitida por formato no reconocido.")
        time_value = _normalize_time(deadline_time) or parsed_time
        if time_value:
            fields["hora_limite"] = time_value

    if len(fields) <= 2:
        warnings.append("No se han encontrado datos suficientes en el XML.")

    return {
        "ok": True,
        "platform": "PLACE",
        "fields": fields,
        "warnings": warnings,
        "source_url": source_url,
    }


def fetch_capture_html(url: str, *, opener=None, timeout: int = CAPTURE_TIMEOUT_SECONDS) -> str:
    safe_url = validate_capture_url(url)
    request = urlrequest.Request(safe_url, headers={"User-Agent": CAPTURE_USER_AGENT})
    active_opener = opener or urlrequest.build_opener(_SafeRedirectHandler())
    try:
        response = active_opener.open(request, timeout=timeout)
        final_url = getattr(response, "geturl", lambda: safe_url)()
        validate_capture_url(final_url)
        content = response.read(MAX_CAPTURE_HTML_BYTES + 1)
    except HTTPError as exc:
        raise CaptureFetchError(f"Error consultando plataforma: HTTP {exc.code}.") from exc
    except (OSError, URLError) as exc:
        raise CaptureFetchError("Error consultando plataforma.") from exc
    if len(content) > MAX_CAPTURE_HTML_BYTES:
        raise CaptureFetchError("La respuesta de la plataforma es demasiado grande.")
    return content.decode("utf-8", errors="replace")


def capture_licitacion_from_url(
    url: str | None,
    *,
    fetcher: Callable[[str], str] | None = None,
    profile_url: str | None = None,
) -> dict[str, object]:
    safe_url = validate_capture_url(url)
    safe_profile_url = validate_capture_url(profile_url) if profile_url else None
    platform = detect_platform_from_url(safe_url) or detect_platform_from_url(safe_profile_url)
    if platform != "PLACE":
        raise UnsupportedPlatform("Captura automática no disponible para esta plataforma.")
    response_text = fetcher(safe_url) if fetcher else fetch_capture_html(safe_url)
    if _looks_like_xml(response_text):
        return parse_place_document_xml(response_text, safe_url, profile_url=safe_profile_url)
    return parse_place_detail_html(response_text, safe_url, profile_url=safe_profile_url)
