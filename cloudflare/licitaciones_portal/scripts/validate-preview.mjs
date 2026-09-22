import { readFile } from "node:fs/promises";

const baseUrl = process.env.PORTAL_PREVIEW_URL || "http://localhost:3000/";
const response = await fetch(baseUrl);
if (!response.ok) throw new Error(`La vista previa respondió con estado ${response.status}.`);

const html = await response.text();
const requiredContent = [
  "ASTURSANTINA DISTRIBUCIÓN SL",
  "6301-631-1-2026-17043",
  "Características de la licitación",
  "Condiciones para preparar la oferta",
  "Criterios de valoración",
  "Entrega, recepción y requisitos operativos",
  "Licitación anterior",
  "Descargas",
  "Cobertura completa obligatoria",
  "Ficha.pdf",
  "Plantilla de oferta económica.xlsx",
];

for (const text of requiredContent) {
  if (!html.includes(text)) throw new Error(`Falta contenido esperado en la vista previa: ${text}`);
}

for (const id of ["resumen", "presentacion", "criterios", "condiciones", "antecedentes", "descargas"]) {
  if (!html.includes(`id=\"${id}\"`)) throw new Error(`Falta la sección #${id}.`);
}

if (html.includes("Your site is taking shape")) throw new Error("La página inicial del proyecto sigue presente.");
if (!html.includes("og.png") || !html.includes("Portal de licitaciones | Llangón Asesores")) {
  throw new Error("Faltan los metadatos sociales neutros del portal.");
}

const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
for (const rule of ["@media print", "@page", "max-width: 620px", "print-color-adjust"]) {
  if (!css.includes(rule)) throw new Error(`Falta la regla de presentación: ${rule}`);
}

const data = await readFile(new URL("../app/tender-data.ts", import.meta.url), "utf8");
for (const blockType of ["text", "cards", "criteria", "notice", "table"]) {
  if (!data.includes(`type: \"${blockType}\"`)) throw new Error(`El modelo no incluye bloques de tipo ${blockType}.`);
}

console.log("Vista previa, contenido flexible, responsive e impresión: OK");
