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


def test_private_app_javascript_url_is_versioned_to_avoid_stale_initial_view() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert re.search(r'<script src="/static/app\.js\?v=[^"]+"></script>', html)


def test_actuaciones_view_omits_total_cards() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="actuaciones-summary"' not in html
    assert "actuacionesSummary" not in script
    assert "renderActuacionesSummary" not in script
    assert "function renderMetric([label, value])" in script


def test_public_html_entrypoints_do_not_need_inline_scripts() -> None:
    html = (FIREBASE_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-private-app-url="' in html
    assert not re.search(r"<script(?!\s+src=)", html)
    assert "<style" not in html
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", html)


def test_private_static_tree_does_not_keep_public_site_copy() -> None:
    removed_public_files = [
        STATIC_ROOT / "public.html",
        STATIC_ROOT / "public.css",
        STATIC_ROOT / "public.js",
        STATIC_ROOT / "assets" / "public-hero-procurement.png",
    ]

    assert not any(path.exists() for path in removed_public_files)


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
    script = (FIREBASE_ROOT / "static" / "public.js").read_text(encoding="utf-8")
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
    assert 'data-calendar-date="${escapeHtml(item.date || "sin-fecha")}"' in script
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


def test_agenda_unified_calendar_precedes_tasks_and_has_side_navigation() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert 'calendarSection.classList.add("agenda-view-pending")' in script
    assert 'data-agenda-view' not in html
    assert 'id="agenda-email-summary-button"' not in html
    assert "sendAgendaEmailSummary" not in script
    compact_calendar_render = script.split("function renderCompactCalendarCells", 1)[1].split("function renderAgendaMonth", 1)[0]
    assert 'class="calendar-event-count"' in compact_calendar_render
    assert "dayItems.length" in compact_calendar_render
    assert 'dayItems.length ? "" : "no-items"' in compact_calendar_render
    assert ".calendar-day.no-items" in styles
    assert 'class="calendar-events"' not in compact_calendar_render
    assert "renderCalendarEvent" not in script
    assert "min-height: 72px;" in styles
    pending_render = script.split("function renderAgendaPending", 1)[1].split("function renderAgendaAll", 1)[0]
    assert 'class="pending-agenda-calendar"' in pending_render
    assert 'class="agenda-legend pending-agenda-legend"' in pending_render
    assert '<section class="agenda-legend">' not in html
    assert 'data-pending-calendar-date' in pending_render
    assert pending_render.index("pending-agenda-calendar") < pending_render.index('renderAgendaListPanel("", ""')
    assert 'renderAgendaListPanel("Tareas pendientes", "Lista de trabajo"' not in pending_render
    assert "#calendar-section > .section-head" in styles
    assert "renderCompactCalendarCells(calendarGroups" in pending_render
    assert 'data-calendar-nav="prev"' in pending_render
    assert 'data-calendar-nav="today"' in pending_render
    assert 'data-calendar-nav="next"' in pending_render
    assert 'data-new-agenda-event' in pending_render
    assert 'id="new-agenda-event-button"' not in html
    assert 'class="agenda-search-field"' in html
    assert '<summary>Buscar</summary>' not in html
    assert 'pendingListHeading.after(agendaUnifiedToolbar)' in script
    assert 'document.activeElement === calendarSearch' in pending_render
    assert 'calendarSearch.focus({ preventScroll: true });' in pending_render
    assert pending_render.index('pendingListHeading.after(agendaUnifiedToolbar)') < pending_render.index('calendarSearch.focus({ preventScroll: true });')
    assert 'calendarSearch.setSelectionRange(' in pending_render
    assert 'event.target.closest("button[data-new-agenda-event]")' in script
    assert 'data-calendar-show-all' in pending_render
    assert '<span class="pending-calendar-nav-label">Navegación</span>' in pending_render
    assert '<span class="pending-calendar-nav-label">Filtro</span>' in pending_render
    assert pending_render.index('data-calendar-nav="next"') < pending_render.index('data-calendar-nav="today"')
    assert 'appState.calendarSelectedDate = "";' in script
    show_calendar_view = script.split("function showCalendarView()", 1)[1].split("function ", 1)[0]
    assert 'appState.calendarSelectedDate = "";' in show_calendar_view
    assert "todayKey" not in show_calendar_view
    assert 'dateKey(eventDate) === selectedKey' in pending_render
    assert "monthName(previousMonth)" in pending_render
    assert "monthName(nextMonth)" in pending_render
    assert 'aria-label="Anterior: ${escapeHtml(monthTitle(previousMonth))}"' in pending_render
    assert 'aria-label="Siguiente: ${escapeHtml(monthTitle(nextMonth))}"' in pending_render
    assert "function navigateUnifiedAgendaCalendar(action)" in script
    assert ".pending-agenda-calendar" in styles
    assert ".agenda-view-pending .calendar-layout" in styles
    assert "grid-template-columns: minmax(0, 1fr) 224px;" in styles
    assert "grid-template-columns: minmax(0, 1fr) 86px;" in styles
    assert "overflow-x: visible;" in styles
    assert "min-width: 560px;" not in styles
    assert 'id="back-to-days"' not in html
    assert 'id="current-day-title"' not in html
    assert "currentDayTitle" not in script
    assert "#licitaciones-section:not(.has-day-context) > .section-head" in styles
    assert "body:has(#licitaciones-section:not([hidden])) #ai-queue-button" in styles
    assert "#days-section > .section-head .section-title-block" in styles
    assert 'id="days-summary"' not in html
    assert "renderDaysSummary" not in script
    assert "function renderDeadlineText(value)" in script
    assert "hours > 12 || (hours === 12 && minutes > 0)" in script
    assert 'class="early-deadline-time"' in script
    assert ".early-deadline-time" in styles
    assert ".mobile-compact-card .province-chip" in styles
    assert "background: #218c4f;" in styles
    assert ".mobile-compact-card .mobile-card-actions > button.primary" in styles
    assert "background: #e8f5ec;" in styles
    assert 'class="badge card-state-badge ${badgeClass(item.estado)}"' in script
    assert ".mobile-compact-card .card-flags > *" in styles
    assert ".mobile-compact-card .card-flags > .card-state-badge" in styles
    assert ".mobile-compact-card .card-head > .card-flags" in styles
    assert "padding-right: min(42%, 120px);" in styles


def test_private_search_boxes_submit_only_on_enter() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    helper = script.split("function submitSearchOnEnter", 1)[1].split("function ", 1)[0]

    assert '/static/app.js?v=20260730-pc-restart' in html
    assert 'input?.addEventListener("keydown"' in helper
    assert 'event.key !== "Enter"' in helper
    assert "event.isComposing" in helper
    assert "event.preventDefault();" in helper
    assert "search();" in helper
    for input_name, loader_name in (
        ("searchInput", "loadItems"),
        ("calendarSearch", "loadCalendarItems"),
        ("notificationSearch", "loadNotifications"),
        ("clientSearch", "loadClientes"),
        ("clienteEnviosSearch", "loadClienteEnvios"),
        ("licitacionSelectorSearch", "loadLicitacionSelectorResults"),
    ):
        assert f"submitSearchOnEnter({input_name}, {loader_name});" in script
        assert f'{input_name}.addEventListener("input"' not in script
        assert f'{input_name}?.addEventListener("input"' not in script


def test_infonalia_history_ui_is_admin_only_high_contrast_and_searches_on_enter() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    render = script.split("function renderInfonaliaHistoryEvent", 1)[1].split(
        "function renderInfonaliaHistory()", 1
    )[0]

    assert 'data-nuria-days-view="history" data-admin-only' in html
    assert 'id="infonalia-history" class="infonalia-history" data-admin-only' in html
    assert 'id="infonalia-history-tab-badge"' in html
    assert 'id="infonalia-history-filters"' in html
    assert 'placeholder="Expediente, organismo o texto · Enter"' in html
    assert 'infonaliaHistoryFilters?.addEventListener("submit"' in script
    assert 'infonaliaHistoryQuery?.addEventListener("input"' not in script
    assert "escapeHtml(item.title" in render
    assert "escapeHtml(item.detail)" in render
    assert "context.map((value) => `<span>${escapeHtml(value)}</span>`" in render
    assert ".history-event.severity-attention" in styles
    assert ".history-event.severity-critical" in styles
    assert "border-left-color: #b42318" in styles
    assert ".history-event.is-reviewed" in styles


def test_licitaciones_center_ui_is_simplified_and_has_detail_view() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "Centro de licitaciones" in html
    assert 'data-licitaciones-view="live"' in html
    assert 'data-licitaciones-view="all"' in html
    assert 'data-licitaciones-view="previous">Anuncios previos</button>' in html
    assert 'data-licitaciones-view="active"' not in html
    assert 'id="publication-type-filter"' not in html
    assert 'id="summary" hidden' in html
    assert 'id="licitacion-detail-dialog"' in html
    assert 'id="licitacion-detail-actions"' in html
    assert html.index('id="licitacion-detail-actions"') < html.index('id="close-licitacion-detail"')
    assert "Detalle de trabajo" in html
    assert "PRÓXIMOS MÓDULOS" not in html
    assert '<p class="nav-group-title" data-admin-only hidden>Clientes</p>' in html
    assert 'id="clients-button"' in html
    assert 'id="cliente-envios-button"' in html
    assert 'data-nav-section="cliente-envios"' in html
    assert "Requerimientos" not in html
    assert 'data-open-licitacion-detail="${escapeHtml(item.id)}"' in script
    assert 'appState.licitacionesView === "previous" ? "anuncio_previo" : "licitacion"' in script
    assert 'appState.licitacionesView !== "previous" && appState.licitacionesYear' in script
    assert 'appState.licitacionesView !== "previous" && appState.licitacionesMonth' in script
    assert 'const showFilters = !appState.currentDiaId && appState.licitacionesView !== "previous";' in script
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
    assert ".detail-cover-side" in styles
    assert "grid-template-columns: minmax(360px, 1fr) 190px;" in styles
    assert ".detail-dialog-actions" in styles
    assert "flex-wrap: nowrap;" in styles
    assert "background: #f2f4f7;" in styles
    assert "border: 1px solid #d0d5dd;" in styles
    assert ".detail-tabs" in styles
    assert ".document-card-list" in styles


def test_all_tenders_tab_resets_year_and_month_filters() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    handler = script.split('licitacionesTabs.addEventListener("click", (event) => {', 1)[1].split(
        'licitacionesYearFilters.addEventListener("click", (event) => {', 1
    )[0]

    assert 'if (appState.licitacionesView === "all") {' in handler
    assert 'appState.licitacionesYear = "Todos";' in handler
    assert 'appState.licitacionesMonth = "Todos";' in handler


def test_news_module_remains_integrated_but_hidden_from_suite_navigation() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="news-admin-button" class="nav-item" data-nav-section="news-admin" data-admin-only data-feature-disabled hidden' in html
    assert 'id="news-admin-section" hidden' in html
    assert 'element.hasAttribute("data-feature-disabled")' in script
    assert "function showNewsAdminView" in script
    assert 'fetch("/api/news")' in script


def test_cliente_envios_list_has_confirmed_admin_delete_action() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert 'data-delete-cliente-envio="${escapeHtml(envio.id)}"' in script
    assert "async function deleteClienteEnvio(envioId)" in script
    assert "no los archivos de Dropbox ni el correo preparado" in script
    assert "await afterClienteEnvioMutation(result.item);" in script


def test_client_management_uses_table_modal_and_reversible_status_actions() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    clients_section = html.split('<section id="clients-section" hidden>', 1)[1].split(
        '<dialog id="client-dialog"', 1
    )[0]
    assert 'id="client-form"' not in clients_section
    assert 'id="clients-state-filter"' in clients_section
    assert '<table class="clients-table">' in clients_section
    for heading in ("NIF/CIF", "Razón social", "Nombre comercial", "Teléfono", "Email", "Estado", "Acciones"):
        assert f"<th>{heading}</th>" in clients_section
    assert 'id="client-dialog"' in html
    assert 'id="client-form"' in html
    assert "clientesGestion: []" in script
    assert 'fetch("/api/clientes?estado=activos")' in script
    assert 'params.set("estado", estado)' in script
    assert "function operationalClientOptions" in script
    assert "items.push({ ...currentClient, id: selectedValue, activo: false })" in script
    assert 'populateActuacionClientOptions(item.cliente_id || "", item.cliente)' in script
    assert "activo: item.cliente_activo" in script
    assert 'data-client-status="${client.activo ? "desactivar" : "reactivar"}"' in script
    assert "¿Desactivar a ${clientName}?" in script
    assert ".clients-table td::before" in styles
    assert "content: attr(data-label);" in styles


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
    assert "renderDocumentosTabActions(item, folder)" in script
    assert '${isAdmin() ? `<button type="button" data-marker-action="id"' in script
    assert '${isAdmin() ? `<button type="button" data-marker-action="follow"' in script
    assert "EnSeguimiento.llangon" in script
    assert "data-toggle-follow" not in script
    assert "data-delete-follow" not in script
    assert "data-tracking-notes-for" not in script
    assert "Marcar en seguimiento" not in script
    assert "Dejar de seguir" not in script


def test_licitacion_cards_and_detail_keep_hotfix_ux_noise_out() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    card_render = script.split("function renderCard", 1)[1].split("function renderExpandedCard", 1)[0]
    actuacion_render = script.split("function renderActuacionCard", 1)[1].split("function setSelectedActuacionLicitaciones", 1)[0]
    detail_render = script.split("function renderLicitacionDetailView", 1)[1].split("function renderLicitacionSummary", 1)[0]
    detail_cover_render = detail_render.split('<section class="detail-cover">', 1)[1].split("</section>", 1)[0]
    detail_actions_render = script.split("function renderDetailActionBar", 1)[1].split("function renderLicitacionSummary", 1)[0]

    assert "estadoLabel(item.estado)" in card_render
    assert 'renderExpandableDescription(item.objeto || "Sin objeto informado", "object")' in card_render
    assert 'renderExpandableDescription(item.descripcion, "muted actuacion-description")' in actuacion_render
    assert "function renderExpandableDescription" in script
    assert "function syncExpandableDescriptions" in script
    assert 'text.scrollHeight > text.clientHeight + 1' in script
    assert "MutationObserver(scheduleExpandableDescriptionSync)" in script
    assert ".expandable-description-text" in styles
    assert ".expandable-description.has-overflow .expandable-description-toggle" in styles
    assert "-webkit-line-clamp: 2;" in styles
    assert 'content: "Ver más";' in styles
    assert 'content: "Ver menos";' in styles
    assert "dueText" in card_render
    assert "const dueBadge = remainingDays === null" in card_render
    assert '<div class="deadline-value">${renderDeadlineText(fechaLimite || "Sin fecha")}${dueBadge}</div>' in card_render
    assert '<div class="mobile-deadline"><span>Vencimiento</span><strong>${renderDeadlineText(fechaLimite || "Sin fecha")}</strong>${dueBadge}</div>' in card_render
    assert card_render.index("card-flags") < card_render.index("${dueBadge}")
    assert "province-chip" in card_render
    assert "flex: 0 0 auto;" in styles
    assert "flex-wrap: wrap;" in styles
    assert "card-object-line" in card_render
    assert card_render.index("<h2>${escapeHtml(item.expediente)}</h2>") < card_render.index("province-chip")
    assert card_render.index("province-chip") < card_render.index('renderExpandableDescription(item.objeto || "Sin objeto informado", "object")')
    assert card_render.index("province-chip") < card_render.index("card-flags")
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
    assert 'const reviewStateActions = stateActionButtons.length' in card_render
    assert 'const reviewClass = stateActionButtons.length ? " has-review-actions" : "";' in card_render
    assert 'class="review-state-actions"' in card_render
    assert "...stateActionButtons" not in card_render
    assert card_render.count("${reviewStateActions}") == 2
    assert ".review-state-actions" in styles
    assert ".mobile-compact-card:not(.has-review-actions) > .card-layout" in styles
    assert "@media (min-width: 761px)" in styles
    assert ".card-folder-path::before" in styles
    assert ".comments-widget:not(.comments-widget-full):has(.comments-thread:not([hidden]))" in styles
    assert '<div class="mobile-deadline"><span>Vencimiento</span>' in card_render
    assert '<div class="mobile-deadline"><span>Vencimiento</span>' in actuacion_render
    assert ".mobile-compact-card .mobile-deadline" in styles

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
    assert "renderDocumentosTabActions(item, folder)" in documents_render
    assert "renderLicitacionTrackingSummary(item)" in documents_render
    assert "renderLicitacionHistory(item)" in documents_render
    assert 'renderCommentsWidget("licitacion", item.id, item.comments_summary, { full: true })' in comments_render
    assert "renderLicitacionWorkFields" not in detail_render
    assert 'renderExpandableDescription(item.objeto || "Sin objeto informado", "detail-cover-object")' in detail_cover_render
    assert "Presupuesto" not in detail_cover_render
    assert '["Presupuesto", formatMoney(item.presupuesto)]' in detail_render
    assert detail_cover_render.index("Fecha límite") < detail_cover_render.index("estadoLabel(item.estado)")
    assert detail_cover_render.index("estadoLabel(item.estado)") < detail_cover_render.index("renderAiSummaryBadge(item)")
    assert detail_cover_render.index("renderAiSummaryBadge(item)") < detail_cover_render.index("Carpeta:")
    assert "Descargar documentación" not in detail_actions_render
    assert "Envíos a clientes" not in detail_actions_render
    assert "renderCreateClienteEnvioButton" not in detail_actions_render
    assert "licitacionDetailActions.innerHTML = renderDetailActionBar" in script
    assert 'licitacionDetailActions.addEventListener("click"' in script
    assert 'class="detail-more-actions detail-actions-menu"' in detail_actions_render
    assert 'aria-label="Más acciones"' in detail_actions_render
    assert "☰" in detail_actions_render
    assert "Notas internas" not in detail_render
    assert "Estado interno" not in detail_render
    assert "file:///" not in script


def test_detail_actions_always_use_menu_and_mobile_menu_keeps_a_usable_width() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    detail_actions_render = script.split("function renderDetailActionBar", 1)[1].split("function renderLicitacionSummary", 1)[0]

    assert "if (actions.length === 1)" not in detail_actions_render
    assert 'class="detail-more-actions detail-actions-menu"' in detail_actions_render
    assert ".detail-actions-menu[open] .detail-more-menu" in styles
    assert "min-width: 180px;" in styles


def test_new_actuacion_title_is_suggested_from_type_client_alias_and_folder() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function actuacionTitleFolderParts(item)" in script
    assert "function suggestedActuacionTitle()" in script
    assert "function updateSuggestedActuacionTitle()" in script
    assert "clientIndex = yearIndex > 0 ? yearIndex - 1" in script
    assert 'folderLabel: parts.at(-1)' in script
    assert 'folderLabel: parts.slice(folderStart).join(" ")' not in script
    assert '[typeLabel, clientAlias, folderLabel].filter(Boolean).join(" ")' in script
    assert "titleInput.value !== previousSuggestion" in script
    assert 'actuacionForm.elements.tipo.addEventListener("change", updateSuggestedActuacionTitle)' in script


def test_actuacion_form_has_optional_cliente_selector_for_create_and_edit() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "Cliente (opcional)" in html
    assert '<select name="cliente_id">' in html
    assert '<option value="">Sin cliente</option>' in html
    assert "function populateActuacionClientOptions" in script
    assert 'populateActuacionClientOptions(item.cliente_id || "", item.cliente)' in script
    assert "cliente_id: actuacionForm.elements.cliente_id.value || null" in script


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


def test_agenda_unified_pending_view_is_available_to_nuria() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "data-agenda-view" not in html
    assert 'id="calendar-search"' in html
    assert 'id="calendar-state-filter"' not in html
    assert "calendarStateFilter" not in script
    assert 'class="toolbar calendar-toolbar agenda-unified-toolbar"' in html
    assert "grid-template-columns: minmax(0, 1fr);" in styles
    assert 'id="agenda-email-summary-button"' not in html
    assert "sendAgendaEmailSummary" not in script
    assert "/api/agenda/pending-tasks" in script
    assert "function showInitialView" in script
    assert 'appState.agendaView = "pending";' in script
    assert "showCalendarView();" in script
    assert "showDaysView();" in script
    initial_view = script.split("async function showInitialView()", 1)[1].split("function showActuacionesView", 1)[0]
    assert "if (canUsePendingAgenda())" in initial_view
    assert initial_view.index("if (canUsePendingAgenda())") < initial_view.index("showDaysView();")
    assert "function canUsePendingAgenda()" in script
    assert "return isAdmin() || isNuria();" in script
    assert 'if (!canUsePendingAgenda() || !token) return false;' in script
    show_calendar = script.split("function showCalendarView", 1)[1].split("function agendaDeepLinkToken", 1)[0]
    assert 'appState.agendaView = "pending";' in show_calendar
    assert 'setPageHeader("Agenda", "Calendario y tareas pendientes")' in show_calendar
    assert "nuriaEstados.includes(option.value) || option.value === current" in script
    assert "select data-pending-state" in script
    assert "updatePendingTaskState" in script
    assert "function pendingLicitacionCardItem" in script
    assert "return renderCard(pendingLicitacionCardItem(item)" in script
    assert "pending-licitacion-card" in script
    assert "function renderPendingTaskCard" in script
    assert 'renderExpandableDescription(item.subtitle || item.description || "Sin descripción", "object")' in script
    assert "pending-task-card" in script
    assert 'class="card-layout"' in script
    assert "card-side-actions" in script
    assert 'button[data-open-licitacion-detail]' in script
    assert 'button[data-edit-id]' in script
    assert "agendaDeepLinkToken" in script
    assert 'params.get("agenda_source")' in script
    assert "openAgendaOrigin(token)" in script
    agenda_card_render = script.split("function renderAgendaCompactCard", 1)[1].split("function renderCalendarDayPanel", 1)[0]
    assert 'if (item.source_type === "licitacion")' in agenda_card_render
    assert "return renderPendingTaskCard(item, colorClass);" in agenda_card_render
    assert "isPendingAgendaView() && item.source_type" not in agenda_card_render
    assert '<article class="radar-card agenda-card' not in agenda_card_render


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
    assert "display: grid;" in styles
    assert "grid-template-columns: minmax(38px, 1fr) auto minmax(38px, 1fr);" in styles
    assert "justify-self: center;" in styles
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
    assert "#actuaciones-summary" not in styles


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


def test_config_phase1_tabs_are_structured_and_safe_for_admin_diagnostics() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    expected_tabs = {
        "general": "General",
        "users": "Usuarios y permisos",
        "mail": "Correos y notificaciones",
        "mailboxes": "Buzones automáticos",
        "storage": "Almacenamiento / Dropbox",
        "ai": "IA documental",
        "automation": "Automatismos",
        "advanced": "Avanzado / diagnóstico",
    }

    assert 'id="config-button" class="nav-item" data-nav-section="config" data-admin-only hidden' in html
    assert 'id="config-section" hidden' in html
    for tab_id, label in expected_tabs.items():
        assert f'data-config-tab="{tab_id}"' in html
        assert f'data-config-panel="{tab_id}"' in html
        assert label in html

    assert "Zona avanzada" in html
    assert "Los secretos nunca se muestran en claro." in html
    assert 'id="copy-config-diagnostics-button"' in html
    assert 'id="config-diagnostics-text"' in html
    assert "function renderConfigTabs" in script
    assert "function showConfigTab" in script
    assert "Secretos: no incluidos." in script
    assert "GEMINI_API_KEY" not in script
    assert "LLANGON_TELEGRAM_BOT_TOKEN" not in script
    assert "INFONALIA_DROPBOX_APP_SECRET" not in script
    assert "INFONALIA_DROPBOX_REFRESH_TOKEN" not in script
    assert "LLANGON_ACTIONS_IMAP_PASSWORD" not in script
    assert "INFONALIA_SMTP_PASSWORD" not in script
    assert ".config-tabs" in styles
    assert "overflow-x: auto;" in styles
    assert ".config-tabs button.active" in styles


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
