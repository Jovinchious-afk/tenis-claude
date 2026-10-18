# -*- coding: utf-8 -*-
"""Revizija 18.10.2026, drugi dio — simulacija pravila tiketa na ISTIM mečevima (18.10.2026 12:31).

Pragovi: PRAGOVI_B_2026-10-18.md (12:20), točka T. Bazen = analize spremljene na dan runa
(`created_at`, UTC datum) od 08.09.2026 (od tada 3–6 parova). Kombinaciju bira PRAVI kod
(`ticket_builder._find_best_combination` + `_score_combo`); mijenja se samo konfiguracija.

ŠTO JE PRIBLIŽNO (zapisano unaprijed):
  - redak analize zna biti prepisan kad se par analizira ponovno (24 od 141 noge, jutros) —
    simulacija vidi zadnju verziju retka;
  - AI recenzent tiketa (plaćeni poziv) se ne poziva, a on zna zamijeniti nogu;
  - filtri koji traže polja kojih u bazi nema (oba igrača u padu, clay umor, value-override)
    se ne primjenjuju; dnevna ograničenja i GS prag 65 se primjenjuju.
Zato se prvo mjeri koliko V0 reproducira stvarne tikete.

Mjere: dani s tiketom, prosjek nogu i kvote, očekivana šansa (umnožak devigiranih cijena),
očekivani povrat (šansa × kvota − 1), ostvareni ishod. Samo čita lokalni dump.
    python revizije/2026-10-18/skripte/b_tiketi_sim.py
"""
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
os.environ.setdefault("ANTHROPIC_API_KEY", "nije-potreban-za-simulaciju")
from agent import ticket_builder as tb  # noqa: E402
from config.model_config import DAILY_MATCH_LIMITS, TICKET_CONFIG  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-10-18b")
OD = "2026-09-08"
NON_TICKET = ("challenger", "qualifying", "itf", "future", "davis")


def devig(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    return (1 / a) / (1 / a + 1 / b) if a > 1 and b > 1 else None


def load():
    am = json.load(open(os.path.join(DUMP, "analyzed_matches.json"), encoding="utf-8"))
    tk = json.load(open(os.path.join(DUMP, "tickets.json"), encoding="utf-8"))
    tm = json.load(open(os.path.join(DUMP, "ticket_matches.json"), encoding="utf-8"))
    days = sorted({str(t["ticket_date"])[:10] for t in tk if str(t["ticket_date"])[:10] >= OD})
    real = {str(t["ticket_date"])[:10]: t for t in tk if t.get("status") != "analysis_only"}
    legs = defaultdict(list)
    for m in tm:
        legs[m["ticket_id"]].append(m)
    pool = defaultdict(list)
    for r in am:
        d = str(r.get("created_at") or "")[:10]
        if d < OD:
            continue
        pick, p1, p2 = r.get("predicted_winner"), r.get("player1"), r.get("player2")
        conf = r.get("predicted_confidence")
        o1, o2 = r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")
        if not pick or pick not in (p1, p2) or not isinstance(conf, (int, float)):
            continue
        cs = r.get("context_snapshot") or {}
        pred = {"pick": pick, "confidence": float(conf),
                "fair_odds": r.get("predicted_fair_odds") or (100.0 / conf if conf else None),
                "match": {"player1": p1, "player2": p2, "odds_p1": o1, "odds_p2": o2,
                          "surface": r.get("surface") or "", "level": r.get("tournament_level") or "",
                          "tournament": r.get("tournament") or "", "date": str(r.get("match_date"))[:10],
                          "market_p": cs.get("market_p")},
                "_win": r.get("prediction_correct"), "_id": r.get("id")}
        pool[d].append(pred)
    return days, real, legs, pool


def thr_hist(day):
    """Prag koji je STVARNO vrijedio na dan runa (ispravak 18.10.2026 15:06 po kritičaru): 60 od
    08.09.2026 12:07 do 04.10.2026 19:22, inače 63. Bez ovoga V0 je reproducirao samo 2 od 13 tiketa."""
    return 60.0 if "2026-09-08" <= day <= "2026-10-04" else 63.0


def eligible(p, thr, day):
    m = p["match"]
    if thr == "hist":
        thr = thr_hist(day)
    if any(k in (m["level"] or "").lower() for k in NON_TICKET):
        return False
    try:
        if not (float(m["odds_p1"]) > 1 and float(m["odds_p2"]) > 1):
            return False
    except (TypeError, ValueError):
        return False
    if p["confidence"] < 50:
        return False
    need = 65.0 if ("grand slam" in m["level"].lower() and "hard" in m["surface"].lower()) else thr
    return p["confidence"] >= max(thr, need)


def daily_limits(cands, day):
    groups = defaultdict(list)
    for p in cands:
        groups[(p["match"]["tournament"], p["match"]["date"])].append(p)
    out = []
    for (t, d), g in groups.items():
        lim = DAILY_MATCH_LIMITS.get(g[0]["match"]["level"], {"today": 2, "tomorrow": 2})
        k = lim["today"] if d == day else lim["tomorrow"]
        out += sorted(g, key=lambda p: p["confidence"], reverse=True)[:k]
    return out


def build(pool, day, var):
    preds = pool.get(day, [])
    if len(preds) < 4:                      # run_daily: < 4 valjanih -> samo analiza
        return None
    cands = daily_limits([p for p in preds if eligible(p, var["thr"], day)], day)
    cfg = dict(TICKET_CONFIG)
    cfg.update({"min_matches": var["min"], "max_matches": var["max"],
                "min_combined_odds": var["omin"], "max_combined_odds": var["omax"]})
    old_bonus, old_min = tb._CONSENSUS_GAP_BONUS, tb.TICKET_CONFIG["min_matches"]
    tb._CONSENSUS_GAP_BONUS = var["bonus"]
    tb.TICKET_CONFIG["min_matches"] = var["min"]
    try:
        combo = tb._find_best_combination(cands, cfg)
    finally:
        tb._CONSENSUS_GAP_BONUS, tb.TICKET_CONFIG["min_matches"] = old_bonus, old_min
    return combo


def evaluate(combo):
    odds, p_t, res = 1.0, 1.0, True
    for p in combo:
        m = p["match"]
        is1 = p["pick"] == m["player1"]
        op, oo = (m["odds_p1"], m["odds_p2"]) if is1 else (m["odds_p2"], m["odds_p1"])
        odds *= float(op)
        p_t *= devig(op, oo)
        if p["_win"] is None:
            res = None
        elif res is not None:
            res = res and bool(p["_win"])
    return odds, p_t, res


VARIANTS = [   # "hist" = prag koji je stvarno vrijedio (60 od 08.09. do 04.10., inače 63)
    ("V0 kako je bilo: prag po datumu, 3-6, 4-50, bonus 4", dict(thr="hist", min=3, max=6, omin=4.0, omax=50.0, bonus=4.0)),
    ("V1 isto, bez bonusa za konsenzus (provedeno 18.10.)", dict(thr="hist", min=3, max=6, omin=4.0, omax=50.0, bonus=0.0)),
    ("V2 prag 60 cijelo vrijeme", dict(thr=60, min=3, max=6, omin=4.0, omax=50.0, bonus=0.0)),
    ("V3 prag 63 cijelo vrijeme", dict(thr=63, min=3, max=6, omin=4.0, omax=50.0, bonus=0.0)),
    ("V3b prag 66 cijelo vrijeme", dict(thr=66, min=3, max=6, omin=4.0, omax=50.0, bonus=0.0)),
    ("V4 samo 3 noge, kvota 4-6 (prag po datumu)", dict(thr="hist", min=3, max=3, omin=4.0, omax=6.0, bonus=0.0)),
    ("V5 4-6 noga, bez trojca (prag po datumu)", dict(thr="hist", min=4, max=6, omin=4.0, omax=50.0, bonus=0.0)),
    ("V6 kvota 5-8 (prag po datumu)", dict(thr="hist", min=3, max=6, omin=5.0, omax=8.0, bonus=0.0)),
]


def main():
    days, real, legs, pool = load()
    print(f"dani runa od {OD}: {len(days)} | s pravim tiketom: {sum(d in real for d in days)}")
    # 1) koliko V0 reproducira stvarni tiket
    same, part, tot = 0, 0, 0
    for d in days:
        if d not in real:
            continue
        tot += 1
        combo = build(pool, d, VARIANTS[0][1])
        rl = {(m["pick"], frozenset([m["player1"], m["player2"]])) for m in legs[real[d]["id"]]}
        sl = {(p["pick"], frozenset([p["match"]["player1"], p["match"]["player2"]])) for p in (combo or [])}
        if sl == rl:
            same += 1
        elif sl & rl:
            part += 1
    print(f"V0 reproducira stvarni tiket: isto {same}/{tot}, djelomično {part}/{tot}\n")
    # 2) varijante
    print(f"{'varijanta':52s} dana  nogu  kvota   oček.šansa  oček.povrat  ostvareno")
    out = {}
    for name, var in VARIANTS:
        rows = []
        for d in days:
            combo = build(pool, d, var)
            if combo:
                o, p_t, res = evaluate(combo)
                rows.append({"day": d, "n": len(combo), "odds": o, "p": p_t, "res": res,
                             "legs": [p["pick"] for p in combo]})
        n = len(rows)
        if not n:
            print(f"{name:52s}    0")
            continue
        legs_m = sum(r["n"] for r in rows) / n
        odds_m = sum(r["odds"] for r in rows) / n
        p_m = sum(r["p"] for r in rows) / n
        ev_m = sum(r["p"] * r["odds"] - 1 for r in rows) / n
        done = [r for r in rows if r["res"] is not None]
        won = sum(1 for r in done if r["res"])
        exp_won = sum(r["p"] for r in done)
        roi = (sum((r["odds"] - 1) if r["res"] else -1 for r in done) / len(done)) if done else float("nan")
        print(f"{name:52s} {n:4d}  {legs_m:4.1f}  {odds_m:5.2f}   {100 * p_m:6.1f}%    {100 * ev_m:+6.1f}%    "
              f"{won}/{len(done)} (oček. {exp_won:.1f}), ROI {100 * roi:+.0f}%")
        out[name] = {"rows": rows, "days": n, "legs": legs_m, "odds": odds_m, "p": p_m, "ev": ev_m,
                     "won": won, "done": len(done), "exp_won": exp_won, "roi": roi}
    # 3) čista matematika: šansa tiketa uz poštene noge i maržu 4,5% po nozi
    print("\nMatematika (noge pošteno cijenjene, marža 4,5% po nozi): šansa tiketa i očekivani povrat")
    for total in (4.0, 5.0, 8.0):
        line = []
        for k in (3, 4, 5, 6):
            p_t = (1 / total) * (1 / 1.045) ** k
            line.append(f"{k} noge {100 * p_t:4.1f}% / {100 * (p_t * total - 1):+5.1f}%")
        print(f"  ukupna kvota {total:.0f}: " + " | ".join(line))
    json.dump(out, open(os.path.join(DUMP, "b_tiketi_sim.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
