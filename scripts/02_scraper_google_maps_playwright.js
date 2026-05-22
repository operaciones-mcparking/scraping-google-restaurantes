const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { spawnSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_CONFIG = path.join(ROOT, "configs", "scraper_google_maps.json");
const BUNDLED_PLAYWRIGHT = "C:/Users/gabyp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs";
const BUNDLED_PYTHON = "C:\\Users\\gabyp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const CSV_TO_XLSX = path.join(ROOT, "scripts", "convert_csv_to_xlsx.py");

const FIELDS = [
  "Nombre restaurante",
  "Rating",
  "Cantidad reviews",
  "Dirección",
  "Teléfono",
  "Sitio web",
  "Categoría",
  "Google Maps URL",
  "Latitud",
  "Longitud",
  "Comuna",
  "Región",
  "País",
  "Fuente",
  "Fecha extracción",
  "Calidad dato",
  "Es restaurante válido",
  "Instagram URL",
  "Instagram Usuario",
  "Facebook URL",
  "TikTok URL",
  "Tiene Redes",
  "Calidad Redes",
  "Está en Uber Eats",
  "URL Uber Eats",
  "Confianza Uber Eats",
  "Está en PedidosYa",
  "URL PedidosYa",
  "Confianza PedidosYa",
  "Está en Rappi",
  "URL Rappi",
  "Confianza Rappi",
  "Observaciones",
];

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { config: DEFAULT_CONFIG, check: false };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--config" && args[i + 1]) {
      parsed.config = path.resolve(args[i + 1]);
      i += 1;
    } else if (args[i] === "--check") {
      parsed.check = true;
    }
  }
  return parsed;
}

function loadConfig(configPath) {
  const raw = fs.readFileSync(configPath, "utf8");
  const parsed = JSON.parse(raw);
  return parsed.piloto || parsed;
}

function resolveProjectPath(value) {
  return path.isAbsolute(value) ? value : path.join(ROOT, value);
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function makeLogger(logPath) {
  ensureDir(logPath);
  return (message) => {
    const line = `${new Date().toISOString()} ${message}`;
    console.log(line);
    fs.appendFileSync(logPath, `${line}\n`, "utf8");
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function slowPause(config, log, reason) {
  const min = Number(config.pausaMinMs || 2000);
  const max = Number(config.pausaMaxMs || 5000);
  const wait = Math.floor(min + Math.random() * Math.max(max - min, 0));
  log(`Pausa ${wait} ms: ${reason}`);
  await sleep(wait);
}

async function loadPlaywright() {
  try {
    return require("playwright");
  } catch {
    const moduleUrl = pathToFileURL(BUNDLED_PLAYWRIGHT).href;
    return import(moduleUrl);
  }
}

function escapeCsv(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function writeCsv(filePath, rows) {
  ensureDir(filePath);
  const lines = [FIELDS.map(escapeCsv).join(",")];
  for (const row of rows) {
    lines.push(FIELDS.map((field) => escapeCsv(row[field])).join(","));
  }
  fs.writeFileSync(filePath, `${lines.join("\n")}\n`, "utf8");
}

function writeRawJson(filePath, payload) {
  ensureDir(filePath);
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf8");
}

function convertToExcel(csvPath, xlsxPath, log) {
  if (!fs.existsSync(BUNDLED_PYTHON) || !fs.existsSync(CSV_TO_XLSX)) {
    log("No se encontró Python o convert_csv_to_xlsx.py. Se deja solo CSV.");
    return false;
  }

  const result = spawnSync(BUNDLED_PYTHON, [CSV_TO_XLSX, csvPath, xlsxPath], {
    cwd: ROOT,
    encoding: "utf8",
  });

  if (result.stdout) log(result.stdout.trim());
  if (result.stderr) log(result.stderr.trim());
  if (result.status !== 0) {
    log(`No se pudo crear Excel. Código: ${result.status}`);
    return false;
  }
  return true;
}

function parseLatLng(url) {
  const atMatch = url.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
  if (atMatch) return { lat: atMatch[1], lng: atMatch[2] };

  const dataMatch = url.match(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/);
  if (dataMatch) return { lat: dataMatch[1], lng: dataMatch[2] };

  return { lat: "", lng: "" };
}

function parseRating(text) {
  const match = text.match(/(\d+[,.]\d+)/);
  return match ? match[1].replace(",", ".") : "";
}

function parseReviews(text) {
  const source = String(text || "");
  const compactMatch = source.match(/\d[,.]\d\s*(\d{1,6})\s*(reseñas|resenas|opiniones|reviews)/i);
  if (compactMatch) return compactMatch[1].replace(/\./g, "").replace(/,/g, "");

  const reviewMatch = source.match(/(\d{1,3}(?:[.,]\d{3})*|\d+)\s*(reseñas|resenas|opiniones|reviews)/i);
  if (reviewMatch) return reviewMatch[1].replace(/\./g, "").replace(/,/g, "");

  const reverseMatch = source.match(/(reseñas|resenas|opiniones|reviews)\s*\(?(\d{1,3}(?:[.,]\d{3})*|\d+)\)?/i);
  if (reverseMatch) return reverseMatch[2].replace(/\./g, "").replace(/,/g, "");

  return "";
}

function cleanLabeledValue(text) {
  return String(text || "")
    .replace(/^(Direcci.n|Tel.fono|Sitio web|Website|Phone|Address):\s*/i, "")
    .trim();
}

function normalizeText(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function normalizeKey(text) {
  return normalizeText(text).replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

function normalizePhone(text) {
  return cleanLabeledValue(text)
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeAddress(text) {
  return cleanLabeledValue(text)
    .replace(/\s+/g, " ")
    .trim();
}

function classifyQuality(row) {
  if (!row["Dirección"]) return "Sin dirección";
  if (!row["Teléfono"]) return "Sin teléfono";
  if (row["Nombre restaurante"] && row["Rating"] && row["Cantidad reviews"] && row["Sitio web"]) return "Completo";
  return "Parcial";
}

function classifyRestaurant(row) {
  const category = normalizeText(row["Categoría"]);
  const name = normalizeText(row["Nombre restaurante"]);
  const combined = `${category} ${name}`;
  const validTerms = [
    "restaurante",
    "restaurant",
    "bistro",
    "bistro",
    "cocina",
    "parrilla",
    "pizzeria",
    "sushi",
    "peruano",
    "italiano",
    "comida",
  ];
  const uncertainTerms = [
    "cafeteria",
    "cafe",
    "comida rapida",
    "fast food",
    "dark kitchen",
    "delivery",
    "take away",
    "comida para llevar",
    "hamburgueseria",
    "sandwich",
    "pasteleria",
    "panaderia",
  ];

  const observations = [];
  let valid = validTerms.some((term) => combined.includes(term));
  for (const term of uncertainTerms) {
    if (combined.includes(term)) {
      observations.push(`Revisar: parece ${term}`);
      valid = valid && !["cafeteria", "cafe", "dark kitchen", "delivery", "pasteleria", "panaderia"].includes(term);
    }
  }

  if (!row["Nombre restaurante"]) {
    observations.push("Sin nombre visible");
    valid = false;
  }
  if (!row["Dirección"]) observations.push("Sin dirección visible");
  if (!row["Teléfono"]) observations.push("Sin teléfono visible");

  return {
    isValid: valid ? "Sí" : "No",
    observations,
  };
}

function enrichRow(row) {
  const classification = classifyRestaurant(row);
  const quality = classifyQuality(row);
  const existingObservations = row["Observaciones"] ? [row["Observaciones"]] : [];
  return {
    ...row,
    "Calidad dato": quality,
    "Es restaurante válido": classification.isValid,
    "Instagram URL": row["Instagram URL"] || "",
    "Instagram Usuario": row["Instagram Usuario"] || "",
    "Facebook URL": row["Facebook URL"] || "",
    "TikTok URL": row["TikTok URL"] || "",
    "Tiene Redes": row["Tiene Redes"] || "",
    "Calidad Redes": row["Calidad Redes"] || "",
    "Está en Uber Eats": row["Está en Uber Eats"] || "",
    "URL Uber Eats": row["URL Uber Eats"] || "",
    "Confianza Uber Eats": row["Confianza Uber Eats"] || "",
    "Está en PedidosYa": row["Está en PedidosYa"] || "",
    "URL PedidosYa": row["URL PedidosYa"] || "",
    "Confianza PedidosYa": row["Confianza PedidosYa"] || "",
    "Está en Rappi": row["Está en Rappi"] || "",
    "URL Rappi": row["URL Rappi"] || "",
    "Confianza Rappi": row["Confianza Rappi"] || "",
    "Observaciones": [...existingObservations, ...classification.observations].filter(Boolean).join("; "),
  };
}

function dedupeRows(rows, log) {
  const seen = new Set();
  const deduped = [];

  for (const row of rows) {
    const urlKey = String(row["Google Maps URL"] || "").match(/1s([^!&?]+)/)?.[1] || "";
    const key = urlKey || `${normalizeKey(row["Nombre restaurante"])}|${normalizeKey(row["Dirección"])}`;
    if (!key || seen.has(key)) {
      log(`Duplicado omitido: ${row["Nombre restaurante"] || row["Google Maps URL"] || "sin nombre"}`);
      continue;
    }
    seen.add(key);
    deduped.push(row);
  }

  return deduped;
}

function countEmpty(rows, field) {
  return rows.filter((row) => !String(row[field] || "").trim()).length;
}

function buildSummary(rowsBeforeDedupe, finalRows) {
  return {
    "Total filas extraídas": finalRows.length,
    "Total restaurantes válidos": finalRows.filter((row) => row["Es restaurante válido"] === "Sí").length,
    "Total no válidos": finalRows.filter((row) => row["Es restaurante válido"] === "No").length,
    "Teléfonos vacíos": countEmpty(finalRows, "Teléfono"),
    "Direcciones vacías": countEmpty(finalRows, "Dirección"),
    "Sitios web vacíos": countEmpty(finalRows, "Sitio web"),
    "Duplicados eliminados": Math.max(rowsBeforeDedupe - finalRows.length, 0),
  };
}

function printSummary(summary, log) {
  log("Resumen final:");
  for (const [label, value] of Object.entries(summary)) {
    log(`${label}: ${value}`);
  }
}

async function firstText(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if (await locator.count()) {
        const text = (await locator.innerText({ timeout: 2500 })).trim();
        if (text) return text;
      }
    } catch {
      // Try the next selector.
    }
  }
  return "";
}

async function firstAttribute(page, selectors, attr) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if (await locator.count()) {
        const value = await locator.getAttribute(attr, { timeout: 2500 });
        if (value) return value;
      }
    } catch {
      // Try the next selector.
    }
  }
  return "";
}

async function buttonTextByDataItem(page, prefixes) {
  for (const prefix of prefixes) {
    const selector = `button[data-item-id^="${prefix}"], a[data-item-id^="${prefix}"]`;
    const locator = page.locator(selector).first();
    try {
      if (await locator.count()) {
        const aria = await locator.getAttribute("aria-label", { timeout: 2500 });
        const text = await locator.innerText({ timeout: 2500 }).catch(() => "");
        return cleanLabeledValue(aria || text || "");
      }
    } catch {
      // Try the next selector.
    }
  }
  return "";
}

async function extractRatingAndReviews(page) {
  const signals = await page.evaluate(() => {
    const values = [];
    for (const node of document.querySelectorAll("h1, button, span, div, a")) {
      const aria = node.getAttribute("aria-label");
      const text = node.textContent;
      if (aria) values.push(aria.trim());
      if (text) values.push(text.trim());
      if (values.length > 600) break;
    }
    return [...new Set(values.filter(Boolean))];
  }).catch(() => []);

  let rating = "";
  let reviews = "";

  for (const value of signals) {
    if (!rating && /(estrellas|stars)/i.test(value)) {
      rating = parseRating(value);
    }
    if (!reviews && /(reseñas|resenas|opiniones|reviews)/i.test(value)) {
      reviews = parseReviews(value);
    }
    if (rating && reviews) break;
  }

  if (!rating) {
    for (const value of signals) {
      const match = value.match(/^(\d+[,.]\d)$/);
      if (match) {
        rating = match[1].replace(",", ".");
        break;
      }
    }
  }

  return { rating, reviews };
}

async function detectBlock(page) {
  const url = page.url().toLowerCase();
  if (url.includes("/sorry/") || url.includes("captcha")) return "URL de captcha o bloqueo";

  const body = (await page.locator("body").innerText({ timeout: 5000 }).catch(() => "")).toLowerCase();
  const markers = [
    "unusual traffic",
    "tráfico inusual",
    "captcha",
    "no soy un robot",
    "not a robot",
  ];
  const marker = markers.find((item) => body.includes(item));
  return marker ? `Texto de bloqueo detectado: ${marker}` : "";
}

async function acceptConsentIfVisible(page, log) {
  const buttons = [
    "Aceptar todo",
    "Acepto",
    "Aceptar",
    "Reject all",
    "Accept all",
  ];
  for (const label of buttons) {
    const button = page.getByRole("button", { name: label }).first();
    try {
      if (await button.count()) {
        await button.click({ timeout: 2500 });
        log(`Se cerró aviso de consentimiento: ${label}`);
        await sleep(1000);
        return;
      }
    } catch {
      // Try next button.
    }
  }
}

async function collectResultLinks(page, config, log) {
  const links = new Map();
  const feed = page.locator('div[role="feed"]').first();

  for (let scroll = 0; scroll <= Number(config.maxScrolls || 3); scroll += 1) {
    const candidates = await page.locator('a[href*="/maps/place/"]').evaluateAll((nodes) =>
      nodes.map((node) => ({
        href: node.href,
        text: (node.getAttribute("aria-label") || node.textContent || "").trim(),
      }))
    ).catch(() => []);

    for (const item of candidates) {
      if (item.href && !links.has(item.href)) links.set(item.href, item.text);
      if (links.size >= Number(config.maxResultados || 10)) break;
    }

    log(`Resultados visibles acumulados: ${links.size}`);
    if (links.size >= Number(config.maxResultados || 10)) break;
    if (scroll >= Number(config.maxScrolls || 3)) break;

    if (await feed.count()) {
      await feed.evaluate((node) => node.scrollBy(0, Math.floor(node.clientHeight * 0.85)));
    } else {
      await page.mouse.wheel(0, 900);
    }
    await slowPause(config, log, `scroll ${scroll + 1}`);
  }

  return [...links.keys()].slice(0, Number(config.maxResultados || 10));
}

async function scrapePlace(page, url, config, log) {
  log(`Abriendo ficha: ${url}`);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await slowPause(config, log, "espera de ficha");

  const block = await detectBlock(page);
  if (block) throw new Error(`Bloqueo/captcha detectado. ${block}`);

  const name = await firstText(page, ["h1"]);
  const ratingReviews = await extractRatingAndReviews(page);
  const ratingLabel = await firstAttribute(page, ['div[role="img"][aria-label*="estrellas"]', 'span[role="img"][aria-label*="estrellas"]'], "aria-label");
  const ratingText = ratingLabel || await firstText(page, ['span[aria-hidden="true"]']);
  const reviewsLabel = await firstAttribute(page, ['button[aria-label*="reseñas"]', 'button[aria-label*="opiniones"]'], "aria-label");
  const reviewsText = reviewsLabel || await firstText(page, ['button:has-text("reseñas")', 'button:has-text("opiniones")']);

  const address = normalizeAddress(await buttonTextByDataItem(page, ["address"]));
  const phone = normalizePhone(await buttonTextByDataItem(page, ["phone:tel", "phone"]));
  const website = await firstAttribute(page, ['a[data-item-id="authority"]', 'a[aria-label*="Sitio web"]'], "href");
  const category = await firstText(page, ['button[jsaction*="category"]', 'button:near(h1)']);
  const finalUrl = page.url();
  const { lat, lng } = parseLatLng(finalUrl);

  const row = {
    "Nombre restaurante": name,
    "Rating": ratingReviews.rating || parseRating(ratingText),
    "Cantidad reviews": ratingReviews.reviews || parseReviews(reviewsText),
    "Dirección": address,
    "Teléfono": phone,
    "Sitio web": website,
    "Categoría": category,
    "Google Maps URL": finalUrl,
    "Latitud": lat,
    "Longitud": lng,
    "Comuna": config.comuna,
    "Región": config.region,
    "País": config.pais,
    "Fuente": "Google Maps web scraping con Playwright",
    "Fecha extracción": new Date().toISOString().slice(0, 10),
    "Observaciones": "",
  };

  return enrichRow(row);
}

async function main() {
  const args = parseArgs();
  const config = loadConfig(args.config);
  const logPath = resolveProjectPath(config.log || "data/logs/google_maps_scraper.log");
  const log = makeLogger(logPath);

  const csvPath = resolveProjectPath(config.salidaCsv);
  const xlsxPath = resolveProjectPath(config.salidaExcel);
  const rawPath = resolveProjectPath(config.salidaRaw);
  const query = `${config.busqueda} en ${config.comuna}, Región ${config.region}, ${config.pais}`;
  const searchUrl = `https://www.google.com/maps/search/${encodeURIComponent(query)}?hl=es-419`;

  log("Inicio scraper Google Maps piloto");
  log(`Búsqueda: ${query}`);
  log(`Máximo resultados: ${config.maxResultados}. Scrolls máximos: ${config.maxScrolls}`);

  const { chromium } = await loadPlaywright();
  if (args.check) {
    log("Playwright carga correctamente.");
    if (!fs.existsSync(config.chromePath)) {
      throw new Error(`No se encontró Chrome en chromePath: ${config.chromePath}`);
    }
    const browser = await chromium.launch({
      headless: true,
      executablePath: config.chromePath,
      args: ["--lang=es-419"],
    });
    await browser.close();
    log("Chrome local abre y cierra correctamente con Playwright.");
    return;
  }

  if (!fs.existsSync(config.chromePath)) {
    throw new Error(`No se encontró Chrome en chromePath: ${config.chromePath}`);
  }

  const browser = await chromium.launch({
    headless: Boolean(config.headless),
    executablePath: config.chromePath,
    args: ["--lang=es-419"],
  });

  const context = await browser.newContext({
    locale: "es-419",
    viewport: { width: 1365, height: 900 },
  });
  const page = await context.newPage();
  const rows = [];
  const raw = { config, searchUrl, startedAt: new Date().toISOString(), resultUrls: [], rows: [] };

  try {
    log(`Abriendo Google Maps: ${searchUrl}`);
    await page.goto(searchUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await slowPause(config, log, "carga inicial");
    await acceptConsentIfVisible(page, log);

    const block = await detectBlock(page);
    if (block) throw new Error(`Bloqueo/captcha detectado. ${block}`);

    const urls = await collectResultLinks(page, config, log);
    raw.resultUrls = urls;
    log(`Fichas a abrir una por una: ${urls.length}`);

    for (let index = 0; index < urls.length; index += 1) {
      const url = urls[index];
      log(`Procesando ${index + 1}/${urls.length}`);
      try {
        const row = await scrapePlace(page, url, config, log);
        rows.push(row);
        raw.rows.push(row);
      } catch (error) {
        const message = error && error.message ? error.message : String(error);
        log(`Error en ficha: ${message}`);
        if (message.toLowerCase().includes("captcha") || message.toLowerCase().includes("bloqueo")) {
          throw error;
        }
      }
      await slowPause(config, log, "pausa entre fichas");
    }

    const finalRows = dedupeRows(rows, log).slice(0, Number(config.maxResultados || 10));
    raw.rows = finalRows;
    raw.finishedAt = new Date().toISOString();
    raw.rowsBeforeDedupe = rows.length;
    raw.rowsAfterDedupe = finalRows.length;
    raw.summary = buildSummary(rows.length, finalRows);

    writeCsv(csvPath, finalRows);
    writeRawJson(rawPath, raw);
    log(`CSV creado: ${csvPath}`);
    log(`RAW JSON creado: ${rawPath}`);

    if (finalRows.length > 0) {
      convertToExcel(csvPath, xlsxPath, log);
    } else {
      log("No se creó Excel porque no hubo filas extraídas.");
    }

    printSummary(raw.summary, log);
    log(`Fin scraper. Filas extraídas: ${finalRows.length}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  const message = error && error.stack ? error.stack : String(error);
  console.error(message);
  process.exit(1);
});
