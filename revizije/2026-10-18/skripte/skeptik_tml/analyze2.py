# -*- coding: utf-8 -*-
import os, sys, pickle, math
import numpy as np
import pandas as pd
SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), ".cache", "rev_2026-10-18b", "skeptik_tml")
df, P = pickle.load(open(os.path.join(SCR, "probs.pkl"), "rb"))
LL = {K: -np.log(p) for K, p in P.items()}
half = df["half"].values
name = {None: "(a) karijera", 0: "(b) 12 mj.", 1500: "(c) K=1500"}

print("=== reprodukcija ===")
for K in (None, 0, 1500):
    out = []
    for h in ("P1", "P2"):
        m = half == h
        out.append(f"{h} LL {LL[K][m].mean():.4f} acc {100*(P[K][m] > 0.5).mean():.1f}%")
    print(name[K], " | ".join(out))

print("\n=== K-sken: log-gubitak po polovici (a=None, b=0) ===")
for K in (None, 0, 250, 500, 1000, 1500, 2500, 4000, 8000):
    print(f"K={str(K):>5s}  P1 {LL[K][half=='P1'].mean():.4f}   P2 {LL[K][half=='P2'].mean():.4f}")

def paired(a, b, mask, cluster=None, B=2000, seed=1):
    d = (LL[a] - LL[b])[mask]   # pozitivno = b bolji (manji gubitak)
    n = len(d)
    m = d.mean(); se = d.std(ddof=1) / math.sqrt(n)
    res = {"n": n, "mean(a-b)": m, "se_naive": se, "z": m / se}
    if cluster is not None:
        cl = cluster[mask]
        codes, uniq = pd.factorize(cl)
        k = len(uniq)
        sums_ = np.bincount(codes, weights=d, minlength=k)
        cnt = np.bincount(codes, minlength=k)
        rng = np.random.default_rng(seed)
        bm = np.empty(B)
        for bi in range(B):
            idx = rng.integers(0, k, k)
            bm[bi] = sums_[idx].sum() / cnt[idx].sum()
        res["se_boot_cluster"] = bm.std(ddof=1)
        res["ci95"] = (np.percentile(bm, 2.5), np.percentile(bm, 97.5))
        res["k_clusters"] = k
    return res

tid = df["tid"].astype(str).values
# klaster = turnir (tourney_id)
print("\n=== upareni test (pozitivno = drugi izvor bolji), klaster = turnir ===")
for (a, b, lab) in ((None, 1500, "(a)-(c)"), (None, 0, "(a)-(b)"), (0, 1500, "(b)-(c)")):
    for h in ("P1", "P2"):
        r = paired(a, b, half == h, tid)
        print(f"{lab} {h}: razlika {r['mean(a-b)']:+.4f}  SE naivni {r['se_naive']:.4f} (z {r['z']:+.1f})  SE klaster-turnir {r['se_boot_cluster']:.4f}  CI95 [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}]  n={r['n']} klastera={r['k_clusters']}")

# klaster = igrač pobjednik... (meč ima 2 igrača; koristimo oba kao "povezani" - jednostavno: klaster po turniru-godini već je gruba; dodatno klaster po pobjedniku)
print("\n=== klaster = igrač pobjednik (gruba procjena) ===")
wid = df["wid"].astype(str).values
for (a, b, lab) in ((None, 1500, "(a)-(c)"), (None, 0, "(a)-(b)")):
    for h in ("P1", "P2"):
        r = paired(a, b, half == h, wid)
        print(f"{lab} {h}: SE klaster-igrač {r['se_boot_cluster']:.4f}  CI95 [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] klastera={r['k_clusters']}")

print("\n=== po kalendarskoj godini: log-gubitak i razlika (a)-(c) ===")
yr = df["year"].values
for y_ in sorted(set(yr)):
    m = yr == y_
    d_ac = (LL[None] - LL[1500])[m]
    d_ab = (LL[None] - LL[0])[m]
    d_bc = (LL[0] - LL[1500])[m]
    print(f"{y_}: n={m.sum():5d} | a {LL[None][m].mean():.4f} b {LL[0][m].mean():.4f} c {LL[1500][m].mean():.4f} | (a-c) {d_ac.mean():+.4f} (SE {d_ac.std(ddof=1)/math.sqrt(m.sum()):.4f}) | (a-b) {d_ab.mean():+.4f} | (b-c) {d_bc.mean():+.4f}")

print("\n=== točnost: razlika (c) - (a) po polovici, broj mečeva gdje se razilaze ===")
for h in ("P1", "P2"):
    m = half == h
    ca = (P[None][m] > 0.5); cc = (P[1500][m] > 0.5); cb = (P[0][m] > 0.5)
    print(h, f"acc a {100*ca.mean():.2f} b {100*cb.mean():.2f} c {100*cc.mean():.2f}; razilaze se a/c u {int((ca!=cc).sum())} mečeva (c ispravno, a krivo: {int((cc&~ca).sum())}; obrnuto {int((ca&~cc).sum())})")
