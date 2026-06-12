from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.notification_rendering import (
    build_notification_email_html,
    notification_body_parts,
    parse_day_review_notification,
)


def test_notification_rendering_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.notification_rendering", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.notification_rendering")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess", "smtplib"} & added


def test_notification_body_parts_preserves_current_detail_split() -> None:
    paragraphs, details = notification_body_parts("Hola\nExpediente: EXP-1\nEtiqueta demasiado larga para entrar como detalle: valor")

    assert paragraphs == ["Hola", "Etiqueta demasiado larga para entrar como detalle: valor"]
    assert details == [("Expediente", "EXP-1")]


def test_parse_day_review_notification_preserves_current_shape() -> None:
    parsed = parse_day_review_notification(
        "Día disponible para revisar\n"
        "Total de licitaciones del día: 3\n"
        "Licitaciones pendientes de revisión: 1\n"
        "Listado de licitaciones pendientes:\n"
        "- EXP-1 | Servicio | 12/06/2026 09:30\n"
    )

    assert parsed == {
        "intro": ["Día disponible para revisar"],
        "total": "3",
        "pendientes": "1",
        "no_interesting": False,
        "pending_items": [
            {
                "expediente": "EXP-1",
                "titulo": "Servicio",
                "fecha_hora": "12/06/2026 09:30",
            }
        ],
    }
    assert parse_day_review_notification("sin formato especial") is None


def test_build_notification_email_html_preserves_button_and_escaping() -> None:
    html = build_notification_email_html(
        "Día disponible para revisar",
        "Total de licitaciones del día: 1\nLicitaciones pendientes de revisión: 0\nNO HAY LICITACIONES INTERESANTES",
        "nuria",
        platform_url="https://example.test/panel?x=1&y=2",
        generated_at="2026-06-12T09:30:00",
    )

    assert "Acceder a la plataforma" in html
    assert "https://example.test/panel?x=1&amp;y=2" in html
    assert "NO HAY LICITACIONES INTERESANTES" in html
    assert "Destinatario: nuria" in html
    assert "12/06/2026 09:30" in html
