from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


PARSER_VERSION = "infonalia-fail-closed-v1"
REPRESENTATION_HTML = "html"
REPRESENTATION_TEXT = "text"

REQUIRED_FIELDS = (
    "ref_infonalia",
    "expediente",
    "organismo",
    "resumen_objeto",
    "provincia_ejecucion",
    "presupuesto_texto",
    "plazo_presentacion_texto",
)

COMPARISON_FIELDS = REQUIRED_FIELDS + (
    "url_anuncio_infonalia",
    "url_perfil_contratante",
    "fuente_texto",
)


def normalize_space(value: object) -> str:
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_label(value: object) -> str:
    text = normalize_space(value).strip().rstrip(":").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "ref_infonalia": ("Ref. Infonalia", "Ref Infonalia"),
    "expediente": ("Nº Expediente", "N° Expediente", "N. Expediente", "N Expediente", "Expediente"),
    "organismo": ("Organismo",),
    "resumen_objeto": ("Resumen del Objeto", "Objeto del contrato", "Objeto"),
    "provincia_ejecucion": ("Provincia de Ejecución", "Provincia"),
    "presupuesto_texto": ("Presupuesto",),
    "plazo_presentacion_texto": ("Plazo Presentación", "Plazo de Presentación"),
    "url_anuncio_infonalia": ("Ver el texto íntegro del anuncio", "Ver el texto integro del anuncio"),
    "url_perfil_contratante": ("Perfil del Contratante (Pliegos)", "Perfil del Contratante"),
}

NORMALIZED_LABELS: dict[str, str] = {
    normalize_label(label): field_name
    for field_name, labels in FIELD_LABELS.items()
    for label in labels
}

SOURCE_LABEL_RE = re.compile(
    r"^informaci[oó]n\s+extra[ií]da\s+del(?:\s*:\s*|\s+)?(.*)$",
    re.IGNORECASE,
)
SEPARATOR_RE = re.compile(r"^_{20,}$")
KNOWN_REF_RE = re.compile(r"^\d{10}$")
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
ANGLE_URL_RE = re.compile(r"<\s*(https?://[^>\s]+)\s*>", re.IGNORECASE)
HTTP_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
WWW_URL_RE = re.compile(r"\bwww\.[^\s<>]+", re.IGNORECASE)


@dataclass(frozen=True)
class ParseIssue:
    code: str
    message: str
    representation: str
    severity: str = "error"
    ordinal: int | None = None
    ref_infonalia: str = ""
    field_name: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity == "error"


@dataclass
class CanonicalBlock:
    ordinal: int
    representation: str
    ref_infonalia: str = ""
    expediente: str = ""
    organismo: str = ""
    resumen_objeto: str = ""
    provincia_ejecucion: str = ""
    presupuesto_texto: str = ""
    plazo_presentacion_texto: str = ""
    plazo_presentacion_fecha: str = ""
    url_anuncio_infonalia: str = ""
    url_perfil_contratante: str = ""
    fuente_texto: str = ""
    present_fields: tuple[str, ...] = ()
    issues: list[ParseIssue] = field(default_factory=list)
    warnings: list[ParseIssue] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(issue.code in {"conflicting_field", "duplicate_ref_in_message"} for issue in self.issues):
            return "conflict"
        return "quarantined" if self.issues else "valid"

    def comparison_payload(self) -> dict[str, str]:
        return {field_name: comparison_value(field_name, getattr(self, field_name)) for field_name in COMPARISON_FIELDS}


@dataclass
class RepresentationParse:
    representation: str
    supplied: bool
    marker_count: int
    blocks: list[CanonicalBlock]
    issues: list[ParseIssue] = field(default_factory=list)

    @property
    def valid_blocks(self) -> list[CanonicalBlock]:
        return [block for block in self.blocks if block.status == "valid"]

    @property
    def references(self) -> list[str]:
        return [block.ref_infonalia for block in self.blocks]


@dataclass
class ReconciledMessage:
    parser_version: str
    message_id: str
    content_hash: str
    text: RepresentationParse
    html: RepresentationParse
    canonical_blocks: list[CanonicalBlock]
    issues: list[ParseIssue] = field(default_factory=list)
    warnings: list[ParseIssue] = field(default_factory=list)
    reconciliation_status: str = "failed"
    safe_to_persist: bool = False

    @property
    def detected_count(self) -> int:
        return max(self.text.marker_count, self.html.marker_count)

    @property
    def conflict_count(self) -> int:
        return sum(block.status == "conflict" for block in self.canonical_blocks)

    @property
    def quarantine_count(self) -> int:
        return sum(block.status == "quarantined" for block in self.canonical_blocks)

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "parser_version": self.parser_version,
            "message_id": self.message_id,
            "content_hash": self.content_hash,
            "detected_html": self.html.marker_count,
            "detected_text": self.text.marker_count,
            "canonical_count": len(self.canonical_blocks),
            "references": [block.ref_infonalia for block in self.canonical_blocks],
            "conflicts": self.conflict_count,
            "quarantine": self.quarantine_count,
            "reconciliation_status": self.reconciliation_status,
            "safe_to_persist": self.safe_to_persist,
            "issues": [asdict(issue) for issue in self.issues],
            "warnings": [asdict(issue) for issue in self.warnings],
        }


@dataclass
class _RawBlock:
    ordinal: int
    representation: str
    occurrences: dict[str, list[str]] = field(default_factory=dict)

    def begin_occurrence(self, field_name: str, value: str) -> int:
        values = self.occurrences.setdefault(field_name, [])
        values.append(normalize_space(value))
        return len(values) - 1

    def append_continuation(self, field_name: str, occurrence_index: int, value: str) -> None:
        values = self.occurrences[field_name]
        current = normalize_space(values[occurrence_index])
        continuation = normalize_space(value)
        values[occurrence_index] = normalize_space(f"{current} {continuation}")


def _split_label_and_value(line: str) -> tuple[str, str] | None:
    text = normalize_space(line)
    if not text:
        return None
    source_match = SOURCE_LABEL_RE.match(text)
    if source_match:
        return "fuente_texto", normalize_space(source_match.group(1))
    if ":" in text:
        raw_label, value = text.split(":", 1)
        field_name = NORMALIZED_LABELS.get(normalize_label(raw_label))
        if field_name:
            return field_name, normalize_space(value)
        return None
    field_name = NORMALIZED_LABELS.get(normalize_label(text))
    if field_name:
        return field_name, ""
    return None


def _recognize_at(lines: list[str], index: int) -> tuple[str, str, int] | None:
    direct = _split_label_and_value(lines[index])
    if direct:
        return direct[0], direct[1], 1
    for width in range(2, min(4, len(lines) - index) + 1):
        combined = normalize_space(" ".join(lines[index : index + width]))
        recognized = _split_label_and_value(combined)
        if recognized and not recognized[1]:
            return recognized[0], "", width
    return None


def _plain_lines(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [normalize_space(line) for line in normalized.split("\n") if normalize_space(line)]


def _html_lines(html: str) -> list[str]:
    if not normalize_space(html):
        return []
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    for anchor in soup.find_all("a"):
        href = normalize_space(anchor.get("href"))
        visible = normalize_space(anchor.get_text(" ", strip=True))
        if href and href.lower().startswith(("http://", "https://", "//")):
            anchor.replace_with(normalize_space(f"{visible} <{href}>"))
    return [normalize_space(line) for line in soup.get_text("\n").splitlines() if normalize_space(line)]


def _build_raw_blocks(lines: list[str], representation: str) -> tuple[int, list[_RawBlock]]:
    blocks: list[_RawBlock] = []
    current: _RawBlock | None = None
    current_field = ""
    current_occurrence = -1
    marker_count = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if SEPARATOR_RE.fullmatch(line):
            current_field = ""
            current_occurrence = -1
            index += 1
            continue
        recognized = _recognize_at(lines, index)
        if recognized:
            field_name, value, consumed = recognized
            if field_name == "ref_infonalia":
                marker_count += 1
                current = _RawBlock(ordinal=marker_count, representation=representation)
                blocks.append(current)
            if current is not None:
                current_field = field_name
                current_occurrence = current.begin_occurrence(field_name, value)
            index += consumed
            continue
        if current is not None and current_field:
            current.append_continuation(current_field, current_occurrence, line)
        index += 1
    return marker_count, blocks


def _field_issue(
    *,
    code: str,
    message: str,
    raw: _RawBlock,
    field_name: str,
    ref: str,
    severity: str = "error",
) -> ParseIssue:
    return ParseIssue(
        code=code,
        message=message,
        representation=raw.representation,
        severity=severity,
        ordinal=raw.ordinal,
        ref_infonalia=ref,
        field_name=field_name,
    )


def _resolve_occurrences(raw: _RawBlock, field_name: str, ref: str) -> tuple[str, list[ParseIssue], list[ParseIssue]]:
    occurrences = raw.occurrences.get(field_name, [])
    issues: list[ParseIssue] = []
    warnings: list[ParseIssue] = []
    if not occurrences:
        issues.append(
            _field_issue(
                code="missing_required_field" if field_name in REQUIRED_FIELDS else "missing_field",
                message=f"No aparece la etiqueta obligatoria {field_name}.",
                raw=raw,
                field_name=field_name,
                ref=ref,
            )
        )
        return "", issues, warnings
    nonempty = [normalize_space(value) for value in occurrences if normalize_space(value)]
    if not nonempty:
        issues.append(
            _field_issue(
                code="empty_required_field" if field_name in REQUIRED_FIELDS else "empty_field",
                message=f"La etiqueta {field_name} está presente sin valor.",
                raw=raw,
                field_name=field_name,
                ref=ref,
            )
        )
        return "", issues, warnings
    normalized_values = {comparison_value(field_name, value) for value in nonempty}
    if len(normalized_values) > 1:
        issues.append(
            _field_issue(
                code="conflicting_field",
                message=f"La etiqueta {field_name} contiene valores diferentes.",
                raw=raw,
                field_name=field_name,
                ref=ref,
            )
        )
    elif len(occurrences) > 1:
        severity = "error" if len(nonempty) != len(occurrences) else "warning"
        target = issues if severity == "error" else warnings
        target.append(
            _field_issue(
                code="duplicate_empty_value" if severity == "error" else "duplicate_same_value",
                message=(
                    f"La etiqueta {field_name} se repite con un valor vacío."
                    if severity == "error"
                    else f"La etiqueta {field_name} se repite con el mismo valor."
                ),
                raw=raw,
                field_name=field_name,
                ref=ref,
                severity=severity,
            )
        )
    return nonempty[0], issues, warnings


def _parse_date_from_text(value: str) -> str:
    match = DATE_RE.search(value or "")
    if not match:
        return ""
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return ""


def normalize_url(value: object) -> str:
    text = normalize_space(value)
    match = ANGLE_URL_RE.search(text) or HTTP_URL_RE.search(text) or WWW_URL_RE.search(text)
    url = normalize_space(match.group(1) if match and match.lastindex else match.group(0) if match else text).strip("<>")
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.lower().startswith("www."):
        url = "https://" + url
    elif not re.match(r"(?i)^https?://", url) and "." in url.split("/", 1)[0]:
        url = "https://" + url
    try:
        split = urlsplit(url)
    except ValueError:
        return url
    if split.scheme.lower() not in {"http", "https"}:
        return url
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), split.path, split.query, split.fragment))


def comparison_value(field_name: str, value: object) -> str:
    if field_name in {"url_anuncio_infonalia", "url_perfil_contratante"}:
        return normalize_url(value)
    if field_name == "fuente_texto":
        text = normalize_space(value)
        match = SOURCE_LABEL_RE.match(text)
        if match:
            text = normalize_space(match.group(1))
        return text.casefold()
    return normalize_space(value).casefold()


def _canonicalize_raw_block(raw: _RawBlock, *, enforce_ref_format: bool) -> CanonicalBlock:
    values: dict[str, str] = {}
    issues: list[ParseIssue] = []
    warnings: list[ParseIssue] = []
    ref_values = raw.occurrences.get("ref_infonalia", [])
    ref_hint = next((normalize_space(value) for value in ref_values if normalize_space(value)), "")
    for field_name in REQUIRED_FIELDS + ("url_anuncio_infonalia", "url_perfil_contratante"):
        value, field_issues, field_warnings = _resolve_occurrences(raw, field_name, ref_hint)
        values[field_name] = value
        issues.extend(field_issues)
        warnings.extend(field_warnings)
    source_values = raw.occurrences.get("fuente_texto", [])
    if source_values:
        source, source_issues, source_warnings = _resolve_occurrences(raw, "fuente_texto", ref_hint)
        values["fuente_texto"] = source
        issues.extend(source_issues)
        warnings.extend(source_warnings)
    else:
        values["fuente_texto"] = ""

    ref = normalize_space(values.get("ref_infonalia"))
    if enforce_ref_format and ref and not KNOWN_REF_RE.fullmatch(ref):
        issues.append(
            _field_issue(
                code="unknown_ref_format",
                message=f"La referencia Infonalia {ref!r} no cumple el formato conocido de diez dígitos.",
                raw=raw,
                field_name="ref_infonalia",
                ref=ref,
            )
        )

    pdf_url = normalize_url(values.get("url_anuncio_infonalia"))
    if ref and pdf_url:
        filename_match = re.search(r"/(\d+)\.pdf(?:$|[?#])", pdf_url, re.IGNORECASE)
        if filename_match and filename_match.group(1) != ref:
            issues.append(
                _field_issue(
                    code="pdf_ref_mismatch",
                    message=f"El PDF enlazado corresponde a {filename_match.group(1)} y el bloque declara {ref}.",
                    raw=raw,
                    field_name="url_anuncio_infonalia",
                    ref=ref,
                )
            )

    return CanonicalBlock(
        ordinal=raw.ordinal,
        representation=raw.representation,
        ref_infonalia=ref,
        expediente=normalize_space(values.get("expediente")),
        organismo=normalize_space(values.get("organismo")),
        resumen_objeto=normalize_space(values.get("resumen_objeto")),
        provincia_ejecucion=normalize_space(values.get("provincia_ejecucion")),
        presupuesto_texto=normalize_space(values.get("presupuesto_texto")),
        plazo_presentacion_texto=normalize_space(values.get("plazo_presentacion_texto")),
        plazo_presentacion_fecha=_parse_date_from_text(values.get("plazo_presentacion_texto", "")),
        url_anuncio_infonalia=pdf_url,
        url_perfil_contratante=normalize_url(values.get("url_perfil_contratante")),
        fuente_texto=normalize_space(values.get("fuente_texto")),
        present_fields=tuple(sorted(raw.occurrences)),
        issues=issues,
        warnings=warnings,
    )


def parse_representation(text: str, *, representation: str, enforce_ref_format: bool = True) -> RepresentationParse:
    supplied = bool(normalize_space(text))
    lines = _html_lines(text) if representation == REPRESENTATION_HTML else _plain_lines(text)
    marker_count, raw_blocks = _build_raw_blocks(lines, representation)
    blocks = [_canonicalize_raw_block(raw, enforce_ref_format=enforce_ref_format) for raw in raw_blocks]
    issues: list[ParseIssue] = []
    if supplied and marker_count == 0:
        issues.append(
            ParseIssue(
                code="zero_blocks",
                message=f"La representación {representation} no contiene ningún bloque Ref. Infonalia.",
                representation=representation,
            )
        )
    if marker_count != len(blocks):
        issues.append(
            ParseIssue(
                code="unaccounted_marker",
                message=f"Se detectaron {marker_count} marcadores y se construyeron {len(blocks)} bloques.",
                representation=representation,
            )
        )
    seen: dict[str, int] = {}
    for block in blocks:
        if block.ref_infonalia and block.ref_infonalia in seen:
            issue = ParseIssue(
                code="duplicate_ref_in_message",
                message=(
                    f"La referencia {block.ref_infonalia} se repite en los bloques "
                    f"{seen[block.ref_infonalia]} y {block.ordinal}."
                ),
                representation=representation,
                ordinal=block.ordinal,
                ref_infonalia=block.ref_infonalia,
                field_name="ref_infonalia",
            )
            block.issues.append(issue)
            issues.append(issue)
        elif block.ref_infonalia:
            seen[block.ref_infonalia] = block.ordinal
    return RepresentationParse(
        representation=representation,
        supplied=supplied,
        marker_count=marker_count,
        blocks=blocks,
        issues=issues,
    )


def _content_hash(plain_text: str, html_text: str) -> str:
    payload = json.dumps(
        {
            "plain": normalize_space(plain_text),
            "html": normalize_space(html_text),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reconciliation_issue(code: str, message: str) -> ParseIssue:
    return ParseIssue(code=code, message=message, representation="reconciliation")


def reconcile_message(
    *,
    plain_text: str,
    html_text: str,
    message_id: str = "",
    require_both: bool = True,
    enforce_ref_format: bool = True,
) -> ReconciledMessage:
    text_result = parse_representation(
        plain_text,
        representation=REPRESENTATION_TEXT,
        enforce_ref_format=enforce_ref_format,
    )
    html_result = parse_representation(
        html_text,
        representation=REPRESENTATION_HTML,
        enforce_ref_format=enforce_ref_format,
    )
    issues: list[ParseIssue] = []
    warnings: list[ParseIssue] = []
    for result in (text_result, html_result):
        issues.extend(result.issues)
        for block in result.blocks:
            issues.extend(block.issues)
            warnings.extend(block.warnings)

    supplied = [result for result in (text_result, html_result) if result.supplied]
    if not supplied:
        issues.append(_reconciliation_issue("missing_all_representations", "El mensaje no contiene texto ni HTML utilizable."))
        canonical: list[CanonicalBlock] = []
    elif require_both and len(supplied) != 2:
        missing = REPRESENTATION_HTML if not html_result.supplied else REPRESENTATION_TEXT
        issues.append(
            _reconciliation_issue(
                "missing_representation",
                f"Falta la representación {missing}; el modo estricto exige HTML y texto plano.",
            )
        )
        canonical = list(supplied[0].blocks)
    elif len(supplied) == 1:
        canonical = list(supplied[0].blocks)
        warnings.append(
            ParseIssue(
                code="single_representation_accepted",
                message=f"Solo se recibió la representación {supplied[0].representation}.",
                representation="reconciliation",
                severity="warning",
            )
        )
    else:
        # On disagreement we retain the longest observed representation only for
        # quarantine/audit accounting. It is never selected for persistence.
        canonical = list(
            html_result.blocks
            if html_result.marker_count > text_result.marker_count
            else text_result.blocks
        )
        if text_result.marker_count != html_result.marker_count:
            issues.append(
                _reconciliation_issue(
                    "block_count_mismatch",
                    f"Texto={text_result.marker_count} bloques; HTML={html_result.marker_count} bloques.",
                )
            )
        if text_result.references != html_result.references:
            missing_in_text = [ref for ref in html_result.references if ref not in text_result.references]
            missing_in_html = [ref for ref in text_result.references if ref not in html_result.references]
            issues.append(
                _reconciliation_issue(
                    "reference_order_mismatch",
                    "Las referencias u orden no coinciden. "
                    f"Solo HTML={missing_in_text}; solo texto={missing_in_html}; "
                    f"texto={text_result.references}; HTML={html_result.references}.",
                )
            )
        for ordinal, (text_block, html_block) in enumerate(zip(text_result.blocks, html_result.blocks), start=1):
            for field_name in COMPARISON_FIELDS:
                text_value = comparison_value(field_name, getattr(text_block, field_name))
                html_value = comparison_value(field_name, getattr(html_block, field_name))
                if text_value != html_value:
                    issues.append(
                        ParseIssue(
                            code="field_mismatch",
                            message=(
                                f"El campo {field_name} del bloque {ordinal} difiere entre texto "
                                f"({getattr(text_block, field_name)!r}) y HTML ({getattr(html_block, field_name)!r})."
                            ),
                            representation="reconciliation",
                            ordinal=ordinal,
                            ref_infonalia=text_block.ref_infonalia or html_block.ref_infonalia,
                            field_name=field_name,
                        )
                    )

    blocking = any(issue.blocking for issue in issues)
    detected = max(text_result.marker_count, html_result.marker_count)
    accounted = len(canonical)
    if detected != accounted:
        issues.append(
            _reconciliation_issue(
                "mathematical_reconciliation_failed",
                f"Detectados={detected}; bloques canónicos={accounted}.",
            )
        )
        blocking = True
    if detected == 0:
        issues.append(_reconciliation_issue("candidate_without_blocks", "El correo candidato no contiene bloques."))
        blocking = True
    if any(block.status != "valid" for block in canonical):
        blocking = True

    return ReconciledMessage(
        parser_version=PARSER_VERSION,
        message_id=normalize_space(message_id),
        content_hash=_content_hash(plain_text, html_text),
        text=text_result,
        html=html_result,
        canonical_blocks=canonical,
        issues=issues,
        warnings=warnings,
        reconciliation_status="reconciled" if not blocking else "failed",
        safe_to_persist=not blocking,
    )


def parse_money_value(value: object) -> float | None:
    text = normalize_space(value)
    match = re.search(r"[-+]?\d[\d.,]*", text)
    if not match:
        return None
    number = match.group(0)
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def block_to_legacy_item(block: CanonicalBlock) -> dict[str, object]:
    return {
        "ref_infonalia": block.ref_infonalia,
        "expediente": block.expediente,
        "organismo": block.organismo,
        "resumen_objeto": block.resumen_objeto,
        "provincia_ejecucion": block.provincia_ejecucion,
        "presupuesto": parse_money_value(block.presupuesto_texto),
        "presupuesto_texto": block.presupuesto_texto,
        "plazo_presentacion_texto": block.plazo_presentacion_texto,
        "plazo_presentacion_fecha": block.plazo_presentacion_fecha,
        "url_anuncio_infonalia": block.url_anuncio_infonalia,
        "url_perfil_contratante": block.url_perfil_contratante,
        "fuente_texto": block.fuente_texto,
        "plataforma_origen": "",
        "fecha_fuente": "",
        "bloque_texto": "",
    }


def legacy_items(result: ReconciledMessage, *, require_safe: bool = False) -> list[dict[str, object]]:
    if require_safe and not result.safe_to_persist:
        return []
    return [block_to_legacy_item(block) for block in result.canonical_blocks]


def issue_messages(issues: Iterable[ParseIssue]) -> list[str]:
    return [issue.message for issue in issues]
