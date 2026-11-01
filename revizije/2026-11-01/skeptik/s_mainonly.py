# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - koliko se profil 365 d (povrat, hold) mijenja kad se Challengeri i kvalifikacije
izbace (kao sto bi bilo za 2010-2019 gdje u kesu ima samo glavni zdrijeb). Mjeri na LAB-u 2022-2026.
Samo cita .cache/lab/*.pkl."""
import os
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
KEYS = ("svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")
W = {k: pd.to_numeric(tml["w_" + k], errors="coerce") for k in KEYS}
L = {k: pd.to_numeric(tml["l_" + k], errors="coerce") for k in KEYS}
ok = (pd.concat(list(W.values()) + list(L.values()), axis=1).notna().all(axis=1) & (W["svpt"] > 0) & (L["svpt"] > 0)
      & (W["SvGms"] > 0) & (L["SvGms"] > 0) & (W["1stIn"] > 0) & (L["1stIn"] > 0))


def side(pid, S, O):
    return pd.DataFrame({"pid": pid.values, "date": tml["date"].values, "src": tml["src"].values, "ok": ok.values,
                         "sg": S["SvGms"].values, "bps": S["bpSaved"].values, "bpf": S["bpFaced"].values,
                         "osv": O["svpt"].values, "ow1": O["1stWon"].values, "ow2": O["2ndWon"].values})


rec = pd.concat([side(tml["winner_id"], W, L), side(tml["loser_id"], L, W)], ignore_index=True)
rec = rec[rec["pid"].notna()].copy()
for c in ("sg", "bps", "bpf", "osv", "ow1", "ow2"):
    rec[c] = np.where(rec["ok"], rec[c], 0.0)


def build(r):
    r = r.sort_values(["pid", "date"]).reset_index(drop=True)
    pidv = r["pid"].values
    bounds, s0 = {}, 0
    for i in range(1, len(r) + 1):
        if i == len(r) or pidv[i] != pidv[s0]:
            bounds[pidv[s0]] = (s0, i)
            s0 = i
    dates = r["date"].values.astype("datetime64[ns]")
    cs = {c: np.concatenate([[0.0], np.cumsum(r[c].values.astype(float))]) for c in ("sg", "bps", "bpf", "osv", "ow1", "ow2")}
    return bounds, dates, cs


def prof(B, pid, cd):
    bounds, dates, cs = B
    if pid not in bounds:
        return (np.nan, np.nan)
    a, b = bounds[pid]
    d = dates[a:b]
    lo = a + np.searchsorted(d, np.datetime64(cd - pd.Timedelta(days=365)), side="left")
    hi = a + np.searchsorted(d, np.datetime64(cd), side="left")
    g = lambda c: cs[c][hi] - cs[c][lo]
    ret = 1 - (g("ow1") + g("ow2")) / g("osv") if g("osv") >= 300 else np.nan
    hold = 1 - (g("bpf") - g("bps")) / g("sg") if g("sg") >= 30 else np.nan
    return ret, hold


Ball = build(rec)
Bmain = build(rec[rec["src"] == "main"])
tm = tml.loc[td["tml_idx"]].reset_index(drop=True)
out = []
for i in range(len(td)):
    cd = td["Date"].iat[i]
    for pid in (tm["winner_id"].iat[i], tm["loser_id"].iat[i]):
        out.append((i, prof(Ball, pid, cd), prof(Bmain, pid, cd)))
ra = np.array([o[1][0] for o in out]); ha = np.array([o[1][1] for o in out])
rm = np.array([o[2][0] for o in out]); hm = np.array([o[2][1] for o in out])
print("pokrivenost povrata: sve razine %.1f%% | samo glavni zdrijeb %.1f%%" % (100 * np.isfinite(ra).mean(), 100 * np.isfinite(rm).mean()))
print("pokrivenost holda:   sve razine %.1f%% | samo glavni zdrijeb %.1f%%" % (100 * np.isfinite(ha).mean(), 100 * np.isfinite(hm).mean()))
for nm, a, m in (("povrat", ra, rm), ("hold", ha, hm)):
    both = np.isfinite(a) & np.isfinite(m)
    print(f"{nm}: korelacija sve/glavni {np.corrcoef(a[both], m[both])[0,1]:.3f} | srednja razlika (glavni - sve) {np.mean(m[both]-a[both]):+.4f}")
    for q in (.10, .25, .75, .90):
        print(f"   percentil {int(q*100)}: sve razine {np.nanquantile(a, q):.4f} | samo glavni {np.nanquantile(m, q):.4f}")
# kako bi se apsolutni pragovi iz C1r ponasali na profilu 'samo glavni zdrijeb'
both = np.isfinite(ra) & np.isfinite(ha)
sel_all = (ra >= 0.3924) & (ha <= 0.7752)
sel_main = (rm >= 0.3924) & (hm <= 0.7752)
print("udio strana koje zadovoljavaju C1r pragove: sve razine %.2f%% | samo glavni zdrijeb (isti apsolutni pragovi) %.2f%%" % (100 * np.nanmean(sel_all), 100 * np.nanmean(sel_main)))
print("  od onih u 'sve razine' koliko ih je i u 'samo glavni':", int((sel_all & sel_main).sum()), "od", int(sel_all.sum()))


# ---- H1 (favorit 0,5-0,7, hard dvorana, povrat visok + hold nizak) pod razlicitim definicijama profila
import math
pf = td["p_fair"].values
ih = ((td["Court"] == "Indoor") & (td["Surface"] == "Hard")).values
half = td["half"].values
n_ = len(td)
rw, rl = ra[0::2], ra[1::2]
hw_, hl_ = ha[0::2], ha[1::2]
rmw, rml = rm[0::2], rm[1::2]
hmw, hml = hm[0::2], hm[1::2]


def h1(rw_, rl_, hw2, hl2, rthr, hthr, label):
    selw = ih & (rw_ >= rthr) & (hw2 <= hthr) & (pf >= .5) & (pf < .7)
    sell = ih & (rl_ >= rthr) & (hl2 <= hthr) & ((1 - pf) >= .5) & ((1 - pf) < .7)
    res = np.concatenate([(1 - pf)[selw], (-(1 - pf))[sell]])
    hh = np.concatenate([half[selw], half[sell]])
    if len(res) < 5:
        print(label, "n=", len(res)); return
    m = res.mean(); se = res.std(ddof=1) / math.sqrt(len(res))
    print(f"{label:62s} n={len(res):3d} edge {100*m:+5.1f} [{100*(m-1.96*se):+5.1f},{100*(m+1.96*se):+5.1f}] P1 {100*res[hh=='P1'].mean():+5.1f}(n={(hh=='P1').sum()}) P2 {100*res[hh=='P2'].mean():+5.1f}(n={(hh=='P2').sum()})")


print("\nH1 pod razlicitim definicijama profila (LAB 2022-2026):")
h1(rw, rl, hw_, hl_, 0.3924, 0.7752, "sve razine, apsolutni pragovi (C1r + fav 0,5-0,7)")
h1(rmw, rml, hmw, hml, 0.3924, 0.7752, "samo glavni zdrijeb, ISTI apsolutni pragovi")
qr75 = np.nanquantile(rm, .75); qh25 = np.nanquantile(hm, .25)
h1(rmw, rml, hmw, hml, qr75, qh25, f"samo glavni zdrijeb, vlastiti P75/P25 ({qr75:.4f}/{qh25:.4f})")
qr90 = np.nanquantile(rm, .90); qh10 = np.nanquantile(hm, .10)
h1(rmw, rml, hmw, hml, qr90, qh10, f"samo glavni zdrijeb, vlastiti P90/P10 ({qr90:.4f}/{qh10:.4f})")
