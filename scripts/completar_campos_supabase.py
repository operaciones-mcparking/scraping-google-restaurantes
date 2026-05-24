from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.auditar_campos_restaurantes import AUDITED_FIELDS, fetch_all_supabase, is_empty, parse_dt
from scripts.sincronizar_incremental_supabase import clean_text, load_config, project_path, restaurant_record, sqlite_rows
from supabase_client import get_supabase_service_client


DEFAULT_CONFIG = ROOT / "configs" / "actualizacion_incremental_manual.json"
DEFAULT_FIELDS = [
    "comuna",
    "nivel_comercial",
    "tipo_negocio",
    "telefono",
    "instagram_url",
    "facebook_url",
    "google_maps_url",
    "sitio_web",
    "direccion",
    "rating",
    "cantidad_reviews",
    "nombre_normalizado",
]


def local_records(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = sqlite_rows(project_path(config["baseDatos"]))
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        record = restaurant_record(row)
        crm_id = clean_text(record.get("crm_id"))
        if crm_id:
            records[crm_id] = record
    return records


def build_updates(
    supabase_rows: list[dict[str, Any]],
    local_by_id: dict[str, dict[str, Any]],
    fields: list[str],
    new_cutoff: str | None = None,
) -> list[dict[str, Any]]:
    cutoff = parse_dt(new_cutoff) if new_cutoff else None
    updates: list[dict[str, Any]] = []
    for row in supabase_rows:
        if cutoff:
            row_date = parse_dt(row.get("created_at")) or parse_dt(row.get("fecha_carga"))
            if not row_date or row_date < cutoff:
                continue
        crm_id = clean_text(row.get("crm_id"))
        local = local_by_id.get(crm_id)
        if not local:
            continue
        patch = {"crm_id": crm_id}
        for field in fields:
            if is_empty(row.get(field)) and not is_empty(local.get(field)):
                patch[field] = local.get(field)
        if len(patch) > 1:
            updates.append(patch)
    return updates


def upload_updates(client, updates: list[dict[str, Any]], batch_size: int = 100) -> int:
    total = 0
    for start in range(0, len(updates), batch_size):
        batch = updates[start : start + batch_size]
        client.table("restaurantes").upsert(batch, on_conflict="crm_id").execute()
        total += len(batch)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Completar campos vacios de Supabase desde SQLite local.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--apply", action="store_true", help="Ejecuta la reparación. Sin esto solo muestra dry-run.")
    parser.add_argument("--fields", nargs="*", default=DEFAULT_FIELDS, choices=AUDITED_FIELDS)
    parser.add_argument("--new-cutoff", default="", help="Si se indica, repara solo registros creados/cargados desde esta fecha ISO.")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    supabase_rows = fetch_all_supabase()
    local_by_id = local_records(config)
    updates = build_updates(supabase_rows, local_by_id, args.fields, args.new_cutoff or None)
    summary = {
        "modo": "apply" if args.apply else "dry-run",
        "restaurantes_supabase": len(supabase_rows),
        "restaurantes_sqlite": len(local_by_id),
        "registros_con_campos_reparables": len(updates),
        "campos": args.fields,
        "new_cutoff": args.new_cutoff or None,
        "ejemplos": updates[:20],
        "actualizados": 0,
    }

    if args.apply and updates:
        client = get_supabase_service_client()
        summary["actualizados"] = upload_updates(client, updates)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
