const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const NODE = "C:\\Users\\gabyp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\bin\\node.exe";
const SCRAPER = path.join(ROOT, "scripts", "02_scraper_google_maps_playwright.js");
const CONSOLIDAR = path.join(ROOT, "scripts", "05_consolidar_resultados.py");
const PYTHON = "C:\\Users\\gabyp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const DEFAULT_CONFIG = path.join(ROOT, "configs", "scraper_google_maps_multi_comuna.json");

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { config: DEFAULT_CONFIG, check: false, soloConsolidar: false };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--config" && args[i + 1]) {
      parsed.config = path.resolve(args[i + 1]);
      i += 1;
    } else if (args[i] === "--check") {
      parsed.check = true;
    } else if (args[i] === "--solo-consolidar") {
      parsed.soloConsolidar = true;
    }
  }
  return parsed;
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function slugConfigPath(slug) {
  return path.join(ROOT, "configs", "runs", `scraper_${slug}.json`);
}

function buildRunConfig(baseConfig, item) {
  const baseName = `${item.slug}_restaurantes_30`;
  return {
    piloto: {
      comuna: item.comuna,
      region: item.region,
      pais: item.pais,
      busqueda: baseConfig.busqueda,
      maxResultados: baseConfig.maxResultados,
      maxScrolls: baseConfig.maxScrolls,
      pausaMinMs: baseConfig.pausaMinMs,
      pausaMaxMs: baseConfig.pausaMaxMs,
      headless: baseConfig.headless,
      chromePath: baseConfig.chromePath,
      salidaCsv: `data/comunas/${baseName}.csv`,
      salidaExcel: `data/comunas/${baseName}.xlsx`,
      salidaRaw: `data/comunas/${baseName}_raw.json`,
      log: `data/logs/${baseName}.log`,
    },
  };
}

function writeRunConfigs(baseConfig) {
  const paths = [];
  for (const item of baseConfig.comunas) {
    const configPath = slugConfigPath(item.slug);
    ensureDir(configPath);
    fs.writeFileSync(configPath, JSON.stringify(buildRunConfig(baseConfig, item), null, 2), "utf8");
    paths.push(configPath);
  }
  return paths;
}

function runCommand(command, args) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    stdio: "inherit",
    encoding: "utf8",
  });
  return result.status || 0;
}

function consolidate(configPath) {
  return runCommand(PYTHON, [CONSOLIDAR, configPath]);
}

function main() {
  const args = parseArgs();
  const config = JSON.parse(fs.readFileSync(args.config, "utf8"));
  const runConfigs = writeRunConfigs(config);

  console.log(`Configuraciones por comuna creadas: ${runConfigs.length}`);
  for (const configPath of runConfigs) console.log(`- ${path.relative(ROOT, configPath)}`);

  if (args.check) {
    console.log("Check listo. No se ejecutó scraping.");
    return 0;
  }

  if (!args.soloConsolidar) {
    for (const configPath of runConfigs) {
      console.log(`\n=== Ejecutando comuna: ${path.basename(configPath)} ===`);
      const status = runCommand(NODE, [SCRAPER, "--config", configPath]);
      if (status !== 0) {
        console.error(`Proceso detenido. Falló: ${configPath}`);
        return status;
      }
    }
  }

  console.log("\n=== Consolidando resultados ===");
  return consolidate(args.config);
}

process.exitCode = main();
