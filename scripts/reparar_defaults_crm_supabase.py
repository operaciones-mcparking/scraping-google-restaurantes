from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import get_supabase_service_client


INITIAL_ACTION = "Restaurante agregado"
INITIAL_MESSAGE = "Lead ingresado a la base"


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip() == ""


def fetch_all(client, table: str, select: str = "*") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    chunk = 1000
    while True:
        response = client.table(table).select(select).range(start, start + chunk - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < chunk:
            break
        start += chunk
    return rows


def event_key(crm_id: str, timestamp: str) -> str:
    raw = "|".join([crm_id, timestamp, "Sistema", INITIAL_ACTION, INITIAL_MESSAGE])
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def chunks(items: list[Any], size: int = 100):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reparar defaults CRM/Supabase sin sobrescribir datos reales.")
    parser.add_argument("--execute", action="store_true", help="Aplica cambios. Sin esto solo dry-run.")
    args = parser.parse_args()

    client = get_supabase_service_client()
    restaurants = fetch_all(
        client,
        "restaurantes",
        "id,crm_id,nombre_restaurante,nombre_normalizado,comuna,estado_revision_rappi,fecha_carga,fecha_extraccion,created_at",
    )
    states = fetch_all(client, "crm_estado")
    history = fetch_all(client, "historial_contactos", "event_key,crm_id,accion")

    restaurant_by_id = {clean(row.get("crm_id")): row for row in restaurants if clean(row.get("crm_id"))}
    state_by_id = {clean(row.get("crm_id")): row for row in states if clean(row.get("crm_id"))}
    initial_ids = {
        clean(event.get("crm_id"))
        for event in history
        if clean(event.get("crm_id")) and clean(event.get("accion")) == INITIAL_ACTION
    }

    crm_upserts: list[dict[str, Any]] = []
    for crm_id, restaurant in restaurant_by_id.items():
      state = state_by_id.get(crm_id)
      patch = {"crm_id": crm_id}
      if state is None or is_empty(state.get("estado_crm")):
          patch["estado_crm"] = "Nuevo"
      if state is None or is_empty(state.get("resultado_seguimiento")):
          patch["resultado_seguimiento"] = "Sin respuesta"
      if state is None or is_empty(state.get("estado_whatsapp")):
          patch["estado_whatsapp"] = "No contactado"
      if state is None:
          patch.update({
              "canal_ultimo_contacto": None,
              "fecha_ultimo_contacto": None,
              "fecha_ultimo_whatsapp": None,
              "mensaje_enviado": None,
              "observacion_crm": "",
          })
      if len(patch) > 1:
          crm_upserts.append(patch)

    rappi_missing = [crm_id for crm_id, row in restaurant_by_id.items() if is_empty(row.get("estado_revision_rappi"))]

    timestamp = datetime.now(timezone.utc).isoformat()
    initial_events: list[dict[str, Any]] = []
    for crm_id, row in restaurant_by_id.items():
        if crm_id in initial_ids:
            continue
        fecha = timestamp
        initial_events.append(
            {
                "event_key": event_key(crm_id, clean(fecha) or timestamp),
                "crm_id": crm_id,
                "restaurante_id": row.get("id"),
                "fecha_hora": fecha,
                "restaurante": row.get("nombre_restaurante") or row.get("nombre_normalizado"),
                "comuna": row.get("comuna"),
                "canal": "Sistema",
                "accion": INITIAL_ACTION,
                "estado_crm_actual": "Nuevo",
                "resultado_seguimiento_actual": "Sin respuesta",
                "mensaje_enviado": INITIAL_MESSAGE,
            }
        )

    summary = {
        "modo": "execute" if args.execute else "dry-run",
        "restaurantes": len(restaurants),
        "crm_estado": len(states),
        "crm_estado_a_reparar_o_crear": len(crm_upserts),
        "restaurantes_rappi_a_default": len(rappi_missing),
        "eventos_iniciales_a_crear": len(initial_events),
        "ejemplos_crm_estado": crm_upserts[:20],
        "ejemplos_rappi": rappi_missing[:20],
        "ejemplos_eventos": initial_events[:20],
        "aplicados": {
            "crm_estado": 0,
            "rappi": 0,
            "eventos": 0,
        },
    }

    if args.execute:
        for batch in chunks(crm_upserts):
            client.table("crm_estado").upsert(batch, on_conflict="crm_id").execute()
            summary["aplicados"]["crm_estado"] += len(batch)
        for batch in chunks(rappi_missing):
            client.table("restaurantes").update({"estado_revision_rappi": "No revisado", "fecha_revision_rappi": None}).in_("crm_id", batch).execute()
            summary["aplicados"]["rappi"] += len(batch)
        for batch in chunks(initial_events):
            client.table("historial_contactos").upsert(batch, on_conflict="event_key").execute()
            summary["aplicados"]["eventos"] += len(batch)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
