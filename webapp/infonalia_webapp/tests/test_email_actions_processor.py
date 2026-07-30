from __future__ import annotations

from datetime import datetime, timedelta
from email.message import EmailMessage
from http import HTTPStatus

from webapp.infonalia_webapp.email_actions import (
    ACTION_AI_SUMMARY,
    ACTION_DISCARD,
    ACTION_DOWNLOAD_REVIEW,
    ACTION_PREPARE,
    ACTION_REVIEWED,
    check_action_code,
    ensure_review_action_codes,
    generate_action_code,
)
from webapp.infonalia_webapp.email_actions_processor import (
    MailboxConfig,
    check_code_payload,
    mailbox_config_from_env,
    process_mailbox_once,
    simulate_code_payload,
)
from webapp.infonalia_webapp.services.telegram_notifications import TelegramResult
from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import insert_dia, insert_licitacion
from webapp.infonalia_webapp.tests.test_email_actions import licitacion_state, set_licitacion_state
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def make_message(subject: str, sender: str, body: str, message_id: str) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Message-ID"] = message_id
    msg.set_content(body)
    return msg.as_bytes()


class FakeIMAP:
    def __init__(self, messages: dict[bytes, dict[str, object]]):
        self.messages = messages
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.store_calls: list[tuple[bytes, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[bytes, str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def login(self, *_args):
        self.calls.append(("LOGIN", ()))
        return "OK", [b""]

    def select(self, folder):
        self.calls.append(("SELECT", (folder,)))
        return "OK", [b""]

    def uid(self, command, *args):
        normalized = str(command).upper()
        self.calls.append((normalized, args))
        if normalized == "SEARCH":
            include_seen = "UNSEEN" not in {str(arg).upper() for arg in args}
            subject_filtered = any(str(arg).upper() == "HEADER" for arg in args)
            found: list[bytes] = []
            for uid, item in self.messages.items():
                if not include_seen and item.get("seen"):
                    continue
                subject = str(item["subject"])
                if subject_filtered and "LLANGON_CMD" not in subject:
                    continue
                found.append(uid)
            return "OK", [b" ".join(found)]
        if normalized == "FETCH":
            uid = args[0]
            query = str(args[1])
            self.fetch_calls.append((uid, query))
            raw = self.messages[uid]["raw"]
            if "HEADER.FIELDS" in query:
                raw = raw.split(b"\n\n", 1)[0] + b"\n\n"
            return "OK", [(b"FETCH", raw)]
        if normalized == "STORE":
            uid = args[0]
            self.messages[uid]["seen"] = True
            self.store_calls.append((uid, args[1:]))
            return "OK", [b""]
        raise AssertionError(f"Unexpected IMAP command: {command} {args}")


def fake_config(allowed: list[str] | None = None) -> MailboxConfig:
    return MailboxConfig(
        host="imap.example.test",
        port=993,
        user="info3llangon@gmail.com",
        password="secret",
        folder="INBOX",
        allowed_senders=allowed if allowed is not None else ["nuria@example.test"],
        notify_email="info3@llangon.com",
    )


def test_mailbox_config_without_settings_uses_environment_only(monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_ACTION_ALLOWED_SENDERS", "nuria@example.test")

    config = mailbox_config_from_env()

    assert config.allowed_senders == ["nuria@example.test"]


def prepare_action(app, estado: str = "Importada") -> tuple[int, int]:
    dia_id = insert_dia(app)
    licitacion_id = insert_licitacion(app, dia_id, "EXP-PROCESSOR")
    set_licitacion_state(app, licitacion_id, estado)
    with app.db_session() as conn:
        rows = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchall()
        ensure_review_action_codes(conn, review_id=dia_id, licitaciones=rows, timestamp="2026-06-26T14:00:00")
    return dia_id, licitacion_id


def run_with_fake_imap(app, fake: FakeIMAP, **kwargs):
    return process_mailbox_once(
        db_session_factory=app.db_session,
        notification_sender=lambda *_args: None,
        config=kwargs.pop("config", fake_config()),
        imap_factory=lambda *_args, **_kwargs: fake,
        **kwargs,
    )


def download_jobs_for_licitacion(app, licitacion_id: int) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM download_jobs WHERE licitacion_id = ? ORDER BY id ASC",
            (licitacion_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def email_action_events_for_licitacion(app, licitacion_id: int) -> list[dict]:
    with app.db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM email_action_events WHERE licitacion_id = ? ORDER BY id ASC",
            (licitacion_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def enable_admin_telegram(app, *, username: str = "admin_test", enabled: bool = True, chat_id: str = "1648124154") -> None:
    with app.db_session() as conn:
        conn.execute(
            """
            INSERT INTO usuarios (
                username, password_hash, role, display_name, email,
                telegram_chat_id, telegram_notifications_enabled,
                active, created_at, updated_at
            )
            VALUES (?, 'test-hash', 'admin', 'Admin Test', 'admin@example.test', ?, ?, 1,
                    '2026-07-07T09:00:00', '2026-07-07T09:00:00')
            ON CONFLICT(username) DO UPDATE SET
                role = 'admin',
                telegram_chat_id = excluded.telegram_chat_id,
                telegram_notifications_enabled = excluded.telegram_notifications_enabled,
                active = 1,
                updated_at = excluded.updated_at
            """,
            (username, chat_id, 1 if enabled else 0),
        )


def fake_completed_download_factory(app, *, ruta: str = "2026\\07 JULIO\\07 JULIO 1200 PRUEBA") :
    def fake_execute_download_for_destination(
        *,
        licitacion_id: int,
        row,
        destino,
        ruta_guardada: str,
        download_job_id: int,
        source_url: str,
    ):
        timestamp = "2026-07-07T12:00:00"
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET ruta_carpeta = ?, updated_at = ? WHERE id = ?",
                (ruta, timestamp, licitacion_id),
            )
            app.finish_download_job(
                conn,
                download_job_id,
                status=app.DOWNLOAD_JOB_STATUS_COMPLETED,
                storage_backend="local",
                storage_uri=ruta,
                file_manifest="manifest.json",
                timestamp=timestamp,
            )
        return (
            HTTPStatus.OK,
            {
                "ok": True,
                "ruta_carpeta": ruta,
                "storage": {
                    "job_status": app.DOWNLOAD_JOB_STATUS_COMPLETED,
                },
            },
        )

    return fake_execute_download_for_destination


def fake_failed_download_factory(app, error_message: str):
    def fake_execute_download_for_destination(
        *,
        licitacion_id: int,
        row,
        destino,
        ruta_guardada: str,
        download_job_id: int,
        source_url: str,
    ):
        app._finish_failed_download_job(
            download_job_id,
            error_message,
            failure_stage="downloader",
            failure_code="DOWNLOADER_EXIT_CODE",
        )
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "ok": False,
                "error": error_message,
                "codigo": 1,
            },
        )

    return fake_execute_download_for_destination


def test_normal_mode_searches_only_llangon_cmd_and_does_not_touch_normal_mail() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app)
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"1": {
                    "subject": "Correo normal",
                    "seen": False,
                    "raw": make_message("Correo normal", "cliente@example.test", "hola", "<normal>"),
                },
                b"2": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descartar",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<cmd>",
                    ),
                },
            }
        )

        result = run_with_fake_imap(app, fake)

    assert result["mode"] == "llangon_cmd_only"
    assert result["processed"] == 1
    assert ("SEARCH", (None, "UNSEEN", "HEADER", "Subject", "LLANGON_CMD")) in fake.calls
    assert all(uid != b"1" for uid, _query in fake.fetch_calls)
    assert fake.messages[b"1"]["seen"] is False
    assert fake.messages[b"2"]["seen"] is True
    assert any("BODY.PEEK[]" in query for _uid, query in fake.fetch_calls)


def test_candidate_with_unknown_code_is_not_marked_read_by_default() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        fake = FakeIMAP(
            {
                b"7": {
                    "subject": "LLANGON_CMD 99999999901 - Descartar",
                    "seen": False,
                    "raw": make_message(
                        "LLANGON_CMD 99999999901 - Descartar",
                        "nuria@example.test",
                        "LLANGON_ACTION_CODE=99999999901",
                        "<unknown>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)

    assert result["processed"] == 0
    assert result["errors"] == 1
    assert result["errors_by_reason"]["LICITACION_NOT_FOUND"] == 1
    assert fake.messages[b"7"]["seen"] is False
    assert fake.store_calls == []


def test_late_individual_action_is_applied_notified_and_consumed_once() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE infonalia_dias SET reviewed_at = '2026-07-16T10:00:00', estado = 'Completado' WHERE id = ?",
                (dia_id,),
            )
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"8": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descartar",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<late-change>",
                    ),
                }
            }
        )
        notifications: list[tuple] = []

        result = process_mailbox_once(
            db_session_factory=app.db_session,
            notification_sender=lambda *args: notifications.append(args),
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: fake,
        )
        second = process_mailbox_once(
            db_session_factory=app.db_session,
            notification_sender=lambda *args: notifications.append(args),
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: fake,
        )

        assert result["processed"] == 1
        assert result["late_change_notifications"] == 1
        assert fake.messages[b"8"]["seen"] is True
        assert len(notifications) == 1
        assert notifications[0][0] == "info3@llangon.com"
        assert "Cambio de decisión de Nuria tras cierre" in notifications[0][1]
        assert second["candidates_seen"] == 0
        assert licitacion_state(app, licitacion_id) == "Descartada"
        with app.db_session() as conn:
            day = conn.execute(
                "SELECT reviewed_at, nuria_dirty_at, estado FROM infonalia_dias WHERE id = ?", (dia_id,)
            ).fetchone()
            history = conn.execute(
                "SELECT severity, requires_review FROM infonalia_activity_events WHERE event_type = 'late_decision_change'"
            ).fetchone()
        assert dict(day) == {
            "reviewed_at": "2026-07-16T10:00:00",
            "nuria_dirty_at": None,
            "estado": "Completado",
        }
        assert dict(history) == {"severity": "critical", "requires_review": 1}


def test_late_individual_action_without_state_change_does_not_notify() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id, licitacion_id = prepare_action(app, estado="Descartada")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE infonalia_dias SET reviewed_at = '2026-07-16T10:00:00', estado = 'Completado' WHERE id = ?",
                (dia_id,),
            )
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"9": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": False,
                    "raw": make_message(f"LLANGON_CMD {code}", "nuria@example.test", code, "<late-same>"),
                }
            }
        )
        notifications: list[tuple] = []

        result = process_mailbox_once(
            db_session_factory=app.db_session,
            notification_sender=lambda *args: notifications.append(args),
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: fake,
        )

        assert result["processed"] == 1
        assert result["late_change_notifications"] == 0
        assert notifications == []
        with app.db_session() as conn:
            history = conn.execute(
                "SELECT severity, requires_review FROM infonalia_activity_events WHERE licitacion_id = ?",
                (licitacion_id,),
            ).fetchone()
        assert dict(history) == {"severity": "attention", "requires_review": 1}


def test_closed_reviewed_action_is_ignored_marked_read_and_not_retried() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id, _licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE infonalia_dias SET reviewed_at = '2026-07-16T10:00:00', estado = 'Completado' WHERE id = ?",
                (dia_id,),
            )
        code = generate_action_code(dia_id, ACTION_REVIEWED)
        fake = FakeIMAP(
            {
                b"10": {
                    "subject": f"LLANGON_CMD {code} - Revisado",
                    "seen": False,
                    "raw": make_message(f"LLANGON_CMD {code}", "nuria@example.test", code, "<closed-99>"),
                }
            }
        )

        first = run_with_fake_imap(app, fake)
        second = run_with_fake_imap(app, fake)

        assert first["ignored_by_reason"]["REVIEW_CLOSED"] == 1
        assert fake.messages[b"10"]["seen"] is True
        assert second["candidates_seen"] == 0
        with app.db_session() as conn:
            history = conn.execute(
                "SELECT severity, result, requires_review FROM infonalia_activity_events WHERE day_id = ? ORDER BY id DESC LIMIT 1",
                (dia_id,),
            ).fetchone()
        assert dict(history) == {"severity": "attention", "result": "ignored", "requires_review": 1}


def test_late_notification_failure_does_not_rollback_and_creates_critical_event() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE infonalia_dias SET reviewed_at = '2026-07-16T10:00:00', estado = 'Completado' WHERE id = ?",
                (dia_id,),
            )
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"11": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": False,
                    "raw": make_message(f"LLANGON_CMD {code}", "nuria@example.test", code, "<smtp-fail>"),
                }
            }
        )

        def fail_notification(*_args):
            raise RuntimeError("SMTP simulado no disponible")

        result = process_mailbox_once(
            db_session_factory=app.db_session,
            notification_sender=fail_notification,
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: fake,
        )

        assert result["processed"] == 1
        assert result["late_change_notification_errors"] == 1
        assert licitacion_state(app, licitacion_id) == "Descartada"
        with app.db_session() as conn:
            failure = conn.execute(
                "SELECT severity, result, detail FROM infonalia_activity_events WHERE event_type = 'late_decision_notification_failed'"
            ).fetchone()
        assert failure["severity"] == "critical"
        assert failure["result"] == "error"
        assert "SMTP simulado" in failure["detail"]


def test_dry_run_does_not_execute_action_or_mark_read() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"5": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<dry-run>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake, dry_run=True)

        assert licitacion_state(app, licitacion_id) == "Importada"

    assert result["processed"] == 0
    assert result["ignored_by_reason"]["dry-run"] == 1
    assert fake.messages[b"5"]["seen"] is False
    assert fake.store_calls == []


def test_include_seen_searches_command_subjects_without_unseen_filter() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app)
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"2": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": True,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descartar",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<seen>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake, include_seen=True)

    assert result["processed"] == 1
    assert ("SEARCH", (None, "HEADER", "Subject", "LLANGON_CMD")) in fake.calls


def test_scan_all_peeks_headers_but_does_not_mark_non_candidates() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        fake = FakeIMAP(
            {
                b"1": {
                    "subject": "Correo normal",
                    "seen": False,
                    "raw": make_message("Correo normal", "cliente@example.test", "hola", "<normal>"),
                }
            }
        )

        result = run_with_fake_imap(app, fake, scan_all=True)

    assert result["mode"] == "scan_all"
    assert result["total_messages_seen"] == 1
    assert result["skipped_non_candidates"] == 1
    assert fake.messages[b"1"]["seen"] is False
    assert fake.store_calls == []
    assert fake.fetch_calls == [(b"1", "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM REPLY-TO MESSAGE-ID)])")]


def test_empty_allowed_senders_blocks_processing_and_keeps_mail_unread() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app)
        code = generate_action_code(licitacion_id, ACTION_DISCARD)
        fake = FakeIMAP(
            {
                b"3": {
                    "subject": f"LLANGON_CMD {code} - Descartar",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descartar",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<no-allowed>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake, config=fake_config(allowed=[]))

    assert result["errors"] == 1
    assert result["total_unauthorized_senders"] == 1
    assert result["errors_by_reason"]["NO_ALLOWED_SENDERS"] == 1
    assert fake.messages[b"3"]["seen"] is False


def test_check_code_and_simulate_code_without_imap(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("LLANGON_ACTION_ALLOWED_SENDERS", "nuria@example.test")
    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)

        existing = check_code_payload(app.db_session, code)
        missing = check_code_payload(app.db_session, "99999999901")
        simulated = simulate_code_payload(
            app.db_session,
            code=code,
            from_email="nuria@example.test",
            dry_run=True,
        )

        with app.db_session() as conn:
            direct = check_action_code(
                conn,
                code=code,
                sender_email="otra@example.test",
                allowed_senders=["nuria@example.test"],
            )
        state_after_simulation = licitacion_state(app, licitacion_id)

    assert existing["exists"] is True
    assert existing["processable"] is True
    assert missing["exists"] is False
    assert simulated["status"] == "dry_run"
    assert simulated["old_state"] == "Enviada a Nuria"
    assert simulated["new_state"] == "Descargar para ver"
    assert simulated["would_change"] is True
    assert state_after_simulation == "Enviada a Nuria"
    assert direct["reason"] == "remitente no autorizado"


def test_download_review_email_action_queues_download_job_and_starts_worker(monkeypatch) -> None:
    app = load_app_module()
    worker_calls: list[int] = []

    def fake_start_download_worker(*, job_id=None):
        worker_calls.append(int(job_id))
        return {"started": True, "pid": 4321}

    monkeypatch.setattr(app, "start_download_worker", fake_start_download_worker)

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"9": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-review>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        current_state = licitacion_state(app, licitacion_id)

    assert result["processed"] == 1
    assert current_state == "Descargar para ver"
    assert len(jobs) == 1
    assert jobs[0]["status"] == "pending"
    assert jobs[0]["request_source"] == "email_action"
    assert jobs[0]["request_action"] == "Descargar para ver"
    assert jobs[0]["requested_by"] == "nuria@example.test"
    assert worker_calls == [jobs[0]["id"]]


def test_download_worker_sees_committed_job_and_event_when_started(monkeypatch) -> None:
    app = load_app_module()
    visible_at_worker_start: list[dict[str, object]] = []

    def fake_start_download_worker(*, job_id=None):
        with app.db_session() as observer:
            job = observer.execute(
                "SELECT status FROM download_jobs WHERE id = ?",
                (int(job_id),),
            ).fetchone()
            event = observer.execute(
                "SELECT execution_status FROM email_action_events WHERE download_job_id = ?",
                (int(job_id),),
            ).fetchone()
        visible_at_worker_start.append(
            {
                "job_status": job["status"] if job else None,
                "event_status": event["execution_status"] if event else None,
            }
        )
        return {"started": True, "pid": 4321}

    monkeypatch.setattr(app, "start_download_worker", fake_start_download_worker)

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"90": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-visibility-race>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)

    assert result["processed"] == 1
    assert visible_at_worker_start == [
        {"job_status": "pending", "event_status": "pending"}
    ]


def test_ai_summary_email_action_chains_download_to_ai_job_and_email_notification(monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED", "1")
    app = load_app_module()
    download_workers: list[int] = []
    ai_workers: list[int] = []
    ai_requests: list[dict] = []
    notification_calls: list[dict] = []

    monkeypatch.setattr(
        app,
        "start_download_worker",
        lambda *, job_id=None: download_workers.append(int(job_id)) or {"started": True, "pid": 4321},
    )

    def fake_request_ai_analysis(conn, licitacion_id, **kwargs):
        ai_requests.append({"licitacion_id": licitacion_id, **kwargs})
        return {
            "ok": True,
            "job_id": 701,
            "job_status": "pending",
            "job": {"id": 701, "status": "pending"},
        }

    def fake_create_job_notifications(conn, **kwargs):
        notification_calls.append(kwargs)
        return 1

    monkeypatch.setattr(app, "request_ai_analysis", fake_request_ai_analysis)
    monkeypatch.setattr(app, "create_job_notifications", fake_create_job_notifications)
    monkeypatch.setattr(
        app,
        "start_ai_worker_for_job",
        lambda conn, job_id: ai_workers.append(job_id) or {"ok": True, "pid": 9876, "log_path": "worker.log"},
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_AI_SUMMARY)
        fake = FakeIMAP(
            {
                b"91": {
                    "subject": f"LLANGON_CMD {code} - Solicitar resumen IA",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Solicitar resumen IA",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<ai-summary-new-job>",
                    ),
                }
            }
        )

        mailbox_result = run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        completion = app.process_download_job(int(jobs[0]["id"]))
        with app.db_session() as conn:
            request = conn.execute(
                "SELECT * FROM email_ai_summary_requests WHERE licitacion_id = ?",
                (licitacion_id,),
            ).fetchone()
            current_state = conn.execute("SELECT estado FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()["estado"]

    assert mailbox_result["processed"] == 1
    assert fake.messages[b"91"]["seen"] is True
    assert current_state == "Descargar para ver"
    assert download_workers == [jobs[0]["id"]]
    assert ai_requests == [
        {
            "licitacion_id": licitacion_id,
            "requested_by": "nuria@example.test",
            "selected_files": None,
            "notify_on_completion": True,
            "notification_emails": ["nuria@example.test"],
        }
    ]
    assert len(notification_calls) == 1
    assert notification_calls[0]["job_id"] == 701
    assert notification_calls[0]["licitacion_id"] == licitacion_id
    assert notification_calls[0]["requested_by"] == "nuria@example.test"
    assert notification_calls[0]["recipients"] == ["nuria@example.test"]
    assert notification_calls[0]["created_at"]
    assert ai_workers == [701]
    assert request["download_job_id"] == jobs[0]["id"]
    assert request["ai_job_id"] == 701
    assert request["status"] == "analysis_queued"
    assert completion["payload"]["ai_summary_requests"]["queued"] == 1


def test_ai_summary_email_action_attaches_to_existing_download_and_active_ai_job(monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED", "1")
    app = load_app_module()
    download_workers: list[int] = []
    ai_workers: list[int] = []
    notification_calls: list[dict] = []

    monkeypatch.setattr(
        app,
        "start_download_worker",
        lambda *, job_id=None: download_workers.append(int(job_id)) or {"started": True, "pid": 4321},
    )
    monkeypatch.setattr(
        app,
        "request_ai_analysis",
        lambda conn, licitacion_id, **kwargs: {
            "ok": True,
            "job_status": "processing",
            "job": {"id": 702, "status": "processing"},
        },
    )
    monkeypatch.setattr(app, "create_job_notifications", lambda conn, **kwargs: notification_calls.append(kwargs) or 1)
    monkeypatch.setattr(app, "start_ai_worker_for_job", lambda conn, job_id: ai_workers.append(job_id) or {"ok": True})

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Descargar para ver")
        with app.db_session() as conn:
            existing_job_id = app.create_download_job(
                conn,
                licitacion_id,
                timestamp="2026-07-11T10:00:00",
                status="pending",
                request_source="manual_button",
                request_action="manual_download",
                request_message_id="",
                requested_by="admin_test",
            )
        code = generate_action_code(licitacion_id, ACTION_AI_SUMMARY)
        fake = FakeIMAP(
            {
                b"92": {
                    "subject": f"LLANGON_CMD {code} - Solicitar resumen IA",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Solicitar resumen IA",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<ai-summary-existing-job>",
                    ),
                }
            }
        )

        mailbox_result = run_with_fake_imap(app, fake)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        completion = app.process_download_job(existing_job_id)
        with app.db_session() as conn:
            request = conn.execute(
                "SELECT * FROM email_ai_summary_requests WHERE licitacion_id = ?",
                (licitacion_id,),
            ).fetchone()

    assert mailbox_result["processed"] == 1
    assert download_workers == []
    assert ai_workers == []
    assert notification_calls[0]["job_id"] == 702
    assert notification_calls[0]["recipients"] == ["nuria@example.test"]
    assert request["download_job_id"] == existing_job_id
    assert request["ai_job_id"] == 702
    assert request["status"] == "analysis_waiting"
    assert completion["payload"]["ai_summary_requests"]["waiting_for_active_job"] == 1


def test_ai_summary_email_action_sends_existing_summary_without_starting_another_ai_job(monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED", "1")
    app = load_app_module()
    deliveries: list[dict] = []
    ai_workers: list[int] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "request_ai_analysis",
        lambda conn, licitacion_id, **kwargs: {"ok": True, "has_summary": True, "job_status": "completed"},
    )
    monkeypatch.setattr(
        app,
        "generate_ai_summary_pdf_and_email",
        lambda conn, **kwargs: deliveries.append(kwargs) or {"sent": 1, "error": 0, "job_id": 703},
    )
    monkeypatch.setattr(app, "start_ai_worker_for_job", lambda conn, job_id: ai_workers.append(job_id) or {"ok": True})

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_AI_SUMMARY)
        fake = FakeIMAP(
            {
                b"93": {
                    "subject": f"LLANGON_CMD {code} - Solicitar resumen IA",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Solicitar resumen IA",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<ai-summary-existing-summary>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        job_id = download_jobs_for_licitacion(app, licitacion_id)[0]["id"]
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        completion = app.process_download_job(int(job_id))
        with app.db_session() as conn:
            request = conn.execute(
                "SELECT * FROM email_ai_summary_requests WHERE licitacion_id = ?",
                (licitacion_id,),
            ).fetchone()

    assert len(deliveries) == 1
    assert deliveries[0]["licitacion_id"] == licitacion_id
    assert deliveries[0]["recipients"] == ["nuria@example.test"]
    assert deliveries[0]["requested_by"] == "nuria@example.test"
    assert deliveries[0]["now"] is app.now_iso
    assert deliveries[0]["pdf_output_root"].name == "ai_summary_pdfs"
    assert ai_workers == []
    assert request["ai_job_id"] == 703
    assert request["status"] == "summary_delivered"
    assert completion["payload"]["ai_summary_requests"]["delivered_existing_summary"] == 1


def test_ai_summary_preparation_failure_sends_nuria_order_telegram(monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED", "1")
    app = load_app_module()
    telegram_messages: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})

    def fail_ai_request(*_args, **_kwargs):
        raise ValueError("No hay documentos aptos para preparar el resumen.")

    monkeypatch.setattr(app, "request_ai_analysis", fail_ai_request)
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=97),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_DISABLED",
            error_message="disabled",
        ),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_AI_SUMMARY)
        fake = FakeIMAP(
            {
                b"94": {
                    "subject": f"LLANGON_CMD {code} - Solicitar resumen IA",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Solicitar resumen IA",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<ai-summary-preparation-failure>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        job_id = int(download_jobs_for_licitacion(app, licitacion_id)[0]["id"])
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        completion = app.process_download_job(job_id)
        event = email_action_events_for_licitacion(app, licitacion_id)[-1]

    assert completion["ok"] is True
    assert completion["payload"]["ai_summary_requests"]["errors"] == 1
    assert event["execution_status"] == "failed"
    assert event["failure_stage"] == "ai"
    assert event["failure_code"] == "AI_PREPARATION_ERROR"
    assert event["telegram_notification_status"] == "sent_user"
    assert len(telegram_messages) == 1
    assert "Nuria ha solicitado: Solicitar resumen IA" in telegram_messages[0]
    assert "Punto de fallo: Procesamiento del resumen IA" in telegram_messages[0]
    assert "No hay documentos aptos" in telegram_messages[0]


def test_prepare_email_action_does_not_duplicate_existing_pending_download_job(monkeypatch) -> None:
    app = load_app_module()
    worker_calls: list[int] = []

    def fake_start_download_worker(*, job_id=None):
        worker_calls.append(int(job_id))
        return {"started": True, "pid": 4321}

    monkeypatch.setattr(app, "start_download_worker", fake_start_download_worker)

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Descargar para ver")
        with app.db_session() as conn:
            app.create_download_job(
                conn,
                licitacion_id,
                timestamp="2026-07-03T10:00:00",
                status="pending",
                request_source="email_action",
                request_action="Descargar para ver",
                request_message_id="<prev>",
                requested_by="nuria@example.test",
            )
        code = generate_action_code(licitacion_id, ACTION_PREPARE)
        fake = FakeIMAP(
            {
                b"10": {
                    "subject": f"LLANGON_CMD {code} - Preparar ficha",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Preparar ficha",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<prepare>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        current_state = licitacion_state(app, licitacion_id)

    assert result["processed"] == 1
    assert current_state == "Preparar ficha"
    assert len(jobs) == 1
    assert jobs[0]["status"] == "pending"
    assert worker_calls == []


def test_download_review_email_action_still_queues_job_when_ruta_carpeta_is_informed(monkeypatch) -> None:
    app = load_app_module()
    worker_calls: list[int] = []

    def fake_start_download_worker(*, job_id=None):
        worker_calls.append(int(job_id))
        return {"started": True, "pid": 4321}

    monkeypatch.setattr(app, "start_download_worker", fake_start_download_worker)

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET ruta_carpeta = ? WHERE id = ?",
                ("2026\\07 JULIO\\03 JULIO 1400 PRUEBA EXP-EMAIL", licitacion_id),
            )
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"11": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-review-ruta>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        current_state = licitacion_state(app, licitacion_id)

    assert result["processed"] == 1
    assert current_state == "Descargar para ver"
    assert len(jobs) == 1
    assert jobs[0]["status"] == "pending"
    assert jobs[0]["request_source"] == "email_action"
    assert worker_calls == [jobs[0]["id"]]


def test_reprocessing_same_unread_email_action_does_not_queue_duplicate_download(monkeypatch) -> None:
    app = load_app_module()
    worker_calls: list[int] = []

    def fake_start_download_worker(*, job_id=None):
        worker_calls.append(int(job_id))
        return {"started": True, "pid": 4321}

    monkeypatch.setattr(app, "start_download_worker", fake_start_download_worker)

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"12": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<same-download-message>",
                    ),
                }
            }
        )

        first = run_with_fake_imap(app, fake)
        fake.messages[b"12"]["seen"] = False
        second = run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        events = email_action_events_for_licitacion(app, licitacion_id)

    assert first["processed"] == 1
    assert second["processed"] == 0
    assert second["total_duplicate_codes"] == 1
    assert second["ignored_by_reason"]["DUPLICATE_EMAIL_ACTION"] == 1
    assert fake.messages[b"12"]["seen"] is True
    assert len(jobs) == 1
    assert worker_calls == [jobs[0]["id"]]
    assert [event["result"] for event in events] == ["processed", "ignored"]


def test_download_review_email_action_sends_admin_telegram_when_download_finishes(monkeypatch) -> None:
    app = load_app_module()
    worker_calls: list[int] = []
    telegram_messages: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: worker_calls.append(int(job_id)) or {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=51),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=61),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"12": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-review-finish>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        result = app.process_download_job(int(jobs[0]["id"]))
        events = email_action_events_for_licitacion(app, licitacion_id)

    assert worker_calls == [jobs[0]["id"]]
    assert result["ok"] is True
    assert len(telegram_messages) == 1
    assert "Nuria ha solicitado: Descargar para ver" in telegram_messages[0]
    assert "Expediente:" in telegram_messages[0]
    assert "Título:" in telegram_messages[0]
    assert "Vencimiento:" in telegram_messages[0]
    assert "Estado actual:" in telegram_messages[0]
    assert "Carpeta:" in telegram_messages[0]
    assert "Ruta Dropbox:" in telegram_messages[0]
    assert "Origen: correo de revisión Infonalia" in telegram_messages[0]
    assert group_calls == []
    assert events[-1]["telegram_notification_status"] == "sent_user"
    assert events[-1]["telegram_notification_target"] == "user:admin_test"
    assert events[-1]["telegram_notification_attempted_at"]


def test_prepare_action_download_failure_sends_detailed_admin_telegram_once(monkeypatch) -> None:
    app = load_app_module()
    telegram_messages: list[str] = []
    group_calls: list[str] = []
    error_message = (
        "El descargador devolvio codigo 1: URL detectada: "
        "https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=260715105302B4482A94\n"
        "No se reconoce la plataforma de esta URL.\n"
        "Host detectado: hacienda.navarra.es"
    )

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=91),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=92),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE licitaciones
                    SET expediente = '3225_536/2026',
                        organismo = 'AYUNTAMIENTO DE AZAGRA (NAVARRA)',
                        objeto = 'Licitación Navarra sin descargador',
                    enlace_perfil = 'https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=260715105302B4482A94'
                WHERE id = ?
                """,
                (licitacion_id,),
            )
        code = generate_action_code(licitacion_id, ACTION_PREPARE)
        fake = FakeIMAP(
            {
                b"17": {
                    "subject": f"LLANGON_CMD {code} - Preparar ficha",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Preparar ficha",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<prepare-navarra-failure>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_failed_download_factory(app, error_message))
        result = app.process_download_job(int(jobs[0]["id"]))
        duplicate_attempt = app.notify_pending_email_action_telegram_events(
            licitacion_id=licitacion_id,
            download_job_id=int(jobs[0]["id"]),
        )
        events = email_action_events_for_licitacion(app, licitacion_id)
        with app.db_session() as conn:
            critical_event = conn.execute(
                """
                SELECT * FROM infonalia_activity_events
                WHERE licitacion_id = ? AND event_type = 'download_failed'
                ORDER BY id DESC LIMIT 1
                """,
                (licitacion_id,),
            ).fetchone()

    assert result["ok"] is False
    assert len(telegram_messages) == 1
    assert group_calls == []
    assert "🚨 Falló una orden de Nuria" in telegram_messages[0]
    assert "Nuria ha solicitado: Preparar ficha" in telegram_messages[0]
    assert "Expediente: 3225_536/2026" in telegram_messages[0]
    assert "AYUNTAMIENTO DE AZAGRA (NAVARRA)" in telegram_messages[0]
    assert "Punto de fallo: Descarga de documentación" in telegram_messages[0]
    assert "No se reconoce la plataforma" in telegram_messages[0]
    assert "hacienda.navarra.es" in telegram_messages[0]
    assert "histórico de Infonalia" in telegram_messages[0]
    assert events[-1]["download_job_id"] == jobs[0]["id"]
    assert events[-1]["execution_status"] == "failed"
    assert events[-1]["failure_code"] == "DOWNLOADER_EXIT_CODE"
    assert events[-1]["telegram_notification_status"] == "sent_user"
    assert events[-1]["telegram_notification_attempt_count"] == 1
    assert duplicate_attempt["checked"] == 0
    assert critical_event is not None


def test_worker_start_failure_is_persisted_and_notified(monkeypatch) -> None:
    app = load_app_module()
    telegram_messages: list[str] = []

    monkeypatch.setattr(
        app,
        "start_download_worker",
        lambda *, job_id=None: {"started": False, "error": "No se pudo crear el proceso de descarga."},
    )
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=94),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_DISABLED",
            error_message="disabled",
        ),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"19": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-worker-start-failure>",
                    ),
                }
            }
        )

        result = run_with_fake_imap(app, fake)
        delivery = app.notify_pending_email_action_telegram_events(licitacion_id=licitacion_id)
        job = download_jobs_for_licitacion(app, licitacion_id)[0]
        event = email_action_events_for_licitacion(app, licitacion_id)[-1]

    assert result["processed"] == 1
    assert job["status"] == "failed"
    assert event["execution_status"] == "failed"
    assert event["failure_stage"] == "worker_start"
    assert event["failure_code"] == "DOWNLOAD_WORKER_START_FAILED"
    assert delivery["sent"] == 1
    assert len(telegram_messages) == 1
    assert "Punto de fallo: Inicio del proceso de descarga" in telegram_messages[0]
    assert "No se pudo crear el proceso de descarga" in telegram_messages[0]


def test_prepare_email_action_pending_job_notifies_when_existing_job_finishes(monkeypatch) -> None:
    app = load_app_module()
    telegram_messages: list[str] = []
    worker_calls: list[int] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: worker_calls.append(int(job_id)) or {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=52),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: TelegramResult(ok=False, status="error", message="No", error_code="TELEGRAM_DISABLED", error_message="disabled"),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Descargar para ver")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            existing_job_id = app.create_download_job(
                conn,
                licitacion_id,
                timestamp="2026-07-07T10:00:00",
                status="pending",
                request_source="manual_button",
                request_action="manual_download",
                request_message_id="",
                requested_by="admin_test",
            )
        code = generate_action_code(licitacion_id, ACTION_PREPARE)
        fake = FakeIMAP(
            {
                b"13": {
                    "subject": f"LLANGON_CMD {code} - Preparar ficha",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Preparar ficha",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<prepare-existing-job>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        result = app.process_download_job(existing_job_id)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        events = email_action_events_for_licitacion(app, licitacion_id)

    assert result["ok"] is True
    assert len(jobs) == 1
    assert worker_calls == []
    assert len(telegram_messages) == 1
    assert "Nuria ha solicitado: Preparar ficha" in telegram_messages[0]
    assert "Vencimiento:" in telegram_messages[0]
    assert "Ruta Dropbox:" in telegram_messages[0]
    assert events[-1]["telegram_notification_status"] == "sent_user"
    assert events[-1]["telegram_notification_target"] == "user:admin_test"


def test_email_action_telegram_falls_back_to_group_when_admin_private_chat_is_not_available(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(str(user["username"])) or TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_USER_DISABLED",
            error_message="disabled",
        ),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=62),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE usuarios
                SET telegram_chat_id = '', telegram_notifications_enabled = 0, updated_at = '2026-07-07T09:00:00'
                WHERE username = 'admin_test'
                """
            )
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"14": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-fallback-group>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        app.process_download_job(int(jobs[0]["id"]))
        events = email_action_events_for_licitacion(app, licitacion_id)

    assert user_calls == []
    assert len(group_calls) == 1
    assert events[-1]["telegram_notification_status"] == "sent_group"
    assert events[-1]["telegram_notification_target"] == "group"


def test_manual_download_without_email_action_events_does_not_send_telegram(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=63),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=64),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Descargar para ver")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            job_id = app.create_download_job(
                conn,
                licitacion_id,
                timestamp="2026-07-07T11:00:00",
                status="pending",
                request_source="manual_button",
                request_action="manual_download",
                request_message_id="",
                requested_by="admin_test",
            )
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        result = app.process_download_job(job_id)

    assert result["ok"] is True
    assert user_calls == []
    assert group_calls == []
    assert result["payload"]["telegram_notifications"]["checked"] == 0


def test_manual_download_failure_without_nuria_order_does_not_send_telegram(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=95),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text)
        or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=96),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Descargar para ver")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            job_id = app.create_download_job(
                conn,
                licitacion_id,
                timestamp="2026-07-07T12:30:00",
                status="pending",
                request_source="manual_button",
                request_action="manual_download",
                request_message_id="",
                requested_by="admin_test",
            )
        delivery = app._finish_failed_download_job(
            job_id,
            "No se reconoce la plataforma manual.",
            failure_stage="downloader",
            failure_code="DOWNLOADER_EXIT_CODE",
        )

    assert delivery["checked"] == 0
    assert user_calls == []
    assert group_calls == []


def test_manual_prepare_state_without_email_event_does_not_send_telegram(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=71),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=72),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Importada")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET estado = ?, updated_at = '2026-07-07T12:15:00' WHERE id = ?",
                ("Preparar ficha", licitacion_id),
            )
        result = app.notify_pending_email_action_telegram_events(licitacion_id=licitacion_id)

    assert result["checked"] == 0
    assert user_calls == []
    assert group_calls == []


def test_email_action_telegram_failure_does_not_break_download_and_marks_event_failed(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(str(user["username"])) or TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_USER_DISABLED",
            error_message="disabled",
        ),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text) or TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_DISABLED",
            error_message="disabled",
        ),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"15": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-telegram-failure>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        result = app.process_download_job(int(jobs[0]["id"]))
        events = email_action_events_for_licitacion(app, licitacion_id)

    assert result["ok"] is True
    assert user_calls == ["admin_test"]
    assert len(group_calls) == 1
    assert result["payload"]["telegram_notifications"]["failed"] == 1
    assert events[-1]["telegram_notification_status"] == "failed"
    assert "group:TELEGRAM_DISABLED" in events[-1]["telegram_notification_error"]


def test_failed_order_telegram_is_retried_without_duplicate_attempts(monkeypatch) -> None:
    app = load_app_module()
    user_calls: list[str] = []
    group_calls: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: user_calls.append(text)
        or TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_NETWORK_ERROR",
            error_message="network",
        ),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: group_calls.append(text)
        or TelegramResult(
            ok=False,
            status="error",
            message="No enviado",
            error_code="TELEGRAM_NETWORK_ERROR",
            error_message="network",
        ),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"18": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-retry-telegram>",
                    ),
                }
            }
        )
        run_with_fake_imap(app, fake)
        job_id = int(download_jobs_for_licitacion(app, licitacion_id)[0]["id"])

        first = app._finish_failed_download_job(
            job_id,
            "No se reconoce la plataforma hacienda.navarra.es.",
            failure_stage="downloader",
            failure_code="DOWNLOADER_EXIT_CODE",
        )
        event = email_action_events_for_licitacion(app, licitacion_id)[-1]
        retry_at = datetime.fromisoformat(event["telegram_notification_next_attempt_at"])

        too_early = app.notify_pending_email_action_telegram_events(
            download_job_id=job_id,
            current=retry_at - timedelta(seconds=1),
        )
        monkeypatch.setattr(
            app,
            "send_telegram_user_message",
            lambda user, text, env=None: user_calls.append(text)
            or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=93),
        )
        retried = app.notify_pending_email_action_telegram_events(
            download_job_id=job_id,
            current=retry_at,
        )
        final_event = email_action_events_for_licitacion(app, licitacion_id)[-1]

    assert first["checked"] == 1
    assert first["failed"] == 1
    assert first["pending_retry"] == 1
    assert too_early["checked"] == 0
    assert retried["checked"] == 1
    assert retried["sent"] == 1
    assert len(user_calls) == 2
    assert len(group_calls) == 1
    assert final_event["telegram_notification_status"] == "sent_user"
    assert final_event["telegram_notification_attempt_count"] == 2
    assert not final_event["telegram_notification_next_attempt_at"]


def test_reprocessing_same_email_action_job_does_not_duplicate_telegram_notice(monkeypatch) -> None:
    app = load_app_module()
    telegram_messages: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=81),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: TelegramResult(ok=False, status="error", message="No", error_code="TELEGRAM_DISABLED", error_message="disabled"),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"16": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-dedupe>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app))
        first = app.process_download_job(int(jobs[0]["id"]))
        second = app.notify_pending_email_action_telegram_events(
            licitacion_id=licitacion_id,
            download_job_id=int(jobs[0]["id"]),
        )

    assert first["ok"] is True
    assert len(telegram_messages) == 1
    assert first["payload"]["telegram_notifications"]["sent"] == 1
    assert second["checked"] == 0
    assert second["sent"] == 0


def test_email_action_telegram_message_handles_missing_optional_fields(monkeypatch) -> None:
    app = load_app_module()
    telegram_messages: list[str] = []

    monkeypatch.setattr(app, "start_download_worker", lambda *, job_id=None: {"started": True, "pid": 4321})
    monkeypatch.setattr(
        app,
        "send_telegram_user_message",
        lambda user, text, env=None: telegram_messages.append(text) or TelegramResult(ok=True, status="ok", message="Enviado", telegram_message_id=91),
    )
    monkeypatch.setattr(
        app,
        "send_telegram_group_message",
        lambda text, env=None: TelegramResult(ok=False, status="error", message="No", error_code="TELEGRAM_DISABLED", error_message="disabled"),
    )

    with temporary_app_database(app):
        _dia_id, licitacion_id = prepare_action(app, estado="Enviada a Nuria")
        enable_admin_telegram(app)
        with app.db_session() as conn:
            conn.execute(
                """
                UPDATE licitaciones
                SET objeto = '', fecha_limite = NULL, hora_limite = '', ruta_carpeta = ''
                WHERE id = ?
                """,
                (licitacion_id,),
            )
        code = generate_action_code(licitacion_id, ACTION_DOWNLOAD_REVIEW)
        fake = FakeIMAP(
            {
                b"17": {
                    "subject": f"LLANGON_CMD {code} - Descargar para ver",
                    "seen": False,
                    "raw": make_message(
                        f"LLANGON_CMD {code} - Descargar para ver",
                        "nuria@example.test",
                        f"LLANGON_ACTION_CODE={code}",
                        "<download-missing-fields>",
                    ),
                }
            }
        )

        run_with_fake_imap(app, fake)
        jobs = download_jobs_for_licitacion(app, licitacion_id)
        monkeypatch.setattr(app, "execute_download_for_destination", fake_completed_download_factory(app, ruta=""))
        app.process_download_job(int(jobs[0]["id"]))

    assert len(telegram_messages) == 1
    assert "Título: Sin descripción" in telegram_messages[0]
    assert "Vencimiento: No consta" in telegram_messages[0]
    assert "Carpeta: no consta" in telegram_messages[0]
    assert "Ruta Dropbox: no consta" in telegram_messages[0]
