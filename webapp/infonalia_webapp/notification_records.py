from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

try:
    from .formatting import format_datetime_es
    from .normalization import clean_text
except ImportError:
    from formatting import format_datetime_es
    from normalization import clean_text


def first_param(params: Mapping[str, Sequence[str]], key: str, default: str = "") -> str:
    values = params.get(key, [default])
    return values[0] if values else default


def notification_query_filters(
    params: Mapping[str, Sequence[str]],
    user: Mapping[str, Any],
) -> tuple[list[str], list[object]]:
    search = clean_text(first_param(params, "q"))
    usuario_destino = clean_text(first_param(params, "usuario_destino")).lower()
    usuario_origen = clean_text(first_param(params, "usuario_origen")).lower()
    email_estado = clean_text(first_param(params, "email_estado"))
    scope = clean_text(first_param(params, "scope", "mine"))

    where = []
    values: list[object] = []

    if user.get("role") == "admin" and scope == "all":
        pass
    else:
        destinos = ["", user["username"]]
        placeholders = ", ".join("?" for _ in destinos)
        where.append(f"COALESCE(usuario_destino, '') IN ({placeholders})")
        values.extend(destinos)

    if usuario_destino:
        where.append("COALESCE(usuario_destino, '') = ?")
        values.append(usuario_destino)
    if usuario_origen:
        where.append("COALESCE(usuario_origen, '') = ?")
        values.append(usuario_origen)
    if search:
        where.append("(asunto LIKE ? OR cuerpo LIKE ?)")
        like = f"%{search}%"
        values.extend([like, like])
    if email_estado == "sent":
        where.append("email_sent_at IS NOT NULL AND email_sent_at <> ''")
    elif email_estado == "pending":
        where.append("(email_sent_at IS NULL OR email_sent_at = '')")

    return where, values


def notification_row_to_dict(row: Any) -> dict[str, object]:
    item = {key: row[key] for key in row.keys()}
    item["fecha_hora_formateada"] = format_datetime_es(row["fecha_hora"])
    return item


def notification_items_and_unread(rows: Sequence[Any]) -> tuple[list[dict[str, object]], int]:
    items = []
    unread = 0
    for row in rows:
        item = notification_row_to_dict(row)
        if not clean_text(row["read_at"]):
            unread += 1
        items.append(item)
    return items, unread
