from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .markers import is_monitor_marker


SYSTEM_FILENAMES = {
    "comando_python.txt",
    "desktop.ini",
    "thumbs.db",
    ".ds_store",
}
SYSTEM_SUFFIXES = {".py", ".tmp", ".crdownload", ".part", ".log"}


def normalized_text(value: object) -> str:
    text = str(value or "").casefold()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalized_path_text(path: Path) -> str:
    return normalized_text(str(path).replace("\\", "/"))


def is_system_file(path: Path) -> bool:
    name = normalized_text(path.name)
    if is_monitor_marker(path):
        return True
    if path.name.startswith("~$"):
        return True
    if name in SYSTEM_FILENAMES:
        return True
    if path.suffix.casefold() in SYSTEM_SUFFIXES:
        return True
    if name == "http.url":
        return True
    return False


def classify_folder(relative_path: str) -> str:
    path = Path(relative_path)
    parent_parts = path.parts[:-1]
    if not parent_parts:
        return "raiz_licitacion"
    parts = [normalized_text(part) for part in parent_parts]
    joined = " / ".join(parts)
    if any(part == "no" for part in parts):
        return "no"
    if any("sobre 1" in part or part in {"sobre1", "sobre_1"} for part in parts):
        return "sobre_1"
    if any("sobre 2" in part or part in {"sobre2", "sobre_2"} for part in parts):
        return "sobre_2"
    if any("sobre 3" in part or part in {"sobre3", "sobre_3"} for part in parts):
        return "sobre_3"
    if "requerimiento" in joined or "subsanacion" in joined or re.search(r"\breq\b", joined):
        return "requerimiento"
    if any(part.startswith("recibido") for part in parts):
        return "recibido"
    if "oferta" in joined:
        return "oferta"
    if "documentacion" in joined:
        return "documentacion"
    return "otros"


def classify_document(path: Path, relative_path: str = "") -> str:
    name = normalized_text(path.name)
    full_text = normalized_text(f"{relative_path} {path.name}")
    if is_system_file(path):
        if name == "http.url":
            return "Enlace"
        return "Sistema"
    if "sobre 1" in full_text:
        return "Sobre 1"
    if "sobre 2" in full_text:
        return "Sobre 2"
    if "sobre 3" in full_text:
        return "Sobre 3"
    if "pcap" in full_text or "pliego administrativo" in full_text or "pliego clausulas administrativas" in full_text:
        return "PCAP"
    if "ppt" in full_text or "pliego tecnico" in full_text or "prescripciones tecnicas" in full_text:
        return "PPT"
    if "requerimiento" in full_text or "carta de requerimiento" in full_text or "subsanacion" in full_text:
        return "Requerimiento"
    if re.search(r"\breq\b", full_text):
        return "Requerimiento"
    if "acta" in full_text or "mesa" in full_text:
        return "Acta"
    if "anuncio" in full_text or "licitacion.html" in full_text or "licitacion.pdf" in full_text:
        return "Anuncio"
    if "doc_cd" in full_text or "doc_cn" in full_text:
        return "Anuncio"
    if "modelo oferta" in full_text or "anexo" in full_text:
        return "Anexo"
    if "aclaracion" in full_text:
        return "Aclaracion"
    if "correccion" in full_text or "rectificacion" in full_text:
        return "Correccion"
    if "memoria" in full_text:
        return "Memoria"
    if "resolucion" in full_text:
        return "Resolucion"
    if "justificante presentacion" in full_text or "oferta" in full_text:
        return "Oferta"
    if "modelo" in full_text:
        return "Modelo"
    if "certificado" in full_text or "iso" in full_text or "ifs" in full_text:
        return "Certificado"
    if "appcc" in full_text or "registro sanitario" in full_text:
        return "Certificado"
    if "ficha tecnica" in full_text or re.search(r"\bft\b", full_text):
        return "Ficha tecnica"
    return "Otro"


def is_relevant_document(path: Path, file_type: str, folder_type: str) -> bool:
    if is_system_file(path):
        return False
    if folder_type == "no":
        return False
    return file_type not in {"Enlace", "Sistema"}


def document_group(file_type: str, folder_type: str) -> str:
    if folder_type == "requerimiento" or file_type == "Requerimiento":
        return "Requerimientos"
    if folder_type in {"sobre_1", "sobre_2", "sobre_3", "oferta"}:
        return "Oferta / Sobres"
    if file_type in {"Oferta", "Sobre 1", "Sobre 2", "Sobre 3", "Justificante"}:
        return "Oferta / Sobres"
    if file_type == "Anexo":
        return "Anexos"
    if file_type in {"PCAP", "PPT", "Anuncio", "Memoria", "Resolucion", "Ficha tecnica"}:
        return "Documentos principales"
    return "Otros"
