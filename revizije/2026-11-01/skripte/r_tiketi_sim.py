# -*- coding: utf-8 -*-
"""Revizija 01.11.2026 — D4: simulacija ograničenja pojasa kvote na tiketu (točka 4) na ISTIM
mečevima (01.11.2026 13:29; po uzoru na reviziju 18.10.2026 `b_tiketi_sim.py`).

Pragovi: PRAGOVI_REVIZIJA_2026-11-01.md, točka D4 (13:05). Bazen = analize spremljene na dan runa
(`created_at`, UTC datum) od 08.09.2026 do 31.10.2026. Kombinaciju bira ista logika kao
`ticket_builder._find_best_combination` (pravi `_score_combo`, prave zone opreza za hard i clay),
uz JEDNO dodatno ograničenje po varijanti. Prag po datumu (60 od 08.09. do 04.10., inače 63),
bonus za konsenzus 4 do 17.10. (ugašen 18.10.2026).

ŠTO JE PRIBLIŽNO (kao 18.10.): redak analize zna biti prepisan kad se par analizira ponovno;
AI recenzent tiketa se ne poziva; filtri koji traže polja kojih u bazi nema se ne primjenjuju.
Zato se prvo mjeri koliko V0 reproducira stvarne tikete.

Mjere: dani s tiketom, prosjek nogu i kvote, očekivana šansa (umnožak devigiranih cijena),
očekivani povrat (šansa × kvota − 1), ostvareno. Kriterij (18.10., T): varijanta je zanimljiva
samo uz >= +5pp očekivanog povrata i <= 30% manje dana s tiketom. Samo čita lokalni dump.
    python revizije/2026-11-01/skripte/r_tiketi_sim.py
"""
import itertools
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
os.environ.setdefault("ANTHROPIC_API_KEY", "nije-potreban-za-simulaciju")
from agent import ticket_builder as tb  # noqa: E402
from config.model_config import DAILY_MATCH_LIMITS, TICKET_CONFIG  # noqa: E402
from utils.helpers import combined_odds  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-01")
OD, DO = "2026-09-08", "2026-10-31"
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
    days = sorted({str(t["ticket_date"])[:10] for t in tk if OD <= str(t["ticket_date"])[:10] <= DO})
    real = {str(t["ticket_date"])[:10]: t for t in tk if t.get("status") in ("won", "lost", "pending")}
    legs = defaultdict(list)
    for m in tm:
        legs[m["ticket_id"]].append(m)
    pool = defaultdict(list)
    for r in am:
        d = str(r.get("created_at") or "")[:10]
        if not (OD <= d <= DO):
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
    return 60.0 if "2026-09-08" <= day <= "2026-10-04" else 63.0


def eligible(p, day):
    m = p["match"]
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


def in_band(p, band):
    o = tb._pick_odds(p)
    return band[0] <= o < band[1]


def find_best(cands, cfg, band=None, max_in_band=None):
    """Ista logika kao tb._find_best_combination + jedno dodatno ograničenje pojasa."""
    if band is not None and max_in_band == 0:
        cands = [p for p in cands if not in_band(p, band)]
    best, best_score = None, -1
    for n in range(cfg["max_matches"], cfg["min_matches"] - 1, -1):
        if n > len(cands):
            continue
        for combo in itertools.combinations(cands, n):
            if any(tb._pick_odds(p) < 1.06 for p in combo):
                continue
            odds = combined_odds([tb._pick_odds(p) for p in combo])
            if odds < cfg["min_combined_odds"] or odds > cfg["max_combined_odds"]:
                continue
            if tb._clay_dead_zone_count(combo) > tb._CLAY_DEAD_ZONE_MAX:
                continue
            if tb._hard_caution_zone_count(combo) > tb._HARD_CAUTION_ZONE_MAX:
                continue
            if band is not None and max_in_band and sum(1 for p in combo if in_band(p, band)) > max_in_band:
                continue
            score = tb._score_combo(combo)
            if score > best_score:
                best_score, best = score, list(combo)
    return best


def build(pool, day, var):
    preds = pool.get(day, [])
    if len(preds) < 4:
        return None
    cands = daily_limits([p for p in preds if eligible(p, day)], day)
    cfg = dict(TICKET_CONFIG)
    cfg.update({"min_matches": 3, "max_matches": 6, "min_combined_odds": 4.0, "max_combined_odds": 50.0})
    old_bonus, old_min = tb._CONSENSUS_GAP_BONUS, tb.TICKET_CONFIG["min_matches"]
    tb._CONSENSUS_GAP_BONUS = 4.0 if day < "2026-10-18" else 0.0
    tb.TICKET_CONFIG["min_matches"] = 3
    try:
        return find_best(cands, cfg, var.get("band"), var.get("max"))
    finally:
        tb._CONSENSUS_GAP_BONUS, tb.TICKET_CONFIG["min_matches"] = old_bonus, old_min


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


VARIANTS = [
    ("V0 kako je bilo", {}),
    ("B1 bez nogu 1,35-1,45", {"band": (1.35, 1.45), "max": 0}),
    ("B2 najviše 1 noga 1,35-1,45", {"band": (1.35, 1.45), "max": 1}),
    ("B3 bez nogu 1,50-1,65", {"band": (1.50, 1.65), "max": 0}),
    ("B4 najviše 1 noga 1,50-1,65", {"band": (1.50, 1.65), "max": 1}),
    ("B5 bez nogu >= 1,65", {"band": (1.65, 99.0), "max": 0}),
    ("B6 najviše 1 noga >= 1,65", {"band": (1.65, 99.0), "max": 1}),
]


def main():
    days, real, legs, pool = load()
    print(f"dani runa {OD} – {DO}: {len(days)} | s pravim tiketom: {sum(d in real for d in days)}")
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
    print(f"{'varijanta':34s} dana  nogu  kvota   oček.šansa  oček.povrat  ostvareno")
    out, base = {}, None
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
            print(f"{name:34s}    0")
            continue
        legs_m = sum(r["n"] for r in rows) / n
        odds_m = sum(r["odds"] for r in rows) / n
        p_m = sum(r["p"] for r in rows) / n
        ev_m = sum(r["p"] * r["odds"] - 1 for r in rows) / n
        done = [r for r in rows if r["res"] is not None]
        won = sum(1 for r in done if r["res"])
        exp_won = sum(r["p"] for r in done)
        roi = (sum((r["odds"] - 1) if r["res"] else -1 for r in done) / len(done)) if done else float("nan")
        if base is None:
            base = (n, ev_m)
        verdict = ""
        if base and name != "V0 kako je bilo":
            dd = 100 * (n - base[0]) / base[0]
            dev = 100 * (ev_m - base[1])
            verdict = f"  | dana {dd:+.0f}%, oček. povrat {dev:+.1f}pp -> {'ZANIMLJIVO' if (dev >= 5 and dd >= -30) else 'ne'}"
        print(f"{name:34s} {n:4d}  {legs_m:4.1f}  {odds_m:5.2f}   {100 * p_m:6.1f}%    {100 * ev_m:+6.1f}%    "
              f"{won}/{len(done)} (oček. {exp_won:.1f}), ROI {100 * roi:+.0f}%{verdict}")
        out[name] = {"rows": rows, "days": n, "legs": legs_m, "odds": odds_m, "p": p_m, "ev": ev_m,
                     "won": won, "done": len(done), "exp_won": exp_won, "roi": roi}
    json.dump(out, open(os.path.join(DUMP, "tiketi_sim.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
