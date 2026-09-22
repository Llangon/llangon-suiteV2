from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
BRAND_LOGO = ROOT.parent / "firebase" / "public_firebase" / "static" / "logo-llangon.png"
MAX_JSON_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
SESSION_SECONDS = 12 * 60 * 60


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class PortalConfig:
    host: str
    port: int
    db_path: Path
    files_root: Path
    sync_secret: str
    session_secret: str
    public_base_url: str

    @classmethod
    def from_environment(cls) -> "PortalConfig":
        runtime_root = Path(os.environ.get("LLANGON_PUBLIC_PORTAL_RUNTIME", ROOT.parent / "runtime" / "public_portal"))
        sync_secret = os.environ.get("LLANGON_PORTAL_SYNC_SECRET", "").strip()
        session_secret = os.environ.get("LLANGON_PORTAL_SESSION_SECRET", "").strip()
        if len(sync_secret) < 32 or len(session_secret) < 32:
            raise RuntimeError("LLANGON_PORTAL_SYNC_SECRET y LLANGON_PORTAL_SESSION_SECRET deben tener al menos 32 caracteres.")
        host = os.environ.get("LLANGON_PUBLIC_PORTAL_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("El portal público local solo puede escuchar en loopback; usa Cloudflare Tunnel para publicarlo.")
        return cls(
            host=host,
            port=int(os.environ.get("LLANGON_PUBLIC_PORTAL_PORT", "8790")),
            db_path=runtime_root / "portal.db",
            files_root=runtime_root / "files",
            sync_secret=sync_secret,
            session_secret=session_secret,
            public_base_url=os.environ.get("LLANGON_PUBLIC_PORTAL_URL", "https://licitaciones.llangon.es").strip().rstrip("/"),
        )


def connect(config: PortalConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(config: PortalConfig) -> None:
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.files_root.mkdir(parents=True, exist_ok=True)
    with connect(config) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS publications (
                id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, client_label TEXT NOT NULL DEFAULT '',
                model_json TEXT NOT NULL, access_salt TEXT NOT NULL, access_hash TEXT NOT NULL,
                access_iterations INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'uploading',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT
            );
            CREATE TABLE IF NOT EXISTS publication_files (
                id TEXT PRIMARY KEY, publication_id TEXT NOT NULL, name TEXT NOT NULL,
                extension TEXT NOT NULL DEFAULT '', size_bytes INTEGER NOT NULL DEFAULT 0,
                object_key TEXT NOT NULL UNIQUE, content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS portal_events (
                id TEXT PRIMARY KEY, publication_id TEXT NOT NULL, event_type TEXT NOT NULL,
                file_id TEXT, file_name TEXT, visitor_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_publication_files_publication ON publication_files(publication_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_portal_events_publication ON portal_events(publication_id, occurred_at);
            """
        )


def make_session(config: PortalConfig, publication_id: str) -> tuple[str, str]:
    visitor_id = secrets.token_hex(16)
    payload = _b64(json.dumps({"publication_id": publication_id, "visitor_id": visitor_id, "expires": int(time.time()) + SESSION_SECONDS}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(config.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", visitor_id


def read_session(config: PortalConfig, cookie_header: str, publication_id: str) -> str:
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header or "")
        token = cookie["llangon_portal"].value
        payload, signature = token.split(".", 1)
        expected = _b64(hmac.new(config.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return ""
        data = json.loads(_unb64(payload))
        if data.get("publication_id") != publication_id or int(data.get("expires") or 0) <= int(time.time()):
            return ""
        return str(data.get("visitor_id") or "")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return ""


def _safe_file_name(value: object) -> str:
    name = Path(str(value or "")).name
    return re.sub(r"[\x00-\x1f\x7f\"\\]", "_", name)[:220]


class PortalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: PortalConfig):
        self.config = config
        self.access_failures: dict[str, list[float]] = {}
        super().__init__(address, PortalHandler)


class PortalHandler(BaseHTTPRequestHandler):
    server: PortalHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    @property
    def config(self) -> PortalConfig:
        return self.server.config

    def _headers(self, status: int, content_type: str, length: int, *, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send(self, data: bytes, status: int = 200, content_type: str = "application/octet-stream", *, extra: dict[str, str] | None = None) -> None:
        self._headers(status, content_type, len(data), extra=extra)
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, payload: object, status: int = 200, *, extra: dict[str, str] | None = None) -> None:
        self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), status, "application/json; charset=utf-8", extra=extra)

    def _body(self, limit: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Longitud no válida.") from exc
        if length < 0 or length > limit:
            raise ValueError("Petición demasiado grande.")
        return self.rfile.read(length)

    def _json_body(self) -> dict[str, object]:
        try:
            data = json.loads(self._body(MAX_JSON_BYTES))
        except json.JSONDecodeError as exc:
            raise ValueError("JSON no válido.") from exc
        if not isinstance(data, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON.")
        return data

    def _sync_allowed(self) -> bool:
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        return bool(supplied and hmac.compare_digest(supplied, self.config.sync_secret))

    def _publication(self, slug: str) -> sqlite3.Row | None:
        with connect(self.config) as conn:
            return conn.execute("SELECT * FROM publications WHERE slug = ? AND status = 'published'", (slug,)).fetchone()

    def _visitor(self, publication_id: str) -> str:
        return read_session(self.config, self.headers.get("Cookie", ""), publication_id)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._json({"ok": True, "service": "llangon-public-portal"})
            return
        match = re.fullmatch(r"/api/admin/publications/([^/]+)/events", path)
        if match:
            self._admin_events(unquote(match.group(1)), parse_qs(parsed.query).get("after", [""])[0])
            return
        match = re.fullmatch(r"/api/portal/([^/]+)/files/([^/]+)", path)
        if match:
            self._download(unquote(match.group(1)), unquote(match.group(2)))
            return
        match = re.fullmatch(r"/api/portal/([^/]+)", path)
        if match:
            self._portal_payload(unquote(match.group(1)))
            return
        if path == "/" or re.fullmatch(r"/p/[^/]+", path):
            self._static("index.html")
            return
        if path.startswith("/static/"):
            self._static(path.removeprefix("/static/"))
            return
        self._json({"error": "No encontrado."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/admin/publications":
            self._admin_publication()
            return
        match = re.fullmatch(r"/api/admin/publications/([^/]+)/finalize", path)
        if match:
            self._admin_finalize(unquote(match.group(1)))
            return
        match = re.fullmatch(r"/api/admin/publications/([^/]+)/access-code", path)
        if match:
            self._admin_access_code(unquote(match.group(1)))
            return
        match = re.fullmatch(r"/api/portal/([^/]+)/access", path)
        if match:
            self._access(unquote(match.group(1)))
            return
        self._json({"error": "No encontrado."}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        match = re.fullmatch(r"/api/admin/publications/([^/]+)/files/([^/]+)", urlparse(self.path).path)
        if not match:
            self._json({"error": "No encontrado."}, HTTPStatus.NOT_FOUND)
            return
        self._admin_file(unquote(match.group(1)), unquote(match.group(2)))

    def _static(self, relative: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", relative) or ".." in relative.split("/"):
            self._json({"error": "Ruta no válida."}, HTTPStatus.BAD_REQUEST)
            return
        path = BRAND_LOGO if relative == "logo-llangon.png" else (STATIC_ROOT / relative).resolve()
        if not path.is_file() or (path != BRAND_LOGO and STATIC_ROOT.resolve() not in path.parents):
            self._json({"error": "No encontrado."}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        cache = "public, max-age=3600" if path.name != "index.html" else "no-store"
        self._send(path.read_bytes(), content_type=f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type, extra={"Cache-Control": cache})

    def _admin_publication(self) -> None:
        if not self._sync_allowed():
            self._json({"error": "No autorizado."}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            data = self._json_body()
            publication_id = str(data["id"])
            slug = str(data["slug"])
            model = data["model"]
            files = data.get("files") if isinstance(data.get("files"), list) else []
            if not re.fullmatch(r"[a-z0-9-]{3,100}", slug):
                raise ValueError("Slug no válido.")
            now = _utcnow()
            with connect(self.config) as conn:
                conn.execute(
                    """INSERT INTO publications (id, slug, client_label, model_json, access_salt, access_hash, access_iterations, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'uploading', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, client_label=excluded.client_label,
                    model_json=excluded.model_json, access_salt=excluded.access_salt, access_hash=excluded.access_hash,
                    access_iterations=excluded.access_iterations, status='uploading', updated_at=excluded.updated_at""",
                    (publication_id, slug, str(data.get("client_label") or ""), json.dumps(model, ensure_ascii=False), str(data["access_salt"]), str(data["access_hash"]), int(data["access_iterations"]), now, now),
                )
                conn.execute("DELETE FROM publication_files WHERE publication_id = ?", (publication_id,))
                uploads = []
                for order, raw in enumerate(files):
                    if not isinstance(raw, dict):
                        continue
                    file_id = str(raw.get("id") or "")
                    name = _safe_file_name(raw.get("name"))
                    size = int(raw.get("size_bytes") or 0)
                    if not file_id or not name or size < 0 or size > MAX_FILE_BYTES:
                        raise ValueError("Metadatos de fichero no válidos.")
                    object_key = f"{publication_id}/{file_id}"
                    conn.execute("INSERT INTO publication_files (id, publication_id, name, extension, size_bytes, object_key, content_type, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (file_id, publication_id, name, str(raw.get("extension") or "")[:12], size, object_key, str(raw.get("content_type") or "application/octet-stream")[:120], int(raw.get("sort_order") or order)))
                    uploads.append({"id": file_id, "path": f"/api/admin/publications/{quote(publication_id)}/files/{quote(file_id)}"})
            self._json({"id": publication_id, "slug": slug, "upload_files": uploads})
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            self._json({"error": str(exc) or "Publicación incompleta."}, HTTPStatus.BAD_REQUEST)

    def _admin_file(self, publication_id: str, file_id: str) -> None:
        if not self._sync_allowed():
            self._json({"error": "No autorizado."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect(self.config) as conn:
            row = conn.execute("SELECT * FROM publication_files WHERE id = ? AND publication_id = ?", (file_id, publication_id)).fetchone()
        if not row:
            self._json({"error": "Fichero no registrado."}, HTTPStatus.NOT_FOUND)
            return
        try:
            content = self._body(min(MAX_FILE_BYTES, int(row["size_bytes"]) + 1))
        except ValueError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if len(content) != int(row["size_bytes"]):
            self._json({"error": "El tamaño del fichero no coincide."}, HTTPStatus.BAD_REQUEST)
            return
        target = (self.config.files_root / row["object_key"]).resolve()
        if self.config.files_root.resolve() not in target.parents:
            self._json({"error": "Ruta no válida."}, HTTPStatus.BAD_REQUEST)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(content)
        os.replace(temporary, target)
        self._json({"ok": True, "file_id": file_id})

    def _admin_finalize(self, publication_id: str) -> None:
        if not self._sync_allowed():
            self._json({"error": "No autorizado."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect(self.config) as conn:
            publication = conn.execute("SELECT * FROM publications WHERE id = ?", (publication_id,)).fetchone()
            files = conn.execute("SELECT * FROM publication_files WHERE publication_id = ?", (publication_id,)).fetchall()
            if not publication:
                self._json({"error": "Publicación no encontrada."}, HTTPStatus.NOT_FOUND)
                return
            for file in files:
                path = self.config.files_root / file["object_key"]
                if not path.is_file() or path.stat().st_size != int(file["size_bytes"]):
                    self._json({"error": "Todavía faltan documentos por cargar."}, HTTPStatus.CONFLICT)
                    return
            now = _utcnow()
            conn.execute("UPDATE publications SET status='published', published_at=COALESCE(published_at, ?), updated_at=? WHERE id=?", (now, now, publication_id))
        self._json({"ok": True, "id": publication_id, "files": len(files)})

    def _admin_access_code(self, publication_id: str) -> None:
        """Sustituye la clave de una publicación sin alterar contenido ni eventos."""
        if not self._sync_allowed():
            self._json({"error": "No autorizado."}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            data = self._json_body()
            access_salt = str(data["access_salt"])
            access_hash = str(data["access_hash"])
            access_iterations = int(data["access_iterations"])
            if not access_salt or not access_hash or not 100_000 <= access_iterations <= 1_000_000:
                raise ValueError("Datos de acceso no válidos.")
            _unb64(access_salt)
            _unb64(access_hash)
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc) or "Datos de acceso incompletos."}, HTTPStatus.BAD_REQUEST)
            return
        with connect(self.config) as conn:
            publication = conn.execute(
                "SELECT status FROM publications WHERE id = ?", (publication_id,)
            ).fetchone()
            if not publication or publication["status"] != "published":
                self._json({"error": "Publicación no encontrada."}, HTTPStatus.NOT_FOUND)
                return
            now = _utcnow()
            conn.execute(
                """UPDATE publications
                   SET access_salt = ?, access_hash = ?, access_iterations = ?, updated_at = ?
                   WHERE id = ?""",
                (access_salt, access_hash, access_iterations, now, publication_id),
            )
        self._json({"ok": True, "id": publication_id, "updated_at": now})

    def _admin_events(self, publication_id: str, after: str) -> None:
        if not self._sync_allowed():
            self._json({"error": "No autorizado."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect(self.config) as conn:
            rows = conn.execute("SELECT id, event_type, file_id, file_name, visitor_id, occurred_at FROM portal_events WHERE publication_id = ? AND occurred_at > ? ORDER BY occurred_at, id LIMIT 1000", (publication_id, after)).fetchall()
        self._json({"items": [dict(row) for row in rows]})

    def _access(self, slug: str) -> None:
        publication = self._publication(slug)
        if not publication:
            self._json({"error": "Publicación no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        client = self.headers.get("CF-Connecting-IP") or self.client_address[0]
        now = time.time()
        failures = [stamp for stamp in self.server.access_failures.get(client, []) if stamp > now - 15 * 60]
        self.server.access_failures[client] = failures
        if len(failures) >= 10:
            self._json({"error": "Demasiados intentos. Espera unos minutos."}, HTTPStatus.TOO_MANY_REQUESTS)
            return
        try:
            code = str(self._json_body().get("code") or "").strip().upper()
        except ValueError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        calculated = _b64(hashlib.pbkdf2_hmac("sha256", code.encode(), _unb64(publication["access_salt"]), int(publication["access_iterations"])))
        if not hmac.compare_digest(calculated, publication["access_hash"]):
            failures.append(now)
            self._json({"error": "La palabra clave no es correcta."}, HTTPStatus.UNAUTHORIZED)
            return
        self.server.access_failures.pop(client, None)
        token, visitor_id = make_session(self.config, publication["id"])
        with connect(self.config) as conn:
            conn.execute("INSERT INTO portal_events (id, publication_id, event_type, visitor_id, occurred_at) VALUES (?, ?, 'access', ?, ?)", (secrets.token_hex(16), publication["id"], visitor_id, _utcnow()))
        self._json({"ok": True}, extra={"Set-Cookie": f"llangon_portal={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={SESSION_SECONDS}"})

    def _portal_payload(self, slug: str) -> None:
        publication = self._publication(slug)
        if not publication:
            self._json({"error": "Publicación no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        if not self._visitor(publication["id"]):
            self._json({"error": "Acceso requerido."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect(self.config) as conn:
            files = conn.execute("SELECT id, name, extension, size_bytes FROM publication_files WHERE publication_id = ? ORDER BY sort_order, name", (publication["id"],)).fetchall()
        self._json({"model": json.loads(publication["model_json"]), "client_label": publication["client_label"], "files": [dict(row) for row in files]})

    def _download(self, slug: str, file_id: str) -> None:
        publication = self._publication(slug)
        if not publication:
            self._json({"error": "Publicación no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        visitor_id = self._visitor(publication["id"])
        if not visitor_id:
            self._json({"error": "Acceso requerido."}, HTTPStatus.UNAUTHORIZED)
            return
        with connect(self.config) as conn:
            file = conn.execute("SELECT * FROM publication_files WHERE id = ? AND publication_id = ?", (file_id, publication["id"])).fetchone()
            if not file:
                self._json({"error": "Fichero no encontrado."}, HTTPStatus.NOT_FOUND)
                return
            path = (self.config.files_root / file["object_key"]).resolve()
            if self.config.files_root.resolve() not in path.parents or not path.is_file():
                self._json({"error": "Fichero no disponible."}, HTTPStatus.NOT_FOUND)
                return
            conn.execute("INSERT INTO portal_events (id, publication_id, event_type, file_id, file_name, visitor_id, occurred_at) VALUES (?, ?, 'download', ?, ?, ?, ?)", (secrets.token_hex(16), publication["id"], file["id"], file["name"], visitor_id, _utcnow()))
        name = _safe_file_name(file["name"])
        self._send(path.read_bytes(), content_type=file["content_type"], extra={"Content-Disposition": f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}"})


def serve(config: PortalConfig | None = None) -> None:
    active = config or PortalConfig.from_environment()
    ensure_schema(active)
    server = PortalHTTPServer((active.host, active.port), active)
    print(f"Portal público Llangón disponible en http://{active.host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    try:
        serve()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"No se pudo iniciar el portal público: {exc}", file=sys.stderr)
        raise SystemExit(1)
