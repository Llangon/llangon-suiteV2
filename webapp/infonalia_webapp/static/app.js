const appState = {
  user: null,
  dias: [],
  items: [],
  estados: [],
  totals: {},
  currentDiaId: "",
  currentDiaTitle: "Todas las licitaciones",
  currentDayPendingReview: null,
  currentDayPendingAdmin: null,
  currentDaySentNuriaAt: "",
  currentDayNuriaDirtyAt: "",
  currentDayNuriaPendingUpdate: false,
  currentDayReviewedAt: "",
  currentDayNuriaTotal: null,
  calendarItems: [],
  newsItems: [],
  calendarDate: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  calendarSelectedDate: "",
  nuriaDaysView: "pending",
  licitacionesView: "live",
  lastSection: "days",
  config: null,
  expandedCards: new Set(),
  monitorDetails: {},
};

const daysSection = document.getElementById("days-section");
const licitacionesSection = document.getElementById("licitaciones-section");
const calendarSection = document.getElementById("calendar-section");
const notificationsSection = document.getElementById("notifications-section");
const newsAdminSection = document.getElementById("news-admin-section");
const configSection = document.getElementById("config-section");
const daysBoard = document.getElementById("days-board");
const daysSummary = document.getElementById("days-summary");
const nuriaDaysTabs = document.getElementById("nuria-days-tabs");
const licitacionesTabs = document.getElementById("licitaciones-tabs");
const board = document.getElementById("board");
const summary = document.getElementById("summary");
const stateFilter = document.getElementById("state-filter");
const dateOrder = document.getElementById("date-order");
const searchInput = document.getElementById("search");
const currentDayTitle = document.getElementById("current-day-title");
const reviewDayButton = document.getElementById("review-day-button");
const sendNuriaButton = document.getElementById("send-nuria-button");
const calendarMonthTitle = document.getElementById("calendar-month-title");
const calendarSearch = document.getElementById("calendar-search");
const calendarStateFilter = document.getElementById("calendar-state-filter");
const calendarSummary = document.getElementById("calendar-summary");
const calendarRadar = document.getElementById("calendar-radar");
const calendarBoard = document.getElementById("calendar-board");
const calendarDayPanel = document.getElementById("calendar-day-panel");
const notificationsBoard = document.getElementById("notifications-board");
const newsAdminBoard = document.getElementById("news-admin-board");
const newsForm = document.getElementById("news-form");
const newsResult = document.getElementById("news-result");
const newsFormTitle = document.getElementById("news-form-title");
const notificationSearch = document.getElementById("notification-search");
const notificationScope = document.getElementById("notification-scope");
const notificationDestination = document.getElementById("notification-destination");
const notificationEmailState = document.getElementById("notification-email-state");
const editor = document.getElementById("editor");
const editorTitle = document.getElementById("editor-title");
const editorEyebrow = document.getElementById("editor-eyebrow");
const form = document.getElementById("licitacion-form");
const importer = document.getElementById("importer");
const importForm = document.getElementById("import-form");
const importResult = document.getElementById("import-result");
const monitorDialog = document.getElementById("monitor-dialog");
const monitorDialogTitle = document.getElementById("monitor-dialog-title");
const monitorDialogContent = document.getElementById("monitor-dialog-content");
const userConfigForm = document.getElementById("user-config-form");
const usersBoard = document.getElementById("users-board");
const settingsForm = document.getElementById("settings-form");
const settingsResult = document.getElementById("settings-result");
const testSmtpButton = document.getElementById("test-smtp-button");
const pageTitle = document.getElementById("page-title");
const pageKicker = document.getElementById("page-kicker");
const sessionUser = document.getElementById("session-user");

const estadoOrden = [
  "Pendiente",
  "Descartada por mí",
  "Pendiente Nuria",
  "Descartar",
  "Descargar",
  "Hacer",
];

const estadoLabels = {
  "Pendiente": "Pendiente",
  "Descartada por mí": "Descartada por mí",
  "Pendiente Nuria": "Pendiente de revisión",
  "Descartar": "Descartada",
  "Descargar": "Solo descargar",
  "Hacer": "Preparar licitación",
};

const nuriaEstados = ["Pendiente Nuria", "Descartar", "Descargar", "Hacer"];
const nuriaLicitacionesEstados = ["Descargar", "Hacer"];
const calendarioEstados = ["Pendiente Nuria", "Descargar", "Hacer"];
const editorFields = [
  "id",
  "expediente",
  "estado",
  "objeto",
  "organismo",
  "provincia",
  "tipo",
  "presupuesto",
  "fecha_limite",
  "hora_limite",
  "fecha_infonalia",
  "plataforma",
  "enlace_perfil",
  "enlace_infonalia",
  "ruta_carpeta",
  "comentario",
];

function isAdmin() {
  return appState.user?.role === "admin";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "";
  return Number(value).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

function formatDate(value) {
  if (!value || value === "sin-fecha") return "";
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

function parseTimeParts(value) {
  const match = String(value || "").match(/(\d{1,2}):(\d{2})/);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
  return { hours, minutes };
}

function daysUntil(value, timeValue = "") {
  if (!value || value === "sin-fecha") return null;
  const [year, month, day] = String(value).split("-").map(Number);
  if (!year || !month || !day) return null;

  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dueDate = new Date(year, month - 1, day);
  const calendarDays = Math.ceil((dueDate - startToday) / 86400000);
  const timeParts = parseTimeParts(timeValue);

  if (timeParts) {
    const dueAt = new Date(year, month - 1, day, timeParts.hours, timeParts.minutes);
    if (dueAt < now) return -1;
  }

  return calendarDays;
}

function dueLabel(days) {
  if (days === null) return "";
  if (days < 0) return "Vencida";
  if (days === 0) return "Vence hoy";
  if (days === 1) return "Vence mañana";
  return `Vence en ${days} días`;
}

function dueClass(days) {
  if (days === null) return "";
  if (days < 0) return "due-expired";
  if (days <= 2) return "due-urgent";
  if (days <= 7) return "due-soon";
  if (days <= 15) return "due-medium";
  return "due-late";
}

function parseDate(value) {
  if (!value || value === "sin-fecha") return null;
  const [year, month, day] = String(value).split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function dateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthTitle(date) {
  const text = date.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function isSameMonth(date, monthDate) {
  return date.getFullYear() === monthDate.getFullYear() && date.getMonth() === monthDate.getMonth();
}

function addMonths(date, amount) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function monthStartMonday(date) {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const mondayIndex = (first.getDay() + 6) % 7;
  first.setDate(first.getDate() - mondayIndex);
  return first;
}

function badgeClass(value) {
  return String(value || "Pendiente")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll(" ", "-");
}

function estadoLabel(value) {
  return estadoLabels[value] || value || "";
}

function normalizeUrl(value) {
  const url = String(value ?? "").trim();
  if (!url) return "";
  const lower = url.toLowerCase();
  if (lower.startsWith("http://") || lower.startsWith("https://") || lower.startsWith("mailto:")) {
    return url;
  }
  if (url.startsWith("//")) return `https:${url}`;
  if (/^[a-z0-9.-]+\.[a-z]{2,}([/:?#].*)?$/i.test(url)) return `https://${url}`;
  return url;
}

function applyRoleUi() {
  document.body.classList.toggle("is-admin", isAdmin());
  document.body.classList.toggle("is-nuria", !isAdmin());
  document.querySelectorAll("[data-admin-only]").forEach((element) => {
    element.hidden = !isAdmin();
  });
  nuriaDaysTabs.hidden = false;
  document.getElementById("list-button").textContent = isAdmin() ? "Todas las licitaciones" : "Todas mis licitaciones";
  if (sessionUser) {
    const name = appState.user?.display_name || appState.user?.username || "";
    sessionUser.textContent = name ? `Sesión: ${name}` : "";
  }
}

async function loadMe() {
  const response = await fetch("/api/me");
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    return;
  }
  const data = await response.json();
  appState.user = data;
  Object.assign(estadoLabels, data.labels || {});
  applyRoleUi();
}

function setActiveNav(section) {
  document.querySelectorAll("[data-nav-section]").forEach((button) => {
    button.classList.toggle("active", button.dataset.navSection === section);
  });
}

function setPageHeader(title, kicker = "Panel privado") {
  if (pageTitle) pageTitle.textContent = title;
  if (pageKicker) pageKicker.textContent = kicker;
}

function showDaysView() {
  appState.currentDiaId = "";
  appState.currentDiaTitle = "Todas las licitaciones";
  appState.lastSection = "days";
  setActiveNav("days");
  setPageHeader("Días Infonalia", "Revisión");
  daysSection.hidden = false;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  configSection.hidden = true;
  loadDias();
}

function showLicitacionesView({ diaId = "", title = "Todas las licitaciones", view = "live" } = {}) {
  appState.currentDiaId = diaId;
  appState.currentDiaTitle = title;
  appState.licitacionesView = diaId ? "all" : view;
  currentDayTitle.textContent = title;
  appState.lastSection = "licitaciones";
  setActiveNav("licitaciones");
  setPageHeader(diaId ? "Revisión de día" : "Licitaciones", diaId ? title : "Bandeja");
  daysSection.hidden = true;
  licitacionesSection.hidden = false;
  calendarSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  configSection.hidden = true;
  renderLicitacionesTabs();
  loadItems();
}

function showCalendarView() {
  const todayKey = dateKey(new Date());
  if (!appState.calendarSelectedDate) appState.calendarSelectedDate = todayKey;
  appState.lastSection = "calendar";
  setActiveNav("calendar");
  setPageHeader("Calendario", "Vencimientos");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = false;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  configSection.hidden = true;
  loadCalendarItems();
}

function showNotificationsView() {
  setActiveNav("notifications");
  setPageHeader("Buzón", "Notificaciones");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  notificationsSection.hidden = false;
  newsAdminSection.hidden = true;
  configSection.hidden = true;
  loadNotifications();
}

function showNewsAdminView() {
  if (!isAdmin()) return;
  appState.lastSection = "news-admin";
  setActiveNav("news-admin");
  setPageHeader("Gestión de noticias", "Web pública");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = false;
  configSection.hidden = true;
  loadNewsAdmin();
}

function showConfigView() {
  if (!isAdmin()) return;
  appState.lastSection = "config";
  setActiveNav("config");
  setPageHeader("Configuración", "Administración");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  configSection.hidden = false;
  loadConfig();
}

function backFromNotifications() {
  if (appState.lastSection === "calendar") {
    showCalendarView();
    return;
  }
  if (appState.lastSection === "licitaciones") {
    showLicitacionesView({
      diaId: appState.currentDiaId,
      title: appState.currentDiaTitle,
      view: appState.licitacionesView,
    });
    return;
  }
  showDaysView();
}

function backFromConfig() {
  showDaysView();
}

async function loadDias() {
  const response = await fetch("/api/dias");
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    return;
  }
  const data = await response.json();
  appState.dias = data.items;
  renderNuriaDaysTabs();
  renderDaysSummary();
  renderDays();
}

function visibleDias() {
  if (appState.nuriaDaysView === "reviewed") {
    return appState.dias.filter((dia) => diaIsCurrentlyReviewed(dia));
  }

  return appState.dias.filter((dia) => !diaIsCurrentlyReviewed(dia));
}

function renderNuriaDaysTabs() {
  const pendientes = appState.dias.filter((dia) => !diaIsCurrentlyReviewed(dia)).length;
  const revisados = appState.dias.filter((dia) => diaIsCurrentlyReviewed(dia)).length;

  nuriaDaysTabs.querySelectorAll("button[data-nuria-days-view]").forEach((button) => {
    const view = button.dataset.nuriaDaysView;
    button.classList.toggle("active", view === appState.nuriaDaysView);
    button.textContent = view === "pending"
      ? `Pendientes de revisión (${pendientes})`
      : `Revisados (${revisados})`;
  });
}

function diaIsCurrentlyReviewed(dia) {
  return Boolean(dia?.reviewed_at) && !dia?.nuria_pending_update;
}

function renderDaysSummary() {
  const days = visibleDias();
  if (!isAdmin()) {
    const total = days.reduce((sum, dia) => sum + Number(dia.total_nuria || 0), 0);
    const pendientes = days.reduce((sum, dia) => sum + Number(dia.pendientes_nuria || 0), 0);
    const descartadas = days.reduce((sum, dia) => sum + Number(dia.descartadas_nuria || 0), 0);
    const soloDescargar = days.reduce((sum, dia) => sum + Number(dia.solo_descargar || 0), 0);
    const preparar = days.reduce((sum, dia) => sum + Number(dia.preparar_licitacion || 0), 0);

    daysSummary.innerHTML = [
      ["Total licitaciones", total],
      ["Pendientes de revisión", pendientes],
      ["Descartadas", descartadas],
      ["Solo descargar", soloDescargar],
      ["Preparar licitación", preparar],
    ].map(renderMetric).join("");
    return;
  }

  const total = days.length;
  const pendientes = days.filter((dia) => dia.estado !== "Completado").length;
  const enRevision = days.filter((dia) => dia.pendientes_nuria > 0 || dia.decisiones_nuria > 0).length;
  const completados = days.filter((dia) => dia.estado === "Completado").length;

  daysSummary.innerHTML = [
    ["Días cargados", total],
    ["Pendientes", pendientes],
    ["En revisión", enRevision],
    ["Completados", completados],
  ].map(renderMetric).join("");
}

function renderMetric([label, value]) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function renderDays() {
  const days = visibleDias();

  if (!days.length) {
    daysBoard.innerHTML = isAdmin()
      ? `<div class="empty">Todavía no hay días Infonalia cargados.</div>`
      : `<div class="empty">No hay días ${appState.nuriaDaysView === "reviewed" ? "revisados" : "pendientes de revisión"}.</div>`;
    return;
  }

  daysBoard.innerHTML = days.map((dia) => {
    const metrics = isAdmin()
      ? [
          ["Total", dia.total],
          ["Pendientes", dia.pendientes],
          ["Descartadas por mí", dia.descartadas_mi],
          ["Pendientes de revisión", dia.pendientes_nuria],
          ["Decisiones de revisión", dia.decisiones_nuria],
        ]
      : [
          ["Total licitaciones", dia.total_nuria],
          ["Pendientes de revisión", dia.pendientes_nuria],
          ["Descartadas", dia.descartadas_nuria],
          ["Solo descargar", dia.solo_descargar],
          ["Preparar licitación", dia.preparar_licitacion],
          ["Fecha de revisión", dia.fecha_revision || "Sin revisar"],
        ];

    return `
      <article class="day-card">
        <div class="card-head">
          <div>
            <p class="eyebrow">Día Infonalia</p>
            <h2>${escapeHtml(dia.titulo)}</h2>
          </div>
          <span class="badge ${badgeClass(dia.estado)}">${escapeHtml(dia.estado)}</span>
        </div>

        <div class="day-metrics ${isAdmin() ? "" : "day-metrics-nuria"}">
          ${metrics.map(([label, value]) => `
            <div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "")}</strong></div>
          `).join("")}
        </div>

        <div class="card-actions">
          <button class="primary" data-open-dia="${dia.id}" data-title="${escapeHtml(dia.titulo)}">Abrir revisión</button>
          ${isAdmin() ? `<button class="danger" data-delete-dia="${dia.id}" data-title="${escapeHtml(dia.titulo)}">Borrar día</button>` : ""}
        </div>
      </article>
    `;
  }).join("");
}

async function loadItems() {
  const params = new URLSearchParams();
  let estado = stateFilter.value;
  const ordenFecha = dateOrder.value || "asc";
  const q = searchInput.value.trim();
  const visibleOrder = visibleStateOrder();

  if (estado && estado !== "Todos" && !visibleOrder.includes(estado)) {
    estado = "Todos";
    stateFilter.value = "Todos";
  }

  if (estado && estado !== "Todos") params.set("estado", estado);
  if (appState.currentDiaId) params.set("dia_id", appState.currentDiaId);
  if (!appState.currentDiaId && appState.licitacionesView === "live") params.set("vivas", "1");
  if (!appState.currentDiaId && appState.licitacionesView === "active") params.set("vigentes", "1");
  params.set("orden_fecha", ordenFecha);
  if (q) params.set("q", q);

  const response = await fetch(`/api/licitaciones?${params.toString()}`);
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    return;
  }
  const data = await response.json();
  appState.items = data.items;
  appState.estados = data.estados;
  appState.totals = data.totals;
  appState.currentDayPendingReview = data.day_pending_review;
  appState.currentDayPendingAdmin = data.day_pending_admin;
  appState.currentDaySentNuriaAt = data.day_sent_nuria_at || "";
  appState.currentDayNuriaDirtyAt = data.day_nuria_dirty_at || "";
  appState.currentDayNuriaPendingUpdate = Boolean(data.day_nuria_pending_update);
  appState.currentDayReviewedAt = data.day_reviewed_at || "";
  appState.currentDayNuriaTotal = data.day_nuria_total;
  renderLicitacionesTabs();
  renderStateFilter();
  renderSummary();
  renderReviewButton();
  renderSendNuriaButton();
  renderBoard();
}

function renderLicitacionesTabs() {
  const showTabs = !appState.currentDiaId;
  licitacionesTabs.hidden = !showTabs;
  if (!showTabs) return;

  licitacionesTabs.querySelectorAll("button[data-licitaciones-view]").forEach((button) => {
    const view = button.dataset.licitacionesView;
    button.classList.toggle("active", view === appState.licitacionesView);
  });
}

function visibleStateOrder() {
  if (!appState.currentDiaId && appState.licitacionesView === "live") {
    return isAdmin() ? calendarioEstados : nuriaLicitacionesEstados;
  }
  if (isAdmin()) return estadoOrden;
  return appState.currentDiaId ? nuriaEstados : nuriaLicitacionesEstados;
}

function renderStateFilter() {
  const current = stateFilter.value || "Todos";
  const visibleOrder = visibleStateOrder();
  const safeCurrent = current === "Todos" || visibleOrder.includes(current) ? current : "Todos";
  const options = ["Todos", ...visibleOrder.filter((estado) => appState.estados.includes(estado))];
  stateFilter.innerHTML = options
    .map((estado) => {
      const value = estado === "Todos" ? "Todos" : estado;
      const label = estado === "Todos" ? "Todos" : estadoLabel(estado);
      return `<option value="${escapeHtml(value)}" ${value === safeCurrent ? "selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("");
  if (safeCurrent !== current) stateFilter.value = safeCurrent;
}

function renderSummary() {
  summary.innerHTML = [
    ["Vista actual", appState.items.length],
    ["Pendientes de revisión", appState.totals["Pendiente Nuria"] || 0],
    ["Solo descargar", appState.totals["Descargar"] || 0],
    ["Preparar licitación", appState.totals["Hacer"] || 0],
  ].map(renderMetric).join("");
}

function renderReviewButton() {
  const hasDay = Boolean(appState.currentDiaId);
  const hasPendingReview = Number(appState.currentDayPendingReview ?? appState.totals["Pendiente Nuria"] ?? 0) > 0;
  const dia = appState.dias.find((item) => String(item.id) === String(appState.currentDiaId));
  const isReviewed = diaIsCurrentlyReviewed(dia);
  reviewDayButton.hidden = !hasDay;
  reviewDayButton.dataset.reviewAction = isReviewed ? "unmark" : "mark";
  reviewDayButton.disabled = !hasDay || hasPendingReview || (isReviewed && !isAdmin());
  reviewDayButton.textContent = isReviewed
    ? isAdmin()
      ? "Desmarcar revisado"
      : "Día revisado"
    : "Marcar como revisado";
  reviewDayButton.title = hasPendingReview
    ? "No se puede marcar como revisado mientras queden licitaciones pendientes de revisión."
    : isReviewed
      ? isAdmin()
        ? "Quitar la fecha y hora de revisión de este día."
        : "Este día ya está marcado como revisado."
    : "";
}

function renderSendNuriaButton() {
  const hasDay = Boolean(appState.currentDiaId);
  const pendingAdmin = Number(appState.currentDayPendingAdmin || 0);
  const pendingReview = Number(appState.currentDayPendingReview || 0);
  const nuriaTotal = Number(appState.currentDayNuriaTotal ?? pendingReview);
  const alreadySent = Boolean(appState.currentDaySentNuriaAt);
  const hasPendingUpdate = Boolean(appState.currentDayNuriaPendingUpdate);
  const isReviewed = Boolean(appState.currentDayReviewedAt) && !hasPendingUpdate;
  const canSend = isAdmin()
    && hasDay
    && pendingAdmin === 0
    && (nuriaTotal > 0 || (alreadySent && hasPendingUpdate))
    && (!alreadySent || hasPendingUpdate);

  sendNuriaButton.hidden = !isAdmin() || !hasDay;
  sendNuriaButton.disabled = !canSend;
  if (pendingAdmin > 0) {
    sendNuriaButton.textContent = `Faltan ${pendingAdmin} por revisar`;
    sendNuriaButton.title = "Se activa cuando no quedan licitaciones pendientes de tu revisión.";
  } else if (nuriaTotal === 0 && !(alreadySent && hasPendingUpdate)) {
    sendNuriaButton.textContent = "Sin licitaciones para revisión";
    sendNuriaButton.title = "No hay licitaciones marcadas para revisión.";
  } else if (!alreadySent) {
    sendNuriaButton.textContent = "Enviar a revisión";
    sendNuriaButton.title = "";
  } else if (hasPendingUpdate) {
    sendNuriaButton.textContent = "Enviar actualización a revisión";
    sendNuriaButton.title = "Hay cambios posteriores al último envío.";
  } else if (isReviewed) {
    sendNuriaButton.textContent = "Revisado";
    sendNuriaButton.title = "El equipo revisor ya marcó este día como revisado.";
  } else {
    sendNuriaButton.textContent = "Ya enviado a revisión";
    sendNuriaButton.title = "No hay cambios nuevos desde el último envío.";
  }
}

function renderBoard() {
  if (!appState.items.length) {
    board.innerHTML = `<div class="empty">Todavía no hay licitaciones para esta vista.</div>`;
    return;
  }

  board.innerHTML = appState.items.map(renderCard).join("");
}

async function loadCalendarItems() {
  const response = await fetch("/api/licitaciones?orden_fecha=asc&calendario=1");
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    calendarBoard.innerHTML = `<div class="empty">No se pudo cargar el calendario.</div>`;
    calendarRadar.innerHTML = "";
    calendarDayPanel.innerHTML = "";
    return;
  }

  const data = await response.json();
  appState.calendarItems = data.items || [];
  renderCalendarStateFilter();
  renderCalendar();
}

function calendarFilteredItems() {
  const estado = calendarStateFilter.value || "Todos";
  const q = calendarSearch.value.trim().toLowerCase();
  return appState.calendarItems.filter((item) => {
    if (estado !== "Todos" && item.estado !== estado) return false;
    if (!q) return true;
    return [
      item.expediente,
      item.objeto,
      item.organismo,
      item.provincia,
      item.tipo,
    ].some((value) => String(value || "").toLowerCase().includes(q));
  });
}

function renderCalendarStateFilter() {
  const current = calendarStateFilter.value || "Todos";
  const present = new Set(appState.calendarItems.map((item) => item.estado).filter(Boolean));
  const calendarVisibleStates = isAdmin() ? calendarioEstados : nuriaLicitacionesEstados;
  const options = ["Todos", ...calendarVisibleStates.filter((estado) => present.has(estado))];
  calendarStateFilter.innerHTML = options
    .map((estado) => `<option value="${escapeHtml(estado)}">${escapeHtml(estado === "Todos" ? "Todos" : estadoLabel(estado))}</option>`)
    .join("");
  calendarStateFilter.value = options.includes(current) ? current : "Todos";
}

function itemsByDate(items) {
  return items.reduce((groups, item) => {
    const key = item.fecha_limite || "sin-fecha";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
    return groups;
  }, new Map());
}

function renderCalendar() {
  const filtered = calendarFilteredItems();
  const groups = itemsByDate(filtered);
  const monthDate = appState.calendarDate;
  const today = new Date();
  const todayKey = dateKey(today);
  const selectedKey = appState.calendarSelectedDate || todayKey;
  const monthItems = filtered.filter((item) => {
    const parsed = parseDate(item.fecha_limite);
    return parsed && isSameMonth(parsed, monthDate);
  });
  const urgentThisMonth = monthItems.filter((item) => {
    const days = daysUntil(item.fecha_limite, item.hora_limite);
    return days !== null && days >= 0 && days <= 7;
  }).length;
  const preparing = monthItems.filter((item) => item.estado === "Hacer").length;
  const withoutDate = filtered.filter((item) => !item.fecha_limite).length;

  calendarMonthTitle.textContent = monthTitle(monthDate);
  calendarSummary.innerHTML = [
    ["Mes visible", monthItems.length],
    ["Vencen en 7 días", urgentThisMonth],
    ["Preparar licitación", preparing],
    ["Sin fecha límite", withoutDate],
  ].map(renderMetric).join("");

  renderCalendarRadar(filtered);

  const start = monthStartMonday(monthDate);
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const current = new Date(start);
    current.setDate(start.getDate() + index);
    const key = dateKey(current);
    const dayItems = (groups.get(key) || []).sort(compareCalendarItems);
    const itemDays = dayItems
      .map((item) => daysUntil(item.fecha_limite, item.hora_limite))
      .filter((days) => days !== null);
    const liveItemDays = itemDays.filter((days) => days >= 0);
    const remainingDays = liveItemDays.length
      ? Math.min(...liveItemDays)
      : itemDays.length
        ? Math.min(...itemDays)
        : daysUntil(key);
    const urgent = dayItems.some((item) => {
      const days = daysUntil(item.fecha_limite, item.hora_limite);
      return days !== null && days >= 0 && days <= 2;
    });
    const expired = dayItems.length && dayItems.every((item) => daysUntil(item.fecha_limite, item.hora_limite) < 0);
    const classes = [
      "calendar-day",
      isSameMonth(current, monthDate) ? "" : "not-current",
      key === todayKey ? "today" : "",
      key === selectedKey ? "selected" : "",
      dayItems.length ? "has-items" : "",
      urgent ? "urgent-day" : "",
      expired ? "expired-day" : "",
    ].filter(Boolean).join(" ");

    cells.push(`
      <article class="${classes}" data-calendar-date="${key}">
        <div class="calendar-day-head">
          <strong>${current.getDate()}</strong>
          ${dayItems.length ? `<span>${dayItems.length}</span>` : ""}
        </div>
        <div class="calendar-events">
          ${dayItems.slice(0, 3).map(renderCalendarEvent).join("")}
          ${dayItems.length > 3 ? `<span class="calendar-more">+${dayItems.length - 3} más</span>` : ""}
        </div>
        ${dayItems.length && remainingDays !== null ? `<div class="calendar-day-foot ${dueClass(remainingDays)}">${escapeHtml(dueLabel(remainingDays))}</div>` : ""}
      </article>
    `);
  }
  calendarBoard.innerHTML = cells.join("");
  renderCalendarDayPanel(groups.get(selectedKey) || [], selectedKey);
}

function compareCalendarItems(a, b) {
  const timeA = a.hora_limite || "99:99";
  const timeB = b.hora_limite || "99:99";
  if (timeA !== timeB) return timeA.localeCompare(timeB);
  return String(a.expediente || "").localeCompare(String(b.expediente || ""));
}

function renderCalendarEvent(item) {
  const stateClass = badgeClass(item.estado);
  const time = item.hora_limite ? `${item.hora_limite} · ` : "";
  return `
    <span class="calendar-event event-${stateClass}">
      <span>${escapeHtml(time)}${escapeHtml(item.expediente || "Sin expediente")}</span>
    </span>
  `;
}

function renderCalendarRadar(items) {
  const upcoming = items
    .filter((item) => {
      const days = daysUntil(item.fecha_limite, item.hora_limite);
      return days !== null && days >= 0;
    })
    .sort((a, b) => {
      const dateCompare = String(a.fecha_limite || "").localeCompare(String(b.fecha_limite || ""));
      if (dateCompare) return dateCompare;
      return compareCalendarItems(a, b);
    })
    .slice(0, 8);

  if (!upcoming.length) {
    calendarRadar.innerHTML = `<div class="empty">No hay vencimientos próximos con los filtros actuales.</div>`;
    return;
  }

  calendarRadar.innerHTML = upcoming.map((item) => {
    const days = daysUntil(item.fecha_limite, item.hora_limite);
    return `
      <article class="radar-card ${dueClass(days)}" data-calendar-date="${escapeHtml(item.fecha_limite)}">
        <span>${escapeHtml(dueLabel(days))}</span>
        <strong>${escapeHtml(item.expediente || "Sin expediente")}</strong>
        <small>${escapeHtml(formatDate(item.fecha_limite))}${item.hora_limite ? ` · ${escapeHtml(item.hora_limite)}` : ""}</small>
      </article>
    `;
  }).join("");
}

function renderCalendarDayPanel(items, key) {
  const dateText = key === "sin-fecha" ? "Sin fecha límite" : formatDate(key);
  const sorted = [...items].sort(compareCalendarItems);
  if (!sorted.length) {
    calendarDayPanel.innerHTML = `
      <div class="panel-sticky">
        <p class="eyebrow">Día seleccionado</p>
        <h3>${escapeHtml(dateText)}</h3>
        <div class="empty">No hay licitaciones que venzan este día.</div>
      </div>
    `;
    return;
  }

  calendarDayPanel.innerHTML = `
    <div class="panel-sticky">
      <p class="eyebrow">Día seleccionado</p>
      <h3>${escapeHtml(dateText)}</h3>
      <div class="calendar-panel-list">
        ${sorted.map((item) => {
          const days = daysUntil(item.fecha_limite, item.hora_limite);
          const enlacePerfil = normalizeUrl(item.enlace_perfil);
          const enlaceInfonalia = normalizeUrl(item.enlace_infonalia);
          return `
            <article class="calendar-panel-item">
              <div class="calendar-panel-head">
                <span class="due-chip ${dueClass(days)}">${escapeHtml(dueLabel(days))}</span>
                <span class="badge ${badgeClass(item.estado)}">${escapeHtml(estadoLabel(item.estado))}</span>
              </div>
              <h4>${escapeHtml(item.expediente || "Sin expediente")}</h4>
              <p class="calendar-panel-org">${escapeHtml(item.organismo || "")}</p>
              <p>${escapeHtml(item.objeto || "Sin objeto informado")}</p>
              <div class="calendar-panel-meta">
                ${item.hora_limite ? `<span>${escapeHtml(item.hora_limite)}</span>` : ""}
                ${item.tipo ? `<span>${escapeHtml(item.tipo)}</span>` : ""}
                ${item.presupuesto ? `<span>${escapeHtml(formatMoney(item.presupuesto))}</span>` : ""}
                ${item.provincia ? `<span>${escapeHtml(item.provincia)}</span>` : ""}
              </div>
              <div class="links">
                ${enlacePerfil ? `<a href="${escapeHtml(enlacePerfil)}" target="_blank" rel="noreferrer">Perfil</a>` : ""}
                ${enlaceInfonalia ? `<a href="${escapeHtml(enlaceInfonalia)}" target="_blank" rel="noreferrer">Infonalia</a>` : ""}
                ${isAdmin() ? `<button type="button" data-calendar-edit="${item.id}">Editar</button>` : ""}
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

async function loadNotifications() {
  const params = new URLSearchParams();
  const q = notificationSearch.value.trim();
  if (q) params.set("q", q);
  if (isAdmin()) {
    params.set("scope", notificationScope.value || "mine");
    if (notificationDestination.value) params.set("usuario_destino", notificationDestination.value);
  }
  if (notificationEmailState.value) params.set("email_estado", notificationEmailState.value);

  const response = await fetch(`/api/notificaciones?${params.toString()}`);
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    notificationsBoard.innerHTML = `<div class="empty">No se pudo cargar el buzón.</div>`;
    return;
  }

  const data = await response.json();
  populateNotificationUsers(data.users || []);
  const items = data.items || [];
  if (!items.length) {
    notificationsBoard.innerHTML = `<div class="empty">No hay notificaciones.</div>`;
    return;
  }

  notificationsBoard.innerHTML = items.map((item) => `
    <article class="notification-card">
      <div class="card-head">
        <div>
          <p class="eyebrow">${escapeHtml(item.fecha_hora_formateada || item.fecha_hora)}</p>
          <h2>${escapeHtml(item.asunto)}</h2>
        </div>
        <span class="badge ${item.email_sent_at ? "Hacer" : "Pendiente"}">
          ${item.email_sent_at ? "Email enviado" : "Email pendiente"}
        </span>
      </div>
      <div class="notification-meta">
        <span>De: ${escapeHtml(item.usuario_origen || "Sistema")}</span>
        <span>Para: ${escapeHtml(item.usuario_destino || "Todos")}</span>
      </div>
      <p class="notification-body">${escapeHtml(item.cuerpo || "")}</p>
      ${item.email_error ? `<p class="notification-warning">${escapeHtml(item.email_error)}</p>` : ""}
    </article>
  `).join("");
}

function populateNotificationUsers(users) {
  if (!isAdmin()) return;
  const current = notificationDestination.value;
  notificationDestination.innerHTML = [
    `<option value="">Todos</option>`,
    ...users.map((user) => `
      <option value="${escapeHtml(user.username)}">${escapeHtml(user.display_name || user.username)}</option>
    `),
  ].join("");
  notificationDestination.value = current;
}

function toDatetimeLocal(value) {
  if (!value) return "";
  const text = String(value).replace("Z", "");
  return text.length >= 16 ? text.slice(0, 16) : text;
}

async function loadNewsAdmin() {
  if (!isAdmin()) return;
  const response = await fetch("/api/news");
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    newsAdminBoard.innerHTML = `<div class="empty">No se pudieron cargar las noticias.</div>`;
    return;
  }
  const data = await response.json();
  appState.newsItems = data.items || [];
  renderNewsAdmin();
}

function renderNewsAdmin() {
  if (!appState.newsItems.length) {
    newsAdminBoard.innerHTML = `<div class="empty">Todavía no hay noticias.</div>`;
    return;
  }

  const labels = {
    draft: "Borrador",
    published: "Publicada",
    archived: "Archivada",
  };

  newsAdminBoard.innerHTML = appState.newsItems.map((item) => `
    <article class="user-row">
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(labels[item.status] || item.status)} · ${escapeHtml(item.category || "Sin categoría")}</span>
        <span>${escapeHtml(item.slug)}${item.isFeatured ? " · Destacada" : ""}</span>
      </div>
      <div class="card-actions">
        <a class="ghost" href="/noticias/${encodeURIComponent(item.slug)}" target="_blank" rel="noreferrer">Ver</a>
        <button data-edit-news="${item.id}">Editar</button>
        <button class="danger" data-delete-news="${item.id}">Eliminar</button>
      </div>
    </article>
  `).join("");
}

function resetNewsForm() {
  newsForm.reset();
  newsForm.elements.id.value = "";
  newsForm.elements.status.value = "draft";
  newsFormTitle.textContent = "Nueva noticia";
  newsResult.textContent = "";
  newsResult.className = "import-result";
}

function editNews(id) {
  const item = appState.newsItems.find((entry) => String(entry.id) === String(id));
  if (!item) return;
  newsForm.elements.id.value = item.id;
  newsForm.elements.title.value = item.title || "";
  newsForm.elements.slug.value = item.slug || "";
  newsForm.elements.excerpt.value = item.excerpt || "";
  newsForm.elements.content.value = item.content || "";
  newsForm.elements.category.value = item.category || "";
  newsForm.elements.tags.value = item.tags || "";
  newsForm.elements.featuredImage.value = item.featuredImage || "";
  newsForm.elements.status.value = item.status || "draft";
  newsForm.elements.publishedAt.value = toDatetimeLocal(item.publishedAt || "");
  newsForm.elements.isFeatured.checked = Boolean(item.isFeatured);
  newsFormTitle.textContent = `Editar ${item.title || "noticia"}`;
  newsResult.textContent = "";
  newsResult.className = "import-result";
}

async function saveNews(event) {
  event.preventDefault();
  const id = newsForm.elements.id.value;
  const payload = {
    title: newsForm.elements.title.value,
    slug: newsForm.elements.slug.value,
    excerpt: newsForm.elements.excerpt.value,
    content: newsForm.elements.content.value,
    category: newsForm.elements.category.value,
    tags: newsForm.elements.tags.value,
    featuredImage: newsForm.elements.featuredImage.value,
    status: newsForm.elements.status.value,
    publishedAt: newsForm.elements.publishedAt.value,
    isFeatured: newsForm.elements.isFeatured.checked,
  };
  const response = await fetch(id ? `/api/news/${id}` : "/api/news", {
    method: id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    newsResult.textContent = result.error || "No se pudo guardar la noticia.";
    newsResult.className = "import-result error";
    return;
  }
  newsResult.textContent = "Noticia guardada correctamente.";
  newsResult.className = "import-result ok";
  resetNewsForm();
  await loadNewsAdmin();
}

async function deleteNews(id) {
  if (!confirm("¿Eliminar esta noticia?")) return;
  const response = await fetch(`/api/news/${id}`, { method: "DELETE" });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo eliminar la noticia.");
    return;
  }
  if (newsForm.elements.id.value === String(id)) resetNewsForm();
  await loadNewsAdmin();
}

async function loadConfig() {
  if (!isAdmin()) return;
  const response = await fetch("/api/config");
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    usersBoard.innerHTML = `<div class="empty">No se pudo cargar la configuración.</div>`;
    return;
  }
  appState.config = await response.json();
  renderConfig();
}

function renderConfig() {
  renderUsersConfig();
  renderSettingsConfig();
}

function renderUsersConfig() {
  const users = appState.config?.users || [];
  if (!users.length) {
    usersBoard.innerHTML = `<div class="empty">No hay usuarios configurados.</div>`;
    return;
  }

  usersBoard.innerHTML = users.map((user) => `
    <article class="user-row ${user.active ? "" : "inactive"}">
      <div>
        <strong>${escapeHtml(user.display_name || user.username)}</strong>
        <span>${escapeHtml(user.username)} · ${escapeHtml(user.role === "admin" ? "Administrador" : "Revisión")}</span>
        <span>${escapeHtml(user.email || "Sin email")}</span>
      </div>
      <div class="card-actions">
        <button data-edit-user="${escapeHtml(user.username)}">Editar</button>
        <button class="danger" data-delete-user="${escapeHtml(user.username)}">${user.active ? "Dar de baja" : "Desactivado"}</button>
      </div>
    </article>
  `).join("");
}

function renderSettingsConfig() {
  const settings = appState.config?.settings || {};
  settingsForm.elements.maintenance_mode.checked = settings.maintenance_mode === "1";
  settingsForm.elements.smtp_host.value = settings.smtp_host || "";
  settingsForm.elements.smtp_port.value = settings.smtp_port || "587";
  settingsForm.elements.smtp_user.value = settings.smtp_user || "";
  settingsForm.elements.smtp_from.value = settings.smtp_from || "";
  settingsForm.elements.smtp_tls.checked = settings.smtp_tls !== "0";
  settingsForm.elements.smtp_ssl.checked = settings.smtp_ssl === "1";
  settingsForm.elements.smtp_password.placeholder = settings.smtp_password_set
    ? "Contraseña guardada, dejar vacío para no cambiar"
    : "Sin contraseña guardada";
  settingsForm.elements.smtp_password.value = "";
  settingsForm.elements.clear_smtp_password.checked = false;
}

function resetUserForm() {
  userConfigForm.reset();
  userConfigForm.elements.editing_username.value = "";
  userConfigForm.elements.username.disabled = false;
  userConfigForm.elements.active.checked = true;
}

function editUser(username) {
  const user = (appState.config?.users || []).find((entry) => entry.username === username);
  if (!user) return;
  userConfigForm.elements.editing_username.value = user.username;
  userConfigForm.elements.username.value = user.username;
  userConfigForm.elements.username.disabled = true;
  userConfigForm.elements.display_name.value = user.display_name || "";
  userConfigForm.elements.email.value = user.email || "";
  userConfigForm.elements.role.value = user.role || "nuria";
  userConfigForm.elements.password.value = "";
  userConfigForm.elements.active.checked = Boolean(user.active);
}

async function saveUserConfig(event) {
  event.preventDefault();
  if (!isAdmin()) return;

  const editing = userConfigForm.elements.editing_username.value;
  const payload = {
    username: userConfigForm.elements.username.value.trim(),
    display_name: userConfigForm.elements.display_name.value.trim(),
    email: userConfigForm.elements.email.value.trim(),
    role: userConfigForm.elements.role.value,
    password: userConfigForm.elements.password.value,
    active: userConfigForm.elements.active.checked,
  };
  if (editing && !payload.password) delete payload.password;

  const response = await fetch(editing ? `/api/config/users/${encodeURIComponent(editing)}` : "/api/config/users", {
    method: editing ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo guardar el usuario.");
    return;
  }
  appState.config = result;
  resetUserForm();
  renderConfig();
}

async function deleteUserConfig(username) {
  if (!confirm("¿Seguro que quieres dar de baja este usuario?")) return;
  const response = await fetch(`/api/config/users/${encodeURIComponent(username)}`, { method: "DELETE" });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo dar de baja el usuario.");
    return;
  }
  appState.config = result;
  renderConfig();
}

function settingsPayload() {
  const payload = {
    maintenance_mode: settingsForm.elements.maintenance_mode.checked ? "1" : "0",
    smtp_host: settingsForm.elements.smtp_host.value.trim(),
    smtp_port: settingsForm.elements.smtp_port.value.trim() || "587",
    smtp_user: settingsForm.elements.smtp_user.value.trim(),
    smtp_from: settingsForm.elements.smtp_from.value.trim(),
    smtp_tls: settingsForm.elements.smtp_tls.checked ? "1" : "0",
    smtp_ssl: settingsForm.elements.smtp_ssl.checked ? "1" : "0",
    clear_smtp_password: settingsForm.elements.clear_smtp_password.checked,
  };
  if (settingsForm.elements.smtp_password.value) {
    payload.smtp_password = settingsForm.elements.smtp_password.value;
  }
  return payload;
}

async function saveSettingsPayload() {
  const response = await fetch("/api/config/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settingsPayload()),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.error || "No se pudo guardar la configuración.");
  }
  appState.config = result;
  renderConfig();
  return result;
}

async function saveSettingsConfig(event) {
  event.preventDefault();
  if (!isAdmin()) return;

  settingsResult.textContent = "";
  try {
    await saveSettingsPayload();
  } catch (error) {
    settingsResult.className = "import-result error";
    settingsResult.textContent = error.message || "No se pudo guardar la configuración.";
    return;
  }
  settingsResult.className = "import-result ok";
  settingsResult.textContent = "Configuración guardada.";
}

async function testSmtpConfig() {
  if (!isAdmin()) return;

  const originalText = testSmtpButton.textContent;
  testSmtpButton.disabled = true;
  testSmtpButton.textContent = "Probando...";
  settingsResult.className = "import-result";
  settingsResult.textContent = "Guardando configuración y probando envío SMTP...";

  try {
    await saveSettingsPayload();
    settingsResult.className = "import-result";
    settingsResult.textContent = "Configuración guardada. Probando envío SMTP...";
    const response = await fetch("/api/config/test-smtp", { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      settingsResult.className = "import-result error";
      settingsResult.textContent = result.error || result.message || "No se pudo enviar el correo de prueba.";
      return;
    }
    settingsResult.className = "import-result ok";
    settingsResult.textContent = result.message || "Correo de prueba enviado correctamente.";
  } catch (error) {
    settingsResult.className = "import-result error";
    settingsResult.textContent = error.message || "No se pudo completar la prueba SMTP.";
  } finally {
    testSmtpButton.disabled = false;
    testSmtpButton.textContent = originalText;
  }
}

function renderCard(item) {
  const fechaLimite = [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ");
  const remainingDays = daysUntil(item.fecha_limite, item.hora_limite);
  const enlacePerfil = normalizeUrl(item.enlace_perfil);
  const enlaceInfonalia = normalizeUrl(item.enlace_infonalia);
  const monitorDetail = appState.monitorDetails[item.id] || null;
  const expanded = appState.expandedCards.has(String(item.id));
  const links = [
    enlacePerfil ? `<a href="${escapeHtml(enlacePerfil)}" target="_blank" rel="noreferrer">Perfil del contratante</a>` : "",
    enlaceInfonalia ? `<a href="${escapeHtml(enlaceInfonalia)}" target="_blank" rel="noreferrer">Anuncio Infonalia</a>` : "",
  ].filter(Boolean).join("");
  const stateActions = isAdmin() ? estadoOrden : nuriaEstados;
  const showActions = true;
  const showFooterState = !showActions || !stateActions.includes(item.estado);
  const dueText = dueLabel(remainingDays);

  return `
    <article class="card compact-card">
      <div class="card-layout">
        <div class="card-content">
          <div class="card-head">
            <div class="card-title-block">
              <p class="eyebrow">Expediente</p>
              <h2>${escapeHtml(item.expediente)}</h2>
              <p class="card-organismo">${escapeHtml(item.organismo)}</p>
              <p class="object">${escapeHtml(item.objeto || "Sin objeto informado")}</p>
            </div>
            <div class="card-flags">
              ${dueText ? `<span class="due-chip ${dueClass(remainingDays)}">${escapeHtml(dueText)}</span>` : ""}
              ${item.provincia ? `<span class="province-chip">${escapeHtml(item.provincia)}</span>` : ""}
              ${item.documentos_count ? `<span class="document-chip">${escapeHtml(item.documentos_count)} doc.</span>` : ""}
            </div>
          </div>

          <div class="details">
            <div class="detail"><span>Tipo</span>${escapeHtml(item.tipo)}</div>
            <div class="detail"><span>Presupuesto</span>${escapeHtml(formatMoney(item.presupuesto))}</div>
            <div class="detail"><span>Fecha límite</span>${escapeHtml(fechaLimite)}</div>
          </div>

          ${links ? `<div class="links">${links}</div>` : ""}

          <div class="card-actions state-actions">
            ${showActions ? stateActions.map((estado) => `
              <button class="${item.estado === estado ? "active-state" : ""}" data-id="${item.id}" data-estado="${escapeHtml(estado)}">${escapeHtml(estadoLabel(estado))}</button>
            `).join("") : ""}
            ${showFooterState ? `<span class="badge footer-state ${badgeClass(item.estado)}">${escapeHtml(estadoLabel(item.estado))}</span>` : ""}
          </div>
        </div>

        <div class="card-side-actions">
          ${isAdmin() ? `<button class="download-button" data-download-id="${item.id}">Descargar ficheros</button>` : ""}
          ${isAdmin() ? `<button data-monitor-id="${item.id}">Actualizar ficha desde URL</button>` : ""}
          <button data-preview-id="${item.id}">Vista preliminar por IA</button>
          ${isAdmin() ? `<button data-edit-id="${item.id}">Editar</button>` : ""}
          ${isAdmin() ? `<button data-duplicate-id="${item.id}">Duplicar</button>` : ""}
          ${isAdmin() ? `<button class="danger" data-delete-id="${item.id}">Borrar</button>` : ""}
          <button class="expand-button ${expanded ? "active-state" : ""}" data-toggle-details="${item.id}">
            ${expanded ? "Ocultar detalles" : "Ver detalles"}
          </button>
        </div>
      </div>

      ${expanded ? renderExpandedCard(item, monitorDetail) : ""}
    </article>
  `;
}

function renderExpandedCard(item, detail) {
  if (!detail) {
    return `<div class="card-expanded"><div class="empty">Cargando información ampliada...</div></div>`;
  }

  const monitor = detail.monitor || {};
  const documentos = detail.documentos || [];
  const preview = detail.preview || null;
  const monitorStatus = monitor.status || item.monitor_status || "Sin revisar";

  return `
    <div class="card-expanded">
      <div class="expanded-toolbar">
        <button class="secondary" data-open-monitor="${item.id}">Ver monitor de licitación</button>
        <span class="muted">${escapeHtml(monitorStatus)}${monitor.last_checked_at_formatted ? ` · Última revisión: ${escapeHtml(monitor.last_checked_at_formatted)}` : ""}</span>
      </div>

      <section class="expanded-panel">
          <p class="eyebrow">Ficheros disponibles</p>
          <h3>${documentos.length} documento(s)</h3>
          ${renderDocumentTable(documentos)}
      </section>

      <section class="expanded-panel ai-preview-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Vista preliminar por IA</p>
            <h3>${preview ? escapeHtml(preview.cabecera?.Expediente || item.expediente) : "Resumen pendiente"}</h3>
          </div>
          <button data-email-preview-id="${item.id}" ${preview ? "" : "disabled"}>Recibir por email</button>
        </div>
        ${preview ? renderPreview(preview) : `<div class="empty">Pulsa “Vista preliminar por IA” para generar el resumen.</div>`}
      </section>
    </div>
  `;
}

function documentTypeLabel(documento) {
  const ext = String(documento?.extension || "").replace(".", "").trim().toUpperCase();
  return ext ? `(${ext})` : "";
}

function documentDateLabel(documento) {
  return documento?.fecha_documento_formatted
    || documento?.fecha_documento
    || "";
}

function renderDocumentTable(documentos) {
  if (!documentos.length) {
    return `<div class="empty">No hay ficheros detectados. Pulsa “Actualizar ficha desde URL”.</div>`;
  }

  return `
    <div class="document-table-wrap">
      <table class="document-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Descripción</th>
            <th>Tipo</th>
          </tr>
        </thead>
        <tbody>
          ${documentos.map((documento) => `
            <tr>
              <td>${escapeHtml(documentDateLabel(documento) || "Sin fecha")}</td>
              <td>
                <a href="${escapeHtml(normalizeUrl(documento.url))}" target="_blank" rel="noreferrer">${escapeHtml(documento.titulo || "Documento")}</a>
                ${documento.seccion ? `<small>${escapeHtml(documento.seccion)}</small>` : ""}
              </td>
              <td>${escapeHtml(documentTypeLabel(documento))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderMonitorInfo(item, detail) {
  const monitor = detail?.monitor || {};
  const eventos = detail?.eventos || [];
  const monitorStatus = monitor.status || item?.monitor_status || "Sin revisar";

  return `
    <div class="monitor-status-grid">
      <div>
        <p class="eyebrow">Estado</p>
        <h3>${escapeHtml(monitorStatus)}</h3>
      </div>
      <div>
        <p class="eyebrow">Última revisión</p>
        <h3>${escapeHtml(monitor.last_checked_at_formatted || "Sin revisar")}</h3>
      </div>
    </div>
    ${monitor.page_title ? `<p><strong>Ficha:</strong> ${escapeHtml(monitor.page_title)}</p>` : ""}
    ${monitor.url ? `<p><strong>URL:</strong> <a href="${escapeHtml(normalizeUrl(monitor.url))}" target="_blank" rel="noreferrer">${escapeHtml(monitor.url)}</a></p>` : ""}
    ${monitor.error ? `<p class="notification-warning">${escapeHtml(monitor.error)}</p>` : ""}
    <div class="event-list">
      ${eventos.length ? eventos.map((event) => `
        <div class="event-row">
          <span>${escapeHtml(event.fecha_hora_formatted || event.fecha_hora)}</span>
          <strong>${escapeHtml(event.resumen)}</strong>
        </div>
      `).join("") : `<div class="empty">Todavía no hay eventos registrados para esta ficha.</div>`}
    </div>
  `;
}

async function openMonitorDialog(id) {
  if (!appState.monitorDetails[id]) {
    monitorDialogContent.innerHTML = `<div class="empty">Cargando monitor...</div>`;
    monitorDialog.showModal();
    await loadMonitorDetails(id);
  }
  const item = appState.items.find((row) => String(row.id) === String(id)) || {};
  monitorDialogTitle.textContent = item.expediente ? `Monitor ${item.expediente}` : "Revisión de plataforma";
  monitorDialogContent.innerHTML = renderMonitorInfo(item, appState.monitorDetails[id]);
  if (!monitorDialog.open) monitorDialog.showModal();
}

function renderPreview(preview) {
  const cabecera = preview.cabecera || {};
  const rows = Object.entries(cabecera).filter(([, value]) => value);
  const list = (items) => items?.length
    ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : `<p class="muted">No detectado en la ficha disponible.</p>`;

  return `
    <div class="preview-grid">
      <div class="preview-box">
        <p class="eyebrow">Cabecera</p>
        ${rows.map(([key, value]) => `<p><strong>${escapeHtml(key)}:</strong> ${escapeHtml(value)}</p>`).join("")}
      </div>
      <div class="preview-box">
        <p class="eyebrow">Centros</p>
        ${list(preview.centros)}
      </div>
      <div class="preview-box">
        <p class="eyebrow">Lotes e importes</p>
        ${list(preview.lotes)}
      </div>
      <div class="preview-box">
        <p class="eyebrow">Criterios de adjudicación</p>
        ${list(preview.criterios_adjudicacion)}
      </div>
      <div class="preview-box">
        <p class="eyebrow">Criterios especiales de ejecución</p>
        ${list(preview.criterios_ejecucion)}
      </div>
      <div class="preview-box preview-summary">
        <p class="eyebrow">Resumen generado por IA</p>
        <p>${escapeHtml(preview.resumen || "")}</p>
        <small>${escapeHtml(preview.nota || "")}</small>
      </div>
    </div>
  `;
}

async function updateEstado(id, estado) {
  const response = await fetch(`/api/licitaciones/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estado }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo actualizar el estado.");
    return;
  }
  await loadItems();
}

async function markDayReviewed() {
  if (!appState.currentDiaId || reviewDayButton.disabled) return;

  const action = reviewDayButton.dataset.reviewAction || "mark";
  const endpoint = action === "unmark"
    ? `/api/dias/${appState.currentDiaId}/desmarcar-revisado`
    : `/api/dias/${appState.currentDiaId}/revisado`;
  const loadingText = action === "unmark" ? "Desmarcando..." : "Marcando...";

  reviewDayButton.disabled = true;
  reviewDayButton.textContent = loadingText;
  let success = false;
  try {
    const response = await fetch(endpoint, { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      alert(result.error || "No se pudo actualizar la marca de revisión.");
      return;
    }
    success = true;
    appState.nuriaDaysView = "pending";
    showDaysView();
  } finally {
    if (!success) renderReviewButton();
  }
}

async function sendDayToNuria() {
  if (!appState.currentDiaId || sendNuriaButton.disabled) return;

  sendNuriaButton.disabled = true;
  sendNuriaButton.textContent = "Enviando...";
  try {
    const response = await fetch(`/api/dias/${appState.currentDiaId}/enviar-nuria`, { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      alert(result.error || "No se pudo enviar el día a revisión.");
      return;
    }
    await loadDias();
    await loadItems();
  } finally {
    renderSendNuriaButton();
  }
}

async function downloadLicitacion(id, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Descargando...";

  try {
    const response = await fetch(`/api/licitaciones/${id}/descargar`, { method: "POST" });
    const result = await response.json();
    if (!response.ok) {
      alert(result.error || result.salida || "No se pudo completar la descarga.");
      return;
    }
    alert(`Descarga completada.\n\nCarpeta:\n${result.carpeta}`);
    await loadItems();
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function loadMonitorDetails(id) {
  const response = await fetch(`/api/licitaciones/${id}/monitor`);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    appState.monitorDetails[id] = { monitor: { status: "Error", error: result.error || "No se pudo cargar la información ampliada." }, documentos: [], eventos: [] };
    return;
  }
  appState.monitorDetails[id] = { ...(appState.monitorDetails[id] || {}), ...result };
}

async function toggleDetails(id) {
  const key = String(id);
  if (appState.expandedCards.has(key)) {
    appState.expandedCards.delete(key);
    renderBoard();
    return;
  }
  appState.expandedCards.add(key);
  if (!appState.monitorDetails[id]) {
    renderBoard();
    await loadMonitorDetails(id);
  }
  renderBoard();
}

async function runMonitor(id, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Actualizando...";
  appState.expandedCards.add(String(id));
  try {
    const response = await fetch(`/api/licitaciones/${id}/monitor`, { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      appState.monitorDetails[id] = result.monitor || { monitor: { status: "Error", error: result.error || "No se pudo actualizar la ficha." }, documentos: [], eventos: [] };
      alert(result.error || "No se pudo actualizar la ficha.");
    } else {
      appState.monitorDetails[id] = result.monitor;
    }
    await loadItems();
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function generatePreview(id, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Generando...";
  appState.expandedCards.add(String(id));
  if (!appState.monitorDetails[id]) {
    await loadMonitorDetails(id);
  }
  try {
    const response = await fetch(`/api/licitaciones/${id}/ia-preview`, { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      alert(result.error || "No se pudo generar la vista preliminar.");
      return;
    }
    appState.monitorDetails[id] = { ...(appState.monitorDetails[id] || {}), preview: result.preview };
    renderBoard();
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function emailPreview(id, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Enviando...";
  try {
    const response = await fetch(`/api/licitaciones/${id}/ia-preview/email`, { method: "POST" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      alert(result.error || "No se pudo enviar la vista preliminar.");
      return;
    }
    alert(result.message || "Vista preliminar enviada.");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function openCreateEditor() {
  form.reset();
  form.elements.id.value = "";
  editorEyebrow.textContent = "Alta manual";
  editorTitle.textContent = "Nueva licitación";
  form.elements.estado.value = "Pendiente";
  editor.showModal();
}

function openEditEditor(id) {
  const item = [...appState.items, ...appState.calendarItems].find((entry) => String(entry.id) === String(id));
  if (!item) return;

  form.reset();
  editorEyebrow.textContent = "Edición";
  editorTitle.textContent = `Editar ${item.expediente || "licitación"}`;

  editorFields.forEach((field) => {
    if (form.elements[field]) form.elements[field].value = item[field] ?? "";
  });

  editor.showModal();
}

function openDuplicateEditor(id) {
  const item = [...appState.items, ...appState.calendarItems].find((entry) => String(entry.id) === String(id));
  if (!item) return;

  form.reset();
  editorEyebrow.textContent = "Alta manual";
  editorTitle.textContent = `Nueva licitación desde ${item.expediente || "licitación"}`;

  editorFields.forEach((field) => {
    if (!form.elements[field]) return;
    form.elements[field].value = field === "id" ? "" : item[field] ?? "";
  });

  editor.showModal();
}

async function deleteLicitacion(id) {
  if (!confirm("¿Seguro que quieres borrar esta licitación?")) return;

  const response = await fetch(`/api/licitaciones/${id}`, { method: "DELETE" });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo borrar la licitación.");
    return;
  }
  await loadItems();
  await loadDias();
}

async function deleteDia(id, title) {
  if (!isAdmin()) return;
  const confirmation = window.prompt(
    `Vas a borrar el día "${title || "Infonalia"}" y todas sus licitaciones.\n\nEscribe Borrar para confirmar.`
  );
  if ((confirmation || "").trim() !== "Borrar") return;

  const response = await fetch(`/api/dias/${id}`, { method: "DELETE" });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo borrar el día Infonalia.");
    return;
  }

  if (String(appState.currentDiaId) === String(id)) {
    appState.currentDiaId = "";
    appState.currentDiaTitle = "Todas las licitaciones";
  }
  await loadDias();
  showDaysView();
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

document.getElementById("days-button").addEventListener("click", showDaysView);
document.getElementById("list-button").addEventListener("click", () => showLicitacionesView({ view: "live" }));
document.getElementById("calendar-button").addEventListener("click", showCalendarView);
document.getElementById("notifications-button").addEventListener("click", showNotificationsView);
document.getElementById("back-from-notifications").addEventListener("click", backFromNotifications);
document.getElementById("news-admin-button").addEventListener("click", showNewsAdminView);
document.getElementById("config-button").addEventListener("click", showConfigView);
document.getElementById("back-from-config").addEventListener("click", backFromConfig);
document.getElementById("back-to-days").addEventListener("click", showDaysView);
reviewDayButton.addEventListener("click", markDayReviewed);
sendNuriaButton.addEventListener("click", sendDayToNuria);
licitacionesTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-licitaciones-view]");
  if (!button) return;
  appState.licitacionesView = button.dataset.licitacionesView;
  renderLicitacionesTabs();
  loadItems();
});
nuriaDaysTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-nuria-days-view]");
  if (!button) return;
  appState.nuriaDaysView = button.dataset.nuriaDaysView;
  renderNuriaDaysTabs();
  renderDaysSummary();
  renderDays();
});
document.getElementById("new-button").addEventListener("click", openCreateEditor);
document.getElementById("close-editor").addEventListener("click", () => editor.close());
document.getElementById("cancel-editor").addEventListener("click", () => editor.close());
document.getElementById("import-button").addEventListener("click", () => {
  importResult.textContent = "";
  importer.showModal();
});
document.getElementById("close-importer").addEventListener("click", () => importer.close());
document.getElementById("cancel-importer").addEventListener("click", () => importer.close());
document.getElementById("close-monitor-dialog").addEventListener("click", () => monitorDialog.close());
document.getElementById("accept-monitor-dialog").addEventListener("click", () => monitorDialog.close());
stateFilter.addEventListener("change", loadItems);
dateOrder.addEventListener("change", loadItems);
searchInput.addEventListener("input", debounce(loadItems, 250));
calendarSearch.addEventListener("input", debounce(renderCalendar, 250));
calendarStateFilter.addEventListener("change", renderCalendar);
document.getElementById("calendar-prev").addEventListener("click", () => {
  appState.calendarDate = addMonths(appState.calendarDate, -1);
  appState.calendarSelectedDate = dateKey(appState.calendarDate);
  renderCalendar();
});
document.getElementById("calendar-next").addEventListener("click", () => {
  appState.calendarDate = addMonths(appState.calendarDate, 1);
  appState.calendarSelectedDate = dateKey(appState.calendarDate);
  renderCalendar();
});
document.getElementById("calendar-today").addEventListener("click", () => {
  const today = new Date();
  appState.calendarDate = new Date(today.getFullYear(), today.getMonth(), 1);
  appState.calendarSelectedDate = dateKey(today);
  renderCalendar();
});
notificationSearch.addEventListener("input", debounce(loadNotifications, 250));
notificationScope.addEventListener("change", loadNotifications);
notificationDestination.addEventListener("change", loadNotifications);
notificationEmailState.addEventListener("change", loadNotifications);
newsForm.addEventListener("submit", saveNews);
document.getElementById("reset-news-form").addEventListener("click", resetNewsForm);
userConfigForm.addEventListener("submit", saveUserConfig);
settingsForm.addEventListener("submit", saveSettingsConfig);
testSmtpButton.addEventListener("click", testSmtpConfig);
document.getElementById("reset-user-form").addEventListener("click", resetUserForm);

usersBoard.addEventListener("click", (event) => {
  const editButton = event.target.closest("button[data-edit-user]");
  if (editButton) {
    editUser(editButton.dataset.editUser);
    return;
  }
  const deleteButton = event.target.closest("button[data-delete-user]");
  if (deleteButton) {
    deleteUserConfig(deleteButton.dataset.deleteUser);
  }
});

newsAdminBoard.addEventListener("click", (event) => {
  const editButton = event.target.closest("button[data-edit-news]");
  if (editButton) {
    editNews(editButton.dataset.editNews);
    return;
  }
  const deleteButton = event.target.closest("button[data-delete-news]");
  if (deleteButton) {
    deleteNews(deleteButton.dataset.deleteNews);
  }
});

daysBoard.addEventListener("click", (event) => {
  const deleteButton = event.target.closest("button[data-delete-dia]");
  if (deleteButton) {
    deleteDia(deleteButton.dataset.deleteDia, deleteButton.dataset.title);
    return;
  }

  const button = event.target.closest("button[data-open-dia]");
  if (!button) return;
  showLicitacionesView({ diaId: button.dataset.openDia, title: button.dataset.title });
});

board.addEventListener("click", (event) => {
  const downloadButton = event.target.closest("button[data-download-id]");
  if (downloadButton) {
    downloadLicitacion(downloadButton.dataset.downloadId, downloadButton);
    return;
  }

  const monitorButton = event.target.closest("button[data-monitor-id]");
  if (monitorButton) {
    runMonitor(monitorButton.dataset.monitorId, monitorButton);
    return;
  }

  const previewButton = event.target.closest("button[data-preview-id]");
  if (previewButton) {
    generatePreview(previewButton.dataset.previewId, previewButton);
    return;
  }

  const emailPreviewButton = event.target.closest("button[data-email-preview-id]");
  if (emailPreviewButton) {
    emailPreview(emailPreviewButton.dataset.emailPreviewId, emailPreviewButton);
    return;
  }

  const openMonitorButton = event.target.closest("button[data-open-monitor]");
  if (openMonitorButton) {
    openMonitorDialog(openMonitorButton.dataset.openMonitor);
    return;
  }

  const detailsButton = event.target.closest("button[data-toggle-details]");
  if (detailsButton) {
    toggleDetails(detailsButton.dataset.toggleDetails);
    return;
  }

  const editButton = event.target.closest("button[data-edit-id]");
  if (editButton) {
    openEditEditor(editButton.dataset.editId);
    return;
  }

  const duplicateButton = event.target.closest("button[data-duplicate-id]");
  if (duplicateButton) {
    openDuplicateEditor(duplicateButton.dataset.duplicateId);
    return;
  }

  const deleteButton = event.target.closest("button[data-delete-id]");
  if (deleteButton) {
    deleteLicitacion(deleteButton.dataset.deleteId);
    return;
  }

  const button = event.target.closest("button[data-id]");
  if (!button) return;
  updateEstado(button.dataset.id, button.dataset.estado);
});

calendarBoard.addEventListener("click", (event) => {
  const day = event.target.closest("[data-calendar-date]");
  if (!day) return;
  appState.calendarSelectedDate = day.dataset.calendarDate;
  renderCalendar();
});

calendarRadar.addEventListener("click", (event) => {
  const day = event.target.closest("[data-calendar-date]");
  if (!day) return;
  const parsed = parseDate(day.dataset.calendarDate);
  if (parsed) appState.calendarDate = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
  appState.calendarSelectedDate = day.dataset.calendarDate;
  renderCalendar();
});

calendarDayPanel.addEventListener("click", (event) => {
  const editButton = event.target.closest("button[data-calendar-edit]");
  if (editButton) {
    openEditEditor(editButton.dataset.calendarEdit);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!isAdmin()) return;

  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  delete data.id;

  const response = await fetch(id ? `/api/licitaciones/${id}` : "/api/licitaciones", {
    method: id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    alert(error.error || "No se pudo guardar la licitación.");
    return;
  }

  form.reset();
  editor.close();
  await loadDias();
  if (appState.lastSection === "calendar") {
    await loadCalendarItems();
    return;
  }
  showLicitacionesView({ diaId: appState.currentDiaId, title: appState.currentDiaTitle });
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!isAdmin()) return;

  const fileInput = importForm.elements.import_file;
  const file = fileInput?.files?.[0];
  if (!file) {
    importResult.textContent = "Selecciona un fichero para importar.";
    importResult.className = "import-result error";
    return;
  }

  const lowerName = file.name.toLowerCase();
  const isCsv = lowerName.endsWith(".csv");
  const isMsg = lowerName.endsWith(".msg");
  if (!isCsv && !isMsg) {
    importResult.textContent = "Formato no reconocido. Selecciona un fichero .msg o .csv.";
    importResult.className = "import-result error";
    return;
  }

  const formData = new FormData();
  if (isMsg) {
    formData.append("msg_file", file);
    const enrich = importForm.elements.enrich_pdf;
    if (enrich?.checked) formData.append("enrich_pdf", "on");
  } else {
    formData.append("csv_file", file);
  }

  const endpoint = isMsg ? "/api/import/msg" : "/api/import/csv";
  const submit = importForm.querySelector("button[type='submit']");
  submit.disabled = true;
  submit.textContent = "Importando...";
  importResult.textContent = "";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    if (!response.ok) {
      importResult.textContent = result.error || "No se pudo importar el fichero.";
      importResult.className = "import-result error";
      return;
    }

    importResult.className = "import-result ok";
    importResult.textContent = isMsg
      ? `Días: ${result.dias || 0}. Importadas: ${result.importadas}. Actualizadas: ${result.actualizadas || 0}. Omitidas: ${result.omitidas}.`
      : `Días: ${result.dias || 0}. Importadas: ${result.importadas}. Actualizadas: ${result.actualizadas || 0}. Omitidas: ${result.omitidas}. Sin expediente: ${result.sin_expediente}.`;
    importForm.reset();
    await loadDias();
    if (appState.lastSection === "calendar") await loadCalendarItems();
  } finally {
    submit.disabled = false;
    submit.textContent = "Importar";
  }
});

loadMe().then(showDaysView);
