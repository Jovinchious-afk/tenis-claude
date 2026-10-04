# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — C i D: korisnikove varijable i kombinacije naspram tržišta (04.10.2026 18:08).

Povijesni laboratorij (tennis-data + TML, ATP 2022 - 13.09.2026, ~12.300 mečeva s poštenom
cijenom). Pragovi i definicije: revizije/2026-10-04/PRAGOVI_REVIZIJA_2026-10-04.md (C1-C9,
D1-D6, D8, D9 zapisani 17:54; D10 dodatak 18:07). Sve osobine samo iz mečeva PRIJE ovog meča.

Mjera: za igrača iz ćelije edge = pobjeda - poštena cijena (Pinnacle, inače prosjek kladionica).
Kriterij: PROLAZI |edge|>=2pp, interval ne prelazi nulu, isti predznak u polovicama
(P1 2022-23, P2 2024-26), smjer kao u pragovima; SLAB isto uz |edge|<2pp; inače PADA.

Samo čita .cache/lab/td_joined.pkl i tml.pkl. Izlaz: ispis + .cache/rev_2026-10-04/lab_r.json
"""
import json
import math
import os
import re
import sys
from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LAB = os.path.join(ROOT, ".cache", "lab")
OUT = os.path.join(ROOT, ".cache", "rev_2026-10-04", "lab_r.json")
if "--avg" in sys.argv:
    OUT = OUT.replace("lab_r.json", "lab_r_avg.json")
SET_RE = re.compile(r"\d+-\d+")
USE_AVG = "--avg" in sys.argv


def n_sets(score):
    return len(SET_RE.findall(str(score or "")))


def num(x):
    try:
        v = float(x)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None


def build_history(tml, exact):
    """igrač -> sortirani zapisi (datum, turnir, runda, podloga, protivnik, pobjeda, rang protivnika,
    servis-gemovi, primljeni breakovi, protivnikovi servis-gemovi, napravljeni breakovi,
    servisni poeni, asovi, dvostruke, setovi)."""
    hist = defaultdict(list)
    cols = ["tourney_id", "rord", "surface", "winner_id", "loser_id", "winner_rank", "loser_rank",
            "approx_date", "score", "w_SvGms", "w_bpFaced", "w_bpSaved", "l_SvGms", "l_bpFaced",
            "l_bpSaved", "w_svpt", "w_ace", "w_df", "l_svpt", "l_ace", "l_df"]
    for idx, r in zip(tml.index, tml[cols].itertuples(index=False)):
        d = exact.get(idx, r.approx_date)
        st = n_sets(r.score)
        wsg, wbf, wbs = num(r.w_SvGms), num(r.w_bpFaced), num(r.w_bpSaved)
        lsg, lbf, lbs = num(r.l_SvGms), num(r.l_bpFaced), num(r.l_bpSaved)
        ok = None not in (wsg, wbf, wbs, lsg, lbf, lbs) and wsg > 0 and lsg > 0
        wbr = (wbf - wbs) if ok else None   # breakovi koje je pobjednik primio
        lbr = (lbf - lbs) if ok else None
        for pid, opp, won, orank, sg, br_against, osg, br_made, sv, ace, df in (
                (r.winner_id, r.loser_id, 1, r.loser_rank, wsg, wbr, lsg, lbr, num(r.w_svpt), num(r.w_ace), num(r.w_df)),
                (r.loser_id, r.winner_id, 0, r.winner_rank, lsg, lbr, wsg, wbr, num(r.l_svpt), num(r.l_ace), num(r.l_df))):
            if pd.isna(pid):
                continue
            hist[pid].append((d, r.tourney_id, r.rord, r.surface, opp, won, num(orank),
                              sg if ok else None, br_against, osg if ok else None, br_made,
                              sv, ace, df, st))
    for pid in hist:
        hist[pid].sort(key=lambda x: (x[0], x[2]))
    return hist


def feats(pid, other, D, T, R, surface, hist):
    recs = hist.get(pid, [])
    dates = [x[0] for x in recs]
    hi = bisect_left(dates, D + pd.Timedelta(days=25))
    prev = []
    for x in recs[:hi]:
        same = x[1] == T
        if (same and x[2] < R) or (not same and x[0] < D):
            prev.append(x)
    lo_d = D - pd.Timedelta(days=365)
    win365 = [x for x in prev if x[0] >= lo_d]
    out = {}
    last10 = prev[-10:]
    out["form10"] = (sum(x[5] for x in last10) / len(last10)) if len(last10) >= 5 else None
    out["all365"] = (sum(x[5] for x in win365) / len(win365)) if len(win365) >= 10 else None
    srf = [x for x in win365 if x[3] == surface]
    out["srf365"] = (sum(x[5] for x in srf) / len(srf)) if len(srf) >= 5 else None
    sg = sum(x[7] for x in win365 if x[7]) or 0
    bra = sum(x[8] for x in win365 if x[7]) or 0
    osg = sum(x[9] for x in win365 if x[9]) or 0
    brm = sum(x[10] for x in win365 if x[9]) or 0
    out["hold"] = (1 - bra / sg) if sg >= 30 else None
    out["brk"] = (brm / osg) if osg >= 30 else None
    sv = sum(x[11] for x in win365 if x[11] and x[12] is not None and x[13] is not None) or 0
    ace = sum(x[12] for x in win365 if x[11] and x[12] is not None and x[13] is not None) or 0
    dfs = sum(x[13] for x in win365 if x[11] and x[12] is not None and x[13] is not None) or 0
    out["ace"] = (ace / sv) if sv >= 300 else None
    out["df"] = (dfs / sv) if sv >= 300 else None
    out["top20w"] = sum(1 for x in win365 if x[5] and x[6] is not None and x[6] <= 20)
    h = [x for x in prev if x[4] == other]
    out["h2h_w"], out["h2h_l"] = sum(x[5] for x in h), sum(1 - x[5] for x in h)
    ev = [x for x in prev if x[1] == T]
    out["ev_won"] = sum(x[5] for x in ev)
    out["ev_sets"] = sum(x[14] for x in ev)
    return out


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


def test(rows):
    return {"all": stats(rows), "P1": stats([r for r in rows if r[2] == "P1"]),
            "P2": stats([r for r in rows if r[2] == "P2"])}


def verdict(t, sign):
    a, p1, p2 = t["all"], t["P1"], t["P2"]
    if a.get("n", 0) < 30 or p1.get("n", 0) < 10 or p2.get("n", 0) < 10:
        return "PREMALO"
    same = (a["edge"] > 0) == (sign > 0)
    ci = (a["lo"] > 0) if sign > 0 else (a["hi"] < 0)
    halves = (p1["edge"] > 0) == (p2["edge"] > 0) == (a["edge"] > 0)
    if same and ci and halves and abs(a["edge"]) >= 2:
        return "PROLAZI"
    if same and ci and halves:
        return "SLAB"
    return "PADA"


def fmt(t):
    a, p1, p2 = t["all"], t["P1"], t["P2"]
    if not a.get("n"):
        return "n=0"
    return (f"n={a['n']:5d}  edge {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]  "
            f"P1 {p1.get('edge', float('nan')):+5.1f} / P2 {p2.get('edge', float('nan')):+5.1f}")


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact)
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    rows = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        D, T, R = m["Date"], r["tourney_id"], r["rord"]
        fw = feats(r["winner_id"], r["loser_id"], D, T, R, r["surface"], hist)
        fl = feats(r["loser_id"], r["winner_id"], D, T, R, r["surface"], hist)
        # --avg: provjera otpornosti — poštena cijena samo iz prosjeka kladionica (kao lab 27.09.)
        pf = m["p_avg"] if USE_AVG else m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        row = {"pf": pf, "half": m["half"], "surface": r["surface"], "indoor": r.get("indoor"),
               "round": r["round"], "bo": m["Best of"], "rank_w": num(r["winner_rank"]), "rank_l": num(r["loser_rank"])}
        for k, v in fw.items():
            row[f"{k}_w"] = v
        for k, v in fl.items():
            row[f"{k}_l"] = v
        rows.append(row)
    f = pd.DataFrame(rows)
    print(f"mečeva: {len(f)}")
    for c in ["form10", "srf365", "hold", "brk", "ace", "df", "all365"]:
        print(f"  popunjeno {c:7s} {100*f[c+'_w'].notna().mean():5.1f}%  medijan {f[c+'_w'].median():.3f}")

    def oriented(a_better_w, a_better_l):
        """Retci (pobijedio A?, cijena A, polovica): A = igrač iz ćelije."""
        out = []
        for aw, al, pf, h in zip(a_better_w, a_better_l, f["pf"], f["half"]):
            if aw:
                out.append((1, pf, h))
            elif al:
                out.append((0, 1 - pf, h))
        return out

    def better(col, lower_is_better=False, min_gap=0.0):
        w, l = f[col + "_w"], f[col + "_l"]
        ok = w.notna() & l.notna()
        g = (l - w) if lower_is_better else (w - l)
        return ok & (g > min_gap), ok & (g < -min_gap)

    dog_w, dog_l = f["pf"] < 0.5, (1 - f["pf"]) < 0.5
    fast = (f["surface"] == "Grass") | ((f["surface"] == "Hard") & (f["indoor"] == "I"))
    clay = f["surface"] == "Clay"
    indoor = f["indoor"] == "I"
    late = f["round"].isin(["QF", "SF", "F"])
    res = {}

    tests = []
    # C — pojedinačne varijable (igrač s boljom vrijednošću)
    tests.append(("C1 forma 10", +1, better("form10")))
    tests.append(("C2 podloga 365", +1, better("srf365")))
    tests.append(("C3 hold %", +1, better("hold")))
    tests.append(("C4 break %", +1, better("brk")))
    tests.append(("C5 asovi/servis", +1, better("ace")))
    tests.append(("C6 manje dvostrukih", +1, better("df", lower_is_better=True)))
    hw, hl = f["h2h_w_w"] + f["h2h_l_w"] >= 2, f["h2h_w_w"] + f["h2h_l_w"] >= 2
    tests.append(("C7 H2H vođa (2+ meča)", +1, (hw & (f["h2h_w_w"] > f["h2h_l_w"]), hl & (f["h2h_l_w"] > f["h2h_w_w"]))))
    rk_ok = f["rank_w"].notna() & f["rank_l"].notna()
    tests.append(("C8 bolji rang, a autsajder", +1, (rk_ok & (f["rank_w"] < f["rank_l"]) & dog_w,
                                                  rk_ok & (f["rank_l"] < f["rank_w"]) & dog_l)))
    tests.append(("C9 manje setova na turniru", +1, better("ev_sets", lower_is_better=True, min_gap=0.5)))
    # D — kombinacije
    fw_, fl_ = better("form10", min_gap=0.199)
    tests.append(("D1 vruć autsajder (forma +2/10)", +1, (fw_ & dog_w, fl_ & dog_l)))
    hw_, hl_ = better("hold", min_gap=0.05)
    tests.append(("D2 hold +5pp na brzom", +1, (hw_ & fast, hl_ & fast)))
    bw_, bl_ = better("brk", min_gap=0.05)
    tests.append(("D3 break +5pp na zemlji", +1, (bw_ & clay, bl_ & clay)))
    h3 = f["h2h_w_w"] + f["h2h_l_w"] >= 3
    tests.append(("D4 H2H vođa (3+, +2) autsajder", +1, (h3 & (f["h2h_w_w"] - f["h2h_l_w"] >= 2) & dog_w,
                                                        h3 & (f["h2h_l_w"] - f["h2h_w_w"] >= 2) & dog_l)))
    sw_, sl_ = better("ev_sets", min_gap=1.5)   # A ima 2+ seta više = umorniji
    tests.append(("D5 umoran u QF/SF/F (2+ seta)", -1, (sw_ & late, sl_ & late)))
    tw_, tl_ = better("top20w", min_gap=0.5)
    tests.append(("D6 više top-20 pobjeda, autsajder", +1, (tw_ & dog_w, tl_ & dog_l)))
    spec_w = (f["srf365_w"] - f["all365_w"] >= 0.10) & ((f["srf365_l"] - f["all365_l"]) < 0.10)
    spec_l = (f["srf365_l"] - f["all365_l"] >= 0.10) & ((f["srf365_w"] - f["all365_w"]) < 0.10)
    tests.append(("D8 specijalist podloge, autsajder", +1, (spec_w & dog_w, spec_l & dog_l)))
    aw_, al_ = better("ace", min_gap=0.03)
    tests.append(("D9 asovi +3/100 u dvorani", +1, (aw_ & indoor, al_ & indoor)))
    ew_, el_ = better("ev_won", min_gap=1.5)
    tests.append(("D10 zalet na turniru, autsajder", +1, ((ew_ & dog_w & (f["ev_won_w"] >= 2)),
                                                         (el_ & dog_l & (f["ev_won_l"] >= 2)))))

    print("\n" + "=" * 118)
    pvals = []
    for name, sign, (mw, ml) in tests:
        tt = test(oriented(mw, ml))
        res[name] = {"sign": sign, **tt, "verdict": verdict(tt, sign)}
        pvals.append(tt["all"].get("p", 1.0) if tt["all"].get("n") else 1.0)
    # Holm
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    holm, run = [None] * len(pvals), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(pvals) - k) * pvals[i]))
        holm[i] = run
    for (name, sign, _), hp in zip(tests, holm):
        r = res[name]
        r["holm"] = hp
        print(f"{name:36s} smjer {'+' if sign > 0 else '-'}  {fmt(r)}  Holm P={hp:.2f}  -> {r['verdict']}")

    # monotonost po tercilama razlike za C1-C6 (opis)
    print("\nTercile razlike (igrač s boljom vrijednošću; mala / srednja / velika razlika):")
    for col, low in [("form10", False), ("srf365", False), ("hold", False), ("brk", False), ("ace", False), ("df", True)]:
        w, l = f[col + "_w"], f[col + "_l"]
        g = ((l - w) if low else (w - l))
        ok = g.notna() & (g != 0)
        a = g[ok].abs()
        q1, q2 = a.quantile([1 / 3, 2 / 3])
        parts = []
        for lo_, hi_ in [(0, q1), (q1, q2), (q2, 9e9)]:
            sel = ok & (g.abs() > lo_) & (g.abs() <= hi_)
            rr = oriented(sel & (g > 0), sel & (g < 0))
            s = stats(rr)
            parts.append(f"{s['edge']:+5.1f} (n={s['n']})")
        print(f"  {col:7s} " + " | ".join(parts))
    with open(OUT, "w", encoding="utf-8") as fo:
        json.dump(res, fo, indent=1, default=float)
    if not USE_AVG:
        f.to_pickle(os.path.join(ROOT, ".cache", "rev_2026-10-04", "lab_features_r.pkl"))


if __name__ == "__main__":
    main()
