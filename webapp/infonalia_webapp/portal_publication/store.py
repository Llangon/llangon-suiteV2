from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import unicodedata
import uuid
from datetime import datetime


ACCESS_CODE_ITERATIONS = 210_000


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _slug_part(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    folded = "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()
    clean = "-".join("".join(ch if ch.isalnum() else " " for ch in folded).split())
    return clean[:42].strip("-") or "cliente"


def generate_access_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)]
    return "LL-" + "-".join(groups)


def hash_access_code(code: str, *, salt: bytes | None = None) -> tuple[str, str]:
    active_salt = salt or secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), active_salt, ACCESS_CODE_ITERATIONS)
    return _b64(active_salt), _b64(digest)


def ensure_portal_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portal_publications (
            id TEXT PRIMARY KEY,
            licitacion_id INTEGER NOT NULL,
            ficha_relative_path TEXT NOT NULL,
            client_label TEXT,
            slug TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'draft',
            model_json TEXT NOT NULL,
            selected_files_json TEXT NOT NULL,
            access_salt TEXT NOT NULL,
            access_hash TEXT NOT NULL,
            access_iterations INTEGER NOT NULL,
            public_url TEXT,
            remote_publication_id TEXT,
            published_at TEXT,
            last_event_sync_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (licitacion_id, ficha_relative_path),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portal_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publication_id TEXT NOT NULL,
            remote_event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            file_id TEXT,
            file_name TEXT,
            visitor_id TEXT,
            occurred_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            FOREIGN KEY (publication_id) REFERENCES portal_publications(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_portal_publications_licitacion ON portal_publications(licitacion_id, updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_portal_publications_status ON portal_publications(status, updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_portal_events_publication ON portal_events(publication_id, occurred_at)")


def save_portal_draft(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    ficha_relative_path: str,
    model: dict[str, object],
    selected_files: list[str],
) -> dict[str, object]:
    ensure_portal_schema(conn)
    existing = conn.execute(
        "SELECT * FROM portal_publications WHERE licitacion_id = ? AND ficha_relative_path = ?",
        (licitacion_id, ficha_relative_path),
    ).fetchone()
    tender = model.get("tender") if isinstance(model.get("tender"), dict) else {}
    client_label = str((tender or {}).get("recipient") or "").strip()
    access_code = generate_access_code()
    salt, access_hash = hash_access_code(access_code)
    coverage = model.get("coverage") if isinstance(model.get("coverage"), dict) else {}
    status = "draft" if (coverage or {}).get("status") == "preview_ready" else "needs_review"
    now = _now()
    if existing:
        publication_id = str(existing["id"])
        slug = str(existing["slug"])
        conn.execute(
            """
            UPDATE portal_publications
            SET client_label = ?, status = ?, model_json = ?, selected_files_json = ?,
                access_salt = ?, access_hash = ?, access_iterations = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                client_label,
                status,
                json.dumps(model, ensure_ascii=False),
                json.dumps(selected_files, ensure_ascii=False),
                salt,
                access_hash,
                ACCESS_CODE_ITERATIONS,
                now,
                publication_id,
            ),
        )
    else:
        publication_id = str(uuid.uuid4())
        slug = f"l{licitacion_id}-{_slug_part(client_label)}-{secrets.token_hex(3)}"
        conn.execute(
            """
            INSERT INTO portal_publications (
                id, licitacion_id, ficha_relative_path, client_label, slug, status,
                model_json, selected_files_json, access_salt, access_hash, access_iterations,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publication_id,
                licitacion_id,
                ficha_relative_path,
                client_label,
                slug,
                status,
                json.dumps(model, ensure_ascii=False),
                json.dumps(selected_files, ensure_ascii=False),
                salt,
                access_hash,
                ACCESS_CODE_ITERATIONS,
                now,
                now,
            ),
        )
    return {
        "id": publication_id,
        "licitacion_id": licitacion_id,
        "ficha_relative_path": ficha_relative_path,
        "client_label": client_label,
        "slug": slug,
        "status": status,
        "access_code": access_code,
        "public_url": str(existing["public_url"] or "") if existing else "",
        "published": status == "published",
        "updated_at": now,
    }


def publication_rows(conn: sqlite3.Connection, licitacion_id: int) -> list[dict[str, object]]:
    ensure_portal_schema(conn)
    rows = conn.execute(
        """
        SELECT p.*,
               SUM(CASE WHEN e.event_type = 'access' THEN 1 ELSE 0 END) AS access_count,
               SUM(CASE WHEN e.event_type = 'download' THEN 1 ELSE 0 END) AS download_count,
               MAX(e.occurred_at) AS last_activity_at
        FROM portal_publications p
        LEFT JOIN portal_events e ON e.publication_id = p.id
        WHERE p.licitacion_id = ?
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """,
        (licitacion_id,),
    ).fetchall()
    publications: list[dict[str, object]] = []
    for row in rows:
        recent = conn.execute(
            """SELECT event_type, file_name, occurred_at
               FROM portal_events WHERE publication_id = ?
               ORDER BY occurred_at DESC, id DESC LIMIT 25""",
            (row["id"],),
        ).fetchall()
        publications.append({
            "id": row["id"],
            "client_label": row["client_label"] or "",
            "ficha_relative_path": row["ficha_relative_path"],
            "slug": row["slug"],
            "status": row["status"],
            "public_url": row["public_url"] or "",
            "published_at": row["published_at"] or "",
            "updated_at": row["updated_at"],
            "access_count": int(row["access_count"] or 0),
            "download_count": int(row["download_count"] or 0),
            "last_activity_at": row["last_activity_at"] or "",
            "recent_events": [
                {
                    "event_type": event["event_type"],
                    "file_name": event["file_name"] or "",
                    "occurred_at": event["occurred_at"],
                }
                for event in recent
            ],
        })
    return publications


def recover_portal_preview(conn: sqlite3.Connection, publication_id: str) -> dict[str, object]:
    """Recupera un modelo ya generado y rota la clave que nunca llegó al navegador."""
    ensure_portal_schema(conn)
    row = conn.execute("SELECT * FROM portal_publications WHERE id = ?", (publication_id,)).fetchone()
    if not row:
        raise ValueError("No se encuentra el borrador del portal.")
    access_code = generate_access_code()
    salt, access_hash = hash_access_code(access_code)
    now = _now()
    conn.execute(
        "UPDATE portal_publications SET access_salt = ?, access_hash = ?, access_iterations = ?, updated_at = ? WHERE id = ?",
        (salt, access_hash, ACCESS_CODE_ITERATIONS, now, publication_id),
    )
    model = json.loads(row["model_json"])
    model["publication"] = {
        "id": row["id"],
        "licitacion_id": row["licitacion_id"],
        "ficha_relative_path": row["ficha_relative_path"],
        "client_label": row["client_label"] or "",
        "slug": row["slug"],
        "status": row["status"],
        "access_code": access_code,
        "public_url": row["public_url"] or "",
        "published": row["status"] == "published",
        "updated_at": now,
    }
    return model


def approve_portal_review(conn: sqlite3.Connection, publication_id: str) -> dict[str, object]:
    """Permite aprobar solo revisiones cuyo contenido dudoso ya está conservado literalmente."""
    ensure_portal_schema(conn)
    row = conn.execute("SELECT * FROM portal_publications WHERE id = ?", (publication_id,)).fetchone()
    if not row:
        raise ValueError("No se encuentra el borrador del portal.")
    model = json.loads(row["model_json"])
    coverage = model.get("coverage") if isinstance(model.get("coverage"), dict) else {}
    blocking_keys = (
        "missing_coverage_pages",
        "invalid_hash_pages",
        "visual_unreviewed_pages",
        "unmapped_pages",
        "invalid_block_mapping_pages",
    )
    if any(coverage.get(key) for key in blocking_keys):
        raise ValueError("La revisión contiene incidencias de integridad que no pueden aprobarse manualmente.")
    fallback_pages = {int(page) for page in coverage.get("fallback_pages") or []}
    literal_pages = {
        int(block.get("page"))
        for section in model.get("sections") or []
        for block in section.get("blocks") or []
        if isinstance(block, dict) and block.get("type") == "source_page" and block.get("page")
    }
    if fallback_pages - literal_pages:
        raise ValueError("Falta el contenido literal de alguna página pendiente.")
    coverage.update(
        {
            "status": "preview_ready",
            "ready_for_publication_review": True,
            "publication_allowed": True,
            "manual_review_approved": True,
            "manual_review_approved_at": _now(),
        }
    )
    model["coverage"] = coverage
    now = _now()
    conn.execute(
        "UPDATE portal_publications SET status = 'draft', model_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(model, ensure_ascii=False), now, publication_id),
    )
    return {"ok": True, "id": publication_id, "status": "draft", "coverage": coverage, "updated_at": now}


def ingest_portal_events(conn: sqlite3.Connection, publication_id: str, events: list[dict[str, object]]) -> int:
    ensure_portal_schema(conn)
    inserted = 0
    now = _now()
    for event in events:
        remote_id = str(event.get("id") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        occurred_at = str(event.get("occurred_at") or "").strip()
        if not remote_id or event_type not in {"access", "download"} or not occurred_at:
            continue
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO portal_events (
                publication_id, remote_event_id, event_type, file_id, file_name,
                visitor_id, occurred_at, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publication_id,
                remote_id,
                event_type,
                str(event.get("file_id") or ""),
                str(event.get("file_name") or ""),
                str(event.get("visitor_id") or ""),
                occurred_at,
                now,
            ),
        )
        inserted += int(cursor.rowcount > 0)
    latest = max((str(event.get("occurred_at") or "") for event in events), default="")
    if latest:
        conn.execute("UPDATE portal_publications SET last_event_sync_at = ? WHERE id = ?", (latest, publication_id))
    return inserted
