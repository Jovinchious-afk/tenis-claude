# -*- coding: utf-8 -*-
# Scratch: varijanta "samo glavni ždrijeb" naspram "sve razine" NA ISTIM MEČEVIMA + pojasi cijene.
import os, sys, pickle, math
from bisect import bisect_left
import numpy as np
import pandas as pd
ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
from b_lab import build_history, F_TS, F_DATE, F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W, F_OK, F_TID, F_SRC
from agent.nose import point_model_prob
LAB = os.path.join(ROOT, ".cache", "lab")
FIELDS = (F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W); F_TML_IDX = 30

def run(main_only):
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl")); tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy(); td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact, {})
    if main_only:
        for pid, recs in hist.items():
            for x in recs:
                if x[F_SRC] != "main":
                    x[F_OK] = False
    pref, ts, pos = {}, {}, {}
    for pid, recs in hist.items():
        acc = np.zeros((len(recs) + 1, len(FIELDS)))
        for i, x in enumerate(recs):
            acc[i + 1] = acc[i] + (np.array([x[f] for f in FIELDS]) if x[F_OK] else 0)
        pref[pid] = acc; ts[pid] = [x[F_TS] for x in recs]
        for i, x in enumerate(recs): pos[(pid, x[F_TML_IDX])] = i
    tt = tml.loc[td["tml_idx"]].reset_index(drop=True)
    def sums(pid, lo, j, cd):
        recs = hist[pid]; s = pref[pid][j] - pref[pid][lo]
        for x in recs[max(lo, j - 8):j]:
            if x[F_DATE] >= cd and x[F_OK]: s = s - np.array([x[f] for f in FIELDS])
        return s
    def sr(s):
        sv, w1, w2, osv, o1, o2 = s
        if sv < 300 or osv < 300: return None
        return (w1 + w2) / sv, 1 - (o1 + o2) / osv, sv
    R = []
    for i in range(len(td)):
        m, r = td.iloc[i], tt.iloc[i]
        if pd.isna(m["p_fair"]): continue
        tidx = int(m["tml_idx"])
        d = {"key": (str(m["Date"])[:10], str(r["tourney_id"]), str(r["winner_id"]), str(r["loser_id"])), "pf": float(m["p_fair"]),
             "half": m["half"], "bo": int(m["Best of"]) if not pd.isna(m["Best of"]) else 3, "date": m["Date"]}
        ok_ = True
        for side, pid in (("w", r["winner_id"]), ("l", r["loser_id"])):
            j = pos.get((pid, tidx))
            if j is None: ok_ = False; break
            cd = hist[pid][j][F_DATE]
            c = sr(sums(pid, 0, j, cd)); lo = bisect_left(ts[pid], hist[pid][j][F_TS] - pd.Timedelta(days=365)); y = sr(sums(pid, lo, j, cd))
            if c is None or y is None: ok_ = False; break
            d[f"c_{side}"] = c; d[f"y_{side}"] = y
        if ok_: R.append(d)
    def vals(K, side, row):
        c, y = row[f"c_{side}"], row[f"y_{side}"]
        if K is None: return c[0], c[1]
        if K == 0: return y[0], y[1]
        w = y[2] / (y[2] + K); return w * y[0] + (1 - w) * c[0], w * y[1] + (1 - w) * c[1]
    out = {}
    for K in (None, 0, 1500, 4000):
        avg_r = np.mean([vals(K, s, row)[1] for row in R for s in ("w", "l")])
        p = np.empty(len(R))
        for i, row in enumerate(R):
            sw, rw = vals(K, "w", row); sl, rl = vals(K, "l", row)
            p[i] = min(max(point_model_prob(sw - (rl - avg_r), sl - (rw - avg_r), row["bo"]), 1e-4), 1 - 1e-4)
        out[K] = p
    df = pd.DataFrame({"key": [r["key"] for r in R], "pf": [r["pf"] for r in R], "half": [r["half"] for r in R], "date": [r["date"] for r in R]})
    for K, p in out.items():
        df[f"ll_{K}"] = -np.log(p)
    return df

dm = run(True)
da = run(False)
dm.to_pickle(os.path.join(SCR, "dm.pkl")); da.to_pickle(os.path.join(SCR, "da.pkl"))
print("main-only mečeva", len(dm), "| sve razine", len(da))
