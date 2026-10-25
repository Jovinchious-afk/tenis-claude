# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — A1/A2: dijagnoza TJEDNA (Lyon, Bruxelles, Almaty), NOVO i STARO + sreća ili
čitanje (25.10.2026 10:31; kopija revizije 18.10.2026 `r_novo.py`).

Pragovi: revizije/2026-10-25/PRAGOVI_REVIZIJA_2026-10-25.md (točke A1, A2; 10:20).
Samo čita .cache/rev_2026-10-25/base.pkl i points_calib.json (baždarenje iz LAB-a, 04.10.2026).
Analize s `elo_suspect` (Munar s tuđim ELO-om, revizija 04.10.) ne ulaze u brojke.
    python revizije/2026-10-25/skripte/r_tjedan.py
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
BANDS = [(1.0, 1.20), (1.20, 1.35), (1.35, 1.43), (1.43, 1.65), (1.65, 1.85), (1.85, 2.10), (2.10, 9)]


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
    return df


def classify(r):
    if pd.isna(r.pm_tp_share):
        return "bez statistike"
    if r.pm_tp_total < 60:
        return "predaja / prekid"
    if r.win == 0:
        return "poraz: tijesno/nesreća" if (r.pts_resid >= 0 or r.pm_tp_share >= 0.48) else "poraz: nadigran"
    return "pobjeda: sretna" if (r.pts_resid < 0 and r.pm_tp_share < 0.52) else "pobjeda: zaslužena"


def classify_c2(r):
    """C2 (pragovi 25.10.): udio poena našeg picka < 47% nadigran, 47-50% tijesno, > 50% više poena."""
    if pd.isna(r.pm_tp_share):
        return "bez statistike"
    if r.pm_tp_total < 60:
        return "predaja / prekid"
    s = r.pm_tp_share
    return "nadigran (<47%)" if s < 0.47 else ("tijesno (47-50%)" if s <= 0.50 else "više poena (>50%)")


def line(label, s):
    n, e, ci, roi = edge(s)
    if n == 0:
        return f"  {label:38s} n=  0"
    return (f"  {label:38s} n={n:3d}  {int(s.win.sum()):3d}W  pogodak {100*s.win.mean():5.1f}%  cijena "
            f"{100*s.p_dev.mean():5.1f}%  edge {e:+6.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%")


def block(name, g):
    print(f"\n######## {name}")
    print(line("UKUPNO", g))
    print("--- po turniru")
    for t, x in g.groupby("tournament"):
        print(line(str(t)[:38], x))
    print("--- po pojasu kvote")
    for lo, hi in BANDS:
        print(line(f"{lo:.2f}-{hi:.2f}", g[(g.odds >= lo) & (g.odds < hi)]))
    print("--- po rundi (ručne)")
    for rd in ["Q1", "Q2", "Q3", "R128", "R64", "R32", "R16", "QF", "SF", "F"]:
        x = g[g["round"] == rd]
        if len(x):
            print(line(rd, x))
    print("--- sesija")
    for s_, x in g.groupby(g.session.fillna("?")):
        print(line(str(s_), x))
    print("--- pouzdanost (konačna)")
    for lo, hi in [(0, 60), (60, 63), (63, 65), (65, 68), (68, 101)]:
        print(line(f"conf {lo}-{hi}", g[(g.conf >= lo) & (g.conf < hi)]))
    print("--- sirova pouzdanost (prije kazni)")
    for lo, hi in [(0, 60), (60, 63), (63, 65), (65, 68), (68, 101)]:
        print(line(f"raw {lo}-{hi}", g[(g.conf_raw >= lo) & (g.conf_raw < hi)]))
    print("--- tržišni favorit?")
    print(line("pick favorit (p>=0,5)", g[g.p_dev >= 0.5]))
    print(line("pick autsajder (p<0,5)", g[g.p_dev < 0.5]))
    print("--- na tiketu")
    print(line("noga tiketa", g[g.on_ticket]))
    print(line("nije na tiketu", g[~g.on_ticket]))


def main():
    df = pd.read_pickle(os.path.join(DUMP, "base.pkl"))
    print("isključeno elo_suspect:", int(df.elo_suspect.sum()), "| bez cijene:", int(df.p_dev.isna().sum()))
    df = df[df.p_dev.notna() & ~df.elo_suspect].copy()
    df = add_points(df)
    df["klasa"] = df.apply(classify, axis=1)
    df["c2"] = df.apply(classify_c2, axis=1)
    nv = df[df["sample"] == "NOVO"].copy()
    st = df[df["sample"] == "STARO"].copy()
    tj = nv[nv.tjedan].copy()
    prije = nv[~nv.tjedan].copy()

    block("TJEDAN (19.-25.10.2026: Lyon, Bruxelles, Almaty)", tj)
    block("NOVO (od 27.09.2026, uključuje TJEDAN)", nv)
    print("\n######## usporedba")
    print(line("NOVO bez TJEDNA (27.09.-18.10.)", prije))
    print(line("STARO", st))
    print(line("STARO samo hard", st[st.surface == "hard"]))
    print(line("TJEDAN dvorana (indoor)", tj[tj.indoor == True]))  # noqa: E712
    print(line("TJEDAN otvoreno", tj[tj.indoor == False]))  # noqa: E712

    print("\n######## A2. Sreća ili čitanje (poeni)")
    for lab_, g in (("TJEDAN", tj), ("NOVO bez TJEDNA", prije), ("NOVO", nv), ("STARO", st)):
        g = g[g.pm_tp_share.notna() & (g.pm_tp_total >= 60)]
        n = len(g)
        if n < 5:
            continue
        pr = g.pts_resid
        ci = 1.96 * pr.std() / math.sqrt(n)
        dw = 100 * (g.dwin - g.p_dev)
        ci_dw = 1.96 * dw.std() / math.sqrt(n)
        wl = 100 * (g.win - g.p_dev)
        ci_wl = 1.96 * wl.std() / math.sqrt(n)
        print(f"  {lab_:30s} n={n:3d}  ostatak poena {pr.mean():+5.2f}pp ±{ci:4.2f} | zasluženi edge {dw.mean():+5.1f}pp"
              f" [{dw.mean()-ci_dw:+5.1f}, {dw.mean()+ci_dw:+5.1f}] | W/L edge {wl.mean():+5.1f}pp ±{ci_wl:4.1f}")
    for lab_, g in (("TJEDAN", tj), ("NOVO", nv), ("STARO", st)):
        print(f"\n--- klasifikacija {lab_}")
        print(g["klasa"].value_counts().to_string())
    print("\n--- C2 TJEDAN gubitni parovi po udjelu poena")
    print(tj[tj.win == 0]["c2"].value_counts().to_string())
    print("--- C2 STARO gubitni (usporedba)")
    print(st[st.win == 0]["c2"].value_counts().to_string())
    print("\n--- TJEDAN statistika meča: pokrivenost", int(tj.pm_tp_share.notna().sum()), "od", len(tj))

    pd.set_option("display.width", 320)
    pd.set_option("display.max_rows", 300)
    out = tj[["date", "tournament", "round", "pick", "opp", "odds", "p_dev", "conf", "conf_raw", "penalties", "win",
              "pm_tp_share", "pts_resid", "klasa", "on_ticket", "nose_suit", "nose_diff", "int_prior"]].copy()
    out["date"] = out["date"].dt.strftime("%m-%d")
    out["tournament"] = out["tournament"].str.split("-").str[-1].str.strip().str[:8]
    out["pick"] = out["pick"].str.split().str[-1]
    out["opp"] = out["opp"].str.split().str[-1]
    print("\n######## TJEDAN meč po meč")
    print(out.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    df.to_pickle(os.path.join(DUMP, "all_points.pkl"))


if __name__ == "__main__":
    main()
