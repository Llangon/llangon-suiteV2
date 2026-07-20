from __future__ import annotations

from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"


def test_monitor_ui_has_named_section_tabs_history_settings_and_manual_action() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "Monitor de licitaciones" in html
    assert 'id="tender-monitor-run-global"' in html
    assert 'data-tender-monitor-tab="overview"' in html
    assert 'data-tender-monitor-tab="history"' in html
    assert 'data-tender-monitor-tab="settings"' in html
    assert 'id="tender-monitor-history-filters"' in html
    assert 'name="date_from"' in html
    assert 'name="platform"' in html
    assert "/static/tender_monitor.js" in html
    assert "/static/tender_monitor.css" in html


def test_monitor_frontend_uses_csrf_and_exposes_safe_manual_retries() -> None:
    javascript = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")

    assert 'headers["X-CSRF-Token"]' in javascript
    assert "/api/tender-monitor/notifications/" in javascript
    assert "/api/tender-monitor/batches/" in javascript
    assert "/api/tender-monitor/executions/" in javascript
    assert "/api/tender-monitor/incident-reports/" in javascript
    assert "/rebuild-baseline" in javascript
    assert 'body: JSON.stringify({ active })' in javascript
    assert "setTimeout(() => loadDashboard" in javascript


def test_licitacion_detail_mounts_monitor_panel_without_parallel_follow_flag() -> None:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    monitor_js = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")

    assert "TenderMonitorUI?.renderTenderPanel" in app_js
    assert "Seguimiento y monitorización" in monitor_js
    assert "EnSeguimiento.llangon" in monitor_js
    assert "seguimiento_activo" not in monitor_js
