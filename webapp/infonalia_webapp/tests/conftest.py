from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def prevent_real_external_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never inherit production notification credentials in the test process."""

    monkeypatch.setenv("LLANGON_TESTING", "1")
    monkeypatch.delenv("LLANGON_TEST_ALLOW_REAL_TELEGRAM", raising=False)
