from __future__ import annotations

import unicodedata

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


ESTADO_IMPORTADA = "Importada"
ESTADO_DESCARTADA = "Descartada"
ESTADO_ENVIADA_NURIA = "Enviada a Nuria"
ESTADO_DESCARGAR_PARA_VER = "Descargar para ver"
ESTADO_PREPARAR_FICHA = "Preparar ficha"
ESTADO_PREPARADA = "Preparada"
ESTADO_OFERTA_ENVIADA = "Oferta enviada"

ESTADOS_ORDEN = [
    ESTADO_IMPORTADA,
    ESTADO_DESCARTADA,
    ESTADO_ENVIADA_NURIA,
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
    ESTADO_PREPARADA,
    ESTADO_OFERTA_ENVIADA,
]
ESTADOS_VALIDOS = set(ESTADOS_ORDEN)

ADMIN_REVIEW_STATES = [ESTADO_DESCARTADA, ESTADO_ENVIADA_NURIA]
NURIA_REVIEW_STATES = [ESTADO_DESCARTADA, ESTADO_DESCARGAR_PARA_VER, ESTADO_PREPARAR_FICHA]
NURIA_DEFAULT_REVIEW_STATES = [
    ESTADO_ENVIADA_NURIA,
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
    ESTADO_PREPARADA,
    ESTADO_OFERTA_ENVIADA,
]
NURIA_DISCARDED_STATES = [ESTADO_DESCARTADA]
NURIA_VISIBLE_STATES = [*NURIA_DEFAULT_REVIEW_STATES, *NURIA_DISCARDED_STATES]
AGENDA_LICITACION_STATES = [ESTADO_DESCARGAR_PARA_VER, ESTADO_PREPARAR_FICHA, ESTADO_PREPARADA]

ESTADO_LABELS = {state: state for state in ESTADOS_ORDEN}

OLD_STATE_MAP = {
    "": ESTADO_IMPORTADA,
    "pendiente": ESTADO_IMPORTADA,
    "importado": ESTADO_IMPORTADA,
    "importada": ESTADO_IMPORTADA,
    "descartadapormi": ESTADO_DESCARTADA,
    "descartadainterna": ESTADO_DESCARTADA,
    "descartar": ESTADO_DESCARTADA,
    "descartada": ESTADO_DESCARTADA,
    "no": ESTADO_DESCARTADA,
    "nointeresa": ESTADO_DESCARTADA,
    "pendientenuria": ESTADO_ENVIADA_NURIA,
    "enviadanuria": ESTADO_ENVIADA_NURIA,
    "enviadaanuria": ESTADO_ENVIADA_NURIA,
    "solodescargar": ESTADO_DESCARGAR_PARA_VER,
    "solodescarga": ESTADO_DESCARGAR_PARA_VER,
    "descargar": ESTADO_DESCARGAR_PARA_VER,
    "descargada": ESTADO_DESCARGAR_PARA_VER,
    "descargado": ESTADO_DESCARGAR_PARA_VER,
    "descargarparaver": ESTADO_DESCARGAR_PARA_VER,
    "hacer": ESTADO_PREPARAR_FICHA,
    "hacerconcurso": ESTADO_PREPARAR_FICHA,
    "concurso": ESTADO_PREPARAR_FICHA,
    "prepararficha": ESTADO_PREPARAR_FICHA,
    "prepararlicitacion": ESTADO_PREPARAR_FICHA,
    "preparada": ESTADO_PREPARADA,
    "presentada": ESTADO_OFERTA_ENVIADA,
    "ofertaenviada": ESTADO_OFERTA_ENVIADA,
}


def state_key(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(value).lower())
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return "".join(character for character in without_accents if character.isalnum())


def normalize_licitacion_estado(value: object, *, default: str = ESTADO_IMPORTADA) -> str:
    text = clean_text(value)
    if not text:
        return default
    if text in ESTADOS_VALIDOS:
        return text
    return OLD_STATE_MAP.get(state_key(text), default)


def is_agenda_licitacion_estado(value: object) -> bool:
    return normalize_licitacion_estado(value) in AGENDA_LICITACION_STATES
