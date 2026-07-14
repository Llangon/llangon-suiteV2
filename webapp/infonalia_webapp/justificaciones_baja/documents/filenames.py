"""Safe deterministic filenames and atomic, no-overwrite publication."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path


_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


class UnsafeDocumentPathError(ValueError):
    """Raised for traversal, relative output paths or unsafe components."""


def safe_component(value: object, *, maximum_length: int = 80) -> str:
    raw = unicodedata.normalize("NFKC", str(value).strip())
    if not raw:
        raise UnsafeDocumentPathError("El componente de nombre no puede estar vacío.")
    if ".." in raw:
        raise UnsafeDocumentPathError("No se admiten componentes con '..'.")
    cleaned = _INVALID_WINDOWS_CHARS.sub("_", raw)
    cleaned = _WHITESPACE.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
    if not cleaned:
        raise UnsafeDocumentPathError("El componente no contiene caracteres utilizables.")
    return cleaned[:maximum_length].rstrip(" ._")


def ensure_safe_output_directory(path: str | os.PathLike[str]) -> Path:
    raw = Path(path)
    if not raw.is_absolute():
        raise UnsafeDocumentPathError("La carpeta de salida debe ser absoluta.")
    if ".." in raw.parts:
        raise UnsafeDocumentPathError("La carpeta de salida no puede contener '..'.")
    resolved = raw.resolve(strict=False)
    resolved.mkdir(parents=True, exist_ok=True)
    if not resolved.is_dir():
        raise UnsafeDocumentPathError("La salida indicada no es una carpeta.")
    return resolved


def next_versioned_path(
    output_directory: str | os.PathLike[str],
    *,
    prefix: str,
    expediente: str,
    lot_number: str,
    suffix: str,
    version: int | None = None,
) -> tuple[Path, int]:
    directory = ensure_safe_output_directory(output_directory)
    safe_expediente = safe_component(expediente)
    safe_lot = safe_component(lot_number, maximum_length=40)
    safe_prefix = safe_component(prefix, maximum_length=40)
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    if normalized_suffix.lower() not in {".docx", ".xlsx"}:
        raise UnsafeDocumentPathError("La extensión documental no está permitida.")
    versions = (version,) if version is not None else range(1, 10_000)
    for candidate_version in versions:
        if not isinstance(candidate_version, int) or candidate_version < 1:
            raise UnsafeDocumentPathError("La versión debe ser un entero positivo.")
        filename = (
            f"{safe_prefix}_{safe_expediente}_Lote_{safe_lot}_"
            f"v{candidate_version:03d}{normalized_suffix.lower()}"
        )
        if len(filename) > 220:
            filename = (
                f"{safe_prefix}_{safe_expediente[:50]}_Lote_{safe_lot[:30]}_"
                f"v{candidate_version:03d}{normalized_suffix.lower()}"
            )
        candidate = directory / filename
        if candidate.parent != directory:
            raise UnsafeDocumentPathError("El nombre generado sale de la carpeta permitida.")
        if not candidate.exists():
            return candidate, candidate_version
    raise FileExistsError("No hay una versión documental libre.")


def temporary_output_path(final_path: Path) -> Path:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=f".{final_path.stem}_tmp_",
        suffix=final_path.suffix,
        dir=final_path.parent,
    )
    os.close(handle)
    return Path(name)


def publish_atomic_no_overwrite(completed_temp: Path, final_path: Path) -> None:
    """Publish a completed file atomically through an exclusive hard link."""

    completed_temp = completed_temp.resolve(strict=True)
    final_path = final_path.resolve(strict=False)
    if completed_temp.parent != final_path.parent:
        raise UnsafeDocumentPathError("El temporal debe estar en la carpeta final.")
    try:
        os.link(completed_temp, final_path)
    except FileExistsError:
        raise
    except OSError:
        # Conservative fallback: O_EXCL prevents overwriting. The write is
        # fsynced before the caller receives success.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(final_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as destination:
                with completed_temp.open("rb") as source:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                destination.flush()
                os.fsync(destination.fileno())
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
    finally:
        completed_temp.unlink(missing_ok=True)


__all__ = (
    "UnsafeDocumentPathError",
    "ensure_safe_output_directory",
    "next_versioned_path",
    "publish_atomic_no_overwrite",
    "safe_component",
    "temporary_output_path",
)
