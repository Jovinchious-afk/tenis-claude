# -*- coding: utf-8 -*-
"""Oznaka `elo_suspect` u context_snapshot za analize s Munarovim krivim ELO-om (04.10.2026 19:21).

Korisnik odobrio (popravak ELO-a, tocka 1). Dodaje se SAMO kljuc `elo_suspect`; ostatak
snapshota ostaje netaknut. measure_candidates.py takve retke preskace.
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db

NAME = "Jaume Antoni Munar Clar"
rows = []
for col in ("player1", "player2"):
    rows += db._rest("GET", "analyzed_matches", params={"select": "id,match_date,player1,player2,context_snapshot",
                                                        col: f"eq.{NAME}"})
print("analiza s Munarom:", len(rows))
done = 0
for r in rows:
    cs = dict(r.get("context_snapshot") or {})
    side = "p1" if r["player1"] == NAME else "p2"
    cs["elo_suspect"] = {"player": NAME, "side": side,
                         "used": [cs.get(f"{side}_elo_overall"), cs.get(f"{side}_elo_surface")],
                         "true_cache_04_10": [1766.7, 1748.0],
                         "reason": "find_player_elo pogodio 'jay clarke' (revizija 04.10.2026)",
                         "flagged": "04.10.2026"}
    out = db._rest("PATCH", "analyzed_matches", params={"id": f"eq.{r['id']}"},
                   body={"context_snapshot": cs}, prefer="return=representation")
    ok = bool(out) and (out[0].get("context_snapshot") or {}).get("elo_suspect", {}).get("player") == NAME
    done += ok
    print(f"  {str(r['match_date'])[:10]} {r['player1']} - {r['player2']}: {'OK' if ok else 'NIJE'}")
print("oznaceno:", done, "od", len(rows))
