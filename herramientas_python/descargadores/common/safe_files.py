"""Nombres y escritura local segura, independientes de la plataforma remota."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, TypeAlias
from urllib.parse import unquote

from .errors import QuestionStateError, SafeFileError


OUTPUT_DATETIME_FORMAT = "%Y-%m-%d %H-%M-%S"


@dataclass(frozen=True)
class SafeWriteResult:
    path: Path | None
    written: bool
    skipped: bool = False
    sha256: str = ""


@dataclass(frozen=True)
class TextDocumentOutput:
    """Contrato sencillo para registrar otro renderizador de texto."""

    format_name: str
    extension: str
    encoding: str
    render: Callable[[Any], str]
    validator: Callable[[str], None]


@dataclass(frozen=True)
class BinaryDocumentOutput:
    """Contrato para formatos documentales binarios, como DOCX."""

    format_name: str
    extension: str
    render: Callable[[Any], bytes]
    validator: Callable[[bytes], None]


DocumentOutput: TypeAlias = TextDocumentOutput | BinaryDocumentOutput
DocumentContent: TypeAlias = str | bytes


def sanitize_filename(
    name: object,
    *,
    fallback: str = "documento",
    max_length: int | None = None,
) -> str:
    text = unquote(str(name or ""))
    text = re.sub(r'[\\/*?:"<>|\n\r\t]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .") or fallback
    if max_length is None or len(text) <= max_length:
        return text
    suffix = Path(text).suffix
    base_limit = max(1, max_length - len(suffix))
    return text[:base_limit].rstrip(" .") + suffix


def ensure_safe_child(parent: Path, candidate: Path) -> Path:
    parent_resolved = Path(parent).resolve(strict=False)
    candidate_resolved = Path(candidate).resolve(strict=False)
    try:
        candidate_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise SafeFileError("La ruta de salida queda fuera de la carpeta permitida.") from exc
    return candidate_resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_matches_bytes(path: Path, content: bytes) -> bool:
    """Compara el contenido real sin confiar en una huella criptográfica."""

    path = Path(path)
    try:
        if path.stat().st_size != len(content):
            return False
        offset = 0
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                if chunk != content[offset : offset + len(chunk)]:
                    return False
                offset += len(chunk)
        return offset == len(content)
    except OSError:
        return False


def mark_hidden(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        hidden = 0x2
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attributes != -1:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attributes | hidden)
    except (AttributeError, OSError):
        return


def mark_visible(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        hidden = 0x2
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attributes != -1 and attributes & hidden:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attributes & ~hidden)
    except (AttributeError, OSError):
        return


def replace_with_retry(source: Path, target: Path, *, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except OSError:
            if attempt + 1 >= attempts:
                raise
            time.sleep(0.15 * (attempt + 1))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    ensure_safe_child(path.parent, temporary)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        replace_with_retry(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def unique_dated_path(
    destination: Path,
    prefix: str,
    extension: str,
    generated_at: datetime,
) -> tuple[Path, datetime]:
    destination = Path(destination).resolve()
    normalized_extension = "." + extension.lstrip(".")
    timestamp = generated_at
    while True:
        candidate = destination / f"{prefix}{timestamp.strftime(OUTPUT_DATETIME_FORMAT)}{normalized_extension}"
        ensure_safe_child(destination, candidate)
        if not candidate.exists():
            return candidate, timestamp
        timestamp += timedelta(seconds=1)


def write_text_temporary(
    directory: Path,
    content: str,
    *,
    extension: str,
    encoding: str,
    validator: Callable[[str], None] | None = None,
) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "." + extension.lstrip(".")
    temporary = directory / f".document-{uuid.uuid4().hex}{suffix}.tmp"
    ensure_safe_child(directory, temporary)
    try:
        with temporary.open("x", encoding=encoding, newline="") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if validator:
            validator(temporary.read_text(encoding=encoding))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def write_bytes_temporary(
    directory: Path,
    content: bytes,
    *,
    extension: str,
    validator: Callable[[bytes], None] | None = None,
) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "." + extension.lstrip(".")
    temporary = directory / f".document-{uuid.uuid4().hex}{suffix}.tmp"
    ensure_safe_child(directory, temporary)
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if validator:
            validator(temporary.read_bytes())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def write_document_temporary(
    directory: Path,
    content: DocumentContent,
    *,
    output: DocumentOutput,
) -> Path:
    """Escribe y valida un temporal según el contrato de salida."""

    if isinstance(output, BinaryDocumentOutput):
        if not isinstance(content, bytes):
            raise TypeError("El renderizador binario no devolvió bytes.")
        return write_bytes_temporary(
            directory,
            content,
            extension=output.extension,
            validator=output.validator,
        )
    if not isinstance(content, str):
        raise TypeError("El renderizador de texto no devolvió texto.")
    return write_text_temporary(
        directory,
        content,
        extension=output.extension,
        encoding=output.encoding,
        validator=output.validator,
    )


def read_document_content(path: Path, output: DocumentOutput) -> DocumentContent:
    if isinstance(output, BinaryDocumentOutput):
        return Path(path).read_bytes()
    return Path(path).read_text(encoding=output.encoding)


def document_content_sha256(content: DocumentContent, output: DocumentOutput) -> str:
    if isinstance(output, BinaryDocumentOutput):
        if not isinstance(content, bytes):
            raise TypeError("El contenido binario no está expresado como bytes.")
        material = content
    else:
        if not isinstance(content, str):
            raise TypeError("El contenido textual no está expresado como texto.")
        material = content.encode(output.encoding)
    return hashlib.sha256(material).hexdigest()


def write_bytes_if_absent(destination: Path, filename: str, content: bytes) -> SafeWriteResult:
    """Guarda bytes ya obtenidos, sin conocer HTTP ni la plataforma."""

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    target = ensure_safe_child(destination, destination / sanitize_filename(filename))
    if target.exists():
        return SafeWriteResult(path=None, written=False, skipped=True)
    temporary = destination / f".{target.name}.{uuid.uuid4().hex}.tmp"
    ensure_safe_child(destination, temporary)
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if target.exists():
            return SafeWriteResult(path=None, written=False, skipped=True)
        os.rename(temporary, target)
        mark_visible(target)
        return SafeWriteResult(path=target, written=True, sha256=sha256_file(target))
    except OSError as exc:
        raise SafeFileError(f"No se pudo guardar el archivo «{target.name}».") from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_bytes_content_aware(destination: Path, filename: str, content: bytes) -> SafeWriteResult:
    """Publica bytes sin sobrescribir y solo omite contenidos idénticos."""

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    digest = hashlib.sha256(content).hexdigest()
    target = ensure_safe_child(destination, destination / safe_name)
    if target.is_file():
        if file_matches_bytes(target, content):
            return SafeWriteResult(path=target, written=False, skipped=True, sha256=digest)
        base, suffix = os.path.splitext(target.name)
        collision_index = 1
        while True:
            collision_label = digest[:10]
            if collision_index > 1:
                collision_label += f"-{collision_index}"
            candidate = ensure_safe_child(
                destination,
                destination / f"{base} [{collision_label}]{suffix}",
            )
            if not candidate.exists():
                target = candidate
                break
            if candidate.is_file() and file_matches_bytes(candidate, content):
                return SafeWriteResult(path=candidate, written=False, skipped=True, sha256=digest)
            collision_index += 1
    temporary = destination / f".{target.name}.{uuid.uuid4().hex}.tmp"
    ensure_safe_child(destination, temporary)
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if target.exists():
            if target.is_file() and file_matches_bytes(target, content):
                return SafeWriteResult(path=target, written=False, skipped=True, sha256=digest)
            raise SafeFileError(f"El destino «{target.name}» apareció durante la escritura.")
        os.rename(temporary, target)
        mark_visible(target)
        return SafeWriteResult(path=target, written=True, sha256=digest)
    except SafeFileError:
        raise
    except OSError as exc:
        raise SafeFileError(f"No se pudo guardar el archivo «{target.name}».") from exc
    finally:
        temporary.unlink(missing_ok=True)


def commit_document_and_state(
    *,
    destination: Path,
    technical_directory: Path,
    state_path: Path,
    journal_path: Path,
    state: dict[str, Any],
    content: DocumentContent,
    target: Path,
    output: DocumentOutput,
) -> None:
    """Publica documento y estado con diario recuperable, sin sobrescribir."""

    destination = Path(destination).resolve()
    target = ensure_safe_child(destination, target)
    technical_directory.mkdir(parents=True, exist_ok=True)
    temporary = write_document_temporary(technical_directory, content, output=output)
    journal = {
        "target_name": target.name,
        "temporary_name": temporary.name,
        "document_format": output.format_name,
        "document_extension": output.extension,
        "state": state,
    }
    renamed = False
    try:
        atomic_write_json(journal_path, journal)
        if target.exists():
            raise FileExistsError(target)
        os.rename(temporary, target)
        renamed = True
        mark_visible(target)
        output.validator(read_document_content(target, output))
        atomic_write_json(state_path, state)
        journal_path.unlink(missing_ok=True)
    except Exception as exc:
        if not renamed:
            temporary.unlink(missing_ok=True)
            journal_path.unlink(missing_ok=True)
        raise SafeFileError(
            "No se pudo completar de forma atómica la escritura del documento y su estado técnico."
        ) from exc


def recover_document_transaction(
    *,
    destination: Path,
    technical_directory: Path,
    state_path: Path,
    journal_path: Path,
    output: DocumentOutput,
    state_validator: Callable[[object], dict[str, Any]],
) -> bool:
    """Recupera una publicación interrumpida sin conocer su formato concreto."""

    if not journal_path.is_file():
        return False
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionStateError("No se pudo leer la transacción documental pendiente.") from exc
    target_name = str(journal.get("target_name") or "")
    expected_suffix = "." + output.extension.lstrip(".").casefold()
    if Path(target_name).name != target_name or not target_name.casefold().endswith(expected_suffix):
        raise QuestionStateError("La transacción pendiente contiene una ruta no válida.")
    target = ensure_safe_child(destination, Path(destination) / target_name)
    state_payload = state_validator(journal.get("state"))
    temporary_name = Path(str(journal.get("temporary_name") or "")).name
    temporary = technical_directory / temporary_name if temporary_name else None
    if target.is_file():
        output.validator(read_document_content(target, output))
        atomic_write_json(state_path, state_payload)
        journal_path.unlink(missing_ok=True)
        if temporary and temporary.exists():
            temporary.unlink()
        return True
    if temporary and temporary.exists():
        temporary.unlink()
    journal_path.unlink(missing_ok=True)
    return False


def publish_document(
    *,
    destination: Path,
    technical_directory: Path,
    content: DocumentContent,
    target: Path,
    output: DocumentOutput,
) -> SafeWriteResult:
    """Publica un documento validado sin sobrescribir ni modificar el estado."""

    destination = Path(destination).resolve()
    target = ensure_safe_child(destination, target)
    temporary = write_document_temporary(technical_directory, content, output=output)
    renamed = False
    try:
        if target.exists():
            raise FileExistsError(target)
        os.rename(temporary, target)
        renamed = True
        mark_visible(target)
        output.validator(read_document_content(target, output))
        return SafeWriteResult(
            path=target,
            written=True,
            sha256=sha256_file(target),
        )
    except Exception as exc:
        raise SafeFileError(f"No se pudo publicar el documento «{target.name}».") from exc
    finally:
        if not renamed:
            temporary.unlink(missing_ok=True)
