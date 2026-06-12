const configuredPrivateUrl = document.body?.dataset?.privateAppUrl || "";
const privateUrl = configuredPrivateUrl && configuredPrivateUrl !== "__PRIVATE_APP_URL__"
  ? configuredPrivateUrl
  : "/login";

document.querySelectorAll("[data-private-link]").forEach((link) => {
  link.href = privateUrl;
});

const menuToggle = document.querySelector(".menu-toggle");
const publicNav = document.getElementById("public-nav");
if (menuToggle && publicNav) {
  menuToggle.addEventListener("click", () => {
    const open = publicNav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(open));
  });
}

const coreServices = [
  ["Búsqueda de licitaciones", "Identificación de oportunidades acordes al perfil, actividad y solvencia del cliente."],
  ["Análisis de pliegos", "Revisión técnico-jurídica de requisitos, criterios, plazos, documentación y posibles riesgos."],
  ["Preparación documental", "Organización de anexos, declaraciones, documentación administrativa y documentación técnica."],
  ["Plantillas económicas", "Preparación de modelos y plantillas conforme al pliego, sin decidir precios ni bajas."],
  ["Subsanaciones y adjudicación", "Atención a requerimientos, subsanaciones y documentación previa a la adjudicación."],
  ["Recursos y ejecución contractual", "Apoyo en alegaciones, recursos y actuaciones vinculadas a la ejecución del contrato."],
];

const serviceDetails = [
  {
    title: "Búsqueda y selección de licitaciones",
    text: "Localizamos oportunidades de contratación pública acordes al perfil, actividad, solvencia y estrategia comercial de cada cliente. Analizamos anuncios, pliegos, lotes, requisitos de participación, criterios de adjudicación, plazos y documentación exigida.",
    points: ["Búsqueda de licitaciones en plataformas públicas.", "Revisión de objeto, CPV, lotes y presupuesto.", "Análisis de solvencia y requisitos de participación.", "Identificación de riesgos y oportunidades.", "Seguimiento de plazos."],
  },
  {
    title: "Análisis de pliegos",
    text: "Realizamos un análisis técnico-jurídico de los pliegos administrativos y técnicos, detectando obligaciones, criterios de valoración, documentación exigida, garantías, penalidades, condiciones especiales de ejecución y posibles aspectos impugnables.",
    points: ["Análisis de PCAP y PPT.", "Estudio de criterios automáticos y sujetos a juicio de valor.", "Detección de contradicciones o requisitos restrictivos.", "Preparación de consultas al órgano de contratación.", "Valoración de posibles impugnaciones o recursos frente a pliegos."],
  },
  {
    title: "Preparación de ofertas y documentación",
    text: "Preparamos y ordenamos la documentación necesaria para concurrir a licitaciones públicas, adaptando cada expediente a los anexos, modelos y exigencias concretas del pliego.",
    points: ["Elaboración de plantillas documentales.", "Preparación de anexos administrativos.", "Supervisión de documentación remitida por el cliente.", "Preparación de declaraciones responsables.", "Control de firmas, certificados y formatos.", "Organización de documentación por sobres o archivos electrónicos.", "Revisión previa a la presentación."],
  },
  {
    title: "Documentación administrativa",
    text: "Asistimos al cliente en la recopilación, revisión y preparación de la documentación administrativa exigida por los órganos de contratación.",
    points: ["Escrituras, poderes y bastanteos.", "Certificados de estar al corriente con la AEAT.", "Certificados de Seguridad Social.", "Certificados de alta en IAE.", "ROLECE y registros autonómicos.", "Garantías provisionales.", "Documentación de capacidad, representación y solvencia."],
  },
  {
    title: "Documentación técnica",
    text: "Colaboramos en la preparación y supervisión de documentación técnica, memorias, fichas, planes de trabajo y documentos justificativos, utilizando modelos estandarizados y adaptándolos a las exigencias concretas de cada pliego.",
    points: ["Memorias técnicas.", "Planes de prestación del servicio.", "Fichas técnicas.", "Compromisos de calidad.", "Planes de medios personales y materiales.", "Criterios de sostenibilidad, calidad, seguridad o medioambiente.", "Revisión de coherencia con el PPT."],
  },
  {
    title: "Plantillas y revisión formal de anexos económicos",
    text: "Preparamos plantillas y modelos de apoyo para que el cliente pueda cumplimentar su oferta económica conforme a los anexos y exigencias del pliego. Nuestro trabajo se limita al apoyo documental, formal y de revisión de coherencia.",
    points: ["Preparación de plantillas en Excel conforme a los anexos del pliego.", "Revisión de unidades, lotes, precios máximos y formatos exigidos.", "Control formal de IVA, importes unitarios, totales y subtotales.", "Revisión de fórmulas y criterios económicos previstos en el pliego.", "Comparativa de información pública de licitaciones anteriores, cuando proceda.", "Detección de posibles incoherencias formales o errores aritméticos.", "Apoyo en la cumplimentación documental de modelos económicos.", "Confirmación expresa de que la decisión económica corresponde siempre al cliente."],
    note: "ASESORES LLANGON, S.L. no decide ni fija los precios ofertados. La oferta económica es elaborada, decidida y validada siempre por la empresa licitadora.",
  },
  {
    title: "Consultas, subsanaciones y requerimientos",
    text: "Atendemos consultas, requerimientos de documentación, solicitudes de subsanación y comunicaciones de las mesas u órganos de contratación, preparando respuestas ordenadas y ajustadas a lo solicitado.",
    points: ["Preparación de consultas durante la licitación.", "Revisión de requerimientos.", "Preparación de escritos de subsanación.", "Recopilación documental.", "Control de plazos.", "Atención a comunicaciones de la plataforma.", "Seguimiento del expediente hasta su resolución."],
  },
  {
    title: "Justificación de ofertas anormales",
    text: "Apoyamos la preparación documental de justificaciones de ofertas incursas en presunción de anormalidad, tomando como base modelos estandarizados y siempre a partir de los datos, costes, medios y explicaciones facilitados por la propia empresa licitadora.",
    points: ["Ordenación de la documentación justificativa.", "Apoyo en el desglose documental de costes facilitados por el cliente.", "Preparación formal del escrito justificativo.", "Revisión de coherencia documental.", "Incorporación de medios, condiciones y explicaciones aportadas por la empresa.", "Control de plazos de respuesta."],
    note: "ASESORES LLANGON, S.L. no determina la viabilidad económica de la oferta ni sustituye al cliente en la explicación de sus costes, medios o márgenes.",
  },
  {
    title: "Propuesta de adjudicación y formalización",
    text: "Cuando el cliente resulta propuesto como adjudicatario, preparamos y revisamos la documentación necesaria para completar la adjudicación y formalizar el contrato.",
    points: ["Documentación previa a la adjudicación.", "Garantías definitivas.", "Depósitos en Caja General de Depósitos o tesorerías correspondientes.", "Certificados actualizados.", "Revisión del contrato antes de la firma.", "Control de plazos de adjudicación y formalización."],
  },
  {
    title: "Recursos, alegaciones e impugnaciones",
    text: "Estudiamos la viabilidad de recursos especiales en materia de contratación, recursos administrativos ordinarios, alegaciones y, en su caso, actuaciones vinculadas a exclusiones, adjudicaciones, desistimientos u otros actos del procedimiento.",
    points: ["Recursos frente a pliegos.", "Alegaciones frente a exclusiones.", "Recursos frente a adjudicaciones.", "Escritos frente a desistimientos.", "Defensa frente a requerimientos o decisiones de la mesa.", "Análisis de viabilidad jurídica."],
  },
  {
    title: "Asistencia durante la ejecución del contrato",
    text: "Aunque la actividad principal se desarrolla en la fase de licitación, en determinados casos prestamos apoyo durante la ejecución del contrato, especialmente cuando surgen incidencias, modificaciones, prórrogas, reclamaciones o discrepancias con la Administración.",
    points: ["Asistencia a reuniones con responsables del contrato.", "Reclamación de pagos.", "Intereses de demora.", "Modificaciones contractuales.", "Prórrogas o renuncias.", "Escritos por incidencias de ejecución.", "Recursos o reclamaciones durante la vida del contrato."],
  },
  {
    title: "Registros, plataformas y certificados",
    text: "Asistimos a empresas en altas y gestiones necesarias para poder licitar en plataformas y registros oficiales españoles.",
    points: ["Alta en ROLECE.", "Alta en la Plataforma de Contratación del Sector Público.", "Altas en plataformas autonómicas.", "Apoyo en certificados digitales.", "Coordinación con empresas de sistemas de calidad, seguridad o medioambiente.", "Apoyo en certificados de producto."],
  },
];

const methodology = [
  ["Identificación de oportunidades", "Revisión de licitaciones adecuadas al perfil del cliente, su actividad, solvencia y objetivos comerciales."],
  ["Análisis de viabilidad documental", "Estudio de pliegos, requisitos de participación, criterios de adjudicación, documentación exigida, riesgos y solvencia."],
  ["Planificación documental", "Creación de un índice de documentación, calendario interno, reparto de tareas y control de plazos."],
  ["Preparación de documentación", "Elaboración de anexos, plantillas, documentación administrativa, documentación técnica y revisión de coherencia global."],
  ["Presentación y seguimiento", "Apoyo en la presentación electrónica, seguimiento de comunicaciones, atención a requerimientos y subsanaciones."],
  ["Adjudicación, defensa o ejecución", "Preparación de documentación de adjudicación, revisión del contrato, recursos, alegaciones o asistencia posterior."],
];

const procurementTopics = [
  "Análisis de pliegos",
  "Solvencia y documentación",
  "Presentación electrónica",
  "Criterios de adjudicación",
  "Plantillas económicas y revisión formal",
  "Subsanaciones",
  "Recursos y alegaciones",
  "Ejecución contractual",
];

const placeholderNews = [
  {
    slug: "nueva-licitacion-suministro-publicada",
    title: "Nueva licitación de suministro publicada en la Plataforma de Contratación",
    date: "Pendiente de publicación",
    category: "Licitaciones",
    excerpt: "Ejemplo de noticia para maquetación. Sustituir por una publicación real desde la zona privada.",
    content: "Contenido provisional. Esta noticia sirve para revisar el diseño público de actualidad sin inventar expedientes reales.",
  },
  {
    slug: "aspectos-clave-revisar-oferta",
    title: "Aspectos clave a revisar antes de presentar una oferta",
    date: "Pendiente de publicación",
    category: "Documentación",
    excerpt: "Checklist orientativo para recordar la importancia de revisar plazos, anexos, firmas y requisitos del pliego.",
    content: "Contenido provisional. Antes de publicar una noticia real, completar desde la gestión privada de noticias.",
  },
  {
    slug: "control-plazos-subsanacion",
    title: "La importancia de controlar los plazos de subsanación",
    date: "Pendiente de publicación",
    category: "Procedimiento",
    excerpt: "La atención a requerimientos exige orden documental y control de comunicaciones de la plataforma.",
    content: "Contenido provisional. No contiene organismos ni expedientes reales.",
  },
];

const content = document.getElementById("public-content");
let publicNews = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeHref(value) {
  const text = String(value ?? "").trim();
  if (!text) return "#";
  if (text.startsWith("//")) return "#";
  if (text.startsWith("/") || text.startsWith("#")) return text;
  try {
    const url = new URL(text, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? text : "#";
  } catch {
    return "#";
  }
}

function button(label, href, variant = "button-primary") {
  return `<a class="button-link ${escapeHtml(variant)}" href="${escapeHtml(safeHref(href))}">${escapeHtml(label)}</a>`;
}

function sectionTitle(kicker, title, text) {
  return `<div class="section-title"><p class="kicker">${kicker}</p><h2>${title}</h2>${text ? `<p>${text}</p>` : ""}</div>`;
}

function cards(items) {
  return `<div class="cards-grid">${items.map((item, index) => `
    <article class="card">
      <span class="card-icon">${String(index + 1).padStart(2, "0")}</span>
      <h3>${item[0]}</h3>
      <p>${item[1]}</p>
    </article>
  `).join("")}</div>`;
}

function homePage() {
  return `
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-copy">
          <h1>Especialistas en contratación pública y asistencia en preparación de ofertas</h1>
          <p class="lead">Acompañamos a empresas en la búsqueda, análisis, preparación documental, presentación y seguimiento de procedimientos de contratación pública en España.</p>
          <div class="hero-actions">
            ${button("Ver servicios", "/servicios")}
            ${button("Acceso a zona privada", privateUrl, "button-secondary")}
          </div>
        </div>
        <div class="hero-proof" aria-label="Áreas de trabajo">
          <span>Análisis de pliegos</span>
          <span>Preparación documental</span>
          <span>Subsanaciones y adjudicación</span>
          <span>Seguimiento de expedientes</span>
        </div>
      </div>
    </section>
    ${aboutSection()}
    ${visualWorkSection()}
    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle("Servicios", "Apoyo especializado durante todo el procedimiento", "Servicios principales para ordenar, preparar, revisar y presentar documentación conforme a los pliegos.")}
        ${cards(coreServices)}
        <div class="section-actions">${button("Servicios especializados", "/servicios")}</div>
      </div>
    </section>
    ${methodologySection(true)}
    ${procurementSection(true)}
    ${newsSection(true)}
    ${privateAccessSection()}
    ${contactSection(true)}
  `;
}

function visualWorkSection() {
  return `
    <section class="visual-work-section">
      <div class="visual-work-image" role="img" aria-label="Mesa de trabajo con documentación de contratación pública"></div>
      <div class="visual-work-content">
        <p class="kicker">Ritmo de trabajo</p>
        <h2>Ordenar el expediente antes de que el plazo apriete.</h2>
        <p>Convertimos pliegos, anexos, certificados, comunicaciones y requisitos en una hoja de ruta documental clara. El objetivo es que cada licitación avance con método, responsables y control de vencimientos.</p>
        <div class="visual-checks">
          <span>Lectura rigurosa del pliego</span>
          <span>Índice documental por sobres</span>
          <span>Revisión formal antes de presentar</span>
        </div>
      </div>
    </section>
  `;
}

function aboutSection() {
  return `
    <section class="public-section">
      <div class="section-inner split-grid">
        <div>${sectionTitle("Quiénes somos", "Una firma centrada exclusivamente en contratación pública", "")}</div>
        <div class="text-block">
          <p>ASESORES LLANGON, S.L. es una firma especializada en el asesoramiento a empresas que participan en procedimientos de contratación pública en España.</p>
          <p>Nuestro trabajo se centra en el acompañamiento técnico, jurídico y documental durante las distintas fases de la licitación: desde la identificación de oportunidades y el análisis de pliegos hasta la preparación de documentación administrativa y técnica, la atención a requerimientos, la fase de adjudicación y determinadas actuaciones vinculadas a la ejecución contractual.</p>
          <p>Trabajamos con un enfoque práctico, ordenado y riguroso, orientado al control de plazos, la coherencia documental y la correcta presentación de la información exigida por los órganos de contratación.</p>
          <div class="highlight-line">Del análisis del pliego a la formalización del contrato.</div>
        </div>
      </div>
    </section>
  `;
}

function servicesPage() {
  return `
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("Servicios", "Servicios especializados en contratación pública", "Acompañamos a empresas en la preparación, presentación, seguimiento y defensa documental ante el sector público.")}
        <div class="services-list">
          ${serviceDetails.map((service) => `
            <article class="service-detail">
              <div>
                <h2>${service.title}</h2>
                <p>${service.text}</p>
                ${service.note ? `<div class="notice-box">${service.note}</div>` : ""}
              </div>
              <ul>${service.points.map((point) => `<li>${point}</li>`).join("")}</ul>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
  `;
}

function methodologySection(compact = false) {
  return `
    <section class="public-section ${compact ? "" : "light-band"}">
      <div class="section-inner">
        ${sectionTitle("Metodología", "Una metodología orientada al control documental y al cumplimiento de plazos", "Cada expediente se aborda con una planificación clara, revisión de requisitos, preparación documental ordenada y seguimiento de comunicaciones hasta la finalización del procedimiento.")}
        <div class="method-grid">
          ${methodology.map((step, index) => `
            <article class="method-step">
              <span class="method-number">${index + 1}</span>
              <h3>${step[0]}</h3>
              <p>${step[1]}</p>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
  `;
}

function methodologyPage() {
  return methodologySection(false);
}

function procurementSection(compact = false) {
  return `
    <section class="public-section ${compact ? "light-band" : ""}">
      <div class="section-inner">
        ${sectionTitle("Contratación pública", "Precisión, orden documental y conocimiento práctico", "Una licitación no se limita a presentar un precio: exige interpretar pliegos, cumplir requisitos de capacidad y solvencia, preparar documentación administrativa y técnica, controlar plazos, responder a requerimientos y valorar posibles recursos.")}
        <div class="text-block">
          <p>ASESORES LLANGON, S.L. acompaña a sus clientes en ese proceso, ayudando a reducir errores formales, mejorar la calidad de la documentación presentada y tomar decisiones informadas en cada fase del expediente.</p>
          <p>En España, los procedimientos se rigen por la normativa de contratación pública, especialmente la Ley 9/2017, de Contratos del Sector Público. Nuestro enfoque traduce esa complejidad en planificación documental, revisión formal y seguimiento ordenado.</p>
        </div>
        <div class="procurement-grid">
          ${procurementTopics.map((topic) => `<div class="mini-card"><strong>${topic}</strong></div>`).join("")}
        </div>
      </div>
    </section>
  `;
}

function procurementPage() {
  return procurementSection(false);
}

function visibleNews() {
  return publicNews && publicNews.length ? publicNews : placeholderNews;
}

function newsCards(items = visibleNews().slice(0, 3)) {
  return `<div class="news-grid">${items.map((news) => `
    <a class="news-card" href="/noticias/${encodeURIComponent(news.slug)}">
      <span class="news-meta">${escapeHtml(news.category || "Actualidad")} · ${escapeHtml(news.date || news.publishedAtFormatted || "Pendiente de publicación")}</span>
      <h3>${escapeHtml(news.title)}</h3>
      <p>${escapeHtml(news.excerpt)}</p>
      <strong>Leer más</strong>
    </a>
  `).join("")}</div>`;
}

function newsSection(compact = false) {
  return `
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle(compact ? "Actualidad destacada" : "Noticias", compact ? "Actualidad destacada" : "Actualidad sobre contratación pública, licitaciones y novedades relevantes", compact ? "Selección de publicaciones recientes o destacadas." : "Licitaciones relevantes, novedades normativas, criterios prácticos y recomendaciones documentales para empresas.")}
        ${newsCards(compact ? visibleNews().slice(0, 3) : visibleNews())}
        ${compact ? `<div class="section-actions">${button("Ver todas las noticias", "/noticias", "button-secondary")}</div>` : ""}
      </div>
    </section>
  `;
}

function newsDetailPage(slug) {
  const item = visibleNews().find((news) => news.slug === slug) || placeholderNews.find((news) => news.slug === slug) || placeholderNews[0];
  const paragraphs = String(item.content || "").split(/\n+/).filter(Boolean);
  return `
    <section class="public-section">
      <div class="section-inner">
        <p class="kicker">${escapeHtml(item.category || "Actualidad")} · ${escapeHtml(item.date || item.publishedAtFormatted || "Pendiente de publicación")}</p>
        <h1>${escapeHtml(item.title)}</h1>
        <p class="lead">${escapeHtml(item.excerpt)}</p>
        <div class="legal-box">
          ${paragraphs.length ? paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("") : `<p>Contenido pendiente de completar.</p>`}
          ${publicNews && publicNews.length ? "" : "<p>Las noticias reales se publicarán desde la gestión privada de LLANGON WEB APP.</p>"}
        </div>
        <div class="section-actions">${button("Volver a noticias", "/noticias", "button-secondary")}</div>
      </div>
    </section>
  `;
}

function privateAccessSection() {
  return `
    <section class="public-section">
      <div class="section-inner">
        <div class="private-panel">
          <div>
            <p class="kicker">Zona privada</p>
            <h2>LLANGON WEB APP</h2>
            <p>Zona privada para clientes. Permitirá acceder de forma segura a información, documentación y seguimiento de expedientes mediante usuario y contraseña.</p>
            <div class="section-actions">${button("Acceso a zona privada", privateUrl)}</div>
          </div>
          <div class="private-features">
            <span>Acceso seguro</span>
            <span>Seguimiento de expedientes</span>
            <span>Documentación organizada</span>
            <span>Comunicaciones y avisos</span>
            <span>Control de plazos</span>
            <span>Área privada de cliente</span>
          </div>
        </div>
      </div>
    </section>
  `;
}

function contactSection(compact = false) {
  return `
    <section class="public-section ${compact ? "light-band" : ""}">
      <div class="section-inner">
        ${sectionTitle("Contacto", "Cuéntenos qué procedimiento, licitación o necesidad documental tiene", "Estudiaremos cómo podemos ayudarle desde el análisis del pliego hasta la preparación y seguimiento documental.")}
        <div class="contact-grid">
          <form class="contact-form" id="contact-form" novalidate>
            <label>Nombre<input name="name" required></label>
            <label>Empresa<input name="company"></label>
            <label>Email<input name="email" type="email" required></label>
            <label>Teléfono<input name="phone"></label>
            <label>Mensaje<textarea name="message" rows="5" required></textarea></label>
            <label class="check-field"><input name="privacy" type="checkbox" required><span>Acepto la política de privacidad.</span></label>
            <p class="form-message" id="contact-message" aria-live="polite"></p>
            <button class="button-link button-primary" type="submit">Enviar consulta</button>
          </form>
          <aside class="contact-note">
            <h3>ASESORES LLANGON, S.L.</h3>
            <p>Especialistas en contratación pública.</p>
            <p>España.</p>
            <p>Email: [pendiente de completar]</p>
            <p>Teléfono: [pendiente de completar]</p>
            <p>Dirección: [pendiente de completar]</p>
          </aside>
        </div>
      </div>
    </section>
  `;
}

function legalPage(kind) {
  const titles = {
    "/aviso-legal": "Aviso legal",
    "/politica-privacidad": "Política de privacidad",
    "/politica-cookies": "Política de cookies",
  };
  return `
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("Información legal", titles[kind] || "Información legal", "Texto provisional pendiente de revisión antes de publicación definitiva.")}
        <div class="legal-box">
          <p>Este contenido es un placeholder profesional y debe ser completado y revisado antes de la publicación definitiva de la web.</p>
          <ul>
            <li>ASESORES LLANGON, S.L.</li>
            <li>CIF: [Completar CIF]</li>
            <li>Domicilio social: [Completar domicilio social]</li>
            <li>Email de contacto: [Completar email de contacto]</li>
            <li>Datos registrales: [Completar datos registrales]</li>
          </ul>
          <p>No se han incluido datos fiscales, registrales o de contacto no facilitados.</p>
        </div>
      </div>
    </section>
  `;
}

function setMeta(title, description) {
  document.title = title;
  const meta = document.querySelector("meta[name='description']");
  if (meta) meta.setAttribute("content", description);
}

function render() {
  const path = location.pathname.replace(/\/$/, "") || "/";
  let html = "";
  let title = "ASESORES LLANGON, S.L. | Especialistas en contratación pública";
  let description = "Asesoramiento a empresas en contratación pública en España.";

  if (path === "/") html = homePage();
  else if (path === "/servicios") html = servicesPage();
  else if (path === "/metodologia") html = methodologyPage();
  else if (path === "/contratacion-publica") html = procurementPage();
  else if (path === "/noticias") html = newsSection(false);
  else if (path.startsWith("/noticias/")) html = newsDetailPage(decodeURIComponent(path.split("/").pop()));
  else if (path === "/zona-privada") html = privateAccessSection();
  else if (path === "/contacto") html = contactSection(false);
  else if (["/aviso-legal", "/politica-privacidad", "/politica-cookies"].includes(path)) html = legalPage(path);
  else html = homePage();

  if (path === "/servicios") {
    title = "Servicios de contratación pública | ASESORES LLANGON, S.L.";
    description = "Servicios especializados para empresas: búsqueda, análisis de pliegos, preparación documental, subsanaciones, adjudicación, recursos y ejecución.";
  } else if (path === "/metodologia") {
    title = "Metodología | ASESORES LLANGON, S.L.";
    description = "Metodología de trabajo orientada al control documental y al cumplimiento de plazos en licitaciones públicas.";
  } else if (path === "/noticias") {
    title = "Noticias de contratación pública | ASESORES LLANGON, S.L.";
    description = "Actualidad sobre contratación pública, licitaciones y novedades relevantes para empresas.";
  } else if (path === "/contacto") {
    title = "Contacto | ASESORES LLANGON, S.L.";
    description = "Contacte con ASESORES LLANGON, S.L. para consultas relacionadas con contratación pública en España.";
  }

  content.innerHTML = html;
  setMeta(title, description);
  wireContactForm();
}

function wireContactForm() {
  const form = document.getElementById("contact-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = document.getElementById("contact-message");
    if (!form.reportValidity()) return;
    if (message) {
      message.textContent = "Gracias por contactar con ASESORES LLANGON, S.L. Hemos recibido su consulta.";
    }
    form.reset();
  });
}

render();

fetch("/api/public/noticias")
  .then((response) => response.ok ? response.json() : { items: [] })
  .then((data) => {
    publicNews = Array.isArray(data.items) ? data.items : [];
    if (location.pathname === "/" || location.pathname.startsWith("/noticias")) {
      render();
    }
  })
  .catch(() => {});
