# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — C: analize gubitaka od 27.09. (18.10.2026 09:14, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točka C (09:07).
C1 popis verdikata i prijedloga; C2 točnost oznake [SIGNAL CONFIRMED] (točno = skupina s tim
faktorom ima edge ≤ −3pp i interval ispod nule na NOVO+STARO, uz kontrolu cijene); C3 koliko
analiza spominje "ATP wins this season" i kako ga ocjenjuje.
Samo čita .cache/rev_2026-10-18/*.
"""
import math
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, load  # noqa: E402

VERDICTS = ["SIGNAL CONFIRMED", "SIGNAL NOT CONFIRMED", "SIGNAL CONTRADICTED", "INSUFFICIENT DATA", "POST-MATCH ONLY"]


def edge_ci(g):
    n = len(g)
    if n == 0:
        return 0, np.nan, np.nan, np.nan
    e = 100 * (g.win.mean() - g.p_dev.mean())
    se = 100 * math.sqrt((g.p_dev * (1 - g.p_dev)).sum()) / n
    return n, e, e - 1.96 * se, e + 1.96 * se


def banded(g_in, g_out):
    """Ponderirana razlika edgea (u skupini − izvan) unutar pojasa kvote."""
    tot, w = 0.0, 0
    for lo, hi in [(1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)]:
        a = g_in[(g_in.odds >= lo) & (g_in.odds < hi)]
        b = g_out[(g_out.odds >= lo) & (g_out.odds < hi)]
        if len(a) and len(b):
            tot += ((a.win.mean() - a.p_dev.mean()) - (b.win.mean() - b.p_dev.mean())) * len(a)
            w += len(a)
    return 100 * tot / w if w else np.nan


def main():
    tm = pd.DataFrame(load("ticket_matches"))
    tk = pd.DataFrame(load("tickets")).set_index("id")
    la = tm[tm.loss_analysis.notna() & (tm.match_date.astype(str) >= "2026-09-27")].copy()
    la["ticket_status"] = la.ticket_id.map(tk.status)
    print(f"=== C1. Analize gubitaka od 27.09.: {len(la)} (od 04.10.: {(la.match_date.astype(str) >= '2026-10-04').sum()}; "
          f"na pravom tiketu: {la.ticket_status.isin(['won','lost']).sum()}, samo analiza: {(la.ticket_status == 'analysis_only').sum()})")
    uniq = la.drop_duplicates(["match_date", "pick"])
    print(f"  različitih mečeva: {len(uniq)} (ostalo su isti meč na dva tiketa)")
    vc = Counter()
    confirmed = []
    for _, r in la.iterrows():
        txt = str(r.loss_analysis)
        for v in VERDICTS:
            vc[v] += len(re.findall(r"\[" + re.escape(v), txt))
        for m in re.finditer(r"\*\*(?:Factor \d[^*]*|[^*]{3,80})\*\*[^\[]{0,1500}?\[SIGNAL CONFIRMED", txt, re.S):
            head = re.sub(r"\s+", " ", m.group(0)[:110])
            confirmed.append((str(r.match_date)[:10], r.pick.split()[-1], head))
    print("  oznake (broj pojavljivanja):", dict(vc))
    nochange = la.loss_analysis.str.contains("No model change justified", case=False).sum()
    print(f"  'No model change justified': {nochange} od {len(la)}")
    print("  faktori proglašeni [SIGNAL CONFIRMED]:")
    for c in confirmed:
        print("    ", c)

    print("\n=== C3. 'ATP wins this season'")
    m_atp = la.loss_analysis.str.contains("ATP wins this season|season wins|seasonal win", case=False, regex=True)
    print(f"  spominje: {m_atp.sum()} od {len(la)} analiza")
    for v in VERDICTS:
        pat = r"(?:ATP wins this season|season wins|seasonal win)[^\[]{0,700}\[" + re.escape(v)
        k = la.loss_analysis.str.contains(pat, case=False, regex=True).sum()
        if k:
            print(f"    uz oznaku [{v}]: {k}")
    prop = la.loss_analysis.str.contains(r"WHAT SHOULD CHANGE[\s\S]{0,400}(?:ATP wins|season wins)", case=False, regex=True).sum()
    print(f"  predlaže izmjenu vezanu uz ATP pobjede u 'What should change': {prop}")

    print("\n=== C2. Točnost [SIGNAL CONFIRMED] — mjereno na NOVO+STARO (hard i sve), uz kontrolu cijene")
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    df = df[df.p_dev.notna()]
    hard = df[df.surface == "hard"]
    s14 = df[(df.date >= "2026-09-14") & (df["round"] != "")]
    checks = [
        ("R16/QF (runde od 14.09.)", s14[s14["round"].isin(["R16", "QF"])], s14[~s14["round"].isin(["R16", "QF"])]),
        ("pojas 1,43-1,60 (sve)", df[(df.odds >= 1.43) & (df.odds < 1.60)], df[(df.odds < 1.43) | (df.odds >= 1.60)]),
        ("pojas 1,43-1,60 (hard)", hard[(hard.odds >= 1.43) & (hard.odds < 1.60)], hard[(hard.odds < 1.43) | (hard.odds >= 1.60)]),
        ("pick ima MANJE ATP pobjeda u sezoni", df[df.d_seas_w < 0], df[df.d_seas_w > 0]),
        ("pick ima 8+ ATP pobjeda MANJE", df[df.d_seas_w <= -8], df[df.d_seas_w > -8]),
        ("pick ima 8+ ATP pobjeda VIŠE", df[df.d_seas_w >= 8], df[df.d_seas_w < 8]),
    ]
    for lab, a, b in checks:
        n, e, lo, hi = edge_ci(a)
        n2, e2, _, _ = edge_ci(b)
        verdict = "TOČNO (≤−3pp, interval ispod 0)" if (e <= -3 and hi < 0) else "NETOČNO"
        print(f"  {lab:38s} n={n:3d} edge {e:+6.1f}pp [{lo:+5.1f}, {hi:+5.1f}] | ostali n={n2:3d} {e2:+6.1f}pp | "
              f"razlika u istom pojasu {banded(a, b):+5.1f}pp -> {verdict}")
    sw = df[df.d_seas_w.notna()]
    r = np.corrcoef(sw.d_seas_w, sw.resid)[0, 1] if len(sw) > 5 else np.nan
    print(f"  r(razlika ATP pobjeda u sezoni, ishod − cijena): {r:+.3f} (n={len(sw)}); NOVO: "
          f"{np.corrcoef(sw[sw['sample']=='NOVO'].d_seas_w, sw[sw['sample']=='NOVO'].resid)[0,1]:+.3f} (n={(sw['sample']=='NOVO').sum()})")


if __name__ == "__main__":
    main()
