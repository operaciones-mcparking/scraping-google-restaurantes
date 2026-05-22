from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase_client import SupabaseConfigError, test_supabase_connection


def main() -> int:
    try:
        result = test_supabase_connection()
    except SupabaseConfigError as exc:
        print(f"Error de configuración: {exc}")
        return 2
    except Exception as exc:
        print(f"Error conectando a Supabase: {exc}")
        return 1

    if result.get("ok"):
        print("Conexión Supabase OK")
        print(f"Status HTTP: {result.get('status')}")
        return 0

    print("Error conectando a Supabase: respuesta no OK")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
