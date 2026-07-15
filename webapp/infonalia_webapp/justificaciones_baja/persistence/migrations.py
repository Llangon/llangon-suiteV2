"""Idempotent SQLite schema for low-bid justification persistence.

The migration is deliberately additive.  It owns only tables prefixed with
``justificacion_baja`` and never reads or writes business rows while ensuring
the schema.
"""

from __future__ import annotations

import sqlite3


JUSTIFICATION_STATES = (
    "borrador",
    "enviado_cliente",
    "final",
)


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    if column not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_justificaciones_baja_schema(conn: sqlite3.Connection) -> None:
    """Create the isolated, idempotent schema registered as migration 0029."""

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS justificaciones_baja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            cliente_id INTEGER NOT NULL,
            expediente TEXT NOT NULL,
            lote_numero TEXT NOT NULL,
            lote_nombre TEXT NOT NULL DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'borrador'
                CHECK (estado IN ('borrador', 'enviado_cliente', 'final')),
            draft_json TEXT NOT NULL,
            draft_frozen INTEGER NOT NULL DEFAULT 0 CHECK (draft_frozen IN (0, 1)),
            draft_based_on_version INTEGER,
            latest_version INTEGER NOT NULL DEFAULT 0 CHECK (latest_version >= 0),
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            profit_raw TEXT,
            profit_display TEXT,
            profit_percentage_raw TEXT,
            profit_percentage_display TEXT,
            route_asset_id INTEGER,
            created_by TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id) ON DELETE RESTRICT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT,
            FOREIGN KEY (route_asset_id, id)
                REFERENCES justificacion_baja_assets(id, justificacion_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS justificacion_baja_versiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            justificacion_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number >= 1),
            snapshot_json TEXT NOT NULL,
            snapshot_sha256 TEXT NOT NULL,
            document_context_json TEXT NOT NULL,
            document_context_sha256 TEXT NOT NULL,
            snapshot_schema_version TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (justificacion_id, version_number),
            UNIQUE (id, justificacion_id),
            FOREIGN KEY (justificacion_id) REFERENCES justificaciones_baja(id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS justificacion_baja_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            justificacion_id INTEGER NOT NULL,
            version_id INTEGER NOT NULL,
            document_type TEXT NOT NULL CHECK (document_type IN ('word', 'excel')),
            generation_number INTEGER NOT NULL CHECK (generation_number >= 1),
            file_name TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            snapshot_sha256 TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            template_version TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (justificacion_id, relative_path),
            UNIQUE (justificacion_id, version_id, document_type, generation_number),
            FOREIGN KEY (justificacion_id) REFERENCES justificaciones_baja(id) ON DELETE RESTRICT,
            FOREIGN KEY (version_id, justificacion_id)
                REFERENCES justificacion_baja_versiones(id, justificacion_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS justificacion_baja_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            justificacion_id INTEGER NOT NULL,
            asset_kind TEXT NOT NULL DEFAULT 'route_image'
                CHECK (asset_kind = 'route_image'),
            file_name TEXT NOT NULL,
            mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png', 'image/jpeg')),
            width_px INTEGER NOT NULL CHECK (width_px > 0),
            height_px INTEGER NOT NULL CHECK (height_px > 0),
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            content BLOB NOT NULL,
            replaced_asset_id INTEGER,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (id, justificacion_id),
            FOREIGN KEY (justificacion_id) REFERENCES justificaciones_baja(id) ON DELETE RESTRICT,
            FOREIGN KEY (replaced_asset_id, justificacion_id)
                REFERENCES justificacion_baja_assets(id, justificacion_id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS justificacion_baja_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            justificacion_id INTEGER NOT NULL,
            version_id INTEGER,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (justificacion_id) REFERENCES justificaciones_baja(id) ON DELETE RESTRICT,
            FOREIGN KEY (version_id, justificacion_id)
                REFERENCES justificacion_baja_versiones(id, justificacion_id) ON DELETE RESTRICT
        )
        """
    )

    # Additive compatibility for databases created with an early local spike.
    _add_column_if_missing(conn, "justificaciones_baja", "profit_percentage_raw", "TEXT")
    _add_column_if_missing(conn, "justificaciones_baja", "profit_percentage_display", "TEXT")
    _add_column_if_missing(conn, "justificaciones_baja", "route_asset_id", "INTEGER")
    _add_column_if_missing(
        conn,
        "justificacion_baja_versiones",
        "document_context_sha256",
        "TEXT NOT NULL DEFAULT ''",
    )
    _add_column_if_missing(
        conn,
        "justificacion_baja_documentos",
        "generation_number",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(
        conn,
        "justificacion_baja_documentos",
        "snapshot_sha256",
        "TEXT NOT NULL DEFAULT ''",
    )

    indexes = (
        "CREATE INDEX IF NOT EXISTS idx_jb_licitacion ON justificaciones_baja(licitacion_id, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_cliente ON justificaciones_baja(cliente_id, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_estado ON justificaciones_baja(estado, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_versiones ON justificacion_baja_versiones(justificacion_id, version_number DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_versiones_hash ON justificacion_baja_versiones(justificacion_id, snapshot_sha256)",
        "CREATE INDEX IF NOT EXISTS idx_jb_documentos ON justificacion_baja_documentos(justificacion_id, version_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_assets ON justificacion_baja_assets(justificacion_id, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jb_assets_hash ON justificacion_baja_assets(justificacion_id, sha256)",
        "CREATE INDEX IF NOT EXISTS idx_jb_historial ON justificacion_baja_historial(justificacion_id, created_at DESC, id DESC)",
    )
    for statement in indexes:
        conn.execute(statement)

    # Frozen versions, generated-document audit records, assets and history are
    # append-only. Replacement is represented by a new row and a traced pointer.
    immutable_tables = {
        "versiones": "justificacion_baja_versiones",
        "documentos": "justificacion_baja_documentos",
        "assets": "justificacion_baja_assets",
        "historial": "justificacion_baja_historial",
    }
    for suffix, table in immutable_tables.items():
        conn.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_jb_{suffix}_no_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END
            """
        )
        conn.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_jb_{suffix}_no_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END
            """
        )

    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_jb_documentos_payload_consistente
        BEFORE INSERT ON justificacion_baja_documentos
        WHEN EXISTS (
            SELECT 1
            FROM justificacion_baja_documentos existing
            WHERE existing.justificacion_id = NEW.justificacion_id
              AND existing.version_id = NEW.version_id
              AND existing.generation_number = NEW.generation_number
              AND (
                    existing.snapshot_sha256 <> NEW.snapshot_sha256
                 OR existing.payload_sha256 <> NEW.payload_sha256
              )
        )
        BEGIN
            SELECT RAISE(ABORT, 'document generation hashes do not match');
        END
        """
    )


__all__ = ("JUSTIFICATION_STATES", "ensure_justificaciones_baja_schema")
