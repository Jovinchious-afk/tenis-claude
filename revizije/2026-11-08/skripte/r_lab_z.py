# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — LAB: nove kombinacije iz analiza gubitaka (Z1–Z7) naspram poštene cijene
(08.11.2026 11:49).

Pragovi i definicije: revizije/2026-11-08/PRAGOVI_REVIZIJA_2026-11-08.md, točka H (NAKNADNO 08.11.2026
11:48, prije računanja). Presuda kao `r_lab.py` (isti kriterij kao revizija 25.10.2026); Holm unutar
obitelji Z (7 testova); uz to P × (109 + 24 + 7).

Podaci i zaštita od curenja kao `r_lab.py`: samo zapisi igrača s datumom STROGO prije datuma meča;
prethodni turnir, revanš i niz ne broje aktualni turnir.

Samo čita. Izlaz: ispis (u .cache/rev_2026-11-08/out_lab_z.txt) + lab_z_rezultati.json
    python revizije/2026-11-08/skripte/r_lab_z.py > .cache/rev_2026-11-08/out_lab_z.txt
"""
import json
import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r_lab import LAB, OUTD, monday, stats  # noqa: E402

N_ALL = 109 + 24 + 7


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], pd.to_datetime(td["Date"])))

    # pid -> [(datum, t_start, tid, src, opp, won, opp_rank, own_rank, runda, rezultat)]
    recs = defaultdict(list)
    for idx, r in zip(tml.index, tml.itertuples(index=False)):
        d = exact.get(idx, pd.Timestamp(r.approx_date))
        ts = pd.Timestamp(r.t_start) if not pd.isna(r.t_start) else d
        sc = str(r.score or "")
        for pid, opp, won, orank, rank in ((r.winner_id, r.loser_id, 1, r.loser_rank, r.winner_rank),
                                           (r.loser_id, r.winner_id, 0, r.winner_rank, r.loser_rank)):
            if pd.isna(pid):
                continue
            recs[pid].append((d, ts, r.tourney_id, r.src, opp, won, orank, rank, r.round, sc))
    dates = {}
    for pid in recs:
        recs[pid].sort(key=lambda x: (x[0], x[1]))
        dates[pid] = [x[0] for x in recs[pid]]

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
        row = {"pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"], "date": d0,
               "late": (s0.month in (10, 11)) and (r["tourney_level"] != "F")}
        ok = True
        for side, pid, opp, age, rank in (("w", r["winner_id"], r["loser_id"], r["winner_age"], r["winner_rank"]),
                                          ("l", r["loser_id"], r["winner_id"], r["loser_age"], r["loser_rank"])):
            if pid not in recs:
                ok = False
                break
            j = bisect_left(dates[pid], d0)
            prev = recs[pid][max(0, j - 400):j]
            other = [x for x in prev if x[2] != tid0]
            weeks = {monday(x[0]) for x in other if x[0] >= w0 - pd.Timedelta(days=7 * 12)}
            k = 0
            while (w0 - pd.Timedelta(days=7 * (k + 1))) in weeks:
                k += 1
            row[f"streak_{side}"] = k
            row[f"age_{side}"] = float(age) if not pd.isna(age) else np.nan
            row[f"rank_{side}"] = float(rank) if not pd.isna(rank) else np.nan
            # rang prije 90–150 dana
            old = [x for x in prev if d0 - pd.Timedelta(days=150) <= x[0] <= d0 - pd.Timedelta(days=90)
                   and not pd.isna(x[7])]
            row[f"rank90_{side}"] = float(old[-1][7]) if old else np.nan
            # prethodni turnir: titula u finalu ≤ 10 dana prije početka ovog; prvi meč ovdje
            first_here = not any(x[2] == tid0 and x[3] == "main" for x in prev)
            title = False
            if other:
                last = other[-1]
                if last[8] == "F" and last[5] == 1 and last[0] >= s0 - pd.Timedelta(days=10):
                    title = True
            row[f"title_{side}"] = bool(title and first_here)
            # prethodni meč (≤ 21 d) završen vlastitom predajom
            lastm = prev[-1] if prev else None
            row[f"ret_{side}"] = bool(lastm is not None and lastm[0] >= d0 - pd.Timedelta(days=21)
                                      and lastm[5] == 0 and "RET" in lastm[9].upper())
            # revanš: zadnji susret s B u 21 dan (drugi turnir) — je li ga A dobio
            h = [x for x in other if x[4] == opp and x[0] >= d0 - pd.Timedelta(days=21)]
            row[f"rem_{side}"] = (h[-1][5] == 1) if h else None
        if ok:
            rows.append(row)
    f = pd.DataFrame(rows)
    print(f"LAB mečeva s cijenom i obje strane: {len(f)}")
    for c in ["rank90_w", "title_w", "ret_w", "rem_w"]:
        s = f[c]
        if s.dtype == bool:
            print(f"   {c:9s} istinito {int(s.sum())}")
        else:
            print(f"   {c:9s} popunjeno {s.notna().mean()*100:4.1f}%")

    pf_arr, half_arr = f["pf"].values, f["half"].values

    def oriented(mw, ml):
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    def M(ew, el):
        return np.asarray(pd.Series(ew).fillna(False), bool), np.asarray(pd.Series(el).fillna(False), bool)

    riser_w = (f.rank_w <= 0.70 * f.rank90_w) & (f.rank_w <= 100) & ((f.rank_l / f.rank90_l - 1).abs() <= 0.10)
    riser_l = (f.rank_l <= 0.70 * f.rank90_l) & (f.rank_l <= 100) & ((f.rank_w / f.rank90_w - 1).abs() <= 0.10)
    late = f.late
    tests = [
        ("Z1 brzi uspon (rang ≤ 0,70 × prije 90 d), protivnik stabilan", +1, *M(riser_w, riser_l)),
        ("Z2 pad nakon titule (prvi meč tjedan nakon naslova)", -1, *M(f.title_w, f.title_l)),
        ("Z3 nedavna predaja (prethodni meč ≤ 21 d, RET)", -1, *M(f.ret_w, f.ret_l)),
        ("Z4 revanš u 21 dan: A je dobio zadnji susret", +1, *M(f.rem_w == True, f.rem_l == True)),  # noqa: E712
        ("Z5 kraj sezone × top 5 favorit", -1, *M(late & (f.rank_w <= 5) & (f.pf >= 0.5), late & (f.rank_l <= 5) & (f.pf < 0.5))),
        ("Z6 kraj sezone × niz ≥ 2, protivnik niz 0", -1, *M(late & (f.streak_w >= 2) & (f.streak_l == 0),
                                                              late & (f.streak_l >= 2) & (f.streak_w == 0))),
        ("Z7 kraj sezone × mlađi od 23 i niz ≥ 2, protivnik niz 0", -1,
         *M(late & (f.age_w < 23) & (f.streak_w >= 2) & (f.streak_l == 0),
            late & (f.age_l < 23) & (f.streak_l >= 2) & (f.streak_w == 0))),
    ]

    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values

    def bandof(pA):
        return "jak fav" if pA >= 0.70 else ("fav" if pA >= 0.5 else ("autsajder" if pA >= 0.30 else "veliki autsajder"))

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
            kk = sum(1 for g in okg if (g["edge"] > 0) == (a["edge"] > 0))
            return kk >= min(need, len(okg))
        stab = stable(r["lvl"], 2) and stable(r["rnd"], 2) and stable(r["band"], 3)
        if same and ci and halves and abs(a["edge"]) >= 2 and r["holm"] < 0.05 and stab:
            return "PROLAZI"
        if same and ci and halves:
            return "SLAB" + ("" if stab else " (nestabilno)")
        width = (a["hi"] - a["lo"]) / 2
        return "PADA → ODBAČENO" if width <= 4 else "PADA (nije potvrđeno, interval širi od ±4)"

    print("\n" + "=" * 160)
    print(f"OBITELJ Z: {'test':62s} smjer   n      edge   [95% interval]    P1 / P2     Holm  (P×{N_ALL})  pobjeđuje  favorit  presuda")
    for (name, sign, *_), hp, pv in zip(tests, holm, pvals):
        r = res[name]
        r["holm"], r["p_raw"], r["bonf_all"] = hp, pv, min(1.0, pv * N_ALL)
        r["verdict"] = verdict(r)
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if not a.get("n"):
            print(f"  {name:68s} n=0")
            continue
        print(f"  {name:68s} {'+' if sign > 0 else '-'}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
              f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}  {hp:5.2f}  ({r['bonf_all']:4.2f})"
              f"   {100*r['raw_win']:5.1f}%   {100*r['raw_fav']:5.1f}%   {r['verdict']}")
        fmt = lambda dct: " ".join(f"{kk}:{v.get('edge', float('nan')):+.1f}(n={v.get('n', 0)})" for kk, v in dct.items())
        print(f"       razina {fmt(r['lvl'])} | runda {fmt(r['rnd'])} | pojas {fmt(r['band'])}")
    with open(os.path.join(OUTD, "lab_z_rezultati.json"), "w", encoding="utf-8") as fo:
        json.dump(res, fo, indent=1, default=float)


if __name__ == "__main__":
    main()
