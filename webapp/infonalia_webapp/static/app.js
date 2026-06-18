const appState = {
  user: null,
  csrfToken: "",
  dias: [],
  items: [],
  estados: [],
  totals: {},
  currentDiaId: "",
  currentDiaTitle: "Centro de licitaciones",
  currentDayPendingReview: null,
  currentDayPendingAdmin: null,
  currentDaySentNuriaAt: "",
  currentDayNuriaDirtyAt: "",
  currentDayNuriaPendingUpdate: false,
  currentDayReviewedAt: "",
  currentDayNuriaTotal: null,
  calendarItems: [],
  agendaGroups: {},
  agendaSummary: {},
  agendaWorkbench: null,
  agendaWorkbenchSelectedKey: "",
  agendaActiveDateLabel: "",
  agendaIsToday: false,
  agendaView: "day",
  agendaType: "all",
  newsItems: [],
  monitorRuns: [],
  actuaciones: [],
  actuacionesSummary: {},
  actuacionSelectedLicitaciones: [],
  actuacionSelectorResults: [],
  actuacionSelectorDraft: new Map(),
  calendarDate: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  calendarSelectedDate: "",
  nuriaDaysView: "pending",
  licitacionesView: "live",
  lastSection: "days",
  config: null,
  storage: null,
  expandedCards: new Set(),
  cardDetails: {},
};

const daysSection = document.getElementById("days-section");
const licitacionesSection = document.getElementById("licitaciones-section");
const calendarSection = document.getElementById("calendar-section");
const actuacionesSection = document.getElementById("actuaciones-section");
const notificationsSection = document.getElementById("notifications-section");
const newsAdminSection = document.getElementById("news-admin-section");
const monitorSection = document.getElementById("monitor-section");
const configSection = document.getElementById("config-section");
const daysBoard = document.getElementById("days-board");
const daysSummary = document.getElementById("days-summary");
const nuriaDaysTabs = document.getElementById("nuria-days-tabs");
const licitacionesTabs = document.getElementById("licitaciones-tabs");
const board = document.getElementById("board");
const summary = document.getElementById("summary");
const stateFilter = document.getElementById("state-filter");
const dateOrder = document.getElementById("date-order");
const licitacionesActuacionesFilter = document.getElementById("licitaciones-actuaciones-filter");
const licitacionesQuickFilter = document.getElementById("licitaciones-quick-filter");
const searchInput = document.getElementById("search");
const currentDayTitle = document.getElementById("current-day-title");
const reviewDayButton = document.getElementById("review-day-button");
const sendNuriaButton = document.getElementById("send-nuria-button");
const calendarMonthTitle = document.getElementById("calendar-month-title");
const calendarSearch = document.getElementById("calendar-search");
const calendarStateFilter = document.getElementById("calendar-state-filter");
const agendaWorkbench = document.getElementById("agenda-workbench");
const calendarSummary = document.getElementById("calendar-summary");
const calendarRadar = document.getElementById("calendar-radar");
const calendarBoard = document.getElementById("calendar-board");
const calendarDayPanel = document.getElementById("calendar-day-panel");
const agendaEventDialog = document.getElementById("agenda-event-dialog");
const agendaEventForm = document.getElementById("agenda-event-form");
const agendaEventFormTitle = document.getElementById("agenda-event-form-title");
const agendaEventDateWarning = document.getElementById("agenda-event-date-warning");
const actuacionesBoard = document.getElementById("actuaciones-board");
const actuacionesSummary = document.getElementById("actuaciones-summary");
const actuacionesFilter = document.getElementById("actuaciones-filter");
const actuacionDialog = document.getElementById("actuacion-dialog");
const actuacionForm = document.getElementById("actuacion-form");
const actuacionFormTitle = document.getElementById("actuacion-form-title");
const actuacionLicitacionesSummary = document.getElementById("actuacion-licitaciones-summary");
const actuacionSelectedLicitaciones = document.getElementById("actuacion-selected-licitaciones");
const actuacionHistoryPanel = document.getElementById("actuacion-history-panel");
const actuacionHistory = document.getElementById("actuacion-history");
const actuacionComment = document.getElementById("actuacion-comment");
const actuacionDateWarning = document.getElementById("actuacion-date-warning");
const licitacionSelectorDialog = document.getElementById("licitacion-selector-dialog");
const licitacionSelectorForm = document.getElementById("licitacion-selector-form");
const licitacionSelectorSearch = document.getElementById("licitacion-selector-search");
const licitacionSelectorResults = document.getElementById("licitacion-selector-results");
const notificationsBoard = document.getElementById("notifications-board");
const newsAdminBoard = document.getElementById("news-admin-board");
const monitorRunsBoard = document.getElementById("monitor-runs-board");
const monitorRunDetail = document.getElementById("monitor-run-detail");
const monitorTaskTypeFilter = document.getElementById("monitor-task-type-filter");
const monitorActionResult = document.getElementById("monitor-action-result");
const monitorSendAgendaSummaryButton = document.getElementById("monitor-send-agenda-summary");
const monitorSendAgendaDailyButton = document.getElementById("monitor-send-agenda-daily");
const monitorSendAgendaWeeklyButton = document.getElementById("monitor-send-agenda-weekly");
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
const capturePlatformButton = document.getElementById("capture-platform-button");
const capturePlatformResult = document.getElementById("capture-platform-result");
const licitacionDetailDialog = document.getElementById("licitacion-detail-dialog");
const licitacionDetailTitle = document.getElementById("licitacion-detail-title");
const licitacionDetailContent = document.getElementById("licitacion-detail-content");
const importer = document.getElementById("importer");
const importForm = document.getElementById("import-form");
const importResult = document.getElementById("import-result");
const userConfigForm = document.getElementById("user-config-form");
const usersBoard = document.getElementById("users-board");
const settingsForm = document.getElementById("settings-form");
const settingsResult = document.getElementById("settings-result");
const testSmtpButton = document.getElementById("test-smtp-button");
const storageStatusBoard = document.getElementById("storage-status-board");
const storageResult = document.getElementById("storage-result");
const testDropboxButton = document.getElementById("test-dropbox-button");
const dryRunDropboxButton = document.getElementById("dry-run-dropbox-button");
const syncDropboxMarkersButton = document.getElementById("sync-dropbox-markers-button");
const monitorDryRunButton = document.getElementById("monitor-dry-run-button");
const monitorRepairButton = document.getElementById("monitor-repair-button");
const refreshMonitorRunsButton = document.getElementById("refresh-monitor-runs");
const pageTitle = document.getElementById("page-title");
const pageKicker = document.getElementById("page-kicker");
const sessionUser = document.getElementById("session-user");
const logoutButton = document.getElementById("logout-button");

const estadoOrden = [
  "Importada",
  "Descartada",
  "Enviada a Nuria",
  "Descargar para ver",
  "Preparar ficha",
  "Preparada",
  "Oferta enviada",
];

const estadoLabels = {
  "Importada": "Importada",
  "Descartada": "Descartada",
  "Enviada a Nuria": "Enviada a Nuria",
  "Descargar para ver": "Descargar para ver",
  "Preparar ficha": "Preparar ficha",
  "Preparada": "Preparada",
  "Oferta enviada": "Oferta enviada",
};

const monitorTaskTypeLabels = {
  licitaciones: "Licitaciones",
  resumen_agenda: "Resumen agenda",
  agenda_diaria: "Agenda diaria",
  agenda_semanal: "Agenda semanal",
  aviso_vencimiento_7d: "Aviso 7 días",
  aviso_vencimiento_3d: "Aviso 3 días",
  aviso_vencimiento_1d: "Aviso mañana",
  aviso_vencimiento_hoy: "Aviso hoy",
  avisos_vencimientos: "Avisos vencimientos",
  tareas_pendientes: "Tareas pendientes",
  monitor_licitaciones: "Monitor licitaciones",
  otro: "Otro",
};

const adminReviewEstados = ["Descartada", "Enviada a Nuria"];
const nuriaEstados = ["Descartada", "Descargar para ver", "Preparar ficha"];
const nuriaDefaultReviewEstados = ["Enviada a Nuria", "Descargar para ver", "Preparar ficha", "Preparada", "Oferta enviada"];
const nuriaVisibleEstados = [...nuriaDefaultReviewEstados, "Descartada"];
const nuriaLicitacionesEstados = ["Descargar para ver", "Preparar ficha", "Preparada"];
const calendarioEstados = ["Descargar para ver", "Preparar ficha", "Preparada"];
const nuriaDayFilterOptions = [
  { value: "__nuria_active", label: "No descartadas", filter: "active" },
  { value: "__nuria_all", label: "Todas", filter: "all" },
  { value: "__nuria_discarded", label: "Descartadas", filter: "discarded" },
];
const estadosInternos = [
  "Nueva",
  "Pendiente revisión",
  "En estudio",
  "Preparando oferta",
  "Presentada",
  "En seguimiento",
  "Descartada",
  "Finalizada",
];
const actuacionTipoLabels = {
  requerimiento: "Requerimiento",
  subsanacion: "Subsanación",
  aclaracion: "Aclaración",
  documentacion_adicional: "Documentación adicional",
  justificacion_baja: "Justificación baja",
  garantia_definitiva: "Garantía definitiva",
  firma_contrato: "Firma contrato",
  presentacion_oferta: "Presentación oferta",
  visita_tecnica: "Visita técnica",
  apertura_mesa: "Apertura mesa",
  consulta_organo: "Consulta órgano",
  recurso_alegaciones: "Recurso / alegaciones",
  revision_interna: "Revisión interna",
  comunicacion_cliente: "Comunicación cliente",
  seguimiento: "Seguimiento",
  otro: "Otro",
};
const actuacionEstadoLabels = {
  pendiente: "Pendiente",
  en_curso: "Pendiente",
  preparado: "Preparado",
  preparada: "Preparado",
  respondida: "Enviado",
  cerrada: "Enviado",
  cerrado: "Enviado",
  enviado: "Enviado",
  enviada: "Enviado",
  cancelado: "Cancelado",
  cancelada: "Cancelado",
};
const actuacionVisualLabels = {
  vencida: "Vencida",
  vence_hoy: "Vence hoy",
  vence_esta_semana: "Esta semana",
  sin_fecha: "Sin fecha",
  cerrada_fuera_de_plazo: "Cerrada fuera de plazo",
  cerrado: "Enviado",
  cerrada: "Enviado",
  enviado: "Enviado",
  enviada: "Enviado",
  cancelado: "Cancelado",
  cancelada: "Cancelado",
  pendiente: "Pendiente",
  preparado: "Preparado",
};
const agendaTypeLabels = {
  actuacion: "Actuación",
  licitacion: "Licitación",
  interno: "Interno",
  vencido: "Vencido",
  sin_fecha: "Sin fecha",
};
const agendaColorTypes = new Set(["actuacion", "licitacion", "interno", "vencido"]);
const agendaStatusLabels = {
  pendiente: "Pendiente",
  en_curso: "Pendiente",
  preparado: "Preparado",
  preparada: "Preparado",
  respondida: "Enviado",
  cerrado: "Enviado",
  cerrada: "Enviado",
  enviado: "Enviado",
  enviada: "Enviado",
  cancelado: "Cancelado",
  cancelada: "Cancelado",
};
const taskStateOptions = [
  { value: "pendiente", label: "Pendiente" },
  { value: "preparado", label: "Preparado" },
  { value: "enviado", label: "Enviado" },
  { value: "cancelado", label: "Cancelado" },
];
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
const captureFieldTargets = {
  expediente: "expediente",
  objeto: "objeto",
  organismo: "organismo",
  organo_contratacion: "organismo",
  provincia: "provincia",
  tipo: "tipo",
  presupuesto: "presupuesto",
  fecha_limite: "fecha_limite",
  hora_limite: "hora_limite",
  plataforma: "plataforma",
  enlace_perfil: "enlace_perfil",
};
const captureFieldLabels = {
  expediente: "Expediente",
  objeto: "Objeto",
  organismo: "Órgano de contratación",
  organo_contratacion: "Órgano de contratación",
  provincia: "Provincia/lugar",
  tipo: "Tipo",
  presupuesto: "Presupuesto",
  fecha_limite: "Fecha límite",
  fecha_presentacion: "Fecha límite",
  hora_limite: "Hora límite",
  plataforma: "Plataforma",
  enlace_perfil: "Enlace plataforma",
  procedimiento: "Procedimiento",
  cpv: "CPV",
  estado_licitacion: "Estado plataforma",
  valor_estimado: "Valor estimado",
  duracion: "Duración/plazo",
};

function isAdmin() {
  return appState.user?.role === "admin";
}

function isNuria() {
  return appState.user?.role === "nuria";
}

function isNuriaDayReview() {
  return Boolean(appState.currentDiaId) && isNuria();
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

function formatDateTime(value) {
  if (!value) return "";
  const [datePart, timePart = ""] = String(value).split("T");
  const time = timePart.slice(0, 5);
  return [formatDate(datePart), time].filter(Boolean).join(" ");
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

function cssClassToken(value, fallback = "Pendiente") {
  const token = String(value || fallback)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return token || fallback;
}

function badgeClass(value) {
  return cssClassToken(value, "Pendiente");
}

function estadoLabel(value) {
  return estadoLabels[value] || value || "";
}

function estadoActionLabel(value) {
  if (value === "Descartada") return "Descartar";
  if (value === "Enviada a Nuria") return "Enviar a Nuria para revisión";
  if (value === "Descargar para ver") return "Descargar para ver";
  if (value === "Preparar ficha") return "Preparar ficha";
  return estadoLabel(value);
}

function normalizedTaskStateValue(value) {
  const key = String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
  if (["preparado", "preparada"].includes(key)) return "preparado";
  if (["respondida", "cerrado", "cerrada", "enviado", "enviada"].includes(key)) return "enviado";
  if (["cancelado", "cancelada"].includes(key)) return "cancelado";
  return "pendiente";
}

function normalizeUrl(value) {
  const url = String(value ?? "").trim();
  if (!url) return "";
  const lower = url.toLowerCase();
  if (lower.startsWith("http://") || lower.startsWith("https://")) {
    return url;
  }
  if (url.startsWith("//")) return "";
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return "";
  if (url.startsWith("/") || url.startsWith("#")) return url;
  if (/^[a-z0-9.-]+\.[a-z]{2,}([/:?#].*)?$/i.test(url)) return `https://${url}`;
  return "";
}

function applyRoleUi() {
  document.body.classList.toggle("is-admin", isAdmin());
  document.body.classList.toggle("is-nuria", !isAdmin());
  document.querySelectorAll("[data-admin-only]").forEach((element) => {
    element.hidden = !isAdmin();
  });
  nuriaDaysTabs.hidden = false;
  document.getElementById("list-button").textContent = "Centro de licitaciones";
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
  appState.csrfToken = data.csrf_token || "";
  Object.assign(estadoLabels, data.labels || {});
  applyRoleUi();
}

function csrfHeaders() {
  return appState.csrfToken ? { "X-CSRF-Token": appState.csrfToken } : {};
}

async function logout() {
  if (logoutButton) logoutButton.disabled = true;
  try {
    const response = await fetch("/logout", {
      method: "POST",
      headers: csrfHeaders(),
    });
    if (!response.ok && !response.redirected) {
      const result = await response.json().catch(() => ({}));
      alert(result.error || "No se pudo cerrar la sesión.");
      return;
    }
    location.href = "/login";
  } finally {
    if (logoutButton) logoutButton.disabled = false;
  }
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
  appState.currentDiaTitle = "Centro de licitaciones";
  appState.lastSection = "days";
  setActiveNav("days");
  setPageHeader("Días Infonalia", "Revisión");
  daysSection.hidden = false;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = true;
  loadDias();
}

function showLicitacionesView({ diaId = "", title = "Centro de licitaciones", view = "live" } = {}) {
  appState.currentDiaId = diaId;
  appState.currentDiaTitle = title;
  appState.licitacionesView = diaId ? "all" : view;
  if (diaId && isNuria()) stateFilter.value = "__nuria_active";
  if (!diaId) dateOrder.value = appState.licitacionesView === "live" ? "asc" : "desc";
  currentDayTitle.textContent = title;
  appState.lastSection = "licitaciones";
  setActiveNav("licitaciones");
  setPageHeader(diaId ? "Revisión de día" : "Centro de licitaciones", diaId ? title : "Bandeja");
  daysSection.hidden = true;
  licitacionesSection.hidden = false;
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = true;
  renderLicitacionesTabs();
  loadItems();
}

function showCalendarView() {
  const todayKey = dateKey(new Date());
  if (!isAdmin() && appState.agendaView === "pending") appState.agendaView = "day";
  if (!appState.calendarSelectedDate) appState.calendarSelectedDate = todayKey;
  appState.lastSection = "calendar";
  setActiveNav("calendar");
  setPageHeader("Agenda", isAdmin() ? "Tareas pendientes / Hoy / Semana / Calendario / Todo" : "Hoy / Semana / Calendario / Todo");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = false;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = true;
  loadCalendarItems();
}

function showInitialView() {
  if (isAdmin()) {
    appState.agendaView = "pending";
    appState.calendarSelectedDate = dateKey(new Date());
    showCalendarView();
    return;
  }
  showDaysView();
}

function showActuacionesView() {
  appState.lastSection = "actuaciones";
  setActiveNav("actuaciones");
  setPageHeader("Actuaciones", "Actuaciones y vencimientos");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  actuacionesSection.hidden = false;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = true;
  loadActuaciones();
}

function showNotificationsView() {
  setActiveNav("notifications");
  setPageHeader("Buzón", "Notificaciones");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = false;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
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
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = false;
  monitorSection.hidden = true;
  configSection.hidden = true;
  loadNewsAdmin();
}

function showMonitorView() {
  if (!isAdmin()) return;
  appState.lastSection = "monitor";
  setActiveNav("monitor");
  setPageHeader("Monitor", "Histórico de ejecuciones");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = false;
  configSection.hidden = true;
  loadMonitorRuns();
}

function showConfigView() {
  if (!isAdmin()) return;
  appState.lastSection = "config";
  setActiveNav("config");
  setPageHeader("Configuración", "Administración");
  daysSection.hidden = true;
  licitacionesSection.hidden = true;
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = false;
  loadConfig();
}

function backFromNotifications() {
  if (appState.lastSection === "actuaciones") {
    showActuacionesView();
    return;
  }
  if (appState.lastSection === "calendar") {
    showCalendarView();
    return;
  }
  if (appState.lastSection === "monitor") {
    showMonitorView();
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

function actuacionLabel(map, value) {
  return map[value] || value || "";
}

function actuacionesQueryParams() {
  const params = new URLSearchParams();
  const filter = actuacionesFilter.value || "abiertas";
  if (filter === "abiertas") params.set("abiertas", "1");
  if (filter === "vencidas") params.set("vencidas", "1");
  if (filter === "hoy") params.set("hoy", "1");
  if (filter === "semana") params.set("semana", "1");
  if (filter === "sin_licitacion") params.set("sin_licitacion", "1");
  if (filter === "cerradas") params.set("estado", "cerrada");
  return params;
}

async function loadActuaciones() {
  const params = actuacionesQueryParams();
  const response = await fetch(`/api/actuaciones?${params.toString()}`);
  if (!response.ok) {
    actuacionesBoard.innerHTML = `<div class="empty">No se pudieron cargar las actuaciones.</div>`;
    return;
  }
  const data = await response.json();
  appState.actuaciones = data.items || [];
  appState.actuacionesSummary = data.summary || {};
  renderActuacionesSummary();
  renderActuacionesBoard();
}

function renderActuacionesSummary() {
  const summaryData = appState.actuacionesSummary || {};
  actuacionesSummary.innerHTML = [
    ["Abiertas", summaryData.total_abiertas || 0],
    ["Vencidas", summaryData.vencidas || 0],
    ["Hoy", summaryData.vencen_hoy || 0],
    ["Esta semana", summaryData.vencen_semana || 0],
    ["Sin licitación", summaryData.sin_licitacion || 0],
  ].map(renderMetric).join("");
}

function renderActuacionesBoard() {
  if (!appState.actuaciones.length) {
    actuacionesBoard.innerHTML = `<div class="empty">No hay actuaciones para esta vista.</div>`;
    return;
  }
  actuacionesBoard.innerHTML = appState.actuaciones.map(renderActuacionCard).join("");
}

function licitacionBrief(item) {
  return item.expediente || item.organismo || item.objeto || `Licitación ${item.id}`;
}

function linkedLicitacionesText(licitaciones = []) {
  if (!licitaciones.length) return "Sin licitación";
  const labels = licitaciones.slice(0, 3).map(licitacionBrief);
  if (licitaciones.length > 3) labels.push(`+${licitaciones.length - 3} más`);
  return labels.join(", ");
}

function linkedLicitacionesCountText(licitaciones = []) {
  if (!licitaciones.length) return "Sin licitaciones vinculadas";
  if (licitaciones.length === 1) return "1 licitación vinculada";
  return `${licitaciones.length} licitaciones vinculadas`;
}

function renderActuacionCard(item) {
  const deadline = item.deadline_at ? item.deadline_at.replace("T", " ") : "Sin fecha";
  const linked = item.licitaciones || [];
  const canClose = ["pendiente", "en_curso", "preparado", "preparada"].includes(item.estado);
  return `
    <article class="card compact-card actuacion-card">
      <div class="card-content">
        <div class="card-head">
          <div class="card-title-block">
            <p class="eyebrow">${escapeHtml(linkedLicitacionesCountText(linked))}</p>
            <h2>${escapeHtml(item.titulo)}</h2>
            <p class="card-organismo">${escapeHtml(linkedLicitacionesText(linked))}</p>
          </div>
          <div class="card-flags">
            <span class="due-chip ${escapeHtml(item.estado_visual)}">${escapeHtml(actuacionLabel(actuacionVisualLabels, item.estado_visual))}</span>
            <span class="province-chip">${escapeHtml(actuacionLabel(actuacionTipoLabels, item.tipo))}</span>
          </div>
        </div>
        <div class="details">
          <div class="detail"><span>Límite</span>${escapeHtml(deadline)}</div>
          <div class="detail"><span>Estado</span>${escapeHtml(actuacionLabel(actuacionEstadoLabels, item.estado))}</div>
          <div class="detail"><span>Vínculos</span>${escapeHtml(String(item.licitaciones_count || linked.length || 0))}</div>
        </div>
        ${item.descripcion ? `<p class="muted">${escapeHtml(item.descripcion)}</p>` : ""}
        <div class="card-actions">
          <button data-edit-actuacion="${escapeHtml(item.id)}">Editar</button>
          <button data-comment-actuacion="${escapeHtml(item.id)}">Añadir comentario</button>
          <button data-duplicate-actuacion="${escapeHtml(item.id)}">Duplicar actuación</button>
          ${canClose ? `<button data-close-actuacion="${escapeHtml(item.id)}">Cerrar</button>` : ""}
          ${canClose ? `<button class="danger" data-cancel-actuacion="${escapeHtml(item.id)}">Cancelar</button>` : ""}
        </div>
      </div>
    </article>
  `;
}

function setSelectedActuacionLicitaciones(items = []) {
  const unique = new Map();
  for (const item of items) {
    if (item?.id) unique.set(String(item.id), item);
  }
  appState.actuacionSelectedLicitaciones = [...unique.values()];
  renderSelectedActuacionLicitaciones();
}

function renderSelectedActuacionLicitaciones() {
  const selected = appState.actuacionSelectedLicitaciones || [];
  actuacionLicitacionesSummary.textContent = linkedLicitacionesCountText(selected);
  if (!selected.length) {
    actuacionSelectedLicitaciones.innerHTML = `<div class="empty">Sin licitaciones vinculadas.</div>`;
    return;
  }
  actuacionSelectedLicitaciones.innerHTML = selected.map((item) => `
    <article class="linked-item">
      <strong>${escapeHtml(licitacionBrief(item))}</strong>
      <small>${escapeHtml(item.organismo || "")}${item.fecha_limite ? ` · ${escapeHtml(item.fecha_limite)}` : ""}</small>
      <button type="button" class="ghost" data-remove-selected-licitacion="${escapeHtml(item.id)}">Quitar</button>
    </article>
  `).join("");
}

async function loadLicitacionSelectorResults() {
  const params = new URLSearchParams();
  params.set("limit", "100");
  const search = licitacionSelectorSearch.value.trim();
  if (search) params.set("q", search);
  const response = await fetch(`/api/licitaciones/search?${params.toString()}`);
  if (!response.ok) {
    licitacionSelectorResults.innerHTML = `<div class="empty">No se pudieron cargar licitaciones.</div>`;
    return;
  }
  const data = await response.json();
  appState.actuacionSelectorResults = data.items || [];
  renderLicitacionSelectorResults();
}

function renderLicitacionSelectorResults() {
  const results = appState.actuacionSelectorResults || [];
  if (!results.length) {
    licitacionSelectorResults.innerHTML = `<div class="empty">No hay licitaciones para esa búsqueda.</div>`;
    return;
  }
  licitacionSelectorResults.innerHTML = results.map((item) => {
    const checked = appState.actuacionSelectorDraft.has(String(item.id)) ? "checked" : "";
    return `
      <label class="selector-item">
        <input type="checkbox" value="${escapeHtml(item.id)}" ${checked}>
        <span>
          <strong>${escapeHtml(licitacionBrief(item))}</strong>
          <small>${escapeHtml(item.organismo || "Sin organismo")} · ${escapeHtml(item.objeto || "Sin objeto")}</small>
          <small>${escapeHtml(item.fecha_limite || "Sin fecha")} · ${escapeHtml(item.estado || "")} · ${escapeHtml(item.plataforma || "")}</small>
        </span>
      </label>
    `;
  }).join("");
}

async function openLicitacionSelector() {
  appState.actuacionSelectorDraft = new Map(
    (appState.actuacionSelectedLicitaciones || []).map((item) => [String(item.id), item])
  );
  licitacionSelectorSearch.value = "";
  await loadLicitacionSelectorResults();
  licitacionSelectorDialog.showModal();
}

function commitLicitacionSelection() {
  setSelectedActuacionLicitaciones([...appState.actuacionSelectorDraft.values()]);
  licitacionSelectorDialog.close();
}

function findLicitacionSelection(id) {
  const stringId = String(id);
  const direct = appState.items.find((item) => String(item.id) === stringId);
  if (direct) return direct;
  for (const event of appState.calendarItems || []) {
    const linked = (event.linked_licitaciones || []).find((item) => String(item.id) === stringId);
    if (linked) return linked;
  }
  return null;
}

function renderActuacionHistory(entries = []) {
  if (!actuacionForm.elements.id.value) {
    actuacionHistoryPanel.hidden = true;
    actuacionHistory.innerHTML = "";
    return;
  }
  actuacionHistoryPanel.hidden = false;
  if (!entries.length) {
    actuacionHistory.innerHTML = `<div class="empty">Sin movimientos registrados.</div>`;
    return;
  }
  actuacionHistory.innerHTML = entries.map((entry) => `
    <article class="history-item">
      <strong>${escapeHtml(entry.event_type || "evento")}</strong>
      <small>${escapeHtml(entry.created_at || "")}${entry.user_id ? ` · ${escapeHtml(entry.user_id)}` : ""}</small>
      ${entry.comentario ? `<p>${escapeHtml(entry.comentario)}</p>` : ""}
      ${entry.old_value || entry.new_value ? `<small>${escapeHtml(entry.old_value || "vacío")} -> ${escapeHtml(entry.new_value || "vacío")}</small>` : ""}
    </article>
  `).join("");
}

async function openActuacionDialog(licitacionId = "") {
  actuacionForm.reset();
  actuacionForm.elements.id.value = "";
  actuacionFormTitle.textContent = "Nueva actuación";
  actuacionForm.elements.recordatorio_email.checked = true;
  showDateWarning(actuacionDateWarning, "");
  const linkedItem = licitacionId ? findLicitacionSelection(licitacionId) : null;
  const linked = linkedItem ? [linkedItem] : [];
  setSelectedActuacionLicitaciones(linked);
  renderActuacionHistory([]);
  actuacionDialog.showModal();
}

async function editActuacion(id) {
  const response = await fetch(`/api/actuaciones/${id}`);
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.item) {
    alert(result.error || "No se pudo cargar la actuación.");
    return;
  }
  const item = result.item;
  actuacionForm.reset();
  actuacionFormTitle.textContent = `Editar ${item.titulo || "actuación"}`;
  actuacionForm.elements.id.value = item.id;
  actuacionForm.elements.tipo.value = item.tipo || "otro";
  actuacionForm.elements.titulo.value = item.titulo || "";
  actuacionForm.elements.descripcion.value = item.descripcion || "";
  actuacionForm.elements.deadline_at.value = toDatetimeLocal(item.deadline_at || "");
  showDateWarning(actuacionDateWarning, actuacionForm.elements.deadline_at.value);
  actuacionForm.elements.estado.value = normalizedTaskStateValue(item.estado || "pendiente");
  actuacionForm.elements.recordatorio_email.checked = Boolean(item.recordatorio_email);
  setSelectedActuacionLicitaciones(item.licitaciones || []);
  renderActuacionHistory(item.historial || []);
  actuacionDialog.showModal();
}

async function saveActuacion(event) {
  event.preventDefault();
  const id = actuacionForm.elements.id.value;
  showDateWarning(actuacionDateWarning, actuacionForm.elements.deadline_at.value);
  const payload = {
    tipo: actuacionForm.elements.tipo.value,
    titulo: actuacionForm.elements.titulo.value,
    descripcion: actuacionForm.elements.descripcion.value,
    deadline_at: actuacionForm.elements.deadline_at.value,
    estado: actuacionForm.elements.estado.value,
    recordatorio_email: actuacionForm.elements.recordatorio_email.checked,
    licitacion_ids: (appState.actuacionSelectedLicitaciones || []).map((item) => Number(item.id)),
    origen: "manual",
  };
  const response = await fetch(id ? `/api/actuaciones/${id}` : "/api/actuaciones", {
    method: id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo guardar la actuación.");
    return;
  }
  actuacionDialog.close();
  await loadActuaciones();
  await loadItems();
}

async function addActuacionComment() {
  const id = actuacionForm.elements.id.value;
  const comentario = actuacionComment.value.trim();
  if (!id || !comentario) return;
  const response = await fetch(`/api/actuaciones/${id}/historial`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ comentario }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo añadir el comentario.");
    return;
  }
  actuacionComment.value = "";
  renderActuacionHistory(result.item?.historial || []);
  await loadActuaciones();
}

async function quickActuacionComment(id) {
  const comentario = window.prompt("Comentario para la actuación:");
  if (!comentario || !comentario.trim()) return;
  const response = await fetch(`/api/actuaciones/${id}/historial`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ comentario: comentario.trim() }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo añadir el comentario.");
    return;
  }
  await loadActuaciones();
  await loadCalendarItems();
}

async function duplicateActuacion(id) {
  const response = await fetch(`/api/actuaciones/${id}/duplicar`, { method: "POST", headers: csrfHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo duplicar la actuación.");
    return;
  }
  await loadActuaciones();
  await loadCalendarItems();
}

async function setActuacionClosedState(id, action) {
  const response = await fetch(`/api/actuaciones/${id}/${action}`, { method: "POST", headers: csrfHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo actualizar la actuación.");
    return;
  }
  await loadActuaciones();
  await loadItems();
}

function openAgendaEventoDialog(item = null) {
  agendaEventForm.reset();
  agendaEventForm.elements.id.value = item?.source_id || item?.id || "";
  agendaEventFormTitle.textContent = item ? `Editar ${item.title || item.titulo || "evento"}` : "Nuevo evento interno";
  agendaEventForm.elements.titulo.value = item?.title || item?.titulo || "";
  agendaEventForm.elements.descripcion.value = item?.subtitle || item?.descripcion || "";
  agendaEventForm.elements.starts_at.value = toDatetimeLocal(item?.datetime || item?.starts_at || "");
  showDateWarning(agendaEventDateWarning, agendaEventForm.elements.starts_at.value, { required: true });
  agendaEventForm.elements.estado.value = normalizedTaskStateValue(item?.status || item?.estado || "pendiente");
  agendaEventDialog.showModal();
}

async function saveAgendaEvento(event) {
  event.preventDefault();
  const id = agendaEventForm.elements.id.value;
  showDateWarning(agendaEventDateWarning, agendaEventForm.elements.starts_at.value, { required: true });
  const payload = {
    titulo: agendaEventForm.elements.titulo.value,
    descripcion: agendaEventForm.elements.descripcion.value,
    starts_at: agendaEventForm.elements.starts_at.value,
    estado: agendaEventForm.elements.estado.value,
  };
  const response = await fetch(id ? `/api/agenda/eventos/${id}` : "/api/agenda/eventos", {
    method: id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo guardar el evento interno.");
    return;
  }
  agendaEventDialog.close();
  await loadCalendarItems();
}

async function setAgendaEventoEstado(id, action) {
  const response = await fetch(`/api/agenda/eventos/${id}/${action}`, { method: "POST", headers: csrfHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo actualizar el evento interno.");
    return;
  }
  await loadCalendarItems();
}

async function updatePendingTaskState(token, stateValue) {
  const [sourceType, sourceId] = String(token || "").split(":");
  if (!sourceType || !sourceId) return;
  const endpoint = {
    licitacion: `/api/licitaciones/${sourceId}`,
    actuacion: `/api/actuaciones/${sourceId}`,
    interno: `/api/agenda/eventos/${sourceId}`,
  }[sourceType];
  if (!endpoint) return;
  const response = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ estado: stateValue }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo actualizar el estado.");
    return;
  }
  await loadCalendarItems();
}

async function sendAgendaEmailSummary() {
  const payload = {
    view: appState.agendaView || "day",
    date: appState.calendarSelectedDate || dateKey(new Date()),
    type_filter: appState.agendaType || "all",
    search: calendarSearch.value.trim(),
    include_no_date: appState.agendaType === "sin_fecha" || appState.agendaView === "all",
  };
  const response = await fetch("/api/agenda/email-summary", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo enviar el resumen.");
    return;
  }
  const status = result.dry_run
    ? "Dry-run: no se ha enviado email real."
    : "Resumen enviado por email.";
  alert(`${status}\n\n${result.subject || ""}\n\n${result.preview || ""}`.trim());
}

function openAgendaOrigin(token) {
  const [sourceType, sourceId] = String(token || "").split(":");
  if (!sourceType || !sourceId) return;
  if (sourceType === "licitacion") {
    openLicitacionDetail(sourceId);
    return;
  }
  if (sourceType === "actuacion") {
    editActuacion(sourceId);
    return;
  }
  if (sourceType === "interno") {
    const item = appState.calendarItems.find((entry) => entry.source_type === "interno" && String(entry.source_id) === String(sourceId));
    openAgendaEventoDialog(item);
  }
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
          <button class="primary" data-open-dia="${escapeHtml(dia.id)}" data-title="${escapeHtml(dia.titulo)}">Abrir revisión</button>
          ${isAdmin() ? `<button class="danger" data-delete-dia="${escapeHtml(dia.id)}" data-title="${escapeHtml(dia.titulo)}">Borrar día</button>` : ""}
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

  if (isNuriaDayReview()) {
    const option = nuriaDayFilterOptions.find((item) => item.value === estado) || nuriaDayFilterOptions[0];
    estado = option.value;
    stateFilter.value = estado;
    params.set("nuria_filter", option.filter);
  } else if (estado && estado !== "Todos" && !visibleOrder.includes(estado)) {
    estado = "Todos";
    stateFilter.value = "Todos";
  }

  if (!isNuriaDayReview() && estado && estado !== "Todos") params.set("estado", estado);
  if (appState.currentDiaId) params.set("dia_id", appState.currentDiaId);
  if (!appState.currentDiaId && appState.licitacionesView === "live") params.set("vivas", "1");
  params.set("orden_fecha", ordenFecha);
  if (q) params.set("q", q);
  if (licitacionesActuacionesFilter.value) params.set("actuaciones", licitacionesActuacionesFilter.value);
  const quickFilter = licitacionesQuickFilter.value;
  if (quickFilter === "revision_pendiente") params.set("revision", "pendiente");
  if (quickFilter === "revision_revisada") params.set("revision", "revisada");
  if (quickFilter === "seguimiento") params.set("seguimiento", "1");
  if (quickFilter === "sin_documentacion") params.set("documentacion", "sin_descargar");
  if (quickFilter === "descarga_fallida") params.set("documentacion", "fallida");
  if (quickFilter === "estado_descartada") params.set("estado_interno", "Descartada");
  if (quickFilter === "estado_presentada") params.set("estado_interno", "Presentada");

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
  if (appState.currentDiaId && isAdmin()) return ["Importada", ...adminReviewEstados];
  if (isAdmin()) return estadoOrden;
  return appState.currentDiaId ? nuriaDefaultReviewEstados : nuriaLicitacionesEstados;
}

function renderStateFilter() {
  if (isNuriaDayReview()) {
    const current = stateFilter.value || "__nuria_active";
    const safeCurrent = nuriaDayFilterOptions.some((option) => option.value === current) ? current : "__nuria_active";
    stateFilter.innerHTML = nuriaDayFilterOptions
      .map((option) => (
        `<option value="${escapeHtml(option.value)}" ${option.value === safeCurrent ? "selected" : ""}>${escapeHtml(option.label)}</option>`
      ))
      .join("");
    stateFilter.value = safeCurrent;
    return;
  }
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
  summary.innerHTML = "";
  summary.hidden = true;
}

function renderReviewButton() {
  const hasDay = Boolean(appState.currentDiaId);
  const hasPendingReview = Number(appState.currentDayPendingReview ?? appState.totals["Enviada a Nuria"] ?? 0) > 0;
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
  if (appState.agendaView === "pending") {
    const params = new URLSearchParams();
    const search = calendarSearch.value.trim();
    if (search) params.set("q", search);
    const response = await fetch(`/api/agenda/pending-tasks?${params.toString()}`);
    if (!response.ok) {
      if (response.status === 401) location.href = "/login";
      if (response.status === 403) showDaysView();
      return;
    }
    const data = await response.json();
    appState.calendarItems = data.items || [];
    appState.agendaGroups = data.groups || {};
    appState.agendaSummary = {};
    appState.agendaWorkbench = null;
    renderCalendarStateFilter();
    renderCalendar();
    return;
  }

  const params = new URLSearchParams();
  params.set("view", appState.agendaView || "day");
  params.set("date", appState.calendarSelectedDate || dateKey(new Date()));
  params.set("type", appState.agendaType || "all");
  const search = calendarSearch.value.trim();
  if (search) params.set("q", search);
  if (appState.agendaView === "month" || appState.agendaView === "all") params.set("include_overdue", "1");
  const response = await fetch(`/api/agenda?${params.toString()}`);
  if (!response.ok) {
    if (response.status === 401) location.href = "/login";
    calendarBoard.innerHTML = `<div class="empty">No se pudo cargar la agenda.</div>`;
    calendarRadar.innerHTML = "";
    calendarDayPanel.innerHTML = "";
    return;
  }

  const data = await response.json();
  appState.calendarItems = data.events || [];
  appState.agendaGroups = data.groups || {};
  appState.agendaSummary = data.summary || {};
  appState.agendaActiveDateLabel = data.active_date_label || "";
  appState.agendaIsToday = Boolean(data.is_today);
  appState.agendaWorkbench = null;
  renderCalendarStateFilter();
  renderCalendar();
}

function calendarFilteredItems() {
  const q = calendarSearch.value.trim().toLowerCase();
  return appState.calendarItems.filter((item) => {
    if (!q) return true;
    return [
      item.title,
      item.subtitle,
      item.status,
      item.source_type,
      ...(item.linked_licitaciones || []).flatMap((licitacion) => [
        licitacion.expediente,
        licitacion.organismo,
        licitacion.objeto,
        licitacion.plataforma,
        licitacion.provincia,
      ]),
    ].some((value) => String(value || "").toLowerCase().includes(q));
  });
}

function renderCalendarStateFilter() {
  calendarStateFilter.value = appState.agendaType || "all";
  calendarStateFilter.disabled = appState.agendaView === "pending";
  calendarSection.classList.remove("agenda-view-pending", "agenda-view-day", "agenda-view-week", "agenda-view-month", "agenda-view-all");
  calendarSection.classList.add(`agenda-view-${appState.agendaView || "day"}`);
  document.querySelectorAll("[data-agenda-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.agendaView === appState.agendaView);
    if (button.dataset.agendaView === "day") {
      button.textContent = "Hoy";
    }
  });
}

function itemsByDate(items) {
  return items.reduce((groups, item) => {
    const key = item.date || "sin-fecha";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
    return groups;
  }, new Map());
}

function addDays(date, amount) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function weekStartMonday(date) {
  const start = new Date(date);
  const mondayIndex = (start.getDay() + 6) % 7;
  start.setDate(start.getDate() - mondayIndex);
  return start;
}

function agendaEventDate(item) {
  return item.datetime ? new Date(item.datetime) : parseDate(item.date);
}

function agendaEventTime(item) {
  if (!item.datetime) return "";
  const parsed = new Date(item.datetime);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

function agendaTypeLabel(item) {
  return agendaTypeLabels[agendaColorType(item)] || agendaTypeLabels[item.source_type] || item.source_type || "";
}

function agendaStatusLabel(item) {
  return agendaStatusLabels[item.status] || estadoLabel(item.status) || item.status || "";
}

function agendaColorType(item) {
  const rawColor = item && item.is_overdue ? "vencido" : String(item?.color_type || item?.source_type || "").toLowerCase();
  return agendaColorTypes.has(rawColor) ? rawColor : "interno";
}

function agendaEventClass(item) {
  return `agenda-event--${agendaColorType(item)}`;
}

function agendaLinkedText(item) {
  const linked = item.linked_licitaciones || [];
  if (!linked.length) return "";
  const labels = linked.slice(0, 3).map((licitacion) => (
    licitacion.expediente || licitacion.organismo || `Licitación ${licitacion.id}`
  ));
  if (linked.length > 3) labels.push(`+${linked.length - 3} más`);
  return labels.join(", ");
}

function agendaOpenLabel(item) {
  if (item.source_type === "actuacion") return "Abrir actuación";
  if (item.source_type === "licitacion") return "Abrir licitación";
  return "Abrir evento";
}

function isPendingAgendaView() {
  return appState.agendaView === "pending";
}

function pendingStateOptions(item) {
  if (item.state_options && item.state_options.length) return item.state_options;
  if (item.source_type === "licitacion") return estadoOrden.map((estado) => ({ value: estado, label: estadoLabel(estado) }));
  return taskStateOptions;
}

function renderPendingStateControl(item) {
  if (!isPendingAgendaView()) return "";
  const token = `${item.source_type}:${item.source_id}`;
  const value = item.source_type === "licitacion"
    ? (item.state_value || item.status || item.state || "")
    : normalizedTaskStateValue(item.state_value || item.raw_state || item.status || item.state);
  return `
    <label class="agenda-state-control">
      <span>Estado</span>
      <select data-pending-state="${escapeHtml(token)}">
        ${pendingStateOptions(item).map((option) => `
          <option value="${escapeHtml(option.value)}" ${String(option.value) === String(value) ? "selected" : ""}>${escapeHtml(option.label)}</option>
        `).join("")}
      </select>
    </label>
  `;
}

function renderAgendaActions(item) {
  const token = `${item.source_type}:${item.source_id}`;
  const actions = [`<button type="button" data-agenda-open="${escapeHtml(token)}">${escapeHtml(agendaOpenLabel(item))}</button>`];
  if (item.source_type === "licitacion") {
    actions.push(`<button type="button" data-new-actuacion-id="${escapeHtml(item.source_id)}">Nueva actuación</button>`);
  }
  if (item.source_type === "actuacion") {
    actions.push(`<button type="button" data-agenda-comment="${escapeHtml(item.source_id)}">Añadir comentario</button>`);
    actions.push(`<button type="button" data-agenda-duplicate="${escapeHtml(item.source_id)}">Duplicar actuación</button>`);
  }
  if (item.source_type === "interno" && !isPendingAgendaView()) {
    actions.push(`<button type="button" data-agenda-close="${escapeHtml(item.source_id)}">Cerrar</button>`);
    actions.push(`<button type="button" class="danger" data-agenda-cancel="${escapeHtml(item.source_id)}">Cancelar</button>`);
  }
  return `${renderPendingStateControl(item)}<div class="links">${actions.join("")}</div>`;
}

function renderCalendar() {
  const filtered = calendarFilteredItems();
  const monthDate = appState.calendarDate;
  const today = new Date();
  const todayKey = dateKey(today);
  const selectedKey = appState.calendarSelectedDate || todayKey;
  if (agendaWorkbench) agendaWorkbench.innerHTML = "";
  calendarSummary.innerHTML = "";

  if (appState.agendaView === "day") {
    calendarMonthTitle.textContent = `Fecha activa · ${appState.agendaActiveDateLabel || formatDate(selectedKey)}`;
  } else if (appState.agendaView === "week") {
    const start = weekStartMonday(parseDate(selectedKey) || today);
    const end = addDays(start, 6);
    calendarMonthTitle.textContent = `Semana · ${formatDate(dateKey(start))} - ${formatDate(dateKey(end))}`;
  } else if (appState.agendaView === "all") {
    calendarMonthTitle.textContent = "Todo lo agendado";
  } else if (appState.agendaView === "pending") {
    calendarMonthTitle.textContent = "Tareas pendientes";
  } else {
    calendarMonthTitle.textContent = `Calendario · ${monthTitle(monthDate)}`;
  }

  if (appState.agendaView === "pending") {
    renderAgendaPending(filtered);
    return;
  }
  if (appState.agendaView === "day") {
    renderAgendaDay(filtered, selectedKey);
    return;
  }
  if (appState.agendaView === "week") {
    renderAgendaWeek(filtered, selectedKey);
    return;
  }
  if (appState.agendaView === "all") {
    renderAgendaAll(filtered, selectedKey);
    return;
  }
  renderAgendaMonth(filtered, selectedKey);
}

function renderAgendaWorkbench() {
  const workbench = appState.agendaWorkbench;
  if (!workbench || !agendaWorkbench) {
    if (agendaWorkbench) agendaWorkbench.innerHTML = "";
    return;
  }
  const sections = workbench.sections || [];
  const counts = workbench.summary || {};
  const grouped = workbench.actuaciones_by_licitacion || [];
  const selected = sections.find((section) => section.key === appState.agendaWorkbenchSelectedKey);
  agendaWorkbench.innerHTML = `
    <div class="workbench-head">
      <div>
        <p class="eyebrow">Bandeja operativa</p>
        <h3>Prioridades</h3>
      </div>
      <span>${escapeHtml(counts.open_actuaciones_count || 0)} actuaciones abiertas</span>
    </div>
    <div class="workbench-grid">
      ${sections.map((section) => `
        <button type="button" class="workbench-card ${selected?.key === section.key ? "active-state" : ""}" data-workbench-key="${escapeHtml(section.key)}">
          <span>${escapeHtml(section.title)}</span>
          <strong>${escapeHtml(section.count || 0)}</strong>
        </button>
      `).join("")}
    </div>
    ${selected ? `
      <section class="agenda-group workbench-group">
        <h3>${escapeHtml(selected.title)}</h3>
        ${(selected.items || []).length ? (selected.items || []).slice(0, 10).map(renderWorkbenchItem).join("") : `<div class="empty">Sin elementos.</div>`}
      </section>
    ` : ""}
    ${grouped.length ? `
      <section class="agenda-group workbench-group">
        <h3>Actuaciones por licitación</h3>
        ${grouped.slice(0, 6).map((item) => `
          <article class="radar-card agenda-card ${Number(item.overdue_count || 0) ? "agenda-event--vencido" : "agenda-event--actuacion"}">
            <span>${escapeHtml(item.open_count || 0)} abiertas · ${escapeHtml(item.overdue_count || 0)} vencidas</span>
            <strong>${escapeHtml(item.expediente || item.organismo || `Licitación ${item.licitacion_id}`)}</strong>
            <small>${escapeHtml(item.next_deadline_at || "Sin próxima fecha")}</small>
            <div class="links">
              <button type="button" data-workbench-licitacion="${escapeHtml(item.licitacion_id)}">Abrir licitación</button>
              <button type="button" data-workbench-actuaciones="${escapeHtml(item.licitacion_id)}">Ver actuaciones</button>
            </div>
          </article>
        `).join("")}
      </section>
    ` : ""}
  `;
}

function renderWorkbenchItem(item) {
  const sourceType = item.source_type || (item.expediente ? "licitacion" : "");
  const title = item.title || item.expediente || item.objeto || item.organismo || "Sin título";
  const subtitle = item.subtitle || item.objeto || item.organismo || item.error_message || "";
  const when = item.datetime || item.date || item.fecha_limite || item.download_updated_at || "Sin fecha";
  const id = item.source_id || item.id || "";
  const colorClass = sourceType === "actuacion"
    ? "agenda-event--actuacion"
    : sourceType === "licitacion"
      ? "agenda-event--licitacion"
      : "agenda-event--interno";
  return `
    <article class="radar-card agenda-card ${item.is_overdue ? "agenda-event--vencido" : colorClass}">
      <span>${escapeHtml(sourceType || "Prioridad")}</span>
      <strong>${escapeHtml(title)}</strong>
      <small>${escapeHtml(when)}</small>
      <small>${escapeHtml(subtitle)}</small>
      ${sourceType === "licitacion" && id ? `<div class="links"><button type="button" data-workbench-licitacion="${escapeHtml(id)}">Abrir licitación</button></div>` : ""}
      ${sourceType === "actuacion" && id ? `<div class="links"><button type="button" data-workbench-actuacion="${escapeHtml(id)}">Abrir actuación</button></div>` : ""}
    </article>
  `;
}

function activateWorkbenchSection(key) {
  appState.agendaWorkbenchSelectedKey = key;
  const today = dateKey(new Date());
  if (key === "overdue") {
    appState.agendaView = "all";
    appState.agendaType = "vencido";
    loadCalendarItems();
    return;
  }
  if (key === "due_today") {
    appState.agendaView = "day";
    appState.agendaType = "all";
    appState.calendarSelectedDate = today;
    loadCalendarItems();
    return;
  }
  if (key === "next_7_days") {
    appState.agendaView = "week";
    appState.agendaType = "all";
    appState.calendarSelectedDate = today;
    loadCalendarItems();
    return;
  }
  if (key === "without_date") {
    appState.agendaView = "all";
    appState.agendaType = "sin_fecha";
    loadCalendarItems();
    return;
  }
  if (key === "new_licitaciones") {
    stateFilter.value = "Importada";
    licitacionesActuacionesFilter.value = "";
    showLicitacionesView({ view: "all" });
    return;
  }
  if (key === "failed_downloads") {
    renderAgendaWorkbench();
  }
}

function renderAgendaMonth(items, selectedKey) {
  const groups = itemsByDate(items);
  const monthDate = appState.calendarDate;
  const todayKey = dateKey(new Date());
  calendarRadar.innerHTML = "";
  const start = monthStartMonday(monthDate);
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const current = new Date(start);
    current.setDate(start.getDate() + index);
    const key = dateKey(current);
    const dayItems = (groups.get(key) || []).sort(compareCalendarItems);
    const expired = dayItems.some((item) => item.is_overdue);
    const classes = [
      "calendar-day",
      isSameMonth(current, monthDate) ? "" : "not-current",
      key === todayKey ? "today" : "",
      key === selectedKey ? "selected" : "",
      dayItems.length ? "has-items" : "",
      expired ? "expired-day" : "",
    ].filter(Boolean).join(" ");

    cells.push(`
      <article class="${classes}" data-calendar-date="${escapeHtml(key)}">
        <div class="calendar-day-head">
          <strong>${current.getDate()}</strong>
          ${dayItems.length ? `<span>${dayItems.length}</span>` : ""}
        </div>
        <div class="calendar-events">
          ${dayItems.slice(0, 3).map(renderCalendarEvent).join("")}
          ${dayItems.length > 3 ? `<span class="calendar-more">+${dayItems.length - 3} más</span>` : ""}
        </div>
      </article>
    `);
  }
  calendarBoard.innerHTML = cells.join("");
  renderCalendarDayPanel(groups.get(selectedKey) || [], selectedKey);
}

function compareCalendarItems(a, b) {
  const timeA = agendaEventTime(a) || "99:99";
  const timeB = agendaEventTime(b) || "99:99";
  if (timeA !== timeB) return timeA.localeCompare(timeB);
  return String(a.title || "").localeCompare(String(b.title || ""));
}

function renderCalendarEvent(item) {
  const time = agendaEventTime(item) ? `${agendaEventTime(item)} · ` : "";
  const colorClass = agendaEventClass(item);
  return `
    <span class="calendar-event ${colorClass}">
      <b class="agenda-event-dot ${colorClass}"></b>
      <span>${escapeHtml(time)}${escapeHtml(item.title || "Sin título")}</span>
    </span>
  `;
}

function renderCalendarRadar(items) {
  const upcoming = items
    .filter((item) => item.is_overdue)
    .sort(compareCalendarItems)
    .slice(0, 8);

  if (!upcoming.length) {
    calendarRadar.innerHTML = `<div class="empty">No hay vencidos abiertos con los filtros actuales.</div>`;
    return;
  }

  calendarRadar.innerHTML = upcoming.map(renderAgendaCompactCard).join("");
}

function renderAgendaDay(items, selectedKey) {
  const dayTitle = agendaDayHeading(selectedKey);
  calendarRadar.innerHTML = renderAgendaListPanel(
    "Agenda del día",
    "Eventos del día",
    renderAgendaGroup(dayTitle, items)
  );
  calendarBoard.innerHTML = "";
  calendarDayPanel.innerHTML = "";
}

function renderAgendaPending(items) {
  const groups = appState.agendaGroups || {};
  const blocks = [
    renderAgendaGroup("Vencidos", groups.overdue || items.filter((item) => item.is_overdue)),
    renderAgendaGroup("Sin fecha", groups.no_date || items.filter((item) => item.is_without_date)),
    renderAgendaGroup("Hoy", groups.today || items.filter((item) => item.is_today && !item.is_overdue)),
    renderAgendaGroup("Próximos", groups.upcoming || items.filter((item) => (
      !item.is_overdue && !item.is_without_date && !item.is_today
    ))),
  ];
  calendarRadar.innerHTML = renderAgendaListPanel("Tareas pendientes", "Lista de trabajo", blocks.join(""));
  calendarBoard.innerHTML = "";
  calendarDayPanel.innerHTML = "";
}

function renderAgendaAll(items, selectedKey) {
  const groups = appState.agendaGroups || {};
  const noDate = groups.no_date || items.filter((item) => !item.date);
  const overdue = groups.overdue || items.filter((item) => item.is_overdue);
  const upcoming = [
    ...(groups.day || []),
    ...(groups.today || []),
    ...(groups.upcoming || []),
  ].filter((item, index, allItems) => (
    item.date && !item.is_overdue && allItems.findIndex((candidate) => candidate.id === item.id) === index
  ));
  const blocks = [
    renderAgendaGroup("Sin fecha", noDate),
    renderAgendaGroup("Vencidos", overdue),
    renderAgendaGroup("Próximos", upcoming),
  ];
  calendarRadar.innerHTML = renderAgendaListPanel("Agenda completa", "Todos los eventos", blocks.join(""));
  calendarBoard.innerHTML = "";
  calendarDayPanel.innerHTML = "";
}

function renderAgendaWeek(items, selectedKey) {
  const selected = parseDate(selectedKey) || new Date();
  const start = weekStartMonday(selected);
  const groups = itemsByDate(items);
  calendarBoard.innerHTML = "";
  calendarDayPanel.innerHTML = "";
  renderAgendaWeekList(items, start, groups);
}

function renderAgendaWeekList(items, start, groups) {
  const sections = [];
  for (let index = 0; index < 7; index += 1) {
    const day = addDays(start, index);
    const key = dateKey(day);
    const title = agendaDayHeading(key);
    const dayItems = (groups.get(key) || []).sort(compareCalendarItems);
    sections.push(renderAgendaGroup(title, dayItems));
  }
  calendarRadar.innerHTML = renderAgendaListPanel("Agenda semanal", "Eventos de la semana", sections.join(""));
}

function renderAgendaGroup(title, items) {
  return `
    <section class="agenda-group">
      <h3>${escapeHtml(title)}</h3>
      ${items.length ? items.map(renderAgendaCompactCard).join("") : `<div class="empty">Sin elementos.</div>`}
    </section>
  `;
}

function renderAgendaListPanel(eyebrow, title, content) {
  return `
    <div class="panel-sticky agenda-week-list">
      <p class="eyebrow">${escapeHtml(eyebrow)}</p>
      <h3>${escapeHtml(title)}</h3>
      <div class="agenda-week-list-content">${content}</div>
    </div>
  `;
}

function agendaDayHeading(key) {
  if (key === "sin-fecha") return "Sin fecha";
  const parsed = parseDate(key);
  const text = parsed
    ? parsed.toLocaleDateString("es-ES", { weekday: "long", day: "2-digit", month: "short" })
    : formatDate(key);
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Sin fecha";
}

function renderAgendaCompactCard(item) {
  const colorClass = agendaEventClass(item);
  const linked = agendaLinkedText(item);
  return `
    <article class="radar-card agenda-card ${colorClass}" data-calendar-date="${escapeHtml(item.date || "sin-fecha")}">
      <span><b class="agenda-event-dot ${colorClass}"></b>${escapeHtml(agendaTypeLabel(item))}${item.is_overdue ? " · Vencido" : ""}</span>
      <strong>${escapeHtml(item.title || "Sin título")}</strong>
      <small>Estado: ${escapeHtml(agendaStatusLabel(item))}</small>
      <small>${escapeHtml(item.date ? formatDate(item.date) : "Sin fecha")}${agendaEventTime(item) ? ` · ${escapeHtml(agendaEventTime(item))}` : ""}</small>
      <small>${escapeHtml(item.subtitle || "")}</small>
      ${linked ? `<small>Licitación vinculada: ${escapeHtml(linked)}</small>` : ""}
      ${renderAgendaActions(item)}
    </article>
  `;
}

function renderCalendarDayPanel(items, key) {
  const dateText = agendaDayHeading(key);
  const sorted = [...items].sort(compareCalendarItems);
  calendarDayPanel.innerHTML = renderAgendaListPanel(
    "Calendario",
    "Eventos del día seleccionado",
    renderAgendaGroup(dateText, sorted)
  );
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

function dateWarningText(value, { required = false } = {}) {
  if (!value) return required ? "La fecha y hora es obligatoria." : "Esta actuación no tiene fecha límite.";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Formato de fecha inválido.";
  const warnings = [];
  if (!String(value).includes("T")) warnings.push("No se ha indicado hora.");
  if (parsed.getTime() < Date.now()) warnings.push("La fecha indicada ya ha pasado.");
  return warnings.join(" ");
}

function showDateWarning(element, value, options = {}) {
  if (!element) return;
  const text = dateWarningText(value, options);
  element.hidden = !text;
  element.textContent = text;
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
        <button data-edit-news="${escapeHtml(item.id)}">Editar</button>
        <button class="danger" data-delete-news="${escapeHtml(item.id)}">Eliminar</button>
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
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
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
  const response = await fetch(`/api/news/${id}`, { method: "DELETE", headers: csrfHeaders() });
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
  const storageResponse = await fetch("/api/storage/status");
  appState.storage = storageResponse.ok
    ? await storageResponse.json()
    : { error: "No se pudo cargar el estado de almacenamiento." };
  renderConfig();
}

function renderConfig() {
  renderUsersConfig();
  renderSettingsConfig();
  renderStorageConfig();
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
  settingsForm.elements.agenda_email_to.value = settings.agenda_email_to || "";
  settingsForm.elements.seguimiento_emails.value = settings.seguimiento_emails || "";
  settingsForm.elements.smtp_tls.checked = settings.smtp_tls !== "0";
  settingsForm.elements.smtp_ssl.checked = settings.smtp_ssl === "1";
  settingsForm.elements.smtp_password.placeholder = settings.smtp_password_set
    ? "Contraseña guardada, dejar vacío para no cambiar"
    : "Sin contraseña guardada";
  settingsForm.elements.smtp_password.value = "";
  settingsForm.elements.clear_smtp_password.checked = false;
}

function storageValue(value) {
  if (value === true) return "Sí";
  if (value === false) return "No";
  return value || "No configurado";
}

function renderStorageConfig() {
  const storage = appState.storage || {};
  if (storage.error) {
    storageStatusBoard.innerHTML = `<div class="empty">${escapeHtml(storage.error)}</div>`;
    return;
  }
  const warnings = storage.warnings || [];
  const apiStatus = storage.dropbox_api_status === "experimental_enabled"
    ? "experimental activo"
    : "experimental desactivado";
  storageStatusBoard.innerHTML = `
    <div class="storage-status-row"><span>Modo actual</span><strong>${escapeHtml(storageValue(storage.current_mode_label || storage.backend))}</strong></div>
    <div class="storage-status-row"><span>Carpeta local</span><strong>${escapeHtml(storageValue(storage.local_download_root))}</strong></div>
    <div class="storage-status-row"><span>Dropbox Desktop</span><strong>${escapeHtml(storage.dropbox_desktop_detected ? "detectado" : "no detectado")}</strong></div>
    <div class="storage-status-row"><span>Escaneo marcadores</span><strong>${escapeHtml(`${storage.monitor_year_min || 2000}-${storage.monitor_year_max || 2300}`)}</strong></div>
    <div class="storage-status-row"><span>Dropbox API</span><strong>${escapeHtml(apiStatus)}</strong></div>
    <div class="storage-status-row"><span>Raíz API remota</span><strong>${escapeHtml(storageValue(storage.root))}</strong></div>
    ${warnings.length ? `<div class="notification-warning">${warnings.map(escapeHtml).join("<br>")}</div>` : ""}
  `;
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
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
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
  const response = await fetch(`/api/config/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
    headers: csrfHeaders(),
  });
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
    agenda_email_to: settingsForm.elements.agenda_email_to.value.trim(),
    seguimiento_emails: settingsForm.elements.seguimiento_emails.value.trim(),
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
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
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
    const response = await fetch("/api/config/test-smtp", { method: "POST", headers: csrfHeaders() });
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

async function runDropboxAction(button, endpoint, loadingText) {
  if (!isAdmin()) return;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = loadingText;
  storageResult.className = "import-result";
  storageResult.textContent = loadingText;
  try {
    const response = await fetch(endpoint, { method: "POST", headers: csrfHeaders() });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      storageResult.className = "import-result error";
      storageResult.textContent = result.error || result.message || "No se pudo completar la operación Dropbox.";
      return;
    }
    storageResult.className = "import-result ok";
    storageResult.textContent = result.message || (
      result.dry_run
        ? `Dry-run correcto. Ficheros previstos: ${result.would_upload_count || 0}.`
        : "Operación Dropbox completada."
    );
    const statusResponse = await fetch("/api/storage/status");
    appState.storage = statusResponse.ok ? await statusResponse.json() : appState.storage;
    renderStorageConfig();
  } catch (error) {
    storageResult.className = "import-result error";
    storageResult.textContent = error.message || "No se pudo completar la operación Dropbox.";
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function testDropboxConfig() {
  runDropboxAction(testDropboxButton, "/api/storage/dropbox/test", "Probando Dropbox...");
}

function dryRunDropboxConfig() {
  runDropboxAction(dryRunDropboxButton, "/api/storage/dropbox/dry-run", "Simulando dry-run...");
}

async function syncDropboxMarkers() {
  if (!isAdmin()) return;
  const originalText = syncDropboxMarkersButton.textContent;
  syncDropboxMarkersButton.disabled = true;
  syncDropboxMarkersButton.textContent = "Sincronizando...";
  storageResult.className = "import-result";
  storageResult.textContent = "Sincronizando marcadores Dropbox...";
  try {
    const response = await fetch("/api/storage/markers/sync", { method: "POST", headers: csrfHeaders() });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      storageResult.className = "import-result error";
      storageResult.textContent = result.error || "No se pudo sincronizar marcadores Dropbox.";
      return;
    }
    storageResult.className = result.conflicts?.length || result.warnings?.length ? "import-result warning" : "import-result ok";
    storageResult.textContent = `Marcadores: ${result.found || 0}. Rutas actualizadas: ${result.updated || 0}. En seguimiento: ${result.following || 0}. Conflictos: ${(result.conflicts || []).length}. Avisos: ${(result.warnings || []).length}.`;
    await loadItems();
  } catch (error) {
    storageResult.className = "import-result error";
    storageResult.textContent = error.message || "No se pudo sincronizar marcadores Dropbox.";
  } finally {
    syncDropboxMarkersButton.disabled = false;
    syncDropboxMarkersButton.textContent = originalText;
  }
}

function monitorSummaryText(result) {
  return [
    `Modo: ${result.mode || ""}`,
    `Años: ${(result.year_roots || []).length}`,
    `Marcadores: ${result.found_markers_count || 0}`,
    `Licitaciones monitorizadas: ${result.followed_count || 0}`,
    `Carpetas revisadas: ${result.folders_checked_count || 0}`,
    `Carpetas corregidas: ${result.folders_repaired_count || result.route_updates_count || 0}`,
    `Carpetas con incidencias: ${result.folders_broken_count || 0}`,
    `Plataformas consultadas: ${result.platforms_checked_count || 0}`,
    `Modificaciones localizadas: ${result.changes_detected_count || 0}`,
    `Correos preparados/enviados: ${result.emails_prepared_count || 0}/${result.emails_sent_count || 0}`,
    `Conflictos: ${(result.conflicts || []).length}`,
    `Avisos: ${(result.warnings || []).length}`,
  ].join(". ");
}

function monitorEmailResultText(result) {
  const details = result.task_details || {};
  const recipient = details.recipient ? ` Destinatario: ${details.recipient}.` : "";
  return `Resumen de agenda preparado: ${result.emails_prepared_count || 0}. Enviado: ${result.emails_sent_count || 0}.${recipient}`;
}

function monitorStatusLabel(status) {
  const labels = {
    running: "En curso",
    completed: "Completada",
    completed_with_errors: "Completada con errores",
    failed: "Fallida",
    ok: "Completada",
    error: "Fallida",
  };
  return labels[status] || status || "Pendiente";
}

function monitorStatusClass(status) {
  if (status === "completed") return "ok";
  if (status === "completed_with_errors") return "warning";
  if (status === "failed" || status === "error") return "error";
  return "running";
}

function monitorTaskTypeLabel(taskType) {
  return monitorTaskTypeLabels[taskType] || taskType || "Licitaciones";
}

function monitorIncidenceText(item) {
  if (item.error_message) return item.error_message;
  const conflicts = Number(item.conflicts_count || 0);
  const warnings = Number(item.warnings_count || 0);
  if (conflicts || warnings) return `${conflicts} conflicto(s), ${warnings} aviso(s)`;
  return "Sin incidencias";
}

async function loadMonitorRuns() {
  if (!isAdmin() || !monitorRunsBoard) return;
  monitorRunsBoard.innerHTML = `<div class="empty">Cargando histórico...</div>`;
  try {
    const params = new URLSearchParams({ limit: "50" });
    if (monitorTaskTypeFilter?.value) params.set("task_type", monitorTaskTypeFilter.value);
    const response = await fetch(`/api/monitor/runs?${params.toString()}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      monitorRunsBoard.innerHTML = `<div class="empty">No se pudo cargar el histórico del monitor.</div>`;
      if (monitorRunDetail) monitorRunDetail.innerHTML = `<div class="empty">${escapeHtml(data.error || "Sin detalle disponible.")}</div>`;
      return;
    }
    appState.monitorRuns = data.items || [];
    renderMonitorRuns();
  } catch (error) {
    monitorRunsBoard.innerHTML = `<div class="empty">${escapeHtml(error.message || "No se pudo cargar el histórico del monitor.")}</div>`;
  }
}

function renderMonitorRuns() {
  if (!monitorRunsBoard) return;
  if (!appState.monitorRuns.length) {
    monitorRunsBoard.innerHTML = `<div class="empty">Todavía no hay ejecuciones del monitor.</div>`;
    if (monitorRunDetail) monitorRunDetail.innerHTML = `<div class="empty">Ejecuta el monitor para ver detalle aquí.</div>`;
    return;
  }
  monitorRunsBoard.innerHTML = appState.monitorRuns.map((item, index) => `
    <button type="button" class="monitor-run-card ${index === 0 ? "active" : ""}" data-monitor-run="${escapeHtml(item.id)}">
      <span class="monitor-run-head">
        <strong>${escapeHtml(formatDateTime(item.started_at) || item.started_at || `Ejecución ${item.id}`)}</strong>
        <span class="monitor-status ${monitorStatusClass(item.status)}">${escapeHtml(monitorStatusLabel(item.status))}</span>
      </span>
      <span class="monitor-run-meta">
        <span>Tipo: ${escapeHtml(monitorTaskTypeLabel(item.task_type))}</span>
        <span>Elementos: ${escapeHtml(item.processed_items_count || item.followed_count || 0)}</span>
        <span>Cambios: ${escapeHtml(item.changes_detected_count || 0)}</span>
        <span>Correos: ${escapeHtml(item.emails_prepared_count || 0)}/${escapeHtml(item.emails_sent_count || 0)}</span>
        <span>Corregidas: ${escapeHtml(item.folders_repaired_count || item.route_updates_count || 0)}</span>
      </span>
    </button>
  `).join("");
  renderMonitorRunDetail(appState.monitorRuns[0]);
}

async function openMonitorRun(id) {
  if (!id || !monitorRunDetail) return;
  monitorRunsBoard?.querySelectorAll("[data-monitor-run]").forEach((button) => {
    button.classList.toggle("active", button.dataset.monitorRun === String(id));
  });
  monitorRunDetail.innerHTML = `<div class="empty">Cargando detalle...</div>`;
  const response = await fetch(`/api/monitor/runs/${encodeURIComponent(id)}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    monitorRunDetail.innerHTML = `<div class="empty">${escapeHtml(data.error || "No se pudo cargar el detalle.")}</div>`;
    return;
  }
  renderMonitorRunDetail(data.item);
}

function renderMonitorRunDetail(item) {
  if (!monitorRunDetail || !item) return;
  const details = item.details || {};
  const taskDetails = details.task_details || {};
  const warnings = details.warnings || [];
  const conflicts = details.conflicts || [];
  const updates = details.route_updates || [];
  const incidents = [...conflicts, ...warnings];
  monitorRunDetail.innerHTML = `
    <div class="panel-head">
      <div>
        <p class="eyebrow">Detalle</p>
        <h3>${escapeHtml(formatDateTime(item.started_at) || item.started_at || `Ejecución ${item.id}`)}</h3>
      </div>
      <span class="monitor-status ${monitorStatusClass(item.status)}">${escapeHtml(monitorStatusLabel(item.status))}</span>
    </div>
    <div class="monitor-detail-grid">
      <div class="detail"><span>Tipo de tarea</span>${escapeHtml(monitorTaskTypeLabel(item.task_type))}</div>
      <div class="detail"><span>Modo</span>${escapeHtml(item.mode || "No informado")}</div>
      <div class="detail"><span>Programación</span>${escapeHtml(item.schedule_key || "Manual")}</div>
      <div class="detail"><span>Finalización</span>${escapeHtml(formatDateTime(item.finished_at) || "En curso")}</div>
      <div class="detail"><span>Elementos procesados</span>${escapeHtml(item.processed_items_count || 0)}</div>
      <div class="detail"><span>Elementos avisados</span>${escapeHtml(taskDetails.items_notified_count ?? item.changes_detected_count ?? 0)}</div>
      <div class="detail"><span>Licitaciones monitorizadas</span>${escapeHtml(item.followed_count || 0)}</div>
      <div class="detail"><span>Carpetas revisadas</span>${escapeHtml(item.folders_checked_count || 0)}</div>
      <div class="detail"><span>Carpetas corregidas</span>${escapeHtml(item.folders_repaired_count || item.route_updates_count || 0)}</div>
      <div class="detail"><span>Carpetas con incidencias</span>${escapeHtml(item.folders_broken_count || 0)}</div>
      <div class="detail"><span>Plataformas consultadas</span>${escapeHtml(item.platforms_checked_count || 0)}</div>
      <div class="detail"><span>Modificaciones localizadas</span>${escapeHtml(item.changes_detected_count || 0)}</div>
      <div class="detail"><span>Correos preparados</span>${escapeHtml(item.emails_prepared_count || 0)}</div>
      <div class="detail"><span>Correos enviados</span>${escapeHtml(item.emails_sent_count || 0)}</div>
      <div class="detail full-width"><span>Raíz</span>${escapeHtml(item.root_path || "No informada")}</div>
      <div class="detail full-width"><span>Incidencias</span>${escapeHtml(monitorIncidenceText(item))}</div>
    </div>
    ${updates.length ? `<div class="monitor-detail-list"><h4>Rutas corregidas</h4>${updates.map((entry) => `
      <article class="history-row">
        <strong>ID ${escapeHtml(entry.licitacion_id)}</strong>
        <small>${escapeHtml(entry.old_path || "Sin ruta previa")}</small>
        <span>${escapeHtml(entry.new_path || "")}</span>
      </article>
    `).join("")}</div>` : ""}
    ${incidents.length ? `<div class="monitor-detail-list"><h4>Incidencias</h4>${incidents.map((entry) => `
      <article class="history-row">
        <strong>${escapeHtml(entry.code || "incidencia")}</strong>
        <small>${escapeHtml(entry.path || "")}</small>
        <span>${escapeHtml(entry.message || "")}</span>
      </article>
    `).join("")}</div>` : ""}
  `;
}

async function runMonitorMode(button, mode, loadingText) {
  if (!isAdmin()) return;
  const originalText = button.textContent;
  const monitorButtons = [monitorDryRunButton, monitorRepairButton].filter(Boolean);
  monitorButtons.forEach((item) => { item.disabled = true; });
  button.textContent = loadingText;
  storageResult.className = "import-result";
  storageResult.textContent = loadingText;
  try {
    const response = await fetch("/api/monitor/run", {
      method: "POST",
      headers: { ...csrfHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      storageResult.className = "import-result error";
      storageResult.textContent = result.error || "No se pudo ejecutar el monitor.";
      return;
    }
    storageResult.className = result.conflicts?.length || result.warnings?.length ? "import-result warning" : "import-result ok";
    storageResult.textContent = monitorSummaryText(result);
    if (mode !== "dry-run") {
      await loadItems();
    }
    await loadMonitorRuns();
  } catch (error) {
    storageResult.className = "import-result error";
    storageResult.textContent = error.message || "No se pudo ejecutar el monitor.";
  } finally {
    button.textContent = originalText;
    monitorButtons.forEach((item) => { item.disabled = false; });
  }
}

async function sendMonitorAgendaTask(button, taskType, loadingText, errorText) {
  if (!isAdmin() || !button) return;
  const originalText = button.textContent;
  const monitorEmailButtons = [
    monitorSendAgendaSummaryButton,
    monitorSendAgendaDailyButton,
    monitorSendAgendaWeeklyButton,
  ].filter(Boolean);
  monitorEmailButtons.forEach((item) => { item.disabled = true; });
  button.textContent = "Enviando...";
  if (monitorActionResult) {
    monitorActionResult.className = "import-result";
    monitorActionResult.textContent = loadingText;
  }
  try {
    const response = await fetch("/api/monitor/run", {
      method: "POST",
      headers: { ...csrfHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ task_type: taskType, dry_run: false }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (monitorActionResult) {
        monitorActionResult.className = "import-result error";
        monitorActionResult.textContent = result.error || errorText;
      }
      await loadMonitorRuns();
      return;
    }
    if (monitorActionResult) {
      monitorActionResult.className = "import-result ok";
      monitorActionResult.textContent = monitorEmailResultText(result);
    }
    if (monitorTaskTypeFilter) monitorTaskTypeFilter.value = taskType;
    await loadMonitorRuns();
  } catch (error) {
    if (monitorActionResult) {
      monitorActionResult.className = "import-result error";
      monitorActionResult.textContent = error.message || errorText;
    }
  } finally {
    button.textContent = originalText;
    monitorEmailButtons.forEach((item) => { item.disabled = false; });
  }
}

syncDropboxMarkersButton?.addEventListener("click", syncDropboxMarkers);
monitorDryRunButton?.addEventListener("click", () => runMonitorMode(monitorDryRunButton, "dry-run", "Simulando monitor..."));
monitorRepairButton?.addEventListener("click", () => runMonitorMode(monitorRepairButton, "repair-routes", "Reparando rutas..."));
refreshMonitorRunsButton?.addEventListener("click", loadMonitorRuns);
monitorSendAgendaSummaryButton?.addEventListener("click", () => sendMonitorAgendaTask(
  monitorSendAgendaSummaryButton,
  "resumen_agenda",
  "Preparando y enviando resumen de agenda...",
  "No se pudo enviar el resumen de agenda.",
));
monitorSendAgendaDailyButton?.addEventListener("click", () => sendMonitorAgendaTask(
  monitorSendAgendaDailyButton,
  "agenda_diaria",
  "Preparando y enviando agenda diaria...",
  "No se pudo enviar la agenda diaria.",
));
monitorSendAgendaWeeklyButton?.addEventListener("click", () => sendMonitorAgendaTask(
  monitorSendAgendaWeeklyButton,
  "agenda_semanal",
  "Preparando y enviando agenda semanal...",
  "No se pudo enviar la agenda semanal.",
));
monitorTaskTypeFilter?.addEventListener("change", loadMonitorRuns);
monitorRunsBoard?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-monitor-run]");
  if (button) openMonitorRun(button.dataset.monitorRun);
});

function renderCard(item) {
  const fechaLimite = [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ");
  const remainingDays = daysUntil(item.fecha_limite, item.hora_limite);
  const enlacePerfil = normalizeUrl(item.enlace_perfil);
  const enlaceInfonalia = normalizeUrl(item.enlace_infonalia);
  const links = [
    enlacePerfil ? `<a href="${escapeHtml(enlacePerfil)}" target="_blank" rel="noreferrer">Perfil del contratante</a>` : "",
    enlaceInfonalia ? `<a href="${escapeHtml(enlaceInfonalia)}" target="_blank" rel="noreferrer">Anuncio Infonalia</a>` : "",
  ].filter(Boolean).join("");
  const isReview = Boolean(appState.currentDiaId);
  const stateActions = isAdmin() ? adminReviewEstados : nuriaEstados;
  const showStateActions = isReview;
  const dueText = dueLabel(remainingDays) || "Sin fecha";
  const dueClassName = remainingDays === null ? "" : dueClass(remainingDays);

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
              <span class="badge ${badgeClass(item.estado)}">${escapeHtml(estadoLabel(item.estado))}</span>
              <span class="due-chip ${dueClassName}">${escapeHtml(dueText)}</span>
              ${item.provincia ? `<span class="province-chip">${escapeHtml(item.provincia)}</span>` : ""}
            </div>
          </div>

          <div class="details">
            <div class="detail"><span>Tipo</span>${escapeHtml(item.tipo)}</div>
            <div class="detail"><span>Presupuesto</span>${escapeHtml(formatMoney(item.presupuesto))}</div>
            <div class="detail"><span>Fecha límite</span>${escapeHtml(fechaLimite)}</div>
          </div>

          ${links ? `<div class="links">${links}</div>` : ""}

          ${showStateActions ? `<div class="card-actions state-actions">
            ${stateActions.map((estado) => `
              <button class="${item.estado === estado ? "active-state" : ""}" data-id="${escapeHtml(item.id)}" data-estado="${escapeHtml(estado)}">${escapeHtml(estadoActionLabel(estado))}</button>
            `).join("")}
          </div>` : ""}
        </div>

        <div class="card-side-actions">
          <button data-open-licitacion-detail="${escapeHtml(item.id)}">Abrir</button>
          ${isAdmin() ? `<button data-edit-id="${escapeHtml(item.id)}">Editar</button>` : ""}
          <button data-new-actuacion-id="${escapeHtml(item.id)}">Crear nueva actuación</button>
          <span class="card-side-id">ID ${escapeHtml(item.id)}</span>
        </div>
      </div>
    </article>
  `;
}

function renderExpandedCard(item, detail) {
  if (!detail) {
    return `<div class="card-expanded"><div class="empty">Cargando información ampliada...</div></div>`;
  }

  const detailItem = detail.item || item;
  const linkedActuaciones = detailItem.actuaciones || [];
  const documentCount = documentCountLabel(detailItem);

  return `
    <div class="card-expanded">
      <section class="expanded-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Resumen</p>
            <h3>${escapeHtml(detailItem.expediente || item.expediente)}</h3>
          </div>
        </div>
        ${renderLicitacionSummary(detailItem)}
        ${renderLicitacionMainActions(detailItem)}
      </section>
      <section class="expanded-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Documentación</p>
            <h3>${escapeHtml(documentCount)}</h3>
          </div>
          ${isAdmin() ? `<button class="download-button" data-download-id="${escapeHtml(item.id)}">Descargar documentación</button>` : ""}
        </div>
        ${renderLicitacionDocuments(detailItem)}
      </section>
      <section class="expanded-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Actuaciones vinculadas</p>
            <h3>${escapeHtml(linkedActuaciones.length ? `${linkedActuaciones.length} actuación(es)` : "Sin actuaciones vinculadas")}</h3>
          </div>
          <button data-new-actuacion-id="${escapeHtml(item.id)}">Nueva actuación desde esta licitación</button>
        </div>
        ${linkedActuaciones.length ? renderLinkedActuaciones(linkedActuaciones) : `<div class="empty">No hay actuaciones vinculadas a esta licitación.</div>`}
      </section>
      <section class="expanded-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Seguimiento</p>
            <h3>${detailItem.seguimiento_activo ? "En seguimiento" : "No en seguimiento"}</h3>
          </div>
        </div>
        ${renderLicitacionTracking(detailItem)}
      </section>
    </div>
  `;
}

function renderLicitacionDetailView(item) {
  const actuaciones = item.actuaciones || [];
  const seguimiento = item.seguimiento || {};
  const folder = item.ruta_carpeta || "";
  const folderUrl = fileUrl(folder);
  const profile = normalizeUrl(item.enlace_perfil);
  const infonalia = normalizeUrl(item.enlace_infonalia);
  const fechaLimite = [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ");
  const documentCount = documentCountLabel(item);
  return `
    <article class="licitacion-print-sheet">
      <section class="expanded-panel detail-hero">
        <div>
          <p class="eyebrow">Expediente</p>
          <h2>${escapeHtml(item.expediente || "Sin expediente")}</h2>
          <p>${escapeHtml(item.organismo || "Organismo no informado")}</p>
        </div>
        <div class="card-flags">
          <span class="badge ${badgeClass(item.estado)}">${escapeHtml(estadoLabel(item.estado))}</span>
          ${fechaLimite ? `<span class="due-chip">${escapeHtml(fechaLimite)}</span>` : ""}
          ${item.plataforma ? `<span class="province-chip">${escapeHtml(item.plataforma)}</span>` : ""}
          ${item.provincia ? `<span class="province-chip">${escapeHtml(item.provincia)}</span>` : ""}
        </div>
      </section>

      <section class="expanded-panel no-print">
        <div class="card-actions state-actions">
          ${isAdmin() ? `<button class="download-button" data-download-id="${escapeHtml(item.id)}">Descargar</button>` : ""}
          ${isAdmin() ? `<button data-edit-id="${escapeHtml(item.id)}">Editar</button>` : ""}
          ${isAdmin() ? `<button data-duplicate-id="${escapeHtml(item.id)}">Duplicar</button>` : ""}
          ${isAdmin() ? `<button data-new-actuacion-id="${escapeHtml(item.id)}">Crear nueva actuación</button>` : ""}
          ${isAdmin() ? `<button class="danger" data-delete-id="${escapeHtml(item.id)}">Borrar</button>` : ""}
        </div>
      </section>

      <section class="expanded-panel">
        <div class="panel-head"><div><p class="eyebrow">Resumen de la licitación</p><h3>Información principal</h3></div></div>
        <div class="detail-grid">
          <div class="detail full-width"><span>Objeto</span>${escapeHtml(item.objeto || "No informado")}</div>
          <div class="detail"><span>Presupuesto</span>${escapeHtml(formatMoney(item.presupuesto))}</div>
          <div class="detail"><span>Estado</span>${escapeHtml(estadoLabel(item.estado))}</div>
          <div class="detail full-width"><span>Observaciones</span>${escapeHtml(item.comentario || "Sin observaciones")}</div>
        </div>
        <div class="links no-print">
          ${profile ? `<a href="${escapeHtml(profile)}" target="_blank" rel="noreferrer">Abrir enlace plataforma</a>` : ""}
          ${infonalia ? `<a href="${escapeHtml(infonalia)}" target="_blank" rel="noreferrer">Abrir Infonalia</a>` : ""}
        </div>
      </section>

      <section class="expanded-panel">
        <div class="panel-head"><div><p class="eyebrow">Datos administrativos</p><h3>Contratación</h3></div></div>
        <div class="detail-grid">
          <div class="detail"><span>Expediente</span>${escapeHtml(item.expediente || "No informado")}</div>
          <div class="detail"><span>Órgano / organismo</span>${escapeHtml(item.organismo || "No informado")}</div>
          <div class="detail"><span>Tipo de contrato</span>${escapeHtml(item.tipo || "No informado")}</div>
          <div class="detail"><span>Procedimiento</span>${escapeHtml(item.procedimiento || "No informado")}</div>
          <div class="detail"><span>CPV</span>${escapeHtml(item.cpv || "No informado")}</div>
          <div class="detail"><span>Lugar ejecución</span>${escapeHtml(item.provincia || "No informado")}</div>
          <div class="detail"><span>Fecha presentación</span>${escapeHtml(fechaLimite || "No informado")}</div>
          <div class="detail"><span>Fecha Infonalia</span>${escapeHtml(formatDate(item.fecha_infonalia) || "No informado")}</div>
        </div>
      </section>

      <section class="expanded-panel">
        <div class="panel-head">
          <div><p class="eyebrow">Documentación</p><h3>${escapeHtml(documentCount)}</h3></div>
          ${folderUrl ? `<a class="no-print" href="${escapeHtml(folderUrl)}" target="_blank" rel="noreferrer">Abrir carpeta</a>` : ""}
        </div>
        <div class="detail-grid">
          <div class="detail full-width"><span>Carpeta</span>${escapeHtml(folder || "Sin carpeta")}</div>
          <div class="detail"><span>Estado descarga</span>${escapeHtml(item.descarga_fallida ? "Descarga fallida" : item.documentacion_descargada ? "Con documentación" : "Pendiente")}</div>
          <div class="detail"><span>Error descarga</span>${escapeHtml(item.download_error || "Sin errores")}</div>
        </div>
        ${renderLicitacionDocuments(item)}
      </section>

      <section class="expanded-panel">
        <div class="panel-head"><div><p class="eyebrow">Seguimiento</p><h3>${escapeHtml(seguimiento.activo ? "En seguimiento" : "No en seguimiento")}</h3></div></div>
        <div class="detail-grid">
          <div class="detail"><span>Estado</span>${escapeHtml(seguimiento.activo ? "En seguimiento" : "No en seguimiento")}</div>
          <div class="detail"><span>Fuente</span>${escapeHtml(seguimiento.fuente || "marcador Dropbox")}</div>
          <div class="detail full-width"><span>Carpeta detectada</span>${escapeHtml(seguimiento.folder_path || folder || "Sin carpeta")}</div>
          <div class="detail"><span>Marcador ID</span>${escapeHtml(seguimiento.id_marker_exists ? "Correcto" : "No encontrado")}</div>
          <div class="detail"><span>Última sincronización</span>${escapeHtml(seguimiento.ultima_sync || "Pendiente")}</div>
          ${seguimiento.warning ? `<div class="detail full-width warning-detail"><span>Aviso</span>${escapeHtml(seguimiento.warning)}</div>` : ""}
        </div>
      </section>

      <section class="expanded-panel">
        <div class="panel-head">
          <div><p class="eyebrow">Actuaciones vinculadas</p><h3>${escapeHtml(actuaciones.length ? `${actuaciones.length} actuación(es)` : "Sin actuaciones vinculadas")}</h3></div>
        </div>
        ${actuaciones.length ? renderLinkedActuaciones(actuaciones) : `<div class="empty">No hay actuaciones vinculadas a esta licitación.</div>`}
      </section>

    </article>
  `;
}

function renderLicitacionSummary(item) {
  const folder = item.ruta_carpeta || "";
  const profile = normalizeUrl(item.enlace_perfil);
  const infonalia = normalizeUrl(item.enlace_infonalia);
  const folderUrl = fileUrl(folder);
  const rows = [
    ["Objeto", item.objeto],
    ["Organismo", item.organismo],
    ["Plataforma", item.plataforma],
    ["Provincia", item.provincia],
    ["Presupuesto", formatMoney(item.presupuesto)],
    ["Fecha límite", [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ")],
    ["Estado interno", item.estado_interno || "Nueva"],
    ["Revisión", item.revisada ? "Revisada" : "No revisada"],
    ["Seguimiento", item.seguimiento_activo ? "Sí" : "No"],
    ["Ruta carpeta", folder || "Sin carpeta"],
  ];
  return `
    <div class="detail-grid">
      ${rows.map(([label, value]) => `<div class="detail"><span>${escapeHtml(label)}</span>${escapeHtml(value || "No informado")}</div>`).join("")}
    </div>
    <div class="links">
      ${folderUrl ? `<a href="${escapeHtml(folderUrl)}" target="_blank" rel="noreferrer">Abrir carpeta</a>` : ""}
      ${profile ? `<a href="${escapeHtml(profile)}" target="_blank" rel="noreferrer">Abrir enlace plataforma</a>` : ""}
      ${infonalia ? `<a href="${escapeHtml(infonalia)}" target="_blank" rel="noreferrer">Abrir Infonalia</a>` : ""}
    </div>
  `;
}

function renderLicitacionMainActions(item) {
  return `
    <div class="card-actions state-actions">
      ${isAdmin() ? `<button class="download-button" data-download-id="${escapeHtml(item.id)}">Descargar documentación</button>` : ""}
      <button data-toggle-reviewed="${escapeHtml(item.id)}" data-reviewed="${item.revisada ? "0" : "1"}">
        ${item.revisada ? "Marcar no revisada" : "Marcar revisada"}
      </button>
      <button data-new-actuacion-id="${escapeHtml(item.id)}">Nueva actuación</button>
      <button data-set-internal-state="${escapeHtml(item.id)}" data-internal-state="Descartada">Descartar</button>
    </div>
  `;
}

function fileUrl(path) {
  const value = String(path || "").trim();
  if (!value) return "";
  const normalized = value.replaceAll("\\", "/");
  if (/^[a-zA-Z]:\//.test(normalized)) return `file:///${encodeURI(normalized)}`;
  if (normalized.startsWith("/")) return `file://${encodeURI(normalized)}`;
  return "";
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size >= 1048576) return `${(size / 1048576).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function documentCountLabel(item) {
  const docs = item.documentos || [];
  if (docs.length) return `${docs.length} documento(s)`;
  return "Documentación";
}

function yesNo(value) {
  return value ? "Sí" : "No";
}

function renderDocumentSummary(item) {
  const summary = item.document_summary || {};
  if (!summary.total_files && !(item.documentos || []).length) return "";
  const metrics = [
    ["PCAP", yesNo(summary.has_pcap)],
    ["PPT", yesNo(summary.has_ppt)],
    ["Anuncio", yesNo(summary.has_announcement)],
    ["Requerimientos", summary.requirement_count || 0],
    ["Anexos", summary.annex_count || 0],
    ["Oferta/Sobres", yesNo(summary.has_offer_documents)],
    ["Relevantes", summary.relevant_files_count || (item.documentos || []).length || 0],
  ];
  return `
    <div class="document-summary-grid">
      ${metrics.map(([label, value]) => `<div class="document-summary-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
    </div>
  `;
}

function renderLicitacionDocuments(item) {
  const docs = item.documentos || [];
  if (!docs.length) return `<div class="empty">Sin documentación registrada.</div>`;
  return `
    <div class="document-table-wrap">
      <table class="document-table">
        <thead><tr><th>Tipo</th><th>Documento</th><th>Tamaño</th><th></th></tr></thead>
        <tbody>
          ${docs.map((doc) => `
            <tr>
              <td><span class="badge">${escapeHtml(doc.category || "Otros")}</span></td>
              <td><strong>${escapeHtml(doc.name)}</strong><small>${escapeHtml(doc.relative_path || "")}</small></td>
              <td>${escapeHtml(formatBytes(doc.size_bytes))}</td>
              <td>${doc.open_url ? `<a href="${escapeHtml(doc.open_url)}" target="_blank" rel="noreferrer">Abrir</a>` : ""}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderLicitacionTracking(item) {
  const seguimiento = item.seguimiento || {};
  const novedades = seguimiento.novedades || [];
  return `
    <div class="detail-grid">
      <div class="detail"><span>Estado</span>${escapeHtml(seguimiento.activo ? "En seguimiento" : "No en seguimiento")}</div>
      <div class="detail"><span>Fuente</span>${escapeHtml(seguimiento.fuente || "marcador Dropbox")}</div>
      <div class="detail"><span>Última sincronización</span>${escapeHtml(seguimiento.ultima_sync || seguimiento.ultimo_check || "Pendiente")}</div>
      <div class="detail"><span>Última novedad</span>${escapeHtml(seguimiento.ultima_novedad || "Sin novedades")}</div>
      ${seguimiento.warning ? `<div class="detail full-width warning-detail"><span>Aviso</span>${escapeHtml(seguimiento.warning)}</div>` : ""}
    </div>
    ${novedades.length ? novedades.map((entry) => `
      <article class="history-row">
        <strong>${escapeHtml(entry.title)}</strong>
        <small>${escapeHtml(entry.detected_at)} · ${escapeHtml(entry.change_type || entry.source || "")}</small>
        <span>${escapeHtml(entry.summary || "")}</span>
      </article>
    `).join("") : `<div class="empty">Sin novedades registradas todavía.</div>`}
  `;
}

function renderLicitacionWorkFields(item) {
  return `
    <div class="form-grid compact-form">
      <label>Estado interno
        <select data-internal-state-for="${escapeHtml(item.id)}">
          ${estadosInternos.map((estado) => `<option value="${escapeHtml(estado)}" ${estado === (item.estado_interno || "Nueva") ? "selected" : ""}>${escapeHtml(estado)}</option>`).join("")}
        </select>
      </label>
      <label class="full-width">Notas internas
        <textarea rows="3" data-notes-for="${escapeHtml(item.id)}">${escapeHtml(item.notas_internas || "")}</textarea>
      </label>
    </div>
  `;
}

function renderLicitacionHistory(item) {
  const rows = item.historial || [];
  if (!rows.length) return `<div class="empty">Sin histórico todavía.</div>`;
  return rows.map((entry) => `
    <article class="history-row">
      <strong>${escapeHtml(entry.event_type)}</strong>
      <small>${escapeHtml(entry.created_at)} · ${escapeHtml(entry.user_id || "Sistema")}</small>
      <span>${escapeHtml(entry.old_value || "")} → ${escapeHtml(entry.new_value || "")}</span>
    </article>
  `).join("");
}

function renderLinkedActuaciones(items) {
  return `
    <div class="linked-actuaciones">
      ${items.map((actuacion) => `
        <article class="linked-actuacion ${actuacion.estado_visual === "vencida" ? "agenda-event--vencido" : "agenda-event--actuacion"}">
          <div>
            <span class="due-chip ${escapeHtml(actuacion.estado_visual || "")}">${escapeHtml(actuacionLabel(actuacionEstadoLabels, actuacion.estado))}</span>
            <strong>${escapeHtml(actuacion.titulo || "Actuación")}</strong>
            <small>${escapeHtml(actuacion.deadline_at ? formatDateTime(actuacion.deadline_at) : "Sin fecha")}</small>
            ${actuacion.ultimo_comentario ? `<small>${escapeHtml(actuacion.ultimo_comentario)}</small>` : `<small>${escapeHtml(actuacion.historial_count || 0)} comentario(s)</small>`}
          </div>
          <div class="links">
            <button data-edit-actuacion="${escapeHtml(actuacion.id)}">Abrir actuación</button>
            <button data-comment-actuacion="${escapeHtml(actuacion.id)}">Añadir comentario</button>
          </div>
        </article>
      `).join("")}
    </div>
  `;
}


async function updateEstado(id, estado) {
  const response = await fetch(`/api/licitaciones/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
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
    const response = await fetch(endpoint, { method: "POST", headers: csrfHeaders() });
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
    const response = await fetch(`/api/dias/${appState.currentDiaId}/enviar-nuria`, {
      method: "POST",
      headers: csrfHeaders(),
    });
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
    const response = await fetch(`/api/licitaciones/${id}/descargar`, {
      method: "POST",
      headers: csrfHeaders(),
    });
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

async function toggleDetails(id) {
  const key = String(id);
  if (appState.expandedCards.has(key)) {
    appState.expandedCards.delete(key);
    renderBoard();
    return;
  }
  appState.expandedCards.add(key);
  if (!appState.cardDetails[id]) {
    appState.cardDetails[id] = {};
  }
  renderBoard();
  try {
    const response = await fetch(`/api/licitaciones/${id}`);
    const result = await response.json().catch(() => ({}));
    if (response.ok) {
      appState.cardDetails[id] = { ...(appState.cardDetails[id] || {}), item: result.item };
      renderBoard();
    }
  } catch {
    appState.cardDetails[id] = { ...(appState.cardDetails[id] || {}), loadError: true };
    renderBoard();
  }
}

async function openLicitacionDetail(id) {
  licitacionDetailTitle.textContent = "Cargando licitación...";
  licitacionDetailContent.innerHTML = `<div class="empty">Cargando ficha ampliada...</div>`;
  licitacionDetailDialog.showModal();
  const response = await fetch(`/api/licitaciones/${id}`);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    licitacionDetailContent.innerHTML = `<div class="empty">No se pudo cargar la ficha.</div>`;
    return;
  }
  const item = result.item;
  appState.cardDetails[id] = { ...(appState.cardDetails[id] || {}), item };
  licitacionDetailTitle.textContent = item.expediente || "Licitación";
  licitacionDetailContent.innerHTML = renderLicitacionDetailView(item);
}

async function refreshLicitacionDetail(id) {
  const response = await fetch(`/api/licitaciones/${id}`);
  const result = await response.json().catch(() => ({}));
  if (response.ok) {
    appState.cardDetails[id] = { ...(appState.cardDetails[id] || {}), item: result.item };
  }
}

async function patchLicitacionWork(id, payload) {
  const response = await fetch(`/api/licitaciones/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo actualizar la licitación.");
    return false;
  }
  await loadItems();
  await refreshLicitacionDetail(id);
  renderBoard();
  const detail = appState.cardDetails[id]?.item;
  if (detail && licitacionDetailDialog.open) {
    licitacionDetailTitle.textContent = detail.expediente || "Licitación";
    licitacionDetailContent.innerHTML = renderLicitacionDetailView(detail);
  }
  return true;
}

function renderCaptureResult(message, type = "", details = []) {
  capturePlatformResult.className = `import-result capture-result ${type}`.trim();
  const detailItems = details.filter(Boolean).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  capturePlatformResult.innerHTML = `${escapeHtml(message)}${detailItems ? `<ul>${detailItems}</ul>` : ""}`;
}

function applyCapturedFields(fields) {
  const filled = [];
  const skipped = [];
  const seenTargets = new Set();
  Object.entries(fields || {}).forEach(([field, rawValue]) => {
    const value = String(rawValue ?? "").trim();
    const target = captureFieldTargets[field];
    if (!value || !target || !form.elements[target] || seenTargets.has(target)) return;
    seenTargets.add(target);
    const label = captureFieldLabels[field] || field;
    if (String(form.elements[target].value || "").trim()) {
      skipped.push(label);
      return;
    }
    form.elements[target].value = value;
    filled.push(label);
  });
  return { filled, skipped };
}

async function capturePlatformData() {
  if (!isAdmin()) return;
  const profileUrl = String(form.elements.enlace_perfil?.value || "").trim();
  const defaultCaptureUrl = profileUrl.includes("GetDocumentByIdServlet") ? profileUrl : "";
  const requestedUrl = window.prompt("Pega la URL XML del pliego o documento PLACE:", defaultCaptureUrl);
  if (requestedUrl === null) return;
  const url = String(requestedUrl || "").trim();
  if (!url) {
    renderCaptureResult("Pega la URL XML del pliego o documento PLACE.", "error");
    return;
  }
  capturePlatformButton.disabled = true;
  renderCaptureResult("Consultando XML de PLACE...", "");
  try {
    const response = await fetch("/api/licitaciones/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ url, profile_url: profileUrl || undefined }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      renderCaptureResult(result.error || "Error consultando plataforma.", "error");
      return;
    }
    const fields = result.fields || {};
    const { filled, skipped } = applyCapturedFields(fields);
    const captured = Object.entries(fields)
      .filter(([, value]) => String(value ?? "").trim())
      .map(([field, value]) => `${captureFieldLabels[field] || field}: ${value}`);
    const details = [
      ...captured.slice(0, 8),
      ...skipped.map((label) => `${label}: campo ya tenía valor, no se ha sobrescrito`),
      ...(result.warnings || []),
    ];
    if (filled.length) {
      renderCaptureResult(`Datos capturados correctamente. Se han capturado ${filled.length} campos.`, "ok", details);
      return;
    }
    renderCaptureResult(
      captured.length ? "Datos capturados, pero no se han sobrescrito campos con valor." : "No se han encontrado datos suficientes.",
      captured.length ? "ok" : "error",
      details
    );
  } catch (error) {
    renderCaptureResult(error.message || "Error consultando plataforma.", "error");
  } finally {
    capturePlatformButton.disabled = false;
  }
}

function openCreateEditor() {
  form.reset();
  capturePlatformResult.textContent = "";
  form.elements.id.value = "";
  editorEyebrow.textContent = "Alta manual";
  editorTitle.textContent = "Nueva licitación";
  form.elements.estado.value = "Importada";
  editor.showModal();
}

function openEditEditor(id) {
  let item = [...appState.items, ...appState.calendarItems].find((entry) => (
    String(entry.id) === String(id) || String(entry.source_id || "") === String(id)
  ));
  if (item?.source_type === "licitacion") item = item.linked_licitaciones?.[0] || item;
  if (!item) return;

  form.reset();
  capturePlatformResult.textContent = "";
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
  capturePlatformResult.textContent = "";
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

  const response = await fetch(`/api/licitaciones/${id}`, { method: "DELETE", headers: csrfHeaders() });
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

  const response = await fetch(`/api/dias/${id}`, { method: "DELETE", headers: csrfHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(result.error || "No se pudo borrar el día Infonalia.");
    return;
  }

  if (String(appState.currentDiaId) === String(id)) {
    appState.currentDiaId = "";
    appState.currentDiaTitle = "Centro de licitaciones";
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
document.getElementById("actuaciones-button").addEventListener("click", showActuacionesView);
logoutButton?.addEventListener("click", logout);
document.getElementById("notifications-button").addEventListener("click", showNotificationsView);
document.getElementById("back-from-notifications").addEventListener("click", backFromNotifications);
document.getElementById("news-admin-button").addEventListener("click", showNewsAdminView);
document.getElementById("monitor-button").addEventListener("click", showMonitorView);
document.getElementById("config-button").addEventListener("click", showConfigView);
document.getElementById("back-from-config").addEventListener("click", backFromConfig);
document.getElementById("back-to-days").addEventListener("click", showDaysView);
reviewDayButton.addEventListener("click", markDayReviewed);
sendNuriaButton.addEventListener("click", sendDayToNuria);
licitacionesTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-licitaciones-view]");
  if (!button) return;
  appState.licitacionesView = button.dataset.licitacionesView;
  dateOrder.value = appState.licitacionesView === "live" ? "asc" : "desc";
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
capturePlatformButton.addEventListener("click", capturePlatformData);
document.getElementById("import-button").addEventListener("click", () => {
  importResult.textContent = "";
  importer.showModal();
});
document.getElementById("close-importer").addEventListener("click", () => importer.close());
document.getElementById("cancel-importer").addEventListener("click", () => importer.close());
stateFilter.addEventListener("change", loadItems);
dateOrder.addEventListener("change", loadItems);
licitacionesActuacionesFilter.addEventListener("change", loadItems);
licitacionesQuickFilter.addEventListener("change", loadItems);
searchInput.addEventListener("input", debounce(loadItems, 250));
calendarSearch.addEventListener("input", debounce(loadCalendarItems, 250));
calendarStateFilter.addEventListener("change", () => {
  appState.agendaType = calendarStateFilter.value || "all";
  loadCalendarItems();
});
agendaWorkbench.addEventListener("click", (event) => {
  const sectionButton = event.target.closest("button[data-workbench-key]");
  if (sectionButton) {
    activateWorkbenchSection(sectionButton.dataset.workbenchKey);
    return;
  }
  const licitacionButton = event.target.closest("button[data-workbench-licitacion]");
  if (licitacionButton) {
    showLicitacionesView({ view: "all" });
    toggleDetails(licitacionButton.dataset.workbenchLicitacion);
    return;
  }
  const actuacionesButton = event.target.closest("button[data-workbench-actuaciones]");
  if (actuacionesButton) {
    actuacionesFilter.value = "abiertas";
    showActuacionesView();
    return;
  }
  const actuacionButton = event.target.closest("button[data-workbench-actuacion]");
  if (actuacionButton) editActuacion(actuacionButton.dataset.workbenchActuacion);
});
document.querySelectorAll("[data-agenda-view]").forEach((button) => {
  button.addEventListener("click", () => {
    appState.agendaView = button.dataset.agendaView || "day";
    const selected = parseDate(appState.calendarSelectedDate) || new Date();
    appState.calendarDate = new Date(selected.getFullYear(), selected.getMonth(), 1);
    loadCalendarItems();
  });
});
document.getElementById("calendar-prev").addEventListener("click", () => {
  const selected = parseDate(appState.calendarSelectedDate) || new Date();
  const next = appState.agendaView === "month"
    ? addMonths(appState.calendarDate, -1)
    : addDays(selected, appState.agendaView === "week" ? -7 : -1);
  appState.calendarDate = new Date(next.getFullYear(), next.getMonth(), 1);
  appState.calendarSelectedDate = dateKey(next);
  loadCalendarItems();
});
document.getElementById("calendar-next").addEventListener("click", () => {
  const selected = parseDate(appState.calendarSelectedDate) || new Date();
  const next = appState.agendaView === "month"
    ? addMonths(appState.calendarDate, 1)
    : addDays(selected, appState.agendaView === "week" ? 7 : 1);
  appState.calendarDate = new Date(next.getFullYear(), next.getMonth(), 1);
  appState.calendarSelectedDate = dateKey(next);
  loadCalendarItems();
});
document.getElementById("calendar-today").addEventListener("click", () => {
  const today = new Date();
  appState.calendarDate = new Date(today.getFullYear(), today.getMonth(), 1);
  appState.calendarSelectedDate = dateKey(today);
  loadCalendarItems();
});
document.getElementById("new-agenda-event-button").addEventListener("click", () => openAgendaEventoDialog());
document.getElementById("agenda-email-summary-button").addEventListener("click", sendAgendaEmailSummary);
document.getElementById("close-agenda-event-dialog").addEventListener("click", () => agendaEventDialog.close());
document.getElementById("cancel-agenda-event-dialog").addEventListener("click", () => agendaEventDialog.close());
agendaEventForm.addEventListener("submit", saveAgendaEvento);
agendaEventForm.elements.starts_at.addEventListener("input", () => (
  showDateWarning(agendaEventDateWarning, agendaEventForm.elements.starts_at.value, { required: true })
));
notificationSearch.addEventListener("input", debounce(loadNotifications, 250));
notificationScope.addEventListener("change", loadNotifications);
notificationDestination.addEventListener("change", loadNotifications);
notificationEmailState.addEventListener("change", loadNotifications);
actuacionesFilter.addEventListener("change", loadActuaciones);
document.getElementById("new-actuacion-button").addEventListener("click", () => openActuacionDialog());
document.getElementById("close-actuacion-dialog").addEventListener("click", () => actuacionDialog.close());
document.getElementById("cancel-actuacion-dialog").addEventListener("click", () => actuacionDialog.close());
document.getElementById("open-licitacion-selector").addEventListener("click", openLicitacionSelector);
document.getElementById("close-licitacion-selector").addEventListener("click", () => licitacionSelectorDialog.close());
document.getElementById("cancel-licitacion-selector").addEventListener("click", () => licitacionSelectorDialog.close());
document.getElementById("clear-licitacion-selection").addEventListener("click", () => {
  appState.actuacionSelectorDraft.clear();
  renderLicitacionSelectorResults();
});
document.getElementById("add-actuacion-comment").addEventListener("click", addActuacionComment);
actuacionForm.elements.deadline_at.addEventListener("input", () => (
  showDateWarning(actuacionDateWarning, actuacionForm.elements.deadline_at.value)
));
licitacionSelectorSearch.addEventListener("input", debounce(loadLicitacionSelectorResults, 250));
licitacionSelectorForm.addEventListener("submit", (event) => {
  event.preventDefault();
  commitLicitacionSelection();
});
licitacionSelectorResults.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[type='checkbox']");
  if (!checkbox) return;
  const item = (appState.actuacionSelectorResults || []).find((entry) => String(entry.id) === String(checkbox.value));
  if (!item) return;
  if (checkbox.checked) {
    appState.actuacionSelectorDraft.set(String(item.id), item);
  } else {
    appState.actuacionSelectorDraft.delete(String(item.id));
  }
});
actuacionSelectedLicitaciones.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-remove-selected-licitacion]");
  if (!button) return;
  setSelectedActuacionLicitaciones(
    (appState.actuacionSelectedLicitaciones || []).filter((item) => String(item.id) !== String(button.dataset.removeSelectedLicitacion))
  );
});
actuacionForm.addEventListener("submit", saveActuacion);
newsForm.addEventListener("submit", saveNews);
document.getElementById("reset-news-form").addEventListener("click", resetNewsForm);
userConfigForm.addEventListener("submit", saveUserConfig);
settingsForm.addEventListener("submit", saveSettingsConfig);
testSmtpButton.addEventListener("click", testSmtpConfig);
testDropboxButton.addEventListener("click", testDropboxConfig);
dryRunDropboxButton.addEventListener("click", dryRunDropboxConfig);
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

document.getElementById("close-licitacion-detail").addEventListener("click", () => licitacionDetailDialog.close());

licitacionDetailContent.addEventListener("click", (event) => {
  const downloadButton = event.target.closest("button[data-download-id]");
  if (downloadButton) {
    downloadLicitacion(downloadButton.dataset.downloadId, downloadButton);
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

  const newActuacionButton = event.target.closest("button[data-new-actuacion-id]");
  if (newActuacionButton) {
    openActuacionDialog(newActuacionButton.dataset.newActuacionId);
    return;
  }

  const deleteButton = event.target.closest("button[data-delete-id]");
  if (deleteButton) {
    deleteLicitacion(deleteButton.dataset.deleteId);
    licitacionDetailDialog.close();
    return;
  }

  const saveWorkButton = event.target.closest("button[data-save-licitacion-work]");
  if (saveWorkButton) {
    const id = saveWorkButton.dataset.saveLicitacionWork;
    const notes = licitacionDetailContent.querySelector(`[data-notes-for="${id}"]`);
    const state = licitacionDetailContent.querySelector(`[data-internal-state-for="${id}"]`);
    patchLicitacionWork(id, {
      notas_internas: notes ? notes.value : "",
      estado_interno: state ? state.value : "Nueva",
    });
    return;
  }

  const editActuacionButton = event.target.closest("button[data-edit-actuacion]");
  if (editActuacionButton) {
    editActuacion(editActuacionButton.dataset.editActuacion);
    return;
  }

  const commentActuacionButton = event.target.closest("button[data-comment-actuacion]");
  if (commentActuacionButton) {
    quickActuacionComment(commentActuacionButton.dataset.commentActuacion);
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
  const openDetailButton = event.target.closest("button[data-open-licitacion-detail]");
  if (openDetailButton) {
    openLicitacionDetail(openDetailButton.dataset.openLicitacionDetail);
    return;
  }

  const downloadButton = event.target.closest("button[data-download-id]");
  if (downloadButton) {
    downloadLicitacion(downloadButton.dataset.downloadId, downloadButton);
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

  const newActuacionButton = event.target.closest("button[data-new-actuacion-id]");
  if (newActuacionButton) {
    openActuacionDialog(newActuacionButton.dataset.newActuacionId);
    return;
  }

  const reviewedButton = event.target.closest("button[data-toggle-reviewed]");
  if (reviewedButton) {
    patchLicitacionWork(reviewedButton.dataset.toggleReviewed, {
      revisada: reviewedButton.dataset.reviewed === "1",
    });
    return;
  }

  const internalStateButton = event.target.closest("button[data-set-internal-state]");
  if (internalStateButton) {
    patchLicitacionWork(internalStateButton.dataset.setInternalState, {
      estado_interno: internalStateButton.dataset.internalState,
    });
    return;
  }

  const saveWorkButton = event.target.closest("button[data-save-licitacion-work]");
  if (saveWorkButton) {
    const id = saveWorkButton.dataset.saveLicitacionWork;
    const notes = board.querySelector(`[data-notes-for="${id}"]`);
    const state = board.querySelector(`[data-internal-state-for="${id}"]`);
    patchLicitacionWork(id, {
      notas_internas: notes ? notes.value : "",
      estado_interno: state ? state.value : "Nueva",
    });
    return;
  }

  const editActuacionButton = event.target.closest("button[data-edit-actuacion]");
  if (editActuacionButton) {
    editActuacion(editActuacionButton.dataset.editActuacion);
    return;
  }

  const commentActuacionButton = event.target.closest("button[data-comment-actuacion]");
  if (commentActuacionButton) {
    quickActuacionComment(commentActuacionButton.dataset.commentActuacion);
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

actuacionesBoard.addEventListener("click", (event) => {
  const editButton = event.target.closest("button[data-edit-actuacion]");
  if (editButton) {
    editActuacion(editButton.dataset.editActuacion);
    return;
  }
  const commentButton = event.target.closest("button[data-comment-actuacion]");
  if (commentButton) {
    quickActuacionComment(commentButton.dataset.commentActuacion);
    return;
  }
  const duplicateButton = event.target.closest("button[data-duplicate-actuacion]");
  if (duplicateButton) {
    duplicateActuacion(duplicateButton.dataset.duplicateActuacion);
    return;
  }
  const closeButton = event.target.closest("button[data-close-actuacion]");
  if (closeButton) {
    setActuacionClosedState(closeButton.dataset.closeActuacion, "cerrar");
    return;
  }
  const cancelButton = event.target.closest("button[data-cancel-actuacion]");
  if (cancelButton) {
    setActuacionClosedState(cancelButton.dataset.cancelActuacion, "cancelar");
  }
});

calendarBoard.addEventListener("click", (event) => {
  const day = event.target.closest("[data-calendar-date]");
  if (!day) return;
  appState.calendarSelectedDate = day.dataset.calendarDate;
  const parsed = parseDate(day.dataset.calendarDate);
  if (parsed) appState.calendarDate = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
  loadCalendarItems();
});

calendarRadar.addEventListener("click", (event) => {
  const openButton = event.target.closest("button[data-agenda-open]");
  if (openButton) {
    openAgendaOrigin(openButton.dataset.agendaOpen);
    return;
  }
  const commentButton = event.target.closest("button[data-agenda-comment]");
  if (commentButton) {
    quickActuacionComment(commentButton.dataset.agendaComment);
    return;
  }
  const duplicateButton = event.target.closest("button[data-agenda-duplicate]");
  if (duplicateButton) {
    duplicateActuacion(duplicateButton.dataset.agendaDuplicate);
    return;
  }
  const newActuacionButton = event.target.closest("button[data-new-actuacion-id]");
  if (newActuacionButton) {
    openActuacionDialog(newActuacionButton.dataset.newActuacionId);
    return;
  }
  const closeButton = event.target.closest("button[data-agenda-close]");
  if (closeButton) {
    setAgendaEventoEstado(closeButton.dataset.agendaClose, "cerrar");
    return;
  }
  const cancelButton = event.target.closest("button[data-agenda-cancel]");
  if (cancelButton) {
    setAgendaEventoEstado(cancelButton.dataset.agendaCancel, "cancelar");
    return;
  }
  if (!["week", "month"].includes(appState.agendaView)) return;
  const day = event.target.closest("[data-calendar-date]");
  if (!day) return;
  const parsed = parseDate(day.dataset.calendarDate);
  if (parsed) appState.calendarDate = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
  appState.calendarSelectedDate = day.dataset.calendarDate;
  loadCalendarItems();
});

calendarRadar.addEventListener("change", (event) => {
  const stateSelect = event.target.closest("select[data-pending-state]");
  if (!stateSelect) return;
  updatePendingTaskState(stateSelect.dataset.pendingState, stateSelect.value);
});

calendarDayPanel.addEventListener("click", (event) => {
  const openButton = event.target.closest("button[data-agenda-open]");
  if (openButton) {
    openAgendaOrigin(openButton.dataset.agendaOpen);
    return;
  }
  const commentButton = event.target.closest("button[data-agenda-comment]");
  if (commentButton) {
    quickActuacionComment(commentButton.dataset.agendaComment);
    return;
  }
  const duplicateButton = event.target.closest("button[data-agenda-duplicate]");
  if (duplicateButton) {
    duplicateActuacion(duplicateButton.dataset.agendaDuplicate);
    return;
  }
  const newActuacionButton = event.target.closest("button[data-new-actuacion-id]");
  if (newActuacionButton) {
    openActuacionDialog(newActuacionButton.dataset.newActuacionId);
    return;
  }
  const closeButton = event.target.closest("button[data-agenda-close]");
  if (closeButton) {
    setAgendaEventoEstado(closeButton.dataset.agendaClose, "cerrar");
    return;
  }
  const cancelButton = event.target.closest("button[data-agenda-cancel]");
  if (cancelButton) {
    setAgendaEventoEstado(cancelButton.dataset.agendaCancel, "cancelar");
  }
});

calendarDayPanel.addEventListener("change", (event) => {
  const stateSelect = event.target.closest("select[data-pending-state]");
  if (!stateSelect) return;
  updatePendingTaskState(stateSelect.dataset.pendingState, stateSelect.value);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!isAdmin()) return;

  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  delete data.id;

  const response = await fetch(id ? `/api/licitaciones/${id}` : "/api/licitaciones", {
    method: id ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
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
      headers: csrfHeaders(),
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

loadMe().then(showInitialView);
