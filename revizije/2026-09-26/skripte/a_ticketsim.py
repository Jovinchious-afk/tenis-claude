# -*- coding: utf-8 -*-
"""Simulacija tiketa kroz STVARNI ticket_builder._find_best_combination / _score_combo
(pravilo projekta od 08.09.2026: simulacije selekcije ne smiju ici kroz skicu).

Pojednostavljenja (zapisana, jer mijenjaju rezultat):
 - "dan" = datum meca; stvarni run gleda danas+sutra, pa je broj kandidata ovdje nesto manji
 - bez LLM recenzenta (`_review_ticket`) i bez `_both_declining_ok` (nije u zapisu)
 - Davis Cup se ne stavlja na tiket (kao u produkciji)
 - filtri P1-P5 su NADJENI NA ISTIM PODACIMA -> rezultat je optimisticna gornja granica
"""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\jovin\Desktop\Tenis Claude")
from agent import ticket_builder as tb
from config.model_config import TICKET_CONFIG

j = pd.read_pickle(r"C:\Users\jovin\Desktop\Tenis Claude\.cache\rev2609\classified_idea3.pkl")
j = j[j.win.notna() & j.p_dev.notna() & (j.level != "Davis Cup")].copy()
j["dkey"] = j.date.dt.date


def cand(r):
    o1, o2 = (r.odds, r.odds_opp) if r.pick_is_p1 else (r.odds_opp, r.odds)
    mp = r.market_p if not pd.isna(r.market_p) else None
    mp1 = (mp if r.pick_is_p1 else (1 - mp)) if mp is not None else None
    p1, p2 = (r.pick, r.opp) if r.pick_is_p1 else (r.opp, r.pick)
    return {"pick": r.pick, "confidence": float(r.conf), "fair_odds": round(100.0 / r.conf, 2),
            "match": {"player1": p1, "player2": p2, "odds_p1": o1, "odds_p2": o2, "surface": r.surface_raw,
                      "level": r.level, "tournament": r.tournament, "date": str(r.dkey), "market_p": mp1,
                      "odds_available": True},
            "_win": r.win, "_odds": r.odds}


def eligible(d, policy):
    m = (d.conf >= 60) | ((d.conf >= 58) & ((d.conf / 100 - 1 / d.odds) * 100 >= 12))
    m &= ~(d.level.eq("Grand Slam") & d.surface.isin(["hard", "clay"]) & (d.conf < 65))
    m &= ~(d.surface.eq("grass") & d.odds.between(1.43, 1.60))
    if "hole" in policy:
        m &= ~d.odds.between(1.35, 1.5999)
    if "dog" in policy:
        m &= d.p_dev >= 0.5
    if "r16qf" in policy:
        m &= ~d["round"].isin(["R16", "QF"])
    if "hard250" in policy:
        m &= ~(d.level.eq("ATP 250") & d.surface.eq("hard"))
    return d[m]


def day_ticket(d, policy):
    e = eligible(d, policy)
    # dnevni limit 6 po turniru (po pouzdanosti)
    e = e.sort_values("conf", ascending=False).groupby("tournament").head(6)
    cands = [cand(r) for r in e.itertuples()]
    if len(cands) < TICKET_CONFIG["min_matches"]:
        return None
    if len(cands) > 14:
        cands = sorted(cands, key=lambda c: c["confidence"], reverse=True)[:14]
    best = tb._find_best_combination(cands, dict(TICKET_CONFIG))
    return best


POL = {"P0 trenutna pravila": (), "P1 + bez rupe 1,35-1,60": ("hole",), "P2 + bez screenshot autsajdera": ("dog",),
       "P3 + bez R16/QF": ("r16qf",), "P4 + bez hard ATP 250": ("hard250",),
       "P5 = P1+P2+P3": ("hole", "dog", "r16qf"), "P6 = P1+P2": ("hole", "dog")}
days = sorted(j.dkey.unique())
rows = []
for name, pol in POL.items():
    tick = []; singles = []
    for dd in days:
        d = j[j.dkey == dd]
        best = day_ticket(d, pol)
        e = eligible(d, pol)
        for r in e.itertuples():
            singles.append((dd, r.win * r.odds - 1))
        if not best:
            continue
        won = all(c["_win"] == 1 for c in best)
        odds = float(np.prod([c["_odds"] for c in best]))
        tick.append((dd, len(best), odds, won))
    T = pd.DataFrame(tick, columns=["d", "legs", "odds", "won"])
    S = pd.DataFrame(singles, columns=["d", "ret"])
    for per, cond in [("sve", lambda x: True), ("do 22.08", lambda x: str(x) < "2026-08-23"), ("od 23.08", lambda x: str(x) >= "2026-08-23")]:
        t = T[T.d.apply(cond)]; s = S[S.d.apply(cond)]
        roi_t = (t.won * t.odds).sum() / len(t) - 1 if len(t) else np.nan
        rows.append(dict(politika=name, razdoblje=per, tiketa=len(t), dobitnih=int(t.won.sum()) if len(t) else 0,
                         prosj_nogu=round(t.legs.mean(), 1) if len(t) else None, prosj_kvota=round(t.odds.mean(), 1) if len(t) else None,
                         ROI_tiketi=round(100 * roi_t, 1) if len(t) else None,
                         singlova=len(s), ROI_singlovi=round(100 * s.ret.mean(), 1) if len(s) else None))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(out.to_string(index=False))
out.to_csv(r"C:\Users\jovin\Desktop\Tenis Claude\.cache\rev2609\out_ticketsim.csv", index=False)
