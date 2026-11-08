# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — simulacija NOVOG toka tiketa (nos-odluka + nos-autsajder) na danima Pariza (08.11.2026 12:50).

Za svaki dan D (02.–07.11.) predikcije se rekonstruiraju iz zadnjih spremljenih analiza mečeva s datumom D
i D+1 (približno: baza čuva ZADNJU analizu svakog meča), težine nosa uče se SAMO na pickovima prije D
(hod naprijed), pa se uspoređuje izbor bez nosa (`predlozi_bez_pregleda`) i s nosom (`primijeni` +
`_select_combo` s nos-autsajderima). Claudeov pregled i sažetak se NE pozivaju (plaćeni pozivi), pa je to
provjera TOKA i LOGIKE, ne vjerna reprodukcija stvarnih tiketa. Ishod nogu iz baze.
    python revizije/2026-11-08/skripte/r_nos_tiket_sim.py
"""
import contextlib
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from agent import nos_odluka as no  # noqa: E402
from agent import ticket_builder as tb  # noqa: E402
from config.model_config import TICKET_CONFIG  # noqa: E402

sys.path.insert(0, HERE)
from r_nos_replay import primjer  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-08", "analyzed_matches.json")
DANI = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07"]


def pred_iz_retka(r):
    cs = copy.deepcopy(r.get("context_snapshot") or {})
    conf = float(r.get("predicted_confidence") or 0)
    m = {"player1": r["player1"], "player2": r["player2"], "odds_p1": r.get("bookmaker_odds_p1"),
         "odds_p2": r.get("bookmaker_odds_p2"), "odds_available": True, "tournament": r.get("tournament"),
         "level": r.get("tournament_level"), "surface": r.get("surface"), "round": r.get("round"),
         "date": str(r.get("match_date"))[:10]}
    return {"pick": r["predicted_winner"], "confidence": conf, "fair_odds": round(100 / conf, 3) if conf else None,
            "match": m, "context_snapshot": cs, "skip_reason": None, "value": r.get("value_detected"),
            "measured_penalties": cs.get("measured_penalties"), "risk_level": "srednji", "key_factors": [],
            "_win": r.get("actual_winner")}


def ishod(combo):
    if not combo:
        return "—"
    res = []
    for p in combo:
        aw = p.get("_win")
        res.append("✓" if aw == p["pick"] else ("✗" if aw else "?"))
    odds = tb.combined_odds([tb._pick_odds(p) for p in combo])
    dob = "DOBITAN" if all(x == "✓" for x in res) else ("izgubljen" if "✗" in res else "?")
    return f"{len(combo)} noge @{odds:.2f} {''.join(res)} -> {dob}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(DUMP, encoding="utf-8"))
    ex = [e for e in (primjer(r) for r in rows) if e]
    for d in DANI:
        d1 = DANI[DANI.index(d) + 1] if DANI.index(d) + 1 < len(DANI) else "2026-11-08"
        day_rows = [r for r in rows if str(r.get("match_date"))[:10] in (d, d1)
                    and r.get("predicted_winner") and r.get("predicted_confidence")]
        preds = [pred_iz_retka(r) for r in day_rows]
        t = no.nauci([dict(e) for e in ex], danas=d)
        with contextlib.redirect_stdout(io.StringIO()):
            stari = tb.predlozi_bez_pregleda(preds)
            dogs = no.primijeni(preds, t)
            novi, _ = tb._select_combo(preds, dict(TICKET_CONFIG), dogs)
        gore = sum(1 for p in preds if (p.get("_nos_model") or {}).get("confidence", 99) < 63 <= p["confidence"])
        print(f"{d}: {len(preds)} predikcija | nos preko praga {gore} | kandidata za autsajdera {len(dogs)}")
        print(f"   bez nosa: {ishod(stari)}" + (f"  [{', '.join(p['pick'] for p in stari)}]" if stari else ""))
        print(f"   s nosom : {ishod(novi)}" + (f"  [{', '.join(p['pick'] + (' (NOS-AUTSAJDER)' if p.get('nos_autsajder') else '') for p in novi)}]" if novi else ""))
        no.vrati_model(preds)


if __name__ == "__main__":
    main()
