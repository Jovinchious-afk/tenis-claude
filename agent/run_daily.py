"""
Glavni orchestrator — pokreće se svaki dan u 9:30h CET putem GitHub Actions.

Tok:
1. Dohvati mečeve za danas i sutra
2. Dohvati podatke o igračima (statistike, ELO, forma, H2H)
3. Dohvati kvote i vijesti
4. Analiziraj svaki meč (Claude Haiku)
5. Generiraj optimalni tiket (Claude Sonnet)
6. Spremi u Supabase
7. Pošalji email
"""
import sys
import os
import datetime
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent import data_fetcher as df
from agent.predictor import analyze_matches_batch
from agent.ticket_builder import build_ticket
from agent.feedback_analyzer import run_evening_update
from database import supabase_client as db
from utils.email_sender import send_daily_ticket_email
from utils.helpers import today_zagreb, tomorrow_zagreb, format_date, format_date_hr

DRY_RUN = "--dry-run" in sys.argv
EVENING_MODE = "--evening" in sys.argv


def main():
    if EVENING_MODE:
        print("=== Pokretanje večernjeg updatea ===")
        run_evening_update()
        return

    print(f"=== Tennis Agent — {format_date_hr(today_zagreb())} ===")
    if DRY_RUN:
        print("DRY RUN MODE: tiket se neće spremiti u DB niti poslati emailom")

    # 1. Učitaj aktivne težine iz Supabase
    from config.model_config import DEFAULT_WEIGHTS
    try:
        weights = db.get_active_weights()
        # Migracija: ako stare težine još imaju odds_movement, upiši novu verziju bez njega
        if "odds_movement" in weights:
            print("Migracija težina: uklanjam odds_movement, redistribuiram na recent_form i fatigue_injuries.")
            db.save_new_weights(
                DEFAULT_WEIGHTS,
                "Uklonjen odds_movement faktor — model formira predikcije neovisno od tržišta. "
                "Redistribuirano: recent_form +2% (18→20), fatigue_injuries +2% (12→14).",
                "Automatska migracija v2"
            )
            weights = DEFAULT_WEIGHTS
        print(f"Učitane težine modela: {weights}")
    except Exception as e:
        print(f"Greška učitavanja težina, koristim default: {e}")
        weights = DEFAULT_WEIGHTS

    # 2. Dohvati mečeve za danas i sutra
    today = today_zagreb()
    tomorrow = tomorrow_zagreb()
    print(f"\nDohvaćam mečeve za {format_date(today)} i {format_date(tomorrow)}...")

    matches_today = df.get_matches_for_date(today)
    matches_tomorrow = df.get_matches_for_date(tomorrow)
    all_matches = matches_today + matches_tomorrow

    print(f"Pronađeno {len(matches_today)} mečeva danas, {len(matches_tomorrow)} sutra = {len(all_matches)} ukupno")

    # Sortiraj po razini turnira: GS > Masters > 500 > 250 > Challenger
    from config.model_config import TOURNAMENT_LEVELS
    all_matches.sort(key=lambda m: (
        -TOURNAMENT_LEVELS.get(m.get("level", "ATP 250"), 45),
        m.get("date", ""),
    ))

    # Cap na 35 mečeva — GS/Masters uvijek unutar limita, Challengeri se režu ako ima previše
    MAX_MATCHES = 35
    if len(all_matches) > MAX_MATCHES:
        print(f"Reduciram na {MAX_MATCHES} mečeva (izbačeno {len(all_matches) - MAX_MATCHES} nižih turnira).")
        all_matches = all_matches[:MAX_MATCHES]

    if not all_matches:
        print("Nema mečeva za analizu. Završavam.")
        return

    # Prilagodi min odds prema broju dostupnih mečeva
    total_matches = len(all_matches)
    if total_matches <= 3:
        print(f"Samo {total_matches} meča dostupno — premalo za tiket. Završavam.")
        _send_no_ticket_email(today, [])
        return
    elif total_matches == 4:
        min_odds_override = 6.0
        print(f"Točno 4 meča — spuštam min kvotu na {min_odds_override} (QF/mali dan).")
    else:
        min_odds_override = None  # standardnih 9.0

    # 3. Dohvati ELO ratings jednom za sve (batch)
    print("\nDohvaćam ELO ratingse s Tennis Abstract...")
    elo_data = df.get_tennis_abstract_elo()
    print(f"Dohvaćeno {len(elo_data)} ELO ratinga")

    # 4. Dohvati ATP rankings
    print("Dohvaćam ATP rankings...")
    atp_rankings = df.get_atp_rankings()

    # 5. Dohvati odds za sve mečeve
    print("Dohvaćam bookmaker kvote...")
    all_odds = df.get_tennis_odds([m["player1"] for m in all_matches])

    # 6. Dohvati novosti o ozljedama
    print("Dohvaćam vijesti o ozljedama...")
    injury_news = df.get_atp_injury_news()

    # 6b. Dohvati vremenske uvjete za svaki turnir (jednom po gradu)
    print("Dohvaćam vremenske uvjete...")
    weather_cache = {}
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        if city and city not in weather_cache:
            w = df.get_weather_for_tournament(city)
            if w:
                weather_cache[city] = (
                    f"{w['temp_c']}°C, {w['condition']}, "
                    f"Vjetar: {w['wind_kmh']} km/h, Vlaga: {w['humidity']}%"
                )
                print(f"  {city}: {weather_cache[city]}")
            else:
                weather_cache[city] = "N/A"
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        match["weather"] = weather_cache.get(city, "N/A")

    # 7. Za svaki meč dohvati podatke o igračima
    print(f"\nDohvaćam podatke za {len(all_matches)} mečeva...")
    matches_with_data = []

    for match in all_matches:
        try:
            print(f"  Obrađujem: {match['player1']} vs {match['player2']} ({match.get('tournament', '')})")
            p1_id = match.get("player1_id", "")
            p2_id = match.get("player2_id", "")

            # Player 1 data
            p1_info = df.get_player_info(p1_id) if p1_id else {}
            p1_stats = df.get_player_stats(p1_id) if p1_id else {}
            p1_form = df.get_recent_form(p1_id, 10) if p1_id else {}
            p1_elo = df.find_player_elo(match["player1"], elo_data)
            p1_surface_summary = df.get_player_surface_summary(p1_id) if p1_id else {}

            # Player 2 data
            p2_info = df.get_player_info(p2_id) if p2_id else {}
            p2_stats = df.get_player_stats(p2_id) if p2_id else {}
            p2_form = df.get_recent_form(p2_id, 10) if p2_id else {}
            p2_elo = df.find_player_elo(match["player2"], elo_data)
            p2_surface_summary = df.get_player_surface_summary(p2_id) if p2_id else {}

            # Tournament record (cached — isti igrač ne zove API više puta)
            tournament_id = match.get("tournament_id", "")
            p1_tournament_rec = df.get_player_tournament_record(p1_id, tournament_id) if p1_id and tournament_id else {}
            p2_tournament_rec = df.get_player_tournament_record(p2_id, tournament_id) if p2_id and tournament_id else {}

            # H2H
            h2h = df.get_h2h(p1_id, p2_id) if p1_id and p2_id else {}

            # Kvote
            odds = df.find_match_odds(match["player1"], match["player2"], all_odds)
            match["odds_p1"] = odds.get("p1_odds", 0)
            match["odds_p2"] = odds.get("p2_odds", 0)
            match["odds_available"] = bool(odds)  # False = kvote nisu nađene u Odds API

            # Kompajliraj p1_data i p2_data
            p1_data = {**p1_info, **p1_stats,
                       "form_recent": p1_form,
                       "elo_overall": p1_elo.get("elo_overall", 1500),
                       "elo_clay": p1_elo.get("elo_clay", 1500),
                       "elo_hard": p1_elo.get("elo_hard", 1500),
                       "elo_grass": p1_elo.get("elo_grass", 1500),
                       "matches_7d": _count_matches_last_n_days(p1_form.get("matches", []), 7),
                       "last_match_date": _last_match_date(p1_form.get("matches", [])),
                       "ranking": p1_info.get("ranking") or atp_rankings.get(match["player1"], 999),
                       "news": _extract_player_news(match["player1"], injury_news),
                       "surface_summary": p1_surface_summary,
                       "tournament_record": p1_tournament_rec,
                       }

            p2_data = {**p2_info, **p2_stats,
                       "form_recent": p2_form,
                       "elo_overall": p2_elo.get("elo_overall", 1500),
                       "elo_clay": p2_elo.get("elo_clay", 1500),
                       "elo_hard": p2_elo.get("elo_hard", 1500),
                       "elo_grass": p2_elo.get("elo_grass", 1500),
                       "matches_7d": _count_matches_last_n_days(p2_form.get("matches", []), 7),
                       "last_match_date": _last_match_date(p2_form.get("matches", [])),
                       "ranking": p2_info.get("ranking") or atp_rankings.get(match["player2"], 999),
                       "news": _extract_player_news(match["player2"], injury_news),
                       "surface_summary": p2_surface_summary,
                       "tournament_record": p2_tournament_rec,
                       }

            matches_with_data.append({
                "match": match,
                "p1_data": p1_data,
                "p2_data": p2_data,
                "h2h": h2h,
            })

        except Exception as e:
            print(f"  Greška za {match['player1']} vs {match['player2']}: {e}")
            continue

    print(f"\nAnaliziram {len(matches_with_data)} mečeva s Claude...")
    predictions = analyze_matches_batch(matches_with_data, weights, injury_news)

    valid_predictions = [p for p in predictions if not p.get("skip_reason")]
    print(f"Valjane predikcije: {len(valid_predictions)}/{len(predictions)}")

    # 8. Generiraj tiket
    print("\nGeneriram optimalni tiket...")
    ticket = build_ticket(predictions, weights, min_odds_override=min_odds_override)

    if not ticket:
        # build_ticket ima kaskadni fallback i ne bi smio vratiti None
        print("KRITIČNA GREŠKA: Nema valjanih predikcija. Završavam.")
        return

    print(f"\n=== TIKET GENERIRAN ===")
    print(f"Mečevi: {ticket['matches_count']}")
    print(f"Ukupna kvota: {ticket['total_odds']:.2f}")
    print(f"Potencijalni dobitak: €{ticket['potential_win']:.2f}")
    for m in ticket["matches"]:
        print(f"  {m['pick']} ({m['tournament']}, {m['surface']}) — kvota: {m['odds']:.2f}, conf: {m['confidence']:.0f}%")

    # 9. Spremi u Supabase
    if not DRY_RUN:
        try:
            # Ako tiket za danas već postoji, obriši ga (sprječava duplikate)
            existing = db.get_ticket_by_date(format_date(today))
            if existing:
                print(f"Tiket za {format_date(today)} već postoji (ID: {existing.get('id')}) — brišem stari.")
                db.delete_ticket(str(existing.get("id", "")))

            saved_ticket = db.save_ticket({
                "ticket_date": format_date(today),
                "status": "pending",
                "stake": ticket["stake"],
                "total_odds": ticket["total_odds"],
                "potential_win": ticket["potential_win"],
                "matches_count": ticket["matches_count"],
                "ticket_summary": ticket.get("ticket_summary", ""),
            })
            ticket_id = saved_ticket.get("id")
            if ticket_id:
                for m in ticket["matches"]:
                    m["ticket_id"] = ticket_id
                db.save_ticket_matches(ticket["matches"])
            print(f"Tiket spremljen u Supabase (ID: {ticket_id})")

            # Spremi i analizirane mečeve
            for pred in predictions:
                m = pred.get("match", {})
                if m.get("external_id"):
                    db.save_analyzed_match({
                        "external_match_id": m["external_id"],
                        "match_date": m.get("date"),
                        "player1": m.get("player1"),
                        "player2": m.get("player2"),
                        "tournament": m.get("tournament"),
                        "tournament_level": m.get("level"),
                        "surface": m.get("surface"),
                        "round": m.get("round"),
                        "predicted_winner": pred.get("pick"),
                        "predicted_confidence": pred.get("confidence"),
                        "predicted_fair_odds": pred.get("fair_odds"),
                        "bookmaker_odds_p1": m.get("odds_p1"),
                        "bookmaker_odds_p2": m.get("odds_p2"),
                        "value_detected": pred.get("value", False),
                        "full_analysis": {
                            "risk_notes": pred.get("risk_notes"),
                            "key_factors": pred.get("key_factors"),
                            "analysis": pred.get("analysis"),
                            "handicap_option": pred.get("handicap_option"),
                        }
                    })
        except Exception as e:
            print(f"Greška spremanja u Supabase: {e}")

        # 10. Pošalji email
        try:
            send_daily_ticket_email(ticket, ticket["matches"])
        except Exception as e:
            print(f"Greška slanja emaila: {e}")
    else:
        print("\n[DRY RUN] Tiket nije spremljen niti email poslan.")
        print("\nTiket summary:")
        print(ticket.get("ticket_summary", ""))

    print("\n=== Završeno ===")


def _count_matches_last_n_days(matches: list, n: int) -> int:
    from utils.helpers import today_zagreb
    cutoff = today_zagreb() - datetime.timedelta(days=n)
    count = 0
    for m in matches:
        try:
            d = datetime.date.fromisoformat(m.get("date", "")[:10])
            if d >= cutoff:
                count += 1
        except Exception:
            pass
    return count


def _last_match_date(matches: list) -> str:
    if not matches:
        return "N/A"
    return matches[0].get("date", "N/A")[:10]


def _city_for_weather(tournament_name: str) -> str:
    """Izvlači grad iz naziva turnira za weather API lookup."""
    if not tournament_name:
        return ""
    # Format "French Open - Paris" → "Paris"
    if " - " in tournament_name:
        return tournament_name.split(" - ")[-1].strip()
    # Format "Vicenza Challenger" → "Vicenza", "Little Rock Challenger" → "Little Rock"
    for suffix in [" Challenger", " Open", " Masters", " Cup", " Trophy", " International"]:
        if tournament_name.endswith(suffix):
            return tournament_name[:-len(suffix)].strip()
    return tournament_name.strip()


def _extract_player_news(player_name: str, all_news: str) -> str:
    parts = player_name.split()
    surname = parts[-1].lower() if parts else ""
    if not surname or not all_news:
        return ""
    sentences = all_news.split(";")
    relevant = [s.strip() for s in sentences if surname in s.lower()]
    return "; ".join(relevant[:2]) if relevant else ""


def _send_no_ticket_email(date, predictions: list) -> None:
    from utils.email_sender import _send_email
    valid_count = len([p for p in predictions if not p.get("skip_reason")])
    high_conf = len([p for p in predictions if (p.get("confidence") or 0) >= 63])
    body = f"""<html><body>
    <h2>🎾 Tenis Agent — {format_date_hr(date)}</h2>
    <p>Danas nije moguće generirati tiket unutar zadanih parametara.</p>
    <p>Analizirani mečevi: {len(predictions)}<br>
    Valjane analize: {valid_count}<br>
    Visoki confidence (&ge;63%): {high_conf}<br>
    Problem: nije moguće složiti kombinaciju s kvotom 8-15 u 4-7 mečeva</p>
    </body></html>"""
    _send_email(f"⚠️ Tenis Agent — Nema tiketa za {format_date_hr(date)}", body)


if __name__ == "__main__":
    main()
