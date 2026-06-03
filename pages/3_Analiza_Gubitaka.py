"""
Stranica 3: Analiza Gubitaka
Claude-ova analiza izgubljenih parova — zašto smo pogriješili.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
from collections import defaultdict
import streamlit as st
from database import supabase_client as db

st.set_page_config(page_title="Loss Analysis | Tennis Agent", page_icon="🎾", layout="wide")
st.title("🔍 Loss Analysis")
st.markdown("Detailed analysis of incorrect predictions — what went wrong and what to change.")

tickets = db.get_tickets(limit=100)
# Include analysis-only tickets — their matches are tracked and can lose
relevant_tickets = [t for t in tickets if t.get("status") in ("lost", "analysis_only")]

if not relevant_tickets:
    st.success("No lost picks in archive. Excellent!")
    st.stop()

# Sve izgubljene parove s analizom
all_lost_matches = []
for t in relevant_tickets:
    for m in t.get("ticket_matches", []):
        if m.get("result") == "lost":
            m["ticket_date"] = t.get("ticket_date", "")
            m["from_analysis_only"] = t.get("status") == "analysis_only"
            all_lost_matches.append(m)

analyzed = [m for m in all_lost_matches if m.get("loss_analysis")]
not_analyzed = [m for m in all_lost_matches if not m.get("loss_analysis")]


def _group_by_match(matches: list) -> list:
    """Grupira iste mečeve (isti igrači, isti match_date) koji su bili na više tiketa."""
    groups = defaultdict(list)
    for m in matches:
        key = (
            m.get("player1", "").lower().strip(),
            m.get("player2", "").lower().strip(),
            m.get("match_date") or m.get("ticket_date", ""),
        )
        groups[key].append(m)

    merged = []
    for group in groups.values():
        group.sort(key=lambda x: x.get("ticket_date", ""))
        if len(group) == 1:
            merged.append(group[0])
        else:
            base = dict(group[-1])
            all_dates = sorted(set(m.get("ticket_date", "") for m in group))
            base["ticket_dates_merged"] = all_dates
            base["all_analyses"] = [
                (m.get("ticket_date", ""), m.get("loss_analysis", ""))
                for m in group if m.get("loss_analysis")
            ]
            merged.append(base)

    merged.sort(key=lambda x: (x.get("ticket_dates_merged") or [x.get("ticket_date", "")])[-1], reverse=True)
    return merged


grouped_analyzed = _group_by_match(analyzed)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total lost picks", len(all_lost_matches))
with col2:
    st.metric("Unique matches lost", len(grouped_analyzed))
with col3:
    st.metric("Appeared on 2+ tickets", sum(1 for m in grouped_analyzed if m.get("ticket_dates_merged")))

if not_analyzed:
    st.info(f"{len(not_analyzed)} pick(s) not yet analysed (analysis runs automatically in the evening job).")

st.markdown("---")

# Filteri
col_f1, col_f2 = st.columns(2)
with col_f1:
    surface_filter = st.selectbox("Filter by surface:", ["All", "Clay", "Hard", "Grass", "Indoor Hard"])
with col_f2:
    tournament_filter = st.text_input("Filter by tournament:", "")

# Filter po datumu (po najnovijem ticket_date u grupi)
all_dates = sorted(set(
    (m.get("ticket_dates_merged") or [m.get("ticket_date", "")])[-1]
    for m in grouped_analyzed
))
if all_dates:
    min_date = datetime.date.fromisoformat(all_dates[0])
    max_date = datetime.date.fromisoformat(all_dates[-1])
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_from = st.date_input("From date:", value=min_date, min_value=min_date, max_value=max_date)
    with col_d2:
        date_to = st.date_input("To date:", value=max_date, min_value=min_date, max_value=max_date)
else:
    date_from = date_to = None

filtered = grouped_analyzed
if surface_filter != "All":
    filtered = [m for m in filtered if m.get("surface", "") == surface_filter]
if tournament_filter:
    filtered = [m for m in filtered if tournament_filter.lower() in m.get("tournament", "").lower()]
if date_from and date_to:
    filtered = [m for m in filtered
                if date_from.isoformat() <= (m.get("ticket_dates_merged") or [m.get("ticket_date", "")])[-1] <= date_to.isoformat()]

st.markdown(f"**Showing {len(filtered)} analysed losses:**")
st.markdown("---")

if not filtered:
    st.info("Nema rezultata za odabrane filtre.")
    st.stop()

for m in filtered:
    merged_dates = m.get("ticket_dates_merged")
    date_label = " & ".join(merged_dates) if merged_dates else m.get("ticket_date", "")
    repeat_badge = " 🔁" if merged_dates else ""
    analysis_badge = " 📊" if m.get("from_analysis_only") else ""

    with st.expander(
        f"❌ {m.get('pick','')} — {m.get('player1','')} vs {m.get('player2','')} ({date_label}){repeat_badge}{analysis_badge}",
        expanded=False
    ):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Tournament:** {m.get('tournament','')}")
            st.write(f"**Surface:** {m.get('surface','')}")
            st.write(f"**Round:** {m.get('round','')}")
        with col2:
            st.write(f"**Our pick:** {m.get('pick','')}")
            st.write(f"**Confidence:** {m.get('confidence',0):.0f}%")
            st.write(f"**Odds:** {m.get('odds',0):.2f}")
        with col3:
            st.write(f"**Winner:** {m.get('actual_winner','N/A')}")
            st.write(f"**Score:** {m.get('actual_score','N/A')}")
            st.write(f"**Risk level:** {m.get('risk_level','N/A')}")

        if m.get("risk_notes"):
            st.warning(f"⚠️ Stated risks: {m['risk_notes']}")

        if m.get("key_factors"):
            st.write(f"**Factors that drove the pick:** {', '.join(m.get('key_factors',[]))}")

        # Prikaz analiza — jedna ili više (ako je isti meč bio na više tiketa)
        all_analyses = m.get("all_analyses")
        if all_analyses and len(all_analyses) > 1:
            st.markdown(f"**🤖 Claude error analysis** — appeared on **{len(all_analyses)} tickets**:")
            for ticket_date, analysis_text in all_analyses:
                st.markdown(f"*Ticket {ticket_date}:*")
                st.info(analysis_text or "Analysis not available.")
        else:
            st.markdown("**🤖 Claude error analysis:**")
            st.info(m.get("loss_analysis", "Analysis not available."))


# Agregirana statistika grešaka
st.markdown("---")
st.subheader("📊 Error patterns")

if len(grouped_analyzed) >= 3:
    from collections import Counter
    surfaces = Counter(m.get("surface","") for m in grouped_analyzed)
    st.write("**Losses by surface:**")
    for surface, count in surfaces.most_common():
        st.write(f"  • {surface}: {count}")

    col1, col2, col3 = st.columns(3)
    with col1:
        avg_conf = sum(m.get("confidence",0) for m in grouped_analyzed) / len(grouped_analyzed)
        st.metric("Avg confidence on losses", f"{avg_conf:.0f}%")
    with col2:
        high_conf_lost = sum(1 for m in grouped_analyzed if m.get("confidence",0) >= 70)
        st.metric("Lost with conf. ≥70%", high_conf_lost)
    with col3:
        repeat_losses = sum(1 for m in grouped_analyzed if m.get("ticket_dates_merged"))
        st.metric("Same match, 2+ tickets", repeat_losses)
else:
    st.info("Not enough data for aggregate statistics (minimum 3 analyses required).")
