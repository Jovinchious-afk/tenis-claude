# -*- coding: utf-8 -*-
import os, math
import numpy as np
import pandas as pd
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
dm = pd.read_pickle(os.path.join(SCR, "dm.pkl")); da = pd.read_pickle(os.path.join(SCR, "da.pkl"))
m = dm.merge(da, on="key", suffixes=("_m", "_a"))
print("presjek:", len(m), "od main-only", len(dm), "i all", len(da))
m["yr"] = pd.to_datetime(m["date_m"]).dt.year
m["fav"] = np.maximum(m["pf_m"], 1 - m["pf_m"])
def line(mask, lab):
    n = mask.sum()
    d_all = (m["ll_None_a"] - m["ll_1500_a"])[mask]
    d_main = (m["ll_None_m"] - m["ll_1500_m"])[mask]
    return f"{lab:14s} n={n:5d} | SVE RAZINE (a)-(c) {d_all.mean():+.4f}±{d_all.std(ddof=1)/math.sqrt(n):.4f} | SAMO GLAVNI (a)-(c) {d_main.mean():+.4f}±{d_main.std(ddof=1)/math.sqrt(n):.4f}"
print("=== ISTI MEČEVI (presjek), razlika (a)-(c) log-gubitka; pozitivno = mješavina bolja ===")
for y in (2022, 2023, 2024, 2025, 2026):
    print(line(m["yr"].values == y, str(y)))
for h in ("P1", "P2"):
    print(line((m["half_m"] == h).values, h))
print(line(np.ones(len(m), bool), "ukupno"))
print("\n=== po pojasu cijene favorita (isti mečevi), polovice ===")
for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01), (0.5, 0.8)):
    mb = ((m["fav"] > lo) & (m["fav"] <= hi)).values
    for h in ("P1", "P2"):
        print(line(mb & (m["half_m"] == h).values, f"({lo},{hi}] {h}"))
print("\n=== apsolutni log-gubitak na presjeku, (a) / (b) / (c1500) ===")
for lab, sfx in (("sve razine", "a"), ("samo glavni", "m")):
    for h in ("P1", "P2"):
        mm = (m["half_m"] == h).values
        print(lab, h, " ".join(f"{m[f'll_{K}_{sfx}'][mm].mean():.4f}" for K in ("None", "0", "1500", "4000")))
