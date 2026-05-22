from __future__ import annotations

import base64
import hashlib
import html
import json
import random
import re
import subprocess
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlencode

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from auth import auth_config, current_user_email, is_authenticated, login, logout
from data_source import (
    get_data_mode,
    insert_historial_evento as ds_insert_historial_evento,
    load_crm_estado as ds_load_crm_estado,
    load_historial_contactos as ds_load_historial_contactos,
    load_mensajes as ds_load_mensajes,
    load_restaurantes as ds_load_restaurantes,
    clear_contact_history_for_leads as ds_clear_contact_history_for_leads,
    save_call_event as ds_save_call_event,
    save_crm_estado as ds_save_crm_estado,
    save_whatsapp_event as ds_save_whatsapp_event,
)


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "rappi_logo.png"
BASE_XLSX = ROOT / "data" / "base_restaurantes_actualizada.xlsx"
CRM_XLSX = ROOT / "data" / "crm_restaurantes_estado.xlsx"
CONTACT_HISTORY_XLSX = ROOT / "data" / "historial_contactos.xlsx"
MANUAL_CONFIG = ROOT / "configs" / "actualizacion_incremental_manual.json"
WHATSAPP_MESSAGES_CONFIG = ROOT / "configs" / "mensajes_whatsapp.json"
UI_RUN_CONFIG = ROOT / "configs" / "runs" / "actualizacion_incremental_crm_ui.json"
UPDATE_LOCK = ROOT / "data" / "logs" / "actualizacion_incremental_crm_ui.lock"
UI_LOG = ROOT / "data" / "logs" / "actualizacion_incremental_crm_ui.log"
UI_STDOUT_LOG = ROOT / "data" / "logs" / "actualizacion_incremental_crm_ui_stdout.log"
CRM_RESET_LOG = ROOT / "data" / "logs" / "crm_resets.log"
NODE_EXE = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"

CRM_FIELDS = [
    "Estado CRM",
    "Fecha ultimo contacto",
    "Canal ultimo contacto",
    "Responsable",
    "Observacion CRM",
    "Proxima accion",
    "Fecha proxima accion",
    "Fecha ultimo WhatsApp",
    "Mensaje WhatsApp sugerido",
    "Estado WhatsApp",
    "Variante mensaje",
    "Mensaje enviado",
    "Fecha envio WhatsApp",
    "Respondio",
    "Interesado",
    "Reunion agendada",
    "Resultado comercial",
    "Resultado seguimiento",
]

CONTACT_HISTORY_FIELDS = [
    "Fecha/hora",
    "CRM ID",
    "Restaurante",
    "Comuna",
    "Canal",
    "Acción",
    "Estado CRM actual",
    "Resultado seguimiento actual",
    "Mensaje enviado",
]

CRM_STATES = [
    "Nuevo",
    "Pendiente contacto",
    "Contactado",
]

PHONE_COLUMNS = [
    "Telefono",
    "Teléfono",
    "Teléfono",
    "Tel?fono",
    "Tel?fono",
    "Tel?fono",
]

ADDRESS_COLUMNS = ["Direccion", "Dirección", "Dirección", "Direcci?n"]

WHATSAPP_STATES = [
    "No contactado",
    "Link abierto",
    "Contactado manualmente",
    "Respondio",
    "No respondio",
]

RESULTADO_SEGUIMIENTO_OPTIONS = [
    "Sin respuesta",
    "No interesado",
    "Negociando",
    "Local cerrado",
    "Ya está en Rappi",
    "En proceso de firma",
]

RESULTADO_SEGUIMIENTO_LOOKUP = {
    re.sub(r"\s+", " ", value).strip().lower(): value for value in RESULTADO_SEGUIMIENTO_OPTIONS
}

DEFAULT_MESSAGE_VARIANTS = {
    "1": "Hola, ¿cómo estás? Te escribo porque encontré el restaurante {nombre} en {comuna} en Google y quería hacer una consulta comercial breve. ¿Con quién podría hablar?",
    "2": "Hola, ¿cómo estás? Vi el restaurante {nombre} en Google y quería consultar si actualmente están trabajando con plataformas de delivery.",
    "3": "Hola, ¿cómo estás? Vi que {nombre} aparece muy bien posicionado en Google y quería hacer una consulta comercial rápida. ¿Quién ve estos temas comerciales?",
    "4": "Hola, ¿cómo estás? Quería conversar brevemente con el encargado de {nombre} sobre una oportunidad comercial.",
    "5": "Hola, ¿cómo estás? Estoy contactando restaurantes de {comuna} y quería hacer una consulta rápida sobre {nombre}.",
    "6": "Hola, ¿cómo estás? Vi {nombre} en Google y quería saber con quién puedo hablar sobre temas comerciales.",
    "7": "Hola, ¿cómo estás? Quería hacer una consulta breve para {nombre}. ¿Me podrías orientar con la persona encargada?",
    "8": "Hola, ¿cómo estás? Vi que {nombre} tiene presencia en Google y quería hacer una consulta comercial corta.",
    "9": "Hola, ¿cómo estás? Te escribo por {nombre}; quería consultar si están evaluando nuevas opciones comerciales.",
    "10": "Hola, ¿cómo estás? Quería hablar con la persona encargada de alianzas o ventas de {nombre}.",
}

CONTACTED_STATES = ["Contactado"]
PENDING_STATES = ["Pendiente contacto"]

COMMERCIAL_TABLE_COLUMNS = [
    "Numero",
    "Nombre",
    "Comuna",
    "Tipo negocio",
    "Nivel comercial",
    "Score comercial",
    "Telefono",
    "WhatsApp disponible",
    "Instagram",
    "Estado CRM",
    "Resultado seguimiento",
    "Proxima accion",
]

SUMMARY_LABELS = {
    "totalAntes": "Base antes",
    "encontrados": "Encontrados",
    "insertados": "Nuevos agregados",
    "duplicados": "Duplicados ignorados",
    "errores": "Errores",
    "totalFinal": "Base final",
}


st.set_page_config(page_title="Rappi Leads CRM", layout="wide", initial_sidebar_state="collapsed")


fragment = st.fragment if hasattr(st, "fragment") else (lambda func: func)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --crm-rappi: #ff4f3d;
            --crm-rappi-dark: #db3325;
            --crm-rappi-soft: #fff1ee;
            --crm-green: #16a05d;
            --crm-green-dark: #137d4b;
            --crm-green-soft: #edf8f2;
            --crm-ink: #1f2933;
            --crm-muted: #68727d;
            --crm-line: #e3e7eb;
            --crm-card: #ffffff;
            --crm-shadow: 0 8px 22px rgba(31, 41, 51, 0.055);
        }
        .stApp {
            background: #f7f8fa;
        }
        .block-container {
            width: 100%;
            max-width: 1360px;
            margin: 0 auto;
            padding: 1rem 3rem 2rem 3rem;
        }
        [data-testid="stHeader"] {
            height: 0;
            background: transparent;
        }
        [data-testid="stToolbar"] {
            display: none;
        }
        h1, h2, h3 {
            color: var(--crm-ink);
            letter-spacing: 0;
        }
        .crm-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 10px 14px;
            margin: 0 0 12px 0;
            box-shadow: var(--crm-shadow);
        }
        .crm-brand {
            display: flex;
            align-items: center;
            gap: 11px;
            min-width: 0;
        }
        .crm-logo,
        .crm-logo-fallback {
            width: 38px;
            height: 38px;
            border-radius: 8px;
            flex: 0 0 auto;
        }
        .crm-logo {
            object-fit: contain;
            display: block;
        }
        .crm-logo-fallback {
            background: var(--crm-rappi);
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.95rem;
        }
        .crm-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--crm-ink);
            line-height: 1.1;
        }
        .crm-subtitle {
            color: var(--crm-muted);
            margin-top: 1px;
            font-size: 0.9rem;
        }
        .crm-pill {
            display: none;
        }
        .login-shell {
            max-width: 480px;
            margin: 6vh auto 0 auto;
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 12px;
            padding: 24px;
            box-shadow: var(--crm-shadow);
        }
        .login-top-space {
            height: 6vh;
            min-height: 32px;
            max-height: 82px;
        }
        .login-brand {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
        }
        .login-title {
            color: var(--crm-ink);
            font-size: 1.35rem;
            font-weight: 600;
            line-height: 1.15;
        }
        .login-subtitle {
            color: var(--crm-muted);
            font-size: 0.92rem;
            margin-top: 2px;
        }
        .logout-row {
            display: flex;
            justify-content: flex-end;
            margin: -6px 0 8px 0;
        }
        div[data-testid="stForm"] {
            border: 0;
            padding: 0;
        }
        div[data-testid="stFormSubmitButton"] button {
            background: var(--crm-rappi) !important;
            border-color: var(--crm-rappi) !important;
            color: #ffffff !important;
            min-height: 42px !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            box-shadow: 0 8px 18px rgba(255, 79, 61, 0.14) !important;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background: var(--crm-rappi-dark) !important;
            border-color: var(--crm-rappi-dark) !important;
        }
        div[data-testid="InputInstructions"],
        div[data-baseweb="input"] + div,
        div[data-testid="stTextInput"] [aria-live="polite"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 12px;
            margin: 8px 0 0 0;
            width: 100%;
        }
        .kpi-card {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 12px 14px;
            min-height: 74px;
            box-shadow: var(--crm-shadow);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .kpi-accent {
            width: 32px;
            height: 3px;
            border-radius: 999px;
            background: var(--crm-rappi);
            margin-bottom: 7px;
        }
        .kpi-label {
            color: var(--crm-muted);
            font-size: 0.78rem;
            font-weight: 500;
            line-height: 1.2;
        }
        .kpi-value {
            color: var(--crm-ink);
            font-size: 1.2rem;
            font-weight: 600;
            line-height: 1;
            margin-top: 6px;
            white-space: normal;
        }
        .crm-card {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 14px 16px;
            margin: 8px 0 12px 0;
            box-shadow: var(--crm-shadow);
        }
        .crm-card h3 {
            margin: 0 0 4px 0;
            font-size: 1.08rem;
        }
        .crm-card p {
            margin: 0;
            color: var(--crm-muted);
        }
        .crm-note {
            background: var(--crm-green-soft);
            border: 1px solid #caecd8;
            border-radius: 8px;
            padding: 10px 12px;
            color: var(--crm-ink);
            margin: 8px 0 12px 0;
        }
        .crm-section-title {
            color: var(--crm-rappi-dark);
            font-weight: 500;
            margin: 16px 0 8px 0;
            font-size: 1rem;
        }
        .crm-divider {
            height: 1px;
            background: var(--crm-line);
            margin: 18px 0 16px 0;
        }
        .update-shell {
            max-width: 620px;
        }
        .update-controls {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            max-width: 420px;
        }
        .update-actions {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            max-width: 420px;
        }
        .update-grid {
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 12px;
            align-items: start;
            margin-top: 6px;
        }
        .update-panel {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 14px;
            box-shadow: var(--crm-shadow);
        }
        .update-panel h3 {
            margin: 0 0 4px 0;
            color: var(--crm-ink);
            font-size: 1.05rem;
        }
        .update-panel p {
            margin: 0;
            color: var(--crm-muted);
            font-size: 0.9rem;
        }
        .compact-kpis .kpi-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 0;
        }
        .kpi-grid.compact-grid {
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            max-width: 100%;
            gap: 12px;
            margin-bottom: 0;
        }
        .compact-kpis .kpi-card {
            min-height: 72px;
            padding: 11px 12px;
        }
        .compact-grid .kpi-card {
            min-height: 72px;
            padding: 11px 12px;
        }
        .compact-kpis .kpi-value {
            font-size: 0.96rem;
            line-height: 1.08;
        }
        .compact-grid .kpi-value {
            font-size: 1rem;
            line-height: 1.08;
        }
        .compact-kpis .kpi-label {
            font-size: 0.76rem;
        }
        .compact-grid .kpi-label {
            font-size: 0.76rem;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.55rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.7rem;
        }
        div[data-testid="stSelectbox"],
        div[data-testid="stMultiSelect"],
        div[data-testid="stTextInput"],
        div[data-testid="stNumberInput"] {
            margin-bottom: 0;
        }
        div[data-testid="stNumberInput"],
        div[data-testid="stMultiSelect"],
        div[data-testid="stSelectbox"],
        div[data-testid="stTextInput"],
        div[data-testid="stDateInput"],
        div[data-testid="stTextArea"] {
            width: 100%;
            max-width: none;
        }
        div[data-testid="stNumberInput"] > div,
        div[data-testid="stMultiSelect"] > div,
        div[data-testid="stSelectbox"] > div,
        div[data-testid="stTextInput"] > div,
        div[data-testid="stDateInput"] > div,
        div[data-testid="stTextArea"] > div {
            width: 100%;
            max-width: none;
        }
        div.stButton > button[kind="primary"] {
            background: var(--crm-rappi);
            border-color: var(--crm-rappi);
            border-radius: 8px;
            font-weight: 500;
            min-height: 42px;
            box-shadow: 0 8px 18px rgba(255, 79, 61, 0.18);
        }
        div.stButton > button[kind="primary"]:hover {
            background: var(--crm-rappi-dark);
            border-color: var(--crm-rappi-dark);
        }
        div.stButton > button {
            border-radius: 8px;
            min-height: 42px;
            font-weight: 500;
            border-color: var(--crm-line);
            background: #ffffff;
            width: 100%;
            max-width: none;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            border-bottom: 1px solid var(--crm-line);
            margin-bottom: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-bottom: 0;
            border-radius: 8px 8px 0 0;
            padding: 8px 18px;
            height: 42px;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            border-color: var(--crm-rappi);
            color: var(--crm-rappi-dark);
            background: var(--crm-rappi-soft);
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            overflow: auto;
            box-shadow: var(--crm-shadow);
            max-width: 100%;
        }
        @media (min-width: 1600px) {
            .block-container {
                padding-left: 3.25rem;
                padding-right: 3.25rem;
            }
        }
        @media (max-width: 1200px) {
            .block-container {
                padding-left: 1.25rem;
                padding-right: 1.25rem;
            }
            .kpi-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .update-grid {
                grid-template-columns: 1fr;
            }
            .compact-kpis .kpi-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .kpi-grid.compact-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                max-width: 100%;
            }
        }
        @media (max-width: 760px) {
            .block-container {
                padding: 0.65rem 0.75rem 1.2rem 0.75rem;
            }
            .crm-topbar {
                align-items: flex-start;
                flex-direction: column;
                gap: 10px;
                padding: 10px 12px;
            }
            .crm-title {
                font-size: 1.08rem;
            }
            .crm-subtitle {
                font-size: 0.82rem;
            }
            .crm-pill {
                white-space: normal;
            }
            .kpi-grid {
                grid-template-columns: 1fr;
            }
            .compact-kpis .kpi-grid {
                grid-template-columns: 1fr;
            }
            .kpi-grid.compact-grid {
                grid-template-columns: 1fr;
            }
            .stTabs [data-baseweb="tab-list"] {
                overflow-x: auto;
                flex-wrap: nowrap;
            }
            .stTabs [data-baseweb="tab"] {
                min-width: max-content;
                padding: 8px 12px;
            }
            .update-panel {
                padding: 12px;
            }
            .update-shell,
            .update-controls,
            .update-actions {
                max-width: 100%;
            }
            .login-top-space {
                height: 24px;
                min-height: 24px;
            }
        }
        .app-shell {
            width: 100%;
            max-width: 1320px;
            margin: 0 auto;
        }
        .app-header {
            display: flex;
            align-items: center;
            gap: 12px;
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 10px;
            box-shadow: var(--crm-shadow);
        }
        .page-section {
            margin-top: 14px;
        }
        .panel-grid-spacer {
            height: 18px;
        }
        .layout-grid {
            display: grid;
            grid-template-columns: minmax(240px, 0.28fr) minmax(0, 0.72fr);
            gap: 18px;
            align-items: start;
        }
        .layout-grid.update-layout {
            grid-template-columns: minmax(320px, 0.55fr) minmax(300px, 0.45fr);
        }
        .side-panel,
        .main-panel {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-radius: 8px;
            padding: 14px;
            box-shadow: var(--crm-shadow);
        }
        .side-panel {
            position: sticky;
            top: 12px;
        }
        .section-title {
            color: var(--crm-ink);
            font-size: 0.98rem;
            font-weight: 500;
            margin: 0 0 12px 0;
        }
        .muted-text {
            color: var(--crm-muted);
            font-size: 0.86rem;
        }
        .table-count-text {
            color: var(--crm-muted);
            font-size: 0.78rem;
            margin-bottom: 8px;
        }
        .result-card {
            background: #ffffff;
            border: 1px solid var(--crm-line);
            border-left: 3px solid var(--crm-rappi);
            border-radius: 8px;
            padding: 12px 14px;
            margin: 0 0 12px 0;
            box-shadow: var(--crm-shadow);
        }
        .result-card-title {
            color: var(--crm-ink);
            font-size: 0.96rem;
            font-weight: 500;
            margin-bottom: 4px;
        }
        .result-card-text {
            color: var(--crm-muted);
            font-size: 0.84rem;
        }
        .action-button {
            width: 100%;
        }
        .layout-grid .kpi-grid {
            margin-top: 0;
        }
        .side-panel div[data-testid="stNumberInput"],
        .side-panel div[data-testid="stMultiSelect"],
        .side-panel div[data-testid="stSelectbox"],
        .side-panel div[data-testid="stTextInput"],
        .side-panel div[data-testid="stDateInput"],
        .side-panel div[data-testid="stTextArea"],
        .main-panel div[data-testid="stNumberInput"],
        .main-panel div[data-testid="stMultiSelect"],
        .main-panel div[data-testid="stSelectbox"],
        .main-panel div[data-testid="stTextInput"],
        .main-panel div[data-testid="stDateInput"],
        .main-panel div[data-testid="stTextArea"] {
            width: 100%;
            max-width: 100%;
        }
        .side-panel div.stButton > button,
        .main-panel div.stButton > button {
            width: 100%;
            max-width: 100%;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--crm-line);
            border-radius: 8px;
            box-shadow: var(--crm-shadow);
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 14px;
        }
        @media (max-width: 1100px) {
            .layout-grid,
            .layout-grid.update-layout {
                grid-template-columns: 1fr;
            }
            .side-panel {
                position: static;
            }
        }
        .crm-topbar {
            border: 0;
            box-shadow: none;
            padding: 8px 2px 10px 2px;
            background: transparent;
        }
        .kpi-grid {
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px;
            margin-top: 6px;
        }
        .kpi-card {
            min-height: 58px;
            padding: 10px 12px;
            border-color: #edf0f3;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035);
        }
        .kpi-accent {
            display: none;
        }
        .kpi-label {
            font-size: 0.74rem;
            font-weight: 400;
        }
        .kpi-value {
            font-size: 1.05rem;
            font-weight: 500;
        }
        .section-title,
        .crm-section-title {
            font-size: 0.88rem;
            font-weight: 500;
            color: #20242a;
            margin: 0 0 10px 0;
        }
        .modern-card {
            background: #ffffff;
            border: 1px solid #e8ebef;
            border-radius: 10px;
            padding: 14px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035);
        }
        .lead-name {
            font-size: 1.05rem;
            font-weight: 500;
            color: #20242a;
            line-height: 1.25;
            margin-bottom: 8px;
        }
        .lead-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0 12px 0;
        }
        .mini-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 4px 8px;
            font-size: 0.72rem;
            font-weight: 500;
            background: #f2f4f7;
            color: #47505a;
        }
        .mini-badge.accent {
            background: #fff0ec;
            color: #c83a20;
        }
        .mini-badge.positive {
            background: #edf8f2;
            color: #16784b;
        }
        .table-count-text {
            margin-bottom: 10px;
            color: #68727d;
            font-size: 0.82rem;
        }
        div[data-testid="stDataFrame"] div[role="columnheader"] {
            background: #fafbfc;
            font-weight: 500;
        }
        div[data-testid="stLinkButton"] a {
            min-height: 34px;
            height: 34px;
            padding: 0;
            border-radius: 10px;
            border-color: #e7eaef;
            background: #ffffff;
            box-shadow: none;
            font-size: 0.95rem;
            font-weight: 500;
            justify-content: center;
        }
        div[data-testid="stLinkButton"] a:hover {
            background: #fff4f1;
            border-color: #ffd0c5;
            color: #c83a20;
        }
        div[data-testid="stLinkButton"] a[aria-disabled="true"],
        div[data-testid="stLinkButton"] a[data-disabled="true"] {
            background: #f3f4f6;
            border-color: #e5e7eb;
            color: #a2a9b2;
        }
        .lead-actions {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 10px 0 12px 0;
        }
        .lead-action-icon {
            width: 34px;
            height: 34px;
            border: 1px solid #e7eaef;
            border-radius: 10px;
            background: #ffffff;
            color: #68727d;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
        }
        .lead-action-icon svg {
            width: 17px;
            height: 17px;
            display: block;
        }
        .lead-action-icon:hover {
            background: #fff4f1;
            border-color: #ffd0c5;
            color: #ff441f;
            transform: translateY(-1px);
        }
        .lead-action-icon.disabled {
            background: #f3f4f6;
            border-color: #e5e7eb;
            color: #a2a9b2;
            pointer-events: none;
            cursor: default;
        }
        .floating-toast-success {
            position: fixed;
            right: 24px;
            bottom: 24px;
            z-index: 9999;
            width: min(320px, calc(100vw - 32px));
            padding: 12px 14px;
            border: 1px solid #cbeedd;
            border-radius: 14px;
            background: #f0fbf5;
            color: #173f2b;
            box-shadow: 0 18px 50px rgba(31, 41, 51, 0.16);
            animation: toastFade 4.8s ease forwards;
        }
        .floating-toast-success strong,
        .floating-toast-success span,
        .floating-toast-success small {
            display: block;
        }
        .floating-toast-success strong {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .floating-toast-success span {
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .floating-toast-success small {
            color: #4f6f5e;
            font-size: 12px;
            line-height: 1.35;
        }
        @keyframes toastFade {
            0% { opacity: 0; transform: translateY(10px); }
            10% { opacity: 1; transform: translateY(0); }
            82% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(8px); pointer-events: none; }
        }
        .mini-badge.hot {
            color: #b93815;
            border-color: #ffd0bf;
            background: #fff4ef;
        }
        .lead-action-icon.whatsapp.active {
            color: #25d366;
        }
        .lead-action-icon.instagram.active {
            color: #e4405f;
        }
        .lead-action-icon.facebook.active {
            color: #1877f2;
        }
        .lead-action-icon.maps.active {
            color: #34a853;
        }
        .lead-action-icon.website.active {
            color: #ff441f;
        }
        .lead-alert-badge {
            border: 1px solid #ffd8a8;
            border-left: 3px solid #f59e0b;
            border-radius: 10px;
            background: #fff8ed;
            color: #7a3f00;
            padding: 9px 10px;
            margin: 10px 0 12px;
        }
        .lead-alert-badge strong,
        .lead-alert-badge span {
            display: block;
        }
        .lead-alert-badge strong {
            font-size: 12.5px;
            font-weight: 600;
        }
        .lead-alert-badge span {
            color: #9a650b;
            font-size: 12px;
            margin-top: 2px;
        }
        .timeline-card {
            background: #ffffff;
            border: 1px solid #e8ebef;
            border-radius: 12px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035);
            padding: 14px;
            margin-top: 14px;
        }
        .timeline-list {
            position: relative;
            display: grid;
            gap: 10px;
            margin-top: 10px;
        }
        .timeline-item {
            position: relative;
            display: grid;
            grid-template-columns: 18px minmax(0, 1fr);
            gap: 10px;
        }
        .timeline-dot {
            width: 9px;
            height: 9px;
            margin-top: 6px;
            border-radius: 999px;
            background: #ff441f;
            box-shadow: 0 0 0 4px #fff0ec;
        }
        .timeline-body {
            border: 1px solid #edf0f3;
            border-radius: 10px;
            background: #fafbfc;
            padding: 9px 10px;
        }
        .timeline-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
            color: #68727d;
            font-size: 11.5px;
            margin-bottom: 4px;
        }
        .timeline-action {
            color: #20242a;
            font-size: 13px;
            font-weight: 500;
        }
        .timeline-detail {
            color: #59636f;
            font-size: 12px;
            line-height: 1.35;
            margin-top: 3px;
        }
        .timeline-empty {
            margin-top: 10px;
            border: 1px solid #edf0f3;
            border-radius: 10px;
            background: #fafbfc;
            color: #68727d;
            font-size: 13px;
            padding: 10px 12px;
        }
        .message-preview-box {
            background: #fafbfc;
            border: 1px solid #e8ebef;
            border-radius: 10px;
            padding: 10px 12px;
            margin: 6px 0 10px 0;
            color: #343a40;
            font-size: 0.84rem;
            line-height: 1.4;
            max-height: 96px;
            overflow-y: auto;
        }
        .rules-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }
        .rules-card {
            background: #fafbfc;
            border: 1px solid #e8ebef;
            border-radius: 10px;
            padding: 12px;
        }
        .rules-title {
            font-size: 0.86rem;
            font-weight: 500;
            color: #20242a;
            margin-bottom: 8px;
        }
        .rules-card ul {
            margin: 0;
            padding-left: 18px;
            color: #4b5563;
            font-size: 0.8rem;
            line-height: 1.45;
        }
        .rules-card.automation {
            border-left: 3px solid #ffb020;
        }
        .rules-card.manual {
            border-left: 3px solid #ff441f;
        }

        /* Visual system override: one lightweight CRM identity across sections. */
        :root {
            --crm-rappi: #FF441F;
            --crm-rappi-dark: #D93A1B;
            --crm-rappi-soft: #FFF2EE;
            --crm-bg: #F7F8FA;
            --crm-card: #FFFFFF;
            --crm-ink: #20242A;
            --crm-muted: #6B7280;
            --crm-line: #E6E9EE;
            --crm-radius: 12px;
            --crm-control-radius: 10px;
            --crm-card-padding: 16px;
            --crm-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
            --crm-shadow-hover: 0 6px 18px rgba(15, 23, 42, 0.08);
        }
        html, body, .stApp {
            background: var(--crm-bg) !important;
            color: var(--crm-ink) !important;
            font-family: "Inter", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif !important;
            font-size: 15px;
            font-weight: 400;
        }
        .block-container {
            max-width: 1360px;
            padding-top: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        .app-shell {
            max-width: 1360px;
        }
        .app-header,
        [data-testid="stVerticalBlockBorderWrapper"],
        .crm-card,
        .update-panel,
        .side-panel,
        .main-panel,
        .modern-card,
        .kpi-card,
        .rules-card {
            background: var(--crm-card) !important;
            border: 1px solid var(--crm-line) !important;
            border-radius: var(--crm-radius) !important;
            box-shadow: var(--crm-shadow) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: var(--crm-card-padding) !important;
        }
        .app-header {
            padding: 12px 16px !important;
            margin-bottom: 14px !important;
        }
        .crm-title {
            font-size: 22px !important;
            font-weight: 600 !important;
            line-height: 1.15 !important;
            letter-spacing: 0 !important;
            color: var(--crm-ink) !important;
        }
        .crm-subtitle,
        .muted-text,
        .table-count-text,
        .crm-row-help,
        .result-card-text,
        .contact-last-box span,
        .stCaptionContainer {
            font-size: 13px !important;
            font-weight: 400 !important;
            color: var(--crm-muted) !important;
        }
        .section-title,
        .crm-section-title {
            font-size: 22px !important;
            line-height: 1.2 !important;
            font-weight: 600 !important;
            color: var(--crm-ink) !important;
            margin: 0 0 14px 0 !important;
            letter-spacing: 0 !important;
        }
        .panel-grid-spacer {
            height: 18px !important;
        }
        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"] {
            gap: 14px;
        }
        .kpi-grid {
            gap: 12px !important;
            margin: 8px 0 0 0 !important;
        }
        .kpi-card {
            min-height: 70px !important;
            padding: 14px 16px !important;
            justify-content: center !important;
        }
        .kpi-label {
            color: var(--crm-muted) !important;
            font-size: 13px !important;
            font-weight: 400 !important;
            line-height: 1.25 !important;
        }
        .kpi-value {
            color: var(--crm-ink) !important;
            font-size: 22px !important;
            font-weight: 600 !important;
            line-height: 1.1 !important;
            margin-top: 5px !important;
        }
        .kpi-accent {
            display: none !important;
        }
        label,
        .stMarkdown,
        .stText,
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stMultiSelect"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stDateInput"] label {
            font-size: 15px !important;
            font-weight: 400 !important;
            color: var(--crm-ink);
        }
        div.stButton > button,
        div[data-testid="stDownloadButton"] button,
        div[data-testid="stLinkButton"] a {
            min-height: 40px !important;
            border-radius: var(--crm-control-radius) !important;
            padding: 0 14px !important;
            font-size: 15px !important;
            font-weight: 500 !important;
            border: 1px solid var(--crm-line) !important;
            box-shadow: none !important;
            transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease, box-shadow 0.14s ease;
        }
        div.stButton > button[kind="primary"],
        div[data-testid="stDownloadButton"] button[kind="primary"] {
            background: var(--crm-rappi) !important;
            border-color: var(--crm-rappi) !important;
            color: #ffffff !important;
        }
        div.stButton > button[kind="primary"]:hover,
        div[data-testid="stDownloadButton"] button[kind="primary"]:hover {
            background: var(--crm-rappi-dark) !important;
            border-color: var(--crm-rappi-dark) !important;
        }
        div.stButton > button:not([kind="primary"]):hover,
        div[data-testid="stDownloadButton"] button:hover,
        div[data-testid="stLinkButton"] a:hover {
            background: #FAFBFC !important;
            border-color: #D7DCE2 !important;
            color: var(--crm-ink) !important;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] textarea,
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,
        textarea {
            min-height: 40px !important;
            border-radius: var(--crm-control-radius) !important;
            font-size: 15px !important;
            font-weight: 400 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px !important;
            border-bottom: 1px solid var(--crm-line) !important;
            margin-bottom: 18px !important;
        }
        .stTabs [data-baseweb="tab"] {
            height: 40px !important;
            padding: 0 16px !important;
            border: 0 !important;
            border-radius: var(--crm-control-radius) var(--crm-control-radius) 0 0 !important;
            background: transparent !important;
            font-size: 15px !important;
            font-weight: 500 !important;
            color: var(--crm-muted) !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--crm-rappi) !important;
            background: #FFFFFF !important;
            box-shadow: inset 0 -2px 0 var(--crm-rappi) !important;
        }
        .lead-name {
            font-size: 22px !important;
            font-weight: 600 !important;
            line-height: 1.2 !important;
            color: var(--crm-ink) !important;
            margin-bottom: 10px !important;
        }
        .lead-meta {
            gap: 6px !important;
            margin: 8px 0 14px 0 !important;
        }
        .mini-badge {
            padding: 4px 8px !important;
            font-size: 13px !important;
            font-weight: 400 !important;
            border: 1px solid #E8EBEF !important;
            background: #F7F8FA !important;
            color: #4B5563 !important;
        }
        .mini-badge.accent {
            background: var(--crm-rappi-soft) !important;
            color: #B9361C !important;
            border-color: #FFD8CE !important;
        }
        .mini-badge.positive {
            background: #EDF8F2 !important;
            color: #137D4B !important;
            border-color: #CBEEDD !important;
        }
        div[role="radiogroup"] {
            gap: 2px !important;
        }
        div[role="radiogroup"] label {
            min-height: 30px !important;
            padding: 4px 8px 4px 10px !important;
            border: 1px solid transparent !important;
            border-bottom-color: #EEF1F4 !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            background: #FFFFFF !important;
        }
        div[role="radiogroup"] label:hover {
            background: #FAFBFC !important;
            border-color: #EEF1F4 !important;
        }
        div[role="radiogroup"] label:has(input:checked) {
            background: var(--crm-rappi-soft) !important;
            border-color: #FFE0D8 !important;
            box-shadow: inset 2px 0 0 var(--crm-rappi) !important;
        }
        div[role="radiogroup"] label p {
            font-size: 16px !important;
            font-weight: 500 !important;
            color: var(--crm-ink) !important;
            text-align: left !important;
            line-height: 1.2 !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--crm-line) !important;
            border-radius: var(--crm-radius) !important;
            box-shadow: none !important;
            background: #FFFFFF !important;
        }
        div[data-testid="stDataFrame"] div[role="columnheader"] {
            background: #FAFBFC !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            color: var(--crm-muted) !important;
        }
        .rules-grid {
            gap: 12px !important;
        }
        .rules-card {
            padding: 14px !important;
            border-left-width: 2px !important;
        }
        .rules-title {
            font-size: 15px !important;
            font-weight: 600 !important;
            color: var(--crm-ink) !important;
        }
        .rules-card ul {
            font-size: 13px !important;
            font-weight: 400 !important;
            color: var(--crm-muted) !important;
            line-height: 1.5 !important;
        }
        @media (max-width: 760px) {
            .rules-grid {
                grid-template-columns: 1fr;
            }
            .block-container {
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
            }
            .section-title,
            .crm-section-title,
            .lead-name {
                font-size: 20px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text.strip()


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {clean_text(col).lower(): col for col in df.columns}
    for candidate in candidates:
        found = normalized.get(candidate.lower())
        if found:
            return found
    return None


def get_series(df: pd.DataFrame, candidates: list[str], default: str = "") -> pd.Series:
    col = find_column(df, candidates)
    if col and col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def normalize_message_variant_key(value: object) -> str:
    text = clean_text(value)
    return {"A": "1", "B": "2", "C": "3"}.get(text, text)


def default_message_config() -> dict[str, dict[str, object]]:
    return {key: {"text": text, "active": True} for key, text in DEFAULT_MESSAGE_VARIANTS.items()}


def save_message_config(config: dict[str, dict[str, object]]) -> None:
    WHATSAPP_MESSAGES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    defaults = default_message_config()
    for key in DEFAULT_MESSAGE_VARIANTS:
        item = config.get(key, {})
        payload[key] = {
            "text": clean_text(item.get("text", defaults[key]["text"])),
            "active": bool(item.get("active", True)),
        }
    WHATSAPP_MESSAGES_CONFIG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_message_config() -> dict[str, dict[str, object]]:
    if get_data_mode() == "supabase":
        loaded = ds_load_mensajes()
        config = default_message_config()
        for variant in DEFAULT_MESSAGE_VARIANTS:
            raw = loaded.get(variant, {})
            if isinstance(raw, dict):
                value = clean_text(raw.get("text", ""))
                active = bool(raw.get("active", True))
            else:
                value = clean_text(raw)
                active = True
            if value:
                config[variant]["text"] = value
            config[variant]["active"] = active
        return config

    if not WHATSAPP_MESSAGES_CONFIG.exists():
        config = default_message_config()
        save_message_config(config)
        return config
    try:
        loaded = json.loads(WHATSAPP_MESSAGES_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        loaded = {}
    config = default_message_config()
    legacy_map = {"A": "1", "B": "2", "C": "3"}
    for legacy_key, new_key in legacy_map.items():
        if legacy_key in loaded and new_key not in loaded:
            loaded[new_key] = loaded[legacy_key]
    for variant in DEFAULT_MESSAGE_VARIANTS:
        raw = loaded.get(variant, {})
        if isinstance(raw, dict):
            value = clean_text(raw.get("text", ""))
            active = bool(raw.get("active", True))
        else:
            value = clean_text(raw)
            active = True
        if value:
            config[variant]["text"] = value
        config[variant]["active"] = active
    if loaded != config:
        save_message_config(config)
    return config


def save_message_variants(messages: dict[str, str]) -> None:
    config = load_message_config()
    for key, text in messages.items():
        normalized = normalize_message_variant_key(key)
        if normalized in config:
            config[normalized]["text"] = clean_text(text)
    save_message_config(config)


def load_message_variants(active_only: bool = True) -> dict[str, str]:
    config = load_message_config()
    out = {}
    for key, item in config.items():
        if active_only and not bool(item.get("active", True)):
            continue
        out[key] = clean_text(item.get("text", ""))
    return out or {"1": DEFAULT_MESSAGE_VARIANTS["1"]}


def refresh_whatsapp_message_state(active_messages: dict[str, str] | None = None) -> None:
    st.session_state["whatsapp_messages_version"] = int(st.session_state.get("whatsapp_messages_version", 0)) + 1
    for key in list(st.session_state.keys()):
        if key.startswith("lead_wa_msg_") or key.startswith("lead_msg_variant_") or key.startswith("assigned_msg_variant_"):
            del st.session_state[key]
    active_messages = active_messages or load_message_variants()
    active_keys = ", ".join(active_messages.keys())
    print(f"Mensajes WhatsApp activos actualizados: {active_keys}")


def normalize_crm_columns(df: pd.DataFrame) -> pd.DataFrame:
    renames = {
        "Fecha último contacto": "Fecha ultimo contacto",
        "Fecha ?ltimo contacto": "Fecha ultimo contacto",
        "Fecha ?ltimo contacto": "Fecha ultimo contacto",
        "Canal último contacto": "Canal ultimo contacto",
        "Observación CRM": "Observacion CRM",
        "Observaci?n CRM": "Observacion CRM",
        "Observaci?n CRM": "Observacion CRM",
        "Próxima acción": "Proxima accion",
        "Pr?xima acci?n": "Proxima accion",
        "Pr?xima acci?n": "Proxima accion",
        "Fecha próxima acción": "Fecha proxima accion",
        "Fecha pr?xima acci?n": "Fecha proxima accion",
        "Fecha pr?xima acci?n": "Fecha proxima accion",
        "Fecha último WhatsApp": "Fecha ultimo WhatsApp",
        "Fecha ?ltimo WhatsApp": "Fecha ultimo WhatsApp",
        "Fecha ?ltimo WhatsApp": "Fecha ultimo WhatsApp",
        "Fecha envío WhatsApp": "Fecha envio WhatsApp",
        "Fecha env?o WhatsApp": "Fecha envio WhatsApp",
        "Respondió": "Respondio",
        "Reunión agendada": "Reunion agendada",
        "Reuni?n agendada": "Reunion agendada",
        "Respondió": "Respondio",
    }
    return df.rename(columns=renames)


def normalize_crm_state(value: object) -> str:
    text = clean_text(value)
    if not text:
        return "Nuevo"
    legacy_map = {
        "Respondio": "Contactado",
        "Respondió": "Contactado",
        "Interesado": "Contactado",
        "No interesado": "Contactado",
        "Cliente potencial": "Contactado",
    }
    text = legacy_map.get(text, text)
    return text if text in CRM_STATES else "Contactado"


def normalize_crm_state_series(series: pd.Series) -> pd.Series:
    return series.apply(normalize_crm_state)


def normalize_resultado_seguimiento(value: object, empty_as: str = "") -> str:
    text = re.sub(r"\s+", " ", clean_text(value)).strip()
    if not text:
        return empty_as
    return RESULTADO_SEGUIMIENTO_LOOKUP.get(text.lower(), text)


def normalize_phone(value: object) -> str:
    digits = re.sub(r"\D", "", clean_text(value))
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("56"):
        return digits
    if digits.startswith("9") and len(digits) == 9:
        return "56" + digits
    return digits


def normalize_chilean_mobile(phone: object) -> str:
    normalized = normalize_phone(phone)
    if re.fullmatch(r"569\d{8}", normalized or ""):
        return normalized
    return ""


def normalizar_telefono_llamada(phone: object) -> str:
    digits = re.sub(r"\D", "", clean_text(phone))
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("56") and 10 <= len(digits) <= 12:
        return digits
    if digits.startswith("9") and len(digits) == 9:
        return "56" + digits
    if len(digits) == 9 and digits[0] in "2345678":
        return "56" + digits
    if 8 <= len(digits) <= 12:
        return digits
    return ""


def telefono_tipo(phone: object) -> str:
    if normalizar_telefono_whatsapp(phone):
        return "Celular"
    normalized = normalizar_telefono_llamada(phone)
    if normalized:
        return "Fijo"
    return "Sin teléfono"


def telefono_normalizado_display(phone: object) -> str:
    mobile = normalizar_telefono_whatsapp(phone)
    if mobile:
        return f"+56 9 {mobile[3:7]} {mobile[7:11]}"
    normalized = normalizar_telefono_llamada(phone)
    if not normalized:
        return ""
    if normalized.startswith("562") and len(normalized) == 11:
        return f"+56 2 {normalized[3:7]} {normalized[7:11]}"
    if normalized.startswith("56") and len(normalized) >= 10:
        rest = normalized[2:]
        return f"+56 {rest[:1]} {rest[1:5]} {rest[5:]}"
    return f"+{normalized}" if normalized.startswith("56") else normalized


def normalizar_telefono_whatsapp(phone: object) -> str:
    return normalize_chilean_mobile(phone)


def is_valid_whatsapp_phone(phone: object) -> bool:
    return bool(normalizar_telefono_whatsapp(phone))


def whatsapp_message(name: object, comuna: object) -> str:
    restaurant = clean_text(name) or "tu restaurante"
    comuna_text = clean_text(comuna)
    location = f" en {comuna_text}" if comuna_text else ""
    return (
        f"Hola, ¿cómo estás? Te escribo porque encontré el restaurante {restaurant}{location} "
        "en Google y quería hacer una consulta comercial breve. ¿Con quién podría hablar?"
    )


def render_variant_message(variant: str, name: object, comuna: object) -> str:
    variants = load_message_variants()
    variant = normalize_message_variant_key(variant)
    template = variants.get(variant, DEFAULT_MESSAGE_VARIANTS["1"])
    try:
        return template.format(nombre=clean_text(name) or "tu restaurante", comuna=clean_text(comuna) or "tu comuna")
    except KeyError:
        return template


def is_whatsapp_contact_registered(row: pd.Series) -> bool:
    estado = clean_text(row.get("Estado WhatsApp", ""))
    return any(
        [
            clean_text(row.get("Fecha envio WhatsApp", "")),
            clean_text(row.get("Mensaje enviado", "")),
            estado and estado != "No contactado",
        ]
    )


def total_whatsapp_contacts_registered(crm: pd.DataFrame) -> int:
    if crm.empty:
        return 0
    return int(crm.apply(is_whatsapp_contact_registered, axis=1).sum())


def next_message_variant() -> str:
    variants = list(load_message_variants())
    return random.choice(variants) if variants else "1"


def assigned_message_variant(row: pd.Series) -> str:
    existing = normalize_message_variant_key(row.get("Variante mensaje", ""))
    variants = load_message_variants()
    crm_id = clean_text(row.get("CRM ID", "")) or lead_selection_key(row)
    version = int(st.session_state.get("whatsapp_messages_version", 0))
    session_key = f"assigned_msg_variant_{crm_id}_{version}"
    if is_whatsapp_contact_registered(row) and existing in variants:
        return existing
    if st.session_state.get(session_key) not in variants:
        st.session_state[session_key] = random.choice(list(variants)) if variants else "1"
    return st.session_state[session_key]


def whatsapp_url(phone: object, message: str = "") -> str:
    normalized = normalize_chilean_mobile(phone)
    if not normalized:
        return ""
    if message:
        return f"https://wa.me/{normalized}?text={quote(message)}"
    return f"https://wa.me/{normalized}"


def ensure_key(df: pd.DataFrame) -> pd.Series:
    maps = get_series(df, ["Google Maps URL"]).fillna("").astype(str).str.strip()
    fallback = (
        get_series(df, ["Nombre restaurante"]).fillna("").astype(str).str.lower().str.strip()
        + "|"
        + get_series(df, ADDRESS_COLUMNS).fillna("").astype(str).str.lower().str.strip()
        + "|"
        + get_series(df, ["Comuna"]).fillna("").astype(str).str.lower().str.strip()
    )
    return maps.where(maps != "", fallback)


def lead_identifier(row: pd.Series, index: object | None = None) -> str:
    crm_id = clean_text(row.get("CRM ID", ""))
    if crm_id:
        return crm_id
    maps = clean_text(row.get("Google Maps URL", ""))
    if maps:
        return maps
    name = clean_text(row.get("Nombre restaurante", "")).lower()
    address = clean_text(row.get("Direccion", row.get("Dirección", row.get("Dirección", "")))).lower()
    comuna = clean_text(row.get("Comuna", "")).lower()
    fallback = "|".join([name, address, comuna]).strip("|")
    return fallback or f"idx:{index}"


def selected_index_from_lead_id(df: pd.DataFrame, lead_id: str) -> object | None:
    if df.empty or not lead_id:
        return None
    if "CRM ID" in df.columns:
        matches = df.index[df["CRM ID"].fillna("").astype(str) == lead_id].tolist()
        if matches:
            return matches[0]
    for index, row in df.iterrows():
        if lead_identifier(row, index) == lead_id:
            return index
    return None


def lead_selection_key(row: pd.Series, index: object | None = None) -> str:
    raw = lead_identifier(row, index)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def selected_index_from_selection_key(df: pd.DataFrame, selection_key: str) -> object | None:
    if df.empty or not selection_key:
        return None
    for index, row in df.iterrows():
        if lead_selection_key(row, index) == selection_key:
            return index
    return None


def sync_selected_lead_from_query(filtered: pd.DataFrame) -> None:
    selection_key = clean_text(st.query_params.get("selected_lead_key", ""))
    selected_index = selected_index_from_selection_key(filtered, selection_key)
    if selected_index in filtered.index:
        st.session_state["selected_lead_id"] = lead_identifier(filtered.loc[selected_index], selected_index)
        st.session_state["selected_lead_key"] = selection_key
        st.session_state["selected_lead_index"] = selected_index


def resolve_visible_selected_index(filtered: pd.DataFrame) -> object | None:
    if filtered.empty:
        st.session_state.pop("selected_lead_id", None)
        return None
    selected_id = clean_text(st.session_state.get("selected_lead_id", ""))
    selected_index = selected_index_from_lead_id(filtered, selected_id)
    if selected_index in filtered.index:
        return selected_index
    first_index = filtered.index[0]
    st.session_state["selected_lead_id"] = lead_identifier(filtered.loc[first_index], first_index)
    st.session_state["selected_lead_key"] = lead_selection_key(filtered.loc[first_index], first_index)
    st.session_state["selected_lead_index"] = first_index
    return first_index


def select_lead(lead_id: str, lead_key: str, index: object) -> None:
    st.session_state["selected_lead_id"] = lead_id
    st.session_state["selected_lead_key"] = lead_key
    st.session_state["selected_lead_index"] = index


def derive_load_date(df: pd.DataFrame) -> pd.Series:
    source = get_series(
        df,
        ["Fecha carga", "Fecha extraccion", "Fecha extracción", "Fecha extracci?n", "Fecha actualizacion", "Fecha actualización", "Fecha actualizaci?n"],
    )
    parsed = pd.to_datetime(source, errors="coerce").dt.date
    fallback = datetime.fromtimestamp(BASE_XLSX.stat().st_mtime).date() if BASE_XLSX.exists() else date.today()
    return parsed.fillna(fallback).astype(str)


@st.cache_data(show_spinner=False)
def load_base() -> pd.DataFrame:
    if get_data_mode() == "supabase":
        df = ds_load_restaurantes()
        if df.empty:
            return df
        if "CRM ID" not in df.columns:
            df["CRM ID"] = ensure_key(df)
        if "Fecha carga CRM" not in df.columns:
            df["Fecha carga CRM"] = derive_load_date(df)
        return df

    if not BASE_XLSX.exists():
        return pd.DataFrame()
    df = pd.read_excel(BASE_XLSX, sheet_name="Base restaurantes")
    df["CRM ID"] = ensure_key(df)
    df["Fecha carga CRM"] = derive_load_date(df)
    return df


@st.cache_data(show_spinner=False)
def load_crm_state() -> pd.DataFrame:
    if get_data_mode() == "supabase":
        crm = normalize_crm_columns(ds_load_crm_estado())
    elif CRM_XLSX.exists():
        crm = normalize_crm_columns(pd.read_excel(CRM_XLSX))
    else:
        crm = pd.DataFrame(columns=["CRM ID"] + CRM_FIELDS)
    missing_fields = [field for field in ["CRM ID"] + CRM_FIELDS if field not in crm.columns]
    for field in ["CRM ID"] + CRM_FIELDS:
        if field not in crm.columns:
            crm[field] = ""
    crm["Estado CRM"] = crm["Estado CRM"].replace({"Respondió": "Respondio"})
    previous_states = crm["Estado CRM"].fillna("").astype(str).copy()
    crm["Estado CRM"] = normalize_crm_state_series(crm["Estado CRM"])
    if get_data_mode() == "local" and CRM_XLSX.exists() and (missing_fields or not previous_states.eq(crm["Estado CRM"].fillna("").astype(str)).all()):
        save_crm_state(crm)
    return crm[["CRM ID"] + CRM_FIELDS]


def migrate_legacy_crm_states(crm: pd.DataFrame) -> bool:
    if crm.empty or "Estado CRM" not in crm.columns:
        return False
    normalized = normalize_crm_state_series(crm["Estado CRM"])
    changed = ~crm["Estado CRM"].fillna("").astype(str).eq(normalized.fillna("").astype(str))
    if not bool(changed.any()):
        return False
    updated = crm.copy()
    updated["Estado CRM"] = normalized
    save_crm_state(updated)
    st.cache_data.clear()
    return True


def save_crm_state(df: pd.DataFrame) -> None:
    CRM_XLSX.parent.mkdir(parents=True, exist_ok=True)
    out = normalize_crm_columns(df)[["CRM ID"] + CRM_FIELDS].copy()
    out["Estado CRM"] = normalize_crm_state_series(out["Estado CRM"])
    out["Resultado seguimiento"] = out["Resultado seguimiento"].apply(lambda value: normalize_resultado_seguimiento(value, ""))
    out = out.drop_duplicates(subset=["CRM ID"], keep="last")
    if get_data_mode() == "supabase":
        ds_save_crm_estado(out)
        st.session_state["crm_state_version"] = int(st.session_state.get("crm_state_version", 0)) + 1
        return
    out = out.rename(
        columns={
            "Fecha ultimo contacto": "Fecha último contacto",
            "Canal ultimo contacto": "Canal último contacto",
            "Observacion CRM": "Observación CRM",
            "Proxima accion": "Próxima acción",
            "Fecha proxima accion": "Fecha próxima acción",
            "Fecha ultimo WhatsApp": "Fecha último WhatsApp",
            "Fecha envio WhatsApp": "Fecha envío WhatsApp",
            "Respondio": "Respondió",
            "Reunion agendada": "Reunión agendada",
        }
    )
    out.to_excel(CRM_XLSX, index=False)
    st.session_state["crm_state_version"] = int(st.session_state.get("crm_state_version", 0)) + 1


def normalize_contact_history_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {
        "Fecha hora": "Fecha/hora",
        "Fecha contacto": "Fecha/hora",
        "Accion": "Acción",
        "Estado CRM": "Estado CRM actual",
        "Resultado seguimiento": "Resultado seguimiento actual",
        "Mensaje / detalle": "Mensaje enviado",
    }
    out = out.rename(columns={key: value for key, value in rename_map.items() if key in out.columns})
    for field in CONTACT_HISTORY_FIELDS:
        if field not in out.columns:
            out[field] = ""
    return out[CONTACT_HISTORY_FIELDS]


@st.cache_data(show_spinner=False)
def load_contact_history() -> pd.DataFrame:
    if get_data_mode() == "supabase":
        history = ds_load_historial_contactos()
        if history.empty:
            return pd.DataFrame(columns=CONTACT_HISTORY_FIELDS)
        history = normalize_contact_history_columns(history)
        for col in CONTACT_HISTORY_FIELDS:
            history[col] = history[col].fillna("").astype(str).replace({"nan": "", "None": ""})
        return history

    if not CONTACT_HISTORY_XLSX.exists():
        return pd.DataFrame(columns=CONTACT_HISTORY_FIELDS)
    history = pd.read_excel(CONTACT_HISTORY_XLSX)
    history = normalize_contact_history_columns(history)
    for col in CONTACT_HISTORY_FIELDS:
        history[col] = history[col].fillna("").astype(str).replace({"nan": "", "None": ""})
    return history


def save_contact_history(df: pd.DataFrame) -> None:
    CONTACT_HISTORY_XLSX.parent.mkdir(parents=True, exist_ok=True)
    out = normalize_contact_history_columns(df)
    if get_data_mode() == "supabase":
        for row in out.to_dict(orient="records"):
            ds_insert_historial_evento(row)
        st.session_state["contact_history_version"] = int(st.session_state.get("contact_history_version", 0)) + 1
        return
    out.to_excel(CONTACT_HISTORY_XLSX, index=False)
    st.session_state["contact_history_version"] = int(st.session_state.get("contact_history_version", 0)) + 1


def crm_event_context(crm_id: str, fallback_name: str = "") -> dict[str, str]:
    base = load_base()
    if not base.empty and "CRM ID" in base.columns:
        match = base[base["CRM ID"].fillna("").astype(str) == clean_text(crm_id)]
        if not match.empty:
            row = match.iloc[0]
            name_col = find_column(base, ["Nombre restaurante"]) or "Nombre restaurante"
            comuna_col = find_column(base, ["Comuna"]) or "Comuna"
            return {
                "Restaurante": clean_text(row.get(name_col, "")) or clean_text(fallback_name),
                "Comuna": clean_text(row.get(comuna_col, "")),
            }
    return {"Restaurante": clean_text(fallback_name), "Comuna": ""}


def append_contact_event(
    crm_id: str,
    canal: str,
    accion: str,
    current_state: dict[str, object],
    mensaje: str = "",
    restaurant_name: str = "",
    fecha_hora: object | None = None,
    skip_if_same_event: bool = False,
) -> None:
    context = crm_event_context(crm_id, restaurant_name)
    timestamp = pd.to_datetime(clean_text(fecha_hora), errors="coerce") if fecha_hora is not None else pd.NaT
    timestamp_text = timestamp.strftime("%Y-%m-%d %H:%M:%S") if not pd.isna(timestamp) else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = {
        "Fecha/hora": timestamp_text,
        "CRM ID": clean_text(crm_id),
        "Restaurante": context["Restaurante"],
        "Comuna": context["Comuna"],
        "Canal": clean_text(canal) or "Manual",
        "Acción": clean_text(accion),
        "Estado CRM actual": normalize_crm_state(current_state.get("Estado CRM", "")),
        "Resultado seguimiento actual": normalize_resultado_seguimiento(current_state.get("Resultado seguimiento", ""), ""),
        "Mensaje enviado": clean_text(mensaje),
    }
    if get_data_mode() == "supabase":
        ds_insert_historial_evento(event)
        st.cache_data.clear()
        return
    history = load_contact_history()
    if skip_if_same_event and not history.empty:
        duplicate = (
            (history["CRM ID"].fillna("").astype(str) == event["CRM ID"])
            & (history["Canal"].fillna("").astype(str) == event["Canal"])
            & (history["Acción"].fillna("").astype(str) == event["Acción"])
            & (history["Mensaje enviado"].fillna("").astype(str) == event["Mensaje enviado"])
        )
        if bool(duplicate.any()):
            return
    history = pd.concat([history, pd.DataFrame([event])], ignore_index=True)
    save_contact_history(history)
    st.cache_data.clear()


def best_added_date(row: pd.Series) -> str:
    for name in ["Fecha carga", "Fecha extracción", "Fecha extraccion", "Fecha actualización", "Fecha actualizacion", "Fecha carga CRM"]:
        value = clean_text(row.get(name, ""))
        if value:
            parsed = pd.to_datetime(value, errors="coerce")
            if not pd.isna(parsed):
                return parsed.strftime("%Y-%m-%d %H:%M:%S")
            return value
    if BASE_XLSX.exists():
        return datetime.fromtimestamp(BASE_XLSX.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_restaurant_added_events(df: pd.DataFrame) -> int:
    if df.empty or "CRM ID" not in df.columns:
        return 0
    history = load_contact_history()
    existing_ids: set[str] = set()
    if not history.empty:
        mask = history["Acción"].fillna("").astype(str) == "Restaurante agregado"
        existing_ids = set(history.loc[mask, "CRM ID"].fillna("").astype(str))
    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(df, ["Comuna"]) or "Comuna"
    events = []
    for _, row in df.iterrows():
        crm_id = clean_text(row.get("CRM ID", ""))
        if not crm_id or crm_id in existing_ids:
            continue
        events.append(
            {
                "Fecha/hora": best_added_date(row),
                "CRM ID": crm_id,
                "Restaurante": clean_text(row.get(name_col, "")),
                "Comuna": clean_text(row.get(comuna_col, "")),
                "Canal": "Sistema",
                "Acción": "Restaurante agregado",
                "Estado CRM actual": normalize_crm_state(row.get("Estado CRM", "")) or "Nuevo",
                "Resultado seguimiento actual": normalize_resultado_seguimiento(row.get("Resultado seguimiento", ""), ""),
                "Mensaje enviado": "Lead ingresado a la base",
            }
        )
    if not events:
        return 0
    history = pd.concat([history, pd.DataFrame(events)], ignore_index=True)
    save_contact_history(history)
    st.cache_data.clear()
    return len(events)


def contact_history_for_crm_id(crm_id: object) -> pd.DataFrame:
    history = load_contact_history()
    if history.empty:
        return history
    key = clean_text(crm_id)
    return history[history["CRM ID"].fillna("").astype(str) == key].copy()


def last_contact_datetime(row: pd.Series) -> pd.Timestamp | None:
    candidates = [
        row.get("Fecha ultimo contacto", ""),
        row.get("Fecha ultimo WhatsApp", ""),
        row.get("Fecha envio WhatsApp", ""),
    ]
    for value in candidates:
        parsed = pd.to_datetime(clean_text(value), errors="coerce", utc=True)
        if not pd.isna(parsed):
            return parsed
    return None


def should_show_no_response_alert(row: pd.Series) -> bool:
    if normalize_crm_state(row.get("Estado CRM", "")) != "Contactado":
        return False
    if normalize_resultado_seguimiento(row.get("Resultado seguimiento", ""), "") != "Sin respuesta":
        return False
    last_contact = last_contact_datetime(row)
    if last_contact is None:
        return False
    now_utc = pd.Timestamp.now(tz="UTC")
    return last_contact <= (now_utc - pd.Timedelta(days=3))


def has_no_response_alert_event(crm_id: object) -> bool:
    history = contact_history_for_crm_id(crm_id)
    if history.empty:
        return False
    return bool((history["Acción"].fillna("").astype(str) == "Alerta sin respuesta").any())


def generate_no_response_alerts(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    created = 0
    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    for _, row in df.iterrows():
        crm_id = clean_text(row.get("CRM ID", ""))
        if not crm_id or not should_show_no_response_alert(row) or has_no_response_alert_event(crm_id):
            continue
        append_contact_event(
            crm_id,
            "Sistema",
            "Alerta sin respuesta",
            {
                "Estado CRM": row.get("Estado CRM", ""),
                "Resultado seguimiento": row.get("Resultado seguimiento", ""),
            },
            "Lead sin respuesta después de 3 días",
            clean_text(row.get(name_col, "")),
        )
        created += 1
    return created


@st.cache_data(show_spinner=False)
def merge_crm(base: pd.DataFrame, crm: pd.DataFrame) -> pd.DataFrame:
    df = base.merge(crm, on="CRM ID", how="left", suffixes=("", "_crm"))
    for field in CRM_FIELDS:
        df[field] = df[field].fillna("")
    df["Estado CRM"] = normalize_crm_state_series(df["Estado CRM"])
    df["Estado CRM"] = df["Estado CRM"].replace({"Respondió": "Respondio"})
    df["Estado CRM"] = normalize_crm_state_series(df["Estado CRM"])
    df["Estado WhatsApp"] = df["Estado WhatsApp"].replace("", "No contactado")
    df["Estado WhatsApp"] = df["Estado WhatsApp"].replace({"Respondió": "Respondio", "No respondió": "No respondio"})
    for field in ["Respondio", "Interesado", "Reunion agendada"]:
        df[field] = df[field].replace("", "No")
    df["Resultado seguimiento"] = df["Resultado seguimiento"].apply(lambda value: normalize_resultado_seguimiento(value, ""))
    return df


def has_manual_interaction(row: pd.Series) -> bool:
    interaction_fields = [
        "Fecha ultimo WhatsApp",
        "Fecha envio WhatsApp",
        "Mensaje enviado",
        "Mensaje WhatsApp sugerido",
        "Observacion CRM",
        "Resultado comercial",
        "Resultado seguimiento",
        "Respondio",
        "Interesado",
        "Reunion agendada",
    ]
    for field in interaction_fields:
        value = clean_text(row.get(field, ""))
        if field in {"Respondio", "Interesado", "Reunion agendada"}:
            if value == "Si":
                return True
        elif value:
            return True
    return False


def auto_transition_pending_contacts(base: pd.DataFrame, crm: pd.DataFrame) -> bool:
    if base.empty:
        return False
    merged = merge_crm(base, crm)
    loaded_at = pd.to_datetime(merged["Fecha carga CRM"], errors="coerce", utc=True)
    now_utc = pd.Timestamp.now(tz="UTC")
    older_than_24h = loaded_at.notna() & (loaded_at <= (now_utc - pd.Timedelta(hours=24)))
    candidates = merged[
        (merged["Estado CRM"] == "Nuevo")
        & older_than_24h
        & (merged["Estado WhatsApp"] == "No contactado")
        & ~yes_no_has_value(merged["Fecha ultimo WhatsApp"])
        & ~merged.apply(has_manual_interaction, axis=1)
    ]
    if candidates.empty:
        return False

    updated = crm.copy()
    name_col = find_column(candidates, ["Nombre restaurante"]) or "Nombre restaurante"
    for crm_id in candidates["CRM ID"]:
        existing = updated[updated["CRM ID"] == crm_id].tail(1)
        current = {field: "" for field in CRM_FIELDS}
        current["CRM ID"] = crm_id
        if not existing.empty:
            current.update(existing.iloc[0].to_dict())
        current["Estado CRM"] = "Pendiente contacto"
        updated = updated[updated["CRM ID"] != crm_id]
        updated = pd.concat([updated, pd.DataFrame([current])], ignore_index=True)
        candidate_row = candidates[candidates["CRM ID"] == crm_id].tail(1)
        restaurant_name = clean_text(candidate_row.iloc[0].get(name_col, "")) if not candidate_row.empty else ""
        append_contact_event(
            crm_id,
            "Sistema",
            "Estado CRM cambiado automáticamente",
            current,
            "Nuevo → Pendiente contacto por regla 24h",
            restaurant_name,
            skip_if_same_event=True,
        )
    save_crm_state(updated)
    st.session_state["auto_pending_count"] = len(candidates)
    st.cache_data.clear()
    return True


def reset_lead_values(row: dict) -> dict:
    updated = {field: clean_text(row.get(field, "")) for field in CRM_FIELDS}
    updated["Estado CRM"] = "Nuevo"
    updated["Fecha ultimo contacto"] = ""
    updated["Canal ultimo contacto"] = ""
    updated["Proxima accion"] = ""
    updated["Fecha proxima accion"] = ""
    updated["Estado WhatsApp"] = "No contactado"
    updated["Fecha ultimo WhatsApp"] = ""
    updated["Fecha envio WhatsApp"] = ""
    updated["Mensaje WhatsApp sugerido"] = ""
    updated["Mensaje enviado"] = ""
    updated["Variante mensaje"] = ""
    updated["Respondio"] = "No"
    updated["Interesado"] = "No"
    updated["Reunion agendada"] = "No"
    updated["Resultado comercial"] = ""
    updated["Resultado seguimiento"] = ""
    return updated


def log_crm_reset(reset_type: str, count: int, cleaned_events: int = 0) -> None:
    CRM_RESET_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo_reset": reset_type,
        "cantidad_afectada": int(count),
        "eventos_contacto_eliminados": int(cleaned_events),
    }
    with CRM_RESET_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def empty_reset_history_stats() -> dict[str, int | str]:
    return {
        "data_mode": get_data_mode(),
        "total_before": 0,
        "target_before": 0,
        "kept_initial": 0,
        "deleted": 0,
        "total_after": 0,
    }


def initial_contact_history_mask(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=bool)
    action_col = "Acción" if "Acción" in history.columns else "Accion"
    actions = history[action_col].fillna("").astype(str).str.strip() if action_col in history.columns else pd.Series("", index=history.index)
    messages = history["Mensaje enviado"].fillna("").astype(str).str.strip() if "Mensaje enviado" in history.columns else pd.Series("", index=history.index)
    return actions.eq("Restaurante agregado") | messages.eq("Lead ingresado a la base")


def non_initial_history_ids() -> set[str]:
    history = load_contact_history()
    if history.empty or "CRM ID" not in history.columns:
        return set()
    initial_mask = initial_contact_history_mask(history)
    return set(history.loc[~initial_mask, "CRM ID"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna())


def contacted_history_ids() -> set[str]:
    history = load_contact_history()
    if history.empty or "CRM ID" not in history.columns:
        return set()
    non_initial = ~initial_contact_history_mask(history)
    contact_events = history["Canal"].fillna("").astype(str).isin(["WhatsApp", "Llamada"]) | history["Acción"].fillna("").astype(str).isin(
        ["WhatsApp abierto", "Llamada iniciada"]
    )
    return set(history.loc[non_initial & contact_events, "CRM ID"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna())



def clean_contact_history_after_reset(crm_ids: set[str]) -> dict[str, int | str]:
    ids = {clean_text(value) for value in crm_ids if clean_text(value)}
    stats = empty_reset_history_stats()
    if not ids:
        return stats
    if get_data_mode() == "supabase":
        stats = ds_clear_contact_history_for_leads(ids)
        st.cache_data.clear()
        st.session_state["contact_history_version"] = int(st.session_state.get("contact_history_version", 0)) + 1
        return stats

    history = load_contact_history()
    if history.empty:
        return stats
    stats["total_before"] = len(history)
    target_mask = history["CRM ID"].fillna("").astype(str).isin(ids)
    initial_mask = initial_contact_history_mask(history)
    delete_mask = target_mask & ~initial_mask
    stats["target_before"] = int(target_mask.sum())
    stats["kept_initial"] = int((target_mask & initial_mask).sum())
    stats["deleted"] = int(delete_mask.sum())
    if stats["deleted"]:
        save_contact_history(history.loc[~delete_mask].copy())
        st.cache_data.clear()
    stats["total_after"] = int(stats["total_before"]) - int(stats["deleted"])
    st.session_state["contact_history_version"] = int(st.session_state.get("contact_history_version", 0)) + 1
    return stats


def reset_crm_ids(affected_ids: set[str], reset_type: str) -> int:
    crm = load_crm_state()
    ids = {clean_text(value) for value in affected_ids if clean_text(value)}
    if not ids:
        log_crm_reset(reset_type, 0)
        st.session_state["reset_cleaned_events"] = 0
        st.session_state["last_reset_stats"] = empty_reset_history_stats()
        return 0
    crm = crm.copy()
    updated_rows = []
    for _, row in crm.iterrows():
        row_id = clean_text(row.get("CRM ID", ""))
        if row_id in ids:
            new_row = reset_lead_values(row.to_dict())
            new_row["CRM ID"] = row_id
            updated_rows.append(new_row)
        else:
            updated_rows.append(row.to_dict())
    existing_ids = {clean_text(row.get("CRM ID", "")) for row in updated_rows}
    for missing_id in sorted(ids - existing_ids):
        new_row = reset_lead_values({})
        new_row["CRM ID"] = missing_id
        updated_rows.append(new_row)
    save_crm_state(pd.DataFrame(updated_rows))
    stats = clean_contact_history_after_reset(ids)
    cleaned_events = int(stats.get("deleted", 0))
    st.session_state["reset_cleaned_events"] = cleaned_events
    st.session_state["last_reset_stats"] = stats
    log_crm_reset(reset_type, len(ids), cleaned_events)
    st.cache_data.clear()
    return len(ids)


def reset_crm_rows(mask: pd.Series, reset_type: str) -> int:
    crm = load_crm_state()
    if crm.empty or not mask.any():
        return reset_crm_ids(set(), reset_type)
    return reset_crm_ids(set(crm.loc[mask, "CRM ID"]), reset_type)


def reset_single_lead(crm_id: str) -> int:
    crm = load_crm_state()
    mask = crm["CRM ID"] == crm_id
    return reset_crm_rows(mask, "reset_individual")


def reset_massive_leads(option: str) -> int:
    crm = load_crm_state()
    history_ids = non_initial_history_ids()
    if crm.empty:
        if option == "contactados":
            return reset_crm_ids(contacted_history_ids(), "reset_masivo_contactados")
        return reset_crm_ids(history_ids if option == "todos" else set(), f"reset_masivo_{option}")
    estado = crm["Estado CRM"].fillna("").astype(str)
    estado_wa = crm["Estado WhatsApp"].fillna("").astype(str)
    if option == "contactados":
        mask = estado.isin(CONTACTED_STATES) | estado_wa.ne("No contactado")
        ids = set(crm.loc[mask, "CRM ID"]) | contacted_history_ids()
        return reset_crm_ids(ids, "reset_masivo_contactados")
    if option == "respondidos":
        mask = (crm["Respondio"].fillna("").astype(str) == "Si") | estado_wa.eq("Respondio")
        return reset_crm_rows(mask, "reset_masivo_respondidos")
    interaction_mask = (
        estado.ne("Nuevo")
        | estado_wa.ne("No contactado")
        | yes_no_has_value(crm["Fecha ultimo WhatsApp"])
        | yes_no_has_value(crm["Fecha envio WhatsApp"])
        | yes_no_has_value(crm["Mensaje enviado"])
        | yes_no_has_value(crm["Variante mensaje"])
        | (crm["Respondio"].fillna("").astype(str) == "Si")
        | (crm["Interesado"].fillna("").astype(str) == "Si")
        | (crm["Reunion agendada"].fillna("").astype(str) == "Si")
        | yes_no_has_value(crm["Resultado comercial"])
        | yes_no_has_value(crm["Resultado seguimiento"])
    )
    ids = set(crm.loc[interaction_mask, "CRM ID"]) | history_ids
    return reset_crm_ids(ids, "reset_masivo_todos_prueba")


def yes_no_has_value(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip() != ""


def metric_count(df: pd.DataFrame, column: str, value: str) -> int:
    if column not in df.columns:
        return 0
    return int((df[column].fillna("").astype(str) == value).sum())


def state_count(df: pd.DataFrame, states: list[str]) -> int:
    return int(df["Estado CRM"].isin(states).sum()) if "Estado CRM" in df.columns else 0


def format_mtime(path: Path) -> str:
    if not path.exists():
        return "No disponible"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")


def format_date_label(value: object) -> str:
    parsed = pd.to_datetime(clean_text(value), errors="coerce")
    if pd.isna(parsed):
        return clean_text(value)
    return parsed.strftime("%d-%m-%Y")


def make_table_view(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["Numero"] = range(1, len(df) + 1)
    out["Nombre"] = get_series(df, ["Nombre restaurante"])
    out["Comuna"] = get_series(df, ["Comuna"])
    out["Tipo negocio"] = get_series(df, ["Tipo negocio"])
    out["Nivel comercial"] = get_series(df, ["Nivel comercial"])
    out["Score comercial"] = get_series(df, ["Score comercial"])
    raw_phone = get_series(df, PHONE_COLUMNS)
    out["Telefono"] = raw_phone.apply(telefono_normalizado_display)
    out["Telefono normalizado"] = out["Telefono"]
    out["Telefono tipo"] = raw_phone.apply(telefono_tipo)
    out["WhatsApp disponible"] = raw_phone.apply(lambda value: "Si" if is_valid_whatsapp_phone(value) else "No")
    out["Instagram"] = get_series(df, ["Instagram URL"])
    out["Estado CRM"] = get_series(df, ["Estado CRM"])
    out["Resultado seguimiento"] = get_series(df, ["Resultado seguimiento"]).apply(lambda value: normalize_resultado_seguimiento(value, ""))
    out["Proxima accion"] = get_series(df, ["Proxima accion"])
    for col in ["Nombre", "Comuna", "Tipo negocio", "Nivel comercial", "Telefono", "Telefono normalizado", "Telefono tipo", "WhatsApp disponible", "Instagram", "Estado CRM", "Resultado seguimiento", "Proxima accion"]:
        out[col] = out[col].fillna("").astype(str).replace({"nan": "", "None": ""})
    return out


def logo_markup() -> str:
    if LOGO_PATH.exists():
        encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        return f'<img class="crm-logo" src="data:image/png;base64,{encoded}" alt="Rappi Leads CRM">'
    return '<div class="crm-logo-fallback">RL</div>'


def render_header() -> None:
    mode_label = "Supabase" if get_data_mode() == "supabase" else "Local"
    st.markdown(
        f"""
        <div class="crm-topbar">
            <div class="crm-brand">
                {logo_markup()}
                <div>
                    <div class="crm-title">Rappi Leads CRM</div>
                    <div class="crm-subtitle">Gestión comercial de restaurantes</div>
                </div>
            </div>
            <div class="crm-pill">Modo datos: {mode_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([0.84, 0.16])
    with left:
        user_label = current_user_email()
        suffix = f" · Usuario: {user_label}" if user_label else ""
        st.caption(f"Modo datos: {mode_label}{suffix}")
    with right:
        if st.button("Cerrar sesión", type="secondary", use_container_width=True, key="logout_button"):
            logout()
            st.rerun()


def render_login_screen() -> bool:
    st.markdown('<div class="login-top-space"></div>', unsafe_allow_html=True)
    _, login_col, _ = st.columns([1, 1.1, 1], gap="large")
    with login_col:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="login-brand">
                    {logo_markup()}
                    <div>
                        <div class="login-title">Rappi Leads CRM</div>
                        <div class="login-subtitle">Gestión comercial de restaurantes</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            try:
                auth_config()
            except RuntimeError as exc:
                st.error(str(exc))
                return False

            email = st.text_input(
                "Correo electrónico",
                key="login_email",
                placeholder="Ingresa tu correo",
            )
            password = st.text_input(
                "Contraseña",
                type="password",
                key="login_password",
                placeholder="Ingresa tu contraseña",
            )
            if st.button("Ingresar", type="primary", use_container_width=True, key="login_submit"):
                try:
                    if login(email, password):
                        st.rerun()
                    else:
                        st.error("Correo electrónico o contraseña incorrectos")
                except RuntimeError as exc:
                    st.error(str(exc))
    return False


def render_kpi_cards(kpis: list[tuple[str, object]], compact: bool = False) -> None:
    cards = []
    for label, value in kpis:
        cards.append(
            '<div class="kpi-card">'
            '<div>'
            '<div class="kpi-accent"></div>'
            f'<div class="kpi-label">{label}</div>'
            '</div>'
            f'<div class="kpi-value">{value}</div>'
            '</div>'
        )
    grid_class = "kpi-grid compact-grid" if compact else "kpi-grid"
    st.markdown(f'<div class="{grid_class}">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_panel_grid_spacer() -> None:
    st.markdown('<div class="panel-grid-spacer"></div>', unsafe_allow_html=True)


def render_links(row: pd.Series) -> None:
    links = []
    wa = whatsapp_url(row.get(find_column(pd.DataFrame([row]), ["Telefono", "Teléfono", "Tel?fono"]) or "Telefono", ""))
    if wa:
        links.append(f"[WhatsApp]({wa})")
    for label, names in [
        ("Instagram", ["Instagram URL"]),
        ("Facebook", ["Facebook URL"]),
        ("Google Maps", ["Google Maps URL"]),
        ("Sitio web", ["Sitio web"]),
    ]:
        col = find_column(pd.DataFrame([row]), names)
        value = clean_text(row.get(col, "")) if col else ""
        if value:
            links.append(f"[{label}]({value})")
    st.markdown(" · ".join(links) if links else "Sin links disponibles")


def apply_crm_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="crm-section-title">Filtros comerciales</div>', unsafe_allow_html=True)
    row1 = st.columns(4, gap="small")
    row2 = st.columns(4, gap="small")
    comunas = sorted([x for x in get_series(df, ["Comuna"]).dropna().unique() if clean_text(x)])
    niveles = sorted([x for x in get_series(df, ["Nivel comercial"]).dropna().unique() if clean_text(x)])
    tipos = sorted([x for x in get_series(df, ["Tipo negocio"]).dropna().unique() if clean_text(x)])
    fechas = sorted([x for x in df["Fecha carga CRM"].dropna().unique() if clean_text(x)], reverse=True)

    selected_comunas = row1[0].multiselect("Comuna", comunas, placeholder="Seleccionar")
    selected_niveles = row1[1].multiselect("Nivel comercial", niveles, placeholder="Seleccionar")
    selected_tipos = row1[2].multiselect("Tipo negocio", tipos, placeholder="Seleccionar")
    selected_states = row1[3].multiselect("Estado CRM", CRM_STATES, placeholder="Seleccionar")
    phone_filter = row2[0].selectbox("Tiene teléfono", ["Todos", "Sí", "No"])
    instagram_filter = row2[1].selectbox("Tiene Instagram", ["Todos", "Sí", "No"])
    selected_resultados = row2[2].multiselect("Resultado seguimiento", RESULTADO_SEGUIMIENTO_OPTIONS, placeholder="Seleccionar")
    selected_dates = row2[3].multiselect("Fecha de carga", fechas, placeholder="Seleccionar")
    search = st.text_input("Buscar restaurante")

    out = df.copy()
    if selected_comunas:
        out = out[out[find_column(out, ["Comuna"])].isin(selected_comunas)]
    if selected_niveles:
        out = out[out[find_column(out, ["Nivel comercial"])].isin(selected_niveles)]
    if selected_tipos:
        out = out[out[find_column(out, ["Tipo negocio"])].isin(selected_tipos)]
    if selected_states:
        out = out[out["Estado CRM"].isin(selected_states)]
    if selected_resultados:
        selected_norm = {normalize_resultado_seguimiento(value, "") for value in selected_resultados}
        resultado_source = out["Resultado seguimiento"] if "Resultado seguimiento" in out.columns else pd.Series([""] * len(out), index=out.index)
        resultado_series = resultado_source.apply(lambda value: normalize_resultado_seguimiento(value, ""))
        out = out[resultado_series.isin(selected_norm)]
    if selected_dates:
        out = out[out["Fecha carga CRM"].isin(selected_dates)]
    if phone_filter != "Todos":
        has_phone = yes_no_has_value(get_series(out, ["Telefono", "Teléfono", "Tel?fono"]))
        out = out[has_phone if phone_filter == "Sí" else ~has_phone]
    if instagram_filter != "Todos":
        has_ig = yes_no_has_value(get_series(out, ["Instagram URL"]))
        out = out[has_ig if instagram_filter == "Sí" else ~has_ig]
    if search:
        name_col = find_column(out, ["Nombre restaurante"])
        if name_col:
            out = out[out[name_col].fillna("").astype(str).str.contains(search, case=False, na=False)]
    return out


def render_kpis(df: pd.DataFrame) -> None:
    latest_date = df["Fecha carga CRM"].max() if "Fecha carga CRM" in df.columns and not df.empty else ""
    latest_count = int((df["Fecha carga CRM"] == latest_date).sum()) if latest_date else 0
    kpis = [
        ("Total restaurantes", len(df)),
        ("Alto potencial", metric_count(df, "Nivel comercial", "Alto potencial")),
        ("Pendientes contacto", state_count(df, PENDING_STATES)),
        ("Contactados", state_count(df, CONTACTED_STATES)),
        ("Negociando", metric_count(df, "Resultado seguimiento", "Negociando")),
        ("Nuevos última carga", latest_count),
    ]
    render_kpi_cards(kpis)


def render_status_summary(df: pd.DataFrame) -> None:
    st.markdown('<div class="crm-section-title">Seguimiento por estado CRM</div>', unsafe_allow_html=True)
    phone_col = find_column(df, ["Telefono", "Teléfono", "Tel?fono"]) or "CRM ID"
    ig_col = find_column(df, ["Instagram URL"]) or "CRM ID"
    grouped = (
        df.groupby("Estado CRM", dropna=False)
        .agg(
            Leads=("CRM ID", "count"),
            Con_telefono=(phone_col, lambda s: int(yes_no_has_value(s).sum())),
            Con_Instagram=(ig_col, lambda s: int(yes_no_has_value(s).sum())),
        )
        .reset_index()
        .rename(columns={"Con_telefono": "Con teléfono", "Con_Instagram": "Con Instagram"})
        .sort_values("Leads", ascending=False)
    )
    st.dataframe(grouped, use_container_width=True, hide_index=True, height=210)


def apply_search_filter() -> None:
    st.session_state["texto_aplicado_buscador"] = st.session_state.get("texto_temporal_buscador", "")


def clear_search_filter() -> None:
    st.session_state["buscador_restaurante_select"] = "Todos los restaurantes"
    st.session_state["texto_temporal_buscador"] = ""
    st.session_state["texto_aplicado_buscador"] = ""


def query_values(name: str) -> list[str]:
    try:
        return [clean_text(value) for value in st.query_params.get_all(name) if clean_text(value)]
    except Exception:
        value = st.query_params.get(name, "")
        if isinstance(value, list):
            return [clean_text(item) for item in value if clean_text(item)]
        return [clean_text(value)] if clean_text(value) else []


def restore_commercial_filters_from_query(
    search_options: list[str],
    comunas: list[str],
    niveles: list[str],
    states: list[str],
    resultados: list[str] | None = None,
) -> None:
    selection_key = clean_text(st.query_params.get("selected_lead_key", ""))
    should_restore = bool(selection_key) and st.session_state.get("last_restored_filter_selection_key") != selection_key

    search = clean_text(st.query_params.get("filtro_nombre", "")) if should_restore else ""
    if should_restore and search in search_options:
        st.session_state["buscador_restaurante_select"] = search
    elif "buscador_restaurante_select" not in st.session_state:
        st.session_state["buscador_restaurante_select"] = "Todos los restaurantes"

    multi_filters = {
        "crm_top_comuna": ("filtro_comuna", comunas),
        "crm_top_nivel": ("filtro_nivel", niveles),
        "crm_top_estado": ("filtro_estado", states),
        "crm_top_resultado": ("filtro_resultado", resultados or []),
    }
    for session_key, (query_key, valid_options) in multi_filters.items():
        values = [value for value in query_values(query_key) if value in valid_options] if should_restore else []
        if should_restore:
            st.session_state[session_key] = values
        elif session_key not in st.session_state:
            st.session_state[session_key] = []

    for session_key, query_key in {
        "crm_top_phone": "filtro_telefono",
        "crm_top_whatsapp": "filtro_whatsapp",
    }.items():
        value = clean_text(st.query_params.get(query_key, "")) if should_restore else ""
        if should_restore and value in {"Todos", "Si", "No"}:
            st.session_state[session_key] = value
        elif session_key not in st.session_state:
            st.session_state[session_key] = "Si" if session_key == "crm_top_whatsapp" else "Todos"

    if should_restore:
        st.session_state["last_restored_filter_selection_key"] = selection_key


def current_commercial_filter_params() -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    search = clean_text(st.session_state.get("buscador_restaurante_select", "Todos los restaurantes"))
    if search and search != "Todos los restaurantes":
        params.append(("filtro_nombre", search))
    for session_key, query_key in {
        "crm_top_comuna": "filtro_comuna",
        "crm_top_nivel": "filtro_nivel",
        "crm_top_estado": "filtro_estado",
        "crm_top_resultado": "filtro_resultado",
    }.items():
        for value in st.session_state.get(session_key, []) or []:
            if clean_text(value):
                params.append((query_key, clean_text(value)))
    for session_key, query_key in {
        "crm_top_phone": "filtro_telefono",
        "crm_top_whatsapp": "filtro_whatsapp",
    }.items():
        value = clean_text(st.session_state.get(session_key, "Todos"))
        if value and value != "Todos":
            params.append((query_key, value))
    return params
    st.session_state["sugerencia_buscador"] = ""
    st.session_state["buscador_restaurante_select"] = "Todos los restaurantes"


def apply_selected_search_suggestion() -> None:
    suggestion = clean_text(st.session_state.get("sugerencia_buscador", ""))
    if suggestion:
        st.session_state["texto_temporal_buscador"] = suggestion
        st.session_state["texto_aplicado_buscador"] = suggestion


def render_lead_editor(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    st.markdown('<div class="crm-section-title">Editar lead</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes con los filtros actuales.")
        return

    name_col = find_column(filtered, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(filtered, ["Comuna"]) or "Comuna"
    options = filtered[name_col].fillna("").astype(str) + " | " + filtered[comuna_col].fillna("").astype(str)
    selected_label = st.selectbox("Selecciona un restaurante", options.tolist())
    selected_index = options[options == selected_label].index[0]
    row = df.loc[selected_index]

    left, right = st.columns([1, 1])
    with left:
        st.markdown(f"### {row.get(name_col, '')}")
        st.write(f"**Comuna:** {row.get(comuna_col, '')}")
        st.write(f"**Nivel comercial:** {row.get(find_column(df, ['Nivel comercial']) or 'Nivel comercial', '')}")
        st.write(f"**Tipo negocio:** {row.get(find_column(df, ['Tipo negocio']) or 'Tipo negocio', '')}")
        st.write(f"**Fecha de carga:** {format_date_label(row.get('Fecha carga CRM', ''))}")
        render_links(row)

    with right:
        current_state = row.get("Estado CRM", "Nuevo") if row.get("Estado CRM", "Nuevo") in CRM_STATES else "Nuevo"
        estado = st.selectbox("Estado del lead", CRM_STATES, index=CRM_STATES.index(current_state))
        responsable = st.text_input("Responsable", value=clean_text(row.get("Responsable", "")))
        observacion = st.text_area("Notas comerciales", value=clean_text(row.get("Observacion CRM", "")), height=110)
        proxima = st.text_input("Próxima acción", value=clean_text(row.get("Proxima accion", "")))
        fecha_ultimo = st.date_input("Fecha último contacto", value=None)
        fecha_proxima = st.date_input("Fecha próxima acción", value=None)

        if st.button("Guardar cambios", type="primary"):
            crm_current = load_crm_state()
            crm_current = crm_current[crm_current["CRM ID"] != row["CRM ID"]]
            new_row = {
                "CRM ID": row["CRM ID"],
                "Estado CRM": estado,
                "Fecha ultimo contacto": fecha_ultimo.isoformat() if isinstance(fecha_ultimo, date) else clean_text(row.get("Fecha ultimo contacto", "")),
                "Responsable": responsable,
                "Observacion CRM": observacion,
                "Proxima accion": proxima,
                "Fecha proxima accion": fecha_proxima.isoformat() if isinstance(fecha_proxima, date) else clean_text(row.get("Fecha proxima accion", "")),
            }
            crm_current = pd.concat([crm_current, pd.DataFrame([new_row])], ignore_index=True)
            save_crm_state(crm_current)
            st.cache_data.clear()
            st.success("Cambios guardados.")
            st.rerun()


def render_crm_comercial(df: pd.DataFrame) -> None:
    render_kpis(df)
    filtered = apply_crm_filters(df)
    st.markdown('<div class="crm-section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.write(f"Mostrando {len(filtered)} de {len(df)} restaurantes")
    table = make_table_view(filtered)
    visible = [col for col in COMMERCIAL_TABLE_COLUMNS if col in table.columns]
    st.dataframe(
        table[visible],
        use_container_width=True,
        hide_index=True,
        height=430,
        column_config={
            "Nombre": st.column_config.TextColumn("Nombre", width="large"),
            "Comuna": st.column_config.TextColumn("Comuna", width="small"),
            "Tipo negocio": st.column_config.TextColumn("Tipo negocio", width="medium"),
            "Nivel comercial": st.column_config.TextColumn("Nivel comercial", width="medium"),
            "Score comercial": st.column_config.NumberColumn("Score", width="small", format="%.0f"),
            "Telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "WhatsApp disponible": st.column_config.TextColumn("WhatsApp", width="small"),
            "Instagram": st.column_config.LinkColumn("Instagram", width="medium", display_text="Abrir"),
            "Estado CRM": st.column_config.TextColumn("Estado CRM", width="medium"),
            "Proxima accion": st.column_config.TextColumn("Próxima acción", width="large"),
        },
    )
    render_status_summary(filtered)
    render_lead_editor(df, filtered)


def load_manual_config() -> dict:
    if not MANUAL_CONFIG.exists():
        return {}
    return json.loads(MANUAL_CONFIG.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9áéíóúñü]+", "_", text)
    return text.strip("_") or "comuna"


def comuna_options(base: pd.DataFrame, config: dict) -> list[dict]:
    items: dict[str, dict] = {}
    for item in config.get("comunas", []):
        name = clean_text(item.get("comuna"))
        if name:
            items[name] = {
                "comuna": name,
                "region": clean_text(item.get("region")) or "Metropolitana",
                "pais": clean_text(item.get("pais")) or "Chile",
                "busqueda": clean_text(item.get("busqueda")) or "restaurantes",
                "slug": clean_text(item.get("slug")) or slugify(name),
            }

    comuna_col = find_column(base, ["Comuna"])
    region_col = find_column(base, ["Region", "Región", "Regi?n"])
    pais_col = find_column(base, ["Pais", "País", "Pa?s"])
    if comuna_col:
        cols = [c for c in [comuna_col, region_col, pais_col] if c]
        for _, row in base[cols].drop_duplicates().iterrows():
            name = clean_text(row.get(comuna_col))
            if name and name not in items:
                items[name] = {
                    "comuna": name,
                    "region": clean_text(row.get(region_col)) if region_col else "Metropolitana",
                    "pais": clean_text(row.get(pais_col)) if pais_col else "Chile",
                    "busqueda": "restaurantes",
                    "slug": slugify(name),
                }
    return [items[key] for key in sorted(items)]


def write_ui_config(config: dict, selected: list[dict], objetivo: int, max_resultados: int, max_scrolls: int) -> Path:
    run_config = dict(config)
    run_config["modoPrueba"] = False
    run_config["maxNuevosObjetivo"] = int(objetivo)
    run_config["maxResultadosPorComuna"] = int(max_resultados)
    run_config["maxScrollsPorComuna"] = int(max_scrolls)
    run_config["pausaMinMs"] = max(int(run_config.get("pausaMinMs", 2000)), 2000)
    run_config["pausaMaxMs"] = max(int(run_config.get("pausaMaxMs", 5000)), run_config["pausaMinMs"])
    run_config["detenerSiCaptchaOBloqueo"] = True
    run_config["log"] = "data/logs/actualizacion_incremental_crm_ui.log"
    run_config["comunas"] = selected
    UI_RUN_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    UI_RUN_CONFIG.write_text(json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8")
    return UI_RUN_CONFIG


def parse_summary(output: str) -> dict[str, int]:
    patterns = {
        "totalAntes": r"total base antes:\s*(\d+)",
        "encontrados": r"resultados encontrados en la corrida:\s*(\d+)",
        "insertados": r"nuevos insertados:\s*(\d+)",
        "duplicados": r"duplicados ignorados:\s*(\d+)",
        "errores": r"errores:\s*(\d+)",
        "totalFinal": r"total base final:\s*(\d+)",
    }
    summary = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output, flags=re.IGNORECASE)
        summary[key] = int(match.group(1)) if match else 0
    return summary


def is_update_running() -> bool:
    if not UPDATE_LOCK.exists():
        return False
    age_seconds = datetime.now().timestamp() - UPDATE_LOCK.stat().st_mtime
    if age_seconds > 6 * 60 * 60:
        UPDATE_LOCK.unlink(missing_ok=True)
        return False
    return True


def run_update(config_path: Path) -> tuple[int, str, dict[str, int]]:
    UPDATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_LOCK.write_text(datetime.now().isoformat(), encoding="utf-8")
    try:
        result = subprocess.run(
            [str(NODE_EXE), str(ROOT / "scripts" / "10_actualizar_incremental.js"), "--config", str(config_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = "\n".join([result.stdout or "", result.stderr or ""]).strip()
        return result.returncode, output, parse_summary(output)
    finally:
        UPDATE_LOCK.unlink(missing_ok=True)


def start_update_process(config_path: Path) -> None:
    UPDATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_LOCK.write_text(datetime.now().isoformat(), encoding="utf-8")
    stdout_handle = UI_STDOUT_LOG.open("w", encoding="utf-8", errors="replace")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [str(NODE_EXE), str(ROOT / "scripts" / "10_actualizar_incremental.js"), "--config", str(config_path)],
        cwd=ROOT,
        stdout=stdout_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    st.session_state["update_process"] = process
    st.session_state["update_stdout_handle"] = stdout_handle
    st.session_state["last_update_status"] = "Búsqueda en curso"
    st.session_state.pop("last_update_summary", None)
    st.session_state.pop("last_update_output", None)


def close_update_stdout_handle() -> None:
    handle = st.session_state.pop("update_stdout_handle", None)
    if handle:
        try:
            handle.close()
        except Exception:
            pass


def read_update_stdout() -> str:
    if UI_STDOUT_LOG.exists():
        return UI_STDOUT_LOG.read_text(encoding="utf-8", errors="replace")
    return ""


def finalize_update_process_if_done() -> bool:
    process = st.session_state.get("update_process")
    if not process:
        return False
    return_code = process.poll()
    if return_code is None:
        return False

    close_update_stdout_handle()
    output = read_update_stdout()
    summary = parse_summary(output)
    text_to_check = output.lower()

    if "captcha" in text_to_check or "bloqueo" in text_to_check or "blocked" in text_to_check:
        st.session_state["last_update_status"] = "Se detectó una señal de captcha o bloqueo. Espera antes de volver a intentar."
    elif return_code == 0:
        st.session_state["last_update_status"] = "Se agregaron los restaurantes nuevos encontrados y se ignoraron duplicados."
    else:
        st.session_state["last_update_status"] = "La búsqueda terminó con errores. Revisa el último log."

    st.session_state["last_update_output"] = output
    st.session_state["last_update_summary"] = summary
    st.session_state.pop("update_process", None)
    UPDATE_LOCK.unlink(missing_ok=True)
    st.cache_data.clear()
    return True


@st.fragment(run_every="5s")
def poll_update_process() -> None:
    if is_update_process_running():
        st.caption("Revisando estado de la búsqueda...")
        return
    if st.session_state.get("update_process") and finalize_update_process_if_done():
        st.rerun()


def is_update_process_running() -> bool:
    process = st.session_state.get("update_process")
    return bool(process and process.poll() is None)


def cancel_update_process() -> None:
    process = st.session_state.get("update_process")
    if process and process.poll() is None:
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, text=True)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
    close_update_stdout_handle()
    st.session_state.pop("update_process", None)
    st.session_state["last_update_status"] = "Búsqueda cancelada por el usuario."
    st.session_state.pop("last_update_summary", None)
    UPDATE_LOCK.unlink(missing_ok=True)


def read_latest_log() -> str:
    if UI_LOG.exists():
        text = UI_LOG.read_text(encoding="utf-8", errors="replace")
    else:
        logs = sorted((ROOT / "data" / "logs").glob("actualizacion_incremental*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        text = logs[0].read_text(encoding="utf-8", errors="replace") if logs else ""
    lines = text.splitlines()
    return "\n".join(lines[-160:])


def latest_update_summary() -> dict[str, int]:
    log_text = read_latest_log()
    json_matches = re.findall(r"Resumen final:\s*(\{.*?\})", log_text)
    if json_matches:
        try:
            parsed = json.loads(json_matches[-1])
            return {key: int(parsed.get(key, 0) or 0) for key in SUMMARY_LABELS}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return parse_summary(log_text)


def open_excel_file() -> tuple[bool, str]:
    if not BASE_XLSX.exists():
        return False, "No se encontró el Excel actualizado."
    try:
        import os

        os.startfile(BASE_XLSX)  # type: ignore[attr-defined]
        return True, "Excel abierto."
    except Exception as error:
        return False, f"No se pudo abrir automáticamente. Ruta: {BASE_XLSX}. Detalle: {error}"


def render_update_base(base: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="crm-card">
            <h3>Buscar restaurantes nuevos</h3>
            <p>Elige comunas y límites seguros. La app revisa Google Maps, agrega nuevos restaurantes y evita duplicados.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_kpi_cards(
        [
            ("Restaurantes actuales", len(base)),
            ("?ltima actualización", format_mtime(BASE_XLSX)),
            ("?ltima búsqueda", format_mtime(UI_LOG if UI_LOG.exists() else BASE_XLSX)),
        ],
        compact=True,
    )

    config = load_manual_config()
    if not config:
        st.error(f"No se encontró la configuración: {MANUAL_CONFIG}")
        return

    options = comuna_options(base, config)
    names = [item["comuna"] for item in options]
    default_names = [item["comuna"] for item in config.get("comunas", []) if item.get("comuna") in names] or names[:1]

    st.markdown('<div class="crm-section-title">Configuración de búsqueda</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        objetivo = st.number_input("Objetivo nuevos", min_value=1, max_value=50, value=10, step=1)
        st.caption("Máximo de restaurantes nuevos que intentaremos agregar.")
    with c2:
        max_resultados = st.number_input("Máximo resultados por comuna", min_value=1, max_value=50, value=min(int(config.get("maxResultadosPorComuna", 15)), 50), step=1)
        st.caption("Restaurantes que se revisarán por cada comuna.")
    with c3:
        max_scrolls = st.number_input("Scrolls máximos", min_value=1, max_value=10, value=min(int(config.get("maxScrollsPorComuna", 4)), 10), step=1)
        st.caption("Veces que bajará en la lista para encontrar más locales.")

    selected_names = st.multiselect("Comunas a actualizar", names, default=default_names)
    selected = [item for item in options if item["comuna"] in selected_names]

    st.markdown(
        '<div class="crm-note">La búsqueda es lenta y segura: no duplica restaurantes y se detiene si aparece captcha o bloqueo.</div>',
        unsafe_allow_html=True,
    )

    running = is_update_running()
    if running:
        st.warning("Ya hay una búsqueda en curso. Espera a que termine.")

    primary, secondary = st.columns([0.36, 0.64])
    if primary.button("Buscar nuevos restaurantes", type="primary", disabled=running or not selected):
        config_path = write_ui_config(config, selected, int(objetivo), int(max_resultados), int(max_scrolls))
        with st.spinner("Buscando nuevos restaurantes. Puede tardar varios minutos."):
            return_code, output, summary = run_update(config_path)

        text_to_check = output.lower()
        if "captcha" in text_to_check or "bloqueo" in text_to_check or "blocked" in text_to_check:
            st.error("Apareció una señal de captcha o bloqueo. Espera antes de volver a intentar.")
        elif return_code == 0:
            st.success("Búsqueda terminada.")
        else:
            st.error("La búsqueda terminó con errores. Revisa el resumen.")

        cols = st.columns(6)
        for col, key in zip(cols, ["totalAntes", "encontrados", "insertados", "duplicados", "errores", "totalFinal"]):
            col.metric(SUMMARY_LABELS[key], summary.get(key, 0))
        st.session_state["last_update_output"] = output
        st.cache_data.clear()

    if secondary.button("Actualizar datos en pantalla"):
        st.cache_data.clear()
        st.rerun()

    with st.expander("Ver registro de la última búsqueda", expanded=False):
        st.code(read_latest_log() or "Aún no hay registros de búsqueda.", language="text")


def render_update_base(base: pd.DataFrame) -> None:
    config = load_manual_config()
    if not config:
        st.error(f"No se encontró la configuración: {MANUAL_CONFIG}")
        return

    options = comuna_options(base, config)
    names = [item["comuna"] for item in options]
    default_names = [item["comuna"] for item in config.get("comunas", []) if item.get("comuna") in names] or names[:1]
    last_summary = st.session_state.get("last_update_summary") or latest_update_summary()

    st.markdown(
        """
        <div class="update-grid">
            <div class="update-panel">
                <h3>Buscar restaurantes nuevos</h3>
                <p>Configura una búsqueda pequeña y agrega solo locales que no existan en la base.</p>
            </div>
            <div class="update-panel">
                <h3>Resumen actual</h3>
                <p>Vista rápida del Excel principal y la última búsqueda realizada.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="compact-kpis">', unsafe_allow_html=True)
    render_kpi_cards(
        [
            ("Total restaurantes", len(base)),
            ("?ltima actualización", format_mtime(BASE_XLSX)),
            ("Últimos nuevos agregados", last_summary.get("insertados", 0)),
        ],
        compact=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="crm-section-title">Configuración rápida</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([0.16, 0.2, 0.16, 0.48], gap="small")
    with c1:
        objetivo = st.number_input("Objetivo", min_value=1, max_value=50, value=10, step=1, help="Cantidad máxima de restaurantes nuevos que se intentará agregar.")
    with c2:
        max_resultados = st.number_input(
            "Resultados/comuna",
            min_value=1,
            max_value=50,
            value=min(int(config.get("maxResultadosPorComuna", 15)), 50),
            step=1,
            help="Cantidad de restaurantes que se revisarán por cada comuna seleccionada.",
        )
    with c3:
        max_scrolls = st.number_input(
            "Scrolls",
            min_value=1,
            max_value=10,
            value=min(int(config.get("maxScrollsPorComuna", 4)), 10),
            step=1,
            help="Veces que baja en Google Maps para encontrar más locales.",
        )
    with c4:
        selected_names = st.multiselect("Comunas", names, default=default_names, placeholder="Seleccionar comunas", help="Comunas donde se buscarán restaurantes nuevos.")
    selected = [item for item in options if item["comuna"] in selected_names]

    with st.expander("¿Qué significa cada opción?", expanded=False):
        st.write("**Objetivo:** máximo de restaurantes nuevos que se intentará agregar.")
        st.write("**Resultados/comuna:** cuántos restaurantes revisará por comuna seleccionada.")
        st.write("**Scrolls:** veces que baja en Google Maps para encontrar más locales.")
        st.write("**Comunas:** lugares donde se buscarán restaurantes nuevos.")
        st.write("La búsqueda evita duplicados y se detiene si aparece captcha o bloqueo.")

    running = is_update_running()
    if running:
        st.warning("Ya hay una búsqueda en curso. Espera a que termine.")

    st.markdown('<div class="crm-section-title">Acciones</div>', unsafe_allow_html=True)
    primary, secondary, third, fourth = st.columns([0.27, 0.22, 0.18, 0.23], gap="small")
    if primary.button("Buscar nuevos restaurantes", type="primary", disabled=running or not selected, use_container_width=True):
        config_path = write_ui_config(config, selected, int(objetivo), int(max_resultados), int(max_scrolls))
        with st.spinner("Buscando nuevos restaurantes. Puede tardar varios minutos."):
            return_code, output, summary = run_update(config_path)

        text_to_check = output.lower()
        if "captcha" in text_to_check or "bloqueo" in text_to_check or "blocked" in text_to_check:
            st.error("Apareció una señal de captcha o bloqueo. Espera antes de volver a intentar.")
        elif return_code == 0:
            st.success("Búsqueda terminada.")
        else:
            st.error("La búsqueda terminó con errores. Revisa el resumen.")

        st.session_state["last_update_output"] = output
        st.session_state["last_update_summary"] = summary
        st.cache_data.clear()

    if secondary.button("Actualizar pantalla", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if third.button("Ver último log", use_container_width=True):
        st.session_state["show_update_log"] = not st.session_state.get("show_update_log", False)

    if fourth.button("Abrir Excel actualizado", use_container_width=True, disabled=not BASE_XLSX.exists()):
        ok, message = open_excel_file()
        if ok:
            st.success(message)
        else:
            st.warning(message)

    current_summary = st.session_state.get("last_update_summary") or latest_update_summary()
    st.markdown('<div class="crm-section-title">Resultado última ejecución</div>', unsafe_allow_html=True)
    st.markdown('<div class="compact-kpis">', unsafe_allow_html=True)
    render_kpi_cards(
        [
            ("Nuevos agregados", current_summary.get("insertados", 0)),
            ("Duplicados ignorados", current_summary.get("duplicados", 0)),
            ("Errores", current_summary.get("errores", 0)),
            ("Base final", current_summary.get("totalFinal", len(base)) or len(base)),
        ]
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("show_update_log", False):
        st.code(read_latest_log() or "Aún no hay registros de búsqueda.", language="text")


def render_update_base_compact(base: pd.DataFrame) -> None:
    config = load_manual_config()
    if not config:
        st.error(f"No se encontró la configuración: {MANUAL_CONFIG}")
        return

    options = comuna_options(base, config)
    names = [item["comuna"] for item in options]
    default_names = [item["comuna"] for item in config.get("comunas", []) if item.get("comuna") in names] or names[:1]
    last_summary = st.session_state.get("last_update_summary") or latest_update_summary()

    st.markdown('<div class="update-shell">', unsafe_allow_html=True)
    st.markdown('<div class="crm-section-title">Resumen actual</div>', unsafe_allow_html=True)
    st.markdown('<div class="compact-kpis">', unsafe_allow_html=True)
    render_kpi_cards(
        [
            ("Total restaurantes", len(base)),
            ("?ltima actualización", format_mtime(BASE_XLSX)),
            ("Últimos nuevos agregados", last_summary.get("insertados", 0)),
        ]
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="crm-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="crm-section-title">Configuración de búsqueda</div>', unsafe_allow_html=True)
    st.markdown('<div class="update-controls">', unsafe_allow_html=True)
    objetivo = st.number_input(
        "Objetivo",
        min_value=1,
        max_value=50,
        value=10,
        step=1,
        help="Cantidad máxima de restaurantes nuevos que se intentará agregar.",
    )
    max_resultados = st.number_input(
        "Resultados/comuna",
        min_value=1,
        max_value=50,
        value=min(int(config.get("maxResultadosPorComuna", 15)), 50),
        step=1,
        help="Cantidad de restaurantes que se revisarán por cada comuna seleccionada.",
    )
    max_scrolls = st.number_input(
        "Scrolls",
        min_value=1,
        max_value=10,
        value=min(int(config.get("maxScrollsPorComuna", 4)), 10),
        step=1,
        help="Veces que baja en Google Maps para encontrar más locales.",
    )
    selected_names = st.multiselect(
        "Comunas",
        names,
        default=default_names,
        placeholder="Seleccionar comunas",
        help="Comunas donde se buscarán restaurantes nuevos.",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    selected = [item for item in options if item["comuna"] in selected_names]

    with st.expander("¿Qué significa cada opción?", expanded=False):
        st.write("**Objetivo:** máximo de restaurantes nuevos que se intentará agregar.")
        st.write("**Resultados/comuna:** cuántos restaurantes revisará por comuna seleccionada.")
        st.write("**Scrolls:** veces que baja en Google Maps para encontrar más locales.")
        st.write("**Comunas:** lugares donde se buscarán restaurantes nuevos.")
        st.write("La búsqueda evita duplicados y se detiene si aparece captcha o bloqueo.")

    running = is_update_running()
    if running:
        st.warning("Ya hay una búsqueda en curso. Espera a que termine.")

    st.markdown('<div class="crm-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="crm-section-title">Acciones</div>', unsafe_allow_html=True)
    st.markdown('<div class="update-actions">', unsafe_allow_html=True)
    if st.button("Buscar nuevos restaurantes", type="primary", disabled=running or not selected, use_container_width=True):
        config_path = write_ui_config(config, selected, int(objetivo), int(max_resultados), int(max_scrolls))
        with st.spinner("Buscando nuevos restaurantes. Puede tardar varios minutos."):
            return_code, output, summary = run_update(config_path)

        text_to_check = output.lower()
        if "captcha" in text_to_check or "bloqueo" in text_to_check or "blocked" in text_to_check:
            st.error("Apareció una señal de captcha o bloqueo. Espera antes de volver a intentar.")
        elif return_code == 0:
            st.success("Búsqueda terminada.")
        else:
            st.error("La búsqueda terminó con errores. Revisa el resumen.")

        st.session_state["last_update_output"] = output
        st.session_state["last_update_summary"] = summary
        st.cache_data.clear()

    if st.button("Actualizar pantalla", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("Ver último log", use_container_width=True):
        st.session_state["show_update_log"] = not st.session_state.get("show_update_log", False)

    if st.button("Abrir Excel actualizado", use_container_width=True, disabled=not BASE_XLSX.exists()):
        ok, message = open_excel_file()
        if ok:
            st.success(message)
        else:
            st.warning(message)
    st.markdown("</div>", unsafe_allow_html=True)

    current_summary = st.session_state.get("last_update_summary") or latest_update_summary()
    st.markdown('<div class="crm-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="crm-section-title">Resultado última ejecución</div>', unsafe_allow_html=True)
    st.markdown('<div class="compact-kpis">', unsafe_allow_html=True)
    render_kpi_cards(
        [
            ("Nuevos agregados", current_summary.get("insertados", 0)),
            ("Duplicados ignorados", current_summary.get("duplicados", 0)),
            ("Errores", current_summary.get("errores", 0)),
            ("Base final", current_summary.get("totalFinal", len(base)) or len(base)),
        ]
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("show_update_log", False):
        st.code(read_latest_log() or "Aún no hay registros de búsqueda.", language="text")
    st.markdown("</div>", unsafe_allow_html=True)


def render_update_base_panel(base: pd.DataFrame) -> None:
    panel, _ = st.columns([0.68, 0.32])
    with panel:
        render_update_base_compact(base)


def apply_crm_filters_side_panel(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="section-title">Filtros comerciales</div>', unsafe_allow_html=True)
    comunas = sorted([x for x in get_series(df, ["Comuna"]).dropna().unique() if clean_text(x)])
    niveles = sorted([x for x in get_series(df, ["Nivel comercial"]).dropna().unique() if clean_text(x)])
    tipos = sorted([x for x in get_series(df, ["Tipo negocio"]).dropna().unique() if clean_text(x)])
    fechas = sorted([x for x in df["Fecha carga CRM"].dropna().unique() if clean_text(x)], reverse=True)

    selected_comunas = st.multiselect("Comuna", comunas, placeholder="Seleccionar", key="crm_filter_comuna")
    selected_niveles = st.multiselect("Nivel comercial", niveles, placeholder="Seleccionar", key="crm_filter_nivel")
    selected_tipos = st.multiselect("Tipo negocio", tipos, placeholder="Seleccionar", key="crm_filter_tipo")
    selected_states = st.multiselect("Estado CRM", CRM_STATES, placeholder="Seleccionar", key="crm_filter_estado")
    selected_resultados = st.multiselect("Resultado seguimiento", RESULTADO_SEGUIMIENTO_OPTIONS, placeholder="Seleccionar", key="crm_filter_resultado")
    phone_filter = st.selectbox("Tiene teléfono", ["Todos", "Sí", "No"], key="crm_filter_phone")
    instagram_filter = st.selectbox("Tiene Instagram", ["Todos", "Sí", "No"], key="crm_filter_instagram")
    selected_dates = st.multiselect("Fecha carga", fechas, placeholder="Seleccionar", key="crm_filter_fecha")

    out = df.copy()
    if selected_comunas:
        out = out[out[find_column(out, ["Comuna"])].isin(selected_comunas)]
    if selected_niveles:
        out = out[out[find_column(out, ["Nivel comercial"])].isin(selected_niveles)]
    if selected_tipos:
        out = out[out[find_column(out, ["Tipo negocio"])].isin(selected_tipos)]
    if selected_states:
        out = out[out["Estado CRM"].isin(selected_states)]
    if selected_dates:
        out = out[out["Fecha carga CRM"].isin(selected_dates)]
    if phone_filter != "Todos":
        has_phone = yes_no_has_value(get_series(out, ["Telefono", "Teléfono", "Tel?fono", "Tel?fono"]))
        out = out[has_phone if phone_filter == "Sí" else ~has_phone]
    if instagram_filter != "Todos":
        has_ig = yes_no_has_value(get_series(out, ["Instagram URL"]))
        out = out[has_ig if instagram_filter == "Sí" else ~has_ig]
    return out


def apply_crm_filters_compact(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="section-title">Filtros comerciales</div>', unsafe_allow_html=True)
    name_options = sorted(
        [clean_text(x) for x in get_series(df, ["Nombre restaurante"]).dropna().unique() if clean_text(x)],
        key=str.lower,
    )
    all_restaurants_label = "Todos los restaurantes"
    search_options = [all_restaurants_label] + name_options
    comunas = sorted([x for x in get_series(df, ["Comuna"]).dropna().unique() if clean_text(x)])
    niveles = sorted([x for x in get_series(df, ["Nivel comercial"]).dropna().unique() if clean_text(x)])
    restore_commercial_filters_from_query(search_options, comunas, niveles, CRM_STATES, RESULTADO_SEGUIMIENTO_OPTIONS)

    if st.session_state.get("buscador_restaurante_select") not in search_options:
        st.session_state["buscador_restaurante_select"] = all_restaurants_label
    st.session_state["crm_top_comuna"] = [value for value in st.session_state.get("crm_top_comuna", []) if value in comunas]
    st.session_state["crm_top_nivel"] = [value for value in st.session_state.get("crm_top_nivel", []) if value in niveles]
    st.session_state["crm_top_estado"] = [value for value in st.session_state.get("crm_top_estado", []) if value in CRM_STATES]
    st.session_state["crm_top_resultado"] = [value for value in st.session_state.get("crm_top_resultado", []) if value in RESULTADO_SEGUIMIENTO_OPTIONS]

    search_cols = st.columns([6, 1], gap="small", vertical_alignment="bottom")
    search = search_cols[0].selectbox(
        "Buscar restaurante",
        search_options,
        key="buscador_restaurante_select",
        placeholder="Escribe o selecciona restaurante...",
    )
    search_cols[1].button("Limpiar", type="secondary", use_container_width=True, on_click=clear_search_filter)
    search = "" if search == all_restaurants_label else search
    st.session_state["texto_temporal_buscador"] = search
    st.session_state["texto_aplicado_buscador"] = search
    cols = st.columns([1.05, 1.05, 0.95, 1.2, 0.75, 0.8], gap="small")

    selected_comunas = cols[0].multiselect("Comuna", comunas, placeholder="Todas", key="crm_top_comuna")
    selected_niveles = cols[1].multiselect("Nivel", niveles, placeholder="Todos", key="crm_top_nivel")
    selected_states = cols[2].multiselect("Estado", CRM_STATES, placeholder="Todos", key="crm_top_estado")
    selected_resultados = cols[3].multiselect("Resultado", RESULTADO_SEGUIMIENTO_OPTIONS, placeholder="Todos", key="crm_top_resultado")
    phone_filter = cols[4].selectbox("Telefono", ["Todos", "Si", "No"], key="crm_top_phone")
    whatsapp_filter = cols[5].selectbox("WhatsApp", ["Todos", "Si", "No"], key="crm_top_whatsapp")

    out = df.copy()
    comuna_col = find_column(out, ["Comuna"])
    nivel_col = find_column(out, ["Nivel comercial"])
    name_col = find_column(out, ["Nombre restaurante"])
    if selected_comunas and comuna_col:
        out = out[out[comuna_col].isin(selected_comunas)]
    if selected_niveles and nivel_col:
        out = out[out[nivel_col].isin(selected_niveles)]
    if selected_states:
        out = out[out["Estado CRM"].isin(selected_states)]
    if selected_resultados:
        selected_norm = {normalize_resultado_seguimiento(value, "") for value in selected_resultados}
        before_resultado = len(out)
        resultado_source = out["Resultado seguimiento"] if "Resultado seguimiento" in out.columns else pd.Series([""] * len(out), index=out.index)
        resultado_series = resultado_source.apply(lambda value: normalize_resultado_seguimiento(value, ""))
        unique_values = sorted([value for value in resultado_series.unique() if value])
        out = out[resultado_series.isin(selected_norm)]
        debug_msg = (
            f"Filtro Resultado seguimiento | antes={before_resultado} | despues={len(out)} | "
            f"seleccion={', '.join(sorted(selected_norm))} | valores={', '.join(unique_values) or 'sin valores'}"
        )
        print(debug_msg)
        with st.expander("Debug filtro Resultado", expanded=False):
            st.caption(f"Columna usada: Resultado seguimiento")
            st.caption(f"Total antes del filtro: {before_resultado}")
            st.caption(f"Total después del filtro: {len(out)}")
            st.caption(f"Valores únicos encontrados: {', '.join(unique_values) or 'sin valores'}")
    if phone_filter != "Todos":
        has_phone = yes_no_has_value(get_series(out, PHONE_COLUMNS))
        out = out[has_phone if phone_filter == "Si" else ~has_phone]
    if whatsapp_filter != "Todos":
        has_whatsapp = get_series(out, PHONE_COLUMNS).apply(is_valid_whatsapp_phone)
        out = out[has_whatsapp if whatsapp_filter == "Si" else ~has_whatsapp]
    if search and name_col:
        out = out[out[name_col].fillna("").astype(str).str.contains(search, case=False, na=False)]
    return out


def parse_existing_date(value: object) -> date | None:
    parsed = pd.to_datetime(clean_text(value), errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def row_link(row: pd.Series, names: list[str]) -> str:
    col = find_column(pd.DataFrame([row]), names)
    return clean_text(row.get(col, "")) if col else ""


def action_icon_svg(name: str) -> str:
    icons = {
        "phone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.7.6 2.5a2 2 0 0 1-.5 2.1L8 9.5a16 16 0 0 0 6.5 6.5l1.2-1.2a2 2 0 0 1 2.1-.5c.8.3 1.6.5 2.5.6A2 2 0 0 1 22 16.9z"/></svg>',
        "whatsapp": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3.5A11.8 11.8 0 0 0 2.4 18.4L1 23l4.7-1.3A11.8 11.8 0 0 0 23 11.8a11.7 11.7 0 0 0-2.5-8.3Zm-8.7 17.2c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-2.8.8.8-2.7-.2-.4A9.8 9.8 0 1 1 21 11.8a9.2 9.2 0 0 1-9.2 8.9Zm5.3-6.9c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2-.2.3-.8.9-.9 1.1-.2.2-.3.2-.6.1-.3-.2-1.2-.4-2.3-1.4-.8-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6l.5-.6c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.9-2c-.2-.5-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4s1 2.8 1.2 3c.2.3 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 1.9-1.4.2-.7.2-1.3.2-1.4-.1-.2-.3-.3-.5-.4Z"/></svg>',
        "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.1" fill="currentColor" stroke="none"/></svg>',
        "facebook": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 8.1V6.4c0-.8.5-1 1.1-1H17V2.2c-.9-.1-1.8-.2-2.7-.2-2.7 0-4.5 1.6-4.5 4.6v1.5H7v3.6h2.8V22H14V11.7h2.8l.5-3.6H14Z"/></svg>',
        "maps": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-5.4 7-12a7 7 0 1 0-14 0c0 6.6 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg>',
        "website": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1"/></svg>',
    }
    return icons[name]


def action_icon_link(icon: str, tooltip: str, url: str, css_class: str) -> str:
    if url:
        safe_url = html.escape(url, quote=True)
        safe_tip = html.escape(tooltip, quote=True)
        return f'<a class="lead-action-icon {css_class} active" href="{safe_url}" target="_blank" rel="noopener noreferrer" title="{safe_tip}">{action_icon_svg(icon)}</a>'
    safe_tip = html.escape(tooltip, quote=True)
    return f'<span class="lead-action-icon {css_class} disabled" title="{safe_tip}">{action_icon_svg(icon)}</span>'


def mark_whatsapp_contacted(crm_id: str, message: str, variant: str, restaurant_name: str) -> None:
    crm_current = load_crm_state()
    existing = crm_current[crm_current["CRM ID"] == crm_id].tail(1)
    current = {field: "" for field in CRM_FIELDS}
    current["CRM ID"] = crm_id
    if not existing.empty:
        current.update(existing.iloc[0].to_dict())
    previous_estado = normalize_crm_state(current.get("Estado CRM", "")) or "Nuevo"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current["Estado CRM"] = "Contactado"
    current["Estado WhatsApp"] = "Contactado manualmente"
    current["Resultado seguimiento"] = "Sin respuesta"
    current["Fecha ultimo contacto"] = now
    current["Canal ultimo contacto"] = "WhatsApp"
    current["Fecha ultimo WhatsApp"] = now
    current["Fecha envio WhatsApp"] = now
    current["Mensaje WhatsApp sugerido"] = message
    current["Mensaje enviado"] = message
    current["Variante mensaje"] = variant
    crm_current = crm_current[crm_current["CRM ID"] != crm_id]
    crm_current = pd.concat([crm_current, pd.DataFrame([current])], ignore_index=True)
    save_crm_state(crm_current)
    if get_data_mode() == "supabase":
        context = crm_event_context(crm_id, restaurant_name)
        ds_save_whatsapp_event(crm_id, context["Restaurante"], context["Comuna"], message, fecha_hora=now)
    else:
        append_contact_event(crm_id, "WhatsApp", "WhatsApp abierto", current, message, restaurant_name)
    if previous_estado != "Contactado":
        append_contact_event(
            crm_id,
            "WhatsApp",
            "Estado CRM cambiado",
            current,
            f"{previous_estado} → Contactado",
            restaurant_name,
            skip_if_same_event=True,
        )
    st.cache_data.clear()
    st.session_state["whatsapp_toast"] = {
        "restaurant": restaurant_name,
    }


def mark_call_contacted(crm_id: str, restaurant_name: str) -> None:
    crm_current = load_crm_state()
    existing = crm_current[crm_current["CRM ID"] == crm_id].tail(1)
    current = {field: "" for field in CRM_FIELDS}
    current["CRM ID"] = crm_id
    if not existing.empty:
        current.update(existing.iloc[0].to_dict())
    previous_estado = normalize_crm_state(current.get("Estado CRM", "")) or "Nuevo"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current["Estado CRM"] = "Contactado"
    current["Resultado seguimiento"] = "Sin respuesta"
    current["Fecha ultimo contacto"] = now
    current["Canal ultimo contacto"] = "Llamada"
    if not clean_text(current.get("Mensaje enviado", "")) and not clean_text(current.get("Mensaje WhatsApp sugerido", "")):
        current["Mensaje WhatsApp sugerido"] = "Llamada iniciada desde CRM"
    crm_current = crm_current[crm_current["CRM ID"] != crm_id]
    crm_current = pd.concat([crm_current, pd.DataFrame([current])], ignore_index=True)
    save_crm_state(crm_current)
    if get_data_mode() == "supabase":
        context = crm_event_context(crm_id, restaurant_name)
        ds_save_call_event(crm_id, context["Restaurante"], context["Comuna"], fecha_hora=now)
    else:
        append_contact_event(crm_id, "Llamada", "Llamada iniciada", current, "Llamada iniciada desde CRM", restaurant_name)
    if previous_estado != "Contactado":
        append_contact_event(
            crm_id,
            "Llamada",
            "Estado CRM cambiado",
            current,
            f"{previous_estado} → Contactado",
            restaurant_name,
            skip_if_same_event=True,
        )
    st.cache_data.clear()
    st.session_state["call_toast"] = {
        "restaurant": restaurant_name,
    }


def render_whatsapp_toast() -> None:
    toast = st.session_state.pop("whatsapp_toast", None)
    if toast:
        restaurant = clean_text(toast.get("restaurant", "Restaurante"))
        st.markdown(
            f"""
            <div class="floating-toast-success">
                <strong>WhatsApp abierto</strong>
                <span title="{html.escape(restaurant, quote=True)}">{html.escape(restaurant)}</span>
                <small>Marcado como Contactado.<br>Estado WhatsApp: Contactado manualmente</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
    call_toast = st.session_state.pop("call_toast", None)
    if call_toast:
        restaurant = clean_text(call_toast.get("restaurant", "Restaurante"))
        st.markdown(
            f"""
            <div class="floating-toast-success">
                <strong>Llamada iniciada</strong>
                <span title="{html.escape(restaurant, quote=True)}">{html.escape(restaurant)}</span>
                <small>Marcado como Contactado.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


def whatsapp_action_url(row: pd.Series, name_col: str, comuna_col: str, message: str | None = None) -> str:
    phone_col = find_column(pd.DataFrame([row]), PHONE_COLUMNS) or "Telefono"
    final_message = message or whatsapp_message(row.get(name_col, ""), row.get(comuna_col, ""))
    return whatsapp_url(row.get(phone_col, ""), final_message)


def render_lead_action_icons(row: pd.Series, name_col: str, comuna_col: str, message: str | None = None, variant: str = "A") -> None:
    phone_col = find_column(pd.DataFrame([row]), PHONE_COLUMNS) or "Telefono"
    call_phone = normalizar_telefono_llamada(row.get(phone_col, ""))
    wa_url = whatsapp_action_url(row, name_col, comuna_col, message)
    actions = [
        action_icon_link("phone", "Llamar", f"tel:{call_phone}" if call_phone else "", "phone"),
        action_icon_link("instagram", "Abrir Instagram", row_link(row, ["Instagram URL"]), "instagram"),
        action_icon_link("facebook", "Abrir Facebook", row_link(row, ["Facebook URL"]), "facebook"),
        action_icon_link("maps", "Abrir Google Maps", row_link(row, ["Google Maps URL"]), "maps"),
        action_icon_link("website", "Abrir sitio web", row_link(row, ["Sitio web"]), "website"),
    ]
    st.markdown(f'<div class="lead-actions">{"".join(actions)}</div>', unsafe_allow_html=True)
    st.link_button(
        "WhatsApp",
        wa_url or "https://example.com",
        type="primary",
        disabled=not bool(wa_url),
        use_container_width=True,
        help="Abre WhatsApp con el mensaje sugerido y registra el contacto en el CRM.",
        on_click=mark_whatsapp_contacted,
        args=(row["CRM ID"], message or "", variant, clean_text(row.get(name_col, ""))),
    )


def save_lead_updates(row: pd.Series, updates: dict[str, object]) -> None:
    crm_current = load_crm_state()
    existing = crm_current[crm_current["CRM ID"] == row["CRM ID"]].tail(1)
    current = {field: clean_text(row.get(field, "")) for field in CRM_FIELDS}
    current["CRM ID"] = row["CRM ID"]
    if not existing.empty:
        current.update(existing.iloc[0].to_dict())
    previous = current.copy()
    current.update(updates)
    crm_current = crm_current[crm_current["CRM ID"] != row["CRM ID"]]
    crm_current = pd.concat([crm_current, pd.DataFrame([current])], ignore_index=True)
    save_crm_state(crm_current)
    name_col = find_column(pd.DataFrame([row]), ["Nombre restaurante"]) or "Nombre restaurante"
    previous_estado = normalize_crm_state(previous.get("Estado CRM", ""))
    current_estado = normalize_crm_state(current.get("Estado CRM", ""))
    if current_estado and current_estado != previous_estado:
        append_contact_event(
            row["CRM ID"],
            "Manual",
            "Estado CRM cambiado",
            current,
            f"Anterior: {previous_estado or 'Sin estado'} | Nuevo: {current_estado}",
            clean_text(row.get(name_col, "")),
            skip_if_same_event=True,
        )
    previous_resultado = normalize_resultado_seguimiento(previous.get("Resultado seguimiento", ""), "")
    current_resultado = normalize_resultado_seguimiento(current.get("Resultado seguimiento", ""), "")
    if current_resultado and current_resultado != previous_resultado:
        append_contact_event(
            row["CRM ID"],
            "Manual",
            "Resultado cambiado",
            current,
            f"Anterior: {previous_resultado or 'Sin resultado'} | Nuevo: {current_resultado}",
            clean_text(row.get(name_col, "")),
        )
    previous_note = clean_text(previous.get("Observacion CRM", ""))
    current_note = clean_text(current.get("Observacion CRM", ""))
    if current_note and current_note != previous_note:
        append_contact_event(
            row["CRM ID"],
            "Manual",
            "Nota comercial agregada",
            current,
            current_note,
            clean_text(row.get(name_col, "")),
        )
    st.cache_data.clear()


def save_resultado_seguimiento(crm_id: str, key: str) -> None:
    value = normalize_resultado_seguimiento(st.session_state.get(key, ""), "")
    if value not in RESULTADO_SEGUIMIENTO_OPTIONS:
        return
    crm_current = load_crm_state()
    existing = crm_current[crm_current["CRM ID"] == crm_id].tail(1)
    current = {field: "" for field in CRM_FIELDS}
    current["CRM ID"] = crm_id
    if not existing.empty:
        current.update(existing.iloc[0].to_dict())
    previous_resultado = normalize_resultado_seguimiento(current.get("Resultado seguimiento", ""), "")
    current["Resultado seguimiento"] = value
    crm_current = crm_current[crm_current["CRM ID"] != crm_id]
    crm_current = pd.concat([crm_current, pd.DataFrame([current])], ignore_index=True)
    save_crm_state(crm_current)
    if value != previous_resultado:
        append_contact_event(
            crm_id,
            "Manual",
            "Resultado cambiado",
            current,
            f"Anterior: {previous_resultado or 'Sin resultado'} | Nuevo: {value}",
        )
    st.cache_data.clear()


def render_selected_lead_panel(df: pd.DataFrame, filtered: pd.DataFrame, selected_index: object | None) -> None:
    st.markdown('<div class="section-title">Lead seleccionado</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes para estos filtros.")
        return
    selected_index = selected_index_from_lead_id(filtered, clean_text(st.session_state.get("selected_lead_id", ""))) or selected_index
    if selected_index not in filtered.index:
        selected_index = resolve_visible_selected_index(filtered)
    if selected_index is None or selected_index not in df.index:
        st.info("No hay restaurantes para estos filtros.")
        return

    row = df.loc[selected_index]
    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(df, ["Comuna"]) or "Comuna"
    nivel_col = find_column(df, ["Nivel comercial"]) or "Nivel comercial"
    tipo_col = find_column(df, ["Tipo negocio"]) or "Tipo negocio"
    phone_col = find_column(df, PHONE_COLUMNS) or "Telefono"
    name = html.escape(clean_text(row.get(name_col, "")) or "Restaurante sin nombre")
    comuna = html.escape(clean_text(row.get(comuna_col, "")))
    nivel = html.escape(clean_text(row.get(nivel_col, "")))
    tipo = html.escape(clean_text(row.get(tipo_col, "")))
    telefono_original = clean_text(row.get(phone_col, ""))
    telefono_display = telefono_normalizado_display(telefono_original)
    estado_actual = clean_text(row.get("Estado CRM", "Nuevo")) or "Nuevo"
    badge_class = "positive" if estado_actual in CONTACTED_STATES else "accent" if nivel == "Alto potencial" else ""

    st.markdown(
        f"""
        <div class="lead-name">{name}</div>
        <div class="lead-meta">
            <span class="mini-badge">{comuna}</span>
            <span class="mini-badge accent">⭐ {nivel}</span>
            <span class="mini-badge">{tipo}</span>
            <span class="mini-badge {badge_class}">{html.escape(estado_actual)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if telefono_display:
        st.markdown(f"**Teléfono:** {html.escape(telefono_display)}")
        if not is_valid_whatsapp_phone(telefono_original):
            st.caption("Disponible para llamada. No disponible para WhatsApp.")
    else:
        st.caption("Sin teléfono registrado")

    st.markdown('<div class="section-title">Seguimiento WhatsApp</div>', unsafe_allow_html=True)
    current_variant = assigned_message_variant(row)
    message_variants = load_message_variants()
    if current_variant not in message_variants:
        current_variant = next(iter(message_variants), "1")
    variante_mensaje = st.selectbox("Variante mensaje", list(message_variants), index=list(message_variants).index(current_variant), disabled=True, key=f"lead_msg_variant_{row['CRM ID']}")
    default_variant_message = render_variant_message(variante_mensaje, row.get(name_col, ""), row.get(comuna_col, ""))
    mensaje_whatsapp = st.text_area("Mensaje enviado", value=clean_text(row.get("Mensaje enviado", "")) or clean_text(row.get("Mensaje WhatsApp sugerido", "")) or default_variant_message, height=200, key=f"lead_wa_msg_{row['CRM ID']}")
    st.caption(f"{len(mensaje_whatsapp)} caracteres")
    render_lead_action_icons(row, name_col, comuna_col, mensaje_whatsapp, variante_mensaje)

    current_state = estado_actual if estado_actual in CRM_STATES else "Nuevo"
    estado = st.selectbox("Estado CRM", CRM_STATES, index=CRM_STATES.index(current_state), key=f"lead_estado_{row['CRM ID']}")
    fecha_ultimo_whatsapp = st.date_input("Último WhatsApp", value=parse_existing_date(row.get("Fecha ultimo WhatsApp", "")), key=f"lead_wa_last_{row['CRM ID']}")
    observacion = st.text_area("Notas comerciales", value=clean_text(row.get("Observacion CRM", "")), height=90, key=f"lead_obs_{row['CRM ID']}")

    if st.button("Guardar cambios", type="primary", use_container_width=True, key=f"save_{row['CRM ID']}"):
        crm_current = load_crm_state()
        crm_current = crm_current[crm_current["CRM ID"] != row["CRM ID"]]
        new_row = {
            "CRM ID": row["CRM ID"],
            "Estado CRM": estado,
            "Fecha ultimo contacto": clean_text(row.get("Fecha ultimo contacto", "")),
            "Responsable": clean_text(row.get("Responsable", "")),
            "Observacion CRM": observacion,
            "Proxima accion": clean_text(row.get("Proxima accion", "")),
            "Fecha proxima accion": clean_text(row.get("Fecha proxima accion", "")),
            "Fecha ultimo WhatsApp": fecha_ultimo_whatsapp.isoformat() if isinstance(fecha_ultimo_whatsapp, date) else clean_text(row.get("Fecha ultimo WhatsApp", "")),
            "Mensaje WhatsApp sugerido": mensaje_whatsapp,
            "Estado WhatsApp": estado_whatsapp,
            "Variante mensaje": variante_mensaje,
            "Mensaje enviado": mensaje_whatsapp,
            "Fecha envio WhatsApp": clean_text(row.get("Fecha envio WhatsApp", "")),
            "Resultado seguimiento": normalize_resultado_seguimiento(row.get("Resultado seguimiento", ""), ""),
        }
        crm_current = pd.concat([crm_current, pd.DataFrame([new_row])], ignore_index=True)
        save_crm_state(crm_current)
        st.cache_data.clear()
        st.success("Cambios guardados.")
        st.rerun()

    st.markdown('<div class="crm-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Reiniciar lead</div>', unsafe_allow_html=True)
    confirm_reset = st.checkbox("¿Seguro que deseas reiniciar este lead?", key=f"confirm_reset_{row['CRM ID']}")
    if st.button("Reiniciar lead", type="secondary", use_container_width=True, disabled=not confirm_reset, key=f"reset_lead_{row['CRM ID']}"):
        affected = reset_single_lead(row["CRM ID"])
        cleaned = int(st.session_state.get("reset_cleaned_events", 0))
        st.session_state["reset_feedback_message"] = (
            "Se reiniciaron estados y se limpiaron eventos de contacto, manteniendo el evento inicial del lead. "
            f"Leads afectados: {affected}. Eventos eliminados: {cleaned}."
        )
        st.rerun()


def selected_lead_row(df: pd.DataFrame, filtered: pd.DataFrame, selected_index: object | None) -> pd.Series | None:
    if filtered.empty:
        return None
    selected_index = selected_index_from_lead_id(filtered, clean_text(st.session_state.get("selected_lead_id", ""))) or selected_index
    if selected_index not in filtered.index:
        selected_index = resolve_visible_selected_index(filtered)
    if selected_index is None or selected_index not in df.index:
        return None
    return df.loc[selected_index]


def render_lead_link_icons(row: pd.Series) -> None:
    actions = [
        action_icon_link("instagram", "Abrir Instagram", row_link(row, ["Instagram URL"]), "instagram"),
        action_icon_link("facebook", "Abrir Facebook", row_link(row, ["Facebook URL"]), "facebook"),
        action_icon_link("maps", "Abrir Google Maps", row_link(row, ["Google Maps URL"]), "maps"),
        action_icon_link("website", "Abrir sitio web", row_link(row, ["Sitio web"]), "website"),
    ]
    st.markdown(f'<div class="lead-actions">{"".join(actions)}</div>', unsafe_allow_html=True)


def render_selected_lead_panel(df: pd.DataFrame, filtered: pd.DataFrame, selected_index: object | None) -> None:
    st.markdown('<div class="section-title">Lead seleccionado</div>', unsafe_allow_html=True)
    row = selected_lead_row(df, filtered, selected_index)
    if row is None:
        st.info("No hay restaurantes para estos filtros.")
        return

    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(df, ["Comuna"]) or "Comuna"
    nivel_col = find_column(df, ["Nivel comercial"]) or "Nivel comercial"
    tipo_col = find_column(df, ["Tipo negocio"]) or "Tipo negocio"
    phone_col = find_column(df, PHONE_COLUMNS) or "Telefono"
    name = html.escape(clean_text(row.get(name_col, "")) or "Restaurante sin nombre")
    comuna = html.escape(clean_text(row.get(comuna_col, "")))
    nivel = html.escape(clean_text(row.get(nivel_col, "")))
    tipo = html.escape(clean_text(row.get(tipo_col, "")))
    telefono_original = clean_text(row.get(phone_col, ""))
    telefono_display = telefono_normalizado_display(telefono_original)
    estado_actual = normalize_crm_state(row.get("Estado CRM", "Nuevo"))
    resultado_seguimiento = clean_text(row.get("Resultado seguimiento", "")) or "Sin respuesta"
    badge_class = "positive" if estado_actual in CONTACTED_STATES else "accent" if nivel == "Alto potencial" else ""

    st.markdown(
        f"""
        <div class="lead-name">{name}</div>
        <div class="lead-meta">
            <span class="mini-badge">📍 {comuna}</span>
            <span class="mini-badge accent">⭐ {nivel}</span>
            <span class="mini-badge">🏷 {tipo}</span>
            <span class="mini-badge {badge_class}">{html.escape(estado_actual)}</span>
            <span class="mini-badge">{html.escape(resultado_seguimiento)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if telefono_display:
        st.markdown(f"**Teléfono:** {html.escape(telefono_display)}")
        if not is_valid_whatsapp_phone(telefono_original):
            st.caption("Disponible para llamada. No disponible para WhatsApp.")
    else:
        st.caption("Sin teléfono registrado")
    if should_show_no_response_alert(row):
        st.markdown(
            """
            <div class="lead-alert-badge">
                <strong>Sin respuesta hace 3 días</strong>
                <span>Este lead necesita seguimiento.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_lead_link_icons(row)

    current_state = estado_actual if estado_actual in CRM_STATES else "Nuevo"
    estado = st.selectbox("Estado CRM", CRM_STATES, index=CRM_STATES.index(current_state), key=f"lead_estado_{row['CRM ID']}")
    observacion = st.text_area("Notas comerciales", value=clean_text(row.get("Observacion CRM", "")), height=230, key=f"lead_obs_{row['CRM ID']}")

    if st.button("Guardar lead", type="primary", use_container_width=True, key=f"save_lead_main_{row['CRM ID']}"):
        save_lead_updates(
            row,
            {
                "Estado CRM": estado,
                "Observacion CRM": observacion,
            },
        )
        st.success("Lead guardado.")


def render_whatsapp_column_panel(df: pd.DataFrame, filtered: pd.DataFrame, selected_index: object | None) -> None:
    header_cols = st.columns([0.86, 0.14], vertical_alignment="center")
    header_cols[0].markdown('<div class="section-title">Contacto WhatsApp</div>', unsafe_allow_html=True)
    with header_cols[1]:
        render_whatsapp_messages_launcher(None, None, None)
    row = selected_lead_row(df, filtered, selected_index)
    if row is None:
        st.info("No hay restaurante seleccionado.")
        return
    render_whatsapp_toast()
    message_notice = st.session_state.pop("messages_saved_notice", "")
    if message_notice:
        st.success(message_notice)

    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(df, ["Comuna"]) or "Comuna"
    current_variant = assigned_message_variant(row)
    message_variants = load_message_variants()
    if current_variant not in message_variants:
        current_variant = next(iter(message_variants), "1")
    message_version = int(st.session_state.get("whatsapp_messages_version", 0))
    variante_mensaje = st.selectbox("Variante", list(message_variants), index=list(message_variants).index(current_variant), disabled=True, key=f"lead_msg_variant_{row['CRM ID']}_{message_version}")
    default_variant_message = render_variant_message(variante_mensaje, row.get(name_col, ""), row.get(comuna_col, ""))

    current_whatsapp_state = clean_text(row.get("Estado WhatsApp", "No contactado")) or "No contactado"
    last_contact = clean_text(row.get("Fecha ultimo WhatsApp", "")) or clean_text(row.get("Fecha envio WhatsApp", ""))
    last_contact_dt = pd.to_datetime(last_contact, errors="coerce")
    last_contact_text = last_contact_dt.strftime("%d/%m %H:%M") if not pd.isna(last_contact_dt) else "Sin registro"
    resultado_badge = normalize_resultado_seguimiento(row.get("Resultado seguimiento", ""), "")
    contacted = current_whatsapp_state != "No contactado" or bool(clean_text(row.get("Fecha envio WhatsApp", "")))
    badges = []
    if contacted:
        badges.append('<span class="mini-badge positive">🟢 Contactado</span>')
    if resultado_badge:
        badges.append(f'<span class="mini-badge accent">{html.escape(resultado_badge)}</span>')
    if not badges:
        badges.append('<span class="mini-badge">Sin contacto</span>')
    st.markdown(
        f"""
        <div class="lead-meta">{''.join(badges)}</div>
        <div class="contact-last-box">
            <span>Último contacto</span>
            <strong>{html.escape(last_contact_text)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    current_resultado = clean_text(row.get("Resultado seguimiento", "")) or "Sin respuesta"
    if current_resultado not in RESULTADO_SEGUIMIENTO_OPTIONS:
        current_resultado = "Sin respuesta"
    resultado_key = f"resultado_seguimiento_{row['CRM ID']}"
    st.selectbox(
        "Resultado seguimiento",
        RESULTADO_SEGUIMIENTO_OPTIONS,
        index=RESULTADO_SEGUIMIENTO_OPTIONS.index(current_resultado),
        key=resultado_key,
        on_change=save_resultado_seguimiento,
        args=(row["CRM ID"], resultado_key),
    )

    mensaje_whatsapp = st.text_area("Mensaje enviado", value=default_variant_message, height=200, key=f"lead_wa_msg_{row['CRM ID']}_{message_version}")
    st.caption(f"{len(mensaje_whatsapp)} caracteres")

    wa_url = whatsapp_action_url(row, name_col, comuna_col, mensaje_whatsapp)
    phone_col = find_column(pd.DataFrame([row]), PHONE_COLUMNS) or "Telefono"
    call_phone = normalizar_telefono_llamada(row.get(phone_col, ""))
    st.markdown(
        """
        <style>
        .contact-last-box {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin: 10px 0 14px;
            padding: 10px 12px;
            border: 1px solid var(--crm-line);
            border-radius: 10px;
            background: #fafbfc;
        }
        .contact-last-box span {
            color: var(--crm-muted);
            font-size: 12px;
        }
        .contact-last-box strong {
            color: var(--crm-ink);
            font-size: 13px;
            font-weight: 500;
        }
        div[data-testid="stLinkButton"] a {
            min-height: 40px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            border-radius: 10px !important;
            padding: 0 14px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            line-height: 1 !important;
            box-shadow: none !important;
            text-decoration: none !important;
        }
        div[data-testid="stLinkButton"] a[href*="wa.me"] {
            background: #25D366 !important;
            border-color: #25D366 !important;
            color: #ffffff !important;
        }
        div[data-testid="stLinkButton"] a[href*="wa.me"]:hover {
            background: #1fb457 !important;
            border-color: #1fb457 !important;
            color: #ffffff !important;
        }
        div[data-testid="stLinkButton"] a[href*="wa.me"]::before,
        div[data-testid="stButton"] button:disabled::before {
            content: "";
            width: 16px;
            height: 16px;
            display: inline-block;
            flex: 0 0 16px;
            background: currentColor;
            -webkit-mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M20.5 3.5A11.8 11.8 0 0 0 2.4 18.4L1 23l4.7-1.3A11.8 11.8 0 0 0 23 11.8a11.7 11.7 0 0 0-2.5-8.3Zm-8.7 17.2c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-2.8.8.8-2.7-.2-.4A9.8 9.8 0 1 1 21 11.8a9.2 9.2 0 0 1-9.2 8.9Zm5.3-6.9c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2-.2.3-.8.9-.9 1.1-.2.2-.3.2-.6.1-.3-.2-1.2-.4-2.3-1.4-.8-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6l.5-.6c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.9-2c-.2-.5-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4s1 2.8 1.2 3c.2.3 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 1.9-1.4.2-.7.2-1.3.2-1.4-.1-.2-.3-.3-.5-.4Z'/%3E%3C/svg%3E") center / contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M20.5 3.5A11.8 11.8 0 0 0 2.4 18.4L1 23l4.7-1.3A11.8 11.8 0 0 0 23 11.8a11.7 11.7 0 0 0-2.5-8.3Zm-8.7 17.2c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-2.8.8.8-2.7-.2-.4A9.8 9.8 0 1 1 21 11.8a9.2 9.2 0 0 1-9.2 8.9Zm5.3-6.9c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2-.2.3-.8.9-.9 1.1-.2.2-.3.2-.6.1-.3-.2-1.2-.4-2.3-1.4-.8-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6l.5-.6c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.9-2c-.2-.5-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4s1 2.8 1.2 3c.2.3 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 1.9-1.4.2-.7.2-1.3.2-1.4-.1-.2-.3-.3-.5-.4Z'/%3E%3C/svg%3E") center / contain no-repeat;
        }
        div[data-testid="stLinkButton"] a[href^="tel:"] {
            background: #eef8f2 !important;
            border-color: #cbeedd !important;
            color: #137d4b !important;
        }
        div[data-testid="stLinkButton"] a[href^="tel:"]:hover {
            background: #dff3e8 !important;
            border-color: #addfca !important;
            color: #10683f !important;
        }
        div[data-testid="stLinkButton"] a[href^="tel:"]::before {
            content: "";
            width: 16px;
            height: 16px;
            display: inline-block;
            flex: 0 0 16px;
            background: currentColor;
            -webkit-mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.7.6 2.5a2 2 0 0 1-.5 2.1L8 9.5a16 16 0 0 0 6.5 6.5l1.2-1.2a2 2 0 0 1 2.1-.5c.8.3 1.6.5 2.5.6A2 2 0 0 1 22 16.9z'/%3E%3C/svg%3E") center / contain no-repeat;
            mask: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.7.6 2.5a2 2 0 0 1-.5 2.1L8 9.5a16 16 0 0 0 6.5 6.5l1.2-1.2a2 2 0 0 1 2.1-.5c.8.3 1.6.5 2.5.6A2 2 0 0 1 22 16.9z'/%3E%3C/svg%3E") center / contain no-repeat;
        }
        div[data-testid="stButton"] button:disabled {
            min-height: 40px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            border-radius: 10px !important;
            padding: 0 14px !important;
            background: #f2f4f6 !important;
            border-color: #e2e6ea !important;
            color: #8b96a3 !important;
            opacity: 0.72 !important;
            cursor: not-allowed !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            line-height: 1 !important;
            box-shadow: none !important;
        }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] div[data-testid="stLinkButton"],
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] div[data-testid="stButton"] {
            height: 40px !important;
        }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] div[data-testid="stLinkButton"] a,
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] div[data-testid="stButton"] button {
            width: 100% !important;
            height: 40px !important;
            min-height: 40px !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            box-sizing: border-box !important;
            vertical-align: middle !important;
        }
        button[kind="secondary"][title="Editar mensajes WhatsApp"] {
            width: 34px !important;
            height: 34px !important;
            min-height: 34px !important;
            padding: 0 !important;
            border-radius: 10px !important;
            background: #ffffff !important;
            border-color: #e7eaef !important;
            color: #68727d !important;
            box-shadow: none !important;
        }
        button[kind="secondary"][title="Editar mensajes WhatsApp"]:hover {
            background: #fff4f1 !important;
            border-color: #ffd0c5 !important;
            color: #ff441f !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    action_cols = st.columns(2, gap="small")
    if wa_url:
        action_cols[0].link_button(
            "WhatsApp",
            wa_url,
            disabled=False,
            use_container_width=True,
            help="Abre WhatsApp con el mensaje sugerido y registra el contacto en el CRM.",
            on_click=mark_whatsapp_contacted,
            args=(row["CRM ID"], mensaje_whatsapp or "", variante_mensaje, clean_text(row.get(name_col, ""))),
        )
    else:
        action_cols[0].button(
            "WhatsApp no disponible",
            disabled=True,
            use_container_width=True,
            help="Este restaurante no tiene WhatsApp válido",
            key=f"wa_unavailable_{row['CRM ID']}",
        )
    action_cols[1].link_button(
        "Llamar",
        f"tel:+{call_phone}" if call_phone else "https://example.com",
        disabled=not bool(call_phone),
        use_container_width=True,
        help="Llamar al teléfono registrado." if call_phone else "No hay teléfono válido para llamada.",
        on_click=mark_call_contacted if call_phone else "ignore",
        args=(row["CRM ID"], clean_text(row.get(name_col, ""))) if call_phone else None,
    )

    if st.session_state.get("show_message_editor"):
        render_whatsapp_messages_dialog(row, name_col, comuna_col)


def compact_level(value: object) -> str:
    text = clean_text(value)
    mapping = {
        "Alto potencial": "Alto",
        "Medio potencial": "Medio",
        "Bajo potencial": "Bajo",
    }
    return mapping.get(text, text)


def compact_status(value: object) -> str:
    text = normalize_crm_state(value)
    mapping = {
        "Nuevo": "Nuevo",
        "Pendiente contacto": "Pend.",
        "Contactado": "Contact.",
        "Respondio": "Resp.",
        "Interesado": "Interes.",
        "No interesado": "No int.",
        "Cliente potencial": "Cliente",
    }
    return mapping.get(text, text)


def compact_whatsapp(value: object) -> str:
    return "🟢" if clean_text(value).lower() in {"si", "sí"} else "⚪"


def render_restaurant_table_modern_legacy(filtered: pd.DataFrame, total: int) -> object | None:
    st.markdown('<div class="section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="table-count-text">Mostrando {len(filtered)} de {total} restaurantes</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes para estos filtros.")
        st.session_state.pop("selected_lead_id", None)
        return None

    current_index = resolve_visible_selected_index(filtered)
    table = make_table_view(filtered)
    table["Numero"] = range(1, len(table) + 1)
    display_table = table.copy()
    if "Nivel comercial" in display_table.columns:
        display_table["Nivel comercial"] = display_table["Nivel comercial"].apply(compact_level)
    if "Estado CRM" in display_table.columns:
        display_table["Estado CRM"] = display_table["Estado CRM"].apply(compact_status)
    if "WhatsApp disponible" in display_table.columns:
        display_table["WhatsApp disponible"] = display_table["WhatsApp disponible"].apply(compact_whatsapp)
    visible = ["Numero", "Nombre", "Comuna", "Tipo negocio", "Nivel comercial", "Estado CRM", "Telefono", "WhatsApp disponible"]
    visible = [col for col in visible if col in display_table.columns]
    event = st.dataframe(
        display_table[visible],
        use_container_width=True,
        hide_index=True,
        height=520,
        row_height=30,
        on_select="rerun",
        selection_mode="single-row",
        key="crm_table_modern",
        column_config={
            "Numero": st.column_config.NumberColumn("N" + "\N{DEGREE SIGN}", width=60, format="%d"),
            "Nombre": st.column_config.TextColumn("Nombre", width=240, max_chars=28, help="Nombre completo del restaurante"),
            "Comuna": st.column_config.TextColumn("Comuna", width=120, max_chars=16),
            "Tipo negocio": st.column_config.TextColumn("Tipo", width=120, max_chars=16),
            "Nivel comercial": st.column_config.TextColumn("Nivel", width=140),
            "Estado CRM": st.column_config.TextColumn("Estado", width=120),
            "Telefono": st.column_config.TextColumn("Teléfono", width=120, max_chars=14),
            "WhatsApp disponible": st.column_config.TextColumn("WA", width=90, help="WhatsApp disponible"),
        },
    )
    selected_rows = []
    if hasattr(event, "selection"):
        selected_rows = event.selection.rows
    elif isinstance(event, dict):
        selected_rows = event.get("selection", {}).get("rows", [])
    if selected_rows:
        selected_index = table.index[selected_rows[0]]
        st.session_state["selected_lead_id"] = lead_identifier(filtered.loc[selected_index], selected_index)
        return selected_index
    return current_index


def render_restaurant_table(filtered: pd.DataFrame, total: int) -> None:
    st.markdown('<div class="section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="table-count-text">Mostrando {len(filtered)} de {total} restaurantes</div>', unsafe_allow_html=True)
    table = make_table_view(filtered)
    if "Nivel comercial" in table.columns:
        table["Nivel comercial"] = table["Nivel comercial"].apply(compact_level)
    if "Estado CRM" in table.columns:
        table["Estado CRM"] = table["Estado CRM"].apply(compact_status)
    if "WhatsApp disponible" in table.columns:
        table["WhatsApp disponible"] = table["WhatsApp disponible"].apply(compact_whatsapp)
    visible = [col for col in COMMERCIAL_TABLE_COLUMNS if col in table.columns]
    st.dataframe(
        table[visible],
        use_container_width=True,
        hide_index=True,
        height=430,
        row_height=30,
        column_config={
            "Numero": st.column_config.NumberColumn("N" + "\N{DEGREE SIGN}", width=60, format="%d"),
            "Nombre": st.column_config.TextColumn("Nombre", width=240, max_chars=28),
            "Comuna": st.column_config.TextColumn("Comuna", width=120, max_chars=16),
            "Tipo negocio": st.column_config.TextColumn("Tipo negocio", width=120, max_chars=16),
            "Nivel comercial": st.column_config.TextColumn("Nivel comercial", width=140),
            "Score comercial": st.column_config.NumberColumn("Score", width=80, format="%.0f"),
            "Telefono": st.column_config.TextColumn("Teléfono", width=120, max_chars=14),
            "WhatsApp disponible": st.column_config.TextColumn("WA", width=90),
            "Instagram": st.column_config.LinkColumn("Instagram", width=90, display_text="Abrir"),
            "Estado CRM": st.column_config.TextColumn("Estado CRM", width=120),
            "Proxima accion": st.column_config.TextColumn("Próxima acción", width="large"),
        },
    )


def render_restaurant_table_modern_legacy_click_table(filtered: pd.DataFrame, total: int) -> object | None:
    st.markdown('<div class="section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="table-count-text">Mostrando {len(filtered)} de {total} restaurantes</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes para estos filtros.")
        st.session_state.pop("selected_lead_id", None)
        return None

    sync_selected_lead_from_query(filtered)
    current_index = resolve_visible_selected_index(filtered)
    table = make_table_view(filtered)
    table["Numero"] = range(1, len(table) + 1)
    display_table = table.copy()
    if "Nivel comercial" in display_table.columns:
        display_table["Nivel comercial"] = display_table["Nivel comercial"].apply(compact_level)
    if "Estado CRM" in display_table.columns:
        display_table["Estado CRM"] = display_table["Estado CRM"].apply(compact_status)
    if "WhatsApp disponible" in display_table.columns:
        display_table["WhatsApp disponible"] = display_table["WhatsApp disponible"].apply(compact_whatsapp)

    visible = ["Numero", "Nombre", "Comuna", "Tipo negocio", "Nivel comercial", "Estado CRM", "Telefono", "WhatsApp disponible"]
    visible = [col for col in visible if col in display_table.columns]
    headers = {
        "Numero": "N" + "\N{DEGREE SIGN}",
        "Nombre": "Nombre",
        "Comuna": "Comuna",
        "Tipo negocio": "Tipo",
        "Nivel comercial": "Nivel",
        "Estado CRM": "Estado",
        "Telefono": "Teléfono",
        "WhatsApp disponible": "WA",
    }
    widths = {
        "Numero": "54px",
        "Nombre": "minmax(210px, 1.9fr)",
        "Comuna": "112px",
        "Tipo negocio": "112px",
        "Nivel comercial": "128px",
        "Estado CRM": "112px",
        "Telefono": "118px",
        "WhatsApp disponible": "72px",
    }
    grid_template = " ".join(widths[col] for col in visible)
    header_html = "".join(f'<div class="crm-click-table-th">{html.escape(headers.get(col, col))}</div>' for col in visible)
    rows_html = []
    for index, row in display_table[visible].iterrows():
        selected_class = " selected" if index == current_index else ""
        selection_key = lead_selection_key(filtered.loc[index], index)
        params = [("selected_lead_key", selection_key)] + current_commercial_filter_params()
        href = "?" + urlencode(params)
        cells = []
        for col in visible:
            value = clean_text(row.get(col, ""))
            cells.append(
                '<a class="crm-click-table-td" href="{href}" target="_self" title="{title}">{text}</a>'.format(
                    href=href,
                    title=html.escape(value, quote=True),
                    text=html.escape(value),
                )
            )
        rows_html.append(f'<div class="crm-click-table-row{selected_class}" style="grid-template-columns:{grid_template};">{"".join(cells)}</div>')

    st.markdown(
        f"""
        <style>
        .crm-click-table {{
            border: 1px solid var(--crm-line);
            border-radius: 12px;
            overflow: hidden;
            background: #ffffff;
        }}
        .crm-click-table-head,
        .crm-click-table-row {{
            display: grid;
            min-width: 900px;
        }}
        .crm-click-table-head {{
            position: sticky;
            top: 0;
            z-index: 2;
            background: #fafbfc;
            border-bottom: 1px solid var(--crm-line);
        }}
        .crm-click-table-th {{
            color: var(--crm-muted);
            font-size: 12px;
            font-weight: 500;
            padding: 9px 10px;
            white-space: nowrap;
        }}
        .crm-click-table-body {{
            max-height: 520px;
            overflow: auto;
        }}
        .crm-click-table-row {{
            border-bottom: 1px solid #eef1f4;
            transition: background 0.12s ease, box-shadow 0.12s ease;
        }}
        .crm-click-table-row:hover {{
            background: #fff6f3;
        }}
        .crm-click-table-row.selected {{
            background: #fff1ee;
            box-shadow: inset 3px 0 0 var(--crm-rappi);
        }}
        .crm-click-table-td {{
            display: block;
            min-width: 0;
            color: var(--crm-ink);
            font-size: 12.5px;
            line-height: 1.3;
            padding: 8px 10px;
            text-decoration: none;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            cursor: pointer;
        }}
        .crm-click-table-td:hover {{
            color: var(--crm-ink);
            text-decoration: none;
        }}
        </style>
        <div class="crm-click-table">
            <div class="crm-click-table-head" style="grid-template-columns:{grid_template};">{header_html}</div>
            <div class="crm-click-table-body">
                {''.join(rows_html)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return current_index


def render_restaurant_table_modern_legacy_buttons(filtered: pd.DataFrame, total: int) -> object | None:
    st.markdown('<div class="section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="table-count-text">Mostrando {len(filtered)} de {total} restaurantes</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes para estos filtros.")
        st.session_state.pop("selected_lead_id", None)
        return None

    current_index = resolve_visible_selected_index(filtered)
    table = make_table_view(filtered)
    table["Numero"] = range(1, len(table) + 1)
    display_table = table.copy()

    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="secondary"] {
            justify-content: flex-start;
            min-height: 36px;
            padding: 7px 10px;
            border-color: #e6e9ed;
            background: #ffffff;
            color: var(--crm-ink);
            font-weight: 400;
            box-shadow: none;
            text-align: left;
            font-family: "Inter", "Segoe UI", sans-serif;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="secondary"]:hover {
            border-color: #ffd0c7;
            background: #fff8f6;
            color: var(--crm-ink);
        }
        .crm-row-help {
            color: var(--crm-muted);
            font-size: 12px;
            margin: -2px 0 8px;
        }
        .lead-row-number {
            display: inline-block;
            width: 34px;
            color: var(--crm-muted);
            font-variant-numeric: tabular-nums;
        }
        </style>
        <div class="crm-row-help">Haz clic en cualquier fila para ver el lead a la derecha.</div>
        """,
        unsafe_allow_html=True,
    )

    for index, row in display_table.iterrows():
        lead_id = lead_identifier(filtered.loc[index], index)
        lead_key = lead_selection_key(filtered.loc[index], index)
        is_selected = index == current_index
        number = f"{int(row.get('Numero', 0)):02d}"
        name = clean_text(row.get("Nombre", "")) or "Restaurante sin nombre"
        prefix = "" if is_selected else "  "
        label = f"{prefix}{number}   {name[:58]}"
        st.button(
            label,
            key=f"select_lead_row_{lead_key}",
            type="secondary",
            use_container_width=True,
            on_click=select_lead,
            args=(lead_id, lead_key, index),
        )
    return resolve_visible_selected_index(filtered)


def render_restaurant_table_modern(filtered: pd.DataFrame, total: int) -> object | None:
    st.markdown('<div class="section-title">Restaurantes</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="table-count-text">Mostrando {len(filtered)} de {total} restaurantes</div>', unsafe_allow_html=True)
    if filtered.empty:
        st.info("No hay restaurantes para estos filtros.")
        st.session_state.pop("selected_lead_id", None)
        return None

    current_index = resolve_visible_selected_index(filtered)
    table = make_table_view(filtered)
    table["Numero"] = range(1, len(table) + 1)

    option_keys: list[str] = []
    option_labels: dict[str, str] = {}
    option_meta: dict[str, tuple[str, object]] = {}
    for index, row in table.iterrows():
        lead_id = lead_identifier(filtered.loc[index], index)
        lead_key = lead_selection_key(filtered.loc[index], index)
        number = f"{int(row.get('Numero', 0)):02d}"
        name = clean_text(row.get("Nombre", "")) or "Restaurante sin nombre"
        option_keys.append(lead_key)
        option_labels[lead_key] = f"{number}  {name}"
        option_meta[lead_key] = (lead_id, index)

    current_key = lead_selection_key(filtered.loc[current_index], current_index) if current_index in filtered.index else option_keys[0]
    if st.session_state.get("lead_list_radio") not in option_keys:
        st.session_state["lead_list_radio"] = current_key

    st.markdown(
        """
        <style>
        .crm-row-help {
            color: var(--crm-muted);
            font-size: 11.5px;
            margin: -4px 0 8px;
        }
        div[role="radiogroup"] {
            gap: 3px;
            width: 100%;
        }
        div[role="radiogroup"] label {
            width: 100%;
            max-width: 100%;
            min-height: 28px;
            padding: 4px 8px 4px 10px;
            border: 1px solid transparent;
            border-bottom-color: #eef1f4;
            border-radius: 7px;
            background: #ffffff;
            color: var(--crm-ink);
            font-size: 12.5px;
            font-weight: 400;
            line-height: 1.25;
            transition: background 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
            justify-content: flex-start;
            text-align: left;
            box-sizing: border-box;
        }
        div[role="radiogroup"] label:hover {
            background: #fafbfc;
            border-color: #edf0f3;
        }
        div[role="radiogroup"] label:has(input:checked) {
            background: #fff7f4;
            border-color: #ffe0d8;
            box-shadow: inset 2px 0 0 var(--crm-rappi);
        }
        div[role="radiogroup"] label > div:first-child {
            display: none;
        }
        div[role="radiogroup"] label p {
            display: block;
            width: 100%;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: left;
            margin: 0;
            font-size: 12.5px;
            line-height: 1.2;
            font-variant-numeric: tabular-nums;
        }
        div[role="radiogroup"] label span {
            width: 100%;
            max-width: 100%;
            min-width: 0;
        }
        </style>
        <div class="crm-row-help">Haz clic en cualquier fila para ver el lead a la derecha.</div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(height=500, border=False):
        selected_key = st.radio(
            "Restaurantes",
            option_keys,
            key="lead_list_radio",
            format_func=lambda key: option_labels.get(key, key),
            label_visibility="collapsed",
        )
    lead_id, selected_index = option_meta[selected_key]
    select_lead(lead_id, selected_key, selected_index)
    return resolve_visible_selected_index(filtered)


@fragment
def render_lead_workspace_fragment(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    table_col, detail_col, whatsapp_col = st.columns([0.38, 0.30, 0.32], gap="large")
    panel_height = 650
    with table_col:
        with st.container(border=True, height=panel_height):
            selected_index = render_restaurant_table_modern(filtered, len(df))
    with detail_col:
        with st.container(border=True, height=panel_height):
            render_selected_lead_panel(df, filtered, selected_index)
    with whatsapp_col:
        with st.container(border=True, height=panel_height):
            render_whatsapp_column_panel(df, filtered, selected_index)

    render_lead_timeline(df, filtered)

    render_panel_grid_spacer()
    with st.container(border=True):
        render_message_results(filtered)

def render_lead_timeline(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    row = selected_lead_row(df, filtered, resolve_visible_selected_index(filtered) if not filtered.empty else None)
    if row is None:
        return
    crm_id = clean_text(row.get("CRM ID", ""))
    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    lead_name = clean_text(row.get(name_col, "")) or "Restaurante seleccionado"
    history = contact_history_for_crm_id(crm_id)
    if history.empty:
        components.html(
            f"""
            <div class="timeline-shell">
                <style>
                    .timeline-shell {{
                        font-family: "Inter", "Segoe UI", Arial, sans-serif;
                        box-sizing: border-box;
                        border: 1px solid #e8ebef;
                        border-radius: 12px;
                        background: #ffffff;
                        padding: 14px;
                        color: #1f2933;
                    }}
                    .timeline-title {{
                        font-size: 18px;
                        font-weight: 600;
                        margin: 0 0 2px;
                    }}
                    .timeline-subtitle {{
                        color: #68727d;
                        font-size: 13px;
                        margin-bottom: 12px;
                    }}
                    .timeline-empty {{
                        border: 1px solid #edf0f3;
                        border-radius: 10px;
                        background: #fafbfc;
                        color: #68727d;
                        font-size: 13px;
                        padding: 12px;
                    }}
                </style>
                <div class="timeline-title">Línea de tiempo del lead</div>
                <div class="timeline-subtitle">{html.escape(lead_name)}</div>
                <div class="timeline-empty">Este lead aún no tiene historial.</div>
            </div>
            """,
            height=150,
        )
        return

    history = history.copy()
    history["_fecha_sort"] = pd.to_datetime(history["Fecha/hora"], errors="coerce")
    history = history.sort_values("_fecha_sort", ascending=True, na_position="last").tail(20)

    channel_colors = {
        "WhatsApp": "#25D366",
        "Llamada": "#2563eb",
        "Manual": "#f97316",
        "Sistema": "#6b7280",
    }
    items = []
    for index, (_, event) in enumerate(history.iterrows()):
        fecha = format_mtime_like_text(event.get("Fecha/hora", ""))
        canal = clean_text(event.get("Canal", "Manual")) or "Manual"
        accion = clean_text(event.get("Acción", "")) or "Evento"
        resultado = clean_text(event.get("Resultado seguimiento actual", ""))
        detalle = clean_text(event.get("Mensaje enviado", ""))
        brief = resultado or detalle
        if len(brief) > 78:
            brief = brief[:75].rstrip() + "..."
        if accion == "Restaurante agregado":
            color = "#3b82f6"
        elif "Alerta" in accion:
            color = "#f59e0b"
        else:
            color = channel_colors.get(canal, "#6b7280")
        placement = "top" if index % 2 == 0 else "bottom"
        items.append(
            f"""
            <div class="timeline-event {placement}" style="--event-color:{color};">
                <div class="event-card">
                    <div class="event-date">{html.escape(fecha)}</div>
                    <div class="event-action">{html.escape(accion)}</div>
                    <div class="event-detail">{html.escape(brief or canal)}</div>
                </div>
                <div class="event-dot" title="{html.escape(canal, quote=True)}"></div>
                <div class="event-channel">{html.escape(canal)}</div>
            </div>
            """
        )

    timeline_html = f"""
    <div class="timeline-shell">
        <style>
            .timeline-shell {{
                font-family: "Inter", "Segoe UI", Arial, sans-serif;
                box-sizing: border-box;
                border: 1px solid #e8ebef;
                border-radius: 12px;
                background: #ffffff;
                min-height: 350px;
                padding: 14px 14px 80px;
                color: #1f2933;
                overflow: visible;
            }}
            .timeline-title {{
                font-size: 18px;
                font-weight: 600;
                margin: 0 0 2px;
            }}
            .timeline-subtitle {{
                color: #68727d;
                font-size: 13px;
                margin-bottom: 12px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .timeline-scroll {{
                overflow-x: auto;
                overflow-y: visible;
                padding: 8px 2px 78px;
            }}
            .timeline-track {{
                position: relative;
                display: flex;
                align-items: center;
                gap: 34px;
                min-width: max-content;
                min-height: 300px;
                padding: 0 14px;
            }}
            .timeline-track::before {{
                content: "";
                position: absolute;
                left: 14px;
                right: 14px;
                top: 132px;
                height: 2px;
                background: #e6e9ed;
            }}
            .timeline-event {{
                position: relative;
                width: 170px;
                min-width: 170px;
                min-height: 300px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }}
            .event-dot {{
                position: absolute;
                top: 123px;
                width: 18px;
                height: 18px;
                border-radius: 999px;
                background: var(--event-color);
                border: 4px solid #ffffff;
                box-shadow: 0 0 0 2px color-mix(in srgb, var(--event-color) 28%, transparent);
                z-index: 2;
            }}
            .event-card {{
                position: absolute;
                width: 158px;
                min-height: 78px;
                border: 1px solid #edf0f3;
                border-radius: 11px;
                background: #fafbfc;
                padding: 9px 10px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                box-sizing: border-box;
            }}
            .timeline-event.top .event-card {{
                bottom: 172px;
            }}
            .timeline-event.bottom .event-card {{
                top: 172px;
            }}
            .event-card::after {{
                content: "";
                position: absolute;
                left: 50%;
                width: 1px;
                height: 18px;
                background: #dfe4ea;
            }}
            .timeline-event.top .event-card::after {{
                bottom: -19px;
            }}
            .timeline-event.bottom .event-card::after {{
                top: -19px;
            }}
            .event-date {{
                color: #68727d;
                font-size: 11px;
                line-height: 1.2;
                margin-bottom: 4px;
            }}
            .event-action {{
                color: #20242a;
                font-size: 12.5px;
                font-weight: 600;
                line-height: 1.25;
                margin-bottom: 4px;
            }}
            .event-detail {{
                color: #59636f;
                font-size: 11.5px;
                line-height: 1.25;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
            .event-channel {{
                position: absolute;
                top: 146px;
                color: var(--event-color);
                font-size: 11.5px;
                font-weight: 600;
            }}
        </style>
        <div class="timeline-title">Línea de tiempo del lead</div>
        <div class="timeline-subtitle">{html.escape(lead_name)}</div>
        <div class="timeline-scroll">
            <div class="timeline-track">
                {''.join(items)}
            </div>
        </div>
    </div>
    """
    components.html(timeline_html, height=390, scrolling=False)


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Historial contactos") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def build_contact_history_table(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "CRM ID",
        "Restaurante",
        "Comuna",
        "Canal",
        "Acción",
        "Estado CRM",
        "Resultado seguimiento",
        "Fecha contacto",
        "Mensaje / detalle",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    history = load_contact_history()
    if history.empty:
        return pd.DataFrame(columns=columns)
    visible_ids = set(df["CRM ID"].fillna("").astype(str)) if "CRM ID" in df.columns else set()
    if visible_ids:
        history = history[history["CRM ID"].fillna("").astype(str).isin(visible_ids)].copy()
    if history.empty:
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame(
        {
            "CRM ID": history["CRM ID"],
            "Restaurante": history["Restaurante"],
            "Comuna": history["Comuna"],
            "Canal": history["Canal"],
            "Acción": history["Acción"],
            "Estado CRM": history["Estado CRM actual"].apply(normalize_crm_state),
            "Resultado seguimiento": history["Resultado seguimiento actual"].apply(lambda value: normalize_resultado_seguimiento(value, "")),
            "Fecha contacto": history["Fecha/hora"],
            "Mensaje / detalle": history["Mensaje enviado"],
        }
    )
    parsed = pd.to_datetime(out["Fecha contacto"], errors="coerce")
    out = out.assign(_fecha_sort=parsed).sort_values("_fecha_sort", ascending=False, na_position="last").drop(columns=["_fecha_sort"])
    out["Fecha contacto"] = out["Fecha contacto"].apply(format_mtime_like_text)
    for col in columns:
        out[col] = out[col].fillna("").astype(str).replace({"nan": "", "None": ""})
    return out[columns]


def build_legacy_contact_history_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Restaurante",
                "Comuna",
                "Canal",
                "Estado CRM",
                "Resultado seguimiento",
                "Fecha contacto",
                "Mensaje / detalle",
            ]
        )
    name_col = find_column(df, ["Nombre restaurante"]) or "Nombre restaurante"
    comuna_col = find_column(df, ["Comuna"]) or "Comuna"
    canal_source = get_series(df, ["Canal ultimo contacto"]).apply(clean_text)
    estado_whatsapp = get_series(df, ["Estado WhatsApp"]).fillna("").astype(str).str.strip()
    message_enviado = get_series(df, ["Mensaje enviado"])
    message_sugerido = get_series(df, ["Mensaje WhatsApp sugerido"])
    message_series = message_enviado.where(yes_no_has_value(message_enviado), message_sugerido)
    last_whatsapp = get_series(df, ["Fecha ultimo WhatsApp"]).where(
        yes_no_has_value(get_series(df, ["Fecha ultimo WhatsApp"])),
        get_series(df, ["Fecha envio WhatsApp"]),
    )
    fecha_contacto = get_series(df, ["Fecha ultimo contacto"]).where(
        yes_no_has_value(get_series(df, ["Fecha ultimo contacto"])),
        last_whatsapp,
    )
    canal = canal_source.copy()
    canal = canal.mask(canal.eq("") & yes_no_has_value(last_whatsapp), "WhatsApp")
    canal = canal.mask(canal.eq("") & yes_no_has_value(fecha_contacto), "Llamada")
    detalle = message_series.where(canal.ne("Llamada"), "Llamada iniciada desde CRM")
    registered_mask = (
        yes_no_has_value(fecha_contacto)
        | yes_no_has_value(last_whatsapp)
        | canal.ne("")
        | yes_no_has_value(message_series)
        | (get_series(df, ["Estado WhatsApp"]).fillna("").astype(str).str.strip() != "No contactado")
    )
    out = pd.DataFrame(
        {
            "Restaurante": get_series(df, [name_col, "Nombre restaurante"]),
            "Comuna": get_series(df, [comuna_col, "Comuna"]),
            "Canal": canal,
            "Estado CRM": get_series(df, ["Estado CRM"]),
            "Resultado seguimiento": get_series(df, ["Resultado seguimiento"]).apply(lambda value: normalize_resultado_seguimiento(value, "")),
            "Fecha contacto": fecha_contacto.apply(format_mtime_like_text),
            "Mensaje / detalle": detalle,
        },
        index=df.index,
    )
    out = out[registered_mask].copy()
    out["Canal"] = out["Canal"].replace("", "WhatsApp")
    for col in out.columns:
        out[col] = out[col].fillna("").astype(str).replace({"nan": "", "None": ""})
    return out


def build_message_results_table(df: pd.DataFrame) -> pd.DataFrame:
    return build_contact_history_table(df)


def format_mtime_like_text(value: object) -> str:
    text = clean_text(value)
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%d/%m/%Y %H:%M")


def render_message_results(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Historial de contactos</div>', unsafe_allow_html=True)
    table = build_contact_history_table(df)
    if table.empty:
        st.info("No hay contactos registrados para los filtros actuales.")
        return
    filter_cols = st.columns([0.34, 0.18, 0.22, 0.26])
    restaurant_options = ["Todos"] + sorted([value for value in table["Restaurante"].dropna().astype(str).unique() if value])
    restaurant_filter = filter_cols[0].selectbox("Restaurante", restaurant_options, key="history_restaurante")
    canal_options = ["Todos"] + sorted([value for value in table["Canal"].dropna().astype(str).unique() if value])
    canal_filter = filter_cols[1].selectbox("Canal", canal_options, key="history_canal")
    resultado_options = ["Todos"] + RESULTADO_SEGUIMIENTO_OPTIONS
    resultado_filter = filter_cols[2].selectbox("Resultado", resultado_options, key="history_resultado")
    parsed_dates = pd.to_datetime(table["Fecha contacto"], dayfirst=True, errors="coerce")
    valid_dates = parsed_dates.dropna()
    default_range = (valid_dates.min().date(), valid_dates.max().date()) if not valid_dates.empty else (date.today(), date.today())
    fecha_filter = filter_cols[3].date_input("Fecha", value=default_range, key="history_fecha")

    filtered_table = table.copy()
    if restaurant_filter != "Todos":
        filtered_table = filtered_table[filtered_table["Restaurante"] == restaurant_filter]
    if canal_filter != "Todos":
        filtered_table = filtered_table[filtered_table["Canal"] == canal_filter]
    if resultado_filter != "Todos":
        normalized_result = normalize_resultado_seguimiento(resultado_filter, "")
        filtered_table = filtered_table[
            filtered_table["Resultado seguimiento"].apply(lambda value: normalize_resultado_seguimiento(value, "")) == normalized_result
        ]
    if isinstance(fecha_filter, tuple) and len(fecha_filter) == 2:
        start_date, end_date = fecha_filter
        table_dates = pd.to_datetime(filtered_table["Fecha contacto"], dayfirst=True, errors="coerce").dt.date
        filtered_table = filtered_table[(table_dates >= start_date) & (table_dates <= end_date)]
    elif isinstance(fecha_filter, date):
        table_dates = pd.to_datetime(filtered_table["Fecha contacto"], dayfirst=True, errors="coerce").dt.date
        filtered_table = filtered_table[table_dates == fecha_filter]

    if filtered_table.empty:
        st.info("No hay contactos registrados para estos filtros.")
        return

    export_table = filtered_table.drop(columns=["CRM ID"], errors="ignore")
    st.download_button(
        "Descargar historial de contactos",
        data=dataframe_to_excel_bytes(export_table),
        file_name="historial_contactos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )
    st.dataframe(
        export_table,
        use_container_width=True,
        hide_index=True,
        height=260,
        row_height=30,
        column_config={
            "Restaurante": st.column_config.TextColumn("Restaurante", width="medium", max_chars=28),
            "Comuna": st.column_config.TextColumn("Comuna", width="small", max_chars=16),
            "Canal": st.column_config.TextColumn("Canal", width="small"),
            "Acción": st.column_config.TextColumn("Acción", width="medium"),
            "Estado CRM": st.column_config.TextColumn("Estado CRM", width="small"),
            "Resultado seguimiento": st.column_config.TextColumn("Resultado", width="medium"),
            "Fecha contacto": st.column_config.TextColumn("Fecha contacto", width="small"),
            "Mensaje / detalle": st.column_config.TextColumn("Mensaje / detalle", width="large", max_chars=52),
        },
    )


def render_crm_rules() -> None:
    st.markdown('<div class="section-title">Reglas CRM</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="rules-grid">
            <div class="rules-card automation">
                <div class="rules-title">Automatizaciones</div>
                <ul>
                    <li>Después de 24h: Nuevo → Pendiente contacto.</li>
                    <li>Al abrir WhatsApp: Estado CRM → Contactado.</li>
                    <li>Al abrir WhatsApp: Estado WhatsApp → Contactado manualmente.</li>
                    <li>Al abrir WhatsApp: Resultado seguimiento → Sin respuesta.</li>
                    <li>Se guarda fecha/hora y mensaje enviado.</li>
                    <li>Al llamar: se registra el evento y el lead queda Contactado.</li>
                    <li>Si pasan 3 días sin respuesta: se genera una alerta en el historial.</li>
                    <li>El mensaje WhatsApp se elige aleatoriamente entre los mensajes activos.</li>
                </ul>
            </div>
            <div class="rules-card manual">
                <div class="rules-title">Acciones manuales</div>
                <ul>
                    <li>Cambiar Estado CRM entre Nuevo, Pendiente contacto y Contactado.</li>
                    <li>Cambiar Resultado seguimiento: Sin respuesta, No interesado, Negociando, Local cerrado, Ya está en Rappi o En proceso de firma.</li>
                    <li>Escribir notas comerciales.</li>
                    <li>Revisar la línea de tiempo y el historial de contactos.</li>
                    <li>Editar mensajes WhatsApp desde el pop-up.</li>
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_testing_tools() -> None:
    st.markdown('<div class="section-title">Herramientas de testing</div>', unsafe_allow_html=True)
    st.caption("Estas acciones no borran restaurantes ni datos de scraping. Solo reinician estados CRM/WhatsApp.")
    feedback = clean_text(st.session_state.get("reset_feedback_message", ""))
    stats = st.session_state.get("last_reset_stats", {})
    if feedback:
        st.success(feedback)
    if isinstance(stats, dict) and stats:
        st.caption(
            "Último reset: "
            f"modo datos = {stats.get('data_mode', get_data_mode())} · "
            f"eventos antes = {stats.get('total_before', 0)} · "
            f"eventos eliminados = {stats.get('deleted', 0)} · "
            f"eventos iniciales conservados = {stats.get('kept_initial', 0)} · "
            f"eventos después = {stats.get('total_after', 0)}"
        )
    options = {
        "Reiniciar leads Contactados": "contactados",
        "Reiniciar leads Respondidos": "respondidos",
        "Reiniciar todos los leads de prueba": "todos",
    }
    selected_label = st.selectbox("Tipo de reset", list(options), key="testing_reset_option")
    confirm = st.checkbox("Confirmo que solo quiero reiniciar estados comerciales.", key="testing_reset_confirm")
    if st.button("Ejecutar reset", type="secondary", use_container_width=True, disabled=not confirm, key="testing_reset_run"):
        affected = reset_massive_leads(options[selected_label])
        cleaned = int(st.session_state.get("reset_cleaned_events", 0))
        st.session_state["reset_feedback_message"] = (
            "Se reiniciaron estados y se limpiaron eventos de contacto, manteniendo el evento inicial del lead. "
            f"Leads afectados: {affected}. Eventos eliminados: {cleaned}."
        )
        st.rerun()


def validate_message_template(text: str) -> list[str]:
    warnings = []
    if "{nombre}" not in text:
        warnings.append("Falta {nombre}. Se puede guardar igual, pero el mensaje será menos personalizado.")
    if len(text) > 320:
        warnings.append("Mensaje largo. WhatsApp lo soporta, pero podría verse menos natural.")
    try:
        text.format(nombre="Demo", comuna="Las Condes")
    except KeyError as exc:
        warnings.append(f"Variable no reconocida: {{{exc.args[0]}}}. Usa solo {{nombre}} y {{comuna}}.")
    return warnings


def render_whatsapp_messages_editor_body(selected_row: pd.Series | None, name_col: str | None, comuna_col: str | None) -> None:
    config = load_message_config()
    preview_name = selected_row.get(name_col, "Demo") if selected_row is not None and name_col else "Demo"
    preview_comuna = selected_row.get(comuna_col, "Las Condes") if selected_row is not None and comuna_col else "Las Condes"

    st.markdown('<div class="section-title">Mensajes WhatsApp</div>', unsafe_allow_html=True)
    st.caption("Edita los mensajes que se usan para abrir WhatsApp. Puedes activar o pausar cada mensaje.")

    for variant in DEFAULT_MESSAGE_VARIANTS:
        item = config.get(variant, {"text": DEFAULT_MESSAGE_VARIANTS[variant], "active": True})
        text_key = f"msg_variant_text_{variant}"
        active_key = f"msg_variant_active_{variant}"
        st.markdown(f"**Mensaje {variant}**")
        st.checkbox("Activo", value=bool(item.get("active", True)), key=active_key)
        text = st.text_area(
            f"Texto mensaje {variant}",
            value=clean_text(item.get("text", DEFAULT_MESSAGE_VARIANTS[variant])),
            height=220,
            key=text_key,
            label_visibility="collapsed",
        )
        st.caption(f"{len(text)} caracteres")
        for warning in validate_message_template(text):
            st.warning(warning)
        try:
            preview = text.format(nombre=clean_text(preview_name) or "Demo", comuna=clean_text(preview_comuna) or "Las Condes")
        except KeyError:
            preview = text
        st.markdown(
            f'<div class="message-preview-box"><strong>Vista previa</strong><br>{html.escape(preview)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="crm-divider"></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="small")
    if c1.button("Guardar mensajes", key="save_all_whatsapp_messages", use_container_width=True):
        updated = {}
        for variant in DEFAULT_MESSAGE_VARIANTS:
            updated[variant] = {
                "text": clean_text(st.session_state.get(f"msg_variant_text_{variant}", DEFAULT_MESSAGE_VARIANTS[variant])),
                "active": bool(st.session_state.get(f"msg_variant_active_{variant}", True)),
            }
        save_message_config(updated)
        active_messages = load_message_variants()
        refresh_whatsapp_message_state(active_messages)
        st.session_state["messages_saved_notice"] = (
            f"Mensajes guardados. Mensaje activo actualizado: {', '.join(active_messages.keys())}."
        )
        st.session_state["show_message_editor"] = False
        st.rerun()
    if c2.button("Restaurar por defecto", key="reset_all_whatsapp_messages", use_container_width=True):
        save_message_config(default_message_config())
        for variant, text in DEFAULT_MESSAGE_VARIANTS.items():
            st.session_state[f"msg_variant_text_{variant}"] = text
            st.session_state[f"msg_variant_active_{variant}"] = True
        active_messages = load_message_variants()
        refresh_whatsapp_message_state(active_messages)
        st.session_state["messages_saved_notice"] = (
            f"Mensajes restaurados. Mensaje activo actualizado: {', '.join(active_messages.keys())}."
        )
        st.rerun()
    if c3.button("Cerrar", key="close_whatsapp_messages", use_container_width=True):
        st.session_state["show_message_editor"] = False
        st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("Editar mensajes WhatsApp")
    def render_whatsapp_messages_dialog(selected_row: pd.Series | None, name_col: str | None, comuna_col: str | None) -> None:
        render_whatsapp_messages_editor_body(selected_row, name_col, comuna_col)
else:
    def render_whatsapp_messages_dialog(selected_row: pd.Series | None, name_col: str | None, comuna_col: str | None) -> None:
        with st.expander("Editar mensajes WhatsApp", expanded=True):
            render_whatsapp_messages_editor_body(selected_row, name_col, comuna_col)


def render_whatsapp_messages_launcher(selected_row: pd.Series | None, name_col: str | None, comuna_col: str | None) -> None:
    if st.button("⚙", key="open_whatsapp_messages_editor", help="Editar mensajes WhatsApp", use_container_width=True):
        st.session_state["show_message_editor"] = True
    if st.session_state.get("show_message_editor") and selected_row is not None:
        render_whatsapp_messages_dialog(selected_row, name_col, comuna_col)


def render_crm_comercial_unified(df: pd.DataFrame) -> None:
    render_kpi_cards(
        [
            ("Total restaurantes", len(df)),
            ("Alto potencial", metric_count(df, "Nivel comercial", "Alto potencial")),
            ("Pendientes contacto", state_count(df, PENDING_STATES)),
            ("Contactados", state_count(df, CONTACTED_STATES)),
            ("Negociando", metric_count(df, "Resultado seguimiento", "Negociando")),
        ]
    )

    render_panel_grid_spacer()
    with st.container(border=True):
        filtered = apply_crm_filters_compact(df)

    render_lead_workspace_fragment(df, filtered)

    render_panel_grid_spacer()
    with st.expander("Reglas CRM", expanded=False):
        render_crm_rules()

    render_panel_grid_spacer()
    with st.container(border=True):
        render_testing_tools()


def render_update_base_unified(base: pd.DataFrame) -> None:
    finished_now = finalize_update_process_if_done()
    if finished_now:
        st.rerun()

    config = load_manual_config()
    if not config:
        st.error(f"No se encontró la configuración: {MANUAL_CONFIG}")
        return

    options = comuna_options(base, config)
    names = [item["comuna"] for item in options]
    default_names = [item["comuna"] for item in config.get("comunas", []) if item.get("comuna") in names] or names[:1]
    st.markdown(
        f'<div class="muted-text">Base actual: {len(base)} restaurantes · Ultima actualizacion: {format_mtime(BASE_XLSX)}</div>',
        unsafe_allow_html=True,
    )
    render_panel_grid_spacer()
    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        with st.container(border=True):
            st.markdown('<div class="section-title">Configuración de búsqueda</div>', unsafe_allow_html=True)
            objetivo = st.number_input("Objetivo", min_value=1, max_value=50, value=10, step=1, help="Cantidad máxima de restaurantes nuevos que se intentará agregar.", key="upd_objetivo")
            max_resultados = st.number_input("Resultados/comuna", min_value=1, max_value=50, value=min(int(config.get("maxResultadosPorComuna", 15)), 50), step=1, help="Cantidad de restaurantes que se revisarán por cada comuna seleccionada.", key="upd_resultados")
            max_scrolls = st.number_input("Scrolls", min_value=1, max_value=10, value=min(int(config.get("maxScrollsPorComuna", 4)), 10), step=1, help="Veces que baja en Google Maps para encontrar más locales.", key="upd_scrolls")
            selected_names = st.multiselect("Comunas", names, default=default_names, placeholder="Seleccionar comunas", help="Comunas donde se buscarán restaurantes nuevos.", key="upd_comunas")
            selected = [item for item in options if item["comuna"] in selected_names]

    with right:
        with st.container(border=True):
            st.markdown('<div class="section-title">Resumen y acciones</div>', unsafe_allow_html=True)
            update_running = is_update_process_running()
            if update_running:
                st.markdown(
                    """
                    <div class="result-card">
                        <div class="result-card-title">Búsqueda en curso</div>
                        <div class="result-card-text">Google Maps está buscando restaurantes nuevos. Puedes cancelar la búsqueda si lo necesitas.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                poll_update_process()
            elif st.session_state.get("last_update_status"):
                st.markdown(
                    f"""
                    <div class="result-card">
                        <div class="result-card-title">Búsqueda terminada</div>
                        <div class="result-card-text">{st.session_state["last_update_status"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.session_state.get("last_update_summary"):
                    summary_to_show = st.session_state.get("last_update_summary", {})
                    render_kpi_cards(
                        [
                            ("Nuevos agregados", summary_to_show.get("insertados", 0)),
                            ("Duplicados ignorados", summary_to_show.get("duplicados", 0)),
                            ("Errores", summary_to_show.get("errores", 0)),
                            ("Base final", summary_to_show.get("totalFinal", len(base)) or len(base)),
                        ],
                        compact=True,
                    )

            running = update_running or is_update_running()
            if running and not update_running:
                st.warning("Ya hay una búsqueda en curso. Espera a que termine o cancélala si lo necesitas.")
            if st.button("Buscar nuevos restaurantes", type="primary", disabled=running or not selected, use_container_width=True, key="upd_run"):
                config_path = write_ui_config(config, selected, int(objetivo), int(max_resultados), int(max_scrolls))
                start_update_process(config_path)
                st.rerun()
            if update_running:
                if st.button("Cancelar búsqueda", use_container_width=True, key="upd_cancel"):
                    cancel_update_process()
                    st.rerun()
            if st.button("Ver último log", use_container_width=True, key="upd_log"):
                st.session_state["show_update_log"] = not st.session_state.get("show_update_log", False)
            if st.button("Abrir Excel actualizado", use_container_width=True, disabled=not BASE_XLSX.exists(), key="upd_excel"):
                ok, message = open_excel_file()
                if ok:
                    st.success(message)
                else:
                    st.warning(message)
            if st.session_state.get("show_update_log", False):
                st.code(read_latest_log() or "Aún no hay registros de búsqueda.", language="text")


def main() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    inject_styles()
    if not is_authenticated():
        render_login_screen()
        return
    render_header()

    base = load_base()
    if base.empty:
        st.error(f"No se encontró la base principal: {BASE_XLSX}")
        return

    crm = load_crm_state()
    if auto_transition_pending_contacts(base, crm):
        crm = load_crm_state()
    df = merge_crm(base, crm)
    added_events = generate_restaurant_added_events(df)
    alert_count = generate_no_response_alerts(df)
    if alert_count:
        st.session_state["system_alert_count"] = alert_count
    if added_events:
        st.session_state["restaurant_added_events"] = added_events
    if st.session_state.get("auto_pending_count"):
        st.info(f'{st.session_state["auto_pending_count"]} restaurantes nuevos pasaron automáticamente a "Pendiente contacto".')
    if st.session_state.get("system_alert_count"):
        st.info(f'{st.session_state.pop("system_alert_count")} alertas de falta de respuesta se agregaron al historial.')
    if st.session_state.get("restaurant_added_events"):
        st.session_state.pop("restaurant_added_events")

    tab_crm, tab_update = st.tabs(["CRM Comercial", "Actualizar base"])
    with tab_crm:
        render_crm_comercial_unified(df)
    with tab_update:
        render_update_base_unified(base)

    st.divider()
    st.caption(f"Base principal: {BASE_XLSX}")
    st.caption(f"Seguimiento comercial: {CRM_XLSX}")


if __name__ == "__main__":
    main()
