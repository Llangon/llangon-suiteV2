const accessScreen = document.getElementById("access-screen");
const accessForm = document.getElementById("access-form");
const accessCode = document.getElementById("access-code");
const accessError = document.getElementById("access-error");
const accessSubmit = document.getElementById("access-submit");
const portal = document.getElementById("portal");
const slug = decodeURIComponent(location.pathname.match(/^\/p\/([^/]+)$/)?.[1] || "");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function sourcePages(pages) {
  return Array.isArray(pages) && pages.length ? `<span class="source-pages">Ficha · ${pages.map((page) => `p. ${escapeHtml(page)}`).join(", ")}</span>` : "";
}

function renderBlock(block = {}) {
  if (block.type === "source_page") return `<article class="content-card source-page"><h3>Contenido íntegro · página ${escapeHtml(block.page)}</h3><div>${escapeHtml(block.text)}</div></article>`;
  if (block.type === "text") return `<article class="content-card">${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}${(block.paragraphs || []).map((value) => `<p>${escapeHtml(value)}</p>`).join("")}${(block.bullets || []).length ? `<ul>${block.bullets.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>` : ""}${sourcePages(block.sourcePages)}</article>`;
  if (block.type === "cards") return `<div class="mini-grid">${(block.items || []).map((item, index) => `<article><span>${String(index + 1).padStart(2, "0")}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.text)}</p></article>`).join("")}</div>${sourcePages(block.sourcePages)}`;
  if (block.type === "notice") return `<aside class="notice notice-${escapeHtml(block.tone || "neutral")}"><strong>${escapeHtml(block.title)}</strong><p>${escapeHtml(block.text)}</p>${sourcePages(block.sourcePages)}</aside>`;
  if (block.type === "criteria") return `<article class="content-card"><header class="criteria-head"><div><p>${escapeHtml(block.title)}</p><h3>${escapeHtml(block.scope)}</h3></div><strong>${escapeHtml(block.total)}</strong></header><div class="criteria-list">${(block.criteria || []).map((item) => `<div><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.description)}</small></span><strong>${escapeHtml(item.score)}</strong></div>`).join("")}</div>${sourcePages(block.sourcePages)}</article>`;
  return `<article class="content-card table-card">${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}${block.caption ? `<p>${escapeHtml(block.caption)}</p>` : ""}<div class="table-scroll"><table><thead><tr>${(block.columns || []).map((value) => `<th>${escapeHtml(value)}</th>`).join("")}</tr></thead><tbody>${(block.rows || []).map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${sourcePages(block.sourcePages)}</article>`;
}

function normalize(model, files) {
  const tender = model.tender || {};
  return { tender, sections: model.sections || [], coverage: model.coverage || {}, files };
}

function renderPortal(payload) {
  const { tender, sections, coverage, files } = normalize(payload.model || {}, payload.files || []);
  const deadline = tender.deadline || {};
  document.title = `${tender.reference || "Licitación"} · Llangón Asesores`;
  portal.innerHTML = `
    <a class="skip-link" href="#resumen">Saltar al contenido</a>
    <header class="site-header"><a href="#inicio"><img src="/static/logo-llangon.png" width="360" height="150" alt="Llangón Asesores"></a><nav><a href="#resumen">Resumen</a><a href="#descargas">Descargas</a></nav><button id="print-button" type="button">Imprimir</button></header>
    <section class="hero" id="inicio"><div class="hero-copy"><p class="eyebrow">Ficha de licitación</p>${tender.recipient ? `<p class="recipient">Preparada para ${escapeHtml(tender.recipient)}</p>` : ""}<h1>${escapeHtml(tender.title || "Licitación")}</h1><p>Expediente ${escapeHtml(tender.reference || "")}</p></div><aside class="deadline"><span>Presentación de ofertas</span><strong>${escapeHtml(deadline.day || "—")}</strong><b>${escapeHtml([deadline.month, deadline.year].filter(Boolean).join(" · "))}</b><small>${escapeHtml([deadline.weekday, deadline.time].filter(Boolean).join(" · "))}</small></aside></section>
    ${(tender.highlights || []).length ? `<section class="highlights">${tender.highlights.map((item) => `<article><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.detail)}</small></article>`).join("")}</section>` : ""}
    <section class="confidential"><strong>Información confidencial</strong><p>Información de uso exclusivo para su destinatario. El acceso y las descargas quedan registrados por motivos de trazabilidad.</p></section>
    ${(tender.details || []).length ? `<section class="content-section" id="resumen"><header><div><p class="eyebrow">Resumen</p><h2>Características de la licitación</h2></div>${sourcePages([1])}</header><div class="detail-grid">${tender.details.map((item) => `<article><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong>${item.note ? `<p>${escapeHtml(item.note)}</p>` : ""}</article>`).join("")}</div></section>` : ""}
    ${sections.map((section, index) => `<section class="content-section ${index % 2 ? "tint" : ""}" id="${escapeHtml(section.id)}"><header><div><p class="eyebrow">${escapeHtml(section.eyebrow || "Información")}</p><h2>${escapeHtml(section.title)}</h2>${section.introduction ? `<p>${escapeHtml(section.introduction)}</p>` : ""}</div>${sourcePages(section.sourcePages)}</header><div class="blocks">${(section.blocks || []).map(renderBlock).join("")}</div></section>`).join("")}
    <section class="content-section downloads" id="descargas"><header><div><p class="eyebrow">Documentación</p><h2>Descargas</h2></div><strong>${files.length} documentos</strong></header><div class="download-list">${files.map((file) => `<article><span>${escapeHtml(file.extension || "FILE")}</span><div><h3>${escapeHtml(file.name)}</h3><small>${Math.max(1, Math.round(Number(file.size_bytes || 0) / 1024))} KB</small></div><a href="/api/portal/${encodeURIComponent(slug)}/files/${encodeURIComponent(file.id)}">Descargar</a></article>`).join("")}</div></section>
    <section class="coverage"><strong>${escapeHtml(coverage.pages_audited || 0)}/${escapeHtml(coverage.pages_total || 0)}</strong><div><p class="eyebrow">Trazabilidad documental</p><h2>Ficha completa auditada</h2></div></section>
    <footer><img src="/static/logo-llangon.png" width="360" height="150" alt="Llangón Asesores"><p>Información preparada exclusivamente para ${escapeHtml(tender.recipient || "su destinatario")}.</p><span>info@llangon.com · ASESORES LLANGÓN, S.L.</span></footer>`;
  document.getElementById("print-button").addEventListener("click", () => window.print());
  accessScreen.hidden = true;
  portal.hidden = false;
}

async function loadPortal() {
  if (!slug) return;
  const response = await fetch(`/api/portal/${encodeURIComponent(slug)}`, { cache: "no-store" });
  if (response.ok) renderPortal(await response.json());
}

accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  accessError.hidden = true;
  accessSubmit.disabled = true;
  accessSubmit.textContent = "Comprobando…";
  const response = await fetch(`/api/portal/${encodeURIComponent(slug)}/access`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: accessCode.value }) });
  const result = await response.json().catch(() => ({}));
  if (response.ok) await loadPortal();
  else { accessError.textContent = result.error || "No se pudo validar el acceso."; accessError.hidden = false; }
  accessSubmit.disabled = false;
  accessSubmit.textContent = "Acceder";
});

void loadPortal();
