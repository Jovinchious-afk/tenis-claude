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

print("\n=== 6. Hard pravilo 2 nosi ogradu o capu ===")
from agent.predictor import _surface_specific_rules
h = _surface_specific_rules("Hard")
check("64% označen kao CEILING", "This 64% is a CEILING, not a base" in h)
check("Landaluce dokumentiran", "Landaluce" in h)

print("\n" + "=" * 60)
if _fails:
    print(f"PALO: {len(_fails)}")
    for f in _fails:
        print(f"  - {f}")
    sys.exit(1)
print("SVI TESTOVI PROŠLI")
