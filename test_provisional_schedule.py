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
check("context_version 15 (analiza 22.08.2026)", '"context_version": 15' in _pr)
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
check("context_version 15 (analiza 22.08.2026)", '"context_version": 15' in _pr)
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
check("context_version 15 (analiza 22.08.2026)", '"context_version": 15' in _pr)
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


print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVE PROŠLO")
