from __future__ import annotations

import csv
import io
import re
import unicodedata

try:
    from .licitacion_states import ESTADO_IMPORTADA, normalize_licitacion_estado
    from .normalization import clean_text, parse_date_value, parse_money, parse_time_value
    from .url_helpers import detectar_plataforma, normalize_url
except ImportError:
    from licitacion_states import ESTADO_IMPORTADA, normalize_licitacion_estado
    from normalization import clean_text, parse_date_value, parse_money, parse_time_value
    from url_helpers import detectar_plataforma, normalize_url


CSV_ALIASES = {
    "fecha_infonalia": [
        "Fecha_Infonalia",
        "Fecha Infonalia",
        "Infonalia",
    ],
    "expediente": ["Expediente"],
    "objeto": [
        "Objeto_del_contrato",
        "Objeto del contrato",
        "Resumen del Objeto",
        "Objeto",
    ],
    "organismo": ["Organismo"],
    "provincia": [
        "Provincia_de_ejecucion",
        "Provincia de ejecucion",
        "Provincia de ejecución",
        "Provincia de ejecucin",
        "Provincia",
    ],
    "tipo": [
        "Tipo_de_Contrato",
        "Tipo de Contrato",
        "Tipo",
    ],
    "presupuesto": ["Presupuesto"],
    "fecha_limite": [
        "Fecha_de_presentacion",
        "Fecha de presentacion",
        "Fecha de presentación",
        "Fecha de presentacin",
        "Fecha limite",
        "Fecha límite",
    ],
    "hora_limite": [
        "Hora_limite",
        "Hora limite",
        "Hora límite",
        "Hora lmite",
    ],
    "plataforma": ["Plataforma"],
    "enlace_perfil": [
        "Enlace_Perfil_del_contratante",
        "Enlace Perfil del contratante",
        "Perfil del Contratante",
        "Perfil",
    ],
    "enlace_infonalia": [
        "EnlaceInfonalia",
        "Enlace Infonalia",
        "Anuncio Infonalia",
    ],
    "estado": [
        "Estado",
        "Nuria",
    ],
    "comentario": ["Comentario"],
    "ruta_carpeta": [
        "No_tocar._Ruta_carpeta",
        "Ruta_carpeta",
        "Ruta carpeta",
        "Carpeta",
    ],
}


def normalize_key(value: object) -> str:
    text = clean_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "", text).lower()
    return text


def csv_alias_map(headers: list[str]) -> dict[str, str]:
    normalized_headers = {normalize_key(header): header for header in headers}
    result = {}
    for field, aliases in CSV_ALIASES.items():
        for alias in aliases:
            normalized = normalize_key(alias)
            if normalized in normalized_headers:
                result[field] = normalized_headers[normalized]
                break
    return result


def row_value(row: dict[str, str], mapping: dict[str, str], field: str) -> str:
    header = mapping.get(field)
    if not header:
        return ""
    return clean_text(row.get(header))


def normalize_estado(value: object) -> str:
    return normalize_licitacion_estado(value)


def decode_csv_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def read_csv_rows(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = decode_csv_bytes(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    csv_rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    best_header_index = 0
    best_score = -1

    for index, cells in enumerate(csv_rows[:50]):
        headers_candidate = [clean_text(cell) for cell in cells]
        mapping = csv_alias_map(headers_candidate)
        non_empty = sum(1 for header in headers_candidate if header)
        score = len(mapping) + (10 if "expediente" in mapping else 0)
        if non_empty >= 3 and score > best_score:
            best_header_index = index
            best_score = score

    headers = [clean_text(header) for header in csv_rows[best_header_index]] if csv_rows else []
    rows = []
    for cells in csv_rows[best_header_index + 1 :]:
        if not any(clean_text(value) for value in cells):
            continue
        row = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = cells[index] if index < len(cells) else ""
        rows.append(row)

    return rows, headers


def build_payload_from_csv_row(row: dict[str, str], mapping: dict[str, str]) -> dict[str, object]:
    enlace_perfil = normalize_url(row_value(row, mapping, "enlace_perfil"))
    enlace_infonalia = normalize_url(row_value(row, mapping, "enlace_infonalia"))
    plataforma = row_value(row, mapping, "plataforma") or detectar_plataforma(enlace_perfil)

    return {
        "fecha_infonalia": parse_date_value(row_value(row, mapping, "fecha_infonalia")),
        "expediente": row_value(row, mapping, "expediente"),
        "objeto": row_value(row, mapping, "objeto"),
        "organismo": row_value(row, mapping, "organismo"),
        "provincia": row_value(row, mapping, "provincia"),
        "tipo": row_value(row, mapping, "tipo"),
        "presupuesto": parse_money(row_value(row, mapping, "presupuesto")),
        "fecha_limite": parse_date_value(row_value(row, mapping, "fecha_limite")),
        "hora_limite": parse_time_value(row_value(row, mapping, "hora_limite")),
        "plataforma": plataforma,
        "enlace_perfil": enlace_perfil,
        "enlace_infonalia": enlace_infonalia,
        "estado": ESTADO_IMPORTADA,
        "comentario": row_value(row, mapping, "comentario"),
        "ruta_carpeta": row_value(row, mapping, "ruta_carpeta"),
    }
