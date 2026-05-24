from __future__ import annotations

import html
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from supabase_client import get_supabase_service_client


ROOT = Path(__file__).resolve().parent
PROGRESS_PATH = ROOT / "data" / "scraping_progress.json"
PROCESS_PATH = ROOT / "data" / "scraping_process.json"
STOP_FLAG = ROOT / "data" / "stop_scraping.flag"
CONFIG_PATH = ROOT / "configs" / "actualizacion_incremental_manual.json"
DEFAULT_LOG = ROOT / "data" / "logs" / "actualizacion_incremental_manual.log"
START_BAT = ROOT / "actualizar_restaurantes.bat"
PYTHON = Path(r"C:\Users\gabyp\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SYNC_SCRIPT = ROOT / "scripts" / "sincronizar_incremental_supabase.py"
REFRESH_MS = 3000
TERMINAL_STATUSES = {"idle", "finished", "stopped", "error"}


st.set_page_config(page_title="Control Scraping", page_icon="search", layout="wide")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_stop_flag() -> None:
    STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    STOP_FLAG.write_text(utc_now(), encoding="utf-8")


def process_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            capture_output=True,
            timeout=4,
        )
    except Exception:
        return False
    return str(pid) in result.stdout


def start_scraping() -> tuple[bool, str]:
    process_info = load_json(PROCESS_PATH, {})
    progress = load_json(PROGRESS_PATH, {"status": "idle"})
    status = progress.get("status", "idle")
    pid = process_info.get("pid")
    if process_is_alive(pid) and status not in TERMINAL_STATUSES:
        return False, f"Ya hay una corrida activa con PID {pid}."
    if not START_BAT.exists():
        return False, f"No existe {START_BAT.name}."

    if STOP_FLAG.exists():
        STOP_FLAG.unlink()

    process = subprocess.Popen(
        ["cmd.exe", "/c", str(START_BAT)],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    write_json(
        PROCESS_PATH,
        {
            "pid": process.pid,
            "started_at": utc_now(),
            "command": str(START_BAT),
            "status": "started",
        },
    )
    return True, f"Scraping iniciado. PID {process.pid}."


def fmt_seconds(value: int | float | None) -> str:
    if value is None:
        return "-"
    seconds = max(int(value), 0)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def human_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d %b %H:%M")


def local_count() -> int | None:
    db_path = ROOT / "data" / "restaurantes.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("select count(*) from restaurantes").fetchone()[0])
    finally:
        conn.close()


def supabase_count(table: str) -> int | None:
    try:
        client = get_supabase_service_client()
        result = client.table(table).select("id", count="exact").limit(1).execute()
        return result.count
    except Exception:
        return None


def read_logs(progress: dict, limit: int = 50) -> list[str]:
    log_path = Path(progress.get("logs_path") or DEFAULT_LOG)
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def run_supabase_retry() -> tuple[bool, str]:
    result = subprocess.run(
        [str(PYTHON), str(SYNC_SCRIPT), "--config", str(CONFIG_PATH)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=300,
    )
    output = "\n".join(part for part in [result.stdout, result.stderr] if part)
    return result.returncode == 0, output


def health(status: str, errors: int, errors_supabase: int) -> tuple[str, str]:
    if status == "error" or errors or errors_supabase:
        return "Error", "health-red"
    if status in {"stopping", "stopped"} or STOP_FLAG.exists():
        return "Warning", "health-yellow"
    if status == "running":
        return "Funcionando", "health-green"
    return "Idle", "health-slate"


def kpi(label: str, value: str | int | None, detail: str = "") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{html.escape(label)}</div>
          <div class="kpi-value">{html.escape(str(value if value not in (None, "") else "-"))}</div>
          <div class="kpi-detail">{html.escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def button_row(disable_start: bool, status: str) -> None:
    start_col, stop_col, sync_col = st.columns(3)
    with start_col:
        if st.button("Iniciar scraping", use_container_width=True, disabled=disable_start):
            ok, message = start_scraping()
            if ok:
                st.success(message)
            else:
                st.warning(message)
    with stop_col:
        if st.button("Detener scraping", use_container_width=True, disabled=status not in {"running", "stopping"}):
            save_stop_flag()
            st.warning("Detencion solicitada. El scraper se detendra en el siguiente punto seguro.")
    with sync_col:
        if st.button("Reintentar sync Supabase", use_container_width=True, disabled=status == "running"):
            with st.spinner("Sincronizando faltantes sin volver a scrapear..."):
                ok, output = run_supabase_retry()
            st.session_state["last_sync_output"] = output[-5000:] if output else "Sin salida."
            if ok:
                st.success("Sincronizacion ejecutada.")
            else:
                st.error("La sincronizacion fallo. Revisa el detalle en la seccion secundaria.")


st.markdown(
    """
    <style>
      .stApp { background: #f6f8fb; color: #0f172a; }
      .block-container { padding-top: 1.2rem; max-width: 1320px; }
      .hero, .card, .kpi-card {
        background: rgba(255,255,255,.96);
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        box-shadow: 0 10px 28px rgba(15,23,42,.05);
      }
      .hero { padding: 18px 20px; margin-bottom: 14px; }
      .hero-title { font-size: 23px; font-weight: 760; letter-spacing: 0; }
      .hero-subtitle { color: #64748b; margin-top: 3px; font-size: 14px; }
      .card { padding: 18px; margin-bottom: 14px; }
      .kpi-card { padding: 13px 15px; min-height: 88px; }
      .kpi-label { color:#64748b; font-size:12px; font-weight:650; }
      .kpi-value { color:#0f172a; font-size:25px; font-weight:780; margin-top:7px; }
      .kpi-detail { color:#94a3b8; font-size:12px; margin-top:2px; }
      .status-pill { display:inline-flex; align-items:center; gap:8px; font-weight:720; }
      .status-pill:before { content:""; width:10px; height:10px; border-radius:99px; display:inline-block; }
      .health-green:before { background:#10b981; box-shadow:0 0 0 4px #d1fae5; }
      .health-yellow:before { background:#f59e0b; box-shadow:0 0 0 4px #fef3c7; }
      .health-red:before { background:#ef4444; box-shadow:0 0 0 4px #fee2e2; }
      .health-slate:before { background:#64748b; box-shadow:0 0 0 4px #e2e8f0; }
      .progress-shell { height: 16px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin: 16px 0 10px; }
      .progress-bar { height:100%; background:linear-gradient(90deg,#0f766e,#2563eb); border-radius:999px; transition:width .3s ease; }
      .small-grid { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
      .small-item { border:1px solid #e2e8f0; border-radius:16px; padding:11px 12px; background:#f8fafc; }
      .small-label { color:#64748b; font-size:12px; font-weight:650; }
      .small-value { color:#0f172a; font-size:14px; font-weight:720; margin-top:3px; }
      .terminal {
        background:#0f172a; color:#dbeafe; border-radius:16px; padding:15px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size:12px; line-height:1.55; max-height:360px; overflow:auto;
      }
      .terminal-line { white-space: pre-wrap; border-bottom: 1px solid rgba(148,163,184,.12); padding: 3px 0; }
      .muted { color:#64748b; }
      .final-card { border-left: 4px solid #10b981; }
      div[data-testid="stExpander"] {
        background: rgba(255,255,255,.96);
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(15,23,42,.04);
      }
      @media (max-width: 900px) {
        .small-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
    </style>
    """,
    unsafe_allow_html=True,
)
components.html(
    f"<script>setTimeout(function() {{ window.parent.location.reload(); }}, {REFRESH_MS});</script>",
    height=0,
)

progress = load_json(PROGRESS_PATH, {"status": "idle", "mensaje_actual": "Idle", "porcentaje_estimado": 0})
config = load_json(CONFIG_PATH, {})
process_info = load_json(PROCESS_PATH, {})
status = progress.get("status", "idle")
process_alive = process_is_alive(process_info.get("pid"))
is_running = status in {"running", "stopping"} or (process_alive and status not in TERMINAL_STATUSES)
health_label, health_class = health(status, int(progress.get("errores") or 0), int(progress.get("errores_supabase") or 0))
sync = progress.get("sincronizacion_supabase") or {}
resumen = progress.get("resumen_final") or {}
local_total = local_count()
remote_total = supabase_count("restaurantes")
pct = max(0, min(float(progress.get("porcentaje_estimado") or 0), 100))

st.markdown(
    f"""
    <div class="hero">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;">
        <div>
          <div class="hero-title">Centro de control scraping</div>
          <div class="hero-subtitle">Inicia, monitorea, detiene y sincroniza restaurantes sin abrir una consola aparte.</div>
        </div>
        <div class="status-pill {health_class}">{html.escape(health_label)} · {html.escape(status)}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

button_row(disable_start=is_running, status=status)

if STOP_FLAG.exists() and status in {"running", "stopping"}:
    st.warning("Detencion solicitada. Esperando que el scraper llegue al siguiente punto seguro.")

st.markdown(
    f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
        <div>
          <div style="font-weight:760;font-size:19px;">{html.escape(str(progress.get("etapa_actual") or "Idle"))}</div>
          <div class="muted">{html.escape(str(progress.get("mensaje_actual") or "Sin actividad reciente."))}</div>
        </div>
        <div style="font-weight:820;font-size:26px;">{pct:.0f}%</div>
      </div>
      <div class="progress-shell"><div class="progress-bar" style="width:{pct:.0f}%"></div></div>
      <div class="small-grid">
        <div class="small-item"><div class="small-label">Comuna</div><div class="small-value">{html.escape(str(progress.get("comuna_actual") or "Sin comuna activa"))}</div></div>
        <div class="small-item"><div class="small-label">Avance comunas</div><div class="small-value">{html.escape(str(progress.get("comuna_index", 0)))} de {html.escape(str(progress.get("total_comunas", 0)))}</div></div>
        <div class="small-item"><div class="small-label">Ultimo restaurante</div><div class="small-value">{html.escape(str(progress.get("ultimo_restaurante") or "-"))}</div></div>
        <div class="small-item"><div class="small-label">Tiempo</div><div class="small-value">{fmt_seconds(progress.get("tiempo_transcurrido_segundos"))} / {fmt_seconds(progress.get("tiempo_estimado_restante_segundos"))}</div></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

kpi_cols = st.columns(5)
with kpi_cols[0]:
    kpi("Revisados", progress.get("restaurantes_revisados", 0), "restaurantes")
with kpi_cols[1]:
    kpi("Nuevos", progress.get("restaurantes_nuevos", 0), "detectados")
with kpi_cols[2]:
    kpi("Duplicados", progress.get("duplicados_ignorados", 0), "ignorados")
with kpi_cols[3]:
    kpi("Supabase", progress.get("subidos_supabase", 0), "subidos")
with kpi_cols[4]:
    total_errors = int(progress.get("errores") or 0) + int(progress.get("errores_supabase") or 0)
    kpi("Errores", total_errors, "local + Supabase")

if status in {"idle", "finished", "stopped", "error"} and resumen:
    st.markdown('<div class="card final-card">', unsafe_allow_html=True)
    st.subheader("Ultima ejecucion")
    final_cols = st.columns(5)
    with final_cols[0]:
        kpi("Duracion", fmt_seconds(resumen.get("duracion_total_segundos")), human_time(progress.get("finished_at")))
    with final_cols[1]:
        kpi("Nuevos", resumen.get("nuevos_encontrados", 0), "")
    with final_cols[2]:
        kpi("Duplicados", resumen.get("duplicados", 0), "")
    with final_cols[3]:
        kpi("Supabase", resumen.get("insertados_supabase", 0), "insertados")
    with final_cols[4]:
        kpi("Errores", int(resumen.get("errores", 0)) + int(resumen.get("errores_supabase", 0)), resumen.get("ultima_comuna_procesada", ""))
    st.markdown("</div>", unsafe_allow_html=True)
elif status == "idle":
    st.info("Idle. No hay scraping corriendo. Puedes iniciar una nueva corrida desde el boton superior.")

with st.expander("Configuracion scraping", expanded=False):
    cfg_cols = st.columns(3)
    with cfg_cols[0]:
        st.write(f"**Modo prueba:** {config.get('modoPrueba', False)}")
        st.write(f"**Objetivo nuevos:** {config.get('maxNuevosObjetivo', '-')}")
    with cfg_cols[1]:
        st.write(f"**Max resultados/comuna:** {config.get('maxResultadosPorComuna', '-')}")
        st.write(f"**Scrolls maximos:** {config.get('maxScrollsPorComuna', '-')}")
    with cfg_cols[2]:
        st.write(f"**Sincronizar Supabase:** {config.get('sincronizarSupabase', '-')}")
        st.write(f"**Archivo config:** `{CONFIG_PATH.name}`")
    st.caption("Comunas configuradas")
    st.write(", ".join(item.get("comuna", "") for item in config.get("comunas", [])) or "-")

with st.expander("SQLite, Supabase y sincronizacion", expanded=False):
    db_cols = st.columns(4)
    diff = None if local_total is None or remote_total is None else remote_total - local_total
    with db_cols[0]:
        kpi("SQLite local", local_total, "restaurantes")
    with db_cols[1]:
        kpi("Supabase", remote_total, "restaurantes")
    with db_cols[2]:
        kpi("Diferencia", diff, "Supabase - local")
    with db_cols[3]:
        kpi("Credencial", sync.get("credencial_usada") or "-", "sin exponer secrets")
    st.write(f"**Ultima sync exitosa:** {human_time(sync.get('ultima_exitosa'))}")
    st.write(f"**Insertados ultima corrida:** {sync.get('registros_insertados', 0)}")
    st.write(f"**Duplicados ignorados:** {sync.get('duplicados_ignorados', 0)}")
    st.write(f"**Errores Supabase:** {sync.get('errores_supabase', 0)}")
    if st.session_state.get("last_sync_output"):
        st.caption("Ultima salida de reintento sync")
        st.code(st.session_state["last_sync_output"], language="json")

with st.expander("Variables tecnicas", expanded=False):
    st.json(
        {
            "status": status,
            "pid_guardado": process_info.get("pid"),
            "proceso_activo": process_alive,
            "stop_flag": STOP_FLAG.exists(),
            "progress_path": str(PROGRESS_PATH),
            "process_path": str(PROCESS_PATH),
            "logs_path": progress.get("logs_path") or str(DEFAULT_LOG),
        }
    )

with st.expander("Logs completos", expanded=False):
    lines = read_logs(progress, 50)
    if lines:
        rendered_lines = "".join(f'<div class="terminal-line">{html.escape(line)}</div>' for line in lines)
        st.markdown('<div class="terminal">' + rendered_lines + "</div>", unsafe_allow_html=True)
    else:
        st.info("Aun no hay logs recientes.")
