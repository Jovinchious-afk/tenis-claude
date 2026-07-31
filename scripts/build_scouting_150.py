# -*- coding: utf-8 -*-
"""Proširenje scouting tablice na ATP top 150 (31.07.2026).

NAČELO: ništa se ne izmišlja. Svaki profil je izveden iz MJERENIH podataka koje već
imamo (surface W-L zadnje 3 godine, hold%, return points won, ace rate, surface ELO), a
kvalitativni opis stila dodan je samo za igrače za koje je nađen provjeren izvor
(ATP Tour bio, Wikipedia, LTA). Gdje podatka nema, profil to izrijekom kaže
("cannot be determined") umjesto da popuni prazninu nagađanjem.

Confidence se dodjeljuje po KOLIČINI dokaza, ne po dojmu:
  Med       = mjereni podaci (>=40 mečeva) + potvrđen vanjski opis stila
  Med-Low   = samo mjereni podaci, dovoljan uzorak
  Low       = mali uzorak ILI nedostaje pravi ELO (fallback 1500) — prompt ga ionako filtrira

Pokretanje:  python scripts/build_scouting_150.py [--dry-run]
"""
import sys
import os
import io
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase_client as db
from agent import data_fetcher as df
from agent.data_fetcher import _norm_key

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "scouting_top150_source.json")

# Kvalitativni opisi iz PROVJERENIH vanjskih izvora (ATP Tour bio, Wikipedia, LTA).
# Samo igrači za koje je izvor stvarno pronađen — ostali ostaju bez ovog sloja.
_WEB = {
    "toby samuel": {
        "hand": "Right-handed, two-handed backhand; 1.91 m",
        "note": "British, b.2002. Career-high #159 (May 2026); first ATP semi-final "
                "Eastbourne 2026. Source: Wikipedia/LTA.",
    },
    "dane sweeny": {
        "hand": "Right-handed, two-handed backhand; 1.70 m",
        "note": "Australian. Compact, quick baseliner — court speed complements aggressive "
                "baseline play. Small stature limits serve leverage. Source: Wikipedia/Tennis Australia.",
    },
    "michael zheng": {
        "hand": "Right-handed, two-handed backhand",
        "note": "American, b.2004, two-time NCAA champion (Columbia). Well-rounded, "
                "baseline-oriented with strong defence and methodical point construction. "
                "Beat Norrie at Wimbledon 2026. Source: ATP Tour feature.",
    },
    "nicolai budkov kjaer": {
        "hand": "Right-handed, two-handed backhand",
        "note": "Norwegian. Self-described 'aggressive, bold, sometimes weird'; favourite "
                "shot is the serve, favourite surface grass. Source: ATP Tour bio.",
    },
    "chak lam coleman wong": {
        "hand": "Right-handed, two-handed backhand; 1.91 m",
        "note": "Hong Kong's highest-ranked man ever. 2026: ~10 aces/match — serve is the "
                "weapon. BEAT OUR PICKS 3x in Los Cabos week (Lehecka, Brooksby, Blanch). "
                "Source: ATP Tour bio + our own match records.",
    },
    "arthur gea": {
        "hand": "Right-handed",
        "note": "French, b.2004. Own words: 'big serve and big forehand, and also good "
                "defence'; moves opponents side to side, favourite surface hard. Upset "
                "Lehecka at AO 2026; BEAT OUR PICK Cerundolo in Los Cabos. Source: ATP Tour bio.",
    },
    "eliot spizzirri": {
        "hand": "Right-handed, two-handed backhand",
        "note": "American (Texas). Career-high #67 (Feb 2026), AO 3rd round 2026. "
                "Source: ATP Tour bio.",
    },
    "jacob fearnley": {
        "hand": "Right-handed",
        "note": "Scottish. Grass is his strongest surface — big serve plus aggressive "
                "baseline game. Beat Djokovic at Wimbledon 2025. Source: ATP/LiveTennis.",
    },
}


# ── Ispravci POSTOJEĆIH profila koje su naši vlastiti mečevi opovrgnuli ──────────
# Sva tri su bila "Med-Low / partial data", prošla su gate (prag je Med-Low) i sva tri
# su sudjelovala u gubicima. Ispravci su izvedeni iz NAŠIH zabilježenih rezultata, ne
# iz dojma — svaki nosi konkretan meč kao dokaz.
_CORRECTIONS = {
    "luca van assche": {
        "rank": 48,
        "style": "Clay-first all-court baseliner (level jumped mid-2026)",
        "best_surfaces": "Clay (title Estoril 2026), Hard",
        "strengths": "Clean groundstrokes; movement; absorbs and redirects pace; "
                     "proven ability to beat elite ball-strikers",
        "weaknesses": "Modest serve; needs long rallies to build advantage",
        "favourable_matchups": "Big hitters who over-press — he absorbs pace and waits "
                               "for the error (beat Rublev from a set down)",
        "tough_matchups": "Elite servers who deny him rally length on fast courts",
        "confidence": "Med",
        "note": "CORRECTED 2026-07-31 from our own match records. The previous profile "
                "('needs a weapon, tough vs big power + servers', Med-Low, partial data) "
                "was contradicted by results: he won Estoril 2026 beating Rublev 3-6 6-3 6-4, "
                "Carreno-Busta, Gaston and Blockx — five straight clay wins. Ranking moved "
                "#78 -> #48. Treat him as a genuine top-50 clay threat, not a prospect.",
    },
    "quentin halys": {
        "rank": 52,
        "style": "Big-serving baseliner — effective on FAST clay too, not only hard",
        "best_surfaces": "Hard, Grass, Indoor, and fast/high-altitude clay",
        "strengths": "Serve; forehand; on quick surfaces the serve is close to unbreakable",
        "weaknesses": "Return; movement; slow high-bouncing clay still blunts him",
        "favourable_matchups": "Grinders and clay movers on FAST courts — his serve removes "
                               "their break chances (beat Navone, an elite clay mover, 7-5 6-3)",
        "tough_matchups": "Elite returners on slow surfaces where rallies get long",
        "confidence": "Med",
        "note": "CORRECTED 2026-07-31 from our own match records. The previous profile listed "
                "only 'Hard, Grass, Indoor' and 'tough vs elite returners/movers' — both were "
                "contradicted at Kitzbuhel (fast clay), where he beat THREE of our picks in one "
                "week: Navone 7-5 6-3, Hanfmann 6-4 7-6(2), Bublik 6-4 7-6(6), taking the title. "
                "Ranking moved #83 -> #52. See hard rule 13 (serve-dominant opponent).",
    },
    "kamil majchrzak": {
        "confidence": "Med",
        "note": "UPDATED 2026-07-31. Beat our pick Tommy Paul 7-5 7-6(4) at Washington 2026 "
                "in a match where both players held ~81% — the converged-serve pattern now "
                "covered by hard rule 16. Profile was 'Med-Low, partial data' before.",
    },
}


def _style_from_stats(hold, ret, ace):
    """Stil izveden iz brojki — objektivno, bez nagađanja."""
    if hold is None or ret is None:
        return None, None, None
    ace = ace or 0
    # Pragovi kalibrirani na stvarnom rasponu ovog korpusa (hold 67-93%, return 32-47%),
    # ne na apstraktnim brojkama — inace bi gotovo svi ispali "all-court".
    if hold >= 86 or (hold >= 83 and ace >= 10):
        return ("Big server / first-strike",
                "Elite hold rate; free points on serve; short points",
                "Return game is the weak link; struggles to break back; long rallies")
    if (hold >= 82 and ace >= 7) or ace >= 9.5:
        return ("Serve-led aggressive baseliner",
                "Strong serve plus first-strike power off the ground",
                "Vulnerable when the serve is neutralised; modest return")
    if ret >= 44.5:
        return ("Elite returner / counter-puncher",
                "Outstanding return; breaks serve regularly; extends rallies",
                "Low hold rate; few free points; must earn every game")
    if hold < 78 and ret >= 42.5:
        return ("Defensive baseliner / grinder",
                "Return and rally tolerance; movement; wins on attrition",
                "Serve is a liability; no put-away weapon; long matches")
    if hold >= 81 and ret >= 41:
        return ("Balanced all-court baseliner",
                "Holds reliably and returns competently — no obvious hole",
                "No single dominant weapon to force the issue")
    if hold >= 80:
        return ("Solid-serving baseliner",
                "Reliable hold; steady from the back",
                "Return is the weaker half; needs the serve to carry him")
    return ("All-court baseliner (no clear specialisation)",
            "Balanced but unremarkable serve/return profile",
            "Neither serve nor return stands out — exposed against a clear specialist")


def _surfaces(sf):
    """Najbolje/najslabije podloge iz stvarnog W-L (min 12 mečeva za tvrdnju)."""
    ranked = []
    for key, label in (("hard", "Hard"), ("clay", "Clay"), ("grass", "Grass"),
                       ("indoor_hard", "Indoor")):
        d = (sf or {}).get(key) or {}
        n = d.get("matches") or 0
        if n >= 12 and d.get("win_pct") is not None:
            ranked.append((label, d["win_pct"], n))
    ranked.sort(key=lambda x: -x[1])
    best = [r for r in ranked if r[1] >= 55]
    worst = [r for r in ranked if r[1] < 45]
    return ranked, best, worst


def build(rec):
    name = rec["name"]
    k = _norm_key(name)
    st = rec.get("stats") or {}
    sf = rec.get("surface") or {}
    elo = rec.get("elo") or {}
    hold, ret, ace = st.get("hold_pct"), st.get("return_points_won"), st.get("aces_per_game")
    style, strengths, weaknesses = _style_from_stats(hold, ret, ace)
    ranked, best, worst = _surfaces(sf)
    total_matches = sum((sf.get(x) or {}).get("matches") or 0
                        for x in ("hard", "clay", "grass", "indoor_hard"))
    elo_missing = (elo.get("elo_overall") in (None, 1500)) and (elo.get("elo_hard") in (None, 1500))
    web = _WEB.get(k)

    if style is None:
        style = "Cannot be determined — serve/return statistics unavailable"
        strengths = "Cannot be determined from available data"
        weaknesses = "Cannot be determined from available data"

    best_str = ", ".join(f"{l} ({p:.0f}%, n={n})" for l, p, n in best) or \
        ("No surface above 55% win rate in the last 3 years" if ranked
         else "Insufficient surface data (<12 matches per surface)")
    weak_str = "; ".join(f"weak on {l} ({p:.0f}%, n={n})" for l, p, n in worst)
    if weak_str:
        weaknesses = f"{weaknesses}; {weak_str}"

    # Matchupi izvedeni iz stila — eksplicitno označeni kao izvedeni, ne skautirani
    fav = tough = "Cannot be determined from available data"
    if style.startswith("Big server") or style.startswith("Serve-led"):
        fav = "Weak returners on fast courts; anyone in a tiebreak shootout"
        tough = "Elite returners and movers; slow/high-bouncing courts that neutralise serve"
    elif style.startswith("Elite returner") or style.startswith("Defensive"):
        fav = "Big servers on slow courts where returns come back; error-prone aggressors"
        tough = "Elite servers on fast courts (few break chances); short-point attackers"
    elif style.startswith("Solid-serving") or style.startswith("Balanced") or style.startswith("All-court"):
        fav = "One-dimensional opponents whose single weapon can be neutralised"
        tough = "Players with a clear elite weapon (serve or return) they cannot match"

    if hold is not None:
        strengths = f"{strengths} [hold {hold}%, return {ret}%, aces/match {ace}]"

    # Confidence po kolicini dokaza
    if web and total_matches >= 40 and not elo_missing:
        conf = "Med"
    elif total_matches >= 40 and not elo_missing:
        conf = "Med-Low"
    else:
        conf = "Low"

    notes = []
    if web:
        notes.append(web["note"])
        # Ako vanjski izvor tvrdi "big serve", a izmjereni hold to ne potvrduje, to je
        # informacija sama po sebi — model mora vidjeti sukob, ne jednu stranu.
        claims_serve = "big serve" in web["note"].lower() or "serve is the weapon" in web["note"].lower()
        if claims_serve and hold is not None and hold < 79:
            notes.append(f"CONFLICT: the external description claims a big serve, but the "
                         f"measured hold rate is only {hold}% with {ret}% return points won — "
                         f"at tour level the numbers describe a returner, not a server. "
                         f"Trust the measured figures over the label.")
    notes.append("Profile DERIVED from measured data (3y surface W-L, serve/return "
                 "statistics), not from independent scouting.")
    if total_matches and total_matches >= 80 and (rec.get("rank") or 999) > 100:
        notes.append("NOTE: 3-year W-L includes Challenger/ITF level — tour-level "
                     "quality is likely lower than the raw percentage suggests.")
    if elo_missing:
        notes.append("NOTE: no real ELO rating available (fallback 1500) — ratings-based "
                     "comparisons for this player are unreliable.")
    if web and web.get("hand"):
        notes.insert(0, web["hand"] + ".")

    return {
        "player_name": _norm_key(name),
        "display_name": name,
        "rank": rec.get("rank"),
        "country": rec.get("country") or None,
        # stupac je VARCHAR(30) — puni opis (backhand, visina) ide u note
        "hand": (((web or {}).get("hand") or "Cannot be determined").split(",")[0]
                 .split(";")[0].strip())[:30],
        "style": style,
        "best_surfaces": best_str,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "favourable_matchups": fav,
        "tough_matchups": tough,
        "note": " ".join(notes)[:900],
        "confidence": conf,
        "source_date": "2026-07-31",
    }


def main(dry_run):
    with io.open(DATA, encoding="utf-8") as f:
        recs = json.load(f)
    existing = {_norm_key(r.get("display_name") or "")
                for r in db._select("player_scouting", select="display_name", limit=300)}
    # Preskoci one koji VEC imaju profil pod drugom varijantom imena (crtice, srednja imena) —
    # runtime lookup ih fuzzy matchira, pa bi novi zapis bio duplikat.
    skip = {"felix auger aliassime", "jaume antoni munar clar", "pablo carreno busta"}
    def _dedash(x):
        return _norm_key(x).replace("-", " ")
    profiles = [build(r) for r in recs if _dedash(r["name"]) not in skip]

    by_conf = {}
    for p in profiles:
        by_conf[p["confidence"]] = by_conf.get(p["confidence"], 0) + 1
    print(f"Generirano profila: {len(profiles)}  -> po confidence: {by_conf}")
    for p in profiles[:4]:
        print(f"\n  #{p['rank']} {p['display_name']} [{p['confidence']}]")
        print(f"     style: {p['style']}")
        print(f"     best : {p['best_surfaces']}")
        print(f"     str  : {p['strengths'][:110]}")
        print(f"     weak : {p['weaknesses'][:110]}")

    # Ispravci POSTOJEĆIH profila (izvedeni iz naših zabilježenih mečeva)
    corr_rows = []
    for key, patch in _CORRECTIONS.items():
        cur = db._select("player_scouting", select="*",
                         filters={"player_name": f"eq.{key}"}, limit=1)
        if not cur:
            print(f"  ISPRAVAK preskočen (nema profila): {key}")
            continue
        row = dict(cur[0])
        row.pop("updated_at", None)
        row.update(patch)
        row["source_date"] = "2026-07-31"
        corr_rows.append(row)
        print(f"  ISPRAVAK: {row['display_name']} -> confidence "
              f"{patch.get('confidence', row.get('confidence'))}")

    if dry_run:
        print("\n[dry-run] ništa nije upisano.")
        return
    if corr_rows:
        db._rest("POST", "player_scouting", body=corr_rows,
                 prefer="return=representation,resolution=merge-duplicates",
                 params={"on_conflict": "player_name"})
        print(f"  ispravljeno postojećih profila: {len(corr_rows)}")
    saved = 0
    for i in range(0, len(profiles), 40):
        batch = profiles[i:i + 40]
        db._rest("POST", "player_scouting", body=batch,
                 prefer="return=representation,resolution=merge-duplicates",
                 params={"on_conflict": "player_name"})
        saved += len(batch)
    print(f"\nUpisano/ažurirano: {saved}")
    print(f"Ukupno u tablici: {len(db._select('player_scouting', select='player_name', limit=400))}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
