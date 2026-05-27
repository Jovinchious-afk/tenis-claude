"""
Stranica 4: Model Statistike
ROI kroz sezonu, win rate, history težina modela, learning log.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from database import supabase_client as db

st.set_page_config(page_title="Model Statistike | Tennis Agent", page_icon="🎾", layout="wide")
st.title("📊 Model Statistike")

# ── Performance data ──────────────────────────────────────────────────────────

perf_data = db.get_performance_history(days=90)
tickets = db.get_tickets(limit=200)

resolved = [t for t in tickets if t.get("status") in ("won", "lost")]
won_tickets = [t for t in resolved if t.get("status") == "won"]
lost_tickets = [t for t in resolved if t.get("status") == "lost"]

total_staked = len(resolved) * 50.0
total_returned = sum(t.get("actual_win", 0) or 0 for t in won_tickets)
roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0
win_rate = (len(won_tickets) / len(resolved) * 100) if resolved else 0

# KPI row
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Ukupno tiketa", len(resolved))
with col2:
    st.metric("Win rate tiketa", f"{win_rate:.1f}%")
with col3:
    roi_color = "normal" if roi >= 0 else "inverse"
    st.metric("ROI", f"{roi:.1f}%", delta=f"€{total_returned - total_staked:.2f}")
with col4:
    st.metric("Uloženo", f"€{total_staked:.0f}")
with col5:
    st.metric("Vraćeno", f"€{total_returned:.0f}")

st.markdown("---")

# ── ROI Chart ────────────────────────────────────────────────────────────────

if perf_data and len(perf_data) > 1:
    st.subheader("📈 Kumulativni balans kroz sezonu")
    df_perf = pd.DataFrame(perf_data)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_perf["log_date"],
        y=df_perf["running_balance"],
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.1)",
        name="Kumulativni balans (€)"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        yaxis_title="€", xaxis_title="Datum",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Win rate po turniru ───────────────────────────────────────────────────────

if resolved:
    st.subheader("🏆 Performanse po tipu turnira")
    all_matches = []
    for t in resolved:
        for m in t.get("ticket_matches", []):
            if m.get("result") in ("won", "lost"):
                all_matches.append(m)

    if all_matches:
        from collections import defaultdict
        level_stats = defaultdict(lambda: {"won": 0, "total": 0})
        for m in all_matches:
            level = m.get("tournament_level", "Nepoznato")
            level_stats[level]["total"] += 1
            if m.get("result") == "won":
                level_stats[level]["won"] += 1

        level_rows = []
        for level, stats in level_stats.items():
            wr = stats["won"] / stats["total"] * 100 if stats["total"] else 0
            level_rows.append({"Razina": level, "Parovi": stats["total"], "Pogođeni": stats["won"], "Win %": f"{wr:.0f}%"})

        st.dataframe(pd.DataFrame(level_rows).sort_values("Parovi", ascending=False), hide_index=True, use_container_width=True)

    # Win rate po podlozi
    st.subheader("🎾 Performanse po podlozi")
    surface_stats = defaultdict(lambda: {"won": 0, "total": 0})
    for m in all_matches:
        surface = m.get("surface", "Nepoznato")
        surface_stats[surface]["total"] += 1
        if m.get("result") == "won":
            surface_stats[surface]["won"] += 1

    surf_rows = []
    for surface, stats in surface_stats.items():
        wr = stats["won"] / stats["total"] * 100 if stats["total"] else 0
        surf_rows.append({"Podloga": surface, "Parovi": stats["total"], "Pogođeni": stats["won"], "Win %": f"{wr:.0f}%"})

    if surf_rows:
        fig2 = px.bar(pd.DataFrame(surf_rows), x="Podloga", y=["Pogođeni", "Parovi"],
                      barmode="overlay", color_discrete_map={"Pogođeni": "#22c55e", "Parovi": "#e2e8f0"})
        fig2.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Trenutne težine modela ────────────────────────────────────────────────────

st.subheader("⚙️ Trenutne težine modela")
current_weights = db.get_active_weights()

if current_weights:
    labels = {
        "elo_ranking": "ELO + Ranking trend",
        "surface_style": "Podloga + Stil igre",
        "serve_return": "Servis + Return",
        "recent_form": "Forma (5-10 mečeva)",
        "fatigue_injuries": "Umor + Ozljede",
        "h2h_context": "H2H + Kontekst",
        "odds_movement": "Kretanje kvota",
    }
    weight_rows = [{"Faktor": labels.get(k, k), "Težina (%)": v} for k, v in current_weights.items()]
    df_weights = pd.DataFrame(weight_rows).sort_values("Težina (%)", ascending=False)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.dataframe(df_weights, hide_index=True, use_container_width=True)
    with col2:
        fig3 = px.pie(df_weights, values="Težina (%)", names="Faktor",
                      color_discrete_sequence=px.colors.qualitative.Set3)
        fig3.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=True)
        st.plotly_chart(fig3, use_container_width=True)

# ── History težina ────────────────────────────────────────────────────────────

st.subheader("📜 Historija promjena težina")
weight_history = db.get_weight_history()

if len(weight_history) > 1:
    for wh in weight_history:
        with st.expander(f"Verzija {wh.get('version')} — {wh.get('created_at','')[:10]} {'(aktivna)' if wh.get('is_active') else ''}", expanded=False):
            if wh.get("update_reason"):
                st.write(f"**Razlog:** {wh['update_reason']}")
            if wh.get("triggered_by"):
                st.write(f"**Pokrenuto od:** {wh['triggered_by']}")
            st.json(wh.get("weights", {}))
else:
    st.info("Samo jedna verzija težina postoji (početna verzija). Težine se automatski prilagođavaju nakon dovoljno analiziranih grešaka.")

# ── Confidence kalibracija ────────────────────────────────────────────────────

if resolved and all_matches:
    st.markdown("---")
    st.subheader("🎯 Kalibracija confidence-a")
    st.caption("Uspoređuje navedeni confidence s stvarnim win rateom — dobro kalibriran model ima dijagonalu.")

    bins = [(55, 65), (65, 70), (70, 75), (75, 80), (80, 100)]
    cal_rows = []
    for low, high in bins:
        in_bin = [m for m in all_matches if low <= m.get("confidence", 0) < high]
        if not in_bin:
            continue
        actual_wr = sum(1 for m in in_bin if m.get("result") == "won") / len(in_bin) * 100
        cal_rows.append({
            "Confidence range": f"{low}-{high}%",
            "Parovi": len(in_bin),
            "Navedeni conf.": f"{(low+high)/2:.0f}%",
            "Stvarni win%": f"{actual_wr:.0f}%",
            "Kalibriran?": "✅" if abs((low+high)/2 - actual_wr) < 10 else "⚠️"
        })

    if cal_rows:
        st.dataframe(pd.DataFrame(cal_rows), hide_index=True, use_container_width=True)
