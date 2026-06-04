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

st.set_page_config(page_title="Model Statistics | Tennis Agent", page_icon="🎾", layout="wide")
st.title("📊 Model Statistics")

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
    st.metric("Total tickets", len(resolved))
with col2:
    st.metric("Ticket win rate", f"{win_rate:.1f}%")
with col3:
    balance = total_returned - total_staked
    roi_hex = "#22c55e" if roi >= 0 else "#ef4444"
    sign = "+" if balance >= 0 else ""
    st.markdown(f"""
    <div style="padding:4px 0">
        <div style="font-size:0.85rem;color:#9ca3af;margin-bottom:4px;">ROI</div>
        <div style="font-size:2rem;font-weight:700;color:{roi_hex};line-height:1.1">{roi:.1f}%</div>
        <div style="font-size:0.85rem;color:{roi_hex};">{sign}€{balance:.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.metric("Staked", f"€{total_staked:.0f}")
with col5:
    st.metric("Returned", f"€{total_returned:.0f}")

st.markdown("---")

# ── ROI Chart ────────────────────────────────────────────────────────────────

if perf_data and len(perf_data) > 1:
    st.subheader("📈 Cumulative balance through the season")
    df_perf = pd.DataFrame(perf_data)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_perf["log_date"],
        y=df_perf["running_balance"],
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.1)",
        name="Cumulative balance (€)"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        yaxis_title="€", xaxis_title="Date",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Win rate by tournament ───────────────────────────────────────────────────

if resolved:
    st.subheader("🏆 Performance by tournament level")
    all_matches = []
    for t in resolved:
        for m in t.get("ticket_matches", []):
            if m.get("result") in ("won", "lost"):
                all_matches.append(m)

    if all_matches:
        from collections import defaultdict
        level_stats = defaultdict(lambda: {"won": 0, "total": 0})
        for m in all_matches:
            level = m.get("tournament_level", "Unknown")
            level_stats[level]["total"] += 1
            if m.get("result") == "won":
                level_stats[level]["won"] += 1

        level_rows = []
        for level, stats in level_stats.items():
            wr = stats["won"] / stats["total"] * 100 if stats["total"] else 0
            level_rows.append({"Level": level, "Picks": stats["total"], "Correct": stats["won"], "Win %": f"{wr:.0f}%"})

        st.dataframe(pd.DataFrame(level_rows).sort_values("Picks", ascending=False), hide_index=True, use_container_width=True)

    # Win rate by surface
    st.subheader("🎾 Performance by surface")
    surface_stats = defaultdict(lambda: {"won": 0, "total": 0})
    for m in all_matches:
        surface = m.get("surface", "Unknown")
        surface_stats[surface]["total"] += 1
        if m.get("result") == "won":
            surface_stats[surface]["won"] += 1

    surf_rows = []
    for surface, stats in surface_stats.items():
        wr = stats["won"] / stats["total"] * 100 if stats["total"] else 0
        surf_rows.append({"Surface": surface, "Picks": stats["total"], "Correct": stats["won"], "Win %": f"{wr:.0f}%"})

    if surf_rows:
        fig2 = px.bar(pd.DataFrame(surf_rows), x="Surface", y=["Correct", "Picks"],
                      barmode="overlay", color_discrete_map={"Correct": "#22c55e", "Picks": "#e2e8f0"})
        fig2.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Trenutne težine modela ────────────────────────────────────────────────────

st.subheader("⚙️ Current model weights")

labels = {
    "elo_ranking":            "ELO + Ranking trend",
    "surface_style":          "Surface + Style matchup",
    "serve_return":           "Serve + Return",
    "recent_form":            "Form (5-10 matches)",
    "fatigue_injuries":       "Fatigue + Injuries",
    "h2h_context":            "H2H + Context",
    "tournament_trajectory":  "Tournament Trajectory",
}
# Fixed color per factor — consistent across all 3 surface tabs
FACTOR_COLORS = {
    "ELO + Ranking trend":    "#2563eb",
    "Serve + Return":         "#16a34a",
    "Surface + Style matchup":"#ea580c",
    "Form (5-10 matches)":    "#dc2626",
    "Fatigue + Injuries":     "#7c3aed",
    "H2H + Context":          "#ca8a04",
    "Tournament Trajectory":  "#0891b2",
}

tab_clay, tab_grass, tab_hard = st.tabs(["🟤 Clay", "🟢 Grass", "🔵 Hard"])
for tab, surface in [(tab_clay, "clay"), (tab_grass, "grass"), (tab_hard, "hard")]:
    with tab:
        w = db.get_active_weights(surface)
        if w:
            rows = [{"Factor": labels.get(k, k), "Weight (%)": v}
                    for k, v in w.items() if isinstance(v, (int, float)) and k != "odds_movement"]
            df_w = pd.DataFrame(rows).sort_values("Weight (%)", ascending=False)
            colors = [FACTOR_COLORS.get(r["Factor"], "#94a3b8") for r in rows]
            df_w_sorted = df_w.reset_index(drop=True)
            colors_sorted = [FACTOR_COLORS.get(f, "#94a3b8") for f in df_w_sorted["Factor"]]
            c1, c2 = st.columns([1, 1])
            with c1:
                st.dataframe(df_w_sorted, hide_index=True, use_container_width=True)
            with c2:
                fig_pie = px.pie(df_w_sorted, values="Weight (%)", names="Factor",
                                 color="Factor",
                                 color_discrete_map=FACTOR_COLORS)
                fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=True)
                st.plotly_chart(fig_pie, use_container_width=True)

# ── Weight history ────────────────────────────────────────────────────────────

st.subheader("📜 Weight change history")
weight_history = db.get_weight_history()

if len(weight_history) > 1:
    for wh in weight_history:
        with st.expander(f"Version {wh.get('version')} — {wh.get('created_at','')[:10]} {'(active)' if wh.get('is_active') else ''}", expanded=False):
            if wh.get("update_reason"):
                st.write(f"**Reason:** {wh['update_reason']}")
            if wh.get("triggered_by"):
                st.write(f"**Triggered by:** {wh['triggered_by']}")
            st.json(wh.get("weights", {}))
else:
    st.info("Only one version of weights exists (initial version). Weights are automatically adjusted after enough error analyses.")

# ── Confidence calibration ────────────────────────────────────────────────────

if resolved and all_matches:
    st.markdown("---")
    st.subheader("🎯 Confidence calibration")
    st.caption("Compares stated confidence with actual win rate — a well-calibrated model follows the diagonal.")

    bins = [(55, 65), (65, 70), (70, 75), (75, 80), (80, 100)]
    cal_rows = []
    for low, high in bins:
        in_bin = [m for m in all_matches if low <= m.get("confidence", 0) < high]
        if not in_bin:
            continue
        actual_wr = sum(1 for m in in_bin if m.get("result") == "won") / len(in_bin) * 100
        cal_rows.append({
            "Confidence range": f"{low}-{high}%",
            "Picks": len(in_bin),
            "Stated conf.": f"{(low+high)/2:.0f}%",
            "Actual win%": f"{actual_wr:.0f}%",
            "Calibrated?": "✅" if abs((low+high)/2 - actual_wr) < 10 else "⚠️"
        })

    if cal_rows:
        st.dataframe(pd.DataFrame(cal_rows), hide_index=True, use_container_width=True)
