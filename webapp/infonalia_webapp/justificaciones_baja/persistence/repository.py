"""Small SQLite repository with optimistic concurrency and immutable versions."""

from __future__ import annotations

import hashlib
import itertools
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterator, Mapping

from .migrations import JUSTIFICATION_STATES, ensure_justificaciones_baja_schema


class JustificationNotFoundError(LookupError):
    """Raised when a justification or frozen version does not exist."""


class JustificationConflictError(RuntimeError):
    """Raised when an optimistic revision no longer matches."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_SAVEPOINT_SEQUENCE = itertools.count(1)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _validate_hash(value: str, *, label: str) -> str:
    normalized = str(value or "").strip().upper()
    if len(normalized) != 64 or any(character not in "0123456789ABCDEF" for character in normalized):
        raise ValueError(f"{label} debe ser un SHA-256 hexadecimal de 64 caracteres.")
    return normalized


def _validate_state(value: str) -> str:
    if value not in JUSTIFICATION_STATES:
        allowed = ", ".join(JUSTIFICATION_STATES)
        raise ValueError(f"Estado no válido. Valores permitidos: {allowed}.")
    return value


def _validate_relative_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if not normalized or posix.is_absolute() or windows.is_absolute() or ".." in posix.parts:
        raise ValueError("relative_path debe ser una ruta relativa segura.")
    return normalized


def _like_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _validate_json_text(value: str, *, label: str) -> None:
    try:
        json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} no contiene JSON válido.") from exc


def _validate_no_embedded_binary(value: object, *, path: str = "draft") -> None:
    """Reject embedded image/base64 payloads; drafts store only logical asset ids."""

    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError(f"{path} no puede contener datos binarios; usa asset_id.")
    if isinstance(value, str) and value.lstrip().lower().startswith("data:image/"):
        raise ValueError(f"{path} no puede contener imágenes base64; usa asset_id.")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            normalized_key = key_text.lower().replace("-", "_")
            if "base64" in normalized_key or normalized_key in {
                "image_data",
                "image_bytes",
                "content_bytes",
                "blob",
            }:
                raise ValueError(f"{path}.{key_text} no puede almacenar binarios; usa asset_id.")
            _validate_no_embedded_binary(nested, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_no_embedded_binary(nested, path=f"{path}[{index}]")


@contextmanager
def _savepoint(conn: sqlite3.Connection) -> Iterator[None]:
    name = f"jb_repository_{next(_SAVEPOINT_SEQUENCE)}"
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")
        raise
    else:
        conn.execute(f"RELEASE {name}")


@dataclass(slots=True)
class JustificationRepository:
    conn: sqlite3.Connection

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Group several repository operations into one rollback boundary."""

        with _savepoint(self.conn):
            yield

    def create(
        self,
        *,
        licitacion_id: int,
        cliente_id: int,
        expediente: str,
        lote_numero: str,
        lote_nombre: str,
        draft: Mapping[str, Any],
        user_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        _validate_no_embedded_binary(draft)
        with _savepoint(self.conn):
            cursor = self.conn.execute(
                """
                INSERT INTO justificaciones_baja (
                    licitacion_id, cliente_id, expediente, lote_numero, lote_nombre,
                    estado, draft_json, draft_frozen, latest_version, revision,
                    created_by, updated_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'borrador', ?, 0, 0, 1, ?, ?, ?, ?)
                """,
                (
                    licitacion_id,
                    cliente_id,
                    expediente,
                    lote_numero,
                    lote_nombre,
                    canonical_json(dict(draft)),
                    user_id,
                    user_id,
                    timestamp,
                    timestamp,
                ),
            )
            row_id = int(cursor.lastrowid)
            self.add_history(
                row_id,
                event_type="created",
                message="Justificación creada.",
                user_id=user_id,
                timestamp=timestamp,
            )
        return self.get(row_id)

    def create_with_draft(
        self,
        *,
        licitacion_id: int,
        initial_cliente_id: int,
        expediente: str,
        lote_numero: str,
        lote_nombre: str,
        initial_draft: Mapping[str, Any],
        draft: Mapping[str, Any],
        cliente_id: int,
        profit_raw: str | None,
        profit_display: str | None,
        profit_percentage_raw: str | None,
        profit_percentage_display: str | None,
        user_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        """Create and persist a supplied full draft as one SQLite operation."""

        with _savepoint(self.conn):
            created = self.create(
                licitacion_id=licitacion_id,
                cliente_id=initial_cliente_id,
                expediente=expediente,
                lote_numero=lote_numero,
                lote_nombre=lote_nombre,
                draft=initial_draft,
                user_id=user_id,
                timestamp=timestamp,
            )
            return self.update_draft(
                int(created["id"]),
                expected_revision=int(created["revision"]),
                draft=draft,
                cliente_id=cliente_id,
                expediente=str(draft["identification"]["expediente"]),
                lote_numero=str(draft["identification"]["lot_number"]),
                lote_nombre=str(draft["identification"]["lot_name"]),
                profit_raw=profit_raw,
                profit_display=profit_display,
                profit_percentage_raw=profit_percentage_raw,
                profit_percentage_display=profit_percentage_display,
                user_id=user_id,
                timestamp=timestamp,
                event_type="initial_draft_saved",
                event_message="Borrador inicial completo guardado.",
            )

    def get(self, justification_id: int, *, include_related: bool = True) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT jb.*, c.razon_social AS cliente_razon_social,
                   l.objeto AS licitacion_objeto, l.organismo AS licitacion_organismo,
                   l.ruta_carpeta AS licitacion_ruta_carpeta
            FROM justificaciones_baja jb
            JOIN clientes c ON c.id = jb.cliente_id
            JOIN licitaciones l ON l.id = jb.licitacion_id
            WHERE jb.id = ? AND jb.archived_at IS NULL
            """,
            (justification_id,),
        ).fetchone()
        if row is None:
            raise JustificationNotFoundError("No existe la justificación solicitada.")
        result = _justification_row(row)
        if include_related:
            result["versions"] = self.list_versions(justification_id)
            result["documents"] = self.list_documents(justification_id)
            result["route_image"] = self.get_route_image(
                justification_id=justification_id,
                include_content=False,
            )
            result["history"] = self.list_history(justification_id)
        return result

    def list(
        self,
        *,
        licitacion_id: int | None = None,
        cliente_id: int | None = None,
        state: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        where = ["jb.archived_at IS NULL"]
        params: list[object] = []
        if licitacion_id is not None:
            where.append("jb.licitacion_id = ?")
            params.append(licitacion_id)
        if cliente_id is not None:
            where.append("jb.cliente_id = ?")
            params.append(cliente_id)
        if state:
            _validate_state(state)
            where.append("jb.estado = ?")
            params.append(state)
        query = str(q or "").strip()
        if query:
            if len(query) > 200:
                raise ValueError("q no puede superar 200 caracteres.")
            where.append(
                """
                LOWER(
                    COALESCE(jb.expediente, '') || ' ' ||
                    COALESCE(jb.lote_numero, '') || ' ' ||
                    COALESCE(jb.lote_nombre, '') || ' ' ||
                    COALESCE(c.razon_social, '') || ' ' ||
                    COALESCE(l.objeto, '') || ' ' ||
                    COALESCE(l.organismo, '')
                ) LIKE LOWER(?) ESCAPE '\\'
                """
            )
            params.append(f"%{_like_literal(query)}%")
        rows = self.conn.execute(
            f"""
            SELECT jb.*, c.razon_social AS cliente_razon_social,
                   l.objeto AS licitacion_objeto, l.organismo AS licitacion_organismo,
                   l.ruta_carpeta AS licitacion_ruta_carpeta,
                   (SELECT COUNT(*) FROM justificacion_baja_documentos d WHERE d.justificacion_id = jb.id) AS document_count
            FROM justificaciones_baja jb
            JOIN clientes c ON c.id = jb.cliente_id
            JOIN licitaciones l ON l.id = jb.licitacion_id
            WHERE {' AND '.join(where)}
            ORDER BY jb.updated_at DESC, jb.id DESC
            """,
            params,
        ).fetchall()
        return [_justification_row(row, include_draft=False) for row in rows]

    def update_draft(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        draft: Mapping[str, Any],
        expediente: str,
        lote_numero: str,
        lote_nombre: str,
        profit_raw: str | None,
        profit_display: str | None,
        user_id: str,
        timestamp: str,
        event_type: str = "saved",
        event_message: str = "Borrador guardado.",
        event_metadata: Mapping[str, Any] | None = None,
        profit_percentage_raw: str | None = None,
        profit_percentage_display: str | None = None,
        cliente_id: int | None = None,
    ) -> dict[str, Any]:
        _validate_no_embedded_binary(draft)
        with _savepoint(self.conn):
            row = self.conn.execute(
                """
                SELECT draft_frozen, latest_version, revision, cliente_id
                FROM justificaciones_baja
                WHERE id = ? AND archived_at IS NULL
                """,
                (justification_id,),
            ).fetchone()
            if row is None:
                raise JustificationNotFoundError("No existe la justificación solicitada.")
            if int(row["revision"]) != expected_revision:
                raise JustificationConflictError(
                    "El borrador ha cambiado en otra pestaña. Recarga antes de continuar."
                )
            previous_cliente_id = int(row["cliente_id"])
            target_cliente_id = previous_cliente_id if cliente_id is None else int(cliente_id)
            if target_cliente_id <= 0 or self.conn.execute(
                "SELECT 1 FROM clientes WHERE id = ?",
                (target_cliente_id,),
            ).fetchone() is None:
                raise ValueError("El cliente indicado en el borrador no existe.")
            was_frozen = bool(row["draft_frozen"])
            cursor = self.conn.execute(
                """
                UPDATE justificaciones_baja
                SET cliente_id = ?, expediente = ?, lote_numero = ?, lote_nombre = ?,
                    estado = 'borrador',
                    draft_json = ?, draft_frozen = 0,
                    draft_based_on_version = CASE
                        WHEN draft_frozen = 1 THEN latest_version
                        ELSE draft_based_on_version
                    END,
                    revision = revision + 1, profit_raw = ?, profit_display = ?,
                    profit_percentage_raw = ?, profit_percentage_display = ?,
                    updated_by = ?, updated_at = ?
                WHERE id = ? AND revision = ? AND archived_at IS NULL
                """,
                (
                    target_cliente_id,
                    expediente,
                    lote_numero,
                    lote_nombre,
                    canonical_json(dict(draft)),
                    profit_raw,
                    profit_display,
                    profit_percentage_raw,
                    profit_percentage_display,
                    user_id,
                    timestamp,
                    justification_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise JustificationConflictError(
                    "El borrador ha cambiado en otra pestaña. Recarga antes de continuar."
                )
            if target_cliente_id != previous_cliente_id:
                self.add_history(
                    justification_id,
                    event_type="client_changed",
                    message="Cliente vinculado actualizado desde el borrador.",
                    metadata={
                        "previous_cliente_id": previous_cliente_id,
                        "cliente_id": target_cliente_id,
                    },
                    user_id=user_id,
                    timestamp=timestamp,
                )
            if was_frozen:
                self.add_history(
                    justification_id,
                    event_type="new_draft_from_version",
                    message="Se creó un nuevo borrador desde la última versión congelada.",
                    metadata={"version": int(row["latest_version"] or 0)},
                    user_id=user_id,
                    timestamp=timestamp,
                )
            self.add_history(
                justification_id,
                event_type=event_type,
                message=event_message,
                metadata=event_metadata,
                user_id=user_id,
                timestamp=timestamp,
            )
        return self.get(justification_id)

    def update_product_locks(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        draft: Mapping[str, Any],
        line_ids: list[str] | tuple[str, ...],
        locked: bool,
        cliente_id: int,
        expediente: str,
        lote_numero: str,
        lote_nombre: str,
        profit_raw: str | None,
        profit_display: str | None,
        profit_percentage_raw: str | None,
        profit_percentage_display: str | None,
        user_id: str,
        timestamp: str,
        event_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a validated multi-product lock change in one revision."""

        if not isinstance(locked, bool):
            raise ValueError("locked debe ser booleano.")
        selected = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in line_ids
                if item is not None and str(item).strip()
            )
        )
        if not selected:
            raise ValueError("line_ids debe contener al menos una línea.")
        products = draft.get("products")
        if not isinstance(products, list):
            raise ValueError("El borrador no contiene una lista de productos válida.")
        by_id = {
            str(item.get("line_id")): item
            for item in products
            if isinstance(item, Mapping) and item.get("line_id")
        }
        missing = [line_id for line_id in selected if line_id not in by_id]
        if missing:
            raise ValueError(f"No existen las líneas indicadas: {', '.join(missing)}.")
        if any(by_id[line_id].get("locked") is not locked for line_id in selected):
            raise ValueError("El borrador no refleja el bloqueo solicitado.")
        single = len(selected) == 1
        metadata = {
            **dict(event_metadata or {}),
            "line_ids": list(selected),
            "locked": locked,
        }
        if single:
            metadata["line_id"] = selected[0]
        return self.update_draft(
            justification_id,
            expected_revision=expected_revision,
            draft=draft,
            cliente_id=cliente_id,
            expediente=expediente,
            lote_numero=lote_numero,
            lote_nombre=lote_nombre,
            profit_raw=profit_raw,
            profit_display=profit_display,
            profit_percentage_raw=profit_percentage_raw,
            profit_percentage_display=profit_percentage_display,
            user_id=user_id,
            timestamp=timestamp,
            event_type=(
                "product_locked"
                if single and locked
                else "product_unlocked"
                if single
                else "products_locked"
                if locked
                else "products_unlocked"
            ),
            event_message=(
                "Producto bloqueado."
                if single and locked
                else "Producto desbloqueado."
                if single
                else "Productos bloqueados."
                if locked
                else "Productos desbloqueados."
            ),
            event_metadata=metadata,
        )

    def freeze(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        snapshot_json: str,
        snapshot_sha256: str,
        document_context: Mapping[str, Any],
        snapshot_schema_version: str,
        algorithm_version: str,
        user_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        _validate_json_text(snapshot_json, label="snapshot_json")
        normalized_snapshot_hash = _validate_hash(snapshot_sha256, label="snapshot_sha256")
        if _sha256_text(snapshot_json) != normalized_snapshot_hash:
            raise ValueError("snapshot_sha256 no coincide con snapshot_json.")
        _validate_no_embedded_binary(document_context, path="document_context")
        context_json = canonical_json(dict(document_context))
        context_hash = _sha256_text(context_json)

        try:
            with _savepoint(self.conn):
                row = self.conn.execute(
                    """
                    SELECT revision, latest_version, draft_frozen
                    FROM justificaciones_baja
                    WHERE id = ? AND archived_at IS NULL
                    """,
                    (justification_id,),
                ).fetchone()
                if row is None:
                    raise JustificationNotFoundError("No existe la justificación solicitada.")
                if int(row["revision"]) != expected_revision:
                    raise JustificationConflictError(
                        "El borrador ha cambiado en otra pestaña. Recarga antes de congelar."
                    )
                if bool(row["draft_frozen"]):
                    raise JustificationConflictError(
                        "La versión actual ya está congelada; crea antes un nuevo borrador."
                    )
                next_version = int(row["latest_version"] or 0) + 1
                cursor = self.conn.execute(
                    """
                    INSERT INTO justificacion_baja_versiones (
                        justificacion_id, version_number, snapshot_json, snapshot_sha256,
                        document_context_json, document_context_sha256,
                        snapshot_schema_version, algorithm_version, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        justification_id,
                        next_version,
                        snapshot_json,
                        normalized_snapshot_hash,
                        context_json,
                        context_hash,
                        snapshot_schema_version,
                        algorithm_version,
                        user_id,
                        timestamp,
                    ),
                )
                version_id = int(cursor.lastrowid)
                updated = self.conn.execute(
                    """
                    UPDATE justificaciones_baja
                    SET draft_frozen = 1, latest_version = ?, revision = revision + 1,
                        updated_by = ?, updated_at = ?
                    WHERE id = ? AND revision = ? AND draft_frozen = 0
                      AND archived_at IS NULL
                    """,
                    (next_version, user_id, timestamp, justification_id, expected_revision),
                )
                if updated.rowcount != 1:
                    raise JustificationConflictError(
                        "No se pudo congelar por un cambio concurrente."
                    )
                self.add_history(
                    justification_id,
                    version_id=version_id,
                    event_type="frozen",
                    message=f"Versión económica {next_version} congelada.",
                    metadata={
                        "snapshot_sha256": normalized_snapshot_hash,
                        "document_context_sha256": context_hash,
                        "version": next_version,
                    },
                    user_id=user_id,
                    timestamp=timestamp,
                )
        except sqlite3.IntegrityError as exc:
            raise JustificationConflictError(
                "No se pudo congelar la versión por un conflicto de persistencia."
            ) from exc
        return self.get_version(justification_id, version_number=next_version)

    def get_version(
        self,
        justification_id: int,
        *,
        version_number: int | None = None,
        version_id: int | None = None,
    ) -> dict[str, Any]:
        if version_id is not None:
            where = "id = ? AND justificacion_id = ?"
            params = (version_id, justification_id)
        elif version_number is not None:
            where = "justificacion_id = ? AND version_number = ?"
            params = (justification_id, version_number)
        else:
            where = "justificacion_id = ?"
            params = (justification_id,)
        row = self.conn.execute(
            f"SELECT * FROM justificacion_baja_versiones WHERE {where} ORDER BY version_number DESC LIMIT 1",
            params,
        ).fetchone()
        if row is None:
            raise JustificationNotFoundError("No existe la versión congelada solicitada.")
        return _version_row(row)

    def list_versions(self, justification_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM justificacion_baja_versiones WHERE justificacion_id = ? ORDER BY version_number DESC",
            (justification_id,),
        ).fetchall()
        return [_version_row(row, include_payload=False) for row in rows]

    def add_document(
        self,
        justification_id: int,
        *,
        version_id: int,
        document_type: str,
        file_name: str,
        relative_path: str,
        sha256: str,
        size_bytes: int,
        payload_sha256: str,
        template_version: str,
        user_id: str,
        timestamp: str,
        generation_number: int | None = None,
        snapshot_sha256: str | None = None,
    ) -> dict[str, Any]:
        if document_type not in {"word", "excel"}:
            raise ValueError("document_type debe ser 'word' o 'excel'.")
        if size_bytes < 0:
            raise ValueError("size_bytes no puede ser negativo.")
        normalized_path = _validate_relative_path(relative_path)
        normalized_file_hash = _validate_hash(sha256, label="sha256")
        normalized_payload_hash = _validate_hash(payload_sha256, label="payload_sha256")

        try:
            with _savepoint(self.conn):
                version = self.conn.execute(
                    """
                    SELECT id, snapshot_sha256
                    FROM justificacion_baja_versiones
                    WHERE id = ? AND justificacion_id = ?
                    """,
                    (version_id, justification_id),
                ).fetchone()
                if version is None:
                    raise JustificationNotFoundError(
                        "La versión no pertenece a la justificación indicada."
                    )
                stored_snapshot_hash = str(version["snapshot_sha256"]).upper()
                if snapshot_sha256 is not None:
                    supplied_snapshot_hash = _validate_hash(
                        snapshot_sha256,
                        label="snapshot_sha256",
                    )
                    if supplied_snapshot_hash != stored_snapshot_hash:
                        raise ValueError(
                            "snapshot_sha256 no coincide con la versión congelada."
                        )
                if generation_number is None:
                    generation_row = self.conn.execute(
                        """
                        SELECT COALESCE(MAX(generation_number), 0) + 1
                        FROM justificacion_baja_documentos
                        WHERE justificacion_id = ? AND version_id = ? AND document_type = ?
                        """,
                        (justification_id, version_id, document_type),
                    ).fetchone()
                    resolved_generation = int(generation_row[0])
                else:
                    resolved_generation = int(generation_number)
                if resolved_generation < 1:
                    raise ValueError("generation_number debe ser mayor o igual que 1.")

                cursor = self.conn.execute(
                    """
                    INSERT INTO justificacion_baja_documentos (
                        justificacion_id, version_id, document_type, generation_number,
                        file_name, relative_path, sha256, size_bytes, snapshot_sha256,
                        payload_sha256, template_version, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        justification_id,
                        version_id,
                        document_type,
                        resolved_generation,
                        file_name,
                        normalized_path,
                        normalized_file_hash,
                        size_bytes,
                        stored_snapshot_hash,
                        normalized_payload_hash,
                        template_version,
                        user_id,
                        timestamp,
                    ),
                )
                document_id = int(cursor.lastrowid)
                self.add_history(
                    justification_id,
                    version_id=version_id,
                    event_type=f"document_{document_type}",
                    message=f"Documento {document_type.upper()} generado.",
                    metadata={
                        "document_id": document_id,
                        "sha256": normalized_file_hash,
                        "file_name": file_name,
                        "generation_number": resolved_generation,
                    },
                    user_id=user_id,
                    timestamp=timestamp,
                )
        except sqlite3.IntegrityError as exc:
            raise JustificationConflictError(
                "Existe un conflicto de ruta, generación o hashes documentales."
            ) from exc
        return self.get_document(justification_id, document_id)

    def get_document(self, justification_id: int, document_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM justificacion_baja_documentos WHERE id = ? AND justificacion_id = ?",
            (document_id, justification_id),
        ).fetchone()
        if row is None:
            raise JustificationNotFoundError("No existe el documento solicitado.")
        return dict(row)

    def get_document_by_id(self, document_id: int) -> dict[str, Any]:
        """Resolve an opaque document id; callers never provide a filesystem path."""

        row = self.conn.execute(
            """
            SELECT d.*, v.version_number, l.id AS licitacion_id,
                   l.expediente AS licitacion_expediente,
                   l.ruta_carpeta AS licitacion_ruta_carpeta,
                   jb.cliente_id
            FROM justificacion_baja_documentos d
            JOIN justificacion_baja_versiones v
              ON v.id = d.version_id AND v.justificacion_id = d.justificacion_id
            JOIN justificaciones_baja jb ON jb.id = d.justificacion_id
            JOIN licitaciones l ON l.id = jb.licitacion_id
            WHERE d.id = ? AND jb.archived_at IS NULL
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            raise JustificationNotFoundError("No existe el documento solicitado.")
        return dict(row)

    def list_documents(self, justification_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.*, v.version_number
            FROM justificacion_baja_documentos d
            JOIN justificacion_baja_versiones v ON v.id = d.version_id
            WHERE d.justificacion_id = ?
            ORDER BY v.version_number DESC, d.created_at DESC, d.id DESC
            """,
            (justification_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def put_route_image(
        self,
        justification_id: int,
        *,
        content: bytes,
        mime_type: str,
        width_px: int,
        height_px: int,
        user_id: str,
        timestamp: str,
        expected_revision: int | None = None,
        file_name: str | None = None,
        original_name: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
    ) -> dict[str, Any]:
        """Store or replace the active route image without embedding it in draft JSON."""

        if not isinstance(content, bytes) or not content:
            raise ValueError("content debe contener bytes de imagen.")
        if mime_type not in {"image/png", "image/jpeg"}:
            raise ValueError("mime_type debe ser image/png o image/jpeg.")
        if int(width_px) < 1 or int(height_px) < 1:
            raise ValueError("Las dimensiones de la imagen deben ser positivas.")
        resolved_file_name = str(file_name or original_name or "").strip()
        if not resolved_file_name:
            raise ValueError("file_name es obligatorio.")
        calculated_hash = _sha256_bytes(content)
        if sha256 is not None and _validate_hash(sha256, label="sha256") != calculated_hash:
            raise ValueError("sha256 no coincide con los bytes de la imagen.")
        if size_bytes is not None and int(size_bytes) != len(content):
            raise ValueError("size_bytes no coincide con los bytes de la imagen.")

        try:
            with _savepoint(self.conn):
                owner = self.conn.execute(
                    """
                    SELECT revision, route_asset_id
                    FROM justificaciones_baja
                    WHERE id = ? AND archived_at IS NULL
                    """,
                    (justification_id,),
                ).fetchone()
                if owner is None:
                    raise JustificationNotFoundError("No existe la justificación solicitada.")
                resolved_revision = (
                    int(owner["revision"])
                    if expected_revision is None
                    else int(expected_revision)
                )
                if int(owner["revision"]) != resolved_revision:
                    raise JustificationConflictError(
                        "El borrador ha cambiado en otra pestaña. Recarga antes de guardar la ruta."
                    )
                replaced_asset_id = owner["route_asset_id"]
                if replaced_asset_id is not None:
                    current = self.conn.execute(
                        """
                        SELECT * FROM justificacion_baja_assets
                        WHERE id = ? AND justificacion_id = ?
                        """,
                        (replaced_asset_id, justification_id),
                    ).fetchone()
                    if (
                        current is not None
                        and str(current["sha256"]).upper() == calculated_hash
                        and current["mime_type"] == mime_type
                        and int(current["width_px"]) == int(width_px)
                        and int(current["height_px"]) == int(height_px)
                        and current["file_name"] == resolved_file_name
                    ):
                        return _asset_row(current, include_content=True)

                cursor = self.conn.execute(
                    """
                    INSERT INTO justificacion_baja_assets (
                        justificacion_id, asset_kind, file_name, mime_type,
                        width_px, height_px, sha256, size_bytes, content,
                        replaced_asset_id, created_by, created_at
                    ) VALUES (?, 'route_image', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        justification_id,
                        resolved_file_name,
                        mime_type,
                        int(width_px),
                        int(height_px),
                        calculated_hash,
                        len(content),
                        sqlite3.Binary(content),
                        replaced_asset_id,
                        user_id,
                        timestamp,
                    ),
                )
                asset_id = int(cursor.lastrowid)
                updated = self.conn.execute(
                    """
                    UPDATE justificaciones_baja
                    SET route_asset_id = ?, updated_by = ?, updated_at = ?
                    WHERE id = ? AND revision = ? AND archived_at IS NULL
                    """,
                    (asset_id, user_id, timestamp, justification_id, resolved_revision),
                )
                if updated.rowcount != 1:
                    raise JustificationConflictError(
                        "No se pudo guardar la imagen por un cambio concurrente."
                    )
                self.add_history(
                    justification_id,
                    event_type="route_image_replaced" if replaced_asset_id else "route_image_added",
                    message=(
                        "Imagen de ruta sustituida."
                        if replaced_asset_id
                        else "Imagen de ruta añadida."
                    ),
                    metadata={
                        "asset_id": asset_id,
                        "replaced_asset_id": replaced_asset_id,
                        "sha256": calculated_hash,
                        "mime_type": mime_type,
                        "width_px": int(width_px),
                        "height_px": int(height_px),
                    },
                    user_id=user_id,
                    timestamp=timestamp,
                )
        except sqlite3.IntegrityError as exc:
            raise JustificationConflictError(
                "No se pudo guardar la imagen por un conflicto de persistencia."
            ) from exc
        result = self.get_route_image(asset_id=asset_id)
        assert result is not None
        return result

    def get_route_image(
        self,
        justification_id: int | None = None,
        *,
        asset_id: int | None = None,
        include_content: bool | None = None,
    ) -> dict[str, Any] | None:
        """Return active metadata by justification, or full bytes by opaque asset id."""

        if justification_id is None and asset_id is None:
            raise ValueError("Indica justification_id o asset_id.")
        if asset_id is not None:
            if justification_id is None:
                row = self.conn.execute(
                    "SELECT * FROM justificacion_baja_assets WHERE id = ?",
                    (asset_id,),
                ).fetchone()
            else:
                row = self.conn.execute(
                    """
                    SELECT * FROM justificacion_baja_assets
                    WHERE id = ? AND justificacion_id = ?
                    """,
                    (asset_id, justification_id),
                ).fetchone()
            return None if row is None else _asset_row(row, include_content=True)
        if include_content:
            raise ValueError("Los bytes solo se recuperan mediante un asset_id opaco.")
        row = self.conn.execute(
            """
            SELECT a.*
            FROM justificaciones_baja jb
            LEFT JOIN justificacion_baja_assets a
              ON a.id = jb.route_asset_id AND a.justificacion_id = jb.id
            WHERE jb.id = ? AND jb.archived_at IS NULL
            """,
            (justification_id,),
        ).fetchone()
        if row is None or row["id"] is None:
            return None
        return _asset_row(row, include_content=False)

    def update_state(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        state: str,
        user_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        _validate_state(state)
        with _savepoint(self.conn):
            cursor = self.conn.execute(
                """
                UPDATE justificaciones_baja
                SET estado = ?, revision = revision + 1, updated_by = ?, updated_at = ?
                WHERE id = ? AND revision = ? AND archived_at IS NULL
                """,
                (state, user_id, timestamp, justification_id, expected_revision),
            )
            if cursor.rowcount != 1:
                if self.conn.execute(
                    "SELECT 1 FROM justificaciones_baja WHERE id = ? AND archived_at IS NULL",
                    (justification_id,),
                ).fetchone() is None:
                    raise JustificationNotFoundError("No existe la justificación solicitada.")
                raise JustificationConflictError(
                    "El registro ha cambiado en otra pestaña. Recarga antes de cambiar el estado."
                )
            self.add_history(
                justification_id,
                event_type="state_changed",
                message=f"Estado cambiado a {state}.",
                metadata={"state": state},
                user_id=user_id,
                timestamp=timestamp,
            )
        return self.get(justification_id)

    def add_history(
        self,
        justification_id: int,
        *,
        event_type: str,
        message: str,
        user_id: str,
        timestamp: str,
        metadata: Mapping[str, Any] | None = None,
        version_id: int | None = None,
    ) -> int:
        _validate_no_embedded_binary(metadata or {}, path="history.metadata")
        if version_id is not None:
            version = self.conn.execute(
                """
                SELECT 1 FROM justificacion_baja_versiones
                WHERE id = ? AND justificacion_id = ?
                """,
                (version_id, justification_id),
            ).fetchone()
            if version is None:
                raise JustificationNotFoundError(
                    "La versión no pertenece a la justificación indicada."
                )
        cursor = self.conn.execute(
            """
            INSERT INTO justificacion_baja_historial (
                justificacion_id, version_id, event_type, message,
                metadata_json, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                justification_id,
                version_id,
                event_type,
                message,
                canonical_json(dict(metadata or {})),
                user_id,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def list_history(self, justification_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM justificacion_baja_historial
            WHERE justificacion_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (justification_id,),
        ).fetchall()
        return [_history_row(row) for row in rows]


def _loads_json(value: object, *, fallback: object) -> Any:
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _justification_row(row: sqlite3.Row, *, include_draft: bool = True) -> dict[str, Any]:
    result = dict(row)
    if include_draft:
        result["draft"] = _loads_json(result.pop("draft_json", ""), fallback={})
    else:
        result.pop("draft_json", None)
    result["draft_frozen"] = bool(result.get("draft_frozen"))
    result["revision"] = int(result.get("revision") or 0)
    result["latest_version"] = int(result.get("latest_version") or 0)
    if "document_count" in result:
        result["document_count"] = int(result.get("document_count") or 0)
    return result


def _version_row(row: sqlite3.Row, *, include_payload: bool = True) -> dict[str, Any]:
    result = dict(row)
    if include_payload:
        result["document_context"] = _loads_json(
            result.pop("document_context_json", ""), fallback={}
        )
    else:
        result.pop("document_context_json", None)
        result.pop("snapshot_json", None)
    return result


def _history_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = _loads_json(result.pop("metadata_json", ""), fallback={})
    return result


def _asset_row(row: sqlite3.Row, *, include_content: bool) -> dict[str, Any]:
    result = dict(row)
    if include_content:
        content = result.get("content")
        if isinstance(content, memoryview):
            result["content"] = content.tobytes()
    else:
        result.pop("content", None)
    return result


__all__ = (
    "JustificationConflictError",
    "JustificationNotFoundError",
    "JustificationRepository",
    "canonical_json",
    "ensure_justificaciones_baja_schema",
)
