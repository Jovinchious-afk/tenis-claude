"""
Brzi test da provjeri da li API ključevi rade.
Pokreni: python test_api.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from agent.data_fetcher import get_matches_for_date, get_atp_rankings, get_tennis_abstract_elo
from utils.helpers import today_zagreb, tomorrow_zagreb, format_date_hr

print("=" * 50)
print("TENNIS AGENT — API TEST")
print("=" * 50)

# Test 1: Mečevi danas
print(f"\n1. Mečevi danas ({format_date_hr(today_zagreb())})...")
try:
    matches = get_matches_for_date(today_zagreb())
    if matches:
        print(f"   OK! Pronađeno {len(matches)} mečeva")
        for m in matches[:3]:
            print(f"   - {m['player1']} vs {m['player2']} | {m['tournament']} ({m['surface']})")
        if len(matches) > 3:
            print(f"   ... i još {len(matches)-3} mečeva")
    else:
        print("   Nema mečeva danas (ili nema podataka za danas)")
except Exception as e:
    print(f"   GREŠKA: {e}")

# Test 2: Mečevi sutra
print(f"\n2. Mečevi sutra ({format_date_hr(tomorrow_zagreb())})...")
try:
    matches_tm = get_matches_for_date(tomorrow_zagreb())
    if matches_tm:
        print(f"   OK! Pronađeno {len(matches_tm)} mečeva")
        for m in matches_tm[:3]:
            print(f"   - {m['player1']} vs {m['player2']} | {m['tournament']}")
    else:
        print("   Nema mečeva sutra")
except Exception as e:
    print(f"   GREŠKA: {e}")

# Test 3: ATP Rankings
print("\n3. ATP Rankings...")
try:
    rankings = get_atp_rankings(limit=5)
    if rankings:
        print(f"   OK! Top 5:")
        for name, rank in sorted(rankings.items(), key=lambda x: x[1])[:5]:
            print(f"   #{rank} {name}")
    else:
        print("   Nema ranking podataka")
except Exception as e:
    print(f"   GREŠKA: {e}")

# Test 4: ELO (web scraping - ne ovisi o API ključu)
print("\n4. Tennis Abstract ELO (scraping)...")
try:
    elo = get_tennis_abstract_elo()
    if elo:
        print(f"   OK! {len(elo)} igrača s ELO ratingom")
        # Prikaži top 3
        top = sorted(elo.items(), key=lambda x: x[1]["elo_overall"], reverse=True)[:3]
        for name, data in top:
            print(f"   {name.title()}: ELO={data['elo_overall']:.0f} (clay={data['elo_clay']:.0f})")
    else:
        print("   ELO podatci nisu dostupni (web scraping blokiran?)")
except Exception as e:
    print(f"   GREŠKA: {e}")

print("\n" + "=" * 50)
print("Ako vidite OK! za test 1, sve je postavljeno ispravno!")
print("=" * 50)
