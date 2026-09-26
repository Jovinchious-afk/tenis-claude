# -*- coding: utf-8 -*-
"""Historical Match-Up Context — CETVRTI backtest (26.09.2026), po korisnikovoj specifikaciji.

Za svaki mec i u trenutku t: pool = nasi razrijeseni mecevi s datumom <= t-3 dana (walk-forward,
bez ikakvog pogleda u buducnost; razmak 3 dana zbog 23% neuskladjenih datuma).
Slicnost:
  TVRDI UVJETI  : isti pojas trzisne vjerojatnosti (|p_i - p_j| <= 0,05) — "ne usporedjuj 70% s 55%"
  UDALJENOST    : standardizirane razlike, ponderirano, samo po dimenzijama koje oba meca imaju:
                  ELO jaz podloge 1,0 | prosj. ELO zadnjih 5 protivnika (pick i protivnik) 1,0 |
                  rang (log) 0,5 | dob jaz 0,5 | mecevi u 7 dana jaz 0,5 | ruka (matchup) 0,5 |
                  servis jaz 0,5 | povrat jaz 0,5 | forma 10 jaz 0,5 | visina jaz 0,25 | runda 0,5
HPS (historical pattern score) = prosjek (pobjeda - devig cijena) k najblizih; uz n i SE.
Mjeri se: predvidja li HPS ostatak NOVOG meca (r, i skupine negativno/neutralno/pozitivno).
Plus: ORACLE (smije gledati i buducnost) — ako ni on nema strukturu, nema je.
"""
import numpy as np, pandas as pd, base, math

j = pd.read_pickle("classified_idea3.pkl")
j = j[j.win.notna() & j.p_dev.notna()].sort_values("date").reset_index(drop=True)
j["hand_mu"] = (j.hand_p.fillna("") + j.hand_o.fillna("")).replace("", np.nan)
j["rgrp"] = j["round"].map({"R128": 0, "R64": 0, "R32": 0, "R16": 1, "QF": 1, "SF": 2, "F": 2}).astype(float)
FEAT = [("d_elo_s", 1.0), ("aoe5_p", 1.0), ("aoe5_o", 1.0), ("d_rank", 0.5), ("d_age", 0.5), ("d_m7", 0.5),
        ("d_serve", 0.5), ("d_ret", 0.5), ("d_f10", 0.5), ("d_h", 0.25), ("rgrp", 0.5)]
Z = {}
for f, w in FEAT:
    s = j[f].astype(float)
    Z[f] = ((s - s.mean()) / s.std()).values
P = j.p_dev.values; D = j.date.values; Y = (j.win - j.p_dev).values; HM = j.hand_mu.values


def dist(i, idx):
    num = np.zeros(len(idx)); den = np.zeros(len(idx))
    for f, w in FEAT:
        a = Z[f][i]
        if np.isnan(a):
            continue
        b = Z[f][idx]
        ok = ~np.isnan(b)
        num[ok] += w * (a - b[ok]) ** 2
        den[ok] += w
    hm = HM[i]
    if isinstance(hm, str):
        same = np.array([isinstance(x, str) and x == hm for x in HM[idx]])
        known = np.array([isinstance(x, str) for x in HM[idx]])
        num[known & ~same] += 0.5
        den[known] += 0.5
    d = np.where(den > 0, np.sqrt(num / np.maximum(den, 1e-9)), np.inf)
    d[den < 1.5] = np.inf        # premalo zajednickih dimenzija = nije usporedivo
    return d


def run(k, oracle=False, band=0.05):
    out = []
    for i in range(len(j)):
        if oracle:
            idx = np.array([x for x in range(len(j)) if x != i])
        else:
            idx = np.where(D <= D[i] - np.timedelta64(3, "D"))[0]
        if len(idx) == 0:
            out.append((np.nan, 0)); continue
        idx = idx[np.abs(P[idx] - P[i]) <= band]
        if len(idx) == 0:
            out.append((np.nan, 0)); continue
        d = dist(i, idx)
        ok = np.isfinite(d)
        idx, d = idx[ok], d[ok]
        if len(idx) < k:
            out.append((np.nan, len(idx))); continue
        nn = idx[np.argsort(d)[:k]]
        out.append((Y[nn].mean(), k))
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])


print(f"korpus: {len(j)} razrijesenih pickova s cijenom")
for k in [5, 10, 15, 30]:
    hps, n = run(k)
    m = ~np.isnan(hps)
    r, p, nn = base.corr(hps[m], Y[m])
    neg = m & (hps <= -0.10); pos = m & (hps >= 0.10); neu = m & ~neg & ~pos
    def e(mask):
        return f"n={mask.sum():3d} ostatak {100*Y[mask].mean():+5.1f}pp" if mask.sum() else "n=0"
    print(f"k={k:2d}: pokriveno {m.sum()}/{len(j)}  r(HPS, stvarni ostatak) = {r:+.3f} P={p:.3f} | "
          f"HPS<=-10pp: {e(neg)} | neutralno: {e(neu)} | HPS>=+10pp: {e(pos)}")
for k in [10, 30]:
    hps, n = run(k, oracle=True)
    m = ~np.isnan(hps)
    r, p, nn = base.corr(hps[m], Y[m])
    print(f"ORACLE k={k}: r = {r:+.3f} P={p:.3f} n={nn}")

# snaga: koliko slicnih slucajeva treba da se -10pp razlikuje od nule
for eff in [0.05, 0.10, 0.17]:
    need = (1.96 + 0.84) ** 2 * 0.23 / eff ** 2
    print(f"za pouzdano razlikovanje ucinka {100*eff:.0f}pp od nule (80% snage) treba ~{need:.0f} slicnih slucajeva")
se12 = math.sqrt(0.23 / 12)
print(f"primjer '12 slicnih: 41,7% naspram 58,9%': SE = {100*se12:.1f}pp -> 95% interval {-17.2-196*se12:.0f} do {-17.2+196*se12:+.0f}pp")
