from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.notification_records import (
    notification_items_and_unread,
    notification_query_filters,
    notification_row_to_dict,
)


class FakeRow(dict):
    pass


def test_notification_records_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.notification_records", None)
    top_level_app_was_imported = "app" in sys.modules
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.notification_records")

    added = set(sys.modules) - before
    assert ("app" in sys.modules) is top_level_app_was_imported
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess", "smtplib"} & added


def test_notification_query_filters_preserves_private_default_scope() -> None:
    where, values = notification_query_filters({}, {"username": "nuria", "role": "nuria"})

    assert where == ["COALESCE(usuario_destino, '') IN (?, ?)"]
    assert values == ["", "nuria"]


def test_notification_query_filters_admin_all_skips_visibility_scope() -> None:
    where, values = notification_query_filters(
        {"scope": ["all"], "q": ["Informe"]},
        {"username": "admin", "role": "admin"},
    )

    assert where == ["(asunto LIKE ? OR cuerpo LIKE ?)"]
    assert values == ["%Informe%", "%Informe%"]


def test_notification_query_filters_applies_all_supported_filters() -> None:
    where, values = notification_query_filters(
        {
            "usuario_destino": [" Nuria "],
            "usuario_origen": [" Sistema "],
            "q": ["licitación"],
            "email_estado": ["pending"],
        },
        {"username": "admin", "role": "admin"},
    )

    assert where == [
        "COALESCE(usuario_destino, '') IN (?, ?)",
        "COALESCE(usuario_destino, '') = ?",
        "COALESCE(usuario_origen, '') = ?",
        "(asunto LIKE ? OR cuerpo LIKE ?)",
        "(email_sent_at IS NULL OR email_sent_at = '')",
    ]
    assert values == ["", "admin", "nuria", "sistema", "%licitación%", "%licitación%"]


def test_notification_query_filters_sent_email_state() -> None:
    where, values = notification_query_filters(
        {"email_estado": ["sent"]},
        {"username": "admin", "role": "admin"},
    )

    assert where == [
        "COALESCE(usuario_destino, '') IN (?, ?)",
        "email_sent_at IS NOT NULL AND email_sent_at <> ''",
    ]
    assert values == ["", "admin"]


def test_notification_row_to_dict_adds_formatted_date() -> None:
    row = FakeRow(
        {
            "id": 3,
            "fecha_hora": "2026-06-12T10:30:00",
            "asunto": "Aviso",
            "read_at": "",
        }
    )

    item = notification_row_to_dict(row)

    assert item == {
        "id": 3,
        "fecha_hora": "2026-06-12T10:30:00",
        "asunto": "Aviso",
        "read_at": "",
        "fecha_hora_formateada": "12/06/2026 10:30",
    }


def test_notification_items_and_unread_preserves_unread_count() -> None:
    rows = [
        FakeRow({"id": 1, "fecha_hora": "2026-06-12T10:30:00", "read_at": ""}),
        FakeRow({"id": 2, "fecha_hora": "2026-06-12T10:31:00", "read_at": "2026-06-12T10:32:00"}),
        FakeRow({"id": 3, "fecha_hora": "2026-06-12T10:33:00", "read_at": None}),
    ]

    items, unread = notification_items_and_unread(rows)

    assert [item["id"] for item in items] == [1, 2, 3]
    assert unread == 2
