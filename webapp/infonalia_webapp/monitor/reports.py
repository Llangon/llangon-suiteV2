from __future__ import annotations

import json
from typing import Any


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": report.get("task_type", "licitaciones"),
        "mode": report.get("mode"),
        "dry_run": report.get("dry_run"),
        "root_path": report.get("root_path"),
        "status": report.get("status"),
        "year_roots_count": len(report.get("year_roots", [])),
        "found_markers_count": report.get("found_markers_count", 0),
        "processed_items_count": report.get("processed_items_count", 0),
        "route_updates_count": report.get("route_updates_count", 0),
        "followed_count": report.get("followed_count", 0),
        "folders_checked_count": report.get("folders_checked_count", 0),
        "folders_repaired_count": report.get("folders_repaired_count", 0),
        "folders_broken_count": report.get("folders_broken_count", 0),
        "platforms_checked_count": report.get("platforms_checked_count", 0),
        "changes_detected_count": report.get("changes_detected_count", 0),
        "emails_prepared_count": report.get("emails_prepared_count", 0),
        "emails_sent_count": report.get("emails_sent_count", 0),
        "conflicts_count": len(report.get("conflicts", [])),
        "warnings_count": len(report.get("warnings", [])),
    }


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
