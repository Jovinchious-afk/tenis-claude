"""
Stranica 2: Arhiva Listića
Svi prošli tiketi s W/L statusom i running totals.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from database import supabase_client as db


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a.split()[-1] == b.split()[-1]

st.set_page_config(page_title="Arhiva | Tennis Agent", page_icon="🎾", layout="wide")
st.title("📋 Arhiva Listića")

tickets = db.get_tickets(limit=100)

if not tickets:
    st.info("Nema tiketa u arhivi.")
    st.stop()

# Summary metrics
won = [t for t in tickets if t.get("status") == "won"]
lost = [t for t in tickets if t.get("status") == "lost"]
pending = [t for t in tickets if t.get("status") == "pending"]
resolved = won + lost

total_staked = len(resolved) * 50.0
total_returned = sum(t.get("actual_win", 0) or 0 for t in won)
roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0
balance = total_returned - total_staked

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Ukupno tiketa", len(resolved))
with col2:
    st.metric("Dobiveni", len(won), delta=f"{len(won)/len(resolved)*100:.0f}%" if resolved else "0%")
with col3:
    st.metric("Izgubljeni", len(lost))
with col4:
    roi_delta = "positive" if roi > 0 else "negative"
    st.metric("ROI", f"{roi:.1f}%", delta=f"€{balance:.2f}")
with col5:
    st.metric("Neriješeni", len(pending))

if pending:
    st.info(f"Još {len(pending)} tiketa čeka rezultate.")

st.markdown("---")

# Tablica
rows = []
running_balance = 0.0

for t in reversed(resolved):
    won_t = t.get("status") == "won"
    actual_win = t.get("actual_win", 0) or 0
    running_balance += (actual_win - 50) if won_t else -50
    matches = t.get("ticket_matches", [])
    picked = [m.get("pick", "") for m in matches]

    rows.append({
        "Datum": t.get("ticket_date", ""),
        "Status": "✅ WON" if won_t else "❌ LOST",
        "Parovi": len(matches),
        "Ukupna kvota": f"{t.get('total_odds', 0):.2f}",
        "Pot. dobitak": f"€{t.get('potential_win', 0):.2f}",
        "Ostvaren": f"€{actual_win:.2f}" if won_t else "—",
        "Running balance": f"€{running_balance:.2f}",
        "Pikovi": ", ".join(picked),
    })

df_tickets = pd.DataFrame(rows)

def _color_row(row):
    if "WON" in str(row.get("Status", "")):
        return ["background-color: #f0fdf4"] * len(row)
    if "LOST" in str(row.get("Status", "")):
        return ["background-color: #fef2f2"] * len(row)
    return [""] * len(row)

st.dataframe(
    df_tickets.style.apply(_color_row, axis=1),
    use_container_width=True,
    hide_index=True,
    height=500,
)

st.markdown("---")

# Detalji odabranog tiketa
st.subheader("Detalji tiketa")
ticket_dates = [t.get("ticket_date", "") for t in tickets]
selected_date = st.selectbox("Odaberi tiket:", ticket_dates)

selected = next((t for t in tickets if t.get("ticket_date") == selected_date), None)
if selected:
    matches = selected.get("ticket_matches", [])
    status = selected.get("status", "pending")

    if selected.get("ticket_summary"):
        with st.expander("📝 Write-up tiketa", expanded=True):
            st.markdown(selected["ticket_summary"])
        st.markdown("---")

    for m in matches:
        m_result = m.get("result", "pending")
        if m_result == "won":
            icon = "✅"
        elif m_result == "lost":
            icon = "❌"
        elif m_result == "void":
            icon = "🟡"
        else:
            icon = "⏳"

        with st.expander(f"{icon} {m.get('pick','')} — {m.get('tournament','')} ({m.get('surface','')})", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Par:** {m.get('player1','')} vs {m.get('player2','')}")
                st.write(f"**Pick:** {m.get('pick','')}")
                st.write(f"**Kvota:** {m.get('odds',0):.2f}")
                st.write(f"**Confidence:** {m.get('confidence',0):.0f}%")
            with c2:
                st.write(f"**Runda:** {m.get('round','')}")
                st.write(f"**Datum:** {m.get('match_date','')}")
                if m_result == "void":
                    st.markdown("**Rezultat:** 🟡 Walkover / Odgoda")
                else:
                    st.write(f"**Rezultat:** {m_result}")
                if m.get("actual_winner"):
                    st.write(f"**Pobijedio:** {m.get('actual_winner','')}")

            # Ručno razrješavanje pending mečeva
            if m_result == "pending":
                st.markdown("---")
                st.caption("Ručno označi rezultat:")
                col_w, col_l, col_v = st.columns(3)
                match_id = m.get("id", "")
                pick = m.get("pick", "")
                p1 = m.get("player1", "")
                p2 = m.get("player2", "")
                with col_w:
                    if st.button("✅ Won", key=f"won_{match_id}"):
                        db.update_match_result(match_id, "won", pick)
                        st.success("Označeno kao won")
                        st.rerun()
                with col_l:
                    if st.button("❌ Lost", key=f"lost_{match_id}"):
                        actual = p2 if _names_match(pick, p1) else p1
                        db.update_match_result(match_id, "lost", actual)
                        st.success("Označeno kao lost")
                        st.rerun()
                with col_v:
                    if st.button("🟡 Void", key=f"void_{match_id}"):
                        db.update_match_result(match_id, "void", "Walkover / Odgoda")
                        st.success("Označeno kao void")
                        st.rerun()
