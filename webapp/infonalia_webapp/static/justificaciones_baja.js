/* Frontend aislado para justificaciones de ofertas anormalmente bajas. */
(function justificacionesBajaFeature(global) {
  "use strict";

  const FEATURE_NAME = "justificaciones-baja";
  const SECTION_ID = "justificaciones-baja-section";
  const ROOT_ID = "justificaciones-baja-root";
  const DEFAULT_API_BASE = "/api/justificaciones-baja";
  const LIVE_SAVE_DELAY = 550;

  const STATUS_LABELS = {
    borrador: "Borrador",
    enviado_cliente: "Enviado al cliente",
    final: "Final",
  };

  const SUMMARY_ROWS = [
    ["declared_lot_offer", "Oferta del lote"],
    ["prorated_product_cost", "Coste de productos"],
    ["gross_margin", "Margen bruto"],
    ["gross_margin_percentage", "Margen bruto %"],
    ["allocated_transport", "Transporte imputado"],
    ["general_expenses", "Gastos generales"],
    ["indirect_costs", "Costes indirectos"],
    ["total_cost", "Coste total"],
    ["profit", "Beneficio"],
    ["profit_percentage", "Beneficio %"],
    ["visual_product_residual", "Residual visible"],
  ];

  const REQUIRED_NUMERIC_FIELDS = [
    ["declared_lot_offer", "importe ofertado", "decimal"],
    ["operational_weeks", "semanas operativas", "integer"],
    ["weekly_deliveries", "entregas semanales", "integer"],
    ["contract_stops", "puntos o paradas", "integer"],
    ["circular_kilometres", "kilómetros circulares", "decimal"],
    ["effective_decimal_hours", "horas decimales", "decimal"],
    ["kilometre_rate", "tarifa por kilómetro", "decimal"],
    ["hourly_rate", "tarifa por hora", "decimal"],
    ["shared_orders", "pedidos compartidos", "integer"],
    ["general_expense_base", "base de gastos generales", "decimal"],
    ["general_expense_percentage", "porcentaje de gastos generales", "decimal"],
    ["minimum_percentage", "horquilla mínima", "integer"],
    ["maximum_percentage", "horquilla máxima", "integer"],
  ];

  const state = {
    initialized: false,
    bridge: {},
    apiBase: DEFAULT_API_BASE,
    root: null,
    section: null,
    list: [],
    clients: [],
    current: null,
    permissions: {},
    selectedLineIds: new Set(),
    dirty: false,
    conflict: false,
    busy: false,
    liveSaveTimer: null,
    requestSerial: 0,
    importMode: "xlsx",
    importPreview: null,
    importPreviewSerial: 0,
    importPreviewSignature: "",
    importPreviewPending: false,
    clientLoadSerial: 0,
    clientLoadController: null,
    clientLoading: false,
    clientSnapshotClientId: "",
    clientSnapshotValid: false,
    navigationSerial: 0,
    navigationController: null,
    returnLicitacionId: "",
    listLicitacionId: "",
  };

  class HttpError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.name = "HttpError";
      this.status = status;
      this.payload = payload || {};
    }
  }

  class ConflictError extends HttpError {
    constructor(message, payload) {
      super(message, 409, payload);
      this.name = "ConflictError";
    }
  }

  function apiPaths() {
    const base = state.apiBase;
    return {
      collection: () => base,
      detail: (id) => `${base}/${encodeURIComponent(id)}`,
      generateCosts: (id) => `${base}/${encodeURIComponent(id)}/costes/generar`,
      recalculateCosts: (id) => `${base}/${encodeURIComponent(id)}/costes/recalcular`,
      manualCost: (id) => `${base}/${encodeURIComponent(id)}/costes/manual`,
      removeManualCost: (id) => `${base}/${encodeURIComponent(id)}/costes/retirar-manual`,
      productLock: (id) => `${base}/${encodeURIComponent(id)}/productos/bloqueo`,
      routeImage: (id) => `${base}/${encodeURIComponent(id)}/imagen-ruta`,
      freeze: (id) => `${base}/${encodeURIComponent(id)}/congelar`,
      status: (id) => `${base}/${encodeURIComponent(id)}/estado`,
      preview: () => `${base}/preview`,
      versionDocuments: (id, version) => `${base}/${encodeURIComponent(id)}/versiones/${encodeURIComponent(version)}/documentos`,
      xlsxPreview: () => `${base}/importar-xlsx/preview`,
      pastePreview: () => `${base}/pegar/preview`,
      documentDownload: (documentId) => `${base}/documentos/${encodeURIComponent(documentId)}/download`,
      licitacion: (id) => `/api/licitaciones/${encodeURIComponent(id)}`,
      clients: (query = "") => `/api/clientes${query ? `?q=${encodeURIComponent(query)}` : ""}`,
      client: (id) => `/api/clientes/${encodeURIComponent(id)}`,
    };
  }

  function csrfHeaders() {
    if (typeof state.bridge.csrfHeaders === "function") {
      return { ...state.bridge.csrfHeaders() };
    }
    if (typeof state.bridge.getCsrfToken === "function") {
      const token = state.bridge.getCsrfToken();
      return token ? { "X-CSRF-Token": token } : {};
    }
    return {};
  }

  async function request(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    const headers = { ...(options.headers || {}) };
    let body = options.body;
    if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }
    if (!new Set(["GET", "HEAD", "OPTIONS"]).has(method)) {
      Object.assign(headers, csrfHeaders());
    }
    const response = await fetch(path, {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json().catch(() => ({}))
      : { message: await response.text().catch(() => "") };
    if (response.status === 401) {
      global.location.href = "/login";
      throw new HttpError("La sesión ha caducado.", 401, payload);
    }
    const message = payload.error || payload.message || `La operación no pudo completarse (${response.status}).`;
    if (response.status === 409) throw new ConflictError(message, payload);
    if (!response.ok) throw new HttpError(message, response.status, payload);
    return payload;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function displayDateTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
  }

  function displayBytes(value) {
    const bytes = Number(value || 0);
    if (bytes >= 1048576) return `${(bytes / 1048576).toLocaleString("es-ES", { maximumFractionDigits: 1 })} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toLocaleString("es-ES", { maximumFractionDigits: 0 })} KB`;
    return `${bytes} B`;
  }

  function joinedAddress(client) {
    return [client.domicilio_fiscal, client.codigo_postal, client.municipio, client.provincia]
      .map((part) => String(part || "").trim())
      .filter(Boolean)
      .join(", ");
  }

  function numericTextIsValid(value, kind) {
    const text = String(value || "").trim();
    if (!text) return false;
    if (kind === "integer") return /^\d+$/.test(text);
    return /^[+-]?(?:\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?|[.,]\d+)$/.test(text);
  }

  function getIn(object, path, fallback = "") {
    let current = object;
    for (const key of String(path).split(".")) {
      if (current === null || current === undefined || typeof current !== "object") return fallback;
      current = current[key];
    }
    return current === null || current === undefined ? fallback : current;
  }

  function firstValue(object, paths, fallback = "") {
    for (const path of paths) {
      const value = getIn(object, path, undefined);
      if (value !== undefined && value !== null && value !== "") return value;
    }
    return fallback;
  }

  function normalizeItem(payload) {
    const item = payload?.item || payload || {};
    const draft = item.draft && typeof item.draft === "object" ? item.draft : {};
    return {
      ...item,
      draft,
      products: Array.isArray(draft.products) ? draft.products : [],
      calculation: item.calculation || draft.calculation || null,
      issues: item.issues || item.calculation?.warnings || [],
      versions: Array.isArray(item.versions) ? item.versions : [],
      documents: Array.isArray(item.documents) ? item.documents : [],
      history: Array.isArray(item.history) ? item.history : [],
      revision: Number(item.revision || 0),
    };
  }

  function currentDraft() {
    return state.current?.draft || {};
  }

  function isAllowed(name, fallback = true) {
    if (!state.permissions || Object.keys(state.permissions).length === 0) return fallback;
    if (Object.prototype.hasOwnProperty.call(state.permissions, name)) return Boolean(state.permissions[name]);
    const aliases = {
      can_view: "view",
      can_download: "download",
      can_create: "create",
      can_edit: "edit",
      can_generate_costs: "generate_costs",
      can_freeze: "freeze",
      can_generate_documents: "generate_documents",
      can_change_status: "change_state",
    };
    const alias = aliases[name];
    if (alias && Object.prototype.hasOwnProperty.call(state.permissions, alias)) {
      return Boolean(state.permissions[alias]);
    }
    return fallback;
  }

  function requirePermission(name, message = "Tu perfil dispone de acceso de solo lectura.") {
    if (isAllowed(name)) return true;
    setResult("editor", message, "warning");
    return false;
  }

  function defaultPermissions() {
    const user = typeof state.bridge.getCurrentUser === "function"
      ? state.bridge.getCurrentUser()
      : state.bridge.currentUser || null;
    const editable = user?.role ? user.role === "admin" : true;
    return {
      view: true,
      download: true,
      create: editable,
      edit: editable,
      generate_costs: editable,
      freeze: editable,
      generate_documents: editable,
      change_state: editable,
    };
  }

  function makeManualLineId() {
    if (global.crypto?.randomUUID) return `MAN-${global.crypto.randomUUID()}`;
    const bytes = new Uint8Array(12);
    global.crypto?.getRandomValues?.(bytes);
    return `MAN-${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}-${Date.now()}`;
  }

  function ensureSection() {
    let section = document.getElementById(SECTION_ID);
    if (!section) {
      section = document.createElement("section");
      section.id = SECTION_ID;
      section.hidden = true;
      const shell = document.querySelector("main.shell") || document.querySelector("main") || document.body;
      shell.append(section);
    }
    let root = section.querySelector(`#${ROOT_ID}`);
    if (!root) {
      root = document.createElement("div");
      root.id = ROOT_ID;
      section.append(root);
    }
    state.section = section;
    state.root = root;
    root.innerHTML = shellMarkup();
  }

  function shellMarkup() {
    return `
      <div class="jb-screen" data-jb-screen>
        <div class="jb-list-view" data-jb-list-view>
          <div class="section-head">
            <div class="section-title-block">
              <p class="eyebrow">Ofertas anormalmente bajas</p>
              <h2>Justificaciones de baja</h2>
            </div>
            <div class="section-actions">
              <button type="button" class="ghost" data-jb-refresh-list>Actualizar</button>
            </div>
          </div>
          <section class="toolbar jb-list-toolbar" aria-label="Filtros de justificaciones">
            <label>Buscar<input type="search" data-jb-list-search placeholder="Expediente, lote o cliente"></label>
            <label>Estado
              <select data-jb-list-status>
                <option value="">Todos</option>
                <option value="borrador">Borrador</option>
                <option value="enviado_cliente">Enviado al cliente</option>
                <option value="final">Final</option>
              </select>
            </label>
          </section>
          <div class="import-result" data-jb-list-result role="status" aria-live="polite"></div>
          <section class="jb-list" data-jb-list><div class="empty">Cargando justificaciones…</div></section>
        </div>

        <div class="jb-editor-view" data-jb-editor-view hidden>
          <div class="jb-editor-header">
            <div>
              <p class="eyebrow">Lote independiente</p>
              <h2 data-jb-editor-title>Nueva justificación</h2>
              <div class="jb-editor-meta" data-jb-editor-meta></div>
            </div>
            <div class="section-actions">
              <button type="button" class="ghost" data-jb-back-list>Volver al listado</button>
              <button type="button" class="primary" data-jb-save>Guardar borrador</button>
            </div>
          </div>
          <div class="jb-unsaved" data-jb-unsaved hidden>Hay cambios sin guardar.</div>
          <div class="jb-conflict" data-jb-conflict hidden>
            <strong>El borrador cambió en otra pestaña.</strong>
            <span>Los cambios locales no se han sobrescrito.</span>
            <button type="button" data-jb-reload-conflict>Recargar versión del servidor</button>
          </div>
          <div class="import-result" data-jb-editor-result role="status" aria-live="polite"></div>
          <div class="jb-editor-layout">
            <form class="jb-editor-form" data-jb-form novalidate>
              ${editorSectionsMarkup()}
            </form>
            <aside class="jb-summary panel-sticky" data-jb-summary aria-label="Resumen económico">
              <h3>Resultado económico</h3>
              <div class="jb-summary-empty">Guarda el borrador para obtener el cálculo del servidor.</div>
            </aside>
          </div>
        </div>

        ${importDialogMarkup()}
      </div>
    `;
  }

  function editorSectionsMarkup() {
    return `
      <section class="jb-step" data-jb-step="identificacion">
        <header><span>1</span><div><h3>Identificación y cliente</h3><p>Los datos del cliente se copian a esta justificación y después pueden editarse.</p></div></header>
        <div class="jb-field-grid">
          <label>Cliente<select name="cliente_id" data-jb-client required><option value="">Selecciona cliente</option></select></label>
          <label>Expediente<input name="expediente" required></label>
          <label class="jb-span-2">Organismo<input name="organismo"></label>
          <label class="jb-span-2">Objeto<textarea name="objeto" rows="2"></textarea></label>
          <label>Número de lote<input name="lote_numero" required></label>
          <label>Nombre del lote<input name="lote_nombre"></label>
          <label>Importe ofertado sin IVA<input name="declared_lot_offer" inputmode="decimal" data-live-economic required></label>
        </div>
        <details class="jb-client-snapshot">
          <summary>Datos del cliente y representante</summary>
          <div class="jb-field-grid">
            <label class="jb-span-2">Razón social<input name="cliente_razon_social"></label>
            <label>NIF/CIF<input name="cliente_nif"></label>
            <label>Teléfono<input name="cliente_telefono"></label>
            <label class="jb-span-2">Domicilio<input name="cliente_domicilio"></label>
            <label>Email<input name="cliente_email" type="email"></label>
            <label>Representante<input name="representante_nombre"></label>
            <label>DNI/NIF representante<input name="representante_nif"></label>
            <label>Cargo<input name="representante_cargo"></label>
          </div>
        </details>
      </section>

      <section class="jb-step" data-jb-step="contrato">
        <header><span>2</span><div><h3>Contrato y periodicidad</h3><p>Datos confirmados del lote que condicionan el transporte.</p></div></header>
        <div class="jb-field-grid">
          <label class="jb-span-2">Duración descriptiva<input name="duracion_descriptiva" placeholder="Por ejemplo: doce meses"></label>
          <label>Semanas operativas<input name="operational_weeks" inputmode="numeric" data-live-economic required></label>
          <label>Entregas semanales<input name="weekly_deliveries" inputmode="numeric" data-live-economic required></label>
          <label>Meses descriptivos<input name="descriptive_months" inputmode="numeric"></label>
          <label>Puntos o paradas<input name="contract_stops" inputmode="numeric" data-live-economic required></label>
        </div>
      </section>

      <section class="jb-step" data-jb-step="transporte">
        <header><span>3</span><div><h3>Transporte</h3><p>Ruta circular y datos confirmados del Observatorio.</p></div></header>
        <div class="jb-field-grid">
          <label>Kilómetros circulares<input name="circular_kilometres" inputmode="decimal" data-live-economic required></label>
          <label>Horas decimales<input name="effective_decimal_hours" inputmode="decimal" data-live-economic required></label>
          <label class="jb-span-2">Duración humana de la ruta<input name="route_duration_text" placeholder="Por ejemplo: 2 horas y 40 minutos"></label>
          <label>Tarifa por kilómetro<input name="kilometre_rate" inputmode="decimal" data-live-economic required></label>
          <label>Tarifa por hora<input name="hourly_rate" inputmode="decimal" data-live-economic required></label>
          <label>Pedidos compartidos<input name="shared_orders" inputmode="numeric" data-live-economic required></label>
          <label>Tipo de vehículo<input name="vehicle_type"></label>
          <label>Fecha del Observatorio<input name="observatory_date" type="date"></label>
          <label class="jb-span-2">URL del Observatorio<input name="observatory_url" type="url"></label>
          <label>Base de gastos generales<input name="general_expense_base" inputmode="decimal" data-live-economic required></label>
          <label>Gastos generales (0,10 = 10 %)<input name="general_expense_percentage" inputmode="decimal" data-live-economic required></label>
          <label>Costes indirectos opcionales<input name="indirect_costs" inputmode="decimal" data-live-economic></label>
        </div>
      </section>

      <section class="jb-step" data-jb-step="productos">
        <header><span>4</span><div><h3>Productos</h3><p>Cada línea conserva un identificador estable, aunque existan nombres duplicados.</p></div></header>
        <div class="jb-product-toolbar">
          <button type="button" data-jb-add-product>Añadir producto</button>
          <button type="button" data-jb-open-xlsx>Importar Excel</button>
          <button type="button" data-jb-open-paste>Pegar tabla</button>
          <span data-jb-selection-count>0 seleccionados</span>
        </div>
        <div class="jb-product-table-wrap">
          <table class="jb-product-table">
            <thead><tr>
              <th><input type="checkbox" data-jb-select-all aria-label="Seleccionar todos"></th>
              <th>Producto</th><th>Características</th><th>Cantidad</th><th>Precio ofertado</th><th>Importe</th>
              <th>Coste efectivo</th><th>Coste línea</th><th>Margen</th><th>Estado</th><th>Acciones</th>
            </tr></thead>
            <tbody data-jb-products><tr><td colspan="11" class="empty">Añade o importa productos.</td></tr></tbody>
          </table>
        </div>
      </section>

      <section class="jb-step" data-jb-step="costes">
        <header><span>5</span><div><h3>Generación y ajuste de costes</h3><p>La generación es siempre explícita y los productos bloqueados no cambian.</p></div></header>
        <div class="jb-cost-controls">
          <label>Horquilla mínima %<input name="minimum_percentage" inputmode="numeric" required></label>
          <label>Horquilla máxima %<input name="maximum_percentage" inputmode="numeric" required></label>
          <button type="button" class="primary" data-jb-generate-costs>Generar costes</button>
          <button type="button" data-jb-recalculate-selected>Recalcular seleccionados</button>
          <button type="button" data-jb-recalculate-unlocked>Recalcular no bloqueados</button>
          <button type="button" data-jb-lock-selected>Bloquear seleccionados</button>
          <button type="button" data-jb-unlock-selected>Desbloquear seleccionados</button>
        </div>
      </section>

      <section class="jb-step" data-jb-step="narrativa">
        <header><span>6</span><div><h3>Narrativa e imagen</h3><p>Textos confirmados por la asesoría y captura opcional de la ruta.</p></div></header>
        <div class="jb-field-grid">
          <label class="jb-span-2">Exposición y antecedentes<textarea name="exposition" rows="4"></textarea></label>
          <label class="jb-span-2">Argumentos empresariales<textarea name="argumentos" rows="7"></textarea></label>
          <label class="jb-span-2">Texto de adquisición de productos<textarea name="acquisition_text" rows="4"></textarea></label>
          <label class="jb-span-2">Texto de transporte<textarea name="texto_transporte" rows="4"></textarea></label>
          <label class="jb-span-2">Texto de estructura y gastos<textarea name="structure_text" rows="4"></textarea></label>
          <label class="jb-span-2">Conclusión<textarea name="conclusion" rows="4"></textarea></label>
          <label>Lugar<input name="lugar"></label>
          <label>Fecha del informe<input name="fecha_informe" type="date"></label>
          <label>Firmante<input name="firmante"></label>
          <label>Cargo del firmante<input name="firmante_cargo"></label>
        </div>
        <div class="jb-route-image">
          <label>Captura de la ruta (PNG o JPEG)<input type="file" accept="image/png,image/jpeg" data-jb-route-image></label>
          <button type="button" data-jb-upload-route-image>Adjuntar imagen</button>
          <label class="jb-route-existing">Imagen existente en la carpeta de la licitación
            <input data-jb-route-relative-path placeholder="Ej.: Rutas/ruta_lote_1.png" autocomplete="off">
          </label>
          <button type="button" data-jb-attach-existing-route-image>Seleccionar imagen existente</button>
          <div data-jb-route-image-state>La imagen es opcional.</div>
        </div>
      </section>

      <section class="jb-step" data-jb-step="versiones">
        <header><span>7</span><div><h3>Versiones y documentos</h3><p>Word y Excel siempre parten del mismo snapshot congelado.</p></div></header>
        <div class="jb-version-actions">
          <button type="button" class="primary" data-jb-freeze>Congelar versión económica</button>
          <label>Estado
            <select data-jb-status>
              <option value="borrador">Borrador</option>
              <option value="enviado_cliente">Enviado al cliente</option>
              <option value="final">Final</option>
            </select>
          </label>
          <button type="button" data-jb-change-status>Actualizar estado</button>
        </div>
        <div class="jb-versions" data-jb-versions><div class="empty">Aún no hay versiones congeladas.</div></div>
        <div class="jb-history" data-jb-history></div>
      </section>
    `;
  }

  function importDialogMarkup() {
    return `
      <dialog class="wide-dialog jb-import-dialog" data-jb-import-dialog>
        <div class="dialog-head">
          <div><p class="eyebrow">Productos</p><h2 data-jb-import-title>Importar productos</h2></div>
          <button type="button" class="icon-button" data-jb-close-import aria-label="Cerrar">×</button>
        </div>
        <div data-jb-xlsx-fields>
          <label>Fichero XLSX<input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" data-jb-xlsx-file></label>
          <label>Hoja<select data-jb-import-sheet><option value="">Primera hoja</option></select></label>
        </div>
        <div data-jb-paste-fields hidden>
          <label>Filas copiadas desde Excel<textarea rows="9" data-jb-paste-text placeholder="Producto\tCaracterísticas\tCantidad\tPrecio\tImporte"></textarea></label>
        </div>
        <fieldset class="jb-import-mapping">
          <legend>Fila inicial y columnas</legend>
          <label>Fila inicial<input type="number" min="1" value="2" data-jb-import-start-row></label>
          <label>Producto<input value="A" data-jb-map="name"></label>
          <label>Características<input value="B" data-jb-map="characteristics"></label>
          <label>Cantidad<input value="C" data-jb-map="quantity"></label>
          <label>Precio ofertado<input value="D" data-jb-map="offered_unit_price"></label>
          <label>Importe opcional<input value="E" data-jb-map="offered_amount"></label>
        </fieldset>
        <div class="dialog-actions">
          <button type="button" data-jb-preview-import>Previsualizar</button>
          <button type="button" class="primary" data-jb-confirm-import disabled>Incorporar productos</button>
        </div>
        <div class="import-result" data-jb-import-result role="status" aria-live="polite"></div>
        <div class="jb-import-preview" data-jb-import-preview></div>
      </dialog>
    `;
  }

  function setResult(targetName, message = "", tone = "") {
    const target = state.root?.querySelector(`[data-jb-${targetName}-result]`);
    if (!target) return;
    target.className = `import-result ${tone}`.trim();
    target.textContent = message;
  }

  function setBusy(value, message = "") {
    state.busy = Boolean(value);
    state.root?.querySelectorAll("button").forEach((button) => {
      if (!button.matches("[data-jb-close-import]")) button.disabled = state.busy || button.dataset.jbPermissionDisabled === "1";
    });
    if (state.root) applyPermissions();
    if (message) setResult("editor", message, "");
  }

  function setDirty(value) {
    state.dirty = Boolean(value);
    const banner = state.root?.querySelector("[data-jb-unsaved]");
    if (banner) banner.hidden = !state.dirty;
  }

  function invalidateLivePreview() {
    global.clearTimeout(state.liveSaveTimer);
    state.liveSaveTimer = null;
    state.requestSerial += 1;
  }

  function handleConflict(error) {
    state.conflict = true;
    const banner = state.root?.querySelector("[data-jb-conflict]");
    if (banner) banner.hidden = false;
    setResult("editor", error.message, "error");
  }

  function navigateToFeature(title = "Justificaciones de baja", kicker = "Licitaciones") {
    state.section.hidden = false;
    if (typeof state.bridge.navigate === "function") {
      state.bridge.navigate(FEATURE_NAME, title, kicker);
    } else {
      document.querySelectorAll("main.shell > section[id$='-section']").forEach((section) => {
        section.hidden = section !== state.section;
      });
      document.querySelectorAll("[data-nav-section]").forEach((button) => {
        button.classList.toggle("active", button.dataset.navSection === FEATURE_NAME);
      });
      document.body.dataset.activeSection = FEATURE_NAME;
    }
  }

  function beginNavigationLoad() {
    state.navigationController?.abort();
    const controller = new AbortController();
    const serial = ++state.navigationSerial;
    state.navigationController = controller;
    return { controller, serial };
  }

  function cancelNavigationLoad() {
    state.navigationSerial += 1;
    state.navigationController?.abort();
    state.navigationController = null;
  }

  function navigationLoadIsCurrent(serial, controller) {
    return serial === state.navigationSerial && controller === state.navigationController;
  }

  function resumeDirtyEditor() {
    if (!state.current) return false;
    navigateToFeature(
      state.current.id ? "Justificación de baja" : "Nueva justificación de baja",
      "Licitaciones",
    );
    state.root.querySelector("[data-jb-list-view]").hidden = true;
    state.root.querySelector("[data-jb-editor-view]").hidden = false;
    return true;
  }

  function confirmDiscardForNavigation(message) {
    if (!state.dirty) return true;
    if (!global.confirm(message)) {
      resumeDirtyEditor();
      return false;
    }
    setDirty(false);
    return true;
  }

  function showListView(options = {}) {
    if (!confirmDiscardForNavigation("Hay cambios sin guardar. ¿Descartarlos y volver al listado?")) return false;
    invalidateLivePreview();
    cancelClientSnapshotLoad();
    cancelNavigationLoad();
    invalidateImportPreview();
    setDirty(false);
    state.current = null;
    state.conflict = false;
    state.selectedLineIds.clear();
    state.clientSnapshotClientId = "";
    state.clientSnapshotValid = false;
    const requested = typeof options === "object" ? options.licitacionId : options;
    state.listLicitacionId = requested ? String(requested) : "";
    navigateToFeature();
    state.root.querySelector("[data-jb-list-view]").hidden = false;
    state.root.querySelector("[data-jb-editor-view]").hidden = true;
    loadList();
  }

  async function loadList() {
    const { controller, serial } = beginNavigationLoad();
    const listNode = state.root.querySelector("[data-jb-list]");
    const status = state.root.querySelector("[data-jb-list-status]")?.value || "";
    const params = new URLSearchParams();
    if (status) params.set("estado", status);
    if (state.listLicitacionId) params.set("licitacion_id", state.listLicitacionId);
    listNode.innerHTML = `<div class="empty">Cargando justificaciones…</div>`;
    try {
      const payload = await request(`${apiPaths().collection()}${params.size ? `?${params}` : ""}`, { signal: controller.signal });
      if (!navigationLoadIsCurrent(serial, controller)) return;
      state.list = payload.items || [];
      state.permissions = payload.permissions || state.permissions;
      renderList();
      setResult("list", "");
    } catch (error) {
      if (error?.name === "AbortError" || !navigationLoadIsCurrent(serial, controller)) return;
      listNode.innerHTML = `<div class="empty">No se pudo cargar el listado.</div>`;
      setResult("list", error.message, "error");
    } finally {
      if (navigationLoadIsCurrent(serial, controller)) state.navigationController = null;
    }
  }

  function renderList() {
    const node = state.root.querySelector("[data-jb-list]");
    const query = state.root.querySelector("[data-jb-list-search]")?.value.trim().toLocaleLowerCase("es") || "";
    const items = query ? state.list.filter((item) => [item.expediente, item.lote_numero, item.lote_nombre, item.cliente_razon_social, item.cliente_nombre]
      .some((value) => String(value || "").toLocaleLowerCase("es").includes(query))) : state.list;
    if (!items.length) {
      node.innerHTML = `<div class="empty">No hay justificaciones con estos filtros.</div>`;
      return;
    }
    node.innerHTML = items.map((item) => `
      <article class="jb-list-card">
        <div class="jb-list-card-main">
          <div class="jb-list-card-head">
            <span class="jb-status jb-status-${escapeHtml(item.estado || "borrador")}">${escapeHtml(STATUS_LABELS[item.estado] || item.estado || "Borrador")}</span>
            <strong>${escapeHtml(item.expediente || "Sin expediente")}</strong>
          </div>
          <h3>Lote ${escapeHtml(item.lote_numero || "—")}${item.lote_nombre ? ` · ${escapeHtml(item.lote_nombre)}` : ""}</h3>
          <p>${escapeHtml(item.cliente_razon_social || item.cliente_nombre || "Sin cliente")}</p>
          <dl>
            <div><dt>Beneficio</dt><dd>${escapeHtml(item.profit_display || "Pendiente")}</dd></div>
            <div><dt>Versión</dt><dd>${escapeHtml(item.latest_version || 0)}</dd></div>
            <div><dt>Documentos</dt><dd>${escapeHtml(item.document_count || 0)}</dd></div>
            <div><dt>Modificada</dt><dd>${escapeHtml(displayDateTime(item.updated_at))}</dd></div>
          </dl>
        </div>
        <div class="card-actions"><button type="button" data-jb-open="${escapeHtml(item.id)}">Abrir</button></div>
      </article>
    `).join("");
  }

  async function openForLicitacion(licitacionId) {
    if (!state.initialized) return;
    if (!confirmDiscardForNavigation("Hay cambios sin guardar. ¿Descartarlos y crear otra justificación?")) return;
    invalidateLivePreview();
    cancelClientSnapshotLoad();
    state.returnLicitacionId = String(licitacionId || "");
    navigateToFeature("Nueva justificación de baja", "Licitaciones");
    showEditorLoading("Cargando datos de la licitación…");
    const { controller, serial } = beginNavigationLoad();
    try {
      const [licPayload, clientsPayload] = await Promise.all([
        request(apiPaths().licitacion(licitacionId), { signal: controller.signal }),
        request(apiPaths().clients(), { signal: controller.signal }),
      ]);
      if (!navigationLoadIsCurrent(serial, controller)) return;
      const licitacion = licPayload.item || {};
      state.clients = clientsPayload.items || [];
      state.current = normalizeItem({
        id: null,
        licitacion_id: Number(licitacionId),
        expediente: licitacion.expediente || "",
        estado: "borrador",
        revision: 0,
        draft: {
          schema_version: "1",
          identification: {
            expediente: licitacion.expediente || "",
            organismo: licitacion.organismo || "",
            objeto: licitacion.objeto || "",
            lot_number: "1",
            lot_name: "",
            duration_description: "",
            place: "",
            date_text: "",
          },
          client: {
            client_id: null,
            name: "",
            nif: "",
            address: "",
            phone: "",
            email: "",
            representative: "",
            representative_dni: "",
            role: "",
            signatory: "",
          },
          products: [],
          transport: {
            operational_weeks: 0,
            weekly_deliveries: 0,
            circular_kilometres: "0",
            effective_decimal_hours: "0",
            kilometre_rate: "0",
            hourly_rate: "0",
            contract_stops: 1,
            shared_orders: 15,
            descriptive_months: null,
            route_duration_text: "",
          },
          financial: {
            declared_lot_offer: "",
            general_expense_base: "",
            general_expense_percentage: "0.10",
            indirect_costs: null,
          },
          cost_range: { minimum_percentage: 40, maximum_percentage: 47 },
          transport_document: {
            observatory: "Observatorio de Costes del Transporte de Mercancías por Carretera",
            observatory_date: "",
            observatory_url: "",
            vehicle: "Vehículo rígido de 2 ejes de distribución",
          },
          narrative: {
            subject: "Justificación de oferta anormalmente baja",
            exposition: "",
            arguments: [],
            acquisition_text: "",
            transport_text: "",
            structure_text: "",
            conclusion: "",
            estimated_draft_notice: "BORRADOR ESTIMATIVO PENDIENTE DE VALIDACIÓN DEL CLIENTE",
            confidentiality_text: "Documento confidencial para uso exclusivo en el procedimiento indicado.",
            pending_validation_fields: ["costes unitarios", "medios y circunstancias empresariales"],
          },
          route_image: null,
          accepted_warning_codes: [],
          source: { defaults_are_proposals: true, product_import: null },
        },
      });
      state.permissions = clientsPayload.permissions || defaultPermissions();
      state.clientSnapshotClientId = "";
      state.clientSnapshotValid = false;
      renderEditor();
      setDirty(false);
    } catch (error) {
      if (error?.name === "AbortError" || !navigationLoadIsCurrent(serial, controller)) return;
      showEditorLoading(`No se pudo preparar la justificación: ${error.message}`, true);
    } finally {
      if (navigationLoadIsCurrent(serial, controller)) state.navigationController = null;
    }
  }

  async function openExisting(id) {
    if (!state.initialized) return;
    if (!state.conflict && !confirmDiscardForNavigation("Hay cambios sin guardar. ¿Descartarlos y abrir otra justificación?")) return;
    if (state.conflict) setDirty(false);
    invalidateLivePreview();
    cancelClientSnapshotLoad();
    navigateToFeature("Justificación de baja", "Licitaciones");
    showEditorLoading("Cargando justificación…");
    const { controller, serial } = beginNavigationLoad();
    try {
      const [payload, clientsPayload] = await Promise.all([
        request(apiPaths().detail(id), { signal: controller.signal }),
        request(apiPaths().clients(), { signal: controller.signal }),
      ]);
      if (!navigationLoadIsCurrent(serial, controller)) return;
      state.clients = clientsPayload.items || [];
      state.current = normalizeItem(payload);
      state.permissions = payload.permissions || {};
      state.returnLicitacionId = String(state.current.licitacion_id || "");
      state.selectedLineIds.clear();
      state.conflict = false;
      state.clientSnapshotClientId = String(state.current.cliente_id || "");
      state.clientSnapshotValid = true;
      renderEditor();
      setDirty(false);
    } catch (error) {
      if (error?.name === "AbortError" || !navigationLoadIsCurrent(serial, controller)) return;
      showEditorLoading(`No se pudo cargar la justificación: ${error.message}`, true);
    } finally {
      if (navigationLoadIsCurrent(serial, controller)) state.navigationController = null;
    }
  }

  function showEditorLoading(message, error = false) {
    state.root.querySelector("[data-jb-list-view]").hidden = true;
    const editor = state.root.querySelector("[data-jb-editor-view]");
    editor.hidden = false;
    editor.querySelector("[data-jb-form]").innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
    editor.querySelector("[data-jb-summary]").innerHTML = error ? `<div class="import-result error">${escapeHtml(message)}</div>` : `<div class="empty">Cargando…</div>`;
  }

  function renderEditor() {
    const editor = state.root.querySelector("[data-jb-editor-view]");
    state.root.querySelector("[data-jb-list-view]").hidden = true;
    editor.hidden = false;
    editor.querySelector("[data-jb-form]").innerHTML = editorSectionsMarkup();
    editor.querySelector("[data-jb-editor-title]").textContent = state.current.id
      ? `${state.current.expediente || "Justificación"} · Lote ${state.current.lote_numero || "—"}`
      : "Nueva justificación de baja";
    fillEditorFields();
    renderProducts();
    renderSummary();
    renderIssues();
    renderVersions();
    applyPermissions();
    updateEditorMeta();
  }

  function editorValue(paths, fallback = "") {
    return firstValue(state.current, paths, fallback);
  }

  function setField(name, value) {
    const field = state.root.querySelector(`[data-jb-form] [name="${name}"]`);
    if (!field) return;
    field.value = value === null || value === undefined ? "" : String(value);
  }

  function textAreaValue(value) {
    if (Array.isArray(value)) return value.join("\n\n");
    return value === null || value === undefined ? "" : String(value);
  }

  function fillEditorFields() {
    const draft = currentDraft();
    populateClientOptions(state.current.cliente_id || draft.client?.client_id || "");
    const values = {
      expediente: state.current.expediente || draft.expediente,
      organismo: firstValue(draft, ["identification.organismo", "organismo"]),
      objeto: firstValue(draft, ["identification.objeto", "objeto"]),
      lote_numero: state.current.lote_numero || firstValue(draft, ["identification.lot_number", "lote_numero", "lot_identifier"]),
      lote_nombre: state.current.lote_nombre || firstValue(draft, ["identification.lot_name", "lote_nombre"]),
      declared_lot_offer: firstValue(draft, ["financial.declared_lot_offer", "importe_ofertado"]),
      duracion_descriptiva: firstValue(draft, ["identification.duration_description", "duracion_descriptiva"]),
      operational_weeks: firstValue(draft, ["transport.operational_weeks"]),
      weekly_deliveries: firstValue(draft, ["transport.weekly_deliveries"]),
      descriptive_months: firstValue(draft, ["transport.descriptive_months"]),
      contract_stops: firstValue(draft, ["transport.contract_stops"]),
      circular_kilometres: firstValue(draft, ["transport.circular_kilometres"]),
      effective_decimal_hours: firstValue(draft, ["transport.effective_decimal_hours"]),
      route_duration_text: firstValue(draft, ["transport.route_duration_text"]),
      kilometre_rate: firstValue(draft, ["transport.kilometre_rate"]),
      hourly_rate: firstValue(draft, ["transport.hourly_rate"]),
      shared_orders: firstValue(draft, ["transport.shared_orders"]),
      vehicle_type: firstValue(draft, ["transport_document.vehicle", "observatory.vehicle_type", "transport.vehicle_type"]),
      observatory_date: firstValue(draft, ["transport_document.observatory_date", "observatory.date", "observatory_date"]),
      observatory_url: firstValue(draft, ["transport_document.observatory_url", "observatory.url", "observatory_url"]),
      general_expense_base: firstValue(draft, ["financial.general_expense_base"]),
      general_expense_percentage: firstValue(draft, ["financial.general_expense_percentage"]),
      indirect_costs: firstValue(draft, ["financial.indirect_costs"]),
      minimum_percentage: firstValue(draft, ["cost_range.minimum_percentage"]),
      maximum_percentage: firstValue(draft, ["cost_range.maximum_percentage"]),
      cliente_razon_social: firstValue(draft, ["client.name", "client_snapshot.razon_social"]),
      cliente_nif: firstValue(draft, ["client.nif", "client_snapshot.nif_cif", "client_snapshot.nif"]),
      cliente_telefono: firstValue(draft, ["client.phone", "client_snapshot.telefono_principal", "client_snapshot.telefono"]),
      cliente_domicilio: firstValue(draft, ["client.address", "client_snapshot.domicilio_fiscal", "client_snapshot.domicilio"]),
      cliente_email: firstValue(draft, ["client.email", "client_snapshot.email_principal", "client_snapshot.email"]),
      representante_nombre: firstValue(draft, ["client.representative", "client_snapshot.representante_nombre"]),
      representante_nif: firstValue(draft, ["client.representative_dni", "client_snapshot.representante_nif"]),
      representante_cargo: firstValue(draft, ["client.role", "client_snapshot.representante_cargo"]),
      exposition: firstValue(draft, ["narrative.exposition"]),
      argumentos: textAreaValue(firstValue(draft, ["narrative.arguments", "narrative.argumentos", "argumentos"])),
      acquisition_text: firstValue(draft, ["narrative.acquisition_text"]),
      texto_transporte: firstValue(draft, ["narrative.transport_text", "narrative.texto_transporte"]),
      structure_text: firstValue(draft, ["narrative.structure_text"]),
      conclusion: firstValue(draft, ["narrative.conclusion", "narrative.conclusion_text"]),
      lugar: firstValue(draft, ["identification.place", "narrative.place", "narrative.lugar"]),
      fecha_informe: firstValue(draft, ["identification.date_text", "narrative.report_date", "narrative.fecha_informe"]),
      firmante: firstValue(draft, ["client.signatory", "narrative.signatory", "narrative.firmante"]),
      firmante_cargo: firstValue(draft, ["client.role", "narrative.signatory_title", "narrative.firmante_cargo"]),
    };
    Object.entries(values).forEach(([name, value]) => setField(name, value));
    const status = state.root.querySelector("[data-jb-status]");
    if (status) status.value = state.current.estado || "borrador";
    renderRouteImageState();
  }

  function populateClientOptions(selectedValue = "") {
    const select = state.root.querySelector("[data-jb-client]");
    if (!select) return;
    select.innerHTML = [
      `<option value="">Selecciona cliente</option>`,
      ...state.clients.map((client) => {
        const name = client.display_name || client.nombre_comercial || client.razon_social || "Cliente sin nombre";
        const nif = client.nif_cif ? ` · ${client.nif_cif}` : "";
        return `<option value="${escapeHtml(client.id)}" ${String(client.id) === String(selectedValue) ? "selected" : ""}>${escapeHtml(`${name}${nif}`)}</option>`;
      }),
    ].join("");
  }

  function collectProductsFromTable() {
    const rows = [...state.root.querySelectorAll("[data-jb-product-row]")];
    return rows.map((row) => {
      const original = (state.current.products || []).find((item) => String(item.line_id) === row.dataset.jbProductRow) || {};
      const value = (field) => row.querySelector(`[data-product-field="${field}"]`)?.value.trim() || "";
      return {
        ...original,
        line_id: row.dataset.jbProductRow,
        name: value("name"),
        characteristics: value("characteristics"),
        quantity: value("quantity"),
        offered_unit_price: value("offered_unit_price"),
      };
    });
  }

  function collectDraft() {
    const form = state.root.querySelector("[data-jb-form]");
    const value = (name) => String(form.elements[name]?.value ?? "").trim();
    const products = collectProductsFromTable();
    state.current.products = products;
    const previous = currentDraft();
    const argumentsText = value("argumentos");
    return {
      ...previous,
      schema_version: previous.schema_version || "1",
      identification: {
        ...(previous.identification || {}),
        expediente: value("expediente"),
        organismo: value("organismo"),
        objeto: value("objeto"),
        lot_number: value("lote_numero"),
        lot_name: value("lote_nombre"),
        duration_description: value("duracion_descriptiva"),
        place: value("lugar"),
        date_text: value("fecha_informe"),
      },
      client: {
        ...(previous.client || {}),
        client_id: Number(value("cliente_id") || 0),
        name: value("cliente_razon_social"),
        nif: value("cliente_nif"),
        address: value("cliente_domicilio"),
        phone: value("cliente_telefono"),
        email: value("cliente_email"),
        representative: value("representante_nombre"),
        representative_dni: value("representante_nif"),
        role: value("representante_cargo") || value("firmante_cargo"),
        signatory: value("firmante"),
      },
      products,
      transport: {
        ...(previous.transport || {}),
        operational_weeks: value("operational_weeks"),
        weekly_deliveries: value("weekly_deliveries"),
        circular_kilometres: value("circular_kilometres"),
        effective_decimal_hours: value("effective_decimal_hours"),
        kilometre_rate: value("kilometre_rate"),
        hourly_rate: value("hourly_rate"),
        contract_stops: value("contract_stops"),
        shared_orders: value("shared_orders"),
        descriptive_months: value("descriptive_months") || null,
        route_duration_text: value("route_duration_text"),
      },
      financial: {
        ...(previous.financial || {}),
        declared_lot_offer: value("declared_lot_offer"),
        general_expense_base: value("general_expense_base"),
        general_expense_percentage: value("general_expense_percentage"),
        indirect_costs: value("indirect_costs") || null,
      },
      cost_range: {
        ...(previous.cost_range || {}),
        minimum_percentage: value("minimum_percentage"),
        maximum_percentage: value("maximum_percentage"),
      },
      transport_document: {
        ...(previous.transport_document || {}),
        observatory: previous.transport_document?.observatory || "Observatorio de Costes del Transporte de Mercancías por Carretera",
        observatory_date: value("observatory_date"),
        observatory_url: value("observatory_url"),
        vehicle: value("vehicle_type"),
      },
      narrative: {
        ...(previous.narrative || {}),
        exposition: value("exposition"),
        arguments: argumentsText ? argumentsText.split(/\n\s*\n|\n/).map((item) => item.trim()).filter(Boolean) : [],
        acquisition_text: value("acquisition_text"),
        transport_text: value("texto_transporte"),
        structure_text: value("structure_text"),
        conclusion: value("conclusion"),
      },
      route_image: previous.route_image || null,
      accepted_warning_codes: previous.accepted_warning_codes || [],
      source: previous.source || {},
    };
  }

  function ensureGeneralExpenseBase() {
    const form = state.root.querySelector("[data-jb-form]");
    const base = form?.elements.general_expense_base;
    const offer = form?.elements.declared_lot_offer;
    if (base && offer && !base.value.trim() && offer.value.trim()) base.value = offer.value;
  }

  function validateRequestFields({ focus = true, announce = true } = {}) {
    const form = state.root.querySelector("[data-jb-form]");
    if (!form) return false;
    form.querySelectorAll('[aria-invalid="true"]').forEach((field) => field.removeAttribute("aria-invalid"));
    const problems = [];
    let firstInvalid = null;
    const markInvalid = (field, message) => {
      field?.setAttribute("aria-invalid", "true");
      firstInvalid ||= field;
      problems.push(message);
    };
    REQUIRED_NUMERIC_FIELDS.forEach(([name, label, kind]) => {
      const field = form.elements[name];
      if (!numericTextIsValid(field?.value, kind)) markInvalid(field, label);
    });
    form.querySelectorAll("[data-jb-product-row]").forEach((row, index) => {
      for (const [fieldName, label] of [["quantity", "cantidad"], ["offered_unit_price", "precio ofertado"]]) {
        const field = row.querySelector(`[data-product-field="${fieldName}"]`);
        if (!numericTextIsValid(field?.value, "decimal")) markInvalid(field, `${label} del producto ${index + 1}`);
      }
    });
    if (!problems.length) return true;
    if (announce) {
      const visible = problems.slice(0, 5).join(", ");
      const extra = problems.length > 5 ? ` y ${problems.length - 5} campo(s) más` : "";
      setResult("editor", `Completa con números válidos: ${visible}${extra}.`, "warning");
    }
    if (focus) firstInvalid?.focus();
    return false;
  }

  function savePayload() {
    const form = state.root.querySelector("[data-jb-form]");
    const field = (name) => form.elements[name]?.value.trim() || "";
    const draft = collectDraft();
    return {
      licitacion_id: Number(state.current.licitacion_id || 0),
      cliente_id: Number(field("cliente_id") || 0),
      expediente: field("expediente"),
      lote_numero: field("lote_numero"),
      lote_nombre: field("lote_nombre"),
      importe_ofertado: draft.financial.declared_lot_offer,
      revision: state.current.revision,
      draft,
    };
  }

  async function saveCurrent({ silent = false, withinMutation = false } = {}) {
    if (!state.current || (!withinMutation && state.busy) || state.conflict) return null;
    if (!isAllowed("can_edit")) {
      setResult("editor", "Tu perfil dispone de acceso de solo lectura.", "warning");
      return null;
    }
    if (state.clientLoading) {
      setResult("editor", "Espera a que terminen de cargarse los datos del cliente.", "warning");
      return null;
    }
    if (!clientSnapshotMatchesSelection()) {
      setResult("editor", "No se han podido confirmar los datos del cliente seleccionado. Vuelve a seleccionarlo o recarga la ficha.", "error");
      return null;
    }
    ensureGeneralExpenseBase();
    if (!validateRequestFields({ focus: true, announce: true })) return null;
    const payload = savePayload();
    if (!payload.cliente_id || !payload.expediente || !payload.lote_numero || !payload.importe_ofertado) {
      setResult("editor", "Selecciona cliente e indica expediente, número de lote e importe ofertado.", "error");
      return null;
    }
    invalidateLivePreview();
    if (!withinMutation) setBusy(true, silent ? "" : "Guardando borrador…");
    try {
      let response;
      if (state.current.id) {
        response = await request(apiPaths().detail(state.current.id), { method: "PATCH", json: payload });
      } else {
        response = await request(apiPaths().collection(), { method: "POST", json: payload });
      }
      applyServerItem(response);
      setDirty(false);
      if (!silent) setResult("editor", "Borrador guardado.", "ok");
      return state.current;
    } catch (error) {
      if (error instanceof ConflictError) handleConflict(error);
      else setResult("editor", error.message, "error");
      return null;
    } finally {
      if (!withinMutation) setBusy(false);
    }
  }

  function scheduleLivePreview() {
    invalidateLivePreview();
    if (!state.current || state.conflict || !isAllowed("can_edit")) return;
    const serial = state.requestSerial;
    state.liveSaveTimer = global.setTimeout(async () => {
      ensureGeneralExpenseBase();
      if (!validateRequestFields({ focus: false, announce: false })) {
        setResult("editor", "Completa los campos numéricos obligatorios para actualizar la previsualización.", "warning");
        return;
      }
      try {
        const response = await request(apiPaths().preview(), {
          method: "POST",
          json: { draft: collectDraft() },
        });
        if (serial !== state.requestSerial) return;
        state.current.calculation = response.calculation || response.item?.calculation || null;
        state.current.issues = response.issues || response.item?.issues || [];
        const focus = captureProductFocus();
        renderProducts();
        restoreProductFocus(focus);
        renderSummary();
        renderIssues();
        const hasErrors = Boolean(response.calculation?.errors?.length);
        setResult(
          "editor",
          hasErrors ? "La previsualización contiene errores que deben corregirse." : "Previsualización económica actualizada por el servidor.",
          hasErrors ? "warning" : "ok",
        );
      } catch (error) {
        if (serial !== state.requestSerial) return;
        setResult("editor", error.message, error.status === 422 ? "warning" : "error");
      }
    }, LIVE_SAVE_DELAY);
  }

  function captureProductFocus() {
    const active = document.activeElement;
    const row = active?.closest?.("[data-jb-product-row]");
    const field = active?.dataset?.productField;
    if (!row || !field) return null;
    return {
      lineId: row.dataset.jbProductRow,
      field,
      start: active.selectionStart,
      end: active.selectionEnd,
    };
  }

  function restoreProductFocus(focus) {
    if (!focus) return;
    const row = [...state.root.querySelectorAll("[data-jb-product-row]")]
      .find((item) => item.dataset.jbProductRow === focus.lineId);
    const field = row?.querySelector(`[data-product-field="${focus.field}"]`);
    if (!field) return;
    field.focus();
    if (typeof field.setSelectionRange === "function" && focus.start !== null) {
      field.setSelectionRange(focus.start, focus.end);
    }
  }

  function applyServerItem(payload) {
    invalidateLivePreview();
    state.current = normalizeItem(payload);
    state.permissions = payload.permissions || state.permissions;
    state.conflict = false;
    const conflict = state.root.querySelector("[data-jb-conflict]");
    if (conflict) conflict.hidden = true;
    fillEditorFields();
    renderProducts();
    renderSummary();
    renderIssues();
    renderVersions();
    updateEditorMeta();
    applyPermissions();
  }

  function calculationLines() {
    return state.current?.calculation?.values?.product_lines || [];
  }

  function renderProducts() {
    const body = state.root.querySelector("[data-jb-products]");
    if (!body) return;
    const products = state.current?.products || [];
    const resultById = new Map(calculationLines().map((line) => [String(line.line_id), line]));
    if (!products.length) {
      body.innerHTML = `<tr><td colspan="11" class="empty">Añade o importa productos.</td></tr>`;
      updateSelectionCount();
      applyPermissions();
      return;
    }
    body.innerHTML = products.map((product, index) => {
      const lineId = String(product.line_id || makeManualLineId());
      product.line_id = lineId;
      const result = resultById.get(lineId) || {};
      const display = result.display || {};
      const effectiveCost = display.effective_unit_cost || result.effective_unit_cost || product.manual_unit_cost || product.generated_unit_cost || "—";
      const origin = product.cost_origin || (product.manual_unit_cost !== null && product.manual_unit_cost !== undefined ? "manual" : product.generated_unit_cost !== null && product.generated_unit_cost !== undefined ? "generado" : "sin_generar");
      return `
        <tr data-jb-product-row="${escapeHtml(lineId)}">
          <td><input type="checkbox" data-jb-select-line="${escapeHtml(lineId)}" ${state.selectedLineIds.has(lineId) ? "checked" : ""} aria-label="Seleccionar línea ${index + 1}"></td>
          <td><input data-product-field="name" value="${escapeHtml(product.name || "")}" aria-label="Producto"></td>
          <td><input data-product-field="characteristics" value="${escapeHtml(product.characteristics || "")}" aria-label="Características"></td>
          <td><input data-product-field="quantity" inputmode="decimal" value="${escapeHtml(product.quantity || "")}" aria-label="Cantidad" required></td>
          <td><input data-product-field="offered_unit_price" inputmode="decimal" value="${escapeHtml(product.offered_unit_price || "")}" aria-label="Precio ofertado" required></td>
          <td>${escapeHtml(display.offered_amount || result.offered_amount || product.offered_amount_display || "—")}</td>
          <td>
            <span class="jb-cost-origin jb-cost-origin-${escapeHtml(origin)}">${escapeHtml(effectiveCost)}</span>
            <input data-jb-manual-input inputmode="decimal" value="${escapeHtml(product.manual_unit_cost || "")}" placeholder="Coste manual" aria-label="Coste manual">
          </td>
          <td>${escapeHtml(display.cost_amount || result.cost_amount || "—")}</td>
          <td class="${String(result.margin || "").startsWith("-") ? "jb-negative" : ""}">${escapeHtml(display.margin || result.margin || "—")}</td>
          <td><span class="jb-lock-state">${product.locked ? "Bloqueado" : "Editable"}</span></td>
          <td>
            <div class="jb-row-actions">
              <button type="button" data-jb-apply-manual="${escapeHtml(lineId)}">Aplicar manual</button>
              ${origin === "manual" ? `<button type="button" data-jb-remove-manual="${escapeHtml(lineId)}">Retirar manual</button>` : ""}
              <button type="button" data-jb-toggle-lock="${escapeHtml(lineId)}" data-locked="${product.locked ? "1" : "0"}">${product.locked ? "Desbloquear" : "Bloquear"}</button>
              <button type="button" data-jb-move-product="${escapeHtml(lineId)}" data-direction="-1" aria-label="Subir">↑</button>
              <button type="button" data-jb-move-product="${escapeHtml(lineId)}" data-direction="1" aria-label="Bajar">↓</button>
              <button type="button" data-jb-duplicate-product="${escapeHtml(lineId)}">Duplicar</button>
              <button type="button" class="danger" data-jb-delete-product="${escapeHtml(lineId)}">Eliminar</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
    updateSelectionCount();
    applyPermissions();
  }

  function summaryValues() {
    return state.current?.calculation?.values || null;
  }

  function renderSummary() {
    const summary = state.root.querySelector("[data-jb-summary]");
    if (!summary) return;
    const values = summaryValues();
    if (!values) {
      summary.innerHTML = `
        <h3>Resultado económico</h3>
        <div class="jb-summary-empty">Todavía no existe un cálculo válido del servidor.</div>
        <div class="jb-issues" data-jb-issues></div>
      `;
      return;
    }
    const raw = values.raw || {};
    const display = values.display || {};
    summary.innerHTML = `
      <h3>Resultado económico</h3>
      <dl class="jb-summary-values">
        ${SUMMARY_ROWS.map(([key, label]) => `
          <div class="${key === "profit" || key === "profit_percentage" ? "jb-summary-emphasis" : ""}">
            <dt>${escapeHtml(label)}</dt>
            <dd data-summary-key="${escapeHtml(key)}" data-raw="${escapeHtml(raw[key] ?? "")}">${escapeHtml(display[key] ?? raw[key] ?? "—")}</dd>
          </div>
        `).join("")}
      </dl>
      <p class="jb-summary-source">Calculado por el backend · revisión ${escapeHtml(state.current.revision)}</p>
      <div class="jb-issues" data-jb-issues></div>
    `;
  }

  function normalizedIssues() {
    const calculation = state.current?.calculation || {};
    return [
      ...(state.current?.issues || []),
      ...(calculation.errors || []),
      ...(calculation.warnings || []),
    ].filter((item, index, items) => index === items.findIndex((other) => `${other.code}|${other.line_id || ""}|${other.message}` === `${item.code}|${item.line_id || ""}|${item.message}`));
  }

  function renderIssues() {
    const target = state.root.querySelector("[data-jb-issues]");
    if (!target) return;
    const issues = normalizedIssues();
    if (!issues.length) {
      target.innerHTML = `<div class="jb-no-issues">Sin advertencias.</div>`;
      return;
    }
    target.innerHTML = `
      <h4>Advertencias</h4>
      <ul>${issues.map((issue) => `<li class="jb-issue-${escapeHtml(issue.severity || "advertencia")}"><strong>${escapeHtml(issue.code || "Aviso")}</strong><span>${escapeHtml(issue.message || "")}</span></li>`).join("")}</ul>
    `;
  }

  function renderRouteImageState() {
    const target = state.root.querySelector("[data-jb-route-image-state]");
    if (!target) return;
    const image = currentDraft().route_image || state.current?.route_image;
    target.textContent = image
      ? `${image.logical_name || image.file_name || "Imagen adjunta"}${image.sha256 ? ` · ${image.sha256.slice(0, 12)}…` : ""}`
      : "Sin imagen. Su ausencia genera una advertencia, no bloquea el cálculo.";
  }

  function renderVersions() {
    const container = state.root.querySelector("[data-jb-versions]");
    const history = state.root.querySelector("[data-jb-history]");
    if (!container || !history) return;
    const versions = state.current?.versions || [];
    const documents = state.current?.documents || [];
    if (!versions.length) {
      container.innerHTML = `<div class="empty">Aún no hay versiones congeladas.</div>`;
    } else {
      container.innerHTML = versions.map((version) => {
        const number = version.version_number || version.version || 0;
        const versionDocs = documents.filter((document) => Number(document.version_number || document.version) === Number(number) || Number(document.version_id) === Number(version.id));
        return `
          <article class="jb-version-card">
            <div><strong>Versión ${escapeHtml(number)}</strong><span>${escapeHtml(displayDateTime(version.created_at))}</span><code>${escapeHtml(version.snapshot_sha256 || "")}</code></div>
            <div class="jb-version-documents">
              ${versionDocs.map((document) => `
                <a href="${escapeHtml(apiPaths().documentDownload(document.id))}" data-jb-download-document="${escapeHtml(document.id)}">
                  ${escapeHtml((document.document_type || "documento").toUpperCase())} · ${escapeHtml(document.file_name || "Documento")} · ${escapeHtml(displayBytes(document.size_bytes))}
                </a>
              `).join("") || `<span>Sin documentos generados.</span>`}
              ${isAllowed("can_generate_documents") ? `<button type="button" data-jb-generate-documents="${escapeHtml(number)}">Generar Word y Excel</button>` : ""}
            </div>
          </article>
        `;
      }).join("");
    }
    const events = state.current?.history || [];
    history.innerHTML = events.length ? `
      <details><summary>Historial (${events.length})</summary>
        <ol>${events.map((event) => `<li><span>${escapeHtml(displayDateTime(event.created_at))}</span><strong>${escapeHtml(event.message || event.event_type || "Evento")}</strong><small>${escapeHtml(event.created_by || "")}</small></li>`).join("")}</ol>
      </details>
    ` : "";
  }

  function updateEditorMeta() {
    const target = state.root.querySelector("[data-jb-editor-meta]");
    if (!target || !state.current) return;
    target.innerHTML = `
      <span class="jb-status jb-status-${escapeHtml(state.current.estado || "borrador")}">${escapeHtml(STATUS_LABELS[state.current.estado] || state.current.estado || "Borrador")}</span>
      <span>Revisión ${escapeHtml(state.current.revision || 0)}</span>
      <span>Última versión ${escapeHtml(state.current.latest_version || 0)}</span>
      ${state.current.draft_frozen ? `<span>Snapshot congelado</span>` : `<span>Borrador editable</span>`}
    `;
  }

  function applyPermissions() {
    const canEdit = isAllowed("can_edit");
    const clientReady = clientSnapshotMatchesSelection() && !state.clientLoading;
    const canGenerateCosts = isAllowed("can_generate_costs", canEdit) && clientReady;
    const canFreeze = isAllowed("can_freeze", canEdit) && clientReady;
    const canChangeStatus = isAllowed("can_change_status", canEdit) && clientReady;
    const permissionMap = [
      ["[data-jb-save]", canEdit && clientReady],
      ["[data-jb-add-product]", canEdit],
      ["[data-jb-open-xlsx]", canEdit],
      ["[data-jb-open-paste]", canEdit],
      ["[data-jb-preview-import]", canEdit],
      ["[data-jb-confirm-import]", canEdit && Boolean(state.importPreview?.can_confirm !== false && state.importPreview?.products?.length)],
      ["[data-jb-apply-manual]", canGenerateCosts],
      ["[data-jb-remove-manual]", canGenerateCosts],
      ["[data-jb-toggle-lock]", canGenerateCosts],
      ["[data-jb-lock-selected]", canGenerateCosts],
      ["[data-jb-unlock-selected]", canGenerateCosts],
      ["[data-jb-move-product]", canEdit],
      ["[data-jb-duplicate-product]", canEdit],
      ["[data-jb-delete-product]", canEdit],
      ["[data-jb-generate-costs]", canGenerateCosts],
      ["[data-jb-recalculate-selected]", canGenerateCosts],
      ["[data-jb-recalculate-unlocked]", canGenerateCosts],
      ["[data-jb-freeze]", canFreeze],
      ["[data-jb-change-status]", canChangeStatus],
      ["[data-jb-upload-route-image]", canEdit && clientReady],
      ["[data-jb-attach-existing-route-image]", canEdit && clientReady],
    ];
    permissionMap.forEach(([selector, enabled]) => {
      state.root.querySelectorAll(selector).forEach((element) => {
        element.dataset.jbPermissionDisabled = enabled ? "0" : "1";
        element.disabled = state.busy || !enabled;
      });
    });
    state.root.querySelectorAll("[data-jb-form] input, [data-jb-form] textarea, [data-jb-form] select").forEach((field) => {
      if (field.matches("[data-jb-status]")) field.disabled = state.busy || !canChangeStatus;
      else if (field.matches("[data-jb-select-line], [data-jb-select-all]")) field.disabled = state.busy || !canGenerateCosts;
      else field.disabled = !canEdit || state.busy;
    });
    const client = state.root.querySelector("[data-jb-client]");
    if (client) client.disabled = !canEdit || Boolean(state.current?.id) || state.busy;
    state.root.querySelectorAll("[data-jb-import-dialog] input, [data-jb-import-dialog] textarea, [data-jb-import-dialog] select").forEach((field) => {
      field.disabled = !canEdit || state.busy;
    });
  }

  function updateSelectionCount() {
    const count = state.selectedLineIds.size;
    const target = state.root.querySelector("[data-jb-selection-count]");
    if (target) target.textContent = `${count} seleccionado${count === 1 ? "" : "s"}`;
  }

  async function ensureSaved({ withinMutation = false } = {}) {
    if (!state.current?.id || state.dirty) return saveCurrent({ silent: withinMutation, withinMutation });
    return state.current;
  }

  async function performAction(pathBuilder, json, progress, success) {
    if (state.busy) return null;
    invalidateLivePreview();
    setBusy(true, progress);
    try {
      const saved = await ensureSaved({ withinMutation: true });
      if (!saved) return null;
      const path = typeof pathBuilder === "function" ? pathBuilder(state.current.id) : pathBuilder;
      const response = await request(path, { method: "POST", json: { revision: state.current.revision, ...json } });
      applyServerItem(response);
      setDirty(false);
      setResult("editor", success, "ok");
      return response;
    } catch (error) {
      if (error instanceof ConflictError) handleConflict(error);
      else setResult("editor", error.message, "error");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function generateCosts() {
    if (!requirePermission("can_generate_costs")) return;
    await performAction(
      (id) => apiPaths().generateCosts(id),
      {},
      "Generando costes…",
      "Costes generados. Los valores quedan guardados hasta una nueva acción explícita.",
    );
  }

  async function recalculateCosts(selectedOnly) {
    if (!requirePermission("can_generate_costs")) return;
    if (selectedOnly && !state.selectedLineIds.size) {
      setResult("editor", "Selecciona al menos un producto.", "warning");
      return;
    }
    await performAction(
      (id) => apiPaths().recalculateCosts(id),
      { line_ids: selectedOnly ? [...state.selectedLineIds] : null },
      "Recalculando costes…",
      selectedOnly ? "Productos seleccionados recalculados." : "Productos no bloqueados recalculados.",
    );
  }

  async function applyManualCost(lineId, button) {
    if (!requirePermission("can_generate_costs")) return;
    const row = button.closest("[data-jb-product-row]");
    const manual = row?.querySelector("[data-jb-manual-input]")?.value.trim() || "";
    if (!manual) {
      setResult("editor", "Indica un coste manual.", "warning");
      return;
    }
    await performAction((id) => apiPaths().manualCost(id), { line_id: lineId, manual_unit_cost: manual }, "Aplicando coste manual…", "Coste manual aplicado y trazado.");
  }

  async function removeManualCost(lineId) {
    if (!requirePermission("can_generate_costs")) return;
    await performAction((id) => apiPaths().removeManualCost(id), { line_id: lineId }, "Retirando coste manual…", "Se ha restaurado el coste generado.");
  }

  async function setProductLock(lineIds, locked) {
    if (!requirePermission("can_generate_costs")) return;
    if (state.busy) return;
    if (!lineIds.length) {
      setResult("editor", "Selecciona al menos un producto.", "warning");
      return;
    }
    invalidateLivePreview();
    setBusy(true, locked ? "Bloqueando productos…" : "Desbloqueando productos…");
    try {
      const saved = await ensureSaved({ withinMutation: true });
      if (!saved) return;
      const response = await request(apiPaths().productLock(state.current.id), {
        method: "POST",
        json: { revision: state.current.revision, line_ids: lineIds, locked },
      });
      applyServerItem(response);
      setDirty(false);
      setResult("editor", locked ? "Productos bloqueados." : "Productos desbloqueados.", "ok");
    } catch (error) {
      if (error instanceof ConflictError) handleConflict(error);
      else setResult("editor", error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  function addProduct(source = {}) {
    if (!requirePermission("can_edit")) return;
    collectDraft();
    state.current.products.push({
      line_id: makeManualLineId(),
      name: source.name || "",
      characteristics: source.characteristics || "",
      quantity: source.quantity || "",
      offered_unit_price: source.offered_unit_price || "",
      applied_percentage: null,
      applied_factor: null,
      generated_unit_cost: null,
      manual_unit_cost: null,
      locked: false,
      cost_origin: "sin_generar",
    });
    state.current.draft.products = state.current.products;
    renderProducts();
    setDirty(true);
    scheduleLivePreview();
  }

  function mutateProduct(lineId, action) {
    if (!requirePermission("can_edit")) return;
    collectDraft();
    const products = state.current.products;
    const index = products.findIndex((item) => String(item.line_id) === String(lineId));
    if (index < 0) return;
    if (action === "delete") products.splice(index, 1);
    if (action === "duplicate") products.splice(index + 1, 0, { ...products[index], line_id: makeManualLineId(), generated_unit_cost: null, manual_unit_cost: null, cost_origin: "sin_generar", locked: false });
    if (action === "up" && index > 0) [products[index - 1], products[index]] = [products[index], products[index - 1]];
    if (action === "down" && index < products.length - 1) [products[index + 1], products[index]] = [products[index], products[index + 1]];
    state.current.draft.products = products;
    state.selectedLineIds.delete(String(lineId));
    renderProducts();
    setDirty(true);
    scheduleLivePreview();
  }

  function cancelClientSnapshotLoad() {
    state.clientLoadSerial += 1;
    state.clientLoadController?.abort();
    state.clientLoadController = null;
    state.clientLoading = false;
    if (state.root) applyPermissions();
  }

  function clientSnapshotMatchesSelection() {
    if (state.current?.id) return true;
    const selected = state.root?.querySelector("[data-jb-client]")?.value || "";
    return Boolean(
      selected
      && state.clientSnapshotValid
      && String(state.clientSnapshotClientId) === String(selected)
    );
  }

  function clearClientSnapshotFields() {
    for (const name of (
      [
        "cliente_razon_social",
        "cliente_nif",
        "cliente_telefono",
        "cliente_domicilio",
        "cliente_email",
        "representante_nombre",
        "representante_nif",
        "representante_cargo",
        "firmante",
        "firmante_cargo",
        "lugar",
      ]
    )) setField(name, "");
  }

  async function loadClientSnapshot(clientId) {
    if (state.current?.id || !requirePermission("can_edit")) return;
    state.clientLoadController?.abort();
    const serial = ++state.clientLoadSerial;
    state.clientSnapshotClientId = "";
    state.clientSnapshotValid = false;
    clearClientSnapshotFields();
    setDirty(true);
    if (!clientId) {
      state.clientLoadController = null;
      state.clientLoading = false;
      applyPermissions();
      return;
    }
    const controller = new AbortController();
    state.clientLoadController = controller;
    state.clientLoading = true;
    applyPermissions();
    setResult("editor", "Cargando datos del cliente…", "");
    try {
      const payload = await request(apiPaths().client(clientId), { signal: controller.signal });
      const selectedClient = state.root.querySelector("[data-jb-client]")?.value || "";
      if (serial !== state.clientLoadSerial || String(selectedClient) !== String(clientId) || state.current?.id) return;
      const client = payload.item || {};
      const fields = {
        cliente_razon_social: client.razon_social,
        cliente_nif: client.nif_cif,
        cliente_telefono: client.telefono_principal,
        cliente_domicilio: joinedAddress(client),
        cliente_email: client.email_principal,
        representante_nombre: client.representante_nombre,
        representante_nif: client.representante_nif,
        representante_cargo: client.representante_cargo,
        firmante: client.representante_nombre,
        firmante_cargo: client.representante_cargo,
        lugar: client.municipio,
      };
      Object.entries(fields).forEach(([name, value]) => setField(name, value || ""));
      state.clientSnapshotClientId = String(clientId);
      state.clientSnapshotValid = true;
      setDirty(true);
      setResult("editor", "Datos del cliente copiados. Puedes revisarlos antes de guardar.", "ok");
    } catch (error) {
      if (error?.name !== "AbortError" && serial === state.clientLoadSerial) {
        setResult("editor", error.message, "error");
      }
    } finally {
      if (serial === state.clientLoadSerial) {
        state.clientLoadController = null;
        state.clientLoading = false;
        applyPermissions();
      }
    }
  }

  function importInputSignature() {
    const dialog = state.root.querySelector("[data-jb-import-dialog]");
    const file = dialog.querySelector("[data-jb-xlsx-file]").files?.[0] || null;
    return JSON.stringify({
      mode: state.importMode,
      startRow: dialog.querySelector("[data-jb-import-start-row]").value || "1",
      sheet: dialog.querySelector("[data-jb-import-sheet]").value || "",
      mapping: importMapping(),
      text: dialog.querySelector("[data-jb-paste-text]").value || "",
      file: file ? [file.name, file.size, file.lastModified, file.type] : null,
    });
  }

  function invalidateImportPreview({ announce = false } = {}) {
    const dialog = state.root?.querySelector("[data-jb-import-dialog]");
    const hadPreview = Boolean(state.importPreview || state.importPreviewPending || dialog?.querySelector("[data-jb-import-preview]")?.children.length);
    state.importPreviewSerial += 1;
    state.importPreview = null;
    state.importPreviewSignature = "";
    state.importPreviewPending = false;
    const confirm = dialog?.querySelector("[data-jb-confirm-import]");
    if (confirm) confirm.disabled = true;
    const target = dialog?.querySelector("[data-jb-import-preview]");
    if (target) target.innerHTML = "";
    if (state.root) applyPermissions();
    if (announce && hadPreview) {
      setResult("import", "Los datos de importación han cambiado. Vuelve a previsualizar antes de incorporar.", "warning");
    }
  }

  function openImport(mode) {
    if (!requirePermission("can_edit")) return;
    state.importMode = mode;
    invalidateImportPreview();
    const dialog = state.root.querySelector("[data-jb-import-dialog]");
    dialog.querySelector("[data-jb-import-title]").textContent = mode === "xlsx" ? "Importar productos desde Excel" : "Pegar productos desde el portapapeles";
    dialog.querySelector("[data-jb-xlsx-fields]").hidden = mode !== "xlsx";
    dialog.querySelector("[data-jb-paste-fields]").hidden = mode !== "paste";
    dialog.querySelector("[data-jb-confirm-import]").disabled = true;
    dialog.querySelector("[data-jb-import-preview]").innerHTML = "";
    setResult("import", "");
    dialog.showModal();
  }

  function closeImport() {
    invalidateImportPreview();
    state.root.querySelector("[data-jb-import-dialog]").close();
  }

  function importMapping() {
    const dialog = state.root.querySelector("[data-jb-import-dialog]");
    const mapping = {};
    dialog.querySelectorAll("[data-jb-map]").forEach((input) => {
      if (input.value.trim()) mapping[input.dataset.jbMap] = input.value.trim();
    });
    return mapping;
  }

  async function previewImport() {
    if (!requirePermission("can_edit")) return;
    const dialog = state.root.querySelector("[data-jb-import-dialog]");
    const startRow = dialog.querySelector("[data-jb-import-start-row]").value || "1";
    invalidateImportPreview();
    const serial = state.importPreviewSerial;
    const signature = importInputSignature();
    state.importPreviewPending = true;
    setResult("import", "Analizando filas…", "");
    try {
      let payload;
      let sheetOptions = null;
      if (state.importMode === "xlsx") {
        const file = dialog.querySelector("[data-jb-xlsx-file]").files?.[0];
        if (!file) throw new Error("Selecciona un fichero XLSX.");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("start_row", startRow);
        formData.append("mapping", JSON.stringify(importMapping()));
        const sheet = dialog.querySelector("[data-jb-import-sheet]").value;
        if (sheet) formData.append("sheet_name", sheet);
        const response = await request(apiPaths().xlsxPreview(), { method: "POST", body: formData });
        payload = response.preview || response;
        sheetOptions = { sheets: payload.sheets || [], selected: payload.sheet || sheet };
      } else {
        const text = dialog.querySelector("[data-jb-paste-text]").value;
        const response = await request(apiPaths().pastePreview(), { method: "POST", json: { text, start_row: startRow, mapping: importMapping() } });
        payload = response.preview || response;
      }
      if (serial !== state.importPreviewSerial) return;
      if (signature !== importInputSignature()) {
        invalidateImportPreview({ announce: true });
        return;
      }
      if (sheetOptions) populateSheetOptions(sheetOptions.sheets, sheetOptions.selected);
      state.importPreviewPending = false;
      state.importPreview = payload;
      state.importPreviewSignature = importInputSignature();
      renderImportPreview(payload);
    } catch (error) {
      if (serial !== state.importPreviewSerial) return;
      state.importPreviewPending = false;
      setResult("import", error.message, "error");
    }
  }

  function populateSheetOptions(sheets, selected) {
    const select = state.root.querySelector("[data-jb-import-sheet]");
    select.innerHTML = sheets.map((name) => `<option value="${escapeHtml(name)}" ${name === selected ? "selected" : ""}>${escapeHtml(name)}</option>`).join("");
  }

  function renderImportPreview(payload) {
    const target = state.root.querySelector("[data-jb-import-preview]");
    const products = payload.products || [];
    const issues = payload.issues || [];
    const rawRows = payload.rows || [];
    const rows = products.length ? products.map((product) => [product.name, product.characteristics, product.quantity, product.offered_unit_price, product.offered_amount_input]) : rawRows;
    target.innerHTML = `
      <p><strong>${escapeHtml(products.length || payload.row_count || 0)} fila(s)</strong>${payload.ignored_rows?.length ? ` · ${escapeHtml(payload.ignored_rows.length)} ignorada(s)` : ""}</p>
      <div class="jb-import-table-wrap"><table><tbody>${rows.slice(0, 50).map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      ${issues.length ? `<ul class="jb-import-issues">${issues.map((issue) => `<li class="jb-issue-${escapeHtml(issue.severity)}">Fila ${escapeHtml(issue.row_number)}: ${escapeHtml(issue.message)}</li>`).join("")}</ul>` : ""}
    `;
    const canConfirm = Boolean(products.length) && payload.can_confirm !== false;
    state.root.querySelector("[data-jb-confirm-import]").disabled = !canConfirm;
    applyPermissions();
    setResult("import", canConfirm ? "Previsualización válida. Revisa las filas antes de incorporarlas." : "Corrige los errores antes de confirmar.", canConfirm ? "ok" : "warning");
  }

  function confirmImport() {
    if (!requirePermission("can_edit")) return;
    if (!state.importPreviewSignature || state.importPreviewSignature !== importInputSignature()) {
      invalidateImportPreview({ announce: true });
      return;
    }
    const products = state.importPreview?.products || [];
    if (!products.length) return;
    collectDraft();
    const existing = new Set(state.current.products.map((item) => String(item.line_id)));
    products.forEach((product) => {
      let lineId = String(product.line_id || makeManualLineId());
      if (existing.has(lineId)) lineId = makeManualLineId();
      existing.add(lineId);
      state.current.products.push({ ...product, line_id: lineId });
    });
    state.current.draft.products = state.current.products;
    renderProducts();
    setDirty(true);
    scheduleLivePreview();
    state.root.querySelector("[data-jb-import-dialog]").close();
    setResult("editor", `${products.length} producto(s) incorporado(s). Guarda para validar el cálculo.`, "ok");
  }

  async function uploadRouteImage() {
    if (!requirePermission("can_edit")) return;
    const input = state.root.querySelector("[data-jb-route-image]");
    const file = input.files?.[0];
    if (!file) {
      setResult("editor", "Selecciona una imagen PNG o JPEG.", "warning");
      return;
    }
    if (state.busy) return;
    invalidateLivePreview();
    setBusy(true, "Validando y adjuntando imagen…");
    try {
      const saved = await ensureSaved({ withinMutation: true });
      if (!saved) return;
      const formData = new FormData();
      formData.append("revision", String(state.current.revision));
      formData.append("image", file);
      const response = await request(apiPaths().routeImage(state.current.id), { method: "POST", body: formData });
      applyServerItem(response);
      renderRouteImageState();
      setResult("editor", "Imagen de ruta adjuntada.", "ok");
    } catch (error) {
      if (error instanceof ConflictError) handleConflict(error);
      else setResult("editor", error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function attachExistingRouteImage() {
    if (!requirePermission("can_edit")) return;
    const relativePath = state.root.querySelector("[data-jb-route-relative-path]")?.value.trim() || "";
    if (!relativePath) {
      setResult("editor", "Indica una ruta relativa dentro de la carpeta de la licitación.", "warning");
      return;
    }
    if (state.busy) return;
    invalidateLivePreview();
    setBusy(true, "Validando la imagen existente…");
    try {
      const saved = await ensureSaved({ withinMutation: true });
      if (!saved) return;
      const response = await request(apiPaths().routeImage(state.current.id), {
        method: "POST",
        json: { revision: state.current.revision, relative_path: relativePath },
      });
      applyServerItem(response);
      renderRouteImageState();
      setResult("editor", "Imagen existente seleccionada y validada.", "ok");
    } catch (error) {
      if (error instanceof ConflictError) handleConflict(error);
      else setResult("editor", error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function freezeVersion() {
    if (!requirePermission("can_freeze")) return;
    const response = await performAction((id) => apiPaths().freeze(id), {}, "Congelando versión económica…", "Versión congelada. Ya puede generar Word y Excel.");
    if (response) renderVersions();
  }

  async function generateDocuments(version) {
    if (!requirePermission("can_generate_documents")) return;
    await performAction((id) => apiPaths().versionDocuments(id, version), {}, "Generando Word y Excel…", "Word y Excel generados desde el mismo snapshot.");
  }

  async function changeStatus() {
    if (!requirePermission("can_change_status")) return;
    const status = state.root.querySelector("[data-jb-status]").value;
    await performAction((id) => apiPaths().status(id), { state: status }, "Actualizando estado…", `Estado actualizado a ${STATUS_LABELS[status] || status}.`);
  }

  async function reloadAfterConflict() {
    if (!state.current?.id) return;
    await openExisting(state.current.id);
    setResult("editor", "Se ha cargado la última revisión del servidor.", "ok");
  }

  function handleInput(event) {
    if (event.target.closest("[data-jb-import-dialog]")) {
      invalidateImportPreview({ announce: true });
      return;
    }
    if (!event.target.closest("[data-jb-form]")) return;
    if (event.target.matches("[data-jb-select-line], [data-jb-select-all]")) return;
    invalidateLivePreview();
    if (event.target.name === "declared_lot_offer") {
      const base = state.root.querySelector('[name="general_expense_base"]');
      if (base && !base.value.trim()) base.value = event.target.value;
    }
    setDirty(true);
    if (event.target.matches("[data-live-economic], [data-product-field]")) scheduleLivePreview();
  }

  async function handleChange(event) {
    if (event.target.closest("[data-jb-import-dialog]")) {
      invalidateImportPreview({ announce: true });
      return;
    }
    if (event.target.closest("[data-jb-form]")) {
      invalidateLivePreview();
      if (event.target.matches("[data-live-economic], [data-product-field]")) {
        scheduleLivePreview();
      }
    }
    const client = event.target.closest("[data-jb-client]");
    if (client) await loadClientSnapshot(client.value);
    const line = event.target.closest("[data-jb-select-line]");
    if (line) {
      if (line.checked) state.selectedLineIds.add(String(line.dataset.jbSelectLine));
      else state.selectedLineIds.delete(String(line.dataset.jbSelectLine));
      updateSelectionCount();
    }
    if (event.target.matches("[data-jb-select-all]")) {
      state.selectedLineIds.clear();
      if (event.target.checked) (state.current?.products || []).forEach((product) => state.selectedLineIds.add(String(product.line_id)));
      renderProducts();
    }
  }

  async function handleClick(event) {
    const target = event.target;
    const open = target.closest("[data-jb-open]");
    if (open) return openExisting(open.dataset.jbOpen);
    if (target.closest("[data-jb-refresh-list]")) return loadList();
    if (target.closest("[data-jb-back-list]")) {
      return showListView();
    }
    if (target.closest("[data-jb-save]")) return saveCurrent();
    if (target.closest("[data-jb-reload-conflict]")) return reloadAfterConflict();
    if (target.closest("[data-jb-add-product]")) return addProduct();
    if (target.closest("[data-jb-open-xlsx]")) return openImport("xlsx");
    if (target.closest("[data-jb-open-paste]")) return openImport("paste");
    if (target.closest("[data-jb-close-import]")) return closeImport();
    if (target.closest("[data-jb-preview-import]")) return previewImport();
    if (target.closest("[data-jb-confirm-import]")) return confirmImport();
    if (target.closest("[data-jb-generate-costs]")) return generateCosts();
    if (target.closest("[data-jb-recalculate-selected]")) return recalculateCosts(true);
    if (target.closest("[data-jb-recalculate-unlocked]")) return recalculateCosts(false);
    if (target.closest("[data-jb-lock-selected]")) return setProductLock([...state.selectedLineIds], true);
    if (target.closest("[data-jb-unlock-selected]")) return setProductLock([...state.selectedLineIds], false);
    if (target.closest("[data-jb-upload-route-image]")) return uploadRouteImage();
    if (target.closest("[data-jb-attach-existing-route-image]")) return attachExistingRouteImage();
    if (target.closest("[data-jb-freeze]")) return freezeVersion();
    if (target.closest("[data-jb-change-status]")) return changeStatus();
    const documents = target.closest("[data-jb-generate-documents]");
    if (documents) return generateDocuments(documents.dataset.jbGenerateDocuments);
    const manual = target.closest("[data-jb-apply-manual]");
    if (manual) return applyManualCost(manual.dataset.jbApplyManual, manual);
    const removeManual = target.closest("[data-jb-remove-manual]");
    if (removeManual) return removeManualCost(removeManual.dataset.jbRemoveManual);
    const lock = target.closest("[data-jb-toggle-lock]");
    if (lock) return setProductLock([lock.dataset.jbToggleLock], lock.dataset.locked !== "1");
    const duplicate = target.closest("[data-jb-duplicate-product]");
    if (duplicate) return mutateProduct(duplicate.dataset.jbDuplicateProduct, "duplicate");
    const remove = target.closest("[data-jb-delete-product]");
    if (remove) return mutateProduct(remove.dataset.jbDeleteProduct, "delete");
    const move = target.closest("[data-jb-move-product]");
    if (move) return mutateProduct(move.dataset.jbMoveProduct, move.dataset.direction === "-1" ? "up" : "down");
  }

  function bindEvents() {
    state.root.addEventListener("click", (event) => { handleClick(event); });
    state.root.addEventListener("input", handleInput);
    state.root.addEventListener("change", (event) => { handleChange(event); });
    const search = state.root.querySelector("[data-jb-list-search]");
    let searchTimer = null;
    search.addEventListener("input", () => {
      global.clearTimeout(searchTimer);
      searchTimer = global.setTimeout(renderList, 150);
    });
    state.root.querySelector("[data-jb-list-status]").addEventListener("change", loadList);
    document.addEventListener("click", (event) => {
      const action = event.target.closest("[data-create-justificacion-baja]");
      if (action) openForLicitacion(action.dataset.createJustificacionBaja);
      const existing = event.target.closest("[data-open-justificaciones-baja]");
      if (existing) showListView({ licitacionId: existing.dataset.openJustificacionesBaja });
      const nav = event.target.closest("[data-nav-section='justificaciones-baja']");
      if (nav) {
        if (state.dirty && state.current) resumeDirtyEditor();
        else showListView();
      }
    });
    global.addEventListener("llangon:viewchange", (event) => {
      if (!state.section) return;
      const active = event.detail?.section === FEATURE_NAME;
      state.section.hidden = !active;
      if (!active) {
        invalidateLivePreview();
        cancelClientSnapshotLoad();
        cancelNavigationLoad();
        invalidateImportPreview();
      }
    });
    global.addEventListener("beforeunload", (event) => {
      if (!state.dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  function init(options = {}) {
    if (state.initialized) return global.JustificacionesBaja;
    state.bridge = options.bridge || options;
    state.apiBase = String(options.apiBase || DEFAULT_API_BASE).replace(/\/$/, "");
    ensureSection();
    bindEvents();
    state.initialized = true;
    return global.JustificacionesBaja;
  }

  global.JustificacionesBaja = Object.freeze({
    init,
    showList: showListView,
    showForLicitacion: (licitacionId) => showListView({ licitacionId }),
    openForLicitacion,
    openExisting,
    apiPaths,
  });
})(window);
