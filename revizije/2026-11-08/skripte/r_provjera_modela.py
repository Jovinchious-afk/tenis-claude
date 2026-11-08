# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 (večer) — provjera POSTOJEĆIH kazni, praga 63, bonusa u bodovanju i varijabli
"maknuto iz modela" na zadnjih 5 tjedana (08.11.2026 17:09).

Pragovi: revizije/2026-11-08/PRAGOVI_REVIZIJA_2026-11-08.md, točke K i L (NAKNADNO 08.11.2026 17:08).
Ništa se ne mijenja u modelu. Čita lokalni dump (.cache/rev_2026-11-08/base.pkl i analyzed_matches.json).
    python revizije/2026-11-08/skripte/r_provjera_modela.py > .cache/rev_2026-11-08/out_provjera_modela.txt
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r_base import DUMP, ROOT, edge, holm  # noqa: E402
from r_nasi import band, boot, diff_bw, halves  # noqa: E402

sys.path.insert(0, ROOT)
from agent import nos_ploca as npl  # noqa: E402

RNG = np.random.default_rng(20261108)


def e(s):
    n, ed, ci, _ = edge(s)
    return n, ed


def boot_cijena(df, mask, reps=2000):
    """Za skupinu koju definira cijena: razlika edgea skupine i ostalih (bootstrap)."""
    m = np.asarray(mask, bool)
    r = df["resid"].values
    vals = []
    n = len(df)
    for _ in range(reps):
        ix = RNG.integers(0, n, n)
        a, b = r[ix][m[ix]], r[ix][~m[ix]]
        if len(a) >= 3 and len(b) >= 3:
            vals.append(100 * (a.mean() - b.mean()))
    vals = np.array(vals)
    d = 100 * (r[m].mean() - r[~m].mean()) if m.any() and (~m).any() else np.nan
    lo, hi = np.percentile(vals, [2.5, 97.5]) if len(vals) > 50 else (np.nan, np.nan)
    p = max(2 * min((vals <= 0).mean(), (vals >= 0).mean()), 1 / reps) if len(vals) > 50 else np.nan
    return d, lo, hi, p


def red(lab, df, mask, cijena=False):
    m = np.asarray(pd.Series(mask).fillna(False), bool)
    if m.sum() < 3 or (~m).sum() < 3:
        return {"lab": lab, "n": int(m.sum()), "d": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan,
                "h1": np.nan, "h2": np.nan, "e1": np.nan, "e0": np.nan}
    if cijena:
        d, lo, hi, p = boot_cijena(df, m)
        med = df["date"].sort_values().iloc[len(df) // 2]
        f = (df["date"] < med).values
        h = []
        for part in (f, ~f):
            sub, mm = df[part], m[part]
            h.append(100 * (sub["resid"].values[mm].mean() - sub["resid"].values[~mm].mean())
                     if mm.any() and (~mm).any() else np.nan)
        h1, h2 = h
    else:
        d = diff_bw(df, m)
        lo, hi, p = boot(df, m)
        h1, h2 = halves(df, m)
    return {"lab": lab, "n": int(m.sum()), "d": d, "lo": lo, "hi": hi, "p": p, "h1": h1, "h2": h2,
            "e1": e(df[m])[1], "e0": e(df[~m])[1]}


def ispis(rows, smjer=None, holm_p=None):
    for i, r in enumerate(rows):
        hp = f" Holm {holm_p[i]:.2f}" if holm_p is not None else ""
        print(f"  {r['lab']:58s} n={r['n']:4d}  edge {r['e1']:+6.1f} naspram {r['e0']:+6.1f} | razlika {r['d']:+6.1f}pp "
              f"[{r['lo']:+6.1f}, {r['hi']:+6.1f}] P={r['p']:.2f}{hp} | polovice {r['h1']:+5.1f}/{r['h2']:+5.1f}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = pd.read_pickle(os.path.join(DUMP, "base.pkl"))
    d = d[d.p_dev.notna() & d.odds.notna()].copy()
    d["band"] = d["odds"].map(band)
    pen = d["penalties"].fillna("")
    z5 = (d.date >= "2026-10-05") & (d.date <= "2026-11-07")
    W = {"Z5 (05.10.–07.11.)": d[z5].copy(), "UV od 17.08.": d[d.date >= "2026-08-17"].copy(),
         "UV od 30.08.": d[d.date >= "2026-08-30"].copy()}

    print("=" * 140)
    print("K — POSTOJEĆE KAZNE I PRAG (razlika = skupina naspram ostalih pickova u istom pojasu kvote; za autsajdera edge naspram edgea)")
    for wlab in ("Z5 (05.10.–07.11.)", "UV od 17.08."):
        s = W[wlab]
        p_s = s["penalties"].fillna("")
        print(f"\n {wlab}: {len(s)} pickova")
        ispis([red("KZ1 scouting picka Med-Low (kazna −4)", s, (s.scout_p == "Med-Low").values),
               red("KZ2 pick je tržišni autsajder (kazna −5)", s, (s.p_dev < 0.5).values, cijena=True)])
    for wlab in ("Z5 (05.10.–07.11.)", "UV od 30.08."):
        s = W[wlab]
        p_s = s["penalties"].fillna("")
        print(f"\n {wlab}: {len(s)} pickova")
        ispis([red("KZ3 pojas 65–68 prije kazne (kazna −5)", s, p_s.str.contains("conf_band_65_68").values)])
        sub = s[s.conf >= 60]
        ispis([red("KZ4 pouzdanost 60–62,9 naspram 63+", sub, (sub.conf < 63).values)])
    print("\n  Krivulja pouzdanosti PRIJE kazni (od 30.08.; edge u istom pojasu naspram svih ostalih):")
    s = W["UV od 30.08."]
    cr = s.conf_raw.fillna(s.conf)
    for lo_, hi_ in ((0, 60), (60, 63), (63, 65), (65, 68), (68, 72), (72, 101)):
        m = ((cr >= lo_) & (cr < hi_)).values
        r = red(f"   sirova pouzdanost {lo_}–{hi_ - 1}", s, m)
        print(f"  {r['lab']:30s} n={r['n']:4d}  edge {r['e1']:+6.1f}pp | naspram ostalih u istom pojasu {r['d']:+6.1f}pp")
    rr = s[["conf", "resid"]].dropna()
    print(f"  r(pouzdanost, pobjeda − cijena) od 30.08.: {np.corrcoef(rr.conf, rr.resid)[0, 1]:+.3f} (n={len(rr)})")

    print("\n" + "=" * 140)
    print("BOD — BONUSI U BODOVANJU (leg-razina)")
    for wlab in ("Z5 (05.10.–07.11.)", "UV od 17.08."):
        s = W[wlab]
        em = s.conf - 100 / s.odds
        cap = np.where(s.odds >= 2.0, 28.0, 20.0)
        print(f"\n {wlab}: {len(s)} pickova")
        ispis([red("BOD1 'value' (pouzdanost − 100/kvota u 3–20/28pp) — bonus", s, ((em >= 3) & (em <= cap)).values),
               red("BOD2 pouzdanost 72+ — bonus", s, (s.conf >= 72).values)])
        v = s[(em >= 3) & (em <= cap)]
        print(f"    (value pickovi: medijan kvote {v.odds.median():.2f}, ostali {s[~((em >= 3) & (em <= cap))].odds.median():.2f})")

    print("\n" + "=" * 140)
    print("L — 'MAKNUTO IZ MODELA', ponovno na Z5 (05.10.–07.11.)")
    s = W["Z5 (05.10.–07.11.)"].copy()
    raw = {r["id"]: r for r in json.load(open(os.path.join(DUMP, "analyzed_matches.json"), encoding="utf-8"))}
    boards = [npl.compute(npl.rec_from_row(raw[i])).get("znakovi") or [] for i in s["id"]]
    s["pick_dom"] = [("pick_domaci" in b) for b in boards]
    s["prot_dom"] = [("prot_domaci" in b) for b in boards]
    sc = 0.02 if np.nanmedian(pd.concat([s.tf_sv_p, s.tf_sv_o])) < 1.5 else 2.0
    # M7: protivnik je na ovom turniru već izbacio našeg picka (iz naših riješenih pickova prije tog dana)
    allr = W["UV od 17.08."]
    elim = [(r.tournament, r.date, r.opp) for r in allr.itertuples() if r.win == 0]
    s["izbacio"] = [any(t == r.tournament and dd < r.date and o == r.opp for t, dd, o in elim) for r in s.itertuples()]
    tests = [
        ("M1 konsenzus ≥ +1pp iznad SuperSporta", s[s.cons_gap.notna()], lambda x: x.cons_gap >= 1.0),
        ("M2 pick je domaći", s, lambda x: x.pick_dom),
        ("M2b protivnik je domaći", s, lambda x: x.prot_dom),
        ("M3 forma na turniru: pick +servis, oba ≥2 meča", s[(s.tf_n_p >= 2) & (s.tf_n_o >= 2)],
         lambda x: (x.tf_sv_p - x.tf_sv_o) >= sc),
        ("M4 povijest turnira: pick dalje došao (3 god.)", s[s.tbest_p.notna() & s.tbest_o.notna()],
         lambda x: x.tbest_p > x.tbest_o),
        ("M5 tie-break vodstvo picka ≥10pp (oba ≥3 TB)", s[(s.tb_pn >= 3) & (s.tb_on >= 3)],
         lambda x: (x.tb_p - x.tb_o) >= 0.10),
        ("M6 izjednačen servis (< 2,5pp)", s[s.serve_p.notna() & s.serve_o.notna()],
         lambda x: (x.serve_p - x.serve_o).abs() < 2.5),
        ("M7 protivnik nam je već izbacio picka na turniru", s, lambda x: x.izbacio),
        ("M8 pick ≥ 8 ATP pobjeda više u sezoni", s[s.seas_w_p.notna() & s.seas_w_o.notna()],
         lambda x: (x.seas_w_p - x.seas_w_o) >= 8),
    ]
    rows = [red(lab, df_, f(df_).values) for lab, df_, f in tests]
    hp = holm([r["p"] if not np.isnan(r["p"]) else 1.0 for r in rows])
    ispis(rows, holm_p=hp)
    smjer = {"M1": 1, "M2": -1, "M2b": 1, "M3": 1, "M4": 1, "M5": -1, "M6": -1, "M7": -1, "M8": 1}
    print("\n  Presude (KANDIDAT = interval ne prelazi 0 i obje polovice istog predznaka; smjer iz tablice L):")
    for (lab, *_), r in zip(tests, rows):
        k = lab.split()[0]
        ok_ci = (r["lo"] > 0) or (r["hi"] < 0)
        same = np.sign(r["h1"]) == np.sign(r["h2"]) == np.sign(r["d"])
        smjer_ok = np.sign(r["d"]) == smjer[k]
        v = "KANDIDAT" if (ok_ci and same) else "nije potvrđeno"
        print(f"   {lab:52s} -> {v}{'' if smjer_ok or np.isnan(r['d']) else ' (SUPROTAN smjer od stare pretpostavke)'}")


if __name__ == "__main__":
    main()
