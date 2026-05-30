"""
Stranica 1: Dnevni Listić
Prikazuje trenutni/najnoviji tiket s detaljima svakog para.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from database import supabase_client as db
from utils.helpers import today_zagreb, format_date, format_date_hr

st.set_page_config(page_title="Daily Ticket | Tennis Agent", page_icon="🎾", layout="wide")
st.title("🎾 Daily Ticket")


def _status_badge(status: str) -> str:
    colors = {"won": "#22c55e", "lost": "#ef4444", "pending": "#f59e0b", "void": "#9ca3af"}
    labels = {"won": "✅ WON", "lost": "❌ LOST", "pending": "⏳ PENDING", "void": "⚪ VOID"}
    c = colors.get(status, "#9ca3af")
    l = labels.get(status, status.upper())
    return f'<span style="background:{c};color:white;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold;">{l}</span>'


def _risk_color(risk: str) -> str:
    return {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444",
            "nizak": "#22c55e", "srednji": "#f59e0b", "visok": "#ef4444"}.get(risk.lower() if risk else "", "#9ca3af")


today_str = format_date(today_zagreb())
ticket = db.get_ticket_by_date(today_str)

if not ticket:
    st.info("No ticket for today. Run the Daily Ticket action on GitHub to generate one.")
    st.markdown("---")
    st.subheader("Latest available ticket")
    tickets = db.get_tickets(limit=1)
    ticket = tickets[0] if tickets else None

if not ticket:
    st.warning("No tickets in database. Check that the agent has been run.")
    st.stop()

matches = ticket.get("ticket_matches", [])
status = ticket.get("status", "pending")
ticket_date = ticket.get("ticket_date", "")

# Header
col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
with col1:
    st.subheader(f"Tiket — {format_date_hr(today_zagreb()) if ticket_date == today_str else ticket_date}")
    st.markdown(_status_badge(status), unsafe_allow_html=True)
with col2:
    st.metric("Combined odds", f"{ticket.get('total_odds', 0):.2f}")
with col3:
    st.metric("Potential return", f"€{ticket.get('potential_win', 0):.2f}")
with col4:
    won_count = sum(1 for m in matches if m.get("result") == "won")
    st.metric("Correct picks", f"{won_count}/{len(matches)}")
with col5:
    if st.button("🗑️ Delete ticket", type="secondary", use_container_width=True):
        if db.delete_ticket(str(ticket.get("id", ""))):
            st.success("Ticket deleted.")
            st.rerun()
        else:
            st.error("Error deleting ticket.")

st.markdown("---")

# Summary
if ticket.get("ticket_summary"):
    with st.expander("📝 Ticket write-up", expanded=True):
        st.markdown(ticket["ticket_summary"])

st.markdown("---")

# Parovi
for i, m in enumerate(matches):
    m_result = m.get("result", "pending")
    border_color = {"won": "#22c55e", "lost": "#ef4444", "pending": "#94a3b8"}.get(m_result, "#94a3b8")

    with st.container():
        st.markdown(f"""<div style="border-left:4px solid {border_color};padding-left:12px;margin-bottom:16px;">""", unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 2])

        with c1:
            st.markdown(f"**{i+1}. {m.get('pick', '')}** to win")
            st.caption(f"{m.get('player1','')} vs {m.get('player2','')}")
            st.caption(f"🏆 {m.get('tournament','')} · {m.get('surface','')} · {m.get('round','')}")
            if m.get("match_date"):
                st.caption(f"📅 {m.get('match_date','')}" + (f" {m.get('match_time','')}" if m.get("match_time") else ""))

        with c2:
            st.metric("Kvota", f"{m.get('odds', 0):.2f}")
            if m.get("value_bet"):
                st.markdown('<span style="background:#3b82f6;color:white;padding:2px 8px;border-radius:6px;font-size:11px;">VALUE ✓</span>', unsafe_allow_html=True)

        with c3:
            st.metric("Confidence", f"{m.get('confidence', 0):.0f}%")
            fair = m.get("fair_odds")
            if fair:
                st.caption(f"Fair odds: {fair:.2f}")

        with c4:
            risk = m.get("risk_level", "srednji")
            rc = _risk_color(risk)
            st.markdown(f'<span style="color:{rc};font-weight:bold;">{risk.upper()}</span>', unsafe_allow_html=True)
            st.markdown(_status_badge(m_result), unsafe_allow_html=True)

        with c5:
            if m.get("risk_notes"):
                st.caption(f"⚠️ {m['risk_notes']}")
            if m.get("handicap_option"):
                st.caption(f"📊 Handicap: {m['handicap_option']}")
            if m.get("actual_winner") and m_result != "pending":
                st.caption(f"🏁 Winner: {m['actual_winner']}")

        st.markdown("</div>", unsafe_allow_html=True)

    if m.get("key_factors"):
        with st.expander(f"Key factors — {m.get('pick','')}"):
            for factor in m.get("key_factors", []):
                st.write(f"• {factor}")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Stake:** €{ticket.get('stake', 50):.0f}")
    st.markdown(f"**Combined odds:** {ticket.get('total_odds', 0):.2f}")
with col2:
    st.markdown(f"**Potential return:** €{ticket.get('potential_win', 0):.2f}")
    if status == "won":
        st.markdown(f"**Actual return:** €{ticket.get('actual_win', 0):.2f}")
