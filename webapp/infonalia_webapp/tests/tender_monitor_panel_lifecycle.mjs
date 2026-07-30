import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, "..", "static", "tender_monitor.js"), "utf8");

async function settle(turns = 30) {
  for (let index = 0; index < turns; index += 1) await Promise.resolve();
}

function abortError() {
  const error = new Error("The operation was aborted.");
  error.name = "AbortError";
  return error;
}

function response(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function createHarness(detailPlans = [{ status: 200 }]) {
  const panels = [];
  const observers = [];
  const listenerCounts = new Map();
  const plans = [...detailPlans];
  let detailRequests = 0;
  let abortedRequests = 0;
  let mutationDeliveries = 0;

  class FakeChild {
    constructor() {
      this.nodeType = 1;
      this.isConnected = true;
    }

    matches() { return false; }
    querySelectorAll() { return []; }
  }

  const deliver = (records) => {
    queueMicrotask(() => {
      mutationDeliveries += 1;
      if (mutationDeliveries > 80) return;
      observers.filter((item) => item.active).forEach((item) => item.callback(records));
    });
  };

  class FakePanel {
    constructor(id) {
      this.nodeType = 1;
      this.dataset = { tenderMonitorPanelCard: String(id) };
      this.isConnected = false;
      this._innerHTML = '<div class="empty">Cargando monitor…</div>';
    }

    matches(selector) {
      return selector === "[data-tender-monitor-panel-card]";
    }

    querySelectorAll() { return []; }

    get innerHTML() { return this._innerHTML; }

    set innerHTML(value) {
      this._innerHTML = String(value);
      if (this.isConnected) {
        deliver([{ type: "childList", target: this, addedNodes: [new FakeChild()], removedNodes: [] }]);
      }
    }
  }

  class FakeMutationObserver {
    constructor(callback) {
      this.callback = callback;
      this.active = false;
      observers.push(this);
    }

    observe() { this.active = true; }
    disconnect() { this.active = false; }
  }

  const document = {
    body: new FakeChild(),
    getElementById: () => null,
    querySelectorAll(selector) {
      const exact = selector.match(/^\[data-tender-monitor-panel-card="([^"]+)"\]$/);
      if (exact) {
        return panels.filter((panel) => panel.isConnected && panel.dataset.tenderMonitorPanelCard === exact[1]);
      }
      if (selector === "[data-tender-monitor-panel-card]") {
        return panels.filter((panel) => panel.isConnected);
      }
      return [];
    },
    addEventListener(type) {
      listenerCounts.set(type, (listenerCounts.get(type) || 0) + 1);
    },
  };

  async function fetch(url, options = {}) {
    if (url === "/api/me") {
      return response(200, { username: "admin", role: "admin", csrf_token: "csrf" });
    }
    if (!String(url).startsWith("/api/tender-monitor/licitaciones/335")) {
      throw new Error(`Unexpected fetch: ${url}`);
    }
    detailRequests += 1;
    const plan = plans.shift() || { status: 200 };
    if (plan.error) throw plan.error;
    if (plan.deferred) {
      return new Promise((resolve, reject) => {
        const signal = options.signal;
        if (signal?.aborted) {
          abortedRequests += 1;
          reject(abortError());
          return;
        }
        signal?.addEventListener("abort", () => {
          abortedRequests += 1;
          reject(abortError());
        }, { once: true });
        plan.resolve = () => resolve(response(plan.status || 200, plan.payload || successPayload()));
      });
    }
    return response(plan.status || 200, plan.payload || (plan.status >= 400 ? {} : successPayload()));
  }

  function successPayload() {
    return {
      monitor: { followed: true, prepared: true, reason: "" },
      executions: [],
    };
  }

  const window = {
    setTimeout,
    clearTimeout,
    confirm: () => true,
    dispatchEvent: () => true,
  };
  window.window = window;
  const context = vm.createContext({
    AbortController,
    CustomEvent: class CustomEvent { constructor(type, init) { this.type = type; this.detail = init?.detail; } },
    Date,
    FormData: class FormData { forEach() {} },
    Map,
    MutationObserver: FakeMutationObserver,
    Promise,
    Set,
    String,
    URLSearchParams,
    WeakMap,
    WeakSet,
    console,
    document,
    encodeURIComponent,
    fetch,
    queueMicrotask,
    window,
  });
  vm.runInContext(source, context, { filename: "tender_monitor.js" });

  function insert(panel) {
    panel.isConnected = true;
    panels.push(panel);
    deliver([{ type: "childList", target: document.body, addedNodes: [panel], removedNodes: [] }]);
  }

  function remove(panel) {
    panel.isConnected = false;
    const index = panels.indexOf(panel);
    if (index >= 0) panels.splice(index, 1);
    deliver([{ type: "childList", target: document.body, addedNodes: [], removedNodes: [panel] }]);
  }

  return {
    context,
    insert,
    remove,
    panel: (id = 335) => new FakePanel(id),
    deliverInternal(panel, count = 1) {
      for (let index = 0; index < count; index += 1) {
        deliver([{ type: "childList", target: panel, addedNodes: [new FakeChild()], removedNodes: [] }]);
      }
    },
    stats: () => ({
      abortedRequests,
      detailRequests,
      listenerCounts: Object.fromEntries(listenerCounts),
      observerCount: observers.length,
    }),
  };
}

async function testSingleRequestIgnoresInternalRendering() {
  const harness = createHarness();
  const panel = harness.panel();
  harness.insert(panel);
  harness.deliverInternal(panel, 4);
  await settle(100);

  assert.equal(harness.stats().detailRequests, 1, "inserting one panel must issue one detail request");
  assert.equal(panel.dataset.monitorInitialized, "1", "the panel must be marked before loading");
  panel.innerHTML = '<div class="empty">Cargando monitor…</div>';
  harness.deliverInternal(panel, 5);
  await settle(100);
  assert.equal(harness.stats().detailRequests, 1, "loading/success/internal mutations must not reload the panel");
}

async function testErrorsRenderOnceWithoutRetry() {
  for (const item of [
    { plan: { status: 500 }, message: "Error HTTP 500" },
    { plan: { status: 502 }, message: "Error HTTP 502" },
    { plan: { error: new Error("Fallo de red") }, message: "Fallo de red" },
  ]) {
    const harness = createHarness([item.plan]);
    const panel = harness.panel();
    harness.insert(panel);
    await settle(100);

    assert.equal(harness.stats().detailRequests, 1, `${item.message} must not be retried`);
    assert.equal((panel.innerHTML.match(new RegExp(item.message, "g")) || []).length, 1, `${item.message} must render once`);
    harness.deliverInternal(panel, 6);
    await settle(100);
    assert.equal(harness.stats().detailRequests, 1, "error rendering must not reload the panel");
  }
}

async function testConcurrentMutationAbortAndLegitimateReopen() {
  const firstPlan = { deferred: true, status: 200 };
  const harness = createHarness([firstPlan, { status: 200 }, { status: 200 }]);
  const first = harness.panel();
  const duplicate = harness.panel();
  harness.insert(first);
  harness.insert(duplicate);
  harness.deliverInternal(first, 5);
  await settle(30);
  assert.equal(harness.stats().detailRequests, 1, "concurrent panels must reuse the in-flight request");

  harness.remove(first);
  await settle(30);
  assert.equal(harness.stats().abortedRequests, 0, "a shared request must remain while another panel is mounted");
  harness.remove(duplicate);
  await settle(30);
  assert.equal(harness.stats().abortedRequests, 1, "removing the panel must abort its request");

  const second = harness.panel();
  harness.insert(second);
  await settle(100);
  assert.equal(harness.stats().detailRequests, 2, "reopening must issue one fresh request");

  harness.remove(second);
  const third = harness.panel();
  harness.insert(third);
  await settle(100);
  assert.equal(harness.stats().detailRequests, 3, "a second legitimate reopen must still issue only one request");

  vm.runInContext(source, harness.context, { filename: "tender_monitor_second_load.js" });
  assert.equal(harness.stats().observerCount, 1, "module re-entry must not duplicate the observer");
  assert.equal(harness.stats().listenerCounts.click, 1, "module re-entry must not duplicate click delegation");
  assert.equal(harness.stats().listenerCounts.submit, 1, "module re-entry must not duplicate submit delegation");
}

await testSingleRequestIgnoresInternalRendering();
await testErrorsRenderOnceWithoutRetry();
await testConcurrentMutationAbortAndLegitimateReopen();
console.log("tender monitor panel lifecycle: ok");
