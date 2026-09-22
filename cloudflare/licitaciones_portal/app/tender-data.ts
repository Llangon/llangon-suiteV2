export type Detail = {
  label: string;
  value: string;
  note?: string;
  emphasis?: "positive" | "warning";
};

export type Criterion = {
  name: string;
  score: string;
  description: string;
};

export type TableBlock = {
  id?: string;
  sourcePages?: number[];
  type: "table";
  title?: string;
  caption?: string;
  columns: string[];
  rows: string[][];
};

export type TextBlock = {
  id?: string;
  sourcePages?: number[];
  type: "text";
  title?: string;
  paragraphs?: string[];
  bullets?: string[];
};

export type NoticeBlock = {
  id?: string;
  sourcePages?: number[];
  type: "notice";
  tone: "important" | "success" | "neutral";
  title: string;
  text: string;
};

export type CriteriaBlock = {
  id?: string;
  sourcePages?: number[];
  type: "criteria";
  title: string;
  scope: string;
  criteria: Criterion[];
  total: string;
};

export type CardsBlock = {
  id?: string;
  sourcePages?: number[];
  type: "cards";
  items: Array<{ title: string; text: string }>;
};

export type SourcePageBlock = {
  type: "source_page";
  page: number;
  text: string;
  sourcePages: number[];
  sourceSha256: string;
  visualFallbackRequired?: boolean;
};

export type ContentBlock = TextBlock | NoticeBlock | CriteriaBlock | TableBlock | CardsBlock | SourcePageBlock;

export type TenderSection = {
  id: string;
  eyebrow: string;
  title: string;
  introduction?: string;
  sourcePages: number[];
  blocks: ContentBlock[];
};

export const tender = {
  recipient: "ASTURSANTINA DISTRIBUCIÓN SL",
  reference: "6301-631-1-2026-17043",
  title: "Suministro de víveres de almacenamiento CAUSE",
  submissionChannel: "Electrónica · Plataforma de Contratación del Sector Público",
  tenderUrl: "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=SrPFd8l3%2BZ6ExvMJXBMHHQ%3D%3D",
  deadline: { day: "26", month: "agosto", year: "2026", weekday: "miércoles", time: "23:59" },
  sourcePages: 7,
  highlights: [
    { label: "Fecha límite", value: "26 agosto 2026", detail: "miércoles · 23:59" },
    { label: "Presupuesto", value: "229.197,53 €", detail: "sin impuestos" },
    { label: "Valor estimado", value: "504.234,57 €", detail: "duración total prevista" },
    { label: "Presentación", value: "Electrónica", detail: "Plataforma de Contratación" },
  ],
  details: [
    { label: "Tipo de contrato", value: "Suministros" },
    { label: "Regulación armonizada", value: "Sí", emphasis: "positive" },
    { label: "Presupuesto", value: "229.197,53 €" },
    { label: "Valor estimado", value: "504.234,57 €" },
    { label: "Plazo inicial", value: "12 meses", note: "Desde el 1 de noviembre de 2026 o desde la formalización si fuera posterior." },
    { label: "Prórrogas", value: "Sí", note: "Doce meses, obligatoria para el empresario con preaviso de dos meses." },
    { label: "Adjudicación", value: "Por lotes" },
    { label: "Garantía provisional", value: "No" },
    { label: "Garantía definitiva", value: "Sí", emphasis: "positive" },
    { label: "Garantía complementaria", value: "No" },
    { label: "Adscripción de medios", value: "No" },
    { label: "Número de sobres", value: "2" },
    { label: "Fichas técnicas", value: "Sí", emphasis: "warning" },
    { label: "Memoria técnica", value: "No" },
  ] satisfies Detail[],
  sections: [
    {
      id: "presentacion",
      eyebrow: "Presentación",
      title: "Condiciones para preparar la oferta",
      introduction: "Requisitos que deben tenerse en cuenta antes de confeccionar y presentar la documentación.",
      sourcePages: [1, 2],
      blocks: [
        {
          type: "text",
          title: "Subcontratación",
          paragraphs: [
            "La oferta deberá indicar la parte del contrato que se prevé subcontratar, su importe y el nombre o perfil empresarial del posible subcontratista.",
            "La subcontratación quedará sometida a los requisitos y limitaciones establecidos en la documentación contractual y en la legislación aplicable.",
          ],
          bullets: [
            "No se exige información adicional distinta de la prevista en los pliegos.",
            "Las prestaciones esenciales y las prohibiciones indicadas en el contrato deberán respetarse íntegramente.",
          ],
        },
        {
          type: "cards",
          items: [
            { title: "Muestras", text: "No se exige presentación de muestras." },
            { title: "Fichas técnicas", text: "Sí. Deben aportarse conforme a las condiciones del expediente." },
            { title: "Sobres", text: "La licitación se presenta en dos sobres electrónicos." },
          ],
        },
      ],
    },
    {
      id: "criterios",
      eyebrow: "Adjudicación",
      title: "Criterios de valoración",
      introduction: "La ponderación cambia en el lote de conservas; por eso se presenta cada ámbito de valoración de forma independiente.",
      sourcePages: [2, 3, 4],
      blocks: [
        {
          type: "criteria",
          title: "Criterios mediante fórmulas",
          scope: "Lotes 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 y 15",
          criteria: [
            { name: "Precio", score: "Hasta 100 puntos", description: "La oferta se valora mediante la fórmula económica indicada en el pliego. Las ofertas que superen el precio unitario máximo quedan excluidas." },
          ],
          total: "100 puntos",
        },
        {
          type: "criteria",
          title: "Criterios mediante fórmulas",
          scope: "Lote 2 · Conservas",
          criteria: [
            { name: "Precio", score: "Hasta 70 puntos", description: "Valoración proporcional de la oferta económica conforme a los precios máximos del lote." },
            { name: "Peso neto escurrido", score: "Hasta 30 puntos", description: "Valoración del mayor peso neto escurrido ofertado para cada producto, expresado en gramos." },
          ],
          total: "100 puntos",
        },
        {
          type: "notice",
          tone: "neutral",
          title: "Condición especial de ejecución",
          text: "Los vehículos destinados al transporte de los bienes deberán disponer de un distintivo ambiental que cumpla las condiciones medioambientales indicadas en la ficha.",
        },
      ],
    },
    {
      id: "condiciones",
      eyebrow: "Ejecución",
      title: "Entrega, recepción y requisitos operativos",
      introduction: "Condiciones aplicables durante la ejecución del suministro y documentación que podrá exigirse al adjudicatario.",
      sourcePages: [5, 6],
      blocks: [
        {
          type: "cards",
          items: [
            { title: "Lugar de entrega", text: "Almacén de productos de cocina situado en Segovia, en el punto de recepción indicado por el centro." },
            { title: "Pedidos ordinarios", text: "Plazo máximo de entrega de 72 horas desde la recepción del pedido." },
            { title: "Pedidos urgentes", text: "Plazo máximo de 24 horas; para productos perecederos se aplicarán los tiempos específicos establecidos." },
            { title: "Recepción", text: "Los pedidos se efectuarán por teléfono o correo electrónico y su recepción se realizará por la mañana hasta las 14:00 horas." },
          ],
        },
        {
          type: "text",
          title: "Obligaciones del adjudicatario",
          bullets: [
            "Seguro de responsabilidad civil con el límite de indemnización indicado en el expediente.",
            "Sistema de autocontrol y documentación de seguridad alimentaria aplicable.",
            "Inscripción o autorización sanitaria y demás acreditaciones exigibles.",
            "Cumplimiento de las condiciones de calidad, conservación, limpieza y transporte de los productos.",
          ],
        },
        {
          type: "notice",
          tone: "important",
          title: "Control de calidad",
          text: "No podrán utilizarse productos químicos para el mantenimiento de los alimentos ni admitirse suciedad en productos o envases. Todos los productos deberán cumplir la normativa técnico-sanitaria aplicable.",
        },
      ],
    },
    {
      id: "antecedentes",
      eyebrow: "Referencia histórica",
      title: "Licitación anterior",
      introduction: "La ficha incorpora información histórica para facilitar la comparación. Estos datos se muestran separados de la licitación actual.",
      sourcePages: [7],
      blocks: [
        {
          type: "table",
          title: "Resultado por lotes · año 2023",
          caption: "Ejemplo de tabla extensa conservada como contenido web y adaptada para pantallas pequeñas.",
          columns: ["Lote", "Denominación", "Baja", "Puntuación", "Resultado"],
          rows: [
            ["1", "Aceites y aceitunas", "7,95 %", "100,00", "Adjudicado"],
            ["2", "Conservas", "50,76 %", "100,00", "Desierto"],
            ["3", "Arroz, cacao, café e infusiones", "33,47 %", "73,90", "Adjudicado"],
            ["4", "Legumbres y arroz", "9,88 %", "100,00", "Adjudicado"],
            ["5", "Fiambres y arroz", "6,56 %", "100,00", "Adjudicado"],
            ["6", "Pastas y harinas", "4,73 %", "98,91", "Adjudicado"],
            ["7", "Bollería, galletas y cereales", "3,08 %", "97,79", "Adjudicado"],
            ["8", "Leche y derivados", "2,13 %", "98,24", "Adjudicado"],
            ["9", "Huevos y derivados", "0,48 %", "100,00", "Adjudicado"],
            ["10", "Condimentos y salsas", "3,02 %", "100,00", "Adjudicado"],
            ["11", "Varios", "7,29 %", "100,00", "Adjudicado"],
            ["12", "Agua y zumos", "4,01 %", "99,24", "Adjudicado"],
            ["13", "Atún y caballa", "8,47 %", "100,00", "Adjudicado"],
            ["14", "Pan de día", "0,43 %", "93,65", "Adjudicado"],
            ["15", "Yogures y otros lácteos", "—", "—", "Desierto"],
          ],
        },
        {
          type: "notice",
          tone: "important",
          title: "Información histórica",
          text: "Los resultados anteriores son orientativos y no modifican las condiciones de la licitación actual.",
        },
      ],
    },
  ] satisfies TenderSection[],
  downloads: [
    { name: "Ficha.pdf", type: "PDF", size: "614 KB", description: "Ficha completa de la licitación preparada para el destinatario." },
    { name: "Pliego de cláusulas administrativas.pdf", type: "PDF", size: "2,8 MB", description: "Condiciones administrativas que regulan el procedimiento." },
    { name: "Pliego de prescripciones técnicas.pdf", type: "PDF", size: "1,6 MB", description: "Requisitos técnicos del suministro y de los productos." },
    { name: "Plantilla de oferta económica.xlsx", type: "XLSX", size: "186 KB", description: "Archivo editable para preparar la propuesta económica." },
    { name: "Cuadro licitación anterior.xlsx", type: "XLSX", size: "94 KB", description: "Información de referencia correspondiente al procedimiento anterior." },
  ],
};
