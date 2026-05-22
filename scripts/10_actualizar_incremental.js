const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_CONFIG = path.join(ROOT, "configs", "actualizacion_incremental.json");
const NODE = "C:\\Users\\gabyp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\bin\\node.exe";
const PYTHON = "C:\\Users\\gabyp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const IMPORTER = path.join(ROOT, "scripts", "09_importar_base_a_sqlite.py");
const SCRAPER = path.join(ROOT, "scripts", "02_scraper_google_maps_playwright.js");
const SUPABASE_SYNC = path.join(ROOT, "scripts", "sincronizar_incremental_supabase.py");

function projectPath(value) {
  return path.isAbsolute(value) ? value : path.join(ROOT, value);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { config: DEFAULT_CONFIG };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--config" && args[i + 1]) {
      parsed.config = path.resolve(args[i + 1]);
      i += 1;
    }
  }
  return parsed;
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function makeLogger(logPath) {
  ensureDir(logPath);
  fs.writeFileSync(logPath, `\n=== Actualizacion incremental ${new Date().toISOString()} ===\n`, { flag: "a", encoding: "utf8" });
  return (message) => {
    const line = `${new Date().toISOString()} ${message}`;
    console.log(line);
    fs.writeFileSync(logPath, `${line}\n`, { flag: "a", encoding: "utf8" });
  };
}

function run(command, args, log) {
  log(`Ejecutando: ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, { cwd: ROOT, encoding: "utf8" });
  if (result.stdout) {
    for (const line of result.stdout.trim().split(/\r?\n/).filter(Boolean)) log(line);
  }
  if (result.stderr) {
    for (const line of result.stderr.trim().split(/\r?\n/).filter(Boolean)) log(`ERR: ${line}`);
  }
  if (result.status !== 0) {
    throw new Error(`Comando falló con código ${result.status}`);
  }
  return result.stdout || "";
}

function runSoft(command, args, log) {
  log(`Ejecutando: ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, { cwd: ROOT, encoding: "utf8" });
  if (result.stdout) {
    for (const line of result.stdout.trim().split(/\r?\n/).filter(Boolean)) log(line);
  }
  if (result.stderr) {
    for (const line of result.stderr.trim().split(/\r?\n/).filter(Boolean)) log(`ERR: ${line}`);
  }
  return { ok: result.status === 0, stdout: result.stdout || "", status: result.status };
}

function parseLastJson(stdout) {
  const text = stdout.trim();
  const start = text.lastIndexOf("{");
  if (start === -1) return {};
  try {
    return JSON.parse(text.slice(start));
  } catch {
    return {};
  }
}

function readDbCount(config, log) {
  const stdout = run(PYTHON, [
    "-c",
    `import sqlite3; conn=sqlite3.connect(r'''${projectPath(config.baseDatos)}'''); print(conn.execute('select count(*) from restaurantes').fetchone()[0]); conn.close()`
  ], log);
  const match = stdout.match(/(\d+)\s*$/);
  return match ? Number(match[1]) : 0;
}

function createRunConfig(config, comunaConfig, index) {
  const baseName = `incremental_${String(index + 1).padStart(2, "0")}_${comunaConfig.slug}`;
  const runConfig = {
    piloto: {
      comuna: comunaConfig.comuna,
      region: comunaConfig.region,
      pais: comunaConfig.pais,
      busqueda: comunaConfig.busqueda || "restaurantes",
      maxResultados: config.maxResultadosPorComuna,
      maxScrolls: config.maxScrollsPorComuna,
      pausaMinMs: config.pausaMinMs,
      pausaMaxMs: config.pausaMaxMs,
      headless: false,
      chromePath: config.chromePath,
      salidaCsv: `data/incremental/${baseName}.csv`,
      salidaExcel: `data/incremental/${baseName}.xlsx`,
      salidaRaw: `data/incremental/${baseName}_raw.json`,
      log: `data/logs/${baseName}.log`,
    },
  };
  const runPath = path.join(ROOT, "configs", "runs", `${baseName}.json`);
  ensureDir(runPath);
  fs.writeFileSync(runPath, JSON.stringify(runConfig, null, 2), "utf8");
  return { runPath, csvPath: projectPath(runConfig.piloto.salidaCsv) };
}

function printSummary(summary, config) {
  console.log("");
  console.log("RESUMEN FINAL");
  console.log("-------------");
  console.log(`total base antes: ${summary.totalAntes}`);
  console.log(`resultados encontrados en la corrida: ${summary.encontrados}`);
  console.log(`nuevos insertados: ${summary.insertados}`);
  console.log(`duplicados ignorados: ${summary.duplicados}`);
  console.log(`errores: ${summary.errores}`);
  console.log(`nuevos subidos a Supabase: ${summary.nuevosSupabase || 0}`);
  console.log(`duplicados Supabase ignorados: ${summary.duplicadosSupabase || 0}`);
  console.log(`errores Supabase: ${summary.erroresSupabase || 0}`);
  console.log(`total base final: ${summary.totalFinal}`);
  console.log(`archivo Excel generado: ${projectPath(config.excelSalida)}`);
  console.log("");
}

function syncSupabase(config, args, log, dryRun = false) {
  if (config.sincronizarSupabase === false) {
    log("Sincronizacion Supabase desactivada por configuracion.");
    return { nuevos_supabase: 0, duplicados_supabase: 0, errores_supabase: 0 };
  }
  const syncArgs = [SUPABASE_SYNC, "--config", args.config];
  if (dryRun) syncArgs.push("--dry-run");
  const result = runSoft(PYTHON, syncArgs, log);
  const summary = parseLastJson(result.stdout);
  if (!result.ok) {
    log(`Error sincronizando Supabase. Codigo: ${result.status}`);
    return { ...summary, errores_supabase: (summary.errores_supabase || 0) + 1 };
  }
  return summary;
}

function main() {
  const args = parseArgs();
  const config = JSON.parse(fs.readFileSync(args.config, "utf8"));
  const log = makeLogger(projectPath(config.log));
  const dbPath = projectPath(config.baseDatos);

  log("Inicio aplicación incremental");
  log(`Modo prueba: ${config.modoPrueba ? "SI" : "NO"}`);

  if (!fs.existsSync(dbPath)) {
    log("No existe SQLite. Importando base inicial desde Excel.");
    run(PYTHON, [IMPORTER, "--config", args.config, "--import-base"], log);
  } else {
    log("SQLite existente encontrado.");
  }

  let totalAntes = 0;
  let totalFinal = 0;
  let encontrados = 0;
  let insertados = 0;
  let duplicados = 0;
  let errores = 0;
  let nuevosSupabase = 0;
  let duplicadosSupabase = 0;
  let erroresSupabase = 0;

  if (config.modoPrueba) {
    log("Modo prueba activo: no se abrirá Google Maps ni se hará scraping.");
    const stdout = run(PYTHON, [IMPORTER, "--config", args.config, "--test-no-scraping"], log);
    const summary = parseLastJson(stdout);
    totalAntes = summary.total_antes || 0;
    totalFinal = summary.total_final || totalAntes;
    encontrados = summary.encontrados || 0;
    insertados = 0;
    duplicados = summary.duplicados || 0;
    errores = summary.errores || 0;
    run(PYTHON, [IMPORTER, "--config", args.config, "--export"], log);
    const supabaseSummary = syncSupabase(config, args, log, true);
    nuevosSupabase += supabaseSummary.nuevos_supabase || 0;
    duplicadosSupabase += supabaseSummary.duplicados_supabase || 0;
    erroresSupabase += supabaseSummary.errores_supabase || 0;
  } else {
    totalAntes = readDbCount(config, log);
    for (let i = 0; i < config.comunas.length; i += 1) {
      if (insertados >= Number(config.maxNuevosObjetivo || 100)) {
        log("Objetivo de nuevos registros alcanzado. Se detiene la corrida.");
        break;
      }
      const item = config.comunas[i];
      const { runPath, csvPath } = createRunConfig(config, item, i);
      log(`Scraping controlado para comuna: ${item.comuna}`);
      run(NODE, [SCRAPER, "--config", runPath], log);
      if (!fs.existsSync(csvPath)) {
        errores += 1;
        log(`No se encontró CSV de resultados: ${csvPath}`);
        continue;
      }
      const stdout = run(PYTHON, [IMPORTER, "--config", args.config, "--merge-file", csvPath], log);
      const summary = parseLastJson(stdout);
      totalFinal = summary.total_final || totalFinal;
      encontrados += summary.encontrados || 0;
      insertados += summary.insertados || 0;
      duplicados += summary.duplicados || 0;
      errores += summary.errores || 0;
    }
    run(PYTHON, [IMPORTER, "--config", args.config, "--export"], log);
    totalFinal = readDbCount(config, log);
    const supabaseSummary = syncSupabase(config, args, log, false);
    nuevosSupabase += supabaseSummary.nuevos_supabase || 0;
    duplicadosSupabase += supabaseSummary.duplicados_supabase || 0;
    erroresSupabase += supabaseSummary.errores_supabase || 0;
  }

  const finalSummary = { totalAntes, encontrados, insertados, duplicados, errores, totalFinal, nuevosSupabase, duplicadosSupabase, erroresSupabase };
  log(`Resumen final: ${JSON.stringify(finalSummary)}`);
  printSummary(finalSummary, config);
  log("Fin aplicación incremental");
}

try {
  main();
} catch (error) {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
}
