from __future__ import annotations

import logging
import logging.handlers
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .environment import load_env_file


APP_ROOT = Path(__file__).resolve().parent
WEBAPP_ROOT = APP_ROOT.parent
PROJECT_ROOT = WEBAPP_ROOT.parent
ENV_PATH = APP_ROOT / ".env"

RUNTIME_ROOT_ENV = "LLANGON_RUNTIME_ROOT"
DEFAULT_LOCK_STALE_SECONDS = 2 * 60 * 60


def load_deployment_env() -> None:
    load_env_file(ENV_PATH)


def runtime_root() -> Path:
    configured = os.environ.get(RUNTIME_ROOT_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (PROJECT_ROOT / "runtime").resolve()


def logs_dir() -> Path:
    return runtime_root() / "logs"


def locks_dir() -> Path:
    return runtime_root() / "locks"


def default_backup_dir() -> Path:
    return runtime_root() / "backups" / "sqlite"


def ensure_runtime_dirs() -> None:
    for directory in (logs_dir(), locks_dir(), default_backup_dir()):
        directory.mkdir(parents=True, exist_ok=True)


def rotating_log_path(file_name: str) -> Path:
    ensure_runtime_dirs()
    return logs_dir() / file_name


def setup_rotating_logger(name: str, file_name: str, *, level: int = logging.INFO) -> logging.Logger:
    path = rotating_log_path(file_name)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    existing_paths = {
        Path(getattr(handler, "baseFilename", "")).resolve()
        for handler in logger.handlers
        if getattr(handler, "baseFilename", "")
    }
    if path.resolve() not in existing_paths:
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


class AlreadyRunningError(RuntimeError):
    pass


@dataclass
class FileLock:
    name: str
    stale_seconds: int = DEFAULT_LOCK_STALE_SECONDS

    def __post_init__(self) -> None:
        ensure_runtime_dirs()
        self.path = locks_dir() / f"{self.name}.lock"
        self._fd: int | None = None

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def acquire(self) -> None:
        self._remove_stale_lock()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            self._fd = os.open(str(self.path), flags)
        except FileExistsError as exc:
            raise AlreadyRunningError(f"Proceso ya en ejecucion: {self.name}") from exc
        payload = f"pid={os.getpid()}\ncreated_at={time.time():.0f}\n"
        os.write(self._fd, payload.encode("ascii", errors="ignore"))

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _remove_stale_lock(self) -> None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return
        if self.stale_seconds <= 0:
            return
        if time.time() - stat.st_mtime > self.stale_seconds:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

