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

const homePainPoints = [
  [
    "No todas las licitaciones encajan",
    "Antes de invertir horas, conviene comprobar objeto, solvencia, criterios, riesgos y capacidad de ejecución.",
  ],
  [
    "Cada pliego tiene sus propias reglas",
    "Un requisito, un formato o una firma mal resueltos pueden dejar fuera una oferta válida.",
  ],
  [
    "La documentación exige coordinación",
    "Anexos, certificados, solvencia y memoria técnica deben avanzar con responsables, versiones y fechas claras.",
  ],
  [
    "El plazo condiciona cada decisión",
    "La presentación, las subsanaciones y los requerimientos exigen reaccionar a tiempo y con la documentación adecuada.",
  ],
];

const homeServices = [
  [
    "Búsqueda y filtro de oportunidades",
    "Revisamos licitaciones según actividad, zona, importe, solvencia y capacidad de ejecución para concentrar el esfuerzo donde existe mejor encaje.",
  ],
  [
    "Análisis de pliegos",
    "Aclaramos requisitos, criterios de valoración, obligaciones, documentación y plazos para que tu empresa pueda decidir cómo avanzar.",
  ],
  [
    "Documentación administrativa",
    "Organizamos anexos, declaraciones, acreditaciones, certificados y demás documentación exigida para participar.",
  ],
  [
    "Memoria y documentación técnica",
    "Estructuramos y redactamos el contenido técnico a partir de la información y las evidencias que aporta y valida tu empresa.",
  ],
  [
    "Revisión formal de la oferta económica",
    "Preparamos plantillas y herramientas de análisis y revisamos la coherencia formal, sin decidir precios, descuentos ni márgenes.",
  ],
  [
    "Presentación y seguimiento",
    "Acompañamos la presentación electrónica y el seguimiento de comunicaciones, requerimientos, subsanaciones y formalización.",
  ],
];

const homeBenefits = [
  [
    "Oportunidades con mejor encaje",
    "Priorizamos expedientes compatibles con la actividad, los recursos y la capacidad real de tu empresa.",
  ],
  [
    "Decisiones antes de invertir horas",
    "Aclaramos requisitos, criterios y carga documental antes de comprometer al equipo con la preparación.",
  ],
  [
    "Menos errores evitables",
    "Revisamos documentos, formatos, firmas y coherencia para detectar incidencias antes de presentar.",
  ],
  [
    "Tareas y plazos visibles",
    "Convertimos el expediente en un plan de trabajo con responsables, documentos pendientes y fechas internas.",
  ],
  [
    "Menos carga para tu equipo",
    "Coordinamos la preparación para que las personas clave se concentren en aportar y validar la información técnica.",
  ],
  [
    "Un expediente coherente",
    "Conectamos las exigencias administrativas, técnicas y económicas para evitar contradicciones entre documentos.",
  ],
];

const homeProcess = [
  [
    "Comprobamos el encaje",
    "Contrastamos la oportunidad con la actividad, la solvencia, los recursos y la capacidad de ejecución de tu empresa.",
  ],
  [
    "Analizamos y planificamos",
    "Identificamos requisitos, criterios y fechas y los convertimos en tareas, responsables y entregas internas.",
  ],
  [
    "Preparamos y revisamos",
    "Coordinamos anexos y documentación administrativa y técnica y comprobamos su coherencia antes de presentar.",
  ],
  [
    "Acompañamos y seguimos",
    "Apoyamos la presentación y atendemos las comunicaciones y los siguientes pasos del procedimiento.",
  ],
];

const trustPoints = [
  "Alcance y responsabilidades definidos desde el inicio.",
  "Requisitos del pliego convertidos en tareas concretas.",
  "Documentación ordenada y trazable.",
  "Comunicación directa y sin complejidad innecesaria.",
  "Datos técnicos y decisiones económicas validados por el cliente.",
  "Sin promesas de adjudicación.",
];

const faqItems = [
  {
    question: "¿Puede ayudarnos ASESORES LLANGON si todavía no hemos licitado?",
    answer: "Sí. El primer paso es revisar la actividad, el ámbito de trabajo, la solvencia y la documentación disponible para identificar qué preparación previa necesita tu empresa y qué oportunidades pueden tener encaje.",
  },
  {
    question: "¿Trabajáis con una licitación concreta o de forma continuada?",
    answer: "De ambas formas. Podemos intervenir en un expediente concreto o prestar apoyo recurrente en la búsqueda, preparación y seguimiento de licitaciones.",
  },
  {
    question: "¿Qué información debemos enviar para una primera consulta?",
    answer: "Basta con una breve descripción de la actividad de la empresa y del apoyo que necesita. Si ya existe un expediente, conviene añadir el enlace o número, la fecha límite y los pliegos o comunicaciones disponibles.",
  },
  {
    question: "¿Preparáis la documentación técnica y la oferta económica?",
    answer: "Podemos estructurar y redactar documentación técnica a partir de la información que aporta y valida el cliente. En la parte económica preparamos plantillas y revisamos la coherencia formal; el precio, los descuentos y los márgenes los decide siempre la empresa licitadora.",
  },
  {
    question: "¿Os encargáis de presentar la oferta?",
    answer: "Acompañamos la preparación y la presentación electrónica según el alcance acordado. El uso de certificados, las autorizaciones y la validación final se coordinan con la empresa licitadora.",
  },
  {
    question: "¿Con cuánto tiempo debemos contactar?",
    answer: "Cuanto antes se revise el expediente, más margen habrá para analizar requisitos, repartir tareas y preparar la documentación. Si el plazo está próximo, estudiaremos el estado del caso y te indicaremos con realismo qué apoyo puede prestarse en el tiempo disponible.",
  },
  {
    question: "¿Podéis garantizar la adjudicación?",
    answer: "No. La adjudicación depende del pliego, de las ofertas presentadas y de la valoración del órgano de contratación. Nuestro trabajo se centra en elegir mejor, reducir errores evitables y preparar un expediente ordenado, coherente y ajustado a los requisitos.",
  },
];

const methodology = [
  [
    "Encaje inicial",
    "Revisamos si el objeto, el ámbito, el importe y los requisitos principales encajan con la actividad y la capacidad de tu empresa.",
  ],
  [
    "Análisis del expediente",
    "Identificamos requisitos de participación, solvencia, criterios de valoración, documentación, obligaciones, plazos y puntos críticos.",
  ],
  [
    "Plan de trabajo",
    "Definimos tareas, responsables, documentación pendiente y fechas internas para preparar la oferta con margen.",
  ],
  [
    "Preparación y coordinación",
    "Preparamos anexos y documentación administrativa y técnica, coordinando la información que debe aportar y validar tu empresa.",
  ],
  [
    "Revisión y presentación",
    "Comprobamos firmas, formatos, coherencia y documentación, y acompañamos la presentación electrónica antes del cierre del plazo.",
  ],
  [
    "Seguimiento y respuesta",
    "Seguimos las comunicaciones y prestamos apoyo ante requerimientos, subsanaciones, propuesta de adjudicación o actuaciones posteriores, cuando proceda.",
  ],
];

const serviceGroups = [
  {
    id: "oportunidades",
    title: "Oportunidades y análisis",
    text: "Seleccionar bien antes de preparar: qué encaja, qué exige el pliego y dónde están los puntos críticos.",
  },
  {
    id: "oferta",
    title: "Preparación de la oferta",
    text: "Documentación administrativa, técnica y económica coordinada conforme a las reglas de cada expediente.",
  },
  {
    id: "seguimiento",
    title: "Presentación y seguimiento",
    text: "Apoyo para presentar, responder a comunicaciones y completar los pasos previos a la formalización.",
  },
  {
    id: "defensa",
    title: "Defensa y ejecución",
    text: "Asesoramiento en actuaciones posteriores cuando el procedimiento o la ejecución del contrato lo requieren.",
  },
];

const serviceDetails = [
  {
    group: "oportunidades",
    title: "Búsqueda y selección de oportunidades",
    text: "Buscamos y filtramos licitaciones según la actividad, zona, solvencia, experiencia y capacidad operativa de tu empresa, para que dediques tiempo a oportunidades con un encaje real.",
    points: [
      "Búsqueda en plataformas públicas.",
      "Revisión de objeto, CPV, lotes, presupuesto y ámbito geográfico.",
      "Contraste de solvencia y requisitos principales.",
      "Control de fechas relevantes.",
    ],
  },
  {
    group: "oportunidades",
    title: "Análisis de pliegos y encaje",
    text: "Revisamos los pliegos administrativos y técnicos para identificar requisitos, criterios de valoración, documentación, obligaciones, plazos y riesgos. Te explicamos los puntos críticos para que puedas decidir si concurrir y cómo plantear el expediente.",
    points: [
      "Análisis de PCAP y PPT.",
      "Criterios automáticos y sujetos a juicio de valor.",
      "Garantías, penalidades y condiciones de ejecución.",
      "Consultas y posibles actuaciones frente a los pliegos.",
    ],
  },
  {
    group: "oferta",
    title: "Coordinación y preparación de ofertas",
    text: "Convertimos las exigencias del pliego en un índice de trabajo, coordinamos la información pendiente y preparamos la documentación de cada sobre o archivo electrónico antes de la presentación.",
    points: [
      "Índice documental y calendario interno.",
      "Organización por sobres o archivos electrónicos.",
      "Control de modelos, formatos y firmas.",
      "Revisión de coherencia antes de presentar.",
    ],
  },
  {
    group: "oferta",
    title: "Documentación administrativa",
    text: "Recopilamos, revisamos y preparamos declaraciones, anexos, acreditaciones de solvencia, certificados y demás documentación administrativa exigida en el expediente.",
    points: [
      "Declaraciones responsables y anexos.",
      "Capacidad, representación y solvencia.",
      "Certificados administrativos.",
      "ROLECE y registros autonómicos cuando proceda.",
    ],
  },
  {
    group: "oferta",
    title: "Memorias y documentación técnica",
    text: "Preparamos y revisamos memorias, fichas, planes de trabajo y otros documentos técnicos a partir de la información, los medios y las evidencias facilitados y validados por tu empresa, adaptándolos a las exigencias y criterios del pliego.",
    points: [
      "Memorias y planes de prestación.",
      "Fichas y documentos justificativos.",
      "Medios personales y materiales.",
      "Coherencia con el pliego técnico.",
    ],
  },
  {
    group: "oferta",
    title: "Plantillas y revisión formal de la oferta económica",
    text: "Preparamos plantillas y modelos conforme al pliego y revisamos unidades, fórmulas, importes y coherencia formal para que tu empresa pueda completar y validar su oferta económica.",
    points: [
      "Unidades, lotes y precios máximos.",
      "IVA, importes unitarios, totales y subtotales.",
      "Fórmulas y criterios económicos del pliego.",
      "Detección de incoherencias formales o aritméticas.",
    ],
    note: "ASESORES LLANGON, S.L. no decide ni fija los precios ofertados. La oferta económica es elaborada, decidida y validada siempre por la empresa licitadora.",
  },
  {
    group: "seguimiento",
    title: "Consultas, subsanaciones y requerimientos",
    text: "Analizamos la comunicación recibida, concretamos qué se solicita y preparamos contigo una respuesta ordenada, completa y dentro del plazo disponible.",
    points: [
      "Consultas durante la licitación.",
      "Revisión de requerimientos.",
      "Preparación de escritos de subsanación.",
      "Control de documentación y plazos.",
    ],
  },
  {
    group: "seguimiento",
    title: "Justificación documental de ofertas anormales",
    text: "Estructuramos la respuesta documental ante una oferta incursa en presunción de anormalidad a partir de los costes, medios, condiciones y explicaciones aportados y validados por tu empresa.",
    points: [
      "Ordenación de datos y documentos justificativos.",
      "Desglose de costes facilitado por el cliente.",
      "Preparación formal del escrito.",
      "Revisión de coherencia y plazo de respuesta.",
    ],
    note: "ASESORES LLANGON, S.L. no determina la viabilidad económica de la oferta ni sustituye al cliente en la explicación de sus costes, medios o márgenes.",
  },
  {
    group: "seguimiento",
    title: "Adjudicación y formalización",
    text: "Si tu empresa resulta propuesta como adjudicataria, preparamos y revisamos certificados, garantías y demás documentación previa para completar la adjudicación y formalizar el contrato en plazo.",
    points: [
      "Documentación previa a la adjudicación.",
      "Garantías definitivas.",
      "Certificados actualizados.",
      "Revisión del contrato y control de plazos.",
    ],
  },
  {
    group: "defensa",
    title: "Recursos, alegaciones e impugnaciones",
    text: "Analizamos la viabilidad de alegaciones, recursos e impugnaciones ante pliegos, exclusiones, adjudicaciones, desistimientos u otros actos del procedimiento y preparamos la actuación que corresponda en cada caso.",
    points: [
      "Actuaciones frente a pliegos.",
      "Alegaciones ante exclusiones.",
      "Recursos frente a adjudicaciones.",
      "Análisis individual de viabilidad.",
    ],
  },
  {
    group: "defensa",
    title: "Apoyo durante la ejecución del contrato",
    text: "Cuando el caso lo requiere, prestamos apoyo documental y de asesoramiento ante incidencias, modificaciones, prórrogas, reclamaciones o discrepancias surgidas durante la ejecución.",
    points: [
      "Incidencias de ejecución.",
      "Modificaciones y prórrogas.",
      "Reclamaciones y discrepancias.",
      "Revisión documental de las actuaciones.",
    ],
  },
  {
    group: "defensa",
    title: "ROLECE, plataformas y certificados",
    text: "Te ayudamos con las altas y gestiones necesarias para licitar en ROLECE, la Plataforma de Contratación del Sector Público, plataformas autonómicas y otros registros oficiales españoles.",
    points: [
      "ROLECE y registros autonómicos.",
      "Plataformas de contratación electrónica.",
      "Apoyo relacionado con certificados digitales.",
      "Coordinación de documentación habilitante.",
    ],
  },
];

const procurementTopics = [
  "Encaje y solvencia",
  "Análisis de pliegos",
  "Documentación administrativa",
  "Memoria técnica",
  "Oferta económica",
  "Presentación electrónica",
  "Subsanaciones y requerimientos",
  "Adjudicación y formalización",
];

const content = document.getElementById("public-content");
const menuToggle = document.querySelector(".menu-toggle");
const menuToggleLabel = document.querySelector(".menu-toggle-label");
const publicNav = document.getElementById("public-nav");

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

function emailHref(subject = "Consulta sobre licitaciones") {
  return `mailto:${companyInfo.email}?subject=${encodeURIComponent(subject)}`;
}

function sectionTitle(kicker, title, text = "") {
  return `
    <div class="section-title">
      <p class="kicker">${escapeHtml(kicker)}</p>
      <h2>${escapeHtml(title)}</h2>
      ${text ? `<p>${escapeHtml(text)}</p>` : ""}
    </div>
  `;
}

function pageHeader(kicker, title, text) {
  return `
    <section class="page-hero">
      <div class="section-inner">
        <p class="kicker">${escapeHtml(kicker)}</p>
        <h1>${escapeHtml(title)}</h1>
        <p class="page-lead">${escapeHtml(text)}</p>
      </div>
    </section>
  `;
}

function numberedCards(items, className = "cards-grid") {
  return `
    <div class="${escapeHtml(className)}">
      ${items.map((item, index) => `
        <article class="card">
          <span class="card-icon" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
          <h3>${escapeHtml(item[0])}</h3>
          <p>${escapeHtml(item[1])}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function faqList(items = faqItems) {
  return `
    <div class="faq-list">
      ${items.map((item) => `
        <details class="faq-item">
          <summary>${escapeHtml(item.question)}</summary>
          <p>${escapeHtml(item.answer)}</p>
        </details>
      `).join("")}
    </div>
  `;
}

function compactCta({ kicker, title, text, label = "Cuéntanos tu caso", href = "/contacto" }) {
  return `
    <section class="public-section compact-cta-section">
      <div class="section-inner compact-cta">
        <div>
          <p class="kicker">${escapeHtml(kicker)}</p>
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(text)}</p>
        </div>
        <div>${button(label, href)}</div>
      </div>
    </section>
  `;
}

function finalCta() {
  return `
    <section class="public-section final-cta">
      <div class="section-inner final-cta-grid">
        <div>
          <p class="kicker">Hablemos</p>
          <h2>¿Tienes una licitación en marcha o quieres empezar a buscar oportunidades?</h2>
          <p>Cuéntanos a qué se dedica tu empresa y en qué punto estás. Si ya tienes un expediente, envíanos el enlace o número y la fecha límite.</p>
          <div class="section-actions">
            ${button("Cuéntanos tu caso", "/contacto")}
            <a class="button-link button-on-dark" href="mailto:${escapeHtml(companyInfo.email)}">Escribir por email</a>
          </div>
        </div>
        <div class="final-cta-contact" aria-label="Contacto directo">
          <span>Contacto directo</span>
          <a href="mailto:${escapeHtml(companyInfo.email)}">${escapeHtml(companyInfo.email)}</a>
          <a href="${escapeHtml(companyInfo.phoneHref)}">${escapeHtml(companyInfo.phone)}</a>
        </div>
      </div>
    </section>
  `;
}

function homePage() {
  return `
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-copy">
          <p class="kicker">Asesoramiento en licitaciones públicas para empresas</p>
          <h1>Licitaciones bien elegidas, ofertas bien preparadas</h1>
          <p class="lead">En ASESORES LLANGON te ayudamos a encontrar oportunidades con encaje real, interpretar los pliegos y preparar la documentación administrativa y técnica que exige cada expediente.</p>
          <p class="hero-support">Cuenta con un equipo especializado para una licitación concreta o para gestionar este canal de forma continuada, con atención directa, plazos bajo control y las decisiones de negocio siempre en tus manos.</p>
          <div class="hero-actions">
            ${button("Cuéntanos tu caso", "/contacto")}
            ${button("Ver servicios", "/servicios", "button-secondary")}
          </div>
          <p class="hero-microcopy">Primera orientación · Atención directa · Apoyo puntual o continuado</p>
        </div>
        <div class="hero-visual">
          <picture>
            <source srcset="/static/assets/public-hero-procurement.webp" type="image/webp">
            <img src="/static/assets/public-hero-procurement.png" width="1774" height="887" alt="Mesa de trabajo con documentación organizada para una licitación" fetchpriority="high">
          </picture>
          <div class="hero-visual-card">
            <span>Dos formas de trabajar</span>
            <strong>Una licitación concreta o gestión continuada</strong>
          </div>
        </div>
      </div>
      <div class="hero-proof-wrap">
        <div class="hero-proof" aria-label="Áreas principales de trabajo">
          <span>Selección de oportunidades</span>
          <span>Análisis de pliegos</span>
          <span>Preparación de ofertas</span>
          <span>Presentación y seguimiento</span>
        </div>
      </div>
    </section>

    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle(
          "El reto",
          "Licitar no debería frenar el trabajo de tu equipo",
          "Cada expediente exige valorar el encaje, interpretar requisitos, coordinar documentación y llegar a tiempo. Sin un método claro, la oportunidad compite con el día a día de la empresa.",
        )}
        <div class="compact-card-grid">
          ${homePainPoints.map((item) => `
            <article class="compact-card">
              <h3>${escapeHtml(item[0])}</h3>
              <p>${escapeHtml(item[1])}</p>
            </article>
          `).join("")}
        </div>
        <div class="highlight-line">Convertimos cada licitación en un plan claro: qué exige, qué aporta tu equipo, qué preparamos nosotros y cuándo debe estar listo.</div>
      </div>
    </section>

    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle(
          "Cómo podemos ayudarte",
          "Apoyo especializado en cada fase de la licitación",
          "Puedes delegar la gestión completa o contar con nosotros en una fase concreta, desde la selección de oportunidades hasta los requerimientos posteriores a la presentación.",
        )}
        ${numberedCards(homeServices)}
        <div class="section-actions">
          ${button("Ver todos los servicios", "/servicios")}
        </div>
      </div>
    </section>

    ${compactCta({
      kicker: "Una licitación concreta",
      title: "¿Ya tienes un expediente y una fecha límite?",
      text: "Envíanos el enlace o número de expediente y la fecha de presentación. Te indicaremos qué apoyo podemos ofrecerte y qué información necesita aportar tu empresa.",
    })}

    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle(
          "Beneficios operativos",
          "Más oportunidades útiles, menos carga y mayor control",
          "El valor está en decidir antes, coordinar mejor y presentar un expediente coherente.",
        )}
        <div class="benefit-grid">
          ${homeBenefits.map((item) => `
            <article class="benefit-card">
              <span class="benefit-mark" aria-hidden="true"></span>
              <div>
                <h3>${escapeHtml(item[0])}</h3>
                <p>${escapeHtml(item[1])}</p>
              </div>
            </article>
          `).join("")}
        </div>
      </div>
    </section>

    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle(
          "Cómo trabajamos",
          "Un proceso claro, desde el encaje hasta el seguimiento",
          "En cada fase sabrás qué revisamos, qué necesita aportar tu equipo y cuál es el siguiente paso.",
        )}
        <div class="process-grid">
          ${homeProcess.map((step, index) => `
            <article class="process-step">
              <span class="process-number">${String(index + 1).padStart(2, "0")}</span>
              <h3>${escapeHtml(step[0])}</h3>
              <p>${escapeHtml(step[1])}</p>
            </article>
          `).join("")}
        </div>
        <div class="section-actions">
          ${button("Ver cómo trabajamos", "/metodologia", "button-secondary")}
        </div>
      </div>
    </section>

    <section class="public-section">
      <div class="section-inner">
        ${sectionTitle(
          "Modalidades",
          "Apoyo puntual o gestión continuada: tú eliges",
          "El alcance se adapta al ritmo de licitación y a los recursos internos de tu empresa.",
        )}
        <div class="work-mode-grid">
          <article class="work-mode-card">
            <p class="card-label">Para trabajar este canal de forma estable</p>
            <h3>Gestión continuada</h3>
            <p>Seleccionamos oportunidades, coordinamos expedientes y realizamos un seguimiento recurrente sin que tu empresa tenga que asumir internamente toda la gestión.</p>
            <div class="section-actions">${button("Consultar gestión continuada", "/contacto", "button-secondary")}</div>
          </article>
          <article class="work-mode-card featured-card">
            <p class="card-label">Para una oportunidad ya localizada</p>
            <h3>Apoyo para una licitación concreta</h3>
            <p>Intervenimos en todo el expediente o en una fase concreta: análisis, documentación administrativa, memoria técnica, revisión formal o seguimiento.</p>
            <div class="section-actions">${button("Consultar una licitación", "/contacto")}</div>
          </article>
        </div>
      </div>
    </section>

    <section class="public-section responsibility-section light-band">
      <div class="section-inner">
        ${sectionTitle(
          "Responsabilidades claras",
          "Tu empresa decide; nosotros aportamos análisis, estructura y control",
          "Definimos contigo qué necesita el expediente, organizamos las tareas y revisamos la coherencia de la oferta, manteniendo claro qué corresponde a cada parte.",
        )}
        <div class="two-column-panel">
          <article>
            <span class="panel-tag">Documentación técnica</span>
            <h3>El conocimiento de tu empresa, bien estructurado</h3>
            <p>Redactamos y ordenamos memorias, planes y fichas a partir de la información, los medios y las evidencias que aporta y valida tu equipo.</p>
          </article>
          <article>
            <span class="panel-tag">Oferta económica</span>
            <h3>Herramientas y revisión, con la decisión en tus manos</h3>
            <p>Preparamos plantillas y revisamos la coherencia formal. Tu empresa define y valida los precios, descuentos, márgenes y la viabilidad económica.</p>
          </article>
        </div>
        <div class="expectation-grid">
          <div>
            <h3>Qué puedes esperar de nuestro trabajo</h3>
            <p>Un expediente comprensible, responsabilidades definidas y comunicación directa durante todo el proceso.</p>
            <a class="text-link" href="/contratacion-publica">Conocer mejor el marco de la contratación pública</a>
          </div>
          <ul class="trust-list">
            ${trustPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
          </ul>
        </div>
      </div>
    </section>

    <section class="public-section faq-section">
      <div class="section-inner faq-layout">
        <div>
          ${sectionTitle(
            "Preguntas frecuentes",
            "Lo esencial antes de empezar",
            "Resolvemos las dudas más habituales sobre el alcance del apoyo y la forma de trabajar.",
          )}
          <div class="section-actions">${button("Hablar sobre mi caso", "/contacto", "button-secondary")}</div>
        </div>
        ${faqList()}
      </div>
    </section>

    ${finalCta()}
  `;
}

function serviceAccordion(service, index) {
  return `
    <details class="service-detail" ${index === 0 ? "open" : ""}>
      <summary>
        <span class="service-number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
        <span class="service-summary-title">${escapeHtml(service.title)}</span>
        <span class="summary-icon" aria-hidden="true"></span>
      </summary>
      <div class="service-detail-body">
        <div>
          <p>${escapeHtml(service.text)}</p>
          ${service.note ? `<div class="notice-box">${escapeHtml(service.note)}</div>` : ""}
        </div>
        <ul>${service.points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>
      </div>
    </details>
  `;
}

function servicesPage() {
  return `
    ${pageHeader(
      "Servicios",
      "Apoyo especializado en cada fase de la licitación",
      "Puedes contar con nosotros para gestionar el proceso completo o para reforzar una fase concreta, según las necesidades y los recursos de tu empresa.",
    )}
    <section class="public-section service-overview-section">
      <div class="section-inner">
        <nav class="service-path-grid" aria-label="Áreas de servicio">
          ${serviceGroups.map((group, index) => `
            <a href="#${escapeHtml(group.id)}" class="service-path-card">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <strong>${escapeHtml(group.title)}</strong>
              <small>${escapeHtml(group.text)}</small>
            </a>
          `).join("")}
        </nav>
      </div>
    </section>
    <section class="public-section services-detail-section light-band">
      <div class="section-inner services-groups">
        ${serviceGroups.map((group) => {
          const groupServices = serviceDetails.filter((service) => service.group === group.id);
          return `
            <section id="${escapeHtml(group.id)}" class="service-group">
              <div class="service-group-heading">
                <p class="kicker">Área de trabajo</p>
                <h2>${escapeHtml(group.title)}</h2>
                <p>${escapeHtml(group.text)}</p>
              </div>
              <div class="service-accordion">
                ${groupServices.map((service, index) => serviceAccordion(service, index)).join("")}
              </div>
            </section>
          `;
        }).join("")}
      </div>
    </section>
    ${compactCta({
      kicker: "Un alcance a medida",
      title: "¿Necesitas el proceso completo o apoyo en una fase?",
      text: "Cuéntanos qué licitación tienes delante o cómo gestiona hoy tu empresa este canal. Te explicaremos qué apoyo podemos ofrecerte.",
    })}
    ${finalCta()}
  `;
}

function methodologyPage() {
  return `
    ${pageHeader(
      "Cómo trabajamos",
      "Un método claro para decidir, preparar y seguir cada licitación",
      "Ordenamos cada expediente para que tu empresa sepa qué debe decidir, qué información tiene que aportar y qué tareas asumimos nosotros.",
    )}
    <section class="public-section">
      <div class="section-inner">
        <div class="method-grid">
          ${methodology.map((step, index) => `
            <article class="method-step">
              <span class="method-number">${String(index + 1).padStart(2, "0")}</span>
              <h2>${escapeHtml(step[0])}</h2>
              <p>${escapeHtml(step[1])}</p>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
    <section class="public-section light-band">
      <div class="section-inner split-grid methodology-principles">
        <div>
          ${sectionTitle(
            "Coordinación",
            "Cada parte sabe qué debe hacer",
            "Tu equipo conserva las decisiones de negocio y valida la información de la empresa. Nosotros traducimos el pliego a tareas, documentos y fechas concretas.",
          )}
        </div>
        <ul class="trust-list">
          <li>Un índice documental para cada expediente.</li>
          <li>Fechas internas antes del plazo oficial.</li>
          <li>Responsables y validaciones identificados.</li>
          <li>Revisión formal antes de presentar.</li>
          <li>Seguimiento de comunicaciones posteriores.</li>
        </ul>
      </div>
    </section>
    ${finalCta()}
  `;
}

function procurementPage() {
  return `
    ${pageHeader(
      "Contratación pública",
      "Convierte los requisitos del pliego en un plan de acción",
      "Licitar exige mucho más que fijar un precio: hay que comprobar el encaje, acreditar capacidad y solvencia, preparar la oferta, controlar plazos y responder a las comunicaciones del procedimiento.",
    )}
    <section class="public-section">
      <div class="section-inner split-grid procurement-intro">
        <div>
          ${sectionTitle(
            "Un mercado regulado",
            "El sector público también puede ser cliente de tu empresa",
            "Las administraciones contratan obras, servicios y suministros de empresas privadas. La oportunidad está en identificar los procedimientos que encajan y prepararlos con método.",
          )}
        </div>
        <div class="text-block">
          <p>La Ley 9/2017, de Contratos del Sector Público, establece el marco principal de estos procedimientos en España sobre principios como la transparencia, la igualdad de trato y la libre competencia.</p>
          <p>ASESORES LLANGON convierte esas exigencias en tareas concretas y coordinadas para reducir errores evitables, mejorar la coherencia de la documentación y facilitar decisiones informadas.</p>
          <div class="highlight-line">No se trata de presentarse a todo, sino de elegir mejor y preparar cada expediente con método.</div>
        </div>
      </div>
    </section>
    <section class="public-section light-band">
      <div class="section-inner">
        ${sectionTitle(
          "Áreas clave",
          "Qué debe quedar bajo control",
          "Cada pliego concreta las reglas, pero estos son los ámbitos que suelen concentrar la preparación del expediente.",
        )}
        <div class="procurement-grid">
          ${procurementTopics.map((topic) => `<div class="mini-card"><strong>${escapeHtml(topic)}</strong></div>`).join("")}
        </div>
      </div>
    </section>
    ${finalCta()}
  `;
}

function resourcesPage() {
  return `
    ${pageHeader(
      "Recursos",
      "Claves prácticas para licitar mejor",
      "Estamos preparando análisis y recursos para ayudar a las empresas a entender mejor los procedimientos y organizar sus expedientes.",
    )}
    <section class="public-section">
      <div class="section-inner empty-state">
        <span class="empty-state-mark" aria-hidden="true"></span>
        <h2>Nuevos contenidos en preparación</h2>
        <p>Publicaremos únicamente recursos completos y revisados. Mientras tanto, si necesitas aplicar una cuestión a una licitación concreta, puedes consultarnos directamente.</p>
        <div class="section-actions">${button("Cuéntanos tu caso", "/contacto")}</div>
      </div>
    </section>
  `;
}

function privateAccessPage() {
  const hasExternalAccess = privateUrl && !["/contacto", "/login"].includes(privateUrl);
  return `
    ${pageHeader(
      "Zona de clientes",
      "Acceso reservado para clientes",
      "Esta zona no forma parte del recorrido comercial de la web pública.",
    )}
    <section class="public-section">
      <div class="section-inner empty-state">
        <h2>${hasExternalAccess ? "Accede a tu área privada" : "¿Necesitas ayuda con tu acceso?"}</h2>
        <p>${hasExternalAccess ? "Utiliza el acceso facilitado para consultar la información disponible de tus expedientes." : "Contacta con ASESORES LLANGON para solicitar o recuperar la información de acceso que corresponda."}</p>
        <div class="section-actions">
          ${hasExternalAccess ? button("Acceder", privateUrl) : button("Contactar", "/contacto")}
        </div>
      </div>
    </section>
  `;
}

function contactPage() {
  return `
    ${pageHeader(
      "Contacto",
      "¿Tienes una licitación en marcha o quieres empezar a licitar?",
      "Tanto si ya tienes un expediente como si quieres abrir una nueva vía de negocio en el sector público, hablemos del punto de partida de tu empresa y del apoyo que necesitas.",
    )}
    <section class="public-section contact-section">
      <div class="section-inner contact-layout">
        <div class="contact-primary">
          <div>
            <p class="kicker">Contacto directo</p>
            <h2>Escríbenos o llámanos</h2>
            <p>No necesitas tener toda la información ordenada antes de contactar.</p>
          </div>
          <div class="contact-methods" aria-label="Datos de contacto">
            <a class="contact-method" href="mailto:${escapeHtml(companyInfo.email)}">
              <span>Escribir por email</span>
              <strong>${escapeHtml(companyInfo.email)}</strong>
            </a>
            <a class="contact-method" href="${escapeHtml(companyInfo.phoneHref)}">
              <span>Llamar</span>
              <strong>${escapeHtml(companyInfo.phone)}</strong>
            </a>
          </div>
          <div class="contact-intent-grid">
            <article class="contact-intent-card">
              <p class="card-label">Necesidad puntual</p>
              <h3>Tengo una licitación en marcha</h3>
              <p>Envíanos el enlace o número de expediente, la fecha límite y los documentos disponibles. No necesitas preparar un resumen completo.</p>
              <a class="text-link" href="${escapeHtml(emailHref("Consulta sobre una licitación en marcha"))}">Consultar una licitación</a>
            </article>
            <article class="contact-intent-card">
              <p class="card-label">Colaboración recurrente</p>
              <h3>Quiero trabajar las licitaciones de forma continuada</h3>
              <p>Cuéntanos a qué se dedica tu empresa, dónde trabaja y cómo localiza y prepara actualmente sus oportunidades.</p>
              <a class="text-link" href="${escapeHtml(emailHref("Consulta sobre gestión continuada de licitaciones"))}">Consultar gestión continuada</a>
            </article>
          </div>
          <p class="contact-hint"><strong>Si existe una fecha límite, un requerimiento o una subsanación en curso, incluye el plazo en el asunto del mensaje.</strong> No envíes contraseñas, certificados digitales ni información confidencial innecesaria en el primer contacto.</p>
        </div>
        <aside class="contact-note">
          <p class="kicker">Datos de la empresa</p>
          <h2>${escapeHtml(companyInfo.name)}</h2>
          <dl>
            <div><dt>CIF</dt><dd>${escapeHtml(companyInfo.cif)}</dd></div>
            <div><dt>Dirección postal</dt><dd>${escapeHtml(companyInfo.postalAddress)}</dd></div>
            <div><dt>Correo electrónico</dt><dd><a href="mailto:${escapeHtml(companyInfo.email)}">${escapeHtml(companyInfo.email)}</a></dd></div>
            <div><dt>Teléfono</dt><dd><a href="${escapeHtml(companyInfo.phoneHref)}">${escapeHtml(companyInfo.phone)}</a></dd></div>
          </dl>
          <p class="contact-note-closing">Atención directa para empresas que quieren competir mejor en el mercado público.</p>
        </aside>
      </div>
    </section>
    <section class="public-section light-band contact-faq">
      <div class="section-inner faq-layout">
        <div>${sectionTitle("Antes de escribir", "Tres dudas habituales", "Información útil para situar mejor tu consulta.")}</div>
        ${faqList([faqItems[2], faqItems[4], faqItems[5]])}
      </div>
    </section>
  `;
}

function companyIdentityList({ includePhone = false } = {}) {
  return `
    <ul>
      <li><strong>Titular:</strong> ${escapeHtml(companyInfo.name)}</li>
      <li><strong>CIF:</strong> ${escapeHtml(companyInfo.cif)}</li>
      <li><strong>Dirección postal:</strong> ${escapeHtml(companyInfo.postalAddress)}</li>
      <li><strong>Correo electrónico:</strong> <a href="mailto:${escapeHtml(companyInfo.email)}">${escapeHtml(companyInfo.email)}</a></li>
      ${includePhone ? `<li><strong>Teléfono:</strong> <a href="${escapeHtml(companyInfo.phoneHref)}">${escapeHtml(companyInfo.phone)}</a></li>` : ""}
    </ul>
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
      <h2>Titular del sitio web</h2>
      ${companyIdentityList({ includePhone: true })}
      <h2>Objeto del sitio</h2>
      <p>Este sitio web ofrece información corporativa y profesional sobre los servicios de asesoramiento en contratación pública prestados por ${escapeHtml(companyInfo.name)}.</p>
      <h2>Uso del sitio</h2>
      <p>La persona usuaria se compromete a utilizar este sitio de forma lícita, diligente y respetuosa con la normativa aplicable, sin dañar el funcionamiento de la web ni los derechos de terceros.</p>
      <h2>Propiedad intelectual</h2>
      <p>Los textos, diseño, logotipos, imágenes y demás contenidos de este sitio pertenecen a ${escapeHtml(companyInfo.name)} o se utilizan con autorización, salvo indicación expresa en contrario.</p>
      <h2>Responsabilidad</h2>
      <p>La información publicada tiene carácter informativo y no sustituye el estudio individual de cada expediente, pliego o situación jurídica concreta.</p>
      <h2>Legislación aplicable</h2>
      <p>Este sitio se rige por la normativa española aplicable, incluida la normativa sobre servicios de la sociedad de la información, protección de datos y contratación pública cuando corresponda.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  } else if (kind === "/politica-privacidad") {
    body = `
      <h2>Responsable del tratamiento</h2>
      ${companyIdentityList({ includePhone: true })}
      <h2>Datos tratados</h2>
      <p>La web pública no incorpora formulario de contacto. Si una persona contacta por correo electrónico o teléfono, trataremos los datos que facilite voluntariamente para atender su consulta.</p>
      <h2>Finalidades</h2>
      <ul>
        <li>Responder solicitudes de información, valoración o contacto profesional.</li>
        <li>Gestionar comunicaciones relacionadas con servicios de asesoramiento en contratación pública.</li>
        <li>Mantener la relación precontractual o contractual cuando proceda.</li>
      </ul>
      <h2>Legitimación</h2>
      <p>El tratamiento se basa en la aplicación de medidas precontractuales o contractuales solicitadas por la persona interesada, el interés legítimo en responder consultas profesionales y, cuando sea necesario, el consentimiento prestado por la persona que contacta.</p>
      <h2>Destinatarios</h2>
      <p>No se prevén cesiones de datos a terceros salvo obligación legal o intervención de proveedores necesarios para prestar servicios técnicos, administrativos o profesionales bajo las garantías correspondientes.</p>
      <h2>Conservación</h2>
      <p>Los datos se conservarán durante el tiempo necesario para atender la consulta, gestionar la relación profesional y cumplir las obligaciones legales que puedan resultar aplicables.</p>
      <h2>Derechos</h2>
      <p>Puede ejercer los derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo a <a href="mailto:${escapeHtml(companyInfo.email)}">${escapeHtml(companyInfo.email)}</a>. También puede presentar una reclamación ante la Agencia Española de Protección de Datos si considera que el tratamiento no se ajusta a la normativa.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  } else {
    body = `
      <h2>Uso actual de cookies</h2>
      <p>En esta versión, el código público de la web no instala cookies propias no técnicas ni cookies de analítica, publicidad o seguimiento desde el navegador.</p>
      <h2>Cookies técnicas</h2>
      <p>Si en algún momento fueran necesarias cookies técnicas para prestar un servicio solicitado por la persona usuaria, se utilizarían únicamente con esa finalidad y no requerirían consentimiento previo.</p>
      <h2>Herramientas externas</h2>
      <p>Si más adelante se incorporan herramientas de analítica, publicidad, mapas, vídeos, chat, medición o servicios de terceros que instalen cookies no exentas, se actualizará esta política y se mostrará un mecanismo de consentimiento con opciones para aceptar, rechazar y configurar.</p>
      <h2>Configuración del navegador</h2>
      <p>La persona usuaria puede revisar, bloquear o eliminar cookies desde la configuración de su navegador. El bloqueo de cookies técnicas podría afectar al funcionamiento de algunos sitios web.</p>
      <p class="legal-muted">Última actualización: ${updatedAt}.</p>
    `;
  }

  return `
    ${pageHeader("Información legal", titles[kind] || "Información legal", "Información corporativa y normativa básica de la web pública de ASESORES LLANGON, S.L.")}
    <section class="public-section legal-section">
      <div class="section-inner legal-box">${body}</div>
    </section>
  `;
}

function notFoundPage() {
  return `
    ${pageHeader("Página no encontrada", "No hemos encontrado esta dirección", "Puedes volver al inicio, revisar nuestros servicios o contactar con nosotros.")}
    <section class="public-section">
      <div class="section-inner empty-state">
        <div class="section-actions">
          ${button("Volver al inicio", "/")}
          ${button("Ver servicios", "/servicios", "button-secondary")}
        </div>
      </div>
    </section>
  `;
}

const routes = {
  "/": {
    render: homePage,
    title: "Asesoría de licitaciones públicas para empresas | ASESORES LLANGON",
    description: "Ayudamos a empresas a seleccionar, preparar y seguir licitaciones públicas en España, por expediente o mediante una gestión continuada.",
  },
  "/servicios": {
    render: servicesPage,
    title: "Servicios de licitaciones públicas | ASESORES LLANGON",
    description: "Búsqueda, análisis de pliegos, preparación documental, presentación, subsanaciones, adjudicación y apoyo posterior para empresas.",
  },
  "/metodologia": {
    render: methodologyPage,
    title: "Cómo trabajamos las licitaciones | ASESORES LLANGON",
    description: "Un método claro para decidir, preparar, presentar y seguir licitaciones públicas con tareas, responsabilidades y plazos definidos.",
  },
  "/contratacion-publica": {
    render: procurementPage,
    title: "Contratación pública para empresas | ASESORES LLANGON",
    description: "Claves para entender los pliegos, organizar la documentación y participar en procedimientos de contratación pública en España.",
  },
  "/noticias": {
    render: resourcesPage,
    title: "Recursos sobre licitaciones públicas | ASESORES LLANGON",
    description: "Análisis y recursos prácticos sobre licitaciones y contratación pública para empresas.",
  },
  "/zona-privada": {
    render: privateAccessPage,
    title: "Zona de clientes | ASESORES LLANGON",
    description: "Información de acceso para clientes de ASESORES LLANGON.",
  },
  "/contacto": {
    render: contactPage,
    title: "Contacto para licitaciones públicas | ASESORES LLANGON",
    description: "Contacta con ASESORES LLANGON para una licitación concreta o para una gestión continuada de oportunidades y expedientes.",
  },
  "/aviso-legal": {
    render: () => legalPage("/aviso-legal"),
    title: "Aviso legal | ASESORES LLANGON",
    description: "Aviso legal de la web pública de ASESORES LLANGON, S.L.",
  },
  "/politica-privacidad": {
    render: () => legalPage("/politica-privacidad"),
    title: "Política de privacidad | ASESORES LLANGON",
    description: "Política de privacidad de la web pública de ASESORES LLANGON, S.L.",
  },
  "/politica-cookies": {
    render: () => legalPage("/politica-cookies"),
    title: "Política de cookies | ASESORES LLANGON",
    description: "Información sobre el uso de cookies en la web pública de ASESORES LLANGON, S.L.",
  },
};

function normalizedPath() {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  return path.startsWith("/noticias/") ? "/noticias" : path;
}

function setMeta(title, description) {
  document.title = title;
  const meta = document.querySelector("meta[name='description']");
  if (meta) meta.setAttribute("content", description);
}

function updateActiveNavigation(path) {
  document.querySelectorAll("[data-nav-path]").forEach((link) => {
    if (link.dataset.navPath === path) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function setMenuOpen(open) {
  if (!menuToggle || !publicNav) return;
  publicNav.classList.toggle("open", open);
  menuToggle.setAttribute("aria-expanded", String(open));
  if (menuToggleLabel) menuToggleLabel.textContent = open ? "Cerrar" : "Menú";
}

if (menuToggle && publicNav) {
  menuToggle.addEventListener("click", () => {
    setMenuOpen(!publicNav.classList.contains("open"));
  });

  publicNav.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenuOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && publicNav.classList.contains("open")) {
      setMenuOpen(false);
      menuToggle.focus();
    }
  });

  window.matchMedia("(min-width: 981px)").addEventListener("change", (event) => {
    if (event.matches) setMenuOpen(false);
  });
}

function render() {
  if (!content) return;
  const path = normalizedPath();
  const route = routes[path];

  if (route) {
    content.innerHTML = route.render();
    setMeta(route.title, route.description);
    updateActiveNavigation(path);
    return;
  }

  content.innerHTML = notFoundPage();
  setMeta("Página no encontrada | ASESORES LLANGON", "La dirección solicitada no existe en la web pública de ASESORES LLANGON.");
  updateActiveNavigation("");
}

render();
