# Revizija 26.09.2026 — samo CITANJE iz Supabasea u lokalni kes. Nista se ne upisuje.
import os, sys, json, time, requests
from dotenv import load_dotenv
ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
load_dotenv(os.path.join(ROOT, ".env"))
URL = os.environ["SUPABASE_URL"].rstrip("/"); KEY = os.environ["SUPABASE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
OUT = os.path.join(ROOT, ".cache", "rev2609", "data")

def fetch_all(table, select="*", order="id", page=1000):
    rows, off = [], 0
    while True:
        hh = dict(H); hh["Range-Unit"] = "items"; hh["Range"] = f"{off}-{off+page-1}"
        r = requests.get(f"{URL}/rest/v1/{table}", headers=hh,
                         params={"select": select, "order": order}, timeout=60)
        if r.status_code not in (200, 206):
            print(table, "ERR", r.status_code, r.text[:300]); break
        chunk = r.json()
        rows.extend(chunk)
        if len(chunk) < page: break
        off += page
    return rows

tables = sys.argv[1:] or ["analyzed_matches", "ticket_matches", "tickets", "model_weights",
          "player_scouting", "tournament_history", "player_match_history", "screenshot_odds",
          "performance_log", "elo_cache", "market_lines"]
for t in tables:
    t0 = time.time()
    order = {"player_scouting": "player_name", "elo_cache": "player_name",
             "player_match_history": "match_key", "screenshot_odds": "match_date"}.get(t, "id")
    rows = fetch_all(t, order=order)
    with open(os.path.join(OUT, f"{t}.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"{t}: {len(rows)} redaka ({time.time()-t0:.1f}s)")
