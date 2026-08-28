# -*- coding: utf-8 -*-
"""Testovi za izmjenu 14.08.2026 11:02: neobjavljen raspored za sutra -> bez uvjeta i bez dan/noć.

Pokretanje:  python test_provisional_schedule.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agent.run_daily import (_detect_provisional_schedule, _PROVISIONAL_MIN_SAME_START,
                             _PROVISIONAL_WEATHER_NOTE)
from agent import data_fetcher as df

_fails = []


def check(name, cond, detail=""):
    print(f"  {'OK  ' if cond else 'PAD '} {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        _fails.append(name)


TODAY, TOMORROW = "2026-08-14", "2026-08-15"


def m(tour, start_utc, src_date=TOMORROW, **kw):
    d = {"tournament": tour, "start_utc": start_utc, "time_source": "screenshot",
         "time_screenshot_date": src_date}
    d.update(kw)
    return d


def at(hhmm, day="15"):
    """Zagrebački sat -> ISO UTC (ljetno vrijeme, Zagreb = UTC+2)."""
    return f"2026-08-{day}T{int(hhmm[:2]) - 2:02d}:{hhmm[3:]}:00.000Z"


print("\n=== 1. Prag: 4+ na najranijem terminu ===")

# Korisnikov stvarni screenshot za 15.08: 10 parova, svih 10 na 17:00.
real_tomorrow = [m("Cincinnati Open", at("17:00")) for _ in range(10)]
check("stvarni 15.08 (10x17:00) je označen",
      _detect_provisional_schedule(real_tomorrow, TOMORROW) == {"Cincinnati Open"})

check("3 na istom terminu NIJE dovoljno (prag je 4)",
      _detect_provisional_schedule([m("T", at("17:00")) for _ in range(3)], TOMORROW) == set())
check("4 na istom terminu JEST dovoljno",
      _detect_provisional_schedule([m("T", at("17:00")) for _ in range(4)], TOMORROW) ==  {"T"})
check("prag u kodu je 4", _PROVISIONAL_MIN_SAME_START == 4)

# Raspršen raspored: 4 su najbrojniji termin, ali NIJE najraniji.
spread = ([m("T", at("17:00"))] + [m("T", at("18:10")) for _ in range(4)]
          + [m("T", at("19:20")) for _ in range(3)])
check("gleda se NAJRANIJI termin, ne najbrojniji",
      _detect_provisional_schedule(spread, TOMORROW) == set())


print("\n=== 2. Samo rubrika 'sutra' ===")

# Korisnikov stvarni screenshot za 14.08 ('danas'): objavljen raspored, ali 5 u prvom terminu.
real_today = ([m("Cincinnati Open", at("17:00", "14"), src_date=TODAY) for _ in range(5)]
              + [m("Cincinnati Open", at("18:10", "14"), src_date=TODAY) for _ in range(5)]
              + [m("Cincinnati Open", at("19:20", "14"), src_date=TODAY) for _ in range(6)]
              + [m("Cincinnati Open", at("20:30", "14"), src_date=TODAY) for _ in range(4)])
check("stvarni 14.08 'danas' (5x17:00) se NE dira",
      _detect_provisional_schedule(real_today, TOMORROW) == set())
check("'danas' se ne dira ni kad je cijeli dan na jednom satu",
      _detect_provisional_schedule(
          [m("T", at("17:00"), src_date=TODAY) for _ in range(9)], TOMORROW) == set())
check("meč bez screenshot vremena (API sat) se ne broji",
      _detect_provisional_schedule(
          [m("T", at("17:00"), src_date=None) for _ in range(9)], TOMORROW) == set())


print("\n=== 3. Detekcija po turniru ===")

mixed = ([m("Cincinnati Open", at("17:00")) for _ in range(6)]
         + [m("Winston-Salem", at("18:00"))] + [m("Winston-Salem", at("19:30"))])
check("placeholder na jednom turniru ne povlači drugi",
      _detect_provisional_schedule(mixed, TOMORROW) == {"Cincinnati Open"})


print("\n=== 4. Mečevi iza ponoći: najraniji TRENUTAK, ne sat na ekranu ===")

# 'sub 01:00' je po satu najmanji, ali je stvarno ZADNJI meč liste.
past_midnight = ([m("T", at("01:00", "16"))]
                 + [m("T", at("17:00")) for _ in range(4)])
check("01:00 sljedećeg dana ne broji se kao najraniji termin",
      _detect_provisional_schedule(past_midnight, TOMORROW) == {"T"})

# Kontrola: da se uspoređuje sat kao string, '01:00' bi bio najraniji s brojem 1 -> ne bi palo.
one_late = [m("T", at("01:00", "16"))] + [m("T", at("17:00")) for _ in range(3)]
check("ista lista s 3 na 17:00 ne pada (potvrda da prag stvarno gleda 17:00)",
      _detect_provisional_schedule(one_late, TOMORROW) == set())


print("\n=== 5. Poruka u promptu ===")

check("poruka nije golo N/A", "N/A" not in _PROVISIONAL_WEATHER_NOTE)
check("poruka kaže da raspored nije konačan",
      "schedule is not final" in _PROVISIONAL_WEATHER_NOTE)
check("poruka zabranjuje čitanje izostanka kao prednosti",
      "either player" in _PROVISIONAL_WEATHER_NOTE)
check("poruka pokriva i dan/noć", "day/night" in _PROVISIONAL_WEATHER_NOTE)


print("\n=== 6. find_screenshot_entry vraća rubriku ===")

ss = {TODAY: {"Alcaraz Carlos|Sinner Jannik": {"p1": "Alcaraz Carlos", "p2": "Sinner Jannik",
                                               "p1_odds": 1.8, "p2_odds": 2.0,
                                               "start_time": "17:00"}},
      TOMORROW: {"Zverev Alexander|Rune Holger": {"p1": "Zverev Alexander", "p2": "Rune Holger",
                                                  "p1_odds": 1.5, "p2_odds": 2.5,
                                                  "start_time": "16:00"}}}
d, e = df.find_screenshot_entry("Alcaraz Carlos", "Sinner Jannik", ss)
check("par iz 'danas' vraća današnji datum", d == TODAY and e.get("start_time") == "17:00")
d, e = df.find_screenshot_entry("Rune Holger", "Zverev Alexander", ss)
check("par iz 'sutra' vraća sutrašnji datum (i obrnut redoslijed imena)", d == TOMORROW)
d, e = df.find_screenshot_entry("Nepoznat Igrac", "Drugi Igrac", ss)
check("nepoznat par vraća ('', {})", d == "" and e == {})

# Stara funkcija mora raditi identično kao prije refaktora.
check("find_screenshot_time i dalje vraća ISO UTC",
      df.find_screenshot_time("Alcaraz Carlos", "Sinner Jannik", ss).startswith("2026-08-14T15:00"))
check("find_screenshot_time za nepoznat par vraća ''",
      df.find_screenshot_time("Nepoznat Igrac", "Drugi Igrac", ss) == "")


print("\n=== 7. Ožičenje kroz pipeline ===")

import inspect
from agent import predictor as pr

_rd = inspect.getsource(sys.modules["agent.run_daily"])
_pr = inspect.getsource(pr)

# Oba dohvata prognoze moraju biti preskočena — i satni i grubi fallback po danu.
_wx = _rd.split("Dohvaćam vremenske uvjete")[1]
check("dohvat prognoze preskače označene mečeve",
      _wx.count('if match.get("schedule_provisional"):') >= 2)
check("označeni meč dobiva poruku umjesto prognoze",
      "_PROVISIONAL_WEATHER_NOTE" in _wx and 'match["weather_data"] = {}' in _wx)
check("local_time/session se ne postavljaju kad raspored nije objavljen",
      'if not match.get("schedule_provisional") else None' in _rd)
check("wave_first ostaje prazan, ne lažni True",
      'match["wave_first"] = None' in _rd)
check("placeholder ne definira početak vala ostalima",
      'or match.get("schedule_provisional")' in _rd)

check("prompt dobiva eksplicitan razlog umjesto sata",
      "Unknown — tomorrow's schedule is not final" in _pr)
check("snapshot bilježi schedule_provisional", '"schedule_provisional"' in _pr)
check("snapshot bilježi iz koje rubrike je sat", '"scheduled_start_source_date"' in _pr)
check("context_version 17 (snapshot i kod neuspjele analize, 27.08.2026)", '"context_version": 17' in _pr)
check("rules_hash a0424315 (era od 22.08.2026)",
      pr._model_stamp("hard")["rules_hash"] == "a0424315")
check("nova polja ne cure u predložak prompta",
      "schedule_provisional" not in pr.ANALYSIS_PROMPT_TEMPLATE)


print("\n=== 8. Dob: popravljen dohvat, ali NAMJERNO izvan prompta (15.08.2026) ===")

check("_get_age cita `birthday` (stvarni naziv iz API-ja)",
      df._get_age({"birthday": "2001-08-03T00:00:00.000Z"}) is not None)
check("dob iz `birthday` je smislena", 20 <= (df._get_age({"birthday": "2001-08-03T00:00:00.000Z"}) or 0) <= 30)
check("stari nazivi i dalje rade (fallback)",
      df._get_age({"dateOfBirth": "1995-05-22"}) is not None)
check("izravno polje `age` ima prednost", df._get_age({"age": 27}) == 27)
check("nema podatka -> None", df._get_age({}) is None)
check("besmislena dob se odbacuje", df._get_age({"age": 99, "birthday": ""}) is None)

check("dob NE ide u prompt dok traje mjerenje", pr._AGE_TO_PROMPT is False)
check("dob se ipak biljezi u snapshot", '"age_in_prompt"' in _pr)
check("context_version 17 (snapshot i kod neuspjele analize, 27.08.2026)", '"context_version": 17' in _pr)
check("rules_hash a0424315 (era od 22.08.2026)",
      pr._model_stamp("hard")["rules_hash"] == "a0424315")


print("\n=== 9. Tržišni konsenzus — samo mjeri, ne odlučuje (15.08.2026) ===")

from agent import market as mkt

# de-vig: dvije kvote 2.00/2.00 -> 50/50; marža se mora maknuti
_p1, _p2 = mkt.devig(2.0, 2.0)
check("devig 2.00/2.00 -> 50/50", abs(_p1 - 0.5) < 1e-9 and abs(_p2 - 0.5) < 1e-9)
_p1, _p2 = mkt.devig(1.5, 2.5)
check("devig zbroj je uvijek 1", abs(_p1 + _p2 - 1.0) < 1e-9)
check("devig favorita drži iznad 50%", _p1 > 0.5)
check("besmislene kvote -> (None, None)", mkt.devig(0, 2.0) == (None, None))
check("kvota 1.00 se odbacuje", mkt.devig(1.0, 5.0) == (None, None))

check("EV: p=0,55 uz kvotu 2,00 = +10%", abs(mkt.expected_value(0.55, 2.0) - 0.1) < 1e-9)
check("EV: poštena oklada = 0", abs(mkt.expected_value(0.5, 2.0)) < 1e-9)
check("EV bez kvote -> None", mkt.expected_value(0.5, None) is None)

# consensus: medijan preko kuća, oštre odvojeno
_ev = {"home_team": "A Player", "away_team": "B Player", "bookmakers": [
    {"key": "softbook1", "markets": [{"key": "h2h", "outcomes": [
        {"name": "A Player", "price": 2.0}, {"name": "B Player", "price": 2.0}]}]},
    {"key": "softbook2", "markets": [{"key": "h2h", "outcomes": [
        {"name": "A Player", "price": 1.9}, {"name": "B Player", "price": 2.1}]}]},
    {"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
        {"name": "A Player", "price": 1.8}, {"name": "B Player", "price": 2.2}]}]},
]}
_c = mkt.consensus(_ev)
check("consensus računa preko svih kuća", _c["n_books"] == 3)
check("oštre kuće se broje odvojeno", _c["n_sharp"] == 1)
check("p_best uzima oštru kuću kad postoji", abs(_c["p_best"] - _c["p_sharp"]) < 1e-9)
check("p_median se razlikuje od p_sharp", _c["p_median"] != _c["p_sharp"])
check("spread bilježi neslaganje kuća", _c["spread"] > 0)

# uparivanje: SuperSport piše "Prezime Ime", API "Ime Prezime"
_idx = [dict(_c, home="Alexander Zverev", away="Cameron Norrie")]
check("uparuje obrnut redoslijed imena",
      bool(mkt.find_for_pair(_idx, "Zverev Alexander", "Norrie Cameron")))
_f = mkt.find_for_pair(_idx, "Norrie Cameron", "Zverev Alexander")
check("preokreće vjerojatnost kad je par obrnut",
      _f.get("flipped") is True and abs(_f["p_best"] - (1 - _c["p_best"])) < 1e-9)
check("nepoznat par -> {}", mkt.find_for_pair(_idx, "Neki Igrac", "Drugi Igrac") == {})

# najvažnije: tržište NE smije doći do prompta
check("market_p NIJE u predlošku prompta", "market_p" not in pr.ANALYSIS_PROMPT_TEMPLATE)
check("snapshot bilježi market_p", '"market_p"' in _pr)
check("snapshot bilježi EV picka", '"market_ev_pick"' in _pr)
check("context_version 17 (snapshot i kod neuspjele analize, 27.08.2026)", '"context_version": 17' in _pr)
check("rules_hash a0424315 (era od 22.08.2026)",
      pr._model_stamp("hard")["rules_hash"] == "a0424315")
# ticket_builder SMIJE zapisati tržište uz odigrani pick, ali NE SMIJE po njemu birati.
_tb = inspect.getsource(__import__("agent.ticket_builder", fromlist=["x"]))
check("ticket_builder zapisuje tržište uz pick", '"market_snapshot"' in _tb)
check("ticket_builder ne uvozi market modul", "import agent.market" not in _tb
      and "from agent import market" not in _tb)
# Jedino dopusteno spominjanje trzista je gradnja retka za bazu (market_snapshot).
# Svako pojavljivanje u sortiranju, filtriranju ili sastavljanju kombinacije bilo bi
# prelazak na EV-selekciju, a to jos NIJE odluceno.
_sel = [ln.strip() for ln in _tb.splitlines()
        if "market" in ln and not ln.strip().startswith("#")
        and any(w in ln for w in ("sort", "candidates", "combo", "_selection_ok",
                                  "_pick_edge", "append(p)"))]
check("nijedna odluka o selekciji ne gleda tržište", not _sel,
      f"sumnjivi redci: {_sel[:2]}")


print("\n=== 10. Cijene svake kladionice zasebno (15.08.2026) ===")

_evt = {"id": "abc", "sport_key": "tennis_atp_x", "home_team": "A Player",
        "away_team": "B Player", "commence_time": "2026-08-15T15:00:00Z",
        "bookmakers": [
            {"key": "softbook", "markets": [{"key": "h2h", "outcomes": [
                {"name": "A Player", "price": 1.70}, {"name": "B Player", "price": 2.20}]}]},
            {"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
                {"name": "A Player", "price": 1.80}, {"name": "B Player", "price": 2.10}]}]}]}
_rows = mkt.flatten_lines([_evt], captured_utc="2026-08-15T09:00:00Z")
check("jedan redak po kladionici", len(_rows) == 2)
check("čuva se sirova kvota obje strane",
      {r["bookmaker"]: (r["odds_p1"], r["odds_p2"]) for r in _rows}["pinnacle"] == (1.80, 2.10))
check("oštra kuća je označena",
      [r["is_sharp"] for r in _rows if r["bookmaker"] == "pinnacle"] == [True])
check("meka kuća nije označena kao oštra",
      [r["is_sharp"] for r in _rows if r["bookmaker"] == "softbook"] == [False])
check("sati do početka izračunati (15:00 - 09:00 = 6h)",
      all(abs(r["hours_to_start"] - 6.0) < 0.01 for r in _rows))
check("de-vig po kladionici se razlikuje",
      len({r["p1_devig"] for r in _rows}) == 2)
check("kuća bez h2h tržišta se preskače",
      mkt.flatten_lines([dict(_evt, bookmakers=[{"key": "x", "markets": [
          {"key": "totals", "outcomes": []}]}])]) == [])
check("prazan ulaz -> prazan izlaz", mkt.flatten_lines([]) == [])

from database import supabase_client as _db
check("save_market_lines postoji", hasattr(_db, "save_market_lines"))
check("prazan upis ne zove bazu", _db.save_market_lines([]) == 0)
check("tablica opisana u schema.sql",
      "market_lines" in open("database/schema.sql", encoding="utf-8").read())


# ============================================================================
print("\n=== 11. Revizija 17.08.2026: raspršenost pouzdanosti + mjerene kazne ===")

# --- strop 64 -> 70 ---
check("strop podignut na 70", pr._CONF_CEILING == 70.0)
_r = {"confidence": 74.0, "pick": "A", "above_64_basis": None}
pr._enforce_confidence_ceiling(_r)
check("74 bez obrazloženja -> clamp na 70", _r["confidence"] == 70.0)
check("clamp se bilježi", bool(_r.get("ceiling_enforced")))

_r = {"confidence": 68.0, "pick": "A", "above_64_basis": None}
pr._enforce_confidence_ceiling(_r)
check("68 PROLAZI (prije bi bilo srezano na 64)", _r["confidence"] == 68.0)
check("prolaz se ne bilježi kao clamp", _r.get("ceiling_enforced") is None)

_r = {"confidence": 76.0, "pick": "A",
      "above_64_basis": {"confirmations": ["hard ELO +180", "serve pts 68.4 vs 61.3"],
                         "what_would_beat_it": "ako Faria servira iznad 65%"}}
pr._enforce_confidence_ceiling(_r)
check("76 s dvije mjerene potvrde + downside PROLAZI", _r["confidence"] == 76.0)

# --- mjerene kazne ---
check("kazne postoje", hasattr(pr, "_apply_measured_penalties"))
check("Med-Low kazna 4pp", pr._SCOUTING_MEDLOW_PENALTY == 4.0)
check("tržišni autsajder kazna 5pp", pr._MARKET_UNDERDOG_PENALTY == 5.0)

_m = {"player1": "Jack Draper", "player2": "Martin Landaluce", "market_p": 0.45}
_r = {"confidence": 64.0, "pick": "Jack Draper"}
pr._apply_measured_penalties(_r, _m, {"scouting": {"confidence": "Med-Low"}},
                             {"scouting": {"confidence": "High"}})
check("Med-Low + autsajder = -9pp", _r["confidence"] == 55.0)
check("kazne se bilježe pojedinačno", len(_r["measured_penalties"]["applied"]) == 2)

_r = {"confidence": 64.0, "pick": "Martin Landaluce"}
pr._apply_measured_penalties(_r, _m, {"scouting": {"confidence": "Med-Low"}},
                             {"scouting": {"confidence": "High"}})
check("kazna gleda scouting NAŠEG picka, ne player1", _r["confidence"] == 64.0)

# Korisnikovo pravilo (08.08.2026): ne kažnjavati kvotu zato što je velika.
_r = {"confidence": 64.0, "pick": "X"}
pr._apply_measured_penalties(_r, {"player1": "X", "player2": "Y", "market_p": 0.55},
                             {"scouting": {}}, {"scouting": {}})
check("visoka kvota uz tržišnu podršku NIJE kažnjena", _r["confidence"] == 64.0)

_r = {"confidence": 64.0, "pick": "X"}
pr._apply_measured_penalties(_r, {"player1": "X", "player2": "Y"},
                             {"scouting": {}}, {"scouting": {}})
check("bez tržišne cijene nema kazne", _r.get("measured_penalties") is None)

# --- prompt ---
check("prompt traži raspon pouzdanosti", "CONFIDENCE MUST SPREAD" in _pr)
check("stari strop 64 maknut iz prompta", "CONFIDENCE CEILING AT 64%" not in _pr)
check("hold% označen kao izvedena veličina", "DERIVED from the number to its left" in _pr)
check("pragovi potvrde bazdareni na serve_pts_won",
      "USE THE SERVE-POINTS-WON GAP, NOT THE HOLD GAP" in _pr)
check("tržišni autsajder objašnjen u promptu",
      "de-vigged consensus at or below 50%" in _pr)
check("izričito NIJE pravilo protiv velikih kvota",
      "This is NOT a rule against big odds" in _pr)
check("snapshot bilježi sirovi servisni jaz", '"serve_gap_raw_pp"' in _pr)
check("snapshot bilježi kazne", '"measured_penalties"' in _pr)

# --- drugo hvatanje cijena ---
import os as _os
check("skripta za zatvaranje linije postoji",
      _os.path.exists("scripts/capture_market_close.py"))
_cap = open("scripts/capture_market_close.py", encoding="utf-8").read()
check("zatvaranje linije ne dira selekciju",
      "Ne ulazi ni u jednu odluku" in _cap and "build_ticket" not in _cap)
check("workflow za zatvaranje linije postoji",
      _os.path.exists(".github/workflows/market_close.yml"))
_wf = open(".github/workflows/market_close.yml", encoding="utf-8").read()
check("workflow ima cron", "cron:" in _wf)
check("workflow ima ODDS_API_KEY", "ODDS_API_KEY" in _wf)

# --- što NIJE dirano (attribution) ---
_tb = open("agent/ticket_builder.py", encoding="utf-8").read()
check("prag 63% nije diran", '"min_confidence": 63.0' in
      open("config/model_config.py", encoding="utf-8").read())
check("ticket_builder i dalje ne gleda tržište pri selekciji",
      "market_p" not in _tb.split("def build_ticket")[1].split("def ")[0]
      if "def build_ticket" in _tb else True)


# ============================================================================
print("\n=== 12. Analiza 22.08.2026: povijest na turniru, visina, biljezenje ===")

import os as _os2
_rdsrc = inspect.getsource(sys.modules["agent.run_daily"])

# --- PRIJEDLOG 2: povijest na turniru ---
check("prompt ima redak o povijesti na turniru",
      "Best at THIS tournament, last 3 seasons:" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("prompt ima pravilo o povijesti", "TOURNAMENT HISTORY" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("pravilo nosi izmjereni broj", "71.6% (n=102)" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("pravilo izricito kaze da NIJE osobni strop",
      "not a personal ceiling" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("pravilo upozorava na QF", "In QUARTER-FINALS this signal breaks down" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("run_daily racuna povijest", "_tourn_best_3y" in _rdsrc)
check("povijest se racuna za 3 sezone", "datetime.date.today().year - 3" in _rdsrc)
check("_format_tourn_hist postoji", hasattr(pr, "_format_tourn_hist"))
check("0 se ne cita kao 'nikad nije igrao'",
      "no trace" in pr._format_tourn_hist(0))
check("3 -> polufinale", pr._format_tourn_hist(3) == "semi-final")
check("5 -> naslov", "title" in pr._format_tourn_hist(5))

# --- PRIJEDLOG 4: visina kao OPIS, ne prediktor ---
check("prompt ima redak Build:", "Build: {p1_build}" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("prompt ima pravilo o visini", "HEIGHT AND BUILD" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("pravilo izricito zabranjuje 'visi pobjedjuje'",
      'NEVER write "X is taller so he should win"' in pr.ANALYSIS_PROMPT_TEMPLATE)
check("pravilo nosi nulti nalaz", "r = +0.005 (P=0.947)" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("_format_build postoji", hasattr(pr, "_format_build"))
check("build spaja visinu/tezinu/ruku",
      pr._format_build({"height_cm": 198, "weight_kg": 90, "plays": "Right-Handed"})
      == "198 cm, 90 kg, Right-Handed")
check("build bez podataka -> N/A", pr._format_build({}) == "N/A")
check("build s djelomicnim podatkom radi", pr._format_build({"height_cm": 185}) == "185 cm")

# --- kategorije key_factors: 6 slotova, 4+5 spojeni ---
check("kategorija 4 je spojena", "4. Matchup & conditions" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("kategorija 5 je nova", "5. Tournament history & context" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("i dalje 6 kategorija (own read ostaje 6.)",
      "6. Own read" in pr.ANALYSIS_PROMPT_TEMPLATE)
check("stara zasebna kategorija stila je maknuta",
      "4. Style matchup —" not in pr.ANALYSIS_PROMPT_TEMPLATE)

# --- PRIJEDLOG 1 + 3: biljezenje ---
for _f in ("p1_matches_7d", "p1_sets_7d", "p1_days_rest", "p1_avg_opp_elo", "p1_form_5",
           "p1_form_10", "p1_surface_record", "p1_tournament_path", "p1_ranking",
           "p1_ranking_trend", "p1_height_cm", "p1_weight_kg", "p1_plays",
           "round_is_qf", "p1_tourn_best_3y"):
    check(f"snapshot biljezi {_f}", f'"{_f}"' in _pr)
check("days_rest se sprema kao BROJ", hasattr(pr, "_days_rest_num"))
check("'3 days' -> 3", pr._days_rest_num("3 days") == 3)
check("'N/A' -> None", pr._days_rest_num("N/A") is None)

# --- nista od novoga ne smije diktirati selekciju ---
_tbsrc = open("agent/ticket_builder.py", encoding="utf-8").read()
check("ticket_builder ne zna za povijest na turniru", "tourn_best_3y" not in _tbsrc)
check("ticket_builder ne zna za visinu", "height_cm" not in _tbsrc)
check("QF se samo biljezi, ne kaznjava", "round_is_qf" not in _tbsrc)

# --- PRIJEDLOG 5: harvest povijesti meceva ---
check("skripta za harvest postoji", _os2.path.exists("scripts/harvest_player_history.py"))
_hv = open("scripts/harvest_player_history.py", encoding="utf-8").read()
check("harvest ne dira selekciju", "NE ULAZI NI U JEDNU ODLUKU" in _hv)
check("harvest ima stabilan kljuc meca", "match_key" in _hv)
check("tablica opisana u schema.sql",
      "player_match_history" in open("database/schema.sql", encoding="utf-8").read())


# ============================================================================
print("\n=== 13. Hvatanje zatvarajuce linije + CLV (22.08.2026 15:20) ===")

import os as _os3
_cap = open("scripts/capture_market_close.py", encoding="utf-8").read()
_wf = open(".github/workflows/market_close.yml", encoding="utf-8").read()

# --- filtar na prozor prije pocetka ---
check("skripta ima --max-hours", "--max-hours" in _cap)
check("zadani prozor je 2.5h", "DEFAULT_MAX_HOURS = 2.5" in _cap)
check("filtar koristi hours_to_start", 'r["hours_to_start"] <= args.max_hours' in _cap)
check("prazan prozor nije greska",
      "Nijedan mec ne pocinje u tom prozoru" in _cap and "return 0" in _cap)
check("skripta ima --dry-run", "--dry-run" in _cap)
check("argparse je uvezen", "import argparse" in _cap)

# --- zasto je stari raspored bio pogresan, zapisano ---
check("zapisano zasto je prvi raspored pao", "ZASTO JE PRVI RASPORED BIO POGRESAN" in _cap)
check("zapisan mjereni udio unutar 2h", "5,1%" in _cap)
check("zapisan medijan razmaka snimki", "26 SATI" in _cap)

# --- CLV obrazlozenje (korisnikovo pitanje) ---
check("zapisano zasto mjerimo cijenu koju ne igramo", "CLV" in _cap)
check("zapisan racun snage ishod vs cijena",
      "~4.500 meceva" in _cap and "~46 meceva" in _cap)
check("zapisana ograda o mijesanju dviju kuca",
      "mijesa dvije kuce" in _cap or "mijesa dvije kuće" in _cap)

# --- workflow: tri termina ---
check("workflow ima tri crona", _wf.count("- cron:") == 3)
for _c in ("30 16 * * *", "30 20 * * *", "30 0 * * *"):
    check(f"cron {_c} postoji", _c in _wf)
check("workflow prosljedjuje --max-hours", "--max-hours" in _wf)
check("workflow objasnjava korisnikov tijek rada",
      "NE MOGU promijeniti nijedan njegov tiket" in _wf)

# --- CLV izvjestaj ---
check("clv_report postoji", _os3.path.exists("scripts/clv_report.py"))
_clv = open("scripts/clv_report.py", encoding="utf-8").read()
check("clv_report ne ulazi u pipeline", "NE ULAZI NI U JEDNU ODLUKU" in _clv)
check("clv_report zna za lose stare podatke", "GOOD_CAPTURE_FROM" in _clv)
check("clv_report upozorava kad je snimka daleko",
      "zavrsna snimka je daleko od pocetka" in _clv)
check("clv_report racuna interval pouzdanosti", "95% interval" in _clv)
check("clv_report nosi polaznu tocku -0,53pp", "-0,53pp" in _clv)

# --- nista od ovoga ne smije dirati selekciju ---
_tb2 = open("agent/ticket_builder.py", encoding="utf-8").read()
check("ticket_builder ne zna za CLV", "clv" not in _tb2.lower())
check("hvatanje ne uvozi ticket_builder", "ticket_builder" not in _cap)


# ============================================================================
print("\n=== 14. Zastita od curenja u znacajkama iz povijesti (22.08.2026 17:05) ===")

from agent import history_features as hf

# --- osnovne brave ---
check("vremenska brava je 3 dana", hf.MIN_DAYS_BEFORE == 3)
check("brava po paru je 5 dana", hf.SAME_PAIR_WINDOW == 5)

_H = [{"date": "2026-08-01", "won": True,  "opp": "Rafael Jodar",     "score": "6-3 6-4"},
      {"date": "2026-08-09", "won": False, "opp": "Brandon Nakashima", "score": "4-6 6-3 6-2"},
      {"date": "2026-08-11", "won": True,  "opp": "Marin Cilic",      "score": "7-6(3) 6-4"}]

# meč od 11.08. je 1 dan prije predikcije -> mora ispasti
_safe = hf.safe_history(_H, as_of="2026-08-12")
check("meč od jučer NE ulazi u povijest", all(m["date"] != "2026-08-11" for m in _safe))
check("meč od 3+ dana ranije ULAZI", any(m["date"] == "2026-08-09" for m in _safe))
check("meč od 11 dana ranije ULAZI", any(m["date"] == "2026-08-01" for m in _safe))

# brava po paru: isti protivnik unutar 5 dana ispada i kad je >=3 dana
_safe2 = hf.safe_history(_H, as_of="2026-08-13", opponent="Nakashima Brandon")
check("isti protivnik unutar 5 dana ispada (obrnut redoslijed imena)",
      all(not hf.same_player(m["opp"], "Nakashima Brandon") for m in _safe2))
_safe3 = hf.safe_history(_H, as_of="2026-08-20", opponent="Nakashima Brandon")
check("isti protivnik izvan 5 dana OSTAJE",
      any(hf.same_player(m["opp"], "Nakashima Brandon") for m in _safe3))

# bez as_of se NE smije moci pozvati
try:
    hf.safe_history(_H, as_of=None)
    _ok = False
except ValueError:
    _ok = True
check("bez as_of baca gresku (nema tihog curenja)", _ok)

# --- konkretan slucaj koji je otkrio bug ---
_med = [{"date": "2026-08-05", "won": False, "opp": "Botic Van De Zandschulp", "score": "6-3 7-6(5)"}]
check("Medvedev slucaj: isti mec pod drugim datumom je odbacen",
      hf.h2h_record(_med, as_of="2026-08-06", opponent="Van De Zandschulp Botic") is None)

# --- pomocne ---
check("parse_sets cita rezultat", hf.parse_sets("6-4 3-6 7-6(5)") == [(6,4),(3,6),(7,6)])
check("predaja se prepoznaje", hf.is_retirement("6-2 2-0 ret.") is True)
check("normalan rezultat nije predaja", hf.is_retirement("6-4 6-2") is False)
check("prazan rezultat ne ruси", hf.parse_sets(None) == [])

# --- znacajke postuju zastitu ---
_long = [{"date": "2026-07-%02d" % d, "won": d % 2 == 0, "opp": "X Y",
          "score": "6-4 6-3" if d % 2 == 0 else "3-6 4-6"} for d in range(1, 20)]
check("matches_in_window ne broji zadnja 2 dana",
      hf.matches_in_window(_long + [{"date": "2026-08-11", "won": True, "opp": "Z W",
                                     "score": "6-1 6-1"}], as_of="2026-08-12") == 0)
check("comeback_rate vraca None bez uzorka",
      hf.comeback_rate(_H, as_of="2026-08-20", min_n=10) is None)
check("build_history_index preskace mec bez pobjednika",
      hf.build_history_index([{"match_date": "2026-08-01", "player1_id": "1",
                               "player2_id": "2", "winner_id": None}]) == {})

# --- modul NE SMIJE biti u pipelineu ---
for _f in ("agent/run_daily.py", "agent/predictor.py", "agent/ticket_builder.py"):
    check(f"{_f.split('/')[-1]} ne uvozi history_features",
          "history_features" not in open(_f, encoding="utf-8").read())

# --- postojeca logika vremena NIJE dirnuta (korisnikovo izricito upozorenje) ---
_rd2 = open("agent/run_daily.py", encoding="utf-8").read()
check("prekosutra se i dalje dohvaca uvjetno", "fetch_day_after = bool(screenshot_tomorrow)" in _rd2)
check("_gate_by_screenshot i dalje postoji", "_gate_by_screenshot" in _rd2)
check("_detect_provisional_schedule i dalje postoji", "_detect_provisional_schedule" in _rd2)
_df2 = open("agent/data_fetcher.py", encoding="utf-8").read()
check("get_recent_form NIJE dirnut (nema filtra po datumu)",
      "def get_recent_form" in _df2 and "MIN_DAYS_BEFORE" not in _df2)

# --- harvest: ispravni kljucevi ---
_hv2 = open("scripts/harvest_player_history.py", encoding="utf-8").read()
check("harvest cita tournamentId", 'g.get("tournamentId")' in _hv2)
check("harvest cita roundId", 'g.get("roundId")' in _hv2)
check("zapisano da podloge nema", "Podloge u `past-matches` NEMA" in _hv2)


# =============================================================================================
# v16 BILJEZENJE + POPRAVAK ANALIZE GUBITAKA (26.08.2026 15:20)
# Obje izmjene su namjerno BEZ ucinka na pickove. Ovi testovi cuvaju bas to.
# =============================================================================================
print("\n=== 23. v16: biljezenje kandidata + analiza gubitaka (26.08.2026) ===")

import agent.run_daily as _rd_mod

# --- prompt i pravila NISU dirani: zig ere mora ostati isti ---
import hashlib as _hl
from agent.predictor import _HARD_RULES_V1 as _HR, ANALYSIS_PROMPT_TEMPLATE as _APT
check("rules_hash hard ostaje a0424315 (prompt netaknut)",
      _hl.md5((_HR + _APT).encode()).hexdigest()[:8] == "a0424315")

# --- nove velicine se BILJEZE, ali NE ulaze u prompt ---
_prv = open("agent/predictor.py", encoding="utf-8").read()
for _f in ("p1_avg_opp_elo_5", "p1_form_quality", "p1_matches_3_9d", "age_gap"):
    check(f"{_f} ide u context_snapshot", f'"{_f}"' in _prv)
    check(f"{_f} NIJE u predlosku prompta", "{" + _f + "}" not in _APT)
check("context_version 16", '"context_version": 17' in _prv)

# --- zastita od curenja u novom brojacu opterecenja ---
_m = [{"date": "2026-08-19", "won": True}, {"date": "2026-08-17", "won": True},
      {"date": "2026-08-11", "won": False}, {"date": "2026-08-05", "won": True}]
check("matches_in_window ne broji zadnja 2 dana prije meca",
      _rd_mod._count_matches_in_window(_m, 3, 9, "2026-08-20") == 2)
check("matches_in_window racuna od datuma MECA, ne od danas",
      _rd_mod._count_matches_in_window(_m, 3, 9, "2026-08-14") == 2)
check("matches_in_window prazna lista = 0",
      _rd_mod._count_matches_in_window([], 3, 9, "2026-08-20") == 0)

# --- form_quality: bez uzorka vraca None, i raste s kvalitetom protivnika ---
_elo = {"aa bb": {"player_name": "Aa Bb", "elo_hard": 1900, "elo_overall": 1900},
        "cc dd": {"player_name": "Cc Dd", "elo_hard": 1500, "elo_overall": 1500}}
check("form_quality vraca None ispod 3 meca",
      _rd_mod._form_quality([{"opponent": "Aa Bb", "won": True}], _elo, 5) is None)
_strong = [{"opponent": "Aa Bb", "won": True} for _ in range(4)]
_weak = [{"opponent": "Cc Dd", "won": True} for _ in range(4)]
_fs, _fw = _rd_mod._form_quality(_strong, _elo, 5), _rd_mod._form_quality(_weak, _elo, 5)
check("form_quality: iste pobjede vrijede vise protiv jacih",
      _fs is not None and _fw is not None and _fs > _fw)
check("form_quality: pobjede protiv slabih daju negativan rezultat", _fw < 0)

# --- avg_opp_elo_lastn biljezi i koliko je protivnika stvarno uslo ---
_q = _rd_mod._avg_opponent_elo_lastn(
    [{"opponent": "Aa Bb"}, {"opponent": "Cc Dd"}, {"opponent": "Nepoznat Igrac"}], _elo, 5)
check("avg_opp_elo_lastn racuna prosjek bez podrazumijevanih", _q["value"] == 1700.0)
check("avg_opp_elo_lastn biljezi used/total/defaulted (pristranost mjerljiva)",
      _q["used"] == 2 and _q["total"] == 3 and _q["defaulted"] == 1)
check("neprepoznat igrac se NE broji kao 1500 u novom zapisu",
      _rd_mod._is_default_elo({"elo_overall": 1500, "elo_hard": 1500,
                               "elo_clay": 1500, "elo_grass": 1500}) is True)
check("pravi ELO od 1500 na jednoj podlozi NIJE podrazumijevana vrijednost",
      _rd_mod._is_default_elo({"elo_overall": 1500, "elo_hard": 1820,
                               "elo_clay": 1500, "elo_grass": 1500}) is False)

# --- analiza gubitaka: bazne stope + verdikti + zabrana dodavanja postojecih ulaza ---
_fb = open("agent/feedback_analyzer.py", encoding="utf-8").read()
check("analiza gubitka ima bazne stope", "_LOSS_BASE_RATES" in _fb and "{base_rates}" in _fb)
for _v in ("[SIGNAL CONFIRMED]", "[SIGNAL NOT CONFIRMED]", "[SIGNAL CONTRADICTED]",
           "[INSUFFICIENT DATA]", "[POST-MATCH ONLY]"):
    check(f"verdikt {_v} postoji", _v in _fb)
check("rijec 'cause' je ogranicena", "is BANNED unless" in _fb)
check("dopusteno je ne predloziti nista", "No model change justified by this match." in _fb)
check("popis postojecih ulaza (protiv 'dodaj 2. servis')",
      "INPUTS THE PREDICTION MODEL ALREADY RECEIVES" in _fb and "2ND-SERVE POINTS WON" in _fb)
check("bazne stope nose datum mjerenja", "04.-26.08.2026" in _fb)

# --- automatsko azuriranje tezina i dalje ZAMRZNUTO (analiza gubitka ne smije mijenjati model) ---
check("tezine se i dalje ne azuriraju automatski", "ZAMRZNUTO AUTOMATSKO" in _fb)


# =============================================================================================
# 24. STROP TOKENA, PONOVLJENI POKUSAJ I SNAPSHOT NA GRESCI (27.08.2026 18:55)
# Povod: 3 od 4 meca sa screenshota 27.08. zavrsila su s predicted_winner=NULL jer je odgovor
# bio odrezan na stropu prije nego sto je JSON uopce poceo. Ovi testovi cuvaju sva tri popravka.
# =============================================================================================
print("\n=== 24. Strop tokena + retry + snapshot na gresci (27.08.2026) ===")

import json as _json
import agent.predictor as _P

check("strop je podignut s 2600", _P._ANALYSIS_MAX_TOKENS[0] >= 4000)
check("ponovljeni pokusaj ima veci strop",
      _P._ANALYSIS_MAX_TOKENS[1] > _P._ANALYSIS_MAX_TOKENS[0])
check("tocno dva pokusaja (ne beskonacna petlja)", len(_P._ANALYSIS_MAX_TOKENS) == 2)

_GOOD = _json.dumps({"pick": "Ana Anic", "confidence": 66, "fair_odds": 1.52, "value": True,
                     "risk_level": "medium", "risk_notes": "t", "handicap_option": None,
                     "applied_caps": [], "above_64_basis": None, "market_check": None,
                     "key_factors": ["1. Rating: x"], "analysis": "t", "skip_reason": None})
_TRUNC = "Let me work through this. Rating: Ana leads by 120 ELO, serve converged, so"

class _TBlk:
    type = "text"
    def __init__(self, t): self.text = t
class _TUsage:
    def __init__(self, n): self.output_tokens = n; self.input_tokens = 14441
class _TResp:
    def __init__(self, t, stop):
        self.content = [_TBlk(t)]; self.stop_reason = stop; self.usage = _TUsage(len(t) // 3)
class _TMsgs:
    def __init__(self, seq): self.seq = list(seq); self.calls = []
    def create(self, **kw):
        self.calls.append(kw["max_tokens"])
        t, stop = self.seq.pop(0) if self.seq else (_GOOD, "end_turn")
        return _TResp(t, stop)
class _TClient:
    def __init__(self, seq): self.messages = _TMsgs(seq)

_TMATCH = {"player1": "Ana Anic", "player2": "Bruno Buric", "surface": "Hard",
           "tournament": "Test Open - Testville", "level": "ATP 250", "round": "R16",
           "date": "2026-08-27", "odds_p1": 1.65, "odds_p2": 2.20,
           "local_time": "18:00", "session": "day", "weather": "Clear, 26C",
           "v16_logging": {"p1_avg_opp_elo_5": {"value": 1755.0, "used": 5, "total": 5,
                                                "defaulted": 0},
                           "p2_avg_opp_elo_5": {"value": 1610.0, "used": 4, "total": 5,
                                                "defaulted": 1},
                           "p1_form_quality": 0.44, "p2_form_quality": -0.18,
                           "p1_matches_3_9d": 2, "p2_matches_3_9d": 0}}
_TP1 = {"age": 24, "elo_overall": 1820, "elo_hard": 1805, "ranking": 44,
        "serve_points_won": 64.1, "hold_pct": 81.8, "return_points_won": 41.0,
        "form_recent": {"matches": []}, "scouting": {}, "titles": {}, "surface_summary": {},
        "tournament_record": {}, "avg_opp_elo": 1755, "decider_record": {"won": 2, "lost": 1},
        "tiebreak_record": {"won": 4, "lost": 2}, "news": "", "matches_7d": 2, "sets_7d": 5}
_TP2 = dict(_TP1)
_TP2.update({"age": 31, "elo_overall": 1690, "elo_hard": 1675, "ranking": 96,
             "avg_opp_elo": 1610})

_orig_client = _P._get_client
def _run(seq):
    _P._get_client = lambda: _TClient(seq)
    try:
        return _P.analyze_match(_TMATCH, _TP1, _TP2, {}, {"elo_ranking": 19}, "")
    finally:
        _P._get_client = _orig_client

_r_ok = _run([(_GOOD, "end_turn")])
_r_retry = _run([(_TRUNC, "max_tokens"), (_GOOD, "end_turn")])
_r_fail = _run([(_TRUNC, "max_tokens"), (_TRUNC, "max_tokens")])

check("uspjesan poziv daje pick", _r_ok.get("pick") == "Ana Anic")
check("uspjeh ide iz prvog pokusaja",
      _r_ok["context_snapshot"]["analysis_call"]["attempts"] == 1)
check("odrezan prvi pokusaj -> retry spasi analizu", _r_retry.get("pick") == "Ana Anic")
check("retry je zabiljezen kao drugi pokusaj",
      _r_retry["context_snapshot"]["analysis_call"]["attempts"] == 2)

# --- srz popravka 3: neuspjeh vise NE gubi predmecne uvjete ---
check("neuspjeh nema pick", _r_fail.get("pick") is None)
check("neuspjeh NE postavlja skip_reason (to je odluka modela, ne greska)",
      _r_fail.get("skip_reason") is None)
check("neuspjeh IPAK ima context_snapshot", bool(_r_fail.get("context_snapshot")))
for _f, _v in (("p1_elo_surface", 1805), ("p1_form_quality", 0.44), ("age_gap", -7.0),
               ("p1_avg_opp_elo_5", 1755.0), ("p1_matches_3_9d", 2)):
    check(f"neuspjeh cuva {_f}", _r_fail["context_snapshot"].get(_f) == _v)
check("neuspjeh je oznacen (analysis_failed)",
      _r_fail["context_snapshot"].get("analysis_failed") is True)
check("uspjeh NIJE oznacen kao neuspjeh",
      _r_ok["context_snapshot"].get("analysis_failed") is None)
check("dijagnostika biljezi rezanje na stropu",
      _r_fail["context_snapshot"]["analysis_call"]["stop_reason"] == "max_tokens")
check("dijagnostika se biljezi i kod uspjeha",
      _r_ok["context_snapshot"]["analysis_call"]["attempts"] == 1
      and _r_ok["context_snapshot"]["analysis_call"]["error"] is None)

# --- capovi/kazne se na praznom picku moraju tiho preskociti, ne srusiti ---
check("neuspjeh ne pokrece cap/kaznu",
      _r_fail["context_snapshot"].get("cap_enforced") is None
      and _r_fail["context_snapshot"].get("measured_penalties") is None)
check("neuspjeh ima confidence 0 (ne None)", _r_fail.get("confidence") == 0)

# --- API greska se NE ponavlja drugim punim pozivom (SDK to vec radi) ---
class _BoomMsgs:
    def __init__(self): self.n = 0
    def create(self, **kw):
        self.n += 1
        raise RuntimeError("simulirana API greska")
class _BoomClient:
    def __init__(self): self.messages = _BoomMsgs()
_boom = _BoomClient()
_P._get_client = lambda: _boom
try:
    _res, _meta = _P._call_analysis_model("x", "test")
finally:
    _P._get_client = _orig_client
check("API greska se ne ponavlja drugim punim pozivom", _boom.messages.n == 1)
check("API greska vraca None + poruku", _res is None and "simulirana" in str(_meta.get("error")))


print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVE PROŠLO")
