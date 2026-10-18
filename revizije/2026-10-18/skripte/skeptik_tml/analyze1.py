# -*- coding: utf-8 -*-
# Scratch (skeptik 18.10.2026): upareni SE, po godinama, skeniranje K, rekalibracija. Samo čita.
import os, sys, pickle, math
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
sys.path.insert(0, ROOT)
from agent.nose import point_model_prob

rows = pickle.load(open(os.path.join(SCR, "rows.pkl"), "rb"))

def sr(s):
    sv, w1, w2, osv, o1, o2 = s
    if sv < 300 or osv < 300:
        return None
    return (w1 + w2) / sv, 1 - (o1 + o2) / osv, sv

R = []
for x in rows:
    d = {k: x[k] for k in ("pf", "half", "bo", "date", "tid", "wid", "lid", "series", "surface", "round")}
    ok = True
    for side in ("w", "l"):
        c = sr(x[f"car_{side}"]); y = sr(x[f"y_{side}"])
        if c is None or y is None:
            ok = False; break
        d[f"c_{side}"] = c; d[f"y_{side}"] = y
        d[f"ncar_{side}"] = x[f"ncar_{side}"]; d[f"ny_{side}"] = x[f"ny_{side}"]
    if ok:
        R.append(d)
print("meceva:", len(R))
df = pd.DataFrame(R)
df["year"] = pd.to_datetime(df["date"]).dt.year

def mixvals(K, side, row):
    c, y = row[f"c_{side}"], row[f"y_{side}"]
    if K is None:   # car
        return c[0], c[1]
    if K == 0:
        return y[0], y[1]
    w = y[2] / (y[2] + K)
    return w * y[0] + (1 - w) * c[0], w * y[1] + (1 - w) * c[1]

def probs(K):
    # K: 'car' -> None; 0 -> 12m; else mix
    avg_r = np.mean([mixvals(K, s, row)[1] for row in R for s in ("w", "l")])
    p = np.empty(len(R))
    for i, row in enumerate(R):
        sw, rw = mixvals(K, "w", row)
        sl, rl = mixvals(K, "l", row)
        pw = point_model_prob(sw - (rl - avg_r), sl - (rw - avg_r), row["bo"])
        p[i] = min(max(pw, 1e-4), 1 - 1e-4)
    return p

Ks = [None, 0, 250, 500, 1000, 1500, 2500, 4000, 8000]
P = {}
for K in Ks:
    P[K] = probs(K)
    print("gotov K", K, flush=True)
pickle.dump((df, P), open(os.path.join(SCR, "probs.pkl"), "wb"))
