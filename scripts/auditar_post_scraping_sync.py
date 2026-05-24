from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sincronizar_incremental_supabase import clean_text, load_config, project_path, restaurant_record, sqlite_rows
from supabase_client import get_supabase_service_client


DEFAULT_CONFIG = ROOT / "configs" / "actualizacion_incremental_manual.json"
PROGRESS_PATH = ROOT / "data" / "scraping_progress.json"
DEFAULT_EXCEL = ROOT / "data" / "base_restaurantes_actualizada.xlsx"
INITIAL_ACTION = "Restaurante agregado"


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip() == ""


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def sqlite_summary(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    db_path = project_path(config["baseDatos"])
    rows = sqlite_rows(db_path)
    records = [restaurant_record(row) for row in rows]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    latest = [
        dict(row)
        for row in conn.execute(
            "select id, nombre_restaurante, comuna, fecha_insertado, fecha_actualizado from restaurantes order by id desc limit 20"
        )
    ]
    conn.close()
    return records, latest


def excel_count(path: Path = DEFAULT_EXCEL) -> int | None:
    if not path.exists():
        return None
    try:
        return int(len(pd.read_excel(path, sheet_name="Base restaurantes")))
    except Exception:
        return None


def fetch_all(client, table: str, select: str = "*", order: str | None = None, desc: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    chunk = 1000
    while True:
        query = client.table(table).select(select)
        if order:
            query = query.order(order, desc=desc)
        response = query.range(start, start + chunk - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < chunk:
            break
        start += chunk
    return rows


def latest_supabase(client) -> list[dict[str, Any]]:
    return (
        client.table("restaurantes")
        .select("crm_id,nombre_restaurante,comuna,created_at,fecha_carga,nivel_comercial,tipo_negocio,estado_revision_rappi")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar pipeline post scraping local -> Supabase -> CRM.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()

    config = load_config(Path(args.config))
    local_records, latest_local = sqlite_summary(config)
    local_by_id = {clean_text(row.get("crm_id")): row for row in local_records if clean_text(row.get("crm_id"))}

    client = get_supabase_service_client()
    restaurants = fetch_all(client, "restaurantes")
    states = fetch_all(client, "crm_estado")
    history = fetch_all(client, "historial_contactos")

    restaurant_by_id = {clean_text(row.get("crm_id")): row for row in restaurants if clean_text(row.get("crm_id"))}
    state_by_id = {clean_text(row.get("crm_id")): row for row in states if clean_text(row.get("crm_id"))}
    initial_events = [event for event in history if clean_text(event.get("accion")) == INITIAL_ACTION]
    initial_by_crm = Counter(clean_text(event.get("crm_id")) for event in initial_events if clean_text(event.get("crm_id")))

    local_missing_supabase = [row for crm_id, row in local_by_id.items() if crm_id not in restaurant_by_id]
    supabase_missing_local = [row for crm_id, row in restaurant_by_id.items() if crm_id not in local_by_id]
    restaurants_without_state = [row for crm_id, row in restaurant_by_id.items() if crm_id not in state_by_id]
    states_without_restaurant = [row for crm_id, row in state_by_id.items() if crm_id not in restaurant_by_id]
    restaurants_without_initial = [row for crm_id, row in restaurant_by_id.items() if initial_by_crm.get(crm_id, 0) == 0]

    progress = read_json(PROGRESS_PATH, {})
    report = {
        "totales": {
            "sqlite_local": len(local_records),
            "excel_local": excel_count(),
            "supabase_restaurantes": len(restaurants),
            "supabase_crm_estado": len(states),
            "supabase_historial": len(history),
        },
        "ultima_corrida": {
            "status": progress.get("status"),
            "started_at": progress.get("started_at"),
            "finished_at": progress.get("finished_at"),
            "nuevos_locales": progress.get("restaurantes_nuevos"),
            "subidos_supabase": progress.get("subidos_supabase"),
            "errores_supabase": progress.get("errores_supabase"),
            "ultimo_restaurante": progress.get("ultimo_restaurante"),
            "sync": progress.get("sincronizacion_supabase"),
            "logs_path": progress.get("logs_path"),
        },
        "ultimos_20_locales": latest_local,
        "ultimos_20_supabase": latest_supabase(client),
        "diferencias": {
            "locales_no_en_supabase": len(local_missing_supabase),
            "supabase_no_en_local": len(supabase_missing_local),
            "locales_no_en_supabase_ejemplos": compact_restaurants(local_missing_supabase),
            "supabase_no_en_local_ejemplos": compact_restaurants(supabase_missing_local),
        },
        "crm_estado": {
            "restaurantes_sin_crm_estado": len(restaurants_without_state),
            "crm_estado_sin_restaurante": len(states_without_restaurant),
            "resultado_seguimiento_vacio": sum(1 for row in states if is_empty(row.get("resultado_seguimiento"))),
            "estado_crm_vacio": sum(1 for row in states if is_empty(row.get("estado_crm"))),
            "estado_whatsapp_vacio": sum(1 for row in states if is_empty(row.get("estado_whatsapp"))),
            "restaurantes_sin_crm_estado_ejemplos": compact_restaurants(restaurants_without_state),
        },
        "restaurantes": {
            "estado_revision_rappi_vacio": sum(1 for row in restaurants if is_empty(row.get("estado_revision_rappi"))),
        },
        "historial_inicial": {
            "restaurantes_sin_evento_inicial": len(restaurants_without_initial),
            "eventos_iniciales_sin_crm_id": sum(1 for event in initial_events if is_empty(event.get("crm_id"))),
            "eventos_iniciales_sin_event_key": sum(1 for event in initial_events if is_empty(event.get("event_key"))),
            "eventos_iniciales_resultado_vacio": sum(1 for event in initial_events if is_empty(event.get("resultado_seguimiento_actual"))),
            "restaurantes_sin_evento_inicial_ejemplos": compact_restaurants(restaurants_without_initial),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


def compact_restaurants(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    return [
        {
            "crm_id": row.get("crm_id"),
            "nombre_restaurante": row.get("nombre_restaurante"),
            "comuna": row.get("comuna"),
            "created_at": row.get("created_at"),
            "fecha_carga": row.get("fecha_carga"),
        }
        for row in rows[:limit]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
