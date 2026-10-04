# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — A: dijagnoza NOVOG uzorka + A2: sreća ili čitanje (04.10.2026 18:06).

Pragovi: revizije/2026-10-04/PRAGOVI_REVIZIJA_2026-10-04.md (točke A i A2).
Samo čita .cache/rev_2026-10-04/base.pkl i points_calib.json.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, edge  # noqa: E402

CAL = json.load(open(os.path.join(DUMP, "points_calib.json"), encoding="utf-8"))


def add_points(df):
    """Očekivani udio poena za cijenu, ostatak poena i zasluženi P(pobjeda) (baždareno u LAB-u)."""
    bo = np.where(df["level"].astype(str).str.contains("Grand Slam", case=False), 5, 3)
    a3, b3 = CAL["bo3"]["share_given_logitp"]
    a5, b5 = CAL["bo5"]["share_given_logitp"]
    lp = np.log(df["p_dev"] / (1 - df["p_dev"]))
    df["exp_share"] = np.where(bo == 5, a5 + b5 * lp, a3 + b3 * lp)
    df["pts_resid"] = 100 * (df["pm_tp_share"] - df["exp_share"])
    w3, w5 = CAL["bo3"]["win_given_share"], CAL["bo5"]["win_given_share"]
    z = np.where(bo == 5, w5[0] + w5[1] * (df["pm_tp_share"] - 0.5) * 100,
                 w3[0] + w3[1] * (df["pm_tp_share"] - 0.5) * 100)
    df["dwin"] = 1 / (1 + np.exp(-z))
    # pretvorba ostatka poena u "pp vjerojatnosti pobjede": dp/dudio = p(1-p)/b
    b = np.where(bo == 5, b5, b3)
    df["pts_resid_wpp"] = df["pts_resid"] / 100 * df["p_dev"] * (1 - df["p_dev"]) / b * 100
    return df


def classify(r):
    if pd.isna(r.pm_tp_share):
        return "bez statistike"
    if r.pm_tp_total < 60:
        return "predaja / prekid"
    if r.win == 0:
        return "poraz: tijesno/nesreća" if (r.pts_resid >= 0 or r.pm_tp_share >= 0.48) else "poraz: nadigran"
    return "pobjeda: sretna" if (r.pts_resid < 0 and r.pm_tp_share < 0.52) else "pobjeda: zaslužena"


def line(label, s):
    n, e, ci, roi = edge(s)
    if n == 0:
        return f"  {label:34s} n=  0"
    return f"  {label:34s} n={n:3d}  {int(s.win.sum()):2d}W  pogodak {100*s.win.mean():5.1f}%  cijena {100*s.p_dev.mean():5.1f}%  edge {e:+6.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%"


def main():
    df = pd.read_pickle(os.path.join(DUMP, "base.pkl"))
    df = df[df.p_dev.notna()].copy()
    df = add_points(df)
    df["klasa"] = df.apply(classify, axis=1)
    nv = df[df["sample"] == "NOVO"].copy()
    st = df[df["sample"] == "STARO"].copy()

    print("=== A. NOVO naspram STARO")
    print(line("NOVO (28.09.-04.10.)", nv))
    print(line("STARO", st))
    print("\n--- po turniru")
    for t, g in nv.groupby("tournament"):
        print(line(str(t)[:34], g))
    print("\n--- po razini")
    for t, g in nv.groupby("level"):
        print(line(str(t), g))
    print("\n--- po pojasu kvote")
    bands = [(1.0, 1.20), (1.20, 1.35), (1.35, 1.43), (1.43, 1.65), (1.65, 1.85), (1.85, 9)]
    for lo, hi in bands:
        print(line(f"{lo:.2f}-{hi:.2f}", nv[(nv.odds >= lo) & (nv.odds < hi)]))
    print("\n--- po rundi (ručne)")
    for rd in ["R32", "R16", "QF", "SF", "F"]:
        print(line(rd, nv[nv["round"] == rd]))
    print("\n--- sesija")
    for s_, g in nv.groupby("session"):
        print(line(str(s_), g))
    print("\n--- pouzdanost (konačna)")
    for lo, hi in [(0, 60), (60, 63), (63, 65), (65, 68), (68, 101)]:
        print(line(f"conf {lo}-{hi}", nv[(nv.conf >= lo) & (nv.conf < hi)]))
    print("\n--- tržišni favorit?")
    print(line("pick favorit (p>=0,5)", nv[nv.p_dev >= 0.5]))
    print(line("pick autsajder (p<0,5)", nv[nv.p_dev < 0.5]))
    print("\n--- na tiketu")
    print(line("noga tiketa", nv[nv.on_ticket]))
    print(line("nije na tiketu", nv[~nv.on_ticket]))

    print("\n=== A2. Sreća ili čitanje (poeni)")
    for lab_, g in (("NOVO", nv), ("STARO", st), ("SVE", df)):
        g = g[g.pm_tp_share.notna() & (g.pm_tp_total >= 60)]
        n = len(g)
        pr = g.pts_resid
        ci = 1.96 * pr.std() / math.sqrt(n)
        dw = 100 * (g.dwin - g.p_dev)
        ci_dw = 1.96 * dw.std() / math.sqrt(n)
        wl = 100 * (g.win - g.p_dev)
        ci_wl = 1.96 * wl.std() / math.sqrt(n)
        print(f"  {lab_:5s} n={n:3d}  ostatak poena {pr.mean():+5.2f}pp ±{ci:4.2f}  (≈ {g.pts_resid_wpp.mean():+5.1f}pp pobjede)"
              f" | zasluženi edge {dw.mean():+5.1f}pp ±{ci_dw:4.1f} | W/L edge {wl.mean():+5.1f}pp ±{ci_wl:4.1f}")
    print("\n--- klasifikacija NOVO")
    print(nv["klasa"].value_counts().to_string())
    print("\n--- klasifikacija STARO (za usporedbu)")
    print(st["klasa"].value_counts().to_string())

    cols = ["date", "tournament", "round", "session", "pick", "opp", "odds", "p_dev", "conf", "conf_raw",
            "penalties", "win", "pm_tp_share", "exp_share", "pts_resid", "klasa", "on_ticket", "leg_score",
            "pm_aces", "pmo_aces", "pm_dfs", "pmo_dfs", "pm_bp_saved", "pm_bp_faced", "pmo_bp_saved", "pmo_bp_faced",
            "pm_serve_won", "pmo_serve_won", "market_src", "cons_gap", "market_check"]
    out = nv[cols].copy()
    out["tournament"] = out["tournament"].str.slice(0, 14)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print("\n=== NOVO meč po meč")
    print(out[["date", "tournament", "round", "session", "pick", "opp", "odds", "conf", "win", "pm_tp_share",
               "pts_resid", "klasa", "on_ticket"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    nv.to_pickle(os.path.join(DUMP, "novo_points.pkl"))
    df.to_pickle(os.path.join(DUMP, "all_points.pkl"))


if __name__ == "__main__":
    main()
