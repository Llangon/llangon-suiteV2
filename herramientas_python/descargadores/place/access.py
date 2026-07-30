"""Resolución local de credenciales para la fachada operativa de PLACE."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


PLACE_USER_ENV = "PLACE_USUARIO"
PLACE_PASSWORD_ENV = "PLACE_CONTRASENA"
DEFAULT_SUITE_DB_PATH = (
    Path(__file__).resolve().parents[3]
    / "webapp"
    / "infonalia_webapp"
    / "data"
    / "infonalia.db"
)


def credenciales_place_desde_suite(db_path=None):
    path = Path(db_path or DEFAULT_SUITE_DB_PATH).resolve(strict=False)
    if not path.is_file():
        return "", ""
    uri = f"{path.as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            rows = connection.execute(
                "SELECT key, value FROM app_settings "
                "WHERE key IN ('place_username', 'place_password')"
            ).fetchall()
    except (OSError, sqlite3.Error):
        return "", ""
    settings = {str(key): str(value or "") for key, value in rows}
    return settings.get("place_username", "").strip(), settings.get("place_password", "")


def resolver_credenciales_place(usuario=None, contrasena=None, *, db_path=None):
    if usuario is not None or contrasena is not None:
        return str(usuario or "").strip(), str(contrasena or "")
    env_user = os.environ.get(PLACE_USER_ENV, "").strip()
    env_password = os.environ.get(PLACE_PASSWORD_ENV, "")
    if env_user or env_password:
        return env_user, env_password
    return credenciales_place_desde_suite(db_path)

