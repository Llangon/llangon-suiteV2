from __future__ import annotations

import sqlite3
import json
from http import HTTPStatus

from webapp.infonalia_webapp.infonalia_history import (
    SEVERITY_ATTENTION,
    SEVERITY_CRITICAL,
    acknowledge_filtered_infonalia_events,
    acknowledge_infonalia_event,
    ensure_infonalia_history_schema,
    list_infonalia_history,
    record_infonalia_activity,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    load_app_module,
    make_handler,
    temporary_app_database,
)


def history_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE infonalia_dias (id INTEGER PRIMARY KEY, fecha TEXT, titulo TEXT)"
    )
    conn.execute(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            infonalia_dia_id INTEGER,
            expediente TEXT,
            organismo TEXT
        )
        """
    )
    conn.execute("INSERT INTO infonalia_dias VALUES (1, '2026-07-16', 'Infonalia 16/07/2026')")
    conn.execute("INSERT INTO infonalia_dias VALUES (2, '2026-07-17', 'Infonalia 17/07/2026')")
    conn.execute("INSERT INTO licitaciones VALUES (10, 1, 'EXP-10', 'Hospital de prueba')")
    ensure_infonalia_history_schema(conn)
    return conn


def test_history_deduplicates_and_keeps_entity_snapshots_after_deletion() -> None:
    conn = history_connection()

    first_id = record_infonalia_activity(
        conn,
        category="nuria_action",
        event_type="late_decision_change",
        source="email",
        actor="nuria@example.test",
        result="processed",
        title="Cambio tardío",
        day_id=1,
        licitacion_id=10,
        severity=SEVERITY_CRITICAL,
        dedupe_key="message:1",
        timestamp="2026-07-16T10:00:00",
    )
    duplicate_id = record_infonalia_activity(
        conn,
        category="nuria_action",
        event_type="late_decision_change",
        source="email",
        title="Duplicado",
        day_id=1,
        licitacion_id=10,
        severity=SEVERITY_CRITICAL,
        dedupe_key="message:1",
        timestamp="2026-07-16T10:01:00",
    )
    conn.execute("DELETE FROM licitaciones WHERE id = 10")
    conn.execute("DELETE FROM infonalia_dias WHERE id = 1")

    payload = list_infonalia_history(conn)

    assert first_id
    assert duplicate_id is None
    assert payload["summary"]["total"] == 1
    item = payload["items"][0]
    assert item["day_id"] is None
    assert item["licitacion_id"] is None
    assert item["day_date"] == "2026-07-16"
    assert item["expediente"] == "EXP-10"
    assert item["organismo"] == "Hospital de prueba"
    assert item["day_exists"] is False
    assert item["licitacion_exists"] is False


def test_history_combines_filters_paginates_and_searches() -> None:
    conn = history_connection()
    for index in range(55):
        record_infonalia_activity(
            conn,
            category="import" if index % 2 == 0 else "closure",
            event_type="event",
            source="web",
            actor="admin",
            result="processed",
            title=f"Evento {index}",
            detail="Hospital de prueba" if index == 54 else "Actividad",
            day_id=1 if index < 54 else 2,
            severity=SEVERITY_ATTENTION if index % 2 else "normal",
            timestamp=f"2026-07-16T10:{index:02d}:00",
        )

    first = list_infonalia_history(conn, limit=50)
    second = list_infonalia_history(conn, filters={"cursor": first["next_cursor"]}, limit=50)
    searched = list_infonalia_history(
        conn,
        filters={"day_id": "2", "q": "Hospital", "category": "import"},
    )

    assert len(first["items"]) == 50
    assert first["next_cursor"]
    assert len(second["items"]) == 5
    assert searched["summary"]["total"] == 1
    assert searched["items"][0]["day_id"] == 2


def test_acknowledgement_individual_and_filtered_only_changes_pending_matches() -> None:
    conn = history_connection()
    critical_id = record_infonalia_activity(
        conn,
        category="system",
        event_type="error",
        source="email_processor",
        title="Error",
        day_id=1,
        severity=SEVERITY_CRITICAL,
    )
    attention_id = record_infonalia_activity(
        conn,
        category="closure",
        event_type="reopened",
        source="web",
        title="Reapertura",
        day_id=2,
        severity=SEVERITY_ATTENTION,
    )
    record_infonalia_activity(
        conn,
        category="import",
        event_type="imported",
        source="web",
        title="Importación normal",
        day_id=2,
    )

    assert acknowledge_infonalia_event(
        conn, int(critical_id), reviewed_by="admin", timestamp="2026-07-16T12:00:00"
    )
    changed = acknowledge_filtered_infonalia_events(
        conn,
        filters={"day_id": "2", "severity": "attention"},
        reviewed_by="supervisor",
        timestamp="2026-07-16T12:05:00",
    )

    assert changed == 1
    rows = conn.execute(
        "SELECT id, reviewed_by FROM infonalia_activity_events ORDER BY id"
    ).fetchall()
    assert rows[0]["reviewed_by"] == "admin"
    assert rows[1]["id"] == attention_id
    assert rows[1]["reviewed_by"] == "supervisor"
    assert rows[2]["reviewed_by"] is None


def test_schema_creation_does_not_backfill_existing_days() -> None:
    conn = history_connection()

    assert conn.execute("SELECT COUNT(*) FROM infonalia_activity_events").fetchone()[0] == 0
    ensure_infonalia_history_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM infonalia_activity_events").fetchone()[0] == 0


def test_admin_history_api_lists_and_acknowledges_only_filtered_incidents() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        with app.db_session() as conn:
            first = app.record_infonalia_activity(
                conn,
                category="system",
                event_type="error",
                source="test",
                title="Error crítico",
                severity=app.SEVERITY_CRITICAL,
            )
            app.record_infonalia_activity(
                conn,
                category="closure",
                event_type="reopened",
                source="test",
                title="Reapertura",
                severity=app.SEVERITY_ATTENTION,
            )

        list_handler = make_handler(app, b"", "application/json")
        list_handler.api_list_infonalia_history("severity=critical&review_state=pending")
        status, payload = list_handler.responses[-1]
        assert status == HTTPStatus.OK
        assert payload["summary"]["total"] == 1
        assert payload["items"][0]["id"] == first

        ack_handler = make_handler(app, b"", "application/json")
        ack_handler.api_acknowledge_infonalia_history(int(first))
        assert ack_handler.responses[-1][1]["changed"] is True

        body = json.dumps({"filters": {"severity": "attention"}}).encode("utf-8")
        bulk_handler = make_handler(app, body, "application/json")
        bulk_handler.api_acknowledge_filtered_infonalia_history()
        assert bulk_handler.responses[-1][1]["acknowledged"] == 1

        with app.db_session() as conn:
            rows = conn.execute(
                "SELECT reviewed_by FROM infonalia_activity_events ORDER BY id"
            ).fetchall()
        assert [row["reviewed_by"] for row in rows] == ["admin_test", "admin_test"]


def test_history_api_requires_admin_and_mutations_are_csrf_protected() -> None:
    app = load_app_module()
    handler = make_handler(app, b"", "application/json")
    calls: list[str] = []
    handler.require_admin = lambda: calls.append("checked") or False

    handler.api_list_infonalia_history("")
    handler.api_acknowledge_infonalia_history(1)
    handler.api_acknowledge_filtered_infonalia_history()

    assert calls == ["checked", "checked", "checked"]
    assert handler.is_known_mutating_route("POST", "/api/infonalia/history/1/acknowledge") is True
    assert handler.is_known_mutating_route("POST", "/api/infonalia/history/acknowledge-filtered") is True
