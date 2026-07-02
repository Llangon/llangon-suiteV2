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
  licitacionesYear: String(new Date().getFullYear()),
  licitacionesMonth: String(new Date().getMonth() + 1),
  licitacionesDateFilters: { years: [], month_counts: {} },
  lastSection: "days",
  config: null,
  storage: null,
  expandedCards: new Set(),
  cardDetails: {},
  documentTrees: {},
  preparedNoticePreview: null,
  preparedNoticeSending: false,
  downloadFolder: null,
  downloadFolderSubmitting: false,
  aiFileSelection: null,
  aiSummaryEmail: null,
  aiPolling: new Map(),
  aiQueue: null,
  aiQueueTimer: null,
  aiQueueOpen: false,
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
const licitacionesDateFilters = document.getElementById("licitaciones-date-filters");
const licitacionesYearFilters = document.getElementById("licitaciones-year-filters");
const licitacionesMonthFilters = document.getElementById("licitaciones-month-filters");
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
const monitorSchedulerStatus = document.getElementById("monitor-scheduler-status");
const monitorSendAgendaDailyButton = document.getElementById("monitor-send-agenda-daily");
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
const preparedNoticeDialog = document.getElementById("prepared-notice-dialog");
const preparedNoticeTo = document.getElementById("prepared-notice-to");
const preparedNoticeSubject = document.getElementById("prepared-notice-subject");
const preparedNoticeBody = document.getElementById("prepared-notice-body");
const preparedNoticeStatus = document.getElementById("prepared-notice-status");
const sendPreparedNoticeButton = document.getElementById("send-prepared-notice");
const copyPreparedNoticeButton = document.getElementById("copy-prepared-notice");
const downloadFolderDialog = document.getElementById("download-folder-dialog");
const downloadFolderName = document.getElementById("download-folder-name");
const downloadFolderStatus = document.getElementById("download-folder-status");
const confirmDownloadFolderButton = document.getElementById("confirm-download-folder");
const aiFileDialog = document.getElementById("ai-file-dialog");
const aiFileList = document.getElementById("ai-file-list");
const aiFileStatus = document.getElementById("ai-file-status");
const aiFileSelectionCount = document.getElementById("ai-file-selection-count");
const confirmAiFileSelectionButton = document.getElementById("confirm-ai-file-selection");
const aiNotifyOnCompletion = document.getElementById("ai-notify-on-completion");
const aiNotificationEmails = document.getElementById("ai-notification-emails");
const aiSummaryEmailDialog = document.getElementById("ai-summary-email-dialog");
const aiSummaryEmailTo = document.getElementById("ai-summary-email-to");
const aiSummaryEmailSubject = document.getElementById("ai-summary-email-subject");
const aiSummaryEmailPreview = document.getElementById("ai-summary-email-preview");
const aiSummaryEmailStatus = document.getElementById("ai-summary-email-status");
const sendAiSummaryEmailButton = document.getElementById("send-ai-summary-email");
const aiQueueButton = document.getElementById("ai-queue-button");
const aiQueueBadge = document.getElementById("ai-queue-badge");
const aiQueueDialog = document.getElementById("ai-queue-dialog");
const aiQueueContent = document.getElementById("ai-queue-content");
const aiQueueStatus = document.getElementById("ai-queue-status");
const refreshAiQueueButton = document.getElementById("refresh-ai-queue");
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
const mobileMenuButton = document.getElementById("mobile-menu-button");
const mobileMenuClose = document.getElementById("mobile-menu-close");
const sidebarOverlay = document.getElementById("sidebar-overlay");
const mobileLogoutButton = document.getElementById("mobile-logout-button");

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
  "Preparar": "Preparar",
  "Preparada": "Preparada",
  "Oferta enviada": "Oferta enviada",
};

const monitorTaskTypeLabels = {
  licitaciones: "Licitaciones",
  agenda_pendientes_diaria: "Pendientes de Agenda",
  agenda_diaria: "Agenda diaria (legado)",
  agenda_semanal: "Agenda semanal (legado)",
  aviso_vencimiento_7d: "Aviso 7 días (legado)",
  aviso_vencimiento_3d: "Aviso 3 días (legado)",
  aviso_vencimiento_1d: "Aviso mañana (legado)",
  aviso_vencimiento_hoy: "Aviso hoy (legado)",
  avisos_vencimientos: "Avisos vencimientos (legado)",
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
const gestionadasEstados = ["Oferta enviada", "Preparada", "Descargar para ver", "Preparar ficha", "Preparar"];
const monthFilterLabels = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];
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

function renderAiSummaryBadge(item) {
  if (!item?.has_ai_summary) return "";
  return `<span class="ai-summary-badge" title="Resumen IA disponible">✨ Resumen IA</span>`;
}

function commentEntityTypeForAgenda(item) {
  if (item?.source_type === "licitacion") return "licitacion";
  if (item?.source_type === "actuacion") return "actuacion";
  return "agenda_evento";
}

function commentCountText(count) {
  const total = Number(count || 0);
  if (total === 1) return "💬 1 comentario";
  return `💬 ${total} comentarios`;
}

function renderCommentLatest(summary) {
  const latest = summary?.latest;
  if (!latest?.body) return `<span class="comments-latest empty">Sin comentarios todavía.</span>`;
  const author = latest.author_name || latest.author_user_id || "Usuario";
  return `
    <span class="comments-latest">
      <strong>${escapeHtml(author)}:</strong>
      ${escapeHtml(latest.body)}
    </span>
  `;
}

function renderCommentsWidget(entityType, entityId, summary = {}, options = {}) {
  if (!entityType || !entityId) return "";
  const full = Boolean(options.full);
  const threadHidden = full ? "" : "hidden";
  const toggleText = full ? "Actualizar comentarios" : "Ver comentarios";
  return `
    <section class="comments-widget ${full ? "comments-widget-full" : ""}"
      data-comments-entity-type="${escapeHtml(entityType)}"
      data-comments-entity-id="${escapeHtml(entityId)}"
      data-comments-loaded="0">
      <div class="comments-compact">
        <button type="button" class="comments-toggle" data-comments-toggle>
          ${escapeHtml(commentCountText(summary?.count || 0))}
        </button>
        ${renderCommentLatest(summary)}
        <button type="button" class="ghost comments-reply" data-comments-toggle>${escapeHtml(toggleText)}</button>
      </div>
      <div class="comments-thread" data-comments-thread ${threadHidden}>
        <div class="comments-list" data-comments-list>
          <div class="empty compact">Cargando comentarios...</div>
        </div>
        <form class="comments-form" data-comments-form>
          <textarea name="body" rows="2" maxlength="5000" placeholder="Escribe un comentario interno..."></textarea>
          <button type="submit">Enviar comentario</button>
        </form>
      </div>
    </section>
  `;
}

function renderCommentItem(comment) {
  const edited = comment.is_edited ? " · editado" : "";
  const pinned = comment.is_pinned ? "📌 " : "";
  const actions = [];
  if (comment.can_edit) actions.push(`<button type="button" class="ghost" data-comment-edit="${escapeHtml(comment.id)}">Editar</button>`);
  if (comment.can_delete) actions.push(`<button type="button" class="ghost danger-text" data-comment-delete="${escapeHtml(comment.id)}">Eliminar</button>`);
  if (comment.can_pin) {
    actions.push(`<button type="button" class="ghost" data-comment-pin="${escapeHtml(comment.id)}" data-comment-pinned="${comment.is_pinned ? "1" : "0"}">${comment.is_pinned ? "Desfijar" : "Fijar"}</button>`);
  }
  return `
    <article class="comment-item ${comment.is_pinned ? "pinned" : ""}" data-comment-id="${escapeHtml(comment.id)}">
      <div class="comment-meta">
        <strong>${pinned}${escapeHtml(comment.author_name || comment.author_user_id || "Usuario")}</strong>
        <span>${escapeHtml(formatDateTime(comment.created_at) || comment.created_at || "")}${escapeHtml(edited)}</span>
      </div>
      <p class="comment-body">${escapeHtml(comment.body || "")}</p>
      ${actions.length ? `<div class="comment-actions">${actions.join("")}</div>` : ""}
    </article>
  `;
}

function renderCommentsList(items = []) {
  if (!items.length) return `<div class="empty compact">Sin comentarios todavía.</div>`;
  return items.map(renderCommentItem).join("");
}

async function loadCommentsWidget(widget) {
  if (!widget) return;
  const entityType = widget.dataset.commentsEntityType;
  const entityId = widget.dataset.commentsEntityId;
  const list = widget.querySelector("[data-comments-list]");
  if (!entityType || !entityId || !list) return;
  list.innerHTML = `<div class="empty compact">Cargando comentarios...</div>`;
  const params = new URLSearchParams({ entity_type: entityType, entity_id: entityId });
  const response = await fetch(`/api/comments?${params.toString()}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    list.innerHTML = `<div class="empty compact">${escapeHtml(data.error || "No se pudieron cargar los comentarios.")}</div>`;
    return;
  }
  list.innerHTML = renderCommentsList(data.items || []);
  widget.dataset.commentsLoaded = "1";
  const summary = data.summary || {};
  const compact = widget.querySelector(".comments-compact");
  if (compact) {
    compact.querySelector(".comments-toggle").innerHTML = escapeHtml(commentCountText(summary.count || 0));
    const latest = compact.querySelector(".comments-latest");
    if (latest) {
      const template = document.createElement("template");
      template.innerHTML = renderCommentLatest(summary).trim();
      latest.replaceWith(template.content.firstElementChild);
    }
  }
}

async function refreshRelatedCommentWidgets(widget) {
  const entityType = widget?.dataset.commentsEntityType;
  const entityId = widget?.dataset.commentsEntityId;
  if (!entityType || !entityId) return;
  const selector = `.comments-widget[data-comments-entity-type="${CSS.escape(entityType)}"][data-comments-entity-id="${CSS.escape(entityId)}"]`;
  for (const item of document.querySelectorAll(selector)) {
    if (!item.querySelector("[data-comments-thread]")?.hidden || item.classList.contains("comments-widget-full")) {
      await loadCommentsWidget(item);
    } else {
      item.dataset.commentsLoaded = "0";
    }
  }
}

async function submitCommentForm(form) {
  const widget = form.closest(".comments-widget");
  const textarea = form.elements.body;
  const body = textarea.value.trim();
  if (!body) return;
  const response = await fetch("/api/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({
      entity_type: widget.dataset.commentsEntityType,
      entity_id: widget.dataset.commentsEntityId,
      body,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(data.error || "No se pudo guardar el comentario.");
    return;
  }
  textarea.value = "";
  await refreshRelatedCommentWidgets(widget);
}

async function editComment(button) {
  const widget = button.closest(".comments-widget");
  const item = button.closest(".comment-item");
  const current = item?.querySelector(".comment-body")?.textContent || "";
  const body = window.prompt("Editar comentario:", current);
  if (body === null) return;
  const trimmed = body.trim();
  if (!trimmed) {
    alert("El comentario no puede estar vacío.");
    return;
  }
  const response = await fetch(`/api/comments/${button.dataset.commentEdit}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ body: trimmed }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(data.error || "No se pudo editar el comentario.");
    return;
  }
  await refreshRelatedCommentWidgets(widget);
}

async function deleteComment(button) {
  if (!window.confirm("¿Eliminar este comentario?")) return;
  const widget = button.closest(".comments-widget");
  const response = await fetch(`/api/comments/${button.dataset.commentDelete}`, {
    method: "DELETE",
    headers: csrfHeaders(),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(data.error || "No se pudo eliminar el comentario.");
    return;
  }
  await refreshRelatedCommentWidgets(widget);
}

async function pinComment(button) {
  const widget = button.closest(".comments-widget");
  const pinned = button.dataset.commentPinned === "1";
  const response = await fetch(`/api/comments/${button.dataset.commentPin}/${pinned ? "unpin" : "pin"}`, {
    method: "POST",
    headers: csrfHeaders(),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    alert(data.error || "No se pudo actualizar el comentario.");
    return;
  }
  await refreshRelatedCommentWidgets(widget);
}

function handleCommentsClick(event) {
  const toggle = event.target.closest("[data-comments-toggle]");
  if (toggle) {
    const widget = toggle.closest(".comments-widget");
    const thread = widget?.querySelector("[data-comments-thread]");
    if (!thread) return false;
    thread.hidden = !thread.hidden;
    if (!thread.hidden && widget.dataset.commentsLoaded !== "1") loadCommentsWidget(widget);
    return true;
  }
  const editButton = event.target.closest("[data-comment-edit]");
  if (editButton) {
    editComment(editButton);
    return true;
  }
  const deleteButton = event.target.closest("[data-comment-delete]");
  if (deleteButton) {
    deleteComment(deleteButton);
    return true;
  }
  const pinButton = event.target.closest("[data-comment-pin]");
  if (pinButton) {
    pinComment(pinButton);
    return true;
  }
  return false;
}

function handleCommentsSubmit(event) {
  const form = event.target.closest("[data-comments-form]");
  if (!form) return false;
  event.preventDefault();
  submitCommentForm(form);
  return true;
}

function hydrateFullCommentWidgets(root = document) {
  root.querySelectorAll(".comments-widget-full").forEach((widget) => {
    if (widget.dataset.commentsLoaded !== "1") loadCommentsWidget(widget);
  });
}

function defaultNuriaReviewEmail() {
  const settings = appState.config?.settings || {};
  return (
    settings.nuria_review_email_to ||
    settings.prepared_notice_email_to ||
    "info3@llangon.com"
  ).trim();
}

function confirmNuriaReviewEmail() {
  const email = window.prompt(
    "Confirma el correo de destino para avisar a Nuria:",
    defaultNuriaReviewEmail(),
  );
  if (email === null) return null;
  const trimmedEmail = email.trim();
  if (!trimmedEmail) {
    alert("Debes indicar un correo de destino.");
    return null;
  }
  return trimmedEmail;
}

async function logout() {
  if (logoutButton) logoutButton.disabled = true;
  if (mobileLogoutButton) mobileLogoutButton.disabled = true;
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
    if (mobileLogoutButton) mobileLogoutButton.disabled = false;
  }
}

function setActiveNav(section) {
  document.querySelectorAll("[data-nav-section]").forEach((button) => {
    button.classList.toggle("active", button.dataset.navSection === section);
  });
  document.body.dataset.activeSection = section || "";
}

function setPageHeader(title, kicker = "Panel privado") {
  if (pageTitle) pageTitle.textContent = title;
  if (pageKicker) pageKicker.textContent = kicker;
}

function openSidebar() {
  document.body.classList.add("sidebar-open");
  if (sidebarOverlay) sidebarOverlay.hidden = false;
  if (mobileMenuButton) mobileMenuButton.setAttribute("aria-expanded", "true");
}

function closeSidebar() {
  document.body.classList.remove("sidebar-open");
  if (sidebarOverlay) sidebarOverlay.hidden = true;
  if (mobileMenuButton) mobileMenuButton.setAttribute("aria-expanded", "false");
}

function toggleSidebar() {
  if (document.body.classList.contains("sidebar-open")) {
    closeSidebar();
  } else {
    openSidebar();
  }
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
  if (!diaId) dateOrder.value = appState.licitacionesView === "all" ? "desc" : "asc";
  currentDayTitle.textContent = title;
  appState.lastSection = "licitaciones";
  setActiveNav("licitaciones");
  setPageHeader(diaId ? "Revisión de día" : "Centro de licitaciones", diaId ? title : "Bandeja");
  daysSection.hidden = true;
  licitacionesSection.hidden = false;
  licitacionesSection.classList.toggle("has-day-context", Boolean(diaId));
  calendarSection.hidden = true;
  actuacionesSection.hidden = true;
  notificationsSection.hidden = true;
  newsAdminSection.hidden = true;
  monitorSection.hidden = true;
  configSection.hidden = true;
  renderLicitacionesTabs();
  renderLicitacionesDateFilters();
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
  return loadCalendarItems();
}

function agendaDeepLinkToken() {
  const params = new URLSearchParams(window.location.search);
  return params.get("agenda_source") || "";
}

function clearAgendaDeepLinkToken() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("agenda_source")) return;
  params.delete("agenda_source");
  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash || ""}`;
  window.history.replaceState({}, "", nextUrl);
}

async function openAgendaDeepLink(token) {
  if (!isAdmin() || !token) return false;
  appState.agendaView = "pending";
  appState.calendarSelectedDate = dateKey(new Date());
  await showCalendarView();
  openAgendaOrigin(token);
  clearAgendaDeepLinkToken();
  return true;
}

async function showInitialView() {
  const token = agendaDeepLinkToken();
  if (token && await openAgendaDeepLink(token)) return;
  if (isAdmin()) {
    appState.agendaView = "pending";
    appState.calendarSelectedDate = dateKey(new Date());
    await showCalendarView();
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
        ${renderCommentsWidget("actuacion", item.id, item.comments_summary)}
        <div class="card-actions">
          <button data-edit-actuacion="${escapeHtml(item.id)}">Editar</button>
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

function renderActuacionHistory(entries = [], item = null) {
  if (!actuacionForm.elements.id.value) {
    actuacionHistoryPanel.hidden = true;
    actuacionHistory.innerHTML = "";
    return;
  }
  actuacionHistoryPanel.hidden = false;
  const historyHtml = entries.length ? entries.map((entry) => `
    <article class="history-item">
      <strong>${escapeHtml(entry.event_type || "evento")}</strong>
      <small>${escapeHtml(entry.created_at || "")}${entry.user_id ? ` · ${escapeHtml(entry.user_id)}` : ""}</small>
      ${entry.comentario ? `<p>${escapeHtml(entry.comentario)}</p>` : ""}
      ${entry.old_value || entry.new_value ? `<small>${escapeHtml(entry.old_value || "vacío")} -> ${escapeHtml(entry.new_value || "vacío")}</small>` : ""}
    </article>
  `).join("") : `<div class="empty">Sin movimientos registrados.</div>`;
  const commentsHtml = item?.id ? renderCommentsWidget("actuacion", item.id, item.comments_summary, { full: true }) : "";
  actuacionHistory.innerHTML = `${historyHtml}${commentsHtml}`;
  hydrateFullCommentWidgets(actuacionHistoryPanel);
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
  renderActuacionHistory(item.historial || [], item);
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
  if (!appState.currentDiaId && appState.licitacionesView === "managed") params.set("gestionadas", "1");
  if (!appState.currentDiaId && appState.licitacionesYear && appState.licitacionesYear !== "Todos") {
    params.set("ejercicio", appState.licitacionesYear);
  }
  if (!appState.currentDiaId && appState.licitacionesMonth && appState.licitacionesMonth !== "Todos") {
    params.set("mes", appState.licitacionesMonth);
  }
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
  appState.licitacionesDateFilters = data.date_filters || { years: [], month_counts: {} };
  appState.currentDayPendingReview = data.day_pending_review;
  appState.currentDayPendingAdmin = data.day_pending_admin;
  appState.currentDaySentNuriaAt = data.day_sent_nuria_at || "";
  appState.currentDayNuriaDirtyAt = data.day_nuria_dirty_at || "";
  appState.currentDayNuriaPendingUpdate = Boolean(data.day_nuria_pending_update);
  appState.currentDayReviewedAt = data.day_reviewed_at || "";
  appState.currentDayNuriaTotal = data.day_nuria_total;
  renderLicitacionesTabs();
  renderLicitacionesDateFilters();
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

function renderLicitacionesDateFilters() {
  const showFilters = !appState.currentDiaId;
  licitacionesDateFilters.hidden = !showFilters;
  if (!showFilters) return;

  const filterData = appState.licitacionesDateFilters || {};
  const years = (filterData.years || []).map((year) => String(year));
  const selectedYear = appState.licitacionesYear || "Todos";
  const selectedMonth = appState.licitacionesMonth || "Todos";
  const yearAllCount = Number(filterData.year_all_count || 0);
  const monthAllCount = Number(filterData.month_all_count || 0);
  const yearValues = ["Todos", ...years];
  if (selectedYear !== "Todos" && !yearValues.includes(selectedYear)) {
    yearValues.splice(1, 0, selectedYear);
  }

  licitacionesYearFilters.innerHTML = yearValues.map((year) => `
    <button type="button"
      class="filter-chip ${year === selectedYear ? "active" : ""}"
      data-licitaciones-year="${escapeHtml(year)}">
      ${escapeHtml(year === "Todos" ? `Todos (${yearAllCount})` : year)}
    </button>
  `).join("");

  const monthCounts = filterData.month_counts || {};
  const monthButtons = [
    `<button type="button" class="filter-chip ${selectedMonth === "Todos" ? "active" : ""}" data-licitaciones-month="Todos">Todos (${monthAllCount})</button>`,
  ];
  monthFilterLabels.forEach((label, index) => {
    const monthValue = String(index + 1);
    const paddedMonth = monthValue.padStart(2, "0");
    const count = Number(monthCounts[monthValue] ?? monthCounts[paddedMonth] ?? 0);
    monthButtons.push(`
      <button type="button"
        class="filter-chip ${selectedMonth === monthValue ? "active" : ""}"
        data-licitaciones-month="${monthValue}">
        ${escapeHtml(label)} (${count})
      </button>
    `);
  });
  licitacionesMonthFilters.innerHTML = monthButtons.join("");
}

function visibleStateOrder() {
  if (!appState.currentDiaId && appState.licitacionesView === "live") {
    return calendarioEstados;
  }
  if (!appState.currentDiaId && appState.licitacionesView === "managed") {
    return gestionadasEstados;
  }
  if (appState.currentDiaId && isAdmin()) return ["Importada", ...adminReviewEstados];
  if (appState.currentDiaId) return nuriaDefaultReviewEstados;
  return estadoOrden;
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

function pendingLicitacionCardItem(item) {
  return {
    ...item,
    id: item.source_id,
    expediente: item.expediente || item.title || `Licitación ${item.source_id}`,
    organismo: item.organismo || item.description || "",
    objeto: item.objeto || item.subtitle || "",
    estado: item.state_value || item.status || item.state || "",
    fecha_limite: item.fecha_limite || item.date || "",
    hora_limite: item.hora_limite || agendaEventTime(item) || "",
  };
}

function renderPendingTaskCard(item, colorClass) {
  const token = `${item.source_type}:${item.source_id}`;
  const linked = agendaLinkedText(item);
  const dueText = [
    item.date ? formatDate(item.date) : "Sin fecha",
    agendaEventTime(item),
  ].filter(Boolean).join(" ");
  const sideActions = [
    `<button type="button" data-agenda-open="${escapeHtml(token)}">Abrir</button>`,
  ];
  if (item.source_type === "actuacion") {
    sideActions.push(`<button type="button" data-agenda-duplicate="${escapeHtml(item.source_id)}">Duplicar actuación</button>`);
  }
  const commentEntityType = commentEntityTypeForAgenda(item);
  return `
    <article class="card compact-card agenda-card pending-task-card ${colorClass}" data-calendar-date="${escapeHtml(item.date || "sin-fecha")}">
      <div class="card-layout">
        <div class="card-content">
          <div class="card-head">
            <div class="card-title-block">
              <p class="eyebrow">${escapeHtml(agendaTypeLabel(item))}</p>
              <h2>${escapeHtml(item.title || "Sin título")}</h2>
              <p class="card-organismo">${escapeHtml(linked ? `Licitación vinculada: ${linked}` : item.description || "")}</p>
              <p class="object">${escapeHtml(item.subtitle || item.description || "Sin descripción")}</p>
            </div>
            <div class="card-flags">
              <span class="badge">${escapeHtml(agendaStatusLabel(item))}</span>
              <span class="due-chip ${colorClass}">${escapeHtml(item.is_overdue ? `Vencido · ${dueText}` : dueText)}</span>
            </div>
          </div>

          <div class="details">
            <div class="detail"><span>Tipo</span>${escapeHtml(agendaTypeLabel(item))}</div>
            <div class="detail"><span>Estado</span>${escapeHtml(agendaStatusLabel(item))}</div>
            <div class="detail"><span>Fecha límite</span>${escapeHtml(dueText)}</div>
          </div>
          ${renderCommentsWidget(commentEntityType, item.source_id, item.comments_summary)}
        </div>

        <div class="card-side-actions">
          ${sideActions.join("")}
          ${renderPendingStateControl(item)}
          <span class="card-side-id">ID ${escapeHtml(item.source_id)}</span>
        </div>
      </div>
    </article>
  `;
}

function renderAgendaCompactCard(item) {
  const colorClass = agendaEventClass(item);
  if (isPendingAgendaView() && item.source_type === "licitacion") {
    return renderCard(pendingLicitacionCardItem(item), {
      extraClass: `agenda-card pending-licitacion-card ${colorClass}`,
      sideActionsExtra: renderPendingStateControl(item),
    });
  }
  if (isPendingAgendaView()) {
    return renderPendingTaskCard(item, colorClass);
  }
  const linked = agendaLinkedText(item);
  return `
    <article class="radar-card agenda-card ${colorClass}" data-calendar-date="${escapeHtml(item.date || "sin-fecha")}">
      <span><b class="agenda-event-dot ${colorClass}"></b>${escapeHtml(agendaTypeLabel(item))}${item.is_overdue ? " · Vencido" : ""}</span>
      <strong>${escapeHtml(item.title || "Sin título")}</strong>
      <small>Estado: ${escapeHtml(agendaStatusLabel(item))}</small>
      <small>${escapeHtml(item.date ? formatDate(item.date) : "Sin fecha")}${agendaEventTime(item) ? ` · ${escapeHtml(agendaEventTime(item))}` : ""}</small>
      <small>${escapeHtml(item.subtitle || "")}</small>
      ${linked ? `<small>Licitación vinculada: ${escapeHtml(linked)}</small>` : ""}
      ${renderAiSummaryBadge(item)}
      ${renderCommentsWidget(commentEntityTypeForAgenda(item), item.source_id, item.comments_summary)}
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
  settingsForm.elements.prepared_notice_email_to.value = settings.prepared_notice_email_to || "info3@llangon.com";
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
  const dropboxBase = storage.dropbox_base || {};
  const dropboxBaseWarnings = [];
  if (dropboxBase.error && dropboxBase.configured) {
    dropboxBaseWarnings.push(dropboxBase.error);
  }
  if (dropboxBase.source === "legacy") {
    dropboxBaseWarnings.push("Usando fallback / legado. Configura LLANGON_DROPBOX_BASE_PATH para usar Dropbox real.");
  }
  const apiStatus = storage.dropbox_api_status === "experimental_enabled"
    ? "experimental activo"
    : "experimental desactivado";
  storageStatusBoard.innerHTML = `
    <div class="storage-status-row"><span>Modo actual</span><strong>${escapeHtml(storageValue(storage.local_flow_label || storage.current_mode_label || storage.backend))}</strong></div>
    <div class="storage-status-row"><span>Carpeta local</span><strong>${escapeHtml(storageValue(storage.local_download_root))}</strong></div>
    <div class="storage-status-row"><span>Configuración local</span><strong>${escapeHtml(storageValue(dropboxBase.label || dropboxBase.env_var))}</strong></div>
    <div class="storage-status-row"><span>Dropbox Desktop</span><strong>${escapeHtml(storage.dropbox_desktop_detected ? "detectado / activo" : "no detectado")}</strong></div>
    <div class="storage-status-row"><span>Escaneo marcadores</span><strong>${escapeHtml(`${storage.monitor_year_min || 2000}-${storage.monitor_year_max || 2300}`)}</strong></div>
    <div class="storage-status-row"><span>Dropbox API</span><strong>${escapeHtml(apiStatus)}</strong></div>
    <div class="storage-status-row"><span>Raíz API remota</span><strong>${escapeHtml(storageValue(storage.root))}</strong></div>
    ${dropboxBaseWarnings.length ? `<div class="notification-warning">${dropboxBaseWarnings.map(escapeHtml).join("<br>")}</div>` : ""}
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
    prepared_notice_email_to: settingsForm.elements.prepared_notice_email_to.value.trim(),
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

async function loadMonitorSchedulerStatus() {
  if (!isAdmin() || !monitorSchedulerStatus) return;
  try {
    const response = await fetch("/api/monitor/scheduler/status");
    const data = await response.json().catch(() => ({}));
    const scheduler = data.scheduler || {};
    if (!response.ok) {
      monitorSchedulerStatus.textContent = "Scheduler: estado no disponible";
      return;
    }
    const state = scheduler.enabled ? "activo" : "desactivado";
    const recipients = Array.isArray(scheduler.agenda_pending_recipients) && scheduler.agenda_pending_recipients.length
      ? scheduler.agenda_pending_recipients.join(", ")
      : "sin destinatarios";
    const lastCheck = scheduler.last_check_at ? ` Última comprobación: ${formatDateTime(scheduler.last_check_at) || scheduler.last_check_at}.` : " Sin heartbeat reciente.";
    const lastRun = scheduler.last_automatic_run?.started_at
      ? ` Última ejecución automática: ${formatDateTime(scheduler.last_automatic_run.started_at) || scheduler.last_automatic_run.started_at} (${monitorStatusLabel(scheduler.last_automatic_run.status)}).`
      : " Sin ejecución automática registrada.";
    const next = scheduler.next?.task_type ? ` Próxima ejecución: ${monitorTaskTypeLabel(scheduler.next.task_type)} ${formatDateTime(scheduler.next.run_at) || scheduler.next.run_at}.` : " Sin próxima ejecución activa.";
    const licitaciones = scheduler.monitor_licitaciones_schedule_enabled ? " Monitor licitaciones: programado." : " Monitor licitaciones: desactivado.";
    const error = scheduler.last_error ? ` Error: ${scheduler.last_error}` : "";
    monitorSchedulerStatus.textContent = `Scheduler: ${state}. Pendientes: ${recipients}.${lastCheck}${lastRun}${next}${licitaciones}${error}`;
  } catch (_error) {
    monitorSchedulerStatus.textContent = "Scheduler: estado no disponible";
  }
}

async function loadMonitorRuns() {
  if (!isAdmin() || !monitorRunsBoard) return;
  await loadMonitorSchedulerStatus();
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
    monitorSendAgendaDailyButton,
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
monitorSendAgendaDailyButton?.addEventListener("click", () => sendMonitorAgendaTask(
  monitorSendAgendaDailyButton,
  "agenda_pendientes_diaria",
  "Preparando y enviando Pendientes de Agenda...",
  "No se pudo enviar el correo diario de Pendientes.",
));
monitorTaskTypeFilter?.addEventListener("change", loadMonitorRuns);
monitorRunsBoard?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-monitor-run]");
  if (button) openMonitorRun(button.dataset.monitorRun);
});

document.addEventListener("click", (event) => {
  if (handleCommentsClick(event)) {
    event.preventDefault();
    event.stopPropagation();
  }
}, true);

document.addEventListener("submit", (event) => {
  if (handleCommentsSubmit(event)) {
    event.stopPropagation();
  }
}, true);

function renderCard(item, options = {}) {
  const fechaLimite = [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ");
  const remainingDays = daysUntil(item.fecha_limite, item.hora_limite);
  const enlacePerfil = normalizeUrl(item.enlace_perfil);
  const enlaceInfonalia = normalizeUrl(item.enlace_infonalia);
  const links = [
    enlacePerfil ? `<a href="${escapeHtml(enlacePerfil)}" target="_blank" rel="noreferrer">Perfil del contratante</a>` : "",
    enlaceInfonalia ? `<a href="${escapeHtml(enlaceInfonalia)}" target="_blank" rel="noreferrer">Anuncio Infonalia</a>` : "",
  ].filter(Boolean).join("");
  const folderPath = folderDisplayPath(item);
  const folderText = folderPath ? compactFolderDisplayPath(folderPath) : "Carpeta no localizada";
  const folderClass = folderPath ? "" : " muted";
  const isReview = Boolean(appState.currentDiaId);
  const stateActions = isAdmin() ? adminReviewEstados : nuriaEstados;
  const showStateActions = options.showStateActions ?? isReview;
  const dueText = dueLabel(remainingDays) || "Sin fecha";
  const dueClassName = remainingDays === null ? "" : dueClass(remainingDays);
  const extraClass = options.extraClass ? ` ${options.extraClass}` : "";
  const sideActionsExtra = options.sideActionsExtra || "";
  const showEditButton = options.showEditButton ?? isAdmin();
  const showNewActuacionButton = options.showNewActuacionButton ?? true;

  return `
    <article class="card compact-card${extraClass}">
      <div class="card-layout">
        <div class="card-content">
          <div class="card-head">
            <div class="card-title-block">
              <h2>${escapeHtml(item.expediente)}</h2>
              <p class="card-organismo">${escapeHtml(item.organismo)}</p>
              <p class="object">${escapeHtml(item.objeto || "Sin objeto informado")}</p>
            </div>
            <div class="card-flags">
              ${renderAiSummaryBadge(item)}
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

          ${(links || folderText) ? `<div class="links card-footer-links">${links}<span class="card-folder-path${folderClass}" title="${escapeHtml(folderPath || folderText)}" data-folder-path="${escapeHtml(folderPath || "")}">${escapeHtml(folderText)}</span></div>` : ""}
          ${renderCommentsWidget("licitacion", item.id, item.comments_summary)}

          ${showStateActions ? `<div class="card-actions state-actions">
            ${stateActions.map((estado) => `
              <button class="${item.estado === estado ? "active-state" : ""}" data-id="${escapeHtml(item.id)}" data-estado="${escapeHtml(estado)}">${escapeHtml(estadoActionLabel(estado))}</button>
            `).join("")}
          </div>` : ""}
        </div>

        <div class="card-side-actions">
          <button data-open-licitacion-detail="${escapeHtml(item.id)}">Abrir</button>
          ${showEditButton ? `<button data-edit-id="${escapeHtml(item.id)}">Editar</button>` : ""}
          ${showNewActuacionButton ? `<button data-new-actuacion-id="${escapeHtml(item.id)}">Crear nueva actuación</button>` : ""}
          ${sideActionsExtra}
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
  const folder = folderDisplayPath(item);
  const folderLabel = folderStatusLabel(item);
  const profile = normalizeUrl(item.enlace_perfil);
  const infonalia = normalizeUrl(item.enlace_infonalia);
  const fechaLimite = [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ");
  const documentCount = documentCountLabel(item);
  const folderTone = folderStatusTone(item);
  const summaryRows = [
    ["Órgano / organismo", item.organismo],
    ["Lugar / provincia", item.provincia],
    ["Tipo de contrato", item.tipo],
    ["Procedimiento", item.procedimiento],
    ["CPV", item.cpv],
    ["Cliente / representada", item.cliente || item.representada],
  ];

  return `
    <article class="licitacion-detail-workspace">
      <section class="detail-cover">
        <div class="detail-cover-main">
          <p class="eyebrow">Expediente</p>
          <h2>${escapeHtml(item.expediente || "Sin expediente")}</h2>
          <p class="detail-cover-object">${escapeHtml(item.objeto || "Sin objeto informado")}</p>
          <p class="detail-cover-meta">${escapeHtml([item.organismo, item.provincia].filter(Boolean).join(" · "))}</p>
        </div>
        <div class="detail-cover-side">
          ${renderAiSummaryBadge(item)}
          <span class="badge ${badgeClass(item.estado)}">${escapeHtml(estadoLabel(item.estado))}</span>
          ${fechaLimite ? `<div class="detail-kpi"><span>Fecha límite</span><strong>${escapeHtml(fechaLimite)}</strong></div>` : ""}
          ${item.presupuesto ? `<div class="detail-kpi"><span>Presupuesto</span><strong>${escapeHtml(formatMoney(item.presupuesto))}</strong></div>` : ""}
          <span class="folder-status-chip ${escapeHtml(folderTone)}">Carpeta: ${escapeHtml(folderLabel)}</span>
          ${renderDetailHeaderActions(item)}
        </div>
      </section>

      <nav class="detail-tabs no-print" aria-label="Secciones de la ficha">
        <button type="button" class="detail-tab-button active" data-detail-tab="resumen">Resumen</button>
        <button type="button" class="detail-tab-button" data-detail-tab="actuaciones">Actuaciones</button>
        <button type="button" class="detail-tab-button" data-detail-tab="documentos-seguimiento">Documentos y seguimiento</button>
        <button type="button" class="detail-tab-button" data-detail-tab="comentarios">Comentarios</button>
        <button type="button" class="detail-tab-button" data-detail-tab="ai">Análisis IA</button>
      </nav>

      <section class="detail-tab-panel active" data-detail-tab-panel="resumen">
        <div class="detail-panel-head">
          <div>
            <p class="eyebrow">Resumen</p>
            <h3>Información esencial</h3>
          </div>
        </div>
        ${renderCleanDetailGrid(summaryRows)}
        <div class="links no-print">
          ${profile ? `<a href="${escapeHtml(profile)}" target="_blank" rel="noreferrer">Abrir enlace plataforma</a>` : ""}
          ${infonalia ? `<a href="${escapeHtml(infonalia)}" target="_blank" rel="noreferrer">Abrir Infonalia</a>` : ""}
        </div>
      </section>

      <section class="detail-tab-panel" data-detail-tab-panel="actuaciones">
        <div class="detail-panel-head">
          <div>
            <p class="eyebrow">Actuaciones / Agenda</p>
            <h3>${escapeHtml(actuaciones.length ? `${actuaciones.length} actuación(es) vinculada(s)` : "Sin actuaciones vinculadas")}</h3>
          </div>
        </div>
        ${actuaciones.length ? renderLinkedActuaciones(actuaciones) : `<div class="empty">No hay actuaciones ni hitos vinculados a esta licitación.</div>`}
      </section>

      <section class="detail-tab-panel" data-detail-tab-panel="documentos-seguimiento">
        <div class="detail-panel-head">
          <div>
            <p class="eyebrow">Documentos y seguimiento</p>
            <h3>${escapeHtml(documentCount)}</h3>
          </div>
        </div>
        ${renderLicitacionTracking(item)}
        ${renderFolderPanel(item, folder, folderLabel)}
        ${item.descarga_fallida || item.download_error ? `<div class="warning-detail document-warning"><strong>Error de descarga</strong><span>${escapeHtml(item.download_error || "La última descarga falló.")}</span></div>` : ""}
        ${renderDocumentSummary(item)}
        <div class="document-tree-panel" data-document-tree-panel="${escapeHtml(item.id)}">
          <div class="empty">Cargando árbol documental...</div>
        </div>
        ${renderLicitacionHistory(item)}
      </section>

      <section class="detail-tab-panel" data-detail-tab-panel="comentarios">
        <div class="detail-panel-head">
          <div>
            <p class="eyebrow">Comentarios</p>
            <h3>Hilo interno de trabajo</h3>
          </div>
        </div>
        ${renderCommentsWidget("licitacion", item.id, item.comments_summary, { full: true })}
      </section>

      <section class="detail-tab-panel" data-detail-tab-panel="ai">
        <div class="detail-panel-head">
          <div>
            <p class="eyebrow">Análisis IA del expediente</p>
            <h3>Resumen estructurado</h3>
          </div>
        </div>
        <div class="ai-summary-panel" data-ai-summary-panel="${escapeHtml(item.id)}">
          <div class="empty">Cargando estado IA...</div>
        </div>
      </section>

    </article>
  `;
}

function renderDetailHeaderActions(item) {
  return `
    <div class="detail-header-actions no-print">
      ${isAdmin() ? `<button class="download-button primary" data-download-id="${escapeHtml(item.id)}">Descargar documentación</button>` : ""}
      <button data-new-actuacion-id="${escapeHtml(item.id)}">Crear actuación</button>
      ${isAdmin() ? `<button data-edit-id="${escapeHtml(item.id)}">Editar</button>` : ""}
      ${isAdmin() ? `<button data-duplicate-id="${escapeHtml(item.id)}">Duplicar</button>` : ""}
      ${isAdmin() ? `<button class="danger" data-delete-id="${escapeHtml(item.id)}">Borrar</button>` : ""}
    </div>
  `;
}

function renderLicitacionSummary(item) {
  const folder = folderDisplayPath(item);
  const profile = normalizeUrl(item.enlace_perfil);
  const infonalia = normalizeUrl(item.enlace_infonalia);
  const folderUrl = fileUrl(folder);
  const folderLabel = folderStatusLabel(item);
  const rows = [
    ["Objeto", item.objeto],
    ["Organismo", item.organismo],
    ["Plataforma", item.plataforma],
    ["Provincia", item.provincia],
    ["Presupuesto", formatMoney(item.presupuesto)],
    ["Fecha límite", [formatDate(item.fecha_limite), item.hora_limite].filter(Boolean).join(" ")],
    ["Carpeta", folderLabel],
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

function folderDisplayPath(item) {
  const status = item?.folder_status || {};
  return String(status.path || item?.ruta_carpeta || "").trim();
}

function compactFolderDisplayPath(path) {
  const parts = String(path || "")
    .replaceAll("/", "\\")
    .split("\\")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) return "";

  const monthIndex = parts.findIndex((part) => /^\d{2}\s+[A-ZÁÉÍÓÚÜÑ]+$/i.test(part));
  if (monthIndex >= 0) return parts.slice(monthIndex).join("\\");

  const yearIndex = parts.findIndex((part) => /^\d{4}$/.test(part));
  if (yearIndex >= 0 && yearIndex < parts.length - 1) {
    return parts.slice(yearIndex + 1).join("\\");
  }

  return parts.slice(Math.max(0, parts.length - 2)).join("\\");
}

function folderStatusLabel(item) {
  const status = item?.folder_status || {};
  if (status.label) return status.label;
  if (item?.ruta_carpeta) return "Ruta registrada";
  return "Carpeta no configurada";
}

function folderStatusTone(item) {
  const status = item?.folder_status || {};
  const label = folderStatusLabel(item).toLowerCase();
  if (status.inside_dropbox_base === false || label.includes("fuera")) return "warning";
  if (status.exists === true || label.includes("correcta") || label.includes("válida") || label.includes("valida")) return "ok";
  if (!item?.ruta_carpeta || label.includes("no configurada")) return "muted";
  if (status.exists === false || label.includes("no existe")) return "danger";
  return "muted";
}

function renderCleanDetailGrid(rows, options = {}) {
  const visibleRows = rows
    .map(([label, value]) => [label, String(value ?? "").trim()])
    .filter(([, value]) => value);
  if (!visibleRows.length) return `<div class="empty">Sin datos relevantes para mostrar.</div>`;
  const className = options.technical ? "detail-grid clean-detail-grid technical-detail-grid" : "detail-grid clean-detail-grid";
  return `
    <div class="${className}">
      ${visibleRows.map(([label, value]) => `
        <div class="detail ${value.length > 90 ? "full-width" : ""}">
          <span>${escapeHtml(label)}</span>${escapeHtml(value)}
        </div>
      `).join("")}
    </div>
  `;
}

function renderFolderPanel(item, folder, folderLabel) {
  const tone = folderStatusTone(item);
  const hasFolder = Boolean(String(folder || item.ruta_carpeta || "").trim());
  const fullPath = String(folder || item.ruta_carpeta || "").trim();
  const shortPath = fullPath.length > 92 ? `...${fullPath.slice(-89)}` : fullPath;
  const outsideDropbox = tone === "warning";
  return `
    <section class="folder-panel ${escapeHtml(tone)}">
      <div>
        <span class="folder-status-chip ${escapeHtml(tone)}">Carpeta: ${escapeHtml(folderLabel)}</span>
        ${outsideDropbox ? `<p>La carpeta registrada está fuera de la base de Dropbox configurada.</p>` : ""}
        ${!hasFolder ? `<p>No hay carpeta documental registrada todavía.</p>` : `<code title="${escapeHtml(fullPath)}">${escapeHtml(shortPath)}</code>`}
      </div>
      <div class="folder-panel-actions">
        ${hasFolder ? `<button type="button" data-copy-text="${escapeHtml(fullPath)}">Copiar ruta</button>` : ""}
        ${isAdmin() ? `<button type="button" class="download-button" data-download-id="${escapeHtml(item.id)}">${hasFolder ? "Actualizar carpeta" : "Crear carpeta"}</button>` : ""}
      </div>
    </section>
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
  return "";
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size >= 1048576) return `${(size / 1048576).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function safeDocumentOpenUrl(value) {
  const url = normalizeUrl(value);
  return /^https?:\/\//i.test(url) ? url : "";
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
  const categories = [...new Set(docs.map((doc) => String(doc.category || "Otros").trim() || "Otros"))];
  return `
    <div class="document-filter-row no-print" aria-label="Filtrar documentos por tipo">
      <button type="button" class="filter-chip active" data-document-filter="Todos">Todos (${docs.length})</button>
      ${categories.map((category) => {
        const count = docs.filter((doc) => (String(doc.category || "Otros").trim() || "Otros") === category).length;
        return `<button type="button" class="filter-chip" data-document-filter="${escapeHtml(category)}">${escapeHtml(category)} (${count})</button>`;
      }).join("")}
    </div>
    <div class="document-card-list">
      ${docs.map((doc) => {
        const category = String(doc.category || "Otros").trim() || "Otros";
        const openUrl = safeDocumentOpenUrl(doc.open_url);
        const relative = String(doc.relative_path || "").trim();
        return `
          <article class="document-card" data-document-category="${escapeHtml(category)}">
            <div>
              <span class="badge">${escapeHtml(category)}</span>
              <strong>${escapeHtml(doc.name || relative || "Documento")}</strong>
              ${relative && relative !== doc.name ? `<small>${escapeHtml(relative)}</small>` : ""}
            </div>
            <div class="document-card-meta">
              <span>${escapeHtml(formatBytes(doc.size_bytes))}</span>
              ${openUrl ? `<a href="${escapeHtml(openUrl)}" target="_blank" rel="noreferrer">Ver online</a>` : `<span class="muted">En carpeta</span>`}
            </div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderDocumentTreeNode(node, depth = 0) {
  const children = node.children || [];
  if (node.type === "folder") {
    return `
      <details class="document-tree-folder" ${depth < 2 ? "open" : ""}>
        <summary>
          <span class="document-tree-indent" style="--depth:${depth}"></span>
          <span class="document-tree-icon">▸</span>
          <strong>${escapeHtml(node.name || "Carpeta")}</strong>
          <small>${escapeHtml(children.length ? `${children.length} elemento(s)` : "Vacía")}</small>
        </summary>
        <div class="document-tree-children">
          ${children.map((child) => renderDocumentTreeNode(child, depth + 1)).join("")}
        </div>
      </details>
    `;
  }
  const openUrl = safeDocumentOpenUrl(node.open_url);
  return `
    <article class="document-tree-file">
      <span class="document-tree-indent" style="--depth:${depth}"></span>
      <span class="document-tree-file-icon">${escapeHtml((node.extension || "doc").slice(0, 4).toUpperCase())}</span>
      <div>
        <strong title="${escapeHtml(node.relative_path || node.name)}">${escapeHtml(node.name || "Documento")}</strong>
        <small>${escapeHtml([node.category, formatBytes(node.size_bytes), formatDateTime(node.modified_at)].filter(Boolean).join(" · "))}</small>
      </div>
      ${openUrl ? `<a href="${escapeHtml(openUrl)}" target="_blank" rel="noreferrer">Abrir</a>` : ""}
    </article>
  `;
}

function renderDocumentTreePayload(payload) {
  const tree = payload.tree || [];
  const statusClass = payload.root_status === "valid" ? "ok" : payload.root_status === "missing" ? "danger" : "warning";
  const sourceLabel = payload.source === "inventory" ? "Inventario guardado" : "Lectura directa de carpeta";
  return `
    <section class="document-tree-wrap">
      <div class="document-tree-head">
        <div>
          <p class="eyebrow">Documentación</p>
          <h4>${escapeHtml(payload.root_name || "Carpeta del expediente")}</h4>
          <span class="folder-status-chip ${escapeHtml(statusClass)}">${escapeHtml(payload.message || sourceLabel)}</span>
          ${payload.path_reconcile_message ? `<span class="folder-status-chip warning">${escapeHtml(payload.path_reconcile_message)}</span>` : ""}
        </div>
        <div class="document-tree-meta">
          <strong>${escapeHtml(`${payload.count || 0} fichero(s)`)}</strong>
          <span>${escapeHtml(sourceLabel)}</span>
          ${payload.truncated ? `<span class="danger-text">Listado limitado por seguridad</span>` : ""}
        </div>
      </div>
      ${tree.length ? `<div class="document-tree">${tree.map((node) => renderDocumentTreeNode(node, 0)).join("")}</div>` : `<div class="empty">${escapeHtml(payload.message || "No hay documentación inventariada.")}</div>`}
    </section>
  `;
}

async function loadDocumentTree(licitacionId, options = {}) {
  const panel = licitacionDetailContent.querySelector(`[data-document-tree-panel="${licitacionId}"]`);
  if (!panel) return;
  if (!options.silent) panel.innerHTML = `<div class="empty">Cargando árbol documental...</div>`;
  try {
    const response = await fetch(`/api/licitaciones/${licitacionId}/document-tree`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      panel.innerHTML = `<div class="empty">${escapeHtml(payload.error || "No se pudo consultar la documentación.")}</div>`;
      return;
    }
    appState.documentTrees[licitacionId] = payload;
    panel.innerHTML = renderDocumentTreePayload(payload);
  } catch (error) {
    panel.innerHTML = `<div class="empty">${escapeHtml(error.message || "No se pudo consultar la documentación.")}</div>`;
  }
}

function aiStatusLabel(payload) {
  if (payload.provider_status_label && (!payload.provider_enabled || !payload.provider_configured)) {
    return payload.provider_status_label;
  }
  if (!payload.enabled) return payload.provider_status_label || "IA desactivada";
  if (!payload.configured) return payload.provider_status_label || "IA no configurada";
  if (payload.job_status === "pending" || payload.job_status === "queued") return "En cola";
  if (payload.job_status === "processing") return "Procesando";
  if (payload.job_status === "deferred") return "Límite alcanzado, reintento posterior";
  if (payload.job_status === "error") return "Error";
  if (payload.has_summary) return "Completado";
  return "Sin análisis";
}

function aiProviderFromPayload(payload) {
  return payload?.job?.provider || payload?.active_provider || payload?.analysis_provider || "gemini";
}

function aiProviderErrorMessage(payload) {
  const job = payload?.job || {};
  const provider = aiProviderFromPayload(payload);
  const code = job.error_code || "";
  if (provider === "codex_local") {
    if (code === "CODEX_DISABLED") return "Codex Local no está activado.";
    if (code === "CODEX_NOT_FOUND") return "No se encuentra el ejecutable de Codex.";
    if (code === "CODEX_TIMEOUT") return "Codex no respondió dentro del tiempo configurado.";
    if (code === "INVALID_JSON") return "Codex devolvió una respuesta que no es JSON válido.";
    if (code) return job.error_message || "Error consultando Codex Local.";
  }
  if (provider === "gemini") {
    if (code === "GEMINI_DISABLED") return "Gemini desactivado.";
    if (code === "GEMINI_NOT_CONFIGURED" || code === "NOT_CONFIGURED") return "Gemini no configurado.";
    if (code === "GEMINI_TIMEOUT") return "Gemini no respondió dentro del tiempo configurado.";
    if (code) return job.error_message || "Error consultando Gemini.";
  }
  if (provider === "disabled") return "IA desactivada.";
  return job.error_message || "";
}

function isAiJobActive(payload) {
  return ["pending", "queued", "processing"].includes(payload?.job_status || "");
}

function stopAiSummaryPolling(licitacionId) {
  const key = String(licitacionId);
  const current = appState.aiPolling.get(key);
  if (current?.timer) clearInterval(current.timer);
  appState.aiPolling.delete(key);
}

function startAiSummaryPolling(licitacionId) {
  const key = String(licitacionId);
  if (appState.aiPolling.has(key)) return;
  const startedAt = Date.now();
  const timer = setInterval(() => {
    loadAiSummary(licitacionId, { silent: true, pollingStartedAt: startedAt });
  }, 4000);
  appState.aiPolling.set(key, { timer, startedAt });
}

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours) return `${hours}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function renderAiJobStateCard(licitacionId, job, selectedDocs) {
  if (!job || !["pending", "queued", "processing", "deferred"].includes(job.status || "")) return "";
  const processing = job.status === "processing";
  const longMessage = job.is_taking_longer_than_expected
    ? `<p class="ai-long-running">El análisis está tardando más de lo habitual. Si hay actividad reciente, el worker sigue trabajando.</p>`
    : "";
  return `
    <div class="ai-active-job">
      <div>
        <p class="eyebrow">Análisis IA en curso</p>
        <h4>${escapeHtml(processing ? "Procesando análisis IA" : "Análisis IA en cola")}</h4>
        <p>${escapeHtml(job.progress_message || (processing ? "Puedes cerrar esta ficha y volver más tarde." : "Se iniciará en breve."))}</p>
        ${longMessage}
      </div>
      <dl>
        <dt>Estado</dt><dd>${escapeHtml(job.progress_label || aiStatusLabel({ job_status: job.status }))}</dd>
        <dt>Fase</dt><dd>${escapeHtml(job.progress_stage || "")}</dd>
        <dt>Tiempo</dt><dd>${escapeHtml(formatDuration(job.elapsed_seconds))}</dd>
        <dt>Estimación</dt><dd>${escapeHtml(job.estimated_label || "aprox.")}</dd>
        <dt>Documentos</dt><dd>${escapeHtml(job.selected_documents_count || selectedDocs.length || 0)}</dd>
        <dt>Proveedor</dt><dd>${escapeHtml(job.provider || "")}</dd>
      </dl>
      <div class="ai-active-actions">
        <button type="button" data-ai-refresh="${escapeHtml(licitacionId)}">Actualizar estado</button>
        <button type="button" data-open-ai-queue>Ver Cola IA</button>
      </div>
    </div>
  `;
}

function aiStatusClass(payload) {
  if (payload.has_summary) return "ok";
  if (!payload.provider_enabled || !payload.provider_configured || !payload.enabled || !payload.configured) return "muted";
  if (payload.job_status === "error") return "danger";
  if (payload.job_status === "deferred") return "warning";
  if (payload.job_status === "pending" || payload.job_status === "queued" || payload.job_status === "processing") return "warning";
  return "muted";
}

function renderAiArray(items) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!list.length) return `<div class="empty compact">Sin datos.</div>`;
  return `<ul class="ai-list">${list.map((item) => `<li>${escapeHtml(typeof item === "object" ? JSON.stringify(item) : item)}</li>`).join("")}</ul>`;
}

function aiAsArray(value) {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined && item !== "");
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function aiReadableValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (Array.isArray(value)) return value.map(aiReadableValue).filter(Boolean).join("; ");
  if (typeof value === "object") {
    const parts = Object.values(value).map(aiReadableValue).filter(Boolean);
    return parts.join("; ");
  }
  return String(value);
}

function aiTableValue(item, key) {
  const value = item?.[key];
  if ((value === null || value === undefined || value === "") && ["numero_lote", "presupuesto", "valor_estimado", "importe_minimo"].includes(key)) {
    return "No consta";
  }
  if (typeof value === "number" && ["presupuesto", "valor_estimado", "importe_minimo", "presupuesto_base"].includes(key)) {
    return formatMoney(value);
  }
  return aiReadableValue(value);
}

function aiRiskClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("alta") || text.includes("alto")) return "ai-critical";
  if (text.includes("media") || text.includes("medio")) return "ai-warning-soft";
  return "ai-muted";
}

function renderAiList(items, emptyText = "Sin datos localizados.") {
  const list = aiAsArray(items).map(aiReadableValue).filter(Boolean);
  if (!list.length) return `<p class="ai-muted">${escapeHtml(emptyText)}</p>`;
  return `<ul class="ai-list">${list.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderAiObjectTable(items, columns, emptyText = "Sin datos localizados.") {
  const list = aiAsArray(items).filter((item) => item && typeof item === "object");
  if (!list.length) return `<p class="ai-muted">${escapeHtml(emptyText)}</p>`;
  return `
    <div class="ai-table-scroll">
      <table class="ai-key-table">
        <thead><tr>${columns.map(([label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead>
        <tbody>
          ${list.map((item) => `
            <tr>
              ${columns.map(([, key]) => `<td>${escapeHtml(aiTableValue(item, key))}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderAiKeyTable(rows) {
  const visibleRows = rows.filter((row) => aiReadableValue(row.value) || aiReadableValue(row.note));
  if (!visibleRows.length) return `<p class="ai-muted">No hay datos clave localizados.</p>`;
  return `
    <div class="ai-table-scroll">
      <table class="ai-key-table">
        <thead><tr><th>Campo</th><th>Valor</th><th>Observación</th></tr></thead>
        <tbody>
          ${visibleRows.map((row) => `
            <tr class="${row.critical ? "ai-row-critical" : ""}">
              <td>${escapeHtml(row.label)}</td>
              <td>${escapeHtml(aiReadableValue(row.value))}</td>
              <td>${escapeHtml(aiReadableValue(row.note))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderAiAlertList(alerts) {
  const list = aiAsArray(alerts).filter((item) => item && typeof item === "object");
  if (!list.length) return `<p class="ai-muted">Sin alertas destacadas.</p>`;
  return `
    <div class="ai-alert-list">
      ${list.map((item) => `
        <article class="${aiRiskClass(item.nivel)}">
          <strong>${escapeHtml(item.titulo || item.nivel || "Alerta")}</strong>
          <p>${escapeHtml(item.descripcion || item.observaciones || "")}</p>
          ${item.accion_recomendada ? `<span>${escapeHtml(item.accion_recomendada)}</span>` : ""}
        </article>
      `).join("")}
    </div>
  `;
}

function aiCriteriaAsObject(value) {
  if (Array.isArray(value)) return { juicio_valor: [], formulas: value, total_puntos: "", observaciones: "" };
  return value && typeof value === "object" ? value : { juicio_valor: [], formulas: [], total_puntos: "", observaciones: "" };
}

function renderAiSummaryBlocks(payload) {
  const record = payload.summary || {};
  const data = record.summary || {};
  if (!data || !Object.keys(data).length) return `<div class="empty">Todavía no hay análisis guardado.</div>`;
  const metadata = data.metadata || {};
  const ejecutivo = data.resumen_ejecutivo || {};
  const caracteristicas = data.caracteristicas || {};
  const economicos = data.datos_economicos || {};
  const plazos = data.plazos || {};
  const garantias = data.garantias || {};
  const presentacion = data.presentacion_documentacion || data.presentacion || {};
  const muestras = data.muestras_fichas_memoria || {};
  const solvencia = data.solvencia || {};
  const subcontratacion = data.subcontratacion || {};
  const criterios = aiCriteriaAsObject(data.criterios_adjudicacion);
  const operaciones = data.observaciones_operativas || data.logistica_entrega || {};
  const calidad = data.control_calidad || {};
  const technical = {
    provider: record.provider || payload.provider || "",
    job_id: payload.job?.id || "",
    document_hash: record.document_hash || payload.document_hash || "",
    model: record.model || payload.model || "",
    generated_at: record.updated_at || record.created_at || "",
    selected_documents: payload.selected_documents || [],
    quality_check: payload.job?.quality_check || {},
    diagnostics: payload.job?.diagnostics || {},
  };
  return `
    <div class="ai-ficha">
      <div class="ai-warning">Análisis automático. Revisar siempre contra los pliegos antes de enviar información al cliente.</div>
      <section class="ai-section full">
        <h4 class="ai-section-title">Resumen ejecutivo</h4>
        <p>${escapeHtml(ejecutivo.texto || record.summary_text || "Sin resumen ejecutivo.")}</p>
        ${renderAiList(ejecutivo.aspectos_clave, "Sin aspectos clave.")}
        ${ejecutivo.decision_preliminar ? `<p class="ai-decision">${escapeHtml(ejecutivo.decision_preliminar)}</p>` : ""}
      </section>
      <section class="ai-section full">
        <h4 class="ai-section-title">Alertas y acciones</h4>
        ${renderAiAlertList(data.alertas)}
        <h5>Acciones recomendadas</h5>
        ${renderAiObjectTable(data.acciones_recomendadas, [["Prioridad", "prioridad"], ["Acción", "accion"], ["Motivo", "motivo"]], "Sin acciones recomendadas.")}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Datos clave</h4>
        ${renderAiKeyTable([
          { label: "Expediente", value: metadata.expediente },
          { label: "Título", value: metadata.titulo },
          { label: "Organismo", value: metadata.organismo },
          { label: "Provincia", value: metadata.provincia },
          { label: "Plataforma", value: metadata.plataforma },
          { label: "Fecha límite", value: [metadata.fecha_limite_presentacion, metadata.hora_limite_presentacion].filter(Boolean).join(" ") },
          { label: "Tipo de contrato", value: metadata.tipo_contrato },
          { label: "Regulación armonizada", value: metadata.regulacion_armonizada },
          { label: "Presupuesto base", value: typeof (caracteristicas.presupuesto_base ?? economicos.presupuesto_base) === "number" ? formatMoney(caracteristicas.presupuesto_base ?? economicos.presupuesto_base) : (caracteristicas.presupuesto_base ?? economicos.presupuesto_base), note: caracteristicas.moneda || economicos.moneda },
          { label: "Valor estimado", value: typeof (caracteristicas.valor_estimado ?? economicos.valor_estimado) === "number" ? formatMoney(caracteristicas.valor_estimado ?? economicos.valor_estimado) : (caracteristicas.valor_estimado ?? economicos.valor_estimado), note: caracteristicas.moneda || economicos.moneda },
          { label: "Plazo ejecución inicial", value: caracteristicas.plazo_ejecucion_inicial || plazos.plazo_ejecucion_inicial },
          { label: "Prórrogas", value: caracteristicas.prorrogas?.existen ?? plazos.prorrogas?.existen, note: caracteristicas.prorrogas?.detalle || plazos.prorrogas?.detalle },
          { label: "Adjudicación", value: caracteristicas.adjudicacion },
          { label: "Nº sobres", value: caracteristicas.numero_sobres ?? presentacion.numero_sobres },
          { label: "Garantía provisional", value: garantias.garantia_provisional?.exigida, note: [garantias.garantia_provisional?.importe, garantias.garantia_provisional?.alerta, garantias.garantia_provisional?.observaciones].filter(Boolean).join(" · "), critical: garantias.garantia_provisional?.exigida === true },
          { label: "Garantía definitiva", value: garantias.garantia_definitiva?.exigida, note: [garantias.garantia_definitiva?.importe, garantias.garantia_definitiva?.observaciones].filter(Boolean).join(" · ") },
          { label: "Garantía complementaria", value: garantias.garantia_complementaria?.exigida, note: garantias.garantia_complementaria?.observaciones, critical: garantias.garantia_complementaria?.exigida === true },
          { label: "Fichas técnicas", value: muestras.fichas_tecnicas?.exigidas, note: muestras.fichas_tecnicas?.detalle, critical: muestras.fichas_tecnicas?.exigidas === true },
          { label: "Memoria técnica", value: muestras.memoria_tecnica?.exigida, note: muestras.memoria_tecnica?.detalle, critical: muestras.memoria_tecnica?.exigida === true },
          { label: "Adscripción de medios", value: muestras.adscripcion_medios?.exigida, note: muestras.adscripcion_medios?.detalle, critical: muestras.adscripcion_medios?.exigida === true },
        ])}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Lotes</h4>
        ${renderAiObjectTable(data.lotes, [["Lote", "numero_lote"], ["Denominación", "denominacion"], ["Presupuesto", "presupuesto"], ["Observaciones", "observaciones"]], "Expediente completo o sin división en lotes localizada.")}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Presentación y documentación</h4>
        ${renderAiKeyTable([
          { label: "Forma de presentación", value: presentacion.forma_presentacion },
          { label: "Nº sobres", value: presentacion.numero_sobres },
          { label: "Observaciones", value: presentacion.observaciones },
        ])}
        <h5>Documentación administrativa</h5>
        ${renderAiList(presentacion.documentacion_administrativa)}
        <h5>Documentación técnica</h5>
        ${renderAiList(presentacion.documentacion_tecnica)}
        <h5>Documentación económica</h5>
        ${renderAiList(presentacion.documentacion_economica)}
        <h5>Anexos relevantes</h5>
        ${renderAiList(presentacion.anexos_relevantes)}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Muestras / fichas / memoria</h4>
        ${renderAiKeyTable([
          { label: "Muestras", value: muestras.muestras?.exigidas, note: [muestras.muestras?.momento, muestras.muestras?.detalle, muestras.muestras?.consecuencia_no_presentar].filter(Boolean).join(" · "), critical: muestras.muestras?.exigidas === true },
          { label: "Fichas técnicas", value: muestras.fichas_tecnicas?.exigidas, note: [muestras.fichas_tecnicas?.sobre, muestras.fichas_tecnicas?.detalle].filter(Boolean).join(" · "), critical: muestras.fichas_tecnicas?.exigidas === true },
          { label: "Memoria técnica", value: muestras.memoria_tecnica?.exigida, note: muestras.memoria_tecnica?.detalle, critical: muestras.memoria_tecnica?.exigida === true },
          { label: "Adscripción medios", value: muestras.adscripcion_medios?.exigida, note: muestras.adscripcion_medios?.detalle, critical: muestras.adscripcion_medios?.exigida === true },
        ])}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Criterios de adjudicación</h4>
        <h5>Criterios sujetos a juicio de valor</h5>
        ${renderAiObjectTable(criterios.juicio_valor, [["Criterio", "nombre"], ["Puntos", "puntuacion_maxima"], ["Documentación", "documentacion_a_aportar"], ["Observaciones", "observaciones"]], "No se han localizado criterios de juicio de valor.")}
        <h5>Criterios mediante fórmulas</h5>
        ${renderAiObjectTable(criterios.formulas, [["Criterio", "nombre"], ["Puntos", "puntuacion_maxima"], ["Fórmula / valoración", "formula"], ["Documentación", "documentacion_a_aportar"], ["Observaciones", "observaciones"]], "No se han localizado criterios mediante fórmulas.")}
        ${criterios.total_puntos ? `<p class="ai-muted">Total puntos: ${escapeHtml(criterios.total_puntos)}</p>` : ""}
        ${criterios.observaciones ? `<p>${escapeHtml(criterios.observaciones)}</p>` : ""}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Subcontratación</h4>
        ${renderAiKeyTable([
          { label: "Permitida", value: subcontratacion.permitida },
          { label: "Debe declararse", value: subcontratacion.debe_declararse_en_oferta },
          { label: "Pago directo subcontratistas", value: subcontratacion.pago_directo_subcontratistas },
          { label: "Restricciones", value: subcontratacion.restricciones },
          { label: "Penalidades", value: subcontratacion.penalidades },
          { label: "Comentario práctico", value: subcontratacion.comentario_practico },
          { label: "Alerta", value: subcontratacion.alerta, critical: Boolean(subcontratacion.alerta) },
        ])}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Solvencia</h4>
        <h5>Económica</h5>
        ${renderAiObjectTable(solvencia.economica, [["Lote", "lote"], ["Objeto", "objeto"], ["Importe mínimo", "importe_minimo"], ["Detalle", "detalle"]], "No localizada en los documentos seleccionados.")}
        <h5>Técnica</h5>
        ${renderAiObjectTable(solvencia.tecnica, [["Lote", "lote"], ["Objeto", "objeto"], ["Importe mínimo", "importe_minimo"], ["Certificados/suministros", "certificados_o_suministros"], ["Detalle", "detalle"]], "No localizada en los documentos seleccionados.")}
        ${solvencia.observaciones ? `<p>${escapeHtml(solvencia.observaciones)}</p>` : ""}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Condiciones especiales de ejecución</h4>
        ${renderAiObjectTable(data.condiciones_especiales_ejecucion, [["Categoría", "categoria"], ["Obligación", "obligacion"], ["Riesgo", "riesgo"], ["Observaciones", "observaciones"]], "No localizadas en los documentos seleccionados.")}
      </section>
      <section class="ai-section">
        <h4 class="ai-section-title">Observaciones operativas</h4>
        ${renderAiKeyTable([
          { label: "Habilitación profesional", value: operaciones.habilitacion_profesional },
          { label: "Seguro obligatorio", value: operaciones.seguro_obligatorio },
          { label: "Lugar de entrega", value: operaciones.lugar_entrega || operaciones.lugares_entrega },
          { label: "Horario", value: operaciones.horario_entrega || operaciones.horarios_entrega },
          { label: "Plazo de entrega", value: operaciones.plazo_entrega || operaciones.plazos_entrega_desde_pedido },
          { label: "Periodicidad", value: operaciones.periodicidad },
          { label: "Transporte", value: operaciones.transporte },
          { label: "Descarga", value: operaciones.descarga },
          { label: "Albaranes", value: operaciones.albaranes },
          { label: "Envases/etiquetado", value: operaciones.envases_etiquetado },
          { label: "Caducidad/consumo preferente", value: operaciones.caducidad_consumo_preferente },
          { label: "Observaciones producto", value: operaciones.observaciones_producto },
        ])}
      </section>
      <details class="ai-section ai-technical-details">
        <summary>Campos no encontrados / baja confianza</summary>
        <h5>Campos no encontrados</h5>
        ${renderAiList(calidad.campos_no_encontrados)}
        <h5>Campos con baja confianza</h5>
        ${renderAiList(calidad.campos_con_baja_confianza)}
        <h5>Advertencias</h5>
        ${renderAiList(calidad.advertencias)}
      </details>
      ${aiAsArray(data.referencias_historicas_no_analizadas).length ? `
        <details class="ai-section ai-technical-details">
          <summary>Licitación anterior</summary>
          <p>Referencia histórica detectada. No analizada en esta fase.</p>
          ${renderAiObjectTable(data.referencias_historicas_no_analizadas, [["Descripción", "descripcion"], ["Motivo", "motivo_no_analisis"]])}
        </details>
      ` : ""}
      <details class="ai-section ai-technical-details">
        <summary>Ver detalles técnicos</summary>
        <pre>${escapeHtml(JSON.stringify(technical, null, 2))}</pre>
      </details>
    </div>
  `;
}

function renderAiDocumentDiagnostics(payload) {
  const diagnostics = payload.document_diagnostics || {};
  const selectedDocs = payload.selected_documents || [];
  if (selectedDocs.length) return "";
  const parts = [];
  if (diagnostics.resolved_message) parts.push(diagnostics.resolved_message);
  if (diagnostics.pdfs_found_count !== undefined) parts.push(`${diagnostics.pdfs_found_count} PDF(s) encontrados`);
  if (diagnostics.discarded_documents_count) parts.push(`${diagnostics.discarded_documents_count} descartado(s) por reglas de selección`);
  const message = diagnostics.final_reason || payload.motivo_si_no_puede_generar || "";
  const adminDetails = isAdmin()
    ? `<details class="ai-technical-json"><summary>Diagnóstico documental</summary><pre>${escapeHtml(JSON.stringify(diagnostics, null, 2))}</pre></details>`
    : "";
  if (!message && !parts.length && !adminDetails) return "";
  return `
    <div class="ai-warning">
      ${message ? `<strong>${escapeHtml(message)}</strong>` : ""}
      ${parts.length ? `<p>${escapeHtml(parts.join(" · "))}</p>` : ""}
    </div>
    ${adminDetails}
  `;
}

function renderAiNotificationStatus(status) {
  if (!status || !status.label) return "";
  const items = status.items || [];
  const detail = items.length ? `
    <details>
      <summary>Detalle de avisos</summary>
      <ul>
        ${items.map((item) => `<li>${escapeHtml(item.recipient_email || "")} — ${escapeHtml(item.status || "")}${item.error_message ? ` · ${escapeHtml(item.error_message)}` : ""}</li>`).join("")}
      </ul>
    </details>
  ` : "";
  return `
    <div class="ai-notification-status ${escapeHtml(status.state || "none")}">
      <span>${escapeHtml(status.label)}</span>
      ${detail}
    </div>
  `;
}

function renderAiSummaryContent(licitacionId, payload) {
  const selectedDocs = payload.selected_documents || [];
  const job = payload.job || {};
  const canGenerate = Boolean(payload.puede_generar);
  const canRetry = payload.job_status === "error" || payload.job_status === "deferred";
  const hasAnyAnalysis = Boolean(payload.has_summary || payload.job_status || payload.job);
  const reason = aiProviderErrorMessage(payload) || payload.motivo_si_no_puede_generar || job.error_message || "";
  const summaryQuality = payload.summary?.quality_status || payload.job?.summary_quality_status || "";
  const canEmailSummary = Boolean(payload.has_summary && !["empty_analysis", "low_quality_analysis", "encoding_error"].includes(summaryQuality));
  const activeMessage = renderAiJobStateCard(licitacionId, job, selectedDocs);
  return `
    <div class="ai-summary-toolbar">
      <span class="ai-status ${aiStatusClass(payload)}">${escapeHtml(aiStatusLabel(payload))}</span>
      <span>${escapeHtml(selectedDocs.length ? `${selectedDocs.length} documento(s) seleccionado(s)` : "Sin documentos aptos")}</span>
      ${payload.document_hash ? `<code title="${escapeHtml(payload.document_hash)}">${escapeHtml(payload.document_hash.slice(0, 12))}</code>` : ""}
      <div class="ai-actions">
        <button type="button" data-ai-generate="${escapeHtml(licitacionId)}" ${canGenerate && !payload.has_summary ? "" : "disabled"}>Generar análisis IA</button>
        ${isAdmin() ? `<button type="button" data-ai-regenerate="${escapeHtml(licitacionId)}" ${canGenerate ? "" : "disabled"}>Regenerar análisis IA</button>` : ""}
        <button type="button" data-ai-generate="${escapeHtml(licitacionId)}" ${canRetry && canGenerate ? "" : "disabled"}>Reintentar</button>
        <button type="button" data-ai-email="${escapeHtml(licitacionId)}" ${canEmailSummary ? "" : "disabled"}>Enviar por correo</button>
        ${hasAnyAnalysis ? `<button type="button" class="danger-soft" data-ai-delete="${escapeHtml(licitacionId)}">Borrar</button>` : ""}
      </div>
    </div>
    ${reason ? `<div class="ai-reason">${escapeHtml(reason)}</div>` : ""}
    ${activeMessage}
    ${renderAiNotificationStatus(payload.notification_status)}
    ${renderAiDocumentDiagnostics(payload)}
    ${selectedDocs.length ? `
      <div class="ai-documents">
        ${selectedDocs.map((doc) => `<span title="${escapeHtml(doc.path || "")}">${escapeHtml(doc.name || doc.relative_path || "Documento")} · ${escapeHtml(doc.reason || "")}</span>`).join("")}
      </div>
    ` : ""}
    ${renderAiSummaryBlocks(payload)}
  `;
}

async function loadAiSummary(licitacionId, options = {}) {
  const panel = licitacionDetailContent.querySelector(`[data-ai-summary-panel="${licitacionId}"]`);
  if (!panel) return;
  if (!options.silent) panel.innerHTML = `<div class="empty">Cargando estado IA...</div>`;
  try {
    const response = await fetch(`/api/licitaciones/${licitacionId}/ai-summary`);
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      panel.innerHTML = `<div class="empty">${escapeHtml(result.error || "No se pudo consultar el análisis IA.")}</div>`;
      return;
    }
    panel.innerHTML = renderAiSummaryContent(licitacionId, result);
    if (isAiJobActive(result)) {
      startAiSummaryPolling(licitacionId);
    } else {
      stopAiSummaryPolling(licitacionId);
    }
  } catch (error) {
    panel.innerHTML = `<div class="empty">${escapeHtml(error.message || "No se pudo consultar el análisis IA.")}</div>`;
  }
}

function renderAiQueueJobs(title, items) {
  if (!items.length) return "";
  return `
    <section class="ai-queue-section">
      <h3>${escapeHtml(title)}</h3>
      <div class="ai-queue-table-wrap">
        <table class="ai-queue-table">
          <thead>
            <tr>
              <th>Estado</th>
              <th>Expediente</th>
              <th>Título</th>
              <th>Proveedor</th>
              <th>Inicio / creado</th>
              <th>Tiempo</th>
              <th>Estimación</th>
              <th>Docs.</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            ${items.map((job) => `
              <tr class="${job.is_taking_longer_than_expected ? "is-late" : ""}">
                <td>
                  <span class="ai-status ${job.status === "error" ? "danger" : job.status === "completed" ? "ok" : "warning"}">${escapeHtml(job.progress_label || job.status || "")}</span>
                  ${job.progress_message ? `<small>${escapeHtml(job.progress_message)}</small>` : ""}
                </td>
                <td><strong>${escapeHtml(job.expediente || "")}</strong></td>
                <td>${escapeHtml(job.titulo_corto || "")}</td>
                <td>${escapeHtml(job.provider || "")}</td>
                <td>${escapeHtml(formatDateTime(job.started_at || job.created_at))}</td>
                <td>${escapeHtml(formatDuration(job.elapsed_seconds))}</td>
                <td>${escapeHtml(job.estimated_label || "")}</td>
                <td>
                  ${escapeHtml(job.selected_documents_count || 0)}
                  ${job.notification_status?.state && job.notification_status.state !== "none" ? `<small>${escapeHtml(job.notification_status.label || "")}</small>` : ""}
                </td>
                <td>
                  <div class="ai-queue-actions">
                    ${job.can_open ? `<button type="button" data-ai-queue-open="${escapeHtml(job.licitacion_id)}">Abrir ficha</button>` : ""}
                    ${job.can_cancel ? `<button type="button" data-ai-queue-cancel="${escapeHtml(job.id)}" data-ai-queue-cancel-status="${escapeHtml(job.status || "")}">Cancelar</button>` : ""}
                    ${job.can_retry ? `<button type="button" data-ai-queue-open="${escapeHtml(job.licitacion_id)}">Reintentar</button>` : ""}
                    ${!["pending", "queued", "processing", "deferred"].includes(job.status || "") ? `<button type="button" data-ai-queue-dismiss="${escapeHtml(job.id)}">Ocultar</button>` : ""}
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderAiQueue(payload) {
  const active = payload.active_jobs || [];
  const recent = payload.recent_jobs || [];
  if (!active.length && !recent.length) return `<div class="empty">No hay trabajos IA en cola ni recientes.</div>`;
  return `
    ${renderAiQueueJobs("Activos", active)}
    ${renderAiQueueJobs("Recientes", recent)}
  `;
}

function updateAiQueueBadge(payload) {
  const counts = payload?.counts || {};
  const active = Number(counts.active || 0);
  const errors = Number(counts.error_recent || 0);
  if (!aiQueueBadge) return;
  aiQueueBadge.hidden = active <= 0 && errors <= 0;
  aiQueueBadge.textContent = active > 0 ? String(active) : errors ? "!" : "0";
  aiQueueBadge.classList.toggle("has-error", active <= 0 && errors > 0);
}

function handleAiQueueActionError(error, fallbackMessage) {
  const rawMessage = String(error?.message || "").trim();
  if (!rawMessage || rawMessage === "Failed to fetch" || rawMessage.includes("NetworkError")) {
    return "No se pudo contactar con la web local. Comprueba que la Suite sigue arrancada.";
  }
  return rawMessage || fallbackMessage;
}

function parseEmailList(value, { required = false } = {}) {
  const raw = Array.isArray(value) ? value.join(",") : String(value || "");
  const parts = raw.split(/[,;\n\r]+/).map((part) => part.trim()).filter(Boolean);
  const emails = [];
  const invalid = [];
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  parts.forEach((part) => {
    const match = part.match(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/i);
    const email = (match ? match[0] : part.replace(/^mailto:/i, "")).trim().toLowerCase();
    if (!emailPattern.test(email)) {
      invalid.push(part);
      return;
    }
    if (!emails.includes(email)) emails.push(email);
  });
  if (invalid.length) throw new Error(`Email no válido: ${invalid.join(", ")}`);
  if (required && !emails.length) throw new Error("Indica al menos un email de destino válido.");
  return emails;
}

async function loadAiQueue(options = {}) {
  try {
    const response = await fetch("/api/ai/queue");
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error_message || payload.error || "No se pudo consultar la Cola IA.");
    }
    appState.aiQueue = payload;
    updateAiQueueBadge(payload);
    if (aiQueueContent && (appState.aiQueueOpen || options.forceRender)) {
      aiQueueContent.innerHTML = renderAiQueue(payload);
    }
    if (aiQueueStatus) {
      aiQueueStatus.className = "import-result";
      aiQueueStatus.textContent = "";
    }
  } catch (error) {
    if (aiQueueStatus && appState.aiQueueOpen) {
      aiQueueStatus.className = "import-result error";
      aiQueueStatus.textContent = handleAiQueueActionError(error, "No se pudo consultar la Cola IA.");
    }
  }
}

function startAiQueuePolling(interval = 15000) {
  if (appState.aiQueueTimer) clearInterval(appState.aiQueueTimer);
  appState.aiQueueTimer = setInterval(() => {
    if (document.hidden && !appState.aiQueueOpen) return;
    loadAiQueue();
  }, interval);
}

function openAiQueueDialog() {
  appState.aiQueueOpen = true;
  if (aiQueueContent) aiQueueContent.innerHTML = `<div class="empty">Cargando Cola IA...</div>`;
  aiQueueDialog.showModal();
  loadAiQueue({ forceRender: true });
  startAiQueuePolling(5000);
}

function closeAiQueueDialog() {
  appState.aiQueueOpen = false;
  aiQueueDialog.close();
  startAiQueuePolling(15000);
}

async function aiQueueAction(jobId, action, button = null) {
  if (button) {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  }
  try {
    const response = await fetch(`/api/ai/jobs/${jobId}/${action}`, { method: "POST", headers: csrfHeaders() });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error_message || payload.error || "No se pudo actualizar el trabajo IA.");
    }
    await loadAiQueue({ forceRender: true });
    if (aiQueueStatus) {
      aiQueueStatus.className = "import-result success";
      aiQueueStatus.textContent = payload.message || "Trabajo IA actualizado.";
    }
  } finally {
    if (button) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }
}

function updateAiFileSelectionCount() {
  const checked = aiFileList ? [...aiFileList.querySelectorAll("input[type='checkbox']:checked")].length : 0;
  if (aiFileSelectionCount) aiFileSelectionCount.textContent = `${checked} fichero(s) seleccionado(s)`;
  if (confirmAiFileSelectionButton) confirmAiFileSelectionButton.disabled = checked === 0;
}

function renderAiFileRows(items) {
  if (!aiFileList) return;
  if (!items.length) {
    aiFileList.innerHTML = `<tr><td colspan="5" class="empty">No se han encontrado ficheros aptos en la carpeta del expediente.</td></tr>`;
    updateAiFileSelectionCount();
    return;
  }
  aiFileList.innerHTML = items.map((item) => `
    <tr class="${item.warning ? "not-recommended" : ""}">
      <td><input type="checkbox" value="${escapeHtml(item.relative_path)}" ${item.selected_by_default ? "checked" : ""} ${item.selectable ? "" : "disabled"}></td>
      <td title="${escapeHtml(item.relative_path || item.name)}">
        <strong>${escapeHtml(item.name)}</strong>
        ${item.warning ? `<small>${escapeHtml(item.warning)}</small>` : ""}
      </td>
      <td>${escapeHtml(item.extension || "")}</td>
      <td>${escapeHtml(formatDateTime(item.modified_at) || item.modified_at || "")}</td>
      <td>${escapeHtml(item.size_human || formatBytes(item.size_bytes))}</td>
    </tr>
  `).join("");
  aiFileList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", updateAiFileSelectionCount);
  });
  updateAiFileSelectionCount();
}

async function openAiFileSelection(licitacionId, button, force = false) {
  appState.aiFileSelection = { licitacionId, force, button, files: [] };
  if (aiFileStatus) {
    aiFileStatus.className = "import-result";
    aiFileStatus.textContent = "";
  }
  if (aiFileList) aiFileList.innerHTML = `<tr><td colspan="5" class="empty">Cargando ficheros...</td></tr>`;
  if (confirmAiFileSelectionButton) confirmAiFileSelectionButton.disabled = true;
  if (aiNotifyOnCompletion) aiNotifyOnCompletion.checked = true;
  if (aiNotificationEmails) aiNotificationEmails.value = appState.user?.email || "";
  aiFileDialog.showModal();
  try {
    const response = await fetch(`/api/licitaciones/${licitacionId}/ai-files`);
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "No se pudieron listar los ficheros.");
    appState.aiFileSelection.files = result.items || [];
    renderAiFileRows(appState.aiFileSelection.files);
  } catch (error) {
    if (aiFileStatus) {
      aiFileStatus.className = "import-result error";
      aiFileStatus.textContent = error.message || "No se pudieron listar los ficheros.";
    }
    renderAiFileRows([]);
  }
}

function closeAiFileSelection() {
  appState.aiFileSelection = null;
  aiFileDialog.close();
}

async function confirmAiFileSelection() {
  const state = appState.aiFileSelection;
  if (!state) return;
  const selectedFiles = [...aiFileList.querySelectorAll("input[type='checkbox']:checked")].map((input) => input.value);
  if (!selectedFiles.length) {
    if (aiFileStatus) aiFileStatus.textContent = "Selecciona al menos un fichero.";
    return;
  }
  let notificationEmails = [];
  const notifyOnCompletion = Boolean(aiNotifyOnCompletion?.checked);
  try {
    notificationEmails = parseEmailList(aiNotificationEmails?.value || "", { required: notifyOnCompletion });
  } catch (error) {
    if (aiFileStatus) {
      aiFileStatus.className = "import-result error";
      aiFileStatus.textContent = error.message || "Revisa los destinatarios del aviso.";
    }
    return;
  }
  closeAiFileSelection();
  await runAiSummaryGeneration(state.licitacionId, state.button, state.force, selectedFiles, {
    notify_on_completion: notifyOnCompletion,
    notification_emails: notifyOnCompletion ? notificationEmails : [],
  });
}

async function runAiSummaryGeneration(licitacionId, button, force = false, selectedFiles = null, notificationOptions = {}) {
  const panel = licitacionDetailContent.querySelector(`[data-ai-summary-panel="${licitacionId}"]`);
  const originalText = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = force ? "Regenerando..." : "Generando...";
  }
  try {
    const endpoint = force
      ? `/api/licitaciones/${licitacionId}/ai-summary/regenerate`
      : `/api/licitaciones/${licitacionId}/ai-summary/generate`;
    if (panel) panel.innerHTML = `<div class="empty">Iniciando análisis IA...</div>`;
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { ...csrfHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_files: selectedFiles || [],
        provider: appState.config?.ai?.analysis_provider || undefined,
        notify_on_completion: Boolean(notificationOptions.notify_on_completion),
        notification_emails: notificationOptions.notification_emails || [],
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (panel) panel.innerHTML = `<div class="empty">${escapeHtml(result.error || "No se pudo generar el análisis IA.")}</div>`;
      return;
    }
    if (panel) panel.innerHTML = renderAiSummaryContent(licitacionId, result);
    if (isAiJobActive(result)) startAiSummaryPolling(licitacionId);
    loadAiQueue();
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function generateAiSummary(licitacionId, button, force = false) {
  await openAiFileSelection(licitacionId, button, force);
}

async function deleteAiSummary(licitacionId) {
  const ok = confirm("Esto borrará únicamente el análisis IA guardado para esta licitación. No se borrará ningún documento de la carpeta del expediente.");
  if (!ok) return;
  stopAiSummaryPolling(licitacionId);
  const panel = licitacionDetailContent.querySelector(`[data-ai-summary-panel="${licitacionId}"]`);
  if (panel) panel.innerHTML = `<div class="empty">Borrando análisis IA...</div>`;
  const response = await fetch(`/api/licitaciones/${licitacionId}/ai-summary`, { method: "DELETE", headers: csrfHeaders() });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (panel) panel.innerHTML = `<div class="empty">${escapeHtml(result.error || "No se pudo borrar el análisis.")}</div>`;
    return;
  }
  if (panel) panel.innerHTML = renderAiSummaryContent(licitacionId, result);
}

function openAiSummaryEmail(licitacionId) {
  const detail = appState.cardDetails[licitacionId]?.item || {};
  const subject = `Análisis IA - ${detail.expediente || "licitación"} - ${String(detail.objeto || "").slice(0, 60)}`;
  appState.aiSummaryEmail = { licitacionId };
  aiSummaryEmailTo.value = appState.user?.email || "";
  aiSummaryEmailSubject.value = subject;
  aiSummaryEmailPreview.value = [
    `Expediente: ${detail.expediente || ""}`,
    `Objeto: ${detail.objeto || ""}`,
    `Fecha límite: ${[formatDate(detail.fecha_limite), detail.hora_limite].filter(Boolean).join(" ")}`,
    "",
    "Se enviará el análisis IA guardado. No se adjuntarán documentos.",
  ].join("\n");
  aiSummaryEmailStatus.textContent = "";
  aiSummaryEmailDialog.showModal();
}

async function sendAiSummaryEmail() {
  const state = appState.aiSummaryEmail;
  if (!state) return;
  let recipients = [];
  try {
    recipients = parseEmailList(aiSummaryEmailTo.value, { required: true });
  } catch (error) {
    aiSummaryEmailStatus.className = "import-result error";
    aiSummaryEmailStatus.textContent = error.message || "Revisa los destinatarios.";
    return;
  }
  sendAiSummaryEmailButton.disabled = true;
  sendAiSummaryEmailButton.textContent = "Enviando...";
  try {
    const response = await fetch(`/api/licitaciones/${state.licitacionId}/ai-summary/email`, {
      method: "POST",
      headers: { ...csrfHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ notification_emails: recipients, subject: aiSummaryEmailSubject.value }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      throw new Error(result.error || result.notification_status?.label || "No se pudo enviar el email.");
    }
    aiSummaryEmailStatus.className = "import-result ok";
    aiSummaryEmailStatus.textContent = result.notification_status?.label || "Email enviado correctamente.";
    loadAiSummary(state.licitacionId, { silent: true });
  } catch (error) {
    aiSummaryEmailStatus.className = "import-result error";
    aiSummaryEmailStatus.textContent = error.message || "No se pudo enviar el email.";
  } finally {
    sendAiSummaryEmailButton.disabled = false;
    sendAiSummaryEmailButton.textContent = "Enviar";
  }
}

function markerStatusText(value) {
  return value ? "Existe" : "No consta";
}

function renderLicitacionMarkerActions(item, seguimiento) {
  if (!isAdmin()) return "";
  const id = item.id;
  const folderExists = Boolean(seguimiento.folder_exists);
  const idMarkerExists = Boolean(seguimiento.id_marker_exists);
  const followMarkerExists = Boolean(seguimiento.follow_marker_exists);
  const idFileName = `${id}.llangon`;
  return `
    <div class="marker-actions full-width">
      <button type="button" data-marker-action="id" data-marker-licitacion-id="${escapeHtml(id)}" ${!folderExists || idMarkerExists ? "disabled" : ""}>
        ${idMarkerExists ? "Ya existe" : `Crear ${escapeHtml(idFileName)}`}
      </button>
      <button type="button" data-marker-action="follow" data-marker-licitacion-id="${escapeHtml(id)}" ${!folderExists || followMarkerExists ? "disabled" : ""}>
        ${followMarkerExists ? "Ya existe" : "Crear EnSeguimiento.llangon"}
      </button>
      <button type="button" data-open-licitacion-folder="${escapeHtml(id)}" ${!folderExists ? "disabled" : ""}>Abrir carpeta</button>
      <small class="marker-action-result" data-marker-action-result="${escapeHtml(id)}"></small>
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
      <div class="detail"><span>Carpeta</span>${escapeHtml(seguimiento.folder_exists ? "Localizada" : "No localizada")}</div>
      <div class="detail"><span>${escapeHtml(`${item.id}.llangon`)}</span>${escapeHtml(markerStatusText(seguimiento.id_marker_exists))}</div>
      <div class="detail"><span>EnSeguimiento.llangon</span>${escapeHtml(markerStatusText(seguimiento.follow_marker_exists))}</div>
      <div class="detail"><span>Última sincronización</span>${escapeHtml(seguimiento.ultima_sync || seguimiento.ultimo_check || "Pendiente")}</div>
      <div class="detail"><span>Última novedad</span>${escapeHtml(seguimiento.ultima_novedad || "Sin novedades")}</div>
      ${seguimiento.warning ? `<div class="detail full-width warning-detail"><span>Aviso</span>${escapeHtml(seguimiento.warning)}</div>` : ""}
      ${renderLicitacionMarkerActions(item, seguimiento)}
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
            ${renderCommentsWidget("actuacion", actuacion.id, actuacion.comments_summary)}
          </div>
          <div class="links">
            <button data-edit-actuacion="${escapeHtml(actuacion.id)}">Abrir actuación</button>
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
  showPreparedNoticeFromResult(result);
}

function setPreparedNoticeStatus(message = "", type = "") {
  if (!preparedNoticeStatus) return;
  preparedNoticeStatus.textContent = message;
  preparedNoticeStatus.className = `import-result ${type}`.trim();
}

function showPreparedNoticeFromResult(result) {
  const preview = result?.prepared_notice_preview;
  if (!preview || !preparedNoticeDialog) return;
  appState.preparedNoticePreview = preview;
  appState.preparedNoticeSending = false;
  preparedNoticeTo.value = preview.to || "";
  preparedNoticeSubject.value = preview.subject || "";
  preparedNoticeBody.value = preview.email_body || "";
  sendPreparedNoticeButton.textContent = "Enviar email";
  sendPreparedNoticeButton.disabled = false;
  setPreparedNoticeStatus(preview.email_warning || "", preview.email_warning ? "error" : "");
  if (typeof preparedNoticeDialog.showModal === "function") {
    preparedNoticeDialog.showModal();
  } else {
    alert("Ficha preparada. Revisa el aviso asistido.");
  }
}

function closePreparedNotice() {
  if (preparedNoticeDialog?.open) preparedNoticeDialog.close();
  appState.preparedNoticePreview = null;
  appState.preparedNoticeSending = false;
}

async function copyPreparedNoticeText() {
  const preview = appState.preparedNoticePreview;
  if (!preview) return;
  const text = preview.whatsapp_text || preparedNoticeBody.value || "";
  await copyTextToClipboard(text);
  setPreparedNoticeStatus("Texto copiado para WhatsApp.", "success");
}

async function copyTextToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
}

async function sendPreparedNoticeEmail() {
  const preview = appState.preparedNoticePreview;
  if (!preview || appState.preparedNoticeSending) return;
  appState.preparedNoticeSending = true;
  sendPreparedNoticeButton.disabled = true;
  sendPreparedNoticeButton.textContent = "Enviando...";
  setPreparedNoticeStatus("Enviando email...", "");
  try {
    const response = await fetch(`/api/licitaciones/${preview.licitacion_id}/prepared-notice/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({
        to: preparedNoticeTo.value.trim(),
        subject: preparedNoticeSubject.value.trim(),
        email_body: preparedNoticeBody.value.trim(),
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.message || result.error || "No se ha podido enviar el email. La licitación se ha guardado correctamente.");
    }
    sendPreparedNoticeButton.textContent = "Email enviado";
    setPreparedNoticeStatus(result.message || "Email enviado correctamente.", "success");
  } catch (error) {
    appState.preparedNoticeSending = false;
    sendPreparedNoticeButton.disabled = false;
    sendPreparedNoticeButton.textContent = "Enviar email";
    setPreparedNoticeStatus(error.message || "No se ha podido enviar el email. La licitación se ha guardado correctamente.", "error");
  }
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

  const notificationEmail = confirmNuriaReviewEmail();
  if (notificationEmail === null) return;

  sendNuriaButton.disabled = true;
  sendNuriaButton.textContent = "Enviando...";
  try {
    const response = await fetch(`/api/dias/${appState.currentDiaId}/enviar-nuria`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ notification_email: notificationEmail }),
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

function setDownloadFolderStatus(message = "", type = "") {
  if (!downloadFolderStatus) return;
  downloadFolderStatus.textContent = message;
  downloadFolderStatus.className = `import-result ${type}`.trim();
}

function closeDownloadFolderDialog() {
  if (downloadFolderDialog?.open) downloadFolderDialog.close();
  appState.downloadFolder = null;
  appState.downloadFolderSubmitting = false;
  setDownloadFolderStatus("");
}

function showDownloadFolderDialog(id, suggestedFolderName, button) {
  appState.downloadFolder = {
    id,
    button,
    originalText: button?.textContent || "Descargar",
  };
  appState.downloadFolderSubmitting = false;
  downloadFolderName.value = suggestedFolderName || "";
  confirmDownloadFolderButton.disabled = false;
  confirmDownloadFolderButton.textContent = "Crear carpeta y descargar";
  setDownloadFolderStatus("");
  downloadFolderDialog.showModal();
  downloadFolderName.focus();
  downloadFolderName.select();
}

async function finishDownload(result) {
  alert(`Descarga completada.\n\nCarpeta:\n${result.carpeta}`);
  await loadItems();
}

async function downloadLicitacion(id, button, options = {}) {
  const originalText = button?.textContent || "Descargar";
  if (button) {
    button.disabled = true;
    button.textContent = "Descargando...";
  }

  try {
    const hasConfirmedName = Object.prototype.hasOwnProperty.call(options, "folderName");
    const body = hasConfirmedName ? JSON.stringify({ folder_name_confirmed: options.folderName }) : undefined;
    const response = await fetch(`/api/licitaciones/${id}/descargar`, {
      method: "POST",
      headers: hasConfirmedName
        ? { "Content-Type": "application/json", ...csrfHeaders() }
        : csrfHeaders(),
      body,
    });
    const result = await response.json().catch(() => ({}));
    if (result.needs_folder_confirmation) {
      showDownloadFolderDialog(id, result.suggested_folder_name, button);
      return;
    }
    if (!response.ok) {
      alert(result.error || result.salida || "No se pudo completar la descarga.");
      return;
    }
    await finishDownload(result);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function confirmDownloadFolder() {
  const pending = appState.downloadFolder;
  if (!pending || appState.downloadFolderSubmitting) return;
  const folderName = downloadFolderName.value.trim();
  if (!folderName) {
    setDownloadFolderStatus("El nombre de carpeta es obligatorio.", "error");
    return;
  }
  appState.downloadFolderSubmitting = true;
  confirmDownloadFolderButton.disabled = true;
  confirmDownloadFolderButton.textContent = "Creando...";
  setDownloadFolderStatus("Creando carpeta y descargando documentación...", "");
  try {
    const response = await fetch(`/api/licitaciones/${pending.id}/descargar`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ folder_name_confirmed: folderName }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.error || result.salida || "No se pudo completar la descarga.");
    }
    closeDownloadFolderDialog();
    await finishDownload(result);
  } catch (error) {
    appState.downloadFolderSubmitting = false;
    confirmDownloadFolderButton.disabled = false;
    confirmDownloadFolderButton.textContent = "Crear carpeta y descargar";
    setDownloadFolderStatus(error.message || "No se pudo completar la descarga.", "error");
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
  licitacionDetailTitle.textContent = "Ficha de licitación";
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
  licitacionDetailTitle.textContent = "Ficha de licitación";
  licitacionDetailContent.innerHTML = renderLicitacionDetailView(item);
  hydrateFullCommentWidgets(licitacionDetailContent);
  loadDocumentTree(id);
  loadAiSummary(id);
}

async function refreshLicitacionDetail(id) {
  const response = await fetch(`/api/licitaciones/${id}`);
  const result = await response.json().catch(() => ({}));
  if (response.ok) {
    appState.cardDetails[id] = { ...(appState.cardDetails[id] || {}), item: result.item };
  }
}

function markerActionMessage(result, fallback) {
  if (result.created) return result.message || "Marcador creado.";
  if (result.exists) return "Ya existe.";
  return result.message || result.error || fallback;
}

function setMarkerActionResult(id, message, type = "", root = document) {
  const scope = root && typeof root.querySelector === "function" ? root : document;
  const target = scope.querySelector(`[data-marker-action-result="${id}"]`);
  if (!target) return;
  target.className = `marker-action-result ${type}`.trim();
  target.textContent = message;
}

async function runLicitacionMarkerAction(id, action, button) {
  if (!isAdmin() || !id || !action) return;
  const endpoint = action === "follow"
    ? `/api/licitaciones/${id}/markers/follow`
    : `/api/licitaciones/${id}/markers/id`;
  const originalText = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = "Creando...";
  }
  try {
    const messageScope = button?.closest(".marker-actions") || document;
    const response = await fetch(endpoint, { method: "POST", headers: csrfHeaders() });
    const result = await response.json().catch(() => ({}));
    const message = markerActionMessage(result, "No se pudo crear el marcador.");
    if (!response.ok) {
      setMarkerActionResult(id, message, "error", messageScope);
      return;
    }
    await refreshLicitacionDetail(id);
    renderBoard();
    const detail = appState.cardDetails[id]?.item;
    if (detail && licitacionDetailDialog.open) {
    licitacionDetailTitle.textContent = "Ficha de licitación";
    licitacionDetailContent.innerHTML = renderLicitacionDetailView(detail);
    hydrateFullCommentWidgets(licitacionDetailContent);
    loadDocumentTree(id, { silent: true });
    loadAiSummary(id);
    setMarkerActionResult(id, message, "success");
  }
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function openLicitacionFolder(id, button) {
  if (!isAdmin() || !id) return;
  const originalText = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = "Abriendo...";
  }
  try {
    const messageScope = button?.closest(".marker-actions") || document;
    const response = await fetch(`/api/licitaciones/${id}/open-folder`, { method: "POST", headers: csrfHeaders() });
    const result = await response.json().catch(() => ({}));
    const message = result.message || result.error || "No se pudo abrir la carpeta.";
    setMarkerActionResult(id, message, response.ok ? "success" : "error", messageScope);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
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
    licitacionDetailTitle.textContent = "Ficha de licitación";
    licitacionDetailContent.innerHTML = renderLicitacionDetailView(detail);
    hydrateFullCommentWidgets(licitacionDetailContent);
    loadDocumentTree(id, { silent: true });
    loadAiSummary(id);
  }
  showPreparedNoticeFromResult(result);
  return true;
}

function renderCaptureResult(message, type = "", details = []) {
  capturePlatformResult.className = `import-result capture-result ${type}`.trim();
  const detailItems = details.filter(Boolean).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  capturePlatformResult.innerHTML = `${escapeHtml(message)}${detailItems ? `<ul>${detailItems}</ul>` : ""}`;
}

function isPlaceDocumentUrl(value) {
  const text = String(value || "").toLowerCase();
  return text.includes("getdocumentbyidservlet") || text.includes("documentidparam=");
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
    const currentValue = String(form.elements[target].value || "").trim();
    const shouldReplaceDocumentProfile =
      field === "enlace_perfil" && isPlaceDocumentUrl(currentValue) && !isPlaceDocumentUrl(value);
    if (currentValue && !shouldReplaceDocumentProfile) {
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
  const defaultCaptureUrl = isPlaceDocumentUrl(profileUrl) ? profileUrl : "";
  const profileUrlForCapture = isPlaceDocumentUrl(profileUrl) ? "" : profileUrl;
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
      body: JSON.stringify({ url, profile_url: profileUrlForCapture || undefined }),
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

mobileMenuButton?.addEventListener("click", toggleSidebar);
mobileMenuClose?.addEventListener("click", closeSidebar);
sidebarOverlay?.addEventListener("click", closeSidebar);
mobileLogoutButton?.addEventListener("click", logout);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSidebar();
});
window.addEventListener("resize", () => {
  if (window.innerWidth > 980) closeSidebar();
});
document.querySelectorAll(".sidebar [data-nav-section]").forEach((button) => {
  button.addEventListener("click", closeSidebar);
});

document.getElementById("days-button").addEventListener("click", showDaysView);
document.getElementById("list-button").addEventListener("click", () => showLicitacionesView({ view: "live" }));
document.getElementById("calendar-button").addEventListener("click", showCalendarView);
document.getElementById("actuaciones-button").addEventListener("click", showActuacionesView);
logoutButton?.addEventListener("click", logout);
aiQueueButton?.addEventListener("click", openAiQueueDialog);
document.getElementById("notifications-button").addEventListener("click", showNotificationsView);
document.getElementById("notifications-menu-button")?.addEventListener("click", showNotificationsView);
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
  dateOrder.value = appState.licitacionesView === "all" ? "desc" : "asc";
  renderLicitacionesTabs();
  loadItems();
});
licitacionesYearFilters.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-licitaciones-year]");
  if (!button) return;
  appState.licitacionesYear = button.dataset.licitacionesYear || "Todos";
  renderLicitacionesDateFilters();
  loadItems();
});
licitacionesMonthFilters.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-licitaciones-month]");
  if (!button) return;
  appState.licitacionesMonth = button.dataset.licitacionesMonth || "Todos";
  renderLicitacionesDateFilters();
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
document.getElementById("close-prepared-notice").addEventListener("click", closePreparedNotice);
document.getElementById("cancel-prepared-notice").addEventListener("click", closePreparedNotice);
sendPreparedNoticeButton.addEventListener("click", sendPreparedNoticeEmail);
copyPreparedNoticeButton.addEventListener("click", copyPreparedNoticeText);
document.getElementById("close-download-folder").addEventListener("click", closeDownloadFolderDialog);
document.getElementById("cancel-download-folder").addEventListener("click", closeDownloadFolderDialog);
confirmDownloadFolderButton.addEventListener("click", confirmDownloadFolder);
downloadFolderName.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    confirmDownloadFolder();
  }
});
document.getElementById("close-ai-file-dialog").addEventListener("click", closeAiFileSelection);
document.getElementById("cancel-ai-file-dialog").addEventListener("click", closeAiFileSelection);
confirmAiFileSelectionButton.addEventListener("click", confirmAiFileSelection);
document.getElementById("ai-select-recommended").addEventListener("click", () => {
  aiFileList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    const file = appState.aiFileSelection?.files?.find((item) => item.id === checkbox.value);
    checkbox.checked = Boolean(file?.selected_by_default && file?.selectable !== false);
  });
  updateAiFileSelectionCount();
});
document.getElementById("ai-clear-selection").addEventListener("click", () => {
  aiFileList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.checked = false;
  });
  updateAiFileSelectionCount();
});
document.getElementById("close-ai-summary-email").addEventListener("click", () => aiSummaryEmailDialog.close());
document.getElementById("cancel-ai-summary-email").addEventListener("click", () => aiSummaryEmailDialog.close());
sendAiSummaryEmailButton.addEventListener("click", sendAiSummaryEmail);
document.getElementById("close-ai-queue").addEventListener("click", closeAiQueueDialog);
refreshAiQueueButton.addEventListener("click", () => loadAiQueue({ forceRender: true }));
aiQueueContent.addEventListener("click", async (event) => {
  const openButton = event.target.closest("button[data-ai-queue-open]");
  if (openButton) {
    closeAiQueueDialog();
    await openLicitacionDetail(openButton.dataset.aiQueueOpen);
    return;
  }
  const cancelButton = event.target.closest("button[data-ai-queue-cancel]");
  if (cancelButton) {
    const status = cancelButton.dataset.aiQueueCancelStatus || "";
    const message = status === "processing"
      ? "¿Cancelar este análisis IA?\n\nEl análisis ya está en curso. Se solicitará la cancelación, pero puede finalizar al terminar la fase actual."
      : "¿Cancelar este análisis IA?";
    if (!confirm(message)) return;
    try {
      await aiQueueAction(cancelButton.dataset.aiQueueCancel, "cancel", cancelButton);
    } catch (error) {
      aiQueueStatus.className = "import-result error";
      aiQueueStatus.textContent = handleAiQueueActionError(error, "No se pudo cancelar el análisis.");
    }
    return;
  }
  const dismissButton = event.target.closest("button[data-ai-queue-dismiss]");
  if (dismissButton) {
    try {
      await aiQueueAction(dismissButton.dataset.aiQueueDismiss, "dismiss", dismissButton);
    } catch (error) {
      aiQueueStatus.className = "import-result error";
      aiQueueStatus.textContent = handleAiQueueActionError(error, "No se pudo ocultar el análisis.");
    }
  }
});
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
document.getElementById("add-actuacion-comment")?.addEventListener("click", addActuacionComment);
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

function activateDetailTab(button) {
  const workspace = button.closest(".licitacion-detail-workspace");
  if (!workspace) return;
  const tab = button.dataset.detailTab || "resumen";
  workspace.querySelectorAll("[data-detail-tab]").forEach((item) => {
    item.classList.toggle("active", item.dataset.detailTab === tab);
  });
  workspace.querySelectorAll("[data-detail-tab-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.detailTabPanel === tab);
  });
  const aiPanel = workspace.querySelector("[data-ai-summary-panel]");
  if (tab === "ai" && aiPanel?.dataset.aiSummaryPanel) {
    loadAiSummary(aiPanel.dataset.aiSummaryPanel, { silent: true });
  }
  const treePanel = workspace.querySelector("[data-document-tree-panel]");
  if (tab === "documentos-seguimiento" && treePanel?.dataset.documentTreePanel) {
    loadDocumentTree(treePanel.dataset.documentTreePanel, { silent: true });
  }
}

function filterDocumentCards(button) {
  const container = button.closest("[data-detail-tab-panel], .card-expanded, .document-card-list")?.parentElement || button.closest(".licitacion-detail-workspace") || document;
  const value = button.dataset.documentFilter || "Todos";
  const filterRoot = button.closest(".document-filter-row");
  filterRoot?.querySelectorAll("[data-document-filter]").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
  container.querySelectorAll("[data-document-category]").forEach((card) => {
    card.hidden = value !== "Todos" && card.dataset.documentCategory !== value;
  });
}

licitacionDetailContent.addEventListener("click", (event) => {
  const tabButton = event.target.closest("button[data-detail-tab]");
  if (tabButton) {
    activateDetailTab(tabButton);
    return;
  }

  const documentFilterButton = event.target.closest("button[data-document-filter]");
  if (documentFilterButton) {
    filterDocumentCards(documentFilterButton);
    return;
  }

  const copyButton = event.target.closest("button[data-copy-text]");
  if (copyButton) {
    copyTextToClipboard(copyButton.dataset.copyText || "");
    copyButton.textContent = "Ruta copiada";
    window.setTimeout(() => {
      copyButton.textContent = "Copiar ruta";
    }, 1800);
    return;
  }

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

  const markerActionButton = event.target.closest("button[data-marker-action]");
  if (markerActionButton) {
    runLicitacionMarkerAction(
      markerActionButton.dataset.markerLicitacionId,
      markerActionButton.dataset.markerAction,
      markerActionButton,
    );
    return;
  }

  const openFolderButton = event.target.closest("button[data-open-licitacion-folder]");
  if (openFolderButton) {
    openLicitacionFolder(openFolderButton.dataset.openLicitacionFolder, openFolderButton);
    return;
  }

  const aiRefreshButton = event.target.closest("button[data-ai-refresh]");
  if (aiRefreshButton) {
    loadAiSummary(aiRefreshButton.dataset.aiRefresh);
    loadAiQueue();
    return;
  }

  const openAiQueueButton = event.target.closest("button[data-open-ai-queue]");
  if (openAiQueueButton) {
    openAiQueueDialog();
    return;
  }

  const aiEmailButton = event.target.closest("button[data-ai-email]");
  if (aiEmailButton) {
    openAiSummaryEmail(aiEmailButton.dataset.aiEmail);
    return;
  }

  const aiDeleteButton = event.target.closest("button[data-ai-delete]");
  if (aiDeleteButton) {
    deleteAiSummary(aiDeleteButton.dataset.aiDelete);
    return;
  }

  const aiGenerateButton = event.target.closest("button[data-ai-generate]");
  if (aiGenerateButton) {
    generateAiSummary(aiGenerateButton.dataset.aiGenerate, aiGenerateButton, false);
    return;
  }

  const aiRegenerateButton = event.target.closest("button[data-ai-regenerate]");
  if (aiRegenerateButton) {
    generateAiSummary(aiRegenerateButton.dataset.aiRegenerate, aiRegenerateButton, true);
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
  const documentFilterButton = event.target.closest("button[data-document-filter]");
  if (documentFilterButton) {
    filterDocumentCards(documentFilterButton);
    return;
  }

  const copyButton = event.target.closest("button[data-copy-text]");
  if (copyButton) {
    copyTextToClipboard(copyButton.dataset.copyText || "");
    copyButton.textContent = "Ruta copiada";
    window.setTimeout(() => {
      copyButton.textContent = "Copiar ruta";
    }, 1800);
    return;
  }

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

  const markerActionButton = event.target.closest("button[data-marker-action]");
  if (markerActionButton) {
    runLicitacionMarkerAction(
      markerActionButton.dataset.markerLicitacionId,
      markerActionButton.dataset.markerAction,
      markerActionButton,
    );
    return;
  }

  const openFolderButton = event.target.closest("button[data-open-licitacion-folder]");
  if (openFolderButton) {
    openLicitacionFolder(openFolderButton.dataset.openLicitacionFolder, openFolderButton);
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
  const openDetailButton = event.target.closest("button[data-open-licitacion-detail]");
  if (openDetailButton) {
    openLicitacionDetail(openDetailButton.dataset.openLicitacionDetail);
    return;
  }
  const editButton = event.target.closest("button[data-edit-id]");
  if (editButton) {
    openEditEditor(editButton.dataset.editId);
    return;
  }
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
  const openDetailButton = event.target.closest("button[data-open-licitacion-detail]");
  if (openDetailButton) {
    openLicitacionDetail(openDetailButton.dataset.openLicitacionDetail);
    return;
  }
  const editButton = event.target.closest("button[data-edit-id]");
  if (editButton) {
    openEditEditor(editButton.dataset.editId);
    return;
  }
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
  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    alert(result.error || "No se pudo guardar la licitación.");
    return;
  }

  form.reset();
  editor.close();
  await loadDias();
  if (appState.lastSection === "calendar") {
    await loadCalendarItems();
    showPreparedNoticeFromResult(result);
    return;
  }
  showLicitacionesView({ diaId: appState.currentDiaId, title: appState.currentDiaTitle });
  showPreparedNoticeFromResult(result);
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

loadMe().then(() => {
  showInitialView();
  loadAiQueue();
  startAiQueuePolling(15000);
});

