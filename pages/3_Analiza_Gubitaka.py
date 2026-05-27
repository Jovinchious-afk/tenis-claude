"""
Stranica 3: Analiza Gubitaka
Claude-ova analiza izgubljenih parova — zašto smo pogriješili.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from database import supabase_client as db

st.set_page_config(page_title="Analiza Gubitaka | Tennis Agent", page_icon="🎾", layout="wide")
st.title("🔍 Analiza Gubitaka")
st.markdown("Detaljne analize izgubljenih parova — zašto je procjena bila pogrešna i što promijeniti.")

tickets = db.get_tickets(limit=100)
lost_tickets = [t for t in tickets if t.get("status") == "lost"]

if not lost_tickets:
    st.success("Nema izgubljenih tiketa u arhivi. Odlično!")
    st.stop()

# Sve izgubljene parove s analizom
all_lost_matches = []
for t in lost_tickets:
    for m in t.get("ticket_matches", []):
        if m.get("result") == "lost":
            m["ticket_date"] = t.get("ticket_date", "")
            all_lost_matches.append(m)

analyzed = [m for m in all_lost_matches if m.get("loss_analysis")]
not_analyzed = [m for m in all_lost_matches if not m.get("loss_analysis")]

col1, col2 = st.columns(2)
with col1:
    st.metric("Ukupno izgubljenih parova", len(all_lost_matches))
with col2:
    st.metric("Analiziranih", len(analyzed))

if not_analyzed:
    st.info(f"{len(not_analyzed)} parova još nije analizirano (analiza se izvodi automatski 2 dana nakon meča).")

st.markdown("---")

# Filter
surface_filter = st.selectbox("Filtriraj po podlozi:", ["Sve", "Clay", "Hard", "Grass", "Indoor Hard"])
tournament_filter = st.text_input("Filtriraj po turniru:", "")

filtered = analyzed
if surface_filter != "Sve":
    filtered = [m for m in filtered if m.get("surface", "") == surface_filter]
if tournament_filter:
    filtered = [m for m in filtered if tournament_filter.lower() in m.get("tournament", "").lower()]

st.markdown(f"**Prikazujem {len(filtered)} analiziranih gubitaka:**")
st.markdown("---")

if not filtered:
    st.info("Nema rezultata za odabrane filtre.")
    st.stop()

for m in filtered:
    with st.expander(
        f"❌ {m.get('pick','')} — {m.get('player1','')} vs {m.get('player2','')} ({m.get('ticket_date','')})",
        expanded=False
    ):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Turnir:** {m.get('tournament','')}")
            st.write(f"**Podloga:** {m.get('surface','')}")
            st.write(f"**Runda:** {m.get('round','')}")
        with col2:
            st.write(f"**Naš pick:** {m.get('pick','')}")
            st.write(f"**Confidence:** {m.get('confidence',0):.0f}%")
            st.write(f"**Kvota:** {m.get('odds',0):.2f}")
        with col3:
            st.write(f"**Pobijedio:** {m.get('actual_winner','N/A')}")
            st.write(f"**Score:** {m.get('actual_score','N/A')}")
            st.write(f"**Rizik bio:** {m.get('risk_level','N/A')}")

        if m.get("risk_notes"):
            st.warning(f"⚠️ Navedeni rizici: {m['risk_notes']}")

        if m.get("key_factors"):
            st.write(f"**Faktori koji su odredili pick:** {', '.join(m.get('key_factors',[]))}")

        st.markdown("**🤖 Claude analiza greške:**")
        st.info(m.get("loss_analysis", "Analiza nije dostupna."))


# Agregirana statistika grešaka
st.markdown("---")
st.subheader("📊 Obrasci grešaka")

if len(analyzed) >= 3:
    from collections import Counter
    surfaces = Counter(m.get("surface","") for m in analyzed)
    st.write("**Greške po podlozi:**")
    for surface, count in surfaces.most_common():
        st.write(f"  • {surface}: {count}")

    col1, col2 = st.columns(2)
    with col1:
        avg_conf = sum(m.get("confidence",0) for m in analyzed) / len(analyzed)
        st.metric("Prosječni confidence izgubljenih", f"{avg_conf:.0f}%")
    with col2:
        high_conf_lost = sum(1 for m in analyzed if m.get("confidence",0) >= 70)
        st.metric("Izgubili s conf. ≥70%", high_conf_lost)
else:
    st.info("Nedovoljno podataka za agregiranu statistiku (potrebno min. 3 analize).")
