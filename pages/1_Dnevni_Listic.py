"""
Stranica 1: Dnevni Listić
Prikazuje trenutni/najnoviji tiket s detaljima svakog para.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from database import supabase_client as db
# ZASTARJELI MODUL U MEMORIJI — zasto ovaj try/except postoji (29.08.2026 12:45)
# Streamlit stranice se pri SVAKOJ navigaciji iznova citaju s diska, ali moduli koje
# uvoze ostaju u `sys.modules` od pokretanja aplikacije. Kad se u `utils/helpers.py`
# doda novo ime, Streamlit Cloud odmah posluzi NOVU stranicu, a ona ga trazi od STAROG
# modula u memoriji -> ImportError, sve dok se aplikacija rucno ne restarta.
# Dogodilo se 29.08.2026 u 12:40 na Dnevnom listicu i Arhivi (`pick_ledger`,
# `is_no_selection`, `MIN_PICK_CONFIDENCE`), dok su ostale stranice radile jer uvoze
# samo stara imena. `utils.helpers` je modul cistih funkcija bez stanja, pa je reload
# siguran; guard se pali samo u kvaru i sam se gasi cim modul postane svjez.
try:
    from utils.helpers import today_zagreb, format_date, format_date_hr, pick_ledger, is_no_selection, MIN_PICK_CONFIDENCE
except ImportError:
    import importlib
    import utils.helpers as _stale_helpers
    importlib.reload(_stale_helpers)
    from utils.helpers import today_zagreb, format_date, format_date_hr, pick_ledger, is_no_selection, MIN_PICK_CONFIDENCE

st.set_page_config(page_title="Daily Ticket | Tennis Agent", page_icon="🎾", layout="wide")
st.title("🎾 Daily Ticket")


def _status_badge(status: str) -> str:
    colors = {"won": "#22c55e", "lost": "#ef4444", "pending": "#f59e0b", "void": "#9ca3af", "analysis_only": "#6366f1"}
    labels = {"won": "✅ WON", "lost": "❌ LOST", "pending": "⏳ PENDING", "void": "⚪ VOID", "analysis_only": "📊 ANALYSIS ONLY"}
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
    if status == "analysis_only":
        st.metric("Matches analysed", len(matches))
    else:
        st.metric("Combined odds", f"{ticket.get('total_odds', 0):.2f}")
with col3:
    if status == "analysis_only":
        best_conf = max((m.get("confidence", 0) for m in matches), default=0)
        st.metric("Best confidence", f"{best_conf:.0f}%")
    else:
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

if status == "analysis_only":
    st.info(
        "📊 **Analysis only** — insufficient main-tour matches for a full accumulator today. "
        "Predictions below are tracked for model learning. Results and loss analysis run automatically."
    )

st.markdown("---")

# Summary
if ticket.get("ticket_summary"):
    expander_label = "📊 Analysis write-up" if status == "analysis_only" else "📝 Ticket write-up"
    with st.expander(expander_label, expanded=True):
        # (4) SLUZBENI POPIS PICKOVA — crta se IZ BAZE, ne iz teksta ispod
        # (29.08.2026 13:05). Povod: write-up je istog jutra za dva meca imenovao
        # protivnika naseg picka. Uzrok je popravljen u ticket_builderu, ali ovo
        # ostaje kao trajna referenca — korisnik nikad ne treba zakljucivati sto
        # je sluzbena odluka iz proze koju je napisao model.
        _ledger = pick_ledger(matches)
        if _ledger:
            _lines = []
            for _e in _ledger:
                _tag = "  ·  ⚠️ NO SELECTION" if _e["no_selection"] else ""
                _lines.append(
                    f"{_e['n']}. **{_e['pick']}** — {_e['player1']} vs {_e['player2']} "
                    f"· {_e['odds']:.2f} · {_e['confidence']:.0f}%{_tag}"
                )
            st.caption("Picks as recorded (source: database, not the text below)")
            st.markdown("\n".join(_lines))
            st.markdown("")
        st.markdown(ticket["ticket_summary"])

        # Reviewer notes — always show if available
        rev_decision = ticket.get("reviewer_decision", "")
        rev_changes = ticket.get("reviewer_changes", "")
        rev_warning = ticket.get("reviewer_warning", "")

        if rev_decision or rev_changes or rev_warning:
            st.markdown("---")
            st.markdown("**🤖 Analyst Reviewer:**")
            if rev_decision and rev_decision != "CONFIRM":
                st.info(f"**Decision: {rev_decision}** — {rev_changes}")
            elif rev_changes and rev_changes != "No changes made.":
                st.info(f"**Decision: {rev_decision}** — {rev_changes}")
            if rev_warning:
                st.warning(f"⚠️ {rev_warning}")

st.markdown("---")

# Parovi
for i, m in enumerate(matches):
    m_result = m.get("result", "pending")
    border_color = {"won": "#22c55e", "lost": "#ef4444", "pending": "#94a3b8"}.get(m_result, "#94a3b8")

    with st.container():
        st.markdown(f"""<div style="border-left:4px solid {border_color};padding-left:12px;margin-bottom:16px;">""", unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 2])

        _no_sel = is_no_selection(m)

        with c1:
            if _no_sel:
                # (5) Pouzdanost ispod 50% znaci da model tvrdi da vlastiti pick
                # GUBI (29.08.2026 13:05). Predikcija se i dalje biljezi i boduje —
                # samo se ne prikazuje kao nesto sto bismo igrali.
                st.markdown(f"**{i+1}. {m.get('pick', '')}** — model's lean, "
                            f"<span style=\"background:#a16207;color:white;padding:2px 8px;"
                            f"border-radius:6px;font-size:11px;\">NO SELECTION</span>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"**{i+1}. {m.get('pick', '')}** to win")
            st.caption(f"{m.get('player1','')} vs {m.get('player2','')}")
            st.caption(f"🏆 {m.get('tournament','')} · {m.get('surface','')} · {m.get('round','')}")
            if m.get("match_date"):
                st.caption(f"📅 {m.get('match_date','')}" + (f" {m.get('match_time','')}" if m.get("match_time") else ""))

        with c2:
            st.metric("Kvota", f"{m.get('odds', 0):.2f}")
            # VALUE se racuna iz fair_odds, dakle iz pouzdanosti — ispod praga je
            # ta oznaka besmislena (tvrdila bi vrijednost na picku koji sam model
            # ne vjeruje da pobjeđuje).
            if m.get("value_bet") and not _no_sel:
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
            if _no_sel:
                st.caption(f"🚫 Below the {MIN_PICK_CONFIDENCE:.0f}% floor — the model reads "
                           f"this as a coin-flip against its own pick. Tracked, not backed.")
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
if status != "analysis_only":
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Stake:** €{ticket.get('stake', 50):.0f}")
        st.markdown(f"**Combined odds:** {ticket.get('total_odds', 0):.2f}")
    with col2:
        st.markdown(f"**Potential return:** €{ticket.get('potential_win', 0):.2f}")
        if status == "won":
            st.markdown(f"**Actual return:** €{ticket.get('actual_win', 0):.2f}")
