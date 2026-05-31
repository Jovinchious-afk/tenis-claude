"""
ELO Cache Updater — run locally (not on GitHub Actions).
Scrapes Tennis Abstract ELO ratings and stores them in Supabase.

Usage:
    python scripts/update_elo_cache.py

Run once a week or before important tournaments.
Tennis Abstract updates weekly so more frequent is unnecessary.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup
from database import supabase_client as db


def _safe_float(val):
    try:
        return float(str(val).replace(",", ".").strip())
    except Exception:
        return None


def scrape_elo() -> list:
    url = "https://www.tennisabstract.com/reports/atp_elo_ratings.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tennisabstract.com/",
    }
    print("Fetching Tennis Abstract ELO ratings...")
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table", {"id": "reportable"}) or soup.find("table")
    if not table:
        print("ERROR: Table not found in page.")
        return []

    # Detect column indices from header
    # Expected: ELO Rank | Player | Age | Elo | hElo Rank | hElo | cElo Rank | cElo | gElo Rank | gElo
    col = {"name": 1, "elo": 3, "hard": 5, "clay": 7, "grass": 9}
    header_row = table.find("tr")
    if header_row:
        hdrs = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        for i, h in enumerate(hdrs):
            if "player" in h or "name" in h:
                col["name"] = i
            elif h == "elo":
                col["elo"] = i
            elif h == "helo":
                col["hard"] = i
            elif h == "celo":
                col["clay"] = i
            elif h == "gelo":
                col["grass"] = i

    entries = []
    for row in table.find_all("tr")[1:600]:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        name = cols[col["name"]].get_text(strip=True) if len(cols) > col["name"] else ""
        if not name:
            continue

        def _val(idx):
            if len(cols) <= idx:
                return None
            v = _safe_float(cols[idx].get_text(strip=True))
            return v if v and v > 500 else None

        elo_overall = _val(col["elo"]) or 1500
        elo_hard    = _val(col["hard"]) or elo_overall
        elo_clay    = _val(col["clay"]) or elo_overall
        elo_grass   = _val(col["grass"]) or elo_overall

        entries.append({
            "player_name": name.lower().strip(),
            "elo_overall": elo_overall,
            "elo_hard":    elo_hard,
            "elo_clay":    elo_clay,
            "elo_grass":   elo_grass,
        })

    print(f"Scraped {len(entries)} players.")
    return entries


def main():
    entries = scrape_elo()
    if not entries:
        print("No data scraped. Aborting.")
        return

    print(f"Uploading {len(entries)} ELO entries to Supabase...")
    db.upsert_elo_cache(entries)
    print("Done! ELO cache updated in Supabase.")
    print("\nSample entries:")
    for e in entries[:5]:
        print(f"  {e['player_name']}: overall={e['elo_overall']}, clay={e['elo_clay']}, hard={e['elo_hard']}, grass={e['elo_grass']}")


if __name__ == "__main__":
    main()
