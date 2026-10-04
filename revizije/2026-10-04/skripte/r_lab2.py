# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — dodatak 2: korisnikovi prijedlozi u povijesnom labu (04.10.2026 19:07).

TWL1-3: omjer pobjeda NA OVOM turniru u prethodne 3 sezone (korisnikova tablica "top 200 x
turniri"), i "višak na turniru" (omjer ondje minus opći omjer u istim godinama).
QF1-2: favorit u QF/SF/F protiv igrača s boljim holdom / više asova (korisnikova ideja o
četvrtfinalima); QF0 je kontrola u ranim rundama.
Pragovi: revizije/2026-10-04/PRAGOVI_DODATAK_2.md (zapisani 19:07, prije računanja).
Samo čita .cache/lab/*.pkl i .cache/rev_2026-10-04/lab_features_r.pkl (iz r_lab.py).
"""
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_lab import stats, test, verdict, fmt, LAB, ROOT  # noqa: E402


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    feat = pd.read_pickle(os.path.join(ROOT, ".cache", "rev_2026-10-04", "lab_features_r.pkl"))
    assert len(feat) == len(td), (len(feat), len(td))
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)

    # igrač -> godina -> [pobjede, porazi] (glavni + kvalifikacije) i (igrač, turnir, godina) -> [w, l]
    tour = tml[tml["src"].isin(["main", "q"])]
    yr = tour["t_start"].dt.year
    allwl = defaultdict(lambda: [0, 0])
    twl = defaultdict(lambda: [0, 0])
    for w, l, tn, y in zip(tour["winner_id"], tour["loser_id"], tour["tname"], yr):
        allwl[(w, y)][0] += 1
        allwl[(l, y)][1] += 1
        twl[(w, tn, y)][0] += 1
        twl[(l, tn, y)][1] += 1

    def hist(pid, tn, y):
        tw = tl = aw = al = 0
        for yy in (y - 3, y - 2, y - 1):
            a = twl.get((pid, tn, yy))
            if a:
                tw += a[0]
                tl += a[1]
            b = allwl.get((pid, yy))
            if b:
                aw += b[0]
                al += b[1]
        return tw, tl, aw, al

    rows = []
    for i in range(len(td)):
        r = t.iloc[i]
        y, tn = r["t_start"].year, r["tname"]
        hw = hist(r["winner_id"], tn, y)
        hl = hist(r["loser_id"], tn, y)
        rows.append(hw + hl)
    h = pd.DataFrame(rows, columns=["tw_w", "tl_w", "aw_w", "al_w", "tw_l", "tl_l", "aw_l", "al_l"])
    f = pd.concat([feat.reset_index(drop=True), h], axis=1)
    f["tn_w"], f["tn_l"] = f.tw_w + f.tl_w, f.tw_l + f.tl_l
    f["trate_w"] = np.where(f.tn_w >= 3, f.tw_w / f.tn_w.replace(0, np.nan), np.nan)
    f["trate_l"] = np.where(f.tn_l >= 3, f.tw_l / f.tn_l.replace(0, np.nan), np.nan)
    f["arate_w"] = f.aw_w / (f.aw_w + f.al_w).replace(0, np.nan)
    f["arate_l"] = f.aw_l / (f.aw_l + f.al_l).replace(0, np.nan)
    f["exc_w"] = f.trate_w - f.arate_w
    f["exc_l"] = f.trate_l - f.arate_l
    print(f"mečeva: {len(f)} | oba s >=3 meča na turniru u 3 sezone: {(f.trate_w.notna() & f.trate_l.notna()).sum()}")

    # --od=GGGG-MM-DD (04.10.2026 19:36): buduca NEOVISNA provjera K21 na mecevima nakon datuma
    # (npr. --od=2026-09-14 kad se osvjezi .cache/tennis-data/2026.xlsx). Polovice su tada
    # prva i druga polovica NOVOG razdoblja, ne 2022-23 / 2024-26.
    f["Date"] = td["Date"].values
    od = next((x.split("=", 1)[1] for x in sys.argv if x.startswith("--od=")), None)
    if od:
        f = f[f["Date"] >= pd.Timestamp(od)].reset_index(drop=True)
        f["half"] = np.where(f["Date"] <= f["Date"].median(), "P1", "P2")
        print(f"SAMO mečevi od {od}: {len(f)} (polovice = prva/druga polovica tog razdoblja)")

    def oriented(mw, ml):
        out = []
        for aw, al, pf, hf in zip(mw, ml, f["pf"], f["half"]):
            if aw:
                out.append((1, pf, hf))
            elif al:
                out.append((0, 1 - pf, hf))
        return out

    both = f.trate_w.notna() & f.trate_l.notna()
    dog_w, dog_l = f["pf"] < 0.5, (1 - f["pf"]) < 0.5
    late = f["round"].isin(["QF", "SF", "F"])
    early = f["round"].isin(["R128", "R64", "R32"])
    fav_w, fav_l = f["pf"] > 0.5, f["pf"] < 0.5
    hold_ok = f.hold_w.notna() & f.hold_l.notna()
    ace_ok = f.ace_w.notna() & f.ace_l.notna()
    # favorit je "ugrožen" kad protivnik ima bolji hold / više asova
    hold_threat_w = hold_ok & (f.hold_l - f.hold_w >= 0.03)   # pobjednik je favorit, poraženi jači hold
    hold_threat_l = hold_ok & (f.hold_w - f.hold_l >= 0.03)
    ace_threat_w = ace_ok & (f.ace_l - f.ace_w >= 0.02)
    ace_threat_l = ace_ok & (f.ace_w - f.ace_l >= 0.02)

    tests = [
        ("TWL1 bolji omjer na turniru (3 sez.)", +1, (both & (f.trate_w > f.trate_l), both & (f.trate_l > f.trate_w))),
        ("TWL2 veći višak na turniru", +1, (both & (f.exc_w > f.exc_l), both & (f.exc_l > f.exc_w))),
        ("TWL3 višak +15pp, autsajder", +1, (both & (f.exc_w - f.exc_l >= 0.15) & dog_w,
                                            both & (f.exc_l - f.exc_w >= 0.15) & dog_l)),
        ("QF1 favorit QF+ vs bolji hold (+3pp)", -1, (late & fav_w & hold_threat_w, late & fav_l & hold_threat_l)),
        ("QF2 favorit QF+ vs više asova (+2/100)", -1, (late & fav_w & ace_threat_w, late & fav_l & ace_threat_l)),
    ]
    pv, res = [], {}
    for name, sign, (mw, ml) in tests:
        tt = test(oriented(mw, ml))
        res[name] = (sign, tt, verdict(tt, sign))
        pv.append(tt["all"].get("p", 1.0) if tt["all"].get("n") else 1.0)
    order = sorted(range(len(pv)), key=lambda i: pv[i])
    holm, run = [None] * len(pv), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(pv) - k) * pv[i]))
        holm[i] = run
    print("=" * 118)
    for (name, sign, _), hp in zip(tests, holm):
        s_, tt, v = res[name]
        print(f"{name:40s} smjer {'+' if sign > 0 else '-'}  {fmt(tt)}  Holm P={hp:.2f}  -> {v}")

    # K21 = JEDNO spojeno pravilo (skeptik 04.10.2026): protivnik jaci u holdu ILI u asovima.
    # Prag za NEOVISNU potvrdu (DI K21): edge <= -4pp, 95% interval ispod nule, obje polovice < 0.
    k21 = test(oriented(late & fav_w & (hold_threat_w | ace_threat_w), late & fav_l & (hold_threat_l | ace_threat_l)))
    a21 = k21["all"]
    ok21 = (a21.get("n", 0) >= 30 and a21["edge"] <= -4 and a21["hi"] < 0
            and k21["P1"].get("edge", 0) < 0 and k21["P2"].get("edge", 0) < 0)
    print(f"\nK21 spojeno (favorit QF/SF/F, protivnik +3pp hold ILI +2 asa/100): {fmt(k21)}"
          f"  -> {'PROLAZI prag K21' if ok21 else 'ne prolazi prag K21'}")

    print("\nKontrole i opis (bez praga):")
    for name, (mw, ml) in [
        ("QF0 favorit RANE runde vs bolji hold", (early & fav_w & hold_threat_w, early & fav_l & hold_threat_l)),
        ("QF0 favorit RANE runde vs više asova", (early & fav_w & ace_threat_w, early & fav_l & ace_threat_l)),
        ("svi favoriti u QF/SF/F", (late & fav_w, late & fav_l)),
        ("favorit QF+ BEZ prijetnje (hold i asovi slabiji)", (late & fav_w & hold_ok & ~hold_threat_w & ace_ok & ~ace_threat_w,
                                                            late & fav_l & hold_ok & ~hold_threat_l & ace_ok & ~ace_threat_l)),
    ]:
        print(f"  {name:48s} {fmt(test(oriented(mw, ml)))}")
    # TWL1 tercile razlike omjera na turniru (monotonost)
    g = (f.trate_w - f.trate_l)
    ok = both & (g != 0)
    a = g[ok].abs()
    q1, q2 = a.quantile([1 / 3, 2 / 3])
    parts = []
    for lo_, hi_ in [(0, q1), (q1, q2), (q2, 9)]:
        sel = ok & (g.abs() > lo_) & (g.abs() <= hi_)
        st = stats(oriented(sel & (g > 0), sel & (g < 0)))
        parts.append(f"{st['edge']:+5.1f} (n={st['n']})")
    print("  TWL1 tercile razlike (mala/srednja/velika):", " | ".join(parts))
    # koliko podataka ima korisnikova tablica po igraču (za igrača-specifičnu QF ideju)
    lq = tml[(tml["src"] == "main") & tml["round"].isin(["QF"]) & (tml["t_start"].dt.year >= 2023)]
    per = pd.concat([lq["winner_id"], lq["loser_id"]]).value_counts()
    print(f"\nČetvrtfinala po igraču 2023-2026 (glavni ždrijeb): medijan {per.median():.0f}, 90. percentil {per.quantile(0.9):.0f}, "
          f"najviše {per.max()} | igrača s 10+ QF: {(per >= 10).sum()}")


if __name__ == "__main__":
    main()
