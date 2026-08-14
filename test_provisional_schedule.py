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
check("context_version 11", '"context_version": 11' in _pr)
check("rules_hash NIJE dirnut (predložak prompta netaknut)",
      pr._model_stamp("hard")["rules_hash"] == "2b08e904")
check("nova polja ne cure u predložak prompta",
      "schedule_provisional" not in pr.ANALYSIS_PROMPT_TEMPLATE)


print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVE PROŠLO")
