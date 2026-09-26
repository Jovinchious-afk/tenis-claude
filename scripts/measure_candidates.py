# -*- coding: utf-8 -*-
"""Kapija jednom naredbom — mjeri kandidate iz registra na NOVIM podacima (26.09.2026 20:28).

NASTALO na reviziji 26.09.2026 (revizije/2026-09-26/REVIZIJA_2026-09-26.md). Kapija od
06.09.2026 kaze: nijedan nalaz ne ulazi u kod dok se ne potvrdi na mecevima na kojima NIJE
nadjen, uz prag zapisan UNAPRIJED. Do danas se svaki kandidat mjerio ad-hoc skriptom koja
je nakon sesije nestajala. Ova skripta drzi definicije i pragove na jednom mjestu, pa je
provjera ponovljiva i bez prostora za "pomicanje stative".

SAMO CITA iz Supabasea. Ne mijenja nista.

    python scripts/measure_candidates.py            # svi kandidati
    python scripts/measure_candidates.py --only K18 # jedan

Svaka mjera je naspram DEVIGIRANE SuperSport cijene (obje kvote sa screenshota):
edge = stvarni postotak pogodaka - prosjek devigirane cijene, u postotnim bodovima.

PRAGOVI (zapisani PRIJE podataka; isti su u DECISION_INPUTS.md, sekcija 0a):
  K5   kvota 1,35-1,43             od 07.09.   n>=20 i edge <= -5pp  -> zona (1,35, 1,60)
  K10  oblik pojaseva              od 14.09.   1,35-1,65 < 0 i (1,20-1,35 > 0 ili 1,65-1,85 > 0),
                                               n>=25 po pojasu -> izricit bonus po pojasu umjesto edge_bonus
  K11  R16+QF                      od 14.09.   n>=20, ostatak <= -5pp i losije od ostalih rundi
                                               -> kazna u _score_combo (NIKAD u promptu)
  K17  pick s High profilom        od 27.09.   n>=30 i edge <= -5pp -> kazna -3pp; > 0 -> odbaciti
  K18  hard ATP 250                od 27.09.   n>=30 i edge <= -5pp -> najvise 1 takva noga po
                                               tiketu; > 0 -> odbaciti
  K19  pauza >= 21 dan             od 27.09.   n>=40 (pick ili protivnik); predznak kao na trzistu
                                               (pick s pauzom < 0, protivnik s pauzom > 0)
  KONS konsenzus >= +1pp           od 08.09.   do 31.10.2026: n>=60 i edge > +5pp -> tvrdi uvjet;
                                               edge < 0 -> maknuti bonus
"""
import sys
import os
import io
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from database import supabase_client as db
from utils.helpers import devig_pick_prob, safe_float


def load_rows() -> list:
    """Razrijesene analize s pickom i obje kvote, poravnate na stranu picka."""
    raw = []
    off = 0
    while True:
        chunk = db._rest("GET", "analyzed_matches", params={
            "select": "match_date,player1,player2,predicted_winner,actual_winner,prediction_correct,"
                      "bookmaker_odds_p1,bookmaker_odds_p2,round,surface,tournament_level,context_snapshot",
            "prediction_correct": "not.is.null", "order": "match_date.asc",
            "offset": str(off), "limit": "1000"})
        raw.extend(chunk)
        if len(chunk) < 1000:
            break
        off += 1000
    out = []
    for r in raw:
        pick, p1, p2 = r.get("predicted_winner") or "", r.get("player1") or "", r.get("player2") or ""
        if pick not in (p1, p2) or r.get("actual_winner") not in (p1, p2):
            continue
        is_p1 = pick == p1
        o1, o2 = safe_float(r.get("bookmaker_odds_p1")), safe_float(r.get("bookmaker_odds_p2"))
        po, oo = (o1, o2) if is_p1 else (o2, o1)
        p = devig_pick_prob(po, oo)
        if p is None:
            continue
        cs = r.get("context_snapshot") or {}
        a, b = ("p1", "p2") if is_p1 else ("p2", "p1")
        mp = cs.get("market_p")
        mp_pick = (mp if is_p1 else 1 - mp) if isinstance(mp, (int, float)) else None
        out.append({
            "date": str(r.get("match_date") or "")[:10], "odds": po, "p": p,
            "win": 1.0 if r.get("prediction_correct") else 0.0,
            "round": (r.get("round") or "").upper(), "round_source": cs.get("round_source") or "",
            "surface": (r.get("surface") or "").lower(), "level": r.get("tournament_level") or "",
            "scout_pick": cs.get(f"{a}_scouting_confidence"),
            "rest_pick": cs.get(f"{a}_days_rest"), "rest_opp": cs.get(f"{b}_days_rest"),
            "gap": (100 * (mp_pick - p)) if mp_pick is not None else None,
        })
    return out


def edge(rows: list) -> tuple:
    if not rows:
        return 0, None
    n = len(rows)
    return n, 100 * (sum(r["win"] for r in rows) - sum(r["p"] for r in rows)) / n


def fmt(n, e) -> str:
    return f"n={n:3d}  edge={e:+6.1f}pp" if e is not None else f"n={n:3d}  edge=   -  "


def k5(rows):
    s = [r for r in rows if r["date"] >= "2026-09-07" and 1.35 <= r["odds"] < 1.43]
    n, e = edge(s)
    st = "POTVRDJEN" if n >= 20 and e <= -5 else ("PAO" if n >= 20 and e > 0 else "CEKA")
    return [("K5  kvota 1,35-1,43 (od 07.09.)", n, e, st)]


def k10(rows):
    s = [r for r in rows if r["date"] >= "2026-09-14"]
    bands = {"1,20-1,35": (1.20, 1.35), "1,35-1,65": (1.35, 1.65), "1,65-1,85": (1.65, 1.85)}
    res = {k: edge([r for r in s if lo <= r["odds"] < hi]) for k, (lo, hi) in bands.items()}
    ok_n = all(v[0] >= 25 for v in res.values())
    hole = res["1,35-1,65"][1]
    good = [res["1,20-1,35"][1], res["1,65-1,85"][1]]
    if ok_n and hole is not None and hole < 0 and any(g is not None and g > 0 for g in good):
        st = "POTVRDJEN"
    elif res["1,35-1,65"][0] >= 25 and hole is not None and hole >= 0:
        st = "PAO"
    else:
        st = "CEKA"
    return [(f"K10 pojas {k} (od 14.09.)", v[0], v[1], st if k == "1,35-1,65" else "")
            for k, v in res.items()]


def k11(rows):
    s = [r for r in rows if r["date"] >= "2026-09-14" and r["round"] and r["round_source"] != "cleared_wrong_auto"]
    rq = [r for r in s if r["round"] in ("R16", "QF")]
    ot = [r for r in s if r["round"] not in ("R16", "QF", "DC")]
    n1, e1 = edge(rq)
    n2, e2 = edge(ot)
    if n1 >= 20 and e1 is not None and e1 <= -5 and (e2 is None or e1 < e2):
        st = "POTVRDJEN"
    elif n1 >= 20 and e1 is not None and e1 > 0:
        st = "PAO"
    else:
        st = "CEKA"
    return [("K11 R16+QF (od 14.09., runda poznata)", n1, e1, st),
            ("    ostale runde (kontrola)", n2, e2, "")]


def k17(rows):
    s = [r for r in rows if r["date"] >= "2026-09-27" and r["scout_pick"] == "High"]
    n, e = edge(s)
    st = "POTVRDJEN" if n >= 30 and e <= -5 else ("PAO" if n >= 30 and e > 0 else "CEKA")
    return [("K17 pick s High profilom (od 27.09.)", n, e, st)]


def k18(rows):
    s = [r for r in rows if r["date"] >= "2026-09-27" and r["level"] == "ATP 250" and "hard" in r["surface"]]
    n, e = edge(s)
    st = "POTVRDJEN" if n >= 30 and e <= -5 else ("PAO" if n >= 30 and e > 0 else "CEKA")
    return [("K18 hard ATP 250 (od 27.09.)", n, e, st)]


def k19(rows):
    s = [r for r in rows if r["date"] >= "2026-09-27"]
    pk = [r for r in s if safe_float(r["rest_pick"]) >= 21]
    op = [r for r in s if safe_float(r["rest_opp"]) >= 21]
    n1, e1 = edge(pk)
    n2, e2 = edge(op)
    if n1 + n2 >= 40 and e1 is not None and e2 is not None:
        st = "POTVRDJEN" if (e1 < 0 and e2 > 0) else ("PAO" if (e1 > 0 and e2 < 0) else "NEJASNO")
    else:
        st = "CEKA"
    return [("K19 NAS pick s pauzom >= 21 dan (od 27.09.)", n1, e1, st),
            ("    PROTIVNIK s pauzom >= 21 dan", n2, e2, "")]


def kons(rows):
    s = [r for r in rows if r["date"] >= "2026-09-08" and r["gap"] is not None]
    pos = [r for r in s if r["gap"] >= 1]
    n, e = edge(pos)
    st = "POTVRDJEN" if n >= 60 and e > 5 else ("PAO" if n >= 30 and e < 0 else "CEKA")
    return [("KONS konsenzus >= +1pp (od 08.09.)", n, e, st),
            ("     mecevi s konsenzusom uopce", len(s), None, "")]


ALL = {"K5": k5, "K10": k10, "K11": k11, "K17": k17, "K18": k18, "K19": k19, "KONS": kons}

if __name__ == "__main__":
    # Preusmjerenje izlaza SAMO kad se skripta pokrece — test je uvozi kao modul, a zamjena
    # sys.stdout pri uvozu zatvorila bi izlaz testnom paketu.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    rows = load_rows()
    print(f"Razrijesenih analiza s obje kvote: {len(rows)} (zadnja {rows[-1]['date'] if rows else '-'})\n")
    for key, fn in ALL.items():
        if a.only and key != a.only:
            continue
        for label, n, e, st in fn(rows):
            print(f"  {label:44s} {fmt(n, e)}   {st}")
    print("\nPOTVRDJEN = prag ispunjen -> smije u kod (uz zapis u MODEL_CHANGELOG);"
          " PAO = zatvoriti; CEKA = premalo podataka.")
