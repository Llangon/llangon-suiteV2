from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from ..ai.file_selection import resolve_ai_source_folder
from .store import ACCESS_CODE_ITERATIONS, generate_access_code, hash_access_code, ingest_portal_events


class PortalRemoteError(ValueError):
    pass


def _settings() -> tuple[str, str, str]:
    base_url = os.environ.get("LLANGON_PORTAL_BASE_URL", "").strip().rstrip("/")
    public_url = os.environ.get("LLANGON_PUBLIC_PORTAL_URL", "").strip().rstrip("/")
    secret = os.environ.get("LLANGON_PORTAL_SYNC_SECRET", "").strip()
    if not base_url or not public_url or not secret:
        raise PortalRemoteError("Configura LLANGON_PORTAL_BASE_URL, LLANGON_PUBLIC_PORTAL_URL y LLANGON_PORTAL_SYNC_SECRET antes de publicar.")
    if not base_url.startswith("https://") and not base_url.startswith("http://127.0.0.1"):
        raise PortalRemoteError("La dirección del portal debe usar HTTPS.")
    if not public_url.startswith("https://") and not public_url.startswith("http://127.0.0.1"):
        raise PortalRemoteError("La dirección pública del portal debe usar HTTPS.")
    return base_url, public_url, secret


def _request(url: str, secret: str, *, method: str = "GET", data: bytes | None = None, content_type: str = "application/json") -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": content_type, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise PortalRemoteError(f"El portal público no respondió: {reason}") from exc
    try:
        return json.loads(payload.decode("utf-8")) if payload else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PortalRemoteError("El portal público devolvió una respuesta no válida.") from exc


def _file_id(relative_path: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, relative_path.casefold().replace("\\", "/")))


def publish_portal(conn: sqlite3.Connection, publication_id: str) -> dict[str, object]:
    base_url, public_base_url, secret = _settings()
    publication = conn.execute("SELECT * FROM portal_publications WHERE id = ?", (publication_id,)).fetchone()
    if not publication:
        raise PortalRemoteError("No se encuentra el borrador del portal.")
    model = json.loads(publication["model_json"])
    coverage = model.get("coverage") if isinstance(model, dict) else {}
    if publication["status"] != "draft" or not isinstance(coverage, dict) or coverage.get("status") != "preview_ready":
        raise PortalRemoteError("La vista previa tiene revisiones pendientes y todavía no puede publicarse.")
    licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (publication["licitacion_id"],)).fetchone()
    if not licitacion:
        raise PortalRemoteError("No se encuentra la licitación asociada.")
    folder, _diagnostics = resolve_ai_source_folder(licitacion)
    selected_files = json.loads(publication["selected_files_json"])
    files: list[dict[str, object]] = []
    local_files: dict[str, Path] = {}
    for order, relative in enumerate(selected_files):
        path = (folder / str(relative)).resolve()
        try:
            path.relative_to(folder.resolve())
        except ValueError as exc:
            raise PortalRemoteError("Un fichero del borrador queda fuera de la licitación.") from exc
        if not path.is_file():
            raise PortalRemoteError(f"Ya no se encuentra el fichero: {relative}")
        file_id = _file_id(str(relative))
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append({
            "id": file_id,
            "name": path.name,
            "extension": path.suffix.lstrip(".").upper(),
            "size_bytes": path.stat().st_size,
            "content_type": content_type,
            "sort_order": order,
        })
        local_files[file_id] = path
    body = {
        "id": publication["id"],
        "slug": publication["slug"],
        "client_label": publication["client_label"] or "",
        "model": model,
        "access_salt": publication["access_salt"],
        "access_hash": publication["access_hash"],
        "access_iterations": publication["access_iterations"],
        "files": files,
    }
    remote = _request(f"{base_url}/api/admin/publications", secret, method="POST", data=json.dumps(body, ensure_ascii=False).encode("utf-8"))
    for upload in remote.get("upload_files", []):
        if not isinstance(upload, dict):
            continue
        file_id = str(upload.get("id") or "")
        remote_path = str(upload.get("path") or "")
        local = local_files.get(file_id)
        if not local or not remote_path.startswith("/api/admin/"):
            raise PortalRemoteError("El portal devolvió una ruta de carga no válida.")
        _request(
            f"{base_url}{remote_path}",
            secret,
            method="PUT",
            data=local.read_bytes(),
            content_type=mimetypes.guess_type(local.name)[0] or "application/octet-stream",
        )
    _request(
        f"{base_url}/api/admin/publications/{urllib.parse.quote(publication_id)}/finalize",
        secret,
        method="POST",
        data=b"{}",
    )
    now = datetime.now().replace(microsecond=0).isoformat()
    public_url = f"{public_base_url}/p/{urllib.parse.quote(str(publication['slug']))}"
    conn.execute(
        "UPDATE portal_publications SET status = 'published', public_url = ?, remote_publication_id = ?, published_at = COALESCE(published_at, ?), updated_at = ? WHERE id = ?",
        (public_url, str(remote.get("id") or publication_id), now, now, publication_id),
    )
    return {"id": publication_id, "status": "published", "public_url": public_url, "files_uploaded": len(files)}


def sync_portal_events(conn: sqlite3.Connection, publication_id: str) -> dict[str, object]:
    base_url, _public_base_url, secret = _settings()
    publication = conn.execute("SELECT * FROM portal_publications WHERE id = ?", (publication_id,)).fetchone()
    if not publication or publication["status"] != "published":
        raise PortalRemoteError("El portal todavía no está publicado.")
    after = str(publication["last_event_sync_at"] or "")
    url = f"{base_url}/api/admin/publications/{urllib.parse.quote(publication_id)}/events?after={urllib.parse.quote(after)}"
    payload = _request(url, secret)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    inserted = ingest_portal_events(conn, publication_id, items)
    return {"id": publication_id, "events_received": len(items), "events_inserted": inserted}


def rotate_portal_access_code(conn: sqlite3.Connection, publication_id: str) -> dict[str, object]:
    """Genera una clave visible nueva y la aplica al portal ya publicado."""
    base_url, _public_base_url, secret = _settings()
    publication = conn.execute(
        "SELECT * FROM portal_publications WHERE id = ?", (publication_id,)
    ).fetchone()
    if not publication or publication["status"] != "published":
        raise PortalRemoteError("El portal todavía no está publicado.")
    access_code = generate_access_code()
    access_salt, access_hash = hash_access_code(access_code)
    body = {
        "access_salt": access_salt,
        "access_hash": access_hash,
        "access_iterations": ACCESS_CODE_ITERATIONS,
    }
    _request(
        f"{base_url}/api/admin/publications/{urllib.parse.quote(publication_id)}/access-code",
        secret,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
    )
    now = datetime.now().replace(microsecond=0).isoformat()
    conn.execute(
        """UPDATE portal_publications
           SET access_salt = ?, access_hash = ?, access_iterations = ?, updated_at = ?
           WHERE id = ?""",
        (access_salt, access_hash, ACCESS_CODE_ITERATIONS, now, publication_id),
    )
    model = json.loads(publication["model_json"])
    model["publication"] = {
        "id": publication["id"],
        "licitacion_id": publication["licitacion_id"],
        "ficha_relative_path": publication["ficha_relative_path"],
        "client_label": publication["client_label"] or "",
        "slug": publication["slug"],
        "status": "published",
        "access_code": access_code,
        "public_url": publication["public_url"] or "",
        "published": True,
        "updated_at": now,
    }
    return model
