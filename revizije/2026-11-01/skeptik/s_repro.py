# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - NEOVISNA ponovna izvedba C1, C1r, N1, T1 i postojanosti TB iz sirovih
.cache/lab/td_joined.pkl i tml.pkl. Ne uvozi funkcije iz revizije za racunanje (samo popis gradova/granica
koji se ispisuje i provjerava). Samo cita.
    PYTHONIOENCODING=utf-8 python revizije/2026-11-01/skeptik/s_repro.py
"""
import math
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"

td = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "td_joined.pkl"))
tml = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "tml.pkl"))
td = td[td["tml_idx"].notna()].copy()
td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)
td = td[td["p_fair"].notna()].reset_index(drop=True)
print("LAB mecheva:", len(td))

# ---- zapisi igrac-mec (obje strane svakog TML retka)
date = tml["approx_date"].copy()
ex = pd.Series(dict(zip(td["tml_idx"], td["Date"])))
date.loc[ex.index] = ex.values
tml = tml.assign(date=date)


def num(c):
    return pd.to_numeric(tml[c], errors="coerce")


KEYS = ("svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")
W = {k: num("w_" + k) for k in KEYS}
L = {k: num("l_" + k) for k in KEYS}
allv = pd.concat(list(W.values()) + list(L.values()), axis=1)
ok = (allv.notna().all(axis=1) & (W["svpt"] > 0) & (L["svpt"] > 0) & (W["SvGms"] > 0) & (L["SvGms"] > 0)
      & (W["1stIn"] > 0) & (L["1stIn"] > 0))
print("zapisa s potpunom statistikom: %.1f%%" % (100 * ok.mean()))

TBS = re.compile(r"^(\d+)-(\d+)")


def tbs(score):
    w = l = 0
    for tok in str(score).split():
        m = TBS.match(tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a + b == 13 and abs(a - b) == 1:
                if a > b:
                    w += 1
                else:
                    l += 1
    return w, l


tb_w, tb_l = zip(*[tbs(s) if isinstance(s, str) else (0, 0) for s in tml["score"]])
tb_w, tb_l = np.array(tb_w), np.array(tb_l)


def side(pid, S, O, won, tw, tl, ioc):
    return pd.DataFrame({
        "pid": pid.values, "idx": tml.index.values, "date": tml["date"].values, "src": tml["src"].values,
        "won": won, "ok": ok.values,
        "sg": S["SvGms"].values, "bps": S["bpSaved"].values, "bpf": S["bpFaced"].values,
        "osv": O["svpt"].values, "ow1": O["1stWon"].values, "ow2": O["2ndWon"].values,
        "tbw": tw, "tbl": tl, "ioc": ioc.values, "year": pd.to_datetime(tml["date"]).dt.year.values})


rec = pd.concat([side(tml["winner_id"], W, L, 1, tb_w, tb_l, tml["winner_ioc"]),
                 side(tml["loser_id"], L, W, 0, tb_l, tb_w, tml["loser_ioc"])], ignore_index=True)
rec = rec[rec["pid"].notna()].copy()
for c in ("sg", "bps", "bpf", "osv", "ow1", "ow2"):
    rec[c] = np.where(rec["ok"], rec[c], 0.0)
rec = rec.sort_values(["pid", "date"]).reset_index(drop=True)
pidv = rec["pid"].values
bounds = {}
start = 0
for i in range(1, len(rec) + 1):
    if i == len(rec) or pidv[i] != pidv[start]:
        bounds[pidv[start]] = (start, i)
        start = i
dates = rec["date"].values.astype("datetime64[ns]")
cs = {c: np.concatenate([[0.0], np.cumsum(rec[c].values.astype(float))]) for c in ("sg", "bps", "bpf", "osv", "ow1", "ow2", "tbw", "tbl")}


def window(pid, cd, days=365):
    if pid not in bounds:
        return None
    a, b = bounds[pid]
    d = dates[a:b]
    lo = a + np.searchsorted(d, np.datetime64(cd - pd.Timedelta(days=days)), side="left")
    hi = a + np.searchsorted(d, np.datetime64(cd), side="left")      # STROGO prije datuma meca
    return lo, hi


def prof(pid, cd):
    w = window(pid, cd)
    if w is None:
        return dict(ret=np.nan, hold=np.nan, tbn=0, tb=np.nan)
    lo, hi = w

    def g(c):
        return cs[c][hi] - cs[c][lo]
    ret = 1 - (g("ow1") + g("ow2")) / g("osv") if g("osv") >= 300 else np.nan
    hold = 1 - (g("bpf") - g("bps")) / g("sg") if g("sg") >= 30 else np.nan
    tw, tl = g("tbw"), g("tbl")
    return dict(ret=ret, hold=hold, tbn=tw + tl, tb=(tw / (tw + tl)) if tw + tl > 0 else np.nan)


tm = tml.loc[td["tml_idx"]].reset_index(drop=True)
rows = []
for i in range(len(td)):
    cd = td["Date"].iat[i]
    rows.append((prof(tm["winner_id"].iat[i], cd), prof(tm["loser_id"].iat[i], cd)))
F = pd.DataFrame({
    "pf": td["p_fair"].values, "half": td["half"].values, "court": td["Court"].values, "surf": td["Surface"].values,
    "ret_w": [r[0]["ret"] for r in rows], "ret_l": [r[1]["ret"] for r in rows],
    "hold_w": [r[0]["hold"] for r in rows], "hold_l": [r[1]["hold"] for r in rows],
    "tb_w": [r[0]["tb"] for r in rows], "tb_l": [r[1]["tb"] for r in rows],
    "tbn_w": [r[0]["tbn"] for r in rows], "tbn_l": [r[1]["tbn"] for r in rows],
    "wid": tm["winner_id"].values, "lid": tm["loser_id"].values,
    "ioc_w": tm["winner_ioc"].values, "ioc_l": tm["loser_ioc"].values, "loc": td["Location"].values,
    "country": td["country"].values, "date": td["Date"].values})
F.to_pickle(os.path.join(ROOT, ".cache", "rev_2026-11-01", "skeptik_F.pkl"))
vals = pd.concat([F["ret_w"], F["ret_l"]]).dropna()
hv = pd.concat([F["hold_w"], F["hold_l"]]).dropna()
P = dict(ret90=vals.quantile(.9), ret75=vals.quantile(.75), hold10=hv.quantile(.1), hold25=hv.quantile(.25))
print("MOJI percentili:", {k: round(float(v), 4) for k, v in P.items()})
print("njihovi:        {'ret90': 0.4088, 'ret75': 0.3924, 'hold10': 0.7447, 'hold25': 0.7752}")


def edge(sel_w, sel_l, label):
    """sel_w / sel_l: strana pobjednika / gubitnika zadovoljava uvjet."""
    sel_w, sel_l = np.asarray(sel_w, bool), np.asarray(sel_l, bool)
    pf = F["pf"].values
    res = np.concatenate([(1 - pf)[sel_w], (-(1 - pf))[sel_l]])
    pA = np.concatenate([pf[sel_w], (1 - pf)[sel_l]])
    won = np.concatenate([np.ones(sel_w.sum()), np.zeros(sel_l.sum())])
    half = np.concatenate([F["half"].values[sel_w], F["half"].values[sel_l]])
    pid = np.concatenate([F["wid"].values[sel_w], F["lid"].values[sel_l]])
    n = len(res)
    if n < 3:
        print(f"{label}: n={n}")
        return None
    m = res.mean()
    se = res.std(ddof=1) / math.sqrt(n)
    dfc = pd.DataFrame({"pid": pid, "r": res - m})
    se_c = math.sqrt((dfc.groupby("pid")["r"].sum() ** 2).sum()) / n
    both = int((sel_w & sel_l).sum())
    h = {k: (res[half == k].mean() * 100 if (half == k).any() else float("nan"), int((half == k).sum())) for k in ("P1", "P2")}
    sw2, sl2 = sel_w & ~sel_l, sel_l & ~sel_w
    res2 = np.concatenate([(1 - pf)[sw2], (-(1 - pf))[sl2]])
    m2 = res2.mean() if len(res2) else float("nan")
    se2 = res2.std(ddof=1) / math.sqrt(len(res2)) if len(res2) > 2 else float("nan")
    print(f"{label:44s} n={n:5d} edge {100*m:+5.1f}pp [{100*(m-1.96*se):+5.1f},{100*(m+1.96*se):+5.1f}] "
          f"(klaster-igrac +-{196*se_c:4.1f}) P1 {h['P1'][0]:+5.1f}(n={h['P1'][1]}) P2 {h['P2'][0]:+5.1f}(n={h['P2'][1]}) "
          f"| OBA zadovoljavaju: {both} meceva -> bez njih n={len(res2)} edge {100*m2:+5.1f} [{100*(m2-1.96*se2):+5.1f},{100*(m2+1.96*se2):+5.1f}] "
          f"| pobjeduje {100*won.mean():.1f}% cijena {100*pA.mean():.1f}%")
    return dict(n=n, edge=100 * m)


pf = F["pf"].values
ih = ((F["court"] == "Indoor") & (F["surf"] == "Hard")).values
fav_w, fav_l = pf >= 0.5, pf <= 0.5
dog_w, dog_l = (pf >= .3) & (pf < .5), (pf > .5) & (pf <= .7)
print("\n--- C1 (ret>=P90 & hold<=P10, hard dvorana)")
edge(ih & (F["ret_w"] >= P["ret90"]).values & (F["hold_w"] <= P["hold10"]).values,
     ih & (F["ret_l"] >= P["ret90"]).values & (F["hold_l"] <= P["hold10"]).values, "C1 (moji percentili)")
edge(ih & (F["ret_w"] >= 0.4088).values & (F["hold_w"] <= 0.7447).values,
     ih & (F["ret_l"] >= 0.4088).values & (F["hold_l"] <= 0.7447).values, "C1 (njihovi literalni pragovi)")
cw = ih & (F["ret_w"] >= 0.3924).values & (F["hold_w"] <= 0.7752).values
cl = ih & (F["ret_l"] >= 0.3924).values & (F["hold_l"] <= 0.7752).values
edge(cw, cl, "C1r (njihovi pragovi)")
edge(cw & fav_w & (pf < 0.7), cl & fav_l & (pf > 0.3), "C1r + favorit 0,5-0,7 (NAKNADNI REZ)")
print("--- baze")
edge(ih & fav_w, ih & fav_l, "svi favoriti, hard dvorana")
edge(fav_w, fav_l, "SVI favoriti LAB")
edge(fav_w & (pf < .7), fav_l & (pf > .3), "svi favoriti 0,5-0,7 LAB")
edge(ih & fav_w & (pf < .7), ih & fav_l & (pf > .3), "favoriti 0,5-0,7, hard dvorana")
edge(dog_w, dog_l, "SVI autsajderi 0,30-0,50 LAB")

print("\n--- T1 (tb12 A >= B + 20pp, oba >= 6 TB u 365 d)")
for thr, mn in ((0.20, 6), (0.10, 6), (0.20, 3), (0.30, 6)):
    tw_ = ((F["tbn_w"] >= mn) & (F["tbn_l"] >= mn) & ((F["tb_w"] - F["tb_l"]) >= thr)).values
    tl_ = ((F["tbn_w"] >= mn) & (F["tbn_l"] >= mn) & ((F["tb_l"] - F["tb_w"]) >= thr)).values
    edge(tw_, tl_, f"T1 prag {int(thr*100)}pp, min {mn} TB")

# ---- N1: kod iz r_lab_nos.py samo za popis gradova/granica
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
import importlib.util
spec = importlib.util.spec_from_file_location("rl", os.path.join(ROOT, "revizije", "2026-11-01", "skripte", "r_lab_nos.py"))
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)
BORDERS, CAPITAL, CITY, IOC_FIX, km = rl.BORDERS, rl.CAPITAL, rl.CITY, rl.IOC_FIX, rl.km


def nb_flag(ioc, country, loc):
    ioc = IOC_FIX.get(str(ioc), str(ioc))
    if not isinstance(country, str) or ioc == country:
        return (False, False, False)
    by_b = ioc in BORDERS.get(country, set())
    by_d = bool(ioc in CAPITAL and loc in CITY and km(CAPITAL[ioc], CITY[loc][:2]) <= 600)
    return (by_b or by_d, by_b, by_d)


fw = [nb_flag(a, c, l) for a, c, l in zip(F["ioc_w"], F["country"], F["loc"])]
fl = [nb_flag(a, c, l) for a, c, l in zip(F["ioc_l"], F["country"], F["loc"])]
nbw, nbl = np.array([x[0] for x in fw]), np.array([x[0] for x in fl])
print("\n--- N1 (susjed)")
edge(nbw, nbl, "N1 (njihova definicija)")
edge(np.array([x[1] for x in fw]), np.array([x[1] for x in fl]), "N1 samo kopnena granica")
edge(np.array([x[2] and not x[1] for x in fw]), np.array([x[2] and not x[1] for x in fl]), "N1 samo udaljenost (bez granice)")
edge(nbw & dog_w, nbl & dog_l, "N2 susjed autsajder")
edge(nbw & fav_w, nbl & fav_l, "susjed favorit (opis)")
homew = np.array([isinstance(c, str) and IOC_FIX.get(str(a), str(a)) == c for a, c in zip(F["ioc_w"], F["country"])])
homel = np.array([isinstance(c, str) and IOC_FIX.get(str(a), str(a)) == c for a, c in zip(F["ioc_l"], F["country"])])
edge(homew, homel, "domaci (referenca: OBA domaca ulaze dvaput)")
edge(homew & ~homel, homel & ~homew, "domaci protiv ne-domaceg (K2 kako je 27.09.)")
edge(homew & dog_w, homel & dog_l, "domaci autsajder 0,30-0,50")
edge((homew | nbw) & dog_w, (homel | nbl) & dog_l, "domaci ILI susjed autsajder (H3 iz plana C)")
pairs = Counter()
for a, c, w_ in zip(list(F["ioc_w"]) + list(F["ioc_l"]), list(F["country"]) * 2, list(nbw) + list(nbl)):
    if w_:
        pairs[(c, IOC_FIX.get(str(a), str(a)))] += 1
print("najcesci parovi (domacin, igrac) koje kod broji 'susjedom':")
print(pairs.most_common(45))
unk = Counter(IOC_FIX.get(str(a), str(a)) for a in list(F["ioc_w"]) + list(F["ioc_l"]) if IOC_FIX.get(str(a), str(a)) not in CAPITAL)
print("IOC bez glavnog grada u popisu:", unk.most_common(15))


# ---- postojanost TB (neovisno)
print("\n--- postojanost TB (igrac-godina, >=10 TB obje godine)")


def pts_cols(pid, S, O):
    return pd.DataFrame({"pid": pid.values, "year": pd.to_datetime(tml["date"]).dt.year.values,
                         "won": (S["1stWon"] + S["2ndWon"] + O["svpt"] - O["1stWon"] - O["2ndWon"]).values,
                         "tot": (S["svpt"] + O["svpt"]).values, "ok": ok.values,
                         "sv_won": (S["1stWon"] + S["2ndWon"]).values, "sv_n": S["svpt"].values})


pp = pd.concat([pts_cols(tml["winner_id"], W, L), pts_cols(tml["loser_id"], L, W)], ignore_index=True)
pp = pp[pp["ok"] & pp["pid"].notna()]
pyr = pp.groupby(["pid", "year"])[["won", "tot", "sv_won", "sv_n"]].sum()
tbg = rec.groupby(["pid", "year"])[["tbw", "tbl"]].sum()
Y = tbg.join(pyr, how="left").reset_index()
Y = Y[Y["year"] >= 2010].copy()
Y["n"] = Y["tbw"] + Y["tbl"]
Y["tbp"] = Y["tbw"] / Y["n"].replace(0, np.nan)
Y["share"] = Y["won"] / Y["tot"]
Y["svp"] = Y["sv_won"] / Y["sv_n"]
A = Y.copy()
B = Y.copy()
B["year"] = B["year"] - 1
M = A.merge(B, on=["pid", "year"], suffixes=("1", "2"))


def resid(y, x):
    X = np.vstack([np.ones_like(x), x]).T
    return y - X @ np.linalg.lstsq(X, y, rcond=None)[0]


def persistence(lo_year, hi_year, minTB=10, minpts=500, label=""):
    m = M[(M["year"] >= lo_year) & (M["year"] + 1 <= hi_year) & (M["n1"] >= minTB) & (M["n2"] >= minTB)
          & (M["tot1"] >= minpts) & (M["tot2"] >= minpts)].dropna(subset=["tbp1", "tbp2", "share1", "share2", "svp1", "svp2"])
    a, b, s1, s2, v1, v2 = (m[c].values.astype(float) for c in ("tbp1", "tbp2", "share1", "share2", "svp1", "svp2"))
    if len(a) < 20:
        print(label, "n=", len(a))
        return
    r_tb = np.corrcoef(a, b)[0, 1]
    r_sh = np.corrcoef(s1, s2)[0, 1]
    r_res = np.corrcoef(resid(a, s1), resid(b, s2))[0, 1]
    r_res_sv = np.corrcoef(resid(a, v1), resid(b, v2))[0, 1]
    r_sp = np.corrcoef(pd.Series(a).rank().values, pd.Series(b).rank().values)[0, 1]
    # bootstrap po igracu
    rng = np.random.default_rng(1)
    pids = m["pid"].values
    up = np.unique(pids)
    idx_by = {p: np.where(pids == p)[0] for p in up}
    bs = []
    for _ in range(300):
        samp = rng.choice(up, len(up))
        ii = np.concatenate([idx_by[p] for p in samp])
        bs.append(np.corrcoef(a[ii], b[ii])[0, 1])
    lo_, hi_ = np.percentile(bs, [2.5, 97.5])
    print(f"{label:34s} parova={len(a):5d} igraca={len(up):4d} r(TB%)={r_tb:+.3f} [boot igrac {lo_:+.3f},{hi_:+.3f}] (Spearman {r_sp:+.3f}) "
          f"r(udio poena)={r_sh:+.3f} r(ostatak|udio poena)={r_res:+.3f} r(ostatak|poeni na servisu)={r_res_sv:+.3f}")


persistence(2010, 2026, label="2010-2026 (njihov postupak)")
persistence(2010, 2019, label="2010-2019 (samo glavni zdrijeb)")
persistence(2021, 2026, label="2021-2026 (sve razine)")
persistence(2010, 2026, minTB=15, label="min 15 TB")
persistence(2010, 2026, minTB=6, label="min 6 TB")
