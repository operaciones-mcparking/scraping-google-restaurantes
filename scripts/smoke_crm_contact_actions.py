from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_crm_restaurantes as app  # noqa: E402


class FakeCacheData:
    def clear(self) -> None:
        return None


class FakeSt:
    cache_data = FakeCacheData()
    session_state: dict[str, object] = {}


def make_crm_row(crm_id: str = "crm-test") -> dict[str, str]:
    row = {field: "" for field in app.CRM_FIELDS}
    row.update(
        {
            "CRM ID": crm_id,
            "Estado CRM": "Nuevo",
            "Estado WhatsApp": "No contactado",
            "Resultado seguimiento": "Sin respuesta",
        }
    )
    return row


def install_common_mocks(mode: str, crm_row: dict[str, str]) -> dict[str, object]:
    action_col = app.CONTACT_HISTORY_FIELDS[5]
    state: dict[str, object] = {
        "crm": pd.DataFrame([crm_row], columns=["CRM ID"] + app.CRM_FIELDS),
        "history": pd.DataFrame(columns=app.CONTACT_HISTORY_FIELDS),
        "supabase_events": [],
    }

    app.st = FakeSt()
    app.get_data_mode = lambda: mode
    app.refresh_crm_after_action = lambda: None
    app.crm_event_context = lambda crm_id, fallback_name="": {
        "Restaurante": fallback_name or "Restaurante Demo",
        "Comuna": "Las Condes",
    }
    app.load_crm_state = lambda: state["crm"].copy()

    def save_crm_state(df: pd.DataFrame) -> None:
        state["crm"] = app.normalize_crm_columns(df)[["CRM ID"] + app.CRM_FIELDS].copy()

    def save_crm_estado(records) -> int:
        if isinstance(records, pd.DataFrame):
            rows = app.normalize_crm_columns(records)[["CRM ID"] + app.CRM_FIELDS].to_dict(orient="records")
        elif isinstance(records, dict):
            rows = [records]
        else:
            rows = list(records)
        current = state["crm"].copy()
        for row in rows:
            crm_id = str(row.get("CRM ID", "")).strip()
            if not crm_id:
                continue
            current = current[current["CRM ID"].fillna("").astype(str) != crm_id]
            normalized = app.normalize_crm_columns(pd.DataFrame([row]))[["CRM ID"] + app.CRM_FIELDS]
            current = pd.concat([current, normalized], ignore_index=True)
        state["crm"] = current
        return len(rows)

    app.save_crm_state = save_crm_state
    app.ds_save_crm_estado = save_crm_estado
    app.load_contact_history = lambda: state["history"].copy()
    app.save_contact_history = lambda df: state.update({"history": app.normalize_contact_history_columns(df)})
    app.ds_save_whatsapp_event = lambda crm_id, restaurant, comuna, message, fecha_hora=None: state["supabase_events"].append(
        {
            "CRM ID": crm_id,
            "Canal": "WhatsApp",
            action_col: "WhatsApp abierto",
            "Mensaje enviado": message,
            "Fecha/hora": fecha_hora,
        }
    )
    app.ds_save_call_event = lambda crm_id, restaurant, comuna, fecha_hora=None: state["supabase_events"].append(
        {
            "CRM ID": crm_id,
            "Canal": "Llamada",
            action_col: "Llamada iniciada",
            "Mensaje enviado": "Llamada iniciada desde CRM",
            "Fecha/hora": fecha_hora,
        }
    )
    app.ds_insert_historial_evento = lambda event: state["supabase_events"].append(event)
    app.log_performance_event = lambda *args, **kwargs: None
    return state


def assert_whatsapp_state(state: dict[str, object]) -> None:
    row = state["crm"].iloc[0].to_dict()
    assert row["Estado CRM"] == "Contactado"
    assert row["Estado WhatsApp"] == "Contactado manualmente"
    assert row["Resultado seguimiento"] == "Sin respuesta"
    assert row["Canal ultimo contacto"] == "WhatsApp"
    assert row["Fecha ultimo contacto"]
    assert row["Fecha ultimo WhatsApp"]
    assert row["Fecha envio WhatsApp"]
    assert row["Mensaje enviado"] == "Mensaje exacto"


def assert_call_state(state: dict[str, object]) -> None:
    row = state["crm"].iloc[0].to_dict()
    assert row["Estado CRM"] == "Contactado"
    assert row["Resultado seguimiento"] == "Sin respuesta"
    assert row["Canal ultimo contacto"] == "Llamada"
    assert row["Fecha ultimo contacto"]
    assert row["Estado WhatsApp"] == "No contactado"
    assert not row["Fecha ultimo WhatsApp"]
    assert not row["Fecha envio WhatsApp"]
    assert not row["Mensaje enviado"]


def test_local_whatsapp() -> None:
    state = install_common_mocks("local", make_crm_row())
    app.mark_whatsapp_contacted("crm-test", "Mensaje exacto", "1", "Restaurante Demo")
    assert_whatsapp_state(state)
    history = state["history"]
    action_col = app.CONTACT_HISTORY_FIELDS[5]
    assert set(history[action_col]) == {"WhatsApp abierto", "Estado CRM cambiado"}
    assert "Mensaje exacto" in set(history["Mensaje enviado"])


def test_local_call() -> None:
    state = install_common_mocks("local", make_crm_row())
    app.mark_call_contacted("crm-test", "Restaurante Demo")
    assert_call_state(state)
    history = state["history"]
    action_col = app.CONTACT_HISTORY_FIELDS[5]
    assert set(history[action_col]) == {"Llamada iniciada", "Estado CRM cambiado"}
    assert "Llamada iniciada desde CRM" in set(history["Mensaje enviado"])


def test_supabase_whatsapp() -> None:
    state = install_common_mocks("supabase", make_crm_row())
    app.mark_whatsapp_contacted("crm-test", "Mensaje exacto", "1", "Restaurante Demo")
    assert_whatsapp_state(state)
    action_col = app.CONTACT_HISTORY_FIELDS[5]
    actions = [event.get(action_col) for event in state["supabase_events"]]
    assert "WhatsApp abierto" in actions
    assert "Estado CRM cambiado" in actions


def test_supabase_call() -> None:
    state = install_common_mocks("supabase", make_crm_row())
    app.mark_call_contacted("crm-test", "Restaurante Demo")
    assert_call_state(state)
    action_col = app.CONTACT_HISTORY_FIELDS[5]
    actions = [event.get(action_col) for event in state["supabase_events"]]
    assert "Llamada iniciada" in actions
    assert "Estado CRM cambiado" in actions


def test_estado_crm_widget_sync() -> None:
    app.st = FakeSt()
    app.st.session_state["lead_estado_crm-test"] = "Nuevo"
    key = app.sync_estado_crm_widget("crm-test", "Contactado")
    assert key == "lead_estado_crm-test"
    assert app.st.session_state[key] == "Contactado"


def main() -> None:
    tests = [
        test_local_whatsapp,
        test_local_call,
        test_supabase_whatsapp,
        test_supabase_call,
        test_estado_crm_widget_sync,
    ]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print("Smoke CRM contact actions OK")


if __name__ == "__main__":
    main()
