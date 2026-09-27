# -*- coding: utf-8 -*-
"""Povijesni laboratorij — testovi pitanja 2, 3 i 4 (27.09.2026 11:42).

Pragovi i definicije: revizije/2026-09-27/PRAGOVI_POVIJESNI_LAB.md (zapisani 11:32, prije
ikakvog računanja). Ovaj kod ih samo provodi. Rezultat: ispis + lab_rezultati.json.

    python lab_tests.py            # poštena cijena = Pinnacle, inače Avg (glavno)
    python lab_tests.py --avg      # robusnost: poštena cijena = samo Avg
"""
import json
import math
import os
import sys

import pandas as pd

from lab_data import LAB_CACHE

USE_AVG = "--avg" in sys.argv


def stats(won, p):
    n = len(won)
    if n == 0:
        return {"n": 0}
    res = [w - q for w, q in zip(won, p)]
    m = sum(res) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in res) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    z = m / se if se and se > 0 else 0.0
    pval = math.erfc(abs(z) / math.sqrt(2))
    return {"n": n, "edge": 100 * m, "lo": 100 * (m - 1.96 * se), "hi": 100 * (m + 1.96 * se),
            "p": pval, "wr": 100 * sum(won) / n, "exp": 100 * sum(p) / n}


def side_rows(f, mask_a_is_w, mask_a_is_l):
    """Iz redaka (pobjednik/poraženi) napravi (pobijedio A?, poštena cijena A, polovica)."""
    out = []
    for aw, al, pf, half in zip(mask_a_is_w, mask_a_is_l, f["pf"], f["half"]):
        if aw:
            out.append((1, pf, half))
        elif al:
            out.append((0, 1 - pf, half))
    return out


def test(rows):
    all_ = stats([r[0] for r in rows], [r[1] for r in rows])
    p1 = stats([r[0] for r in rows if r[2] == "P1"], [r[1] for r in rows if r[2] == "P1"])
    p2 = stats([r[0] for r in rows if r[2] == "P2"], [r[1] for r in rows if r[2] == "P2"])
    return {"all": all_, "P1": p1, "P2": p2}


def verdict(t, sign):
    a, p1, p2 = t["all"], t["P1"], t["P2"]
    if a.get("n", 0) < 30 or p1.get("n", 0) < 10 or p2.get("n", 0) < 10:
        return "PREMALO"
    same_dir = (a["edge"] > 0) == (sign > 0)
    ci_ok = (a["lo"] > 0) if sign > 0 else (a["hi"] < 0)
    halves = (p1["edge"] > 0) == (p2["edge"] > 0) == (a["edge"] > 0)
    if same_dir and ci_ok and halves and abs(a["edge"]) >= 2:
        return "PROLAZI"
    if same_dir and ci_ok and halves:
        return "SLAB"
    return "PADA"


def fmt(t):
    a, p1, p2 = t["all"], t["P1"], t["P2"]
    if not a.get("n"):
        return "n=0"
    return (f"n={a['n']:5d}  edge {a['edge']:+5.1f}pp  [{a['lo']:+5.1f}, {a['hi']:+5.1f}]  "
            f"P1 {p1.get('edge', float('nan')):+5.1f} (n={p1.get('n', 0)})  "
            f"P2 {p2.get('edge', float('nan')):+5.1f} (n={p2.get('n', 0)})")


def favourite_rows(f, mask):
    fw = f["pf"] > 0.5
    return side_rows(f, mask & fw, mask & ~fw)


def main():
    f = pd.read_pickle(os.path.join(LAB_CACHE, "features.pkl"))
    f["pf"] = f["p_avg"] if USE_AVG else f["p_fair"]
    f = f[f["pf"].notna()].copy()
    out = {"cijena": "Avg" if USE_AVG else "Pinnacle, inače Avg", "n_meceva": len(f)}
    print(f"POŠTENA CIJENA: {out['cijena']}  |  mečeva: {len(f)}\n")

    # ---------------- PITANJE 2: pojasevi kvote favorita ----------------
    fav_is_w = f["pf"] > 0.5
    fav_odds = f["AvgW"].where(fav_is_w, f["AvgL"])
    bands = [("<1,20", 1.0, 1.20), ("1,20-1,30", 1.20, 1.30), ("1,30-1,35", 1.30, 1.35),
             ("1,35-1,43", 1.35, 1.43), ("1,43-1,60", 1.43, 1.60), ("1,60-1,75", 1.60, 1.75),
             ("1,75-2,00", 1.75, 2.001)]
    print("PITANJE 2 — favoriti po Avg kvoti (edge = stvarno − poštena cijena)")
    q2 = {}
    for name, lo, hi in bands:
        m = (fav_odds >= lo) & (fav_odds < hi)
        t = test(favourite_rows(f, m))
        q2[name] = t
        print(f"  {name:10s} {fmt(t)}")
    hole = all(q2[b]["all"].get("edge", 0) <= -1.5 and q2[b]["all"].get("hi", 1) < 0 and
               (q2[b]["P1"].get("edge", 0) < 0) and (q2[b]["P2"].get("edge", 0) < 0)
               for b in ("1,35-1,43", "1,43-1,60"))
    print(f"  => rupa 1,35-1,60 je tržišna: {'DA' if hole else 'NE'}\n")
    out["Q2"] = {"pojasevi": q2, "rupa_trzisna": hole}

    # ---------------- PITANJE 3: kandidati ----------------
    print("PITANJE 3 — kandidati (igrač s osobinom naspram poštene cijene)")
    q3 = {}
    # K15: više ATP pobjeda u sezoni
    q3["K15 više ATP pobjeda u sezoni"] = (test(side_rows(f, f["sw_w"] > f["sw_l"], f["sw_l"] > f["sw_w"])), +1)
    # K16: QF/SF/F, samo jedan ima GS polufinale
    late = f["round"].isin(["QF", "SF", "F"])
    q3["K16 jedini s GS polufinalom (QF/SF/F)"] = (test(side_rows(f, late & (f["gssf_w"] > 0) & (f["gssf_l"] == 0),
                                                                    late & (f["gssf_l"] > 0) & (f["gssf_w"] == 0))), +1)
    # K18: favorit na hard ATP 250
    h250 = (f["Series"] == "ATP250") & (f["Surface"] == "Hard")
    q3["K18 favorit na hard ATP 250"] = (test(favourite_rows(f, h250)), -1)
    k18_ref = test(favourite_rows(f, ~h250))
    # K19: povratak nakon >= 21 dan
    rw, rl = f["rest_w"].fillna(0), f["rest_l"].fillna(0)
    q3["K19 povratak nakon 21+ dana"] = (test(side_rows(f, (rw >= 21) & (rl < 21), (rl >= 21) & (rw < 21))), -1)
    k19_2141 = test(side_rows(f, (rw >= 21) & (rw < 42) & (rl < 21), (rl >= 21) & (rl < 42) & (rw < 21)))
    k19_42 = test(side_rows(f, (rw >= 42) & (rl < 21), (rl >= 42) & (rw < 21)))
    # K2: domaći igrač
    hw = (f["ioc_w"] == f["country"]) & f["country"].notna()
    hl = (f["ioc_l"] == f["country"]) & f["country"].notna()
    q3["K2 domaći igrač"] = (test(side_rows(f, hw & ~hl, hl & ~hw)), +1)
    # K3: Bo5 favorit 1,30-1,50
    q3["K3 Bo5 favorit 1,30-1,50"] = (test(favourite_rows(f, (f["Best of"] == 5) & (fav_odds >= 1.30) & (fav_odds < 1.50))), -1)
    # K11: favorit u R16/QF
    r16qf = f["round"].isin(["R16", "QF"])
    q3["K11 favorit u R16/QF"] = (test(favourite_rows(f, r16qf)), -1)
    k11_ref = test(favourite_rows(f, ~r16qf & ~f["round"].isin(["RR"])))
    # POV: bolja povijest na turniru
    q3["POV bolja povijest na turniru"] = (test(side_rows(f, f["hist_w"] > f["hist_l"], f["hist_l"] > f["hist_w"])), +1)
    # K12: dubina 3+, veći % poena na servisu na turniru
    deep = (f["depth_w"] >= 3) & (f["depth_l"] >= 3) & f["spw_w"].notna() & f["spw_l"].notna()
    q3["K12 servis na turniru (dubina 3+)"] = (test(side_rows(f, deep & (f["spw_w"] > f["spw_l"]), deep & (f["spw_l"] > f["spw_w"]))), +1)
    # CO: zajednički protivnici
    co = f["co"].fillna(0)
    q3["CO bolji protiv zajedničkih"] = (test(side_rows(f, co > 0, co < 0)), +1)

    # Holm preko svih testova pitanja 3
    names = list(q3)
    ps = sorted(((q3[k][0]["all"].get("p", 1.0), k) for k in names))
    holm, running = {}, 0.0
    for i, (p, k) in enumerate(ps):
        running = max(running, min(1.0, (len(ps) - i) * p))
        holm[k] = running
    q3_out = {}
    for k in names:
        t, sign = q3[k]
        v = verdict(t, sign)
        q3_out[k] = {"test": t, "smjer": sign, "presuda": v, "holm_p": holm[k]}
        print(f"  {k:38s} {fmt(t)}  Holm P={holm[k]:.3f}  -> {v}")
    print(f"    usporedba K18: favoriti izvan hard ATP 250  {fmt(k18_ref)}")
    print(f"    usporedba K11: favoriti u ostalim rundama   {fmt(k11_ref)}")
    print(f"    K19 po duljini: 21-41 dan {fmt(k19_2141)}")
    print(f"                    42+ dana  {fmt(k19_42)}")
    # K12 i K15: korelacija razlike s ostatkom (dodatno)
    for key, cw, cl, mask in (("K15", "sw_w", "sw_l", f["sw_w"] != f["sw_l"]),
                              ("K12", "spw_w", "spw_l", deep & (f["spw_w"] != f["spw_l"]))):
        g = f[mask]
        a_is_w = g[cw] > g[cl]
        diff = (g[cw] - g[cl]).abs()
        resid = [(1 - pf) if aw else (0 - (1 - pf)) for aw, pf in zip(a_is_w, g["pf"])]
        n = len(diff)
        if n > 2:
            dm, rm = diff.mean(), sum(resid) / n
            cov = sum((d - dm) * (r - rm) for d, r in zip(diff, resid))
            vd = sum((d - dm) ** 2 for d in diff)
            vr = sum((r - rm) ** 2 for r in resid)
            r = cov / math.sqrt(vd * vr) if vd > 0 and vr > 0 else 0
            print(f"    {key}: r(veličina razlike, ostatak) = {r:+.3f} (n={n})")
            q3_out[f"{key}_r"] = r
    out["Q3"] = q3_out
    out["Q3_usporedbe"] = {"K18_ostalo": k18_ref, "K11_ostalo": k11_ref, "K19_21_41": k19_2141, "K19_42": k19_42}
    print()

    # ---------------- PITANJE 4: Bet365 naspram poštene cijene ----------------
    print("PITANJE 4 — klađenje po Bet365 kvoti prema gapu (poštena − devig Bet365)")
    rows = []
    for pf, pb, ow, ol, half in zip(f["pf"], f["p_b365"], f["B365W"], f["B365L"], f["half"]):
        if pd.isna(pb) or pd.isna(ow) or pd.isna(ol):
            continue
        rows.append((1, pf, pb, float(ow), half))           # strana pobjednika
        rows.append((0, 1 - pf, 1 - pb, float(ol), half))   # strana poraženog
    q4 = {}
    for name, lo, hi in (("< -1pp", -99, -1), ("-1..+1pp", -1, 1), ("+1..+2pp", 1, 2), (">= +2pp", 2, 99)):
        sel = [r for r in rows if lo <= 100 * (r[1] - r[2]) < hi]
        res = {}
        for part in ("all", "P1", "P2"):
            s = sel if part == "all" else [r for r in sel if r[4] == part]
            n = len(s)
            if n < 2:
                res[part] = {"n": n}
                continue
            roi = [r[0] * r[3] - 1 for r in s]
            m = sum(roi) / n
            sd = math.sqrt(sum((x - m) ** 2 for x in roi) / (n - 1))
            res[part] = {"n": n, "roi": 100 * m, "lo": 100 * (m - 1.96 * sd / math.sqrt(n)),
                         "hi": 100 * (m + 1.96 * sd / math.sqrt(n)),
                         "edge_b365": 100 * (sum(r[0] for r in s) - sum(r[2] for r in s)) / n,
                         "gap": 100 * (sum(r[1] for r in s) - sum(r[2] for r in s)) / n}
        q4[name] = res
        a = res["all"]
        print(f"  gap {name:9s} n={a['n']:5d}  gap {a['gap']:+5.2f}pp  edge naspram Bet365 {a['edge_b365']:+5.1f}pp  "
              f"ROI po Bet365 {a['roi']:+5.1f}% [{a['lo']:+5.1f}, {a['hi']:+5.1f}]  "
              f"P1 {res['P1'].get('roi', float('nan')):+5.1f}%  P2 {res['P2'].get('roi', float('nan')):+5.1f}%")
    top = q4[">= +2pp"]
    holds = top["all"].get("lo", -1) > 0 and top["P1"].get("roi", -1) > 0 and top["P2"].get("roi", -1) > 0
    print(f"  => mehanizam drži (ROI > 0 u gap >= +2pp, obje polovice): {'DA' if holds else 'NE'}")
    out["Q4"] = {"pojasevi": q4, "drzi": holds}

    fn = os.path.join(LAB_CACHE, "lab_rezultati_avg.json" if USE_AVG else "lab_rezultati.json")
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
