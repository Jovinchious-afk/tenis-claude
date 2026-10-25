# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — naši pickovi: A4 (pouzdanost po eri), H2 (pravilo 15), N2 (ritam protiv
odmora), N3 (forma × kvaliteta), G2 (težine po kategoriji, kriterij J iz revizije 18.10.), C4
(gubitni naspram dobitnih uz kontrolu cijene), K18 pobliže, F1 (Nose po ocjeni), runde, noćna
sesija, ponovne analize istog para (25.10.2026 10:36).

Pragovi: revizije/2026-10-25/PRAGOVI_REVIZIJA_2026-10-25.md (10:20 i NAKNADNO 10:32).
Sve uz kontrolu cijene (edge = pobjeda − devigirana SuperSport cijena; usporedbe skupina unutar
pojasa kvote). Analize s `elo_suspect` isključene. Samo čita .cache/rev_2026-10-25/*.
    python revizije/2026-10-25/skripte/r_nasi.py
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, corr, holm, load  # noqa: E402

BANDS = [(1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)]


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
        return f"  {lab:58s} n=  0"
    s = f"  {lab:58s} n={n:3d} {int(g.win.sum()):3d}W  edge {e:+6.1f}pp [{lo:+6.1f}, {hi:+6.1f}]"
    if ref is not None and len(ref):
        s += f" | ostali {e_ci(ref)[1]:+5.1f}pp (n={len(ref)}) | razlika u istom pojasu {banded(g, ref):+5.1f}pp"
    return s


def rline(lab, x, y):
    r, p, n, (lo, hi) = corr(x, y)
    if n < 5 or pd.isna(r):
        return f"  {lab:58s} n={n:3d}  r = -", np.nan, n, (np.nan, np.nan), 1.0
    return f"  {lab:58s} n={n:3d}  r = {r:+.3f} [{lo:+.2f}, {hi:+.2f}]  P={p:.3f}", r, n, (lo, hi), p


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    df = df[df.p_dev.notna() & ~df.elo_suspect].copy()
    df["resid"] = df.win - df.p_dev
    nv = df[df["sample"] == "NOVO"]
    st = df[df["sample"] == "STARO"]
    tj = df[df.tjedan]
    hard = df[(df.surface == "hard") & (df.date >= "2026-08-04")]

    print("=== A4. Pouzdanost nosi li informaciju povrh cijene? r(pouzdanost − cijena, ishod − cijena)")
    for lab, g in (("STARO (prije 27.09.)", st), ("era bccf4742 (NOVO)", nv), ("NOVO do 18.10.", nv[~nv.tjedan]),
                   ("TJEDAN", tj)):
        print(rline(f"{lab} — konačna pouzdanost", g.conf - 100 * g.p_dev, g.resid)[0])
        print(rline(f"{lab} — sirova pouzdanost (prije kazni)", g.conf_raw - 100 * g.p_dev, g.resid)[0])
    print("  --- unutar pojasa: konačna pouzdanost >= 65 naspram < 63 (NOVO)")
    hi_, lo_ = nv[nv.conf >= 65], nv[nv.conf < 63]
    print(line("NOVO pouzdanost >= 65", hi_, lo_))
    hi_, lo_ = st[st.conf >= 65], st[st.conf < 63]
    print(line("STARO pouzdanost >= 65", hi_, lo_))
    print("  --- po pojasu (NOVO): edge pouzdanosti 68+ / 63-68 / <63")
    for lo, hi in BANDS:
        b = nv[(nv.odds >= lo) & (nv.odds < hi)]
        parts = []
        for a_, b_ in ((68, 101), (63, 68), (0, 63)):
            x = b[(b.conf >= a_) & (b.conf < b_)]
            n, e, l_, h_ = e_ci(x)
            parts.append(f"{a_}-{b_}: {e:+5.1f} (n={n})" if n else f"{a_}-{b_}: -")
        print(f"    kvota {lo:.2f}-{hi:.2f}: " + " | ".join(parts))

    print("\n=== H2. Pravilo 15 (pickov omjer na hardu <= 50% ILI protivnikov >= 70%), hard od 04.08.")
    h = hard[hard.srf_p.notna() & hard.srf_o.notna()]
    r15 = h[(h.srf_p <= 0.50) | (h.srf_o >= 0.70)]
    print(line("pravilo 15 vrijedi", r15, h.drop(r15.index)))
    print(line("  samo pick <= 50%", h[h.srf_p <= 0.50], h[h.srf_p > 0.50]))
    print(line("  samo protivnik >= 70%", h[h.srf_o >= 0.70], h[h.srf_o < 0.70]))
    print(line("  od 18.10. (novi podaci)", r15[r15.date >= "2026-10-19"], h[(h.date >= "2026-10-19")].drop(r15.index, errors="ignore")))
    print(line("protivnik ima bolji omjer na podlozi za 8pp+", h[h.srf_o - h.srf_p >= 0.08], h[h.srf_o - h.srf_p < 0.08]))

    print("\n=== N2. Ritam protiv odmora (protivnik 2+ meča u 7 dana, pick 10+ dana odmora) — opis")
    for lab, g in (("NOVO", nv), ("STARO hard", st[st.surface == "hard"]), ("TJEDAN", tj)):
        c = g[(g.m7_o >= 2) & (g.rest_p >= 10)]
        print(line(f"{lab}: protivnik u ritmu, pick odmoran", c, g.drop(c.index)))
        c2 = g[(g.m7_p >= 2) & (g.rest_o >= 10)]
        print(line(f"{lab}: pick u ritmu, protivnik odmoran", c2, g.drop(c2.index)))

    print("\n=== N3. Forma × kvaliteta kao druga potvrda (fq pick − protivnik >= 0,30) — opis")
    for lab, g in (("NOVO", nv), ("STARO hard", st[st.surface == "hard"]), ("TJEDAN", tj)):
        c = g[g.d_fq >= 0.30]
        print(line(f"{lab}: pick bolji po formi × kvaliteti", c, g.drop(c.index)))
    sec3 = tj.sec3.fillna("").str.lower()
    claims = tj[sec3.str.contains("quality-adjusted|quality adjusted") & sec3.str.contains("favou?r", regex=True)]
    print(f"  TJEDAN: odjeljak 3 spominje 'quality-adjusted' i prednost: {len(claims)} od {len(tj)} "
          f"(gubitnih {int((claims.win == 0).sum())} od {int((tj.win == 0).sum())})")

    print("\n=== G2 (kriterij J, revizija 18.10.). Težine hard modela — predstavnik kategorije naspram ostatka, hard od 04.08.")
    hard = hard.copy()
    hard["sr_gap"] = (hard.serve_p - hard.serve_o) + (hard.ret_p - hard.ret_o)
    hard["tml_gap"] = 100 * ((hard.tml_s_p - hard.tml_s_o) + (hard.tml_r_p - hard.tml_r_o))
    cats = [("elo_ranking: ELO jaz na podlozi", "d_elo_s"), ("serve_return: servis + povrat (RapidAPI)", "sr_gap"),
            ("serve_return: servis + povrat (TML 12 mj., od 18.10.)", "tml_gap"),
            ("recent_form: forma 10", "d_f10"), ("recent_form: forma × kvaliteta", "d_fq"),
            ("surface_style: omjer na podlozi", "d_srf"), ("fatigue: manje setova u 7 dana", "neg_s7"),
            ("tournament_trajectory: najdalje ovdje (3 god.)", "d_tbest")]
    hard["neg_s7"] = -hard.d_s7
    h1, h2 = hard[hard.date <= "2026-09-13"], hard[hard.date >= "2026-09-14"]
    print(f"  polovice: do 13.09. n={len(h1)}, od 14.09. n={len(h2)} (h2h nije u snapshotu — ne mjeri se)")
    for lab, col in cats:
        a = rline(f"{lab} | do 13.09.", h1[col], h1.resid)
        b = rline(f"{lab} | od 14.09.", h2[col], h2.resid)
        print(a[0]); print(b[0])
        r1, r2 = a[1], b[1]
        heavier = (not pd.isna(r1) and not pd.isna(r2) and r1 >= 0.10 and r2 >= 0.10 and a[3][0] > 0 and b[3][0] > 0)
        lighter = (not pd.isna(r1) and not pd.isna(r2) and r1 <= -0.10 and r2 <= -0.10)
        print(f"    -> {'VEĆA TEŽINA (kandidat)' if heavier else ('MANJA TEŽINA (kandidat)' if lighter else 'nema podloge za promjenu')}")

    print("\n=== C4. Gubitni naspram dobitnih: r(varijabla pick − protivnik, ishod − cijena), Holm po uzorku")
    df["sr_gap"] = (df.serve_p - df.serve_o) + (df.ret_p - df.ret_o)
    df["tml_gap"] = 100 * ((df.tml_s_p - df.tml_s_o) + (df.tml_r_p - df.tml_r_o))
    df["rest_gap"] = df.rest_p - df.rest_o
    df["m7_gap"] = df.m7_p - df.m7_o
    df["nose_gap"] = df.nose_p_own - df.p_dev
    df["tf_gap"] = df.tf_sv_p - df.tf_sv_o
    vars_ = [("ELO jaz na podlozi", "d_elo_s"), ("rang (log, + = pick bolji)", "d_rank"), ("forma 10", "d_f10"),
             ("forma × kvaliteta", "d_fq"), ("servis + povrat RapidAPI", "sr_gap"), ("servis + povrat TML 12 mj.", "tml_gap"),
             ("hold TML 12 mj.", "d_tml_hold"), ("omjer na podlozi", "d_srf"), ("odmor (dana)", "rest_gap"),
             ("mečeva u 7 dana", "m7_gap"), ("dob", "d_age"), ("visina", "d_ht"), ("servis na ovom turniru", "tf_gap"),
             ("Nose vlastita − cijena", "nose_gap"), ("Intuicija prior", "int_prior")]
    for lab_s, g in (("TJEDAN", df[df.tjedan]), ("NOVO", df[df["sample"] == "NOVO"])):
        print(f"  --- {lab_s} (n={len(g)})")
        res = [rline(lab, g[col], g.win - g.p_dev) for lab, col in vars_]
        hp = holm([x[4] for x in res])
        for (txt, *_), h_ in zip(res, hp):
            print(f"{txt}  Holm {h_:.2f}")

    print("\n=== K18 pobliže: hard ATP 250 od 27.09.")
    # ISPRAVAK 25.10.2026 11:16 (skeptik): sort samo po datumu nije stabilan — "prvih 30" je
    # proizvoljno sjeklo 20.10. Sada prirodni poredak (datum, vrijeme upisa analize); uz to se
    # ispisuju i druga dva poretka, jer o poretku ovisi presuda.
    k18 = df[(df.surface == "hard") & (df.level.astype(str).str.contains("250")) & (df.date >= "2026-09-27")].sort_values(["date", "created"], kind="mergesort")
    print(line("svi", k18))
    print(line("prvih 30 po datumu (kad je prag dosegnut)", k18.head(30)))
    print(line("  isto, poredak (datum, turnir, pick)", k18.sort_values(["date", "tournament", "pick"], kind="mergesort").head(30)))
    print(line("  isto, poredak po vremenu upisa analize", k18.sort_values("created", kind="mergesort").head(30)))
    print(line("bez TJEDNA (27.09.-18.10.)", k18[~k18.tjedan]))
    print(line("pouzdanost >= 63 (smiju na tiket)", k18[k18.conf >= 63], k18[k18.conf < 63]))
    print(line("noge stvarnih tiketa", k18[k18.on_ticket]))
    for t_, g in k18.groupby("tournament"):
        print(line(f"  {str(t_)[:40]}", g))
    o250 = df[(df.surface == "hard") & (df.date >= "2026-09-27") & ~df.level.astype(str).str.contains("250")]
    print(line("usporedba: hard 500/1000 od 27.09.", o250))
    print(line("razlika 250 naspram 500/1000 u istom pojasu", k18, o250))

    print("\n=== F1. Nose (nose-v1) po ocjeni — TJEDAN (= sve od 19.10.)")
    g = df[df.tjedan & df.nose_suit.notna()]
    for s_ in ("UKLJUČI", "UZ UPOZORENJE", "IZBJEGAVAJ"):
        x = g[g.nose_suit == s_]
        print(line(f"Nose {s_}", x, g.drop(x.index)))
    print("  --- Nose vlastita − cijena po tercilama (TJEDAN)")
    q = g.nose_gap if "nose_gap" in g else (g.nose_p_own - g.p_dev)
    q = g.nose_p_own - g.p_dev
    t1, t2 = q.quantile([1 / 3, 2 / 3])
    for lab, m in (("niska (Nose ispod cijene)", q <= t1), ("srednja", (q > t1) & (q <= t2)), ("visoka (Nose iznad cijene)", q > t2)):
        print(line(f"  {lab}", g[m]))
    print("  --- zastavice mina (TJEDAN): koliko puta i kako su prošli pickovi s njima")
    for fl in ("M1", "M2", "M3", "M4", "M5"):
        x = g[g.nose_mines.fillna("").str.contains(fl)]
        if len(x):
            print(line(f"  mina {fl}", x, g.drop(x.index)))
    print("  --- Nose na karijeri (usporedna varijanta) naspram TML ulaza: r(vlastita − cijena, ostatak)")
    print(rline("  nose (TML 12 mj.)", g.nose_p_own - g.p_dev, g.resid)[0])
    print(rline("  nose_karijera", g.nosek_p_own - g.p_dev, g.resid)[0])

    print("\n=== Runde (NOVO) i prvo kolo")
    for rd in ["R128", "R64", "R32", "R16", "QF", "SF", "F"]:
        x = nv[nv["round"] == rd]
        if len(x):
            print(line(rd, x))
    first = nv[((nv["round"] == "R32") & nv.level.astype(str).str.contains("250|500")) |
               ((nv["round"] == "R128") & nv.level.astype(str).str.contains("1000|Grand"))]
    print(line("prvo kolo (R32 na 250/500, R128 na Mastersu)", first, nv.drop(first.index)))

    print("\n=== Noćna sesija (od 05.10.2026)")
    ns = df[(df.session == "night") & (df.date >= "2026-10-05")]
    ds = df[(df.session == "day") & (df.date >= "2026-10-05")]
    print(line("noć od 05.10.", ns, ds))
    print(line("noć sve (svi podaci)", df[df.session == "night"], df[df.session == "day"]))

    print("\n=== Ponovne analize istog para: noga tiketa naspram zadnje analize")
    legs = df[df.on_ticket & (df.date >= "2026-09-27")]
    diff = legs[(legs.leg_conf.notna()) & ((legs.leg_conf - legs.conf).abs() >= 1)]
    print(f"  noge od 27.09.: {len(legs)}; s različitom pouzdanošću na tiketu i u bazi: {len(diff)}")
    for _, r in diff.iterrows():
        print(f"    {r.date:%d.%m.} {r.pick} — tiket {r.leg_conf:.0f} @ {r.leg_odds:.2f}, baza {r.conf:.0f} @ {r.odds:.2f}, ishod {'W' if r.win else 'L'}")


if __name__ == "__main__":
    main()
