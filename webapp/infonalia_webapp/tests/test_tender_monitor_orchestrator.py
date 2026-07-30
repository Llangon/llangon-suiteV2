from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

import webapp.infonalia_webapp.monitor.tender_orchestrator as tender_orchestrator

from herramientas_python.descargadores.common.run_result import (
    DownloadArtifact,
    DownloadRunResult,
    PlatformCapabilities,
)
from webapp.infonalia_webapp.ai.queue import ensure_ai_schema
from webapp.infonalia_webapp.monitor.markers import FOLLOW_MARKER_NAME
from webapp.infonalia_webapp.monitor.snapshots import read_technical_sidecar, snapshot_from_result
from webapp.infonalia_webapp.monitor.tender_api import TenderMonitorAPIContext, dispatch_get
from webapp.infonalia_webapp.monitor.tender_orchestrator import (
    TenderMonitorDependencies,
    retry_batch_ai,
    retry_notification,
    run_tender_monitor_cycle,
    send_consolidated_incident_report,
)
from webapp.infonalia_webapp.monitor.tender_repository import (
    create_cycle,
    save_snapshot,
    set_monitor_baseline,
)
from webapp.infonalia_webapp.monitor.tender_schema import ensure_tender_monitor_schema


CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)


def make_result(*names: str, status: str = "success", hashes: dict[str, str] | None = None) -> DownloadRunResult:
    hashes = hashes or {}
    artifacts = [
        DownloadArtifact(
            name=name,
            status="created",
            source_url=f"https://example.test/docs/{name}",
            path=name,
            sha256=hashes.get(name, f"hash-{name}"),
        )
        for name in names
    ]
    return DownloadRunResult(
        platform="PLACE",
        source_url="https://contrataciondelestado.es/tender/1",
        started_at="2026-07-20T09:00:00",
        finished_at="2026-07-20T09:01:00",
        status=status,
        capabilities=CAPABILITIES,
        tender_id="EXP-1",
        changes_detected=bool(names),
        artifacts=artifacts,
        documents_found=len(artifacts),
        documents_downloaded=len(artifacts),
        documents_new=len(artifacts),
    )


def make_xunta_result(*names: str, status: str = "success") -> DownloadRunResult:
    artifacts = [
        DownloadArtifact(
            name=name,
            status="reused",
            source_url=f"https://www.contratosdegalicia.gal/descargaG?N=827794&T={index}",
            path=name,
            sha256=f"xunta-hash-{index}",
        )
        for index, name in enumerate(names, 1)
    ]
    return DownloadRunResult(
        platform="XUNTA_DE_GALICIA",
        source_url="https://www.contratosdegalicia.gal/licitacion?N=827794",
        started_at="2026-07-20T09:00:00",
        finished_at="2026-07-20T09:01:00",
        status=status,
        capabilities=CAPABILITIES,
        tender_id="827794",
        artifacts=artifacts,
        documents_found=len(artifacts),
        recoverable_issues=(
            ["XUNTA_RECAPTCHA_BLOCKED: reto interactivo"] if status == "partial" else []
        ),
    )


def make_question_result(platform: str, state_path: Path) -> DownloadRunResult:
    return DownloadRunResult(
        platform=platform,
        source_url="https://example.test/tender/questions",
        started_at="2026-07-20T09:00:00",
        finished_at="2026-07-20T09:01:00",
        status="success",
        capabilities=PlatformCapabilities(documents=True, questions_and_answers=True),
        tender_id="EXP-Q-1",
        changes_detected=False,
        state_path=str(state_path),
        questions={"query_successful": True, "snapshot_complete": True, "no_changes": True},
        block_completeness={"documents": "complete", "questions": "complete"},
    )


def prepare_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            expediente TEXT,
            objeto TEXT,
            plataforma TEXT,
            enlace_perfil TEXT,
            ruta_carpeta TEXT
        );
        CREATE TABLE usuarios (
            username TEXT PRIMARY KEY,
            display_name TEXT,
            email TEXT,
            role TEXT,
            active INTEGER,
            telegram_chat_id TEXT,
            telegram_notifications_enabled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE automation_tasks (
            key TEXT PRIMARY KEY, enabled INTEGER, schedule_value TEXT, updated_at TEXT, updated_by TEXT
        );
        """
    )
    ensure_ai_schema(conn)
    ensure_tender_monitor_schema(conn)
    conn.commit()
    conn.close()


def create_followed_tender(db_path: Path, root: Path, *, licitacion_id: int = 1) -> Path:
    folder = root / "2026" / f"EXP-{licitacion_id}"
    folder.mkdir(parents=True)
    (folder / f"{licitacion_id}.llangon").write_text("", encoding="utf-8")
    (folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO licitaciones (id, expediente, objeto, plataforma, enlace_perfil, ruta_carpeta)
        VALUES (?, ?, ?, 'PLACE', 'https://contrataciondelestado.es/tender/1', ?)
        """,
        (licitacion_id, f"EXP-{licitacion_id}", f"Servicio {licitacion_id}", str(folder)),
    )
    conn.commit()
    conn.close()
    return folder


def add_recipient(db_path: Path, *, email: bool = True, telegram: bool = True, incident_admin: bool = True) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO usuarios (
            username, display_name, email, role, active,
            telegram_chat_id, telegram_notifications_enabled
        ) VALUES ('admin', 'Administrador', 'admin@example.test', 'admin', 1, '12345', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO tender_monitor_recipients (
            username, email_enabled, telegram_enabled, incident_admin, updated_at, updated_by
        ) VALUES ('admin', ?, ?, ?, '2026-07-20T09:00:00', 'test')
        """,
        (1 if email else 0, 1 if telegram else 0, 1 if incident_admin else 0),
    )
    conn.commit()
    conn.close()


def create_monitor_cycle(
    db_path: Path,
    *,
    licitacion_id: int | None = None,
    metadata: dict[str, object] | None = None,
) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cycle_id = create_cycle(
        conn,
        origin="manual_individual" if licitacion_id else "manual_global",
        requested_by="admin",
        licitacion_id=licitacion_id,
        metadata=metadata,
    )
    conn.commit()
    conn.close()
    return cycle_id


def seed_monitor_baseline(
    db_path: Path,
    folder: Path,
    result: DownloadRunResult,
    *,
    licitacion_id: int = 1,
) -> int:
    snapshot = snapshot_from_result(result, destination=folder, captured_at="2026-07-20T08:00:00")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    snapshot_id = save_snapshot(
        conn,
        licitacion_id=licitacion_id,
        platform=result.platform,
        snapshot=snapshot,
        source="monitor",
        execution_id=None,
        timestamp="2026-07-20T08:00:00",
    )
    set_monitor_baseline(
        conn,
        licitacion_id=licitacion_id,
        snapshot_id=snapshot_id,
        execution_id=None,
        reason="migration",
        timestamp="2026-07-20T08:00:00",
    )
    conn.commit()
    conn.close()
    return snapshot_id


def dependencies(downloader, sent_email: list, sent_telegram: list, *, email_fails: bool = False):
    def email_sender(to, subject, text, html):
        sent_email.append((to, subject, text, html))
        return (None, "fallo simulado") if email_fails else ("2026-07-20T09:05:00", None)

    def telegram_sender(user, message):
        sent_telegram.append((user["username"], message))
        return {"ok": True, "message_id": "77"}

    return TenderMonitorDependencies(
        downloader=downloader,
        email_sender=email_sender,
        telegram_sender=telegram_sender,
        now=lambda: datetime(2026, 7, 20, 9, 5, 0),
        sleep=lambda _seconds: None,
        suite_base_url="http://127.0.0.1:8787",
    )


def test_old_tender_without_state_rebuilds_baseline_without_ai_or_notifications(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    emails: list = []
    telegram: list = []
    cycle_id = create_monitor_cycle(db_path, licitacion_id=1)

    report = run_tender_monitor_cycle(
        cycle_id,
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf"), emails, telegram),
    )

    assert report["status"] == "completed"
    assert emails == [] and telegram == []
    assert (folder / ".llangon-monitor" / "technical_snapshot.json").is_file()
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM tender_monitor_executions").fetchone()
    assert row[0] == "baseline_rebuilt"
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 0


def test_individual_cycle_uses_same_canonical_folder_as_followed_listing(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    stale_folder = root / "2026" / "07 JULIO" / "carpeta antigua"
    canonical_folder = root / "2026" / "07 JULIO" / "licitacion real"
    stale_folder.mkdir(parents=True)
    canonical_folder.mkdir(parents=True)
    (canonical_folder / "335.llangon").write_text("", encoding="utf-8")
    (canonical_folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    prepare_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO licitaciones (id, expediente, objeto, plataforma, enlace_perfil, ruta_carpeta)
        VALUES (335, ?, 'Servicio de prueba', 'PLACE',
                'https://contrataciondelestado.es/tender/335', ?)
        """,
        ("CS/AH02/1101474371/27/AMUP", r"2026\07 JULIO\carpeta antigua"),
    )
    conn.commit()
    conn.close()

    listing = dispatch_get(
        "/api/tender-monitor/followed",
        "",
        TenderMonitorAPIContext(
            db_path=db_path,
            user={"username": "admin", "role": "admin"},
            root=root,
        ),
    )
    assert listing is not None
    assert listing.payload["items"][0]["id"] == 335
    listed_folder = Path(listing.payload["items"][0]["folder_path"]).resolve(strict=True)
    assert listed_folder == canonical_folder.resolve(strict=True)

    downloaded_to: list[Path] = []

    def fake_downloader(_platform, _url, destination, **_options):
        downloaded_to.append(Path(destination).resolve(strict=True))
        return make_result("pliego.pdf")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path, licitacion_id=335),
        db_path=db_path,
        root=root,
        dependencies=dependencies(fake_downloader, [], []),
    )

    assert report["results"] == [{"licitacion_id": 335, "status": "baseline_rebuilt"}]
    assert downloaded_to == [listed_folder]
    conn = sqlite3.connect(db_path)
    execution = conn.execute(
        "SELECT status, preparation_status, preparation_reason FROM tender_monitor_executions"
    ).fetchone()
    assert execution == ("baseline_rebuilt", "prepared", None)


def test_monitor_notifies_remote_novelty_even_when_normal_download_already_reused_file(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    known = make_result("pliego.pdf", "acta.pdf")
    known.artifacts[1] = DownloadArtifact(
        name="acta.pdf",
        status="reused",
        source_url="https://example.test/docs/acta.pdf",
        path="acta.pdf",
        sha256="hash-acta.pdf",
    )
    emails: list = []
    telegram: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: known, emails, telegram),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "notified"}]
    assert len(emails) == 1 and len(telegram) == 1
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 1
    assert conn.execute(
        "SELECT change_type FROM tender_monitor_differences"
    ).fetchone()[0] == "document_new"


def test_legacy_sidecar_ahead_is_ignored_and_replaced_after_confirmed_review(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False, incident_admin=False)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    legacy = snapshot_from_result(make_result("pliego.pdf", "acta.pdf"), destination=folder)
    sidecar_path = folder / ".llangon-monitor" / "technical_snapshot.json"
    sidecar_path.parent.mkdir(parents=True)
    sidecar_path.write_text(json.dumps(legacy), encoding="utf-8")
    emails: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("pliego.pdf", "acta.pdf"),
            emails,
            [],
        ),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "notified"}]
    assert len(emails) == 1
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE phase = 'baseline'"
    ).fetchone()[0] == "LEGACY_SIDECAR_IGNORED"
    sidecar = read_technical_sidecar(folder)
    assert sidecar is not None and sidecar["writer"] == "monitor"
    assert sidecar["snapshot_id"] == conn.execute(
        "SELECT snapshot_id FROM tender_monitor_baselines WHERE licitacion_id = 1"
    ).fetchone()[0]


def test_legacy_sidecar_equal_to_sqlite_baseline_is_repaired_without_incident(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    baseline_result = make_result("pliego.pdf")
    seed_monitor_baseline(db_path, folder, baseline_result)
    legacy = snapshot_from_result(baseline_result, destination=folder)
    sidecar_path = folder / ".llangon-monitor" / "technical_snapshot.json"
    sidecar_path.parent.mkdir(parents=True)
    sidecar_path.write_text(json.dumps(legacy), encoding="utf-8")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: baseline_result, [], []),
    )

    assert report["status"] == "completed"
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_incidents").fetchone()[0] == 0
    sidecar = read_technical_sidecar(folder)
    assert sidecar is not None and sidecar["writer"] == "monitor"


def test_orphaned_legacy_sidecar_without_sqlite_baseline_is_silently_replaced(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    legacy = snapshot_from_result(make_result("antiguo.pdf"), destination=folder)
    sidecar_path = folder / ".llangon-monitor" / "technical_snapshot.json"
    sidecar_path.parent.mkdir(parents=True)
    sidecar_path.write_text(json.dumps(legacy), encoding="utf-8")
    current = make_result("oficial.pdf")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: current, [], []),
    )

    assert report["status"] == "completed"
    assert report["results"] == [{"licitacion_id": 1, "status": "baseline_rebuilt"}]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_incidents").fetchone()[0] == 0
    baseline_id = conn.execute(
        "SELECT snapshot_id FROM tender_monitor_baselines WHERE licitacion_id = 1"
    ).fetchone()[0]
    sidecar = read_technical_sidecar(folder)
    assert sidecar is not None and sidecar["writer"] == "monitor"
    assert sidecar["snapshot_id"] == baseline_id


@pytest.mark.parametrize(
    "invalid_sidecar",
    (
        {"schema_version": "invalid"},
        {
            "schema_version": 2,
            "writer": "monitor",
            "snapshot_id": "invalid",
            "fingerprint": "not-the-baseline",
            "snapshot": {},
        },
    ),
)
def test_malformed_sidecar_never_blocks_sqlite_baseline_review(
    tmp_path: Path,
    invalid_sidecar: dict[str, object],
) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    sidecar_path = folder / ".llangon-monitor" / "technical_snapshot.json"
    sidecar_path.parent.mkdir(parents=True)
    sidecar_path.write_text(json.dumps(invalid_sidecar), encoding="utf-8")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("pliego.pdf", "acta.pdf"),
            [],
            [],
        ),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "no_recipients"}]
    sidecar = read_technical_sidecar(folder)
    assert sidecar is not None and sidecar["writer"] == "monitor"


def test_monitor_defers_when_direct_download_holds_shared_tender_lease(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    create_followed_tender(db_path, root)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO tender_monitor_leases (
            lease_key, owner, acquired_at, heartbeat_at, expires_at, metadata_json
        ) VALUES ('tender-io:licitacion:1', 'download-job:9', '2026-07-20T09:00:00',
                  '2026-07-20T09:00:00', '2026-07-20T10:00:00', '{}')
        """
    )
    conn.commit()
    conn.close()
    calls = 0

    def downloader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return make_result("pliego.pdf")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(downloader, [], []),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "deferred_busy"}]
    assert calls == 0
    conn = sqlite3.connect(db_path)
    execution = conn.execute(
        "SELECT status, error_code FROM tender_monitor_executions"
    ).fetchone()
    assert execution == ("deferred_busy", "TENDER_OPERATION_BUSY")
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_baselines").fetchone()[0] == 0


def test_sidecar_write_failure_keeps_sqlite_baseline_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    create_followed_tender(db_path, root)
    monkeypatch.setattr(
        tender_orchestrator,
        "write_monitor_sidecar_cache",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fallo de sidecar simulado")),
    )

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf"), [], []),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "baseline_rebuilt"}]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_baselines").fetchone()[0] == 1
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE phase = 'sidecar'"
    ).fetchone()[0] == "SIDECAR_WRITE_FAILED"


def test_batch_persistence_failure_rolls_back_snapshot_and_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    previous_snapshot_id = seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    monkeypatch.setattr(
        tender_orchestrator,
        "create_batch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("fallo de lote simulado")
        ),
    )

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("pliego.pdf", "acta.pdf"),
            [],
            [],
        ),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "error"}]
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT snapshot_id FROM tender_monitor_baselines WHERE licitacion_id = 1"
    ).fetchone()[0] == previous_snapshot_id
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_snapshots").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("platform", "state_directory"),
    (("PLACE", ".llangon-place"), ("CATALUNYA", ".llangon-catalunya")),
)
def test_monitor_detects_question_recorded_by_direct_download_even_if_sync_says_no_changes(
    tmp_path: Path,
    platform: str,
    state_directory: str,
) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False)
    state_path = folder / state_directory / "questions_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"questions": {}}), encoding="utf-8")
    baseline_result = make_question_result(platform, state_path)
    seed_monitor_baseline(db_path, folder, baseline_result)
    state_path.write_text(
        json.dumps(
            {
                "questions": {
                    "Q-1": {
                        "stable_id": "Q-1",
                        "number": 1,
                        "question_hash": "question-hash",
                        "answer_hash": "answer-hash",
                        "attachments_hash": "attachments-hash",
                        "status": "published",
                        "versions": [{"fingerprint": "version-1"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    emails: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_question_result(platform, state_path),
            emails,
            [],
        ),
    )

    assert report["results"] == [{"licitacion_id": 1, "status": "notified"}]
    assert len(emails) == 1
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT change_type FROM tender_monitor_differences"
    ).fetchone()[0] == "question_new"


def test_invalid_monitor_root_finishes_cycle_and_records_configuration_incident(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    prepare_db(db_path)
    cycle_id = create_monitor_cycle(db_path)

    report = run_tender_monitor_cycle(
        cycle_id,
        db_path=db_path,
        root=tmp_path / "Dropbox" / "produccion",
        dependencies=dependencies(lambda *_args, **_kwargs: make_result(), [], []),
    )

    assert report["status"] == "failed"
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT status FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)
    ).fetchone()[0] == "failed"
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE cycle_id = ?", (cycle_id,)
    ).fetchone()[0] == "MONITOR_CONFIGURATION_INVALID"


def test_multiple_new_documents_create_one_batch_one_email_and_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    emails: list = []
    telegram: list = []
    current = make_result("pliego.pdf", "acta.pdf", "resolucion.pdf")
    deps = dependencies(lambda *_args, **_kwargs: current, emails, telegram)

    first = run_tender_monitor_cycle(create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps)
    second = run_tender_monitor_cycle(create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps)

    assert first["status"] == second["status"] == "completed"
    assert len(emails) == 1
    assert len(telegram) == 1
    assert emails[0][1] == "[Llangon Monitor] EXP-1"
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_differences").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_notifications").fetchone()[0] == 2


def test_email_failure_does_not_block_telegram_and_is_consolidated_once(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    emails: list = []
    telegram: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("pliego.pdf", "nuevo.pdf"),
            emails,
            telegram,
            email_fails=True,
        ),
    )

    assert report["status"] == "completed_with_incidents"
    assert len(telegram) == 1
    assert len(emails) == 3  # dos intentos limitados de novedades + un resumen consolidado
    conn = sqlite3.connect(db_path)
    statuses = conn.execute(
        "SELECT channel, status FROM tender_monitor_notifications ORDER BY channel"
    ).fetchall()
    assert statuses == [("email", "failed"), ("telegram", "sent")]
    assert conn.execute(
        "SELECT attempt_count FROM tender_monitor_notifications WHERE channel = 'email'"
    ).fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_incident_reports").fetchone()[0] == 1


def test_no_global_recipients_records_no_recipients_without_failing_cycle(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf", "nuevo.pdf"), [], []),
    )

    assert report["status"] == "completed"
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT status FROM tender_monitor_executions").fetchone()[0] == "no_recipients"
    assert conn.execute("SELECT notification_status FROM tender_monitor_batches").fetchone()[0] == "no_recipients"


def test_partial_response_preserves_previous_documents_and_sends_one_incident_report(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False)
    seed_monitor_baseline(db_path, folder, make_result("uno.pdf", "dos.pdf"))
    emails: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("uno.pdf", status="partial"), emails, []
        ),
    )

    assert report["status"] == "completed_with_incidents"
    assert len(emails) == 1
    assert "Incidencias del ciclo" in emails[0][1]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 0
    saved = conn.execute(
        "SELECT snapshot_json FROM tender_monitor_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    assert "uno.pdf" in saved and "dos.pdf" in saved


def test_partial_verified_document_notifies_but_failed_artifact_never_reaches_batch_or_baseline(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False, incident_admin=False)
    seed_monitor_baseline(db_path, folder, make_result("uno.pdf", "dos.pdf"))
    current = make_result("uno.pdf", "acta-publicada.pdf", status="partial")
    current.artifacts.append(
        DownloadArtifact(
            name="proteccion-javascript.html",
            status="failed",
            source_url="https://contrataciondelestado.es/documento/bloqueado",
            path="proteccion-javascript.html",
            sha256="html-blocked",
            content_type="text/html",
            size=5205,
        )
    )
    emails: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(lambda *_args, **_kwargs: current, emails, []),
    )

    assert report["status"] == "completed_with_incidents"
    assert report["results"] == [{"licitacion_id": 1, "status": "notified"}]
    assert len(emails) == 1
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 1
    assert conn.execute(
        "SELECT change_type, title FROM tender_monitor_differences"
    ).fetchall() == [("document_new", "acta-publicada.pdf")]
    current_snapshot_id, saved = conn.execute(
        "SELECT id, snapshot_json FROM tender_monitor_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert conn.execute(
        "SELECT snapshot_id FROM tender_monitor_baselines WHERE licitacion_id = 1"
    ).fetchone()[0] == current_snapshot_id
    saved_snapshot = json.loads(saved)
    saved_items = saved_snapshot["blocks"]["documents"]["items"].values()
    assert {item["name"] for item in saved_items} == {
        "uno.pdf",
        "dos.pdf",
        "acta-publicada.pdf",
    }


def test_xunta_recaptcha_partial_uses_registry_name_and_preserves_monitor_baseline(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE licitaciones SET plataforma = ?, enlace_perfil = ? WHERE id = 1",
        (
            "Xunta de Galicia",
            "https://www.contratosdegalicia.gal/licitacion?N=827794",
        ),
    )
    conn.commit()
    conn.close()
    seed_monitor_baseline(db_path, folder, make_xunta_result("memoria.pdf"))
    calls: list[tuple[str, str, Path]] = []

    def downloader(platform, source_url, destination, **_options):
        calls.append((platform, source_url, Path(destination)))
        return make_xunta_result("memoria.pdf", status="partial")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(downloader, [], []),
    )

    assert calls == [
        (
            "XUNTA_DE_GALICIA",
            "https://www.contratosdegalicia.gal/licitacion?N=827794",
            folder,
        )
    ]
    assert report["status"] == "completed_with_incidents"
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 0
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE phase = 'download'"
    ).fetchone()[0] == "PARTIAL_PLATFORM_RESPONSE"


def test_ai_failure_notifies_without_analysis_and_records_incident(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE tender_monitor_settings SET value = '1' WHERE key = 'ai_enabled'")
    conn.commit()
    conn.close()
    emails: list = []
    deps = dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf", "acta-fallida.pdf"), emails, [])
    deps.ai_requester = lambda *_args: {"message": "fallo IA simulado"}

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps
    )

    assert report["status"] == "completed_with_incidents"
    assert "sin análisis" not in emails[0][2]
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT code FROM tender_monitor_incidents WHERE phase = 'ai'"
    ).fetchone()[0] == "AI_QUEUE_REJECTED"
    assert conn.execute("SELECT ai_status FROM tender_monitor_batches").fetchone()[0] == "failed"


def test_ai_timeout_is_terminal_and_does_not_block_notification(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE tender_monitor_settings SET value = '1' WHERE key = 'ai_enabled'")
    conn.execute("UPDATE tender_monitor_settings SET value = '5' WHERE key = 'ai_timeout_seconds'")
    conn.commit()
    conn.close()
    emails: list = []

    def pending_ai(conn, licitacion_id, paths, requested_by):
        cursor = conn.execute(
            """
            INSERT INTO ai_analysis_jobs (
                licitacion_id, document_hash, status, provider, model,
                requested_by, created_at, selected_documents_json
            ) VALUES (?, 'timeout-hash', 'pending', 'gemini', 'fake', ?, ?, '[]')
            """,
            (licitacion_id, requested_by, "2026-07-20T09:00:00"),
        )
        return {"job_id": int(cursor.lastrowid), "document_hash": "timeout-hash"}

    ticks = iter([0.0, 6.0])
    monkeypatch.setattr(tender_orchestrator.time, "monotonic", lambda: next(ticks))
    deps = dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf", "resolucion.pdf"), emails, [])
    deps.ai_requester = pending_ai
    deps.ai_starter = lambda _conn, _job_id: {"ok": True}

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps
    )

    assert report["status"] == "completed_with_incidents"
    assert "sin análisis" not in emails[0][2]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT error_code FROM ai_analysis_jobs").fetchone()[0] == "MONITOR_AI_TIMEOUT"
    assert conn.execute("SELECT code FROM tender_monitor_incidents WHERE phase = 'ai'").fetchone()[0] == "AI_TIMEOUT"


def test_telegram_failure_does_not_block_email(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    emails: list = []
    telegram_attempts: list = []
    deps = dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf", "nuevo.pdf"), emails, [])

    def failed_telegram(user, message):
        telegram_attempts.append((user["username"], message))
        return {"ok": False, "error": "fallo Telegram simulado"}

    deps.telegram_sender = failed_telegram
    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps
    )

    assert report["status"] == "completed_with_incidents"
    assert len(telegram_attempts) == 2
    assert emails[0][1] == "[Llangon Monitor] EXP-1"
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT status FROM tender_monitor_notifications WHERE channel = 'email'"
    ).fetchone()[0] == "sent"
    assert conn.execute(
        "SELECT status FROM tender_monitor_notifications WHERE channel = 'telegram'"
    ).fetchone()[0] == "failed"


def test_multiple_tender_incidents_generate_one_report_and_retry_does_not_download(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    create_followed_tender(db_path, root, licitacion_id=1)
    create_followed_tender(db_path, root, licitacion_id=2)
    add_recipient(db_path, telegram=False)
    emails: list = []
    download_calls = 0

    def failed_downloader(*_args, **_kwargs):
        nonlocal download_calls
        download_calls += 1
        raise RuntimeError("fallo permanente")

    failed_report_deps = dependencies(failed_downloader, emails, [], email_fails=True)
    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=failed_report_deps
    )
    assert report["incident_report_status"] == "failed"
    assert download_calls == 2
    assert len(emails) == 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    retried_emails: list = []
    successful_deps = dependencies(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar")),
        retried_emails,
        [],
    )
    status = send_consolidated_incident_report(
        conn,
        deps=successful_deps,
        cycle_id=report["cycle_id"],
    )
    conn.commit()

    assert status == "sent"
    assert download_calls == 2
    assert len(retried_emails) == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM tender_monitor_incidents WHERE cycle_id = ?", (report["cycle_id"],)
    ).fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_incident_reports").fetchone()[0] == 1


def test_forced_baseline_rebuild_never_creates_batch_or_notification(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path)
    seed_monitor_baseline(db_path, folder, make_result("antiguo.pdf"))
    emails: list = []
    telegram: list = []

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path, licitacion_id=1, metadata={"force_baseline": True}),
        db_path=db_path,
        root=root,
        dependencies=dependencies(
            lambda *_args, **_kwargs: make_result("nuevo.pdf"), emails, telegram
        ),
    )

    assert report["status"] == "completed"
    assert report["results"][0]["status"] == "baseline_rebuilt"
    assert emails == [] and telegram == []
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 0


def test_failure_of_one_tender_does_not_stop_next_tender(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    first_folder = create_followed_tender(db_path, root, licitacion_id=1)
    second_folder = create_followed_tender(db_path, root, licitacion_id=2)
    seed_monitor_baseline(db_path, first_folder, make_result("one.pdf"), licitacion_id=1)
    seed_monitor_baseline(db_path, second_folder, make_result("two.pdf"), licitacion_id=2)
    calls = 0

    def downloader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("fallo permanente simulado")
        return make_result("two.pdf")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(downloader, [], []),
    )

    assert calls == 2
    assert report["processed"] == 2
    assert report["status"] == "completed_with_incidents"
    assert [item["status"] for item in report["results"]] == ["error", "no_changes"]


def test_transient_failed_result_is_retried_with_a_new_downloader_call(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    baseline = make_result("estable.pdf")
    seed_monitor_baseline(db_path, folder, baseline)
    calls = 0
    logs: list[str] = []

    def downloader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return DownloadRunResult.failed(
                platform="PLACE",
                source_url="https://contrataciondelestado.es/tender/1",
                capabilities=CAPABILITIES,
                error=TimeoutError("Connection timed out"),
                started_at="2026-07-20T09:00:00",
            )
        return make_result("estable.pdf")

    deps = dependencies(downloader, [], [])
    deps.logger = logs.append
    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=deps,
    )

    assert calls == 2
    assert report["status"] == "completed"
    assert report["results"] == [{"licitacion_id": 1, "status": "no_changes"}]
    assert any("fallo transitorio en intento 1" in line for line in logs)
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT attempt_count FROM tender_monitor_executions"
    ).fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_incidents").fetchone()[0] == 0
    conn.close()


def test_structured_retryable_failure_does_not_depend_on_error_wording(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    seed_monitor_baseline(db_path, folder, make_result("estable.pdf"))
    calls = 0

    def downloader(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return DownloadRunResult.failed(
                platform="JUNTA_ANDALUCIA",
                source_url="https://www.juntadeandalucia.es/tender/1",
                capabilities=CAPABILITIES,
                error="La aplicación no produjo contenido",
                error_code="JUNTA_EMPTY_RENDER",
                retryable=True,
                started_at="2026-07-24T12:00:00",
            )
        return make_result("estable.pdf")

    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path),
        db_path=db_path,
        root=root,
        dependencies=dependencies(downloader, [], []),
    )

    assert calls == 2
    assert report["status"] == "completed"
    assert report["results"] == [{"licitacion_id": 1, "status": "no_changes"}]


def test_new_acta_uses_existing_ai_queue_and_notification_waits_for_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE tender_monitor_settings SET value = '1' WHERE key = 'ai_enabled'")
    conn.commit()
    conn.close()
    emails: list = []

    def ai_requester(conn, licitacion_id, paths, requested_by):
        assert paths == ["acta-nueva.pdf"]
        cursor = conn.execute(
            """
            INSERT INTO ai_analysis_jobs (
                licitacion_id, document_hash, status, provider, model,
                requested_by, created_at, selected_documents_json
            ) VALUES (?, 'acta-hash', 'completed', 'gemini', 'fake', ?, ?, '[]')
            """,
            (licitacion_id, requested_by, "2026-07-20T09:00:00"),
        )
        job_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO ai_summaries (
                licitacion_id, document_hash, provider, model, summary_json,
                summary_text, created_at, updated_at, created_from_job_id
            ) VALUES (?, 'acta-hash', 'gemini', 'fake', '{}', 'Resumen del acta', ?, ?, ?)
            """,
            (licitacion_id, "2026-07-20T09:01:00", "2026-07-20T09:01:00", job_id),
        )
        return {"job_id": job_id, "document_hash": "acta-hash"}

    deps = dependencies(lambda *_args, **_kwargs: make_result("pliego.pdf", "acta-nueva.pdf"), emails, [])
    deps.ai_requester = ai_requester
    report = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps
    )
    repeated = run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=deps
    )

    assert report["status"] == "completed"
    assert repeated["status"] == "completed"
    assert len(emails) == 1 and "Resumen del acta" in emails[0][2]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM ai_analysis_jobs").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM tender_monitor_ai_links").fetchone()[0] == "completed"


def test_failed_email_can_be_retried_without_downloading_again(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    add_recipient(db_path, telegram=False, incident_admin=False)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    download_calls = 0

    def downloader(*_args, **_kwargs):
        nonlocal download_calls
        download_calls += 1
        return make_result("pliego.pdf", "nuevo.pdf")

    failed_deps = dependencies(downloader, [], [], email_fails=True)
    run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=failed_deps
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    notification_id = conn.execute(
        "SELECT id FROM tender_monitor_notifications WHERE channel = 'email'"
    ).fetchone()["id"]
    retried: list = []
    retry_deps = dependencies(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar")),
        retried,
        [],
    )
    result = retry_notification(conn, notification_id, deps=retry_deps)
    conn.commit()

    assert result["ok"] is True
    assert result["overall_status"] == "notified"
    assert download_calls == 1
    assert len(retried) == 1
    assert conn.execute(
        "SELECT status FROM tender_monitor_notifications WHERE id = ?", (notification_id,)
    ).fetchone()["status"] == "sent"


def test_failed_ai_can_be_retried_on_same_batch_without_downloading(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    root = tmp_path / "replica"
    prepare_db(db_path)
    folder = create_followed_tender(db_path, root)
    seed_monitor_baseline(db_path, folder, make_result("pliego.pdf"))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE tender_monitor_settings SET value = '1' WHERE key = 'ai_enabled'")
    conn.commit()
    conn.close()
    download_calls = 0

    def downloader(*_args, **_kwargs):
        nonlocal download_calls
        download_calls += 1
        return make_result("pliego.pdf", "acta-nueva.pdf")

    failed_deps = dependencies(downloader, [], [])
    failed_deps.ai_requester = lambda *_args: {"message": "cola no disponible"}
    run_tender_monitor_cycle(
        create_monitor_cycle(db_path), db_path=db_path, root=root, dependencies=failed_deps
    )

    def successful_ai_requester(conn, licitacion_id, paths, requested_by):
        cursor = conn.execute(
            """
            INSERT INTO ai_analysis_jobs (
                licitacion_id, document_hash, status, provider, model,
                requested_by, created_at, selected_documents_json
            ) VALUES (?, 'retry-hash', 'completed', 'gemini', 'fake', ?, ?, '[]')
            """,
            (licitacion_id, requested_by, "2026-07-20T09:10:00"),
        )
        job_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO ai_summaries (
                licitacion_id, document_hash, provider, model, summary_json,
                summary_text, created_at, updated_at, created_from_job_id
            ) VALUES (?, 'retry-hash', 'gemini', 'fake', '{}', 'Resumen recuperado', ?, ?, ?)
            """,
            (licitacion_id, "2026-07-20T09:11:00", "2026-07-20T09:11:00", job_id),
        )
        return {"job_id": job_id, "document_hash": "retry-hash"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    batch_id = conn.execute("SELECT id FROM tender_monitor_batches").fetchone()["id"]
    retry_deps = dependencies(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar")),
        [],
        [],
    )
    retry_deps.ai_requester = successful_ai_requester
    result = retry_batch_ai(conn, batch_id, deps=retry_deps)
    conn.commit()

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["summary"] == "Resumen recuperado"
    assert download_calls == 1
    assert conn.execute("SELECT COUNT(*) FROM tender_monitor_batches").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM tender_monitor_ai_links").fetchone()[0] == "completed"
