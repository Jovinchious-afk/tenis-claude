# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — H: scouting (Excel top 150 i tablica player_scouting) (04.10.2026 18:12).

Prag (PRAGOVI točka H): dopuna se preporučuje samo ako mečevi bez profila idu >= 5pp lošije
uz interval koji ne prelazi nulu, ILI neka razina profila nosi informaciju povrh cijene i
ponavlja se u obje polovice. Inače se Excel ne širi radi predviđanja.
Samo čita .cache/rev_2026-10-04/all_vars.pkl i player_scouting.json.
"""
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, edge, load  # noqa: E402


def key(s):
    s = unicodedata.normalize("NFKD", str(s or "").replace("\xa0", " "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()


def line(label, s):
    n, e, ci, roi = edge(s)
    if n == 0:
        return f"  {label:44s} n=  0"
    pr = s.pts_resid.dropna()
    return f"  {label:44s} n={n:3d}  edge {e:+6.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%  poeni {pr.mean():+5.2f}"


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_vars.pkl"))
    ps = pd.DataFrame(load("player_scouting"))
    prof = {}
    for _, p in ps.iterrows():
        for nm in (p.get("player_name"), p.get("display_name")):
            if nm:
                prof[" ".join(key(nm))] = p

    def find(nm):
        k = " ".join(key(nm))
        if k in prof:
            return prof[k]
        toks = set(key(nm))
        c = [v for kk, v in prof.items() if len(kk.split()) >= 2 and set(kk.split()) <= toks]
        return c[0] if c else None

    nv = df[df["sample"] == "NOVO"]
    print("=== Pokrivenost NOVOG uzorka")
    players = pd.unique(pd.concat([nv.pick, nv.opp]))
    found = {p: find(p) for p in players}
    has = [p for p, v in found.items() if v is not None]
    print(f"  igrača u NOVOM uzorku: {len(players)}, s profilom u tablici: {len(has)} ({100*len(has)/len(players):.0f}%)")
    print(f"  pick ima razinu u snapshotu: {nv.scout_p.notna().mean():.0%}; protivnik: {nv.scout_o.notna().mean():.0%}")
    print("  razine (pick):", nv.scout_p.fillna("nema").value_counts().to_dict())
    print("  razine (protivnik):", nv.scout_o.fillna("nema").value_counts().to_dict())
    miss = sorted(p for p, v in found.items() if v is None)
    print("  bez profila:", miss)
    print("\n=== Starost profila (source_date) i pomak ranga")
    ps["source_date"] = pd.to_datetime(ps["source_date"], errors="coerce")
    print("  source_date:", ps.source_date.min().date(), "do", ps.source_date.max().date(),
          "| medijan", ps.source_date.median().date())
    drift = []
    for p in has:
        v = found[p]
        rk_now = pd.concat([nv.loc[nv.pick == p, "rank_p"], nv.loc[nv.opp == p, "rank_o"]]).dropna()
        if len(rk_now) and pd.notna(v.get("rank")):
            drift.append((p, int(v["rank"]), int(rk_now.iloc[-1]), str(v.get("confidence")), str(v.get("source_date"))[:10]))
    big = [d for d in drift if abs(d[1] - d[2]) >= 20]
    print(f"  profila s rangom u tablici i danas: {len(drift)}; pomak ranga >= 20 mjesta: {len(big)}")
    for d in sorted(big, key=lambda x: -abs(x[1] - x[2]))[:15]:
        print(f"    {d[0]:30s} rang u profilu {d[1]:4d} -> danas {d[2]:4d}  razina {d[3]:12s} izvor {d[4]}")
    print("  'Insufficient'/'Low' profili koji su u NOVOM uzorku:",
          sorted(p for p in has if str(found[p].get("confidence")) in ("Insufficient", "Low")))

    print("\n=== Nosi li profil išta povrh cijene (STARO+NOVO)")
    print(line("pick ima profil", df[df.scout_p.notna()]))
    print(line("pick nema profil", df[df.scout_p.isna()]))
    print(line("protivnik ima profil", df[df.scout_o.notna()]))
    print(line("protivnik nema profil", df[df.scout_o.isna()]))
    print(line("NOVO: protivnik nema profil ili Insufficient", nv[nv.scout_o.isna() | (nv.scout_o == "Insufficient")]))
    print(line("NOVO: protivnik s profilom (osim Insufficient)", nv[nv.scout_o.notna() & (nv.scout_o != "Insufficient")]))
    print("  po razini profila picka (polovice: do 08.09. / od 08.09.):")
    for lv in ["High", "Med-High", "Med", "Med-Low", "Low", "Insufficient"]:
        s = df[df.scout_p == lv]
        a, b = s[s.date < "2026-09-08"], s[s.date >= "2026-09-08"]
        na, ea, _, _ = edge(a)
        nb, eb, _, _ = edge(b)
        n, e, ci, roi = edge(s)
        print(f"    {lv:12s} n={n:3d} edge {e:+6.1f}pp ±{ci:4.1f} | prva {ea:+6.1f} (n={na}) / druga {eb:+6.1f} (n={nb})")
    print("\n=== K17 (High profil picka od 27.09.)")
    print(line("High od 27.09.", df[(df.scout_p == "High") & (df.date >= "2026-09-27")]))
    print(line("High do 26.09. (nalaz revizije: -12,4pp n=52)", df[(df.scout_p == "High") & (df.date < "2026-09-27")]))


if __name__ == "__main__":
    main()
