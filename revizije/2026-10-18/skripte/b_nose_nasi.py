# -*- coding: utf-8 -*-
"""Revizija 18.10.2026, drugi dio — Nose (nose-v1) na NAŠIM riješenim analizama (18.10.2026 12:33).

RAZVOJNI UZORAK, NE POTVRDA (PRAGOVI_B 12:20, točka N-NAŠI). Isti kod kao uživo
(`agent/nose.py`: match_features -> assess -> freeze -> compare_with_market), na snapshotima
zapisanima PRIJE meča. Edge picka = pobjeda − devigirana SuperSport cijena.
Bez analiza s dokazano tuđim ELO-om (`elo_suspect`); isti meč (turnir + par, ±3 dana) jednom.

Samo čita lokalni dump (.cache/rev_2026-10-18b, b_dump.py 12:13).
    python revizije/2026-10-18/skripte/b_nose_nasi.py
"""
import json
import math
import os
import sys
from collections import Counter

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from agent import nose as N  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-10-18b")
NOVO_OD = "2026-09-27"


def edge(rows, key="win", p="p"):
    n = len(rows)
    if n == 0:
        return 0, float("nan"), float("nan")
    res = [r[key] - r[p] for r in rows]
    m = sum(res) / n
    se = math.sqrt(sum(r[p] * (1 - r[p]) for r in rows)) / n
    return n, 100 * m, 100 * 1.96 * se


def main():
    am = json.load(open(os.path.join(DUMP, "analyzed_matches.json"), encoding="utf-8"))
    rows, seen = [], {}
    for r in am:
        pick, p1, p2 = r.get("predicted_winner"), r.get("player1"), r.get("player2")
        if not pick or pick not in (p1, p2) or r.get("prediction_correct") is None:
            continue
        if r.get("actual_winner") not in (p1, p2):
            continue
        cs = r.get("context_snapshot") or {}
        if cs.get("elo_suspect"):
            continue
        side = 1 if pick == p1 else 2
        o1, o2 = r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")
        op, oo = (o1, o2) if side == 1 else (o2, o1)
        p = N.devig(op, oo)
        if p is None:
            continue
        feat = N.match_features(cs, r.get("surface") or "", r.get("tournament_level") or "")
        a = N.assess(feat, side)
        a["frozen"] = N.freeze(a)
        b = N.compare_with_market(a, op, oo)
        d = str(r.get("match_date"))[:10]
        key = (r.get("tournament"), tuple(sorted([p1, p2])))
        row = {"date": d, "sample": "NOVO" if d >= NOVO_OD else "STARO", "pick": pick,
               "win": 1.0 if r.get("prediction_correct") else 0.0, "p": p, "odds": float(op),
               "suit": a["ticket_suitability"], "mr": a["mine_risk"]["n"], "mflags": a["mine_risk"]["flags"],
               "uv": a["upset_value"]["n"], "uflags": a["upset_value"]["flags"],
               "p_own": a["pick_quality"]["p_own"], "rel": a["pick_quality"]["reliability"],
               "diff": (a["pick_quality"]["p_own"] - p) if a["pick_quality"]["p_own"] is not None else None,
               "opp_value": b.get("opp_value", False), "label": b.get("label"),
               "tournament": r.get("tournament"), "id": r.get("id"), "created": r.get("created_at")}
        prev = seen.get(key)
        if prev is not None and abs((pd.Timestamp(d) - pd.Timestamp(rows[prev]["date"])).days) <= 3:
            rows[prev] = row          # zadrži zadnji (najbogatiji) zapis istog meča
            continue
        seen[key] = len(rows)
        rows.append(row)
    print(f"riješenih analiza s cijenom (bez elo_suspect, bez duplikata): {len(rows)}")
    print("  po uzorku:", dict(Counter(r["sample"] for r in rows)))
    print("  Ticket Suitability:", dict(Counter(r["suit"] for r in rows)))
    print("  pouzdanost:", dict(Counter(r["rel"] for r in rows)))
    ev = [r for r in rows if r["suit"] != "NEMA PODATAKA"]
    print(f"  s procjenom: {len(ev)}  (pick = tržišni favorit u {100 * sum(r['p'] > 0.5 for r in ev) / max(len(ev), 1):.1f}%)")

    print("\nEdge picka po Ticket Suitability (razvojni uzorak):")
    print(f"  {'skupina':16s} {'SVE':>26s} {'STARO':>26s} {'NOVO':>26s}")
    for s in ("UKLJUČI", "UZ UPOZORENJE", "IZBJEGAVAJ"):
        out = []
        for samp in (None, "STARO", "NOVO"):
            rs = [r for r in ev if r["suit"] == s and (samp is None or r["sample"] == samp)]
            n, e, ci = edge(rs)
            out.append(f"n={n:3d} {e:+6.1f}pp ±{ci:4.1f}")
        print(f"  {s:16s} " + "   ".join(out))
    print("\nMine Risk (pick):")
    for k in (0, 1, 2):
        rs = [r for r in ev if (r["mr"] >= 2 if k == 2 else r["mr"] == k)]
        n, e, ci = edge(rs)
        st = edge([r for r in rs if r["sample"] == "STARO"])
        nv = edge([r for r in rs if r["sample"] == "NOVO"])
        print(f"  MR {'2+' if k == 2 else k}: n={n:3d} {e:+6.1f}pp ±{ci:4.1f} | STARO {st[1]:+6.1f} (n={st[0]}) | NOVO {nv[1]:+6.1f} (n={nv[0]})")
    print("  pojedinačna upozorenja:", dict(Counter(f for r in ev for f in r["mflags"])))
    print("\nUpset Value (protivnik; edge PROTIVNIKA = njegova pobjeda − njegova cijena):")
    for k in (0, 1, 2):
        rs = [r for r in ev if (r["uv"] >= 2 if k == 2 else r["uv"] == k)]
        opp = [{"win": 1 - r["win"], "p": 1 - r["p"], "sample": r["sample"]} for r in rs]
        n, e, ci = edge(opp)
        print(f"  UV {'2+' if k == 2 else k}: n={n:3d} protivnik {e:+6.1f}pp ±{ci:4.1f}")
    print("  pojedinačni razlozi:", dict(Counter(f for r in ev for f in r["uflags"])))
    print("\nFaza B — Nose naspram cijene:")
    for lab in sorted({r["label"] for r in ev}):
        rs = [r for r in ev if r["label"] == lab]
        n, e, ci = edge(rs)
        print(f"  {lab[:62]:62s} n={n:3d} pick {e:+6.1f}pp ±{ci:4.1f}")
    g = N.gate_status([{"suit": r["suit"], "win": r["win"], "p": r["p"], "date": r["date"],
                        "opp_value": r["opp_value"], "diff": r["diff"]} for r in ev])
    print("\nK24 funkcija na RAZVOJNOM uzorku (samo provjera koda, NE ishod kapije):")
    for k, v in g.items():
        print(f"  {k}: {v}")
    for samp in ("STARO", "NOVO"):
        rs = [r for r in ev if r["sample"] == samp and r["diff"] is not None]
        xs = [r["diff"] for r in rs]
        ys = [r["win"] - r["p"] for r in rs]
        if len(rs) > 10:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            sxx = sum((x - mx) ** 2 for x in xs)
            syy = sum((y - my) ** 2 for y in ys)
            print(f"  r(P_own − cijena, ishod − cijena) {samp}: {sxy / math.sqrt(sxx * syy):+.3f} (n={len(rs)})")
    pd.DataFrame(rows).to_pickle(os.path.join(DUMP, "b_nose_nasi.pkl"))


if __name__ == "__main__":
    main()
