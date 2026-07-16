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
from agent.ticket_builder import build_ticket, build_analysis_only_ticket
from agent.feedback_analyzer import run_evening_update
from database import supabase_client as db
from utils.email_sender import send_daily_ticket_email, send_analysis_only_email
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

    # 1. Učitaj surface-specific težine iz Supabase
    from config.model_config import DEFAULT_WEIGHTS
    try:
        weights = {
            "clay":  db.get_active_weights("clay"),
            "grass": db.get_active_weights("grass"),
            "hard":  db.get_active_weights("hard"),
        }
        for surf, w in weights.items():
            print(f"  Težine ({surf}): {w}")
    except Exception as e:
        print(f"Greška učitavanja težina, koristim default za sve površine: {e}")
        weights = {"clay": DEFAULT_WEIGHTS, "grass": DEFAULT_WEIGHTS, "hard": DEFAULT_WEIGHTS}

    # 2. Dohvati mečeve za danas i sutra
    today = today_zagreb()
    tomorrow = tomorrow_zagreb()
    print(f"\nDohvaćam mečeve za {format_date(today)} i {format_date(tomorrow)}...")

    matches_today = df.get_matches_for_date(today)
    matches_tomorrow = df.get_matches_for_date(tomorrow)
    all_matches = matches_today + matches_tomorrow

    # 1. Filter live/finished — only upcoming scheduled matches
    live_removed = [m for m in all_matches if m.get("status") in ("live", "finished")]
    all_matches = [m for m in all_matches if m.get("status") == "scheduled"]
    if live_removed:
        print(f"Filtered out {len(live_removed)} live/finished matches.")

    # 2. Filter to main tour only — GS, Masters 1000, ATP 500, ATP 250
    # Challengers, ITF, Qualifying are excluded BEFORE any data fetching (saves API calls)
    _MAIN_TOUR_LEVELS = {"Grand Slam", "ATP Masters 1000", "ATP 500", "ATP 250"}
    main_tour = [m for m in all_matches if m.get("level") in _MAIN_TOUR_LEVELS]
    excluded = len(all_matches) - len(main_tour)
    if excluded:
        print(f"Filtered out {excluded} non-main-tour matches (Challenger/ITF/Qualifying).")
    all_matches = main_tour

    print(f"Found {len(matches_today)} today + {len(matches_tomorrow)} tomorrow → {len(all_matches)} main-tour scheduled")

    # Ručno unesene kvote sa screenshotova — drže se ODVOJENO od Odds API podataka
    # kako bi find_match_odds mogao uvijek provjeriti screenshot PRVI (prioritet),
    # a tek tada pasti na The Odds API kao fallback.
    # Učitava se OVDJE (prije _infer_rounds) jer je screenshot izvor istine da meč
    # NIJE kvalifikacija: korisnik screenshota samo mečeve glavnog ždrijeba, nikad
    # kvalifikacije. _infer_rounds to koristi da prepozna API-jev pogrešan Q-tag
    # (npr. Umag QF označen kao Q2) i izvede pravu rundu iz broja mečeva.
    screenshot_odds = {}
    screenshot_odds.update(df.get_screenshot_odds(format_date(today)))
    screenshot_odds.update(df.get_screenshot_odds(format_date(tomorrow)))
    if screenshot_odds:
        print(f"  Učitano {len(screenshot_odds)} screenshot kvota (imaju prioritet nad Odds API).")

    # Fix unreliable round labels using match count per tournament per day
    all_matches = _infer_rounds(all_matches, screenshot_odds)

    # Sortiraj po razini turnira: GS > Masters > 500 > 250 > Challenger
    from config.model_config import TOURNAMENT_LEVELS
    all_matches.sort(key=lambda m: (
        -TOURNAMENT_LEVELS.get(m.get("level", "ATP 250"), 45),
        m.get("date", ""),
    ))

    # Cap na 40 mečeva s pametnom alokacijom za R128/R64 Grand Slam dane.
    # Kada GS ima >20 mečeva (R128 ili R64), Wimbledon/AO/RG bi pojeo svih 40 mjesta
    # i ostali turniri (ATP 250/500) ne bi ušli u analizu niti na tiket.
    # Rješenje: rezerviraj 10 mjesta za ne-GS turnire, a GS uzima random 30.
    MAX_MATCHES = 40
    GS_LARGE_ROUND_THRESHOLD = 20   # >20 GS mečeva = R128 ili R64 u tijeku
    GS_LARGE_ROUND_CAP = 30         # max GS mečeva u tom slučaju
    OTHER_TOUR_RESERVE = 10         # uvijek rezervirano za ATP 250/500/Masters

    gs_matches = [m for m in all_matches if m.get("level") == "Grand Slam"]
    other_matches = [m for m in all_matches if m.get("level") != "Grand Slam"]

    if len(gs_matches) > GS_LARGE_ROUND_THRESHOLD:
        import random as _random
        selected_gs = _random.sample(gs_matches, min(GS_LARGE_ROUND_CAP, len(gs_matches)))
        selected_other = other_matches[:OTHER_TOUR_RESERVE]
        print(
            f"Grand Slam R128/R64 detektiran ({len(gs_matches)} GS mečeva): "
            f"uzimam {len(selected_gs)} random GS + {len(selected_other)} ostalih "
            f"({', '.join(sorted({m.get('tournament','').split(' - ')[0] for m in selected_other}))})."
        )
        all_matches = selected_gs + selected_other
    else:
        if len(all_matches) > MAX_MATCHES:
            print(f"Reduciram na {MAX_MATCHES} mečeva (izbačeno {len(all_matches) - MAX_MATCHES} nižih turnira).")
            all_matches = all_matches[:MAX_MATCHES]

    if not all_matches:
        print("Nema mečeva za analizu. Završavam.")
        return

    # Odredi mode: analysis-only (< 4 mečeva) ili puni tiket
    total_matches = len(all_matches)
    analysis_only_mode = total_matches < 4
    if analysis_only_mode:
        print(f"Samo {total_matches} meča — analysis-only mode (QF/SF/F faza). Tiket neće biti kreiran.")
    # Jedinstvena, stabilna tvrda granica kombinirane kvote: 6.5-40 (iz TICKET_CONFIG).
    # Nema više posebnog spuštanja za 4 meča — granica je uvijek ista.
    min_odds_override = None

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

    # Očisti zastarjele screenshot kvote — zapisi za dane koji su već prošli više
    # nikad neće biti korišteni (mečevi su odigrani), pa se ne nakupljaju zauvijek.
    # (screenshot_odds su već učitane gore, prije _infer_rounds.)
    n_cleaned = db.cleanup_old_screenshot_odds(format_date(today))
    if n_cleaned:
        print(f"  Očišćeno {n_cleaned} zastarjelih zapisa screenshot kvota.")

    # 6. Dohvati novosti o ozljedama
    print("Dohvaćam vijesti o ozljedama...")
    injury_news = df.get_atp_injury_news()

    # 6b. Dohvati vremenske uvjete za svaki turnir (jednom po gradu)
    print("Dohvaćam vremenske uvjete...")
    # Cache by (city, date) so today and tomorrow get separate weather
    weather_cache = {}
    today_str = format_date(today)
    tomorrow_str = format_date(tomorrow)
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        match_date = match.get("date", today_str)
        cache_key = (city, match_date)
        if city and cache_key not in weather_cache:
            w = df.get_weather_for_tournament(city, forecast_date=match_date)
            if w:
                label = "forecast" if match_date != today_str else "current"
                weather_str = (
                    f"{w['temp_c']}°C, {w['condition']}, "
                    f"Wind: {w['wind_kmh']} km/h, Humidity: {w['humidity']}% ({label})"
                )
                weather_cache[cache_key] = weather_str
                print(f"  {city} ({match_date}): {weather_str}")
            else:
                weather_cache[cache_key] = "N/A"
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        match_date = match.get("date", today_str)
        base_weather = weather_cache.get((city, match_date), "N/A")
        if base_weather == "N/A":
            match["weather"] = base_weather
        elif "indoor" in match.get("surface", "").lower():
            match["weather"] = base_weather + " — indoor venue (weather not a factor for play)"
        elif _has_retractable_roof(match.get("tournament", ""), city):
            rain_conds = {"rain", "drizzle", "thunderstorm", "shower"}
            if any(rc in base_weather.lower() for rc in rain_conds):
                match["weather"] = base_weather + " — retractable roof venue (roof closed if rain: conditions indoor, rain/wind irrelevant for play)"
            else:
                match["weather"] = base_weather
        else:
            match["weather"] = base_weather

    # 6c. Dohvati/cachaj draw povijest za sve unikatne turnire (lazy — samo jednom po turniru).
    # Sprema F/SF/QF/R16 rezultate zadnje 3 sezone u Supabase; subsequent pozivi čitaju cache.
    print("Dohvaćam tournament draw povijest (za anti-halucinacijski kontekst)...")
    tournament_draw_cache: dict = {}
    _fetched_this_run: set = set()
    for _m in all_matches:
        _tid = _m.get("tournament_id", "")
        _tname = _m.get("tournament", "")
        _base = _tname.split(" - ")[0].strip()
        if _base and _base not in tournament_draw_cache:
            if _base not in _fetched_this_run:
                _fetched_this_run.add(_base)
                if not db.has_tournament_history(_tname):
                    _records = df.get_tournament_draw_history(_tid, _tname, years=3)
                    if _records:
                        _n = db.save_tournament_history(_records)
                        print(f"  Spremljeno {_n} draw zapisa za {_base}.")
            _min_yr = datetime.date.today().year - 3
            tournament_draw_cache[_base] = db.get_tournament_draw(_tname, _min_yr)
    _total_draw = sum(len(v) for v in tournament_draw_cache.values())
    print(f"  Draw cache: {_total_draw} zapisa za {len(tournament_draw_cache)} turnira.")

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

            # Isključi meč ako bilo koji igrač nema pravi ELO — 1500 je fallback default
            # za igrače koji nisu u elo_cache (~521 igrača), pa bi analiza bila zasnovana
            # na izmišljenom broju umjesto stvarnoj procjeni snage
            if p1_elo.get("elo_overall") == 1500 or p2_elo.get("elo_overall") == 1500:
                missing = match["player1"] if p1_elo.get("elo_overall") == 1500 else match["player2"]
                print(f"  Preskačem (nema ELO u cacheu): {match['player1']} vs {match['player2']} — "
                      f"'{missing}' nema stvarnu ELO ocjenu (fallback 1500)")
                continue

            # Tournament record (cached — isti igrač ne zove API više puta)
            tournament_id = match.get("tournament_id", "")
            p1_tournament_rec = df.get_player_tournament_record(p1_id, tournament_id) if p1_id and tournament_id else {}
            p2_tournament_rec = df.get_player_tournament_record(p2_id, tournament_id) if p2_id and tournament_id else {}

            # Avg opponent ELO last 10 — quality-adjusted form signal
            p1_avg_opp_elo = _avg_opponent_elo(p1_form.get("matches", []), elo_data)
            p2_avg_opp_elo = _avg_opponent_elo(p2_form.get("matches", []), elo_data)

            # Current tournament path — sets/scores dropped this week
            p1_tourn_path = _tournament_path(p1_form.get("matches", []), tournament_id)
            p2_tourn_path = _tournament_path(p2_form.get("matches", []), tournament_id)

            # Form trend — last 3 vs previous 7
            p1_trend = _form_trend(p1_form.get("matches", []))
            p2_trend = _form_trend(p2_form.get("matches", []))

            # Altitude context
            altitude = _altitude_context(match.get("tournament", ""))
            if altitude:
                match["altitude"] = altitude

            # H2H
            h2h = df.get_h2h(p1_id, p2_id) if p1_id and p2_id else {}
            h2h_stats = df.get_h2h_stats(p1_id, p2_id) if p1_id and p2_id else {}
            if h2h_stats:
                h2h["stats"] = h2h_stats

            # Kvote
            odds = df.find_match_odds(match["player1"], match["player2"], all_odds,
                                      screenshot_odds=screenshot_odds)
            match["odds_p1"] = odds.get("p1_odds", 0)
            match["odds_p2"] = odds.get("p2_odds", 0)
            match["odds_available"] = bool(odds)  # False = kvote nisu nađene u Odds API
            # Screenshot = korisnikova potvrda glavnog ždrijeba (izvor istine da meč
            # NIJE kvalifikacija). _is_main_tour koristi ovu zastavicu da propusti meč
            # čak i ako je API ostavio Q/R128 oznaku. Provjera samo protiv screenshota.
            ss = df.find_match_odds(match["player1"], match["player2"], {},
                                    screenshot_odds=screenshot_odds)
            match["has_screenshot_odds"] = bool(ss)

            # Kompajliraj p1_data i p2_data
            p1_data = {**p1_info, **p1_stats,
                       "form_recent": p1_form,
                       "elo_overall": p1_elo.get("elo_overall", 1500),
                       "elo_clay": p1_elo.get("elo_clay", 1500),
                       "elo_hard": p1_elo.get("elo_hard", 1500),
                       "elo_grass": p1_elo.get("elo_grass", 1500),
                       "matches_7d": _count_matches_last_n_days(p1_form.get("matches", []), 7),
                       "sets_7d": _count_sets_last_n_days(p1_form.get("matches", []), 7),
                       "last_match_date": _last_match_date(p1_form.get("matches", [])),
                       "ranking": p1_info.get("ranking") or atp_rankings.get(match["player1"], 999),
                       "news": _extract_player_news(match["player1"], injury_news),
                       "surface_summary": p1_surface_summary,
                       "tournament_record": p1_tournament_rec,
                       "avg_opp_elo": p1_avg_opp_elo,
                       "tournament_path": p1_tourn_path,
                       "form_trend": p1_trend,
                       }

            p2_data = {**p2_info, **p2_stats,
                       "form_recent": p2_form,
                       "elo_overall": p2_elo.get("elo_overall", 1500),
                       "elo_clay": p2_elo.get("elo_clay", 1500),
                       "elo_hard": p2_elo.get("elo_hard", 1500),
                       "elo_grass": p2_elo.get("elo_grass", 1500),
                       "matches_7d": _count_matches_last_n_days(p2_form.get("matches", []), 7),
                       "sets_7d": _count_sets_last_n_days(p2_form.get("matches", []), 7),
                       "last_match_date": _last_match_date(p2_form.get("matches", [])),
                       "ranking": p2_info.get("ranking") or atp_rankings.get(match["player2"], 999),
                       "news": _extract_player_news(match["player2"], injury_news),
                       "surface_summary": p2_surface_summary,
                       "tournament_record": p2_tournament_rec,
                       "avg_opp_elo": p2_avg_opp_elo,
                       "tournament_path": p2_tourn_path,
                       "form_trend": p2_trend,
                       }

            _base_tname = match.get("tournament", "").split(" - ")[0].strip()
            match["draw_history"] = tournament_draw_cache.get(_base_tname, [])

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

    # 8. Generiraj tiket ili analysis-only zapis
    print("\nGeneriram tiket...")
    if analysis_only_mode or len(valid_predictions) < 4:
        ticket = build_analysis_only_ticket(valid_predictions)
        print(f"Analysis-only: {ticket['matches_count']} mečeva analizirano, tiket nije kreiran.")
    else:
        ticket = build_ticket(predictions, weights, min_odds_override=min_odds_override)
        if not ticket:
            print("Kaskadni fallback nije uspio — prelazim u analysis-only mode.")
            ticket = build_analysis_only_ticket(valid_predictions)

    print(f"\n=== TIKET GENERIRAN ===")
    print(f"Mečevi: {ticket['matches_count']}")
    print(f"Ukupna kvota: {ticket['total_odds']:.2f}")
    print(f"Potencijalni dobitak: €{ticket['potential_win']:.2f}")
    for m in ticket["matches"]:
        print(f"  {m['pick']} ({m['tournament']}, {m['surface']}) — kvota: {m['odds']:.2f}, conf: {m['confidence']:.0f}%")

    # 9. Spremi u Supabase
    is_analysis_only = ticket.get("status") == "analysis_only"
    if not DRY_RUN:
        try:
            # Ako tiket za danas već postoji, obriši ga (sprječava duplikate)
            existing = db.get_ticket_by_date(format_date(today))
            if existing:
                print(f"Tiket za {format_date(today)} već postoji (ID: {existing.get('id')}) — brišem stari.")
                db.delete_ticket(str(existing.get("id", "")))

            saved_ticket = db.save_ticket({
                "ticket_date": format_date(today),
                "status": ticket.get("status", "pending"),
                "stake": ticket["stake"],
                "total_odds": ticket["total_odds"],
                "potential_win": ticket["potential_win"],
                "matches_count": ticket["matches_count"],
                "ticket_summary": ticket.get("ticket_summary", ""),
                "reviewer_decision": ticket.get("reviewer_decision", ""),
                "reviewer_changes": ticket.get("reviewer_changes", ""),
                "reviewer_warning": ticket.get("reviewer_warning", ""),
            })
            ticket_id = saved_ticket.get("id")
            if ticket_id:
                for m in ticket["matches"]:
                    m["ticket_id"] = ticket_id
                db.save_ticket_matches(ticket["matches"])
            label = "Analiza" if is_analysis_only else "Tiket"
            print(f"{label} spremljen u Supabase (ID: {ticket_id})")

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
            if is_analysis_only:
                send_analysis_only_email(
                    {"ticket_date": format_date(today), **ticket},
                    ticket["matches"]
                )
            else:
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


def _count_sets_last_n_days(matches: list, n: int) -> int:
    """Total sets played in last n days — better fatigue indicator than match count."""
    from utils.helpers import today_zagreb
    cutoff = today_zagreb() - datetime.timedelta(days=n)
    total_sets = 0
    for m in matches:
        try:
            d = datetime.date.fromisoformat(m.get("date", "")[:10])
            if d >= cutoff:
                sets = m.get("sets_played", 0) or 0
                # If no set data, estimate: assume avg 2.5 sets per match (between straight sets and full distance)
                total_sets += sets if sets > 0 else 0
        except Exception:
            pass
    return total_sets


def _tournament_path(form_matches: list, tournament_id: str) -> str:
    """Summarize player's current tournament run — sets/score context for fatigue."""
    current = [m for m in form_matches if str(m.get("tournament_id", "")) == str(tournament_id)]
    if not current:
        return "N/A (not yet tracked this tournament)"
    wins = sum(1 for m in current if m.get("won"))
    losses = sum(1 for m in current if not m.get("won"))
    total_sets = sum(m.get("sets_played", 0) or 0 for m in current)
    scores = [m.get("score", "") for m in current if m.get("score")]
    score_str = " | ".join(scores) if scores else "scores N/A"
    # Knockout format: wins > 0 AND losses > 0 is physically impossible —
    # player would have been eliminated. Flag as API data error (retirement/walkover misrecord).
    if wins > 0 and losses > 0:
        return f"{wins}W/0L*, {total_sets} sets played | Scores: {score_str} (⚠️ API recorded {losses} loss — likely retirement/walkover error, treated as win)"
    return f"{wins}W/{losses}L, {total_sets} sets played | Scores: {score_str}"


def _form_trend(matches: list) -> str:
    """Compare last 3 vs matches 4-10 to detect improving/declining form."""
    if len(matches) < 4:
        return "N/A"
    recent3 = matches[:3]
    older = matches[3:10]
    r_wins = sum(1 for m in recent3 if m.get("won"))
    o_wins = sum(1 for m in older if m.get("won"))
    o_total = len(older)
    r_rate = r_wins / 3
    o_rate = o_wins / o_total if o_total else 0
    if r_rate > o_rate + 0.2:
        trend = "IMPROVING"
    elif r_rate < o_rate - 0.2:
        trend = "DECLINING"
    else:
        trend = "STABLE"
    return f"Last 3: {r_wins}/3 | Prev {o_total}: {o_wins}/{o_total} → {trend}"


def _has_retractable_roof(tournament_name: str, city: str) -> bool:
    """Returns True if the tournament's main court has a retractable roof (rain → roof closed → weather irrelevant)."""
    t = tournament_name.lower()
    c = city.lower()
    # Grand Slams — check by tournament name to avoid same-city conflicts (e.g. Wimbledon vs Queen's in London)
    if any(k in t for k in ["australian open", "roland", "french open", "roland-garros",
                             "wimbledon", "the championships", "us open"]):
        return True
    # Masters 1000 with confirmed retractable roofs
    if "madrid" in c:    return True   # Caja Mágica — all 3 courts have hydraulic retractable roofs
    if "shanghai" in c:  return True   # Qizhong Forest — 8-petal sliding roof
    # ATP 500 with confirmed retractable roofs
    if "hamburg" in c:   return True   # Am Rothenbaum — retractable membrane roof since 1997
    if "halle" in c:     return True   # OWL Arena — closes in 88 seconds
    if "tokyo" in c:     return True   # Ariake Coliseum — horizontal sliding roof
    if "beijing" in c:   return True   # National Tennis Center Diamond Court
    if "dubai" in c:     return True   # Aviation Club centre court
    # ATP 250
    if "hangzhou" in c:  return True   # Olympic Sports Expo Center centre court
    return False

# High-altitude tournaments — affects ball speed, serve dominance, endurance.
# Gstaad/Kitzbühel dodani u clay reviziji 2026-07-11: model je najviši europski clay
# turnir (Gstaad, ~1050m — brži servis, niži odskok spina) analizirao kao razinu mora.
_ALTITUDE_M = {
    "bogota": 2638, "quito": 2850, "mexico city": 2240,
    "mexico": 2240, "monterrey": 538, "lima": 154,
    "johannesburg": 1753, "santiago": 520,
    "gstaad": 1050, "kitzbuhel": 762, "kitzbühel": 762,
}


def _altitude_context(tournament_name: str) -> str:
    """Returns altitude context if tournament city is at significant altitude (>600m).
    Pragovi spušteni 1500/800 → 1000/600 (2026-07-11) da Gstaad (1050m) uđe u HIGH:
    na 1000m+ zrak je dovoljno rjeđi da servis mjerljivo dominira više, a clay-spin
    manje grize — teniski konsenzus za Gstaad. Santiago/Monterrey (<600) i dalje bez efekta."""
    city = _city_for_weather(tournament_name).lower()
    for key, alt in _ALTITUDE_M.items():
        if key in city:
            if alt >= 1000:
                return f"HIGH ALTITUDE ({alt}m) — ball flies faster, serve dominates more, endurance harder"
            elif alt >= 600:
                return f"MODERATE ALTITUDE ({alt}m) — slight effect on ball speed and stamina"
    return ""


def _last_match_date(matches: list) -> str:
    if not matches:
        return "N/A"
    return matches[0].get("date", "N/A")[:10]


def _avg_opponent_elo(matches: list, elo_data: dict) -> str:
    """Compute average ELO of last 10 opponents — quality-of-opposition signal."""
    from agent import data_fetcher as _df
    elos = []
    for m in matches[:10]:
        opp = m.get("opponent", "")
        if not opp:
            continue
        opp_elo = _df.find_player_elo(opp, elo_data).get("elo_overall", 0)
        if opp_elo and opp_elo > 1000:
            elos.append(opp_elo)
    if not elos:
        return "N/A"
    return str(round(sum(elos) / len(elos)))


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


def _infer_rounds(matches: list, screenshot_odds: dict = None) -> list:
    """
    Ispravlja NEPRAVILNE oznake runda s API-ja — ali samo kad su nemoguće ili
    neprepoznate, jer rundu ne određuje samo broj mečeva u danu (rundа se
    često proteže kroz više dana — npr. R32 prelijeva iz subote u nedjelju,
    pa dan s 2-3 R32 meča NE znači da je to zapravo SF).

    API ponekad vrati neprepoznat roundId (npr. 'R12' umjesto 'F') ili
    label koji je fizički nemoguć za broj mečeva tog dana (npr. 'F' uz
    3 meča — finale je uvijek točno 1 meč). U tim slučajevima procjenjujemo
    rundu iz broja mečeva; inače VJERUJEMO API-jevoj oznaci.

    Q-tag iznimka (2026-07-16): API zna glavni ždrijeb označiti kao kvalifikacije
    (npr. Umag QF vraćen kao roundId=9/Q2). Kvalifikacije se inače nikad ne diraju,
    ALI ako meč iz Q-grupe ima ručno unesenu screenshot kvotu, korisnik je potvrdio
    da je to glavni ždrijeb (kvalifikacije nikad ne screenshota) — tada ne vjerujemo
    Q-oznaci i izvodimo pravu rundu iz broja mečeva. Bez screenshota Q ostaje Q.
    """
    from collections import defaultdict

    screenshot_odds = screenshot_odds or {}
    _ROUND_ID = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7}

    def _has_screenshot(m: dict) -> bool:
        if not screenshot_odds:
            return False
        res = df.find_match_odds(m.get("player1", ""), m.get("player2", ""),
                                 {}, screenshot_odds=screenshot_odds)
        return bool(res)

    # Maksimalan broj mečeva koji ta runda fizički može imati (jedan turnir, jedan dan).
    # Ako je stvarni broj manji ili jednak, API-jeva oznaka je vjerodostojna —
    # runda se mogla protegnuti kroz više dana pa dio mečeva nedostaje.
    _MAX_MATCHES = {"F": 1, "SF": 2, "QF": 4, "R16": 8, "R32": 16, "R64": 32, "R128": 64}
    # Round-robin uvijek ima nepravilne brojeve — nikad ne diraj.
    # Q1/Q2 se ne diraju OSIM kad grupa ima screenshot (vidi Q-tag iznimku gore).
    _TRUST_ALWAYS = {"RR", "Q1", "Q2"}

    # Count all scheduled matches per (tournament, date) — before any cap
    counts: dict = defaultdict(list)
    for m in matches:
        key = (m.get("tournament", ""), m.get("date", ""))
        counts[key].append(m)

    for (tournament, date), group in counts.items():
        n = len(group)
        level = group[0].get("level", "")
        current_round = group[0].get("round", "")

        if current_round in _TRUST_ALWAYS:
            # Q-tag iznimka: ako je BILO KOJI meč iz ove grupe screenshotan, API je
            # krivo označio glavni ždrijeb kao kvalifikacije → padni na re-inference.
            # RR ostaje uvijek netaknut. Kvalifikacije bez screenshota isto.
            group_is_mislabelled_quali = (
                current_round in ("Q1", "Q2")
                and any(_has_screenshot(m) for m in group)
            )
            if not group_is_mislabelled_quali:
                continue
            print(f"  Q-tag override: {tournament} ({date}) — '{current_round}' ima "
                  f"screenshot kvotu, tretiram kao glavni ždrijeb i izvodim rundu iz broja mečeva.")
        max_for_current = _MAX_MATCHES.get(current_round)
        if max_for_current is not None and n <= max_for_current:
            continue  # API-jeva oznaka je fizički moguća — vjeruj joj

        if "Grand Slam" in level:
            if n >= 16:   inferred = "R64"
            elif n >= 8:  inferred = "R32"
            elif n >= 5:  inferred = "R16"
            elif n == 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"   # n == 1 → genuine final
        elif "Masters 1000" in level:
            if n >= 8:    inferred = "R32"
            elif n >= 5:  inferred = "R16"
            elif n == 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"
        else:
            # ATP 500/250 — manji ždrijebi (28-32), ali R16 svejedno ima 7-8 mečeva
            if n >= 8:    inferred = "R16"
            elif n >= 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"

        if current_round != inferred:
            print(f"  Round fix: {tournament} ({date}) — {current_round} → {inferred} ({n} matches)")
            for m in group:
                m["round"] = inferred
                m["round_id"] = _ROUND_ID.get(inferred, 0)

    return matches


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
