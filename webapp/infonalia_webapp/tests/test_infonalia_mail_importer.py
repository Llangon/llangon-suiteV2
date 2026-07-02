from __future__ import annotations

import imaplib
from email.headerregistry import Address
from email.message import EmailMessage

from webapp.infonalia_webapp.infonalia_mail_importer import (
    EXPECTED_FROM,
    EXPECTED_SUBJECT,
    InfonaliaImportConfig,
    config_from_env,
    ensure_infonalia_email_import_schema,
    import_parsed_email,
    INCLUDE_SEEN_UID_LIMIT,
    imap_search_criteria,
    is_expected_infonalia_message,
    parse_infonalia_email,
    process_mailbox_once,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def sample_plain_body() -> str:
    return """
Ref. Infonalia: INF-001
Nº Expediente: EXP-001
Organismo: AYUNTAMIENTO DE PRUEBA
Resumen del Objeto: Suministro de alimentos para centro municipal.
Provincia de Ejecución: Madrid
Presupuesto: 12.345,67 EUR
Plazo Presentación: Hasta el próximo día 30/06/2026 14:00
Ver el texto íntegro del anuncio: <https://infonalia.example/anuncio/1>
Perfil del Contratante (Pliegos): <https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=abc>
Información extraída de plataforma: PLACE 05/06/2026 12:33
________________________________________
Ref. Infonalia: INF-002
Nº Expediente: EXP-002
Organismo: DIPUTACIÓN DE PRUEBA
Resumen del Objeto: Servicio de limpieza.
Provincia de Ejecución: Sevilla
Presupuesto: 5000,00 EUR
Plazo Presentación: 01/07/2026
Ver el texto íntegro del anuncio: https://infonalia.example/anuncio/2
Perfil del Contratante (Pliegos): https://www.juntadeandalucia.es/perfil/2
"""


def make_infonalia_message(*, sender: str = EXPECTED_FROM, subject: str = EXPECTED_SUBJECT, plain: str | None = None, html: str | None = None, message_id: str = "<msg-1@example.test>") -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = Address(addr_spec=sender)
    msg["To"] = "info3llangon@gmail.com"
    msg["Date"] = "Fri, 05 Jun 2026 12:33:00 +0200"
    msg["Message-ID"] = message_id
    if html is not None:
        msg.set_content(plain or "")
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(plain or sample_plain_body())
    return msg.as_bytes()


def make_regular_message() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "Correo normal"
    msg["From"] = Address(addr_spec="cliente@example.test")
    msg["To"] = "info3llangon@gmail.com"
    msg["Date"] = "Fri, 05 Jun 2026 12:33:00 +0200"
    msg["Message-ID"] = "<regular@example.test>"
    msg.set_content("Este correo no contiene una estructura de licitaciones Infonalia.")
    return msg.as_bytes()


class FakeIMAP:
    def __init__(self, messages: dict[bytes, dict[str, object]]):
        self.messages = messages
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[bytes, str]] = []
        self.store_calls: list[tuple[bytes, tuple[object, ...]]] = []

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
            found = [uid for uid, item in self.messages.items() if include_seen or not item.get("seen")]
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


class BadSearchIMAP(FakeIMAP):
    def uid(self, command, *args):
        normalized = str(command).upper()
        self.calls.append((normalized, args))
        if normalized == "SEARCH":
            raise imaplib.IMAP4.error("BAD [b'Could not parse command']")
        return super().uid(command, *args)


def fake_config(*, enabled: bool = True) -> InfonaliaImportConfig:
    return InfonaliaImportConfig(
        enabled=enabled,
        host="imap.example.test",
        port=993,
        user="info3llangon@gmail.com",
        password="secret",
        folder="LLANGON_INFONALIA",
        expected_from=EXPECTED_FROM,
        expected_subject=EXPECTED_SUBJECT,
        notify_email="info3@llangon.com",
        mark_read_on_success=True,
        test_forwarders=[],
        lookback_hours=48,
    )


def test_config_defaults_to_infonalia_label_not_general_inbox() -> None:
    config = config_from_env(
        {
            "LLANGON_INFONALIA_IMPORT_ENABLED": "1",
            "LLANGON_ACTIONS_IMAP_HOST": "imap.example.test",
            "LLANGON_ACTIONS_IMAP_PORT": "993",
            "LLANGON_ACTIONS_IMAP_USER": "info3llangon@gmail.com",
            "LLANGON_ACTIONS_IMAP_PASSWORD": "secret",
            "LLANGON_ACTIONS_IMAP_FOLDER": "INBOX",
        }
    )

    assert config.folder == "LLANGON_INFONALIA"


def test_parser_decodes_mime_subject_and_extracts_plain_items() -> None:
    raw = make_infonalia_message(subject=EXPECTED_SUBJECT, plain=sample_plain_body())

    parsed = parse_infonalia_email(raw)
    items = parsed["items"]

    assert parsed["subject"] == EXPECTED_SUBJECT
    assert parsed["from_email"] == EXPECTED_FROM
    assert len(items) == 2
    assert items[0]["ref_infonalia"] == "INF-001"
    assert items[0]["expediente"] == "EXP-001"
    assert items[0]["organismo"] == "AYUNTAMIENTO DE PRUEBA"
    assert items[0]["resumen_objeto"].startswith("Suministro de alimentos")
    assert items[0]["provincia_ejecucion"] == "Madrid"
    assert items[0]["presupuesto"] == 12345.67
    assert items[0]["plazo_presentacion_fecha"] == "2026-06-30"
    assert items[0]["url_anuncio_infonalia"] == "https://infonalia.example/anuncio/1"
    assert "contrataciondelestado.es" in items[0]["url_perfil_contratante"]


def test_parser_falls_back_to_html_when_plain_is_empty() -> None:
    html = sample_plain_body().replace("\n", "<br>")
    raw = make_infonalia_message(plain="", html=f"<html><body>{html}</body></html>")

    parsed = parse_infonalia_email(raw)

    assert len(parsed["items"]) == 2
    assert parsed["items"][1]["expediente"] == "EXP-002"


def test_candidate_validation_uses_real_sender_and_subject_with_optional_forwarder() -> None:
    parsed = parse_infonalia_email(make_infonalia_message(sender="otra@example.test"))
    valid, reason = is_expected_infonalia_message(parsed, fake_config())
    assert valid is False
    assert reason == "remitente no coincide"

    config = fake_config()
    config = InfonaliaImportConfig(**{**config.__dict__, "test_forwarders": ["otra@example.test"]})
    valid, reason = is_expected_infonalia_message(parsed, config)
    assert valid is True
    assert reason == ""

    parsed = parse_infonalia_email(make_infonalia_message(subject="MODIFICACIONES - Envío de Novedades - 149022"))
    valid, reason = is_expected_infonalia_message(parsed, fake_config())
    assert valid is False
    assert reason == "asunto no coincide"


def test_import_from_parsed_email_is_idempotent_and_notifies_once() -> None:
    app = load_app_module()
    sent: list[tuple[str, str]] = []
    raw = make_infonalia_message(message_id="<unique@example.test>")
    parsed = parse_infonalia_email(raw)
    with temporary_app_database(app):
        first = import_parsed_email(
            parsed,
            raw_bytes=raw,
            mailbox_user="info3llangon@gmail.com",
            notification_sender=lambda to, subject, body, html: sent.append((to, subject)) or ("2026-06-05T12:34:00", None),
        )
        second = import_parsed_email(
            parsed,
            raw_bytes=raw,
            mailbox_user="info3llangon@gmail.com",
            notification_sender=lambda to, subject, body, html: sent.append((to, subject)) or ("2026-06-05T12:35:00", None),
        )
        with app.db_session() as conn:
            ensure_infonalia_email_import_schema(conn)
            licitaciones = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]
            imports = conn.execute("SELECT COUNT(*) FROM infonalia_email_imports").fetchone()[0]

    assert first["status"] == "imported"
    assert first["imported"] == 2
    assert first["notified"] == 1
    assert second["status"] == "duplicate"
    assert second["notified"] == 0
    assert licitaciones == 2
    assert imports == 2
    assert len(sent) == 1


def test_import_does_not_break_if_notification_sender_fails() -> None:
    app = load_app_module()
    raw = make_infonalia_message(message_id="<smtp-failure@example.test>")
    parsed = parse_infonalia_email(raw)
    with temporary_app_database(app):
        result = import_parsed_email(
            parsed,
            raw_bytes=raw,
            mailbox_user="info3llangon@gmail.com",
            notification_sender=lambda *_args: (_ for _ in ()).throw(RuntimeError("SMTP no configurado")),
        )
        with app.db_session() as conn:
            licitaciones = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]

    assert result["status"] == "imported"
    assert result["imported"] == 2
    assert result["notified"] == 0
    assert "SMTP no configurado" in result["notification_error"]
    assert licitaciones == 2


def test_dry_run_from_parsed_email_does_not_import_or_notify() -> None:
    app = load_app_module()
    raw = make_infonalia_message()
    parsed = parse_infonalia_email(raw)
    with temporary_app_database(app):
        result = import_parsed_email(parsed, raw_bytes=raw, dry_run=True)
        with app.db_session() as conn:
            licitaciones = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]

    assert result["status"] == "dry_run"
    assert result["would_import"] == 2
    assert licitaciones == 0


def test_mailbox_uses_body_peek_and_marks_only_successful_candidate() -> None:
    app = load_app_module()
    raw = make_infonalia_message()
    fake = FakeIMAP(
        {
            b"1": {"seen": False, "raw": make_regular_message()},
            b"2": {"seen": False, "raw": raw},
        }
    )
    with temporary_app_database(app):
        result = process_mailbox_once(
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: fake,
            notification_sender=lambda *_args: ("2026-06-05T12:34:00", None),
        )

    assert result["candidates_seen"] == 1
    assert result["imported"] == 2
    assert fake.messages[b"1"]["seen"] is False
    assert fake.messages[b"2"]["seen"] is True
    select_calls = [args for command, args in fake.calls if command == "SELECT"]
    assert select_calls == [("LLANGON_INFONALIA",)]
    search_calls = [args for command, args in fake.calls if command == "SEARCH"]
    assert search_calls == [("UNSEEN",)]
    assert all(None not in args for args in search_calls)
    assert all("BODY.PEEK" in query for _uid, query in fake.fetch_calls)


def test_mailbox_search_uses_simple_unseen_without_headers_or_since() -> None:
    config = fake_config()
    criteria = imap_search_criteria(config)

    assert criteria == ("UNSEEN",)
    assert "SUBJECT" not in {str(item).upper() for item in criteria}
    assert "FROM" not in {str(item).upper() for item in criteria}
    assert "SINCE" not in {str(item).upper() for item in criteria}
    assert config.expected_subject not in criteria
    for item in criteria:
        if isinstance(item, str):
            item.encode("ascii")


def test_mailbox_include_seen_uses_simple_all_without_headers_or_since() -> None:
    config = fake_config()
    criteria = imap_search_criteria(config, include_seen=True)

    assert criteria == ("ALL",)
    assert "SUBJECT" not in {str(item).upper() for item in criteria}
    assert "FROM" not in {str(item).upper() for item in criteria}
    assert "SINCE" not in {str(item).upper() for item in criteria}


def test_mailbox_include_seen_limits_uid_scan_to_recent_tail() -> None:
    messages = {
        str(i).encode("ascii"): {"seen": True, "raw": make_regular_message()}
        for i in range(1, INCLUDE_SEEN_UID_LIMIT + 6)
    }
    fake = FakeIMAP(messages)

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        include_seen=True,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    assert result["include_seen_total_uids"] == INCLUDE_SEEN_UID_LIMIT + 5
    assert result["include_seen_limited_to"] == INCLUDE_SEEN_UID_LIMIT
    assert result["ignored"] == INCLUDE_SEEN_UID_LIMIT
    assert len({uid for uid, _query in fake.fetch_calls}) == INCLUDE_SEEN_UID_LIMIT
    assert b"1" not in {uid for uid, _query in fake.fetch_calls}


def test_mailbox_imports_labeled_unread_message_by_structure_not_sender_or_subject() -> None:
    raw = make_infonalia_message(sender="otro@example.test", subject="Asunto ya filtrado por Gmail")
    fake = FakeIMAP(
        {
            b"1": {"seen": False, "raw": raw},
        }
    )

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        dry_run=True,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    search_calls = [args for command, args in fake.calls if command == "SEARCH"]
    assert search_calls
    assert all(None not in args for args in search_calls)
    assert result["candidates_seen"] == 1
    assert result["parsed_items"] == 2
    assert fake.messages[b"1"]["seen"] is False
    assert all("BODY.PEEK[HEADER" in query or "BODY.PEEK[]" in query for _uid, query in fake.fetch_calls)


def test_mailbox_invalid_labeled_message_is_not_imported_or_marked_read() -> None:
    fake = FakeIMAP({b"1": {"seen": False, "raw": make_regular_message()}})

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    assert result["candidates_seen"] == 0
    assert result["ignored"] == 1
    assert result["imported"] == 0
    assert result["errors"] == 0
    assert result["last_ignored_reason"] == "Correo sin estructura válida de LICITACIONES Infonalia."
    assert fake.messages[b"1"]["seen"] is False
    assert fake.store_calls == []


def test_mailbox_keeps_candidate_unread_if_import_fails(monkeypatch) -> None:
    raw = make_infonalia_message()
    fake = FakeIMAP({b"2": {"seen": False, "raw": raw}})

    def fail_import(*_args, **_kwargs):
        raise RuntimeError("fallo importación")

    monkeypatch.setattr("webapp.infonalia_webapp.infonalia_mail_importer.import_parsed_email", fail_import)

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        notification_sender=lambda *_args: ("2026-06-05T12:34:00", None),
    )

    assert result["candidates_seen"] == 1
    assert result["errors"] == 1
    assert fake.messages[b"2"]["seen"] is False
    assert fake.store_calls == []


class MissingFolderIMAP(FakeIMAP):
    def select(self, folder):
        self.calls.append(("SELECT", (folder,)))
        return "NO", [b"Unknown Mailbox"]


def test_mailbox_missing_label_is_controlled_and_does_not_search_or_mark_read() -> None:
    fake = MissingFolderIMAP({b"2": {"seen": False, "raw": make_infonalia_message()}})

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    assert result["status"] == "failed"
    assert result["errors"] == 1
    assert "No se pudo seleccionar la etiqueta IMAP LLANGON_INFONALIA" in result["last_error"]
    assert [command for command, _args in fake.calls] == ["LOGIN", "SELECT"]
    assert fake.store_calls == []
    assert fake.messages[b"2"]["seen"] is False


def test_mailbox_imap_search_bad_is_controlled_and_does_not_mark_read() -> None:
    fake = BadSearchIMAP({b"2": {"seen": False, "raw": make_infonalia_message()}})

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    assert result["status"] == "failed"
    assert result["errors"] == 1
    assert "Could not parse command" in result["last_error"]
    assert fake.store_calls == []
    assert fake.messages[b"2"]["seen"] is False


def test_mailbox_dry_run_does_not_mark_read_or_notify() -> None:
    raw = make_infonalia_message()
    fake = FakeIMAP({b"2": {"seen": False, "raw": raw}})

    result = process_mailbox_once(
        config=fake_config(),
        imap_factory=lambda *_args, **_kwargs: fake,
        dry_run=True,
        notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no notify")),
    )

    assert result["parsed_items"] == 2
    assert fake.messages[b"2"]["seen"] is False
    assert fake.store_calls == []


def test_mailbox_reprocessing_unread_duplicate_does_not_duplicate_or_notify_again() -> None:
    app = load_app_module()
    raw = make_infonalia_message(message_id="<repeat@example.test>")
    sent: list[tuple[str, str]] = []

    with temporary_app_database(app):
        first_fake = FakeIMAP({b"2": {"seen": False, "raw": raw}})
        first = process_mailbox_once(
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: first_fake,
            notification_sender=lambda to, subject, body, html: sent.append((to, subject)) or ("2026-06-05T12:34:00", None),
        )
        second_fake = FakeIMAP({b"2": {"seen": False, "raw": raw}})
        second = process_mailbox_once(
            config=fake_config(),
            imap_factory=lambda *_args, **_kwargs: second_fake,
            notification_sender=lambda *_args: (_ for _ in ()).throw(AssertionError("no second notify")),
        )

    assert first["imported"] == 2
    assert first_fake.messages[b"2"]["seen"] is True
    assert second["imported"] == 0
    assert second["duplicates"] >= 2
    assert second["ignored"] == 1
    assert second_fake.messages[b"2"]["seen"] is True
    assert len(sent) == 1
