# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — naši pickovi: W (vrijeme), R (runde), J (težine), K (scouting),
H (izostavljene varijable), L1/L2 ("nos": profil poraza, autsajderi) (18.10.2026 09:23, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točke W, R, J, K, H, L (09:07). Sve uz kontrolu
cijene (edge = pobjeda − devigirana SuperSport cijena; usporedbe skupina unutar pojasa kvote).
Analize s `elo_suspect` isključene. Samo čita .cache/rev_2026-10-18/*.
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


def pz(g):
    """P-vrijednost za edge ≠ 0 (normalna aproksimacija)."""
    n = len(g)
    if n < 5:
        return 1.0
    e = (g.win - g.p_dev).sum()
    se = math.sqrt((g.p_dev * (1 - g.p_dev)).sum())
    return math.erfc(abs(e / se) / math.sqrt(2)) if se > 0 else 1.0


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
        return f"  {lab:52s} n=  0"
    s = f"  {lab:52s} n={n:3d} {int(g.win.sum()):3d}W  edge {e:+6.1f}pp [{lo:+6.1f}, {hi:+6.1f}]"
    if ref is not None and len(ref):
        s += f" | ostali {e_ci(ref)[1]:+5.1f}pp | razlika u istom pojasu {banded(g, ref):+5.1f}pp"
    return s


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    df = df[df.p_dev.notna() & ~df.elo_suspect].copy()
    hard = df[df.surface == "hard"].copy()
    nv = df[df["sample"] == "NOVO"]
    st = df[df["sample"] == "STARO"]

    # ------------------------------------------------------------------ W: vrijeme
    print("=== W. Vrijeme (otvoreni tereni = nije zaklonjeno; STARO + NOVO)")
    op = df[(df.shielded != True) & df.temp.notna()].copy()  # noqa: E712
    print(f"  otvoreno s vremenom: n={len(op)} (NOVO {int((op['sample']=='NOVO').sum())}, STARO {int((op['sample']=='STARO').sum())})")
    op["d_ace"] = op.ace100_p - op.ace100_o
    op["d_age"] = op.age_p - op.age_o
    W = [
        ("W1 vrućina >=28°C x pick veći server (+2 asa/100)", +1, (op.temp >= 28) & (op.d_ace >= 2)),
        ("W2 vjetar >=20 km/h x pick veći server", -1, (op.wind >= 20) & (op.d_ace >= 2)),
        ("W3 vlaga >=70% x pick stariji 4+ god.", -1, (op.humidity >= 70) & (op.d_age >= 4)),
        ("W4 tlak na tlu <=1005 hPa x pick veći server", +1, (op.press_ground <= 1005) & (op.d_ace >= 2)),
    ]
    pv = []
    for lab, sgn, m in W:
        g = op[m.fillna(False)]
        pv.append(pz(g))
    hp = holm(pv)
    for (lab, sgn, m), h in zip(W, hp):
        g = op[m.fillna(False)]
        n, e, lo, hi = e_ci(g)
        gs, gn = g[g["sample"] == "STARO"], g[g["sample"] == "NOVO"]
        ok = (n >= 40 and abs(e) >= 5 and ((lo > 0) if sgn > 0 else (hi < 0)) and (np.sign(e) == sgn)
              and len(gs) and len(gn) and np.sign(e_ci(gs)[1]) == np.sign(e_ci(gn)[1]) and h < 0.05)
        print(line(lab, g, op[~m.fillna(False)]) + f" | STARO {e_ci(gs)[1]:+.1f} (n={len(gs)}) NOVO {e_ci(gn)[1]:+.1f} (n={len(gn)})"
              f" | Holm {h:.2f} -> {'KANDIDAT' if ok else 'PADA'}")
    print("  glavni učinci (r naspram ishod − cijena):")
    for c in ["temp", "humidity", "press_ground", "wind"]:
        r, p, n, ci = corr(op[c], op.resid)
        r1 = corr(op[op['sample'] == 'STARO'][c], op[op['sample'] == 'STARO'].resid)[0]
        r2 = corr(op[op['sample'] == 'NOVO'][c], op[op['sample'] == 'NOVO'].resid)[0]
        print(f"    {c:13s} r={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] n={n} | STARO {r1:+.3f} NOVO {r2:+.3f}")

    print("\n--- W0 (opis): vrijeme naspram statistike meča (zbroj oba igrača, otvoreno)")
    ms = op[op.pm_ace_rate.notna() & op.pmo_ace_rate.notna()].copy()
    ms["m_ace"] = 0.5 * (ms.pm_ace_rate + ms.pmo_ace_rate)
    ms["m_w1"] = 0.5 * (ms.pm_first_won + ms.pmo_first_won)
    ms["m_w2"] = 0.5 * (ms.pm_second_won + ms.pmo_second_won)
    ms["m_serve"] = 0.5 * (ms.pm_serve_won + ms.pmo_serve_won)
    ms["m_bpconv"] = (ms.pm_bp_won + ms.pmo_bp_won) / (ms.pm_bp_chances + ms.pmo_bp_chances).replace(0, np.nan)
    ms["m_first_in"] = 0.5 * (ms.pm_first_in + ms.pmo_first_in)
    tests, pv = [], []
    for wc in ["temp", "humidity", "press_ground", "wind"]:
        for sc in ["m_ace", "m_w1", "m_w2", "m_serve", "m_bpconv", "m_first_in"]:
            r, p, n, ci = corr(ms[wc], ms[sc])
            tests.append((wc, sc, r, n, ci))
            pv.append(p if not np.isnan(p) else 1.0)
    for (wc, sc, r, n, ci), h in zip(tests, holm(pv)):
        print(f"    {wc:13s} x {sc:10s} r={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] n={n}  Holm P={h:.2f}")

    # ------------------------------------------------------------------ R: runde
    print("\n=== R. Runde od 14.09. (ručne/ispravljene) — edge i kalibracija pouzdanosti")
    s14 = df[(df.date >= "2026-09-14") & (df["round"] != "") & (df.round_source != "cleared_wrong_auto")].copy()
    groups = [("R128+R64", ["R128", "R64"]), ("R32", ["R32"]), ("R16", ["R16"]), ("QF", ["QF"]), ("SF+F", ["SF", "F"])]
    for lab, rr in groups:
        g = s14[s14["round"].isin(rr)]
        n, e, lo, hi = e_ci(g)
        if n == 0:
            continue
        cal = (g.conf - 100 * g.win).mean()
        cal_p = (g.conf - 100 * g.p_dev).mean()
        crit = n >= 40 and e <= -5 and hi < 0
        print(line(lab, g, s14[~s14["round"].isin(rr)]) + f" | pouzdanost−stvarno {cal:+5.1f} | pouzdanost−cijena {cal_p:+5.1f}"
              f" -> {'KANDIDAT (ako i LAB)' if crit else 'ne'}")
    lab_f = pd.read_pickle(os.path.join(os.path.dirname(DUMP), "rev_2026-10-18", "lab3_features.pkl"))
    print("  LAB: favoriti po rundi (edge naspram poštene cijene):")
    for lab, rr in groups:
        g = lab_f[lab_f["round"].isin(rr)]
        if not len(g):
            continue
        fav_p = np.where(g.pf >= 0.5, g.pf, 1 - g.pf)
        fav_w = np.where(g.pf >= 0.5, 1.0, 0.0)
        e = 100 * (fav_w.mean() - fav_p.mean())
        se = 100 * math.sqrt((fav_p * (1 - fav_p)).sum()) / len(g)
        print(f"    {lab:9s} n={len(g):5d} edge favorita {e:+5.1f}pp [{e-1.96*se:+5.1f}, {e+1.96*se:+5.1f}]")

    # ------------------------------------------------------------------ J: težine (hard, od 04.08.)
    print("\n=== J. Kategorije težina — predstavnik naspram ishod − cijena (hard, od 04.08.2026)")
    hv = hard[hard.date >= "2026-08-04"].copy()
    hv["d_sr"] = hv.d_serve + hv.d_ret
    J = [("elo_ranking (ELO podloge)", "d_elo_s"), ("serve_return (servis+povrat)", "d_sr"),
         ("recent_form (forma 10)", "d_f10"), ("recent_form (forma x kvaliteta)", "d_fq"),
         ("surface_style (omjer na podlozi)", "d_srf"), ("fatigue (setovi 7 dana, manje=bolje)", "d_s7"),
         ("tournament_trajectory (najdalja runda 3 g.)", "d_tbest")]
    for lab, c in J:
        x = hv[c] * (-1 if "fatigue" in lab else 1)
        r, p, n, ci = corr(x, hv.resid)
        a = hv[hv.date < "2026-09-14"]
        b = hv[hv.date >= "2026-09-14"]
        ra = corr(a[c] * (-1 if "fatigue" in lab else 1), a.resid)
        rb = corr(b[c] * (-1 if "fatigue" in lab else 1), b.resid)
        up = ra[0] >= 0.10 and rb[0] >= 0.10 and ra[3][0] > 0 and rb[3][0] > 0
        down = ra[0] <= -0.10 and rb[0] <= -0.10
        print(f"  {lab:46s} r={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] n={n} | do 13.09. {ra[0]:+.3f} (n={ra[2]}) | od 14.09. {rb[0]:+.3f} (n={rb[2]})"
              f" -> {'kandidat VIŠE' if up else ('kandidat MANJE' if down else 'nema podloge')}")
    print(f"  spominjanje težina u tekstu analiza (NOVO): {count_weight_mentions(nv)}")

    # ------------------------------------------------------------------ K: scouting
    print("\n=== K. Scouting (razina profila picka i protivnika)")
    for lab, g in (("NOVO", nv), ("ŠANGAJ", nv[nv.shanghai]), ("STARO", st)):
        print(f"  {lab}:")
        for lvl in ["High", "Med-High", "Med", "Med-Low", "Low", None]:
            x = g[g.scout_p.fillna("nema") == (lvl or "nema")]
            if len(x):
                print("  " + line(f"pick {lvl or 'bez profila'}", x))
        for lvl in ["High", "Med-High", "Med", None]:
            x = g[g.scout_o.fillna("nema") == (lvl or "nema")]
            if len(x):
                print("  " + line(f"protivnik {lvl or 'bez profila'}", x))

    # ------------------------------------------------------------------ H: izostavljene varijable na NOVO
    print("\n=== H. Izostavljene varijable — NOVO (od 27.09.), uz kontrolu cijene; izvorni smjer u zagradi")
    nvh = nv.copy()
    # domaći: država turnira iz imena (samo turniri NOVO uzorka: Kina i Japan)
    t_cty = nvh.tournament.str.lower().map(lambda t: "CHN" if any(k in t for k in ("shanghai", "beijing", "china", "chengdu", "hangzhou"))
                                           else ("JPN" if ("tokyo" in t or "japan" in t) else None))
    home = (nvh.nat_p == t_cty) & t_cty.notna()
    H = [
        ("K12 statistika s turnira, oba 3+ meča, pick bolji serve_won (+)", (nvh.tf_n_p >= 3) & (nvh.tf_n_o >= 3) & (nvh.d_tf_sv > 0),
         (nvh.tf_n_p >= 3) & (nvh.tf_n_o >= 3) & (nvh.d_tf_sv < 0), +1),
        ("K12 isto, oba 2+ meča (+)", (nvh.tf_n_p >= 2) & (nvh.tf_n_o >= 2) & (nvh.d_tf_sv > 0),
         (nvh.tf_n_p >= 2) & (nvh.tf_n_o >= 2) & (nvh.d_tf_sv < 0), +1),
        ("K15 pick 8+ ATP pobjeda više u sezoni (+)", nvh.d_seas_w >= 8, nvh.d_seas_w < 8, +1),
        ("K15 pick ima manje ATP pobjeda (-)", nvh.d_seas_w < 0, nvh.d_seas_w >= 0, -1),
        ("K16 QF+ samo pick ima GS polufinale (+)", nvh["round"].isin(["QF", "SF", "F"]) & (nvh.gs_sf_p > 0) & (nvh.gs_sf_o == 0),
         nvh["round"].isin(["QF", "SF", "F"]) & ~((nvh.gs_sf_p > 0) & (nvh.gs_sf_o == 0)), +1),
        ("umor: pick 2+ seta više u 7 dana (-)", nvh.d_s7 >= 2, nvh.d_s7 < 2, -1),
        ("dob: pick stariji 4+ god. (-)", nvh.d_age >= 4, nvh.d_age < 4, -1),
        ("TB: pick vodi u TB zapisu 10pp+ (-)", (nvh.d_tb >= 0.10) & (nvh.tb_pn >= 3) & (nvh.tb_on >= 3), (nvh.d_tb < 0.10), -1),
        ("hold jaz: pick +7pp hold (-)", nvh.d_hold >= 7, nvh.d_hold < 7, -1),
        ("pauza: pick 21+ dan bez meča (-)", nvh.rest_p >= 21, nvh.rest_p < 21, -1),
        ("domaći: pick igra kod kuće (izvorno -)", home, ~home, -1),
        ("vrućina >=28°C (opis)", nvh.temp >= 28, nvh.temp < 28, 0),
        ("vjetar >=20 km/h (opis)", nvh.wind >= 20, nvh.wind < 20, 0),
        ("vlaga >=70% (opis)", nvh.humidity >= 70, nvh.humidity < 70, 0),
    ]
    for lab, a, b, sgn in H:
        ga, gb = nvh[a.fillna(False)], nvh[b.fillna(False)]
        n, e, lo, hi = e_ci(ga)
        back = (sgn != 0 and n >= 30 and abs(e) >= 5 and np.sign(e) == sgn)
        print(line(lab, ga, gb) + f" -> {'ponovni KANDIDAT?' if back else 'ostaje kako je'}")

    # ------------------------------------------------------------------ L: nos
    print("\n=== L2. Naši pickovi koji su tržišni autsajderi")
    for lab, g in (("NOVO", nv), ("STARO", st), ("SVE", df)):
        d = g[g.p_dev < 0.5]
        n, e, lo, hi = e_ci(d)
        roi = 100 * d.roi.mean() if len(d) else np.nan
        print(f"  {lab:6s} autsajderi n={n:3d} pogodak {100*d.win.mean() if n else np.nan:5.1f}% cijena {100*d.p_dev.mean() if n else np.nan:5.1f}%"
              f" edge {e:+6.1f}pp [{lo:+5.1f}, {hi:+5.1f}] ROI {roi:+6.1f}%  (udio pickova {100*n/max(1,len(g)):.1f}%)")

    print("\n=== L1. Profil poraza naspram pobjeda u istom pojasu (NOVO + STARO hard) — opis, Holm")
    feats = [("ELO podloge razlika", "d_elo_s"), ("rang (log omjer)", "d_rank"), ("servis poeni razlika", "d_serve"),
             ("povrat razlika", "d_ret"), ("hold razlika", "d_hold"), ("asovi/100 razlika", "d_ace100"),
             ("1. servis osvojen razlika", "d_w1"), ("2. servis osvojen razlika", "d_w2"), ("forma 10 razlika", "d_f10"),
             ("forma x kvaliteta razlika", "d_fq"), ("omjer na podlozi razlika", "d_srf"), ("setovi 7 dana razlika", "d_s7"),
             ("dani odmora razlika", "d_rest"), ("dob razlika", "d_age"), ("visina razlika", "d_ht"),
             ("ATP pobjede u sezoni razlika", "d_seas_w"), ("najdalja runda na turniru 3 g.", "d_tbest"),
             ("prosj. ELO protivnika (5) razlika", "d_aoe5"), ("pouzdanost − cijena", "d_conf")]
    rows, pv = [], []
    for lab, c in feats:
        r, p, n, ci = corr(hard[c], hard.resid)
        rows.append((lab, r, n, ci))
        pv.append(p if not np.isnan(p) else 1.0)
    for (lab, r, n, ci), h in zip(rows, holm(pv)):
        print(f"  {lab:36s} r(ishod − cijena)={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] n={n}  Holm P={h:.2f}")


def load_texts():
    am = load("analyzed_matches")
    return [str((r.get("full_analysis") or {}).get("analysis") or "") for r in am if str(r.get("match_date")) >= "2026-09-27"]


def count_weight_mentions(nv):
    txt = (nv.analysis.fillna("") + " " + nv.own_read.fillna("") + " " + nv.sec1.fillna("") + " " + nv.sec2.fillna("")).str.lower()
    k = txt.str.contains(r"weight|23%|19%|17%|18%|12%|\(w=|weighted at", regex=True).sum()
    return f"{k} od {len(nv)} analiza spominje težinu/postotak kategorije"


if __name__ == "__main__":
    main()
