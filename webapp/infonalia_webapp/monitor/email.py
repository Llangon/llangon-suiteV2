"""Future email notification extension point.

Monitor V0 never sends emails.
"""

from __future__ import annotations


def prepare_monitor_emails(changes: list[dict[str, object]], *, dry_run: bool) -> dict[str, object]:
    return {
        "dry_run": dry_run,
        "emails_prepared_count": 0,
        "emails_sent_count": 0,
        "drafts": [],
        "changes_without_email_count": len(changes),
    }
