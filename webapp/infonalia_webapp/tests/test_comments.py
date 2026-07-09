from __future__ import annotations

import sqlite3
import sys

import pytest

from webapp.infonalia_webapp.comments import (
    comments_summary_for_entities,
    create_comment,
    create_system_comment,
    delete_comment,
    ensure_comments_schema,
    list_comments,
    set_comment_pinned,
    update_comment,
)
from webapp.infonalia_webapp.db_migrations import MIGRATIONS


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, expediente TEXT)")
    conn.execute("CREATE TABLE actuaciones (id INTEGER PRIMARY KEY, titulo TEXT)")
    conn.execute("CREATE TABLE agenda_eventos (id INTEGER PRIMARY KEY, titulo TEXT)")
    conn.execute("CREATE TABLE infonalia_dias (id INTEGER PRIMARY KEY, titulo TEXT)")
    conn.execute("INSERT INTO licitaciones (id, expediente) VALUES (1, 'EXP-1')")
    conn.execute("INSERT INTO actuaciones (id, titulo) VALUES (1, 'Actuacion')")
    conn.execute("INSERT INTO agenda_eventos (id, titulo) VALUES (1, 'Evento')")
    conn.execute("INSERT INTO infonalia_dias (id, titulo) VALUES (1, 'Infonalia 08/07/2026')")
    ensure_comments_schema(conn)
    return conn


def test_create_list_edit_delete_comment_with_logical_delete() -> None:
    conn = make_conn()
    user = {"username": "manolo", "display_name": "Manolo", "role": "admin"}

    created = create_comment(
        conn,
        entity_type="licitacion",
        entity_id=1,
        body="Primer comentario",
        user=user,
        timestamp="2026-07-01T10:00:00",
    )

    assert created["body"] == "Primer comentario"
    assert created["author_name"] == "Manolo"
    assert list_comments(conn, entity_type="licitacion", entity_id=1, user=user)[0]["body"] == "Primer comentario"

    updated = update_comment(
        conn,
        comment_id=created["id"],
        body="Comentario editado",
        user=user,
        timestamp="2026-07-01T10:05:00",
    )
    assert updated["body"] == "Comentario editado"
    assert updated["is_edited"] is True

    deleted = delete_comment(
        conn,
        comment_id=created["id"],
        user=user,
        timestamp="2026-07-01T10:10:00",
    )
    assert deleted["is_deleted"] is True
    assert deleted["body"] == "Comentario eliminado."
    assert list_comments(conn, entity_type="licitacion", entity_id=1, include_deleted=False) == []


def test_comments_can_target_infonalia_day() -> None:
    conn = make_conn()
    user = {"username": "manolo", "display_name": "Manolo", "role": "admin"}

    created = create_comment(
        conn,
        entity_type="infonalia_dia",
        entity_id=1,
        body="Día revisado internamente.",
        user=user,
        timestamp="2026-07-08T13:13:00",
    )
    summary = comments_summary_for_entities(conn, [("infonalia_dia", 1)])

    assert created["body"] == "Día revisado internamente."
    assert summary[("infonalia_dia", 1)]["count"] == 1


def test_comments_validate_empty_body_and_entity_type() -> None:
    conn = make_conn()
    user = {"username": "nuria", "display_name": "Nuria", "role": "nuria"}

    with pytest.raises(ValueError, match="vacío"):
        create_comment(conn, entity_type="licitacion", entity_id=1, body="   ", user=user)

    with pytest.raises(ValueError, match="entidad"):
        create_comment(conn, entity_type="cliente", entity_id=1, body="Hola", user=user)

    with pytest.raises(ValueError, match="no existe"):
        create_comment(conn, entity_type="licitacion", entity_id=999, body="Hola", user=user)


def test_comment_permissions_owner_admin_and_system() -> None:
    conn = make_conn()
    owner = {"username": "nuria", "display_name": "Nuria", "role": "nuria"}
    other = {"username": "manolo", "display_name": "Manolo", "role": "nuria"}
    admin = {"username": "admin", "display_name": "Admin", "role": "admin"}

    created = create_comment(conn, entity_type="actuacion", entity_id=1, body="Tarea revisada", user=owner)

    with pytest.raises(PermissionError):
        update_comment(conn, comment_id=created["id"], body="No permitido", user=other)

    assert update_comment(conn, comment_id=created["id"], body="Edita admin", user=admin)["body"] == "Edita admin"
    assert set_comment_pinned(conn, comment_id=created["id"], pinned=True, user=admin)["is_pinned"] is True

    system = create_system_comment(conn, entity_type="actuacion", entity_id=1, body="Estado cambiado")
    with pytest.raises(PermissionError):
        update_comment(conn, comment_id=system["id"], body="No", user=admin)


def test_comments_summary_counts_only_active_and_keeps_latest_pinned_first() -> None:
    conn = make_conn()
    user = {"username": "manolo", "display_name": "Manolo", "role": "admin"}
    first = create_comment(conn, entity_type="licitacion", entity_id=1, body="Primero", user=user, timestamp="2026-07-01T10:00:00")
    second = create_comment(conn, entity_type="licitacion", entity_id=1, body="Segundo", user=user, timestamp="2026-07-01T10:05:00")
    set_comment_pinned(conn, comment_id=first["id"], pinned=True, user=user)
    delete_comment(conn, comment_id=second["id"], user=user)

    summary = comments_summary_for_entities(conn, [("licitacion", 1)])

    assert summary[("licitacion", 1)]["count"] == 1
    assert summary[("licitacion", 1)]["pinned_count"] == 1
    assert summary[("licitacion", 1)]["latest"]["body"] == "Primero"


def test_comments_migration_moves_legacy_notes_without_duplicates() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            expediente TEXT,
            notas_internas TEXT,
            seguimiento_notas TEXT,
            comentario TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO licitaciones (id, expediente, notas_internas, seguimiento_notas, comentario)
        VALUES (1, 'EXP', 'nota interna', 'nota seguimiento', 'comentario viejo')
        """
    )
    migration = [item for item in MIGRATIONS if item.version == "0017_comments_unified"][0]

    migration.apply(conn)
    migration.apply(conn)

    rows = conn.execute("SELECT author_user_id, body FROM comments ORDER BY id").fetchall()
    assert [(row["author_user_id"], row["body"]) for row in rows] == [
        ("system", "Nota interna migrada: nota interna"),
        ("system", "Nota de seguimiento migrada: nota seguimiento"),
        ("system", "Comentario migrado: comentario viejo"),
    ]


def test_ai_summary_indicator_uses_existing_ai_summaries_without_physical_paths() -> None:
    from webapp.infonalia_webapp.app import apply_licitacion_list_metadata

    conn = make_conn()
    conn.execute(
        """
        CREATE TABLE ai_summaries (
            id INTEGER PRIMARY KEY,
            licitacion_id INTEGER,
            summary_json TEXT,
            quality_status TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO ai_summaries (id, licitacion_id, summary_json, quality_status, updated_at)
        VALUES (10, 1, '{"resumen":"ok"}', 'pending_review', '2026-07-01T10:00:00')
        """
    )
    rows = [{"id": 1}, {"id": 2}]

    apply_licitacion_list_metadata(conn, rows)
    sys.modules.pop("webapp.infonalia_webapp.app", None)
    sys.modules.pop("app", None)

    assert rows[0]["has_ai_summary"] is True
    assert rows[0]["ai_summary_id"] == 10
    assert "path" not in rows[0]
    assert rows[1]["has_ai_summary"] is False


def test_ai_summary_indicator_ignores_empty_or_low_quality_summaries() -> None:
    from webapp.infonalia_webapp.app import apply_licitacion_list_metadata

    conn = make_conn()
    conn.execute(
        """
        CREATE TABLE ai_summaries (
            id INTEGER PRIMARY KEY,
            licitacion_id INTEGER,
            summary_json TEXT,
            quality_status TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO ai_summaries (id, licitacion_id, summary_json, quality_status, updated_at)
        VALUES (11, 1, '{}', 'pending_review', '2026-07-01T10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO ai_summaries (id, licitacion_id, summary_json, quality_status, updated_at)
        VALUES (12, 1, '{"resumen":"flojo"}', 'empty_analysis', '2026-07-01T10:05:00')
        """
    )
    rows = [{"id": 1}]

    apply_licitacion_list_metadata(conn, rows)
    sys.modules.pop("webapp.infonalia_webapp.app", None)
    sys.modules.pop("app", None)

    assert rows[0]["has_ai_summary"] is False
