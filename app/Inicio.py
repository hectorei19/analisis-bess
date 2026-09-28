"""
Página de inicio. Arrancar la web desde la carpeta del proyecto con:
    .\\.venv\\Scripts\\python.exe -m streamlit run app/Inicio.py
"""

import streamlit as st

from common import branding, footer, setup_page, t

lang = setup_page("app_title")
st.title(t(lang, "app_title"))
st.caption(branding()["company"]["name"])
st.write(t(lang, "home_intro"))
st.write(t(lang, "home_status"))
st.page_link("pages/1_Ingresos_diarios.py", label=t(lang, "page_daily"), icon="📈")
footer(lang)
