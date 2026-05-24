from __future__ import annotations

import base64
import json
import os
import tomllib
from tomllib import TOMLDecodeError
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from supabase import Client, create_client


ROOT = Path(__file__).resolve().parent
DEFAULT_SECRETS = ROOT / ".streamlit" / "secrets.toml"
WINDOWS_TXT_SECRETS = ROOT / ".streamlit" / "secrets.toml.txt"


class SupabaseConfigError(RuntimeError):
    pass


def load_supabase_secrets(path: Path | None = None) -> dict[str, str]:
    secrets_path = path or DEFAULT_SECRETS
    if not secrets_path.exists():
        if path is None and WINDOWS_TXT_SECRETS.exists():
            secrets_path = WINDOWS_TXT_SECRETS
        else:
            raise SupabaseConfigError(f"No existe el archivo de secrets: {secrets_path}")

    try:
        with secrets_path.open("rb") as handle:
            data = tomllib.load(handle)
    except TOMLDecodeError:
        data = _load_simple_key_value_secrets(secrets_path)

    supabase_section = data.get("supabase", {})
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or data.get("SUPABASE_URL")
        or supabase_section.get("SUPABASE_URL")
    )
    anon_key = os.environ.get("SUPABASE_KEY") or data.get("SUPABASE_KEY") or supabase_section.get("SUPABASE_KEY")
    service_role_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or data.get("SUPABASE_SERVICE_ROLE_KEY")
        or supabase_section.get("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not url:
        raise SupabaseConfigError("Falta SUPABASE_URL en .streamlit/secrets.toml")
    if not anon_key and not service_role_key:
        raise SupabaseConfigError("Falta SUPABASE_KEY o SUPABASE_SERVICE_ROLE_KEY en .streamlit/secrets.toml")

    return {
        "SUPABASE_URL": normalize_supabase_url(str(url).strip()),
        "SUPABASE_KEY": str(anon_key or "").strip(),
        "SUPABASE_SERVICE_ROLE_KEY": str(service_role_key or "").strip(),
    }


def jwt_role(key: str) -> str | None:
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
        return decoded.get("role")
    except Exception:
        return None


def normalize_supabase_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _load_simple_key_value_secrets(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        data[key.strip()] = value
    return data


def get_supabase_client(path: Path | None = None) -> Client:
    secrets = load_supabase_secrets(path)
    if not secrets["SUPABASE_KEY"]:
        raise SupabaseConfigError("Falta SUPABASE_KEY para crear cliente de lectura Supabase.")
    return create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])


def get_supabase_service_client(path: Path | None = None) -> Client:
    secrets = load_supabase_secrets(path)
    key = secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise SupabaseConfigError("Falta SUPABASE_SERVICE_ROLE_KEY para escribir en Supabase con RLS activo.")
    role = jwt_role(key)
    if role and role != "service_role":
        raise SupabaseConfigError(
            f"SUPABASE_SERVICE_ROLE_KEY no tiene rol service_role; rol detectado: {role}."
        )
    return create_client(secrets["SUPABASE_URL"], key)


def test_supabase_connection(path: Path | None = None, timeout: int = 15) -> dict:
    secrets = load_supabase_secrets(path)
    client = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])

    request = Request(
        secrets["SUPABASE_URL"].rstrip("/") + "/auth/v1/settings",
        headers={
            "apikey": secrets["SUPABASE_KEY"],
            "Authorization": f"Bearer {secrets['SUPABASE_KEY']}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(512).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "client": client,
                "preview": _safe_json_preview(body),
            }
    except HTTPError as exc:
        detail = exc.read(512).decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase respondió con error HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"No se pudo conectar a Supabase: {exc.reason}") from exc


def _safe_json_preview(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text[:160]
    if isinstance(parsed, dict):
        keys = list(parsed.keys())[:8]
        return "Respuesta JSON con claves: " + ", ".join(keys)
    return "Respuesta JSON recibida"
