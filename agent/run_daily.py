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

    # 1b. Hard revalidacijski okidač (preporuka D, 18.07.2026): hard pravila v1 su pisana
    # BLIND (0 stvarnih pickova u korpusu kad su pisana — vidi MODEL_CHANGELOG.md). Javi
    # svaki dan dok prag ne bude ručno riješen, umjesto da čekamo da netko ručno primijeti.
    #
    # ODRAĐENO 08.08.2026 (puna hard revizija na 90 riješenih analiza — vidi MODEL_CHANGELOG).
    # Okidač je od 18.07. vikao svaki dan; sad se javlja tek na SLJEDEĆI prag, da opet
    # postane koristan kad se korpus udvostruči umjesto da postane šum koji svi preskaču.
    _HARD_REVALIDATED_AT = 90        # stanje korpusa na dan zadnje pune revizije
    _HARD_NEXT_TRIGGER = 180         # sljedeća revizija kad se udvostruči
    try:
        _hard_resolved_n = sum(
            1 for m in db.get_resolved_analyzed_matches(limit=2000)
            if "hard" in (m.get("surface") or "").lower()
        )
        if _hard_resolved_n >= _HARD_NEXT_TRIGGER:
            print(f"  ⚠️ HARD REVALIDACIJA: {_hard_resolved_n} riješenih hard analiza "
                  f"(prag {_HARD_NEXT_TRIGGER} dosegnut, zadnja revizija bila na "
                  f"{_HARD_REVALIDATED_AT}) — vrijeme za novu punu reviziju.")
        else:
            print(f"  Hard korpus: {_hard_resolved_n} riješenih analiza "
                  f"(zadnja revizija 08.08.2026 na {_HARD_REVALIDATED_AT}, "
                  f"sljedeća na {_HARD_NEXT_TRIGGER}).")
    except Exception as e:
        print(f"  Hard revalidacijski okidač preskočen (greška: {e})")

    # 2. Dohvati mečeve za danas i sutra (+ prekosutra, uvjetno — vidi ispod)
    today = today_zagreb()
    tomorrow = tomorrow_zagreb()
    day_after = tomorrow + datetime.timedelta(days=1)
    today_str = format_date(today)
    tomorrow_str = format_date(tomorrow)
    day_after_str = format_date(day_after)

    # Screenshot kvote se učitavaju OVDJE (prije dohvata mečeva) jer o njima ovisi
    # hoće li se uopće dohvatiti prekosutra. Danas/sutra ostaju odvojeni — gate mora
    # znati JE LI konkretan dan screenshotan.
    screenshot_today = df.get_screenshot_odds(today_str)
    screenshot_tomorrow = df.get_screenshot_odds(tomorrow_str)
    screenshot_odds = {**screenshot_today, **screenshot_tomorrow}

    # PROŠIRENI PROZOR (01.08.2026, korisnikov zahtjev): pod "Sutra" korisnik zna
    # uploadati i prekosutrašnje parove — SuperSport ima kvote za ponedjeljak već u
    # subotu, dok naš API tada još nema taj raspored. Dokumentirano 01.08.: od 16
    # uploadanih parova, 13 se zapravo igralo prekosutra (Montreal glavni ždrijeb
    # počinje 03.08. po API-jevim vlastitim podacima) pa nikad nisu ni dohvaćeni.
    # Prekosutra se dohvaća SAMO ako postoji "sutra" screenshot, i za taj je dan gate
    # UVIJEK aktivan (always_gated) — inače bi prošao nefiltriran jer nema vlastiti
    # screenshot slot, i povukao bi cijeli turnir u analizu.
    fetch_day_after = bool(screenshot_tomorrow)
    days_label = f"{today_str} i {tomorrow_str}"
    if fetch_day_after:
        days_label += f" (+ {day_after_str}, jer postoji screenshot za sutra)"
    print(f"\nDohvaćam mečeve za {days_label}...")

    matches_today = df.get_matches_for_date(today)
    matches_tomorrow = df.get_matches_for_date(tomorrow)
    all_matches = matches_today + matches_tomorrow
    matches_day_after = []
    if fetch_day_after:
        matches_day_after = df.get_matches_for_date(day_after)
        all_matches += matches_day_after

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

    # NAPOMENA: duplikat pravilo (isti meč na 2 uzastopna tiketa) je UKINUTO na
    # korisnikov zahtjev 2026-07-18 — tiket pokriva danas+sutra, i legitimno je isti
    # dobar meč ponoviti sutra; ne želimo izbacivati kvalitetne mečeve zbog ponavljanja.
    _extra = f" + {len(matches_day_after)} day-after" if fetch_day_after else ""
    print(f"Found {len(matches_today)} today + {len(matches_tomorrow)} tomorrow{_extra} "
          f"→ {len(all_matches)} main-tour scheduled")

    # Screenshot kvote (učitane gore, prije dohvata mečeva) drže se ODVOJENO od Odds API
    # podataka kako bi find_match_odds uvijek provjerio screenshot PRVI (prioritet), a tek
    # tada pao na The Odds API kao fallback. Screenshot je i izvor istine da meč NIJE
    # kvalifikacija — _infer_rounds to koristi za API-jev pogrešan Q-tag.
    if screenshot_odds:
        print(f"  Učitano {len(screenshot_odds)} screenshot kvota (imaju prioritet nad Odds API).")

    # Screenshot-isključivost (korisnikov zahtjev 27.07.2026, PREPISANA 11.08.2026 18:44):
    # meč prolazi ako i samo ako je njegov PAR na screenshotu (danas ∪ sutra) — datum nije
    # kriterij. Sve ostalo se izbacuje PRIJE analize, dakle iz cijele obrade, ne samo s
    # tiketa. Puno obrazloženje i incident koji je to iznudio: vidi `_gate_by_screenshot`.
    # Broj mečeva po (turnir, dan) mora se izbrojati PRIJE gatea (07.08.2026). `_infer_rounds`
    # procjenjuje rundu iz broja mečeva tog dana, a gate izbacuje sve što nije screenshotano —
    # od 27.07. je dakle brojao samo screenshotane mečeve i mislio da je dan manji nego što
    # jest. Ako screenshotaš 12 od 16 mečeva, procjena runde računa 12. Docstring je i dalje
    # tvrdio "before any cap", što je bilo točno samo prije uvođenja gatea.
    pre_gate_counts = _count_by_tournament_day(all_matches)

    all_matches = _gate_by_screenshot(all_matches, screenshot_today, screenshot_tomorrow)

    # Rani izlaz (11.08.2026 18:44): bez ijednog screenshot para nema što analizirati, a
    # nastavak bi potrošio ELO, kvote, vrijeme i Claude pozive na mečeve koji ionako ne
    # smiju proći. Povod: run u 15:08 istog dana analizirao je 21 kvalifikacijski meč
    # (21 Claude poziv) jer je screenshot tablica tada bila prazna.
    if not all_matches:
        print("\nNema nijednog meča sa screenshota — zaustavljam prije analize.")
        print("Uploadaj kvote screenshot za 'danas' i/ili 'sutra' pa pokreni ponovno.")
        return

    # Fix unreliable round labels using match count per tournament per day
    all_matches = _infer_rounds(all_matches, screenshot_odds, pre_gate_counts)

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
    # Jedinstvena, stabilna tvrda granica kombinirane kvote: 6.0-40 (iz TICKET_CONFIG).
    # Nema više posebnog spuštanja za 4 meča — granica je uvijek ista.
    min_odds_override = None

    # 3. Dohvati ELO ratings jednom za sve (batch)
    print("\nDohvaćam ELO ratingse s Tennis Abstract...")
    elo_data = df.get_tennis_abstract_elo()
    print(f"Dohvaćeno {len(elo_data)} ELO ratinga")
    # Starost cachea (07.08.2026): korisnik `scripts/update_elo_cache.py` pokreće ručno
    # prije turnira, pa mu treba vidljiv podsjetnik. Tennis Abstract osvježava tjedno.
    _elo_age = db.elo_cache_age_days()
    if _elo_age is not None:
        _mark = "  <-- pokreni scripts/update_elo_cache.py" if _elo_age > 7 else ""
        print(f"  ELO cache osvježen prije {_elo_age} dana{_mark}")

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

    # 6b. Lokalno vrijeme početka + sesija + brzina terena (31.07.2026, korisnikov zahtjev).
    # Vrijeme se veže na LOKALNI sat mjesta gdje se meč igra, ne na naš zagrebački —
    # meč koji nama počinje u 4 ujutro u Washingtonu je popodnevna sesija po suncu.
    # Brzina terena se računa iz score stringova rezultata sezone (0 dodatnih API poziva).
    # REDOSLIJED (04.08.2026): ovo se sada računa PRIJE vremenske prognoze jer prognoza od
    # danas ovisi o satu meča — vidi `weather_at_match_time` u data_fetcheru.
    # SCREENSHOT JE IZVOR ISTINE ZA VRIJEME POCETKA (04.08.2026, korisnikov zahtjev).
    # Povod: API-jev `date` za Montreal kasni ~3h. Sluzbeni raspored turnira kaze da dnevna
    # sesija pocinje 11:00 ET (= 17:00 po Zagrebu, tocno kako pise na SuperSport screenshotu),
    # a API nije imao NIJEDAN mec prije 14:00 ET. Razlika nije konstantna (3h00 do 4h05), pa
    # nije rijec o pogresnoj vremenskoj zoni koju bi se dalo korigirati konstantom.
    # Posljedice krive satnice: (1) `session` dan/noc — Lehecka je po API-ju bio "night"
    # (18:35 ET) a stvarno je dnevni mec (14:30 ET), sto krivo hrani pravilo 14; (2) izbor
    # vremenske prognoze po satu meca (uveden ranije istog dana) precizno bi pogadjao krivi sat.
    # Isti princip koji vec vrijedi za kvote i za zdrijeb: sto korisnik vidi na screenshotu
    # ima prioritet nad API-jem.
    screenshot_by_date = {today_str: screenshot_today, tomorrow_str: screenshot_tomorrow}
    _n_ss_time = 0
    for match in all_matches:
        ss_utc = df.find_screenshot_time(match["player1"], match["player2"], screenshot_by_date)
        if ss_utc:
            match["start_utc"] = ss_utc
            match["time_source"] = "screenshot"
            _n_ss_time += 1
        else:
            match["time_source"] = "api"
    if _n_ss_time:
        print(f"  Vrijeme početka sa screenshota za {_n_ss_time}/{len(all_matches)} mečeva "
              f"(ostali padaju na API-jev sat).")

    # KASNJENJE KASNIJIH VALOVA (05.08.2026, korisnikov zahtjev).
    #
    # Samo PRVI mecevi dana krecu po rasporedu; sve iza njih ceka da se prethodni na tom
    # terenu zavrsi, pa realno pocinje kasnije nego sto pise. Korisnikovo pravilo: najraniji
    # val dana ide tocno kako pise, SVI ostali dobivaju +1h — bez obzira koliko meceva ima
    # u kojem terminu. Pomak vrijedi i za odabir prognoze i za oznaku dan/noc (inace bismo
    # tvrdili da mec igra po danu, a citali prognozu za noc).
    #
    # "NAJRANIJI" SE ODREDJUJE PO (TURNIR, LOKALNI DAN TURNIRA), i to iz STVARNOG trenutka,
    # ne iz sata na ekranu. Dva razloga, oba dokumentirana na stvarnim podacima:
    #  - Po turniru, jer se kasnjenje gomila unutar jednog turnira. Ako Montreal krece u
    #    17:00 a Cincinnati u 19:00 (po Zagrebu), Cincinnatijev prvi val ne smije dobiti +1h.
    #  - Po LOKALNOM danu turnira, ne po zagrebackom datumu. Korisnik meceve iza ponoci
    #    namjerno sprema pod "danas" (kladionica ih tako lista). Za Montreal je "cet 02:10"
    #    zapravo srijeda 20:10 po lokalnom — zadnji mec istog turnirskog dana, a ne prvi mec
    #    novog. Provjereno 05.08.: svih 23 para pada u isti montrealski dan.
    #  - Sortiranje po stvarnom trenutku usput rjesava i zamku "sat na ekranu": "cet 00:00"
    #    bi kao string bio najraniji, a zapravo je pretposljednji.
    #
    # ZASTO NE "najranije vrijeme prije ponoci": za turnire na istoku to bi puklo. Melbourne
    # je u sijecnju Zagreb +10, pa Australian Open krece u 11:00 po Melbourneu = 01:00 po
    # Zagrebu — SVI mecevi su ondje "poslije ponoci", a prvi je bas taj u 01:00. Grupiranje
    # po lokalnom danu turnira radi jednako za Montreal, Dubai i Melbourne, bez iznimki.
    _sched = {}
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        lt = df.local_match_time(match.get("start_utc", ""), city)
        if lt:
            match["scheduled_local_time"] = lt["local_time"]
            _sched[id(match)] = (match.get("tournament", ""), lt["local_date"])

    # Najraniji stvarni trenutak po (turnir, lokalni dan turnira).
    _wave_start = {}
    for match in all_matches:
        key = _sched.get(id(match))
        su = match.get("start_utc", "")
        if not key or not su:
            continue
        if key not in _wave_start or su < _wave_start[key]:
            _wave_start[key] = su

    _n_bumped = 0
    for match in all_matches:
        key = _sched.get(id(match))
        su = match.get("start_utc", "")
        # Pomak SAMO kad vrijeme dolazi sa screenshota — kod API-jevog sata ne znamo u kojem
        # je meč valu, pa se ne nagađa (bolje neutralno nego krivo).
        first = (not key) or (match.get("time_source") != "screenshot") or (su == _wave_start.get(key))
        match["wave_first"] = bool(first)
        if first or not su:
            match["effective_utc"] = su
        else:
            try:
                base = datetime.datetime.fromisoformat(str(su).replace("Z", "+00:00"))
                match["effective_utc"] = (base + datetime.timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z")
                _n_bumped += 1
            except ValueError:
                match["effective_utc"] = su
    if _n_bumped:
        print(f"  Kašnjenje kasnijih valova: +1h za {_n_bumped}/{len(all_matches)} mečeva "
              f"(prvi val svakog turnira ostaje po rasporedu).")

    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        # Sve nizvodno (sesija, prognoza) koristi EFEKTIVNO vrijeme — ono kad mec realno krece.
        lt = df.local_match_time(match.get("effective_utc") or match.get("start_utc", ""), city)
        if lt:
            match["local_time"] = lt["local_time"]
            match["session"] = lt["session"]
            match["utc_offset"] = lt["utc_offset"]
            match["local_date"] = lt["local_date"]
        cp = df.get_court_pace(match.get("tournament_id", ""), match.get("tournament", ""))
        if cp:
            match["court_pace_str"] = (f"{cp['tb_pct']}% of sets ({cp['label']} court, "
                                       f"n={cp['sets']} sets this event)")
            match["court_pace_label"] = cp["label"]
    _n_lt = sum(1 for m in all_matches if m.get("local_time"))
    _n_cp = sum(1 for m in all_matches if m.get("court_pace_str"))
    print(f"  Lokalno vrijeme izračunato za {_n_lt}/{len(all_matches)} mečeva; "
          f"brzina terena za {_n_cp}/{len(all_matches)}.")

    # 6c. Vremenski uvjeti — PO SATU MEČA, ne po podnevu.
    # Bug ispravljen 04.08.2026 (korisnik uočio na Berrettiniju: model je tvrdio 99% vlage,
    # a stvarnost je bila 85-90%): stara logika je uzimala unos u 12:00 UTC, što je za
    # Montreal 08:00 ujutro. Izmjereno na stvarnoj prognozi za 05.08.: jutro 68% vlage /
    # 19.2°C, sesija meča u 14h 48% / 28.3°C — 20pp i 9°C greške, uvijek u istom smjeru.
    # Prognoza se dohvaća JEDNOM po gradu (cijela serija), pa biranje po satu ne košta
    # dodatne pozive — zapravo ih ima manje nego prije.
    print("Dohvaćam vremenske uvjete (po satu meča)...")
    weather_cache = {}
    weather_raw_cache = {}
    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        match_date = match.get("date", today_str)
        lt_str = match.get("local_time") or ""
        off = match.get("utc_offset")
        # LOKALNI datum turnira, ne datum meča — večernja sesija pada u sljedeći UTC dan.
        wx_date = match.get("local_date") or match_date
        hour = int(lt_str[:2]) if lt_str[:2].isdigit() else None
        minute = int(lt_str[3:5]) if lt_str[3:5].isdigit() else 0
        # Ključ nosi i puni sat:minutu — termini 18:10 i 18:30 mogu pasti na različite
        # zapise prognoze, pa ih ne smiju dijeliti.
        cache_key = (city, wx_date, hour, minute)
        if not city or cache_key in weather_cache:
            continue
        w = {}
        if hour is not None and off is not None:
            w = df.weather_at_match_time(city, wx_date, hour, off, minute)
        if not w:
            # Sat ili offset nepoznat — ne pogađamo, vraćamo se na staru grubu procjenu.
            w = df.get_weather_for_tournament(city, forecast_date=match_date)
        if w:
            if w.get("forecast_local_time"):
                label = f"local {w['forecast_local_time'][11:]} forecast"
                if (w.get("hours_off") or 0) > 2.0:
                    label += f", nearest available ±{w['hours_off']}h"
            else:
                label = "forecast" if match_date != today_str else "current"
            weather_str = (
                f"{w['temp_c']}°C, {w['condition']}, "
                f"Wind: {w['wind_kmh']} km/h, Humidity: {w['humidity']}% ({label})"
            )
            weather_cache[cache_key] = weather_str
            weather_raw_cache[cache_key] = w
            print(f"  {city} ({match_date} {lt_str or '??'}): {weather_str}")
        else:
            weather_cache[cache_key] = "N/A"

    for match in all_matches:
        city = _city_for_weather(match.get("tournament", ""))
        match_date = match.get("date", today_str)
        lt_str = match.get("local_time") or ""
        hour = int(lt_str[:2]) if lt_str[:2].isdigit() else None
        minute = int(lt_str[3:5]) if lt_str[3:5].isdigit() else 0
        wkey = (city, match.get("local_date") or match_date, hour, minute)
        base_weather = weather_cache.get(wkey, "N/A")
        # Strukturirani zapis za context_snapshot v5 — ide u bazu, NE u prompt.
        match["weather_data"] = weather_raw_cache.get(wkey) or {}
        # venue_shielded: dvorana ili zatvoreni krov — prognoza tada ne opisuje uvjete
        # igre, pa se ti mečevi pri kasnijem mjerenju moraju izdvojiti, inače bi razblažili
        # svaki nalaz o vremenu.
        match["weather_shielded"] = False
        if base_weather == "N/A":
            match["weather"] = base_weather
        elif "indoor" in match.get("surface", "").lower():
            match["weather"] = base_weather + " — indoor venue (weather not a factor for play)"
            match["weather_shielded"] = True
        elif _has_retractable_roof(match.get("tournament", ""), city):
            rain_conds = {"rain", "drizzle", "thunderstorm", "shower"}
            if any(rc in base_weather.lower() for rc in rain_conds):
                match["weather"] = base_weather + " — retractable roof venue (roof closed if rain: conditions indoor, rain/wind irrelevant for play)"
                match["weather_shielded"] = True
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

    # 6d. Fery veto podaci (revizija 2026-07-18, korekcija istog dana): igrači koji su
    # srušili naš pick 2+ PUTA u istom turniru zadnjih 14 dana. Prag podignut s 1 na 2
    # poraza — jedan poraz je unutar normalne varijance (naši pickovi pogađaju ~60%, pa
    # čak i ispravan pick gubi ~40% vremena), dok 2 poraza od istog igrača u istom
    # turniru je jak signal stvarnog obrasca, ne slučajnosti. Ticket builder kroz
    # zastavice p1_beat_us/p2_beat_us NIKAD ne dopušta daljnji fade takvog igrača u
    # tom turniru (Fery nas je srušio 6× u 3 tjedna — pravila su rizik zapisivala u
    # risk_notes, ali ga nisu provodila).
    from collections import Counter as _Counter
    _beat_counts = _Counter()   # {(winner_name_lower, tournament_base_lower): broj poraza}
    beaten_us = set()           # samo oni s 2+ poraza — ovo čita _beat_us ispod
    try:
        for lost in db.get_recent_lost_matches(14):
            w = (lost.get("actual_winner") or "").strip()
            t = (lost.get("tournament") or "").split(" - ")[0].strip().lower()
            if w and t:
                _beat_counts[(w.lower(), t)] += 1
        beaten_us = {key for key, n in _beat_counts.items() if n >= 2}
        if beaten_us:
            print(f"  Fery veto: {len(beaten_us)} igrač(a) koji su nas 2+ puta srušili "
                  f"({', '.join(sorted(w for w, _ in beaten_us))}).")
    except Exception as e:
        print(f"  Fery veto: greška dohvata izgubljenih pickova ({e}) — nastavljam bez veta.")

    def _beat_us(player_name: str, tournament: str) -> bool:
        t_base = (tournament or "").split(" - ")[0].strip().lower()
        pl = (player_name or "").lower()
        return any(w == pl and t == t_base for w, t in beaten_us)

    # 6e. Scouting profili (korisnikov Excel → player_scouting tablica, 25.07.2026):
    # SEKUNDARNI kvalitativni kontekst za prompt (stil, matchupovi) — max ±3pp utjecaja,
    # nikad ne nadjačava mjerene brojke. Jedan query za sve, nula dodatnih API poziva.
    scouting_map = db.get_all_scouting()
    if scouting_map:
        print(f"  Scouting profili: učitano {len(scouting_map)} igrača.")

    def _find_scouting(player_name: str) -> dict:
        """Lookup po normaliziranom imenu; fallback fuzzy match (isti _name_match kao kvote)."""
        key = " ".join(df._strip_diacritics(player_name or "").lower().strip().split())
        if key in scouting_map:
            return scouting_map[key]
        for k, v in scouting_map.items():
            if df._name_match(player_name, v.get("display_name") or k):
                return v
        return {}

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

            # Karijerna finala (C1, 26.07.2026) — iskustvo u završnicama, cached po igraču
            p1_titles = df.get_player_titles(p1_id) if p1_id else {}
            p2_titles = df.get_player_titles(p2_id) if p2_id else {}

            # Avg opponent ELO last 10 — quality-adjusted form signal
            p1_avg_opp_elo = _avg_opponent_elo(p1_form.get("matches", []), elo_data)
            p2_avg_opp_elo = _avg_opponent_elo(p2_form.get("matches", []), elo_data)
            # Koliko je protivnika stvarno uslo u taj prosjek (08.08.2026 11:35) — samo
            # biljezenje, ne ulazi u prompt. Vidi `_avg_opponent_elo_n`.
            match["avg_opp_elo_n"] = {
                "p1": _avg_opponent_elo_n(p1_form.get("matches", []), elo_data),
                "p2": _avg_opponent_elo_n(p2_form.get("matches", []), elo_data),
            }

            # Common opponents — samo za context_snapshot, NE ulazi u prompt (vidi helper).
            match["common_opponents"] = _common_opponents(
                p1_form.get("matches", []), p2_form.get("matches", []))

            # Current tournament path — sets/scores dropped this week
            p1_tourn_path = _tournament_path(p1_form.get("matches", []), tournament_id)
            p2_tourn_path = _tournament_path(p2_form.get("matches", []), tournament_id)

            # Form trend — last 3 vs previous 7
            p1_trend = _form_trend(p1_form.get("matches", []))
            p2_trend = _form_trend(p2_form.get("matches", []))

            # decider_record je od 18.07. bio SAMO sirova varijabla u snapshotu; od 31.07.
            # ulazi i u prompt (hard pravilo 16 — konvergiran servis se odlučuje u
            # tiebreakovima i odlučujućem setu, pa ondje ovi zapisi nose odluku).
            p1_decider = _decider_record(p1_form.get("matches", []))
            p2_decider = _decider_record(p2_form.get("matches", []))
            p1_tb = _tiebreak_record(p1_form.get("matches", []))
            p2_tb = _tiebreak_record(p2_form.get("matches", []))
            p1_prev_tourn_level = _previous_tournament_level(p1_form.get("matches", []))
            p2_prev_tourn_level = _previous_tournament_level(p2_form.get("matches", []))

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

            # Fery veto zastavice — ticket_builder._opponent_beat_us ih čita
            match["p1_beat_us"] = _beat_us(match["player1"], match.get("tournament", ""))
            match["p2_beat_us"] = _beat_us(match["player2"], match.get("tournament", ""))
            if match["p1_beat_us"] or match["p2_beat_us"]:
                who = match["player1"] if match["p1_beat_us"] else match["player2"]
                print(f"    ⚠ Fery veto aktivan: {who} nas je već srušio u ovom turniru — "
                      f"pick protiv njega neće ući na tiket.")

            # Both-players-declining zastavice (18.07., otvrdnuto iz prompta) — univerzalno,
            # sve podloge. ticket_builder._both_declining_ok ih čita.
            match["p1_declining"] = _is_declining(p1_form.get("matches", []))
            match["p2_declining"] = _is_declining(p2_form.get("matches", []))

            # Clay REST & FATIGUE DIFFERENTIAL zastavice (18.07., otvrdnuto iz prompta) —
            # CLAY-ONLY (rezoniranje vezano uz najduže razmjene u tenisu, nema dokaza za
            # grass/hard). ticket_builder._clay_fatigue_ok ih čita.
            _p1_rest = _rest_days(_last_match_date(p1_form.get("matches", [])), match.get("date", ""))
            _p2_rest = _rest_days(_last_match_date(p2_form.get("matches", [])), match.get("date", ""))
            _p1_m7d = _count_matches_last_n_days(p1_form.get("matches", []), 7)
            _p2_m7d = _count_matches_last_n_days(p2_form.get("matches", []), 7)
            match["p1_fatigue_disadvantage"] = bool(
                _p1_m7d >= 2 and _p1_rest >= 0 and _p2_rest >= 0 and _p1_rest <= _p2_rest - 2
            )
            match["p2_fatigue_disadvantage"] = bool(
                _p2_m7d >= 2 and _p1_rest >= 0 and _p2_rest >= 0 and _p2_rest <= _p1_rest - 2
            )

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
                       "decider_record": p1_decider,
                       "tiebreak_record": p1_tb,
                       "previous_tournament_level": p1_prev_tourn_level,
                       "scouting": _find_scouting(match["player1"]),
                       "titles": p1_titles,
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
                       "decider_record": p2_decider,
                       "tiebreak_record": p2_tb,
                       "previous_tournament_level": p2_prev_tourn_level,
                       "scouting": _find_scouting(match["player2"]),
                       "titles": p2_titles,
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
                        # API player ID-evi (05.08.2026, korisnikov zahtjev). Već ih imamo u
                        # ruci dok generiramo analizu, pa spremanje ne košta NIJEDAN dodatni
                        # API poziv. Svrha: bez njih se post-match statistika (asovi, break
                        # lopte, postotak servisa) ne može dohvatiti za mečeve koji NISU bili
                        # na tiketu — a to je veći dio korpusa. `ticket_matches` ih ima od
                        # 26.07., `analyzed_matches` do sada nije.
                        # Traži ALTER TABLE u Supabaseu — vidi schema.sql; `save_analyzed_match`
                        # ima defenzivni fallback ako stupci još ne postoje.
                        "player1_id": m.get("player1_id"),
                        "player2_id": m.get("player2_id"),
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
                        },
                        # Sirovi kontekst za buduću analizu (korisnikov prijedlog 2026-07-18,
                        # točke 1/2/4/7) — dob, nacionalnost, vrijeme meča, Bo3 decider record,
                        # razina prethodnog turnira. Univerzalno za sve podloge. Ne utječe na
                        # pick/confidence — čeka se uzorak prije bilo kakve analize/pravila.
                        "context_snapshot": pred.get("context_snapshot", {}),
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


def _common_opponents(p1_matches: list, p2_matches: list) -> dict:
    """Common-opponent metrika: ako A i B nisu igrali medjusobno, ali su oba igrala protiv
    istih protivnika, iz toga se izvodi relativna snaga.

    Uvedeno 04.08.2026 na korisnikov prijedlog. SAMO SE BILJEZI u context_snapshot — NE ide
    u prompt i NE utjece na nijedan pick. Razlog je isti standard koji je projekt vec dvaput
    naplatio: 31.07. je auto-analiza predlozila pravilo "dugi odmor = penal" koje bi nas
    kostalo cetiri dobitnika, a 04.08. je prividan signal o vlazi ispao konfundiran jednim
    kisnim tjednom. Prvo mjerimo je li signal stvaran, tek onda mu dajemo glas.

    Racuna se iz vec dohvacenih zadnjih 10 meceva po igracu — NULA dodatnih API poziva.
    Posljedica te odluke je nisko poklapanje (dva igraca rijetko dijele protivnika unutar
    po 10 meceva), pa je prva stvar koju cemo iz loga vidjeti KOLIKO CESTO metrika uopce
    okine. Ako je preretka da bi bila korisna, prosirenje dubine trazi vlastite API pozive
    i tada je to zasebna odluka s vlastitom cijenom.

    Vraca {} kad nema zajednickog protivnika, inace {n_common, p1_wins, p2_wins, edge, names}.
    """
    def by_opp(ms):
        out = {}
        for m in ms or []:
            o = (m.get("opponent") or "").strip().lower()
            if not o or not m.get("finished"):
                continue
            w, l = out.get(o, (0, 0))
            out[o] = (w + 1, l) if m.get("won") else (w, l + 1)
        return out

    a, b = by_opp(p1_matches), by_opp(p2_matches)
    shared = sorted(set(a) & set(b))
    if not shared:
        return {}
    p1_w = sum(a[o][0] for o in shared)
    p1_l = sum(a[o][1] for o in shared)
    p2_w = sum(b[o][0] for o in shared)
    p2_l = sum(b[o][1] for o in shared)
    p1_rate = p1_w / (p1_w + p1_l) if (p1_w + p1_l) else None
    p2_rate = p2_w / (p2_w + p2_l) if (p2_w + p2_l) else None
    return {
        "n_common": len(shared),
        "p1_record": f"{p1_w}-{p1_l}",
        "p2_record": f"{p2_w}-{p2_l}",
        # edge > 0 znaci da je P1 bio uspjesniji protiv istih protivnika
        "edge_pp": (round((p1_rate - p2_rate) * 100, 1)
                    if p1_rate is not None and p2_rate is not None else None),
        "opponents": shared[:6],
    }


def _last_match_date(matches: list) -> str:
    if not matches:
        return "N/A"
    return matches[0].get("date", "N/A")[:10]


def _is_declining(matches: list) -> bool:
    """Igrač je izgubio SVA 3 zadnja meča (0/3) — prag KOREKCIJA 20.07.2026 (korisnik uočio
    na stvarnim ponedjeljkovim mečevima da širi prag "1/3 ili lošije" isključuje 43% ATP
    250/500 prvokolaških parova, gotovo sve 1/3-vs-1/3, umjesto samo pravi rijedak slučaj).
    Originalni dokumentirani dokaz (Butvilas-Huesler, clay rules v1) bio je baš 0/3-vs-0/3
    — "1/3 ili lošije" bio je NEPROVJERENA generalizacija u deterministički filter (kod), ne
    dokazan prag. Prompt-tekst (Claudeova vlastita procjena, grass rule 7 / clay rule 3)
    NAMJERNO ostaje širi ("1/3 ili lošije") — Claude i dalje smije biti oprezan kod 1/3-vs-1/3
    kroz vlastiti confidence, samo to više nije automatski tvrdi izbačaj iz tiketa. Traži
    barem 3 odigrana meča da bi tvrdnja bila pouzdana (isti prag kao _form_trend)."""
    last3 = matches[:3]
    if len(last3) < 3:
        return False
    return sum(1 for m in last3 if m.get("won")) == 0


def _rest_days(last_match_date: str, reference_date: str) -> int:
    """Dani odmora = reference_date - last_match_date. Vraća -1 ako nepoznato (tretira se kao
    'nema fatigue signala', ne kao 0 dana odmora)."""
    if not last_match_date or not reference_date:
        return -1
    try:
        import datetime as _dt
        last = _dt.date.fromisoformat(str(last_match_date)[:10])
        ref = _dt.date.fromisoformat(str(reference_date)[:10])
        return (ref - last).days
    except (ValueError, TypeError):
        return -1


def _decider_record(matches: list) -> dict:
    """Bo3 decider-set (2-1) win/loss tally iz zadnjih odigranih mečeva — sirova varijabla,
    NE ulazi u prompt niti u odluku, samo se bilježi za buduću analizu kad se skupi uzorak
    (korisnikov prijedlog 2026-07-18, točka 2: 'koliko puta je igrač dobio/izgubio 2-1').
    Napomena: obuhvaća samo Bo3 (sets_played==3); Bo5 decideri (5 setova, Grand Slam) su
    namjerno izostavljeni jer bez podatka o formatu prošle utakmice ne možemo razlikovati
    čisti 3-0 sweep od pravog decidera u Bo5."""
    won = sum(1 for m in matches if m.get("sets_played") == 3 and m.get("won"))
    lost = sum(1 for m in matches if m.get("sets_played") == 3 and not m.get("won"))
    return {"won": won, "lost": lost}


def _tiebreak_record(matches: list) -> dict:
    """Igračev VLASTITI tiebreak učinak iz rezultata zadnjih mečeva (31.07.2026).

    Zašto: dosad smo imali samo MEĐUSOBNI tiebreak record iz H2H-a, koji je na malom
    uzorku čisti šum — dokumentirano: "Mensik 100% vs Nakashima" temeljilo se na JEDNOM
    ranijem meču i navedeno je kao potvrdni argument; pick je izgubio 7-6 3-6 6-4.
    Hard pravilo 16 (konvergiran servis) treba pravi, vlastiti uzorak igrača.

    Konvencija rezultata (provjerena na našim zapisima): score je zapisan iz perspektive
    POBJEDNIKA meča — npr. Majchrzak d. Paul "7-5 7-6(4)". Zato se strana čita preko
    zastavice `won`: ako je igrač dobio meč, prvi broj u setu je njegov; ako je izgubio,
    prvi broj je protivnikov. Bez API poziva — koristi podatke koje već imamo."""
    won = lost = 0
    for m in matches:
        score = str(m.get("score") or "")
        if "(" not in score:
            continue
        player_is_perspective_owner = bool(m.get("won"))
        for token in score.split():
            if "(" not in token:
                continue
            games = token.split("(")[0]
            if "-" not in games:
                continue
            a, _, b = games.partition("-")
            try:
                a, b = int(a), int(b)
            except ValueError:
                continue
            perspective_won_set = a > b
            player_won_tb = (perspective_won_set == player_is_perspective_owner)
            if player_won_tb:
                won += 1
            else:
                lost += 1
    return {"won": won, "lost": lost}


def _previous_tournament_level(matches: list) -> str:
    """Razina (tier) igračevog POSLJEDNJEG odigranog turnira prije trenutnog — sirova varijabla
    za buduću analizu (korisnikov prijedlog 2026-07-18, točka 7: umor/motivacija nakon velikog
    turnira, npr. Wimbledon → mali ATP 250). NE ulazi u prompt niti u odluku.
    matches su već sortirani najnoviji-prvi (ista pretpostavka kao _form_trend/_tournament_path)."""
    if not matches:
        return "N/A"
    prev_tid = matches[0].get("tournament_id", "")
    if not prev_tid:
        return "N/A"
    return df.get_tournament_tier(prev_tid) or "N/A"


def _avg_opponent_elo(matches: list, elo_data: dict) -> str:
    """Compute average ELO of last 10 opponents — quality-of-opposition signal.

    ZA REVIZIJU (uoceno 07.08.2026 iz GitHub Actions logova): protivnici bez ELO-a se TIHO
    ISPUSTAJU, a oni koji nedostaju sustavno su SLABIJI igraci — kvalifikanti, challengeri,
    wildcardi kojih nema u `elo_cache` (559 igraca). U logu od 27.07. ima nekoliko desetaka
    `ELO MISS` redaka po jednom runu. Posljedica ide u jednom smjeru: prosjek ispada
    PREVISOK, pa igrac koji je punio omjer protiv slabe konkurencije izgleda kao da je
    pobjedjivao jake. A ovo je bas nas "kvalitetom prilagodjen" signal forme.
    Koliko je to veliko NE ZNAMO jer ne biljezimo koliko je protivnika uslo u prosjek.
    Prijedlog za reviziju: vratiti i broj koristenih protivnika i spremiti ga u
    context_snapshot, pa da se pristranost moze izmjeriti umjesto naslucivati.
    STANJE 08.08.2026 11:35: broj koristenih protivnika se od danas BILJEZI
    (`_avg_opponent_elo_n`, ide u context_snapshot v9). Sama vrijednost je NEPROMIJENJENA —
    prompt dobiva isti string kao i dosad, pa se nijedan pick ne mijenja. Kad se skupi
    uzorak, usporediti WR mecheva gdje je prosjek racunat iz 9-10 protivnika naspram onih
    iz 4-5; ako se razlikuju, pristranost je stvarna i tek onda je treba ispravljati.

    ZA REVIZIJU (08.08.2026 12:30): neovisno o pristranosti, promptu bi uz vrijednost trebao
    ici i BROJ protivnika iz kojeg je izracunata — model danas cita "Avg opponent ELO: 1712"
    jednako uvjerljivo bez obzira dolazi li iz deset protivnika ili iz cetiri. Vidi
    DECISION_INPUTS.md tocku 4; ide u paket s ostalim mjerama pouzdanosti."""
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


def _avg_opponent_elo_n(matches: list, elo_data: dict) -> dict:
    """Koliko je protivnika stvarno uslo u `_avg_opponent_elo`, i koliko ih je bilo ukupno.

    Uvedeno 08.08.2026 11:35 — SAMO ZA BILJEZENJE, ne ulazi u prompt. Vidi obrazlozenje
    u `_avg_opponent_elo`: protivnici bez ELO-a se ispustaju, a nedostaju sustavno slabiji,
    pa prosjek ispada previsok. Bez ovog broja se velicina te pristranosti ne moze izmjeriti."""
    from agent import data_fetcher as _df
    total = used = 0
    for m in matches[:10]:
        opp = m.get("opponent", "")
        if not opp:
            continue
        total += 1
        e = _df.find_player_elo(opp, elo_data).get("elo_overall", 0)
        if e and e > 1000:
            used += 1
    return {"used": used, "total": total}


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


def _gate_by_screenshot(matches: list, screenshot_today: dict, screenshot_tomorrow: dict) -> list:
    """Screenshot-isključivost. JEDNO pravilo, bez iznimaka:

        meč prolazi ako i samo ako je njegov PAR na screenshotu (danas ∪ sutra);
        ako screenshota nema, ne prolazi ništa.

    PREPISANO 11.08.2026 18:44 nakon incidenta koji je stara verzija propustila.
    Stara je gate aktivirala PO DANU — samo za datum koji ima vlastiti screenshot:

        gate_active = (d == today_str and gate_today) or (d == tomorrow_str and gate_tomorrow) ...

    Dvije rupe koje je to ostavljalo:
      (1) korisnik uploada SAMO "danas" -> `gate_tomorrow` je False -> svaki sutrašnji meč
          prolazi NEPROVJEREN. Dogodilo se 11.08.2026: uploadana su 4 montrealska
          četvrtfinala pod "danas", a listić je izašao s 3 Cincinnati kvalifikacijska meča
          i 1 Montrealom — sve četiri noge s datumom 12.08., dana bez ijednog screenshota.
      (2) nema screenshota uopće -> `return matches` -> prolazi SVE. Tako je run u 15:08
          istog dana analizirao 21 kvalifikacijski meč (21 Claude poziv) na praznoj tablici.

    ZAŠTO PO PARU, A NE PO DANU — korisnikovo objašnjenje 11.08.2026: SuperSport stavlja
    mečeve koji počinju poslije ponoći (01:00, 02:00) pod "DANAS", jer se sutra više ne može
    kladiti na nešto što je odigrano. API takav meč datira SUTRAŠNJIM danom. Provjera po
    datumu bi ga zato promašila; provjera po imenima ga hvata bez obzira na datum.
    Provjereno na stvarnim podacima 11.08.: od 4 uploadana para njih 2 (Menšik/Shelton,
    Merida/Tien) API datira 12.08. — oba ispravno prolaze, dok svih 21 Cincinnati pada.

    Nestali su `gate_today`, `gate_tomorrow`, `always_gated_dates`, usporedba datuma i
    `return matches` fallback — svi su bili zakrpe na simptom, a ne na uzrok.

    NAPOMENA: par sa screenshota koji se ne nađe među dohvaćenim mečevima NIJE nužno greška
    i namjerno se ne prijavljuje kao upozorenje (korisnikova odluka 11.08.2026). Obrnuti smjer
    je češći i benigan: kad je meč jednostran, SuperSport ne ponudi kvotu na obje strane pa
    par uopće ne uđe na screenshot — a takav pick ionako pada na pragu 1,06
    (`ticket_builder`, kombinacija i analysis-only). Ne "popravljati" to.

    Vrijeme početka meča se ovdje NE dira: `find_screenshot_time` traži par po imenima kroz
    sve screenshot dane i izvršava se poslije, pa nijedan sat sa screenshota ne može nestati.
    """
    pool = {**screenshot_today, **screenshot_tomorrow}
    if not pool:
        print("  Screenshot-isključivost: nema nijedne screenshot kvote — "
              "nijedan meč ne ulazi u obradu.")
        return []

    def _in_pool(m: dict) -> bool:
        return bool(df.find_match_odds(m.get("player1", ""), m.get("player2", ""),
                                       {}, screenshot_odds=pool))

    kept, dropped = [], []
    for m in matches:
        (kept if _in_pool(m) else dropped).append(m)

    if dropped:
        tours = sorted({m.get("tournament", "").split(" - ")[0] for m in dropped})
        print(f"  Screenshot-isključivost: izbačeno {len(dropped)} meč(eva) izvan "
              f"screenshota ({', '.join(tours)}):")
        for m in dropped:
            print(f"    - {m.get('date')} {m.get('tournament', '')} {m.get('round', '')} "
                  f"{m.get('player1')} vs {m.get('player2')}")
    print(f"  Screenshot-isključivost: zadržano {len(kept)} od {len(pool)} screenshot parova.")
    return kept


def _count_by_tournament_day(matches: list) -> dict:
    """Broj zakazanih mečeva po (turnir, datum, runda) — mjeri se PRIJE screenshot-gatea.

    Vidi poziv u glavnom toku: `_infer_rounds` procjenjuje rundu iz broja mečeva tog dana,
    a gate izbacuje sve nescreenshotano, pa bi bez ovoga brojao filtrirani skup."""
    from collections import defaultdict
    counts = defaultdict(int)
    for m in matches:
        counts[(m.get("tournament", ""), m.get("date", ""), m.get("round", ""))] += 1
    return dict(counts)


def _infer_rounds(matches: list, screenshot_odds: dict = None,
                  pre_gate_counts: dict = None) -> list:
    """
    Ispravlja NEPRAVILNE oznake runda s API-ja — ali samo kad su nemoguće ili
    neprepoznate, jer rundu ne određuje samo broj mečeva u danu (runda se
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

    TRI POPRAVKA 07.08.2026 (korisnik uočio Montreal: dio mečeva označen QF, većina R32,
    a radi se o istoj rundi). Izmjereno prije popravka: 170 od 399 redaka (42,6%) sjedilo
    je u grupi (turnir, runda) gdje isti igrač igra više puta — fizički nemoguće. Samo
    "Montreal R32": 97 redaka, 68 igrača koji se ponavljaju (npr. Hurkacz "R32" 03., 04.,
    05. i 07.08.). Runda ide RAVNO u prompt i nosi vlastita pravila (LATE-ROUND PRICING
    DISCIPLINE, hot-hand), pa kriva oznaka mijenja pickove.

    (a) Grupiranje je sada po (turnir, datum, RUNDA), ne po (turnir, datum). Dan legitimno
        nosi dvije runde — Wimbledon 02.07. R64+R32, Bastad 13.07. R32+R16, Montreal 06.08.
        R32+QF. Stara verzija je uzimala `group[0]["round"]` kao rundu CIJELOG dana, a kad
        bi ispravak okinuo, prepisala bi cijelu grupu jednom oznakom i uništila onu manjinu
        koja je bila točna.
    (b) Ljestvica za Masters dobila je prečke R64 i R128. Prije je stajala na `n >= 8 -> R32`,
        pa je svaki dan s 8+ mečeva postajao "R32" — a Masters je danas ždrijeb od 96 s 12
        dana igre, gdje druge runde imaju po 32 meča. Otud Montreal s 28 mečeva kao "R32".
    (c) Broj mečeva dolazi iz `pre_gate_counts` (izbrojan prije screenshot-gatea).
    """
    from collections import defaultdict

    screenshot_odds = screenshot_odds or {}
    pre_gate_counts = pre_gate_counts or {}
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

    # Grupiranje po (turnir, datum, RUNDA) — vidi (a) u docstringu.
    counts: dict = defaultdict(list)
    for m in matches:
        key = (m.get("tournament", ""), m.get("date", ""), m.get("round", ""))
        counts[key].append(m)

    for (tournament, date, current_round), group in counts.items():
        # Broj iz PRE-GATE prebrojavanja; pad na veličinu grupe ako ga nema (npr. pri
        # izravnom pozivu iz testova).
        n = pre_gate_counts.get((tournament, date, current_round), len(group))
        level = group[0].get("level", "")

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

        # ZA REVIZIJU (uoceno 07.08.2026): ljestvice ispod mogu vratiti ISTU oznaku koja je
        # maloprije proglasena nemogucom, pa se kriva oznaka ne popravi. Uzrok: pragovi
        # (`>= 4`, `>= 8`) ukljucuju i maksimum runde ISPOD, a ovamo se dolazi samo kad je
        # n VECI od maksimuma trenutne oznake — dakle prava runda je nuzno RANIJA (veca).
        # Pogodjeni slucajevi:
        #   ATP 250/500: oznaka QF  uz n=5..7   -> `n >= 4`  vrati QF  (max QF je 4)
        #   ATP 250/500: oznaka R16 uz n=9..15  -> `n >= 8`  vrati R16 (max R16 je 8)
        #   sve razine:  oznaka SF  uz n=3      -> `n in (2,3)` vrati SF (max SF je 2)
        # Steta je ogranicena — NE stvara novu krivu oznaku, samo ne popravi staru.
        # Popravak bi bio "inferred mora biti strogo ranija runda od current_round", ali to
        # mijenja rundu koja ide u prompt, dakle i pickove; model je zamrznut. Ne dirati bez
        # odluke na reviziji.
        if "Grand Slam" in level:
            if n >= 32:   inferred = "R128"
            elif n >= 16: inferred = "R64"
            elif n >= 8:  inferred = "R32"
            elif n >= 5:  inferred = "R16"
            elif n == 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"   # n == 1 → genuine final
        elif "Masters 1000" in level:
            # Ždrijeb od 96 (od 2025. Masters traju 12 dana): prve dvije runde imaju po
            # 32 meča, pa prečke R64/R128 moraju postojati — vidi (b) u docstringu.
            # OGRANIČENJE: broj mečeva sam po sebi NE razlikuje 1. od 2. runde u ždrijebu
            # od 96 — obje imaju 32 meča. Dan s 32+ mečeva ovdje dobiva "R128". To je
            # namjeran izbor, ne rješenje: procjena okida samo kad je API-jeva oznaka
            # fizički nemoguća, a redoslijed rundi API obično pogodi.
            if n >= 32:   inferred = "R128"
            elif n >= 17: inferred = "R64"
            elif n >= 9:  inferred = "R32"
            elif n >= 5:  inferred = "R16"
            elif n == 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"
        else:
            # ATP 500/250 — manji ždrijebi (28-32), ali R16 svejedno ima 7-8 mečeva
            if n >= 16:   inferred = "R32"
            elif n >= 8:  inferred = "R16"
            elif n >= 4:  inferred = "QF"
            elif n in (2, 3): inferred = "SF"
            else:         inferred = "F"

        if current_round != inferred:
            print(f"  Round fix: {tournament} ({date}) — {current_round} → {inferred} ({n} matches)")
            for m in group:
                m["round"] = inferred
                m["round_id"] = _ROUND_ID.get(inferred, 0)

    _warn_impossible_rounds(matches)
    return matches


def _warn_impossible_rounds(matches: list) -> None:
    """Prijavi ako isti igrač igra više od jednom u istoj (turnir, runda).

    Ne ispravlja ništa — samo viče. Ovakav obrazac je bio jedini pouzdan trag da su oznake
    runda krive (Montreal: 68 igrača ponovljeno unutar "R32"), a nitko ga nije gledao jer
    ga ništa nije ispisivalo. Za dan-po-dan pokretanje uhvatit će samo ono što je vidljivo
    unutar jednog runa, ali to je dovoljno da se problem primijeti rano."""
    from collections import defaultdict
    seen = defaultdict(lambda: defaultdict(int))
    for m in matches:
        key = (m.get("tournament", ""), m.get("round", ""))
        for p in (m.get("player1", ""), m.get("player2", "")):
            if p:
                seen[key][p] += 1
    for (tournament, rnd), players in seen.items():
        rep = {p: n for p, n in players.items() if n > 1}
        if rep and rnd not in ("RR", ""):
            print(f"  UPOZORENJE runda: {tournament} '{rnd}' — isti igrač igra više puta "
                  f"({', '.join(f'{p} x{n}' for p, n in list(rep.items())[:4])}). "
                  f"Oznaka runde je vjerojatno kriva.")


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
    Problem: nije moguće složiti valjanu kombinaciju unutar zadanih granica</p>
    </body></html>"""
    _send_email(f"⚠️ Tenis Agent — Nema tiketa za {format_date_hr(date)}", body)


if __name__ == "__main__":
    main()
