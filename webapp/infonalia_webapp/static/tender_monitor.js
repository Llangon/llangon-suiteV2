(() => {
  "use strict";

  const state = {
    me: null,
    summary: null,
    followed: [],
    settings: null,
    activeTab: "overview",
    pollTimer: null,
  };

  const byId = (id) => document.getElementById(id);
  const root = byId("tender-monitor-root");

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(value) {
    if (!value) return "Pendiente";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("es-ES");
  }

  function durationLabel(value) {
    const started = new Date(value || "");
    if (Number.isNaN(started.getTime())) return "duración pendiente";
    const seconds = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
    const minutes = Math.floor(seconds / 60);
    return minutes ? `${minutes} min` : `${seconds} s`;
  }

  function tone(status) {
    const value = String(status || "").toLowerCase();
    if (["completed", "notified", "no_changes", "baseline_rebuilt", "prepared", "sent"].includes(value)) return "ok";
    if (["running", "pending", "waiting", "waiting_ai", "pending_notification"].includes(value)) return "running";
    if (["failed", "error", "notification_failed", "not_prepared"].includes(value)) return "error";
    return "warning";
  }

  function pill(label, status = label) {
    return `<span class="tender-monitor-pill ${tone(status)}">${escapeHtml(label || "Pendiente")}</span>`;
  }

  async function ensureMe() {
    if (state.me) return state.me;
    const response = await fetch("/api/me");
    if (!response.ok) throw new Error("No se pudo leer la sesión.");
    state.me = await response.json();
    return state.me;
  }

  function isAdmin() {
    return state.me?.role === "admin";
  }

  async function api(path, options = {}) {
    await ensureMe();
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = state.me.csrf_token || "";
    const response = await fetch(path, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Error HTTP ${response.status}`);
    return payload;
  }

  function showResult(message, type = "ok") {
    const element = byId("tender-monitor-result");
    if (!element) return;
    element.className = `import-result ${type}`;
    element.textContent = message;
  }

  function renderSummary() {
    const item = state.summary || {};
    const counts = item.counts || {};
    const active = item.active_cycle;
    const last = item.last_cycle;
    const banner = byId("tender-monitor-banner");
    if (banner) {
      banner.className = `tender-monitor-banner ${active ? "running" : ""}`;
      banner.textContent = active
        ? `Ciclo ${active.id} en curso · iniciado por ${active.requested_by || "sistema"} · ${durationLabel(active.started_at || active.created_at)} · ${active.processed_count || 0}/${active.total_count || 0} procesadas${active.current_licitacion_id ? ` · licitación ${active.current_licitacion_id}` : ""}.`
        : (item.config_error || item.automatic_message || "Ejecución automática desactivada.");
    }
    const target = byId("tender-monitor-summary");
    if (!target) return;
    target.innerHTML = `
      <article class="tender-monitor-card"><span>En seguimiento</span><strong>${escapeHtml(counts.followed || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Preparadas</span><strong>${escapeHtml(counts.prepared || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Requieren atención</span><strong>${escapeHtml((counts.not_prepared || 0) + (counts.discovery_issues || 0))}</strong></article>
      <article class="tender-monitor-card"><span>Revisadas (último ciclo)</span><strong>${escapeHtml(last?.processed_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Sin cambios</span><strong>${escapeHtml(last?.no_changes_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Con novedades</span><strong>${escapeHtml(last?.changes_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Esperando IA</span><strong>${escapeHtml(active?.waiting_ai_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Notificadas</span><strong>${escapeHtml(last?.notified_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Errores</span><strong>${escapeHtml(last?.error_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Incidencias</span><strong>${escapeHtml((active || last)?.incident_count || 0)}</strong></article>
      <article class="tender-monitor-card"><span>Último ciclo</span><strong>${last ? escapeHtml(`#${last.id}`) : "—"}</strong><small>${last ? escapeHtml(last.status) : "Sin ejecuciones"}</small></article>
    `;
    const runButton = byId("tender-monitor-run-global");
    if (runButton) runButton.disabled = Boolean(active);
  }

  function renderFollowed() {
    const target = byId("tender-monitor-followed");
    if (!target) return;
    if (!state.followed.length) {
      target.innerHTML = `<div class="empty">No hay licitaciones con el marcador físico EnSeguimiento.llangon.</div>`;
      return;
    }
    target.innerHTML = `
      <table class="tender-monitor-table">
        <thead><tr><th>ID</th><th>Expediente</th><th>Plataforma</th><th>Preparación</th><th>Última revisión</th><th>Última novedad</th><th>Resultado</th><th>IA / aviso</th><th></th></tr></thead>
        <tbody>${state.followed.map((item) => `
          <tr>
            <td>${escapeHtml(item.id)}</td>
            <td><strong>${escapeHtml(item.expediente || `#${item.id}`)}</strong><br><small>${escapeHtml(item.title)}</small></td>
            <td>${escapeHtml(item.platform || "—")}</td>
            <td>${pill(item.prepared ? "Preparada" : "No preparada", item.prepared ? "prepared" : "not_prepared")}<br><small>${escapeHtml(item.preparation_reason || "")}</small></td>
            <td>${escapeHtml(formatDate(item.last_review))}</td>
            <td>${escapeHtml(formatDate(item.last_change))}</td>
            <td>${pill(item.last_result, item.last_result)}</td>
            <td>${escapeHtml(item.ai_status || "—")} / ${escapeHtml(item.notification_status || "—")}</td>
            <td class="actions"><button type="button" class="secondary" data-tm-run-id="${escapeHtml(item.id)}" ${item.prepared ? "" : "disabled"}>Revisar</button> <button type="button" class="ghost" data-tm-open-id="${escapeHtml(item.id)}">Ficha</button> <button type="button" class="ghost" data-tm-history-id="${escapeHtml(item.id)}">Histórico</button></td>
          </tr>`).join("")}</tbody>
      </table>`;
  }

  async function loadDashboard({ silent = false } = {}) {
    try {
      const [summary, followed] = await Promise.all([
        api("/api/tender-monitor/summary"),
        api("/api/tender-monitor/followed"),
      ]);
      state.summary = summary;
      state.followed = followed.items || [];
      renderSummary();
      renderFollowed();
      schedulePoll();
    } catch (error) {
      if (!silent) showResult(error.message, "error");
    }
  }

  function schedulePoll() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
    if (!state.summary?.active_cycle) return;
    state.pollTimer = window.setTimeout(() => loadDashboard({ silent: true }), 4000);
  }

  async function startCycle(licitacionId = null) {
    const button = licitacionId ? document.querySelector(`[data-tm-run-id="${licitacionId}"]`) : byId("tender-monitor-run-global");
    if (button) button.disabled = true;
    try {
      const path = licitacionId
        ? `/api/tender-monitor/licitaciones/${encodeURIComponent(licitacionId)}/cycles`
        : "/api/tender-monitor/cycles";
      const result = await api(path, { method: "POST", body: "{}" });
      showResult(`Ciclo ${result.cycle_id} encolado. El estado se actualizará automáticamente.`);
      await loadDashboard({ silent: true });
      if (licitacionId) refreshTenderPanels(licitacionId);
    } catch (error) {
      showResult(error.message, "error");
      if (button) button.disabled = false;
    }
  }

  function historyQuery() {
    const form = byId("tender-monitor-history-filters");
    const params = new URLSearchParams();
    if (!form) return params;
    new FormData(form).forEach((value, key) => {
      if (String(value).trim()) params.set(key, String(value).trim());
    });
    return params;
  }

  async function loadHistory() {
    const target = byId("tender-monitor-history");
    if (target) target.innerHTML = `<div class="empty">Cargando ciclos…</div>`;
    try {
      const payload = await api(`/api/tender-monitor/cycles?${historyQuery().toString()}`);
      const items = payload.items || [];
      if (!target) return;
      target.innerHTML = items.length ? `
        <table class="tender-monitor-table"><thead><tr><th>Ciclo</th><th>Origen</th><th>Estado</th><th>Procesadas</th><th>Novedades</th><th>Incidencias</th></tr></thead>
        <tbody>${items.map((item) => `<tr data-tm-cycle-id="${escapeHtml(item.id)}" tabindex="0"><td><strong>#${escapeHtml(item.id)}</strong><br><small>${escapeHtml(formatDate(item.started_at || item.created_at))}</small></td><td>${escapeHtml(item.origin)}</td><td>${pill(item.status, item.status)}</td><td>${escapeHtml(item.processed_count || 0)}/${escapeHtml(item.total_count || 0)}</td><td>${escapeHtml(item.changes_count || 0)}</td><td>${escapeHtml(item.incident_count || 0)}</td></tr>`).join("")}</tbody></table>`
        : `<div class="empty">No hay ciclos para estos filtros.</div>`;
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
  }

  function notificationRow(item) {
    const retry = isAdmin() && item.status !== "sent"
      ? `<button type="button" class="ghost" data-tm-retry-notification="${escapeHtml(item.id)}">Reintentar ${escapeHtml(item.channel)}</button>`
      : "";
    return `<div class="tender-monitor-detail-item"><strong>${escapeHtml(item.channel)} · ${escapeHtml(item.destination)}</strong> ${pill(item.status, item.status)}<p>${escapeHtml(item.error_message || "")}</p>${retry}</div>`;
  }

  function renderCycleDetail(item) {
    const target = byId("tender-monitor-cycle-detail");
    if (!target) return;
    const executions = item.executions || [];
    const incidents = item.incidents || [];
    target.innerHTML = `
      <h3>Ciclo #${escapeHtml(item.id)}</h3>
      <p>${pill(item.status, item.status)} · ${escapeHtml(formatDate(item.started_at || item.created_at))}</p>
      <h4>Licitaciones</h4>
      <div class="tender-monitor-detail-list">${executions.length ? executions.map((execution) => {
        const batch = execution.batch;
        const differences = batch?.differences || [];
        const notifications = batch?.notifications || [];
        return `<div class="tender-monitor-detail-item">
          <strong>${escapeHtml(execution.expediente || `Licitación ${execution.licitacion_id}`)}</strong> ${pill(execution.status, execution.status)}
          <p>${escapeHtml(execution.preparation_reason || execution.error_message || "")}</p>
          ${differences.length ? `<ul>${differences.map((difference) => `<li><strong>${escapeHtml(difference.change_type)}</strong> · ${escapeHtml(difference.title || difference.item_key)}</li>`).join("")}</ul>` : ""}
          ${batch && isAdmin() && batch.ai_status === "failed" ? `<button type="button" class="ghost" data-tm-retry-ai="${escapeHtml(batch.id)}">Reintentar IA</button>` : ""}
          ${notifications.map(notificationRow).join("")}
          ${isAdmin() && (execution.previous_snapshot || execution.current_snapshot) ? `<details><summary>Snapshots técnicos</summary><p><strong>Anterior</strong></p><pre>${escapeHtml(JSON.stringify(execution.previous_snapshot || {}, null, 2))}</pre><p><strong>Actual</strong></p><pre>${escapeHtml(JSON.stringify(execution.current_snapshot || {}, null, 2))}</pre></details>` : ""}
          ${isAdmin() && execution.log?.length ? `<details><summary>Log técnico</summary><pre>${escapeHtml(JSON.stringify(execution.log, null, 2))}</pre></details>` : ""}
          ${isAdmin() && execution.status === "error" ? `<button type="button" class="secondary" data-tm-retry-execution="${escapeHtml(execution.id)}">Reintentar licitación</button>` : ""}
        </div>`;
      }).join("") : `<div class="empty">Sin ejecuciones.</div>`}</div>
      <h4>Incidencias</h4>
      <div class="tender-monitor-detail-list">${incidents.length ? incidents.map((incident) => `<div class="tender-monitor-detail-item"><strong>${escapeHtml(incident.phase)} · ${escapeHtml(incident.code)}</strong><p>${escapeHtml(incident.summary)}</p>${incident.technical_detail ? `<small>${escapeHtml(incident.technical_detail)}</small>` : ""}</div>`).join("") : `<div class="empty">Sin incidencias.</div>`}</div>
      ${isAdmin() && item.incident_report?.status === "failed" ? `<button type="button" class="secondary" data-tm-retry-report="${escapeHtml(item.id)}">Reintentar informe de incidencias</button>` : ""}
    `;
  }

  async function loadCycleDetail(cycleId) {
    const target = byId("tender-monitor-cycle-detail");
    if (target) target.innerHTML = `<div class="empty">Cargando detalle…</div>`;
    try {
      renderCycleDetail(await api(`/api/tender-monitor/cycles/${encodeURIComponent(cycleId)}`));
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
  }

  function renderSettings(payload) {
    state.settings = payload;
    const target = byId("tender-monitor-settings");
    if (!target) return;
    const values = payload.values || {};
    const users = payload.users || [];
    target.innerHTML = `
      <h3>Configuración global</h3>
      <p class="tender-monitor-banner">${escapeHtml(payload.automatic_message)}</p>
      <form id="tender-monitor-settings-form">
        <div class="tender-monitor-setting-grid">
          <label>Programación automática<input value="Desactivada" disabled></label>
          <label>Periodicidad futura<input name="future_frequency" value="${escapeHtml(values.future_frequency || "manual")}"></label>
          <label>Hora futura<input name="future_time" type="time" value="${escapeHtml(values.future_time || "")}"></label>
          <label>Tiempo máximo IA (segundos)<input name="ai_timeout_seconds" type="number" min="5" max="86400" value="${escapeHtml(values.ai_timeout_seconds || 900)}"></label>
          <label>Intentos de consulta<input name="download_retries" type="number" min="1" max="5" value="${escapeHtml(values.download_retries || 2)}"></label>
          <label>Intentos de aviso<input name="notification_retries" type="number" min="1" max="5" value="${escapeHtml(values.notification_retries || 2)}"></label>
          <label>Caducidad de lock (minutos)<input name="lease_minutes" type="number" min="5" max="1440" value="${escapeHtml(values.lease_minutes || 60)}"></label>
          <label><span>IA para documentos relevantes</span><input name="ai_enabled" type="checkbox" ${String(values.ai_enabled) === "1" ? "checked" : ""}></label>
          <label>Categorías IA (separadas por coma)<input name="document_ai_categories" value="${escapeHtml(values.document_ai_categories || "")}"></label>
        </div>
        <h4>Destinatarios globales</h4>
        <div class="tender-monitor-recipient-grid">${users.map((user) => `
          <div class="tender-monitor-recipient" data-tm-user="${escapeHtml(user.username)}">
            <strong>${escapeHtml(user.display_name || user.username)}<br><small>${escapeHtml(user.email || "Sin correo")} · ${escapeHtml(user.telegram_chat_id || "Sin Telegram")}</small></strong>
            <label><input type="checkbox" data-tm-email ${user.email_enabled ? "checked" : ""} ${user.email ? "" : "disabled"}> Email</label>
            <label title="${user.telegram_notifications_enabled ? "" : "Activa Telegram en la ficha del usuario"}"><input type="checkbox" data-tm-telegram ${user.telegram_enabled ? "checked" : ""} ${user.telegram_chat_id && user.telegram_notifications_enabled ? "" : "disabled"}> Telegram</label>
            <label><input type="checkbox" data-tm-incident ${user.incident_admin ? "checked" : ""}> Incidencias</label>
            <span><button type="button" class="ghost" data-tm-test-email="${escapeHtml(user.username)}">Probar email</button> <button type="button" class="ghost" data-tm-test-telegram="${escapeHtml(user.username)}">Probar Telegram</button></span>
          </div>`).join("")}</div>
        <button type="submit" class="primary">Guardar configuración</button>
      </form>`;
  }

  async function loadSettings() {
    const target = byId("tender-monitor-settings");
    if (!isAdmin()) {
      if (target) target.innerHTML = `<div class="empty">La configuración está reservada a administración.</div>`;
      return;
    }
    try {
      renderSettings(await api("/api/tender-monitor/settings"));
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
  }

  async function saveSettings(form) {
    const values = {};
    for (const name of ["future_frequency", "future_time", "ai_timeout_seconds", "download_retries", "notification_retries", "lease_minutes"]) {
      values[name] = form.elements[name].value;
    }
    values.ai_enabled = form.elements.ai_enabled.checked ? "1" : "0";
    values.document_ai_categories = form.elements.document_ai_categories.value;
    const users = [...form.querySelectorAll("[data-tm-user]")].map((row) => ({
      username: row.dataset.tmUser,
      email_enabled: row.querySelector("[data-tm-email]").checked,
      telegram_enabled: row.querySelector("[data-tm-telegram]").checked,
      incident_admin: row.querySelector("[data-tm-incident]").checked,
    }));
    try {
      renderSettings(await api("/api/tender-monitor/settings", { method: "PATCH", body: JSON.stringify({ values, users }) }));
      showResult("Configuración guardada.");
    } catch (error) {
      showResult(error.message, "error");
    }
  }

  async function retry(path, successMessage) {
    try {
      await api(path, { method: "POST", body: "{}" });
      showResult(successMessage);
      await loadHistory();
    } catch (error) {
      showResult(error.message, "error");
    }
  }

  function setTab(tab) {
    state.activeTab = tab;
    root?.querySelectorAll("[data-tender-monitor-tab]").forEach((button) => button.classList.toggle("active", button.dataset.tenderMonitorTab === tab));
    root?.querySelectorAll("[data-tender-monitor-panel]").forEach((panel) => { panel.hidden = panel.dataset.tenderMonitorPanel !== tab; });
    if (tab === "history") loadHistory();
    if (tab === "settings") loadSettings();
  }

  function tenderPanelHtml(licitacion) {
    return `<section class="tender-monitor-panel-card" data-tender-monitor-panel-card="${escapeHtml(licitacion.id)}">
      <div class="tender-monitor-panel-head"><div><p class="eyebrow">Monitor de licitaciones</p><h4>Seguimiento y monitorización</h4></div></div>
      <div class="empty">Cargando monitor…</div>
    </section>`;
  }

  async function loadTenderPanel(element) {
    const id = element.dataset.tenderMonitorPanelCard;
    if (!id || element.dataset.loading === "1") return;
    element.dataset.loading = "1";
    try {
      await ensureMe();
      const payload = await api(`/api/tender-monitor/licitaciones/${encodeURIComponent(id)}`);
      const monitor = payload.monitor || {};
      const executions = payload.executions || [];
      element.innerHTML = `
        <div class="tender-monitor-panel-head"><div><p class="eyebrow">Seguimiento y monitorización</p><h4>${monitor.followed ? "En seguimiento" : "Fuera de seguimiento"}</h4></div>${pill(monitor.prepared ? "Preparada" : "No preparada", monitor.prepared ? "prepared" : "not_prepared")}</div>
        <p>${escapeHtml(monitor.reason || "La licitación está lista para revisión técnica.")}</p>
        <div class="tender-monitor-panel-actions">
          ${(isAdmin() || state.me.role === "nuria") && monitor.prepared ? `<button type="button" class="primary" data-tm-run-id="${escapeHtml(id)}">Revisar ahora</button>` : ""}
          ${isAdmin() ? `<button type="button" class="secondary" data-tm-follow-id="${escapeHtml(id)}" data-active="${monitor.followed ? "0" : "1"}">${monitor.followed ? "Dejar de seguir" : "Seguir"}</button>` : ""}
          ${isAdmin() && monitor.prepared ? `<button type="button" class="ghost" data-tm-rebuild-id="${escapeHtml(id)}">Reconstruir línea base</button>` : ""}
          <button type="button" class="ghost" data-tm-history-id="${escapeHtml(id)}">${isAdmin() ? "Ver histórico completo" : "Actualizar historial"}</button>
        </div>
        <div class="tender-monitor-detail-list">${executions.slice(0, 5).map((execution) => `<div class="tender-monitor-detail-item"><strong>${escapeHtml(formatDate(execution.finished_at || execution.started_at))}</strong> ${pill(execution.status, execution.status)}<p>IA: ${escapeHtml(execution.ai_status)} · Avisos: ${escapeHtml(execution.notification_status)}</p></div>`).join("") || `<div class="empty">Todavía no se ha revisado.</div>`}</div>`;
    } catch (error) {
      element.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    } finally {
      element.dataset.loading = "0";
    }
  }

  function scanTenderPanels() {
    document.querySelectorAll("[data-tender-monitor-panel-card]").forEach(loadTenderPanel);
  }

  function refreshTenderPanels(id) {
    document.querySelectorAll(`[data-tender-monitor-panel-card="${id}"]`).forEach((element) => {
      element.dataset.loading = "0";
      loadTenderPanel(element);
    });
  }

  async function toggleFollow(id, active) {
    try {
      await api(`/api/tender-monitor/licitaciones/${encodeURIComponent(id)}/follow`, {
        method: "POST",
        body: JSON.stringify({ active }),
      });
      showResult(active ? "Seguimiento activado mediante el marcador físico." : "Seguimiento desactivado; el marcador físico se ha retirado.");
      refreshTenderPanels(id);
      await loadDashboard({ silent: true });
    } catch (error) {
      showResult(error.message, "error");
    }
  }

  async function rebuildBaseline(id) {
    if (!window.confirm("Se consultará la plataforma y se sustituirá la referencia técnica sin generar novedades. ¿Continuar?")) return;
    try {
      const result = await api(`/api/tender-monitor/licitaciones/${encodeURIComponent(id)}/rebuild-baseline`, {
        method: "POST",
        body: "{}",
      });
      showResult(`Reconstrucción de línea base encolada en el ciclo ${result.cycle_id}.`);
      refreshTenderPanels(id);
      await loadDashboard({ silent: true });
    } catch (error) {
      showResult(error.message, "error");
    }
  }

  async function testChannel(username, channel) {
    try {
      await api(`/api/tender-monitor/test-${channel}`, { method: "POST", body: JSON.stringify({ username }) });
      showResult(`Prueba de ${channel} enviada a ${username}.`);
    } catch (error) {
      showResult(error.message, "error");
    }
  }

  root?.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tender-monitor-tab]");
    if (tab) setTab(tab.dataset.tenderMonitorTab);
    const cycle = event.target.closest("[data-tm-cycle-id]");
    if (cycle) loadCycleDetail(cycle.dataset.tmCycleId);
  });

  document.addEventListener("click", (event) => {
    const run = event.target.closest("[data-tm-run-id]");
    if (run) startCycle(run.dataset.tmRunId);
    const history = event.target.closest("[data-tm-history-id]");
    if (history) {
      if (!isAdmin()) {
        refreshTenderPanels(history.dataset.tmHistoryId);
        return;
      }
      const form = byId("tender-monitor-history-filters");
      if (form) form.elements.licitacion_id.value = history.dataset.tmHistoryId;
      setTab("history");
      byId("monitor-button")?.click();
    }
    const follow = event.target.closest("[data-tm-follow-id]");
    if (follow) toggleFollow(follow.dataset.tmFollowId, follow.dataset.active === "1");
    const openTender = event.target.closest("[data-tm-open-id]");
    if (openTender) window.dispatchEvent(new CustomEvent("tender-monitor:open-licitacion", { detail: { id: openTender.dataset.tmOpenId } }));
    const rebuild = event.target.closest("[data-tm-rebuild-id]");
    if (rebuild) rebuildBaseline(rebuild.dataset.tmRebuildId);
    const notification = event.target.closest("[data-tm-retry-notification]");
    if (notification) retry(`/api/tender-monitor/notifications/${notification.dataset.tmRetryNotification}/retry`, "Canal reintentado.");
    const ai = event.target.closest("[data-tm-retry-ai]");
    if (ai) retry(`/api/tender-monitor/batches/${ai.dataset.tmRetryAi}/retry-ai`, "IA reintentada sobre el lote existente.");
    const execution = event.target.closest("[data-tm-retry-execution]");
    if (execution) retry(`/api/tender-monitor/executions/${execution.dataset.tmRetryExecution}/retry`, "Revisión individual encolada.");
    const report = event.target.closest("[data-tm-retry-report]");
    if (report) retry(`/api/tender-monitor/incident-reports/${report.dataset.tmRetryReport}/retry`, "Informe de incidencias reintentado.");
    const email = event.target.closest("[data-tm-test-email]");
    if (email) testChannel(email.dataset.tmTestEmail, "email");
    const telegram = event.target.closest("[data-tm-test-telegram]");
    if (telegram) testChannel(telegram.dataset.tmTestTelegram, "telegram");
  });

  byId("tender-monitor-run-global")?.addEventListener("click", () => startCycle());
  byId("tender-monitor-refresh")?.addEventListener("click", () => {
    loadDashboard();
    if (state.activeTab === "history") loadHistory();
  });
  byId("tender-monitor-history-filters")?.addEventListener("submit", (event) => {
    event.preventDefault();
    loadHistory();
  });
  document.addEventListener("submit", (event) => {
    if (event.target.id !== "tender-monitor-settings-form") return;
    event.preventDefault();
    saveSettings(event.target);
  });

  new MutationObserver(scanTenderPanels).observe(document.body, { childList: true, subtree: true });

  window.TenderMonitorUI = {
    show: async () => {
      await ensureMe();
      await loadDashboard();
      if (state.activeTab === "history") await loadHistory();
    },
    renderTenderPanel: tenderPanelHtml,
    refreshTenderPanels,
  };
  scanTenderPanels();
})();
