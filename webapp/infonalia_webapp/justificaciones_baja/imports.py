"""Pure, deterministic and bounded product imports for one justification lot.

The importer never evaluates formulas, writes files or mutates the economic
domain.  Its output contains canonical decimal strings that an application
service can subsequently turn into :class:`Product` instances.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from .calculations import canonical_decimal, format_spanish_amount


MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2_000
MAX_COMPRESSION_RATIO = 2_000
MAX_IMPORT_ROWS = 5_000
MAX_IMPORT_COLUMNS = 256
MAX_PREVIEW_ROWS = 50
MAX_PREVIEW_COLUMNS = 30
MAX_CELL_CHARACTERS = 32_767
MAX_NUMERIC_CHARACTERS = 128

REQUIRED_MAPPING_FIELDS = ("name", "quantity", "offered_unit_price")
OPTIONAL_MAPPING_FIELDS = ("characteristics", "offered_amount")
SUPPORTED_MAPPING_FIELDS = frozenset((*REQUIRED_MAPPING_FIELDS, *OPTIONAL_MAPPING_FIELDS))

_REQUIRED_XLSX_PARTS = frozenset(
    {
        "[content_types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
    }
)
_FORBIDDEN_XLSX_PARTS = frozenset(
    {
        "xl/vbaproject.bin",
        "xl/connections.xml",
    }
)
_FORBIDDEN_XLSX_PREFIXES = (
    "xl/embeddings/",
    "xl/externallinks/",
)
_FORMULA_PREFIX = "="
_SPANISH_GROUPED_INTEGER = re.compile(r"[-+]?[1-9]\d{0,2}(?:\.\d{3})+")
_CANONICAL_DECIMAL = re.compile(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)")
_SPANISH_DECIMAL = re.compile(r"[-+]?(?:\d{1,3}(?:\.\d{3})+|\d+),\d+")


class ProductImportError(ValueError):
    """Raised when an import payload or workbook is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class ImportIssue:
    row_number: int
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "row_number": self.row_number,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


def inspect_xlsx(
    content: bytes,
    *,
    filename: str | None = None,
    sheet_name: str | None = None,
    preview_rows: int = 20,
) -> dict[str, Any]:
    """Inspect sheet names and raw rows without importing products."""

    return preview_xlsx(
        content,
        filename=filename,
        sheet_name=sheet_name,
        preview_rows=preview_rows,
    )


def preview_xlsx(
    content: bytes,
    *,
    filename: str | None = None,
    sheet_name: str | None = None,
    start_row: int = 1,
    mapping: Mapping[str, object] | None = None,
    preview_rows: int = 20,
) -> dict[str, Any]:
    """Return a bounded XLSX preview and, optionally, normalized products."""

    start = _positive_row(start_row)
    preview_limit = _preview_limit(preview_rows)
    _validate_xlsx_filename(filename)
    payload = _bytes_payload(content)
    _inspect_xlsx_archive(payload)
    source_sha256 = hashlib.sha256(payload).hexdigest()

    try:
        load_workbook = importlib.import_module("openpyxl").load_workbook
        workbook = load_workbook(
            io.BytesIO(payload),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
    except Exception as exc:
        raise ProductImportError("No se ha podido abrir el Excel.") from exc

    try:
        sheets = tuple(workbook.sheetnames)
        if not sheets:
            raise ProductImportError("El Excel no contiene hojas.")
        selected_name = _selected_sheet_name(sheet_name, sheets)
        sheet = workbook[selected_name]
        rows, column_count = _read_worksheet_rows(sheet, selected_name)
    finally:
        workbook.close()

    response: dict[str, Any] = {
        "format": "xlsx",
        "source_sha256": source_sha256,
        "sheets": list(sheets),
        "sheet": selected_name,
        "rows": _raw_preview(rows, maximum=preview_limit),
        "row_count": len(rows),
        "column_count": column_count,
        "preview_rows": min(preview_limit, len(rows)),
        "preview_columns": min(column_count, MAX_PREVIEW_COLUMNS),
        "start_row": start,
    }
    if mapping is not None:
        response.update(
            parse_product_rows(
                rows,
                mapping=mapping,
                start_row=start,
                source_key=f"xlsx:{source_sha256}:{selected_name}",
            )
        )
    return response


def preview_tabular(
    text: str,
    *,
    start_row: int = 1,
    mapping: Mapping[str, object] | None = None,
    preview_rows: int = 20,
) -> dict[str, Any]:
    """Preview tab-separated clipboard text without spreadsheet evaluation."""

    start = _positive_row(start_row)
    preview_limit = _preview_limit(preview_rows)
    if not isinstance(text, str) or not text.strip():
        raise ProductImportError("No hay contenido tabular para importar.")
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_IMPORT_BYTES:
        raise ProductImportError("El contenido pegado supera el tamaño permitido.")
    if "\x00" in text:
        raise ProductImportError("El contenido pegado contiene caracteres no permitidos.")

    rows = [tuple(cell.strip() for cell in line.split("\t")) for line in text.splitlines()]
    _validate_row_shape(rows, source="El contenido pegado")
    _reject_formula_text(rows, source="el contenido pegado")
    source_sha256 = hashlib.sha256(encoded).hexdigest()
    column_count = max((len(row) for row in rows), default=0)
    response: dict[str, Any] = {
        "format": "tabular",
        "source_sha256": source_sha256,
        "rows": _raw_preview(rows, maximum=preview_limit),
        "row_count": len(rows),
        "column_count": column_count,
        "preview_rows": min(preview_limit, len(rows)),
        "preview_columns": min(column_count, MAX_PREVIEW_COLUMNS),
        "start_row": start,
    }
    if mapping is not None:
        response.update(
            parse_product_rows(
                rows,
                mapping=mapping,
                start_row=start,
                source_key=f"tabular:{source_sha256}",
            )
        )
    return response


def parse_product_rows(
    rows: Sequence[Sequence[object]],
    *,
    mapping: Mapping[str, object],
    start_row: int,
    source_key: str,
) -> dict[str, Any]:
    """Normalize mapped rows without calculating or generating product costs."""

    if isinstance(rows, (str, bytes, bytearray)):
        raise ProductImportError("Las filas de productos no tienen un formato válido.")
    _validate_row_shape(rows, source="La tabla")
    _reject_formula_text(rows, source="la tabla")
    normalized_mapping = _normalize_mapping(mapping)
    first_index = _positive_row(start_row) - 1
    stable_source = str(source_key or "").strip()
    if not stable_source:
        raise ProductImportError("El origen de la importación es obligatorio.")

    products: list[dict[str, Any]] = []
    issues: list[ImportIssue] = []
    ignored_rows: list[int] = []
    for index, row in enumerate(rows[first_index:], start=first_index):
        row_number = index + 1
        values = list(row)
        if _empty_row(values):
            ignored_rows.append(row_number)
            continue

        raw_name = _mapped_value(values, normalized_mapping["name"])
        if isinstance(raw_name, bool):
            issues.append(
                ImportIssue(row_number, "tipo_celda_no_admitido", "El producto no puede ser booleano.")
            )
            continue
        name = _cell_text(raw_name)
        if _looks_like_total(name):
            ignored_rows.append(row_number)
            continue
        if not name:
            issues.append(ImportIssue(row_number, "producto_ausente", "Falta el nombre del producto."))
            continue

        try:
            quantity = parse_decimal(
                _mapped_value(values, normalized_mapping["quantity"]),
                field="cantidad",
                integer_hint=True,
            )
            unit_price = parse_decimal(
                _mapped_value(values, normalized_mapping["offered_unit_price"]),
                field="precio ofertado",
            )
        except ProductImportError as exc:
            issues.append(ImportIssue(row_number, "decimal_invalido", str(exc)))
            continue
        if quantity < 0 or unit_price < 0:
            issues.append(
                ImportIssue(
                    row_number,
                    "valor_negativo",
                    "Cantidad y precio deben ser valores no negativos.",
                )
            )
            continue

        characteristics = ""
        if "characteristics" in normalized_mapping:
            raw_characteristics = _mapped_value(values, normalized_mapping["characteristics"])
            if isinstance(raw_characteristics, bool):
                issues.append(
                    ImportIssue(
                        row_number,
                        "tipo_celda_no_admitido",
                        "Las características no pueden ser booleanas.",
                    )
                )
                continue
            characteristics = _cell_text(raw_characteristics)

        calculated_amount = quantity * unit_price
        try:
            _ensure_decimal_within_limits(calculated_amount, field="importe calculado")
        except ProductImportError as exc:
            issues.append(ImportIssue(row_number, "decimal_invalido", str(exc)))
            continue
        amount_input: str | None = None
        amount_origin = "calculado"
        if "offered_amount" in normalized_mapping:
            supplied = _mapped_value(values, normalized_mapping["offered_amount"])
            if supplied not in (None, ""):
                if isinstance(supplied, bool):
                    issues.append(
                        ImportIssue(
                            row_number,
                            "tipo_celda_no_admitido",
                            "El importe ofertado no puede ser booleano.",
                        )
                    )
                    continue
                try:
                    supplied_amount = parse_decimal(supplied, field="importe ofertado")
                    if supplied_amount < 0:
                        raise ProductImportError("importe ofertado no puede ser negativo.")
                    amount_input = canonical_decimal(supplied_amount)
                    amount_origin = "aportado"
                    if supplied_amount != calculated_amount:
                        issues.append(
                            ImportIssue(
                                row_number,
                                "importe_no_coincide",
                                "El importe indicado no coincide con cantidad por precio; se conserva para revisión.",
                                severity="advertencia",
                            )
                        )
                except ProductImportError as exc:
                    issues.append(
                        ImportIssue(
                            row_number,
                            "importe_invalido",
                            str(exc),
                            severity="advertencia",
                        )
                    )

        line_id = _stable_line_id(stable_source, row_number)
        products.append(
            {
                "line_id": line_id,
                "name": name,
                "characteristics": characteristics,
                "quantity": canonical_decimal(quantity),
                "offered_unit_price": canonical_decimal(unit_price),
                "offered_amount_input": amount_input,
                "offered_amount_calculated": canonical_decimal(calculated_amount),
                "offered_amount_display": format_spanish_amount(calculated_amount),
                "offered_amount_origin": amount_origin,
                "applied_percentage": None,
                "applied_factor": None,
                "generated_unit_cost": None,
                "manual_unit_cost": None,
                "locked": False,
                "cost_origin": "sin_generar",
                "source_row": row_number,
            }
        )

    serialized_issues = [issue.to_dict() for issue in issues]
    return {
        "products": products,
        "issues": serialized_issues,
        "ignored_rows": ignored_rows,
        "can_confirm": bool(products) and not any(issue.severity == "error" for issue in issues),
        "mapping": normalized_mapping,
    }


def parse_decimal(value: object, *, field: str, integer_hint: bool = False) -> Decimal:
    """Parse an Excel scalar or Spanish/canonical decimal without using float arithmetic."""

    del integer_hint  # Kept for API compatibility; grouped integers are recognized for every field.
    if isinstance(value, bool) or value is None:
        raise ProductImportError(f"{field} no contiene un número válido.")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        result = Decimal(str(value))
    elif isinstance(value, str):
        text = _numeric_text(value, field=field)
        normalized = _normalize_numeric_text(text, field=field)
        try:
            result = Decimal(normalized)
        except InvalidOperation as exc:
            raise ProductImportError(f"{field} no contiene un decimal válido.") from exc
    else:
        raise ProductImportError(f"{field} no contiene un número válido.")

    if not result.is_finite():
        raise ProductImportError(f"{field} debe ser finito.")
    _ensure_decimal_within_limits(result, field=field)
    return result


def _ensure_decimal_within_limits(value: Decimal, *, field: str) -> None:
    decimal_tuple = value.as_tuple()
    exponent = decimal_tuple.exponent
    if not isinstance(exponent, int):
        raise ProductImportError(f"{field} debe ser finito.")
    digit_count = len(decimal_tuple.digits)
    if exponent >= 0:
        fixed_length = digit_count + exponent
    elif digit_count + exponent > 0:
        fixed_length = digit_count + 1
    else:
        fixed_length = 2 - exponent
    if decimal_tuple.sign:
        fixed_length += 1
    if fixed_length > MAX_NUMERIC_CHARACTERS:
        raise ProductImportError(f"{field} supera la precisión admitida.")


def _bytes_payload(content: object) -> bytes:
    if not isinstance(content, (bytes, bytearray, memoryview)):
        raise ProductImportError("El contenido del Excel debe recibirse como bytes.")
    payload = bytes(content)
    if not payload:
        raise ProductImportError("El Excel está vacío.")
    if len(payload) > MAX_IMPORT_BYTES:
        raise ProductImportError("El Excel supera el tamaño máximo permitido.")
    return payload


def _validate_xlsx_filename(filename: str | None) -> None:
    if filename is None:
        return
    clean = str(filename).strip()
    if not clean or clean in {".", ".."} or "\x00" in clean or "/" in clean or "\\" in clean:
        raise ProductImportError("El nombre del Excel no es válido.")
    if not clean.casefold().endswith(".xlsx"):
        raise ProductImportError("Solo se admiten ficheros XLSX sin macros.")


def _inspect_xlsx_archive(content: bytes) -> None:
    stream = io.BytesIO(content)
    if not zipfile.is_zipfile(stream):
        raise ProductImportError("El fichero no es un XLSX válido.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ProductImportError("El Excel contiene demasiadas partes internas.")
            names: set[str] = set()
            total_uncompressed = 0
            for member in members:
                normalized_name = _safe_archive_member_name(member.filename)
                folded_name = normalized_name.casefold()
                if folded_name in names:
                    raise ProductImportError("El Excel contiene partes internas duplicadas.")
                names.add(folded_name)
                if member.flag_bits & 0x1:
                    raise ProductImportError("No se admiten Excel cifrados.")
                if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise ProductImportError("Una parte interna del Excel supera el límite permitido.")
                total_uncompressed += member.file_size
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ProductImportError("El Excel descomprimido supera el límite permitido.")
                if member.file_size and not member.is_dir():
                    if member.compress_size <= 0:
                        raise ProductImportError("El Excel contiene una parte comprimida no válida.")
                    if member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                        raise ProductImportError("El Excel presenta una compresión no segura.")

            if not _REQUIRED_XLSX_PARTS <= names:
                raise ProductImportError("El fichero no contiene la estructura mínima de un XLSX.")
            if _FORBIDDEN_XLSX_PARTS & names or any(
                name.startswith(prefix) for name in names for prefix in _FORBIDDEN_XLSX_PREFIXES
            ):
                raise ProductImportError("El Excel contiene macros, conexiones o contenido incrustado no admitido.")
            if archive.testzip() is not None:
                raise ProductImportError("El Excel está corrupto.")
    except ProductImportError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ProductImportError("El fichero no es un XLSX válido.") from exc


def _safe_archive_member_name(value: str) -> str:
    if not value or "\x00" in value or "\\" in value or value.startswith("/"):
        raise ProductImportError("El Excel contiene una ruta interna no segura.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise ProductImportError("El Excel contiene una ruta interna no segura.")
    return "/".join(parts)


def _selected_sheet_name(sheet_name: str | None, sheets: Sequence[str]) -> str:
    if sheet_name is None or sheet_name == "":
        return sheets[0]
    if not isinstance(sheet_name, str):
        raise ProductImportError("La hoja seleccionada no es válida.")
    if sheet_name not in sheets:
        raise ProductImportError("La hoja seleccionada no existe.")
    return sheet_name


def _read_worksheet_rows(sheet: object, sheet_name: str) -> tuple[list[tuple[object, ...]], int]:
    max_row = int(getattr(sheet, "max_row", 0) or 0)
    max_column = int(getattr(sheet, "max_column", 0) or 0)
    if max_row > MAX_IMPORT_ROWS:
        raise ProductImportError("El Excel supera el máximo de filas permitido.")
    if max_column > MAX_IMPORT_COLUMNS:
        raise ProductImportError("El Excel supera el máximo de columnas permitido.")
    if max_row <= 0 or max_column <= 0:
        return [], 0

    rows: list[tuple[object, ...]] = []
    for row_number, cells in enumerate(
        sheet.iter_rows(min_row=1, max_row=max_row, max_col=max_column),
        start=1,
    ):
        values: list[object] = []
        for cell in cells:
            data_type = str(getattr(cell, "data_type", "") or "")
            coordinate = str(getattr(cell, "coordinate", "") or "")
            if data_type == "f":
                raise ProductImportError(
                    f"No se admiten fórmulas ({sheet_name}!{coordinate or row_number})."
                )
            if data_type == "e":
                raise ProductImportError(
                    f"No se admiten errores de Excel ({sheet_name}!{coordinate or row_number})."
                )
            value = getattr(cell, "value", None)
            _validate_cell_value(value)
            values.append(value)
        rows.append(tuple(values))

    while rows and _empty_row(rows[-1]):
        rows.pop()
    effective_columns = max((len(row) for row in rows), default=0)
    return rows, effective_columns


def _validate_cell_value(value: object) -> None:
    if isinstance(value, str):
        if len(value) > MAX_CELL_CHARACTERS:
            raise ProductImportError("El Excel contiene una celda de texto demasiado extensa.")
        if value.lstrip().startswith(_FORMULA_PREFIX):
            raise ProductImportError("No se admiten textos con sintaxis de fórmulas.")


def _validate_row_shape(rows: Sequence[Sequence[object]], *, source: str) -> None:
    if len(rows) > MAX_IMPORT_ROWS:
        raise ProductImportError(f"{source} supera el máximo de filas permitido.")
    for row in rows:
        if isinstance(row, (str, bytes, bytearray)):
            raise ProductImportError("Las filas deben contener una secuencia de celdas.")
        if len(row) > MAX_IMPORT_COLUMNS:
            raise ProductImportError(f"{source} supera el máximo de columnas permitido.")
        for value in row:
            _validate_cell_value(value)


def _reject_formula_text(rows: Iterable[Sequence[object]], *, source: str) -> None:
    for row_number, row in enumerate(rows, start=1):
        for column_number, value in enumerate(row, start=1):
            if isinstance(value, str) and value.lstrip().startswith(_FORMULA_PREFIX):
                raise ProductImportError(
                    f"No se admiten fórmulas en {source} (fila {row_number}, columna {column_number})."
                )


def _normalize_mapping(mapping: Mapping[str, object]) -> dict[str, int]:
    if not isinstance(mapping, Mapping):
        raise ProductImportError("El mapeo de columnas no es válido.")
    unknown = sorted(
        str(field)
        for field, value in mapping.items()
        if field not in SUPPORTED_MAPPING_FIELDS and value not in (None, "")
    )
    if unknown:
        raise ProductImportError(f"El mapeo contiene campos desconocidos: {', '.join(unknown)}.")

    result: dict[str, int] = {}
    for field in (*REQUIRED_MAPPING_FIELDS, *OPTIONAL_MAPPING_FIELDS):
        raw = mapping.get(field)
        if raw in (None, ""):
            continue
        if isinstance(raw, bool):
            raise ProductImportError("El mapeo de columnas no es válido.")
        if isinstance(raw, str) and raw.strip().isalpha():
            index = _column_letter_index(raw.strip())
        else:
            try:
                index = int(raw)
            except (TypeError, ValueError) as exc:
                raise ProductImportError("El mapeo de columnas no es válido.") from exc
        if index < 0 or index >= MAX_IMPORT_COLUMNS:
            raise ProductImportError("El índice de columna queda fuera del rango permitido.")
        result[field] = index

    missing = [field for field in REQUIRED_MAPPING_FIELDS if field not in result]
    if missing:
        raise ProductImportError(f"Faltan columnas obligatorias: {', '.join(missing)}.")
    reverse: dict[int, list[str]] = {}
    for field, index in result.items():
        reverse.setdefault(index, []).append(field)
    duplicates = [fields for fields in reverse.values() if len(fields) > 1]
    if duplicates:
        joined = "; ".join(", ".join(fields) for fields in duplicates)
        raise ProductImportError(f"Una columna no puede representar varios campos: {joined}.")
    return result


def _column_letter_index(value: str) -> int:
    result = 0
    for character in value.upper():
        if not "A" <= character <= "Z":
            raise ProductImportError("La letra de columna no es válida.")
        result = result * 26 + (ord(character) - ord("A") + 1)
    index = result - 1
    if index >= MAX_IMPORT_COLUMNS:
        raise ProductImportError("La columna queda fuera del rango permitido.")
    return index


def _mapped_value(row: Sequence[object], index: int) -> object:
    return row[index] if index < len(row) else None


def _raw_preview(rows: Sequence[Sequence[object]], *, maximum: int) -> list[list[str]]:
    return [
        [_cell_text(cell) for cell in row[:MAX_PREVIEW_COLUMNS]]
        for row in rows[:maximum]
    ]


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(Decimal(str(value)), "f")
    if isinstance(value, Decimal):
        return canonical_decimal(value)
    return str(value).strip()


def _empty_row(row: Sequence[object]) -> bool:
    return not any(_cell_text(value) for value in row)


def _looks_like_total(value: str) -> bool:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(character for character in decomposed if not unicodedata.combining(character))
    normalized = re.sub(r"\s+", " ", normalized).strip(" :.-")
    return bool(re.match(r"^(?:total(?:es)?|subtotal|importe total|suma)(?:\b|$)", normalized))


def _stable_line_id(source: str, row_number: int) -> str:
    digest = hashlib.sha256(f"{source}|{row_number}".encode("utf-8")).hexdigest()[:12].upper()
    return f"IMP-{row_number:05d}-{digest}"


def _numeric_text(value: str, *, field: str) -> str:
    text = value.strip().replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"(?i)EUR", "", text).replace("€", "").strip()
    if not text or len(text) > MAX_NUMERIC_CHARACTERS:
        raise ProductImportError(f"{field} no contiene un número válido.")
    if text.startswith(_FORMULA_PREFIX):
        raise ProductImportError(f"{field} no admite fórmulas.")
    return text


def _normalize_numeric_text(text: str, *, field: str) -> str:
    if _SPANISH_DECIMAL.fullmatch(text):
        return text.replace(".", "").replace(",", ".")
    if _SPANISH_GROUPED_INTEGER.fullmatch(text):
        return text.replace(".", "")
    if _CANONICAL_DECIMAL.fullmatch(text):
        return text
    raise ProductImportError(f"{field} no contiene un decimal válido.")


def _positive_row(value: object) -> int:
    if isinstance(value, bool):
        raise ProductImportError("La fila inicial no es válida.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ProductImportError("La fila inicial no es válida.") from exc
    if result < 1 or result > MAX_IMPORT_ROWS:
        raise ProductImportError("La fila inicial queda fuera del rango permitido.")
    return result


def _preview_limit(value: object) -> int:
    if isinstance(value, bool):
        raise ProductImportError("El número de filas de previsualización no es válido.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ProductImportError("El número de filas de previsualización no es válido.") from exc
    if result < 1:
        raise ProductImportError("Debe previsualizarse al menos una fila.")
    return min(result, MAX_PREVIEW_ROWS)


__all__ = (
    "MAX_ARCHIVE_MEMBERS",
    "MAX_ARCHIVE_UNCOMPRESSED_BYTES",
    "MAX_IMPORT_BYTES",
    "MAX_IMPORT_COLUMNS",
    "MAX_IMPORT_ROWS",
    "ProductImportError",
    "inspect_xlsx",
    "parse_decimal",
    "parse_product_rows",
    "preview_tabular",
    "preview_xlsx",
)
