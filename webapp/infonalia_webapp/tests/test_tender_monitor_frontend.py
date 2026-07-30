from __future__ import annotations

import subprocess
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
    assert 'id="tender-monitor-search"' in html
    assert 'name="date_from"' in html
    assert 'name="platform"' in html
    assert "/static/tender_monitor.js" in html
    assert "/static/tender_monitor.css" in html


def test_monitor_and_automation_console_are_separate_admin_views() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    monitor = html.split('<section id="monitor-section" hidden>', 1)[1].split(
        '<section id="automation-section" hidden>', 1
    )[0]
    automation = html.split('<section id="automation-section" hidden>', 1)[1].split(
        '<section id="config-section" hidden>', 1
    )[0]

    assert 'id="automation-button"' in html
    assert 'data-nav-section="automation"' in html
    assert 'id="tender-monitor-root"' in monitor
    assert 'id="automation-tasks-board"' not in monitor
    assert 'id="automation-tasks-board"' in automation
    assert 'id="monitor-runs-board"' in automation
    assert "function showAutomationView()" in javascript
    assert 'setActiveNav("automation")' in javascript


def test_monitor_mobile_layout_uses_labeled_cards_and_touch_sized_controls() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")
    styles = (STATIC / "tender_monitor.css").read_text(encoding="utf-8")

    assert "/static/tender_monitor.css?v=20260723-detail-priority" in html
    assert "/static/tender_monitor.js?v=20260723-detail-priority" in html
    assert 'data-label="Expediente"' in javascript
    assert 'data-label="Acciones"' in javascript
    assert 'data-label="Procesadas"' in javascript
    assert "content: attr(data-label);" in styles
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in styles
    assert "#monitor-section > .section-head" in styles
    assert "#automation-section > .section-head" in styles
    assert "min-height: 44px;" in styles
    assert "max-height: none;" in styles
    assert "min-height: 64px;" in styles


def test_monitor_summary_is_reduced_and_search_filters_each_monitor_view() -> None:
    javascript = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")

    summary = javascript.split("target.innerHTML = `", 1)[1].split("`;", 1)[0]
    assert summary.count('class="tender-monitor-card"') == 4
    assert "Preparadas" not in summary
    assert "Errores" not in summary
    assert "(cycle?.error_count || 0) + (cycle?.incident_count || 0)" in summary
    assert "function applySearch()" in javascript
    assert "renderFollowed();" in javascript
    assert "renderHistory();" in javascript
    assert "renderSettings(state.settings);" in javascript


def test_monitor_history_uses_lazy_inline_cycle_details_on_mobile() -> None:
    javascript = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")
    styles = (STATIC / "tender_monitor.css").read_text(encoding="utf-8")

    assert 'data-tm-cycle-details="${escapeHtml(item.id)}"' in javascript
    assert 'root?.addEventListener("toggle"' in javascript
    assert 'loadCycleDetail(details.dataset.tmCycleDetails, target);' in javascript
    assert 'if (cycle && window.matchMedia("(max-width: 640px)").matches) return;' in javascript
    assert ".tender-monitor-cycle-inline-detail" in styles
    assert ".tender-monitor-history-layout > .tender-monitor-detail" in styles
    assert "min-height: 42px;" in styles


def test_cycle_detail_prioritizes_incidents_and_collapses_tenders() -> None:
    javascript = (STATIC / "tender_monitor.js").read_text(encoding="utf-8")

    detail = javascript.split("function renderCycleDetail", 1)[1].split("async function loadCycleDetail", 1)[0]
    assert detail.index("<h4>Incidencias</h4>") < detail.index('class="tender-monitor-cycle-tenders"')
    assert '<summary>Licitaciones (${escapeHtml(executions.length)})</summary>' in detail


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


def test_tender_panel_lifecycle_does_not_refetch_on_internal_mutations() -> None:
    test_script = Path(__file__).with_name("tender_monitor_panel_lifecycle.mjs")
    completed = subprocess.run(
        ["node", str(test_script)],
        cwd=STATIC.parents[2],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "tender monitor panel lifecycle: ok" in completed.stdout
