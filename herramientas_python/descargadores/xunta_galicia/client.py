"""Validación de fichas y extracción del inventario público de Xunta."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag


PLATFORM = "XUNTA_DE_GALICIA"
ALLOWED_HOST = "contratosdegalicia.gal"
DETAIL_PATH = "/licitacion"
DOWNLOAD_PATH = "/descargaG"
DOWNLOAD_CALL_RE = re.compile(r"^javascript:(mostrarTabla[A-Za-z]*)\(([^()]*)\)$")
ARGUMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DATE_RE = re.compile(r"\b\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}(?::\d{2})?\b")
EXTENSION_RE = re.compile(r"Formato\s*\.\s*([A-Za-z0-9]+)", re.IGNORECASE)
SIZE_RE = re.compile(r"\(([0-9]+(?:[.,][0-9]+)?)\s*(B|KB|MB|GB)\)", re.IGNORECASE)


class XuntaParseError(ValueError):
    """La respuesta no es una ficha pública utilizable."""


class UnknownDownloadCall(XuntaParseError):
    """La plataforma expone una función documental todavía no conocida."""


@dataclass(frozen=True)
class DownloadDescriptor:
    call: str
    function: str
    arguments: tuple[str, ...]
    form_fields: tuple[tuple[str, str], ...]
    source_url: str
    title: str
    published_at: str = ""
    remote_status: str = ""
    extension: str = ""
    declared_size: int = 0
    section: str = ""

    @property
    def fingerprint(self) -> str:
        material = {
            "source_url": self.source_url,
            "title": self.title,
            "published_at": self.published_at,
            "remote_status": self.remote_status,
            "extension": self.extension,
            "declared_size": self.declared_size,
            "section": self.section,
        }
        raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TenderPage:
    tender_id: str
    source_url: str
    general_data: dict[str, object]
    relevant_dates: dict[str, str]
    documents: tuple[DownloadDescriptor, ...]
    complete: bool
    warnings: tuple[str, ...] = ()

    @property
    def inventory_fingerprint(self) -> str:
        material = [
            {"source_url": item.source_url, "fingerprint": item.fingerprint}
            for item in self.documents
        ]
        raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    if isinstance(value, Tag):
        value = value.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized(value: object) -> str:
    text = unicodedata.normalize("NFD", _text(value).casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def validate_detail_url(url: str) -> tuple[str, str]:
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.casefold().split(":", 1)[0]
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise XuntaParseError("La URL de Xunta debe usar HTTP o HTTPS.")
    if host != ALLOWED_HOST and not host.endswith(f".{ALLOWED_HOST}"):
        raise XuntaParseError("La URL no pertenece a Contratos Públicos de Galicia.")
    if parsed.path.rstrip("/").casefold() != DETAIL_PATH:
        raise XuntaParseError("La URL de Xunta no corresponde a una ficha de licitación.")
    tender_ids = [value.strip() for value in parse_qs(parsed.query).get("N", []) if value.strip()]
    if len(tender_ids) != 1 or not tender_ids[0].isdigit():
        raise XuntaParseError("La ficha de Xunta necesita un identificador N numérico.")
    canonical = urlunparse(("https", host, DETAIL_PATH, "", urlencode({"N": tender_ids[0]}), ""))
    return tender_ids[0], canonical


def _clean_arguments(raw_arguments: str) -> tuple[str, ...]:
    values = tuple(part.strip().strip("'\"") for part in raw_arguments.split(","))
    if not values or any(not value or not ARGUMENT_RE.fullmatch(value) for value in values):
        raise XuntaParseError("La llamada documental contiene argumentos no válidos.")
    return values


def _fields_for_call(function: str, values: tuple[str, ...]) -> dict[str, str]:
    if function == "mostrarTabla" and len(values) in {4, 5}:
        fields = dict(zip(("T", "F", "V", "N"), values[:4]))
        if len(values) == 5:
            fields["M"] = values[4]
        return fields
    if function == "mostrarTablaPub" and len(values) == 2:
        return {"T": values[0], "F": "0", "N": values[1]}
    if function == "mostrarTablaResolucionAdx" and len(values) == 3:
        return {"J": values[0], "L": values[1], "N": values[2]}
    if function == "mostrarTablaFormalizacion" and len(values) == 3:
        return {"K2": values[0], "L": values[1], "N": values[2]}
    if function == "mostrarTablaFicheroAnexo" and len(values) == 2:
        return {"N": values[0], "D": values[1]}
    if function == "mostrarTablaFicheroAnexoContrato" and len(values) == 2:
        return {"N": values[0], "DC": values[1]}
    if function == "mostrarTablaFicheroAnexoEjecucion" and len(values) == 2:
        return {"N": values[0], "DE": values[1]}
    raise UnknownDownloadCall(f"Función documental no admitida: {function}/{len(values)}.")


def parse_download_call(call: str, page_url: str) -> tuple[str, tuple[str, ...], tuple[tuple[str, str], ...], str]:
    match = DOWNLOAD_CALL_RE.fullmatch(_text(call))
    if not match:
        raise XuntaParseError("Enlace documental de Xunta no reconocido.")
    function = match.group(1)
    values = _clean_arguments(match.group(2))
    fields = _fields_for_call(function, values)
    parsed = urlparse(page_url)
    source_url = urlunparse(
        (
            "https",
            parsed.netloc.casefold(),
            DOWNLOAD_PATH,
            "",
            urlencode(sorted(fields.items())),
            "",
        )
    )
    return function, values, tuple(sorted(fields.items())), source_url


def _declared_size(text: str) -> int:
    match = SIZE_RE.search(text)
    if not match:
        return 0
    value = float(match.group(1).replace(",", "."))
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return int(value * multipliers[match.group(2).upper()])


def _section_id(anchor: Tag) -> str:
    container = anchor.find_parent(
        lambda tag: isinstance(tag, Tag)
        and bool(tag.get("id"))
        and str(tag.get("id")).startswith(("collapse", "consulta-"))
    )
    return _text(container.get("id")) if isinstance(container, Tag) else ""


def _descriptor_from_anchor(anchor: Tag, page_url: str) -> DownloadDescriptor:
    call = _text(anchor.get("href"))
    function, arguments, fields, source_url = parse_download_call(call, page_url)
    row = anchor.find_parent("tr")
    cells = row.find_all(["td", "th"], recursive=False) if isinstance(row, Tag) else []
    row_text = _text(row or anchor)
    title = _text(cells[0]) if cells else _text(anchor)
    if not title or EXTENSION_RE.fullmatch(title):
        title = _text(anchor)
    published_at = _text(cells[1]) if len(cells) > 1 else ""
    if not published_at:
        date_match = DATE_RE.search(row_text)
        published_at = date_match.group(0) if date_match else ""
    remote_status = _text(cells[2]) if len(cells) > 2 else ""
    extension_match = EXTENSION_RE.search(row_text)
    extension = f".{extension_match.group(1).lower()}" if extension_match else ""
    return DownloadDescriptor(
        call=call,
        function=function,
        arguments=arguments,
        form_fields=fields,
        source_url=source_url,
        title=title,
        published_at=published_at,
        remote_status=remote_status,
        extension=extension,
        declared_size=_declared_size(row_text),
        section=_section_id(anchor),
    )


def _definition_values(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for term in soup.select("dt"):
        definition = term.find_next_sibling("dd")
        key = _normalized(term)
        value = _text(definition)
        if key and value and key not in values:
            values[key] = value
    return values


def _first(values: dict[str, str], aliases: Iterable[str]) -> str:
    for alias in aliases:
        value = values.get(_normalized(alias), "")
        if value:
            return value
    return ""


def _extract_metadata(soup: BeautifulSoup) -> tuple[dict[str, object], dict[str, str]]:
    values = _definition_values(soup)
    authority = soup.select_one("#consulta-datos-xerais .organismo .logo-texto a")
    status = soup.select_one("#consulta-datos-xerais .titulo em")
    general_data: dict[str, object] = {
        "expediente": _first(values, ("Referencia",)),
        "title": _first(values, ("Obxecto", "Objeto")),
        "organismo": _text(authority),
        "procedure": _first(values, ("Tipo de procedemento", "Tipo de procedimiento")),
        "contract_type": _first(values, ("Tipo de contrato",)),
        "presupuesto": _first(
            values,
            ("Orzamento base de licitación", "Presupuesto base de licitación"),
        ),
        "valor_estimado": _first(values, ("Valor estimado",)),
        "lots": _first(values, ("Nº lotes", "Número de lotes")),
        "tender_status": _text(status),
    }
    general_data = {key: value for key, value in general_data.items() if _text(value)}
    deadline = _first(values, ("Data e hora límite", "Fecha y hora límite"))
    return general_data, ({"fecha_limite": deadline} if deadline else {})


def parse_tender_page(content: bytes | str | BeautifulSoup, page_url: str) -> TenderPage:
    tender_id, canonical_url = validate_detail_url(page_url)
    soup = content if isinstance(content, BeautifulSoup) else BeautifulSoup(content, "html.parser")
    title = _text(soup.title)
    if tender_id not in title or not soup.select_one("#consulta-datos-xerais"):
        raise XuntaParseError("La respuesta no contiene la ficha de Xunta solicitada.")

    warnings: list[str] = []
    complete = True
    documents_by_call: dict[str, DownloadDescriptor] = {}
    for anchor in soup.select('a[href^="javascript:mostrarTabla"]'):
        call = _text(anchor.get("href"))
        try:
            descriptor = _descriptor_from_anchor(anchor, canonical_url)
        except UnknownDownloadCall as exc:
            complete = False
            warning = str(exc)
            if warning not in warnings:
                warnings.append(warning)
            continue
        except XuntaParseError as exc:
            complete = False
            warning = str(exc)
            if warning not in warnings:
                warnings.append(warning)
            continue
        existing = documents_by_call.get(call)
        if existing is None:
            documents_by_call[call] = descriptor
        elif existing.fingerprint != descriptor.fingerprint:
            complete = False
            warnings.append(f"Metadatos contradictorios para {call}.")

    form = soup.select_one("#formDescargaG")
    action = _text(form.get("action")) if isinstance(form, Tag) else ""
    if documents_by_call and (not form or "descargaG" not in action):
        complete = False
        warnings.append("No se encontró el formulario oficial de descarga de Xunta.")

    general_data, relevant_dates = _extract_metadata(soup)
    return TenderPage(
        tender_id=tender_id,
        source_url=canonical_url,
        general_data=general_data,
        relevant_dates=relevant_dates,
        documents=tuple(documents_by_call.values()),
        complete=complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
