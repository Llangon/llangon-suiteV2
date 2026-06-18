from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest

from webapp.infonalia_webapp.services.download_storage_service import (
    download_staging_root_for_backend,
    StorageConfigurationError,
    simulate_dropbox_dry_run,
    storage_config_from_env,
    storage_status_payload,
    test_dropbox_configuration as validate_dropbox_configuration,
)
from webapp.infonalia_webapp.tests.test_download_endpoint import make_download_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import VALID_CSRF_TOKEN, load_app_module


def test_dropbox_config_defaults_to_local_dry_run_without_secrets() -> None:
    payload = storage_status_payload({})

    assert payload["backend"] == "local"
    assert payload["current_mode_label"] == "local / Dropbox Desktop"
    assert payload["dropbox_enabled"] is False
    assert payload["dry_run"] is True
    assert payload["root"] == "/LlangonSuite"
    assert payload["non_destructive"] is True
    assert payload["dropbox_api_status"] == "experimental_disabled"
    assert payload["dropbox_api_recommended"] is False
    assert "APP_SECRET" not in str(payload)
    assert "REFRESH_TOKEN" not in str(payload)


def test_download_staging_root_is_used_only_for_dropbox_backend(tmp_path: Path) -> None:
    default_root = tmp_path / "data" / "descargas"

    assert download_staging_root_for_backend(tmp_path, default_root, {}) == default_root.resolve(strict=False)
    assert download_staging_root_for_backend(
        tmp_path,
        default_root,
        {"INFONALIA_STORAGE_BACKEND": "dropbox"},
    ) == (tmp_path / ".local_runtime" / "downloads").resolve(strict=False)
    assert download_staging_root_for_backend(
        tmp_path,
        default_root,
        {
            "INFONALIA_STORAGE_BACKEND": "dropbox",
            "INFONALIA_DOWNLOAD_STAGING_ROOT": str(tmp_path / "custom-staging"),
        },
    ) == (tmp_path / "custom-staging").resolve(strict=False)


def test_dropbox_enabled_without_credentials_fails_only_for_real_mode() -> None:
    env = {
        "INFONALIA_STORAGE_BACKEND": "dropbox",
        "INFONALIA_DROPBOX_ENABLED": "1",
        "INFONALIA_DROPBOX_DRY_RUN": "0",
    }

    config = storage_config_from_env(env)
    with pytest.raises(StorageConfigurationError, match="faltan credenciales"):
        config.validate_for_real_dropbox()


def test_dropbox_dry_run_endpoint_payload_has_no_tokens() -> None:
    payload = simulate_dropbox_dry_run(
        {
            "INFONALIA_STORAGE_BACKEND": "dropbox",
            "INFONALIA_DROPBOX_ENABLED": "1",
            "INFONALIA_DROPBOX_DRY_RUN": "1",
            "INFONALIA_DROPBOX_APP_SECRET": "super-secret",
            "INFONALIA_DROPBOX_REFRESH_TOKEN": "refresh-secret",
        }
    )

    assert payload["dry_run"] is True
    assert payload["files"][0]["status"] == "dry_run_upload"
    assert "super-secret" not in str(payload)
    assert "refresh-secret" not in str(payload)


def test_dropbox_test_configuration_dry_run_uses_no_network() -> None:
    payload = validate_dropbox_configuration(
        {
            "INFONALIA_STORAGE_BACKEND": "dropbox",
            "INFONALIA_DROPBOX_ENABLED": "1",
            "INFONALIA_DROPBOX_DRY_RUN": "1",
        }
    )

    assert payload["ok"] is True
    assert payload["network_checked"] is False


def test_storage_status_api_requires_admin_and_exposes_no_secrets(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setenv("INFONALIA_STORAGE_BACKEND", "dropbox")
    monkeypatch.setenv("INFONALIA_DROPBOX_ENABLED", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_DRY_RUN", "1")
    monkeypatch.setenv("INFONALIA_DROPBOX_APP_SECRET", "hidden")
    handler = make_download_handler(app, path="/api/storage/status")

    handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["backend"] == "dropbox"
    assert payload["dry_run"] is True
    assert payload["dropbox_api_status"] == "experimental_enabled"
    assert "hidden" not in str(payload)


def test_storage_status_api_shows_local_dropbox_desktop_as_main_flow(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    replica_root.mkdir(parents=True)
    monkeypatch.setenv("INFONALIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("INFONALIA_DROPBOX_ENABLED", "0")
    monkeypatch.setattr(app, "find_dropbox_root", lambda: replica_root)
    handler = make_download_handler(app, path="/api/storage/status")

    handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload["backend"] == "local"
    assert payload["current_mode_label"] == "local / Dropbox Desktop"
    assert payload["local_flow_label"] == "Dropbox Desktop"
    assert payload["dropbox_desktop_detected"] is True
    assert payload["dropbox_desktop_root"] == str(replica_root)
    assert payload["local_download_root"] == str(replica_root)
    assert payload["dropbox_api_status"] == "experimental_disabled"


def test_configured_dropbox_root_never_falls_back_to_real_dropbox(monkeypatch, tmp_path: Path) -> None:
    app = load_app_module()
    replica_root = tmp_path / "ReplicaDb"
    monkeypatch.setenv("INFONALIA_DROPBOX_ROOT", str(replica_root))

    assert app.find_dropbox_root() is None

    replica_root.mkdir()

    assert app.find_dropbox_root() == replica_root


def test_storage_dropbox_posts_require_csrf_before_running(monkeypatch) -> None:
    app = load_app_module()
    called = []
    monkeypatch.setattr(app, "test_dropbox_configuration", lambda: called.append(True) or {"ok": True})
    handler = make_download_handler(app, path="/api/storage/dropbox/test")

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.FORBIDDEN
    assert "CSRF" in payload["error"]
    assert called == []


def test_storage_dropbox_test_post_accepts_valid_csrf(monkeypatch) -> None:
    app = load_app_module()
    monkeypatch.setattr(app, "test_dropbox_configuration", lambda: {"ok": True, "network_checked": False})
    handler = make_download_handler(
        app,
        path="/api/storage/dropbox/test",
        csrf_token=VALID_CSRF_TOKEN,
    )

    handler.do_POST()

    status, payload = handler.responses[-1]
    assert status == HTTPStatus.OK
    assert payload == {"ok": True, "network_checked": False}
