# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — LAB: umor (U1–U7), H2H (H1–H3), runda × autsajder (D1–D14) naspram poštene
cijene (08.11.2026 11:40).

Pragovi i definicije: revizije/2026-11-08/PRAGOVI_REVIZIJA_2026-11-08.md (08.11.2026 11:27), točke B, C, D.
Presuda kao revizija 25.10.2026 (`r_lab_d.verdict`): PROLAZI / SLAB / PADA; "ODBAČENO" samo uz pola
širine intervala ≤ 4pp. Holm unutar obitelji; uz to P × (109 + 24) za sve testove na istom uzorku.

Podaci: povijesni laboratorij (.cache/lab/td_joined.pkl + tml.pkl; tennis-data + TML, ATP 2022 –
06.10.2026, poštena cijena = Pinnacle bez marže, inače prosjek kladionica).
ZAŠTITA OD CURENJA: za svaki meč samo zapisi igrača s datumom STROGO prije datuma meča; niz tjedana,
turniri u 45 dana i H2H ne broje aktualni turnir; datum = točan datum iz tennis-data gdje postoji,
inače TML-ov približni datum.

Samo čita. Izlaz: ispis (u .cache/rev_2026-11-08/out_lab.txt) + lab_rezultati.json
    python revizije/2026-11-08/skripte/r_lab.py > .cache/rev_2026-11-08/out_lab.txt
"""
import json
import math
import os
from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LAB = os.path.join(ROOT, ".cache", "lab")
OUTD = os.path.join(ROOT, ".cache", "rev_2026-11-08")
N_PRIOR = 109
N_TODAY = 24


def stats(rows):
    if not rows:
        return {"n": 0}
    won = np.array([r[0] for r in rows], float)
    p = np.array([r[1] for r in rows], float)
    res = won - p
    n = len(res)
    m = res.mean()
    se = res.std(ddof=1) / math.sqrt(n) if n > 1 else float("nan")
    z = m / se if se and se > 0 else 0.0
    return {"n": n, "edge": 100 * m, "lo": 100 * (m - 1.96 * se), "hi": 100 * (m + 1.96 * se),
            "p": math.erfc(abs(z) / math.sqrt(2))}


def monday(ts):
    return (ts - pd.Timedelta(days=ts.weekday())).normalize()


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], pd.to_datetime(td["Date"])))

    # ---------------------------------------------------------------- povijest igrača
    recs = defaultdict(list)   # pid -> [(datum, t_start, tid, src, opp, won, opp_rank)]
    for idx, r in zip(tml.index, tml.itertuples(index=False)):
        d = exact.get(idx, pd.Timestamp(r.approx_date))
        ts = pd.Timestamp(r.t_start) if not pd.isna(r.t_start) else d
        for pid, opp, won, orank in ((r.winner_id, r.loser_id, 1, r.loser_rank), (r.loser_id, r.winner_id, 0, r.winner_rank)):
            if pd.isna(pid):
                continue
            recs[pid].append((d, ts, r.tourney_id, r.src, opp, won, orank))
    dates = {}
    for pid in recs:
        recs[pid].sort(key=lambda x: (x[0], x[1]))
        dates[pid] = [x[0] for x in recs[pid]]
    print(f"igrača u povijesti: {len(recs)}")

    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    rows = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        d0 = pd.Timestamp(m["Date"])
        s0 = pd.Timestamp(r["t_start"]) if not pd.isna(r["t_start"]) else d0
        tid0 = r["tourney_id"]
        w0 = monday(s0)
        row = {"pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"], "date": d0}
        ok = True
        for side, pid, opp, age, rank in (("w", r["winner_id"], r["loser_id"], r["winner_age"], r["winner_rank"]),
                                          ("l", r["loser_id"], r["winner_id"], r["loser_age"], r["loser_rank"])):
            if pid not in recs:
                ok = False
                break
            j = bisect_left(dates[pid], d0)          # samo zapisi strogo prije datuma meča
            prev = recs[pid][max(0, j - 400):j]
            other = [x for x in prev if x[2] != tid0]
            weeks = {monday(x[0]) for x in other if x[0] >= w0 - pd.Timedelta(days=7 * 12)}
            k = 0
            while (w0 - pd.Timedelta(days=7 * (k + 1))) in weeks:
                k += 1
            row[f"streak_{side}"] = k
            row[f"t45_{side}"] = len({x[2] for x in other if s0 - pd.Timedelta(days=45) <= x[0] < s0})
            row[f"m30_{side}"] = sum(1 for x in prev if d0 - pd.Timedelta(days=30) <= x[0])
            row[f"rest_{side}"] = ((d0 - prev[-1][0]).days - 1) if prev else np.nan
            row[f"age_{side}"] = float(age) if not pd.isna(age) else np.nan
            row[f"rank_{side}"] = float(rank) if not pd.isna(rank) else np.nan
            h = [x for x in other if x[4] == opp]
            row[f"h2h_n_{side}"] = len(h)
            row[f"h2h_w_{side}"] = sum(x[5] for x in h)
            row[f"top5w_{side}"] = sum(1 for x in other if x[5] == 1 and not pd.isna(x[6]) and x[6] <= 5
                                       and x[0] >= d0 - pd.Timedelta(days=730))
        if ok:
            rows.append(row)
    f = pd.DataFrame(rows)
    print(f"LAB mečeva s cijenom i obje strane: {len(f)}")
    for c in ["streak_w", "t45_w", "m30_w", "rest_w", "age_w", "h2h_n_w", "top5w_w"]:
        s = f[c]
        print(f"   {c:10s} prazno {s.isna().mean()*100:4.1f}%  medijan {s.median():6.1f}  max {s.max():6.1f}")

    pf_arr, half_arr = f["pf"].values, f["half"].values

    def oriented(mw, ml):
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    def M(expr_w, expr_l):
        return np.asarray(expr_w.fillna(False), bool), np.asarray(expr_l.fillna(False), bool)

    sw, sl = f.streak_w, f.streak_l
    tests_u = [
        ("U1 A niz ≥3 (4.+ tjedan zaredom), B niz 0", -1, *M((sw >= 3) & (sl == 0), (sl >= 3) & (sw == 0))),
        ("U2 A niz =2 (3. tjedan zaredom), B niz 0", -1, *M((sw == 2) & (sl == 0), (sl == 2) & (sw == 0))),
        ("U3 A ≥3 turnira u 45 d, B ≤1", -1, *M((f.t45_w >= 3) & (f.t45_l <= 1), (f.t45_l >= 3) & (f.t45_w <= 1))),
        ("U4 A ≥10 mečeva u 30 d, B ≤4", -1, *M((f.m30_w >= 10) & (f.m30_l <= 4), (f.m30_l >= 10) & (f.m30_w <= 4))),
        ("U5 A ≥33 god., odmor ≤1 d, B <30 god.", -1,
         *M((f.age_w >= 33) & (f.rest_w <= 1) & (f.age_l < 30), (f.age_l >= 33) & (f.rest_l <= 1) & (f.age_w < 30))),
        ("U6 A ≥30 god., odmor ≤1 d, B <26 god.", -1,
         *M((f.age_w >= 30) & (f.rest_w <= 1) & (f.age_l < 26), (f.age_l >= 30) & (f.rest_l <= 1) & (f.age_w < 26))),
        ("U7 A ≥30 god. i niz ≥2, B <26 god.", -1,
         *M((f.age_w >= 30) & (sw >= 2) & (f.age_l < 26), (f.age_l >= 30) & (sl >= 2) & (f.age_w < 26))),
    ]
    lead_w = (f.h2h_n_w >= 3) & (f.h2h_w_w >= 0.75 * f.h2h_n_w)
    lead_l = (f.h2h_n_l >= 3) & (f.h2h_w_l >= 0.75 * f.h2h_n_l)
    dog_w, dog_l = f.pf < 0.5, f.pf > 0.5
    tests_h = [
        ("H1 A vodi u H2H (≥3 susreta, ≥75%)", +1, *M(lead_w, lead_l)),
        ("H2 kao H1, A autsajder", +1, *M(lead_w & dog_w, lead_l & dog_l)),
        ("H3 ubojica velikana: A autsajder, B top 5, A ≥2 pobjede nad top-5 u 2 god.", +1,
         *M(dog_w & (f.rank_l <= 5) & (f.top5w_w >= 2), dog_l & (f.rank_w <= 5) & (f.top5w_l >= 2))),
    ]
    tests_d = []
    for rd in ["R128", "R64", "R32", "R16", "QF", "SF", "F"]:
        inr = (f["round"] == rd)
        tests_d.append((f"D autsajder u {rd}", +1, *M(inr & dog_w, inr & dog_l)))
    for rd in ["R128", "R64", "R32", "R16", "QF", "SF", "F"]:
        inr = (f["round"] == rd)
        tests_d.append((f"D tijesni autsajder (0,40–0,50) u {rd}", +1,
                        *M(inr & (f.pf >= 0.40) & (f.pf < 0.5), inr & (f.pf > 0.5) & (f.pf <= 0.60))))

    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values

    def bandof(pA):
        return "jak fav" if pA >= 0.70 else ("fav" if pA >= 0.5 else ("autsajder" if pA >= 0.30 else "veliki autsajder"))

    def run(tests):
        res, pvals = {}, []
        for name, sign, mw, ml in tests:
            rows_ = oriented(mw, ml)
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
            res[name]["bonf_all"] = min(1.0, pv * (N_PRIOR + N_TODAY))
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
        width = (a["hi"] - a["lo"]) / 2
        return "PADA → ODBAČENO" if width <= 4 else "PADA (nije potvrđeno, interval širi od ±4)"

    out = {}
    for fam, tests in (("U (umor)", tests_u), ("H (H2H)", tests_h), ("D (runda × autsajder)", tests_d)):
        res = run(tests)
        print("\n" + "=" * 160)
        print(f"OBITELJ {fam}: {'test':66s} smjer   n      edge   [95% interval]    P1 / P2     Holm  (P×{N_PRIOR + N_TODAY})  pobjeđuje  favorit  presuda")
        for name, sign, *_ in tests:
            r = res[name]
            r["verdict"] = verdict(r)
            a, p1, p2 = r["all"], r["P1"], r["P2"]
            if not a.get("n"):
                print(f"  {name:72s} n=0")
                continue
            print(f"  {name:72s} {'+' if sign > 0 else '-'}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
                  f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}  {r['holm']:5.2f}  ({r['bonf_all']:4.2f})"
                  f"   {100*r['raw_win']:5.1f}%   {100*r['raw_fav']:5.1f}%   {r['verdict']}")
        out[fam] = res

    # opis: koliko je vođa u H2H ujedno tržišni favorit (tržište "zna" H2H)
    lw = lead_w.fillna(False).values
    ll = lead_l.fillna(False).values
    fav_of_leader = [pf_arr[k] >= 0.5 for k in range(len(f)) if lw[k]] + [pf_arr[k] < 0.5 for k in range(len(f)) if ll[k]]
    win_of_leader = [1 for k in range(len(f)) if lw[k]] + [0 for k in range(len(f)) if ll[k]]
    print(f"\nOPIS H2H: vođa (≥3 susreta, ≥75%) pobjeđuje {100*np.mean(win_of_leader):.1f}%, a tržišni je favorit u "
          f"{100*np.mean(fav_of_leader):.1f}% slučajeva (n={len(win_of_leader)})")
    # opis: niz tjedana po dobi (koliko često 4.+ tjedan zaredom)
    for side in ("w", "l"):
        pass
    allp = pd.concat([pd.DataFrame({"streak": f.streak_w, "age": f.age_w}), pd.DataFrame({"streak": f.streak_l, "age": f.age_l})])
    print("OPIS niz tjedana (svi igrači-mečevi): " + ", ".join(f"{k}: {v}" for k, v in allp.streak.clip(upper=5).value_counts().sort_index().items()))

    with open(os.path.join(OUTD, "lab_rezultati.json"), "w", encoding="utf-8") as fo:
        json.dump(out, fo, indent=1, default=float)


if __name__ == "__main__":
    main()
