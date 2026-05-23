from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from supabase_client import get_supabase_client
from supabase_client import load_supabase_secrets


ROOT = Path(__file__).resolve().parent
APP_MODE_CONFIG = ROOT / "configs" / "app_mode.json"
BASE_XLSX = ROOT / "data" / "base_restaurantes_actualizada.xlsx"
CRM_XLSX = ROOT / "data" / "crm_restaurantes_estado.xlsx"
HISTORY_XLSX = ROOT / "data" / "historial_contactos.xlsx"
MESSAGES_JSON = ROOT / "configs" / "mensajes_whatsapp.json"

VALID_MODES = {"local", "supabase"}

CRM_COLUMN_MAP = {
    "CRM ID": "crm_id",
    "Estado CRM": "estado_crm",
    "Fecha ultimo contacto": "fecha_ultimo_contacto",
    "Canal ultimo contacto": "canal_ultimo_contacto",
    "Responsable": "responsable",
    "Observacion CRM": "observacion_crm",
    "Proxima accion": "proxima_accion",
    "Fecha proxima accion": "fecha_proxima_accion",
    "Fecha ultimo WhatsApp": "fecha_ultimo_whatsapp",
    "Mensaje WhatsApp sugerido": "mensaje_whatsapp_sugerido",
    "Estado WhatsApp": "estado_whatsapp",
    "Variante mensaje": "variante_mensaje",
    "Mensaje enviado": "mensaje_enviado",
    "Fecha envio WhatsApp": "fecha_envio_whatsapp",
    "Respondio": "respondio",
    "Interesado": "interesado",
    "Reunion agendada": "reunion_agendada",
    "Resultado comercial": "resultado_comercial",
    "Resultado seguimiento": "resultado_seguimiento",
}


def get_data_mode() -> str:
    if not APP_MODE_CONFIG.exists():
        return "local"
    try:
        payload = json.loads(APP_MODE_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "local"
    mode = str(payload.get("data_mode", "local")).strip().lower()
    return mode if mode in VALID_MODES else "local"


def load_restaurantes() -> pd.DataFrame:
    return _load_restaurantes_supabase() if get_data_mode() == "supabase" else _load_restaurantes_local()


def load_crm_estado() -> pd.DataFrame:
    return _load_crm_estado_supabase() if get_data_mode() == "supabase" else _load_crm_estado_local()


def load_historial_contactos() -> pd.DataFrame:
    return _load_historial_contactos_supabase() if get_data_mode() == "supabase" else _load_historial_contactos_local()


def load_mensajes() -> dict[str, dict[str, object]]:
    return _load_mensajes_supabase() if get_data_mode() == "supabase" else _load_mensajes_local()


def _load_restaurantes_local() -> pd.DataFrame:
    if not BASE_XLSX.exists():
        return pd.DataFrame()
    return pd.read_excel(BASE_XLSX, sheet_name="Base restaurantes")


def _load_crm_estado_local() -> pd.DataFrame:
    if not CRM_XLSX.exists():
        return pd.DataFrame()
    return pd.read_excel(CRM_XLSX)


def _load_historial_contactos_local() -> pd.DataFrame:
    if not HISTORY_XLSX.exists():
        return pd.DataFrame()
    return pd.read_excel(HISTORY_XLSX)


def _load_mensajes_local() -> dict[str, dict[str, object]]:
    if not MESSAGES_JSON.exists():
        return {}
    return json.loads(MESSAGES_JSON.read_text(encoding="utf-8-sig"))


def _supabase_rows(table: str, select: str = "*") -> list[dict[str, Any]]:
    secrets = load_supabase_secrets()
    url = f'{secrets["SUPABASE_URL"].rstrip("/")}/rest/v1/{table}'
    base_headers = {
        "apikey": secrets["SUPABASE_KEY"],
        "Authorization": f'Bearer {secrets["SUPABASE_KEY"]}',
        "Accept": "application/json",
    }
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    while True:
        headers = dict(base_headers)
        headers["Range"] = f"{start}-{start + page_size - 1}"
        params = {"select": select}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=25)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"No se pudo cargar la tabla Supabase '{table}': {exc}") from exc
        payload = response.json()
        page = list(payload or []) if isinstance(payload, list) else []
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _load_restaurantes_supabase() -> pd.DataFrame:
    rows = _supabase_rows("restaurantes")
    records = []
    for row in rows:
        payload = row.get("data_json") if isinstance(row.get("data_json"), dict) else {}
        record = dict(payload)
        record.setdefault("Nombre restaurante", row.get("nombre_restaurante", ""))
        record.setdefault("Rating", row.get("rating", ""))
        record.setdefault("Cantidad reviews", row.get("cantidad_reviews", ""))
        record.setdefault("Dirección", row.get("direccion", ""))
        record.setdefault("Teléfono", row.get("telefono", ""))
        record.setdefault("Sitio web", row.get("sitio_web", ""))
        record.setdefault("Categoría", row.get("categoria", ""))
        record.setdefault("Google Maps URL", row.get("google_maps_url", ""))
        record.setdefault("Latitud", row.get("latitud", ""))
        record.setdefault("Longitud", row.get("longitud", ""))
        record.setdefault("Comuna", row.get("comuna", ""))
        record.setdefault("Región", row.get("region", ""))
        record.setdefault("País", row.get("pais", ""))
        record.setdefault("Fuente", row.get("fuente", ""))
        record.setdefault("Fecha extracción", row.get("fecha_extraccion", ""))
        record.setdefault("Nombre normalizado", row.get("nombre_normalizado", ""))
        record.setdefault("Tipo negocio", row.get("tipo_negocio", ""))
        record.setdefault("Score comercial", row.get("score_comercial", ""))
        record.setdefault("Nivel comercial", row.get("nivel_comercial", ""))
        record.setdefault("Estado revision Rappi", row.get("estado_revision_rappi", "") or "No revisado")
        record.setdefault("URL Rappi", row.get("url_rappi", ""))
        record.setdefault("Fecha revision Rappi", row.get("fecha_revision_rappi", ""))
        record.setdefault("Observacion revision Rappi", row.get("observacion_revision_rappi", ""))
        record["CRM ID"] = row.get("crm_id", "")
        record["Fecha carga CRM"] = row.get("fecha_carga") or row.get("fecha_extraccion") or ""
        records.append(record)
    return pd.DataFrame(records)


def _load_crm_estado_supabase() -> pd.DataFrame:
    rows = _supabase_rows("crm_estado")
    records = []
    for row in rows:
        records.append(
            {
                "CRM ID": row.get("crm_id", ""),
                "Estado CRM": row.get("estado_crm", ""),
                "Fecha ultimo contacto": row.get("fecha_ultimo_contacto", ""),
                "Canal ultimo contacto": row.get("canal_ultimo_contacto", ""),
                "Responsable": row.get("responsable", ""),
                "Observacion CRM": row.get("observacion_crm", ""),
                "Proxima accion": row.get("proxima_accion", ""),
                "Fecha proxima accion": row.get("fecha_proxima_accion", ""),
                "Fecha ultimo WhatsApp": row.get("fecha_ultimo_whatsapp", ""),
                "Mensaje WhatsApp sugerido": row.get("mensaje_whatsapp_sugerido", ""),
                "Estado WhatsApp": row.get("estado_whatsapp", ""),
                "Variante mensaje": row.get("variante_mensaje", ""),
                "Mensaje enviado": row.get("mensaje_enviado", ""),
                "Fecha envio WhatsApp": row.get("fecha_envio_whatsapp", ""),
                "Respondio": row.get("respondio", ""),
                "Interesado": row.get("interesado", ""),
                "Reunion agendada": row.get("reunion_agendada", ""),
                "Resultado comercial": row.get("resultado_comercial", ""),
                "Resultado seguimiento": row.get("resultado_seguimiento", ""),
            }
        )
    return pd.DataFrame(records)


def _load_historial_contactos_supabase() -> pd.DataFrame:
    rows = _supabase_rows("historial_contactos")
    records = []
    for row in rows:
        records.append(
            {
                "Fecha/hora": row.get("fecha_hora", ""),
                "CRM ID": row.get("crm_id", ""),
                "Restaurante": row.get("restaurante", ""),
                "Comuna": row.get("comuna", ""),
                "Canal": row.get("canal", ""),
                "Acción": row.get("accion", ""),
                "Estado CRM actual": row.get("estado_crm_actual", ""),
                "Resultado seguimiento actual": row.get("resultado_seguimiento_actual", ""),
                "Mensaje enviado": row.get("mensaje_enviado", ""),
            }
        )
    return pd.DataFrame(records)


def _load_mensajes_supabase() -> dict[str, dict[str, object]]:
    rows = _supabase_rows("mensajes_whatsapp")
    config: dict[str, dict[str, object]] = {}
    for row in sorted(rows, key=lambda item: item.get("orden") or 0):
        codigo = str(row.get("codigo", "")).strip()
        if not codigo:
            continue
        config[codigo] = {
            "text": row.get("texto", "") or "",
            "active": bool(row.get("activo", True)),
        }
    return config


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _crm_record(row: dict[str, Any]) -> dict[str, Any]:
    record = {}
    for source, target in CRM_COLUMN_MAP.items():
        if source in row:
            record[target] = _clean_value(row.get(source))
    return record


def save_crm_estado(records: pd.DataFrame | list[dict[str, Any]] | dict[str, Any]) -> int:
    if get_data_mode() != "supabase":
        return 0
    if isinstance(records, pd.DataFrame):
        rows = records.fillna("").to_dict(orient="records")
    elif isinstance(records, dict):
        rows = [records]
    else:
        rows = records
    payload = [_crm_record(row) for row in rows]
    payload = [row for row in payload if row.get("crm_id")]
    if not payload:
        return 0
    client = get_supabase_client()
    client.table("crm_estado").upsert(payload, on_conflict="crm_id").execute()
    return len(payload)


def update_lead_status(crm_id: str, updates: dict[str, Any]) -> None:
    if get_data_mode() != "supabase":
        return
    record = {"CRM ID": crm_id}
    record.update(updates)
    save_crm_estado(record)


def save_rappi_review(
    crm_id: str,
    estado: str,
    url_rappi: str = "",
    observacion: str = "",
    fecha_revision: str | None = None,
) -> None:
    if get_data_mode() != "supabase":
        return
    payload = {
        "estado_revision_rappi": _clean_value(estado) or "No revisado",
        "url_rappi": _clean_value(url_rappi),
        "observacion_revision_rappi": _clean_value(observacion),
        "fecha_revision_rappi": _clean_value(fecha_revision),
    }
    client = get_supabase_client()
    client.table("restaurantes").update(payload).eq("crm_id", crm_id).execute()


def reset_rappi_reviews(crm_ids: set[str] | list[str] | None = None) -> int:
    if get_data_mode() != "supabase":
        return 0
    payload = {
        "estado_revision_rappi": "No revisado",
        "url_rappi": None,
        "fecha_revision_rappi": None,
        "observacion_revision_rappi": None,
    }
    client = get_supabase_client()
    if crm_ids is None:
        response = client.table("restaurantes").update(payload).execute()
        return len(response.data or [])

    ids = sorted({str(value).strip() for value in crm_ids if str(value).strip()})
    if not ids:
        return 0

    updated = 0
    # PostgREST sends filters in the URL. Keep batches small because some crm_id
    # values can be long and otherwise httpx rejects the query before sending it.
    batch_size = 10
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        client.table("restaurantes").update(payload).in_("crm_id", batch).execute()
        updated += len(batch)
    return updated


def _event_key(event: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(event.get("crm_id", "")),
            str(event.get("canal", "")),
            str(event.get("accion", "")),
            str(event.get("fecha_hora", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def _history_record(event: dict[str, Any]) -> dict[str, Any]:
    record = {
        "event_key": event.get("event_key"),
        "crm_id": event.get("CRM ID") or event.get("crm_id"),
        "fecha_hora": event.get("Fecha/hora") or event.get("fecha_hora"),
        "restaurante": event.get("Restaurante") or event.get("restaurante"),
        "comuna": event.get("Comuna") or event.get("comuna"),
        "canal": event.get("Canal") or event.get("canal"),
        "accion": event.get("Acción") or event.get("Accion") or event.get("accion"),
        "estado_crm_actual": event.get("Estado CRM actual") or event.get("estado_crm_actual"),
        "resultado_seguimiento_actual": event.get("Resultado seguimiento actual") or event.get("resultado_seguimiento_actual"),
        "mensaje_enviado": event.get("Mensaje enviado") or event.get("mensaje_enviado"),
    }
    if not record.get("accion"):
        record["accion"] = event.get("Acción")
    record = {key: _clean_value(value) for key, value in record.items() if _clean_value(value) is not None}
    if not record.get("event_key"):
        record["event_key"] = _event_key(record)
    return record


def insert_historial_evento(event: dict[str, Any]) -> str:
    if get_data_mode() != "supabase":
        return ""
    record = _history_record(event)
    if not record.get("crm_id") or not record.get("accion"):
        return ""
    client = get_supabase_client()
    client.table("historial_contactos").upsert(record, on_conflict="event_key").execute()
    return str(record["event_key"])


def replace_contact_history(events: pd.DataFrame | list[dict[str, Any]]) -> dict[str, int | str]:
    stats: dict[str, int | str] = {
        "data_mode": get_data_mode(),
        "total_before": 0,
        "target_before": 0,
        "kept_initial": 0,
        "deleted": 0,
        "initial_recreated": 0,
        "total_after": 0,
    }
    if get_data_mode() != "supabase":
        return stats
    if isinstance(events, pd.DataFrame):
        event_rows = events.fillna("").to_dict(orient="records")
    else:
        event_rows = events

    payload = [_history_record(row) for row in event_rows]
    payload = [row for row in payload if row.get("crm_id") and row.get("accion")]
    raw_rows = _supabase_rows("historial_contactos")
    stats["total_before"] = len(raw_rows)
    stats["target_before"] = len(raw_rows)
    if not payload:
        stats["total_after"] = len(raw_rows)
        return stats

    keys = [row.get("event_key") for row in raw_rows if row.get("event_key")]
    client = get_supabase_client()
    for start in range(0, len(keys), 100):
        batch = keys[start : start + 100]
        if batch:
            client.table("historial_contactos").delete().in_("event_key", batch).execute()
            stats["deleted"] = int(stats["deleted"]) + len(batch)

    for start in range(0, len(payload), 100):
        batch = payload[start : start + 100]
        if batch:
            client.table("historial_contactos").upsert(batch, on_conflict="event_key").execute()
            stats["initial_recreated"] = int(stats["initial_recreated"]) + len(batch)
    stats["total_after"] = len(_supabase_rows("historial_contactos"))
    return stats


def save_whatsapp_event(
    crm_id: str,
    restaurant: str,
    comuna: str,
    message: str,
    estado_crm: str = "Contactado",
    resultado: str = "Sin respuesta",
    fecha_hora: str | None = None,
) -> str:
    return insert_historial_evento(
        {
            "CRM ID": crm_id,
            "Fecha/hora": fecha_hora,
            "Restaurante": restaurant,
            "Comuna": comuna,
            "Canal": "WhatsApp",
            "Acción": "WhatsApp abierto",
            "Estado CRM actual": estado_crm,
            "Resultado seguimiento actual": resultado,
            "Mensaje enviado": message,
        }
    )


def save_call_event(
    crm_id: str,
    restaurant: str,
    comuna: str,
    estado_crm: str = "Contactado",
    resultado: str = "Sin respuesta",
    fecha_hora: str | None = None,
) -> str:
    return insert_historial_evento(
        {
            "CRM ID": crm_id,
            "Fecha/hora": fecha_hora,
            "Restaurante": restaurant,
            "Comuna": comuna,
            "Canal": "Llamada",
            "Acción": "Llamada iniciada",
            "Estado CRM actual": estado_crm,
            "Resultado seguimiento actual": resultado,
            "Mensaje enviado": "Llamada iniciada desde CRM",
        }
    )


def clear_contact_history_for_leads(crm_ids: set[str] | list[str]) -> dict[str, int | str]:
    stats: dict[str, int | str] = {
        "data_mode": get_data_mode(),
        "total_before": 0,
        "target_before": 0,
        "kept_initial": 0,
        "deleted": 0,
        "total_after": 0,
    }
    if get_data_mode() != "supabase":
        return stats
    ids = {str(value).strip() for value in crm_ids if str(value).strip()}
    if not ids:
        return stats
    raw_rows = _supabase_rows("historial_contactos")
    stats["total_before"] = len(raw_rows)

    def is_initial(row: dict[str, Any]) -> bool:
        return (
            str(row.get("accion", "")).strip() == "Restaurante agregado"
            or str(row.get("mensaje_enviado", "")).strip() == "Lead ingresado a la base"
        )

    target_rows = [row for row in raw_rows if str(row.get("crm_id", "")).strip() in ids]
    stats["target_before"] = len(target_rows)
    stats["kept_initial"] = sum(1 for row in target_rows if is_initial(row))
    keys = [row.get("event_key") for row in target_rows if not is_initial(row) and row.get("event_key")]
    if not keys:
        stats["total_after"] = len(raw_rows)
        return stats
    client = get_supabase_client()
    for start in range(0, len(keys), 100):
        batch = keys[start : start + 100]
        if batch:
            client.table("historial_contactos").delete().in_("event_key", batch).execute()
            stats["deleted"] = int(stats["deleted"]) + len(batch)
    stats["total_after"] = len(_supabase_rows("historial_contactos"))
    return stats
