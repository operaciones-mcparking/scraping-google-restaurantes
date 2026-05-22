from __future__ import annotations

import time
import json
from datetime import datetime, timedelta

import streamlit as st
from supabase import create_client
from supabase import Client

from supabase_client import SupabaseConfigError, load_supabase_secrets, normalize_supabase_url


AUTH_COOKIE_NAME = "rappi_leads_auth"
AUTH_COOKIE_DAYS = 30


@st.cache_resource(show_spinner=False)
def cookie_manager():
    try:
        import extra_streamlit_components as stx
    except Exception:
        return None
    try:
        return stx.CookieManager()
    except Exception:
        return None


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
        raise RuntimeError("Falta configurar SUPABASE_URL y SUPABASE_KEY en Streamlit secrets.") from exc

    return secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"]


def auth_client() -> Client:
    supabase_url, supabase_key = auth_config()
    return create_client(supabase_url, supabase_key)


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


def _save_session_cookie() -> None:
    manager = cookie_manager()
    if manager is None:
        return
    payload = _session_payload()
    if not payload["access_token"] or not payload["refresh_token"]:
        return
    try:
        manager.set(
            AUTH_COOKIE_NAME,
            json.dumps(payload),
            expires_at=datetime.now() + timedelta(days=AUTH_COOKIE_DAYS),
        )
    except Exception:
        pass


def _read_session_cookie() -> dict[str, object]:
    manager = cookie_manager()
    if manager is None:
        return {}
    try:
        value = ""
        if hasattr(manager, "get"):
            value = manager.get(AUTH_COOKIE_NAME) or ""
        if not value and hasattr(manager, "get_all"):
            cookies = manager.get_all() or {}
            value = cookies.get(AUTH_COOKIE_NAME, "") if isinstance(cookies, dict) else ""
        if not value:
            return {}
        payload = json.loads(value)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _delete_session_cookie() -> None:
    manager = cookie_manager()
    if manager is None:
        return
    try:
        manager.delete(AUTH_COOKIE_NAME)
    except Exception:
        try:
            manager.set(AUTH_COOKIE_NAME, "", expires_at=datetime.now() - timedelta(days=1))
        except Exception:
            pass


def _store_session(session: object, user: object | None = None) -> bool:
    access_token = str(_session_value(session, "access_token", "") or "")
    refresh_token = str(_session_value(session, "refresh_token", "") or "")
    expires_at = _session_value(session, "expires_at", None)
    expires_in = _session_value(session, "expires_in", None)

    if not access_token:
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

    if user is not None:
        st.session_state["auth_user_email"] = _user_value(user, "email")
        st.session_state["auth_user_id"] = _user_value(user, "id")

    st.session_state.pop("login_password", None)
    _save_session_cookie()
    return True


def _session_expired() -> bool:
    expires_at = st.session_state.get("auth_expires_at", "")
    if not expires_at:
        return False
    try:
        return int(float(expires_at)) <= int(time.time()) + 60
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
        "login_email",
        "login_password",
    ]:
        st.session_state.pop(key, None)


def restore_session_from_cookie() -> bool:
    payload = _read_session_cookie()
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
    except Exception:
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
    return True


def is_authenticated() -> bool:
    if not st.session_state.get("authenticated", False) or not st.session_state.get("auth_access_token"):
        if restore_session_from_cookie():
            return True
        return False
    return validate_current_session()


def current_user_email() -> str:
    return str(st.session_state.get("auth_user_email", "")).strip()


def login(email: str, password: str) -> bool:
    supabase_url, supabase_key = auth_config()
    email = str(email).strip().lower()
    password = str(password)
    if not email or not password:
        return False

    client = create_client(supabase_url, supabase_key)
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        return False

    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if user is not None:
        st.session_state["auth_user_email"] = _user_value(user, "email", email)
        st.session_state["auth_user_id"] = _user_value(user, "id")
    return _store_session(session, user)


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
