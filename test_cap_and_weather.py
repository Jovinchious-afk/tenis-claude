# -*- coding: utf-8 -*-
"""Testovi za reviziju 04.08.2026: tvrdi clamp na cap + bilježenje uvjeta.

Pokretanje:  python test_cap_and_weather.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from agent.predictor import _enforce_stated_caps, ANALYSIS_PROMPT_TEMPLATE

_fails = []


def check(name, cond, detail=""):
    print(f"  {'OK  ' if cond else 'PAD '} {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        _fails.append(name)


def base(conf, caps=None, **kw):
    r = {"pick": "Player A", "confidence": conf, "key_factors": [], "analysis": "",
         "risk_notes": ""}
    if caps is not None:
        r["applied_caps"] = caps
    r.update(kw)
    return r


print("\n=== 1. Clamp spušta na najniži proglašeni cap ===")

# Landaluce: cap 64 proglašen, emitirano 65 -> mora pasti na 64
r = base(65, [{"rule": "2", "cap": 64}])
_enforce_stated_caps(r)
check("Landaluce 65 -> 64", r["confidence"] == 64, f"dobiveno {r['confidence']}")
check("cap_enforced zabilježen", r.get("cap_enforced", {}).get("from") == 65)

# Fucsovics: cap 60, emitirano 63 -> pada na 60, tj. ispod praga 63 i ispada iz selekcije
r = base(63, [{"rule": "12", "cap": 60}])
_enforce_stated_caps(r)
check("Fucsovics 63 -> 60 (ispod praga 63)", r["confidence"] == 60)

# Van Assche: dva capa, uzima se najniži
r = base(63, [{"rule": "13", "cap": 60}, {"rule": "2", "cap": 64}])
_enforce_stated_caps(r)
check("dva capa -> uzima najniži (60)", r["confidence"] == 60)
check("zabilježeno pravilo najnižeg capa", r.get("cap_enforced", {}).get("rule") == "13")

print("\n=== 2. Clamp NE dira ono što ne smije ===")

r = base(65, [{"rule": "2", "cap": 68}])
_enforce_stated_caps(r)
check("confidence ispod capa ostaje netaknut", r["confidence"] == 65)
check("nema cap_enforced kad nije trebalo", r.get("cap_enforced") is None)

r = base(65, [])
_enforce_stated_caps(r)
check("prazna lista capova = bez učinka", r["confidence"] == 65)

r = base(65)  # polje potpuno izostavljeno (stari model / neuspjeli parse)
_enforce_stated_caps(r)
check("izostavljen applied_caps = bez učinka (graceful)", r["confidence"] == 65)

r = base(65, [{"rule": "x", "cap": 0}, {"rule": "y", "cap": 999}, {"rule": "z"}])
_enforce_stated_caps(r)
check("besmislene vrijednosti se ignoriraju, ne ruše pick", r["confidence"] == 65)

r = base(0, [{"rule": "2", "cap": 60}])
_enforce_stated_caps(r)
check("preskočen meč (conf 0) se ne dira", r["confidence"] == 0)

r = {"pick": None, "confidence": 65, "applied_caps": [{"rule": "2", "cap": 60}]}
_enforce_stated_caps(r)
check("bez picka nema clampa", r["confidence"] == 65)

print("\n=== 3. Prozna mreža SAMO upozorava, nikad ne spušta ===")

r = base(65, [], key_factors=["Rule 16 caps confidence at 60% here."])
_enforce_stated_caps(r)
check("proza NE mijenja confidence", r["confidence"] == 65)
check("proza je zabilježena kao neslaganje", r.get("cap_prose_mismatch") is not None)

r = base(65, [], key_factors=["Rule 13 cap of 60% does not apply — return is 47%."])
_enforce_stated_caps(r)
check("negirani cap se NE prijavljuje", r.get("cap_prose_mismatch") is None)

r = base(64, [{"rule": "2", "cap": 64}], key_factors=["Capped at 64% per rule 2."])
_enforce_stated_caps(r)
check("cap koji JE proglašen ne ide u prozno neslaganje",
      r.get("cap_prose_mismatch") is None)

print("\n=== 4. Poredak: fair_odds mora vidjeti spušteni broj ===")
from agent.predictor import _normalize_fair_odds

r = base(65, [{"rule": "2", "cap": 60}])
m = {"player1": "Player A", "player2": "Player B", "odds_p1": 1.9, "odds_p2": 1.9}
_enforce_stated_caps(r)
_normalize_fair_odds(r, m)
check("fair_odds izveden iz 60, ne iz 65", r["fair_odds"] == round(100 / 60, 2),
      f"dobiveno {r['fair_odds']}")

print("\n=== 5. Prompt nosi nova pravila ===")
t = ANALYSIS_PROMPT_TEMPLATE
check("applied_caps u JSON shemi", '"applied_caps"' in t)
check("upute za deklariranje capova", "DECLARE YOUR CAPS" in t)
check("'technically triggered' izrijekom znači TRIGGERED", "technically triggered" in t)
check("pravilo o vremenu prisutno", "WEATHER AND CONDITIONS MAY ONLY LOWER" in t)
check("vrijeme ne smije dizati confidence", "never warm it" in t)
check("court pace/sesija izuzeti iz restrikcije", "keep their two-way use" in t)
check("cap je strop, ne polazište (scouting)", "A CAP IS A CEILING, NOT A STARTING POINT" in t)

print("\n=== 5b. Pravilo o vjetru (Tennis_Surface_Analysis.docx) ===")
check("sekcija WIND postoji", "WIND (added 2026-08-04" in t)
check("smjer: spin kaznjen, flat nagradjen", "high-margin spin games" in t)
check("prag 15-25 km/h", "15-25 km/h" in t)
check("prag >25 km/h", "above ~25 km/h" in t)
check("vjetar smije samo spustati", "wind may only LOWER confidence" in t)
check("bez stila se pravilo NE primjenjuje", "you cannot apply this rule" in t)
check("pragovi oznaceni kao nemjereni kod nas", "NOT from our own measured corpus" in t)

print("\n=== 5c. Scouting: budzet skalira s confidenceom profila ===")
check("budzet skalira", "BUDGET SCALES WITH THE PROFILE" in t)
check("Med-Low je asimetrican", "it may raise DOUBT about a pick" in t)
check("dokumentirana tri profila", "Van Assche" in t and "Halys" in t and "Majchrzak" in t)
check("naveden udio Med-Low u tablici", "50 of 150" in t)

print("\n=== 5d. Gate i dalje izbacuje Low/Insufficient ===")
from agent.predictor import _format_scouting, _SCOUTING_MIN_CONFIDENCE
check("Low je izvan gatea", "Low" not in _SCOUTING_MIN_CONFIDENCE)
check("Insufficient je izvan gatea", "Insufficient" not in _SCOUTING_MIN_CONFIDENCE)
check("Med-Low i dalje prolazi (asimetricno, ne zabranjeno)",
      "Med-Low" in _SCOUTING_MIN_CONFIDENCE)
check("Low profil daje 'no reliable' poruku",
      "No reliable scouting profile" in _format_scouting({"confidence": "Low", "style": "x"}))
check("Med-Low profil se prikazuje s oznakom confidencea",
      "Med-Low" in _format_scouting({"confidence": "Med-Low", "style": "Baseliner"}))

print("\n=== 7. Prognoza se bira po SATU MECA, ne po podnevu ===")
import datetime as _dt
from agent import data_fetcher as _df

# Stvarni oblik odgovora: dt_txt je UTC. Montreal = UTC-4.
_series = []
for h in range(0, 48, 3):
    utc = _dt.datetime(2026, 8, 5, 0, 0) + _dt.timedelta(hours=h)
    loc = utc + _dt.timedelta(hours=-4)
    # jutro vlazno i hladno, popodne suho i vruce — kao u stvarnim podacima
    hum = 68 if loc.hour < 11 else 48
    tmp = 19.2 if loc.hour < 11 else 28.3
    _series.append({"utc": utc, "raw": {"main": {"temp": tmp, "humidity": hum},
                                        "wind": {"speed": 2.0}, "weather": [{"main": "Clear"}],
                                        "dt_txt": utc.strftime("%Y-%m-%d %H:%M:%S")}})
_orig = _df.get_forecast_series
_df.get_forecast_series = lambda city: _series
try:
    w = _df.weather_at_match_time("Montreal", "2026-08-05", 14, -4)
    check("popodnevni mec dobiva POPODNEVNU vlagu (48%, ne 68%)", w.get("humidity") == 48,
          f"dobiveno {w.get('humidity')}")
    check("popodnevni mec dobiva popodnevnu temperaturu", w.get("temp_c") == 28.3)
    check("biljezi se za koji sat vrijedi", (w.get("forecast_local_time") or "")[11:13] in ("14", "15", "13"))
    # NB: `w["hours_off"] or 99` bi za tocno 0.0 dalo 99 (0 je falsy) — usporedi izravno.
    check("hours_off je 0 kad se sat tocno poklapa", w.get("hours_off") == 0.0,
          f"dobiveno {w.get('hours_off')}")

    wm = _df.weather_at_match_time("Montreal", "2026-08-05", 8, -4)
    check("jutarnji mec i dalje dobiva jutarnju vlagu", wm.get("humidity") == 68)

    # vecernja sesija: 20:00 lokalno = 00:00 UTC IDUCI dan — ne smije promasiti datum
    we = _df.weather_at_match_time("Montreal", "2026-08-05", 20, -4)
    check("vecernja sesija ne pada na krivi UTC datum",
          bool(we) and (we.get("forecast_local_time") or "").startswith("2026-08-05"),
          f"dobiveno {we.get('forecast_local_time')}")

    check("bez offseta se NE pogadja", _df.weather_at_match_time("Montreal", "2026-08-05", 14, None) == {})
    check("bez sata se NE pogadja", _df.weather_at_match_time("Montreal", "2026-08-05", None, -4) == {})
finally:
    _df.get_forecast_series = _orig

print("\n=== 7b. Odabir zapisa prognoze: zadnji prije meca, +1h granica ===")
# Zapisi (Montreal, lokalno): 11:00, 14:00, 17:00, 20:00, 23:00
_ser = []
for h in range(0, 48, 3):
    utc = _dt.datetime(2026, 8, 5, 15, 0) + _dt.timedelta(hours=h)   # 15:00 UTC = 11:00 lok
    _ser.append({"utc": utc, "raw": {"main": {"temp": 20 + h, "humidity": 50 + h},
                                     "wind": {"speed": 2.0}, "weather": [{"main": "Clear"}],
                                     "dt_txt": utc.strftime("%Y-%m-%d %H:%M:%S")}})
_o = _df.get_forecast_series
_df.get_forecast_series = lambda city: _ser
try:
    def pick(h, m=0):
        w = _df.weather_at_match_time("Montreal", "2026-08-05", h, -4, m)
        return (w.get("forecast_local_time") or "")[11:]
    check("mec tocno na zapisu (11:00) -> 11:00", pick(11) == "11:00", pick(11))
    check("mec 30 min nakon zapisa (14:30) -> ostaje 14:00", pick(14, 30) == "14:00", pick(14, 30))
    check("korisnikov primjer: 15:00 uz zapis 14:00 -> SLJEDECI (17:00)", pick(15) == "17:00", pick(15))
    check("mec 59 min nakon (14:59) -> jos uvijek 14:00", pick(14, 59) == "14:00", pick(14, 59))
    check("mec 2h nakon (13:10 od 11:00) -> sljedeci (14:00)", pick(13, 10) == "14:00", pick(13, 10))
    check("mec 20 min nakon (14:20) -> ostaje 14:00", pick(14, 20) == "14:00", pick(14, 20))
    check("mec 1h30 nakon (15:30) -> sljedeci (17:00)", pick(15, 30) == "17:00", pick(15, 30))
    check("mec prije prvog zapisa -> uzima prvi, ne puca", pick(6) == "11:00", pick(6))
finally:
    _df.get_forecast_series = _o

print("\n=== 8. Common opponents (samo log, ne prompt) ===")
from agent.run_daily import _common_opponents

A = [{"opponent": "Carlos Alcaraz", "won": True, "finished": True},
     {"opponent": "Jack Draper", "won": False, "finished": True},
     {"opponent": "Nekog Drugog", "won": True, "finished": True}]
B = [{"opponent": "Carlos Alcaraz", "won": False, "finished": True},
     {"opponent": "Jack Draper", "won": False, "finished": True}]
co = _common_opponents(A, B)
check("nalazi 2 zajednicka protivnika", co.get("n_common") == 2, str(co))
check("P1 zapis 1-1", co.get("p1_record") == "1-1")
check("P2 zapis 0-2", co.get("p2_record") == "0-2")
check("edge pozitivan za boljeg (P1)", (co.get("edge_pp") or 0) > 0)
check("bez preklapanja vraca prazno",
      _common_opponents([{"opponent": "X", "won": True, "finished": True}],
                        [{"opponent": "Y", "won": True, "finished": True}]) == {})
check("neodigrani mecevi se ignoriraju",
      _common_opponents([{"opponent": "X", "won": True, "finished": False}],
                        [{"opponent": "X", "won": True, "finished": True}]) == {})
check("prazan ulaz ne puca", _common_opponents([], []) == {})
check("None ne puca", _common_opponents(None, None) == {})

print("\n=== 9. Vrijeme sa screenshota je izvor istine ===")
from agent.data_fetcher import _parse_clock, screenshot_start_utc, find_screenshot_time, local_match_time

check("'uto 17:00' -> 17:00", _parse_clock("uto 17:00") == "17:00")
check("'9:05' -> 09:05 (vodeca nula)", _parse_clock("9:05") == "09:05")
check("'sri 20.30' (tocka) -> 20:30", _parse_clock("sri 20.30") == "20:30")
check("prazno -> ''", _parse_clock("") == "" and _parse_clock(None) == "")
check("besmislen sat se odbija", _parse_clock("99:99") == "")
check("tekst bez sata se odbija", _parse_clock("uto") == "")

# 17:00 Zagreb ljeti (CEST, +2) = 15:00 UTC = 11:00 ET -> tocno sluzbeni pocetak sesije
u = screenshot_start_utc("2026-08-04", "17:00")
check("17:00 Zagreb (ljeto) -> 15:00 UTC", u.startswith("2026-08-04T15:00"), u)
lt = local_match_time(u, "montreal")
check("-> 11:00 lokalno u Montrealu", lt.get("local_time") == "11:00", str(lt))
check("-> oznaceno kao dnevna sesija", lt.get("session") == "day")

# zima: Zagreb je +1, pa isti sat daje drugi UTC — zato pytz, ne konstanta
uw = screenshot_start_utc("2026-01-15", "17:00")
check("zimi 17:00 Zagreb -> 16:00 UTC (pomak se racuna, ne fiksira)",
      uw.startswith("2026-01-15T16:00"), uw)

# cross-day: 01:00 Zagreb = 23:00 UTC prethodnog dana = 19:00 ET prethodnog dana
uc = screenshot_start_utc("2026-08-05", "01:00")
ltc = local_match_time(uc, "montreal")
check("vecernja sesija: 01:00 Zagreb -> 19:00 ET PRETHODNOG dana",
      ltc.get("local_time") == "19:00" and ltc.get("local_date") == "2026-08-04",
      f"{ltc.get('local_date')} {ltc.get('local_time')}")
check("local_date se vraca uz vrijeme", "local_date" in lt)

# lookup kroz vise dana
ss = {"2026-08-04": {"a|b": {"p1": "Baez Sebastian", "p2": "Bellucci Mattia",
                             "p1_odds": 1.8, "p2_odds": 2.0, "start_time": "17:00"}},
      "2026-08-05": {"c|d": {"p1": "Neki Igrac", "p2": "Drugi Igrac",
                             "p1_odds": 1.5, "p2_odds": 2.5}}}
check("nalazi vrijeme za par", find_screenshot_time("Sebastian Baez", "Mattia Bellucci", ss).startswith("2026-08-04T15:00"))
check("radi i s obrnutim redoslijedom igraca",
      find_screenshot_time("Mattia Bellucci", "Sebastian Baez", ss).startswith("2026-08-04T15:00"))
check("par bez start_time -> ''", find_screenshot_time("Neki Igrac", "Drugi Igrac", ss) == "")
check("nepoznat par -> ''", find_screenshot_time("Roger Federer", "Rafael Nadal", ss) == "")
check("prazan ulaz ne puca", find_screenshot_time("A", "B", {}) == "")

print("\n=== 9b. Mecevi iza ponoci (korisnik ih namjerno sprema pod 'danas') ===")
# 2026-08-04 je UTORAK. "sri 00:00" spremljen pod utorak = 05.08. 00:00 Zagreb.
u_sri = screenshot_start_utc("2026-08-04", "00:00", "sri")
check("'sri 00:00' pod utorkom -> 05.08., ne 04.08.",
      u_sri.startswith("2026-08-04T22:00"), u_sri)   # 00:00 Zagreb 05.08 = 22:00 UTC 04.08
lt_sri = local_match_time(u_sri, "montreal")
check("-> 18:00 ET u utorak (vecernja sesija)",
      lt_sri.get("local_time") == "18:00" and lt_sri.get("local_date") == "2026-08-04",
      f"{lt_sri.get('local_date')} {lt_sri.get('local_time')}")
check("bez kratice dana ostaje na datumu spremanja (staro ponasanje)",
      screenshot_start_utc("2026-08-04", "00:00").startswith("2026-08-03T22:00"))
check("'uto' pod utorkom ne pomice datum",
      screenshot_start_utc("2026-08-04", "17:00", "uto").startswith("2026-08-04T15:00"))
check("kratica s dijakritikom ('ČET') se prepoznaje",
      screenshot_start_utc("2026-08-04", "01:00", "ČET").startswith("2026-08-05T23:00"))
check("kratica predaleko unaprijed (>2 dana) se ODBIJA, ne nagadja",
      screenshot_start_utc("2026-08-04", "12:00", "sub") == "")
check("nepoznata kratica se ignorira, vrijeme ostaje",
      screenshot_start_utc("2026-08-04", "17:00", "xyz").startswith("2026-08-04T15:00"))

from agent.data_fetcher import _parse_day_abbr
check("_parse_day_abbr normalizira", _parse_day_abbr("ČET") == "cet" and _parse_day_abbr("sri") == "sri")
check("_parse_day_abbr odbija smece", _parse_day_abbr("abc") == "" and _parse_day_abbr(None) == "")

ss2 = {"2026-08-04": {"x|y": {"p1": "Nakashima Brandon", "p2": "Altmaier Daniel",
                              "p1_odds": 1.27, "p2_odds": 3.8,
                              "start_time": "00:00", "start_day": "sri"}}}
check("lookup prosljedjuje kraticu dana",
      find_screenshot_time("Brandon Nakashima", "Daniel Altmaier", ss2).startswith("2026-08-04T22:00"))

print("\n=== 10. Statistike meca u analizi gubitka ===")
from agent.feedback_analyzer import _format_match_stats as FMS, _ratio, WEIGHTS_AUTO_UPDATE_ENABLED

_S = {"player1Stats": {"player1Id": 111, "aces": 9, "doubleFaults": 6, "firstServe": 49,
                       "firstServeOf": 88, "winningOnFirstServe": 36, "winningOnFirstServeOf": 49,
                       "breakPointWonGm": 3, "breakPointChanceGm": 4, "totalPointsWon": 79},
      "player2Stats": {"player2Id": 222, "aces": 5, "doubleFaults": 2, "firstServe": 34,
                       "firstServeOf": 67, "winningOnFirstServe": 22, "winningOnFirstServeOf": 34,
                       "breakPointWonGm": 2, "breakPointChanceGm": 9, "totalPointsWon": 76}}

out = FMS("Atmane", "Draper", _S, 111, 222)
check("blok se generira (prije je BUG vracao prazno)", len(out) > 0)
check("camelCase polja se citaju", "Dvostruke greške" in out and "=6" in out)
check("racuna se postotak, ne samo broj", "49/88 (55.7%)" in out, out[:120])
check("Atmane je prvi kad ID-evi odgovaraju", out.index("Atmane") < out.index("Draper"))

# zamijenjen redoslijed: nasi ID-evi obrnuti -> mora zamijeniti statistike
sw = FMS("Draper", "Atmane", _S, 222, 111)
check("zamijenjen redoslijed se ISPRAVLJA po ID-u",
      "Draper=5" in sw and "Atmane=9" in sw, sw[:160])

check("ID-evi koji se ne poklapaju ni u jednom smjeru -> prazno",
      FMS("A", "B", _S, 999, 888) == "")
check("nasi ID-evi nepoznati, a statistika ih ima -> prazno (ne riskiramo zamjenu)",
      FMS("A", "B", _S) == "")
check("prazna statistika -> prazno", FMS("A", "B", {}) == "" and FMS("A", "B", None) == "")
check("_ratio racuna postotak", _ratio(35, 59) == "35/59 (59.3%)")
check("_ratio odbija dijeljenje s nulom", _ratio(3, 0) is None and _ratio(None, 5) is None)
check("polja koja su null se izostavljaju (nema 'N/A | N/A' redaka)", "Winneri" not in out)

# Brzine servisa: postoje samo POSLIJE meca i samo na ~38% turnira (mjeraci).
_S2 = {"player1Stats": dict(_S["player1Stats"], averageFirstServeSpeed=195,
                            averageSecondServeSpeed=152, fastestServe=211),
       "player2Stats": dict(_S["player2Stats"], averageFirstServeSpeed=178,
                            averageSecondServeSpeed=149, fastestServe=196)}
sp = FMS("A", "B", _S2, 111, 222)
check("brzina 1. servisa se prikazuje", "Prosj. brzina 1. servisa" in sp and "A=195" in sp)
check("brzina 2. servisa se prikazuje", "Prosj. brzina 2. servisa" in sp and "B=149" in sp)
check("najbrzi servis se prikazuje", "Najbrži servis" in sp and "A=211" in sp)
check("bez brzina se retci izostavljaju", "Prosj. brzina" not in out)

print("\n=== 10b. Zamrznuto azuriranje tezina ===")
check("WEIGHTS_AUTO_UPDATE_ENABLED je False (zamrznuto 05.08.)",
      WEIGHTS_AUTO_UPDATE_ENABLED is False)
from agent import feedback_analyzer as _fa
check("_maybe_update_weights odmah vraca False dok je zamrznuto",
      _fa._maybe_update_weights([{"x": 1}] * 20) is False)

print("\n=== 6. Hard pravilo 2 nosi ogradu o capu ===")
from agent.predictor import _surface_specific_rules
h = _surface_specific_rules("Hard")
check("64% označen kao CEILING", "This 64% is a CEILING, not a base" in h)
check("Landaluce dokumentiran", "Landaluce" in h)

print("\n=== 6b. Pravilo 12 usklađeno s kodom (0/3, ne 1/3) ===")
check("hard pravilo 12 trazi STROGO 0/3", "strictly 0/3 each" in h)
check("izricito kaze da 1/3 NE okida", "ONE-OF-THREE IS NOT ENOUGH" in h)
check("stara sira formulacija maknuta iz hard pravila 12",
      "BOTH players show 1/3 or worse" not in h)
check("mjerenje dokumentirano u pravilu", "ALL SIX WON" in h and "11W-1L" in h)

# Kod je izvor istine za prag — provjeri da se stvarno poklapaju.
from agent.run_daily import _is_declining
m = lambda res: [{"won": x, "finished": True} for x in res]
check("kod: 0/3 je declining", _is_declining(m([False, False, False])) is True)
check("kod: 1/3 NIJE declining", _is_declining(m([True, False, False])) is False)

# clay/grass namjerno ostaju siri — nemamo mjerenje za te podloge
c = _surface_specific_rules("Clay")
g = _surface_specific_rules("Grass")
check("clay namjerno NIJE diran (nema mjerenja)", "1/3 or worse" in c)
check("grass namjerno NIJE diran (nema mjerenja)", "1/3 or worse" in g)

print("\n=== 11. Runde: grupiranje, ljestvica, brojanje prije gatea (07.08.2026) ===")
from agent.run_daily import _infer_rounds, _count_by_tournament_day

def mk(t, d, rnd, p1, p2, level="ATP Masters 1000"):
    return {"tournament": t, "date": d, "round": rnd, "player1": p1, "player2": p2,
            "level": level}

# (a) mjesoviti dan: dvije runde istog dana ne smiju se stopiti u jednu oznaku
mixed = ([mk("T", "2026-08-06", "R32", f"A{i}", f"B{i}") for i in range(7)]
         + [mk("T", "2026-08-06", "QF", f"C{i}", f"D{i}") for i in range(4)])
_infer_rounds(mixed)
check("mjesoviti dan: R32 grupa ostaje R32",
      all(m["round"] == "R32" for m in mixed[:7]))
check("mjesoviti dan: QF grupa ostaje QF (4 meca je legitimno)",
      all(m["round"] == "QF" for m in mixed[7:]))

# stara verzija bi cijeli dan prepisala oznakom prvog meca — provjeri da vise ne
mixed2 = ([mk("T", "2026-08-06", "QF", f"C{i}", f"D{i}") for i in range(5)]
          + [mk("T", "2026-08-06", "R32", f"A{i}", f"B{i}") for i in range(7)])
_infer_rounds(mixed2)
check("nemoguc QF (5 meceva) se ispravlja", mixed2[0]["round"] != "QF")
check("...a susjedna R32 grupa ostaje netaknuta",
      all(m["round"] == "R32" for m in mixed2[5:]))

# (b) Masters ljestvica vise ne staje na R32
big = [mk("M", "2026-08-03", "R32", f"P{i}", f"Q{i}") for i in range(28)]
_infer_rounds(big)
check("Masters, 28 meceva -> R64 (prije: uvijek R32)", big[0]["round"] == "R64")
big32 = [mk("M", "2026-08-02", "R32", f"P{i}", f"Q{i}") for i in range(32)]
_infer_rounds(big32)
check("Masters, 32 meca -> R128", big32[0]["round"] == "R128")
mid = [mk("M", "2026-08-05", "R16", f"P{i}", f"Q{i}") for i in range(12)]
_infer_rounds(mid)
check("Masters, 12 meceva -> R32", mid[0]["round"] == "R32")
gs = [mk("G", "2026-07-01", "R64", f"P{i}", f"Q{i}", level="Grand Slam") for i in range(40)]
_infer_rounds(gs)
check("Grand Slam, 40 meceva -> R128", gs[0]["round"] == "R128")
small = [mk("S", "2026-07-19", "R16", f"P{i}", f"Q{i}", level="ATP 250") for i in range(16)]
_infer_rounds(small)
check("ATP 250, 16 meceva -> R32", small[0]["round"] == "R32")

# (c) broj mecheva dolazi iz pre-gate prebrojavanja, ne iz filtrirane liste
full = [mk("W", "2026-08-05", "R32", f"P{i}", f"Q{i}") for i in range(24)]
counts = _count_by_tournament_day(full)
check("_count_by_tournament_day broji po (turnir, dan, runda)",
      counts.get(("W", "2026-08-05", "R32")) == 24)
# kao da je screenshotano samo 6 od 24 — kopije, da prvi poziv ne zagadi drugi
gated = [dict(m) for m in full[:6]]
_infer_rounds(gated, None, counts)
check("gate ne smanjuje procjenu runde (6 vidljivih, 24 stvarnih -> R64)",
      gated[0]["round"] == "R64")
gated_naive = [dict(m) for m in full[:6]]
_infer_rounds(gated_naive)          # bez pre-gate brojeva
check("bez pre-gate brojeva ista lista daje drugu rundu (dokaz da (c) radi)",
      gated_naive[0]["round"] != "R64")

# RR i kvalifikacije se i dalje ne diraju
rr = [mk("F", "2026-11-12", "RR", f"P{i}", f"Q{i}") for i in range(6)]
_infer_rounds(rr)
check("round-robin ostaje netaknut", all(m["round"] == "RR" for m in rr))
q = [mk("Q", "2026-07-16", "Q2", f"P{i}", f"Q{i}", level="ATP 250") for i in range(9)]
_infer_rounds(q)
check("kvalifikacije bez screenshota ostaju Q2", all(m["round"] == "Q2" for m in q))

print("\n=== 12. Spajanje duplikata analiza (±3 dana) ===")
import inspect
from database import supabase_client as _db
check("find_existing_analysis postoji", hasattr(_db, "find_existing_analysis"))
_src = inspect.getsource(_db.save_analyzed_match)
check("save_analyzed_match trazi postojeci zapis prije upisa",
      "find_existing_analysis" in _src)
check("zadrzava postojeci external_match_id",
      'data["external_match_id"] = existing["external_match_id"]' in _src)
check("prozor je 3 dana",
      inspect.signature(_db.find_existing_analysis).parameters["window_days"].default == 3)
check("elo_cache_age_days postoji", hasattr(_db, "elo_cache_age_days"))
check("upsert_elo_cache izricito upisuje updated_at",
      '"updated_at": now' in inspect.getsource(_db.upsert_elo_cache))

print("\n=== 13. Break lopte + servis/povrat (07.08.2026) ===")
from agent import predictor as _pr
from agent import data_fetcher as _df

# (a) nazivi polja: kod mora traziti ono sto API stvarno vraca
_src = inspect.getsource(_df.get_player_stats)
check("trazi breakPointFacedGm (ne breakPointOf)", 'bps.get("breakPointFacedGm")' in _src)
check("trazi breakPointSavedGm", 'bps.get("breakPointSavedGm")' in _src)
check("trazi breakPointChanceGm", 'bpr.get("breakPointChanceGm")' in _src)
check("trazi breakPointWonGm", 'bpr.get("breakPointWonGm")' in _src)
check("stari krivi nazivi vise se ne koriste",
      'bps.get("breakPointOf")' not in _src and 'bpr.get("breakPoint")' not in _src)

# (b) ponderirani povrat mora biti NIZI od neponderiranog (1. servis nosi vise poena)
_o1of, _o1w, _o2of, _o2w = 30954, 21400, 19187, 9285      # stvarni Norrie brojevi
_r1 = (_o1of - _o1w) / _o1of * 100
_r2 = (_o2of - _o2w) / _o2of * 100
_unw = (_r1 + _r2) / 2
_wei = ((_o1of - _o1w) + (_o2of - _o2w)) / (_o1of + _o2of) * 100
check("ponderirani povrat je nizi od neponderiranog", _wei < _unw)
check("razlika je oko 2,4pp (Norrie)", 2.0 < (_unw - _wei) < 2.8,
      f"{_unw - _wei:.2f}")

# (c) 07.08. je BP bio zamrznut; UKLJUCEN 08.08.2026 11:35 nakon hard revizije
check("_BP_TO_PROMPT je True (ukljuceno 08.08.)", _pr._BP_TO_PROMPT is True)
_psrc = inspect.getsource(_pr.build_analysis_prompt) if hasattr(_pr, "build_analysis_prompt") else ""
_all = open("agent/predictor.py", encoding="utf-8").read()
check("prompt cita BP kroz zastavicu, ne izravno",
      'p1_bp_saved=p1.get("break_points_saved") if _BP_TO_PROMPT else None' in _all)
check("p2 isto", 'p2_bp_saved=p2.get("break_points_saved") if _BP_TO_PROMPT else None' in _all)

# (d) context_snapshot v8 nosi i ono sto prompt vidi i ispravljene vrijednosti
for f in ("p1_serve_pts_won", "p1_hold_pct", "p1_hold_pct_from_bp", "p1_return_won",
          "p1_return_won_weighted", "p1_bp_saved", "p1_bp_converted", "p1_first_serve_pct",
          "bp_in_prompt"):
    check(f"snapshot biljezi {f}", f'"{f}"' in _all)
check("context_version podignut na 17 (v15 22.08., v16 26.08., v17 27.08.)",
      '"context_version": 17' in _all)

# (e) nove vrijednosti ne smiju procuriti u prompt template
check("prompt template nema novih polja",
      "hold_pct_from_bp" not in _pr.ANALYSIS_PROMPT_TEMPLATE
      and "return_won_weighted" not in _pr.ANALYSIS_PROMPT_TEMPLATE)

print("\n=== 14. Otvorene stavke zapisane u kodu (07.08.2026) ===")
_tb = open("agent/ticket_builder.py", encoding="utf-8").read()
_mc = open("config/model_config.py", encoding="utf-8").read()
_dfsrc = open("agent/data_fetcher.py", encoding="utf-8").read()
check("prag selekcije 63% nosi nalaz uz sebe", "OTVORENO PITANJE ZA REVIZIJU" in _tb
      and "13W-4L" in _tb)
check("tezine nose ogradu o servisu i umoru", "fatigue_injuries" in _mc
      and "SUPROTNIM" in _mc and "+2,33pp" in _mc)
check("late-round pravilo nosi ogradu o krivim rundama",
      "OGRADA NA PRAVILO" in _all and "42,6%" in _all)
check("pristranost povrata zapisana uz izracun", "POZNATA PRISTRANOST" in _dfsrc)
check("ograda na hold proxy zapisana uz izracun", "OGRADA NA OVAJ PROXY" in _dfsrc)
check("krivi nazivi API polja dokumentirani", "breakPointOf" in _dfsrc)

# NAJVAZNIJE: ograda o late-round pravilu NE SMIJE biti unutar prompt templatea —
# rules_hash je md5 nad njim, a i model bi je citao kao uputu.
check("ograda je IZVAN prompt templatea (rules_hash netaknut)",
      "OGRADA NA PRAVILO" not in _pr.ANALYSIS_PROMPT_TEMPLATE)
import hashlib as _hl
_h = _hl.md5((_surface_specific_rules("Hard") + _pr.ANALYSIS_PROMPT_TEMPLATE)
             .encode("utf-8")).hexdigest()[:8]
# Ako ovo padne, prompt se PROMIJENIO. To je u redu kad je namjerno — tada osvjezi
# vrijednost ovdje i zabiljezi izmjenu u MODEL_CHANGELOG. Ako nije bilo namjerno, vrati je.
check("hard rules_hash je a0424315 (era od 22.08.2026)", _h == "a0424315", _h)

print("\n=== 15. Natpisi podloge u selekciji (07.08.2026) ===")
from agent import ticket_builder as _tbm
_mk = lambda s: {"match": {"surface": s}}
check("hard se zove 'hard' (prije: 'grass')", _tbm._surface_label(_mk("Hard")) == "hard")
check("indoor hard se zove 'hard'", _tbm._surface_label(_mk("Indoor Hard")) == "hard")
check("clay se zove 'clay'", _tbm._surface_label(_mk("Clay")) == "clay")
check("grass se zove 'grass'", _tbm._surface_label(_mk("Grass")) == "grass")
check("nepoznata podloga daje '?', ne pogadja", _tbm._surface_label(_mk("Carpet")) == "?")
_tbsrc = open("agent/ticket_builder.py", encoding="utf-8").read()
# stari natpisi smiju ostati SAMO u docstringu koji objasnjava popravak
_code = "\n".join(l for l in _tbsrc.splitlines()
                  if not l.strip().startswith("#") and "pisao \"Grass/clay" not in l
                  and "izbor bio je" not in l)
check("stari skupni natpis maknut iz koda", "Grass/clay disciplina" not in _code)
check("stari grass/clay ternar maknut iz koda",
      '"clay" if _is_clay(p) else "grass"' not in _code)
check("floor pokriva sve tri podloge",
      all(_tbm._needs_conf_floor(_mk(s)) for s in ("Hard", "Clay", "Grass")))

print("\n=== 16. Stavke na popisu za reviziju zapisane u kodu ===")
_rdsrc = open("agent/run_daily.py", encoding="utf-8").read()
_wf = open(".github/workflows/daily_ticket.yml", encoding="utf-8").read()
check("avg_opponent_elo nosi biljesku o pristranosti",
      "ZA REVIZIJU" in _rdsrc and "PREVISOK" in _rdsrc)
check("PYTHONUNBUFFERED je aktiviran 08.08. (07.08. je bila samo biljeska)",
      'PYTHONUNBUFFERED: "1"' in _wf)
check("timeout je 35 (popravljeno nakon prekida 02.08.)", "timeout-minutes: 35" in _wf)
check("timeout ostaje 35 (nije se diralo 08.08.)", "timeout-minutes: 35" in _wf)

print("\n=== 17. Revizija 08.08.2026: sto je ukljuceno, sto nije ===")
import hashlib as _h2
_prsrc = open("agent/predictor.py", encoding="utf-8").read()
_tb2 = open("agent/ticket_builder.py", encoding="utf-8").read()
_rd2 = open("agent/run_daily.py", encoding="utf-8").read()
_wf2 = open(".github/workflows/daily_ticket.yml", encoding="utf-8").read()

# A — bez utjecaja na pickove
check("ELO se biljezi u snapshot", '"p1_elo_overall"' in _prsrc and '"elo_gap_surface"' in _prsrc)
check("context_version podignut na 17", '"context_version": 17' in _prsrc)
check("broj protivnika u avg_opp_elo se biljezi", "_avg_opponent_elo_n" in _rd2)
check("PYTHONUNBUFFERED aktiviran", 'PYTHONUNBUFFERED: "1"' in _wf2)
check("hard okidac vise ne vristi na 30", "_HARD_NEXT_TRIGGER = 180" in _rd2)
# ELO NE smije uci u prompt (samo biljezenje)
check("ELO polja NISU u prompt templateu",
      "elo_gap_surface" not in _pr.ANALYSIS_PROMPT_TEMPLATE
      and "avg_opp_elo_n" not in _pr.ANALYSIS_PROMPT_TEMPLATE)

# B — mijenja pickove
check("break lopte idu u prompt", _pr._BP_TO_PROMPT is True)
check("zona opreza suzena na 1.43-1.60", _tbm._HARD_CAUTION_ZONE == (1.43, 1.60))
check("max 1 po tiketu ostaje", _tbm._HARD_CAUTION_ZONE_MAX == 1)
check("1.60-1.90 vise NIJE u zoni opreza",
      not (_tbm._HARD_CAUTION_ZONE[0] <= 1.75 <= _tbm._HARD_CAUTION_ZONE[1]))
check("1.50 je JOS UVIJEK u zoni opreza",
      _tbm._HARD_CAUTION_ZONE[0] <= 1.50 <= _tbm._HARD_CAUTION_ZONE[1])

# D — namjerno NEpromijenjeno
check("edge cap ostaje 28 (kocnica na uvjerenje, ne na kvotu)", _tbm._UNDERDOG_EDGE_CAP == 28.0)
check("underdog prag ostaje 2.00", _tbm._UNDERDOG_MIN_ODDS == 2.00)
check("prag selekcije ostaje 63", _tbm.TICKET_CONFIG["min_confidence"] == 63.0
      if hasattr(_tbm, "TICKET_CONFIG") else True)
check("granice tiketa nedirnute (4-6 parova, 6-40)",
      _mc.count('"min_matches": 4') == 1 and _mc.count('"max_matches": 6') == 1
      and '"min_combined_odds": 6.0' in _mc and '"max_combined_odds": 40.0' in _mc)
check("return_points_won JOS NIJE ispravljen u promptu", "POZNATA PRISTRANOST" in _dfsrc)

# zamka: rules_hash se NIJE promijenio, pa se era mora rezati po bp_in_prompt
_hh = _h2.md5((_surface_specific_rules("Hard") + _pr.ANALYSIS_PROMPT_TEMPLATE)
              .encode("utf-8")).hexdigest()[:8]
# Prompt JE mijenjan 13.08.2026 (strop 64 + trzisna provjera) -> hash se MORAO promijeniti.
# Ako ovo padne, prompt je diran: osvjezi vrijednost i zabiljezi izmjenu u MODEL_CHANGELOG.
check("hard rules_hash je a0424315 (era od 22.08.2026)", _hh == "a0424315", _hh)
check("zamka o rezanju ere dokumentirana", "ZAMKA ZA BUDUĆU ANALIZU" in _prsrc)
check("bp_in_prompt se biljezi kao oznaka ere", '"bp_in_prompt": _BP_TO_PROMPT' in _prsrc)

print("\n=== 18. Screenshot-iskljucivost po PARU (11.08.2026 18:44) ===")
import io as _io2, contextlib as _cl
from agent.run_daily import _gate_by_screenshot as _gate
_ss = {"Jodar Rafael|Fils Arthur":
       {"p1": "Jodar Rafael", "p2": "Fils Arthur", "p1_odds": 2.1, "p2_odds": 1.7},
       "Mensik Jakub|Shelton Ben":
       {"p1": "Mensik Jakub", "p2": "Shelton Ben", "p1_odds": 2.0, "p2_odds": 1.75}}
_mkm = lambda a, b, d, t: {"player1": a, "player2": b, "date": d, "tournament": t, "round": "R128"}
_pool_matches = [
    _mkm("Rafael Jodar", "Arthur Fils", "2026-08-11", "Montreal"),
    _mkm("Jakub Mensik", "Ben Shelton", "2026-08-12", "Montreal"),   # poslije ponoci
    _mkm("Billy Harris", "Kyrian Jacquet", "2026-08-11", "Cincinnati"),
    _mkm("Marcos Giron", "Henrique Rocha", "2026-08-12", "Cincinnati"),
]
def _rungate(a, b):
    _b = _io2.StringIO()
    with _cl.redirect_stdout(_b):
        return _gate([dict(x) for x in _pool_matches], a, b)

_k = _rungate(_ss, {})
_names = {x["player1"] for x in _k}
check("screenshot samo DANAS: par s API datumom SUTRA ipak prolazi (poslije ponoci)",
      "Jakub Mensik" in _names)
check("screenshot samo DANAS: nescreenshotani SUTRASNJI mec PADA (bug od 11.08.)",
      "Marcos Giron" not in _names)
check("screenshot samo DANAS: nescreenshotani DANASNJI mec pada",
      "Billy Harris" not in _names)
check("prolaze tocno screenshotani parovi", len(_k) == 2)
check("BEZ screenshota ne prolazi NISTA (prije: prolazilo sve)", _rungate({}, {}) == [])
check("screenshot samo SUTRA gata jednako", len(_rungate({}, _ss)) == 2)
# potpis vise ne prima datume — datum nije kriterij
import inspect as _i2
_par = list(_i2.signature(_gate).parameters)
check("potpis bez datumskih parametara",
      _par == ["matches", "screenshot_today", "screenshot_tomorrow"], str(_par))
check("rani izlaz kad nema nijednog meca", "zaustavljam prije analize" in _rd2 if "_rd2" in dir()
      else "zaustavljam prije analize" in open("agent/run_daily.py", encoding="utf-8").read())

print("\n=== 19. Kvalifikacije: R128 izvan Grand Slama ===")
_mkp = lambda lvl, rnd, ss=False: {"match": {"level": lvl, "round": rnd, "has_screenshot_odds": ss}}
check("Masters R128 pada (Cincinnati kvalifikacije 11.08.)",
      _tbm._is_main_tour(_mkp("ATP Masters 1000", "R128")) is False)
check("ATP 500 R128 i dalje pada", _tbm._is_main_tour(_mkp("ATP 500", "R128")) is False)
check("Grand Slam R128 PROLAZI (ondje je to prava prva runda)",
      _tbm._is_main_tour(_mkp("Grand Slam", "R128")) is True)
check("Masters R64 prolazi", _tbm._is_main_tour(_mkp("ATP Masters 1000", "R64")) is True)
check("QF nije kvalifikacija", _tbm._is_main_tour(_mkp("ATP 250", "QF")) is True)
check("Q2 pada", _tbm._is_main_tour(_mkp("ATP 250", "Q2")) is False)
check("screenshot override i dalje nadjacava round-tag",
      _tbm._is_main_tour(_mkp("ATP Masters 1000", "R128", ss=True)) is True)

print("\n=== 20. Strop pouzdanosti: 64% -> 70% (revizija 17.08.2026 11:46) ===")
# Strop je 13.08. postavljen na 64 jer je razred 65-67% davao 50,0% (n=20, ROI -34,8%).
# Revizija 17.08. izmjerila je nuspojavu: pouzdanost je postala konstanta (Brier 0,2308
# naspram 0,2305 za konstantu 0,64; 61% analiza na tocno 64), pa je selekcija oslijepila.
# Strop je podignut na 70; zahtjev za DEKLARACIJOM iznad stropa ostaje nepromijenjen.
from agent.predictor import _enforce_confidence_ceiling as _ceil, _market_line, _CONF_CEILING
_mk = lambda c, **kw: {**{"pick": "A", "confidence": c}, **kw}
_r = _mk(74); _ceil(_r)
check("74 bez obrazlozenja pada na 70", _r["confidence"] == 70.0)
check("clamp se biljezi", (_r.get("ceiling_enforced") or {}).get("from") == 74.0)
_r = _mk(67); _ceil(_r)
check("67 sada PROLAZI (13.08.-17.08. bilo srezano na 64)", _r["confidence"] == 67)
_r = _mk(70); _ceil(_r)
check("70 se ne dira", _r["confidence"] == 70 and _r.get("ceiling_enforced") is None)
_r = _mk(60); _ceil(_r)
check("ispod stropa se ne dira", _r["confidence"] == 60)
_ok = {"confirmations": ["hard ELO +180", "serve pts 68.4% vs 61.3%"],
       "what_would_beat_it": "ako servira ispod 60% prvog"}
_r = _mk(76, above_64_basis=_ok); _ceil(_r)
check("76 s DVIJE mjerene potvrde + downside prolazi", _r["confidence"] == 76)
_r = _mk(76, above_64_basis={"confirmations": ["serves well", "moves well"],
                             "what_would_beat_it": "x"}); _ceil(_r)
check("potvrde bez brojke ne vrijede", _r["confidence"] == 70.0)
_r = _mk(76, above_64_basis={"confirmations": ["hard ELO +180", "serve pts 68.4%"]}); _ceil(_r)
check("bez recenice o porazu ne prolazi", _r["confidence"] == 70.0)
_r = _mk(76, above_64_basis={"confirmations": ["hard ELO +180"],
                             "what_would_beat_it": "x"}); _ceil(_r)
check("jedna potvrda nije dovoljna", _r["confidence"] == 70.0)
_r = _mk(0, above_64_basis=None); _ceil(_r)
check("preskocen mec (conf 0) se ne dira", _r["confidence"] == 0)
check("strop je 70", _CONF_CEILING == 70.0)
# redoslijed: strop PRVI, pa capovi, pa mjerene kazne (17.08.2026 11:46)
_all2 = open("agent/predictor.py", encoding="utf-8").read()
check("mjerene kazne idu POSLIJE capova",
      _all2.index("_enforce_stated_caps(result)") < _all2.index("_apply_measured_penalties(result"))
check("strop se primjenjuje PRIJE capova",
      _all2.index("_enforce_confidence_ceiling(result)") < _all2.index("_enforce_stated_caps(result)"))

print("\n=== 21. Trzisna cijena kao PROVJERA, ne ulaz ===")
_ml = _market_line(1.28, 3.60, "Rublev", "Shang")
check("prikazuje impliciranu vjerojatnost, ne kvotu", "78%" in _ml and "1.28" not in _ml)
check("bez kvota vraca N/A", _market_line(0, 0, "A", "B") == "N/A")
check("prompt nosi Market check redak", "Market check (NOT an input" in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("prompt izricito kaze da NIJE ulaz",
      "must NOT enter your estimate" in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("prompt trazi obrazlozenje samo iznad 10pp",
      "differs by more than 10pp" in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("mjerenje 2W-6L zapisano u pravilu", "2W-6L" in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("stara zabrana oslanjanja na kvotu i dalje stoji",
      "independent of bookmaker odds" in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("nova polja u JSON shemi",
      '"above_64_basis"' in _pr.ANALYSIS_PROMPT_TEMPLATE
      and '"market_check"' in _pr.ANALYSIS_PROMPT_TEMPLATE)
check("context_version podignut na 17", '"context_version": 17' in _all2)

print("\n=== 22. Runde na razini TURNIRA (13.08.2026) ===")
from agent.run_daily import _verify_late_rounds, _LATE_ROUND_TOTAL
import io as _io3, contextlib as _cl3
def _vr(today, hist):
    _b = _io3.StringIO()
    with _cl3.redirect_stdout(_b):
        _verify_late_rounds(today, hist)
    return today
_mkr = lambda d, r, i: {"tournament": "T", "date": d, "round": r,
                        "player1": f"A{i}", "player2": f"B{i}"}
# Montreal obrazac: cetiri dana po dva "SF"
_t = [_mkr("2026-08-13", "SF", 1), _mkr("2026-08-13", "SF", 2)]
_h = [{"tournament": "T", "match_date": d, "round": "SF"}
      for d in ("2026-08-10", "2026-08-10", "2026-08-11", "2026-08-11",
                "2026-08-12", "2026-08-12")]
_vr(_t, _h)
check("dva SF od danas OSTAJU SF (najkasniji su pravi)",
      all(m["round"] == "SF" for m in _t))
_t2 = [_mkr("2026-08-12", "SF", 1), _mkr("2026-08-12", "SF", 2)]
_vr(_t2, _h + [{"tournament": "T", "match_date": "2026-08-13", "round": "SF"}] * 2)
check("raniji 'SF' se spusta u QF kad ih je previse",
      all(m["round"] == "QF" for m in _t2))
_t3 = [_mkr("2026-08-13", "SF", 1), _mkr("2026-08-13", "SF", 2)]
_vr(_t3, [])
check("bez povijesti se 2 SF ne diraju", all(m["round"] == "SF" for m in _t3))
_t4 = [_mkr("2026-08-13", "R32", i) for i in range(20)]
_vr(_t4, [])
check("rane runde se NE diraju (bez punog zdrijeba ne znamo)",
      all(m["round"] == "R32" for m in _t4))
check("ukupni brojevi samo za zavrsnice",
      set(_LATE_ROUND_TOTAL) == {"F", "SF", "QF"})
check("get_tournament_rounds postoji", hasattr(_db, "get_tournament_rounds"))

print("\n=== 25. Analysis-only write-up: sazetak ne smije okrenuti pick (29.08.2026) ===")
import agent.ticket_builder as _tb

# --- prepoznavanje imena ---
check("prvo ime se preskace (Arthur Fery vs Arthur Fils se ne spajaju)",
      _tb._name_tokens("Arthur Fery") == ["fery"]
      and _tb._name_tokens("Arthur Fils") == ["fils"])
check("jednorjecno prezime prezivi ('Wu')", _tb._name_tokens("Yibing Wu") == ["wu"])
check("crtica se cijepa (Auger-Aliassime)",
      set(_tb._name_tokens("Felix Auger Aliassime")) == {"auger", "aliassime"})
check("cestice ispadaju (Van De Zandschulp)",
      "van" not in _tb._name_tokens("Botic Van De Zandschulp")
      and "zandschulp" in _tb._name_tokens("Botic Van De Zandschulp"))
check("posvojni nastavak se skida, zadnje slovo NE ('Fils' != 'fil')",
      _tb._norm_word("Fils") == "fils" and _tb._norm_word("Borges's") == "borges")

_m = lambda p1, p2, pick, **kw: dict(
    {"player1": p1, "player2": p2, "pick": pick, "odds": 1.80, "confidence": 60.0,
     "risk_notes": "test risk", "key_factors": [], "tournament": "T", "surface": "Hard",
     "round": "R32"}, **kw)
_vukic = _m("Aleksandar Vukic", "Rei Sakamoto", "Aleksandar Vukic")
_wu = _m("Yibing Wu", "Adam Walton", "Yibing Wu")
check("protivnik se nalazi bez obzira na stranu",
      _tb._opponent_of(_vukic) == "Rei Sakamoto"
      and _tb._opponent_of(_m("Martin Landaluce", "Jacob Fearnley", "Jacob Fearnley"))
          == "Martin Landaluce")

# --- detekcija okretanja: cetiri STVARNA slucaja iz povijesti ---
check("lovi '**Sakamoto** over Vukic'",
      len(_tb._writeup_flips(
          "1. **Sakamoto** over Vukic \u2014 Sakamoto's 61% hard win rate beats Vukic's 46.9%.",
          [_vukic])) == 1)
check("lovi '**Walton** over Wu'",
      len(_tb._writeup_flips(
          "3. **Walton** over Wu \u2014 quality-adjusted form favours Walton.", [_wu])) == 1)
check("lovi '**Fucsovics to win** \u2014 despite ... Safiullin'",
      len(_tb._writeup_flips(
          "**Fucsovics to win** \u2014 despite market consensus favouring Safiullin, "
          "Fucsovics's title and freshness outweigh Safiullin's form edge.",
          [_m("Roman Safiullin", "Marton Fucsovics", "Roman Safiullin")])) == 1)
check("lovi vodeci podebljani '**Tarvet** \u2014 ... override Rinderknech'",
      len(_tb._writeup_flips(
          "**Tarvet** \u2014 69.2% grass record and 3/3 rhythm override Rinderknech's ELO.",
          [_m("Arthur Rinderknech", "Oliver Tarvet", "Arthur Rinderknech")])) == 1)

# --- NE smije prijaviti ispravne recenice (izmjereno: 8 laznih na prvoj heuristici) ---
check("ustupna uvodna recenica NIJE okretanje ('Despite Bellucci's ..., Baez's ...')",
      _tb._writeup_flips(
          "**Baez vs Bellucci:** Despite Bellucci's superior hold percentage, Baez's "
          "elite tiebreak record becomes the decisive edge.",
          [_m("Sebastian Baez", "Mattia Bellucci", "Sebastian Baez")]) == [])
check("zaglavlje 'X vs Y' se ne cita kao tvrdnja",
      _tb._writeup_flips(
          "**Zhang vs Brooksby:** Brooksby's collapse renders his ELO edge meaningless, "
          "with Zhang's trajectory pointing to an upset.",
          [_m("Zhizhen Zhang", "Jenson Brooksby", "Zhizhen Zhang")]) == [])
check("'Fils to beat Norrie' je ISPRAVNO (ime na koje se kladi je prvo)",
      _tb._writeup_flips(
          "**Fils to beat Norrie** \u2014 a 138-point ELO gap overrides Norrie's threat.",
          [_m("Arthur Fils", "Cameron Norrie", "Arthur Fils")]) == [])
check("'Borges over Darderi' je ISPRAVNO",
      _tb._writeup_flips(
          "**Borges over Darderi** \u2014 Borges's 23.8pp hard win-rate gap is decisive.",
          [_m("Nuno Borges", "Luciano Darderi", "Nuno Borges")]) == [])
check("'Auger-Aliassime over Tabilo' je ISPRAVNO (crtica)",
      _tb._writeup_flips(
          "**Auger-Aliassime over Tabilo:** a dominant +50 clay ELO gap makes FAA "
          "the clear favourite despite Tabilo's credentials.",
          [_m("Felix Auger Aliassime", "Alejandro Tabilo", "Felix Auger Aliassime")]) == [])
check("cist tekst bez tvrdnje se ne dira",
      _tb._writeup_flips("Vukic and Sakamoto both hold serve well.", [_vukic]) == [])

# --- kirurski popravak ---
_bad = ("No ticket today.\n"
        "1. **Sakamoto** over Vukic \u2014 his hard record is superior.\n"
        "2. **Faria** over Brooksby \u2014 clear surface edge.")
_flips = _tb._writeup_flips(_bad, [_vukic, _m("Jaime Faria", "Jenson Brooksby", "Jaime Faria")])
_fixed = _tb._repair_flips(_bad, [_vukic, _m("Jaime Faria", "Jenson Brooksby", "Jaime Faria")], _flips)
check("popravak uklanja okretanje", _tb._writeup_flips(
    _fixed, [_vukic, _m("Jaime Faria", "Jenson Brooksby", "Jaime Faria")]) == [])
check("popravak imenuje NAS pick", "Aleksandar Vukic" in _fixed)
check("popravak cuva numeraciju", "1. **Aleksandar Vukic**" in _fixed)
check("popravak NE dira ispravne recenice", "**Faria** over Brooksby" in _fixed)
check("popravak cuva uvodnu recenicu", _fixed.startswith("No ticket today."))

# --- rezanje ulaza ---
_kf = ["1. Rating: " + "x" * 900, "2. Serve: " + "y" * 900, "6. Own read: " + "z" * 900]
check("bira 'Own read' faktor", _tb._own_read(_m("A B", "C D", "A B", key_factors=_kf)).startswith("Own read"))
check("bez 'Own read' uzima zadnji", _tb._own_read(
    _m("A B", "C D", "A B", key_factors=["1. Rating: aaa", "2. Serve: bbb"])) == "Serve: bbb")
check("rez je ogranicen", len(_tb._own_read(_m("A B", "C D", "A B", key_factors=_kf))) <= 640)
check("bez faktora ne puca", _tb._own_read(_m("A B", "C D", "A B")) == "")

_big = [_m("Aleksandar Vukic", "Rei Sakamoto", "Aleksandar Vukic",
           key_factors=["%d. Faktor: %s" % (k, "q" * 900) for k in range(1, 7)])
        for _ in range(12)]
_pr_len = len(_tb._analysis_only_prompt(_big))
_kf_len = sum(len(", ".join(x["key_factors"])) for x in _big)
check("ulaz je bitno manji od zbroja key_factors (>60% usteda)",
      _pr_len < 0.4 * _kf_len, "%d vs %d" % (_pr_len, _kf_len))

# --- prompt je u nacinu IZVJESTAVANJA, ne odlucivanja ---
_p = _tb._analysis_only_prompt([_vukic])
check("prompt kaze da su odluke vec donesene", "ALREADY been made" in _p and "already decided" in _p)
check("prompt oznacava pick kao SELECTION", "SELECTION: Aleksandar Vukic" in _p)
check("prompt izricito zabranjuje imenovanje protivnika",
      "Never name the opponent as the winner" in _p)
check("prompt dopusta 'coin-flip' formulaciju bez mijenjanja imena", "coin-flip" in _p)
check("prompt cuva zabranu demonima (stari popravak zamjena imena)",
      "demonyms" in _p)
check("stari nacin ODLUCIVANJA je uklonjen",
      "if I had to bet" not in _p and "your pick" not in _p
      and "AVAILABLE MATCHES" not in _p)

# --- zamka: ovo je sloj prikaza, model se NE mijenja ---
check("write-up popravak NE dira rules_hash",
      _pr._model_stamp("hard")["rules_hash"] == "a0424315")

print("\n=== 26. Sluzbeni popis pickova + prag 50% (29.08.2026) ===")
from utils.helpers import is_no_selection, pick_ledger, MIN_PICK_CONFIDENCE
from utils import email_sender as _es
import io as _io26

check("prag je 50", MIN_PICK_CONFIDENCE == 50.0)
check("49% je no-selection", is_no_selection({"confidence": 49.0}) is True)
check("49.9% je no-selection", is_no_selection({"confidence": 49.9}) is True)
check("50% NIJE no-selection (granica ukljuciva)", is_no_selection({"confidence": 50.0}) is False)
check("65% NIJE no-selection", is_no_selection({"confidence": 65.0}) is False)
check("bez pouzdanosti se NE oznacava", is_no_selection({}) is False
      and is_no_selection({"confidence": None}) is False)
check("prazan ulaz ne puca", is_no_selection(None) is False)

_lm = [{"pick": "Yibing Wu", "player1": "Yibing Wu", "player2": "Adam Walton",
        "odds": 1.85, "confidence": 49.0, "value_bet": True},
       {"pick": "Cameron Norrie", "player1": "Luca Van Assche", "player2": "Cameron Norrie",
        "odds": 1.42, "confidence": 65.0, "value_bet": True}]
_led = pick_ledger(_lm)
check("ledger numerira od 1", [e["n"] for e in _led] == [1, 2])
check("ledger nosi pick iz baze, ne iz teksta",
      [e["pick"] for e in _led] == ["Yibing Wu", "Cameron Norrie"])
check("ledger oznacava samo pick ispod praga",
      [e["no_selection"] for e in _led] == [True, False])
check("prazna lista daje prazan ledger", pick_ledger([]) == [] and pick_ledger(None) == [])

# --- ticket_builder: pick ispod praga ne ulazi ni u hipotetski tiket ---
check("_conf_floor_ok odbija 49%", _tb._conf_floor_ok({"confidence": 49.0}) is False)
check("_conf_floor_ok prima 63%", _tb._conf_floor_ok({"confidence": 63.0}) is True)
check("_selection_ok koristi conf floor",
      "_conf_floor_ok(p)" in inspect.getsource(_tb._selection_ok))

# --- write-up prompt ---
_ns_m = {"pick": "Yibing Wu", "player1": "Yibing Wu", "player2": "Adam Walton",
         "odds": 1.85, "confidence": 49.0, "value_bet": True, "risk_notes": "converged serve",
         "key_factors": ["6. Own read: coin flip"], "tournament": "US Open",
         "surface": "Hard", "round": "R64"}
_ok_m = dict(_ns_m, pick="Cameron Norrie", player1="Luca Van Assche", player2="Cameron Norrie",
             confidence=65.0)
_p26 = _tb._analysis_only_prompt([_ns_m, _ok_m])
check("prompt oznacava unos ispod praga", "[NOT BACKED — below the 50% floor]" in _p26)
check("oznaka stoji SAMO na tom unosu", _p26.count("NOT BACKED — below") == 1)
check("VALUE se gasi na unosu ispod praga",
      _p26.split("2. SELECTION")[0].count("VALUE") == 0
      and "VALUE" in _p26.split("2. SELECTION")[1])
check("prompt objasnjava sto je [NOT BACKED]",
      "coin-flip against its own lean" in _p26
      and "Do not present it as a recommendation" in _p26)
check("prompt i dalje trazi da se imenuje NAS igrac",
      "Still name that player as the side the model leaned to" in _p26)
check("postotak nije dvostruko escapean", "50%%" not in _p26)

# --- rezervna deterministicka recenica ---
_dl_ns = _tb._deterministic_line(_ns_m)
check("rezervna recenica kaze da nije podrzano",
      "not backed" in _dl_ns and "below our 50% floor" in _dl_ns)
check("rezervna recenica i dalje imenuje NAS pick", _dl_ns.startswith("**Yibing Wu**"))
check("normalan pick ostaje 'over'", "over" in _tb._deterministic_line(_ok_m)
      and "not backed" not in _tb._deterministic_line(_ok_m))
check("provjera okretanja i dalje prolazi na rezervnoj recenici",
      _tb._writeup_flips(_dl_ns, [_ns_m]) == [])

# --- mail ---
_tk = {"ticket_date": "2026-08-29", "ticket_summary": "Test summary.", "status": "analysis_only"}
_html = _es._build_analysis_only_html(_tk, _lm)
check("mail nosi sluzbeni popis pickova", "Picks as recorded" in _html)
check("popis dolazi PRIJE teksta modela",
      _html.index("Picks as recorded") < _html.index("Test summary."))
check("mail oznacava NO SELECTION", "NO SELECTION" in _html)
check("mail gasi VALUE na picku ispod praga",
      _html[_html.index("<table"):].split("Cameron Norrie")[0].count("VALUE") == 0)
check("mail zadrzava VALUE na urednom picku", "VALUE" in _html)
_html2 = _es._build_ticket_html({"ticket_date": "2026-08-29", "total_odds": 5.0,
                                 "stake": 50, "potential_win": 250.0}, _lm)
check("i tiket-mail nosi popis pickova", "Picks as recorded" in _html2)

# --- Streamlit stranice ---
_dl_src = _io26.open(r"pages/1_Dnevni_Listic.py", encoding="utf-8").read()
_ar_src = _io26.open(r"pages/2_Arhiva.py", encoding="utf-8").read()
check("dnevni listic crta popis iz baze", "pick_ledger(matches)" in _dl_src
      and "source: database, not the text below" in _dl_src)
check("dnevni listic oznacava NO SELECTION", "NO SELECTION" in _dl_src)
check("dnevni listic gasi VALUE ispod praga",
      'm.get("value_bet") and not _no_sel' in _dl_src)
check("arhiva crta popis iz baze", "pick_ledger(matches)" in _ar_src)
check("arhiva oznacava NO SELECTION", "NO SELECTION" in _ar_src)

# --- zamka: predikcija se i dalje BILJEZI i BODUJE ---
check("nista ne brise pick iz ticket_matches",
      "no_selection" not in inspect.getsource(_tb.build_analysis_only_ticket))
check("prag NE dira rules_hash", _pr._model_stamp("hard")["rules_hash"] == "a0424315")

print("\n=== 27. Streamlit: zastarjeli utils.helpers u sys.modules (29.08.2026) ===")
import io as _io27
import utils.helpers as _real_h

_pages = {"pages/1_Dnevni_Listic.py": ["pick_ledger", "is_no_selection", "MIN_PICK_CONFIDENCE"],
          "pages/2_Arhiva.py": ["pick_ledger", "is_no_selection"]}
for _path, _names in _pages.items():
    _src27 = _io27.open(_path, encoding="utf-8").read()
    check("%s ima guard oko uvoza" % _path.split("/")[-1],
          "except ImportError:" in _src27 and "importlib.reload(_stale_helpers)" in _src27)

# Stvarna simulacija kvara: modul u memoriji nema nova imena.
_saved = {k: getattr(_real_h, k) for k in ("pick_ledger", "is_no_selection", "MIN_PICK_CONFIDENCE")}
for _k in _saved:
    delattr(_real_h, _k)
try:
    from utils.helpers import pick_ledger as _boom
    _raised = False
except ImportError:
    _raised = True
check("simulacija je stvarna (uvoz doista pukne)", _raised)

_src27 = _io27.open("pages/2_Arhiva.py", encoding="utf-8").read()
_a = _src27.index("try:\n    from utils.helpers import pick_ledger")
_b = _src27.index("import pandas as pd")
_ns27 = {}
_failed27 = None
try:
    exec(compile(_src27[_a:_b], "<guard>", "exec"), _ns27)
except Exception as _e27:
    _failed27 = _e27
check("guard se oporavlja bez restarta aplikacije",
      _failed27 is None and "pick_ledger" in _ns27 and "is_no_selection" in _ns27,
      str(_failed27))
check("reload je vratio imena i u sam modul",
      all(hasattr(_real_h, _k) for _k in _saved))
for _k, _v in _saved.items():          # sigurnosna mreza ako reload ne bi uspio
    if not hasattr(_real_h, _k):
        setattr(_real_h, _k, _v)
check("funkcije nakon oporavka i dalje rade",
      _ns27["is_no_selection"]({"confidence": 49.0}) is True
      and _ns27["is_no_selection"]({"confidence": 65.0}) is False)

print("\n=== 28. Post-match statistika: poravnanje po IGRACU (30.08.2026) ===")
from agent.data_fetcher import align_match_stats, _block_id, _stats_blocks
from agent.feedback_analyzer import _format_match_stats, _build_season_winner_lookup
import agent.feedback_analyzer as _fa
import copy as _copy

# Stvarni odgovor za Fery-Buse 29.08.2026: API je vratio BUSEA (79113) kao "player1Stats",
# iako je nas player1 Fery (79065). Ovo je uzorak koji mora ostati zauvijek testiran.
_RAW = {"player1Stats": {"player1Id": 79113, "aces": 2, "totalPointsWon": 57,
                         "breakPointWonGm": 4, "breakPointChanceGm": 7},
        "player2Stats": {"player2Id": 79065, "aces": 0, "totalPointsWon": 39,
                         "breakPointSavedGm": 3, "breakPointFacedGm": 7}}
FERY, BUSE = "79065", "79113"

_al, _why = align_match_stats(_RAW, FERY, BUSE)
check("prepoznaje zamijenjen redoslijed", _al is not None and _why == "zamijenjen redoslijed")
check("player1Stats postaje NAS player1 (Fery, 0 asova)",
      _al["player1Stats"]["aces"] == 0 and _al["player1Stats"]["totalPointsWon"] == 39)
check("player2Stats postaje NAS player2 (Buse, 2 asa)",
      _al["player2Stats"]["aces"] == 2 and _al["player2Stats"]["totalPointsWon"] == 57)
check("svaki blok nosi nedvosmislen our_player_id",
      _al["player1Stats"]["our_player_id"] == FERY
      and _al["player2Stats"]["our_player_id"] == BUSE)
check("_align nosi dokaz", _al["_align"]["verified"] is True
      and _al["_align"]["swapped"] is True
      and _al["_align"]["our_p1_id"] == FERY and _al["_align"]["api_p1_id"] == "79113")
check("izvorni dict se NE mijenja", _RAW["player1Stats"]["aces"] == 2
      and "our_player_id" not in _RAW["player1Stats"])

_al2, _why2 = align_match_stats(_RAW, BUSE, FERY)
check("obrnut par -> nema zamjene", _al2["_align"]["swapped"] is False
      and _al2["player1Stats"]["aces"] == 2)

# --- ODBIJANJA: nikad se ne pogadja ---
for _args, _frag in (((_RAW, "111", "222"), "ne poklapaju"),
                     ((_RAW, None, BUSE), "vlastite"),
                     ((_RAW, FERY, FERY), "ista"),
                     (({}, FERY, BUSE), "prazna"),
                     (({"player1Stats": {"aces": 1}, "player2Stats": {"aces": 2}}, FERY, BUSE),
                      "nema ID-eve")):
    _r, _w = align_match_stats(*_args)
    check("odbija: %s" % _frag, _r is None and _frag in _w, _w)

# jedan igrac se poklapa, drugi ne -> i dalje odbijeno (djelomicno poklapanje NIJE dokaz)
_r, _w = align_match_stats(_RAW, FERY, "99999")
check("djelomicno poklapanje ID-eva se odbija", _r is None)

# --- CITAC ---
_out = _format_match_stats("Arthur Fery", "Ignacio Buse", _al, FERY, BUSE)
check("citac pripisuje 0 asova Feryju, 2 Buseu",
      "Ace: Arthur Fery=0 | Ignacio Buse=2" in _out)
check("citac pripisuje ukupne poene tocno",
      "Ukupni poeni: Arthur Fery=39 | Ignacio Buse=57" in _out)
_out_legacy = _format_match_stats("Arthur Fery", "Ignacio Buse", _RAW, FERY, BUSE)
check("stari (sirovi) redci i dalje rade jednako", _out_legacy == _out)
check("_align za DRUGI par -> prazno, ne pogadja se",
      _format_match_stats("A", "B", _al, "111", "222") == "")
check("bez nasih ID-eva na sirovom retku -> prazno",
      _format_match_stats("A", "B", _RAW, None, None) == "")

# --- POVRATNI UPIS tournament_id-a ---
_saved = _fa.get_current_season_results
_fa.get_current_season_results = lambda tid: []
try:
    _rows = [{"tournament": "Winston-Salem Open - Winston-Salem", "match_date": "2026-08-28",
              "player1": "Ignacio Buse", "player2": "Benjamin Bonzi"},
             {"tournament": "Winston-Salem Open - Winston-Salem", "match_date": "2026-08-29",
              "player1": "Arthur Fery", "player2": "Ignacio Buse"}]
    # fixtures je imao SAMO prvi par (drugi je ispao iz feeda) — tocno slucaj od 29.08.
    _p2t = {("ignacio buse", "benjamin bonzi"): "21348",
            ("benjamin bonzi", "ignacio buse"): "21348"}
    _n_before = len(_p2t)
    _fa._build_season_winner_lookup(_rows, _p2t)
    check("tid je dopunjen za par kojeg fixtures nije imao",
          _p2t.get(("arthur fery", "ignacio buse")) == "21348")
    check("dopunjen je i obrnuti smjer",
          _p2t.get(("ignacio buse", "arthur fery")) == "21348")
    check("postojeci unosi se ne diraju",
          _p2t[("ignacio buse", "benjamin bonzi")] == "21348" and len(_p2t) > _n_before)
finally:
    _fa.get_current_season_results = _saved

# --- pisci koriste poravnati put ---
_fsrc = inspect.getsource(_fa.run_evening_update)
check("korak 2 (ticket_matches) koristi poravnati dohvat",
      "get_match_stats_aligned(tournament_id, p1_id, p2_id)" in _fsrc)
check("korak 2b (analyzed_matches) koristi poravnati dohvat",
      "get_match_stats_aligned(tid, p1_id, p2_id)" in _fsrc)
check("nijedan pisac ne zove sirovi get_match_stats",
      "= get_match_stats(" not in _fsrc)
_bsrc = _io26.open(r"scripts/backfill_match_stats.py", encoding="utf-8").read()
check("backfill skripta koristi poravnati dohvat",
      "get_match_stats_aligned(tid, p1_id, p2_id)" in _bsrc
      and "get_match_stats(" not in _bsrc.replace("get_match_stats_aligned(", ""))
check("backfill sprema ID-eve tek kad je poravnanje uspjelo",
      _bsrc.index("stat[\"upisano\"] += 1") < _bsrc.index("dopunjeni player ID-evi"))

check("backfill ima mod za poravnanje unatrag (bez API poziva)",
      "def realign(" in _bsrc and "align_match_stats(ms, p1_id, p2_id)" in _bsrc)
check("realign preskace retke bez dokazivog poravnanja",
      "preskoceno: " in _bsrc)
check("realign ne dira retke koji vec nose _align",
      '(ms.get("_align") or {}).get("verified")' in _bsrc)

check("realign upisuje ID-eve PRIJE statistike (polovican upis ostaje bezopasan)",
      _bsrc.index("REDOSLIJED JE NAMJERAN") < _bsrc.index('if save(r["id"], out):'))

print("\n=== 29. Revizija hard modela 30.08.2026: dvije kazne + Med-Low veto ===")
from agent.predictor import (_apply_measured_penalties, _CONF_BAND_LO, _CONF_BAND_HI,
                             _CONF_BAND_PENALTY, _TB_LEAD_PENALTY, _TB_LEAD_MIN_GAP_PP,
                             _TB_LEAD_MIN_SAMPLE)


def _pen(conf, tb_pick=(3, 3), tb_opp=(3, 3), scout="High", mp=0.70):
    r = {"pick": "Ana Anic", "confidence": conf}
    m = {"player1": "Ana Anic", "player2": "Bruno Bric", "market_p": mp}
    a = {"scouting": {"confidence": scout},
         "tiebreak_record": {"won": tb_pick[0], "lost": tb_pick[1]}}
    b = {"scouting": {"confidence": "High"},
         "tiebreak_record": {"won": tb_opp[0], "lost": tb_opp[1]}}
    _apply_measured_penalties(r, m, a, b)
    rules = [x["rule"] for x in (r.get("measured_penalties") or {}).get("applied", [])]
    return r["confidence"], rules


check("pragovi su 65/68 i kazna 5pp",
      (_CONF_BAND_LO, _CONF_BAND_HI, _CONF_BAND_PENALTY) == (65.0, 68.0, 5.0))
check("TB kazna 4pp, prag 10pp, min 3 tie-breaka",
      (_TB_LEAD_PENALTY, _TB_LEAD_MIN_GAP_PP, _TB_LEAD_MIN_SAMPLE) == (4.0, 10.0, 3))

# --- pojas 65-68 ---
c, rl = _pen(66)
check("66%% pada na 61%% (pojas 65-68)", c == 61.0 and "conf_band_65_68" in rl, str((c, rl)))
c, rl = _pen(65)
check("65%% je UNUTAR pojasa (donja granica ukljuciva)", c == 60.0, str((c, rl)))
c, rl = _pen(68)
check("68%% je IZVAN pojasa (gornja granica iskljuciva)", c == 68 and not rl, str((c, rl)))
c, rl = _pen(64)
check("64%% se ne dira", c == 64 and not rl, str((c, rl)))
c, rl = _pen(70)
check("70%% se ne dira", c == 70 and not rl, str((c, rl)))

# --- tie-break vodstvo ---
c, rl = _pen(64, tb_pick=(5, 1), tb_opp=(2, 4))
check("TB vodstvo 83%% vs 33%% -> BEZ kazne (uklonjeno 06.09.2026)",
      c == 64 and "tiebreak_lead" not in rl, str((c, rl)))
c, rl = _pen(64, tb_pick=(2, 0), tb_opp=(0, 3))
check("premali uzorak TB (2 meca) -> BEZ kazne", c == 64 and "tiebreak_lead" not in rl, str((c, rl)))
c, rl = _pen(64, tb_pick=(3, 3), tb_opp=(3, 3))
check("izjednacen TB -> bez kazne", c == 64 and not rl, str((c, rl)))
c, rl = _pen(64, tb_pick=(2, 4), tb_opp=(5, 1))
check("pick ZAOSTAJE u TB -> bez kazne (nalaz je jednosmjeran)",
      c == 64 and "tiebreak_lead" not in rl, str((c, rl)))
c, rl = _pen(64, tb_pick=(4, 3), tb_opp=(3, 3))
check("vodstvo 57%% vs 50%% (<10pp) -> bez kazne", c == 64, str((c, rl)))

# --- redoslijed: pojas se racuna NAKON ostalih kazni ---
c, rl = _pen(71, tb_pick=(5, 1), tb_opp=(2, 4))
check("71%% ostaje 71 (TB kazne vise nema, pojas se ne aktivira)",
      c == 71 and not rl, str((c, rl)))
c, rl = _pen(66, tb_pick=(5, 1), tb_opp=(2, 4))
check("66%% -> samo pojas(-5) -> 61 (TB vise ne sudjeluje)",
      c == 61.0 and rl == ["conf_band_65_68"], str((c, rl)))
c, rl = _pen(70, scout="Med-Low")
check("70%% -> Med-Low(-4) -> 66 -> pojas(-5) -> 61", c == 61.0 and len(rl) == 2, str((c, rl)))

# --- Med-Low veto u selekciji ---
check("_scouting_ok VISE NE odbija Med-Low (veto ukinut 06.09.2026)",
      _tb._scouting_ok({"measured_penalties": {"applied": [{"rule": "scouting_med_low"}]}}) is True)
check("_scouting_ok propusta ostale kazne",
      _tb._scouting_ok({"measured_penalties": {"applied": [{"rule": "market_underdog"}]}}) is True)
check("_scouting_ok propusta pick bez kazni", _tb._scouting_ok({}) is True)
check("_selection_ok koristi _scouting_ok",
      "_scouting_ok(p)" in inspect.getsource(_tb._selection_ok))
check("kazna -4pp OSTAJE u prediktoru (analiza treba brojku)",
      _pen(64, scout="Med-Low")[0] == 60.0)

# --- zamka: model se NIJE promijenio ---
check("revizija NE dira rules_hash", _pr._model_stamp("hard")["rules_hash"] == "a0424315")
check("ANALYSIS_PROMPT_TEMPLATE ne spominje nove kazne",
      "conf_band_65_68" not in _pr.ANALYSIS_PROMPT_TEMPLATE
      and "tiebreak_lead" not in _pr.ANALYSIS_PROMPT_TEMPLATE)

print()
print("=== 30. Fery veto UKINUT iz selekcije (30.08.2026 12:37) ===")
from agent import run_daily as _rd


def _cand(beat_p1=False, beat_p2=False, pick="Ana Anic", conf=70.0):
    """Kandidat koji prolazi sve ostale filtre — mijenja se samo Fery zastavica."""
    return {"pick": pick, "confidence": conf,
            "match": {"player1": "Ana Anic", "player2": "Bruno Bric",
                      "level": "ATP 250", "surface": "Hard", "round": "R32",
                      "odds_available": True, "has_screenshot_odds": True,
                      "p1_beat_us": beat_p1, "p2_beat_us": beat_p2}}


# --- zastavica se i dalje CITA ispravno (funkcija nije pokvarena) ---
check("_opponent_beat_us prepoznaje zastavicu na protivniku",
      _tb._opponent_beat_us(_cand(beat_p2=True)) is True)
check("_opponent_beat_us ne reagira na zastavicu na NASEM picku",
      _tb._opponent_beat_us(_cand(beat_p1=True)) is False)
check("_opponent_beat_us bez zastavica je False",
      _tb._opponent_beat_us(_cand()) is False)
check("_opponent_beat_us radi i kad je nas pick player2",
      _tb._opponent_beat_us(_cand(beat_p1=True, pick="Bruno Bric")) is True)

# --- ali selekcija je vise NE koristi ---
_sel_src = chr(10).join(l for l in inspect.getsource(_tb._selection_ok).splitlines()
                        if not l.strip().startswith("#"))
check("_selection_ok NE zove _opponent_beat_us (izvan komentara)",
      "_opponent_beat_us" not in _sel_src)
check("kandidat s Fery zastavicom sada PROLAZI selekciju",
      _tb._selection_ok(_cand(beat_p2=True)) is True)
check("kontrola: isti kandidat bez zastavice prolazi",
      _tb._selection_ok(_cand()) is True)
check("zastavica ne mijenja ishod selekcije ni u jednom smjeru",
      _tb._selection_ok(_cand(beat_p2=True)) == _tb._selection_ok(_cand()))

# --- ostali filtri i dalje rezu (nismo slucajno otvorili vrata) ---
check("Med-Low pick sada PROLAZI selekciju (veto ukinut 06.09.2026)",
      _tb._selection_ok(dict(_cand(),
                             measured_penalties={"applied": [{"rule": "scouting_med_low"}]})) is True)
check("prag pouzdanosti i dalje reze", _tb._selection_ok(_cand(conf=40.0)) is False)
check("Challenger i dalje reze",
      _tb._selection_ok({"pick": "Ana Anic", "confidence": 70.0,
                         "match": {"player1": "Ana Anic", "player2": "Bruno Bric",
                                   "level": "ATP Challenger", "surface": "Hard",
                                   "odds_available": True}}) is False)
check("mec bez kvote i dalje reze",
      _tb._selection_ok({"pick": "Ana Anic", "confidence": 70.0,
                         "match": {"player1": "Ana Anic", "player2": "Bruno Bric",
                                   "level": "ATP 250", "surface": "Hard",
                                   "odds_available": False}}) is False)

# --- mjerenje je zapisano u kodu, ne samo u changelogu ---
_src_tb = inspect.getsource(_tb._opponent_beat_us)
check("docstring nosi datum I vrijeme izmjene", "30.08.2026 12:37" in _src_tb)
check("docstring nosi obje izmjerene skupine",
      "93,3%" in _src_tb and "56,8%" in _src_tb)
check("docstring nosi kontrolu cijene i runde",
      "-2,8pp" in _src_tb and "-14,7pp" in _src_tb)
check("docstring nosi uvjet za povratak veta", "veto se vraća" in _src_tb)
check("run_daily vise ne tvrdi da pick nece uci na tiket",
      "neće ući na tiket" not in inspect.getsource(_rd))
check("run_daily i dalje racuna zastavice (potrebne za premjeravanje)",
      'match["p1_beat_us"]' in inspect.getsource(_rd))

print()
print("=== 31. Predlozak prompta: bez manjka i bez viska (31.08.2026 18:31) ===")
import ast as _ast
from string import Formatter as _Fmt

_src = io.open(inspect.getsourcefile(_pr), encoding="utf-8").read()
_Q3 = chr(34) * 3
_tpl = _src.split("ANALYSIS_PROMPT_TEMPLATE = " + _Q3, 1)[1].split(_Q3)[0]
_ph = {f for _, f, _, _ in _Fmt().parse(_tpl) if f}
_kw = None
for _node in _ast.walk(_ast.parse(_src)):
    if (isinstance(_node, _ast.Call) and isinstance(_node.func, _ast.Attribute)
            and _node.func.attr == "format"
            and isinstance(_node.func.value, _ast.Name)
            and _node.func.value.id == "ANALYSIS_PROMPT_TEMPLATE"):
        _kw = {a.arg for a in _node.keywords if a.arg}

check("poziv .format() na predlosku je pronadjen", _kw is not None)
check("predlozak ima ocekivani broj polja (100)", len(_ph) == 100, "nadjeno %d" % len(_ph))
check("NIJEDAN placeholder nije bez argumenta (inace KeyError u produkciji)",
      not (_ph - _kw), "manjka: %s" % sorted(_ph - _kw))
check("NIJEDAN argument nije bez placeholdera (mrtva varijabla)",
      not (_kw - _ph), "visak: %s" % sorted(_kw - _ph))
check("p1_last_match / p2_last_match vise se ne prosljedjuju",
      "p1_last_match" not in _kw and "p2_last_match" not in _kw)
check("podatak last_match_date nije izbrisan iz koda", "last_match_date" in _src)

_zone_src = inspect.getsource(_tb._hard_caution_zone_count)
# Docstring NAMJERNO jos spominje 1,43-1,90 — ali kao opis nedosljednosti s promptom,
# ne kao tvrdnju o vlastitom rasponu. Provjerava se da je stara TVRDNJA nestala.
check("stara tvrdnja 'oprezna zona 1.43-1.90' je uklonjena",
      "oprezna zona 1.43-1.90" not in _zone_src)
check("spominjanje 1,43-1,90 stoji samo uz prompt-nedosljednost",
      ("1.43-1.90" not in _zone_src) or ("pravilo 3 u promptu" in _zone_src))
check("opis oprezne zone navodi stvarni raspon 1,43-1,60", "1,43-1,60" in _zone_src)
check("konstanta oprezne zone je i dalje (1.43, 1.60)",
      _tb._HARD_CAUTION_ZONE == (1.43, 1.60))
check("opis biljezi otvorenu nedosljednost s promptom",
      "OTVORENA NEDOSLJEDNOST" in _zone_src)
check("rules_hash netaknut ovim izmjenama",
      _pr._model_stamp("hard")["rules_hash"] == "a0424315")

print()
print("=== 32. Revizija 06.09.2026: uklonjeno ono sto nije repliciralo ===")

# --- kazna za TB vodstvo je UKLONJENA, ali alat i konstante ostaju ---
check("TB kazna se ne primjenjuje ni pri ekstremnom vodstvu",
      _pen(64, tb_pick=(8, 0), tb_opp=(0, 8))[0] == 64)
check("`tiebreak_lead` se vise ne pojavljuje u primijenjenim kaznama",
      "tiebreak_lead" not in _pen(64, tb_pick=(8, 0), tb_opp=(0, 8))[1])
check("razlog uklanjanja je zapisan u kodu",
      "pala je izvan uzorka" in inspect.getsource(_pr._apply_measured_penalties))
check("zapisane su obje brojke (stara i nova)",
      "-7,2pp" in inspect.getsource(_pr._apply_measured_penalties)
      and "+7,9pp" in inspect.getsource(_pr._apply_measured_penalties))

# --- pojas 65-68 OSTAJE (replicirao se na cijelom korpusu) ---
check("pojas 65-68 i dalje kaznjava", _pen(66)[0] == 61.0)
check("pojas 65-68 i dalje daje ispravno ime pravila", "conf_band_65_68" in _pen(66)[1])

# --- trzisni autsajder OSTAJE (jedini nalaz s istim predznakom u obje ere) ---
# 75 -> 70 (kazna -5pp), a 70 NIJE u pojasu 65-68 pa se pojas ne aktivira
_r = {"pick": "Ana Anic", "confidence": 75.0}
_pr._apply_measured_penalties(_r, {"player1": "Ana Anic", "player2": "Bruno Bric",
                                   "market_p": 0.40}, {}, {})
check("kazna za trzisnog autsajdera OSTAJE (-5pp)", _r["confidence"] == 70.0, str(_r))
# 70 -> 65 (kazna) -> 65 JE u pojasu -> jos -5 -> 60; kazne se i dalje zbrajaju
_r2 = {"pick": "Ana Anic", "confidence": 70.0}
_pr._apply_measured_penalties(_r2, {"player1": "Ana Anic", "player2": "Bruno Bric",
                                    "market_p": 0.40}, {}, {})
check("autsajder + pojas se zbrajaju (70 -> 65 -> 60)",
      _r2["confidence"] == 60.0
      and [a["rule"] for a in _r2["measured_penalties"]["applied"]] == ["market_underdog",
                                                                        "conf_band_65_68"],
      str(_r2))

# --- Med-Low: veto pao, kazna ostala ---
check("Med-Low kazna -4pp OSTAJE u prediktoru", _pen(64, scout="Med-Low")[0] == 60.0)
check("_scouting_ok je sada bezuvjetno True", _tb._scouting_ok({}) is True
      and _tb._scouting_ok({"measured_penalties": {"applied": [{"rule": "scouting_med_low"}]}}) is True)
check("razlog ukidanja veta zapisan, s pragom za povratak",
      "PRAG ZA PONOVNO UVODJENJE VETA" in inspect.getsource(_tb._scouting_ok))

# --- GS prag OSTAJE na 65 (moja preporuka za 63 je povucena) ---
check("hard GS prag je i dalje 65", _tb._HARD_GS_MIN_CONF == 65.0)
check("obrazlozenje GS praga sadrzi izmjereni pojas 63-65",
      "-10,3pp" in inspect.getsource(_tb._hard_gs_conf_ok))

# --- analiza gubitaka: kontrolna skupina + omjer winneri/greske ---
_fa_src = inspect.getsource(_fa)
check("bazne stope sadrze kontrolnu tablicu pobjeda/poraza",
      "THE CONTROL TABLE" in _fa_src)
check("bazne stope imenuju varijable koje NE razdvajaju", "IDENTICAL" in _fa_src)
check("bazne stope nose upozorenje o replikaciji",
      "REPLICATION WARNING" in _fa_src and "0 of 3" in _fa_src)
check("omjer winneri/greske je u statistici meca", "_wue(" in _fa_src)
_st = {"player1Stats": {"winners": 55, "unforcedErrors": 59, "our_player_id": 1},
       "player2Stats": {"winners": 41, "unforcedErrors": 54, "our_player_id": 2},
       "_align": {"verified": True, "our_p1_id": "1", "our_p2_id": "2"}}
_out = _fa._format_match_stats("Ana Anic", "Bruno Bric", _st, "1", "2")
check("omjer se stvarno ispisuje", "0.93" in _out and "0.76" in _out, _out[:120])

check("rules_hash i dalje netaknut", _pr._model_stamp("hard")["rules_hash"] == "a0424315")

print()
print("=== 33. Registar kandidata + bazne stope o cijeni i kvotama (06.09.2026 10:55) ===")

_di = io.open(r"c:/Users/jovin/Desktop/Tenis Claude/DECISION_INPUTS.md", encoding="utf-8").read()
for _k in ("### K1 ", "### K2 ", "### K3 ", "### K4 ", "### K5 ", "### K6 ", "### K7 "):
    check("registar sadrzi kandidata %s" % _k.strip(" #"), _k in _di)
check("svaki kandidat ima zapisan prag",
      _di.count("PRAG") >= 6, "nadjeno %d" % _di.count("PRAG"))
check("K5 nosi izmjereni pojas 1,35-1,43", "1,35-1,43" in _di)
check("K6 nosi ogradu o monotonosti", "nije monotona" in _di or "monotonos" in _di)
check("odbaceno kretanje kvota je zapisano s brojkom", "+0,007" in _di)
check("odbacene su i kratke kvote kao 'problem'", "varijanca" in _di)

_b = _fa._LOSS_BASE_RATES
check("bazne stope sadrze strukturu pojasa cijene", "PRICE BAND STRUCTURE" in _b)
check("bazne stope imenuju rupu 1,35-1,60",
      "1.35-1.43" in _b and "1.43-1.60" in _b)
check("bazne stope kazu da kratke kvote nisu obrazac", "VARIANCE" in _b)
check("bazne stope zabranjuju objasnjenje 'trziste se pomaknulo'",
      "ODDS MOVEMENT CARRIES NOTHING" in _b and "P=0.927" in _b)
check("bazne stope i dalje nose kontrolnu tablicu", "THE CONTROL TABLE" in _b)
check("bazne stope nisu narasle preko razumnog (prompt budzet)",
      len(_b) < 12000, "%d znakova" % len(_b))

check("rules_hash i dalje netaknut", _pr._model_stamp("hard")["rules_hash"] == "a0424315")

print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVI TESTOVI PROŠLI")
