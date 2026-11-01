# -*- coding: utf-8 -*-
"""Revizija 01.11.2026 — naši pickovi: D4 (pojas kvote), D7 (tko nas ruši po rundama), D8 (novčić
odlučen samo ELO-om), D9 (tie-break zapis), C4 (gubitni naspram dobitnih uz kontrolu cijene), F
(Nose i Intuicija na tjednu) i ista noga na dva tiketa (01.11.2026 13:26).

Pragovi: revizije/2026-11-01/PRAGOVI_REVIZIJA_2026-11-01.md (13:05), točke C4, D4, D7, D8, D9, F.
Sve uz kontrolu cijene (edge = pobjeda − devigirana SuperSport cijena; usporedbe skupina unutar
pojasa kvote). Analize s `elo_suspect` isključene. Samo čita .cache/rev_2026-11-01/*.
    python revizije/2026-11-01/skripte/r_nasi.py
"""
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, corr, holm, load  # noqa: E402

BANDS = [(1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)]
BANDS_D4 = [(1.0, 1.35), (1.35, 1.45), (1.45, 1.50), (1.50, 1.65), (1.65, 99)]
HOST = {"basel": "SUI", "vienna": "AUT", "paris": "FRA", "lyon": "FRA", "brussels": "BEL", "almaty": "KAZ",
        "shanghai": "CHN", "beijing": "CHN", "chengdu": "CHN", "hangzhou": "CHN", "tokyo": "JPN",
        "new york": "USA", "us open": "USA", "cincinnati": "USA", "toronto": "CAN", "montreal": "CAN",
        "washington": "USA", "winston": "USA", "umag": "CRO", "kitzb": "AUT", "gstaad": "SUI",
        "hamburg": "GER", "bastad": "SWE", "los cabos": "MEX", "atlanta": "USA", "metz": "FRA",
        "antwerp": "BEL", "stockholm": "SWE", "laver": "", "davis": "", "wimbledon": "GBR", "london": "GBR",
        "mallorca": "ESP", "eastbourne": "GBR", "halle": "GER", "queen": "GBR", "stuttgart": "GER",
        "s-hertogenbosch": "NED", "roland": "FRA", "geneva": "SUI", "rome": "ITA", "madrid": "ESP",
        "munich": "GER", "barcelona": "ESP", "monte": "MON", "estoril": "POR", "bucharest": "ROU",
        "marrakech": "MAR", "houston": "USA", "miami": "USA", "indian wells": "USA"}


def host_of(t):
    t = str(t or "").lower()
    for k, v in HOST.items():
        if k in t:
            return v
    return None


def e_ci(g):
    n = len(g)
    if n == 0:
        return 0, np.nan, np.nan, np.nan
    e = 100 * (g.win.mean() - g.p_dev.mean())
    se = 100 * math.sqrt((g.p_dev * (1 - g.p_dev)).sum()) / n
    return n, e, e - 1.96 * se, e + 1.96 * se


def banded(a, b):
    tot, w = 0.0, 0
    for lo, hi in BANDS:
        x = a[(a.odds >= lo) & (a.odds < hi)]
        y = b[(b.odds >= lo) & (b.odds < hi)]
        if len(x) and len(y):
            tot += ((x.win.mean() - x.p_dev.mean()) - (y.win.mean() - y.p_dev.mean())) * len(x)
            w += len(x)
    return 100 * tot / w if w else np.nan


def line(lab, g, ref=None):
    n, e, lo, hi = e_ci(g)
    if n == 0:
        return f"  {lab:60s} n=  0"
    s = f"  {lab:60s} n={n:3d} {int(g.win.sum()):3d}W  edge {e:+6.1f}pp [{lo:+6.1f}, {hi:+6.1f}]"
    if ref is not None and len(ref):
        s += f" | ostali {e_ci(ref)[1]:+5.1f}pp (n={len(ref)}) | razlika u istom pojasu {banded(g, ref):+5.1f}pp"
    return s


def rline(lab, x, y):
    r, p, n, (lo, hi) = corr(x, y)
    if n < 5 or pd.isna(r):
        return f"  {lab:60s} n={n:3d}  r = -", np.nan, n, 1.0
    return f"  {lab:60s} n={n:3d}  r = {r:+.3f} [{lo:+.2f}, {hi:+.2f}]  P={p:.3f}", r, n, p


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    df = df[df.p_dev.notna() & ~df.elo_suspect].copy()
    df["resid"] = df.win - df.p_dev
    df["host"] = df.tournament.map(host_of)
    df["home_p"] = (df.nat_p.notna()) & (df.nat_p == df.host)
    df["home_o"] = (df.nat_o.notna()) & (df.nat_o == df.host)
    nv = df[df["sample"] == "NOVO"]
    st = df[df["sample"] == "STARO"]
    tj = df[df.tjedan]

    # ------------------------------------------------------------------ D4
    print("=== D4. Edge po pojasu kvote (naši pickovi). Prag: <= -5pp u OBJE ere i spojeni interval ispod 0")
    print(f"  {'pojas':12s} {'STARO':>26s} {'NOVO':>26s} {'TJEDAN':>26s} {'spojeno STARO+NOVO':>30s}  presuda")
    for lo, hi in BANDS_D4:
        sel = lambda g: g[(g.odds >= lo) & (g.odds < hi)]
        a, b, c = sel(st), sel(nv), sel(tj)
        ab = pd.concat([a, b])
        na, ea, _, _ = e_ci(a)
        nb, eb, _, _ = e_ci(b)
        nc, ec, _, _ = e_ci(c)
        nab, eab, lab_, hab = e_ci(ab)
        ok = (ea <= -5) and (eb <= -5) and (hab < 0)
        print(f"  {lo:.2f}-{(hi if hi < 50 else 9):.2f}   {ea:+6.1f}pp (n={na:3d})        {eb:+6.1f}pp (n={nb:3d})        "
              f"{ec:+6.1f}pp (n={nc:3d})     {eab:+6.1f}pp [{lab_:+5.1f}, {hab:+5.1f}] (n={nab})   "
              f"{'PRIJEDLOG' if ok else 'ne predlaže se'}")
    print("  --- samo noge stvarnih tiketa (svi od 27.05.)")
    legs = df[df.on_ticket]
    for lo, hi in BANDS_D4:
        g = legs[(legs.odds >= lo) & (legs.odds < hi)]
        print(line(f"noge {lo:.2f}-{(hi if hi < 50 else 9):.2f}", g))
    print("  --- hard: pojas 1,35-1,43 (K5) i 1,43-1,60 (postojeća oprezna zona, max 1 po tiketu)")
    for lab, g in (("STARO hard", st[st.surface == "hard"]), ("NOVO", nv)):
        print(line(f"{lab} 1,35-1,43", g[(g.odds >= 1.35) & (g.odds < 1.43)]))
        print(line(f"{lab} 1,43-1,60", g[(g.odds >= 1.43) & (g.odds <= 1.60)]))

    # ------------------------------------------------------------------ D7
    print("\n=== D7. Tko nas ruši po rundama (NOVO, ručne runde) — opis")
    rmap = {"R128": "R128/R64", "R64": "R128/R64", "R32": "R32", "R16": "R16", "QF": "QF", "SF": "SF/F", "F": "SF/F"}
    nv = nv.copy()
    nv["rg"] = nv["round"].map(rmap)
    feats = [("ELO jaz na podlozi (pick − prot.)", "d_elo_s"), ("rang (log, + = pick bolji)", "d_rank"),
             ("dob (pick − prot.)", "d_age"), ("forma 10 (pick − prot.)", "d_f10"),
             ("forma × kvaliteta", "d_fq"), ("TML servis+povrat 12 mj.", None),
             ("odmor dana (pick − prot.)", "d_rest"), ("setovi u 7 dana (pick − prot.)", "d_s7"),
             ("servis na turniru (pick − prot.)", "d_tf_sv"), ("TB zapis (pick − prot.)", "d_tb")]
    nv["d_tml_sr"] = (nv.tml_s_p - nv.tml_s_o) + (nv.tml_r_p - nv.tml_r_o)
    for g_ in ("R128/R64", "R32", "R16", "QF", "SF/F"):
        x = nv[nv.rg == g_]
        n, e, lo, hi = e_ci(x)
        lost, won = x[x.win == 0], x[x.win == 1]
        print(f"\n  {g_}: n={n} edge {e:+.1f}pp [{lo:+.1f}, {hi:+.1f}] | izgubljeno {len(lost)} | "
              f"protivnik domaći u porazima {int(lost.home_o.sum())}/{len(lost)}, u pobjedama {int(won.home_o.sum())}/{len(won)} | "
              f"pick autsajder u porazima {int((lost.p_dev < 0.5).sum())}, u pobjedama {int((won.p_dev < 0.5).sum())}")
        parts = []
        for lab, c in feats:
            c = c or "d_tml_sr"
            a_, b_ = lost[c].dropna(), won[c].dropna()
            if len(a_) >= 3 and len(b_) >= 3:
                parts.append(f"{lab}: porazi {a_.mean():+.3f} / pobjede {b_.mean():+.3f}")
        print("     " + "\n     ".join(parts))
        if len(lost):
            print("     porazi: " + "; ".join(f"{r.pick.split()[-1]} – {r.opp.split()[-1]} @{r.odds:.2f}" for _, r in lost.iterrows()))

    # ------------------------------------------------------------------ D8
    print("\n=== D8. Novčić odlučen samo ELO-om (cijena picka < 0,60) i tekst analize o tankoj prednosti — opis")
    for lab, g in (("STARO", st), ("NOVO", nv), ("TJEDAN", tj)):
        c = g[g.p_dev < 0.60]
        print(line(f"{lab}: cijena picka < 0,60", c, g.drop(c.index)))
    pat = re.compile(r"coin[- ]?flip|near coin|narrow|marginal|thin|solely|sole |nearly sole|only (?:argument|real|clear|edge|category|confirm)|single (?:category|confirm)|one category", re.I)
    for lab, g in (("STARO", st), ("NOVO", nv)):
        txt = (g.analysis.fillna("") + " " + g.own_read.fillna("")).str.lower()
        c = g[txt.apply(lambda s: bool(pat.search(s)))]
        print(line(f"{lab}: analiza sama kaže 'tanko/novčić/samo X'", c, g.drop(c.index)))
        cc = c[c.p_dev < 0.60]
        print(line(f"{lab}:   ... i cijena < 0,60", cc, g[(g.p_dev < 0.60)].drop(cc.index, errors="ignore")))

    # ------------------------------------------------------------------ D9
    print("\n=== D9. Tie-break zapis (API, zadnji mečevi) na našim pickovima — r(razlika TB %, ishod − cijena), oba >= 5 TB")
    for lab, g in (("STARO", st), ("NOVO", nv), ("svi", df)):
        h = g[(g.tb_pn >= 5) & (g.tb_on >= 5)]
        print(rline(lab, h.d_tb, h.resid)[0])
        lead = h[h.d_tb >= 0.20]
        print(line(f"{lab}: pick vodi u TB zapisu 20pp+", lead, h.drop(lead.index)))
        trail = h[h.d_tb <= -0.20]
        print(line(f"{lab}: protivnik vodi u TB zapisu 20pp+", trail, h.drop(trail.index)))

    # ------------------------------------------------------------------ C4
    print("\n=== C4. Gubitni naspram dobitnih uz kontrolu cijene (r s ostatkom ishod − cijena) — opis, Holm po uzorku")
    df["d_tml_sr"] = (df.tml_s_p - df.tml_s_o) + (df.tml_r_p - df.tml_r_o)
    df["nose_vs_p"] = df.nose_p_own - df.p_dev
    tj, nv2 = df[df.tjedan], df[df["sample"] == "NOVO"]
    vars_ = [("ELO jaz podloga", "d_elo_s"), ("rang", "d_rank"), ("forma 10", "d_f10"), ("forma × kvaliteta", "d_fq"),
             ("TML servis+povrat", "d_tml_sr"), ("odmor", "d_rest"), ("setovi 7 dana", "d_s7"), ("dob", "d_age"),
             ("TB zapis", "d_tb"), ("servis na turniru", "d_tf_sv"), ("Nose vlastita − cijena", "nose_vs_p"),
             ("Intuicija prior", "int_prior")]
    for lab_s, g in (("TJEDAN", tj), ("NOVO", nv2)):
        outs, ps = [], []
        for lab, c in vars_:
            s, r, n, p = rline(f"{lab_s} {lab}", g[c], g.resid)
            outs.append(s)
            ps.append(p if not pd.isna(r) else 1.0)
        for s, hp in zip(outs, holm(ps)):
            print(s + f"  Holm {hp:.2f}")
        for lab, c in (("protivnik domaći", "home_o"), ("pick domaći", "home_p")):
            x = g[g[c]]
            print(line(f"{lab_s} {lab}", x, g.drop(x.index)))

    # ------------------------------------------------------------------ F
    print("\n=== F. Nose i Intuicija na TJEDNU")
    for s_ in ("UKLJUČI", "UZ UPOZORENJE", "IZBJEGAVAJ"):
        x = tj[tj.nose_suit == s_]
        print(line(f"Nose {s_}", x, tj.drop(x.index)))
    up = tj[tj.nose_diff >= 5]
    print(line("Nose daje picku 5pp+ više od cijene", up, tj.drop(up.index)))
    dn = tj[tj.nose_diff <= -5]
    print(line("Nose daje picku 5pp+ manje od cijene", dn, tj.drop(dn.index)))
    print(rline("Nose vlastita − cijena (TJEDAN)", tj.nose_p_own - tj.p_dev, tj.resid)[0])
    print(rline("Intuicija prior (TJEDAN)", tj.int_prior, tj.resid)[0])

    # ------------------------------------------------------------------ ista noga na dva tiketa
    print("\n=== Ista noga (isti meč) na više tiketa — svi tiketi od 27.05.")
    tk = pd.DataFrame(load("tickets"))
    tm = pd.DataFrame(load("ticket_matches"))
    real = tk[tk.status.isin(["won", "lost", "pending"])]
    legs_ = tm[tm.ticket_id.isin(real.id)].copy()
    legs_ = legs_.merge(real[["id", "ticket_date", "status"]], left_on="ticket_id", right_on="id", suffixes=("", "_t"))
    legs_["pair"] = legs_.apply(lambda r: frozenset([str(r.player1), str(r.player2)]), axis=1)
    legs_["md"] = pd.to_datetime(legs_.match_date.astype(str).str[:10])
    groups = defaultdict(list)
    for _, r in legs_.iterrows():
        key = (r.pair, r.pick)
        found = None
        for k2 in groups:
            if k2[0] == key and abs((k2[1] - r.md).days) <= 2:
                found = k2
                break
        groups[found or (key, r.md)].append(r)
    multi = {k: v for k, v in groups.items() if len({x.ticket_id for x in v}) >= 2}
    n_t = real.shape[0]
    print(f"  stvarnih tiketa: {n_t} | noga koje se pojavljuju na 2+ tiketa: {len(multi)}")
    lost_by_shared = 0
    for k, v in sorted(multi.items(), key=lambda kv: kv[0][1]):
        tids = sorted({str(x.ticket_date)[:10] + ' ' + str(x['status']) for x in v})
        res = {x.result for x in v}
        print(f"   {k[0][1]:24s} {k[1]:%d.%m.}  tiketi: {', '.join(tids)}  ishod noge: {','.join(sorted(map(str, res)))}")
        if "lost" in res:
            lost_by_shared += 1
    print(f"  od toga izgubljenih noga: {lost_by_shared}")


if __name__ == "__main__":
    main()
