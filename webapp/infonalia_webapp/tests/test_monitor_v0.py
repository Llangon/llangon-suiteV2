from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.agenda.email_summary import (
    build_operational_email_html,
    build_operational_email_text,
    build_pending_tasks_email_payload,
)
from webapp.infonalia_webapp.monitor.cli import main as monitor_cli_main
from webapp.infonalia_webapp.monitor.config import (
    DEFAULT_YEAR_MAX,
    DEFAULT_YEAR_MIN,
    MonitorConfigError,
    load_monitor_config,
)
from webapp.infonalia_webapp.monitor.markers import FOLLOW_MARKER_NAME, read_marker_id
from webapp.infonalia_webapp.monitor.scanner import is_year_folder, iter_monitor_year_roots, scan_marker_tree
from webapp.infonalia_webapp.monitor.scheduler import MonitorScheduler, list_schedule, next_schedule_preview, scheduler_enabled_from_env
from webapp.infonalia_webapp.monitor.service import (
    due_automation_task_types,
    monitor_automation_schedules,
    run_due_automation_tasks,
    run_automation_task,
    run_monitor,
    reset_scheduler_test_state,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    make_handler,
    temporary_app_database,
)


def make_db(path: Path, rows: list[tuple[int, str]] | None = None) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE licitaciones (
                id INTEGER PRIMARY KEY,
                expediente TEXT,
                ruta_carpeta TEXT,
                seguimiento_activo INTEGER NOT NULL DEFAULT 0,
                seguimiento_ultimo_check TEXT,
                seguimiento_ultima_sync TEXT,
                seguimiento_marker_path TEXT,
                seguimiento_marker_warning TEXT,
                updated_at TEXT
            );
            """
        )
        for licitacion_id, ruta_carpeta in rows or []:
            conn.execute(
                "INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at) VALUES (?, ?, ?, '')",
                (licitacion_id, f"EXP-{licitacion_id}", ruta_carpeta),
            )
        conn.commit()
    finally:
        conn.close()


def fetch_one(path: Path, sql: str):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


def test_monitor_config_prefers_monitor_root_defaults_and_rejects_real_dropbox(monkeypatch) -> None:
    monkeypatch.setenv("INFONALIA_MONITOR_ROOT", r"C:\ReplicaDb")
    monkeypatch.setenv("INFONALIA_DROPBOX_ROOT", r"D:\OtraReplica")
    monkeypatch.delenv("INFONALIA_MONITOR_YEAR_MIN", raising=False)
    monkeypatch.delenv("INFONALIA_MONITOR_YEAR_MAX", raising=False)

    config = load_monitor_config()

    assert str(config.root_path) == r"C:\ReplicaDb"
    assert config.year_min == DEFAULT_YEAR_MIN
    assert config.year_max == DEFAULT_YEAR_MAX

    monkeypatch.delenv("INFONALIA_MONITOR_ROOT", raising=False)
    monkeypatch.setenv("INFONALIA_DROPBOX_ROOT", r"C:\Users\LLangon03\Dropbox\00000 LLANGON")
    monkeypatch.delenv("INFONALIA_MONITOR_ALLOW_REAL_DROPBOX", raising=False)
    with pytest.raises(MonitorConfigError):
        load_monitor_config()

    monkeypatch.setenv("INFONALIA_MONITOR_ALLOW_REAL_DROPBOX", "1")
    assert "Dropbox" in str(load_monitor_config().root_path)


def test_year_roots_only_scan_direct_valid_year_folders(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    for name in [
        "2026",
        "2122",
        "Luisa",
        "Infonalia",
        "Plantillas",
        "Resumen licitaciones 2016 a 2021",
        "202A",
        "99",
    ]:
        (root / name).mkdir(parents=True)
    (root / "Luisa" / "2022").mkdir()

    year_roots = [path.name for path in iter_monitor_year_roots(root)]

    assert year_roots == ["2026", "2122"]
    assert is_year_folder("2026")
    assert is_year_folder("2122")
    assert not is_year_folder("Luisa")
    assert not is_year_folder("202A")
    assert not is_year_folder("99")


def test_marker_scan_detects_id_follow_and_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    for name in ["ID_33.llangon", "Lic_33.llangon", "abc.llangon"]:
        (folder / name).write_text("", encoding="utf-8")

    result = scan_marker_tree(root)

    assert read_marker_id(folder / "33.llangon") == 33
    assert read_marker_id(folder / "ID_33.llangon") is None
    assert result.raw_id_marker_count == 1
    assert result.markers[0].licitacion_id == 33
    assert result.markers[0].is_followed is True

    second = root / "2026" / "06 JUNIO" / "otra"
    second.mkdir()
    (second / "33.llangon").write_text("", encoding="utf-8")
    conflict = scan_marker_tree(root)
    assert not conflict.markers
    assert any(issue.code == "duplicate_id_marker" for issue in conflict.conflicts)


def test_repair_routes_and_dry_run_behavior(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "no" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "2026/antigua")])

    dry_run = run_monitor("dry-run", db_path=db_path, root=root)
    assert dry_run["dry_run"] is True
    assert dry_run["route_updates_count"] == 1
    assert fetch_one(db_path, "SELECT ruta_carpeta FROM licitaciones WHERE id = 33")[0] == "2026/antigua"
    dry_run_row = fetch_one(
        db_path,
        """
        SELECT task_type, mode, status, dry_run, route_updates_count, folders_checked_count,
               folders_repaired_count, processed_items_count
        FROM monitor_runs
        ORDER BY id DESC
        LIMIT 1
        """,
    )
    assert dry_run_row == ("licitaciones", "dry-run", "completed", 1, 1, 1, 1, 1)

    repaired = run_monitor("repair-routes", db_path=db_path, root=root)
    assert repaired["route_updates_count"] == 1
    assert fetch_one(db_path, "SELECT ruta_carpeta FROM licitaciones WHERE id = 33")[0] == str(folder)


def test_sync_updates_follow_cache_without_inventory_by_default(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    follow_marker = folder / FOLLOW_MARKER_NAME
    follow_marker.write_text("", encoding="utf-8")
    (folder / "PCAP contrato.pdf").write_text("contenido", encoding="utf-8")
    (folder / "Anexo 1.docx").write_text("contenido", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])

    report = run_monitor("sync", db_path=db_path, root=root)

    assert report["followed_count"] == 1
    assert report["folders_checked_count"] == 1
    assert report["inventory_files_count"] == 0
    row = fetch_one(db_path, "SELECT seguimiento_activo, seguimiento_marker_path FROM licitaciones WHERE id = 33")
    assert row[0] == 1
    assert row[1] == str(follow_marker)
    conn = sqlite3.connect(db_path)
    try:
        inventory_rows = conn.execute("SELECT * FROM licitacion_file_inventory WHERE licitacion_id = 33").fetchall()
        run_row = conn.execute(
            """
            SELECT task_type, mode, status, followed_count, folders_checked_count, processed_items_count,
                   platforms_checked_count, changes_detected_count, emails_prepared_count, emails_sent_count
            FROM monitor_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert inventory_rows == []
    assert run_row == ("licitaciones", "sync", "completed", 1, 1, 1, 0, 0, 0, 0)


def test_monitor_mode_and_cli_are_available(tmp_path: Path, capsys) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])

    monitor_report = run_monitor("monitor", db_path=db_path, root=root)
    assert monitor_report["mode"] == "monitor"
    assert monitor_report["inventory_files_count"] == 0

    exit_code = monitor_cli_main(["--mode", "dry-run", "--root", str(root), "--db", str(db_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"mode": "dry-run"' in captured.out


def test_monitor_endpoint_runs_with_csrf_and_reports_summary(tmp_path: Path, monkeypatch) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    monkeypatch.setenv("INFONALIA_MONITOR_ROOT", str(root))
    monkeypatch.delenv("INFONALIA_MONITOR_ALLOW_REAL_DROPBOX", raising=False)

    with temporary_app_database(app):
        with app.db_session() as conn:
            app.ensure_monitor_schema(conn)
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (33, 'EXP-33', 'Objeto', 'Org', 'Madrid', '2026-06-30',
                        '12:00', 'https://example.test', 'Importada', '2026/antigua',
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
        body = json.dumps({"mode": "dry-run"}).encode("utf-8")
        handler = make_handler(
            app,
            body,
            "application/json",
            path="/api/monitor/run",
            csrf_token=VALID_CSRF_TOKEN,
        )
        handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["mode"] == "dry-run"
    assert payload["task_type"] == "licitaciones"
    assert payload["found_markers_count"] == 1
    assert payload["route_updates_count"] == 1
    assert payload["monitor_run_id"]


def test_monitor_history_endpoint_is_admin_only_and_lists_runs(tmp_path: Path, monkeypatch) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    monkeypatch.setenv("INFONALIA_MONITOR_ROOT", str(root))

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (33, 'EXP-33', 'Objeto', 'Org', 'Madrid', '2026-06-30',
                        '12:00', 'https://example.test', 'Importada', ?,
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """,
                (str(folder),),
            )
        run_monitor("sync", db_path=app.DB_PATH, root=root)
        handler = make_handler(app, b"", "application/json", path="/api/monitor/runs")
        handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["items"]
    assert payload["items"][0]["task_type"] == "licitaciones"
    assert payload["items"][0]["mode"] == "sync"
    assert payload["items"][0]["folders_checked_count"] == 1
    assert payload["items"][0]["changes_detected_count"] == 0


def test_monitor_history_endpoint_filters_by_task_type_and_agenda_summary_skeleton(tmp_path: Path) -> None:
    app = load_app_module()

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Reunión interna', '', '2026-06-18T10:00:00', 'pendiente',
                        'admin_test', '2026-06-18T09:00:00', '2026-06-18T09:00:00')
                """
            )
        report = run_automation_task("resumen_agenda", db_path=app.DB_PATH)
        handler = make_handler(app, b"", "application/json", path="/api/monitor/runs?task_type=resumen_agenda")
        handler.do_GET()

    assert report["task_type"] == "resumen_agenda"
    assert report["dry_run"] is True
    assert report["processed_items_count"] == 1
    assert report["emails_prepared_count"] == 1
    assert report["emails_sent_count"] == 0

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert len(payload["items"]) == 1
    assert payload["items"][0]["task_type"] == "resumen_agenda"
    assert payload["items"][0]["processed_items_count"] == 1


def test_monitor_automation_schedule_declares_agenda_tasks_and_licitaciones_proposal(monkeypatch) -> None:
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_ENABLED", "1")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_TIME", "06:00")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", "1")
    monkeypatch.setenv("MONITOR_LICITACIONES_SCHEDULE_ENABLED", "1")
    monkeypatch.setenv("MONITOR_LICITACIONES_TIME_1", "07:00")
    monkeypatch.setenv("MONITOR_LICITACIONES_TIME_2", "12:30")
    monkeypatch.setenv("MONITOR_LICITACIONES_TIME_3", "17:30")
    schedules = monitor_automation_schedules()

    assert set(schedules) == {"agenda_pendientes_diaria", "monitor_licitaciones"}
    assert schedules["agenda_pendientes_diaria"]["time"] == "06:00"
    assert schedules["monitor_licitaciones"]["times"] == ["07:00", "12:30", "17:30"]
    assert due_automation_task_types(datetime(2026, 6, 15, 5, 59)) == []
    assert due_automation_task_types(datetime(2026, 6, 15, 6, 0)) == ["agenda_pendientes_diaria"]
    assert due_automation_task_types(datetime(2026, 6, 16, 6, 14)) == ["agenda_pendientes_diaria"]
    assert due_automation_task_types(datetime(2026, 6, 16, 7, 0)) == [
        "agenda_pendientes_diaria",
        "monitor_licitaciones",
    ]
    assert due_automation_task_types(datetime(2026, 6, 20, 13, 0)) == []
    assert due_automation_task_types(datetime(2026, 6, 21, 13, 0)) == []


def test_monitor_licitaciones_schedule_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_ENABLED", "1")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", "1")
    monkeypatch.setenv("MONITOR_LICITACIONES_SCHEDULE_ENABLED", "0")

    schedules = monitor_automation_schedules()

    assert set(schedules) == {"agenda_pendientes_diaria"}
    assert due_automation_task_types(datetime(2026, 6, 16, 17, 30)) == ["agenda_pendientes_diaria"]


def test_agenda_pending_weekdays_only_rules_and_next_schedule(monkeypatch) -> None:
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_ENABLED", "1")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_TIME", "06:00")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", "1")
    monkeypatch.setenv("MONITOR_LICITACIONES_SCHEDULE_ENABLED", "0")

    assert due_automation_task_types(datetime(2026, 6, 20, 6, 1)) == []
    assert due_automation_task_types(datetime(2026, 6, 21, 6, 1)) == []
    assert due_automation_task_types(datetime(2026, 6, 22, 6, 1)) == ["agenda_pendientes_diaria"]
    assert next_schedule_preview(datetime(2026, 6, 19, 18, 0)) == {
        "task_type": "agenda_pendientes_diaria",
        "run_at": "2026-06-22T06:00:00+02:00",
    }
    assert next_schedule_preview(datetime(2026, 6, 20, 6, 1)) == {
        "task_type": "agenda_pendientes_diaria",
        "run_at": "2026-06-22T06:00:00+02:00",
    }
    assert next_schedule_preview(datetime(2026, 6, 21, 6, 1)) == {
        "task_type": "agenda_pendientes_diaria",
        "run_at": "2026-06-22T06:00:00+02:00",
    }
    schedule = list_schedule(datetime(2026, 6, 21, 6, 1))[0]
    assert schedule["schedules"][0]["weekdays_only"] is True
    assert schedule["next"]["run_at"] == "2026-06-22T06:00:00+02:00"


def test_agenda_pending_weekend_once_creates_no_monitor_run_and_no_friday_catchup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_ENABLED", "1")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_TIME", "06:00")
    monkeypatch.setenv("MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY", "1")
    monkeypatch.setenv("MONITOR_LICITACIONES_SCHEDULE_ENABLED", "0")
    app = load_app_module()

    with temporary_app_database(app):
        with app.db_session() as conn:
            app.ensure_monitor_schema(conn)
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Pendiente del viernes', '', '2026-06-19T10:00:00', 'pendiente',
                        'admin_test', '2026-06-18T09:00:00', '2026-06-18T09:00:00')
                """
            )
        reports = run_due_automation_tasks(
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("weekend email")),
            current=datetime(2026, 6, 20, 6, 1),
        )
        with app.db_session() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM monitor_runs WHERE task_type = 'agenda_pendientes_diaria'"
            ).fetchone()[0]

    assert reports == []
    assert count == 0


def test_agenda_summary_task_sends_to_test_recipient_with_fake_sender(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Resumen real', '', '2026-06-18T10:00:00', 'pendiente',
                        'admin_test', '2026-06-18T09:00:00', '2026-06-18T09:00:00')
                """
            )
        report = run_automation_task(
            "resumen_agenda",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-18T10:05:00", None),
        )

    assert report["task_type"] == "resumen_agenda"
    assert report["mode"] == "manual"
    assert report["dry_run"] is False
    assert report["processed_items_count"] == 1
    assert report["emails_prepared_count"] == 1
    assert report["emails_sent_count"] == 1
    assert sent
    assert sent[0][0] == "monitor-test@example.test"
    assert "Agenda Llangón" in sent[0][3]
    assert "Resumen real" in sent[0][3]


def test_agenda_daily_task_sends_only_due_today_with_required_fields(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    current = datetime(2026, 6, 18, 6, 0, 0)

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (88, 'EXP-88', 'Suministro crítico', 'Org', 'Madrid', '2026-06-18',
                        '14:00', 'https://example.test', 'Preparar ficha', '',
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
        report = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-18T06:01:00", None),
            current=current,
        )

    assert report["task_type"] == "agenda_diaria"
    assert report["processed_items_count"] == 1
    assert report["emails_prepared_count"] == 1
    assert report["emails_sent_count"] == 1
    assert sent[0][0] == "monitor-test@example.test"
    assert sent[0][1] == "Agenda Llangón jueves 18-06-2026"
    assert "Expediente: EXP-88" in sent[0][2]
    assert "Título: EXP-88" in sent[0][2]
    assert "Estado: Preparar ficha" in sent[0][2]
    assert "Vence: 2026-06-18T14:00:00" in sent[0][2]
    assert "Ver perfil del contratante: https://example.test" in sent[0][2]
    assert "Expediente: EXP-88" in sent[0][3]
    assert "Fecha/hora final" not in sent[0][3]
    assert "Vence: 18/06/2026 14:00" in sent[0][3]
    assert "Ver perfil del contratante" in sent[0][3]


def test_pending_agenda_email_groups_cards_links_and_visual_state(monkeypatch) -> None:
    long_description = "Suministro de víveres con descripción completa sin recorte visible en el correo."
    payload = build_pending_tasks_email_payload(
        {
            "items": [
                {
                    "source_type": "licitacion",
                    "source_id": 88,
                    "title": "EXP-88",
                    "subtitle": long_description,
                    "expediente": "EXP-88",
                    "datetime": "2026-06-18T14:00:00",
                    "date": "2026-06-18",
                    "status": "Preparar ficha",
                    "tipo": "Licitación",
                    "enlace_perfil": "https://perfil.example.test/exp-88",
                    "linked_licitaciones": [{"expediente": "EXP-88"}],
                },
                {
                    "source_type": "licitacion",
                    "source_id": 89,
                    "title": "EXP-89",
                    "subtitle": "Suministro de mañana",
                    "expediente": "EXP-89",
                    "datetime": "2026-06-19T08:30:00",
                    "date": "2026-06-19",
                    "status": "Descargar para ver",
                    "tipo": "Licitación",
                    "enlace_perfil": "ftp://perfil-no-valido.example/exp-89",
                },
                {
                    "source_type": "actuacion",
                    "source_id": 9,
                    "title": "Actuación próxima",
                    "description": "Preparar documentación",
                    "datetime": "2026-06-20T09:00:00",
                    "date": "2026-06-20",
                    "status": "Pendiente",
                    "tipo": "subsanacion",
                    "linked_licitaciones": [{"enlace_perfil": "https://perfil.example.test/actuacion-9"}],
                },
                {
                    "source_type": "interno",
                    "source_id": 7,
                    "title": "Revisión futura",
                    "description": "Revisar agenda",
                    "datetime": "2026-06-30T10:00:00",
                    "date": "2026-06-30",
                    "status": "Preparada",
                    "tipo": "Interno",
                },
            ]
        },
        current=datetime(2026, 6, 18, 6, 0),
    )

    text = build_operational_email_text(payload)
    html = build_operational_email_html(payload, generated_at="2026-06-18T06:01:00")

    assert [section["title"] for section in payload["sections"]] == [
        "HOY",
        "PRÓXIMOS 7 DÍAS",
        "PRÓXIMAMENTE",
    ]
    assert text.index("HOY") < text.index("PRÓXIMOS 7 DÍAS") < text.index("PRÓXIMAMENTE")
    assert "VIERNES 19/06/2026" in text
    assert "SÁBADO 20/06/2026" in text
    assert "MARTES 30/06/2026" in text
    assert "URGENTE" not in text
    assert "ESTA SEMANA" not in text
    assert "Licitaciones:" not in text
    assert "Licitaciones:" not in html
    assert long_description in html
    assert "Ver en Llangón Suite" not in html
    assert "agenda_source=" not in html
    assert html.count("Ver perfil del contratante") == 2
    assert "https://perfil.example.test/exp-88" in html
    assert "https://perfil.example.test/actuacion-9" in html
    assert "perfil-no-valido" not in html
    assert "Fecha/hora final" not in html
    assert "Vence: 18/06/2026 14:00" in html
    assert "#fef3f2" in html
    assert "#fff7ed" in html
    assert "#eff8ff" in html
    assert "#ecfdf3" in html
    assert "max-width:96px" in html
    assert "padding:12px 20px" in html


def test_pending_agenda_email_omits_profile_link_without_valid_url() -> None:
    payload = build_pending_tasks_email_payload(
        {
            "items": [
                {
                    "source_type": "licitacion",
                    "source_id": 88,
                    "title": "EXP-88",
                    "datetime": "2026-06-18T14:00:00",
                    "date": "2026-06-18",
                    "status": "Preparada",
                    "enlace_perfil": "file:///tmp/perfil.html",
                }
            ]
        },
        current=datetime(2026, 6, 18, 6, 0),
    )

    html = build_operational_email_html(payload)

    assert "Ver en Llangón Suite" not in html
    assert "Ver perfil del contratante" not in html


def test_agenda_weekly_email_uses_single_today_and_tomorrow_labels(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    current = datetime(2026, 6, 18, 5, 30, 0)

    with temporary_app_database(app):
        with app.db_session() as conn:
            for title, starts_at in [
                ("Vence jueves", "2026-06-18T10:00:00"),
                ("Vence viernes", "2026-06-19T10:00:00"),
                ("Vence sábado", "2026-06-20T10:00:00"),
            ]:
                conn.execute(
                    """
                    INSERT INTO agenda_eventos (
                        titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                    )
                    VALUES (?, '', ?, 'pendiente', 'admin_test',
                            '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                    """,
                    (title, starts_at),
                )
        report = run_automation_task(
            "agenda_semanal",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-18T05:31:00", None),
            current=current,
        )

    text_body = sent[0][2]
    assert report["emails_sent_count"] == 1
    assert text_body.count("HOY") == 1
    assert text_body.count("MAÑANA") == 1
    assert "HOY, JUEVES 18/06/2026" in text_body
    assert "MAÑANA, VIERNES 19/06/2026" in text_body
    assert "SÁBADO 20/06/2026" in text_body
    assert "HOY, VIERNES" not in text_body


def test_agenda_email_hides_internal_numeric_expediente(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    current = datetime(2026, 6, 18, 6, 0, 0)

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (3, '3', 'Suministro sin expediente real', 'Org', 'Madrid', '2026-06-18',
                        '14:00', 'https://example.test', 'Preparar ficha', '',
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
        report = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-18T06:01:00", None),
            current=current,
        )

    assert report["emails_sent_count"] == 1
    assert "Expediente: 3" not in sent[0][2]
    assert "Expediente: 3" not in sent[0][3]
    assert "Fecha/hora final" not in sent[0][3]
    assert "Vence: 18/06/2026 14:00" in sent[0][3]


def test_agenda_daily_task_without_due_items_registers_no_email(tmp_path: Path) -> None:
    app = load_app_module()
    current = datetime(2026, 6, 18, 6, 0, 0)

    with temporary_app_database(app):
        report = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no email expected")),
            current=current,
        )
        with app.db_session() as conn:
            row = conn.execute(
                """
                SELECT status, processed_items_count, emails_prepared_count, emails_sent_count
                FROM monitor_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

    assert report["status"] == "completed"
    assert report["processed_items_count"] == 0
    assert report["emails_prepared_count"] == 0
    assert report["emails_sent_count"] == 0
    assert "Tareas pendientes" in report["task_details"]["message"]
    assert row["status"] == "completed"
    assert row["processed_items_count"] == 0
    assert row["emails_prepared_count"] == 0
    assert row["emails_sent_count"] == 0


def test_agenda_weekly_task_sends_even_without_items(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    current = datetime(2026, 6, 15, 5, 30, 0)

    with temporary_app_database(app):
        report = run_automation_task(
            "agenda_semanal",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-15T05:31:00", None),
            current=current,
        )

    assert report["task_type"] == "agenda_semanal"
    assert report["processed_items_count"] == 0
    assert report["emails_prepared_count"] == 1
    assert report["emails_sent_count"] == 1
    assert "Resumen semanal de agenda" in sent[0][1]
    assert "Sin elementos" in sent[0][2]
    assert "Sin elementos" in sent[0][3]


def test_agenda_automatic_duplicate_is_skipped_but_manual_can_send(tmp_path: Path) -> None:
    app = load_app_module()
    current = datetime(2026, 6, 18, 6, 0, 0)
    sent: list[str] = []

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Vence hoy', '', '2026-06-18T10:00:00', 'pendiente',
                        'admin_test', '2026-06-18T09:00:00', '2026-06-18T09:00:00')
                """
            )
        first = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: sent.append("first") or ("2026-06-18T06:01:00", None),
            current=current,
            trigger_mode="automatic",
        )
        second = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: sent.append("duplicate") or ("2026-06-18T06:02:00", None),
            current=current,
            trigger_mode="automatic",
        )
        manual = run_automation_task(
            "agenda_diaria",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: sent.append("manual") or ("2026-06-18T06:03:00", None),
            current=current,
        )

    assert first["mode"] == "automatic"
    assert first["schedule_key"] == "agenda_pendientes_diaria:2026-06-18"
    assert first["emails_sent_count"] == 1
    assert second["mode"] == "automatic"
    assert second["emails_sent_count"] == 0
    assert second["task_details"]["skipped_duplicate"] is True
    assert manual["mode"] == "manual"
    assert manual["emails_sent_count"] == 1
    assert sent == ["first", "manual"]


def test_run_due_automation_tasks_filters_already_executed_schedule(tmp_path: Path) -> None:
    app = load_app_module()
    current = datetime(2026, 6, 16, 6, 0, 0)
    sent: list[str] = []

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Vence una vez', '', '2026-06-16T10:00:00', 'pendiente',
                        'admin_test', '2026-06-15T09:00:00', '2026-06-15T09:00:00')
                """
            )
        first = run_due_automation_tasks(
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: sent.append("sent") or ("2026-06-16T06:01:00", None),
            current=current,
        )
        second = run_due_automation_tasks(
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("duplicate email")),
            current=current,
        )

    assert [item["task_type"] for item in first] == ["agenda_pendientes_diaria"]
    assert [item["task_details"]["skipped_duplicate"] for item in second] == [True]
    assert sent == ["sent"]


def test_monitor_licitaciones_scheduled_task_is_registered_without_external_calls(tmp_path: Path) -> None:
    app = load_app_module()
    current = datetime(2026, 6, 16, 7, 0, 0)

    with temporary_app_database(app):
        report = run_automation_task(
            "monitor_licitaciones",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no email expected")),
            current=current,
            trigger_mode="automatic",
        )

    assert report["task_type"] == "monitor_licitaciones"
    assert report["mode"] == "automatic"
    assert report["schedule_key"] == "monitor_licitaciones:2026-06-16:0700"
    assert report["emails_sent_count"] == 0
    assert "sin consulta externa" in report["task_details"]["preview"]


def test_due_notice_task_sends_grouped_email_records_alerts_and_blocks_same_level_duplicate(tmp_path: Path) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    current = datetime(2026, 6, 18, 6, 20, 0)

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (91, 'EXP-91', 'Contrato asociado', 'Org', 'Madrid', '2026-07-30',
                        '12:00', 'https://example.test', 'Preparar ficha', '',
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
            cursor = conn.execute(
                """
                INSERT INTO actuaciones (
                    tipo, titulo, descripcion, estado, deadline_at, origen, created_by, created_at, updated_at
                )
                VALUES ('requerimiento', 'Preparar solvencia', '', 'pendiente',
                        '2026-06-21T12:00:00', 'manual', 'admin_test',
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO actuacion_licitaciones (actuacion_id, licitacion_id, created_at, created_by)
                VALUES (?, 91, '2026-06-17T10:00:00', 'admin_test')
                """,
                (int(cursor.lastrowid),),
            )
            conn.execute(
                """
                INSERT INTO agenda_eventos (
                    titulo, descripcion, starts_at, estado, created_by, created_at, updated_at
                )
                VALUES ('Evento interno crítico', '', '2026-06-21T09:00:00', 'pendiente',
                        'admin_test', '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """
            )
        first = run_automation_task(
            "aviso_vencimiento_3d",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-18T06:21:00", None),
            current=current,
        )
        duplicate = run_automation_task(
            "aviso_vencimiento_3d",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("duplicate email")),
            current=current,
        )
        next_level = run_automation_task(
            "aviso_vencimiento_1d",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda to, subject, body, html: sent.append((to, subject, body, html)) or ("2026-06-20T06:26:00", None),
            current=datetime(2026, 6, 20, 6, 25, 0),
        )
        with app.db_session() as conn:
            rows = conn.execute(
                """
                SELECT notice_level, event_key, due_at, subject
                FROM monitor_vencimiento_alerts
                ORDER BY notice_level, event_key
                """
            ).fetchall()

    assert first["task_type"] == "aviso_vencimiento_3d"
    assert first["processed_items_count"] == 2
    assert first["changes_detected_count"] == 2
    assert first["emails_prepared_count"] == 1
    assert first["emails_sent_count"] == 1
    assert first["task_details"]["items_notified_count"] == 2
    assert sent[0][1] == "Vencimientos en 3 días (2 elementos)"
    assert "Expediente: EXP-91" in sent[0][2]
    assert "Título: Preparar solvencia" in sent[0][2]
    assert "Estado: pendiente" in sent[0][2]
    assert "Fecha/hora final: 2026-06-21T12:00:00" in sent[0][2]
    assert "Evento interno crítico" in sent[0][3]

    assert duplicate["processed_items_count"] == 2
    assert duplicate["changes_detected_count"] == 0
    assert duplicate["emails_prepared_count"] == 0
    assert duplicate["emails_sent_count"] == 0
    assert "no hay vencimientos nuevos" in duplicate["task_details"]["message"]

    assert next_level["task_type"] == "aviso_vencimiento_1d"
    assert next_level["processed_items_count"] == 2
    assert next_level["emails_sent_count"] == 1
    assert sent[1][1] == "Vencimientos de mañana (2 elementos)"

    assert len(rows) == 4
    assert {row["notice_level"] for row in rows} == {"1d", "3d"}
    assert {row["due_at"] for row in rows} == {"2026-06-21T09:00:00", "2026-06-21T12:00:00"}


def test_due_notice_task_without_items_registers_no_email(tmp_path: Path) -> None:
    app = load_app_module()

    with temporary_app_database(app):
        report = run_automation_task(
            "aviso_vencimiento_hoy",
            dry_run=False,
            db_path=app.DB_PATH,
            recipient="monitor-test@example.test",
            email_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no email expected")),
            current=datetime(2026, 6, 18, 6, 30, 0),
        )

    assert report["status"] == "completed"
    assert report["processed_items_count"] == 0
    assert report["changes_detected_count"] == 0
    assert report["emails_prepared_count"] == 0
    assert report["emails_sent_count"] == 0
    assert report["task_details"]["items_due_count"] == 0
    assert report["task_details"]["items_notified_count"] == 0


def test_agenda_summary_task_records_clear_error_without_test_recipient(tmp_path: Path) -> None:
    app = load_app_module()

    with temporary_app_database(app):
        report = run_automation_task("resumen_agenda", dry_run=False, db_path=app.DB_PATH)
        with app.db_session() as conn:
            row = conn.execute(
                "SELECT status, emails_prepared_count, emails_sent_count, error_message FROM monitor_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()

    assert report["status"] == "failed"
    assert report["emails_prepared_count"] == 1
    assert report["emails_sent_count"] == 0
    assert "email de pruebas" in report["error_message"]
    assert row["status"] == "failed"
    assert "email de pruebas" in row["error_message"]


def test_monitor_run_endpoint_can_send_agenda_summary_with_fake_sender(tmp_path: Path, monkeypatch) -> None:
    app = load_app_module()
    sent: list[tuple[str, str, str, str]] = []
    monkeypatch.delenv("MONITOR_TEST_EMAIL", raising=False)
    monkeypatch.delenv("INFONALIA_MONITOR_TEST_EMAIL", raising=False)

    with temporary_app_database(app):
        with app.db_session() as conn:
            for key, value in {
                "monitor_test_email": "monitor-test@example.test",
                "smtp_host": "smtp.example.test",
                "smtp_port": "2525",
                "smtp_from": "monitor@example.test",
                "smtp_tls": "0",
                "smtp_ssl": "0",
            }.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, "2026-06-18T10:00:00"),
                )
        monkeypatch.setattr(
            app,
            "send_monitor_email",
            lambda to, subject, body, html_body, settings=None: sent.append((to, subject, body, html_body)) or ("2026-06-18T10:05:00", None),
        )
        body = json.dumps({"task_type": "resumen_agenda"}).encode("utf-8")
        handler = make_handler(
            app,
            body,
            "application/json",
            path="/api/monitor/run",
            csrf_token=VALID_CSRF_TOKEN,
        )
        handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["task_type"] == "resumen_agenda"
    assert payload["mode"] == "manual"
    assert payload["dry_run"] is False
    assert payload["emails_prepared_count"] == 1
    assert payload["emails_sent_count"] == 1
    assert sent
    assert sent[0][0] == "monitor-test@example.test"


def test_monitor_pending_email_uses_multiple_configured_recipients(monkeypatch) -> None:
    app = load_app_module()
    captured: dict[str, object] = {}
    settings = {
        "monitor_agenda_pending_email_to": "info3@llangon.com; info@llangon.com",
        "smtp_host": "smtp.example.test",
        "smtp_port": "2525",
        "smtp_from": "monitor@example.test",
        "smtp_tls": "0",
        "smtp_ssl": "0",
    }
    monkeypatch.delenv("MONITOR_AGENDA_PENDING_EMAIL_TO", raising=False)
    monkeypatch.setattr(
        app,
        "send_notification_email_with_settings",
        lambda **kwargs: captured.update(kwargs) or ("2026-06-18T10:05:00", None),
    )

    sent_at, error = app.send_monitor_email(
        app.monitor_agenda_pending_recipient(settings),
        "Pendientes",
        "Texto",
        "<p>Texto</p>",
        settings=settings,
    )

    assert sent_at == "2026-06-18T10:05:00"
    assert error is None
    assert captured["recipients"] == ["info3@llangon.com", "info@llangon.com"]


def test_monitor_scheduler_status_endpoint_is_available_to_admin() -> None:
    app = load_app_module()
    handler = make_handler(app, b"", "application/json", path="/api/monitor/scheduler")
    handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["scheduler"]["running"] is False
    assert "due_now" in payload["scheduler"]


def test_monitor_scheduler_can_run_once_and_stays_disabled_under_pytest(monkeypatch) -> None:
    calls: list[datetime] = []
    current = datetime(2026, 6, 18, 6, 0, 0)
    scheduler = MonitorScheduler(
        interval_seconds=5,
        task_runner=lambda now: calls.append(now) or [{"task_type": "agenda_pendientes_diaria"}],
        now_factory=lambda: current,
    )

    reports = scheduler.run_once()

    monkeypatch.setenv("MONITOR_SCHEDULER_ENABLED", "1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    assert reports == [{"task_type": "agenda_pendientes_diaria"}]
    assert calls[0].replace(tzinfo=None) == current
    assert scheduler.status()["last_reports_count"] == 1
    assert scheduler_enabled_from_env() is False


def test_scheduler_reset_test_state_clears_claims_and_keys_without_deleting_history(tmp_path: Path) -> None:
    app = load_app_module()
    schedule_key = "agenda_pendientes_diaria:2026-06-21"

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO monitor_runs (
                    task_type, mode, root_path, started_at, status, dry_run, schedule_key,
                    details_json
                )
                VALUES ('agenda_pendientes_diaria', 'automatic', '', '2026-06-21T06:01:00',
                        'completed', 0, ?, '{}')
                """,
                (schedule_key,),
            )
            run_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                INSERT INTO monitor_automation_claims (
                    task_type, schedule_key, status, claimed_at, run_id
                )
                VALUES ('agenda_pendientes_diaria', ?, 'completed', '2026-06-21T06:00:00', ?)
                """,
                (schedule_key, run_id),
            )
            conn.execute(
                """
                INSERT INTO monitor_scheduler_heartbeat (
                    id, checked_at, status, next_task, next_run_at, timezone
                )
                VALUES (1, '2026-06-21T06:02:00', 'checked', '', '', 'Europe/Madrid')
                """
            )
            result = reset_scheduler_test_state(conn, schedule_keys=[schedule_key])
            run = conn.execute("SELECT id, schedule_key FROM monitor_runs WHERE id = ?", (run_id,)).fetchone()
            claims = conn.execute("SELECT COUNT(*) FROM monitor_automation_claims").fetchone()[0]
            heartbeat = conn.execute("SELECT COUNT(*) FROM monitor_scheduler_heartbeat").fetchone()[0]

    assert result["claims_deleted"] == 1
    assert result["monitor_run_schedule_keys_cleared"] == 1
    assert run["id"] == run_id
    assert run["schedule_key"] is None
    assert claims == 0
    assert heartbeat == 0


def test_scheduler_scripts_install_real_windows_task_without_flask() -> None:
    root = Path(__file__).resolve().parents[3]
    install_script = (root / "scripts" / "install_monitor_scheduler.ps1").read_text(encoding="utf-8")
    runner_script = (root / "scripts" / "run_monitor_scheduler_once.ps1").read_text(encoding="utf-8")
    hidden_runner_script = (root / "scripts" / "run_monitor_scheduler_hidden.vbs").read_text(encoding="utf-8")
    test_script = (root / "scripts" / "test_monitor_scheduler.ps1").read_text(encoding="utf-8")

    assert "New-ScheduledTaskTrigger" in install_script
    assert "New-TimeSpan -Minutes 5" in install_script
    assert "MultipleInstances IgnoreNew" in install_script
    assert "run_monitor_scheduler_once.ps1" in install_script
    assert "run_monitor_scheduler_hidden.vbs" in install_script
    assert "wscript.exe" in install_script
    assert "ServiceAccount" in install_script
    assert "--once" in runner_script
    assert "monitor_scheduler.log" in runner_script
    assert "Move-Item" in runner_script
    assert "WindowStyle Hidden" in hidden_runner_script
    assert "shell.Run(command, 0, True)" in hidden_runner_script
    assert "--reset-test-state" in test_script
