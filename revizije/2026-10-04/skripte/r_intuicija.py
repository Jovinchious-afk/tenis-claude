# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — E: "intuicija" agenta (04.10.2026 18:06).

E1: odmak od tržišta d = pouzdanost - 100*cijena; nosi li informaciju (r(d, ostatak))?
    Prag (PRAGOVI): r >= +0,10 s intervalom iznad nule na STARO i isti predznak na NOVO.
E2: isto s ostatkom poena.
E3: razlozi u "Own read"/analizi NOVIH mečeva (opis, hipoteze).
E4: market_check popunjen naspram ne.
Samo čita .cache/rev_2026-10-04/all_points.pkl.
"""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, corr, edge  # noqa: E402

THEMES = {
    "umor/raspored": r"fatigue|sets this week|sets in (the )?last|matches in (the )?last|7 days|rest|fresh|workload|back-to-back",
    "rejting/ELO/rang": r"\bELO\b|rating|ranking|#\d",
    "forma": r"\bform\b|recent|streak|W-L|wins? in (a row|last)",
    "servis/return": r"serve|hold|return|break[- ]point|\bBP\b|ace",
    "povijest turnira": r"reached|title|champion here|history here|last year|in 20\d\d",
    "teren/uvjeti": r"court|fast|slow|wind|humid|heat|indoor|conditions|altitude|night",
    "stil/matchup": r"style|counter|baseline|power|flat|lefty|left-handed|matchup|weapon|net",
    "tržište": r"market|de-vig|devig|price|odds|implied",
    "H2H": r"\bH2H\b|head-to-head|head to head|met (\w+ )?times|previous meeting",
    "mentalno/pritisak": r"pressure|tight|nerv|mental|clutch|composure|wobble",
}


def line(label, s):
    n, e, ci, roi = edge(s)
    if n == 0:
        return f"  {label:40s} n=  0"
    pr = s.pts_resid.dropna()
    return (f"  {label:40s} n={n:3d}  {100*s.win.mean():5.1f}% / {100*s.p_dev.mean():5.1f}%  edge {e:+6.1f}pp ±{ci:4.1f}"
            f"  ROI {roi:+6.1f}%  poeni {pr.mean():+5.2f} (n={len(pr)})")


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    st, nv = df[df["sample"] == "STARO"], df[df["sample"] == "NOVO"]

    print("=== Koliko se pick uopće razlikuje od tržišta")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        fav = (g.p_dev >= 0.5).mean()
        print(f"  {lab_}: pick = tržišni favorit u {100*fav:.1f}% (n={len(g)}); "
              f"medijan |pouzdanost - cijena| = {g.d_conf.abs().median():.1f}pp; "
              f"pouzdanost SD {g.conf.std():.1f} naspram cijena SD {100*g.p_dev.std():.1f}")

    print("\n=== E1/E2 — odmak od tržišta (d = pouzdanost - cijena) i ishod")
    for lab_, g in (("STARO", st), ("NOVO", nv), ("SVE", df)):
        r, p, n, ci = corr(g.d_conf, g.resid)
        r2, p2, n2, ci2 = corr(g.d_conf, g.pts_resid)
        print(f"  {lab_:5s} r(d, ishod-cijena) = {r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] P={p:.3f} n={n}"
              f" | r(d, ostatak poena) = {r2:+.3f} [{ci2[0]:+.2f}, {ci2[1]:+.2f}] n={n2}")
    print("\n  po eri (STARO+NOVO, ere s n>=25):")
    for era, g in df.groupby("era"):
        if len(g) < 25:
            continue
        r, p, n, ci = corr(g.d_conf, g.resid)
        print(f"    {str(era):10s} n={n:3d}  r={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}]  od {g.date.min():%d.%m.} do {g.date.max():%d.%m.}")
    print("\n  skupine po odmaku:")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        for lo, hi, nm in [(-99, -5, "model 5pp+ ispod cijene"), (-5, 5, "unutar ±5pp"), (5, 10, "model 5-10pp iznad"), (10, 99, "model 10pp+ iznad")]:
            print(line(f"{lab_} {nm}", g[(g.d_conf >= lo) & (g.d_conf < hi)]))

    print("\n=== Pouzdanost kao takva (NOVO naspram STARO), uz kontrolu cijene")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        r, p, n, ci = corr(g.conf, g.resid)
        print(f"  {lab_}: r(pouzdanost, ishod-cijena) = {r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] P={p:.3f} n={n}")
    b = lambda g, y: float(np.mean((g[y] - g.win) ** 2))
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        g = g.assign(cp=g.conf / 100)
        print(f"  {lab_}: Brier cijena {b(g,'p_dev'):.4f} | pouzdanost {b(g,'cp'):.4f} | konstanta "
              f"{float(np.mean((g.win.mean()-g.win)**2)):.4f}")

    print("\n=== E4 — market_check (model se odmaknuo 10pp+ i obrazložio)")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        mc = g.market_check.astype(str).str.len() > 5
        print(line(f"{lab_} market_check popunjen", g[mc]))
        print(line(f"{lab_} prazan", g[~mc]))

    print("\n=== E3 — teme u 'Own read' (NOVO), opis")
    rows = []
    for _, r in nv.iterrows():
        txt = (r.own_read or "")
        for th, pat in THEMES.items():
            if re.search(pat, txt, re.I):
                rows.append((th, r.win, r.p_dev, r.pts_resid))
    t = pd.DataFrame(rows, columns=["tema", "win", "p", "pr"])
    for th, g in t.groupby("tema"):
        n = len(g)
        print(f"  {th:20s} n={n:2d}  {100*g.win.mean():5.1f}% / {100*g.p.mean():5.1f}%  edge {100*(g.win.mean()-g.p.mean()):+6.1f}pp  poeni {g.pr.mean():+5.2f}")
    print("\n  pomaknuti 'tržište' u Own read (model eksplicitno raspravlja cijenu):")
    mk = nv.own_read.str.contains(THEMES["tržište"], case=False, regex=True)
    print(line("  spominje tržište", nv[mk]))
    print(line("  ne spominje", nv[~mk]))

    print("\n=== Duljina Own read i pouzdanost (je li duljina samo zamjena za pouzdanost?)")
    nv2 = nv.assign(L=nv.own_read.str.len())
    for a_, b_ in (("L", "conf"), ("L", "d_conf"), ("L", "p_dev")):
        r, p, n, ci = corr(nv2[a_], nv2[b_])
        print(f"  r({a_}, {b_}) = {r:+.3f} P={p:.3f}")


if __name__ == "__main__":
    main()
