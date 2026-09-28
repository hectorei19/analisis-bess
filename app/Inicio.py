"""
Página de inicio. Arrancar la web desde la carpeta del proyecto con:
    .\\.venv\\Scripts\\python.exe -m streamlit run app/Inicio.py
"""

import streamlit as st

from common import branding, footer, setup_page, t

lang = setup_page("app_title")
st.title(t(lang, "app_title"))
if branding()["company"]["name"]:
    st.caption(branding()["company"]["name"])
st.write(t(lang, "home_intro"))
st.write(t(lang, "home_status"))
st.page_link("pages/1_Calculadora_BESS.py", label=t(lang, "page_calc"), icon="📈")
footer(lang)
