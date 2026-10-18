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
  K5   kvota 1,35-1,43             od 07.09.   n>=100 i edge <= -5pp -> zona (1,35, 1,60)
                                               (27.09.2026 12:16: bilo n>=20; trziste u pojasu +3,7pp)
  K10  oblik pojaseva              od 14.09.   1,35-1,65 < 0 i (1,20-1,35 > 0 ili 1,65-1,85 > 0),
                                               n>=25 po pojasu -> izricit bonus po pojasu umjesto edge_bonus
  K11  R16+QF                      od 14.09.   n>=20, ostatak <= -5pp i losije od ostalih rundi
                                               -> kazna u _score_combo (NIKAD u promptu)
  K17  pick s High profilom        od 27.09.   n>=30 i edge <= -5pp -> kazna -3pp; > 0 -> odbaciti
  K18  hard ATP 250                od 27.09.   n>=30 i edge <= -5pp -> najvise 1 takva noga po
                                               tiketu; > 0 -> odbaciti
  K19  pauza >= 21 dan             od 27.09.   n>=40 (pick ili protivnik); predznak kao na trzistu
                                               (pick s pauzom < 0, protivnik s pauzom > 0)
  K13  protivnik s vijesti o ozljedi od 28.09.  (snapshot v23, Google News, dodano 27.09.2026 12:03)
                                               n>=40 i edge >= ostali + 5pp -> prijedlog korisniku;
                                               razlika <= 0 -> samo biljezenje
  K20  Intuicija (sjena)           od 28.09.   provjere na 150 i 300 zapisanih procjena (poslije svakih +300):
                                               r >= +0,12 i interval iznad 0 (uz 150 -> r >= 0,16), gornja
                                               tercila >= +3pp i >= 3pp iznad donje, r > 0 u obje polovice
                                               -> prijedlog korisniku; inace uci dalje (27.09.2026 12:45)
  KONS konsenzus >= +1pp           od 08.09.   do 31.10.2026: n>=60 i edge > +5pp -> tvrdi uvjet;
                                               edge < 0 -> maknuti bonus
                                               >>> BONUS UKLONJEN 18.10.2026 12:37 (korisnik, 3a);
                                               ovdje se i dalje samo PRATI za eventualni novi test
  K22  ELO i servis+povrat (hard)  od 19.10.   150 hard pickova: r(ELO jaz, ostatak) >= +0,10 ILI
                                               r(servis+povrat jaz, ostatak) >= +0,10, interval iznad 0,
                                               isti predznak u obje polovice -> prijedlog; oba r <= 0 -> pada
                                               (DI K22, 18.10.2026 10:09)
  K24  Nose u sjeni (nose-v1)      od 19.10.   G1 mina (IZBJEGAVAJ): probir n=60 (edge >= +3 -> PAO),
                                               odluka n=150 (<= -5pp, interval < 0, polovice < 0);
                                               G2 vrijednost na protivniku: isto, zrcalno (+5pp);
                                               G3 r(P_own - cijena, ostatak) >= +0,10 uz n=300.
                                               Pravilo zivi u agent.nose.gate_status (PRAGOVI_B 12:20)
  L4   upozorenje AI recenzenta    od 19.10.   30 novih oznacenih noga; na spojenom uzorku uparena
                                               razlika (oznacena − ostale noge istog tiketa) <= -5pp
                                               i interval ispod 0 -> tek tada kandidat (DI 18.10. 10:09)
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
        # 04.10.2026 19:27: analize s dokazano TUĐIM ELO-om (Munar je dobivao ELO Jaya Clarkea,
        # revizija 04.10.2026) ne ulaze u mjerenja — model je na njima čitao lažni podatak.
        if cs.get("elo_suspect"):
            continue
        a, b = ("p1", "p2") if is_p1 else ("p2", "p1")
        mp = cs.get("market_p")
        mp_pick = (mp if is_p1 else 1 - mp) if isinstance(mp, (int, float)) else None
        # K22 (18.10.2026 12:44): ELO jaz na podlozi i jaz servis+povrat, oba iz perspektive picka.
        eg = cs.get("elo_gap_surface")
        elo_gap = ((eg if is_p1 else -eg) if isinstance(eg, (int, float)) else None)
        sv_a, rt_a = safe_float(cs.get(f"{a}_serve_pts_won")), safe_float(cs.get(f"{a}_return_won"))
        sv_b, rt_b = safe_float(cs.get(f"{b}_serve_pts_won")), safe_float(cs.get(f"{b}_return_won"))
        sr_gap = ((sv_a + rt_a) - (sv_b + rt_b)) if all(
            isinstance(x, float) and x > 0 for x in (sv_a, rt_a, sv_b, rt_b)) else None
        # K24 (18.10.2026 12:44): Nose zapis iz dnevnog runa (samo nose-v1, bez greske).
        nz = cs.get("nose") if isinstance(cs.get("nose"), dict) else {}
        nz = nz if (nz.get("version") == "nose-v1" and not nz.get("error")) else {}
        out.append({
            "date": str(r.get("match_date") or "")[:10], "odds": po, "p": p,
            "win": 1.0 if r.get("prediction_correct") else 0.0,
            "round": (r.get("round") or "").upper(), "round_source": cs.get("round_source") or "",
            "surface": (r.get("surface") or "").lower(), "level": r.get("tournament_level") or "",
            "scout_pick": cs.get(f"{a}_scouting_confidence"),
            "rest_pick": cs.get(f"{a}_days_rest"), "rest_opp": cs.get(f"{b}_days_rest"),
            "gap": (100 * (mp_pick - p)) if mp_pick is not None else None,
            # K13 (27.09.2026 12:03): broj naslova o ozljedi iz Google Newsa (v23);
            # None = nema zapisa ili dohvat nije uspio (tada se redak ne broji).
            "ctxv": cs.get("context_version") or 0,
            "inj_pick": (cs.get(f"{a}_gnews") or {}).get("injury_n"),
            "inj_opp": (cs.get(f"{b}_gnews") or {}).get("injury_n"),
            # K20 (27.09.2026 12:33): procjena Intuicije za NAS pick, zapisana prije meca.
            "int_edge": ((cs.get("intuicija") or {}).get("pick") or {}).get("edge_pp"),
            "elo_gap": elo_gap, "sr_gap": sr_gap,
            "nose_suit": nz.get("ticket_suitability"),
            "nose_p_own": (nz.get("pick_quality") or {}).get("p_own"),
            "nose_opp_value": bool((nz.get("vs_market") or {}).get("opp_value")),
        })
    return out


def _corr(xs, ys):
    """(r, donja granica 95%, gornja granica 95%) — Fisherova transformacija."""
    import math
    n = len(xs)
    if n < 10:
        return None, None, None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None, None, None
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
    z = math.atanh(max(min(r, 0.999), -0.999))
    se = 1 / math.sqrt(max(n - 3, 1))
    return r, math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


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
    # Prag n>=100 od 27.09.2026 12:16 (bio 20): povijesni laboratorij — favoriti u 1,35-1,43 na
    # trzistu +3,7pp (n=1.364), pa uz n=20 (interval ±21pp) "potvrda" bi vjerojatno bila sum.
    st = "POTVRDJEN" if n >= 100 and e <= -5 else ("PAO" if n >= 100 and e > 0 else "CEKA")
    return [("K5  kvota 1,35-1,43 (od 07.09., n>=100)", n, e, st)]


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
    # ZATVOREN 04.10.2026 19:27 (revizija 04.10.): u zadanom roku (dva dovrsena turnira od
    # 13.09., runde rucne) R16+QF -1,5pp n=31, BOLJE od ostalih rundi (-3,5pp); povijest: trziste
    # u R16/QF nema rupu. Brojke se i dalje ispisuju samo radi pracenja.
    st = "ZATVOREN 04.10."
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


def k13(rows):
    """Pickovi protiv igraca s vijesti o ozljedi (DI K13, prag zapisan 27.09.2026 11:58)."""
    s = [r for r in rows if r["ctxv"] >= 23 and r["inj_opp"] is not None]
    inj = [r for r in s if r["inj_opp"] >= 1]
    rest = [r for r in s if r["inj_opp"] == 0]
    n1, e1 = edge(inj)
    n2, e2 = edge(rest)
    if n1 >= 40 and e1 is not None and e2 is not None:
        st = "POTVRDJEN" if e1 - e2 >= 5 else ("PAO" if e1 - e2 <= 0 else "NEJASNO")
    else:
        st = "CEKA"
    return [("K13 protivnik s vijesti o ozljedi (v23)", n1, e1, st),
            ("    protivnik bez takve vijesti", n2, e2, "")]


def k20(rows):
    """Intuicija u sjeni (DI K20). Pravilo zivi u agent.intuicija.gate_status (jedno mjesto);
    dvije provjere: na 150 pa na 300 zapisanih procjena (27.09.2026 12:45)."""
    from agent.intuicija import gate_status
    pairs = [(r["int_edge"], 100 * (r["win"] - r["p"]), r["date"]) for r in rows
             if isinstance(r["int_edge"], (int, float))]
    g = gate_status(pairs)
    if g["n"] < 150:
        return [(f"K20 Intuicija: {g['verdict']}", g["n"], None, "CEKA")]
    st = "POTVRDJEN" if g["passed"] else "UCI DALJE"
    return [(f"K20 Intuicija {g['stage']}: r={g['r']:+.3f} (treba {g['need_r']:.2f})", g["n"], g["top"], st),
            ("    donja trecina procjene", g["n"] // 3, g["bottom"], "")]


def kons(rows):
    s = [r for r in rows if r["date"] >= "2026-09-08" and r["gap"] is not None]
    pos = [r for r in s if r["gap"] >= 1]
    n, e = edge(pos)
    # 18.10.2026 12:37: bonus uklonjen iz odabira (korisnik, 3a). Mjera ostaje radi eventualnog
    # novog testa — novi prag se zapisuje UNAPRIJED u DECISION_INPUTS, ne ovdje naknadno.
    st = "UKLONJEN 18.10. (prati se)"
    return [("KONS konsenzus >= +1pp (od 08.09.)", n, e, st),
            ("     mecevi s konsenzusom uopce", len(s), None, "")]


def k22(rows):
    """ELO jaz i servis+povrat na 150 hard pickova od 19.10.2026 (DI K22, prag 18.10.2026 10:09)."""
    s = sorted([r for r in rows if r["date"] >= "2026-10-19" and "hard" in r["surface"]],
               key=lambda r: r["date"])
    out, st_parts = [], []
    for key, label in (("elo_gap", "ELO jaz na podlozi"), ("sr_gap", "servis+povrat jaz")):
        ss = [r for r in s if r[key] is not None]
        r_, lo, hi = _corr([r[key] for r in ss], [r["win"] - r["p"] for r in ss])
        h = len(ss) // 2
        r1 = _corr([r[key] for r in ss[:h]], [r["win"] - r["p"] for r in ss[:h]])[0]
        r2 = _corr([r[key] for r in ss[h:]], [r["win"] - r["p"] for r in ss[h:]])[0]
        st_parts.append((len(ss), r_, lo, r1, r2))
        txt = (f"K22 {label}: r={r_:+.3f} [{lo:+.2f}, {hi:+.2f}]" if r_ is not None
               else f"K22 {label}: r = -")
        out.append((txt, len(ss), None, ""))
    n_ok = min(p[0] for p in st_parts)
    if n_ok < 150:
        st = "CEKA"
    elif any(p[1] is not None and p[1] >= 0.10 and p[2] > 0 and p[3] is not None and p[4] is not None
             and p[3] > 0 and p[4] > 0 for p in st_parts):
        st = "POTVRDJEN"
    elif all(p[1] is not None and p[1] <= 0 for p in st_parts):
        st = "PAO"
    else:
        st = "CEKA (+150)"
    out[0] = (out[0][0], out[0][1], out[0][2], st)
    return out


def k24(rows):
    """Nose u sjeni (nose-v1). Pravilo zivi u agent.nose.gate_status (PRAGOVI_B 18.10.2026 12:20)."""
    from agent.nose import gate_status
    s = [{"suit": r["nose_suit"], "win": r["win"], "p": r["p"], "date": r["date"],
          "opp_value": r["nose_opp_value"],
          "diff": (r["nose_p_own"] - r["p"]) if isinstance(r["nose_p_own"], (int, float)) else None}
         for r in rows if r["nose_suit"] and r["nose_suit"] != "NEMA PODATAKA"]
    g = gate_status(s)
    g3 = g["G3"]
    return [("K24 Nose G1 mina (IZBJEGAVAJ)", g["G1"]["n"], g["G1"]["edge"], g["G1"]["status"]),
            ("K24 Nose G2 vrijednost na protivniku (njegov edge)", g["G2"]["n"], g["G2"]["edge"], g["G2"]["status"]),
            (f"K24 Nose G3 vlastita procjena r={g3['r']:+.3f}" if g3["r"] is not None
             else "K24 Nose G3 vlastita procjena", g3["n"], None, g3["status"])]


def l4(_rows):
    """Upozorenje AI recenzenta ("X carries the most risk") — PRACENJE od 19.10.2026 (DI 18.10.)."""
    import math
    import re
    import unicodedata

    def norm(x):
        x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z ]", " ", x)

    def pull(table, select, extra=None):
        out, off = [], 0
        while True:
            p = {"select": select, "offset": str(off), "limit": "1000"}
            p.update(extra or {})
            ch = db._rest("GET", table, params=p)
            out.extend(ch)
            if len(ch) < 1000:
                break
            off += 1000
        return out

    tk = pull("tickets", "id,ticket_date,status,reviewer_warning", {"status": "in.(won,lost)"})
    tm = pull("ticket_matches", "ticket_id,player1,player2,pick,match_date,result")
    am = pull("analyzed_matches", "player1,player2,match_date,bookmaker_odds_p1,bookmaker_odds_p2,"
                                  "context_snapshot", {"prediction_correct": "not.is.null"})
    price = {}
    for r in am:
        if (r.get("context_snapshot") or {}).get("elo_suspect"):
            continue
        price.setdefault(frozenset([r["player1"], r["player2"]]), []).append(r)
    pairs = []      # (datum tiketa, oznacena noga - prosjek ostalih noga istog tiketa)
    for t in tk:
        m = re.search(r"^(.{3,60}?)\s+carr(?:y|ies)\s+the\s+most\s+risk", str(t.get("reviewer_warning") or "").strip(), re.I)
        if not m:
            continue
        flagged = norm(m.group(1))
        res = []
        for lg in (x for x in tm if x["ticket_id"] == t["id"] and x.get("result") in ("won", "lost")):
            cand = [r for r in price.get(frozenset([lg["player1"], lg["player2"]]), [])
                    if abs((__import__("datetime").date.fromisoformat(str(r["match_date"])[:10])
                            - __import__("datetime").date.fromisoformat(str(lg["match_date"])[:10])).days) <= 2]
            if not cand:
                continue
            r0 = cand[0]
            is1 = lg["pick"] == r0["player1"]
            p = devig_pick_prob(safe_float(r0["bookmaker_odds_p1" if is1 else "bookmaker_odds_p2"]),
                                safe_float(r0["bookmaker_odds_p2" if is1 else "bookmaker_odds_p1"]))
            if p is None:
                continue
            is_flag = any(len(w) >= 4 and w in flagged for w in norm(lg["pick"]).split())
            res.append((is_flag, (1.0 if lg["result"] == "won" else 0.0) - p))
        fl = [x for f, x in res if f]
        ot = [x for f, x in res if not f]
        if len(fl) == 1 and ot:
            pairs.append((str(t["ticket_date"])[:10], fl[0] - sum(ot) / len(ot)))
    new = [d for d, _ in pairs if d >= "2026-10-19"]
    diffs = [x for _, x in pairs]
    n = len(diffs)
    if n >= 2:
        mu = sum(diffs) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (n - 1))
        lo, hi = 100 * (mu - 1.96 * sd / math.sqrt(n)), 100 * (mu + 1.96 * sd / math.sqrt(n))
    else:
        mu, lo, hi = None, None, None
    if len(new) < 30:
        st = f"CEKA ({len(new)}/30 novih)"
    elif mu is not None and 100 * mu <= -5 and hi < 0:
        st = "KANDIDAT"
    else:
        st = "OPIS (prag nije ispunjen)"
    lab = (f"L4 recenzent: uparena razlika [{lo:+.1f}, {hi:+.1f}]" if mu is not None else "L4 recenzent")
    return [(lab, n, (100 * mu) if mu is not None else None, st)]


ALL = {"K5": k5, "K10": k10, "K11": k11, "K13": k13, "K17": k17, "K18": k18, "K19": k19, "K20": k20,
       "KONS": kons, "K22": k22, "K24": k24, "L4": l4}

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
