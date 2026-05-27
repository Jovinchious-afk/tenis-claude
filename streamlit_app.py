"""
Glavni entry point za Streamlit aplikaciju.
Postavlja izgled i navigaciju između stranica.
"""
import streamlit as st

st.set_page_config(
    page_title="Tennis Agent",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Globalni CSS
st.markdown("""
<style>
    .won-badge { background:#22c55e; color:white; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:bold; }
    .lost-badge { background:#ef4444; color:white; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:bold; }
    .pending-badge { background:#f59e0b; color:white; padding:3px 10px; border-radius:12px; font-size:13px; font-weight:bold; }
    .value-badge { background:#3b82f6; color:white; padding:2px 8px; border-radius:8px; font-size:11px; }
    .metric-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🎾 Tennis Agent")
st.sidebar.markdown("---")
st.sidebar.caption("Automatska tenis prognoza")
st.sidebar.markdown("Odaberi stranicu u gornjem izborniku.")

st.title("🎾 Tennis Agent")
st.markdown("""
Dobrodošao u Tennis Agent! Koristi navigaciju gore za pristup stranicama:

- **Dnevni Listić** — današnji/sutrašnji tiket
- **Arhiva** — svi prošli listići
- **Analiza Gubitaka** — što je pošlo po krivu
- **Model Statistike** — ROI, win rate, težine modela
""")
