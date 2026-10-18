# -*- coding: utf-8 -*-
"""Revizija 18.10.2026, drugi dio — težine hard v14 naspram v18 (18.10.2026 12:36). PRAGOVI_B točka W.

Hard analize po `model_stamp.weights_version` (14 = 18.07.–03.08., 18 = od 04.08.), edge picka
naspram devigirane SuperSport cijene, unutar pojasa kvote picka (< 1,35; 1,35–1,65; >= 1,65),
pa ponderirano veličinom pojasa. Samo čita dump (.cache/rev_2026-10-18b).
    python revizije/2026-10-18/skripte/b_tezine.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r_base  # noqa: E402

r_base.DUMP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), ".cache", "rev_2026-10-18b")


def main():
    d = r_base.dedupe_same_match(r_base.build())
    d = d[(d.surface == "hard") & d.p_dev.notna() & (~d.elo_suspect)]
    print("hard riješenih s cijenom po verziji težina:", d.weights_version.value_counts(dropna=False).to_dict())
    bands = [(0, 1.35), (1.35, 1.65), (1.65, 99)]
    res = {}
    for v in (14, 18):
        s = d[d.weights_version == v]
        n, e, ci, roi = r_base.edge(s)
        res[v] = s
        print(f"  v{v}: n={n:3d} edge {e:+5.1f}pp ±{ci:4.1f} | pogođeno {100 * s.win.mean():.1f}% | cijena {100 * s.p_dev.mean():.1f}%")
    # stratificirano: razlika v18 − v14 po pojasu, ponderirano brojem v14+v18 u pojasu
    tot_w, diff, var = 0, 0.0, 0.0
    for lo, hi in bands:
        a = res[14][(res[14].odds >= lo) & (res[14].odds < hi)]
        b = res[18][(res[18].odds >= lo) & (res[18].odds < hi)]
        if len(a) < 3 or len(b) < 3:
            print(f"  pojas {lo}-{hi}: premalo (v14 {len(a)}, v18 {len(b)})")
            continue
        ea, eb = (a.win - a.p_dev).mean(), (b.win - b.p_dev).mean()
        va = (a.p_dev * (1 - a.p_dev)).sum() / len(a) ** 2
        vb = (b.p_dev * (1 - b.p_dev)).sum() / len(b) ** 2
        w = len(a) + len(b)
        tot_w += w
        diff += w * (eb - ea)
        var += w * w * (va + vb)
        print(f"  pojas {lo}-{hi}: v14 {100 * ea:+5.1f}pp (n={len(a)}) | v18 {100 * eb:+5.1f}pp (n={len(b)})")
    if tot_w:
        print(f"  RAZLIKA v18 − v14 uz kontrolu pojasa: {100 * diff / tot_w:+.1f}pp ±{196 * math.sqrt(var) / tot_w:.1f}")
    # pick = tržišni favorit (mijenjaju li težine stranu?)
    for v in (14, 18):
        s = res[v]
        print(f"  v{v}: pick je tržišni favorit u {100 * (s.p_dev > 0.5).mean():.1f}% | prosječna pouzdanost {s.conf.mean():.1f}")


if __name__ == "__main__":
    main()
