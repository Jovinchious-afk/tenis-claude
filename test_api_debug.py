"""
Debug test — pokazuje sirovi API odgovor za sve ključne endpointe.
Pokreni: python test_api_debug.py
"""
import sys, os, json, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

KEY  = os.environ.get("RAPID_API_KEY", "")
BASE = "https://tennis-api-atp-wta-itf.p.rapidapi.com/tennis/v2"
HEADERS = {
    "x-rapidapi-key":  KEY,
    "x-rapidapi-host": "tennis-api-atp-wta-itf.p.rapidapi.com",
    "Content-Type":    "application/json",
}

def test(path, params=None, label=""):
    url = f"{BASE}{path}"
    print(f"\n{'='*60}")
    print(f"{'['+label+'] ' if label else ''}GET {url}")
    if params:
        print(f"Params: {params}")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"Status: {r.status_code}")
        try:
            data = r.json()
            # Prikaži strukturu odgovora
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
                inner = data.get("result", data.get("data", None))
                if isinstance(inner, list):
                    print(f"  → result je lista od {len(inner)} stavki")
                    if inner:
                        print(f"  → prva stavka keys: {list(inner[0].keys()) if isinstance(inner[0], dict) else type(inner[0])}")
                elif isinstance(inner, dict):
                    print(f"  → result je dict, keys: {list(inner.keys())}")
            elif isinstance(data, list):
                print(f"Direktna lista od {len(data)} stavki")
                if data:
                    print(f"  → prva stavka keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
            print(f"\nPrvih 800 znakova JSON-a:")
            print(json.dumps(data, indent=2)[:800])
        except Exception:
            print(f"Raw (prve 300 znakova): {r.text[:300]}")
    except Exception as e:
        print(f"Greška: {e}")

print("=" * 60)
print("DEBUG TEST — provjera ispravnih endpointa")
print(f"API KEY postavljen: {'DA (' + KEY[:8] + '...)' if KEY else 'NE!'}")
print("=" * 60)

# ── Fixtures ───────────────────────────────────────────────────────────────────
print("\n\n>>> FIXTURES (mečevi po datumu) <<<")
test("/atp/fixtures/2026-05-27", label="Fixtures danas")
test("/atp/fixtures/2026-05-28", label="Fixtures sutra")

# ── Rankings ──────────────────────────────────────────────────────────────────
print("\n\n>>> RANKINGS <<<")
test("/atp/ranking/singles", params={"pageSize": 10, "pageNo": 1}, label="Singles ranking p1")

# ── Player profile (Novak Djokovic = česti test player) ───────────────────────
# ID 1 je obično Djokovic na ovom API-ju, ali ćemo probati nekoliko
print("\n\n>>> PLAYER PROFILE <<<")
test("/atp/player/profile/1", label="Player profile id=1")
test("/atp/player/past-matches/1", label="Past matches id=1")
test("/atp/player/match-stats/1", label="Match stats id=1")
test("/atp/player/surface-summary/1", label="Surface summary id=1")
