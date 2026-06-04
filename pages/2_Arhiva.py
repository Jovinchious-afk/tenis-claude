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


def _recompute_ticket_status(ticket: dict) -> None:
    if ticket.get("status") == "analysis_only":
        return
    updated = db.get_ticket_by_date(ticket.get("ticket_date", ""))
    if not updated:
        return
    matches = updated.get("ticket_matches", [])
    lost_count = sum(1 for m in matches if m.get("result") == "lost")
    pending_count = sum(1 for m in matches if m.get("result") == "pending")
    if lost_count > 0:
        db.update_ticket_status(updated["id"], "lost", 0)
    elif pending_count == 0:
        actual_win = updated.get("stake", 50) * updated.get("total_odds", 1)
        db.update_ticket_status(updated["id"], "won", actual_win)
    else:
        db.update_ticket_status(updated["id"], "pending")


def _analysis_outcome(t: dict) -> str:
    matches = t.get("ticket_matches", [])
    non_void = [m.get("result", "pending") for m in matches if m.get("result") != "void"]
    if not non_void or any(r == "pending" for r in non_void):
        return "📊 ANALYSIS"
    if any(r == "lost" for r in non_void):
        return "❌ LOST ANALYSIS"
    return "✅ WON ANALYSIS"

st.set_page_config(page_title="Archive | Tennis Agent", page_icon="🎾", layout="wide")
st.title("📋 Ticket Archive")

tickets = db.get_tickets(limit=100)

if not tickets:
    st.info("Nema tiketa u arhivi.")
    st.stop()

# Summary metrics
won = [t for t in tickets if t.get("status") == "won"]
lost = [t for t in tickets if t.get("status") == "lost"]
pending = [t for t in tickets if t.get("status") == "pending"]
analysis_only = [t for t in tickets if t.get("status") == "analysis_only"]
resolved = won + lost

total_staked = len(resolved) * 50.0
total_returned = sum(t.get("actual_win", 0) or 0 for t in won)
roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0
balance = total_returned - total_staked

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("Total tickets", len(resolved))
with col2:
    st.metric("Won", len(won), delta=f"{len(won)/len(resolved)*100:.0f}%" if resolved else "0%")
with col3:
    st.metric("Lost", len(lost))
with col4:
    roi_hex = "#22c55e" if roi >= 0 else "#ef4444"
    sign = "+" if balance >= 0 else ""
    st.markdown(f"""
    <div style="padding:4px 0">
        <div style="font-size:0.85rem;color:#9ca3af;margin-bottom:4px;">ROI</div>
        <div style="font-size:2rem;font-weight:700;color:{roi_hex};line-height:1.1">{roi:.1f}%</div>
        <div style="font-size:0.85rem;color:{roi_hex};">{sign}€{balance:.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col5:
    st.metric("Pending", len(pending))
with col6:
    st.metric("Analysis days", len(analysis_only))

if pending:
    st.info(f"{len(pending)} ticket(s) still waiting for results.")

st.markdown("---")

# Tablica — resolved + analysis_only, sortirani po datumu
rows = []
running_balance = 0.0
table_tickets = sorted(resolved + analysis_only, key=lambda t: t.get("ticket_date", ""))

for t in table_tickets:
    status = t.get("status", "")
    won_t = status == "won"
    is_ao = status == "analysis_only"
    actual_win = t.get("actual_win", 0) or 0
    if not is_ao:
        running_balance += (actual_win - 50) if won_t else -50
    matches = t.get("ticket_matches", [])
    picked = [m.get("pick", "") for m in matches]

    rows.append({
        "Date": t.get("ticket_date", ""),
        "Status": "✅ WON" if won_t else (_analysis_outcome(t) if is_ao else "❌ LOST"),
        "Picks": len(matches),
        "Combined odds": "—" if is_ao else f"{t.get('total_odds', 0):.2f}",
        "Pot. return": "—" if is_ao else f"€{t.get('potential_win', 0):.2f}",
        "Returned": f"€{actual_win:.2f}" if won_t else "—",
        "Running balance": "—" if is_ao else f"€{running_balance:.2f}",
        "Selections": ", ".join(picked),
    })

df_tickets = pd.DataFrame(rows)

def _color_row(row):
    status = str(row.get("Status", ""))
    if "LOST ANALYSIS" in status:
        return ["background-color: #fed7aa; color: #7c2d12"] * len(row)
    if "WON ANALYSIS" in status:
        return ["background-color: #bbf7d0; color: #14532d"] * len(row)
    if "ANALYSIS" in status:
        return ["background-color: #ddd6fe; color: #3b0764"] * len(row)
    if "WON" in status:
        return ["background-color: #bbf7d0; color: #14532d"] * len(row)
    if "LOST" in status:
        return ["background-color: #fca5a5; color: #7f1d1d"] * len(row)
    return [""] * len(row)

st.dataframe(
    df_tickets.style.apply(_color_row, axis=1),
    use_container_width=True,
    hide_index=True,
    height=500,
)

st.markdown("---")

# Detalji odabranog tiketa
st.subheader("Ticket details")
ticket_dates = [t.get("ticket_date", "") for t in tickets]
selected_date = st.selectbox("Select ticket:", ticket_dates)

selected = next((t for t in tickets if t.get("ticket_date") == selected_date), None)
if selected:
    matches = selected.get("ticket_matches", [])
    status = selected.get("status", "pending")

    if selected.get("ticket_summary"):
        label = "📊 Analysis write-up" if selected.get("status") == "analysis_only" else "📝 Ticket write-up"
        with st.expander(label, expanded=True):
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
                st.write(f"**Match:** {m.get('player1','')} vs {m.get('player2','')}")
                st.write(f"**Pick:** {m.get('pick','')}")
                st.write(f"**Odds:** {m.get('odds',0):.2f}")
                st.write(f"**Confidence:** {m.get('confidence',0):.0f}%")
            with c2:
                st.write(f"**Round:** {m.get('round','')}")
                st.write(f"**Date:** {m.get('match_date','')}")
                if m_result == "void":
                    st.markdown("**Result:** 🟡 Walkover / Postponed")
                else:
                    st.write(f"**Result:** {m_result}")
                if m.get("actual_winner"):
                    st.write(f"**Winner:** {m.get('actual_winner','')}")

            # Manual result override (pending or correct a wrong resolved result)
            if m_result != "void":
                st.markdown("---")
                label = "Manually set result:" if m_result == "pending" else "Override result (correct error):"
                st.caption(label)
                col_w, col_l, col_v = st.columns(3)
                match_id = m.get("id", "")
                pick = m.get("pick", "")
                p1 = m.get("player1", "")
                p2 = m.get("player2", "")
                with col_w:
                    if st.button("✅ Won", key=f"won_{match_id}", disabled=(m_result == "won")):
                        db.update_match_result(match_id, "won", pick)
                        _recompute_ticket_status(selected)
                        st.success("Marked as won")
                        st.rerun()
                with col_l:
                    if st.button("❌ Lost", key=f"lost_{match_id}", disabled=(m_result == "lost")):
                        actual = p2 if _names_match(pick, p1) else p1
                        db.update_match_result(match_id, "lost", actual)
                        _recompute_ticket_status(selected)
                        st.success("Marked as lost")
                        st.rerun()
                with col_v:
                    if st.button("🟡 Void", key=f"void_{match_id}"):
                        db.update_match_result(match_id, "void", "Walkover / Postponed")
                        _recompute_ticket_status(selected)
                        st.success("Marked as void")
                        st.rerun()
