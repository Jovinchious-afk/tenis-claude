# -*- coding: utf-8 -*-
"""Prelazak modela na TML 12 mj. — kriterij A: koja statistika servisa/povrata bolje procjenjuje igrača
(18.10.2026 16:27). Pragovi: revizije/2026-10-18/PRAGOVI_C_TML_PROMPT_2026-10-18.md (16:25).

Kandidati za istu veličinu (servis i povrat igrača), samo mečevi PRIJE datuma meča:
  (a) karijera (svi TML mečevi; zamjena za RapidAPI), (b) 365 dana, (c) 365 dana povučeno prema
  karijeri s K = 1.500 servisnih poena.
Vjerojatnost iz modela poena (`agent.nose.point_model_prob`) — BEZ cijene i bez ELO-a. Na istim
mečevima za sva tri izvora. P1 = 2022–2023, P2 = 2024–2026 (provjera).
Samo čita .cache/lab (obnovljen 18.10.2026 15:36).
    python revizije/2026-10-18/skripte/c_tml_lab.py
"""
import math
import os
import sys
from bisect import bisect_left

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from b_lab import build_history, F_TS, F_DATE, F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W, F_OK  # noqa: E402
from agent.nose import point_model_prob  # noqa: E402

LAB = os.path.join(ROOT, ".cache", "lab")
K = 1500.0
FIELDS = (F_SV, F_1W, F_2W, F_OSV, F_O1W, F_O2W)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact, {})
    # prefiksni zbrojevi po igraču (samo zapisi s potpunom statistikom)
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
        for x in recs[max(lo, j - 8):j]:          # strogi datum: van sve što nije PRIJE dana meča
            if x[F_DATE] >= cd and x[F_OK]:
                s = s - np.array([x[f] for f in FIELDS])
        return s

    def sr(s):
        sv, w1, w2, osv, o1, o2 = s
        if sv < 300 or osv < 300:
            return None
        return (w1 + w2) / sv, 1 - (o1 + o2) / osv, sv

    rows = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_fair"]
        if pd.isna(pf):
            continue
        tidx = int(m["tml_idx"])
        out = {"pf": float(pf), "half": m["half"], "bo": int(m["Best of"]) if not pd.isna(m["Best of"]) else 3}
        ok = True
        for side, pid in (("w", r["winner_id"]), ("l", r["loser_id"])):
            j = pos.get((pid, tidx))
            if j is None:
                ok = False
                break
            cd = hist[pid][j][F_DATE]
            car = sr(sums(pid, 0, j, cd))
            lo = bisect_left(ts[pid], hist[pid][j][F_TS] - pd.Timedelta(days=365))
            y = sr(sums(pid, lo, j, cd))
            if car is None or y is None:
                ok = False
                break
            wy = y[2] / (y[2] + K)
            out[f"car_{side}"] = car[:2]
            out[f"y_{side}"] = y[:2]
            out[f"mix_{side}"] = (wy * y[0] + (1 - wy) * car[0], wy * y[1] + (1 - wy) * car[1])
        if ok:
            rows.append(out)
    print(f"LAB mečeva s cijenom i sva tri izvora za oba igrača: {len(rows)}")
    res = {}
    for src in ("car", "y", "mix"):
        avg_r = np.mean([x[f"{src}_{s}"][1] for x in rows for s in ("w", "l")])
        p, gap, half, pfs = [], [], [], []
        for x in rows:
            sw, rw = x[f"{src}_w"]
            sl, rl = x[f"{src}_l"]
            pw = point_model_prob(sw - (rl - avg_r), sl - (rw - avg_r), x["bo"])
            p.append(min(max(pw, 1e-4), 1 - 1e-4))
            gap.append((sw + rw) - (sl + rl))
            half.append(x["half"])
            pfs.append(x["pf"])
        p, gap, half, pfs = map(np.array, (p, gap, half, pfs))
        res[src] = {}
        for h in ("P1", "P2"):
            mm = half == h
            ll = -np.log(p[mm]).mean()
            acc = (p[mm] > 0.5).mean()
            # r(razlika, ishod − cijena), simetrično (strana pobjednika i gubitnika)
            xg = np.concatenate([gap[mm], -gap[mm]])
            yg = np.concatenate([1 - pfs[mm], -(1 - pfs[mm])])
            rr = float(np.corrcoef(xg, yg)[0, 1])
            res[src][h] = (ll, acc, rr, int(mm.sum()))
    names = {"car": "(a) karijera", "y": "(b) 12 mjeseci", "mix": "(c) 12 mj. prema karijeri (K=1500)"}
    print(f"\n{'izvor':36s} {'P1 log-gub.':>12s} {'P1 točnost':>11s} {'P2 log-gub.':>12s} {'P2 točnost':>11s}   r(ostatak) P1/P2")
    for src in ("car", "y", "mix"):
        a, b = res[src]["P1"], res[src]["P2"]
        print(f"{names[src]:36s} {a[0]:12.4f} {100 * a[1]:10.1f}% {b[0]:12.4f} {100 * b[1]:10.1f}%   {a[2]:+.3f} / {b[2]:+.3f}   (n {a[3]} / {b[3]})")
    pll = {h: -np.log(np.clip(np.array([x["pf"] for x in rows if x["half"] == h]), 1e-4, 1)).mean() for h in ("P1", "P2")}
    pacc = {h: np.mean([x["pf"] > 0.5 for x in rows if x["half"] == h]) for h in ("P1", "P2")}
    print(f"{'za usporedbu: poštena cijena':36s} {pll['P1']:12.4f} {100 * pacc['P1']:10.1f}% {pll['P2']:12.4f} {100 * pacc['P2']:10.1f}%")
    a2, b2, c2 = res["car"]["P2"], res["y"]["P2"], res["mix"]["P2"]
    passed = b2[0] <= a2[0] and b2[1] >= a2[1] - 0.005
    mix_better = (res["mix"]["P1"][0] <= res["y"]["P1"][0] - 0.001) and (c2[0] <= b2[0] - 0.001)
    print(f"\nKRITERIJ A: (b) 12 mj. {'PROLAZI' if passed else 'NE PROLAZI'} naspram karijere na P2 "
          f"(log-gub. {b2[0]:.4f} naspram {a2[0]:.4f}; točnost {100 * b2[1]:.1f}% naspram {100 * a2[1]:.1f}%)")
    print(f"(c) mješavina bolja od (b) na obje polovice za ≥ 0,001: {'DA' if mix_better else 'NE'}")


F_TML_IDX = 30   # indeks zapisa u povijesti (F_TML u b_lab.py)

if __name__ == "__main__":
    main()
