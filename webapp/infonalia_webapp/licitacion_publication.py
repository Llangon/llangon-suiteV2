from __future__ import annotations

import re
import unicodedata

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


TIPO_PUBLICACION_LICITACION = "licitacion"
TIPO_PUBLICACION_ANUNCIO_PREVIO = "anuncio_previo"

TIPOS_PUBLICACION = [
    TIPO_PUBLICACION_LICITACION,
    TIPO_PUBLICACION_ANUNCIO_PREVIO,
]
TIPOS_PUBLICACION_VALIDOS = set(TIPOS_PUBLICACION)
TIPO_PUBLICACION_LABELS = {
    TIPO_PUBLICACION_LICITACION: "Licitación",
    TIPO_PUBLICACION_ANUNCIO_PREVIO: "Anuncio previo",
}


def publication_key(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(value).lower())
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def normalize_tipo_publicacion(value: object, *, default: str = TIPO_PUBLICACION_LICITACION) -> str:
    text = clean_text(value)
    if not text:
        return default
    if text in TIPOS_PUBLICACION_VALIDOS:
        return text
    key = publication_key(text)
    if key in {"anuncioprevio", "previo", "informacionprevia"}:
        return TIPO_PUBLICACION_ANUNCIO_PREVIO
    if key in {"licitacion", "licitacionnormal", "contratacion", "procedimiento"}:
        return TIPO_PUBLICACION_LICITACION
    return default


def is_anuncio_previo(value: object) -> bool:
    return normalize_tipo_publicacion(value) == TIPO_PUBLICACION_ANUNCIO_PREVIO


def detect_tipo_publicacion_from_texts(*values: object, has_fecha_limite: bool = False) -> str:
    joined = " ".join(clean_text(value) for value in values if clean_text(value))
    if not joined or has_fecha_limite:
        return TIPO_PUBLICACION_LICITACION
    if "anuncio previo" in joined.lower():
        return TIPO_PUBLICACION_ANUNCIO_PREVIO
    return TIPO_PUBLICACION_LICITACION
