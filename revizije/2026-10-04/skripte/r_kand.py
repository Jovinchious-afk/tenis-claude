# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — B: kandidati na redu (K1, K1b, K9, K10, K11) i tiketi (04.10.2026 18:06).

Pragovi: DECISION_INPUTS (K1, K9, K10, K11), prepisani u PRAGOVI_REVIZIJA_2026-10-04.md točka B.
Samo čita .cache/rev_2026-10-04/*.
"""
import json
import math
import os
import sys
from itertools import combinations

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, edge, corr, load  # noqa: E402


def line(label, s):
    n, e, ci, roi = edge(s)
    if n == 0:
        return f"  {label:46s} n=  0"
    pr = s["pts_resid"].dropna() if "pts_resid" in s else pd.Series(dtype=float)
    pts = f"  poeni {pr.mean():+5.2f}pp (n={len(pr)})" if len(pr) else ""
    return (f"  {label:46s} n={n:3d}  {int(s.win.sum()):3d}W  {100*s.win.mean():5.1f}% / cijena {100*s.p_dev.mean():5.1f}%"
            f"  edge {e:+6.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%{pts}")


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    nv = df[df["sample"] == "NOVO"]

    print("=== K1 — pouzdanost u eri bccf4742 (NOVO)")
    pen = nv.penalties.str.contains("conf_band_65_68", na=False)
    print(line("60-63 sve (prag K1: edge<0 uz n>=25 -> 63)", nv[(nv.conf >= 60) & (nv.conf < 63)]))
    print(line("  od toga izvorno 60-63 (bez kazne 65-68)", nv[(nv.conf >= 60) & (nv.conf < 63) & ~pen]))
    print(line("  od toga spušteno iz 65-68 (kazna -5)", nv[(nv.conf >= 60) & (nv.conf < 63) & pen]))
    print(line(">=63", nv[nv.conf >= 63]))
    print(line("<60", nv[nv.conf < 60]))
    print("  raspodjela sirove pouzdanosti (prije kazni):")
    print("   ", nv.conf_raw.round().value_counts().sort_index().to_dict())
    print("  kazne:", nv.penalties.replace("", "nema").value_counts().to_dict())

    print("\n=== K1b — kazna 65-68 od uvođenja praga 60 (08.09.): pušta li prag 60 kažnjene natrag na tiket?")
    s9 = df[df.date >= "2026-09-08"]
    pen9 = s9.penalties.str.contains("conf_band_65_68", na=False)
    print(line("od 08.09. kažnjeni 65-68 (sada 60-63)", s9[pen9]))
    print(line("  ...od toga na tiketu", s9[pen9 & s9.on_ticket]))
    print(line("od 08.09. izvorno 60-63", s9[(s9.conf >= 60) & (s9.conf < 63) & ~pen9]))
    print(line("od 08.09. >=63", s9[s9.conf >= 63]))
    print(line("STARO prije 08.09. sirovo 65-68", df[(df.date < "2026-09-08") & (df.conf_raw >= 65) & (df.conf_raw < 68)]))

    print("\n=== K9 — duljina 'Own read' (NOVO, era bccf4742; prag: pobjede-porazi < -40 znakova uz n>=60)")
    nv2 = nv.assign(own_len=nv.own_read.str.len())
    w, l = nv2[nv2.win == 1].own_len, nv2[nv2.win == 0].own_len
    print(f"  n={len(nv2)}  prosjek pobjede {w.mean():.0f}  porazi {l.mean():.0f}  razlika {w.mean()-l.mean():+.0f} znakova")
    r, p, n, ci = corr(nv2.own_len, nv2.resid)
    print(f"  uz kontrolu cijene: r(duljina, ishod-cijena) = {r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] P={p:.2f}")
    r, p, n, ci = corr(nv2.own_len, nv2.pts_resid)
    print(f"  r(duljina, ostatak poena) = {r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] P={p:.2f} n={n}")

    print("\n=== K10 — oblik pojaseva od 14.09.")
    s14 = df[df.date >= "2026-09-14"]
    for lo, hi in [(1.20, 1.35), (1.35, 1.65), (1.65, 1.85)]:
        print(line(f"{lo:.2f}-{hi:.2f}", s14[(s14.odds >= lo) & (s14.odds < hi)]))

    print("\n=== K11 — R16+QF")
    s = df[(df.date >= "2026-09-14") & (df["round"] != "") & (df.round_source != "cleared_wrong_auto")]
    print("  službena definicija (measure_candidates: od 14.09., runda poznata):")
    print(line("    R16+QF", s[s["round"].isin(["R16", "QF"])]))
    print(line("    ostale (bez DC)", s[~s["round"].isin(["R16", "QF", "DC"])]))
    m = df[df.round_source == "manual"]
    print("  samo ručne runde (od 26.09.):")
    print(line("    R16+QF", m[m["round"].isin(["R16", "QF"])]))
    print(line("    ostale", m[~m["round"].isin(["R16", "QF", "DC"])]))
    print("  po rundi, ručne:")
    for rd in ["R32", "R16", "QF", "SF", "F"]:
        print(line(f"    {rd}", m[m["round"] == rd]))

    print("\n=== Tiketi od 26.09.")
    tk = pd.DataFrame(load("tickets"))
    tm = pd.DataFrame(load("ticket_matches"))
    tk = tk[tk.ticket_date >= "2026-09-26"].sort_values("ticket_date")
    probs = []
    for _, t in tk.iterrows():
        legs = tm[tm.ticket_id == t["id"]]
        ps, desc = [], []
        for _, lg in legs.iterrows():
            md = pd.Timestamp(str(lg["match_date"])[:10])
            row = df[(df.pick == lg["pick"]) & ((df.opp == lg["player1"]) | (df.opp == lg["player2"]))
                     & ((df.date - md).abs() <= pd.Timedelta(days=2))]
            p = float(row.p_dev.iloc[0]) if len(row) else np.nan
            ps.append(p)
            desc.append(f"{lg['pick'].split()[-1]} @{float(lg['odds']):.2f} {('W' if lg['result']=='won' else ('L' if lg['result']=='lost' else '?'))}"
                        f"{'' if np.isnan(p) else f' (p={p:.2f})'}")
        pj = float(np.prod([p for p in ps if not np.isnan(p)])) if ps else np.nan
        probs.append((t["ticket_date"], t["status"], pj))
        ev = pj * float(t["total_odds"]) - 1 if not np.isnan(pj) else np.nan
        print(f"  {t['ticket_date']} {t['status']:5s} kvota {float(t['total_odds']):5.2f}  P(prolaz) {pj:5.1%}  EV {ev:+.1%}  | " + ", ".join(desc))
    after = [p for d, s_, p in probs if d >= "2026-09-28"]
    p0 = float(np.prod([1 - p for p in after]))
    print(f"  tiketi od 28.09.: {len(after)}, očekivano dobitnih {sum(after):.2f}; vjerojatnost 0 dobitnih slučajno = {p0:.0%}")


if __name__ == "__main__":
    main()
