from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

try:
    from .dropbox_paths import DropboxPathError, path_inside_base, preferred_dropbox_base_path, resolve_path_inside_base
    from .folder_names import safe_folder_name
    from .normalization import clean_text
    from .outlook_drafts import DraftAttachment, DraftGenerationResult, generate_outlook_draft
    from .storage_paths import path_is_relative_to
except ImportError:
    from dropbox_paths import DropboxPathError, path_inside_base, preferred_dropbox_base_path, resolve_path_inside_base
    from folder_names import safe_folder_name
    from normalization import clean_text
    from outlook_drafts import DraftAttachment, DraftGenerationResult, generate_outlook_draft
    from storage_paths import path_is_relative_to


CLIENTE_ENVIO_ESTADOS = [
    {"value": "en_preparacion", "label": "En preparación"},
    {"value": "listo_para_preparar_correo", "label": "Listo para preparar correo"},
    {"value": "correo_outlook_generado", "label": "Correo Outlook generado"},
    {"value": "enviado", "label": "Enviado"},
    {"value": "incidencia", "label": "Incidencia / Error"},
    {"value": "cancelado", "label": "Cancelado / No procede"},
]

CLIENTE_ENVIO_TIPOS = [
    {"value": "ficha_inicial", "label": "Ficha inicial / resumen de licitación"},
    {"value": "plantilla_oferta", "label": "Plantilla de oferta"},
    {"value": "documentacion_revision", "label": "Documentación para revisión"},
    {"value": "documentacion_firma", "label": "Documentación para firma"},
    {"value": "requerimiento", "label": "Requerimiento"},
    {"value": "subsanacion", "label": "Subsanación"},
    {"value": "aclaracion", "label": "Aclaración"},
    {"value": "documentacion_adicional", "label": "Documentación adicional"},
    {"value": "contrato_encargo", "label": "Contrato / encargo"},
    {"value": "recordatorio", "label": "Recordatorio"},
    {"value": "otro", "label": "Otro"},
]

CLIENTE_ENVIO_ESTADO_LABELS = {item["value"]: item["label"] for item in CLIENTE_ENVIO_ESTADOS}
CLIENTE_ENVIO_TIPO_LABELS = {item["value"]: item["label"] for item in CLIENTE_ENVIO_TIPOS}
CLIENTE_ENVIO_PENDIENTES_AGENDA = {
    "listo_para_preparar_correo",
    "correo_outlook_generado",
    "incidencia",
}
CLIENTE_ENVIO_PANEL_TITLES = {
    "regular": "Tareas y actuaciones pendientes",
    "ready": "Envíos listos para preparar correo",
    "generated": "Correos Outlook generados pendientes de marcar como enviados",
    "incidents": "Envíos con incidencia",
}

CORREOS_PREPARADOS_FOLDER = "Correos preparados"
TEMPORARY_FILE_PREFIXES = ("~$",)
EXCLUDED_ATTACHMENT_FOLDER_NAMES = {CORREOS_PREPARADOS_FOLDER.lower()}
ATTACHMENT_WARNING_BYTES = 20 * 1024 * 1024
ATTACHMENT_HARD_LIMIT_BYTES = 35 * 1024 * 1024

CLIENT_FIELDS = (
    "razon_social",
    "nombre_comercial",
    "nif_cif",
    "domicilio_fiscal",
    "codigo_postal",
    "municipio",
    "provincia",
    "pais",
    "telefono_principal",
    "email_principal",
    "email_alternativo",
    "persona_contacto_operativa",
    "observaciones_internas",
    "representante_nombre",
    "representante_nif",
    "representante_cargo",
    "representante_email",
    "representante_telefono",
    "condiciones_particulares",
    "tipo_cliente",
    "forma_facturacion",
    "plantilla_contractual",
)


CLIENT_COLUMN_DEFINITIONS = {
    "razon_social": "TEXT NOT NULL DEFAULT ''",
    "nombre_comercial": "TEXT",
    "nif_cif": "TEXT",
    "domicilio_fiscal": "TEXT",
    "codigo_postal": "TEXT",
    "municipio": "TEXT",
    "provincia": "TEXT",
    "pais": "TEXT",
    "telefono_principal": "TEXT",
    "email_principal": "TEXT",
    "email_alternativo": "TEXT",
    "persona_contacto_operativa": "TEXT",
    "observaciones_internas": "TEXT",
    "representante_nombre": "TEXT",
    "representante_nif": "TEXT",
    "representante_cargo": "TEXT",
    "representante_email": "TEXT",
    "representante_telefono": "TEXT",
    "condiciones_particulares": "TEXT",
    "tipo_cliente": "TEXT",
    "forma_facturacion": "TEXT",
    "plantilla_contractual": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}

CLIENTE_ENVIO_COLUMN_DEFINITIONS = {
    "cliente_id": "INTEGER NOT NULL DEFAULT 0",
    "licitacion_id": "INTEGER NOT NULL DEFAULT 0",
    "actuacion_id": "INTEGER",
    "tipo_envio": "TEXT NOT NULL DEFAULT 'otro'",
    "estado": "TEXT NOT NULL DEFAULT 'en_preparacion'",
    "carpeta_dropbox": "TEXT NOT NULL DEFAULT ''",
    "destinatario_email": "TEXT",
    "asunto": "TEXT",
    "cuerpo": "TEXT",
    "observaciones_internas": "TEXT",
    "correo_generado_path": "TEXT",
    "correo_generado_formato": "TEXT",
    "correo_generado_warning": "TEXT",
    "correo_generado_at": "TEXT",
    "correo_generado_by": "TEXT",
    "enviado_at": "TEXT",
    "enviado_by": "TEXT",
    "incidencia_detalle": "TEXT",
    "attachments_size_total": "INTEGER NOT NULL DEFAULT 0",
    "created_by": "TEXT NOT NULL DEFAULT ''",
    "updated_by": "TEXT NOT NULL DEFAULT ''",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}

CLIENTE_ENVIO_ADJUNTO_COLUMN_DEFINITIONS = {
    "envio_id": "INTEGER NOT NULL DEFAULT 0",
    "relative_path": "TEXT NOT NULL DEFAULT ''",
    "absolute_path": "TEXT NOT NULL DEFAULT ''",
    "file_name": "TEXT NOT NULL DEFAULT ''",
    "size_bytes": "INTEGER NOT NULL DEFAULT 0",
    "content_type": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}

CLIENTE_ENVIO_EVENTO_COLUMN_DEFINITIONS = {
    "envio_id": "INTEGER NOT NULL DEFAULT 0",
    "event_type": "TEXT NOT NULL DEFAULT ''",
    "old_value": "TEXT",
    "new_value": "TEXT",
    "user_id": "TEXT",
    "message": "TEXT",
    "metadata_json": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_columns(conn: sqlite3.Connection, table: str, definitions: dict[str, str]) -> None:
    columns = _column_names(conn, table)
    for column, definition in definitions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            columns.add(column)


def ensure_client_shipments_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL,
            nombre_comercial TEXT,
            nif_cif TEXT,
            domicilio_fiscal TEXT,
            codigo_postal TEXT,
            municipio TEXT,
            provincia TEXT,
            pais TEXT,
            telefono_principal TEXT,
            email_principal TEXT,
            email_alternativo TEXT,
            persona_contacto_operativa TEXT,
            observaciones_internas TEXT,
            representante_nombre TEXT,
            representante_nif TEXT,
            representante_cargo TEXT,
            representante_email TEXT,
            representante_telefono TEXT,
            condiciones_particulares TEXT,
            tipo_cliente TEXT,
            forma_facturacion TEXT,
            plantilla_contractual TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cliente_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            licitacion_id INTEGER NOT NULL,
            actuacion_id INTEGER,
            tipo_envio TEXT NOT NULL,
            estado TEXT NOT NULL,
            carpeta_dropbox TEXT NOT NULL,
            destinatario_email TEXT,
            asunto TEXT,
            cuerpo TEXT,
            observaciones_internas TEXT,
            correo_generado_path TEXT,
            correo_generado_formato TEXT,
            correo_generado_warning TEXT,
            correo_generado_at TEXT,
            correo_generado_by TEXT,
            enviado_at TEXT,
            enviado_by TEXT,
            incidencia_detalle TEXT,
            attachments_size_total INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (actuacion_id) REFERENCES actuaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cliente_envio_adjuntos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            envio_id INTEGER NOT NULL,
            relative_path TEXT NOT NULL,
            absolute_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            content_type TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (envio_id) REFERENCES cliente_envios(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cliente_envio_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            envio_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            user_id TEXT,
            message TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (envio_id) REFERENCES cliente_envios(id) ON DELETE CASCADE
        )
        """
    )
    _ensure_columns(conn, "clientes", CLIENT_COLUMN_DEFINITIONS)
    _ensure_columns(conn, "cliente_envios", CLIENTE_ENVIO_COLUMN_DEFINITIONS)
    _ensure_columns(conn, "cliente_envio_adjuntos", CLIENTE_ENVIO_ADJUNTO_COLUMN_DEFINITIONS)
    _ensure_columns(conn, "cliente_envio_eventos", CLIENTE_ENVIO_EVENTO_COLUMN_DEFINITIONS)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(razon_social, nombre_comercial)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nif ON clientes(nif_cif)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envios_cliente ON cliente_envios(cliente_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envios_licitacion ON cliente_envios(licitacion_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envios_actuacion ON cliente_envios(actuacion_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envios_estado ON cliente_envios(estado, updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envio_adjuntos_envio ON cliente_envio_adjuntos(envio_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cliente_envio_eventos_envio ON cliente_envio_eventos(envio_id, created_at DESC)")


def _row_value(row: sqlite3.Row | dict[str, object], key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return ""


def _normalize_slug(value: object, *, allowed: set[str], default: str) -> str:
    text = clean_text(value).lower().replace("-", "_").replace("/", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    return text if text in allowed else default


def normalize_cliente_envio_state(value: object, *, default: str = "en_preparacion") -> str:
    allowed = set(CLIENTE_ENVIO_ESTADO_LABELS.keys())
    mapping = {
        "listo": "listo_para_preparar_correo",
        "listo_para_preparar": "listo_para_preparar_correo",
        "correo_generado": "correo_outlook_generado",
        "correo_preparado": "correo_outlook_generado",
        "incidencia_error": "incidencia",
        "cancelado_no_procede": "cancelado",
    }
    normalized = _normalize_slug(value, allowed=allowed | set(mapping.keys()), default=default)
    return mapping.get(normalized, normalized)


def normalize_cliente_envio_type(value: object, *, default: str = "otro") -> str:
    allowed = set(CLIENTE_ENVIO_TIPO_LABELS.keys())
    return _normalize_slug(value, allowed=allowed, default=default)


def cliente_envio_state_label(value: object) -> str:
    return CLIENTE_ENVIO_ESTADO_LABELS.get(normalize_cliente_envio_state(value), CLIENTE_ENVIO_ESTADO_LABELS["en_preparacion"])


def cliente_envio_type_label(value: object) -> str:
    return CLIENTE_ENVIO_TIPO_LABELS.get(normalize_cliente_envio_type(value), CLIENTE_ENVIO_TIPO_LABELS["otro"])


def cliente_display_name(row: sqlite3.Row | dict[str, object]) -> str:
    return clean_text(_row_value(row, "nombre_comercial")) or clean_text(_row_value(row, "razon_social")) or "Cliente sin nombre"


def cliente_row_to_dict(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
    return {
        "id": int(_row_value(row, "id") or 0),
        **{field: clean_text(_row_value(row, field)) for field in CLIENT_FIELDS},
        "display_name": cliente_display_name(row),
        "created_at": clean_text(_row_value(row, "created_at")),
        "updated_at": clean_text(_row_value(row, "updated_at")),
    }


def _event_rows(conn: sqlite3.Connection, envio_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, event_type, old_value, new_value, user_id, message, metadata_json, created_at
        FROM cliente_envio_eventos
        WHERE envio_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (envio_id,),
    ).fetchall()
    items: list[dict[str, object]] = []
    for row in rows:
        metadata = clean_text(row["metadata_json"])
        items.append(
            {
                "id": int(row["id"]),
                "event_type": row["event_type"] or "",
                "old_value": row["old_value"] or "",
                "new_value": row["new_value"] or "",
                "user_id": row["user_id"] or "",
                "message": row["message"] or "",
                "metadata": json.loads(metadata) if metadata else {},
                "created_at": row["created_at"] or "",
            }
        )
    return items


def _attachment_rows(conn: sqlite3.Connection, envio_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, relative_path, absolute_path, file_name, size_bytes, content_type, created_at
        FROM cliente_envio_adjuntos
        WHERE envio_id = ?
        ORDER BY lower(relative_path), id ASC
        """,
        (envio_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "relative_path": row["relative_path"] or "",
            "absolute_path": row["absolute_path"] or "",
            "file_name": row["file_name"] or "",
            "size_bytes": int(row["size_bytes"] or 0),
            "content_type": row["content_type"] or "",
            "created_at": row["created_at"] or "",
        }
        for row in rows
    ]


def _envio_join_sql(where_sql: str = "") -> str:
    sql = """
        SELECT
            e.*,
            c.razon_social AS cliente_razon_social,
            c.nombre_comercial AS cliente_nombre_comercial,
            c.email_principal AS cliente_email_principal,
            l.expediente AS licitacion_expediente,
            l.objeto AS licitacion_objeto,
            l.organismo AS licitacion_organismo,
            l.enlace_perfil AS licitacion_enlace_perfil,
            l.fecha_limite AS licitacion_fecha_limite,
            l.hora_limite AS licitacion_hora_limite,
            a.titulo AS actuacion_titulo,
            (
                SELECT COUNT(*) FROM cliente_envio_adjuntos adj
                WHERE adj.envio_id = e.id
            ) AS attachment_count
        FROM cliente_envios e
        JOIN clientes c ON c.id = e.cliente_id
        JOIN licitaciones l ON l.id = e.licitacion_id
        LEFT JOIN actuaciones a ON a.id = e.actuacion_id
    """
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY e.updated_at DESC, e.id DESC"
    return sql


def cliente_envio_row_to_dict(
    row: sqlite3.Row | dict[str, object],
    *,
    attachments: list[dict[str, object]] | None = None,
    events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    cliente_nombre = clean_text(_row_value(row, "cliente_nombre_comercial")) or clean_text(_row_value(row, "cliente_razon_social"))
    tipo_envio = normalize_cliente_envio_type(_row_value(row, "tipo_envio"))
    estado = normalize_cliente_envio_state(_row_value(row, "estado"))
    folder = clean_text(_row_value(row, "carpeta_dropbox"))
    return {
        "id": int(_row_value(row, "id") or 0),
        "cliente_id": int(_row_value(row, "cliente_id") or 0),
        "cliente_nombre": cliente_nombre or "Cliente sin nombre",
        "licitacion_id": int(_row_value(row, "licitacion_id") or 0),
        "licitacion_expediente": clean_text(_row_value(row, "licitacion_expediente")),
        "licitacion_objeto": clean_text(_row_value(row, "licitacion_objeto")),
        "licitacion_organismo": clean_text(_row_value(row, "licitacion_organismo")),
        "licitacion_enlace_perfil": clean_text(_row_value(row, "licitacion_enlace_perfil")),
        "actuacion_id": int(_row_value(row, "actuacion_id") or 0) or None,
        "actuacion_titulo": clean_text(_row_value(row, "actuacion_titulo")),
        "tipo_envio": tipo_envio,
        "tipo_envio_label": cliente_envio_type_label(tipo_envio),
        "estado": estado,
        "estado_label": cliente_envio_state_label(estado),
        "carpeta_dropbox": folder,
        "destinatario_email": clean_text(_row_value(row, "destinatario_email")),
        "asunto": clean_text(_row_value(row, "asunto")),
        "cuerpo": clean_text(_row_value(row, "cuerpo")),
        "observaciones_internas": clean_text(_row_value(row, "observaciones_internas")),
        "correo_generado_path": clean_text(_row_value(row, "correo_generado_path")),
        "correo_generado_formato": clean_text(_row_value(row, "correo_generado_formato")),
        "correo_generado_warning": clean_text(_row_value(row, "correo_generado_warning")),
        "correo_generado_at": clean_text(_row_value(row, "correo_generado_at")),
        "correo_generado_by": clean_text(_row_value(row, "correo_generado_by")),
        "enviado_at": clean_text(_row_value(row, "enviado_at")),
        "enviado_by": clean_text(_row_value(row, "enviado_by")),
        "incidencia_detalle": clean_text(_row_value(row, "incidencia_detalle")),
        "attachments_size_total": int(_row_value(row, "attachments_size_total") or 0),
        "attachment_count": int(_row_value(row, "attachment_count") or (len(attachments or []))),
        "created_by": clean_text(_row_value(row, "created_by")),
        "updated_by": clean_text(_row_value(row, "updated_by")),
        "created_at": clean_text(_row_value(row, "created_at")),
        "updated_at": clean_text(_row_value(row, "updated_at")),
        "attachments": attachments or [],
        "events": events or [],
    }


def _client_payload(data: dict[str, object]) -> dict[str, object]:
    payload = {field: clean_text(data.get(field)) for field in CLIENT_FIELDS}
    payload["razon_social"] = clean_text(data.get("razon_social"))
    if not payload["razon_social"]:
        raise ValueError("La razon social es obligatoria.")
    if not payload["pais"]:
        payload["pais"] = "España"
    return payload


def _shipment_state_options() -> list[dict[str, str]]:
    return [dict(item) for item in CLIENTE_ENVIO_ESTADOS]


def _shipment_type_options() -> list[dict[str, str]]:
    return [dict(item) for item in CLIENTE_ENVIO_TIPOS]


def _require_existing_row(conn: sqlite3.Connection, table: str, row_id: int) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not row:
        raise ValueError(f"No existe el registro solicitado en {table}.")
    return row


def _validate_linked_actuacion(conn: sqlite3.Connection, actuacion_id: int, licitacion_id: int) -> None:
    exists = conn.execute(
        """
        SELECT 1
        FROM actuacion_licitaciones
        WHERE actuacion_id = ? AND licitacion_id = ?
        """,
        (actuacion_id, licitacion_id),
    ).fetchone()
    if not exists:
        raise ValueError("La actuacion seleccionada no esta vinculada a la licitacion indicada.")


def _dropbox_base_path() -> Path:
    base = preferred_dropbox_base_path()
    if base is None:
        raise DropboxPathError("Carpeta Dropbox no configurada.")
    resolved = Path(base).resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise DropboxPathError("La carpeta base de Dropbox no existe o no es valida.")
    return resolved


def resolve_envio_dropbox_folder(value: object, *, dropbox_base: Path | None = None) -> Path:
    base = (dropbox_base or _dropbox_base_path()).resolve(strict=False)
    text = clean_text(value).strip('"')
    if not text:
        raise DropboxPathError("La carpeta Dropbox es obligatoria.")
    path = Path(text)
    if path.is_absolute() or (len(text) >= 2 and text[1] == ":"):
        resolved = path.resolve(strict=False)
        if not path_inside_base(resolved, base):
            raise DropboxPathError("La carpeta debe quedar dentro de la base permitida de Dropbox.")
    else:
        resolved = resolve_path_inside_base(base, text)
    if resolved.is_symlink():
        raise DropboxPathError("No se permiten enlaces simbolicos como carpeta de envio.")
    if not resolved.exists() or not resolved.is_dir():
        raise DropboxPathError("La carpeta indicada no existe.")
    return resolved


def _dropbox_storage_value(folder: Path, *, dropbox_base: Path) -> str:
    return str(folder.resolve(strict=False).relative_to(dropbox_base.resolve(strict=False)))


def _is_excluded_attachment(relative_path: Path, file_path: Path) -> bool:
    if not file_path.name or any(file_path.name.startswith(prefix) for prefix in TEMPORARY_FILE_PREFIXES):
        return True
    if relative_path.parts and relative_path.parts[0].lower() in EXCLUDED_ATTACHMENT_FOLDER_NAMES:
        return True
    return False


def list_dropbox_folder_files(value: object, *, dropbox_base: Path | None = None) -> dict[str, object]:
    base = dropbox_base or _dropbox_base_path()
    folder = resolve_envio_dropbox_folder(value, dropbox_base=base)
    folder_resolved = folder.resolve(strict=False)
    files: list[dict[str, object]] = []
    for candidate in sorted(folder.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            resolved = candidate.resolve(strict=False)
            relative_path = resolved.relative_to(folder_resolved)
            stat = resolved.stat()
        except (OSError, ValueError):
            continue
        if not path_is_relative_to(resolved, folder_resolved):
            continue
        if stat.st_size <= 0 or _is_excluded_attachment(relative_path, resolved):
            continue
        files.append(
            {
                "name": resolved.name,
                "relative_path": str(relative_path),
                "absolute_path": str(resolved),
                "size_bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat(),
            }
        )
    return {
        "folder_path": str(folder_resolved),
        "folder_storage_path": _dropbox_storage_value(folder_resolved, dropbox_base=base),
        "files": files,
        "total_files": len(files),
    }


def _attachment_lookup(folder_payload: dict[str, object]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for item in folder_payload.get("files") or []:
        relative = clean_text(item.get("relative_path"))
        if relative:
            lookup[relative.replace("/", "\\")] = item
            lookup[relative.replace("\\", "/")] = item
    return lookup


def validate_selected_attachments(
    folder_value: object,
    selected_relative_paths: Sequence[object],
    *,
    dropbox_base: Path | None = None,
) -> tuple[dict[str, object], list[dict[str, object]], list[str]]:
    folder_payload = list_dropbox_folder_files(folder_value, dropbox_base=dropbox_base)
    lookup = _attachment_lookup(folder_payload)
    selected: list[dict[str, object]] = []
    warnings: list[str] = []
    if not selected_relative_paths:
        raise ValueError("Selecciona al menos un archivo adjunto.")
    seen: set[str] = set()
    total_size = 0
    for raw_relative in selected_relative_paths:
        relative = clean_text(raw_relative).replace("/", "\\")
        if not relative or relative in seen:
            continue
        item = lookup.get(relative)
        if not item:
            raise ValueError("Todos los adjuntos deben pertenecer a la carpeta asignada al envio.")
        seen.add(relative)
        total_size += int(item.get("size_bytes") or 0)
        selected.append(item)
    if not selected:
        raise ValueError("Selecciona al menos un archivo valido.")
    if total_size > ATTACHMENT_HARD_LIMIT_BYTES:
        raise ValueError("El tamano total de adjuntos supera el limite permitido.")
    if total_size > ATTACHMENT_WARNING_BYTES:
        warnings.append("El tamano total de adjuntos supera el umbral recomendado para email.")
    folder_payload["selected_files"] = selected
    folder_payload["selected_total_size"] = total_size
    return folder_payload, selected, warnings


def _template_intro(tipo_envio: str) -> str:
    mapping = {
        "ficha_inicial": "Les remitimos adjunta la documentacion relativa a la licitacion indicada para su revision.",
        "plantilla_oferta": "Les remitimos adjunta la plantilla de oferta preparada para su revision.",
        "documentacion_revision": "Les remitimos adjunta la documentacion preparada para su revision.",
        "documentacion_firma": "Les remitimos adjunta la documentacion preparada para su firma.",
        "requerimiento": "Les remitimos la documentacion relativa al requerimiento recibido en el expediente indicado.",
        "subsanacion": "Les remitimos la documentacion necesaria para atender la subsanacion correspondiente al expediente indicado.",
        "aclaracion": "Les remitimos la documentacion relacionada con la aclaracion del expediente indicado.",
        "documentacion_adicional": "Les remitimos la documentacion adicional correspondiente al expediente indicado.",
        "contrato_encargo": "Les remitimos la documentacion contractual preparada para su revision.",
        "recordatorio": "Les remitimos un recordatorio con la documentacion del expediente indicado.",
    }
    return mapping.get(tipo_envio, "Les remitimos la documentacion adjunta correspondiente al expediente indicado.")


def build_cliente_envio_email_suggestion(row: sqlite3.Row | dict[str, object]) -> dict[str, str]:
    tipo_envio = normalize_cliente_envio_type(_row_value(row, "tipo_envio"))
    cliente = clean_text(_row_value(row, "cliente_nombre_comercial")) or clean_text(_row_value(row, "cliente_razon_social"))
    expediente = clean_text(_row_value(row, "licitacion_expediente"))
    objeto = clean_text(_row_value(row, "licitacion_objeto"))
    actuacion = clean_text(_row_value(row, "actuacion_titulo"))
    destinatario = clean_text(_row_value(row, "destinatario_email")) or clean_text(_row_value(row, "cliente_email_principal"))
    tipo_label = cliente_envio_type_label(tipo_envio)
    asunto_pieces = [tipo_label]
    if expediente:
        asunto_pieces.append(expediente)
    if cliente:
        asunto_pieces.append(cliente)
    asunto = " - ".join(piece for piece in asunto_pieces if piece)
    lines = [
        "Buenos dias,",
        "",
        _template_intro(tipo_envio),
        "",
    ]
    if expediente:
        lines.append(f"Expediente: {expediente}")
    if objeto:
        lines.append(f"Asunto licitacion: {objeto}")
    if actuacion:
        lines.append(f"Actuacion asociada: {actuacion}")
    lines.extend(["", "Quedamos pendientes de sus comentarios.", "", "Un saludo."])
    return {
        "to": destinatario,
        "subject": asunto,
        "body": "\n".join(lines).strip(),
    }


def _safe_email_filename(row: sqlite3.Row | dict[str, object], *, timestamp: str) -> str:
    date_text = clean_text(timestamp)[:10] or datetime.now().date().isoformat()
    tipo = safe_folder_name(cliente_envio_type_label(_row_value(row, "tipo_envio")))
    cliente = safe_folder_name(
        clean_text(_row_value(row, "cliente_nombre_comercial"))
        or clean_text(_row_value(row, "cliente_razon_social"))
        or "Cliente"
    )
    expediente = safe_folder_name(clean_text(_row_value(row, "licitacion_expediente")) or f"ENVIO-{_row_value(row, 'id')}")
    return f"{date_text} - {tipo} - {cliente} - {expediente}"


def _allowed_transition(current_state: str, new_state: str) -> bool:
    if current_state == new_state:
        return True
    transitions = {
        "en_preparacion": {"listo_para_preparar_correo", "incidencia", "cancelado"},
        "listo_para_preparar_correo": {"en_preparacion", "correo_outlook_generado", "incidencia", "cancelado"},
        "correo_outlook_generado": {"listo_para_preparar_correo", "enviado", "incidencia", "cancelado"},
        "incidencia": {"en_preparacion", "listo_para_preparar_correo", "correo_outlook_generado", "cancelado"},
        "cancelado": {"en_preparacion", "listo_para_preparar_correo"},
        "enviado": set(),
    }
    return new_state in transitions.get(current_state, set())


def _record_envio_event(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    event_type: str,
    user_id: object,
    timestamp: str,
    message: object = "",
    old_value: object = "",
    new_value: object = "",
    metadata: dict[str, object] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO cliente_envio_eventos (
            envio_id, event_type, old_value, new_value, user_id, message, metadata_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            envio_id,
            clean_text(event_type),
            clean_text(old_value),
            clean_text(new_value),
            clean_text(user_id),
            clean_text(message),
            json.dumps(metadata or {}, ensure_ascii=True),
            timestamp,
        ),
    )


def create_cliente(conn: sqlite3.Connection, data: dict[str, object], *, user_id: object, timestamp: str) -> dict[str, object]:
    payload = _client_payload(data)
    payload["created_at"] = timestamp
    payload["updated_at"] = timestamp
    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    cur = conn.execute(
        f"INSERT INTO clientes ({columns}) VALUES ({placeholders})",
        list(payload.values()),
    )
    row = conn.execute("SELECT * FROM clientes WHERE id = ?", (int(cur.lastrowid),)).fetchone()
    return cliente_row_to_dict(row)


def update_cliente(conn: sqlite3.Connection, cliente_id: int, data: dict[str, object], *, user_id: object, timestamp: str) -> dict[str, object]:
    row = _require_existing_row(conn, "clientes", cliente_id)
    payload = _client_payload({**cliente_row_to_dict(row), **data})
    payload["updated_at"] = timestamp
    assignments = ", ".join(f"{key} = ?" for key in payload)
    conn.execute(
        f"UPDATE clientes SET {assignments} WHERE id = ?",
        [*payload.values(), cliente_id],
    )
    updated = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    return cliente_row_to_dict(updated)


def list_clientes(conn: sqlite3.Connection, *, search: str = "") -> list[dict[str, object]]:
    where = ""
    params: list[object] = []
    q = clean_text(search)
    if q:
        like = f"%{q}%"
        where = """
            WHERE razon_social LIKE ? OR nombre_comercial LIKE ? OR nif_cif LIKE ?
               OR email_principal LIKE ? OR persona_contacto_operativa LIKE ?
        """
        params.extend([like, like, like, like, like])
    rows = conn.execute(
        f"""
        SELECT * FROM clientes
        {where}
        ORDER BY lower(COALESCE(nombre_comercial, razon_social)), id ASC
        """,
        params,
    ).fetchall()
    return [cliente_row_to_dict(row) for row in rows]


def get_cliente(conn: sqlite3.Connection, cliente_id: int) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    if not row:
        return None
    payload = cliente_row_to_dict(row)
    payload["envios"] = list_cliente_envios(conn, cliente_id=cliente_id)
    return payload


def _create_envio_attachment_rows(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    items: Sequence[dict[str, object]],
    timestamp: str,
) -> None:
    conn.execute("DELETE FROM cliente_envio_adjuntos WHERE envio_id = ?", (envio_id,))
    for item in items:
        conn.execute(
            """
            INSERT INTO cliente_envio_adjuntos (
                envio_id, relative_path, absolute_path, file_name, size_bytes, content_type, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                envio_id,
                clean_text(item.get("relative_path")),
                clean_text(item.get("absolute_path")),
                clean_text(item.get("name")) or clean_text(item.get("file_name")),
                int(item.get("size_bytes") or 0),
                "",
                timestamp,
            ),
        )


def _shipment_payload(
    conn: sqlite3.Connection,
    data: dict[str, object],
    *,
    default_licitacion_id: int | None = None,
    default_actuacion_id: int | None = None,
    current_row: sqlite3.Row | None = None,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], list[str]]:
    cliente_id = int(data.get("cliente_id") or (current_row["cliente_id"] if current_row else 0) or 0)
    licitacion_id = int(data.get("licitacion_id") or default_licitacion_id or (current_row["licitacion_id"] if current_row else 0) or 0)
    actuacion_value = data.get("actuacion_id", default_actuacion_id if default_actuacion_id is not None else (current_row["actuacion_id"] if current_row else 0))
    actuacion_id = int(actuacion_value or 0) or None
    if cliente_id <= 0:
        raise ValueError("Selecciona un cliente valido.")
    if licitacion_id <= 0:
        raise ValueError("Selecciona una licitacion valida.")
    _require_existing_row(conn, "clientes", cliente_id)
    _require_existing_row(conn, "licitaciones", licitacion_id)
    if actuacion_id is not None:
        _require_existing_row(conn, "actuaciones", actuacion_id)
        _validate_linked_actuacion(conn, actuacion_id, licitacion_id)
    tipo_envio = normalize_cliente_envio_type(data.get("tipo_envio"), default=normalize_cliente_envio_type(current_row["tipo_envio"]) if current_row else "otro")
    estado = normalize_cliente_envio_state(data.get("estado"), default=normalize_cliente_envio_state(current_row["estado"]) if current_row else "en_preparacion")
    folder_value = data.get("carpeta_dropbox", current_row["carpeta_dropbox"] if current_row else "")
    dropbox_base = _dropbox_base_path()
    folder_payload, selected_files, warnings = validate_selected_attachments(
        folder_value,
        data.get("adjuntos") or [],
        dropbox_base=dropbox_base,
    )
    payload = {
        "cliente_id": cliente_id,
        "licitacion_id": licitacion_id,
        "actuacion_id": actuacion_id,
        "tipo_envio": tipo_envio,
        "estado": estado,
        "carpeta_dropbox": clean_text(folder_payload.get("folder_storage_path")),
        "destinatario_email": clean_text(data.get("destinatario_email")),
        "asunto": clean_text(data.get("asunto")),
        "cuerpo": clean_text(data.get("cuerpo")),
        "observaciones_internas": clean_text(data.get("observaciones_internas")),
        "attachments_size_total": int(folder_payload.get("selected_total_size") or 0),
    }
    return payload, folder_payload, selected_files, warnings


def create_cliente_envio(
    conn: sqlite3.Connection,
    data: dict[str, object],
    *,
    user_id: object,
    timestamp: str,
    default_licitacion_id: int | None = None,
    default_actuacion_id: int | None = None,
) -> dict[str, object]:
    payload, folder_payload, selected_files, warnings = _shipment_payload(
        conn,
        data,
        default_licitacion_id=default_licitacion_id,
        default_actuacion_id=default_actuacion_id,
    )
    payload["created_by"] = clean_text(user_id)
    payload["updated_by"] = clean_text(user_id)
    payload["created_at"] = timestamp
    payload["updated_at"] = timestamp
    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    cur = conn.execute(
        f"INSERT INTO cliente_envios ({columns}) VALUES ({placeholders})",
        list(payload.values()),
    )
    envio_id = int(cur.lastrowid)
    suggestion_row = conn.execute(
        _envio_join_sql("e.id = ?"),
        (envio_id,),
    ).fetchone()
    suggestion = build_cliente_envio_email_suggestion(suggestion_row)
    conn.execute(
        """
        UPDATE cliente_envios
        SET destinatario_email = ?, asunto = ?, cuerpo = ?
        WHERE id = ?
        """,
        (
            payload["destinatario_email"] or suggestion["to"],
            payload["asunto"] or suggestion["subject"],
            payload["cuerpo"] or suggestion["body"],
            envio_id,
        ),
    )
    _create_envio_attachment_rows(conn, envio_id, items=selected_files, timestamp=timestamp)
    _record_envio_event(
        conn,
        envio_id,
        event_type="creacion",
        user_id=user_id,
        timestamp=timestamp,
        message="Envio a cliente creado.",
        metadata={
            "warnings": warnings,
            "folder_path": folder_payload.get("folder_path"),
            "selected_count": len(selected_files),
        },
    )
    return get_cliente_envio(conn, envio_id, include_available_files=True) or {}


def update_cliente_envio(
    conn: sqlite3.Connection,
    envio_id: int,
    data: dict[str, object],
    *,
    user_id: object,
    timestamp: str,
) -> dict[str, object]:
    row = _require_existing_row(conn, "cliente_envios", envio_id)
    payload, folder_payload, selected_files, warnings = _shipment_payload(conn, data, current_row=row)
    current_state = normalize_cliente_envio_state(row["estado"])
    if not _allowed_transition(current_state, payload["estado"]):
        raise ValueError("La transicion de estado no esta permitida para este envio.")
    payload["updated_by"] = clean_text(user_id)
    payload["updated_at"] = timestamp
    assignments = ", ".join(f"{key} = ?" for key in payload)
    conn.execute(
        f"UPDATE cliente_envios SET {assignments} WHERE id = ?",
        [*payload.values(), envio_id],
    )
    _create_envio_attachment_rows(conn, envio_id, items=selected_files, timestamp=timestamp)
    _record_envio_event(
        conn,
        envio_id,
        event_type="actualizacion",
        user_id=user_id,
        timestamp=timestamp,
        old_value=current_state,
        new_value=payload["estado"],
        message="Envio actualizado.",
        metadata={
            "warnings": warnings,
            "folder_path": folder_payload.get("folder_path"),
            "selected_count": len(selected_files),
        },
    )
    return get_cliente_envio(conn, envio_id, include_available_files=True) or {}


def list_cliente_envios(
    conn: sqlite3.Connection,
    *,
    cliente_id: int | None = None,
    licitacion_id: int | None = None,
    actuacion_id: int | None = None,
    state: str = "",
    search: str = "",
) -> list[dict[str, object]]:
    where: list[str] = []
    params: list[object] = []
    if cliente_id:
        where.append("e.cliente_id = ?")
        params.append(cliente_id)
    if licitacion_id:
        where.append("e.licitacion_id = ?")
        params.append(licitacion_id)
    if actuacion_id:
        where.append("e.actuacion_id = ?")
        params.append(actuacion_id)
    if clean_text(state):
        where.append("e.estado = ?")
        params.append(normalize_cliente_envio_state(state, default=""))
    q = clean_text(search)
    if q:
        like = f"%{q}%"
        where.append(
            """
            (
                c.razon_social LIKE ? OR c.nombre_comercial LIKE ? OR c.nif_cif LIKE ?
                OR e.destinatario_email LIKE ? OR e.asunto LIKE ? OR e.cuerpo LIKE ?
                OR l.expediente LIKE ? OR l.objeto LIKE ? OR l.organismo LIKE ?
                OR COALESCE(a.titulo, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like, like])
    rows = conn.execute(_envio_join_sql(" AND ".join(where)), params).fetchall()
    return [cliente_envio_row_to_dict(row) for row in rows]


def get_cliente_envio(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    include_available_files: bool = False,
) -> dict[str, object] | None:
    row = conn.execute(_envio_join_sql("e.id = ?"), (envio_id,)).fetchone()
    if not row:
        return None
    attachments = _attachment_rows(conn, envio_id)
    events = _event_rows(conn, envio_id)
    payload = cliente_envio_row_to_dict(row, attachments=attachments, events=events)
    payload["state_options"] = _shipment_state_options()
    payload["type_options"] = _shipment_type_options()
    payload["draft_suggestion"] = build_cliente_envio_email_suggestion(row)
    if include_available_files:
        try:
            payload["folder_files"] = list_dropbox_folder_files(payload["carpeta_dropbox"])
        except Exception as exc:
            payload["folder_files"] = {
                "folder_path": "",
                "folder_storage_path": clean_text(payload.get("carpeta_dropbox")),
                "files": [],
                "error": str(exc),
            }
    return payload


def _draft_attachment_objects(attachments: Sequence[dict[str, object]], folder_path: Path) -> list[DraftAttachment]:
    result: list[DraftAttachment] = []
    for attachment in attachments:
        absolute = Path(clean_text(attachment.get("absolute_path")))
        if not absolute.is_absolute():
            absolute = (folder_path / clean_text(attachment.get("relative_path"))).resolve(strict=False)
        if not path_is_relative_to(absolute, folder_path.resolve(strict=False)):
            raise ValueError("Todos los adjuntos deben permanecer dentro de la carpeta asignada.")
        if not absolute.exists() or not absolute.is_file():
            raise ValueError("Uno de los adjuntos ya no existe en la carpeta seleccionada.")
        result.append(
            DraftAttachment(
                path=absolute,
                name=clean_text(attachment.get("file_name")) or absolute.name,
                content_type=clean_text(attachment.get("content_type")),
            )
        )
    return result


def generate_cliente_envio_draft(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    user_id: object,
    timestamp: str,
    overrides: dict[str, object] | None = None,
    opener: Callable[[str], object] | None = None,
    generator: Callable[..., DraftGenerationResult] = generate_outlook_draft,
) -> dict[str, object]:
    detail = get_cliente_envio(conn, envio_id)
    if not detail:
        raise ValueError("Envio no encontrado.")
    state = normalize_cliente_envio_state(detail["estado"])
    if state not in {"listo_para_preparar_correo", "correo_outlook_generado", "incidencia"}:
        raise ValueError("El envio todavia no esta listo para generar el correo.")
    folder = resolve_envio_dropbox_folder(detail["carpeta_dropbox"])
    dropbox_base = _dropbox_base_path()
    current_attachments = detail.get("attachments") or []
    selected_relative_paths = (overrides or {}).get("adjuntos")
    attachment_warning_messages: list[str] = []
    if selected_relative_paths is not None:
        selected_sequence = (
            list(selected_relative_paths)
            if isinstance(selected_relative_paths, Sequence) and not isinstance(selected_relative_paths, (str, bytes))
            else []
        )
        folder_payload, selected_files, warnings = validate_selected_attachments(
            detail["carpeta_dropbox"],
            selected_sequence,
            dropbox_base=dropbox_base,
        )
        attachments = [
            {
                "relative_path": clean_text(item.get("relative_path")),
                "absolute_path": clean_text(item.get("absolute_path")),
                "file_name": clean_text(item.get("name")) or clean_text(item.get("file_name")),
                "size_bytes": int(item.get("size_bytes") or 0),
                "content_type": "",
            }
            for item in selected_files
        ]
        conn.execute(
            """
            UPDATE cliente_envios
            SET attachments_size_total = ?, updated_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                int(folder_payload.get("selected_total_size") or 0),
                clean_text(user_id),
                timestamp,
                envio_id,
            ),
        )
        _create_envio_attachment_rows(conn, envio_id, items=selected_files, timestamp=timestamp)
        attachment_warning_messages.extend(warnings)
    else:
        attachments = current_attachments
    if not attachments:
        raise ValueError("El envio no tiene adjuntos seleccionados.")
    draft = detail.get("draft_suggestion") or build_cliente_envio_email_suggestion(detail)
    merged = {
        "to": clean_text((overrides or {}).get("destinatario_email")) or clean_text(detail.get("destinatario_email")) or clean_text(draft.get("to")),
        "subject": clean_text((overrides or {}).get("asunto")) or clean_text(detail.get("asunto")) or clean_text(draft.get("subject")),
        "body": clean_text((overrides or {}).get("cuerpo")) or clean_text(detail.get("cuerpo")) or clean_text(draft.get("body")),
    }
    attachment_objects = _draft_attachment_objects(attachments, folder)
    prepared_folder = folder / CORREOS_PREPARADOS_FOLDER
    filename = _safe_email_filename(detail, timestamp=timestamp)
    result = generator(
        preferred_msg_path=prepared_folder / f"{filename}.msg",
        to=merged["to"],
        subject=merged["subject"],
        body=merged["body"],
        attachments=attachment_objects,
        opener=opener,
    )
    combined_warning = " ".join(
        piece.strip()
        for piece in [*attachment_warning_messages, clean_text(result.warning)]
        if clean_text(piece)
    ).strip()
    if not result.ok:
        conn.execute(
            """
            UPDATE cliente_envios
            SET estado = ?, incidencia_detalle = ?, updated_by = ?, updated_at = ?
            WHERE id = ?
            """,
            ("incidencia", result.error or result.message, clean_text(user_id), timestamp, envio_id),
        )
        _record_envio_event(
            conn,
            envio_id,
            event_type="generacion_error",
            user_id=user_id,
            timestamp=timestamp,
            message=result.error or result.message,
        )
        updated = get_cliente_envio(conn, envio_id, include_available_files=True) or {}
        updated["draft_generation"] = {
            "ok": False,
            "path": result.path,
            "file_format": result.file_format,
            "message": result.message,
            "warning": combined_warning,
            "error": result.error,
        }
        return updated
    conn.execute(
        """
        UPDATE cliente_envios
        SET estado = ?, destinatario_email = ?, asunto = ?, cuerpo = ?,
            correo_generado_path = ?, correo_generado_formato = ?, correo_generado_warning = ?,
            correo_generado_at = ?, correo_generado_by = ?, updated_by = ?, updated_at = ?, incidencia_detalle = ''
        WHERE id = ?
        """,
        (
            "correo_outlook_generado",
            merged["to"],
            merged["subject"],
            merged["body"],
            result.path,
            result.file_format,
            combined_warning,
            timestamp,
            clean_text(user_id),
            clean_text(user_id),
            timestamp,
            envio_id,
        ),
    )
    _record_envio_event(
        conn,
        envio_id,
        event_type="correo_generado",
        user_id=user_id,
        timestamp=timestamp,
        old_value=state,
        new_value="correo_outlook_generado",
        message=result.message,
        metadata={
            "path": result.path,
            "file_format": result.file_format,
            "warning": combined_warning,
            "opened": result.opened,
        },
    )
    updated = get_cliente_envio(conn, envio_id, include_available_files=True) or {}
    updated["draft_generation"] = {
        "ok": True,
        "path": result.path,
        "file_format": result.file_format,
        "message": result.message,
        "warning": combined_warning,
        "error": result.error,
    }
    return updated


def mark_cliente_envio_sent(conn: sqlite3.Connection, envio_id: int, *, user_id: object, timestamp: str) -> dict[str, object]:
    detail = get_cliente_envio(conn, envio_id)
    if not detail:
        raise ValueError("Envio no encontrado.")
    state = normalize_cliente_envio_state(detail["estado"])
    if not _allowed_transition(state, "enviado"):
        raise ValueError("Solo se pueden marcar como enviados los correos ya preparados.")
    conn.execute(
        """
        UPDATE cliente_envios
        SET estado = ?, enviado_at = ?, enviado_by = ?, updated_by = ?, updated_at = ?
        WHERE id = ?
        """,
        ("enviado", timestamp, clean_text(user_id), clean_text(user_id), timestamp, envio_id),
    )
    _record_envio_event(
        conn,
        envio_id,
        event_type="marcado_enviado",
        user_id=user_id,
        timestamp=timestamp,
        old_value=state,
        new_value="enviado",
        message="Envio marcado manualmente como enviado.",
    )
    return get_cliente_envio(conn, envio_id, include_available_files=True) or {}


def _safe_open_path(path: Path, *, allowed_root: Path, opener: Callable[[str], object] | None = None) -> dict[str, object]:
    if not path.exists():
        return {"ok": False, "error": "La ruta indicada no existe.", "path": str(path)}
    if path.is_symlink():
        return {"ok": False, "error": "No se permiten enlaces simbolicos.", "path": str(path)}
    resolved = path.resolve(strict=True)
    if not path_inside_base(resolved, allowed_root):
        return {"ok": False, "error": "La ruta queda fuera de Dropbox.", "path": str(path)}
    open_with = opener or getattr(__import__("os"), "startfile", None)
    if open_with is None:
        return {"ok": False, "error": "No hay un mecanismo disponible para abrir el archivo.", "path": str(path)}
    try:
        open_with(str(resolved))
    except OSError as exc:
        return {"ok": False, "error": str(exc), "path": str(resolved)}
    return {"ok": True, "message": "Ruta abierta.", "path": str(resolved)}


def open_cliente_envio_folder(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    opener: Callable[[str], object] | None = None,
) -> dict[str, object]:
    detail = get_cliente_envio(conn, envio_id)
    if not detail:
        raise ValueError("Envio no encontrado.")
    folder = resolve_envio_dropbox_folder(detail["carpeta_dropbox"])
    return _safe_open_path(folder, allowed_root=_dropbox_base_path(), opener=opener)


def open_cliente_envio_draft(
    conn: sqlite3.Connection,
    envio_id: int,
    *,
    opener: Callable[[str], object] | None = None,
) -> dict[str, object]:
    detail = get_cliente_envio(conn, envio_id)
    if not detail:
        raise ValueError("Envio no encontrado.")
    draft_path = clean_text(detail.get("correo_generado_path"))
    if not draft_path:
        raise ValueError("El envio todavia no tiene un correo preparado.")
    return _safe_open_path(Path(draft_path), allowed_root=_dropbox_base_path(), opener=opener)
