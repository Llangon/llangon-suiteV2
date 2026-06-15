from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DROPBOX_API_URL = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_URL = "https://content.dropboxapi.com/2"
DROPBOX_OAUTH_URL = "https://api.dropboxapi.com/oauth2/token"


class DropboxClientError(RuntimeError):
    """Raised for Dropbox API errors."""


@dataclass(frozen=True)
class DropboxCredentials:
    app_key: str
    app_secret: str
    refresh_token: str


class DropboxHttpClient:
    """Minimal Dropbox API client used only outside tests.

    The client intentionally exposes no delete, overwrite, or destructive move
    operations. Uploads use Dropbox mode "add" with autorename disabled.
    """

    def __init__(self, credentials: DropboxCredentials, *, timeout: int = 30) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self._access_token: str | None = None

    def _token(self) -> str:
        if self._access_token:
            return self._access_token

        body = urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.credentials.refresh_token,
            }
        ).encode("utf-8")
        raw_auth = f"{self.credentials.app_key}:{self.credentials.app_secret}".encode("utf-8")
        request = Request(
            DROPBOX_OAUTH_URL,
            data=body,
            headers={
                "Authorization": f"Basic {base64.b64encode(raw_auth).decode('ascii')}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise DropboxClientError(f"Dropbox OAuth error {exc.code}") from exc
        except OSError as exc:
            raise DropboxClientError(f"Dropbox OAuth connection error: {exc}") from exc

        token = str(payload.get("access_token") or "")
        if not token:
            raise DropboxClientError("Dropbox OAuth response did not include access_token.")
        self._access_token = token
        return token

    def _api_json(self, endpoint: str, payload: dict) -> dict:
        request = Request(
            f"{DROPBOX_API_URL}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                content = response.read().decode("utf-8")
        except HTTPError:
            raise
        except OSError as exc:
            raise DropboxClientError(f"Dropbox API connection error: {exc}") from exc
        return json.loads(content or "{}")

    def get_metadata(self, path: str) -> dict:
        try:
            return self._api_json("/files/get_metadata", {"path": path, "include_deleted": False})
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 409 and "not_found" in body:
                raise FileNotFoundError(path) from exc
            raise DropboxClientError(f"Dropbox metadata error {exc.code}") from exc

    def path_exists(self, path: str) -> bool:
        try:
            self.get_metadata(path)
            return True
        except FileNotFoundError:
            return False

    def ensure_folder(self, path: str) -> dict:
        if self.path_exists(path):
            return {"status": "reused_existing", "path": path}
        try:
            metadata = self._api_json("/files/create_folder_v2", {"path": path, "autorename": False})
            return {"status": "created", "path": path, "metadata": metadata}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 409 and "conflict" in body:
                return {"status": "reused_existing", "path": path}
            raise DropboxClientError(f"Dropbox create folder error {exc.code}") from exc

    def _upload_bytes_if_missing(self, content: bytes, dropbox_path: str) -> dict:
        if self.path_exists(dropbox_path):
            return {
                "status": "skipped_existing",
                "path": dropbox_path,
                "upload_mode": "add",
                "autorename": False,
            }

        api_arg = {
            "path": dropbox_path,
            "mode": {".tag": "add"},
            "autorename": False,
            "mute": True,
            "strict_conflict": False,
        }
        request = Request(
            f"{DROPBOX_CONTENT_URL}/files/upload",
            data=content,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(api_arg),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                metadata = json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 409 and "conflict" in body:
                return {
                    "status": "skipped_existing",
                    "path": dropbox_path,
                    "upload_mode": "add",
                    "autorename": False,
                }
            raise DropboxClientError(f"Dropbox upload error {exc.code}") from exc
        except OSError as exc:
            raise DropboxClientError(f"Dropbox upload connection error: {exc}") from exc

        return {
            "status": "uploaded",
            "path": dropbox_path,
            "metadata": metadata,
            "upload_mode": "add",
            "autorename": False,
        }

    def upload_file_if_missing(self, local_path: Path, dropbox_path: str) -> dict:
        return self._upload_bytes_if_missing(Path(local_path).read_bytes(), dropbox_path)

    def upload_stream_if_missing(self, stream: BinaryIO, dropbox_path: str) -> dict:
        content = stream.read()
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self._upload_bytes_if_missing(bytes(content), dropbox_path)


def bytes_stream(content: bytes) -> BinaryIO:
    return BytesIO(content)

