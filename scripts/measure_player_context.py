# -*- coding: utf-8 -*-
"""Mjerenje triju igracevih varijabli naspram TRZISNE CIJENE (26.09.2026 17:04).

Varijable (vidi `agent/player_context.py`): omjer protiv ljevaka/desnjaka, ATP pobjede u
sezoni, Grand Slam polufinala/finala. Ova skripta je PRVI stupanj kapije (otkrivanje) i,
ponovno pokrenuta nakon 2-3 nova turnira, DRUGI stupanj (potvrda).

METRIKE SU ZAPISANE PRIJE PODATAKA (26.09.2026, prije prvog pokretanja):
  S1  razlika u broju ATP pobjeda u sezoni (pick - protivnik)      <- korisnikova formulacija
  S2  razlika u postotku ATP pobjeda u sezoni, skupljeno prema 50% s k=4
  G1  razlika u broju GS polufinala (pick - protivnik)
  G2  asimetrija iskustva: pick ima GS polufinale, protivnik nema (1) / obrnuto (-1) / 0
  H1  "rub po ruci": koliko igrac protiv RUKE danasnjeg protivnika odstupa od svog
      prosjeka (skupljeno prema prosjeku s k=10), pick minus protivnik; SAMO mecevi s
      bar jednim ljevakom (desnjak-desnjak nosi prazan signal jer je "protiv desnjaka"
      gotovo isto sto i ukupni omjer)

ISHOD: ostatak = pobjeda picka (1/0) - devigirana SuperSport vjerojatnost picka. Varijabla
koja samo ponavlja kvalitetu igraca (koju kvota vec zna) daje r ~ 0 na ostatku. Tri puta
smo u ovom projektu vidjeli dramatican sirovi nalaz koji je bio cijena (vidi
`value-je-prerusena-cijena` u memoriji), pa se sirova korelacija ispisuje samo usporedbe
radi.

Pokretanje:
    python scripts/measure_player_context.py            # iz baze (nakon --apply backfilla)
    python scripts/measure_player_context.py --local    # iz .cache/player_context/values.json
"""
import sys
import os
import io
import json
import math
import random
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

random.seed(20260926)


def _pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if not sx or not sy:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def _p_value(r, n):
    """Dvostrani P za Pearsonov r (normalna aproksimacija t-distribucije, n>30 dovoljno)."""
    if n < 4 or r != r or abs(r) >= 1:
        return float("nan")
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return math.erfc(abs(t) / math.sqrt(2))


def _boot_ci(x, y, reps=2000):
    idx = list(range(len(x)))
    rs = []
    for _ in range(reps):
        s = [random.choice(idx) for _ in idx]
        r = _pearson([x[i] for i in s], [y[i] for i in s])
        if r == r:
            rs.append(r)
    rs.sort()
    if not rs:
        return (float("nan"), float("nan"))
    return rs[int(0.025 * len(rs))], rs[int(0.975 * len(rs)) - 1]


def _devig(o_pick, o_opp):
    a, b = 1 / o_pick, 1 / o_opp
    return a / (a + b)


def _shrunk(w, n, prior, k):
    return (w + k * prior) / (n + k)


def load_rows(local: bool):
    if local:
        c = os.path.join(_ROOT, ".cache", "player_context")
        rows = json.load(open(os.path.join(c, "analyzed_matches.json"), encoding="utf-8"))
        vals = json.load(open(os.path.join(c, "values.json"), encoding="utf-8"))
        for r in rows:
            r["context_snapshot"] = {**(r.get("context_snapshot") or {}), **vals.get(r["id"], {})}
        return rows
    from database import supabase_client as sb
    out, off = [], 0
    while True:
        rows = sb._rest("GET", "analyzed_matches", params={
            "select": "id,match_date,player1,player2,tournament,tournament_level,round,"
                      "predicted_winner,bookmaker_odds_p1,bookmaker_odds_p2,"
                      "prediction_correct,context_snapshot",
            "prediction_correct": "not.is.null", "order": "match_date.asc",
            "offset": str(off), "limit": "1000"})
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def build_sample(rows):
    """Jedan zapis po razrijesenoj analizi: pick, cijena, ostatak i varijable."""
    out = []
    for r in rows:
        if r.get("prediction_correct") is None:
            continue
        cs = r.get("context_snapshot") or {}
        c1, c2 = cs.get("p1_ctx") or {}, cs.get("p2_ctx") or {}
        if not c1 or not c2 or c1.get("error") or c2.get("error"):
            continue
        o1, o2 = float(r.get("bookmaker_odds_p1") or 0), float(r.get("bookmaker_odds_p2") or 0)
        if o1 <= 1.0 or o2 <= 1.0:
            continue
        pick = (r.get("predicted_winner") or "").strip().lower()
        if pick == (r.get("player1") or "").strip().lower():
            me, op, om, oo = c1, c2, o1, o2
        elif pick == (r.get("player2") or "").strip().lower():
            me, op, om, oo = c2, c1, o2, o1
        else:
            continue
        won = 1.0 if r["prediction_correct"] else 0.0
        mkt = _devig(om, oo)
        rec = {"date": r["match_date"], "won": won, "mkt": mkt, "resid": won - mkt,
               "level": r.get("tournament_level") or "", "round": r.get("round") or "",
               "odds": om}

        # S1/S2 — sezona
        sm, so = me.get("season") or {}, op.get("season") or {}
        nm = sm.get("tour_w", 0) + sm.get("tour_l", 0)
        no = so.get("tour_w", 0) + so.get("tour_l", 0)
        rec["S1"] = sm.get("tour_w", 0) - so.get("tour_w", 0)
        rec["S2"] = (_shrunk(sm.get("tour_w", 0), nm, 0.5, 4)
                     - _shrunk(so.get("tour_w", 0), no, 0.5, 4))

        # G1/G2 — Grand Slam
        gm, go = me.get("gs") or {}, op.get("gs") or {}
        rec["G1"] = gm.get("sf", 0) - go.get("sf", 0)
        rec["G2"] = (1 if gm.get("sf", 0) > 0 and go.get("sf", 0) == 0
                     else -1 if go.get("sf", 0) > 0 and gm.get("sf", 0) == 0 else 0)
        rec["gs_any"] = gm.get("sf", 0) > 0 or go.get("sf", 0) > 0

        # H1 — rub po ruci danasnjeg protivnika
        def _edge(ctx, opp_hand):
            vs = ctx.get("vs_hand") or {}
            L, R = vs.get("L") or {}, vs.get("R") or {}
            w_all = L.get("w", 0) + R.get("w", 0)
            n_all = w_all + L.get("l", 0) + R.get("l", 0)
            if opp_hand not in ("L", "R") or n_all < 10:
                return None
            h = vs.get(opp_hand) or {}
            p_all = w_all / n_all
            n_h = h.get("w", 0) + h.get("l", 0)
            return _shrunk(h.get("w", 0), n_h, p_all, 10) - p_all, n_h

        em = _edge(me, me.get("opp_hand"))
        eo = _edge(op, op.get("opp_hand"))
        rec["lefty_involved"] = "L" in (me.get("hand"), op.get("hand"))
        rec["H1"] = (em[0] - eo[0]) if (em and eo) else None
        rec["H1_n"] = (em[1], eo[1]) if (em and eo) else None
        out.append(rec)
    return out


def report(sample, key, label, subset=None, note=""):
    rows = [s for s in sample if s.get(key) is not None and (subset is None or subset(s))]
    x = [float(s[key]) for s in rows]
    if len(rows) < 20:
        print(f"{label:48s} n={len(rows):4d}  (premalo za mjerenje)")
        return
    y_res = [s["resid"] for s in rows]
    y_won = [s["won"] for s in rows]
    r_res, r_won = _pearson(x, y_res), _pearson(x, y_won)
    lo, hi = _boot_ci(x, y_res)
    half = len(rows) // 2
    r1 = _pearson(x[:half], y_res[:half])
    r2 = _pearson(x[half:], y_res[half:])
    print(f"{label:48s} n={len(rows):4d}  r(ostatak)={r_res:+.3f} P={_p_value(r_res, len(rows)):.3f} "
          f"CI[{lo:+.3f},{hi:+.3f}]  polovice {r1:+.3f}/{r2:+.3f}  | sirovo r(pobjeda)={r_won:+.3f}"
          + (f"  {note}" if note else ""))


def groups(sample, key, cuts, label, subset=None):
    rows = [s for s in sample if s.get(key) is not None and (subset is None or subset(s))]
    print(f"  {label}:")
    for lo, hi, name in cuts:
        g = [s for s in rows if lo <= s[key] < hi]
        if not g:
            print(f"    {name:22s} n=   0")
            continue
        wr = sum(s["won"] for s in g) / len(g)
        mk = sum(s["mkt"] for s in g) / len(g)
        roi = sum((s["odds"] - 1) if s["won"] else -1 for s in g) / len(g)
        print(f"    {name:22s} n={len(g):4d}  pobjeda {100 * wr:5.1f}%  trziste {100 * mk:5.1f}%  "
              f"rub {100 * (wr - mk):+5.1f}pp  ROI {100 * roi:+6.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args()
    sample = build_sample(load_rows(a.local))
    sample.sort(key=lambda s: s["date"])
    print(f"Uzorak: {len(sample)} razrijesenih analiza s kvotom i obje vrijednosti "
          f"({sample[0]['date'] if sample else '-'} -> {sample[-1]['date'] if sample else '-'})")
    print(f"Prosjecni rub svih pickova naspram trzista: "
          f"{100 * sum(s['resid'] for s in sample) / max(1, len(sample)):+.1f}pp\n")

    print("=== SEZONA ===")
    report(sample, "S1", "S1 razlika u broju ATP pobjeda")
    report(sample, "S2", "S2 razlika u postotku ATP pobjeda (k=4)")
    groups(sample, "S2", [(-9, -0.15, "protivnik jaci 15pp+"), (-0.15, -0.05, "protivnik 5-15pp"),
                          (-0.05, 0.05, "podjednako"), (0.05, 0.15, "pick 5-15pp"),
                          (0.15, 9, "pick jaci 15pp+")], "S2 po razredima")

    print("\n=== GRAND SLAM ISKUSTVO ===")
    report(sample, "G1", "G1 razlika u broju GS polufinala")
    report(sample, "G1", "G1 samo mecevi gdje bar jedan ima GS SF", subset=lambda s: s["gs_any"])
    report(sample, "G1", "G1 samo Grand Slam", subset=lambda s: s["level"] == "Grand Slam")
    groups(sample, "G2", [(-1, 0, "samo protivnik ima SF"), (0, 1, "izjednaceno"),
                          (1, 2, "samo pick ima SF")], "G2 asimetrija iskustva")
    groups(sample, "G2", [(-1, 0, "samo protivnik ima SF"), (0, 1, "izjednaceno"),
                          (1, 2, "samo pick ima SF")], "G2 samo QF/SF/F",
           subset=lambda s: s["round"] in ("QF", "SF", "F"))

    print("\n=== RUKA PROTIVNIKA ===")
    report(sample, "H1", "H1 rub po ruci, mecevi s ljevakom",
           subset=lambda s: s["lefty_involved"])
    report(sample, "H1", "H1 rub po ruci, desnjak-desnjak (kontrola)",
           subset=lambda s: not s["lefty_involved"])
    groups(sample, "H1", [(-9, -0.04, "protivnik bolji 4pp+"), (-0.04, 0.04, "podjednako"),
                          (0.04, 9, "pick bolji 4pp+")], "H1 po razredima (s ljevakom)",
           subset=lambda s: s["lefty_involved"])
    n_l = [s for s in sample if s["lefty_involved"]]
    if n_l:
        ns = [min(s["H1_n"]) for s in n_l if s.get("H1_n")]
        ns.sort()
        if ns:
            print(f"  medijan broja meceva protiv te ruke (manji od dvojice): {ns[len(ns) // 2]}")
    print("\nNAPOMENA: 7 testova na istom korpusu — uz toliko pokusaja jedan P<0,05 ocekuje se")
    print("u ~30% slucajeva i bez ikakvog stvarnog ucinka. Presudan je PREDZNAK u obje")
    print("polovice i CI koji ne prelazi nulu, ne P.")


if __name__ == "__main__":
    main()
