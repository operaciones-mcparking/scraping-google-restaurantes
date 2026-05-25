import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import get_supabase_service_client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INITIAL_ACTION = "Restaurante agregado"
CHILE_TZ = ZoneInfo("America/Santiago")


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


def fmt_chile(value: Any) -> str | None:
    parsed = parse_dt(value)
    if not parsed:
        return None
    return parsed.astimezone(CHILE_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def classify(event: dict[str, Any]) -> str:
    fecha = parse_dt(event.get("fecha_hora"))
    created = parse_dt(event.get("created_at"))
    if not fecha or not created:
        return "incompleto"
    diff_minutes = abs((created - fecha).total_seconds()) / 60
    if diff_minutes <= 5:
        return "reset/sync_ok"
    if fecha.hour == 0 and fecha.minute == 0 and fecha.second == 0:
        return "fecha_scraping_o_fecha_sin_hora"
    if fecha < created:
        return "fecha_evento_anterior_a_created_at"
    return "fecha_evento_posterior_a_created_at"


def main() -> None:
    client = get_supabase_service_client()
    response = (
        client.table("historial_contactos")
        .select("id,event_key,crm_id,restaurante,comuna,canal,accion,fecha_hora,created_at,estado_crm_actual,resultado_seguimiento_actual,mensaje_enviado")
        .eq("accion", INITIAL_ACTION)
        .order("fecha_hora", desc=True)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    rows = response.data or []
    result = {
        "columna_evento_usada": "fecha_hora",
        "timezone_visual_crm": "America/Santiago",
        "eventos": [
            {
                "restaurante": row.get("restaurante"),
                "comuna": row.get("comuna"),
                "canal": row.get("canal"),
                "accion": row.get("accion"),
                "fecha_hora_raw": row.get("fecha_hora"),
                "created_at_raw": row.get("created_at"),
                "fecha_hora_chile": fmt_chile(row.get("fecha_hora")),
                "created_at_chile": fmt_chile(row.get("created_at")),
                "origen_inferido": classify(row),
                "resultado": row.get("resultado_seguimiento_actual"),
                "event_key": "ok" if row.get("event_key") else None,
            }
            for row in rows
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
