from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Iterable, Mapping

try:
    from ..dropbox_paths import preferred_dropbox_base_path
except ImportError:  # pragma: no cover
    from dropbox_paths import preferred_dropbox_base_path


QUESTION_DOCUMENT_PREFIX = "Preguntas y respuestas a fecha "
ATTACHABLE_DOCUMENT_CHANGES = {"document_new", "document_modified", "document_restored"}
QUESTION_CHANGES = {"question_new", "question_modified", "question_restored"}
DEFAULT_EMAIL_ATTACHMENT_LIMIT_BYTES = 17 * 1024 * 1024


def folder_name(value: object) -> str:
    raw = str(value or "").strip().rstrip("\\/")
    return PureWindowsPath(raw).name if raw else ""


def _safe_file(folder: Path, relative: object) -> Path | None:
    text = str(relative or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = folder / candidate
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(folder.resolve(strict=True))
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _question_state(folder: Path) -> dict[str, object]:
    candidates = sorted(folder.glob(".llangon-*/questions_state.json"))
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("questions"), dict):
            return payload
    return {}


def _question_document(folder: Path) -> Path | None:
    candidates = [
        path
        for suffix in (".docx", ".rtf")
        for path in folder.glob(f"{QUESTION_DOCUMENT_PREFIX}*{suffix}")
        if path.is_file()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def notification_files_and_differences(
    folder_value: object,
    differences: Iterable[Mapping[str, object]],
) -> tuple[list[Path], list[dict[str, object]]]:
    """Resolve only files belonging to this batch and enrich question labels.

    The result can be rebuilt during a notification retry without downloading or
    changing monitor state.
    """
    rows = [dict(item) for item in differences]
    folder_text = str(folder_value or "").strip()
    folder = Path(folder_text) if folder_text else None
    if folder and not folder.is_absolute():
        base = preferred_dropbox_base_path()
        folder = base / folder if base else folder
    if not folder or not folder.is_dir():
        return [], rows

    state = _question_state(folder)
    questions = state.get("questions") if isinstance(state.get("questions"), dict) else {}
    attachments: list[Path] = []
    has_question_change = False
    for row in rows:
        change_type = str(row.get("change_type") or "").strip().casefold()
        if change_type in ATTACHABLE_DOCUMENT_CHANGES:
            value = row.get("new_value") if isinstance(row.get("new_value"), Mapping) else {}
            path = _safe_file(folder, value.get("relative_path"))
            if path:
                attachments.append(path)
        if change_type not in QUESTION_CHANGES:
            continue
        has_question_change = True
        key = str(row.get("item_key") or "")
        question = questions.get(key) if isinstance(questions, dict) else None
        if not isinstance(question, Mapping):
            continue
        versions = question.get("versions") if isinstance(question.get("versions"), list) else []
        latest = versions[-1] if versions and isinstance(versions[-1], Mapping) else {}
        number = question.get("number") or ""
        row["title"] = f"Pregunta o respuesta {number}".strip()
        row["question_text"] = str(question.get("question") or latest.get("question") or "").strip()
        row["answer_text"] = str(question.get("answer") or latest.get("answer") or "").strip()
        row["question_number"] = int(question.get("number") or 0)
        row["official_datetime"] = str(
            question.get("official_datetime") or question.get("answered_at") or latest.get("answered_at") or ""
        ).strip()
        raw_attachments = question.get("attachments") or latest.get("attachments") or []
        row["question_attachments"] = [
            {
                "name": str(item.get("name") or "").strip(),
                "source_id": str(item.get("source_id") or item.get("id") or "").strip(),
                "url": str(item.get("url") or item.get("source_url") or "").strip(),
            }
            for item in raw_attachments
            if isinstance(item, Mapping) and str(item.get("name") or "").strip()
        ]

    if has_question_change:
        document = _question_document(folder)
        if document:
            attachments.append(document)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in attachments:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique, rows


def select_email_attachments(
    attachments: Iterable[Path],
    *,
    limit_bytes: int = DEFAULT_EMAIL_ATTACHMENT_LIMIT_BYTES,
) -> tuple[list[Path], list[dict[str, object]]]:
    """Keep the message below a conservative SMTP limit.

    MIME/base64 expands binary files by roughly one third, so the default raw
    payload is deliberately below the usual 25 MB provider limit.
    """
    candidates: list[tuple[Path, int]] = []
    skipped: list[dict[str, object]] = []
    for path in attachments:
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"name": path.name, "size": 0, "reason": "unavailable"})
            continue
        candidates.append((path, size))
    if sum(size for _path, size in candidates) <= limit_bytes:
        return [path for path, _size in candidates], skipped

    selected: list[Path] = []
    used = 0
    for path, size in sorted(candidates, key=lambda item: (item[1], item[0].name.casefold())):
        if size <= limit_bytes - used:
            selected.append(path)
            used += size
        else:
            skipped.append({"name": path.name, "size": size, "reason": "size_limit"})
    selected_set = {str(path).casefold() for path in selected}
    selected = [path for path, _size in candidates if str(path).casefold() in selected_set]
    return selected, skipped
