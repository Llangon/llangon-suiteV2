from __future__ import annotations

import importlib
import sqlite3
import sys
from email.message import EmailMessage
from pathlib import Path

import pytest

from webapp.infonalia_webapp.notification_delivery import (
    attach_logo_to_message,
    build_notification_message,
    create_notification_record,
    notification_recipients_for_target,
    send_notification_email_with_settings,
)


class FakeSMTP:
    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.sent_message: EmailMessage | None = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.sent_message = message


def test_notification_delivery_import_does_not_import_app_or_smtp() -> None:
    sys.modules.pop("webapp.infonalia_webapp.notification_delivery", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.notification_delivery")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert "smtplib" not in added


def test_notification_recipients_for_target_uses_active_target_user() -> None:
    calls = []

    recipients = notification_recipients_for_target(
        "nuria",
        get_user=lambda username: calls.append(username) or {"active": 1, "email": " nuria@example.test "},
        list_users=lambda **_: [{"active": 1, "email": "admin@example.test"}],
    )

    assert recipients == ["nuria@example.test"]
    assert calls == ["nuria"]


def test_notification_recipients_for_target_lists_active_users_and_deduplicates() -> None:
    recipients = notification_recipients_for_target(
        None,
        get_user=lambda _username: None,
        list_users=lambda **kwargs: [
            {"active": 1, "email": "admin@example.test"},
            {"active": 1, "email": "admin@example.test"},
            {"active": 1, "email": "nuria@example.test"},
            {"active": 1, "email": ""},
        ],
    )

    assert recipients == ["admin@example.test", "nuria@example.test"]


def test_build_notification_message_preserves_headers_text_and_html(tmp_path: Path) -> None:
    logo_path = tmp_path / "logo-llangon.png"
    logo_path.write_bytes(b"fake-png")

    message = build_notification_message(
        smtp_from="infonalia@example.test",
        recipients=["a@example.test", "b@example.test"],
        subject="Asunto",
        text_body="Texto",
        html_body="<p>HTML</p>",
        logo_path=logo_path,
    )

    assert message["From"] == "infonalia@example.test"
    assert message["To"] == "a@example.test, b@example.test"
    assert message["Subject"] == "Asunto"
    assert "Texto" in message.get_body(preferencelist=("plain",)).get_content()
    assert "HTML" in message.get_body(preferencelist=("html",)).get_content()
    assert any(part.get("Content-ID") == "<llangon-logo>" for part in message.walk())


def test_attach_logo_to_message_ignores_missing_or_invalid_message(tmp_path: Path) -> None:
    message = EmailMessage()
    attach_logo_to_message(message, tmp_path / "missing.png")

    logo_path = tmp_path / "logo-llangon.png"
    logo_path.write_bytes(b"fake-png")
    attach_logo_to_message(message, logo_path)

    assert message.get_payload() is None


@pytest.mark.parametrize(
    ("settings", "recipients", "expected"),
    [
        ({"smtp_host": ""}, ["a@example.test"], "SMTP no configurado"),
        ({"smtp_host": "smtp.example.test", "smtp_from": "", "smtp_user": ""}, ["a@example.test"], "Remitente SMTP no configurado"),
        ({"smtp_host": "smtp.example.test", "smtp_from": "infonalia@example.test"}, [], "El usuario de destino no tiene email configurado"),
    ],
)
def test_send_notification_email_with_settings_returns_configuration_errors(
    settings: dict[str, object],
    recipients: list[str],
    expected: str,
) -> None:
    result = send_notification_email_with_settings(
        settings=settings,
        recipients=recipients,
        subject="Asunto",
        body="Cuerpo",
        html_body="<p>Cuerpo</p>",
        logo_path=None,
        now=lambda: "2026-06-12T10:00:00",
        smtp_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no smtp")),
        smtp_ssl_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no smtp ssl")),
    )

    assert result == (None, expected)


def test_send_notification_email_with_settings_uses_tls_login_and_send() -> None:
    servers: list[FakeSMTP] = []

    def smtp_factory(host: str, port: int, *, timeout: int) -> FakeSMTP:
        server = FakeSMTP(host, port, timeout=timeout)
        servers.append(server)
        return server

    sent_at, error = send_notification_email_with_settings(
        settings={
            "smtp_host": "smtp.example.test",
            "smtp_port": "2525",
            "smtp_user": "user",
            "smtp_password": "secret",
            "smtp_from": "",
            "smtp_tls": "1",
            "smtp_ssl": "0",
        },
        recipients=["nuria@example.test"],
        subject="Asunto",
        body="",
        html_body="<p>Asunto</p>",
        logo_path=None,
        now=lambda: "2026-06-12T10:00:00",
        smtp_factory=smtp_factory,
        smtp_ssl_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no ssl")),
    )

    assert (sent_at, error) == ("2026-06-12T10:00:00", None)
    assert len(servers) == 1
    server = servers[0]
    assert (server.host, server.port, server.timeout) == ("smtp.example.test", 2525, 20)
    assert server.started_tls is True
    assert server.login_args == ("user", "secret")
    assert server.sent_message is not None
    assert server.sent_message["From"] == "user"
    assert server.sent_message["To"] == "nuria@example.test"
    assert server.sent_message["Subject"] == "Asunto"
    assert "Asunto" in server.sent_message.get_body(preferencelist=("plain",)).get_content()


def test_send_notification_email_with_settings_uses_ssl_without_starttls() -> None:
    ssl_servers: list[FakeSMTP] = []

    def smtp_ssl_factory(host: str, port: int, *, timeout: int) -> FakeSMTP:
        server = FakeSMTP(host, port, timeout=timeout)
        ssl_servers.append(server)
        return server

    sent_at, error = send_notification_email_with_settings(
        settings={
            "smtp_host": "smtp.example.test",
            "smtp_port": "",
            "smtp_user": "",
            "smtp_password": "",
            "smtp_from": "infonalia@example.test",
            "smtp_tls": "1",
            "smtp_ssl": "1",
        },
        recipients=["admin@example.test"],
        subject="Asunto",
        body="Cuerpo",
        html_body="<p>Cuerpo</p>",
        logo_path=None,
        now=lambda: "2026-06-12T10:00:00",
        smtp_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no plain smtp")),
        smtp_ssl_factory=smtp_ssl_factory,
    )

    assert (sent_at, error) == ("2026-06-12T10:00:00", None)
    assert len(ssl_servers) == 1
    assert ssl_servers[0].port == 587
    assert ssl_servers[0].started_tls is False
    assert ssl_servers[0].login_args is None


def test_send_notification_email_with_settings_preserves_windows_socket_error_message() -> None:
    error = PermissionError("blocked")
    error.winerror = 10013

    sent_at, message = send_notification_email_with_settings(
        settings={
            "smtp_host": "smtp.example.test",
            "smtp_port": "2525",
            "smtp_from": "infonalia@example.test",
        },
        recipients=["admin@example.test"],
        subject="Asunto",
        body="Cuerpo",
        html_body="<p>Cuerpo</p>",
        logo_path=None,
        now=lambda: "2026-06-12T10:00:00",
        smtp_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        smtp_ssl_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no ssl")),
    )

    assert sent_at is None
    assert message == (
        "Windows ha bloqueado la conexión SMTP saliente "
        "(smtp.example.test:2525). Revisa firewall, antivirus, proxy o permisos de red."
    )


def test_create_notification_record_preserves_inserted_shape() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE notificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            usuario_origen TEXT,
            usuario_destino TEXT,
            asunto TEXT,
            cuerpo TEXT,
            ficheros_adjuntos TEXT,
            email_sent_at TEXT,
            email_error TEXT
        )
        """
    )

    notification_id = create_notification_record(
        conn,
        usuario_origen=" Sistema ",
        usuario_destino=" nuria ",
        asunto=" Asunto ",
        cuerpo="Cuerpo",
        ficheros_adjuntos=" adjunto.pdf ",
        sent_at="2026-06-12T10:05:00",
        email_error=None,
        timestamp="2026-06-12T10:00:00",
    )

    row = conn.execute("SELECT * FROM notificaciones WHERE id = ?", (notification_id,)).fetchone()
    assert dict(row) == {
        "id": notification_id,
        "fecha_hora": "2026-06-12T10:00:00",
        "usuario_origen": "Sistema",
        "usuario_destino": "nuria",
        "asunto": "Asunto",
        "cuerpo": "Cuerpo",
        "ficheros_adjuntos": "adjunto.pdf",
        "email_sent_at": "2026-06-12T10:05:00",
        "email_error": None,
    }
