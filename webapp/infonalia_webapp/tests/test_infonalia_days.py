from __future__ import annotations

import importlib
import sqlite3
import sys

import pytest

from webapp.infonalia_webapp.infonalia_days import (
    day_row_to_dict,
    get_or_create_day,
    is_nuria_update_pending,
    mark_day_nuria_dirty,
    refresh_day_status,
)


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE infonalia_dias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            titulo TEXT,
            estado TEXT,
            enviado_nuria_at TEXT,
            nuria_dirty_at TEXT,
            reviewed_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            infonalia_dia_id INTEGER,
            estado TEXT,
            updated_at TEXT
        );
        CREATE TABLE usuarios (
            username TEXT PRIMARY KEY,
            role TEXT
        );
        CREATE TABLE licitacion_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER,
            event_type TEXT,
            old_value TEXT,
            new_value TEXT,
            user_id TEXT,
            created_at TEXT
        );
        CREATE TABLE email_action_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            source_message_id TEXT,
            from_email TEXT,
            subject TEXT,
            code TEXT,
            action_code TEXT,
            action_name TEXT,
            review_id INTEGER,
            licitacion_id INTEGER,
            previous_status TEXT,
            new_status TEXT,
            result TEXT,
            reason TEXT
        );
        """
    )
    conn.execute("INSERT INTO usuarios (username, role) VALUES ('manolo', 'admin')")
    conn.execute("INSERT INTO usuarios (username, role) VALUES ('nuria', 'nuria')")
    return conn


def insert_day(conn: sqlite3.Connection, **overrides: object) -> int:
    values = {
        "fecha": "2026-06-12",
        "titulo": "Infonalia 12/06/2026",
        "estado": "Importado",
        "enviado_nuria_at": "",
        "nuria_dirty_at": "",
        "reviewed_at": "",
        "created_at": "2026-06-12T08:00:00",
        "updated_at": "2026-06-12T08:00:00",
    }
    values.update(overrides)
    cur = conn.execute(
        """
        INSERT INTO infonalia_dias (
            fecha, titulo, estado, enviado_nuria_at, nuria_dirty_at, reviewed_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            values["fecha"],
            values["titulo"],
            values["estado"],
            values["enviado_nuria_at"],
            values["nuria_dirty_at"],
            values["reviewed_at"],
            values["created_at"],
            values["updated_at"],
        ),
    )
    return int(cur.lastrowid)


def insert_licitaciones(conn: sqlite3.Connection, dia_id: int, estados: list[str]) -> None:
    conn.executemany(
        "INSERT INTO licitaciones (infonalia_dia_id, estado, updated_at) VALUES (?, ?, ?)",
        [(dia_id, estado, "2026-06-12T08:30:00") for estado in estados],
    )


def test_infonalia_days_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.infonalia_days", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.infonalia_days")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"requests", "http.server", "socketserver", "subprocess", "smtplib"} & added


def test_get_or_create_day_creates_current_shape_and_reuses_existing_day() -> None:
    conn = make_conn()

    dia_id = get_or_create_day(conn, "2026-06-12", now=lambda: "2026-06-12T10:00:00")
    same_id = get_or_create_day(conn, "2026-06-12", now=lambda: "2026-06-12T11:00:00")

    row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    assert same_id == dia_id
    assert row["fecha"] == "2026-06-12"
    assert row["titulo"] == "Infonalia 12/06/2026"
    assert row["estado"] == "Importado"
    assert row["created_at"] == "2026-06-12T10:00:00"
    assert conn.execute("SELECT COUNT(*) FROM infonalia_dias").fetchone()[0] == 1


def test_get_or_create_day_uses_sin_fecha_for_blank_values() -> None:
    conn = make_conn()

    dia_id = get_or_create_day(conn, " ", now=lambda: "2026-06-12T10:00:00")

    row = conn.execute("SELECT fecha, titulo FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    assert dict(row) == {"fecha": "sin-fecha", "titulo": "Infonalia sin fecha"}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (None, False),
        ({}, False),
        ({"nuria_dirty_at": "2026-06-12T10:00:00", "enviado_nuria_at": ""}, True),
        ({"nuria_dirty_at": "2026-06-12T10:00:00", "enviado_nuria_at": "2026-06-12T10:00:00"}, True),
        ({"nuria_dirty_at": "2026-06-12T09:00:00", "enviado_nuria_at": "2026-06-12T10:00:00"}, False),
    ],
)
def test_is_nuria_update_pending_preserves_current_rule(row: dict | None, expected: bool) -> None:
    assert is_nuria_update_pending(row) is expected


def test_mark_day_nuria_dirty_updates_timestamp_fields() -> None:
    conn = make_conn()
    dia_id = insert_day(conn)

    mark_day_nuria_dirty(conn, dia_id, timestamp="2026-06-12T12:00:00")

    row = conn.execute("SELECT nuria_dirty_at, updated_at FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    assert dict(row) == {
        "nuria_dirty_at": "2026-06-12T12:00:00",
        "updated_at": "2026-06-12T12:00:00",
    }


@pytest.mark.parametrize(
    ("estados", "day_fields", "expected"),
    [
        ([], {}, "Importado"),
        (["Importada"], {}, "En filtrado interno"),
        (["Enviada a Nuria"], {}, "Listo para enviar a Nuria"),
        (["Enviada a Nuria"], {"enviado_nuria_at": "2026-06-12T09:00:00"}, "Pendiente de revisión Nuria"),
        (["Preparar ficha"], {"enviado_nuria_at": "2026-06-12T09:00:00"}, "Revisión parcial"),
        (
            ["Preparar ficha"],
            {"enviado_nuria_at": "2026-06-12T09:00:00", "nuria_dirty_at": "2026-06-12T10:00:00"},
            "Cambios pendientes para Nuria",
        ),
        (["Descartada"], {"reviewed_at": "2026-06-12T12:00:00"}, "Completado"),
    ],
)
def test_refresh_day_status_preserves_existing_state_machine(
    estados: list[str],
    day_fields: dict[str, str],
    expected: str,
) -> None:
    conn = make_conn()
    dia_id = insert_day(conn, **day_fields)
    insert_licitaciones(conn, dia_id, estados)

    refresh_day_status(conn, dia_id, timestamp="2026-06-12T13:00:00")

    row = conn.execute("SELECT estado, updated_at FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
    assert dict(row) == {"estado": expected, "updated_at": "2026-06-12T13:00:00"}


def test_day_row_to_dict_preserves_api_payload_shape() -> None:
    conn = make_conn()
    dia_id = insert_day(
        conn,
        enviado_nuria_at="2026-06-12T09:00:00",
        nuria_dirty_at="2026-06-12T10:00:00",
        reviewed_at="2026-06-12T11:00:00",
    )
    insert_licitaciones(
        conn,
        dia_id,
        ["Importada", "Descartada", "Enviada a Nuria", "Descargar para ver", "Preparar ficha", "Preparada"],
    )
    row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()

    item = day_row_to_dict(conn, row)

    assert item["id"] == dia_id
    assert item["fecha_formateada"] == "12/06/2026"
    assert item["total"] == 6
    assert item["gestionadas_admin"] == 5
    assert item["gestionadas_nuria"] == 3
    assert item["avance_porcentaje"] == 83
    assert item["estado_visual"] == "Cerrado"
    assert item["total_nuria"] == 4
    assert item["pendientes"] == 1
    assert item["descartadas_mi"] == 1
    assert item["pendientes_nuria"] == 1
    assert item["decisiones_nuria"] == 3
    assert item["descartadas_nuria"] == 1
    assert item["solo_descargar"] == 1
    assert item["preparar_licitacion"] == 1
    assert item["fecha_envio_nuria"] == "12/06/2026 09:00"
    assert item["fecha_cambio_nuria"] == "12/06/2026 10:00"
    assert item["fecha_revision"] == "12/06/2026 11:00"
    assert item["ultima_revision_admin"] == "12/06/2026 09:00"
    assert item["ultima_revision_nuria"] == ""
    assert item["ultima_actividad"] == "12/06/2026 11:00"
    assert item["ultima_accion_nuria"] == ""
    assert item["nuria_pending_update"] is True
    assert item["counts"] == {
        "Importada": 1,
        "Descartada": 1,
        "Enviada a Nuria": 1,
        "Descargar para ver": 1,
        "Preparar ficha": 1,
        "Preparada": 1,
    }


def test_day_row_to_dict_detects_reviewer_activity_without_closing_day() -> None:
    conn = make_conn()
    dia_id = insert_day(
        conn,
        enviado_nuria_at="2026-06-12T09:00:00",
        updated_at="2026-06-12T09:00:00",
    )
    insert_licitaciones(conn, dia_id, ["Enviada a Nuria", "Descargar para ver", "Importada"])
    licitaciones = conn.execute(
        "SELECT id, estado FROM licitaciones WHERE infonalia_dia_id = ? ORDER BY id ASC",
        (dia_id,),
    ).fetchall()
    conn.execute(
        """
        INSERT INTO email_action_events (
            created_at, licitacion_id, review_id, action_code, action_name, previous_status, new_status, result
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-06-12T10:15:00",
            licitaciones[1]["id"],
            dia_id,
            "02",
            "Descargar para ver",
            "Enviada a Nuria",
            "Descargar para ver",
            "processed",
        ),
    )
    row = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()

    item = day_row_to_dict(conn, row)

    assert item["gestionadas_admin"] == 2
    assert item["gestionadas_nuria"] == 1
    assert item["pendientes"] == 1
    assert item["estado_visual"] == "Revisado por Nuria · pendiente de cerrar"
    assert item["ultima_accion_nuria"] == "12/06/2026 10:15"
    assert item["ultima_revision_nuria"] == "12/06/2026 10:15"
    assert item["ultima_actividad"] == "12/06/2026 10:15"
