# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - dio 2: 'dob' u NOVO (robusnost) i D8 regex (granice rijeci). Cita
.cache/rev_2026-11-01/skeptik_d2.pkl (napravio s_nasi.py).
"""
import math
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

D = r"C:\Users\jovin\Desktop\Tenis Claude\.cache\rev_2026-11-01"
d2 = pd.read_pickle(os.path.join(D, "skeptik_d2.pkl"))
nv = d2[d2.date >= "2026-09-27"].copy()
st = d2[d2.date < "2026-09-27"].copy()
for g in (nv, st):
    g["age_p"] = pd.to_numeric(g.age_p, errors="coerce")
    g["age_o"] = pd.to_numeric(g.age_o, errors="coerce")
    g["d_age"] = g.age_p - g.age_o
    g["resid"] = g.win - g.p
print("DOB NOVO: nan p/o", int(nv.age_p.isna().sum()), int(nv.age_o.isna().sum()), "| raspon age_p", nv.age_p.min(), nv.age_p.max(),
      "age_o", nv.age_o.min(), nv.age_o.max())
m = nv.dropna(subset=["d_age"])
print(f"  n={len(m)} Pearson r={np.corrcoef(m.d_age, m.resid)[0,1]:+.3f}  Spearman {np.corrcoef(m.d_age.rank(), m.resid.rank())[0,1]:+.3f}  d_age sd {m.d_age.std():.2f}")
lo, hi = m.d_age.quantile([.05, .95])
mm = m[(m.d_age >= lo) & (m.d_age <= hi)]
print(f"  bez 5/95% repova: n={len(mm)} r={np.corrcoef(mm.d_age, mm.resid)[0,1]:+.3f}")
for t, g in m.groupby("tour"):
    if len(g) >= 20:
        print(f"    {t[:34]:34s} n={len(g)} r={np.corrcoef(g.d_age, g.resid)[0,1]:+.2f}")
a, b = m[m.date >= "2026-10-26"], m[m.date < "2026-10-26"]
print(f"  TJEDAN r={np.corrcoef(a.d_age, a.resid)[0,1]:+.3f} (n={len(a)}) | NOVO bez tjedna r={np.corrcoef(b.d_age, b.resid)[0,1]:+.3f} (n={len(b)})")
s2 = st.dropna(subset=["d_age"])
print(f"  STARO n={len(s2)} r={np.corrcoef(s2.d_age, s2.resid)[0,1]:+.3f}")
# starost: kvantilne skupine (da vidimo oblik ovisnosti)
m = m.copy()
m["q"] = pd.qcut(m.d_age, 5, duplicates="drop")
print(m.groupby("q", observed=True).agg(n=("resid", "size"), resid=("resid", "mean"), dage=("d_age", "mean")).round(3).to_string())

pat_orig = re.compile(r"coin[- ]?flip|near coin|narrow|marginal|thin|solely|sole |nearly sole|only (?:argument|real|clear|edge|category|confirm)|single (?:category|confirm)|one category", re.I)
pat_wb = re.compile(r"coin[- ]?flip|near coin|\bnarrow|\bmarginal|\bthin\b|\bsolely\b|\bsole\b|nearly sole|only (?:argument|real|clear|edge|category|confirm)|single (?:category|confirm)|one category", re.I)


def banded_diff(g, flag):
    tot = w = 0.0
    for lo_, hi_ in ((1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)):
        x = g[flag & (g.odds >= lo_) & (g.odds < hi_)]
        y = g[~flag & (g.odds >= lo_) & (g.odds < hi_)]
        if len(x) and len(y):
            tot += ((x.win.mean() - x.p.mean()) - (y.win.mean() - y.p.mean())) * len(x)
            w += len(x)
    return 100 * tot / w if w else float("nan")


for lab, g in (("STARO", st), ("NOVO", nv)):
    txt = (g.analysis.fillna("") + " " + g.own.fillna("")).str.lower()
    a_ = txt.apply(lambda s: bool(pat_orig.search(s))).values
    b_ = txt.apply(lambda s: bool(pat_wb.search(s))).values
    cnt = Counter()
    for s in txt:
        for m_ in pat_orig.finditer(s):
            cnt[m_.group(0)] += 1
    print(f"\nD8 {lab}: n={len(g)} originalni regex pogadja {int(a_.sum())} ({100*a_.mean():.0f}%), s granicama rijeci {int(b_.sum())} ({100*b_.mean():.0f}%)")
    print("   najcesci pogodci (original):", cnt.most_common(8))
    for nm, flag in (("original", a_), ("granice rijeci", b_)):
        x = g[flag]
        if len(x):
            print(f"   {nm:15s} n={len(x):3d} edge {100*(x.win.mean()-x.p.mean()):+5.1f} | razlika u istom pojasu {banded_diff(g, flag):+5.1f}pp")
# D8 prva tri reda: grupa definirana CIJENOM, usporedba 'u istom pojasu' kvote
for lab, g in (("STARO", st), ("NOVO", nv)):
    c = (g.p < 0.60).values
    print(f"\nD8 {lab} cijena<0,60: n={c.sum()} | 'ostali' n={(~c).sum()} | preklapanje po pojasima kvote:")
    for lo_, hi_ in ((1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)):
        print(f"   pojas {lo_}-{hi_}: u skupini {int((c & (g.odds >= lo_).values & (g.odds < hi_).values).sum()):3d}, u 'ostalima' {int((~c & (g.odds >= lo_).values & (g.odds < hi_).values).sum()):3d}")
