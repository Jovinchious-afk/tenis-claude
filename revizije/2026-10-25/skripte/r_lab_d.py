# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — LAB: korisnikova ideja 1 ("koliko je daleko došao na zadnja 3 turnira",
D1, D3–D7, opis D2) i "ritam protiv odmora" (N1a–N1c) naspram poštene cijene (25.10.2026 10:34).

Pragovi i definicije: revizije/2026-10-25/PRAGOVI_REVIZIJA_2026-10-25.md, točka D (10:20) i
NAKNADNO (10:32). Holm posebno u obitelji D (6 testova) i N (3 testa); uz to ispis kako bi P stajao
uz Holm na svih 88 testova na istom povijesnom uzorku (79 ranijih + 9 današnjih).

Podaci: povijesni laboratorij (.cache/lab/td_joined.pkl + tml.pkl; tennis-data + TML, ATP
2022 – 06.10.2026, poštena cijena = Pinnacle bez marže, inače prosjek kladionica).
Povijest igrača i zaštita od curenja preuzete su iz revizije 18.10. (`r_lab3.build_history`,
`Profiles`): u obzir ulaze SAMO zapisi s datumom strogo prije datuma ovog meča; aktualni turnir je
isključen iz "zadnja 3 turnira".

Samo čita. Izlaz: ispis + .cache/rev_2026-10-25/lab_d_rezultati.json
    python revizije/2026-10-25/skripte/r_lab_d.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
from r_lab3 import (F_DATE, F_LVL, F_RORD, F_SRC, F_TID, F_TS, F_WON, LAB, Profiles,  # noqa: E402
                    build_history, stats)

OUTD = os.path.join(ROOT, ".cache", "rev_2026-10-25")
TOUR_LEVELS = {"G", "M", "250", "500", "A", "F", "O"}   # glavni ždrijeb ATP razine, bez Davis Cupa (D)
WINDOW_DAYS = 120
N_PRIOR_TESTS = 79                                     # isti povijesni uzorak: 27.09. + 04.10. + 18.10.


def last_tournaments(recs, j, any_level=False, k=3):
    """Zadnjih k turnira prije zapisa j (bez aktualnog): [(pobjede, najdalja runda)], najnoviji prvi."""
    me = recs[j]
    d0, tid0 = me[F_DATE], me[F_TID]
    lo = d0 - pd.Timedelta(days=WINDOW_DAYS)
    order, info = [], {}
    for x in reversed(recs[:j]):
        if x[F_DATE] >= d0 or x[F_TID] == tid0:
            continue
        if x[F_TS] < lo:
            break
        if x[F_SRC] == "main" and x[F_LVL] in TOUR_LEVELS:
            pass
        elif any_level and x[F_SRC] == "ch":
            pass
        else:
            continue
        t = x[F_TID]
        if t not in info:
            if len(order) == k:
                continue      # stariji zapisi istih k turnira se i dalje zbrajaju (ne smije se prekinuti)
            order.append(t)
            info[t] = [0, 0]
        w = int(x[F_WON])
        info[t][0] += w
        rd = int(x[F_RORD]) + (1 if (int(x[F_RORD]) == 7 and w) else 0)   # osvojen naslov = 8
        info[t][1] = max(info[t][1], rd)
    return [tuple(info[t]) for t in order]


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact)
    P = Profiles(hist)
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    print(f"igrača u povijesti: {len(hist)} | LAB mečeva: {len(td)}")

    rows = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        row = {"pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"], "date": m["Date"]}
        ok = True
        for side, pid in (("w", r["winner_id"]), ("l", r["loser_id"])):
            j = P.pos.get((pid, int(m["tml_idx"])))
            if j is None:
                ok = False
                break
            recs = hist[pid]
            me = recs[j]
            d0 = me[F_DATE]
            lt = last_tournaments(recs, j)
            la = last_tournaments(recs, j, any_level=True)
            row[f"n3_{side}"] = len(lt)
            row[f"avg_{side}"] = np.mean([w for w, _ in lt]) if len(lt) == 3 else np.nan
            row[f"zero3_{side}"] = (len(lt) == 3 and all(w == 0 for w, _ in lt))
            row[f"sf_{side}"] = (len(lt) == 3 and any(rd >= 6 for _, rd in lt))
            row[f"noqf_{side}"] = (len(lt) == 3 and all(rd <= 4 for _, rd in lt))
            row[f"avgall_{side}"] = np.mean([w for w, _ in la]) if len(la) == 3 else np.nan
            prev = [x for x in recs[max(0, j - 30):j] if x[F_DATE] < d0]
            l10 = prev[-10:]
            row[f"f10_{side}"] = (sum(x[F_WON] for x in l10) / len(l10)) if len(l10) >= 5 else np.nan
            row[f"m7_{side}"] = sum(1 for x in prev if (d0 - x[F_DATE]).days <= 7)
            row[f"m10_{side}"] = sum(1 for x in prev if (d0 - x[F_DATE]).days <= 10)
            same_q = any(x[F_TID] == me[F_TID] and x[F_SRC] == "q" for x in prev)
            first_main = not any(x[F_TID] == me[F_TID] and x[F_SRC] == "main" for x in prev)
            row[f"qual_{side}"] = bool(same_q and first_main and me[F_SRC] == "main")
        if ok:
            rows.append(row)
    f = pd.DataFrame(rows)
    print(f"mečeva s cijenom i obje strane: {len(f)} | oba s 3 turnira ATP razine u {WINDOW_DAYS} dana: "
          f"{int(((f.n3_w == 3) & (f.n3_l == 3)).sum())}")

    pf_arr, half_arr = f["pf"].values, f["half"].values

    def oriented(mw, ml):
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    aw, al = f["avg_w"], f["avg_l"]
    both3 = (f.n3_w == 3) & (f.n3_l == 3)
    dog_w = (f.pf >= 0.30) & (f.pf < 0.50)
    dog_l = (f.pf > 0.50) & (f.pf <= 0.70)
    fav_w, fav_l = f.pf >= 0.5, f.pf < 0.5
    f10close = (f.f10_w - f.f10_l).abs() <= 0.10
    aall_w, aall_l = f["avgall_w"], f["avgall_l"]
    tests_d = [
        ("D1 prosjek pobjeda zadnja 3 turnira +1,0 (PRIMARNI)", +1,
         ((aw - al >= 1.0) & both3).values, ((al - aw >= 1.0) & both3).values),
        ("D3 vruć: SF+ na zadnja 3, protivnik bez QF", +1,
         (f.sf_w & f.noqf_l).values, (f.sf_l & f.noqf_w).values),
        ("D4 hladan favorit: 0 pobjeda na sva 3 (mina)", -1,
         (f.zero3_w & fav_w & (al >= 1.0)).values, (f.zero3_l & fav_l & (aw >= 1.0)).values),
        ("D5 vruć autsajder (0,30-0,50), +1,0", +1,
         ((aw - al >= 1.0) & both3 & dog_w).values, ((al - aw >= 1.0) & both3 & dog_l).values),
        ("D6 sve razine (i Challengeri), +1,0", +1,
         ((aall_w - aall_l >= 1.0)).fillna(False).values, ((aall_l - aall_w >= 1.0)).fillna(False).values),
        ("D7 kao D1, forma 10 slična (|razlika| <= 0,10)", +1,
         ((aw - al >= 1.0) & both3 & f10close).values, ((al - aw >= 1.0) & both3 & f10close).values),
    ]
    rhythm_w = (f.m7_w >= 2) & (f.m10_l == 0)
    rhythm_l = (f.m7_l >= 2) & (f.m10_w == 0)
    tests_n = [
        ("N1a ritam (2+ meča u 7 d) protiv odmora (0 u 10 d)", +1, rhythm_w.values, rhythm_l.values),
        ("N1b kvalifikant u ritmu, prvi meč glavnog ždrijeba", +1,
         (rhythm_w & f.qual_w).values, (rhythm_l & f.qual_l).values),
        ("N1c ritam protiv odmora, autsajder 0,30-0,50", +1, (rhythm_w & dog_w).values, (rhythm_l & dog_l).values),
    ]

    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values

    def bandof(pA):
        return "jak fav" if pA >= 0.70 else ("fav" if pA >= 0.5 else ("autsajder" if pA >= 0.30 else "veliki autsajder"))

    def run(tests):
        res, pvals = {}, []
        for name, sign, mw, ml in tests:
            rows_ = oriented(np.asarray(mw, bool), np.asarray(ml, bool))
            a = stats(rows_)
            res[name] = {"sign": sign, "all": a,
                         "P1": stats([x for x in rows_ if x[2] == "P1"]), "P2": stats([x for x in rows_ if x[2] == "P2"]),
                         "lvl": {g: stats([x for x in rows_ if lv[x[3]] == g]) for g in ("GS+M", "500", "250")},
                         "rnd": {g: stats([x for x in rows_ if (early[x[3]] if g == "rano" else not early[x[3]])]) for g in ("rano", "kasno")},
                         "band": {g: stats([x for x in rows_ if bandof(x[1]) == g]) for g in ("jak fav", "fav", "autsajder", "veliki autsajder")},
                         "raw_win": float(np.mean([x[0] for x in rows_])) if rows_ else float("nan"),
                         "raw_fav": float(np.mean([1.0 if x[1] >= 0.5 else 0.0 for x in rows_])) if rows_ else float("nan")}
            pvals.append(a.get("p", 1.0) if a.get("n") else 1.0)
        order = sorted(range(len(pvals)), key=lambda q: pvals[q])
        holm, run_ = [None] * len(pvals), 0.0
        for k, q in enumerate(order):
            run_ = max(run_, min(1.0, (len(pvals) - k) * pvals[q]))
            holm[q] = run_
        for (name, *_), hp, pv in zip(tests, holm, pvals):
            res[name]["holm"] = hp
            res[name]["p_raw"] = pv
            res[name]["bonf_88"] = min(1.0, pv * (N_PRIOR_TESTS + 9))
        return res

    def verdict(r):
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if a.get("n", 0) < 30 or p1.get("n", 0) < 10 or p2.get("n", 0) < 10:
            return "PREMALO"
        sgn = r["sign"]
        same = (a["edge"] > 0) == (sgn > 0)
        ci = (a["lo"] > 0) if sgn > 0 else (a["hi"] < 0)
        halves = (p1["edge"] > 0) == (p2["edge"] > 0) == (a["edge"] > 0)

        def stable(groups, need):
            okg = [g for g in groups.values() if g.get("n", 0) >= 50]
            if not okg:
                return True
            k = sum(1 for g in okg if (g["edge"] > 0) == (a["edge"] > 0))
            return k >= min(need, len(okg))
        stab = stable(r["lvl"], 2) and stable(r["rnd"], 2) and stable(r["band"], 3)
        if same and ci and halves and abs(a["edge"]) >= 2 and r["holm"] < 0.05 and stab:
            return "PROLAZI"
        if same and ci and halves:
            return "SLAB" + ("" if stab else " (nestabilno)")
        return "PADA"

    out = {}
    for fam, tests in (("D", tests_d), ("N", tests_n)):
        res = run(tests)
        print("\n" + "=" * 150)
        print(f"OBITELJ {fam}: {'test':56s} smjer   n      edge   [95% interval]    P1 / P2      Holm  (P×88)  pobjeđuje  favorit  presuda")
        for name, sign, *_ in tests:
            r = res[name]
            r["verdict"] = verdict(r)
            a, p1, p2 = r["all"], r["P1"], r["P2"]
            if not a.get("n"):
                print(f"  {name:62s} n=0")
                continue
            print(f"  {name:62s} {'+' if sign > 0 else '-'}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
                  f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}   {r['holm']:5.2f}  ({r['bonf_88']:4.2f})"
                  f"   {100*r['raw_win']:5.1f}%   {100*r['raw_fav']:5.1f}%   {r['verdict']}")
        for name, *_ in tests:
            r = res[name]
            fmt = lambda d: " ".join(f"{k}:{v.get('edge', float('nan')):+.1f}(n={v.get('n', 0)})" for k, v in d.items())
            print(f"     {name[:40]:40s} razina {fmt(r['lvl'])} | runda {fmt(r['rnd'])}\n{'':46s} pojas {fmt(r['band'])}")
        out[fam] = res

    # D2 (opis): tercile razlike prosjeka (oba s 3 turnira) — strana s većim prosjekom
    g = (aw - al)[both3]
    a_ = g[g != 0].abs()
    if len(a_) > 30:
        q1, q2 = a_.quantile([1 / 3, 2 / 3])
        parts = []
        for lo_, hi_ in [(0, q1), (q1, q2), (q2, 99)]:
            sel = both3 & ((aw - al).abs() > lo_) & ((aw - al).abs() <= hi_)
            st_ = stats(oriented((sel & (aw > al)).values, (sel & (al > aw)).values))
            parts.append(f"{st_['edge']:+5.1f}pp [{st_['lo']:+.1f}, {st_['hi']:+.1f}] (n={st_['n']}, razlika do {hi_:.2f})")
        print("\nD2 (opis) tercile razlike prosjeka pobjeda (mala / srednja / velika):\n   " + "\n   ".join(parts))
    # kontinuirano: r(razlika, ishod − cijena) iz perspektive pobjednika i poraženog (simetrično)
    xs, ys = [], []
    for k in range(len(f)):
        if both3.iat[k]:
            d = aw.iat[k] - al.iat[k]
            xs += [d, -d]
            ys += [1 - f.pf.iat[k], -(1 - f.pf.iat[k])]
    if xs:
        r_ = float(np.corrcoef(xs, ys)[0, 1])
        n_ = len(xs) // 2
        print(f"D2 (opis) r(razlika prosjeka, ishod − cijena) = {r_:+.3f} na {n_} mečeva (simetrično, svaka strana jednom)")

    with open(os.path.join(OUTD, "lab_d_rezultati.json"), "w", encoding="utf-8") as fo:
        json.dump(out, fo, indent=1, default=float)


if __name__ == "__main__":
    main()
