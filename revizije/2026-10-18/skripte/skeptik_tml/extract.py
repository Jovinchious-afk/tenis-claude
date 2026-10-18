# -*- coding: utf-8 -*-
# Scratch (skeptik 18.10.2026): replicira c_tml_lab.py, ali sprema sirove zbrojeve po meču. Samo čita.
import os, sys, pickle, time
from bisect import bisect_left
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
from b_lab import build_history, F_TS, F_DATE, F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W, F_OK, F_TID, F_SRC  # noqa
LAB = os.path.join(ROOT, ".cache", "lab")
FIELDS = (F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W)
F_TML_IDX = 30

td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
td = td[td["tml_idx"].notna()].copy()
td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)
exact = dict(zip(td["tml_idx"], td["Date"]))
hist = build_history(tml, exact, {})
pref, ts, pos = {}, {}, {}
for pid, recs in hist.items():
    acc = np.zeros((len(recs) + 1, len(FIELDS)))
    for i, x in enumerate(recs):
        acc[i + 1] = acc[i] + (np.array([x[f] for f in FIELDS]) if x[F_OK] else 0)
    pref[pid] = acc
    ts[pid] = [x[F_TS] for x in recs]
    for i, x in enumerate(recs):
        pos[(pid, x[F_TML_IDX])] = i
t = tml.loc[td["tml_idx"]].reset_index(drop=True)

def sums(pid, lo, j, cd):
    recs = hist[pid]
    s = pref[pid][j] - pref[pid][lo]
    for x in recs[max(lo, j - 8):j]:
        if x[F_DATE] >= cd and x[F_OK]:
            s = s - np.array([x[f] for f in FIELDS])
    return s

rows = []
t0 = time.time()
for i in range(len(td)):
    m, r = td.iloc[i], t.iloc[i]
    pf = m["p_fair"]
    if pd.isna(pf):
        continue
    tidx = int(m["tml_idx"])
    out = {"pf": float(pf), "half": m["half"], "bo": int(m["Best of"]) if not pd.isna(m["Best of"]) else 3,
           "date": m["Date"], "tid": r["tourney_id"], "wid": r["winner_id"], "lid": r["loser_id"],
           "series": m["Series"], "surface": m["Surface"], "round": m["Round"]}
    ok = True
    for side, pid in (("w", r["winner_id"]), ("l", r["loser_id"])):
        j = pos.get((pid, tidx))
        if j is None:
            ok = False; break
        cd = hist[pid][j][F_DATE]
        car = sums(pid, 0, j, cd)
        lo = bisect_left(ts[pid], hist[pid][j][F_TS] - pd.Timedelta(days=365))
        y = sums(pid, lo, j, cd)
        # broj mečeva u karijeri/12 mj. (za dijagnostiku)
        out[f"car_{side}"] = car.copy()
        out[f"y_{side}"] = y.copy()
        out[f"ncar_{side}"] = j
        out[f"ny_{side}"] = j - lo
    if ok:
        rows.append(out)
print("redaka (prije filtra 300 poena):", len(rows), "vrijeme", round(time.time() - t0, 1))
with open(os.path.join(SCR, "rows.pkl"), "wb") as fo:
    pickle.dump(rows, fo)
