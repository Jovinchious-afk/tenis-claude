# -*- coding: utf-8 -*-
# Scratch: dose-odgovor - udio servisnih poena iz Challengera/kvalifikacija u 12-mj. prozoru vs korist mješavine (sve razine)
import os, sys, pickle, math
from bisect import bisect_left
import numpy as np
import pandas as pd
ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
from b_lab import build_history, F_TS, F_DATE, F_SV, F_OK, F_SRC
LAB = os.path.join(ROOT, ".cache", "lab"); F_TML_IDX = 30
td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl")); tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
td = td[td["tml_idx"].notna()].copy(); td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)
exact = dict(zip(td["tml_idx"], td["Date"]))
hist = build_history(tml, exact, {})
ts = {pid: [x[F_TS] for x in recs] for pid, recs in hist.items()}
pos = {}
for pid, recs in hist.items():
    for i, x in enumerate(recs): pos[(pid, x[F_TML_IDX])] = i
tt = tml.loc[td["tml_idx"]].reset_index(drop=True)
def low_share(pid, tidx):
    j = pos[(pid, tidx)]; recs = hist[pid]; cd = recs[j][F_DATE]
    lo = bisect_left(ts[pid], recs[j][F_TS] - pd.Timedelta(days=365))
    tot = low = 0.0
    for x in recs[lo:j]:
        if x[F_OK] and x[F_DATE] < cd:
            tot += x[F_SV]
            if x[F_SRC] != "main": low += x[F_SV]
    return (low / tot) if tot > 0 else np.nan
keys, shares = [], []
for i in range(len(td)):
    m, r = td.iloc[i], tt.iloc[i]
    if pd.isna(m["p_fair"]): continue
    tidx = int(m["tml_idx"])
    pw, pl = r["winner_id"], r["loser_id"]
    if (pw, tidx) not in pos or (pl, tidx) not in pos: continue
    keys.append((str(m["Date"])[:10], str(r["tourney_id"]), str(pw), str(pl)))
    shares.append((low_share(pw, tidx), low_share(pl, tidx)))
sh = pd.DataFrame({"key": keys, "sw": [s[0] for s in shares], "sl": [s[1] for s in shares]})
sh["smax"] = sh[["sw", "sl"]].max(axis=1)
da = pd.read_pickle(os.path.join(SCR, "da.pkl")).merge(sh, on="key")
da["yr"] = pd.to_datetime(da["date"]).dt.year
da["d_ac"] = da["ll_None"] - da["ll_1500"]
da["era"] = np.where(da["yr"] >= 2025, "2025-26", "2022-24")
bins = [-0.001, 0.10, 0.30, 0.50, 1.01]
da["bin"] = pd.cut(da["smax"], bins, labels=["<=10%", "10-30%", "30-50%", ">50%"])
print("(a)-(c) sve razine po udjelu servisnih poena iz Challengera/kvalifikacija u 12 mj. (veći od dvaju igrača), po eri")
g = da.groupby(["bin", "era"], observed=True)["d_ac"].agg(["mean", "size", lambda s: s.std(ddof=1) / math.sqrt(len(s))])
print(g.round(4).to_string())
print("\nudio mečeva po binu (sve):", (da["bin"].value_counts(normalize=True).sort_index() * 100).round(1).to_dict())

# dvosmjerno: izloženost nižim razinama x pojas cijene favorita (kontrola cijene), sve razine, (a)-(c)
da["fav"] = np.maximum(da["pf"], 1 - da["pf"])
da["expo"] = np.where(da["smax"] > 0.5, "visoka(>50%)", "niska(<=50%)")
da["fband"] = pd.cut(da["fav"], [0.5, 0.65, 0.8, 1.01], labels=["0.50-0.65", "0.65-0.80", ">0.80"])
print("\n(a)-(c) sve razine: izloženost x pojas cijene favorita x era; mean ± SE (n)")
g = da.groupby(["fband", "expo", "era"], observed=True)["d_ac"].agg(["mean", "size", lambda s: s.std(ddof=1) / math.sqrt(len(s))])
print(g.round(4).to_string())
# isto za (a)-(b)
da["d_ab"] = da["ll_None"] - da["ll_0"]
print("\n(a)-(b) ukupno po izloženosti i eri")
print(da.groupby(["expo", "era"])["d_ab"].agg(["mean", "size"]).round(4).to_string())
