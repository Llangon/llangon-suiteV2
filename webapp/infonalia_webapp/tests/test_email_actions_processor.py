from __future__ import annotations

from email.message import EmailMessage

from webapp.infonalia_webapp.email_actions import (
    ACTION_DISCARD,
    ACTION_DOWNLOAD_REVIEW,
    ACTION_PREPARE,
    check_action_code,
    ensure_review_action_codes,
    generate_action_code,
)
from webapp.infonalia_webapp.email_actions_processor import (
    MailboxConfig,
    check_code_payload,
    process_mailbox_once,
    simulate_code_payload,
)
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
