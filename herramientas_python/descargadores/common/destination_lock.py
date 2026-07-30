"""Bloqueo local entre procesos para una carpeta documental de licitación."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DestinationBusyError(RuntimeError):
    """La carpeta ya está siendo modificada por otra operación local."""


def _pid_is_active(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_path(destination: Path, lock_root: Path | None) -> Path:
    root = lock_root or Path(tempfile.gettempdir()) / "llangon-suite-tender-locks"
    root.mkdir(parents=True, exist_ok=True)
    canonical = str(destination.resolve(strict=False)).casefold()
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return root / f"{key}.lock"


def _remove_abandoned_lock(path: Path, *, stale_after_seconds: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {}
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    if pid and _pid_is_active(pid):
        return False
    try:
        age = max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return True
    if pid or age >= max(1, stale_after_seconds):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return False
        return True
    return False


@contextmanager
def destination_lock(
    destination: Path | str,
    *,
    owner: str,
    stale_after_seconds: int = 4 * 60 * 60,
    lock_root: Path | None = None,
) -> Iterator[Path]:
    """Acquire an atomic same-host lock keyed by canonical destination path."""

    destination_path = Path(destination)
    path = _lock_path(destination_path, lock_root)
    token = uuid.uuid4().hex
    payload = {
        "token": token,
        "pid": os.getpid(),
        "owner": str(owner or "unknown"),
        "destination": str(destination_path.resolve(strict=False)),
        "created_at": time.time(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    acquired = False
    for _attempt in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _remove_abandoned_lock(path, stale_after_seconds=stale_after_seconds):
                continue
            raise DestinationBusyError(
                f"La carpeta está bloqueada por otra operación local: {destination_path}"
            )
        try:
            os.write(descriptor, encoded)
        finally:
            os.close(descriptor)
        acquired = True
        break
    if not acquired:
        raise DestinationBusyError(f"No se pudo adquirir el bloqueo local: {destination_path}")
    try:
        yield path
    finally:
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            current = {}
        if current.get("token") == token:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

