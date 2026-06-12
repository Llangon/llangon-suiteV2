from __future__ import annotations

import re
from datetime import datetime

try:
    from .normalization import clean_text, parse_date_value, parse_time_value
except ImportError:
    from normalization import clean_text, parse_date_value, parse_time_value


def extraer_despues_de_dos_puntos(texto: str) -> str:
    pos = texto.find(":")
    if pos < 0:
        return ""
    resultado = texto[pos + 1 :].strip()
    match = re.search(r"<(https?://[^>]+)>", resultado, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return resultado


def extract_msg_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = clean_text(value)
    if not text:
        return datetime.now().date().isoformat()
    return parse_date_value(text) or datetime.now().date().isoformat()


def extraer_fecha_msg(texto: str) -> str:
    match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", texto)
    if not match:
        return ""
    return parse_date_value(match.group(1))


def extract_tipo_contrato(texto: str) -> str:
    if not texto:
        return ""
    tipos = [
        ("Concesión de servicios", r"concesi[oó]n\s+de\s+servicios"),
        ("Concesión de obras", r"concesi[oó]n\s+de\s+obras"),
        ("Suministro", r"suministros?"),
        ("Servicios", r"servicios?"),
        ("Obras", r"obras?"),
    ]
    contextual_patterns = [
        r"tipo\s+de\s+contrato\s*:?\s*(.{0,80})",
        r"contrato\s+de\s+(.{0,80})",
    ]
    for pattern in contextual_patterns:
        for match in re.finditer(pattern, texto, re.IGNORECASE):
            fragment = match.group(1)
            for label, tipo_pattern in tipos:
                if re.search(tipo_pattern, fragment, re.IGNORECASE):
                    return label
    for label, tipo_pattern in tipos:
        if re.search(tipo_pattern, texto, re.IGNORECASE):
            return label
    return ""


def extract_hora_limite_from_text(texto: str, fecha_limite: str) -> str:
    if not texto or not fecha_limite:
        return ""
    lines = [clean_text(line) for line in texto.splitlines()]
    date_pattern = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
    time_pattern = re.compile(r"(\d{1,2}:\d{2})")

    for index, line in enumerate(lines):
        date_match = date_pattern.search(line)
        if not date_match:
            continue
        if parse_date_value(date_match.group(1)) != fecha_limite:
            continue
        for candidate in lines[index : index + 3]:
            time_match = time_pattern.search(candidate)
            if time_match:
                return parse_time_value(time_match.group(1))
    return ""
