from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

try:
    from .normalization import clean_text
except ImportError:
    from normalization import clean_text


COMMENT_ENTITY_TYPES = {"licitacion", "actuacion", "agenda_evento"}
COMMENT_VISIBILITIES = {"internal", "team"}
MAX_COMMENT_BODY_LENGTH = 5000


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def ensure_comments_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            author_user_id TEXT,
            author_name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            is_edited INTEGER NOT NULL DEFAULT 0,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            visibility TEXT NOT NULL DEFAULT 'internal',
            metadata_json TEXT
        )
        """
    )
    additions = {
        "deleted_at": "TEXT",
        "is_deleted": "INTEGER NOT NULL DEFAULT 0",
        "is_edited": "INTEGER NOT NULL DEFAULT 0",
        "is_pinned": "INTEGER NOT NULL DEFAULT 0",
        "visibility": "TEXT NOT NULL DEFAULT 'internal'",
        "metadata_json": "TEXT",
    }
    for column, definition in additions.items():
        if not _column_exists(conn, "comments", column):
            conn.execute(f"ALTER TABLE comments ADD COLUMN {column} {definition}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_entity ON comments(entity_type, entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_active ON comments(entity_type, entity_id, is_deleted)")


def _normalize_entity_type(value: object) -> str:
    entity_type = clean_text(value).lower()
    if entity_type not in COMMENT_ENTITY_TYPES:
        raise ValueError("Tipo de entidad no válido.")
    return entity_type


def _normalize_entity_id(value: object) -> int:
    try:
        entity_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Id de entidad no válido.") from exc
    if entity_id <= 0:
        raise ValueError("Id de entidad no válido.")
    return entity_id


def normalize_comment_body(value: object) -> str:
    body = clean_text(value)
    if not body:
        raise ValueError("El comentario no puede estar vacío.")
    if len(body) > MAX_COMMENT_BODY_LENGTH:
        raise ValueError(f"El comentario no puede superar {MAX_COMMENT_BODY_LENGTH} caracteres.")
    return body


def normalize_visibility(value: object) -> str:
    visibility = clean_text(value).lower() or "internal"
    return visibility if visibility in COMMENT_VISIBILITIES else "internal"


def validate_comment_entity(conn: sqlite3.Connection, entity_type: str, entity_id: int) -> None:
    table_by_type = {
        "licitacion": "licitaciones",
        "actuacion": "actuaciones",
        "agenda_evento": "agenda_eventos",
    }
    table = table_by_type[entity_type]
    if not _table_exists(conn, table):
        raise ValueError("La entidad indicada no existe.")
    row = conn.execute(f"SELECT id FROM {table} WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        raise ValueError("La entidad indicada no existe.")


def is_admin_user(user: Mapping[str, object] | None) -> bool:
    return clean_text((user or {}).get("role")).lower() == "admin"


def user_identity(user: Mapping[str, object] | None) -> tuple[str, str]:
    username = clean_text((user or {}).get("username")).lower()
    display_name = clean_text((user or {}).get("display_name")) or username or "Usuario"
    return username, display_name


def can_modify_comment(row: sqlite3.Row, user: Mapping[str, object] | None) -> bool:
    username, _ = user_identity(user)
    if clean_text(row["author_user_id"]).lower() == "system":
        return False
    return is_admin_user(user) or bool(username and clean_text(row["author_user_id"]).lower() == username)


def can_pin_comment(row: sqlite3.Row, user: Mapping[str, object] | None) -> bool:
    return can_modify_comment(row, user)


def comment_to_dict(row: sqlite3.Row, *, user: Mapping[str, object] | None = None) -> dict[str, object]:
    is_deleted = bool(row["is_deleted"] or 0)
    body = "Comentario eliminado." if is_deleted else row["body"]
    return {
        "id": int(row["id"]),
        "entity_type": row["entity_type"],
        "entity_id": int(row["entity_id"]),
        "author_user_id": row["author_user_id"] or "",
        "author_name": row["author_name"] or "",
        "body": body,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"] or "",
        "is_deleted": is_deleted,
        "is_edited": bool(row["is_edited"] or 0),
        "is_pinned": bool(row["is_pinned"] or 0),
        "visibility": row["visibility"] or "internal",
        "can_edit": (not is_deleted) and can_modify_comment(row, user),
        "can_delete": (not is_deleted) and can_modify_comment(row, user),
        "can_pin": (not is_deleted) and can_pin_comment(row, user),
    }


def list_comments(
    conn: sqlite3.Connection,
    *,
    entity_type: object,
    entity_id: object,
    user: Mapping[str, object] | None = None,
    include_deleted: bool = True,
) -> list[dict[str, object]]:
    ensure_comments_schema(conn)
    normalized_type = _normalize_entity_type(entity_type)
    normalized_id = _normalize_entity_id(entity_id)
    where = "entity_type = ? AND entity_id = ?"
    values: list[object] = [normalized_type, normalized_id]
    if not include_deleted:
        where += " AND is_deleted = 0"
    rows = conn.execute(
        f"""
        SELECT *
        FROM comments
        WHERE {where}
        ORDER BY is_pinned DESC, created_at ASC, id ASC
        """,
        values,
    ).fetchall()
    return [comment_to_dict(row, user=user) for row in rows]


def create_comment(
    conn: sqlite3.Connection,
    *,
    entity_type: object,
    entity_id: object,
    body: object,
    user: Mapping[str, object] | None,
    visibility: object = "internal",
    timestamp: str | None = None,
) -> dict[str, object]:
    ensure_comments_schema(conn)
    normalized_type = _normalize_entity_type(entity_type)
    normalized_id = _normalize_entity_id(entity_id)
    validate_comment_entity(conn, normalized_type, normalized_id)
    username, display_name = user_identity(user)
    created_at = timestamp or now_iso()
    cur = conn.execute(
        """
        INSERT INTO comments (
            entity_type, entity_id, author_user_id, author_name, body,
            created_at, updated_at, visibility
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_type,
            normalized_id,
            username,
            display_name,
            normalize_comment_body(body),
            created_at,
            created_at,
            normalize_visibility(visibility),
        ),
    )
    row = conn.execute("SELECT * FROM comments WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return comment_to_dict(row, user=user)


def create_system_comment(
    conn: sqlite3.Connection,
    *,
    entity_type: object,
    entity_id: object,
    body: object,
    metadata: Mapping[str, object] | None = None,
    timestamp: str | None = None,
) -> dict[str, object]:
    ensure_comments_schema(conn)
    normalized_type = _normalize_entity_type(entity_type)
    normalized_id = _normalize_entity_id(entity_id)
    validate_comment_entity(conn, normalized_type, normalized_id)
    created_at = timestamp or now_iso()
    cur = conn.execute(
        """
        INSERT INTO comments (
            entity_type, entity_id, author_user_id, author_name, body,
            created_at, updated_at, visibility, metadata_json
        )
        VALUES (?, ?, 'system', 'Sistema', ?, ?, ?, 'internal', ?)
        """,
        (
            normalized_type,
            normalized_id,
            normalize_comment_body(body),
            created_at,
            created_at,
            json.dumps(dict(metadata or {}), ensure_ascii=False) if metadata else "",
        ),
    )
    row = conn.execute("SELECT * FROM comments WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return comment_to_dict(row, user={"username": "system", "role": "admin"})


def update_comment(
    conn: sqlite3.Connection,
    *,
    comment_id: object,
    body: object,
    user: Mapping[str, object] | None,
    timestamp: str | None = None,
) -> dict[str, object]:
    ensure_comments_schema(conn)
    row = conn.execute("SELECT * FROM comments WHERE id = ?", (_normalize_entity_id(comment_id),)).fetchone()
    if not row:
        raise LookupError("Comentario no encontrado.")
    if row["is_deleted"]:
        raise ValueError("No se puede editar un comentario eliminado.")
    if not can_modify_comment(row, user):
        raise PermissionError("No tienes permiso para editar este comentario.")
    updated_at = timestamp or now_iso()
    conn.execute(
        """
        UPDATE comments
        SET body = ?, updated_at = ?, is_edited = 1
        WHERE id = ?
        """,
        (normalize_comment_body(body), updated_at, int(row["id"])),
    )
    updated = conn.execute("SELECT * FROM comments WHERE id = ?", (int(row["id"]),)).fetchone()
    return comment_to_dict(updated, user=user)


def delete_comment(
    conn: sqlite3.Connection,
    *,
    comment_id: object,
    user: Mapping[str, object] | None,
    timestamp: str | None = None,
) -> dict[str, object]:
    ensure_comments_schema(conn)
    row = conn.execute("SELECT * FROM comments WHERE id = ?", (_normalize_entity_id(comment_id),)).fetchone()
    if not row:
        raise LookupError("Comentario no encontrado.")
    if row["is_deleted"]:
        return comment_to_dict(row, user=user)
    if not can_modify_comment(row, user):
        raise PermissionError("No tienes permiso para eliminar este comentario.")
    deleted_at = timestamp or now_iso()
    conn.execute(
        """
        UPDATE comments
        SET is_deleted = 1, deleted_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (deleted_at, deleted_at, int(row["id"])),
    )
    deleted = conn.execute("SELECT * FROM comments WHERE id = ?", (int(row["id"]),)).fetchone()
    return comment_to_dict(deleted, user=user)


def set_comment_pinned(
    conn: sqlite3.Connection,
    *,
    comment_id: object,
    pinned: bool,
    user: Mapping[str, object] | None,
    timestamp: str | None = None,
) -> dict[str, object]:
    ensure_comments_schema(conn)
    row = conn.execute("SELECT * FROM comments WHERE id = ?", (_normalize_entity_id(comment_id),)).fetchone()
    if not row:
        raise LookupError("Comentario no encontrado.")
    if row["is_deleted"]:
        raise ValueError("No se puede fijar un comentario eliminado.")
    if not can_pin_comment(row, user):
        raise PermissionError("No tienes permiso para fijar este comentario.")
    updated_at = timestamp or now_iso()
    conn.execute(
        "UPDATE comments SET is_pinned = ?, updated_at = ? WHERE id = ?",
        (1 if pinned else 0, updated_at, int(row["id"])),
    )
    updated = conn.execute("SELECT * FROM comments WHERE id = ?", (int(row["id"]),)).fetchone()
    return comment_to_dict(updated, user=user)


def comments_summary_for_entities(
    conn: sqlite3.Connection,
    entities: Iterable[tuple[str, int]],
) -> dict[tuple[str, int], dict[str, object]]:
    ensure_comments_schema(conn)
    keys = [(clean_text(entity_type).lower(), int(entity_id)) for entity_type, entity_id in entities if int(entity_id) > 0]
    if not keys:
        return {}
    result: dict[tuple[str, int], dict[str, object]] = {
        key: {"count": 0, "latest": None, "pinned_count": 0}
        for key in keys
        if key[0] in COMMENT_ENTITY_TYPES
    }
    for entity_type in sorted({key[0] for key in result}):
        ids = [key[1] for key in result if key[0] == entity_type]
        if not ids:
            continue
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"""
            SELECT *
            FROM comments
            WHERE entity_type = ?
              AND entity_id IN ({placeholders})
              AND is_deleted = 0
            ORDER BY entity_id ASC, is_pinned DESC, created_at DESC, id DESC
            """,
            [entity_type, *ids],
        ).fetchall()
        seen_latest: set[tuple[str, int]] = set()
        for row in rows:
            key = (row["entity_type"], int(row["entity_id"]))
            if key not in result:
                continue
            result[key]["count"] = int(result[key]["count"] or 0) + 1
            if row["is_pinned"]:
                result[key]["pinned_count"] = int(result[key]["pinned_count"] or 0) + 1
            if key not in seen_latest:
                result[key]["latest"] = comment_to_dict(row)
                seen_latest.add(key)
    return result


def attach_comment_summaries(items: Sequence[dict[str, Any]], *, entity_type: str) -> None:
    # Kept as a tiny marker for future service-level enrichment; app.py performs the DB call in batches.
    return None


def recent_comments(conn: sqlite3.Connection, *, limit: int = 20) -> list[dict[str, object]]:
    ensure_comments_schema(conn)
    limit = max(1, min(int(limit or 20), 100))
    rows = conn.execute(
        """
        SELECT c.*,
               CASE
                 WHEN c.entity_type = 'licitacion' THEN l.expediente
                 WHEN c.entity_type = 'actuacion' THEN a.titulo
                 WHEN c.entity_type = 'agenda_evento' THEN g.titulo
                 ELSE ''
               END AS entity_title
        FROM comments c
        LEFT JOIN licitaciones l ON c.entity_type = 'licitacion' AND l.id = c.entity_id
        LEFT JOIN actuaciones a ON c.entity_type = 'actuacion' AND a.id = c.entity_id
        LEFT JOIN agenda_eventos g ON c.entity_type = 'agenda_evento' AND g.id = c.entity_id
        WHERE c.is_deleted = 0
        ORDER BY c.created_at DESC, c.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    items = []
    for row in rows:
        item = comment_to_dict(row)
        item["entity_title"] = row["entity_title"] or ""
        items.append(item)
    return items
