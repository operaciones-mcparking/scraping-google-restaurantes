import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = new URL("../data/", import.meta.url);
const outputPath = new URL("../data/plantilla_restaurantes_chile.xlsx", import.meta.url);

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Restaurantes");

const headers = [
  "Nombre del restaurante",
  "Teléfono",
  "Dirección",
  "Comuna",
  "Región",
  "Sitio web",
  "Rating",
  "Cantidad de reseñas",
  "Link de Google Maps",
  "Latitud",
  "Longitud",
  "Categoría",
  "Fuente",
  "Fecha de actualización",
  "Place ID",
  "Presente en Rappi",
  "Link Rappi",
  "Presente en Uber Eats",
  "Link Uber Eats",
  "Presente en PedidosYa",
  "Link PedidosYa",
  "Fecha de verificación delivery",
  "Método de verificación",
];

sheet.getRange("A1:W1").values = [headers];
sheet.getRange("A2:W2").values = [[
  "Ejemplo Restaurante",
  "+56 2 1234 5678",
  "Av. Ejemplo 123",
  "Santiago",
  "Región Metropolitana",
  "https://ejemplo.cl",
  4.5,
  120,
  "https://maps.google.com/?cid=ejemplo",
  -33.4489,
  -70.6693,
  "Restaurante",
  "Google Places API (New)",
  new Date(),
  "places/ejemplo",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
]];

const notes = workbook.worksheets.add("Guía");
notes.getRange("A1:B8").values = [
  ["Tema", "Detalle"],
  ["Uso", "Esta plantilla muestra las columnas esperadas para la base final."],
  ["Etapa 1", "Ejecutar scripts/01_extraer_google_places.ps1 para poblar datos desde Google Places."],
  ["Etapa 2", "Revisar duplicados y datos faltantes en Excel."],
  ["Etapa 3", "Agregar columnas de presencia en Rappi, Uber Eats y PedidosYa."],
  ["Fuente principal", "Google Places API (New), respetando políticas de uso y atribución."],
  ["Fuente secundaria", "leads-rappi solo como referencia secundaria, no como base principal."],
  ["Actualización", "Registrar siempre la fecha de actualización."],
];

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(`Plantilla creada en ${outputPath.pathname}`);
