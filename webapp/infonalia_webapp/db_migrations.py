from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

try:
    from .licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_OFERTA_ENVIADA,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
    )
except ImportError:
    from licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_OFERTA_ENVIADA,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
    )

try:
    from .monitor.repository import ensure_monitor_schema as _ensure_monitor_schema
except ImportError:
    from monitor.repository import ensure_monitor_schema as _ensure_monitor_schema

try:
    from .ai.queue import ensure_ai_schema as _ensure_ai_schema
except ImportError:
    from ai.queue import ensure_ai_schema as _ensure_ai_schema

try:
    from .ai.notifications import ensure_ai_notifications_schema as _ensure_ai_notifications_schema
except ImportError:
    from ai.notifications import ensure_ai_notifications_schema as _ensure_ai_notifications_schema

try:
    from .comments import ensure_comments_schema as _ensure_comments_schema
except ImportError:
    from comments import ensure_comments_schema as _ensure_comments_schema

try:
    from .email_actions import ensure_email_action_schema as _ensure_email_action_schema
except ImportError:
    from email_actions import ensure_email_action_schema as _ensure_email_action_schema

try:
    from .infonalia_mail_importer import ensure_infonalia_email_import_schema as _ensure_infonalia_email_import_schema
except ImportError:
    from infonalia_mail_importer import ensure_infonalia_email_import_schema as _ensure_infonalia_email_import_schema


MIGRATIONS_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    apply: Callable[[sqlite3.Connection], None]


def enable_foreign_keys(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _baseline_schema(_: sqlite3.Connection) -> None:
    return None


def _download_jobs_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS download_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            storage_backend TEXT,
            storage_uri TEXT,
            file_manifest TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_licitacion ON download_jobs(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_created ON download_jobs(created_at)")


def _import_history_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            triggered_by TEXT,
            input_name TEXT,
            input_hash TEXT,
            new_count INTEGER NOT NULL DEFAULT 0,
            updated_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS import_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_run_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            external_id TEXT,
            fingerprint TEXT,
            licitacion_id INTEGER,
            status TEXT NOT NULL,
            error_message TEXT,
            raw_payload TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (import_run_id) REFERENCES import_runs(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_runs_source_started ON import_runs(source_name, started_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_runs_status ON import_runs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_results_run ON import_results(import_run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_results_licitacion ON import_results(licitacion_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_import_results_source_external ON import_results(source_name, external_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_results_fingerprint ON import_results(fingerprint)")


def _actuaciones_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licitacion_actuaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            prioridad TEXT NOT NULL DEFAULT 'normal',
            responsable_user_id TEXT,
            deadline_at TEXT,
            recordatorio_email INTEGER NOT NULL DEFAULT 1,
            origen TEXT NOT NULL DEFAULT 'manual',
            respuesta_resumen TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            closed_by TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actuaciones_licitacion ON licitacion_actuaciones(licitacion_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_estado ON licitacion_actuaciones(estado)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_deadline ON licitacion_actuaciones(deadline_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actuaciones_responsable ON licitacion_actuaciones(responsable_user_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_tipo ON licitacion_actuaciones(tipo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_prioridad ON licitacion_actuaciones(prioridad)")


def _create_actuaciones_multilicitacion_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actuaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            deadline_at TEXT,
            recordatorio_email INTEGER NOT NULL DEFAULT 1,
            origen TEXT NOT NULL DEFAULT 'manual',
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            closed_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actuacion_licitaciones (
            actuacion_id INTEGER NOT NULL,
            licitacion_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT,
            PRIMARY KEY (actuacion_id, licitacion_id),
            FOREIGN KEY (actuacion_id) REFERENCES actuaciones(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actuacion_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actuacion_id INTEGER NOT NULL,
            user_id TEXT,
            event_type TEXT NOT NULL,
            comentario TEXT,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (actuacion_id) REFERENCES actuaciones(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_deadline ON actuaciones(deadline_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_estado ON actuaciones(estado)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actuaciones_tipo ON actuaciones(tipo)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actuacion_licitaciones_licitacion ON actuacion_licitaciones(licitacion_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actuacion_licitaciones_actuacion ON actuacion_licitaciones(actuacion_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_actuacion_historial_actuacion ON actuacion_historial(actuacion_id)"
    )


def _actuaciones_multilicitacion_schema(conn: sqlite3.Connection) -> None:
    legacy_exists = _table_exists(conn, "licitacion_actuaciones")
    legacy_rows = []
    if legacy_exists:
        legacy_columns = [
            "id",
            "licitacion_id",
            "tipo",
            "titulo",
            "descripcion",
            "estado",
            "deadline_at",
            "recordatorio_email",
            "origen",
            "created_by",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
        ]
        legacy_rows = [
            dict(zip(legacy_columns, row))
            for row in conn.execute(
            """
            SELECT id, licitacion_id, tipo, titulo, descripcion, estado, deadline_at,
                   recordatorio_email, origen, created_by, created_at, updated_at,
                   closed_at, closed_by
            FROM licitacion_actuaciones
            ORDER BY id ASC
            """
            ).fetchall()
        ]
        conn.execute("DROP TABLE IF EXISTS actuacion_historial")
        conn.execute("DROP TABLE IF EXISTS actuacion_licitaciones")
        conn.execute("DROP TABLE IF EXISTS actuaciones")
        conn.execute("DROP TABLE IF EXISTS licitacion_actuaciones")

    _create_actuaciones_multilicitacion_tables(conn)

    if legacy_exists:
        for row in legacy_rows:
            conn.execute(
                """
                INSERT INTO actuaciones (
                    id, tipo, titulo, descripcion, estado, deadline_at, recordatorio_email,
                    origen, created_by, created_at, updated_at, closed_at, closed_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["tipo"],
                    row["titulo"],
                    row["descripcion"],
                    row["estado"],
                    row["deadline_at"],
                    row["recordatorio_email"],
                    row["origen"],
                    row["created_by"],
                    row["created_at"],
                    row["updated_at"],
                    row["closed_at"],
                    row["closed_by"],
                ),
            )
            if conn.execute("SELECT 1 FROM licitaciones WHERE id = ?", (row["licitacion_id"],)).fetchone():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO actuacion_licitaciones (
                        actuacion_id, licitacion_id, created_at, created_by
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (row["id"], row["licitacion_id"], row["created_at"], row["created_by"]),
                )
            conn.execute(
                """
                INSERT INTO actuacion_historial (
                    actuacion_id, user_id, event_type, comentario, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["created_by"],
                    "migracion",
                    "Actuacion migrada a modelo multi-licitacion",
                    row["updated_at"],
                ),
            )


def _agenda_eventos_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agenda_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            starts_at TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            closed_by TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agenda_eventos_starts_at ON agenda_eventos(starts_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agenda_eventos_estado ON agenda_eventos(estado)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agenda_eventos_created_by ON agenda_eventos(created_by)")


def _storage_uploads_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storage_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            download_job_id INTEGER,
            backend TEXT NOT NULL,
            destination_uri TEXT,
            manifest_json TEXT,
            status TEXT NOT NULL,
            dry_run INTEGER NOT NULL DEFAULT 0,
            mode TEXT NOT NULL,
            uploaded_count INTEGER NOT NULL DEFAULT 0,
            skipped_existing_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            no_changes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            error_message TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (download_job_id) REFERENCES download_jobs(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_uploads_licitacion ON storage_uploads(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_uploads_job ON storage_uploads(download_job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_uploads_backend ON storage_uploads(backend)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_uploads_created ON storage_uploads(created_at)")


def _licitaciones_center_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones"):
        conn.execute(
            """
            CREATE TABLE licitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'Importada',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(licitaciones)")}
    additions = {
        "reviewed_at": "TEXT",
        "reviewed_by": "TEXT",
        "estado_interno": "TEXT NOT NULL DEFAULT 'Nueva'",
        "notas_internas": "TEXT",
        "seguimiento_activo": "INTEGER NOT NULL DEFAULT 0",
        "seguimiento_desde": "TEXT",
        "seguimiento_ultimo_check": "TEXT",
        "seguimiento_ultima_novedad": "TEXT",
        "seguimiento_notas": "TEXT",
    }
    for column, definition in additions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE licitaciones ADD COLUMN {column} {definition}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licitacion_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            user_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licitacion_seguimiento_novedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            licitacion_id INTEGER NOT NULL,
            detected_at TEXT NOT NULL,
            source TEXT,
            title TEXT NOT NULL,
            summary TEXT,
            change_type TEXT,
            file_name TEXT,
            file_path TEXT,
            status TEXT NOT NULL DEFAULT 'nueva',
            raw_data_json TEXT,
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_reviewed ON licitaciones(reviewed_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_estado_interno ON licitaciones(estado_interno)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_licitaciones_seguimiento ON licitaciones(seguimiento_activo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_licitacion_historial_licitacion ON licitacion_historial(licitacion_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_seguimiento_novedades_licitacion ON licitacion_seguimiento_novedades(licitacion_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_seguimiento_novedades_detected ON licitacion_seguimiento_novedades(detected_at)"
    )


def _normalize_licitacion_states(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones") or not _column_exists(conn, "licitaciones", "estado"):
        return
    mappings = {
        "": ESTADO_IMPORTADA,
        "Pendiente": ESTADO_IMPORTADA,
        "Importado": ESTADO_IMPORTADA,
        "Descartada por mí": ESTADO_DESCARTADA,
        "Descartada interna": ESTADO_DESCARTADA,
        "Descartar": ESTADO_DESCARTADA,
        "Pendiente Nuria": ESTADO_ENVIADA_NURIA,
        "Enviada Nuria": ESTADO_ENVIADA_NURIA,
        "Descargar": ESTADO_DESCARGAR_PARA_VER,
        "Solo descargar": ESTADO_DESCARGAR_PARA_VER,
        "Hacer": ESTADO_PREPARAR_FICHA,
        "Hacer concurso": ESTADO_PREPARAR_FICHA,
        "Preparar licitación": ESTADO_PREPARAR_FICHA,
        "Presentada": ESTADO_OFERTA_ENVIADA,
    }
    for old, new in mappings.items():
        conn.execute(
            "UPDATE licitaciones SET estado = ? WHERE COALESCE(estado, '') = ?",
            (new, old),
        )
    conn.execute(
        """
        UPDATE licitaciones
        SET estado = ?
        WHERE estado NOT IN (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ESTADO_IMPORTADA,
            ESTADO_IMPORTADA,
            ESTADO_DESCARTADA,
            ESTADO_ENVIADA_NURIA,
            ESTADO_DESCARGAR_PARA_VER,
            ESTADO_PREPARAR_FICHA,
            ESTADO_PREPARADA,
            ESTADO_OFERTA_ENVIADA,
        ),
    )


def _licitaciones_marker_cache_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones"):
        return
    additions = {
        "seguimiento_ultima_sync": "TEXT",
        "seguimiento_marker_path": "TEXT",
        "seguimiento_marker_warning": "TEXT",
    }
    for column, definition in additions.items():
        if not _column_exists(conn, "licitaciones", column):
            conn.execute(f"ALTER TABLE licitaciones ADD COLUMN {column} {definition}")


def _monitor_v0_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones"):
        return
    _ensure_monitor_schema(conn)


def _monitor_inventory_v05_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones"):
        return
    _ensure_monitor_schema(conn)


def _ai_analysis_phase1_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "licitaciones"):
        return
    _ensure_ai_schema(conn)


def _ai_jobs_dismissed_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ai_analysis_jobs"):
        _ensure_ai_schema(conn)
        return
    if not _column_exists(conn, "ai_analysis_jobs", "dismissed_at"):
        conn.execute("ALTER TABLE ai_analysis_jobs ADD COLUMN dismissed_at TEXT")
    if not _column_exists(conn, "ai_analysis_jobs", "dismissed_by"):
        conn.execute("ALTER TABLE ai_analysis_jobs ADD COLUMN dismissed_by TEXT")


def _ai_jobs_progress_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ai_analysis_jobs"):
        _ensure_ai_schema(conn)
        return
    _ensure_ai_schema(conn)


def _ai_notifications_schema(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ai_analysis_jobs") or not _table_exists(conn, "licitaciones"):
        return
    _ensure_ai_notifications_schema(conn)


def _comments_schema(conn: sqlite3.Connection) -> None:
    _ensure_comments_schema(conn)
    if not _table_exists(conn, "licitaciones"):
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(licitaciones)").fetchall()}
    migrated_at = datetime.now().replace(microsecond=0).isoformat()
    for column, label in (
        ("notas_internas", "Nota interna migrada"),
        ("seguimiento_notas", "Nota de seguimiento migrada"),
        ("comentario", "Comentario migrado"),
    ):
        if column not in columns:
            continue
        rows = conn.execute(
            f"""
            SELECT id, {column} AS note
            FROM licitaciones
            WHERE COALESCE({column}, '') <> ''
            """
        ).fetchall()
        for row in rows:
            body = f"{label}: {row['note']}"
            exists = conn.execute(
                """
                SELECT 1
                FROM comments
                WHERE entity_type = 'licitacion'
                  AND entity_id = ?
                  AND author_user_id = 'system'
                  AND body = ?
                LIMIT 1
                """,
                (row["id"], body),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO comments (
                    entity_type, entity_id, author_user_id, author_name, body,
                    created_at, updated_at, visibility, metadata_json
                )
                VALUES ('licitacion', ?, 'system', 'Sistema', ?, ?, ?, 'internal', ?)
                """,
                (
                    row["id"],
                    body,
                    migrated_at,
                    migrated_at,
                    f'{{"source_column":"{column}"}}',
                ),
            )


def _email_action_codes_schema(conn: sqlite3.Connection) -> None:
    _ensure_email_action_schema(conn)


def _email_action_events_schema(conn: sqlite3.Connection) -> None:
    _ensure_email_action_schema(conn)


def _infonalia_email_imports_schema(conn: sqlite3.Connection) -> None:
    _ensure_infonalia_email_import_schema(conn)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001_baseline_schema",
        description="Baseline del esquema historico gestionado por init_db",
        apply=_baseline_schema,
    ),
    Migration(
        version="0002_download_jobs",
        description="Tabla preparatoria para jobs de descarga",
        apply=_download_jobs_schema,
    ),
    Migration(
        version="0003_import_history",
        description="Tablas preparatorias para historial de importaciones",
        apply=_import_history_schema,
    ),
    Migration(
        version="0004_actuaciones",
        description="Tabla operativa para actuaciones y vencimientos",
        apply=_actuaciones_schema,
    ),
    Migration(
        version="0005_actuaciones_multilicitacion",
        description="Modelo independiente de actuaciones con vinculos multiples e historial",
        apply=_actuaciones_multilicitacion_schema,
    ),
    Migration(
        version="0006_agenda_eventos",
        description="Eventos internos para Agenda operativa",
        apply=_agenda_eventos_schema,
    ),
    Migration(
        version="0007_storage_uploads",
        description="Auditoria de almacenamiento local y Dropbox",
        apply=_storage_uploads_schema,
    ),
    Migration(
        version="0008_licitaciones_center",
        description="Campos de trabajo, seguimiento e historial para licitaciones",
        apply=_licitaciones_center_schema,
    ),
    Migration(
        version="0009_licitaciones_estados_operativos",
        description="Normalizacion de estados operativos de licitaciones",
        apply=_normalize_licitacion_states,
    ),
    Migration(
        version="0010_licitaciones_seguimiento_markers",
        description="Cache derivada de marcadores Dropbox para seguimiento",
        apply=_licitaciones_marker_cache_schema,
    ),
    Migration(
        version="0011_monitor_licitaciones_v0",
        description="Monitor V0 local con runs e inventario de ficheros",
        apply=_monitor_v0_schema,
    ),
    Migration(
        version="0012_monitor_inventory_v05",
        description="Clasificacion documental del inventario Monitor V0.5",
        apply=_monitor_inventory_v05_schema,
    ),
    Migration(
        version="0013_ai_analysis_phase1",
        description="Analisis IA Gemini Fase 1 con jobs, summaries y usage log",
        apply=_ai_analysis_phase1_schema,
    ),
    Migration(
        version="0014_ai_jobs_dismissed",
        description="Marca de descarte UI para jobs IA historicos",
        apply=_ai_jobs_dismissed_schema,
    ),
    Migration(
        version="0015_ai_jobs_progress",
        description="Campos de progreso y control para la cola IA",
        apply=_ai_jobs_progress_schema,
    ),
    Migration(
        version="0016_ai_analysis_notifications",
        description="Avisos por email asociados a jobs de analisis IA",
        apply=_ai_notifications_schema,
    ),
    Migration(
        version="0017_comments_unified",
        description="Comentarios unificados por entidad",
        apply=_comments_schema,
    ),
    Migration(
        version="0018_email_action_codes",
        description="Codigos de accion por correo para revision Infonalia",
        apply=_email_action_codes_schema,
    ),
    Migration(
        version="0019_email_action_events",
        description="Auditoria de acciones por correo de revision Infonalia",
        apply=_email_action_events_schema,
    ),
    Migration(
        version="0020_infonalia_email_imports",
        description="Control idempotente de importaciones de correos Infonalia",
        apply=_infonalia_email_imports_schema,
    ),
)


def migration_timestamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def applied_migration_versions(conn: sqlite3.Connection) -> set[str]:
    ensure_migrations_table(conn)
    return {
        row[0]
        for row in conn.execute(
            f"SELECT version FROM {MIGRATIONS_TABLE}"
        ).fetchall()
    }


def validate_migrations(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    items = tuple(migrations)
    seen: set[str] = set()
    duplicates: list[str] = []
    for migration in items:
        if not migration.version:
            raise ValueError("Migration version cannot be empty")
        if migration.version in seen:
            duplicates.append(migration.version)
        seen.add(migration.version)
    if duplicates:
        joined = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"Duplicate migration version: {joined}")
    return items


def run_migrations(
    conn: sqlite3.Connection,
    migrations: Iterable[Migration] = MIGRATIONS,
    *,
    now: Callable[[], str] = migration_timestamp,
) -> list[str]:
    enable_foreign_keys(conn)
    items = validate_migrations(migrations)
    ensure_migrations_table(conn)
    applied = applied_migration_versions(conn)
    applied_now: list[str] = []

    for migration in items:
        if migration.version in applied:
            continue
        migration.apply(conn)
        conn.execute(
            f"""
            INSERT INTO {MIGRATIONS_TABLE} (version, description, applied_at)
            VALUES (?, ?, ?)
            """,
            (migration.version, migration.description, now()),
        )
        applied.add(migration.version)
        applied_now.append(migration.version)

    return applied_now
