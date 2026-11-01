# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - C5 (H2H protiv favorita): neovisna izvedba + provjera curenja (isti mec pod drugim
datumom), doza-odgovor i osjetljivost definicije. Samo cita .cache/lab/*.pkl.
    PYTHONIOENCODING=utf-8 python revizije/2026-11-01/skeptik/s_h2h.py
"""
import math
import os
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
td = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "td_joined.pkl"))
tml = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "tml.pkl"))
td = td[td["tml_idx"].notna()].copy()
td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)
td = td[td["p_fair"].notna()].reset_index(drop=True)
date = tml["approx_date"].copy()
ex = pd.Series(dict(zip(td["tml_idx"], td["Date"])))
date.loc[ex.index] = ex.values
tml = tml.assign(date=date)


def surf(s):
    s = str(s)
    return "Hard" if s in ("Hard", "Carpet") else (s if s in ("Clay", "Grass") else "Hard")


h2h = defaultdict(list)
for idx, w, l, sc, sf, tid, dt, nm, src in zip(tml.index, tml["winner_id"], tml["loser_id"], tml["score"], tml["surface"],
                                              tml["tourney_id"], tml["date"], tml["tourney_name"], tml["src"]):
    if pd.isna(w) or pd.isna(l) or not isinstance(sc, str) or "W/O" in sc.upper() or not sc.strip():
        continue
    h2h[frozenset((w, l))].append((dt, w, surf(sf), tid, idx, sc, nm, src))
for k in h2h:
    h2h[k].sort(key=lambda x: x[0])

tm = tml.loc[td["tml_idx"]].reset_index(drop=True)
pf = td["p_fair"].values
n = len(td)
leak = dict(same_score=0, same_name_year=0, within7=0, total_prior=0, same_idx=0)
recs = []   # po meču: (strana favorita je 'w' ili 'l'), H2H iz perspektive FAVORITA
for i in range(n):
    cd, tid, idx = td["Date"].iat[i], tm["tourney_id"].iat[i], td["tml_idx"].iat[i]
    w, l = tm["winner_id"].iat[i], tm["loser_id"].iat[i]
    cur_score = tm["score"].iat[i]
    cur_name = tm["tourney_name"].iat[i]
    lst = h2h.get(frozenset((w, l)), [])
    prior = []
    for (dt, hw, hs, htid, hidx, hsc, hnm, hsrc) in lst:
        if hidx == idx:
            leak["same_idx"] += 1
            continue
        if dt < cd and htid != tid:
            prior.append((dt, hw, hs, hnm, hsc))
            leak["total_prior"] += 1
            if hsc == cur_score and abs((dt - cd).days) <= 45:
                leak["same_score"] += 1
            if hnm == cur_name and dt.year == cd.year:
                leak["same_name_year"] += 1
            if abs((dt - cd).days) <= 7:
                leak["within7"] += 1
    recs.append(prior)
print("provjera curenja u H2H (prethodni susreti koje bi kod koristio):", leak)

surf_td = td["Surface"].map(lambda s: s if s in ("Clay", "Grass") else "Hard").values


def fav_side(i):
    return "w" if pf[i] >= 0.5 else "l"


def c5_rows(variant="orig"):
    out = []
    for i in range(n):
        prior = recs[i]
        if len(prior) < 2:
            continue
        cd = td["Date"].iat[i]
        w, l = tm["winner_id"].iat[i], tm["loser_id"].iat[i]
        fs = fav_side(i)
        fid = w if fs == "w" else l
        last = prior[-1]
        last3 = prior[-3:]
        b_won_last = last[1] != fid
        b_won_2of3 = sum(1 for x in last3 if x[1] != fid) >= 2
        if variant == "orig":
            cond = b_won_last and (cd - last[0]).days <= 548 and last[2] == surf_td[i] and b_won_2of3
        elif variant == "last_only":
            cond = b_won_last
        elif variant == "last_only_18m":
            cond = b_won_last and (cd - last[0]).days <= 548
        elif variant == "2of3_only":
            cond = b_won_2of3
        elif variant == "no_surface":
            cond = b_won_last and (cd - last[0]).days <= 548 and b_won_2of3
        elif variant == "fav_dominates":     # placebo / dvosmjerno: favorit dobio zadnji i >=2 od 3
            cond = (not b_won_last) and (cd - last[0]).days <= 548 and last[2] == surf_td[i] and sum(1 for x in last3 if x[1] == fid) >= 2
        else:
            raise ValueError
        if cond:
            p = pf[i] if fs == "w" else 1 - pf[i]
            won = 1 if fs == "w" else 0
            out.append((won, p, td["half"].iat[i], i, fid))
    return out


def summ(rows, label):
    if not rows:
        print(label, "n=0"); return
    r = np.array([x[0] - x[1] for x in rows])
    m = r.mean(); se = r.std(ddof=1) / math.sqrt(len(r))
    h = {k: (np.mean([x[0] - x[1] for x in rows if x[2] == k]) * 100, sum(1 for x in rows if x[2] == k)) for k in ("P1", "P2")}
    ids = pd.DataFrame({"pid": [x[4] for x in rows], "r": r - m})
    se_c = math.sqrt((ids.groupby("pid")["r"].sum() ** 2).sum()) / len(r)
    print(f"{label:44s} n={len(r):4d} edge {100*m:+5.1f}pp [{100*(m-1.96*se):+5.1f},{100*(m+1.96*se):+5.1f}] klaster-igrac +-{196*se_c:4.1f}  "
          f"P1 {h['P1'][0]:+5.1f}(n={h['P1'][1]}) P2 {h['P2'][0]:+5.1f}(n={h['P2'][1]})")


for v in ("orig", "last_only", "last_only_18m", "2of3_only", "no_surface", "fav_dominates"):
    summ(c5_rows(v), f"C5 varijanta {v}")
# sve favorite s >=2 prethodna susreta (baza)
base = []
for i in range(n):
    if len(recs[i]) >= 2:
        fs = fav_side(i)
        base.append((1 if fs == "w" else 0, pf[i] if fs == "w" else 1 - pf[i], td["half"].iat[i], i, tm["winner_id"].iat[i] if fs == "w" else tm["loser_id"].iat[i]))
summ(base, "baza: favoriti s >=2 prethodna H2H susreta")

# doza-odgovor: omjer pobjeda favorita u zadnja 3 susreta
for k_ in (0, 1, 2, 3):
    rows = []
    for i in range(n):
        prior = recs[i]
        if len(prior) < 3:
            continue
        fs = fav_side(i)
        fid = tm["winner_id"].iat[i] if fs == "w" else tm["loser_id"].iat[i]
        fwins = sum(1 for x in prior[-3:] if x[1] == fid)
        if fwins == k_:
            rows.append((1 if fs == "w" else 0, pf[i] if fs == "w" else 1 - pf[i], td["half"].iat[i], i, fid))
    summ(rows, f"doza: favorit dobio {k_} od zadnja 3 (>=3 susreta)")
# po cijeni favorita
rows = c5_rows("orig")
for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 1.01)):
    summ([x for x in rows if lo <= x[1] < hi], f"C5 orig, cijena favorita {lo:.2f}-{hi:.2f}")


print("\n--- C5 orig, favorit >= 0,70: popis mečeva")
rows = [x for x in c5_rows("orig") if x[1] >= 0.70]
for won, p, half, i, fid in sorted(rows, key=lambda x: td["Date"].iat[x[3]]):
    w, l = tm["winner_name"].iat[i], tm["loser_name"].iat[i]
    fav = w if pf[i] >= 0.5 else l
    prior = recs[i]
    seq = "".join("F" if x[1] == fid else "o" for x in prior[-5:])
    print(td["Date"].iat[i].date(), td["Tournament"].iat[i][:22].ljust(22), td["Round"].iat[i].ljust(9), f"fav={fav[:22]:22s} p={p:.2f} won={won}",
          f"H2H (F=favorit dobio, o=protivnik) zadnjih do 5: {seq}  zadnji {(td['Date'].iat[i] - prior[-1][0]).days} d")
print("n=", len(rows), "pobjeda:", sum(x[0] for x in rows), "prosj. cijena %.3f" % np.mean([x[1] for x in rows]))
# koliko je igraca u tih 35
print("razlicitih favorita:", len({x[4] for x in rows}))
