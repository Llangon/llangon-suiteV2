"""Minimal, defence-in-depth read-only access to the Suite client catalogue."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {
    "id",
    "razon_social",
    "nombre_comercial",
    "activo",
    "updated_at",
}

_DENIED_ACTIONS = {
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_CREATE_INDEX,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_INDEX,
    sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
    sqlite3.SQLITE_CREATE_TEMP_VIEW,
    sqlite3.SQLITE_CREATE_TRIGGER,
    sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_INDEX,
    sqlite3.SQLITE_DROP_TEMP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_TRIGGER,
    sqlite3.SQLITE_DROP_TEMP_VIEW,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_REINDEX,
    sqlite3.SQLITE_ANALYZE,
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_DETACH,
    sqlite3.SQLITE_TRANSACTION,
    sqlite3.SQLITE_SAVEPOINT,
}


class ClientReadError(RuntimeError):
    pass


def default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "infonalia.db"


def _authorizer(action: int, _arg1: str | None, _arg2: str | None, _db: str | None, _trigger: str | None) -> int:
    if action in _DENIED_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_read_only(db_path: str | Path | None = None, *, timeout: float = 1.0) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    if not path.is_file():
        raise ClientReadError("No se encuentra la base local de Llangon Suite.")
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.set_authorizer(_authorizer)
        conn.execute("PRAGMA query_only=ON")
        return conn
    except sqlite3.Error as exc:
        raise ClientReadError("No se pudo abrir la base local en modo de solo lectura.") from exc


def _display_name(row: sqlite3.Row | dict[str, Any]) -> str:
    razon = str(row["razon_social"] or "").strip()
    nombre = str(row["nombre_comercial"] or "").strip()
    return razon or nombre or "Cliente sin nombre"


LEGACY_EXPORT_COLUMNS = (
    "id",
    "label",
    "display_name",
    "razon_social",
    "nombre_comercial",
    "active",
    "updated_at",
)


def read_client_catalog(
    db_path: str | Path | None = None,
    *,
    timeout: float = 1.0,
) -> tuple[list[str], list[dict[str, Any]]]:
    conn = open_read_only(db_path, timeout=timeout)
    try:
        table_info = conn.execute("PRAGMA table_info(clientes)").fetchall()
        raw_columns = [str(row[1]) for row in table_info]
        missing = sorted(REQUIRED_COLUMNS - set(raw_columns))
        if missing:
            raise ClientReadError("La base local no contiene la estructura de clientes esperada.")
        rows = conn.execute(
            """
            SELECT *
            FROM clientes
            ORDER BY activo DESC, lower(COALESCE(razon_social, nombre_comercial)), id ASC
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise ClientReadError("No se pudo consultar la lista local de clientes.") from exc
    finally:
        conn.close()

    names = [_display_name(row) for row in rows]
    duplicates = Counter(name.casefold() for name in names)
    clients: list[dict[str, Any]] = []
    for row, display_name in zip(rows, names, strict=True):
        razon = str(row["razon_social"] or "").strip()
        nombre = str(row["nombre_comercial"] or "").strip()
        active = bool(int(row["activo"] or 0))
        label = display_name
        if duplicates[display_name.casefold()] > 1:
            label = f"{display_name} [ID {int(row['id'])}]"
        if not active:
            label = f"{label} (inactivo)"
        item = {column: row[column] for column in raw_columns}
        item.update(
            {
                "id": int(row["id"]),
                "display_name": display_name,
                "razon_social": razon,
                "nombre_comercial": nombre,
                "active": active,
                "updated_at": str(row["updated_at"] or "").strip(),
                "label": label,
            }
        )
        clients.append(item)

    export_columns = list(LEGACY_EXPORT_COLUMNS)
    represented_raw = {"id", "razon_social", "nombre_comercial", "updated_at"}
    for column in raw_columns:
        if column in represented_raw:
            continue
        export_name = column if column not in export_columns else f"db_{column}"
        export_columns.append(export_name)
        if export_name != column:
            for item in clients:
                item[export_name] = item.get(column)
    return export_columns, clients


def read_clients(db_path: str | Path | None = None, *, timeout: float = 1.0) -> list[dict[str, Any]]:
    return read_client_catalog(db_path, timeout=timeout)[1]


__all__ = ("ClientReadError", "default_db_path", "open_read_only", "read_client_catalog", "read_clients")
