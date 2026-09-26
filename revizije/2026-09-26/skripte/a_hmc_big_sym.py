# -*- coding: utf-8 -*-
"""HMC princip na VELIKOM uzorku (26.09.2026): ~12.000 ATP/Masters/GS meceva s kvotama iz berbe.
Ako "slicni povijesni slucajevi" ne predvidjaju ostatak naspram cijene ni ovdje, gdje ima
stotine susjeda po mecu, nece ni na nasih 450.
Znacajke (sve walk-forward, iz povijesti PRIJE meca): vlastiti ELO (racunat sekvencijalno iz
berbe), forma zadnjih 10, mecevi u 7 dana, ruka (matchup), runda, razina, podloga.
Tvrdi uvjet: isti pojas cijene (+-0,03). Mec se promatra iz perspektive FAVORITA.
"""
import json, os, numpy as np, pandas as pd, base, pmbase

pm, names = pmbase.load_matches()
pm = pm.sort_values("date").reset_index(drop=True)
hands = json.load(open(r"C:\Users\jovin\Desktop\Tenis Claude\player_hands.json", encoding="utf-8"))

# --- sekvencijalni ELO + forma + opterecenje (na SVIM mecevima berbe, i bez kvota)
elo = {}; ngames = {}; hist = {}
feats = []
for r in pm.itertuples():
    a, b = r.p1, r.p2                    # a je pobjednik
    ea, eb = elo.get(a, 1500.0), elo.get(b, 1500.0)
    def form(p):
        h = hist.get(p, [])
        last = h[-10:]
        return np.mean([x[1] for x in last]) if len(last) >= 5 else np.nan
    def load7(p):
        h = hist.get(p, [])
        return sum(1 for x in h if (r.date - x[0]).days <= 7)
    feats.append(dict(ea=ea, eb=eb, fa=form(a), fb=form(b), la=load7(a), lb=load7(b),
                      na=ngames.get(a, 0), nb=ngames.get(b, 0)))
    pa = 1 / (1 + 10 ** ((eb - ea) / 400))
    ka = 250 / (ngames.get(a, 0) + 5) ** 0.4; kb = 250 / (ngames.get(b, 0) + 5) ** 0.4
    elo[a] = ea + ka * (1 - pa); elo[b] = eb - kb * (1 - pa)
    ngames[a] = ngames.get(a, 0) + 1; ngames[b] = ngames.get(b, 0) + 1
    hist.setdefault(a, []).append((r.date, 1.0)); hist.setdefault(b, []).append((r.date, 0.0))
F = pd.DataFrame(feats)
pm = pd.concat([pm, F], axis=1)
import os as _os
HARV = set(f[:-5] for f in _os.listdir("pm"))
p = pm[pm.o1.notna() & pm.o2.notna() & (pm.o1 > 1) & (pm.o2 > 1) & pm.level.isin([2, 3, 4, 7]) & (pm.na >= 10) & (pm.nb >= 10) & pm.p1.isin(HARV) & pm.p2.isin(HARV)].copy()
print("SIMETRICNO UZORKOVANJE: oba igraca u berbi")
p["pw"] = (1 / p.o1) / (1 / p.o1 + 1 / p.o2)
# perspektiva favorita
fav_is_a = p.pw >= 0.5
p["pf"] = np.where(fav_is_a, p.pw, 1 - p.pw)
p["y"] = np.where(fav_is_a, 1.0, 0.0)
p["elo_gap"] = np.where(fav_is_a, p.ea - p.eb, p.eb - p.ea)
p["form_gap"] = np.where(fav_is_a, p.fa - p.fb, p.fb - p.fa)
p["load_gap"] = np.where(fav_is_a, p.la - p.lb, p.lb - p.la)
hf = np.where(fav_is_a, p.p1.map(hands), p.p2.map(hands)); hd = np.where(fav_is_a, p.p2.map(hands), p.p1.map(hands))
p["hand_mu"] = pd.Series(hf, index=p.index).fillna("?") + pd.Series(hd, index=p.index).fillna("?")
p["rgrp"] = p.round_id.map(lambda x: 0 if x is None or x < 7 else (1 if x in (7, 8, 9) else 2))
p["res"] = p.y - p.pf
p = p.dropna(subset=["elo_gap", "form_gap"]).reset_index(drop=True)
print(f"meceva s kvotom i znacajkama: {len(p)}; favorit pobijedio {100*p.y.mean():.1f}% naspram {100*p.pf.mean():.1f}% cijene")
# samo informativno: nosi li nas vlastiti ELO jaz nesto povrh cijene?
p["logit"] = np.log(p.pf / (1 - p.pf))
for v in ["elo_gap", "form_gap", "load_gap"]:
    b_, se, z, pp, n = base.offset_logit(p[v], p.y, p.logit)
    print(f"  glavni ucinak {v}: offset z={z:+.2f} P={pp:.3f} n={n}")

Zs = {c: ((p[c] - p[c].mean()) / p[c].std()).values for c in ["elo_gap", "form_gap", "load_gap"]}
PF = p.pf.values; DT = p.date.values; RES = p.res.values; HM = p.hand_mu.values; RG = p.rgrp.values
LV = p.level.values; CT = p.court.values
test = np.where(p.date >= "2025-07-01")[0]
for k in [15, 50, 150]:
    hps = np.full(len(p), np.nan)
    for i in test:
        idx = np.where(DT <= DT[i] - np.timedelta64(3, "D"))[0]
        idx = idx[np.abs(PF[idx] - PF[i]) <= 0.03]
        if len(idx) < k:
            continue
        d = (Zs["elo_gap"][idx] - Zs["elo_gap"][i]) ** 2 + 0.5 * (Zs["form_gap"][idx] - Zs["form_gap"][i]) ** 2 \
            + 0.5 * (Zs["load_gap"][idx] - Zs["load_gap"][i]) ** 2 + 0.5 * (HM[idx] != HM[i]) + 0.5 * (RG[idx] != RG[i]) \
            + 0.5 * (LV[idx] != LV[i]) + 0.5 * (CT[idx] != CT[i])
        nn = idx[np.argsort(d)[:k]]
        hps[i] = RES[nn].mean()
    m = ~np.isnan(hps)
    r, pv, n = base.corr(hps[m], RES[m])
    q = pd.qcut(hps[m], 5, labels=False)
    tops = [f"{100*RES[m][q==g].mean():+.1f}" for g in range(5)]
    print(f"k={k:3d}: n={n}  r(HPS, stvarni ostatak) = {r:+.3f} P={pv:.3f} | kvintili HPS -> stvarni ostatak (pp): {tops}")

# KONTROLA: je li "slicnost" ista osim pristranosti po POJASU CIJENE?
# baza = prosjecni ostatak SVIH ranijih meceva u istom pojasu cijene (bez ijedne znacajke)
base_hps = np.full(len(p), np.nan)
for i in test:
    idx = np.where(DT <= DT[i] - np.timedelta64(3, "D"))[0]
    idx = idx[np.abs(PF[idx] - PF[i]) <= 0.03]
    if len(idx) >= 50:
        base_hps[i] = RES[idx].mean()
m = ~np.isnan(base_hps)
r, pv, n = base.corr(base_hps[m], RES[m])
print(f"SAMO POJAS CIJENE (bez slicnosti): r = {r:+.3f} P={pv:.3f} n={n}")
# prirast slicnosti povrh pojasa cijene: parcijalno
for k in [50, 150]:
    hps = np.full(len(p), np.nan)
    for i in test:
        idx = np.where(DT <= DT[i] - np.timedelta64(3, "D"))[0]
        idx = idx[np.abs(PF[idx] - PF[i]) <= 0.03]
        if len(idx) < k:
            continue
        d = (Zs["elo_gap"][idx] - Zs["elo_gap"][i]) ** 2 + 0.5 * (Zs["form_gap"][idx] - Zs["form_gap"][i]) ** 2 \
            + 0.5 * (Zs["load_gap"][idx] - Zs["load_gap"][i]) ** 2 + 0.5 * (HM[idx] != HM[i]) + 0.5 * (RG[idx] != RG[i]) \
            + 0.5 * (LV[idx] != LV[i]) + 0.5 * (CT[idx] != CT[i])
        nn = idx[np.argsort(d)[:k]]
        hps[i] = RES[nn].mean()
    mm = ~np.isnan(hps) & ~np.isnan(base_hps)
    X = np.column_stack([np.ones(mm.sum()), base_hps[mm], hps[mm]])
    coef, *_ = np.linalg.lstsq(X, RES[mm], rcond=None)
    resid_y = RES[mm] - np.column_stack([np.ones(mm.sum()), base_hps[mm]]) @ np.linalg.lstsq(np.column_stack([np.ones(mm.sum()), base_hps[mm]]), RES[mm], rcond=None)[0]
    resid_h = hps[mm] - np.column_stack([np.ones(mm.sum()), base_hps[mm]]) @ np.linalg.lstsq(np.column_stack([np.ones(mm.sum()), base_hps[mm]]), hps[mm], rcond=None)[0]
    r2, pv2, n2 = base.corr(resid_h, resid_y)
    print(f"k={k}: prirast SLICNOSTI povrh pojasa cijene: parcijalni r = {r2:+.3f} P={pv2:.3f} n={n2}")
