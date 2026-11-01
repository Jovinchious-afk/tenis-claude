# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - neovisna provjera brojki o NASIM pickovima iz sirovog dumpa
(.cache/rev_2026-11-01/analyzed_matches.json), bez r_base.py. Samo cita.
    PYTHONIOENCODING=utf-8 python revizije/2026-11-01/skeptik/s_nasi.py
"""
import json
import math
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
D = os.path.join(ROOT, ".cache", "rev_2026-11-01")
am = json.load(open(os.path.join(D, "analyzed_matches.json"), encoding="utf-8"))
print("redaka u dumpu:", len(am))
rows = []
for r in am:
    pw, p1, p2 = r.get("predicted_winner"), r.get("player1"), r.get("player2")
    res, aw = r.get("prediction_correct"), r.get("actual_winner")
    if not pw or pw not in (p1, p2) or res is None or aw not in (p1, p2):
        continue
    try:
        o1, o2 = float(r.get("bookmaker_odds_p1")), float(r.get("bookmaker_odds_p2"))
    except (TypeError, ValueError):
        o1 = o2 = np.nan
    is1 = pw == p1
    op, oo = (o1, o2) if is1 else (o2, o1)
    p = (1 / op) / (1 / op + 1 / oo) if (op > 1 and oo > 1) else np.nan
    cs = r.get("context_snapshot") or {}
    fa = r.get("full_analysis") or {}
    rows.append(dict(id=r["id"], date=str(r.get("match_date"))[:10], created=r.get("created_at"), tour=r.get("tournament"),
                     pick=pw, opp=p2 if is1 else p1, win=1.0 if res else 0.0, odds=op, odds_opp=oo, p=p,
                     elo_susp=bool(cs.get("elo_suspect")), rnd=r.get("round"), conf=r.get("predicted_confidence"),
                     age_p=cs.get(("p1" if is1 else "p2") + "_age"),
                     age_o=cs.get(("p2" if is1 else "p1") + "_age"),
                     analysis=(fa.get("analysis") or ""),
                     kf=" ".join(str(x) for x in (fa.get("key_factors") or [])),
                     own=next((m.group(3).strip() for m in (re.match(r"\s*(\d)\.\s*([^:]+):\s*(.*)", str(x), re.S) for x in (fa.get("key_factors") or [])) if m and m.group(1) == "5"), "")))
df = pd.DataFrame(rows)
print("razrijesenih s pickom:", len(df), "| s cijenom:", int(df.p.notna().sum()), "| elo_suspect:", int(df.elo_susp.sum()))
df["pair"] = df.apply(lambda r: tuple(sorted([str(r.pick), str(r.opp)])), axis=1)
dup = df.duplicated(["tour", "pair"], keep=False)
print("redaka koji dijele turnir+par:", int(dup.sum()))
tj = df[(df.date >= "2026-10-26") & (df.date <= "2026-11-01")]
print("TJEDAN sirovo:", len(tj), tj.tour.value_counts().to_dict())
tj = tj.drop_duplicates(["tour", "pair"], keep="last")
tj = tj[tj.p.notna() & ~tj.elo_susp]
n = len(tj)
e = 100 * (tj.win.mean() - tj.p.mean())
se = 100 * math.sqrt((tj.p * (1 - tj.p)).sum()) / n
print(f"TJEDAN n={n} W={int(tj.win.sum())} pogodak {100*tj.win.mean():.1f}% cijena {100*tj.p.mean():.1f}% edge {e:+.1f} +-{1.96*se:.1f}")
fav_wins = np.where(tj.p >= 0.5, tj.win, 1 - tj.win)
fav_p = np.where(tj.p >= 0.5, tj.p, 1 - tj.p)
print(f"  trzisni favorit u tih {n} meceva: pobijedio {int(fav_wins.sum())}/{n} ({100*fav_wins.mean():.1f}%), cijena {100*fav_p.mean():.1f}% -> edge favorita {100*(fav_wins.mean()-fav_p.mean()):+.1f}pp")
print(f"  nas pick: pobijedio {int(tj.win.sum())}/{n}; pickova koji NISU trzisni favorit: {(tj.p < 0.5).sum()}")
print(f"  razlika pick - favorit u pobjedama: {int((tj.win.values - fav_wins).sum())} (pozitivno = model bolji od 'uvijek favorit')")
for t, g in tj.groupby("tour"):
    fw = np.where(g.p >= .5, g.win, 1 - g.win)
    fp = np.where(g.p >= .5, g.p, 1 - g.p)
    print(f"  {t[:34]:34s} n={len(g)} pick {int(g.win.sum())}W  favorit {int(fw.sum())}W  edge picka {100*(g.win.mean()-g.p.mean()):+.1f}  edge favorita {100*(fw.mean()-fp.mean()):+.1f}")
d2 = df[df.p.notna() & ~df.elo_susp].drop_duplicates(["tour", "pair"], keep="last")
nv, st = d2[d2.date >= "2026-09-27"], d2[d2.date < "2026-09-27"]
for lab, g in (("NOVO", nv), ("STARO", st)):
    print(f"{lab}: n={len(g)} edge {100*(g.win.mean()-g.p.mean()):+.1f} +-{196*math.sqrt((g.p*(1-g.p)).sum())/len(g):.1f}")
for lab, g in (("STARO", st), ("NOVO", nv), ("TJEDAN", tj), ("STARO+NOVO", pd.concat([st, nv]))):
    b = g[(g.odds >= 1.35) & (g.odds < 1.45)]
    if len(b):
        print(f"D4 1,35-1,45 {lab:11s} n={len(b):3d} W={int(b.win.sum()):3d} edge {100*(b.win.mean()-b.p.mean()):+6.1f} +-{196*math.sqrt((b.p*(1-b.p)).sum())/len(b):.1f}")
d2.to_pickle(os.path.join(D, "skeptik_d2.pkl"))
