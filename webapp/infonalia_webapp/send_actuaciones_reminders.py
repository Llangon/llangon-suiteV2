from __future__ import annotations

import argparse
import os
import smtplib
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from . import app
    from .actuaciones_reminders import build_reminder_body, reminder_rows, send_reminder_email
except ImportError:
    from webapp.infonalia_webapp import app
    from webapp.infonalia_webapp.actuaciones_reminders import build_reminder_body, reminder_rows, send_reminder_email


def configured_recipients() -> list[str]:
    configured = os.environ.get("INFONALIA_REMINDER_RECIPIENTS", "")
    if configured.strip():
        return [item.strip() for item in configured.split(",") if item.strip()]
    return [
        user["email"]
        for user in app.list_user_records(active_only=True)
        if str(user.get("email") or "").strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enviar resumen de actuaciones y vencimientos.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el resumen sin enviar email.")
    args = parser.parse_args(argv)

    app.init_db()
    with app.db_session() as conn:
        rows = reminder_rows(conn)
    recipients = configured_recipients()
    text, _html = build_reminder_body(rows)
    if args.dry_run:
        print(text)
        print("")
        print("Destinatarios:", ", ".join(recipients) or "sin destinatarios")
        return 0

    sent_at, error = send_reminder_email(
        settings=app.get_settings(),
        recipients=recipients,
        rows=rows,
        now=app.now_iso,
        smtp_factory=smtplib.SMTP,
        smtp_ssl_factory=smtplib.SMTP_SSL,
    )
    if error:
        print(f"No se pudo enviar el recordatorio: {error}", file=sys.stderr)
        return 1
    print(f"Recordatorio enviado: {sent_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
