from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from webapp.infonalia_webapp.monitor.tender_api import TenderMonitorAPIContext
from webapp.infonalia_webapp.monitor.snapshots import snapshot_from_result
from webapp.infonalia_webapp.monitor.tender_repository import save_snapshot, set_monitor_baseline
from webapp.infonalia_webapp.tests.test_download_endpoint import (
    make_download_handler,
    temporary_download_app,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import VALID_CSRF_TOKEN, load_app_module
from webapp.infonalia_webapp.tests.test_seguimiento_markers_api import insert_licitacion_with_id


def prepare_followed_licitacion(app, root: Path, licitacion_id: int = 33) -> Path:
    folder = root / "2026" / "07 JULIO" / f"licitacion {licitacion_id}"
    folder.mkdir(parents=True)
    (folder / f"{licitacion_id}.llangon").write_text("", encoding="utf-8")
    (folder / "EnSeguimiento.llangon").write_text("", encoding="utf-8")
    insert_licitacion_with_id(app, licitacion_id, str(folder))
    with app.db_session() as conn:
        conn.execute(
            "UPDATE licitaciones SET plataforma = 'PLACE', enlace_perfil = ? WHERE id = ?",
            (f"https://contrataciondelestado.es/wps/poc?licitacion={licitacion_id}", licitacion_id),
        )
    return folder


def attach_monitor_context(handler, app, root: Path, *, role: str = "admin", launched: list[int] | None = None) -> None:
    user = {
        "username": "admin_test" if role == "admin" else "reviewer_test",
        "role": role,
        "display_name": "Usuario de prueba",
        "csrf_token": VALID_CSRF_TOKEN,
    }
    handler.current_user = lambda: user

    def fake_launcher(cycle_id: int, **_kwargs):
        if launched is not None:
            launched.append(cycle_id)
        return {"ok": True, "pid": 12345, "cycle_id": cycle_id}

    handler.tender_monitor_api_context = lambda: TenderMonitorAPIContext(
        db_path=app.DB_PATH,
        user=user,
        root=root,
        email_sender=lambda *_args: ("2026-07-20T10:00:00", None),
        telegram_sender=lambda *_args: {"ok": True, "message_id": "test"},
        worker_launcher=fake_launcher,
    )


def test_monitor_get_summary_discovers_only_physical_follow_marker(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    with temporary_download_app(app):
        prepare_followed_licitacion(app, root)
        handler = make_download_handler(app, path="/api/tender-monitor/followed")
        attach_monitor_context(handler, app, root)
        handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert [item["id"] for item in payload["items"]] == [33]
    assert payload["items"][0]["followed"] is True
    assert payload["items"][0]["prepared"] is True


def test_monitor_tender_detail_endpoint_uses_temporary_data(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    with temporary_download_app(app):
        prepare_followed_licitacion(app, root)
        snapshot = snapshot_from_result(
            {
                "platform": "PLACE",
                "source_url": "https://contrataciondelestado.es/wps/poc?licitacion=33",
                "status": "success",
                "finished_at": "2026-07-20T10:00:00",
                "capabilities": {"documents": True, "questions_and_answers": False},
                "artifacts": [],
            }
        )
        with app.db_session() as conn:
            snapshot_id = save_snapshot(
                conn,
                licitacion_id=33,
                platform="PLACE",
                snapshot=snapshot,
                source="monitor",
                execution_id=None,
                timestamp="2026-07-20T10:00:00",
            )
            set_monitor_baseline(
                conn,
                licitacion_id=33,
                snapshot_id=snapshot_id,
                execution_id=None,
                reason="migration",
                timestamp="2026-07-20T10:00:00",
            )
        handler = make_download_handler(app, path="/api/tender-monitor/licitaciones/33")
        attach_monitor_context(handler, app, root)
        handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["licitacion"]["id"] == 33
    assert payload["monitor"]["followed"] is True
    assert payload["monitor"]["prepared"] is True
    assert payload["monitor"]["baseline"]["snapshot_id"] == snapshot_id
    assert payload["monitor"]["baseline"]["reason"] == "migration"
    assert payload["monitor"]["baseline"]["completeness"]["documents"] == "complete"


def test_monitor_manual_permissions_and_worker_are_shared(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    launched: list[int] = []
    with temporary_download_app(app):
        prepare_followed_licitacion(app, root)

        reviewer_global = make_download_handler(
            app,
            path="/api/tender-monitor/cycles",
            csrf_token=VALID_CSRF_TOKEN,
            payload={},
        )
        attach_monitor_context(reviewer_global, app, root, role="nuria", launched=launched)
        reviewer_global.do_POST()

        reviewer_individual = make_download_handler(
            app,
            path="/api/tender-monitor/licitaciones/33/cycles",
            csrf_token=VALID_CSRF_TOKEN,
            payload={},
        )
        attach_monitor_context(reviewer_individual, app, root, role="nuria", launched=launched)
        reviewer_individual.do_POST()

        overlapping_global = make_download_handler(
            app,
            path="/api/tender-monitor/cycles",
            csrf_token=VALID_CSRF_TOKEN,
            payload={},
        )
        attach_monitor_context(overlapping_global, app, root, launched=launched)
        overlapping_global.do_POST()

    assert reviewer_global.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert reviewer_individual.responses[-1][0] == HTTPStatus.ACCEPTED
    assert overlapping_global.responses[-1][0] == HTTPStatus.CONFLICT
    assert launched == [reviewer_individual.responses[-1][1]["cycle_id"]]


def test_admin_can_enqueue_forced_baseline_but_reviewer_cannot(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    launched: list[int] = []
    with temporary_download_app(app):
        prepare_followed_licitacion(app, root)
        reviewer = make_download_handler(
            app,
            path="/api/tender-monitor/licitaciones/33/rebuild-baseline",
            csrf_token=VALID_CSRF_TOKEN,
            payload={},
        )
        attach_monitor_context(reviewer, app, root, role="nuria", launched=launched)
        reviewer.do_POST()

        admin = make_download_handler(
            app,
            path="/api/tender-monitor/licitaciones/33/rebuild-baseline",
            csrf_token=VALID_CSRF_TOKEN,
            payload={},
        )
        attach_monitor_context(admin, app, root, launched=launched)
        admin.do_POST()
        cycle_id = admin.responses[-1][1]["cycle_id"]
        with app.db_session() as conn:
            row = conn.execute(
                "SELECT origin, metadata_json FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)
            ).fetchone()

    assert reviewer.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert admin.responses[-1][0] == HTTPStatus.ACCEPTED
    assert row["origin"] == "manual_baseline_rebuild"
    assert '"force_baseline":true' in row["metadata_json"]
    assert launched == [cycle_id]


def test_monitor_mutations_require_csrf_before_launch(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    launched: list[int] = []
    with temporary_download_app(app):
        handler = make_download_handler(app, path="/api/tender-monitor/cycles", payload={})
        attach_monitor_context(handler, app, root, launched=launched)
        handler.do_POST()

    assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert launched == []


def test_monitor_follow_endpoint_creates_and_removes_exact_marker(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    folder = root / "2026" / "licitacion 33"
    folder.mkdir(parents=True)
    with temporary_download_app(app):
        insert_licitacion_with_id(app, 33, str(folder))
        create_handler = make_download_handler(
            app,
            path="/api/tender-monitor/licitaciones/33/follow",
            csrf_token=VALID_CSRF_TOKEN,
            payload={"active": True},
        )
        attach_monitor_context(create_handler, app, root)
        create_handler.do_POST()
        marker = folder / "EnSeguimiento.llangon"
        assert marker.is_file()

        remove_handler = make_download_handler(
            app,
            path="/api/tender-monitor/licitaciones/33/follow",
            csrf_token=VALID_CSRF_TOKEN,
            payload={"active": False},
        )
        attach_monitor_context(remove_handler, app, root)
        remove_handler.do_POST()

    assert create_handler.responses[-1][0] == HTTPStatus.OK
    assert remove_handler.responses[-1][0] == HTTPStatus.OK
    assert not marker.exists()


def test_monitor_settings_are_admin_only_and_cannot_enable_automatic_mode(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    with temporary_download_app(app):
        reviewer = make_download_handler(app, path="/api/tender-monitor/settings")
        attach_monitor_context(reviewer, app, root, role="nuria")
        reviewer.do_GET()

        admin = make_download_handler(
            app,
            path="/api/tender-monitor/settings",
            csrf_token=VALID_CSRF_TOKEN,
            payload={"values": {"automatic_enabled": True}},
        )
        attach_monitor_context(admin, app, root)
        admin.do_PATCH()

    assert reviewer.responses[-1][0] == HTTPStatus.FORBIDDEN
    assert admin.responses[-1][0] == HTTPStatus.CONFLICT
    assert "no puede activarse" in admin.responses[-1][1]["error"]


def test_reviewer_cycle_detail_redacts_technical_error_and_log(tmp_path: Path) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaMonitor"
    root.mkdir()
    with temporary_download_app(app):
        prepare_followed_licitacion(app, root)
        with app.db_session() as conn:
            from webapp.infonalia_webapp.monitor.tender_repository import create_cycle, create_execution
            from webapp.infonalia_webapp.monitor.tender_schema import ensure_tender_monitor_schema

            ensure_tender_monitor_schema(conn)
            cycle_id = create_cycle(conn, origin="test", requested_by="admin_test")
            execution_id = create_execution(
                conn,
                cycle_id=cycle_id,
                licitacion_id=33,
                platform="PLACE",
                timestamp="2026-07-20T10:00:00",
            )
            conn.execute(
                "UPDATE tender_monitor_executions SET status = 'error', error_message = 'secreto técnico', log_json = '[\"traza\"]' WHERE id = ?",
                (execution_id,),
            )
            conn.execute(
                "INSERT INTO tender_monitor_incidents (cycle_id, execution_id, licitacion_id, phase, code, summary, technical_detail, dedupe_key, created_at) VALUES (?, ?, 33, 'download', 'E', 'Resumen', 'detalle técnico', 'test', '2026-07-20T10:00:00')",
                (cycle_id, execution_id),
            )
        handler = make_download_handler(app, path=f"/api/tender-monitor/cycles/{cycle_id}")
        attach_monitor_context(handler, app, root, role="nuria")
        handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert "technical_detail" not in payload["incidents"][0]
    assert "error_message" not in payload["executions"][0]
    assert "log" not in payload["executions"][0]
