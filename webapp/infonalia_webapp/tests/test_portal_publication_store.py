from __future__ import annotations

import json
import sqlite3

from webapp.infonalia_webapp.portal_publication.store import (
    ACCESS_CODE_ITERATIONS,
    approve_portal_review,
    ensure_portal_schema,
    ingest_portal_events,
    publication_rows,
    recover_portal_preview,
    save_portal_draft,
)


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO licitaciones (id) VALUES (402)")
    return conn


def _model(recipient: str = "Astursantina") -> dict[str, object]:
    return {
        "tender": {"recipient": recipient},
        "coverage": {"status": "preview_ready"},
        "downloads": [{"name": "Ficha.pdf"}],
    }


def test_saves_one_independent_draft_per_ficha_and_returns_personal_code() -> None:
    conn = _connection()
    first = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="ASTURSANTINA/Ficha.pdf",
        model=_model(),
        selected_files=["ASTURSANTINA/Ficha.pdf"],
    )
    second = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="OTRO CLIENTE/Ficha.pdf",
        model=_model("Otro cliente"),
        selected_files=["OTRO CLIENTE/Ficha.pdf"],
    )

    assert first["id"] != second["id"]
    assert first["slug"] != second["slug"]
    assert str(first["access_code"]).startswith("LL-")
    assert len(publication_rows(conn, 402)) == 2
    stored = conn.execute("SELECT * FROM portal_publications WHERE id = ?", (first["id"],)).fetchone()
    assert stored["access_iterations"] == ACCESS_CODE_ITERATIONS
    assert str(first["access_code"]) not in stored["access_hash"]


def test_regeneration_updates_same_ficha_without_creating_a_duplicate() -> None:
    conn = _connection()
    first = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="ASTURSANTINA/Ficha.pdf",
        model=_model(),
        selected_files=["ASTURSANTINA/Ficha.pdf"],
    )
    updated = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="ASTURSANTINA/Ficha.pdf",
        model=_model("Astursantina actualizada"),
        selected_files=["ASTURSANTINA/Ficha.pdf", "Pliego.pdf"],
    )

    assert updated["id"] == first["id"]
    assert updated["slug"] == first["slug"]
    assert conn.execute("SELECT COUNT(*) FROM portal_publications").fetchone()[0] == 1


def test_event_import_is_idempotent_and_counts_accesses_and_downloads() -> None:
    conn = _connection()
    publication = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="Ficha.pdf",
        model=_model(),
        selected_files=["Ficha.pdf"],
    )
    events = [
        {"id": "evt-1", "event_type": "access", "visitor_id": "visitor-1", "occurred_at": "2026-08-21T10:00:00Z"},
        {"id": "evt-2", "event_type": "download", "file_id": "file-1", "file_name": "Pliego.pdf", "visitor_id": "visitor-1", "occurred_at": "2026-08-21T10:01:00Z"},
    ]

    assert ingest_portal_events(conn, str(publication["id"]), events) == 2
    assert ingest_portal_events(conn, str(publication["id"]), events) == 0
    row = publication_rows(conn, 402)[0]
    assert row["access_count"] == 1
    assert row["download_count"] == 1
    assert row["last_activity_at"] == "2026-08-21T10:01:00Z"


def test_saved_preview_can_be_recovered_with_a_new_visible_access_code() -> None:
    conn = _connection()
    publication = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="ASTURSANTINA/Ficha.pdf",
        model=_model(),
        selected_files=["ASTURSANTINA/Ficha.pdf"],
    )
    previous_hash = conn.execute("SELECT access_hash FROM portal_publications WHERE id = ?", (publication["id"],)).fetchone()[0]

    recovered = recover_portal_preview(conn, str(publication["id"]))

    assert recovered["tender"]["recipient"] == "Astursantina"
    assert str(recovered["publication"]["access_code"]).startswith("LL-")
    assert recovered["publication"]["id"] == publication["id"]
    current_hash = conn.execute("SELECT access_hash FROM portal_publications WHERE id = ?", (publication["id"],)).fetchone()[0]
    assert current_hash != previous_hash


def test_manual_review_can_only_approve_pages_preserved_literally() -> None:
    conn = _connection()
    model = _model()
    model["coverage"] = {
        "status": "needs_review",
        "fallback_pages": [2],
        "missing_coverage_pages": [],
        "invalid_hash_pages": [],
        "visual_unreviewed_pages": [],
        "unmapped_pages": [],
        "invalid_block_mapping_pages": [],
    }
    model["sections"] = [{"blocks": [{"type": "source_page", "page": 2, "text": "Contenido íntegro"}]}]
    publication = save_portal_draft(
        conn,
        licitacion_id=402,
        ficha_relative_path="Ficha.pdf",
        model=model,
        selected_files=["Ficha.pdf"],
    )

    approved = approve_portal_review(conn, str(publication["id"]))

    assert approved["status"] == "draft"
    assert approved["coverage"]["manual_review_approved"] is True
    stored = conn.execute("SELECT status, model_json FROM portal_publications WHERE id = ?", (publication["id"],)).fetchone()
    assert stored["status"] == "draft"
    assert json.loads(stored["model_json"])["coverage"]["status"] == "preview_ready"
