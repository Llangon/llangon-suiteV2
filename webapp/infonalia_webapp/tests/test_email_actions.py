from __future__ import annotations

from datetime import datetime

import pytest

from webapp.infonalia_webapp.email_actions import (
    ACTION_DISCARD,
    ACTION_DOWNLOAD_REVIEW,
    ACTION_PREPARE,
    ACTION_REVIEWED,
    build_infonalia_review_email_html,
    check_action_code,
    ensure_review_action_codes,
    extract_action_code,
    generate_action_code,
    process_email_action,
)
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def set_licitacion_state(app, licitacion_id: int, estado: str) -> None:
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE licitaciones
            SET estado = ?,
                objeto = COALESCE(NULLIF(objeto, ''), 'Suministro de prueba'),
                organismo = 'Ayuntamiento de prueba',
                provincia = 'Madrid',
                tipo = 'Suministro',
                presupuesto = 1234.56,
                fecha_limite = '2026-06-30',
                hora_limite = '12:30',
                enlace_perfil = 'https://example.test/perfil',
                enlace_infonalia = 'https://example.test/infonalia'
            WHERE id = ?
            """,
            (estado, licitacion_id),
        )


def licitacion_state(app, licitacion_id: int) -> str:
    with app.db_session() as conn:
        return conn.execute("SELECT estado FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()["estado"]


def insert_custom_dia(app, fecha: str) -> int:
    with app.db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO infonalia_dias (fecha, titulo, estado, created_at, updated_at)
            VALUES (?, ?, 'Importado', ?, ?)
            """,
            (fecha, f"Infonalia {fecha}", "2026-06-26T10:00:00", "2026-06-26T10:00:00"),
        )
        return int(cur.lastrowid)


def test_generate_action_code_and_parser() -> None:
    assert generate_action_code(141, ACTION_DISCARD) == "00000014101"
    assert generate_action_code(141, ACTION_DOWNLOAD_REVIEW) == "00000014102"
    assert generate_action_code(141, ACTION_PREPARE) == "00000014103"
    assert generate_action_code(58, ACTION_REVIEWED) == "00000005899"
    assert extract_action_code("LLANGON_CMD 00000014101 - Descartar", "") == "00000014101"
    assert extract_action_code("", "LLANGON_ACTION_CODE=00000014102") == "00000014102"
    assert extract_action_code("Sin codigo", "Nada") == ""


def test_review_email_html_uses_mailto_buttons_and_cc_rules() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-MAILTO")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        with app.db_session() as conn:
            day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()
            rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
            codes = ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            html = build_infonalia_review_email_html(
                day=day,
                licitaciones=rows,
                action_codes=codes,
                mailbox_to="info3llangon@gmail.com",
                mailbox_cc="info3@llangon.com",
                generated_at=datetime(2026, 6, 26, 14, 0, 0),
            )

    assert "Asesores Llangón S.L." in html
    assert "Resumen de licitaciones Infonalia" in html
    assert "Descartar" in html
    assert "Descargar para ver" in html
    assert "Preparar ficha" in html
    assert "Revisado" in html
    assert "00000000101" in html
    assert "00000000102" in html
    assert "00000000103" in html
    assert "00000000199" in html
    assert html.count("cc=info3%40llangon.com") == 3


@pytest.mark.parametrize(
    ("action_code", "expected_state"),
    [
        (ACTION_DISCARD, "Descartada"),
        (ACTION_DOWNLOAD_REVIEW, "Descargar para ver"),
        (ACTION_PREPARE, "Preparar ficha"),
    ],
)
def test_individual_action_accepts_enviada_a_nuria_while_review_is_open(action_code: str, expected_state: str) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-NURIA-ACTION")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        with app.db_session() as conn:
            result = process_email_action(
                conn,
                code=generate_action_code(licitacion_id, action_code),
                sender_email="nuria@example.test",
                source_message_id=f"msg-{action_code}",
                timestamp="2026-06-26T14:05:00",
                allowed_senders=["nuria@example.test"],
            )
            event = conn.execute(
                "SELECT previous_status, new_status, result FROM email_action_events WHERE licitacion_id = ? ORDER BY id DESC LIMIT 1",
                (licitacion_id,),
            ).fetchone()

        assert result["status"] == "processed"
        assert result["old_state"] == "Enviada a Nuria"
        assert result["new_state"] == expected_state
        assert licitacion_state(app, licitacion_id) == expected_state
        assert event["previous_status"] == "Enviada a Nuria"
        assert event["new_status"] == expected_state
        assert event["result"] == "processed"


def test_individual_action_accepts_repeated_changes_while_review_is_open() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        first = insert_licitacion(app, dia_id, "EXP-ACTION-1")
        second = insert_licitacion(app, dia_id, "EXP-ACTION-2")
        set_licitacion_state(app, first, "Enviada a Nuria")
        set_licitacion_state(app, second, "Importada")
        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE infonalia_dia_id = ?", (dia_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            discard = process_email_action(
                conn,
                code=generate_action_code(first, ACTION_DISCARD),
                sender_email="nuria@example.test",
                source_message_id="msg-1",
                timestamp="2026-06-26T14:05:00",
                allowed_senders=["nuria@example.test"],
            )
            prepare = process_email_action(
                conn,
                code=generate_action_code(first, ACTION_PREPARE),
                sender_email="nuria@example.test",
                source_message_id="msg-2",
                timestamp="2026-06-26T14:06:00",
                allowed_senders=["nuria@example.test"],
            )
            download = process_email_action(
                conn,
                code=generate_action_code(first, ACTION_DOWNLOAD_REVIEW),
                sender_email="nuria@example.test",
                source_message_id="msg-3",
                timestamp="2026-06-26T14:07:00",
                allowed_senders=["nuria@example.test"],
            )
            final_discard = process_email_action(
                conn,
                code=generate_action_code(first, ACTION_DISCARD),
                sender_email="nuria@example.test",
                source_message_id="msg-4",
                timestamp="2026-06-26T14:08:00",
                allowed_senders=["nuria@example.test"],
            )
            comments_count = conn.execute(
                "SELECT COUNT(*) FROM comments WHERE entity_type = 'licitacion' AND entity_id = ?",
                (first,),
            ).fetchone()[0]
            events_count = conn.execute(
                "SELECT COUNT(*) FROM email_action_events WHERE licitacion_id = ? AND result = 'processed'",
                (first,),
            ).fetchone()[0]

        assert discard["status"] == "processed"
        assert prepare["status"] == "processed"
        assert download["status"] == "processed"
        assert final_discard["status"] == "processed"
        assert licitacion_state(app, first) == "Descartada"
        assert licitacion_state(app, second) == "Importada"
        assert comments_count == 4
        assert events_count == 4


def test_same_email_message_action_is_ignored_when_already_processed() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-DEDUPE-MSG")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            first = process_email_action(
                conn,
                code=code,
                sender_email="nuria@example.test",
                source_message_id="<same-message>",
                timestamp="2026-06-26T14:05:00",
                allowed_senders=["nuria@example.test"],
            )
            second = process_email_action(
                conn,
                code=code,
                sender_email="nuria@example.test",
                source_message_id="<same-message>",
                timestamp="2026-06-26T14:10:00",
                allowed_senders=["nuria@example.test"],
            )
            events = conn.execute(
                "SELECT result, reason FROM email_action_events WHERE licitacion_id = ? ORDER BY id ASC",
                (licitacion_id,),
            ).fetchall()

        assert first["status"] == "processed"
        assert second["status"] == "ignored"
        assert second["error_code"] == "DUPLICATE_EMAIL_ACTION"
        assert licitacion_state(app, licitacion_id) == "Descartada"
        assert [event["result"] for event in events] == ["processed", "ignored"]
        assert "ya fue procesado" in events[-1]["reason"]


def test_same_email_message_action_is_ignored_via_action_code_marker_even_without_processed_event() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-DEDUPE-CODE")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            first = process_email_action(
                conn,
                code=code,
                sender_email="nuria@example.test",
                source_message_id="<same-message-code>",
                timestamp="2026-06-26T14:05:00",
                allowed_senders=["nuria@example.test"],
            )
            conn.execute(
                """
                DELETE FROM email_action_events
                WHERE licitacion_id = ?
                  AND code = ?
                  AND source_message_id = ?
                  AND result = 'processed'
                """,
                (licitacion_id, code, "<same-message-code>"),
            )
            second = process_email_action(
                conn,
                code=code,
                sender_email="nuria@example.test",
                source_message_id="<same-message-code>",
                timestamp="2026-06-26T14:10:00",
                allowed_senders=["nuria@example.test"],
            )
            action_row = conn.execute(
                "SELECT status, source_message_id, result_message FROM email_action_codes WHERE code = ?",
                (code,),
            ).fetchone()
            events = conn.execute(
                "SELECT result, reason FROM email_action_events WHERE licitacion_id = ? ORDER BY id ASC",
                (licitacion_id,),
            ).fetchall()

        assert first["status"] == "processed"
        assert second["status"] == "ignored"
        assert second["error_code"] == "DUPLICATE_EMAIL_ACTION"
        assert second["duplicate_source"] == "action_code"
        assert licitacion_state(app, licitacion_id) == "Descargar para ver"
        assert action_row["status"] == "processed"
        assert action_row["source_message_id"] == "<same-message-code>"
        assert "Acción Descargar para ver aplicada" in (action_row["result_message"] or "")
        assert [event["result"] for event in events] == ["ignored"]
        assert "ya fue procesado" in events[-1]["reason"]


def test_review_action_marks_day_and_auto_discards_only_pending_same_review() -> None:
    app = load_app_module()
    confirmations: list[tuple[str, str, str]] = []
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        other_dia_id = insert_custom_dia(app, "2026-06-15")
        pending_nuria = insert_licitacion(app, dia_id, "EXP-PENDING-NURIA")
        imported = insert_licitacion(app, dia_id, "EXP-IMPORTADA")
        download = insert_licitacion(app, dia_id, "EXP-DOWNLOAD")
        prepare = insert_licitacion(app, dia_id, "EXP-PREPARE")
        discarded = insert_licitacion(app, dia_id, "EXP-DISCARDED")
        other = insert_licitacion(app, other_dia_id, "EXP-OTHER")
        set_licitacion_state(app, pending_nuria, "Enviada a Nuria")
        set_licitacion_state(app, imported, "Importada")
        set_licitacion_state(app, download, "Descargar para ver")
        set_licitacion_state(app, prepare, "Preparar ficha")
        set_licitacion_state(app, discarded, "Descartada")
        set_licitacion_state(app, other, "Importada")

        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE infonalia_dia_id = ?", (dia_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            result = process_email_action(
                conn,
                code=generate_action_code(dia_id, ACTION_REVIEWED),
                sender_email="nuria@example.test",
                source_message_id="msg-review",
                timestamp="2026-06-26T15:00:00",
                allowed_senders=["nuria@example.test"],
                confirmation_sender=lambda subject, body, html: confirmations.append((subject, body, html)),
            )
            day = conn.execute("SELECT estado, reviewed_at FROM infonalia_dias WHERE id = ?", (dia_id,)).fetchone()

        assert result["status"] == "processed"
        assert result["auto_discarded"] == 2
        assert result["untouched"] == 3
        assert day["estado"] == "Completado"
        assert day["reviewed_at"] == "2026-06-26T15:00:00"
        assert licitacion_state(app, pending_nuria) == "Descartada"
        assert licitacion_state(app, imported) == "Descartada"
        assert licitacion_state(app, download) == "Descargar para ver"
        assert licitacion_state(app, prepare) == "Preparar ficha"
        assert licitacion_state(app, discarded) == "Descartada"
        assert licitacion_state(app, other) == "Importada"
        assert confirmations


def test_individual_action_after_review_closed_is_ignored() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-CLOSED")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE infonalia_dias
                SET reviewed_at = ?, estado = 'Completado'
                WHERE id = ?
                """,
                ("2026-06-26T15:00:00", dia_id),
            )
            result = process_email_action(
                conn,
                code=generate_action_code(licitacion_id, ACTION_DISCARD),
                sender_email="nuria@example.test",
                source_message_id="msg-late",
                timestamp="2026-06-26T15:30:00",
                allowed_senders=["nuria@example.test"],
            )
            event = conn.execute(
                "SELECT result, reason FROM email_action_events WHERE licitacion_id = ? ORDER BY id DESC LIMIT 1",
                (licitacion_id,),
            ).fetchone()

        assert result["status"] == "ignored"
        assert result["error_code"] == "REVIEW_CLOSED"
        assert licitacion_state(app, licitacion_id) == "Enviada a Nuria"
        assert event["result"] == "ignored"
        assert event["reason"] == "Orden ignorada: revisión Infonalia ya cerrada."


@pytest.mark.parametrize(
    "advanced_state",
    ["Preparada", "Oferta enviada", "Adjudicada", "No adjudicada", "En seguimiento"],
)
def test_individual_action_does_not_modify_advanced_states(advanced_state: str) -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, f"EXP-{advanced_state}")
        set_licitacion_state(app, licitacion_id, advanced_state)
        with app.db_session() as conn:
            result = process_email_action(
                conn,
                code=generate_action_code(licitacion_id, ACTION_DISCARD),
                sender_email="nuria@example.test",
                source_message_id=f"msg-{advanced_state}",
                timestamp="2026-06-26T14:30:00",
                allowed_senders=["nuria@example.test"],
            )
            event = conn.execute(
                "SELECT result, reason FROM email_action_events WHERE licitacion_id = ? ORDER BY id DESC LIMIT 1",
                (licitacion_id,),
            ).fetchone()

        assert result["status"] == "ignored"
        assert result["error_code"] == "ADVANCED_STATE"
        assert licitacion_state(app, licitacion_id) == advanced_state
        assert event["result"] == "ignored"
        assert "estado avanzado" in event["reason"]


def test_email_action_codes_status_does_not_block_direct_code_processing() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-LEGACY-CODE")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            conn.execute(
                "UPDATE email_action_codes SET status = 'processed' WHERE code = ?",
                (code,),
            )
            result = process_email_action(
                conn,
                code=code,
                sender_email="nuria@example.test",
                source_message_id="msg-legacy",
                timestamp="2026-06-26T14:10:00",
                allowed_senders=["nuria@example.test"],
            )

        assert result["status"] == "processed"
        assert licitacion_state(app, licitacion_id) == "Descartada"


def test_check_code_interprets_direct_code_without_pre_generated_row() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-CHECK-DIRECT")
        set_licitacion_state(app, licitacion_id, "Enviada a Nuria")
        with app.db_session() as conn:
            payload = check_action_code(
                conn,
                code=generate_action_code(licitacion_id, ACTION_PREPARE),
                sender_email="nuria@example.test",
                allowed_senders=["nuria@example.test"],
            )
            legacy_row = conn.execute(
                "SELECT 1 FROM email_action_codes WHERE code = ?",
                (generate_action_code(licitacion_id, ACTION_PREPARE),),
            ).fetchone()

        assert payload["exists"] is True
        assert payload["kind"] == "licitacion"
        assert payload["entity_id"] == licitacion_id
        assert payload["action_code"] == ACTION_PREPARE
        assert payload["review_id"] == dia_id
        assert payload["licitacion_status"] == "Enviada a Nuria"
        assert payload["processable"] is True
        assert legacy_row is None


def test_unknown_and_unauthorized_codes_are_rejected() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "EXP-SEC")
        with app.db_session() as conn:
            rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
            ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
            unknown = process_email_action(
                conn,
                code="99999999901",
                sender_email="nuria@example.test",
                allowed_senders=["nuria@example.test"],
            )
            unauthorized = process_email_action(
                conn,
                code=generate_action_code(licitacion_id, ACTION_DISCARD),
                sender_email="otra@example.test",
                allowed_senders=["nuria@example.test"],
            )

        assert unknown["error_code"] == "LICITACION_NOT_FOUND"
        assert unauthorized["error_code"] == "UNAUTHORIZED_SENDER"
        assert licitacion_state(app, licitacion_id) == "Importada"
