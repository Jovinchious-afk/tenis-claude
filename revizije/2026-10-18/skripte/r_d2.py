# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — D2 (opis): statistika s aktualnog turnira iz NAŠIH post-match podataka (18.10.2026 09:26, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točka D2 (09:07) — samo opis, pokrivenost niska.
Za svaki naš pick od 27.09.: raniji mečevi ISTOG turnira u kojima je igrač bio u našoj analizi i
imamo post-match statistiku (poravnatu po ID-u). Prosjek po igraču: udio poena, winneri −
neiznuđene greške po meču, omjer winneri/greške, servis osvojen %. Uspoređuje se pick s protivnikom.
Samo čita .cache/rev_2026-10-18/*.
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, load, post_stats, post_metrics  # noqa: E402


def main():
    am = [r for r in load("analyzed_matches") if str(r.get("match_date")) >= "2026-09-20"]
    # igrač -> turnir -> [(datum, metrike)]
    hist = {}
    for r in am:
        ms = r.get("match_stats") or {}
        for pid, oid in ((r.get("player1_id"), r.get("player2_id")), (r.get("player2_id"), r.get("player1_id"))):
            s, o = post_stats(ms, pid), post_stats(ms, oid)
            mm = post_metrics(s, o)
            if not mm or np.isnan(mm.get("tp_share", np.nan)):
                continue
            hist.setdefault(str(pid), {}).setdefault(r.get("tournament"), []).append((str(r.get("match_date"))[:10], mm))
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    nv = df[(df["sample"] == "NOVO") & df.p_dev.notna() & ~df.elo_suspect].copy()

    def avg(pid, tour, date):
        xs = [m for d, m in hist.get(str(pid), {}).get(tour, []) if d < str(date)[:10]]
        if not xs:
            return None
        g = lambda k: np.nanmean([x.get(k, np.nan) for x in xs])
        w, u = np.nansum([x.get("winners", np.nan) for x in xs]), np.nansum([x.get("ue", np.nan) for x in xs])
        return {"n": len(xs), "tp": g("tp_share"), "serve": g("serve_won"),
                "wue": (w / u) if u > 0 else np.nan, "wmu": (w - u) / len(xs)}

    rows = []
    for _, r in nv.iterrows():
        a, b = avg(r.pick_id, r.tournament, r.date), avg(r.opp_id, r.tournament, r.date)
        if a and b:
            rows.append({"n_min": min(a["n"], b["n"]), "d_tp": a["tp"] - b["tp"], "d_wue": a["wue"] - b["wue"],
                         "d_wmu": a["wmu"] - b["wmu"], "d_serve": a["serve"] - b["serve"],
                         "win": r.win, "p": r.p_dev, "round": r["round"]})
    d = pd.DataFrame(rows)
    print(f"NOVO pickova gdje OBA igrača imaju bar 1 raniji meč na turniru s našom statistikom: {len(d)} od {len(nv)}")
    if d.empty:
        return
    print("  dubina (manji od dva broja ranijih mečeva):", d.n_min.value_counts().sort_index().to_dict())
    for lab, c in (("udio poena na turniru", "d_tp"), ("winneri/greške omjer", "d_wue"), ("winneri − greške po meču", "d_wmu"),
                   ("servis osvojen %", "d_serve")):
        for nm in (1, 2):
            x = d[(d.n_min >= nm) & d[c].notna()]
            a, b = x[x[c] > 0], x[x[c] < 0]
            def e(g):
                if not len(g):
                    return "n=0"
                ed = 100 * (g.win.mean() - g.p.mean())
                se = 100 * math.sqrt((g.p * (1 - g.p)).sum()) / len(g)
                return f"n={len(g):2d} pogodak {100*g.win.mean():5.1f}% edge {ed:+6.1f}pp ±{1.96*se:4.1f}"
            print(f"  {lab:26s} dubina {nm}+ | pick bolji: {e(a)} | pick lošiji: {e(b)}")


if __name__ == "__main__":
    main()
