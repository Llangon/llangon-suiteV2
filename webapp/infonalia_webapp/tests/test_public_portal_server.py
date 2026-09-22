from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.error
import urllib.request
import sqlite3

from public_portal_server.app import PortalConfig, PortalHTTPServer, ensure_schema
from webapp.infonalia_webapp.portal_publication.remote import publish_portal, rotate_portal_access_code, sync_portal_events
from webapp.infonalia_webapp.portal_publication.store import ensure_portal_schema, save_portal_draft


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _request(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        response = urllib.request.urlopen(request, timeout=5)
        return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_public_portal_access_download_and_event_trace_are_end_to_end(tmp_path) -> None:
    config = PortalConfig(
        host="127.0.0.1",
        port=0,
        db_path=tmp_path / "portal.db",
        files_root=tmp_path / "files",
        sync_secret="s" * 48,
        session_secret="c" * 48,
        public_base_url="https://licitaciones.llangon.es",
    )
    ensure_schema(config)
    server = PortalHTTPServer((config.host, 0), config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    code = "LL-ABCD-2345"
    salt = b"test-salt-for-portal"
    access_hash = _b64(hashlib.pbkdf2_hmac("sha256", code.encode(), salt, 210_000))
    publication = {
        "id": "pub-402",
        "slug": "l402-astursantina-test",
        "client_label": "Astursantina",
        "model": {"tender": {"title": "Suministro", "recipient": "Astursantina"}, "sections": [], "coverage": {"pages_total": 6, "pages_audited": 6}},
        "access_salt": _b64(salt),
        "access_hash": access_hash,
        "access_iterations": 210_000,
        "files": [{"id": "file-1", "name": "Pliego.pdf", "extension": "PDF", "size_bytes": 7, "content_type": "application/pdf"}],
    }
    auth = {"Authorization": f"Bearer {config.sync_secret}", "Content-Type": "application/json"}
    try:
        status, _, payload = _request(f"{base}/api/admin/publications", method="POST", body=json.dumps(publication).encode(), headers=auth)
        assert status == 200
        upload_path = json.loads(payload)["upload_files"][0]["path"]
        status, _, _ = _request(f"{base}{upload_path}", method="PUT", body=b"PDFDATA", headers={"Authorization": f"Bearer {config.sync_secret}", "Content-Type": "application/pdf"})
        assert status == 200
        status, _, _ = _request(f"{base}/api/admin/publications/pub-402/finalize", method="POST", body=b"{}", headers=auth)
        assert status == 200

        replacement_code = "LL-WXYZ-6789"
        replacement_salt = b"replacement-salt"
        replacement_hash = _b64(hashlib.pbkdf2_hmac("sha256", replacement_code.encode(), replacement_salt, 210_000))
        status, _, _ = _request(
            f"{base}/api/admin/publications/pub-402/access-code",
            method="POST",
            body=json.dumps({
                "access_salt": _b64(replacement_salt),
                "access_hash": replacement_hash,
                "access_iterations": 210_000,
            }).encode(),
            headers=auth,
        )
        assert status == 200

        status, _, _ = _request(f"{base}/api/portal/l402-astursantina-test")
        assert status == 401
        status, _, _ = _request(f"{base}/api/portal/l402-astursantina-test/access", method="POST", body=json.dumps({"code": code}).encode(), headers={"Content-Type": "application/json"})
        assert status == 401
        status, _, _ = _request(f"{base}/api/portal/l402-astursantina-test/access", method="POST", body=b'{"code":"incorrecta"}', headers={"Content-Type": "application/json"})
        assert status == 401
        status, response_headers, _ = _request(f"{base}/api/portal/l402-astursantina-test/access", method="POST", body=json.dumps({"code": replacement_code}).encode(), headers={"Content-Type": "application/json"})
        assert status == 200
        cookie = response_headers["Set-Cookie"].split(";", 1)[0]
        assert "HttpOnly" in response_headers["Set-Cookie"]
        assert "Secure" in response_headers["Set-Cookie"]

        status, _, payload = _request(f"{base}/api/portal/l402-astursantina-test", headers={"Cookie": cookie})
        assert status == 200
        assert json.loads(payload)["model"]["coverage"]["pages_audited"] == 6
        status, response_headers, payload = _request(f"{base}/api/portal/l402-astursantina-test/files/file-1", headers={"Cookie": cookie})
        assert status == 200
        assert payload == b"PDFDATA"
        assert "attachment" in response_headers["Content-Disposition"]

        status, _, payload = _request(f"{base}/api/admin/publications/pub-402/events", headers={"Authorization": f"Bearer {config.sync_secret}"})
        events = json.loads(payload)["items"]
        assert status == 200
        assert [event["event_type"] for event in events] == ["access", "download"]
        assert events[1]["file_name"] == "Pliego.pdf"
        assert events[0]["visitor_id"] == events[1]["visitor_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_rejects_non_loopback_binding(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLANGON_PUBLIC_PORTAL_HOST", "0.0.0.0")
    monkeypatch.setenv("LLANGON_PORTAL_SYNC_SECRET", "s" * 32)
    monkeypatch.setenv("LLANGON_PORTAL_SESSION_SECRET", "c" * 32)
    try:
        PortalConfig.from_environment()
    except RuntimeError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("El servidor no debe aceptar una escucha pública directa")


def test_suite_publish_and_event_sync_use_local_origin(tmp_path, monkeypatch) -> None:
    public_config = PortalConfig(
        host="127.0.0.1", port=0, db_path=tmp_path / "public.db", files_root=tmp_path / "public-files",
        sync_secret="z" * 48, session_secret="y" * 48, public_base_url="https://licitaciones.llangon.es",
    )
    ensure_schema(public_config)
    server = PortalHTTPServer((public_config.host, 0), public_config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    folder = tmp_path / "licitacion"
    folder.mkdir()
    (folder / "Ficha.pdf").write_bytes(b"FICHA")
    (folder / "Pliego.pdf").write_bytes(b"PLIEGO")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE licitaciones (id INTEGER PRIMARY KEY, ruta_carpeta TEXT)")
    conn.execute("INSERT INTO licitaciones VALUES (402, ?)", (str(folder),))
    ensure_portal_schema(conn)
    publication = save_portal_draft(
        conn, licitacion_id=402, ficha_relative_path="Ficha.pdf",
        model={"tender": {"recipient": "Cliente"}, "coverage": {"status": "preview_ready"}, "sections": []},
        selected_files=["Ficha.pdf", "Pliego.pdf"],
    )
    monkeypatch.setenv("LLANGON_PORTAL_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("LLANGON_PUBLIC_PORTAL_URL", "https://licitaciones.llangon.es")
    monkeypatch.setenv("LLANGON_PORTAL_SYNC_SECRET", public_config.sync_secret)
    monkeypatch.setattr("webapp.infonalia_webapp.portal_publication.remote.resolve_ai_source_folder", lambda _row: (folder, {}))
    try:
        result = publish_portal(conn, str(publication["id"]))
        assert result["status"] == "published"
        assert result["public_url"].startswith("https://licitaciones.llangon.es/p/")
        assert result["files_uploaded"] == 2
        code = str(publication["access_code"])
        slug = str(publication["slug"])
        status, headers, _ = _request(f"http://127.0.0.1:{server.server_port}/api/portal/{slug}/access", method="POST", body=json.dumps({"code": code}).encode(), headers={"Content-Type": "application/json"})
        assert status == 200
        previous_hash = conn.execute("SELECT access_hash FROM portal_publications WHERE id = ?", (publication["id"],)).fetchone()[0]
        rotated = rotate_portal_access_code(conn, str(publication["id"]))
        new_code = str(rotated["publication"]["access_code"])
        assert new_code.startswith("LL-") and new_code != code
        current_hash = conn.execute("SELECT access_hash FROM portal_publications WHERE id = ?", (publication["id"],)).fetchone()[0]
        assert current_hash != previous_hash
        status, _, _ = _request(f"http://127.0.0.1:{server.server_port}/api/portal/{slug}/access", method="POST", body=json.dumps({"code": code}).encode(), headers={"Content-Type": "application/json"})
        assert status == 401
        status, _, _ = _request(f"http://127.0.0.1:{server.server_port}/api/portal/{slug}/access", method="POST", body=json.dumps({"code": new_code}).encode(), headers={"Content-Type": "application/json"})
        assert status == 200
        # El acceso se sincroniza aunque todavía no se haya descargado ningún documento.
        synced = sync_portal_events(conn, str(publication["id"]))
        assert synced["events_inserted"] == 2
        assert conn.execute("SELECT event_type FROM portal_events").fetchone()[0] == "access"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
