from __future__ import annotations

import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any

import streamlit as st
from supabase import Client, create_client

from supabase_client import SupabaseConfigError, load_supabase_secrets, normalize_supabase_url


AUTH_COOKIE_NAME = "rappi_leads_auth"
AUTH_COOKIE_DAYS = 30
AUTH_REFRESH_MARGIN_SECONDS = 90
AUTH_COOKIE_VERSION = 1


class AuthError(RuntimeError):
    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


def _remember_auth_error(exc: Exception | str) -> None:
    if isinstance(exc, AuthError):
        st.session_state["auth_last_error"] = exc.message
        if exc.detail:
            st.session_state["auth_last_error_detail"] = exc.detail
        else:
            st.session_state.pop("auth_last_error_detail", None)
        return
    st.session_state["auth_last_error"] = str(exc)
    st.session_state.pop("auth_last_error_detail", None)


def last_auth_error() -> str:
    return str(st.session_state.get("auth_last_error", "") or "")


def last_auth_error_detail() -> str:
    return str(st.session_state.get("auth_last_error_detail", "") or "")


def clear_auth_error() -> None:
    st.session_state.pop("auth_last_error", None)
    st.session_state.pop("auth_last_error_detail", None)


def cookie_manager() -> object | None:
    try:
        from streamlit_cookies_controller import CookieController

        return CookieController()
    except Exception:
        pass

    try:
        import extra_streamlit_components as stx

        return stx.CookieManager()
    except Exception:
        return None


def _cookie_get(manager: object, name: str) -> str:
    if hasattr(manager, "get"):
        value = manager.get(name)
        return str(value or "")
    if hasattr(manager, "getAll"):
        cookies = manager.getAll() or {}
        return str(cookies.get(name, "") if isinstance(cookies, dict) else "")
    if hasattr(manager, "get_all"):
        cookies = manager.get_all() or {}
        return str(cookies.get(name, "") if isinstance(cookies, dict) else "")
    return ""


def _cookie_set(manager: object, name: str, value: str) -> None:
    expires_at = datetime.now() + timedelta(days=AUTH_COOKIE_DAYS)
    if hasattr(manager, "set"):
        try:
            manager.set(name, value, max_age=AUTH_COOKIE_DAYS * 24 * 60 * 60)
            return
        except TypeError:
            pass
        try:
            manager.set(name, value, expires_at=expires_at)
            return
        except TypeError:
            manager.set(name, value)
            return
    if hasattr(manager, "__setitem__"):
        manager[name] = value
        if hasattr(manager, "save"):
            manager.save()


def _cookie_delete(manager: object, name: str) -> None:
    if hasattr(manager, "remove"):
        manager.remove(name)
        return
    if hasattr(manager, "delete"):
        manager.delete(name)
        return
    if hasattr(manager, "set"):
        try:
            manager.set(name, "", max_age=0)
        except TypeError:
            try:
                manager.set(name, "", expires_at=datetime.now() - timedelta(days=1))
            except TypeError:
                manager.set(name, "")


def _exception_text(exc: Exception) -> str:
    chunks = [str(exc)]
    for attr in ("message", "error_description", "description", "details"):
        value = getattr(exc, attr, "")
        if value:
            chunks.append(str(value))
    return " | ".join(dict.fromkeys(chunk for chunk in chunks if chunk)).strip()


def _classify_auth_exception(exc: Exception, fallback: str) -> AuthError:
    detail = _exception_text(exc)
    lowered = detail.lower()
    if any(text in lowered for text in ["email not confirmed", "not confirmed", "confirm"]):
        return AuthError("El usuario existe, pero el correo aún no está confirmado en Supabase.", detail)
    if any(text in lowered for text in ["invalid login credentials", "invalid credentials", "invalid_grant"]):
        return AuthError("Correo electrónico o contraseña incorrectos.", detail)
    if any(text in lowered for text in ["api key", "jwt", "invalid key", "invalid api", "unauthorized", "forbidden"]):
        return AuthError("Supabase rechazó las credenciales de configuración. Revisa SUPABASE_URL y SUPABASE_KEY.", detail)
    if any(text in lowered for text in ["timeout", "connection", "network", "temporarily", "failed to establish"]):
        return AuthError("Supabase no responde o hay un problema de conexión. Intenta nuevamente en unos segundos.", detail)
    return AuthError(fallback, detail)


def auth_config() -> tuple[str, str]:
    """Return Supabase URL/key for Auth, preferring Streamlit secrets."""
    try:
        url = str(st.secrets.get("SUPABASE_URL", "")).strip()
        key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
    except Exception:
        url = ""
        key = ""

    if url and key:
        return normalize_supabase_url(url), key

    try:
        secrets = load_supabase_secrets()
    except SupabaseConfigError as exc:
        raise AuthError("Falta configurar SUPABASE_URL y SUPABASE_KEY en Streamlit secrets.", str(exc)) from exc

    return secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"]


def auth_client() -> Client:
    supabase_url, supabase_key = auth_config()
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as exc:
        raise _classify_auth_exception(exc, "No se pudo crear el cliente de Supabase Auth.") from exc


def _session_value(session: object, name: str, default: object = "") -> object:
    return getattr(session, name, default) if session else default


def _user_value(user: object, name: str, default: str = "") -> str:
    return str(getattr(user, name, default) or default)


def _session_payload() -> dict[str, object]:
    return {
        "access_token": str(st.session_state.get("auth_access_token", "") or ""),
        "refresh_token": str(st.session_state.get("auth_refresh_token", "") or ""),
        "user_email": str(st.session_state.get("auth_user_email", "") or ""),
        "user_id": str(st.session_state.get("auth_user_id", "") or ""),
        "expires_at": st.session_state.get("auth_expires_at", "") or "",
    }


def _cookie_secret() -> str:
    try:
        _, key = auth_config()
    except Exception:
        key = ""
    return key or "rappi-leads-crm-cookie"


def _sign_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(_cookie_secret().encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_cookie_payload(payload: dict[str, object]) -> str:
    return json.dumps({"v": AUTH_COOKIE_VERSION, "payload": payload, "sig": _sign_payload(payload)}, separators=(",", ":"))


def _decode_cookie_payload(value: str) -> dict[str, object]:
    raw = json.loads(value)
    if not isinstance(raw, dict):
        return {}
    payload = raw.get("payload")
    signature = str(raw.get("sig", "") or "")
    if isinstance(payload, dict) and signature and hmac.compare_digest(signature, _sign_payload(payload)):
        return payload
    if {"access_token", "refresh_token"}.issubset(raw.keys()):
        return raw
    return {}


def _save_session_cookie() -> None:
    manager = cookie_manager()
    if manager is None:
        _remember_auth_error("No se pudo inicializar el componente de cookies persistentes.")
        return
    payload = _session_payload()
    if not payload["access_token"] or not payload["refresh_token"]:
        return
    try:
        _cookie_set(manager, AUTH_COOKIE_NAME, _encode_cookie_payload(payload))
    except Exception as exc:
        _remember_auth_error(AuthError("No se pudo guardar la sesión persistente en cookies.", _exception_text(exc)))


def _read_session_cookie() -> dict[str, object]:
    manager = cookie_manager()
    if manager is None:
        return {}
    try:
        value = _cookie_get(manager, AUTH_COOKIE_NAME)
        if not value:
            return {}
        return _decode_cookie_payload(value)
    except Exception as exc:
        _remember_auth_error(AuthError("No se pudo leer la cookie de sesión.", _exception_text(exc)))
        return {}


def _delete_session_cookie() -> None:
    manager = cookie_manager()
    if manager is None:
        return
    try:
        _cookie_delete(manager, AUTH_COOKIE_NAME)
    except Exception:
        pass


def _store_session(session: object, user: object | None = None, remember_session: bool | None = None) -> bool:
    access_token = str(_session_value(session, "access_token", "") or "")
    refresh_token = str(_session_value(session, "refresh_token", "") or "")
    expires_at = _session_value(session, "expires_at", None)
    expires_in = _session_value(session, "expires_in", None)

    if not access_token or not refresh_token:
        _remember_auth_error("Supabase autenticó, pero no devolvió una sesión válida.")
        return False

    if expires_at in ("", None) and expires_in not in ("", None):
        try:
            expires_at = int(time.time()) + int(expires_in)
        except (TypeError, ValueError):
            expires_at = None

    st.session_state["authenticated"] = True
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_expires_at"] = expires_at or ""
    if remember_session is not None:
        st.session_state["auth_remember_session"] = bool(remember_session)

    if user is not None:
        st.session_state["auth_user_email"] = _user_value(user, "email")
        st.session_state["auth_user_id"] = _user_value(user, "id")

    st.session_state.pop("login_password", None)
    if st.session_state.get("auth_remember_session", False):
        _save_session_cookie()
    else:
        _delete_session_cookie()
    clear_auth_error()
    return True


def _session_expired() -> bool:
    expires_at = st.session_state.get("auth_expires_at", "")
    if not expires_at:
        return False
    try:
        return int(float(expires_at)) <= int(time.time()) + AUTH_REFRESH_MARGIN_SECONDS
    except (TypeError, ValueError):
        return False


def _clear_session_state() -> None:
    st.session_state["authenticated"] = False
    for key in [
        "auth_user_email",
        "auth_user_id",
        "auth_access_token",
        "auth_refresh_token",
        "auth_expires_at",
        "auth_remember_session",
        "login_email",
        "login_password",
        "login_remember_session",
    ]:
        st.session_state.pop(key, None)


def _apply_cookie_payload(payload: dict[str, Any]) -> bool:
    access_token = str(payload.get("access_token", "") or "")
    refresh_token = str(payload.get("refresh_token", "") or "")
    if not access_token or not refresh_token:
        return False
    st.session_state["authenticated"] = True
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    st.session_state["auth_user_email"] = str(payload.get("user_email", "") or "")
    st.session_state["auth_user_id"] = str(payload.get("user_id", "") or "")
    st.session_state["auth_expires_at"] = payload.get("expires_at", "") or ""
    st.session_state["auth_remember_session"] = True
    return True


def restore_session_from_cookie() -> bool:
    payload = _read_session_cookie()
    if not _apply_cookie_payload(payload):
        return False

    if validate_current_session():
        return True
    _delete_session_cookie()
    return False


def refresh_current_session() -> bool:
    refresh_token = str(st.session_state.get("auth_refresh_token", "") or "")
    if not refresh_token:
        _clear_session_state()
        return False
    try:
        response = auth_client().auth.refresh_session(refresh_token)
    except Exception as exc:
        _remember_auth_error(_classify_auth_exception(exc, "No se pudo renovar la sesión de Supabase."))
        _clear_session_state()
        return False
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if not _store_session(session, user):
        _clear_session_state()
        return False
    return True


def validate_current_session() -> bool:
    access_token = str(st.session_state.get("auth_access_token", "") or "")
    refresh_token = str(st.session_state.get("auth_refresh_token", "") or "")
    if not access_token:
        if refresh_token:
            return refresh_current_session()
        _clear_session_state()
        return False

    if _session_expired():
        return refresh_current_session()

    try:
        client = auth_client()
        client.auth.set_session(access_token, refresh_token)
        response = client.auth.get_user(access_token)
    except Exception:
        return refresh_current_session()

    user = getattr(response, "user", None)
    if user is None:
        return refresh_current_session()

    st.session_state["authenticated"] = True
    st.session_state["auth_user_email"] = _user_value(user, "email", current_user_email())
    st.session_state["auth_user_id"] = _user_value(user, "id", str(st.session_state.get("auth_user_id", "")))
    if st.session_state.get("auth_remember_session", False):
        _save_session_cookie()
    return True


def is_authenticated() -> bool:
    if not st.session_state.get("authenticated", False) or not st.session_state.get("auth_access_token"):
        return restore_session_from_cookie()
    return validate_current_session()


def current_user_email() -> str:
    return str(st.session_state.get("auth_user_email", "")).strip()


def login(email: str, password: str, remember_session: bool = False) -> bool:
    clear_auth_error()
    email = str(email).strip().lower()
    password = str(password)
    if not email or not password:
        _remember_auth_error("Ingresa correo electrónico y contraseña.")
        return False

    try:
        client = auth_client()
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except AuthError as exc:
        _remember_auth_error(exc)
        return False
    except Exception as exc:
        _remember_auth_error(_classify_auth_exception(exc, "No se pudo iniciar sesión con Supabase."))
        return False

    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if user is not None:
        st.session_state["auth_user_email"] = _user_value(user, "email", email)
        st.session_state["auth_user_id"] = _user_value(user, "id")
    return _store_session(session, user, remember_session=remember_session)


def logout() -> None:
    access_token = str(st.session_state.get("auth_access_token", "") or "")
    refresh_token = str(st.session_state.get("auth_refresh_token", "") or "")
    if access_token and refresh_token:
        try:
            client = auth_client()
            client.auth.set_session(access_token, refresh_token)
            client.auth.sign_out()
        except Exception:
            pass
    _clear_session_state()
    _delete_session_cookie()
    clear_auth_error()
