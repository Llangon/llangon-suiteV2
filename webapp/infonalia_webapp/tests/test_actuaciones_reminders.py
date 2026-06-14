from __future__ import annotations

import sys
from datetime import datetime, timedelta

from webapp.infonalia_webapp.actuaciones_reminders import build_reminder_body, reminder_rows
from webapp.infonalia_webapp.tests.test_actuaciones_api import create_actuacion
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def teardown_function() -> None:
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)
    sys.modules.pop("webapp.infonalia_webapp.send_actuaciones_reminders", None)


def test_reminder_body_includes_vencidas_hoy_semana_and_sin_licitacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "REM-001")
        now = datetime.now().replace(microsecond=0)
        create_actuacion(app, [licitacion_id], titulo="Vencida", deadline_at=(now - timedelta(hours=1)).isoformat())
        create_actuacion(app, [licitacion_id], titulo="Hoy", deadline_at=(now + timedelta(minutes=30)).isoformat())
        create_actuacion(app, [licitacion_id], titulo="Semana", deadline_at=(now + timedelta(days=4)).isoformat())
        create_actuacion(app, None, titulo="Sin licitación", deadline_at="")
        with app.db_session() as conn:
            rows = reminder_rows(conn, now=now)

    text, html = build_reminder_body(rows, now=now)

    assert "Vencida" in text
    assert "Hoy" in text
    assert "Semana" in text
    assert "Sin licitación" in text
    assert "Actuaciones vencidas" in html


def test_reminder_body_summarizes_more_than_three_licitaciones() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_ids = [
            insert_licitacion(app, dia_id, f"REM-MULTI-{index}")
            for index in range(1, 5)
        ]
        now = datetime.now().replace(microsecond=0)
        create_actuacion(
            app,
            licitacion_ids,
            titulo="Revisión conjunta",
            deadline_at=(now + timedelta(hours=1)).isoformat(),
        )
        with app.db_session() as conn:
            rows = reminder_rows(conn, now=now)

    text, _html = build_reminder_body(rows, now=now)

    assert "REM-MULTI-1" in text
    assert "REM-MULTI-2" in text
    assert "REM-MULTI-3" in text
    assert "+1 más" in text


def test_send_actuaciones_reminders_dry_run_does_not_send(monkeypatch, capsys) -> None:
    from webapp.infonalia_webapp import send_actuaciones_reminders as script

    app = load_app_module()
    with temporary_app_database(app):
        monkeypatch.setattr(script.app, "DATA_ROOT", app.DATA_ROOT)
        monkeypatch.setattr(script.app, "DOWNLOAD_ROOT", app.DOWNLOAD_ROOT)
        monkeypatch.setattr(script.app, "DB_PATH", app.DB_PATH)
        monkeypatch.setenv("INFONALIA_REMINDER_RECIPIENTS", "avisos@example.test")

        def fail_send(**_kwargs):
            raise AssertionError("dry-run must not send email")

        monkeypatch.setattr(script, "send_reminder_email", fail_send)
        exit_code = script.main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Resumen de actuaciones y vencimientos" in captured.out
    assert "avisos@example.test" in captured.out
