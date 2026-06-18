from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.csv_parsing import (
    build_payload_from_csv_row,
    csv_alias_map,
    normalize_estado,
    normalize_key,
    read_csv_rows,
)


def test_csv_parsing_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.csv_parsing", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.csv_parsing")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_normalize_key_preserves_alias_matching_behavior() -> None:
    assert normalize_key("Fecha de presentación") == "fechadepresentacion"
    assert normalize_key("No_tocar._Ruta_carpeta") == "notocarrutacarpeta"


def test_csv_alias_map_preserves_known_aliases() -> None:
    mapping = csv_alias_map(["Fecha de presentación", "Expediente", "Perfil del Contratante"])

    assert mapping["fecha_limite"] == "Fecha de presentación"
    assert mapping["expediente"] == "Expediente"
    assert mapping["enlace_perfil"] == "Perfil del Contratante"


def test_normalize_estado_preserves_existing_labels() -> None:
    assert normalize_estado("Descartada por mí") == "Descartada"
    assert normalize_estado("Pendiente Nuria") == "Enviada a Nuria"
    assert normalize_estado("Solo descargar") == "Descargar para ver"
    assert normalize_estado("Hacer concurso") == "Preparar ficha"
    assert normalize_estado("No interesa") == "Descartada"
    assert normalize_estado("") == "Importada"


def test_read_csv_rows_selects_best_header_row() -> None:
    content = (
        "cabecera sin interes\n"
        "Fecha Infonalia;Expediente;Objeto;Organismo\n"
        "12/06/2026;EXP-1;Servicio ficticio;Org ficticio\n"
    ).encode("utf-8")

    rows, headers = read_csv_rows(content)

    assert headers == ["Fecha Infonalia", "Expediente", "Objeto", "Organismo"]
    assert rows == [
        {
            "Fecha Infonalia": "12/06/2026",
            "Expediente": "EXP-1",
            "Objeto": "Servicio ficticio",
            "Organismo": "Org ficticio",
        }
    ]


def test_build_payload_from_csv_row_preserves_current_transformations() -> None:
    row = {
        "Fecha Infonalia": "12/06/2026",
        "Expediente": "EXP-1",
        "Objeto": "Servicio ficticio",
        "Organismo": "Org ficticio",
        "Presupuesto": "1.234,56 EUR",
        "Fecha de presentación": "30/06/2026",
        "Hora límite": "9:05",
        "Perfil del Contratante": "contrataciondelestado.es/wps",
        "Estado": "Solo descargar",
    }
    mapping = csv_alias_map(list(row))

    payload = build_payload_from_csv_row(row, mapping)

    assert payload["fecha_infonalia"] == "2026-06-12"
    assert payload["expediente"] == "EXP-1"
    assert payload["presupuesto"] == 1234.56
    assert payload["fecha_limite"] == "2026-06-30"
    assert payload["hora_limite"] == "09:05"
    assert payload["enlace_perfil"] == "https://contrataciondelestado.es/wps"
    assert payload["plataforma"] == "PLACE"
    assert payload["estado"] == "Importada"
