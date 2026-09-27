# -*- coding: utf-8 -*-
"""Povijesni laboratorij — pitanje 1: naši mečevi naspram zatvorne tržišne cijene (27.09.2026 11:43).

SAMO ČITA Supabase (analyzed_matches, ticket_matches, tickets) i lokalni tennis-data.
Pragovi: revizije/2026-09-27/PRAGOVI_POVIJESNI_LAB.md (pitanje 1 je dijagnoza, bez praga;
KONS na zatvornoj cijeni s ogradom zapisanom unaprijed).

Poštena cijena = zatvorna tennis-data cijena bez marže (Pinnacle gdje postoji, inače Avg).
SuperSport cijena = obje kvote sa screenshota (bookmaker_odds_p1/p2), jutarnja.
"""
import json
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_data import ROOT, LAB_CACHE, load_td, letters, full_matches_td, devig  # noqa: E402

sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402


def fetch(table, select, filters=None):
    out, off = [], 0
    while True:
        params = {"select": select, "offset": str(off), "limit": "1000"}
        params.update(filters or {})
        chunk = db._rest("GET", table, params=params)
        out.extend(chunk)
        if len(chunk) < 1000:
            return out
        off += 1000


def name_ok(full, key):
    fl = letters(full)
    return full_matches_td(fl, key) or (len(key[0]) >= 5 and key[0] in fl)


def join(rows, td, p1k="player1", p2k="player2", datek="match_date"):
    """Svakom našem retku nađi tennis-data meč: isti par (bilo koji redoslijed), datum ±3 dana
    (naš datum i stvarni se razlikuju u ~23% slučajeva, vidi memoriju 'curenje-iz-povijesti')."""
    td = td.sort_values("Date")
    by_day = {}
    for i, d in zip(td.index, td["Date"]):
        by_day.setdefault(d.date(), []).append(i)
    out = []
    for r in rows:
        try:
            d0 = pd.Timestamp(str(r[datek])[:10])
        except Exception:
            out.append(None)
            continue
        hit = None
        for k in (0, -1, 1, -2, 2, -3, 3):
            for i in by_day.get((d0 + pd.Timedelta(days=k)).date(), []):
                wk, lk = td.at[i, "wkey"], td.at[i, "lkey"]
                a, b = r[p1k] or "", r[p2k] or ""
                if (name_ok(a, wk) and name_ok(b, lk)) or (name_ok(a, lk) and name_ok(b, wk)):
                    hit = i
                    break
            if hit is not None:
                break
        out.append(hit)
    return out


def mean_ci(xs):
    n = len(xs)
    if n < 2:
        return (sum(xs) / n if n else float("nan")), float("nan"), float("nan"), n
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m, m - 1.96 * sd / math.sqrt(n), m + 1.96 * sd / math.sqrt(n), n


def main():
    td = load_td()
    am = fetch("analyzed_matches",
               "match_date,player1,player2,predicted_winner,actual_winner,prediction_correct,"
               "bookmaker_odds_p1,bookmaker_odds_p2,tournament,tournament_level,round,predicted_confidence",
               {"prediction_correct": "not.is.null", "order": "match_date.asc"})
    am = [r for r in am if r.get("predicted_winner") in (r.get("player1"), r.get("player2"))
          and r.get("actual_winner") in (r.get("player1"), r.get("player2"))]
    hits = join(am, td)
    print(f"razriješenih analiza s pickom: {len(am)} | nađeno u tennis-data: {sum(h is not None for h in hits)} "
          f"(tennis-data 2026 ide do {td['Date'].max().date()})")

    rows = []
    for r, h in zip(am, hits):
        if h is None:
            continue
        m = td.loc[h]
        pick, p1 = r["predicted_winner"], r["player1"]
        opp = r["player2"] if pick == p1 else p1
        o_pick = float(r["bookmaker_odds_p1"] or 0) if pick == p1 else float(r["bookmaker_odds_p2"] or 0)
        o_opp = float(r["bookmaker_odds_p2"] or 0) if pick == p1 else float(r["bookmaker_odds_p1"] or 0)
        p_ss = devig(o_pick, o_opp)
        if p_ss is None:
            continue
        pick_is_w = name_ok(pick, m["wkey"]) and not name_ok(pick, m["lkey"])
        pick_is_l = name_ok(pick, m["lkey"]) and not name_ok(pick, m["wkey"])
        if pick_is_w == pick_is_l:
            continue
        pf = m["p_fair"] if pick_is_w else 1 - m["p_fair"]
        avg_pick = m["AvgW"] if pick_is_w else m["AvgL"]
        won = 1 if r["prediction_correct"] else 0
        # provjera poravnanja: ishod iz naše baze mora se slagati s tennis-data pobjednikom
        if won != (1 if pick_is_w else 0):
            continue
        rows.append({"date": str(r["match_date"])[:10], "level": r.get("tournament_level") or "",
                     "series": m["Series"], "odds": o_pick, "p_ss": p_ss, "pf": pf, "won": won,
                     "ss_over": 1 / o_pick + 1 / o_opp - 1,
                     "avg_over": 1 / m["AvgW"] + 1 / m["AvgL"] - 1 if m["AvgW"] and m["AvgL"] else None,
                     "avg_pick": avg_pick, "src": m["fair_src"], "conf": r.get("predicted_confidence")})
    q = pd.DataFrame(rows)
    out = {"n_spojeno": len(q)}
    print(f"poravnato i provjereno (ishod se slaže): {len(q)}\n")

    so = mean_ci(list(q["ss_over"]))
    ao = mean_ci([x for x in q["avg_over"] if x is not None and not pd.isna(x)])
    print(f"MARŽA na istim mečevima: SuperSport {100*so[0]:.2f}%  |  prosjek kladionica {100*ao[0]:.2f}%")
    better = (q["odds"] > q["avg_pick"]).mean()
    print(f"naš pick: SuperSport kvota viša od prosjeka kladionica u {100*better:.0f}% slučajeva; "
          f"medijan omjera {q['odds'].div(q['avg_pick']).median():.3f}")
    out["marza_ss"], out["marza_avg"], out["ss_bolji_od_avg"] = 100 * so[0], 100 * ao[0], 100 * better

    ev = [o * p - 1 for o, p in zip(q["odds"], q["pf"])]
    m, lo, hi, n = mean_ci(ev)
    print(f"EV naših pickova po SuperSport kvoti (zatvorna poštena cijena): {100*m:+.1f}% [{100*lo:+.1f}, {100*hi:+.1f}] n={n}; "
          f"EV>0 u {100*sum(e > 0 for e in ev)/n:.0f}%")
    out["ev"] = {"m": 100 * m, "lo": 100 * lo, "hi": 100 * hi, "n": n}

    e_close = mean_ci([w - p for w, p in zip(q["won"], q["pf"])])
    e_ss = mean_ci([w - p for w, p in zip(q["won"], q["p_ss"])])
    print(f"edge naših pickova naspram ZATVORNE poštene cijene: {100*e_close[0]:+.1f}pp [{100*e_close[1]:+.1f}, {100*e_close[2]:+.1f}]")
    print(f"edge naših pickova naspram devig SUPERSPORT cijene:  {100*e_ss[0]:+.1f}pp [{100*e_ss[1]:+.1f}, {100*e_ss[2]:+.1f}]")
    roi = mean_ci([w * o - 1 for w, o in zip(q["won"], q["odds"])])
    print(f"ROI naših pickova po SuperSport kvoti (svaki pick zasebno): {100*roi[0]:+.1f}% [{100*roi[1]:+.1f}, {100*roi[2]:+.1f}]")
    out["edge_close"], out["edge_ss"], out["roi"] = e_close[:3], e_ss[:3], roi[:3]

    print("\npo razini turnira (tennis-data Series):")
    out["po_razini"] = {}
    for s, g in q.groupby("series"):
        ev_s = mean_ci([o * p - 1 for o, p in zip(g["odds"], g["pf"])])
        ec = mean_ci([w - p for w, p in zip(g["won"], g["pf"])])
        print(f"  {s:13s} n={len(g):3d}  marža SS {100*g['ss_over'].mean():.2f}%  EV {100*ev_s[0]:+.1f}%  "
              f"edge naspram zatvorne {100*ec[0]:+.1f}pp")
        out["po_razini"][s] = {"n": len(g), "marza": 100 * g["ss_over"].mean(), "ev": 100 * ev_s[0], "edge": 100 * ec[0]}

    # KONS na zatvornoj cijeni: gap = poštena − devig SuperSport za naš pick
    q["gap"] = 100 * (q["pf"] - q["p_ss"])
    print("\nKONS na zatvornoj cijeni (gap = zatvorna poštena − devig SuperSport, za naš pick):")
    out["kons"] = {}
    for name, mask in (("gap >= +1pp", q["gap"] >= 1), ("gap < +1pp", q["gap"] < 1)):
        g = q[mask]
        e = mean_ci([w - p for w, p in zip(g["won"], g["p_ss"])])
        r_ = mean_ci([w * o - 1 for w, o in zip(g["won"], g["odds"])])
        print(f"  {name:12s} n={len(g):3d}  gap {g['gap'].mean():+5.2f}pp  edge naspram SS {100*e[0]:+5.1f}pp "
              f"[{100*e[1]:+.1f}, {100*e[2]:+.1f}]  ROI {100*r_[0]:+5.1f}%")
        out["kons"][name] = {"n": len(g), "gap": g["gap"].mean(), "edge": 100 * e[0], "lo": 100 * e[1],
                             "hi": 100 * e[2], "roi": 100 * r_[0]}

    # Prave noge tiketa (stvarne oklade)
    legs = fetch("ticket_matches", "ticket_id,player1,player2,pick,odds,match_date,tournament_level,result")
    tk = {t["id"]: t for t in fetch("tickets", "id,status,ticket_date")}
    legs = [l for l in legs if (tk.get(l["ticket_id"]) or {}).get("status") in ("won", "lost", "pending")]
    lh = join(legs, td)
    evl = []
    for l, h in zip(legs, lh):
        if h is None:
            continue
        m = td.loc[h]
        pw = name_ok(l["pick"], m["wkey"]) and not name_ok(l["pick"], m["lkey"])
        pl = name_ok(l["pick"], m["lkey"]) and not name_ok(l["pick"], m["wkey"])
        if pw == pl:
            continue
        pf = m["p_fair"] if pw else 1 - m["p_fair"]
        evl.append(float(l["odds"]) * pf - 1)
    if evl:
        m_, lo_, hi_, n_ = mean_ci(evl)
        print(f"\nNOGE PRAVIH TIKETA: {len(legs)} ukupno, {n_} nađeno u tennis-data; EV po SuperSport kvoti "
              f"{100*m_:+.1f}% [{100*lo_:+.1f}, {100*hi_:+.1f}]; EV>0 u {100*sum(e > 0 for e in evl)/n_:.0f}%")
        out["noge"] = {"n": n_, "ev": 100 * m_, "lo": 100 * lo_, "hi": 100 * hi_}
    with open(os.path.join(LAB_CACHE, "lab_q1.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
