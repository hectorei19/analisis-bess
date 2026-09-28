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
    brand = branding()["company"]
    title = TEXTS["es"][title_key]
    st.set_page_config(page_title=f"{brand['name']} · {title}" if brand["name"] else title,
                       layout="wide")
    if brand.get("logo"):
        st.logo(str(APP_DIR / brand["logo"]))
    return st.sidebar.radio("Idioma / Language", ["es", "en"],
                            format_func=lambda x: {"es": "Español", "en": "English"}[x],
                            horizontal=True, key="lang")


def t(lang: str, key: str, **kwargs) -> str:
    return TEXTS[lang][key].format(**kwargs)


def footer(lang: str) -> None:
    """Fuente y aviso legal (siempre) y llamada a la acción (si hay enlace de contacto)."""
    contact_url = branding()["company"].get("contact_url")
    st.divider()
    st.caption(t(lang, "source"))
    st.caption(t(lang, "disclaimer"))
    if contact_url:
        col_text, col_btn = st.columns([4, 1], vertical_alignment="center")
        col_text.markdown(f"**{t(lang, 'cta')}**")
        col_btn.link_button(t(lang, "cta_button"), contact_url, type="primary")
