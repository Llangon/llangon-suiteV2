from __future__ import annotations

import json
from pathlib import Path

import pytest

from herramientas_python.descargadores.common.destination_lock import (
    DestinationBusyError,
    destination_lock,
)


def test_destination_lock_excludes_same_canonical_folder_and_releases(tmp_path: Path) -> None:
    destination = tmp_path / "licitacion"
    destination.mkdir()
    lock_root = tmp_path / "locks"

    with destination_lock(destination, owner="first", lock_root=lock_root) as lock_path:
        assert json.loads(lock_path.read_text(encoding="utf-8"))["owner"] == "first"
        with pytest.raises(DestinationBusyError):
            with destination_lock(destination / ".", owner="second", lock_root=lock_root):
                pass

    with destination_lock(destination, owner="third", lock_root=lock_root):
        pass


def test_destination_lock_recovers_abandoned_process(tmp_path: Path) -> None:
    destination = tmp_path / "licitacion"
    destination.mkdir()
    lock_root = tmp_path / "locks"
    with destination_lock(destination, owner="seed", lock_root=lock_root) as lock_path:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        payload["pid"] = 999_999_999
        lock_path.write_text(json.dumps(payload), encoding="utf-8")
        with destination_lock(destination, owner="recovered", lock_root=lock_root):
            pass
