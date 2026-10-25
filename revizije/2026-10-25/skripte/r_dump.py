# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — jednokratni dump baze (25.10.2026 10:21). SAMO CITA Supabase.

Isti postupak kao revizija 18.10.2026, samo u novi folder,
da je revizija ponovljiva i kad se baza promijeni: sve skripte r_*.py citaju ovaj dump.
    python revizije/2026-10-25/skripte/r_dump.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402

OUT = os.path.join(ROOT, ".cache", "rev_2026-10-25")
os.makedirs(OUT, exist_ok=True)


def pull(table, params):
    rows, off = [], 0
    while True:
        p = dict(params)
        p.update({"offset": str(off), "limit": "1000"})
        ch = db._rest("GET", table, params=p)
        if not isinstance(ch, list):
            print("ERR", table, ch)
            break
        rows += ch
        if len(ch) < 1000:
            break
        off += 1000
    return rows


if __name__ == "__main__":
    am = pull("analyzed_matches", {"select": "*", "order": "match_date.asc"})
    json.dump(am, open(os.path.join(OUT, "analyzed_matches.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    print("analyzed_matches:", len(am))
    for t in ["tickets", "ticket_matches", "player_scouting", "screenshot_odds", "market_lines", "model_weights"]:
        try:
            r = pull(t, {"select": "*"})
            json.dump(r, open(os.path.join(OUT, f"{t}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
            print(t, len(r))
        except Exception as e:  # noqa: BLE001
            print(t, "ERR", e)
