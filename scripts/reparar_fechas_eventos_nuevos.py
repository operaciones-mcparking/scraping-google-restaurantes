import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import get_supabase_service_client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INITIAL_ACTION = "Restaurante agregado"
INITIAL_CHANNEL = "Sistema"
INITIAL_MESSAGE = "Lead ingresado a la base"


def parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def should_repair(event: dict[str, Any], min_diff_minutes: int) -> bool:
    if event.get("canal") != INITIAL_CHANNEL or event.get("accion") != INITIAL_ACTION:
        return False
    if event.get("mensaje_enviado") != INITIAL_MESSAGE:
        return False
    fecha = parse_dt(event.get("fecha_hora"))
    created = parse_dt(event.get("created_at"))
    if not fecha or not created:
        return False
    diff_minutes = (created - fecha).total_seconds() / 60
    return diff_minutes >= min_diff_minutes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repara fecha_hora de eventos iniciales creados por sync con fecha antigua.")
    parser.add_argument("--execute", action="store_true", help="Aplica cambios. Por defecto solo dry-run.")
    parser.add_argument("--limit", type=int, default=500, help="Cantidad maxima de eventos iniciales recientes a revisar.")
    parser.add_argument("--min-diff-minutes", type=int, default=30, help="Diferencia minima entre created_at y fecha_hora para reparar.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = get_supabase_service_client()
    response = (
        client.table("historial_contactos")
        .select("id,event_key,crm_id,restaurante,comuna,canal,accion,fecha_hora,created_at,mensaje_enviado")
        .eq("accion", INITIAL_ACTION)
        .eq("canal", INITIAL_CHANNEL)
        .order("created_at", desc=True)
        .limit(args.limit)
        .execute()
    )
    events = response.data or []
    candidates = [event for event in events if should_repair(event, args.min_diff_minutes)]

    updated = 0
    errors: list[dict[str, str]] = []
    if args.execute:
        for event in candidates:
            new_fecha = event.get("created_at")
            result = (
                client.table("historial_contactos")
                .update({"fecha_hora": new_fecha})
                .eq("id", event["id"])
                .execute()
            )
            if getattr(result, "data", None) is not None:
                updated += 1
            else:
                errors.append({"id": str(event.get("id")), "error": "Sin respuesta data de Supabase"})

    summary = {
        "modo": "execute" if args.execute else "dry-run",
        "eventos_revisados": len(events),
        "candidatos_a_reparar": len(candidates),
        "actualizados": updated,
        "errores": errors,
        "criterio": {
            "accion": INITIAL_ACTION,
            "canal": INITIAL_CHANNEL,
            "mensaje": INITIAL_MESSAGE,
            "fecha_hora_anterior_a_created_at_minutos": args.min_diff_minutes,
            "nuevo_valor_fecha_hora": "created_at",
        },
        "ejemplos": [
            {
                "id": event.get("id"),
                "restaurante": event.get("restaurante"),
                "comuna": event.get("comuna"),
                "fecha_hora_actual": event.get("fecha_hora"),
                "created_at": event.get("created_at"),
                "fecha_hora_nueva": event.get("created_at"),
            }
            for event in candidates[:20]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
