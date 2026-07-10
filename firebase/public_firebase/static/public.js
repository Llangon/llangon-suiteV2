const configuredPrivateUrl = document.body?.dataset?.privateAppUrl || "";
const privateUrl = configuredPrivateUrl && configuredPrivateUrl !== "__PRIVATE_APP_URL__"
  ? configuredPrivateUrl
  : "/login";

const companyInfo = {
  name: "ASESORES LLANGON, S.L.",
  cif: "B73803637",
  postalAddress: "C/ ULIA, 9, 1ºD, 41005, SEVILLA",
  email: "info@llangon.com",
  phone: "617 11 02 81",
  phoneHref: "tel:+34617110281",
};

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

const homePainPoints = [
  ["Pliegos extensos y difíciles de interpretar", "Un requisito mal leído puede convertir una oportunidad en una exclusión."],
  ["Documentación dispersa", "Anexos, declaraciones, solvencia, fichas técnicas, memorias y certificados deben prepararse con orden y coherencia."],
  ["Plazos que no perdonan", "Una subsanación, un requerimiento o una garantía fuera de plazo puede hacer perder meses de trabajo."],
  ["Decisiones económicas sin información suficiente", "No basta con decidir un precio. Hay que entender presupuestos máximos, fórmulas, criterios y antecedentes públicos cuando existan."],
];

const homeServices = [
  ["Búsqueda y selección de oportunidades", "Localizamos licitaciones que encajan con la actividad, zona, solvencia y capacidad operativa de la empresa."],
  ["Análisis de pliegos", "Revisamos requisitos administrativos, técnicos, económicos, criterios de adjudicación, garantías, plazos y riesgos del expediente."],
  ["Preparación administrativa", "Organizamos declaraciones, anexos, acreditaciones, certificados y documentación exigida para concurrir."],
  ["Documentación técnica", "Redactamos memorias, planes, fichas y documentos técnicos a partir de la información y soporte facilitados por el cliente."],
  ["Herramientas para la oferta económica", "Facilitamos plantillas, fórmulas, cuadros de análisis e información pública para que el cliente pueda decidir."],
  ["Presentación y seguimiento", "Acompañamos la presentación y realizamos seguimiento de aperturas, subsanaciones, requerimientos, adjudicación y formalización."],
];

const homeBenefits = [
  ["Más oportunidades reales", "Filtramos licitaciones para que tu equipo no pierda tiempo con expedientes que no encajan."],
  ["Menos riesgo de exclusión", "Revisamos requisitos, plazos, formatos y documentación para reducir errores evitables."],
  ["Más control interno", "Cada licitación se convierte en un proceso ordenado, con tareas, documentación y fechas claras."],
  ["Menos carga administrativa", "Tu empresa puede centrarse en su actividad mientras coordinamos la preparación documental."],
  ["Mejor lectura del expediente", "Traducimos el lenguaje del pliego a decisiones prácticas: qué exige, qué implica y qué preparar."],
  ["Un canal de ventas más profesionalizado", "La contratación pública puede convertirse en una vía estable de crecimiento si se trabaja con método y continuidad."],
];

const homeProcess = [
  ["Analizamos tu empresa", "Actividad, productos o servicios, solvencia, experiencia, zonas de interés y capacidad real de ejecución."],
  ["Localizamos oportunidades", "Buscamos y filtramos licitaciones que puedan encajar con tu perfil."],
  ["Revisamos el pliego", "Identificamos requisitos, riesgos, documentación, criterios, plazos y puntos críticos."],
  ["Preparamos la documentación", "Coordinamos la parte administrativa y redactamos documentación técnica con la información aportada por el cliente."],
  ["Facilitamos herramientas económicas", "Preparamos plantillas, fórmulas y referencias públicas para que el cliente valore su oferta."],
  ["Presentamos y seguimos", "Acompañamos el envío y controlamos subsanaciones, requerimientos, adjudicación y formalización."],
];

const trustPoints = [
  "Rigor jurídico sin lenguaje innecesariamente complejo.",
  "Control documental desde el primer análisis.",
  "Comunicación clara con el cliente.",
  "Herramientas prácticas para tomar mejores decisiones.",
  "Confidencialidad y trazabilidad en cada expediente.",
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

function companyIdentityList({ includePhone = false, includeRegistry = false } = {}) {
  return `
    <ul>
      <li><strong>Titular:</strong> ${companyInfo.name}</li>
      <li><strong>CIF:</strong> ${companyInfo.cif}</li>
      <li><strong>Dirección postal:</strong> ${companyInfo.postalAddress}</li>
      <li><strong>Correo electrónico:</strong> <a href="mailto:${companyInfo.email}">${companyInfo.email}</a></li>
      ${includePhone ? `<li><strong>Teléfono:</strong> <a href="${companyInfo.phoneHref}">${companyInfo.phone}</a></li>` : ""}
      ${includeRegistry ? "<li><strong>Datos registrales:</strong> pendiente de incorporar tras confirmación.</li>" : ""}
    </ul>
  `;
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
          <p class="kicker">Asesoría especializada en licitaciones públicas</p>
          <h1>Convierte la contratación pública en un canal de crecimiento para tu empresa</h1>
          <p class="lead">En ASESORES LLANGON ayudamos a empresas a localizar, analizar y preparar licitaciones públicas con rigor jurídico, control documental y una visión práctica del negocio.</p>
          <p class="hero-support">Te acompañamos desde el análisis del pliego hasta la presentación y seguimiento del expediente, para que puedas competir con más seguridad, menos carga interna y una oferta mejor preparada.</p>
          <div class="hero-actions">
            ${button("Solicitar valoración", "/contacto")}
            ${button("Ver servicios", "/servicios", "button-secondary")}
          </div>
          <p class="hero-microcopy">Primera revisión orientativa · Atención directa · Licitaciones públicas en España</p>
        </div>
        <div class="hero-proof" aria-label="Áreas de trabajo">
          <span>Análisis de pliegos</span>
          <span>Control documental</span>
          <span>Herramientas económicas</span>
          <span>Seguimiento del expediente</span>
        </div>
      </div>
    </section>
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("El problema", "Presentarse a una licitación no debería depender de tener tiempo libre", "Los contratos públicos son una oportunidad enorme, pero también exigen plazos, documentación, solvencia, plataformas electrónicas y una lectura precisa de los pliegos.")}
        <div class="compact-card-grid">
          ${homePainPoints.map((item) => `
            <article class="compact-card">
              <h3>${item[0]}</h3>
              <p>${item[1]}</p>
            </article>
          `).join("")}
        </div>
        <div class="highlight-line">Nuestro trabajo es convertir ese proceso en una hoja de ruta clara, controlada y comprensible para la empresa.</div>
      </div>
    </section>
    <section class="public-section law-section light-band">
      <div class="section-inner law-grid">
        <div>
          <p class="kicker">Ley 9/2017</p>
          <h2>La contratación pública permite competir en igualdad de condiciones</h2>
        </div>
        <div class="text-block">
          <p>La contratación pública se basa en principios como transparencia, igualdad de trato, libre competencia y mejor relación calidad-precio. Dominar esas reglas permite presentarse con más seguridad y criterio.</p>
          <p>La <a href="https://www.boe.es/buscar/act.php?id=BOE-A-2017-12902" target="_blank" rel="noopener noreferrer">Ley 9/2017, de Contratos del Sector Público</a>, es el marco que permite a empresas privadas acceder a contratos con administraciones, organismos públicos y entidades del sector público bajo reglas claras.</p>
          <p>En ASESORES LLANGON trabajamos cada expediente desde esa base: analizamos pliegos, identificamos requisitos, controlamos documentación y ayudamos a que la empresa pueda competir de forma ordenada y profesional.</p>
          <div class="notice-box">Contratación pública no significa burocracia inaccesible. Significa un mercado regulado donde la preparación marca la diferencia.</div>
          <div class="section-actions">${button("Quiero competir con más seguridad", "/contacto")}</div>
        </div>
      </div>
    </section>
    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle("Qué hacemos", "Te ayudamos a preparar licitaciones con criterio, orden y seguridad", "No somos un simple servicio de búsqueda de concursos. Acompañamos a la empresa en las fases clave del procedimiento.")}
        ${cards(homeServices)}
        <div class="section-actions">${button("Ver todos los servicios", "/servicios")}</div>
      </div>
    </section>
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("Criterio profesional", "Asesoramiento experto, decisiones empresariales claras", "Preparamos, ordenamos y redactamos documentación para que la empresa pueda concurrir con más seguridad, manteniendo una separación clara entre asesoramiento y decisiones del licitador.")}
        <div class="two-column-panel">
          <article>
            <h3>Documentación técnica</h3>
            <p>Redactamos y elaboramos documentación técnica a partir de la información, documentación y soporte que proporciona el cliente.</p>
            <p>Ayudamos a presentar esa información de forma clara, coherente y adaptada a los criterios del pliego.</p>
          </article>
          <article>
            <h3>Oferta económica</h3>
            <p>Proporcionamos herramientas de análisis, plantillas, fórmulas, comparativas e información pública disponible.</p>
            <p>La decisión sobre precios, descuentos, márgenes e importe final corresponde siempre al cliente.</p>
          </article>
        </div>
        <div class="highlight-line">Esta forma de trabajar protege a la empresa, refuerza la trazabilidad del expediente y permite competir con mayor seguridad.</div>
      </div>
    </section>
    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle("Beneficios", "Lo que gana tu empresa al trabajar con ASESORES LLANGON", "")}
        <div class="compact-card-grid">
          ${homeBenefits.map((item) => `
            <article class="compact-card">
              <h3>${item[0]}</h3>
              <p>${item[1]}</p>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("Método", "De la oportunidad al expediente presentado", "Un procedimiento complejo se entiende mejor cuando cada fase está ordenada.")}
        <div class="method-grid">
          ${homeProcess.map((step, index) => `
            <article class="method-step">
              <span class="method-number">${index + 1}</span>
              <h3>${step[0]}</h3>
              <p>${step[1]}</p>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle("Modalidades", "Un servicio adaptado a tu forma de licitar", "")}
        <div class="work-mode-grid">
          <article class="work-mode-card">
            <h3>Gestión continuada de licitaciones</h3>
            <p>Para empresas que quieren incorporar la contratación pública como canal estable de ventas. Incluye vigilancia de oportunidades, análisis de pliegos, preparación documental y seguimiento recurrente.</p>
            <div class="section-actions">${button("Quiero externalizar licitaciones", "/contacto", "button-secondary")}</div>
          </article>
          <article class="work-mode-card">
            <h3>Apoyo por expediente</h3>
            <p>Para empresas que tienen una licitación concreta y necesitan ayuda en una o varias fases: análisis del pliego, documentación administrativa, documentación técnica, herramientas económicas o seguimiento posterior.</p>
            <div class="section-actions">${button("Tengo una licitación en marcha", "/contacto", "button-secondary")}</div>
          </article>
        </div>
      </div>
    </section>
    <section class="public-section">
      <div class="section-inner split-grid">
        <div>${sectionTitle("Confianza", "Especialización práctica en contratación pública", "")}</div>
        <div class="text-block">
          <p>ASESORES LLANGON, S.L. trabaja con empresas que necesitan competir en licitaciones públicas sin asumir internamente toda la carga administrativa, técnica y documental que exige el procedimiento.</p>
          <p>Nuestro enfoque combina conocimiento normativo, experiencia práctica en expedientes, claridad en la comunicación y control de cada fase.</p>
          <p>No prometemos adjudicaciones. Preparamos mejor el camino para que tu empresa pueda competir con seriedad, seguridad y criterio.</p>
          <div class="trust-list">
            ${trustPoints.map((point) => `<span>${point}</span>`).join("")}
          </div>
        </div>
      </div>
    </section>
    <section class="public-section final-cta light-band">
      <div class="section-inner">
        <p class="kicker">Primera valoración</p>
        <h2>¿Quieres saber si una licitación merece la pena?</h2>
        <p>Envíanos el enlace, número de expediente o una breve descripción de la oportunidad. Revisaremos el caso y te diremos cómo podemos ayudarte.</p>
        <div class="section-actions">
          ${button("Solicitar valoración", "/contacto")}
          <a class="button-link button-secondary" href="mailto:info@llangon.com">Contactar por email</a>
        </div>
        <p class="hero-microcopy">También puedes escribirnos directamente a <a href="mailto:info@llangon.com">info@llangon.com</a></p>
      </div>
    </section>
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

function newsBodyHtml(item) {
  const trustedHtml = String(item.contentHtml || "").trim();
  if (trustedHtml) return trustedHtml;
  const paragraphs = String(item.content || "").split(/\n+/).filter(Boolean);
  return paragraphs.length ? paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("") : `<p>Contenido pendiente de completar.</p>`;
}

function newsDetailPage(slug) {
  const item = visibleNews().find((news) => news.slug === slug) || placeholderNews.find((news) => news.slug === slug) || placeholderNews[0];
  return `
    <section class="public-section">
      <div class="section-inner">
        <p class="kicker">${escapeHtml(item.category || "Actualidad")} · ${escapeHtml(item.date || item.publishedAtFormatted || "Pendiente de publicación")}</p>
        <h1>${escapeHtml(item.title)}</h1>
        <p class="lead">${escapeHtml(item.excerpt)}</p>
        <div class="legal-box">
          ${newsBodyHtml(item)}
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
        ${sectionTitle("Contacto", "Cuéntenos qué procedimiento, licitación o necesidad documental tiene", "Puede ponerse en contacto con nosotros por correo electrónico o teléfono. Estudiaremos cómo podemos ayudarle desde el análisis del pliego hasta la preparación y seguimiento documental.")}
        <div class="contact-grid">
          <article class="contact-panel">
            <h3>Cómo ponerse en contacto</h3>
            <p>Para una primera valoración, envíenos el enlace de la licitación, el número de expediente o una descripción breve de la necesidad documental.</p>
            <div class="contact-methods" aria-label="Datos de contacto">
              <a class="contact-method" href="mailto:${companyInfo.email}">
                <span>Correo electrónico</span>
                <strong>${companyInfo.email}</strong>
              </a>
              <a class="contact-method" href="${companyInfo.phoneHref}">
                <span>Teléfono</span>
                <strong>${companyInfo.phone}</strong>
              </a>
            </div>
            <p class="contact-hint">Si ya dispone de pliegos, fechas límite o comunicaciones del órgano de contratación, indíquelo en el primer mensaje para poder situar mejor el expediente.</p>
          </article>
          <aside class="contact-note">
            <h3>Datos de la empresa</h3>
            <p><strong>${companyInfo.name}</strong></p>
            <p>CIF: ${companyInfo.cif}</p>
            <p>Dir. postal: ${companyInfo.postalAddress}</p>
            <p>Correo electrónico: <a href="mailto:${companyInfo.email}">${companyInfo.email}</a></p>
            <p>Teléfono: <a href="${companyInfo.phoneHref}">${companyInfo.phone}</a></p>
            <p>Especialistas en contratación pública.</p>
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
  const updatedAt = "10 de julio de 2026";
  let body = "";

  if (kind === "/aviso-legal") {
    body = `
      <h3>Titular del sitio web</h3>
      ${companyIdentityList({ includePhone: true, includeRegistry: true })}
      <h3>Objeto del sitio</h3>
      <p>Este sitio web ofrece información corporativa y profesional sobre los servicios de asesoramiento en contratación pública prestados por ${companyInfo.name}.</p>
      <h3>Uso del sitio</h3>
      <p>La persona usuaria se compromete a utilizar este sitio de forma lícita, diligente y respetuosa con la normativa aplicable, sin dañar el funcionamiento de la web ni los derechos de terceros.</p>
      <h3>Propiedad intelectual</h3>
      <p>Los textos, diseño, logotipos, imágenes y demás contenidos de este sitio pertenecen a ${companyInfo.name} o se utilizan con autorización, salvo indicación expresa en contrario.</p>
      <h3>Responsabilidad</h3>
      <p>La información publicada tiene carácter informativo y no sustituye el estudio individual de cada expediente, pliego o situación jurídica concreta.</p>
      <h3>Legislación aplicable</h3>
      <p>Este sitio se rige por la normativa española aplicable, incluida la normativa sobre servicios de la sociedad de la información, protección de datos y contratación pública cuando corresponda.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  } else if (kind === "/politica-privacidad") {
    body = `
      <h3>Responsable del tratamiento</h3>
      ${companyIdentityList({ includePhone: true })}
      <h3>Datos tratados</h3>
      <p>La web pública no incorpora formulario de contacto. Si una persona contacta por correo electrónico o teléfono, trataremos los datos que facilite voluntariamente para atender su consulta.</p>
      <h3>Finalidades</h3>
      <ul>
        <li>Responder solicitudes de información, valoración o contacto profesional.</li>
        <li>Gestionar comunicaciones relacionadas con servicios de asesoramiento en contratación pública.</li>
        <li>Mantener la relación precontractual o contractual cuando proceda.</li>
      </ul>
      <h3>Legitimación</h3>
      <p>El tratamiento se basa en la aplicación de medidas precontractuales o contractuales solicitadas por la persona interesada, el interés legítimo en responder consultas profesionales y, cuando sea necesario, el consentimiento prestado por la persona que contacta.</p>
      <h3>Destinatarios</h3>
      <p>No se prevén cesiones de datos a terceros salvo obligación legal o intervención de proveedores necesarios para prestar servicios técnicos, administrativos o profesionales bajo las garantías correspondientes.</p>
      <h3>Conservación</h3>
      <p>Los datos se conservarán durante el tiempo necesario para atender la consulta, gestionar la relación profesional y cumplir las obligaciones legales que puedan resultar aplicables.</p>
      <h3>Derechos</h3>
      <p>Puede ejercer los derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo a <a href="mailto:${companyInfo.email}">${companyInfo.email}</a>. También puede presentar una reclamación ante la Agencia Española de Protección de Datos si considera que el tratamiento no se ajusta a la normativa.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  } else {
    body = `
      <h3>Uso actual de cookies</h3>
      <p>En esta versión, el código público de la web no instala cookies propias no técnicas ni cookies de analítica, publicidad o seguimiento desde el navegador.</p>
      <h3>Cookies técnicas</h3>
      <p>Si en algún momento fueran necesarias cookies técnicas para prestar un servicio solicitado por la persona usuaria, se utilizarían únicamente con esa finalidad y no requerirían consentimiento previo.</p>
      <h3>Herramientas externas</h3>
      <p>Si más adelante se incorporan herramientas de analítica, publicidad, mapas, vídeos, chat, medición o servicios de terceros que instalen cookies no exentas, se actualizará esta política y se mostrará un mecanismo de consentimiento con opciones para aceptar, rechazar y configurar.</p>
      <h3>Configuración del navegador</h3>
      <p>La persona usuaria puede revisar, bloquear o eliminar cookies desde la configuración de su navegador. El bloqueo de cookies técnicas podría afectar al funcionamiento de algunos sitios web.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  }

  return `
    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle("Información legal", titles[kind] || "Información legal", "Información corporativa y normativa básica de la web pública de ASESORES LLANGON, S.L.")}
        <div class="legal-box">
          ${body}
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
}

render();
