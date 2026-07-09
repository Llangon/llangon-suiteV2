from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class DraftAttachment:
    path: Path
    name: str
    content_type: str = ""


@dataclass(frozen=True)
class DraftGenerationResult:
    ok: bool
    path: str
    file_format: str
    message: str
    warning: str = ""
    error: str = ""
    opened: bool = False


def _open_generated_file(path: Path, opener: Callable[[str], object] | None = None) -> tuple[bool, str]:
    open_with = opener or getattr(os, "startfile", None)
    if open_with is None:
        return False, "No hay un mecanismo disponible para abrir el borrador."
    try:
        open_with(str(path))
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _guess_content_type(path: Path, fallback: str = "") -> tuple[str, str]:
    content_type = fallback or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if "/" not in content_type:
        return "application", "octet-stream"
    return tuple(content_type.split("/", 1))  # type: ignore[return-value]


def _write_eml_draft(
    *,
    path: Path,
    to: str,
    subject: str,
    body: str,
    attachments: Sequence[DraftAttachment],
    opener: Callable[[str], object] | None = None,
    reason: str = "",
) -> DraftGenerationResult:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body or "")

    try:
        for attachment in attachments:
            maintype, subtype = _guess_content_type(attachment.path, attachment.content_type)
            message.add_attachment(
                attachment.path.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=attachment.name,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(message.as_bytes())
    except OSError as exc:
        return DraftGenerationResult(
            ok=False,
            path="",
            file_format="eml",
            message="No se pudo generar el borrador alternativo.",
            error=str(exc),
        )

    opened, open_error = _open_generated_file(path, opener=opener)
    warning_parts = ["Outlook COM no esta disponible; se ha generado un borrador .eml."]
    if reason:
        warning_parts.append(reason)
    if open_error:
        warning_parts.append(f"No se pudo abrir automaticamente: {open_error}")
    return DraftGenerationResult(
        ok=True,
        path=str(path),
        file_format="eml",
        message="Correo preparado generado en formato .eml.",
        warning=" ".join(part for part in warning_parts if part).strip(),
        opened=opened,
    )


def generate_outlook_draft(
    *,
    preferred_msg_path: Path,
    to: str,
    subject: str,
    body: str,
    attachments: Sequence[DraftAttachment],
    opener: Callable[[str], object] | None = None,
) -> DraftGenerationResult:
    try:
        from win32com.client import Dispatch  # type: ignore[import-not-found]
    except Exception as exc:
        return _write_eml_draft(
            path=preferred_msg_path.with_suffix(".eml"),
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            opener=opener,
            reason=str(exc),
        )

    try:
        preferred_msg_path.parent.mkdir(parents=True, exist_ok=True)
        outlook = Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        mail.Subject = subject
        mail.Body = body or ""
        for attachment in attachments:
            mail.Attachments.Add(str(attachment.path))
        mail.SaveAs(str(preferred_msg_path), 3)
    except Exception as exc:
        return _write_eml_draft(
            path=preferred_msg_path.with_suffix(".eml"),
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            opener=opener,
            reason=str(exc),
        )

    opened, open_error = _open_generated_file(preferred_msg_path, opener=opener)
    return DraftGenerationResult(
        ok=True,
        path=str(preferred_msg_path),
        file_format="msg",
        message="Correo Outlook generado.",
        warning=f"No se pudo abrir automaticamente: {open_error}" if open_error else "",
        opened=opened,
    )
