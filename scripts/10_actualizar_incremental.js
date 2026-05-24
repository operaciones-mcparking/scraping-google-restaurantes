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
const PROGRESS_PATH = path.join(ROOT, "data", "scraping_progress.json");
const STOP_FLAG = path.join(ROOT, "data", "stop_scraping.flag");

class StopRequested extends Error {
  constructor(message = "Detencion solicitada por el usuario.") {
    super(message);
    this.name = "StopRequested";
  }
}

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

function readProgress() {
  try {
    return JSON.parse(fs.readFileSync(PROGRESS_PATH, "utf8"));
  } catch {
    return {};
  }
}

function elapsedSeconds(startedAt) {
  const started = startedAt ? Date.parse(startedAt) : Date.now();
  return Math.max(Math.round((Date.now() - started) / 1000), 0);
}

function updateProgress(patch) {
  ensureDir(PROGRESS_PATH);
  const previous = readProgress();
  const startedAt = patch.started_at || previous.started_at || new Date().toISOString();
  const porcentaje = Number(patch.porcentaje_estimado ?? previous.porcentaje_estimado ?? 0);
  const elapsed = elapsedSeconds(startedAt);
  const estimatedTotal = porcentaje > 0 ? Math.round(elapsed / Math.max(porcentaje / 100, 0.01)) : 0;
  const remaining = estimatedTotal ? Math.max(estimatedTotal - elapsed, 0) : null;
  const next = {
    status: "idle",
    started_at: null,
    updated_at: new Date().toISOString(),
    finished_at: null,
    porcentaje_estimado: 0,
    tiempo_transcurrido_segundos: 0,
    tiempo_estimado_restante_segundos: null,
    mensaje_actual: "Idle",
    etapa_actual: "Idle",
    comuna_actual: "",
    comuna_index: 0,
    total_comunas: 0,
    ultimo_restaurante: "",
    restaurantes_revisados: 0,
    restaurantes_nuevos: 0,
    duplicados_ignorados: 0,
    subidos_supabase: 0,
    errores: 0,
    errores_supabase: 0,
    sincronizacion_supabase: {
      ultima_exitosa: null,
      registros_insertados: 0,
      duplicados_ignorados: 0,
      errores_supabase: 0,
      credencial_usada: "",
    },
    config: {},
    resumen_final: null,
    ...previous,
    ...patch,
    started_at: startedAt,
    updated_at: new Date().toISOString(),
    tiempo_transcurrido_segundos: elapsed,
    tiempo_estimado_restante_segundos: patch.tiempo_estimado_restante_segundos ?? remaining,
    porcentaje_estimado: Math.max(0, Math.min(100, porcentaje)),
  };
  fs.writeFileSync(PROGRESS_PATH, JSON.stringify(next, null, 2), "utf8");
  return next;
}

function checkStop() {
  if (fs.existsSync(STOP_FLAG)) {
    updateProgress({
      status: "stopping",
      mensaje_actual: "Scraping detenido por el usuario",
      etapa_actual: "Deteniendo",
    });
    throw new StopRequested("Scraping detenido por el usuario");
  }
}

function lockPathFor(config) {
  return `${projectPath(config.log)}.lock`;
}

function acquireLock(config) {
  const lockPath = lockPathFor(config);
  ensureDir(lockPath);
  if (fs.existsSync(lockPath)) {
    try {
      const payload = JSON.parse(fs.readFileSync(lockPath, "utf8"));
      const startedAt = payload.startedAt ? Date.parse(payload.startedAt) : 0;
      const ageMs = startedAt ? Date.now() - startedAt : 0;
      if (ageMs > 0 && ageMs < 6 * 60 * 60 * 1000) {
        throw new Error(
          `Ya hay una actualizacion en curso desde ${payload.startedAt}. ` +
          "Espera a que termine o cierra la ventana anterior antes de ejecutar otra."
        );
      }
    } catch (error) {
      if (String(error.message || error).includes("Ya hay una actualizacion")) throw error;
    }
  }
  fs.writeFileSync(lockPath, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }, null, 2), "utf8");
  return lockPath;
}

function releaseLock(lockPath) {
  if (lockPath && fs.existsSync(lockPath)) {
    fs.unlinkSync(lockPath);
  }
}

let activeLockPath = "";
process.on("exit", () => releaseLock(activeLockPath));

function makeLogger(logPath) {
  ensureDir(logPath);
  fs.writeFileSync(logPath, `\n=== Actualizacion incremental ${new Date().toISOString()} ===\n`, { flag: "a", encoding: "utf8" });
  return (message) => {
    const line = `${new Date().toISOString()} ${message}`;
    console.log(line);
    fs.writeFileSync(logPath, `${line}\n`, { flag: "a", encoding: "utf8" });
    const progress = readProgress();
    if (progress.status && progress.status !== "idle") {
      updateProgress({ logs_path: logPath, mensaje_actual: message });
    }
  };
}

function run(command, args, log) {
  checkStop();
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
  checkStop();
  return result.stdout || "";
}

function runSoft(command, args, log) {
  checkStop();
  log(`Ejecutando: ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, { cwd: ROOT, encoding: "utf8" });
  if (result.stdout) {
    for (const line of result.stdout.trim().split(/\r?\n/).filter(Boolean)) log(line);
  }
  if (result.stderr) {
    for (const line of result.stderr.trim().split(/\r?\n/).filter(Boolean)) log(`ERR: ${line}`);
  }
  checkStop();
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
  checkStop();
  updateProgress({
    etapa_actual: dryRun ? "Simulando sincronizacion Supabase..." : "Sincronizando Supabase...",
    mensaje_actual: dryRun ? "Calculando diferencias con Supabase." : "Subiendo faltantes a Supabase.",
    porcentaje_estimado: 94,
  });
  const syncArgs = [SUPABASE_SYNC, "--config", args.config];
  if (dryRun) syncArgs.push("--dry-run");
  const result = runSoft(PYTHON, syncArgs, log);
  const summary = parseLastJson(result.stdout);
  if (!result.ok) {
    log(`Error sincronizando Supabase. Codigo: ${result.status}`);
    updateProgress({
      status: "error",
      errores_supabase: (summary.errores_supabase || 0) + 1,
      mensaje_actual: summary.error || summary.motivo_abortado || `Error sincronizando Supabase. Codigo: ${result.status}`,
      etapa_actual: "Error Supabase",
    });
    return { ...summary, errores_supabase: (summary.errores_supabase || 0) + 1 };
  }
  updateProgress({
    subidos_supabase: summary.insertados_supabase ?? summary.nuevos_supabase ?? 0,
    errores_supabase: summary.errores_supabase || 0,
    sincronizacion_supabase: {
      ultima_exitosa: (summary.errores_supabase || 0) === 0 ? new Date().toISOString() : null,
      registros_insertados: summary.insertados_supabase ?? summary.nuevos_supabase ?? 0,
      duplicados_ignorados: summary.duplicados_supabase || 0,
      errores_supabase: summary.errores_supabase || 0,
      credencial_usada: summary.credencial || "",
    },
  });
  return summary;
}

function main() {
  const args = parseArgs();
  const config = JSON.parse(fs.readFileSync(args.config, "utf8"));
  activeLockPath = acquireLock(config);
  if (fs.existsSync(STOP_FLAG)) fs.unlinkSync(STOP_FLAG);
  const log = makeLogger(projectPath(config.log));
  const dbPath = projectPath(config.baseDatos);
  const startedAt = new Date().toISOString();

  updateProgress({
    status: "running",
    started_at: startedAt,
    finished_at: null,
    porcentaje_estimado: 2,
    mensaje_actual: "Iniciando actualizacion incremental.",
    etapa_actual: "Iniciando",
    total_comunas: config.comunas.length,
    archivo_config_usado: args.config,
    config: {
      modo_prueba: Boolean(config.modoPrueba),
      objetivo_nuevos: Number(config.maxNuevosObjetivo || 0),
      maximo_resultados_por_comuna: Number(config.maxResultadosPorComuna || 0),
      scrolls_maximos: Number(config.maxScrollsPorComuna || 0),
      comunas_configuradas: (config.comunas || []).map((item) => item.comuna),
      archivo_config_usado: args.config,
      sincronizar_supabase: config.sincronizarSupabase !== false,
      dry_run_supabase: Boolean(config.modoPrueba),
    },
  });

  log("Inicio aplicación incremental");
  log(`Modo prueba: ${config.modoPrueba ? "SI" : "NO"}`);

  if (!fs.existsSync(dbPath)) {
    checkStop();
    updateProgress({ etapa_actual: "Importando base inicial", mensaje_actual: "No existe SQLite. Importando base inicial." });
    log("No existe SQLite. Importando base inicial desde Excel.");
    run(PYTHON, [IMPORTER, "--config", args.config, "--import-base"], log);
    checkStop();
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
    checkStop();
    updateProgress({ etapa_actual: "Modo prueba", mensaje_actual: "Modo prueba activo.", porcentaje_estimado: 15 });
    log("Modo prueba activo: no se abrirá Google Maps ni se hará scraping.");
    const stdout = run(PYTHON, [IMPORTER, "--config", args.config, "--test-no-scraping"], log);
    checkStop();
    const summary = parseLastJson(stdout);
    totalAntes = summary.total_antes || 0;
    totalFinal = summary.total_final || totalAntes;
    encontrados = summary.encontrados || 0;
    insertados = 0;
    duplicados = summary.duplicados || 0;
    errores = summary.errores || 0;
    checkStop();
    run(PYTHON, [IMPORTER, "--config", args.config, "--export"], log);
    checkStop();
    const supabaseSummary = syncSupabase(config, args, log, true);
    nuevosSupabase += supabaseSummary.insertados_supabase ?? supabaseSummary.nuevos_supabase ?? 0;
    duplicadosSupabase += supabaseSummary.duplicados_supabase || 0;
    erroresSupabase += supabaseSummary.errores_supabase || 0;
  } else {
    totalAntes = readDbCount(config, log);
    for (let i = 0; i < config.comunas.length; i += 1) {
      checkStop();
      if (insertados >= Number(config.maxNuevosObjetivo || 100)) {
        log("Objetivo de nuevos registros alcanzado. Se detiene la corrida.");
        break;
      }
      const item = config.comunas[i];
      const { runPath, csvPath } = createRunConfig(config, item, i);
      updateProgress({
        etapa_actual: "Procesando comuna...",
        mensaje_actual: `Scraping controlado para comuna: ${item.comuna}`,
        comuna_actual: item.comuna,
        comuna_index: i + 1,
        total_comunas: config.comunas.length,
        porcentaje_estimado: Math.round((i / Math.max(config.comunas.length, 1)) * 82) + 5,
        restaurantes_revisados: encontrados,
        restaurantes_nuevos: insertados,
        duplicados_ignorados: duplicados,
        errores,
      });
      log(`Scraping controlado para comuna: ${item.comuna}`);
      run(NODE, [SCRAPER, "--config", runPath], log);
      checkStop();
      if (!fs.existsSync(csvPath)) {
        errores += 1;
        log(`No se encontró CSV de resultados: ${csvPath}`);
        continue;
      }
      checkStop();
      updateProgress({ etapa_actual: "Guardando SQLite...", mensaje_actual: `Guardando resultados de ${item.comuna} en SQLite.` });
      const stdout = run(PYTHON, [IMPORTER, "--config", args.config, "--merge-file", csvPath], log);
      checkStop();
      const summary = parseLastJson(stdout);
      totalFinal = summary.total_final || totalFinal;
      encontrados += summary.encontrados || 0;
      insertados += summary.insertados || 0;
      duplicados += summary.duplicados || 0;
      errores += summary.errores || 0;
      updateProgress({
        restaurantes_revisados: encontrados,
        restaurantes_nuevos: insertados,
        duplicados_ignorados: duplicados,
        errores,
        porcentaje_estimado: Math.round(((i + 1) / Math.max(config.comunas.length, 1)) * 82) + 8,
      });
    }
    checkStop();
    updateProgress({ etapa_actual: "Guardando Excel...", mensaje_actual: "Exportando base local a Excel/CSV.", porcentaje_estimado: 90 });
    run(PYTHON, [IMPORTER, "--config", args.config, "--export"], log);
    checkStop();
    totalFinal = readDbCount(config, log);
    checkStop();
    const supabaseSummary = syncSupabase(config, args, log, false);
    checkStop();
    nuevosSupabase += supabaseSummary.insertados_supabase ?? supabaseSummary.nuevos_supabase ?? 0;
    duplicadosSupabase += supabaseSummary.duplicados_supabase || 0;
    erroresSupabase += supabaseSummary.errores_supabase || 0;
  }

  const finalSummary = { totalAntes, encontrados, insertados, duplicados, errores, totalFinal, nuevosSupabase, duplicadosSupabase, erroresSupabase };
  updateProgress({
    status: errores || erroresSupabase ? "error" : "finished",
    finished_at: new Date().toISOString(),
    porcentaje_estimado: 100,
    etapa_actual: errores || erroresSupabase ? "Finalizado con errores" : "Finalizado",
    mensaje_actual: errores || erroresSupabase ? "La corrida termino con errores." : "Actualizacion finalizada correctamente.",
    restaurantes_revisados: encontrados,
    restaurantes_nuevos: insertados,
    duplicados_ignorados: duplicados,
    subidos_supabase: nuevosSupabase,
    errores,
    errores_supabase: erroresSupabase,
    total_restaurantes_locales: totalFinal,
    resumen_final: {
      duracion_total_segundos: elapsedSeconds(startedAt),
      nuevos_encontrados: insertados,
      duplicados,
      insertados_supabase: nuevosSupabase,
      errores,
      errores_supabase: erroresSupabase,
      ultima_comuna_procesada: config.comunas[Math.min(config.comunas.length - 1, Math.max(0, (readProgress().comuna_index || 1) - 1))]?.comuna || "",
    },
  });
  log(`Resumen final: ${JSON.stringify(finalSummary)}`);
  printSummary(finalSummary, config);
  releaseLock(activeLockPath);
  activeLockPath = "";
  log("Fin aplicación incremental");
}

try {
  main();
} catch (error) {
  if (error instanceof StopRequested) {
    updateProgress({
      status: "stopped",
      finished_at: new Date().toISOString(),
      etapa_actual: "Detenido",
      mensaje_actual: "Scraping detenido por el usuario",
    });
    releaseLock(activeLockPath);
    activeLockPath = "";
    console.log(error.message);
    process.exitCode = 0;
  } else {
    updateProgress({
      status: "error",
      finished_at: new Date().toISOString(),
      etapa_actual: "Error",
      mensaje_actual: error.message || String(error),
      errores: (readProgress().errores || 0) + 1,
    });
    console.error(error.stack || error.message || String(error));
    process.exitCode = 1;
  }
}
