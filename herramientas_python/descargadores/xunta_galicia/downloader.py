"""Coordinación del descargador documental de Xunta de Galicia."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Mapping

from bs4 import BeautifulSoup

from ..common.http import create_public_session
from ..common.run_result import DownloadArtifact, DownloadRunResult, PlatformCapabilities, utc_now_iso
from . import browser as platform_browser
from .client import DownloadDescriptor, parse_tender_page, validate_detail_url
from .documents import XuntaCaptchaBlockedError, publish_download
from .state import load_state, record_for_descriptor, reusable_record, save_state, state_path


XUNTA_CAPABILITIES = PlatformCapabilities(documents=True, questions_and_answers=False)
PAGE_TIMEOUT = (10, 45)


def _artifact(descriptor: DownloadDescriptor, record: Mapping[str, object], path: Path, *, status: str) -> DownloadArtifact:
    return DownloadArtifact(
        name=path.name,
        status=status,
        source_url=descriptor.source_url,
        path=str(path),
        sha256=str(record.get("sha256") or ""),
        content_type=str(record.get("content_type") or ""),
        size=int(record.get("size") or 0),
        role="document",
    )


def run_xunta_galicia(
    url: str,
    destination: Path,
    *,
    session=None,
    browser_api=platform_browser,
    logger=print,
    started_at: str | None = None,
) -> DownloadRunResult:
    started = started_at or utc_now_iso()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    session = session or create_public_session()
    try:
        tender_id, canonical_url = validate_detail_url(url)
        logger(f"Consultando ficha pública de Xunta de Galicia: {canonical_url}")
        response = session.get(canonical_url, timeout=PAGE_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        response_url = str(getattr(response, "url", "") or canonical_url)
        page_data = parse_tender_page(BeautifulSoup(response.content, "html.parser"), response_url)
    except Exception as exc:
        return DownloadRunResult.failed(
            platform="XUNTA_DE_GALICIA",
            source_url=url,
            capabilities=XUNTA_CAPABILITIES,
            error=exc,
            started_at=started,
        )

    state, state_warnings = load_state(
        destination,
        tender_id=tender_id,
        source_url=page_data.source_url,
    )
    previous_documents = dict(state.get("documents") or {})
    previous_complete_keys = {
        str(key) for key in state.get("last_complete_keys", []) if str(key)
    }
    descriptors = {item.source_url: item for item in page_data.documents}
    artifacts: dict[str, DownloadArtifact] = {}
    resolved_records: dict[str, dict[str, object]] = {}
    unresolved: list[DownloadDescriptor] = []
    warnings = [*page_data.warnings, *state_warnings]
    issues: list[str] = []

    for descriptor in page_data.documents:
        reusable = reusable_record(
            previous_documents.get(descriptor.source_url),
            descriptor,
            destination=destination,
        )
        if reusable is None:
            unresolved.append(descriptor)
            continue
        record, path = reusable
        resolved_records[descriptor.source_url] = record
        artifacts[descriptor.source_url] = _artifact(descriptor, record, path, status="reused")

    logger(
        f"Documentos encontrados: {len(page_data.documents)}; "
        f"pendientes de descarga: {len(unresolved)}."
    )
    process = profile = browser = browser_page = None
    if unresolved:
        try:
            logger("Abriendo Chrome o Edge en segundo plano para las descargas protegidas...")
            process, profile, browser, port = browser_api.open_browser()
            with tempfile.TemporaryDirectory(prefix="llangon-xunta-download-") as click_directory:
                browser_page = browser_api.create_page(browser, port, click_directory)
                browser_api.navigate(browser_page, page_data.source_url)
                for index, descriptor in enumerate(unresolved, 1):
                    logger(f"[{index}/{len(unresolved)}] {descriptor.title}")
                    try:
                        temporary = browser_api.download_by_click(
                            browser_page,
                            descriptor.call,
                            click_directory,
                            expected_extension=descriptor.extension,
                        )
                        published = publish_download(temporary, descriptor, destination)
                        record = record_for_descriptor(
                            descriptor,
                            destination=destination,
                            path=published.path,
                            sha256=published.sha256,
                            content_type=published.content_type,
                            size=published.size,
                        )
                        resolved_records[descriptor.source_url] = record
                        artifacts[descriptor.source_url] = _artifact(
                            descriptor,
                            record,
                            published.path,
                            status="created" if published.written else "reused",
                        )
                        warnings.extend(published.warnings)
                    except XuntaCaptchaBlockedError as exc:
                        issues.append(f"{descriptor.title}: {exc}")
                        artifacts[descriptor.source_url] = DownloadArtifact(
                            name=descriptor.title,
                            status="failed",
                            source_url=descriptor.source_url,
                        )
                        break
                    except Exception as exc:
                        issues.append(f"{descriptor.title}: {exc}")
                        artifacts[descriptor.source_url] = DownloadArtifact(
                            name=descriptor.title,
                            status="failed",
                            source_url=descriptor.source_url,
                        )
        except Exception as exc:
            issues.append(str(exc))
        finally:
            if process and profile:
                browser_api.close_browser(process, profile, browser, browser_page)

    all_resolved = len(resolved_records) == len(page_data.documents)
    complete_run = page_data.complete and all_resolved and not issues
    working_documents = dict(previous_documents)
    working_documents.update(resolved_records)
    current_keys = set(descriptors)
    removed_keys = previous_complete_keys - current_keys if complete_run else set()
    new_keys = {
        key for key in current_keys - previous_complete_keys if key in resolved_records
    }
    modified_keys: set[str] = set()
    for key in current_keys & previous_complete_keys:
        previous = previous_documents.get(key)
        current = resolved_records.get(key)
        descriptor = descriptors[key]
        if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
            continue
        if (
            str(previous.get("descriptor_fingerprint") or "") != descriptor.fingerprint
            or str(previous.get("sha256") or "") != str(current.get("sha256") or "")
        ):
            modified_keys.add(key)

    state.update(
        {
            "schema_version": 1,
            "platform": "XUNTA_DE_GALICIA",
            "tender_id": tender_id,
            "source_url": page_data.source_url,
            "documents": (
                {key: resolved_records[key] for key in current_keys}
                if complete_run
                else working_documents
            ),
            "last_run_complete": complete_run,
            "last_run_at": utc_now_iso(),
            "last_issues": [*warnings, *issues],
        }
    )
    if complete_run:
        state["last_complete_keys"] = sorted(current_keys)
        state["last_complete_inventory_fingerprint"] = page_data.inventory_fingerprint
    try:
        saved_state_path = save_state(destination, state)
    except Exception as exc:
        issues.append(f"No se pudo guardar el estado técnico de Xunta: {exc}")
        complete_run = False
        saved_state_path = state_path(destination)

    for descriptor in page_data.documents:
        artifacts.setdefault(
            descriptor.source_url,
            DownloadArtifact(
                name=descriptor.title,
                status="failed",
                source_url=descriptor.source_url,
            ),
        )

    ordered_artifacts = [
        artifacts[item.source_url]
        for item in page_data.documents
        if item.source_url in artifacts
    ]
    if complete_run:
        status = "success"
    elif ordered_artifacts:
        status = "partial"
    else:
        status = "failed"
    created = [item.path for item in ordered_artifacts if item.status == "created" and item.path]
    reused = [item.path for item in ordered_artifacts if item.status == "reused" and item.path]
    error = "; ".join(issues or warnings) if status == "failed" else ""
    logger(
        f"Descarga Xunta finalizada: {len(created)} creado(s), {len(reused)} reutilizado(s), "
        f"{len(issues)} incidencia(s)."
    )
    return DownloadRunResult(
        platform="XUNTA_DE_GALICIA",
        tender_id=tender_id,
        source_url=page_data.source_url,
        started_at=started,
        finished_at=utc_now_iso(),
        status=status,
        capabilities=XUNTA_CAPABILITIES,
        changes_detected=bool(new_keys or modified_keys or removed_keys),
        general_data=page_data.general_data,
        relevant_dates=page_data.relevant_dates,
        documents_found=len(page_data.documents),
        documents_downloaded=len(created),
        documents_new=len(new_keys),
        documents_modified=len(modified_keys),
        documents_removed=len(removed_keys),
        artifacts=ordered_artifacts,
        files_created=created,
        files_reused=reused,
        state_path=str(saved_state_path),
        warnings=list(dict.fromkeys(warnings)),
        recoverable_issues=issues,
        error=error,
        block_completeness={"documents": "complete" if complete_run else "partial"},
    )
