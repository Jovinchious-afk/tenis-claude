# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 — provjera parsiranja tie-breakova iz TML rezultata naspram tennis-data
stupaca W1..W5/L1..L5 (neovisan izvor). Samo čita .cache/lab/*.pkl.
    PYTHONIOENCODING=utf-8 python -I revizije/2026-11-01/skeptik/s_tb_parse.py
"""
import os
import re
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
td = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "td_joined.pkl"))
tml = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "tml.pkl"))
td = td[td["tml_idx"].notna()].copy()
td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)

# neovisni parser: TML rezultat, pobjednik-prvi; set je TB set ako je zbroj gemova 13 i razlika 1
def tb_from_score(sc):
    w = l = 0
    for tok in str(sc or "").split():
        m = re.match(r"^(\d+)-(\d+)", tok)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a + b == 13 and abs(a - b) == 1:
            if a > b: w += 1
            else: l += 1
    return w, l

def tb_from_td(row):
    w = l = 0
    for i in range(1, 6):
        a, b = row.get(f"W{i}"), row.get(f"L{i}")
        try:
            a, b = int(a), int(b)
        except (TypeError, ValueError):
            continue
        if a + b == 13 and abs(a - b) == 1:
            if a > b: w += 1
            else: l += 1
    return w, l

sc = tml.loc[td["tml_idx"], "score"].values
tmlw = np.array([tb_from_score(s)[0] for s in sc]); tmll = np.array([tb_from_score(s)[1] for s in sc])
tdw = np.array([tb_from_td(r)[0] for r in td.to_dict("records")]); tdl = np.array([tb_from_td(r)[1] for r in td.to_dict("records")])
print("mečeva:", len(td))
print("TML  TB pobjednik/gubitnik:", tmlw.sum(), tmll.sum(), " udio TB koje dobiva pobjednik meča: %.3f" % (tmlw.sum() / (tmlw.sum() + tmll.sum())))
print("TD   TB pobjednik/gubitnik:", tdw.sum(), tdl.sum(), " udio: %.3f" % (tdw.sum() / (tdw.sum() + tdl.sum())))
same = ((tmlw == tdw) & (tmll == tdl))
print("podudaranje TML vs TD po meču: %.4f (%d nepodudarnih)" % (same.mean(), (~same).sum()))
bad = td.loc[~same, ["Date", "Tournament", "Winner", "Loser", "W1", "L1", "W2", "L2", "W3", "L3"]].copy()
bad["tml_score"] = np.array(sc, dtype=object)[~same]
bad["tml_tb"] = list(zip(tmlw[~same], tmll[~same]))
bad["td_tb"] = list(zip(tdw[~same], tdl[~same]))
print(bad.head(25).to_string())

# kontrola: je li pravi TML parser (iz r_lab_nos.py: samo {6,7}) jednak ovome na LAB mečevima
TB_SET = re.compile(r"^(\d+)-(\d+)")
def tb_counts(score):
    w = l_ = 0
    for tok in str(score or "").split():
        m = TB_SET.match(tok)
        if not m: continue
        a, b = int(m.group(1)), int(m.group(2))
        if {a, b} == {6, 7}:
            if a > b: w += 1
            else: l_ += 1
    return w, l_
o = np.array([tb_counts(s) for s in sc])
print("r_lab_nos parser == moj parser:", bool(((o[:, 0] == tmlw) & (o[:, 1] == tmll)).all()))

# raspodjela oblika tokena u cijelom TML-u (svi mečevi), da vidimo egzotične zapise
from collections import Counter
c = Counter()
for s in tml["score"].astype(str):
    for tok in s.split():
        c[re.sub(r"\d", "9", tok)] += 1
print(c.most_common(25))
