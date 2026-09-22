import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const repoRoot = path.resolve(process.argv[2] || ".");
const outputPath = path.resolve(process.argv[3] || path.join(repoRoot, "tmp", "Ficha_Llangon_v2_base.xlsx"));
const packageRoot = path.join(repoRoot, "webapp", "infonalia_webapp", "tender_documents");
const manifest = JSON.parse(await fs.readFile(path.join(packageRoot, "field_manifest.json"), "utf8"));
const layout = JSON.parse(await fs.readFile(path.join(packageRoot, "workbook_layout.json"), "utf8"));
const logoBytes = await fs.readFile(path.join(repoRoot, "webapp", "infonalia_webapp", "static", "logo-llangon.png"));
const logoData = `data:image/png;base64,${logoBytes.toString("base64")}`;

const GREEN = "#3AAE2A";
const DARK = "#1F3027";
const DARK_GREEN = "#176B32";
const PALE_GREEN = "#EFF8F0";
const PALE_BLUE = "#EEF5F8";
const PALE_GREY = "#F3F5F4";
const BORDER = "#CBD8CF";
const INPUT = "#FFFDF4";
const WHITE = "#FFFFFF";
const AMBER = "#FFF2CC";
const RED = "#FCE8E6";

const wb = Workbook.create();
const ficha = wb.worksheets.add("Ficha");
const informe = wb.worksheets.add("Informe_PDF");
const listas = wb.worksheets.add("_Listas");
const tech = wb.worksheets.add("_Llangon");

for (const sheet of [ficha, informe, listas, tech]) sheet.showGridLines = false;
ficha.getRange("A1:H111").format.font = { name: "Aptos", size: 9, color: DARK };

function setValue(sheet, range, value) {
  sheet.getRange(range).values = [[value]];
}

function mergeValue(sheet, range, value) {
  const target = sheet.getRange(range);
  target.merge();
  target.values = [[value]];
}

function sectionHeader(sheet, row, title) {
  mergeValue(sheet, `B${row}:H${row}`, title);
  sheet.getRange(`B${row}:H${row}`).format = {
    fill: DARK_GREEN,
    font: { name: "Aptos Display", size: 11, bold: true, color: WHITE },
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: DARK_GREEN },
  };
  sheet.getRange(`B${row}:H${row}`).format.rowHeight = 23;
}

function labelCell(sheet, address, label) {
  setValue(sheet, address, label);
  sheet.getRange(address).format = {
    fill: PALE_GREY,
    font: { name: "Aptos", size: 9, bold: true, color: DARK_GREEN },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: BORDER },
  };
}

function inputCell(sheet, range, value = "", kind = "manual") {
  const target = sheet.getRange(range);
  if (range.includes(":")) target.merge();
  target.values = [[value]];
  target.format = {
    fill: kind === "automatic" ? PALE_BLUE : kind === "calculated" ? PALE_GREEN : INPUT,
    font: { name: "Aptos", size: 10, color: DARK },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: BORDER },
  };
}

// Main title and action strip.
mergeValue(ficha, "A1:H1", "FICHA LLANGON v2");
ficha.getRange("A1:H1").format = {
  fill: DARK,
  font: { name: "Aptos Display", size: 15, bold: true, color: WHITE },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
ficha.getRange("A1:H1").format.rowHeight = 29;
ficha.images.add({ dataUrl: logoData, anchor: { from: { row: 1, col: 1 }, extent: { widthPx: 150, heightPx: 63 } } });
mergeValue(ficha, "D2:H3", "Ficha profesional de licitación");
ficha.getRange("D2:H3").format = {
  font: { name: "Aptos Display", size: 20, bold: true, color: DARK_GREEN },
  horizontalAlignment: "right",
  verticalAlignment: "center",
};
mergeValue(ficha, "D4:H4", "Herramienta de trabajo · PDF profesional · Integración local segura");
ficha.getRange("D4:H4").format = { font: { name: "Aptos", size: 9, color: "#607067" }, horizontalAlignment: "right" };
mergeValue(ficha, "B6:H6", "ACCIONES");
ficha.getRange("B6:H6").format = { fill: PALE_GREEN, font: { name: "Aptos", bold: true, color: DARK_GREEN }, horizontalAlignment: "left" };
mergeValue(ficha, "B7:H8", "Los botones se incorporan al finalizar la plantilla. Abrir el libro no consulta clientes ni ejecuta procesos externos.");
ficha.getRange("B7:H8").format = { fill: PALE_GREY, font: { name: "Aptos", size: 9, color: "#607067", italic: true }, wrapText: true, verticalAlignment: "center" };

sectionHeader(ficha, 9, "Destinatario");
labelCell(ficha, "B10", "Cliente"); inputCell(ficha, "C10:H10");
labelCell(ficha, "B11", "Caché"); mergeValue(ficha, "C11:H11", "Clientes sin actualizar. La ficha funciona offline.");
ficha.getRange("C11:H11").format = { fill: PALE_GREY, font: { name: "Aptos", size: 9, color: "#607067" }, borders: { preset: "outside", style: "thin", color: BORDER } };
labelCell(ficha, "B12", "Revisión"); mergeValue(ficha, "C12:H12", "Pendiente de revisar");
ficha.getRange("C12:H12").format = { fill: PALE_GREY, font: { name: "Aptos", size: 9, bold: true, color: DARK_GREEN }, borders: { preset: "outside", style: "thin", color: BORDER } };

sectionHeader(ficha, 14, "Identificación de la licitación");
labelCell(ficha, "B16", "Expediente"); inputCell(ficha, "C16:D16", "", "automatic");
labelCell(ficha, "E16", "Fecha límite"); inputCell(ficha, "F16", "", "automatic");
labelCell(ficha, "G16", "Hora"); inputCell(ficha, "H16", "", "automatic");
labelCell(ficha, "B17", "Objeto / título"); inputCell(ficha, "C17:H18", "", "automatic");
labelCell(ficha, "B19", "Enlace"); inputCell(ficha, "C19:H19", "", "automatic");
labelCell(ficha, "B20", "Organismo"); inputCell(ficha, "C20:D20", "", "automatic");
labelCell(ficha, "E20", "Plataforma"); inputCell(ficha, "F20:H20", "", "automatic");
labelCell(ficha, "B21", "Tipo contrato"); inputCell(ficha, "C21:D21", "", "automatic");
labelCell(ficha, "E21", "Procedimiento"); inputCell(ficha, "F21:H21", "", "automatic");
labelCell(ficha, "B22", "Reg. armonizada"); inputCell(ficha, "C22:D22", "", "automatic");
labelCell(ficha, "E22", "Aviso fecha"); inputCell(ficha, "F22:H22", "Pendiente de fecha", "calculated");
labelCell(ficha, "B23", "Origen PLACE"); inputCell(ficha, "C23:H23");

sectionHeader(ficha, 25, "Datos económicos y plazos");
labelCell(ficha, "B27", "Presupuesto base"); inputCell(ficha, "C27:D27", "", "automatic");
labelCell(ficha, "E27", "Valor estimado"); inputCell(ficha, "F27:H27", "", "automatic");
labelCell(ficha, "B28", "Plazo"); inputCell(ficha, "C28:H28", "", "automatic");
labelCell(ficha, "B29", "Comentario plazo"); inputCell(ficha, "C29:H29");
labelCell(ficha, "B30", "Prórroga"); inputCell(ficha, "C30:D30", "", "automatic");
labelCell(ficha, "E30", "Detalle"); inputCell(ficha, "F30:H30");
labelCell(ficha, "B31", "Forma adjudicación"); inputCell(ficha, "C31:H31");

sectionHeader(ficha, 33, "Lotes (opcional)");
const lotRows = [["Numero", "Titulo", "Presupuesto", "ValorEstimado", "Comentarios"]];
for (let i = 0; i < 5; i++) lotRows.push(["", "", "", "", ""]);
ficha.getRange("B34:H39").values = lotRows.map(row => [row[0], row[1], row[2], row[3], row[4], "", ""]);
// Repack to five visual columns across B:H through merges is not compatible with tables;
// use B:F as the actual structured table and reserve G:H as a calm notes gutter.
ficha.getRange("B34:F39").values = lotRows;
const lotTable = ficha.tables.add("B34:F39", true, "tblLotes");
lotTable.style = "TableStyleMedium4";
mergeValue(ficha, "G34:H39", "Añada filas con Tab en la última celda de la tabla.");
ficha.getRange("G34:H39").format = { fill: PALE_GREY, font: { name: "Aptos", size: 8, italic: true, color: "#607067" }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: BORDER } };

sectionHeader(ficha, 40, "Garantías y participación");
labelCell(ficha, "B41", "Garantía provisional"); inputCell(ficha, "C41:D41"); labelCell(ficha, "E41", "Detalle"); inputCell(ficha, "F41:H41");
labelCell(ficha, "B42", "Garantía definitiva"); inputCell(ficha, "C42:D42"); labelCell(ficha, "E42", "Detalle"); inputCell(ficha, "F42:H42");
labelCell(ficha, "B43", "Garantía complementaria"); inputCell(ficha, "C43:D43"); labelCell(ficha, "E43", "Detalle"); inputCell(ficha, "F43:H43");
labelCell(ficha, "B44", "Adscripción medios"); inputCell(ficha, "C44:D44"); labelCell(ficha, "E44", "Detalle"); inputCell(ficha, "F44:H44");
labelCell(ficha, "B45", "Número sobres"); inputCell(ficha, "C45:D45"); labelCell(ficha, "E45", "Aviso"); inputCell(ficha, "F45:H45", "", "calculated");
labelCell(ficha, "B46", "Fichas técnicas"); inputCell(ficha, "C46:D46"); labelCell(ficha, "E46", "Detalle"); inputCell(ficha, "F46:H46");
labelCell(ficha, "B47", "Memoria técnica"); inputCell(ficha, "C47:D47"); labelCell(ficha, "E47", "Detalle"); inputCell(ficha, "F47:H47");
labelCell(ficha, "B48", "Subcontratación"); inputCell(ficha, "C48:D48"); labelCell(ficha, "E48", "Detalle"); inputCell(ficha, "F48:H48");

sectionHeader(ficha, 50, "Muestras");
labelCell(ficha, "B51", "Exigidas"); inputCell(ficha, "C51:D51"); labelCell(ficha, "E51", "Momento"); inputCell(ficha, "F51:H51");
labelCell(ficha, "B52", "Detalle"); inputCell(ficha, "C52:H52");

sectionHeader(ficha, 54, "Criterios sujetos a juicio de valor");
const judgmentRows = [["Orden", "Criterio", "Subcriterio", "Descripcion", "Puntos", "Comentarios"]];
for (let i = 0; i < 12; i++) judgmentRows.push([i + 1, "", "", "", "", ""]);
ficha.getRange("B55:G67").values = judgmentRows;
const judgmentTable = ficha.tables.add("B55:G67", true, "tblCriteriosJuicio");
judgmentTable.style = "TableStyleMedium4";
labelCell(ficha, "B68", "Total puntos"); inputCell(ficha, "C68", "", "calculated"); mergeValue(ficha, "D68:H68", "La suma se calcula automáticamente; 100 puntos es una advertencia, no una regla universal.");
ficha.getRange("D68:H68").format = { fill: PALE_GREY, font: { name: "Aptos", size: 8, italic: true, color: "#607067" }, wrapText: true };

sectionHeader(ficha, 70, "Criterios evaluables mediante fórmula");
const formulaRows = [["Orden", "Criterio", "Subcriterio", "Descripcion", "Puntos", "FormulaTexto", "Comentarios"]];
for (let i = 0; i < 12; i++) formulaRows.push([i + 1, "", "", "", "", "", ""]);
ficha.getRange("B71:H83").values = formulaRows;
const formulaTable = ficha.tables.add("B71:H83", true, "tblCriteriosFormula");
formulaTable.style = "TableStyleMedium4";
labelCell(ficha, "B84", "Total puntos"); inputCell(ficha, "C84", "", "calculated"); mergeValue(ficha, "D84:H84", "La fórmula jurídica se conserva como texto y no se ejecuta en Excel.");
ficha.getRange("D84:H84").format = { fill: PALE_GREY, font: { name: "Aptos", size: 8, italic: true, color: "#607067" }, wrapText: true };

sectionHeader(ficha, 86, "Condiciones especiales de ejecución");
const conditionRows = [["Orden", "Condicion", "Detalle", "Comentarios"]];
for (let i = 0; i < 8; i++) conditionRows.push([i + 1, "", "", ""]);
ficha.getRange("B87:E95").values = conditionRows;
const conditionTable = ficha.tables.add("B87:E95", true, "tblCondicionesEspeciales");
conditionTable.style = "TableStyleMedium4";
for (const headerRange of ["B34:F34", "B55:G55", "B71:H71", "B87:E87"]) {
  ficha.getRange(headerRange).format.font = { name: "Aptos", size: 9, bold: true, color: WHITE };
}
mergeValue(ficha, "F87:H95", "Incluya solo condiciones contractuales relevantes. Añada filas con Tab en la última celda.");
ficha.getRange("F87:H95").format = { fill: PALE_GREY, font: { name: "Aptos", size: 8, italic: true, color: "#607067" }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: BORDER } };

sectionHeader(ficha, 97, "Observaciones");
mergeValue(ficha, "B98:H100", "Utilice este espacio para notas breves de trabajo. Las observaciones completas se introducen en el bloque siguiente.");
ficha.getRange("B98:H100").format = { fill: PALE_GREY, font: { name: "Aptos", size: 9, italic: true, color: "#607067" }, wrapText: true, verticalAlignment: "center" };
inputCell(ficha, "B102:H108");
ficha.getRange("B102:H108").format.rowHeight = 22;
mergeValue(ficha, "B110:H111", "Documento confidencial. La información debe revisarse antes de su envío al cliente.");
ficha.getRange("B110:H111").format = { fill: PALE_GREEN, font: { name: "Aptos", size: 9, color: DARK_GREEN, italic: true }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };

// Main sheet sizing and behavior.
const widths = { A: 3, B: 22, C: 17, D: 17, E: 18, F: 18, G: 18, H: 18 };
for (const [column, width] of Object.entries(widths)) ficha.getRange(`${column}1:${column}111`).format.columnWidth = width;
ficha.getRange("16:52").format.rowHeight = 25;
ficha.getRange("17:18").format.rowHeight = 27;
ficha.getRange("23:23").format.rowHeight = 28;
ficha.freezePanes.freezeRows(9);

// Validations.
const states = ["Sí", "No", "No consta", "No aplica"];
for (const address of ["C22:D22", "C30:D30", "C41:D44", "C46:D48", "C51:D51"]) {
  ficha.getRange(address).dataValidation = { rule: { type: "list", values: states } };
}
ficha.getRange("C21:D21").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$A$2:$A$8" } };
ficha.getRange("F21:H21").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$B$2:$B$12" } };
ficha.getRange("F20:H20").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$C$2:$C$8" } };
ficha.getRange("C31:H31").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$D$2:$D$6" } };
ficha.getRange("F51:H51").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$E$2:$E$9" } };
ficha.getRange("C10:H10").dataValidation = { rule: { type: "list", formula1: "'_Listas'!$H$2:$H$501" } };

// Important conditional formats.
ficha.getRange("C16:D16").conditionalFormats.add("containsBlanks", { format: { fill: AMBER } });
ficha.getRange("C17:H18").conditionalFormats.add("containsBlanks", { format: { fill: AMBER } });
ficha.getRange("F16").conditionalFormats.add("containsBlanks", { format: { fill: AMBER } });
ficha.getRange("F22:H22").conditionalFormats.add("containsText", { text: "AVISO", format: { fill: AMBER, font: { color: "#7F6000", bold: true } } });
ficha.getRange("C12:H12").conditionalFormats.add("containsText", { text: "ERROR", format: { fill: RED, font: { color: "#9C0006", bold: true } } });

// Derived Excel fallback report. VBA refreshes the content before export.
informe.images.add({ dataUrl: logoData, anchor: { from: { row: 0, col: 0 }, extent: { widthPx: 145, heightPx: 60 } } });
mergeValue(informe, "A1:H2", "INFORME DE LICITACIÓN");
informe.getRange("A1:H2").format = { font: { name: "Aptos Display", size: 18, bold: true, color: DARK_GREEN }, horizontalAlignment: "right", verticalAlignment: "center" };
mergeValue(informe, "A4:H4", "Vista derivada para previsualización y contingencia");
informe.getRange("A4:H4").format = { fill: PALE_GREEN, font: { name: "Aptos", size: 9, italic: true, color: DARK_GREEN }, horizontalAlignment: "center" };
mergeValue(informe, "A6:H6", "Utilice «Abrir informe» para regenerar esta vista desde Ficha.");
informe.getRange("A6:H6").format = { fill: PALE_GREY, font: { name: "Aptos", size: 9, color: "#607067" }, horizontalAlignment: "center" };
for (const col of "ABCDEFGH") informe.getRange(`${col}1:${col}140`).format.columnWidth = col === "A" ? 18 : 15;

// Lists: no real clients in the master.
listas.getRange("A1:E12").values = [
  ["TipoContrato", "Procedimiento", "Plataforma", "FormaAdjudicacion", "MomentoMuestras"],
  ["Suministros", "Abierto", "PLACE", "Expediente completo", "A solicitud de la mesa"],
  ["Servicios", "Abierto simplificado", "SIREC", "Por lotes", "Durante el plazo de oferta"],
  ["Obras", "Restringido", "Plataforma de Euskadi", "Por producto", "Antes de la adjudicación"],
  ["Concesión de obras", "Negociado con publicidad", "VORTAL", "Otra", "Solo adjudicatario"],
  ["Concesión de servicios", "Negociado sin publicidad", "Portal autonómico/local", "", "Antes de la ejecución"],
  ["Mixto", "Diálogo competitivo", "Envío manual", "", "Durante la ejecución"],
  ["Otro", "Asociación para la innovación", "Otro", "", "Otro"],
  ["", "Acuerdo marco", "", "", "No consta"],
  ["", "Sistema dinámico", "", "", ""],
  ["", "Contrato menor", "", "", ""],
  ["", "Otro", "", "", ""],
];
listas.getRange("G1:M2").values = [
  ["ID", "Label", "DisplayName", "RazonSocial", "NombreComercial", "Activo", "UpdatedAt"],
  [0, "", "", "", "", 0, ""],
];
const clientsTable = listas.tables.add("G1:M2", true, "tblClientes");
clientsTable.style = "TableStyleMedium4";
listas.getRange("O1:R9").values = [
  ["Fecha", "Nombre", "Ambito", "Fuente"],
  [new Date("2026-01-01"), "Año Nuevo", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-01-06"), "Epifanía del Señor", "Nacional 2026", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-04-03"), "Viernes Santo", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-05-01"), "Fiesta del Trabajo", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-08-15"), "Asunción de la Virgen", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-10-12"), "Fiesta Nacional de España", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-12-08"), "Inmaculada Concepción", "Nacional 2026", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
  [new Date("2026-12-25"), "Natividad del Señor", "Nacional", "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-21667"],
];
listas.getRange("O2:O9").format.numberFormat = "yyyy-mm-dd";
const holidaysTable = listas.tables.add("O1:R9", true, "tblFestivos");
holidaysTable.style = "TableStyleMedium4";
for (const headerRange of ["G1:M1", "O1:R1"]) {
  listas.getRange(headerRange).format.font = { name: "Aptos", size: 9, bold: true, color: WHITE };
}
mergeValue(listas, "O11:R13", "Cobertura 2026: solo fiestas nacionales comunes publicadas en BOE. No acredita festivos autonómicos ni locales.");
listas.getRange("O11:R13").format = { fill: AMBER, font: { name: "Aptos", size: 9, color: "#7F6000" }, wrapText: true };
listas.getRange("A1:R13").format.font = { name: "Aptos", size: 9 };
const listWidths = { A: 19, B: 24, C: 24, D: 23, E: 27, F: 3, G: 9, H: 42, I: 28, J: 28, K: 28, L: 10, M: 21, N: 3, O: 14, P: 25, Q: 18, R: 58 };
for (const [column, width] of Object.entries(listWidths)) listas.getRange(`${column}1:${column}13`).format.columnWidth = width;

// Technical metadata and logical registry.
tech.getRange("A1:B21").values = [
  ["Metadato", "Valor"],
  ["document_id", ""], ["licitacion_id", ""], ["client_id", ""], ["client_razon_social", ""],
  ["client_active", ""], ["template_version", manifest.template_version], ["payload_schema_version", manifest.payload_schema_version],
  ["created_at", ""], ["source", "manual"], ["last_import_at", ""], ["clients_updated_at", ""],
  ["bridge_version", ""], ["quality_errors", 0], ["quality_warnings", 0], ["quality_info", 0],
  ["last_review_at", ""], ["quality_status", "Pendiente"], ["cache_stale_days", 7], ["early_time", "12:00"], ["last_pdf_path", ""],
];
const registryRows = [["LogicalID", "StorageKind", "Locator", "Type", "Owner", "RequiredFinal", "PDF"]];
for (const item of manifest.scalar_fields) registryRows.push([item.logical_id, "name", item.excel_name, item.type, item.owner, item.required_final ? 1 : 0, item.pdf ? 1 : 0]);
for (const item of manifest.tables) registryRows.push([item.logical_id, "table", item.excel_table, "collection", "document", 0, 1]);
tech.getRangeByIndexes(0, 3, registryRows.length, registryRows[0].length).values = registryRows;
const registryTable = tech.tables.add(`D1:J${registryRows.length}`, true, "tblFieldRegistry");
registryTable.style = "TableStyleMedium4";
tech.getRange("D1:J1").format.font = { name: "Aptos", size: 9, bold: true, color: WHITE };
tech.getRange("L1:M4").values = [
  ["Control", "Valor"], ["build_source", "scripts/build_ficha_llangon_v2.mjs"],
  ["client_refresh_policy", "manual_only"], ["external_query_on_open", "false"],
];
const techWidths = { A: 25, B: 28, C: 3, D: 34, E: 20, F: 27, G: 17, H: 18, I: 19, J: 12, K: 3, L: 28, M: 42 };
for (const [column, width] of Object.entries(techWidths)) tech.getRange(`${column}1:${column}${registryRows.length}`).format.columnWidth = width;

// Workbook-wide number formats.
ficha.getRange("F16").format.numberFormat = "dd/mm/yyyy";
ficha.getRange("H16").format.numberFormat = "hh:mm";
ficha.getRange("C27:D27").format.numberFormat = "#,##0.00 [$€-es-ES]";
ficha.getRange("F27:H27").format.numberFormat = "#,##0.00 [$€-es-ES]";
ficha.getRange("F56:F67").format.numberFormat = "0.00";
ficha.getRange("F72:F83").format.numberFormat = "0.00";

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const qaDirectory = path.join(path.dirname(outputPath), "renders");
await fs.mkdir(qaDirectory, { recursive: true });
const keyRanges = await wb.inspect({
  kind: "table",
  range: "Ficha!B1:H25",
  include: "values,formulas",
  tableMaxRows: 25,
  tableMaxCols: 7,
  maxChars: 7000,
});
const formulaErrors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 5000,
});
const renderTargets = [
  ["Ficha", "A1:H111", "Ficha.png"],
  ["Informe_PDF", "A1:H20", "Informe_PDF.png"],
  ["_Listas", "A1:R13", "Listas.png"],
  ["_Llangon", `A1:M${registryRows.length}`, "Llangon.png"],
];
for (const [sheetName, range, fileName] of renderTargets) {
  const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(qaDirectory, fileName), new Uint8Array(await preview.arrayBuffer()));
}
await fs.writeFile(
  path.join(qaDirectory, "inspection.json"),
  JSON.stringify({ key_ranges: keyRanges.ndjson, formula_errors: formulaErrors.ndjson }, null, 2),
  "utf8",
);
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, qaDirectory, sheets: ["Ficha", "Informe_PDF", "_Listas", "_Llangon"], names: Object.keys(layout.names).length }));
