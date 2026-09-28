"""Piezas compartidas por todas las páginas: marca, idioma, aviso legal y contacto."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:          # para poder importar src.*
    sys.path.insert(0, str(PROJECT_ROOT))

from i18n import TEXTS  # noqa: E402


@st.cache_data
def branding() -> dict:
    with open(APP_DIR / "branding.toml", "rb") as f:
        return tomllib.load(f)


def setup_page(title_key: str) -> str:
    """Configura la página y la barra lateral. Devuelve el idioma elegido."""
    brand = branding()
    st.set_page_config(page_title=f"{brand['company']['name']} · {TEXTS['es'][title_key]}",
                       layout="wide")
    logo = brand["company"].get("logo")
    if logo:
        st.logo(str(APP_DIR / logo))
    return st.sidebar.radio("Idioma / Language", ["es", "en"],
                            format_func=lambda x: {"es": "Español", "en": "English"}[x],
                            horizontal=True, key="lang")


def t(lang: str, key: str, **kwargs) -> str:
    return TEXTS[lang][key].format(**kwargs)


def footer(lang: str) -> None:
    """Fuente, aviso legal y llamada a la acción: van al pie de cada página."""
    brand = branding()
    st.divider()
    st.caption(t(lang, "source"))
    st.caption(t(lang, "disclaimer"))
    col_text, col_btn = st.columns([4, 1], vertical_alignment="center")
    col_text.markdown(f"**{t(lang, 'cta', company=brand['company']['name'])}**")
    if brand["company"].get("contact_url"):
        col_btn.link_button(t(lang, "cta_button"), brand["company"]["contact_url"],
                            type="primary")
