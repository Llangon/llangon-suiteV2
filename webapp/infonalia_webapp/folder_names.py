from __future__ import annotations

import re
import unicodedata

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


def safe_folder_name(value: str) -> str:
    text = clean_text(value) or "licitacion"
    text = re.sub(r'[\\/:*?"<>|]+', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:140] or "licitacion"


def folder_text(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.upper().replace("&", " Y ")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def expediente_folder_text(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.upper().replace("&", " Y ")
    text = re.sub(r"[\\/.-]+", "", text)
    text = re.sub(r"[()]+", " ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def short_folder_phrase(value: str, max_words: int = 7) -> str:
    words = folder_text(value).split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def extract_municipio_from_organismo(organismo: object, provincia: object) -> str:
    text = folder_text(organismo)
    provincia_text = folder_text(provincia)
    if not text:
        return ""

    patterns = [
        r"\bAYUNTAMIENTO\s+DE\s+(.+)",
        r"\bAYUNTAMIENTO\s+DEL\s+(.+)",
        r"\bAYUNTAMIENTO\s+(.+)",
    ]
    candidate = ""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            break

    if not candidate:
        return ""

    candidate = re.split(r"\b(ALCALDIA|CONCEJALIA|AREA|SERVICIO|PROVINCIA|CIF)\b", candidate)[0]
    if provincia_text:
        candidate = re.sub(rf"\b{re.escape(provincia_text)}\b", " ", candidate)

    candidate = re.sub(r"\b(EL|LA|LOS|LAS)?\s*AYUNTAMIENTO\b", " ", candidate)
    candidate = short_folder_phrase(candidate, max_words=4)
    if candidate == "PINOSO":
        return "EL PINOSO"
    return candidate


def extract_residencia_phrase(text: str) -> str:
    match = re.search(r"\bRESIDENCIA\s+([A-Z0-9 ]{3,60}?)(?:\s+DE\s+|\s+PARA\s+|\s+LOTE\b|$)", text)
    if not match:
        return ""
    phrase = short_folder_phrase(f"RESIDENCIA {match.group(1)}", max_words=5)
    return phrase


def extract_hospital_phrase(text: str) -> str:
    match = re.search(r"\bHOSPITAL\s+([A-Z0-9 ]{3,80}?)(?:\s+Y\s+|\s+PARA\s+|\s+LOTE\b|$)", text)
    if not match:
        return ""
    return short_folder_phrase(f"HOSPITAL {match.group(1)}", max_words=6)


def extract_objeto_folder_key(objeto: object) -> str:
    text = folder_text(objeto)
    if not text:
        return ""

    residencia = extract_residencia_phrase(text)
    if residencia:
        return residencia

    if "ESCUELA INFANTIL" in text:
        return "ESCUELA INFANTIL"

    hospital = extract_hospital_phrase(text)
    if hospital:
        return hospital

    preferred_phrases = [
        "CARNE Y DERIVADOS",
        "PRODUCTOS CARNICOS",
        "PESCADO Y PRODUCTOS DERIVADOS",
        "FRUTAS Y VERDURAS",
        "PRODUCTOS ALIMENTARIOS",
        "VIVERES",
        "PAN",
    ]
    for phrase in preferred_phrases:
        if phrase in text:
            return phrase

    base = re.split(r"\bLOTE\s*\d+\b|\bLOTES?\b", text, maxsplit=1)[0]
    base = re.sub(
        r"^(EL\s+|LA\s+)?(CONTRATO\s+DE\s+)?(SUMINISTRO|SERVICIO|OBRA|CONCESION)\s+(DE|DEL|PARA)?\s+",
        "",
        base,
    )
    if " PARA " in base:
        candidate = base.split(" PARA ", 1)[1]
    else:
        candidate = base

    stop_words = {
        "EL",
        "LA",
        "LOS",
        "LAS",
        "DE",
        "DEL",
        "PARA",
        "POR",
        "CON",
        "Y",
        "EN",
        "A",
        "AL",
        "LOS",
        "CENTROS",
        "DEPENDIENTES",
        "AYUNTAMIENTO",
        "MUNICIPAL",
    }
    words = [word for word in candidate.split() if word not in stop_words]
    return " ".join(words[:6])
