from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sincronizar_incremental_supabase import clean_text, load_config, project_path, restaurant_record, sqlite_rows
from supabase_client import get_supabase_service_client


DEFAULT_CONFIG = ROOT / "configs" / "actualizacion_incremental_manual.json"
AUDITED_FIELDS = [
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
LINK_FIELDS = ["instagram_url", "facebook_url", "google_maps_url", "sitio_web"]


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def parse_dt(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_all_supabase() -> list[dict[str, Any]]:
    client = get_supabase_service_client()
    rows: list[dict[str, Any]] = []
    start = 0
    chunk = 1000
    while True:
        response = client.table("restaurantes").select("*").range(start, start + chunk - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < chunk:
            break
        start += chunk
    return rows


def local_records(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = sqlite_rows(project_path(config["baseDatos"]))
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        record = restaurant_record(row)
        crm_id = clean_text(record.get("crm_id"))
        if crm_id:
            records[crm_id] = record
    return records


def classify_rows(rows: list[dict[str, Any]], cutoff: datetime | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if cutoff is None:
        sorted_rows = sorted(rows, key=lambda row: clean_text(row.get("created_at") or row.get("fecha_carga")))
        return sorted_rows[:-76], sorted_rows[-76:]

    old_rows: list[dict[str, Any]] = []
    new_rows: list[dict[str, Any]] = []
    for row in rows:
        date_value = parse_dt(row.get("created_at")) or parse_dt(row.get("fecha_carga"))
        if date_value and date_value >= cutoff:
            new_rows.append(row)
        else:
            old_rows.append(row)
    return old_rows, new_rows


def empty_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {field: sum(1 for row in rows if is_empty(row.get(field))) for field in AUDITED_FIELDS}


def source_gap_analysis(supabase_rows: list[dict[str, Any]], local_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gaps = []
    fixable = Counter()
    missing_local = 0
    for row in supabase_rows:
        crm_id = clean_text(row.get("crm_id"))
        local = local_by_id.get(crm_id)
        if not local:
            missing_local += 1
            continue
        for field in AUDITED_FIELDS:
            if is_empty(row.get(field)):
                local_value = local.get(field)
                if not is_empty(local_value):
                    fixable[field] += 1
                    gaps.append(
                        {
                            "crm_id": crm_id,
                            "nombre_restaurante": row.get("nombre_restaurante"),
                            "field": field,
                            "local_value": local_value,
                        }
                    )
    return {"campos_reparables": dict(fixable), "sin_registro_local": missing_local, "ejemplos_reparables": gaps[:20]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar campos vacios en restaurantes Supabase vs SQLite local.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--new-cutoff",
        default="2026-05-24T00:00:00+00:00",
        help="Fecha ISO para separar nuevos vs antiguos. Usa los ultimos 76 si se pasa vacio.",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    supabase_rows = fetch_all_supabase()
    local_by_id = local_records(config)
    cutoff = parse_dt(args.new_cutoff) if args.new_cutoff else None
    old_rows, new_rows = classify_rows(supabase_rows, cutoff)

    report = {
        "total_restaurantes_supabase": len(supabase_rows),
        "total_restaurantes_sqlite": len(local_by_id),
        "criterio_nuevos": args.new_cutoff or "ultimos_76_por_fecha",
        "antiguos": {
            "total": len(old_rows),
            "campos_vacios": empty_counts(old_rows),
        },
        "nuevos": {
            "total": len(new_rows),
            "campos_vacios": empty_counts(new_rows),
            "sin_links": sum(1 for row in new_rows if all(is_empty(row.get(field)) for field in LINK_FIELDS)),
        },
        "totales": {
            "nivel_comercial_vacio": sum(1 for row in supabase_rows if is_empty(row.get("nivel_comercial"))),
            "tipo_negocio_vacio": sum(1 for row in supabase_rows if is_empty(row.get("tipo_negocio"))),
            "telefono_vacio": sum(1 for row in supabase_rows if is_empty(row.get("telefono"))),
            "links_vacios": {field: sum(1 for row in supabase_rows if is_empty(row.get(field))) for field in LINK_FIELDS},
        },
        "analisis_origen_nuevos": source_gap_analysis(new_rows, local_by_id),
        "ejemplos_nuevos_incompletos": [
            {
                "crm_id": row.get("crm_id"),
                "nombre_restaurante": row.get("nombre_restaurante"),
                "comuna": row.get("comuna"),
                "nivel_comercial": row.get("nivel_comercial"),
                "tipo_negocio": row.get("tipo_negocio"),
                "telefono": row.get("telefono"),
                "categoria": row.get("categoria"),
                "created_at": row.get("created_at"),
                "fecha_carga": row.get("fecha_carga"),
            }
            for row in new_rows
            if any(is_empty(row.get(field)) for field in ["nivel_comercial", "tipo_negocio", "telefono", "nombre_normalizado"])
        ][:20],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
