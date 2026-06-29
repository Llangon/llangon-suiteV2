from __future__ import annotations

import hashlib
from pathlib import Path


def hash_documents(documents: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda item: str(item.get("relative_path") or item.get("name") or "")):
        path = Path(str(document.get("path") or ""))
        name = str(document.get("relative_path") or document.get("name") or path.name)
        digest.update(name.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()

