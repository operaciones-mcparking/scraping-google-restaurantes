from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from supabase_client import get_supabase_client


DELIVERY_COLUMNS = {
    "rappi": {
        "present": "en_rappi",
        "url": "url_rappi",
    },
    "uber_eats": {
        "present": "en_uber_eats",
        "url": "url_uber_eats",
    },
    "pedidosya": {
        "present": "en_pedidosya",
        "url": "url_pedidosya",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara enriquecimiento local de presencia en Rappi, Uber Eats y PedidosYa."
    )
    parser.add_argument("--limit", type=int, default=5, help="Cantidad máxima de restaurantes a revisar.")
    parser.add_argument("--execute", action="store_true", help="Escribe resultados en Supabase. Por defecto solo muestra dry-run.")
    parser.add_argument("--only-pending", action="store_true", help="Revisa solo restaurantes con estado_revision_delivery vacío o No revisado.")
    return parser.parse_args()


def fetch_restaurants(limit: int, only_pending: bool) -> list[dict[str, Any]]:
    client = get_supabase_client()
    query = (
        client.table("restaurantes")
        .select("crm_id,nombre_restaurante,comuna,estado_revision_delivery")
        .order("fecha_carga", desc=True)
        .limit(limit)
    )
    if only_pending:
        # Supabase Python does not expose a simple OR helper consistently across versions,
        # so pending filtering is kept conservative for the first local dry-run.
        query = query.eq("estado_revision_delivery", "No revisado")
    response = query.execute()
    return list(response.data or [])


def build_empty_delivery_result(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "crm_id": row.get("crm_id"),
        "en_rappi": None,
        "en_uber_eats": None,
        "en_pedidosya": None,
        "url_rappi": "",
        "url_uber_eats": "",
        "url_pedidosya": "",
        "fecha_revision_delivery": now,
        "estado_revision_delivery": "No revisado",
        "observacion_revision_delivery": "Pendiente: scraper delivery no implementado en esta etapa.",
    }


def main() -> None:
    args = parse_args()
    rows = fetch_restaurants(args.limit, args.only_pending)
    print(f"Restaurantes leídos desde Supabase: {len(rows)}")
    print(f"Modo: {'EXECUTE' if args.execute else 'DRY-RUN'}")

    results = [build_empty_delivery_result(row) for row in rows]
    for row, result in zip(rows, results):
        name = row.get("nombre_restaurante", "")
        comuna = row.get("comuna", "")
        print(f"- {name} | {comuna} | estado={result['estado_revision_delivery']}")

    if not args.execute:
        print("Dry-run: no se escribió nada en Supabase.")
        return

    if not results:
        print("No hay restaurantes para actualizar.")
        return

    client = get_supabase_client()
    for result in results:
        crm_id = result.get("crm_id")
        if not crm_id:
            continue
        payload = {key: value for key, value in result.items() if key != "crm_id"}
        client.table("restaurantes").update(payload).eq("crm_id", crm_id).execute()
    print(f"Supabase actualizado: {len(results)} registros.")


if __name__ == "__main__":
    main()
