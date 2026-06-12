from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

try:
    from .msg_parsing import extract_hora_limite_from_text, extract_tipo_contrato
    from .normalization import clean_text
    from .url_helpers import normalize_url
except ImportError:
    from msg_parsing import extract_hora_limite_from_text, extract_tipo_contrato
    from normalization import clean_text
    from url_helpers import normalize_url


Downloader = Callable[[str, Path], bool]
TextReader = Callable[[Path], str]
ClockNs = Callable[[], int]


def find_pdftotext_path(
    project_root: Path,
    app_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    env = environ if environ is not None else os.environ
    configured = clean_text(env.get("INFONALIA_PDFTOTEXT"))
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            project_root / "pdftotext.exe",
            app_root / "pdftotext.exe",
            (home or Path.home()) / "Dropbox" / "00000 LLANGON" / "Infonalia" / "pdftotext.exe",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def download_to_path(
    url: str,
    destination: Path,
    *,
    opener: Callable[..., Any] = urlrequest.urlopen,
) -> bool:
    try:
        req = urlrequest.Request(
            normalize_url(url),
            headers={"User-Agent": "Mozilla/5.0 InfonaliaWeb"},
        )
        with opener(req, timeout=30) as response:
            destination.write_bytes(response.read())
        return destination.exists() and destination.stat().st_size > 0
    except Exception:
        return False


def pdf_file_to_text(
    pdf_path: Path,
    pdftotext_path: Path | None,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> str:
    if not pdftotext_path:
        return ""
    txt_path = pdf_path.with_suffix(".txt")
    try:
        runner(
            [str(pdftotext_path), "-layout", str(pdf_path), str(txt_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def enrich_from_pdf_url(
    url: str,
    fecha_limite: str,
    *,
    temp_dir: Path,
    downloader: Downloader,
    text_reader: TextReader,
    clock_ns: ClockNs = time.time_ns,
) -> dict[str, str]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = temp_dir / f"infonalia_{clock_ns()}.pdf"
    if not downloader(url, pdf_path):
        return {}
    texto = text_reader(pdf_path)
    return {
        "tipo": extract_tipo_contrato(texto),
        "hora_limite": extract_hora_limite_from_text(texto, fecha_limite),
    }
