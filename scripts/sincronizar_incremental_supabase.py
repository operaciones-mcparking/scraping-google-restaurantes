import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import SupabaseConfigError, get_supabase_client, get_supabase_service_client, jwt_role


DEFAULT_CONFIG = ROOT / "configs" / "actualizacion_incremental_manual.json"


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def display_normalized_name(value: Any) -> str:
    text = clean_text(value)
    return re.sub(r"\s+", " ", text).strip()


def infer_tipo_negocio(row: dict[str, Any]) -> str:
    category = norm_text(find_value(row, "Categoria", "Categoría"))
    name = norm_text(find_value(row, "Nombre restaurante"))
    text = f"{category} {name}".strip()
    if any(token in text for token in ["bar", "pub", "cerveceria"]):
        return "Bar/Pub"
    if any(token in text for token in ["cafe", "cafeteria", "bakery", "pasteleria", "heladeria", "salon de te"]):
        return "Cafetería"
    if any(token in text for token in ["fast", "hamburg", "burger", "pizza", "sandwich", "shawarma", "empanad", "completo", "food truck"]):
        return "Fast Food"
    if any(token in text for token in ["restaurant", "restaurante", "marisqueria", "parrilla", "sushi", "peruano", "italiano", "chino", "indio", "cocina"]):
        return "Restaurante"
    return "Otro"


def infer_score_comercial(row: dict[str, Any], tipo_negocio: str) -> float | None:
    rating = parse_number(find_value(row, "Rating"))
    reviews = parse_int(find_value(row, "Cantidad reviews"))
    if rating is None and reviews is None:
        return None
    rating_score = min(max((rating or 0) * 12, 0), 60)
    reviews_value = reviews or 0
    if reviews_value >= 500:
        reviews_score = 25
    elif reviews_value >= 200:
        reviews_score = 20
    elif reviews_value >= 100:
        reviews_score = 16
    elif reviews_value >= 50:
        reviews_score = 12
    elif reviews_value >= 20:
        reviews_score = 8
    elif reviews_value > 0:
        reviews_score = 4
    else:
        reviews_score = 0
    type_bonus = {"Restaurante": 5, "Bar/Pub": 5, "Fast Food": 0, "Cafetería": 0, "Otro": -5}.get(tipo_negocio, 0)
    return float(max(0, min(90, round(rating_score + reviews_score + type_bonus))))


def infer_nivel_comercial(score: float | None, tipo_negocio: str) -> str:
    if score is None:
        return ""
    if score >= 78 and tipo_negocio != "Cafetería":
        return "Alto potencial"
    if score >= 60:
        return "Medio potencial"
    return "Bajo potencial"


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


def find_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return ""


def lead_key(row: dict[str, Any]) -> str:
    maps = clean_text(find_value(row, "Google Maps URL"))
    if maps:
        return maps
    name = norm_text(find_value(row, "Nombre normalizado", "Nombre restaurante"))
    address = norm_text(find_value(row, "Direccion", "Dirección"))
    comuna = norm_text(find_value(row, "Comuna"))
    fallback = "|".join([name, address, comuna]).strip("|")
    if fallback:
        return fallback
    lat = norm_coord(find_value(row, "Latitud"))
    lng = norm_coord(find_value(row, "Longitud"))
    return "|".join([name, lat, lng]).strip("|")


def key_parts(row: dict[str, Any]) -> dict[str, str]:
    url = clean_text(find_value(row, "Google Maps URL"))
    name = norm_text(find_value(row, "Nombre normalizado", "Nombre restaurante"))
    address = norm_text(find_value(row, "Direccion", "Dirección"))
    comuna = norm_text(find_value(row, "Comuna"))
    lat = norm_coord(find_value(row, "Latitud"))
    lng = norm_coord(find_value(row, "Longitud"))
    key1 = f"url::{url}" if url else ""
    key2 = f"name_address_comuna::{name}|{address}|{comuna}" if name and address and comuna else ""
    key3 = f"name_lat_lng::{name}|{lat}|{lng}" if name and lat and lng else ""
    return {"key1": key1, "key2": key2, "key3": key3, "selected": key1 or key2 or key3 or lead_key(row)}


def row_to_json(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): json_safe(value) for key, value in row.items()}


def sqlite_rows(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = []
    for item in conn.execute("SELECT data_json, fecha_insertado FROM restaurantes ORDER BY id"):
        data = json.loads(item["data_json"])
        data["_fecha_insertado_sqlite"] = item["fecha_insertado"]
        rows.append(data)
    conn.close()
    return rows


def restaurant_record(row: dict[str, Any]) -> dict[str, Any]:
    crm_id = lead_key(row)
    keys = key_parts(row)
    tipo_negocio = clean_text(find_value(row, "Tipo negocio")) or infer_tipo_negocio(row)
    score_comercial = parse_number(find_value(row, "Score comercial"))
    if score_comercial is None:
        score_comercial = infer_score_comercial(row, tipo_negocio)
    nivel_comercial = clean_text(find_value(row, "Nivel comercial")) or infer_nivel_comercial(score_comercial, tipo_negocio)
    return {
        "crm_id": crm_id,
        "unique_key": keys["selected"],
        "key_google_maps_url": keys["key1"],
        "key_nombre_direccion_comuna": keys["key2"],
        "key_nombre_lat_lng": keys["key3"],
        "nombre_restaurante": clean_text(find_value(row, "Nombre restaurante")),
        "nombre_normalizado": clean_text(find_value(row, "Nombre normalizado")) or display_normalized_name(find_value(row, "Nombre restaurante")),
        "rating": parse_number(find_value(row, "Rating")),
        "cantidad_reviews": parse_int(find_value(row, "Cantidad reviews")),
        "direccion": clean_text(find_value(row, "Direccion", "Dirección")),
        "telefono": clean_text(find_value(row, "Telefono", "Teléfono")),
        "sitio_web": clean_text(find_value(row, "Sitio web")),
        "categoria": clean_text(find_value(row, "Categoria", "Categoría")),
        "google_maps_url": clean_text(find_value(row, "Google Maps URL")),
        "latitud": parse_number(find_value(row, "Latitud")),
        "longitud": parse_number(find_value(row, "Longitud")),
        "comuna": clean_text(find_value(row, "Comuna")),
        "region": clean_text(find_value(row, "Region", "Región")),
        "pais": clean_text(find_value(row, "Pais", "País")),
        "fuente": clean_text(find_value(row, "Fuente")),
        "fecha_extraccion": parse_datetime(find_value(row, "Fecha extracción", "Fecha extraccion")),
        "fecha_carga": parse_datetime(find_value(row, "Fecha carga", "Fecha extracción", "Fecha extraccion")) or parse_datetime(row.get("_fecha_insertado_sqlite")),
        "calidad_dato": clean_text(find_value(row, "Calidad dato")),
        "es_restaurante_valido": clean_text(find_value(row, "Es restaurante válido", "Es restaurante valido")),
        "instagram_url": clean_text(find_value(row, "Instagram URL")),
        "instagram_usuario": clean_text(find_value(row, "Instagram Usuario")),
        "facebook_url": clean_text(find_value(row, "Facebook URL")),
        "tiktok_url": clean_text(find_value(row, "TikTok URL")),
        "tiene_redes": clean_text(find_value(row, "Tiene Redes")),
        "calidad_redes": clean_text(find_value(row, "Calidad Redes")),
        "observaciones": clean_text(find_value(row, "Observaciones")),
        "tipo_negocio": tipo_negocio,
        "score_comercial": score_comercial,
        "nivel_comercial": nivel_comercial,
        "estado_revision_rappi": clean_text(find_value(row, "Estado revision Rappi", "Estado revisión Rappi")) or "No revisado",
        "fecha_revision_rappi": parse_datetime(find_value(row, "Fecha revision Rappi", "Fecha revisión Rappi")),
        "url_rappi": clean_text(find_value(row, "URL Rappi")),
        "observacion_revision_rappi": clean_text(find_value(row, "Observacion revision Rappi", "Observación revision Rappi")),
        "data_json": row_to_json({key: value for key, value in row.items() if not str(key).startswith("_")}),
    }


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: json_safe(value) for key, value in record.items() if value is not None}


def existing_supabase_keys(client) -> tuple[set[str], set[str], int]:
    response = client.table("restaurantes").select("crm_id,google_maps_url").execute()
    rows = response.data or []
    crm_ids = {clean_text(row.get("crm_id")) for row in rows if clean_text(row.get("crm_id"))}
    urls = {clean_text(row.get("google_maps_url")) for row in rows if clean_text(row.get("google_maps_url"))}
    return crm_ids, urls, len(rows)


def event_key(crm_id: str, fecha_hora: str, accion: str, mensaje: str) -> str:
    raw = "|".join([crm_id, fecha_hora, "Sistema", accion, mensaje])
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def upload_batch(client, table: str, records: list[dict[str, Any]], conflict_key: str, batch_size: int = 100) -> int:
    total = 0
    for start in range(0, len(records), batch_size):
        batch = [clean_record(record) for record in records[start : start + batch_size]]
        if batch:
            client.table(table).upsert(batch, on_conflict=conflict_key).execute()
            total += len(batch)
    return total


def sync(config: dict, dry_run: bool = False) -> dict:
    summary = {
        "modo_prueba": bool(dry_run),
        "registros_locales": 0,
        "existentes_supabase": 0,
        "nuevos_supabase": 0,
        "insertados_supabase": 0,
        "crm_estado_creados": 0,
        "eventos_iniciales_creados": 0,
        "duplicados_supabase": 0,
        "errores_supabase": 0,
        "credencial": "",
        "ultimos_restaurantes_nuevos": [],
    }
    rows = sqlite_rows(project_path(config["baseDatos"]))
    summary["registros_locales"] = len(rows)
    if not rows:
        return summary

    try:
        client = get_supabase_service_client()
        summary["credencial"] = "service_role"
    except SupabaseConfigError as exc:
        if not dry_run:
            summary["errores_supabase"] = 1
            summary["motivo_abortado"] = str(exc)
            summary["error"] = str(exc)
            return summary

        try:
            client = get_supabase_client()
            summary["credencial"] = f"lectura_{jwt_role(load_supabase_key_for_role_check()) or 'desconocida'}"
        except SupabaseConfigError as read_exc:
            summary["errores_supabase"] = 1
            summary["motivo_abortado"] = f"No se pudo configurar cliente de lectura: {read_exc}"
            summary["error"] = summary["motivo_abortado"]
            return summary

    try:
        existing_ids, existing_urls, existing_count = existing_supabase_keys(client)
        summary["existentes_supabase"] = existing_count
    except Exception as exc:
        summary["errores_supabase"] = 1
        summary["motivo_abortado"] = f"No se pudieron leer existentes en Supabase. No se asumen nuevos para evitar duplicados: {exc}"
        summary["error"] = summary["motivo_abortado"]
        return summary

    restaurants = []
    crm_rows = []
    history_rows = []
    for row in rows:
        record = restaurant_record(row)
        crm_id = clean_text(record.get("crm_id"))
        google_url = clean_text(record.get("google_maps_url"))
        if not crm_id:
            summary["errores_supabase"] += 1
            continue
        if crm_id in existing_ids or (google_url and google_url in existing_urls):
            summary["duplicados_supabase"] += 1
            continue
        fecha = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        restaurants.append(record)
        summary["ultimos_restaurantes_nuevos"].append(
            {
                "nombre_restaurante": record.get("nombre_restaurante", ""),
                "comuna": record.get("comuna", ""),
                "tipo_negocio": record.get("tipo_negocio", ""),
                "nivel_comercial": record.get("nivel_comercial", ""),
                "telefono": record.get("telefono", ""),
                "rating": record.get("rating"),
                "reviews": record.get("reviews"),
                "fecha_detectado": fecha,
                "fecha_sincronizado": fecha,
                "sincronizado_supabase": not dry_run,
                "crm_id": crm_id,
                "google_maps_url": record.get("google_maps_url", ""),
            }
        )
        crm_rows.append(
            {
                "crm_id": crm_id,
                "estado_crm": "Nuevo",
                "resultado_seguimiento": "Sin respuesta",
                "estado_whatsapp": "No contactado",
                "canal_ultimo_contacto": None,
                "fecha_ultimo_contacto": None,
                "fecha_ultimo_whatsapp": None,
                "mensaje_enviado": None,
                "observacion_crm": "",
            }
        )
        history_rows.append(
            {
                "event_key": event_key(crm_id, clean_text(fecha), "Restaurante agregado", "Lead ingresado a la base"),
                "crm_id": crm_id,
                "fecha_hora": fecha,
                "restaurante": record.get("nombre_restaurante", ""),
                "comuna": record.get("comuna", ""),
                "canal": "Sistema",
                "accion": "Restaurante agregado",
                "estado_crm_actual": "Nuevo",
                "resultado_seguimiento_actual": "Sin respuesta",
                "mensaje_enviado": "Lead ingresado a la base",
            }
        )
        existing_ids.add(crm_id)
        if google_url:
            existing_urls.add(google_url)

    summary["nuevos_supabase"] = len(restaurants)
    summary["crm_estado_creados"] = len(crm_rows)
    summary["eventos_iniciales_creados"] = len(history_rows)
    if dry_run or not restaurants:
        return summary

    try:
        summary["insertados_supabase"] = upload_batch(client, "restaurantes", restaurants, "crm_id")
        upload_batch(client, "crm_estado", crm_rows, "crm_id")
        upload_batch(client, "historial_contactos", history_rows, "event_key")
    except Exception as exc:
        summary["errores_supabase"] += 1
        summary["error"] = str(exc)
    return summary


def load_supabase_key_for_role_check() -> str:
    from supabase_client import load_supabase_secrets

    secrets = load_supabase_secrets()
    return secrets.get("SUPABASE_KEY", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincronizar nuevos restaurantes locales hacia Supabase.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry-run", action="store_true", help="Calcula lo que subiria sin insertar en Supabase.")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    summary = sync(config, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary.get("error") else 2


if __name__ == "__main__":
    raise SystemExit(main())
