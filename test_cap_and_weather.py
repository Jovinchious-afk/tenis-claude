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

print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVI TESTOVI PROŠLI")
