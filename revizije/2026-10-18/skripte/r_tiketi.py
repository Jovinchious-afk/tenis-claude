# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — A3/A4: tiketi od 27.09. i učestalost tiketa od 04.10. (18.10.2026 09:11, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točke A3 i A4 (09:07).
- P(tiket) = umnožak devigiranih SuperSport cijena nogu (cijena iz analize istog para, ±2 dana;
  ako analize nema, devig iz same kvote noge uz prosječnu maržu 6%).
- "odlučujuća" noga = jedina izgubljena noga na tiketu.
Samo čita .cache/rev_2026-10-18/*.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, load  # noqa: E402

MARGIN = 1.06   # prosječna marža SuperSporta na dvije strane (samo rezerva kad analize nema)


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    tk = pd.DataFrame(load("tickets"))
    tm = pd.DataFrame(load("ticket_matches"))
    real = tk[(tk.ticket_date >= "2026-09-27") & tk.status.isin(["won", "lost"])].sort_values("ticket_date")
    probs, legs_all = [], []
    print("=== A3. Tiketi od 27.09.2026")
    for _, t in real.iterrows():
        legs = tm[tm.ticket_id == t["id"]]
        ps, desc, lost = [], [], []
        for _, lg in legs.iterrows():
            md = pd.Timestamp(str(lg["match_date"])[:10])
            row = df[(df.pick == lg["pick"]) & ((df.opp == lg["player1"]) | (df.opp == lg["player2"]))
                     & ((df.date - md).abs() <= pd.Timedelta(days=2))]
            o = float(lg["odds"])
            p = float(row.p_dev.iloc[0]) if len(row) else min(0.97, MARGIN / o / (MARGIN / o + 1 - 1 / o) if o > 1 else np.nan)
            src = "analiza" if len(row) else "procjena"
            res = lg["result"]
            ps.append(p)
            mark = "W" if res == "won" else ("L" if res == "lost" else "?")
            extra = ""
            if len(row):
                r0 = row.iloc[0]
                extra = (f" [{r0['round']}, conf {r0.conf:.0f}"
                         f"{', poeni %.1f%%' % (100*r0.pm_tp_share) if not pd.isna(r0.pm_tp_share) else ''}"
                         f"{', ' + r0.klasa if isinstance(r0.get('klasa'), str) else ''}]")
            desc.append(f"{lg['pick'].split()[-1]} @{o:.2f} {mark} (p={p:.2f}{'' if src=='analiza' else '*'}){extra}")
            if res == "lost":
                lost.append(f"{lg['pick'].split()[-1]} @{o:.2f}")
            legs_all.append({"ticket": t["ticket_date"], "pick": lg["pick"], "opp": lg["player2"] if lg["pick"] == lg["player1"] else lg["player1"],
                             "odds": o, "p": p, "result": res, "round": (row.iloc[0]["round"] if len(row) else lg.get("round")),
                             "tour": (row.iloc[0]["tournament"] if len(row) else lg.get("tournament")),
                             "conf": (row.iloc[0]["conf"] if len(row) else np.nan),
                             "tp": (row.iloc[0]["pm_tp_share"] if len(row) else np.nan),
                             "klasa": (row.iloc[0].get("klasa") if len(row) else None),
                             "cons_gap": (row.iloc[0]["cons_gap"] if len(row) else np.nan),
                             "decision": t.get("reviewer_decision")})
        pj = float(np.prod(ps)) if ps else np.nan
        probs.append((t["ticket_date"], t["status"], pj))
        ev = pj * float(t["total_odds"]) - 1
        dec = "ODLUČUJUĆA: " + lost[0] if len(lost) == 1 else (f"palo {len(lost)}: " + ", ".join(lost) if lost else "sve prošlo")
        print(f"\n  {t['ticket_date']} {t['status']:4s} kvota {float(t['total_odds']):5.2f}  nogu {len(legs)}  P(prolaz) {pj:5.1%}"
              f"  EV po kvoti {ev:+.1%}  recenzent: {t.get('reviewer_decision') or '-'}  | {dec}")
        for d in desc:
            print("      " + d)
    lg = pd.DataFrame(legs_all)
    p_all = [p for _, _, p in probs]
    print(f"\n  tiketa: {len(probs)}, dobitnih {sum(1 for _, s, _ in probs if s == 'won')}, očekivano dobitnih {sum(p_all):.2f}")
    streak = [p for d, s, p in probs if d >= "2026-09-29"]
    p0 = float(np.prod([1 - p for p in streak]))
    print(f"  niz 29.09.-12.10.: {len(streak)} tiketa, očekivano dobitnih {sum(streak):.2f}; "
          f"vjerojatnost da nijedan ne prođe slučajno = {p0:.1%}")
    # simulacija: koliko često u 10 tiketa ovakvih P dobijemo <=1 dobitan
    rng = np.random.default_rng(18102026)
    sims = rng.random((200000, len(p_all))) < np.array(p_all)
    k = sims.sum(axis=1)
    print(f"  simulacija 200.000 x {len(p_all)} tiketa s ovim P: 0 dobitnih {np.mean(k==0):.1%}, <=1 dobitan {np.mean(k<=1):.1%}, "
          f">=2 dobitna {np.mean(k>=2):.1%}")
    print("\n--- noge tiketa (sve)")
    lg["win"] = (lg.result == "won").astype(float)
    res = lg[lg.result.isin(["won", "lost"])]
    print(f"  nogu {len(res)}: prošlo {int(res.win.sum())} ({100*res.win.mean():.1f}%), cijena očekivala {100*res.p.mean():.1f}% "
          f"-> edge {100*(res.win.mean()-res.p.mean()):+.1f}pp")
    for lo, hi in [(1.0, 1.35), (1.35, 1.65), (1.65, 1.85), (1.85, 9)]:
        s = res[(res.odds >= lo) & (res.odds < hi)]
        if len(s):
            print(f"    kvota {lo:.2f}-{hi:.2f}: n={len(s):2d} prošlo {int(s.win.sum()):2d}  cijena {100*s.p.mean():5.1f}%  edge {100*(s.win.mean()-s.p.mean()):+6.1f}pp")
    print("  izgubljene noge:")
    for _, r in res[res.win == 0].iterrows():
        print(f"    {r.ticket} {str(r.pick).split()[-1]:14s} vs {str(r.opp).split()[-1]:14s} @{r.odds:.2f} p={r.p:.2f} {r['round']} "
              f"{str(r.tour)[:12]} conf={r.conf} poeni={r.tp if pd.isna(r.tp) else round(100*r.tp,1)} {r.klasa} kons_gap={r.cons_gap if pd.isna(r.cons_gap) else round(r.cons_gap,1)}")

    print("\n=== A4. Učestalost tiketa od 05.10. (prag 63)")
    allt = tk[tk.ticket_date >= "2026-10-05"].sort_values("ticket_date")
    for _, t in allt.iterrows():
        n = int(t.get("matches_count") or 0)
        print(f"  {t['ticket_date']} {t['status']:13s} nogu/pickova {n:2d}  kvota {float(t.get('total_odds') or 0):5.2f}")
    print(f"  dana s pravim tiketom: {int(allt.status.isin(['won','lost']).sum())} od {allt.ticket_date.nunique()} dana s runom")
    lg.to_pickle(os.path.join(DUMP, "ticket_legs.pkl"))


if __name__ == "__main__":
    main()
