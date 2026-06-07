"""
Stranica 5: Kvote sa Screenshota
Upload screenshota kvota kladionice (npr. SuperSport) za turnire koje The Odds API
ne pokriva (ATP 250/500). Claude vision izvuče parove i kvote, korisnik potvrdi,
pa se spreme u Supabase — daily ticket pipeline ih automatski povlači i mergira
s Odds API rezultatima.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st
from database import supabase_client as db
from agent.data_fetcher import extract_odds_from_screenshot
from utils.helpers import today_zagreb, tomorrow_zagreb, format_date, format_date_hr

st.set_page_config(page_title="Kvote sa Screenshota | Tennis Agent", page_icon="📸", layout="wide")
st.title("📸 Kvote sa Screenshota")

st.markdown(
    "Uploadaj screenshot kvota kladionice za **službeno prvo kolo (main draw)** — "
    "**bez kvalifikacijskih mečeva**. Claude će pročitati parove i kvote, "
    "ti ih provjeriš, pa se spreme za daily ticket."
)

today = today_zagreb()
tomorrow = tomorrow_zagreb()
date_options = {
    f"Danas — {format_date_hr(today)}": format_date(today),
    f"Sutra — {format_date_hr(tomorrow)}": format_date(tomorrow),
}
date_label = st.radio("Za koji dan su ove kvote?", list(date_options.keys()), horizontal=True)
match_date = date_options[date_label]

uploaded = st.file_uploader("Screenshot kvota (PNG/JPG)", type=["png", "jpg", "jpeg"])

if uploaded is not None:
    st.image(uploaded, caption="Učitani screenshot", width=500)

    if st.button("🔍 Pročitaj kvote sa slike", type="primary"):
        media_type = uploaded.type or "image/png"
        with st.spinner("Claude čita kvote sa screenshota..."):
            extracted = extract_odds_from_screenshot(uploaded.getvalue(), media_type=media_type)
        st.session_state["extracted_odds"] = extracted
        st.session_state["extracted_for_date"] = match_date

extracted = st.session_state.get("extracted_odds")
extracted_for = st.session_state.get("extracted_for_date")

if extracted is not None and extracted_for == match_date:
    if not extracted:
        st.warning("Nisam uspio pročitati nijedan par sa slike. Pokušaj s jasnijim screenshotom.")
    else:
        st.subheader(f"Pronađeno {len(extracted)} parova — provjeri prije spremanja")
        rows = []
        for key, val in extracted.items():
            rows.append({
                "Igrač 1": val["p1"], "Kvota 1": val["p1_odds"],
                "Igrač 2": val["p2"], "Kvota 2": val["p2_odds"],
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.caption(
            "Ako nešto nije točno pročitano, otkaži i probaj ponovno s drugačijim screenshotom — "
            "trenutno nema ručne korekcije pojedinačnih redaka."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Spremi ove kvote", type="primary"):
                db.save_screenshot_odds(match_date, extracted)
                st.success(f"Spremljeno {len(extracted)} parova za {match_date}. "
                           "Daily ticket pipeline će ih sada koristiti.")
                del st.session_state["extracted_odds"]
                del st.session_state["extracted_for_date"]
                st.rerun()
        with col2:
            if st.button("❌ Odustani"):
                del st.session_state["extracted_odds"]
                del st.session_state["extracted_for_date"]
                st.rerun()

st.markdown("---")
st.subheader("Već spremljene kvote")
for label, d in date_options.items():
    saved = db.get_screenshot_odds(d)
    with st.expander(f"{label} — {len(saved)} parova"):
        if saved:
            st.dataframe(
                [{"Igrač 1": v["p1"], "Kvota 1": v["p1_odds"], "Igrač 2": v["p2"], "Kvota 2": v["p2_odds"]}
                 for v in saved.values()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("Nema spremljenih kvota za ovaj dan.")
