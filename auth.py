from __future__ import annotations

import time

import streamlit as st
from supabase import create_client
from supabase import Client

from supabase_client import SupabaseConfigError, load_supabase_secrets, normalize_supabase_url


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
    if not st.session_state.get("authenticated", False):
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
