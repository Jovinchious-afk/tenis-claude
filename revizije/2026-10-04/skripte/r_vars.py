# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — F: korisnikove varijable na NAŠEM korpusu, uz kontrolu cijene (04.10.2026 18:10).

Prag (PRAGOVI točka F): "zanimljivo" = |r| >= 0,10, interval ne prelazi nulu na STARO+NOVO,
isti predznak na STARO i NOVO; Holm preko svih F testova.
Mjera: r(razlika pick - protivnik, ishod - devigirana cijena) i edge gornje/donje trećine.
H2H se računa iz TML-a (samo mečevi PRIJE datuma meča; TML seže do 20.09.2026).
Samo čita .cache/rev_2026-10-04/all_points.pkl i .cache/lab/tml.pkl.
"""
import os
import re
import sys
import unicodedata
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, corr, edge, holm  # noqa: E402

ROOT = os.path.dirname(DUMP.rstrip("\\/").rsplit(os.sep, 1)[0])


def letters(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " "))


def h2h_table(df):
    """(pick, protivnik, datum) -> (pobjede picka, porazi picka) iz TML-a, samo mečevi prije datuma."""
    tml = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "tml.pkl"))
    tml = tml[["winner_name", "loser_name", "approx_date"]].copy()
    tml["w"] = tml["winner_name"].map(letters)
    tml["l"] = tml["loser_name"].map(letters)
    names = sorted(set(tml["w"]) | set(tml["l"]))
    tokset = {n: set(n.split()) for n in names}

    def resolve(nm):
        n = letters(nm)
        if n in tokset:
            return n
        toks = set(n.split())
        # TML ime čije su sve riječi sadržane u našem (npr. "jaume munar" u "jaume antoni munar clar")
        c = [k for k, t in tokset.items() if len(t) >= 2 and t <= toks]
        return max(c, key=lambda k: len(tokset[k])) if len(c) >= 1 else None

    pair = defaultdict(list)
    for w, l, d in zip(tml["w"], tml["l"], tml["approx_date"]):
        pair[frozenset([w, l])].append((d, w))
    out, res = [], {}
    for _, r in df.iterrows():
        a, b = resolve(r.pick), resolve(r.opp)
        if not a or not b:
            out.append((np.nan, np.nan))
            continue
        recs = [x for x in pair.get(frozenset([a, b]), []) if x[0] < r.date - pd.Timedelta(days=3)]
        out.append((sum(1 for d, w in recs if w == a), sum(1 for d, w in recs if w == b)))
        res[(r.pick, r.opp)] = (a, b)
    return out


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    h = h2h_table(df)
    df["h2h_w"] = [x[0] for x in h]
    df["h2h_l"] = [x[1] for x in h]
    df["h2h_n"] = df.h2h_w + df.h2h_l
    df["d_h2h"] = np.where(df.h2h_n >= 2, (df.h2h_w - df.h2h_l) / df.h2h_n.replace(0, np.nan), np.nan)
    df["night"] = np.where(df.session.isin(["day", "night"]), (df.session == "night").astype(float), np.nan)
    df["scout_has"] = df.scout_p.notna().astype(float)
    lvl = {"Insufficient": 0, "Low": 1, "Med-Low": 2, "Med": 3, "Med-High": 4, "High": 5}
    df["scout_lvl"] = df.scout_p.map(lvl)
    df["opp_scout_lvl"] = df.scout_o.map(lvl)
    print(f"H2H iz TML-a: par pronađen u {df.h2h_n.notna().sum()} od {len(df)}; 2+ meča u {(df.h2h_n >= 2).sum()}")

    VARS = [("night", "sesija noć (1) / dan (0)"), ("d_hold", "hold % (sezona)"), ("d_ret", "return % (sezona)"),
            ("d_serve", "servisni poeni %"), ("d_ace100", "asovi na 100 (v20+)"), ("d_fs_pct", "1. servis %"),
            ("d_bps", "BP spašeni %"), ("d_bpc", "BP iskorišteni %"), ("d_f10", "forma 10"), ("d_f5", "forma 5"),
            ("d_fq", "forma x kvaliteta"), ("d_srf", "zapis na podlozi/uvjetima"), ("d_rank", "rang (log omjer)"),
            ("d_elo_s", "ELO podloge"), ("d_elo_o", "ELO ukupni"), ("d_h2h", "H2H (2+ meča, TML)"),
            ("d_rest", "dani odmora"), ("d_s7", "setovi u 7 dana"), ("d_m7", "mečevi u 7 dana"), ("d_age", "dob"),
            ("scout_has", "pick ima scouting profil"), ("scout_lvl", "razina profila picka"),
            ("opp_scout_lvl", "razina profila protivnika"), ("d_tbest", "povijest na turniru")]
    st, nv = df[df["sample"] == "STARO"], df[df["sample"] == "NOVO"]
    out = []
    for col, label in VARS:
        r_all, p_all, n_all, ci = corr(df[col], df.resid)
        r_st, _, n_st, _ = corr(st[col], st.resid)
        r_nv, _, n_nv, _ = corr(nv[col], nv.resid)
        r_pt, p_pt, n_pt, _ = corr(df[col], df.pts_resid)
        s = df[df[col].notna()]
        if s[col].nunique() > 3:
            q1, q2 = s[col].quantile([1 / 3, 2 / 3])
            lo_, hi_ = s[s[col] <= q1], s[s[col] >= q2]
        else:
            lo_, hi_ = s[s[col] == s[col].min()], s[s[col] == s[col].max()]
        e_lo, e_hi = edge(lo_)[1], edge(hi_)[1]
        out.append((label, n_all, r_all, ci, p_all, r_st, n_st, r_nv, n_nv, r_pt, n_pt, e_lo, e_hi))
    hp = holm([o[4] if not np.isnan(o[4]) else 1.0 for o in out])
    print(f"\n{'varijabla':28s} {'n':>4s}  r(ishod) [95%]       STARO  NOVO   r(poeni)  donja/gornja trećina edge   Holm  ocjena")
    for o, h_ in zip(out, hp):
        label, n_all, r_all, ci, p_all, r_st, n_st, r_nv, n_nv, r_pt, n_pt, e_lo, e_hi = o
        same = (np.sign(r_st) == np.sign(r_nv)) if not (np.isnan(r_st) or np.isnan(r_nv)) else False
        zan = abs(r_all) >= 0.10 and (ci[0] > 0 or ci[1] < 0) and same
        print(f"{label:28s} {n_all:4d}  {r_all:+.3f} [{ci[0]:+.2f},{ci[1]:+.2f}]  {r_st:+.2f}  {r_nv:+.2f}"
              f"   {r_pt:+.3f}     {e_lo:+6.1f} / {e_hi:+6.1f}pp          {h_:.2f}  {'ZANIMLJIVO' if zan else '-'}")

    print("\n=== Umor kao argument modela: kad je naš pick 'odmorniji' (3+ seta manje u 7 dana)")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        fresher = g[g.d_s7 <= -3]
        tired = g[g.d_s7 >= 3]
        rest_ = g[(g.d_s7 > -3) & (g.d_s7 < 3)]
        for nm, s in (("pick odmorniji 3+ seta", fresher), ("podjednako", rest_), ("pick umorniji 3+ seta", tired)):
            n, e, ci, roi = edge(s)
            pr = s.pts_resid.dropna()
            print(f"  {lab_:5s} {nm:24s} n={n:3d} edge {e:+6.1f}pp ±{ci:4.1f}  poeni {pr.mean() if len(pr) else float('nan'):+5.2f}")

    print("\n=== Sesija po uzorku (noć naspram dan)")
    for lab_, g in (("STARO", st), ("NOVO", nv)):
        for s_ in ("day", "night"):
            n, e, ci, roi = edge(g[g.session == s_])
            print(f"  {lab_:5s} {s_:5s} n={n:3d} edge {e:+6.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%")
    df.to_pickle(os.path.join(DUMP, "all_vars.pkl"))


if __name__ == "__main__":
    main()
