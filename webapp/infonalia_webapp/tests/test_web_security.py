from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

from webapp.infonalia_webapp.web_security import (
    LoginRateLimiter,
    build_clear_cookie,
    build_content_security_policy,
    build_public_content_security_policy,
    build_security_headers,
    build_session_cookie,
    normalize_login_key,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
FIREBASE_ROOT = REPOSITORY_ROOT / "firebase" / "public_firebase"
FIREBASE_CONFIG = REPOSITORY_ROOT / "firebase.json"


def test_web_security_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.web_security", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.web_security")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_private_security_headers_include_basic_hardening() -> None:
    headers = build_security_headers(is_private=True)

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cache-Control"] == "no-store"
    assert headers["Content-Security-Policy"] == build_content_security_policy()


def test_private_content_security_policy_is_strict_and_self_hosted() -> None:
    policy = build_content_security_policy()

    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "style-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "base-uri 'self'" in policy
    assert "form-action 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy


def test_public_security_headers_apply_public_csp_without_private_cache() -> None:
    headers = build_security_headers(is_private=False)

    assert headers["Content-Security-Policy"] == build_public_content_security_policy()
    assert "Cache-Control" not in headers


def test_private_html_entrypoints_do_not_need_inline_scripts() -> None:
    for name in ("index.html", "login.html"):
        html = (STATIC_ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"<script(?!\s+src=)", html)
        assert "<style" not in html
        assert not re.search(r"<[^>]+\son[a-z]+\s*=", html)


def test_public_html_entrypoints_do_not_need_inline_scripts() -> None:
    for path in (STATIC_ROOT / "public.html", FIREBASE_ROOT / "index.html"):
        html = path.read_text(encoding="utf-8")
        assert 'data-private-app-url="' in html
        assert not re.search(r"<script(?!\s+src=)", html)
        assert "<style" not in html
        assert not re.search(r"<[^>]+\son[a-z]+\s*=", html)


def test_login_back_link_points_to_firebase_public_site() -> None:
    html = (STATIC_ROOT / "login.html").read_text(encoding="utf-8")

    assert 'class="ghost login-back-link"' in html
    assert 'href="/"' not in html
    assert 'href="https://llangon-web-publica-prueba.web.app/"' in html


def test_firebase_hosting_headers_include_public_csp() -> None:
    config = json.loads(FIREBASE_CONFIG.read_text(encoding="utf-8"))
    assert config["hosting"]["public"] == "firebase/public_firebase"
    headers = config["hosting"]["headers"]
    global_headers = next(entry["headers"] for entry in headers if entry["source"] == "**")
    header_map = {entry["key"]: entry["value"] for entry in global_headers}

    assert header_map["Content-Security-Policy"] == build_public_content_security_policy()
    assert header_map["X-Content-Type-Options"] == "nosniff"
    assert header_map["X-Frame-Options"] == "DENY"
    assert header_map["Referrer-Policy"] == "same-origin"


def test_public_js_escapes_dynamic_button_hrefs() -> None:
    for path in (STATIC_ROOT / "public.js", FIREBASE_ROOT / "static" / "public.js"):
        script = path.read_text(encoding="utf-8")
        assert "function safeHref" in script
        assert 'if (text.startsWith("//")) return "#";' in script
        assert '["http:", "https:"]' in script
        assert 'href="${escapeHtml(safeHref(href))}"' in script
        assert ">${escapeHtml(label)}</a>" in script
        assert 'href="${href}"' not in script


def test_private_app_normalize_url_rejects_unsafe_schemes() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function normalizeUrl" in script
    assert 'lower.startsWith("http://") || lower.startsWith("https://")' in script
    assert 'if (url.startsWith("//")) return "";' in script
    assert 'if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return "";' in script
    assert 'return `https://${url}`;' in script
    assert 'startsWith("mailto:")' not in script


def test_private_app_escapes_dynamic_data_attributes() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert not re.search(r'data-[a-z0-9-]+="\$\{(?:item|dia)\.id\}"', script)
    assert 'data-calendar-date="${key}"' not in script
    assert 'data-open-dia="${escapeHtml(dia.id)}"' in script
    assert 'data-calendar-date="${escapeHtml(key)}"' in script
    assert 'data-id="${escapeHtml(item.id)}"' in script
    assert 'data-download-id="${escapeHtml(item.id)}"' in script
    assert 'data-toggle-reviewed="${escapeHtml(item.id)}"' in script


def test_private_app_sanitizes_dynamic_css_class_tokens() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function cssClassToken" in script
    assert "function badgeClass" in script
    assert 'return cssClassToken(value, "Pendiente");' in script
    assert ".replace(/[^a-zA-Z0-9_-]+/g, \"-\")" in script
    assert ".replace(/^-+|-+$/g, \"\")" in script
    assert ".replaceAll(\" \", \"-\")" not in script


def test_agenda_layout_views_are_isolated() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert 'calendarSection.classList.add(`agenda-view-${appState.agendaView || "day"}`)' in script
    assert "function renderAgendaWeekList" in script
    assert "calendarDayPanel.innerHTML = \"\";" in script
    assert ".agenda-view-day .calendar-layout" in styles
    assert ".agenda-view-all .calendar-layout" in styles
    assert ".agenda-view-week .calendar-layout" in styles
    assert ".agenda-week-list-content" in styles


def test_licitaciones_center_ui_is_simplified_and_has_detail_view() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "Centro de licitaciones" in html
    assert 'data-licitaciones-view="live"' in html
    assert 'data-licitaciones-view="all"' in html
    assert 'data-licitaciones-view="active"' not in html
    assert 'id="summary" hidden' in html
    assert 'id="licitacion-detail-dialog"' in html
    assert "Detalle de trabajo" in html
    assert "PRÓXIMOS MÓDULOS" not in html
    assert "Clientes" not in html
    assert "Requerimientos" not in html
    assert 'data-open-licitacion-detail="${escapeHtml(item.id)}"' in script
    assert "function renderLicitacionDetailView" in script
    assert "data-detail-tab=\"resumen\"" in script
    assert "data-detail-tab-panel=\"documentos-seguimiento\"" in script
    assert "data-detail-tab-panel=\"comentarios\"" in script
    assert "data-document-filter" in script
    assert "renderCommentsWidget" in script
    assert "Copiar ruta" in script
    assert "Crear nueva actuación" in script
    assert "@media print" in styles
    assert ".detail-dialog[open]" in styles
    assert ".detail-cover" in styles
    assert ".detail-tabs" in styles
    assert ".document-card-list" in styles


def test_dropbox_marker_followup_ui_has_admin_only_safe_marker_controls() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="sync-dropbox-markers-button"' in html
    assert "/api/storage/markers/sync" in script
    assert "/markers/id" in script
    assert "/markers/follow" in script
    assert "/open-folder" in script
    assert "data-marker-action" in script
    assert "data-open-licitacion-folder" in script
    assert "${renderLicitacionTracking(item)}" in script
    assert "renderLicitacionMarkerActions(item, seguimiento)" in script
    assert 'if (!isAdmin()) return "";' in script
    assert "EnSeguimiento.llangon" in script
    assert "data-toggle-follow" not in script
    assert "data-delete-follow" not in script
    assert "data-tracking-notes-for" not in script
    assert "Marcar en seguimiento" not in script
    assert "Dejar de seguir" not in script


def test_licitacion_cards_and_detail_keep_hotfix_ux_noise_out() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    card_render = script.split("function renderCard", 1)[1].split("function renderExpandedCard", 1)[0]
    detail_render = script.split("function renderLicitacionDetailView", 1)[1].split("function renderLicitacionSummary", 1)[0]

    assert "estadoLabel(item.estado)" in card_render
    assert "dueText" in card_render
    assert "province-chip" in card_render
    assert "No revisada" not in card_render
    assert "Revisada" not in card_render
    assert "Nueva" not in card_render
    assert "En seguimiento" not in card_render
    assert "Documentación descargada" not in card_render
    assert "Sin descargar" not in card_render
    assert "Descarga fallida" not in card_render
    assert "footer-state" not in card_render
    assert "Ver detalles" not in card_render
    assert "const showEditButton = options.showEditButton ?? isAdmin();" in card_render
    assert 'showEditButton ? `<button data-edit-id="${escapeHtml(item.id)}">Editar</button>` : ""' in card_render
    assert "card-side-id" in card_render
    assert "ID ${escapeHtml(item.id)}" in card_render
    assert "Duplicar" not in card_render
    assert "Borrar" not in card_render
    assert ">Abrir</button>" in card_render
    assert "Crear nueva actuación" in card_render

    summary_render = detail_render.split('data-detail-tab-panel="resumen"', 1)[1].split('data-detail-tab-panel="actuaciones"', 1)[0]
    documents_render = detail_render.split('data-detail-tab-panel="documentos-seguimiento"', 1)[1].split('data-detail-tab-panel="comentarios"', 1)[0]
    comments_render = detail_render.split('data-detail-tab-panel="comentarios"', 1)[1].split('data-detail-tab-panel="ai"', 1)[0]

    assert "renderLicitacionDocuments(item)" not in summary_render
    assert "Ruta registrada" not in summary_render
    assert "Error descarga" not in summary_render
    assert "renderLicitacionDocuments(item)" not in documents_render
    assert "data-document-tree-panel" in documents_render
    assert "renderDocumentTreePayload" in script
    assert "/document-tree" in script
    assert "renderFolderPanel" in documents_render
    assert "renderDocumentSummary(item)" in documents_render
    assert "renderLicitacionTracking(item)" in documents_render
    assert "renderLicitacionHistory(item)" in documents_render
    assert 'renderCommentsWidget("licitacion", item.id, item.comments_summary, { full: true })' in comments_render
    assert "renderLicitacionWorkFields" not in detail_render
    assert "Notas internas" not in detail_render
    assert "Estado interno" not in detail_render
    assert "file:///" not in script


def test_nuria_day_review_filter_defaults_to_not_discarded() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "__nuria_active" in script
    assert "No descartadas" in script
    assert "__nuria_all" in script
    assert "Todas" in script
    assert "__nuria_discarded" in script
    assert "Descartadas" in script
    assert 'params.set("nuria_filter", option.filter)' in script
    assert 'if (diaId && isNuria()) stateFilter.value = "__nuria_active";' in script


def test_agenda_pending_tasks_ui_is_admin_only_and_initial_route_by_role() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'data-agenda-view="pending" data-admin-only hidden' in html
    assert "Tareas pendientes" in html
    assert "/api/agenda/pending-tasks" in script
    assert "function showInitialView" in script
    assert 'appState.agendaView = "pending";' in script
    assert "showCalendarView();" in script
    assert "showDaysView();" in script
    assert "select data-pending-state" in script
    assert "updatePendingTaskState" in script
    assert "function pendingLicitacionCardItem" in script
    assert "return renderCard(pendingLicitacionCardItem(item)" in script
    assert "pending-licitacion-card" in script
    assert "function renderPendingTaskCard" in script
    assert "pending-task-card" in script
    assert 'class="card-layout"' in script
    assert "card-side-actions" in script
    assert 'button[data-open-licitacion-detail]' in script
    assert 'button[data-edit-id]' in script
    assert "agendaDeepLinkToken" in script
    assert 'params.get("agenda_source")' in script
    assert "openAgendaOrigin(token)" in script


def test_private_app_has_mobile_drawer_shell() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert 'class="mobile-topbar"' in html
    assert 'id="mobile-menu-button"' in html
    assert 'aria-controls="app-sidebar"' in html
    assert 'id="sidebar-overlay"' in html
    assert 'id="app-sidebar" class="sidebar"' in html
    assert 'id="mobile-menu-close"' in html

    assert "function openSidebar" in script
    assert "function closeSidebar" in script
    assert "function toggleSidebar" in script
    assert 'document.body.classList.add("sidebar-open")' in script
    assert 'document.body.classList.remove("sidebar-open")' in script
    assert 'event.key === "Escape"' in script
    assert 'document.querySelectorAll(".sidebar [data-nav-section]")' in script

    assert ".mobile-topbar" in styles
    assert "body.sidebar-open .sidebar" in styles
    assert ".sidebar-overlay:not([hidden])" in styles
    assert "transform: translateX(-105%)" in styles
    assert "position: fixed;" in styles


def test_private_app_mobile_responsive_controls_stay_compact_without_horizontal_cutoff() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert 'id="notifications-menu-button"' in html
    assert 'class="section-title-block"' in html
    assert 'document.body.dataset.activeSection = section || "";' in script
    assert 'licitacionesSection.classList.toggle("has-day-context", Boolean(diaId));' in script

    assert "@media (max-width: 980px)" in styles
    assert "@media (max-width: 760px)" in styles
    assert "body[data-active-section=\"licitaciones\"] .topbar-actions" in styles
    assert "#licitaciones-section:not(.has-day-context) > .section-head .section-title-block" in styles
    assert "#calendar-section > .section-head .section-title-block" in styles
    assert "#actuaciones-section > .section-head .section-title-block" in styles
    assert ".filter-chip-scroll" in styles
    assert "flex-wrap: wrap;" in styles
    assert "overflow-x: visible;" in styles
    assert "#actuaciones-summary .metric" in styles


def test_desktop_layout_keeps_sidebar_topbar_fixed_and_scrolls_central_content() -> None:
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "@media (min-width: 981px)" in styles
    assert "body {\n    overflow: hidden;" in styles
    assert ".app-layout {\n    height: 100vh;" in styles
    assert ".main-area {\n    display: flex;" in styles
    assert "overflow: hidden;" in styles
    assert ".shell {\n    flex: 1 1 auto;" in styles
    assert "overflow-y: auto;" in styles


def test_monitor_history_ui_is_admin_only_and_inventory_ui_is_hidden() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="monitor-button" class="nav-item" data-nav-section="monitor" data-admin-only hidden' in html
    assert 'id="monitor-section" hidden' in html
    assert 'id="monitor-task-type-filter"' in html
    assert "Pendientes de Agenda" in html
    assert "Monitor licitaciones" in html
    assert "Resumen agenda" not in html
    assert "Agenda semanal" not in html
    assert "Aviso 7 días" not in html
    assert "Aviso 3 días" not in html
    assert "Aviso mañana" not in html
    assert "Aviso hoy" not in html
    assert 'id="monitor-send-agenda-daily"' in html
    assert 'id="monitor-send-agenda-summary"' not in html
    assert 'id="monitor-send-agenda-weekly"' not in html
    assert "Enviar correo diario de Pendientes de prueba" in html
    assert "Enviar resumen de agenda de prueba" not in html
    assert "Enviar agenda semanal de prueba" not in html
    assert 'id="monitor-runs-board"' in html
    assert 'id="monitor-run-detail"' in html
    assert 'id="monitor-inventory-button"' not in html
    assert "Inventariar carpetas" not in html
    assert "/api/monitor/runs" in script
    assert "function showMonitorView" in script
    assert "monitorTaskTypeLabels" in script
    assert 'params.set("task_type", monitorTaskTypeFilter.value)' in script
    assert "Elementos procesados" in script
    assert "function sendMonitorAgendaTask" in script
    assert '"agenda_pendientes_diaria"' in script
    assert 'sendMonitorAgendaTask(\n  monitorSendAgendaDailyButton,\n  "agenda_pendientes_diaria"' in script
    assert "schedule_key" in script
    assert "monitorInventoryButton" not in script
    assert "Ficheros inventariados" not in script
    assert "Sin documentación inventariada" not in script


def test_new_licitacion_platform_capture_ui_exists_and_preserves_manual_values() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="capture-platform-button"' in html
    assert "Capturar XML" in html
    assert 'id="capture-platform-result"' in html
    assert "Pega la URL XML del pliego" in script
    assert 'fetch("/api/licitaciones/capture"' in script
    assert "profile_url: profileUrlForCapture" in script
    assert "form.elements[target].value = value" in script
    assert "function isPlaceDocumentUrl" in script
    assert "shouldReplaceDocumentProfile" in script
    assert "currentValue && !shouldReplaceDocumentProfile" in script
    assert "campo ya tenía valor, no se ha sobrescrito" in script


def test_private_app_has_no_obvious_html_injection_patterns() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    lowered = script.lower()

    assert "insertadjacenthtml" not in lowered
    assert "outerhtml" not in lowered
    assert "document.write" not in lowered
    assert "javascript:" not in lowered
    assert not re.search(r"<script\b", script, re.IGNORECASE)
    assert not re.search(r"<style\b", script, re.IGNORECASE)
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", script, re.IGNORECASE)


def test_session_cookie_contains_expected_attributes() -> None:
    cookie = build_session_cookie("session", "token", max_age=60, secure=False)

    assert cookie.startswith("session=token")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=60" in cookie
    assert "Secure" not in cookie


def test_session_cookie_adds_secure_when_requested() -> None:
    cookie = build_session_cookie("session", "token", secure=True)

    assert "Secure" in cookie


def test_clear_cookie_expires_session_cookie() -> None:
    cookie = build_clear_cookie("session", secure=True)

    assert cookie.startswith("session=")
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie


def test_normalize_login_key_normalizes_username() -> None:
    assert normalize_login_key("127.0.0.1", "  Admin@Test.COM ") == "127.0.0.1|admin@test.com"


def test_rate_limiter_allows_attempts_below_limit() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)

    assert limiter.is_limited(key) is False


def test_rate_limiter_blocks_at_limit() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)

    assert limiter.is_limited(key) is True


def test_rate_limiter_clears_after_success() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=2, window_seconds=300, now=lambda: current_time)
    key = normalize_login_key("127.0.0.1", "admin")

    limiter.record_failure(key)
    limiter.record_failure(key)
    limiter.clear(key)

    assert limiter.is_limited(key) is False


def test_rate_limiter_separates_users_and_ips() -> None:
    current_time = 1000.0
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=300, now=lambda: current_time)
    admin_key = normalize_login_key("127.0.0.1", "admin")
    other_user_key = normalize_login_key("127.0.0.1", "other")
    other_ip_key = normalize_login_key("127.0.0.2", "admin")

    limiter.record_failure(admin_key)

    assert limiter.is_limited(admin_key) is True
    assert limiter.is_limited(other_user_key) is False
    assert limiter.is_limited(other_ip_key) is False
