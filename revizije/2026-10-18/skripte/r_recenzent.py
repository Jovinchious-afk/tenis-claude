# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — L4: "nos" AI recenzenta tiketa i A3b pouzdanost noge (18.10.2026 09:12, zadnja izmjena).

Prag (PRAGOVI, NAKNADNO 09:12, zapisan prije ovog računa): noge koje recenzent imenuje kao
najrizičnije ("X carries the most risk") — edge ≤ −5pp, n ≥ 30, interval ispod nule i lošije od
ostalih noga istih tiketa → kandidat; inače opis.
Cijena noge: devigirana SuperSport cijena iz analize istog para (±2 dana); bez analize se noga
ne broji (nema poštene cijene). Samo čita .cache/rev_2026-10-18/*.
"""
import math
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, load  # noqa: E402


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s)


def stats(g):
    n = len(g)
    if n == 0:
        return "n=0"
    e = 100 * (g.win.mean() - g.p.mean())
    se = 100 * math.sqrt((g.p * (1 - g.p)).sum()) / n
    roi = 100 * np.where(g.win == 1, g.odds - 1, -1).mean()
    return f"n={n:3d}  prošlo {int(g.win.sum()):3d} ({100*g.win.mean():5.1f}%)  cijena {100*g.p.mean():5.1f}%  edge {e:+6.1f}pp [{e-1.96*se:+5.1f}, {e+1.96*se:+5.1f}]  ROI {roi:+6.1f}%"


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    tk = pd.DataFrame(load("tickets"))
    tm = pd.DataFrame(load("ticket_matches"))
    real = tk[tk.status.isin(["won", "lost"])].copy()
    rows, conf_diff = [], []
    for _, t in real.iterrows():
        w = str(t.get("reviewer_warning") or "")
        m = re.search(r"^(.{3,60}?)\s+carr(?:y|ies)\s+the\s+most\s+risk", w.strip(), re.I)
        flagged = norm(m.group(1)) if m else ""
        legs = tm[tm.ticket_id == t["id"]]
        for _, lg in legs.iterrows():
            if lg["result"] not in ("won", "lost"):
                continue
            md = pd.Timestamp(str(lg["match_date"])[:10])
            row = df[(df.pick == lg["pick"]) & ((df.opp == lg["player1"]) | (df.opp == lg["player2"]))
                     & ((df.date - md).abs() <= pd.Timedelta(days=2))]
            if not len(row):
                continue
            r0 = row.iloc[0]
            sur = norm(lg["pick"]).split()
            is_flag = bool(flagged) and any(len(x) >= 4 and x in flagged for x in sur)
            rows.append({"date": t["ticket_date"], "pick": lg["pick"], "odds": float(lg["odds"]), "p": float(r0.p_dev),
                         "win": 1.0 if lg["result"] == "won" else 0.0, "flag": is_flag, "has_warning": bool(flagged),
                         "conf_leg": lg.get("confidence"), "conf_an": r0.conf, "surface": r0.surface})
            if lg.get("confidence") is not None and not pd.isna(r0.conf):
                conf_diff.append(abs(float(lg["confidence"]) - float(r0.conf)))
    d = pd.DataFrame(rows)
    print(f"noga s cijenom: {len(d)} | tiketa s upozorenjem koje imenuje nogu: {d[d.has_warning].date.nunique()}")
    w = d[d.has_warning]
    print("\n=== L4 — noge koje je recenzent imenovao kao najrizičnije")
    print("  označene      " + stats(w[w.flag]))
    print("  ostale noge   " + stats(w[~w.flag]))
    for lab, s in (("do 13.09.", w[w.date < "2026-09-14"]), ("od 14.09.", w[w.date >= "2026-09-14"])):
        print(f"  {lab}  označene " + stats(s[s.flag]) + "\n             ostale   " + stats(s[~s.flag]))
    print("  po pojasu kvote (označene / ostale):")
    for lo, hi in [(1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)]:
        a = w[w.flag & (w.odds >= lo) & (w.odds < hi)]
        b = w[~w.flag & (w.odds >= lo) & (w.odds < hi)]
        print(f"    {lo:.2f}-{hi:.2f}  označene {stats(a)}\n               ostale   {stats(b)}")
    # ponderirana razlika unutar pojasa (kontrola cijene)
    tot, wsum = 0.0, 0
    for lo, hi in [(1.0, 1.35), (1.35, 1.65), (1.65, 2.10), (2.10, 9)]:
        a = w[w.flag & (w.odds >= lo) & (w.odds < hi)]
        b = w[~w.flag & (w.odds >= lo) & (w.odds < hi)]
        if len(a) and len(b):
            diff = (a.win.mean() - a.p.mean()) - (b.win.mean() - b.p.mean())
            tot += diff * len(a)
            wsum += len(a)
    if wsum:
        print(f"  razlika označene − ostale unutar istog pojasa (ponderirano): {100*tot/wsum:+.1f}pp (n označenih={wsum})")
    print("\n=== A3b — pouzdanost noge na tiketu naspram pouzdanosti u analizi")
    cd = np.array(conf_diff)
    print(f"  noga s obje vrijednosti: {len(cd)} | različite: {(cd > 0.5).sum()} | razlika >= 5: {(cd >= 5).sum()} | najveća {cd.max():.0f}")
    d.to_pickle(os.path.join(DUMP, "reviewer_legs.pkl"))


if __name__ == "__main__":
    main()
