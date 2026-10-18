# -*- coding: utf-8 -*-
"""Jedini plaćeni probni poziv nove ere 881d89f8 (18.10.2026 16:47, korisnik odobrio).

RADI SAMO NA GRANI `tml-era-881d89f8` (18.10.2026 17:34: era nije uvedena u master; izlaz je
spremljen u zivi_poziv_TML/, pa skripta ionako ne zove model ponovno).

Meč: Zverev – Davidovich Fokina, Šangaj SF 17.10.2026 (naš pick Zverev, izgubio). Poziv ide kroz
PRAVU `predictor.analyze_match` (novi `_sr_prompt`, novi predložak, obrada odgovora, snapshot),
s JEDNIM pokušajem (bez ponavljanja na 6.000), pa se plaća točno jedan poziv.

Ulazi:
  - servis/povrat: TML složen zaključno sa 16.10.2026 (u datotekama turnira u tijeku datum je datum
    meča, pa SF 17.10. i finale 18.10. NISU uključeni) -> isto što bi jutarnji run vidio tog dana;
  - ostalo iz `context_snapshot` toga meča (baza, 18.10. 09:02): ELO, rang, forma, put na turniru,
    tiebreak/odlučujući setovi, naslovi, scouting (stanje prije današnjih izmjena ranga);
  - H2H, povijest ždrijeba i trend forme nisu spremljeni u snapshotu -> u ovom testu "not loaded".
Ovo je provjera OBLIKA (JSON, duljina, navodi li brojke 12 mj. i miješa li ih s karijerom), ne
mjerenje točnosti. Ništa se ne sprema u bazu. Izlaz: revizije/2026-10-18/zivi_poziv_TML/.
"""
import datetime as dt
import json
import os
import sys

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
OUT = os.path.join(ROOT, "revizije", "2026-10-18", "zivi_poziv_TML")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

if os.path.exists(os.path.join(OUT, "odgovor.json")) and "--ponovi" not in sys.argv:
    print("Probni poziv je već napravljen (odgovor.json postoji) — ne zovem model ponovno.")
    sys.exit(0)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from agent import predictor as pr, tml_forma as tf  # noqa: E402
import update_tml_form as ut  # noqa: E402

REF = dt.date(2026, 10, 16)
t12 = ut.build(ut.local(ut._files(2025, 2026, 2025)), REF, ut.DAYS)
tk = ut.build(ut.local(ut._files(2000, 2026, 2020)), REF, None)

am = json.load(open(os.path.join(ROOT, ".cache", "rev_2026-10-18", "analyzed_matches.json"), encoding="utf-8"))
r = next(x for x in am if x["player1"] == "Alexander Zverev" and "Davidovich" in x["player2"]
         and x["match_date"] == "2026-10-17")
cs = r["context_snapshot"]
sc = {x["display_name"]: x for x in json.load(open(os.path.join(
    ROOT, "revizije", "2026-10-18", "scouting", "player_scouting_prije_2026-10-18.json"), encoding="utf-8"))}


def side(s, name):
    tform = {"matches": cs.get(f"{s}_tourn_form_matches"), "serve_won": cs.get(f"{s}_tourn_form_serve_won"),
             "ace_rate": cs.get(f"{s}_tourn_form_ace_rate"), "bp_saved": cs.get(f"{s}_tourn_form_bp_saved"),
             "bp_conv": cs.get(f"{s}_tourn_form_bp_conv")}
    return {"age": cs.get(f"{s}_age"), "hand": cs.get(f"{s}_hand"), "nationality": cs.get(f"{s}_nationality"),
            "ranking": cs.get(f"{s}_ranking"), "elo_overall": cs.get(f"{s}_elo_overall"),
            "elo_hard": cs.get(f"{s}_elo_surface"), "avg_opp_elo": cs.get(f"{s}_avg_opp_elo"),
            # RapidAPI (karijera) — model ih u novoj eri NE vidi kad TML postoji; ostaju za snapshot
            "serve_points_won": cs.get(f"{s}_serve_pts_won"), "hold_pct": cs.get(f"{s}_hold_pct"),
            "return_points_won": cs.get(f"{s}_return_won"), "first_serve_pct": cs.get(f"{s}_first_serve_pct"),
            "first_serve_points_won": cs.get(f"{s}_first_serve_won"),
            "second_serve_points_won": cs.get(f"{s}_second_serve_won"),
            "aces_per_game": cs.get(f"{s}_aces_per100"), "break_points_saved": cs.get(f"{s}_bp_saved"),
            "break_points_converted": cs.get(f"{s}_bp_converted"),
            "tiebreak_record": cs.get(f"{s}_tiebreak_record"), "decider_record": cs.get(f"{s}_decider_record"),
            "scouting": sc.get(name) or {}, "titles": cs.get(f"{s}_titles") or {},
            "height_cm": cs.get(f"{s}_height_cm"), "weight_kg": cs.get(f"{s}_weight_kg"),
            "plays": cs.get(f"{s}_plays"), "matches_7d": cs.get(f"{s}_matches_7d"), "sets_7d": cs.get(f"{s}_sets_7d"),
            "tournament_path": cs.get(f"{s}_tournament_path"), "tournament_form": tform, "news": "No news",
            "form_recent": {"matches": []}, "surface_summary": {}, "tournament_record": {},
            "sr_tml": tf.prompt_values(name, t12, tk)}


p1, p2 = side("p1", r["player1"]), side("p2", r["player2"])
match = {"player1": r["player1"], "player2": r["player2"], "surface": "Hard", "tournament": r["tournament"],
         "level": r.get("tournament_level") or "ATP Masters 1000", "round": "SF", "date": "2026-10-17",
         "odds_p1": r["bookmaker_odds_p1"], "odds_p2": r["bookmaker_odds_p2"], "local_time": "16:30",
         "session": "day", "weather": "27°C, Clouds, Wind: 17 km/h, Humidity: 60%",
         "court_pace_str": f"{cs.get('court_pace_label')} court (tiebreak share not stored in snapshot)",
         "p1_tourn_best_3y": cs.get("p1_tourn_best_3y"), "p2_tourn_best_3y": cs.get("p2_tourn_best_3y"),
         "schedule_provisional": False, "draw_history": []}

# Polja koja se ne daju rekonstruirati iz snapshota (formatirani nizovi) — upisuju se spremljeni nizovi.
_NL = "not loaded for this test"
OVR = {"p1_form_5": cs["p1_form_5"], "p1_form_10": cs["p1_form_10"], "p2_form_5": cs["p2_form_5"],
       "p2_form_10": cs["p2_form_10"], "p1_surface_record": cs["p1_surface_record"],
       "p2_surface_record": cs["p2_surface_record"], "p1_days_rest": cs["p1_days_rest"],
       "p2_days_rest": cs["p2_days_rest"], "p1_surface_form": _NL, "p2_surface_form": _NL,
       "h2h_overall": _NL, "h2h_surface": _NL, "h2h_last": _NL, "h2h_trend": _NL, "h2h_reliability": _NL,
       "h2h_detailed_stats": _NL, "tournament_draw_history": _NL, "p1_tournament_history": _NL,
       "p2_tournament_history": _NL}
PROMPT = {}


class _T(str):
    def format(self, *a, **kw):
        kw.update(OVR)
        PROMPT["user"] = str.format(self, *a, **kw)
        return PROMPT["user"]


pr.ANALYSIS_PROMPT_TEMPLATE = _T(pr.ANALYSIS_PROMPT_TEMPLATE)
pr._ANALYSIS_MAX_TOKENS = (4000,)          # točno jedan plaćeni poziv, bez ponavljanja
weights = {"elo_ranking": 19, "h2h_context": 4, "recent_form": 17, "serve_return": 23,
           "surface_style": 18, "fatigue_injuries": 12, "tournament_trajectory": 7}   # hard v18 (aktivne)

print("TML ulaz:", {k: p1["sr_tml"].get(k) for k in ("s", "r", "hold", "w", "n12", "izvor", "podaci_do")})
print("TML ulaz:", {k: p2["sr_tml"].get(k) for k in ("s", "r", "hold", "w", "n12", "izvor", "podaci_do")})

if "--suho" in sys.argv:   # besplatna proba: lažni klijent, ništa se ne sprema
    class _B:
        type = "text"
        text = json.dumps({"pick": r["player1"], "confidence": 61, "key_factors": ["x"], "analysis": "x"})
    class _U:
        output_tokens = input_tokens = 1
    class _R:
        content, stop_reason, usage = [_B()], "end_turn", _U()
    class _M:
        def create(self, **kw):
            PROMPT["system"] = kw["system"][0]["text"]
            return _R()
    class _C:
        messages = _M()
    pr._get_client = lambda: _C()
    pr.analyze_match(match, p1, p2, {}, weights, "")
    u = PROMPT["user"]
    i = u.find("--- Serve & return")
    print(u[i:i + 700])
    j = u.find("--- Serve & return", i + 10)
    print(u[j:j + 700])
    print("scouting:", [ln[:300] for ln in u.splitlines() if ln.startswith("Scouting ")])
    print("duljina user:", len(u), "| system:", len(PROMPT["system"]))
    sys.exit(0)

res = pr.analyze_match(match, p1, p2, {}, weights, "")

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "prompt_user.txt"), "w", encoding="utf-8") as fo:
    fo.write(PROMPT.get("user", ""))
with open(os.path.join(OUT, "odgovor.json"), "w", encoding="utf-8") as fo:
    json.dump({"vrijeme": dt.datetime.now().strftime("%d.%m.%Y %H:%M"), "rezultat": res,
               "stari": {"pick": r.get("predicted_winner"), "confidence": r.get("predicted_confidence"),
                         "rules_hash": (cs.get("model_stamp") or {}).get("rules_hash"),
                         "full_analysis": r.get("full_analysis")}},
              fo, ensure_ascii=False, indent=1, default=str)

snap = res.get("context_snapshot") or {}
meta = snap.get("analysis_call") or {}
print("\nmeta:", meta)
print("era:", snap.get("model_stamp"))
print("pick:", res.get("pick"), "| conf:", res.get("confidence"), "| stari:", r.get("predicted_winner"),
      r.get("predicted_confidence"))
print("p1_sr_prompt:", snap.get("p1_sr_prompt"))
print("p2_sr_prompt:", snap.get("p2_sr_prompt"))
print("\nKEY FACTORS:")
for k in res.get("key_factors") or []:
    print(" -", k)
print("\nANALYSIS:", res.get("analysis"))
