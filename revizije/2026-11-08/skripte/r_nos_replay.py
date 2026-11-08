# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — nos-odluka na Parizu s težinama naučenim SAMO PRIJE Pariza (08.11.2026 12:48).

Pošteni pokus (izvan uzorka učenja): `nos_odluka.nauci` uči na riješenim pickovima do 01.11.2026, pa se
odluka primijeni na Pariz (02.–07.11.). Gleda se: koliko pickova nos pomakne preko/ispod praga 63, kako
su prošli pickovi koje nos podiže naspram onih koje spušta, i nos-autsajderi. Usporedno i u uzorku
(težine naučene i na Parizu), da se vidi koliko je "uspjeha" samo naknadna pamet.
Čita lokalni dump (.cache/rev_2026-11-08/analyzed_matches.json). Bez plaćenih poziva.
    python revizije/2026-11-08/skripte/r_nos_replay.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from agent import nos_odluka as no  # noqa: E402
from agent import nos_ploca as npl  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-08", "analyzed_matches.json")
PARIZ = ("2026-11-02", "2026-11-08")


def primjer(row):
    if row.get("prediction_correct") is None or (row.get("context_snapshot") or {}).get("elo_suspect"):
        return None
    pick, p1 = row.get("predicted_winner"), row.get("player1")
    o_p, o_o = ((row.get("bookmaker_odds_p1"), row.get("bookmaker_odds_p2")) if pick == p1
                else (row.get("bookmaker_odds_p2"), row.get("bookmaker_odds_p1")))
    p = npl.devig(o_p, o_o)
    if p is None:
        return None
    rec = npl.rec_from_row(row)
    z = no.znakovi(rec)
    if z.get("error"):
        return None
    return {"aktivni": z["aktivni"], "nedostaje": z["nedostaje"], "win": 1.0 if row["prediction_correct"] else 0.0,
            "p": p, "date": str(row.get("match_date"))[:10], "rec": rec, "row": row, "o_opp": o_o, "o_pick": o_p}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(DUMP, encoding="utf-8"))
    ex = [e for e in (primjer(r) for r in rows) if e]
    for lab, danas in (("IZVAN UZORKA (učio do 01.11.)", PARIZ[0]), ("U UZORKU (učio i na Parizu)", "2026-11-08")):
        t = no.nauci([dict(e) for e in ex], danas=danas)
        par = [e for e in ex if PARIZ[0] <= e["date"] < PARIZ[1]]
        print("=" * 100)
        print(f"{lab}: težine na {t['n_pickova']} pickova; Pariz {len(par)} pickova")
        print("  težine ≠ 0:", ", ".join(f"{s} {z['tezina_pp']:+.1f}" for s, z in t["znakovi"].items() if z["tezina_pp"]))
        gore = dolje = 0
        grp = {"podiže (≥ +1)": [], "spušta (≤ −1)": [], "neutralno": []}
        dogs = []
        for e in par:
            s, _ = no.ocjena(e["aktivni"], t)
            cm = float(e["row"].get("predicted_confidence") or 0)
            cn = cm + s
            gore += cm < 63 <= cn
            dolje += cn < 63 <= cm
            grp["podiže (≥ +1)" if s >= 1 else ("spušta (≤ −1)" if s <= -1 else "neutralno")].append(e)
            # nos-autsajder (isto pravilo kao `_autsajder`, iz spremljenog Nosea)
            nz = (e["row"].get("context_snapshot") or {}).get("nose") or {}
            vm = nz.get("vs_market") or {} if isinstance(nz, dict) else {}
            if vm.get("opp_value") and cm <= no.AUTS_MAX_MODEL_CONF:
                p_own_opp = (nz.get("upset_value") or {}).get("p_own_opp")
                p_mkt = vm.get("p_market")
                oo = float(e["o_opp"] or 0)
                if p_own_opp and p_mkt and no.AUTS_KVOTA[0] <= oo <= no.AUTS_KVOTA[1]:
                    pred_ = 100 * (p_own_opp - (1 - p_mkt))
                    if pred_ >= no.AUTS_MIN_PREDNOST_PP:
                        p1, p2 = e["rec"]["p1"], e["rec"]["p2"]
                        opp = p2 if e["rec"]["pick"] == p1 else p1
                        zo = no.znakovi(e["rec"], za_igraca=opp)
                        so, _ = no.ocjena(zo.get("aktivni") or [], t, bez_cjenovnih=True)
                        if so >= no.AUTS_MIN_OCJENA:
                            dogs.append((e["date"], opp, oo, pred_, 1 - e["win"]))
        print(f"  nos bi pomaknuo preko praga 63: {gore}, ispod praga: {dolje}")
        for g, lst in grp.items():
            if lst:
                w = sum(x["win"] for x in lst)
                pr = sum(x["p"] for x in lst)
                print(f"   {g:16s} n={len(lst):3d}  {int(w)}–{len(lst) - int(w)}  edge {100 * (w - pr) / len(lst):+6.1f}pp")
        print(f"  nos-autsajderi: {len(dogs)}" + (" — " + "; ".join(
            f"{d} {o} @{k:.2f} (+{pp:.1f}pp) {'✓' if won else '✗'}" for d, o, k, pp, won in dogs) if dogs else ""))
        if dogs:
            won = sum(d[4] for d in dogs)
            roi = sum((d[2] - 1) if d[4] else -1 for d in dogs) / len(dogs)
            print(f"    pogođeno {int(won)} od {len(dogs)}, ROI {100 * roi:+.0f}%")


if __name__ == "__main__":
    main()
