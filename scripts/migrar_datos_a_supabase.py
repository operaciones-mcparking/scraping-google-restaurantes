from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import SupabaseConfigError, get_supabase_client


BASE_XLSX = ROOT / "data" / "base_restaurantes_actualizada.xlsx"
CRM_XLSX = ROOT / "data" / "crm_restaurantes_estado.xlsx"
HISTORY_XLSX = ROOT / "data" / "historial_contactos.xlsx"
MESSAGES_JSON = ROOT / "configs" / "mensajes_whatsapp.json"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text.strip()


def strip_accents(text: Any) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", clean_text(text)) if unicodedata.category(ch) != "Mn")


def norm_text(text: Any) -> str:
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_coord(value: Any) -> str:
    text = clean_text(value).replace(",", ".")
    if not text:
        return ""
    try:
        return f"{float(text):.6f}"
    except ValueError:
        return norm_text(text)


def parse_number(value: Any) -> float | None:
    text = clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_datetime(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.isoformat()


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return value


def row_to_json(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): json_safe(value) for key, value in row.items()}


def find_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return ""


def lead_key(row: dict[str, Any]) -> str:
    maps = clean_text(find_value(row, "Google Maps URL"))
    if maps:
        return maps
    name = clean_text(find_value(row, "Nombre restaurante")).lower()
    address = clean_text(find_value(row, "Dirección", "Direccion")).lower()
    comuna = clean_text(find_value(row, "Comuna")).lower()
    fallback = "|".join([name, address, comuna]).strip("|")
    return fallback


def key_parts(row: dict[str, Any]) -> dict[str, str]:
    url = clean_text(find_value(row, "Google Maps URL"))
    name = norm_text(find_value(row, "Nombre normalizado", "Nombre restaurante"))
    address = norm_text(find_value(row, "Dirección", "Direccion"))
    comuna = norm_text(find_value(row, "Comuna"))
    lat = norm_coord(find_value(row, "Latitud"))
    lng = norm_coord(find_value(row, "Longitud"))
    key1 = f"url::{url}" if url else ""
    key2 = f"name_address_comuna::{name}|{address}|{comuna}" if name and address and comuna else ""
    key3 = f"name_lat_lng::{name}|{lat}|{lng}" if name and lat and lng else ""
    selected = key1 or key2 or key3 or lead_key(row)
    return {"key1": key1, "key2": key2, "key3": key3, "selected": selected}


def read_excel_rows(path: Path, sheet_name: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    df = pd.read_excel(path, sheet_name=sheet_name or 0)
    return df.fillna("").to_dict(orient="records")


def build_restaurantes() -> list[dict[str, Any]]:
    rows = read_excel_rows(BASE_XLSX, "Base restaurantes")
    records = []
    for row in rows:
        crm_id = lead_key(row)
        keys = key_parts(row)
        if not crm_id:
            continue
        record = {
            "crm_id": crm_id,
            "unique_key": keys["selected"],
            "key_google_maps_url": keys["key1"],
            "key_nombre_direccion_comuna": keys["key2"],
            "key_nombre_lat_lng": keys["key3"],
            "nombre_restaurante": clean_text(find_value(row, "Nombre restaurante")),
            "nombre_normalizado": clean_text(find_value(row, "Nombre normalizado")),
            "rating": parse_number(find_value(row, "Rating")),
            "cantidad_reviews": parse_int(find_value(row, "Cantidad reviews")),
            "direccion": clean_text(find_value(row, "Dirección", "Direccion")),
            "telefono": clean_text(find_value(row, "Teléfono", "Telefono")),
            "sitio_web": clean_text(find_value(row, "Sitio web")),
            "categoria": clean_text(find_value(row, "Categoría", "Categoria")),
            "google_maps_url": clean_text(find_value(row, "Google Maps URL")),
            "latitud": parse_number(find_value(row, "Latitud")),
            "longitud": parse_number(find_value(row, "Longitud")),
            "comuna": clean_text(find_value(row, "Comuna")),
            "region": clean_text(find_value(row, "Región", "Region")),
            "pais": clean_text(find_value(row, "País", "Pais")),
            "fuente": clean_text(find_value(row, "Fuente")),
            "fecha_extraccion": parse_datetime(find_value(row, "Fecha extracción", "Fecha extraccion")),
            "fecha_carga": parse_datetime(find_value(row, "Fecha carga", "Fecha extracción", "Fecha extraccion")),
            "calidad_dato": clean_text(find_value(row, "Calidad dato")),
            "es_restaurante_valido": clean_text(find_value(row, "Es restaurante válido", "Es restaurante valido")),
            "instagram_url": clean_text(find_value(row, "Instagram URL")),
            "instagram_usuario": clean_text(find_value(row, "Instagram Usuario")),
            "facebook_url": clean_text(find_value(row, "Facebook URL")),
            "tiktok_url": clean_text(find_value(row, "TikTok URL")),
            "tiene_redes": clean_text(find_value(row, "Tiene Redes")),
            "calidad_redes": clean_text(find_value(row, "Calidad Redes")),
            "esta_en_uber_eats": clean_text(find_value(row, "Está en Uber Eats", "Esta en Uber Eats")),
            "url_uber_eats": clean_text(find_value(row, "URL Uber Eats")),
            "confianza_uber_eats": clean_text(find_value(row, "Confianza Uber Eats")),
            "esta_en_pedidosya": clean_text(find_value(row, "Está en PedidosYa", "Esta en PedidosYa")),
            "url_pedidosya": clean_text(find_value(row, "URL PedidosYa")),
            "confianza_pedidosya": clean_text(find_value(row, "Confianza PedidosYa")),
            "esta_en_rappi": clean_text(find_value(row, "Está en Rappi", "Esta en Rappi")),
            "url_rappi": clean_text(find_value(row, "URL Rappi")),
            "confianza_rappi": clean_text(find_value(row, "Confianza Rappi")),
            "observaciones": clean_text(find_value(row, "Observaciones")),
            "posible_cadena_franquicia": clean_text(find_value(row, "Posible cadena/franquicia")),
            "grupo_cadena_franquicia": clean_text(find_value(row, "Grupo cadena/franquicia")),
            "posible_duplicado_entre_comunas": clean_text(find_value(row, "Posible duplicado entre comunas")),
            "grupo_duplicado": clean_text(find_value(row, "Grupo duplicado")),
            "tipo_negocio": clean_text(find_value(row, "Tipo negocio")),
            "score_comercial": parse_number(find_value(row, "Score comercial")),
            "nivel_comercial": clean_text(find_value(row, "Nivel comercial")),
            "data_json": row_to_json(row),
        }
        records.append(record)
    return dedupe(records, "crm_id")


def build_crm_estado() -> list[dict[str, Any]]:
    rows = read_excel_rows(CRM_XLSX)
    records = []
    for row in rows:
        crm_id = clean_text(find_value(row, "CRM ID"))
        if not crm_id:
            continue
        records.append(
            {
                "crm_id": crm_id,
                "estado_crm": clean_text(find_value(row, "Estado CRM")),
                "fecha_ultimo_contacto": parse_datetime(find_value(row, "Fecha último contacto", "Fecha ultimo contacto")),
                "canal_ultimo_contacto": clean_text(find_value(row, "Canal último contacto", "Canal ultimo contacto")),
                "responsable": clean_text(find_value(row, "Responsable")),
                "observacion_crm": clean_text(find_value(row, "Observación CRM", "Observacion CRM")),
                "proxima_accion": clean_text(find_value(row, "Próxima acción", "Proxima accion")),
                "fecha_proxima_accion": parse_datetime(find_value(row, "Fecha próxima acción", "Fecha proxima accion")),
                "fecha_ultimo_whatsapp": parse_datetime(find_value(row, "Fecha último WhatsApp", "Fecha ultimo WhatsApp")),
                "mensaje_whatsapp_sugerido": clean_text(find_value(row, "Mensaje WhatsApp sugerido")),
                "estado_whatsapp": clean_text(find_value(row, "Estado WhatsApp")),
                "variante_mensaje": clean_text(find_value(row, "Variante mensaje")),
                "mensaje_enviado": clean_text(find_value(row, "Mensaje enviado")),
                "fecha_envio_whatsapp": parse_datetime(find_value(row, "Fecha envío WhatsApp", "Fecha envio WhatsApp")),
                "respondio": clean_text(find_value(row, "Respondió", "Respondio")),
                "interesado": clean_text(find_value(row, "Interesado")),
                "reunion_agendada": clean_text(find_value(row, "Reunión agendada", "Reunion agendada")),
                "resultado_comercial": clean_text(find_value(row, "Resultado comercial")),
                "resultado_seguimiento": clean_text(find_value(row, "Resultado seguimiento")),
            }
        )
    return dedupe(records, "crm_id")


def build_historial_contactos() -> list[dict[str, Any]]:
    rows = read_excel_rows(HISTORY_XLSX)
    records = []
    for row in rows:
        crm_id = clean_text(find_value(row, "CRM ID"))
        fecha_hora = parse_datetime(find_value(row, "Fecha/hora", "Fecha hora"))
        canal = clean_text(find_value(row, "Canal"))
        accion = clean_text(find_value(row, "Acción", "Accion"))
        mensaje = clean_text(find_value(row, "Mensaje enviado"))
        if not crm_id or not accion:
            continue
        event_key = hashlib.sha1("|".join([crm_id, fecha_hora or "", canal, accion, mensaje]).encode("utf-8")).hexdigest()
        records.append(
            {
                "event_key": event_key,
                "crm_id": crm_id,
                "fecha_hora": fecha_hora,
                "restaurante": clean_text(find_value(row, "Restaurante")),
                "comuna": clean_text(find_value(row, "Comuna")),
                "canal": canal,
                "accion": accion,
                "estado_crm_actual": clean_text(find_value(row, "Estado CRM actual")),
                "resultado_seguimiento_actual": clean_text(find_value(row, "Resultado seguimiento actual")),
                "mensaje_enviado": mensaje,
            }
        )
    return dedupe(records, "event_key")


def build_mensajes_whatsapp() -> list[dict[str, Any]]:
    if not MESSAGES_JSON.exists():
        return []
    data = json.loads(MESSAGES_JSON.read_text(encoding="utf-8-sig"))
    records = []
    for idx, codigo in enumerate(sorted(data, key=lambda value: int(value) if str(value).isdigit() else str(value)), start=1):
        item = data[codigo]
        records.append(
            {
                "codigo": str(codigo),
                "texto": clean_text(item.get("text", "")),
                "activo": bool(item.get("active", True)),
                "orden": idx,
            }
        )
    return dedupe(records, "codigo")


def dedupe(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for record in records:
        value = clean_text(record.get(key))
        if value:
            seen[value] = record
    return list(seen.values())


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: json_safe(value) for key, value in record.items() if value is not None}


def upload(client, table: str, records: list[dict[str, Any]], conflict_key: str, batch_size: int = 100) -> int:
    total = 0
    for start in range(0, len(records), batch_size):
        batch = [clean_record(record) for record in records[start : start + batch_size]]
        if not batch:
            continue
        client.table(table).upsert(batch, on_conflict=conflict_key).execute()
        total += len(batch)
    return total


def print_summary(name: str, records: list[dict[str, Any]]) -> None:
    print(f"{name}: {len(records)} registros preparados")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar datos locales a Supabase en modo seguro.")
    parser.add_argument("--execute", action="store_true", help="Inserta/upsertea datos en Supabase. Sin esto solo hace dry-run.")
    args = parser.parse_args()

    datasets = {
        "restaurantes": (build_restaurantes(), "crm_id"),
        "crm_estado": (build_crm_estado(), "crm_id"),
        "historial_contactos": (build_historial_contactos(), "event_key"),
        "mensajes_whatsapp": (build_mensajes_whatsapp(), "codigo"),
    }

    print("Migracion Supabase")
    print("Modo:", "EXECUTE" if args.execute else "DRY-RUN")
    for table, (records, _) in datasets.items():
        print_summary(table, records)

    if not args.execute:
        print("Dry-run completado. No se inserto nada.")
        print("Para migrar realmente, ejecuta con --execute.")
        return 0

    try:
        client = get_supabase_client()
    except SupabaseConfigError as exc:
        print(f"Error de configuracion Supabase: {exc}")
        return 2

    for table, (records, conflict_key) in datasets.items():
        inserted = upload(client, table, records, conflict_key)
        print(f"{table}: upsert completado ({inserted})")

    print("Migracion Supabase completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
